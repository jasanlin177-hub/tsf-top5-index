import os

# 專案路徑設定
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_CONFIG_FILE = os.path.join(BASE_DIR, 'data', 'tsf_index_config.json') # 儲存成分股權重
HISTORY_FILE = os.path.join(BASE_DIR, 'data', 'tsf_history.csv')           # 儲存每日指數點位 (新增這項以便畫圖)
NAV_HISTORY_FILE = os.path.join(BASE_DIR, 'data', 'universe_nav_history.csv') # 全市場季末淨值歷史庫 (換股回看值)
REBALANCE_ARCHIVE_DIR = os.path.join(BASE_DIR, 'data', 'rebalance_archive')   # 每期換股名單/評分歸檔

# SITCA 爬蟲設定
SITCA_URL = "https://www.sitca.org.tw/ROC/Industry/IN2106.aspx?pid=IN2213_02"

# 成分股預設定義 (短名: 統編)。換股後由 data/tsf_index_config.json 的「統編」覆寫。
# 路博邁取 T累積級別（統編去字尾後為 42532205，fetch_universe 去重已優先 T累積）。
TARGET_FUNDS = {
    "統一奔騰": "73990253",
    "安聯台灣科技": "18480065",
    "路博邁台灣5G": "42532205",
    "野村鴻運": "00968493",
    "野村台灣運籌": "00988316",
}