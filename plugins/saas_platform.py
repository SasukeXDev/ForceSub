import logging

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

from bot import Bot
from clone_platform import clone_runtime_manager
from config import ADMINS
from database.multi_mongo import mongo_manager
from database.saas_database import (
    create_clone_bot,
    list_clone_bots,
    load_mongo_uri_pool,
    save_mongo_uri_pool,
    update_withdrawal_status,
)

LOGGER = logging.getLogger(__name__)


@Bot.on_message(filters.private & filters.command("create_bot"))
async def create_bot_handler(client, message: Message):
    owner_id = message.from_user.id
    try:
        token_msg = await client.ask(owner_id, "Send your @BotFather token:", timeout=180)
        token = token_msg.text.strip()

        # Validate token by starting temporary client
        from pyrogram import Client
        from config import APP_ID, API_HASH

        tmp = Client(name=f"validate_{owner_id}", api_id=APP_ID, api_hash=API_HASH, bot_token=token, in_memory=True)
        await tmp.start()
        me = await tmp.get_me()
        await tmp.stop()

        await create_clone_bot(owner_id, token, (me.username or "").lower())
        ok = await clone_runtime_manager.start_clone(token)
        if not ok:
            return await message.reply_text("❌ Bot registered but runtime failed to start.")

        await message.reply_text(
            f"✅ Clone bot created: @{me.username}\n"
            "Available owner commands:\n"
            "/dashboard /withdraw /set_force_sub /set_update_channel /set_bot_text /set_bot_photo /set_welcome"
        )
    except Exception as e:
        await message.reply_text(f"Error: {e}")


@Bot.on_message(filters.private & filters.command("my_bots"))
async def my_bots_handler(_, message: Message):
    owner_id = message.from_user.id
    bots = [b for b in await list_clone_bots(active_only=True) if b.get("owner_id") == owner_id]
    if not bots:
        return await message.reply_text("You do not own clone bots yet. Use /create_bot")
    rows = [f"• @{b.get('bot_username','unknown')}" for b in bots]
    await message.reply_text("<b>Your Clone Bots</b>\n" + "\n".join(rows))


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("all_bots"))
async def all_bots_handler(_, message: Message):
    bots = await list_clone_bots(active_only=True)
    await message.reply_text(f"Total active clone bots: {len(bots)}")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("add_mongo"))
async def add_mongo_handler(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /add_mongo <mongodb-uri>")
    uri = message.text.split(" ", 1)[1].strip()
    if not mongo_manager.add_uri(uri):
        return await message.reply_text("❌ Failed to validate/add URI")

    merged = list(dict.fromkeys(mongo_manager.list_uris() + await load_mongo_uri_pool()))
    await save_mongo_uri_pool(merged)
    await message.reply_text("✅ Mongo URI added to failover pool.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("remove_mongo"))
async def remove_mongo_handler(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /remove_mongo <mongodb-uri>")
    uri = message.text.split(" ", 1)[1].strip()
    ok = mongo_manager.remove_uri(uri)
    uris = [u for u in await load_mongo_uri_pool() if u != uri]
    await save_mongo_uri_pool(uris)
    await message.reply_text("✅ Removed." if ok else "⚠️ URI was not present in runtime pool.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("mongo_pool"))
async def mongo_pool_handler(_, message: Message):
    uris = mongo_manager.list_uris()
    masked = [f"{u[:18]}...{u[-8:]}" for u in uris]
    await message.reply_text("Mongo URI Pool:\n" + "\n".join(masked if masked else ["(empty)"]))


@Bot.on_callback_query(filters.regex(r"^wd:(approve|reject):"))
async def payout_decision(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
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
    except Exception as e:
        LOGGER.warning("Unable to notify owner %s: %s", req["owner_id"], e)

    await query.answer("Updated")
