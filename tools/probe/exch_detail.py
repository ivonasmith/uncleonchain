#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bitget 公告接口沿 cursor 往前翻页：覆盖多久、有哪些子类型、有没有现货上币（只读，不写数据）。Actions 上跑。"""
import collections, datetime as dt, json, re, sys, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"}
BASE = "https://api.bitget.com/api/v2/public/annoucements?annType=coin_listings&language=en_US&limit=10"


def jget(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)[:160]}


def main():
    rows, cur, pages = [], None, 0
    while pages < 120:
        j = jget(BASE + (f"&cursor={cur}" if cur else ""))
        d = j.get("data") or []
        if not d:
            print("停在第", pages, "页：", j.get("msg") or j.get("error") or "无数据")
            break
        rows += d
        cur = d[-1]["annId"]
        pages += 1
        time.sleep(0.15)
    f = lambda r: dt.datetime.fromtimestamp(int(r["cTime"]) / 1000, dt.timezone.utc).strftime("%Y-%m-%d")
    print(f"共翻 {pages} 页、{len(rows)} 条；最新 {f(rows[0])}，最早 {f(rows[-1])}")
    print("子类型计数:", dict(collections.Counter(r["annSubType"] for r in rows)))
    byday = collections.Counter(f(r) for r in rows)
    print("每天条数(最近 8 天):", sorted(byday.items(), reverse=True)[:8])
    spot = [r for r in rows if r["annSubType"] not in ("copy_trading",) and not re.search(r"perpetual|futures|copy", r["annTitle"], re.I)]
    print(f"非跟单、非合约的公告 {len(spot)} 条：")
    for r in spot[:25]:
        print("  ", f(r), r["annSubType"], "|", r["annTitle"][:110])


if __name__ == "__main__":
    sys.exit(main())
