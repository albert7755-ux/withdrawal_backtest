# -*- coding: utf-8 -*-
"""
退休提領回測工具（Streamlit 版 v3）
新增：① 比較模式（固定 vs GK 並排）② 策略說明分頁
本機測試：streamlit run app.py
"""

import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="退休提領回測", page_icon="📉", layout="wide")


# =====================================================================
# 引擎
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


def analyze(strategy, principal, init_rate, inflation, returns, start_year,
            infl_cap, band, step):
    """跑一次回測，回傳所有要顯示的統計。"""
    rows, bankrupt = run_backtest(principal, init_rate, inflation, strategy,
                                  returns, start_year, infl_cap, band, step)
    res = pd.DataFrame(rows)
    final = res["期末資產"].iloc[-1] if len(res) else principal
    total = int(res["當年提領"].sum()) if len(res) else 0

    vals = [principal] + [r["期末資產"] for r in rows]
    yrs = ["起始"] + [r["年度"] for r in rows]
    peak, cpi = vals[0], 0
    worst, wp, wt = 0.0, 0, 0
    for i, v in enumerate(vals):
        if v > peak:
            peak, cpi = v, i
        d = (v / peak - 1) * 100 if peak > 0 else 0
        if d < worst:
            worst, wp, wt = d, cpi, i

    return {
        "rows": rows, "res": res, "bankrupt": bankrupt,
        "final": final, "total": total,
        "change": final - principal,
        "change_pct": (final / principal - 1) * 100 if principal else 0,
        "worst_dd": worst, "dd_amt": vals[wp] - vals[wt],
        "peak_y": yrs[wp], "trough_y": yrs[wt],
        "peak_v": vals[wp], "trough_v": vals[wt],
        "min_v": res["期末資產"].min() if len(res) else principal,
    }


def fetch_annual_returns(ticker, sy, ey):
    import yfinance as yf
    # 用 Ticker.history(period="max") 抓「全部歷史」，比 download(start,end) 完整、穩定
    hist = None
    try:
        hist = yf.Ticker(ticker).history(period="max", auto_adjust=True)
    except Exception:
        hist = None
    if hist is None or hist.empty:                       # 退而求其次
        hist = yf.download(ticker, period="max", auto_adjust=True, progress=False)
    if hist is None or hist.empty:
        return None, "抓不到資料，請確認代碼是否正確、或稍後再試。"
    close = hist["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close[close > 0].dropna()                    # 濾掉 0/NaN 壞點
    yearly = close.resample("YE").last().dropna()        # 每年年底收盤
    rets = (yearly.pct_change() * 100).dropna()          # 年報酬 %
    rets = rets[(rets.index.year >= sy) & (rets.index.year <= ey)]
    if len(rets) == 0:
        return None, "這段期間沒有足夠資料計算年報酬。"
    return [round(float(x), 1) for x in rets.values], int(rets.index.year[0])


@st.cache_data
def load_builtin_0050():
    """讀取與 app.py 放在一起的 0050_data.csv，算「完整年度」的年報酬。"""
    path = Path(__file__).parent / "0050_data.csv"
    df = pd.read_csv(path, parse_dates=["date"]).dropna().sort_values("date").set_index("date")
    year = df.index.year
    last_close = df["close"].groupby(year).last()
    last_month = pd.Series(df.index.month, index=df.index).groupby(year).max()
    lc = last_close[last_month >= 12]                 # 只保留資料到 12 月的完整年度
    rets = (lc.pct_change() * 100).dropna()
    return [round(float(x), 1) for x in rets.values], int(rets.index[0])


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
st.session_state.setdefault("data_version", 0)


# =====================================================================
# 側邊欄
# =====================================================================
with st.sidebar:
    st.header("⚙️ 設定")
    principal = st.number_input("初始本金（萬元）", value=1000, step=100)
    init_rate = st.number_input("初始提領率（%）", value=6.0, step=0.5)
    inflation = st.number_input("年通膨率（%）", value=3.0, step=0.5)

    st.divider()
    compare = st.checkbox("🔀 比較兩種策略（固定 vs GK）", value=False)
    if compare:
        strategy = "GK"
        st.caption("已開啟比較模式：固定與 GK 並排對照")
    else:
        strategy = st.radio("提領策略", ["固定", "GK"], index=1, horizontal=True)

    if compare or strategy == "GK":
        st.divider(); st.caption("GK 護欄參數")
        infl_cap = st.number_input("通膨調整上限（%）", value=6.0)
        band = st.number_input("護欄帶寬（±%）", value=20.0)
        step = st.number_input("每次調整幅度（%）", value=10.0)
    else:
        infl_cap, band, step = 6.0, 20.0, 10.0


st.title("📉 退休提領回測工具")
st.caption("固定提領 vs. Guyton-Klinger 動態提領")
tool_tab, guide_tab = st.tabs(["📊 回測工具", "📖 策略說明"])


# =====================================================================
# 分頁一：回測工具
# =====================================================================
with tool_tab:
    st.subheader("📊 報酬率資料")
    t_builtin, t_online, t_manual = st.tabs(
        ["📁 內建 0050（你的資料）", "🌐 線上抓取（Yahoo Finance）", "✍️ 手動輸入"])

    with t_builtin:
        st.caption("內建 0050 歷史：2004-2023 為含息（還原），2024-2025 以價格報酬估計（約少算配息）。"
                   "若日後拿到完整含息資料到 2026，替換 0050_data.csv 即可，程式不用動。")
        if st.button("📁 載入內建 0050 歷史", type="primary"):
            try:
                b_rets, b_info = load_builtin_0050()
                st.session_state["returns"] = b_rets
                st.session_state["sy_w"] = b_info
                st.session_state["data_version"] += 1
                st.success(f"✅ 已載入 {len(b_rets)} 年（{b_info}-{b_info + len(b_rets) - 1}）")
            except Exception as e:
                st.error(f"讀取失敗：{e}（請確認 0050_data.csv 與 app.py 放在同一資料夾）")

    with t_online:
        name = st.selectbox("選擇標的", list(PRESETS.keys()))
        ticker = PRESETS[name] or st.text_input("輸入代碼（例如 AAPL、^DJI）", value="")
        c1, c2 = st.columns(2)
        sy = c1.number_input("起始年", min_value=1990, max_value=2026, value=2004, step=1)
        ey = c2.number_input("結束年", min_value=1991, max_value=2026, value=2025, step=1)
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
                        st.session_state["data_version"] += 1
                        st.success(f"✅ 抓到 {len(rets)} 年（{info}-{info + len(rets) - 1}）")
                except Exception as e:
                    st.error(f"抓取失敗：{e}")
                    st.caption("雲端有時會被 Yahoo 限流，可改用『手動輸入』或稍後再試。")
        st.caption("ℹ️ 指數（^GSPC、^SOX）為價格報酬不含息；個股/ETF（0050.TW、SPY）已含息。")
        st.caption("⚠️ Yahoo 的台股（如 0050.TW）歷史常只到 2010 年左右、舊年份偶有錯誤。"
                   "要完整 2003 年起的真實含息資料，建議用 FundDJ／cnYES／TWSE 等來源手動貼上。")

    with t_manual:
        st.caption("⚠️ 預設為 0050 範例（估算值）。直接點表格『報酬率』欄改數字即可。")
        st.number_input("起始年份", min_value=1980, max_value=2035, step=1, key="sy_w")

    # 可編輯表格
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
        height=320, key=f"editor_{st.session_state['data_version']}",
    )
    returns = [float(x) for x in edited["報酬率(%)"].tolist()]
    st.session_state["returns"] = returns

    if len(returns) == 0:
        st.warning("請至少輸入一年的報酬率。"); st.stop()

    bad = [(years[i], returns[i]) for i in range(len(returns)) if abs(returns[i]) > 60]
    if bad:
        items = "、".join(f"{y} 年 {r:+.1f}%" for y, r in bad)
        st.warning(
            f"⚠️ 這幾年波動偏大：{items}。有些是真的（0050 在 2008 約 −44%、2009 約 +74%），"
            f"但也可能是資料源的錯誤點，建議和可靠來源核對後再用。"
        )

    args = (principal, init_rate, inflation, returns, start_year, infl_cap, band, step)

    # ---------- 比較模式 ----------
    if compare:
        fix = analyze("固定", *args)
        gk = analyze("GK", *args)

        st.subheader("策略比較")
        colF, colG = st.columns(2)
        for col, label, d in [(colF, "固定提領", fix), (colG, "GK 動態", gk)]:
            with col:
                st.markdown(f"#### {label}")
                if d["bankrupt"]:
                    st.error(f"💀 第 {d['bankrupt']} 年破產")
                else:
                    st.success("✅ 撐住了")
                st.metric("期末資產", f"{d['final']:,.0f} 萬", f"{d['change']:+,.0f} 萬")
                st.metric("最大回撤", f"{d['worst_dd']:.1f}%")
                st.metric("回撤最多少掉", f"{d['dd_amt']:,.0f} 萬")
                st.metric("累計提領", f"{d['total']:,.0f} 萬")

        st.subheader("資產走勢對比")
        dfF = fix["res"].set_index("年度")["期末資產"].rename("固定")
        dfG = gk["res"].set_index("年度")["期末資產"].rename("GK")
        st.line_chart(pd.concat([dfF, dfG], axis=1), color=["#c8a24b", "#0e2a47"])

        st.subheader("數字總表")
        def cells(d):
            return [f"{d['final']:,.0f}", f"{d['change']:+,.0f}", f"{d['total']:,.0f}",
                    f"{d['worst_dd']:.1f}%", f"{d['dd_amt']:,.0f}",
                    f"破產@{d['bankrupt']}" if d["bankrupt"] else "撐住"]
        summary = pd.DataFrame({
            "指標": ["期末資產(萬)", "資產淨變化(萬)", "累計提領(萬)",
                     "最大回撤", "回撤少掉(萬)", "結果"],
            "固定提領": cells(fix), "GK 動態": cells(gk),
        })
        st.dataframe(summary, hide_index=True)

    # ---------- 單一策略模式 ----------
    else:
        a = analyze(strategy, *args)

        st.subheader("結果")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("期末資產", f"{a['final']:,.0f} 萬", f"{a['change']:+,.0f} 萬")
        c2.metric("結果", "💀 破產" if a["bankrupt"] else "✅ 撐住了",
                  f"第 {a['bankrupt']} 年" if a["bankrupt"] else None, delta_color="off")
        c3.metric("累計提領", f"{a['total']:,.0f} 萬")
        c4.metric("最低點資產", f"{a['min_v']:,.0f} 萬")

        st.subheader("風險指標")
        d1, d2, d3 = st.columns(3)
        d1.metric("資產淨變化", f"{a['change']:+,.0f} 萬", f"{a['change_pct']:+.1f}%")
        d2.metric("最大回撤", f"{a['worst_dd']:.1f}%")
        d3.metric("回撤最多少掉", f"{a['dd_amt']:,.0f} 萬")
        if a["dd_amt"] > 0:
            st.caption(
                f"📉 最大回撤發生在 **{a['peak_y']} → {a['trough_y']}**："
                f"帳戶從 {a['peak_v']:,.0f} 萬一度掉到 {a['trough_v']:,.0f} 萬，"
                f"少掉 **{a['dd_amt']:,.0f} 萬（{a['worst_dd']:.1f}%）**。"
                f"此為『提領之後』的實際帳戶波動。"
            )

        st.subheader("資產走勢")
        st.line_chart(a["res"].set_index("年度")[["期末資產"]], color="#0e2a47")
        st.subheader("每年提領金額")
        st.bar_chart(a["res"].set_index("年度")[["當年提領"]], color="#c8a24b")
        st.subheader("逐年明細")
        st.dataframe(a["res"], hide_index=True)


# =====================================================================
# 分頁二：策略說明
# =====================================================================
with guide_tab:
    st.markdown("""
## 一句話總覽
**固定提領**＝不看市場、只跟通膨走的「定速巡航」；
**GK 動態提領**＝會看帳戶狀況自動調整的「自動駕駛」。

---

### 🟡 固定提領法
**怎麼運作**：第一年領「本金 × 提領率」，之後每年金額只跟著通膨往上加，
**完全不管市場賺賠**。

- ✅ **優點**：每年能花多少很好預測，生活開銷穩定、好規劃。
- ⚠️ **缺點**：踩到「報酬順序風險」會出事——一退休就遇大跌，帳戶縮水了你卻照樣領原本金額，等於在變淺的池子舀同樣多水，很容易提早破產。

---

### 🔵 GK 動態提領法（Guyton-Klinger）
以固定提領為骨架，再加上三道「護欄」自動修正。學界與美國財務顧問圈的主流做法之一。

**三條規則：**
1. **通膨規則**：前一年有賺 → 提領金額隨通膨調（最多加到「通膨上限」）；前一年賠 → 今年不調。
2. **保本規則**：當年提領率衝得比初始高出一個「帶寬」（例如 +20%）→ 提領金額**砍 10%**，避免油盡燈枯。
3. **繁榮規則**：當年提領率掉得比初始低一個帶寬（例如 −20%）→ 提領金額**加 10%**，資產太肥就多花一點。

- ✅ **優點**：會對風險做反應，破產機率低、又能在好年頭多花，敢用比較高的初始提領率。
- ⚠️ **缺點**：每年實際能花的錢會浮動，市場差的年份得忍著少花。

---

### 📚 名詞解釋
- **報酬順序風險**：就算長期平均報酬一樣，**大跌發生在退休「前期」還是「後期」結果天差地遠**。前期就大跌最傷。
- **護欄帶寬**：幫提領率畫出一個安全區。以初始 6%、帶寬 ±20% 為例，安全區是 4.8%～7.2%，待在裡面就不調整，衝出去才出手。
- **最大回撤**：帳戶價值從高點跌到低點，跌最深的那一段。是衡量「過程多嚇人」的指標，跟「最後剩多少」是兩回事。

---

### 🎯 怎麼選？
根據歷史回測，全股配置下 **6% 初始 + GK 動態** 是相對穩健又靈活的甜蜜點。
> ⚠️ 高提領率（如 10%）只是極端示範，除非你願意嚴格照護欄調整生活開銷，否則遇上長空頭仍有風險。

打開「比較模式」勾選框，就能把兩種策略的期末資產、最大回撤、累計提領左右並排，一眼看出差別。
""")
