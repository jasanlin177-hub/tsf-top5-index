TSF-Top5 Index 系統架構與維護手冊 
1. 系統概要 (System Overview) 
•	專案名稱：台股基金五虎將指數 (TSF-Top5 Index)
•	系統目標：追蹤特定 5 檔台股主動式基金的績效，每日自動計算指數點位並視覺化呈現。
•	網頁連結：https://tsf-top5-index-k5yfhkjzsgzmuma2sd8a9g.streamlit.app/
•	資料來源：投信投顧公會 (SITCA) 淨值查詢系統。
2. 系統架構 (Architecture)
這部分最重要，要解釋「資料是怎麼流動的」。建議放入這張流程圖：
程式碼片段
graph LR
    A[每日排程 18:00] -->|觸發| B(GitHub Actions)
    B -->|執行腳本| C[run_daily_update.py]
    C -->|爬蟲請求| D[公會網站]
    D -->|回傳淨值| C
    C -->|寫入數據| E[data/tsf_history.csv]
    E -->|Git Commit & Push| F[GitHub Repository]
    F -->|自動同步| G[Streamlit Cloud]
    G -->|前端渲染| H[app.py / Plotly]
核心目錄結構說明
•	.github/workflows/：存放自動化排程設定檔 (daily_cron.yml)。
•	core/：核心邏輯區。
o	engine.py：大腦，負責計算指數、讀寫 CSV、增量更新。
o	scraper.py：手腳，負責去公會網站抓資料。
•	data/：資料庫區。
o	tsf_history.csv：最重要的檔案，儲存歷史指數數據。
o	tsf_index_config.json：儲存 5 檔成分股的初始權重與基期設定。
•	app.py：前端介面，負責讀取 CSV 並畫出 Plotly 圖表。
•	run_daily_update.py：機器人專用的啟動腳本，只做計算不畫圖。
3. 自動化維護 (Automation)
說明 GitHub Actions 是如何運作的，這對除錯很重要。
•	執行時間：每日 UTC 10:00 (台灣時間 18:00)。
•	觸發機制：
1.	定時排程 (cron).
2.	手動觸發 (Workflow Dispatch)。
•	權限設定：必須在 GitHub Settings 中開啟 Read and write permissions，機器人才能寫入 CSV。
4. 常見維護情境 (Maintenance Scenarios)
Q1: 發現指數數據錯誤，如何修正？
1.	進入 GitHub 網頁，找到 data/tsf_history.csv。
2.	點擊右上角「鉛筆」圖示編輯。
3.	直接修改錯誤的數值或刪除錯誤的行。
4.	點擊 Commit changes 存檔。
5.	Streamlit 網頁會在幾分鐘後自動修正。
Q2: 遇到連續假期或颱風假，需要關閉程式嗎？
•	不需要。系統內建防呆機制，若當日爬蟲抓不到淨值（因為公會沒更新），程式會顯示 No Data 並略過存檔，不會破壞歷史資料。
Q3: 半年後 (2026 H2) 要換成分股，怎麼做？
1.	重置基期：
o	在 Streamlit 網頁後台輸入新的基期日期 (例如 20260701)。
o	點擊「執行初始化」。
2.	更新程式碼 (若成分股名單改變)：
o	修改 app.py 中的 cons_data 預設名單。
o	(進階) 修改 core/engine.py 中初始化時的權重分配邏輯。
5. 故障排除 (Troubleshooting)
問題徵兆	可能原因	解決方案
網頁顯示 "Oh no, something went wrong"	通常是 requirements.txt 少了套件	檢查 GitHub 上是否有該檔案，且包含 plotly, pandas 等。
網頁數據沒更新	1. 公會網站尚未更新 
2. GitHub Action 執行失敗	1. 等晚點再看 
2. 去 GitHub "Actions" 分頁查看錯誤日誌 (Log)。
GitHub Action 出現紅叉 (Error)	通常是爬蟲被擋，或是權限不足	1. 檢查 scraper.py 是否需要更新 headers 2. 檢查 Workflow permissions 是否有開 Write 權限。
6. 開發環境設置 (Development)
若換了一台電腦要開發，需要做什麼？
1.	安裝 Python 3.10+。
2.	Clone 專案：git clone https://github.com/jasanlin177-hub/tsf-top5-index
3.	安裝依賴：pip install -r requirements.txt
4.	本地執行：streamlit run app.py

