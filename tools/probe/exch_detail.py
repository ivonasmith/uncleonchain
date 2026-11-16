#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测 OKX / Bitget 上币：开盘时间正则、历史 1 分钟 K 线可回溯多久、Bitget 翻页（只读，不写数据）。Actions 上跑。"""
import datetime as dt, json, re, sys, time, urllib.request

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


def okx_open(txt):
    """→ [(base, quote, open_ms)]"""
    out = []
    P = r"([A-Z0-9]{1,15}) ?/ ?(USDT|USDC|USD|EUR|BTC)"
    for m in re.finditer(P + r" (?:spot )?trading (?:will )?open(?:s)? at (?:([A-Z][a-z]{2,8} \d{1,2}, \d{4}) (\d{1,2}:\d{2})|(\d{1,2}:\d{2}) UTC on ([A-Z][a-z]{2,8} \d{1,2}, \d{4}))", txt):
        d, t = (m.group(3), m.group(4)) if m.group(3) else (m.group(6), m.group(5))
        fmt = "%b %d, %Y %H:%M" if len(d.split()[0]) <= 3 else "%B %d, %Y %H:%M"
        out.append((m.group(1), m.group(2), int(dt.datetime.strptime(f"{d} {t}", fmt).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)))
    for m in re.finditer(P + r"[^.]*? in our spot trading at ([A-Z][a-z]{2} \d{1,2}, \d{4} \d{1,2}:\d{2}) ?UTC", txt):
        out.append((m.group(1), m.group(2), int(dt.datetime.strptime(m.group(3), "%b %d, %Y %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)))
    return out


def main():
    d = json.load(open("data/alpha/exch_announce.json", encoding="utf-8"))
    okx = [v for v in d["items"].values() if v["exchange"] == "OKX" and v["kind"] == "spot"]
    for v in okx[:10]:
        try:
            txt = text_of(get(v["url"]))
        except Exception as e:
            print("OKX 取页失败", v["url"], str(e)[:80]); continue
        ev = okx_open(txt)
        print("OKX ·", v["title"][:70], "· 公告", v["announce_utc"], "→ 开盘", [(b, q, dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).strftime("%m-%d %H:%M")) for b, q, t in ev])
        for b, q, t in ev:
            if q != "USDT":
                continue
            j = jget(f"https://www.okx.com/api/v5/market/history-candles?instId={b}-USDT&bar=1m&before={t-1}&after={t+100*60000}&limit=100")
            rows = j.get("data") or []
            print(f"     {b}-USDT code={j.get('code')} msg={j.get('msg') or j.get('error')} 条数={len(rows)}",
                  "首根", (dt.datetime.fromtimestamp(int(rows[-1][0]) / 1000, dt.timezone.utc).strftime("%H:%M"), rows[-1][1:5]) if rows else None)
    # OKX 1 分钟历史回溯深度：BTC-USDT 在 N 天前
    now = int(time.time() * 1000)
    for days in (30, 60, 90, 120, 150, 200):
        t = now - days * 86400000
        j = jget(f"https://www.okx.com/api/v5/market/history-candles?instId=BTC-USDT&bar=1m&before={t-1}&after={t+30*60000}&limit=100")
        print(f"OKX 1m 回溯 {days} 天前: 条数={len(j.get('data') or [])} code={j.get('code')}")
    # Bitget：翻页参数
    base = "https://api.bitget.com/api/v2/public/annoucements?annType=coin_listings&language=en_US"
    for lim in (10, 20, 50, 100):
        j = jget(base + f"&limit={lim}")
        print(f"Bitget limit={lim}: code={j.get('code')} msg={j.get('msg') or j.get('error')} 条数={len(j.get('data') or [])}")
    j = jget(base + "&limit=10")
    rows = j.get("data") or []
    if rows:
        for pname in ("cursor", "beforeId", "pageNo"):
            val = rows[-1]["annId"] if pname != "pageNo" else 2
            j2 = jget(base + f"&limit=10&{pname}={val}")
            r2 = j2.get("data") or []
            print(f"Bitget {pname}: 条数={len(r2)} msg={j2.get('msg') or j2.get('error')} 首条", (r2[0]["annId"], r2[0]["annSubType"], r2[0]["annTitle"][:60]) if r2 else None)
        print("Bitget 第一页 annId 范围", rows[0]["annId"], rows[-1]["annId"])
    # Bitget 其它 annType 中是否有现货上币
    for t in ("coin_listings", "latest_news", "product_updates"):
        j = jget(f"https://api.bitget.com/api/v2/public/annoucements?annType={t}&language=en_US")
        rs = j.get("data") or []
        print(f"Bitget annType={t}: 条数={len(rs)} 子类型={sorted({r.get('annSubType') for r in rs})} 含spot标题:",
              [r["annTitle"][:70] for r in rs if re.search(r"\blist(s|ing)?\b", r["annTitle"], re.I) and "copy" not in r["annTitle"].lower() and "perpetual" not in r["annTitle"].lower()][:4])


if __name__ == "__main__":
    sys.exit(main())
