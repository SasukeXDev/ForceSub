from typing import Dict

from database.ads_database import get_ad_settings, update_ad_settings

SUPPORTED_AD_TYPES = {"smartlink", "interstitial", "rewarded_popup"}


async def set_ads_enabled(enabled: bool) -> Dict:
    return await update_ad_settings({"ads_enabled": enabled})


async def set_mode(mode: str) -> Dict:
    return await update_ad_settings({"mode": mode})


async def save_ad_unit(ad_type: str, value: str, enabled: bool = True) -> Dict:
    ad_type = ad_type.strip().lower()
    if ad_type not in SUPPORTED_AD_TYPES:
        raise ValueError("unsupported_ad_type")

    settings = await get_ad_settings()
    ad_units = settings.get("ad_units", {}).copy()
    ad_units[ad_type] = {
        "enabled": enabled,
        "value": value.strip(),
    }
    return await update_ad_settings({"ad_units": ad_units})


async def remove_ad_unit(ad_type: str) -> Dict:
    return await save_ad_unit(ad_type, "", enabled=False)


async def toggle_ad_unit(ad_type: str, enabled: bool) -> Dict:
    ad_type = ad_type.strip().lower()
    if ad_type not in SUPPORTED_AD_TYPES:
        raise ValueError("unsupported_ad_type")

    settings = await get_ad_settings()
    ad_units = settings.get("ad_units", {}).copy()
    current = ad_units.get(ad_type, {})
    ad_units[ad_type] = {
        "enabled": enabled,
        "value": current.get("value", ""),
    }
    return await update_ad_settings({"ad_units": ad_units})


async def status_text() -> str:
    s = await get_ad_settings()
    units = s.get("ad_units", {})

    lines = [
        "<b>Ads Status</b>",
        f"Global Ads: <code>{'ON' if s.get('ads_enabled') else 'OFF'}</code>",
        f"Mode: <code>{s.get('mode')}</code>",
        "",
        "<b>Configured Ad Units</b>",
    ]

    for ad_type in ["smartlink", "interstitial", "rewarded_popup"]:
        unit = units.get(ad_type, {})
        lines.append(
            f"• <b>{ad_type}</b> → <code>{'ON' if unit.get('enabled') else 'OFF'}</code> | Value Set: <code>{'YES' if unit.get('value') else 'NO'}</code>"
        )

    lines.extend(
        [
            "",
            "<b>Commands</b>",
            "<code>/add_ad smartlink https://example.com</code>",
            "<code>/edit_ad interstitial ZONE_OR_SCRIPT</code>",
            "<code>/toggle_ad rewarded_popup on|off</code>",
            "<code>/remove_ad smartlink</code>",
            "<code>/set_ad_mode smartlink|interstitial|rewarded_popup|mixed</code>",
        ]
    )
    return "\n".join(lines)
