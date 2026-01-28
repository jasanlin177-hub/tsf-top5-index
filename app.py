import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from core.engine import IndexEngine

# ==========================================
# 1. 頁面基礎設定
# ==========================================
st.set_page_config(page_title="TSF-Top5 指數", page_icon="🏆", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0E1117; }
    h1 { color: #FFFFFF !important; }
    p { color: #AAAAAA; }
    </style>
""", unsafe_allow_html=True)

engine = IndexEngine()

# ==========================================
# 2. 輔助函式：Plotly 看板
# ==========================================
def plot_indicator(title, value, suffix="", delta=None, color="#FFD700"):
    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode = "number+delta" if delta is not None else "number",
        value = value,
        title = {"text": title, "font": {"size": 24, "color": "white"}},
        number = {"suffix": suffix, "font": {"size": 80, "color": color, "family": "Arial Black"}, "valueformat": ".2f"},
        delta = {
            "reference": value - delta if delta is not None else None, 
            "relative": True, 
            "valueformat": ".2%",
            "font": {"size": 40, "weight": "bold"}, 
            "increasing": {"color": "#FF4B4B", "symbol": "▲"},
            "decreasing": {"color": "#00FF00", "symbol": "▼"} 
        } if delta is not None else None,
        domain = {'x': [0, 1], 'y': [0, 1]}
    ))
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=200, margin=dict(l=0, r=0, t=50, b=0))
    return fig

# ==========================================
# 3. 輔助函式：Plotly 表格
# ==========================================
def plot_table(df):
    fig = go.Figure(data=[go.Table(
        columnwidth=[0.8, 3.5, 1.5, 1.2],
        header=dict(
            values=["<b>排名</b>", "<b>基金名稱</b>", "<b>最新淨值</b>", "<b>權重</b>"],
            line_color='#8B7355', fill_color='#C5A572', align=['center', 'left', 'right', 'center'], font=dict(color='black', size=18)
        ),
        cells=dict(
            values=[df['rank'], df['name'], df['nav'], df['weight']],
            line_color='#444', fill_color='#Fdfbf7', align=['center', 'left', 'right', 'center'], font=dict(color='black', size=16), height=40
        ))
    ])
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=350, paper_bgcolor='rgba(0,0,0,0)')
    return fig

# ==========================================
# 4. 主程式邏輯
# ==========================================
st.title("🏆 台股基金五虎將指數")
st.markdown("**TSF-Top5 Index** | 鎖定最強攻擊手・追求極致超額報酬")

# --- A. 數據計算核心 ---
try:
    df_hist = engine.get_history()
    
    if not df_hist.empty:
        df_hist = df_hist.rename(columns={'date': 'Date', 'index_value': 'Value'})
        df_hist['Date'] = pd.to_datetime(df_hist['Date'].astype(str), format='%Y%m%d')
        
        latest_val = df_hist.iloc[-1]['Value']
        # 抓取最後更新日期，給管理後台用
        last_updated_date = df_hist.iloc[-1]['Date'].strftime('%Y%m%d')

        delta_val = 0.0
        if len(df_hist) >= 2:
            delta_val = latest_val - df_hist.iloc[-2]['Value']

        # YTD
        start_val = df_hist.iloc[0]['Value'] 
        ytd_val = ((latest_val - start_val) / start_val) * 100

        # MDD
        roll_max = df_hist['Value'].cummax()
        drawdown = (df_hist['Value'] - roll_max) / roll_max
        mdd_val = drawdown.min() * 100

        # Sharpe
        df_hist['daily_ret'] = df_hist['Value'].pct_change()
        if df_hist['daily_ret'].std() != 0:
            sharpe_val = (df_hist['daily_ret'].mean() / df_hist['daily_ret'].std()) * (252**0.5)
        else:
            sharpe_val = 0.0
    else:
        latest_val, delta_val, ytd_val, mdd_val, sharpe_val = 100.0, 0.0, 0.0, 0.0, 0.0
        last_updated_date = "尚無資料"

except Exception as e:
    st.error(f"運算錯誤: {e}")
    latest_val = 100.0
    last_updated_date = "N/A"

st.markdown("---")

# --- B. 核心看板 ---
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.plotly_chart(plot_indicator("指數點位", latest_val, delta=delta_val, color="#FFD700"), use_container_width=True)
with c2:
    ytd_color = "#FF4B4B" if ytd_val >= 0 else "#00FF00"
    st.plotly_chart(plot_indicator("今年以來 (YTD)", ytd_val, suffix="%", color=ytd_color), use_container_width=True)
with c3:
    st.plotly_chart(plot_indicator("夏普值 (Sharpe)", sharpe_val, color="white"), use_container_width=True)
with c4:
    st.plotly_chart(plot_indicator("最大回撤 (MDD)", mdd_val, suffix="%", color="#00FF00"), use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- C. 走勢圖 ---
st.subheader("📈 指數走勢")
if not df_hist.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_hist['Date'], y=df_hist['Value'],
        mode='lines', name='TSF-Top5',
        line=dict(color='#FFD700', width=3)
    ))
    fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=450, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- D. 成分股表格 ---
st.subheader("🛡️ 最新成分基金權重 (2026 H1)")
today_str = datetime.now().strftime("%Y%m%d")
_, components_data = engine.calculate_index(today_str)

if isinstance(components_data, list) and len(components_data) > 0:
    cons_data = pd.DataFrame(components_data)
    cons_data = cons_data.rename(columns={'基金名稱': 'name', '最新淨值': 'nav', '權重': 'weight'})
    formatted_data = pd.DataFrame({
        "rank": range(1, len(cons_data) + 1),
        "name": cons_data['name'],
        "nav": cons_data['nav'].apply(lambda x: f"{float(x):.2f}" if pd.notnull(x) else "--"),
        "weight": "20%"
    })
else:
    formatted_data = pd.DataFrame({
        "rank": [1, 2, 3, 4, 5],
        "name": ["統一奔騰基金 (王者)", "安聯台灣科技基金 (權值)", "路博邁台灣5G (新星)", "野村鴻運基金 (戰將)", "野村台灣運籌 (守門)"],
        "nav": ["--", "--", "--", "--", "--"],
        "weight": ["20%", "20%", "20%", "20%", "20%"]
    })

st.plotly_chart(plot_table(formatted_data), use_container_width=True)

# --- E. 管理後台 (新增狀態顯示) ---
with st.expander("⚙️ 管理員後台"):
    # 顯示目前狀態
    st.info(f"📅 資料庫目前更新至: **{last_updated_date}**")
    
    col_adm1, col_adm2 = st.columns(2)
    
    with col_adm1:
        st.write("#### 1. 重置 (危險)")
        base_date = st.text_input("輸入基期日期", "20260102")
        if st.button("🚀 執行初始化 (清空資料)"):
            success, msg = engine.initialize_index(base_date)
            if success: st.success(msg)
            
    with col_adm2:
        st.write("#### 2. 智慧補齊")
        batch_end = st.text_input("補齊至日期 (End Date)", datetime.now().strftime("%Y%m%d"))
        if st.button("🔥 開始批次補齊"):
            pbar = st.progress(0)
            status_txt = st.empty()
            # 這裡呼叫 engine 的新邏輯，它會自動判斷從哪一天開始
            res = engine.run_batch_update(batch_end, lambda p, m: (pbar.progress(p), status_txt.text(m)))
            pbar.progress(100)
            status_txt.text("Done!")
            st.success(res)