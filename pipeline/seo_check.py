#!/usr/bin/env python3
"""SEO 构建检查（docs/SEO规范.md 基建 4）：出网站后跑，只报警告不拦构建。

检查每个 index.html：
  - 有 <title>，且（同一语言里）不和别的页重复
  - 有 description：中文 20～150 字、英文 40～220 字符
  - 有 canonical（noindex 的除外）
  - 正文不能是空壳：去掉导航 / 页脚 / 脚本后可见文字太少，且含「读取中…」/「Loading…」
  - sitemap.xml 里每个 URL 都有对应文件

用法：python3 pipeline/seo_check.py [site 目录]；出网站.py 末尾会自动调一次。
"""
import os, re, sys, html
from collections import defaultdict

SKIP_DIRS = {"data", "assets", "monitor"}   # 数据文件、静态资源、原样发布的交接包页面


def _text(h):
    h = re.sub(r"(?is)<(script|style|template|nav|footer|aside)\b.*?</\1>", " ", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(h)).strip()


def _self_canonical(h, rel):
    m = re.search(r'rel="canonical" href="https://[^/]+(/[^"]*)"', h)
    return not m or m.group(1) == rel


def check(site):
    warns = defaultdict(list)
    titles = defaultdict(list)
    n = 0
    for root, dirs, files in os.walk(site):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f != "index.html":
                continue
            fp = os.path.join(root, f)
            rel = "/" + os.path.relpath(root, site).replace(os.sep, "/").strip(".") + "/"
            rel = re.sub(r"/+", "/", rel)
            h = open(fp, encoding="utf-8", errors="ignore").read()
            if 'http-equiv="refresh"' in h:
                continue
            n += 1
            en = rel.startswith("/en/")
            noindex = 'name="robots" content="noindex' in h
            m = re.search(r"<title>(.*?)</title>", h, re.S)
            if not m or not m.group(1).strip():
                warns["缺 title"].append(rel)
            elif not noindex and _self_canonical(h, rel):
                titles[(en, html.unescape(m.group(1).strip()))].append(rel)
            m = re.search(r'<meta name="description" content="([^"]*)"', h)
            d = html.unescape(m.group(1)) if m else ""
            lo, hi = (40, 220) if en else (20, 150)
            if not d:
                warns["缺 description"].append(rel)
            elif not noindex and not (lo <= len(d) <= hi):
                warns["description 长度不对（中文 20～150 字 / 英文 40～220 字符）"].append(f"{rel}（{len(d)}）")
            if not noindex and 'rel="canonical"' not in h:
                warns["缺 canonical"].append(rel)
            main = re.search(r'(?s)<main class="main">(.*)</main>', h)
            body = _text(main.group(1)) if main else _text(h)
            if not noindex and ("读取中" in body or "Loading…" in body) and len(body) < 400:
                warns["空壳页（正文只有「读取中…」，首屏数字要写进 HTML）"].append(rel)
    for (en, t), us in titles.items():
        if len(us) > 1:
            warns["title 重复"].append(f"{t} ← {', '.join(us[:4])}{' …' if len(us) > 4 else ''}")
    sm = os.path.join(site, "sitemap.xml")
    if os.path.exists(sm):
        for loc in re.findall(r"<loc>https://[^/]+(/[^<]*)</loc>", open(sm, encoding="utf-8").read()):
            if not os.path.exists(os.path.join(site, loc.strip("/"), "index.html")) and loc != "/":
                warns["sitemap 里的 URL 没有文件"].append(loc)
    else:
        warns["没有 sitemap.xml"].append("/")
    return n, warns


def run(site, limit=6):
    n, warns = check(site)
    tot = sum(len(v) for v in warns.values())
    print(f"SEO 检查：{n} 页，{tot} 条警告" + ("" if tot else " ✓"))
    for k, v in sorted(warns.items(), key=lambda kv: -len(kv[1])):
        print(f"  ⚠️ {k}：{len(v)}")
        for x in v[:limit]:
            print(f"      {x}")
    return warns


if __name__ == "__main__":
    site = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")
    run(os.path.abspath(site), limit=int(os.environ.get("SEO_LIMIT", "20")))
