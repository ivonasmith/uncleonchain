#!/usr/bin/env python3
"""RWA 板块 · 日更（只用标准库）。

自动层只接免费、可再分发的公开接口，回答「规模在哪、谁在收钱、哪些有平台币」：
  ① 资产类规模    CoinGecko 分类市值（/coins/categories）+ 各分类成员（/coins/markets）：前几名、第一名占比
                  分类之间有包含 / 重叠（黄金 ⊂ 商品、货币基金 ≈ 国债），页面不求和
  ② 平台币 / 协议币 CoinGecko「RWA Protocol」分类成员，身份特殊的在 rwa_config.json 的 coin_roles 注明
  ③ 谁在收钱      DefiLlama RWA 类协议（+ 按业务纳入的 Maple / Figure）近 30 天手续费、协议收入、持有人收入，按母协议合并；
                  传统机构产品（Grayscale ETF 管理费等）单列，不算进链上协议合计
研究层（人工 / Codex 核对后并入）：rwa/research/watchlist.json，这里只做校验和新鲜度判断，不改内容。

输出（data/rwa/）：
  rwa_latest.json   当前读数（某个源失败 = 沿用上次结果并标 stale + 上次成功时间）
  rwa_history.json  每次运行一行（样本外，不回填；记录采样时刻，相邻两行之差 ≠ 24 小时变化）
用法：python3 rwa/rwa_daily.py
"""
import json, os, time, urllib.request
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.environ.get("RWA_OUT") or os.path.join(ROOT, "data", "rwa")
CFG = json.load(open(os.path.join(HERE, "rwa_config.json"), encoding="utf-8"))
CG = "https://api.coingecko.com/api/v3"
LLAMA = "https://api.llama.fi"
UA = {"User-Agent": "uncleonchain-rwa/1.0", "Accept": "application/json"}
STATES = {"pending_recheck", "watch", "waiting_evidence", "conditions_met", "invalidated", "historical"}
PT_STATUS = {"issued", "declared_none", "unverified", "tradfi", "n/a"}


def get(url, tries=4, timeout=90, pause=0):
    err = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                out = json.load(r)
            if pause:
                time.sleep(pause)        # CoinGecko 免费接口限流
            return out
        except Exception as e:
            err = e
            time.sleep(8 * (i + 1) if "429" in str(e) else 3 * (i + 1))
    raise RuntimeError(f"{url}: {err}")


def load(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def dump(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)                  # 原子替换：写一半失败不会留下坏文件


def has_tok(p):
    return bool(p.get("gecko_id") or (p.get("symbol") or "-") not in ("-", ""))


# ---------------------------------------------------------------- ① ② CoinGecko
def fetch_cg(now):
    cats = {c["id"]: c for c in get(f"{CG}/coins/categories", pause=3)}
    rows, platform, asset_ids = [], [], set()
    roles = CFG.get("coin_roles", {})
    for c in CFG["categories"]:
        x = cats.get(c["id"])
        if not x:
            rows.append(dict(c, missing=True))
            continue
        mem = get(f"{CG}/coins/markets?vs_currency=usd&category={c['id']}&per_page=250&order=market_cap_desc", pause=6)
        trunc = len(mem) >= 250           # 一页 250 个封顶：成员数写「≥250」
        mem = [m for m in mem if (m.get("market_cap") or 0) > 0]
        if c["role"] == "asset" and not c.get("no_identity"):
            asset_ids.update(m["id"] for m in mem)
        tot = sum(m["market_cap"] for m in mem) or None
        top = [{"id": m["id"], "sym": (m.get("symbol") or "").upper(), "name": m.get("name"), "mcap": round(m["market_cap"]),
                "share": round(m["market_cap"] / tot * 100, 1) if tot else None, "vol24": round(m.get("total_volume") or 0),
                "role": roles.get(m["id"])} for m in mem[:5]]
        rows.append(dict(c, mcap=round(x.get("market_cap") or 0) or None, chg24=x.get("market_cap_change_24h"),
                         vol24=round(x.get("volume_24h") or 0) or None, n=len(mem), truncated=trunc, members_mcap=round(tot) if tot else None,
                         top=top, cg_updated=x.get("updated_at")))
        if c["id"] == "rwa-protocol":
            for m in mem[:40]:
                platform.append({"id": m["id"], "sym": (m.get("symbol") or "").upper(), "name": m.get("name"), "mcap": round(m["market_cap"]),
                                 "fdv": round(m["fully_diluted_valuation"]) if m.get("fully_diluted_valuation") else None,
                                 "vol24": round(m.get("total_volume") or 0), "chg24": m.get("price_change_percentage_24h"),
                                 "role": roles.get(m["id"]), "updated": m.get("last_updated")})
    return rows, platform, sorted(asset_ids)


# ---------------------------------------------------------------- ③ DefiLlama
def fetch_llama(asset_ids):
    protos = get(f"{LLAMA}/protocols")
    dims = {}
    for t in ("dailyFees", "dailyRevenue", "dailyHoldersRevenue"):
        dims[t] = {x.get("defillamaId"): x for x in get(f"{LLAMA}/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType={t}")["protocols"]}
    lc = CFG["llama"]
    tradfi = set(lc.get("tradfi", []))
    ptok = {}
    for p in protos:
        if p.get("parentProtocol") and has_tok(p):
            ptok.setdefault(p["parentProtocol"], {"symbol": p.get("symbol"), "gecko_id": p.get("gecko_id")})
    groups = {}
    for p in protos:
        par = p.get("parentProtocol")
        if p.get("category") not in lc["categories"] and par not in lc.get("extra", {}):
            continue
        kind = "tradfi" if p.get("name") in tradfi else "onchain"
        key = (par or p["id"]) + ("|tradfi" if kind == "tradfi" else "")
        g = groups.setdefault(key, {"key": key, "parent": par, "kind": kind, "children": [], "tvl": 0.0, "chains": {},
                                    "fees30": 0.0, "rev30": 0.0, "hrev30": 0.0, "fees_prev30": 0.0, "has_fees": False, "token": None})
        f = dims["dailyFees"].get(p["id"]) or {}
        r = dims["dailyRevenue"].get(p["id"]) or {}
        h = dims["dailyHoldersRevenue"].get(p["id"]) or {}
        g["has_fees"] |= bool(f or r)
        g["fees30"] += f.get("total30d") or 0
        g["fees_prev30"] += f.get("total60dto30d") or 0
        g["rev30"] += r.get("total30d") or 0
        g["hrev30"] += h.get("total30d") or 0
        g["tvl"] += p.get("tvl") or 0
        for ch in p.get("chains") or []:
            g["chains"][ch] = g["chains"].get(ch, 0) + 1
        g["children"].append({"name": p.get("name"), "slug": p.get("slug"), "fees30": round(f.get("total30d") or 0), "category": p.get("category")})
        if has_tok(p):
            g["token"] = {"symbol": p.get("symbol"), "gecko_id": p.get("gecko_id")}
    rows = []
    for g in groups.values():
        if not g["has_fees"] and g["tvl"] < 1e6:
            continue                    # 没有手续费数据、TVL 也不到 100 万：不上表（分母仍记在 n_seen）
        g["children"].sort(key=lambda c: -c["fees30"])
        top = g["children"][0]
        name = top["name"] if len(g["children"]) == 1 else (g["parent"] or "").split("#", 1)[-1].replace("-", " ").title()
        tok = g["token"] or (ptok.get(g["parent"]) if g["parent"] else None)
        st = "tradfi" if g["kind"] == "tradfi" else ("registered" if tok else "not_registered")
        # DefiLlama 的 symbol 是「协议登记的代币」，发行方常登记成资产币本身（Tether Gold → XAUt）：和 CoinGecko 资产类成员对上、或人工注明的，改记资产币
        ov = lc.get("token_overrides", {}).get(g["parent"] or top["name"])
        if tok and st == "registered" and ov != "registered" and (ov == "asset_token" or (tok.get("gecko_id") and tok["gecko_id"] in asset_ids)):
            st = "asset_token"
        rows.append({"key": g["key"], "name": name, "slug": top["slug"], "kind": g["kind"], "children": [c["name"] for c in g["children"]],
                     "chains": [c for c, _ in sorted(g["chains"].items(), key=lambda t: -t[1])][:3],
                     "category": top["category"], "tvl": round(g["tvl"]) or None,
                     "fees30": round(g["fees30"]) if g["has_fees"] else None, "rev30": round(g["rev30"]) if g["has_fees"] else None,
                     "hrev30": round(g["hrev30"]) if g["has_fees"] else None,
                     "chg30": round((g["fees30"] / g["fees_prev30"] - 1) * 100, 1) if g["fees_prev30"] > 0 else None,
                     "token_status": st, "token": tok})
    rows.sort(key=lambda r: (-(r["fees30"] or 0), -(r["tvl"] or 0)))
    on = [r for r in rows if r["kind"] == "onchain"]
    tf = [r for r in rows if r["kind"] == "tradfi"]
    s = lambda xs, k: round(sum(r[k] or 0 for r in xs))
    totals = {"n_seen": len(groups), "n_onchain": len(on), "n_tradfi": len(tf),
              "fees30_onchain": s(on, "fees30"), "rev30_onchain": s(on, "rev30"), "hrev30_onchain": s(on, "hrev30"),
              "fees30_tradfi": s(tf, "fees30"), "rev30_tradfi": s(tf, "rev30"),
              "n_registered": sum(1 for r in on if r["token_status"] == "registered"),
              "n_asset_token": sum(1 for r in on if r["token_status"] == "asset_token"),
              "n_not_registered": sum(1 for r in on if r["token_status"] == "not_registered"),
              "n_hrev_pos": sum(1 for r in on if (r["hrev30"] or 0) > 0)}
    return rows, totals


# ---------------------------------------------------------------- 研究层：校验 + 新鲜度
def research(today):
    w = load(os.path.join(HERE, "research", "watchlist.json"), {})
    items, problems = [], []
    lim = CFG.get("research_stale_days", 14)
    for it in w.get("items", []):
        vs = it.get("versions") or []
        cur = vs[0] if vs else {}
        st = cur.get("state")
        if st not in STATES:
            problems.append(f"{it.get('id')}: 判断状态 {st!r} 不在枚举里")
        pt = (it.get("platform_token") or {}).get("status")
        if pt not in PT_STATUS:
            problems.append(f"{it.get('id')}: 平台币状态 {pt!r} 不在枚举里（原始值保留）")
        rv = cur.get("reviewed_utc")
        age = (dt.date.fromisoformat(today) - dt.date.fromisoformat(rv[:10])).days if rv else None
        fresh = "never" if rv is None else ("stale" if age > lim else "fresh")
        items.append(dict(it, current=cur, fresh=fresh, age_days=age))
    cnt = {}
    for it in items:
        cnt[it["current"].get("state")] = cnt.get(it["current"].get("state"), 0) + 1
    return {"updated_utc": w.get("updated_utc"), "migration": w.get("migration"), "items": items, "counts": cnt,
            "stale_days": lim, "problems": problems}


def main():
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date().isoformat()
    gen = now.isoformat(timespec="seconds")
    prev = load(os.path.join(OUT, "rwa_latest.json"), {})
    hist = load(os.path.join(OUT, "rwa_history.json"), [])
    src = dict(prev.get("sources") or {})
    out = {"generated": gen, "asof_llama": (now.date() - dt.timedelta(days=1)).isoformat()}

    try:
        cats, platform, asset_ids = fetch_cg(now)
        src["coingecko"] = {"ok": True, "last_ok": gen, "n": len(cats)}
        out.update(categories=cats, platform=platform, cg_sampled=gen, asset_ids=asset_ids)
    except Exception as e:
        print("CoinGecko 失败：", e)
        src["coingecko"] = dict(src.get("coingecko") or {}, ok=False, err=str(e)[:200], failed_at=gen)
        out.update(categories=prev.get("categories", []), platform=prev.get("platform", []), cg_sampled=prev.get("cg_sampled"))
        asset_ids = prev.get("asset_ids", [])
    try:
        rows, totals = fetch_llama(set(asset_ids))
        src["defillama"] = {"ok": True, "last_ok": gen, "n": len(rows)}
        out.update(protocols=rows, totals=totals)
    except Exception as e:
        print("DefiLlama 失败：", e)
        src["defillama"] = dict(src.get("defillama") or {}, ok=False, err=str(e)[:200], failed_at=gen)
        out.update(protocols=prev.get("protocols", []), totals=prev.get("totals", {}), asof_llama=prev.get("asof_llama"))
    out["sources"] = src
    out["stale"] = not all(v.get("ok") for v in src.values())
    out["research"] = research(today)

    if not out.get("categories") and not out.get("protocols"):
        print("两个源都没有结果，也没有上次结果：不写文件")
        raise SystemExit(1)

    if src.get("coingecko", {}).get("ok") or src.get("defillama", {}).get("ok"):
        row = {"date": today, "cg_sampled": out.get("cg_sampled") if src["coingecko"].get("ok") else None,
               "cats": {c["id"]: c.get("mcap") for c in out["categories"] if not c.get("missing")} if src["coingecko"].get("ok") else None,
               "llama_asof": out.get("asof_llama") if src.get("defillama", {}).get("ok") else None,
               "totals": out.get("totals") if src.get("defillama", {}).get("ok") else None}
        hist = [h for h in hist if h["date"] != today] + [row]
    dump(os.path.join(OUT, "rwa_latest.json"), out)
    dump(os.path.join(OUT, "rwa_history.json"), hist)
    t = out.get("totals") or {}
    print(f"分类 {len(out['categories'])} · 平台币 {len(out['platform'])} · 协议 {len(out['protocols'])}"
          f"（链上手续费 30 天 ${t.get('fees30_onchain', 0) / 1e6:.1f}M，持有人 ${t.get('hrev30_onchain', 0) / 1e6:.2f}M）"
          f" · 研究条目 {len(out['research']['items'])}{' · 有源失败' if out['stale'] else ''}")
    for p in out["research"]["problems"]:
        print("研究库校验：", p)


if __name__ == "__main__":
    main()
