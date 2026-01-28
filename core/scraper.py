import requests
from bs4 import BeautifulSoup
import urllib3
from .config import SITCA_URL, TARGET_FUNDS # 引用設定

# 關閉 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SitcaScraper:
    """ 負責從公會抓取官方淨值 (無狀態，只負責抓) """
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": SITCA_URL
        }

    def fetch_data(self, date_str):
        """
        輸入: "20260127"
        輸出: Dict {'統一奔騰': 120.5, ...} 或 None
        """
        try:
            # 1. 取得隱藏欄位 (ViewState)
            r = self.session.get(SITCA_URL, headers=self.headers, verify=False)
            soup = BeautifulSoup(r.text, 'html.parser')
            payload = {tag.get('name'): tag.get('value', '') for tag in soup.find_all('input') if tag.get('name')}
            
            # 2. 填入查詢參數
            payload.update({
                'ctl00$ContentPlaceHolder1$txtQ_Date': date_str,
                'ctl00$ContentPlaceHolder1$ddlQ_Comid': '',
                'ctl00$ContentPlaceHolder1$BtnQuery': '查詢'
            })
            
            # 3. 送出 POST
            r_post = self.session.post(SITCA_URL, data=payload, headers=self.headers, verify=False)
            
            # 4. 解析表格
            tables = BeautifulSoup(r_post.text, 'html.parser').find_all('table')
            # 透過特徵尋找正確表格
            data_table = next((t for t in tables if "基金名稱" in t.text and "淨值" in t.text), None)
            
            if not data_table:
                return None # 查無資料 (可能假日)

            results = {}
            for row in data_table.find_all('tr'):
                text = row.text
                for name, keywords in TARGET_FUNDS.items():
                    # 邏輯：必須包含主關鍵字
                    if keywords[0] in text:
                        # 過濾次要關鍵字 (如 "T", "累積")
                        if len(keywords) > 1 and not any(k in text for k in keywords[1:]):
                            continue

                        cols = row.find_all('td')
                        col_texts = [c.text.strip() for c in cols]
                        
                        # 智能定位 "TWD" 右邊那一欄
                        for i, val in enumerate(col_texts):
                            if val == 'TWD' and i+1 < len(col_texts):
                                try:
                                    nav = float(col_texts[i+1].replace(',', '')) # 去除逗號
                                    results[name] = nav
                                except: pass
                                break
            return results

        except Exception as e:
            print(f"Scraper Error: {e}") # 僅在後台印出錯誤以便除錯
            return None