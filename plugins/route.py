#(©)Codexbotz
#rymme

from pathlib import Path

from aiohttp import web
from miniapp_interstitial import (
    complete,
    interstitial_done,
    interstitial_miniapp,
    smartlink_done,
    verification_page,
)

routes = web.RouteTableDef()

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response("CodeXBotz")


@routes.get("/web/{filename}")
async def web_asset_route(request):
    filename = request.match_info.get("filename", "")
    if filename not in {"verification.css", "verification.js"}:
        raise web.HTTPNotFound()
    return web.FileResponse(WEB_DIR / filename)


@routes.get("/verify/{token}")
async def verify_token(request):
    return await verification_page(request)


@routes.get("/smartlink_done/{token}")
async def smartlink_done_route(request):
    return await smartlink_done(request)


@routes.get("/miniapp/interstitial/{token}")
async def interstitial_route(request):
    return await interstitial_miniapp(request)


@routes.get("/interstitial_done/{token}")
async def interstitial_done_route(request):
    return await interstitial_done(request)


@routes.get("/complete/{token}")
async def complete_route(request):
    return await complete(request)
