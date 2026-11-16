#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测 OKX / Bitget 上币公告详情页正文 + 历史 1 分钟 K 线接口（只读，不写数据）。
在 Actions 上跑（沙盒连不上这些域名）。
"""
import json, re, sys, urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def text_of(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def body_after_title(html, n=1800):
    """跳过导航：从第二次出现标题（正文 h1）之后取一段。"""
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    title = (m.group(1).split("|")[0].strip() if m else "")
    t = text_of(html)
    idx = [x.start() for x in re.finditer(re.escape(title), t)] if title else []
    start = idx[1] if len(idx) > 1 else (idx[0] if idx else 0)
    return title, t[start:start + n]


def jget(url):
    try:
        return json.loads(get(url))
    except Exception as e:
        return {"error": str(e)[:200]}


def main():
    d = json.load(open("data/alpha/exch_announce.json", encoding="utf-8"))
    # --- OKX 正文
    okx = [v for v in d["items"].values() if v["exchange"] == "OKX" and v["kind"] == "spot"][:2]
    for v in okx:
        try:
            title, body = body_after_title(get(v["url"]))
            print("OKX 正文 ·", title, "\n   ", body[:1800])
        except Exception as e:
            print("OKX 取页失败", v["url"], str(e)[:120])
    # --- OKX 历史 1 分钟 K 线：GRVT 开盘 2026-07-30 03:00 UTC（pTime 1785380409238）
    ts = 1785380400000
    for inst in ("GRVT-USD", "GRVT-USDT"):
        j = jget(f"https://www.okx.com/api/v5/market/history-candles?instId={inst}&bar=1m&before={ts-1}&after={ts+100*60000}&limit=100")
        rows = j.get("data") or []
        print(f"OKX history-candles {inst}: code={j.get('code')} msg={j.get('msg') or j.get('error')} 条数={len(rows)}",
              "最早", rows[-1][:6] if rows else None, "最新", rows[0][:6] if rows else None)
    # --- Bitget：取 4 条各类公告原始字段 + 一条文章页
    j = jget("https://api.bitget.com/api/v2/public/annoucements?annType=coin_listings&language=en_US")
    rows = j.get("data") or []
    print("Bitget 公告条数", len(rows), "子类型", sorted({r.get("annSubType") for r in rows}))
    for r in rows[:1]:
        try:
            title, body = body_after_title(get(r["annUrl"]))
            print("Bitget 正文 ·", r["annTitle"], "\n   ", body[:1500])
        except Exception as e:
            print("Bitget 取页失败", r.get("annUrl"), str(e)[:160])
    # --- Bitget 历史 1 分钟 K 线（BTCUSDT 验证接口形态；同一时刻）
    for path in ("spot/market/history-candles", "spot/market/candles"):
        j = jget(f"https://api.bitget.com/api/v2/{path}?symbol=BTCUSDT&granularity=1min&startTime={ts}&endTime={ts+100*60000}&limit=100")
        rows = j.get("data") or []
        print(f"Bitget {path}: code={j.get('code')} msg={j.get('msg') or j.get('error')} 条数={len(rows)}",
              "首", rows[0][:6] if rows else None, "末", rows[-1][:6] if rows else None)


if __name__ == "__main__":
    sys.exit(main())
