from datetime import datetime, timezone
import logging

from aiohttp import web

from config import WEB_BASE_URL
from database.ads_database import get_ad_settings
from verification_system import (
    can_start_ad_attempt,
    complete_step,
    get_next_required_step,
    get_token_or_none,
    register_page_visit,
)
from database.saas_database import record_ad_completion

LOGGER = logging.getLogger(__name__)


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
    interstitial_zone = "10739699"
    token_user_id = data.get("user_id")

    html = f"""
    <!doctype html>
    <html lang='en'>
    <head>
      <meta charset='utf-8' />
      <meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover' />
      <meta name='theme-color' content='#111827' />
      <title>File Verification Required</title>
      <script src='https://telegram.org/js/telegram-web-app.js'></script>
      <script src='https://libtl.com/sdk.js' data-zone='10739699' data-sdk='show_10739699'></script>
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
          <li>Step 1: Interstitial ad</li>
          <li>Step 2: Direct/SmartLink ad</li>
          <li>Unlock content</li>
        </ol>

        <button class='btn' id='interstitialBtn' disabled>Preparing Interstitial… <span id='count'>{ad_ready_in}</span>s</button>
        <button class='btn' id='smartlinkBtn' style='margin-top:10px;opacity:.65;' disabled>Step 2: Open SmartLink</button>
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
          const tokenUserId = {token_user_id!r};
          const adFnName = 'show_10739699';
          const interstitialBtn = document.getElementById('interstitialBtn');
          const smartlinkBtn = document.getElementById('smartlinkBtn');
          const count = document.getElementById('count');
          const status = document.getElementById('status');
          const retry = document.getElementById('retry');
          const bar = document.getElementById('bar');

          const tgWebApp = (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null;
          if (tgWebApp) {{ tgWebApp.ready(); tgWebApp.expand(); }}

          let remaining = {ad_ready_in};
          let flowLocked = false;
          let adPreloaded = false;

          function log(msg, data) {{
            if (data !== undefined) console.info('[verify]', msg, data);
            else console.info('[verify]', msg);
          }}
          function setError(code) {{ status.textContent = 'Error: ' + code; }}
          function setProgress(pct) {{ bar.style.width = Math.max(5, Math.min(100, pct)) + '%'; }}

          const timer = setInterval(() => {{
            if (remaining <= 0) {{
              clearInterval(timer);
              interstitialBtn.textContent = 'Watch Ad & Continue';
              if (adPreloaded) {{
                interstitialBtn.disabled = false;
                status.textContent = 'Step 1 ready.';
              }} else {{
                status.textContent = 'Preparing ad...';
              }}
              return;
            }}
            remaining -= 1;
            count.textContent = remaining;
          }}, 1000);

          async function api(url, payload) {{
            log('api', {{ url: url, payload: payload }});
            const res = await fetch(url, {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify(payload || {{}})
            }});
            const body = await res.json().catch(() => ({{ ok: false, error: 'invalid_json' }}));
            if (!res.ok || !body.ok) throw new Error((body && body.error) ? body.error : 'request_failed');
            return body;
          }}

          async function waitForSdk() {{
            const started = Date.now();
            while (Date.now() - started < 12000) {{
              if (typeof window[adFnName] === 'function') {{
                log('SDK Loaded');
                log('Ad Function Found');
                return;
              }}
              await new Promise(r => setTimeout(r, 250));
            }}
            log('Ad Failed', 'function_not_found');
            throw new Error('sdk_not_loaded');
          }}

          async function preloadAd() {{
            await waitForSdk();
            status.textContent = 'Loading ad unit...';
            try {{
              await window[adFnName]({{ type: 'preload', ymid: tokenUserId }});
              adPreloaded = true;
              log('Preload Success');
              if (remaining <= 0) {{
                interstitialBtn.disabled = false;
                status.textContent = 'Step 1 ready.';
              }}
            }} catch (_) {{
              log('Preload Failed');
              throw new Error('ad_failed');
            }}
          }}

          function openSmartLink() {{
            if (!smartlink) throw new Error('direct_link_missing');
            if (tgWebApp && typeof tgWebApp.openLink === 'function') {{
              tgWebApp.openLink(smartlink, {{ try_instant_view: false }});
            }} else {{
              window.open(smartlink, '_blank', 'noopener,noreferrer');
            }}
          }}

          async function runRewardedInterstitial() {{
            await waitForSdk();
            if (!adPreloaded) throw new Error('ad_failed');
            log('Ad Started');
            try {{
              await window[adFnName]({{ ymid: tokenUserId }});
              log('Ad Completed');
            }} catch (_) {{
              log('Ad Failed');
              throw new Error('ad_failed');
            }}
          }}

          async function handleStep(step) {{
            const payload = {{
              step: step,
              tg_init_data: tgWebApp ? tgWebApp.initData : '',
              tg_user_id: tgWebApp && tgWebApp.initDataUnsafe && tgWebApp.initDataUnsafe.user ? tgWebApp.initDataUnsafe.user.id : null
            }};
            await api('/api/verification/' + token + '/start-ad', payload);

            if (step === 'interstitial') {{
              status.textContent = 'Loading rewarded ad...';
              await runRewardedInterstitial();
            }} else {{
              status.textContent = 'Opening direct link...';
              openSmartLink();
              await new Promise(r => setTimeout(r, 2200));
            }}

            await api('/api/verification/' + token + '/complete-ad', {{ step: step, ad_completed: true }});
          }}

          function showRetry(step) {{
            retry.style.display = 'block';
            retry.onclick = () => {{
              retry.style.display = 'none';
              startFlow(step);
            }};
          }}

          async function startFlow(step) {{
            if (flowLocked) return;
            flowLocked = true;
            retry.style.display = 'none';
            interstitialBtn.disabled = true;
            smartlinkBtn.disabled = true;
            setProgress(step === 'interstitial' ? 25 : 70);

            try {{
              await handleStep(step);
              if (step === 'interstitial') {{
                setProgress(60);
                smartlinkBtn.disabled = false;
                smartlinkBtn.style.opacity = '1';
                status.textContent = 'Step 1 complete. Open direct link.';
              }} else {{
                setProgress(100);
                status.textContent = 'Verification complete. Redirecting...';
                window.location.href = '/complete/' + token;
              }}
            }} catch (e) {{
              const code = (e && e.message) ? e.message : 'ad_failed';
              setError(code);
              log('Error', code);
              interstitialBtn.disabled = false;
              if (step === 'smartlink') smartlinkBtn.disabled = false;
              if (step === 'interstitial' && smartlink) {{
                try {{ openSmartLink(); }} catch (_) {{}}
              }}
              showRetry(step);
            }} finally {{
              flowLocked = false;
            }}
          }}

          interstitialBtn.onclick = () => startFlow('interstitial');
          smartlinkBtn.onclick = () => startFlow('smartlink');
          setProgress(Math.min(20, requiredSteps.length ? 100 : 0));
          preloadAd().catch((e) => {{
            setError(e.message || 'ad_failed');
            showRetry('interstitial');
          }});
        }})();
      </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")


async def start_ad(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    payload = await request.json() if request.can_read_body else {}
    step = payload.get("step", "").strip().lower()
    if step not in {"interstitial", "smartlink"}:
        return web.json_response({"ok": False, "error": "invalid_step"}, status=400)

    LOGGER.info("start-ad token=%s step=%s", token, step)
    data = await can_start_ad_attempt(token)
    if not data:
        LOGGER.info("start-ad denied token=%s reason=token_invalid_or_blocked", token)
        return web.json_response({"ok": False, "error": "token_invalid_or_blocked"}, status=400)

    next_step = get_next_required_step(data)
    if next_step and step != next_step:
        LOGGER.info("start-ad denied token=%s reason=wrong_step expected=%s got=%s", token, next_step, step)
        return web.json_response({"ok": False, "error": f"step_order_invalid_expected_{next_step}"}, status=409)

    tg_user_id = payload.get("tg_user_id")
    token_user_id = data.get("user_id")
    if tg_user_id and token_user_id and int(tg_user_id) != int(token_user_id):
        LOGGER.info("start-ad denied token=%s reason=user_mismatch", token)
        return web.json_response({"ok": False, "error": "user_mismatch"}, status=403)

    if _seconds_until(data.get("ad_available_at", datetime.utcnow())) > 0:
        LOGGER.info("start-ad denied token=%s reason=cooldown", token)
        return web.json_response({"ok": False, "error": "cooldown_not_ready"}, status=429)

    LOGGER.info("start-ad ok token=%s step=%s attempts=%s", token, step, data.get("ad_attempts", 0))
    return web.json_response({"ok": True, "attempts": data.get("ad_attempts", 0), "step": step})


async def complete_ad(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await get_token_or_none(token)
    if not data:
        return web.json_response({"ok": False, "error": "token_invalid"}, status=400)

    payload = await request.json() if request.can_read_body else {}
    step = payload.get("step", "").strip().lower()
    if step not in {"interstitial", "smartlink"}:
        return web.json_response({"ok": False, "error": "invalid_step"}, status=400)
    if not payload.get("ad_completed"):
        return web.json_response({"ok": False, "error": "ad_incomplete"}, status=400)

    LOGGER.info("complete-ad token=%s step=%s", token, step)
    next_step = get_next_required_step(data)
    if next_step and step != next_step:
        LOGGER.info("complete-ad denied token=%s reason=wrong_step expected=%s got=%s", token, next_step, step)
        return web.json_response({"ok": False, "error": f"step_order_invalid_expected_{next_step}"}, status=409)

    required = data.get("required_steps", [])
    if step not in required:
        LOGGER.info("complete-ad denied token=%s reason=step_not_required step=%s", token, step)
        return web.json_response({"ok": False, "error": "step_not_required"}, status=400)

    updated = await complete_step(token, step)
    if not updated:
        LOGGER.info("complete-ad denied token=%s reason=complete_step_failed", token)
        return web.json_response({"ok": False, "error": "complete_step_failed"}, status=400)

    # Credit earnings strictly after ad completion success
    credited = 0.0
    owner_id = data.get("owner_id")
    bot_token = data.get("bot_token")
    if owner_id and bot_token:
        country = request.headers.get("CF-IPCountry", "IN")
        try:
            credited = await record_ad_completion(
                user_id=int(data.get("user_id")),
                token=str(bot_token),
                owner_id=int(owner_id),
                ad_type=step,
                country_code=country,
            )
            LOGGER.info(
                "earning-credited user_id=%s bot=%s ad_type=%s earning=%s",
                data.get("user_id"),
                str(bot_token)[-8:],
                step,
                credited,
            )
        except Exception as e:
            LOGGER.warning("earning-credit-failed token=%s err=%s", token, e)

    LOGGER.info("complete-ad ok token=%s step=%s", token, step)
    return web.json_response({"ok": True, "earning": credited})


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
