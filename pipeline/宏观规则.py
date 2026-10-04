# -*- coding: utf-8 -*-
"""宏观四层框架 · 指标注册表 + 读数规则 + 解读日志生成（纯函数，不联网）

四层框架：
  第一层 宏观流动性  周到月：波动、节奏和风险预算（调速器，不是方向盘；方向看 L2）
  第二层 周期定位    周级别：现在贵不贵、在周期哪一段
  第三层 筹码结构    周/日级别：谁在进出交易所
  第四层 情绪衍生品  日内级别：短期会不会超调

L1 自 2026-10-02 起按《L1 宏观层数据维度规格》（依据《BTC 全周期宏观相关性与归因研究》）重做：
  乐观度（纳指 13 周 / VIX / 综合 z）+ 信用（BAA / NFCI / 高收益利差）+ 实际利率四态 → 情境格 → 顺风 / 中性 / 中性偏谨慎 / 逆风；
  净流动性 × 美元只做「打折闸门」；稳定币改用「剔除支付机构」「交易子弹」两条线 + ETF 4 周（滞后顺势，不作反向信号）。
  规则改动记在 RULE_CHANGES，页面「更正记录」原样展示；已写入的历史日志不改。

每个指标 = 一条「判定序列」（拉数原始序列或由它派生，比如 13 周变化）+ 一张区间表（cuts）。
页面上的读数、区间、90 天小图、点进去的全历史走势和「正常波动范围」都来自同一条判定序列，口径一致。
规则只描述读数所处的区间，不输出买卖建议。

日志三件套（写日志.py 调用，写进 data/解读日志/，写入后冻结）：daily_log / weekly_review / monthly_review
日志里同时存中文和英文字段（…EN），英文站直接读。
"""
import bisect
import datetime as dt
import math

LAYERS = {
    1: {"名称": "宏观流动性", "EN": "Macro Liquidity", "问": "风险预算该松还是紧", "问EN": "How much risk budget",
        "频率": "周到月", "频率EN": "weeks to months"},
    2: {"名称": "周期定位", "EN": "Cycle Position", "问": "现在贵不贵", "问EN": "Cheap or expensive",
        "频率": "周级别", "频率EN": "weekly"},
    3: {"名称": "筹码结构", "EN": "Coin Flows", "问": "谁在进出交易所", "问EN": "Who is moving coins on/off exchanges",
        "频率": "周 / 日级别", "频率EN": "weekly / daily"},
    4: {"名称": "情绪衍生品", "EN": "Sentiment & Derivatives", "问": "短期会不会超调", "问EN": "Is it about to overshoot",
        "频率": "日内级别", "频率EN": "intraday"},
}
L1_POSITION = "L1 管周到月的波动、节奏和风险预算，不管方向——它是调速器，不是方向盘；方向先看 L2 周期层，半年尺度两者同等重要。"
L1_POSITION_EN = ("L1 governs volatility, pacing and risk budget over weeks to months, not direction — it is the throttle, "
                  "not the steering wheel. Direction comes from L2 (cycle); at a six-month horizon both matter equally.")


def shift(d, n):
    return (dt.date.fromisoformat(d) + dt.timedelta(days=n)).isoformat()


def days_between(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


# ---------------------------------------------------------------- 格式化
def f_usd(v):
    if v is None:
        return "—"
    a, s = abs(v), "-" if v < 0 else ""
    if a >= 1e12:
        return f"{s}${a/1e12:.2f}T"
    if a >= 1e9:
        return f"{s}${a/1e9:.2f}B"
    if a >= 1e6:
        return f"{s}${a/1e6:.2f}M"
    if a >= 1e3:
        return f"{s}${a/1e3:.1f}K"
    return f"{s}${a:,.0f}"


def f_signed_usd(v):
    return "—" if v is None else ("+" if v > 0 else "") + f_usd(v)


def f_pct(v, dp=1, signed=False):
    if v is None:
        return "—"
    return f"{'+' if signed and v > 0 else ''}{v:.{dp}f}%"


def f_btc(v, signed=False):
    if v is None:
        return "—"
    return f"{'+' if signed and v > 0 else ''}{v:,.0f} BTC"


FMT = {
    "usd": f_usd,
    "usds": f_signed_usd,
    "pct": lambda v: f_pct(v, 2),
    "pct1": lambda v: f_pct(v, 1),
    "pcts": lambda v: f_pct(v, 2, True),
    "pp": lambda v: "—" if v is None else f"{v:+.2f}pp",
    "x": lambda v: "—" if v is None else f"{v:.2f}",
    "xs": lambda v: "—" if v is None else f"{v:+.2f}",
    "x3": lambda v: "—" if v is None else f"{v:.3f}",
    "int": lambda v: "—" if v is None else f"{v:.0f}",
    "idx": lambda v: "—" if v is None else f"{v:.2f}",
    "btc": f_btc,
    "btcs": lambda v: f_btc(v, True),
    "price": lambda v: "—" if v is None else f"${v:,.0f}",
}


# ---------------------------------------------------------------- 序列工具（全部纯函数，结果按 S 缓存）
def _fri(d):
    x = dt.date.fromisoformat(d)
    return (x + dt.timedelta(days=(4 - x.weekday()) % 7)).isoformat()


def weekly(s):
    """{日期: 值} → {周五: (该周最后一个观测日, 值)}（W-FRI，取当周最后可得值）"""
    out = {}
    for d in sorted(s):
        if s[d] is not None:
            out[_fri(d)] = (d, s[d])
    return out


def wk_combine(fn, *ws):
    keys = set(ws[0])
    for w in ws[1:]:
        keys &= set(w)
    out = {}
    for f in sorted(keys):
        vals = [w[f][1] for w in ws]
        v = fn(*vals)
        if v is not None:
            out[f] = (max(w[f][0] for w in ws), v)
    return out


def chg_weeks(w, mode, n=13):
    """周序列 → {观测日: n 周变化}。mode: log（对数涨跌 %）、pct（%）、diff（差值）。"""
    out = {}
    for f, (d, v) in w.items():
        p = w.get(shift(f, -7 * n))
        if not p or v is None or p[1] is None:
            continue
        v0 = p[1]
        if mode == "diff":
            out[d] = v - v0
        elif v0 and v0 > 0 and v > 0:
            out[d] = math.log(v / v0) * 100 if mode == "log" else (v / v0 - 1) * 100
    return out


def daily_back(s, n, mode="pct", tol=None):
    """每个观测日对 n 天前（≤ 且误差 ≤ tol 天）的变化。"""
    ds = sorted(d for d in s if s[d] is not None)
    tol = tol if tol is not None else max(4, n // 3)
    out = {}
    for d in ds:
        t = shift(d, -n)
        i = bisect.bisect_right(ds, t) - 1
        if i < 0 or days_between(ds[i], t) > tol:
            continue
        v, v0 = s[d], s[ds[i]]
        if mode == "diff":
            out[d] = v - v0
        elif v0:
            out[d] = (v / v0 - 1) * 100
    return out


def rolling_sum(s, n):
    """日历窗口 (d-n, d] 求和。"""
    ds = sorted(s)
    out, acc, j = {}, 0.0, 0
    for i, d in enumerate(ds):
        acc += s[d] or 0
        lo = shift(d, -n)
        while ds[j] <= lo:
            acc -= s[ds[j]] or 0
            j += 1
        out[d] = acc
    return out


def combine_daily(fn, *ss):
    keys = set(ss[0])
    for s in ss[1:]:
        keys &= set(s)
    out = {}
    for d in sorted(keys):
        v = fn(*[s[d] for s in ss])
        if v is not None:
            out[d] = v
    return out


def expanding_z(vals, start, min_n=52):
    """[(key, v)] 升序 → {key: z}，只用 start 之后、截至当期（含）的数据（无前视）。"""
    out, n, mean, m2 = {}, 0, 0.0, 0.0
    for k, v in vals:
        if k < start or v is None:
            continue
        n += 1
        dlt = v - mean
        mean += dlt / n
        m2 += dlt * (v - mean)
        if n >= min_n:
            sd = math.sqrt(m2 / (n - 1))
            if sd > 0:
                out[k] = (v - mean) / sd
    return out


_CACHE = {"sid": None, "m": {}}


def _memo(S, name, fn):
    if _CACHE["sid"] is not id(S):
        _CACHE["sid"], _CACHE["m"] = id(S), {}
    m = _CACHE["m"]
    if name not in m:
        try:
            m[name] = fn() or {}
        except Exception as e:  # noqa —— 某条派生算挂了只影响这一个指标
            print(f"  派生序列 {name} 计算失败：{type(e).__name__}: {e}")
            m[name] = {}
    return m[name]


def raw(key):
    return lambda S: S.get(key) or {}


# ---- L1 派生序列
def s_ndx13(S):
    return _memo(S, "ndx13", lambda: chg_weeks(weekly(S.get("fred_ndx") or {}), "log"))


def s_t10yie13(S):
    return _memo(S, "t10yie13", lambda: chg_weeks(weekly(S.get("fred_t10yie") or {}), "diff"))


def s_optimism(S):
    """乐观度综合 z：纳指 13 周、−VIX、10 年通胀预期 13 周变化，各自 2011 年起扩张窗口 z 分数后取均值（三项齐全才出值）。"""
    def calc():
        nw = chg_weeks(weekly(S.get("fred_ndx") or {}), "log")
        tw = chg_weeks(weekly(S.get("fred_t10yie") or {}), "diff")
        vw = {d: -v for _, (d, v) in weekly(S.get("fred_vix") or {}).items()}
        # 三条序列按周五对齐
        def by_fri(x):
            return {_fri(d): (d, v) for d, v in x.items()}
        a, b, c = by_fri(nw), by_fri(vw), by_fri(tw)
        zs = []
        for comp in (a, b, c):
            z = expanding_z([(f, v) for f, (d, v) in sorted(comp.items())], "2011-01-01")
            zs.append(z)
        out = {}
        for f in sorted(set(zs[0]) & set(zs[1]) & set(zs[2])):
            d = max(a[f][0], b[f][0], c[f][0])
            out[d] = (zs[0][f] + zs[1][f] + zs[2][f]) / 3
        return out
    return _memo(S, "optimism", calc)


def s_baa13(S):
    return _memo(S, "baa13", lambda: chg_weeks(weekly(S.get("fred_baa10y") or {}), "diff"))


def s_nfci13(S):
    return _memo(S, "nfci13", lambda: chg_weeks(weekly(S.get("fred_nfci") or {}), "diff"))


def s_hy13(S):
    return _memo(S, "hy13", lambda: chg_weeks(weekly(S.get("fred_hy") or {}), "diff"))


def s_real13(S):
    return _memo(S, "real13", lambda: chg_weeks(weekly(S.get("fred_dfii10") or {}), "diff"))


def s_real_state(S):
    """10 年实际利率四态，数值编码：2 急升 / 1 高位平台 / 0 低位平台 / −1 下行（页面只用来画状态图）。"""
    def calc():
        lv = weekly(S.get("fred_dfii10") or {})
        ch = s_real13(S)
        out = {}
        for f, (d, v) in lv.items():
            c = ch.get(d)
            if c is None:
                continue
            out[d] = 2 if c >= 0.40 else (-1 if c <= -0.40 else (1 if v >= 1.0 else 0))
        return out
    return _memo(S, "real_state", calc)


def s_netliq(S):
    """美联储净流动性 = WALCL − WTREGEN − RRPONTSYD（美元），周五对齐。"""
    return _memo(S, "netliq", lambda: {d: v for _, (d, v) in wk_combine(
        lambda a, b, c: a - b - c, weekly(S.get("fred_walcl") or {}), weekly(S.get("fred_tga") or {}),
        weekly(S.get("fred_rrp") or {})).items()})


def s_netliq13(S):
    return _memo(S, "netliq13", lambda: chg_weeks(weekly(s_netliq(S)), "pct"))


def s_usd13(S):
    return _memo(S, "usd13", lambda: chg_weeks(weekly(S.get("fred_broad_usd") or {}), "pct"))


def s_stable_expay(S):
    """稳定币主线（去重）= 全部美元稳定币 − 支付/机构类 − 生息/合成类（后者部分拿 USDT/USDC 抵押铸造，不剔除会重复计算）。
    支付类、生息类在各自出现之前记 0。"""
    def calc():
        tot, pay, yl = S.get("stable_total") or {}, S.get("stable_pay") or {}, S.get("stable_yield") or {}
        if not pay or not yl:
            return {}
        p0, y0 = min(pay), min(yl)
        out = {}
        for d, v in tot.items():
            if (d >= p0 and d not in pay) or (d >= y0 and d not in yl):
                continue
            out[d] = v - pay.get(d, 0) - yl.get(d, 0)
        return out
    return _memo(S, "expay", calc)


def s_stable_bullets(S):
    """交易子弹：交易核心（USDT/USDC/FDUSD/USD1/TUSD/USDD）− Tron 链稳定币总量。"""
    return _memo(S, "bullets", lambda: combine_daily(lambda a, b: a - b, S.get("stable_core") or {}, S.get("stable_tron") or {}))


def s_expay13(S):
    return _memo(S, "expay13", lambda: chg_weeks(weekly(s_stable_expay(S)), "pct"))


def s_bullets13(S):
    return _memo(S, "bullets13", lambda: chg_weeks(weekly(s_stable_bullets(S)), "pct"))


def s_yield13(S):
    return _memo(S, "yield13", lambda: chg_weeks(weekly(S.get("stable_yield") or {}), "pct"))


def s_core13(S):
    return _memo(S, "core13", lambda: chg_weeks(weekly(S.get("stable_core") or {}), "pct"))


def s_tron13(S):
    return _memo(S, "tron13", lambda: chg_weeks(weekly(S.get("stable_tron") or {}), "pct"))


def s_pay13(S):
    return _memo(S, "pay13", lambda: chg_weeks(weekly(S.get("stable_pay") or {}), "pct"))


def w52(level_fn):
    """52 周变化（%），给卡片依据里补一个长周期读数。"""
    return lambda S: _memo(S, "w52:" + level_fn.__name__, lambda: chg_weeks(weekly(level_fn(S)), "pct", 52))


def lv(key):
    def f(S):
        return S.get(key) or {}
    f.__name__ = "lv_" + key
    return f


def s_btc13(S):
    return _memo(S, "btc13", lambda: chg_weeks(weekly(S.get("btc_price") or {}), "log"))


def s_etf28(S):
    return _memo(S, "etf28", lambda: rolling_sum(S.get("etf_flow") or {}, 28) if S.get("etf_flow") else {})


def s_etf13(S):
    return _memo(S, "etf13", lambda: rolling_sum(S.get("etf_flow") or {}, 91) if S.get("etf_flow") else {})


def s_btc_ndx_corr(S):
    """BTC − 纳指 52 周滚动相关（周对数收益，只用已结束的周）。"""
    def calc():
        b, n = weekly(S.get("btc_price") or {}), weekly(S.get("fred_ndx") or {})
        fs = sorted(set(b) & set(n))
        rb, rn, keys = [], [], []
        for f0, f1 in zip(fs, fs[1:]):
            if days_between(f0, f1) != 7:
                continue
            if b[f1][1] > 0 and b[f0][1] > 0 and n[f1][1] > 0 and n[f0][1] > 0:
                rb.append(math.log(b[f1][1] / b[f0][1]))
                rn.append(math.log(n[f1][1] / n[f0][1]))
                keys.append(f1)
        out = {}
        for i in range(51, len(keys)):
            x, y = rb[i - 51:i + 1], rn[i - 51:i + 1]
            mx, my = sum(x) / 52, sum(y) / 52
            sxy = sum((a - mx) * (c - my) for a, c in zip(x, y))
            sx = math.sqrt(sum((a - mx) ** 2 for a in x))
            sy = math.sqrt(sum((c - my) ** 2 for c in y))
            if sx and sy and keys[i] <= max(S.get("fred_ndx") or {"": ""}):
                out[keys[i]] = sxy / sx / sy
        return out
    return _memo(S, "btcndx", calc)


def s_tokstock(S):
    return _memo(S, "tokstock", lambda: combine_daily(lambda a, b: a / b * 100 if b else None,
                                                     S.get("tok_stock_mcap") or {}, S.get("cg_stable_mcap") or {}))


# ---- L2–L4 派生
def s_realized_prem(S):
    return _memo(S, "rprem", lambda: combine_daily(lambda p, r: (p / r - 1) * 100 if r else None,
                                                  S.get("btc_price") or {}, S.get("realized_price") or {}))


def s_netflow7(S):
    return _memo(S, "nf7", lambda: rolling_sum(S.get("ex_netflow") or {}, 7))


def s_exbal30(S):
    return _memo(S, "exbal30", lambda: daily_back(S.get("ex_balance") or {}, 30))


def s_oi7(S):
    return _memo(S, "oi7", lambda: daily_back(S.get("hl_oi") or {}, 7, tol=2))


def s_cum_netflow(S):
    """交易所 BTC 累计净流量（从有数据第一天起累加），只用于画图。"""
    def calc():
        s = S.get("ex_netflow") or {}
        acc, out = 0.0, {}
        for d in sorted(s):
            acc += s[d]
            out[d] = acc
        return out
    return _memo(S, "cumnf", calc)


# ---------------------------------------------------------------- 区间判定
def band(v, cuts):
    """cuts: [(上界, 中文, 英文, tone, 分)...]，最后一个上界 None = +∞。"""
    for c in cuts:
        if c[0] is None or v < c[0]:
            return c[1:]
    return cuts[-1][1:]


def pct_rank(series, v, upto=None):
    vals = [x for d, x in series.items() if x is not None and (upto is None or d <= upto)]
    if len(vals) < 2:
        return None
    vals.sort()
    return bisect.bisect_left(vals, v) / (len(vals) - 1) * 100 if len(vals) > 1 else None


def own_pct_zone(min_n=90):
    """只看自身历史分位的描述读数（期货升水）：样本不够时只记录不判定。"""
    def f(v, ctx):
        hist = {d: x for d, x in ctx["series"].items() if d <= ctx["d"]}
        if len(hist) < min_n:
            return ("记录中", "Recording", "neutral", 0,
                    f"已记录 {len(hist)} 天，满 {min_n} 天后给自身历史分位", f"{len(hist)} days recorded; percentile after {min_n}")
        p = pct_rank(hist, v)
        z = band(p, [(20, "自身历史低位", "Low vs own history", "cool", 0), (80, "自身历史中段", "Mid-range", "neutral", 0),
                     (None, "自身历史高位", "High vs own history", "warn", 0)])
        return (*z, f"自身历史第 {p:.0f} 百分位", f"{p:.0f}th percentile of own history")
    return f


def classify_real(v, ctx):
    S, d = ctx["S"], ctx["d"]
    lv = weekly(S.get("fred_dfii10") or {})
    level = next((x for f, (dd, x) in lv.items() if dd == d), None)
    if v >= 0.40:
        z = ("急升", "Surging", "dn", 0)
    elif v <= -0.40:
        z = ("下行", "Falling", "up", 0)
    elif level is not None and level >= 1.0:
        z = ("高位平台", "High plateau", "warn", 0)
    else:
        z = ("低位平台", "Low plateau", "neutral", 0)
    lvs = f"{level:.2f}%" if level is not None else "—"
    return (*z, f"水平 {lvs}，13 周 {v:+.2f}pp", f"level {lvs}, 13w {v:+.2f}pp")


def relation_to_price(zone_cuts):
    """稳定币两条线：区间 + 与 BTC 13 周涨跌同向（确认）还是背离（提示）。"""
    def f(v, ctx):
        zh, en, tone, sc = band(v, zone_cuts)
        b = None
        bs = s_btc13(ctx["S"])
        ks = [k for k in bs if k <= ctx["d"]]
        if ks:
            b = bs[max(ks)]
        rel, rel_en = "", ""
        if b is not None and abs(v) >= 1 and abs(b) >= 3:
            same = (v > 0) == (b > 0)
            rel, rel_en = ("·与价格同向（确认）", " · confirms price") if same else ("·与价格背离（提示）", " · diverges from price")
            if not same:
                tone = "warn"
        bt = f"，BTC 13 周 {b:+.1f}%" if b is not None else ""
        bte = f", BTC 13w {b:+.1f}%" if b is not None else ""
        return (zh + rel, en + rel_en, tone, sc, f"13 周 {v:+.2f}%{bt}", f"13w {v:+.2f}%{bte}")
    return f


# ---------------------------------------------------------------- 指标注册表（顺序即页面顺序）
# 级别：核心 = 进层判定；辅助 = 展示 + 只做记录；观察 = 测过但没达到可用标准，只看不用
# 等级（L1）：已验证 > 已验证·方向 > 描述读数 > 监控；只有「已验证」可以直接影响仓位参数
STABLE_CUTS = [(-1, "收缩", "Contracting", "dn", 0), (1, "持平", "Flat", "neutral", 0), (None, "扩张", "Expanding", "up", 0)]
G_SC = ("L1-B 加密资金通道 · 稳定币（只确认、不预测）", "L1-B crypto funding channels · stablecoins (confirm, don't predict)")
G_ETF = ("L1-B 加密资金通道 · 现货 ETF", "L1-B crypto funding channels · spot ETFs")
G_FUT = ("L1-B 加密资金通道 · 期货升水（两条并列）", "L1-B crypto funding channels · futures basis (side by side)")
G_SEP = ("L1-B 加密资金通道 · 单列观察（不计入）", "L1-B crypto funding channels · watched separately (not counted)")
ETF_CUTS = [(0, "趋势确认（滞后）· 净流出", "Trend confirm (lagging) · outflow", "dn", 0),
            (None, "趋势确认（滞后）· 净流入", "Trend confirm (lagging) · inflow", "up", 0)]
ETF_TXT = ("美国现货 BTC ETF 净流入合计。ETF 资金里有散户和基差套利资金，不等于机构看多；大幅流出后没有反弹规律，不作抄底信号。"
           "日度资金流和过去 3 日涨跌相关 0.60，和未来 1~10 日约 0.05；极端流出周之后 4 周平均 −3.5%（基准 +1.9%，p=0.20），极端流入周之后 +6.6%（p=0.30，不显著）。")
ETF_TXT_EN = ("US spot BTC ETF net flows. ETF money includes retail and basis-trade funds — it does not mean institutions are bullish; "
              "there is no rebound pattern after big outflows, so it is never a bottom signal. Daily flows correlate 0.60 with the past 3 days of price and ~0.05 with the next 1–10; "
              "four weeks after extreme outflow weeks averaged −3.5% (baseline +1.9%, p=0.20), after extreme inflows +6.6% (p=0.30, not significant).")
BASIS_TXT = "同概念不同市场：CME 是美国机构与基差套利，Deribit 是加密原生杠杆，绝对值常差几个百分点，只看各自方向和历史分位。"
BASIS_TXT_EN = "Same concept, different markets: CME is US institutions and basis trades, Deribit is crypto-native leverage; levels often differ by several points — read each one's direction and own percentile only."

INDICATORS = [
    # ================= 第一层：宏观流动性
    {"key": "ndx13", "层": 1, "组": "乐观度 · 美股腿", "组EN": "Optimism · equity leg", "级别": "核心", "等级": "已验证",
     "名称": "纳指 100 · 13 周涨跌", "EN": "Nasdaq-100 · 13w change", "series": s_ndx13, "fmt": "pcts", "freq": "w",
     "来源": "FRED · NASDAQ100", "滞后": 7, "raw": "fred_ndx", "rawfmt": "idx",
     "cuts": [(0, "偏弱", "Weak", "dn", 0), (None, "乐观", "Optimistic", "up", 0)],
     "说明": "美股乐观度第一指标：ln(纳指 / 13 周前纳指)。和「乐观共同因子」相关 0.95，L1 里排第一位。>0 = 乐观。",
     "说明EN": "First optimism gauge: ln(NDX / NDX 13 weeks ago). Correlates 0.95 with the common optimism factor. >0 = optimistic.",
     "依据": "13 周对数涨跌", "依据EN": "13-week log change"},
    {"key": "vix", "层": 1, "组": "乐观度 · 美股腿", "组EN": "Optimism · equity leg", "级别": "核心", "等级": "已验证",
     "名称": "VIX 恐慌指数", "EN": "VIX", "series": raw("fred_vix"), "fmt": "x", "freq": "d",
     "来源": "FRED · VIXCLS", "滞后": 6,
     "cuts": [(20, "平稳", "Calm", "up", 0), (None, "转弱（>20）", "Risk-off (>20)", "dn", 0)],
     "说明": "美股隐含波动率。BTC 跟跌不跟涨：VIX 跳升那几周 BTC 往往跌得比纳指还多。>20 视为乐观度转弱。",
     "说明EN": "US equity implied volatility. BTC follows the downside more than the upside, so a VIX spike usually hurts it more than the Nasdaq. >20 = optimism weakening.",
     "依据": "水平", "依据EN": "level"},
    {"key": "optimism_z", "层": 1, "组": "乐观度 · 美股腿", "组EN": "Optimism · equity leg", "级别": "核心", "等级": "已验证·方向",
     "名称": "乐观度综合 z", "EN": "Optimism composite z", "series": s_optimism, "fmt": "xs", "freq": "w",
     "来源": "FRED（自算）", "滞后": 7,
     "cuts": [(0, "乐观度弱", "Weak", "dn", 0), (None, "乐观度强", "Strong", "up", 0)],
     "说明": "纳指 13 周、VIX 取负、10 年通胀预期（T10YIE）13 周变化，三项各自从 2011 年起做扩张窗口 z 分数（不偷看未来）再取平均。>0 = 比历史平均乐观。",
     "说明EN": "Mean of expanding-window z-scores (from 2011, no look-ahead) of Nasdaq 13w change, −VIX and the 13w change in 10y breakeven inflation. >0 = more optimistic than average.",
     "依据": "三项 z 均值", "依据EN": "mean of 3 z-scores"},
    {"key": "baa13", "层": 1, "组": "乐观度 · 信用腿", "组EN": "Optimism · credit leg", "级别": "核心", "等级": "已验证",
     "名称": "BAA 信用利差 · 13 周变化", "EN": "BAA credit spread · 13w change", "series": s_baa13, "fmt": "pp", "freq": "w",
     "来源": "FRED · BAA10Y", "滞后": 7, "raw": "fred_baa10y", "rawfmt": "pct",
     "cuts": [(0, "信用收窄", "Narrowing", "up", 0), (None, "信用走阔", "Widening", "dn", 0)],
     "说明": "穆迪 BAA 公司债 − 10 年美债。信用腿主指标：2011 年以来和乐观共同因子相关 0.89，有全历史。13 周上升 = 走阔（悲观）。",
     "说明EN": "Moody's BAA corporate yield minus 10y Treasury. Main credit gauge, 0.89 correlation with the optimism factor since 2011. Rising over 13w = widening (pessimistic).",
     "依据": "13 周变化", "依据EN": "13-week change"},
    {"key": "nfci13", "层": 1, "组": "乐观度 · 信用腿", "组EN": "Optimism · credit leg", "级别": "核心", "等级": "已验证·方向",
     "名称": "金融条件 NFCI · 13 周变化", "EN": "NFCI · 13w change", "series": s_nfci13, "fmt": "xs", "freq": "w",
     "来源": "FRED · NFCI（周度）", "滞后": 13, "raw": "fred_nfci", "rawfmt": "x3",
     "cuts": [(0, "放松", "Easing", "up", 0), (None, "收紧", "Tightening", "dn", 0)],
     "说明": "芝加哥联储金融条件指数，0 以下 = 比历史平均宽松。13 周上升 = 收紧。每周三公布上周五的值。",
     "说明EN": "Chicago Fed National Financial Conditions Index; below 0 = looser than average. Rising over 13w = tightening. Published Wednesdays for the prior Friday.",
     "依据": "13 周变化", "依据EN": "13-week change"},
    {"key": "hy13", "层": 1, "组": "乐观度 · 信用腿", "组EN": "Optimism · credit leg", "级别": "辅助", "等级": "描述读数",
     "名称": "高收益利差 · 13 周变化", "EN": "High-yield spread · 13w change", "series": s_hy13, "fmt": "pp", "freq": "w",
     "来源": "FRED · BAMLH0A0HYM2", "滞后": 7, "raw": "fred_hy", "rawfmt": "pct",
     "cuts": [(-0.30, "快速收窄", "Narrowing fast", "up", 0), (0.30, "平稳", "Stable", "neutral", 0),
              (None, "快速走阔（先行提示）", "Widening fast (early warning)", "warn", 0)],
     "说明": "垃圾债比国债多付的利息。FRED 只公开近 3 年，没有长历史验证，只作先行提示：快速走阔时盯 BAA / NFCI 会不会跟上。±0.30pp 是本站设的提示阈值，未经回测。",
     "说明EN": "Junk-bond spread over Treasuries. FRED only publishes ~3 years, so it is an early-warning reading only. The ±0.30pp alert band is this site's own, not back-tested.",
     "依据": "13 周变化", "依据EN": "13-week change"},
    {"key": "real13", "层": 1, "组": "实际利率（状态变量）", "组EN": "Real rate (state variable)", "级别": "核心", "等级": "已验证·方向",
     "名称": "10 年实际利率 · 四态", "EN": "10y real yield · 4 states", "series": s_real13, "fmt": "pp", "freq": "w",
     "来源": "FRED · DFII10", "滞后": 7, "raw": "fred_dfii10", "rawfmt": "pct", "classify": classify_real,
     "cuts": [(-0.40, "下行", "Falling", "up", 0), (0.40, "平台", "Plateau", "neutral", 0), (None, "急升", "Surging", "dn", 0)],
     "说明": "从核心指标降为状态变量：13 周 ≥ +0.40pp = 急升，≤ −0.40pp = 下行，其余按水平 ≥1.0% 分高位 / 低位平台。急升本身是独立逆风（2022 年后），要和信用 / 乐观度一起定档。",
     "说明EN": "Now a state variable, not the headline: 13w ≥ +0.40pp = surging, ≤ −0.40pp = falling, otherwise high/low plateau by level ≥1.0%. A surge is an independent headwind since 2022 and is combined with credit/optimism.",
     "依据": "13 周变化 + 水平", "依据EN": "13-week change + level"},
    {"key": "netliq13", "层": 1, "组": "流动性闸门（只打折不加仓）", "组EN": "Liquidity gate (discount only)", "级别": "核心", "等级": "已验证·方向",
     "名称": "美联储净流动性 · 13 周变化", "EN": "Fed net liquidity · 13w change", "series": s_netliq13, "fmt": "pcts", "freq": "w",
     "来源": "FRED · WALCL − WTREGEN − RRPONTSYD", "滞后": 9, "raw": "netliq", "rawfmt": "usd",
     "cuts": [(-2.72, "大幅收缩", "Sharp contraction", "dn", 0), (0, "小幅收缩", "Mild contraction", "neutral", 0),
              (None, "扩张（不加仓）", "Expanding (no add)", "neutral", 0)],
     "说明": "美联储总资产 − 财政部 TGA − 隔夜逆回购。≤ −2.72% 且美元 13 周走强 → 闸门触发（框架里名义风险预算 ×0.7）；扩张时不加仓。2024-05 后领先关系在变弱，2026 年底复核。",
     "说明EN": "Fed assets − Treasury General Account − overnight RRP. ≤ −2.72% with a stronger dollar over 13w trips the gate (risk budget ×0.7 in the framework); expansion never adds. Weakening since 2024-05; review end-2026.",
     "依据": "13 周变化", "依据EN": "13-week change"},
    {"key": "usd13", "层": 1, "组": "流动性闸门（只打折不加仓）", "组EN": "Liquidity gate (discount only)", "级别": "辅助", "等级": "已验证",
     "名称": "广义美元 · 13 周变化", "EN": "Broad dollar · 13w change", "series": s_usd13, "fmt": "pcts", "freq": "w",
     "来源": "FRED · DTWEXBGS", "滞后": 10, "raw": "fred_broad_usd", "rawfmt": "idx",
     "cuts": [(0, "美元走弱", "Weaker", "up", 0), (None, "美元走强", "Stronger", "dn", 0)],
     "说明": "贸易加权美元（对 26 种货币）。只作确认信号，和净流动性组合成闸门，单独不计入判定。",
     "说明EN": "Trade-weighted dollar vs 26 currencies. Confirmation only; combined with net liquidity for the gate.",
     "依据": "13 周变化", "依据EN": "13-week change"},
    # ---- L1-B 加密资金通道（只确认、不预测）：稳定币 → 资金轮动矩阵（页面插在稳定币和 ETF 之间）→ ETF → 期货升水 → 单列观察
    {"key": "stable_expay13", "层": 1, "组": G_SC[0], "组EN": G_SC[1], "级别": "辅助", "等级": "已验证·方向",
     "名称": "稳定币主线（去重）· 13 周", "EN": "Stablecoin main line (de-duplicated) · 13w", "series": s_expay13, "fmt": "pcts",
     "freq": "w", "来源": "DefiLlama（逐币）", "滞后": 9, "raw": "stable_expay", "rawfmt": "usd", "w52": w52(s_stable_expay),
     "classify": relation_to_price(STABLE_CUTS), "cuts": STABLE_CUTS,
     "说明": "= 全部美元稳定币 − 支付 / 机构类（PYUSD、RLUSD、USDG、USDGO、USDP、GUSD、U）− 生息 / 合成类（USDe、USDf、USDS、DAI 等，"
             "部分是拿 USDT / USDC 抵押铸造的，不剔除会重复计算）。不用 USDT+USDC：会漏掉 FDUSD、USD1 等交易用币，也去不掉支付类和重复计算的生息类。"
             "价格先动、稳定币后增，只确认、不埋伏：稳定币增速和过去 13 周 BTC 涨跌相关 0.60，和未来 13 周相关 −0.26。",
     "说明EN": "= all USD stablecoins − payment/institutional coins (PYUSD, RLUSD, USDG, USDGO, USDP, GUSD, U) − yield/synthetic coins "
               "(USDe, USDf, USDS, DAI… partly minted against USDT/USDC, so keeping them double-counts). Not USDT+USDC, which misses FDUSD/USD1 "
               "and keeps the noise. Price moves first, stablecoins follow — confirm, don't front-run: growth correlates 0.60 with the past 13 weeks of BTC and −0.26 with the next 13.",
     "依据": "13 周变化", "依据EN": "13-week change"},
    {"key": "stable_bullets13", "层": 1, "组": G_SC[0], "组EN": G_SC[1], "级别": "辅助", "等级": "已验证·方向",
     "名称": "交易子弹 · 剔除 Tron", "EN": "Trading bullets · ex-Tron", "series": s_bullets13, "fmt": "pcts",
     "freq": "w", "来源": "DefiLlama（逐币 + Tron 链）", "滞后": 9, "raw": "stable_bullets", "rawfmt": "usd", "w52": w52(s_stable_bullets),
     "classify": relation_to_price(STABLE_CUTS), "cuts": STABLE_CUTS,
     "说明": "交易核心（USDT、USDC、FDUSD、USD1、TUSD、USDD）− Tron 链稳定币。ETF 时代和 BTC 13 周相关 0.52，最贴近交易所和主流链上的资金。"
             "价格先动、稳定币后增，只确认、不埋伏。",
     "说明EN": "Trading core (USDT, USDC, FDUSD, USD1, TUSD, USDD) minus all stablecoins on Tron. 0.52 correlation with BTC over 13 weeks in the ETF era — "
               "the closest proxy for exchange-side dry powder. Confirm, don't front-run.",
     "依据": "13 周变化", "依据EN": "13-week change"},
    {"key": "stable_core13", "层": 1, "组": G_SC[0], "组EN": G_SC[1], "级别": "辅助", "等级": "描述读数",
     "名称": "交易子弹 · 含 Tron（并列口径）", "EN": "Trading bullets · incl. Tron (parallel)", "series": s_core13, "fmt": "pcts",
     "freq": "w", "来源": "DefiLlama（逐币）", "滞后": 9, "raw": "stable_core", "rawfmt": "usd", "w52": w52(lv("stable_core")),
     "cuts": STABLE_CUTS,
     "说明": "交易核心不剔除 Tron。Tron 上的 USDT 有汇款支付，也有场外入金和交易所放在 Tron 上的币，链上分不开，所以含 Tron、剔除 Tron 两种口径并列看。",
     "说明EN": "Trading core without removing Tron. Tron USDT mixes remittances with OTC on-ramps and exchange hot wallets, which cannot be separated on-chain — so both lenses are shown.",
     "依据": "13 周变化", "依据EN": "13-week change"},
    {"key": "stable_yield13", "层": 1, "组": G_SC[0], "组EN": G_SC[1], "级别": "辅助", "等级": "描述读数",
     "名称": "生息 / 合成稳定币 · 13 周", "EN": "Yield / synthetic stablecoins · 13w", "series": s_yield13, "fmt": "pcts",
     "freq": "w", "来源": "DefiLlama（逐币）", "滞后": 9, "raw": "stable_yield", "rawfmt": "usd", "w52": w52(lv("stable_yield")),
     "cuts": [(-1, "杠杆退潮", "Leverage receding", "cool", 0), (1, "持平", "Flat", "neutral", 0), (None, "杠杆扩张", "Leverage building", "warn", 0)],
     "说明": "链上杠杆温度计：收缩 = 杠杆退潮。USDe、USDf、USDS、DAI 等合计（BFUSD 不在 DefiLlama 上），单列观察，不加回主线。",
     "说明EN": "On-chain leverage thermometer: shrinking = leverage receding. USDe, USDf, USDS, DAI… (BFUSD is not on DefiLlama). Shown separately, never added back to the main line.",
     "依据": "13 周变化", "依据EN": "13-week change"},
    {"key": "etf13", "层": 1, "组": G_ETF[0], "组EN": G_ETF[1], "级别": "辅助", "等级": "已验证·方向",
     "名称": "现货 ETF · 近 13 周净流入", "EN": "Spot ETF · 13-week net flow", "series": s_etf13, "fmt": "usds",
     "freq": "d", "来源": "Farside（haturatu 镜像）", "滞后": 5, "raw": "etf_flow", "rawfmt": "usds",
     "cuts": ETF_CUTS, "说明": ETF_TXT, "说明EN": ETF_TXT_EN, "依据": "91 天合计", "依据EN": "91-day sum"},
    {"key": "etf28", "层": 1, "组": G_ETF[0], "组EN": G_ETF[1], "级别": "辅助", "等级": "已验证·方向",
     "名称": "现货 ETF · 近 4 周净流入", "EN": "Spot ETF · 4-week net flow", "series": s_etf28, "fmt": "usds",
     "freq": "d", "来源": "Farside（haturatu 镜像）", "滞后": 5, "raw": "etf_flow", "rawfmt": "usds",
     "cuts": ETF_CUTS, "说明": ETF_TXT, "说明EN": ETF_TXT_EN, "依据": "28 天合计", "依据EN": "28-day sum"},
    {"key": "cme_basis", "层": 1, "组": G_FUT[0], "组EN": G_FUT[1], "级别": "辅助", "等级": "描述读数",
     "名称": "H1 · CME 近月年化升水", "EN": "H1 · CME front-month annualized basis", "series": raw("cme_basis"), "fmt": "pct1",
     "freq": "d", "来源": "Yahoo · CME 近月合约（每天抓一次）", "滞后": 4, "classify": own_pct_zone(),
     "cuts": [(None, "—", "—", "neutral", 0)],
     "说明": "(CME 近月 / 同一时点现货 − 1) × 365 / 剩余天数，到期前约 5 个交易日换下一张；Yahoo 每天只在日更时抓一次。" + BASIS_TXT,
     "说明EN": "(CME front month / spot at the same moment − 1) × 365 / days to expiry, rolling ~5 trading days before expiry; fetched once a day. " + BASIS_TXT_EN,
     "依据": "自身历史分位", "依据EN": "own-history percentile"},
    {"key": "deribit_basis", "层": 1, "组": G_FUT[0], "组EN": G_FUT[1], "级别": "辅助", "等级": "描述读数",
     "名称": "H2 · Deribit 3 个月年化升水", "EN": "H2 · Deribit 3-month annualized basis", "series": raw("deribit_basis"), "fmt": "pct1",
     "freq": "d", "来源": "Deribit（前后两张插值成固定 90 天）", "滞后": 3, "classify": own_pct_zone(),
     "cuts": [(None, "—", "—", "neutral", 0)],
     "说明": "前后两张交割合约按剩余天数插值成固定 90 天（插不了时取剩余 ≥30 天、最接近 90 天的一张）。" + BASIS_TXT,
     "说明EN": "Two delivery contracts interpolated to a constant 90 days (else the nearest contract with ≥30 days left). " + BASIS_TXT_EN,
     "依据": "自身历史分位", "依据EN": "own-history percentile"},
    {"key": "stable_tron13", "层": 1, "组": G_SEP[0], "组EN": G_SEP[1], "级别": "辅助", "等级": "监控",
     "名称": "Tron 链稳定币 · 13 周", "EN": "Stablecoins on Tron · 13w", "series": s_tron13, "fmt": "pcts",
     "freq": "w", "来源": "DefiLlama（按链）", "滞后": 9, "raw": "stable_tron", "rawfmt": "usd", "w52": w52(lv("stable_tron")),
     "cuts": [(-1, "收缩", "Contracting", "neutral", 0), (1, "持平", "Flat", "neutral", 0), (None, "扩张", "Expanding", "neutral", 0)],
     "说明": "Tron 是混合用途：汇款支付、场外入金、交易所放在 Tron 上的币都有。已含在主线（去重）里，只在「交易子弹」里剔除。"
             "与 BTC 周度相关 0.00、13 周 0.15（2022–2026 全段 13 周 0.55）。",
     "说明EN": "Tron is mixed-use (remittances, OTC on-ramps, exchange wallets). Included in the main line, removed only from trading bullets. "
               "Correlation with BTC: 0.00 weekly, 0.15 over 13 weeks (0.55 over 2022–2026).",
     "依据": "13 周变化", "依据EN": "13-week change"},
    {"key": "stable_pay13", "层": 1, "组": G_SEP[0], "组EN": G_SEP[1], "级别": "辅助", "等级": "监控",
     "名称": "支付 / 机构稳定币 · 13 周", "EN": "Payment / institutional stablecoins · 13w", "series": s_pay13, "fmt": "pcts",
     "freq": "w", "来源": "DefiLlama（逐币）", "滞后": 9, "raw": "stable_pay", "rawfmt": "usd", "w52": w52(lv("stable_pay")),
     "cuts": [(-1, "收缩", "Contracting", "neutral", 0), (1, "持平", "Flat", "neutral", 0), (None, "扩张", "Expanding", "neutral", 0)],
     "说明": "支付机构稳定币不是交易资金：一年变成 2.8 倍，与 BTC 13 周相关 −0.43（BTC 弱时反而增长）。不计入主线。",
     "说明EN": "Payment stablecoins are not trading money: 2.8× in a year, −0.43 correlation with BTC over 13 weeks (they grow when BTC is weak). Excluded from the main line.",
     "依据": "13 周变化", "依据EN": "13-week change"},
    {"key": "btc_ndx_corr", "层": 1, "组": "联动与监控", "组EN": "Linkage & monitoring", "级别": "辅助", "等级": "描述读数",
     "名称": "BTC − 纳指 52 周滚动相关", "EN": "BTC–Nasdaq 52w rolling correlation", "series": s_btc_ndx_corr, "fmt": "x", "freq": "w",
     "来源": "CoinMetrics + FRED（自算）", "滞后": 10,
     "cuts": [(0.2, "低相关（纳指类规则降权）", "Low (down-weight Nasdaq rules)", "warn", 0), (None, "正常联动", "Normal linkage", "neutral", 0)],
     "说明": "周对数收益的 52 周滚动相关。明显下降时，纳指 13 周和「跟跌不跟涨」规则要降权；2024 年曾回落到 ≈0。0.2 是本站设的提示线。",
     "说明EN": "52-week rolling correlation of weekly log returns. When it drops, Nasdaq-based rules lose weight; it fell to ~0 in 2024. 0.2 is this site's alert line.",
     "依据": "52 周相关", "依据EN": "52-week correlation"},
    {"key": "tokstock", "层": 1, "组": "联动与监控", "组EN": "Linkage & monitoring", "级别": "辅助", "等级": "监控",
     "名称": "美股代币化 / 稳定币市值", "EN": "Tokenized stocks / stablecoin cap", "series": s_tokstock, "fmt": "pct", "freq": "d",
     "来源": "CoinGecko 类目快照", "滞后": 3,
     "cuts": [(3, "未达纳入门槛", "Below threshold", "neutral", 0), (None, "超过 3%（需纳入稳定币口径调整）", "Above 3% (adjust stablecoin lines)", "warn", 0)],
     "说明": "买美股代币时稳定币一般流到发行方换成美元，会减少稳定币供给。规模 >稳定币 3% 或成交 >5% 才纳入稳定币口径调整，现在只记录。",
     "说明EN": "Buying tokenized stocks usually drains stablecoins to the issuer. Only above 3% of stablecoin cap (or 5% of volume) does it enter the stablecoin adjustment; recorded only.",
     "依据": "市值占比", "依据EN": "cap ratio"},
    {"key": "fred_t10y2y", "层": 1, "组": "观察项（测过，未达可用标准）", "组EN": "Watch only (tested, not usable)", "级别": "观察", "等级": "观察项",
     "名称": "2Y / 10Y 利差", "EN": "2Y/10Y curve", "series": raw("fred_t10y2y"), "fmt": "pct", "freq": "d",
     "来源": "FRED · T10Y2Y", "滞后": 6,
     "cuts": [(0, "倒挂", "Inverted", "neutral", 0), (None, "正常", "Normal", "neutral", 0)],
     "说明": "周度变化和 BTC 相关只有 0.06；倒挂期 BTC 反而更好，和「倒挂=衰退=利空」方向相反，独立样本约 18 段。只做观察，不定参数。",
     "说明EN": "Weekly correlation with BTC only 0.06; BTC did better during inversions, the opposite of the folk rule. ~18 independent samples. Watch only.",
     "依据": "水平", "依据EN": "level"},

    # ================= 第二层：周期定位
    {"key": "mvrv", "层": 2, "级别": "核心", "名称": "MVRV", "EN": "MVRV", "series": raw("mvrv"), "fmt": "x", "freq": "d",
     "来源": "CoinMetrics", "滞后": 3,
     "cuts": [(1.0, "低估·历史底部区", "Undervalued · bottom zone", "cool", 2), (1.5, "偏低", "Low", "cool", 1), (2.4, "合理", "Fair", "neutral", 0),
              (3.2, "偏热", "Warm", "warn", -1), (None, "过热·历史顶部区", "Overheated · top zone", "dn", -2)],
     "说明": "市值 / 已实现市值 = 全网平均浮盈倍数。", "说明EN": "Market cap / realized cap = average paper-profit multiple of all coins.",
     "依据": "水平", "依据EN": "level"},
    {"key": "mvrv_z", "层": 2, "级别": "核心", "名称": "MVRV Z-Score", "EN": "MVRV Z-Score", "series": raw("mvrv_z"), "fmt": "x", "freq": "d",
     "来源": "CoinMetrics（自算）", "滞后": 3,
     "cuts": [(0, "底部区", "Bottom zone", "cool", 2), (1.5, "偏低", "Low", "cool", 1), (3, "合理", "Fair", "neutral", 0),
              (5, "偏热", "Warm", "warn", -1), (None, "过热·顶部区", "Overheated · top zone", "dn", -2)],
     "说明": "（市值 − 已实现市值）÷ 市值历史标准差，把 MVRV 标准化到跨周期可比。",
     "说明EN": "(Market cap − realized cap) ÷ historical std-dev of market cap — MVRV normalised across cycles.",
     "依据": "水平", "依据EN": "level"},
    {"key": "realized_price", "层": 2, "级别": "核心", "名称": "Realized Price（现价溢价）", "EN": "Realized Price (spot premium)",
     "series": s_realized_prem, "fmt": "pcts", "freq": "d", "来源": "CoinMetrics（自算）", "滞后": 3, "raw": "realized_price", "rawfmt": "price",
     "cuts": [(0, "现价跌破成本线", "Below cost basis", "cool", 0), (30, "贴近成本线", "Near cost basis", "cool", 0),
              (140, "合理溢价", "Fair premium", "neutral", 0), (None, "高溢价", "High premium", "warn", 0)],
     "说明": "全网持币成本均价（价格 ÷ MVRV）。现价跌破它 = 全网平均浮亏，历史上是大底区。这里判定的是现价相对它的溢价。",
     "说明EN": "Network-wide average cost basis (price ÷ MVRV). Spot below it = the average holder is under water, historically a major bottom zone. Judged on spot's premium over it.",
     "依据": "现价溢价", "依据EN": "spot premium"},
    {"key": "nupl", "层": 2, "级别": "核心", "名称": "NUPL", "EN": "NUPL", "series": raw("nupl"), "fmt": "x3", "freq": "d",
     "来源": "CoinMetrics（自算）", "滞后": 3,
     "cuts": [(0, "投降", "Capitulation", "cool", 0), (0.25, "希望 / 恐惧", "Hope / fear", "cool", 0), (0.5, "乐观 / 焦虑", "Optimism / anxiety", "neutral", 0),
              (0.75, "信念 / 否认", "Belief / denial", "warn", 0), (None, "狂热", "Euphoria", "dn", 0)],
     "说明": "净未实现盈亏 = 1 − 1/MVRV，和 MVRV 高度相关，看情绪阶段用，不重复计分。",
     "说明EN": "Net unrealized profit/loss = 1 − 1/MVRV. Same source as MVRV, used for sentiment phase only, not scored twice.",
     "依据": "水平", "依据EN": "level"},
    {"key": "mayer", "层": 2, "级别": "辅助", "名称": "Mayer Multiple", "EN": "Mayer Multiple", "series": raw("mayer"), "fmt": "x", "freq": "d",
     "来源": "CoinMetrics（自算）", "滞后": 3,
     "cuts": [(0.8, "深度低估", "Deeply undervalued", "cool", 0), (1.0, "低于 200 日线", "Below 200DMA", "cool", 0), (1.5, "合理", "Fair", "neutral", 0),
              (2.4, "偏热", "Warm", "warn", 0), (None, "过热", "Overheated", "dn", 0)],
     "说明": "价格 ÷ 200 日均线。", "说明EN": "Price ÷ 200-day moving average.", "依据": "水平", "依据EN": "level"},
    {"key": "puell", "层": 2, "级别": "辅助", "名称": "Puell Multiple", "EN": "Puell Multiple", "series": raw("puell"), "fmt": "x", "freq": "d",
     "来源": "CoinMetrics（自算）", "滞后": 3,
     "cuts": [(0.5, "矿工投降区", "Miner capitulation", "cool", 0), (1.0, "偏低", "Low", "cool", 0), (2.0, "合理", "Fair", "neutral", 0),
              (3.5, "偏热", "Warm", "warn", 0), (None, "过热", "Overheated", "dn", 0)],
     "说明": "矿工日发行收入 ÷ 365 日均值，矿工视角的周期位置。", "说明EN": "Daily miner issuance revenue ÷ its 365-day average.",
     "依据": "水平", "依据EN": "level"},
    {"key": "pi_cycle", "层": 2, "级别": "辅助", "名称": "Pi Cycle Top", "EN": "Pi Cycle Top", "series": raw("pi_cycle"), "fmt": "x3", "freq": "d",
     "来源": "CoinMetrics（自算）", "滞后": 3,
     "cuts": [(0.9, "远离顶部信号", "Far from top signal", "neutral", 0), (1.0, "接近顶部信号", "Near top signal", "warn", 0),
              (None, "已触发顶部信号", "Top signal triggered", "dn", 0)],
     "说明": "111 日均线 ÷（2 × 350 日均线），≥ 1 即历史顶部信号触发。只用于顶部区警示。",
     "说明EN": "111DMA ÷ (2 × 350DMA); ≥1 has marked past cycle tops. Top-zone warning only.", "依据": "比值", "依据EN": "ratio"},
    # ================= 第三层：筹码结构
    {"key": "ex_netflow", "层": 3, "级别": "核心", "名称": "交易所 BTC 净流量（7 日合计）", "EN": "Exchange BTC net flow (7-day sum)",
     "series": s_netflow7, "fmt": "btcs", "freq": "d", "来源": "CoinMetrics（flash 口径）", "滞后": 3, "raw": "ex_netflow", "rawfmt": "btcs",
     "cuts": [(-10000, "大幅净流出（提币）", "Heavy outflow (withdrawals)", "up", 2), (-2000, "净流出", "Net outflow", "up", 1),
              (2000, "进出均衡", "Balanced", "neutral", 0), (10000, "净流入", "Net inflow", "dn", -1),
              (None, "大幅净流入（抛压）", "Heavy inflow (sell pressure)", "dn", -2)],
     "说明": "流入 − 流出。持续净流出 = 筹码离开交易所（提币囤币），净流入 = 潜在抛压。flash 数据次日可能小幅修订。",
     "说明EN": "Inflow − outflow. Sustained outflow = coins leaving exchanges (hoarding); inflow = potential sell pressure. Flash data may be revised slightly next day.",
     "依据": "7 日合计", "依据EN": "7-day sum"},
    {"key": "ex_balance", "层": 3, "级别": "核心", "名称": "交易所 BTC 余额（30 日变化）", "EN": "Exchange BTC balance (30d change)",
     "series": s_exbal30, "fmt": "pcts", "freq": "d", "来源": "CoinMetrics", "滞后": 21, "raw": "ex_balance", "rawfmt": "btc",
     "cuts": [(-1, "下降（筹码离场）", "Falling (coins leaving)", "up", 0), (1, "持平", "Flat", "neutral", 0),
              (None, "上升（筹码回流）", "Rising (coins returning)", "dn", 0)],
     "说明": "交易所托管的 BTC 总量，看用户行为最直接的存量指标：长期下降 = 持币人把币提回自己钱包。免费档更新约有 2 周滞后，只看趋势，不计分。",
     "说明EN": "Total BTC held on exchanges — the most direct stock measure of holder behaviour. A long decline = holders self-custodying. ~2-week lag on the free tier; trend only, not scored.",
     "依据": "30 日变化", "依据EN": "30-day change"},
    # ================= 第四层：情绪衍生品
    {"key": "fng", "层": 4, "级别": "核心", "名称": "恐慌贪婪指数", "EN": "Fear & Greed Index", "series": raw("fng"), "fmt": "int", "freq": "d",
     "来源": "alternative.me", "滞后": 2,
     "cuts": [(25, "极度恐慌", "Extreme fear", "cool", -2), (45, "恐慌", "Fear", "cool", -1), (56, "中性", "Neutral", "neutral", 0),
              (76, "贪婪", "Greed", "warn", 1), (None, "极度贪婪", "Extreme greed", "dn", 2)],
     "说明": "综合波动、成交、社媒、搜索的情绪温度计。", "说明EN": "Sentiment thermometer from volatility, volume, social and search data.",
     "依据": "水平", "依据EN": "level"},
    {"key": "hl_funding", "层": 4, "级别": "核心", "名称": "BTC 永续资金费率", "EN": "BTC perp funding rate", "series": raw("hl_funding"), "fmt": "pct1",
     "freq": "d", "来源": "Hyperliquid（日均年化）", "滞后": 2,
     "cuts": [(-5, "空头拥挤（易轧空）", "Shorts crowded", "cool", -1), (5, "偏冷", "Cool", "cool", 0), (20, "正常", "Normal", "neutral", 0),
              (40, "多头偏热", "Longs warm", "warn", 1), (None, "多头极度拥挤", "Longs crowded", "dn", 2)],
     "说明": "多空谁在付钱。含约 11% 年化的基准利息（和币安 0.01%/8h 同量级），所以「正常」不是 0。",
     "说明EN": "Who pays whom. Includes ~11% annualized base interest (same order as Binance 0.01%/8h), so 'normal' is not zero.",
     "依据": "年化", "依据EN": "annualized"},
    {"key": "hl_oi", "层": 4, "级别": "核心", "名称": "BTC 未平仓合约（7 日变化）", "EN": "BTC open interest (7d change)", "series": s_oi7, "fmt": "pcts",
     "freq": "d", "来源": "Hyperliquid", "滞后": 2, "raw": "hl_oi", "rawfmt": "usd",
     "cuts": [(-15, "去杠杆", "Deleveraging", "cool", -1), (15, "平稳", "Stable", "neutral", 0), (None, "杠杆快速堆积", "Leverage piling up", "warn", 1)],
     "说明": "链上最大永续所的 BTC 未平仓名义价值，看 7 日变化判断杠杆在堆还是在出清。单一交易所口径。",
     "说明EN": "BTC open interest on the largest on-chain perp venue; the 7-day change shows leverage building or flushing. Single venue.",
     "依据": "7 日变化", "依据EN": "7-day change"},
    {"key": "altseason", "层": 4, "级别": "核心", "名称": "山寨季指数（自建）", "EN": "Altseason index (own)", "series": raw("altseason"), "fmt": "pct1",
     "freq": "d", "来源": "CoinGecko（自算）", "滞后": 2,
     "cuts": [(25, "比特币季", "Bitcoin season", "neutral", 0), (50, "比特币偏强", "BTC leaning", "neutral", 0), (75, "山寨偏强", "Alts leaning", "warn", 0),
              (None, "山寨季", "Altseason", "warn", 0)],
     "说明": "市值前 50（剔除稳定币、包装币、质押衍生品）里 30 日涨幅跑赢 BTC 的占比。原版用 90 日，没有免费接口，这里是自建口径。",
     "说明EN": "Share of the top-50 coins (ex stablecoins, wrapped and staked derivatives) beating BTC over 30 days. Own construction.",
     "依据": "占比", "依据EN": "share"},
    {"key": "btc_dom", "层": 4, "级别": "辅助", "名称": "BTC 市值占比", "EN": "BTC dominance", "series": raw("btc_dom"), "fmt": "pct1", "freq": "d",
     "来源": "CoinGecko", "滞后": 2, "cuts": [(None, "只看趋势", "Trend only", "neutral", 0)],
     "说明": "和山寨季指数交叉验证。", "说明EN": "Cross-check for the altseason index.", "依据": "水平", "依据EN": "level"},
]
IND = {x["key"]: x for x in INDICATORS}

# 派生「原始水平」序列（详情页第二张图用）：key → 函数
RAW_DERIVED = {"netliq": s_netliq, "stable_expay": s_stable_expay, "stable_bullets": s_stable_bullets}

# 框架里有、但暂时没有免费稳定数据源的指标——页面上明示「待接入」和原因，不拿近似值冒充
PENDING = [
    {"层": 2, "名称": "Realized Cap HODL Waves", "EN": "Realized Cap HODL Waves",
     "原因": "需要按 UTXO 年龄分布计算，免费接口不提供；Glassnode 付费或自建节点", "原因EN": "Needs UTXO age distribution; paid Glassnode or own node"},
    {"层": 3, "名称": "URPD 链上筹码分布", "EN": "URPD", "原因": "Glassnode 付费指标；属于框架里标 🔧 的差异化自建方向", "原因EN": "Paid Glassnode metric; planned self-build"},
    {"层": 3, "名称": "STH-MVRV / LTH-MVRV", "EN": "STH-MVRV / LTH-MVRV", "原因": "需要按持有时长拆分已实现市值，Glassnode 付费", "原因EN": "Needs realized cap by holding age; paid"},
    {"层": 3, "名称": "STH-SOPR / aSOPR", "EN": "STH-SOPR / aSOPR", "原因": "Glassnode 付费指标", "原因EN": "Paid Glassnode metric"},
    {"层": 3, "名称": "矿工储备 / 非流动性供给", "EN": "Miner reserves / illiquid supply", "原因": "Glassnode 付费指标", "原因EN": "Paid Glassnode metric"},
    {"层": 4, "名称": "多空比 / 24h 爆仓", "EN": "Long/short ratio / liquidations", "原因": "Coinglass 接口需要 key（免费档可申请），拿到 key 即可接入", "原因EN": "Coinglass needs an API key"},
    {"层": 4, "名称": "期权 Put/Call · IV Skew", "EN": "Options put/call · IV skew", "原因": "Deribit 免费可取，v2 接入", "原因EN": "Free on Deribit; next version"},
]

# 研究里测过不成立 / 不可复现，网页和日志里一律不用（L1 规格 §2.2）
BANNED = [
    ("M2 及「全球流动性 / M2 领先 BTC 2-3 个月」", "M2 / 'global liquidity leads BTC by 2–3 months'",
     "周度 14 个领先关系样本外只过 1 个；M2 水平相关 0.94 是假相关，涨跌幅相关只有 0.08", "1 of 14 lead relations survives out-of-sample; the 0.94 level correlation is spurious (0.08 in returns)"),
    ("稳定币总量作为加密资金读数", "Total stablecoin supply as crypto dry powder",
     "ETF 时代支付机构稳定币和 BTC 13 周相关 −0.43、Tron≈0；总量 +4.0% 时交易子弹 −4.2%", "Payment stablecoins −0.43 vs BTC, Tron ≈0; total +4.0% while trading bullets −4.2%"),
    ("实际利率作为 L1 第一指标", "Real yield as the first L1 gauge", "周度相关 −0.09 不显著；改为状态变量", "Weekly correlation −0.09, insignificant; now a state variable"),
    ("黄金走势 /「黄金新高利好 BTC」", "Gold / 'gold highs are bullish BTC'", "2022 年后不显著；溢出说法两种口径方向相反", "Insignificant since 2022; two spill-over definitions point opposite ways"),
    ("单次 FOMC 加息 / 降息定方向", "Single FOMC decisions as direction", "7 次事件方向对不上；只调波动预算", "Direction mismatched in 7 events; volatility budget only"),
    ("BTC 顶部对应实际利率低点", "BTC tops align with real-yield lows", "中位相距 96 天 vs 随机 110 天，p=0.40", "Median gap 96 days vs 110 random, p=0.40"),
    ("原油作乐观度指标", "Oil as an optimism gauge", "2023 年后与乐观共同因子相关 0.04", "0.04 correlation with the optimism factor since 2023"),
    ("「ETF 大幅流出 = 抄底 / 反向信号」", "'Big ETF outflows = buy signal'", "极端流出周之后 4 周平均 −3.5%，低于基准 +1.9%，没有反弹", "Four weeks after extreme outflows: −3.5% vs +1.9% baseline"),
    ("「Deribit 升水与 CME 同一口径」", "'Deribit basis = CME basis'", "同概念不同市场，绝对水平常差几个百分点", "Same concept, different markets; levels differ by points"),
    ("用 2018 年以前数据定任何阈值", "Pre-2018 data for any threshold", "2010-2017 宏观解释力低于噪声地板", "2010–2017 macro explanatory power below the noise floor"),
]

# 规则变更留痕（更正记录页原样展示；已写入的历史日志不改）
RULE_CHANGES = [
    {"日期": "2026-10-02", "范围": "L1 宏观流动性", "EN范围": "L1 Macro Liquidity",
     "内容": "按《L1 宏观层数据维度规格》重做：新增纳指 13 周、VIX、乐观度综合 z、BAA / NFCI / 高收益利差 13 周、实际利率四态与情境格、"
             "净流动性 13 周闸门、稳定币「剔除支付机构」「交易子弹」「生息/合成」、ETF 4 周、CME 升水、BTC−纳指 52 周相关、美股代币化快照；"
             "删除「USDT+USDC 总市值」「RRP」「美联储资产负债表单列」；2Y/10Y 利差降为观察项；实际利率从核心指标降为状态变量；"
             "Deribit 升水改为前后两张合约插值成固定 90 天，并去掉「与 CME 同一口径」的说法；L1 判定从「扩张 / 中性 / 收缩」打分改为「顺风 / 中性 / 中性偏谨慎 / 逆风」。"
             "2026-10-02 及以前的日志按旧规则写成，保持原样。",
     "EN": "Rebuilt per the L1 dimension spec: added Nasdaq 13w, VIX, optimism z, BAA/NFCI/HY 13w, real-yield states and scenario grid, "
           "net-liquidity gate, ex-payment / trading-bullet / yield stablecoin lines, ETF 4w, CME basis, BTC–Nasdaq 52w correlation and tokenized-stock monitor; "
           "removed USDT+USDC total, RRP and standalone Fed balance sheet; 2Y/10Y demoted to watch-only; real yield demoted to a state variable; "
           "Deribit basis now interpolated to a constant 90 days. L1 verdict changed from a score (expanding/neutral/contracting) to tailwind / neutral / cautious / headwind. "
           "Logs up to 2026-10-02 were written under the old rules and stay unchanged."},
]

RULE_CHANGES.append(
    {"日期": "2026-10-04", "范围": "L1-B 加密资金通道", "EN范围": "L1-B crypto funding channels",
     "内容": "「L1.5」更名为「L1-B 加密资金通道（只确认、不预测）」。稳定币主线改为去重口径：总供给 − 支付/机构类 − 生息/合成类（原为只剔除支付机构）；"
             "交易子弹旁并列「含 Tron」口径；Tron 链和支付机构稳定币单列观察、不计入；卡片补 52 周变化。新增现货 ETF 13 周净流入和"
             "「资金轮动矩阵」（ETF 13 周 × 交易子弹 13 周）；ETF 标签统一为「趋势确认（滞后）」。L1 每日一行的 L1-B 段改为 主线(去重) / 交易子弹 / ETF 13 周 / 轮动格。",
     "EN": "'L1.5' renamed to 'L1-B crypto funding channels (confirm, don't predict)'. The stablecoin main line is now de-duplicated: total − payment − yield/synthetic "
           "(previously payment only); an incl.-Tron lens sits beside trading bullets; Tron and payment coins are watched separately; 52-week changes added. "
           "New: spot ETF 13-week flow and the rotation matrix (ETF 13w × trading bullets 13w); ETF labels unified as 'trend confirmation (lagging)'."})

# 情境表（L1 规格 §3；2022 年以来 BTC 同期 13 周收益中位数 / 收涨占比，只描述当下，不预测未来 13 周）
SCENARIO_NDX = {("急升", "强"): (27.1, 79), ("急升", "弱"): (-17.8, 13), ("平台", "强"): (13.5, 72), ("平台", "弱"): (-12.0, 33)}
SCENARIO_CREDIT = {("急升", "收窄"): (-3.2, 44), ("急升", "走阔"): (-27.0, 15), ("未急升", "收窄"): (12.5, 67), ("未急升", "走阔"): (-7.6, 39)}


# ---------------------------------------------------------------- 读数
def series_of(S, ind):
    return ind["series"](S) or {}


def reading(S, key, as_of, lag=3, raw=False):
    """判定序列里 ≤ as_of 的最新一个值，外加 1/7/30 日变化与迷你走势。key 可以是指标 key 或原始序列 key；raw=True 强制读原始序列。"""
    s = series_of(S, IND[key]) if key in IND and not raw else (S.get(key) or {})
    ds = sorted(d for d in s if d <= as_of and s[d] is not None)
    if not ds:
        return None
    d = ds[-1]
    v = s[d]

    def back(n):
        t = shift(d, -n)
        i = bisect.bisect_right(ds, t) - 1
        return s[ds[i]] if i >= 0 and days_between(ds[i], t) <= max(4, n // 3) else None

    r = {"key": key, "值": v, "截至": d, "滞后天数": days_between(d, as_of), "过期": days_between(d, as_of) > lag}
    for n in (1, 7, 20, 30):
        b = back(n)
        r[f"前{n}"] = b
        r[f"变{n}"] = (v - b) if b is not None else None
        r[f"涨{n}"] = ((v / b - 1) * 100) if b not in (None, 0) else None
    weekly_ = key in IND and not raw and IND[key].get("freq") == "w"
    span = 365 if weekly_ else 90
    r["走势"] = [s[x] for x in ds if days_between(x, d) <= span]
    r["走势日期"] = [x for x in ds if days_between(x, d) <= span]
    return r


def sum_window(S, key, end, n):
    s = S.get(key) or {}
    vals = [s[d] for d in s if shift(end, -n) < d <= end]
    return sum(vals) if vals else None


def judge(S, ind, as_of):
    r = reading(S, ind["key"], as_of, ind.get("滞后", 3))
    if not r:
        return None
    v = r["值"]
    fmt = FMT[ind["fmt"]]
    if ind.get("classify"):
        res = ind["classify"](v, {"S": S, "as_of": as_of, "d": r["截至"], "series": series_of(S, ind)})
        if res is None:
            return None
        if len(res) == 6:
            zh, en, tone, score, basis, basis_en = res
        else:
            zh, en, tone, score = res
            basis, basis_en = f"{ind['依据']} {fmt(v)}", f"{ind['依据EN']} {fmt(v)}"
    else:
        zh, en, tone, score = band(v, ind["cuts"])
        basis, basis_en = f"{ind['依据']} {fmt(v)}", f"{ind['依据EN']} {fmt(v)}"
    disp = fmt(v)
    # 有「原始水平」的指标在依据里带上水平，读者能对上新闻里的数
    if ind.get("raw") and ind["key"] != "real13":
        rs = RAW_DERIVED[ind["raw"]](S) if ind["raw"] in RAW_DERIVED else (S.get(ind["raw"]) or {})
        ks = [k for k in rs if k <= r["截至"]]
        if ks:
            lv = FMT[ind.get("rawfmt", "x")](rs[max(ks)])
            if ind["key"] in ("ex_netflow", "etf28", "etf13"):          # 原始序列是逐日流量，不是「水平」
                basis += f"，当日 {lv}"
                basis_en += f", latest day {lv}"
            else:
                basis += f"（水平 {lv}）"
                basis_en += f" (level {lv})"
    if ind.get("w52"):
        w = ind["w52"](S)
        ks = [k for k in w if k <= r["截至"]]
        if ks:
            basis += f"，52 周 {w[max(ks)]:+.1f}%"
            basis_en += f", 52w {w[max(ks)]:+.1f}%"
    if ind["key"] == "real13":
        disp = basis.split("，")[0].replace("水平 ", "")
    return {"key": ind["key"], "名称": ind["名称"], "名称EN": ind["EN"], "层": ind["层"], "级别": ind["级别"],
            "等级": ind.get("等级"), "组": ind.get("组"), "值": v, "显示": disp, "截至": r["截至"], "过期": r["过期"],
            "区间": zh, "区间EN": en, "tone": tone, "分": score, "依据": basis, "依据EN": basis_en,
            "走势": r["走势"], "走势日期": r["走势日期"], "涨1": r["涨1"], "变1": r["变1"], "涨7": r["涨7"], "涨30": r["涨30"]}


# ---------------------------------------------------------------- L1：情境格 + 判定
def l1_state(rs_by):
    """从当天读数推出 L1 的各个开关。缺数时对应项为 None。"""
    def val(k):
        x = rs_by.get(k)
        return None if not x or x["过期"] else x["值"]
    real = rs_by.get("real13")
    state = None if not real or real["过期"] else real["区间"]
    return {"实际利率": state, "z": val("optimism_z"), "baa": val("baa13"), "nfci": val("nfci13"), "hy": val("hy13"),
            "净流动性": val("netliq13"), "美元": val("usd13")}


def scenario_cells(st):
    """返回 (纳指口径格, 信用口径格, 较差一格)；格 = (行, 列, 中位, 收涨占比)。"""
    s, z, baa = st["实际利率"], st["z"], st["baa"]
    a = b = None
    if s and z is not None:
        row = "急升" if s == "急升" else ("平台" if s == "高位平台" else None)
        if row:
            col = "强" if z > 0 else "弱"
            a = (row, col, *SCENARIO_NDX[(row, col)])
    if s and baa is not None:
        row = "急升" if s == "急升" else "未急升"
        col = "收窄" if baa < 0 else "走阔"
        b = (row, col, *SCENARIO_CREDIT[(row, col)])
    worse = min([x for x in (a, b) if x], key=lambda x: x[2], default=None)
    return a, b, worse


# 资金轮动矩阵（ETF 13 周 × 交易子弹 13 周）：看两条资金通道是一起进、一起撤，还是互相换手
ROTATION = {
    ("入", "增"): ("新增资金共振（顺风确认）", "New money on both channels (tailwind confirm)", "up"),
    ("入", "减"): ("存量换手（背离，不加仓）", "Existing money switching channels (divergence, no adds)", "warn"),
    ("出", "增"): ("链上资金承接（观察）", "On-chain money absorbing (watch)", "neutral"),
    ("出", "减"): ("资金双撤（逆风确认）", "Money leaving both channels (headwind confirm)", "dn"),
}


def _last(series, d):
    ks = [k for k in series if k <= d]
    return (max(ks), series[max(ks)]) if ks else (None, None)


def rotation(S, as_of):
    de, etf = _last(s_etf13(S), as_of)
    db, b = _last(s_bullets13(S), as_of)
    if etf is None or b is None:
        return None
    _, busd = _last(_memo(S, "bullets13usd", lambda: chg_weeks(weekly(s_stable_bullets(S)), "diff")), as_of)
    _, cpct = _last(s_core13(S), as_of)
    _, cusd = _last(_memo(S, "core13usd", lambda: chg_weeks(weekly(S.get("stable_core") or {}), "diff")), as_of)
    k = ("入" if etf >= 0 else "出", "增" if b >= 0 else "减")
    zh, en, tone = ROTATION[k]
    return {"格": k, "名称": zh, "名称EN": en, "tone": tone, "ETF13": etf, "ETF截至": de, "子弹13": b, "子弹13USD": busd,
            "含Tron13": cpct, "含Tron13USD": cusd, "子弹截至": db,
            "合计USD": (etf + busd) if busd is not None else None}


def l1_verdict(rs):
    by = {x["key"]: x for x in rs if x and x["层"] == 1}
    st = l1_state(by)
    s, z, baa, nfci = st["实际利率"], st["z"], st["baa"], st["nfci"]
    if s is None or (z is None and baa is None):
        return {"层": 1, "结论": "数据不足", "结论EN": "Insufficient data", "短": "数据不足", "短EN": "No data", "tone": "neutral",
                "分": None, "依据": [], "依据EN": [], "状态": st, "情境": None, "闸门": None, "警戒": False}
    surge = s == "急升"
    tight = (baa is not None and baa > 0) or (nfci is not None and nfci > 0)
    gate = st["净流动性"] is not None and st["美元"] is not None and st["净流动性"] <= -2.72 and st["美元"] > 0
    if (surge and (tight or (z is not None and z < 0))) or gate:
        v, ve, short, se, tone = "逆风", "Headwind", "宏观逆风", "Macro headwind", "dn"
    elif surge:
        v, ve, short, se, tone = "中性偏谨慎", "Neutral-cautious", "宏观中性偏谨慎", "Macro cautious", "warn"
    elif z is not None and z > 0 and baa is not None and baa < 0:
        v, ve, short, se, tone = "顺风", "Tailwind", "宏观顺风", "Macro tailwind", "up"
    else:
        v, ve, short, se, tone = "中性", "Neutral", "宏观中性", "Macro neutral", "neutral"
    alert = st["hy"] is not None and st["hy"] >= 0.30
    if alert:
        v, ve = v + "·警戒", ve + " · alert"
    a, b, worse = scenario_cells(st)
    core = [x for x in by.values() if x["级别"] == "核心" and not x["过期"]]
    basis = [f"{x['名称']} {x['区间']}（{x['依据']}）" for x in core]
    basis_en = [f"{x['名称EN']}: {x['区间EN']} ({x['依据EN']})" for x in core]
    if gate:
        basis.append("流动性闸门触发：净流动性 13 周 ≤ −2.72% 且美元 13 周走强")
        basis_en.append("Liquidity gate tripped: net liquidity 13w ≤ −2.72% with a stronger dollar")
    if alert:
        basis.append(f"高收益利差 13 周 {st['hy']:+.2f}pp，快速走阔（先行提示）")
        basis_en.append(f"High-yield spread 13w {st['hy']:+.2f}pp, widening fast (early warning)")
    return {"层": 1, "结论": f"{v}", "结论EN": ve, "短": short + ("·警戒" if alert else ""), "短EN": se + (" · alert" if alert else ""),
            "tone": tone, "分": None, "依据": basis, "依据EN": basis_en, "状态": st,
            "情境": {"纳指口径": a, "信用口径": b, "较差": worse}, "闸门": gate, "警戒": alert}


def l1_line(rs, verdict, rot=None):
    """L1 输出一行（规格 §4）。"""
    by = {x["key"]: x for x in rs if x and x["层"] == 1}

    def g(k, f="显示"):
        x = by.get(k)
        return x[f] if x else "—"

    def lv(k):
        x = by.get(k)
        if not x:
            return "—"
        m = x["依据"]
        return m[m.find("水平 ") + 3:m.rfind("）")] if "水平 " in m else x["显示"]
    w = (verdict.get("情境") or {}).get("较差")
    cell = f"{w[0]}·{w[1]}" if w else "—"
    zh = (f"L1：[{cell}｜{verdict['结论']}]｜乐观度z {g('optimism_z')}｜信用：BAA 13周Δ {g('baa13')} / 高收益利差 {lv('hy13')}（13周 {g('hy13')}）"
          f"｜实际利率 {g('real13')}｜净流动性13周 {g('netliq13')} / 美元13周 {g('usd13')}"
          f"｜L1-B：主线(去重)13周 {g('stable_expay13')} / 交易子弹13周 {g('stable_bullets13')} / ETF 13周 {g('etf13')} / 轮动格 {rot['名称'] if rot else '—'}")
    cell_en = {"急升": "surging", "平台": "plateau", "未急升": "not surging", "强": "strong", "弱": "weak", "收窄": "narrowing", "走阔": "widening"}
    ce = f"{cell_en.get(w[0], w[0])}·{cell_en.get(w[1], w[1])}" if w else "—"
    en = (f"L1: [{ce} | {verdict['结论EN']}] | optimism z {g('optimism_z')} | credit: BAA 13wΔ {g('baa13')} / HY {lv('hy13')} (13w {g('hy13')})"
          f" | real yield {g('real13')} | net liquidity 13w {g('netliq13')} / USD 13w {g('usd13')}"
          f" | L1-B: main line (de-dup) 13w {g('stable_expay13')} / trading bullets 13w {g('stable_bullets13')} / ETF 13w {g('etf13')} / rotation {rot['名称EN'] if rot else '—'}")
    return zh, en


# ---------------------------------------------------------------- 层结论
def layer_verdict(layer, rs):
    if layer == 1:
        return l1_verdict(rs)
    rs = [x for x in rs if x and x["层"] == layer]
    core = [x for x in rs if x["级别"] == "核心" and not x["过期"]]
    if not core:
        return {"层": layer, "结论": "数据不足", "结论EN": "Insufficient data", "短": "数据不足", "短EN": "No data",
                "tone": "neutral", "分": None, "依据": [], "依据EN": []}
    sc = sum(x["分"] for x in core)
    by = {x["key"]: x for x in rs}
    if layer == 2:
        z = by.get("mvrv_z") or by.get("mvrv")
        stage, stage_en = (z["区间"], z["区间EN"]) if z else ("—", "—")
        tone = z["tone"] if z else "neutral"
        v, ve, short, se = f"周期位置：{stage}", f"Cycle position: {stage_en}", f"周期{stage.split('·')[0]}", f"Cycle {stage_en.split(' · ')[0].lower()}"
    elif layer == 3:
        f = by.get("ex_netflow")
        if f and f["分"] > 0:
            v, ve, short, se, tone = "筹码在离开交易所（偏囤币）", "Coins leaving exchanges (hoarding)", "筹码流出交易所", "Coins leaving exchanges", "up"
        elif f and f["分"] < 0:
            v, ve, short, se, tone = "筹码在流入交易所（留意抛压）", "Coins flowing into exchanges (watch selling)", "筹码流入交易所", "Coins entering exchanges", "dn"
        else:
            v, ve, short, se, tone = "交易所进出均衡", "Exchange flows balanced", "筹码进出均衡", "Flows balanced", "neutral"
    else:
        if sc >= 3:
            v, ve, short, se, tone = "过热：短期超调风险高", "Overheated: high overshoot risk", "情绪过热", "Sentiment hot", "dn"
        elif sc >= 1:
            v, ve, short, se, tone = "偏热：杠杆和情绪在升温", "Warm: leverage and sentiment rising", "情绪偏热", "Sentiment warm", "warn"
        elif sc <= -2:
            v, ve, short, se, tone = "偏冷：恐慌出清中", "Cool: fear being flushed", "情绪偏冷", "Sentiment cool", "cool"
        else:
            v, ve, short, se, tone = "中性：没有明显超调", "Neutral: no clear overshoot", "情绪中性", "Sentiment neutral", "neutral"
    basis = [f"{x['名称']} {x['区间']}（{x['依据']}）" for x in core]
    basis_en = [f"{x['名称EN']}: {x['区间EN']} ({x['依据EN']})" for x in core]
    return {"层": layer, "结论": v, "结论EN": ve, "短": short, "短EN": se, "tone": tone, "分": sc, "依据": basis, "依据EN": basis_en}


def composite(vs):
    L1, L4 = vs.get(1, {}), vs.get(4, {})
    s1, s4 = L1.get("tone"), L4.get("tone")
    hot, cold = s4 in ("dn", "warn"), s4 == "cool"
    T = {
        ("dn", "hot"): ("宏观逆风、情绪却偏热——最需要警惕的组合：缺宏观支撑，价格靠杠杆和情绪撑着。",
                        "Macro headwind while sentiment runs hot — the most fragile mix: price is held up by leverage, not macro."),
        ("dn", "cold"): ("宏观逆风、情绪也冷——外部环境和情绪同步退潮。", "Macro headwind and cold sentiment — both are receding together."),
        ("dn", ""): ("宏观逆风（利率急升叠加信用 / 乐观度转弱，或流动性闸门触发），情绪暂时平稳。",
                     "Macro headwind (rate surge plus weaker credit/optimism, or the liquidity gate), sentiment still calm."),
        ("warn", "hot"): ("实际利率在急升、情绪偏热——宏观层降一档风险预算，杠杆拥挤时回调会来得急。",
                          "Real yields surging while sentiment is warm — macro trims the risk budget a notch; crowded leverage makes pullbacks sharp."),
        ("warn", "cold"): ("实际利率在急升、情绪偏冷——宏观和情绪都没给支撑。", "Real yields surging and sentiment cool — neither macro nor sentiment is supportive."),
        ("warn", ""): ("实际利率在急升，但信用和乐观度还撑着——中性偏谨慎，盯信用会不会转紧。",
                       "Real yields surging but credit and optimism still hold — neutral-cautious; watch whether credit tightens."),
        ("up", "hot"): ("宏观顺风、情绪也热——顺风期，但杠杆拥挤时回调会来得很急。", "Macro tailwind and hot sentiment — supportive, but crowded leverage makes pullbacks sharp."),
        ("up", "cold"): ("宏观顺风、情绪偏冷——外部环境支持，情绪还没跟上。", "Macro tailwind but cool sentiment — the backdrop is supportive, sentiment has not caught up."),
        ("up", ""): ("宏观顺风：乐观度和信用条件都在支持风险资产。", "Macro tailwind: optimism and credit both support risk assets."),
        ("neutral", "hot"): ("宏观没给明确方向，情绪和杠杆在升温——短期波动主要由杠杆驱动。",
                             "Macro gives no clear signal while sentiment and leverage heat up — short-term moves are leverage-driven."),
        ("neutral", "cold"): ("宏观没给明确方向，情绪偏冷。", "Macro gives no clear signal; sentiment is cool."),
        ("neutral", ""): ("宏观和情绪都没给明确方向，按区间思路对待。", "Neither macro nor sentiment gives a clear signal — treat it as a range."),
    }
    k1 = s1 if s1 in ("dn", "warn", "up") else "neutral"
    k4 = "hot" if hot else ("cold" if cold else "")
    t, te = T[(k1, k4)]
    vs_ = [vs.get(i, {}) for i in (1, 2, 3, 4)]
    tags = [x.get("短") for x in vs_ if x.get("短") and x.get("短") != "数据不足"]
    tags_en = [x.get("短EN") for x in vs_ if x.get("短EN") and x.get("短") != "数据不足"]
    return {"一句话": t, "一句话EN": te, "标签": tags, "标签EN": tags_en}


# ---------------------------------------------------------------- 发射台摘要（来自 出看板.py 的 网站素材.json）
def launchpad_summary(sd):
    if not sd:
        return None
    tot = sd.get("赛道Top60") or {}
    seq = tot.get("序列") or {}
    ds = sorted(seq)
    chg = None
    if len(ds) >= 2 and seq[ds[-2]]:
        chg = (seq[ds[-1]] / seq[ds[-2]] - 1) * 100
    plats = sorted([p for p in sd.get("平台", []) if p.get("当日手续费") is not None],
                   key=lambda p: -(p.get("当日手续费") or 0))
    top = [{"名称": p["名称"], "链": p["链"], "当日": p["当日手续费"],
            "日环比": None if p.get("日环比") is None else p["日环比"] * 100,
            "份额": None if p.get("占赛道份额") is None else p["占赛道份额"] * 100} for p in plats[:5]]
    return {"日期": sd.get("日期"), "赛道当日": tot.get("当日"), "赛道日环比": chg, "第一": top[0]["名称"] if top else None,
            "Top": top, "一句话": sd.get("一句话"), "异常": sd.get("异常") or [],
            "PONS当日销毁USD": sd.get("PONS当日销毁USD")}


# ---------------------------------------------------------------- 异动预警
def alerts(rs, prev_log, lp, l1=None):
    out = []
    prev = {}
    if prev_log and prev_log.get("版本") == 2:          # 旧规则写的日志口径不同，不拿来比区间切换
        for lay in prev_log.get("层", []):
            for x in lay.get("读数", []):
                prev[x["key"]] = x

    def add(level, zh, en):
        out.append({"级别": level, "文本": zh, "文本EN": en})
    for x in rs:
        if not x or x["过期"]:
            continue
        p = prev.get(x["key"])
        if p and p.get("区间") != x["区间"] and x["级别"] == "核心" and x["区间"] not in ("—", "记录中"):
            add("高" if x["tone"] in ("dn", "warn") else "中",
                f"{x['名称']}从「{p['区间']}」进入「{x['区间']}」（{p['显示']} → {x['显示']}）",
                f"{x['名称EN']} moved from '{p.get('区间EN') or p['区间']}' to '{x['区间EN']}' ({p['显示']} → {x['显示']})")
    if l1 and prev_log:
        p1 = next((lay for lay in prev_log.get("层", []) if lay["层"] == 1), None)
        if p1 and p1.get("短") and p1["短"] != l1["短"] and l1["短"] != "数据不足" and "状态" in p1:
            add("高", f"L1 档位切换：{p1['短']} → {l1['短']}", f"L1 regime change: {p1.get('短EN') or p1['短']} → {l1['短EN']}")
    by = {x["key"]: x for x in rs if x}
    nf = by.get("ex_netflow")
    if nf:
        dval = nf["依据"]
        raw_ = None
        try:
            raw_ = float(dval[dval.find("当日 ") + 3:].split(" BTC")[0].replace(",", "").replace("+", "")) if "当日 " in dval else None
        except ValueError:
            raw_ = None
        if raw_ is not None and abs(raw_) >= 5000:
            add("中", f"交易所单日 BTC 净{'流出' if raw_ < 0 else '流入'} {abs(raw_):,.0f} 枚",
                f"Exchanges saw a one-day net {'outflow' if raw_ < 0 else 'inflow'} of {abs(raw_):,.0f} BTC")
    fu = by.get("hl_funding")
    pf = prev.get("hl_funding")
    if fu and pf and (fu["值"] < 0) != (pf["值"] < 0):
        add("高", f"BTC 资金费率翻{'负' if fu['值'] < 0 else '正'}（{pf['显示']} → {fu['显示']}）",
            f"BTC funding flipped {'negative' if fu['值'] < 0 else 'positive'} ({pf['显示']} → {fu['显示']})")
    vx = by.get("vix")
    pv = prev.get("vix")
    if vx and pv and (vx["值"] >= 20) != (pv["值"] >= 20) and not vx["过期"]:
        add("高" if vx["值"] >= 20 else "中", f"VIX {'升破' if vx['值'] >= 20 else '回落到'} 20（{pv['显示']} → {vx['显示']}）",
            f"VIX {'crossed above' if vx['值'] >= 20 else 'fell back below'} 20 ({pv['显示']} → {vx['显示']})")
    pi = by.get("pi_cycle")
    if pi and pi["值"] >= 1:
        add("高", "Pi Cycle Top 顶部信号处于触发状态", "Pi Cycle Top signal is triggered")
    if lp:
        if lp.get("赛道日环比") is not None and abs(lp["赛道日环比"]) >= 25:
            add("中", f"发射台赛道 Top60 手续费单日 {lp['赛道日环比']:+.1f}%", f"Launchpad top-60 fees {lp['赛道日环比']:+.1f}% day over day")
        plp = (prev_log or {}).get("发射台") or {}
        if plp.get("第一") and lp.get("第一") and plp["第一"] != lp["第一"]:
            add("高", f"发射台当日手续费第一易主：{plp['第一']} → {lp['第一']}", f"New #1 launchpad by daily fees: {plp['第一']} → {lp['第一']}")
        for a in lp.get("异常", [])[:4]:
            add("中", f"发射台：{a}", f"Launchpad: {a}")
    return out


# ---------------------------------------------------------------- 日志
_READ_KEYS = ("key", "名称", "名称EN", "级别", "等级", "值", "显示", "截至", "过期", "区间", "区间EN", "tone", "依据", "依据EN")


def daily_log(date, S, sd, prev_log, sources):
    rs = [judge(S, ind, date) for ind in INDICATORS]
    rs = [x for x in rs if x]
    vs = {i: layer_verdict(i, rs) for i in LAYERS}
    lp = launchpad_summary(sd)
    comp = composite(vs)
    rot = rotation(S, date)
    l1zh, l1en = l1_line(rs, vs[1], rot)
    layers = []
    for i, meta in LAYERS.items():
        extra = {k: vs[i][k] for k in ("状态", "情境", "闸门", "警戒") if k in vs[i]}
        layers.append({"层": i, "名称": meta["名称"], "名称EN": meta["EN"],
                       **{k: vs[i][k] for k in ("结论", "结论EN", "短", "短EN", "tone", "分", "依据", "依据EN")}, **extra,
                       "读数": [{k: x.get(k) for k in _READ_KEYS} for x in rs if x["层"] == i]})
    return {"类型": "日", "版本": 2, "日期": date, "生成时间UTC": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "综合": comp, "L1行": l1zh, "L1行EN": l1en, "轮动": rot, "层": layers, "发射台": lp, "预警": alerts(rs, prev_log, lp, vs[1]),
            "数据源": {k: {"ok": v.get("ok"), "最新日期": v.get("最新日期")} for k, v in (sources or {}).items()},
            "核心缺失": [ind["名称"] for ind in INDICATORS if ind["级别"] == "核心" and not any(x["key"] == ind["key"] and not x["过期"] for x in rs)]}


def _period_review(kind, label, start, end, S, logs, sd, prev_period):
    """周 / 月复盘共用：指标区间变化 + 结论分布 + 预警汇总 + 发射台期间合计。"""
    rows = []
    for ind in INDICATORS:
        if ind["级别"] != "核心":
            continue
        s = series_of(S, ind)
        ds = [d for d in sorted(s) if start <= d <= end]
        if not ds:
            continue
        a, b = s[ds[0]], s[ds[-1]]
        vals = [s[d] for d in ds]
        j0, j1 = judge(S, ind, ds[0]), judge(S, ind, ds[-1])
        fmt = FMT[ind["fmt"]]
        if ind["fmt"] in ("usd", "idx", "price", "btc"):
            chg = f_pct((b / a - 1) * 100, 1, True) if a else "—"
        elif ind["fmt"] in ("pct", "pp"):
            chg = f"{(b - a) * 100:+.0f}bp"
        elif ind["fmt"] in ("pct1", "pcts"):
            chg = f"{b - a:+.1f}pt"
        elif ind["fmt"] in ("btcs", "usds"):
            chg = fmt(b - a)
        else:
            chg = f"{b - a:+.2f}"
        rows.append({"key": ind["key"], "名称": ind["名称"], "名称EN": ind["EN"], "层": ind["层"], "期初": fmt(a), "期末": fmt(b), "变化": chg,
                     "高": fmt(max(vals)), "低": fmt(min(vals)), "期初区间": j0["区间"] if j0 else "—",
                     "期末区间": j1["区间"] if j1 else "—", "期初区间EN": j0["区间EN"] if j0 else "—", "期末区间EN": j1["区间EN"] if j1 else "—",
                     "tone": j1["tone"] if j1 else "neutral", "天数": len(ds)})
    dist = {}
    for lg in logs:
        for lay in lg.get("层", []):
            dist.setdefault(lay["层"], []).append(lay["短"])
    verdicts = []
    for i, meta in LAYERS.items():
        seq = dist.get(i, [])
        cnt = {}
        for v in seq:
            cnt[v] = cnt.get(v, 0) + 1
        switches = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
        verdicts.append({"层": i, "名称": meta["名称"], "名称EN": meta["EN"], "期初": seq[0] if seq else "—", "期末": seq[-1] if seq else "—",
                         "分布": cnt, "切换次数": switches})
    al = [(lg["日期"], a) for lg in logs for a in lg.get("预警", [])]
    lp = None
    if sd:
        seq = (sd.get("赛道Top60") or {}).get("序列") or {}
        cur = [seq[d] for d in seq if start <= d <= end]
        span = days_between(start, end) + 1
        pstart, pend = shift(start, -span), shift(start, -1)
        prev = [seq[d] for d in seq if pstart <= d <= pend]
        plats = []
        for p in sd.get("平台", []):
            fs = p.get("手续费序列") or {}
            c = sum(v for d, v in fs.items() if start <= d <= end)
            pv = sum(v for d, v in fs.items() if pstart <= d <= pend)
            plats.append({"名称": p["名称"], "期间": c, "上期": pv, "变化": ((c / pv - 1) * 100) if pv else None})
        plats.sort(key=lambda x: -x["期间"])
        lp = {"赛道期间合计": sum(cur) if cur else None, "赛道上期合计": sum(prev) if prev else None,
              "赛道变化": ((sum(cur) / sum(prev) - 1) * 100) if cur and prev and sum(prev) else None,
              "平台": plats, "有效天数": len(cur)}
    moves = [f"{v['名称']}由「{v['期初']}」转为「{v['期末']}」" for v in verdicts if v["期初"] != "—" and v["期初"] != v["期末"]]
    moves_en = [f"{v['名称EN']}: {v['期初']} → {v['期末']}" for v in verdicts if v["期初"] != "—" and v["期初"] != v["期末"]]
    if moves:
        one, one_en = "；".join(moves) + "。", "; ".join(moves_en) + "."
    elif logs:
        one = "四层结论在这个区间内没有切换，" + "、".join(v["期末"] for v in verdicts if v["期末"] != "—") + "。"
        one_en = "No layer verdict changed during the period."
    else:
        one, one_en = "这个区间还没有日志，只做指标区间统计。", "No daily logs in this period; indicator statistics only."
    if lp and lp["赛道变化"] is not None:
        one += f"发射台赛道手续费环比{'上期' if kind == '周' else '上月'} {lp['赛道变化']:+.1f}%。"
        one_en += f" Launchpad fees {lp['赛道变化']:+.1f}% vs the previous {'week' if kind == '周' else 'month'}."
    return {"类型": kind, "版本": 2, "标签": label, "起": start, "止": end,
            "生成时间UTC": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "一句话": one, "一句话EN": one_en, "指标": rows, "结论": verdicts, "预警": [{"日期": d, **a} for d, a in al],
            "日志天数": len(logs), "发射台": lp}


def week_bounds(label):
    y, w = label.split("-W")
    mon = dt.date.fromisocalendar(int(y), int(w), 1)
    return mon.isoformat(), (mon + dt.timedelta(days=6)).isoformat()


def week_label(d):
    y, w, _ = dt.date.fromisoformat(d).isocalendar()
    return f"{y}-W{w:02d}"


def month_bounds(label):
    y, m = map(int, label.split("-"))
    first = dt.date(y, m, 1)
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return first.isoformat(), (nxt - dt.timedelta(days=1)).isoformat()


def weekly_review(label, S, logs, sd):
    a, b = week_bounds(label)
    return _period_review("周", label, a, b, S, [x for x in logs if a <= x["日期"] <= b], sd, None)


def monthly_review(label, S, logs, sd):
    a, b = month_bounds(label)
    return _period_review("月", label, a, b, S, [x for x in logs if a <= x["日期"] <= b], sd, None)


# ---------------------------------------------------------------- 详情页用：判定序列的全历史统计
def history_stats(S, ind, since=None):
    s = series_of(S, ind)
    vals = sorted(v for d, v in s.items() if v is not None and (since is None or d >= since))
    if len(vals) < 10:
        return None

    def q(p):
        k = (len(vals) - 1) * p
        lo, hi = math.floor(k), math.ceil(k)
        return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)
    ds = sorted(d for d in s if since is None or d >= since)
    # 各区间历史占比（日度序列按天、周度序列按周）
    share = {}
    if not ind.get("classify") or ind["key"] in ("stable_expay13", "stable_bullets13", "real13"):
        for d in ds:
            z = band(s[d], ind["cuts"])[0]
            share[z] = share.get(z, 0) + 1
    tot = sum(share.values()) or 1
    return {"起": ds[0], "止": ds[-1], "样本": len(vals), "p05": q(.05), "p10": q(.10), "p25": q(.25), "p50": q(.5), "p75": q(.75),
            "p90": q(.90), "p95": q(.95), "min": vals[0], "max": vals[-1],
            "区间占比": [(c[1], c[2], c[3], share.get(c[1], 0) / tot * 100) for c in ind["cuts"]] if share else []}
