#!/usr/bin/env python3
"""核心选币观测台 · 评分模块历史回测（大叔 2026-11-14：评分「全部假设」要合理评估）。只用标准库。

问的问题：每个评分模块（R 收入趋势 / C 价值捕获 / V 估值 / D 价格×收入，及合计）在某天打出的分数，
          能不能区分之后 30 / 60 / 90 天谁跑赢同批币的中位数？
做法（判定标准写在跑之前，跑完不改）：
  样本  DefiLlama 有协议收入、币安有 USDT 现货的代币；近一年协议收入 ≥ 300 万美元；按代币合并（母协议口径）。
        幸存者偏差：只能拿到今天还在的协议和币，已经死掉的不在样本里——结果偏乐观。
  时点  每月 1 日（只用当天之前的数据：收入截至前一天，价格用前一天收盘）。R / C / D 从 2023-03 起；
        V 要历史市值，CoinGecko 免费接口只给近 365 天，所以 V 只有近一年。
  结果  之后 h 天收益 − 同一时点全体样本收益中位数（超额，h = 30 / 60 / 90）。
  指标  每个时点算 Spearman 秩相关 IC，取平均、t 值（均值 / 标准差 × √时点数）、IC>0 的比例；
        同时按网站上 0–3 分档看各档平均超额。60 / 90 天的时点互相重叠，t 值偏高，只作参考。
  判定  已验证·方向：30 天和 60 天平均 IC 都 > 0，且 30 天 t ≥ 2；
        已证伪：30 天平均 IC < 0 且 t ≤ −1；
        其余：未通过（方向对但不显著，或方向反但不显著）。
输出：data/core/score_backtest.json（网站口径页读）+ core/review/score_backtest_detail.json（复核用明细）。
用法：python3 core/score_backtest.py [--max N]
"""
import json, math, os, statistics as st, sys, time, urllib.parse
import datetime as dt
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core_daily as C   # noqa: E402  复用取数函数与评分口径

ROOT = C.ROOT
OUT = os.path.join(ROOT, "data", "core", "score_backtest.json")
DETAIL = os.path.join(HERE, "review", "score_backtest_detail.json")
CACHE = os.path.join(C.CACHE, "bt")
START = "2023-03-01"
MIN_REV_1Y = 3_000_000
HS = (30, 60, 90)
SKIP_CAT = {"CEX", "Chain", "Bridge", "Stablecoin Issuer", "Services"}
STABLES = C.EXCLUDE | {"USDT", "BTC", "ETH", "BNB", "WBTC", "STETH"}


def cached(name, fn):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, name + ".json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 20 * 3600:
        return json.load(open(p))
    v = fn()
    json.dump(v, open(p, "w"))
    return v


def universe(maxn):
    protos = C.get(f"{C.LLAMA}/protocols")
    ov = C.get(f"{C.LLAMA}/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue")
    y1 = {x["slug"]: x.get("total1y") or 0 for x in ov["protocols"] if x.get("slug")}
    spot = set(C.spot_universe())
    by = {}
    for p in protos:
        sy = (p.get("symbol") or "").upper()
        if not sy or sy == "-" or sy in STABLES or sy not in spot or p.get("category") in SKIP_CAT:
            continue
        slug = (p.get("parentProtocol") or "").replace("parent#", "") or p["slug"]
        e = by.setdefault(sy, {"sym": sy, "slug": slug, "gecko": p.get("gecko_id"), "rev1y": 0, "name": p["name"]})
        e["rev1y"] += y1.get(p["slug"], 0)
        if p.get("gecko_id") and not e["gecko"]:
            e["gecko"] = p["gecko_id"]
    xs = sorted((e for e in by.values() if e["rev1y"] >= MIN_REV_1Y), key=lambda e: -e["rev1y"])
    return xs[:maxn]


def fees(slug):
    out, meta = {}, {}
    for k, dtp in (("fees", "dailyFees"), ("revenue", "dailyRevenue"), ("holders", "dailyHoldersRevenue")):
        d = C.get(f"{C.LLAMA}/summary/fees/{slug}?dataType={dtp}&excludeTotalDataChartBreakdown=true") or {}
        meta = meta or {"gecko": d.get("gecko_id"), "symbol": (d.get("symbol") or "").upper(), "name": d.get("name")}
        out[k] = {dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"): v for t, v in (d.get("totalDataChart") or [])
                  if dt.datetime.fromtimestamp(t, dt.timezone.utc).date() < C.TODAY and v is not None}
    out["meta"] = meta
    return out


def prices(sym):
    rows, cur = {}, int(dt.datetime(2022, 10, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    while True:
        d = C.spot_get(f"/api/v3/klines?symbol={urllib.parse.quote(sym)}USDT&interval=1d&startTime={cur}&limit=1000")
        if not d:
            break
        for k in d:
            rows[C.D(k[0])] = float(k[4])
        cur = d[-1][0] + 86400000
        if len(d) < 1000:
            break
    return {k: v for k, v in rows.items() if k < C.TODAY.isoformat()}


def mcaps(gid):
    for i in range(4):
        try:
            d = C.get(f"{C.CG}/coins/{gid}/market_chart?vs_currency=usd&days=365&interval=daily", tries=1)
            return {dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).strftime("%Y-%m-%d"): v for t, v in (d or {}).get("market_caps") or [] if v}
        except Exception:  # noqa
            time.sleep(20 * (i + 1))
    return {}


def day(d, k):
    return (dt.date.fromisoformat(d) + dt.timedelta(days=k)).isoformat()


def window(ser, end, n):
    """end 之前（不含）n 天的值列表，缺的日子当 0（DefiLlama 缺数据多半是那天没有收入），要求 end 前有 ≥ n 天历史。"""
    if not ser:
        return None
    first = min(ser)
    if first > day(end, -n):
        return None
    return [ser.get(day(end, -i), 0) for i in range(n, 0, -1)]


def signals(f, px, mc, t):
    """t 时点（只用 t 之前的数据）的各模块原始值与 0–3 分。"""
    r60, f30, h30 = window(f["revenue"], t, 60), window(f["fees"], t, 30), window(f["holders"], t, 30)
    p0, p30 = px.get(day(t, -1)), px.get(day(t, -31))
    if not r60 or p0 is None:
        return None
    s30, p30s = sum(r60[-30:]), sum(r60[:30])
    if s30 <= 0:
        return None
    a7, a30 = sum(r60[-7:]) / 7, s30 / 30
    d7v30 = (a7 / a30 - 1) * 100
    mom = (s30 / p30s - 1) * 100 if p30s > 0 else None
    o = {"px": p0}
    if mom is not None:
        w = min(d7v30, mom)
        o["R"] = (w, C.band(w, 10, -10, -30))
    hs = (sum(h30) / s30 * 100) if h30 else None
    if hs is not None:
        o["C"] = (hs, 3 if hs >= 50 else 2 if hs >= 20 else 1 if hs > 0 else 0)
    m = mc.get(day(t, -1)) if mc else None
    if m and h30 is not None:
        hr = sum(h30) * 365 / 30
        if hr > 0:
            x = m / hr
            o["V"] = (-math.log(x), 3 if x < 15 else 2 if x < 30 else 1 if x < 60 else 0)
        else:
            o["V"] = (None, 0)
    if mom is not None and p30:
        g = mom - (p0 / p30 - 1) * 100
        o["D"] = (g, 3 if g >= 20 else 2 if g >= -20 else 1 if g >= -50 else 0)
    sc = [o[k][1] for k in ("R", "C", "V", "D") if k in o]
    if len(sc) >= 3:
        o["T"] = (sum(sc) / (3 * len(sc)) * 100, None)
    return o


def spearman(a, b):
    def rk(x):
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
    ra, rb = rk(a), rk(b)
    ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else None


def main():
    maxn = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 80
    uni = cached("universe", lambda: universe(maxn))
    C.log(f"回测样本 {len(uni)} 个代币")
    data = {}

    def job(e):
        try:
            return e["sym"], {"f": fees(e["slug"]), "px": prices(e["sym"])}
        except Exception as ex:  # noqa
            return e["sym"], ex
    raw = cached("raw2", lambda: {k: v for k, v in ThreadPoolExecutor(6).map(job, uni) if not isinstance(v, Exception)})
    # 身份核对（同大叔轮动研究的做法）：用母协议的 gecko_id，CoinGecko 现价和币安最近收盘差 > 5% = 同名不同币，剔除
    dropped = {}
    for e in uni:
        r = raw.get(e["sym"])
        if not r:
            continue
        gid = (r["f"].get("meta") or {}).get("gecko")
        if not gid or (r["f"]["meta"].get("symbol") and r["f"]["meta"]["symbol"] != e["sym"]):
            dropped[e["sym"]] = "母协议没有 gecko_id 或代币符号不一致"
            raw.pop(e["sym"])
            continue
        e["gecko"] = gid
    ids = ",".join(e["gecko"] for e in uni if e["sym"] in raw)
    cg = {x["id"]: x.get("current_price") for x in (C.get(f"{C.CG}/coins/markets?vs_currency=usd&ids={ids}&per_page=250") or [])}
    for e in uni:
        r = raw.get(e["sym"])
        if not r:
            continue
        bp = r["px"][max(r["px"])] if r["px"] else None
        cp = cg.get(e["gecko"])
        if not bp or not cp or abs(cp / bp - 1) > 0.05:
            dropped[e["sym"]] = f"币安收盘 {bp} 对 CoinGecko {cp}（{e['gecko']}），疑似同名不同币"
            raw.pop(e["sym"])
    mc = cached("mcap2", lambda: {e["sym"]: (time.sleep(3), mcaps(e["gecko"]))[1] for e in uni if e["sym"] in raw})
    for e in uni:
        if e["sym"] in raw:
            data[e["sym"]] = dict(raw[e["sym"]], mc=mc.get(e["sym"]) or {})
    C.log(f"身份核对后 {len(data)} 个；剔除：{dropped}")
    last = max(max(d["px"]) for d in data.values() if d["px"])
    dates = []
    d = dt.date.fromisoformat(START)
    while d.isoformat() <= last:
        dates.append(d.isoformat())
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    mods = ("R", "C", "V", "D", "T")
    res = {m: {h: {"ic": [], "bands": {}, "spread": []} for h in HS} for m in mods}
    detail = []
    for t in dates:
        sig = {s: signals(x["f"], x["px"], x["mc"], t) for s, x in data.items()}
        sig = {s: v for s, v in sig.items() if v}
        for h in HS:
            fw = {}
            for s, v in sig.items():
                p1 = data[s]["px"].get(day(t, h - 1))
                if p1:
                    fw[s] = (p1 / v["px"] - 1) * 100
            if len(fw) < 12:
                continue
            med = st.median(fw.values())
            ex = {s: r - med for s, r in fw.items()}
            for m in mods:
                xs = [(sig[s][m][0], sig[s][m][1], ex[s]) for s in ex if m in sig[s] and sig[s][m][0] is not None]
                if len(xs) < 10:
                    continue
                ic = spearman([a for a, _, _ in xs], [c for _, _, c in xs])
                if ic is not None:
                    res[m][h]["ic"].append((t, ic, len(xs)))
                xs.sort(key=lambda z: z[0])
                k = len(xs) // 3
                res[m][h]["spread"].append(st.mean(c for _, _, c in xs[-k:]) - st.mean(c for _, _, c in xs[:k]))
                for _, b, c in xs:
                    if b is not None:
                        res[m][h]["bands"].setdefault(b, []).append(c)
            if h == 30:
                detail.append({"date": t, "n": len(fw), "rows": {s: {"fwd30_ex": round(ex[s], 2), **{m: [None if sig[s][m][0] is None else round(sig[s][m][0], 3), sig[s][m][1]]
                                                                        for m in mods if m in sig[s]}} for s in ex}})
    summ = {}
    for m in mods:
        summ[m] = {}
        for h in HS:
            ics = [x[1] for x in res[m][h]["ic"]]
            if len(ics) < 3:
                summ[m][h] = None
                continue
            mu, sd = st.mean(ics), (st.stdev(ics) if len(ics) > 1 else 0)
            summ[m][h] = {"n_dates": len(ics), "from": res[m][h]["ic"][0][0], "to": res[m][h]["ic"][-1][0],
                          "avg_n": round(st.mean(x[2] for x in res[m][h]["ic"]), 1), "ic": round(mu, 3), "t": round(mu / sd * math.sqrt(len(ics)), 2) if sd else None,
                          "hit": round(sum(1 for x in ics if x > 0) / len(ics) * 100), "spread": round(st.mean(res[m][h]["spread"]), 2),
                          "bands": {str(b): {"n": len(v), "ex": round(st.mean(v), 2)} for b, v in sorted(res[m][h]["bands"].items())}}
        a, b = summ[m].get(30), summ[m].get(60)
        if not a:
            v = "样本不足"
        elif a["ic"] > 0 and b and b["ic"] > 0 and (a["t"] or 0) >= 2:
            v = "已验证·方向"
        elif a["ic"] < 0 and (a["t"] or 0) <= -1:
            v = "已证伪"
        else:
            v = "未通过"
        summ[m]["verdict"] = v
    out = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "n_coins": len(data), "coins": sorted(data), "dropped": dropped,
           "dates": [dates[0], dates[-1]], "rules": __doc__.split("做法")[1].split("输出")[0].strip(), "modules": summ,
           "untested": {"B": "业务量（DEX 成交额 / TVL）历史取数量大，下一轮做", "S": "解锁只有人工登记的当前值，没有历史"}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(C.clean(out), open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.makedirs(os.path.dirname(DETAIL), exist_ok=True)
    json.dump(C.clean(detail), open(DETAIL, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    for m in mods:
        print(m, summ[m]["verdict"], {h: (summ[m][h] or {}).get("ic") for h in HS}, {h: (summ[m][h] or {}).get("t") for h in HS},
              (summ[m][30] or {}).get("n_dates"), (summ[m][30] or {}).get("bands"))


if __name__ == "__main__":
    main()
