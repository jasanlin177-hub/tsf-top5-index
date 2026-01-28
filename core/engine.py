import json
import os
import time
import pandas as pd
from datetime import datetime, timedelta
from .config import INDEX_CONFIG_FILE, HISTORY_FILE
from .scraper import SitcaScraper

class IndexEngine:
    def __init__(self):
        self.scraper = SitcaScraper()
        # 確保 data 資料夾存在
        os.makedirs(os.path.dirname(INDEX_CONFIG_FILE), exist_ok=True)

    def initialize_index(self, base_date):
        """ 初始建倉：計算並儲存權重 """
        navs = self.scraper.fetch_data(base_date)
        if not navs or len(navs) < 5:
            return False, "❌ 無法取得完整 5 檔成分股淨值 (可能是假日或資料源缺漏)。"

        initial_capital = 1_000_000
        allocation = initial_capital / 5
        
        config = {
            "base_date": base_date,
            "base_market_cap": initial_capital,
            "constituents": {}
        }

        for name, nav in navs.items():
            units = allocation / nav
            config["constituents"][name] = {
                "base_nav": nav,
                "units": units
            }

        # 寫入設定檔 (強制 UTF-8)
        with open(INDEX_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            
        # 清空並寫入第一筆歷史
        df = pd.DataFrame([{"date": base_date, "index_value": 100.00}])
        df.to_csv(HISTORY_FILE, index=False)
        return True, "✅ 指數設定檔已建立，基期設為 100.00"

    def calculate_index(self, target_date):
        """ 計算單日指數 (回傳: 指數值, 明細) """
        if not os.path.exists(INDEX_CONFIG_FILE):
            return None, "⚠️ 請先執行初始化"

        # 【修正點 1】這裡原本少了 encoding='utf-8'
        with open(INDEX_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 檢查歷史檔 (簡單快取機制)
        if os.path.exists(HISTORY_FILE):
            df_hist = pd.read_csv(HISTORY_FILE)
            # 強制轉字串比對，避免型別錯誤
            if str(target_date) in df_hist['date'].astype(str).values:
                pass 

        current_navs = self.scraper.fetch_data(target_date)
        if not current_navs:
            # 回傳 None 代表當天沒資料 (假日)
            return None, "No Data" 

        current_market_cap = 0.0
        details = []

        for name, data in config["constituents"].items():
            if name in current_navs:
                nav = current_navs[name]
                mkt_val = data["units"] * nav
                current_market_cap += mkt_val
                
                details.append({
                    "基金名稱": name, 
                    "最新淨值": nav, 
                    "市值貢獻": mkt_val,
                    "權重": "20%" 
                })
            else:
                return None, f"缺值: {name}"

        index_value = (current_market_cap / config["base_market_cap"]) * 100
        self._append_history(target_date, index_value)
        
        return index_value, details

    def run_batch_update(self, end_date_str, progress_callback=None):
        """ 
        一鍵自動補齊功能 
        """
        if not os.path.exists(INDEX_CONFIG_FILE):
            return "請先初始化"
            
        # 【修正點 2】這裡原本少了 encoding='utf-8'，導致錯誤
        with open(INDEX_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            start_date_str = config['base_date']

        # 產生日期範圍
        try:
            start = datetime.strptime(str(start_date_str), "%Y%m%d")
            end = datetime.strptime(str(end_date_str), "%Y%m%d")
        except ValueError:
             return "❌ 日期格式錯誤，請使用 YYYYMMDD"

        date_list = pd.date_range(start=start, end=end).tolist()
        
        total_days = len(date_list)
        success_count = 0
        
        for i, dt in enumerate(date_list):
            d_str = dt.strftime("%Y%m%d")
            
            # 更新前端進度條
            if progress_callback:
                progress_callback(i / total_days, f"正在處理: {d_str}")

            # 呼叫計算
            idx, _ = self.calculate_index(d_str)
            
            if idx:
                success_count += 1
            
            # 避免對公會網站請求過快
            time.sleep(0.3)

        return f"批次處理完成！共掃描 {total_days} 天，成功寫入 {success_count} 筆交易日數據。"

    def _append_history(self, date, value):
        """ 將計算結果存入 CSV """
        new_row = pd.DataFrame([{"date": date, "index_value": value}])
        
        if not os.path.exists(HISTORY_FILE):
            new_row.to_csv(HISTORY_FILE, index=False)
        else:
            df = pd.read_csv(HISTORY_FILE)
            df['date'] = df['date'].astype(str) # 確保日期格式一致
            
            # 只有當日期不存在時才寫入 (避免重複)
            if str(date) not in df['date'].values:
                new_row.to_csv(HISTORY_FILE, mode='a', header=False, index=False)

    def get_history(self):
        """ 讀取歷史資料給前端畫圖 """
        if os.path.exists(HISTORY_FILE):
            return pd.read_csv(HISTORY_FILE).sort_values('date')
        return pd.DataFrame()