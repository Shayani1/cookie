# qx_cookie_refresher.py – updated with automatic Playwright browser install
"""
FastAPI micro‑service that logs into https://market-qx.pro/ via headless
Chromium (Playwright). It refreshes session cookies every REFRESH_MINS
(default 30) and exposes them at /get-cookies for Bubble/Create.
Now includes an automatic `playwright install --with-deps` step on startup
so Railway / Nixpacks deployments work without manual commands.
Environment variables required:
  QX_EMAIL      – Quotex login email
  QX_PASSWORD   – Quotex password
  REFRESH_MINS  – optional refresh interval (integer, default 30)
"""
from __future__ import annotations
import os, json, time, subprocess, sys
from datetime import datetime, timedelta
from threading import Thread
from typing import Dict, Any, List

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# --- Ensure Playwright Browsers Installed ----------------------------------
# This runs only once at startup; safe in Railway read‑only FS.
try:
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps"], check=True)
except Exception as e:
    print("[Playwright] install failed or already done:", e)

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout  # noqa: E402

EMAIL       = os.getenv("QX_EMAIL")
PASSWORD    = os.getenv("QX_PASSWORD")
REFRESH_MIN = int(os.getenv("REFRESH_MINS", "30"))

if not EMAIL or not PASSWORD:
    raise RuntimeError("QX_EMAIL and QX_PASSWORD environment variables are required")

cookie_store: Dict[str, Any] = {
    "cookies": [],
    "headers": {},
    "expires_at": datetime.utcnow(),
}

# ---------------------------------------------------------------------------
# Playwright login & extraction
# ---------------------------------------------------------------------------

def login_and_extract() -> None:
    """Headless login to Quotex, refresh global cookie_store."""
    global cookie_store
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("https://market-qx.pro/", timeout=60000)
            # Click login button if present
            if page.locator('text="Log in"').count():
                page.locator('text="Log in"').first.click()
            page.fill('input[type="email"]', EMAIL)
            page.fill('input[type="password"]', PASSWORD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(7000)

            cookies = page.context.cookies()
            ls = page.evaluate("() => JSON.stringify(localStorage)")
            ss = page.evaluate("() => JSON.stringify(sessionStorage)")
            headers = {
                "localStorage": json.loads(ls),
                "sessionStorage": json.loads(ss),
            }

            cookie_store = {
                "cookies": cookies,
                "headers": headers,
                "expires_at": datetime.utcnow() + timedelta(minutes=REFRESH_MIN),
            }
            print(f"[CookieRefresher] Refreshed at {datetime.utcnow().isoformat()} UTC")
        except PwTimeout:
            print("[CookieRefresher] Timeout during login; cookies not updated")
        except Exception as e:
            print(f"[CookieRefresher] Unexpected error: {e}")
        finally:
            browser.close()

# ---------------------------------------------------------------------------
# Background refresher thread
# ---------------------------------------------------------------------------

def refresher_loop():
    while True:
        login_and_extract()
        time.sleep(REFRESH_MIN * 60)

Thread(target=refresher_loop, daemon=True).start()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Quotex Cookie Refresher", version="1.1.0")

@app.get("/get-cookies", tags=["session"])
def get_cookies():
    """Return latest cookies + headers bundle."""
    return JSONResponse(cookie_store)

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("qx_cookie_refresher:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
