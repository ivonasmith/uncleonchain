"""日历模块 · 每日生成（零配置，自动保存）
两个分区：
  btc   —— 比特币大事件：只放单独检验过的宏观事件（FOMC / CPI / 非农），附检验结论和用法；
           季度期权交割作为“常见说法但数据不支持”的反例显示；中期选举等“未检验”单列。
  web3  —— 行业动向：会议、黑客松、主网升级、代币解锁、上所、TGE、监管、ETF。不做价格检验，只告诉读者行业在发生什么。
输出：cal_latest.json（今天往后的两个分区 + 首页“未来 7 天”卡片）
环境变量：CAL_OUT_DIR（默认 ./output）、COINMARKETCAL_KEY（可选）、CAL_TODAY（测试用 YYYY-MM-DD）、CAL_OFFLINE=1（不联网）
"""
import os, json, csv, datetime as dt
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("CAL_OUT_DIR", os.path.join(HERE, "output"))
TODAY = dt.date.fromisoformat(os.environ["CAL_TODAY"]) if os.environ.get("CAL_TODAY") else dt.datetime.now(dt.timezone.utc).date()
OFFLINE = os.environ.get("CAL_OFFLINE") == "1"
ET, BJ, UTC = ZoneInfo("America/New_York"), ZoneInfo("Asia/Shanghai"), dt.timezone.utc
BTC_DAYS, WEB3_DAYS, CARD_DAYS = 60, 60, 7
STATS = json.load(open(os.path.join(HERE, "ev_stats.json"), encoding="utf-8"))
status = {"stale": False, "detail": {}, "notes": []}

# ---------------- BTC 分区 ----------------
NAME = {"FOMC": ("美联储议息决议", "FOMC rate decision"), "CPI": ("美国 CPI", "US CPI"), "NFP": ("美国非农就业", "US nonfarm payrolls"),
        "期权季度交割": ("BTC 期权季度交割", "BTC quarterly options expiry")}

def what_zh(t):
    s = STATS[t]
    if t == "期权季度交割":
        return (f"常见说法“交割日大波动”，数据不支持：2022 年以来 {s['n']} 次，交割那两个小时 BTC 最高到最低一般拉开 {s['h2_pct_med']}%，"
                f"和平时同一时段（{s['h2_pct_normal']}%）一样；当天全天 {s['day_pct_med']}%，平时 {s['day_pct_normal']}%。")
    return (f"2022 年以来 {s['n']} 次，{round(s['h2_share'] * 100)}% 的时候都比平时晃得厉害。"
            f"公布后第二天涨的比例 {round(s['up1_share'] * 100)}%，涨跌和抛硬币差不多，猜不出方向。")

def what_en(t):
    s = STATS[t]
    if t == "期权季度交割":
        return (f"The 'expiry-day volatility' story doesn't hold: since 2022 ({s['n']} expiries) the 2-hour high-low range is "
                f"{s['h2_pct_med']}%, same as a normal day ({s['h2_pct_normal']}%).")
    return (f"Since 2022 ({s['n']} releases), wider than normal {round(s['h2_share'] * 100)}% of the time. "
            f"Next day up {round(s['up1_share'] * 100)}% of the time — direction is a coin flip.")

def level_of(t):
    m = STATS[t]["h2_pct_med"]
    return ("大", "High") if m >= 2.5 else ("中", "Medium") if m >= 1.8 else ("不放大", "None")

def impact(t, px):
    """给新手看的幅度：公布那两个小时里，BTC 最高价和最低价一般差多少"""
    s = STATS[t]; lv = level_of(t)
    usd = lambda pct: f"约 ${round(px * pct / 100, -1):,.0f}" if px else ""
    if t == "期权季度交割":
        zh = f"交割那两个小时，最高到最低一般差 {s['h2_pct_med']}%，和平时一样。"
        en = f"Typical 2-hour high-low range {s['h2_pct_med']}%, same as normal."
    else:
        zh = (f"公布那两个小时，BTC 最高价和最低价一般差 {s['h2_pct_med']}%{'（' + usd(s['h2_pct_med']) + '）' if px else ''}，"
              f"平时同一时段只有 {s['h2_pct_normal']}%；四次里有一次超过 {s['h2_pct_p75']}%，十次里有一次超过 {s['h2_pct_p90']}%"
              f"{'（' + usd(s['h2_pct_p90']) + '）' if px else ''}，2022 年以来最大一次 {s['h2_pct_max']}%。"
              f"全天最高到最低一般 {s['day_pct_med']}%（平时 {s['day_pct_normal']}%）。")
        en = (f"In the 2 hours after the release, BTC's high-low range is typically {s['h2_pct_med']}% (normal: {s['h2_pct_normal']}%); "
              f"1 in 4 times above {s['h2_pct_p75']}%, 1 in 10 above {s['h2_pct_p90']}%, largest since 2022 {s['h2_pct_max']}%.")
    return dict(level_zh=lv[0], level_en=lv[1], text_zh=zh, text_en=en,
                range_2h_typ_pct=s["h2_pct_med"], range_2h_big_pct=s["h2_pct_p90"], range_2h_max_pct=s["h2_pct_max"],
                range_2h_normal_pct=s["h2_pct_normal"], range_day_typ_pct=s["day_pct_med"], range_day_normal_pct=s["day_pct_normal"],
                usd_typ=round(px * s["h2_pct_med"] / 100) if px else None, usd_big=round(px * s["h2_pct_p90"] / 100) if px else None,
                price_ref=round(px) if px else None)

def btc_price():
    if OFFLINE: return None
    try:
        import requests
        return float(requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=20).json()["data"]["amount"])
    except Exception:
        return None

USE_ZH = {"FOMC": "决议公布（北京时间 {bj}）前后 2 小时不挂贴近现价的单、不加杠杆追单；不提前押方向。",
          "CPI": "数据公布（北京时间 {bj}）前后 2 小时不挂贴近现价的单、不加杠杆追单；不提前押方向。",
          "NFP": "数据公布（北京时间 {bj}）前后 2 小时不挂贴近现价的单；当天整体波动不比平时大。",
          "期权季度交割": "不需要为交割日调整动作。"}
USE_EN = {"FOMC": "No resting orders near price and no leveraged chasing for 2 hours around the release ({utc} UTC). Don't bet on direction.",
          "CPI": "No resting orders near price and no leveraged chasing for 2 hours around the release ({utc} UTC). Don't bet on direction.",
          "NFP": "No resting orders near price for 2 hours around the release ({utc} UTC); the day as a whole is not more volatile.",
          "期权季度交割": "No action needed for expiry day."}
GRADE = {"FOMC": "已验证·波动", "CPI": "已验证·波动", "NFP": "已验证·波动", "期权季度交割": "已证伪"}
UNTESTED = [  # 未检验、只提示的日子：手工维护
    {"date": "2026-11-03", "title_zh": "美国中期选举", "title_en": "US midterm elections",
     "note_zh": "总统大选只有 3 个样本（2016、2020、2024，之后 30 天都上涨），中期选举没检验过。只提示，不改动作。",
     "note_en": "Only 3 presidential elections in the sample; midterms untested. Shown for awareness only."},
]

def last_friday(y, m):
    d = dt.date(y, m, 28)
    while (d + dt.timedelta(days=1)).month == m: d += dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - 4) % 7)

def btc_events():
    px = btc_price()
    rows = list(csv.DictReader(open(os.path.join(HERE, "btc_events.csv"), encoding="utf-8")))
    for y in (TODAY.year, TODAY.year + 1):
        for m in (3, 6, 9, 12):
            rows.append({"type": "期权季度交割", "date": last_friday(y, m).isoformat(), "time_et": "", "source": "https://www.deribit.com/"})
    out, last_known = [], max(r["date"] for r in rows if r["type"] != "期权季度交割")
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        if not (TODAY <= d <= TODAY + dt.timedelta(days=BTC_DAYS)): continue
        t = r["type"]
        if t == "期权季度交割":
            t_utc = dt.datetime(d.year, d.month, d.day, 8, tzinfo=UTC)
        else:
            hh, mm = map(int, r["time_et"].split(":"))
            t_utc = dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).astimezone(UTC)
        bj = t_utc.astimezone(BJ)
        bj_s = f"{bj:%m-%d %H:%M}"
        out.append(dict(type=t, date=d.isoformat(), days_until=(d - TODAY).days,
                        title_zh=NAME[t][0], title_en=NAME[t][1],
                        time_utc=t_utc.strftime("%Y-%m-%d %H:%M"), time_bj=bj.strftime("%Y-%m-%d %H:%M"),
                        time_et=(r["time_et"] + " ET") if r["time_et"] else "",
                        grade=GRADE[t], tested=True, emphasis=t != "期权季度交割",
                        what_zh=what_zh(t), what_en=what_en(t),
                        use_zh=USE_ZH[t].format(bj=bj_s), use_en=USE_EN[t].format(utc=t_utc.strftime("%H:%M")),
                        impact=impact(t, px), stats=STATS[t], source_url=r["source"]))
    for u in UNTESTED:
        d = dt.date.fromisoformat(u["date"])
        if TODAY <= d <= TODAY + dt.timedelta(days=BTC_DAYS):
            out.append(dict(type="未检验", date=u["date"], days_until=(d - TODAY).days, title_zh=u["title_zh"], title_en=u["title_en"],
                            grade="未检验", tested=False, emphasis=False, what_zh=u["note_zh"], what_en=u["note_en"], use_zh="不改动作。", use_en="No action."))
    out.sort(key=lambda x: (x["date"], x.get("time_utc", "")))
    left = (dt.date.fromisoformat(last_known) - TODAY).days
    status["detail"]["btc_schedule"] = f"ok（宏观日程录入到 {last_known}）"
    if left < 90:
        status["stale"] = True
        status["notes"].append(f"宏观日程只录入到 {last_known}，请按 FOMC/BLS 官网补下一年的日期到 btc_events.csv")
    return out

# ---------------- Web3 分区：直接聚合 6 个站 ----------------
# Luma（加密分类的大会时间线）、CryptoEvents、IndustryEvents、Web3Voyager —— 会议 / 黑客松
# CoinMarketCal、Coindar —— 山寨币代币事件（解锁、上所、升级、投票……），需要免费 key，没有就跳过
import re, time, hashlib
UA = {"User-Agent": "Mozilla/5.0 (compatible; uncleonchain-calendar/1.0; +https://uncleonchain.com)"}
CACHE = os.environ.get("CAL_CACHE_DIR", os.path.join(HERE, "cache"))
DETAIL_CACHE = os.path.join(CACHE, "detail_cache.json")
MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
CAT_EN = {"会议": "Conference", "黑客松": "Hackathon", "代币事件": "Token event", "解锁": "Unlock", "上所": "Listing",
          "升级": "Upgrade", "治理投票": "Governance", "空投": "Airdrop"}

def _get(url, **kw):
    import requests
    for i in range(3):
        try:
            r = requests.get(url, headers=kw.pop("headers", UA), timeout=30, **kw)
            if r.status_code == 200: return r
            last = r.status_code
        except Exception as ex:
            last = type(ex).__name__
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"HTTP {last}")

def _ev(src, title, a, b=None, cat="会议", url="", city="", coins=None, importance=1, note=""):
    return dict(date_start=a, date_end=b or a, category=cat, category_en=CAT_EN.get(cat, "Other"), title=title.strip(),
                coins=coins or [], city=city or "", importance=importance, source=src, url=url, note=note)

def _parse_dates(text, year_hint=None):
    """'Oct 23 – 24, 2026' / 'Nov 20 - Dec 2, 2026' / 'Oct222026' / '2026-10-23' → (start, end) ISO"""
    t = text.replace("–", "-").replace("—", "-")
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})(?:\D+(\d{4})-(\d{2})-(\d{2}))?", t)
    if m:
        a = f"{m[1]}-{m[2]}-{m[3]}"; return a, (f"{m[4]}-{m[5]}-{m[6]}" if m[4] else a)
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s*(\d{1,2})(?:\s*-\s*(?:([A-Za-z]{3})[a-z]*\.?\s*)?(\d{1,2}))?,?\s*(\d{4})?", t)
    if not m or m[1].lower() not in MON: return None
    y = int(m[5]) if m[5] else (year_hint or TODAY.year)
    m1 = MON[m[1].lower()]; d1 = int(m[2])
    m2 = MON.get((m[3] or m[1]).lower(), m1); d2 = int(m[4]) if m[4] else d1
    try:
        a = dt.date(y, m1, d1); b = dt.date(y + (1 if m2 < m1 else 0), m2, d2)
    except ValueError:
        return None
    if not m[5] and a < TODAY - dt.timedelta(days=60): a, b = a.replace(year=y + 1), b.replace(year=b.year + 1)
    return a.isoformat(), b.isoformat()

def _jsonld_event(html):
    for blk in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try: data = json.loads(blk.strip())
        except Exception: continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if "@graph" in x: stack += x["@graph"]
                typ = x.get("@type"); typ = typ if isinstance(typ, list) else [typ]
                if any(str(t).endswith("Event") for t in typ) and x.get("startDate"):
                    loc = x.get("location") or {}
                    if isinstance(loc, list): loc = loc[0] if loc else {}
                    addr = loc.get("address") if isinstance(loc, dict) else None
                    city = (addr.get("addressLocality") if isinstance(addr, dict) else (addr if isinstance(addr, str) else "")) or ""
                    if not city and isinstance(loc, dict) and "Virtual" in str(loc.get("@type")): city = "Online"
                    return dict(name=x.get("name", ""), start=str(x["startDate"])[:10], end=str(x.get("endDate") or x["startDate"])[:10], city=city)
    return None

def _detail_pages(src, links, limit=60):
    """列表页只拿到链接时，逐个打开详情页读 schema.org Event；结果缓存，每天只抓新出现的链接"""
    try: cache = json.load(open(DETAIL_CACHE, encoding="utf-8"))
    except Exception: cache = {}
    out, fetched = [], 0
    for url, card_text in links:
        info = cache.get(url)
        if info is None and fetched < limit:
            fetched += 1
            try:
                info = _jsonld_event(_get(url).text) or {}
            except Exception:
                info = {}
            if not info.get("start"):
                d = _parse_dates(card_text)
                if d: info = dict(name=info.get("name") or "", start=d[0], end=d[1], city=info.get("city", ""))
            cache[url] = info
        if info and info.get("start"):
            title = info.get("name") or re.sub(r"\s+", " ", card_text)[:80]
            out.append(_ev(src, title, info["start"], info["end"], cat="黑客松" if "hackathon" in (title + url).lower() else "会议",
                           url=url, city=info.get("city", "")))
    os.makedirs(CACHE, exist_ok=True)
    json.dump(cache, open(DETAIL_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return out

def _links(html, base, pattern):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser"); seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"] if a["href"].startswith("http") else base.rstrip("/") + "/" + a["href"].lstrip("/")
        if not re.search(pattern, href) or href in seen: continue
        seen.add(href)
        card = a
        for _ in range(4):  # 往上找含日期的卡片
            if card.parent is None: break
            card = card.parent
            if re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s*\d", card.get_text(" ")): break
        out.append((href.split("#")[0], card.get_text(" ", strip=True)[:300]))
    return out

def src_luma():
    js = _get("https://api.lu.ma/discover/category/get-page?slug=crypto").json()
    out = []
    for e in js.get("timeline_calendars") or []:
        c = e.get("calendar") or {}
        if not e.get("start_date"): continue
        out.append(_ev("Luma", c.get("name", ""), e["start_date"][:10], (e.get("end_date") or e["start_date"])[:10],
                       url="https://luma.com/" + c.get("slug", ""), city=((c.get("location") or {}).get("city") or ""), importance=3))
    return out

def src_cryptoevents():
    out = []
    for page in ("https://cryptoevents.global/", "https://cryptoevents.global/page/2/"):
        try: html = _get(page).text
        except Exception: break
        out += _links(html, "https://cryptoevents.global", r"^https://cryptoevents\.global/(?!page/|category/|tag/|wp-|about|contact|submit|privacy|feed)[a-z0-9-]+-20\d\d[a-z0-9-]*/?$")
    return _detail_pages("CryptoEvents", out)

def src_industryevents():
    html = _get("https://www.industryevents.com/events/industry/blockchain").text
    return _detail_pages("IndustryEvents", _links(html, "https://www.industryevents.com", r"^https://www\.industryevents\.com/events/(?!industry/|location/)[a-z0-9-]+/?$"))

def src_web3voyager():
    links = []
    for p in (1, 2, 3):
        html = _get(f"https://web3voyager.com/?eventsPage={p}").text
        links += _links(html, "https://web3voyager.com", r"^https://web3voyager\.com/event/[a-z0-9-]+/?$")
    uniq = list(dict(links).items())
    return _detail_pages("Web3Voyager", uniq)

CMC_CAT = [("unlock", "解锁"), ("release", "解锁"), ("exchange", "上所"), ("listing", "上所"), ("delist", "上所"),
           ("airdrop", "空投"), ("fork", "升级"), ("upgrade", "升级"), ("mainnet", "升级"), ("vote", "治理投票"),
           ("governance", "治理投票"), ("tokenomics", "解锁"), ("burn", "代币事件"), ("conference", "会议")]

def _cat(s):
    s = s.lower()
    return next((v for k, v in CMC_CAT if k in s), "代币事件")

def src_coinmarketcal():
    key = os.environ.get("COINMARKETCAL_KEY")
    if not key: raise LookupError("未接入（没有 COINMARKETCAL_KEY）")
    out, end = [], TODAY + dt.timedelta(days=WEB3_DAYS)
    for page in range(1, 6):
        js = _get("https://developers.coinmarketcal.com/v1/events", headers={"x-api-key": key, "Accept": "application/json", "Accept-Encoding": "deflate, gzip"},
                  params={"max": 75, "page": page, "dateRangeStart": TODAY.isoformat(), "dateRangeEnd": end.isoformat(), "sortBy": "hot_events"}).json()
        body = js.get("body") or []
        for e in body:
            t = e.get("title") or {}; title = t.get("en") if isinstance(t, dict) else str(t)
            d = (e.get("date_event") or "")[:10]
            if not d: continue
            coins = [c.get("symbol", "") for c in e.get("coins") or [] if c.get("symbol")]
            cats = " ".join(c.get("name", "") for c in e.get("categories") or [])
            out.append(_ev("CoinMarketCal", f"{'/'.join(coins[:3])} · {title}" if coins else title, d, cat=_cat(cats + " " + title),
                           url=e.get("source") or e.get("proof") or "https://coinmarketcal.com/", coins=coins,
                           importance=2 if (e.get("is_hot") or e.get("hot")) else 1))
        if len(body) < 75: break
    return out

def src_coindar():
    key = os.environ.get("COINDAR_KEY")
    if not key: raise LookupError("未接入（没有 COINDAR_KEY）")
    coins = {str(c["id"]): c.get("symbol", "") for c in _get("https://coindar.org/api/v2/coins", params={"access_token": key}).json()}
    out, end = [], TODAY + dt.timedelta(days=WEB3_DAYS)
    for page in range(1, 6):
        body = _get("https://coindar.org/api/v2/events", params={"access_token": key, "page": page, "page_size": 100,
                    "filter_date_start": TODAY.isoformat(), "filter_date_end": end.isoformat(), "sort_by": "date_start", "order_by": "0"}).json()
        for e in body or []:
            sym = coins.get(str(e.get("coin_id")), "")
            a = str(e.get("date_start", ""))[:10]
            if not a: continue
            out.append(_ev("Coindar", f"{sym} · {e.get('caption', '')}" if sym else e.get("caption", ""), a, str(e.get("date_end") or a)[:10],
                           cat=_cat(str(e.get("tags", "")) + " " + e.get("caption", "")), url=e.get("source") or "https://coindar.org/",
                           coins=[sym] if sym else [], importance=2 if e.get("important") else 1))
        if not body or len(body) < 100: break
    return out

SOURCES = [("Luma", src_luma), ("CryptoEvents", src_cryptoevents), ("IndustryEvents", src_industryevents),
           ("Web3Voyager", src_web3voyager), ("CoinMarketCal", src_coinmarketcal), ("Coindar", src_coindar)]
SITE = {"Luma": "https://luma.com/crypto", "CryptoEvents": "https://cryptoevents.global/", "IndustryEvents": "https://www.industryevents.com/events/industry/blockchain",
        "Web3Voyager": "https://web3voyager.com/", "CoinMarketCal": "https://coinmarketcal.com/", "Coindar": "https://coindar.org/"}

def _norm(t):
    t = re.sub(r"\b20\d\d\b", "", t.lower()); return re.sub(r"[^a-z0-9]+", "", t)[:24]

def web3_events():
    rows, last_path = [], os.path.join(CACHE, "web3_last_ok.json")
    try: last_ok = json.load(open(last_path, encoding="utf-8"))
    except Exception: last_ok = {}
    for name, fn in SOURCES:
        if OFFLINE:
            got = last_ok.get(name, []); status["detail"][name] = f"离线：用缓存 {len(got)} 条"
        else:
            try:
                got = fn(); status["detail"][name] = f"ok（{len(got)} 条）"
                if got: last_ok[name] = got
                else:
                    got = last_ok.get(name, []); status["detail"][name] = f"取到 0 条，用上次结果 {len(got)} 条"; status["stale"] = True
            except LookupError as ex:
                got = []; status["detail"][name] = str(ex)
            except Exception as ex:
                got = last_ok.get(name, []); status["stale"] = True
                status["detail"][name] = f"失败：{type(ex).__name__} {str(ex)[:80]}；用上次结果 {len(got)} 条"
        rows += got
    os.makedirs(CACHE, exist_ok=True); json.dump(last_ok, open(last_path, "w", encoding="utf-8"), ensure_ascii=False)
    lo, hi = TODAY, TODAY + dt.timedelta(days=WEB3_DAYS)
    keep, seen = [], {}
    for r in sorted(rows, key=lambda x: -x["importance"]):
        try: a, b = dt.date.fromisoformat(r["date_start"]), dt.date.fromisoformat(r["date_end"])
        except Exception: continue
        if b < lo or a > hi or (b - a).days > 60: continue
        k = (r["date_start"], _norm(r["title"]))
        if k in seen:  # 同一活动多个站都有：合并来源
            if r["source"] not in seen[k]["sources"]: seen[k]["sources"].append(r["source"])
            continue
        r = dict(r, sources=[r["source"]], days_until=max(0, (a - TODAY).days), ongoing=a <= TODAY)
        seen[k] = r; keep.append(r)
    keep.sort(key=lambda x: (x["date_start"], -x["importance"], x["title"]))
    return keep

# ---------------- 代币解锁（单独一个 Tab：比特币大事件 | 代币解锁 | Web3 行业动向）----------------
# 数据 = ① cal/unlocks.csv（有出处的人工核对条目）+ ② CoinMarketCal / Coindar 里分类为「解锁」的事件（有 key 才有）。
# DefiLlama 的解锁接口是付费的（2026-10-25 实测返回 402），不用。拿不到的数量/价值留空，页面写「数量待核」，不估算。
WATCH = ["BTC", "ETH", "SOL", "XRP", "BNB", "UNI", "CAKE", "HYPE", "ENA", "TAO", "RAY", "DOGE", "LDO", "ARB", "NEAR", "ZEC", "JUP", "AAVE", "WLD", "SUI", "INJ"]
UNLOCK_USD_M, UNLOCK_PCT = 20.0, 2.0          # 「重要」线：单次价值 ≥ 2,000 万美元，或占流通量 ≥ 2%
UNLOCK_CSV = os.path.join(HERE, "unlocks.csv")

def _num(x):
    try: return float(str(x).strip().replace(",", ""))
    except Exception: return None

def unlocks(w3):
    lo, hi = TODAY, TODAY + dt.timedelta(days=WEB3_DAYS)
    rows, n_csv, n_src, asof = {}, 0, 0, ""
    try:
        lines = [l for l in open(UNLOCK_CSV, encoding="utf-8") if l.strip() and not l.lstrip().startswith("#")]
        for r in csv.DictReader(lines):
            try: d = dt.date.fromisoformat(r["date"].strip())
            except Exception: continue
            asof = max(asof, (r.get("asof") or "").strip())
            if not (lo <= d <= hi): continue
            sym = r["symbol"].strip().upper()
            rows[(d.isoformat(), sym)] = dict(date=d.isoformat(), symbol=sym, name=(r.get("name") or "").strip(), usd_m=_num(r.get("usd_m")), pct_circ=_num(r.get("pct_circ")),
                amount=(r.get("amount") or "").strip(), kind=(r.get("kind") or "").strip(), kind_en=(r.get("kind_en") or "").strip(), status=(r.get("status") or "forecast").strip() or "forecast",
                hot=(r.get("hot") or "").strip() == "1", sources=[dict(name=(r.get("source_name") or "").strip(), name_en=(r.get("source_name_en") or "").strip(), url=(r.get("source_url") or "").strip())])
            n_csv += 1
    except FileNotFoundError:
        status["notes"].append("cal/unlocks.csv 不存在")
    for e in w3:
        if e.get("category") != "解锁" or e.get("date_start") is None: continue
        sym = (e.get("coins") or [""])[0].upper() or re.split(r"\s*[·|:-]\s*", e.get("title", ""))[0].strip().upper()[:12]
        k = (e["date_start"], sym)
        src = dict(name=e.get("source", ""), url=e.get("url", ""))
        if k in rows:
            if src["name"] not in [x["name"] for x in rows[k]["sources"]]: rows[k]["sources"].append(src)
            rows[k]["hot"] = rows[k]["hot"] or e.get("importance", 1) >= 2
        else:
            rows[k] = dict(date=e["date_start"], symbol=sym, name="", usd_m=None, pct_circ=None, amount="", kind="", status="forecast", hot=e.get("importance", 1) >= 2, sources=[src])
            n_src += 1
    out = []
    for r in rows.values():
        d = dt.date.fromisoformat(r["date"])
        reasons = []
        if r["usd_m"] is not None and r["usd_m"] >= UNLOCK_USD_M: reasons.append("value")
        if r["pct_circ"] is not None and r["pct_circ"] >= UNLOCK_PCT: reasons.append("pct")
        if r["symbol"] in WATCH: reasons.append("watch")
        if r["hot"]: reasons.append("hot")
        out.append(dict(r, days_until=(d - TODAY).days, important=bool(reasons), reasons=reasons, watch=r["symbol"] in WATCH))
    out.sort(key=lambda x: (x["date"], not x["important"], x["symbol"]))
    status["detail"]["代币解锁"] = f"人工表 {n_csv} 条 + 数据源 {n_src} 条"
    if asof:
        try:
            age = (TODAY - dt.date.fromisoformat(asof)).days
            if age > 10: status["notes"].append(f"代币解锁人工表已 {age} 天没更新（cal/unlocks.csv 最新核对日 {asof}）")
        except Exception: pass
    return dict(
        title_zh="代币解锁", title_en="Token unlocks",
        intro_zh="未来 60 天里值得留意的代币解锁。解锁就是之前锁定的代币按计划释放，市场上可能多出一批卖出压力，但不是必跌信号：这里没有检验过解锁对价格的影响，只告诉你什么时候、大概多大。"
                 "日期和数量多为预测值，以项目方公告为准。",
        intro_en="Token unlocks worth watching over the next 60 days. An unlock releases tokens that were locked on schedule, which can add selling pressure, but it is not a sure drop. "
                 "We have not tested how unlocks affect prices; this page only says when and roughly how big. Dates and amounts are mostly forecasts. Check the project's own announcement.",
        rule_zh=f"「重要」的标准：单次解锁价值 ≥ {UNLOCK_USD_M*100:,.0f} 万美元，或占流通量 ≥ {UNLOCK_PCT:g}%，或属于我们跟踪的 {len(WATCH)} 个币，或数据源标为热门。",
        rule_en=f"'Important' means: one unlock worth at least ${UNLOCK_USD_M:,.0f}M, or at least {UNLOCK_PCT:g}% of circulating supply, or one of the {len(WATCH)} coins we track, or flagged hot by a data source.",
        source_note_zh="来源：Tokenomist、各项目公告（人工核对，每条标明出处，每周日更新）；CoinMarketCal、Coindar 接入后自动补充。拿不到的数量写「数量待核」，不估算。",
        source_note_en="Sources: Tokenomist and project announcements (checked by hand, each with its source, updated Sundays); CoinMarketCal and Coindar are added automatically once connected. Missing amounts say 'amount TBC', never estimated.",
        watch=WATCH, sources=[dict(name="Tokenomist", url="https://tokenomist.ai/"), dict(name="CoinMarketCal", url="https://coinmarketcal.com/"), dict(name="Coindar", url="https://coindar.org/")],
        events=out)

# ---------------- 组装 ----------------
def main():
    btc = btc_events(); w3 = web3_events(); ul = unlocks(w3)
    card = [dict(date=e["date"], days_until=e["days_until"], tab="btc", title_zh=e["title_zh"], title_en=e["title_en"],
                 time_bj=e.get("time_bj", ""), grade=e["grade"])
            for e in btc if e["days_until"] <= CARD_DAYS and e["emphasis"]]
    card += [dict(date=e["date_start"], days_until=e["days_until"], tab="web3", title_zh=e["title"], title_en=e["title"],
                  time_bj="", grade="行业动向", category=e["category"])
             for e in w3 if e["days_until"] <= CARD_DAYS and e["importance"] >= 3]
    card += [dict(date=e["date"], days_until=e["days_until"], tab="unlock", title_zh=f'{e["symbol"]} 解锁', title_en=f'{e["symbol"]} unlock', time_bj="", grade="代币解锁", category="解锁")
             for e in ul["events"] if e["days_until"] <= CARD_DAYS and e["important"]]
    card.sort(key=lambda x: (x["date"], x["tab"]))
    nxt = next((e for e in btc if e["emphasis"]), None)
    res = {
        "generated_utc": dt.datetime.now(UTC).strftime("%Y-%m-%d %H:%M"), "today": TODAY.isoformat(),
        "btc": {
            "title_zh": "比特币大事件（已单独检验）", "title_en": "BTC events (individually tested)",
            "intro_zh": "这里只放我们用 2015 年以来的 BTC 小时数据单独检验过的事件。美联储议息、CPI、非农公布后的两个小时，BTC 会明显比平时晃得厉害"
                        "（2022 年以后才这样）：最高价和最低价一般差 2%~3%，平时同一时段只有 1% 左右，十次里有一次能到 3%~6%。"
                        "但涨还是跌猜不出来，提前几天也不会更动荡。用法只有一个：公布前后两小时别挂贴近现价的单、别加杠杆追，也别提前押方向。",
            "impact_table": [dict(type=t, title_zh=NAME[t][0], title_en=NAME[t][1], grade=GRADE[t], **{k: v for k, v in impact(t, None).items() if not k.startswith("usd") and k != "price_ref"})
                             for t in ("FOMC", "CPI", "NFP", "期权季度交割")],
            "impact_note_zh": "“最高价和最低价差多少”= 那段时间里 BTC 最高成交价比最低成交价高出百分之几，不分涨跌。比如 2.7% 在 BTC 8 万美元时约等于上下晃 2,000 多美元。",
            "stats_asof_zh": "检验数据截至 2026-10-12（Coinbase 小时线），每半年（1 月、7 月）用新数据重测一次，样本每半年约增加 25 次。",
            "intro_en": "Only events we have tested one by one on hourly BTC data since 2015. Fed decisions, CPI and payrolls widen the 2-hour range after release "
                        "(since 2022), but direction is unpredictable and the days before are not more volatile.",
            "next_zh": (f"下一个：{nxt['title_zh']}，{nxt['days_until']} 天后（北京时间 {nxt['time_bj']}）" if nxt else ""),
            "events": btc,
            "method_zh": "对照组：同一星期几、前后 9 周内、没有其他事件的日子的同一时段。振幅 = 区间最高 ÷ 最低。年代分 2015-17、2018-21、2022-26 分别看。"
                         "期权交割：Deribit 每月最后一个周五 08:00 UTC。数据：Coinbase BTC-USD 小时线。",
        },
        "web3": {
            "title_zh": "Web3 行业动向", "title_en": "Web3 industry calendar",
            "intro_zh": "未来 60 天的行业会议、黑客松，以及山寨币的代币事件（解锁、上所、升级、治理投票）。直接汇总自 Luma、CryptoEvents、IndustryEvents、Web3Voyager、CoinMarketCal、Coindar，"
                        "给从业者看行业动向用。这些没有做过对价格的检验，不是交易信号；日期以各来源为准，去之前点进原链接核实。",
            "intro_en": "Conferences, hackathons and altcoin token events (unlocks, listings, upgrades, votes) for the next 60 days, aggregated from Luma, CryptoEvents, IndustryEvents, "
                        "Web3Voyager, CoinMarketCal and Coindar. Industry awareness only — not tested against prices, not trading signals.",
            "categories": [{"zh": k, "en": v} for k, v in CAT_EN.items()],
            "sources": [{"name": k, "url": v} for k, v in SITE.items()],
            "events": w3,
        },
        "unlocks": ul,
        "next7": card,
        "data_status": status,
    }
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, "cal_latest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"cal_latest.json：BTC {len(btc)} 条，解锁 {len(ul['events'])} 条，Web3 {len(w3)} 条，未来 7 天 {len(card)} 条；状态 {status}")

if __name__ == "__main__":
    main()
