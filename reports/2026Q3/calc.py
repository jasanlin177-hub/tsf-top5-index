# -*- coding: utf-8 -*-
"""五虎將指數 2026Q3 報告：統計計算 + 走勢圖。資料只讀 data/*.csv，不抓網路。"""
import json, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

t = pd.read_csv("data/tsf_history.csv", dtype={"date": str}).set_index("date")["index_value"]
b = pd.read_csv("data/benchmark_history.csv", dtype={"date": str}, encoding="utf-8-sig").set_index("date")
df = pd.concat([t.rename("tsf"), b["etf0050"].rename("etf"), b["taiex"].rename("tri")], axis=1).dropna()
# 只留三條線都有值的交易日，才能公平比較
assert df.index.is_monotonic_increasing
Q = {"Q1": ("20260102", "20260331"), "Q2": ("20260331", "20260630"), "Q3": ("20260630", "20260930"), "YTD": ("20260102", "20260930")}
out = {"rows": len(df), "first": df.index[0], "last": df.index[-1]}
for q, (s, e) in Q.items():
    w = df.loc[s:e]; r = {}
    for c in df.columns:
        x = w[c]; ret = x.iloc[-1] / x.iloc[0] - 1
        mdd = (x / x.cummax() - 1).min(); d = x.pct_change().dropna()
        r[c] = dict(start=float(x.iloc[0]), end=float(x.iloc[-1]), ret=float(ret) * 100, mdd=float(mdd) * 100,
                    peak_date=x.loc[:(x / x.cummax() - 1).idxmin()].idxmax(), trough_date=(x / x.cummax() - 1).idxmin(),
                    dstd=float(d.std()) * 100, ann=float(d.std() * np.sqrt(252)) * 100, n=int(len(x)))
    out[q] = r
# 個別基金 Q3：基期淨值（2026/06/30，config）vs 2026/09/30 公會淨值
cfg = json.load(open("data/tsf_index_config.json", encoding="utf-8"))["constituents"]
nav930 = {"安聯台灣科技": 810.52, "路博邁台灣5G股票": 98.89, "野村台灣運籌": 488.07, "街口台灣": 201.61, "野村鴻運": 307.84}
funds = {k: dict(base=v["base_nav"], now=nav930[k], ret=(nav930[k] / v["base_nav"] - 1) * 100) for k, v in cfg.items()}
out["funds"] = funds
out["eq_avg"] = float(np.mean([f["ret"] for f in funds.values()]))
out["idx_from_units"] = sum(cfg[k]["units"] * nav930[k] for k in cfg) / 1e6 * 100
json.dump(out, open("reports/2026Q3/stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 走勢圖：1/2 = 100
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei"]; plt.rcParams["axes.unicode_minus"] = False
fig, ax = plt.subplots(figsize=(10, 5.6), dpi=130)
d = pd.to_datetime(df.index)
for c, lab, col, lw in [("tsf", "五虎將指數", "#d62728", 2.6), ("etf", "0050（含息）", "#1f77b4", 1.8), ("tri", "加權報酬指數（含息）", "#7f7f7f", 1.8)]:
    ax.plot(d, df[c] / df[c].iloc[0] * 100, label=lab, color=col, lw=lw)
for q in ["20260331", "20260630"]:
    ax.axvline(pd.to_datetime(q), color="#bbb", ls="--", lw=1)
ax.axvline(pd.to_datetime("20260630"), color="#bbb", ls="--", lw=1)
ymax = ax.get_ylim()[1]
for q, lab in [("20260215", "Q1"), ("20260515", "Q2"), ("20260815", "Q3")]:
    ax.text(pd.to_datetime(q), ymax * 0.97, lab, ha="center", va="top", color="#666", fontsize=12)
ax.set_title("台股基金五虎將指數 vs 0050 vs 大盤（2026/01/02 = 100）", fontsize=14)
ax.set_ylabel("指數（基期 = 100）"); ax.grid(alpha=.25); ax.legend(loc="lower right")
fig.text(0.01, 0.01, "資料：投信投顧公會、證交所；僅列三條線皆有資料的交易日", fontsize=8, color="#666")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig("reports/2026Q3/tsf_2026Q3_chart.png")
print(json.dumps(out, ensure_ascii=False, indent=1))
