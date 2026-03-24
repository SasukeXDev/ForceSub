from datetime import datetime, timezone
import json
import logging

from aiohttp import web

from config import WEB_BASE_URL
from database.ads_database import get_ad_settings
from verification_system import (
    complete_ad_session,
    get_token_or_none,
    mark_smartlink_completed,
    register_page_visit,
    start_ad_session,
)

LOGGER = logging.getLogger(__name__)


def _tg_open_link(path: str) -> str:
    if WEB_BASE_URL:
        return f"{WEB_BASE_URL}{path}"
    return path


def _seconds_until(dt: datetime) -> int:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return max(0, int((dt - now).total_seconds()))


def _normalize_zone_id(raw: str) -> str:
    return "".join(ch for ch in (raw or "") if ch.isdigit())


async def verification_page(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await register_page_visit(token)
    if not data:
        return web.Response(text="Error: Verification token invalid, expired, or blocked.", status=400)

    settings = await get_ad_settings()
    required = data.get("required_steps", [])
    if not required or not settings.get("ads_enabled"):
        raise web.HTTPFound(_tg_open_link(f"/complete/{token}"))

    ad_ready_in = _seconds_until(data.get("ad_available_at", datetime.utcnow()))
    progress = int((len(data.get("completed_steps", [])) / max(1, len(required))) * 100)
    smartlink = settings.get("smartlink_url", "")
    zone_id = _normalize_zone_id(settings.get("interstitial_script", ""))

    required_json = json.dumps(required)
    smartlink_json = json.dumps(smartlink)
    token_json = json.dumps(token)
    zone_json = json.dumps(zone_id)

    html = f"""
    <!doctype html>
    <html lang='en'>
    <head>
      <meta charset='utf-8' />
      <meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover' />
      <meta name='theme-color' content='#111827' />
      <title>File Verification Required</title>
      <script src='https://telegram.org/js/telegram-web-app.js'></script>
      <script src='//libtl.com/sdk.js' data-zone='{zone_id}' data-sdk='show_{zone_id}'></script>
      <style>
        :root {{ --card-bg: rgba(255,255,255,.85); --text:#0f172a; --muted:#475569; --primary:#2563eb; --accent:#7c3aed; --ok:#16a34a; --err:#dc2626; }}
        @media (prefers-color-scheme: dark) {{
          :root {{ --card-bg: rgba(15,23,42,.86); --text:#e2e8f0; --muted:#94a3b8; --primary:#60a5fa; --accent:#a78bfa; --ok:#4ade80; --err:#f87171; }}
        }}
        * {{ box-sizing: border-box; }}
        body {{ margin:0; min-height:100vh; display:grid; place-items:center; padding:16px; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: var(--text); background: linear-gradient(135deg, #dbeafe, #ede9fe 60%, #bfdbfe); }}
        .card {{ width:min(480px,100%); border-radius:22px; padding:22px; background:var(--card-bg); backdrop-filter: blur(12px); box-shadow: 0 12px 40px rgba(2,6,23,.2); }}
        h1 {{ margin:0 0 8px; font-size:24px; }}
        .sub {{ margin:0 0 16px; color:var(--muted); font-size:14px; }}
        .progress {{ height:10px; border-radius:999px; background:rgba(148,163,184,.35); overflow:hidden; margin:10px 0 14px; }}
        .bar {{ height:100%; width:{progress}%; background:linear-gradient(90deg,var(--primary),var(--accent)); transition:width .4s ease; }}
        .steps {{ margin:0 0 18px; padding-left:18px; color:var(--muted); font-size:14px; line-height:1.7; }}
        .btn {{ width:100%; border:0; border-radius:14px; padding:14px 16px; font-weight:700; background:linear-gradient(90deg,var(--primary),var(--accent)); color:#fff; cursor:pointer; box-shadow:0 8px 20px rgba(37,99,235,.35); }}
        .btn[disabled] {{ opacity:.55; cursor:not-allowed; box-shadow:none; }}
        .status {{ font-size:13px; color:var(--muted); min-height:20px; margin-top:10px; }}
        .status.error {{ color:var(--err); }}
        .status.ok {{ color:var(--ok); }}
        .retry {{ margin-top:12px; display:none; text-align:center; color:var(--primary); font-size:13px; cursor:pointer; font-weight:600; }}
      </style>
    </head>
    <body>
      <div class='card'>
        <h1>Verification Required</h1>
        <p class='sub'>Complete verification to unlock your file in Telegram.</p>
        <div class='progress'><div id='bar' class='bar'></div></div>
        <ol class='steps'>
          <li>Start verification</li>
          <li>Watch ad</li>
          <li>Open SmartLink (if required)</li>
          <li>Back to bot and unlock</li>
        </ol>
        <button class='btn' id='watchBtn' disabled>Preparing… <span id='count'>{ad_ready_in}</span>s</button>
        <div class='status' id='status'>Waiting for cooldown…</div>
        <div id='retry' class='retry'>Retry verification</div>
      </div>

      <script>
        (function() {{
          const token = {token_json};
          const requiredSteps = {required_json};
          const smartlink = {smartlink_json};
          const zoneId = {zone_json};
          const watchBtn = document.getElementById('watchBtn');
          const count = document.getElementById('count');
          const status = document.getElementById('status');
          const retry = document.getElementById('retry');
          const bar = document.getElementById('bar');

          let remaining = {ad_ready_in};
          let adStarted = false;
          let adNonce = '';

          const tg = (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null;
          if (tg) {{
            tg.ready();
            tg.expand();
          }}

          function log(...args) {{ console.log('[verify]', ...args); }}
          function setProgress(v) {{ bar.style.width = Math.max(5, Math.min(100, v)) + '%'; }}
          function setStatus(msg, cls) {{ status.textContent = msg; status.className = 'status' + (cls ? ' ' + cls : ''); }}

          async function callApi(url, payload) {{
            const res = await fetch(url, {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify(payload || {{}})
            }});
            const body = await res.json().catch(() => ({{ ok: false, error: 'invalid_json' }}));
            if (!res.ok || !body.ok) throw new Error(body.error || ('http_' + res.status));
            return body;
          }}

          function openInsideTelegram(url) {{
            if (tg && typeof tg.openLink === 'function') {{
              tg.openLink(url, {{ try_instant_view: false, try_browser: false }});
            }} else {{
              window.location.href = url;
            }}
          }}

          async function waitForSdk(maxMs) {{
            const sdkFn = 'show_' + zoneId;
            const started = Date.now();
            while (Date.now() - started < maxMs) {{
              if (typeof window[sdkFn] === 'function') return window[sdkFn];
              await new Promise(r => setTimeout(r, 120));
            }}
            throw new Error('sdk_not_loaded');
          }}

          async function startFlow() {{
            if (adStarted) return;
            adStarted = true;
            retry.style.display = 'none';
            watchBtn.disabled = true;

            try {{
              setStatus('Starting verification…');
              setProgress(18);

              const started = await callApi('/api/verification/' + token + '/start-ad', {{
                tg_user_id: tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : null,
                tg_init_data: tg ? tg.initData : ''
              }});
              adNonce = started.session_nonce || '';

              setStatus('Loading ad SDK…');
              setProgress(40);

              let adOk = false;
              if (zoneId) {{
                const showAd = await waitForSdk(7000);
                const adResult = await showAd({{
                  type: 'inApp',
                  inAppSettings: {{
                    frequency: 2,
                    capping: 0.1,
                    interval: 30,
                    timeout: 10,
                    everyPage: false
                  }}
                }});
                adOk = !!adResult;
                log('adResult', adResult);
              }}

              if (!adOk && smartlink) {{
                setStatus('Ad unavailable, opening SmartLink fallback…');
                openInsideTelegram(smartlink);
                await new Promise(r => setTimeout(r, 2500));
                adOk = true;
              }}

              if (!adOk) throw new Error('ad_not_completed');

              setStatus('Finalizing verification…');
              setProgress(78);

              const completed = await callApi('/api/verification/' + token + '/complete-ad', {{
                ad_completed: true,
                session_nonce: adNonce,
                tg_user_id: tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : null,
                smartlink_opened: !!smartlink
              }});

              setProgress(100);
              setStatus('Verification complete. Redirecting…', 'ok');
              openInsideTelegram(completed.redirect_url || ('/complete/' + token));
            }} catch (err) {{
              log('verification_error', err);
              setStatus('Error: ' + (err && err.message ? err.message : 'unknown_error'), 'error');
              retry.style.display = 'block';
              watchBtn.disabled = false;
              watchBtn.textContent = 'Retry Verification';
              adStarted = false;
            }}
          }}

          const timer = setInterval(() => {{
            if (remaining <= 0) {{
              clearInterval(timer);
              watchBtn.disabled = false;
              watchBtn.textContent = 'Start Verification';
              setStatus('Ready to verify');
              return;
            }}
            remaining -= 1;
            count.textContent = remaining;
          }}, 1000);

          retry.onclick = startFlow;
          watchBtn.onclick = startFlow;
          setProgress(Math.max(6, Math.min(20, requiredSteps.length * 8)));
        }})();
      </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")


async def start_ad(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")

    payload = await request.json() if request.can_read_body else {}
    tg_user_id = payload.get("tg_user_id")
    try:
        normalized_user_id = int(tg_user_id) if tg_user_id is not None else None
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "invalid_tg_user_id"}, status=400)

    data = await start_ad_session(token, normalized_user_id)
    if not data:
        return web.json_response({"ok": False, "error": "token_invalid_or_step_rejected"}, status=400)

    if _seconds_until(data.get("ad_available_at", datetime.utcnow())) > 0:
        return web.json_response({"ok": False, "error": "cooldown_not_ready"}, status=429)

    LOGGER.info("ad_start token=%s user_id=%s attempts=%s", token, normalized_user_id, data.get("ad_attempts"))
    return web.json_response(
        {
            "ok": True,
            "attempts": data.get("ad_attempts", 0),
            "session_nonce": data.get("ad_session_nonce", ""),
        }
    )


async def complete_ad(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    payload = await request.json() if request.can_read_body else {}

    if not payload.get("ad_completed"):
        return web.json_response({"ok": False, "error": "ad_incomplete"}, status=400)

    session_nonce = (payload.get("session_nonce") or "").strip()
    if not session_nonce:
        return web.json_response({"ok": False, "error": "missing_session_nonce"}, status=400)

    tg_user_id = payload.get("tg_user_id")
    try:
        normalized_user_id = int(tg_user_id) if tg_user_id is not None else None
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "invalid_tg_user_id"}, status=400)

    data = await complete_ad_session(token, normalized_user_id, session_nonce)
    if not data:
        return web.json_response({"ok": False, "error": "ad_session_invalid"}, status=400)

    if payload.get("smartlink_opened"):
        data = await mark_smartlink_completed(token, normalized_user_id)

    LOGGER.info("ad_complete token=%s user_id=%s", token, normalized_user_id)
    return web.json_response({"ok": True, "redirect_url": _tg_open_link(f"/complete/{token}")})


async def smartlink_done(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await mark_smartlink_completed(token, user_id=None)
    if not data:
        return web.Response(text="Invalid token.", status=400)
    raise web.HTTPFound(_tg_open_link(f"/verify/{token}"))


async def interstitial_miniapp(request: web.Request) -> web.Response:
    raise web.HTTPFound(_tg_open_link(f"/verify/{request.match_info.get('token', '')}"))


async def interstitial_done(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await get_token_or_none(token)
    if not data:
        return web.Response(text="Invalid token.", status=400)
    raise web.HTTPFound(_tg_open_link(f"/complete/{token}"))


async def complete(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await get_token_or_none(token)
    if not data:
        return web.Response(text="Error: Token expired. Re-open your original bot link.", status=400)

    deep_link = f"https://t.me/{request.app['bot_username']}?start=unlock_{token}"
    deep_link_json = json.dumps(deep_link)
    html = f"""
    <html>
      <body style='font-family:sans-serif;padding:20px;'>
        <h3>Verification complete</h3>
        <p>Returning you to the bot now...</p>
        <a href='{deep_link}'>Return to bot and unlock file</a>
        <script>
          (function() {{
            const url = {deep_link_json};
            const tg = (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null;
            if (tg) {{
              tg.ready();
              tg.openTelegramLink(url);
            }} else {{
              window.location.href = url;
            }}
          }})();
        </script>
      </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")
