# -*- coding: utf-8 -*-
"""
Tiger Score 532 評分 + 緩衝換股判定（半年換股引擎核心）。

評分模型（官方規格 V1.0）：
    Score = R1y×50% + R3y×30% + R5y×20%
母體：國內投資股票型(AA1)、TWD 計價（由 universe_scraper 已濾好）。
排除：成立未滿 5 年 → 缺任一回看淨值者自動出局。
緩衝：門檻 = 0.6×σ(Top20)；挑戰者分數 > 衛冕者 + 門檻 才換股。

邏輯移植自 tsf-backtest，改吃本專案資料格式：
    - 統編為字串（與 universe_scraper / nav_history 一致）
    - 當期淨值來自 universe_df，回看淨值來自 history_df
本模組保持「純函式」：只吃 DataFrame、不抓網路。
缺回看期由 rebalance.py 負責補抓後再呼叫。
"""
import pandas as pd

ROBECO_ID = "42532205"  # 路博邁台灣5G


def lookback_ym(review_ym, years):
    """回看期別：同月、往前 N 年。例 (202606, 1) -> 202506。

    ⚠️ 鐵則：審核期 review_ym 月份必須是 06 或 12。
    回看期會落在同月（6/12），那是季末完整資料；3/9 月在來源資料常有缺漏。
    """
    year, month = divmod(int(review_ym), 100)
    if month not in (6, 12):
        raise ValueError(f"審核期必須是 6 月或 12 月，收到 {review_ym}")
    return (year - years) * 100 + month


def _nav_series(history_df, ym):
    """從歷史庫取某期別 {統編: 淨值}（統編為 index）。"""
    sub = history_df[history_df["年月"] == int(ym)]
    return sub.set_index("基金統編")["淨值"]


def missing_lookback_periods(history_df, review_ym):
    """回傳 history 中缺少的回看期別清單（供 rebalance 判斷要不要補抓）。"""
    have = set(history_df["年月"].astype(int).unique())
    need = [lookback_ym(review_ym, n) for n in (1, 3, 5)]
    return [ym for ym in need if ym not in have]


def compute_scores(universe_df, review_ym, history_df):
    """
    計算母體 532 評分。

    輸入：
      universe_df ← universe_scraper.fetch_universe()，當期母體（含當期淨值）
      review_ym   ← 審核期別 int，如 202606
      history_df  ← data/universe_nav_history.csv，提供回看淨值
    輸出：
      DataFrame（index=基金統編），欄位 R1y/R3y/R5y/score/基金名稱/nav_now，
      依 score 由高到低排序。成立未滿 5 年者已排除。
    """
    nav_now = universe_df.set_index("基金統編")["淨值"]
    names = universe_df.set_index("基金統編")["基金名稱"]

    nav_1y = _nav_series(history_df, lookback_ym(review_ym, 1))
    nav_3y = _nav_series(history_df, lookback_ym(review_ym, 3))
    nav_5y = _nav_series(history_df, lookback_ym(review_ym, 5))

    # 四個時間點都有淨值才合格（自動排除成立未滿 5 年）
    eligible = (nav_now.index
                .intersection(nav_1y.index)
                .intersection(nav_3y.index)
                .intersection(nav_5y.index))

    scores = pd.DataFrame({
        "nav_now": nav_now[eligible],
        "nav_1y": nav_1y[eligible],
        "nav_3y": nav_3y[eligible],
        "nav_5y": nav_5y[eligible],
    })
    scores["R1y"] = (scores["nav_now"] / scores["nav_1y"] - 1) * 100
    scores["R3y"] = (scores["nav_now"] / scores["nav_3y"] - 1) * 100
    scores["R5y"] = (scores["nav_now"] / scores["nav_5y"] - 1) * 100
    scores["score"] = scores["R1y"] * 0.5 + scores["R3y"] * 0.3 + scores["R5y"] * 0.2
    scores["基金名稱"] = names.reindex(eligible)

    return scores.sort_values("score", ascending=False)


def select_top5(scores, incumbent_ids=None):
    """
    緩衝換股判定。

    首次建倉（incumbent_ids=None）：直接取前 5，不套緩衝。
    後續審核：門檻 = 0.6×σ(Top20)；由分數最低的衛冕者開始逐一被挑戰，
              挑戰者分數 > 衛冕者 + 門檻 才換；基金消滅則強制補位。

    回傳 (selected_ids:list, threshold:float, changes:list)
    """
    top20 = scores.head(20)
    threshold = 0.6 * float(top20["score"].std())

    def _name(fid):
        return scores.loc[fid, "基金名稱"] if fid in scores.index else str(fid)

    def _sc(fid):
        return round(float(scores.loc[fid, "score"]), 2)

    # 首次建倉
    if incumbent_ids is None:
        selected = scores.head(5).index.tolist()
        changes = [{"action": "初始建倉", "in": fid, "in_name": _name(fid),
                    "in_score": _sc(fid)} for fid in selected]
        return selected, threshold, changes

    valid_incumbents = [f for f in incumbent_ids if f in scores.index]
    missing_incumbents = [f for f in incumbent_ids if f not in scores.index]
    challenger_pool = [f for f in scores.index if f not in incumbent_ids]

    portfolio = set(valid_incumbents)
    used = set()
    changes = []

    # 基金消滅 → 強制補位（取分數最高的可用挑戰者）
    for miss in missing_incumbents:
        for ch in challenger_pool:
            if ch not in used and ch not in portfolio:
                portfolio.add(ch)
                used.add(ch)
                changes.append({"action": "強制補位（基金消滅）",
                                "out": miss, "out_name": str(miss),
                                "in": ch, "in_name": _name(ch), "in_score": _sc(ch)})
                break

    # 緩衝換股：衛冕者由弱到強逐一被挑戰
    valid_sorted = sorted(valid_incumbents,
                          key=lambda f: scores.loc[f, "score"])
    for inc in valid_sorted:
        if inc not in portfolio:
            continue
        inc_score = float(scores.loc[inc, "score"])
        for ch in challenger_pool:
            if ch in used or ch in portfolio:
                continue
            ch_score = float(scores.loc[ch, "score"])
            if ch_score > inc_score + threshold:
                portfolio.discard(inc)
                portfolio.add(ch)
                used.add(ch)
                changes.append({"action": "換股",
                                "out": inc, "out_name": _name(inc),
                                "out_score": round(inc_score, 2),
                                "in": ch, "in_name": _name(ch),
                                "in_score": round(ch_score, 2),
                                "gap": round(ch_score - inc_score, 2),
                                "threshold": round(threshold, 2)})
                break  # 每個衛冕者最多被換一次

    if not changes:
        changes.append({"action": "全員衛冕", "threshold": round(threshold, 2)})

    return list(portfolio), threshold, changes


if __name__ == "__main__":
    # 離線自測：用歷史庫 202512 當「當期」（12月審核，回看 202412/202212/202012），
    # 驗證評分管線能跑、且 5 檔現任在排名中的位置。
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    hist = pd.read_csv("data/universe_nav_history.csv", dtype={"基金統編": str})
    review = 202512
    universe = hist[hist["年月"] == review][
        ["基金統編", "基金名稱", "類型代號", "幣別", "淨值"]].copy()

    print(f"離線自測：review={review}，缺回看期={missing_lookback_periods(hist, review)}")
    sc = compute_scores(universe, review, hist)
    print(f"合格母體：{len(sc)} 檔（已排除未滿5年）\n")
    print("Top 10：")
    print(sc.head(10)[["基金名稱", "R1y", "R3y", "R5y", "score"]].round(2).to_string())

    incb = ["73990253", "18480065", "42532205", "00968493", "00988316"]
    print("\n現任 5 檔目前排名：")
    for fid in incb:
        if fid in sc.index:
            rank = sc.index.get_loc(fid) + 1
            print(f"  #{rank:>3}  {sc.loc[fid,'基金名稱']}  score={sc.loc[fid,'score']:.2f}")
        else:
            print(f"  {fid} 不在合格母體")

    selected, thr, changes = select_top5(sc, incb)
    print(f"\n門檻 0.6σ(Top20) = {thr:.2f}")
    print("換股判定：")
    for c in changes:
        print(" ", c)
