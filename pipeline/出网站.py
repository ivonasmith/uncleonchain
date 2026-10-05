#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""链上大叔研究台 · 静态网站生成器（终端版，中英双语 + 深浅两套主题）

产品结构（左侧常驻导航，每个板块独立 URL，方便从推特直链到具体页面；英文版同结构挂在 /en/ 下）：
  /                 终端总览    综合研判 + 四张核心卡 + 四层信号灯 + 异动预警看台 + 发射台 / 板块 / 报告 / 日志快照
  /macro/           宏观仪表盘  四层框架；L1 按《L1 宏观层数据维度规格》：乐观度 · 信用 · 实际利率四态 · 情境格 · 闸门 · L1-B 加密资金通道（稳定币 / ETF / 升水 / 资金轮动矩阵）
                    /macro/<指标>/   每个指标的全历史走势、区间规则、各区间历史占比、正常波动范围（分位带）、当前分位
  /launchpad/       发射台矩阵  全网手续费汇总趋势（金额 / 份额堆叠）+ 当日变化拆解 + 跨链排行（带份额条）+ 多维过滤 + 一键长图
                    /launchpad/platforms/<slug>/  深度追踪平台分数据   /launchpad/report/  每日文字解读（出看板.py 原文）
  /rotation/  /narrative/  /reports/（分析报告：周度深度报告，content/reports/）  /journal/  /methodology/ /corrections/ /about/

读：build/网站素材.json（出看板.py）· data/宏观台账.json · data/板块台账.json · data/发射台矩阵.json
    data/解读日志/ · content/posts/<板块>/ · content/reports/ · content/journal/*.md（人工点评）
写：site/（中文）、site/en/（英文）、site/data/（走势图 JSON，两种语言共用）

视觉与前端脚本在 网站样式.py：深色是默认（终端风），太阳 / 月亮按钮切浅色，偏好记在浏览器里。
"""
import os, sys, re, json, glob, html, math, shutil, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 宏观规则 as R                                                     # noqa: E402
import 网站样式 as ST                                                    # noqa: E402

BUILD = os.path.abspath(os.environ.get("LP_OUT") or os.path.join(ROOT, "build"))
DATA = os.path.abspath(os.environ.get("LP_DATA") or os.path.join(ROOT, "data"))
SITE = os.path.abspath(os.environ.get("LP_SITE") or os.path.join(ROOT, "site"))
CONTENT = os.path.join(ROOT, "content", "posts")
REPORTS = os.path.join(ROOT, "content", "reports")
JCONTENT = os.path.join(ROOT, "content", "journal")
ASSETS = os.path.join(ROOT, "assets")

BRAND = "链上大叔研究台"
BRAND_EN = "Uncle Onchain"
DOMAIN = "uncleonchain.com"
TWITTER = "@Uncle_Onchain"
X_URL = "https://x.com/Uncle_Onchain"
SLOGAN = "宏观流动性 → 周期位置 → 筹码结构 → 情绪 → 发射台一级市场，每天一篇公开解读日志"
SLOGAN_EN = "Macro liquidity → cycle position → coin flows → sentiment → launchpads. One public, frozen research log every day."
DISCLAIMER = "本站只给数据和过程记录，不构成任何投资建议；不对任何交易结果负责。"
DISCLAIMER_EN = "Data and process notes only. Not investment advice."

LANG = {"v": "zh"}


def T(zh, en):
    return en if LANG["v"] == "en" else zh


def U(path):
    """站内链接按当前语言加前缀。"""
    return ("/en" + path) if LANG["v"] == "en" and path.startswith("/") else path


def LF(obj, k, default=""):
    """取字段的当前语言版本：英文站优先 k + 'EN'，没有就退回中文。"""
    if not obj:
        return default
    if LANG["v"] == "en" and obj.get(k + "EN"):
        return obj[k + "EN"]
    return obj.get(k, default)


PILLARS = [
    {"slug": "macro", "nav": "宏观仪表盘", "en": "Macro", "desc": "四层框架：宏观流动性 → 周期定位 → 筹码结构 → 情绪衍生品，每个指标的读数、历史区间和走势。",
     "descEN": "Four layers: macro liquidity → cycle → coin flows → sentiment. Every indicator with its reading, zones and full history."},
    {"slug": "rotation", "nav": "板块轮动", "en": "Rotation", "desc": "CoinGecko 类目逐日快照看资金在哪些赛道之间流动，加手写的轮动交易复盘。",
     "descEN": "Daily CoinGecko category snapshots showing where money rotates, plus hand-written rotation reviews."},
    {"slug": "narrative", "nav": "叙事埋伏", "en": "Narratives", "desc": "低位叙事币的观察笔记：为什么进、仓位怎么摆、后续怎么跟踪——过程记录，不是喊单。",
     "descEN": "Notes on early-stage narratives: why, how it is sized, how it is tracked — a process log, not calls."},
]

ICON = {
    "home": '<path d="M2.5 2.5h4.5v4.5H2.5zM9 2.5h4.5v4.5H9zM2.5 9h4.5v4.5H2.5zM9 9h4.5v4.5H9z"/>',
    "macro": '<path d="M1.5 10.5c1.6-3.2 3.2-3.2 4.8 0s3.2 3.2 4.8 0c.9-1.8 1.9-2.6 2.9-2.2M1.5 5.5c1.6-3.2 3.2-3.2 4.8 0s3.2 3.2 4.8 0"/>',
    "launchpad": '<path d="M3 14V8.5M8 14V2.5M13 14V6"/><path d="M1.5 14h13"/>',
    "rotation": '<path d="M13.2 6A5.5 5.5 0 0 0 3.1 5.4M2.8 10a5.5 5.5 0 0 0 10.1.6M13.4 2.6v3.5H9.9M2.6 13.4V9.9h3.5"/>',
    "narrative": '<circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="2.4"/><path d="M8 8l4.2-4.2"/>',
    "reports": '<path d="M3 1.8h7l3 3v9.4H3z"/><path d="M10 1.8v3h3M5.5 11.5V9.5M8 11.5V7.5M10.5 11.5V8.5"/>',
    "journal": '<path d="M3.5 1.8h9v12.4h-9z"/><path d="M6 5h4M6 8h4M6 11h2.5"/>',
    "methodology": '<path d="M2 12.5 12.5 2l1.5 1.5L3.5 14H2z"/><path d="M9.5 5l1.5 1.5M7.5 7l1 1M5.5 9l1.5 1.5"/>',
    "corrections": '<path d="M2.5 8.5l3.5 3.5 7.5-8"/>',
    "about": '<circle cx="8" cy="5.2" r="2.8"/><path d="M2.5 14c.9-2.9 2.9-4.2 5.5-4.2s4.6 1.3 5.5 4.2"/>',
}
NAV_MAIN = [("home", "/", "终端总览", "Overview"), ("macro", "/macro/", "宏观仪表盘", "Macro"),
            ("launchpad", "/launchpad/", "发射台矩阵", "Launchpads"), ("rotation", "/rotation/", "板块轮动", "Rotation"),
            ("narrative", "/narrative/", "叙事埋伏", "Narratives"), ("reports", "/reports/", "分析报告", "Reports"),
            ("journal", "/journal/", "解读日志", "Journal")]
NAV_MORE = [("methodology", "/methodology/", "口径与规则", "Methodology"), ("corrections", "/corrections/", "更正记录", "Corrections"),
            ("about", "/about/", "关于", "About")]

G = {"更新": None, "url": "/"}      # 侧边栏「数据更新」时间；当前页面路径（语言切换用）


def load(p, default=None):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def esc(s):
    return html.escape(str(s), quote=True)


def icon(k):
    return f'<svg viewBox="0 0 16 16" class="ic" aria-hidden="true">{ICON[k]}</svg>'


# ---------------------------------------------------------------- Markdown（够用就行；以 < 开头的整段原样 HTML 透传）
def md_inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", s)
    s = re.sub(r"`([^`]+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def md_to_html(src):
    lines, out, para, ul, quote, raw = src.split("\n"), [], [], [], [], []

    def fp():
        if para:
            out.append(f"<p>{md_inline(' '.join(para))}</p>"); para.clear()

    def fu():
        if ul:
            out.append("<ul>" + "".join(f"<li>{md_inline(x)}</li>" for x in ul) + "</ul>"); ul.clear()

    def fq():
        if quote:
            out.append(f"<blockquote>{md_inline(' '.join(quote))}</blockquote>"); quote.clear()

    in_raw = False
    for ln in lines:
        t = ln.strip()
        if in_raw:
            if not t:
                out.append("\n".join(raw)); raw.clear(); in_raw = False
            else:
                raw.append(ln)
            continue
        if not t:
            fp(); fu(); fq(); continue
        if t.startswith("<"):
            fp(); fu(); fq(); raw.append(ln); in_raw = True; continue
        m = re.match(r"^(#{1,3})\s+(.*)", t)
        if m:
            fp(); fu(); fq()
            n = len(m.group(1)) + 1
            out.append(f"<h{n}>{md_inline(m.group(2))}</h{n}>"); continue
        if t.startswith("- "):
            fp(); fq(); ul.append(t[2:]); continue
        if t.startswith(">"):
            fp(); fu(); quote.append(t.lstrip("> ")); continue
        fu(); fq(); para.append(t)
    fp(); fu(); fq()
    if raw:
        out.append("\n".join(raw))
    return "\n".join(out)


def split_front(raw):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if not m:
        return {}, raw
    meta = {}
    for ln in m.group(1).split("\n"):
        if ":" in ln:
            k, v = ln.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def slugify(path):
    return re.sub(r"[^a-z0-9\-]+", "-", os.path.splitext(os.path.basename(path))[0].lower()).strip("-")


def parse_post_md(path):
    meta, body = split_front(open(path, encoding="utf-8").read())
    if not meta:
        return None
    slug = slugify(path)
    meta.setdefault("标题", slug)
    meta.setdefault("日期", dt.date.today().isoformat())
    meta.setdefault("摘要", "")
    meta.update({"slug": slug, "kind": "md", "html": md_to_html(body.strip()), "css": ""})
    return meta


def html_meta(raw, path):
    meta = {}
    mm = re.search(r"<!--meta\s*\n(.*?)-->", raw, re.S)
    if mm:
        for ln in mm.group(1).split("\n"):
            if ":" in ln:
                k, v = ln.split(":", 1)
                meta[k.strip()] = v.strip()
    if "标题" not in meta:
        mt = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S)
        meta["标题"] = html.unescape(mt.group(1)).strip() if mt else os.path.basename(path)
    if "摘要" not in meta:
        md_ = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', raw)
        meta["摘要"] = html.unescape(md_.group(1)) if md_ else ""
    meta.setdefault("日期", dt.datetime.fromtimestamp(os.path.getmtime(path), dt.timezone.utc).date().isoformat())
    return meta


def parse_post_html(path):
    raw = open(path, encoding="utf-8").read()
    meta = html_meta(raw, path)
    m_body = re.search(r"<body[^>]*>(.*)</body>", raw, re.S)
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", raw, re.S))
    meta.update({"slug": slugify(path), "kind": "html", "html": m_body.group(1) if m_body else raw, "css": css})
    return meta


def load_posts(slug):
    d = os.path.join(CONTENT, slug)
    posts = []
    if os.path.isdir(d):
        for f in sorted(glob.glob(os.path.join(d, "*.md")) + glob.glob(os.path.join(d, "*.html"))):
            p = parse_post_html(f) if f.endswith(".html") else parse_post_md(f)
            if p:
                posts.append(p)
    posts.sort(key=lambda p: p["日期"], reverse=True)
    return posts


ALL_POSTS = {p["slug"]: load_posts(p["slug"]) for p in PILLARS}


def load_reports():
    """content/reports/ 下的分析报告：<slug>.html（整篇原样，英文版 <slug>.en.html）/ <slug>.md /
    <slug>/index.html（带图片等附件的文件夹，英文版 index.en.html）。"""
    out = []
    if not os.path.isdir(REPORTS):
        return out
    for f in sorted(os.listdir(REPORTS)):
        p = os.path.join(REPORTS, f)
        if f.startswith((".", "_")) or f.lower() == "readme.md" or f.endswith((".en.html", ".en.md")):
            continue
        en = None
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "index.html")):
            raw = open(os.path.join(p, "index.html"), encoding="utf-8").read()
            meta = html_meta(raw, os.path.join(p, "index.html"))
            meta.update({"slug": slugify(f), "kind": "dir", "src": p})
            en = os.path.join(p, "index.en.html")
        elif f.endswith(".html"):
            meta = html_meta(open(p, encoding="utf-8").read(), p)
            meta.update({"slug": slugify(f), "kind": "html", "src": p})
            en = p[:-5] + ".en.html"
        elif f.endswith(".md"):
            meta, body = split_front(open(p, encoding="utf-8").read())
            if not meta:
                continue
            meta.setdefault("标题", slugify(f))
            meta.setdefault("日期", dt.date.today().isoformat())
            meta.update({"slug": slugify(f), "kind": "md", "html": md_to_html(body.strip())})
        else:
            continue
        meta.setdefault("摘要", "")
        if en and os.path.exists(en):
            em = html_meta(open(en, encoding="utf-8").read(), en)
            meta["en_src"] = en
            meta.setdefault("标题EN", em.get("标题"))
            meta.setdefault("摘要EN", em.get("摘要"))
        meta["标签列表"] = [x.strip() for x in re.split(r"[,，、]", meta.get("标签") or "") if x.strip()]
        out.append(meta)
    out.sort(key=lambda p: p["日期"], reverse=True)
    return out


ALL_REPORTS = load_reports()


def commentary(key):
    """content/journal/<key>.md 的人工点评（可选；英文站优先读 <key>.en.md）。"""
    for name in ([f"{key}.en.md"] if LANG["v"] == "en" else []) + [f"{key}.md"]:
        p = os.path.join(JCONTENT, name)
        if os.path.exists(p):
            meta, body = split_front(open(p, encoding="utf-8").read())
            return md_to_html(body.strip())
    return ""


# ---------------------------------------------------------------- 外壳
def nav_html(active):
    def link(k, href, zh, en):
        return f'<a href="{U(href)}" class="{"on" if k == active else ""}">{icon(k)}{esc(T(zh, en))}</a>'
    main = "".join(link(*x) for x in NAV_MAIN)
    more = "".join(link(*x) for x in NAV_MORE)
    upd = G.get("更新") or "—"
    path = G["url"]
    zh_url, en_url = path, "/en" + path
    lang = (f'<span class="lang" role="tablist" aria-label="Language"><a href="{zh_url}" class="{"on" if LANG["v"] == "zh" else ""}" '
            f'hreflang="zh-CN" role="tab">中文</a><a href="{en_url}" class="{"on" if LANG["v"] == "en" else ""}" hreflang="en" role="tab">EN</a></span>')
    thm = ('<button class="thm" type="button" aria-label="' + T("切换浅色 / 深色", "Toggle light / dark") + '" title="'
           + T("切换浅色 / 深色", "Toggle light / dark") + '">'
           '<svg class="ic moon" viewBox="0 0 16 16"><path d="M13.5 9.6A5.8 5.8 0 0 1 6.4 2.5a5.8 5.8 0 1 0 7.1 7.1z"/></svg>'
           '<svg class="ic sun" viewBox="0 0 16 16"><circle cx="8" cy="8" r="3"/><path d="M8 1v1.6M8 13.4V15M1 8h1.6M13.4 8H15M3 3l1.1 1.1M11.9 11.9 13 13M3 13l1.1-1.1M11.9 4.1 13 3"/></svg></button>')
    return f"""<input type="checkbox" id="navtg" class="navtg">
<header class="topbar"><label for="navtg" aria-label="{T('菜单', 'Menu')}"><svg viewBox="0 0 16 16" class="ic"><path d="M2 4h12M2 8h12M2 12h12"/></svg></label>
<a class="home" href="{U('/')}"><img src="/assets/avatar-96.png" alt=""><span>{esc(T(BRAND, BRAND_EN))}</span></a><span class="sp"></span>{lang}{thm}</header>
<aside class="side">
<a class="brand" href="{U('/')}"><img class="av" src="/assets/avatar-96.png" alt="{T('链上大叔', 'Uncle Onchain')}"><span><b>{esc(T(BRAND, BRAND_EN))}</b><i>UNCLE ONCHAIN · TERMINAL</i></span></a>
<div class="tools">{lang}{thm}</div>
<nav class="snav"><div class="sgrp">Terminal</div>{main}<div class="sgrp">Records</div>{more}</nav>
<div class="sfoot"><div class="live"><i></i>{T('数据更新', 'Updated')} {esc(upd)} UTC</div>
<a href="{X_URL}" target="_blank" rel="noopener">𝕏 {esc(TWITTER)}</a><p>{esc(T(DISCLAIMER, DISCLAIMER_EN))}</p></div>
</aside><label for="navtg" class="scrim"></label>"""


def crumbs(items):
    """面包屑：[(文字, 链接), ..., (当前页, None)]。放在页面最上方，返回上级不用找。"""
    out = []
    for label, href in items:
        if href:
            out.append(f'<a href="{U(href)}">{esc(label)}</a>')
        else:
            out.append(f'<span class="cur" aria-current="page">{esc(label)}</span>')
    return '<nav class="crumbs" aria-label="breadcrumb">' + '<span class="sep">/</span>'.join(out) + "</nav>"


# 全站共用的样式和脚本写成独立文件（浏览器缓存，翻页不用重复下载），文件名带内容哈希，改了自动换新
import hashlib                                                           # noqa: E402

ASSET_SRC = {"site.css": ST.SITE_CSS, "ui.js": ST.UI_JS, "share.js": ST.SHARE_JS, "chart.js": ST.CHART_JS}
ASSET_URL = {k: f"/assets/{k}?v={hashlib.md5(v.encode('utf-8')).hexdigest()[:10]}" for k, v in ASSET_SRC.items()}

# Cloudflare Pages 缓存规则：样式脚本带版本号可以长缓存；走势数据一小时；页面本身每次都向服务器确认
HEADERS = """/assets/*
  Cache-Control: public, max-age=2592000
/data/*
  Cache-Control: public, max-age=3600
/*
  X-Content-Type-Options: nosniff
"""


def page(title, body, active="", desc="", extra_head="", narrow=False, share=False, scripts="", chart=False):
    d = esc(desc or T(SLOGAN, SLOGAN_EN))
    t = esc(title)
    path = G["url"]
    return f"""<!DOCTYPE html>
<html lang="{T('zh-CN', 'en')}" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{t}</title>
<script>{ST.HEAD_JS}</script>
<meta name="description" content="{d}">
<meta name="theme-color" content="#05070c">
<link rel="alternate" hreflang="zh-CN" href="https://{DOMAIN}{path}"><link rel="alternate" hreflang="en" href="https://{DOMAIN}/en{path}">
<meta property="og:title" content="{t}"><meta property="og:description" content="{d}">
<meta property="og:type" content="website"><meta property="og:site_name" content="{esc(T(BRAND, BRAND_EN))}">
<meta property="og:image" content="https://{DOMAIN}/assets/og.png">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:site" content="{TWITTER}">
<meta name="twitter:image" content="https://{DOMAIN}/assets/og.png">
<link rel="icon" href="/assets/favicon.ico" sizes="any"><link rel="icon" href="/assets/favicon-32.png" type="image/png" sizes="32x32">
<link rel="icon" href="/assets/favicon-192.png" type="image/png" sizes="192x192"><link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="stylesheet" href="{ASSET_URL["site.css"]}">
{extra_head}
</head>
<body>
{nav_html(active)}
<main class="main"><div class="mi{' narrow' if narrow else ''}">
{body}
</div>
<footer class="foot"><span>{esc(BRAND)}（{BRAND_EN}）</span><a href="{X_URL}">{esc(TWITTER)}</a>
<span>{T('数据', 'Data')}: DefiLlama · CoinMetrics · FRED · Farside · Yahoo · alternative.me · Hyperliquid · Deribit · CoinGecko · {T('链上节点', 'own nodes')}</span><span>{esc(T(DISCLAIMER, DISCLAIMER_EN))}</span></footer>
</main>
<script src="{ASSET_URL["ui.js"]}"></script>
{('<script src="' + ASSET_URL["share.js"] + '"></script>') if share else ''}
{('<script src="' + ASSET_URL["chart.js"] + '"></script>') if chart else ''}
{scripts}
</body>
</html>
"""


def write(rel, text):
    """rel 是中文站的相对路径；英文站自动写到 en/ 下。"""
    p = os.path.join(SITE, "en", rel) if LANG["v"] == "en" else os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


def emit(rel, title, body, **kw):
    """生成一页：rel = 'macro/index.html' 这种中文站相对路径。"""
    G["url"] = "/" + (rel[:-len("index.html")] if rel.endswith("index.html") else rel)
    write(rel, page(title, body, **kw))


def r6(v):
    if v is None or isinstance(v, int):
        return v
    if v == 0 or math.isnan(v) or math.isinf(v):
        return 0 if v == 0 else None
    return round(v, 5 - int(math.floor(math.log10(abs(v)))))


def write_data(rel, dates, series):
    """走势图数据：{"d": [日期...], "s": {key: [值...]}}，两种语言共用 /data/ 下同一份。"""
    p = os.path.join(SITE, "data", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    obj = {"d": dates, "s": {k: [r6(s.get(d)) for d in dates] for k, s in series.items()}}
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
    return "/data/" + rel


def chart_div(cfg, cls="", style=""):
    return f'<div class="{cls}" style="{style}" data-chart="{esc(json.dumps(cfg, ensure_ascii=False))}"></div>'


# ---------------------------------------------------------------- 格式与小图
f_usd = R.f_usd


def fmt_delta(v, pct_input=False):
    """v 为小数（0.05 = 5%）；pct_input=True 时 v 已是百分数。"""
    if v is None:
        return '<span class="d">—</span>'
    p = v if pct_input else v * 100
    cls = "up" if p > 0 else ("dn" if p < 0 else "")
    return f'<span class="d {cls}">{"▲" if p > 0 else ("▼" if p < 0 else "·")} {abs(p):.1f}%</span>'


def fmt_pct(v, dp=1):
    return "—" if v is None else f"{v*100:.{dp}f}%"


TONE_VAR = {"up": "--up", "dn": "--dn", "warn": "--warn", "cool": "--cool", "neutral": "--ink2"}


def spark(vals, tone="up", w=92, h=26, area=False):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return f'<svg class="spk" viewBox="0 0 {w} {h}"></svg>'
    var = TONE_VAR.get(tone, "--up")
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or (abs(hi) or 1)
    n = len(vals)
    pts = [(w * i / (n - 1), h - (v - lo) / rng * h * .84 - h * .08) for i, v in enumerate(vals)]
    p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    fill = ""
    if area:
        gid = f"g{abs(hash((tuple(vals[-5:]), var, n))) % 10**8}"
        fill = (f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var({var});stop-opacity:.22"/>'
                f'<stop offset="1" style="stop-color:var({var});stop-opacity:0"/></linearGradient></defs>'
                f'<polygon points="0,{h} {p} {w},{h}" fill="url(#{gid})"/>')
    return (f'<svg class="spk" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">{fill}'
            f'<polyline points="{p}" fill="none" style="stroke:var({var})" stroke-width="1.5" stroke-linejoin="round" '
            f'stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>')


CHAIN_KEY = {"Solana": "solana", "BSC": "bsc", "Base": "base", "Robinhood Chain": "robinhood", "Arc": "arc", "Monad": "monad",
             "Ethereum": "ethereum", "X Layer": "xlayer", "Arbitrum": "arbitrum", "Avalanche": "avax", "Polygon": "polygon",
             "Hyperliquid L1": "hyperliquid", "TON": "ton", "Sonic": "sonic", "MegaETH": "megaeth", "Stable": "stable",
             "Unichain": "unichain", "Blast": "blast", "Linea": "linea", "Plasma": "plasma", "Ink": "ink", "Tron": "tron",
             "Near": "near", "Aptos": "aptos", "Hedera": "hedera", "OP Mainnet": "optimism", "ZKsync Era": "era"}
KEY_CHAIN = {v: k for k, v in CHAIN_KEY.items()}
MAIN_CHAINS = ["solana", "bsc", "robinhood", "base", "arc", "monad"]


def chain_name(k):
    if k == "other":
        return T("其他", "Other")
    return KEY_CHAIN.get(k, k)


def chain_badge(name):
    k = CHAIN_KEY.get(name, "")
    cls = k if k in ("solana", "robinhood", "bsc", "base", "arc", "monad", "ethereum") else ("bsc" if "BSC" in (name or "") else "other")
    short = {"Robinhood Chain": "Robinhood", "BSC + X Layer + Monad + RH": T("BSC 系", "BSC+")}.get(name, name)
    return f'<span class="badge b-{cls}">{esc(short)}</span>'


def tone_chip(text, tone):
    return f'<span class="chip t-{tone}"><i></i>{esc(text)}</span>'


GRADE_CLS = {"已验证": "g-v", "已验证·方向": "g-d", "描述读数": "", "监控": "g-o", "观察项": "g-o"}
GRADE_EN = {"已验证": "Verified", "已验证·方向": "Verified · direction", "描述读数": "Descriptive", "监控": "Monitor", "观察项": "Watch only"}
LEVEL_EN = {"核心": "core", "辅助": "aux", "观察": "watch"}


def grade_chip(g):
    if not g:
        return ""
    return f'<span class="grade {GRADE_CLS.get(g, "")}">{esc(T(g, GRADE_EN.get(g, g)))}</span>'


def short_zone(z):
    return re.sub(r"（.*?）|\(.*?\)", "", z or "").strip()


# ---------------------------------------------------------------- 数据装载
def load_macro():
    L = load(os.path.join(DATA, "宏观台账.json"), {}) or {}
    return L, L.get("序列") or {}


def load_logs(kind):
    out = []
    for p in sorted(glob.glob(os.path.join(DATA, "解读日志", kind, "*.json"))):
        try:
            out.append(load(p))
        except Exception:  # noqa
            pass
    return out


def ind_href(key):
    return U(f"/macro/{key}/")


def stats_since(ind):
    """「正常波动范围」统计窗口：L1 宏观按研究的方法规则只用 2018 年以后；链上周期指标用全历史。"""
    return "2018-01-01" if ind["层"] == 1 else None


# ---------------------------------------------------------------- 首页组件
def hero_cards(S, as_of, sd):
    """首页四张核心卡：稳定币主线 / 发射台赛道 / 交易所筹码 / 情绪。"""
    cards = []
    j = R.judge(S, R.IND["stable_expay13"], as_of)
    b = R.judge(S, R.IND["stable_bullets13"], as_of)
    if j:
        sub = T(f'交易子弹 13 周 {b["显示"] if b else "—"} · {short_zone(j["区间"])}', f'Trading bullets 13w {b["显示"] if b else "—"} · {short_zone(j["区间EN"])}')
        cards.append((T("稳定币主线（去重）13 周", "Stablecoin main line 13w"), "L1-B", j["显示"], sub, j["tone"], j["走势"],
                      ind_href("stable_expay13")))
    else:
        cards.append((T("稳定币主线（去重）13 周", "Stablecoin main line 13w"), "L1-B", "—",
                      T("等待首次抓取", "Awaiting first fetch"), "neutral", [], ind_href("stable_expay13")))
    if sd:
        tot = sd.get("赛道Top60") or {}
        seq = tot.get("序列") or {}
        ds = sorted(seq)
        chg = (seq[ds[-1]] / seq[ds[-2]] - 1) if len(ds) >= 2 and seq[ds[-2]] else None
        cards.append((T("发射台赛道当日手续费", "Launchpad fees (day)"), "Top60", f_usd(tot.get("当日")),
                      f'{fmt_delta(chg)} {T("日环比", "DoD")} · {T("截至", "as of")} {sd["日期"]}', "up" if (chg or 0) >= 0 else "dn",
                      [seq[d] for d in ds[-30:]], U("/launchpad/")))
    f = R.reading(S, "ex_netflow", as_of, raw=True)
    if f:
        w = R.sum_window(S, "ex_netflow", f["截至"], 7)
        cards.append((T("交易所 BTC 净流量", "Exchange BTC net flow"), T("流入 − 流出", "in − out"), R.f_btc(f["值"], True),
                      T(f'7 日 {R.f_btc(w, True)} · {"净流出=提币" if (w or 0) < 0 else "净流入=潜在抛压"}',
                        f'7d {R.f_btc(w, True)} · {"outflow = withdrawals" if (w or 0) < 0 else "inflow = potential selling"}'),
                      "up" if (f["值"] or 0) < 0 else "dn", f["走势"][-30:], ind_href("ex_netflow")))
    else:
        cards.append((T("交易所 BTC 净流量", "Exchange BTC net flow"), T("流入 − 流出", "in − out"), "—", T("等待首次抓取", "Awaiting first fetch"),
                      "neutral", [], ind_href("ex_netflow")))
    g = R.judge(S, R.IND["fng"], as_of)
    if g:
        prev7 = R.reading(S, "fng", as_of)["前7"]
        cards.append((T("恐慌贪婪指数", "Fear & Greed"), "alternative.me", g["显示"],
                      f'{LF(g, "区间")} · {T("7 日前", "7d ago")} {prev7 if prev7 is not None else "—"}', g["tone"], g["走势"][-30:], ind_href("fng")))
    else:
        cards.append((T("恐慌贪婪指数", "Fear & Greed"), "alternative.me", "—", T("等待首次抓取", "Awaiting first fetch"), "neutral", [], ind_href("fng")))
    out = ""
    for k, tag, v, s, tone, sp, href in cards:
        out += (f'<a class="glass hero" href="{href}"><div class="k">{esc(k)}<span>{esc(tag)}</span></div>'
                f'<div class="v t-{tone}">{v}</div><div class="s">{s}</div>{spark(sp, tone, 200, 34, area=True)}</a>')
    return out, cards


def verdict_block(log, link=True):
    if not log:
        return ('<div class="glass verdict"><div class="body"><div class="lbl">' + T("综合研判", "Verdict") + '</div><div class="txt">'
                + T("今日解读日志还没生成——宏观数据等待首次抓取（每天 UTC 10:20 自动跑）。",
                    "Today's log has not been generated yet (runs daily at 10:20 UTC).") + '</div></div></div>')
    tags = "".join(tone_chip(f'{LF(lay, "名称")} · {LF(lay, "短")}', lay["tone"]) for lay in log["层"])
    more = f'<a class="btn ghost" href="{U("/journal/" + log["日期"] + "/")}">{T("看今日完整解读 →", "Full log →")}</a>' if link else ""
    patch = f'<span class="chip t-warn">{T("补录", "Re-run")}</span>' if log.get("补录") else ""
    l1 = LF(log, "L1行")
    l1h = f'<div class="l1line">{esc(l1)}</div>' if l1 else ""
    return (f'<div class="glass verdict"><div class="body"><div class="lbl">{T("综合研判", "Verdict")} · {log["日期"]} {T("解读日志", "log")} {patch}</div>'
            f'<div class="txt">{esc(LF(log["综合"], "一句话"))}</div><div class="chips">{tags}</div>{l1h}</div>{more}</div>')


def signal_tiles(log):
    if not log:
        return ""
    out = ""
    for lay in log["层"]:
        meta = R.LAYERS[lay["层"]]
        core = [y for y in lay["读数"] if y["级别"] == "核心"][:3]
        items = "".join(f'<li><span>{esc(LF(x, "名称"))}</span><b class="t-{x["tone"]}">{esc(x["显示"])} · {esc(short_zone(LF(x, "区间")))}</b></li>'
                        for x in core)
        out += (f'<a class="card sig t-{lay["tone"]}" href="{U("/macro/")}#layer-{lay["层"]}"><div class="n">LAYER {lay["层"]} · {esc(T(meta["频率"], meta["频率EN"]))}</div>'
                f'<div class="q">{esc(T(meta["名称"], meta["EN"]))}：{esc(T(meta["问"], meta["问EN"]))}？</div><div class="v t-{lay["tone"]}">{esc(LF(lay, "结论"))}</div>'
                f'<ul>{items or "<li><span>" + T("数据不足", "No data") + "</span></li>"}</ul></a>')
    return f'<div class="grid g4">{out}</div>'


def alert_board(log, title=None, share_id=None):
    title = title or T("异动预警看台", "Alert board")
    al = (log or {}).get("预警") or []
    ticker_items = []
    if log:
        for lay in log["层"]:
            for x in lay["读数"]:
                if x["级别"] == "核心":
                    ticker_items.append(f'<span>{esc(LF(x, "名称"))} <b class="t-{x["tone"]}">{esc(x["显示"])}</b> {esc(short_zone(LF(x, "区间")))}</span>')
        lp = log.get("发射台") or {}
        for t in (lp.get("Top") or [])[:5]:
            ticker_items.append(f'<span>{esc(t["名称"])} {T("当日手续费", "fees")} <b>{f_usd(t["当日"])}</b> '
                                f'{fmt_delta(t["日环比"], pct_input=True) if t.get("日环比") is not None else ""}</span>')
    track = "".join(ticker_items)
    ticker = f'<div class="ticker" aria-hidden="true"><div class="ticker-track">{track}{track}</div></div>' if track else ""
    lis = "".join(f'<li><span class="lv {"h" if a["级别"] == "高" else "m"}">{T(a["级别"], "High" if a["级别"] == "高" else "Med")}</span>'
                  f'{esc(LF(a, "文本"))}</li>' for a in al)
    body = f'<ul class="alerts">{lis}</ul>' if lis else ('<div class="quiet">' + T(
        "今天没有触发预警阈值（区间切换、L1 档位切换、交易所单日 ±5,000 BTC、资金费率翻转、VIX 穿越 20、发射台异动等）。",
        "No alert thresholds were hit today (zone changes, L1 regime change, ±5,000 BTC exchange day, funding flip, VIX crossing 20, launchpad moves).") + '</div>')
    btn = f'<button class="btn" onclick="{share_id}()">📸 {T("生成今日长图", "Share image")}</button>' if share_id else ""
    return (f'<div class="card board"><div class="board-hd"><span class="dot"></span><b>{esc(title)}</b>'
            f'<span class="stamp">{(log or {}).get("日期", "")}</span><span class="sp"></span>{btn}</div>{ticker}{body}</div>')


def share_payload_home(log, cards):
    """首页 / 日志页长图内容（纯字符串，交给 ucShare 渲染）。"""
    k = "".join(f'<div class="sc-kpi"><div class="k">{esc(c[0])}</div><div class="v t-{c[4]}">{c[2]}</div></div>' for c in cards)
    chips = "".join(f'<span class="chip t-{lay["tone"]}" style="margin:0 8px 8px 0">{esc(LF(lay, "名称"))} · {esc(LF(lay, "短"))}</span>'
                    for lay in (log or {}).get("层", []))
    al = "".join(f'<li>{"🔴" if a["级别"] == "高" else "🟠"} {esc(LF(a, "文本"))}</li>' for a in (log or {}).get("预警", [])[:7])
    return (f'<div class="sc-kpis">{k}</div><div style="margin-bottom:20px">{chips}</div>'
            + (f'<div class="sc-box"><ul class="sc-al">{al}</ul></div>' if al else ""))


# ---------------------------------------------------------------- 首页：终端总览
def build_home(sd, S, logs, weeks, months, rot, matrix):
    today_log = logs[-1] if logs else None
    as_of = today_log["日期"] if today_log else (G.get("今天") or dt.date.today().isoformat())
    heroes, cards = hero_cards(S, as_of, sd)
    lp_rows = ""
    if matrix:
        ps = sorted([p for p in matrix["协议"] if p.get("当日")], key=lambda p: -p["当日"])[:6]
        tot = sum(p.get("当日") or 0 for p in matrix["协议"]) or 1
        for i, p in enumerate(ps, 1):
            ch = "".join(chain_badge(c) for c in p["链"][:2])
            lp_rows += (f'<tr><td class="rk">{i}</td><td class="l"><span class="pname">{esc(p["名称"])}</span></td>'
                        f'<td class="l">{ch}</td><td>{f_usd(p["当日"])}</td><td>{p["当日"]/tot*100:.1f}%</td><td>{fmt_delta(p.get("日环比"), pct_input=True)}</td></tr>')
    lp_tbl = (f'<div class="tw"><table><thead><tr><th class="l">#</th><th class="l">{T("平台", "Platform")}</th><th class="l">{T("链", "Chain")}</th>'
              f'<th>{T("当日手续费", "Fees (day)")}</th><th>{T("份额", "Share")}</th><th>{T("日环比", "DoD")}</th></tr></thead><tbody>{lp_rows}</tbody></table></div>'
              ) if lp_rows else f'<div class="empty">{T("发射台数据待生成", "Launchpad data pending")}</div>'
    cats = ""
    if rot:
        last = rot[max(rot)]
        top = sorted(rot_clean(last)[0], key=lambda c: -c["24h"])[:6]
        for c in top:
            tone = "up" if c["24h"] >= 0 else "dn"
            cats += (f'<div class="card cat t-{tone}"><div class="nm">{esc(c["名称"])}</div>'
                     f'<div class="v t-{tone}">{c["24h"]:+.2f}%</div><div class="s">{T("市值", "Cap")} {f_usd(c["市值"])}</div></div>')
    cats = f'<div class="grid g3">{cats}</div>' if cats else f'<div class="empty">{T("板块快照待生成", "Snapshot pending")}</div>'
    items = ""
    for lg in reversed(logs[-6:]):
        n = len(lg.get("预警") or [])
        items += (f'<li><span class="d">{lg["日期"]}</span><span><a href="{U("/journal/" + lg["日期"] + "/")}">{T("每日解读", "Daily log")}</a>'
                  f'<span class="s">{esc(LF(lg["综合"], "一句话"))}</span></span><span class="x chip">{n} {T("条预警", "alerts")}</span></li>')
    for wk in reversed(weeks[-2:]):
        items += (f'<li><span class="d">{wk["标签"]}</span><span><a href="{U("/journal/week/" + wk["标签"] + "/")}">{T("周复盘", "Weekly review")}</a>'
                  f'<span class="s">{esc(LF(wk, "一句话"))}</span></span></li>')
    for mo in reversed(months[-1:]):
        items += (f'<li><span class="d">{mo["标签"]}</span><span><a href="{U("/journal/month/" + mo["标签"] + "/")}">{T("月复盘", "Monthly review")}</a>'
                  f'<span class="s">{esc(LF(mo, "一句话"))}</span></span></li>')
    jl = f'<div class="card"><ul class="list">{items}</ul></div>' if items else f'<div class="empty">{T("第一篇解读日志会在下一次每日运行时写入。", "The first log will be written on the next daily run.")}</div>'
    rp = ""
    for r in ALL_REPORTS[:3]:
        rp += (f'<a class="card rcard" href="{U("/reports/" + r["slug"] + "/")}"><span class="d">{esc(r["日期"])}</span><b>{esc(LF(r, "标题"))}</b>'
               f'<p>{esc(LF(r, "摘要"))}</p></a>')
    share_obj = {"title": T("今日链上终端 · 四层研判", "Onchain terminal · 4-layer read"), "date": as_of,
                 "sub": LF((today_log or {}).get("综合") or {}, "一句话"), "html": share_payload_home(today_log, cards),
                 "file": f"uncleonchain-terminal-{as_of}.png"}
    reports_block = ""
    if rp:
        reports_block = (f'<h2>{T("分析报告", "Research reports")} <a class="sub" href="{U("/reports/")}">{T("全部报告 →", "All reports →")}</a></h2>'
                         f'<div class="grid g3">{rp}</div>')
    body = f"""<div class="ph"><div><div class="eyebrow">Terminal Overview</div><h1>{T("终端总览", "Terminal overview")}</h1>
<p class="lede">{T("宏观流动性 → 周期位置 → 筹码结构 → 情绪，再落到发射台一级市场。每天 UTC 10:20 自动拉数、自动写解读日志，写入即冻结，公开可查。",
                   "Macro liquidity → cycle position → coin flows → sentiment, down to launchpads. Data is pulled and a rule-based log is written every day at 10:20 UTC — frozen once written, public forever.")}</p></div>
<div class="stamp">{T("解读日期", "Log date")} <b>{as_of}</b><br>{T("数据更新", "Data updated")} <b>{esc(G.get("更新") or "—")} UTC</b></div></div>
{verdict_block(today_log)}
<div class="grid g4">{heroes}</div>
<h2>{T("四层信号灯", "Four-layer signals")} <span class="sub">{T("点进去看每个指标的读数、区间和全历史走势", "Click through for every reading, its zones and full history")}</span></h2>
{signal_tiles(today_log) or '<div class="empty">' + T("宏观数据等待首次抓取。", "Macro data pending.") + '</div>'}
<h2>{T("异动预警", "Alerts")} <span class="sub">{T("阈值规则见「口径与规则」", "Thresholds in Methodology")}</span></h2>
{alert_board(today_log, share_id="shareHome")}
<div class="grid g2" style="margin-top:22px;align-items:start">
<div><h2 style="margin-top:12px">{T("发射台矩阵 · 当日 Top6", "Launchpads · top 6 today")} <a class="sub" href="{U("/launchpad/")}">{T("全部", "All")} {len((matrix or {}).get("协议", []))} {T("个协议 →", "protocols →")}</a></h2>{lp_tbl}</div>
<div><h2 style="margin-top:12px">{T("板块轮动 · 24h 领涨", "Rotation · 24h leaders")} <a class="sub" href="{U("/rotation/")}">{T("看全部 →", "See all →")}</a></h2>{cats}</div>
</div>
{reports_block}
<h2>{T("解读日志", "Journal")} <a class="sub" href="{U("/journal/")}">{T("全部日志与复盘 →", "All logs and reviews →")}</a></h2>
{jl}"""
    js = f"<script>function shareHome(){{ucShare({json.dumps(share_obj, ensure_ascii=False)})}}</script>"
    emit("index.html", T(f"{BRAND} · 链上数据情报终端", f"{BRAND_EN} · Onchain research terminal"), body, active="home", share=True, scripts=js,
         desc=LF((today_log or {}).get("综合") or {}, "一句话") or T(SLOGAN, SLOGAN_EN))


# ---------------------------------------------------------------- 宏观仪表盘
def ind_card(ind, j, as_of):
    name = T(ind["名称"], ind["EN"])
    lvl = T(ind["级别"], LEVEL_EN.get(ind["级别"], ind["级别"]))
    head = f'<div class="top"><span class="nm">{esc(name)}<span class="grade">{esc(lvl)}</span>{grade_chip(ind.get("等级"))}</span>'
    obs = " obs" if ind["级别"] == "观察" else ""
    if not j:
        return (f'<a class="card ind{obs}" href="{ind_href(ind["key"])}">{head}</div>'
                f'<div class="v t-neutral">—</div><div class="b">{T("等待数据源", "Awaiting source")}（{esc(ind["来源"])}）</div>'
                f'<div class="ft"><span>{esc(ind["来源"])}</span><span class="go">{T("看说明 →", "Details →")}</span></div></a>')
    stale = (f'<span class="stale">{T("滞后", "lag")} {R.days_between(j["截至"], as_of)} {T("天", "d")}</span>' if j["过期"]
             else f'{T("截至", "as of")} {j["截至"][5:]}')
    return (f'<a class="card ind{obs}" href="{ind_href(ind["key"])}">{head}'
            f'{tone_chip(short_zone(LF(j, "区间")), j["tone"])}</div><div class="v">{esc(j["显示"])}</div><div class="b">{esc(LF(j, "依据"))}</div>'
            f'{spark(j["走势"], j["tone"], 240, 32, area=True)}'
            f'<div class="ft"><span>{stale}</span><span class="go">{T("全部历史 →", "Full history →")}</span></div></a>')


def scenario_grid(v1):
    sc = (v1 or {}).get("情境") or {}
    a, b, w = sc.get("纳指口径"), sc.get("信用口径"), sc.get("较差")

    def cell(table, row, col):
        val = (R.SCENARIO_NDX if table == "n" else R.SCENARIO_CREDIT)[(row, col)]
        cur = a if table == "n" else b
        on = bool(cur and cur[0] == row and cur[1] == col)
        worst = on and bool(w and w[0] == row and w[1] == col and a and b and a != b)
        cls = "c" + (" on" if on else "") + (" worst" if worst else "")
        tone = "up" if val[0] > 0 else "dn"
        dw = T("两表取较差一格", "worse of the two")
        return (f'<div class="{cls}" data-w="{esc(dw)}"><b class="t-{tone}">{val[0]:+.1f}%</b>'
                f'<span>{T("收涨", "up")} {val[1]}%</span></div>')
    h = T("纳指口径", "Nasdaq lens")
    hc = T("信用口径", "Credit lens")
    return f"""<div class="scen-wrap"><div class="scen">
<div class="h">{T("实际利率 ↓ / 乐观度 →", "Real yield ↓ / optimism →")}</div><div class="h">{h} · {T("乐观强", "strong")}</div><div class="h">{h} · {T("乐观弱", "weak")}</div>
<div class="h">{hc} · {T("收窄", "narrowing")}</div><div class="h">{hc} · {T("走阔", "widening")}</div>
<div class="r">{T("急升（13 周 ≥ +0.40pp）", "Surging (13w ≥ +0.40pp)")}</div>{cell("n", "急升", "强")}{cell("n", "急升", "弱")}{cell("c", "急升", "收窄")}{cell("c", "急升", "走阔")}
<div class="r">{T("纳指口径 = 高位平台；信用口径 = 未急升", "Nasdaq: high plateau · Credit: not surging")}</div>{cell("n", "平台", "强")}{cell("n", "平台", "弱")}{cell("c", "未急升", "收窄")}{cell("c", "未急升", "走阔")}
</div></div>
<p class="tnote">{T("2022 年以来 BTC 同期 13 周收益中位数 / 收涨占比（周度，独立样本少）。只描述当下所处的格子，不预测未来 13 周；两张表落在不同格子时取较差的一格。绿框 = 当前所在格。",
                   "BTC same-period 13-week median return / share of up periods since 2022 (weekly, few independent samples). Describes the current cell only — no forecast. When the two lenses disagree, the worse cell counts. Highlighted = current cell.")}</p>"""


def rotation_matrix(rot):
    """资金轮动矩阵：ETF 13 周 × 交易子弹 13 周，四格。"""
    def usd(v):
        return R.f_signed_usd(v) if v is not None else "—"
    cells = ""
    for k in (("入", "增"), ("入", "减"), ("出", "增"), ("出", "减")):
        zh, en, tone = R.ROTATION[k]
        on = bool(rot and rot["格"] == k)
        cells += (f'<div class="c{" on" if on else ""}"><b class="t-{tone}" style="font-size:14px;font-family:var(--sans)">{esc(T(zh, en))}</b>'
                  + (f'<span>{T("← 当前所在格", "← current cell")}</span>' if on else "") + "</div>")
    now = ""
    if rot:
        now = T(f"当前：ETF 13 周 {usd(rot['ETF13'])}，交易子弹（剔除 Tron）13 周 {usd(rot['子弹13USD'])}（{rot['子弹13']:+.1f}%；含 Tron {usd(rot['含Tron13USD'])}），"
                f"两条通道合计约 {usd(rot['合计USD'])} → {rot['名称']}。",
                f"Now: ETF 13w {usd(rot['ETF13'])}, trading bullets (ex-Tron) 13w {usd(rot['子弹13USD'])} ({rot['子弹13']:+.1f}%; incl. Tron {usd(rot['含Tron13USD'])}), "
                f"about {usd(rot['合计USD'])} across both channels → {rot['名称EN']}.")
    return f"""<div class="grp">{T("L1-B 资金轮动矩阵 · ETF × 交易子弹", "L1-B rotation matrix · ETF × trading bullets")}</div>
<div class="scen-wrap"><div class="scen" style="grid-template-columns:170px repeat(2,minmax(0,1fr))">
<div class="h"></div><div class="h">{T("交易子弹 13 周增", "Trading bullets 13w up")}</div><div class="h">{T("交易子弹 13 周减", "Trading bullets 13w down")}</div>
<div class="r">{T("ETF 13 周净流入", "ETF 13w net inflow")}</div>{cells.split("</div>", 2)[0]}</div>{cells.split("</div>", 2)[1]}</div>
<div class="r">{T("ETF 13 周净流出", "ETF 13w net outflow")}</div>{"</div>".join(cells.split("</div>")[2:])}
</div></div>
<p class="tnote">{esc(now)} {T("ETF 流入、稳定币下降 = 资金从链上搬到 ETF，不是新钱进场；「存量换手」指资金通道从链上转到 ETF，不是换了一批人。",
                                "ETF inflows with falling stablecoins = money moving from on-chain to ETFs, not new money; 'switching channels' means the pipe changed, not the people.")}</p>"""


FAQ = [
    ("ETF 资金是散户还是机构？流入说明机构看多吗？", "Is ETF money retail or institutional? Do inflows mean institutions are bullish?",
     "从公开的机构季度持仓披露看，机构一直是少数，大部分是散户和小型投顾账户；还有一部分对冲基金在做基差套利（买入 ETF、同时做空期货赚价差），本身不看多也不看空。所以 ETF 流入不等于机构看多。",
     "Quarterly institutional filings show institutions are a minority; most holders are retail and small advisory accounts, plus hedge funds running basis trades (long ETF, short futures) with no directional view. Inflows do not mean institutions are bullish."),
    ("ETF 大幅流出是不是抄底信号？", "Are big ETF outflows a buy signal?",
     "不是。资金流出最多的那 20% 的周，之后 4 周 BTC 平均 −3.5%，全部样本平均 +1.9%，没有反弹规律；流入最多的周之后 4 周平均 +6.6%，方向是延续不是反转，但统计上不显著。日度资金流和过去 3 天涨跌相关 0.60，和之后 1~10 天只有约 0.05——它是滞后的顺势指标。",
     "No. Four weeks after the 20% of weeks with the largest outflows, BTC averaged −3.5% versus +1.9% for all weeks — no rebound pattern; after the largest inflows +6.6%, continuation rather than reversal, but not significant. Daily flows correlate 0.60 with the past 3 days of price and only ~0.05 with the next 1–10: a lagging trend indicator."),
    ("稳定币到底怎么算？", "How should stablecoins be counted?",
     "主线（去重）= 总供给 − 支付/机构类（PYUSD、RLUSD、USDG 等）− 生息/合成类（USDe、USDS、DAI 等，部分拿 USDT/USDC 抵押铸造，会重复计算）。交易子弹 = 交易核心（USDT、USDC、FDUSD、USD1、TUSD、USDD）− Tron 链，旁边并列含 Tron 口径。Tron 和支付机构单列：支付机构稳定币和 BTC 13 周相关 −0.43，不是交易资金。",
     "Main line (de-dup) = total − payment/institutional coins − yield/synthetic coins (partly minted against USDT/USDC). Trading bullets = trading core − Tron, with an incl.-Tron lens beside it. Tron and payment coins are shown separately; payment coins run −0.43 vs BTC over 13 weeks."),
    ("稳定币增长能提前反映资金进场吗？", "Does stablecoin growth lead money into crypto?",
     "不能。ETF 上线以来，稳定币增速和过去 13 周 BTC 涨跌相关 0.60、同期 0.52、未来 13 周 −0.26：是价格先涨，人们才去换稳定币进场。所以只当确认，不当埋伏信号。",
     "No. Since the ETFs, stablecoin growth correlates 0.60 with the past 13 weeks of BTC, 0.52 same-period and −0.26 with the next 13: price rises first, then people buy stablecoins. Confirmation only."),
    ("ETF 在流入、稳定币在下降，说明什么？", "ETF inflows while stablecoins fall — what does it mean?",
     "存量换手：链上的加密资金没有增加，买盘主要从 ETF 这条通道进来。换的是通道不是人群——钱从链上和交易所转到美股券商账户里的 ETF。2024 年以来 ETF 当周资金流和 BTC 当周涨跌相关 0.67，稳定币只有 0.3 左右，边际定价权在 ETF。换手行情里 ETF 一旦转为流出，没有原生资金托底，下跌会比上涨更快。",
     "Money switching channels: on-chain crypto money is not growing; buying comes through the ETF pipe. The pipe changed, not the people. Since 2024 weekly ETF flows correlate 0.67 with BTC versus ~0.3 for stablecoins — the marginal price is set in ETFs. If ETFs turn to outflows, there is no native money underneath, so declines run faster than rallies."),
    ("利率和「印钱」哪个更重要？", "Which matters more: interest rates or money printing?",
     "看「钱的价格」多于「钱的数量」。控制信用条件后，实际利率急升的系数仍为 −0.34（t −3.4）；美联储净流动性和 BTC 相关 0.28~0.32，而且 2024 年 5 月后领先性在变弱；M2 和 BTC 的涨跌幅相关只有 0.08（0.94 是两条都向上的假相关）。所以 L1 看利率和信用多于看印了多少钱，流动性只当打折条件。",
     "The price of money matters more than its quantity. Controlling for credit, a real-yield surge still carries a −0.34 coefficient (t −3.4); Fed net liquidity correlates 0.28–0.32 with BTC and its lead has weakened since May 2024; M2's return correlation is only 0.08 (the 0.94 is a spurious level correlation). Liquidity is only a discount condition."),
    ("加息就一定跌吗？", "Do rate hikes always mean BTC falls?",
     "看信用松不松。2022 年以来实际利率急升时：信用走阔，BTC 同期 13 周中位 −27%；信用收窄，中位只有 −3%；利率没急升、信用收窄，中位 +12.5%。这是同期描述，不预测未来 13 周。",
     "It depends on credit. Since 2022, during real-yield surges: with widening credit BTC's same-period 13-week median was −27%; with narrowing credit −3%; with no surge and narrowing credit +12.5%. Descriptive, not a forecast."),
    ("L1-B 是什么？", "What is L1-B?",
     "L1-B 加密资金通道：稳定币、现货 ETF、期货升水和资金轮动矩阵这一组。它们和价格互为因果、大多是滞后的，所以只用来确认 L1 的判断（同向 = 确认，背离 = 提示），不单独预测方向。",
     "L1-B crypto funding channels: stablecoins, spot ETFs, futures basis and the rotation matrix. They are mutually causal with price and mostly lagging, so they only confirm L1 (agreement = confirmation, divergence = warning) and never predict direction on their own."),
]


def l1_method_faq():
    pq = T("""<b>为什么 L1 看「利率和情绪」多于看「印了多少钱」</b>：实际利率是钱的价格，美联储净流动性是钱的数量。控制信用条件后，实际利率急升的系数仍为 −0.34（t −3.4）；
净流动性和 BTC 的相关只有 0.28~0.32，而且 2024 年 5 月后领先性在变弱；M2 和 BTC 的涨跌幅相关只有 0.08。所以流动性在 L1 里只当「打折条件」，方向信号来自乐观度和信用。""",
           """<b>Why L1 watches rates and sentiment more than money supply</b>: the real yield is the price of money, Fed net liquidity its quantity. Controlling for credit, a real-yield surge still carries −0.34 (t −3.4);
net liquidity correlates only 0.28–0.32 with BTC and its lead has weakened since May 2024; M2's return correlation is 0.08. Liquidity is therefore only a discount condition; the signal comes from optimism and credit.""")
    qa = "".join(f'<details class="card faq"><summary>{esc(T(q, qe))}</summary><p>{esc(T(a, ae))}</p></details>' for q, qe, a, ae in FAQ)
    return (f'<h3>{T("方法说明：价格 vs 数量", "Method note: price vs quantity")}</h3><div class="note">{pq}</div>'
            f'<h3>{T("常见问题", "FAQ")} <span style="font-weight:400;font-size:12px;color:var(--muted)">{T("数字出处：", "Sources: ")}<a href="{U("/reports/2026-10-04-macro-vs-bitcoin/")}">{T("《宏观到底管不管比特币？》", "the macro weekend report")}</a>{T("与 BTC 全周期宏观研究", " and the BTC full-cycle macro study")}</span></h3>'
            f'<div class="faqs">{qa}</div>')


def build_macro(L, S, logs):
    log = logs[-1] if logs else None
    as_of = log["日期"] if log else G.get("今天")
    st = L.get("源状态") or {}
    src = "".join(tone_chip(f'{k} {"✓" if v.get("ok") else "✗"} {(v.get("最新日期") or "")[5:]}', "up" if v.get("ok") else "dn")
                  for k, v in st.items())
    rs = [R.judge(S, ind, as_of) for ind in R.INDICATORS] if as_of else []
    rs = [x for x in rs if x]
    jby = {x["key"]: x for x in rs}
    v1 = R.layer_verdict(1, rs)
    sections = ""
    for i, meta in R.LAYERS.items():
        lay = R.layer_verdict(i, rs)
        inds = [x for x in R.INDICATORS if x["层"] == i]
        if i == 1:
            groups = []
            for ind in inds:
                if ind["组"] not in groups:
                    groups.append(ind["组"])
            cards = ""
            for g in groups:
                gi = [x for x in inds if x["组"] == g]
                cards += f'<div class="grp">{esc(T(g, gi[0]["组EN"]))}</div>'
                if g == R.G_SC[0]:
                    cards += (f'<p class="tnote" style="margin:-2px 0 10px">{T("价格先动、稳定币后增，只确认、不埋伏。", "Price moves first, stablecoins follow — confirm, never front-run.")}</p>')
                cards += '<div class="grid g4">' + "".join(ind_card(x, jby.get(x["key"]), as_of) for x in gi) + "</div>"
                if g == R.G_SC[0]:
                    cards += rotation_matrix(R.rotation(S, as_of) if as_of else None)
        else:
            cards = '<div class="grid g4">' + "".join(ind_card(x, jby.get(x["key"]), as_of) for x in inds) + "</div>"
        pend = "".join(f'<div class="pend"><b>{esc(T(p["名称"], p["EN"]))} · {T("待接入", "pending")}</b>{esc(T(p["原因"], p["原因EN"]))}</div>'
                       for p in R.PENDING if p["层"] == i)
        verdict = tone_chip(LF(lay, "结论"), lay["tone"])
        extra, chart = "", ""
        if i == 1:
            l1zh, l1en = R.l1_line(rs, v1)
            switch = T("切换到「逆风」的条件：BAA 利差或 NFCI 的 13 周变化转为收紧，或乐观度 z 跌破 0（纳指 13 周转负 / VIX>20），或净流动性 13 周 ≤ −2.72% 且美元 13 周走强。",
                       "Switch to headwind if: BAA or NFCI 13w change turns tighter, or optimism z drops below 0 (Nasdaq 13w negative / VIX>20), or net liquidity 13w ≤ −2.72% with a stronger dollar.")
            extra = (f'<div class="note">{esc(T(R.L1_POSITION, R.L1_POSITION_EN))}</div>'
                     f'<div class="card" style="padding:14px 18px;margin-bottom:12px"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">'
                     f'<b>{T("L1 档位", "L1 regime")}</b>{verdict}</div><div class="l1line">{esc(T(l1zh, l1en))}</div>'
                     f'<p class="tnote" style="margin-top:8px">{esc(switch)}</p></div>'
                     f'<h3>{T("情境格：实际利率状态 × 乐观度 / 信用条件", "Scenario grid: real-yield state × optimism / credit")}</h3>{scenario_grid(v1)}')
        if i == 2 and S.get("btc_price") and S.get("realized_price"):
            src_ = write_data("macro/btc-realized.json", sorted(set(S["btc_price"]) & set(S["realized_price"])),
                              {"p": S["btc_price"], "r": S["realized_price"]})
            chart = (f'<h3 style="margin-top:0">{T("BTC 价格 vs 全网持币成本（Realized Price）", "BTC price vs realized price")}</h3>' +
                     chart_div({"src": src_, "fmt": "price", "log": True, "ranges": ["1Y", "3Y", "5Y", "ALL"], "range": "ALL", "note": T("对数坐标：同样的高度代表同样的涨跌幅，比如 1 万→2 万和 5 万→10 万一样高。", "Log scale: equal heights mean equal percentage moves — 10k→20k is as tall as 50k→100k."),
                                "series": [{"k": "p", "n": T("BTC 价格", "BTC price"), "c": "s1"}, {"k": "r", "n": "Realized Price", "c": "s2"}]}))
        if i == 3 and S.get("ex_netflow"):
            cum = R.s_cum_netflow(S)
            src1 = write_data("macro/cum-netflow.json", sorted(cum), {"v": cum})
            src2 = write_data("macro/exbal-level.json", sorted(S.get("ex_balance") or {}), {"v": S.get("ex_balance") or {}})
            first = min(cum)
            chart = (f'<h3 style="margin-top:0">{T("交易所 BTC 累计净流量 · 全部历史（向下 = 筹码持续离开交易所）", "Cumulative exchange BTC net flow · full history (down = coins leaving)")}</h3>'
                     + chart_div({"src": src1, "fmt": "btcs", "ranges": ["1Y", "3Y", "5Y", "ALL"], "range": "ALL", "group": "l3", "zero": True,
                                  "series": [{"k": "v", "n": T("累计净流量", "Cumulative net flow"), "c": "s1", "area": True}],
                                  "note": T(f"从 {first} 起逐日累加流入 − 流出（CoinMetrics flash 口径）。", f"Inflow − outflow summed daily since {first}.")})
                     + f'<h3>{T("交易所 BTC 余额 · 全部历史", "Exchange BTC balance · full history")} <a class="sub" href="{ind_href("ex_balance")}">{T("看区间与分位 →", "Zones & percentiles →")}</a></h3>'
                     + chart_div({"src": src2, "fmt": "btc", "ranges": ["1Y", "3Y", "5Y", "ALL"], "range": "ALL", "group": "l3",
                                  "series": [{"k": "v", "n": T("交易所余额", "Exchange balance"), "c": "s3", "area": True}]}))
        if i == 4 and S.get("fng"):
            src_ = write_data("macro/fng-level.json", sorted(S["fng"]), {"v": S["fng"]})
            chart = (f'<h3 style="margin-top:0">{T("恐慌贪婪指数", "Fear & Greed index")}</h3>'
                     + chart_div({"src": src_, "fmt": "int", "ranges": ["1Y", "3Y", "ALL"], "range": "1Y",
                                  "lines": [{"v": 25, "label": T("恐慌", "fear"), "tone": "cool"}, {"v": 76, "label": T("贪婪", "greed"), "tone": "warn"}],
                                  "series": [{"k": "v", "n": "F&G", "c": "s1"}]}))
        if i == 1:
            chart = ""
            extra_after = l1_method_faq()
        else:
            extra_after = ""
        why = "；".join(LF(lay, "依据", []) or []) if i != 1 else ""
        sections += f"""<section class="layer" id="layer-{i}">
<div class="layer-hd"><span class="no">L{i}</span><h2>{esc(T(meta["名称"], meta["EN"]))} <span class="sub">{esc(T(meta["问"], meta["问EN"]))}？· {esc(T(meta["频率"], meta["频率EN"]))}</span></h2>{verdict if i != 1 else ''}
<div class="why">{esc(why)}</div></div>
{extra}
{cards}
{f'<div class="grid g4" style="margin-top:12px">{pend}</div>' if pend else ''}
{f'<div class="card" style="padding:14px 18px;margin-top:12px">{chart}</div>' if chart else ''}
{extra_after}
</section>"""
    posts = ALL_POSTS["macro"]
    plist = "".join(f'<li><span class="d">{esc(x["日期"])}</span><span><a href="{U("/macro/" + x["slug"] + "/")}">{esc(x["标题"])}</a>'
                    f'<span class="s">{esc(x["摘要"])}</span></span></li>' for x in posts)
    body = f"""<div class="ph"><div><div class="eyebrow">Macro · 4-Layer Framework</div><h1>{T("宏观四层仪表盘", "Four-layer macro dashboard")}</h1>
<p class="lede">{T("先看宏观环境给多少风险预算（L1），再看贵不贵（L2 周期），再看筹码在谁手里（L3 交易所进出），最后看情绪会不会超调（L4）。每张卡都能点开，看这个数字的全部历史、区间规则、每个区间历史上出现的频率和「正常波动范围」。拿不到真实数据的指标标「待接入」，不拿近似值冒充。",
                   "First how much risk budget the macro backdrop allows (L1), then whether it is cheap (L2 cycle), who holds the coins (L3 exchange flows), and whether sentiment is overshooting (L4). Every card opens the full history, the zone rules, how often each zone occurred and the normal range. Anything without real data is marked pending.")}</p></div>
<div class="stamp">{T("解读日期", "Log date")} <b>{as_of or "—"}</b><br>{T("台账更新", "Ledger updated")} <b>{esc(L.get("更新时间UTC") or "—")} UTC</b></div></div>
{verdict_block(log)}
<div class="src">{src}</div>
{sections}
<h2>{T("宏观深度分析", "Macro deep dives")}</h2>
{f'<div class="card"><ul class="list">{plist}</ul></div>' if plist else '<div class="empty">' + T("手写的宏观深度分析会发在这里；系统性的研究报告见「分析报告」。", "Hand-written macro notes go here; full research is under Reports.") + '</div>'}"""
    emit("macro/index.html", T(f"宏观四层仪表盘 · {BRAND}", f"Macro dashboard · {BRAND_EN}"), body, active="macro", chart=True,
         desc=LF((log or {}).get("综合") or {}, "一句话") or T(PILLARS[0]["desc"], PILLARS[0]["descEN"]))


def write_indicator_data(S):
    """每个指标的判定序列 / 原始水平 / BTC 价格写成 JSON（两种语言共用，只写一次）。"""
    out = {}
    btc = S.get("btc_price") or {}
    if btc:
        write_data("macro/btc.json", sorted(btc), {"v": btc})
    for ind in R.INDICATORS:
        s = R.series_of(S, ind)
        info = {"main": write_data(f"macro/{ind['key']}.json", sorted(s), {"v": s}) if s else None}
        rk = ind.get("raw")
        if rk:
            rs = R.RAW_DERIVED[rk](S) if rk in R.RAW_DERIVED else (S.get(rk) or {})
            if ind["key"] == "ex_netflow":
                rs = R.s_cum_netflow(S)
            if rs:
                info["raw"] = write_data(f"macro/{ind['key']}-raw.json", sorted(rs), {"v": rs})
        out[ind["key"]] = info
    return out


RAW_TITLE = {
    "ndx13": ("纳指 100 指数（对数坐标）", "Nasdaq-100 index (log)"), "baa13": ("BAA 信用利差水平", "BAA spread level"),
    "nfci13": ("NFCI 水平（0 以下 = 比平均宽松）", "NFCI level (below 0 = looser than average)"), "hy13": ("高收益利差水平", "High-yield spread level"),
    "real13": ("10 年实际利率水平", "10y real yield level"), "netliq13": ("美联储净流动性水平", "Fed net liquidity level"),
    "usd13": ("广义美元指数", "Broad dollar index"), "stable_expay13": ("稳定币主线规模", "Ex-payment stablecoin supply"),
    "stable_bullets13": ("交易子弹规模", "Trading-bullet supply"), "stable_yield13": ("生息 / 合成稳定币规模", "Yield / synthetic supply"),
    "etf28": ("ETF 逐日净流入", "ETF daily net flows"), "realized_price": ("Realized Price（全网持币成本）", "Realized price"),
    "ex_netflow": ("交易所 BTC 累计净流量（全部历史）", "Cumulative exchange BTC net flow (full history)"),
    "ex_balance": ("交易所 BTC 余额（全部历史）", "Exchange BTC balance (full history)"), "hl_oi": ("BTC 未平仓合约（美元）", "BTC open interest (USD)"),
}
OWN_PCT = ("cme_basis", "deribit_basis")


def zone_table(ind, j, stt):
    fmt = R.FMT[ind["fmt"]]
    cuts = ind["cuts"]
    if ind["key"] in OWN_PCT:
        return ('<div class="tw"><table><tbody><tr><td class="l wrap">'
                + T("只看自身历史分位：< 20 分位 = 自身历史低位，20–80 = 中段，> 80 = 自身历史高位；样本满 90 天才给判定。",
                    "Own-history percentile only: <20 low, 20–80 mid, >80 high; judged after 90 observations.") + "</td></tr></tbody></table></div>")
    if len(cuts) == 1:
        return ""
    share = {z[0]: z[3] for z in (stt or {}).get("区间占比", [])}
    rows, prev_ub = "", None
    jz = short_zone(j["区间"]) if j else None
    for c in cuts:
        ub = c[0]
        rng = (f"< {fmt(ub)}" if prev_ub is None else (f"{fmt(prev_ub)} ~ {fmt(ub)}" if ub is not None else f"≥ {fmt(prev_ub)}"))
        prev_ub = ub if ub is not None else prev_ub
        pc = share.get(c[1])
        zc = short_zone(c[1])
        cur = bool(jz and (jz == zc or jz.startswith(zc) or (ind["key"] == "real13" and zc == "平台" and "平台" in jz)))
        bar = (f'<span class="zbar" style="width:{max(2, pc * 1.4):.0f}px;background:var({TONE_VAR[c[3]]})"></span>{pc:.1f}%' if pc is not None else "—")
        rows += (f'<tr class="{"cur" if cur else ""}"><td class="l">{tone_chip(T(c[1], c[2]), c[3])}{" ◀ " + T("当前", "now") if cur else ""}</td>'
                 f'<td>{esc(rng)}</td><td class="l" style="min-width:180px">{bar}</td></tr>')
    if ind["key"] == "real13":
        rows += (f'<tr><td class="l wrap" colspan="3" style="color:var(--ink2)">'
                 + T("「平台」再按水平分：≥ 1.0% = 高位平台，< 1.0% = 低位平台。", "'Plateau' splits by level: ≥1.0% high, <1.0% low.") + "</td></tr>")
    return (f'<div class="tw"><table><thead><tr><th class="l">{T("区间", "Zone")}</th><th>{T("规则（判定序列）", "Rule")}</th>'
            f'<th class="l">{T("历史上落在这个区间的时间占比", "Share of history in this zone")}</th></tr></thead><tbody>{rows}</tbody></table></div>')


def range_block(S, ind, j, stt, since):
    if not stt:
        return ""
    fmt = R.FMT[ind["fmt"]]
    s = {d: v for d, v in R.series_of(S, ind).items() if since is None or d >= since}
    cur_p = R.pct_rank(s, j["值"]) if j else None
    lo, hi = stt["p05"], stt["p95"]
    span_ = (hi - lo) or 1

    def pos(v):
        return max(0, min(100, (v - lo) / span_ * 100))
    gauge = ""
    if j:
        gauge = (f'<div class="gauge" aria-hidden="true"><div class="trk"></div><div class="p90" style="left:{pos(stt["p10"]):.1f}%;width:{pos(stt["p90"]) - pos(stt["p10"]):.1f}%"></div>'
                 f'<div class="iqr" style="left:{pos(stt["p25"]):.1f}%;width:{pos(stt["p75"]) - pos(stt["p25"]):.1f}%"></div>'
                 f'<div class="now" style="left:{pos(j["值"]):.1f}%"></div></div>'
                 f'<div class="gauge-lbl"><span>p5 {esc(fmt(lo))}</span><span>{T("中位", "median")} {esc(fmt(stt["p50"]))}</span><span>p95 {esc(fmt(hi))}</span></div>')
    wk = ind.get("freq") == "w"
    win = T(f"{stt['起']} ~ {stt['止']}，{stt['样本']} 个{'周' if wk else '日'}度样本",
            f"{stt['起']} – {stt['止']}, {stt['样本']} {'weekly' if wk else 'daily'} observations")
    return f"""<div class="stats">
<div><div class="k">{T("当前读数", "Current")}</div><div class="v">{esc(j["显示"]) if j else "—"}</div><div class="s">{T("历史第", "Percentile")} {f"{cur_p:.0f}" if cur_p is not None else "—"}{T(" 百分位", "")}</div></div>
<div><div class="k">{T("正常波动范围（p10–p90）", "Normal range (p10–p90)")}</div><div class="v">{esc(fmt(stt["p10"]))} ~ {esc(fmt(stt["p90"]))}</div><div class="s">{T("历史上 80% 的时间在这里", "80% of history")}</div></div>
<div><div class="k">{T("常见区间（p25–p75）", "Typical (p25–p75)")}</div><div class="v">{esc(fmt(stt["p25"]))} ~ {esc(fmt(stt["p75"]))}</div><div class="s">{T("中位", "median")} {esc(fmt(stt["p50"]))}</div></div>
<div><div class="k">{T("历史极值", "Extremes")}</div><div class="v">{esc(fmt(stt["min"]))} ~ {esc(fmt(stt["max"]))}</div><div class="s">{esc(win)}</div></div>
</div>{gauge}
<p class="tnote">{T("统计窗口：", "Window: ")}{esc(win)}{T("。L1 宏观指标按研究的方法规则只用 2018 年以后的数据（2010–2017 宏观对 BTC 没有解释力），链上周期指标用全历史。分位只描述读数在自己历史里的位置，不是买卖信号。",
                                                ". L1 macro gauges use post-2018 data only (macro had no explanatory power over BTC in 2010–2017); on-chain cycle gauges use full history. Percentiles describe position in history — not trade signals.")}</p>"""


def build_indicator_pages(L, S, logs, files):
    log = logs[-1] if logs else None
    as_of = log["日期"] if log else G.get("今天")
    for ind in R.INDICATORS:
        key, meta = ind["key"], R.LAYERS[ind["层"]]
        name = T(ind["名称"], ind["EN"])
        j = R.judge(S, ind, as_of) if as_of else None
        since = stats_since(ind)
        stt = R.history_stats(S, ind, since) or R.history_stats(S, ind)
        if stt and since and stt["起"] < since:
            since = None
        f = files.get(key) or {}
        cuts = ind["cuts"]
        lines = []
        if key not in OWN_PCT:
            for n, c in enumerate(cuts):
                if c[0] is not None:
                    nxt = cuts[n + 1]
                    lines.append({"v": c[0], "label": "↑ " + short_zone(T(nxt[1], nxt[2]))[:9], "tone": nxt[3]})
        zone = [] if key in OWN_PCT or len(cuts) == 1 else [{"ub": c[0], "n": T(c[1], c[2]), "t": c[3]} for c in cuts]
        rngs = ["1Y", "3Y", "5Y", "ALL"]
        charts = ""
        if f.get("main"):
            cfg = {"src": f["main"], "fmt": ind["fmt"], "ranges": rngs, "range": "ALL", "group": "d", "lines": lines, "zone": zone,
                   "zero": ind["fmt"] in ("pcts", "pp", "xs", "btcs", "usds"),
                   "series": [{"k": "v", "n": name, "c": "s1", "area": ind["fmt"] in ("btcs", "usds")}]}
            if stt:
                cfg["band"] = {k: stt[k] for k in ("p10", "p25", "p50", "p75", "p90")}
            charts += (f'<h2>{T("判定序列 · 全部历史", "Judged series · full history")} <span class="sub">{esc(T(ind["依据"], ind["依据EN"]))} · '
                       f'{T("虚线 = 区间分界；蓝色带 = 正常波动范围（浅 p10–p90，深 p25–p75）", "dashed = zone boundaries; blue band = normal range (light p10–p90, dark p25–p75)")}</span></h2>'
                       f'<div class="card" style="padding:14px 18px">{chart_div(cfg)}</div>')
        if f.get("raw"):
            rt = RAW_TITLE.get(key, (ind["名称"], ind["EN"]))
            rawfmt = "btcs" if key == "ex_netflow" else ind.get("rawfmt", "x")
            cfg = {"src": f["raw"], "fmt": rawfmt, "ranges": rngs, "range": "ALL", "group": "d", "log": key in ("ndx13", "realized_price"),
                   "note": T("对数坐标：同样的高度代表同样的涨跌幅，比如 1 万→2 万和 5 万→10 万一样高。", "Log scale: equal heights mean equal percentage moves — 10k→20k is as tall as 50k→100k.") if key in ("ndx13", "realized_price") else "",
                   "zero": rawfmt in ("btcs", "usds"), "series": [{"k": "v", "n": T(rt[0], rt[1]), "c": "s3", "area": rawfmt == "btcs"}]}
            if key == "real13":
                cfg["lines"] = [{"v": 1.0, "label": T("1.0% 高位线", "1.0% line"), "tone": "warn"}]
            charts += f'<h2>{esc(T(rt[0], rt[1]))}</h2><div class="card" style="padding:14px 18px">{chart_div(cfg)}</div>'
        if S.get("btc_price") and key != "realized_price":
            charts += (f'<h2>{T("对照：BTC 价格（对数坐标，按涨跌幅比例显示）", "For reference: BTC price (log scale, proportional to % moves)")} <span class="sub">{T("同一时间轴，悬停联动", "same time axis, linked hover")}</span></h2>'
                       f'<div class="card" style="padding:14px 18px">{chart_div({"src": "/data/macro/btc.json", "fmt": "price", "log": True, "ranges": rngs, "range": "ALL", "group": "d", "note": T("对数坐标：同样的高度代表同样的涨跌幅，比如 1 万→2 万和 5 万→10 万一样高。", "Log scale: equal heights mean equal percentage moves — 10k→20k is as tall as 50k→100k."), "series": [{"k": "v", "n": "BTC", "c": "s2"}]})}</div>')
        if not f.get("main"):
            charts = (f'<div class="empty" style="margin-top:20px">{T("这个指标还没有数据（数据源接通后的下一次每日运行会生成）。", "No data yet for this indicator; it appears after the next daily run.")}</div>'
                      + charts)
        head = ""
        if j:
            head = (f'<div class="glass verdict"><div class="body"><div class="lbl">{T("当前读数", "Current reading")} · {T("截至", "as of")} {j["截至"]}'
                    f'{" · " + T("数据滞后", "stale") if j["过期"] else ""}</div><div class="txt" style="font-family:var(--mono);font-size:26px">{esc(j["显示"])}</div>'
                    f'<div class="chips">{tone_chip(LF(j, "区间"), j["tone"])}<span class="chip">{esc(LF(j, "依据"))}</span></div></div></div>')
        zt = zone_table(ind, j, stt)
        rb = range_block(S, ind, j, stt, since)
        body = f"""{crumbs([(T("宏观仪表盘", "Macro"), "/macro/"), (f'L{ind["层"]} · {T(meta["名称"], meta["EN"])}', f'/macro/#layer-{ind["层"]}'), (name, None)])}
<div class="ph"><div><div class="eyebrow">L{ind["层"]} · {esc(T(ind.get("组") or meta["名称"], ind.get("组EN") or meta["EN"]))}</div>
<h1>{esc(name)}</h1><p class="lede">{esc(T(ind["说明"], ind["说明EN"]))}</p>
<div class="chips" style="margin-top:10px"><span class="chip">{T("来源", "Source")}：{esc(ind["来源"])}</span><span class="chip">{T("级别", "Level")}：{esc(T(ind["级别"], LEVEL_EN.get(ind["级别"], "")))}</span>{grade_chip(ind.get("等级"))}</div></div></div>
{head}
<h2>{T("这个数字落在哪：区间规则与历史占比", "Zones: rules and how often each occurred")}</h2>{zt or '<div class="empty">' + T("只看趋势，没有区间判定。", "Trend only, no zones.") + '</div>'}
<h2>{T("正常波动范围", "Normal range")}</h2>{rb or '<div class="empty">' + T("样本还不够，满 10 个数据点后给出。", "Not enough data yet.") + '</div>'}
{charts}
<p class="tnote" style="margin-top:20px">{T("区间规则和证据等级的出处见", "Rules and evidence grades: ")}<a href="{U("/methodology/")}">{T("口径与规则", "Methodology")}</a>{T("；规则改动记在", "; rule changes are logged in ")}<a href="{U("/corrections/")}">{T("更正记录", "Corrections")}</a>{T("。", ".")}</p>"""
        emit(f"macro/{key}/index.html", f"{name} · {T('宏观仪表盘', 'Macro')} · {T(BRAND, BRAND_EN)}", body, active="macro", chart=True,
             desc=T(ind["说明"], ind["说明EN"]))


# ---------------------------------------------------------------- 发射台矩阵
def launchpad_history(matrix):
    """全网手续费汇总：Top8（近 90 天合计排序，颜色按实体固定）+ 其他。返回 (数据路径, 拆解表数据)。"""
    hist = matrix.get("历史") or {}
    ds = sorted(d for d in hist if hist[d])
    if len(ds) < 2:
        return None, None
    names = {p["slug"]: p["名称"] for p in matrix["协议"]}
    agg = {}
    for d in ds[-90:]:
        for s, v in hist[d].items():
            agg[s] = agg.get(s, 0) + (v or 0)
    top = [s for s, _ in sorted(agg.items(), key=lambda x: -x[1])[:8]]
    series = {s: {} for s in top}
    series["_other"], tot = {}, {}
    for d in ds:
        row = hist[d]
        t = sum(v or 0 for v in row.values())
        tot[d] = t
        for s in top:
            series[s][d] = row.get(s, 0) or 0
        series["_other"][d] = t - sum(row.get(s, 0) or 0 for s in top)
    path = write_data("launchpad/total.json", ds, series)
    cfg_series = [{"k": s, "n": names.get(s, s), "c": f"s{k + 1}"} for k, s in enumerate(top)] + [{"k": "_other", "n": T("其他", "Other"), "c": "s9"}]
    d1, d0 = ds[-1], ds[-2]
    t1, t0 = tot[d1], tot[d0]
    rows = []
    for k, s in enumerate(top + ["_other"]):
        a, b = series[s][d1], series[s][d0]
        rows.append({"名称": names.get(s, s) if s != "_other" else T("其他", "Other"), "c": f"s{k + 1}" if s != "_other" else "s9",
                     "今": a, "昨": b, "变": a - b, "份额今": a / t1 * 100 if t1 else None, "份额昨": b / t0 * 100 if t0 else None})
    return path, {"cfg": cfg_series, "d1": d1, "d0": d0, "t1": t1, "t0": t0, "rows": rows, "起": ds[0], "天数": len(ds)}


def breakdown_html(bk):
    if not bk:
        return ""
    t1, t0 = bk["t1"], bk["t0"]
    dt_ = t1 - t0
    trs = ""
    for r in sorted(bk["rows"], key=lambda r: (r["c"] == "s9", -r["今"])):          # 「其他」固定放最后
        dsh = (r["份额今"] - r["份额昨"]) if r["份额今"] is not None and r["份额昨"] is not None else None
        trs += (f'<tr><td class="l"><span class="pname"><i style="width:10px;height:10px;border-radius:2px;background:var(--{r["c"]});display:inline-block"></i>{esc(r["名称"])}</span></td>'
                f'<td>{f_usd(r["今"])}</td><td>{f_usd(r["昨"])}</td><td class="{"t-up" if r["变"] > 0 else "t-dn" if r["变"] < 0 else ""}">{R.f_signed_usd(r["变"])}</td>'
                f'<td>{R.f_pct(r["份额今"], 1)}</td><td class="{"t-up" if (dsh or 0) > 0 else "t-dn" if (dsh or 0) < 0 else ""}">{"—" if dsh is None else f"{dsh:+.1f}pp"}</td></tr>')
    up = sorted([r for r in bk["rows"] if r["变"] > 0], key=lambda r: -r["变"])[:2]
    dn = sorted([r for r in bk["rows"] if r["变"] < 0], key=lambda r: r["变"])[:2]
    chg = (t1 / t0 - 1) * 100 if t0 else 0
    if LANG["v"] == "zh":
        s = f"全网 {f_usd(t0)} → {f_usd(t1)}（{chg:+.1f}%）。"
        if up:
            s += "增量主要来自 " + "、".join(f"{r['名称']}（{R.f_signed_usd(r['变'])}）" for r in up) + "；"
        if dn:
            s += "减少主要在 " + "、".join(f"{r['名称']}（{R.f_signed_usd(r['变'])}）" for r in dn) + "。"
        if abs(chg) < 5 and up and dn:
            s += "总量变化不大但内部此消彼长——是资金在平台之间换手，不是整个赛道变冷或变热。"
    else:
        s = f"Total {f_usd(t0)} → {f_usd(t1)} ({chg:+.1f}%). "
        if up:
            s += "Gains led by " + ", ".join(f"{r['名称']} ({R.f_signed_usd(r['变'])})" for r in up) + ". "
        if dn:
            s += "Declines led by " + ", ".join(f"{r['名称']} ({R.f_signed_usd(r['变'])})" for r in dn) + ". "
        if abs(chg) < 5 and up and dn:
            s += "The total barely moved while platforms swapped share — rotation between venues, not a hotter or colder sector."
    return (f'<p class="tnote" style="font-size:13px;color:var(--ink2)">{esc(s)}</p>'
            f'<div class="tw"><table><thead><tr><th class="l">{T("平台", "Platform")}</th><th>{bk["d1"]}</th><th>{bk["d0"]}</th><th>{T("变化", "Change")}</th>'
            f'<th>{T("份额", "Share")}</th><th>{T("份额变化", "Share Δ")}</th></tr></thead><tbody>{trs}'
            f'<tr><td class="l"><b>{T("全网合计", "Total")}</b></td><td><b>{f_usd(t1)}</b></td><td>{f_usd(t0)}</td><td>{R.f_signed_usd(dt_)}</td><td>100%</td><td></td></tr></tbody></table></div>')


MATRIX_JS = r"""<script>
(function(){
const tb=document.querySelector('#mx tbody'),rows=[...tb.rows],st={chain:'all',p:'d7',tier:'all'};
const pd={d1:1,d7:7,d30:30};
function fmt(v){const a=Math.abs(v);return a>=1e9?'$'+(v/1e9).toFixed(2)+'B':a>=1e6?'$'+(v/1e6).toFixed(2)+'M':a>=1e3?'$'+(v/1e3).toFixed(1)+'K':'$'+Math.round(v).toLocaleString()}
const MAIN=%MAIN%;
function val(r,p){const d=r.dataset,c=st.chain;
 if(c==='all')return +d[p]||0;
 const c1=JSON.parse(d.c1||'{}'),c30=JSON.parse(d.c30||'{}');
 const pick=(o)=>c==='other'?Object.entries(o).filter(([k])=>!MAIN.includes(k)).reduce((s,[,v])=>s+v,0):(o[c]||0);
 const t30=Object.values(c30).reduce((s,v)=>s+v,0)||1;
 if(p==='d1')return pick(c1); if(p==='d30')return pick(c30); return (+d.d7||0)*pick(c30)/t30;}
function apply(){
 const vis=[];
 rows.forEach(r=>{const g=r.dataset.chains.split(',');
  const okC=st.chain==='all'||g.includes(st.chain);
  const v=val(r,st.p),avg=v/pd[st.p];
  const okT=st.tier==='all'||(st.tier==='big'&&avg>=1e5)||(st.tier==='mid'&&avg>=1e4&&avg<1e5)||(st.tier==='small'&&avg<1e4&&avg>0);
  r._v=v;r.style.display=(okC&&okT&&v>0)?'':'none';if(okC&&okT&&v>0)vis.push(r);
  if(st.chain!=='all'){r.querySelector('.v1').textContent=fmt(val(r,'d1'));r.querySelector('.v7').textContent='≈'+fmt(val(r,'d7'));r.querySelector('.v30').textContent=fmt(val(r,'d30'))}
  else{r.querySelector('.v1').textContent=fmt(+r.dataset.d1);r.querySelector('.v7').textContent=fmt(+r.dataset.d7);r.querySelector('.v30').textContent=fmt(+r.dataset.d30)}});
 vis.sort((a,b)=>b._v-a._v);
 const sum=vis.reduce((s,r)=>s+r._v,0)||1,top=vis.length?vis[0]._v/sum:1;
 vis.forEach((r,i)=>{r.cells[0].textContent=i+1;tb.appendChild(r);const sh=r._v/sum;
  r.querySelector('.share .bar i').style.width=(sh/top*100).toFixed(1)+'%';r.querySelector('.sv').textContent=(sh*100).toFixed(sh<0.001?2:1)+'%';
  r.querySelector('.share').title=(sh*100).toFixed(2)+'%'});
 document.querySelectorAll('#mx [data-col]').forEach(c=>c.classList.toggle('hl',c.dataset.col===st.p));
 document.querySelectorAll('.pill[data-f]').forEach(b=>b.classList.toggle('on',st[b.dataset.f]===b.dataset.v));
 document.getElementById('fcount').textContent='%SHOW% '+vis.length+' / '+rows.length;
 history.replaceState(null,'','#'+new URLSearchParams(st).toString());window._vis=vis;window._sum=sum;}
document.querySelectorAll('.pill[data-f]').forEach(b=>b.onclick=()=>{st[b.dataset.f]=b.dataset.v;apply()});
try{const h=new URLSearchParams(location.hash.slice(1));['chain','p','tier'].forEach(k=>{if(h.get(k))st[k]=h.get(k)})}catch(e){}
apply();
const lab=%LAB%;
window.shareMatrix=function(){
 const top=(window._vis||[]).slice(0,10);
 const cn=st.chain==='all'?lab.chain.all:(st.chain==='other'?lab.chain.other:(document.querySelector('.pill[data-v="'+st.chain+'"]').childNodes[0].textContent));
 let t='<div class="sc-box"><table><thead><tr><th class="l">#</th><th class="l">%PROTO%</th><th class="l">%CHAIN%</th><th>'+lab.p[st.p]+'</th><th>%SHARE%</th><th>%DOD%</th></tr></thead><tbody>';
 top.forEach((r,i)=>{const c=r.dataset.chg===''?null:+r.dataset.chg;
  t+='<tr><td class="rk">'+(i+1)+'</td><td class="l"><b>'+r.dataset.name+'</b></td><td class="l" style="color:#8c94a6">'+r.dataset.chainnames+'</td><td>'+((st.chain!=='all'&&st.p==='d7'&&r.dataset.chains.includes(','))?'≈':'')+fmt(r._v)+'</td><td>'+(r._v/window._sum*100).toFixed(1)+'%</td><td class="d '+(c>0?'up':c<0?'dn':'')+'">'+(c==null?'—':(c>0?'▲ ':'▼ ')+Math.abs(c).toFixed(1)+'%')+'</td></tr>'});
 t+='</tbody></table></div>';
 const k=[...document.querySelectorAll('#lpk .hero')].slice(0,4).map(e=>'<div class="sc-kpi"><div class="k">'+e.querySelector('.k').textContent+'</div><div class="v">'+e.querySelector('.v').textContent+'</div></div>').join('');
 ucShare({title:'%TITLE% · '+lab.p[st.p]+' Top10',date:'%DATE%',sub:cn+' · '+lab.tier[st.tier]+' · DefiLlama Launchpad · fees',
  html:'<div class="sc-kpis">'+k+'</div>'+t,file:'uncleonchain-launchpad-%DATE%.png',src:'%SRC%'});
};
})();
</script>"""


def build_launchpad(sd, matrix):
    if not matrix:
        emit("launchpad/index.html", T(f"发射台矩阵 · {BRAND}", f"Launchpads · {BRAND_EN}"),
             f'<h1>{T("发射台矩阵", "Launchpads")}</h1><div class="empty">{T("矩阵数据待生成（拉日度.py）。", "Matrix data pending.")}</div>', active="launchpad")
        return
    ps = [p for p in matrix["协议"] if (p.get("30日") or 0) >= 1000 or (p.get("当日") or 0) >= 100]
    hist = matrix.get("历史") or {}
    hds = sorted(hist)[-30:]
    deep = {x["slug"]: U(f'/launchpad/platforms/{x["slug"]}/') for x in (sd or {}).get("平台", [])}
    ch_day, ch_30 = {}, {}
    for p in matrix["协议"]:
        for k, v in (p.get("分链当日") or {}).items():
            ch_day[k] = ch_day.get(k, 0) + (v or 0)
        for k, v in (p.get("分链30日") or {}).items():
            ch_30[k] = ch_30.get(k, 0) + (v or 0)
    tot_day = sum(ch_day.values()) or 1
    tot_prev = sum((p.get("前日") or 0) for p in matrix["协议"])
    tot_7 = sum((p.get("7日") or 0) for p in matrix["协议"])
    tot_30 = sum(ch_30.values())
    main = sorted([k for k in ch_day if k in MAIN_CHAINS], key=lambda k: -ch_day[k])
    other = sum(v for k, v in ch_day.items() if k not in MAIN_CHAINS)
    bar = "".join(f'<i style="width:{ch_day[k]/tot_day*100:.2f}%;background:var(--c-{k})" title="{esc(chain_name(k))}"></i>' for k in main)
    bar += f'<i style="width:{other/tot_day*100:.2f}%;background:var(--c-other)"></i>'
    leg = "".join(f'<span><i style="background:var(--c-{k})"></i>{esc(chain_name(k))} <b>{f_usd(ch_day[k])}</b> {ch_day[k]/tot_day*100:.1f}%</span>' for k in main)
    leg += f'<span><i style="background:var(--c-other)"></i>{T("其他", "Other")} <b>{f_usd(other)}</b> {other/tot_day*100:.1f}%</span>'
    active_n = sum(1 for p in matrix["协议"] if (p.get("当日") or 0) > 0)
    lead = max(matrix["协议"], key=lambda p: p.get("当日") or 0)
    lead_ch = main[0] if main else None
    kpis = [
        (T("全类目当日手续费", "All launchpads · day"), f_usd(tot_day), fmt_delta((tot_day / tot_prev - 1) if tot_prev else None) + " " + T("日环比", "DoD")),
        (T("7 日 / 30 日合计", "7d / 30d"), f_usd(tot_7), f"{T('30 日', '30d')} {f_usd(tot_30)}"),
        (T("当日活跃协议", "Active protocols"), f"{active_n}", T(f"DefiLlama Launchpad 类目共 {len(matrix['协议'])} 个", f"{len(matrix['协议'])} in DefiLlama's category")),
        (T("当日第一", "#1 today"), esc(lead["名称"]), f'{f_usd(lead.get("当日"))} · {T("占", "")} {(lead.get("当日") or 0)/tot_day*100:.1f}%'),
        (T("链份额第一", "Top chain"), esc(chain_name(lead_ch) if lead_ch else "—"), f'{ch_day.get(lead_ch, 0)/tot_day*100:.1f}% {T("当日手续费", "of fees")}' if lead_ch else ""),
    ]
    kh = "".join(f'<div class="glass hero"><div class="k">{k}</div><div class="v" style="font-size:21px">{v}</div><div class="s">{s}</div></div>' for k, v, s in kpis)
    rows = ""
    for p in ps:
        keys = [CHAIN_KEY.get(c, c.lower().replace(" ", "")) for c in p["链"]]
        grp = [k if k in MAIN_CHAINS else "other" for k in keys]
        c30 = p.get("分链30日") or {}
        ck = max(c30, key=c30.get) if c30 else (keys[0] if keys else "other")          # 份额条颜色 = 手续费最多的那条链
        ck = ck if ck in MAIN_CHAINS else "other"
        sp = [hist[d].get(p["slug"]) for d in hds]
        link = deep.get(p["slug"])
        nm = (f'<a href="{link}">{esc(p["名称"])}</a> <span class="deep">{T("深度", "deep")}</span>' if link else
              f'<a href="https://defillama.com/protocol/{esc(p["slug"])}" target="_blank" rel="noopener">{esc(p["名称"])}</a>')
        logo = f'<img src="{esc(p["logo"])}" alt="" loading="lazy" referrerpolicy="no-referrer">' if p.get("logo") else '<img alt="">'
        badges = "".join(chain_badge(c) for c in p["链"][:3]) + (f'<span class="badge b-other">+{len(p["链"])-3}</span>' if len(p["链"]) > 3 else "")
        attrs = {"name": p["名称"], "chains": ",".join(sorted(set(grp))), "chainnames": " / ".join(p["链"][:3]), "ck": ck,
                 "d1": p.get("当日") or 0, "d7": p.get("7日") or 0, "d30": p.get("30日") or 0, "chg": p.get("日环比"),
                 "c1": json.dumps({k: round(v) for k, v in (p.get("分链当日") or {}).items()}),
                 "c30": json.dumps({k: round(v) for k, v in c30.items()})}
        da = " ".join(f'data-{k}="{esc(v if v is not None else "")}"' for k, v in attrs.items())
        rows += (f'<tr {da}><td class="rk"></td><td class="l"><span class="pname">{logo}{nm}</span></td><td class="l">{badges}</td>'
                 f'<td class="l"><span class="share"><span class="bar"><i style="background:var(--c-{ck})"></i></span><b class="sv"></b></span></td>'
                 f'<td data-col="d1" class="v1">{f_usd(p.get("当日"))}</td><td>{fmt_delta(p.get("日环比"), pct_input=True)}</td>'
                 f'<td data-col="d7" class="v7">{f_usd(p.get("7日"))}</td><td data-col="d30" class="v30">{f_usd(p.get("30日"))}</td>'
                 f'<td>{spark(sp, "up" if (p.get("日环比") or 0) >= 0 else "dn")}</td></tr>')
    chain_pills = f'<button class="pill on" data-f="chain" data-v="all">{T("全部", "All")}</button>' + "".join(
        f'<button class="pill" data-f="chain" data-v="{k}">{esc(chain_name(k))}<small>{ch_day[k]/tot_day*100:.0f}%</small></button>' for k in main
    ) + f'<button class="pill" data-f="chain" data-v="other">{T("其他链", "Other")}</button>'
    deep_rows = ""
    for x in (sd or {}).get("平台", []):
        deep_rows += (f'<tr><td class="l"><span class="pname"><a href="{U("/launchpad/platforms/" + x["slug"] + "/")}">{esc(x["名称"])}</a></span></td>'
                      f'<td class="l">{chain_badge(x["链"])}</td><td>{T("延迟", "late") if x["延迟"] else f_usd(x["当日手续费"])}</td>'
                      f'<td>{fmt_delta(x["日环比"])}</td><td>{f_usd(x["7日均"])}</td><td>{f_usd(x["当日收入"])}</td>'
                      f'<td>{spark(list(x["手续费序列"].values())[-30:])}</td></tr>')
    arc = (sd or {}).get("Arc") or {}
    trend = ""
    if sd and sd.get("平台"):
        allds = sorted(set().union(*[x["手续费序列"].keys() for x in sd["平台"]]))
        src_ = write_data("launchpad/deep.json", allds, {x["slug"]: x["手续费序列"] for x in sd["平台"]})
        trend = chart_div({"src": src_, "fmt": "usd", "ranges": ["3M", "6M", "1Y", "ALL"], "range": "3M",
                           "series": [{"k": x["slug"], "n": x["名称"], "c": f"s{k + 1}"} for k, x in enumerate(sd["平台"][:8])]})
    tpath, bk = launchpad_history(matrix)
    total_html = ""
    if tpath:
        total_html = (f'<h2>{T("全网手续费汇总趋势", "Sector-wide fee trend")} <span class="sub">{T("看赛道水多没多；切到「份额 %」看资金在平台之间怎么挪", "Is the sector heating up? Switch to Share % to see money moving between venues")}</span></h2>'
                      f'<div class="card" style="padding:14px 18px">'
                      + chart_div({"src": tpath, "fmt": "usd", "stack": True, "ranges": ["1M", "3M", "6M", "1Y", "ALL"], "range": "3M", "series": bk["cfg"],
                                   "note": T(f"DefiLlama Launchpad 类目 Top60 逐日手续费（{bk['起']} 起，{bk['天数']} 天），前 8 名按近 90 天合计排序、颜色固定跟着平台走，其余并入「其他」。口径是手续费不是成交量：各平台费率不同，份额按手续费算。",
                                             f"Daily fees of DefiLlama's top-60 launchpads since {bk['起']} ({bk['天数']} days). Top 8 by the last 90 days, colors fixed per platform, the rest folded into Other. Fees, not volume: fee rates differ by venue.")})
                      + f'</div><h3>{T("当日变化拆解", "Day-over-day breakdown")} <span class="sub" style="font-weight:400;color:var(--muted)">{bk["d0"]} → {bk["d1"]}</span></h3>{breakdown_html(bk)}')
    first_arc = str(((arc.get("发射台") or [{}])[0]).get("slug", ""))
    body = f"""<div class="ph"><div><div class="eyebrow">Launchpad Matrix</div><h1>{T("发射台矩阵", "Launchpad matrix")}</h1>
<p class="lede">{T(f"DefiLlama Launchpad 类目全部 {len(matrix['协议'])} 个协议：先看全网汇总趋势（赛道水多没多、资金在哪些平台之间挪），再看跨链排行和每个平台的市场份额。口径统一用手续费（fees），日期是 UTC 完整日。",
                   f"All {len(matrix['协议'])} protocols in DefiLlama's Launchpad category: the sector-wide trend first (is money flowing in, and between which venues), then the cross-chain ranking with market share. Fees, UTC full days.")}</p></div>
<div class="stamp">{T("数据截至", "Data as of")} <b>{matrix["日期"]}</b>{T("（UTC 完整日）", " (UTC)")}<br>{T("生成", "Generated")} <b>{esc(matrix.get("生成时间UTC", "")[:16].replace("T", " "))} UTC</b></div></div>
<div class="grid g5" id="lpk">{kh}</div>
{total_html}
<div class="card" style="padding:14px 16px;margin-top:22px"><div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;font-size:12.5px"><b>{T("生态份额 · 当日手续费按链拆分", "Chain share · today's fees by chain")}</b><span class="stamp">{T("多链协议按 DefiLlama 分链数据精确拆分", "Multi-chain protocols split by DefiLlama's per-chain data")}</span></div>
<div class="chainbar">{bar}</div><div class="chainleg">{leg}</div></div>
<h2>{T("跨链排行 · 市场份额", "Cross-chain ranking · market share")} <span class="sub">{T("份额条 = 占当前筛选范围合计的百分比，颜色 = 主力所在链；链接会记住当前筛选，可直接分享", "Share bar = % of the filtered total, color = main chain; the URL keeps your filters")}</span></h2>
<div class="glass fbar">
<div class="fg"><span class="fl">{T("生态", "Chain")}</span>{chain_pills}</div>
<div class="fg"><span class="fl">{T("周期", "Period")}</span><button class="pill" data-f="p" data-v="d1">{T("当日", "Day")}</button><button class="pill on" data-f="p" data-v="d7">{T("7 日", "7d")}</button><button class="pill" data-f="p" data-v="d30">{T("30 日", "30d")}</button></div>
<div class="fg"><span class="fl">{T("金额档", "Tier")}</span><button class="pill on" data-f="tier" data-v="all">{T("全部", "All")}</button><button class="pill" data-f="tier" data-v="big">{T("主力", "Major")} ≥$100K</button><button class="pill" data-f="tier" data-v="mid">{T("腰部", "Mid")} $10K–100K</button><button class="pill" data-f="tier" data-v="small">{T("黑马", "Small")} &lt;$10K</button></div>
<span class="fcount" id="fcount"></span><button class="btn" onclick="shareMatrix()">📸 {T("生成今日排行长图", "Share ranking image")}</button>
</div>
<div class="tw scroll"><table id="mx"><thead><tr><th class="l">#</th><th class="l">{T("协议", "Protocol")}</th><th class="l">{T("链", "Chain")}</th><th class="l">{T("份额", "Share")}</th><th data-col="d1">{T("当日", "Day")}</th><th>{T("日环比", "DoD")}</th>
<th data-col="d7">{T("7 日", "7d")}</th><th data-col="d30">{T("30 日", "30d")}</th><th>{T("30 日走势", "30d trend")}</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="tnote">{T("金额档按当前选中周期的金额判断（选 7 日 / 30 日时按日均换算）。选了某条链时，当日和 30 日用 DefiLlama 分链数据精确拆分，7 日按该协议 30 日分链占比折算（标 ≈）。「深度」= 本站逐日追踪的平台，点进去看协议收入、回购估值；其余链接到 DefiLlama。",
                  "Tiers use the selected period (daily average for 7d/30d). With a chain selected, day and 30d use DefiLlama's per-chain split and 7d is pro-rated (≈). 'deep' = tracked daily here; others link to DefiLlama.")}</p>
<h2 id="deep">{T("深度追踪平台", "Deep-tracked platforms")} <span class="sub">{T("逐日序列 + 协议收入 + 回购市盈率", "daily series + revenue + buyback P/E")}</span> <a class="sub" href="{U("/launchpad/report/")}">{T("看今日文字解读 →", "Today's narrative →")}</a></h2>
<div class="tw"><table><thead><tr><th class="l">{T("平台", "Platform")}</th><th class="l">{T("链", "Chain")}</th><th>{T("当日手续费", "Fees (day)")}</th><th>{T("日环比", "DoD")}</th><th>{T("7 日均", "7d avg")}</th><th>{T("当日协议收入", "Revenue (day)")}</th><th>{T("30 日走势", "30d trend")}</th></tr></thead><tbody>{deep_rows}</tbody></table></div>
<div class="card" style="padding:14px 18px;margin-top:12px"><h3 style="margin-top:0">{T("深度追踪平台 · 手续费走势", "Deep-tracked platforms · fees")}</h3>{trend}</div>
<h2 id="arc">{T("Arc 整链观察", "Arc chain watch")} <span class="sub">{T("本站链上节点自算口径（和 DefiLlama 口径不同，单独列）", "own node data (differs from DefiLlama)")}</span></h2>
<div class="card" style="padding:14px 18px;font-size:13px;color:var(--ink2)">Arc {esc(arc.get("日期") or "")}：{T("发射台合计", "launchpads")} <b class="num">{f_usd(arc.get("发射台手续费"))}</b> ·
{T("全链手续费", "chain fees")} <b class="num">{f_usd(arc.get("全链手续费"))}</b> · {T("升级条件", "upgrade condition")} {esc(arc.get("升级条件") or "—")} ·
{len(arc.get("发射台") or [])} {T("家发射台", "launchpads")}，<a href="{U("/launchpad/platforms/arc-" + first_arc + "/")}">{T("逐个看 →", "see each →")}</a></div>"""
    lab = {"chain": {"all": T("全部生态", "All chains"), "other": T("其他链", "Other chains")}, "p": {"d1": T("当日", "Day"), "d7": T("7 日", "7d"), "d30": T("30 日", "30d")},
           "tier": {"all": T("全部金额档", "All tiers"), "big": T("主力 ≥$100K", "Major ≥$100K"), "mid": T("腰部 $10K–100K", "Mid $10K–100K"), "small": T("黑马 <$10K", "Small <$10K")}}
    js = (MATRIX_JS.replace("%MAIN%", json.dumps(MAIN_CHAINS)).replace("%DATE%", matrix["日期"]).replace("%LAB%", json.dumps(lab, ensure_ascii=False))
          .replace("%SHOW%", T("显示", "Showing")).replace("%PROTO%", T("协议", "Protocol")).replace("%CHAIN%", T("链", "Chain"))
          .replace("%SHARE%", T("份额", "Share")).replace("%DOD%", T("日环比", "DoD")).replace("%TITLE%", T("发射台矩阵", "Launchpad matrix"))
          .replace("%SRC%", T("数据：DefiLlama · 口径：手续费", "Data: DefiLlama · fees")))
    emit("launchpad/index.html", T(f"发射台矩阵 · 跨链 Launchpad 手续费排行 · {BRAND}", f"Launchpad matrix · cross-chain fees · {BRAND_EN}"), body,
         active="launchpad", share=True, chart=True, scripts=js,
         desc=T(f'{matrix["日期"]} 发射台全类目当日手续费 {f_usd(tot_day)}，第一 {lead["名称"]}。', f'{matrix["日期"]}: launchpad fees {f_usd(tot_day)}, #1 {lead["名称"]}.'))


def build_launchpad_platforms(sd):
    if not sd:
        return
    tpl = lambda k, v, s="": f'<div class="glass hero"><div class="k">{k}</div><div class="v" style="font-size:21px">{v}</div><div class="s">{s}</div></div>'  # noqa: E731
    for x in sd["平台"]:
        sym = x.get("估值符号")
        val = (sd.get("估值") or {}).get(sym) if sym else None
        k = (tpl(T("当日手续费", "Fees (day)"), T("延迟", "late") if x["延迟"] else f_usd(x["当日手续费"]), fmt_delta(x["日环比"]) + " " + T("日环比", "DoD"))
             + tpl(T("7 日均", "7d avg"), f_usd(x["7日均"]), fmt_delta(x["7日均环比"]) + " " + T("周环比", "WoW"))
             + tpl(T("当日协议收入", "Revenue (day)"), f_usd(x["当日收入"]), f"{T('分账比率', 'take rate')} {fmt_pct(x['分账比率'])}")
             + tpl(T("赛道份额（Top60）", "Sector share (top 60)"), fmt_pct(x["占赛道份额"]), f"{T('距单日峰值', 'vs peak day')} {fmt_pct(x['距单日峰值'])}")
             + tpl(T("累计手续费", "Cumulative fees"), f_usd(x["累计"]), f"{T('单日峰值', 'peak day')} {x['峰值日'] or '—'}"))
        dates = sorted(set(x["手续费序列"]) | set(x["收入序列"]))
        src_ = write_data(f'launchpad/p-{x["slug"]}.json', dates, {"f": x["手续费序列"], "r": x["收入序列"]})
        chart = chart_div({"src": src_, "fmt": "usd", "ranges": ["1M", "3M", "6M", "ALL"], "range": "ALL",
                           "series": [{"k": "f", "n": T("手续费", "Fees"), "c": "s1"}, {"k": "r", "n": T("协议收入", "Revenue"), "c": "s2"}]})
        vb = ""
        if val:
            pe = lambda v: f"{v:.2f}x" if v else "—"  # noqa: E731
            vb = (f'<h2>{T("估值", "Valuation")}（{sym}）</h2><div class="grid g3">'
                  + tpl(T("burn-adjusted 市值", "Burn-adjusted market cap"), f_usd(val.get("市值")))
                  + tpl(T("收入市盈率", "Revenue P/E"), pe(val.get("收入市盈率")))
                  + tpl(T("回购市盈率", "Buyback P/E"), pe(val.get("回购市盈率")), f"{T('回购收益率', 'buyback yield')} {fmt_pct(val.get('回购收益率'))}") + "</div>")
        body = f"""{crumbs([(T("发射台矩阵", "Launchpads"), "/launchpad/"), (T("深度追踪", "Deep-tracked"), "/launchpad/#deep"), (x["名称"], None)])}
<div class="ph"><div><div class="eyebrow">Launchpad · {T("深度追踪", "deep-tracked")}</div><h1>{esc(x["名称"])} {chain_badge(x["链"])}</h1></div>
<div class="stamp">{T("数据截至", "Data as of")} <b>{sd["日期"]}</b></div></div>
<div class="grid g5">{k}</div>
<div class="card" style="padding:14px 18px;margin-top:14px"><h3 style="margin-top:0">{T("手续费 / 协议收入", "Fees / revenue")}</h3>{chart}</div>
{vb}"""
        emit(f'launchpad/platforms/{x["slug"]}/index.html', f'{x["名称"]} · {T("发射台", "Launchpad")} · {T(BRAND, BRAND_EN)}', body,
             active="launchpad", chart=True)
    for z in (sd.get("Arc") or {}).get("发射台", []):
        k = (tpl(T("当日手续费", "Fees (day)"), f_usd(z["当日手续费"])) + tpl(T("7 日合计", "7d"), f_usd(z["7日"]))
             + tpl(T("30 日合计", "30d"), f_usd(z["30日"])) + tpl(T("7 日 DEX 成交", "7d DEX volume"), f_usd(z["7日DEX"])))
        src_ = write_data(f'launchpad/arc-{z["slug"]}.json', sorted(z["手续费序列"]), {"f": z["手续费序列"]})
        chart = chart_div({"src": src_, "fmt": "usd", "ranges": ["1M", "3M", "ALL"], "range": "ALL", "series": [{"k": "f", "n": T("手续费", "Fees"), "c": "s1", "area": True}]})
        body = f"""{crumbs([(T("发射台矩阵", "Launchpads"), "/launchpad/"), (T("Arc 整链观察", "Arc chain"), "/launchpad/#arc"), (z["名称"], None)])}
<div class="ph"><div><div class="eyebrow">Launchpad · {T("Arc 链上自算", "Arc · own node")}</div><h1>{esc(z["名称"])} {chain_badge("Arc")}</h1></div>
<div class="stamp">{T("数据截至", "Data as of")} <b>{sd["日期"]}</b></div></div>
<div class="grid g4">{k}</div>
<div class="card" style="padding:14px 18px;margin-top:14px"><h3 style="margin-top:0">{T("手续费走势", "Fees")}</h3>{chart}</div>
<p class="tnote">{T("Arc 上不少发射台的 swap 走 Uniswap 底层池，DEX 成交记在 Uniswap 名下，这里的「DEX 成交」系统性偏低，看手续费更可靠。本页是本站链上节点自算口径，和 DefiLlama 数字可能不同。",
                   "Many Arc launchpads route swaps through Uniswap pools, so DEX volume is understated here; fees are more reliable. Own-node data, may differ from DefiLlama.")}</p>"""
        emit(f'launchpad/platforms/arc-{z["slug"]}/index.html', f'{z["名称"]}（Arc）· {T("发射台", "Launchpad")} · {T(BRAND, BRAND_EN)}', body,
             active="launchpad", chart=True)


def build_launchpad_report(sd):
    if not sd:
        return
    extra = f'<style>{sd["css"]}\n{ST.REPORT_OVERRIDE}</style>'
    scripts = f'<script type="application/json" id="chart-data">{sd["chart_json"]}</script><script>{sd["js"]}</script>'
    rd = os.path.join(SITE, "launchpad", "report")
    os.makedirs(rd, exist_ok=True)
    note_en = '<div class="note">This daily launchpad narrative is generated in Chinese only; the numbers are the same as in the matrix.</div>' if LANG["v"] == "en" else ""
    links = (f'<p class="tnote">{T("本期永久存档", "Permanent link")} <a href="{U("/launchpad/report/" + sd["日期"] + "/")}">/launchpad/report/{sd["日期"]}/</a>'
             f' ｜ <a href="{U("/launchpad/report/archive/")}">{T("全部往期 →", "Archive →")}</a></p>')
    for rel, cur in (("launchpad/report/index.html", T("今日文字解读", "Today's narrative")), (f'launchpad/report/{sd["日期"]}/index.html', sd["日期"])):
        body = (crumbs([(T("发射台矩阵", "Launchpads"), "/launchpad/"), (T("文字解读", "Narrative"), "/launchpad/report/archive/"), (cur, None)])
                + note_en + f'<div class="rpt">{sd["正文"]}{links}</div>')
        emit(rel, f'{T("发射台日更 · 文字解读", "Launchpad daily narrative")} · {sd["日期"]} · {T(BRAND, BRAND_EN)}', body, active="launchpad",
             extra_head=extra, desc=sd["一句话"], scripts=scripts)
    ds = sorted([d for d in os.listdir(rd) if re.match(r"^\d{4}-\d{2}-\d{2}$", d)], reverse=True)
    for base in (rd, os.path.join(SITE, "en", "launchpad", "report")):
        for d in (os.listdir(base) if os.path.isdir(base) else []):
            f = os.path.join(base, d, "index.html")
            if os.path.exists(f):
                old = open(f, encoding="utf-8").read()
                new = strip_webfonts(old)
                if new != old:
                    with open(f, "w", encoding="utf-8") as fh:
                        fh.write(new)
    lis = "".join(f'<li><span class="d">{d}</span><a href="{U("/launchpad/report/" + d + "/")}">{T("发射台日更 · 文字解读", "Launchpad daily narrative")}</a></li>' for d in ds)
    emit("launchpad/report/archive/index.html", T(f"发射台文字解读往期 · {BRAND}", f"Narrative archive · {BRAND_EN}"),
         crumbs([(T("发射台矩阵", "Launchpads"), "/launchpad/"), (T("文字解读 · 往期", "Narrative archive"), None)])
         + f'<div class="eyebrow">Archive</div><h1>{T("发射台文字解读 · 往期", "Launchpad narrative · archive")}</h1><p class="lede">{T(f"共 {len(ds)} 期，UTC 完整日为单位。", f"{len(ds)} issues, by UTC day.")}</p>'
         f'<div class="card" style="margin-top:18px"><ul class="list">{lis}</ul></div>', active="launchpad", narrow=True)


# ---------------------------------------------------------------- 板块轮动 / 叙事埋伏
def post_list(slug):
    posts = ALL_POSTS[slug]
    if not posts:
        return f'<div class="empty">{T("还没有发第一篇。写好会第一时间发在这里。", "Nothing published yet.")}</div>'
    li = "".join(f'<li><span class="d">{esc(x["日期"])}</span><span><a href="{U("/" + slug + "/" + x["slug"] + "/")}">{esc(x["标题"])}</a>'
                 f'<span class="s">{esc(x["摘要"])}</span></span></li>' for x in posts)
    return f'<div class="card"><ul class="list">{li}</ul></div>'


def rot_clean(snap, min_cap=3e8):
    """CoinGecko 类目会不定期增删成分币，市值一天跳几十上百% 基本是成分调整不是行情，排行里剔掉单列。"""
    big = [c for c in snap if c["市值"] >= min_cap]
    return [c for c in big if abs(c["24h"]) <= 35], [c for c in big if abs(c["24h"]) > 35]


def build_rotation(rot):
    grid, lose, meta = "", "", ""
    if rot:
        dates = sorted(rot)
        last = rot[dates[-1]]
        big, odd = rot_clean(last)
        prev7 = next((rot[d] for d in reversed(dates) if R.days_between(d, dates[-1]) >= 7), None)
        p7 = {c["id"]: c["市值"] for c in prev7} if prev7 else {}
        prev1 = rot[dates[-2]] if len(dates) >= 2 else None
        v1 = {c["id"]: c["成交额"] for c in prev1} if prev1 else {}

        def card(c):
            tone = "up" if c["24h"] >= 0 else "dn"
            w = f' · {T("7 日", "7d")} {(c["市值"]/p7[c["id"]]-1)*100:+.1f}%' if c["id"] in p7 and p7[c["id"]] else ""
            vc = f' · {T("成交额环比", "vol DoD")} {(c["成交额"]/v1[c["id"]]-1)*100:+.0f}%' if v1.get(c["id"]) else ""
            return (f'<div class="card cat t-{tone}"><div class="nm" title="{esc(c["名称"])}">{esc(c["名称"])}</div>'
                    f'<div class="v t-{tone}">{c["24h"]:+.2f}%</div><div class="s">{T("市值", "cap")} {f_usd(c["市值"])} · {T("成交", "vol")} {f_usd(c["成交额"])}{w}{vc}</div>'
                    f'<div class="t3">{esc(" · ".join(c.get("前三") or []))}</div></div>')
        grid = "".join(card(c) for c in sorted(big, key=lambda c: -c["24h"])[:16])
        lose = "".join(card(c) for c in sorted(big, key=lambda c: c["24h"])[:8])
        meta = T(f'快照 {dates[-1]} · 共 {len(last)} 个类目（市值 ≥ $50M），这里只看市值 ≥ $300M 的 {len(big)} 个 · 历史快照 {len(dates)} 天'
                 + ("（满 7 天后显示 7 日轮动）" if not prev7 else "")
                 + (" · 疑似成分调整、未进排行：" + "、".join(f"{c['名称']} {c['24h']:+.0f}%" for c in odd[:6]) if odd else ""),
                 f'Snapshot {dates[-1]} · {len(last)} categories (cap ≥ $50M); showing {len(big)} with cap ≥ $300M · {len(dates)} days of history'
                 + (" · likely constituent changes excluded: " + ", ".join(f"{c['名称']} {c['24h']:+.0f}%" for c in odd[:6]) if odd else ""))
    body = f"""<div class="ph"><div><div class="eyebrow">Sector Rotation</div><h1>{T("板块轮动", "Sector rotation")}</h1>
<p class="lede">{esc(T(PILLARS[1]["desc"], PILLARS[1]["descEN"]))} {T("类目口径来自 CoinGecko，一个币可以同时属于多个类目，看相对强弱，不要把类目市值加总。", "Categories overlap (a coin can be in several), so compare relative strength; don't sum category caps.")}</p></div></div>
{f'<p class="tnote">{esc(meta)}</p>' if meta else ''}
<h2>{T("24h 领涨赛道", "24h leaders")}</h2>{f'<div class="grid g4">{grid}</div>' if grid else '<div class="empty">' + T("板块快照待生成。", "Snapshot pending.") + '</div>'}
<h2>{T("24h 领跌赛道", "24h laggards")}</h2>{f'<div class="grid g4">{lose}</div>' if lose else ''}
<h2>{T("轮动复盘", "Rotation reviews")}</h2>{post_list("rotation")}"""
    emit("rotation/index.html", T(f"板块轮动 · {BRAND}", f"Sector rotation · {BRAND_EN}"), body, active="rotation", desc=T(PILLARS[1]["desc"], PILLARS[1]["descEN"]))


RADAR = [
    ("Smart Money 钱包监控", "Smart-money wallets",
     "先从本站已有的链上管道做起：Robinhood Chain / Arc 发射台的大户地址逐笔追踪（RPC 已接通），再扩到 Solana / BSC。免费标签数据不稳定，不拿猜测当结论。",
     "Starting from our own pipes: whale wallets on Robinhood Chain / Arc launchpads, then Solana / BSC. No guessed labels."),
    ("未发币高热度协议雷达", "Tokenless protocol radar", "DefiLlama 协议列表里「没有代币」的协议 × 手续费 / TVL 增速做筛选，找有真实收入、还没发币的项目。",
     "Protocols without a token on DefiLlama, screened by fee / TVL growth — real revenue, no token yet."),
    ("巨鲸埋伏", "Whale positioning", "BTC 层面的交易所净流量已在宏观第三层上线；山寨币层面需要逐币持仓分布，筹备中。",
     "BTC exchange flows are live in macro L3; altcoin holder distribution is in preparation."),
]


def build_narrative():
    cards = "".join(f'<div class="pend"><b>{esc(T(t, te))} · {T("筹备中", "in preparation")}</b>{esc(T(d, de))}</div>' for t, te, d, de in RADAR)
    body = f"""<div class="ph"><div><div class="eyebrow">Narrative Radar</div><h1>{T("叙事埋伏", "Narrative radar")}</h1>
<p class="lede">{esc(T(PILLARS[2]["desc"], PILLARS[2]["descEN"]))}</p></div></div>
<h2>{T("雷达", "Radar")} <span class="sub">{T("数据源接通一个上线一个", "each goes live when its data source does")}</span></h2><div class="grid g3">{cards}</div>
<h2>{T("观察笔记", "Notes")}</h2>{post_list("narrative")}"""
    emit("narrative/index.html", T(f"叙事埋伏 · {BRAND}", f"Narrative radar · {BRAND_EN}"), body, active="narrative", desc=T(PILLARS[2]["desc"], PILLARS[2]["descEN"]))


ZH_ONLY = '<div class="note">This piece is written in Chinese.</div>'


def build_posts():
    for p in PILLARS:
        for x in ALL_POSTS[p["slug"]]:
            cr = crumbs([(T(p["nav"], p["en"]), f'/{p["slug"]}/'), (x["标题"], None)])
            note = ZH_ONLY if LANG["v"] == "en" else ""
            if x["kind"] == "html":
                body, extra = cr + note + x["html"], (f"<style>{x['css']}</style>" if x["css"] else "")
            else:
                body = (cr + note + f'<div class="eyebrow">{esc(T(p["nav"], p["en"]))}</div><h1>{esc(x["标题"])}</h1><p class="stamp" style="text-align:left">{esc(x["日期"])}</p>'
                        f'<div class="article" style="margin-top:18px">{x["html"]}</div>')
                extra = ""
            emit(f'{p["slug"]}/{x["slug"]}/index.html', f'{x["标题"]} · {T(BRAND, BRAND_EN)}', body, active=p["slug"], desc=x["摘要"],
                 extra_head=extra, narrow=x["kind"] == "md")


# ---------------------------------------------------------------- 分析报告
REPORT_JS = r"""<script>
(function(){
const f=document.getElementById('rf'),open=document.getElementById('rf-open');
function fit(){try{const d=f.contentWindow.document;f.style.height=(d.documentElement.scrollHeight+4)+'px'}catch(e){}}
function pick(){const t=document.documentElement.getAttribute('data-theme')==='light'?'light':'dark';
 const want=f.dataset[t];if(f.getAttribute('src')!==want){f.setAttribute('src',want)}if(open)open.href=want}
f.addEventListener('load',()=>{fit();try{new ResizeObserver(fit).observe(f.contentWindow.document.body)}catch(e){};setTimeout(fit,800);setTimeout(fit,2500)});
window.addEventListener('uc-theme',pick);window.addEventListener('resize',fit);pick();
})();
</script>"""


def build_reports():
    lst = ""
    for r in ALL_REPORTS:
        tags = "".join(f'<span class="chip">{esc(t)}</span>' for t in r["标签列表"])
        if LANG["v"] == "en" and not r.get("en_src") and r["kind"] != "md":
            tags = '<span class="chip t-warn">中文</span>' + tags
        lst += (f'<a class="card rcard" href="{U("/reports/" + r["slug"] + "/")}"><span class="d">{esc(r["日期"])}</span><b>{esc(LF(r, "标题"))}</b>'
                f'<p>{esc(LF(r, "摘要"))}</p>{f"<div class=chips>{tags}</div>" if tags else ""}</a>')
    how = T("周度节奏的深度报告：针对一个方向或议题做全方位分析，给出可以拿来做决策依据的结论。报告原样排版、跟随站点深浅色；写作当时的判断发布后不改，后续修正另起一篇。",
            "Weekly deep-dive reports: one theme analysed end to end, with conclusions usable as decision inputs. Original layout, following the site's light/dark theme. Frozen once published; corrections go in a new report.")
    zh_only = [r for r in ALL_REPORTS if not r.get("en_src") and r["kind"] != "md"]
    en_note = ('<div class="note">Reports marked 中文 are available in Chinese only for now.</div>' if LANG["v"] == "en" and zh_only else "")
    empty = '<div class="empty">' + T("第一篇报告整理好就发在这里。", "The first report will appear here.") + '</div>'
    body = f"""<div class="ph"><div><div class="eyebrow">Research Reports</div><h1>{T("分析报告", "Research reports")}</h1>
<p class="lede">{esc(how)}</p></div></div>
{en_note}
{f'<div class="grid g2">{lst}</div>' if lst else empty}"""
    emit("reports/index.html", T(f"分析报告 · {BRAND}", f"Research reports · {BRAND_EN}"), body, active="reports", desc=how)
    for r in ALL_REPORTS:
        cr = crumbs([(T("分析报告", "Reports"), "/reports/"), (LF(r, "标题"), None)])
        note = ZH_ONLY if LANG["v"] == "en" and not r.get("en_src") else ""
        if r["kind"] == "md":
            content = f'<div class="rbody"><div class="article">{r["html"]}</div></div>'
            scripts = ""
        else:
            # 整篇 HTML 原样放进 iframe（报告自己的样式不和站点互相干扰）；浅色用原文，深色用构建时自动换色的副本
            content = (f'<p class="tnote" style="margin:0 0 8px;text-align:right"><a id="rf-open" href="raw.html" target="_blank" rel="noopener">{T("在新窗口全屏阅读 ↗", "Open full screen ↗")}</a></p>'
                       f'<iframe id="rf" data-light="raw.html" data-dark="raw-dark.html" title="{esc(LF(r, "标题"))}" '
                       f'style="width:100%;border:1px solid var(--line);border-radius:14px;min-height:80vh;display:block;background:var(--card)"></iframe>')
            scripts = REPORT_JS
        emit(f'reports/{r["slug"]}/index.html', f'{LF(r, "标题")} · {T("分析报告", "Reports")} · {T(BRAND, BRAND_EN)}', cr + note + content,
             active="reports", desc=LF(r, "摘要"), scripts=scripts)


# 报告深色副本：把每个颜色的明度翻转、色相保留（白纸 → 深底，深字 → 浅字，品牌蓝红金 → 同色系的亮色），
# 只改 <style> 和 style / fill / stroke / color 这些颜色属性，任何排版的报告都能自动适配，不用逐篇手调。
import colorsys                                                          # noqa: E402

_HEX = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
_RGB = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(,\s*[\d.]+\s*)?\)")
_NAMED = re.compile(r"(?<![\w-])(white|black)(?![\w-])")


def _flip(r, g, b):
    h, l, s_ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    l2 = 0.065 + (1 - l) * 0.875
    if l2 < 0.3:                      # 变成深底的浅色块：降饱和，避免一块块脏色
        s_ *= 0.5
    elif s_ > 0.35 and l2 < 0.62:     # 品牌强调色：再提亮一点，深底上看得清
        l2 = min(0.72, l2 + 0.06)
    r2, g2, b2 = colorsys.hls_to_rgb(h, l2, s_)
    return round(r2 * 255), round(g2 * 255), round(b2 * 255)


def _dark_css(text):
    def hx(m):
        v = m.group(1)
        if len(v) in (3, 4):
            v = "".join(c * 2 for c in v)
        r, g, b = (int(v[i:i + 2], 16) for i in (0, 2, 4))
        a = v[6:8] if len(v) == 8 else ""
        return "#%02x%02x%02x%s" % (*_flip(r, g, b), a)

    def rg(m):
        r, g, b = _flip(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return f"rgba({r},{g},{b}{m.group(4)})" if m.group(4) else f"rgb({r},{g},{b})"
    text = _HEX.sub(hx, text)
    text = _RGB.sub(rg, text)
    return _NAMED.sub(lambda m: "#151821" if m.group(1) == "white" else "#e6e9ef", text)


def dark_report(raw):
    raw = re.sub(r"(<style[^>]*>)(.*?)(</style>)", lambda m: m.group(1) + _dark_css(m.group(2)) + m.group(3), raw, flags=re.S | re.I)
    raw = re.sub(r'(\s(?:style|fill|stroke|stop-color|color|bgcolor)=")([^"]*)(")', lambda m: m.group(1) + _dark_css(m.group(2)) + m.group(3), raw)
    return raw.replace("</head>", "<style>html{color-scheme:dark}img{filter:brightness(.9)}</style></head>", 1)


REPORT_HEAD = ("<script>(function(){document.documentElement.setAttribute('data-theme','light');"   # 报告自带的深色媒体查询不要抢
               "document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[href]');if(!a)return;"
               "var h=a.getAttribute('href');if(h&&h.charAt(0)!=='#'&&!a.target){a.target=/uncleonchain\\.com|^\\//.test(h)?'_top':'_blank'}});})();</script>")


def strip_webfonts(html_):
    """去掉 Google Fonts（国内连不上会卡住渲染），字体退回系统字体。"""
    html_ = re.sub(r'<link[^>]*fonts\.(?:googleapis|gstatic)\.com[^>]*>\s*', "", html_)
    return re.sub(r'@import\s+url\([^)]*fonts\.googleapis\.com[^)]*\)\s*;?', "", html_)


def copy_report_files():
    """报告原文和附件拷到 site/reports/<slug>/ 与 site/en/reports/<slug>/：raw.html（浅色原文）+ raw-dark.html（自动深色）。
    英文站有 .en.html 就用英文版，没有就用中文原文。"""
    for r in ALL_REPORTS:
        if r["kind"] not in ("dir", "html"):
            continue
        for lang, base in (("zh", os.path.join(SITE, "reports", r["slug"])), ("en", os.path.join(SITE, "en", "reports", r["slug"]))):
            os.makedirs(base, exist_ok=True)
            main = r.get("en_src") if lang == "en" and r.get("en_src") else (r["src"] if r["kind"] == "html" else os.path.join(r["src"], "index.html"))
            if r["kind"] == "dir":
                for root, _, fs in os.walk(r["src"]):
                    for f in fs:
                        if f in ("index.html", "index.en.html"):
                            continue
                        rel = os.path.relpath(os.path.join(root, f), r["src"])
                        os.makedirs(os.path.dirname(os.path.join(base, rel)), exist_ok=True)
                        shutil.copyfile(os.path.join(root, f), os.path.join(base, rel))
            raw = open(main, encoding="utf-8").read()
            raw = strip_webfonts(raw)
            raw = re.sub(r"<head([^>]*)>", lambda m: f"<head{m.group(1)}>{REPORT_HEAD}", raw, count=1)
            with open(os.path.join(base, "raw.html"), "w", encoding="utf-8") as fh:
                fh.write(raw)
            with open(os.path.join(base, "raw-dark.html"), "w", encoding="utf-8") as fh:
                fh.write(dark_report(raw))


# ---------------------------------------------------------------- 解读日志
def readings_table(lay):
    trs = "".join(f'<tr><td class="l"><a href="{ind_href(x["key"])}" style="text-decoration:none">{esc(LF(x, "名称"))}</a> <span class="badge b-other">{esc(T(x["级别"], LEVEL_EN.get(x["级别"], x["级别"])))}</span></td><td>{esc(x["显示"])}</td>'
                  f'<td class="l">{tone_chip(short_zone(LF(x, "区间")), x["tone"])}</td><td class="l wrap" style="color:var(--ink2)">{esc(LF(x, "依据"))}</td>'
                  f'<td>{x["截至"][5:]}{" ⚠" if x["过期"] else ""}</td></tr>' for x in lay["读数"])
    return (f'<div class="tw"><table><thead><tr><th class="l">{T("指标", "Indicator")}</th><th>{T("读数", "Reading")}</th><th class="l">{T("区间", "Zone")}</th>'
            f'<th class="l">{T("依据", "Basis")}</th><th>{T("数据日", "Data date")}</th></tr></thead>'
            f'<tbody>{trs or "<tr><td class=l colspan=5>" + T("数据不足", "No data") + "</td></tr>"}</tbody></table></div>')


def old_note(obj):
    if obj.get("版本") == 2:
        return ""
    if LANG["v"] == "en":
        return '<div class="note">This entry was written before bilingual logs (and under the pre-2026-10-02 L1 rules), so it is shown in Chinese.</div>'
    if obj.get("类型") == "日":
        return '<div class="note">本篇按 2026-10-02 之前的旧 L1 规则写成，按冻结规则保持原样；规则变更见「更正记录」。</div>'
    return ""


def build_journal(S, logs, weeks, months, sd):
    idx = {lg["日期"]: i for i, lg in enumerate(logs)}
    for lg in logs:
        i = idx[lg["日期"]]
        prev_ = logs[i - 1]["日期"] if i > 0 else None
        next_ = logs[i + 1]["日期"] if i + 1 < len(logs) else None
        layers = ""
        for lay in lg["层"]:
            layers += f'<h3>L{lay["层"]} · {esc(LF(lay, "名称"))} {tone_chip(LF(lay, "结论"), lay["tone"])}</h3>{readings_table(lay)}'
        lp = lg.get("发射台") or {}
        lp_html = ""
        if lp:
            trs = "".join(f'<tr><td class="l">{esc(t["名称"])}</td><td class="l">{chain_badge(t["链"])}</td><td>{f_usd(t["当日"])}</td>'
                          f'<td>{fmt_delta(t["日环比"], pct_input=True)}</td><td>{R.f_pct(t["份额"], 1)}</td></tr>' for t in lp.get("Top") or [])
            lp_html = (f'<h2>{T("发射台", "Launchpads")} <span class="sub">{lp.get("日期")} · Top60 {f_usd(lp.get("赛道当日"))} '
                       f'{fmt_delta(lp.get("赛道日环比"), pct_input=True)}</span></h2>'
                       f'<div class="tw"><table><thead><tr><th class="l">{T("平台", "Platform")}</th><th class="l">{T("链", "Chain")}</th><th>{T("当日手续费", "Fees")}</th>'
                       f'<th>{T("日环比", "DoD")}</th><th>{T("赛道份额", "Share")}</th></tr></thead>'
                       f'<tbody>{trs}</tbody></table></div>' + (f'<p class="tnote">{esc(lp.get("一句话") or "")}</p>' if LANG["v"] == "zh" else ""))
        cm = commentary(lg["日期"])
        srcs = "".join(tone_chip(f'{k} {"✓" if v.get("ok") else "✗"}', "up" if v.get("ok") else "dn") for k, v in (lg.get("数据源") or {}).items())
        miss = f'<p class="tnote">{T("当天缺失的核心指标：", "Core indicators missing that day: ")}{esc("、".join(lg["核心缺失"]))}</p>' if lg.get("核心缺失") else ""
        patch = (f'<p class="tnote">⚠ {T("本篇为补录：首次生成于", "Re-run: first generated")} {esc(lg.get("首次生成UTC") or "")} UTC'
                 f'{T("，当天数据源晚到后按冻结规则覆盖一次。", ", overwritten once after late data per the freeze rule.")}</p>') if lg.get("补录") else ""
        heroes, cards = hero_cards(S, lg["日期"], sd if lg is logs[-1] else None)
        share_obj = {"title": T(f"链上终端 · {lg['日期']} 解读", f"Onchain terminal · {lg['日期']}"), "date": lg["日期"], "sub": LF(lg["综合"], "一句话"),
                     "html": share_payload_home(lg, cards), "file": f"uncleonchain-journal-{lg['日期']}.png"}
        no_cm = '<div class="empty">' + T("今天没有人工点评，上面是规则化自动解读。", "No hand-written note today; the above is rule-based.") + '</div>'
        pager_prev = f'<a href="{U("/journal/" + prev_ + "/")}">← {prev_}</a>' if prev_ else '<span></span>'
        pager_next = f'<a href="{U("/journal/" + next_ + "/")}">{next_} →</a>' if next_ else '<span></span>'
        body = f"""{crumbs([(T("解读日志", "Journal"), "/journal/"), (lg["日期"], None)])}
<div class="ph"><div><div class="eyebrow">Daily Log · {T("每日解读", "daily")}</div><h1>{lg["日期"]} {T("解读日志", "log")}</h1></div>
<div class="stamp">{T("生成于", "Generated")} <b>{esc(lg["生成时间UTC"])} UTC</b><br>{T("写入即冻结 · 规则见「口径与规则」", "Frozen once written · rules in Methodology")}</div></div>
{old_note(lg)}
{verdict_block(lg, link=False)}
{patch}
<h2>{T("大叔点评", "Uncle's note")}</h2>{f'<div class="cmt article">{cm}</div>' if cm else no_cm}
<h2>{T("异动预警", "Alerts")}</h2>{alert_board(lg, title=T("当日预警", "Alerts of the day"), share_id="shareLog")}
<h2>{T("四层读数", "Four-layer readings")}</h2>{layers}
{miss}
{lp_html}
<h2>{T("数据源状态", "Data sources")}</h2><div class="src">{srcs}</div>
<div class="pager">{pager_prev}<a href="{U("/journal/")}">{T("全部日志", "All logs")}</a>{pager_next}</div>"""
        js = f"<script>function shareLog(){{ucShare({json.dumps(share_obj, ensure_ascii=False)})}}</script>"
        emit(f'journal/{lg["日期"]}/index.html', f'{lg["日期"]} {T("解读日志", "log")} · {T(BRAND, BRAND_EN)}', body, active="journal", share=True,
             scripts=js, desc=LF(lg["综合"], "一句话"))

    def review_page(rv, kind_slug, title):
        rows = "".join(f'<tr><td class="l">{esc(LF(x, "名称"))}</td><td>{esc(x["期初"])}</td><td>{esc(x["期末"])}</td><td>{esc(x["变化"])}</td>'
                       f'<td>{esc(x["低"])} ~ {esc(x["高"])}</td><td class="l">{esc(short_zone(LF(x, "期初区间")))} → {tone_chip(short_zone(LF(x, "期末区间")), x["tone"])}</td></tr>'
                       for x in rv["指标"])
        vrows = "".join(f'<tr><td class="l">L{v["层"]} · {esc(LF(v, "名称"))}</td><td class="l">{esc(v["期初"])} → {esc(v["期末"])}</td>'
                        f'<td class="l wrap">{esc("、".join(f"{k}×{n}" for k, n in v["分布"].items()) or "—")}</td>'
                        f'<td>{v["切换次数"]}</td></tr>' for v in rv["结论"])
        al = "".join(f'<li><span class="d">{a["日期"][5:]}</span><span class="lv {"h" if a["级别"] == "高" else "m"}">{T(a["级别"], "H" if a["级别"] == "高" else "M")}</span>{esc(LF(a, "文本"))}</li>' for a in rv["预警"])
        lp = rv.get("发射台") or {}
        prow = "".join(f'<tr><td class="l">{esc(p["名称"])}</td><td>{f_usd(p["期间"])}</td><td>{f_usd(p["上期"])}</td>'
                       f'<td>{fmt_delta(p["变化"], pct_input=True)}</td></tr>' for p in lp.get("平台") or [])
        cm = commentary(rv["标签"])
        no_cm = '<div class="empty">' + T("人工复盘点评待补充（content/journal/" + esc(rv["标签"]) + ".md）。", "No hand-written review yet.") + '</div>'
        no_al = '<div class="empty">' + T("期间没有触发预警。", "No alerts.") + '</div>'
        return f"""{crumbs([(T("解读日志", "Journal"), "/journal/"), (title, None)])}
<div class="ph"><div><div class="eyebrow">{kind_slug.title()} Review</div><h1>{esc(title)}</h1>
<p class="lede">{rv["起"]} ~ {rv["止"]} · {T("期间日志", "logs")} {rv["日志天数"]} {T("篇", "")}</p></div><div class="stamp">{T("生成于", "Generated")} <b>{esc(rv["生成时间UTC"])} UTC</b></div></div>
{old_note(rv)}
<div class="glass verdict"><div class="body"><div class="lbl">{T("一句话复盘", "Summary")}</div><div class="txt">{esc(LF(rv, "一句话"))}</div></div></div>
<h2>{T("大叔点评", "Uncle's note")}</h2>{f'<div class="cmt article">{cm}</div>' if cm else no_cm}
<h2>{T("核心指标区间变化", "Core indicators over the period")}</h2><div class="tw"><table><thead><tr><th class="l">{T("指标", "Indicator")}</th><th>{T("期初", "Start")}</th><th>{T("期末", "End")}</th><th>{T("变化", "Change")}</th><th>{T("区间低 ~ 高", "Low ~ high")}</th><th class="l">{T("区间判定", "Zone")}</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>{T("各层结论分布", "Verdicts by layer")}</h2><div class="tw"><table><thead><tr><th class="l">{T("层", "Layer")}</th><th class="l">{T("期初 → 期末", "Start → end")}</th><th class="l">{T("分布（天数）", "Distribution (days)")}</th><th>{T("切换次数", "Switches")}</th></tr></thead><tbody>{vrows}</tbody></table></div>
<h2>{T("发射台", "Launchpads")} <span class="sub">Top60 {f_usd(lp.get("赛道期间合计"))} · {T("较上期", "vs prior")} {fmt_delta(lp.get("赛道变化"), pct_input=True)}</span></h2>
<div class="tw"><table><thead><tr><th class="l">{T("平台", "Platform")}</th><th>{T("期间手续费", "Fees")}</th><th>{T("上期", "Prior")}</th><th>{T("变化", "Change")}</th></tr></thead><tbody>{prow}</tbody></table></div>
<h2>{T("期间预警", "Alerts")}（{len(rv["预警"])}）</h2>{f'<div class="card"><ul class="alerts">{al}</ul></div>' if al else no_al}"""

    for wk in weeks:
        t_ = T(f'{wk["标签"]} 周复盘', f'{wk["标签"]} weekly review')
        emit(f'journal/week/{wk["标签"]}/index.html', f'{t_} · {T(BRAND, BRAND_EN)}', review_page(wk, "week", t_), active="journal", desc=LF(wk, "一句话"))
    for mo in months:
        t_ = T(f'{mo["标签"]} 月复盘', f'{mo["标签"]} monthly review')
        emit(f'journal/month/{mo["标签"]}/index.html', f'{t_} · {T(BRAND, BRAND_EN)}', review_page(mo, "month", t_), active="journal", desc=LF(mo, "一句话"))
    dl = "".join(f'<li><span class="d">{lg["日期"]}</span><span><a href="{U("/journal/" + lg["日期"] + "/")}">{esc(LF(lg["综合"], "一句话"))}</a>'
                 f'<span class="s">{" ".join(tone_chip(LF(x, "短"), x["tone"]) for x in lg["层"])}</span></span>'
                 f'<span class="x chip">{len(lg.get("预警") or [])} {T("预警", "alerts")}</span></li>' for lg in reversed(logs))
    wl = "".join(f'<li><span class="d">{w["标签"]}</span><span><a href="{U("/journal/week/" + w["标签"] + "/")}">{esc(LF(w, "一句话"))}</a>'
                 f'<span class="s">{w["起"]} ~ {w["止"]}</span></span></li>' for w in reversed(weeks))
    ml = "".join(f'<li><span class="d">{m["标签"]}</span><span><a href="{U("/journal/month/" + m["标签"] + "/")}">{esc(LF(m, "一句话"))}</a></span></li>' for m in reversed(months))
    e1 = '<div class="empty">' + T("第一篇月复盘会在下个月 1 日自动生成。", "The first monthly review comes on the 1st.") + '</div>'
    e2 = '<div class="empty">' + T("第一篇周复盘会在下周一自动生成。", "The first weekly review comes next Monday.") + '</div>'
    e3 = '<div class="empty">' + T("第一篇日志会在下一次每日运行时写入。", "The first log comes with the next daily run.") + '</div>'
    body = f"""<div class="ph"><div><div class="eyebrow">Journal</div><h1>{T("解读日志", "Journal")}</h1>
<p class="lede">{T("每天 UTC 10:20 自动拉数后，按「口径与规则」里公开的区间规则写一篇解读日志：四层读数、各层结论、综合研判、发射台、异动预警。<b>写入即冻结</b>——历史日志不改，唯一例外是当天数据源晚到、重跑后核心缺失变少，会覆盖一次并标「补录」。每周一自动出上一周的周复盘，每月 1 日出上个月的月复盘。大叔的人工点评单独标注，和自动解读分开。",
                   "Every day at 10:20 UTC a rule-based log is written from the public rules in Methodology: four-layer readings, verdicts, launchpads and alerts. <b>Frozen once written</b> — the only exception is a same-day re-run with fewer missing core inputs, marked 'Re-run'. Weekly reviews come out on Mondays, monthly ones on the 1st. Hand-written notes are kept separate.")}</p></div></div>
<h2>{T("月复盘", "Monthly reviews")}</h2>{f'<div class="card"><ul class="list">{ml}</ul></div>' if ml else e1}
<h2>{T("周复盘", "Weekly reviews")}</h2>{f'<div class="card"><ul class="list">{wl}</ul></div>' if wl else e2}
<h2>{T("每日解读", "Daily logs")}</h2>{f'<div class="card"><ul class="list">{dl}</ul></div>' if dl else e3}"""
    emit("journal/index.html", T(f"解读日志 · {BRAND}", f"Journal · {BRAND_EN}"), body, active="journal",
         desc=T("每日规则化解读 + 周复盘 + 月复盘，写入即冻结，公开可查。", "Daily rule-based logs plus weekly and monthly reviews, frozen once written."))


# ---------------------------------------------------------------- 口径 / 更正 / 关于
L1_RULES_ZH = """<p style="margin:0 0 8px"><b style="color:var(--ink)">L1 宏观流动性</b>（2026-10-02 起，依据《BTC 全周期宏观相关性与归因研究》）：L1 管周到月的波动、节奏和风险预算，不管方向。</p>
<ul style="margin:0 0 10px;padding-left:20px"><li><b>顺风</b>：乐观度 z &gt; 0 且 BAA 信用利差 13 周收窄，实际利率没有急升。</li>
<li><b>中性偏谨慎</b>：实际利率急升（13 周 ≥ +0.40pp）单独出现——框架里风险预算降一档、不加仓。</li>
<li><b>逆风</b>：实际利率急升 且（BAA / NFCI 13 周转紧 或 乐观度 z &lt; 0），或流动性闸门触发（净流动性 13 周 ≤ −2.72% 且美元 13 周走强）——框架里名义风险预算 ×0.7，两项不叠乘。</li>
<li><b>中性</b>：其余情况。高收益利差 13 周走阔 ≥ 0.30pp 时加「警戒」（先行提示，本站阈值，未经回测）。</li></ul>
<p style="margin:0 0 8px"><b>L1-B 加密资金通道（只确认、不预测）</b>：稳定币主线（去重 = 总量 − 支付/机构 − 生息/合成）、交易子弹（剔除 Tron，并列含 Tron 口径）、现货 ETF（趋势确认，滞后）、期货升水（CME 与 Deribit 并列）和资金轮动矩阵（ETF 13 周 × 交易子弹 13 周：共振 / 换手 / 承接 / 双撤）。和价格同向 = 确认，背离 = 提示，不进档位判定。</p>
<p style="margin:0 0 8px">证据等级：已验证 &gt; 已验证·方向 &gt; 描述读数 &gt; 监控；只有「已验证」的指标可以直接影响仓位参数，其余只做记录。13 周变化统一按周五收盘对齐（取当周最后可得值）。阈值只用 2018 年以后的数据定。</p>"""
L1_RULES_EN = """<p style="margin:0 0 8px"><b style="color:var(--ink)">L1 Macro liquidity</b> (since 2026-10-02, based on the BTC full-cycle macro attribution study): L1 sets volatility, pacing and risk budget over weeks to months, not direction.</p>
<ul style="margin:0 0 10px;padding-left:20px"><li><b>Tailwind</b>: optimism z &gt; 0 and the BAA spread narrowing over 13 weeks, with no real-yield surge.</li>
<li><b>Neutral-cautious</b>: a real-yield surge (13w ≥ +0.40pp) on its own — one notch less risk budget, no adds.</li>
<li><b>Headwind</b>: a surge plus (BAA/NFCI tightening or optimism z &lt; 0), or the liquidity gate (net liquidity 13w ≤ −2.72% with a stronger dollar) — nominal risk budget ×0.7, not compounded.</li>
<li><b>Neutral</b>: everything else. An 'alert' tag is added when the high-yield spread widens ≥ 0.30pp over 13 weeks (early warning; this site's threshold, not back-tested).</li></ul>
<p style="margin:0 0 8px"><b>L1-B crypto funding channels (confirm, don't predict)</b>: stablecoin main line (de-dup = total − payment − yield/synthetic), trading bullets (ex-Tron, with an incl.-Tron lens), spot ETFs (trend confirmation, lagging), futures basis (CME and Deribit side by side) and the rotation matrix (ETF 13w × trading bullets 13w). Agreement with price confirms, divergence warns; not part of the regime verdict.</p>
<p style="margin:0 0 8px">Evidence grades: verified &gt; verified·direction &gt; descriptive &gt; monitor; only verified gauges may move position parameters. 13-week changes are aligned to Friday closes. Thresholds use post-2018 data only.</p>"""
LP_RULES = {
    "zh": [("统计口径", "发射台一律用手续费（fees），不用成交量；成交量口径覆盖不全，会系统性低估份额。"),
           ("统计周期", "只报「昨天」这一个 UTC 完整日；当天数据永远不完整，不进正文。"),
           ("发射台矩阵", "DefiLlama Launchpad 类目全部协议；多链协议的分链数字用 DefiLlama 分链拆分；汇总趋势用 Top60 逐日手续费（2024-01 起）。"),
           ("份额", "排行榜的份额条 = 该协议占当前筛选范围（链 × 周期 × 金额档）合计的百分比；深度追踪平台的份额分母是 Top60 当日总量。"),
           ("延迟处理", "某个数据源没出昨天的数，标「延迟」，不拿旧值顶替、不记 0。"),
           ("Flap / StonkFun", "Flap 是税代币模型、StonkFun 的 fees 只记平台自己那份，跨平台比较用协议收入。"),
           ("PONS 销毁", "转到 0x…dEaD 地址，不是调用 burn()，市值一律按 burn-adjusted 流通计。"),
           ("绝不做的事", "不拿历史峰值和现在比来判断一个平台是否「死了」；只给数据，不给买卖建议。")],
    "en": [("Measure", "Launchpads are always compared by fees, never volume (volume coverage is incomplete and understates share)."),
           ("Period", "Only 'yesterday' as a full UTC day is reported; today's data is never complete."),
           ("Matrix", "All protocols in DefiLlama's Launchpad category, split by chain with DefiLlama's per-chain data; the sector trend uses daily top-60 fees since 2024-01."),
           ("Share", "Share bars = % of the filtered total (chain × period × tier); deep-tracked share uses the top-60 daily total."),
           ("Late data", "A source that has not published yesterday is marked late — never back-filled with old values or zero."),
           ("Flap / StonkFun", "Flap is a tax-token model and StonkFun fees count only the platform's cut; compare them by revenue."),
           ("PONS burns", "Sent to 0x…dEaD rather than burn(); market cap is always burn-adjusted."),
           ("Never", "No 'it's dead' calls from comparing with all-time peaks; data only, no trade advice.")],
}


def build_methodology():
    lp_rows = "".join(f"<tr><td class='l'>{esc(k)}</td><td class='l wrap'>{esc(v)}</td></tr>" for k, v in LP_RULES[LANG["v"]])
    macro = ""
    for i, meta in R.LAYERS.items():
        trs = ""
        for ind in [x for x in R.INDICATORS if x["层"] == i]:
            zones = "；".join(f"{T(c[1], c[2])}" + ("" if c[0] is None else f" < {R.FMT[ind['fmt']](c[0])}") for c in ind["cuts"])
            if ind["key"] in OWN_PCT:
                zones = T("自身历史分位：<20 低位 / 20–80 中段 / >80 高位（满 90 天）", "own-history percentile: <20 low / 20–80 mid / >80 high (after 90 days)")
            trs += (f"<tr><td class='l'><a href='{ind_href(ind['key'])}'><b>{esc(T(ind['名称'], ind['EN']))}</b></a><br><span class='stamp' style='text-align:left'>{esc(ind['来源'])}</span></td>"
                    f"<td class='l'>{esc(T(ind['级别'], LEVEL_EN.get(ind['级别'], '')))}{('<br>' + grade_chip(ind.get('等级'))) if ind.get('等级') else ''}</td>"
                    f"<td class='l wrap'>{esc(T(ind['说明'], ind['说明EN']))}</td>"
                    f"<td class='l wrap'>{T('按', 'By ')}{esc(T(ind['依据'], ind['依据EN']))}：{esc(zones)}</td></tr>")
        macro += (f"<h3>L{i} · {esc(T(meta['名称'], meta['EN']))}（{esc(T(meta['问'], meta['问EN']))}？）</h3><div class='tw'><table><thead><tr><th class='l'>{T('指标', 'Indicator')}</th>"
                  f"<th class='l'>{T('级别 / 证据', 'Level / evidence')}</th><th class='l'>{T('怎么读', 'How to read')}</th><th class='l'>{T('区间规则', 'Zones')}</th></tr></thead><tbody>{trs}</tbody></table></div>")
    pend = "".join(f"<tr><td class='l'>L{p['层']}</td><td class='l'>{esc(T(p['名称'], p['EN']))}</td><td class='l wrap'>{esc(T(p['原因'], p['原因EN']))}</td></tr>" for p in R.PENDING)
    banned = "".join(f"<tr><td class='l wrap'>{esc(T(a, b))}</td><td class='l wrap'>{esc(T(c, d))}</td></tr>" for a, b, c, d in R.BANNED)
    body = f"""{crumbs([(T("口径与规则", "Methodology"), None)])}<h1>{T("口径与规则", "Methodology")}</h1>
<p class="lede">{T("解读日志里的每一个判断都来自下面这些公开规则。规则改动会在更正记录里留痕，历史日志不跟着改。", "Every judgement in the logs comes from the public rules below. Rule changes are logged in Corrections; past logs are never rewritten.")}</p>
<h2>{T("层结论怎么来", "How layer verdicts are made")}</h2>
<div class="card" style="padding:16px 20px;font-size:13.5px;color:var(--ink2)">
{T(L1_RULES_ZH, L1_RULES_EN)}
<p style="margin:0 0 8px"><b style="color:var(--ink)">L2 {T("周期", "Cycle")}</b>：{T("以 MVRV Z-Score 所在区间为周期位置（缺失时退回 MVRV）。NUPL、Realized Price 与 MVRV 同源，只展示不重复计分。", "Cycle position = the MVRV Z-Score zone (MVRV as fallback). NUPL and realized price share its source and are not scored twice.")}</p>
<p style="margin:0 0 8px"><b style="color:var(--ink)">L3 {T("筹码", "Coin flows")}</b>：{T("以交易所 BTC 7 日净流量为准：净流出 = 筹码离开交易所，净流入 = 留意抛压。交易所余额 30 日变化只展示趋势。", "Based on 7-day exchange net flow: outflow = coins leaving, inflow = watch selling. Exchange balance change is shown as trend only.")}</p>
<p style="margin:0"><b style="color:var(--ink)">L4 {T("情绪", "Sentiment")}</b>：{T("恐慌贪婪（−2~+2）、资金费率（−1~+2）、未平仓 7 日变化（−1~+1）合计 ≥3 过热、1~2 偏热、≤−2 偏冷，其余中性。", "Fear & greed (−2..+2), funding (−1..+2) and 7-day OI change (−1..+1): ≥3 hot, 1–2 warm, ≤−2 cool, otherwise neutral.")}</p></div>
<h2>{T("异动预警阈值", "Alert thresholds")}</h2>
<div class="card" style="padding:16px 20px;font-size:13.5px;color:var(--ink2)">{T("核心指标区间切换 · L1 档位切换 · 交易所单日 BTC 净流量 ≥ 5,000 枚 · 资金费率正负翻转 · VIX 穿越 20 · Pi Cycle Top 触发 · 发射台赛道单日 ±25% · 发射台当日第一易主 · 深度追踪平台日环比超 ±60%。",
                                                                                      "Core zone changes · L1 regime change · ≥5,000 BTC exchange net flow in a day · funding sign flip · VIX crossing 20 · Pi Cycle Top trigger · launchpad sector ±25% in a day · new #1 launchpad · deep-tracked platform ±60% DoD.")}</div>
<h2>{T("宏观四层 · 指标与区间", "Indicators and zones")}</h2>{macro}
<h2>{T("研究里测过、不再使用的说法", "Claims tested and dropped")}</h2><div class="tw"><table><thead><tr><th class="l">{T("说法", "Claim")}</th><th class="l">{T("原因", "Why")}</th></tr></thead><tbody>{banned}</tbody></table></div>
<h2>{T("框架里暂未接入的指标", "Not yet connected")}</h2><div class="tw"><table><thead><tr><th class="l">{T("层", "Layer")}</th><th class="l">{T("指标", "Indicator")}</th><th class="l">{T("原因 / 计划", "Reason / plan")}</th></tr></thead><tbody>{pend}</tbody></table></div>
<h2>{T("解读日志规则", "Log rules")}</h2>
<div class="card" style="padding:16px 20px;font-size:13.5px;color:var(--ink2)">{T("日志日期 = 解读当天（UTC），每个读数带自己的数据日期（FRED 按美国工作日、NFCI 周度、交易所余额约有 2 周滞后，超过容忍天数标 ⚠）。写入即冻结；同一天重跑且核心缺失变少才覆盖一次并标「补录」。周复盘按 ISO 周（周一至周日），月复盘按自然月。人工点评放在 content/journal/，单独标注。",
                                                                                   "Log date = UTC day of the run; each reading carries its own data date (FRED on US business days, NFCI weekly, exchange balance ~2 weeks late; stale readings get ⚠). Frozen once written; a same-day re-run only overwrites when fewer core inputs are missing, marked 'Re-run'. Weekly reviews follow ISO weeks, monthly ones calendar months.")}</div>
<h2>{T("发射台口径", "Launchpad conventions")}</h2><div class="tw"><table><tbody>{lp_rows}</tbody></table></div>"""
    emit("methodology/index.html", T(f"口径与规则 · {BRAND}", f"Methodology · {BRAND_EN}"), body, active="methodology")


def build_corrections(sd, fixes):
    rows = "".join(f"<tr><td class='l'>{esc(f['日期'])}</td><td>{f['旧值']:,.0f} → {f['新值']:,.0f}</td>"
                   f"<td class='l'>{esc(f.get('口径', ''))}</td><td>{esc(f['修正时间UTC'][:10])}</td></tr>"
                   for f in sorted(fixes, key=lambda x: x["日期"], reverse=True)[:60])
    rule_rows = "".join(f"<tr><td class='l'>{esc(c['日期'])}</td><td class='l'>{esc(T(c['范围'], c['EN范围']))}</td><td class='l wrap'>{esc(T(c['内容'], c['EN']))}</td></tr>"
                        for c in R.RULE_CHANGES)
    rev = [a for a in (sd or {}).get("异常", []) if "修订" in a or "延迟" in a]
    rn = (f"<h2>{T('近期数据源变动', 'Recent data-source changes')}</h2><div class='card'><ul class='alerts'>" + "".join(f"<li>{esc(a)}</li>" for a in rev) + "</ul></div>") if rev else ""
    none_ = '<tr><td class="l" colspan="4">' + T("暂无", "None") + '</td></tr>'
    body = f"""{crumbs([(T("更正记录", "Corrections"), None)])}<h1>{T("更正记录", "Corrections")}</h1>
<p class="lede">{T("数据源事后修订、PONS 销毁口径重算、规则调整，全部留痕，不覆盖不删除。", "Source revisions, PONS burn recalculations and rule changes — all logged, nothing overwritten.")}</p>
<h2>{T("规则变更", "Rule changes")}</h2><div class="tw"><table><thead><tr><th class="l">{T("日期", "Date")}</th><th class="l">{T("范围", "Scope")}</th><th class="l">{T("内容", "Change")}</th></tr></thead><tbody>{rule_rows}</tbody></table></div>
{rn}
<h2>{T("PONS 逐日销毁重算记录", "PONS daily burn recalculations")}</h2><div class="tw"><table><thead><tr><th class="l">{T("日期", "Date")}</th><th>{T("旧值 → 新值", "Old → new")}</th><th class="l">{T("口径", "Basis")}</th><th>{T("修正时间", "Fixed")}</th></tr></thead>
<tbody>{rows or none_}</tbody></table></div>"""
    emit("corrections/index.html", T(f"更正记录 · {BRAND}", f"Corrections · {BRAND_EN}"), body, active="corrections")


def build_about():
    txt = T(f"""<p>写这个站的人在 web3 做了快十年，做过项目运营、产品设计，也做过 AMM DEX。现在把自己的研究方式搬到台面上：
先看宏观环境给多少风险预算，再看周期位置（贵不贵），再看筹码结构（谁在进出交易所），再看情绪（会不会超调），最后落到发射台一级市场——每天赚多少钱、钱从哪来。</p>
<p>所有判断都按公开规则自动生成，每天一篇解读日志，写入即冻结；每周、每月再复盘一次；系统性的研究整理成分析报告。对了错了都留在这里，不做事后诸葛亮。</p>
<p>{esc(DISCLAIMER)}</p>""", f"""<p>The author has spent close to ten years in web3 — operations, product design and an AMM DEX. This site puts the research process in public:
first how much risk budget the macro backdrop allows, then the cycle (cheap or expensive), coin flows (who is moving coins on and off exchanges), sentiment (is it overshooting), and finally the launchpad primary market — how much money is made every day and where it comes from.</p>
<p>Every judgement is generated from public rules; one log per day, frozen once written; weekly and monthly reviews; deeper research as reports. Right or wrong, it all stays here.</p>
<p>{esc(DISCLAIMER_EN)}</p>""")
    body = f"""{crumbs([(T("关于", "About"), None)])}<div class="eyebrow">About</div>
<div style="display:flex;gap:18px;align-items:center;margin-top:8px"><img src="/assets/favicon-192.png" alt="" style="width:84px;height:84px;border-radius:50%;box-shadow:0 0 0 2px var(--lime)">
<div><h1>{T("关于" + BRAND, "About " + BRAND_EN)}</h1><p class="stamp" style="text-align:left">{esc(DOMAIN)} · <a href="{X_URL}">{esc(TWITTER)}</a></p></div></div>
<div class="article" style="margin-top:22px">{txt}</div>"""
    emit("about/index.html", T(f"关于 · {BRAND}", f"About · {BRAND_EN}"), body, active="about", narrow=True)


def build_404():
    emit("404.html", T(f"页面不存在 · {BRAND}", f"Not found · {BRAND_EN}"),
         f'<h1>{T("页面不存在", "Page not found")}</h1><p class="lede">{T("链接可能过期了，回", "The link may be outdated. Back to the ")}<a href="{U("/")}">{T("终端总览", "overview")}</a>{T("看看。", ".")}</p>')


def build_misc(logs, weeks, months):
    os.makedirs(os.path.join(SITE, "assets"), exist_ok=True)
    for k, v in ASSET_SRC.items():
        with open(os.path.join(SITE, "assets", k), "w", encoding="utf-8") as fh:
            fh.write(v)
    write("_headers", HEADERS)
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: https://{DOMAIN}/sitemap.xml\n")
    urls = ["/", "/macro/", "/launchpad/", "/rotation/", "/narrative/", "/reports/", "/journal/", "/methodology/", "/corrections/", "/about/",
            "/launchpad/report/", "/launchpad/report/archive/"]
    urls += [f"/macro/{x['key']}/" for x in R.INDICATORS]
    for p in PILLARS:
        urls += [f'/{p["slug"]}/{x["slug"]}/' for x in ALL_POSTS[p["slug"]]]
    urls += [f'/reports/{r["slug"]}/' for r in ALL_REPORTS]
    rd = os.path.join(SITE, "launchpad", "report")
    if os.path.isdir(rd):
        urls += [f"/launchpad/report/{d}/" for d in os.listdir(rd) if re.match(r"^\d{4}-\d{2}-\d{2}$", d)]
    pd_ = os.path.join(SITE, "launchpad", "platforms")
    if os.path.isdir(pd_):
        urls += [f"/launchpad/platforms/{d}/" for d in os.listdir(pd_)]
    urls += [f'/journal/{x["日期"]}/' for x in logs] + [f'/journal/week/{x["标签"]}/' for x in weeks] + [f'/journal/month/{x["标签"]}/' for x in months]
    allu = sorted(set(urls))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "".join(f"<url><loc>https://{DOMAIN}{u}</loc></url>\n<url><loc>https://{DOMAIN}/en{u}</loc></url>\n" for u in allu) + "</urlset>\n")
    write("sitemap.xml", xml)
    os.makedirs(os.path.join(SITE, "assets"), exist_ok=True)
    for f in ("favicon.ico", "favicon-32.png", "favicon-192.png", "apple-touch-icon.png", "avatar-96.png", "og.png"):
        src = os.path.join(ASSETS, f)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(SITE, "assets", f))
    vd = os.path.join(ASSETS, "vendor")
    if os.path.isdir(vd):
        os.makedirs(os.path.join(SITE, "assets", "vendor"), exist_ok=True)
        for f in os.listdir(vd):
            shutil.copyfile(os.path.join(vd, f), os.path.join(SITE, "assets", "vendor", f))
    shutil.copyfile(os.path.join(ASSETS, "favicon.ico"), os.path.join(SITE, "favicon.ico"))
    old = os.path.join(SITE, "favicon.svg")
    if os.path.exists(old):
        os.remove(old)
    write("CNAME", DOMAIN + "\n")


def main():
    sd = load(os.path.join(BUILD, "网站素材.json"))
    if not sd:
        print(f"⛔ 没找到 {os.path.join(BUILD, '网站素材.json')}，先跑 出看板.py")
        sys.exit(1)
    L, S = load_macro()
    logs, weeks, months = load_logs("日"), load_logs("周"), load_logs("月")
    rot = load(os.path.join(DATA, "板块台账.json"), {}) or {}
    matrix = load(os.path.join(DATA, "发射台矩阵.json"))
    fixes = load(os.path.join(DATA, "销毁修正记录.json"), []) or []
    G["今天"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    G["更新"] = (L.get("更新时间UTC") or sd.get("生成时间UTC") or "")[:16].replace("T", " ")
    os.makedirs(SITE, exist_ok=True)
    # 走势数据（两种语言共用）先写；旧版本留下的 data/ 整个清掉重写，避免残留过期文件
    shutil.rmtree(os.path.join(SITE, "data"), ignore_errors=True)
    files = write_indicator_data(S)
    copy_report_files()
    for lang in ("zh", "en"):
        LANG["v"] = lang
        build_home(sd, S, logs, weeks, months, rot, matrix)
        build_macro(L, S, logs)
        build_indicator_pages(L, S, logs, files)
        build_launchpad(sd, matrix)
        build_launchpad_platforms(sd)
        build_launchpad_report(sd)
        build_rotation(rot)
        build_narrative()
        build_posts()
        build_reports()
        build_journal(S, logs, weeks, months, sd)
        build_methodology()
        build_corrections(sd, fixes)
        build_about()
        build_404()
    LANG["v"] = "zh"
    build_misc(logs, weeks, months)
    n = sum(1 for _, _, fs in os.walk(SITE) for f in fs if f == "index.html")
    print(f"网站已生成到 {SITE}（{n} 个页面，中英各一套；日志 {len(logs)} 篇、周复盘 {len(weeks)}、月复盘 {len(months)}、报告 {len(ALL_REPORTS)}）")


if __name__ == "__main__":
    main()
