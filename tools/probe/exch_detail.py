#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测 OKX / Bitget 上币公告正文 + 历史 1 分钟 K 线（只读，不写数据）。在 Actions 上跑。"""
import datetime as dt, json, re, sys, urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def jget(url):
    try:
        return json.loads(get(url))
    except Exception as e:
        return {"error": str(e)[:200]}


def text_of(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def body_after_title(html, n=900):
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    title = (m.group(1).split("|")[0].strip() if m else "")
    t = text_of(html)
    idx = [x.start() for x in re.finditer(re.escape(title), t)] if title else []
    start = idx[1] if len(idx) > 1 else (idx[0] if idx else 0)
    return t[start:start + n]


def okx_time(txt):
    m = re.search(r"([A-Z][a-z]{2} \d{1,2}, \d{4} \d{1,2}:\d{2}) ?UTC", txt)
    return int(dt.datetime.strptime(m.group(1), "%b %d, %Y %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000) if m else None


def main():
    d = json.load(open("data/alpha/exch_announce.json", encoding="utf-8"))
    okx = [v for v in d["items"].values() if v["exchange"] == "OKX"]
    # --- OKX：各种标题模板各取 1 条，打印正文并试 K 线
    seen_tpl = set()
    for v in okx:
        tpl = re.sub(r"[A-Z0-9]{2,}", "X", v["title"])[:60]
        if tpl in seen_tpl or len(seen_tpl) >= 5:
            continue
        seen_tpl.add(tpl)
        try:
            body = body_after_title(get(v["url"]))
        except Exception as e:
            print("OKX 取页失败", v["url"], str(e)[:100]); continue
        print("OKX ·", v["title"], "· pTime", v["announce_utc"], "\n   ", body[:700].split("OKX team")[0])
        t = okx_time(body)
        m = re.search(r"\b([A-Z0-9]{2,15}) ?/ ?(USDT|USD)\b", v["title"] + " " + body)
        if t and m and m.group(2) == "USDT":
            inst = f"{m.group(1)}-USDT"
            j = jget(f"https://www.okx.com/api/v5/market/history-candles?instId={inst}&bar=1m&before={t-1}&after={t+100*60000}&limit=100")
            rows = j.get("data") or []
            print(f"   → {inst} 开盘 {dt.datetime.fromtimestamp(t/1000, dt.timezone.utc):%Y-%m-%d %H:%M} UTC · history-candles code={j.get('code')} msg={j.get('msg') or j.get('error')} 条数={len(rows)}",
                  "首根", rows[-1][:6] if rows else None)
    # --- Bitget：翻页 + 子类型 + 现货上币样本
    base = "https://api.bitget.com/api/v2/public/annoucements?annType=coin_listings&language=en_US"
    j = jget(base + "&limit=100")
    rows = j.get("data") or []
    print("Bitget limit=100 条数", len(rows), "子类型", {s: sum(1 for r in rows if r.get("annSubType") == s) for s in {r.get("annSubType") for r in rows}})
    if rows:
        j2 = jget(base + f"&limit=100&cursor={rows[-1]['annId']}")
        r2 = j2.get("data") or []
        print("Bitget cursor 翻页 条数", len(r2), j2.get("msg") or j2.get("error"), "首条", (r2[0]["annTitle"], r2[0]["cTime"]) if r2 else None)
    spot = [r for r in rows if re.search(r"\bspot\b|will list|to list", r.get("annTitle", ""), re.I) and "copy" not in r.get("annTitle", "").lower()]
    print("Bitget 疑似现货上币标题:", [(r["annSubType"], r["annTitle"][:80]) for r in spot[:8]])
    for r in spot[:1]:
        try:
            print("Bitget 正文 ·", r["annTitle"], "\n   ", body_after_title(get(r["annUrl"]), 1400))
        except Exception as e:
            print("Bitget 取页失败", str(e)[:100])


if __name__ == "__main__":
    sys.exit(main())
