# -*- coding: utf-8 -*-
"""
退休提領回測工具（Streamlit 版 v2）
新增：① 表格標上年度　② 可從 Yahoo Finance 線上抓取指數/股票資料
本機測試：streamlit run app.py
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="退休提領回測", page_icon="📉", layout="wide")
st.title("📉 退休提領回測工具")
st.caption("固定提領 vs. Guyton-Klinger 動態提領")


# =====================================================================
# 引擎（核心邏輯，與前版相同）
# =====================================================================
def run_backtest(principal, init_rate, inflation, strategy, returns,
                 start_year, infl_cap=6, band=20, step=10):
    rate0, inf = init_rate / 100, inflation / 100
    cap, band_v, step_v = infl_cap / 100, band / 100, step / 100

    portfolio = principal
    prev_withdraw = rate0 * principal
    prev_ret = 0.0
    rows, bankrupt_year = [], None

    for i, r_pct in enumerate(returns):
        start = portfolio
        if start <= 0:
            bankrupt_year = start_year + i
            break
        ret = r_pct / 100

        if i == 0:
            withdraw = rate0 * principal
        elif strategy == "固定":
            withdraw = prev_withdraw * (1 + inf)
        else:  # GK
            cand = prev_withdraw
            if prev_ret >= 0:                       # (1) 通膨規則
                cand *= (1 + min(inf, cap))
            cur_rate = cand / start                 # 警報器：當下提領率
            if cur_rate > rate0 * (1 + band_v):     # (2) 保本規則
                cand *= (1 - step_v)
            elif cur_rate < rate0 * (1 - band_v):   # (3) 繁榮規則
                cand *= (1 + step_v)
            withdraw = cand

        actual = min(withdraw, start)
        end = (start - actual) * (1 + ret)
        rows.append({
            "年度": start_year + i,
            "期初資產": round(start),
            "當年提領": round(actual),
            "提領率%": round(actual / start * 100, 1),
            "市場報酬%": round(r_pct, 1),
            "期末資產": round(max(end, 0)),
        })
        prev_withdraw, prev_ret, portfolio = withdraw, ret, max(end, 0)

    return rows, bankrupt_year


# =====================================================================
# 從 Yahoo Finance 抓資料、算每年報酬
# =====================================================================
def fetch_annual_returns(ticker, sy, ey):
    """回傳 (報酬率list, 第一年年份)；失敗回 (None, 錯誤訊息)"""
    import yfinance as yf
    raw = yf.download(ticker, start=f"{sy-1}-11-01", end=f"{ey+1}-01-15",
                      auto_adjust=True, progress=False)
    if raw is None or raw.empty:
        return None, "抓不到資料，請確認代碼是否正確。"
    close = raw["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    yearly = close.resample("YE").last().dropna()
    rets = (yearly.pct_change() * 100).dropna()
    rets = rets[(rets.index.year >= sy) & (rets.index.year <= ey)]
    if len(rets) == 0:
        return None, "這段期間沒有足夠資料計算年報酬。"
    return [round(float(x), 1) for x in rets.values], int(rets.index.year[0])


PRESETS = {
    "元大台灣50 (0050.TW)": "0050.TW",
    "標普500 指數 (^GSPC)": "^GSPC",
    "那斯達克綜合 (^IXIC)": "^IXIC",
    "費城半導體 (^SOX)": "^SOX",
    "台股加權 (^TWII)": "^TWII",
    "Nasdaq-100 ETF (QQQ)": "QQQ",
    "標普500 ETF (SPY)": "SPY",
    "自訂代碼…": "",
}
DEFAULT = [5.3, 10.0, 20.6, 11.2, -42.7, 73.9, 12.8, -15.8, 11.6, 11.5,
           16.7, -6.3, 19.7, 18.1, -4.9, 32.7, 31.1, 21.8, -21.8, 27.9, 47.0]

st.session_state.setdefault("returns", DEFAULT)
st.session_state.setdefault("sy_w", 2004)


# =====================================================================
# 側邊欄：設定
# =====================================================================
with st.sidebar:
    st.header("⚙️ 設定")
    principal = st.number_input("初始本金（萬元）", value=1000, step=100)
    init_rate = st.number_input("初始提領率（%）", value=6.0, step=0.5)
    inflation = st.number_input("年通膨率（%）", value=3.0, step=0.5)
    strategy = st.radio("提領策略", ["固定", "GK"], index=1, horizontal=True)
    if strategy == "GK":
        st.divider(); st.caption("GK 護欄參數")
        infl_cap = st.number_input("通膨調整上限（%）", value=6.0)
        band = st.number_input("護欄帶寬（±%）", value=20.0)
        step = st.number_input("每次調整幅度（%）", value=10.0)
    else:
        infl_cap, band, step = 6.0, 20.0, 10.0


# =====================================================================
# 資料來源：手動 or 線上抓取
# =====================================================================
st.subheader("📊 報酬率資料")
tab_online, tab_manual = st.tabs(["🌐 線上抓取（Yahoo Finance）", "✍️ 手動輸入"])

with tab_online:
    name = st.selectbox("選擇標的", list(PRESETS.keys()))
    ticker = PRESETS[name] or st.text_input("輸入代碼（例如 AAPL、^DJI）", value="")
    c1, c2 = st.columns(2)
    sy = c1.number_input("起始年", min_value=1990, max_value=2025, value=2010, step=1)
    ey = c2.number_input("結束年", min_value=1991, max_value=2025, value=2024, step=1)
    if st.button("📥 抓取資料", type="primary"):
        if not ticker:
            st.warning("請先輸入代碼。")
        else:
            try:
                with st.spinner(f"從 Yahoo Finance 抓取 {ticker} …"):
                    rets, info = fetch_annual_returns(ticker, int(sy), int(ey))
                if rets is None:
                    st.error(info)
                    st.caption("雲端有時會被 Yahoo 限流，可改用『手動輸入』或稍後再試。")
                else:
                    st.session_state["returns"] = rets
                    st.session_state["sy_w"] = info
                    st.success(f"✅ 抓到 {len(rets)} 年（{info}-{info + len(rets) - 1}）")
            except Exception as e:
                st.error(f"抓取失敗：{e}")
                st.caption("雲端有時會被 Yahoo 限流，可改用『手動輸入』或稍後再試。")
    st.caption("ℹ️ 指數（如 ^GSPC、^SOX）為價格報酬，不含配息；個股/ETF（如 0050.TW、SPY）已含息。")

with tab_manual:
    st.caption("⚠️ 預設為 0050 範例（估算值）。直接點表格的『報酬率』欄改數字即可。")
    new_sy = st.number_input("起始年份", value=int(st.session_state["sy_w"]), step=1, key="manual_sy")
    st.session_state["sy_w"] = int(new_sy)


# =====================================================================
# 可編輯表格（年度標清楚！年度欄唯讀，只改報酬率）
# =====================================================================
start_year = int(st.session_state["sy_w"])
rets = st.session_state["returns"]
years = list(range(start_year, start_year + len(rets)))
df_show = pd.DataFrame({"年度": years, "報酬率(%)": rets})

edited = st.data_editor(
    df_show, hide_index=True, disabled=["年度"],
    column_config={
        "年度": st.column_config.NumberColumn(format="%d"),
        "報酬率(%)": st.column_config.NumberColumn(format="%.1f"),
    },
    height=320,
)
returns = [float(x) for x in edited["報酬率(%)"].tolist()]
st.session_state["returns"] = returns


# =====================================================================
# 跑回測
# =====================================================================
if len(returns) == 0:
    st.warning("請至少輸入一年的報酬率。"); st.stop()

rows, bankrupt = run_backtest(principal, init_rate, inflation, strategy,
                              returns, start_year, infl_cap, band, step)
res = pd.DataFrame(rows)
final = res["期末資產"].iloc[-1] if len(res) else principal
total = int(res["當年提領"].sum()) if len(res) else 0

st.subheader("結果")
c1, c2, c3, c4 = st.columns(4)
c1.metric("期末資產", f"{final:,.0f} 萬")
c2.metric("結果", "💀 破產" if bankrupt else "✅ 撐住了",
          f"第 {bankrupt} 年" if bankrupt else None)
c3.metric("累計提領", f"{total:,.0f} 萬")
c4.metric("最低點資產", f"{res['期末資產'].min():,.0f} 萬")

st.subheader("資產走勢")
st.line_chart(res.set_index("年度")[["期末資產"]], color="#0e2a47")
st.subheader("每年提領金額")
st.bar_chart(res.set_index("年度")[["當年提領"]], color="#c8a24b")

st.subheader("逐年明細")
st.dataframe(res, hide_index=True)
