#!/usr/bin/env python3
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

COOKIE = Path("/tmp/session_cookie.txt").read_text().strip()
URL = (
    "https://shivatrade.store/mc325/charts?strike=0&ce=0&pe=0&expiry=&index=NIFTY"
    "&slot=10%3A55&day=2026-10-17&minutes=3&latest=1"
)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_cookies(
            [{"name": "shivtrade_auth_session", "value": COOKIE, "url": "https://shivatrade.store"}]
        )
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        for _ in range(35):
            if page.evaluate("() => document.documentElement.dataset.kiteClean === '1'"):
                break
            time.sleep(1)
        info = page.evaluate(
            """() => {
  const card = document.querySelector('#kiteCall .order-card');
  const sel = document.querySelector('#kiteCall .kiteOrderType');
  const limit = document.querySelector('#kiteCall .kiteLimit');
  return {
    card: !!card,
    trailToggle: !!card?.querySelector('.manual-trail-toggle'),
    trailBar: !!card?.querySelector('.manual-trail-bar'),
    trailBarHidden: card?.querySelector('.manual-trail-bar')?.hidden,
    mtmDialog: !!document.querySelector('dialog.mtm-dialog'),
    portfolioMtm: !!document.querySelector('button.portfolio-mtm-button'),
    selTag: sel?.tagName,
    selValue: sel?.value,
    selText: sel?.selectedOptions?.[0]?.text,
    selDisplay: sel ? getComputedStyle(sel).display : null,
    selWidth: sel?.offsetWidth,
    limitHTML: limit?.innerHTML?.slice(0, 200),
    manualJs: [...document.scripts].find(s => s.src.includes('manual.js'))?.src,
  };
}"""
        )
        print(info)
        page.locator("#kiteCall .kiteRow2 .manual-trail-toggle").first.click()
        time.sleep(0.8)
        pop = page.evaluate(
            """() => ({
  pop: !!document.getElementById('kiteSettingsPop'),
  popHidden: document.getElementById('kiteSettingsPop')?.hidden,
  openBar: !!document.querySelector('#kiteSettingsPop .manual-trail-bar'),
  openBarDisplay: document.querySelector('#kiteSettingsPop .manual-trail-bar')?.getBoundingClientRect?.().width,
})"""
        )
        print("after trail click", pop)
        browser.close()


if __name__ == "__main__":
    main()
