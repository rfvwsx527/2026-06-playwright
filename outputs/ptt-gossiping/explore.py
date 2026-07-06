import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

WORKSPACE = Path(r"C:\Users\user\Desktop\2026-06-playwright\outputs\ptt-gossiping")
SCREENSHOTS = WORKSPACE / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

async def main():
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await context.new_page()

        await page.goto("https://www.ptt.cc/bbs/Gossiping/index.html", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(SCREENSHOTS / "explore_1_initial.png"))

        print("URL:", page.url)
        title = await page.title()
        print("TITLE:", title)

        # Check for age verification overlay
        snapshot = await page.locator("body").aria_snapshot()
        (SCREENSHOTS / "explore_aria_initial.txt").write_text(snapshot[:8000], encoding="utf-8")
        print("Initial ARIA snapshot written")

        # Look for age confirm button
        try:
            confirm_btn = page.get_by_role("button", name="滿18歲")
            if await confirm_btn.count() > 0:
                print("Found age confirm button (滿18歲)")
                await confirm_btn.click()
                await page.wait_for_timeout(2000)
                await page.screenshot(path=str(SCREENSHOTS / "explore_2_after_confirm.png"))
                print("Clicked age confirm button")
            else:
                # Try alternative text
                confirm_btn = page.get_by_role("button", name="我同意")
                if await confirm_btn.count() > 0:
                    print("Found age confirm button (我同意)")
                    await confirm_btn.click()
                    await page.wait_for_timeout(2000)
                    await page.screenshot(path=str(SCREENSHOTS / "explore_2_after_confirm.png"))
                    print("Clicked age confirm button")
                else:
                    print("No age confirm button found, checking all buttons...")
                    all_buttons = await page.get_by_role("button").all()
                    for b in all_buttons:
                        txt = await b.inner_text()
                        print(f"  Button text: '{txt}'")
        except Exception as e:
            print(f"Error with confirm button: {e}")

        # Now get the article list
        await page.screenshot(path=str(SCREENSHOTS / "explore_3_article_list.png"))
        snapshot2 = await page.locator("body").aria_snapshot()
        (SCREENSHOTS / "explore_aria_after.txt").write_text(snapshot2[:10000], encoding="utf-8")
        print("After-confirm ARIA snapshot written")

        # Check for article entries
        entries = page.locator(".r-ent")
        count = await entries.count()
        print(f"Found {count} article entries (.r-ent)")

        # Print first few articles directly
        text = await page.locator("body").inner_text()
        (SCREENSHOTS / "explore_text.txt").write_text(text[:5000], encoding="utf-8")
        print("Body text written")

        await browser.close()

asyncio.run(main())
