"""專案 01：開啟真實網頁，檢查標題並留下截圖。"""

import argparse                 # 標準函式庫：用來解析命令列參數（例如 --browser firefox）
from pathlib import Path        # 標準函式庫：以物件方式操作檔案路徑，比字串拼接安全

from playwright.sync_api import sync_playwright  # Playwright 的「同步版」API


# 要造訪的目標網址
URL = "https://example.com/"

# 截圖輸出資料夾：
# __file__ 是本程式檔的路徑，resolve() 轉成絕對路徑，
# .parent 取得所在資料夾，再接上 "output" 子資料夾
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def check_website(browser_name: str = "chromium") -> None:
    """開啟指定瀏覽器造訪網頁，驗證標題並截圖。

    參數:
        browser_name: 瀏覽器名稱，可為 chromium / firefox / webkit
    """
    # 建立輸出資料夾；exist_ok=True 表示資料夾已存在時不報錯
    OUTPUT_DIR.mkdir(exist_ok=True)

    # with 語法確保 Playwright 結束時自動釋放資源
    with sync_playwright() as playwright:
        # getattr 依名稱動態取得瀏覽器類型物件，
        # 等同於 playwright.chromium 或 playwright.firefox 等
        browser_type = getattr(playwright, browser_name)

        # 啟動瀏覽器；headless=False 表示顯示視窗（True 則背景執行）
        browser = browser_type.launch(headless=False)

        # 開新分頁，並指定視窗大小為 1280x720
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        # 前往目標網址；wait_until="domcontentloaded" 表示
        # 等到 HTML 解析完成即可，不必等所有圖片資源載入
        response = page.goto(URL, wait_until="domcontentloaded")

        # 用「無障礙角色」定位元素：找出名為 "Example Domain" 的標題（h1）
        # inner_text() 取出該元素的文字內容
        heading = page.get_by_role("heading", name="Example Domain").inner_text()

        # 組出截圖檔名，例如 output/homepage_chromium.png
        screenshot = OUTPUT_DIR / f"homepage_{browser_name}.png"

        # 對整個頁面截圖（full_page=True 包含捲動範圍，不只可見區域）
        page.screenshot(path=screenshot, full_page=True)

        # 印出檢查結果
        print(f"瀏覽器: {browser_name}")
        # response 可能為 None（例如導向 about:blank），所以要先判斷
        print(f"HTTP 狀態: {response.status if response else '無回應'}")
        print(f"頁面標題: {page.title()}")      # 瀏覽器分頁上顯示的 <title>
        print(f"主標題: {heading}")             # 頁面內的 h1 文字
        print(f"截圖: {screenshot}")

        # 關閉瀏覽器，釋放資源
        browser.close()


# 只有「直接執行本檔案」時才會進入這個區塊；被 import 時不會執行
if __name__ == "__main__":
    # 建立命令列參數解析器
    parser = argparse.ArgumentParser()

    # 定義 --browser 參數：限定三種選擇，預設用 chromium
    # 使用範例: python practice5.py --browser firefox
    parser.add_argument(
        "--browser", choices=["chromium", "firefox", "webkit"], default="chromium"
    )

    # 解析使用者實際輸入的參數
    args = parser.parse_args()

    # 以指定的瀏覽器執行檢查
    check_website(args.browser)
