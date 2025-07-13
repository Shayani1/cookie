# main.py – Quotex Cookie Refresher with Logging & Screenshot
from __future__ import annotations
import os, json, time, subprocess, sys
from datetime import datetime, timedelta
from threading import Thread
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# --- Ensure Playwright Browsers Installed Automatically --------------------
try:
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps"], check=True)
except Exception as e:
    print("[Playwright] install failed or already done:", e)

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

# --- ENV Setup -------------------------------------------------------------
EMAIL       = os.getenv("QX_EMAIL")
PASSWORD    = os.getenv("QX_PASSWORD")
REFRESH_MIN = int(os.getenv("REFRESH_MINS", "30"))

if not EMAIL or not PASSWORD:
    raise RuntimeError("QX_EMAIL and QX_PASSWORD environment variables are required")

# --- Session Store ---------------------------------------------------------
cookie_store: Dict[str, Any] = {
    "cookies": [],
    "headers": {},
    "expires_at": datetime.utcnow(),
}

# --- Logging Helper --------------------------------------------------------
def log(message: str):
    timestamp = datetime.utcnow().isoformat()
    entry = f"[{timestamp} UTC] {message}"
    print(entry)
    with open("cookie_log.txt", "a") as f:
        f.write(entry + "\n")

# --- Login + Extract Cookies -----------------------------------------------
def login_and_extract() -> None:
    """Headless login to Quotex, refresh global cookie_store."""
    global cookie_store
    log("Attempting login and cookie refresh...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("https://market-qx.pro/", timeout=60000)
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

            log("✅ Cookie refresh complete.")
        except PwTimeout:
            log("⚠️ Timeout during login. Capturing screenshot...")
            page.screenshot(path="login_error.png")
        except Exception as e:
            log(f"❌ Unexpected error: {e}")
            try:
                page.screenshot(path="login_error.png")
            except Exception:
                log("⚠️ Screenshot failed.")
        finally:
            browser.close()

# --- Background Thread for Refreshing -------------------------------------
def refresher_loop():
    while True:
        login_and_extract()
        time.sleep(REFRESH_MIN * 60)

Thread(target=refresher_loop, daemon=True).start()

# --- FastAPI App Setup -----------------------------------------------------
app = FastAPI(title="Quotex Cookie Refresher", version="1.2.0")

@app.get("/get-cookies", tags=["session"])
def get_cookies():
    """Return latest cookies + headers bundle."""
    return JSONResponse(cookie_store)

# --- Run Local Dev ---------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
