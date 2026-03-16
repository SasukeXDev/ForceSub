import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from database.ads_database import (
    create_verification_token,
    get_ad_settings,
    get_verification_token,
    update_verification_token,
)


TOKEN_TTL_MINUTES = 10


async def create_access_token(user_id: int, base64_payload: str) -> Optional[str]:
    settings = await get_ad_settings()
    required_steps: List[str] = []

    if settings.get("ads_enabled"):
        mode = settings.get("mode", "smartlink")
        if mode == "smartlink" and settings.get("smartlink_enabled"):
            required_steps = ["smartlink"]
        elif mode == "interstitial" and settings.get("interstitial_enabled"):
            required_steps = ["interstitial"]
        elif mode == "both":
            if settings.get("smartlink_enabled"):
                required_steps.append("smartlink")
            if settings.get("interstitial_enabled"):
                required_steps.append("interstitial")

    token = secrets.token_urlsafe(24)
    payload = {
        "token": token,
        "user_id": user_id,
        "base64_payload": base64_payload,
        "required_steps": required_steps,
        "completed_steps": [],
        "used": False,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MINUTES),
    }
    return await create_verification_token(payload)


async def get_token_or_none(token: str, user_id: Optional[int] = None) -> Optional[Dict]:
    data = await get_verification_token(token)
    if not data:
        return None
    if data.get("used"):
        return None
    if datetime.utcnow() > data.get("expires_at"):
        return None
    if user_id is not None and data.get("user_id") != user_id:
        return None
    return data


async def complete_step(token: str, step: str) -> Optional[Dict]:
    data = await get_token_or_none(token)
    if not data:
        return None

    completed = set(data.get("completed_steps", []))
    completed.add(step)
    await update_verification_token(token, {"completed_steps": list(completed)})
    return await get_token_or_none(token)


async def is_unlock_ready(token: str, user_id: int) -> Optional[Dict]:
    data = await get_token_or_none(token, user_id=user_id)
    if not data:
        return None

    required = set(data.get("required_steps", []))
    completed = set(data.get("completed_steps", []))
    if required.issubset(completed):
        return data
    return None


async def mark_token_used(token: str) -> None:
    await update_verification_token(token, {"used": True})
