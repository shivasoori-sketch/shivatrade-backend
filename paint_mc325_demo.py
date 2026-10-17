#!/usr/bin/env python3
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

COOKIE = Path("/tmp/session_cookie.txt").read_text().strip()
URL = (
    "https://shivatrade.store/mc325/charts?strike=0&ce=0&pe=0&expiry=&index=NIFTY"
    "&slot=10%3A55&day=2026-10-17&minutes=3&latest=1"
)
OUT = Path(
    "/cursor/stores/bc-5d598de7-bb90-4609-bc39-96ce86cc74ff/media/mc325-painted.png"
)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-cache"]
        )
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_cookies(
            [{"name": "shivtrade_auth_session", "value": COOKIE, "url": "https://shivatrade.store"}]
        )

        def no_cache(route):
            h = dict(route.request.headers)
            h["Cache-Control"] = "no-cache"
            route.continue_(headers=h)

        ctx.route("**/*", no_cache)
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        for _ in range(40):
            ok = page.evaluate(
                """() => document.documentElement.dataset.kiteClean === '1'
                && !!document.getElementById('kiteClean')"""
            )
            if ok:
                break
            time.sleep(1)
        page.evaluate("() => { if (typeof fitKiteCharts === 'function') fitKiteCharts(); }")
        time.sleep(2)
        page.evaluate("() => { if (typeof fitKiteCharts === 'function') fitKiteCharts(); }")
        time.sleep(1)
        page.screenshot(path=str(OUT), full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
