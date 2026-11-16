#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交易所上币事件库（先做 Binance）：公告 → 计划开盘 → 首笔成交 → 30 分钟 / 1 / 4 / 24 小时窗口。

每个时间单独一个字段，不合并（方法论附录二 B）：
  announce_utc      公告发布时间（公告列表 releaseDate）
  revision_utc      修订时间（Binance 详情接口的 lastUpdateTime 实测为 0，拿不到就是 None）
  planned_open_utc  公告正文写的开盘时间
  first_trade_utc   第一根 1 分钟 K 线的开盘时刻（现货 data-api.binance.vision；U 本位合约 data.binance.vision 归档）
窗口：参考价 = 第一根 1 分钟 K 线的开盘价；+30m / +1h / +4h / +24h 取那一分钟的收盘价，另记 24 小时内最高 / 最低。
只是事后读数：第一分钟的价格普通人基本成交不到，不是可执行价。

输出 data/alpha/listings.json：events 按 id（bn:<公告 id>:<交易对>）只追加；窗口算满 24 小时后冻结不再改。
首跑回填 BACKFILL_DAYS 天，之后每天只翻最近几页。用法：python3 alpha/listings.py [--pages N] [--days N]
"""
import csv, datetime as dt, io, json, os, re, sys, time, urllib.error, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(os.environ.get("LP_DATA", os.path.join(ROOT, "data")), "alpha")
PATH = os.path.join(OUT, "listings.json")
BACKFILL_DAYS = 365
LIST = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo={p}&pageSize=20&catalogId=48"
DETAIL = "https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={c}"
SPOT_K = "https://data-api.binance.vision/api/v3/klines?symbol={s}&interval=1m&startTime={t}&limit=1000"
FUT_ZIP = "https://data.binance.vision/data/futures/um/daily/klines/{s}/1m/{s}-1m-{d}.zip"
WINDOWS = [("m30", 30), ("h1", 60), ("h4", 240), ("h24", 1440)]
DROP = re.compile(r"TradFi|bStocks|Tokenized Securit|Exchange Adds|Collateral|Options|Delivery|COIN-Margined", re.I)
QUOTES = ("USDT", "USDC", "FDUSD", "BNB", "BTC", "ETH", "TRY", "EUR", "BRL", "JPY", "USD1", "U")


def get(url, raw=False, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                b = r.read()
            return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            time.sleep(2 + 3 * i)
        except Exception:
            time.sleep(2 + 3 * i)
    return None


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ms(s):
    return int(dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def body_text(body):
    try:
        node = json.loads(body) if isinstance(body, str) else body
    except Exception:
        return body or ""
    out = []

    def walk(x):
        if x.get("node") == "text":
            out.append(x.get("text", ""))
        for c in x.get("child") or []:
            walk(c)
        if x.get("tag") in ("p", "li", "h2", "h3", "tr", "td", "br"):
            out.append("\n")
    walk(node)
    return re.sub(r"\n+", "\n", "".join(out).replace("&nbsp;", " "))


def classify(title):
    """→ 'spot' | 'perp' | None"""
    if DROP.search(title):
        return None
    if re.search(r"Binance Will List\b", title) or re.search(r"Binance Will Add .+ on Earn, Buy Crypto.*Spot|Will Open Trading for", title):
        return "spot"
    if re.search(r"Binance Futures Will Launch USD.?-Margined .*Perpetual", title):
        return "perp"
    return None


def split_pair(sym):
    for q in sorted(QUOTES, key=len, reverse=True):
        if sym.endswith(q) and len(sym) > len(q):
            return sym[:-len(q)], q
    return sym, None


def parse_spot(title, txt):
    """→ [(pair 'XXXUSDT', base, quote, planned_ms)]；一篇公告可能上多个币"""
    out = []
    # 每个「list NAME (SYM) and open trading ... at TIME」段落；找不到就整篇一个时间
    times = re.findall(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(UTC\)", txt)
    pairs = []
    for m in re.finditer(r"New Spot Trading Pairs?:\s*([^\n]+)", txt):
        pairs += re.findall(r"\b([A-Z0-9]{1,15})/([A-Z0-9]{1,6})\b", m.group(1))
    if not pairs:
        pairs = re.findall(r"\b([A-Z0-9]{2,15})/(USDT|USDC|FDUSD|BNB|BTC|TRY|EUR|BRL|JPY|USD1|U)\b", txt)
    seen = set()
    for base, q in pairs:
        if (base, q) in seen:
            continue
        seen.add((base, q))
        # 该币的开盘时间：正文里离「(BASE)」最近的下一个时间，否则第一个时间
        t = None
        m = re.search(r"\(" + re.escape(base) + r"\)[^\n]*?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(UTC\)", txt)
        if m:
            t = m.group(1)
        elif times:
            t = times[0]
        out.append((base + q, base, q, ms(t) if t else None))
    return out


def parse_perp(title, txt):
    out, seen = [], set()
    for m in re.finditer(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(UTC\):\s*([A-Z0-9]{2,20}USD[TC1]?) Perpetual", txt):
        if m.group(2) not in seen:
            seen.add(m.group(2)); out.append((m.group(2), ms(m.group(1))))
    if not out:
        syms = re.findall(r"\b([A-Z0-9]{2,20}USD[TC])\b", title) or re.findall(r"\b([A-Z0-9]{2,20}USD[TC]) [Pp]erpetual", txt)
        t = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(UTC\)", txt)
        for s in syms:
            if s not in seen:
                seen.add(s); out.append((s, ms(t.group(1)) if t else None))
    res = []
    for s, t in out:
        base, q = split_pair(s)
        res.append((s, base, q, t))
    return res


def spot_candles(sym, start_ms, need_until):
    rows, t = [], start_ms
    while t < need_until and len(rows) < 3000:
        k = get(SPOT_K.format(s=sym, t=t))
        if not k:
            break
        rows += [(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7])) for x in k]
        if len(k) < 1000:
            break
        t = int(k[-1][0]) + 60000
    return rows


def fut_candles(sym, start_ms, days=3):
    rows = []
    d0 = dt.datetime.fromtimestamp(start_ms / 1000, dt.timezone.utc).date()
    for i in range(days):
        d = (d0 + dt.timedelta(days=i)).isoformat()
        b = get(FUT_ZIP.format(s=sym, d=d), raw=True)
        if not b:
            if rows:
                break
            continue
        try:
            z = zipfile.ZipFile(io.BytesIO(b))
            for r in csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), "utf-8")):
                if not r or not r[0].isdigit():
                    continue
                rows.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[7])))
        except Exception:
            break
    return rows


def windows(rows):
    """rows: (open_ms, o, h, l, c, quote_vol)，从第一根起。→ dict 或 None"""
    rows = [r for r in rows if r[5] > 0 or r[1] != r[4] or True]
    if not rows:
        return None
    t0, ref = rows[0][0], rows[0][1]
    by = {r[0]: r for r in rows}
    w = {"ref_price": ref, "first_trade_utc": iso(t0), "first_trade_basis": "第一根 1 分钟 K 线的开盘时刻"}
    for name, mins in WINDOWS:
        r = by.get(t0 + (mins - 1) * 60000)
        w[name] = round(r[4] / ref - 1, 4) if r and ref else None
    day = [r for r in rows if r[0] < t0 + 1440 * 60000]
    full = len(day) >= 1380   # 24 小时基本取齐
    if day and ref:
        hi = max(day, key=lambda r: r[2]); lo = min(day, key=lambda r: r[3])
        w.update(high24=round(hi[2] / ref - 1, 4), high24_min=int((hi[0] - t0) / 60000), low24=round(lo[3] / ref - 1, 4), low24_min=int((lo[0] - t0) / 60000),
                 quote_vol24=round(sum(r[5] for r in day)))
    w["complete"] = bool(full and w.get("h24") is not None)
    return w


def main():
    args = sys.argv[1:]
    opt = lambda k, d: int(args[args.index(k) + 1]) if k in args else d
    now = dt.datetime.now(dt.timezone.utc)
    os.makedirs(OUT, exist_ok=True)
    try:
        store = json.load(open(PATH, encoding="utf-8"))
    except Exception:
        store = {"events": {}, "articles": {}}
    E, A = store["events"], store.setdefault("articles", {})
    first = not A
    days = opt("--days", BACKFILL_DAYS)
    max_pages = opt("--pages", 60 if first else 3)
    cutoff = (now - dt.timedelta(days=days)).timestamp() * 1000
    status = {"list_ok": False, "pages": 0, "detail_fail": 0, "kline_fail": 0}
    # 1) 公告列表
    arts = []
    for p in range(1, max_pages + 1):
        d = get(LIST.format(p=p))
        try:
            xs = d["data"]["catalogs"][0]["articles"]
        except Exception:
            break
        status["list_ok"] = True; status["pages"] = p
        arts += xs
        if not xs or xs[-1]["releaseDate"] < cutoff:
            break
        time.sleep(0.3)
    # 2) 新公告 → 详情 → 事件
    for a in arts:
        aid = str(a["id"])
        if a["releaseDate"] < cutoff or aid in A:
            continue
        kind = classify(a["title"])
        if not kind:
            A[aid] = {"title": a["title"], "kind": None}
            continue
        det = get(DETAIL.format(c=a["code"]))
        try:
            dd = det["data"]; txt = body_text(dd.get("body") or "")
        except Exception:
            status["detail_fail"] += 1
            continue
        items = parse_spot(a["title"], txt) if kind == "spot" else parse_perp(a["title"], txt)
        rev = dd.get("lastUpdateTime") or 0
        url = f"https://www.binance.com/en/support/announcement/{a['code']}"
        A[aid] = {"title": a["title"], "kind": kind, "n": len(items)}
        premarket = bool(re.search(r"Pre-Market", a["title"], re.I))
        for sym, base, q, t in items:
            E[f"bn:{aid}:{sym}"] = {"exchange": "Binance", "asset": base, "pair": sym, "quote": q, "market": "永续" if kind == "perp" else "现货", "premarket": premarket,
                                    "title": a["title"], "url": url, "announce_utc": iso(a["releaseDate"]), "revision_utc": iso(rev) if rev and rev > a["releaseDate"] else None,
                                    "planned_open_utc": iso(t) if t else None, "first_seen_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "baseline": first, "w": None}
        time.sleep(0.25)
    # 3) 首笔成交与窗口（没算完的都重试；现货每个币只算 USDT 对，没有就算公告里的第一个对）
    by_art = {}
    for k, e in E.items():
        by_art.setdefault(k.rsplit(":", 1)[0] + ":" + e["asset"], []).append(k)
    for grp in by_art.values():
        main_k = next((k for k in grp if E[k]["quote"] == "USDT"), grp[0])
        for k in grp:
            E[k]["primary"] = k == main_k
    for k, e in E.items():
        if not e.get("primary") or (e.get("w") or {}).get("complete") or not e.get("planned_open_utc"):
            continue
        t = int(dt.datetime.strptime(e["planned_open_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        if t > now.timestamp() * 1000:
            continue
        if now.timestamp() * 1000 - t > 30 * 86400000 and e.get("tries", 0) >= 3:
            continue   # 开盘一个月后还取不到 K 线（改期 / 取消 / 换代码），不再重试
        start = t - 3600000
        rows = spot_candles(e["pair"], start, t + 1441 * 60000) if e["market"] == "现货" else fut_candles(e["pair"], start)
        rows = [r for r in rows if r[0] >= start]
        w = windows(rows) if rows else None
        e["tries"] = e.get("tries", 0) + 1
        if w:
            w["lag_min"] = int((dt.datetime.strptime(w["first_trade_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp() * 1000 - t) / 60000)
            e["w"] = w
        else:
            status["kline_fail"] += 1
        time.sleep(0.2)
    prim = [e for e in E.values() if e.get("primary")]
    store.update(generated=now.strftime("%Y-%m-%dT%H:%M:%SZ"), status=status, exchanges=["Binance"],
                 n={"events": len(E), "primary": len(prim), "with_windows": sum(1 for e in prim if (e.get("w") or {}).get("complete")),
                    "spot": sum(1 for e in prim if e["market"] == "现货"), "perp": sum(1 for e in prim if e["market"] == "永续")},
                 note="窗口参考价 = 第一根 1 分钟 K 线开盘价，是事后读数，不是可成交价；revision_utc 取不到记 null；其它交易所待接入")
    json.dump(store, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("上币事件：", json.dumps(store["n"], ensure_ascii=False), json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
