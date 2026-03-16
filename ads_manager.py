from typing import Dict


def _extract_zone_id(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if v.isdigit():
        return v
    marker = "show_"
    if marker in v:
        suffix = v.split(marker, 1)[1]
        zone = "".join(ch for ch in suffix if ch.isdigit())
        if zone:
            return zone
    return ""

from database.ads_database import get_ad_settings, update_ad_settings


async def set_smartlink(url: str) -> Dict:
    return await update_ad_settings({"smartlink_url": url.strip(), "smartlink_enabled": bool(url.strip())})


async def set_interstitial(script_or_zone: str) -> Dict:
    value = script_or_zone.strip()
    zone_id = _extract_zone_id(value)
    return await update_ad_settings({
        "interstitial_script": value,
        "interstitial_enabled": bool(value),
        "interstitial_zone_id": zone_id,
    })


async def set_rewarded(script_or_zone: str) -> Dict:
    value = script_or_zone.strip()
    zone_id = _extract_zone_id(value)
    return await update_ad_settings({
        "rewarded_script": value,
        "rewarded_enabled": bool(value),
        "rewarded_zone_id": zone_id,
    })


async def set_ads_enabled(enabled: bool) -> Dict:
    return await update_ad_settings({"ads_enabled": enabled})


async def set_mode(mode: str) -> Dict:
    return await update_ad_settings({"mode": mode})


async def status_text() -> str:
    s = await get_ad_settings()
    return (
        "<b>Monetag Ads Status</b>\n"
        f"Global Ads: <code>{'ON' if s.get('ads_enabled') else 'OFF'}</code>\n"
        f"Mode: <code>{s.get('mode')}</code>\n"
        f"SmartLink: <code>{'ON' if s.get('smartlink_enabled') else 'OFF'}</code>\n"
        f"SmartLink URL Set: <code>{'YES' if s.get('smartlink_url') else 'NO'}</code>\n"
        f"Interstitial: <code>{'ON' if s.get('interstitial_enabled') else 'OFF'}</code>\n"
        f"Interstitial Script/Zone Set: <code>{'YES' if s.get('interstitial_script') else 'NO'}</code>\n"
        f"Rewarded Popup: <code>{'ON' if s.get('rewarded_enabled') else 'OFF'}</code>\n"
        f"Rewarded Script/Zone Set: <code>{'YES' if s.get('rewarded_script') else 'NO'}</code>"
    )
