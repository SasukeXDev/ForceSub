from datetime import datetime
from typing import Any, Dict, Optional

from database.database import database

ad_settings = database["ad_settings"] if database is not None else None
verification_tokens = database["verification_tokens"] if database is not None else None


DEFAULT_AD_SETTINGS: Dict[str, Any] = {
    "_id": "global",
    "ads_enabled": False,
    "smartlink_enabled": False,
    "interstitial_enabled": False,
    "rewarded_enabled": False,
    "smartlink_url": "",
    "interstitial_script": "",
    "interstitial_zone_id": "",
    "rewarded_script": "",
    "rewarded_zone_id": "",
    "mode": "smartlink",  # smartlink | interstitial | rewarded | both | all
    "updated_at": datetime.utcnow(),
}


async def get_ad_settings() -> Dict[str, Any]:
    if ad_settings is None:
        return DEFAULT_AD_SETTINGS.copy()

    settings = ad_settings.find_one({"_id": "global"})
    if settings:
        merged = DEFAULT_AD_SETTINGS.copy()
        merged.update(settings)
        return merged

    ad_settings.insert_one(DEFAULT_AD_SETTINGS.copy())
    return DEFAULT_AD_SETTINGS.copy()


async def update_ad_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    if ad_settings is None:
        mock = DEFAULT_AD_SETTINGS.copy()
        mock.update(patch)
        return mock

    patch = {**patch, "updated_at": datetime.utcnow()}
    ad_settings.update_one({"_id": "global"}, {"$set": patch}, upsert=True)
    return await get_ad_settings()


async def create_verification_token(payload: Dict[str, Any]) -> Optional[str]:
    if verification_tokens is None:
        return None
    verification_tokens.insert_one(payload)
    return payload["token"]


async def get_verification_token(token: str) -> Optional[Dict[str, Any]]:
    if verification_tokens is None:
        return None
    return verification_tokens.find_one({"token": token})


async def update_verification_token(token: str, patch: Dict[str, Any]) -> None:
    if verification_tokens is None:
        return
    verification_tokens.update_one({"token": token}, {"$set": patch})
