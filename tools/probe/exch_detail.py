#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测 OKX / Bitget 上币公告详情页的正文结构（只读，不写数据）。
在 Actions 上跑（沙盒连不上这些域名）。输出：每家取 2 条公告的正文里和「开盘 / 交易对 / UTC」相关的片段。
"""
import json, re, sys, urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"}
KEY = re.compile(r"(UTC|trading|open|launch|list|pair|/USDT|/USD|perpetual|spot)", re.I)


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def snippets(text, n=6, w=160):
    out = []
    for m in KEY.finditer(text):
        out.append(text[max(0, m.start() - w // 2): m.end() + w // 2].replace("\n", " "))
        if len(out) >= n:
            break
    return out


def show(name, url):
    try:
        html = get(url)
    except Exception as e:
        print(f"{name}: 取页失败 {url} {str(e)[:120]}")
        return
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"\s+", " ", body)
    print(f"{name}: {url} · 字节 {len(html)} · 正文字符 {len(body)}")
    print("  标题线索:", re.findall(r"<title>(.*?)</title>", html, re.S | re.I)[:1])
    print("  __NEXT_DATA__ 或 JSON 内嵌:", "__NEXT_DATA__" in html, "· application/json 脚本数:", html.count('type="application/json"'))
    for s in snippets(body):
        print("   ·", s[:260])


def main():
    d = json.load(open("data/alpha/exch_announce.json", encoding="utf-8"))
    items = [v for v in d["items"].values() if v["exchange"] in ("OKX", "Bitget")]
    seen = {}
    for v in items:
        seen.setdefault(v["exchange"], [])
        if len(seen[v["exchange"]]) < 2 and v.get("kind") != "other":
            seen[v["exchange"]].append(v)
    for ex, rows in seen.items():
        for v in rows:
            show(f"{ex} · {v['title'][:70]}", v["url"])
    # Bitget 详情页可能需要 API：列一条原始 JSON 字段名
    try:
        j = json.loads(get("https://api.bitget.com/api/v2/public/annoucements?annType=coin_listings&language=en_US"))
        first = (j.get("data") or [{}])[0]
        print("Bitget 列表字段:", sorted(first.keys()))
    except Exception as e:
        print("Bitget 列表失败", str(e)[:120])


if __name__ == "__main__":
    sys.exit(main())
