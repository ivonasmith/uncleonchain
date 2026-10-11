# -*- coding: utf-8 -*-
"""报告 PDF：把 content/reports/ 里每篇整篇 HTML 报告打印成 A4 PDF，存到 content/reports/pdf/。

  中文 <slug>.pdf，英文 <slug>.en.pdf；只出浅色版（PDF 是拿去读、转发、打印的，深色版费墨也不好读）。
  报告发布后不改，所以已有的 PDF 默认跳过；--force 全部重出。
  需要 Playwright + Chromium（本地沙箱有，/opt/pw-browsers）；Actions 里不跑，出网站时只是把 pdf/ 拷进 site/。

用法：python3 pipeline/出报告PDF.py [--force] [slug ...]
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "content", "reports")
OUT = os.path.join(REPORTS, "pdf")

FOOT = {"zh": "链上大叔研究台 · uncleonchain.com", "en": "Uncle Onchain · uncleonchain.com"}


def strip_webfonts(h):
    h = re.sub(r'<link[^>]*fonts\.(?:googleapis|gstatic)\.com[^>]*>\s*', "", h)
    return re.sub(r'@import\s+url\([^)]*fonts\.googleapis\.com[^)]*\)\s*;?', "", h)


def jobs(only):
    for f in sorted(os.listdir(REPORTS)):
        if not f.endswith(".html") or f.endswith(".en.html"):
            continue
        slug = f[:-5]
        if only and slug not in only:
            continue
        yield slug, "zh", os.path.join(REPORTS, f)
        en = os.path.join(REPORTS, slug + ".en.html")
        if os.path.exists(en):
            yield slug, "en", en


def main():
    args = sys.argv[1:]
    force = "--force" in args
    only = {a for a in args if not a.startswith("--")}
    todo = []
    for slug, lang, src in jobs(only):
        dst = os.path.join(OUT, slug + (".en" if lang == "en" else "") + ".pdf")
        if force or not os.path.exists(dst):
            todo.append((slug, lang, src, dst))
    if not todo:
        print("报告 PDF 都已存在，跳过（--force 重出）")
        return
    from playwright.sync_api import sync_playwright
    os.makedirs(OUT, exist_ok=True)
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    with sync_playwright() as p:
        kw = {}
        if exe and os.path.isfile(exe):
            kw["executable_path"] = exe
        b = p.chromium.launch(**kw)
        pg = b.new_page(viewport={"width": 900, "height": 1200})
        for slug, lang, src, dst in todo:
            html = strip_webfonts(open(src, encoding="utf-8").read())
            # 报告自带的深色媒体查询不要抢；打印时保留底色
            html = html.replace("</head>", "<style>html{color-scheme:light}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}"
                                "@page{size:A4;margin:14mm 12mm 16mm}</style></head>", 1)
            pg.emulate_media(media="print", color_scheme="light")
            pg.set_content(html, wait_until="networkidle")
            foot = (f'<div style="width:100%;font-size:8px;color:#9a9186;padding:0 12mm;display:flex;justify-content:space-between;'
                    f'font-family:-apple-system,PingFang SC,Microsoft YaHei,sans-serif"><span>{FOOT[lang]}</span>'
                    f'<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
            pg.pdf(path=dst, format="A4", print_background=True, prefer_css_page_size=True, display_header_footer=True,
                   header_template="<span></span>", footer_template=foot)
            print(f"  {os.path.relpath(dst, ROOT)}  {os.path.getsize(dst) // 1024} KB")
        b.close()


if __name__ == "__main__":
    main()
