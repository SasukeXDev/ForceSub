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
      <meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover' />
      <meta name='theme-color' content='#111827' />
      <title>Uchiha Developer</title>
      <script src='https://telegram.org/js/telegram-web-app.js'></script>
      <style>
        :root { --bg:#0b1020; --card:#111a34; --text:#e5e7eb; --muted:#9ca3af; --primary:#6366f1; --primary2:#8b5cf6; }
        * { box-sizing:border-box; }
        body {
          margin:0; min-height:100vh; display:grid; place-items:center; padding:24px;
          font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          color:var(--text);
          background: radial-gradient(circle at 20% 0%, #1e293b 0%, #0b1020 45%, #05070f 100%);
        }
        .card {
          width:min(520px,100%); border-radius:24px; padding:28px;
          background:linear-gradient(160deg, rgba(99,102,241,.12), rgba(17,24,39,.92));
          border:1px solid rgba(148,163,184,.22);
          box-shadow:0 20px 40px rgba(0,0,0,.35);
        }
        h1 { margin:0 0 8px; font-size:34px; letter-spacing:.3px; }
        p { margin:0; color:var(--muted); line-height:1.6; }
        .stack { margin-top:24px; display:grid; gap:12px; }
        .input {
          width:100%; border-radius:12px; border:1px solid rgba(148,163,184,.35);
          background:rgba(15,23,42,.65); color:var(--text); padding:12px 14px; font-size:14px;
        }
        .btn {
          width:100%; border:0; border-radius:12px; padding:12px 14px; font-weight:700;
          color:#fff; background:linear-gradient(90deg,var(--primary),var(--primary2)); cursor:pointer;
        }
        .note { margin-top:10px; font-size:13px; color:var(--muted); min-height:18px; }
      </style>
    </head>
    <body>
      <main class='card'>
        <h1>Uchiha Developer</h1>
        <p>Welcome to the home page. Paste your verification token below to open the verification link directly in Telegram WebApp.</p>

        <div class='stack'>
          <input id='tokenInput' class='input' placeholder='Enter verification token' />
          <button id='openBtn' class='btn'>Open Verification</button>
        </div>
        <div id='note' class='note'></div>
      </main>

      <script>
        (function () {
          const tg = window.Telegram && Telegram.WebApp ? Telegram.WebApp : null;
          if (tg) {
            tg.ready();
            tg.expand();
          }

          const params = new URLSearchParams(window.location.search);
          const presetToken = params.get('token') || params.get('verify') || '';
          const input = document.getElementById('tokenInput');
          const openBtn = document.getElementById('openBtn');
          const note = document.getElementById('note');

          input.value = presetToken;

          function openVerification(token) {
            if (!token) {
              note.textContent = 'Please enter a valid token.';
              return;
            }

            const verifyUrl = window.location.origin + '/verify/' + encodeURIComponent(token.trim());
            note.textContent = 'Opening verification...';

            if (tg && typeof tg.openLink === 'function') {
              tg.openLink(verifyUrl);
              return;
            }

            window.location.href = verifyUrl;
          }

          openBtn.addEventListener('click', function () {
            openVerification(input.value);
          });

          if (presetToken) {
            openVerification(presetToken);
          }
        })();
      </script>
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
