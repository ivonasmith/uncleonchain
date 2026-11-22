#!/usr/bin/env python3
"""IndexNow 推送（docs/SEO规范.md 基建 5）：把今天（UTC）正文有变化的页面推给 IndexNow（Bing / Yandex / Naver / Seznam 等共享）。
Google 不吃 IndexNow，靠 sitemap + Search Console。

只在 daily.yml 的定时运行里调一次（推送后网站已部署），失败不影响日更。
页面变化日读 site/seo_lastmod.json（出网站.py 写）；公钥文件 site/<key>.txt 由出网站.py 写。
"""
import os, re, sys, json, datetime as dt, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
HOST = "uncleonchain.com"


def main():
    src = open(os.path.join(ROOT, "pipeline", "出网站.py"), encoding="utf-8").read()
    key = re.search(r'^INDEXNOW_KEY = "([0-9a-f]{32})"', src, re.M).group(1)
    state = json.load(open(os.path.join(SITE, "seo_lastmod.json"), encoding="utf-8"))
    sm = open(os.path.join(SITE, "sitemap.xml"), encoding="utf-8").read()
    in_sitemap = set(re.findall(r"<loc>(https://[^<]+)</loc>", sm))
    day = sys.argv[1] if len(sys.argv) > 1 else dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    urls = []
    for k, v in state.items():
        if v.get("d") != day:
            continue
        lang, path = k[:2], k[2:]
        u = f"https://{HOST}{'/en' if lang == 'en' else ''}{path}"
        if u in in_sitemap:
            urls.append(u)
    if not urls:
        print("IndexNow：今天没有变化的页面")
        return
    if os.environ.get("INDEXNOW_DRY"):
        print(f"IndexNow（试跑，不推送）：{len(urls)} 个 URL，例：{urls[:3]}")
        return
    body = json.dumps({"host": HOST, "key": key, "keyLocation": f"https://{HOST}/{key}.txt", "urlList": urls[:10000]}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow：推送 {len(urls)} 个 URL → HTTP {r.status}")
    except Exception as e:  # noqa —— 失败不影响日更
        print(f"IndexNow 推送失败（{len(urls)} 个 URL）：{e}")


if __name__ == "__main__":
    main()
