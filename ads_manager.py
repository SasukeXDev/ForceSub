from typing import Dict, Tuple
from urllib.parse import urlparse

from database.ads_database import get_ad_settings, update_ad_settings


SUPPORTED_MODES = {"smartlink", "interstitial", "rewarded", "both", "all"}
FORMAT_TO_FLAG = {
    "smartlink": "smartlink_enabled",
    "interstitial": "interstitial_enabled",
    "rewarded": "rewarded_enabled",
}


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

    if "data-zone=" in v:
        zone = "".join(ch for ch in v.split("data-zone=", 1)[1] if ch.isdigit())
        if zone:
            return zone

    return ""


def _is_valid_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return bool(parsed.scheme in {"http", "https"} and parsed.netloc)


def _clean_script_or_zone(value: str) -> str:
    return (value or "").strip()


async def set_smartlink(url: str) -> Dict:
    clean_url = (url or "").strip()
    if not _is_valid_url(clean_url):
        raise ValueError("SmartLink must be a valid http/https URL.")

    return await update_ad_settings(
        {
            "smartlink_url": clean_url,
            "smartlink_enabled": True,
        }
    )


async def set_interstitial(script_or_zone: str) -> Dict:
    value = _clean_script_or_zone(script_or_zone)
    if not value:
        raise ValueError("Interstitial config cannot be empty.")

    zone_id = _extract_zone_id(value)
    return await update_ad_settings(
        {
            "interstitial_script": value,
            "interstitial_enabled": True,
            "interstitial_zone_id": zone_id,
        }
    )


async def set_rewarded(script_or_zone: str) -> Dict:
    value = _clean_script_or_zone(script_or_zone)
    if not value:
        raise ValueError("Rewarded config cannot be empty.")

    zone_id = _extract_zone_id(value)
    return await update_ad_settings(
        {
            "rewarded_script": value,
            "rewarded_enabled": True,
            "rewarded_zone_id": zone_id,
        }
    )


async def set_ads_enabled(enabled: bool) -> Dict:
    return await update_ad_settings({"ads_enabled": bool(enabled)})


async def set_mode(mode: str) -> Dict:
    mode = (mode or "").strip().lower()
    if mode not in SUPPORTED_MODES:
        raise ValueError("Invalid mode.")
    return await update_ad_settings({"mode": mode})


async def set_format_enabled(fmt: str, enabled: bool) -> Dict:
    fmt = (fmt or "").strip().lower()
    if fmt not in FORMAT_TO_FLAG:
        raise ValueError("Invalid ad format.")

    patch = {FORMAT_TO_FLAG[fmt]: bool(enabled)}
    return await update_ad_settings(patch)


async def clear_format_config(fmt: str) -> Dict:
    fmt = (fmt or "").strip().lower()
    if fmt == "smartlink":
        patch = {"smartlink_url": "", "smartlink_enabled": False}
    elif fmt == "interstitial":
        patch = {
            "interstitial_script": "",
            "interstitial_zone_id": "",
            "interstitial_enabled": False,
        }
    elif fmt == "rewarded":
        patch = {
            "rewarded_script": "",
            "rewarded_zone_id": "",
            "rewarded_enabled": False,
        }
    else:
        raise ValueError("Invalid ad format.")

    return await update_ad_settings(patch)


async def get_status_snapshot() -> Tuple[Dict, str]:
    settings = await get_ad_settings()
    return settings, await status_text()


async def status_text() -> str:
    s = await get_ad_settings()
    return (
        "<b>Monetag Ads Status</b>\n"
        f"Global Ads: <code>{'ON' if s.get('ads_enabled') else 'OFF'}</code>\n"
        f"Mode: <code>{s.get('mode')}</code>\n"
        f"SmartLink Enabled: <code>{'ON' if s.get('smartlink_enabled') else 'OFF'}</code>\n"
        f"SmartLink URL Set: <code>{'YES' if s.get('smartlink_url') else 'NO'}</code>\n"
        f"Interstitial Enabled: <code>{'ON' if s.get('interstitial_enabled') else 'OFF'}</code>\n"
        f"Interstitial Zone: <code>{s.get('interstitial_zone_id') or 'N/A'}</code>\n"
        f"Interstitial Config Set: <code>{'YES' if s.get('interstitial_script') else 'NO'}</code>\n"
        f"Rewarded Enabled: <code>{'ON' if s.get('rewarded_enabled') else 'OFF'}</code>\n"
        f"Rewarded Zone: <code>{s.get('rewarded_zone_id') or 'N/A'}</code>\n"
        f"Rewarded Config Set: <code>{'YES' if s.get('rewarded_script') else 'NO'}</code>"
    )
