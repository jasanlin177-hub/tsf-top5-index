import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from core.engine import IndexEngine

# ==========================================
# 1. 頁面基礎設定
# ==========================================
st.set_page_config(page_title="TSF-Top5 指數", page_icon="🏆", layout="wide")

# 背景設定
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; }
    h1 { color: #FFFFFF !important; }
    p { color: #AAAAAA; }
    </style>
""", unsafe_allow_html=True)

engine = IndexEngine()

# ==========================================
# 2. 輔助函式：Plotly 看板 (台股紅漲綠跌版)
# ==========================================
def plot_indicator(title, value, suffix="", delta=None, color="#FFD700"):
    """
    繪製指標：支援台股紅漲綠跌邏輯
    """
    fig = go.Figure()
    
    # 建立指標
    fig.add_trace(go.Indicator(
        mode = "number+delta" if delta is not None else "number",
        value = value,
        
        # 標題設定
        title = {
            "text": title, 
            "font": {"size": 24, "color": "white"}
        },
        
        # 主數值設定 (金色/白色)
        number = {
            "suffix": suffix, 
            "font": {"size": 80, "color": color, "family": "Arial Black"}, 
            "valueformat": ".2f"
        },
        
        # 漲跌幅設定 (關鍵修改：紅漲綠跌 + 字體放大)
        delta = {
            "reference": value - delta if delta is not None else None, 
            "relative": True, 
            "valueformat": ".2%",
            "font": {"size": 40, "weight": "bold"}, # 字體放大至 40
            # 台股邏輯：上漲用紅色，下跌用綠色
            "increasing": {"color": "#FF4B4B", "symbol": "▲"}, 
            "decreasing": {"color": "#00FF00", "symbol": "▼"} 
        } if delta is not None else None,
        
        domain = {'x': [0, 1], 'y': [0, 1]}
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=200, 
        margin=dict(l=0, r=0, t=50, b=0)
    )
    return fig

# ==========================================
# 3. 輔助函式：Plotly 表格 (欄寬優化版)
# ==========================================
def plot_table(df):
    """
    繪製表格：調整欄寬比例
    """
    fig = go.Figure(data=[go.Table(
        # 【關鍵修改】調整欄位寬度比例
        # 排名: 0.8 (窄)
        # 名稱: 3.5 (寬)
        # 淨值: 1.5 (中)
        # 權重: 1.2 (窄)
        columnwidth=[0.8, 3.5, 1.5, 1.2],
        
        header=dict(
            values=["<b>排名</b>", "<b>基金名稱</b>", "<b>最新淨值</b>", "<b>權重</b>"],
            line_color='#8B7355',
            fill_color='#C5A572',
            align=['center', 'left', 'right', 'center'], # 對齊方式微調
            font=dict(color='black', size=18)
        ),
        cells=dict(
            values=[df['rank'], df['name'], df['nav'], df['weight']],
            line_color='#444',
            fill_color='#Fdfbf7',
            align=['center', 'left', 'right', 'center'], # 對齊方式微調
            font=dict(color='black', size=16),
            height=40
        ))
    ])
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=350,
        paper_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# ==========================================
# 4. 主程式
# ==========================================
st.title("🏆 台股基金五虎將指數")
st.markdown("**TSF-Top5 Index** | 鎖定最強攻擊手・追求極致超額報酬")

# 數據處理
try:
    df_hist = engine.get_history()
    if not df_hist.empty:
        df_hist = df_hist.rename(columns={'date': 'Date', 'index_value': 'Value'})
        latest_val = df_hist.iloc[-1]['Value']
        delta_val = 0.0
        if len(df_hist) >= 2:
            delta_val = latest_val - df_hist.iloc[-2]['Value']
    else:
        latest_val = 100.0
        delta_val = 0.0
except:
    latest_val = 100.0
    delta_val = 0.0

st.markdown("---")

# --- A. 核心看板 ---
c1, c2, c3, c4 = st.columns(4)

with c1:
    # 指數點位 (有漲跌幅)
    st.plotly_chart(plot_indicator("指數點位", latest_val, delta=delta_val, color="#FFD700"), use_container_width=True)
with c2:
    # YTD (假設數據)
    st.plotly_chart(plot_indicator("今年以來 (YTD)", 13.77, suffix="%", color="white"), use_container_width=True)
with c3:
    # 夏普 (假設數據)
    st.plotly_chart(plot_indicator("夏普值 (Sharpe)", 2.14, color="white"), use_container_width=True)
with c4:
    # MDD (假設數據，注意這裡是負數，通常希望顯示跌幅)
    # 這裡我們手動傳入一個負的 delta 讓它顯示綠色(或紅色)
    st.plotly_chart(plot_indicator("最大回撤 (MDD)", -5.2, suffix="%", color="#FF4B4B"), use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- B. 走勢圖 ---
st.subheader("📈 指數走勢")
if not df_hist.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_hist['Date'], y=df_hist['Value'],
        mode='lines', name='TSF-Top5',
        line=dict(color='#FFD700', width=3)
    ))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=450,
        margin=dict(l=10, r=10, t=30, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- C. 成分股表格 ---
st.subheader("🛡️ 最新成分基金權重 (2026 H1)")

today_str = datetime.now().strftime("%Y%m%d")
_, components_data = engine.calculate_index(today_str)

if isinstance(components_data, list) and len(components_data) > 0:
    cons_data = pd.DataFrame(components_data)
    cons_data = cons_data.rename(columns={'nav': 'nav_val'})
    formatted_data = pd.DataFrame({
        "rank": range(1, len(cons_data) + 1),
        "name": cons_data['name'],
        "nav": cons_data['nav_val'].apply(lambda x: f"{x:.2f}"),
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

# --- D. 管理後台 ---
with st.expander("⚙️ 管理員後台"):
    base_date = st.text_input("輸入基期日期", "20260102")
    if st.button("🚀 執行初始化"):
        success, msg = engine.initialize_index(base_date)
        if success: st.success(msg)
    
    batch_end = st.text_input("補齊至日期", datetime.now().strftime("%Y%m%d"))
    if st.button("🔥 批次補齊"):
        pbar = st.progress(0)
        res = engine.run_batch_update(batch_end, lambda p, m: pbar.progress(p))
        st.success(res)