from typing import Dict

from database.ads_database import get_ad_settings, update_ad_settings


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


def _normalize_script_or_zone(value: str) -> Dict[str, str]:
    raw = (value or "").strip()
    zone_id = _extract_zone_id(raw)
    script = raw
    if zone_id and raw.isdigit():
        script = ""
    return {"script": script, "zone_id": zone_id}


async def set_smartlink(url: str) -> Dict:
    cleaned = (url or "").strip()
    return await update_ad_settings({"smartlink_url": cleaned, "smartlink_enabled": bool(cleaned)})


async def set_interstitial(script_or_zone: str) -> Dict:
    data = _normalize_script_or_zone(script_or_zone)
    return await update_ad_settings(
        {
            "interstitial_script": data["script"],
            "interstitial_enabled": bool(data["script"] or data["zone_id"]),
            "interstitial_zone_id": data["zone_id"],
        }
    )


async def set_rewarded(script_or_zone: str) -> Dict:
    data = _normalize_script_or_zone(script_or_zone)
    return await update_ad_settings(
        {
            "rewarded_script": data["script"],
            "rewarded_enabled": bool(data["script"] or data["zone_id"]),
            "rewarded_zone_id": data["zone_id"],
        }
    )


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
        f"Interstitial Zone: <code>{s.get('interstitial_zone_id') or '-'}</code>\n"
        f"Rewarded Popup: <code>{'ON' if s.get('rewarded_enabled') else 'OFF'}</code>\n"
        f"Rewarded Zone: <code>{s.get('rewarded_zone_id') or '-'}</code>"
    )
