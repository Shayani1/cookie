"""
Quotex Cookie Refresher API
---------------------------------
Logs into https://market-qx.pro/ via headless Playwright Chromium,
extracts cookies + local/sessionStorage tokens, refreshes them every
REFRESH_MINS (default 30) and serves the latest bundle at /get-cookies.
Environment variables required:
  QX_EMAIL      – login email
  QX_PASSWORD   – login password
  REFRESH_MINS  – optional, default 30
Deploy on Railway with:
  web: uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
"""
from __future__ import annotations
import os, json, time
from datetime import datetime, timedelta
from threading import Thread
from typing import Dict, Any, List

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

EMAIL      = os.getenv("QX_EMAIL")
PASSWORD   = os.getenv("QX_PASSWORD")
REFRESH_MIN = int(os.getenv("REFRESH_MINS", "30"))

if not EMAIL or not PASSWORD:
    raise RuntimeError("QX_EMAIL and QX_PASSWORD must be set as env vars")

cookie_store: Dict[str, Any] = {
    "cookies": [],
    "headers": {},
    "expires_at": datetime.utcnow()
}

def login_and_extract() -> None:
    """Perform headless login, update cookie_store in place."""
    global cookie_store
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("https://market-qx.pro/", timeout=60000)
            # Click login button if needed
            if page.locator('text="Log in"').count():
                page.click('text="Log in"')
            page.fill('input[type="email"]', EMAIL)
            page.fill('input[type="password"]', PASSWORD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(7000)  # wait for redirect/session

            cookies = page.context.cookies()
            # grab storage items
            ls = page.evaluate("() => JSON.stringify(localStorage)")
            ss = page.evaluate("() => JSON.stringify(sessionStorage)")
            headers = {"localStorage": json.loads(ls), "sessionStorage": json.loads(ss)}

            cookie_store = {
                "cookies": cookies,
                "headers": headers,
                "expires_at": datetime.utcnow() + timedelta(minutes=REFRESH_MIN)
            }
            print(f"[REFRESH] Cookies refreshed at {datetime.utcnow().isoformat()} UTC")
        except PwTimeout:
            print("[ERROR] Timeout during login")
        except Exception as e:
            print(f"[ERROR] {e}")
        finally:
            browser.close()

def refresher_loop():
    while True:
        login_and_extract()
        time.sleep(REFRESH_MIN * 60)

# start background thread
Thread(target=refresher_loop, daemon=True).start()

app = FastAPI(title="Quotex Cookie Refresher", version="1.0.0")

@app.get("/get-cookies", tags=["session"])
def get_cookies():
    """Return the latest cookies + headers bundle."""
    return JSONResponse(cookie_store)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
