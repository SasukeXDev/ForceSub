# Telegram SaaS Clone Bot Platform

Production-focused Telegram Bot platform where users can create their own clone bots, monetize ad traffic, and request withdrawals under a central admin system.

---

## 📦 Installation Steps

### 1) Clone project
```bash
git clone https://github.com/CodeXBotz/File-Sharing-Bot.git
cd File-Sharing-Bot
```

### 2) Create virtual environment + install requirements
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) Configure environment variables
Create a `.env` or export variables in your process manager.

### 4) Run bot
```bash
python3 main.py
```

---

## ⚙️ Configuration

Minimum required:

- `API_HASH` – Telegram API hash
- `APP_ID` – Telegram app id
- `TG_BOT_TOKEN` – main bot token
- `OWNER_ID` – main owner telegram id
- `CHANNEL_ID` – database channel id (`-100...`)
- `DATABASE_NAME` – Mongo database name

Mongo connection options (any of these):

- `DATABASE_URL` (primary Mongo URI)
- `MONGO_URIS` (comma-separated URI pool)
- `MONGO_URI_1`, `MONGO_URI_2`, `MONGO_URI_3`... (indexed URI pool)

Optional:

- `PAYOUT_CHANNEL_ID` – channel/group for withdrawal requests
- `ADMINS` – extra admin ids (space separated)
- `FORCE_SUB_CHANNEL`, `START_MESSAGE`, `FORCE_SUB_MESSAGE`, `WEB_BASE_URL`, etc.

---

## ✅ MongoDB Setup Guide

This project uses `motor` (`AsyncIOMotorClient`) with startup validation:

1. On startup, the bot logs:
   - `Connecting to MongoDB...`
   - `Trying URI: ...`
   - `Connected successfully`
   - `All DB connections failed` (if no URI works)
2. The bot pings MongoDB before serving features.
3. If DB is not initialized, protected DB calls raise:
   - `Error: Database not initialized`

### Example env (single Mongo)
```env
DATABASE_URL=mongodb+srv://user:pass@cluster.mongodb.net
DATABASE_NAME=filesharexbot
```

### Example env (multi Mongo pool)
```env
MONGO_URI_1=mongodb+srv://user:pass@cluster-a.mongodb.net
MONGO_URI_2=mongodb+srv://user:pass@cluster-b.mongodb.net
DATABASE_NAME=filesharexbot
```

---

## 🤖 Clone Bot System Overview

Main bot commands:

- `/create_bot` – register a new clone bot via BotFather token
- `/my_bots` – list your clone bots

Clone owner commands (inside clone bot):

- `/dashboard`
- `/withdraw`
- `/set_force_sub`
- `/set_update_channel`
- `/set_bot_text`
- `/set_bot_photo`
- `/set_welcome`

Admin-only controls remain restricted from clone users.

---

## 💰 Earnings System

- Earnings are credited only after server-side ad completion success.
- Per-event logs include:
  - `user_id`
  - `token` (bot identifier)
  - `owner_id`
  - `ad_type`
  - `earning`
  - `country_code`
- `/dashboard` shows:
  - total earnings
  - today earnings
  - total users
  - total ad views
  - available balance

---

## 🧾 Withdrawal System

- Minimum withdrawal: `$0.5`
- Owner submits amount + UPI via `/withdraw`
- Balance is deducted on pending request
- Admin can approve/reject
- Reject flow refunds owner balance
- Withdrawal records include owner, bot token, amount, status, timestamps

---

## 🗄️ Multi MongoDB Support

- URI pool sources:
  - `DATABASE_URL`
  - `MONGO_URIS`
  - `MONGO_URI_1..N`
- Startup + runtime fallback:
  - tries active URI first
  - auto-switches to next healthy URI if current fails
- Admin commands:
  - `/add_mongo <uri>`
  - `/remove_mongo <uri>`
  - `/mongo_pool`

---

## 🚀 Deployment (Heroku / VPS)

### Heroku
- Set config vars in app settings
- Ensure worker command runs `python main.py`
- Add MongoDB URI(s) + Telegram vars

### VPS (systemd/supervisor/pm2)
- Install Python 3.10+
- Configure env securely (not hardcoded)
- Run as service and auto-restart on crash

---

## Security Notes

- Never commit bot tokens or Mongo credentials.
- Restrict admin ids.
- Use separate Mongo users with least privileges.
- Prefer TLS SRV URIs (`mongodb+srv://`).

