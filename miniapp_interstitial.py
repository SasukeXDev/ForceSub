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


def _sanitize_zone_id(zone_id: str) -> str:
    return "".join(ch for ch in str(zone_id or "") if ch.isdigit())


def _script_for_zone(zone_id: str) -> str:
    zone = _sanitize_zone_id(zone_id)
    if not zone:
        return ""
    return f"<script async src='https://libtl.com/sdk.js' data-zone='{zone}' data-sdk='show_{zone}'></script>"


def _build_monetag_scripts(settings) -> str:
    scripts = []

    interstitial_script = (settings.get("interstitial_script") or "").strip()
    interstitial_zone = (settings.get("interstitial_zone_id") or "").strip()
    if settings.get("interstitial_enabled"):
        if interstitial_zone:
            scripts.append(_script_for_zone(interstitial_zone))
        elif interstitial_script:
            scripts.append(interstitial_script)

    rewarded_script = (settings.get("rewarded_script") or "").strip()
    rewarded_zone = (settings.get("rewarded_zone_id") or "").strip()
    if settings.get("rewarded_enabled"):
        if rewarded_zone:
            scripts.append(_script_for_zone(rewarded_zone))
        elif rewarded_script:
            scripts.append(rewarded_script)

    return "\n".join(s for s in scripts if s)


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
        await complete_step(token, "rewarded")
        raise web.HTTPFound(_tg_open_link(f"/complete/{token}"))

    ad_ready_in = _seconds_until(data.get("ad_available_at", datetime.utcnow()))
    progress = int((len(data.get("completed_steps", [])) / max(1, len(required))) * 100)
    smartlink = settings.get("smartlink_url", "")
    monetag_scripts = _build_monetag_scripts(settings)
    interstitial_zone = _sanitize_zone_id(settings.get("interstitial_zone_id", ""))
    rewarded_zone = _sanitize_zone_id(settings.get("rewarded_zone_id", ""))

    html = f"""
    <!doctype html>
    <html lang='en'>
    <head>
      <meta charset='utf-8' />
      <meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover' />
      <meta name='theme-color' content='#0f172a' />
      <title>Uchiha Developer | Verification</title>
      <script src='https://telegram.org/js/telegram-web-app.js'></script>
      {monetag_scripts}
      <style>
        * {{ box-sizing: border-box; }}
        body {{ margin:0; min-height:100vh; display:grid; place-items:center; padding:20px; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:#e2e8f0; background: radial-gradient(circle at top, #1e293b 0%, #020617 65%); }}
        .card {{ width:min(500px,100%); border-radius:20px; padding:22px; background:rgba(15,23,42,.85); border:1px solid rgba(148,163,184,.2); box-shadow:0 20px 48px rgba(2,6,23,.5); }}
        h1 {{ margin:0 0 8px; font-size:24px; }}
        .sub {{ margin:0 0 16px; color:#94a3b8; }}
        .progress {{ height:10px; border-radius:999px; background:#334155; overflow:hidden; margin-bottom:14px; }}
        .bar {{ height:100%; width:{progress}%; background:linear-gradient(90deg,#22d3ee,#6366f1); transition:width .35s ease; }}
        .steps {{ color:#cbd5e1; margin:0 0 14px; padding-left:18px; line-height:1.6; }}
        .btn {{ width:100%; border:0; border-radius:14px; padding:14px; font-weight:700; color:#fff; background:linear-gradient(90deg,#06b6d4,#4f46e5); cursor:pointer; }}
        .btn[disabled] {{ opacity:.6; cursor:not-allowed; }}
        .status {{ margin-top:12px; font-size:14px; color:#93c5fd; min-height:20px; }}
        .retry {{ display:none; margin-top:10px; color:#22d3ee; cursor:pointer; text-align:center; }}
      </style>
    </head>
    <body>
      <div class='card'>
        <h1>Uchiha Developer</h1>
        <p class='sub'>Complete Monetag verification to unlock your file.</p>
        <div class='progress'><div id='bar' class='bar'></div></div>
        <ol class='steps'>
          <li>Load interstitial/rewarded ad</li>
          <li>Open SmartLink verification</li>
          <li>Return and unlock in bot</li>
        </ol>
        <button class='btn' id='watchBtn' disabled>Preparing... <span id='count'>{ad_ready_in}</span>s</button>
        <div class='status' id='status'>Waiting for cooldown...</div>
        <div id='retry' class='retry'>Retry verification</div>
      </div>

      <script>
        (function() {{
          const token = {token!r};
          const requiredSteps = {required!r};
          const smartlink = {smartlink!r};
          const monetagConfig = {{
            interstitialZoneId: {interstitial_zone!r},
            rewardedZoneId: {rewarded_zone!r}
          }};

          const watchBtn = document.getElementById('watchBtn');
          const count = document.getElementById('count');
          const status = document.getElementById('status');
          const retry = document.getElementById('retry');
          const bar = document.getElementById('bar');

          if (window.Telegram && Telegram.WebApp) {{
            Telegram.WebApp.ready();
            Telegram.WebApp.expand();
          }}

          let adStarted = false;
          let remaining = {ad_ready_in};
          const timer = setInterval(() => {{
            if (remaining <= 0) {{
              clearInterval(timer);
              watchBtn.disabled = false;
              watchBtn.textContent = 'Start Verification';
              status.textContent = 'Ready.';
              return;
            }}
            remaining -= 1;
            if (count) count.textContent = remaining;
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
            if (!res.ok) throw new Error('Request failed: ' + res.status);
            return await res.json();
          }}

          function sleep(ms) {{
            return new Promise(resolve => setTimeout(resolve, ms));
          }}

          function getMonetagFunctions() {{
            const preferred = [];
            if (requiredSteps.includes('interstitial') && monetagConfig.interstitialZoneId) {{
              preferred.push('show_' + monetagConfig.interstitialZoneId);
            }}
            if (requiredSteps.includes('rewarded') && monetagConfig.rewardedZoneId) {{
              preferred.push('show_' + monetagConfig.rewardedZoneId);
            }}

            const allFns = Object.keys(window)
              .filter(k => k.startsWith('show_') && typeof window[k] === 'function');
            return [...new Set([...preferred, ...allFns])];
          }}

          async function waitForMonetagReady() {{
            const maxTries = 25;
            for (let i = 0; i < maxTries; i += 1) {{
              const fns = getMonetagFunctions();
              if (fns.length > 0) return fns;
              await sleep(200);
            }}
            return [];
          }}

          async function showMonetag() {{
            const fns = await waitForMonetagReady();
            if (!fns.length) return false;

            for (const fnName of fns) {{
              if (typeof window[fnName] !== 'function') continue;
              try {{
                const result = await Promise.resolve(window[fnName]());
                if (result !== false) return true;
              }} catch (_) {{}}
            }}
            return false;
          }}

          async function openSmartLink() {{
            if (!smartlink || !requiredSteps.includes('smartlink')) return true;
            status.textContent = 'Opening SmartLink...';
            const tg = (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null;
            if (tg && typeof tg.openLink === 'function') {{
              tg.openLink(smartlink, {{ try_instant_view: false }});
            }} else {{
              window.open(smartlink, '_blank', 'noopener,noreferrer');
            }}
            await sleep(2500);
            return true;
          }}

          async function startFlow() {{
            if (adStarted) return;
            adStarted = true;
            watchBtn.disabled = true;
            retry.style.display = 'none';
            setProgress(20);
            status.textContent = 'Starting verification...';

            try {{
              const tg = (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null;
              await callApi('/api/verification/' + token + '/start-ad', {{
                tg_init_data: tg ? tg.initData : '',
                tg_user_id: tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : null
              }});

              let adOk = true;
              if (requiredSteps.includes('interstitial') || requiredSteps.includes('rewarded')) {{
                status.textContent = 'Loading ad...';
                setProgress(50);
                adOk = await showMonetag();
              }}

              if (!adOk) throw new Error('Ad not completed');
              await openSmartLink();

              setProgress(80);
              status.textContent = 'Finalizing...';
              await callApi('/api/verification/' + token + '/complete-ad', {{ ad_completed: true }});
              setProgress(100);
              window.location.href = '/complete/' + token;
            }} catch (_) {{
              status.textContent = 'Ad failed to load. Tap retry to try verification again.';
              retry.style.display = 'block';
              watchBtn.disabled = false;
              watchBtn.textContent = 'Start Verification';
              adStarted = false;
            }}
          }}

          retry.onclick = startFlow;
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

    required = data.get("required_steps", [])
    if "smartlink" in required:
        await complete_step(token, "smartlink")
    if "interstitial" in required:
        await complete_step(token, "interstitial")
    if "rewarded" in required:
        await complete_step(token, "rewarded")

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
    <html><body style='font-family:sans-serif;padding:20px;background:#020617;color:#e2e8f0'>
    <h3>Verification complete</h3>
    <p>Returning you to the bot now...</p>
    <a href='{deep_link}'>Return to bot and unlock file</a>
    <script>
    if (window.Telegram && Telegram.WebApp && Telegram.WebApp.openTelegramLink) {{
      Telegram.WebApp.openTelegramLink({deep_link!r});
    }} else {{
      setTimeout(function(){{window.location.href={deep_link!r};}}, 1200);
    }}
    </script>
    </body></html>
    """
    return web.Response(text=html, content_type="text/html")
