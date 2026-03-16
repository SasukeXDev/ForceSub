from pyrogram import filters
from pyrogram.types import Message

from bot import Bot
from config import ADMINS
from ads_manager import (
    SUPPORTED_AD_TYPES,
    remove_ad_unit,
    save_ad_unit,
    set_ads_enabled,
    set_mode,
    status_text,
    toggle_ad_unit,
)


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("enable_ads"))
async def enable_ads(_, message: Message):
    await set_ads_enabled(True)
    await message.reply_text("✅ Ads enabled globally.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("disable_ads"))
async def disable_ads(_, message: Message):
    await set_ads_enabled(False)
    await message.reply_text("✅ Ads disabled globally.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command(["add_ad", "edit_ad"]))
async def add_or_edit_ad(_, message: Message):
    if len(message.command) < 3:
        await message.reply_text("Usage: /add_ad <smartlink|interstitial|rewarded_popup> <value>")
        return

    ad_type = message.command[1].strip().lower()
    value = message.text.split(" ", 2)[2]

    if ad_type not in SUPPORTED_AD_TYPES:
        await message.reply_text("❌ Invalid ad type. Use: smartlink, interstitial, rewarded_popup")
        return

    await save_ad_unit(ad_type, value, enabled=True)
    await message.reply_text(f"✅ {ad_type} saved and enabled.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("remove_ad"))
async def remove_ad(_, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /remove_ad <smartlink|interstitial|rewarded_popup>")
        return

    ad_type = message.command[1].strip().lower()
    if ad_type not in SUPPORTED_AD_TYPES:
        await message.reply_text("❌ Invalid ad type.")
        return

    await remove_ad_unit(ad_type)
    await message.reply_text(f"✅ {ad_type} removed and disabled.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("toggle_ad"))
async def toggle_ad(_, message: Message):
    if len(message.command) < 3:
        await message.reply_text("Usage: /toggle_ad <smartlink|interstitial|rewarded_popup> <on|off>")
        return

    ad_type = message.command[1].strip().lower()
    state = message.command[2].strip().lower()

    if ad_type not in SUPPORTED_AD_TYPES or state not in {"on", "off"}:
        await message.reply_text("❌ Invalid arguments.")
        return

    await toggle_ad_unit(ad_type, state == "on")
    await message.reply_text(f"✅ {ad_type} set to {state.upper()}.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("set_ad_mode"))
async def set_ad_mode_cmd(_, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /set_ad_mode smartlink|interstitial|rewarded_popup|mixed")
        return

    mode = message.command[1].strip().lower()
    if mode not in {"smartlink", "interstitial", "rewarded_popup", "mixed"}:
        await message.reply_text("❌ Invalid mode. Use: smartlink, interstitial, rewarded_popup, or mixed")
        return

    await set_mode(mode)
    await message.reply_text(f"✅ Ad mode set to <code>{mode}</code>.")


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command(["ad_status", "ads_list"]))
async def ad_status_cmd(_, message: Message):
    await message.reply_text(await status_text())
