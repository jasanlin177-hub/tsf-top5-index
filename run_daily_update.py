# run_daily_update.py
import os
from datetime import datetime
from core.engine import IndexEngine

def main():
    print("🤖 GitHub Action 機器人啟動...")
    
    # 初始化引擎
    engine = IndexEngine()
    
    # 設定日期：抓取「今天」 (GitHub 主機通常是 UTC 時間，建議轉為台灣時間或直接抓當日)
    # 這裡簡單抓取系統當下日期，稍後在 YAML 設定台灣時間下午執行即可
    today_str = datetime.now().strftime("%Y%m%d")
    
    print(f"📅 正在計算日期: {today_str}")
    
    # 執行計算 (這會自動更新 tsf_history.csv)
    # 若當天無資料 (假日)，engine 會回傳 None，不會寫入錯誤數據
    idx_value, details = engine.calculate_index(today_str)
    
    if idx_value:
        print(f"✅ 計算成功！今日指數: {idx_value:.2f}")
    else:
        print(f"⚠️ 今日無資料或計算失敗: {details}")

    # 更新基準指數對比資料（0050／大盤 TRI）；失敗不影響指數更新
    try:
        from core.benchmark import update_benchmark_history
        update_benchmark_history()
    except Exception as e:
        print(f"⚠️ benchmark 更新失敗（略過，不影響指數）: {e}")

if __name__ == "__main__":
    main()