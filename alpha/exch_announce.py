#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交易所上币公告框架：大叔列的 10 家，每家一个来源状态 + 公告流水。

Binance 的完整事件（计划开盘 / 首笔成交 / 窗口）在 alpha/listings.py；这里管其它所的「公告」这一层：
标题、链接、公告时间（原样 UTC）、首次抓到时间（= 发现延迟）、粗分类（现货 / 合约 / 其它）和标题里的代码。
计划开盘时间、交易对、K 线窗口等每家的正文解析接好后再进 listings 事件库。

来源状态（11-16 在 GitHub Actions 美国机房实测）：
  官网接口通：OKX、Bitget、Kraken（RSS）
  官网被拦：Bybit（CloudFront 按国家）、Upbit / Bithumb / Coinbase（Cloudflare 人机验证）、Gate / MEXC（Access Denied）
  被拦的走官方 X 账号（X 读取接口，按次付费，repo secret X_BEARER_TOKEN）；账号用户名核实后写进 alpha/exch_sources.json 才启用。

输出 data/alpha/exch_announce.json：sources（每家状态）+ items（只追加）。首跑为基线（baseline=true，不算「新发现」）。
"""
import datetime as dt, json, os, re, sys, time, urllib.error, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(os.environ.get("LP_DATA", os.path.join(ROOT, "data")), "alpha")
PATH = os.path.join(OUT, "exch_announce.json")
CONF = os.path.join(HERE, "exch_sources.json")
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json,application/xml,text/html,*/*", "Accept-Language": "en-US"}


def http(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def f_okx(c):
    out = []
    for p in range(1, int(c.get("pages", 2)) + 1):
        d = json.loads(http(f"https://www.okx.com/api/v5/support/announcements?annType=announcements-new-listings&page={p}"))
        for a in (d.get("data") or [{}])[0].get("details") or []:
            out.append({"id": a["url"].rstrip("/").rsplit("/", 1)[-1], "title": a["title"], "url": a["url"], "announce_utc": iso(int(a["pTime"]) / 1000)})
    return out


def f_bitget(c):
    d = json.loads(http("https://api.bitget.com/api/v2/public/annoucements?annType=coin_listings&language=en_US"))
    return [{"id": str(a["annId"]), "title": a["annTitle"], "url": a.get("annUrl"), "announce_utc": iso(int(a["cTime"]) / 1000), "sub": a.get("annSubType")} for a in d.get("data") or []]


def f_kraken(c):
    root = ET.fromstring(http("https://blog.kraken.com/category/product/asset-listings/feed"))
    out = []
    for it in root.iter("item"):
        link = (it.findtext("link") or "").strip()
        out.append({"id": link.rstrip("/").rsplit("/", 1)[-1], "title": (it.findtext("title") or "").strip(), "url": link,
                    "announce_utc": parsedate_to_datetime(it.findtext("pubDate")).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    return out


def f_x(c):
    """官方 X 账号最近的帖子（只留像上币的）。按次付费：每家每次 1 个请求、最多 max_results 条。"""
    tok = os.environ.get("X_BEARER_TOKEN", "").strip()
    if not tok:
        raise RuntimeError("没有 X_BEARER_TOKEN")
    if not c.get("x_user_id"):
        raise RuntimeError("X 账号还没核实（exch_sources.json 里没有 x_user_id）")
    n = int(c.get("x_max", 20))
    d = json.loads(http(f"https://api.x.com/2/users/{c['x_user_id']}/tweets?max_results={n}&tweet.fields=created_at&exclude=retweets,replies", {"Authorization": f"Bearer {tok}"}))
    keep = re.compile(c.get("x_keep") or r"list|listing|will launch|new pair|上线|상장|마켓 추가", re.I)
    out = []
    for t in d.get("data") or []:
        if keep.search(t["text"]):
            out.append({"id": t["id"], "title": re.sub(r"\s+", " ", t["text"])[:280], "url": f"https://x.com/{c['x_handle'].lstrip('@')}/status/{t['id']}",
                        "announce_utc": t["created_at"][:19] + "Z"})
    return out


FETCH = {"okx": f_okx, "bitget": f_bitget, "kraken": f_kraken, "x": f_x}
SPOT = re.compile(r"\blist(s|ing|ed)?\b|spot|available for trading|market support|마켓|상장|trading (starts|opens|is live)|now available", re.I)
PERP = re.compile(r"perp|futures|contract|swap|margin", re.I)
DROPT = re.compile(r"delist|remov|suspend|maintenance|migration|rebrand|stock|TradFi|pre-ipo|index|copy trad|跟单|convert|earn|loan", re.I)


def kind(title):
    if DROPT.search(title):
        return "other"
    if PERP.search(title):
        return "perp"
    if SPOT.search(title):
        return "spot"
    return "other"


def assets(title):
    xs = [m[0] for m in re.findall(r"\b([A-Z0-9]{2,12})/(USDT|USDC|USD|EUR|KRW|BTC)\b", title)] + re.findall(r"^([A-Z0-9]{2,12}) is available", title) + re.findall(r"\(([A-Z0-9]{2,12})\)", title) + re.findall(r"\$([A-Z0-9]{2,12})\b", title) + [m[:-4] for m in re.findall(r"\b([A-Z0-9]{2,12}USDT)\b", title)]
    return sorted(set(xs))[:8]


def main():
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conf = json.load(open(CONF, encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    try:
        store = json.load(open(PATH, encoding="utf-8"))
    except Exception:
        store = {"items": {}, "sources": {}}
    items, src = store["items"], {}
    only = sys.argv[1:]   # 可只跑指定的所
    for ex in conf["exchanges"]:
        name, via = ex["exchange"], ex.get("via")
        prev = (store.get("sources") or {}).get(name, {})
        s = {"exchange": name, "via": via, "state": ex.get("state"), "page": ex.get("page"), "x_handle": ex.get("x_handle"), "note": ex.get("note"),
             "last_ok_utc": prev.get("last_ok_utc"), "n_total": prev.get("n_total", 0)}
        src[name] = s
        if ex.get("state") != "on" or via not in FETCH or (only and name not in only):
            continue
        first = not any(k.startswith(name + ":") for k in items)
        try:
            got = FETCH[via](ex)
            s["last_ok_utc"], s["err"] = now, None
        except Exception as e:
            s["err"] = str(e)[:200]
            print(f"{name}: 失败 {s['err']}")
            continue
        new = 0
        for a in got:
            k = f"{name}:{a['id']}"
            if k in items:
                continue
            items[k] = {"exchange": name, "via": via, "title": a["title"], "url": a.get("url"), "announce_utc": a["announce_utc"], "first_seen_utc": now,
                        "baseline": first, "kind": kind(a["title"]), "assets": assets(a["title"])}
            new += 1
        s["n_total"] = sum(1 for k in items if k.startswith(name + ":"))
        print(f"{name}: 取到 {len(got)} 条，新增 {new}{'（基线）' if first else ''}")
        time.sleep(0.3)
    store.update(generated=now, sources=src, note="公告时间原样记录；计划开盘 / 首笔成交 / 窗口目前只有 Binance（alpha/listings.py）")
    json.dump(store, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
