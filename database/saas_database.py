import logging
from datetime import datetime
from random import uniform
from typing import Dict, Optional

from motor.motor_asyncio import AsyncIOMotorClient

from config import DB_NAME
from database.multi_mongo import mongo_manager

LOGGER = logging.getLogger(__name__)


async def _db(custom_uri: Optional[str] = None):
    if custom_uri:
        client = AsyncIOMotorClient(custom_uri, serverSelectionTimeoutMS=3000)
        await client.admin.command("ping")
        return client[DB_NAME]
    return await mongo_manager.ensure_database()


def _tier_multiplier(country_code: str) -> float:
    tier_a = {"US", "CA", "GB", "DE", "AU", "FR", "IT", "JP"}
    tier_b = {"AE", "SA", "SG", "NL", "SE", "NO", "ES"}
    if country_code in tier_a:
        return 1.0
    if country_code in tier_b:
        return 0.65
    return 0.35


async def create_clone_bot(owner_id: int, token: str, bot_username: str, custom_mongo_uri: Optional[str] = None) -> Dict:
    db = await _db()
    bots = db["clone_bots"]
    bot_doc = {
        "token": token,
        "owner_id": owner_id,
        "bot_username": bot_username,
        "active": True,
        "custom_mongo_uri": (custom_mongo_uri or "").strip() or None,
        "created_at": datetime.utcnow(),
    }
    await bots.update_one({"token": token}, {"$set": bot_doc}, upsert=True)

    settings = db["bot_settings"]
    await settings.update_one(
        {"token": token},
        {
            "$setOnInsert": {
                "token": token,
                "force_sub_channel": None,
                "update_channel": None,
                "bot_text": "Welcome to your clone bot!",
                "bot_photo": None,
                "welcome": "Hi {first}, welcome!",
            }
        },
        upsert=True,
    )
    return bot_doc


async def get_clone_bot(token: str) -> Optional[Dict]:
    db = await _db()
    return await db["clone_bots"].find_one({"token": token, "active": True})


async def get_clone_bot_by_username(username: str) -> Optional[Dict]:
    db = await _db()
    return await db["clone_bots"].find_one({"bot_username": username.lower(), "active": True})


async def list_clone_bots(active_only: bool = True):
    db = await _db()
    if db is None:
        LOGGER.error("DB is None ERROR")
        raise Exception("Error: DB not connected")

    LOGGER.info("Fetching clone bots...")
    query = {"active": True} if active_only else {}
    return [bot async for bot in db["clone_bots"].find(query)]


async def set_owner_custom_mongo(token: str, owner_id: int, mongo_uri: str) -> bool:
    db = await _db()
    result = await db["clone_bots"].update_one(
        {"token": token, "owner_id": owner_id, "active": True}, {"$set": {"custom_mongo_uri": mongo_uri.strip()}}
    )
    return result.modified_count > 0


async def add_bot_user(token: str, user_id: int) -> None:
    db = await _db()
    await db["bot_users"].update_one(
        {"token": token, "user_id": user_id},
        {"$setOnInsert": {"token": token, "user_id": user_id, "first_seen": datetime.utcnow()}},
        upsert=True,
    )


async def count_bot_users(token: str) -> int:
    db = await _db()
    return await db["bot_users"].count_documents({"token": token})


async def get_bot_settings(token: str) -> Dict:
    db = await _db()
    doc = await db["bot_settings"].find_one({"token": token}) or {}
    return {
        "force_sub_channel": doc.get("force_sub_channel"),
        "update_channel": doc.get("update_channel"),
        "bot_text": doc.get("bot_text", "Welcome to your clone bot!"),
        "bot_photo": doc.get("bot_photo"),
        "welcome": doc.get("welcome", "Hi {first}, welcome!"),
    }


async def update_bot_setting(token: str, owner_id: int, key: str, value):
    db = await _db()
    bot = await db["clone_bots"].find_one({"token": token, "owner_id": owner_id, "active": True})
    if not bot:
        return False
    await db["bot_settings"].update_one({"token": token}, {"$set": {key: value}}, upsert=True)
    return True


async def record_ad_completion(user_id: int, token: str, owner_id: int, ad_type: str, country_code: str = "IN") -> float:
    db = await _db()
    base = uniform(0.001, 0.005)
    earning = round(base * _tier_multiplier((country_code or "IN").upper()), 6)
    event = {
        "user_id": user_id,
        "token": token,
        "owner_id": owner_id,
        "ad_type": ad_type,
        "country_code": (country_code or "IN").upper(),
        "earning": earning,
        "created_at": datetime.utcnow(),
    }
    await db["ad_events"].insert_one(event)
    await db["owner_wallets"].update_one(
        {"owner_id": owner_id, "token": token},
        {"$inc": {"balance": earning, "lifetime": earning}, "$set": {"updated_at": datetime.utcnow()}},
        upsert=True,
    )
    return earning


async def owner_dashboard(owner_id: int, token: str) -> Dict:
    db = await _db()
    wallet = await db["owner_wallets"].find_one({"owner_id": owner_id, "token": token}) or {"balance": 0.0, "lifetime": 0.0}

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_events = await db["ad_events"].count_documents({"owner_id": owner_id, "token": token, "created_at": {"$gte": today_start}})
    today_sum = 0.0
    async for e in db["ad_events"].find({"owner_id": owner_id, "token": token, "created_at": {"$gte": today_start}}, {"earning": 1}):
        today_sum += float(e.get("earning", 0))

    total_views = await db["ad_events"].count_documents({"owner_id": owner_id, "token": token})
    return {
        "balance": float(wallet.get("balance", 0.0)),
        "lifetime": float(wallet.get("lifetime", 0.0)),
        "today_earnings": round(today_sum, 6),
        "today_views": today_events,
        "total_views": total_views,
        "total_users": await db["bot_users"].count_documents({"token": token}),
    }


async def create_withdrawal(owner_id: int, token: str, amount: float, upi_id: str):
    db = await _db()
    wallet = await db["owner_wallets"].find_one({"owner_id": owner_id, "token": token}) or {"balance": 0.0}
    if float(wallet.get("balance", 0.0)) < amount:
        return None, "insufficient_balance"
    if amount < 0.5:
        return None, "minimum_not_met"

    await db["owner_wallets"].update_one({"owner_id": owner_id, "token": token}, {"$inc": {"balance": -amount}}, upsert=True)
    req = {
        "owner_id": owner_id,
        "token": token,
        "amount": amount,
        "upi_id": upi_id,
        "status": "pending",
        "created_at": datetime.utcnow(),
    }
    res = await db["withdrawals"].insert_one(req)
    req["_id"] = res.inserted_id
    return req, None


async def get_withdrawal(withdrawal_id: str):
    db = await _db()
    from bson import ObjectId

    return await db["withdrawals"].find_one({"_id": ObjectId(withdrawal_id)})


async def update_withdrawal_status(withdrawal_id: str, status: str, admin_id: int):
    db = await _db()
    from bson import ObjectId

    req = await db["withdrawals"].find_one({"_id": ObjectId(withdrawal_id)})
    if not req or req.get("status") != "pending":
        return None

    await db["withdrawals"].update_one(
        {"_id": req["_id"]}, {"$set": {"status": status, "reviewed_by": admin_id, "reviewed_at": datetime.utcnow()}}
    )
    if status == "rejected":
        await db["owner_wallets"].update_one(
            {"owner_id": req["owner_id"], "token": req["token"]},
            {"$inc": {"balance": float(req.get("amount", 0.0))}},
            upsert=True,
        )
    return req


async def save_mongo_uri_pool(uris):
    db = await _db()
    await db["system_config"].update_one({"_id": "mongo_uri_pool"}, {"$set": {"uris": uris}}, upsert=True)


async def load_mongo_uri_pool():
    db = await _db()
    doc = await db["system_config"].find_one({"_id": "mongo_uri_pool"}) or {}
    return doc.get("uris", [])
