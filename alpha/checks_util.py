#!/usr/bin/env python3
"""补证文件的统一合并规则（opps / alpha_daily / 出网站 / 任务清单 都用这一份）。

顺序：grok_* 先读，其余按 checked_utc（核对时间）；同一个 key 新的盖过旧的。两条例外（2026-11-16，Codex 首批 41 条里 35 条是空模板）：
  · 空壳 = 所有分数都是 U / NA 且证据链接不超过 1 条。空壳不许盖掉已有的补证；key 还没有补证时才记下它，并标 _stub，
    它的 entry（一律 none）和 one_liner（模板句）不采用，状态只记「待核验」。
  · alpha/review/patches.json：Claude 对个别字段的更正（{key: {字段: 值, "_why": 原因}}），在全部合并之后套上，不改原文件。
flow / events 两种写法都认：flow 可以是 {airdrop: {v, why, src}} 或 {"积分空投": "中", ..., "evidence": 链接}；events 的说明可以叫 what 或 zh。
events 里日期等于核对当天的（「今天去看了一眼」）不是项目事件，不展示。
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
RD = os.path.join(HERE, "review")
FLOW_ZH = {"积分空投": "airdrop", "积分 / 空投": "airdrop", "新链首发": "newchain", "补贴": "subsidy", "返佣 / 补贴": "subsidy", "自然需求": "organic"}


def _load(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def is_stub(c):
    sc = c.get("scores") or {}
    return all((s or {}).get("v") in ("U", "NA", None, "") for s in sc.values() if isinstance(s, dict)) and len(c.get("evidence") or []) <= 1


def norm(c):
    fl = c.get("flow")
    if isinstance(fl, dict) and fl and not any(isinstance(v, dict) for v in fl.values()):
        src = fl.get("evidence") or ""
        c["flow"] = {FLOW_ZH[k]: {"v": v, "why": "", "src": src} for k, v in fl.items() if k in FLOW_ZH}
    day = str(c.get("checked_utc") or "")[:10]
    ev = []
    for e in c.get("events") or []:
        if isinstance(e, dict) and e.get("date") and str(e["date"])[:10] != day:
            ev.append({"date": e["date"], "what": e.get("what") or e.get("zh") or "", "src": e.get("src")})
    c["events"] = ev
    return c


def files():
    import re
    return sorted((f for f in os.listdir(RD) if re.search(r"_checks(_\d+)?\.json$", f)), key=lambda f: (not f.startswith("grok_"), f.replace(".json", "")))   # 也认 _checks_2.json 这种同日第二批


def merged():
    """key → 最终采用的补证（带 _file；空壳带 _stub）。"""
    out, recs = {}, []
    for fn in files():
        for c in _load(os.path.join(RD, fn), []) or []:
            if isinstance(c, dict) and c.get("key"):
                recs.append((not fn.startswith("grok_"), str(c.get("checked_utc") or ""), fn, c))
    recs.sort(key=lambda r: r[:3])   # Grok 自动的先读；其余按核对时间，新的盖旧的（不按文件名：tokenless_checks 字母序排在 codex_ 后面，会盖掉更新的）
    for _, _, fn, c in recs:
        if is_stub(c):
            if c["key"] in out:
                continue
            c = dict(c, _stub=True, verdict="待核验")
            c.pop("entry", None); c.pop("one_liner", None)
        out[c["key"]] = norm(dict(c, _file=fn))
    for k, pt in (_load(os.path.join(RD, "patches.json"), {}) or {}).items():
        if k in out and isinstance(pt, dict):
            out[k].update({a: b for a, b in pt.items() if not a.startswith("_")})
    return out
