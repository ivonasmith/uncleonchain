#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""币安上币后「不同开空位置」的历史读数（只是历史统计，不是操作建议；大叔 11-17 要的研究数据）。

输入 data/alpha/listing_history_binance.json（listing_history.py 的逐币结果，起点 = 开盘第 15 分钟收盘价）。
对每个进统计的币重取上线后 90 天日线（美元计），存逐日路径 data/alpha/listing_paths_binance.json（相对 15 分钟起点）。
开空位置（全部按日收盘价，不看日内）：
  E15 开盘 15 分钟价 / E60 开盘 1 小时价 / D0 首日收盘 / D7 第 7 天收盘 /
  U20 / U50 / U100 = 第一次收盘比 15 分钟价高 20% / 50% / 100% 的那天收盘（没触发的不算进该行，单列触发比例）。
每个位置看：开空后 30 天的涨跌（负 = 价格下跌）、30 天内价格对空单最不利的上冲幅度（只用日收盘，日内插针更高，实际风险比读数大）、
上冲超过 50% / 100% 的比例。按 BTC 牛熊 × 涨跌腿（事后划分）和「当时已确认的腿」分组，n < 20 标样本不足。
用法：python3 alpha/listing_short.py（要联网：data-api.binance.vision、data.binance.vision）
"""
import datetime as dt, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import listing_history as LH

OUT = LH.OUT
SRC = os.path.join(OUT, "listing_history_binance.json")
PATHS = os.path.join(OUT, "listing_paths_binance.json")
DST = os.path.join(OUT, "listing_short_stats.json")
H = 30   # 开空后看多少天


def to_ms(day):
    return int(dt.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def build_paths(coins):
    try:
        paths = json.load(open(PATHS, encoding="utf-8"))
    except Exception:
        paths = {}
    px = {q: LH.usd_closes(q + "USDT") for q in LH.CRYPTOQ}
    for i, r in enumerate(coins):
        if r["asset"] in paths or not r.get("ref15_usd"):
            continue
        rows = LH.daily_rows(r["pair"], to_ms(r["listed"]), 100)
        conv = (lambda d: 1.0) if r["quote"] in LH.USDQ else (lambda d, q=r["quote"]: px[q].get(d))
        p = []
        for x in rows[:91]:
            c = conv(LH.day(x[0]))
            p.append(round(x[4] * c / r["ref15_usd"], 4) if c else None)
        paths[r["asset"]] = p
        if i % 50 == 0:
            json.dump(paths, open(PATHS, "w"), separators=(",", ":"))
            print("  路径", i, "/", len(coins))
        time.sleep(0.03)
    json.dump(paths, open(PATHS, "w"), separators=(",", ":"))
    return paths


def entry_points(r, p):
    """→ {位置: 开空那天的下标 e 和开空价 v}；路径下标 0 = 上币当天收盘"""
    out = {"E15": (0, 1.0), "D0": (0, p[0]), "D7": (7, p[7]) if len(p) > 7 else None}
    if r.get("ref60_usd"):
        out["E60"] = (0, r["ref60_usd"] / r["ref15_usd"])
    for k, th in (("U20", 1.2), ("U50", 1.5), ("U100", 2.0)):
        e = next((d for d in range(1, len(p)) if p[d] is not None and p[d] >= th), None)
        out[k] = (e, p[e]) if e is not None else None
    return out


def one(p, e, v):
    """开空后 H 天：结果涨跌、期间最大上冲（对空单不利）"""
    if v is None or e + H >= len(p) or p[e + H] is None:
        return None
    seg = [x for x in p[e + 1:e + H + 1] if x is not None]
    if not seg:
        return None
    return {"ret": round(p[e + H] / v - 1, 4), "mae": round(max(seg) / v - 1, 4)}


def pct(xs, q):
    return LH.pct(xs, q)


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    coins = [r for r in d["coins"] if "excluded" not in r and r.get("ref15_usd")]
    paths = build_paths(coins)
    NAMES = {"E15": "开盘 15 分钟", "E60": "开盘 1 小时", "D0": "首日收盘", "D7": "第 7 天收盘",
             "U20": "收盘第一次比 15 分钟价高 20%", "U50": "收盘第一次高 50%", "U100": "收盘第一次高 100%"}
    res = {}
    for gname, keyf in (("全部", lambda r: "全部"), ("牛熊 × 涨跌腿（事后划分）", lambda r: f"{r.get('leg_regime')}·{r.get('leg_dir')}"),
                        ("当时已确认的腿", lambda r: f"{r.get('known_leg_regime')}·{r.get('known_leg_dir')}")):
        groups = {}
        for r in coins:
            groups.setdefault(keyf(r), []).append(r)
        res[gname] = {}
        for gk, rs in sorted(groups.items()):
            if "None" in gk:
                continue
            rows = {}
            for ek, label in NAMES.items():
                outs, trig = [], 0
                for r in rs:
                    p = paths.get(r["asset"]) or []
                    if len(p) < 40:
                        continue
                    ep = entry_points(r, p).get(ek)
                    if ep is None:
                        continue
                    trig += 1
                    o = one(p, *ep)
                    if o:
                        outs.append(o)
                n = len(outs)
                ret = [o["ret"] for o in outs]
                mae = [o["mae"] for o in outs]
                rows[ek] = {"label": label, "n": n, "triggered_share": round(trig / len(rs), 4) if rs else None,
                            "ret30_p50": pct(ret, .5), "ret30_p25": pct(ret, .25), "ret30_p75": pct(ret, .75),
                            "fell_share": round(sum(1 for x in ret if x < 0) / n, 4) if n else None,
                            "squeeze_p50": pct(mae, .5), "squeeze_p75": pct(mae, .75),
                            "squeeze_gt50": round(sum(1 for x in mae if x > .5) / n, 4) if n else None,
                            "squeeze_gt100": round(sum(1 for x in mae if x > 1) / n, 4) if n else None,
                            "level": "可看分布（n≥20）" if n >= 20 else "样本不足（n<20）"}
            res[gname][gk] = rows
    note = ("只是历史统计，不是操作建议。价格全部用日收盘（开盘 15 分钟 / 1 小时用分钟收盘）；上冲幅度只看日收盘，日内插针会更高，"
            "实际逼空风险比读数大；现货价格，不含合约资金费率、借币成本和能否借到；开空后看 30 天；「事后划分」的腿当时不知道，交易时能用的是「当时已确认的腿」。")
    json.dump({"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "horizon_days": H, "note": note, "groups": res},
              open(DST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    f = lambda x: "U" if x is None else f"{x:+.0%}"
    for gname, gs in res.items():
        print("==", gname)
        for gk, rows in gs.items():
            print("  ", gk)
            for ek, s in rows.items():
                print(f"     {s['label']:<16} n={s['n']:<4} 触发 {s['triggered_share']:.0%}  开空后30天中位 {f(s['ret30_p50'])}（P25 {f(s['ret30_p25'])} / P75 {f(s['ret30_p75'])}）"
                      f" 下跌比例 {s['fell_share'] if s['fell_share'] is None else format(s['fell_share'], '.0%')}"
                      f" | 上冲中位 {f(s['squeeze_p50'])} P75 {f(s['squeeze_p75'])} 上冲>50% {s['squeeze_gt50'] if s['squeeze_gt50'] is None else format(s['squeeze_gt50'], '.0%')}"
                      f" >100% {s['squeeze_gt100'] if s['squeeze_gt100'] is None else format(s['squeeze_gt100'], '.0%')} {s['level']}")


if __name__ == "__main__":
    main()
