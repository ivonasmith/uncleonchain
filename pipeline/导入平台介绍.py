#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把大叔在 Grok 网页版问来的平台介绍导入 data/onchain/平台AI介绍.json（2026-11-13 定：不走 API，手动问免费）。

用法：python3 pipeline/导入平台介绍.py 回复1.txt [回复2.txt …]
  每个文件是 Grok 的整段回复，里面有一个或多个 ```json 代码块，外层键 = 平台 slug。
  字段和 写平台介绍.py 的 SCHEMA 一样；缺的字段补空，多的忽略。同一个 slug 再导入会覆盖。
"""
import os, re, sys, json, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.abspath(os.environ.get("LP_DATA") or os.path.join(ROOT, "data"))
OUT = os.path.join(DATA, "onchain", "平台AI介绍.json")
TEXT = ["one_liner", "differentiation", "fee_split", "token", "team"]
LIST = ["selling_points", "risks", "unknowns"]


def blocks(text):
    """先找 ```json 代码块；没有就找最外层的 { … }。"""
    got = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if not got:
        i, j = text.find("{"), text.rfind("}")
        got = [text[i:j + 1]] if i >= 0 and j > i else []
    out = []
    for g in got:
        try:
            out.append(json.loads(g))
        except json.JSONDecodeError as ex:
            print(f"  有一段不是合法 JSON，跳过：{ex}")
    return out


def clean(d):
    c = {}
    for k in TEXT:
        for l in ("zh", "en"):
            c[f"{k}_{l}"] = str(d.get(f"{k}_{l}") or "").strip()
    for k in LIST:
        for l in ("zh", "en"):
            v = d.get(f"{k}_{l}") or []
            c[f"{k}_{l}"] = [str(x).strip() for x in (v if isinstance(v, list) else [v]) if str(x).strip()]
    c["sources"] = [{"url": str(x.get("url", "")).strip(), "kind": str(x.get("kind", "")).strip().lower(), "note": str(x.get("note", "")).strip()}
                    for x in (d.get("sources") or []) if isinstance(x, dict) and str(x.get("url", "")).startswith("http")]
    return c


def main(paths):
    known = set()
    try:
        m = json.load(open(os.path.join(DATA, "发射台矩阵.json"), encoding="utf-8"))
        known = {p["slug"] for p in m.get("协议") or []}
    except Exception:
        pass
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    today = dt.date.today().isoformat()
    n = 0
    for path in paths:
        for obj in blocks(open(path, encoding="utf-8").read()):
            items = [(obj["slug"], obj)] if "slug" in obj and "one_liner_zh" in obj else list(obj.items())
            for slug, d in items:
                if not isinstance(d, dict) or not d.get("one_liner_zh"):
                    print(f"  {slug}：没有 one_liner_zh，跳过")
                    continue
                if known and slug not in known:
                    print(f"  {slug}：不在发射台矩阵里（slug 拼错了？），先导入，页面上不会显示")
                out[slug] = {"日期": today, "模型": "Grok（网页版，大叔手动问）", "方式": "手动", "内容": clean(d)}
                n += 1
                print(f"  导入 {slug}：卖点 {len(out[slug]['内容']['selling_points_zh'])} 条、来源 {len(out[slug]['内容']['sources'])} 条")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"共导入 {n} 个，文件里现有 {len(out)} 个")


if __name__ == "__main__":
    main(sys.argv[1:])
