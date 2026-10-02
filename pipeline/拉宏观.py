#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宏观四层仪表盘 · 拉数（全部免费、免 key 的公开接口，GitHub Actions 每天跑一次，不消耗 Claude 额度）

  第一层 宏观流动性  FRED 公开 CSV（2010 年起全历史）：NASDAQ100 · VIXCLS · T10YIE · BAA10Y · NFCI · BAMLH0A0HYM2 ·
                     DFII10 · DTWEXBGS · WALCL · WTREGEN · RRPONTSYD · T10Y2Y；FRED 单条失败时退到 GitHub 镜像（akpasz/btc-data）
                     或 Yahoo（纳指 ^NDX）
                     DefiLlama 稳定币：全部美元稳定币 + 逐币分组（支付机构 / 交易核心 / 生息合成）+ Tron 链总量
                     现货 BTC ETF 逐日净流入：Farside 口径（haturatu/crypto-etf-flow 镜像，每 30 分钟同步）
                     CME 近月年化升水：Yahoo 合约 + 同一时点现货（没有免费历史，从今天起逐日积累）
                     Deribit：前后两张交割合约插值成固定 90 天年化升水
  第二、三层         CoinMetrics Community：价格、MVRV、流通量、市值、矿工发行额、交易所流入/流出/余额（全历史）
  第四层 情绪衍生品  alternative.me · Hyperliquid · CoinGecko（市值占比、自建山寨季、类目快照、美股代币化占比）

每个数据源各自 try，一个挂了不影响其他；失败写进「源状态」，页面上会标出来，绝不拿旧值冒充新值。
写：data/宏观台账.json、data/板块台账.json
"""
import csv, io, json, math, re, sys, time, datetime as dt, urllib.request, urllib.error
from common import get, post_json, load, save, today_utc, shift, day, UA

LEDGER = "宏观台账.json"
ROT = "板块台账.json"
ROT_KEEP = 120
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = today_utc()
FRED_START = "2010-01-01"        # 乐观度 z 从 2011 年起算，13 周变化要往前多留一个季度
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
MIRROR = "https://raw.githubusercontent.com/akpasz/btc-data/main/data/"


def text(url, timeout=60, tries=4, ua=None):
    h = {"User-Agent": ua or UA["User-Agent"], "Accept": "*/*"}
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 403, 404):
                raise
            time.sleep(3 * (i + 1))
        except Exception as e:  # noqa
            last = e
            time.sleep(2 * (i + 1))
    raise last


def sig(v, n=7):
    """台账里的数保留 7 位有效数字（文件小一半，分析精度够用）。"""
    if v is None or v == 0 or not isinstance(v, float) or math.isnan(v) or math.isinf(v):
        return v
    return round(v, n - 1 - int(math.floor(math.log10(abs(v)))))


def sma(vals, n):
    """vals: [(d, v)] 升序 → {d: n 日简单均线}，不足 n 天不出值。"""
    out, s, q = {}, 0.0, []
    for d, v in vals:
        q.append(v); s += v
        if len(q) > n:
            s -= q.pop(0)
        if len(q) == n:
            out[d] = s / n
    return out


# ---------------------------------------------------------------- 第一层：稳定币（总量 + 分组）
PAY = ["PYUSD", "RLUSD", "USDG", "USDGO", "U", "USDP", "GUSD"]           # 支付 / 合规机构
CORE = ["USDT", "USDC", "FDUSD", "USD1", "TUSD", "USDD"]                 # 交易核心
YIELD = ["USDE", "USDF", "BFUSD", "USDS", "DAI"]                          # 生息 / 合成
# 同名符号有多个币时按名称认人（2026-10-02 首跑发现 GUSD 会匹配到 Gate USD，研究里指的是 Gemini Dollar）
PREFER = {"GUSD": "gemini"}


def _llama_chart(path):
    rows = get(f"https://stablecoins.llama.fi/stablecoincharts/{path}", timeout=90)
    out = {}
    for r in rows:
        tot = r.get("totalCirculatingUSD") or {}
        v = sum(x for x in tot.values() if isinstance(x, (int, float)))
        if v:
            out[day(r["date"])] = v
    return {d: v for d, v in out.items() if d < TODAY}          # DefiLlama 当天的点是盘中值，只保留 UTC 完整日


def _group(ids):
    """逐币序列相加；单个币在自己的存续期内缺日用前值补，存续期外记 0。"""
    series = []
    for i in ids:
        series.append(_llama_chart(f"all?stablecoin={i}"))
        time.sleep(0.3)
    days = sorted(set().union(*[s.keys() for s in series])) if series else []
    out = {}
    last = [None] * len(series)
    for d in days:
        tot = 0.0
        for k, s in enumerate(series):
            if d in s:
                last[k] = s[d]
            if last[k] is not None and s and d <= max(s):
                tot += last[k]
        out[d] = tot
    return out


def fetch_stables():
    total = _llama_chart("all")
    lst = get("https://stablecoins.llama.fi/stablecoins?includePrices=false", timeout=90)["peggedAssets"]
    by_sym = {}
    for a in lst:
        if a.get("pegType") != "peggedUSD":
            continue
        circ = ((a.get("circulating") or {}).get("peggedUSD")) or 0
        s = (a.get("symbol") or "").upper()
        if s in PREFER and PREFER[s] not in (a.get("name") or "").lower():
            continue
        if s not in by_sym or circ > by_sym[s][1]:          # 同名币取流通量最大的那个，防仿冒币
            by_sym[s] = (a["id"], circ, a.get("name"))
    note = {}
    out = {"stable_total": total}
    for key, syms in (("stable_pay", PAY), ("stable_core", CORE), ("stable_yield", YIELD)):
        hit = [(s, by_sym[s]) for s in syms if s in by_sym]
        note[key] = [f"{s}（{x[2]}，id {x[0]}）" for s, x in hit]
        out[key] = _group([x[0] for _, x in hit])
    out["stable_tron"] = _llama_chart("Tron")
    return out, {"分组": note, "缺失": [s for s in PAY + CORE + YIELD if s not in by_sym]}


# ---------------------------------------------------------------- 第一层：FRED（公开 CSV，不需要 key）+ 兜底
FRED = {  # 台账 key: (FRED 代码, 换算成美元/原单位的乘数, 镜像文件, 镜像序列名)
    "fred_ndx": ("NASDAQ100", 1, None, None),
    "fred_vix": ("VIXCLS", 1, "macro.json", "vix_daily"),
    "fred_t10yie": ("T10YIE", 1, "macro.json", "breakeven_10y_daily"),
    "fred_baa10y": ("BAA10Y", 1, None, None),
    "fred_nfci": ("NFCI", 1, None, None),
    "fred_hy": ("BAMLH0A0HYM2", 1, "macro.json", "hy_spread_daily"),
    "fred_dfii10": ("DFII10", 1, "fred.json", "real_yield_10y"),
    "fred_broad_usd": ("DTWEXBGS", 1, "fred.json", "dollar_index_broad"),
    "fred_walcl": ("WALCL", 1e6, "fred.json", "walcl"),
    "fred_tga": ("WTREGEN", 1e6, "fred.json", "tga"),
    "fred_rrp": ("RRPONTSYD", 1e9, "fred.json", "rrp_on"),
    "fred_t10y2y": ("T10Y2Y", 1, None, None),
}
_MIRROR_CACHE = {}


def fred_csv(sid, mult):
    raw = text(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={FRED_START}", timeout=60)
    s = {}
    for row in list(csv.reader(io.StringIO(raw)))[1:]:        # 表头 observation_date / DATE 都跳过
        if len(row) < 2 or not re.match(r"^\d{4}-\d{2}-\d{2}$", row[0]) or row[1] in ("", "."):
            continue
        s[row[0]] = float(row[1]) * mult
    if not s:
        raise RuntimeError(f"FRED {sid} 返回空")
    return s


def mirror(fname, name, mult):
    if fname not in _MIRROR_CACHE:
        _MIRROR_CACHE[fname] = json.loads(text(MIRROR + fname, timeout=90))
    rows = (_MIRROR_CACHE[fname].get("series") or {}).get(name) or []
    s = {d: float(v) * mult for d, v in rows if d >= FRED_START and v is not None}
    if not s:
        raise RuntimeError(f"镜像 {fname}:{name} 为空")
    return s


def yahoo_daily(sym, rng="max"):
    last = None
    for host in ("query1", "query2"):
        try:
            j = json.loads(text(f"https://{host}.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval=1d",
                                timeout=60, tries=2, ua=BROWSER_UA))
            res = j["chart"]["result"][0]
            out = {}
            for t, c in zip(res.get("timestamp") or [], res["indicators"]["quote"][0].get("close") or []):
                if c is not None:
                    out[day(t)] = float(c)
            if out:
                return out
        except Exception as e:  # noqa
            last = e
    raise last or RuntimeError(f"Yahoo {sym} 为空")


def fetch_fred():
    out, used, failed = {}, {}, []
    for key, (sid, mult, mf, mn) in FRED.items():
        try:
            out[key] = fred_csv(sid, mult)
            used[key] = "FRED"
        except Exception as e:  # noqa
            err = f"{type(e).__name__}: {str(e)[:60]}"
            try:
                if mf:
                    out[key] = mirror(mf, mn, mult)
                    used[key] = f"镜像 akpasz/btc-data（FRED 失败：{err}）"
                elif key == "fred_ndx":
                    out[key] = {d: v for d, v in yahoo_daily("%5ENDX").items() if d >= FRED_START}
                    used[key] = f"Yahoo ^NDX（FRED 失败：{err}）"
                else:
                    raise
            except Exception as e2:  # noqa
                failed.append(f"{sid}: {err} / 兜底 {type(e2).__name__}")
        time.sleep(0.5)
    if not out:
        raise RuntimeError("FRED 全部失败：" + "；".join(failed))
    return out, {"来源": used, "失败": failed}


# ---------------------------------------------------------------- 第一层：现货 ETF 净流入（Farside 口径）
def fetch_etf():
    raw = text("https://raw.githubusercontent.com/haturatu/crypto-etf-flow/main/etf_btc.csv", timeout=60)
    rows = list(csv.reader(io.StringIO(raw)))
    head, out = rows[0], {}
    ti = head.index("Total")
    for r in rows[1:]:
        if len(r) <= ti:
            continue
        cells = [c.strip() for c in r[1:ti]]
        if not any(cells):                     # 全空 = 休市日 / 当天还没出数，不记 0
            continue
        try:
            d = dt.datetime.strptime(r[0].strip(), "%d %b %Y").date().isoformat()
            out[d] = float(r[ti].replace(",", "")) * 1e6
        except ValueError:
            continue
    if len(out) < 100:
        raise RuntimeError(f"ETF 只解析出 {len(out)} 行")
    return {"etf_flow": out}, {"口径": "美国现货 BTC ETF 合计日度净流入（Farside，单位换算成美元）", "最新": max(out)}


# ---------------------------------------------------------------- 第一层：CME 近月年化升水（Yahoo）
MCODE = "FGHJKMNQUVXZ"


def last_friday(y, m):
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    d = nxt - dt.timedelta(days=1)
    while d.weekday() != 4:
        d -= dt.timedelta(days=1)
    return d


def busdays(a, b):
    n, d = 0, a
    while d < b:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def yahoo_bars(sym, rng="5d", interval="1h"):
    last = None
    for host in ("query1", "query2"):
        try:
            j = json.loads(text(f"https://{host}.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={interval}",
                                timeout=40, tries=2, ua=BROWSER_UA))
            res = j["chart"]["result"][0]
            bars = [(t, float(c)) for t, c in zip(res.get("timestamp") or [], res["indicators"]["quote"][0].get("close") or [])
                    if c is not None]
            if bars:
                return bars
        except Exception as e:  # noqa
            last = e
    raise last or RuntimeError(f"Yahoo {sym} 无数据")


def fetch_cme():
    today = NOW.date()
    y, m = today.year, today.month
    exp = last_friday(y, m)
    if exp < today or busdays(today, exp) <= 5:          # 到期前约 5 个交易日换下一张
        y, m = (y + (m == 12), m % 12 + 1)
        exp = last_friday(y, m)
    sym = f"BTC{MCODE[m - 1]}{str(y)[2:]}.CME"
    try:
        fut = yahoo_bars(sym)
        used = sym
    except Exception:  # noqa —— 个别合约代码 Yahoo 不认，退到连续合约 BTC=F（Yahoo 自己在到期时换月）
        fut = yahoo_bars("BTC%3DF")
        used = "BTC=F"
        e2 = last_friday(today.year, today.month)
        exp = e2 if e2 >= today else last_friday(today.year + (today.month == 12), today.month % 12 + 1)
    spot = dict(yahoo_bars("BTC-USD"))
    pair = None
    for t, f in reversed(fut):                          # 找最近一根两边都有的小时线 = 同一时点
        s = spot.get(t) or next((spot[k] for k in spot if abs(k - t) <= 1800), None)
        if s:
            pair = (t, f, s)
            break
    if not pair:
        raise RuntimeError("期货与现货没有同一时点的报价")
    t, f, s = pair
    exp_ts = dt.datetime(exp.year, exp.month, exp.day, 15, 0, tzinfo=dt.timezone.utc).timestamp()   # 伦敦 16:00 终止交易
    days = (exp_ts - t) / 86400
    if days < 2:
        raise RuntimeError(f"{used} 剩余 {days:.1f} 天，换月中")
    ann = (f / s - 1) * 365 / days * 100
    return {"cme_basis": {TODAY: round(ann, 3)}}, {"合约": used, "到期": exp.isoformat(), "剩余天数": round(days, 1),
                                                    "期货": round(f, 1), "现货": round(s, 1),
                                                    "时点UTC": dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")}


# ---------------------------------------------------------------- 第一层：Deribit 固定 90 天年化升水
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def fetch_basis():
    rows = get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=future")["result"]
    pts = []
    for r in rows:
        m = re.match(r"^BTC-(\d{1,2})([A-Z]{3})(\d{2})$", r.get("instrument_name", ""))
        if not m or not r.get("mark_price") or not r.get("estimated_delivery_price"):
            continue
        exp = dt.datetime(2000 + int(m.group(3)), MON[m.group(2)], int(m.group(1)), 8, tzinfo=dt.timezone.utc)
        days = (exp - NOW).total_seconds() / 86400
        if days < 7:
            continue
        pts.append((days, (r["mark_price"] / r["estimated_delivery_price"] - 1) * 365 / days * 100, r["instrument_name"]))
    pts.sort()
    lo = [p for p in pts if p[0] <= 90]
    hi = [p for p in pts if p[0] > 90]
    if lo and hi:                                       # 前后两张按剩余天数线性插值成固定 90 天
        a, b = lo[-1], hi[0]
        w = (90 - a[0]) / (b[0] - a[0])
        ann, used = a[1] + (b[1] - a[1]) * w, f"{a[2]}（{a[0]:.0f} 天）↔ {b[2]}（{b[0]:.0f} 天）插值"
    else:
        cand = [p for p in pts if p[0] >= 30] or pts
        if not cand:
            raise RuntimeError("没有可用的交割合约")
        p = min(cand, key=lambda p: abs(p[0] - 90))
        ann, used = p[1], f"{p[2]}（{p[0]:.0f} 天，无法插值）"
    return {"deribit_basis": {TODAY: round(ann, 3)}}, {"合约": used}


# ---------------------------------------------------------------- 第二、三层：CoinMetrics Community
CM_A = ["PriceUSD", "CapMVRVCur", "SplyCur", "CapMrktCurUSD", "IssTotUSD"]
CM_B = ["FlowInExNtv", "FlowOutExNtv", "SplyExNtv"]


def cm_rows(metrics, start):
    url = ("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc"
           f"&metrics={','.join(metrics)}&frequency=1d&page_size=10000&start_time={start}")
    rows = []
    while url:
        j = get(url, timeout=120, tries=3)
        rows += j.get("data", [])
        url = j.get("next_page_url")
    return rows


def cm_fetch(metrics, start):
    """一次请求里只要有一个付费指标整批 403；403 时逐个指标重试，拿到多少算多少。"""
    out = {m: {} for m in metrics}
    try:
        batches = [(metrics, cm_rows(metrics, start))]
    except urllib.error.HTTPError as e:
        if e.code != 403:
            raise
        batches = []
        for m in metrics:
            try:
                batches.append(([m], cm_rows([m], start)))
            except urllib.error.HTTPError:
                print(f"  CoinMetrics {m} 不在免费档，跳过")
    for ms, rows in batches:
        for r in rows:
            d = r["time"][:10]
            for m in ms:
                v = r.get(m)
                if v not in (None, ""):
                    out[m][d] = float(v)
    return out


def fetch_cycle():
    c = cm_fetch(CM_A, "2010-07-18")
    p, mvrv, sply, mc, iss = (c[k] for k in CM_A)
    if not p or not mvrv:
        raise RuntimeError("CoinMetrics 价格/MVRV 为空")
    ds = sorted(p)
    out = {"btc_price": dict(p), "mvrv": dict(mvrv)}
    out["realized_price"] = {d: p[d] / mvrv[d] for d in ds if mvrv.get(d)}
    out["nupl"] = {d: 1 - 1 / mvrv[d] for d in ds if mvrv.get(d)}
    # MVRV Z-Score = (市值 − 已实现市值) / 市值的历史标准差（扩张窗口，和 Glassnode 同口径）
    z, n, mean, m2 = {}, 0, 0.0, 0.0
    for d in ds:
        cap = mc.get(d) or (p[d] * sply[d] if sply.get(d) else None)
        if not cap or not mvrv.get(d):
            continue
        n += 1
        delta = cap - mean; mean += delta / n; m2 += delta * (cap - mean)
        if n > 365:
            sd = math.sqrt(m2 / (n - 1))
            z[d] = (cap - cap / mvrv[d]) / sd
    out["mvrv_z"] = z
    pv = [(d, p[d]) for d in ds]
    ma200, ma111, ma350 = sma(pv, 200), sma(pv, 111), sma(pv, 350)
    out["mayer"] = {d: p[d] / ma200[d] for d in ma200}
    out["pi_cycle"] = {d: ma111[d] / (2 * ma350[d]) for d in ma350 if d in ma111}
    iv = [(d, iss[d]) for d in sorted(iss)]
    ma365 = sma(iv, 365)
    out["puell"] = {d: iss[d] / ma365[d] for d in ma365 if ma365[d]}
    return out


def fetch_flows():
    c = cm_fetch(CM_B, "2010-07-18")                     # 全历史：交易所流量 / 余额要能看完整周期
    fin, fout, bal = c["FlowInExNtv"], c["FlowOutExNtv"], c["SplyExNtv"]
    out = {"ex_inflow": fin, "ex_outflow": fout, "ex_balance": bal,
           "ex_netflow": {d: fin[d] - fout[d] for d in fin if d in fout}}
    if not out["ex_netflow"]:
        raise RuntimeError("CoinMetrics 交易所流量为空")
    return out


# ---------------------------------------------------------------- 第四层：情绪 / 衍生品
def fetch_fng():
    rows = get("https://api.alternative.me/fng/?limit=0")["data"]
    return {"fng": {day(r["timestamp"]): int(r["value"]) for r in rows}}


HL = "https://api.hyperliquid.xyz/info"


def fetch_hyperliquid(prev):
    meta, ctxs = post_json(HL, {"type": "metaAndAssetCtxs"})
    names = [u["name"] for u in meta["universe"]]
    ctx = ctxs[names.index("BTC")]
    oi_usd = float(ctx["openInterest"]) * float(ctx["markPx"])
    # 资金费率历史：逐小时，按 UTC 日取均值再年化（Hyperliquid 含约 11% 年化的基准利息，和币安 0.01%/8h 同量级）
    have = sorted((prev.get("hl_funding") or {}).keys())
    start_day = shift(have[-1], -2) if have else shift(TODAY, -180)
    t = int(dt.datetime.fromisoformat(start_day).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    end = int(NOW.timestamp() * 1000)
    hourly = {}
    for _ in range(40):
        rows = post_json(HL, {"type": "fundingHistory", "coin": "BTC", "startTime": t})
        if not rows:
            break
        for r in rows:
            d = day(int(r["time"]) // 1000)
            hourly.setdefault(d, []).append(float(r["fundingRate"]))
        t = int(rows[-1]["time"]) + 1
        if len(rows) < 500 or t >= end:
            break
        time.sleep(0.4)
    funding = {d: sum(v) / len(v) * 24 * 365 * 100 for d, v in hourly.items() if d < TODAY and len(v) >= 20}
    return {"hl_funding": funding, "hl_oi": {TODAY: oi_usd}}


STABLE_SYMS = set("usdt usdc dai usde usds fdusd pyusd tusd usdd busd frax usd1 rlusd usdx gusd lusd susd crvusd gho "
                  "usdb usdy usyc buidl ousg usd0 eurc xaut paxg susde sfrax usdf usdg usdtb bfusd lisusd".split())
DERIV_SYMS = set("wbtc weth steth wsteth weeth eeth cbbtc rseth reth meth cbeth lbtc solvbtc jitosol msol bnsol "
                 "ezeth sweth rsweth tbtc btcb wbeth jupsol bbsol hsol oseth ethx sfrxeth wbnb clbtc fbtc "
                 "unibtc pumpbtc enzobtc stbtc kbtc".split())


def fetch_coingecko():
    g = get("https://api.coingecko.com/api/v3/global")["data"]
    out = {"btc_dom": {TODAY: g["market_cap_percentage"]["btc"]},
           "total_mcap": {TODAY: g["total_market_cap"]["usd"]}}
    time.sleep(4)
    mk = get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc"
             "&per_page=150&page=1&price_change_percentage=30d")
    btc = next((x for x in mk if x["id"] == "bitcoin"), None)
    b30 = btc and btc.get("price_change_percentage_30d_in_currency")
    pool = []
    for x in mk:
        s, i = (x.get("symbol") or "").lower(), (x.get("id") or "")
        if x["id"] == "bitcoin" or s in STABLE_SYMS or s in DERIV_SYMS:
            continue
        if any(k in i for k in ("wrapped", "staked", "bridged", "restaked", "binance-peg", "usd-coin", "tether")):
            continue
        if x.get("price_change_percentage_30d_in_currency") is None:
            continue
        pool.append(x)
    pool = pool[:50]
    extra = {}
    if b30 is not None and len(pool) >= 40:
        beat = sum(1 for x in pool if x["price_change_percentage_30d_in_currency"] > b30)
        out["altseason"] = {TODAY: beat / len(pool) * 100}
        extra = {"样本数": len(pool), "BTC30日涨跌": round(b30, 2)}
    return out, extra


def fetch_categories():
    rows = get("https://api.coingecko.com/api/v3/coins/categories")
    snap, special = [], {}
    for r in rows:
        if r.get("id") in ("tokenized-stock", "stablecoins"):
            special[r["id"]] = (r.get("market_cap") or 0, r.get("volume_24h") or 0)
        if not r.get("market_cap") or r["market_cap"] < 5e7 or r.get("market_cap_change_24h") is None:
            continue
        snap.append({"id": r["id"], "名称": r["name"], "市值": round(r["market_cap"]), "24h": round(r["market_cap_change_24h"], 2),
                     "成交额": round(r.get("volume_24h") or 0), "前三": r.get("top_3_coins_id") or []})
    snap.sort(key=lambda x: -x["市值"])
    return snap[:300], special


# ---------------------------------------------------------------- 主流程
OBSOLETE = ["stable_major"]          # 2026-10-02 起 L1 不再用的序列，从台账里清掉


def main():
    L = load(LEDGER, {}) or {}
    L.setdefault("序列", {})
    L.setdefault("源状态", {})
    L.setdefault("附注", {})
    S = L["序列"]
    for k in OBSOLETE:
        S.pop(k, None)

    def run(name, fn, replace=True):
        t0 = time.time()
        try:
            res = fn()
            extra = None
            if isinstance(res, tuple):
                res, extra = res
            for k, s in res.items():
                S[k] = dict(s) if replace else {**S.get(k, {}), **s}
            latest = max((max(s) for s in res.values() if s), default=None)
            L["源状态"][name] = {"ok": True, "时间UTC": NOW.strftime("%Y-%m-%d %H:%M"), "最新日期": latest, "错误": None}
            if extra:
                L["附注"][name] = extra
            print(f"  OK  {name}（{time.time() - t0:.0f}s，最新 {latest}，{len(res)} 条序列）")
            if extra:
                print("      ", json.dumps(extra, ensure_ascii=False)[:400])
        except Exception as e:  # noqa
            prev = L["源状态"].get(name, {})
            L["源状态"][name] = {"ok": False, "时间UTC": NOW.strftime("%Y-%m-%d %H:%M"),
                                "最新日期": prev.get("最新日期"), "错误": f"{type(e).__name__}: {str(e)[:160]}"}
            print(f"  失败 {name}: {type(e).__name__}: {str(e)[:160]}")

    run("DefiLlama 稳定币", fetch_stables)
    run("FRED", fetch_fred)
    run("ETF 资金流", fetch_etf)
    run("Deribit", fetch_basis, replace=False)
    run("CME 升水", fetch_cme, replace=False)
    run("CoinMetrics 周期", fetch_cycle)
    run("CoinMetrics 交易所流量", fetch_flows)
    run("alternative.me", fetch_fng)
    run("Hyperliquid", lambda: fetch_hyperliquid(S), replace=False)
    run("CoinGecko", fetch_coingecko, replace=False)

    # 板块轮动快照（CoinGecko 类目），逐日攒；顺手记美股代币化 / 稳定币类目规模（L1 监控项）
    try:
        time.sleep(4)
        R = load(ROT, {}) or {}
        R[TODAY], special = fetch_categories()
        R = {k: R[k] for k in sorted(R)[-ROT_KEEP:]}
        save(ROT, R)
        if "tokenized-stock" in special and "stablecoins" in special:
            for k, (a, b) in (("tok_stock", special["tokenized-stock"]), ("cg_stable", special["stablecoins"])):
                S.setdefault(f"{k}_mcap", {})[TODAY] = a
                S.setdefault(f"{k}_vol", {})[TODAY] = b
        L["源状态"]["CoinGecko 类目"] = {"ok": True, "时间UTC": NOW.strftime("%Y-%m-%d %H:%M"), "最新日期": TODAY, "错误": None}
        print(f"  OK  CoinGecko 类目（{len(R[TODAY])} 个）")
    except Exception as e:  # noqa
        L["源状态"]["CoinGecko 类目"] = {"ok": False, "时间UTC": NOW.strftime("%Y-%m-%d %H:%M"),
                                       "最新日期": None, "错误": f"{type(e).__name__}: {str(e)[:160]}"}
        print(f"  失败 CoinGecko 类目: {e}")

    L["序列"] = {k: {d: sig(v) for d, v in sorted(s.items())} for k, s in sorted(S.items())}
    L["更新时间UTC"] = NOW.strftime("%Y-%m-%d %H:%M")
    save(LEDGER, L)
    ok = sum(1 for v in L["源状态"].values() if v["ok"])
    print(f"宏观台账已写入（{ok}/{len(L['源状态'])} 个数据源成功，{sum(len(s) for s in L['序列'].values())} 个数据点）")
    # 宏观数据是锦上添花，全挂也不拦截日更主流程
    sys.exit(0)


if __name__ == "__main__":
    main()
