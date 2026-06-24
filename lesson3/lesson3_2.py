"""
梯形計算器 (Trapezoid Calculator)
使用 Python 內建的 tkinter 製作的圖形介面。

公式：
  面積   = (上底 + 下底) × 高 ÷ 2
  中位線 = (上底 + 下底) ÷ 2
  周長   = 上底 + 下底 + 左腰 + 右腰   (需填入兩腰)

執行方式：
  python trapezoid_calculator.py
  或在 uv 專案中：uv run python trapezoid_calculator.py
"""

import tkinter as tk
from tkinter import messagebox, ttk

# 中文字型（Windows 用「微軟正黑體」，找不到時 tkinter 會自動退回預設字型）
FONT = ("Microsoft JhengHei", 11)
TITLE_FONT = ("Microsoft JhengHei", 16, "bold")


class TrapezoidCalculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("梯形計算器")
        self.resizable(False, False)
        self.configure(padx=24, pady=20)

        # 標題
        ttk.Label(self, text="梯形計算器", font=TITLE_FONT).grid(
            row=0, column=0, columnspan=2, pady=(0, 16)
        )

        # 輸入欄位：(key, 顯示文字, 是否必填)
        self.entries = {}
        fields = [
            ("top", "上底 a：", True),
            ("bottom", "下底 b：", True),
            ("height", "高 h：", True),
            ("leg_left", "左腰 c（選填）：", False),
            ("leg_right", "右腰 d（選填）：", False),
        ]
        for i, (key, label_text, _required) in enumerate(fields, start=1):
            ttk.Label(self, text=label_text, font=FONT).grid(
                row=i, column=0, sticky="e", pady=5
            )
            entry = ttk.Entry(self, width=16, font=FONT)
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            self.entries[key] = entry

        # 按鈕列
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=(16, 12))
        ttk.Button(btn_frame, text="計算", command=self.calculate).grid(
            row=0, column=0, padx=6, ipadx=8
        )
        ttk.Button(btn_frame, text="清除", command=self.clear).grid(
            row=0, column=1, padx=6, ipadx=8
        )

        # 結果顯示區（帶外框）
        result_frame = ttk.LabelFrame(self, text="計算結果", padding=12)
        result_frame.grid(row=7, column=0, columnspan=2, sticky="we")
        self.result_var = tk.StringVar(value="請輸入數值後按「計算」")
        ttk.Label(
            result_frame,
            textvariable=self.result_var,
            justify="left",
            font=FONT,
            foreground="#1a5276",
        ).grid(row=0, column=0, sticky="w")

        # 按 Enter 也能計算；開啟後游標停在第一個欄位
        self.bind("<Return>", lambda event: self.calculate())
        self.entries["top"].focus()

    def _read_positive(self, key, name, required=True):
        """讀取欄位並回傳正數；非必填且留空時回傳 None；輸入不合法時丟出 ValueError。"""
        text = self.entries[key].get().strip()
        if not text:
            if required:
                raise ValueError(f"請輸入「{name}」。")
            return None
        try:
            value = float(text)
        except ValueError:
            raise ValueError(f"「{name}」必須是數字（你輸入的是：{text}）。")
        if value <= 0:
            raise ValueError(f"「{name}」必須大於 0。")
        return value

    def calculate(self):
        try:
            a = self._read_positive("top", "上底 a")
            b = self._read_positive("bottom", "下底 b")
            h = self._read_positive("height", "高 h")
            c = self._read_positive("leg_left", "左腰 c", required=False)
            d = self._read_positive("leg_right", "右腰 d", required=False)
        except ValueError as err:
            messagebox.showerror("輸入錯誤", str(err))
            return

        area = (a + b) * h / 2
        midline = (a + b) / 2

        # :g 會自動去掉多餘的小數點與尾零（例如 5.0 -> 5、5.50 -> 5.5）
        lines = [
            "面積 ＝ (上底＋下底) × 高 ÷ 2",
            f"     ＝ ({a:g} ＋ {b:g}) × {h:g} ÷ 2",
            f"     ＝ {area:g}",
            "",
            f"中位線 ＝ (上底＋下底) ÷ 2 ＝ {midline:g}",
        ]

        if c is not None and d is not None:
            perimeter = a + b + c + d
            lines.append(f"周長 ＝ {a:g}＋{b:g}＋{c:g}＋{d:g} ＝ {perimeter:g}")
        else:
            lines.append("（填入左、右腰可一併計算周長）")

        self.result_var.set("\n".join(lines))

    def clear(self):
        for entry in self.entries.values():
            entry.delete(0, tk.END)
        self.result_var.set("請輸入數值後按「計算」")
        self.entries["top"].focus()


if __name__ == "__main__":
    TrapezoidCalculator().mainloop()
