import os

# 專案路徑設定
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_CONFIG_FILE = os.path.join(BASE_DIR, 'data', 'tsf_index_config.json') # 儲存成分股權重
HISTORY_FILE = os.path.join(BASE_DIR, 'data', 'tsf_history.csv')           # 儲存每日指數點位 (新增這項以便畫圖)

# SITCA 爬蟲設定
SITCA_URL = "https://www.sitca.org.tw/ROC/Industry/IN2106.aspx?pid=IN2213_02"

# 成分股定義 (Name: [Keywords])
TARGET_FUNDS = {
    "統一奔騰": ["統一奔騰基金"],
    "安聯台灣科技": ["安聯台灣科技基金"],
    "路博邁台灣5G": ["路博邁台灣5G", "T", "累積"], 
    "野村鴻運": ["野村鴻運基金"],
    "野村台灣運籌": ["野村台灣運籌基金"]
}