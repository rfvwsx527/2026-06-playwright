import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright

WORKSPACE = Path(r"C:\Users\user\Desktop\2026-06-playwright\outputs\bot-exchange-rate")
SCREENSHOTS = WORKSPACE / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

async def main():
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await context.new_page()

        await page.goto("https://rate.bot.com.tw/xrt?Lang=zh-TW", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(SCREENSHOTS / "explore_1_start.png"))

        print("URL:", page.url)
        title = await page.title()
        print("TITLE:", title)

        snapshot = await page.locator("body").aria_snapshot()
        (SCREENSHOTS / "explore_aria.txt").write_text(snapshot[:10000], encoding="utf-8")
        print("ARIA snapshot written to explore_aria.txt")

        text = await page.locator("body").inner_text()
        (SCREENSHOTS / "explore_text.txt").write_text(text[:10000], encoding="utf-8")
        print("Body text written to explore_text.txt")

        await browser.close()

asyncio.run(main())
