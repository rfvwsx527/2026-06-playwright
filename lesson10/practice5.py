"""專案 01：開啟真實網頁，檢查標題並留下截圖。

本檔案同時扮演兩種角色：
1. CLI 工具（原本的用法完全不變）：
       python practice5.py --browser firefox
2. 核心函式庫：GUI（gui.py）與測試（tests/）都呼叫這裡的
   `run_check()`、`validate_url()`、`validate_timeout()`。
"""

import argparse                 # 標準函式庫：解析命令列參數（例如 --browser firefox）
import time                     # 用來計算回應時間
from dataclasses import dataclass, field   # 用資料類別包裝檢查結果，比 dict 更清楚
from pathlib import Path        # 以物件方式操作檔案路徑，比字串拼接安全
from typing import Callable, Optional
from urllib.parse import urlparse          # 驗證 URL 格式用

from playwright.sync_api import (
    Error as PlaywrightError,   # Playwright 的一般錯誤（例如 DNS 解析失敗）
    TimeoutError as PlaywrightTimeoutError,  # 逾時錯誤
    sync_playwright,            # Playwright 的「同步版」API
)

# 要造訪的預設目標網址（CLI 模式沿用原本行為）
URL = "https://example.com/"

# 截圖輸出資料夾：
# __file__ 是本程式檔的路徑，resolve() 轉成絕對路徑，
# .parent 取得所在資料夾，再接上 "output" 子資料夾
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# 支援的瀏覽器名稱
SUPPORTED_BROWSERS = ("chromium", "firefox", "webkit")

# timeout 允許範圍（秒）
TIMEOUT_MIN_SECONDS = 1
TIMEOUT_MAX_SECONDS = 120


# ---------------------------------------------------------------------------
# 檢查結果的資料結構
# ---------------------------------------------------------------------------
@dataclass
class CheckResult:
    """單次網站健康檢查的完整結果，供 CLI / GUI / 測試共用。"""

    url: str                              # 使用者輸入的網址
    browser_name: str                     # 使用的瀏覽器
    ok: bool = False                      # 是否成功完成整個流程
    status: Optional[int] = None          # HTTP 狀態碼（可能為 None）
    page_title: str = ""                  # 分頁上的 <title>
    heading: str = ""                     # 頁面內第一個 <h1> 文字
    final_url: str = ""                   # 轉址後最終停留的網址
    screenshot_path: Optional[Path] = None  # 截圖檔案位置
    elapsed_ms: Optional[float] = None    # 從導航到讀完資料的耗時（毫秒）
    warnings: list[str] = field(default_factory=list)  # 非致命的警告
    error: Optional[str] = None           # 給學生看的友善錯誤訊息
    error_detail: Optional[str] = None    # 原始技術訊息（除錯用）

    @property
    def level(self) -> str:
        """回傳整體狀態：success / warning / error，方便 UI 上色。"""
        if not self.ok:
            return "error"
        if self.warnings or (self.status is not None and self.status >= 400):
            return "warning"
        return "success"


# ---------------------------------------------------------------------------
# 輸入驗證：GUI 在啟動檢查前先呼叫，避免把爛輸入丟給 Playwright
# ---------------------------------------------------------------------------
def validate_url(raw: str) -> tuple[Optional[str], Optional[str]]:
    """驗證並整理 URL。

    回傳 (整理後的網址, None) 或 (None, 錯誤訊息)。
    """
    url = (raw or "").strip()
    if not url:
        return None, "請先輸入網址，例如 https://example.com/"

    # 學生常忘記打協定，幫忙自動補上 https://
    if "://" not in url:
        url = "https://" + url

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None, (
            f"不支援的協定「{parsed.scheme}」："
            "請使用 http:// 或 https:// 開頭的網址。"
        )
    if not parsed.netloc or "." not in parsed.netloc.strip("."):
        # netloc 是網域部分；沒有「點」通常代表打錯（localhost 除外）
        if parsed.netloc.lower() not in ("localhost",) and ":" not in parsed.netloc:
            return None, (
                "網址看起來不完整：網域應類似 example.com。"
                "請檢查是否有錯字或漏掉 .com / .tw 等結尾。"
            )
    return url, None


def validate_timeout(raw: str) -> tuple[Optional[int], Optional[str]]:
    """驗證 timeout（秒）。回傳 (毫秒, None) 或 (None, 錯誤訊息)。"""
    text = (raw or "").strip()
    if not text:
        return None, "請輸入逾時秒數，建議 15。"
    try:
        seconds = float(text)
    except ValueError:
        return None, f"逾時必須是數字，你輸入的是「{text}」。"
    if not (TIMEOUT_MIN_SECONDS <= seconds <= TIMEOUT_MAX_SECONDS):
        return None, (
            f"逾時需介於 {TIMEOUT_MIN_SECONDS} 到 {TIMEOUT_MAX_SECONDS} 秒之間；"
            "太短容易誤判失敗，太長會等很久。"
        )
    return int(seconds * 1000), None


def _friendly_error(exc: Exception) -> str:
    """把 Playwright 的技術錯誤翻譯成對學生有幫助的中文說明。"""
    msg = str(exc)
    if isinstance(exc, PlaywrightTimeoutError):
        return (
            "載入逾時：網站在指定時間內沒有回應。"
            "可以：1) 確認網址正確 2) 檢查網路連線 3) 把逾時秒數調大再試。"
        )
    if "ERR_NAME_NOT_RESOLVED" in msg or "NS_ERROR_UNKNOWN_HOST" in msg:
        return (
            "找不到這個網域（DNS 解析失敗）。"
            "請確認網址拼字正確，例如 example.com 而不是 exampel.com。"
        )
    if "ERR_CONNECTION_REFUSED" in msg or "NS_ERROR_CONNECTION_REFUSED" in msg:
        return (
            "連線被拒絕：目標主機沒有在該埠提供服務。"
            "若是本機開發伺服器，請確認它已啟動、埠號正確。"
        )
    if "ERR_CERT" in msg or "SSL" in msg.upper():
        return "HTTPS 憑證有問題：網站憑證無效或過期，瀏覽器因安全考量拒絕連線。"
    if "ERR_INTERNET_DISCONNECTED" in msg:
        return "目前沒有網路連線，請先檢查你的網路。"
    if "Executable doesn't exist" in msg or "browserType.launch" in msg:
        return (
            "找不到瀏覽器執行檔：Playwright 的瀏覽器還沒安裝。"
            "請在終端機執行：python -m playwright install"
        )
    return f"發生未預期的錯誤：{msg.splitlines()[0] if msg else exc.__class__.__name__}"


# ---------------------------------------------------------------------------
# 核心檢查函式：CLI 與 GUI 都呼叫這裡
# ---------------------------------------------------------------------------
def run_check(
    url: str = URL,
    browser_name: str = "chromium",
    headless: bool = True,
    timeout_ms: int = 15000,
    output_dir: Path = OUTPUT_DIR,
    screenshot_name: Optional[str] = None,
    on_log: Optional[Callable[[str], None]] = None,
) -> CheckResult:
    """開啟指定瀏覽器造訪網頁，取得狀態 / 標題 / 主標題並截圖。

    參數:
        url:             目標網址
        browser_name:    chromium / firefox / webkit
        headless:        True 背景執行；False 顯示視窗
        timeout_ms:      導航逾時（毫秒）
        output_dir:      截圖輸出資料夾
        screenshot_name: 截圖檔名；None 時用 homepage_{browser_name}.png（與舊版相同）
        on_log:          進度回呼函式，GUI 用來即時顯示日誌；None 表示不需要
    回傳:
        CheckResult 資料類別，成功與失敗都會回傳（不會直接丟出例外）。
    """
    log = on_log or (lambda _msg: None)
    result = CheckResult(url=url, browser_name=browser_name)

    if browser_name not in SUPPORTED_BROWSERS:
        result.error = (
            f"不支援的瀏覽器「{browser_name}」，"
            f"請使用 {', '.join(SUPPORTED_BROWSERS)} 其中之一。"
        )
        return result

    # 建立輸出資料夾；exist_ok=True 表示資料夾已存在時不報錯
    output_dir.mkdir(parents=True, exist_ok=True)

    browser = None
    try:
        # with 語法確保 Playwright 結束時自動釋放資源
        with sync_playwright() as playwright:
            log(f"啟動 {browser_name}（headless={headless}）…")
            # getattr 依名稱動態取得瀏覽器類型物件，
            # 等同於 playwright.chromium 或 playwright.firefox 等
            browser_type = getattr(playwright, browser_name)
            browser = browser_type.launch(headless=headless)

            # 開新分頁，並指定視窗大小為 1280x720
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.set_default_timeout(timeout_ms)

            log(f"導航至 {url} …")
            start = time.perf_counter()
            # wait_until="domcontentloaded" 表示等 HTML 解析完成即可，
            # 不必等所有圖片資源載入
            response = page.goto(url, wait_until="domcontentloaded",
                                 timeout=timeout_ms)
            result.elapsed_ms = (time.perf_counter() - start) * 1000

            # response 可能為 None（例如導向 about:blank），所以要先判斷
            result.status = response.status if response else None
            result.page_title = page.title()   # 分頁上顯示的 <title>
            result.final_url = page.url        # 轉址後的最終網址

            # 取頁面內第一個 <h1> 作為主標題；沒有 h1 不算失敗，記為警告
            h1 = page.locator("h1").first
            if h1.count() > 0:
                result.heading = h1.inner_text().strip()
            else:
                result.warnings.append("頁面沒有 <h1> 主標題。")

            if result.status is None:
                result.warnings.append("沒有取得 HTTP 回應（可能是特殊導向）。")
            elif result.status >= 400:
                result.warnings.append(
                    f"HTTP 狀態 {result.status}：頁面可開啟，但伺服器回報錯誤。"
                )

            # 組出截圖檔名，例如 output/homepage_chromium.png
            name = screenshot_name or f"homepage_{browser_name}.png"
            screenshot = output_dir / name
            log("擷取整頁截圖…")
            # full_page=True 包含捲動範圍，不只可見區域
            page.screenshot(path=screenshot, full_page=True)
            result.screenshot_path = screenshot

            result.ok = True
            log("檢查完成。")
    except (PlaywrightError, PlaywrightTimeoutError) as exc:
        result.error = _friendly_error(exc)
        result.error_detail = str(exc)
        log(f"發生錯誤：{result.error}")
    except Exception as exc:  # 最後防線：任何意外都轉成結果物件，不讓執行緒炸掉
        result.error = _friendly_error(exc)
        result.error_detail = repr(exc)
        log(f"發生錯誤：{result.error}")
    finally:
        # 若在截圖前就失敗，仍嘗試關閉瀏覽器釋放資源
        try:
            if browser is not None and browser.is_connected():
                browser.close()
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# 原本的 CLI 介面：行為與輸出格式維持不變
# ---------------------------------------------------------------------------
def check_website(browser_name: str = "chromium") -> None:
    """開啟指定瀏覽器造訪網頁，驗證標題並截圖（CLI 用，保留原行為）。

    參數:
        browser_name: 瀏覽器名稱，可為 chromium / firefox / webkit
    """
    # 原程式 headless=False（顯示視窗）、固定造訪 URL 常數
    result = run_check(url=URL, browser_name=browser_name, headless=False)

    if not result.ok:
        # 原程式遇錯會直接拋例外中止；這裡改為印出友善訊息後以非零碼結束
        raise SystemExit(f"檢查失敗：{result.error}")

    # 印出檢查結果（與原版相同的欄位與格式）
    print(f"瀏覽器: {result.browser_name}")
    print(f"HTTP 狀態: {result.status if result.status is not None else '無回應'}")
    print(f"頁面標題: {result.page_title}")
    print(f"主標題: {result.heading or '（未找到 h1）'}")
    print(f"截圖: {result.screenshot_path}")


# 只有「直接執行本檔案」時才會進入這個區塊；被 import 時不會執行
if __name__ == "__main__":
    # 建立命令列參數解析器
    parser = argparse.ArgumentParser()

    # 定義 --browser 參數：限定三種選擇，預設用 chromium
    # 使用範例: python practice5.py --browser firefox
    parser.add_argument(
        "--browser", choices=list(SUPPORTED_BROWSERS), default="chromium"
    )

    # 解析使用者實際輸入的參數
    args = parser.parse_args()

    # 以指定的瀏覽器執行檢查
    check_website(args.browser)
