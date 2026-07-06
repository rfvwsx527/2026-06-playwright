import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

RUN_DIR = Path(__file__).parent
SCREENSHOTS = RUN_DIR / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)
LOG = RUN_DIR / "final_script_log.txt"
LOG.write_text("", encoding="utf-8")

def log(step: int, msg: str) -> None:
    line = f"step {step} action: {msg}\n"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")

async def main():
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await context.new_page()

        # CP1: Navigate to BOT exchange rate page
        await page.goto("https://rate.bot.com.tw/xrt?Lang=zh-TW", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(SCREENSHOTS / "final_execution_1_open_page.png"))
        log(1, "open Taiwan Bank exchange rate page")
        assert "牌告匯率" in await page.title() or "rate.bot.com.tw" in page.url

        # Locate the exchange rate table
        table = page.get_by_role("table").first
        await table.wait_for(state="visible", timeout=10000)
        await page.screenshot(path=str(SCREENSHOTS / "final_execution_2_table_visible.png"))
        log(2, "exchange rate table is visible")

        # Find USD row - the row that contains "美金 (USD)"
        usd_row = table.get_by_role("row").filter(has_text="美金 (USD)")
        await usd_row.first.wait_for(state="visible", timeout=5000)

        # Get all cells in the USD row
        cells = await usd_row.first.get_by_role("cell").all()

        # CP2: Cash buying rate (本行買入) - 2nd cell (index 1)
        buying_rate = (await cells[1].inner_text()).strip()
        await page.screenshot(path=str(SCREENSHOTS / "final_execution_3_buying_rate.png"))
        log(2, f"USD cash buying rate (本行買入): {buying_rate}")

        # CP3: Cash selling rate (本行賣出) - 3rd cell (index 2)
        selling_rate = (await cells[2].inner_text()).strip()
        await page.screenshot(path=str(SCREENSHOTS / "final_execution_4_selling_rate.png"))
        log(3, f"USD cash selling rate (本行賣出): {selling_rate}")

        # CP4: Record final datum
        final_datum = f"美元 (USD) 現金買入: {buying_rate}, 現金賣出: {selling_rate}"
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"\nFINAL_RESPONSE: {final_datum}\n")
        print(f"FINAL_RESPONSE: {final_datum}")

        await page.screenshot(path=str(SCREENSHOTS / "final_execution_5_final_result.png"))
        log(5, "task complete - extracted USD rates")

        await browser.close()

asyncio.run(main())
