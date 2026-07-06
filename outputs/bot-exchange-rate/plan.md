# Task

前往台灣銀行牌告匯率頁面，擷取今日美元兌台幣的買入與賣出價。

# Critical Points

- [x] CP1: 成功開啟台灣銀行牌告匯率頁面 (https://rate.bot.com.tw/xrt?Lang=zh-TW) — `final_execution_1_open_page.png` shows BOT頁面; ARIA snapshot confirms heading "2026/07/06 本行非營業時間牌告匯率"
- [x] CP2: 頁面中顯示美元 (USD) 的現金買入匯率 (本行買入) — `final_execution_3_buying_rate.png`; log line `step 2 action: USD cash buying rate (本行買入): 31.625`
- [x] CP3: 頁面中顯示美元 (USD) 的現金賣出匯率 (本行賣出) — `final_execution_4_selling_rate.png`; log line `step 3 action: USD cash selling rate (本行賣出): 32.295`
- [x] CP4: 記錄並輸出今日美元買入與賣出價格 — `final_script_log.txt` contains `FINAL_RESPONSE: 美元 (USD) 現金買入: 31.625, 現金賣出: 32.295`
