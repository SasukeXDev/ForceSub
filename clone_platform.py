import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional

import pyromod.listen  # noqa: F401
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from pyrogram.errors import UserNotParticipant

try:
    from pyrogram.types import WebAppInfo
except Exception:  # pragma: no cover
    WebAppInfo = None

from config import API_HASH, APP_ID, ADMINS, CHANNEL_ID, PAYOUT_CHANNEL_ID, WEB_BASE_URL
from database.saas_database import (
    add_bot_user,
    count_bot_users,
    create_withdrawal,
    get_bot_settings,
    get_clone_bot,
    list_clone_bots,
    owner_dashboard,
    save_clone_content,
    set_owner_custom_mongo,
    list_bot_users,
    update_withdrawal_status,
    update_bot_setting,
)
from helper_func import encode, decode
from verification_system import create_access_token, is_unlock_ready, mark_token_used

LOGGER = logging.getLogger(__name__)


class CloneRuntimeManager:
    def __init__(self):
        self.clients: Dict[str, Client] = {}
        self._rate_limits = defaultdict(dict)

    @staticmethod
    def _command_args(message: Message):
        cmd = message.command or []
        return cmd if isinstance(cmd, list) else []

    @staticmethod
    def _extract_media_file(message: Message):
        if message.document:
            return "document", message.document.file_id
        if message.photo:
            return "photo", message.photo.file_id
        if message.video:
            return "video", message.video.file_id
        if message.audio:
            return "audio", message.audio.file_id
        if message.voice:
            return "voice", message.voice.file_id
        if message.sticker:
            return "sticker", message.sticker.file_id
        return None, None

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
        app.add_handler(CallbackQueryHandler(callback_handler, filters.regex(r"^clone:")))

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
            settings = await get_bot_settings(token)
            dump_channel_id = settings.get("db_channel_id")

            if not self._allow_rate(token, user_id, "msg", 0.7):
                return

            if text.startswith("/start ") and len(text.split(" ", 1)) == 2:
                arg = text.split(" ", 1)[1]
                if arg.startswith("unlock_"):
                    token_key = arg.split("_", 1)[1]
                    token_data = await is_unlock_ready(token_key, user_id)
                    if not token_data:
                        return await message.reply_text("❌ Verification invalid or expired. Re-open original link.")
                    payload = token_data.get("base64_payload", "")
                    try:
                        decoded = await decode(payload)
                    except Exception as e:
                        return await message.reply_text(f"Error: {e}")
                    if not dump_channel_id:
                        return await message.reply_text("⚠️ Dump channel is not configured for this bot.")
                    try:
                        parts = decoded.split("-")
                        if len(parts) != 3 or parts[0] != "get":
                            raise ValueError("invalid link payload")
                        start_id, end_id = int(parts[1]), int(parts[2])
                        step = 1 if start_id <= end_id else -1
                        ids = list(range(start_id, end_id + step, step))
                        messages = await client.get_messages(chat_id=int(dump_channel_id), message_ids=ids)
                        for msg in messages:
                            if msg:
                                await msg.copy(chat_id=user_id, protect_content=False)
                        await mark_token_used(token_key)
                        return
                    except Exception as e:
                        return await message.reply_text(f"Error: {e}")

                access_token = await create_access_token(
                    user_id=user_id,
                    base64_payload=arg,
                    bot_token=token,
                    owner_id=owner_id,
                )
                if not access_token:
                    return await message.reply_text("Error: Verification service unavailable.")
                if not WEB_BASE_URL or WebAppInfo is None:
                    return await message.reply_text("Error: WEB_BASE_URL not configured for verification flow.")
                verify_url = f"{WEB_BASE_URL}/verify/{access_token}"
                kb = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("✅ Verify & Continue", web_app=WebAppInfo(url=verify_url))]]
                )
                return await message.reply_text(
                    "Complete verification in web app to unlock content.",
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )

            if text.startswith("/start"):
                await add_bot_user(token, user_id)
                force_sub = settings.get("force_sub_channel")
                if force_sub:
                    try:
                        member = await client.get_chat_member(force_sub, user_id)
                        if getattr(member, "status", None) not in {"member", "administrator", "creator"}:
                            raise ValueError("not joined")
                    except UserNotParticipant:
                        return await message.reply_text("⚠️ Please join the required channel first, then /start again.")
                    except Exception:
                        return await message.reply_text("⚠️ Please join the required channel first, then /start again.")
                welcome = settings.get("welcome", "Hi {first}, welcome!").format(first=message.from_user.first_name)
                await message.reply_text(
                    welcome,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("📥 Get Link", callback_data="clone:getlink"), InlineKeyboardButton("📦 Batch", callback_data="clone:batch")],
                         [InlineKeyboardButton("📢 Broadcast", callback_data="clone:broadcast"), InlineKeyboardButton("⚙️ Settings", callback_data="clone:settings")],
                         [InlineKeyboardButton("ℹ️ Help", callback_data="clone:help")]]
                    ),
                )
                return

            if text.startswith("/help"):
                await message.reply_text(
                    "<b>Clone Bot Help</b>\n\n"
                    "• /start - Start the bot\n"
                    "• /help - Show commands\n"
                    "• /set_dump - Set your dump channel\n"
                    "• /getlink - Reply to content to generate a share link\n"
                    "• /batch - Generate link for a message-id range\n"
                    "• /broadcast - Owner broadcast to clone users\n"
                    "• /stats - View bot users count\n"
                    "• /dashboard - Owner earnings dashboard\n"
                    "• /users - Owner user count\n"
                    "• /withdraw - Owner withdrawal request\n"
                    "• /set_welcome <text> - Owner welcome text\n"
                    "• /set_force_sub <chat_id> - Owner force-sub setup\n"
                    "• /set_update_channel <chat_id> - Owner update channel setup\n"
                    "\nYou can also send media. It will be stored for analytics and copied to dump channel."
                )
                return

            if text.startswith("/set_dump") or text.startswith("/set_db_channel"):
                if user_id != owner_id:
                    return
                args = self._command_args(message)
                if len(args) >= 2:
                    raw = args[1].strip()
                else:
                    ask_msg = await client.ask(
                        user_id,
                        "Send dump channel ID (e.g. -100...) or forward any message from your dump channel.",
                        timeout=180,
                    )
                    raw = (ask_msg.text or "").strip()
                    if ask_msg.forward_from_chat:
                        raw = str(ask_msg.forward_from_chat.id)
                if not raw:
                    return await message.reply_text("Error: No channel provided.")
                try:
                    if raw.startswith("https://t.me/"):
                        raw = "@" + raw.rsplit("/", 1)[-1]
                    if raw.startswith("@"):
                        channel = await client.get_chat(raw)
                        channel_id = int(channel.id)
                    else:
                        channel_id = int(raw)
                except Exception as e:
                    return await message.reply_text(f"Error: Invalid channel id/username. {e}")
                try:
                    me = await client.get_me()
                    bot_member = await client.get_chat_member(channel_id, me.id)
                    LOGGER.info(
                        "set_dump token=%s channel_id=%s bot_member_status=%s",
                        token[-8:],
                        channel_id,
                        getattr(bot_member, "status", "unknown"),
                    )
                    if getattr(bot_member, "status", "") not in {"administrator", "creator"}:
                        return await message.reply_text("Error: Please make the bot admin in dump channel.")
                except Exception as e:
                    LOGGER.error("set_dump failed token=%s channel_id=%s err=%s", token[-8:], raw, e)
                    return await message.reply_text(f"Error: Cannot access channel. {e}")
                ok = await update_bot_setting(token, owner_id, "db_channel_id", channel_id)
                if not ok:
                    return await message.reply_text("Error: Failed to save dump channel.")
                return await message.reply_text(f"✅ Dump channel saved: <code>{channel_id}</code>")

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
                args = self._command_args(message)
                if len(args) < 2:
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
                args = self._command_args(message)
                if len(args) < 2:
                    prompt = "Send value:"
                    if key == "force_sub_channel":
                        prompt = "Send force-sub channel id (e.g. -100...):"
                    asked = await client.ask(user_id, prompt, timeout=180)
                    value = (asked.text or "").strip()
                else:
                    value = message.text.split(" ", 1)[1]
                if not value:
                    return await message.reply_text("Error: No value provided.")
                ok = await update_bot_setting(token, owner_id, key, value)
                return await message.reply_text("✅ Setting updated." if ok else "❌ Failed to update setting")

            if text.startswith("/stats"):
                total = await count_bot_users(token)
                await message.reply_text(f"Bot stats\nUsers: {total}\nUptime: {datetime.utcnow().isoformat()}Z")
                return

            if text.startswith("/broadcast"):
                if user_id != owner_id:
                    return
                users = await list_bot_users(token)
                if not users:
                    return await message.reply_text("⚠️ No users to broadcast.")
                content = message.reply_to_message
                if not content:
                    asked = await client.ask(user_id, "Reply not found. Send broadcast text:", timeout=180)
                    content = asked
                sent = 0
                for uid in users:
                    try:
                        await content.copy(uid)
                        sent += 1
                    except Exception:
                        continue
                return await message.reply_text(f"✅ Broadcast sent to {sent}/{len(users)} users.")

            if text.startswith("/batch") or text.startswith("/getlink"):
                if user_id != owner_id:
                    return
                if not dump_channel_id:
                    return await message.reply_text(
                        "⚠️ Please set your dump channel using /set_dump before using this command."
                    )
                if text.startswith("/getlink"):
                    if not message.reply_to_message:
                        return await message.reply_text("Reply to a message with /getlink")
                    try:
                        copied = await message.reply_to_message.copy(chat_id=int(dump_channel_id), disable_notification=True)
                        payload = await encode(f"get-{copied.id}-{copied.id}")
                        me = await client.get_me()
                        return await message.reply_text(f"https://t.me/{me.username}?start={payload}")
                    except Exception as e:
                        return await message.reply_text(f"Error: {e}")
                if text.startswith("/batch"):
                    args = self._command_args(message)
                    if len(args) < 3:
                        return await message.reply_text("Usage: /batch <start_message_id> <end_message_id>")
                    try:
                        start_id = int(args[1])
                        end_id = int(args[2])
                        payload = await encode(f"get-{start_id}-{end_id}")
                        me = await client.get_me()
                        return await message.reply_text(f"https://t.me/{me.username}?start={payload}")
                    except Exception as e:
                        return await message.reply_text(f"Error: {e}")


            media_type, file_id = self._extract_media_file(message)
            if file_id:
                await save_clone_content(
                    token=token,
                    owner_id=owner_id,
                    user_id=user_id,
                    message_id=message.id,
                    file_id=file_id,
                    media_type=media_type or "unknown",
                )
                try:
                    await message.copy(chat_id=CHANNEL_ID, disable_notification=True)
                except Exception as dump_error:
                    LOGGER.warning("clone content dump failed token=%s err=%s", token[-8:], dump_error)
                await message.reply_text("✅ Content saved.")
                return
        except Exception as e:
            LOGGER.error("clone dispatch error token=%s err=%s", str(client.clone_meta.get("token", ""))[-8:], e)
            try:
                await message.reply_text(f"Error: {e}")
            except Exception:
                return

    async def _on_callback(self, client: Client, query: CallbackQuery):
        if query.data.startswith("wd:"):
            if not query.from_user or query.from_user.id not in ADMINS:
                return await query.answer("Admin only", show_alert=True)
            _, action, withdrawal_id = query.data.split(":", 2)
            status = "approved" if action == "approve" else "rejected"
            req = await update_withdrawal_status(withdrawal_id, status, query.from_user.id)
            if not req:
                return await query.answer("Invalid request", show_alert=True)
            await query.message.edit_text(
                f"{'✅ Withdrawn' if status == 'approved' else '❌ Rejected'}\n"
                f"Owner: <code>{req['owner_id']}</code>\n"
                f"Amount: <code>${req['amount']}</code>"
            )
            try:
                await client.send_message(
                    req["owner_id"],
                    f"Withdrawal update for bot token suffix {str(req['token'])[-8:]}:\n"
                    f"Status: {'✅ Withdrawn' if status == 'approved' else '❌ Rejected (Refunded)'}",
                )
            except Exception as notify_err:
                LOGGER.warning("unable to notify withdrawal owner=%s err=%s", req.get("owner_id"), notify_err)
            return await query.answer("Updated")

        if query.data == "clone:help":
            await query.message.reply_text("Use /help to view available clone bot commands.")
            return await query.answer()
        if query.data == "clone:getlink":
            await query.message.reply_text("Reply to any message with /getlink")
            return await query.answer()
        if query.data == "clone:batch":
            await query.message.reply_text("Use: /batch <start_message_id> <end_message_id>")
            return await query.answer()
        if query.data == "clone:broadcast":
            await query.message.reply_text("Reply to a message with /broadcast to send it to all clone users.")
            return await query.answer()
        if query.data == "clone:settings":
            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🗂 Set Dump", callback_data="clone:settings:dump")],
                    [InlineKeyboardButton("👋 Set Welcome", callback_data="clone:settings:welcome")],
                    [InlineKeyboardButton("📢 Force Sub", callback_data="clone:settings:force_sub")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="clone:menu")],
                ]
            )
            await query.message.reply_text("⚙️ Settings Menu", reply_markup=kb)
            return await query.answer()
        if query.data == "clone:menu":
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("📥 Get Link", callback_data="clone:getlink"), InlineKeyboardButton("📦 Batch", callback_data="clone:batch")],
                 [InlineKeyboardButton("📢 Broadcast", callback_data="clone:broadcast"), InlineKeyboardButton("⚙️ Settings", callback_data="clone:settings")],
                 [InlineKeyboardButton("ℹ️ Help", callback_data="clone:help")]]
            )
            await query.message.reply_text("Main Menu", reply_markup=kb)
            return await query.answer()
        if query.data == "clone:settings:dump":
            await query.message.reply_text("Use /set_dump and send channel id or forward channel message.")
            return await query.answer()
        if query.data == "clone:settings:welcome":
            await query.message.reply_text("Use /set_welcome then send your welcome text.")
            return await query.answer()
        if query.data == "clone:settings:force_sub":
            await query.message.reply_text("Use /set_force_sub then send force-sub channel id.")
            return await query.answer()
        await query.answer()

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
