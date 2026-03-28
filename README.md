# ForceSub Telegram Bot

An async **Pyrogram + MongoDB** bot project with:
- file/link sharing flows,
- ad/verification system,
- admin controls,
- and a **clone bot platform** where users can register their own bot token and run a clone instance.

---

## Features

### Core bot
- `/start` onboarding flow
- force-subscription support
- file/link generation and delivery
- user tracking + broadcast
- admin stats and controls

### Clone bot platform
- `/create_bot` (aliases: `/clone`, `/addbot`) to register clone bots
- token validation through Telegram API
- clone bot record persisted in MongoDB
- clone bot runtime auto-start on main bot startup
- owner commands (inside clone bot): dashboard, users, withdraw, settings

### Stability and debugging
- startup DB initialization guard
- clone autostart fault isolation (one failure does not crash all)
- explicit error messages in command handlers (`Error: <actual_error>`)
- cleaner MongoDB connection logs (connected / switched / retry / failed)

---

## Quick Start

```bash
git clone https://github.com/CodeXBotz/File-Sharing-Bot.git
cd File-Sharing-Bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

---

## Required Environment Variables

| Variable | Description |
|---|---|
| `APP_ID` | Telegram API ID from my.telegram.org |
| `API_HASH` | Telegram API hash |
| `TG_BOT_TOKEN` | Main bot token from BotFather |
| `OWNER_ID` | Telegram numeric user ID of owner |
| `CHANNEL_ID` | DB/media channel id (e.g. `-100...`) |
| `DATABASE_NAME` | Mongo database name |

At least one Mongo URI source is required:
- `DATABASE_URL` (single URI), or
- `MONGO_URIS` (comma-separated pool), or
- `MONGO_URI_1`, `MONGO_URI_2`, ... (indexed pool).

Common optional vars:
- `ADMINS`
- `FORCE_SUB_CHANNEL`
- `PAYOUT_CHANNEL_ID`
- `WEB_BASE_URL`
- `START_MESSAGE`, `FORCE_SUB_MESSAGE`, `START_PIC`

---

## MongoDB Setup Guide

1. Create a MongoDB database user with read/write access to your target DB.
2. Put the URI in `DATABASE_URL` (or URI pool env vars).
3. Set `DATABASE_NAME`.
4. Start the bot.

Expected connection logs:
- `Connecting to MongoDB...`
- `MongoDB connected (...)` or `MongoDB connected`
- `MongoDB retrying connection (attempt x/y)` when temporary failures happen
- `Database not connected: ...` if all configured URIs fail

If DB is unavailable, DB-protected calls raise:
- `Error: Database not initialized`

---

## Commands

### User commands (main bot)
- `/start`
- `/help`
- `/create_bot` (aliases: `/clone`, `/addbot`)
- `/my_bots`

### Admin commands (main bot)
- `/users`
- `/broadcast` (reply mode)
- `/batch`
- `/genlink`
- `/stats`
- `/enable_ads`, `/disable_ads`, `/ad_status`
- `/set_smartlink`, `/set_interstitial`, `/set_ad_mode`
- `/all_bots`
- `/add_mongo <uri>`
- `/remove_mongo <uri>`
- `/mongo_pool`

### Clone owner commands (inside each clone bot)
- `/dashboard`
- `/users`
- `/withdraw`
- `/set_force_sub <chat_id>`
- `/set_update_channel <chat_id>`
- `/set_bot_text <text>`
- `/set_bot_photo <file_id|url>`
- `/set_welcome <text>`
- `/set_custom_db <mongodb-uri>`

---

## `/create_bot` Flow

1. User sends `/create_bot`.
2. Bot asks for BotFather token.
3. Token format is validated.
4. Token is validated via Telegram API (temporary bot client).
5. Bot checks duplicate ownership rules:
   - already active under same owner → informative response,
   - registered by another owner → denied.
6. Clone bot is saved to MongoDB.
7. Clone runtime is started.
8. User receives success/failure message.

---

## Notes

- FloodWait handling in existing modules is preserved.
- Keep bot tokens and Mongo URIs out of source control.
- Use process manager/supervisor in production for restarts and log collection.
