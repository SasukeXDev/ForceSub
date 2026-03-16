#(©)Codexbotz
#rymme

from aiohttp import web
from miniapp_interstitial import (
    complete,
    interstitial_done,
    interstitial_miniapp,
    smartlink_done,
    verification_page,
    start_ad,
    complete_ad,
)

routes = web.RouteTableDef()


@routes.get("/", allow_head=True)
async def root_route_handler(request):
    html = """
    <!doctype html>
    <html lang='en'>
    <head>
      <meta charset='utf-8' />
      <meta name='viewport' content='width=device-width,initial-scale=1' />
      <title>Uchiha Developer</title>
      <style>
        *{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at top,#1e1b4b,#020617);font-family:Inter,Segoe UI,sans-serif;color:#e2e8f0;padding:20px}
        .wrap{width:min(720px,100%);padding:28px;border-radius:20px;background:rgba(15,23,42,.75);border:1px solid rgba(148,163,184,.25);box-shadow:0 20px 48px rgba(2,6,23,.6)}
        h1{font-size:40px;margin:0 0 10px}.tag{color:#93c5fd;margin:0 0 14px}.desc{color:#cbd5e1;line-height:1.7}
        .btn{display:inline-block;margin-top:14px;padding:12px 18px;border-radius:12px;text-decoration:none;color:white;background:linear-gradient(90deg,#06b6d4,#4f46e5)}
      </style>
    </head>
    <body>
      <main class='wrap'>
        <h1>Uchiha Developer</h1>
        <p class='tag'>Secure File Unlock System</p>
        <p class='desc'>Welcome to the official verification gateway. This web app integrates Monetag ads (Interstitial, Rewarded Popup, and SmartLink) before unlocking protected files in Telegram bot flow.</p>
        <a class='btn' href='https://t.me/Uchiha_Developer' target='_blank' rel='noopener'>Contact Developer</a>
      </main>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")


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


@routes.post("/api/verification/{token}/start-ad")
async def start_ad_route(request):
    return await start_ad(request)


@routes.post("/api/verification/{token}/complete-ad")
async def complete_ad_route(request):
    return await complete_ad(request)
