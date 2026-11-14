#!/usr/bin/env python3
"""Alpha 雷达 · 日更（只用标准库）。

方法论：alpha/research/Alpha标的筛选研究体系.md（Codex 2026-11-14 交付全面版，网站版去掉执行纪律）。
这一版只接「日级、协议级」的发现源，不点名小市值代币：
  ① 无币协议收入榜   DefiLlama dailyRevenue × 协议列表：本协议和母协议都没有代币、近 30 天协议收入 ≥ 门槛（按母协议合并）
  ② 新上架协议       DefiLlama 协议列表 listedAt 在最近 N 天
  ③ 事件流（A2，Codex T1 验收后 11-14 接）：ethresear.ch 新帖、Snapshot 治理提案（大空间 + 价值捕获关键词）、Binance 上新公告（剔除 TradFi / 代币化股票）
     → data/alpha/alpha_feed.json（只追加：原始发布时间 + 本方首次发现时间，发现延迟 = 两者之差）
线索台账（第十三章「保留全部分母」）：进过 ①② 的对象都登记一条，只追加不删除；之后每天回查是否发币（token 出现）。

输出（data/alpha/）：
  alpha_latest.json   今天的雷达读数 + 事件
  alpha_leads.json    线索台账（首次发现日、首次读数、发币日；不删不改历史字段）
  alpha_history.json  每天一行（样本外，不回填）
参数：alpha/alpha_config.json。用法：python3 alpha/alpha_daily.py
"""
import json, os, re, sys, time, urllib.request
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.environ.get("ALPHA_OUT") or os.path.join(ROOT, "data", "alpha")
CFG = json.load(open(os.path.join(HERE, "alpha_config.json"), encoding="utf-8"))
LLAMA = "https://api.llama.fi"
UA = {"User-Agent": "uncleonchain-alpha/1.0"}


def get(url, tries=3, timeout=90):
    err = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.load(r)
        except Exception as e:   # 网络抖动重试
            err = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url}: {err}")


def load(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def dump(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def post(url, body, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=dict(UA, **{"content-type": "application/json"}))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")


def feed_ethresearch(fc):
    d = get("https://ethresear.ch/latest.json")
    cut = time.time() - fc["window_days"] * 86400
    out = []
    for t in d["topic_list"]["topics"]:
        c = dt.datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
        if c.timestamp() < cut or t.get("pinned"):
            continue   # latest 按最后活动排序：只收窗口内新开的帖，旧帖被顶上来不算新
        out.append({"id": f"ethr:{t['id']}", "src": "ethresearch", "title": t["title"], "url": f"https://ethresear.ch/t/{t['slug']}/{t['id']}",
                    "created": c.isoformat(timespec="seconds"), "extra": {"posts": t.get("posts_count"), "views": t.get("views")}})
    return out


def feed_snapshot(fc):
    since = int(time.time() - fc["window_days"] * 86400)
    q = ("{proposals(first:1000,orderBy:\"created\",orderDirection:desc,where:{created_gte:%d})"
         "{id title created end state link space{id name followersCount verified}}}" % since).replace('\\"', '"')
    d = post("https://hub.snapshot.org/graphql", {"query": q})
    kw = re.compile(fc["snapshot_keywords"], re.I)
    out = []
    for x in d["data"]["proposals"]:
        sp = x.get("space") or {}
        if (sp.get("followersCount") or 0) < fc["snapshot_min_followers"] or not kw.search(x["title"] or ""):
            continue
        out.append({"id": f"snap:{x['id']}", "src": "snapshot", "title": x["title"], "url": x.get("link") or f"https://snapshot.box/#/{sp.get('id')}/proposal/{x['id']}",
                    "created": iso(x["created"]), "extra": {"space": sp.get("name") or sp.get("id"), "followers": sp.get("followersCount"), "end": iso(x["end"]) if x.get("end") else None}})
    return out


def feed_binance(fc):
    d = get("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=1&pageSize=20&catalogId=48")
    keep, drop = re.compile(fc["binance_keep"], re.I), re.compile(fc["binance_drop"], re.I)
    out = []
    for c in d["data"]["catalogs"]:
        for a in c.get("articles") or []:
            if not keep.search(a["title"]) or drop.search(a["title"]):
                continue
            out.append({"id": f"bn:{a['id']}", "src": "binance", "title": a["title"], "url": f"https://www.binance.com/en/support/announcement/{a['code']}",
                        "created": iso(a["releaseDate"] / 1000), "extra": {}})
    return out


def has_tok(p):
    return bool(p.get("gecko_id") or (p.get("symbol") or "-") not in ("-", ""))


def main():
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date().isoformat()
    asof = (now.date() - dt.timedelta(days=1)).isoformat()   # DefiLlama 30 天窗口截至前一个完整 UTC 日
    src = {}
    try:
        protos = get(f"{LLAMA}/protocols")
        src["defillama_protocols"] = {"ok": True, "n": len(protos)}
    except Exception as e:
        print("协议列表失败：", e)
        src["defillama_protocols"] = {"ok": False, "err": str(e)[:200]}
        protos = None
    try:
        rev = get(f"{LLAMA}/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue")["protocols"]
        src["defillama_revenue"] = {"ok": True, "n": len(rev)}
    except Exception as e:
        print("收入失败：", e)
        src["defillama_revenue"] = {"ok": False, "err": str(e)[:200]}
        rev = None

    prev = load(os.path.join(OUT, "alpha_latest.json"), {})
    leads = load(os.path.join(OUT, "alpha_leads.json"), {"leads": {}})
    hist = load(os.path.join(OUT, "alpha_history.json"), [])
    L = leads["leads"]
    baseline = not L          # 第一次跑：今天全部记为基线，不算「首次进榜」
    events = []

    if protos is None:        # 主数据源失败：保留上次读数并标 stale，不写台账
        if prev:
            prev.update(stale=True, sources=src, generated=now.isoformat(timespec="seconds"))
            dump(os.path.join(OUT, "alpha_latest.json"), prev)
        print("协议列表取不到，沿用上次结果")
        return

    byid = {p["id"]: p for p in protos}
    ptok = {}                 # 母协议 → 旗下任一子协议有代币
    for p in protos:
        if p.get("parentProtocol"):
            ptok[p["parentProtocol"]] = ptok.get(p["parentProtocol"], False) or has_tok(p)

    def group_tok(gkey):      # g:parent#x / g:id
        if gkey.startswith("parent#"):
            return ptok.get(gkey)
        p = byid.get(gkey)
        return None if p is None else (has_tok(p) or bool(p.get("parentProtocol") and ptok.get(p["parentProtocol"])))

    # ① 无币协议收入榜
    tc = CFG["tokenless"]
    groups, allrev = {}, {}
    if rev is not None:
        for x in rev:
            pid = x.get("defillamaId")
            pp = byid.get(pid)
            par = x.get("parentProtocol") or (pp or {}).get("parentProtocol")
            if pp is None:
                continue           # 协议列表里对不上身份的不收（不猜）
            tok = has_tok(pp) or bool(par and ptok.get(par))
            allrev[par or pid] = allrev.get(par or pid, 0.0) + (x.get("total30d") or 0)   # 全部协议（含有币），给台账做结果追踪
            if tok or x.get("category") in tc["exclude_categories"] or x.get("name") in tc["exclude_names"]:
                continue
            g = groups.setdefault(par or pid, {"key": par or pid, "children": [], "rev30": 0.0, "rev_prev30": 0.0, "cats": {}, "chains": {}})
            r30, r60 = x.get("total30d") or 0, x.get("total60dto30d") or 0
            g["rev30"] += r30
            g["rev_prev30"] += r60
            g["children"].append({"name": x.get("name"), "slug": x.get("slug"), "rev30": round(r30)})
            g["cats"][x.get("category")] = g["cats"].get(x.get("category"), 0) + r30
            for c in x.get("chains") or []:
                g["chains"][c] = g["chains"].get(c, 0) + r30
    rows = []
    for g in groups.values():
        if g["rev30"] < tc["min_rev30_usd"]:
            continue
        g["children"].sort(key=lambda c: -c["rev30"])
        top = g["children"][0]
        name = top["name"] if len(g["children"]) == 1 else g["key"].split("#", 1)[-1].replace("-", " ").title()
        rows.append({"key": "g:" + g["key"], "name": name, "slug": top["slug"],
                     "children": [c["name"] for c in g["children"]],
                     "category": max(g["cats"], key=g["cats"].get),
                     "chains": [c for c, _ in sorted(g["chains"].items(), key=lambda t: -t[1])][:3],
                     "rev30": round(g["rev30"]), "rev_prev30": round(g["rev_prev30"]),
                     "chg30": round((g["rev30"] / g["rev_prev30"] - 1) * 100, 1) if g["rev_prev30"] > 0 else None})
    rows.sort(key=lambda r: -r["rev30"])

    # ② 新上架协议
    days = CFG["listings"]["days"]
    cut = now.timestamp() - days * 86400
    lst = []
    for p in protos:
        if (p.get("listedAt") or 0) >= cut:
            par = p.get("parentProtocol")
            lst.append({"key": "p:" + p["id"], "name": p.get("name"), "slug": p.get("slug"), "category": p.get("category"),
                        "chains": (p.get("chains") or [])[:3], "tvl": round(p.get("tvl") or 0),
                        "listed": dt.datetime.fromtimestamp(p["listedAt"], dt.timezone.utc).date().isoformat(),
                        "token": has_tok(p) or bool(par and ptok.get(par)), "parent": par})
    lst.sort(key=lambda r: (r["listed"], r["tvl"]), reverse=True)

    # 台账：首次出现登记；之后只更新 last_seen / 发币日
    def reg(r, source, metric):
        k = r["key"]
        if k not in L:
            L[k] = {"key": k, "name": r["name"], "slug": r.get("slug"), "source": source, "first_seen": today,
                    "baseline": baseline, "first": metric, "tokenless_at_first": not r.get("token", False),
                    "status": "原始线索", "token_seen": None, "last_seen": today}
            if not baseline:
                events.append({"type": "new_rank" if source == "tokenless_rev" else "new_listing", "key": k, "name": r["name"], **metric})
        else:
            L[k]["last_seen"] = today
            if source not in L[k]["source"].split("+"):
                L[k]["source"] += "+" + source
    for r in rows:
        reg(r, "tokenless_rev", {"rev30": r["rev30"], "chg30": r["chg30"], "category": r["category"]})
    for r in lst:
        reg(r, "new_listing", {"tvl": r["tvl"], "category": r["category"], "listed": r["listed"]})
    # 发币回查：首次发现时无币、现在有代币
    for k, v in L.items():
        if not v.get("tokenless_at_first") or v.get("token_seen"):
            continue
        t = group_tok(k[2:]) if k.startswith("g:") else (lambda p: None if p is None else (has_tok(p) or bool(p.get("parentProtocol") and ptok.get(p["parentProtocol"]))))(byid.get(k[2:]))
        if t:
            v["token_seen"] = today
            events.append({"type": "token", "key": k, "name": v["name"]})

    # 候选池状态：外部补证结果（alpha/review/*_checks.json）并进台账；状态变化只追加到 status_history，不改旧记录
    for fn in sorted(os.listdir(os.path.join(HERE, "review"))):
        if not fn.endswith("_checks.json"):
            continue
        for c in load(os.path.join(HERE, "review", fn), []):
            v = L.get(c.get("key"))
            if not v or c.get("verdict") not in ("待核验", "研究观察", "拒绝", "优先研究"):
                continue
            day = (c.get("checked_utc") or today)[:10]
            hs = v.setdefault("status_history", [])
            if hs and hs[-1]["status"] == c["verdict"]:
                continue
            hs.append({"status": c["verdict"], "date": day, "src": f"alpha/review/{fn}"})
            v["status"] = c["verdict"]
            events.append({"type": "status", "key": c["key"], "name": v["name"], "status": c["verdict"]})

    # ③ 事件流
    fc = CFG["feeds"]
    feed = load(os.path.join(OUT, "alpha_feed.json"), {"items": {}})
    FI = feed["items"]
    feed_base = not FI          # 第一次跑：已经发布的都记基线，发现延迟没有意义
    feed_new = 0
    for name, fn in (("ethresearch", feed_ethresearch), ("snapshot", feed_snapshot), ("binance", feed_binance)):
        try:
            got = fn(fc)
            src[name] = {"ok": True, "n": len(got)}
        except Exception as e:
            print(f"{name} 失败：", e)
            src[name] = {"ok": False, "err": str(e)[:200]}
            continue
        for it in got:
            if it["id"] not in FI:
                it["first_seen"] = now.isoformat(timespec="seconds")
                it["delay_h"] = None if feed_base else round((now - dt.datetime.fromisoformat(it["created"])).total_seconds() / 3600, 1)
                it["baseline"] = feed_base
                FI[it["id"]] = it
                feed_new += 1
    fcut = (now - dt.timedelta(days=fc["window_days"])).isoformat()
    feed_recent = sorted((v for v in FI.values() if v["created"] >= fcut), key=lambda v: v["created"], reverse=True)

    first = {k: v["first_seen"] for k, v in L.items()}
    for r in rows:
        r["first_seen"] = first.get(r["key"])
    out = {"generated": now.isoformat(timespec="seconds"), "asof": asof, "stale": rev is None,
           "baseline_day": min((v["first_seen"] for v in L.values() if v.get("baseline")), default=today),
           "sources": src, "params": {"min_rev30_usd": tc["min_rev30_usd"], "listing_days": days},
           "tokenless": rows, "listings": lst, "events": events, "feed": feed_recent,
           "ledger": {"n": len(L), "tokenless_rev": sum(1 for v in L.values() if "tokenless_rev" in v["source"]),
                      "new_listing": sum(1 for v in L.values() if "new_listing" in v["source"]),
                      "token_seen": sum(1 for v in L.values() if v.get("token_seen")),
                      "status": {st: sum(1 for v in L.values() if v.get("status") == st) for st in ("待核验", "研究观察", "优先研究", "拒绝")}}}
    if rev is None and prev:       # 收入源失败：榜单沿用上次
        out["tokenless"] = prev.get("tokenless", [])
    row = {"date": today, "asof": asof, "baseline": baseline, "n_tokenless": len(rows), "rev30_sum": round(sum(r["rev30"] for r in rows)),
           "n_listings": len(lst), "n_leads": len(L), "feed_new": feed_new,
           "src_ok": {k: bool(v.get("ok")) for k, v in src.items()}, "events": {t: sum(1 for e in events if e["type"] == t) for t in ("new_rank", "new_listing", "token", "status")},
           # A4 结果追踪：台账里每个协议组今天的 30 天收入（含已发币、跌出门槛的；取不到 = 不记，不当 0）
           "rev30": {k: round(allrev[k[2:]]) for k in L if k.startswith("g:") and k[2:] in allrev} if rev is not None else None}
    hist = [h for h in hist if h["date"] != today] + [row]
    dump(os.path.join(OUT, "alpha_latest.json"), out)
    dump(os.path.join(OUT, "alpha_leads.json"), leads)
    dump(os.path.join(OUT, "alpha_feed.json"), feed)
    dump(os.path.join(OUT, "alpha_history.json"), hist)
    print(f"无币协议 {len(rows)} 个 · 新上架 {len(lst)} 个 · 台账 {len(L)} 条 · 事件 {len(events)} · 事件流新增 {feed_new}（{', '.join(f'{k}:{v.get("n", "失败")}' for k, v in src.items())}）")


if __name__ == "__main__":
    main()
    try:   # 机会卡（应用层）：雷达 + 自动打分 + 研究补证 → data/alpha/opps.json
        import opps
        opps.main()
    except Exception as e:
        print("机会卡生成失败：", e)
