import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

WORKSPACE = Path(r"C:\Users\user\Desktop\2026-06-playwright\outputs\ptt-gossiping")
SCREENSHOTS = WORKSPACE / "screenshots"

async def main():
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await context.new_page()

        await page.goto("https://www.ptt.cc/bbs/Gossiping/index.html", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        confirm_btn = page.get_by_role("button", name="我同意")
        if await confirm_btn.count() > 0:
            await confirm_btn.click()
            await page.wait_for_timeout(2000)

        entries = page.locator(".r-ent")
        count = await entries.count()

        lines = [f"Total .r-ent entries: {count}"]
        for i in range(min(12, count)):
            entry = entries.nth(i)
            title_el = entry.locator(".title a")
            nrec_el = entry.locator(".nrec span")
            date_el = entry.locator(".date")
            author_el = entry.locator(".author")

            title = await title_el.inner_text() if await title_el.count() > 0 else "(no title / deleted)"
            nrec = await nrec_el.inner_text() if await nrec_el.count() > 0 else "0"
            date = await date_el.inner_text() if await date_el.count() > 0 else ""
            author = await author_el.inner_text() if await author_el.count() > 0 else ""

            nrec_class = ""
            if await nrec_el.count() > 0:
                nrec_class = await nrec_el.get_attribute("class") or ""

            lines.append(f"Entry {i+1}: title='{title}' push='{nrec}' class='{nrec_class}' author='{author}' date='{date}'")

        result = "\n".join(lines)
        (SCREENSHOTS / "explore2_output.txt").write_text(result, encoding="utf-8")
        print("Output written to explore2_output.txt")

        await browser.close()

asyncio.run(main())
