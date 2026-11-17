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


def home(url):
    """官网只留域名首页：DefiLlama 有的链接带推荐码（如 axiom.trade/@defillama），不替别人带推荐。"""
    if not url:
        return None
    from urllib.parse import urlsplit
    u = urlsplit(url if "://" in url else "https://" + url)
    return f"{u.scheme or 'https'}://{u.netloc}" if u.netloc else None
CFG = load(os.path.join(HERE, "alpha_config.json"))
CAT2BIZ = {c: k for k, cs in FW["category_map"].items() if not k.startswith("_") for c in cs}


def SRC_OF(k, L, li):
    """这张卡是哪些来源发现的（来源台账 alpha/sources.json 的 id）。"""
    out = []
    for x in (L.get("source") or "").split("+"):
        out.append({"tokenless_rev": "llama_tokenless", "rev_surge": "llama_surge", "new_listing": "llama_listing", "manual": "manual"}.get(x, x.replace("site:", "site_")) if x else None)
    if not out or out == [None]:
        out = ["llama_listing" if li else "llama_tokenless"]
    return [x for x in dict.fromkeys(out) if x]


def S(v="U", src=None, why=""):
    return {"v": v, "src": src, "why": why}


def composite(sc, c, data, has_token):
    """综合分 v3（framework.json composite；大叔 11-17 定）。→ {lo 保守分, hi 全查清后最高, cov 覆盖率, parts}
    lo 只加查清的项（没查的按 0）；hi = lo + 每个没查项的满分；势头（R、G）在创新 < 15 分时按一半计。"""
    CP = FW["composite"]
    D = {d["k"]: d for d in CP["dims"]}
    num = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    parts = {}
    m = num(sc["M"]["v"])
    parts["M"] = (D["M"]["points"][str(int(m))], "研究") if m is not None and 0 <= m <= 4 else None
    rr = ((c or {}).get("scores") or {}).get("R") or {}
    rv = num(rr.get("v"))
    parts["R"] = (max(0, min(10, rv)), "研究") if rv is not None else None
    g = num(sc["G"]["v"])
    if g is not None and 0 <= g <= 4:
        parts["G"] = (D["G"]["points"][str(int(g))], "研究")
    elif data.get("chg30") is not None:
        x = data["chg30"]
        x = x / 100 if abs(x) > 5 else x   # chg30 可能是百分数
        parts["G"] = (next(p for lo, hi, p in D["G"]["auto"] if lo <= x < hi), "系统")
    else:
        parts["G"] = None
    team = (c or {}).get("team") or {}
    tm = num(sc["TM"]["v"])
    if tm == -1 or team.get("bad_record") is True:
        parts["TM"] = (-20, "研究")
    elif num(team.get("public_n")) is not None or team.get("caliber") in D["TM"]["caliber"]:
        n = num(team.get("public_n")) or 0
        pts = max(p for k, p in D["TM"]["public_n"] if n >= k)
        parts["TM"] = (pts + D["TM"]["caliber"].get(team.get("caliber"), 0), "研究")
    elif tm is not None:
        parts["TM"] = ({0: 0, 1: 3, 2: 7, 3: 12}.get(int(tm), 0), "研究（旧分换算）")
    else:
        parts["TM"] = None
    d = num(sc["D"]["v"])
    parts["D"] = (D["D"]["points"][str(int(d))], "研究") if d is not None and 0 <= d <= 4 else None
    a, f_ = num(sc["A"]["v"]), num(sc["F"]["v"])
    if a is not None and f_ is not None:
        parts["AF"] = (round((a + f_) / 8 * 10, 1), "研究")
    elif a is not None or f_ is not None:
        parts["AF"] = (round((a if a is not None else f_) / 8 * 10, 1), "研究（只查清一项）")   # 另一半按未知算
    else:
        parts["AF"] = None
    te = sc["TE"]["v"]
    parts["TE"] = ("NA" if not has_token or te == "NA" else (D["TE"]["points"][str(int(te))], "研究") if num(te) is not None and 0 <= te <= 3 else None)
    full_m = parts["M"] is not None and parts["M"][0] >= CP["gate"]["M_min"]
    fac = lambda k: 1 if k not in CP["gate"]["applies"] or full_m else CP["gate"]["factor"]
    lo = hi = 0.0
    known_w = total_w = 0
    for k, dm in D.items():
        p = parts.get(k)
        if p == "NA":
            continue
        w = dm["max"] - dm.get("min", 0)
        total_w += w
        if p is None:
            hi += dm["max"] * (CP["gate"]["factor"] if (k in CP["gate"]["applies"] and parts["M"] is not None and not full_m) else 1)   # 创新没查时假设它够格
            continue
        v = p[0] * fac(k)
        lo += v; hi += v
        if p[1].endswith("只查清一项）"):
            hi += dm["max"] / 2; known_w += w / 2
        else:
            known_w += w
    return {"lo": round(lo, 1), "hi": round(min(hi, CP["max"]), 1), "cov": round(known_w / total_w, 2) if total_w else 0,
            "gated": not full_m, "parts": {k: (None if v is None else v if v == "NA" else {"v": round(v[0] * fac(k), 1), "src": v[1]}) for k, v in parts.items()}}


def build():
    latest = load(os.path.join(OUT, "alpha_latest.json"), {})
    leads = (load(os.path.join(OUT, "alpha_leads.json"), {}) or {}).get("leads", {})
    hist = load(os.path.join(OUT, "alpha_history.json"), []) or []
    import checks_util
    checks = checks_util.merged()   # 合并规则（空壳不盖已有补证、patches）见 alpha/checks_util.py
    rows = {r["key"]: r for r in latest.get("tokenless", []) + latest.get("surge", []) + latest.get("manual", []) + latest.get("site", [])}
    manual = {"m:" + m["id"]: m for m in (load(os.path.join(HERE, "manual_leads.json"), {}) or {}).get("leads", [])}
    lst = {r["key"]: r for r in latest.get("listings", [])}
    base = latest.get("baseline_day")
    min_tvl = (CFG.get("opps") or {}).get("listing_min_tvl", 5e6)
    min_rev = CFG["tokenless"]["min_rev30_usd"]

    keys = list(checks)
    keys += [k for k in manual if k not in checks]                       # 手动线索：登记当天就上看板
    keys += [k for k, v in leads.items() if k not in checks and k[:2] in ("g:", "s:", "x:") and not v.get("baseline") and k in rows]
    keys += [k for k, r in rows.items() if k not in checks and r.get("boards")]      # 站内板块也筛到的：即使是基线日就在榜上的也出卡
    keys += [k for k, r in lst.items() if k not in checks and (r.get("tvl") or 0) >= min_tvl]
    cards = []
    for k in dict.fromkeys(keys):
        L = leads.get(k, {})
        r = rows.get(k) or {}
        li = lst.get(k) or {}
        c = checks.get(k)
        name = (c or {}).get("name") or r.get("name") or li.get("name") or L.get("name") or k
        cat = r.get("category") or li.get("category") or (L.get("first") or {}).get("category")
        has_token = bool(li.get("token")) or bool(L.get("token_seen")) or bool(r.get("token"))
        mn = manual.get(k) or {}
        kind = {"g": "tokenless", "s": "surge", "m": "manual", "x": "site"}.get(k[0], "listing")
        # ---- 分类（自动 → 研究覆盖）
        biz = CAT2BIZ.get(cat)
        cls = {"business": S(biz or "U", "auto", f"DefiLlama 类目「{cat}」→ 映射表" if biz else f"类目「{cat}」不在映射表"),
               "right": S("governance" if has_token else "none", "auto", "已有代币，权利待补证" if has_token else "本协议和母协议都没登记代币"),
               "opportunity": S("rerate" if has_token else "genesis", "auto", "已有代币 → 产品与资产重估" if has_token else "无币 → 初始参与（早期使用 / 积分）"),
               "attribute": S("product", "auto", "协议级对象，默认产品型")}
        # ---- 资金参与方式
        entry, entry_why = [], ""
        stance = (c or {}).get("token_stance")
        if has_token and li.get("parent") and not c:
            # 11-15：母协议有币的新上架产品，没研究前不进可投资——买母币任何时候都能买，说明不了这个新产品
            entry_why = "母协议已有代币，但这个新产品和母币的关系还没研究，先放预警观察"
        elif has_token:
            entry, entry_why = ["buy"], ("母协议已有代币，可二级买入母协议代币（新产品本身不单独发币）" if li.get("parent") else "已有代币，可二级买入")
        if stance == "有积分/空投计划":
            entry.append("use"); entry_why = (entry_why + "；" if entry_why else "") + "官方有积分计划（研究补证）；积分不等于代币，兑现规则未公布"
        if stance == "官方确认不发币":
            entry_why = entry_why or "官方确认不发币"
        ENTRY_KEYS = {o["k"] for o in FW["entry"]["opts"]}
        if c and isinstance(c.get("entry"), list) and c["entry"] and all(e in ENTRY_KEYS for e in c["entry"]):
            entry, entry_why = list(c["entry"]), (c.get("entry_why") or "研究补证给出的资金参与方式")   # 研究结论优先
        if mn.get("entry") and not (c and c.get("entry")):
            entry, entry_why = list(mn["entry"]), mn.get("entry_why") or "手动线索登记的参与方式，待补证"
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
            # 自动规则 v2（11-15）：收入过门槛只记事实，不再自动打 2——门槛就是进榜门槛，所有卡都是 2，分不出谁是真外部客户
            sc["D"] = S("U", "auto", f"事实：近 30 天协议收入 {rev30:,.0f} 美元，已过 {min_rev:,.0f} 门槛；是谁在付钱、去掉补贴还剩多少，待研究")
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
            mx, mn_ = {"TM": 3, "TE": 3}, {"TM": -1}                     # 团队有已证实不良记录 = -1（大叔 11-15 定）
            for k2, v2 in (c.get("scores") or {}).items():   # 研究直接给的分（每条要有依据），优先于上面的自动 / 推导分
                if k2 not in sc or not isinstance(v2, dict):
                    continue
                val = v2.get("v")
                if val in ("U", "NA") or (isinstance(val, int) and mn_.get(k2, 0) <= val <= mx.get(k2, 4)):
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
        disc = mn.get("added") or L.get("first_seen")
        if L.get("baseline") and r.get("boards"):
            disc = (r["boards"][0].get("since") or dt.date.today().isoformat()) if not L.get("board_seen") else L["board_seen"]
        fresh = bool(disc and (not L.get("baseline") or r.get("boards")) and (dt.date.today() - dt.date.fromisoformat(disc)).days <= 3)
        cards.append({
            "fresh": fresh, "reviewer": (c or {}).get("reviewer") or ("codex" if c else None),
            "id": ("m-" if k[0] == "m" else "x-" if k[0] == "x" else "") + k.split(":", 1)[1].replace("parent#", "").replace(":", "-"), "key": k, "name": name,
            "kind": kind, "why_here": r.get("why"), "manual": {x: mn.get(x) for x in ("what", "by", "sources")} if mn else None,
            "discovered": disc, "baseline": bool(L.get("baseline")),
            "status": status, "status_src": f"alpha/review/{c['_file']}" if c else "auto",
            "bucket": "reject" if status == "拒绝" else ("watch" if entry == ["none"] else "invest"),
            "entry": entry, "entry_why": entry_why, "classes": cls, "scores": sc, "gates": gates,
            "comp": composite(sc, c, {"chg30": r.get("chg30")}, has_token),
            "one_liner": (c or {}).get("one_liner") or mn.get("what"),
            "research": {x: (c or {}).get(x) for x in ("token_stance", "token_stance_src", "token_stance_date", "revenue_who", "revenue_method", "wash_or_subsidy",
                                                      "user_role", "counter", "verdict_reason", "missing", "checked_utc", "events", "flow", "next_review", "capture", "quality")} if c else None,
            "evidence": [{"url": e.get("url"), "fields": e.get("fields")} for e in (c or {}).get("evidence") or [] if str(e.get("url", "")).startswith("http")]
                        or [{"url": u, "fields": ["手动线索出处"]} for u in mn.get("sources") or []],
            "data": {"category": cat, "chains": r.get("chains") or li.get("chains"), "rev30": rev30, "chg30": r.get("chg30"), "rev_all": r.get("rev_all"), "llama": mn.get("llama"), "fees7": r.get("fees7"), "fees30": r.get("fees30"),
                     "sources": SRC_OF(k, L, li) , "boards": r.get("boards"),
                     "tvl": li.get("tvl"), "listed": li.get("listed"), "slug": r.get("slug") or li.get("slug") or L.get("slug"),
                     "url": home(r.get("url") or li.get("url")), "logo": r.get("logo") or li.get("logo"), "twitter": r.get("twitter") or li.get("twitter"),
                     "children": r.get("children"), "token": has_token, "token_seen": L.get("token_seen"), "rev_hist": rev_hist},
        })
    for c in cards:
        for b in c["data"].get("boards") or []:
            if "site_" + b["board"] not in c["data"]["sources"]:
                c["data"]["sources"].append("site_" + b["board"])
    # 11-17 大叔定：按综合分排名（保守分高的在上；同分看覆盖率、再看收入 / TVL）
    cards.sort(key=lambda x: (x["status"] == "拒绝", -x["comp"]["lo"], -x["comp"]["cov"], -(x["data"]["rev30"] or x["data"]["tvl"] or 0)))
    return {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "asof": latest.get("asof"),
            "framework": FW["version"], "rules": FW["auto_rules"]["sec"],
            "counts": {b: sum(1 for x in cards if x["bucket"] == b) for b in ("invest", "watch", "reject")}, "opps": cards}


FIRST_REV = {}


def series(cards):
    """监控：每张卡近 180 天逐日协议收入（DefiLlama dailyRevenue）。母协议用 parent 名，单协议用 slug。
    写 data/alpha/rev/<id>.json（网站走势图格式 {d, s:{rev}}），返回 {id: [[日, 值], ...]}。"""
    out, today = {}, dt.date.today().isoformat()
    cut = (dt.date.today() - dt.timedelta(days=180)).isoformat()
    os.makedirs(os.path.join(OUT, "rev"), exist_ok=True)
    for c in cards:
        k = c["key"]
        g = c["data"].get("llama") or k[2:]
        slug = g[len("parent#"):] if g.startswith("parent#") else c["data"].get("slug")
        if not slug or c["kind"] in ("listing", "site"):
            continue
        try:
            d = get(f"https://api.llama.fi/summary/fees/{slug}?dataType=dailyRevenue")
            pts = [(dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat(), v or 0) for t, v in d.get("totalDataChart") or []]
            nz = next((a for a, b in pts if b), None)
            if nz:
                FIRST_REV[c["id"]] = nz
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
结论 verdict 只能是：研究观察（对象明确、有可证伪假设、没查到否决项）/ 待核验（关键事实缺失或冲突，写清缺什么）/ 拒绝（身份错误、已确认风险、不是对普通人开放的正规项目，写证据）。
「已有代币」本身不是拒绝理由：清单里 kind = tokenless 的如果查到其实已经有代币，写进 token_stance 和 missing、verdict 给待核验；kind = surge / site / manual 的本来就可能有代币，照常研究它的新玩法。
只靠搜索摘要、打不开官网和文档的，verdict 最多给待核验，不给拒绝（拒绝必须有一手证据）。
分数按 framework.json 附录一锚点给（M A F E G T D 是 0–4；TM 是 -1–3，有已证实不良记录给 -1；TE 是 0–3；不知道写 U，没有代币时 TE 写 NA）。M（新参与机制：这个玩法新在哪）优先查，每个分数写 why 和 src。
综合分 v3（11-17）另要三项：R 资源导入 0–10（0 查不到 / 3 一般融资或小型生态资助 / 6 头部机构领投或头部交易所、公链官方扶持 / 10 多个头部资源同时导入，必须给出处）；
team.public_n = 能查到真实身份的核心成员人数（数字，查不到写 U）；team.caliber = 普通 / 成功交付 / 头部背景（成员有可核对的成功项目 = 成功交付；有头部项目或顶级机构核心经历 = 头部背景）；有已证实的跑路、欺诈等不良记录写 team.bad_record = true 并给证据。
资金参与方式 entry 从 buy / stake / points / use / presale / mine / none 里选（none = 暂时没有资金入口），写 entry_why。
每张卡要回答三件事：量从哪来（flow 四个标签各给 高 / 中 / 低 / 待验证 + 证据）、量是不是真的（刷量 / 补贴迹象）、激励结束后还剩多少（capture、next_review）。
关键事件（积分开放 / 结束、主网上线、发币、费率改动）写进 events，每条要日期和官方出处。"""

QUEUE_SCHEMA = {"key": "清单里的 key（原样）", "name": "名称", "one_liner": "一句话介绍：它是什么、给谁用、靠什么收钱（30 字内，大白话）", "reviewer": "grok-auto / claude-auto / codex", "checked_utc": "核对时间 ISO",
                "token_stance": "官方确认不发币|有积分/空投计划|官方表态会发|没有表态|U", "token_stance_src": "链接", "token_stance_date": "日期或 U",
                "revenue_who": "收入归谁", "revenue_method": "收入口径要点", "wash_or_subsidy": "刷量 / 补贴迹象或 U", "user_role": "普通人能以什么角色参与",
                "entry": ["points"], "entry_why": "为什么是这种资金参与方式（带来源）",
                "scores": {"M": {"v": "0-4|U", "why": "依据", "src": "链接"}, "TM": {"v": "0-3|U", "why": "", "src": ""}, "R": {"v": "0-10|U", "why": "资源导入依据", "src": "链接"}},
                "team": {"public_n": "实名核心成员人数|U", "caliber": "普通|成功交付|头部背景|U", "bad_record": "true|false", "members": [{"name": "姓名", "role": "职务", "background": "过往经历", "src": "链接"}]},
                "capture": "代币 / 参与者实际能拿到什么（回购、分红、积分兑换规则；没有就写没有），带链接",
                "events": [{"date": "YYYY-MM-DD", "what": "积分开放 / 结束、主网上线、发币、费率改动等", "src": "官方链接"}],
                "flow": {"airdrop": {"v": "高|中|低|待验证", "why": "积分 / 空投带来的量", "src": "链接"}, "newchain": {"v": "…", "why": "新链首发", "src": ""},
                         "subsidy": {"v": "…", "why": "返佣 / 补贴", "src": ""}, "organic": {"v": "…", "why": "去掉激励后的自然需求", "src": ""}},
                "next_review": "YYYY-MM-DD（比如积分结束后 7 天 / 30 天）",
                "counter": "最强反方一句话", "verdict": "研究观察|待核验|拒绝", "verdict_reason": "为什么", "missing": ["还没查清的事项"],
                "evidence": [{"url": "链接", "fields": ["支持了哪些字段"]}]}


def queue(cards):
    """补证队列：没补完的卡，按 手动线索 / 本站板块 → 新发现 → 可投资 → 收入 / TVL 排序。给每日自动补证会话和 Codex 用。"""
    q = [c for c in cards if c["status"] in ("原始线索", "待核验")]
    own = lambda c: any(x == "manual" or x.startswith("site_") for x in c["data"].get("sources") or [])   # 手动线索和本站板块筛到的排最前（11-15 定：来源以这两类为主）
    q.sort(key=lambda c: (not own(c), not c["fresh"], c["bucket"] != "invest", c["status"] != "原始线索", -(c["data"]["rev30"] or c["data"]["tvl"] or 0)))
    items = [{"key": c["key"], "name": c["name"], "status": c["status"], "kind": c["kind"], "fresh": c["fresh"], "bucket": c["bucket"],
              "discovered": c["discovered"], "category": c["data"]["category"], "chains": c["data"]["chains"], "rev30": c["data"]["rev30"], "tvl": c["data"]["tvl"],
              "defillama": f"https://defillama.com/protocol/{c['data']['slug']}" if c["data"].get("slug") else None, "url": c["data"].get("url"), "twitter": c["data"].get("twitter"), "manual": c.get("manual"),
              "pending": [k for k, v in c["scores"].items() if v["v"] == "U" and k not in ("P", "L")],
              "missing_before": (c.get("research") or {}).get("missing") or []} for c in q]
    return {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "n": len(items), "prompt": QUEUE_PROMPT, "schema": QUEUE_SCHEMA, "items": items}


def main():
    res = build()
    if "--no-series" not in sys.argv:
        ser = series(res["opps"])
        json.dump(ser, open(os.path.join(OUT, "opp_series.json"), "w", encoding="utf-8"), separators=(",", ":"))
        old = load(os.path.join(OUT, "rev_first.json"), {}) or {}
        old.update(FIRST_REV)
        json.dump(old, open(os.path.join(OUT, "rev_first.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    else:
        ser = load(os.path.join(OUT, "opp_series.json"), {}) or {}
    try:   # 项目上线天数、币上线天数、看盘入口（alpha/tokens.py；失败不影响出卡）
        import tokens
        manual = {"m:" + m["id"]: m for m in (load(os.path.join(HERE, "manual_leads.json"), {}) or {}).get("leads", [])}
        tokens.enrich(res["opps"], manual, load(os.path.join(OUT, "rev_first.json"), {}) or {})
    except Exception as e:
        print("代币信息失败：", str(e)[:160])
    try:   # 成交与变现（alpha/money.py；在 tokens 之后，要用上线天数）
        import money
        money.enrich(res["opps"])
    except Exception as e:
        print("成交与变现失败：", str(e)[:160])
    for c in res["opps"]:   # 列表里的 30 天迷你走势
        c["spark"] = [v for _, v in (ser.get(c["id"]) or [])[-30:]]
    q = queue(res["opps"])
    res["queue_n"] = q["n"]
    json.dump(res, open(os.path.join(OUT, "opps.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(q, open(os.path.join(OUT, "research_queue.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    SJ = load(os.path.join(HERE, "sources.json"), {}) or {}
    st = {}
    for c in res["opps"]:
        for sid in c["data"]["sources"]:
            a = st.setdefault(sid, {"cards": 0, "fresh": 0, "watching": 0, "rejected": 0, "pending": 0, "names": []})
            a["cards"] += 1
            a["fresh"] += bool(c["fresh"])
            a["watching"] += c["status"] in ("研究观察", "优先研究")
            a["rejected"] += c["status"] == "拒绝"
            a["pending"] += c["status"] in ("原始线索", "待核验")
            if c["fresh"] and len(a["names"]) < 6:
                a["names"].append({"id": c["id"], "name": c["name"]})
    json.dump({"generated": res["generated"], "note": SJ.get("_说明"), "sources": [dict(s, stats=st.get(s["id"], {"cards": 0, "fresh": 0, "watching": 0, "rejected": 0, "pending": 0, "names": []})) for s in SJ.get("sources", [])]},
              open(os.path.join(OUT, "sources_stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("机会卡", len(res["opps"]), res["counts"])


if __name__ == "__main__":
    main()
