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


import collections, re

BATCH_N = 8   # 同一家所同一天上线 ≥ 8 个币：数据起点堆积（OKX 2020-01-01）、代币化股票批量（OKX X 开头、Gate G 结尾）、补上一批老币（Crypto.com 2022-10-11），都不是新币上线
STOCK_RULES = {"okx": r"X[A-Z]{2,6}", "gate": r"[A-Z]{2,6}G"}   # 2025-06 起上线的才套用
INCOMPLETE = {"bitget": "没跑完（时间预算内只做了一部分币）", "gate": "1 分钟 / 1 小时历史只回溯约一年，只剩 2025 年起上线的币，起点用 1 小时价",
              "bingx": "K 线只回溯到 2025-11，只剩近一年的币，起点用 1 小时价"}


def clean(rows, exid):
    """→ (保留的, 剔除计数)"""
    day_n = collections.Counter(r["listed"] for r in rows)
    keep, drop = [], collections.Counter()
    pat = STOCK_RULES.get(exid)
    for r in rows:
        if day_n[r["listed"]] >= BATCH_N:
            drop["批量上线日（同日 ≥ 8 个）"] += 1
        elif pat and r["listed"] >= "2025-06-01" and re.fullmatch(pat, r["asset"]):
            drop["代币化股票（代码规律）"] += 1
        else:
            keep.append(r)
    return keep, dict(drop)


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
    ok, bdrop = clean(ok, "binance")
    res["Binance（全部，含已下架）"] = {"survivorship": False, "dropped": bdrop, **table(ok)}
    if trading:
        res["Binance（只看现在还在交易的）"] = {"survivorship": True, **table([r for r in ok if r["asset"] in trading])}
    merged = {}
    files = sorted(glob.glob(os.path.join(OUT, "listing_history_*.json")), key=lambda p: ("__" not in p, p))   # 分片文件先读
    for f in files:
        exid = os.path.basename(f)[len("listing_history_"):-5]
        if exid == "binance":
            continue
        d = json.load(open(f, encoding="utf-8"))
        if "__" in exid:   # 分片文件：同一所合并（有分片就不用整所的旧文件）
            exid = exid.split("__")[0]
            m = merged.setdefault(exid, {"coins": [], "complete": True, "exchange_first_day": d.get("exchange_first_day"), "n": {}, "_shards": 0})
            if d.get("error"):
                m["error"] = d["error"]
                continue
            m["coins"] += d["coins"]; m["complete"] = m["complete"] and d.get("complete"); m["_shards"] += 1
            continue
        if exid not in merged:   # 有分片就只用分片，整所的旧文件不用
            merged[exid] = d
    for exid, d in sorted(merged.items()):
        if d.get("error"):
            res[exid] = {"error": d["error"]}
            continue
        rows = [r for r in d["coins"] if "excluded" not in r and r.get("r7") is not None]
        rows, drop = clean(rows, exid)
        res[exid] = {"survivorship": exid != "bybit", "complete": d.get("complete"), "incomplete_note": INCOMPLETE.get(exid),
                     "ref_15m": sum(1 for r in rows if str(r.get("ref_type", "")).startswith("15m")), "ref_1h": sum(1 for r in rows if r.get("ref_type") == "1h"),
                     "first_day": d.get("exchange_first_day"), "dropped": drop, **table(rows)}
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
        k = k + ("（不完整）" if v.get("incomplete_note") else "")
        print(f"| {k} | {a['n']} | {f(a['r7'])} | {f(a['r30'])} | {f(a['r90'])} | {'U' if a['win30'] is None else format(a['win30'], '.0%')} | {f(a['x30'])} | {f(a['peak90'])} |")


if __name__ == "__main__":
    main()
