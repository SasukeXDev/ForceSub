from datetime import datetime
from typing import Any, Dict, Optional

from database.database import database

ad_settings = database["ad_settings"] if database is not None else None
verification_tokens = database["verification_tokens"] if database is not None else None


DEFAULT_AD_UNITS: Dict[str, Dict[str, Any]] = {
    "smartlink": {"enabled": False, "value": ""},
    "interstitial": {"enabled": False, "value": ""},
    "rewarded_popup": {"enabled": False, "value": ""},
}

DEFAULT_AD_SETTINGS: Dict[str, Any] = {
    "_id": "global",
    "ads_enabled": False,
    "mode": "smartlink",  # smartlink | interstitial | rewarded_popup | mixed
    "ad_units": DEFAULT_AD_UNITS,
    "updated_at": datetime.utcnow(),
}


async def get_ad_settings() -> Dict[str, Any]:
    if ad_settings is None:
        return DEFAULT_AD_SETTINGS.copy()

    settings = ad_settings.find_one({"_id": "global"})
    if settings:
        merged = DEFAULT_AD_SETTINGS.copy()
        merged.update(settings)

        units = DEFAULT_AD_UNITS.copy()
        raw_units = merged.get("ad_units") or {}

        # Backward compatibility for old schema.
        if merged.get("smartlink_url"):
            raw_units.setdefault("smartlink", {"enabled": bool(merged.get("smartlink_enabled")), "value": merged.get("smartlink_url", "")})
        if merged.get("interstitial_script"):
            raw_units.setdefault("interstitial", {"enabled": bool(merged.get("interstitial_enabled")), "value": merged.get("interstitial_script", "")})

        for ad_type, defaults in DEFAULT_AD_UNITS.items():
            value = raw_units.get(ad_type, {})
            units[ad_type] = {
                "enabled": bool(value.get("enabled", defaults["enabled"])),
                "value": value.get("value", defaults["value"]),
            }

        merged["ad_units"] = units
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
