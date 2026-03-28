import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional

import pyromod.listen  # noqa: F401
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

from config import API_HASH, APP_ID, ADMINS, PAYOUT_CHANNEL_ID
from database.saas_database import (
    add_bot_user,
    count_bot_users,
    create_withdrawal,
    get_bot_settings,
    get_clone_bot,
    list_clone_bots,
    owner_dashboard,
    set_owner_custom_mongo,
    update_bot_setting,
)

LOGGER = logging.getLogger(__name__)


class CloneRuntimeManager:
    def __init__(self):
        self.clients: Dict[str, Client] = {}
        self._rate_limits = defaultdict(dict)

    async def start_all(self):
        try:
            bots = await list_clone_bots(active_only=True)
        except Exception as e:
            LOGGER.error("failed to fetch clone bots on startup err=%s", e)
            return

        for bot in bots:
            token = bot.get("token")
            if not token:
                continue
            try:
                await self.start_clone(token)
            except Exception as e:
                LOGGER.error("clone autostart failed token=%s err=%s", str(token)[-8:], e)

    async def stop_all(self):
        for token, client in list(self.clients.items()):
            try:
                await client.stop()
            except Exception as e:
                LOGGER.warning("clone stop failed token=%s err=%s", token[-8:], e)

    async def start_clone(self, token: str) -> bool:
        if token in self.clients:
            return True

        try:
            bot = await get_clone_bot(token)
        except Exception as e:
            LOGGER.error("clone fetch failed token=%s err=%s", token[-8:], e)
            return False
        if not bot:
            return False

        app = Client(
            name=f"clone_{abs(hash(token))}",
            api_id=APP_ID,
            api_hash=API_HASH,
            bot_token=token,
            workers=8,
            no_updates=False,
        )
        app.clone_meta = bot

        async def handler(client: Client, message: Message):
            await self._dispatch(client, message)

        app.add_handler(MessageHandler(handler, filters.private))

        async def callback_handler(client: Client, query: CallbackQuery):
            await self._on_callback(client, query)

        app.add_handler(CallbackQueryHandler(callback_handler, filters.regex(r"^wd:(approve|reject):")))

        try:
            await app.start()
            me = await app.get_me()
            bot["bot_username"] = me.username.lower() if me.username else ""
            app.clone_meta = bot
            self.clients[token] = app
            LOGGER.info("clone started username=@%s", me.username)
            return True
        except Exception as e:
            LOGGER.error("clone start failed token=%s err=%s", token[-8:], e)
            return False

    async def _dispatch(self, client: Client, message: Message):
        try:
            if not message.from_user:
                return
            user_id = message.from_user.id
            token = client.clone_meta["token"]
            owner_id = client.clone_meta["owner_id"]
            text = message.text or ""

            if not self._allow_rate(token, user_id, "msg", 0.7):
                return

            if text.startswith("/start"):
                await add_bot_user(token, user_id)
                settings = await get_bot_settings(token)
                welcome = settings.get("welcome", "Hi {first}, welcome!").format(first=message.from_user.first_name)
                await message.reply_text(welcome)
                return

            if text.startswith("/dashboard"):
                if user_id != owner_id:
                    return await message.reply_text("Owner only command.")
                stats = await owner_dashboard(owner_id, token)
                await message.reply_text(
                    "<b>Dashboard</b>\n"
                    f"Total Earnings: <code>${stats['lifetime']:.6f}</code>\n"
                    f"Today's Earnings: <code>${stats['today_earnings']:.6f}</code>\n"
                    f"Total Users: <code>{stats['total_users']}</code>\n"
                    f"Total Ad Views: <code>{stats['total_views']}</code>\n"
                    f"Available Balance: <code>${stats['balance']:.6f}</code>"
                )
                return

            if text.startswith("/users"):
                if user_id != owner_id:
                    return
                total = await count_bot_users(token)
                return await message.reply_text(f"{total} users are using this clone bot.")

            if text.startswith("/withdraw"):
                if user_id != owner_id:
                    return
                try:
                    amount_msg = await client.ask(user_id, "Enter amount to withdraw (minimum $0.5):", timeout=120)
                    upi_msg = await client.ask(user_id, "Enter UPI ID:", timeout=120)
                    amount = round(float(amount_msg.text.strip()), 6)
                    req, err = await create_withdrawal(owner_id, token, amount, upi_msg.text.strip())
                    if err == "minimum_not_met":
                        return await message.reply_text("❌ Minimum withdrawal is $0.5")
                    if err:
                        return await message.reply_text("❌ Insufficient balance")
                    await message.reply_text("✅ Withdrawal request created and sent for admin review.")
                    await self._notify_admin_withdrawal(req)
                except Exception as e:
                    await message.reply_text(f"Error: {e}")
                return

            if text.startswith("/set_custom_db"):
                if user_id != owner_id:
                    return
                if len(message.command) < 2:
                    return await message.reply_text("Usage: /set_custom_db <mongodb-uri>")
                ok = await set_owner_custom_mongo(token, owner_id, message.text.split(" ", 1)[1])
                return await message.reply_text("✅ Custom MongoDB linked." if ok else "❌ Failed to set custom DB")

            mapping = {
                "/set_force_sub": "force_sub_channel",
                "/set_update_channel": "update_channel",
                "/set_bot_text": "bot_text",
                "/set_bot_photo": "bot_photo",
                "/set_welcome": "welcome",
            }
            for cmd, key in mapping.items():
                if not text.startswith(cmd):
                    continue
                if user_id != owner_id:
                    return
                if len(message.command) < 2:
                    return await message.reply_text(f"Usage: {cmd} <value>")
                value = message.text.split(" ", 1)[1]
                ok = await update_bot_setting(token, owner_id, key, value)
                return await message.reply_text("✅ Setting updated." if ok else "❌ Failed to update setting")

            if text.startswith("/stats"):
                total = await count_bot_users(token)
                await message.reply_text(f"Bot stats\nUsers: {total}\nUptime: {datetime.utcnow().isoformat()}Z")
                return

            if text.startswith("/broadcast"):
                if user_id != owner_id:
                    return
                await message.reply_text("Reply-based /broadcast will be enabled in next update.")
                return

            if text.startswith("/batch") or text.startswith("/getlink"):
                if user_id != owner_id:
                    return
                await message.reply_text("Link tools are delegated to content module. Configure DB channel integration first.")
                return
        except Exception as e:
            LOGGER.error("clone dispatch error token=%s err=%s", str(client.clone_meta.get("token", ""))[-8:], e)
            try:
                await message.reply_text(f"Error: {e}")
            except Exception:
                return

    async def _notify_admin_withdrawal(self, req: Dict):
        if not self.clients:
            return
        main_client = next(iter(self.clients.values()))
        text = (
            f"💸 Withdrawal Request\n"
            f"Owner: <code>{req['owner_id']}</code>\n"
            f"Bot token suffix: <code>{str(req['token'])[-8:]}</code>\n"
            f"Amount: <code>${req['amount']}</code>\n"
            f"UPI: <code>{req['upi_id']}</code>\n"
            f"Req ID: <code>{req['_id']}</code>"
        )
        kb = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ Approve", callback_data=f"wd:approve:{req['_id']}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"wd:reject:{req['_id']}"),
            ]]
        )
        sent = False
        if PAYOUT_CHANNEL_ID:
            try:
                await main_client.send_message(PAYOUT_CHANNEL_ID, text, reply_markup=kb)
                sent = True
            except Exception:
                sent = False
        if not sent:
            for admin in ADMINS:
                try:
                    await main_client.send_message(admin, text, reply_markup=kb)
                except Exception:
                    continue

    def _allow_rate(self, token: str, user_id: int, key: str, min_gap: float) -> bool:
        now = asyncio.get_event_loop().time()
        user_map = self._rate_limits[(token, user_id)]
        last = user_map.get(key, 0)
        if now - last < min_gap:
            return False
        user_map[key] = now
        return True


clone_runtime_manager = CloneRuntimeManager()
