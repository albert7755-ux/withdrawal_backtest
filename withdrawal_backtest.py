# -*- coding: utf-8 -*-
"""
退休提領回測工具（Streamlit 版）
比較「固定提領」與「Guyton-Klinger 動態提領」兩種策略。
本機測試：streamlit run app.py
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="退休提領回測", page_icon="📉", layout="wide")

st.title("📉 退休提領回測工具")
st.caption("固定提領 vs. Guyton-Klinger 動態提領")


# =====================================================================
# 引擎（跟終端機版完全一樣的核心邏輯）
# =====================================================================
def run_backtest(principal, init_rate, inflation, strategy, returns,
                 start_year, infl_cap=6, band=20, step=10):
    rate0  = init_rate / 100
    inf    = inflation / 100
    cap    = infl_cap / 100
    band_v = band / 100
    step_v = step / 100

    portfolio     = principal
    prev_withdraw = rate0 * principal
    prev_ret      = 0.0
    rows          = []
    bankrupt_year = None

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
            if prev_ret >= 0:                       # ① 通膨規則
                cand *= (1 + min(inf, cap))
            cur_rate = cand / start                 # 警報器：當下提領率
            if cur_rate > rate0 * (1 + band_v):     # ② 保本規則
                cand *= (1 - step_v)
            elif cur_rate < rate0 * (1 - band_v):   # ③ 繁榮規則
                cand *= (1 + step_v)
            withdraw = cand

        actual = min(withdraw, start)
        end = (start - actual) * (1 + ret)

        rows.append({
            "年度":   start_year + i,
            "期初資產": round(start),
            "當年提領": round(actual),
            "提領率%": round(actual / start * 100, 1),
            "市場報酬%": r_pct,
            "期末資產": round(max(end, 0)),
        })
        prev_withdraw = withdraw
        prev_ret      = ret
        portfolio     = max(end, 0)

    return rows, bankrupt_year


# =====================================================================
# 側邊欄：設定
# =====================================================================
with st.sidebar:
    st.header("⚙️ 設定")
    principal = st.number_input("初始本金（萬元）", value=1000, step=100)
    init_rate = st.number_input("初始提領率（%）", value=6.0, step=0.5)
    inflation = st.number_input("年通膨率（%）", value=3.0, step=0.5)
    strategy  = st.radio("提領策略", ["固定", "GK"], index=1, horizontal=True)

    if strategy == "GK":
        st.divider()
        st.caption("GK 護欄參數")
        infl_cap = st.number_input("通膨調整上限（%）", value=6.0)
        band     = st.number_input("護欄帶寬（±%）", value=20.0)
        step     = st.number_input("每次調整幅度（%）", value=10.0)
    else:
        infl_cap, band, step = 6.0, 20.0, 10.0

    st.divider()
    start_year = st.number_input("起始年份", value=2004, step=1)


# =====================================================================
# 主畫面：可編輯的報酬資料
# =====================================================================
st.subheader("📊 每年報酬率（可直接編輯）")
st.caption("⚠️ 預設為 0050 範例（估算值），請換成你自己 NAV 算出來的真實年報酬。可在表格最下方新增/刪除列。")

default_returns = [5.3, 10.0, 20.6, 11.2, -42.7, 73.9, 12.8, -15.8, 11.6, 11.5,
                   16.7, -6.3, 19.7, 18.1, -4.9, 32.7, 31.1, 21.8, -21.8, 27.9, 47.0]
df_in = pd.DataFrame({"報酬率(%)": default_returns})

edited = st.data_editor(
    df_in, num_rows="dynamic", use_container_width=True,
    column_config={"報酬率(%)": st.column_config.NumberColumn(format="%.1f")},
    height=300,
)

# 把編輯後的報酬抓出來（去掉空白列）
returns = [float(x) for x in edited["報酬率(%)"].dropna().tolist()]


# =====================================================================
# 跑回測
# =====================================================================
if len(returns) == 0:
    st.warning("請至少輸入一年的報酬率。")
    st.stop()

rows, bankrupt = run_backtest(principal, init_rate, inflation, strategy,
                              returns, int(start_year), infl_cap, band, step)

res = pd.DataFrame(rows)
final = res["期末資產"].iloc[-1] if len(res) else principal
total = int(res["當年提領"].sum()) if len(res) else 0


# =====================================================================
# 結果卡片
# =====================================================================
st.subheader("結果")
c1, c2, c3, c4 = st.columns(4)
c1.metric("期末資產", f"{final:,.0f} 萬")
if bankrupt:
    c2.metric("結果", "💀 破產", f"第 {bankrupt} 年")
else:
    c2.metric("結果", "✅ 撐住了")
c3.metric("累計提領", f"{total:,.0f} 萬")
c4.metric("最低點資產", f"{res['期末資產'].min():,.0f} 萬")


# =====================================================================
# 圖表（用 Streamlit 原生圖表，中文不會變方框）
# =====================================================================
st.subheader("資產走勢")
chart_df = res.set_index("年度")[["期末資產"]]
st.line_chart(chart_df, color="#0e2a47")

st.subheader("每年提領金額")
st.bar_chart(res.set_index("年度")[["當年提領"]], color="#c8a24b")


# =====================================================================
# 逐年明細
# =====================================================================
st.subheader("逐年明細")
st.dataframe(res, use_container_width=True, hide_index=True)
