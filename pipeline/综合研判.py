# -*- coding: utf-8 -*-
"""综合研判 · L1~L4 四层合成（纯函数，不联网）

分工沿用研究里定下的：L2 给方向的底色；L1 管节奏和风险预算、不管方向；L3 看筹码是否支持这个方向；L4 只描述短期温度、不改变动作。
一句话 =「{方向句}；{但}{节奏句}，{动作}。{筹码背离提示}{短期提示}」，四段固定顺序：方向 · L2 → 节奏 · L1 → 筹码 · L3 → 短期 · L4。
所有短句、动作、逆风触发原因都在 config/composite.json（附录 D 定稿），改措辞只改配置，不改代码。
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(ROOT, "config", "composite.json")
RULE_DATE = "2026-10-08"          # 四层合成规则上线日（更正记录、日志列表分隔行用）


def load_cfg():
    with open(CFG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _num(v):
    return f"{abs(v):,.0f}"


def l1_tier(v1):
    t = (v1 or {}).get("结论") or ""
    t = t.replace("·警戒", "")
    return t if t in ("顺风", "中性", "中性偏谨慎", "逆风") else None


def headwind_reason(v1, C):
    """逆风的触发原因：按配置表顺序取第一条实际成立的。"""
    st = (v1 or {}).get("状态") or {}
    surge = st.get("实际利率") == "急升"
    hits = [surge and (st.get("baa") or 0) > 0, surge and (st.get("nfci") or 0) > 0,
            surge and st.get("z") is not None and st["z"] < 0, bool((v1 or {}).get("闸门"))]
    for h, r in zip(hits, C["逆风原因"]):
        if h:
            return r["中文"], r["英文"]
    return "宏观条件转紧", "Macro conditions have tightened"


def l3_kind(rs):
    by = {x["key"]: x for x in rs if x}
    f = by.get("ex_netflow")
    if not f or f["过期"]:
        return None, None
    if f["分"] > 0:
        return "流出", f["值"]
    if f["分"] < 0:
        return "流入", f["值"]
    return "均衡", f["值"]


L4_NAME = {"hl_oi": ("未平仓合约 7 日", "open interest 7d"), "hl_funding": ("资金费率年化", "funding, annualized"),
           "fng": ("恐慌贪婪指数", "Fear & Greed")}


def l4_kind(v4, rs):
    short = (v4 or {}).get("短") or ""
    kind = {"情绪过热": "过热", "情绪偏热": "偏热", "情绪中性": "中性", "情绪偏冷": "偏冷"}.get(short)
    if not kind:
        return None, ("", "")
    by = {x["key"]: x for x in rs if x and x["层"] == 4}
    want = 1 if kind in ("过热", "偏热") else (-1 if kind == "偏冷" else 0)
    for k in ("hl_oi", "hl_funding", "fng"):           # 关键读数优先级：未平仓合约 7 日变化 > 资金费率 > 恐慌贪婪
        x = by.get(k)
        if x and not x["过期"] and want and (x["分"] > 0) == (want > 0) and x["分"] != 0:
            return kind, (f"{L4_NAME[k][0]} {x['显示']}", f"{L4_NAME[k][1]} {x['显示']}")
    return kind, ("", "")


def compose(vs, rs, l2):
    """vs = {层: 层结论}；rs = 当天全部读数；l2 = l2_latest.json。返回写进日志 / 页面的综合研判。"""
    C = load_cfg()
    # ---- 方向 · L2
    code = ((l2 or {}).get("state") or {}).get("code")
    d2 = C["L2"].get(code) or C["L2"]["_缺"]
    direction = d2["方向"]
    st, cy = (l2 or {}).get("state") or {}, (l2 or {}).get("cycle") or {}
    n_zone = ((l2 or {}).get("counts") or {}).get("bottom_zone", 0)
    low = cy.get("cycle_low")
    fill = {"n": n_zone, "天数": st.get("days", "—"), "days": st.get("days", "—"), "价格": _num(low) if low else "—", "price": _num(low) if low else "—"}
    seg2 = (d2["分段"].format(**fill), d2["分段EN"].format(**fill))
    num2 = (f"第 {st.get('days')} 天", f"day {st.get('days')}") if st.get("days") else ("", "")
    # ---- 节奏 · L1
    v1 = vs.get(1) or {}
    tier = l1_tier(v1)
    d1 = C["L1"].get(tier) or C["L1"]["_缺"]
    if tier == "逆风":
        rz, re_ = headwind_reason(v1, C)
        seg1 = (d1["分段"].format(触发原因=rz), d1["分段EN"].format(trigger=re_))
    else:
        seg1 = (d1["分段"], d1["分段EN"])
    if v1.get("警戒"):
        seg1 = (seg1[0] + C["L1"]["警戒"]["分段"], seg1[1] + " " + C["L1"]["警戒"]["分段EN"])
    real = next((x for x in rs if x and x["key"] == "real13"), None)
    r13 = f"{real['值']:+.2f}".replace("-", "\u2212") if real else ""
    num1 = ((f"实际利率 {real['显示']}，13 周 {r13}pp", f"real yield {real['显示']}, 13w {r13}pp") if real else ("", ""))
    act = C["动作"].get(direction, C["动作"]["待确认"]).get(tier) if tier else None
    # ---- 筹码 · L3
    k3, v3 = l3_kind(rs)
    d3 = C["L3"].get(k3) or C["L3"]["_缺"]
    seg3 = (d3["分段"].format(数值=_num(v3) if v3 is not None else "—"), d3["分段EN"].format(value=_num(v3) if v3 is not None else "—"))
    rel = None
    if k3 and direction != "待确认":
        rel = "一致" if direction in d3.get("一致", []) else ("背离" if direction in d3.get("背离", []) else None)
    n3 = f"{v3:+,.0f}".replace("-", "\u2212") if v3 is not None else ""
    num3 = ((f"7 日 {n3} BTC", f"7d {n3} BTC") if v3 is not None else ("", ""))
    # ---- 短期 · L4
    k4, kr = l4_kind(vs.get(4), rs)
    d4 = C["L4"].get(k4) or C["L4"]["_缺"]
    seg4 = (d4["分段"].format(关键读数=kr[0]), d4["分段EN"].format(reading=kr[1]))
    # ---- 一句话（确定性拼接）
    but = (direction == "偏多" and tier in ("中性偏谨慎", "逆风")) or (direction in ("偏空", "防顶") and tier == "顺风")
    if act:
        head = f"{d2['一句话']}；{'但' if but else ''}{d1['一句话']}，{act[0]}。"
        but_en = but and not act[1].startswith("but ")          # 动作本身以 but 开头时不再重复
        head_en = f"{d2['一句话EN']}; {'but ' if but_en else ''}{d1['一句话EN']}—{act[1]}."
    else:
        head = f"{d2['一句话']}；{d1['一句话']}。"
        head_en = f"{d2['一句话EN']}; {d1['一句话EN']}."
    div = C["L3"]["背离句"] if rel == "背离" else ["", ""]
    sh = (d4.get("一句话") or "", d4.get("一句话EN") or "")
    sh = (sh[0] + "。" if sh[0] else "", (sh[1][:1].upper() + sh[1][1:] + ".") if sh[1] else "")
    cap = C.get("一句话上限", 60)
    parts = [(head, head_en), tuple(div), sh]
    if len(head + div[0] + sh[0]) > cap:
        parts[2] = ("", "")
    if len(head + parts[1][0] + parts[2][0]) > cap:
        parts[1] = ("", "")
    one = "".join(p[0] for p in parts)
    one_en = " ".join(p[1] for p in parts if p[1])
    segs = [
        {"层": 2, "标签": "方向", "标签EN": "Direction", "文本": seg2[0], "文本EN": seg2[1], "数字": num2[0], "数字EN": num2[1],
         "tone": (vs.get(2) or {}).get("tone", "neutral"), "短": (vs.get(2) or {}).get("短"), "短EN": (vs.get(2) or {}).get("短EN")},
        {"层": 1, "标签": "节奏", "标签EN": "Pace", "文本": seg1[0], "文本EN": seg1[1], "数字": num1[0], "数字EN": num1[1],
         "tone": v1.get("tone", "neutral"), "短": v1.get("短"), "短EN": v1.get("短EN")},
        {"层": 3, "标签": "筹码", "标签EN": "Flows", "文本": seg3[0], "文本EN": seg3[1], "数字": num3[0], "数字EN": num3[1],
         "tone": (vs.get(3) or {}).get("tone", "neutral"), "短": (vs.get(3) or {}).get("短"), "短EN": (vs.get(3) or {}).get("短EN"),
         "关系": C["L3"][rel][0] if rel else None, "关系EN": C["L3"][rel][1] if rel else None, "关系类": rel},
        {"层": 4, "标签": "短期", "标签EN": "Short term", "文本": seg4[0], "文本EN": seg4[1], "数字": kr[0], "数字EN": kr[1],
         "tone": (vs.get(4) or {}).get("tone", "neutral"), "短": (vs.get(4) or {}).get("短"), "短EN": (vs.get(4) or {}).get("短EN")},
    ]
    tags = [x.get("短") for x in (vs.get(i, {}) for i in (1, 2, 3, 4)) if x.get("短") and x.get("短") != "数据不足"]
    tags_en = [x.get("短EN") for x in (vs.get(i, {}) for i in (1, 2, 3, 4)) if x.get("短EN") and x.get("短") != "数据不足"]
    return {"规则": "四层合成", "一句话": one, "一句话EN": one_en, "段": segs, "小字": C["小字"][0], "小字EN": C["小字"][1],
            "方向": direction, "L1档": tier, "标签": tags, "标签EN": tags_en}
