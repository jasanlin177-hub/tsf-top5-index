# -*- coding: utf-8 -*-
"""
基準指數（0050／大盤）對比資料。

用途：在網站走勢圖疊上 0050、大盤兩條線，與 TSF 指數比較。
兩者皆採「含息報酬」口徑，與 TSF 指數（追累積型基金淨值＝含息）公平對比：
  - 大盤 TRI：TWSE 發行量加權股價報酬指數（indicesReport/MFI94U，日頻、官方）
  - 0050 TRI：yfinance 0050.TW 還原收盤（auto_adjust＝含息還原）

只需涵蓋 TSF 指數的存續期間（自 20260102 建置起），故不需 2003 起的歷史種子。
維護 data/benchmark_history.csv（date, taiex, etf0050），由每日 cron 更新，
app 讀檔後 rebase 到 100 疊圖。
"""
import os
from datetime import datetime, timedelta

import pandas as pd
import urllib3
import requests

from .config import HISTORY_FILE

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BENCHMARK_FILE = os.path.join(os.path.dirname(HISTORY_FILE), "benchmark_history.csv")
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}


# ─────────────────────────────────────────────
# 抓取來源
# ─────────────────────────────────────────────

def fetch_taiex_tri(start_date, end_date):
    """大盤報酬指數（TWSE MFI94U），逐月抓。回傳 {YYYYMMDD: nav}。"""
    out = {}
    y, m = int(start_date[:4]), int(start_date[4:6])
    ey, em = int(end_date[:4]), int(end_date[4:6])
    while (y, m) <= (ey, em):
        url = ("https://www.twse.com.tw/indicesReport/MFI94U"
               f"?response=json&date={y:04d}{m:02d}01")
        try:
            d = requests.get(url, headers=_HEADERS, timeout=20, verify=False).json()
            for row in d.get("data", []):
                roc = row[0].strip().split("/")               # '115/06/30'
                ymd = f"{int(roc[0])+1911:04d}{int(roc[1]):02d}{int(roc[2]):02d}"
                if start_date <= ymd <= end_date:
                    out[ymd] = float(row[1].replace(",", ""))
        except Exception as e:
            print(f"  [benchmark] TAIEX {y}{m:02d} 失敗: {e}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def fetch_0050_tri(start_date, end_date):
    """0050 含息還原收盤（yfinance）。回傳 {YYYYMMDD: nav}。"""
    import yfinance as yf
    s = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    e = (datetime.strptime(end_date, "%Y%m%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    df = yf.download("0050.TW", start=s, end=e, auto_adjust=True, progress=False)
    if df is None or df.empty:
        print("  [benchmark] 0050 yfinance 無資料")
        return {}
    close = df["Close"]
    if hasattr(close, "columns"):        # 多層欄位（單一 ticker）
        close = close.iloc[:, 0]
    return {d.strftime("%Y%m%d"): float(v)
            for d, v in close.items() if pd.notnull(v)}


# ─────────────────────────────────────────────
# 維護歷史檔
# ─────────────────────────────────────────────

def _index_start_date():
    """TSF 指數建置首日（做為對比起點）。"""
    df = pd.read_csv(HISTORY_FILE)
    return str(int(df["date"].min()))


def update_benchmark_history():
    """
    重抓 TSF 指數存續期間的 0050／大盤 TRI，寫入 benchmark_history.csv。
    區間小（半年～數年），採整段重抓，簡單且不會累積接縫誤差。
    """
    start = _index_start_date()
    end = datetime.now().strftime("%Y%m%d")

    taiex = fetch_taiex_tri(start, end)
    etf = fetch_0050_tri(start, end)
    if not taiex and not etf:
        print("  [benchmark] 兩來源皆無資料，略過")
        return None

    dates = sorted(set(taiex) | set(etf))
    rows = [{"date": d, "taiex": taiex.get(d), "etf0050": etf.get(d)} for d in dates]
    df = pd.DataFrame(rows)
    df.to_csv(BENCHMARK_FILE, index=False, encoding="utf-8-sig")
    print(f"  [benchmark] 已更新 {len(df)} 筆（{start}→{end}）"
          f"　大盤{len(taiex)} 0050:{len(etf)}")
    return df


def load_benchmark():
    """讀 benchmark_history.csv；無則回 None。"""
    if not os.path.exists(BENCHMARK_FILE):
        return None
    df = pd.read_csv(BENCHMARK_FILE)
    df["date"] = df["date"].astype(str)
    return df


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    update_benchmark_history()
