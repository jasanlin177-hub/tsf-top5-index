import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import base64
from datetime import datetime
from core.engine import IndexEngine

# ==========================================
# 1. 頁面基礎設定
# ==========================================
st.set_page_config(
    page_title="TSF-Top5 Index | 台股基金五虎將指數",
    page_icon="🐯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── 五虎將色系（對應 LOGO 彩虹條紋）──
FUND_COLORS = [
    "#FF6B35",  # 1 橙 — 統一奔騰
    "#3498DB",  # 2 藍 — 安聯台灣科技
    "#2ECC71",  # 3 綠 — 路博邁台灣5G
    "#E74C3C",  # 4 紅 — 野村鴻運
    "#9B59B6",  # 5 紫 — 野村台灣運籌
]
GOLD    = "#FFD700"
BG_MAIN = "#0A0E1A"
BG_CARD = "#141827"

# ==========================================
# 2. CSS 全域樣式
# ==========================================
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Noto+Sans+TC:wght@400;700;900&display=swap');

/* ─── 全域背景 ─── */
.stApp {{ background-color: {BG_MAIN}; font-family: 'Noto Sans TC', sans-serif; }}
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding-top: 0 !important; }}

/* ─── 頁首橫幅 ─── */
.tsf-header {{
    background: linear-gradient(135deg, #0A0E1A 0%, #12192D 60%, #0A0E1A 100%);
    border-bottom: 3px solid transparent;
    border-image: linear-gradient(90deg, #FF6B35, #FFD700, #2ECC71, #3498DB, #9B59B6) 1;
    padding: 20px 32px 18px;
    display: flex;
    align-items: center;
    gap: 24px;
    margin-bottom: 0;
}}
.tsf-header img {{
    height: 88px;
    object-fit: contain;
    filter: drop-shadow(0 0 12px rgba(255,215,0,0.3));
}}
.tsf-header-logo-placeholder {{
    width: 88px;
    height: 88px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 3.5rem;
    filter: drop-shadow(0 0 8px rgba(255,215,0,0.4));
}}
.tsf-header-text h1 {{
    font-family: 'Orbitron', 'Noto Sans TC', sans-serif !important;
    font-size: 2.1rem !important;
    font-weight: 900 !important;
    background: linear-gradient(90deg, #FFD700 0%, #FF8C00 50%, #FF6B35 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 4px !important;
    line-height: 1.15 !important;
    text-shadow: none;
}}
.tsf-header-text p {{
    color: #8899BB;
    font-size: 0.95rem;
    margin: 0;
    letter-spacing: 2px;
}}
.tsf-header-right {{
    margin-left: auto;
    text-align: right;
}}
.tsf-header-right .updated-label {{
    color: #556080;
    font-size: 0.75rem;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
.tsf-header-right .updated-date {{
    color: {GOLD};
    font-family: 'Orbitron', monospace;
    font-size: 1rem;
    font-weight: 700;
}}

/* ─── 彩虹分隔線 ─── */
.rainbow-hr {{
    height: 3px;
    background: linear-gradient(90deg, #FF6B35, #FFD700, #2ECC71, #3498DB, #9B59B6);
    border: none;
    border-radius: 2px;
    margin: 0 0 28px;
}}

/* ─── 區塊標題 ─── */
.section-title {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 28px 0 16px;
}}
.section-icon {{ font-size: 1.4rem; }}
.section-title h2 {{
    font-size: 1.2rem !important;
    font-weight: 700 !important;
    color: #FFFFFF !important;
    margin: 0 !important;
    letter-spacing: 1px;
    text-shadow: none !important;
}}
.section-line {{
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, #2A3050 0%, transparent 100%);
}}

/* ─── 指標卡片 ─── */
.metric-card {{
    background: {BG_CARD};
    border-radius: 16px;
    padding: 22px 24px 18px;
    border: 1px solid #1E2840;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    position: relative;
    overflow: hidden;
    height: 140px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: box-shadow 0.2s, transform 0.2s;
}}
.metric-card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.7);
}}
.metric-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 16px 16px 0 0;
}}
.metric-card::after {{
    content: '';
    position: absolute;
    right: -20px; top: -20px;
    width: 100px; height: 100px;
    border-radius: 50%;
    opacity: 0.04;
}}
.card-gold::before   {{ background: linear-gradient(90deg, #FFD700, #FF8C00); }}
.card-gold::after    {{ background: #FFD700; }}
.card-red::before    {{ background: linear-gradient(90deg, #FF4B4B, #FF6B35); }}
.card-red::after     {{ background: #FF4B4B; }}
.card-white::before  {{ background: linear-gradient(90deg, #FFFFFF, #8899BB); }}
.card-white::after   {{ background: #FFFFFF; }}
.card-green::before  {{ background: linear-gradient(90deg, #00C853, #2ECC71); }}
.card-green::after   {{ background: #00C853; }}

.metric-label {{
    color: #6677AA;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 1.8px;
    text-transform: uppercase;
}}
.metric-value {{
    font-family: 'Orbitron', monospace;
    font-size: 2.4rem;
    font-weight: 700;
    line-height: 1;
    margin: 8px 0 6px;
}}
.metric-badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 700;
    margin-right: 4px;
}}
.badge-up   {{ background: rgba(255,75,75,0.15);  color: #FF4B4B; }}
.badge-down {{ background: rgba(0,200,83,0.15);   color: #00C853; }}
.badge-neu  {{ background: rgba(255,215,0,0.12);  color: #FFD700; }}

/* ─── 成分基金列 ─── */
.fund-row {{
    background: {BG_CARD};
    border-radius: 14px;
    padding: 14px 20px;
    margin-bottom: 10px;
    display: grid;
    grid-template-columns: 48px 1fr 120px 120px 70px;
    align-items: center;
    border: 1px solid #1E2840;
    border-left: 4px solid var(--fund-color);
    transition: background 0.18s, box-shadow 0.18s;
}}
.fund-row:hover {{
    background: #1A2035;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}}
.fund-rank {{
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: var(--fund-color);
    color: #000;
    font-weight: 900;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 10px color-mix(in srgb, var(--fund-color) 60%, transparent);
}}
.fund-name {{
    color: #FFFFFF;
    font-weight: 700;
    font-size: 1rem;
    padding-right: 12px;
}}
.fund-nav {{
    color: #DDEEFF;
    font-family: 'Orbitron', monospace;
    font-size: 1rem;
    font-weight: 600;
    text-align: right;
    padding-right: 16px;
}}
.fund-pct {{
    font-weight: 700;
    font-size: 0.95rem;
    text-align: right;
    padding-right: 16px;
}}
.fund-pct.up   {{ color: #FF4B4B; }}
.fund-pct.down {{ color: #00C853; }}
.fund-pct.neu  {{ color: #8899BB; }}
.fund-weight {{
    background: rgba(255,215,0,0.1);
    color: {GOLD};
    border-radius: 20px;
    padding: 4px 0;
    font-size: 0.85rem;
    font-weight: 700;
    text-align: center;
    border: 1px solid rgba(255,215,0,0.2);
}}

/* ─── 表格欄位標頭 ─── */
.fund-header {{
    display: grid;
    grid-template-columns: 48px 1fr 120px 120px 70px;
    align-items: center;
    padding: 8px 20px 12px;
    color: #556080;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}}
.fund-header span:nth-child(n+3) {{ text-align: right; padding-right: 16px; }}
.fund-header span:last-child     {{ text-align: center; padding-right: 0; }}

/* ─── 下載按鈕 ─── */
div.stDownloadButton > button {{
    background: linear-gradient(135deg, {GOLD}, #FF8C00) !important;
    color: #000 !important;
    font-weight: 700 !important;
    border: none !important;
    padding: 12px 28px !important;
    font-size: 15px !important;
    border-radius: 10px !important;
    box-shadow: 0 4px 16px rgba(255,215,0,0.25) !important;
    transition: box-shadow 0.2s, transform 0.15s !important;
}}
div.stDownloadButton > button:hover {{
    box-shadow: 0 6px 24px rgba(255,215,0,0.45) !important;
    transform: translateY(-1px) !important;
}}

/* ─── 其他覆寫 ─── */
h1, h2, h3 {{
    color: #FFFFFF !important;
    font-weight: 800 !important;
    text-shadow: none !important;
}}
p {{ color: #AAAAAA; }}
.stProgress > div > div > div > div {{ background: linear-gradient(90deg, {GOLD}, #FF8C00); }}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 輔助函式
# ==========================================
def get_logo_b64():
    """嘗試多個常見路徑讀取 LOGO"""
    for path in ["logo.png", "assets/logo.png", "static/logo.png", "images/logo.png"]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    return None

def section_header(icon: str, title: str):
    st.markdown(f"""
    <div class="section-title">
        <span class="section-icon">{icon}</span>
        <h2>{title}</h2>
        <div class="section-line"></div>
    </div>""", unsafe_allow_html=True)

def delta_badge(val: float, suffix: str = "", show_sign: bool = True) -> str:
    cls    = "up" if val >= 0 else "down"
    symbol = "▲" if val >= 0 else "▼"
    sign   = ("+" if val >= 0 else "") if show_sign else ""
    return f'<span class="metric-badge badge-{cls}">{symbol} {abs(val):.2f}{suffix}</span>'

def plot_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Date'], y=df['Value'],
        mode='lines',
        name='TSF-Top5',
        line=dict(color=GOLD, width=2.5),
        fill='tozeroy',
        fillcolor='rgba(255,215,0,0.05)',
        hovertemplate='<b>%{x|%Y-%m-%d}</b><br>指數: %{y:.2f}<extra></extra>'
    ))
    # 基準線 100
    fig.add_hline(
        y=100,
        line_dash="dot",
        line_color="rgba(255,255,255,0.15)",
        line_width=1,
        annotation_text="基期 100",
        annotation_font_color="rgba(255,255,255,0.3)"
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=420,
        margin=dict(l=8, r=8, t=16, b=8),
        xaxis=dict(gridcolor='#1A2440', color='#6677AA', showline=False),
        yaxis=dict(gridcolor='#1A2440', color='#6677AA', showline=False),
        showlegend=False,
        hovermode='x unified',
        hoverlabel=dict(bgcolor='#141827', font_size=13)
    )
    return fig

# ==========================================
# 4. 資料計算
# ==========================================
engine = IndexEngine()

try:
    df_hist = engine.get_history()
    if not df_hist.empty:
        df_hist = df_hist.rename(columns={'date': 'Date', 'index_value': 'Value'})
        df_hist['Date'] = pd.to_datetime(df_hist['Date'].astype(str), format='%Y%m%d')
        latest_val        = df_hist.iloc[-1]['Value']
        last_updated_date = df_hist.iloc[-1]['Date'].strftime('%Y/%m/%d')
        delta_val         = latest_val - df_hist.iloc[-2]['Value'] if len(df_hist) >= 2 else 0.0
        delta_pct         = (delta_val / (latest_val - delta_val)) * 100 if (latest_val - delta_val) != 0 else 0.0
        start_val         = df_hist.iloc[0]['Value']
        ytd_val           = (latest_val - start_val) / start_val * 100
        roll_max          = df_hist['Value'].cummax()
        mdd_val           = ((df_hist['Value'] - roll_max) / roll_max).min() * 100
        df_hist['daily_ret'] = df_hist['Value'].pct_change()
        sharpe_val = (
            (df_hist['daily_ret'].mean() / df_hist['daily_ret'].std()) * (252 ** 0.5)
            if df_hist['daily_ret'].std() != 0 else 0.0
        )
    else:
        latest_val = delta_val = delta_pct = ytd_val = mdd_val = sharpe_val = 0.0
        last_updated_date = "尚無資料"
        df_hist = pd.DataFrame()
except Exception as e:
    st.error(f"運算錯誤：{e}")
    latest_val = delta_val = delta_pct = ytd_val = mdd_val = sharpe_val = 0.0
    last_updated_date = "N/A"
    df_hist = pd.DataFrame()

# ==========================================
# 5. 頁首
# ==========================================
logo_b64  = get_logo_b64()
logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}" />'
    if logo_b64
    else '<div class="tsf-header-logo-placeholder">🐯</div>'
)

st.markdown(f"""
<div class="tsf-header">
    {logo_html}
    <div class="tsf-header-text">
        <h1>TSF-Top5 Index</h1>
        <p>台股基金五虎將指數 ｜ 鎖定最強攻擊手 · 追求極致超額報酬</p>
    </div>
    <div class="tsf-header-right">
        <div class="updated-label">最後更新</div>
        <div class="updated-date">{last_updated_date}</div>
    </div>
</div>
<div class="rainbow-hr"></div>
""", unsafe_allow_html=True)

# ==========================================
# 6. 指標看板
# ==========================================
section_header("📊", "即時指數看板")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="metric-card card-gold">
        <div class="metric-label">指數點位</div>
        <div class="metric-value" style="color:{GOLD}">{latest_val:.2f}</div>
        <div>
            {delta_badge(delta_val)}
            {delta_badge(delta_pct, '%')}
        </div>
    </div>""", unsafe_allow_html=True)

with c2:
    color_ytd = "#FF4B4B" if ytd_val >= 0 else "#00C853"
    st.markdown(f"""
    <div class="metric-card card-red">
        <div class="metric-label">今年以來 (YTD)</div>
        <div class="metric-value" style="color:{color_ytd}">{"+" if ytd_val >= 0 else ""}{ytd_val:.2f}%</div>
        <div>{delta_badge(ytd_val, '%')}</div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="metric-card card-white">
        <div class="metric-label">夏普值 (Sharpe)</div>
        <div class="metric-value" style="color:#FFFFFF">{sharpe_val:.2f}</div>
        <div><span class="metric-badge badge-neu">年化風險調整</span></div>
    </div>""", unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="metric-card card-green">
        <div class="metric-label">最大回撤 (MDD)</div>
        <div class="metric-value" style="color:#00C853">{mdd_val:.2f}%</div>
        <div>{delta_badge(mdd_val, '%')}</div>
    </div>""", unsafe_allow_html=True)

# Streamlit 需要佔位符觸發 CSS（columns 實際渲染用）
st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

# ==========================================
# 7. 走勢圖
# ==========================================
section_header("📈", "指數走勢")

if not df_hist.empty:
    st.plotly_chart(plot_chart(df_hist), use_container_width=True)
else:
    st.info("尚無歷史資料，請先至管理後台執行初始化。")

# ==========================================
# 8. 成分基金表格
# ==========================================
section_header("🛡️", "最新成分基金權重 (2026 H1)")

today_str = datetime.now().strftime("%Y%m%d")
_, components_data = engine.calculate_index(today_str)

# 今日資料未發布時，退回歷史最後一筆有效日期
if not isinstance(components_data, list) or len(components_data) == 0:
    _hist = engine.get_history()
    if not _hist.empty:
        last_date = str(int(_hist.sort_values('date').iloc[-1]['date']))
        _, components_data = engine.calculate_index(last_date)

# ── 表格欄位標頭 ──
st.markdown("""
<div class="fund-header">
    <span></span>
    <span>基金名稱</span>
    <span style="text-align:right;padding-right:16px">最新淨值</span>
    <span style="text-align:right;padding-right:16px">本期基金漲幅</span>
    <span style="text-align:center">權重</span>
</div>""", unsafe_allow_html=True)

if isinstance(components_data, list) and len(components_data) > 0:
    cons_df = pd.DataFrame(components_data)
    cons_df = cons_df.rename(columns={
        '基金名稱': 'name',
        '最新淨值': 'nav',
        '本期基金漲幅': 'pct',
        '權重': 'weight'
    })
    for i, row in cons_df.iterrows():
        color = FUND_COLORS[i % len(FUND_COLORS)]
        nav   = f"{float(row['nav']):.2f}" if pd.notnull(row.get('nav')) and str(row.get('nav')) != '--' else '--'
        pct   = row.get('pct', '--')
        try:
            pct_f   = float(str(pct).replace('%', '').replace('+', ''))
            pct_cls = "up" if pct_f >= 0 else "down"
            pct_str = f"{'+'if pct_f >= 0 else ''}{pct_f:.2f}%"
        except Exception:
            pct_cls, pct_str = "neu", str(pct)

        st.markdown(f"""
        <div class="fund-row" style="--fund-color:{color}">
            <div class="fund-rank" style="background:{color}">{i + 1}</div>
            <div class="fund-name">{row['name']}</div>
            <div class="fund-nav">{nav}</div>
            <div class="fund-pct {pct_cls}">{pct_str}</div>
            <div class="fund-weight">20%</div>
        </div>""", unsafe_allow_html=True)
else:
    # Fallback：無資料時顯示佔位
    fallback_names = ["統一奔騰", "安聯台灣科技", "路博邁台灣5G", "野村鴻運", "野村台灣運籌"]
    for i, name in enumerate(fallback_names):
        color = FUND_COLORS[i]
        st.markdown(f"""
        <div class="fund-row" style="--fund-color:{color}">
            <div class="fund-rank" style="background:{color}">{i + 1}</div>
            <div class="fund-name">{name}</div>
            <div class="fund-nav" style="color:#556080">--</div>
            <div class="fund-pct neu">--</div>
            <div class="fund-weight">20%</div>
        </div>""", unsafe_allow_html=True)

# ==========================================
# 9. 簡報下載
# ==========================================
st.markdown('<div class="rainbow-hr" style="margin-top:32px"></div>', unsafe_allow_html=True)
section_header("📄", "指數規格與簡報")

pdf_path = "tsf_presentation.pdf"
if os.path.exists(pdf_path):
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()
    col_dl1, col_dl2 = st.columns([1, 4])
    with col_dl1:
        st.download_button(
            label="📥 下載完整簡報 (PDF)",
            data=pdf_data,
            file_name="tsf_presentation.pdf",
            mime="application/pdf"
        )
    with col_dl2:
        st.caption("👈 點擊下載完整指數規格書 (PDF)")
else:
    st.warning("⚠️  尚未偵測到簡報檔，請確認 `tsf_presentation.pdf` 已上傳至 GitHub。")

# ==========================================
# 10. 管理員後台
# ==========================================
st.markdown("---")
with st.expander("⚙️  管理員後台（需密碼）"):
    password = st.text_input("請輸入管理員密碼", type="password")
    if password == "8888":
        st.success("✅ 驗證成功！")
        st.info(f"📅 資料庫目前更新至：**{last_updated_date}**")
        col_adm1, col_adm2 = st.columns(2)
        with col_adm1:
            st.write("#### 1. 重置（危險）")
            base_date = st.text_input("輸入基期日期", "20251231")
            if st.button("🚀 執行初始化（清空資料）"):
                success, msg = engine.initialize_index(base_date)
                if success:
                    st.success(msg)
        with col_adm2:
            st.write("#### 2. 智慧補齊")
            batch_end = st.text_input("補齊至日期 (End Date)", datetime.now().strftime("%Y%m%d"))
            if st.button("🔥 開始批次補齊"):
                pbar       = st.progress(0)
                status_txt = st.empty()
                res = engine.run_batch_update(
                    batch_end,
                    lambda p, m: (pbar.progress(p), status_txt.text(m))
                )
                pbar.progress(100)
                status_txt.text("Done!")
                st.success(res)
    elif password:
        st.error("❌ 密碼錯誤。")
