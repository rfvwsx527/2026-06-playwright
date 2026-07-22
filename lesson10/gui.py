"""網站健康檢查 App（tkinter GUI 入口）。

執行方式：
    python gui.py
或（使用 uv）：
    uv run python gui.py

設計重點：
- Playwright 一律在 background worker thread 執行，絕不卡住 mainloop。
- worker 只把訊息丟進 queue.Queue；主執行緒用 root.after() 定時取出，
  所有 tkinter 元件更新都發生在主執行緒（thread-safe 的標準做法）。
- 依需求本專案預設不建立任何資料庫。
"""

import math
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional

from practice5 import (
    OUTPUT_DIR,
    SUPPORTED_BROWSERS,
    CheckResult,
    run_check,
    validate_timeout,
    validate_url,
)

# ---------------------------------------------------------------------------
# 色彩系統：深藍底 + 青綠強調色
# ---------------------------------------------------------------------------
C_BG        = "#0B1B2B"   # 視窗底色（深藍）
C_CARD      = "#12283C"   # 卡片底色
C_CARD_HI   = "#16324A"   # 卡片內輸入區
C_BORDER    = "#1E3A55"   # 卡片邊線
C_TEXT      = "#E6F1F7"   # 主要文字
C_MUTED     = "#7FA3BC"   # 次要文字
C_ACCENT    = "#14B8A6"   # 青綠（主按鈕、成功）
C_ACCENT_D  = "#0D9488"   # 青綠 hover
C_WARN      = "#F59E0B"   # 警告
C_ERROR     = "#F87171"   # 失敗
C_INFO      = "#38BDF8"   # 資訊藍

PREVIEW_MAX_W = 520
PREVIEW_MAX_H = 280


class HealthCheckApp:
    """主應用程式：組裝 UI、管理 worker thread 與訊息佇列。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("網站健康檢查 App")
        self.root.geometry("1200x760")
        self.root.minsize(1080, 680)
        self.root.configure(bg=C_BG)

        # worker → 主執行緒 的訊息佇列；每則訊息是 (kind, payload)
        self.msg_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self._preview_image: Optional[tk.PhotoImage] = None  # 防止被 GC 回收

        self._build_styles()
        self._build_layout()
        self._log("就緒。輸入網址後按「開始檢查」。", "info")

        # 啟動佇列輪詢：每 100ms 檢查一次 worker 是否有新訊息
        self.root.after(100, self._poll_queue)

    # ------------------------------------------------------------------ 樣式
    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(".", background=C_BG, foreground=C_TEXT,
                        font=("Microsoft JhengHei UI", 10))
        style.configure("Card.TFrame", background=C_CARD,
                        bordercolor=C_BORDER, relief="flat")
        style.configure("Bg.TFrame", background=C_BG)

        style.configure("Title.TLabel", background=C_BG, foreground=C_TEXT,
                        font=("Microsoft JhengHei UI", 17, "bold"))
        style.configure("Subtitle.TLabel", background=C_BG, foreground=C_MUTED,
                        font=("Microsoft JhengHei UI", 10))
        style.configure("CardTitle.TLabel", background=C_CARD, foreground=C_ACCENT,
                        font=("Microsoft JhengHei UI", 12, "bold"))
        style.configure("Card.TLabel", background=C_CARD, foreground=C_TEXT)
        style.configure("CardMuted.TLabel", background=C_CARD, foreground=C_MUTED,
                        font=("Microsoft JhengHei UI", 9))
        style.configure("Value.TLabel", background=C_CARD, foreground=C_TEXT,
                        font=("Consolas", 11, "bold"))

        # 狀態徽章
        for name, fg in (("Success", C_ACCENT), ("Warning", C_WARN),
                         ("Error", C_ERROR), ("Idle", C_MUTED), ("Run", C_INFO)):
            style.configure(f"{name}.Badge.TLabel", background=C_CARD,
                            foreground=fg,
                            font=("Microsoft JhengHei UI", 12, "bold"))

        # 主要按鈕（青綠實心）
        style.configure("Accent.TButton", background=C_ACCENT, foreground="#06251F",
                        font=("Microsoft JhengHei UI", 11, "bold"),
                        borderwidth=0, focusthickness=0, padding=(16, 10))
        style.map("Accent.TButton",
                  background=[("active", C_ACCENT_D), ("disabled", "#28506B")],
                  foreground=[("disabled", C_MUTED)])

        # 次要按鈕（描邊）
        style.configure("Ghost.TButton", background=C_CARD, foreground=C_TEXT,
                        bordercolor=C_BORDER, borderwidth=1, padding=(12, 7))
        style.map("Ghost.TButton", background=[("active", C_CARD_HI)])

        # 輸入元件
        style.configure("TEntry", fieldbackground=C_CARD_HI, foreground=C_TEXT,
                        bordercolor=C_BORDER, insertcolor=C_TEXT, padding=6)
        style.configure("TCombobox", fieldbackground=C_CARD_HI, foreground=C_TEXT,
                        background=C_CARD_HI, bordercolor=C_BORDER,
                        arrowcolor=C_ACCENT, padding=6)
        self.root.option_add("*TCombobox*Listbox.background", C_CARD_HI)
        self.root.option_add("*TCombobox*Listbox.foreground", C_TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", C_ACCENT)

        style.configure("TCheckbutton", background=C_CARD, foreground=C_TEXT)
        style.map("TCheckbutton", background=[("active", C_CARD)],
                  indicatorcolor=[("selected", C_ACCENT), ("!selected", C_CARD_HI)])

        style.configure("TProgressbar", troughcolor=C_CARD_HI,
                        background=C_ACCENT, bordercolor=C_BORDER,
                        lightcolor=C_ACCENT, darkcolor=C_ACCENT)

    # ------------------------------------------------------------------ 佈局
    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, style="Bg.TFrame", padding=(18, 14, 18, 12))
        outer.pack(fill="both", expand=True)

        # 頂部標題列
        header = ttk.Frame(outer, style="Bg.TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="🌐 網站健康檢查", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Playwright × tkinter・檢查狀態、標題並截圖",
                  style="Subtitle.TLabel").pack(side="left", padx=(14, 0), pady=(6, 0))

        # 中段：左右雙欄
        body = ttk.Frame(outer, style="Bg.TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=380)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_left_panel(body)
        self._build_right_panel(body)
        self._build_bottom_panel(outer)

    def _card(self, parent: tk.Widget) -> ttk.Frame:
        """建立帶邊框的卡片容器。"""
        wrap = tk.Frame(parent, bg=C_BORDER, bd=0,
                        highlightthickness=0)  # 外層當 1px 邊線
        card = ttk.Frame(wrap, style="Card.TFrame", padding=16)
        card.pack(fill="both", expand=True, padx=1, pady=1)
        return wrap, card

    # ---------------------------------------------------------------- 左欄
    def _build_left_panel(self, parent: ttk.Frame) -> None:
        wrap, card = self._card(parent)
        wrap.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        ttk.Label(card, text="檢查設定", style="CardTitle.TLabel").pack(anchor="w")

        ttk.Label(card, text="目標網址", style="Card.TLabel").pack(anchor="w", pady=(14, 4))
        self.url_var = tk.StringVar(value="https://example.com/")
        url_entry = ttk.Entry(card, textvariable=self.url_var, font=("Consolas", 11))
        url_entry.pack(fill="x")
        ttk.Label(card, text="可省略 https://，會自動補上",
                  style="CardMuted.TLabel").pack(anchor="w", pady=(3, 0))

        ttk.Label(card, text="瀏覽器引擎", style="Card.TLabel").pack(anchor="w", pady=(14, 4))
        self.browser_var = tk.StringVar(value="chromium")
        combo = ttk.Combobox(card, textvariable=self.browser_var,
                             values=list(SUPPORTED_BROWSERS), state="readonly")
        combo.pack(fill="x")

        opt_row = ttk.Frame(card, style="Card.TFrame")
        opt_row.pack(fill="x", pady=(14, 0))
        self.headless_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_row, text="Headless（背景執行，不開視窗）",
                        variable=self.headless_var).pack(side="left")

        ttk.Label(card, text="逾時（秒）", style="Card.TLabel").pack(anchor="w", pady=(14, 4))
        self.timeout_var = tk.StringVar(value="15")
        ttk.Entry(card, textvariable=self.timeout_var, width=10,
                  font=("Consolas", 11)).pack(anchor="w")

        self.start_btn = ttk.Button(card, text="▶  開始檢查", style="Accent.TButton",
                                    command=self.start_check)
        self.start_btn.pack(fill="x", pady=(22, 6))

        self.progress = ttk.Progressbar(card, mode="indeterminate")
        # 進度條先不 pack，執行時才顯示

        ttk.Label(card, text="提示：Playwright 會實際開啟瀏覽器造訪頁面，\n"
                             "首次使用請先執行 python -m playwright install",
                  style="CardMuted.TLabel", justify="left").pack(
            side="bottom", anchor="w", pady=(12, 0))

    # ---------------------------------------------------------------- 右欄
    def _build_right_panel(self, parent: ttk.Frame) -> None:
        wrap, card = self._card(parent)
        wrap.grid(row=0, column=1, sticky="nsew")

        top = ttk.Frame(card, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="檢查結果", style="CardTitle.TLabel").pack(side="left")
        self.badge = ttk.Label(top, text="● 待命", style="Idle.Badge.TLabel")
        self.badge.pack(side="right")

        grid = ttk.Frame(card, style="Card.TFrame")
        grid.pack(fill="x", pady=(12, 8))
        for col in (1, 3):
            grid.columnconfigure(col, weight=1)

        self.val_status = self._result_cell(grid, 0, 0, "HTTP 狀態")
        self.val_time   = self._result_cell(grid, 0, 2, "回應時間")
        self.val_title  = self._result_cell(grid, 1, 0, "頁面標題", colspan=3)
        self.val_h1     = self._result_cell(grid, 2, 0, "主標題 (h1)", colspan=3)
        self.val_final  = self._result_cell(grid, 3, 0, "最終 URL", colspan=3)

        ttk.Label(card, text="截圖預覽", style="Card.TLabel").pack(anchor="w", pady=(6, 4))
        self.preview_frame = tk.Frame(card, bg=C_CARD_HI, height=PREVIEW_MAX_H)
        self.preview_frame.pack(fill="both", expand=True)
        self.preview_frame.pack_propagate(False)
        self.preview_label = tk.Label(self.preview_frame, bg=C_CARD_HI,
                                      fg=C_MUTED, text="（尚無截圖）",
                                      font=("Microsoft JhengHei UI", 10))
        self.preview_label.pack(fill="both", expand=True)

    def _result_cell(self, parent, row, col, title, colspan=1) -> ttk.Label:
        cell = ttk.Frame(parent, style="Card.TFrame")
        cell.grid(row=row, column=col, columnspan=colspan + 1,
                  sticky="ew", padx=(0, 16), pady=4)
        ttk.Label(cell, text=title, style="CardMuted.TLabel").pack(anchor="w")
        value = ttk.Label(cell, text="—", style="Value.TLabel",
                          wraplength=640, justify="left")
        value.pack(anchor="w")
        return value

    # ---------------------------------------------------------------- 底部
    def _build_bottom_panel(self, parent: ttk.Frame) -> None:
        wrap, card = self._card(parent)
        wrap.pack(fill="x", pady=(12, 0))

        bar = ttk.Frame(card, style="Card.TFrame")
        bar.pack(fill="x")
        ttk.Label(bar, text="執行日誌", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(bar, text="清除結果", style="Ghost.TButton",
                   command=self.clear_results).pack(side="right", padx=(8, 0))
        ttk.Button(bar, text="開啟輸出資料夾", style="Ghost.TButton",
                   command=self.open_output_dir).pack(side="right")

        log_frame = tk.Frame(card, bg=C_CARD_HI)
        log_frame.pack(fill="x", pady=(8, 0))
        self.log_text = tk.Text(log_frame, height=7, bg=C_CARD_HI, fg=C_TEXT,
                                insertbackground=C_TEXT, relief="flat",
                                font=("Consolas", 10), state="disabled", wrap="word")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical",
                                  command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=6)

        for tag, color in (("info", C_INFO), ("ok", C_ACCENT),
                           ("warn", C_WARN), ("err", C_ERROR),
                           ("muted", C_MUTED)):
            self.log_text.tag_configure(tag, foreground=color)

    # ================================================================ 行為
    def start_check(self) -> None:
        """驗證輸入後啟動 worker thread。此函式只在主執行緒被呼叫。"""
        if self.worker and self.worker.is_alive():
            return  # 防呆：已有檢查在跑

        url, err = validate_url(self.url_var.get())
        if err:
            self._log(f"輸入有誤：{err}", "err")
            self._set_badge("error", "● 輸入錯誤")
            return

        timeout_ms, err = validate_timeout(self.timeout_var.get())
        if err:
            self._log(f"輸入有誤：{err}", "err")
            self._set_badge("error", "● 輸入錯誤")
            return

        browser = self.browser_var.get()
        headless = self.headless_var.get()

        # UI 進入「執行中」狀態
        self.start_btn.configure(state="disabled", text="檢查中…")
        self._set_badge("run", "● 檢查中")
        self.progress.pack(fill="x", pady=(0, 4))
        self.progress.start(12)
        self._log(f"開始檢查 {url}（{browser}, headless={headless}, "
                  f"timeout={timeout_ms // 1000}s）", "info")

        # 每次檢查用時間戳截圖檔名，避免 GUI 預覽讀到舊圖快取
        shot_name = f"gui_{browser}_{int(time.time())}.png"

        def job() -> None:
            """worker thread：只做運算與 queue.put，絕不碰任何 tkinter 元件。"""
            result = run_check(
                url=url, browser_name=browser, headless=headless,
                timeout_ms=timeout_ms, screenshot_name=shot_name,
                on_log=lambda msg: self.msg_queue.put(("log", msg)),
            )
            self.msg_queue.put(("done", result))

        self.worker = threading.Thread(target=job, daemon=True)
        self.worker.start()

    def _poll_queue(self) -> None:
        """主執行緒定時輪詢佇列；所有 UI 更新集中在這裡，確保 thread-safe。"""
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._log(str(payload), "muted")
                elif kind == "done":
                    self._on_done(payload)  # type: ignore[arg-type]
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _on_done(self, result: CheckResult) -> None:
        """把檢查結果反映到畫面（主執行緒）。"""
        self.progress.stop()
        self.progress.pack_forget()
        self.start_btn.configure(state="normal", text="▶  開始檢查")

        if result.level == "error":
            self._set_badge("error", "● 失敗")
            self._log(result.error or "未知錯誤", "err")
            if result.error_detail:
                self._log(f"技術細節：{result.error_detail.splitlines()[0]}", "muted")
            self.val_status.configure(text="—")
            self.val_time.configure(text="—")
            return

        # 成功或警告
        self.val_status.configure(
            text=str(result.status) if result.status is not None else "無回應")
        self.val_time.configure(
            text=f"{result.elapsed_ms:.0f} ms" if result.elapsed_ms else "—")
        self.val_title.configure(text=result.page_title or "（空白）")
        self.val_h1.configure(text=result.heading or "（未找到 h1）")
        self.val_final.configure(text=result.final_url or "—")

        if result.level == "warning":
            self._set_badge("warning", "● 完成（有警告）")
            for w in result.warnings:
                self._log(f"警告：{w}", "warn")
        else:
            self._set_badge("success", "● 成功")

        elapsed = f"{result.elapsed_ms:.0f} ms" if result.elapsed_ms else "—"
        shot = result.screenshot_path.name if result.screenshot_path else "（無）"
        self._log(f"HTTP {result.status}・{elapsed}・截圖 {shot}", "ok")
        if result.screenshot_path:
            self._show_screenshot(result.screenshot_path)

    def _show_screenshot(self, path) -> None:
        """載入 PNG 截圖並等比縮小到預覽區（用內建 PhotoImage，免裝 Pillow）。"""
        try:
            img = tk.PhotoImage(file=str(path))
            factor = max(1,
                         math.ceil(img.width() / PREVIEW_MAX_W),
                         math.ceil(img.height() / PREVIEW_MAX_H))
            if factor > 1:
                img = img.subsample(factor, factor)
            self._preview_image = img  # 保留參考，避免圖片被垃圾回收後消失
            self.preview_label.configure(image=img, text="")
        except Exception as exc:
            self._log(f"截圖預覽載入失敗：{exc}", "warn")

    # ---------------------------------------------------------------- 工具
    def clear_results(self) -> None:
        for label in (self.val_status, self.val_time, self.val_title,
                      self.val_h1, self.val_final):
            label.configure(text="—")
        self._preview_image = None
        self.preview_label.configure(image="", text="（尚無截圖）")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._set_badge("idle", "● 待命")
        self._log("已清除結果。", "info")

    def open_output_dir(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = str(OUTPUT_DIR)
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            self._log(f"已開啟輸出資料夾：{path}", "info")
        except Exception as exc:
            self._log(f"無法開啟資料夾（{exc}），路徑為：{path}", "warn")

    def _set_badge(self, level: str, text: str) -> None:
        style = {"success": "Success", "warning": "Warning", "error": "Error",
                 "run": "Run", "idle": "Idle"}.get(level, "Idle")
        self.badge.configure(text=text, style=f"{style}.Badge.TLabel")

    def _log(self, message: str, tag: str = "muted") -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{stamp}] {message}\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    HealthCheckApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
