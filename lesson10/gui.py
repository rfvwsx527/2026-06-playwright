"""專案 01：開啟真實網頁，檢查標題並留下截圖。

本模組同時支援兩種用法：
1. 命令列直接執行（python practice5.py --browser firefox）
2. 被 gui.py 匯入，提供核心檢查功能給桌面 App 使用
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


# 預設造訪的網址（命令列模式使用）
URL = "https://example.com/"

# 截圖輸出資料夾：本程式檔所在資料夾下的 output 子資料夾
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


@dataclass
class CheckResult:
    """一次網站檢查的完整結果。

    用 dataclass 把所有結果欄位包成一個物件，
    方便 GUI 或其他呼叫端以結構化方式讀取。
    """

    url: str                                # 使用者輸入的原始網址
    success: bool                           # 檢查是否成功完成
    http_status: int | None = None          # HTTP 狀態碼（如 200、404）；無回應則為 None
    response_time_ms: float | None = None   # 頁面載入耗時（毫秒）
    page_title: str | None = None           # 瀏覽器分頁標題（<title>）
    main_heading: str | None = None         # 頁面第一個 h1 主標題文字
    final_url: str | None = None            # 最終網址（可能經過轉址）
    screenshot_path: str | None = None      # 截圖檔案路徑
    error_message: str | None = None        # 失敗時的錯誤訊息


def validate_url(raw_url: str) -> str:
    """驗證並整理使用者輸入的網址。

    規則：
    - 去除前後空白
    - 不可為空
    - 沒有 http:// 或 https:// 開頭時，自動補上 https://
    - 必須解析得出主機名稱（netloc）

    驗證失敗時拋出 ValueError，由呼叫端決定如何呈現錯誤。
    """
    url = raw_url.strip()
    if not url:
        raise ValueError("請輸入網址")

    # 自動補上協定，讓使用者可以只輸入 example.com
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError(f"網址格式不正確：{raw_url}")

    return url


def validate_timeout(raw_timeout: str) -> int:
    """驗證逾時設定（毫秒），回傳整數。

    規則：必須是正整數，且介於 1000～120000 毫秒（1～120 秒）。
    驗證失敗時拋出 ValueError。
    """
    text = raw_timeout.strip()
    try:
        timeout_ms = int(text)
    except ValueError:
        raise ValueError(f"逾時必須是整數（毫秒）：{raw_timeout}") from None

    if not 1000 <= timeout_ms <= 120_000:
        raise ValueError("逾時需介於 1000～120000 毫秒（1～120 秒）")

    return timeout_ms


def check_website_core(
    url: str,
    browser_name: str = "chromium",
    headless: bool = True,
    timeout_ms: int = 30_000,
) -> CheckResult:
    """執行網站檢查的核心邏輯，回傳 CheckResult。

    這個函式「只做事、不印東西」，成功或失敗都以回傳值表達，
    因此命令列和 GUI 都能重複使用它。

    參數:
        url:          要檢查的網址（建議先經過 validate_url）
        browser_name: chromium / firefox / webkit
        headless:     True 為背景執行；False 會顯示瀏覽器視窗
        timeout_ms:   頁面載入逾時（毫秒）
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    try:
        with sync_playwright() as playwright:
            # 依名稱動態取得瀏覽器類型（等同 playwright.chromium 等）
            browser_type = getattr(playwright, browser_name)
            browser = browser_type.launch(headless=headless)
            page = browser.new_page(viewport={"width": 1280, "height": 720})

            # 記錄載入前後時間，計算回應毫秒數
            start = time.perf_counter()
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            elapsed_ms = (time.perf_counter() - start) * 1000

            # 嘗試取得頁面第一個 h1；有些頁面沒有 h1，取不到就記為 None
            heading: str | None
            try:
                heading = page.locator("h1").first.inner_text(timeout=3000)
            except PlaywrightError:
                heading = None

            # 截圖檔名帶上瀏覽器名稱，例如 output/homepage_chromium.png
            screenshot = OUTPUT_DIR / f"homepage_{browser_name}.png"
            page.screenshot(path=screenshot, full_page=True)

            result = CheckResult(
                url=url,
                success=True,
                http_status=response.status if response else None,
                response_time_ms=elapsed_ms,
                page_title=page.title(),
                main_heading=heading,
                final_url=page.url,
                screenshot_path=str(screenshot),
            )
            browser.close()
            return result

    except PlaywrightError as exc:
        # Playwright 相關錯誤（網址打不開、逾時、瀏覽器未安裝等）
        return CheckResult(url=url, success=False, error_message=str(exc))
    except Exception as exc:  # noqa: BLE001 - 保底：任何意外都轉成失敗結果
        return CheckResult(url=url, success=False, error_message=f"未預期的錯誤：{exc}")


def check_website(browser_name: str = "chromium") -> None:
    """命令列版本：執行檢查並把結果印到終端機。

    保留原本的介面，內部改為呼叫 check_website_core。
    """
    result = check_website_core(
        url=URL,
        browser_name=browser_name,
        headless=False,   # 命令列模式維持原本「顯示視窗」的行為
    )

    print(f"瀏覽器: {browser_name}")
    if not result.success:
        print(f"檢查失敗: {result.error_message}")
        return

    print(f"HTTP 狀態: {result.http_status if result.http_status is not None else '無回應'}")
    print(f"回應時間: {result.response_time_ms:.1f} ms")
    print(f"頁面標題: {result.page_title}")
    print(f"主標題: {result.main_heading or '（找不到 h1）'}")
    print(f"截圖: {result.screenshot_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--browser", choices=["chromium", "firefox", "webkit"], default="chromium"
    )
    args = parser.parse_args()
    check_website(args.browser)
