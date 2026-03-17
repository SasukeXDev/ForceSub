#(©)Codexbotz
#rymme

from aiohttp import web
from miniapp_interstitial import (
    complete,
    complete_verification,
    init_verification,
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


@routes.post("/api/verify/{token}/init")
async def verification_init_route(request):
    return await init_verification(request)


@routes.post("/api/verify/{token}/complete")
async def verification_complete_route(request):
    return await complete_verification(request)
