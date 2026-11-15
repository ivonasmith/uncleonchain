#!/usr/bin/env python3
"""机会卡的「上线多少天」和「币上线多少天 + 看盘入口」（大叔 2026-11-15 定）。opps.py 调用，失败不影响出卡。

项目上线天数（写清口径，不冒充真实上线日）：
  取以下最早的一天 —— DefiLlama 收录日（listedAt，本协议和同母协议的子协议里最早的）、协议收入 / 手续费数据第一天（opps.series 拉的全历史）、
  本站板块第一次记到的日子（发射台矩阵首次出现、AI Agent 手续费首日）、手动线索登记的上线日（manual_leads.json 的 launched）。
  页面写「上线约 N 天（以 X 为准）」。
币上线天数：
  代币身份 = DefiLlama 协议 / 母协议登记的 gecko_id、symbol、address（手动线索可以自己写 gecko / address / chain）。
  首个价格日 = CoinGecko 价格历史第一天（market_chart days=max），取不到用 coins.llama.fi 首个价格；结果缓存在 data/alpha/token_meta.json（只查一次）。
  页面写「币上线约 N 天（价格数据从 X 起）」——价格数据起点不一定是真正开盘日。
看盘入口：CoinGecko 币页、DexScreener（有合约地址时按链 + 地址，否则按代码搜索）、DefiLlama 协议页。
"""
import json, os, time, urllib.request, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "alpha")
META = os.path.join(OUT, "token_meta.json")
UA = {"User-Agent": "uncleonchain-alpha/1.0"}

# DefiLlama 地址前缀 → DexScreener 链名
DEX_CHAIN_UNUSED = {"ethereum": "ethereum", "bsc": "bsc", "base": "base", "arbitrum": "arbitrum", "optimism": "optimism", "polygon": "polygon", "avax": "avalanche",
             "solana": "solana", "sui": "sui", "hyperliquid": "hyperevm", "robinhood": "robinhood", "sonic": "sonic", "berachain": "berachain",
             "mantle": "mantle", "linea": "linea", "blast": "blast", "scroll": "scroll", "tron": "tron", "ton": "ton", "aptos": "aptos", "monad": "monad",
             "binance-smart-chain": "bsc", "abstract": "abstract", "unichain": "unichain", "plasma": "plasma", "megaeth": "megaeth", "ink": "ink"}


def _get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


def _load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def directory():
    """DefiLlama 协议列表（id / slug / listedAt / 代币）+ 母协议（lite/protocols2 的 parentProtocols，带代币）。"""
    protos = _get("https://api.llama.fi/protocols")
    try:
        parents = _get("https://api.llama.fi/lite/protocols2").get("parentProtocols") or []
    except Exception:
        parents = []
    return protos, {p["id"]: p for p in parents}


def tok_of(p):
    if not p:
        return None
    sym = p.get("symbol") if p.get("symbol") not in (None, "-", "") else None
    if not (p.get("gecko_id") or sym):
        return None
    addr, chain = p.get("address") or None, None
    if addr and ":" in addr:
        chain, addr = addr.split(":", 1)
    elif addr and addr.startswith("0x"):
        chain = "ethereum"
    return {"gecko": p.get("gecko_id"), "sym": sym, "address": addr, "chain": chain}


def first_day(gecko, meta):
    """价格数据第一天（缓存）。"""
    if not gecko:
        return None
    m = meta.get(gecko)
    if m and m.get("first") and (m.get("src") == "CoinGecko" or m.get("checked", "") >= (dt.date.today() - dt.timedelta(days=7)).isoformat()):
        return m   # CoinGecko 的结果一直用；兜底源的每周再试一次 CoinGecko（它的历史通常更早）
    out = {"first": None, "src": None, "checked": dt.date.today().isoformat()}
    try:
        d = _get(f"https://api.coingecko.com/api/v3/coins/{gecko}/market_chart?vs_currency=usd&days=max&interval=daily", 60)
        pts = d.get("prices") or []
        if pts:
            out.update(first=dt.datetime.fromtimestamp(pts[0][0] / 1000, dt.timezone.utc).date().isoformat(), src="CoinGecko")
        time.sleep(6)   # 免费接口限流
    except Exception as e:
        out["err"] = str(e)[:80]
    if not out["first"]:
        try:
            d = _get(f"https://coins.llama.fi/prices/first/coingecko:{gecko}")
            c = (d.get("coins") or {}).get(f"coingecko:{gecko}")
            if c and c.get("timestamp"):
                out.update(first=dt.datetime.fromtimestamp(c["timestamp"], dt.timezone.utc).date().isoformat(), src="DefiLlama 价格")
        except Exception as e:
            out["err2"] = str(e)[:80]
    meta[gecko] = out
    return out


def market(t, meta):
    """看 K 线的入口 + 市值 / 成交额快照（大叔 11-15 定：按交易的思路，先把人引到第三方看价格走势、市值、成交量）。
    优先级（大叔 11-15 定）：币安现货（CoinGecko 行情表里确认这个币在币安有 USDT 对，防同名不同币，如 Nullmask 的 MASK ≠ 币安的 MASK）
           → CMC（只用 alpha/cmc_slugs.json 里核对过的 slug）→ DexScreener 流动性最大的交易对（按合约地址查，直接打开 K 线）→ CoinGecko 币页。
    快照来自 DexScreener（日更时的读数，不是实时）。"""
    out = {"chart": None, "snap": None}
    g = t.get("gecko")
    if g:
        m = meta.setdefault(g, {})
        if m.get("bn_checked", "") < (dt.date.today() - dt.timedelta(days=7)).isoformat():
            try:
                d = _get(f"https://api.coingecko.com/api/v3/coins/{g}/tickers?exchange_ids=binance", 40)
                tk = [x for x in d.get("tickers") or [] if x.get("target") in ("USDT", "FDUSD", "USDC") and not x.get("is_stale")]
                m["binance"] = tk[0]["base"] + "_" + tk[0]["target"] if tk else None
                m["bn_checked"] = dt.date.today().isoformat()
                time.sleep(6)
            except Exception:
                pass
        if m.get("binance"):
            out["chart"] = {"name": "币安", "name_en": "Binance", "url": f"https://www.binance.com/zh-CN/trade/{m['binance']}?type=spot", "url_en": f"https://www.binance.com/en/trade/{m['binance']}?type=spot"}
    # 第二顺位 CMC（大叔 11-15 定顺序：币安 → CMC → DexScreener）。CMC 的页面要 slug，没有可靠的免费查法（data-api 不许用），
    # 所以只用核对过的登记表 alpha/cmc_slugs.json（{gecko_id: slug}，Codex 核对后补），没登记的跳过，不猜。
    cmc = (_load(os.path.join(HERE, "cmc_slugs.json"), {}) or {}).get(g or "")
    if cmc and not cmc.startswith("_") and not out["chart"]:
        out["chart"] = {"name": "CMC", "name_en": "CMC", "url": f"https://coinmarketcap.com/currencies/{cmc}/"}
    if t.get("address"):
        try:
            d = _get(f"https://api.dexscreener.com/latest/dex/tokens/{t['address']}", 30)
            ps = [p for p in d.get("pairs") or [] if (p.get("baseToken") or {}).get("address", "").lower() == t["address"].lower()]
            ps.sort(key=lambda p: -((p.get("liquidity") or {}).get("usd") or 0))
            if ps:
                p = ps[0]
                if not out["chart"]:
                    out["chart"] = {"name": "DexScreener", "name_en": "DexScreener", "url": p.get("url")}
                out["snap"] = {"mcap": p.get("marketCap"), "fdv": p.get("fdv"), "vol24": sum(((x.get("volume") or {}).get("h24") or 0) for x in ps),
                               "liq": (p.get("liquidity") or {}).get("usd"), "chg24": (p.get("priceChange") or {}).get("h24"), "pairs": len(ps),
                               "dex": p.get("dexId"), "chain": p.get("chainId"), "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "src": "DexScreener"}
            time.sleep(0.3)
        except Exception:
            pass
    if not out["chart"] and g:
        out["chart"] = {"name": "CoinGecko", "name_en": "CoinGecko", "url": f"https://www.coingecko.com/en/coins/{g}"}
    if not out["chart"] and t.get("sym"):   # 只有代码：按代码搜（可能有同名币，页面上写明）
        out["chart"] = {"name": "DexScreener 按代码搜", "name_en": "DexScreener search", "url": f"https://dexscreener.com/search?q={t['sym']}", "search": True}
    return out


def links(t, slug):
    L = []
    if t and t.get("gecko"):
        L.append({"k": "coingecko", "name": "CoinGecko", "url": f"https://www.coingecko.com/en/coins/{t['gecko']}"})
    if t and t.get("address"):
        # 按合约地址搜（链名对不上会 404，搜索最稳）
        L.append({"k": "dexscreener", "name": "DexScreener", "url": f"https://dexscreener.com/search?q={t['address']}"})
    elif t and t.get("sym"):
        L.append({"k": "dexscreener", "name": "DexScreener", "url": f"https://dexscreener.com/search?q={t['sym']}"})
    if slug:
        L.append({"k": "defillama", "name": "DefiLlama", "url": f"https://defillama.com/protocol/{slug}"})
    return L


def enrich(cards, manual, first_rev):
    """给每张卡写 data.age（项目上线天数）和 data.tok（代币身份、上线天数、看盘入口）。first_rev = {卡 id: 收入数据第一天}。"""
    try:
        protos, parents = directory()
    except Exception as e:
        print("代币信息：DefiLlama 协议列表取不到，跳过", str(e)[:100])
        return
    by_id = {str(p.get("id")): p for p in protos}
    by_slug = {p.get("slug"): p for p in protos if p.get("slug")}
    kids = {}
    for p in protos:
        if p.get("parentProtocol"):
            kids.setdefault(p["parentProtocol"], []).append(p)
    meta = _load(META, {})
    today = dt.date.today()
    lst = lambda p: dt.datetime.fromtimestamp(p["listedAt"], dt.timezone.utc).date().isoformat() if p and p.get("listedAt") else None
    for c in cards:
        d, k = c["data"], c["key"]
        g = k.split(":", 1)[1] if ":" in k else ""
        if k.startswith("x:"):
            g = d.get("slug") or ""
        mn = manual.get(k) or {}
        if mn.get("llama"):
            g = mn["llama"]
        self_p = by_id.get(g) or by_slug.get(g) or by_slug.get(d.get("slug") or "")
        par_id = g if g.startswith("parent#") else (self_p or {}).get("parentProtocol")
        group = kids.get(par_id, []) if par_id else ([self_p] if self_p else [])
        # 项目上线：最早的一天
        cand = []
        for p in group:
            if lst(p):
                cand.append((lst(p), "DefiLlama 收录"))
        if first_rev.get(c["id"]):
            cand.append((first_rev[c["id"]], "协议收入数据首日"))
        for b in d.get("boards") or []:
            if b.get("since"):
                cand.append((b["since"], "本站板块首次记录"))
        if d.get("listed"):
            cand.append((d["listed"], "DefiLlama 收录"))
        if mn.get("launched"):
            cand.append((mn["launched"], "官方上线日（手动登记）"))
        cand = [x for x in cand if x[0]]
        if cand:
            day, basis = min(cand)
            d["age"] = {"since": day, "days": (today - dt.date.fromisoformat(day)).days, "basis": basis}
        # 代币：本协议优先，其次母协议，其次同组子协议
        # 本协议、母协议、同组子协议各自登记的字段合起来（子协议常只写代码不写 gecko_id，如 Pons V2）
        srcs = [tok_of(self_p), tok_of(parents.get(par_id))] + [tok_of(p) for p in group]
        srcs = [x for x in srcs if x]
        t = None
        if srcs:
            t = {f: next((x[f] for x in srcs if x.get(f)), None) for f in ("gecko", "sym", "address", "chain")}
        if mn.get("gecko") or mn.get("address"):
            t = {"gecko": mn.get("gecko"), "sym": mn.get("sym"), "address": mn.get("address"), "chain": mn.get("chain")}
        if t:
            fd = first_day(t.get("gecko"), meta) if t.get("gecko") else None
            t["first"] = (fd or {}).get("first")
            t["first_src"] = (fd or {}).get("src")
            t["days"] = (today - dt.date.fromisoformat(t["first"])).days if t["first"] else None
            pn = (parents.get(par_id) or {}).get("name") or ""
            t["parent"] = bool(par_id and pn and pn.lower() != c["name"].lower())   # 卡片是子产品、币是母协议的（如 Pendle Loop → PENDLE）
            t["parent_name"] = pn if t["parent"] else None
            t["links"] = links(t, d.get("slug"))
            try:
                t.update(market(t, meta))
            except Exception as e:
                print("看盘入口失败", t.get("sym"), str(e)[:80])
            d["tok"] = t
        else:
            d["tok"] = None
    json.dump(meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
