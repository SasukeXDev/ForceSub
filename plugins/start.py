import asyncio

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import Bot
from config import (
    ADMINS,
    CUSTOM_CAPTION,
    DISABLE_CHANNEL_BUTTON,
    FORCE_MSG,
    PROTECT_CONTENT,
    START_MSG,
    START_PIC,
    WEB_BASE_URL,
)
from database.database import add_user, del_user, full_userbase, present_user
from helper_func import decode, get_messages, subscribed
from verification_system import create_access_token, is_unlock_ready, mark_token_used


async def _deliver_files(client: Client, message: Message, ids):
    temp_msg = await message.reply("Please wait...")
    try:
        messages = await get_messages(client, ids)
    except Exception:
        await message.reply_text("Something went wrong..! Please try again.")
        return

    await temp_msg.delete()

    for msg in messages:
        if bool(CUSTOM_CAPTION) and bool(msg.document):
            caption = CUSTOM_CAPTION.format(
                previouscaption="" if not msg.caption else msg.caption.html,
                filename=msg.document.file_name,
            )
        else:
            caption = "" if not msg.caption else msg.caption.html

        reply_markup = msg.reply_markup if DISABLE_CHANNEL_BUTTON else None

        try:
            await msg.copy(
                chat_id=message.from_user.id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                protect_content=PROTECT_CONTENT,
            )
            await asyncio.sleep(0.5)
        except FloodWait as e:
            await asyncio.sleep(e.x)
            await msg.copy(
                chat_id=message.from_user.id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                protect_content=PROTECT_CONTENT,
            )
        except Exception:
            pass


def _decode_ids(client: Client, encoded_string: str):
    argument = encoded_string.split("-")
    if len(argument) == 3:
        start = int(int(argument[1]) / abs(client.db_channel.id))
        end = int(int(argument[2]) / abs(client.db_channel.id))
        if start <= end:
            return list(range(start, end + 1))
        return list(range(start, end - 1, -1))

    if len(argument) == 2:
        return [int(int(argument[1]) / abs(client.db_channel.id))]

    return []


@Bot.on_message(filters.command("start") & filters.private & subscribed)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    if not await present_user(user_id):
        try:
            await add_user(user_id)
        except Exception:
            pass

    text = message.text or ""
    if len(text) > 7:
        arg = text.split(" ", 1)[1]

        if arg.startswith("unlock_"):
            token = arg.split("_", 1)[1]
            token_data = await is_unlock_ready(token, user_id)
            if not token_data:
                await message.reply_text("❌ Verification invalid or expired. Please use the original file link again.")
                return

            try:
                decoded = await decode(token_data.get("base64_payload", ""))
                ids = _decode_ids(client, decoded)
            except Exception:
                await message.reply_text("❌ Verification payload invalid. Please regenerate link.")
                return

            await _deliver_files(client, message, ids)
            await mark_token_used(token)
            return

        try:
            decoded = await decode(arg)
            ids = _decode_ids(client, decoded)
        except Exception:
            await message.reply_text("Invalid or corrupted link.")
            return

        token = await create_access_token(user_id, arg)
        if not token:
            await message.reply_text("Verification service unavailable. Try again later.")
            return

        if not WEB_BASE_URL:
            await message.reply_text("⚠️ WEB_BASE_URL is not configured by admin. Unable to run ad verification.")
            return

        verify_url = f"{WEB_BASE_URL}/verify/{token}"
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("✅ Verify & Continue", web_app=WebAppInfo(url=verify_url))]]
        )
        await message.reply_text(
            "Before receiving your file, complete Monetag verification.\n"
            "Tap the button below and follow the steps.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        return

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Join Community", url="https://t.me/Uchiha_Community"),
                InlineKeyboardButton("Join Backup", url="https://t.me/ZolDox"),
            ],
            [
                InlineKeyboardButton("Buy Premium", callback_data="about"),
                InlineKeyboardButton("Developer", url="https://t.me/Uchiha_Developer"),
            ],
        ]
    )

    if START_PIC:
        await message.reply_photo(
            START_PIC,
            caption=START_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None
                if not message.from_user.username
                else "@" + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id,
            ),
            reply_markup=reply_markup,
        )
    else:
        await message.reply_text(
            text=START_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None
                if not message.from_user.username
                else "@" + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id,
            ),
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            quote=True,
        )


WAIT_MSG = "<b>Processing ...</b>"
REPLY_ERROR = (
    """<code>Use this command as a replay to any telegram message with out any spaces.</code>"""
)


@Bot.on_message(filters.command("start") & filters.private & ~subscribed)
async def not_joined(client: Client, message: Message):
    buttons = [
        [
            InlineKeyboardButton("Join Channel", url="https://t.me/+sWFyXexj5oQ3MDI1"),
            InlineKeyboardButton("Join 2nd Channel", url="https://t.me/+Cv5_CBnJgjQ4ZDY1"),
        ],
        [
            InlineKeyboardButton("Join 3nd Channel", url=client.invitelink),
            InlineKeyboardButton("Join 4nd Channel", url="https://openinapp.link/fel7o"),
        ],
    ]
    try:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="Try Again", url=f"https://t.me/{client.username}?start={message.command[1]}"
                )
            ]
        )
    except IndexError:
        pass

    await message.reply(
        text=FORCE_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=None if not message.from_user.username else "@" + message.from_user.username,
            mention=message.from_user.mention,
            id=message.from_user.id,
        ),
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True,
        disable_web_page_preview=True,
    )


@Bot.on_message(filters.command("users") & filters.private & filters.user(ADMINS))
async def get_users(client: Bot, message: Message):
    msg = await client.send_message(chat_id=message.chat.id, text=WAIT_MSG)
    users = await full_userbase()
    await msg.edit(f"{len(users)} users are using this bot")


@Bot.on_message(filters.private & filters.command("broadcast") & filters.user(ADMINS))
async def send_text(client: Bot, message: Message):
    if not message.reply_to_message:
        msg = await message.reply(REPLY_ERROR)
        await asyncio.sleep(8)
        await msg.delete()
        return

    query = await full_userbase()
    broadcast_msg = message.reply_to_message
    total = successful = blocked = deleted = unsuccessful = 0

    pls_wait = await message.reply("<i>Broadcasting Message.. This will Take Some Time</i>")
    for chat_id in query:
        try:
            await broadcast_msg.copy(chat_id)
            successful += 1
        except FloodWait as e:
            await asyncio.sleep(e.x)
            await broadcast_msg.copy(chat_id)
            successful += 1
        except UserIsBlocked:
            await del_user(chat_id)
            blocked += 1
        except InputUserDeactivated:
            await del_user(chat_id)
            deleted += 1
        except Exception:
            unsuccessful += 1
        total += 1

    status = f"""<b><u>Broadcast Completed</u>

Total Users: <code>{total}</code>
Successful: <code>{successful}</code>
Blocked Users: <code>{blocked}</code>
Deleted Accounts: <code>{deleted}</code>
Unsuccessful: <code>{unsuccessful}</code></b>"""

    await pls_wait.edit(status)
