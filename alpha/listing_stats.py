#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交易所上币回报统计 R0（口径和判定标准见 alpha/research/交易所上币回报研究.md，写死，别改）。

输入 data/alpha/listings.json 的事件窗口（24 小时）；BTC 同期对照用币安现货 BTCUSDT 1 分钟 K 线（缓存 data/alpha/btc_ref.json）。
输出 data/alpha/listing_stats.json：按 所 × 市场（现货 / 永续）给 n、未取到数、M1 / M1t / M2 的分位数和区间计数、M2 < 0 比例、平均数旁注、BTC 同期、超额。
n < 20 的格子写「样本不足」，只列数字、不分档。只说历史分布，不写任何操作建议。
用法：python3 alpha/listing_stats.py
"""
import datetime as dt, json, os, statistics as st, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import listings as L

ROOT = os.path.dirname(HERE)
OUT = os.path.join(os.environ.get("LP_DATA", os.path.join(ROOT, "data")), "alpha")
SRC, DST, BTC = (os.path.join(OUT, f) for f in ("listings.json", "listing_stats.json", "btc_ref.json"))
MIN_N = 20
BINS = [(-1e9, -0.20, "< -20%"), (-0.20, 0, "-20%～0"), (0, 0.20, "0～20%"), (0.20, 0.50, "20%～50%"), (0.50, 1.0, "50%～100%"), (1.0, 1e9, "> 100%")]


def pct(xs, q):
    """线性插值分位数（q 0～1）"""
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 4)


def dist(xs):
    return {"n": len(xs), "p10": pct(xs, .1), "p25": pct(xs, .25), "p50": pct(xs, .5), "p75": pct(xs, .75), "p90": pct(xs, .9),
            "mean": round(sum(xs) / len(xs), 4) if xs else None,
            "bins": [{"label": lb, "n": sum(1 for x in xs if lo <= x < hi)} for lo, hi, lb in BINS]}


def btc_move(t0_ms, cache):
    """BTC 在同一 24 小时窗口的涨跌：t0 那根 1 分钟开盘价 → t0 + 1439 分钟那根收盘价（和币的 M2 同口径）"""
    k = str(t0_ms)
    if k in cache:
        return cache[k]
    a = L.get(L.SPOT_K.format(s="BTCUSDT", t=t0_ms).replace("limit=1000", "limit=1"))
    b = L.get(L.SPOT_K.format(s="BTCUSDT", t=t0_ms + 1439 * 60000).replace("limit=1000", "limit=1"))
    try:
        v = round(float(b[0][4]) / float(a[0][1]) - 1, 4) if int(a[0][0]) == t0_ms and int(b[0][0]) == t0_ms + 1439 * 60000 else None
    except Exception:
        v = None
    cache[k] = v
    time.sleep(0.1)
    return v


def main():
    store = json.load(open(SRC, encoding="utf-8"))
    try:
        cache = json.load(open(BTC, encoding="utf-8"))
    except Exception:
        cache = {}
    groups = {}
    for e in store["events"].values():
        if e.get("exchange", "Binance") not in ("Binance", "OKX") or not e.get("primary") or e.get("venue") == "okx_us":
            continue
        groups.setdefault((e.get("exchange", "Binance"), e["market"]), []).append(e)
    rows = []
    for (ex, mk), evs in sorted(groups.items()):
        ok = [e for e in evs if (e.get("w") or {}).get("complete")]
        m1, m1t, m2, m2b, btc, exc = [], [], [], [], [], []
        for e in ok:
            w = e["w"]
            if w.get("high24") is None or w.get("h24") is None:
                continue
            m1.append(w["high24"]); m1t.append(w["high24_min"] / 60); m2.append(w["h24"])
            if w.get("m30") is not None:
                m2b.append(round((1 + w["h24"]) / (1 + w["m30"]) - 1, 4))
            t0 = int(dt.datetime.strptime(w["first_trade_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
            b = btc_move(t0, cache)
            if b is not None:
                btc.append(b); exc.append(round(w["h24"] - b, 4))
        n = len(m2)
        row = {"exchange": ex, "market": mk, "events": len(evs), "n": n, "missing": len(evs) - n,
               "level": "描述级（样本不足 n<%d，只列数字、不分档）" % MIN_N if n < MIN_N else "可看分布（n≥%d）" % MIN_N,
               "enough": n >= MIN_N}
        if n:
            row.update(m1_peak_24h=dist(m1), m1t_hours=dist(m1t), m2_close_24h=dist(m2), m2b_from_30m=dist(m2b), share_below_ref_30m=round(sum(1 for x in m2b if x < 0) / len(m2b), 4) if m2b else None,
                       peak_in_first5min_share=round(sum(1 for x in m1t if x <= 5 / 60) / n, 4), share_below_ref=round(sum(1 for x in m2 if x < 0) / n, 4),
                       btc_24h=dist(btc) if btc else None, excess_24h=dist(exc) if exc else None)
        rows.append(row)
    json.dump(cache, open(BTC, "w", encoding="utf-8"))
    out = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "stage": "R0（24 小时窗口）", "rows": rows,
           "note": "参考价 = 第一根 1 分钟 K 线开盘价，事后读数，不是可成交价；平均数被少数暴涨币拉高，只作旁注，主口径是中位数；"
                   "现货和永续分开；BTC 对照 = 同一 24 小时窗口币安现货 BTCUSDT；口径见 alpha/research/交易所上币回报研究.md"}
    json.dump(out, open(DST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in rows:
        if not r["n"]:
            print(r["exchange"], r["market"], "n=0"); continue
        print(f"{r['exchange']} {r['market']}: n={r['n']} 未取到={r['missing']} {r['level']}")
        print(f"   最高点涨幅 中位 {r['m1_peak_24h']['p50']:+.2%} 到最高点中位 {r['m1t_hours']['p50']:.1f} 小时 | 24h 终点 中位 {r['m2_close_24h']['p50']:+.2%} "
              f"（P25 {r['m2_close_24h']['p25']:+.2%} / P75 {r['m2_close_24h']['p75']:+.2%}）低于上线价 {r['share_below_ref']:.0%} | "
              f"含开盘尖峰：最高点在开盘 5 分钟内占 {r['peak_in_first5min_share']:.0%} | 30 分钟后起点的 24h 回报 中位 {r['m2b_from_30m']['p50']:+.2%}（低于起点 {r['share_below_ref_30m']:.0%}）| "
              f"BTC 同期中位 {r['btc_24h']['p50'] if r['btc_24h'] else 'U'} 超额中位 {r['excess_24h']['p50'] if r['excess_24h'] else 'U'}")


if __name__ == "__main__":
    main()
