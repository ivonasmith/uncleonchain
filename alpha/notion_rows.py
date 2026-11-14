#!/usr/bin/env python3
"""把 Alpha 雷达的数据转成 Notion「Alpha 雷达」入口下各数据库的行（服务器同步 alpha/notion_sync.py 和会话手工同步共用这一份口径）。

Notion 入口页：https://app.notion.com/p/418b72fc8cae8152b4c2f062d2ac389c（只放 Alpha 板块的东西，不和别的板块混）
数据库（data_source）：
  机会卡（应用层）   collection://418b72fc-8cae-815f-9f1a-000b40f30100   ← data/alpha/opps.json（按「卡片ID」更新，没有就新建）
  周复盘             collection://418b72fc-8cae-8104-ad03-000b4f5d96f3   ← data/alpha/weekly/<周>.json（每周一行）
  线索台账（清洗层） collection://418b72fc-8cae-8127-9d38-000bb9984f0b   ← data/alpha/alpha_leads.json（按 key 只追加；状态 / 发币日更新）
  历史案例库（清洗层）collection://418b72fc-8cae-811d-9360-000b10e75a02  ← alpha/cases.json + data/alpha/case_metrics.json
  数据源台账（原始层）collection://418b72fc-8cae-8176-bf2b-000b181bb3dd
  规则版本           collection://418b72fc-8cae-81ef-97a9-000bf6f99697   ← 框架 / 参数每次变化手工加一行
用法：python3 alpha/notion_rows.py opps|leads|cases|weekly [--week 2026-W46] [--since 2026-11-14]  → 打印 JSON 数组（每个元素是 properties）
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
D = os.path.join(ROOT, "data", "alpha")
FW = json.load(open(os.path.join(HERE, "framework.json"), encoding="utf-8"))
NAME = lambda grp: {o["k"]: o["name"].split("（")[0] for o in (FW["classes"][grp] if grp in FW["classes"] else FW[grp])["opts"]}


def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def iv(vals, mx=4):
    ap = [v for v in vals if v != "NA"]
    kn = [v for v in ap if v not in ("U", None, "")]
    s, u, m = sum(kn), len(ap) - len(kn), len(ap)
    return f"{round(100 * s / (mx * m))}–{round(100 * (s + mx * u) / (mx * m))}（覆盖 {round(100 * len(kn) / m)}%）"


def opps():
    d = load(os.path.join(D, "opps.json"), {})
    ent, biz = NAME("entry"), NAME("business")
    out = []
    for o in d.get("opps", []):
        sc = o["scores"]
        r = o.get("research") or {}
        p = {"名称": o["name"], "卡片ID": o["id"], "分栏": {"invest": "可投资机会", "watch": "预警观察", "reject": "已拒绝"}[o["bucket"]],
             "状态": o["status"], "类型": "无币协议" if o["kind"] == "tokenless" else "新上架协议",
             "资金参与方式": [ent[e] for e in o["entry"]], "需求来源": biz.get(o["classes"]["business"]["v"], "尚未判明"),
             "机制区间": iv([sc[k]["v"] for k in "MAFEV"]), "参与优势区间": iv([sc[k]["v"] for k in "GDT"]),
             "待补项数": sum(1 for k in "MAFEVGDT" if sc[k]["v"] == "U"),
             "发币表态": r.get("token_stance") or "", "最强反方": (r.get("counter") or "")[:1900],
             "网站": f"https://uncleonchain.com/alpha/opp/#{o['id']}"}
        if o["data"].get("rev30") is not None:
            p["30天收入"] = o["data"]["rev30"]
        if o["data"].get("chg30") is not None:
            p["收入环比%"] = o["data"]["chg30"]
        if o.get("discovered"):
            p["date:首次发现:start"] = o["discovered"]
        if r.get("checked_utc"):
            p["date:核对日:start"] = r["checked_utc"][:10]
        out.append(p)
    return out


def leads(since=None):
    L = (load(os.path.join(D, "alpha_leads.json"), {}) or {}).get("leads", {})
    out = []
    for v in L.values():
        if since and v["first_seen"] < since:
            continue
        f = v.get("first") or {}
        p = {"线索": v["name"] or v["key"], "key": v["key"],
             "来源": [{"tokenless_rev": "无币收入榜", "new_listing": "新上架"}[s] for s in v["source"].split("+")],
             "date:首次发现:start": v["first_seen"], "基线": "__YES__" if v.get("baseline") else "__NO__", "状态": v.get("status") or "原始线索",
             "首次读数": (f"30天收入 ${f['rev30']:,.0f}" if f.get("rev30") is not None else f"TVL ${f.get('tvl') or 0:,.0f}"), "类目": f.get("category") or ""}
        if v.get("token_seen"):
            p["date:发币日:start"] = v["token_seen"]
        out.append(p)
    return out


def cases():
    cs = load(os.path.join(HERE, "cases.json"))["cases"]
    m = (load(os.path.join(D, "case_metrics.json"), {}) or {}).get("cases", {})
    biz, rt = NAME("business"), NAME("right")
    out = []
    for c in cs:
        r = m.get(c["id"], {})
        t = next((x for x in r.get("tokens", []) if x["role"] == "main"), None)
        p = {"案例": c["name"], "时期": c["period"], "对照组": "__YES__" if c["control"] else "__NO__",
             "需求来源": biz.get(c["classes"]["business"], ""), "资产权利": rt.get(c["classes"]["right"], ""), "教训": c["lesson"]}
        for k in "MAFEVD":
            if c["scores"].get(k) not in ("U", None):
                p[k] = c["scores"][k]
        if t:
            for k, src in (("估值峰值", "val_peak"), ("首日倍数", "mult"), ("首周后倍数", "mult_p7"), ("到峰天数", "days_to_peak")):
                if t.get(src) is not None:
                    p[k] = round(t[src], 2) if isinstance(t[src], float) else t[src]
        if r.get("fees"):
            p["30天手续费峰值"] = r["fees"]["peak30"]
        out.append(p)
    return out


def weekly(tag):
    w = load(os.path.join(D, "weekly", f"{tag}.json"))
    fails = "；".join(f"{k} 失败 {v} 天" for k, v in (w["sources_fail_days"] or {}).items() if v) or "无"
    a = w["a4"]
    return [{"周": w["week"], "date:开始:start": w["from"], "有数据天数": w["days_with_data"], "新增线索": w["leads"]["new"], "状态变化": len(w["leads"]["status_changes"]),
             "发币": len(w["leads"]["token_launch"]), "事件流新增": w["feed"]["new"], **({"发现延迟中位(小时)": w["feed"]["delay_median_h"]} if w["feed"]["delay_median_h"] is not None else {}),
             "数据源异常": fails, "可投资": (w["board"]["counts"] or {}).get("invest"), "预警观察": (w["board"]["counts"] or {}).get("watch"),
             "A4进度": f"研究观察 {a['watch_n']} / 对照 {a['control_n']}；" + ("可以判" if a["judgeable"] else "样本不够，记录中") + (f"；距第 90 天 {a['days_to_d90']} 天" if a["days_to_d90"] is not None else ""),
             **({"收入中位": round(w["threshold"]["p50"])} if w["threshold"]["p50"] else {}), **md_conclusion(tag)}]


def md_conclusion(tag):
    """复盘会话写在 data/alpha/weekly/<周>.md「本周结论 / 规则调整」一节的内容（占位行不算）。"""
    try:
        md = open(os.path.join(D, "weekly", f"{tag}.md"), encoding="utf-8").read()
    except Exception:
        return {}
    sec = md.split("## 本周结论 / 规则调整", 1)[1].strip() if "## 本周结论 / 规则调整" in md else ""
    if not sec or "复盘会话填写" in sec:
        return {}
    return {"结论": sec[:1900]}


if __name__ == "__main__":
    a = sys.argv[1]
    arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
    rows = {"opps": opps, "cases": cases}.get(a, lambda: None)() if a in ("opps", "cases") else leads(arg("--since")) if a == "leads" else weekly(arg("--week"))
    print(json.dumps(rows, ensure_ascii=False))
