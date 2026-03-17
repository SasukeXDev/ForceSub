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


def _script_for_zone(zone_id: str) -> str:
    zone = "".join(ch for ch in str(zone_id or "") if ch.isdigit())
    if not zone:
        return ""
    # ✅ FIX: force https
    return f"<script src='https://libtl.com/sdk.js' data-zone='{zone}' data-sdk='show_{zone}'></script>"


def _build_monetag_scripts(settings) -> str:
    scripts = []

    if settings.get("interstitial_enabled"):
        zone = (settings.get("interstitial_zone_id") or "").strip()
        if zone:
            scripts.append(_script_for_zone(zone))

    if settings.get("rewarded_enabled"):
        zone = (settings.get("rewarded_zone_id") or "").strip()
        if zone:
            scripts.append(_script_for_zone(zone))

    return "\n".join(scripts)


async def verification_page(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await register_page_visit(token)

    if not data:
        return web.Response(text="Invalid token", status=400)

    settings = await get_ad_settings()
    required = data.get("required_steps", [])

    if not required or not settings.get("ads_enabled"):
        await complete_step(token, "smartlink")
        await complete_step(token, "interstitial")
        await complete_step(token, "rewarded")
        raise web.HTTPFound(_tg_open_link(f"/complete/{token}"))

    ad_ready_in = _seconds_until(data.get("ad_available_at", datetime.utcnow()))
    smartlink = settings.get("smartlink_url", "")
    monetag_scripts = _build_monetag_scripts(settings)

    html = f"""
    <!doctype html>
    <html>
    <head>
      <meta name='viewport' content='width=device-width'>
      <script src='https://telegram.org/js/telegram-web-app.js'></script>
      {monetag_scripts}
    </head>
    <body style="background:#020617;color:white;text-align:center;padding:20px;font-family:sans-serif;">

      <h2>Verification Required</h2>
      <button id="btn" disabled>Loading... {ad_ready_in}s</button>
      <p id="status">Please wait...</p>

      <script>
      const token = "{token}";
      const smartlink = "{smartlink}";
      let remaining = {ad_ready_in};
      let started = false;

      const btn = document.getElementById("btn");
      const status = document.getElementById("status");

      // ✅ wait for SDK
      function waitForSdk() {{
        return new Promise((resolve, reject) => {{
          let t = 0;
          const i = setInterval(() => {{
            const fn = Object.keys(window).find(k => k.startsWith("show_"));
            if (fn && typeof window[fn] === "function") {{
              clearInterval(i);
              resolve(window[fn]);
            }}
            t += 100;
            if (t > 5000) {{
              clearInterval(i);
              reject("SDK timeout");
            }}
          }}, 100);
        }});
      }}

      // countdown
      const timer = setInterval(() => {{
        if (remaining <= 0) {{
          clearInterval(timer);
          btn.disabled = false;
          btn.innerText = "Start Verification";
          status.innerText = "Ready";
        }} else {{
          remaining--;
          btn.innerText = "Loading... " + remaining + "s";
        }}
      }}, 1000);

      async function start() {{
        if (started) return;
        started = true;

        btn.disabled = true;
        status.innerText = "Loading ad...";

        try {{
          const showAd = await waitForSdk();

          // ✅ CORRECT Monetag call
          await showAd({{
            type: "inApp",
            inAppSettings: {{
              frequency: 2,
              capping: 0.1,
              interval: 30,
              timeout: 5,
              everyPage: false
            }}
          }});

          status.innerText = "Opening link...";

          if (smartlink) {{
            if (window.Telegram && Telegram.WebApp) {{
              Telegram.WebApp.openLink(smartlink);
            }} else {{
              window.location.href = smartlink;
            }}
          }}

          await new Promise(r => setTimeout(r, 2500));

          await fetch("/api/verification/" + token + "/complete-ad", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ ad_completed: true }})
          }});

          window.location.href = "/complete/" + token;

        }} catch (e) {{
          console.log(e);
          status.innerText = "Ad failed. Retrying...";
          btn.disabled = false;
          started = false;
        }}
      }}

      btn.onclick = start;
      </script>
    </body>
    </html>
    """

    return web.Response(text=html, content_type="text/html")


# ---------------- API ----------------

async def start_ad(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await can_start_ad_attempt(token)

    if not data:
        return web.json_response({"ok": False}, status=400)

    if _seconds_until(data.get("ad_available_at", datetime.utcnow())) > 0:
        return web.json_response({"ok": False, "cooldown": True}, status=429)

    return web.json_response({"ok": True})


async def complete_ad(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    data = await get_token_or_none(token)

    if not data:
        return web.json_response({"ok": False}, status=400)

    await complete_step(token, "interstitial")
    await complete_step(token, "rewarded")
    await complete_step(token, "smartlink")

    return web.json_response({"ok": True})


async def complete(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    deep_link = f"https://t.me/{request.app['bot_username']}?start=unlock_{token}"

    return web.Response(text=f"""
    <html>
    <body style="background:#000;color:#fff;text-align:center;padding:20px;">
    <h3>Done ✅</h3>
    <script>
    setTimeout(()=>window.location.href="{deep_link}",1000);
    </script>
    </body>
    </html>
    """, content_type="text/html")
