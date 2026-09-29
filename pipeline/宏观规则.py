# -*- coding: utf-8 -*-
"""宏观四层框架 · 指标注册表 + 读数规则 + 解读日志生成（纯函数，不联网）

四层框架（来自大叔的「四层框架完整指标测量表」）：
  第一层 宏观流动性  月度级别，判断「水多不多」
  第二层 周期定位    周级别，判断「现在贵不贵、在周期哪一段」
  第三层 筹码结构    周/日级别，判断「支撑压力在哪、谁赚谁亏」
  第四层 情绪衍生品  日内级别，判断「短期会不会超调」

每个指标：怎么取数（ledger 里的 key）、怎么读（区间规则，页面「口径」页原样展示同一张表）、
给层结论打几分。规则只描述读数所处的历史区间，不输出买卖建议。

日志三件套（写日志.py 调用，写进 data/解读日志/，写入后冻结）：
  daily_log     每日一篇：四层读数 + 各层结论 + 综合研判 + 发射台 + 异动预警
  weekly_review 每周一篇（ISO 周，周一出上周）：指标周变化、结论分布与切换、预警汇总、发射台周度
  monthly_review 每月一篇（每月 1 日出上月）：同上，按月
"""
import datetime as dt

LAYERS = {
    1: {"名称": "宏观流动性", "问": "水多不多", "频率": "月度级别"},
    2: {"名称": "周期定位", "问": "现在贵不贵", "频率": "周级别"},
    3: {"名称": "筹码结构", "问": "谁在进出交易所", "频率": "周 / 日级别"},
    4: {"名称": "情绪衍生品", "问": "短期会不会超调", "频率": "日内级别"},
}


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
    "pct": lambda v: f_pct(v, 2),
    "pct1": lambda v: f_pct(v, 1),
    "x": lambda v: "—" if v is None else f"{v:.2f}",
    "x3": lambda v: "—" if v is None else f"{v:.3f}",
    "int": lambda v: "—" if v is None else f"{v:.0f}",
    "idx": lambda v: "—" if v is None else f"{v:.2f}",
    "btc": f_btc,
    "btcs": lambda v: f_btc(v, True),
    "price": lambda v: "—" if v is None else f"${v:,.0f}",
}


# ---------------------------------------------------------------- 读数
def reading(S, key, as_of, lag=3):
    """取 ≤ as_of 的最新一个值，外加 1/7/20/30 日变化与 90 天迷你走势。"""
    s = S.get(key) or {}
    ds = sorted(d for d in s if d <= as_of)
    if not ds:
        return None
    d = ds[-1]
    v = s[d]

    def back(n):
        t = shift(d, -n)
        prev = [x for x in ds if x <= t]
        return s[prev[-1]] if prev and days_between(prev[-1], t) <= max(4, n // 3) else None

    r = {"key": key, "值": v, "截至": d, "滞后天数": days_between(d, as_of), "过期": days_between(d, as_of) > lag}
    for n in (1, 7, 20, 30):
        b = back(n)
        r[f"前{n}"] = b
        r[f"变{n}"] = (v - b) if b is not None else None
        r[f"涨{n}"] = ((v / b - 1) * 100) if b not in (None, 0) else None
    r["走势"] = [s[x] for x in ds if days_between(x, d) <= 90]
    r["走势日期"] = [x for x in ds if days_between(x, d) <= 90]
    return r


def sum_window(S, key, end, n):
    s = S.get(key) or {}
    vals = [s[d] for d in s if shift(end, -n) < d <= end]
    return sum(vals) if vals else None


# ---------------------------------------------------------------- 区间判定工具
def band(v, cuts):
    """cuts: [(上界, 区间名, tone, 分)...] 最后一个上界用 None 表示 +∞。"""
    for ub, name, tone, score in cuts:
        if ub is None or v < ub:
            return name, tone, score
    return cuts[-1][1:]


# tone：up 利好/扩张（荧光绿）· dn 利空/收缩/过热（荧光红）· warn 偏热（琥珀）· cool 偏冷/低估（蓝）· neutral 中性
def J_stable(r, S, as_of):
    g = r["涨30"]
    if g is None:
        return None
    name, tone, sc = band(g, [(-1, "收缩", "dn", -1), (1, "持平", "neutral", 0), (3, "扩张", "up", 1), (None, "强扩张", "up", 2)])
    return name, tone, sc, f"30 日 {f_pct(g, 2, True)}，单日净增发 {f_signed_usd(r['变1'])}"


def J_real(r, S, as_of):
    c = r["变20"]
    if c is None:
        return None
    bp = round(c * 100)
    name, tone, sc = band(bp, [(-15, "下行", "up", 1), (15, "横盘", "neutral", 0), (None, "上行", "dn", -1)])
    lvl = "，绝对水平偏紧（>2%）" if r["值"] > 2 else ""
    return name, tone, sc, f"20 日 {bp:+d}bp{lvl}"


def J_curve(r, S, as_of):
    v = r["值"]
    name, tone, _ = band(v, [(0, "倒挂", "warn", 0), (0.5, "偏平（刚解除倒挂）", "warn", 0), (None, "正常陡峭", "neutral", 0)])
    return name, tone, 0, f"{v:+.2f}%，20 日 {round(r['变20'] * 100):+d}bp" if r["变20"] is not None else f"{v:+.2f}%"


def J_usd(r, S, as_of):
    g = r["涨20"]
    if g is None:
        return None
    name, tone, sc = band(g, [(-1, "走弱", "up", 1), (1, "横盘", "neutral", 0), (None, "走强", "dn", -1)])
    return name, tone, sc, f"20 日 {f_pct(g, 2, True)}"


def J_walcl(r, S, as_of):
    g = r["涨30"]
    if g is None:
        return None
    name, tone, _ = band(g, [(-0.5, "缩表", "dn", 0), (0.5, "持平", "neutral", 0), (None, "扩表", "up", 0)])
    return name, tone, 0, f"30 日 {f_pct(g, 2, True)}"


def J_rrp(r, S, as_of):
    v = r["值"]
    name, tone, _ = band(v, [(1e11, "基本抽干", "warn", 0), (5e11, "低位", "neutral", 0), (None, "充裕", "neutral", 0)])
    return name, tone, 0, f"余额 {f_usd(v)}"


def J_basis(r, S, as_of):
    v = r["值"]
    name, tone, sc = band(v, [(3, "冷淡", "cool", -1), (8, "正常", "neutral", 0), (15, "偏高", "up", 1), (None, "过热", "warn", 1)])
    return name, tone, sc, f"年化 {v:.1f}%"


def J_mvrv(r, S, as_of):
    v = r["值"]
    name, tone, sc = band(v, [(1.0, "低估·历史底部区", "cool", 2), (1.5, "偏低", "cool", 1), (2.4, "合理", "neutral", 0),
                              (3.2, "偏热", "warn", -1), (None, "过热·历史顶部区", "dn", -2)])
    return name, tone, sc, f"{v:.2f}"


def J_z(r, S, as_of):
    v = r["值"]
    name, tone, sc = band(v, [(0, "底部区", "cool", 2), (1.5, "偏低", "cool", 1), (3, "合理", "neutral", 0),
                              (5, "偏热", "warn", -1), (None, "过热·顶部区", "dn", -2)])
    return name, tone, sc, f"{v:.2f}"


def J_realized(r, S, as_of):
    p = reading(S, "btc_price", as_of)
    if not p:
        return None
    prem = (p["值"] / r["值"] - 1) * 100
    name, tone, _ = band(prem, [(0, "现价跌破成本线", "cool", 0), (30, "贴近成本线", "cool", 0), (140, "合理溢价", "neutral", 0),
                                (None, "高溢价", "warn", 0)])
    return name, tone, 0, f"现价 {FMT['price'](p['值'])}，高出 {prem:+.0f}%"


def J_nupl(r, S, as_of):
    v = r["值"]
    name, tone, _ = band(v, [(0, "投降", "cool", 0), (0.25, "希望 / 恐惧", "cool", 0), (0.5, "乐观 / 焦虑", "neutral", 0),
                             (0.75, "信念 / 否认", "warn", 0), (None, "狂热", "dn", 0)])
    return name, tone, 0, f"{v:.3f}"


def J_mayer(r, S, as_of):
    v = r["值"]
    name, tone, _ = band(v, [(0.8, "深度低估", "cool", 0), (1.0, "低于 200 日线", "cool", 0), (1.5, "合理", "neutral", 0),
                             (2.4, "偏热", "warn", 0), (None, "过热", "dn", 0)])
    return name, tone, 0, f"{v:.2f}"


def J_puell(r, S, as_of):
    v = r["值"]
    name, tone, _ = band(v, [(0.5, "矿工投降区", "cool", 0), (1.0, "偏低", "cool", 0), (2.0, "合理", "neutral", 0),
                             (3.5, "偏热", "warn", 0), (None, "过热", "dn", 0)])
    return name, tone, 0, f"{v:.2f}"


def J_pi(r, S, as_of):
    v = r["值"]
    name, tone, _ = band(v, [(0.9, "远离顶部信号", "neutral", 0), (1.0, "接近顶部信号", "warn", 0), (None, "已触发顶部信号", "dn", 0)])
    return name, tone, 0, f"111DMA / 2×350DMA = {v:.3f}"


def J_netflow(r, S, as_of):
    w = sum_window(S, "ex_netflow", r["截至"], 7)
    if w is None:
        return None
    name, tone, sc = band(w, [(-10000, "大幅净流出（提币）", "up", 2), (-2000, "净流出", "up", 1), (2000, "进出均衡", "neutral", 0),
                              (10000, "净流入", "dn", -1), (None, "大幅净流入（抛压）", "dn", -2)])
    return name, tone, sc, f"7 日合计 {f_btc(w, True)}，当日 {f_btc(r['值'], True)}"


def J_exbal(r, S, as_of):
    g = r["涨30"]
    if g is None:
        return None
    name, tone, _ = band(g, [(-1, "下降", "up", 0), (1, "持平", "neutral", 0), (None, "上升", "dn", 0)])
    return name, tone, 0, f"30 日 {f_pct(g, 2, True)}"


def J_fng(r, S, as_of):
    v = r["值"]
    name, tone, sc = band(v, [(25, "极度恐慌", "cool", -2), (45, "恐慌", "cool", -1), (56, "中性", "neutral", 0),
                              (76, "贪婪", "warn", 1), (None, "极度贪婪", "dn", 2)])
    return name, tone, sc, f"{v:.0f} / 100"


def J_funding(r, S, as_of):
    v = r["值"]
    name, tone, sc = band(v, [(-5, "空头拥挤（易轧空）", "cool", -1), (5, "偏冷", "cool", 0), (20, "正常", "neutral", 0),
                              (40, "多头偏热", "warn", 1), (None, "多头极度拥挤", "dn", 2)])
    return name, tone, sc, f"年化 {v:.1f}%，基准约 11%"


def J_oi(r, S, as_of):
    g = r["涨7"]
    if g is None:
        return "记录中", "neutral", 0, f"{f_usd(r['值'])}（自 {r['截至']} 起逐日记录，满 7 天后给判定）"
    name, tone, sc = band(g, [(-15, "去杠杆", "cool", -1), (15, "平稳", "neutral", 0), (None, "杠杆快速堆积", "warn", 1)])
    return name, tone, sc, f"{f_usd(r['值'])}，7 日 {f_pct(g, 1, True)}"


def J_alt(r, S, as_of):
    v = r["值"]
    name, tone, _ = band(v, [(25, "比特币季", "neutral", 0), (50, "比特币偏强", "neutral", 0), (75, "山寨偏强", "warn", 0),
                             (None, "山寨季", "warn", 0)])
    return name, tone, 0, f"Top50 里 {v:.0f}% 跑赢 BTC（30 日）"


def J_dom(r, S, as_of):
    c = r["变30"]
    tail = f"，30 日 {c:+.1f}pt" if c is not None else ""
    return "—", "neutral", 0, f"{r['值']:.1f}%{tail}"


# 指标注册表：顺序即页面顺序。级别：核心 = 日常仪表盘 ✅；辅助 = ⚠️ 阶段性参考
INDICATORS = [
    # ---- 第一层
    {"key": "stable_major", "层": 1, "级别": "核心", "名称": "USDT+USDC 总市值", "fmt": "usd", "来源": "DefiLlama", "滞后": 3,
     "judge": J_stable, "说明": "稳定币是场外资金进场的通道。看 30 日增速：扩张 = 有新钱在进，收缩 = 在撤。",
     "区间": [("< -1%", "收缩"), ("-1% ~ +1%", "持平"), ("+1% ~ +3%", "扩张"), ("> +3%", "强扩张")], "依据": "30 日增速"},
    {"key": "fred_dfii10", "层": 1, "级别": "核心", "名称": "10Y 美债实际利率", "fmt": "pct", "来源": "FRED · DFII10", "滞后": 6,
     "judge": J_real, "说明": "持有无息资产的机会成本。下行 = 对 BTC 这类资产更友好，上行 = 压制。",
     "区间": [("20 日 ≤ -15bp", "下行"), ("±15bp", "横盘"), ("≥ +15bp", "上行")], "依据": "20 日变化"},
    {"key": "fred_t10y2y", "层": 1, "级别": "核心", "名称": "2Y / 10Y 利差", "fmt": "pct", "来源": "FRED · T10Y2Y", "滞后": 6,
     "judge": J_curve, "说明": "衰退与流动性拐点信号。历史上衰退多发生在倒挂「解除」之后，不是倒挂当下。不计入层打分。",
     "区间": [("< 0", "倒挂"), ("0 ~ 0.5%", "偏平（刚解除倒挂）"), ("> 0.5%", "正常陡峭")], "依据": "水平"},
    {"key": "fred_broad_usd", "层": 1, "级别": "核心", "名称": "广义美元指数", "fmt": "idx", "来源": "FRED · DTWEXBGS", "滞后": 8,
     "judge": J_usd, "说明": "覆盖 DXY 盲区的贸易加权美元。美元走弱 = 全球美元流动性宽松。（DXY 本身没有免费官方接口，用它替代）",
     "区间": [("20 日 ≤ -1%", "走弱"), ("±1%", "横盘"), ("≥ +1%", "走强")], "依据": "20 日变化"},
    {"key": "deribit_basis", "层": 1, "级别": "核心", "名称": "BTC 期货年化升水", "fmt": "pct1", "来源": "Deribit（约 3 个月期）", "滞后": 2,
     "judge": J_basis, "说明": "机构加杠杆做多的意愿。CME Basis 没有免费接口，用 Deribit 约 3 个月期交割合约替代，同一口径。",
     "区间": [("< 3%", "冷淡"), ("3% ~ 8%", "正常"), ("8% ~ 15%", "偏高"), ("> 15%", "过热")], "依据": "年化升水"},
    {"key": "fred_walcl", "层": 1, "级别": "辅助", "名称": "美联储资产负债表", "fmt": "usd", "来源": "FRED · WALCL", "滞后": 10,
     "judge": J_walcl, "说明": "QT / QE 节奏。阶段性参考，不计入层打分。",
     "区间": [("30 日 < -0.5%", "缩表"), ("±0.5%", "持平"), ("> +0.5%", "扩表")], "依据": "30 日变化"},
    {"key": "fred_rrp", "层": 1, "级别": "辅助", "名称": "隔夜逆回购 RRP", "fmt": "usd", "来源": "FRED · RRPONTSYD", "滞后": 6,
     "judge": J_rrp, "说明": "流动性「蓄水池」剩多少。抽干后 QT 直接抽银行准备金。阶段性参考，不计入层打分。",
     "区间": [("< $100B", "基本抽干"), ("$100B ~ $500B", "低位"), ("> $500B", "充裕")], "依据": "余额"},
    # ---- 第二层
    {"key": "mvrv", "层": 2, "级别": "核心", "名称": "MVRV", "fmt": "x", "来源": "CoinMetrics", "滞后": 3,
     "judge": J_mvrv, "说明": "市值 / 已实现市值 = 全网平均浮盈倍数。",
     "区间": [("< 1.0", "低估·历史底部区"), ("1.0 ~ 1.5", "偏低"), ("1.5 ~ 2.4", "合理"), ("2.4 ~ 3.2", "偏热"), ("> 3.2", "过热·历史顶部区")], "依据": "水平"},
    {"key": "mvrv_z", "层": 2, "级别": "核心", "名称": "MVRV Z-Score", "fmt": "x", "来源": "CoinMetrics（自算）", "滞后": 3,
     "judge": J_z, "说明": "（市值 − 已实现市值）÷ 市值历史标准差，把 MVRV 标准化到跨周期可比。",
     "区间": [("< 0", "底部区"), ("0 ~ 1.5", "偏低"), ("1.5 ~ 3", "合理"), ("3 ~ 5", "偏热"), ("> 5", "过热·顶部区")], "依据": "水平"},
    {"key": "realized_price", "层": 2, "级别": "核心", "名称": "Realized Price", "fmt": "price", "来源": "CoinMetrics（自算）", "滞后": 3,
     "judge": J_realized, "说明": "全网持币成本均价（价格 ÷ MVRV）。现价跌破它 = 全网平均浮亏，历史上是大底区。待证伪观察中。",
     "区间": [("现价 < 成本", "跌破成本线"), ("溢价 0 ~ 30%", "贴近成本线"), ("30% ~ 140%", "合理溢价"), ("> 140%", "高溢价")], "依据": "现价溢价"},
    {"key": "nupl", "层": 2, "级别": "核心", "名称": "NUPL", "fmt": "x3", "来源": "CoinMetrics（自算）", "滞后": 3,
     "judge": J_nupl, "说明": "净未实现盈亏 = 1 − 1/MVRV，和 MVRV 高度相关，看情绪阶段用，不重复计分。",
     "区间": [("< 0", "投降"), ("0 ~ 0.25", "希望 / 恐惧"), ("0.25 ~ 0.5", "乐观 / 焦虑"), ("0.5 ~ 0.75", "信念 / 否认"), ("> 0.75", "狂热")], "依据": "水平"},
    {"key": "mayer", "层": 2, "级别": "辅助", "名称": "Mayer Multiple", "fmt": "x", "来源": "CoinMetrics（自算）", "滞后": 3,
     "judge": J_mayer, "说明": "价格 ÷ 200 日均线。",
     "区间": [("< 0.8", "深度低估"), ("0.8 ~ 1.0", "低于 200 日线"), ("1.0 ~ 1.5", "合理"), ("1.5 ~ 2.4", "偏热"), ("> 2.4", "过热")], "依据": "水平"},
    {"key": "puell", "层": 2, "级别": "辅助", "名称": "Puell Multiple", "fmt": "x", "来源": "CoinMetrics（自算）", "滞后": 3,
     "judge": J_puell, "说明": "矿工日发行收入 ÷ 365 日均值，矿工视角的周期位置。",
     "区间": [("< 0.5", "矿工投降区"), ("0.5 ~ 1.0", "偏低"), ("1.0 ~ 2.0", "合理"), ("2.0 ~ 3.5", "偏热"), ("> 3.5", "过热")], "依据": "水平"},
    {"key": "pi_cycle", "层": 2, "级别": "辅助", "名称": "Pi Cycle Top", "fmt": "x3", "来源": "CoinMetrics（自算）", "滞后": 3,
     "judge": J_pi, "说明": "111 日均线 ÷（2 × 350 日均线），≥ 1 即历史顶部信号触发。只用于顶部区警示。",
     "区间": [("< 0.9", "远离顶部信号"), ("0.9 ~ 1.0", "接近"), ("≥ 1.0", "已触发")], "依据": "比值"},
    # ---- 第三层
    {"key": "ex_netflow", "层": 3, "级别": "核心", "名称": "交易所 BTC 净流量", "fmt": "btcs", "来源": "CoinMetrics（flash 口径）", "滞后": 3,
     "judge": J_netflow, "说明": "流入 − 流出。持续净流出 = 筹码离开交易所（提币囤币），净流入 = 潜在抛压。flash 数据次日可能小幅修订。",
     "区间": [("7 日 < -10,000", "大幅净流出"), ("-10,000 ~ -2,000", "净流出"), ("±2,000", "进出均衡"), ("2,000 ~ 10,000", "净流入"), ("> 10,000", "大幅净流入")], "依据": "7 日合计"},
    {"key": "ex_balance", "层": 3, "级别": "辅助", "名称": "交易所 BTC 余额", "fmt": "btc", "来源": "CoinMetrics", "滞后": 21,
     "judge": J_exbal, "说明": "交易所托管的 BTC 总量。免费档更新有约 2 周滞后，只看趋势。",
     "区间": [("30 日 < -1%", "下降"), ("±1%", "持平"), ("> +1%", "上升")], "依据": "30 日变化"},
    # ---- 第四层
    {"key": "fng", "层": 4, "级别": "核心", "名称": "恐慌贪婪指数", "fmt": "int", "来源": "alternative.me", "滞后": 2,
     "judge": J_fng, "说明": "综合波动、成交、社媒、搜索的情绪温度计。",
     "区间": [("0 ~ 24", "极度恐慌"), ("25 ~ 44", "恐慌"), ("45 ~ 55", "中性"), ("56 ~ 75", "贪婪"), ("76 ~ 100", "极度贪婪")], "依据": "水平"},
    {"key": "hl_funding", "层": 4, "级别": "核心", "名称": "BTC 永续资金费率", "fmt": "pct1", "来源": "Hyperliquid（日均年化）", "滞后": 2,
     "judge": J_funding, "说明": "多空谁在付钱。含约 11% 年化的基准利息（和币安 0.01%/8h 同量级），所以「正常」不是 0。",
     "区间": [("< -5%", "空头拥挤"), ("-5% ~ 5%", "偏冷"), ("5% ~ 20%", "正常"), ("20% ~ 40%", "多头偏热"), ("> 40%", "多头极度拥挤")], "依据": "年化"},
    {"key": "hl_oi", "层": 4, "级别": "核心", "名称": "BTC 未平仓合约", "fmt": "usd", "来源": "Hyperliquid", "滞后": 2,
     "judge": J_oi, "说明": "链上最大永续所的 BTC 未平仓名义价值，看 7 日变化判断杠杆在堆还是在出清。单一交易所口径。",
     "区间": [("7 日 < -15%", "去杠杆"), ("±15%", "平稳"), ("> +15%", "杠杆快速堆积")], "依据": "7 日变化"},
    {"key": "altseason", "层": 4, "级别": "核心", "名称": "山寨季指数（自建）", "fmt": "pct1", "来源": "CoinGecko（自算）", "滞后": 2,
     "judge": J_alt, "说明": "市值前 50（剔除稳定币、包装币、质押衍生品）里 30 日涨幅跑赢 BTC 的占比。blockchaincenter 原版用 90 日，没有免费接口，这里是自建口径。",
     "区间": [("< 25%", "比特币季"), ("25% ~ 50%", "比特币偏强"), ("50% ~ 75%", "山寨偏强"), ("> 75%", "山寨季")], "依据": "占比"},
    {"key": "btc_dom", "层": 4, "级别": "辅助", "名称": "BTC 市值占比", "fmt": "pct1", "来源": "CoinGecko", "滞后": 2,
     "judge": J_dom, "说明": "和山寨季指数交叉验证。",
     "区间": [("—", "只看趋势")], "依据": "水平"},
]
IND = {x["key"]: x for x in INDICATORS}

# 框架里有、但暂时没有免费稳定数据源的指标——页面上明示「待接入」和原因，不拿近似值冒充
PENDING = [
    {"层": 1, "名称": "DXY 美元指数", "原因": "ICE 官方数据收费，免费行情接口不稳定；先用 FRED 广义美元指数替代"},
    {"层": 1, "名称": "BTC 现货 ETF 净流入", "原因": "Farside 只有网页表格、SoSoValue 接口要 key；v2 接入"},
    {"层": 1, "名称": "黄金 / 纳指 / 标普联动", "原因": "阶段性交叉验证，不进日常仪表盘"},
    {"层": 2, "名称": "Realized Cap HODL Waves", "原因": "需要按 UTXO 年龄分布计算，免费接口不提供；Glassnode 付费或自建节点"},
    {"层": 3, "名称": "URPD 链上筹码分布", "原因": "Glassnode 付费指标；属于框架里标 🔧 的差异化自建方向"},
    {"层": 3, "名称": "STH-MVRV / LTH-MVRV", "原因": "需要按持有时长拆分已实现市值，Glassnode 付费"},
    {"层": 3, "名称": "STH-SOPR / aSOPR", "原因": "Glassnode 付费指标"},
    {"层": 3, "名称": "矿工储备 / 非流动性供给", "原因": "Glassnode 付费指标"},
    {"层": 4, "名称": "多空比 / 24h 爆仓", "原因": "Coinglass 接口需要 key（免费档可申请），拿到 key 即可接入"},
    {"层": 4, "名称": "期权 Put/Call · IV Skew", "原因": "Deribit 免费可取，v2 接入"},
]


def judge(S, ind, as_of):
    r = reading(S, ind["key"], as_of, ind.get("滞后", 3))
    if not r:
        return None
    res = ind["judge"](r, S, as_of)
    if not res:
        return None
    zone, tone, score, basis = res
    return {"key": ind["key"], "名称": ind["名称"], "层": ind["层"], "级别": ind["级别"],
            "值": r["值"], "显示": FMT[ind["fmt"]](r["值"]), "截至": r["截至"], "过期": r["过期"],
            "区间": zone, "tone": tone, "分": score, "依据": basis,
            "走势": r["走势"], "走势日期": r["走势日期"], "涨1": r["涨1"], "变1": r["变1"], "涨7": r["涨7"], "涨30": r["涨30"]}


# ---------------------------------------------------------------- 层结论
def layer_verdict(layer, rs):
    rs = [x for x in rs if x and x["层"] == layer]
    core = [x for x in rs if x["级别"] == "核心" and not x["过期"]]
    if not core:
        return {"层": layer, "结论": "数据不足", "短": "数据不足", "tone": "neutral", "分": None, "依据": []}
    sc = sum(x["分"] for x in core)
    by = {x["key"]: x for x in rs}
    if layer == 1:
        if sc >= 2:
            v, short, tone = "扩张：水在变多", "流动性扩张", "up"
        elif sc <= -2:
            v, short, tone = "收缩：水在变少", "流动性收缩", "dn"
        else:
            v, short, tone = "中性：水位没有明显变化", "流动性中性", "neutral"
    elif layer == 2:
        z = by.get("mvrv_z") or by.get("mvrv")
        stage = z["区间"] if z else "—"
        tone = z["tone"] if z else "neutral"
        v, short = f"周期位置：{stage}", f"周期{stage.split('·')[0]}"
    elif layer == 3:
        f = by.get("ex_netflow")
        if f and f["分"] > 0:
            v, short, tone = "筹码在离开交易所（偏囤币）", "筹码流出交易所", "up"
        elif f and f["分"] < 0:
            v, short, tone = "筹码在流入交易所（留意抛压）", "筹码流入交易所", "dn"
        else:
            v, short, tone = "交易所进出均衡", "筹码进出均衡", "neutral"
    else:
        if sc >= 3:
            v, short, tone = "过热：短期超调风险高", "情绪过热", "dn"
        elif sc >= 1:
            v, short, tone = "偏热：杠杆和情绪在升温", "情绪偏热", "warn"
        elif sc <= -2:
            v, short, tone = "偏冷：恐慌出清中", "情绪偏冷", "cool"
        else:
            v, short, tone = "中性：没有明显超调", "情绪中性", "neutral"
    basis = [f"{x['名称']} {x['区间']}（{x['依据']}）" for x in core]
    return {"层": layer, "结论": v, "短": short, "tone": tone, "分": sc, "依据": basis}


def composite(vs):
    L1, L2, L3, L4 = (vs.get(i, {}) for i in (1, 2, 3, 4))
    s1, s4 = L1.get("tone"), L4.get("tone")
    liq_up, liq_dn = s1 == "up", s1 == "dn"
    hot, cold = s4 in ("dn", "warn"), s4 == "cool"
    if liq_up and cold:
        t = "水在变多、情绪却偏冷——资金和情绪背离，历史上这类背离多以情绪修复收场。"
    elif liq_up and hot:
        t = "水多、情绪也热——顺风期，但杠杆拥挤时回调会来得很急。"
    elif liq_dn and hot:
        t = "水在变少、情绪却偏热——最需要警惕的组合：价格靠杠杆和情绪撑着，缺增量资金。"
    elif liq_dn and cold:
        t = "水少、情绪也冷——资金和情绪同步退潮，流动性拐点比情绪拐点更关键。"
    elif liq_up:
        t = "流动性在改善，情绪还没跟上，属于偏左侧的环境。"
    elif liq_dn:
        t = "流动性在收紧，情绪暂时平稳，留意后续是否传导到价格。"
    elif hot:
        t = "流动性没给方向，情绪和杠杆在升温——短期波动主要由杠杆驱动。"
    elif cold:
        t = "流动性没给方向，情绪偏冷——没有增量资金配合，反弹持续性存疑。"
    else:
        t = "流动性和情绪都没有给出明确方向，按区间思路对待。"
    tags = [x.get("短") for x in (L1, L2, L3, L4) if x.get("短") and x.get("短") != "数据不足"]
    return {"一句话": t, "标签": tags}


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
def alerts(rs, prev_log, lp):
    out = []
    prev = {}
    if prev_log:
        for lay in prev_log.get("层", []):
            for x in lay.get("读数", []):
                prev[x["key"]] = x
    for x in rs:
        if not x or x["过期"]:
            continue
        p = prev.get(x["key"])
        if p and p.get("区间") != x["区间"] and x["级别"] == "核心" and x["区间"] not in ("—", "记录中"):
            out.append({"级别": "高" if x["tone"] in ("dn", "warn") else "中",
                        "文本": f"{x['名称']}从「{p['区间']}」进入「{x['区间']}」（{p['显示']} → {x['显示']}）"})
    by = {x["key"]: x for x in rs if x}
    s = by.get("stable_major")
    if s and s["变1"] is not None and abs(s["变1"]) >= 1e9:
        out.append({"级别": "中", "文本": f"USDT+USDC 单日净{'增发' if s['变1'] > 0 else '赎回'} {f_usd(abs(s['变1']))}"})
    f = by.get("ex_netflow")
    if f and abs(f["值"]) >= 5000:
        out.append({"级别": "中", "文本": f"交易所单日 BTC 净{'流出' if f['值'] < 0 else '流入'} {abs(f['值']):,.0f} 枚"})
    fu = by.get("hl_funding")
    pf = prev.get("hl_funding")
    if fu and pf and (fu["值"] < 0) != (pf["值"] < 0):
        out.append({"级别": "高", "文本": f"BTC 资金费率翻{'负' if fu['值'] < 0 else '正'}（{pf['显示']} → {fu['显示']}）"})
    r = by.get("fred_dfii10")
    if r and r["变1"] is not None and abs(r["变1"]) >= 0.1:
        out.append({"级别": "中", "文本": f"10Y 实际利率单日 {r['变1']*100:+.0f}bp"})
    pi = by.get("pi_cycle")
    if pi and pi["值"] >= 1:
        out.append({"级别": "高", "文本": "Pi Cycle Top 顶部信号处于触发状态"})
    if lp:
        if lp.get("赛道日环比") is not None and abs(lp["赛道日环比"]) >= 25:
            out.append({"级别": "中", "文本": f"发射台赛道 Top60 手续费单日 {lp['赛道日环比']:+.1f}%"})
        plp = (prev_log or {}).get("发射台") or {}
        if plp.get("第一") and lp.get("第一") and plp["第一"] != lp["第一"]:
            out.append({"级别": "高", "文本": f"发射台当日手续费第一易主：{plp['第一']} → {lp['第一']}"})
        for a in lp.get("异常", [])[:4]:
            out.append({"级别": "中", "文本": f"发射台：{a}"})
    return out


# ---------------------------------------------------------------- 日志
def daily_log(date, S, sd, prev_log, sources):
    rs = [judge(S, ind, date) for ind in INDICATORS]
    rs = [x for x in rs if x]
    vs = {i: layer_verdict(i, rs) for i in LAYERS}
    lp = launchpad_summary(sd)
    comp = composite(vs)
    layers = []
    for i, meta in LAYERS.items():
        layers.append({"层": i, "名称": meta["名称"], **{k: vs[i][k] for k in ("结论", "短", "tone", "分", "依据")},
                       "读数": [{k: x[k] for k in ("key", "名称", "级别", "值", "显示", "截至", "过期", "区间", "tone", "依据")}
                              for x in rs if x["层"] == i]})
    return {"类型": "日", "日期": date, "生成时间UTC": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "综合": comp, "层": layers, "发射台": lp, "预警": alerts(rs, prev_log, lp),
            "数据源": {k: {"ok": v.get("ok"), "最新日期": v.get("最新日期")} for k, v in (sources or {}).items()},
            "核心缺失": [ind["名称"] for ind in INDICATORS if ind["级别"] == "核心" and not any(x["key"] == ind["key"] and not x["过期"] for x in rs)]}


def _period_review(kind, label, start, end, S, logs, sd, prev_period):
    """周 / 月复盘共用：指标区间变化 + 结论分布 + 预警汇总 + 发射台期间合计。"""
    rows = []
    for ind in INDICATORS:
        if ind["级别"] != "核心":
            continue
        s = S.get(ind["key"]) or {}
        ds = [d for d in sorted(s) if start <= d <= end]
        if not ds:
            continue
        a, b = s[ds[0]], s[ds[-1]]
        vals = [s[d] for d in ds]
        j0, j1 = judge(S, ind, ds[0]), judge(S, ind, ds[-1])
        fmt = FMT[ind["fmt"]]
        if ind["key"] == "ex_netflow":
            chg = f"期间合计 {f_btc(sum(vals), True)}"
        elif ind["fmt"] in ("usd", "idx", "price", "btc", "btcs"):
            chg = f_pct((b / a - 1) * 100, 1, True) if a else "—"
        elif ind["fmt"] == "pct":                     # 利率 / 利差：用 bp
            chg = f"{(b - a) * 100:+.0f}bp"
        elif ind["fmt"] == "pct1":                    # 升水 / 资金费率 / 山寨季：百分点
            chg = f"{b - a:+.1f}pt"
        else:
            chg = f"{b - a:+.2f}"
        rows.append({"key": ind["key"], "名称": ind["名称"], "层": ind["层"], "期初": fmt(a), "期末": fmt(b), "变化": chg,
                     "高": fmt(max(vals)), "低": fmt(min(vals)), "期初区间": j0["区间"] if j0 else "—",
                     "期末区间": j1["区间"] if j1 else "—", "tone": j1["tone"] if j1 else "neutral", "天数": len(ds)})
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
        verdicts.append({"层": i, "名称": meta["名称"], "期初": seq[0] if seq else "—", "期末": seq[-1] if seq else "—",
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
    # 一句话：各层期初 → 期末
    moves = []
    for v in verdicts:
        if v["期初"] != "—" and v["期初"] != v["期末"]:
            moves.append(f"{v['名称']}由「{v['期初']}」转为「{v['期末']}」")
    if moves:
        one = "；".join(moves) + "。"
    elif logs:
        one = "四层结论在这个区间内没有切换，" + "、".join(v["期末"] for v in verdicts if v["期末"] != "—") + "。"
    else:
        one = "这个区间还没有日志，只做指标区间统计。"
    if lp and lp["赛道变化"] is not None:
        one += f"发射台赛道手续费环比{'上期' if kind == '周' else '上月'} {lp['赛道变化']:+.1f}%。"
    return {"类型": kind, "标签": label, "起": start, "止": end,
            "生成时间UTC": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "一句话": one, "指标": rows, "结论": verdicts, "预警": [{"日期": d, **a} for d, a in al],
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
