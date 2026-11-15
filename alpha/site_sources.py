#!/usr/bin/env python3
"""站内板块 → Alpha 线索（大叔 2026-11-15 定：来源以「关键人 + 本站自己的板块数据」为主，不天天扫合约）。

每个板块按写死的规则挑出「新东西」，交给 alpha_daily 登记进线索台账；规则和参数在 alpha_config.json 的 site_sources。
  发射台矩阵（data/发射台矩阵.json）
    lp_new     新平台起量：进矩阵不到 new_days 天（不是基线），近 7 天手续费 ≥ min_fee7
    lp_accel   平台突然放大：近 7 天手续费 ≥ min_fee7 且 ≥ 上 7 天的 accel_x 倍
    lp_chain   新链聚集：同一条链上 new_days 天内新进矩阵的平台 ≥ chain_n 个（一条线索，指向这条链的生态）
  AI Agent（data/aiagent/aiagent_latest.json）
    ai_new     新协议起量：手续费首日在 new_days 天内（或基线后新收录），近 7 天手续费 ≥ min_fee7
    ai_spike   板块自己标的 spike 事件（单日占比异常）
RWA、聪明钱板块上线后在这里各加一个函数。只读，不写任何板块的数据。
"""
import json, os
import datetime as dt

BOARDS = {"launchpad": {"zh": "发射台矩阵", "en": "Launchpad matrix", "href": "/launchpad/"},
          "aiagent": {"zh": "AI Agent", "en": "AI Agent", "href": "/ai-agent/"}}


def _load(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def launchpad(root, cfg):
    J = _load(os.path.join(root, "data", "发射台矩阵.json"))
    if not J:
        return []
    day = dt.date.fromisoformat(J["日期"])
    out, chains = [], {}
    for p in J.get("协议") or []:
        f, d7, p7 = p.get("首次出现"), p.get("7日") or 0, p.get("上7日") or 0
        age = (day - dt.date.fromisoformat(f)).days if f and f != "基线" else None
        new = age is not None and age <= cfg["new_days"]
        base = {"board": "launchpad", "slug": p["slug"], "name": p["名称"], "chains": (p.get("链") or [])[:3], "logo": p.get("logo"),
                "category": "Launchpad", "since": f if age is not None else None, "fees7": round(d7), "fees_prev7": round(p7), "fees30": round(p.get("30日") or 0), "parent": p.get("母协议"), "asof": J["日期"]}
        if new:
            for c in (p.get("链") or [])[:1]:
                chains.setdefault(c, []).append((p["名称"], d7))
        if new and d7 >= cfg["min_fee7"]:
            out.append(dict(base, rule="lp_new", why=f"进发射台矩阵 {age} 天，近 7 天手续费 {d7:,.0f} 美元"))
        elif d7 >= cfg["min_fee7"] and d7 >= cfg["accel_x"] * p7:
            out.append(dict(base, rule="lp_accel", why=f"近 7 天手续费 {d7:,.0f} 美元，是上 7 天（{p7:,.0f}）的 {d7 / p7:.1f} 倍" if p7 else f"近 7 天手续费 {d7:,.0f} 美元，上 7 天没有"))
    for c, xs in chains.items():
        if len(xs) >= cfg["chain_n"] and sum(v for _, v in xs) >= cfg["min_fee7"]:
            xs.sort(key=lambda t: -t[1])
            out.append({"board": "launchpad", "slug": None, "id": "chain-" + c.lower().replace(" ", "-"), "name": f"{c} 生态（新发射台聚集）", "chains": [c], "category": "新链生态",
                        "rule": "lp_chain", "fees7": round(sum(v for _, v in xs)), "fees30": None, "asof": J["日期"],
                        "why": f"{cfg['new_days']} 天内 {c} 上新进矩阵的发射台有 {len(xs)} 个：{'、'.join(n for n, _ in xs[:6])}；合计近 7 天手续费 {sum(v for _, v in xs):,.0f} 美元"})
    return out


def aiagent(root, cfg):
    J = _load(os.path.join(root, "data", "aiagent", "aiagent_latest.json"))
    if not J:
        return []
    day = dt.date.fromisoformat(J["asof"])
    out, seen = [], set()
    for p in J.get("protocols") or []:
        fd, d7 = p.get("first_day"), p.get("d7") or 0
        young = fd and (day - dt.date.fromisoformat(fd)).days <= cfg["new_days"]
        newly = p.get("first_seen") not in (None, "基线")
        if (young or newly) and d7 >= cfg["min_fee7"]:
            seen.add(p["slug"])
            out.append({"board": "aiagent", "slug": p["slug"], "name": p["name"], "chains": (p.get("chains") or [])[:3], "category": "AI Agents · " + str(p.get("layer")),
                        "rule": "ai_new", "since": fd, "fees7": round(d7), "fees30": round(p.get("f30") or 0), "asof": J["asof"],
                        "why": f"AI Agent 板块：手续费从 {fd} 才开始，近 7 天 {d7:,.0f} 美元" + (f"；板块备注：{p['note_zh']}" if p.get("note_zh") else "")})
    for e in J.get("events") or []:
        if e.get("type") == "spike" and e.get("slug") not in seen:
            out.append({"board": "aiagent", "slug": e["slug"], "name": e["name"], "chains": None, "category": "AI Agents · " + str(e.get("layer")),
                        "rule": "ai_spike", "fees7": None, "fees30": None, "asof": J["asof"], "why": f"AI Agent 板块标了异常：单日手续费占近 30 天的 {e.get('share', 0):.0f}%"})
    return out


def collect(root, cfg):
    cfg = cfg or {}
    out = []
    for name, fn in (("launchpad", launchpad), ("aiagent", aiagent)):
        c = cfg.get(name)
        if c:
            out += fn(root, c)
    return out


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    for r in collect(os.path.dirname(here), _load(os.path.join(here, "alpha_config.json")).get("site_sources")):
        print(r["board"], r["rule"], r["name"], "·", r["why"])
