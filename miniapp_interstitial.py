from datetime import datetime, timezone

from aiohttp import web

from config import WEB_BASE_URL
from database.ads_database import get_ad_settings
from verification_system import (
    can_start_ad_attempt,
    complete_step,
    get_token_or_none,
    register_page_visit,
)


def _tg_open_link(path: str) -> str:
    if WEB_BASE_URL:
        return f"{WEB_BASE_URL}{path}"
    return path


def _seconds_until(dt: datetime) -> int:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return max(0, int((dt - now).total_seconds()))


async def verification_page(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await register_page_visit(token)
    if not data:
        return web.Response(text="Verification token invalid, expired, or blocked.", status=400)

    settings = await get_ad_settings()
    required = data.get("required_steps", [])
    if not required or not settings.get("ads_enabled"):
        for step in required:
            await complete_step(token, step)
        raise web.HTTPFound(_tg_open_link(f"/complete/{token}"))

    ad_ready_in = _seconds_until(data.get("ad_available_at", datetime.utcnow()))
    progress = int((len(data.get("completed_steps", [])) / max(1, len(required))) * 100)
    ad_units = settings.get("ad_units", {})

    html = f"""
    <!doctype html>
    <html lang='en'>
    <head>
      <meta charset='utf-8' />
      <meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover' />
      <meta name='theme-color' content='#111827' />
      <title>File Verification Required</title>
      <script src='https://telegram.org/js/telegram-web-app.js'></script>
      <script src='//libtl.com/sdk.js' data-zone='10739699' data-sdk='show_10739699'></script>
      <style>
        :root {{ --card-bg: rgba(255,255,255,.85); --text:#0f172a; --muted:#475569; --primary:#2563eb; --accent:#7c3aed; }}
        * {{ box-sizing: border-box; }}
        body {{ margin:0; min-height:100vh; display:grid; place-items:center; padding:20px; font-family: Inter, sans-serif; color: var(--text); background: linear-gradient(135deg, #dbeafe, #ede9fe 60%, #bfdbfe); }}
        .card {{ width:min(460px,100%); border-radius:22px; padding:22px; background:var(--card-bg); backdrop-filter: blur(12px); box-shadow: 0 12px 40px rgba(2,6,23,.2); }}
        .progress {{ height:10px; border-radius:999px; background:rgba(148,163,184,.35); overflow:hidden; margin:10px 0 14px; }}
        .bar {{ height:100%; width:{progress}%; background:linear-gradient(90deg,var(--primary),var(--accent)); transition:width .4s ease; }}
        .btn {{ width:100%; border:0; border-radius:14px; padding:14px 16px; font-weight:700; background:linear-gradient(90deg,var(--primary),var(--accent)); color:#fff; cursor:pointer; }}
      </style>
    </head>
    <body>
      <div class='card'>
        <h1>Verification Required</h1>
        <p>Complete ad verification to unlock your file.</p>
        <div class='progress'><div id='bar' class='bar'></div></div>
        <button class='btn' id='watchBtn' disabled>Preparing… <span id='count'>{ad_ready_in}</span>s</button>
        <p id='status'>Waiting for cooldown...</p>
      </div>

      <script>
        (function() {{
          const token = {token!r};
          const requiredSteps = {required!r};
          const adUnits = {ad_units!r};
          const watchBtn = document.getElementById('watchBtn');
          const count = document.getElementById('count');
          const status = document.getElementById('status');
          const bar = document.getElementById('bar');

          const tg = (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null;
          if (tg) {{ tg.ready(); tg.expand(); }}

          let remaining = {ad_ready_in};
          let adStarted = false;

          const timer = setInterval(() => {{
            if (remaining <= 0) {{
              clearInterval(timer);
              watchBtn.disabled = false;
              watchBtn.textContent = 'Start Verification';
              status.textContent = 'Ready to verify.';
              return;
            }}
            remaining -= 1;
            count.textContent = remaining;
          }}, 1000);

          function setProgress(pct) {{
            bar.style.width = Math.max(5, Math.min(100, pct)) + '%';
          }}

          function openSmartLink(url) {{
            if (!url) return;
            if (tg && typeof tg.openLink === 'function') tg.openLink(url);
            else window.open(url, '_blank');
          }}

          async function callApi(url, payload) {{
            const res = await fetch(url, {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify(payload || {{}})
            }});
            if (!res.ok) throw new Error('Request failed');
            return await res.json();
          }}

          async function runSingleStep(step) {{
            const ad = adUnits[step] || {{}};
            const value = ad.value || '';

            if (step === 'smartlink') {{
              openSmartLink(value);
              await new Promise(r => setTimeout(r, 2500));
              return true;
            }}

            if (step === 'interstitial') {{
              if (typeof window.show_10739699 === 'function') {{
                const adResult = await window.show_10739699();
                if (adResult) return true;
              }}
              if (value) {{
                openSmartLink(value);
                await new Promise(r => setTimeout(r, 2500));
                return true;
              }}
            }}

            if (step === 'rewarded_popup') {{
              if (value) {{
                openSmartLink(value);
                await new Promise(r => setTimeout(r, 3000));
                return true;
              }}
            }}
            return false;
          }}

          async function startFlow() {{
            if (adStarted) return;
            adStarted = true;
            watchBtn.disabled = true;

            try {{
              await callApi('/api/verification/' + token + '/start-ad', {{
                tg_init_data: tg ? tg.initData : '',
                tg_user_id: tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : null
              }});

              for (let i = 0; i < requiredSteps.length; i++) {{
                status.textContent = 'Running ' + requiredSteps[i] + '...';
                setProgress(20 + Math.floor(((i + 1) / requiredSteps.length) * 60));
                const ok = await runSingleStep(requiredSteps[i]);
                if (!ok) throw new Error('Step failed: ' + requiredSteps[i]);
              }}

              await callApi('/api/verification/' + token + '/complete-ad', {{ ad_completed: true }});
              status.textContent = 'Complete. Redirecting...';
              setProgress(100);
              window.location.href = '/complete/' + token;
            }} catch (err) {{
              status.textContent = 'Verification failed. Retry.';
              watchBtn.disabled = false;
              watchBtn.textContent = 'Retry Verification';
              adStarted = false;
            }}
          }}

          watchBtn.onclick = startFlow;
          setProgress(10);
        }})();
      </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")


async def start_ad(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await can_start_ad_attempt(token)
    if not data:
        return web.json_response({"ok": False, "error": "token_invalid_or_blocked"}, status=400)

    payload = await request.json() if request.can_read_body else {}
    tg_user_id = payload.get("tg_user_id")
    token_user_id = data.get("user_id")
    if tg_user_id and token_user_id and int(tg_user_id) != int(token_user_id):
        return web.json_response({"ok": False, "error": "user_mismatch"}, status=403)

    if _seconds_until(data.get("ad_available_at", datetime.utcnow())) > 0:
        return web.json_response({"ok": False, "error": "cooldown_not_ready"}, status=429)

    return web.json_response({"ok": True, "attempts": data.get("ad_attempts", 0)})


async def complete_ad(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await get_token_or_none(token)
    if not data:
        return web.json_response({"ok": False, "error": "token_invalid"}, status=400)

    payload = await request.json() if request.can_read_body else {}
    if not payload.get("ad_completed"):
        return web.json_response({"ok": False, "error": "ad_incomplete"}, status=400)

    for step in data.get("required_steps", []):
        await complete_step(token, step)

    return web.json_response({"ok": True})


async def smartlink_done(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await complete_step(token, "smartlink")
    if not data:
        return web.Response(text="Invalid token.", status=400)
    raise web.HTTPFound(_tg_open_link(f"/verify/{token}"))


async def interstitial_miniapp(request: web.Request) -> web.Response:
    raise web.HTTPFound(_tg_open_link(f"/verify/{request.match_info.get('token', '')}"))


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
    <p>Returning you to the bot now...</p>
    <a href='{deep_link}'>Return to bot and unlock file</a>
    <script>setTimeout(function(){{window.location.href={deep_link!r};}}, 1200);</script>
    </body></html>
    """
    return web.Response(text=html, content_type="text/html")
