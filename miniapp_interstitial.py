from datetime import datetime, timezone
import re

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
        await complete_step(token, "smartlink")
        await complete_step(token, "interstitial")
        raise web.HTTPFound(_tg_open_link(f"/complete/{token}"))

    ad_ready_in = _seconds_until(data.get("ad_available_at", datetime.utcnow()))
    progress = int((len(data.get("completed_steps", [])) / max(1, len(required))) * 100)
    smartlink = settings.get("smartlink_url", "")

    script_or_zone = (settings.get("interstitial_script") or "").strip()
    interstitial_callable = "show_10739699"
    if script_or_zone and "<script" not in script_or_zone.lower():
        interstitial_callable = f"show_{script_or_zone}"
        interstitial_script_block = (
            f"<script src='//libtl.com/sdk.js' data-zone='{script_or_zone}' "
            f"data-sdk='{interstitial_callable}'></script>"
        )
    elif script_or_zone:
        interstitial_script_block = script_or_zone
        match = re.search(r"data-sdk\s*=\s*['\"]([^'\"]+)['\"]", script_or_zone, flags=re.IGNORECASE)
        if match:
            interstitial_callable = match.group(1)
    else:
        interstitial_script_block = (
            "<script src='//libtl.com/sdk.js' data-zone='10739699' data-sdk='show_10739699'></script>"
        )

    html = f"""
    <!doctype html>
    <html lang='en'>
    <head>
      <meta charset='utf-8' />
      <meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover' />
      <meta name='theme-color' content='#111827' />
      <title>File Verification Required</title>
      <script src='https://telegram.org/js/telegram-web-app.js'></script>
      {interstitial_script_block}
      <style>
        :root {{ --card-bg: rgba(255,255,255,.85); --text:#0f172a; --muted:#475569; --primary:#2563eb; --accent:#7c3aed; }}
        @media (prefers-color-scheme: dark) {{
          :root {{ --card-bg: rgba(15,23,42,.86); --text:#e2e8f0; --muted:#94a3b8; --primary:#60a5fa; --accent:#a78bfa; }}
        }}
        * {{ box-sizing: border-box; }}
        body {{
          margin:0; min-height:100vh; display:grid; place-items:center; padding:20px;
          font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          color: var(--text);
          background: linear-gradient(135deg, #dbeafe, #ede9fe 60%, #bfdbfe);
        }}
        .card {{
          width:min(460px,100%); border-radius:22px; padding:22px;
          background:var(--card-bg); backdrop-filter: blur(12px);
          box-shadow: 0 12px 40px rgba(2,6,23,.2);
          animation: in .45s ease;
        }}
        @keyframes in {{ from {{ transform:translateY(8px);opacity:0; }} to {{ transform:translateY(0);opacity:1; }} }}
        h1 {{ margin:0 0 8px; font-size:24px; }}
        .sub {{ margin:0 0 16px; color:var(--muted); font-size:14px; }}
        .progress {{ height:10px; border-radius:999px; background:rgba(148,163,184,.35); overflow:hidden; margin:10px 0 14px; }}
        .bar {{ height:100%; width:{progress}%; background:linear-gradient(90deg,var(--primary),var(--accent)); transition:width .4s ease; }}
        .steps {{ margin:0 0 18px; padding-left:18px; color:var(--muted); font-size:14px; line-height:1.7; }}
        .btn {{
          width:100%; border:0; border-radius:14px; padding:14px 16px; font-weight:700;
          background:linear-gradient(90deg,var(--primary),var(--accent)); color:#fff; cursor:pointer;
          transition:transform .15s ease, opacity .15s ease, box-shadow .2s;
          box-shadow:0 8px 20px rgba(37,99,235,.35);
        }}
        .btn:active {{ transform:scale(.98); }}
        .btn[disabled] {{ opacity:.55; cursor:not-allowed; box-shadow:none; }}
        .row {{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:12px; }}
        .badge {{ font-size:12px; color:var(--muted); }}
        .status {{ font-size:13px; color:var(--muted); min-height:20px; }}
        .footer {{ text-align:center; font-size:12px; color:var(--muted); margin-top:16px; }}
        .retry {{ margin-top:10px; display:none; text-align:center; color:var(--primary); font-size:13px; cursor:pointer; }}
      </style>
    </head>
    <body>
      <div class='card'>
        <h1>File Verification Required</h1>
        <p class='sub'>Complete a quick verification to unlock your file.</p>

        <div class='progress'><div id='bar' class='bar'></div></div>
        <ol class='steps'>
          <li>Initialize verification</li>
          <li>Load ad</li>
          <li>Complete verification</li>
          <li>Redirect to bot</li>
        </ol>

        <button class='btn' id='watchBtn' disabled>Preparing verification… <span id='count'>{ad_ready_in}</span>s</button>
        <div class='row'>
          <div class='status' id='status'>Waiting for cooldown...</div>
          <div class='badge'>Protected by secure verification</div>
        </div>
        <div id='retry' class='retry'>Retry verification</div>

        <div class='footer'>This helps us keep the bot free.</div>
      </div>

      <script>
        (function() {{
          const token = {token!r};
          const requiredSteps = {required!r};
          const smartlink = {smartlink!r};
          const interstitialFnName = {interstitial_callable!r};
          const interstitialCandidates = Array.from(new Set([interstitialFnName, 'show_10739699']));
          const needInterstitial = requiredSteps.includes('interstitial');
          const needSmartlink = requiredSteps.includes('smartlink');
          const watchBtn = document.getElementById('watchBtn');
          const count = document.getElementById('count');
          const status = document.getElementById('status');
          const retry = document.getElementById('retry');
          const bar = document.getElementById('bar');

          if (window.Telegram && Telegram.WebApp) {{
            Telegram.WebApp.ready();
            Telegram.WebApp.expand();
          }}

          let remaining = {ad_ready_in};
          let adStarted = false;

          const timer = setInterval(() => {{
            if (remaining <= 0) {{
              clearInterval(timer);
              watchBtn.disabled = false;
              watchBtn.textContent = 'Watch Ad';
              status.textContent = 'Ready to verify.';
              return;
            }}
            remaining -= 1;
            count.textContent = remaining;
          }}, 1000);

          function setProgress(pct) {{
            bar.style.width = Math.max(5, Math.min(100, pct)) + '%';
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

          function openSmartLink() {{
            if (!smartlink) return false;
            const tg = (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null;
            if (tg && typeof tg.openLink === 'function') {{
              tg.openLink(smartlink);
              return true;
            }}
            window.open(smartlink, '_blank');
            return true;
          }}

          async function waitForInterstitialFn() {{
            const started = Date.now();
            while ((Date.now() - started) < 8000) {{
              for (const fnName of interstitialCandidates) {{
                if (typeof window[fnName] === 'function') return window[fnName];
              }}
              await new Promise(r => setTimeout(r, 250));
            }}
            return null;
          }}

          async function playInterstitial() {{
            let fn = null;
            for (const fnName of interstitialCandidates) {{
              if (typeof window[fnName] === 'function') {{
                fn = window[fnName];
                break;
              }}
            }}
            if (typeof fn !== 'function') {{
              fn = await waitForInterstitialFn();
            }}
            if (typeof fn !== 'function') throw new Error('Interstitial SDK not ready');

            const result = await fn({{
              type: 'interstitial',
            }});
            if (result === false) throw new Error('Interstitial was not shown');
            return true;
          }}

          async function startFlow() {{
            if (adStarted) return;
            adStarted = true;
            watchBtn.disabled = true;
            status.textContent = 'Starting verification...';
            setProgress(25);

            try {{
              const tg = (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null;
              await callApi('/api/verification/' + token + '/start-ad', {{
                tg_init_data: tg ? tg.initData : '',
                tg_user_id: tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : null
              }});

              if (needInterstitial) {{
                status.textContent = 'Loading interstitial...';
                setProgress(45);
                await playInterstitial();
              }}

              if (needInterstitial) {{
                await callApi('/api/verification/' + token + '/complete-ad', {{ ad_completed: true }});
              }}

              if (needSmartlink) {{
                status.textContent = 'Opening SmartLink...';
                setProgress(75);
                const opened = openSmartLink();
                if (!opened) throw new Error('SmartLink unavailable');
                await callApi('/api/verification/' + token + '/complete-smartlink', {{ smartlink_opened: true }});
              }}

              setProgress(100);
              status.textContent = 'Verification complete. Redirecting...';
              window.location.href = '/complete/' + token;
            }} catch (err) {{
              status.textContent = 'Verification failed. Please retry.';
              retry.style.display = 'block';
              watchBtn.disabled = false;
              watchBtn.textContent = 'Watch Ad';
              adStarted = false;
            }}
          }}

          retry.onclick = () => {{ retry.style.display = 'none'; startFlow(); }};
          watchBtn.onclick = startFlow;
          setProgress(20);
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

    if "interstitial" in data.get("required_steps", []):
        await complete_step(token, "interstitial")
    return web.json_response({"ok": True})


async def complete_smartlink(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await get_token_or_none(token)
    if not data:
        return web.json_response({"ok": False, "error": "token_invalid"}, status=400)

    payload = await request.json() if request.can_read_body else {}
    if not payload.get("smartlink_opened"):
        return web.json_response({"ok": False, "error": "smartlink_incomplete"}, status=400)

    if "smartlink" in data.get("required_steps", []):
        await complete_step(token, "smartlink")
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
