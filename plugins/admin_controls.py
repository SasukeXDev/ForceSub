from pyrogram import filters
from pyrogram.types import Message

from ads_manager import (
    clear_format_config,
    set_ads_enabled,
    set_format_enabled,
    set_interstitial,
    set_mode,
    set_rewarded,
    set_smartlink,
    status_text,
)
from bot import Bot
from config import ADMINS


ADMIN_FILTER = filters.private & filters.user(ADMINS)


def _cmd_arg(message: Message) -> str:
    parts = (message.text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


@Bot.on_message(ADMIN_FILTER & filters.command("ads_help"))
async def ads_help_cmd(_, message: Message):
    await message.reply_text(
        "<b>Ads Admin Commands</b>\n"
        "• /enable_ads or /ads_on\n"
        "• /disable_ads or /ads_off\n"
        "• /set_smartlink <url>\n"
        "• /set_interstitial <zone-id-or-script>\n"
        "• /set_rewarded <zone-id-or-script>\n"
        "• /set_ad_mode smartlink|interstitial|rewarded|both|all\n"
        "• /enable_ad_format smartlink|interstitial|rewarded\n"
        "• /disable_ad_format smartlink|interstitial|rewarded\n"
        "• /clear_ad_format smartlink|interstitial|rewarded\n"
        "• /ad_status"
    )


@Bot.on_message(ADMIN_FILTER & filters.command(["enable_ads", "ads_on"]))
async def enable_ads_cmd(_, message: Message):
    await set_ads_enabled(True)
    await message.reply_text("✅ Ads enabled globally.")


@Bot.on_message(ADMIN_FILTER & filters.command(["disable_ads", "ads_off"]))
async def disable_ads_cmd(_, message: Message):
    await set_ads_enabled(False)
    await message.reply_text("✅ Ads disabled globally.")


@Bot.on_message(ADMIN_FILTER & filters.command("set_smartlink"))
async def set_smartlink_cmd(_, message: Message):
    value = _cmd_arg(message)
    if not value:
        await message.reply_text("Usage: /set_smartlink <https://monetag-smartlink>")
        return

    try:
        await set_smartlink(value)
    except ValueError as exc:
        await message.reply_text(f"❌ {exc}")
        return

    await message.reply_text("✅ SmartLink URL saved and enabled.")


@Bot.on_message(ADMIN_FILTER & filters.command("set_interstitial"))
async def set_interstitial_cmd(_, message: Message):
    value = _cmd_arg(message)
    if not value:
        await message.reply_text("Usage: /set_interstitial <zone-id-or-script>")
        return

    try:
        await set_interstitial(value)
    except ValueError as exc:
        await message.reply_text(f"❌ {exc}")
        return

    await message.reply_text("✅ Interstitial configuration saved and enabled.")


@Bot.on_message(ADMIN_FILTER & filters.command("set_rewarded"))
async def set_rewarded_cmd(_, message: Message):
    value = _cmd_arg(message)
    if not value:
        await message.reply_text("Usage: /set_rewarded <zone-id-or-script>")
        return

    try:
        await set_rewarded(value)
    except ValueError as exc:
        await message.reply_text(f"❌ {exc}")
        return

    await message.reply_text("✅ Rewarded Popup configuration saved and enabled.")


@Bot.on_message(ADMIN_FILTER & filters.command("set_ad_mode"))
async def set_ad_mode_cmd(_, message: Message):
    mode = _cmd_arg(message).lower()
    if not mode:
        await message.reply_text("Usage: /set_ad_mode smartlink|interstitial|rewarded|both|all")
        return

    try:
        await set_mode(mode)
    except ValueError:
        await message.reply_text("❌ Invalid mode. Use: smartlink, interstitial, rewarded, both, all")
        return

    await message.reply_text(f"✅ Ad mode updated to <code>{mode}</code>.")


@Bot.on_message(ADMIN_FILTER & filters.command("enable_ad_format"))
async def enable_ad_format_cmd(_, message: Message):
    fmt = _cmd_arg(message).lower()
    if not fmt:
        await message.reply_text("Usage: /enable_ad_format smartlink|interstitial|rewarded")
        return

    try:
        await set_format_enabled(fmt, True)
    except ValueError:
        await message.reply_text("❌ Invalid format. Use: smartlink, interstitial, rewarded")
        return

    await message.reply_text(f"✅ <code>{fmt}</code> enabled.")


@Bot.on_message(ADMIN_FILTER & filters.command("disable_ad_format"))
async def disable_ad_format_cmd(_, message: Message):
    fmt = _cmd_arg(message).lower()
    if not fmt:
        await message.reply_text("Usage: /disable_ad_format smartlink|interstitial|rewarded")
        return

    try:
        await set_format_enabled(fmt, False)
    except ValueError:
        await message.reply_text("❌ Invalid format. Use: smartlink, interstitial, rewarded")
        return

    await message.reply_text(f"✅ <code>{fmt}</code> disabled.")


@Bot.on_message(ADMIN_FILTER & filters.command("clear_ad_format"))
async def clear_ad_format_cmd(_, message: Message):
    fmt = _cmd_arg(message).lower()
    if not fmt:
        await message.reply_text("Usage: /clear_ad_format smartlink|interstitial|rewarded")
        return

    try:
        await clear_format_config(fmt)
    except ValueError:
        await message.reply_text("❌ Invalid format. Use: smartlink, interstitial, rewarded")
        return

    await message.reply_text(f"✅ Cleared saved config for <code>{fmt}</code> and disabled it.")


@Bot.on_message(ADMIN_FILTER & filters.command("ad_status"))
async def ad_status_cmd(_, message: Message):
    await message.reply_text(await status_text())
