#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""其它交易所的上币事件（OKX）：公告 → 计划开盘 → 首笔成交 → 30 分钟 / 1 / 4 / 24 小时窗口，并进 data/alpha/listings.json。

输入 data/alpha/exch_announce.json（alpha/exch_announce.py 每天抓的公告流水）；窗口算法复用 listings.windows，口径同 Binance：
参考价 = 第一根 1 分钟 K 线开盘价，事后读数，不是可成交价；窗口算满 24 小时后冻结。事件只追加（key = okx:<公告 slug>:<BASE><QUOTE>）。

OKX（2026-11-16 在 Actions 上实测）：
  · 公告 pTime 是发布时间，不是开盘时间；开盘时间从公告正文取（alpha/okx_parse.py）。
  · 第一根 1 分钟 K 线就是开盘那一分钟；官方 /api/v5/market/history-candles 的 1 分钟数据至少能回溯 5 个月，每次最多 100 根（24 小时 = 15 次请求）。
  · 「OKX will launch X/USD」是 OKX US 的 USD 交易对，全球站公开接口没有这个交易对（返回 51001），只记公告和开盘时间，窗口不算（venue = okx_us）。
Bitget：公告接口每页只有 10 条、约覆盖 12 小时，近期全是跟单和 TradFi 永续，没有现货上币，目前不收事件；Kraken 只有「已可交易」博客，没有计划开盘时间，
公开 OHLC 又只给最近 720 根，窗口算不了，只留公告层。
用法：python3 alpha/listings_x.py
"""
import datetime as dt, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import listings as L            # get / iso / windows / PATH
import okx_parse                # 开盘时间与交易对解析

ROOT = os.path.dirname(HERE)
ANN = os.path.join(os.environ.get("LP_DATA", os.path.join(ROOT, "data")), "alpha", "exch_announce.json")
OKX_K = "https://www.okx.com/api/v5/market/history-candles?instId={inst}&bar=1m&before={b}&after={a}&limit=100"
HTML_UA = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"}
SKIP = re.compile(r"delist|suspend|maintenance|rebrand|copy trad", re.I)   # 注意别加 convert：「list RE … and convert pre-market futures」是真实上币


def page_text(url):
    import urllib.request
    req = urllib.request.Request(url, headers=HTML_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def okx_candles(inst, t0, now_ms):
    """从开盘分钟起 24 小时的 1 分钟 K 线（OKX 每次最多 100 根，降序返回）→ [(open_ms, o, h, l, c, quote_vol)] 升序"""
    rows = {}
    for k in range(0, 1441, 100):
        a = t0 + k * 60000
        if a > now_ms:
            break
        j = L.get(OKX_K.format(inst=inst, b=a - 1, a=a + 100 * 60000)) or {}
        for x in j.get("data") or []:
            rows[int(x[0])] = (int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7]))
        time.sleep(0.15)
    return [rows[k] for k in sorted(rows) if k >= t0]


def run_okx(E, A, ann, now, status):
    now_ms = int(now.timestamp() * 1000)
    first = not any(k.startswith("okx:") for k in E)
    seen_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    # 1) 公告正文 → 事件（每篇只解析一次；取页失败下次再来）
    for key, a in ann.items():
        if a.get("exchange") != "OKX" or SKIP.search(a["title"]):
            continue
        aid = "okx:" + key.split(":", 1)[1]
        if aid in A:
            continue
        try:
            evs = okx_parse.parse_open(page_text(a["url"]))
        except Exception as e:
            status["okx_page_fail"] += 1
            print("OKX 取页失败", a["url"], str(e)[:80])
            continue
        A[aid] = {"title": a["title"], "n": len(evs)}
        for base, quote, t, venue in evs:
            E[f"{aid}:{base}{quote}"] = {
                "exchange": "OKX", "asset": base, "pair": base + quote, "quote": quote, "market": "现货", "premarket": False,
                "title": a["title"], "url": a["url"], "announce_utc": a["announce_utc"], "revision_utc": None,
                "planned_open_utc": L.iso(t), "first_seen_utc": seen_ts, "baseline": first, "venue": venue, "w": None,
                "inst": f"{base}-{quote}", "primary": venue == "okx",
                "w_note": None if venue == "okx" else "OKX US 的 USD 交易对：全球站公开 K 线接口没有这个交易对，窗口不算",
            }
        time.sleep(0.2)
    # 2) 首笔成交与窗口（没算满 24 小时的都重试）
    for k, e in E.items():
        if e.get("exchange") != "OKX" or e.get("venue") != "okx" or (e.get("w") or {}).get("complete"):
            continue
        t = int(dt.datetime.strptime(e["planned_open_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        if t > now_ms:
            continue
        if now_ms - t > 30 * 86400000 and e.get("tries", 0) >= 3:
            continue
        rows = okx_candles(e["inst"], t, now_ms)
        w = L.windows(rows) if rows else None
        e["tries"] = e.get("tries", 0) + 1
        if w:
            w["lag_min"] = int((dt.datetime.strptime(w["first_trade_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp() * 1000 - t) / 60000)
            e["w"] = w
        else:
            status["okx_kline_fail"] += 1


def main():
    now = dt.datetime.now(dt.timezone.utc)
    try:
        ann = json.load(open(ANN, encoding="utf-8"))["items"]
    except Exception as e:
        print("读不到公告流水：", e)
        return
    try:
        store = json.load(open(L.PATH, encoding="utf-8"))
    except Exception:
        store = {"events": {}, "articles": {}}
    E, A = store.setdefault("events", {}), store.setdefault("articles", {})
    status = {"okx_page_fail": 0, "okx_kline_fail": 0}
    run_okx(E, A, ann, now, status)
    ok = [e for e in E.values() if e.get("exchange") == "OKX"]
    store["exchanges"] = sorted({"Binance"} | {e["exchange"] for e in E.values() if e.get("exchange")})
    store["by_exchange"] = {x: {"events": sum(1 for e in E.values() if e.get("exchange", "Binance") == x),
                                "with_windows": sum(1 for e in E.values() if e.get("exchange", "Binance") == x and (e.get("w") or {}).get("complete"))}
                            for x in store["exchanges"]}
    store["x_status"] = {**status, "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    store["note"] = "窗口参考价 = 第一根 1 分钟 K 线开盘价，是事后读数，不是可成交价；revision_utc 取不到记 null；OKX 的 USD 对是 OKX US，不算窗口；Bitget / Kraken 只有公告层"
    json.dump(store, open(L.PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("其它所上币事件：", json.dumps(store["by_exchange"], ensure_ascii=False), json.dumps(status, ensure_ascii=False))
    for e in ok[:40]:
        w = e.get("w") or {}
        print(" ", e["pair"], e["venue"], "开盘", e["planned_open_utc"], "首笔", w.get("first_trade_utc"), "滞后", w.get("lag_min"),
              "30m", w.get("m30"), "1h", w.get("h1"), "4h", w.get("h4"), "24h", w.get("h24"), "完整", w.get("complete"))


if __name__ == "__main__":
    main()
