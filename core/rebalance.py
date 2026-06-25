# -*- coding: utf-8 -*-
"""
半年自動換股主流程（半自動・人在迴路）。

每半年（6/30、12/31）依 Tiger Score 532 + 緩衝門檻重選 Top5，
並用「當前總市值 V 平均分 5 份」反推新單位數，使指數接軌不跳空。

用法：
    # 只看建議（不寫入，預設）
    python -m core.rebalance 20260630

    # 確認後真的生效（寫新 config + 歸檔 + 補歷史快照）
    python -m core.rebalance 20260630 --apply

設計原則：
    - 預設 dry-run，--apply 才寫入 → 決策可人工複核、可稽核
    - 等權重再平衡：5 檔各還原 20%，base_market_cap 不變 → 指數連續
    - 資料自給：回看值讀本地歷史庫，缺期自動補抓 IN2106
"""
import os
import re
import sys
import io
import json
import shutil
from datetime import datetime, timedelta

import pandas as pd

from .config import (INDEX_CONFIG_FILE, NAV_HISTORY_FILE, REBALANCE_ARCHIVE_DIR)
from .universe_scraper import fetch_universe, _normalize_id
from .scoring import compute_scores, select_top5, missing_lookback_periods, lookback_ym

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


# ─────────────────────────────────────────────
# 工具
# ─────────────────────────────────────────────

def next_period_label(review_ym):
    """審核期 → 生效期標籤。202606→2026H2、202612→2027H1。"""
    year, month = divmod(int(review_ym), 100)
    if month == 6:
        return f"{year}H2"
    if month == 12:
        return f"{year + 1}H1"
    raise ValueError(f"審核期必須是 6 月或 12 月：{review_ym}")


def short_name(fund_name):
    """由全名產生顯示短名：取「基金」前段，去掉級別/類型雜訊。"""
    name = fund_name.split("基金")[0] if "基金" in fund_name else fund_name
    name = re.sub(r"[-－].*$", "", name).strip()  # 去掉 -A類型 等後綴
    return name if len(name) >= 2 else fund_name


def load_history():
    return pd.read_csv(NAV_HISTORY_FILE, dtype={"基金統編": str})


def _last_trading_date(period_ym):
    """某季末月內，由月底往前找最近一個有資料的交易日（回 fetch_universe 結果）。"""
    year, month = divmod(int(period_ym), 100)
    last = (datetime(year + 1, 1, 1) - timedelta(days=1)) if month == 12 \
        else (datetime(year, month + 1, 1) - timedelta(days=1))
    for delta in range(15):
        d = (last - timedelta(days=delta)).strftime("%Y%m%d")
        uni = fetch_universe(d)
        if uni is not None and not uni.empty:
            return d, uni
    return None, None


def backfill_lookback(history, review_ym):
    """補齊 history 中缺少的回看期（抓 IN2106 歷史日 → append）。回傳更新後 history。"""
    missing = missing_lookback_periods(history, review_ym)
    if not missing:
        return history
    print(f"⚠️ 歷史庫缺回看期 {missing}，嘗試補抓…")
    new_parts = []
    for ym in missing:
        d, uni = _last_trading_date(ym)
        if uni is None:
            print(f"  ✗ {ym} 補抓失敗（查無交易日資料）")
            continue
        uni = uni.copy()
        uni.insert(0, "年月", int(ym))
        new_parts.append(uni[["年月", "基金統編", "基金名稱", "類型代號", "幣別", "淨值"]])
        print(f"  ✓ {ym} 補抓 {len(uni)} 檔（採 {d}）")
    if new_parts:
        history = pd.concat([history] + new_parts, ignore_index=True)
        history.to_csv(NAV_HISTORY_FILE, index=False, encoding="utf-8-sig")
    return history


# ─────────────────────────────────────────────
# 建議（不寫入）
# ─────────────────────────────────────────────

def propose(review_date_str):
    """
    產生換股建議。回傳 dict：
      review_ym / universe / scores / incumbents / selected / threshold / changes
    """
    review_ym = int(review_date_str[:6])

    print(f"\n=== 半年換股建議　審核日 {review_date_str}（期別 {review_ym}）===\n")

    universe = fetch_universe(review_date_str)
    if universe is None or universe.empty:
        raise SystemExit("✗ 審核日查無母體資料（假日或淨值未發布）")

    history = load_history()
    history = backfill_lookback(history, review_ym)

    # 現任成分股統編（正規化）
    with open(INDEX_CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    incumbents = {name: _normalize_id(d["統編"])
                  for name, d in config["constituents"].items()}
    incumbent_ids = list(incumbents.values())

    scores = compute_scores(universe, review_ym, history)
    selected, threshold, changes = select_top5(scores, incumbent_ids)
    selected = sorted(selected, key=lambda f: -scores.loc[f, "score"])

    # ── 印建議 ──
    print(f"合格母體 {len(scores)} 檔　|　門檻 0.6σ(Top20) = {threshold:.2f}\n")
    print("現任 5 檔現況：")
    for name, fid in incumbents.items():
        if fid in scores.index:
            rank = scores.index.get_loc(fid) + 1
            print(f"  #{rank:>3}  {name:10s} score={scores.loc[fid,'score']:.2f}")
        else:
            print(f"  ✗ {name:10s} 已不在合格母體（清算/改名/未滿5年）")

    print("\n換股判定：")
    for c in changes:
        if c["action"] == "全員衛冕":
            print(f"  ✅ 全員衛冕（無人跨過門檻 {c['threshold']}）")
        elif c["action"] == "換股":
            print(f"  🔄 換出 {c['out_name']}({c['out_score']}) "
                  f"→ 換入 {c['in_name']}({c['in_score']})  "
                  f"領先 {c['gap']} > 門檻 {c['threshold']}")
        elif c["action"].startswith("強制補位"):
            print(f"  ⛑️ {c['action']}：補入 {c['in_name']}({c['in_score']})")
        else:
            print(f"  ➕ {c['action']}：{c.get('in_name')}({c.get('in_score')})")

    print(f"\n下期建議名單（{next_period_label(review_ym)}）：")
    for i, fid in enumerate(selected, 1):
        tag = "（續抱）" if fid in incumbent_ids else "（新進）⭐"
        print(f"  {i}. {scores.loc[fid,'基金名稱']}　score={scores.loc[fid,'score']:.2f} {tag}")

    return {"review_ym": review_ym, "review_date": review_date_str,
            "universe": universe, "scores": scores, "config": config,
            "incumbent_ids": incumbent_ids, "selected": selected,
            "threshold": threshold, "changes": changes}


# ─────────────────────────────────────────────
# 生效（寫入）
# ─────────────────────────────────────────────

def apply(proposal):
    """依建議寫新 config（接軌算 units）+ 歸檔本期 + 補當期快照進歷史庫。"""
    review_ym = proposal["review_ym"]
    review_date = proposal["review_date"]
    universe = proposal["universe"]
    scores = proposal["scores"]
    old_config = proposal["config"]
    selected = proposal["selected"]
    new_period = next_period_label(review_ym)

    nav_by_id = universe.set_index("基金統編")["淨值"].to_dict()

    # 1. 當前總市值 V（用舊 units × 當日淨值）
    V = 0.0
    for name, d in old_config["constituents"].items():
        fid = _normalize_id(d["統編"])
        if fid not in nav_by_id:
            raise SystemExit(f"✗ 現任 {name}({fid}) 在當日母體缺值，無法接軌")
        V += d["units"] * nav_by_id[fid]
    print(f"\n接軌：當前總市值 V = {V:,.2f}　→ 每檔 V/5 = {V/5:,.2f}")

    # 2. 等權重再平衡：每檔還原 20%，反推新 units，base_nav 重設為當日淨值
    base_market_cap = old_config["base_market_cap"]  # 不變 → 指數連續
    new_constituents = {}
    used_names = set()
    for fid in selected:
        full = scores.loc[fid, "基金名稱"]
        sn = short_name(full)
        while sn in used_names:
            sn += "＊"
        used_names.add(sn)
        nav = nav_by_id[fid]
        new_constituents[sn] = {
            "統編": fid,
            "base_nav": round(float(nav), 4),
            "units": round((V / 5) / nav, 6),
        }

    new_config = {
        "period": new_period,
        "base_date": review_date,
        "base_market_cap": base_market_cap,
        "constituents": new_constituents,
    }

    # 3. 歸檔舊期
    os.makedirs(REBALANCE_ARCHIVE_DIR, exist_ok=True)
    old_period = old_config.get("period", "unknown")
    shutil.copy(INDEX_CONFIG_FILE,
                os.path.join(REBALANCE_ARCHIVE_DIR, f"config_{old_period}.json"))
    scores.reset_index().to_csv(
        os.path.join(REBALANCE_ARCHIVE_DIR, f"scores_{review_ym}.csv"),
        index=False, encoding="utf-8-sig")
    with open(os.path.join(REBALANCE_ARCHIVE_DIR, f"changes_{review_ym}.json"),
              "w", encoding="utf-8") as f:
        json.dump({"review_ym": review_ym, "new_period": new_period,
                   "threshold": proposal["threshold"],
                   "changes": proposal["changes"],
                   "selected": [{"統編": fid,
                                 "基金名稱": scores.loc[fid, "基金名稱"],
                                 "score": round(float(scores.loc[fid, "score"]), 2)}
                                for fid in selected]},
                  f, ensure_ascii=False, indent=2)

    # 4. 寫新 config（生效）
    with open(INDEX_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(new_config, f, ensure_ascii=False, indent=4)

    # 5. 補當期全市場快照進歷史庫（供未來回看）
    history = load_history()
    if review_ym not in set(history["年月"].astype(int)):
        snap = universe.copy()
        snap.insert(0, "年月", review_ym)
        snap = snap[["年月", "基金統編", "基金名稱", "類型代號", "幣別", "淨值"]]
        pd.concat([history, snap], ignore_index=True).to_csv(
            NAV_HISTORY_FILE, index=False, encoding="utf-8-sig")

    print(f"\n✅ 已生效：{new_period}（base_date={review_date}，指數接軌不跳空）")
    print(f"   歸檔於 {REBALANCE_ARCHIVE_DIR}")
    print("   新成分股：")
    for sn, d in new_constituents.items():
        print(f"     {sn}　統編{d['統編']}　base_nav={d['base_nav']}　units={d['units']}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_apply = "--apply" in sys.argv
    if not args:
        print("用法：python -m core.rebalance YYYYMMDD [--apply]")
        return
    review_date = args[0]
    proposal = propose(review_date)
    if do_apply:
        apply(proposal)
    else:
        print("\n（此為建議模式，未寫入。確認無誤後加 --apply 生效）")


if __name__ == "__main__":
    main()
