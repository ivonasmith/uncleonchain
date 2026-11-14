#!/usr/bin/env python3
"""AI Agent 赛道监控 · 日更（只用标准库）。

和 tools/agent-id-cloud（币安 Agent ID 生态链上采集）互补：那边只看 BNB 上 Agent ID 门禁的发射台，这里看整条赛道。
  ① 赛道手续费   DefiLlama 逐日手续费，按四层分（发行 / 服务 / 资管 / 框架，口径在 aiagent_config.json），
                 「AI Agents」类目新收录的协议自动并入（默认层 commerce），全历史从 since 起，只取已结束的 UTC 日。
                 每家算近 30 天、前 30 天、中位日、去掉最高一天后的环比（和 Codex v2 研究同一算法，防单日事件把趋势带偏）。
  ② 代币市值     CoinGecko 分类快照（AI Agents / 发射台 / 框架 / 应用 / Meme），免费接口没有分类历史，所以每天自录、不回填。
  ③ 链上身份     读 public/ai-agent/monitor/core_series.json（Agent ID 采集结果）摘要，不重复采集。
  ④ 生命周期     aiagent_registry.json 人工登记（上线 / 停新 / 转型），页面时间线读它。

输出（data/aiagent/）：
  aiagent_latest.json   当前读数、各协议表、层合计、市值快照、事件
  fees_series.json      逐日手续费：各层合计 + 各协议（全历史，数据源回改就跟着变）
  aiagent_history.json  每天一行（样本外，不回填）：市值快照、层 30 天手续费、Agent ID 累计
用法：python3 aiagent/aiagent_daily.py
"""
import json, os, statistics, sys, time, urllib.request
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.environ.get("AIAGENT_OUT") or os.path.join(ROOT, "data", "aiagent")
CFG = json.load(open(os.path.join(HERE, "aiagent_config.json"), encoding="utf-8"))
LLAMA = "https://api.llama.fi"
CG = "https://api.coingecko.com/api/v3"
UA = {"User-Agent": "uncleonchain-aiagent/1.0", "Accept": "application/json"}


def get(url, tries=3, timeout=90):
    err = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.load(r)
        except Exception as e:   # 网络抖动 / 限频重试
            err = e
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"{url}: {err}")


def load(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def dump(p, obj, indent=1):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":"))


def days(a, b):
    d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    return [(d0 + dt.timedelta(i)).isoformat() for i in range((d1 - d0).days + 1)]


def window(ser, end, n):
    """end 往前 n 天（含 end）的逐日值；缺日返回 None。"""
    ds = days((dt.date.fromisoformat(end) - dt.timedelta(n - 1)).isoformat(), end)
    return [ser.get(d) for d in ds]


def wstats(vals):
    """总额、中位日、最高一天、去峰合计；缺日（None）当作覆盖不全，覆盖天数一并给出。"""
    v = [x for x in vals if x is not None]
    if not v:
        return {"total": None, "median": None, "peak": None, "ex_peak": None, "covered": 0, "days": len(vals)}
    return {"total": sum(v), "median": statistics.median(v), "peak": max(v), "ex_peak": sum(v) - max(v), "covered": len(v), "days": len(vals)}


def pct(a, b):
    return None if a is None or not b else (a / b - 1) * 100


def fee_series(slug):
    d = get(f"{LLAMA}/summary/fees/{slug}?dataType=dailyFees")
    s = {}
    for ts, v in d.get("totalDataChart") or []:
        s[dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date().isoformat()] = float(v or 0)
    return s, d


def main():
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date().isoformat()
    yday = (now.date() - dt.timedelta(1)).isoformat()
    src = {}
    prev = load(os.path.join(OUT, "aiagent_latest.json"), {})
    hist = load(os.path.join(OUT, "aiagent_history.json"), [])

    # ---- ① 手续费：名单 = 配置 + 「AI Agents」类目自动并入
    try:
        ov = get(f"{LLAMA}/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyFees")["protocols"]
        src["defillama_overview"] = {"ok": True, "n": len(ov)}
    except Exception as e:
        print("DefiLlama 总览失败：", e)
        src["defillama_overview"] = {"ok": False, "err": str(e)[:200]}
        ov = []
    by = {p.get("slug"): p for p in ov}
    conf = CFG["protocols"]
    slugs = [s for s in conf if not conf[s].get("exclude")]
    auto = []
    for p in ov:
        if p.get("category") in CFG["auto_categories"] and p.get("slug") not in conf:
            slugs.append(p["slug"]); auto.append(p["slug"])
    seen = dict(prev.get("first_seen") or {})
    base_day = prev.get("baseline_day") or today
    series, meta, fails = {}, {}, []
    for s in slugs:
        if ov and s not in by:   # DefiLlama 没有手续费适配器（或下线）：不请求，表里标「无适配器」
            meta[s] = {"name": s, "no_adapter": True}
            continue
        try:
            ser, raw = fee_series(s)
            series[s] = {d: v for d, v in ser.items() if CFG["since"] <= d < today}
            p = by.get(s) or {}
            meta[s] = {"name": raw.get("name") or p.get("name") or s, "category": p.get("category") or raw.get("category"),
                       "chains": (p.get("chains") or raw.get("chains") or [])[:4], "parent": p.get("parentProtocol"),
                       "url": raw.get("url"), "logo": p.get("logo")}
        except Exception as e:
            print("手续费失败：", s, e)
            fails.append(s)
            meta[s] = {"name": (by.get(s) or {}).get("name") or s, "failed": True}
        time.sleep(0.3)
    src["defillama_fees"] = {"ok": not fails, "n": len(series), "failed": fails}

    # 数据日：30 天手续费 ≥ 1 万美元的协议里最晚一天都有数的那天（不超过昨天），防止适配器延迟把最后一天算成 0
    big = [s for s in series if sum(x or 0 for x in window(series[s], yday, 30)) >= 1e4]
    asof = min([max(series[s]) for s in big if series[s]] or [yday])
    asof = min(asof, yday)
    alld = days(CFG["since"], asof)

    rows = []
    for s in slugs:
        m, c = meta.get(s, {}), conf.get(s, {})
        layer = c.get("layer") or CFG["default_layer"]
        ser = series.get(s)
        r = {"slug": s, "name": m.get("name") or s, "layer": layer, "category": m.get("category"), "chains": m.get("chains") or [],
             "auto": s in auto, "note_zh": c.get("note_zh"), "note_en": c.get("note_en"),
             "status": "no_adapter" if m.get("no_adapter") else ("failed" if m.get("failed") else "ok")}
        if s not in seen:
            seen[s] = "基线" if base_day == today else today
        r["first_seen"] = seen[s]
        if ser:
            first = min(ser)
            cur, pr = window(ser, asof, 30), window(ser, (dt.date.fromisoformat(asof) - dt.timedelta(30)).isoformat(), 30)
            # 协议首日之前的日子不算缺，算 0（那时还没上线）
            cur = [0.0 if (x is None and d < first) else x for x, d in zip(cur, days((dt.date.fromisoformat(asof) - dt.timedelta(29)).isoformat(), asof))]
            pr = [0.0 if (x is None and d < first) else x for x, d in zip(pr, days((dt.date.fromisoformat(asof) - dt.timedelta(59)).isoformat(), (dt.date.fromisoformat(asof) - dt.timedelta(30)).isoformat()))]
            a, b = wstats(cur), wstats(pr)
            r.update({"first_day": first, "last_day": max(ser), "d1": ser.get(asof), "d7": sum(x or 0 for x in cur[-7:]),
                      "f30": a["total"], "p30": b["total"], "chg30": pct(a["total"], b["total"]),
                      "med30": a["median"], "med_p30": b["median"], "peak30": a["peak"],
                      "chg30_ex_peak": pct(a["ex_peak"], b["ex_peak"]), "covered30": a["covered"],
                      "peak_share": (a["peak"] / a["total"] * 100) if a["total"] else None,
                      "dormant": bool(a["total"] is not None and a["total"] < 1 and (b["total"] or 0) >= 100)})
        rows.append(r)
    rows.sort(key=lambda r: -(r.get("f30") or 0))

    # 层合计（逐日）：只加 status ok 的协议；协议上线前算 0
    layers = {}
    lser = {k: {} for k in CFG["layers"]}
    for r in rows:
        ser = series.get(r["slug"])
        if not ser:
            continue
        first = min(ser)
        for d in alld:
            v = ser.get(d)
            if v is None and d < first:
                v = 0.0
            if v is not None:
                lser[r["layer"]][d] = lser[r["layer"]].get(d, 0.0) + v
    for k in CFG["layers"]:
        mem = [r for r in rows if r["layer"] == k and r.get("f30") is not None]
        cur, pr = window(lser[k], asof, 30), window(lser[k], (dt.date.fromisoformat(asof) - dt.timedelta(30)).isoformat(), 30)
        a, b = wstats(cur), wstats(pr)
        top = sorted(mem, key=lambda r: -(r["f30"] or 0))
        layers[k] = {"f30": a["total"], "p30": b["total"], "chg30": pct(a["total"], b["total"]), "chg30_ex_peak": pct(a["ex_peak"], b["ex_peak"]),
                     "med30": a["median"], "n": len(mem), "n_active": sum(1 for r in mem if (r["f30"] or 0) >= 100),
                     "top_share": (top[0]["f30"] / a["total"] * 100) if top and a["total"] else None, "top": top[0]["name"] if top else None}
    tot = {d: sum(lser[k].get(d, 0.0) for k in lser) for d in alld}
    a, b = wstats(window(tot, asof, 30)), wstats(window(tot, (dt.date.fromisoformat(asof) - dt.timedelta(30)).isoformat(), 30))
    total = {"f30": a["total"], "p30": b["total"], "chg30": pct(a["total"], b["total"]), "chg30_ex_peak": pct(a["ex_peak"], b["ex_peak"]), "med30": a["median"]}
    # 一年里的位置：近 30 天合计在过去 365 天滚动 30 天合计里的分位
    roll = []
    for i in range(29, len(alld)):
        roll.append(sum(tot[d] for d in alld[i - 29:i + 1]))
    last = roll[-365:]
    total["pctile_1y"] = (sum(1 for x in last if x <= a["total"]) / len(last) * 100) if last and a["total"] is not None else None
    total["max_1y"] = max(last) if last else None

    ref = {}
    for s, nm in CFG["reference_only"].items():
        if s.startswith("_"):
            continue
        p = by.get(s) or {}
        ref[s] = {"name": nm, "f30": p.get("total30d"), "f24h": p.get("total24h")}

    # ---- ② CoinGecko 分类快照 + 头部成分
    cg, top = {}, []
    try:
        cats = {c["id"]: c for c in get(f"{CG}/coins/categories")}
        for cid, zh, en in CFG["cg_categories"]:
            c = cats.get(cid) or {}
            cg[cid] = {"zh": zh, "en": en, "mcap": c.get("market_cap"), "vol24h": c.get("volume_24h"), "chg24h": c.get("market_cap_change_24h"),
                       "updated": c.get("updated_at")}
        src["coingecko_categories"] = {"ok": True}
    except Exception as e:
        print("CoinGecko 分类失败：", e)
        src["coingecko_categories"] = {"ok": False, "err": str(e)[:200]}
        cg = (prev.get("market") or {}).get("categories") or {}
    try:
        time.sleep(3)
        mk = get(f"{CG}/coins/markets?vs_currency=usd&category={CFG['cg_top_category']}&order=market_cap_desc&per_page={CFG['cg_top_n']}&page=1&price_change_percentage=7d,30d")
        for c in mk:
            top.append({"id": c.get("id"), "symbol": (c.get("symbol") or "").upper(), "name": c.get("name"), "mcap": c.get("market_cap"),
                        "vol24h": c.get("total_volume"), "chg7d": c.get("price_change_percentage_7d_in_currency"),
                        "chg30d": c.get("price_change_percentage_30d_in_currency"), "ath_chg": c.get("ath_change_percentage")})
        src["coingecko_markets"] = {"ok": True, "n": len(top)}
    except Exception as e:
        print("CoinGecko 成分失败：", e)
        src["coingecko_markets"] = {"ok": False, "err": str(e)[:200]}
        top = (prev.get("market") or {}).get("top") or []
    tm = sum(x["mcap"] or 0 for x in top)
    top_share = {"top1": (top[0]["mcap"] / tm * 100) if top and tm else None, "top5": (sum(x["mcap"] or 0 for x in top[:5]) / tm * 100) if tm else None}

    # ---- ③ Agent ID 摘要（本站链上采集）
    aid = {}
    cs = load(os.path.join(ROOT, "public", "ai-agent", "monitor", "core_series.json"), {})
    rws = cs.get("rows") or []
    if rws:
        f = lambda k, r: None if r.get(k) in (None, "") else float(r[k])
        last7 = rws[-7:]
        prev7 = rws[-14:-7]
        s7 = lambda k, rr: sum(f(k, r) or 0 for r in rr) if rr and all(f(k, r) is not None for r in rr) else None
        aid = {"through": cs.get("data_through_utc"), "cumulative_ids": f("cumulative_ids", rws[-1]),
               "new_ids_7d": s7("new_ids", last7), "new_ids_prev7d": s7("new_ids", prev7),
               "launches_7d": s7("new_launches", last7), "launches_prev7d": s7("new_launches", prev7),
               "volume_bnb_7d": s7("volume_bnb", last7), "volume_bnb_prev7d": s7("volume_bnb", prev7),
               "peak_volume": max(((f("volume_bnb", r) or 0), r["date"]) for r in rws),
               "peak_traders": max(((f("trading_addresses", r) or 0), r["date"]) for r in rws)}

    # ---- 事件：新进名单的协议、30 天手续费从有到零（休眠）、近 30 天里单日占比过半（单日事件）
    events = []
    if base_day != today:
        for r in rows:
            if r["first_seen"] == today:
                events.append({"type": "new_protocol", "slug": r["slug"], "name": r["name"], "layer": r["layer"]})
    for r in rows:
        if r.get("dormant"):
            events.append({"type": "dormant", "slug": r["slug"], "name": r["name"], "layer": r["layer"]})
        if (r.get("peak_share") or 0) >= 50 and (r.get("f30") or 0) >= 5000:
            events.append({"type": "spike", "slug": r["slug"], "name": r["name"], "layer": r["layer"], "share": r["peak_share"]})

    latest = {"generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "asof": asof, "baseline_day": base_day, "since": CFG["since"],
              "total": total, "layers": layers, "protocols": rows, "reference": ref, "events": events,
              "market": {"snapshot_utc": now.strftime("%Y-%m-%d %H:%M"), "categories": cg, "top": top, "top_share": top_share},
              "agent_id": aid, "first_seen": seen, "sources": src}
    dump(os.path.join(OUT, "aiagent_latest.json"), latest)
    dump(os.path.join(OUT, "fees_series.json"), {"d": alld, "layers": {k: [round(lser[k].get(d), 2) if lser[k].get(d) is not None else None for d in alld] for k in lser},
                                                  "protocols": {s: [round(series[s][d], 2) if d in series[s] else None for d in alld] for s in series if any(series[s].values())}}, indent=None)
    row = {"date": today, "fees_asof": asof, "fees30": {k: layers[k]["f30"] for k in layers}, "fees30_total": total["f30"],
           "cg_mcap": {k: v.get("mcap") for k, v in cg.items()}, "agent_ids": aid.get("cumulative_ids")}
    hist = [h for h in hist if h["date"] != today] + [row]
    dump(os.path.join(OUT, "aiagent_history.json"), hist)
    print(f"AI Agent 赛道：数据日 {asof}，{len(series)} 家有手续费，30 天合计 {total['f30']:,.0f}，事件 {len(events)}；"
          f"CoinGecko {'ok' if src.get('coingecko_categories', {}).get('ok') else '失败'}")
    if not ov:
        sys.exit(1)


if __name__ == "__main__":
    main()
