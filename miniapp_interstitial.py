from aiohttp import web
import json
from pathlib import Path

from config import WEB_BASE_URL
from database.ads_database import get_ad_settings
from verification_system import complete_step, get_token_or_none


WEB_DIR = Path(__file__).resolve().parent / "web"
VERIFICATION_TEMPLATE = WEB_DIR / "verification.html"


def _tg_open_link(path: str) -> str:
    if WEB_BASE_URL:
        return f"{WEB_BASE_URL}{path}"
    return path


async def verification_page(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await get_token_or_none(token)
    if not data:
        return web.Response(text="Verification token invalid or expired.", status=400)

    settings = await get_ad_settings()
    required = data.get("required_steps", [])
    if not required or not settings.get("ads_enabled"):
        await complete_step(token, "smartlink")
        await complete_step(token, "interstitial")
        raise web.HTTPFound(_tg_open_link(f"/complete/{token}"))

    if "smartlink" in required and "smartlink" not in data.get("completed_steps", []):
        smartlink = settings.get("smartlink_url", "")
        if not smartlink:
            return web.Response(text="SmartLink is not configured by admin.", status=500)

        html = f"""
        <html><body style='font-family:sans-serif;padding:24px;'>
        <h3>Step 1/2 - SmartLink Verification</h3>
        <p>Open ad link, then come back and continue.</p>
        <a href='{smartlink}' target='_blank'>Open Monetag SmartLink</a><br/><br/>
        <a href='{_tg_open_link(f"/smartlink_done/{token}")}'>I viewed the ad, continue</a>
        </body></html>
        """
        return web.Response(text=html, content_type="text/html")

    if "interstitial" in required and "interstitial" not in data.get("completed_steps", []):
        raise web.HTTPFound(_tg_open_link(f"/miniapp/interstitial/{token}"))

    raise web.HTTPFound(_tg_open_link(f"/complete/{token}"))


async def smartlink_done(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await complete_step(token, "smartlink")
    if not data:
        return web.Response(text="Invalid token.", status=400)
    raise web.HTTPFound(_tg_open_link(f"/verify/{token}"))


async def interstitial_miniapp(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await get_token_or_none(token)
    if not data:
        return web.Response(text="Invalid or expired token.", status=400)

    settings = await get_ad_settings()
    script_or_zone = settings.get("interstitial_script", "")
    if not script_or_zone:
        return web.Response(text="Interstitial is not configured by admin.", status=500)

    context = {
        "token": token,
        "interstitialScript": script_or_zone,
        "interstitialDoneUrl": _tg_open_link(f"/interstitial_done/{token}"),
    }
    template = VERIFICATION_TEMPLATE.read_text(encoding="utf-8")
    html = template.replace("__VERIFICATION_CONTEXT__", json.dumps(context))
    return web.Response(text=html, content_type="text/html")


async def interstitial_done(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await complete_step(token, "interstitial")
    if not data:
        return web.Response(text="Invalid token.", status=400)
    raise web.HTTPFound(_tg_open_link(f"/complete/{token}"))


async def complete(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await get_token_or_none(token)
    if not data:
        return web.Response(text="Token expired. Re-open your original bot link.", status=400)
    deep_link = f"https://t.me/{request.app['bot_username']}?start=unlock_{token}"
    html = f"""
    <html><body style='font-family:sans-serif;padding:20px;'>
    <h3>Verification complete</h3>
    <a href='{deep_link}'>Return to bot and unlock file</a>
    </body></html>
    """
    return web.Response(text=html, content_type="text/html")
