#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发射台日更 · 生成看板网站 + CSV + 推送摘要 + Notion 追加行
读：日度数据.json / 销毁逐日.json / 销毁累计.json / 销毁台账.json / 估值序列.json / Arc数据.json / 已发布.json
写（全部在 输出/ 下）：
  发射台日更看板.html      完整 HTML 文档（显式 <head>/<body>，给 Notion 嵌入块用 —— 省略这两个标签时
                           某些预览器的过滤会吞掉整页，改脚本时别改回去）
  看板页.html              同一内容的页面片段（给 claude.ai Artifact 发布用，发布时会自动套外壳）
  发射台日更-<日期>.csv     当日 CSV
  摘要.md                  聊天推送正文（含近 7 天逐日表与异常提示）
  notion_payload.json      Notion 五张表待追加的行（已按页面现有格式排好）
给数字，不给买卖建议。
"""
import json, os, csv, html, math, urllib.request, datetime as dt
from common import load, shift, today_utc, OUT

D = load("日度数据.json")
burn_daily = load("销毁逐日.json", {})
cum_exact = load("销毁累计.json", {})
ledger = load("销毁台账.json", [])
VAL = load("估值序列.json")
ARC = load("Arc数据.json")
PUB = load("已发布.json", {}) or {}
FIXES = load("销毁修正记录.json", []) or []
PONS_ADDR = "0x39dBED3a2bd333467115dE45665cC57F813C4571"
SUPPLY = 1_000_000_000
BURN_CHART_START = "2026-07-15"   # ⛔ 上线初期两笔一次性大额销毁不进趋势图（会把后面全部压成贴地直线）

P, TOT = D["平台"], D["赛道Top60日总量"]
NAME = {"pump.fun": "pump.fun", "pons-v2": "Pons V2", "pons-v1": "Pons V1",
        "stonkfun": "StonkFun", "flap-sh": "Flap"}
ORDER = [s for s in ["pump.fun", "pons-v2", "pons-v1", "stonkfun", "flap-sh"] if s in P and P[s]["fees"]]
HAS_STONK = "stonkfun" in ORDER
LASTD = {s: max(P[s]["fees"]) for s in ORDER}
LASTR = {s: (max(P[s]["revenue"]) if P[s]["revenue"] else None) for s in ORDER}

expected = D.get("期望最后一天") or LASTD["pump.fun"]
if any(LASTD.get(s, "") >= expected for s in ("pump.fun", "pons-v2")):
    LAST, GLOBAL_DELAY = expected, False
else:                                      # DefiLlama 整体没出昨天：报到最近的完整日，并明说
    LAST, GLOBAL_DELAY = LASTD["pump.fun"], True
DELAYED = [s for s in ORDER if LASTD[s] < LAST]
days = sorted(d for d in set().union(*[set(P[s]["fees"]) for s in ORDER]) if d <= LAST)
if LAST not in days:
    days.append(LAST)
W7, P7 = days[-7:], days[-14:-7]
PREV = shift(LAST, -1)
GEN = D["生成时间UTC"][:16].replace("T", " ")
AGE = (dt.date.fromisoformat(today_utc()) - dt.date.fromisoformat(LAST)).days


# ---------- 取数（缺失 = None = 延迟；上线前 / 区间内空白 = 0） ----------
def fee(s, d):
    if s not in P or not P[s]["fees"]:
        return None
    m = P[s]["fees"]
    if d in m:
        return m[d]
    return None if d > LASTD[s] else 0.0


def rv(s, d):
    if s not in P or not P[s]["revenue"]:
        return None
    m = P[s]["revenue"]
    if d in m:
        return m[d]
    return None if d > LASTR[s] else 0.0


def pons(d):
    a, b = fee("pons-v1", d), fee("pons-v2", d)
    return None if a is None or b is None else a + b


def pons_rev(d):
    a, b = rv("pons-v1", d), rv("pons-v2", d)
    return None if a is None or b is None else a + b


def avg(xs):
    v = [x for x in xs if x is not None]
    return sum(v) / len(v) if v else None


def pch(a, b):
    return (a / b - 1) if (a is not None and b) else None


def div(a, b):
    return (a / b) if (a is not None and b) else None


# ---------- 格式 ----------
def usd(v, dp=None):
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e9:
        return f"${v/1e9:.2f}B"
    if a >= 1e6:
        return f"${v/1e6:.2f}M"
    if a >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:,.0f}"


def tok(v):
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e6:
        return f"{v/1e6:.2f}M"
    if a >= 1e3:
        return f"{v/1e3:.0f}K"
    return f"{v:,.0f}"


def n0(v, miss="—"):
    return miss if v is None else f"{v:,.0f}"


def pct(v, dp=1, sign=False):
    if v is None:
        return "—"
    return f"{v*100:+.{dp}f}%" if sign else f"{v*100:.{dp}f}%"


def xx(v, dp=1):
    return "—" if v is None else f"{v:.{dp}f}x"


def fmt_val(v, f):
    return {"usd": usd, "tok": tok, "pct": pct, "x": xx,
            "ratio": lambda z: "—" if z is None else f"{z:.2f}"}[f](v)


def esc(s):
    return html.escape(str(s), quote=True)


# ---------- PONS 日末累计（精确值优先，缺的按逐日倒推） ----------
CUM = {}
if burn_daily:
    bdays = sorted(burn_daily)
    if cum_exact:
        anchor = max(cum_exact)
        running = cum_exact[anchor]["累计"]
    else:
        anchor = bdays[-1]
        running = ledger[-1]["销毁地址持仓"] if ledger else 0
    for d in reversed([x for x in bdays if x <= anchor]):
        CUM[d] = cum_exact[d]["累计"] if d in cum_exact else running
        running = CUM[d] - burn_daily[d]

# ---------- 估值序列 ----------
VROWS, VMETA = {}, {}
if VAL:
    for sym, meta in VAL["代币"].items():
        if meta.get("序列"):
            VROWS[sym] = {r["日期"]: r for r in meta["序列"]}
            VMETA[sym] = meta
VSYMS = [s for s in ["PUMP", "PONS", "STONK"] if s in VROWS]
VCLS = {"PUMP": "s1", "PONS": "s2", "STONK": "s3"}


def vr(sym, d=None):
    rs = VROWS.get(sym)
    if not rs:
        return None
    return rs.get(d or LAST)


def vget(sym, key, d=None):
    r = vr(sym, d)
    return None if not r else r.get(key)


def pons_px(d):
    r = vr("PONS", d)
    if not r:
        return None
    if r.get("价格"):
        return r["价格"]
    c = CUM.get(d)
    return r["市值"] / (SUPPLY - c) if c else None


def burn_usd(d):
    r = vr("PONS", d)
    if r and r.get("当日回购额") is not None and burn_daily.get(d) is not None:
        return r["当日回购额"]
    px = pons_px(d)
    return burn_daily[d] * px if (px and d in burn_daily) else None


def live_price():
    try:
        u = f"https://api.dexscreener.com/latest/dex/tokens/{PONS_ADDR}"
        r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        ps = json.load(urllib.request.urlopen(r, timeout=20)).get("pairs") or []
        ps = [p for p in ps if (p.get("liquidity") or {}).get("usd")]
        ps.sort(key=lambda p: -p["liquidity"]["usd"])
        return float(ps[0]["priceUsd"])
    except Exception:
        return None


PX_LIVE = live_price()
BURNED = CUM.get(LAST) or (ledger[-1]["销毁地址持仓"] if ledger else None)
BURN_BASIS = "日末精确值" if LAST in cum_exact else ("逐日倒推" if LAST in CUM else "台账最新读数")
ADJ = SUPPLY - BURNED if BURNED else None
burn_last = burn_daily.get(LAST)
burn7 = [burn_daily.get(x) for x in W7]
burn7_usd = sum(v for v in (burn_usd(x) for x in W7) if v)

# ---------- 各平台指标 ----------
rows = []
for s in ORDER:
    cur, prv = fee(s, LAST), fee(s, PREV)
    hist = [(x, fee(s, x)) for x in days if fee(s, x) is not None]
    pk_day, pk = max(hist, key=lambda t: t[1]) if hist else (None, None)
    r = rv(s, LAST)
    rows.append({
        "slug": s, "名称": P[s]["名称"], "链": P[s]["链"], "延迟": s in DELAYED,
        "当日手续费": cur, "日环比": pch(cur, prv),
        "7日均": avg([fee(s, x) for x in W7]),
        "7日均环比": pch(avg([fee(s, x) for x in W7]), avg([fee(s, x) for x in P7])),
        "当日收入": r, "分账比率": div(r, cur), "占赛道份额": div(cur, TOT.get(LAST)),
        "距单日峰值": div(cur, pk), "单日峰值": pk, "峰值日": pk_day, "累计": P[s].get("累计"),
    })
R = {x["slug"]: x for x in rows}
pons_cur, pons_prev = pons(LAST), pons(PREV)
v2share = div(fee("pons-v2", LAST), pons_cur)
ratio = div(fee("pump.fun", LAST), pons_cur)
ratio_prev = div(fee("pump.fun", PREV), pons_prev)
miss = D.get("赛道分母缺失") or {}
DENOM_BAD = bool(miss.get("日期") == LAST and (miss.get("缺失占前一日总量") or 0) > 0.05)

# ---------- Arc 链 ----------
ARC_OK = bool(ARC and ARC.get("链", {}).get("Arc", {}).get("全链手续费"))
A = ARC["链"]["Arc"] if ARC_OK else {}
RH = ARC["链"].get("Robinhood Chain", {}) if ARC_OK else {}
TH_A, TH_B, TH_C = 300_000, 100_000, 0.25     # 升级为逐家平台收入监控的初始阈值（可调）
ARC_MAINNET = "2026-09-16"                     # 之前的零星数据是测试期残留，不进图


def arc_eval(end):
    """以 end 为最后一天的 7 天窗口评估三条升级条件"""
    w = [shift(end, -i) for i in range(6, -1, -1)]
    if not all(d in A["全链手续费"] for d in w):
        return None
    a_min = min(A["发射台手续费"].get(d, 0) for d in w)
    best, best_min = None, -1
    for n, e in A["发射台"].items():
        m = min(e["fees"].get(d, 0) for d in w)
        if m > best_min:
            best, best_min = n, m
    rh7 = sum(RH.get("全链DEX成交", {}).get(d, 0) for d in w)
    c = (sum(A["全链DEX成交"].get(d, 0) for d in w) / rh7) if rh7 else None
    return {"A": a_min, "B": best_min, "B名": best, "C": c,
            "trig": [k for k, ok in (("A", a_min >= TH_A), ("B", best_min >= TH_B),
                                     ("C", c is not None and c >= TH_C)) if ok]}


if ARC_OK:
    ARC_LAST = min(LAST, max(A["全链手续费"]))
    adays = sorted(d for d in A["全链手续费"] if d <= ARC_LAST)
    AW7 = adays[-7:]
    ARC_NOW, ARC_YDAY = arc_eval(ARC_LAST), arc_eval(shift(ARC_LAST, -1))
    LPS = []
    for n, e in A["发射台"].items():
        LPS.append({"名称": n, "slug": e.get("slug"), "当日": e["fees"].get(ARC_LAST),
                    "7日": sum(e["fees"].get(d, 0) for d in AW7),
                    "30日": sum(e["fees"].get(d, 0) for d in adays[-30:]),
                    "7日DEX": sum(e["dex"].get(d, 0) for d in AW7),
                    "序列": [e["fees"].get(d, 0) for d in adays[-14:]]})
    LPS.sort(key=lambda z: -z["7日"])
    LP7 = sum(z["7日"] for z in LPS) or None
    TOLLY = next((z for z in LPS if (z["slug"] == "tolly" or "tolly" in z["名称"].lower())), None)
    TOP = LPS[0] if LPS else None
else:
    ARC_LAST, ARC_NOW, ARC_YDAY, LPS, LP7, TOLLY, TOP, AW7, adays = None, None, None, [], None, None, None, [], []

# ---------- 修订检查：已发到 Notion 的日子，DefiLlama 事后改了数 ----------
PUBV = PUB.get("表一数值", {})
REVISED = []
for d, vals in sorted(PUBV.items()):
    if d < shift(LAST, -7) or d > LAST:
        continue
    for k, old in vals.items():
        if k == "top60":          # Top60 成员每天按 30 日排名重选，历史分母随之变动，属结构性变化，不算修订
            continue
        new = fee(k, d)
        if new is None:
            continue
        tol = 0.05 if k == "top60" else 0.01      # 分母常被别家迟到的数据小幅修订，阈值放宽
        if old is None or abs(new - old) > max(1000, tol * abs(old)):
            REVISED.append((d, k, old, new))
REVISED_DAYS = sorted({d for d, *_ in REVISED})

# ---------- 异常（按重要性排；推送只放前 3 条） ----------
AN = []
AN_NOTION_ONLY = set()      # 只和 Notion 已发布值有关的条目，网站版不收（网站自己对照它发布过的数）
if GLOBAL_DELAY:
    AN.append(f"DefiLlama 整体延迟：{expected} 尚未出数，本期数据截至 {LAST}")
for s in DELAYED:
    AN.append(f"{NAME[s]} 数据源延迟（最后一天 {LASTD[s]}），相关列标「延迟」，没有拿旧值顶替")
if DENOM_BAD:
    AN.append(f"赛道 Top60 分母缺 {len(miss['缺失协议'])} 家（约占前一日 {miss['缺失占前一日总量']:.0%}），份额偏高")
for d in REVISED_DAYS:
    ks = "、".join(sorted({NAME.get(k, "Top60") for dd, k, *_ in REVISED if dd == d}))
    AN.append(f"DefiLlama 修订了 {d} 的 {ks}，Notion 追加「{d}（修正）」行")
    AN_NOTION_ONLY.add(AN[-1])
if ratio is not None and ratio_prev is not None and (ratio - 1) * (ratio_prev - 1) < 0:
    AN.append(f"pump÷Pons 穿越 1.0：{ratio_prev:.2f} → {ratio:.2f}")
for x in rows:
    if x["日环比"] is not None and abs(x["日环比"]) > 0.6:
        AN.append(f"{NAME[x['slug']]} 日环比 {pct(x['日环比'], 1, True)}（阈值 ±60%）")
for s in ["pump.fun", "pons-v2", "pons-v1", "flap-sh"]:
    if s not in R or R[s]["分账比率"] is None:
        continue
    r7 = avg([div(rv(s, x), fee(s, x)) for x in P7[-7:] + W7[:-1]][-7:])
    if r7 is not None and abs(R[s]["分账比率"] - r7) > 0.05:
        AN.append(f"{NAME[s]} 分账比率 {pct(R[s]['分账比率'])}，较 7 日均 {pct(r7)} 变动超过 5 个百分点")
b7avg = avg(burn_daily.get(x) for x in days[-8:-1])
if burn_last is None:
    AN.append("PONS 当日销毁未读到（链上读取失败或未跑）")
elif burn_last == 0:
    AN.append("PONS 当日销毁为零")
elif b7avg and burn_last > 3 * b7avg:
    AN.append(f"PONS 当日销毁 {tok(burn_last)} 枚，超过此前 7 日均 {tok(b7avg)} 的 3 倍")
if ARC_NOW and ARC_NOW["trig"] and not (ARC_YDAY and ARC_YDAY["trig"]):
    AN.append(f"Arc 升级条件首次触发（{'、'.join(ARC_NOW['trig'])}），可以开始逐家平台收入监控")


# ======================================================================
# 图表（内联 SVG；悬停读数由页尾脚本提供，脚本失效时图本身完整可读）
# ======================================================================
CH = {}


def r4(v):
    return None if v is None else float(f"{v:.4g}")


def xmeta(xs):
    """连续日期只存起点，省体积；不连续才存完整列表"""
    ok = all(shift(xs[i - 1], 1) == xs[i] for i in range(1, len(xs)))
    return {"d0": xs[0], "n": len(xs)} if ok else {"d": xs, "n": len(xs)}


def nice(x):
    if x <= 0:
        return 1
    e = 10 ** math.floor(math.log10(x))
    f = x / e
    for nf in (1, 2, 2.5, 5, 10):
        if f <= nf:
            return nf * e
    return 10 * e


def axis_lab(v, f):
    if f == "usd":
        a = abs(v)
        if a >= 1e9:
            return f"${v/1e9:g}B"
        if a >= 1e6:
            return f"${v/1e6:g}M"
        if a >= 1e3:
            return f"${v/1e3:g}K"
        return f"${v:g}"
    if f == "tok":
        return f"{v/1e6:g}M" if abs(v) >= 1e6 else (f"{v/1e3:g}K" if abs(v) >= 1e3 else f"{v:g}")
    if f == "pct":
        return f"{v*100:g}%"
    if f == "x":
        return f"{v:g}x"
    return f"{v:g}"


def spread(items, lo, hi, gap=14):
    """末端标签防重叠：按 y 排序后向下推开，再整体拉回到绘图区内"""
    items.sort(key=lambda t: t[0])
    ys = []
    for y, *_ in items:
        ys.append(max(y, ys[-1] + gap) if ys else y)
    over = (ys[-1] - hi) if ys and ys[-1] > hi else 0
    ys = [y - over for y in ys]
    for i in range(len(ys) - 2, -1, -1):
        ys[i] = min(ys[i], ys[i + 1] - gap)
    ys = [max(lo, y) for y in ys]
    return [(ys[i],) + tuple(items[i][1:]) for i in range(len(items))]


def figure(cid, title, sub, legend, svg, foot=""):
    lg = "".join(f'<span><i class="key {c}{" dash" if d else ""}"></i>{esc(n)}</span>' for n, c, d in legend)
    return (f'<figure class="chart" data-k="{cid}" tabindex="0" aria-label="{esc(title)}">'
            f'<figcaption><div class="ct">{esc(title)}</div><div class="cs">{sub}</div></figcaption>'
            + (f'<div class="lg">{lg}</div>' if legend else "")
            + f'<div class="plot">{svg}<div class="tip" hidden></div></div>{foot}</figure>')


def line_chart(series, xs, title, sub, f="usd", h=270, ref=None, short=None):
    """series: [(名称, 色类, {日期: 值}, 虚线?)]；None = 断开（延迟/无数据）"""
    cid = f"c{len(CH)}"
    W, Lp, Rp, Tp, Bp = 600, 58, 96, 12, 28
    pw, ph = W - Lp - Rp, h - Tp - Bp
    n = len(xs)
    vals = [m.get(x) for _, _, m, *_ in series for x in xs]
    vals = [v for v in vals if v is not None]
    if not vals or n < 2:
        return figure(cid, title, sub, [], '<div class="empty">暂无数据</div>')
    vmin = min(0, min(vals))
    top = max(vals + ([ref[0]] if ref else []))
    step = nice((top - vmin) / 4)
    top = math.ceil(top / step) * step if top > 0 else step
    if ref and top - ref[0] < step * 0.3:
        top += step
    lo = math.floor(vmin / step) * step

    def X(i):
        return Lp + pw * i / (n - 1)

    def Y(v):
        return Tp + ph * (1 - (v - lo) / (top - lo))
    g = [f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="{esc(title)}">']
    t = lo
    while t <= top + 1e-9:
        y = Y(t)
        g.append(f'<line class="{"axis" if abs(t) < 1e-12 else "grid"}" x1="{Lp}" y1="{y:.1f}" x2="{W-Rp}" y2="{y:.1f}"/>'
                 f'<text class="ax" x="{Lp-8}" y="{y+4:.1f}" text-anchor="end">{esc(axis_lab(t, f))}</text>')
        t += step
    k = max(1, round((n - 1) / 5))
    idx = list(range(0, n - 1, k))
    if n - 1 - idx[-1] < k * 0.6:
        idx = idx[:-1]
    for i in idx + [n - 1]:
        g.append(f'<text class="ax" x="{X(i):.1f}" y="{h-8}" text-anchor="{"end" if i == n-1 else "middle"}">{xs[i][5:]}</text>')
    if ref:
        y = Y(ref[0])
        g.append(f'<line class="ref" x1="{Lp}" y1="{y:.1f}" x2="{W-Rp}" y2="{y:.1f}"/>'
                 f'<text class="ax" x="{Lp+4}" y="{y-5:.1f}">{esc(ref[1])}</text>')
    ends, js = [], []
    for item in series:
        name, cls, m = item[0], item[1], item[2]
        dash = item[3] if len(item) > 3 else False
        seg, segs = [], []
        for i, x in enumerate(xs):
            v = m.get(x)
            if v is None:
                if seg:
                    segs.append(seg)
                seg = []
            else:
                seg.append(f"{X(i):.1f},{Y(v):.1f}")
        if seg:
            segs.append(seg)
        for sg in segs:
            if len(sg) == 1:
                g.append(f'<circle class="f{cls[1:]}" cx="{sg[0].split(",")[0]}" cy="{sg[0].split(",")[1]}" r="2"/>')
            else:
                g.append(f'<polyline class="ln {cls}{" dsh" if dash else ""}" points="{" ".join(sg)}"/>')
        li = max((i for i, x in enumerate(xs) if m.get(x) is not None), default=None)
        if li is not None:
            ends.append((Y(m[xs[li]]), X(li), Y(m[xs[li]]), cls, (short or {}).get(name, name), m[xs[li]], dash))
        js.append({"n": name, "c": cls, "v": [r4(m.get(x)) for x in xs]})
    for ly, ex, ey, cls, nm, v, dash in spread(ends, Tp + 4, Tp + ph):
        if not dash:
            g.append(f'<circle class="end f{cls[1:]}" cx="{ex:.1f}" cy="{ey:.1f}" r="3.6"/>')
        g.append(f'<text class="lab" x="{W-Rp+8}" y="{ly+4:.1f}">{esc(nm)} <tspan class="labv">{esc(fmt_val(v, f))}</tspan></text>')
    g.append("</svg>")
    CH[cid] = {"W": W, "T": Tp, "B": Tp + ph, "L": Lp, "pw": pw, "lo": lo, "top": top, "f": f, **xmeta(xs), "s": js}
    legend = [(it[0], it[1], it[3] if len(it) > 3 else False) for it in series]
    return figure(cid, title, sub, legend, "".join(g))


def bar_chart(m, xs, title, sub, f="tok", cls="s2", h=250, name="数值"):
    cid = f"c{len(CH)}"
    W, Lp, Rp, Tp, Bp = 600, 58, 20, 12, 28
    pw, ph = W - Lp - Rp, h - Tp - Bp
    n = len(xs)
    vals = [m.get(x) for x in xs if m.get(x) is not None]
    if not vals:
        return figure(cid, title, sub, [], '<div class="empty">暂无数据</div>')
    step = nice(max(vals) / 4)
    top = math.ceil(max(vals) / step) * step or step
    slot = pw / n
    bw = max(1.0, slot - 2)                       # 柱间 2px 间隙

    def Y(v):
        return Tp + ph * (1 - v / top)
    g = [f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="{esc(title)}">']
    t = 0
    while t <= top + 1e-9:
        y = Y(t)
        g.append(f'<line class="{"axis" if t == 0 else "grid"}" x1="{Lp}" y1="{y:.1f}" x2="{W-Rp}" y2="{y:.1f}"/>'
                 f'<text class="ax" x="{Lp-8}" y="{y+4:.1f}" text-anchor="end">{esc(axis_lab(t, f))}</text>')
        t += step
    xsx = []
    for i, x in enumerate(xs):
        cx = Lp + slot * (i + 0.5)
        xsx.append(round(cx, 1))
        v = m.get(x)
        if not v:
            continue
        y0, base = Y(v), Tp + ph
        r = min(2.0, bw / 2, base - y0)
        x0 = cx - bw / 2
        g.append(f'<path class="f{cls[1:]}" d="M{x0:.1f},{base:.1f}V{y0+r:.1f}Q{x0:.1f},{y0:.1f} {x0+r:.1f},{y0:.1f}'
                 f'H{x0+bw-r:.1f}Q{x0+bw:.1f},{y0:.1f} {x0+bw:.1f},{y0+r:.1f}V{base:.1f}Z"/>')
    k = max(1, round((n - 1) / 5))
    idx = list(range(0, n - 1, k))
    if len(idx) > 1 and n - 1 - idx[-1] < k * 0.6:
        idx = idx[:-1]
    for i in idx + [n - 1]:
        g.append(f'<text class="ax" x="{xsx[i]}" y="{h-8}" text-anchor="{"end" if i == n-1 else "middle"}">{xs[i][5:]}</text>')
    g.append("</svg>")
    CH[cid] = {"W": W, "T": Tp, "B": Tp + ph, "L": Lp, "pw": pw, "lo": 0, "top": top, "f": f, "bar": 1, **xmeta(xs),
               "s": [{"n": name, "c": cls, "v": [r4(m.get(x)) for x in xs]}]}
    return figure(cid, title, sub, [], "".join(g))


def spark(vals, w=96, h=22):
    if not vals or max(vals) <= 0:
        return '<svg class="spk" viewBox="0 0 96 22"></svg>'
    mx = max(vals)
    pts = " ".join(f"{2 + (w-6) * i / max(1, len(vals)-1):.1f},{h - 3 - (h-6) * v / mx:.1f}" for i, v in enumerate(vals))
    lx, ly = pts.split(" ")[-1].split(",")
    return (f'<svg class="spk" viewBox="0 0 {w} {h}" aria-hidden="true"><polyline class="ln sk" points="{pts}"/>'
            f'<circle class="fsk" cx="{lx}" cy="{ly}" r="2.2"/></svg>')


# ---------- 趋势图数据 ----------
win = days[-90:]
PLAT_SERIES = [("pump.fun", "pump.fun", "s1"), ("Pons 合计", "pons", "s2")]
if HAS_STONK:
    PLAT_SERIES.append(("StonkFun", "stonkfun", "s3"))
PLAT_SERIES.append(("Flap", "flap-sh", "s4"))
SHORT = {"pump.fun": "pump", "Pons 合计": "Pons", "StonkFun": "Stonk", "Flap": "Flap"}


def fees_map(key):
    return {x: (pons(x) if key == "pons" else fee(key, x)) for x in days}


def rev_map(key):
    return {x: (pons_rev(x) if key == "pons" else rv(key, x)) for x in days}


def ma_map(m, n=7):
    out = {}
    for i, x in enumerate(days):
        w = [m.get(z) for z in days[max(0, i - n + 1):i + 1]]
        out[x] = None if m.get(x) is None else avg(w)
    return out


FM = {k: fees_map(k) for _, k, _ in PLAT_SERIES}
RM = {k: rev_map(k) for _, k, _ in PLAT_SERIES}
s_fees = [(n, c, FM[k]) for n, k, c in PLAT_SERIES]
s_ma = [(n, c, ma_map(FM[k])) for n, k, c in PLAT_SERIES]
s_rev = [(n, c, ma_map(RM[k])) for n, k, c in PLAT_SERIES if k != "flap-sh"]
s_share = [(n, c, {x: div(FM[k].get(x), TOT.get(x)) for x in days}) for n, k, c in PLAT_SERIES]
s_split = [(n, c, {x: div(RM[k].get(x), FM[k].get(x)) for x in days if FM[k].get(x)})
           for n, k, c in PLAT_SERIES if k != "stonkfun"]
s_ratio = [("pump÷Pons", "s1", {x: div(FM["pump.fun"].get(x), FM["pons"].get(x)) for x in days})]
burn_win = [x for x in win if x >= BURN_CHART_START]
burn_excl = sorted(x for x in burn_daily if x < BURN_CHART_START)
burn_excl_txt = "；".join(f"{x} {burn_daily[x]:,.0f} 枚" for x in burn_excl)
stonk_note = ("StonkFun 的 fees 在 DefiLlama 只记平台自己那份（与 revenue 相等），pump.fun 的 fees 含创作者费，"
              "两者口径不同，这张图里 StonkFun 天然偏低。") if HAS_STONK else ""

trend_charts = "".join([
    line_chart(s_fees, win, "每日手续费 · 90 天",
               "原始日度值。周末与批次结算会让单日剧烈跳动，判断趋势看 7 日均线。" + stonk_note, short=SHORT),
    line_chart(s_ma, win, "手续费 7 日均线 · 90 天",
               "抹掉周内噪音后的趋势线，⭐ 判断趋势一律看这张。两条线交叉的那天，就是赛道重心易主的那天。", short=SHORT),
    line_chart(s_rev, win, "协议收入 7 日均线 · 90 天（可比口径）",
               "revenue = 平台自己留下的钱。pump.fun、Pons、StonkFun 三家在这个口径上可以并排比；"
               "Flap 是税代币模型，不进这张图。", short=SHORT),
    line_chart(s_share, win, "占赛道当日总量的份额 · 90 天",
               f"分母 = Launchpad 类目 Top60 当日加总（全类目 {D.get('Launchpad协议总数', '—')} 个，尾部未计入）。"
               "份额稳而绝对额跌是周期，份额掉到接近零才是死亡。", f="pct", short=SHORT),
    line_chart(s_split, win, "分账比率 revenue ÷ fees · 90 天",
               "⭐ 最灵敏的预警：这条线突然变台阶 = 平台改了费率或分账。pump.fun 2026-09-01 改档位、"
               "Flap 2026-08-31 DefiLlama 改算法都会在这里露出来。StonkFun 恒为 100%（定义如此），不画。",
               f="pct", short=SHORT),
    line_chart(s_ratio, win, "pump.fun ÷ Pons 合计 · 90 天",
               "小于 1 = Pons 当日手续费更大。穿越 1.0 会进异常提示。", f="ratio", ref=(1.0, "1.0"),
               short={"pump÷Pons": "比值"}),
    bar_chart({x: burn_daily.get(x) for x in burn_win}, burn_win,
              f"PONS 每日销毁量（{BURN_CHART_START} 起）",
              "按 UTC 日界切的销毁地址余额差（2026-09-26 起的新口径，旧日期保留原值）。"
              "呈批次跳跃而非连续流，是「回购由人工执行、非合约强制」的链上证据。"
              + (f" 已剔除上线初期一次性大额销毁：{burn_excl_txt}（剔除只影响本图，累计与市值仍含这两笔）。"
                 if burn_excl else ""), f="tok", cls="s2", name="当日销毁（枚）")
    if len(burn_win) > 2 else "",
])

# ---------- 估值图 ----------
vdays = sorted({d for s in VSYMS for d in VROWS[s] if d <= LAST})[-180:]


def vseries(key, cap):
    out = []
    for s in VSYMS:
        m = {}
        for d in vdays:
            r = VROWS[s].get(d)
            if not r or r.get(key) is None or r["窗口天数"] < 14 or r[key] > cap:
                continue
            m[d] = r[key]
        if m:
            out.append((s, VCLS[s], m))
    return out


val_charts = "".join([
    line_chart(vseries("回购市盈率", 60), vdays, "回购市盈率 · 180 天",
               "市值 ÷ 年化回购销毁额，越低 = 用越少年数就能把当前市值买回来。"
               "滚动窗口不足 14 天的点不画，60x 以上截断。", f="x"),
    line_chart(vseries("回购收益率", 1.2), vdays, "回购收益率 · 180 天",
               "回购市盈率的倒数。回购来自手续费，手续费掉下去这条线立刻跟着掉。"
               "窗口不足 14 天的点不画，120% 以上截断（PONS 上线头几天算出过 6,756%）。", f="pct"),
    line_chart(vseries("收入市盈率", 60), vdays, "收入市盈率 · 180 天",
               "市值 ÷ 年化协议收入。与回购市盈率的差距，就是协议收入里没拿去回购的那部分。"
               "窗口不足 14 天的点不画，60x 以上截断。", f="x"),
]) if VSYMS else '<div class="empty">估值序列尚未生成</div>'

# 理论 vs 实际（小多图，每个代币一张，单一美元轴）
tva_days = sorted({d for s in VSYMS for d in VROWS[s] if d <= LAST})[-30:]
tva_charts = "".join(
    line_chart([(f"{s} 实际回购额", VCLS[s], {d: (VROWS[s].get(d) or {}).get("当日回购额") for d in tva_days}),
                (f"{s} 理论回购额", "sk", {d: (VROWS[s].get(d) or {}).get("当日理论回购额") for d in tva_days}, True)],
               tva_days, f"{s} · 理论 vs 实际回购 · 30 天",
               {"PUMP": "理论 = 当日协议收入 × 100%。实际 = DefiLlama dailyHoldersRevenue（链上销毁，汇总 pump 全部产品线）。",
                "PONS": "理论 = 当日协议收入 × 80%（官方口径）。实际 = 当日销毁枚数 × 当日收盘价。人工执行，非合约强制。",
                "STONK": "理论 = 当日协议收入 × 60%（官网政策，非链上规则）。实际 = DefiLlama dailyHoldersRevenue（Jupiter 买回 STONK）。"}[s],
               h=230, short={f"{s} 实际回购额": "实际", f"{s} 理论回购额": "理论"})
    for s in VSYMS)
bbr_chart = line_chart(
    [(s, VCLS[s], {d: v for d in vdays[-90:] for v in [(VROWS[s].get(d) or {}).get("当日回购占收入")]
                   if v is not None and v <= 2.5}) for s in VSYMS],
    vdays[-90:], "当日回购额 ÷ 当日协议收入 · 90 天",
    "当天协议收入里，有多少被实际拿去回购平台币（链上/官方口径已发生的回购额，不是理论测算）。"
    "三家口径不同源，看走势不抠小数点。超过 250% 的点（结算批次错位）不画。", f="pct") if VSYMS else ""

# ---------- Arc 图 ----------
arc_charts = ""
if ARC_OK:
    ax = [d for d in sorted(set(A["全链DEX成交"]) | set(RH.get("全链DEX成交", {}))) if shift(ARC_MAINNET, -3) <= d <= ARC_LAST]
    arc_charts = "".join([
        line_chart([("Arc", "s7", {d: A["全链DEX成交"].get(d) for d in ax}),
                    ("Robinhood Chain", "sk", {d: RH.get("全链DEX成交", {}).get(d) for d in ax})],
                   ax, "全链 DEX 成交 · Arc vs Robinhood Chain",
                   "DefiLlama overview/dexs。Robinhood Chain 作为对标基准画成灰线。",
                   short={"Arc": "Arc", "Robinhood Chain": "RH"}),
        line_chart([("Arc ÷ Robinhood", "s7", {d: div(A["全链DEX成交"].get(d), RH.get("全链DEX成交", {}).get(d)) for d in ax})],
                   ax, "Arc DEX 成交 ÷ Robinhood Chain",
                   f"虚线 = 升级条件 C 的阈值 {TH_C:.0%}（按 7 日合计判定，这里画的是逐日值）。",
                   f="pct", ref=(TH_C, f"条件 C {TH_C:.0%}"), short={"Arc ÷ Robinhood": "Arc÷RH"}),
        line_chart([("Arc 发射台合计", "s7", {d: A["发射台手续费"].get(d) for d in ax if d >= ARC_MAINNET})],
                   ax, "Arc 发射台手续费合计（逐日）",
                   f"DefiLlama 类目 = Launchpad 的协议加总，当前 {A.get('发射台数量', 0)} 家。虚线 = 条件 A 阈值。",
                   ref=(TH_A, f"条件 A {usd(TH_A)}/日"), short={"Arc 发射台合计": "发射台"}),
        line_chart([("Arc", "s7", {d: A["TVL"].get(d) for d in ax}),
                    ("Robinhood Chain", "sk", {d: RH.get("TVL", {}).get(d) for d in ax})],
                   ax, "TVL · Arc vs Robinhood Chain",
                   "TVL 成分和 meme 交易关系不大（Robinhood Chain 一半以上是 Morpho 稳定币理财），只作背景。",
                   short={"Arc": "Arc", "Robinhood Chain": "RH"}),
    ])


# ======================================================================
# 页面
# ======================================================================
def delta(v):
    if v is None:
        return '<span class="d">—</span>'
    return f'<span class="d {"up" if v > 0 else "dn"}">{"▲" if v > 0 else "▼"} {abs(v)*100:.1f}%</span>'


def cell_money(v, delayed=False):
    return '<span class="chip warn"><b>!</b>延迟</span>' if (delayed or v is None) else f"{v:,.0f}"


def kpi(label, value, sub, extra=""):
    return f'<div class="kpi{extra}"><div class="k">{label}</div><div class="v">{value}</div><div class="ds">{sub}</div></div>'


def plat_kpi(s, label):
    x = R.get(s)
    if not x:
        return kpi(label, "未接入", "本期数据文件里没有这家")
    if x["延迟"]:
        return kpi(label, '<span class="chip warn"><b>!</b>延迟</span>', f"最后一天 {LASTD[s]}")
    return kpi(label, usd(x["当日手续费"]), f"日环比 {delta(x['日环比'])}")


pons_k = (kpi("Pons 合计 · 当日手续费", '<span class="chip warn"><b>!</b>延迟</span>', "V1 或 V2 未出数")
          if pons_cur is None else kpi("Pons 合计 · 当日手续费", usd(pons_cur), f"日环比 {delta(pch(pons_cur, pons_prev))}"))
pe_line = " ｜ ".join(f"{s} {xx(vget(s, '回购市盈率'))}" for s in VSYMS) or "—"
pe_html = "".join(f'<span class="vs">{s} <b>{xx(vget(s, "回购市盈率"))}</b></span>' for s in VSYMS) or "—"
yld_line = " ｜ ".join(f"{s} {pct(vget(s, '回购收益率'))}" for s in VSYMS) or "—"
arc_state = ("未接入" if not ARC_OK else ("已触发 " + "、".join(ARC_NOW["trig"]) if ARC_NOW and ARC_NOW["trig"]
                                         else ("未触发" if ARC_NOW else "样本不足 7 天")))
hero = "".join([
    plat_kpi("pump.fun", "pump.fun · 当日手续费"),
    pons_k,
    plat_kpi("stonkfun", "StonkFun · 当日协议收入") if HAS_STONK else kpi("StonkFun · 当日协议收入", "未接入", "下期起接入"),
    plat_kpi("flap-sh", "Flap · 当日手续费（只看自身）"),
    kpi("pump ÷ Pons", "—" if ratio is None else f"{ratio:.2f}", "小于 1 = Pons 当日更大"),
    kpi("PONS 当日销毁", "—" if burn_last is None else f"{tok(burn_last)} 枚", f"约 {usd(burn_usd(LAST))}"),
    kpi("回购市盈率", pe_html, f"回购收益率 {esc(yld_line)}"),
    kpi("Arc 发射台 · 当日手续费", usd(A["发射台手续费"].get(ARC_LAST)) if ARC_OK else "未接入",
        f"升级条件：{esc(arc_state)}"),
])

status = []
for s in ORDER:
    ok = s not in DELAYED
    status.append(f'<span class="chip {"good" if ok else "warn"}"><b>{"✓" if ok else "!"}</b>{esc(NAME[s])}'
                  f'{"" if ok else " 延迟"}</span>')
status.append(f'<span class="chip {"good" if burn_last is not None else "warn"}"><b>{"✓" if burn_last is not None else "!"}</b>PONS 链上销毁</span>')
status.append(f'<span class="chip {"good" if VSYMS else "warn"}"><b>{"✓" if VSYMS else "!"}</b>估值</span>')
status.append(f'<span class="chip {"good" if ARC_OK else "warn"}"><b>{"✓" if ARC_OK else "!"}</b>Arc 链</span>')
banner = ""
if AGE > 2:
    banner = (f'<div class="banner"><b>!</b> 数据停在 {LAST}（距今 {AGE} 天），不是最新一期。'
              f'{esc(os.environ.get("BANNER_NOTE", "数据源恢复后按日自动更新。"))}</div>')

main_rows = ""
for x in rows:
    dl = x["延迟"]
    main_rows += (f'<tr><td class="nm">{esc(x["名称"])}<span class="ch">{esc(x["链"])}</span></td>'
                  f'<td>{cell_money(x["当日手续费"], dl)}</td><td>{delta(x["日环比"])}</td>'
                  f'<td>{"—" if dl else n0(x["7日均"])}</td><td>{"—" if dl else delta(x["7日均环比"])}</td>'
                  f'<td>{cell_money(x["当日收入"], dl)}</td><td>{pct(x["分账比率"])}</td>'
                  f'<td>{pct(x["占赛道份额"])}</td><td>{pct(x["距单日峰值"])}</td><td>{n0(x["累计"])}</td></tr>')

head7 = "".join(f"<th>{x[5:]}</th>" for x in W7)


def row7(name, getter, f="usd"):
    tds = ""
    for x in W7:
        v = getter(x)
        if v is None:
            tds += "<td>—</td>"
        elif f == "pct":
            tds += f"<td>{v*100:.1f}%</td>"
        elif f == "ratio":
            tds += f"<td>{v:.2f}</td>"
        else:
            tds += f"<td>{v:,.0f}</td>"
    return f'<tr><th class="rh">{esc(name)}</th>{tds}</tr>'


t7 = [f'<table class="t7"><tr><th class="rh">指标（UTC 日）</th>{head7}</tr>']
for s in ORDER:
    t7.append(row7(P[s]["名称"] + " 手续费", lambda x, s=s: fee(s, x)))
t7.append(row7("Pons 合计", pons))
t7.append(row7("赛道 Top60 总量", lambda x: TOT.get(x)))
for n, k, c in PLAT_SERIES:
    t7.append(row7(f"{n} 份额", lambda x, k=k: div(FM[k].get(x), TOT.get(x)), "pct"))
t7.append(row7("pump ÷ Pons", lambda x: div(fee("pump.fun", x), pons(x)), "ratio"))
t7.append(row7("V2 占 Pons", lambda x: div(fee("pons-v2", x), pons(x)), "pct"))
t7.append(row7("PONS 当日销毁（枚）", lambda x: burn_daily.get(x), "num"))
t7.append("</table>")

# 估值表
val_rows = ""
for s in VSYMS:
    r, m = vr(s), VMETA[s]
    if not r:
        val_rows += f'<tr><td class="nm">{s}<span class="ch">{esc(m["平台"])}</span></td><td colspan="6">当日无估值行</td></tr>'
        continue
    flag = ' <span class="warnmark" title="滚动窗口不足 30 天">⚠</span>' if r["窗口不足30天"] else ""
    val_rows += (f'<tr><td class="nm">{s}<span class="ch">{esc(m["平台"])} · {esc(m["链"])}</span></td>'
                 f'<td>{n0(r["市值"])}</td><td>{n0(r["年化协议收入"])}</td><td>{xx(r["收入市盈率"], 2)}</td>'
                 f'<td>{n0(r["年化回购额"])}</td><td><b>{xx(r["回购市盈率"], 2)}</b>{flag}</td><td>{pct(r["回购收益率"])}</td></tr>')
val_rows += ('<tr><td class="nm">Flap<span class="ch">无平台币</span></td><td>—</td><td>—</td>'
             '<td>不适用</td><td>—</td><td>不适用</td><td>—</td></tr>')
supply_notes = []
for s in VSYMS:
    sp = (VMETA[s] or {}).get("供应快照")
    if sp and sp.get("流通量"):
        supply_notes.append(f"{s} CoinGecko 流通量 {sp['流通量']:,.0f} / 总量 {(sp.get('总量') or 0):,.0f}（{sp['读取日']}）")


def tva_row(label, sym, key, f="usd"):
    tds = ""
    for x in W7:
        v = (VROWS.get(sym, {}).get(x) or {}).get(key)
        tds += "<td>—</td>" if v is None else (f"<td>{v*100:.1f}%</td>" if f == "pct" else f"<td>{v:,.0f}</td>")
    return f'<tr><th class="rh">{esc(label)}</th>{tds}</tr>'


tva_table = (f'<table class="t7"><tr><th class="rh">近 7 天（美元 / 枚）</th>{head7}</tr>'
             + "".join(tva_row(f"{s} 协议收入", s, "当日协议收入") + tva_row(f"{s} 理论回购额", s, "当日理论回购额")
                       + tva_row(f"{s} 实际回购额", s, "当日回购额") + tva_row(f"{s} 回购占收入", s, "当日回购占收入", "pct")
                       + tva_row(f"{s} 回购代币数", s, "当日回购代币数") for s in VSYMS)
             + "</table>") if VSYMS else ""

# Arc 表
arc_block = '<div class="empty">Arc 数据尚未接入（拉Arc.py 未产出 Arc数据.json）</div>'
if ARC_OK:
    def cond(label, cur, th, ok, unit):
        return (f'<tr><td class="nm">{label}</td><td>{cur}</td><td>{th}</td>'
                f'<td><span class="chip {"good" if ok else "idle"}"><b>{"✓" if ok else "·"}</b>{"已满足" if ok else "未满足"}</span></td></tr>')
    cond_rows = ""
    if ARC_NOW:
        cond_rows = (cond("A · Arc 发射台合计手续费，最近 7 天每天都 ≥ 阈值", usd(ARC_NOW["A"]) + "（7 天最低）",
                          usd(TH_A) + "/日", "A" in ARC_NOW["trig"], "")
                     + cond(f"B · 任一 Arc 发射台手续费，最近 7 天每天都 ≥ 阈值", usd(ARC_NOW["B"]) + f"（{esc(ARC_NOW['B名'])}，7 天最低）",
                            usd(TH_B) + "/日", "B" in ARC_NOW["trig"], "")
                     + cond("C · Arc 全链 DEX 成交 7 日合计 ÷ Robinhood Chain", pct(ARC_NOW["C"]),
                            f"{TH_C:.0%}", "C" in ARC_NOW["trig"], ""))
    else:
        cond_rows = '<tr><td colspan="4">Arc 完整日不足 7 天，条件暂不评估</td></tr>'
    lp_rows = ""
    show = LPS[:12]
    if TOLLY and TOLLY not in show:
        show.append(TOLLY)
    for z in show:
        hl = ' class="hl"' if z is TOLLY else ""
        tag = ' <span class="tag">待办关注</span>' if z is TOLLY else ""
        lp_rows += (f'<tr{hl}><td class="nm">{esc(z["名称"])}{tag}</td>'
                    f'<td>{n0(z["当日"])}</td><td>{n0(z["7日"])}</td><td>{pct(div(z["7日"], LP7))}</td>'
                    f'<td>{n0(z["30日"])}</td><td>{n0(z["7日DEX"]) if z["7日DEX"] else "—"}</td><td>{spark(z["序列"])}</td></tr>')
    ak = "".join([
        kpi("Arc 全链手续费", usd(A["全链手续费"].get(ARC_LAST)), f"日环比 {delta(pch(A['全链手续费'].get(ARC_LAST), A['全链手续费'].get(shift(ARC_LAST, -1))))}"),
        kpi("Arc 全链 DEX 成交", usd(A["全链DEX成交"].get(ARC_LAST)),
            f"Robinhood Chain {usd(RH.get('全链DEX成交', {}).get(ARC_LAST))}"),
        kpi("Arc TVL", usd(A["TVL"].get(ARC_LAST)), f"Robinhood Chain {usd(RH.get('TVL', {}).get(ARC_LAST))}"),
        kpi("Arc 发射台 7 日合计", usd(LP7), f"第一名 {esc(TOP['名称']) if TOP else '—'} {usd(TOP['7日']) if TOP else ''}"),
    ])
    arc_block = (f'<div class="hero small">{ak}</div>'
                 f'<h3>升级条件（任一满足 → 挑出头部发射台做逐家平台收入监控）</h3>'
                 f'<div class="tbl"><table><tr><th class="rh">条件</th><th>当前</th><th>阈值</th><th>状态</th></tr>{cond_rows}</table></div>'
                 f'<p class="sub">阈值是初始设定：A 约为 Pons 近期日手续费的 1/8，B 约为 StonkFun 的 1/8，C 看整链成交是否到了 Robinhood Chain 的四分之一。'
                 f'要求连续 7 天，是为了不被上线头几天的脉冲骗到。</p>'
                 f'<div class="grid2">{arc_charts}</div>'
                 f'<h3>Arc 发射台排行（按 7 日手续费，截至 {ARC_LAST}）</h3>'
                 f'<div class="tbl"><table><tr><th class="rh">发射台</th><th>当日手续费</th><th>7 日合计</th><th>占 Arc 发射台</th>'
                 f'<th>30 日合计</th><th>7 日 DEX 成交</th><th>近 14 天</th></tr>{lp_rows}</table></div>')

tolly_txt = (f"Tolly 当日手续费 {usd(TOLLY['当日'])}，7 日 {usd(TOLLY['7日'])}，在 Arc 发射台里排第 {LPS.index(TOLLY)+1}。"
             if TOLLY else "Tolly 本期未出现在 DefiLlama 的 Arc 协议列表里。")
fix_recent = [f for f in FIXES if f["日期"] >= shift(LAST, -40)]
fix_txt = ""
if fix_recent:
    fix_txt = ("<p class=\"sub\">口径切换后重算、与旧值不一致的日期（旧值来自 11:00 UTC 读数差或事件扫描）："
               + "；".join(f"{f['日期']} 旧 {f['旧值']:,.0f} → 新 {f['新值']:,.0f}" for f in fix_recent[-12:]) + "。</p>")

CSS = r"""
:root{--bg:#fbfbfa;--panel:#f1f2f3;--ink:#16181b;--ink2:#464b53;--muted:#737982;--rule:#e4e6e9;--rule2:#d2d5da;
--grid:#ebedef;--accent:#8a5a00;--accent-soft:#f7eedb;--up:#1f63a8;--dn:#b3302e;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s7:#4a3aa7;--sk:#8d939b;
--good:#0ca30c;--warn:#fab219;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#131416;--panel:#1c1e21;--ink:#eceef0;--ink2:#bdc2c8;
--muted:#8d939b;--rule:#2a2d31;--rule2:#3a3e44;--grid:#222529;--accent:#dcae4b;--accent-soft:#2b2416;--up:#6fa9ec;--dn:#ef7d7a;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s7:#9085e9;--sk:#7c828a;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#131416;--panel:#1c1e21;--ink:#eceef0;--ink2:#bdc2c8;--muted:#8d939b;--rule:#2a2d31;--rule2:#3a3e44;
--grid:#222529;--accent:#dcae4b;--accent-soft:#2b2416;--up:#6fa9ec;--dn:#ef7d7a;--s1:#3987e5;--s2:#d95926;--s3:#199e70;
--s4:#c98500;--s7:#9085e9;--sk:#7c828a;color-scheme:dark}
*{box-sizing:border-box}
html,body{background:var(--bg)}
body{margin:0;color:var(--ink);font:15px/1.62 "IBM Plex Sans","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding-inline:20px;padding-block:36px 64px}
.eyebrow{font-size:12px;letter-spacing:.14em;color:var(--accent);font-weight:600}
h1{font-family:"Noto Serif SC","Songti SC","STSong","Noto Serif CJK SC",serif;font-weight:700;font-size:36px;line-height:1.2;margin:6px 0 8px;text-wrap:balance}
h2{font-family:"Noto Serif SC","Songti SC","STSong","Noto Serif CJK SC",serif;font-weight:700;font-size:22px;margin:0 0 4px;text-wrap:balance}
h3{font-size:15px;margin:26px 0 6px}
.meta{color:var(--muted);font-size:13.5px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:12px;line-height:1;padding:5px 9px;border-radius:999px;border:1px solid var(--rule2);color:var(--ink2);white-space:nowrap}
.chip b{font-size:11px}
.chip.good b{color:var(--good)} .chip.warn{border-color:var(--warn)} .chip.warn b{color:var(--warn)} .chip.idle b{color:var(--muted)}
.banner{margin-top:16px;padding:10px 14px;border-radius:8px;background:var(--accent-soft);font-size:13.5px;color:var(--ink2)}
.banner b{color:var(--accent)}
nav{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--bg);border-bottom:1px solid var(--rule);margin:22px 0 0;padding:8px 0;display:flex;flex-wrap:wrap;gap:4px 16px;font-size:13px}
nav a{color:var(--ink2);text-decoration:none} nav a:hover,nav a:focus-visible{color:var(--accent)}
.hero{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px 24px;margin:26px 0 6px}
.hero.small{grid-template-columns:repeat(4,minmax(0,1fr));margin-top:14px}
.kpi{border-top:1px solid var(--rule2);padding-top:10px;min-width:0}
.kpi .k{font-size:12px;color:var(--muted);letter-spacing:.02em}
.kpi .v{font-size:26px;font-weight:600;font-variant-numeric:tabular-nums;line-height:1.25;margin:2px 0;overflow-wrap:anywhere}
.kpi .v .vs{display:block;font-size:14.5px;font-weight:500;line-height:1.5;color:var(--ink2)} .kpi .v .vs b{font-size:17px;color:var(--ink);font-weight:600}
.kpi .ds{font-size:12.5px;color:var(--ink2);font-variant-numeric:tabular-nums}
.d{font-variant-numeric:tabular-nums;white-space:nowrap} .up{color:var(--up)} .dn{color:var(--dn)}
section{margin-top:48px;scroll-margin-top:48px}
.sub{color:var(--muted);font-size:13.5px;margin:4px 0 10px;max-width:80ch}
.tbl{overflow-x:auto;margin-top:10px}
table{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}
th,td{padding:8px 10px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap}
th{font-size:12px;color:var(--muted);font-weight:500}
td.nm,th.rh{text-align:left;font-weight:600;color:var(--ink)}
.ch{display:block;font-weight:400;font-size:11.5px;color:var(--muted)}
.t7{font-size:12.5px} .t7 td,.t7 th{padding:6px 8px}
tr.hl td{background:var(--accent-soft)}
.tag{font-size:11px;font-weight:500;color:var(--accent);margin-left:6px}
.warnmark{color:var(--warn)}
.note{background:var(--panel);border-radius:8px;padding:14px 16px;margin:16px 0;font-size:13.5px;color:var(--ink2);max-width:92ch}
.note b{color:var(--ink)}
code{font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-size:.9em;overflow-wrap:anywhere}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:30px 34px;margin-top:14px}
figure.chart{margin:0;min-width:0}
figure.chart:focus-visible{outline:2px solid var(--accent);outline-offset:4px;border-radius:4px}
.ct{font-weight:600;font-size:14.5px}
.cs{color:var(--muted);font-size:12.5px;line-height:1.55;margin-top:2px}
.lg{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--ink2);margin:8px 0 2px}
.lg span{display:inline-flex;align-items:center;gap:6px}
.key{display:inline-block;width:14px;height:0;border-top:2px solid var(--sk)}
.key.dash{border-top-style:dashed}
.key.s1{border-color:var(--s1)}.key.s2{border-color:var(--s2)}.key.s3{border-color:var(--s3)}.key.s4{border-color:var(--s4)}.key.s7{border-color:var(--s7)}.key.sk{border-color:var(--sk)}
.plot{position:relative;overflow-x:auto}
.plot svg{display:block;width:100%;min-width:520px;height:auto}
.empty{padding:28px 0;color:var(--muted);font-size:13px}
svg .grid{stroke:var(--grid);stroke-width:1} svg .axis{stroke:var(--rule2);stroke-width:1}
svg .ax{fill:var(--muted);font-size:11px;font-family:"IBM Plex Sans",system-ui,sans-serif}
svg .lab{fill:var(--ink2);font-size:11.5px;font-family:"IBM Plex Sans",system-ui,sans-serif} svg .labv{fill:var(--ink);font-weight:600}
svg .ln{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round} svg .dsh{stroke-dasharray:5 4}
svg .s1{stroke:var(--s1)} svg .s2{stroke:var(--s2)} svg .s3{stroke:var(--s3)} svg .s4{stroke:var(--s4)} svg .s7{stroke:var(--s7)} svg .sk{stroke:var(--sk)}
svg .f1{fill:var(--s1)} svg .f2{fill:var(--s2)} svg .f3{fill:var(--s3)} svg .f4{fill:var(--s4)} svg .f7{fill:var(--s7)} svg .fk,svg .fsk{fill:var(--sk)}
svg .end{stroke:var(--bg);stroke-width:2}
svg .ref{stroke:var(--muted);stroke-width:1;stroke-dasharray:4 4}
svg .xhair{stroke:var(--ink2);stroke-width:1}
svg .hdot{stroke:var(--bg);stroke-width:2}
svg.spk{width:96px;height:22px;display:block;margin-left:auto} svg.spk .ln{stroke-width:1.5}
.tip{position:absolute;top:6px;pointer-events:none;background:var(--bg);border:1px solid var(--rule2);border-radius:6px;padding:7px 10px;font-size:12px;box-shadow:0 6px 18px rgba(0,0,0,.10);min-width:150px;z-index:3}
.tt-d{color:var(--muted);font-size:11.5px;margin-bottom:3px}
.tt-r{display:flex;align-items:center;gap:7px;line-height:1.7}
.tt-r b{font-variant-numeric:tabular-nums;min-width:62px}
.tt-r span{color:var(--muted)}
.tt-r i{display:inline-block;width:12px;border-top:2px solid var(--sk)}
.tt-r i.s1{border-color:var(--s1)}.tt-r i.s2{border-color:var(--s2)}.tt-r i.s3{border-color:var(--s3)}.tt-r i.s4{border-color:var(--s4)}.tt-r i.s7{border-color:var(--s7)}
ul.gaps{padding-left:20px;font-size:14px;color:var(--ink2);max-width:92ch} ul.gaps li{margin:5px 0}
footer{margin-top:56px;padding-top:16px;border-top:1px solid var(--rule);color:var(--muted);font-size:12.5px}
@media (max-width:900px){.grid2{grid-template-columns:1fr}.hero,.hero.small{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:420px){h1{font-size:28px}.kpi .v{font-size:22px}}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
"""

JS = r"""
(function(){
var el=document.getElementById('chart-data'); if(!el) return;
var D=JSON.parse(el.textContent), NS='http://www.w3.org/2000/svg';
function f(v,k){ if(v===null||v===undefined) return '—'; var a=Math.abs(v);
 if(k==='usd') return a>=1e9?'$'+(v/1e9).toFixed(2)+'B':a>=1e6?'$'+(v/1e6).toFixed(2)+'M':a>=1e3?'$'+(v/1e3).toFixed(1)+'K':'$'+v.toFixed(0);
 if(k==='tok') return a>=1e6?(v/1e6).toFixed(2)+'M':a>=1e3?(v/1e3).toFixed(1)+'K':v.toFixed(0);
 if(k==='pct') return (v*100).toFixed(1)+'%'; if(k==='x') return v.toFixed(2)+'x'; return v.toFixed(2); }
function day(d0,i){var t=new Date(d0+'T00:00:00Z'); t.setUTCDate(t.getUTCDate()+i); return t.toISOString().slice(0,10);}
document.querySelectorAll('figure.chart[data-k]').forEach(function(fig){
 var c=D[fig.getAttribute('data-k')]; if(!c) return;
 c.x=[]; c.dd=[]; for(var i=0;i<c.n;i++){ c.x.push(c.bar? c.L+c.pw/c.n*(i+0.5) : c.L+(c.n>1? c.pw*i/(c.n-1) : c.pw/2)); c.dd.push(c.d? c.d[i] : day(c.d0,i)); }
 c.s.forEach(function(s){ s.y=s.v.map(function(v){ return v===null? null : c.T+(c.B-c.T)*(1-(v-c.lo)/(c.top-c.lo)); }); });
 var svg=fig.querySelector('svg'), tip=fig.querySelector('.tip'), plot=fig.querySelector('.plot'); if(!svg||!tip) return;
 var vl=document.createElementNS(NS,'line'); vl.setAttribute('class','xhair'); vl.setAttribute('y1',c.T); vl.setAttribute('y2',c.B); vl.style.display='none'; svg.appendChild(vl);
 var dots=c.s.map(function(s){var e=document.createElementNS(NS,'circle'); e.setAttribute('r',4); e.setAttribute('class','hdot f'+s.c.slice(1)); e.style.display='none'; svg.appendChild(e); return e;});
 var cur=c.x.length-1;
 function show(i){ cur=i; var x=c.x[i]; if(!c.bar){vl.setAttribute('x1',x); vl.setAttribute('x2',x); vl.style.display='';}
  c.s.forEach(function(s,j){var y=s.y[i]; if(y===null){dots[j].style.display='none';} else {dots[j].setAttribute('cx',x); dots[j].setAttribute('cy',y); dots[j].style.display='';}});
  tip.replaceChildren(); var h=document.createElement('div'); h.className='tt-d'; h.textContent=c.dd[i]+'（UTC）'; tip.appendChild(h);
  c.s.forEach(function(s){var r=document.createElement('div'); r.className='tt-r'; var k=document.createElement('i'); k.className=s.c;
   var b=document.createElement('b'); b.textContent=f(s.v[i],c.f); var n=document.createElement('span'); n.textContent=s.n; r.append(k,b,n); tip.appendChild(r);});
  tip.hidden=false; var sc=svg.getBoundingClientRect().width/c.W, px=x*sc, w=tip.offsetWidth;
  tip.style.left=(px+14+w>svg.getBoundingClientRect().width? Math.max(0,px-14-w): px+14)+'px'; }
 function hide(){ vl.style.display='none'; dots.forEach(function(d){d.style.display='none';}); tip.hidden=true; }
 svg.addEventListener('pointermove',function(ev){var bb=svg.getBoundingClientRect(), x=(ev.clientX-bb.left)*c.W/bb.width, bi=0, bd=1e9;
  c.x.forEach(function(xx,i){var d=Math.abs(xx-x); if(d<bd){bd=d;bi=i;}}); show(bi);});
 svg.addEventListener('pointerleave',hide); fig.addEventListener('blur',hide);
 fig.addEventListener('focus',function(){show(cur);});
 fig.addEventListener('keydown',function(ev){ if(ev.key==='ArrowLeft'){show(Math.max(0,cur-1)); ev.preventDefault();}
  if(ev.key==='ArrowRight'){show(Math.min(c.x.length-1,cur+1)); ev.preventDefault();} });
});
})();
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&'
         'family=IBM+Plex+Mono:wght@500&family=Noto+Serif+SC:wght@700&display=swap">')

flap_note = ("<b>Flap 必须单独看，不能和另外几家比大小。</b>它是税代币模型，费用来自代币转账税。链上 "
             "<code>TaxProcessor.feeConfig()</code> 实测四个代币 <code>feeRate</code> 全部 = 1000 bps，即税收的 10% 归协议、"
             "90% 按 <code>marketBps / deflationBps / lpBps / dividendBps</code> 分给项目方钱包 / 销毁 / 加池 / 持币分红。"
             "DefiLlama 于 2026-08-31 变更了 flap-sh 的算法：此前 fees 与 revenue 完全相等，08-31 起 fees 记全额转账税、"
             "revenue 记协议实得，<b>fees 曲线在 08-31 有人为断点，前后不可直接比较</b>；而长期相等的那段与合约的 90/10 分账对不上，差异未解释。")
stonk_tbl_note = ("<b>StonkFun 横向比较只用协议收入口径。</b>DefiLlama 对 stonkfun 的 fees 只记平台自己那份"
                  "（联合曲线 1% 平台费 + 毕业池创建者费 + 锁仓流动性分成），revenue 与 fees 相等，所以分账比率恒为 100%；"
                  "pump.fun 的 fees 含创作者费，直接拿 fees 比会系统性低估 StonkFun。") if HAS_STONK else ""

CH_JSON = json.dumps(CH, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
inner = f"""
<header>
 <div class="eyebrow">链上发币一级市场 · 日更</div>
 <h1>发射台日更看板</h1>
 <div class="meta">pump.fun · Pons · StonkFun · Flap · Arc 链 ｜ 数据截至 <b>{LAST}</b>（UTC 完整日）｜ 生成于 {GEN} UTC</div>
 <div class="chips">{"".join(status)}</div>
 {banner}
</header>
<nav aria-label="目录"><a href="#s1">横截面</a><a href="#s2">近 7 天</a><a href="#s3">趋势</a><a href="#s4">PONS 销毁</a>
<a href="#s5">估值</a><a href="#s6">理论 vs 实际</a><a href="#s7">回购占收入</a><a href="#s8">Arc 链</a><a href="#s9">口径</a></nav>

<div class="hero">{hero}</div>

<section id="s1"><h2>一 · 当日横截面</h2>
<p class="sub">UTC {LAST} 完整日。标「延迟」的是 DefiLlama 还没出数，没有拿旧值顶替。</p>
<div class="tbl"><table><tr><th class="rh">平台</th><th>当日手续费</th><th>日环比</th><th>7 日均</th><th>7 日均环比</th>
<th>当日协议收入</th><th>分账比率</th><th>赛道份额</th><th>距单日峰值</th><th>累计手续费</th></tr>{main_rows}</table></div>
<div class="note">{flap_note}</div>
{f'<div class="note">{stonk_tbl_note}</div>' if stonk_tbl_note else ''}
</section>

<section id="s2"><h2>二 · 近 7 天逐日</h2>
<p class="sub">这张表用来发现异常：某一行突然跳一个数量级，通常不是市场变了，是平台改了规则或结算批次错位。日环比只当异常探测器用。</p>
<div class="tbl">{"".join(t7)}</div>
</section>

<section id="s3"><h2>三 · 趋势</h2>
<p class="sub">悬停或用键盘左右键看逐日读数。自 2026-09-01 起 pump.fun 改为按市值分档的动态费率，「手续费下降」不一定等于「成交量下降」，要拆开说。</p>
<div class="grid2">{trend_charts}</div>
</section>

<section id="s4"><h2>四 · PONS 回购与销毁</h2>
<div class="tbl"><table><tr><th class="rh">项</th><th>数值</th><th class="rh">说明</th></tr>
<tr><td class="nm">销毁地址累计持仓（{LAST} 日末）</td><td>{n0(BURNED)} PONS</td><td class="nm">balanceOf(dEaD)，{BURN_BASIS}</td></tr>
<tr><td class="nm">已销毁占总量</td><td>{pct(div(BURNED, SUPPLY))}</td><td class="nm">totalSupply 恒为 10 亿，销毁不减少它</td></tr>
<tr><td class="nm">burn-adjusted 流通</td><td>{n0(ADJ)} PONS</td><td class="nm">真实在外流通</td></tr>
<tr><td class="nm">按 totalSupply 算市值的高估幅度</td><td>{pct(div(SUPPLY, ADJ) - 1 if ADJ else None)}</td><td class="nm">约 41%（不是 29%，29% 是已销毁占比），一律用 burn-adjusted</td></tr>
<tr><td class="nm">PONS 价格（{LAST} 收盘）</td><td>{"—" if pons_px(LAST) is None else f"${pons_px(LAST):.4f}"}</td><td class="nm">GeckoTerminal 最深池日线，历史销毁一律按当日收盘价计价</td></tr>
<tr><td class="nm">PONS 价格（实时参考）</td><td>{"—" if PX_LIVE is None else f"${PX_LIVE:.4f}"}</td><td class="nm">DexScreener，⛔ 不用于历史回购额</td></tr>
<tr><td class="nm">当日销毁</td><td>{n0(burn_last)} PONS</td><td class="nm">约 {usd(burn_usd(LAST))}</td></tr>
<tr><td class="nm">近 7 日销毁合计</td><td>{n0(sum(v for v in burn7 if v) if any(burn7) else None)} PONS</td><td class="nm">约 {usd(burn7_usd or None)}，逐日按当天收盘价折算后加总</td></tr>
</table></div>
{fix_txt}
<div class="note">三条口径警告：<br>
一、销毁是把币转到 <code>0x…dEaD</code>，不是调用 <code>burn()</code>，<code>totalSupply()</code> 不会减少。<br>
二、官方回购比例（协议费的 80%）是<b>人工在跑，不是合约强制</b>。逐日销毁呈批次跳跃而非连续流，就是链上证据，意味着它随时可以停。<br>
三、DefiLlama 的 revenue / fees 与官方文档的分账比例对不上，两个都记，差异未解释。</div>
</section>

<section id="s5"><h2>五 · 回购市盈率与估值</h2>
<p class="sub">手续费告诉你平台在赚多少，市盈率才告诉你这个价格贵不贵。市值一律 burn-adjusted 流通市值，年化取近 30 日滚动合计外推，回购市盈率是头条指标。</p>
<div class="tbl"><table><tr><th class="rh">代币</th><th>burn-adjusted 市值</th><th>年化协议收入</th><th>收入市盈率</th>
<th>年化回购额</th><th>回购市盈率</th><th>回购收益率</th></tr>{val_rows}</table></div>
<div class="grid2">{val_charts}</div>
<div class="note">四条口径提醒：<br>
一、用 30 天外推来年化发射台手续费，<b>旺季会系统性低估市盈率、淡季高估</b>。看趋势，不要抠绝对值。标 ⚠ 的行表示滚动窗口不足 30 天。<br>
二、三家的回购额来源不同：PUMP 取 DefiLlama <code>dailyHoldersRevenue</code>（汇总 pump 全部产品线）；STONK 同样取 DefiLlama <code>dailyHoldersRevenue</code>（Jupiter 上买回 STONK 的 swap）；PONS 是链上自算（当日销毁枚数 × 当日收盘价）。跨代币比较要记得这一点。<br>
三、<b>PONS 的回购是人工在跑、不是合约强制；STONK 的 60% 回购是官网政策、不是链上规则。</b>市盈率低不等于这笔现金流有约束力。<br>
四、Flap 没有权益型平台币，市盈率一律「不适用」。bBroker（BSC <code>0xf1969F437Fe3C485468FB17B0d9861c24DCd7777</code>）是 bBroker Vault 的 NFT 金库配套代币，价值来自金库分红而不是平台手续费，不能拿它算市盈率。
{("<br>供应核对：" + "；".join(esc(s) for s in supply_notes) + "。STONK 若流通量接近 10 亿，说明 CoinGecko 没扣销毁，市值需改为 (总量 − 已销毁) × 价格。") if supply_notes else ""}</div>
</section>

<section id="s6"><h2>六 · 理论回购 vs 实际回购</h2>
<p class="sub">理论 = 按公开口径「应该」回购多少；实际 = 链上/官方口径已经执行了多少。差额可能是当天没全部执行，也可能是记账时间错位（今天的收入明天才回购）。回购代币数只在表里给，三家单价差几个数量级，不放进同一张图。</p>
<div class="tbl">{tva_table}</div>
<div class="grid2">{tva_charts}</div>
</section>

<section id="s7"><h2>七 · 协议收入里有多少真花在回购上</h2>
<p class="sub">不是理论测算，是已经发生的回购额 ÷ 当天协议收入。比例超过 100% 通常是结算发生在收入入账的下一天，不代表回购超支。Flap 没有平台币回购机制，不参与对比。</p>
<div class="grid2">{bbr_chart}</div>
</section>

<section id="s8"><h2>八 · Arc 链观察</h2>
<p class="sub">Circle 的 Arc（Chain ID 5042，gas = USDC）2026-09-16 主网上线。先看整条链热不热，热起来再挑头部发射台做逐家平台收入监控。Robinhood Chain 作为对标。</p>
{arc_block}
<div class="note">{esc(tolly_txt)} Tolly 的机制已核实（官方 guide）：不走 bonding curve，全部供应直接进永久锁定的 USDC 池；每笔 1% 池费，
买入费（USDC）64% 给创建者、12% 持币分红、10% 协议、9% 买 TOLLY 销毁、5% 销毁项目代币；卖出费（项目代币）100% 销毁。
TOLLY 销毁与分红监控还缺金库、分红池、销毁去向三个地址，要先去 GitHub 仓库或 Arc 浏览器核实。<br>
⚠️ Arc 上不少发射台的 swap 走 Uniswap 底层池，DEX 成交记在 Uniswap 名下，发射台的 DEX 成交系统性偏低，发射台看手续费更可靠；Dune 口径与 DefiLlama 口径对不上是已知问题。</div>
</section>

<section id="s9"><h2>九 · 口径与已知缺口</h2>
<ul class="gaps">
<li><b>全部用手续费（fees）口径，不用成交量口径。</b>DefiLlama 对发射台类目的 volume 覆盖不全，且会把共享基础设施的成交量算给基础设施而非品牌，用 volume 做份额会系统性低估 Solana。</li>
<li><b>只报昨天（UTC）的完整日。</b>当天那根永远不完整，已剔除；某家延迟就标「延迟」，⛔ 不拿旧值冒充新值。</li>
<li><b>Flap 单独看</b>；<b>StonkFun 跨平台比较用协议收入</b>；<b>绝不拿峰值比现在就说某个平台失败</b>，先看份额。</li>
<li>推算成交额（手续费 ÷ 费率）不做日频，放月度工作流：pump.fun 自 2026-09-01 起按市值分档动态收费（8.5 万美元市值是分账断点：以下协议费 0.93–0.95%、创建者 0.30%；以上协议费 0.05%、创建者 0.95%），日频推算等于每天用一个错的费率相乘。</li>
<li>「pump.fun 手续费」不含 PumpSwap（DefiLlama 拆成 pump.fun / pumpswap / pump.fun-mobile-app 三条，PumpSwap 30 天手续费比主站还大），两期之间不换口径。</li>
<li>赛道总量只加总 Top60（Launchpad 类目共 {D.get('Launchpad协议总数', '—')} 个），尾部未计入，实际总量略高。</li>
<li>Flap 的成交额反推不了（税代币模型），需要链上扫。Pons V2 存活率未测，V1 是 2.37%。pump.fun 毕业前后的手续费拆分需要读链上 FeeConfig，放周频。</li>
<li>Bags、Binance Alpha、Meteora DBC、four.meme、clanker、BONK.fun 的费率未核实。</li>
<li>本页只给数字，不构成任何投资建议。</li>
</ul>
</section>
"""
foot = f"""<footer>数据源：DefiLlama Fees / DEX / TVL API ｜ Robinhood Chain 公共节点 <code>rpc.mainnet.chain.robinhood.com</code>（Chain ID 4663）｜ CoinGecko ｜ GeckoTerminal ｜ DexScreener<br>
产品大叔 ｜ Crypto PM　@Uncle_Onchain　·　内部研究台账，不构成投资建议</footer>"""
scripts = f'<script type="application/json" id="chart-data">{CH_JSON}</script>\n<script>{JS}</script>'
body = f'\n<div class="wrap">\n{inner}\n{foot}\n</div>\n{scripts}\n'

TITLE = f"发射台日更看板 · {LAST}"
frag = f"<title>发射台日更看板</title>\n{FONTS}\n<style>{CSS}</style>\n{body}"     # Artifact 标题保持不变
full = (f'<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        f"<title>{TITLE}</title>\n{FONTS}\n<style>{CSS}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n")
with open(os.path.join(OUT, "发射台日更看板.html"), "w", encoding="utf-8") as fh:
    fh.write(full)
with open(os.path.join(OUT, "看板页.html"), "w", encoding="utf-8") as fh:
    fh.write(frag)

# ======================================================================
# CSV
# ======================================================================
csv_path = os.path.join(OUT, f"发射台日更-{LAST}.csv")
with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["日期", "平台", "链", "当日手续费USD", "日环比", "7日均", "7日均环比", "当日协议收入USD",
                "分账比率revenue/fees", "占赛道份额", "距单日峰值", "单日峰值USD", "峰值日", "累计USD", "状态"])
    for x in rows:
        w.writerow([LAST, x["名称"], x["链"], "" if x["当日手续费"] is None else round(x["当日手续费"], 2),
                    "" if x["日环比"] is None else round(x["日环比"], 4), "" if x["7日均"] is None else round(x["7日均"], 2),
                    "" if x["7日均环比"] is None else round(x["7日均环比"], 4),
                    "" if x["当日收入"] is None else round(x["当日收入"], 2),
                    "" if x["分账比率"] is None else round(x["分账比率"], 4),
                    "" if x["占赛道份额"] is None else round(x["占赛道份额"], 4),
                    "" if x["距单日峰值"] is None else round(x["距单日峰值"], 4),
                    "" if x["单日峰值"] is None else round(x["单日峰值"], 2), x["峰值日"], x["累计"],
                    "延迟" if x["延迟"] else "正常"])
    w.writerow([])
    w.writerow(["日期", "赛道Top60日总量", "Pons合计", "V2占Pons", "pump÷Pons", "PONS当日销毁枚数", "PONS收盘价USD",
                "当日回购额USD", "销毁地址日末持仓", "burn_adjusted流通"])
    w.writerow([LAST, round(TOT.get(LAST) or 0, 2), "" if pons_cur is None else round(pons_cur, 2),
                "" if v2share is None else round(v2share, 4), "" if ratio is None else round(ratio, 4),
                "" if burn_last is None else round(burn_last, 2), pons_px(LAST) or "",
                "" if burn_usd(LAST) is None else round(burn_usd(LAST), 2),
                "" if BURNED is None else round(BURNED, 2), "" if ADJ is None else round(ADJ, 2)])
    w.writerow([])
    w.writerow(["日期", "代币", "平台", "burn_adjusted市值USD", "年化协议收入USD", "收入市盈率", "年化回购额USD",
                "回购市盈率", "回购收益率", "滚动窗口天数"])
    for s in VSYMS:
        r = vr(s)
        if not r:
            continue
        w.writerow([LAST, s, VMETA[s]["平台"], round(r["市值"], 2), round(r["年化协议收入"], 2),
                    "" if r["收入市盈率"] is None else round(r["收入市盈率"], 3), round(r["年化回购额"], 2),
                    "" if r["回购市盈率"] is None else round(r["回购市盈率"], 3),
                    "" if r["回购收益率"] is None else round(r["回购收益率"], 5), r["窗口天数"]])
    w.writerow([LAST, "FLAP", "Flap sh", "", "", "不适用（无平台币）", "", "不适用", "", ""])
    if ARC_OK:
        w.writerow([])
        w.writerow(["日期", "Arc全链手续费", "Arc全链DEX成交", "ArcTVL", "Arc发射台手续费合计", "Robinhood全链DEX成交",
                    "RobinhoodTVL", "升级条件"])
        w.writerow([ARC_LAST, A["全链手续费"].get(ARC_LAST), A["全链DEX成交"].get(ARC_LAST), A["TVL"].get(ARC_LAST),
                    A["发射台手续费"].get(ARC_LAST), RH.get("全链DEX成交", {}).get(ARC_LAST),
                    RH.get("TVL", {}).get(ARC_LAST), arc_state])
        w.writerow(["发射台", "slug", "当日手续费", "7日合计", "30日合计", "7日DEX成交"])
        for z in LPS:
            w.writerow([z["名称"], z["slug"], z["当日"], round(z["7日"], 2), round(z["30日"], 2), round(z["7日DEX"], 2)])

# ======================================================================
# 推送摘要
# ======================================================================
def dd(v):
    return pct(v, 1, True)


def pl(s, label):
    x = R.get(s)
    if not x:
        return f"{label} 未接入"
    if x["延迟"]:
        return f"{label} 延迟"
    return f"{label} {x['当日手续费']:,.0f}（{dd(x['日环比'])}）"


L = [f"发射台日更 · {LAST}（UTC 完整日）", ""]
L.append(" ｜ ".join([pl("pump.fun", "pump.fun"),
                      "Pons 合计 延迟" if pons_cur is None else f"Pons 合计 {pons_cur:,.0f}（{dd(pch(pons_cur, pons_prev))}）",
                      pl("stonkfun", "StonkFun") if HAS_STONK else "StonkFun 未接入",
                      pl("flap-sh", "Flap")]))
L.append(f"pump÷Pons {'—' if ratio is None else f'{ratio:.2f}'} ｜ V2 占 Pons {pct(v2share)} ｜ "
         f"赛道 Top60 当日 {n0(TOT.get(LAST))}{'（分母不完整）' if DENOM_BAD else ''}")
if VSYMS:
    L.append("回购市盈率 " + " / ".join(f"{s} {xx(vget(s, '回购市盈率'), 2)}" for s in VSYMS)
             + " ｜ 回购收益率 " + " / ".join(f"{s} {pct(vget(s, '回购收益率'))}" for s in VSYMS) + " ｜ Flap 不适用")
L.append(f"PONS 当日销毁 {n0(burn_last)} 枚 约 {usd(burn_usd(LAST))}；销毁地址累计 {n0(BURNED)}（占总量 {pct(div(BURNED, SUPPLY))}）")
if ARC_OK:
    L.append(f"Arc（{ARC_LAST}）全链手续费 {usd(A['全链手续费'].get(ARC_LAST))} ｜ DEX 成交 {usd(A['全链DEX成交'].get(ARC_LAST))}"
             f" ｜ TVL {usd(A['TVL'].get(ARC_LAST))} ｜ 发射台合计 {usd(A['发射台手续费'].get(ARC_LAST))}"
             f"（第一 {TOP['名称'] if TOP else '—'}；Tolly {usd(TOLLY['当日']) if TOLLY else '—'}）｜ 升级条件 {arc_state}")
L += ["", "近 7 天", "| 日期 | pump.fun | Pons 合计 | StonkFun | Flap | 赛道总量 | PONS 销毁 |", "|---|---|---|---|---|---|---|"]
for x in W7:
    L.append(f"| {x} | {n0(fee('pump.fun', x), '延迟')} | {n0(pons(x), '延迟')} | "
             f"{n0(fee('stonkfun', x), '延迟') if HAS_STONK else '—'} | {n0(fee('flap-sh', x), '延迟')} | "
             f"{n0(TOT.get(x))} | {n0(burn_daily.get(x))} |")
L += ["", "异常"]
if AN:
    L += [f"- {a}" for a in AN[:3]]
    if len(AN) > 3:
        L.append(f"- 另有 {len(AN) - 3} 条，见看板")
else:
    L.append("无异常")
with open(os.path.join(OUT, "摘要.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(L) + "\n")

# ======================================================================
# Notion 追加行（格式对齐页面现有表格；金额里的 $ 在 Notion markdown 里要写成 \$）
# ======================================================================
def tr(cells):
    return "<tr>\n" + "\n".join(f"<td>{c}</td>" for c in cells) + "\n</tr>"


def m(v):
    return "—" if v is None else "\\$" + f"{v:,.0f}"


def t1(d, label=None):
    pf, v1, v2, pn, fl, tt = fee("pump.fun", d), fee("pons-v1", d), fee("pons-v2", d), pons(d), fee("flap-sh", d), TOT.get(d)
    bad = DENOM_BAD and d == LAST
    return tr([label or d, n0(pf, "延迟"), n0(v1, "延迟"), n0(v2, "延迟"), n0(pn, "延迟"), n0(fl, "延迟"),
               n0(tt) + ("（分母不完整）" if bad else ""),
               "—" if div(pf, pn) is None else f"{div(pf, pn):.2f}", pct(div(v2, pn)), pct(div(pf, tt)), pct(div(pn, tt))])


def t2(d):
    c = CUM.get(d)
    return tr([d, n0(burn_daily.get(d)), n0(c), pct(div(c, SUPPLY)), n0(SUPPLY - c if c else None)])


def t3(d):
    out = []
    for s in VSYMS:
        r = vr(s, d)
        if not r:
            continue
        out.append(tr([d, s, VMETA[s]["平台"], m(r["市值"]), m(r["年化协议收入"]), xx(r["收入市盈率"], 2),
                       m(r["年化回购额"]), xx(r["回购市盈率"], 2), pct(r["回购收益率"], 2)
                       + ("（窗口不足30天）" if r["窗口不足30天"] else "")]))
    out.append(tr([d, "—", "Flap sh", "—", "—", "不适用", "—", "不适用", "—"]))
    return "\n".join(out)


def t4(d):
    f_ = fee("stonkfun", d)
    r = vr("STONK", d) or {}
    return tr([d, n0(f_, "延迟"), dd(pch(f_, fee("stonkfun", shift(d, -1)))),
               "—" if f_ is None else n0(avg([fee("stonkfun", shift(d, -i)) for i in range(7)])),   # 当日延迟不出 7 日均（否则是 6 日均）
               n0(r.get("当日回购额")), pct(r.get("当日回购占收入")), pct(div(f_, TOT.get(d))), xx(r.get("回购市盈率"), 2)])


def t5(d):
    if not ARC_OK or d not in A["全链手续费"]:
        return None
    ev = arc_eval(d)
    best = max(A["发射台"].items(), key=lambda kv: kv[1]["fees"].get(d, 0), default=(None, None))
    tl = TOLLY and A["发射台"].get(TOLLY["名称"], {}).get("fees", {}).get(d)
    st = "样本不足" if not ev else ("已触发 " + "、".join(ev["trig"]) if ev["trig"] else "未触发")
    return tr([d, n0(A["全链手续费"].get(d)), n0(A["全链DEX成交"].get(d)), n0(A["TVL"].get(d)),
               n0(A["发射台手续费"].get(d)),
               f"{best[0]} {n0(best[1]['fees'].get(d))}" if best[0] else "—", n0(tl),
               pct(div(A["全链DEX成交"].get(d), RH.get("全链DEX成交", {}).get(d))), st])


HEADERS = {
    "表四": ["日期", "StonkFun 手续费（=协议收入）", "日环比", "7日均", "当日回购额", "回购占收入", "赛道份额", "STONK 回购市盈率"],
    "表五": ["日期", "Arc 全链手续费", "Arc DEX 成交", "Arc TVL", "Arc 发射台手续费合计", "发射台第一名", "Tolly 手续费",
             "Arc÷Robinhood DEX 成交", "升级条件"],
}


def pending(table, last_day):
    since = PUB.get(table)
    start = shift(since, 1) if since else last_day
    out, d = [], start
    while d <= last_day:
        out.append(d)
        d = shift(d, 1)
    return out


payload = {"LAST": LAST, "ARC_LAST": ARC_LAST, "表": {}, "新表模板": {}, "已发布基准": {k: PUB.get(k) for k in
                                                                            ["表一", "表二", "表三", "表四", "表五"]}}
spec = [("表一", t1, LAST), ("表二", t2, LAST), ("表三", t3, LAST)]
if HAS_STONK:
    spec.append(("表四", t4, LAST))
if ARC_OK:
    spec.append(("表五", t5, ARC_LAST))
for name, fn, last_day in spec:
    ds = pending(name, last_day)
    rows_md = [x for x in (fn(d) for d in ds) if x]
    if name == "表一":
        rows_md += [t1(d, f"{d}（修正）") for d in REVISED_DAYS if d not in ds]
    payload["表"][name] = {"日期": ds, "行": "\n".join(rows_md)}
for name, hdr in HEADERS.items():
    payload["新表模板"][name] = ('<table header-row="true">\n' + tr(hdr) + "\n" +
                                  (payload["表"].get(name, {}).get("行") or "") + "\n</table>")
payload["修订"] = [{"日期": d, "字段": k, "旧": o, "新": n} for d, k, o, n in REVISED]
payload["表一数值"] = {d: {"pump.fun": fee("pump.fun", d), "pons-v1": fee("pons-v1", d), "pons-v2": fee("pons-v2", d),
                          "flap-sh": fee("flap-sh", d), "top60": TOT.get(d)}
                      for d in sorted(set(payload["表"]["表一"]["日期"]) | set(REVISED_DAYS))}
with open(os.path.join(OUT, "notion_payload.json"), "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=1)

print("\n".join(L))
print("\n->", os.path.join(OUT, "发射台日更看板.html"), f"({len(full.encode())/1024:.0f} KB)")
print("->", os.path.join(OUT, "看板页.html"))
print("->", csv_path)
print("->", os.path.join(OUT, "notion_payload.json"), {k: v["日期"] for k, v in payload["表"].items()})

# ======================================================================
# 网站素材：出网站.py 读它，把同一份看板套进网站外壳（Claude 定时任务不用这个文件）
# ======================================================================
SERIES_DAYS = 180        # 网站仪表盘用的历史长度（详情页图表、迷你走势线）
SITE_SYM = {"pump.fun": "PUMP", "stonkfun": "STONK"}      # 平台 slug → 估值符号（Pons 合并算，见下）


def series4(getter, ds):
    """{日期: 数值} 稀疏序列，跳过 None（延迟/上线前），前端按存在的点连线，不补零。"""
    out = {}
    for d in ds:
        v = getter(d)
        if v is not None:
            out[d] = round(v, 2) if isinstance(v, float) else v
    return out


SDAYS = days[-SERIES_DAYS:]
site_platforms = []
for x in rows:
    s = x["slug"]
    sym = SITE_SYM.get(s) or ("PONS" if s in ("pons-v1", "pons-v2") else None)
    site_platforms.append({
        "slug": s, "名称": x["名称"], "链": x["链"], "延迟": x["延迟"],
        "当日手续费": x["当日手续费"], "日环比": x["日环比"], "7日均": x["7日均"], "7日均环比": x["7日均环比"],
        "当日收入": x["当日收入"], "分账比率": x["分账比率"], "占赛道份额": x["占赛道份额"],
        "距单日峰值": x["距单日峰值"], "单日峰值": x["单日峰值"], "峰值日": x["峰值日"], "累计": x["累计"],
        "手续费序列": series4(lambda d, s=s: fee(s, d), SDAYS),
        "收入序列": series4(lambda d, s=s: rv(s, d), SDAYS),
        "估值符号": sym,
    })
site_arc_lp = []
if ARC_OK:
    for z in LPS:
        e = A["发射台"][z["名称"]]
        site_arc_lp.append({
            "slug": z["slug"] or z["名称"], "名称": z["名称"], "链": "Arc",
            "当日手续费": z["当日"], "7日": z["7日"], "30日": z["30日"], "7日DEX": z["7日DEX"],
            "手续费序列": series4(lambda d, e=e: e["fees"].get(d), [d for d in adays if d >= ARC_MAINNET]),
        })
site_val = {}
for sym in VSYMS:
    r = vr(sym) or {}
    site_val[sym] = {**{k: v for k, v in r.items() if k != "日期"},
                      "平台": VMETA[sym].get("平台"),
                      "序列": {d: {kk: vv for kk, vv in (VROWS[sym].get(d) or {}).items() if kk in
                                  ("市值", "回购市盈率", "收入市盈率", "回购收益率")} for d in VROWS.get(sym, {})
                              if d >= shift(LAST, -SERIES_DAYS)}}
site = {
    "日期": LAST, "生成时间UTC": GEN, "距今天数": AGE, "整体延迟": GLOBAL_DELAY,
    "延迟平台": [NAME[s] for s in DELAYED],
    "css": CSS, "fonts": FONTS, "js": JS, "chart_json": CH_JSON,
    "正文": inner, "指标卡": hero,
    "一句话": L[2],
    "异常": [a for a in AN if a not in AN_NOTION_ONLY],
    "平台": site_platforms,
    "赛道Top60": {"当日": TOT.get(LAST), "序列": series4(lambda d: TOT.get(d), SDAYS),
              "协议数": D.get("Launchpad协议总数")},
    "Pons合计": pons_cur, "Pons日环比": pch(pons_cur, pons_prev), "pump除以Pons": ratio,
    "PONS当日销毁": burn_last, "PONS当日销毁USD": burn_usd(LAST), "PONS销毁地址累计": BURNED,
    "PONS销毁序列": series4(lambda d: burn_daily.get(d), SDAYS),
    "回购市盈率": {s: vget(s, "回购市盈率") for s in VSYMS},
    "估值": site_val,
    "Arc": {"日期": ARC_LAST, "发射台手续费": A["发射台手续费"].get(ARC_LAST) if ARC_OK else None,
            "全链手续费": A.get("全链手续费", {}).get(ARC_LAST) if ARC_OK else None,
            "升级条件": arc_state, "发射台": site_arc_lp},
    "csv": os.path.basename(csv_path),
}
with open(os.path.join(OUT, "网站素材.json"), "w", encoding="utf-8") as fh:
    json.dump(site, fh, ensure_ascii=False)
print("->", os.path.join(OUT, "网站素材.json"))
