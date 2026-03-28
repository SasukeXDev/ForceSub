from datetime import datetime
from typing import Any, Dict, Optional

from database.multi_mongo import mongo_manager


DEFAULT_AD_SETTINGS: Dict[str, Any] = {
    "_id": "global",
    "ads_enabled": False,
    "smartlink_enabled": False,
    "interstitial_enabled": False,
    "smartlink_url": "",
    "interstitial_script": "",
    "mode": "smartlink",  # smartlink | interstitial | both
    "updated_at": datetime.utcnow(),
}


async def _ad_settings_col():
    db = await mongo_manager.ensure_database()
    return db["ad_settings"]


async def _verification_tokens_col():
    db = await mongo_manager.ensure_database()
    return db["verification_tokens"]


async def get_ad_settings() -> Dict[str, Any]:
    ad_settings = await _ad_settings_col()
    settings = await ad_settings.find_one({"_id": "global"})
    if settings:
        merged = DEFAULT_AD_SETTINGS.copy()
        merged.update(settings)
        return merged

    await ad_settings.insert_one(DEFAULT_AD_SETTINGS.copy())
    return DEFAULT_AD_SETTINGS.copy()


async def update_ad_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    ad_settings = await _ad_settings_col()
    patch = {**patch, "updated_at": datetime.utcnow()}
    await ad_settings.update_one({"_id": "global"}, {"$set": patch}, upsert=True)
    return await get_ad_settings()


async def create_verification_token(payload: Dict[str, Any]) -> Optional[str]:
    verification_tokens = await _verification_tokens_col()
    await verification_tokens.insert_one(payload)
    return payload["token"]


async def get_verification_token(token: str) -> Optional[Dict[str, Any]]:
    verification_tokens = await _verification_tokens_col()
    return await verification_tokens.find_one({"token": token})


async def update_verification_token(token: str, patch: Dict[str, Any]) -> None:
    verification_tokens = await _verification_tokens_col()
    await verification_tokens.update_one({"token": token}, {"$set": patch})
