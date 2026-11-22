#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""其它交易所全历史上币复盘（CCXT，只在 GitHub Actions 跑；口径同 alpha/listing_history.py 和研究文档 v3）。

做法：拉该所全部现货交易对 → 每个币取它所有交易对里最早的第一根日线 = 上币日（两类 K 线接口都支持：一次取或二分找窗口）→
起点 = 开盘第 15 分钟收盘价（该所 1 分钟历史够深才有；不够就用上币当天第一根 1 小时收盘价，ref_type 标 1h）→
第 7 / 30 / 90 天日收盘回报、90 天内最高点（按日收盘、不含上币当天）、BTC 同期（币安 BTCUSDT）与超额 → 按牛熊 × 涨跌腿、当时已确认的腿、L2 状态、年份分组。
**幸存者偏差**：CCXT 只能列出现在还在交易的交易对，已下架的币查不到，回报会偏高；和 Binance 比要用 Binance「只看现在还在交易的币」口径（listing_compare.py）。
计价：USDT / USDC / USD / EUR / KRW 按计价货币算回报（法币汇率变动相对币价很小，标注）；BTC 计价用该所 BTC 美元价换算。
剔除：稳定币、杠杆代币、疑似代币化股票（启发式：2025-06 起上线、代码以 X / ON 结尾或 r 开头的 4～7 位代码），交易所开张头 30 天的首批币。
用法：python3 alpha/listing_history_x.py <ccxt_id> [--minutes 270] [--shard i/n]
输出 data/alpha/listing_history_<id>.json（逐币 + 分组统计）。
"""
import datetime as dt, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import listing_history as LH

QUOTES = ("USDT", "USDC", "USD", "EUR", "KRW", "BTC")
SINCE0 = int(dt.datetime(2014, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
DAY = 86400000


def iso_day(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d")


def stock_suspect(base, day):
    return day >= "2025-06-01" and (re.fullmatch(r"[A-Z]{2,6}(X|ON)", base) is not None or re.fullmatch(r"r[A-Z]{2,6}", base) is not None)


def main():
    import ccxt
    exid = sys.argv[1]
    budget = int(sys.argv[sys.argv.index("--minutes") + 1]) * 60 if "--minutes" in sys.argv else 270 * 60
    t_start = time.time()
    ex = getattr(ccxt, exid)({"enableRateLimit": True, "timeout": 20000})
    mk = ex.load_markets()
    spot = [m for m in mk.values() if m.get("spot") and m.get("quote") in QUOTES and m.get("active") is not False]
    now = int(time.time() * 1000)

    def ohlcv(sym, tf, since, limit):
        for i in range(3):
            try:
                return ex.fetch_ohlcv(sym, tf, since=since, limit=limit)
            except (ccxt.RateLimitExceeded, ccxt.NetworkError):
                time.sleep(2 + 3 * i)
            except Exception:
                return []
        return []

    LIM = 100   # 每次取日线的根数（多数交易所单次上限 ≥ 100）

    def first_day(sym):
        """第一根日线的开盘时刻。两类接口：① 从 since 往后返回最早的数据（币安、Gate 式）→ 一次就拿到；
        ② 只返回 [since, since + LIM 天] 窗口里的数据（OKX、Bitget、KuCoin 式）→ 二分找最早有数据的窗口，约 12 次请求"""
        r = ohlcv(sym, "1d", SINCE0, LIM)
        if r:
            return r[0][0]
        lo, hi = SINCE0, now - DAY
        if not ohlcv(sym, "1d", hi - LIM * DAY, LIM):
            return None
        while hi - lo > DAY:
            mid = lo + (hi - lo) // 2 // DAY * DAY
            if ohlcv(sym, "1d", mid, LIM):
                hi = mid
            else:
                lo = mid
        r = ohlcv(sym, "1d", hi, LIM)
        return r[0][0] if r else None

    # 交易所能不能按 since 回溯：BTC 第一根日线如果落在最近 30 天，说明它忽略 since，没法复盘
    btc_sym = next((s for s in ("BTC/USDT", "BTC/USD", "BTC/KRW", "BTC/EUR", "BTC/USDC") if s in mk), None)
    bf = first_day(btc_sym) if btc_sym else None
    b = [[bf]] if bf else []
    if not b or b[0][0] > now - 30 * DAY:
        json.dump({"exchange": exid, "error": "该所 K 线接口不按 since 回溯，无法复盘", "btc_first": b[0][0] if b else None},
                  open(os.path.join(LH.OUT, f"listing_history_{exid}.json"), "w"), ensure_ascii=False)
        print(exid, "不能回溯，跳过")
        return
    ex_start = iso_day(b[0][0])
    btc_usd = LH.usd_closes("BTCUSDT")
    leg_at, leg_known, l2_at = LH.regime_tools()
    bases = {}
    for m in spot:
        if m["base"] in LH.STABLE or re.search(r"(UP|DOWN|BULL|BEAR|[235]L|[235]S)$", m["base"]) and len(m["base"]) > 3:
            continue
        bases.setdefault(m["base"], []).append(m)
    print(exid, "现货交易对", len(spot), "币", len(bases), "开张约", ex_start)
    coins = []
    items = sorted(bases.items())
    shard = sys.argv[sys.argv.index("--shard") + 1] if "--shard" in sys.argv else None
    if shard:   # 分片跑：第 i 份 / 共 n 份（大所的币太多，一台机器 4.5 小时跑不完）
        si, sn = (int(x) for x in shard.split("/"))
        items = items[si - 1::sn]
    for bi, (base, ms) in enumerate(items):
        if time.time() - t_start > budget:
            print("到时间预算，停在", bi)
            break
        firsts = []
        for m in ms:
            ft0 = first_day(m["symbol"])
            if ft0:
                firsts.append((ft0, QUOTES.index(m["quote"]), m))
        if not firsts:
            continue
        t0, _, m = min(firsts, key=lambda x: (x[0], x[1]))
        d0 = iso_day(t0)
        row = {"asset": base, "pair": m["symbol"], "quote": m["quote"], "listed": d0}
        if d0 <= (dt.date.fromisoformat(ex_start) + dt.timedelta(days=30)).isoformat():
            row["excluded"] = "开张首批"
        elif stock_suspect(base, d0):
            row["excluded"] = "疑似代币化股票"
        else:
            ref, ref_type, ref_ms = None, None, None
            hrs = ohlcv(m["symbol"], "1h", t0, 24)
            hrs = [x for x in hrs if t0 <= x[0] < t0 + DAY]
            h0 = hrs[0][0] if hrs else t0
            mins = ohlcv(m["symbol"], "1m", h0, 120)
            if mins and h0 <= mins[0][0] < h0 + 3600000 and len(mins) >= 15:
                ft = mins[0][0]
                c15 = next((x for x in mins if x[0] >= ft + 14 * 60000), None)
                if c15:
                    ref, ref_type, ref_ms = c15[4], "15m", c15[0]
            if ref is None and hrs:
                ref, ref_type, ref_ms = hrs[0][4], "1h", hrs[0][0] + 3600000 - 60000
            days = ohlcv(m["symbol"], "1d", t0, 100)
            conv = {}
            if m["quote"] == "BTC":   # BTC 计价换成美元
                conv = {iso_day(x[0]): c for x in days for c in [btc_usd.get(iso_day(x[0]))] if c}
            f = (lambda dd: conv.get(dd)) if m["quote"] == "BTC" else (lambda dd: 1.0)
            if ref and days:
                ref_usd = ref * (f(iso_day(ref_ms)) or 0)
                path = [(iso_day(x[0]), x[4] * (f(iso_day(x[0])) or 0)) for x in days]
                path = [p for p in path if p[1] > 0]
                if ref_usd > 0 and path:
                    row.update(ref_type=ref_type, ref_usd=round(ref_usd, 10), days=len(path))
                    b15 = LH.minute_close("BTCUSDT", ref_ms - ref_ms % 60000)
                    for w in LH.WINDOWS:
                        if len(path) > w:
                            row[f"r{w}"] = round(path[w][1] / ref_usd - 1, 4)
                            b1 = btc_usd.get(path[w][0])
                            if b15 and b1:
                                row[f"x{w}"] = round(row[f"r{w}"] - (b1 / b15 - 1), 4)
                    win = path[1:91]
                    if win:
                        hi = max(win, key=lambda p: p[1])
                        row["peak90"] = round(hi[1] / ref_usd - 1, 4)
                        row["peak90_day"] = path.index(hi)
            if "r7" not in row:
                row["excluded"] = "取不到起点价或日线"
        g, k = leg_at(d0), leg_known(d0)
        row.update(leg_dir=g and g["dir"], leg_regime=g and g["regime"], known_leg_dir=k and k["dir"],
                   known_leg_regime=k and k["regime"], l2_state=l2_at(d0), year=d0[:4])
        coins.append(row)
        if bi % 100 == 0:
            print("  ", bi, "/", len(bases), round((time.time() - t_start) / 60, 1), "分钟")
    ok = [r for r in coins if "excluded" not in r]
    groups = {}
    for name, keyf in (("全部", lambda r: "全部"), ("牛熊 × 涨跌腿（事后划分）", lambda r: f"{r['leg_regime']}·{r['leg_dir']}"),
                       ("当时已确认的腿", lambda r: f"{r['known_leg_regime']}·{r['known_leg_dir']}"),
                       ("L2 状态", lambda r: r["l2_state"]), ("年份", lambda r: r["year"])):
        sub = {}
        for r in ok:
            sub.setdefault(str(keyf(r)), []).append(r)
        groups[name] = {k: LH.summary(v) for k, v in sorted(sub.items())}
    out = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "exchange": exid, "exchange_first_day": ex_start,
           "survivorship": "只含现在还在交易的币（CCXT 列不出已下架的），回报偏高", "complete": len(coins) >= len(bases) * 0.95,
           "n": {"bases": len(bases), "coins": len(coins), "used": len(ok), "ref_15m": sum(1 for r in ok if r.get("ref_type") == "15m"),
                 "ref_1h": sum(1 for r in ok if r.get("ref_type") == "1h")},
           "groups": groups, "coins": coins}
    out["shard"] = shard
    out["complete"] = len(coins) >= len(items) * 0.95
    name = f"listing_history_{exid}" + (f"__{shard.replace('/', 'of')}" if shard else "")
    json.dump(out, open(os.path.join(LH.OUT, name + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    a = groups["全部"].get("全部") or {}
    print(exid, json.dumps(out["n"], ensure_ascii=False), "30天中位", (a.get("r30") or {}).get("p50"), "90天中位", (a.get("r90") or {}).get("p50"))


if __name__ == "__main__":
    main()
