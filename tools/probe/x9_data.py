#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X9 数据源实测（只读，Actions 上跑）：① TokenEarly 公开接口真假 ② CoinGecko 前 50 交易所快照 ③ CCXT 对各所 K 线能回溯多久。
结果写 x9_probe_out.json（工作流作为 artifact 上传）并打印摘要。"""
import json, re, sys, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/html,*/*"}
OUT = {"tokenearly": [], "coingecko_top": [], "ccxt": []}


def get(url, n=400):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
            b = r.read()
            return r.status, r.headers.get("content-type", ""), b
    except urllib.error.HTTPError as e:
        return e.code, "", e.read()[:n]
    except Exception as e:
        return "ERR", "", str(e).encode()[:n]


# ① TokenEarly：Grok 说有不用 key 的 listings.json；Codex 说只看到网页。先抓首页找接口线索，再试常见路径
st, ct, home = get("https://tokenearly.com/en")
hints = sorted(set(re.findall(rb"[\"'(]((?:https?://[^\"' )]*tokenearly[^\"' )]*)?/[^\"' )]*(?:listings?|api|feed)[^\"' )]*\.json[^\"' )]*)", home)))[:20]
OUT["tokenearly"].append({"url": "https://tokenearly.com/en", "status": st, "json_hints": [h.decode("utf-8", "replace") for h in hints]})
cands = [h.decode("utf-8", "replace") for h in hints] + ["/listings.json", "/api/listings.json", "/en/listings.json", "/data/listings.json", "/api/v1/listings", "/api/listings"]
for c in dict.fromkeys(cands):
    u = c if c.startswith("http") else "https://tokenearly.com" + c
    st, ct, b = get(u)
    rec = {"url": u, "status": st, "type": ct, "head": b[:300].decode("utf-8", "replace")}
    try:
        j = json.loads(b)
        items = j if isinstance(j, list) else next((v for v in j.values() if isinstance(v, list)), [])
        rec["n_items"] = len(items)
        rec["sample"] = items[:2]
        rec["exchanges"] = sorted({str(i.get("exchange") or i.get("source") or "") for i in items if isinstance(i, dict)})[:40]
    except Exception:
        pass
    OUT["tokenearly"].append(rec)
    time.sleep(0.3)

# ② CoinGecko 交易所排名（免费公开接口，按 24h 成交额 BTC 计）
st, ct, b = get("https://api.coingecko.com/api/v3/exchanges?per_page=70&page=1")
try:
    for i, x in enumerate(json.loads(b), 1):
        OUT["coingecko_top"].append({"rank": i, "id": x["id"], "name": x["name"], "vol24_btc": x.get("trade_volume_24h_btc"),
                                     "trust": x.get("trust_score"), "country": x.get("country"), "year": x.get("year_established"), "centralized": x.get("centralized", True)})
except Exception as e:
    OUT["coingecko_top"] = [{"error": f"{st} {str(e)[:120]} {b[:200]!r}"}]

# ③ CCXT：前 70 里每家，能否 fetchOHLCV、1 分钟回溯 180 天 / 1 小时回溯 365 天能拿到什么
try:
    import ccxt
    names = {e.lower(): e for e in ccxt.exchanges}
    now = int(time.time() * 1000)
    for x in OUT["coingecko_top"][:70]:
        cid = next((names[k] for k in (x.get("id", "").lower().replace("_", ""), x.get("name", "").lower().replace(" ", "").replace(".", "")) if k in names), None)
        rec = {"name": x.get("name"), "ccxt_id": cid}
        if cid:
            try:
                ex = getattr(ccxt, cid)({"timeout": 15000, "enableRateLimit": True})
                rec["has_ohlcv"] = ex.has.get("fetchOHLCV")
                mk = ex.load_markets()
                sym = next((s for s in ("BTC/USDT", "BTC/USD", "BTC/KRW", "BTC/EUR") if s in mk), None)
                rec["markets"] = len(mk)
                rec["symbol"] = sym
                for tf, days in (("1m", 180), ("1h", 365)):
                    try:
                        rows = ex.fetch_ohlcv(sym, tf, since=now - days * 86400000, limit=3) if sym else []
                        rec[f"{tf}_{days}d_first"] = (time.strftime("%Y-%m-%d %H:%M", time.gmtime(rows[0][0] / 1000)) if rows else None)
                    except Exception as e:
                        rec[f"{tf}_{days}d_first"] = "ERR " + str(e)[:80]
            except Exception as e:
                rec["error"] = str(e)[:120]
        OUT["ccxt"].append(rec)
except Exception as e:
    OUT["ccxt"] = [{"error": "ccxt 不可用 " + str(e)[:120]}]

json.dump(OUT, open("x9_probe_out.json", "w"), ensure_ascii=False, indent=1)
print("== TokenEarly")
for r in OUT["tokenearly"]:
    print(r.get("status"), r["url"], "| 条数", r.get("n_items"), "| 所", r.get("exchanges"), "| hints", r.get("json_hints"), "|", (r.get("head") or "")[:120].replace("\n", " "))
print("== CoinGecko 前 70:", len(OUT["coingecko_top"]))
for x in OUT["coingecko_top"][:70]:
    print(x)
print("== CCXT")
for r in OUT["ccxt"]:
    print(r)
