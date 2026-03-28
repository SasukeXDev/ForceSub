import logging

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

from bot import Bot
from clone_platform import clone_runtime_manager
from config import ADMINS
from database.multi_mongo import mongo_manager
from database.saas_database import (
    create_clone_bot,
    get_clone_bot_any,
    list_clone_bots,
    load_mongo_uri_pool,
    save_mongo_uri_pool,
    update_withdrawal_status,
)

LOGGER = logging.getLogger(__name__)


def _cmd_args(message: Message):
    cmd = message.command or []
    return cmd if isinstance(cmd, list) else []


@Bot.on_message(filters.private & filters.command(["create_bot", "clone", "addbot"]))
async def create_bot_handler(client, message: Message):
    owner_id = message.from_user.id
    LOGGER.info("command=/create_bot triggered owner=%s", owner_id)
    try:
        token_msg = await client.ask(owner_id, "Send your @BotFather token:", timeout=180)
        token = (token_msg.text or "").strip()
        if ":" not in token:
            return await message.reply_text("❌ Invalid token format. Token must look like <id>:<secret>.")

        existing = await get_clone_bot_any(token)
        if existing:
            if existing.get("owner_id") == owner_id and existing.get("active", True):
                return await message.reply_text("ℹ️ This bot is already added to your account and is active.")
            if existing.get("owner_id") != owner_id:
                return await message.reply_text("❌ This bot token is already registered by another owner.")

        progress = await message.reply_text("🔍 Validating token with Telegram API...")

        # Validate token by starting temporary client
        from pyrogram import Client
        from config import APP_ID, API_HASH

        tmp = Client(name=f"validate_{owner_id}", api_id=APP_ID, api_hash=API_HASH, bot_token=token, in_memory=True)
        try:
            await tmp.start()
            me = await tmp.get_me()
        finally:
            try:
                await tmp.stop()
            except Exception:
                pass

        await progress.edit_text("💾 Saving clone bot to database...")
        await create_clone_bot(owner_id, token, (me.username or "").lower())
        LOGGER.info("clone bot saved owner=%s username=@%s", owner_id, me.username)

        await progress.edit_text("🚀 Starting your clone bot...")
        ok = await clone_runtime_manager.start_clone(token)
        if not ok:
            return await progress.edit_text("❌ Bot registered but runtime failed to start.")

        await progress.edit_text(
            f"✅ Clone bot created: @{me.username}\n"
            "Available owner commands:\n"
            "/dashboard /withdraw /set_force_sub /set_update_channel /set_bot_text /set_bot_photo /set_welcome"
        )
    except Exception as e:
        LOGGER.error("clone bot create failed owner=%s err=%s", owner_id, e)
        if "Database not initialized" in str(e):
            return await message.reply_text("❌ Database not connected. Please try again later.")
        await message.reply_text(f"Error: {e}")


@Bot.on_message(filters.private & filters.command("help"))
async def help_handler(_, message: Message):
    try:
        LOGGER.info("command=/help triggered user=%s", message.from_user.id if message.from_user else "unknown")
        help_text = (
            "<b>🤖 Bot Help</b>\n\n"
            "<b>Main Commands</b>\n"
            "• /start - Start bot\n"
            "• /help - Show this guide\n\n"
            "<b>Clone Bot Commands</b>\n"
            "• /create_bot (or /clone, /addbot) - Create clone bot\n"
            "• /my_bots - List your clone bots\n\n"
            "<b>Clone Owner Commands</b>\n"
            "• /dashboard - Earnings + usage stats\n"
            "• /users - Total users in your clone bot\n"
            "• /withdraw - Request payout\n"
            "• /set_welcome <text> - Set clone welcome message\n"
            "• /set_force_sub <chat_id> - Set force-sub channel\n"
            "• /set_update_channel <chat_id> - Set updates channel\n"
            "• /set_bot_text <text> - Set bot text\n"
            "• /set_bot_photo <file_id/url> - Set bot photo\n\n"
            "<b>How to create a clone bot</b>\n"
            "1) Run /create_bot\n"
            "2) Send BotFather token\n"
            "3) Bot validates token, saves it, and starts your clone automatically."
        )
        await message.reply_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🤖 Create Bot", callback_data="main:create_bot"), InlineKeyboardButton("📁 My Bots", callback_data="main:my_bots")],
                    [InlineKeyboardButton("ℹ️ Clone Help", callback_data="main:clone_help")],
                ]
            ),
        )
    except Exception as e:
        LOGGER.error("help handler failed err=%s", e)
        await message.reply_text(f"Error: {e}")


@Bot.on_message(filters.private & filters.command(["my_bots", "mybots"]))
async def my_bots_handler(_, message: Message):
    try:
        owner_id = message.from_user.id
        LOGGER.info("command=/my_bots triggered owner=%s", owner_id)
        bots = [b for b in await list_clone_bots(active_only=True) if b.get("owner_id") == owner_id]
        if not bots:
            return await message.reply_text("You do not own clone bots yet. Use /create_bot")
        rows = [f"• @{b.get('bot_username','unknown')}" for b in bots]
        await message.reply_text("<b>Your Clone Bots</b>\n" + "\n".join(rows))
    except Exception as e:
        LOGGER.error("my_bots handler failed err=%s", e)
        await message.reply_text(f"Error: {e}")


@Bot.on_callback_query(filters.regex(r"^main:"))
async def main_help_nav(_, query: CallbackQuery):
    try:
        if query.data == "main:create_bot":
            await query.message.reply_text("Run /create_bot then send your BotFather token when asked.")
        elif query.data == "main:my_bots":
            await query.message.reply_text("Run /my_bots to view all active clone bots under your account.")
        elif query.data == "main:clone_help":
            await query.message.reply_text("Inside your clone bot, use /help to see owner and user commands.")
        await query.answer()
    except Exception as e:
        LOGGER.error("main help nav error=%s", e)
        await query.answer(f"Error: {e}", show_alert=True)


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("all_bots"))
async def all_bots_handler(_, message: Message):
    bots = await list_clone_bots(active_only=True)
    await message.reply_text(f"Total active clone bots: {len(bots)}")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("add_mongo"))
async def add_mongo_handler(_, message: Message):
    args = _cmd_args(message)
    if len(args) < 2:
        return await message.reply_text("Usage: /add_mongo <mongodb-uri>")
    uri = message.text.split(" ", 1)[1].strip()
    if not await mongo_manager.add_uri(uri):
        return await message.reply_text("❌ Failed to validate/add URI")

    merged = list(dict.fromkeys(mongo_manager.list_uris() + await load_mongo_uri_pool()))
    await save_mongo_uri_pool(merged)
    await message.reply_text("✅ Mongo URI added to failover pool.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("remove_mongo"))
async def remove_mongo_handler(_, message: Message):
    args = _cmd_args(message)
    if len(args) < 2:
        return await message.reply_text("Usage: /remove_mongo <mongodb-uri>")
    uri = message.text.split(" ", 1)[1].strip()
    ok = await mongo_manager.remove_uri(uri)
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
