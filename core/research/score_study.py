#!/usr/bin/env python3
"""评分研究 M1–M2：数据底座 + 单个读数逐项检验（立项书 core/research/评分研究立项.md 第二节第 1、5 条）。只用标准库。
研究用，不接网站、不进日更。结果 → core/research/score_study_results.json + 评分研究_M1M2结果.md

==== 判定标准（2026-11-14 跑之前写死，跑完不改） ====
样本（point-in-time）：每个月 1 日 t，入选条件只用 t 之前的数据：
  ① 币安现货 USDT 交易对（含已下架，价格取 API，取不到用 data.binance.vision 月度归档），t−1 有收盘；
  ② DefiLlama 母协议 t 之前 30 天协议收入合计 ≥ 30 万美元；
  ③ 身份核对：DefiLlama 母协议 gecko_id 在 coins.llama.fi 的历史价格与币安收盘中位偏差 ≤ 5%（同名不同币剔除）。
结果：t−1 收盘到 t+h−1 收盘的收益（h = 30 / 60 / 90 天）。IC 只看同一时点的排序，减不减篮子都一样。
指标：每月 Spearman IC；样本内（2023-03 ～ 2025-06）定方向；样本外（2025-07 起）检验。
  60 / 90 天用不重叠的月份（每 2 / 3 个月取一个）算 t 值。
  偏 IC：每月把读数的排名对“规模（30 日成交额排名）+ 近 30 天涨跌排名”做回归取残差，再算 IC。
方向：有先验的读数按先验方向；没有先验的（成交额 / 技术面）用样本内 IC 的符号当方向。
通过 = 样本外 30 天 IC（按方向）> 0 且 t ≥ 2，60 天同号，样本外五档平均超额的单调性（档位与均值的秩相关）≥ 0.7。
证伪 = 样本外 30 天 IC（按方向）< 0 且 t ≤ −1。其余 = 未通过。
只有近一年数据的读数（估值、换手：CoinGecko 免费市值只有 365 天）全部落在样本外，按先验方向直接检验，单列“仅近一年”。
"""
import csv, io, json, math, os, statistics as st, sys, time, urllib.parse, zipfile
import datetime as dt
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.dirname(HERE)
sys.path.insert(0, CORE)
import core_daily as C   # noqa: E402

CACHE = os.path.join(CORE, "cache", "study")
os.makedirs(CACHE, exist_ok=True)
START, TRAIN_END = "2023-03-01", "2025-06-30"
MIN_REV30 = 300_000
HS = (30, 60, 90)
TODAY = C.TODAY.isoformat()
SKIP_CAT = {"CEX", "Chain", "Bridge", "Stablecoin Issuer"}
STABLE = C.EXCLUDE | {"USDT", "BTC", "ETH", "WBTC", "STETH", "WETH"}


def cached(name, fn, ttl_h=72):
    p = os.path.join(CACHE, name.replace("/", "_") + ".json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < ttl_h * 3600:
        return json.load(open(p))
    v = fn()
    json.dump(v, open(p, "w"))
    return v


def day(d, k):
    return (dt.date.fromisoformat(d) + dt.timedelta(days=k)).isoformat()


# ---------------------------------------------------------------- M1 数据底座
def binance_symbols_ever():
    """币安现货历史上所有 USDT 交易对（S3 月度 K 线目录，含已下架）。"""
    out, marker = [], ""
    while True:
        b = C.get(f"{C.S3}?prefix=data/spot/monthly/klines/&delimiter=/&marker={urllib.parse.quote(marker)}", raw=True)
        root = ET.fromstring(b)
        ns = {"s": root.tag.split("}")[0][1:]}
        for p in root.findall("s:CommonPrefixes/s:Prefix", ns):
            s = p.text.rstrip("/").split("/")[-1]
            if s.endswith("USDT"):
                out.append(s[:-4])
        nxt = root.find("s:NextMarker", ns)
        if nxt is None or not nxt.text:
            break
        marker = nxt.text
    return sorted(set(out))


def candidates(ever):
    protos = C.get(f"{C.LLAMA}/protocols")
    ev = set(ever)
    by = {}
    for p in protos:
        sy = (p.get("symbol") or "").upper()
        if not sy or sy == "-" or sy in STABLE or sy not in ev or p.get("category") in SKIP_CAT:
            continue
        slug = (p.get("parentProtocol") or "").replace("parent#", "") or p["slug"]
        by.setdefault(sy, set()).add(slug)
    return {k: sorted(v) for k, v in by.items()}


def llama_fees(slug):
    out, meta = {}, {}
    for k, dtp in (("fees", "dailyFees"), ("revenue", "dailyRevenue"), ("holders", "dailyHoldersRevenue")):
        try:
            d = C.get(f"{C.LLAMA}/summary/fees/{slug}?dataType={dtp}&excludeTotalDataChartBreakdown=true") or {}
        except Exception:  # noqa
            d = {}
        meta = meta or {"gecko": d.get("gecko_id"), "symbol": (d.get("symbol") or "").upper(), "name": d.get("name"), "category": d.get("category")}
        out[k] = {dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"): v for t, v in (d.get("totalDataChart") or []) if v is not None}
    try:
        d = C.get(f"{C.LLAMA}/summary/dexs/{slug}?dataType=dailyVolume&excludeTotalDataChartBreakdown=true") or {}
        out["dex"] = {dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"): v for t, v in (d.get("totalDataChart") or []) if v is not None}
    except Exception:  # noqa
        out["dex"] = {}
    out["meta"] = meta
    return out


def binance_px(sym):
    """{date: [close, quote_volume]}，API 取不到（已下架）就读月度归档。"""
    rows, cur = {}, int(dt.datetime(2022, 9, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    try:
        while True:
            d = C.spot_get(f"/api/v3/klines?symbol={urllib.parse.quote(sym)}USDT&interval=1d&startTime={cur}&limit=1000")
            if not d:
                break
            for k in d:
                rows[C.D(k[0])] = [float(k[4]), float(k[7])]
            cur = d[-1][0] + 86400000
            if len(d) < 1000:
                break
    except Exception:  # noqa
        pass
    if not rows:   # 已下架：月度归档
        m = dt.date(2022, 9, 1)
        while m.isoformat() < TODAY:
            ym = m.strftime("%Y-%m")
            q = urllib.parse.quote(sym + "USDT")
            try:
                b = C.get(f"{C.ARCH}/data/spot/monthly/klines/{q}/1d/{q}-1d-{ym}.zip", raw=True, tries=2)
            except Exception:  # noqa
                b = None
            if b:
                z = zipfile.ZipFile(io.BytesIO(b))
                for line in csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8")):
                    if line and line[0].isdigit():
                        ts = int(line[0])
                        ts = ts // 1000 if ts > 10 ** 14 else ts   # 2025 年起归档用微秒
                        rows[C.D(ts)] = [float(line[4]), float(line[7])]
            m = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return {k: v for k, v in rows.items() if k < TODAY}


def llama_price(gid):
    """coins.llama.fi 一次最多 500 个点：2023-01 起按 500 天分段取。"""
    out, s = {}, int(dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    while s < time.time():
        d = C.get(f"https://coins.llama.fi/chart/coingecko:{gid}?start={s}&span=500&period=1d") or {}
        for p in ((d.get("coins") or {}).get(f"coingecko:{gid}") or {}).get("prices") or []:
            out[dt.datetime.fromtimestamp(p["timestamp"], dt.timezone.utc).strftime("%Y-%m-%d")] = p["price"]
        s += 500 * 86400
    return out


def mcaps365(gid):
    for i in range(4):
        try:
            d = C.get(f"{C.CG}/coins/{gid}/market_chart?vs_currency=usd&days=365&interval=daily", tries=1)
            return {dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).strftime("%Y-%m-%d"): v for t, v in (d or {}).get("market_caps") or [] if v}
        except Exception:  # noqa
            time.sleep(20 * (i + 1))
    return {}


def tvl(slug):
    try:
        d = C.get(f"{C.LLAMA}/protocol/{slug}", timeout=120) or {}
    except Exception:  # noqa
        return {}
    return {dt.datetime.fromtimestamp(r["date"], dt.timezone.utc).strftime("%Y-%m-%d"): r["totalLiquidityUSD"] for r in d.get("tvl") or []}


def build():
    ever = cached("binance_ever", binance_symbols_ever, 240)
    cand = cached("candidates", lambda: candidates(ever), 240)
    pairs = sorted({(sy, sl) for sy, sls in cand.items() for sl in sls})
    C.log(f"币安历史 USDT 现货 {len(ever)} 个；DefiLlama 同符号协议 {len(pairs)} 组（{len(cand)} 个符号）")

    def job(p):
        return p, cached(f"fees_{p[1]}", lambda: llama_fees(p[1]), 240)
    fees = {}
    with ThreadPoolExecutor(8) as ex:
        for (sy, sl), f in ex.map(job, pairs):
            r = f.get("revenue") or {}
            ds = sorted(d for d in r if d >= day(START, -40))
            best = max((sum(r.get(day(d, -i), 0) for i in range(30)) for d in ds[::15]), default=0)
            if best >= MIN_REV30:
                fees[(sy, sl)] = f
    C.log(f"有过 30 天收入 ≥ 30 万美元的：{len(fees)} 组")
    # 身份核对 + 价格
    uni, drop = {}, {}

    def pjob(sy):
        return sy, cached(f"px_{sy}", lambda: binance_px(sy), 72)
    pxs = dict(ThreadPoolExecutor(8).map(pjob, sorted({sy for sy, _ in fees})))
    for (sy, sl), f in sorted(fees.items(), key=lambda kv: -sum((kv[1].get("revenue") or {}).values())):
        if sy in uni:
            continue
        gid = (f.get("meta") or {}).get("gecko")
        px = pxs.get(sy) or {}
        if not px:
            drop[f"{sy}/{sl}"] = "币安没有价格"; continue
        if not gid:
            drop[f"{sy}/{sl}"] = "母协议没有 gecko_id，无法核对身份"; continue
        lp = cached(f"lp_{gid}", lambda: llama_price(gid), 240)
        both = [d for d in sorted(px) if d in lp and lp[d]][::10]
        if len(both) < 5:
            drop[f"{sy}/{sl}"] = f"历史价格重叠不足（{gid}）"; continue
        dev = st.median(abs(px[d][0] / lp[d] - 1) for d in both)
        if dev > 0.05:
            drop[f"{sy}/{sl}"] = f"币安收盘与 {gid} 历史价格中位偏差 {dev*100:.0f}%（同名不同币）"; continue
        uni[sy] = {"slug": sl, "gecko": gid, "name": f["meta"].get("name"), "cat": f["meta"].get("category"), "f": f, "px": px,
                   "delisted": max(px) < day(TODAY, -5)}
    C.log(f"身份核对通过 {len(uni)} 个（其中已下架 {sum(1 for u in uni.values() if u['delisted'])} 个）；剔除 {len(drop)} 组")
    for sy, u in uni.items():
        if not u["f"].get("dex"):
            u["tvl"] = cached(f"tvl_{u['slug']}", lambda: tvl(u["slug"]), 240)
        else:
            u["tvl"] = {}
        u["mc"] = cached(f"mc_{u['gecko']}", lambda: (time.sleep(3), mcaps365(u["gecko"]))[1], 72)
    return uni, drop


# ---------------------------------------------------------------- M2 读数
def win(ser, end, n):
    """end 之前（不含）n 天；DefiLlama 缺的日子：协议开始报数之前 = 无数据（None），之后缺一天按 0。"""
    if not ser:
        return None
    first = min(ser)
    if first > day(end, -n):
        return None
    return [ser.get(day(end, -i), 0) for i in range(n, 0, -1)]


def g(a, b):
    return (a / b - 1) * 100 if a is not None and b and b > 0 else None


def factors(u, t):
    f, px = u["f"], u["px"]
    p0 = px.get(day(t, -1))
    if not p0:
        return None
    r180 = win(f["revenue"], t, 180) or win(f["revenue"], t, 90) or win(f["revenue"], t, 60)
    if not r180 or sum(r180[-30:]) < MIN_REV30:
        return None
    r = r180
    o = {"_px": p0[0]}
    s30, p30 = sum(r[-30:]), (sum(r[-60:-30]) if len(r) >= 60 else None)
    o["rev_7v30"] = g(sum(r[-7:]) / 7, s30 / 30)
    o["rev_30v30"] = g(s30, p30)
    o["rev_90v90"] = g(sum(r[-90:]), sum(r[-180:-90])) if len(r) >= 180 else None
    h = win(f["holders"], t, 30)
    o["holder_share"] = (sum(h) / s30 * 100) if h is not None else None
    fe = win(f["fees"], t, 30)
    o["take_rate"] = (s30 / sum(fe) * 100) if fe and sum(fe) > 0 else None
    c = [px.get(day(t, -i), [None])[0] for i in range(250, 0, -1)]
    cc = [x for x in c if x]
    p30d = px.get(day(t, -31))
    o["ret30"] = g(p0[0], p30d[0]) if p30d else None
    o["rev_lead"] = o["rev_30v30"] - o["ret30"] if o["rev_30v30"] is not None and o["ret30"] is not None else None
    act = u["f"].get("dex") or u.get("tvl") or {}
    a60 = win(act, t, 60)
    o["act_30v30"] = g(sum(a60[-30:]), sum(a60[:30])) if a60 and u["f"].get("dex") else (g(st.mean(a60[-7:]), st.mean(a60[:7])) if a60 else None)
    v = [px.get(day(t, -i), [None, None])[1] for i in range(30, 0, -1)]
    v = [x for x in v if x is not None]
    o["vol_7v30"] = g(st.mean(v[-7:]), st.mean(v)) if len(v) >= 25 else None
    o["_vol30"] = st.mean(v) if len(v) >= 25 else None
    if len(cc) >= 200:
        o["dist_ma200"] = g(p0[0], st.mean(cc[-200:]))
    if len(cc) >= 120:
        o["dd120"] = g(p0[0], max(cc[-120:]))
    w = cc[-30:]
    o["pos30"] = (p0[0] - min(w)) / (max(w) - min(w)) * 100 if len(w) >= 25 and max(w) > min(w) else None
    m = u["mc"].get(day(t, -1)) if u.get("mc") else None
    if m:
        hr = sum(h) * 365 / 30 if h else 0
        o["val_p_hr"] = -math.log(m / hr) if hr > 0 else None          # 便宜 = 高分
        o["val_p_rev"] = -math.log(m / (s30 * 365 / 30))
        o["turnover"] = (st.mean(v) * 30 / m * 100) if v else None
    o["flag_r3"] = (1.0 if o["ret30"] - o["rev_30v30"] > 30 else 0.0) if o["ret30"] is not None and o["rev_30v30"] is not None else None
    return o


# 先验方向：+1 越高越好，−1 越低越好，0 = 没有先验（用样本内符号）
PRIOR = {"rev_7v30": 1, "rev_30v30": 1, "rev_90v90": 1, "holder_share": 1, "take_rate": 1, "rev_lead": 1, "act_30v30": 1,
         "val_p_hr": 1, "val_p_rev": 1, "flag_r3": -1,
         "vol_7v30": 0, "turnover": 0, "vol_rank_chg": 0, "dist_ma200": 0, "dd120": 0, "pos30": 0}
NAME = {"rev_7v30": "收入 7 日均 vs 30 日均", "rev_30v30": "收入近 30 天 vs 前 30 天", "rev_90v90": "收入近 90 天 vs 前 90 天",
        "holder_share": "持有人收入占协议收入（价值捕获）", "take_rate": "抽成率（协议收入 ÷ 手续费）", "rev_lead": "收入领先价格（收入 30 天变化 − 价格 30 天涨跌）",
        "act_30v30": "业务量增速（DEX 成交额 30v30 / TVL 7 日均对 60 天前）", "val_p_hr": "估值：市值 ÷ 年化持有人收入（越便宜越高）",
        "val_p_rev": "估值：市值 ÷ 年化协议收入（越便宜越高）", "flag_r3": "R3 价格跑在收入前面 > 30pp（是 = 1）",
        "vol_7v30": "代币成交额 7 日均 vs 30 日均", "turnover": "30 日换手（成交额 ÷ 市值）", "vol_rank_chg": "成交额排名 30 天变化（样本内）",
        "dist_ma200": "距 MA200", "dd120": "距 120 日高点", "pos30": "30 日区间位置"}
YEAR_ONLY = {"val_p_hr", "val_p_rev", "turnover"}
GROUP = {"rev_7v30": "基本面", "rev_30v30": "基本面", "rev_90v90": "基本面", "holder_share": "基本面", "take_rate": "基本面", "rev_lead": "基本面",
         "act_30v30": "基本面", "val_p_hr": "基本面·估值", "val_p_rev": "基本面·估值", "flag_r3": "建仓规则 R3",
         "vol_7v30": "资金面", "turnover": "资金面", "vol_rank_chg": "资金面", "dist_ma200": "技术面", "dd120": "技术面", "pos30": "技术面"}


def rank(x):
    idx = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[idx[j + 1]] == x[idx[i]]:
            j += 1
        for k in range(i, j + 1):
            r[idx[k]] = (i + j) / 2
        i = j + 1
    return r


def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else None


def resid(y, xs):
    """y 对若干列做最小二乘（含常数），返回残差。列数少，直接解正规方程。"""
    n, k = len(y), len(xs) + 1
    X = [[1.0] + [c[i] for c in xs] for i in range(n)]
    A = [[sum(X[r][i] * X[r][j] for r in range(n)) for j in range(k)] for i in range(k)]
    b = [sum(X[r][i] * y[r] for r in range(n)) for i in range(k)]
    for i in range(k):          # 高斯消元
        p = max(range(i, k), key=lambda r: abs(A[r][i]))
        A[i], A[p], b[i], b[p] = A[p], A[i], b[p], b[i]
        if abs(A[i][i]) < 1e-12:
            return y
        for r in range(k):
            if r != i:
                f = A[r][i] / A[i][i]
                A[r] = [A[r][j] - f * A[i][j] for j in range(k)]
                b[r] -= f * b[i]
    beta = [b[i] / A[i][i] for i in range(k)]
    return [y[r] - sum(beta[j] * X[r][j] for j in range(k)) for r in range(n)]


def tstat(xs):
    if len(xs) < 3:
        return None
    sd = st.stdev(xs)
    return st.mean(xs) / sd * math.sqrt(len(xs)) if sd else None


def main():
    uni, drop = build()
    last = max(max(u["px"]) for u in uni.values())
    dates, d = [], dt.date.fromisoformat(START)
    while d.isoformat() <= last:
        dates.append(d.isoformat())
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    # 每月读数 + 之后收益
    panel = {}
    for t in dates:
        rows = {}
        for sy, u in uni.items():
            o = factors(u, t)
            if not o:
                continue
            for h in HS:
                p1 = u["px"].get(day(t, h - 1))
                o[f"_fwd{h}"] = (p1[0] / o["_px"] - 1) * 100 if p1 else None
            rows[sy] = o
        # 成交额排名变化（样本内相对排名）
        vs = {s: o["_vol30"] for s, o in rows.items() if o.get("_vol30")}
        if len(vs) >= 10:
            rk = dict(zip(vs, rank(list(vs.values()))))
            prev = panel.get(dates[dates.index(t) - 1], {}) if dates.index(t) else {}
            for s, o in rows.items():
                if s in rk and s in prev and prev[s].get("_vrank") is not None:
                    o["vol_rank_chg"] = (rk[s] - prev[s]["_vrank"]) / len(vs) * 100
                o["_vrank"] = rk.get(s)
        panel[t] = rows
    res = {}
    for fk in PRIOR:
        out = {"name": NAME[fk], "group": GROUP[fk], "prior": PRIOR[fk], "year_only": fk in YEAR_ONLY}
        for h in HS:
            ics, pics, qs = [], [], []
            for t in dates:
                rows = [(o[fk], o[f"_fwd{h}"], o.get("_vol30"), o.get("ret30")) for o in panel[t].values()
                        if o.get(fk) is not None and o.get(f"_fwd{h}") is not None and o.get("_vol30") and o.get("ret30") is not None]
                if len(rows) < 12 or len({r[0] for r in rows}) < 3:
                    continue
                fx, fy = rank([r[0] for r in rows]), rank([r[1] for r in rows])
                ic = corr(fx, fy)
                rs = resid(fx, [rank([r[2] for r in rows]), rank([r[3] for r in rows])])
                pic = corr(rank(rs), fy)
                med = st.median(r[1] for r in rows)
                order = sorted(range(len(rows)), key=lambda i: rows[i][0])
                qm = []
                for q in range(5):
                    sl = order[q * len(rows) // 5:(q + 1) * len(rows) // 5]
                    qm.append(st.mean(rows[i][1] - med for i in sl) if sl else None)
                ics.append((t, ic, len(rows))); pics.append((t, pic)); qs.append((t, qm))
            step = {30: 1, 60: 2, 90: 3}[h]

            def summ(sel):
                xs = [x for x in sel if x[1] is not None]
                if not xs:
                    return None
                no = xs[::step]
                v = [x[1] for x in no]
                return {"months": len(xs), "ic": round(st.mean(x[1] for x in xs), 4), "t": None if tstat(v) is None else round(tstat(v), 2),
                        "hit": round(sum(1 for x in xs if x[1] > 0) / len(xs) * 100), "n": round(st.mean(x[2] for x in xs), 1) if len(xs[0]) > 2 else None}
            tr = summ([x for x in ics if x[0] <= TRAIN_END]); te = summ([x for x in ics if x[0] > TRAIN_END])
            ptr = summ([(a, b, 0) for a, b in pics if a <= TRAIN_END]); pte = summ([(a, b, 0) for a, b in pics if a > TRAIN_END])
            qte = [q for t, q in qs if t > TRAIN_END and None not in q]
            qmean = [round(st.mean(q[i] for q in qte), 2) for i in range(5)] if qte else None
            out[h] = {"train": tr, "test": te, "ptrain": ptr, "ptest": pte, "q_test": qmean,
                      "mono": round(corr(rank([0, 1, 2, 3, 4]), rank(qmean)), 2) if qmean and len(set(qmean)) > 1 else None}
        # 方向与判定
        dirn = PRIOR[fk] or ((1 if out[30]["train"]["ic"] > 0 else -1) if out[30].get("train") else 0)
        out["direction"] = dirn
        te30, te60 = (out[30] or {}).get("test"), (out[60] or {}).get("test")
        if not te30 or not dirn:
            v = "样本不足"
        else:
            ic, tt = te30["ic"] * dirn, (te30["t"] or 0) * dirn
            mono = (out[30]["mono"] or 0) * dirn
            if ic > 0 and tt >= 2 and te60 and te60["ic"] * dirn > 0 and mono >= 0.7:
                v = "通过"
            elif ic < 0 and tt <= -1:
                v = "证伪"
            else:
                v = "未通过"
        out["verdict"] = v
        res[fk] = out
        C.log(f"{fk:14s} {v:4s} 方向 {dirn:+d}  样本内 30d IC {((out[30] or {}).get('train') or {}).get('ic')}  样本外 {te30 and te30['ic']} t {te30 and te30['t']}  偏IC样本外 {((out[30] or {}).get('ptest') or {}).get('ic')}  五档 {out[30].get('q_test')}")
    # 分周期阶段（Q3）：按 t−1 的 L2 状态把月份分组，只看样本内外合并的 30 天 IC
    L2 = json.load(open(os.path.join(os.path.dirname(CORE), "data", "l2", "l2_series.json")))
    codes, s0 = L2["state_codes"], dt.date.fromisoformat(L2["start"])
    stt = L2["series"]["state"]
    state_at = lambda t: codes[stt[(dt.date.fromisoformat(day(t, -1)) - s0).days]] if 0 <= (dt.date.fromisoformat(day(t, -1)) - s0).days < len(stt) and stt[(dt.date.fromisoformat(day(t, -1)) - s0).days] is not None else None
    phase = {}
    for fk in PRIOR:
        byp = {}
        for t in dates:
            rows = [(o[fk], o["_fwd30"]) for o in panel[t].values() if o.get(fk) is not None and o.get("_fwd30") is not None]
            if len(rows) < 12 or len({r[0] for r in rows}) < 3:
                continue
            ic = corr(rank([r[0] for r in rows]), rank([r[1] for r in rows]))
            byp.setdefault(state_at(t), []).append(ic)
        phase[fk] = {k: {"months": len(v), "ic": round(st.mean(v), 3)} for k, v in byp.items() if k}
    meta = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "dates": [dates[0], dates[-1]], "train_end": TRAIN_END,
            "universe": len(uni), "delisted": sorted(s for s, u in uni.items() if u["delisted"]), "coins": sorted(uni),
            "per_month": {t: len(panel[t]) for t in dates}, "dropped": drop}
    json.dump(C.clean({"meta": meta, "factors": res, "phase": phase}), open(os.path.join(HERE, "score_study_results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    C.log("完成")


if __name__ == "__main__":
    main()
