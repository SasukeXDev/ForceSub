#(©)Codexbotz
#rymme

from aiohttp import web
from miniapp_interstitial import (
    complete,
    interstitial_done,
    interstitial_miniapp,
    smartlink_done,
    verification_page,
)

routes = web.RouteTableDef()


@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response("CodeXBotz")


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
