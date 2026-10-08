# -*- coding: utf-8 -*-
"""
L2 状态机：信号计算 + 状态判定（回测脚本 12_state_machine.py 与每日脚本 l2_daily.py 共用，保证口径完全一致）。

输入：按日期索引的原始表 raw，列名统一为：
  price, realized_cap, supply, sth_rp, lth_rp, tmmp, psip(0~1), profit_1y, loss_1y(正数), cdd,
  lth_supply, 以及分龄段 s_<段>/r_<段>（持币量 / 已实现市值）：
  段 = 1_3m, 3_6m, 6_12m, 12_18m, 18_24m, under_10y, over_6m, over_10y, over_7y
所有判断只用“当天及以前”的数据（没有未来函数）。阈值都是研究阶段（§2、§3.4、§3.5）定下的，没有为状态机另外调参。
"""
import numpy as np
import pandas as pd

HALVINGS = pd.to_datetime(["2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20", "2028-04-10"])
GENESIS = pd.Timestamp("2009-01-03")

# 状态代码 → 中文名、网站显示用的一句话
STATES = {
    "BULL": ("牛市", "价格创出新高后处在上升周期里"),
    "BULL_RISK": ("牛市·顶部风险区", "处在历史上见顶的时间窗或高估区，之后一年的收益明显变差"),
    "BULL_PULLBACK": ("牛市回撤·待确认", "从新高回撤超过 20%，还没满足转熊条件"),
    "BEAR": ("熊市", "从新高回撤超过 35% 且新高已过 90 天"),
    "BEAR_ZONE": ("熊底区", "熊市里出现至少两条“底部区”信号"),
    "RECOVERY": ("熊末→牛初（底部已确认）", "满足底部确认条件，到收复上一轮新高之前都在这个阶段"),
}


def _rp(raw, band):
    s, r = raw.get(f"s_{band}"), raw.get(f"r_{band}")
    if s is None or r is None:
        return pd.Series(np.nan, index=raw.index)
    return (r / s).where(s > 1)


def _rp_diff(raw, a, b):
    if any(raw.get(f"{x}_{y}") is None for x in "sr" for y in (a, b)):
        return pd.Series(np.nan, index=raw.index)
    s = raw[f"s_{a}"] - raw[f"s_{b}"]
    r = raw[f"r_{a}"] - raw[f"r_{b}"]
    return (r / s).where(s > 1)


def _days(idx, ref):
    return (pd.Series(idx, index=idx) - pd.to_datetime(pd.Series(ref.values, index=idx))).dt.days


def features(raw):
    p = raw["price"]
    F = pd.DataFrame(index=raw.index)
    F["price"] = p
    F["ath"] = p.cummax()
    F["dd"] = p / F.ath - 1
    is_ath = p >= F.ath
    last_ath = pd.Series(np.where(is_ath, raw.index, pd.NaT), index=raw.index).ffill()
    F["d_ath"] = _days(raw.index, last_ath)
    # 本轮（上一次新高以来）的最低收盘与日期
    grp = is_ath.cumsum()
    F["cyc_low"] = p.groupby(grp).cummin()
    low_day = pd.Series(np.where(p <= F.cyc_low, raw.index, pd.NaT), index=raw.index).groupby(grp).ffill()
    F["d_low"] = _days(raw.index, low_day)
    F["rebound"] = p / F.cyc_low - 1
    prev_h = pd.Series([HALVINGS[HALVINGS <= t].max() if (HALVINGS <= t).any() else pd.NaT for t in raw.index], index=raw.index)
    F["d_halving"] = _days(raw.index, prev_h)
    # 估值
    F["rp"] = raw["realized_cap"] / raw["supply"]
    F["mvrv"] = p / F.rp
    F["ma200d"] = p.rolling(200, min_periods=150).mean()
    F["ma200w"] = p.rolling(1400, min_periods=1000).mean()
    F["p_200w"] = p / F.ma200w
    # 成本线
    F["sth_rp"], F["lth_rp"], F["tmmp"] = raw.get("sth_rp"), raw.get("lth_rp"), raw.get("tmmp")
    F["rp_1_3m"], F["rp_3_6m"], F["rp_6_12m"] = _rp(raw, "1_3m"), _rp(raw, "3_6m"), _rp(raw, "6_12m")
    F["rp_12_18m"] = _rp(raw, "12_18m")
    if raw.get("s_12_18m") is not None and raw.get("s_18_24m") is not None:
        F["rp_1_2y"] = (raw.r_12_18m + raw.r_18_24m) / (raw.s_12_18m + raw.s_18_24m)
    else:
        F["rp_1_2y"] = np.nan
    F["rp_0_10y"] = _rp(raw, "under_10y")
    F["rp_6m_10y"] = _rp_diff(raw, "over_6m", "over_10y")
    F["green_black"] = F.rp_6m_10y / F.rp_0_10y
    # 持有者
    F["psip"] = raw.get("psip")
    if raw.get("lth_supply") is not None and raw.get("s_over_7y") is not None:
        F["lth_share_ex7y"] = (raw.lth_supply - raw.s_over_7y) / (raw.supply - raw.s_over_7y)
    else:
        F["lth_share_ex7y"] = np.nan
    F["pl_365"] = raw.get("profit_1y") / raw.get("loss_1y") if raw.get("profit_1y") is not None else np.nan
    age = (raw.index - GENESIS).days
    if raw.get("cdd") is not None:
        F["cvdd"] = (raw.cdd.fillna(0) * p).cumsum() / (age * 6_000_000)
        F["balanced"] = F.rp - (raw.cdd.fillna(0) * p).cumsum() / (raw.supply * age)
    else:
        F["cvdd"] = F["balanced"] = np.nan
    return F


def _since_ath(flag, F):
    """自上一次新高以来，flag 有没有出现过"""
    grp = (F.price >= F.ath).cumsum()
    return flag.fillna(False).astype(int).groupby(grp).cummax().astype(bool)


def signals(F):
    S = pd.DataFrame(index=F.index)
    mem = lambda x: x.fillna(False).astype(int).rolling(30, min_periods=1).max().astype(bool)   # 30 天记忆，减少来回跳
    # 底部区（§3.4 规则 10、3、12，§2.4，§3.5 规则 21）
    S["Z_盈利供应<50%"] = mem(F.psip < 0.5)
    S["Z_利润365<亏损365"] = mem(F.pl_365 < 1)
    S["Z_MVRV<1"] = mem(F.mvrv < 1)
    S["Z_价<200周均"] = mem(F.p_200w < 1)
    S["Z_LTH占比>75%"] = mem(F.lth_share_ex7y > 0.75)
    S["Z_价≤1.3×CVDD"] = mem(F.price <= 1.3 * F.cvdd)
    zc = [c for c in S.columns if c.startswith("Z_")]
    S["zone_n"] = S[zc].sum(axis=1)
    # 底部确认（§2.5、§3.4 规则 1/2、§3.5 规则 16/17/20/22）
    four = (F.price > F.rp_3_6m) & (F.price > F.rp_1_3m) & (F.price > F.ma200d) & (F.price > F.sth_rp)
    S["C_底后+40%且过90天"] = (F.rebound >= 0.40) & (F.d_low >= 90)
    S["C_四大名右7天"] = four.rolling(7).sum() >= 7
    S["C_6-12M死叉12-18M(本轮)"] = _since_ath(F.rp_6_12m < F.rp_12_18m, F)
    S["C_三叉第三叉(本轮)"] = _since_ath(F.rp_6_12m < F.rp_1_2y, F)
    S["C_绿黑比≥1(本轮)"] = _since_ath(F.green_black >= 1, F)
    S["C_STH成本<LTH成本(本轮)"] = _since_ath(F.sth_rp < F.lth_rp, F)
    S["confirm_n"] = S[["C_6-12M死叉12-18M(本轮)", "C_三叉第三叉(本轮)", "C_绿黑比≥1(本轮)", "C_STH成本<LTH成本(本轮)"]].sum(axis=1)
    # 顶部风险（§2.1 减半到顶 525~546 天，§2.4 高估区 2018 年后）
    S["T_减半后480~600天"] = F.d_halving.between(480, 600)
    S["T_MVRV≥2且价/200周均≥2"] = mem((F.mvrv >= 2) & (F.p_200w >= 2))
    return S


def run_states(F, S):
    """逐日推进的状态机（带滞后，避免来回跳）。
    规则（全部用研究阶段的结论，不另调参）：
      新高 → 牛市；处在“减半后 480~600 天”或“MVRV≥2 且 价/200 周均≥2（30 天内出现过）”→ 牛市·顶部风险区
      牛市里回撤 ≥20% → 牛市回撤·待确认；回撤收窄到 10% 以内 → 回到牛市
      回撤 ≥35% 且新高已过 90 天 且 已过减半后 450 天 → 熊市（减半后 450 天前的深跌，按历史都是牛市中途回撤，§2.1）
      熊市里“底部区”信号 ≥2 条 → 熊底区
      熊市 / 熊底区里：离最低点 +40% 且最低点已过 90 天（§2.5），或“四大名右”连续 7 天且本轮至少出现过 1 条分龄底部确认 → 熊末→牛初
      熊末→牛初里收盘跌破本轮最低收盘 → 退回熊市 / 熊底区
    """
    st = []
    cur = "BULL"
    for i, t in enumerate(F.index):
        f, s = F.iloc[i], S.iloc[i]
        risk = bool(s["T_减半后480~600天"] or s["T_MVRV≥2且价/200周均≥2"])
        if f.price >= f.ath:
            cur = "BULL_RISK" if risk else "BULL"
        elif cur in ("BULL", "BULL_RISK"):
            if f.dd <= -0.20:
                cur = "BULL_PULLBACK"
            else:
                cur = "BULL_RISK" if risk else "BULL"
        elif cur == "BULL_PULLBACK":
            if f.dd > -0.10:
                cur = "BULL_RISK" if risk else "BULL"
        if cur == "BULL_PULLBACK" and f.dd <= -0.35 and f.d_ath >= 90 and f.d_halving >= 450:
            cur = "BEAR"
        if cur in ("BEAR", "BEAR_ZONE"):
            cur = "BEAR_ZONE" if s.zone_n >= 2 else "BEAR"
            if s["C_底后+40%且过90天"] or (s["C_四大名右7天"] and s.confirm_n >= 1):
                cur = "RECOVERY"
        elif cur == "RECOVERY":
            if f.d_low == 0 and i > 0 and f.price < F.cyc_low.iloc[i - 1]:
                cur = "BEAR_ZONE" if s.zone_n >= 2 else "BEAR"
        st.append(cur)
    return pd.Series(st, index=F.index, name="state")
