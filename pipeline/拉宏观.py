#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宏观四层仪表盘 · 拉数（全部免费、免 key 的公开接口，GitHub Actions 每天跑一次，不消耗 Claude 额度）

  第一层 宏观流动性  DefiLlama 稳定币（USDT+USDC / 全部美元稳定币）
                     FRED 公开 CSV：DFII10 10Y 实际利率 · T10Y2Y 利差 · DTWEXBGS 广义美元 · WALCL 美联储资产负债表 · RRPONTSYD 逆回购
                     Deribit：约 3 个月期 BTC 期货年化升水（CME Basis 的替代口径）
  第二层 周期定位    CoinMetrics Community：价格、MVRV、流通量、市值、矿工发行额
                     → 自算 Realized Price、MVRV Z-Score、NUPL、Mayer Multiple、Puell Multiple、Pi Cycle
  第三层 筹码结构    CoinMetrics Community：交易所 BTC 流入/流出（flash 口径）、交易所余额
  第四层 情绪衍生品  alternative.me 恐慌贪婪指数 · Hyperliquid BTC 永续资金费率与未平仓 · CoinGecko 市值占比与自建山寨季指数
  板块轮动           CoinGecko 类目（逐日快照，自己攒历史）

每个数据源各自 try，一个挂了不影响其他；失败写进「源状态」，页面上会标出来，绝不拿旧值冒充新值。
写：data/宏观台账.json、data/板块台账.json
"""
import csv, io, json, math, re, sys, time, datetime as dt, urllib.request, urllib.error
from common import get, post_json, load, save, today_utc, shift, day, UA

LEDGER = "宏观台账.json"
ROT = "板块台账.json"
KEEP = 800           # 逐日序列只留最近 800 天（图最多画 1 年，均线/Z-Score 在拉数时用全历史算好）
ROT_KEEP = 120
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = today_utc()


def text(url, timeout=60, tries=4):
    h = {"User-Agent": UA["User-Agent"], "Accept": "*/*"}
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


def trim(series, keep=KEEP):
    ks = sorted(series)[-keep:]
    return {k: series[k] for k in ks}


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


# ---------------------------------------------------------------- 第一层：稳定币
def fetch_stables():
    def chart(q=""):
        rows = get(f"https://stablecoins.llama.fi/stablecoincharts/all{q}", timeout=90)
        out = {}
        for r in rows:
            tot = r.get("totalCirculatingUSD") or {}
            v = sum(x for x in tot.values() if isinstance(x, (int, float)))
            if v:
                out[day(r["date"])] = v
        return out
    total = chart()
    usdt = chart("?stablecoin=1")
    usdc = chart("?stablecoin=2")
    major = {d: usdt[d] + usdc[d] for d in usdt if d in usdc}
    # DefiLlama 当天的点是盘中值，只保留 UTC 完整日
    return {"stable_total": {d: v for d, v in total.items() if d < TODAY},
            "stable_major": {d: v for d, v in major.items() if d < TODAY}}


# ---------------------------------------------------------------- 第一层：FRED（公开 CSV，不需要 key）
FRED = {"fred_dfii10": ("DFII10", 1), "fred_t10y2y": ("T10Y2Y", 1), "fred_broad_usd": ("DTWEXBGS", 1),
        "fred_walcl": ("WALCL", 1e6), "fred_rrp": ("RRPONTSYD", 1e9)}


def fetch_fred():
    start = shift(TODAY, -KEEP - 40)
    out = {}
    for key, (sid, mult) in FRED.items():
        raw = text(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}", timeout=60)
        s = {}
        for row in list(csv.reader(io.StringIO(raw)))[1:]:        # 表头 observation_date / DATE 都跳过
            if len(row) < 2 or not re.match(r"^\d{4}-\d{2}-\d{2}$", row[0]) or row[1] in ("", "."):
                continue
            s[row[0]] = float(row[1]) * mult
        if not s:
            raise RuntimeError(f"FRED {sid} 返回空")
        out[key] = s
        time.sleep(0.5)
    return out


# ---------------------------------------------------------------- 第一层：Deribit 期货年化升水
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def fetch_basis():
    rows = get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=future")["result"]
    best = None
    for r in rows:
        m = re.match(r"^BTC-(\d{1,2})([A-Z]{3})(\d{2})$", r.get("instrument_name", ""))
        if not m or not r.get("mark_price") or not r.get("estimated_delivery_price"):
            continue
        exp = dt.datetime(2000 + int(m.group(3)), MON[m.group(2)], int(m.group(1)), 8, tzinfo=dt.timezone.utc)
        days = (exp - NOW).total_seconds() / 86400
        if days < 30:
            continue
        ann = (r["mark_price"] / r["estimated_delivery_price"] - 1) * 365 / days * 100
        cand = (abs(days - 90), r["instrument_name"], round(ann, 3), round(days))
        if best is None or cand < best:
            best = cand
    if not best:
        raise RuntimeError("没有 30 天以上的交割合约")
    return {"deribit_basis": {TODAY: best[2]}}, {"合约": best[1], "剩余天数": best[3]}


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
    return {k: trim(v) for k, v in out.items()}


def fetch_flows():
    c = cm_fetch(CM_B, shift(TODAY, -KEEP - 10))
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
    snap = []
    for r in rows:
        if not r.get("market_cap") or r["market_cap"] < 5e7 or r.get("market_cap_change_24h") is None:
            continue
        snap.append({"id": r["id"], "名称": r["name"], "市值": round(r["market_cap"]),
                     "24h": round(r["market_cap_change_24h"], 2), "成交额": round(r.get("volume_24h") or 0),
                     "前三": r.get("top_3_coins_id") or []})
    snap.sort(key=lambda x: -x["市值"])
    return snap[:300]


# ---------------------------------------------------------------- 主流程
def main():
    L = load(LEDGER, {}) or {}
    L.setdefault("序列", {})
    L.setdefault("源状态", {})
    L.setdefault("附注", {})
    S = L["序列"]

    def run(name, fn, replace=True):
        t0 = time.time()
        try:
            res = fn()
            extra = None
            if isinstance(res, tuple):
                res, extra = res
            for k, s in res.items():
                if replace:
                    S[k] = trim(s)
                else:
                    S[k] = trim({**S.get(k, {}), **s})
            latest = max((max(s) for s in res.values() if s), default=None)
            L["源状态"][name] = {"ok": True, "时间UTC": NOW.strftime("%Y-%m-%d %H:%M"), "最新日期": latest, "错误": None}
            if extra:
                L["附注"][name] = extra
            print(f"  OK  {name}（{time.time() - t0:.0f}s，最新 {latest}）")
        except Exception as e:  # noqa
            prev = L["源状态"].get(name, {})
            L["源状态"][name] = {"ok": False, "时间UTC": NOW.strftime("%Y-%m-%d %H:%M"),
                                "最新日期": prev.get("最新日期"), "错误": f"{type(e).__name__}: {str(e)[:160]}"}
            print(f"  失败 {name}: {type(e).__name__}: {str(e)[:160]}")

    run("DefiLlama 稳定币", fetch_stables)
    run("FRED", fetch_fred)
    run("Deribit", fetch_basis, replace=False)
    run("CoinMetrics 周期", fetch_cycle)
    run("CoinMetrics 交易所流量", fetch_flows)
    run("alternative.me", fetch_fng)
    run("Hyperliquid", lambda: fetch_hyperliquid(S), replace=False)
    run("CoinGecko", fetch_coingecko, replace=False)

    # 板块轮动快照（CoinGecko 类目），逐日攒
    try:
        time.sleep(4)
        R = load(ROT, {}) or {}
        R[TODAY] = fetch_categories()
        R = {k: R[k] for k in sorted(R)[-ROT_KEEP:]}
        save(ROT, R)
        L["源状态"]["CoinGecko 类目"] = {"ok": True, "时间UTC": NOW.strftime("%Y-%m-%d %H:%M"), "最新日期": TODAY, "错误": None}
        print(f"  OK  CoinGecko 类目（{len(R[TODAY])} 个）")
    except Exception as e:  # noqa
        L["源状态"]["CoinGecko 类目"] = {"ok": False, "时间UTC": NOW.strftime("%Y-%m-%d %H:%M"),
                                       "最新日期": None, "错误": f"{type(e).__name__}: {str(e)[:160]}"}
        print(f"  失败 CoinGecko 类目: {e}")

    L["更新时间UTC"] = NOW.strftime("%Y-%m-%d %H:%M")
    save(LEDGER, L)
    ok = sum(1 for v in L["源状态"].values() if v["ok"])
    print(f"宏观台账已写入（{ok}/{len(L['源状态'])} 个数据源成功）")
    # 宏观数据是锦上添花，全挂也不拦截日更主流程
    sys.exit(0)


if __name__ == "__main__":
    main()
