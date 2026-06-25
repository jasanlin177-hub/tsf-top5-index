# -*- coding: utf-8 -*-
"""
一次性：把 tsf-backtest 的季末淨值匯成本地歷史庫種子檔。

來源：../tsf-backtest/sitca_fund_equity.csv（2007–2026 月淨值）
輸出：data/universe_nav_history.csv
      schema 與 core/universe_scraper.fetch_universe 對齊（多一欄「年月」）：
        年月 / 基金統編 / 基金名稱 / 類型代號 / 幣別 / 淨值

清洗規則沿用 tsf-backtest load_sitca：
  - 只留季末月（3/6/9/12）
  - 淨值需 > 0
  - 計價幣別 = TWD（空值視為 TWD）
  - 統編正規化為純數字（去級別字尾）
  - 路博邁(42532205) 只留 T累積級別
  - 同(年月,統編)去重：配息/月配/機構級別降權

跑完即產生種子；之後每次換股由 rebalance 增量 append 當期快照。
"""
import os
import sys
import io
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from core.universe_scraper import _normalize_id

SRC = os.path.join("..", "tsf-backtest", "sitca_fund_equity.csv")
OUT = os.path.join("data", "universe_nav_history.csv")
ROBECO_ID = "42532205"  # 路博邁台灣5G，只留 T累積


def main():
    if not os.path.exists(SRC):
        print(f"✗ 找不到來源：{os.path.abspath(SRC)}")
        return

    df = pd.read_csv(SRC, encoding="utf-8-sig", low_memory=False)
    print(f"原始：{len(df)} 筆")

    # NAV 欄名對齊（新檔為 '單位淨值'）
    nav_col = "單位淨值" if "單位淨值" in df.columns else "單位淨值(台幣)"

    # 只留季末月
    df["年月"] = df["年月"].astype(int)
    df = df[(df["年月"] % 100).isin([3, 6, 9, 12])].copy()

    # 淨值數值化 + 去零空
    df[nav_col] = pd.to_numeric(df[nav_col], errors="coerce")
    df = df[df[nav_col] > 0].copy()

    # 幣別：空值視為 TWD，僅留 TWD
    df["計價幣別"] = df["計價幣別"].fillna("TWD")
    df = df[df["計價幣別"] == "TWD"].copy()

    # 統編正規化
    df["基金統編"] = df["基金統編"].map(_normalize_id)
    df = df[df["基金統編"].str.len().between(6, 10)].copy()

    # 路博邁只留 T累積
    rob_mask = df["基金統編"] == ROBECO_ID
    rob_keep = df[rob_mask & df["基金名稱"].str.contains("T累積", na=False)]
    df = pd.concat([df[~rob_mask], rob_keep], ignore_index=True)

    # 同(年月,統編)去重
    df["_prio"] = (
        df["基金名稱"].str.contains("月配|配息", na=False).astype(int) * 4
        + df["基金名稱"].str.contains("I類|I級別|機構", na=False).astype(int) * 2
        + df["基金名稱"].str.contains("N累積|N級別", na=False).astype(int)
    )
    df = df.sort_values(["年月", "基金統編", "_prio"]).drop_duplicates(
        ["年月", "基金統編"], keep="first")

    # 整理輸出欄位
    out = pd.DataFrame({
        "年月": df["年月"].astype(int),
        "基金統編": df["基金統編"],
        "基金名稱": df["基金名稱"],
        "類型代號": df["類型代號"] if "類型代號" in df.columns else "",
        "幣別": df["計價幣別"],
        "淨值": df[nav_col],
    }).sort_values(["年月", "基金統編"]).reset_index(drop=True)

    os.makedirs("data", exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"✓ 種子完成：{OUT}")
    print(f"  共 {len(out)} 筆，{out['年月'].nunique()} 個期別，"
          f"範圍 {out['年月'].min()}–{out['年月'].max()}")
    print("\n各 6 月底期別母體檔數（抽樣）：")
    jun = out[out["年月"] % 100 == 6]
    print(jun.groupby("年月").size().tail(8).to_string())


if __name__ == "__main__":
    main()
