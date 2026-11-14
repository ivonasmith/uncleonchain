#!/usr/bin/env python3
"""核心选币名单（选币规则 v1，core/research/选币规则_v1.md；配置 core/core_classes.json）。只用标准库。

输入：data/core/core_latest.json（core_daily.py 产出的币安全口径成交额榜、价格）+ DefiLlama 协议类别 / 收入 + CoinGecko meme 类目 + DefiLlama 公链列表。
输出：data/core/universe.json（当天名单 + 全部候选的归类与理由）、data/core/universe_history.json（每天冻结一份名单，不回改）。
规则：
  入场 = 币安上市 + 近 90 天合并成交额排名中位数 ≤ 100（原观测池例外，标“流动性不足”）；
  五大类按价格的真实驱动力判，人工指定优先（core_classes.json 的 manual），其次 ETF 表、DefiLlama 收入与类别、公链列表、meme 类目；
  共识储备型全列，其余每个子类按流动性（中位排名）取前 3，现金流有用型另加原观测池；都不沾的 = 中间态，不观测。
"""
import json, os, sys, time
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import core_daily as C   # noqa: E402

CFG = json.load(open(os.path.join(HERE, "core_classes.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "data", "core")
CLASSES = ["共识储备型", "主流公链型", "现金流有用型", "博弈控盘型", "注意力情绪型"]


def cached(name, fn, ttl_h=20):
    p = os.path.join(C.CACHE, f"univ_{name}.json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < ttl_h * 3600:
        return json.load(open(p))
    v = fn()
    os.makedirs(C.CACHE, exist_ok=True)
    json.dump(v, open(p, "w"))
    return v


def llama_by_symbol():
    protos = C.get(f"{C.LLAMA}/protocols")
    rev = C.get(f"{C.LLAMA}/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue")["protocols"]
    hold = C.get(f"{C.LLAMA}/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyHoldersRevenue")["protocols"]
    r30 = {x["slug"]: x.get("total30d") or 0 for x in rev if x.get("slug")}
    h30 = {x["slug"]: x.get("total30d") or 0 for x in hold if x.get("slug")}
    h1y = {x["slug"]: x.get("total1y") or 0 for x in hold if x.get("slug")}
    out = {}
    for p in protos:
        s = (p.get("symbol") or "").upper()
        if not s or s == "-":
            continue
        o = out.setdefault(s, {"rev30": 0, "hold30": 0, "hold1y": 0, "cats": {}, "names": []})
        sl = p["slug"]
        o["rev30"] += r30.get(sl, 0)
        o["hold30"] += h30.get(sl, 0)
        o["hold1y"] += h1y.get(sl, 0)
        c = p.get("category")
        o["cats"][c] = o["cats"].get(c, 0) + max(r30.get(sl, 0), 1)
        if len(o["names"]) < 3:
            o["names"].append(p["name"])
    for o in out.values():
        o["cat"] = max(o["cats"], key=o["cats"].get) if o["cats"] else None
        del o["cats"]
    return out


def main():
    latest = json.load(open(os.path.join(OUT, "core_latest.json"), encoding="utf-8"))
    vol = (latest.get("market") or {}).get("vol") or {}
    rows = {r["sym"]: r for r in vol.get("rows") or []}
    px = {r["sym"]: r.get("last") for r in (latest.get("market") or {}).get("rows") or []}
    for s, c in (latest.get("coins") or {}).items():
        if c.get("price"):
            px.setdefault(s, c["price"]["last"])
    ll = cached("llama", llama_by_symbol)
    chains = cached("chains", lambda: sorted({(c.get("tokenSymbol") or "").upper() for c in C.get(f"{C.LLAMA}/v2/chains") if c.get("tokenSymbol")}))
    meme = cached("meme", lambda: sorted({x["symbol"].upper() for x in C.get(f"{C.CG}/coins/markets?vs_currency=usd&category=meme-token&per_page=250") or []}))
    etf, eu, manual = set(CFG["etf"]["yes"]), CFG["etf_but_useful"], CFG["manual"]
    sub_of = {c: k for k, cs in CFG["subclass_by_category"].items() for c in cs}
    pool = set(CFG["pool_always"])
    LMAX, RMIN, TOP = CFG["liquidity_med_max"], CFG["min_rev30_usd"], CFG["top_n"]
    cand = {s: r for s, r in rows.items() if r.get("med") is not None and r["med"] <= LMAX}
    for s in pool:
        if s in rows:
            cand.setdefault(s, rows[s])
        else:
            cand.setdefault(s, {"sym": s, "med": None, "cur": None})
    items = []
    for s, r in cand.items():
        L = ll.get(s) or {}
        rev30 = L.get("rev30") or 0
        it = {"sym": s, "med": r.get("med"), "cur": r.get("cur"), "qv30": r.get("qv30"), "fut_share": r.get("fut_share_30d"),
              "vtags": r.get("tags") or [], "rev30": rev30, "hold30": L.get("hold30") or 0, "hold1y": L.get("hold1y") or 0,
              "llama_cat": L.get("cat"), "llama_names": L.get("names"), "tags": [], "liquid": r.get("med") is not None and r["med"] <= LMAX}
        if s in manual:
            m = manual[s]
            it.update({"class": m["class"], "sub": m.get("sub"), "why": "人工：" + m["why"]})
            it["tags"] += m.get("tags", [])
        elif s in etf and s not in eu:
            it.update({"class": "共识储备型", "sub": None, "why": "有美国现货 ETF，协议收入相对市值很小"})
        elif rev30 >= RMIN and sub_of.get(L.get("cat")):
            it.update({"class": "现金流有用型", "sub": sub_of[L["cat"]], "why": f"DefiLlama 近 30 天协议收入 ${rev30/1e6:.1f}M，类别 {L.get('cat')}"})
        elif s in chains:
            it.update({"class": "主流公链型", "sub": None, "why": "主流公链原生币，没有美国现货 ETF"})
        elif s in meme:
            it.update({"class": "注意力情绪型", "sub": "Meme", "why": "CoinGecko meme 类目"})
        elif rev30 >= RMIN:
            it.update({"class": "现金流有用型", "sub": "卖水人过路费", "why": f"有收入 ${rev30/1e6:.1f}M，类别 {L.get('cat')} 未映射，暂归卖水人，待人工复核"})
            it["tags"].append("子类待复核")
        else:
            it.update({"class": None, "sub": None, "why": "中间态：没有 ETF、没有可核实收入、不是公链或 meme，也没有人工归类"})
        if s in etf:
            it["tags"].append("ETF")
        if s in CFG["etf"]["pending"]:
            it["tags"].append("ETF 申请中")
        it["tags"] = list(dict.fromkeys(it["tags"]))
        if it["class"] == "现金流有用型":
            cap = CFG["capture"].get(s)
            if cap:
                it["capture"], it["capture_note"] = cap
            elif it["hold30"] > 0:
                it["capture"], it["capture_note"] = "DefiLlama 有记录·未核", f"近 30 天持有人收入 ${it['hold30']/1e6:.2f}M"
            else:
                it["capture"], it["capture_note"] = "无 / 未核", ""
            ul = CFG["unlock_12m_tokens"].get(s)
            p = px.get(s)
            it["buyback_12m"] = it["hold1y"] or None
            if ul and p:
                it["unlock_12m"] = ul[0] * p
                it["unlock_note"] = ul[1]
                it["scissors"] = (it["buyback_12m"] or 0) - it["unlock_12m"]
        items.append(it)
    # 选人
    key = lambda x: (x["med"] if x["med"] is not None else 999, x["cur"] or 999)
    picked = set()
    for it in items:
        if it["class"] == "共识储备型" and it["liquid"]:
            picked.add(it["sym"]); it["pick"] = "共识储备型全列"
    groups = {}
    for it in items:
        if it["class"] and it["class"] != "共识储备型" and it["liquid"]:
            groups.setdefault((it["class"], it["sub"]), []).append(it)
    for (cl, sub), xs in groups.items():
        for i, it in enumerate(sorted(xs, key=key)):
            if i < TOP:
                picked.add(it["sym"]); it["pick"] = f"{sub or cl}按流动性第 {i + 1}"
            else:
                it.setdefault("miss", f"{sub or cl}第 {i + 1}，只取前 {TOP}")
    for it in items:
        if it["sym"] in pool and it["sym"] not in picked:
            picked.add(it["sym"]); it["pick"] = "原观测池保留"
            if not it["liquid"]:
                it["tags"].append("流动性不足")
        if it["class"] is None:
            it["miss"] = it["why"]
        it["in"] = it["sym"] in picked
    items.sort(key=lambda x: (not x["in"], CLASSES.index(x["class"]) if x["class"] in CLASSES else 9, x.get("sub") or "", key(x)))
    day = (vol.get("last_day") or latest.get("last_complete_day"))
    res = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "data_day": day, "rules": "core/research/选币规则_v1.md",
           "liquidity_med_max": LMAX, "count": len(picked), "by_class": {c: sum(1 for i in items if i["in"] and i["class"] == c) for c in CLASSES},
           "items": items}
    json.dump(C.clean(res), open(os.path.join(OUT, "universe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    hp = os.path.join(OUT, "universe_history.json")
    hist = json.load(open(hp, encoding="utf-8")) if os.path.exists(hp) else []
    if not any(h["date"] == day for h in hist):        # 写入即冻结，同日不覆盖
        hist.append({"date": day, "members": [[i["sym"], i["class"], i.get("sub")] for i in items if i["in"]]})
        json.dump(hist, open(hp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    C.log(f"名单 {len(picked)} 个：" + "；".join(f"{c} {res['by_class'][c]}" for c in CLASSES))


if __name__ == "__main__":
    main()
