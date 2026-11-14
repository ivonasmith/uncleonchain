#!/usr/bin/env python3
"""历史案例结果指标（框架第十五节「历史量级对照」）。只用标准库；历史数据不日更，案例或口径改了再跑。

每个案例的代币（alpha/cases.json 的 tokens）：
  价格     Coin Metrics 有的（supply = cm:*）用 PriceUSD 逐日完整；其余 coins.llama.fi/chart（CoinGecko 价格，按 UTC 日取最后一个点 = 当日收盘代理），每次最多 500 天，分段拼
  BTC      Coin Metrics 社区版 PriceUSD（逐日完整；coins.llama.fi 的 BTC 日线有缺日，11-14 实测 ARB 首日对不上），用来算相对 BTC 峰值倍数（附录二 C：max_t[(P_t/P0)/(BTC_t/BTC0)]，同一天对齐）
  估值     supply = "cm:<资产>" → Coin Metrics 社区版 CapMrktCurUSD（流通市值，峰值和日期）；
           supply = "max" → 峰值收盘 × CoinGecko 最大供给（没有最大供给用总供给），叫「峰值完全稀释估值」；
           supply = "none" → 供给无上限或有迁移 / 再基准，不算估值
  资金     DefiLlama 协议 TVL 峰值；手续费（dailyFees）30 天滚动合计的峰值与「热度天数」（30 天均值 ≥ 峰值一半的天数）
口径（写死，改了要在 changelog 记）：
  P0      = 价格源首个有数据的 UTC 日（不是创世、预售或可参与日）
  峰值    = P0 之后收盘最高的一天
  ≥2×天数 = P0 后 365 天内收盘 ≥ 2 × P0 的完整 UTC 日个数
  跌回P0  = 峰值之后第一次收盘 < P0 的日子距峰值的天数；至今没跌回记 None
输出 data/alpha/case_metrics.json（指标）+ data/alpha/case_series.json（周线：价格 / P0、30 天手续费，给网页画图）
"""
import json, os, sys, time, urllib.request
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "alpha")
UA = {"User-Agent": "uncleonchain-alpha/1.0"}
TODAY = dt.datetime.now(dt.timezone.utc).date()


def get(url, tries=3, timeout=90):
    err = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.load(r)
        except Exception as e:
            err = e
            time.sleep((25 if "429" in str(e) else 4) * (i + 1))   # CoinGecko 免费接口限流
    raise RuntimeError(f"{url}: {err}")


def day(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()


def prices(cg, start="2010-07-01"):
    """{UTC 日: 收盘代理}，只取 < 今天的完整日。"""
    out, t = {}, int(dt.datetime.fromisoformat(start + "T00:00:00+00:00").timestamp())
    end = time.time()
    while t < end:
        d = get(f"https://coins.llama.fi/chart/coingecko:{cg}?start={t}&span=500&period=1d")
        pts = (d.get("coins", {}).get(f"coingecko:{cg}") or {}).get("prices") or []
        for p in pts:
            out[day(p["timestamp"])] = p["price"]
        t += 500 * 86400
        time.sleep(0.4)
    return {k: v for k, v in sorted(out.items()) if k < TODAY.isoformat()}


def cm_price(asset):
    d = get(f"https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets={asset}&metrics=PriceUSD&frequency=1d&page_size=10000&start_time=2010-01-01")
    return {r["time"][:10]: float(r["PriceUSD"]) for r in d.get("data", []) if r.get("PriceUSD") and r["time"][:10] < TODAY.isoformat()}


def cm_mcap(asset):
    d = get(f"https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets={asset}&metrics=CapMrktCurUSD&frequency=1d&page_size=10000&start_time=2009-01-01")
    return {r["time"][:10]: float(r["CapMrktCurUSD"]) for r in d.get("data", []) if r.get("CapMrktCurUSD")}


def cg_supply(cg):
    d = get(f"https://api.coingecko.com/api/v3/coins/{cg}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false")
    m = d.get("market_data") or {}
    return m.get("max_supply"), m.get("total_supply")


def price_metrics(px, btc):
    ds = list(px)
    if not ds:
        return None
    d0, p0 = ds[0], px[ds[0]]
    span = (dt.date.fromisoformat(ds[-1]) - dt.date.fromisoformat(d0)).days + 1
    pk = max(ds, key=lambda d: px[d])
    rel = [(d, (px[d] / p0) / (btc[d] / btc[d0])) for d in ds if d in btc and d0 in btc]
    d365 = (dt.date.fromisoformat(d0) + dt.timedelta(days=365)).isoformat()
    rel365 = [r for r in rel if r[0] <= d365]
    below = next((d for d in ds if d > pk and px[d] < p0), None)
    # 首周后口径：第一天的价格普通人基本买不到，另算从 P0+7 天（之后第一个有数据的日子）收盘起的倍数
    d7 = next((d for d in ds if d >= (dt.date.fromisoformat(d0) + dt.timedelta(days=7)).isoformat()), None)
    p7 = px[d7] if d7 else None
    pk7 = max((d for d in ds if d7 and d >= d7), key=lambda d: px[d], default=None)
    rel7 = [(d, (px[d] / p7) / (btc[d] / btc[d7])) for d in ds if d7 and d >= d7 and d in btc and d7 in btc]
    last = ds[-1]
    return {"p0_date": d0, "p0": p0, "peak_date": pk, "peak": px[pk], "mult": px[pk] / p0,
            "days_to_peak": (dt.date.fromisoformat(pk) - dt.date.fromisoformat(d0)).days,
            "rel_btc_peak": max(r[1] for r in rel) if rel else None, "rel_btc_peak_date": max(rel, key=lambda r: r[1])[0] if rel else None,
            "rel_btc_peak_365": max(r[1] for r in rel365) if rel365 else None,
            "days_ge2x_365": sum(1 for d in ds if d <= d365 and px[d] >= 2 * p0),
            "days_peak_to_below_p0": (dt.date.fromisoformat(below) - dt.date.fromisoformat(pk)).days if below else None,
            "last_date": last, "last": px[last], "dd_from_peak": px[last] / px[pk] - 1, "last_vs_p0": px[last] / p0,
            "n_days": len(ds), "coverage": round(len(ds) / span, 3),
            "p7_date": d7, "p7": p7, "mult_p7": px[pk7] / p7 if pk7 else None, "rel_btc_peak_p7": max(r[1] for r in rel7) if rel7 else None}


def fees_metrics(slug):
    d = get(f"https://api.llama.fi/summary/fees/{slug}?dataType=dailyFees")
    ch = [(day(t), v or 0) for t, v in d.get("totalDataChart") or [] if day(t) < TODAY.isoformat()]
    if len(ch) < 30:
        return None, []
    roll, s = [], 0.0
    for i, (dd, v) in enumerate(ch):
        s += v
        if i >= 30:
            s -= ch[i - 30][1]
        if i >= 29:
            roll.append((dd, s))
    pk = max(roll, key=lambda r: r[1])
    hot = sum(1 for r in roll if r[1] >= pk[1] / 2)
    return {"first": ch[0][0], "peak30": pk[1], "peak30_date": pk[0], "hot_days": hot, "last30": roll[-1][1], "last_date": roll[-1][0]}, roll


def tvl_metrics(slug):
    d = get(f"https://api.llama.fi/protocol/{slug}")
    t = [(day(x["date"]), x["totalLiquidityUSD"]) for x in d.get("tvl") or [] if x.get("totalLiquidityUSD") is not None]
    if not t:
        return None
    pk = max(t, key=lambda r: r[1])
    return {"first": t[0][0], "peak": pk[1], "peak_date": pk[0], "last": t[-1][1], "last_date": t[-1][0]}


def weekly(series, base=None):
    """{日: 值} → 每 7 天一个点（给网页画图，控制体积）。"""
    ks = list(series)
    return [[k, round(series[k] / base, 5) if base else round(series[k])] for k in ks[::7]]


def main():
    cases = json.load(open(os.path.join(HERE, "cases.json"), encoding="utf-8"))["cases"]
    only = set(sys.argv[1:])
    prev = {}
    try:
        prev = json.load(open(os.path.join(OUT, "case_metrics.json"), encoding="utf-8"))["cases"]
    except Exception:
        pass
    btc = cm_price("btc")
    print("BTC", len(btc), "天")
    res, ser = dict(prev), {}
    try:
        ser = json.load(open(os.path.join(OUT, "case_series.json"), encoding="utf-8"))
    except Exception:
        pass
    for c in cases:
        if only and c["id"] not in only:
            continue
        r = {"tokens": [], "fees": None, "tvl": None, "errors": []}
        s = {"tokens": {}, "fees30": []}
        for t in c["tokens"]:
            try:
                if t["cg"] == "bitcoin":
                    px = btc
                else:
                    px = prices(t["cg"], t.get("from") or "2010-07-01")
                    if t["supply"].startswith("cm:"):
                        # P0 以最早有数据的源为准（11-14 实测：Coin Metrics 的 UNI 从 09-18 才有，漏了 09-17 首日，倍数差一倍多）；
                        # coins.llama.fi 缺的日子用 Coin Metrics 同日收盘补，不前向填充
                        cmp_ = cm_price(t["supply"][3:])
                        filled = {k: v for k, v in cmp_.items() if k not in px and (not px or k > next(iter(px)))}
                        px = dict(sorted({**px, **filled}.items()))
                m = price_metrics(px, btc)
                if not m:
                    r["errors"].append(f'{t["sym"]}: 价格源没有数据'); continue
                m.update(sym=t["sym"], role=t["role"], cg=t["cg"], supply_basis=t["supply"])
                if t["supply"].startswith("cm:"):
                    mc = cm_mcap(t["supply"][3:])
                    if mc:
                        k = max(mc, key=mc.get)
                        m.update(val_peak=mc[k], val_peak_date=k, val_kind="流通市值（Coin Metrics）")
                elif t["supply"] == "max":
                    try:
                        mx, tot = cg_supply(t["cg"])
                    except Exception as e:   # 供给取不到：估值留空，价格指标照常记
                        mx = tot = None
                        r["errors"].append(f'{t["sym"]} 供给: {str(e)[:120]}')
                    sup = mx or tot
                    if sup:
                        m.update(val_peak=m["peak"] * sup, val_peak_date=m["peak_date"], val_kind="完全稀释估值（峰值收盘 × " + ("最大供给" if mx else "总供给") + "，CoinGecko " + TODAY.isoformat() + "）", supply=sup)
                    time.sleep(3)
                r["tokens"].append(m)
                s["tokens"][t["sym"]] = weekly(px, m["p0"])
            except Exception as e:
                r["errors"].append(f'{t["sym"]}: {str(e)[:160]}')
        if c["llama"].get("fees"):
            try:
                fm, roll = fees_metrics(c["llama"]["fees"])
                mt = next((x for x in r["tokens"] if x["role"] == "main"), None)
                if fm and mt:   # 手续费序列比代币首日晚一年以上：覆盖不到早期热度
                    fm["late"] = (dt.date.fromisoformat(fm["first"]) - dt.date.fromisoformat(mt["p0_date"])).days > 365
                r["fees"] = fm
                s["fees30"] = [[d, round(v)] for d, v in roll[::7]]
            except Exception as e:
                r["errors"].append(f'fees: {str(e)[:160]}')
        if c["llama"].get("tvl"):
            try:
                r["tvl"] = tvl_metrics(c["llama"]["tvl"])
            except Exception as e:
                r["errors"].append(f'tvl: {str(e)[:160]}')
        res[c["id"]] = r
        ser[c["id"]] = s
        main_t = next((x for x in r["tokens"] if x["role"] == "main"), None)
        print(c["id"], "·", (f'{main_t["sym"]} ×{main_t["mult"]:.1f} 峰值 {main_t["peak_date"]}' if main_t else "无价格"), "· 错误", r["errors"] or "无")
    os.makedirs(OUT, exist_ok=True)
    meta = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "btc_from": next(iter(btc)), "cases": res}
    json.dump(meta, open(os.path.join(OUT, "case_metrics.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(ser, open(os.path.join(OUT, "case_series.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
