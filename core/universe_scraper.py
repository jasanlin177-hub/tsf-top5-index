# -*- coding: utf-8 -*-
"""
全市場母體爬蟲（半年換股用）。

對公會 IN2106「單日淨值查詢」抓某一交易日「全市場」所有基金淨值，
解析後濾出官方規格的母體：國內投資股票型(AA1) + 新台幣計價(TWD)，
並套用同統編去重規則（路博邁只留 T累積、排除配息/月配/機構級別）。

回傳乾淨母體 DataFrame，交給 scoring.py 算 532 分。

與 core/scraper.py 的差別：
  - scraper.py：指數日更用，只抓寫死的 5 檔當期淨值。
  - 本檔：     半年選股用，抓全市場讓引擎重新選 5 檔。
"""
import re
import time
import random
import pandas as pd
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# IN2106 單日淨值查詢（與 core/config.py 的 SITCA_URL 同一頁）
IN2106_URL = "https://www.sitca.org.tw/ROC/Industry/IN2106.aspx?pid=IN2213_02"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;"
               "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "Referer": IN2106_URL,
}

# 母體規格
EQUITY_TYPE_CODE = "AA1"   # 國內投資股票型（開放式）
BASE_CURRENCY = "TWD"      # 排除外幣計價級別


def _make_session():
    """優先 curl_cffi（Chrome124 TLS 指紋偽裝，繞雲端 IP 封鎖），失敗退回帶 retry 的 requests。"""
    try:
        from curl_cffi.requests import Session as CurlSession
        return CurlSession(impersonate="chrome124", verify=False), "curl_cffi"
    except Exception:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        s = requests.Session()
        s.verify = False
        retry = Retry(total=3, backoff_factor=2,
                      status_forcelist=[500, 502, 503, 504],
                      allowed_methods=["GET", "POST"])
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s, "requests"


def _normalize_id(raw_id):
    """
    統編正規化：去掉級別字尾字母，回傳主統編（純數字字串）。
    例：'42532205A' -> '42532205'、'00968493' -> '00968493'
    """
    digits = re.sub(r"\D", "", str(raw_id))
    return digits


# IN2106 資料表固定 10 欄，順序穩定：
#   0類型代號 1公司代號 2公司名稱 3受益憑證代號 4基金統編 5基金名稱 6幣別 7淨值 8前一日淨值 9漲跌
N_COLS = 10
IDX = {"類型代號": 0, "基金統編": 4, "基金名稱": 5, "幣別": 6, "淨值": 7}
# 類型代號樣式：1~3 個大寫字母後可接數字（AA1 / AH22 / AJ2 / T...）
_TYPE_RE = re.compile(r"^[A-Z]{1,3}\d*$")


def _find_data_table(soup):
    """找出含最多資料列（每列 10 欄）的資料表。"""
    best, best_trs, best_n = None, None, 0
    for table in soup.find_all("table"):
        if "基金統編" not in table.text:
            continue
        trs = table.find_all("tr")
        n = sum(1 for tr in trs
                if len(tr.find_all(["th", "td"], recursive=False)) == N_COLS)
        if n > best_n:
            best, best_trs, best_n = table, trs, n
    return best, best_trs, best_n


def fetch_universe(date_str):
    """
    抓某交易日全市場母體。

    輸入：date_str，格式 'YYYYMMDD'（如 '20260630'）
    輸出：DataFrame，欄位 = 基金統編 / 基金名稱 / 類型代號 / 幣別 / 淨值
          （已濾 AA1+TWD、已同統編去重）；查無資料回傳 None。
    """
    session, engine = _make_session()
    print(f"🔐 使用 {engine} 查詢 IN2106 全市場 {date_str}")

    # 抓頁面（帶 retry：雲端 IP 偶發被擋/逾時時重試）
    soup2 = None
    for attempt in range(3):
        try:
            # 1. 取得 ViewState
            r = session.get(IN2106_URL, headers=HEADERS, verify=False, timeout=60)
            soup = BeautifulSoup(r.text, "html.parser")
            payload = {t.get("name"): t.get("value", "")
                       for t in soup.find_all("input") if t.get("name")}

            time.sleep(random.uniform(1.5, 3.0))  # 模擬人工延遲，降低防爬風險

            # 2. 查詢全市場（公司留空）
            payload.update({
                "ctl00$ContentPlaceHolder1$txtQ_Date": date_str,
                "ctl00$ContentPlaceHolder1$ddlQ_Comid": "",
                "ctl00$ContentPlaceHolder1$BtnQuery": "查詢",
            })
            rp = session.post(IN2106_URL, data=payload, headers=HEADERS,
                              verify=False, timeout=60)
            soup2 = BeautifulSoup(rp.text, "html.parser")
            break
        except Exception as e:
            print(f"  Scraper Error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep((attempt + 1) * 15)
    if soup2 is None:
        return None

    # 3. 定位資料表
    table, trs, n_data = _find_data_table(soup2)
    if table is None or n_data == 0:
        print("  ✗ 找不到資料表（可能假日/淨值未發布）")
        return None

    # 4. 解析資料列（固定 10 欄）
    rows = []
    for tr in trs:
        cells = tr.find_all(["th", "td"], recursive=False)
        if len(cells) != N_COLS:
            continue
        c = [x.get_text(" ", strip=True) for x in cells]
        type_code = c[IDX["類型代號"]].strip()
        if not _TYPE_RE.match(type_code):   # 跳過表頭/雜訊列
            continue
        name = c[IDX["基金名稱"]].strip()
        if not name or len(name) < 2:
            continue
        nav_str = c[IDX["淨值"]].replace(",", "").strip()
        try:
            nav = float(nav_str)
        except ValueError:
            continue
        if nav <= 0:
            continue
        rows.append({
            "基金統編": _normalize_id(c[IDX["基金統編"]]),
            "基金名稱": name,
            "類型代號": type_code,
            "幣別": c[IDX["幣別"]].strip(),
            "淨值": nav,
        })

    if not rows:
        print("  ✗ 解析到 0 筆")
        return None

    df = pd.DataFrame(rows)
    total = len(df)

    # 5. 濾母體：AA1 + TWD
    df = df[(df["類型代號"] == EQUITY_TYPE_CODE) & (df["幣別"] == BASE_CURRENCY)].copy()

    # 6. 同統編去重：排除配息/月配/機構級別，路博邁只留 T累積
    df["_prio"] = (
        df["基金名稱"].str.contains("月配|配息", na=False).astype(int) * 4
        + df["基金名稱"].str.contains("I類|I級別|機構", na=False).astype(int) * 2
        + df["基金名稱"].str.contains("N累積|N級別", na=False).astype(int)
    )
    df = df.sort_values(["基金統編", "_prio"]).drop_duplicates("基金統編", keep="first")
    df = df.drop(columns="_prio").reset_index(drop=True)

    print(f"  ✓ 全市場 {total} 筆 → 母體(AA1/TWD/去重) {len(df)} 檔")
    return df


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    date = sys.argv[1] if len(sys.argv) > 1 else "20260624"
    uni = fetch_universe(date)
    if uni is not None:
        print(uni.to_string())
