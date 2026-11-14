#!/usr/bin/env python3
"""机会卡（应用层）：把雷达线索 + 系统自动打分 + 研究补证合成一张张按框架结构的卡，给机会看板和详情页用。

输入（清洗层）：data/alpha/alpha_latest.json（雷达读数）、alpha_leads.json（线索台账）、alpha_history.json（每天 rev30）、
      alpha/review/*_checks.json（研究补证，研究结论优先于自动规则）、alpha/framework.json（自动规则 auto_rules、类目映射 category_map、资金参与方式 entry）
输出（应用层）：data/alpha/opps.json（全部机会卡）、data/alpha/opp_series.json（各机会近 180 天协议收入周线，监控用）

谁进机会看板（写死，改了记 changelog）：
  ① 研究补证过的全部（含拒绝，拒绝单列）
  ② 线索台账基线日之后首次进「无币协议收入榜」的（系统自动打分，状态 = 原始线索）
  ③ 最近 14 天新上架、TVL ≥ alpha_config.opps.listing_min_tvl 的协议（同上）
分栏：资金参与方式不是「暂无」→ 可投资机会；否则 → 预警观察。
用法：python3 alpha/opps.py [--no-series]
"""
import json, os, sys, time, urllib.request
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "alpha")
UA = {"User-Agent": "uncleonchain-alpha/1.0"}


def load(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


FW = load(os.path.join(HERE, "framework.json"))
CFG = load(os.path.join(HERE, "alpha_config.json"))
CAT2BIZ = {c: k for k, cs in FW["category_map"].items() if not k.startswith("_") for c in cs}


def S(v="U", src=None, why=""):
    return {"v": v, "src": src, "why": why}


def build():
    latest = load(os.path.join(OUT, "alpha_latest.json"), {})
    leads = (load(os.path.join(OUT, "alpha_leads.json"), {}) or {}).get("leads", {})
    hist = load(os.path.join(OUT, "alpha_history.json"), []) or []
    checks = {}
    rd = os.path.join(HERE, "review")
    for fn in sorted(os.listdir(rd)):
        if fn.endswith("_checks.json"):
            for c in load(os.path.join(rd, fn), []) or []:
                checks[c["key"]] = dict(c, _file=fn)   # 后交的批次覆盖先交的
    rows = {r["key"]: r for r in latest.get("tokenless", [])}
    lst = {r["key"]: r for r in latest.get("listings", [])}
    base = latest.get("baseline_day")
    min_tvl = (CFG.get("opps") or {}).get("listing_min_tvl", 5e6)
    min_rev = CFG["tokenless"]["min_rev30_usd"]

    keys = list(checks)
    keys += [k for k, v in leads.items() if k not in checks and k.startswith("g:") and not v.get("baseline") and k in rows]
    keys += [k for k, r in lst.items() if k not in checks and (r.get("tvl") or 0) >= min_tvl]
    cards = []
    for k in dict.fromkeys(keys):
        L = leads.get(k, {})
        r = rows.get(k) or {}
        li = lst.get(k) or {}
        c = checks.get(k)
        name = (c or {}).get("name") or r.get("name") or li.get("name") or L.get("name") or k
        cat = r.get("category") or li.get("category") or (L.get("first") or {}).get("category")
        has_token = bool(li.get("token")) or bool(L.get("token_seen"))
        # ---- 分类（自动 → 研究覆盖）
        biz = CAT2BIZ.get(cat)
        cls = {"business": S(biz or "U", "auto", f"DefiLlama 类目「{cat}」→ 映射表" if biz else f"类目「{cat}」不在映射表"),
               "right": S("governance" if has_token else "none", "auto", "已有代币，权利待补证" if has_token else "本协议和母协议都没登记代币"),
               "opportunity": S("rerate" if has_token else "genesis", "auto", "已有代币 → 产品与资产重估" if has_token else "无币 → 初始参与（早期使用 / 积分）"),
               "attribute": S("product", "auto", "协议级对象，默认产品型")}
        # ---- 资金参与方式
        entry, entry_why = [], ""
        stance = (c or {}).get("token_stance")
        if has_token:
            entry, entry_why = ["buy"], ("母协议已有代币，可二级买入母协议代币（新产品本身不单独发币）" if li.get("parent") else "已有代币，可二级买入")
        if stance == "有积分/空投计划":
            entry.append("use"); entry_why = (entry_why + "；" if entry_why else "") + "官方有积分 / 空投计划（研究补证）"
        if stance == "官方确认不发币":
            entry_why = entry_why or "官方确认不发币"
        ENTRY_KEYS = {o["k"] for o in FW["entry"]["opts"]}
        if c and isinstance(c.get("entry"), list) and c["entry"] and all(e in ENTRY_KEYS for e in c["entry"]):
            entry, entry_why = list(c["entry"]), (c.get("entry_why") or "研究补证给出的资金参与方式")   # 研究结论优先
        if not entry:
            entry = ["none"]
            entry_why = entry_why or {"官方表态会发": "官方表态会发币，但还没开放资金参与 → 预警观察，等发币 / 积分开放",
                                      "没有表态": "官方没有表态发币，也没查到积分计划"}.get(stance, "还没查到资金参与方式")
        # ---- 评分（附录一 B / C；系统规则 framework.auto_rules）
        sc = {k2: S() for k2 in "MAFEVGPDLT"}
        sc["TM"] = S()                                                                   # 投资补充：团队可识别度（研究补证）
        sc["TE"] = S("U") if has_token else S("NA", "auto", "还没有代币，代币经济不适用")   # 投资补充：代币经济
        rev30 = r.get("rev30")
        if rev30 and rev30 >= min_rev:
            sc["D"] = S(2, "auto", f"近 30 天协议收入 {rev30:,.0f} 美元 ≥ {min_rev:,.0f} → 2（可识别外部客户但账单未核）")
        if c:
            ws = c.get("wash_or_subsidy") or ""
            if c.get("user_role") and c["user_role"] != "U":
                sc["A"] = S(2, "research", "普通人可以「" + c["user_role"][:40] + "」参与，全成本未验 → 2")
            if stance == "官方确认不发币":
                sc["V"] = S(0, "research", "官方确认不发币 → 0（本角色没有所称权益）")
            elif stance == "有积分/空投计划":
                sc["V"] = S(1, "research", "有积分 / 空投计划 → 1（仅排放或升值预期）")
            if "刷量" in ws and ("为主" in ws or "主要" in ws):
                sc["D"] = S(1, "research", "研究查到刷量 / 补贴为主 → 1")
            mx = {"TM": 3, "TE": 3}
            for k2, v2 in (c.get("scores") or {}).items():   # 研究直接给的分（每条要有依据），优先于上面的自动 / 推导分
                if k2 not in sc or not isinstance(v2, dict):
                    continue
                val = v2.get("v")
                if val in ("U", "NA") or (isinstance(val, int) and 0 <= val <= mx.get(k2, 4)):
                    why = (v2.get("why") or "")[:200] + (f"（来源 {v2['src']}）" if v2.get("src") else "")
                    sc[k2] = S(val, "research", why)
        # ---- 门槛
        gates = {"safety": S("待核验", "auto", "没有完成控制权审计一律待核验"),
                 "data": S("通过" if (c or {}).get("verdict") == "研究观察" else "待核验", "research" if c else "auto",
                           "身份经研究核对" if (c or {}).get("verdict") == "研究观察" else "身份未经研究核对"),
                 "exec": S("U", None, "个人执行，不公开")}
        status = (c or {}).get("verdict") or L.get("status") or "原始线索"
        if status not in ("待核验", "研究观察", "优先研究", "拒绝"):
            status = "原始线索"
        # 历史 rev30（台账每天记的）
        rev_hist = [[h["date"], (h.get("rev30") or {}).get(k)] for h in hist if (h.get("rev30") or {}).get(k) is not None]
        disc = L.get("first_seen")
        fresh = bool(disc and not L.get("baseline") and (dt.date.today() - dt.date.fromisoformat(disc)).days <= 3)
        cards.append({
            "fresh": fresh, "reviewer": (c or {}).get("reviewer") or ("codex" if c else None),
            "id": k.split(":", 1)[1].replace("parent#", ""), "key": k, "name": name,
            "kind": "tokenless" if k.startswith("g:") else "listing",
            "discovered": L.get("first_seen"), "baseline": bool(L.get("baseline")),
            "status": status, "status_src": f"alpha/review/{c['_file']}" if c else "auto",
            "bucket": "reject" if status == "拒绝" else ("watch" if entry == ["none"] else "invest"),
            "entry": entry, "entry_why": entry_why, "classes": cls, "scores": sc, "gates": gates,
            "one_liner": (c or {}).get("one_liner"),
            "research": {x: (c or {}).get(x) for x in ("token_stance", "token_stance_src", "token_stance_date", "revenue_who", "revenue_method", "wash_or_subsidy",
                                                      "user_role", "counter", "verdict_reason", "missing", "checked_utc")} if c else None,
            "evidence": [{"url": e.get("url"), "fields": e.get("fields")} for e in (c or {}).get("evidence") or [] if str(e.get("url", "")).startswith("http")],
            "data": {"category": cat, "chains": r.get("chains") or li.get("chains"), "rev30": rev30, "chg30": r.get("chg30"),
                     "tvl": li.get("tvl"), "listed": li.get("listed"), "slug": r.get("slug") or li.get("slug") or L.get("slug"),
                     "children": r.get("children"), "token": has_token, "token_seen": L.get("token_seen"), "rev_hist": rev_hist},
        })
    order = {"研究观察": 0, "优先研究": 0, "待核验": 1, "原始线索": 2, "拒绝": 3}
    cards.sort(key=lambda x: (order.get(x["status"], 9), -(x["data"]["rev30"] or x["data"]["tvl"] or 0)))
    return {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "asof": latest.get("asof"),
            "framework": FW["version"], "rules": FW["auto_rules"]["sec"],
            "counts": {b: sum(1 for x in cards if x["bucket"] == b) for b in ("invest", "watch", "reject")}, "opps": cards}


def series(cards):
    """监控：每张卡近 180 天逐日协议收入（DefiLlama dailyRevenue）。母协议用 parent 名，单协议用 slug。
    写 data/alpha/rev/<id>.json（网站走势图格式 {d, s:{rev}}），返回 {id: [[日, 值], ...]}。"""
    out, today = {}, dt.date.today().isoformat()
    cut = (dt.date.today() - dt.timedelta(days=180)).isoformat()
    os.makedirs(os.path.join(OUT, "rev"), exist_ok=True)
    for c in cards:
        k = c["key"]
        slug = k[len("g:parent#"):] if k.startswith("g:parent#") else c["data"].get("slug")
        if not slug or c["kind"] != "tokenless":
            continue
        try:
            d = get(f"https://api.llama.fi/summary/fees/{slug}?dataType=dailyRevenue")
            pts = [(dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat(), v or 0) for t, v in d.get("totalDataChart") or []]
            pts = [[a, round(b)] for a, b in pts if cut <= a < today]
            if pts:
                out[c["id"]] = pts
                json.dump({"d": [a for a, _ in pts], "s": {"rev": [b for _, b in pts]}}, open(os.path.join(OUT, "rev", c["id"] + ".json"), "w"), separators=(",", ":"))
        except Exception as e:
            print("收入序列失败", slug, str(e)[:100])
        time.sleep(0.3)
    return out


QUEUE_PROMPT = """你在给「链上大叔研究台」Alpha 雷达补证（只研究正规项目，不写买卖建议）。对清单里每个协议，查官方网站 / 文档 / 公告、DefiLlama 方法论和可核对的链上信息，
按下面格式交一个 JSON 数组（文件名 <日期>_checks.json）。第一项 one_liner 用一句大白话说清它是什么（给没听过的人看）。每条事实带来源链接和核对日期；查不到写 "U"，不要估，不要编。
结论 verdict 只能是：研究观察（对象明确、有可证伪假设、没查到否决项）/ 待核验（关键事实缺失或冲突，写清缺什么）/ 拒绝（身份错误、已确认风险、其实已有代币、不是对普通人开放的正规项目，写证据）。
分数按 framework.json 附录一锚点给（M A F E G T 是 0–4，TM TE 是 0–3，不知道写 U，没有代币时 TE 写 NA），每个分数写 why 和 src。
资金参与方式 entry 从 buy / stake / points / use / presale / mine / none 里选（none = 暂时没有资金入口），写 entry_why。"""

QUEUE_SCHEMA = {"key": "清单里的 key（原样）", "name": "名称", "one_liner": "一句话介绍：它是什么、给谁用、靠什么收钱（30 字内，大白话）", "reviewer": "claude-auto 或 codex", "checked_utc": "核对时间 ISO",
                "token_stance": "官方确认不发币|有积分/空投计划|官方表态会发|没有表态|U", "token_stance_src": "链接", "token_stance_date": "日期或 U",
                "revenue_who": "收入归谁", "revenue_method": "收入口径要点", "wash_or_subsidy": "刷量 / 补贴迹象或 U", "user_role": "普通人能以什么角色参与",
                "entry": ["points"], "entry_why": "为什么是这种资金参与方式（带来源）",
                "scores": {"M": {"v": "0-4|U", "why": "依据", "src": "链接"}, "TM": {"v": "0-3|U", "why": "", "src": ""}},
                "counter": "最强反方一句话", "verdict": "研究观察|待核验|拒绝", "verdict_reason": "为什么", "missing": ["还没查清的事项"],
                "evidence": [{"url": "链接", "fields": ["支持了哪些字段"]}]}


def queue(cards):
    """补证队列：没补完的卡，按 新发现 → 可投资 → 收入 / TVL 排序。给每日自动补证会话和 Codex 用。"""
    q = [c for c in cards if c["status"] in ("原始线索", "待核验")]
    q.sort(key=lambda c: (not c["fresh"], c["bucket"] != "invest", c["status"] != "原始线索", -(c["data"]["rev30"] or c["data"]["tvl"] or 0)))
    items = [{"key": c["key"], "name": c["name"], "status": c["status"], "kind": c["kind"], "fresh": c["fresh"], "bucket": c["bucket"],
              "discovered": c["discovered"], "category": c["data"]["category"], "chains": c["data"]["chains"], "rev30": c["data"]["rev30"], "tvl": c["data"]["tvl"],
              "defillama": f"https://defillama.com/protocol/{c['data']['slug']}" if c["data"].get("slug") else None,
              "pending": [k for k, v in c["scores"].items() if v["v"] == "U" and k not in ("P", "L")],
              "missing_before": (c.get("research") or {}).get("missing") or []} for c in q]
    return {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "n": len(items), "prompt": QUEUE_PROMPT, "schema": QUEUE_SCHEMA, "items": items}


def main():
    res = build()
    if "--no-series" not in sys.argv:
        ser = series(res["opps"])
        json.dump(ser, open(os.path.join(OUT, "opp_series.json"), "w", encoding="utf-8"), separators=(",", ":"))
    else:
        ser = load(os.path.join(OUT, "opp_series.json"), {}) or {}
    for c in res["opps"]:   # 列表里的 30 天迷你走势
        c["spark"] = [v for _, v in (ser.get(c["id"]) or [])[-30:]]
    q = queue(res["opps"])
    res["queue_n"] = q["n"]
    json.dump(res, open(os.path.join(OUT, "opps.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(q, open(os.path.join(OUT, "research_queue.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("机会卡", len(res["opps"]), res["counts"])


if __name__ == "__main__":
    main()
