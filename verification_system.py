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
AD_COOLDOWN_SECONDS = 15
MAX_AD_ATTEMPTS = 2
MAX_PAGE_VISITS = 8
STEP_ORDER = ["interstitial", "smartlink"]


async def create_access_token(user_id: int, base64_payload: str) -> Optional[str]:
    settings = await get_ad_settings()
    required_steps: List[str] = []

    if settings.get("ads_enabled"):
        for step in STEP_ORDER:
            if settings.get(f"{step}_enabled"):
                required_steps.append(step)

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
        "ad_available_at": datetime.utcnow() + timedelta(seconds=AD_COOLDOWN_SECONDS),
        "ad_attempts": 0,
        "page_visits": 0,
        "blocked": False,
        "blocked_reason": "",
    }
    return await create_verification_token(payload)


async def get_token_or_none(token: str, user_id: Optional[int] = None) -> Optional[Dict]:
    data = await get_verification_token(token)
    if not data:
        return None
    if data.get("used"):
        return None
    if data.get("blocked"):
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


def get_next_required_step(data: Dict) -> Optional[str]:
    required = data.get("required_steps", [])
    completed = set(data.get("completed_steps", []))
    for step in required:
        if step not in completed:
            return step
    return None


async def register_page_visit(token: str) -> Optional[Dict]:
    data = await get_token_or_none(token)
    if not data:
        return None

    visits = int(data.get("page_visits", 0)) + 1
    patch: Dict[str, object] = {"page_visits": visits}
    if visits > MAX_PAGE_VISITS:
        patch["blocked"] = True
        patch["blocked_reason"] = "refresh_abuse"

    await update_verification_token(token, patch)
    return await get_token_or_none(token)


async def can_start_ad_attempt(token: str) -> Optional[Dict]:
    data = await get_token_or_none(token)
    if not data:
        return None

    attempts = int(data.get("ad_attempts", 0))
    if attempts >= MAX_AD_ATTEMPTS:
        await update_verification_token(
            token,
            {"blocked": True, "blocked_reason": "too_many_attempts"},
        )
        return None

    await update_verification_token(token, {"ad_attempts": attempts + 1})
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
