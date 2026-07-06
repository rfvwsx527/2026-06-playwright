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

async def main():
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await context.new_page()

        # CP1: Navigate to PTT Gossiping
        await page.goto("https://www.ptt.cc/bbs/Gossiping/index.html", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(SCREENSHOTS / "final_execution_1_initial.png"))
        log(1, "open PTT Gossiping index page")

        # CP2: Handle age verification
        confirm_btn = page.get_by_role("button", name="我同意")
        if await confirm_btn.count() > 0:
            await confirm_btn.click()
            await page.wait_for_timeout(2000)
            await page.screenshot(path=str(SCREENSHOTS / "final_execution_2_after_age_confirm.png"))
            log(2, "click age confirm button (我同意) - passed age verification")

        # CP3: Verify article list is visible
        entries = page.locator(".r-ent")
        total = await entries.count()
        await page.screenshot(path=str(SCREENSHOTS / "final_execution_3_article_list.png"))
        log(3, f"article list visible with {total} entries on the page")

        # CP4: Extract top 10 articles
        top_n = min(10, total)
        results = []
        for i in range(top_n):
            entry = entries.nth(i)
            title_el = entry.locator(".title a")
            nrec_el = entry.locator(".nrec span")

            title = (await title_el.inner_text()).strip() if await title_el.count() > 0 else "(本文已被刪除)"
            push = (await nrec_el.inner_text()).strip() if await nrec_el.count() > 0 else "0"

            results.append({"index": i + 1, "title": title, "push": push})

        await page.screenshot(path=str(SCREENSHOTS / "final_execution_4_top10_extracted.png"))
        log(4, f"extracted top {top_n} articles with titles and push counts")

        # CP5: Output results and write to log
        output_lines = []
        output_lines.append(f"PTT 八卦版 首頁前 {top_n} 篇文章：")
        output_lines.append("=" * 60)
        for r in results:
            line = f"{r['index']:2d}. [{r['push']:>4s}推] {r['title']}"
            output_lines.append(line)
            log(5, f"article {r['index']}: push={r['push']} title={r['title']}")

        output_text = "\n".join(output_lines)

        print(output_text)

        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"\n{output_text}\n")
            f.write(f"\nFINAL_RESPONSE: PTT Gossiping top {top_n} articles extracted\n")

        await page.screenshot(path=str(SCREENSHOTS / "final_execution_5_done.png"))
        log(6, "task complete - results written to log")

        await browser.close()

asyncio.run(main())
