from datetime import datetime, timedelta
import secrets

from aiohttp import web

from config import WEB_BASE_URL
from database.ads_database import get_ad_settings, update_verification_token
from verification_system import complete_step, get_token_or_none


COOLDOWN_SECONDS = 15
MAX_REFRESH_COUNT = 4


def _tg_open_link(path: str) -> str:
    if WEB_BASE_URL:
        return f"{WEB_BASE_URL}{path}"
    return path


def _utc_now() -> datetime:
    return datetime.utcnow()


def _to_iso(dt: datetime) -> str:
    return dt.isoformat() + "Z"


async def verification_page(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await get_token_or_none(token)
    if not data:
        return web.Response(text="Verification token invalid or expired.", status=400)

    settings = await get_ad_settings()
    required = data.get("required_steps", [])
    if not required or not settings.get("ads_enabled"):
        await complete_step(token, "smartlink")
        await complete_step(token, "interstitial")
        raise web.HTTPFound(_tg_open_link(f"/complete/{token}"))

    now = _utc_now()
    refresh_count = int(data.get("refresh_count", 0)) + 1
    if refresh_count > MAX_REFRESH_COUNT:
        await update_verification_token(token, {"blocked": True, "refresh_count": refresh_count})
        return web.Response(text="Verification blocked due to repeated refreshes. Open a new link from bot.", status=429)

    session_nonce = secrets.token_urlsafe(16)
    cooldown_until = now + timedelta(seconds=COOLDOWN_SECONDS)

    await update_verification_token(
        token,
        {
            "refresh_count": refresh_count,
            "session_nonce": session_nonce,
            "session_started_at": now,
            "cooldown_until": cooldown_until,
        },
    )

    zone_id = "10739699"
    smartlink_url = settings.get("smartlink_url", "").strip()
    required_js = ",".join([f'"{step}"' for step in required])
    completed_js = ",".join([f'"{step}"' for step in data.get("completed_steps", [])])
    deep_link = f"https://t.me/{request.app['bot_username']}?start=unlock_{token}"

    html = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
  <title>File Verification Required</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <script src='//libtl.com/sdk.js' data-zone='{zone_id}' data-sdk='show_{zone_id}'></script>
  <style>
    :root {{
      --bg-a: #eef2ff;
      --bg-b: #dbeafe;
      --card: rgba(255,255,255,.78);
      --text: #0f172a;
      --muted: #64748b;
      --primary: #2563eb;
      --ok: #16a34a;
      --danger: #dc2626;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg-a: #020617;
        --bg-b: #0f172a;
        --card: rgba(15,23,42,.82);
        --text: #e2e8f0;
        --muted: #94a3b8;
        --primary: #60a5fa;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: linear-gradient(155deg, var(--bg-a), var(--bg-b));
      color: var(--text);
      display: grid;
      place-items: center;
      padding: 20px;
    }}
    .card {{
      width: min(450px, 100%);
      border-radius: 20px;
      background: var(--card);
      box-shadow: 0 20px 45px rgba(0,0,0,.16);
      padding: 22px;
      backdrop-filter: blur(10px);
      animation: rise .35s ease;
    }}
    @keyframes rise {{ from {{ transform: translateY(10px); opacity: 0; }} to {{ transform: none; opacity: 1; }} }}
    h1 {{ margin: 0; font-size: 1.28rem; }}
    .sub {{ margin: 8px 0 20px; color: var(--muted); font-size: .94rem; }}
    .progress-wrap {{ height: 10px; border-radius: 99px; background: rgba(148,163,184,.26); overflow: hidden; }}
    .progress {{ height: 100%; width: 4%; border-radius: inherit; background: linear-gradient(90deg, #3b82f6, #22d3ee); transition: width .55s ease; }}
    .steps {{ margin: 16px 0; padding: 0; list-style: none; display: grid; gap: 8px; }}
    .steps li {{
      border-radius: 10px;
      padding: 10px;
      background: rgba(148,163,184,.12);
      font-size: .9rem;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      transition: all .28s ease;
    }}
    .steps li.done {{ color: var(--ok); background: rgba(22,163,74,.14); }}
    .steps li.active {{ color: var(--primary); background: rgba(37,99,235,.15); }}
    .btn {{
      width: 100%;
      border: none;
      border-radius: 12px;
      padding: 13px;
      color: #fff;
      background: linear-gradient(135deg, #2563eb, #3b82f6);
      font-weight: 700;
      margin-top: 10px;
      cursor: pointer;
      transform: translateY(0);
      transition: transform .16s ease, filter .16s ease, opacity .2s ease;
    }}
    .btn:active {{ transform: translateY(1px) scale(.995); }}
    .btn:hover {{ filter: brightness(1.05); }}
    .btn:disabled {{ opacity: .5; cursor: not-allowed; }}
    .state {{ min-height: 22px; margin-top: 10px; font-size: .92rem; color: var(--muted); }}
    .badge {{ margin-top: 12px; font-size: .8rem; color: var(--muted); text-align: center; }}
    .footer {{ margin-top: 18px; text-align: center; font-size: .78rem; color: var(--muted); }}
    .retry {{
      margin-top: 8px;
      display: none;
      border: 1px solid rgba(148,163,184,.4);
      background: transparent;
      color: var(--text);
      padding: 8px 12px;
      border-radius: 10px;
      width: 100%;
    }}
  </style>
</head>
<body>
  <main class="card">
    <h1>File Verification Required</h1>
    <p class="sub">Complete a quick verification to unlock your file.</p>

    <section>
      <div class="progress-wrap"><div id="progress" class="progress"></div></div>
      <ul class="steps" id="stepsList">
        <li data-step="init">Step 1: Initialize verification <span>⏳</span></li>
        <li data-step="ad">Step 2: Load ad <span>⏳</span></li>
        <li data-step="complete">Step 3: Complete verification <span>⏳</span></li>
        <li data-step="redirect">Step 4: Redirect to bot <span>⏳</span></li>
      </ul>
      <button id="watchBtn" class="btn" disabled>Preparing verification… {COOLDOWN_SECONDS}s</button>
      <button id="retryBtn" class="retry">Retry verification</button>
      <div id="state" class="state">Initializing secure checks…</div>
      <div class="badge">Protected by secure verification</div>
    </section>

    <div class="footer">This helps us keep the bot free.</div>
  </main>

<script>
(() => {{
  const token = {token!r};
  const nonce = {session_nonce!r};
  const cooldownUntil = {int(cooldown_until.timestamp() * 1000)};
  const requiredSteps = [{required_js}];
  const completedSteps = new Set([{completed_js}]);
  const smartlink = {smartlink_url!r};
  const deepLink = {deep_link!r};

  const tg = window.Telegram?.WebApp;
  if (tg) {{ tg.ready(); tg.expand(); }}

  const stateEl = document.getElementById('state');
  const btn = document.getElementById('watchBtn');
  const retry = document.getElementById('retryBtn');
  const progress = document.getElementById('progress');
  const steps = [...document.querySelectorAll('#stepsList li')];

  const setState = (txt, isErr = false) => {{
    stateEl.textContent = txt;
    stateEl.style.color = isErr ? 'var(--danger)' : 'var(--muted)';
  }};

  const mark = (id, kind) => {{
    const item = steps.find(s => s.dataset.step === id);
    if (!item) return;
    item.classList.remove('active', 'done');
    item.classList.add(kind);
    item.querySelector('span').textContent = kind === 'done' ? '✅' : '⏳';
  }};

  const setProgress = (n) => progress.style.width = `${{Math.max(4, Math.min(n, 100))}}%`;

  const post = async (path, body = {{}}) => {{
    const res = await fetch(path, {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(body)
    }});
    const data = await res.json().catch(() => ({{ ok: false, error: 'Unexpected response' }}));
    if (!res.ok || !data.ok) throw new Error(data.error || 'Verification failed');
    return data;
  }};

  const withTimeout = (p, ms = 12000) => Promise.race([
    p,
    new Promise((_, rej) => setTimeout(() => rej(new Error('Network timeout')), ms))
  ]);

  const adCall = async () => {{
    if (typeof window.show_10739699 === 'function') {{
      await window.show_10739699();
      return true;
    }}
    if (smartlink) {{
      window.open(smartlink, '_blank', 'noopener,noreferrer');
      await new Promise(r => setTimeout(r, 1800));
      return true;
    }}
    throw new Error('Ad failed to load. Please retry.');
  }};

  let cooldownTick;
  const tickCooldown = () => {{
    const left = Math.ceil((cooldownUntil - Date.now()) / 1000);
    if (left > 0) {{
      btn.disabled = true;
      btn.textContent = `Preparing verification… ${{left}}s`;
      return;
    }}
    clearInterval(cooldownTick);
    btn.disabled = false;
    btn.textContent = 'Watch Ad';
    setState('Verification ready. Tap Watch Ad to continue.');
  }};

  const run = async () => {{
    try {{
      mark('init', 'active');
      setProgress(15);
      await withTimeout(post(`/api/verify/${{token}}/init`, {{
        nonce,
        tg_user_id: tg?.initDataUnsafe?.user?.id || null,
      }}));
      mark('init', 'done');
      setProgress(35);

      cooldownTick = setInterval(tickCooldown, 350);
      tickCooldown();

      btn.addEventListener('click', async () => {{
        btn.disabled = true;
        retry.style.display = 'none';
        mark('ad', 'active');
        setState('Loading Monetag ad…');
        setProgress(55);
        try {{
          await withTimeout(adCall(), 20000);
          mark('ad', 'done');
          mark('complete', 'active');
          setState('Finishing verification…');
          setProgress(75);

          await withTimeout(post(`/api/verify/${{token}}/complete`, {{
            nonce,
            tg_user_id: tg?.initDataUnsafe?.user?.id || null,
          }}));

          mark('complete', 'done');
          mark('redirect', 'active');
          setProgress(92);
          setState('Verification complete. Redirecting to bot…');
          localStorage.removeItem(`vfy:${{token}}`);
          setTimeout(() => {{
            mark('redirect', 'done');
            setProgress(100);
            if (tg?.openTelegramLink) tg.openTelegramLink(deepLink);
            else window.location.href = deepLink;
          }}, 800);
        }} catch (e) {{
          setState(e.message || 'Verification failed. Try again.', true);
          retry.style.display = 'block';
          btn.disabled = false;
          btn.textContent = 'Watch Ad';
        }}
      }}, {{ once: true }});

      retry.addEventListener('click', () => window.location.reload());
    }} catch (e) {{
      setState(e.message || 'Unable to initialize verification.', true);
      retry.style.display = 'block';
      btn.disabled = true;
    }}
  }};

  const refreshGuard = `vfy:${{token}}`;
  const previousOpen = Number(localStorage.getItem(refreshGuard) || '0');
  if (Date.now() - previousOpen < 2000) {{
    setState('Refresh detected. Please wait a second and try again.', true);
  }}
  localStorage.setItem(refreshGuard, String(Date.now()));

  if (completedSteps.size && requiredSteps.every(s => completedSteps.has(s))) {{
    mark('init', 'done'); mark('ad', 'done'); mark('complete', 'done'); mark('redirect', 'active');
    setProgress(95);
    setState('Already verified. Redirecting…');
    setTimeout(() => window.location.href = deepLink, 900);
    return;
  }}

  run();
}})();
</script>
</body>
</html>
"""

    return web.Response(text=html, content_type="text/html")


async def init_verification(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await get_token_or_none(token)
    if not data:
        return web.json_response({"ok": False, "error": "Token expired or invalid."}, status=400)
    if data.get("blocked"):
        return web.json_response({"ok": False, "error": "Verification blocked. Generate a new link."}, status=403)

    payload = await request.json()
    nonce = payload.get("nonce", "")
    tg_user_id = payload.get("tg_user_id")

    if not nonce or nonce != data.get("session_nonce"):
        return web.json_response({"ok": False, "error": "Session validation failed."}, status=403)

    if tg_user_id is not None and str(tg_user_id) != str(data.get("user_id")):
        return web.json_response({"ok": False, "error": "This verification link belongs to another user."}, status=403)

    if _utc_now() > data.get("expires_at"):
        return web.json_response({"ok": False, "error": "Token expired. Re-open bot link."}, status=400)

    await update_verification_token(token, {"verification_started": True})
    return web.json_response({"ok": True, "cooldown_seconds": COOLDOWN_SECONDS})


async def complete_verification(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await get_token_or_none(token)
    if not data:
        return web.json_response({"ok": False, "error": "Token expired or invalid."}, status=400)
    if data.get("used"):
        return web.json_response({"ok": False, "error": "Token already used."}, status=409)

    payload = await request.json()
    nonce = payload.get("nonce", "")
    tg_user_id = payload.get("tg_user_id")

    if nonce != data.get("session_nonce"):
        return web.json_response({"ok": False, "error": "Invalid verification session."}, status=403)

    if tg_user_id is not None and str(tg_user_id) != str(data.get("user_id")):
        return web.json_response({"ok": False, "error": "User mismatch."}, status=403)

    cooldown_until = data.get("cooldown_until")
    if cooldown_until and _utc_now() < cooldown_until:
        remaining = int((cooldown_until - _utc_now()).total_seconds()) + 1
        return web.json_response({"ok": False, "error": f"Please wait {remaining}s before verification."}, status=429)

    required = data.get("required_steps", [])
    if "interstitial" in required:
        await complete_step(token, "interstitial")
    if "smartlink" in required:
        await complete_step(token, "smartlink")

    await update_verification_token(token, {"verified_at": _utc_now()})
    return web.json_response({"ok": True})


async def smartlink_done(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await complete_step(token, "smartlink")
    if not data:
        return web.Response(text="Invalid token.", status=400)
    raise web.HTTPFound(_tg_open_link(f"/verify/{token}"))


async def interstitial_miniapp(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    raise web.HTTPFound(_tg_open_link(f"/verify/{token}"))


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
    <a href='{deep_link}'>Return to bot and unlock file</a>
    </body></html>
    """
    return web.Response(text=html, content_type="text/html")
