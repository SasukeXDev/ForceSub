from pyrogram import filters
from pyrogram.types import Message

from bot import Bot
from config import ADMINS
from ads_manager import set_ads_enabled, set_interstitial, set_mode, set_smartlink, status_text


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("enable_ads"))
async def enable_ads(_, message: Message):
    await set_ads_enabled(True)
    await message.reply_text("✅ Ads enabled globally.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("disable_ads"))
async def disable_ads(_, message: Message):
    await set_ads_enabled(False)
    await message.reply_text("✅ Ads disabled globally.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("set_smartlink"))
async def set_smartlink_cmd(_, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /set_smartlink <monetag-smartlink-url>")
        return
    await set_smartlink(message.text.split(" ", 1)[1])
    await message.reply_text("✅ SmartLink URL saved and SmartLink ad enabled.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("set_interstitial"))
async def set_interstitial_cmd(_, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /set_interstitial <zone-id-or-script>")
        return
    await set_interstitial(message.text.split(" ", 1)[1])
    await message.reply_text("✅ Interstitial config saved and Interstitial ad enabled.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("set_ad_mode"))
async def set_ad_mode_cmd(_, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /set_ad_mode smartlink|interstitial|both")
        return

    mode = message.command[1].strip().lower()
    if mode not in {"smartlink", "interstitial", "both"}:
        await message.reply_text("❌ Invalid mode. Use: smartlink, interstitial, or both")
        return

    await set_mode(mode)
    await message.reply_text(f"✅ Ad mode set to <code>{mode}</code>.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("ad_status"))
async def ad_status_cmd(_, message: Message):
    await message.reply_text(await status_text())
