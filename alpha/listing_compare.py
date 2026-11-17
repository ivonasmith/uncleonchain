#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""各交易所「上币后买入」历史回报对比（只是历史统计，不是操作建议）。
读 data/alpha/listing_history_binance.json 和 listing_history_<id>.json → data/alpha/listing_compare.json。
公平比较：其它所只含现在还在交易的币（幸存者偏差），所以 Binance 同时给「全部（含已下架）」和「只看现在还在交易的」两行，
和其它所比只用后者。主口径中位数；「30 天赚钱比例」= 第 30 天收盘高于起点的币占比。
用法：python3 alpha/listing_compare.py（Binance「现在还在交易」要联网查 data-api 的 exchangeInfo）
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import listing_history as LH

OUT = LH.OUT


def stats(rows):
    s = LH.summary(rows)
    r30 = [r["r30"] for r in rows if r.get("r30") is not None]
    s["win30"] = round(sum(1 for x in r30 if x > 0) / len(r30), 4) if r30 else None
    return s


def compact(s):
    g = lambda k, q="p50": (s.get(k) or {}).get(q)
    return {"n": s["n"], "level": s["level"], "r7": g("r7"), "r30": g("r30"), "r90": g("r90"), "x30": g("x30"),
            "win30": s.get("win30"), "peak90": g("peak90"), "peak90_day": s.get("peak90_day_p50"), "r30_mean": g("r30", "mean")}


def table(rows):
    out = {"全部": compact(stats(rows))}
    by = {}
    for r in rows:
        by.setdefault(f"{r.get('leg_regime')}·{r.get('leg_dir')}", []).append(r)
    for k, v in sorted(by.items()):
        if "None" not in k:
            out[k] = compact(stats(v))
    return out


def main():
    res = {}
    bn = json.load(open(os.path.join(OUT, "listing_history_binance.json"), encoding="utf-8"))
    ok = [r for r in bn["coins"] if "excluded" not in r and r.get("r7") is not None]
    info = LH.get("https://data-api.binance.vision/api/v3/exchangeInfo")
    trading = {s["baseAsset"] for s in (info or {}).get("symbols", []) if s.get("status") == "TRADING"}
    res["Binance（全部，含已下架）"] = {"survivorship": False, **table(ok)}
    if trading:
        res["Binance（只看现在还在交易的）"] = {"survivorship": True, **table([r for r in ok if r["asset"] in trading])}
    for f in sorted(glob.glob(os.path.join(OUT, "listing_history_*.json"))):
        exid = os.path.basename(f)[len("listing_history_"):-5]
        if exid == "binance":
            continue
        d = json.load(open(f, encoding="utf-8"))
        if d.get("error"):
            res[exid] = {"error": d["error"]}
            continue
        rows = [r for r in d["coins"] if "excluded" not in r and r.get("r7") is not None]
        res[exid] = {"survivorship": True, "complete": d.get("complete"), "ref_15m": d["n"]["ref_15m"], "ref_1h": d["n"]["ref_1h"],
                     "first_day": d.get("exchange_first_day"), **table(rows)}
    note = ("只是历史统计，不是操作建议。起点 = 开盘第 15 分钟收盘价（没有 1 分钟历史的所用第一小时收盘，见 ref_1h）；中位数为主口径；"
            "win30 = 第 30 天收盘高于起点的比例；x30 = 30 天跑赢 BTC 多少（中位）；其它所只含现在还在交易的币，回报偏高，"
            "和 Binance 比请用「只看现在还在交易的」那一行；牛熊 × 涨跌腿是事后划分。")
    json.dump({"note": note, "exchanges": res}, open(os.path.join(OUT, "listing_compare.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    f = lambda x: "U" if x is None else f"{x:+.0%}"
    print("| 交易所 | n | 7天中位 | 30天中位 | 90天中位 | 30天赚钱比例 | 30天跑赢BTC中位 | 90天内最高中位 |")
    for k, v in res.items():
        if v.get("error"):
            print(f"| {k} | {v['error']} |")
            continue
        a = v["全部"]
        print(f"| {k} | {a['n']} | {f(a['r7'])} | {f(a['r30'])} | {f(a['r90'])} | {'U' if a['win30'] is None else format(a['win30'], '.0%')} | {f(a['x30'])} | {f(a['peak90'])} |")


if __name__ == "__main__":
    main()
