from pyrogram import filters
from pyrogram.types import Message

from ads_manager import (
    set_ads_enabled,
    set_interstitial,
    set_mode,
    set_rewarded,
    set_smartlink,
    status_text,
)
from bot import Bot
from config import ADMINS


def _command_value(message: Message) -> str:
    if not message.text or " " not in message.text.strip():
        return ""
    return message.text.split(" ", 1)[1].strip()


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command(["ads", "ads_help"]))
async def ads_help_cmd(_, message: Message):
    await message.reply_text(
        "<b>Ad Admin Commands</b>\n"
        "/ads_on - enable all ads globally\n"
        "/ads_off - disable all ads globally\n"
        "/set_smartlink <url> - set SmartLink URL\n"
        "/set_interstitial <zone-id-or-script> - set interstitial SDK/zone\n"
        "/set_rewarded <zone-id-or-script> - set rewarded SDK/zone\n"
        "/set_ad_mode smartlink|interstitial|rewarded|both|all\n"
        "/ad_status - view current ad configuration"
    )


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command(["enable_ads", "ads_on"]))
async def ads_on_cmd(_, message: Message):
    await set_ads_enabled(True)
    await message.reply_text("✅ Ads enabled globally.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command(["disable_ads", "ads_off"]))
async def ads_off_cmd(_, message: Message):
    await set_ads_enabled(False)
    await message.reply_text("✅ Ads disabled globally.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("set_smartlink"))
async def set_smartlink_cmd(_, message: Message):
    value = _command_value(message)
    if not value:
        await message.reply_text("Usage: /set_smartlink <monetag-smartlink-url>")
        return
    await set_smartlink(value)
    await message.reply_text("✅ SmartLink URL saved and SmartLink ad enabled.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("set_interstitial"))
async def set_interstitial_cmd(_, message: Message):
    value = _command_value(message)
    if not value:
        await message.reply_text("Usage: /set_interstitial <zone-id-or-script>")
        return
    await set_interstitial(value)
    await message.reply_text("✅ Interstitial config saved.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("set_rewarded"))
async def set_rewarded_cmd(_, message: Message):
    value = _command_value(message)
    if not value:
        await message.reply_text("Usage: /set_rewarded <zone-id-or-script>")
        return
    await set_rewarded(value)
    await message.reply_text("✅ Rewarded Popup config saved.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("set_ad_mode"))
async def set_ad_mode_cmd(_, message: Message):
    value = _command_value(message).lower()
    if value not in {"smartlink", "interstitial", "rewarded", "both", "all"}:
        await message.reply_text("Usage: /set_ad_mode smartlink|interstitial|rewarded|both|all")
        return

    await set_mode(value)
    await message.reply_text(f"✅ Ad mode set to <code>{value}</code>.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("ad_status"))
async def ad_status_cmd(_, message: Message):
    await message.reply_text(await status_text())
