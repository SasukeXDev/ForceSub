from bot import Bot
from pyrogram.types import Message
from pyrogram import filters
from config import ADMINS, BOT_STATS_TEXT, USER_REPLY_TEXT
from datetime import datetime
from helper_func import get_readable_time

@Bot.on_message(filters.command('stats') & filters.user(ADMINS))
async def stats(bot: Bot, message: Message):
    now = datetime.now()
    delta = now - bot.uptime
    time = get_readable_time(delta.seconds)
    await message.reply(BOT_STATS_TEXT.format(uptime=time))


@Bot.on_message(
    filters.private
    & filters.incoming
    & ~filters.command(
        [
            'start',
            'help',
            'users',
            'broadcast',
            'batch',
            'genlink',
            'stats',
            'create_bot',
            'clone',
            'addbot',
            'my_bots',
            'all_bots',
            'add_mongo',
            'remove_mongo',
            'mongo_pool',
        ]
    )
)
async def useless(_,message: Message):
    if USER_REPLY_TEXT:
        await message.reply(USER_REPLY_TEXT)
