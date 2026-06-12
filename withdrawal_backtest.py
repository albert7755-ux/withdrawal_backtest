# -*- coding: utf-8 -*-
"""
退休提領回測工具
比較「固定提領」與「Guyton-Klinger 動態提領」兩種策略。
你只要改最上面【設定區】和【資料區】的數字，其它都不用動。
"""

import matplotlib
import matplotlib.pyplot as plt

# =====================================================================
# 【設定區】← 平常只改這裡
# =====================================================================
PRINCIPAL = 1000      # 初始本金（萬元）
INIT_RATE = 6         # 初始提領率（%）
INFLATION = 3         # 年通膨率（%）
STRATEGY  = "GK"      # 策略："固定" 或 "GK"

# --- GK 動態提領的護欄參數（不確定就用預設值）---
INFL_CAP = 6          # 通膨調整上限（%）
BAND     = 20         # 護欄帶寬（±%）
STEP     = 10         # 每次調整幅度（%）

# =====================================================================
# 【資料區】← 每年的報酬率（%），請換成你自己算出來的真實數據
# 這裡先放 0050 的「範例」報酬（憑記憶估算，不精確）
# =====================================================================
START_YEAR = 2004
RETURNS = [5.3, 10.0, 20.6, 11.2, -42.7, 73.9, 12.8, -15.8, 11.6, 11.5,
           16.7, -6.3, 19.7, 18.1, -4.9, 32.7, 31.1, 21.8, -21.8, 27.9, 47.0]


# =====================================================================
# 【引擎】← 核心計算，看懂就好，平常不用改
# =====================================================================
def run_backtest(principal, init_rate, inflation, strategy, returns,
                 infl_cap=6, band=20, step=10):
    rate0     = init_rate / 100      # 初始提領率（小數）
    inf       = inflation / 100      # 通膨（小數）
    cap       = infl_cap / 100       # 通膨上限（小數）
    band_v    = band / 100           # 護欄帶寬（小數）
    step_v    = step / 100           # 調整幅度（小數）

    portfolio     = principal               # 目前資產
    prev_withdraw = rate0 * principal       # 上一年的提領金額
    prev_ret      = 0.0                      # 上一年的市場報酬
    rows          = []                       # 存每一年的結果
    bankrupt_year = None                     # 哪一年破產（None = 沒破產）

    for i, r_pct in enumerate(returns):
        start = portfolio
        if start <= 0:                       # 資產見底 → 破產，停止
            bankrupt_year = START_YEAR + i
            break
        ret = r_pct / 100                    # 當年市場報酬（小數）

        # --- 決定今年要領多少 ---
        if i == 0:
            # 第一年：本金 × 初始提領率
            withdraw = rate0 * principal
        elif strategy == "固定":
            # 固定提領：不管市場，每年金額照通膨往上加
            withdraw = prev_withdraw * (1 + inf)
        else:
            # GK 動態提領
            cand = prev_withdraw
            # ① 通膨規則：前一年有賺才加通膨（上限 cap），前一年賠就不加
            if prev_ret >= 0:
                cand *= (1 + min(inf, cap))
            # 用「當下資產」算出當前提領率（當作警報器）
            cur_rate = cand / start
            # ② 保本規則：提領率太高 → 砍 step%
            if cur_rate > rate0 * (1 + band_v):
                cand *= (1 - step_v)
            # ③ 繁榮規則：提領率太低 → 加 step%
            elif cur_rate < rate0 * (1 - band_v):
                cand *= (1 + step_v)
            withdraw = cand

        # 不能領超過剩下的錢
        actual = min(withdraw, start)
        # 先領錢、再讓剩下的部位吃當年市場漲跌
        end = (start - actual) * (1 + ret)

        rows.append({
            "year":     START_YEAR + i,
            "start":    start,
            "withdraw": actual,
            "rate":     actual / start * 100,   # 當年實際提領率
            "ret":      r_pct,
            "end":      max(end, 0),
        })

        prev_withdraw = withdraw
        prev_ret      = ret
        portfolio     = max(end, 0)

    return rows, bankrupt_year


# =====================================================================
# 【執行 + 印出結果】
# =====================================================================
rows, bankrupt = run_backtest(PRINCIPAL, INIT_RATE, INFLATION, STRATEGY,
                              RETURNS, INFL_CAP, BAND, STEP)

print("=" * 64)
print(f"  策略：{STRATEGY}提領　|　本金 {PRINCIPAL} 萬　|　初始提領率 {INIT_RATE}%　|　通膨 {INFLATION}%")
print("=" * 64)
print(f"{'年度':<6}{'期初資產':>10}{'當年提領':>10}{'提領率':>8}{'市場報酬':>10}{'期末資產':>10}")
print("-" * 64)
for r in rows:
    print(f"{r['year']:<6}{r['start']:>10.0f}{r['withdraw']:>10.0f}"
          f"{r['rate']:>7.1f}%{r['ret']:>9.1f}%{r['end']:>10.0f}")
print("-" * 64)

final = rows[-1]["end"] if rows else PRINCIPAL
total = sum(r["withdraw"] for r in rows)
if bankrupt:
    print(f"  結果：💀 第 {bankrupt} 年破產")
else:
    print(f"  結果：✅ 撐住了，期末資產 {final:.0f} 萬")
print(f"  累計提領：{total:.0f} 萬")
print("=" * 64)


# =====================================================================
# 【畫圖】期末資產走勢 + 每年提領金額
# =====================================================================
# 讓中文能正常顯示（找得到就用，找不到就跳過、用英文）
for f in ["Microsoft JhengHei", "PingFang TC", "Noto Sans CJK TC", "WenQuanYi Micro Hei"]:
    try:
        matplotlib.rcParams["font.sans-serif"] = [f]
        matplotlib.rcParams["axes.unicode_minus"] = False
        break
    except Exception:
        pass

years      = [r["year"] for r in rows]
ends       = [r["end"] for r in rows]
withdraws  = [r["withdraw"] for r in rows]

fig, ax1 = plt.subplots(figsize=(11, 5))
ax2 = ax1.twinx()
ax2.bar(years, withdraws, color="#e3c87f", alpha=0.7, label="當年提領")
ax1.plot(years, ends, color="#0e2a47", linewidth=2.5, marker="o", label="期末資產")
ax1.axhline(PRINCIPAL, color="#c8a24b", linestyle="--", label="起始本金")

ax1.set_ylabel("資產（萬元）")
ax2.set_ylabel("提領（萬元）")
ax1.set_title(f"{STRATEGY}提領　{INIT_RATE}% 起　通膨 {INFLATION}%")
ax1.set_zorder(2); ax1.patch.set_visible(False)   # 讓線蓋在長條上面
fig.legend(loc="upper left", bbox_to_anchor=(0.1, 0.95))
plt.tight_layout()
plt.savefig("backtest_result.png", dpi=120)   # 存成圖檔
plt.show()                                     # 跳出視窗（本機執行時）
print("圖已存成 backtest_result.png")
