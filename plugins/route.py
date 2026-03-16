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
        :root { --bg:#020617; --card:#111827; --accent:#6366f1; --text:#e2e8f0; --muted:#94a3b8; }
        * { box-sizing: border-box; }
        body {
          margin:0; min-height:100vh; display:grid; place-items:center; padding:20px;
          font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          color:var(--text); background: radial-gradient(circle at top,#1e1b4b 0,#020617 55%);
        }
        .card {
          width:min(680px, 100%); border:1px solid rgba(148,163,184,.25); border-radius:22px; padding:32px;
          background: linear-gradient(145deg, rgba(15,23,42,.95), rgba(17,24,39,.95));
          box-shadow:0 30px 70px rgba(2,6,23,.45);
        }
        .label { color:var(--accent); letter-spacing:.12em; text-transform:uppercase; font-weight:700; font-size:12px; }
        h1 { margin:.35rem 0 .6rem; font-size:clamp(32px,6vw,48px); }
        p { margin:0; color:var(--muted); line-height:1.7; }
      </style>
    </head>
    <body>
      <section class='card'>
        <div class='label'>Welcome</div>
        <h1>Uchiha Developer</h1>
        <p>Powering secure Telegram file verification with a smoother mini app experience and flexible ads setup.</p>
      </section>
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
