import urllib3
import time
import random
from bs4 import BeautifulSoup
from .config import SITCA_URL, TARGET_FUNDS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 優先用 curl_cffi（TLS 指紋偽裝，可繞過雲端 IP 封鎖）
# 若未安裝則退回標準 requests
try:
    from curl_cffi.requests import Session as CurlSession
    _USE_CURL = True
except ImportError:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _USE_CURL = False


def _build_requests_session():
    """建立帶 retry 的 requests Session（備援用）"""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=2,
                  status_forcelist=[500, 502, 503, 504],
                  allowed_methods=["GET", "POST"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "Referer": SITCA_URL,
}


class SitcaScraper:
    """負責從公會抓取官方淨值（無狀態，只負責抓）"""

    def __init__(self):
        if _USE_CURL:
            # impersonate="chrome124" 讓 TLS 握手與 Chrome 124 完全相同
            self.session = CurlSession(impersonate="chrome124")
            print("🔐 scraper: 使用 curl_cffi (Chrome TLS 指紋)")
        else:
            self.session = _build_requests_session()
            print("⚠️  scraper: curl_cffi 未安裝，使用 requests 備援")

    def fetch_data(self, date_str: str) -> dict | None:
        """
        輸入: "20260127"
        輸出: {'統一奔騰': 120.5, ...} 或 None
        """
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # 1. 取得隱藏欄位 (ViewState)
                r = self.session.get(
                    SITCA_URL, headers=_HEADERS,
                    verify=False, timeout=60
                )
                soup = BeautifulSoup(r.text, "html.parser")
                payload = {
                    tag.get("name"): tag.get("value", "")
                    for tag in soup.find_all("input")
                    if tag.get("name")
                }

                # 模擬人工操作延遲（降低觸發防爬風險）
                time.sleep(random.uniform(1.5, 3.0))

                # 2. 填入查詢參數
                payload.update({
                    "ctl00$ContentPlaceHolder1$txtQ_Date": date_str,
                    "ctl00$ContentPlaceHolder1$ddlQ_Comid": "",
                    "ctl00$ContentPlaceHolder1$BtnQuery": "查詢",
                })

                # 3. 送出 POST
                r_post = self.session.post(
                    SITCA_URL, data=payload, headers=_HEADERS,
                    verify=False, timeout=60
                )

                # 4. 解析表格
                tables = BeautifulSoup(r_post.text, "html.parser").find_all("table")
                data_table = next(
                    (t for t in tables if "基金名稱" in t.text and "淨值" in t.text),
                    None
                )
                if not data_table:
                    return None  # 假日或查無資料

                results = {}
                for row in data_table.find_all("tr"):
                    text = row.text
                    for name, keywords in TARGET_FUNDS.items():
                        if keywords[0] not in text:
                            continue
                        if len(keywords) > 1 and not any(k in text for k in keywords[1:]):
                            continue
                        cols = row.find_all("td")
                        col_texts = [c.text.strip() for c in cols]
                        for i, val in enumerate(col_texts):
                            if val == "TWD" and i + 1 < len(col_texts):
                                try:
                                    nav = float(col_texts[i + 1].replace(",", ""))
                                    results[name] = nav
                                except (ValueError, IndexError):
                                    pass
                                break
                return results

            except Exception as e:
                print(f"Scraper Error (attempt {attempt + 1}/{max_attempts}): {e}")
                if attempt < max_attempts - 1:
                    wait = (attempt + 1) * 15  # 15s → 30s
                    print(f"⏳ 等待 {wait} 秒後重試...")
                    time.sleep(wait)

        return None
