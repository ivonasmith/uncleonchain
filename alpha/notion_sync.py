#!/usr/bin/env python3
"""Alpha 雷达 → Notion「Alpha 雷达」入口页（服务器端同步，GitHub Actions 跑，不依赖 Claude 会话）。

需要 repo secret NOTION_TOKEN（Notion 内部集成 token），并且「Alpha 雷达」页面已连接这个集成。没有 token 就跳过（退出码 0）。
行数据来自 alpha/notion_rows.py（和手工同步同一份口径），按唯一键 upsert：
  opps    机会卡    键「卡片ID」  每天
  leads   线索台账  键「key」     每天（只同步有研究状态的和基线日之后新进的；完整台账在仓库 data/alpha/alpha_leads.json）
  weekly  周复盘    键「周」      每周一（结论 / 规则调整只在 Notion 里为空时才从 data/alpha/weekly/<周>.md 带入，不覆盖人写的）
用法：python3 alpha/notion_sync.py opps leads [weekly --week 2026-W46] [--dry]
"""
import json, os, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import notion_rows as NR  # noqa: E402

API = "https://api.notion.com/v1"
VER = "2022-06-28"
DB = {  # 数据库 ID（入口页 https://app.notion.com/p/418b72fc8cae8152b4c2f062d2ac389c 下）
    "opps": ("418b72fc8cae8111b3afe313d462105c", "卡片ID"),
    "leads": ("418b72fc8cae8165a439e54d14c26790", "key"),
    "weekly": ("418b72fc8cae816ebe86ee3924f99e31", "周"),
}
TYPES = {
    "opps": {"名称": "title", "卡片ID": "rich_text", "分栏": "select", "状态": "select", "类型": "select", "资金参与方式": "multi_select", "需求来源": "select",
             "机制区间": "rich_text", "参与优势区间": "rich_text", "待补项数": "number", "30天收入": "number", "收入环比%": "number", "发币表态": "rich_text",
             "最强反方": "rich_text", "首次发现": "date", "核对日": "date", "网站": "url"},
    "leads": {"线索": "title", "key": "rich_text", "来源": "multi_select", "首次发现": "date", "基线": "checkbox", "状态": "select", "首次读数": "rich_text", "类目": "rich_text", "发币日": "date"},
    "weekly": {"周": "title", "开始": "date", "有数据天数": "number", "新增线索": "number", "状态变化": "number", "发币": "number", "事件流新增": "number", "发现延迟中位(小时)": "number",
               "数据源异常": "rich_text", "可投资": "number", "预警观察": "number", "A4进度": "rich_text", "收入中位": "number", "结论": "rich_text", "规则调整": "rich_text"},
}
KEEP_IF_SET = {"weekly": {"结论", "规则调整"}}   # Notion 里已有内容就不覆盖
TOKEN = os.environ.get("NOTION_TOKEN", "")
DRY = "--dry" in sys.argv


def call(method, path, body=None):
    for i in range(4):
        req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {TOKEN}", "Notion-Version": VER, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                time.sleep(0.35)   # Notion 限速约 3 次 / 秒
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and i < 3:
                time.sleep(2 * (i + 1)); continue
            raise RuntimeError(f"{method} {path}: {e.code} {e.read()[:300]!r}")


def prop(t, v):
    if t == "title":
        return {"title": [{"text": {"content": str(v)[:1900]}}]}
    if t == "rich_text":
        return {"rich_text": [{"text": {"content": str(v)[:1900]}}] if v not in (None, "") else []}
    if t == "select":
        return {"select": {"name": str(v)} if v else None}
    if t == "multi_select":
        return {"multi_select": [{"name": str(x)} for x in (v or [])]}
    if t == "number":
        return {"number": v}
    if t == "url":
        return {"url": v or None}
    if t == "checkbox":
        return {"checkbox": v == "__YES__" or v is True}
    if t == "date":
        return {"date": {"start": v} if v else None}
    raise ValueError(t)


def to_props(kind, row):
    out = {}
    for k, v in row.items():
        name = k.split(":")[1] if k.startswith("date:") else k
        t = TYPES[kind].get(name)
        if t:
            out[name] = prop(t, v)
    return out


def find(db, keyprop, ktype, val):
    f = {"property": keyprop, ("title" if ktype == "title" else "rich_text"): {"equals": val}}
    r = call("POST", f"/databases/{db}/query", {"filter": f, "page_size": 1})
    return (r.get("results") or [None])[0]


def has_text(page, name):
    p = (page.get("properties") or {}).get(name) or {}
    return bool(p.get("rich_text") or p.get("title"))


def sync(kind, rows):
    db, keyprop = DB[kind]
    ktype = TYPES[kind][keyprop]
    made = upd = 0
    for row in rows:
        props = to_props(kind, row)
        key = row.get(keyprop)
        if DRY:
            print(kind, key, json.dumps(props, ensure_ascii=False)[:200]); continue
        page = find(db, keyprop, ktype, key)
        if page:
            for name in KEEP_IF_SET.get(kind, ()):
                if name in props and has_text(page, name):
                    props.pop(name)
            call("PATCH", f"/pages/{page['id']}", {"properties": props}); upd += 1
        else:
            call("POST", "/pages", {"parent": {"database_id": db}, "properties": props}); made += 1
    print(f"{kind}: 新建 {made}，更新 {upd}，共 {len(rows)}")


def main():
    if not TOKEN and not DRY:
        print("没有 NOTION_TOKEN，跳过 Notion 同步"); return
    args = sys.argv[1:]
    if "opps" in args:
        sync("opps", NR.opps())
    if "leads" in args:
        sync("leads", [r for r in NR.leads() if r["状态"] != "原始线索" or r["基线"] == "__NO__"])
    if "weekly" in args:
        wk = args[args.index("--week") + 1] if "--week" in args else None
        if wk:
            sync("weekly", NR.weekly(wk))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:   # 同步失败不影响日更
        print("Notion 同步失败：", e)
