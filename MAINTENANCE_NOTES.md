# TSF-Top5 Index 維護筆記（爬蟲與自動更新）

> 本檔記錄系統實際遇過的問題與解法，供日後排錯參考。

---

## 🔴 案例 1：雲端被公會網站封鎖（2026/06）

### 症狀
- GitHub Actions 顯示 ✅ Success，但 `data/tsf_history.csv` 沒有新資料
- Streamlit 網站「最後更新」日期卡住不動
- Actions log 出現：
  ```
  Scraper Error: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
  今日無資料或計算失敗: No Data
  ```
  或
  ```
  ReadTimeoutError: Read timed out. (read timeout=30)
  ```

### 根本原因
SITCA 公會網站會偵測來自雲端機房 IP（GitHub Actions 使用 Microsoft Azure IP 段）的請求並封鎖：
- **ConnectionReset**：直接切斷 TCP 連線
- **ReadTimeout**：接受連線但故意拖延、不回應

⚠️ 重點：**本機（家用/公司 IP）執行正常，只有雲端會被擋**。所以不是程式邏輯壞掉。

### 解法
1. **改用 `curl_cffi`**（核心）— 底層用 libcurl，TLS 握手指紋與真實 Chrome 完全一致，伺服器無法分辨是爬蟲
   - `core/scraper.py` 改用 `from curl_cffi.requests import Session`，初始化加 `impersonate="chrome124"`
   - 失敗時自動退回標準 `requests`（備援）
2. **`requirements.txt` 加入** `curl_cffi>=0.7.0`
3. **timeout 從 30 秒延長至 60 秒**（兩處：GET 與 POST 請求）
4. **加入重試機制**：失敗自動等 15s → 30s 重試共 3 次
5. **隨機延遲**：請求間 `time.sleep(random.uniform(1.5, 3.0))` 模擬人工操作

### 成功標準（Actions log）
```
✅ curl_cffi OK
🔐 scraper: 使用 curl_cffi (Chrome TLS 指紋)
🚀 TSF-Top5 Index: xxx.xx
```

---

## ⚠️ 案例 2：「Re-run all jobs」不會套用新的 workflow（重要陷阱）

### 症狀
明明已經修改並 commit 了 `daily_cron.yml`（例如把安裝指令改成 `pip install -r requirements.txt`），
但點「Re-run all jobs」後，log 跑的還是**舊指令**（例如 `pip install pandas requests beautifulsoup4`）。

### 原因
GitHub Actions 的 **「Re-run all jobs」會用「那次執行當下的舊 workflow 版本」重跑**，
**不會**讀取最新的 `daily_cron.yml`。

### 正確做法（套用最新 workflow）
- ✅ **方法 A**：Actions → 左側點該 workflow 名稱 → 右側「**Run workflow**」按鈕 → 選 main → Run
- ✅ **方法 B**：任何新的 commit / push（會自動用最新版）
- ❌ **不要用**：Re-run all jobs（會跑舊版）

---

## 📌 日常維運須知

| 項目 | 說明 |
|---|---|
| 排程時間 | 每日台灣時間 **19:00**（cron `0 11 * * 1-5`，UTC 11:00），週一至週五 |
| 淨值發布時間 | 公會通常下午 **16:30～17:30** 上架，排程設 19:00 較安全 |
| 假日 No Data | 國定假日 / 颱風假股市休市 → 公會無資料 → log 顯示 `No Data` 為**正常**，會自動略過不破壞歷史 |
| 漏抓補救 | Streamlit 管理後台（密碼 8888）→「智慧補齊」輸入結束日期 → 批次補回 |
| 手動修數據 | 直接編輯 GitHub 上的 `data/tsf_history.csv`，commit 後 Streamlit 幾分鐘自動同步 |
| 權限要求 | Repo Settings → Actions → 必須開啟 **Read and write permissions**，機器人才能寫入 CSV |

---

## 🔍 快速排錯流程圖

```
資料沒更新？
  ├─ 看 Actions 該日執行記錄
  │    ├─ ❌ 紅色失敗 → 看 log 錯誤訊息
  │    │     ├─ ConnectionReset / ReadTimeout → 案例 1（curl_cffi）
  │    │     └─ Permission denied → 開啟 write permissions
  │    └─ ✅ 綠色但資料沒變
  │          ├─ log 有 No Data → 是否假日？（正常）
  │          ├─ log 顯示「curl_cffi 未安裝」→ 案例 1 + 案例 2
  │          └─ Commit step 顯示 nothing to commit → 確認 CSV 是否真的有新值
  └─ 直接看 data/tsf_history.csv 最後一行日期確認
```
