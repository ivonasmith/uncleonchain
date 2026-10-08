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


class _CN:
    """全角 / 半角冒号按当前语言输出（英文站不留全角标点）。"""
    def __format__(self, spec):
        return "：" if LANG["v"] == "zh" else ": "


CN = _CN()
SRC_REP = [("（逐币 + Tron 链）", " (per coin + Tron)"), ("（逐币）", " (per coin)"), ("（自算）", " (own calc)"), ("（l2_daily.py）", " (l2_daily.py)"),
           ("（flash 口径）", " (flash)"), ("（周度）", " (weekly)"), ("（每天抓一次）", " (fetched once a day)"), ("CME 近月合约", "CME front month"),
           ("（前后两张插值成固定 90 天）", " (two contracts interpolated to 90 days)"), ("（日均年化）", " (daily avg, annualized)"),
           ("（haturatu 镜像）", " (haturatu mirror)"), ("（按链）", " (by chain)"), ("类目快照", "category snapshot")]


def src_t(x):
    if LANG["v"] == "zh" or not x:
        return x
    for a, b in SRC_REP:
        x = x.replace(a, b)
    return x


def has_cjk(t):
    return bool(re.search(r"[\u4e00-\u9fff]", t or ""))


SHORT_EN = {"流动性收缩": "Liquidity contracting", "周期偏低": "Cycle low", "筹码流出交易所": "Coins leaving exchanges", "情绪偏热": "Sentiment warm"}  # 日志里的层结论短语 → 英文（英文站展示旧日志 / 复盘时替换用，只改显示不改文件）


def en_fix(t):
    """英文站：把还夹着中文短语的冻结文本里能对上的短语换成英文；对不上的整句标「仅中文」。"""
    if LANG["v"] == "zh" or not t or not has_cjk(t):
        return t
    for zh in sorted(SHORT_EN, key=len, reverse=True):
        t = t.replace(zh, SHORT_EN[zh])
    return t if not has_cjk(t) else None


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
CHANGELOG = load(os.path.join(ROOT, "content", "changelog.json"), []) or []
CL_TYPE = {"new": ("新功能", "New"), "improve": ("改进", "Improved"), "fix": ("修复", "Fixed"), "data": ("数据口径", "Data")}


def nav_html(active):
    def link(k, href, zh, en):
        tag = f'<span class="ntag">{T("筹备中", "soon")}</span>' if k == "narrative" else ""
        return f'<a href="{U(href)}" class="{"on" if k == active else ""}">{icon(k)}{esc(T(zh, en))}{tag}</a>'
    main = "".join(link(*x) for x in NAV_MAIN)
    more = "".join(link(*x) for x in NAV_MORE)
    ver = CHANGELOG[0]["version"] if CHANGELOG else ""
    more += (f'<button type="button" class="navbtn" data-guide>{icon("about")}{T("新手说明", "Guide")}</button>'
             f'<a href="{U("/changelog/")}" class="{"on" if active == "changelog" else ""}">{icon("journal")}{T("更新日志", "Changelog")}'
             f'<span class="ver">v{esc(ver)}</span><i class="rdot" hidden></i></a>')
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
<a href="{X_URL}" target="_blank" rel="noopener">𝕏 {esc(TWITTER)}</a> <a class="sfb" href="#" data-feedback>✎ {T('反馈 / 纠错', 'Feedback')}</a><p>{esc(T(DISCLAIMER, DISCLAIMER_EN))}</p></div>
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
<footer class="foot"><span>{esc(T(BRAND + "（" + BRAND_EN + "）", BRAND_EN))}</span><a href="{X_URL}">{esc(TWITTER)}</a>
<span>{T('本站数据来源', 'Data sources')}{CN}DefiLlama · CoinMetrics · bitview.space · FRED · Farside · Yahoo · alternative.me · Hyperliquid · Deribit · CoinGecko{T('（', ' (')}<a href="{U('/methodology/')}">{T('口径与规则', 'methodology')}</a>{T('）', ')')}</span>
<span class="disc">{esc(T(DISCLAIMER, DISCLAIMER_EN))}</span></footer>
{guide_templates()}
</main>
<script src="{ASSET_URL["ui.js"]}"></script>
{('<script src="' + ASSET_URL["share.js"] + '"></script>') if share else ''}
{('<script src="' + ASSET_URL["chart.js"] + '"></script>') if chart else ''}
{scripts}
</body>
</html>
"""


GLOSS = load(os.path.join(ROOT, "config", "glossary.json"), {}) or {}


def gloss_json():
    """当前语言的术语表 + 标签定义（G7），给 ui.js 做悬停解释。"""
    en = LANG["v"] == "en"
    terms = [{"w": t["en"] if en else t["zh"], "d": t["def_en"] if en else t["def_zh"]} for t in GLOSS.get("terms", [])]
    tags = {k: v[1] if en else v[0] for k, v in (GLOSS.get("tags") or {}).items()}
    return json.dumps({"terms": terms, "tags": tags}, ensure_ascii=False).replace("</", "<\\/")


def guide_templates():
    """G1 / G2：欢迎弹窗 + 版本更新弹窗的内容（模板，脚本按本地存储决定弹不弹）。"""
    if not CHANGELOG:
        return ""
    cur = CHANGELOG[0]["version"]
    t = sched_text()
    welcome = T(f"""<h2 id="ucg-t">欢迎来到链上大叔研究台</h2><p>这里每天自动更新一套 BTC 自上而下的四层框架数据：</p>
<ul><li><b>L1 宏观流动性</b>：风险预算该松还是紧</li><li><b>L2 周期定位</b>：处在四年周期的哪一段</li><li><b>L3 筹码结构</b>：筹码在流入还是流出交易所</li><li><b>L4 情绪衍生品</b>：短期会不会过热超调</li></ul>
<p>每层给一个结论，最后汇总成「综合研判」。</p>
<p><b>怎么看</b>：先看顶部的综合研判 → 切换 L1~L4 看每层结论和依据 → 点任意指标卡，看它的全部历史、区间规则和历史上落在每个区间的比例。</p>
<p>数据每天 {esc(t)} 自动更新，解读日志写入即冻结、公开可查。每个指标都标了<a href="{U('/methodology/')}#legend">证据等级</a>；拿不到真实数据的标「待接入」，不用近似值顶替。</p>
<p>本站还在持续迭代，很多地方不完善。发现问题或有建议，欢迎在 X 上找 <a href="{X_URL}" target="_blank" rel="noopener">@Uncle_Onchain</a>。</p>
<p class="muted">本站只提供数据和过程记录，不构成投资建议。</p>""",
                f"""<h2 id="ucg-t">Welcome to Uncle Onchain Terminal</h2><p>A top-down, 4-layer BTC framework, updated automatically every day:</p>
<ul><li><b>L1 Macro Liquidity</b>: should the risk budget be loose or tight?</li><li><b>L2 Cycle Position</b>: where are we in the four-year cycle?</li><li><b>L3 Supply Structure</b>: are coins flowing into or out of exchanges?</li><li><b>L4 Sentiment &amp; Derivatives</b>: is the short term overheating?</li></ul>
<p>Each layer gets a verdict, and the four roll up into one overall read.</p>
<p><b>How to use it</b>: start with the overall read at the top → switch between L1–L4 for each layer's verdict and evidence → click any metric card for its full history, zone rules and how often each zone occurred historically.</p>
<p>Data refreshes daily at {esc(t)}; each daily log is frozen once written. Every metric carries an <a href="{U('/methodology/')}#legend">evidence grade</a>; anything we can't source for real is marked "Pending" rather than filled with a proxy.</p>
<p>This site is a work in progress. Spotted a problem or have an idea? Find us on X at <a href="{X_URL}" target="_blank" rel="noopener">@Uncle_Onchain</a>.</p>
<p class="muted">Data and process records only. Not investment advice.</p>""")
    welcome += f'<div class="ucg-ft"><button type="button" class="btn ucg-ok">{T("开始看", "Start exploring")}</button><small>{T("之后可在左侧栏「新手说明」再次打开", "Reopen anytime from “Guide” in the sidebar")}</small></div>'
    ups = ""
    for v in [x for x in CHANGELOG if x.get("notify")][:3]:
        lis = "".join(f'<li><span class="cltag cl-{i["type"]}">{esc(T(*CL_TYPE[i["type"]]))}</span>{esc(T(i["zh"], i["en"]))}</li>' for i in v["items"])
        ups += f'<div class="ucg-v" data-v="{esc(v["version"])}"><h3>{T("本次更新", "What’s new")} · {esc(v["version"])}</h3><p class="muted">{esc(T(v["title_zh"], v["title_en"]))}</p><ul class="cl">{lis}</ul></div>'
    upd = (ups + f'<div class="ucg-ft"><a class="btn ghost" href="{U("/changelog/")}">{T("查看全部更新日志 →", "Full changelog →")}</a>'
           f'<button type="button" class="btn ucg-ok">{T("知道了", "Got it")}</button></div>')
    vers = json.dumps([{"v": x["version"], "n": bool(x.get("notify"))} for x in CHANGELOG])
    return (f'<template id="ucg-welcome">{welcome}</template><template id="ucg-update">{upd}</template>'
            f'<script type="application/json" id="ucg-meta">{{"cur":"{cur}","vers":{vers}}}</script>'
            f'<script type="application/json" id="uc-gloss">{gloss_json()}</script>')


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


GRADE_CLS = {"已验证": "g-v", "已验证·方向": "g-d", "描述读数": "", "监控": "g-o", "观察项": "g-o", "假设": "g-o", "已证伪": "g-x", "记录中": "g-o"}
GRADE_EN = {"已验证": "Verified", "已验证·方向": "Verified · direction", "描述读数": "Descriptive", "监控": "Monitor", "观察项": "Watch only",
            "假设": "Hypothesis", "已证伪": "Falsified", "记录中": "Recording"}
LEVEL_EN = {"核心": "core", "辅助": "aux", "观察": "watch"}


def grade_chip(g, ind=None):
    if not g:
        return ""
    note = ""
    if ind and ind.get("等级注"):
        note = f"（{ind['等级注']}）" if LANG["v"] == "zh" else f" ({ind['等级注EN']})"
    return (f'<span class="grade {GRADE_CLS.get(g, "")}" data-tag="{esc(g)}" tabindex="0">{esc(T(g, GRADE_EN.get(g, g)))}{esc(note)}</span>')


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


# ---------------------------------------------------------------- 全站配置：定时任务时间从 workflow 的 cron 读出来（G4）
SITE_CFG = load(os.path.join(ROOT, "config", "site.json"), {}) or {}


def schedules():
    out = []
    for t in SITE_CFG.get("定时任务", []):
        p = os.path.join(ROOT, ".github", "workflows", t["文件"])
        txt = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        m = re.search(r'cron:\s*"(\d+)\s+(\d+)\s', txt)
        out.append({**t, "时间": f"{int(m.group(2)):02d}:{int(m.group(1)):02d}" if m else "—"})
    return out


SCHED = schedules()
MAIN_TIME = next((x["时间"] for x in SCHED if x.get("主")), "—")
L2_TIME = next((x["时间"] for x in SCHED if x["文件"] == "l2-daily.yml"), "—")


def sched_text():
    """「每天 UTC 02:17（L2）和 10:20（日更）」这类文案，全站共用。"""
    parts = [(f"UTC {x['时间']}（{x['名称']}）", f"{x['时间']} UTC ({x['EN']})") for x in SCHED]
    return T("、".join(p[0] for p in parts), " and ".join(p[1] for p in parts))


def times_line(log):
    """「解读生成 … · 数据更新 …」：区分日志冻结时间和页面读数的刷新时间。"""
    gen = (log or {}).get("生成时间UTC")
    return (T("解读生成", "Log generated") + f" <b>{esc(gen or '—')} UTC</b> · " + T("数据更新", "Data updated") + f" <b>{esc(G.get('更新') or '—')} UTC</b>")


def stats_since(ind):
    """「正常波动范围」统计窗口（D3 规则在 宏观规则.stats_window）。"""
    return R.stats_window(G["S"], ind)[0] if G.get("S") is not None else None


# ---------------------------------------------------------------- 全历史数据文件（D1）
# /data/series/<id>.json（归档：截至上月末，每月 1 日重写；数据源回改时也重写）+ <id>.recent.json（本月，每天重写）
# 日度序列存「起始日期 + 数值数组」，缺数据存 null；周度序列存日期数组（周五对齐）。前端读两份拼起来。
SERIES_DIR = "series"
REV_PATH = os.path.join(DATA, "data_revisions.json")


def _mend(d):
    x = dt.date.fromisoformat(d).replace(day=1) - dt.timedelta(days=1)
    return x.isoformat()


def _days(a, b):
    x, y = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    return [(x + dt.timedelta(days=i)).isoformat() for i in range((y - x).days + 1)]


def _old_series(name):
    """读上一次写出的归档 + 本月文件 → {日期: 值}（比较数据源回改用）。"""
    out = {}
    for fn in (f"{name}.json", f"{name}.recent.json"):
        j = load(os.path.join(SITE, "data", SERIES_DIR, fn))
        if not j or not j.get("values"):
            continue
        ds = j.get("dates") or (_days(j["start"], (dt.date.fromisoformat(j["start"]) + dt.timedelta(days=len(j["values"]) - 1)).isoformat()) if j.get("start") else [])
        out.update({d: v for d, v in zip(ds, j["values"]) if v is not None})
    return out


def put_series(name, ser, freq="d", meta=None, label=None, revisions=None):
    """写一条序列（归档 + 本月），返回前端用的 src 列表（带 ?v=数据日期）。revisions：检测到数据源回改时追加记录。"""
    ds = sorted(d for d, v in ser.items() if v is not None)
    if not ds:
        return None
    last = ds[-1]
    cut = _mend(last)
    full = _days(ds[0], last) if freq == "d" else ds
    arch, rec = [d for d in full if d <= cut], [d for d in full if d > cut]
    base = os.path.join(SITE, "data", SERIES_DIR)
    os.makedirs(base, exist_ok=True)
    pa, pr = os.path.join(base, f"{name}.json"), os.path.join(base, f"{name}.recent.json")
    old_a = load(pa)
    rewrite = not old_a or old_a.get("archive_end") != cut or old_a.get("freq") != freq
    if revisions is not None and old_a:
        old = _old_series(name)
        vals = sorted(abs(v) for v in ser.values() if v is not None)
        scale = vals[len(vals) // 2] if vals else 1
        lim = (dt.date.fromisoformat(last) - dt.timedelta(days=7)).isoformat()
        hits = [(d, ser[d], old[d]) for d in old if d <= lim and ser.get(d) is not None and old[d] is not None
                and abs(ser[d] - old[d]) > 0.005 * max(abs(old[d]), scale or 1)]
        if hits:
            mx = max(hits, key=lambda h: abs(h[1] - h[2]) / max(abs(h[2]), scale or 1))
            revisions.append({"检测日": G.get("今天"), "指标": name, "名称": label or name, "起": min(h[0] for h in hits), "止": max(h[0] for h in hits),
                              "点数": len(hits), "最大变动": round((mx[1] - mx[2]) / max(abs(mx[2]), scale or 1) * 100, 2), "日期": mx[0]})
            rewrite = True
    head = {"id": name, "freq": "D" if freq == "d" else "W"}
    if rewrite:
        a = {**head, "archive_end": cut, "values": [r6(ser.get(d)) for d in arch]}
        if freq == "d":
            a["start"] = arch[0] if arch else None
        else:
            a["dates"] = arch
        with open(pa, "w", encoding="utf-8") as fh:
            json.dump(a, fh, ensure_ascii=False, separators=(",", ":"))
    r = {**head, **(meta or {}), "archive_end": cut, "updated": last, "values": [r6(ser.get(d)) for d in rec]}
    if freq == "d":
        r["start"] = rec[0] if rec else None
    else:
        r["dates"] = rec
    with open(pr, "w", encoding="utf-8") as fh:
        json.dump(r, fh, ensure_ascii=False, separators=(",", ":"))
    v = f"?v={last}"
    return [f"/data/{SERIES_DIR}/{name}.json{v}", f"/data/{SERIES_DIR}/{name}.recent.json{v}"]


def put_multi(name, start_ser, freq="d", revisions=None):
    """多条同起点日度序列合成一份（L2 价格 + 成本线 + 状态图用）：{key: {日期: 值}}。"""
    keys = list(start_ser)
    all_d = sorted(set().union(*[set(d for d, v in start_ser[k].items() if v is not None) for k in keys]))
    if not all_d:
        return None
    last = all_d[-1]
    cut = _mend(last)
    full = _days(all_d[0], last)
    arch, rec = [d for d in full if d <= cut], [d for d in full if d > cut]
    base = os.path.join(SITE, "data", SERIES_DIR)
    os.makedirs(base, exist_ok=True)
    pa, pr = os.path.join(base, f"{name}.json"), os.path.join(base, f"{name}.recent.json")
    old_a = load(pa)
    if not old_a or old_a.get("archive_end") != cut:
        a = {"id": name, "freq": "D", "archive_end": cut, "start": arch[0] if arch else None,
             "extra": {k: [r6(start_ser[k].get(d)) for d in arch] for k in keys}}
        with open(pa, "w", encoding="utf-8") as fh:
            json.dump(a, fh, ensure_ascii=False, separators=(",", ":"))
    r = {"id": name, "freq": "D", "archive_end": cut, "updated": last, "start": rec[0] if rec else None,
         "extra": {k: [r6(start_ser[k].get(d)) for d in rec] for k in keys}}
    with open(pr, "w", encoding="utf-8") as fh:
        json.dump(r, fh, ensure_ascii=False, separators=(",", ":"))
    v = f"?v={last}"
    return [f"/data/{SERIES_DIR}/{name}.json{v}", f"/data/{SERIES_DIR}/{name}.recent.json{v}"]


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


# ---------------------------------------------------------------- 综合研判（M11）：一句话 + 四段（方向 / 节奏 / 筹码 / 短期）
LAYER_TAB = {1: ("L1", "宏观流动性", "Macro Liquidity"), 2: ("L2", "周期定位", "Cycle Position"), 3: ("L3", "筹码结构", "Coin Flows"),
             4: ("L4", "情绪衍生品", "Sentiment & Derivatives")}


def comp_segments(comp, prev_comp=None, link=True):
    """四段：层徽章（颜色按 bias）+ 文本 + 段末关键数字；和前一天比有变化的段首加「变」。"""
    old = {x["层"]: x for x in (prev_comp or {}).get("段", [])}
    out = ""
    for x in comp.get("段", []):
        o = old.get(x["层"])
        chg = ""
        if o and LF(o, "文本") != LF(x, "文本"):
            chg = f'<span class="chg" title="{esc(T("昨日：", "Yesterday: ") + LF(o, "文本"))}" tabindex="0">{T("变", "chg")}</span>'
        rel = f'<span class="chip rel {"t-warn" if x.get("关系类") == "背离" else ""}">{esc(LF(x, "关系"))}</span>' if x.get("关系") else ""
        num = f' <span class="num">{esc(LF(x, "数字"))}</span>' if LF(x, "数字") else ""
        badge = (f'<a class="lb t-{x["tone"]}" href="{U("/macro/")}#layer-{x["层"]}" data-tab="{x["层"]}"><i></i>L{x["层"]}</a>' if link
                 else f'<span class="lb t-{x["tone"]}"><i></i>L{x["层"]}</span>')
        out += (f'<li>{badge}<div><b>{esc(LF(x, "标签"))}</b>{chg} {esc(LF(x, "文本"))}{num} {rel}</div></li>')
    return f'<ul class="segs">{out}</ul>'


def comp_block(comp, prev_comp=None, log=None, full=True, frozen=False, link=True):
    if not comp:
        return ('<div class="glass verdict"><div class="body"><div class="lbl">' + T("综合研判", "Overall read") + '</div><div class="txt">'
                + T(f"今日解读还没生成（每天 {sched_text()} 自动运行）。", f"Today's read has not been generated yet (runs daily at {sched_text()}).") + '</div></div></div>')
    badges = "".join(f'<a class="chip t-{x["tone"]}" href="{U("/macro/")}#layer-{x["层"]}"><i></i>L{x["层"]} · {esc(LF(x, "短") or "—")}</a>'
                     for x in sorted(comp.get("段", []), key=lambda x: x["层"]))
    if comp.get("规则") != "四层合成":           # 2026-10-08 之前的日志：只有一句话（L1 × L4）
        return (f'<div class="glass verdict"><div class="body"><div class="lbl">{T("综合研判", "Overall read")}'
                f'{" · " + T("日志冻结值", "frozen log value") if frozen else ""}</div><div class="txt">{esc(en_fix(LF(comp, "一句话")) or "(Chinese only)")}</div>'
                f'<div class="chips">{"".join(tone_chip(t, "neutral") for t in (LF(comp, "标签") or []))}</div></div></div>')
    segs = (f'<details class="segd" open><summary>{T("四段分层说明", "Layer by layer")}</summary>{comp_segments(comp, prev_comp, link)}'
            f'<p class="tnote">{esc(LF(comp, "小字"))}</p></details>') if full else ""
    stamp = f'<div class="stamp tl">{times_line(log)}</div>' if full or frozen else ""
    return (f'<div class="glass verdict comp"><div class="body"><div class="lbl">{T("综合研判", "Overall read")}'
            f'{" · " + T("日志冻结值", "frozen log value") if frozen else ""}</div>'
            f'<div class="txt">{esc(LF(comp, "一句话"))}</div><div class="chips">{badges}</div>' + segs + stamp + '</div></div>')


def verdict_block(log, link=True):
    """日志页：显示当天冻结的综合研判。"""
    if not log:
        return comp_block(None)
    comp = log.get("综合") or {}
    patch = f' <span class="chip t-warn">{T("补录", "Re-run")}</span>' if log.get("补录") else ""
    blk = comp_block(comp, None, log, full=True, frozen=False, link=link)
    if comp.get("规则") != "四层合成":
        tags = "".join(tone_chip(f'{LF(lay, "名称")} · {LF(lay, "短")}', lay["tone"]) for lay in log["层"])
        blk = (f'<div class="glass verdict"><div class="body"><div class="lbl">{T("综合研判", "Overall read")} · {log["日期"]}{patch}</div>'
               f'<div class="txt">{esc(en_fix(LF(comp, "一句话")) or "(Chinese only — written before bilingual logs)")}</div><div class="chips">{tags}</div></div></div>')
    return blk


def l1_raw(log_or_line):
    """L1 原始判定串（M4：折叠，供核对，内容不改）。"""
    l1 = log_or_line if isinstance(log_or_line, str) else LF(log_or_line, "L1行")
    if not l1:
        return ""
    return f'<details class="raw"><summary>{T("查看原始判定串", "Show the raw verdict string")}</summary><div class="l1line">{esc(l1)}</div></details>'


def layer_streak(i, short, logs, as_of):
    """与昨日比：昨天的层结论 + 已持续天数（含今天）。"""
    prev = [lg for lg in logs if lg["日期"] < as_of]
    yday = None
    n = 1
    for lg in reversed(prev):
        lay = next((x for x in lg.get("层", []) if x["层"] == i), None)
        if yday is None:
            yday = lay
        if lay and lay.get("短") == short:
            n += 1
        else:
            break
    return yday, n


def signal_tiles(vs, jby, l2):
    """首页四层信号灯（最新数据，不读日志冻结值）。"""
    out = ""
    for i, meta in R.LAYERS.items():
        lay = vs.get(i) or {}
        if i == 2 and l2 and l2.get("signals"):
            sig = l2["signals"]
            st = l2.get("state") or {}
            cnt = lambda c: (sum(1 for x in sig if x["category"] == c and x["on"]), sum(1 for x in sig if x["category"] == c))
            z, cf, tp = cnt("底部区"), cnt("底部确认"), cnt("顶部风险")
            items = (f'<li><span>{T("已持续", "Duration")}</span><b>{T("第", "day ")}{st.get("days", "—")}{T(" 天", "")}</b></li>'
                     f'<li><span>{T("底部区信号", "Bottom-zone signals")}</span><b>{z[0]}/{z[1]}</b></li>'
                     f'<li><span>{T("底部确认", "Bottom confirmation")}</span><b>{cf[0]}/{cf[1]}</b></li>')
        else:
            core = [x for x in ind_layer_list(i) if x["级别"] == "核心" and jby.get(x["key"])][:3]
            items = "".join(f'<li><span>{esc(T(x["名称"], x["EN"]))}</span><b class="t-{jby[x["key"]]["tone"]}">{esc(jby[x["key"]]["显示"])} · '
                            f'{esc(short_zone(LF(jby[x["key"]], "区间")))}</b></li>' for x in core)
        out += (f'<a class="card sig t-{lay.get("tone", "neutral")}" href="{U("/macro/")}#layer-{i}"><div class="n">LAYER {i} · {esc(T(meta["频率"], meta["频率EN"]))}</div>'
                f'<div class="q">{esc(T(meta["名称"], meta["EN"]))}{CN}{esc(T(meta["问"], meta["问EN"]))}{T("？", "?")}</div><div class="v t-{lay.get("tone", "neutral")}">{esc(LF(lay, "结论") or "—")}</div>'
                f'<ul>{items or "<li><span>" + T("数据不足", "No data") + "</span></li>"}</ul></a>')
    return f'<div class="grid g4">{out}</div>'


def alert_text(a):
    t = LF(a, "文本")
    if LANG["v"] == "en" and has_cjk(t):
        return en_fix(t) or ("Launchpad data note (details on the launchpad page, Chinese only)" if a.get("层") == "lp" or t.startswith("Launchpad") else "Data note (Chinese only)")
    return t


def alert_href(a):
    if a.get("层") == "lp":
        return U("/launchpad/")
    if a.get("key") and a["key"] in R.IND:
        return ind_href(a["key"])
    if isinstance(a.get("层"), int):
        return U("/macro/") + f"#layer-{a['层']}"
    return None


def changes_list(al, base_date):
    """今日变化（H1）：按层分组，每条可点进对应详情页；没有变化时明说。"""
    groups = [(1, "L1 " + T("宏观流动性", "Macro")), (2, "L2 " + T("周期定位", "Cycle")), (3, "L3 " + T("筹码结构", "Flows")),
              (4, "L4 " + T("情绪衍生品", "Sentiment")), ("lp", T("发射台", "Launchpads"))]
    out = ""
    for g, title in groups:
        xs = [a for a in al if a.get("层") == g]
        if not xs:
            continue
        lis = ""
        for a in xs:
            h = alert_href(a)
            txt = esc(alert_text(a))
            lis += (f'<li><span class="lv {"h" if a["级别"] == "高" else "m"}">{T(a["级别"], "High" if a["级别"] == "高" else "Med")}</span>'
                    + (f'<a href="{h}">{txt}</a>' if h else txt) + "</li>")
        out += f'<div class="cg"><div class="cgh">{esc(title)}</div><ul class="alerts">{lis}</ul></div>'
    other = [a for a in al if a.get("层") not in (1, 2, 3, 4, "lp")]
    if other:
        out += '<div class="cg"><ul class="alerts">' + "".join(f'<li>{esc(alert_text(a))}</li>' for a in other) + "</ul></div>"
    if not out:
        out = f'<div class="quiet">{T("四层结论与昨日相同，没有指标切换区间。", "All four layer verdicts are the same as yesterday; no gauge changed zone.")}</div>'
    base = T(f"和 {base_date} 的日志比", f"vs the {base_date} log") if base_date else ""
    return out, base


def alert_board(log, title=None, share_id=None):
    """日志页：当天冻结的预警（不再放跑马灯）。"""
    title = title or T("异动预警", "Alerts")
    al = (log or {}).get("预警") or []
    lis = "".join(f'<li><span class="lv {"h" if a["级别"] == "高" else "m"}">{T(a["级别"], "High" if a["级别"] == "高" else "Med")}</span>'
                  f'{esc(alert_text(a))}</li>' for a in al)
    body = f'<ul class="alerts">{lis}</ul>' if lis else ('<div class="quiet">' + T(
        "当天没有触发预警阈值（区间切换、L1 档位切换、L2 状态切换 / 信号亮灭、交易所单日 ±5,000 BTC、资金费率翻转、VIX 穿越 20、发射台异动等）。",
        "No alert thresholds were hit (zone changes, L1 regime change, L2 state / signal changes, ±5,000 BTC exchange day, funding flip, VIX crossing 20, launchpad moves).") + '</div>')
    btn = f'<button class="btn" onclick="{share_id}()">📸 {T("生成长图", "Share image")}</button>' if share_id else ""
    return (f'<div class="card board"><div class="board-hd"><span class="dot"></span><b>{esc(title)}</b>'
            f'<span class="stamp">{(log or {}).get("日期", "")}</span><span class="sp"></span>{btn}</div>{body}</div>')


def share_payload_home(comp, cards, al):
    """首页 / 日志页长图内容（纯字符串，交给 ucShare 渲染）：一句话 + 四层四段 + 关键数字 + 变化。"""
    k = "".join(f'<div class="sc-kpi"><div class="k">{esc(c[0])}</div><div class="v t-{c[4]}">{c[2]}</div></div>' for c in cards)
    segs = "".join(f'<li><b class="t-{x["tone"]}">L{x["层"]} · {esc(LF(x, "标签"))}</b> {esc(LF(x, "文本"))}</li>' for x in (comp or {}).get("段", []))
    if not segs:
        segs = "".join(f'<li>{esc(t)}</li>' for t in (LF(comp or {}, "标签") or []))
    al_h = "".join(f'<li>{"🔴" if a["级别"] == "高" else "🟠"} {esc(alert_text(a))}</li>' for a in (al or [])[:6])
    return (f'<div class="sc-box"><ul class="sc-al">{segs}</ul></div><div class="sc-kpis">{k}</div>'
            + (f'<div class="sc-box"><ul class="sc-al">{al_h}</ul></div>' if al_h else ""))


# ---------------------------------------------------------------- 首页：终端总览
def build_home(sd, S, logs, weeks, months, rot, matrix):
    as_of = G["as_of"]
    tlog = G.get("TODAY_LOG")
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
              ) if lp_rows else empty_state("none", T("发射台数据待生成", "Launchpad data pending"), T("下一次每日运行后出现。", "Appears after the next daily run."), "")
    cats = ""
    if rot:
        last = rot[max(rot)]
        top = sorted(rot_clean(last)[0], key=lambda c: -c["24h"])[:6]
        for c in top:
            tone = "up" if c["24h"] >= 0 else "dn"
            cats += (f'<div class="card cat t-{tone}"><div class="nm">{esc(c["名称"])}</div>'
                     f'<div class="v t-{tone}">{c["24h"]:+.2f}%</div><div class="s">{T("市值", "Cap")} {f_usd(c["市值"])}</div></div>')
    cats = f'<div class="grid g3">{cats}</div>' if cats else empty_state("none", T("板块快照待生成", "Snapshot pending"), T("下一次每日运行后出现。", "Appears after the next daily run."), "")
    items = ""
    for n, lg in enumerate(reversed(logs[-6:])):
        cnt = len(lg.get("预警") or [])
        fz = f'<span class="chip frz">{T("日志", "log")} · {esc((lg.get("生成时间UTC") or "")[11:16])} UTC {T("冻结", "frozen")}</span>' if n == 0 else ""
        items += (f'<li><span class="d">{lg["日期"]}</span><span><a href="{U("/journal/" + lg["日期"] + "/")}">{T("每日解读", "Daily log")}</a> {fz}'
                  f'<span class="s">{esc(en_fix(LF(lg["综合"], "一句话")) or "(Chinese only)")}</span></span><span class="x chip">{cnt} {T("条预警", "alerts")}</span></li>')
    for wk in reversed(weeks[-2:]):
        items += (f'<li><span class="d">{wk["标签"]}</span><span><a href="{U("/journal/week/" + wk["标签"] + "/")}">{T("周复盘", "Weekly review")}</a>'
                  f'<span class="s">{esc(en_fix(LF(wk, "一句话")) or "(Chinese only)")}</span></span></li>')
    for mo in reversed(months[-1:]):
        items += (f'<li><span class="d">{mo["标签"]}</span><span><a href="{U("/journal/month/" + mo["标签"] + "/")}">{T("月复盘", "Monthly review")}</a>'
                  f'<span class="s">{esc(en_fix(LF(mo, "一句话")) or "(Chinese only)")}</span></span></li>')
    jl = f'<div class="card"><ul class="list">{items}</ul></div>' if items else empty_state("none", T("还没有日志", "No logs yet"), T("第一篇解读日志会在下一次每日运行时写入。", "The first log comes with the next daily run."), "")
    rp = ""
    for r in ALL_REPORTS[:3]:
        rp += (f'<a class="card rcard" href="{U("/reports/" + r["slug"] + "/")}"><span class="d">{esc(r["日期"])}</span><b>{esc(LF(r, "标题"))}</b>'
               f'<p>{esc(LF(r, "摘要"))}</p></a>')
    comp = G["COMP"]
    ch_html, ch_base = changes_list(G["CHANGES"], (G.get("PREV_LOG") or {}).get("日期"))
    share_obj = {"title": T("今日链上终端 · 四层研判", "Onchain terminal · 4-layer read"), "date": as_of,
                 "sub": LF(comp or {}, "一句话"), "html": share_payload_home(comp, cards, G["CHANGES"]),
                 "file": f"uncleonchain-terminal-{as_of}.png"}
    reports_block = ""
    if rp:
        reports_block = (f'<h2>{T("分析报告", "Research reports")} <a class="sub" href="{U("/reports/")}">{T("全部报告 →", "All reports →")}</a></h2>'
                         f'<div class="grid g3">{rp}</div>')
    body = f"""<div class="ph"><div><div class="eyebrow">Terminal Overview</div><h1>{T("终端总览", "Terminal overview")}</h1>
<p class="lede">{T(f"宏观流动性 → 周期位置 → 筹码结构 → 情绪，再落到发射台一级市场。每天 {sched_text()} 自动拉数，日更写一篇解读日志，写入即冻结，公开可查。",
                   f"Macro liquidity → cycle position → coin flows → sentiment, down to launchpads. Data refreshes daily at {sched_text()}; the daily run writes a log that is frozen once written.")}</p></div>
<div class="stamp">{times_line(tlog)}</div></div>
{comp_block(comp, None, tlog, full=False)}
<h2>{T("今日变化", "What changed today")} <span class="sub">{esc(ch_base)}</span><span class="sp"></span><button class="btn" onclick="shareHome()">📸 {T("生成今日长图", "Share image")}</button></h2>
<div class="card board changes">{ch_html}</div>
<div class="grid g4" style="margin-top:14px">{heroes}</div>
<h2>{T("四层信号灯", "Four-layer signals")} <span class="sub">{T("点进去看每层结论、依据和每个指标的全部历史", "Click through for each layer's verdict, evidence and every gauge's full history")}</span></h2>
{signal_tiles(G["VS"], G["JBY"], G.get("L2"))}
<div class="grid g2" style="margin-top:22px;align-items:start">
<div><h2 style="margin-top:12px">{T("发射台矩阵 · 当日 Top6", "Launchpads · top 6 today")} <a class="sub" href="{U("/launchpad/")}">{T("全部", "All")} {len((matrix or {}).get("协议", []))} {T("个协议 →", "protocols →")}</a></h2>{lp_tbl}</div>
<div><h2 style="margin-top:12px">{T("板块轮动 · 24h 领涨", "Rotation · 24h leaders")} <a class="sub" href="{U("/rotation/")}">{T("看全部 →", "See all →")}</a></h2>{cats}</div>
</div>
{reports_block}
<h2>{T("解读日志", "Journal")} <a class="sub" href="{U("/journal/")}">{T("全部日志与复盘 →", "All logs and reviews →")}</a></h2>
{jl}"""
    js = f"<script>function shareHome(){{ucShare({json.dumps(share_obj, ensure_ascii=False)})}}</script>"
    emit("index.html", T(f"{BRAND} · 链上数据情报终端", f"{BRAND_EN} · Onchain research terminal"), body, active="home", share=True, scripts=js,
         desc=LF(comp or {}, "一句话") or T(SLOGAN, SLOGAN_EN))


def ind_card(ind, j, as_of, extra=""):
    """指标卡（全站一个组件；L2 六张卡和 L1/L3/L4 同一套样式）。"""
    name = T(ind["名称"], ind["EN"])
    lvl = T(ind["级别"], LEVEL_EN.get(ind["级别"], ind["级别"])) + (f" · {T(ind['级别注'], ind['级别注EN'])}" if ind.get("级别注") else "")
    head = (f'<div class="top"><span class="nm">{esc(name)}<span class="grade lv" data-tag="{esc(ind["级别"])}" tabindex="0">{esc(lvl)}</span>'
            f'{grade_chip(ind.get("等级"))}</span>')
    obs = " obs" if ind["级别"] == "观察" else ""
    rec = R.recording_info(G["S"], ind)
    rec_chip = f'<span class="chip t-warn rc"><i></i>{T("记录中", "Recording")} · {rec["days"]}/{rec["required"]}</span>' if rec and not rec["done"] else ""
    cid = f'id="card-{ind["key"]}"'
    if not j:
        return (f'<a class="card ind{obs}" {cid} href="{ind_href(ind["key"])}">{head}</div>'
                f'<div class="v t-neutral">—</div><div class="b">{T("等待数据源", "Awaiting source")}{T("（", " (")}{esc(src_t(ind["来源"]))}{T("）", ")")}</div>'
                f'<div class="ft"><span>{esc(src_t(ind["来源"]))}</span><span class="go">{T("看说明 →", "Details →")}</span></div></a>')
    stale = (f'<span class="stale">{T("滞后", "lag")} {R.days_between(j["截至"], as_of)} {T("天", "d")}</span>' if j["过期"]
             else f'{T("截至", "as of")} {asof_txt(j["截至"], as_of)}')
    zone = tone_chip(short_zone(LF(j, "区间")), j["tone"]) if not (rec and not rec["done"] and ind["key"] in OWN_PCT) else ""
    return (f'<a class="card ind{obs}" {cid} href="{ind_href(ind["key"])}">{head}'
            f'{zone}</div>{rec_chip}<div class="v">{esc(j["显示"])}</div><div class="b">{esc(LF(j, "依据"))}{extra}</div>'
            f'{spark(j["走势"], j["tone"], 240, 32, area=True)}'
            f'<div class="ft"><span>{stale}</span><span class="go">{T("全部历史 →", "Full history →")}</span></div></a>')


def pending_card(p):
    """待接入占位卡（M9）：和指标卡同尺寸，虚线灰卡，不可点。"""
    return (f'<div class="card ind pendc" id="card-{p["key"]}"><div class="top"><span class="nm">{esc(T(p["名称"], p["EN"]))}</span>'
            f'<span class="chip"><i></i>{T("待接入", "Pending")}</span></div>'
            f'<div class="b">{esc(T(p["原因"], p["原因EN"]))}</div>'
            f'<div class="ft"><span>{T("计划数据源", "Planned source")}{CN}{esc(T(p.get("计划", "—"), p.get("计划EN", "—")))}</span></div></div>')


def cards_by_group(layer, as_of, extra_fn=None):
    """按注册表的分组和顺序出卡片（M12）：组标题 + 卡片网格；待接入放最后一组。"""
    inds = ind_layer_list(layer)
    groups = []
    for ind in inds:
        if (ind["组"], ind["组EN"]) not in groups:
            groups.append((ind["组"], ind["组EN"]))
    out = []
    for g in groups:
        gi = [x for x in inds if x["组"] == g[0]]
        cards = "".join(ind_card(x, G["JBY"].get(x["key"]), as_of, extra_fn(x) if extra_fn else "") for x in gi)
        out.append((g, f'<div class="grid g4">{cards}</div>'))
    return out


def pending_block(layer):
    ps = [p for p in R.PENDING if p["层"] == layer]
    if not ps:
        return ""
    return (f'<div class="grp" id="grp-pending-{layer}">{T("待接入", "Pending")}</div><div class="grid g4">' + "".join(pending_card(p) for p in ps) + "</div>")


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
    return (f'<details class="card fold"><summary>{T("方法说明：价格 vs 数量", "Method note: price vs quantity")}</summary><div class="note" style="margin:0 14px 14px">{pq}</div></details>'
            f'<h3>{T("常见问题", "FAQ")} <span style="font-weight:400;font-size:12px;color:var(--muted)">{T("数字出处：", "Sources: ")}<a href="{U("/reports/2026-10-04-macro-vs-bitcoin/")}">{T("《宏观到底管不管比特币？》", "the macro weekend report")}</a>{T("与 BTC 全周期宏观研究", " and the BTC full-cycle macro study")}</span></h3>'
            f'<div class="faqs">{qa}</div>')


# ---------------------------------------------------------------- L2 周期状态机（只读 data/l2/*.json 展示，规则和计算都在 l2/）
L2_LINES = [("price", "BTC 价格", "BTC price", "ink", 2.0, False), ("sth_rp", "短期持有者成本", "STH cost", "s2", 1.4, False),
            ("tmmp", "真实市场均价", "True Market Mean", "s4", 1.4, False), ("ma200w", "200 周均线", "200W MA", "s7", 1.4, False),
            ("rp", "全网平均成本", "Realized price", "s1", 1.4, False), ("lth_rp", "长期持有者成本", "LTH cost", "s3", 1.3, True),
            ("rp_3_6m", "3-6 月持币成本", "3-6M cost", "s5", 1.2, True), ("rp_6_12m", "6-12 月持币成本", "6-12M cost", "s8", 1.2, True),
            ("cvdd", "CVDD 价格下限", "CVDD", "s9", 1.2, True)]
LAYER_RULE_DATES = {1: ("2026-10-02", "2026-10-04"), 2: ("2026-10-08",)}


def l2_state_meta(code):
    return R.L2_STATES.get(code) or ("—", "—", "", "neutral", "line2")


def l2_chart():
    """M8：2012-01-01 至今的价格 + 成本线 + 状态背景；历史回放和实时记录用一条竖线分开。"""
    ser = G.get("L2S")
    if not ser:
        return empty_state("none", T("等待数据", "Awaiting data"), T("l2_daily.py 下一次运行后生成全历史。", "Full history appears after the next l2_daily.py run."), "")
    if "L2CHART" not in G:
        d0 = dt.date.fromisoformat(ser["start"])
        start = "2012-01-01"
        cols = {}
        for k, *_ in L2_LINES:
            vals = ser["series"].get(k) or []
            cols[k] = {(d0 + dt.timedelta(days=i)).isoformat(): v for i, v in enumerate(vals) if v is not None and (d0 + dt.timedelta(days=i)).isoformat() >= start}
        st = ser["series"].get("state") or []
        cols["st"] = {(d0 + dt.timedelta(days=i)).isoformat(): v for i, v in enumerate(st) if v is not None and (d0 + dt.timedelta(days=i)).isoformat() >= start}
        G["L2CHART"] = put_multi("l2_chart", cols)
    codes = ser.get("state_codes") or R.L2_ORDER
    states = [{"n": T(R.L2_STATES[c][0], R.L2_STATES[c][1]), "c": R.L2_STATES[c][4]} for c in codes]
    leg = "".join(f'<span><i style="background:var(--{R.L2_STATES[c][4]})"></i>{esc(T(R.L2_STATES[c][0], R.L2_STATES[c][1]))}</span>' for c in codes)
    live0 = (G.get("L2LIVE") or [{}])[0].get("date")
    mk = [{"date": m["date"], "label": T("减半", "halving")} for m in ser.get("markers", []) if m.get("type") == "halving"]
    if live0:
        mk.append({"date": live0, "type": "live", "label": T(f"← 历史回放（样本内）｜实时记录 {live0} 起 →", f"← historical replay (in-sample) | live record from {live0} →")})
    cfg = {"v2": True, "src": G["L2CHART"], "fmt": "price", "log": True, "ranges": ["1Y", "3Y", "CYC", "ALL"], "range": "ALL", "cyc": G.get("CYC"),
           "stk": "st", "states": states, "markers": mk, "toggle": True, "last": False,
           "note": T("对数坐标：同样的高度代表同样的涨跌幅。成本线 = 各类持有者的买入均价，现价在线上 = 这批人整体浮盈。点图例可以打开 / 关闭其余成本线。",
                     "Log scale: equal heights mean equal percentage moves. A cost line is a holder group's average buy price; price above it = that group is in profit. Click the legend to toggle the other cost lines."),
           "series": [{"k": k, "n": T(zh, en), "c": c, "w": w, "hidden": hid} for k, zh, en, c, w, hid in L2_LINES]}
    rep = T("竖线左边是历史回放：状态机规则是用这几轮周期定的，属于样本内结果；竖线右边是网站每天实时保存的判定（", "Left of the line is a historical replay — the rules were fitted on these cycles, so it is in-sample; right of it are the daily judgements the site has saved live (")
    rep += T(f"{live0} 起）。", f"since {live0}).") if live0 else T("还没有记录）。", "none yet).")
    return (f'<h3 style="margin-top:0">{T("价格 + 成本线 + 周期状态（2012 年至今）", "Price + cost lines + cycle state (2012–now)")}</h3>'
            f'<div class="l2leg">{T("背景色 = 当天状态：", "Background = state of the day: ")}{leg}</div>' + chart_div(cfg)
            + f'<p class="tnote">{rep}</p>')


def sig_name(x):
    zh = x["name_zh"].replace("（本轮已出现）", "（本轮出现过即计入）")
    en = x["name_en"].replace("(this cycle)", "(counts once seen this cycle)")
    return T(zh, en)


def l2_signals(l2):
    """M7：三组可折叠，标题显示亮起数量；每条带当前读数、规则类型的实际状态、证据等级、出处，能点进对应指标。"""
    sig = l2.get("signals") or []
    out = ""
    for cat, dotc in (("底部区", "l2-zone"), ("底部确认", "l2-rec"), ("顶部风险", "l2-risk")):
        xs = [x for x in sig if x["category"] == cat]
        lis = ""
        for x in xs:
            tags = [f'<span class="ev">{esc(T(x["evidence"], R.L2_EVID.get(x["evidence"], x["evidence"])))}</span>', f'<span class="ref">{esc(x.get("ref") or "")}</span>']
            if x.get("changed_today"):
                tags.append(f'<span class="td">{T("今日", "today")}{T("亮起" if x["on"] else "熄灭", " on" if x["on"] else " off")}</span>')
            rule = x.get("rule") or ("cycle" if x["key"].endswith("(本轮)") else None)
            if rule == "cycle":
                if x.get("cycle_first") or (x["on"] and "cycle_first" not in x):
                    d = x.get("cycle_first")
                    tags.append(f'<span class="st on">{T("本轮已出现", "seen this cycle")}{" · " + d if d else ""}</span>')
                else:
                    tags.append(f'<span class="st">{T("本轮未出现", "not seen this cycle")}</span>')
            elif rule == "mem30" and x["on"] and x.get("now_true") is False and x.get("last_true"):
                tags.append(f'<span class="st on">{T("30 天记忆 · 最近一次满足", "30-day memory · last met")} {x["last_true"]}</span>')
            rd = T(x.get("reading_zh") or "", x.get("reading_en") or "")
            nm = esc(sig_name(x))
            if x.get("metric") and x["metric"] in R.IND:
                nm = f'<a href="{ind_href(x["metric"])}">{nm}</a>'
            lis += (f'<li class="{"on" if x["on"] else ""}"><span class="dot" aria-label="{T("亮起" if x["on"] else "未亮", "on" if x["on"] else "off")}"></span><div><div class="nm">{nm}'
                    f'{" <span class=rd>" + esc(rd) + "</span>" if rd else ""}</div><div class="meta">{"".join(tags)}</div>'
                    f'<div class="nt">{esc(T(x.get("note") or "", R.L2_NOTE_EN.get(x["key"], "")))}</div></div></li>')
        n_on = sum(1 for x in xs if x["on"])
        out += (f'<details class="card l2sig" open style="--l2d:var(--{dotc})"><summary><b>{esc(T(cat, R.L2_CAT[cat]))}</b><span>{n_on}/{len(xs)} {T("亮起", "on")}</span></summary>'
                f'<ul>{lis}</ul></details>')
    return f'<div class="grid g3 sigs">{out}</div>'


def ruler_svg(price, levels, h=460, w=440):
    """M6：竖向对数价格轴，每条价位按真实距离摆放；现价醒目横线，现价到上下最近价位铺色带。"""
    if not levels or not price:
        return ""
    vals = [x["value"] for x in levels] + [price]
    lo, hi = math.log10(min(vals) * 0.96), math.log10(max(vals) * 1.04)
    top, bot = 22, h - 22
    Y = lambda v: top + (bot - top) * (1 - (math.log10(v) - lo) / (hi - lo))
    ax = 150
    out = [f'<line x1="{ax}" x2="{ax}" y1="{top}" y2="{bot}" class="rax"/>']
    above = sorted([x for x in levels if x["value"] > price], key=lambda x: x["value"])
    below = sorted([x for x in levels if x["value"] <= price], key=lambda x: -x["value"])
    yp = Y(price)
    if below:
        yb = Y(below[0]["value"])
        out.append(f'<rect x="{ax - 40}" y="{yp:.1f}" width="80" height="{yb - yp:.1f}" class="rsafe"/>')
        out.append(f'<text x="{ax - 46}" y="{(yp + yb) / 2 + 4:.1f}" text-anchor="end" class="rbt up">{T("安全垫", "cushion")} {below[0]["pct_from_price"]:+.1f}%</text>')
    if above:
        ya = Y(above[0]["value"])
        out.append(f'<rect x="{ax - 40}" y="{ya:.1f}" width="80" height="{yp - ya:.1f}" class="rres"/>')
        out.append(f'<text x="{ax - 46}" y="{(yp + ya) / 2 + 4:.1f}" text-anchor="end" class="rbt dn">{T("上方压力", "resistance")} {above[0]["pct_from_price"]:+.1f}%</text>')
    # 价位标签：按高度排，离上一个标签太近就换到另一侧
    placed = {"r": [], "l": []}
    for x in sorted(levels, key=lambda x: -x["value"]):
        y = Y(x["value"])
        side = "r"
        if any(abs(y - q) < 15 for q in placed["r"]):
            side = "l" if not any(abs(y - q) < 15 for q in placed["l"]) else "r"
        placed[side].append(y)
        cls = "up" if x["value"] <= price else "dn"
        lab = f'{esc(T(x["name_zh"], x["name_en"]))} ${x["value"]:,.0f} ({x["pct_from_price"]:+.1f}%)'
        out.append(f'<line x1="{ax - 10}" x2="{ax + 10}" y1="{y:.1f}" y2="{y:.1f}" class="rtk {cls}"/>')
        if side == "r":
            out.append(f'<text x="{ax + 16}" y="{y + 4:.1f}" class="rlb">{lab}</text>')
        else:
            out.append(f'<text x="{ax - 16}" y="{y + 4:.1f}" text-anchor="end" class="rlb">{lab}</text>')
    out.append(f'<line x1="{ax - 60}" x2="{w - 6}" y1="{yp:.1f}" y2="{yp:.1f}" class="rnow"/>')
    out.append(f'<text x="{w - 6}" y="{yp - 6:.1f}" text-anchor="end" class="rnl">{T("现价", "Price")} ${price:,.0f}</text>')
    return f'<svg viewBox="0 0 {w} {h}" class="ruler-svg" role="img" aria-label="{T("关键价位刻度尺", "Key level ruler")}">{"".join(out)}</svg>'


def l2_levels(l2):
    price = l2.get("price")
    lv = l2.get("levels") or []
    key6 = (l2.get("levels_above") or []) + (l2.get("levels_below") or [])
    allv = sorted(lv, key=lambda x: -x["value"])
    m = lambda v: "—" if v is None else f"${v:,.0f}"
    rows = "".join(f'<tr><td class="l">{esc(T(x["name_zh"], x["name_en"]))}</td><td>{m(x["value"])}</td><td>{x["pct_from_price"]:+.1f}%</td></tr>' for x in allv)
    return (f'<div class="ruler card"><input type="checkbox" id="rl-all" class="rtg"><label for="rl-all" class="pill">'
            f'<span class="a">{T("展开全部 13 条", "Show all 13")}</span><span class="b">{T("只看 6 条重点", "Key 6 only")}</span></label>'
            f'<div class="r6">{ruler_svg(price, key6)}</div><div class="r13">{ruler_svg(price, lv, h=560)}</div>'
            f'<p class="tnote">{T("对数刻度，按真实价格距离摆放；绿色 = 现价下方的支撑，红色 = 上方的压力。价位都由 l2_daily.py 每天算好，网页只展示（均衡价格为近似值）。", "Log scale, placed by real price distance; green = supports below, red = resistance above. All levels come from l2_daily.py; the page only displays them (balanced price is approximate).")}</p></div>'
            f'<details class="card fold"><summary>{T("13 条关键价位表", "All 13 levels (table)")}</summary><div class="tw" style="margin:0;border:0"><table><thead><tr><th class="l">{T("价位", "Level")}</th>'
            f'<th>{T("价格", "Value")}</th><th>{T("离现价", "vs price")}</th></tr></thead><tbody>{rows}</tbody></table></div></details>')


def l2_card_extra(ind):
    """L2 卡片与 14 条信号保持一致：信号靠 30 天记忆仍亮、而当前读数已不满足时，卡片上写明。"""
    for x in (G.get("L2") or {}).get("signals") or []:
        if x.get("metric") == ind["key"] and x.get("on") and x.get("now_true") is False and x.get("last_true"):
            return T(f"（对应信号仍亮：30 天记忆，最近一次满足 {x['last_true']}）", f" (signal still on: 30-day memory, last met {x['last_true']})")
    return ""


def l2_tab(l2, as_of):
    if not l2 or (l2.get("state") or {}).get("code") not in R.L2_STATES:
        return empty_state("pending", T("L2 周期状态机 · 等待首次运行", "L2 cycle state machine · awaiting first run"),
                           T(f"每天 UTC {L2_TIME} 由 GitHub Actions 运行 l2/l2_daily.py 生成。", f"Generated daily at {L2_TIME} UTC by l2/l2_daily.py."), "")
    st, cy = l2["state"], l2.get("cycle") or {}
    zh, en, desc_en, _, col = l2_state_meta(st["code"])
    m = lambda v: "—" if v is None else f"${v:,.0f}"
    stale = (l2.get("data_status") or {}).get("stale")
    chips = ""
    if st.get("previous"):
        prev_en = next((v[1] for v in R.L2_STATES.values() if v[0] == st["previous"]), st["previous"])
        chips += f'<span class="chip l2chg">{esc(T("今日状态变化：" + st["previous"] + " → " + zh, "State changed today: " + prev_en + " → " + en))}</span>'
    if stale:
        chips += f'<span class="chip l2stale">{T("数据延迟 · 用了缓存", "Data delayed · cached")}</span>'
    inval = ""
    if st["code"] == "RECOVERY" and cy.get("cycle_low"):
        inval = f'<div class="inval">{T("失效条件：收盘跌破本轮最低收盘", "Invalidation: a daily close below this cycle’s lowest close,")} <b>{m(cy["cycle_low"])}</b>{T("（退回熊市 / 熊底区）", " (back to bear / bottom zone)")}</div>'
    nxt = st.get("next_zh") if LANG["v"] == "zh" else st.get("next_en")
    summ = l2.get("summary_zh") if LANG["v"] == "zh" else R.l2_summary_en(l2)
    summ_h = "".join(f"<div>{esc(x)}</div>" for x in (summ or "").split("\n") if not x.startswith(("接下来：", "Next: ")))
    card = (f'<div class="card l2card" style="--l2c:var(--{col})"><div class="eb">L2 {T("周期状态机", "cycle state machine")} · {T("数据日", "data date")} {esc(l2.get("data_date") or "—")}'
            f' · {T("运行", "run")} {esc(l2.get("updated_utc") or "—")} UTC {chips}</div>'
            f'<h3 class="st">{esc(T(zh, en))} <span>· {T("第", "day ")}{st.get("days")}{T(" 天", "")}</span></h3>'
            f'<p class="desc">{esc(T(st.get("desc_zh") or "", desc_en.rstrip(".")))}{T("。自 ", ". Since ")}{esc(st.get("since") or "")}{T(" 起。", ".")}</p>'
            f'{inval}<div class="l2next"><b>{T("接下来看什么：", "What next: ")}</b>{esc(nxt or "")}</div>'
            f'<details class="raw"><summary>{T("每日结论原文", "Daily summary text")}</summary><div class="l2sum">{summ_h}</div></details></div>')
    nums = [(T("价格", "Price"), m(l2.get("price"))), (T("距历史高点", "From ATH"), f'{cy.get("drawdown_pct")}%'.replace("-", "−")),
            (T("新高已过", "ATH age"), f'{cy.get("days_since_ath")} {T("天", "d")}'), (T("距本轮最低收盘", "From cycle low"), f'+{cy.get("rebound_pct")}%'),
            (T("最低点已过", "Low age"), f'{cy.get("days_since_low")} {T("天", "d")}'), (T("距上次减半", "Since halving"), f'{cy.get("days_since_halving")} {T("天", "d")}'),
            (T("下次减半（估）", "Next halving (est.)"), cy.get("next_halving_est") or "—")]
    nums_h = '<div class="l2nums card">' + "".join(f"<span>{k}<b>{esc(v)}</b></span>" for k, v in nums) + "</div>"
    groups = cards_by_group(2, as_of, l2_card_extra)
    cards = "".join(f'<h3 id="grp-2-{n}">{esc(T(*g))}</h3>{c}' for n, (g, c) in enumerate(groups))
    method_h = (f'<p class="tnote">{esc(l2.get("method") or "")}</p>' if LANG["v"] == "zh" else
                '<p class="tnote">Historical replay of the state machine: one-year median forward return after "late bear → early bull" +152% (92% positive), '
                'bear bottom zone +68% (91%), bull top-risk zone −6% (47%), bear market −36% (31%).</p>')
    rep = ""
    rp = next((r for r in ALL_REPORTS if "cycle" in r["slug"]), None)
    if rp:
        rep = f'<p class="tnote">{T("相关研究：", "Related research: ")}<a href="{U("/reports/" + rp["slug"] + "/")}">{esc(LF(rp, "标题"))}</a></p>'
    return (card + nums_h + cards
            + f'<h3 id="l2-signals">{T("14 条信号", "14 signals")} <span class="sub">{T("实心 = 亮起；描边小标签 = 证据等级；§ = 研究文档章节", "filled = on; outlined tag = evidence grade; § = study section")}</span></h3>' + l2_signals(l2)
            + f'<h3 id="l2-levels">{T("关键价位刻度尺", "Key level ruler")}</h3>' + l2_levels(l2)
            + f'<div class="card chartcard" style="margin-top:12px">{l2_chart()}</div>'
            + method_h + rep + f'<p class="l2disc">{esc(T(*R.L2_DISCLAIMER))}</p>')


# ---------------------------------------------------------------- 每层结论区（M3）+ 判定明细（M4）
SWITCH_L1 = {
    "顺风": ("转为中性：乐观度 z 跌破 0，或 BAA 利差 13 周转为走阔；实际利率 13 周急升 ≥ +0.40pp 时转为中性偏谨慎，再叠加信用转紧或乐观度 z < 0 即逆风。",
             "To neutral: optimism z drops below 0 or the BAA spread widens over 13w; a real-yield surge (≥ +0.40pp over 13w) makes it neutral-cautious, and headwind if credit tightens or optimism z < 0."),
    "中性": ("转为顺风：乐观度 z > 0 且 BAA 13 周收窄、实际利率不急升；转为中性偏谨慎：实际利率 13 周急升 ≥ +0.40pp；转为逆风：急升叠加信用转紧或乐观度 z < 0，或流动性闸门触发。",
             "To tailwind: optimism z > 0 with BAA narrowing and no real-yield surge; to neutral-cautious: a real-yield surge ≥ +0.40pp over 13w; to headwind: a surge plus tighter credit or optimism z < 0, or the liquidity gate."),
    "中性偏谨慎": ("转为逆风：BAA 利差或 NFCI 的 13 周变化转为收紧，或乐观度 z 跌破 0（纳指 13 周转负 / VIX>20），或净流动性 13 周 ≤ −2.72% 且美元 13 周走强；回到中性 / 顺风：实际利率 13 周变化回到 +0.40pp 以下。",
              "To headwind: BAA or NFCI 13w change turns tighter, or optimism z drops below 0 (Nasdaq 13w negative / VIX > 20), or net liquidity 13w ≤ −2.72% with a stronger dollar; back to neutral/tailwind: the 13w real-yield change falls back below +0.40pp."),
    "逆风": ("回到中性偏谨慎：BAA 和 NFCI 的 13 周变化重新收窄 / 放松，且乐观度 z ≥ 0（实际利率仍急升）；回到中性或顺风：实际利率 13 周变化回到 +0.40pp 以下，且流动性闸门未触发。",
             "Back to neutral-cautious: BAA and NFCI 13w changes ease again and optimism z ≥ 0 (with real yields still surging); back to neutral or tailwind: the 13w real-yield change falls below +0.40pp and the liquidity gate is not tripped."),
}


def switch_text(i, lay, l2):
    if i == 1:
        t = R.re_short(lay.get("结论") or "").replace("·警戒", "")
        return T(*SWITCH_L1.get(t, ("—", "—")))
    if i == 2:
        st = (l2 or {}).get("state") or {}
        return (st.get("next_zh") if LANG["v"] == "zh" else st.get("next_en")) or "—"
    if i == 3:
        return T("交易所 BTC 7 日净流量 < −2,000 枚 = 净流出（筹码离开交易所）；−2,000 ~ +2,000 = 进出均衡；> +2,000 = 净流入（留意抛压）。",
                 "Exchange BTC 7-day net flow < −2,000 = outflow; −2,000 to +2,000 = balanced; > +2,000 = inflow (watch selling).")
    sc = lay.get("分")
    cur = f"{sc:+d}" if isinstance(sc, int) else "—"
    return T(f"恐慌贪婪、资金费率、未平仓 7 日变化三项分数合计 ≥ 3 过热、1~2 偏热、≤ −2 偏冷，其余中性（当前合计 {cur}）。",
             f"Fear & Greed, funding and 7-day OI change scores: total ≥ 3 hot, 1–2 warm, ≤ −2 cool, otherwise neutral (now {cur}).")


def basis_chips(i, lay, l2):
    jby = G["JBY"]

    def chip(k):
        j = jby.get(k)
        if not j:
            return ""
        return f'<a class="chip t-{j["tone"]}" href="#card-{k}" data-hl="card-{k}"><i></i>{esc(T(j["名称"], j["名称EN"]))} {esc(j["显示"])}</a>'
    if i == 1:
        st = lay.get("状态") or {}
        ks = ["real13"]
        if (st.get("nfci") or 0) > 0:
            ks.append("nfci13")
        if (st.get("baa") or 0) > 0 or "nfci13" not in ks:
            ks.append("baa13")
        ks.append("optimism_z")
        if lay.get("警戒"):
            ks.append("hy13")
        return "".join(chip(k) for k in ks[:4])
    if i == 2:
        sig = (l2 or {}).get("signals") or []
        out = ""
        for cat, en in (("底部区", "Bottom zone"), ("底部确认", "Bottom confirmation"), ("顶部风险", "Top risk")):
            xs = [x for x in sig if x["category"] == cat]
            if xs:
                out += f'<a class="chip" href="#l2-signals" data-hl="l2-signals"><i></i>{T(cat, en)} {sum(1 for x in xs if x["on"])}/{len(xs)}</a>'
        return out
    if i == 3:
        return chip("ex_netflow") + chip("ex_balance")
    return "".join(chip(k) for k in ("hl_oi", "hl_funding", "fng") if jby.get(k) and jby[k]["分"] != 0) or chip("fng")


def layer_head(i, lay, comp, logs, as_of, l2):
    seg = next((x for x in (comp or {}).get("段", []) if x["层"] == i), None)
    yday, n = layer_streak(i, lay.get("短"), logs, as_of)
    if yday and yday.get("短") == lay.get("短"):
        cmp_ = T(f"与昨日相同（已持续 {n} 天）", f"Same as yesterday ({n} days running)")
    elif yday:
        rc = ""
        prev_date = next((lg["日期"] for lg in reversed(logs) if lg["日期"] < as_of), None)
        if prev_date and any(prev_date < d <= as_of for d in LAYER_RULE_DATES.get(i, ())):
            rc = T("（规则变更所致，见更正记录）", " (due to a rule change, see Corrections)")
        cmp_ = T(f"昨日：{yday.get('短')} → 今日：{lay.get('短')}", f"Yesterday: {yday.get('短EN') or yday.get('短')} → today: {lay.get('短EN')}") + rc
    else:
        cmp_ = "—"
    mean = esc(LF(seg, "文本")) if seg else ""
    return (f'<div class="card lhead t-{lay.get("tone", "neutral")}"><div class="lh1"><span class="big t-{lay.get("tone", "neutral")}">{esc(LF(lay, "结论") or "—")}</span>'
            f'<span class="mean">{mean}</span></div>'
            f'<div class="lrow"><b>{T("主要依据", "Main evidence")}</b><span class="chips">{basis_chips(i, lay, l2) or "—"}</span></div>'
            f'<div class="lrow"><b>{T("切换条件", "Switch conditions")}</b><span>{esc(switch_text(i, lay, l2))}</span></div>'
            f'<div class="lrow"><b>{T("与昨日比", "Vs yesterday")}</b><span>{esc(cmp_)}</span></div></div>')


def l1_table(rs, v1, rot):
    """M4：L1 判定串改成小表（项目 / 读数 / 状态），原串折叠在下面。"""
    by = {x["key"]: x for x in rs if x and x["层"] == 1}
    rows = []
    w = (v1.get("情境") or {}).get("较差")
    cell_en = {"急升": "surging", "平台": "plateau", "未急升": "not surging", "强": "strong", "弱": "weak", "收窄": "narrowing", "走阔": "widening"}
    if w:
        rows.append((T("情境格（两表取较差）", "Scenario cell (worse of two)"), f"{w[2]:+.1f}% · {T('收涨', 'up')} {w[3]}%",
                     T(f"{w[0]}·{w[1]}", f"{cell_en.get(w[0], w[0])} · {cell_en.get(w[1], w[1])}"), "warn" if w[2] < 0 else "up", None))
    for k in ("real13", "optimism_z", "ndx13", "vix", "baa13", "nfci13", "hy13", "netliq13", "usd13", "stable_expay13", "stable_bullets13", "etf13"):
        x = by.get(k)
        if x:
            rows.append((T(x["名称"], x["名称EN"]), x["显示"], short_zone(LF(x, "区间")), x["tone"], k))
    if rot:
        rows.append((T("资金轮动矩阵", "Rotation matrix"), "—", T(rot["名称"], rot["名称EN"]), rot["tone"], None))
    trs = "".join(f'<tr><td class="l">' + (f'<a href="{ind_href(k)}">{esc(a)}</a>' if k else esc(a)) + f'</td><td>{esc(b)}</td><td class="l">{tone_chip(c, t)}</td></tr>'
                  for a, b, c, t, k in rows)
    l1zh, l1en = R.l1_line(rs, v1, rot)
    return (f'<details class="card fold" open><summary>{T("判定明细", "Verdict details")}</summary><div class="tw" style="margin:0;border:0"><table><thead><tr><th class="l">{T("项目", "Item")}</th>'
            f'<th>{T("读数", "Reading")}</th><th class="l">{T("状态", "State")}</th></tr></thead><tbody>{trs}</tbody></table></div>{l1_raw(T(l1zh, l1en))}</details>')


L1_ANCHOR = {"乐观度 · 美股腿": ("乐观度", "Optimism"), "乐观度 · 信用腿": ("信用", "Credit"), "实际利率（状态变量）": ("实际利率", "Real yield"),
             "流动性闸门（只打折不加仓）": ("流动性闸门", "Liquidity gate"), R.G_SC[0]: ("稳定币", "Stablecoins"), R.G_ETF[0]: ("ETF", "ETF"),
             R.G_FUT[0]: ("期货升水", "Basis"), R.G_SEP[0]: ("单列观察", "Watched"), "联动与监控": ("联动", "Linkage"), "观察项（测过，未达可用标准）": ("观察项", "Watch-only")}


def tag_legend():
    """G7：两组标签的图例（宏观页 Tab 下可展开；口径页放完整版）。"""
    lv = [("核心", "core", "进入本层结论判定。", "Feeds the layer verdict."), ("辅助", "aux", "展示、帮助理解，不进判定。", "Shown for context; not part of the verdict."),
          ("观察", "watch", "测过但没达到可用标准，只看不用。", "Tested but not good enough; watch only."),
          ("状态变量", "state variable", "不单独计分，决定当下落在情境格的哪一行。", "Not scored on its own; picks the row of the scenario grid.")]
    ev = [("已验证", "自有数据实测，且过了噪声 / 稳健性检验。", "Measured on our own data and passed noise / robustness checks."),
          ("已验证·方向", "方向稳定，但样本小或幅度不稳。", "Direction is stable, but samples are few or magnitudes unstable."),
          ("描述读数", "只描述当下所处的位置，不定参数。", "Describes where things stand; sets no parameters."),
          ("监控", "规模或口径还在变，先记录。", "Size or definition is still changing; recorded for now."),
          ("观察项", "测过但没达到可用标准。", "Tested but not usable."),
          ("假设", "机制推理，或只在部分周期成立。", "Reasoned mechanism, or holds only in some cycles."),
          ("已证伪", "测过不成立；仍显示的是为了说明为什么不用。", "Tested and failed; shown only to explain why it is not used."),
          ("记录中", f"自录数据不满 {R.RECORD_DAYS} 天，暂不给分位。", f"Self-recorded for fewer than {R.RECORD_DAYS} days; no percentiles yet.")]
    a = "".join(f'<li><span class="grade lv">{esc(T(z, e))}</span>{esc(T(dz, de))}</li>' for z, e, dz, de in lv)
    b = "".join(f'<li><span class="grade {GRADE_CLS.get(z, "")}">{esc(T(z, GRADE_EN.get(z, z)))}</span>{esc(T(dz, de))}</li>' for z, dz, de in ev)
    c = "".join(f'<li><span class="chip t-{t}"><i></i>{esc(T(z, e))}</span>{esc(T(dz, de))}</li>' for t, z, e, dz, de in (
        ("up", "顺风 / 偏多", "Tailwind", "历史上之后偏多，或支持风险资产。", "Historically followed by gains, or supportive."),
        ("neutral", "中性", "Neutral", "持平、平稳、中间区。", "Flat, calm or mid-range."),
        ("dn", "逆风 / 偏空", "Headwind", "历史上之后偏空，或压制风险资产。", "Historically followed by losses, or a drag."),
        ("warn", "留意", "Watch", "需要留意、只观察，或描述读数 / 记录中。", "Worth watching, descriptive or still recording.")))
    return (f'<div class="legendbox"><div><b>{T("级别（实心小标签）", "Level (solid tag)")}</b><ul>{a}</ul></div>'
            f'<div><b>{T("证据等级（描边小标签）", "Evidence grade (outlined tag)")}</b><ul>{b}</ul></div>'
            f'<div><b>{T("颜色（只按对 BTC 意味着什么）", "Colour (by what it means for BTC)")}</b><ul>{c}</ul></div></div>')


SRC_EN = {"DefiLlama 稳定币": "DefiLlama stablecoins", "CoinMetrics 周期": "CoinMetrics cycle", "CoinMetrics 交易所流量": "CoinMetrics exchange flows",
          "CoinGecko 类目": "CoinGecko categories", "ETF 资金流": "ETF flows", "CME 升水": "CME basis"}


def src_chips(st):
    return "".join(tone_chip(f'{T(k, SRC_EN.get(k, k))} {"✓" if v.get("ok") else "✗"} {(v.get("最新日期") or "")[5:]}', "up" if v.get("ok") else "dn")
                   for k, v in st.items())


def build_macro(L, S, logs):
    as_of = G["as_of"]
    vs, comp, rs = G["VS"], G["COMP"], G["RS"]
    prev_comp = (G.get("PREV_LOG") or {}).get("综合")
    l2 = G.get("L2")
    tlog = G.get("TODAY_LOG")
    st = L.get("源状态") or {}
    if l2:
        st = {**st, "bitview.space (L2)": {"ok": not (l2.get("data_status") or {}).get("stale"), "最新日期": l2.get("data_date")}}
    rot = R.rotation(S, as_of)
    tabs, panels = "", ""
    for i, meta in R.LAYERS.items():
        lay = vs.get(i) or {}
        yday, _ = layer_streak(i, lay.get("短"), logs, as_of)
        chg = f'<span class="chg" title="{esc(T("昨日：", "Yesterday: ") + str((yday or {}).get("短")))}">{T("变", "chg")}</span>' if yday and yday.get("短") != lay.get("短") else ""
        tabs += (f'<a role="tab" id="tab-{i}" href="#layer-{i}" aria-controls="layer-{i}" data-tab="{i}" class="tab{" on" if i == 1 else ""}" aria-selected="{"true" if i == 1 else "false"}">'
                 f'<span class="tn"><i class="dot t-{lay.get("tone", "neutral")}"></i>L{i} <em>{esc(T(meta["名称"], meta["EN"]))}</em></span>'
                 f'<span class="ts t-{lay.get("tone", "neutral")}">{esc(LF(lay, "短") or "—")}</span>{chg}</a>')
        head = layer_head(i, lay, comp, logs, as_of, l2)
        if i == 1:
            groups = cards_by_group(1, as_of)
            anchors = [(T("情境格", "Scenario"), "scen")] + [(T(*L1_ANCHOR.get(g[0], g)), f"grp-1-{n}") for n, (g, _) in enumerate(groups)]
            n_sc = next((n for n, (g, _) in enumerate(groups) if g[0] == R.G_SC[0]), None)
            if n_sc is not None:
                anchors.insert(n_sc + 2, (T("资金矩阵", "Matrix"), "rotm"))
            anchors.append((T("方法与 FAQ", "Method & FAQ"), "l1-faq"))
            bar = '<nav class="anch" aria-label="L1">' + "".join(f'<a href="#{h}" data-anchor="{h}">{esc(t)}</a>' for t, h in anchors) + "</nav>"
            body = ""
            for n, (g, c) in enumerate(groups):
                body += f'<div class="grp" id="grp-1-{n}">{esc(T(*g))}</div>'
                if g[0] == R.G_SC[0]:
                    body += f'<p class="tnote" style="margin:-2px 0 10px">{T("价格先动、稳定币后增，只确认、不埋伏。", "Price moves first, stablecoins follow — confirm, never front-run.")}</p>'
                body += c
                if g[0] == R.G_SC[0]:
                    body += f'<div id="rotm">{rotation_matrix(rot)}</div>'
            content = (bar + l1_table(rs, lay, rot) + f'<div class="note">{esc(T(R.L1_POSITION, R.L1_POSITION_EN))}</div>'
                       + f'<h3 id="scen">{T("情境格：实际利率状态 × 乐观度 / 信用条件", "Scenario grid: real-yield state × optimism / credit")}</h3>{scenario_grid(lay)}'
                       + body + pending_block(1) + f'<div id="l1-faq">{l1_method_faq()}</div>')
        elif i == 2:
            content = l2_tab(l2, as_of) + pending_block(2)
        else:
            groups = cards_by_group(i, as_of)
            content = "".join(f'<div class="grp" id="grp-{i}-{n}">{esc(T(*g))}</div>{c}' for n, (g, c) in enumerate(groups)) + pending_block(i)
            if i == 3 and S.get("ex_netflow"):
                cum = R.s_cum_netflow(S)
                first = min(cum)
                f = G["FILES"]
                content += ('<div class="card chartcard" style="margin-top:12px">'
                            + f'<h3 style="margin-top:0">{T("交易所 BTC 累计净流量 · 全部历史（向下 = 筹码持续离开交易所）", "Cumulative exchange BTC net flow · full history (down = coins leaving)")}</h3>'
                            + chart_div({"v2": True, "src": f["ex_netflow"]["raw"], "fmt": "btcs", "ranges": ["1Y", "3Y", "5Y", "ALL"], "range": "ALL", "group": "l3", "zero": True,
                                         "series": [{"k": "v", "n": T("累计净流量", "Cumulative net flow"), "c": "s1", "area": True}],
                                         "note": T(f"从 {first} 起逐日累加流入 − 流出（CoinMetrics flash 口径）。", f"Inflow − outflow summed daily since {first}.")})
                            + f'<h3>{T("交易所 BTC 余额 · 全部历史", "Exchange BTC balance · full history")} <a class="sub" href="{ind_href("ex_balance")}">{T("看区间与分位 →", "Zones & percentiles →")}</a></h3>'
                            + chart_div({"v2": True, "src": f["ex_balance"]["raw"], "fmt": "btc", "log": True, "ranges": ["1Y", "3Y", "5Y", "ALL"], "range": "ALL", "group": "l3",
                                         "series": [{"k": "v", "n": T("交易所余额", "Exchange balance"), "c": "s3"}]}) + "</div>")
            if i == 4 and G["FILES"].get("fng", {}).get("main"):
                content += ('<div class="card chartcard" style="margin-top:12px">' + f'<h3 style="margin-top:0">{T("恐慌贪婪指数", "Fear & Greed index")}</h3>'
                            + chart_div({"v2": True, "src": G["FILES"]["fng"]["main"], "fmt": "int", "ranges": ["1Y", "3Y", "ALL"], "range": "1Y",
                                         "lines": [{"v": 25, "label": T("恐慌", "fear"), "tone": "neutral"}, {"v": 76, "label": T("贪婪", "greed"), "tone": "warn"}],
                                         "series": [{"k": "v", "n": "F&G", "c": "s1"}]}) + "</div>")
        panels += (f'<section class="layer tabp{" on" if i == 1 else ""}" id="layer-{i}" role="tabpanel" aria-labelledby="tab-{i}" tabindex="-1">'
                   f'<h2 class="ptitle">L{i} · {esc(T(meta["名称"], meta["EN"]))} <span class="sub">{esc(T(meta["问"], meta["问EN"]))}{T("？", "?")} · {esc(T(meta["频率"], meta["频率EN"]))}</span></h2>'
                   f'{head}{content}</section>')
    posts = ALL_POSTS["macro"]
    plist = "".join(f'<li><span class="d">{esc(x["日期"])}</span><span><a href="{U("/macro/" + x["slug"] + "/")}">{esc(x["标题"])}</a>'
                    f'<span class="s">{esc(x["摘要"])}</span></span></li>' for x in posts)
    deep = (f'<h2>{T("宏观深度分析", "Macro deep dives")}</h2><div class="card"><ul class="list">{plist}</ul></div>') if plist else ""   # M10：没有内容前不显示
    body = f"""<div class="ph"><div><div class="eyebrow">Macro · 4-Layer Framework</div><h1>{T("宏观四层仪表盘", "Four-layer macro dashboard")}</h1>
<p class="lede">{T("综合研判把四层合成一句话：周期定方向，宏观管节奏，筹码和情绪用来确认和提醒。下面按层切换，每张指标卡都能点开看全部历史、区间规则和「正常波动范围」。拿不到真实数据的标「待接入」，不拿近似值冒充。",
                   "The overall read rolls four layers into one line: the cycle sets direction, macro sets pace, flows and sentiment confirm and caution. Switch layers below; every card opens its full history, zone rules and normal range. Anything without real data is marked pending.")}</p></div></div>
{comp_block(comp, prev_comp, tlog, full=True)}
<div class="src">{src_chips(st)}</div>
<div class="tabwrap"><nav class="tabs" role="tablist" aria-label="{T("四层", "Four layers")}" data-tabs>{tabs}</nav></div>
<details class="legend-d"><summary>{T("标签说明", "What the tags mean")}</summary>{tag_legend()}</details>
{panels}
{deep}"""
    emit("macro/index.html", T(f"宏观四层仪表盘 · {BRAND}", f"Macro dashboard · {BRAND_EN}"), body, active="macro", chart=True,
         desc=LF(comp or {}, "一句话") or T(PILLARS[0]["desc"], PILLARS[0]["descEN"]))


def write_indicator_data(S):
    """每个指标的判定序列 / 原始水平 / BTC 价格写成全历史文件（两种语言共用，只写一次）；顺带检测数据源回改。"""
    out, revs = {}, []
    btc = S.get("btc_price") or {}
    if btc:
        out["_btc"] = put_series("btc_price", btc, "d", {"name_zh": "BTC 价格", "name_en": "BTC price", "unit": "USD"}, "BTC 价格", revs)
    for ind in R.INDICATORS:
        s = R.series_of(S, ind)
        fq = "w" if ind.get("freq") == "w" else "d"
        since, why, why_en = R.stats_window(S, ind)
        meta = {"name_zh": ind["名称"], "name_en": ind["EN"], "fmt": ind["fmt"], "stats_from": since,
                "stats_from_reason_zh": why, "stats_from_reason_en": why_en,
                "zones": [{"max": c[0], "label_zh": c[1], "label_en": c[2], "bias": R.BIAS.get(c[3], "neutral")} for c in ind["cuts"]]}
        ds = sorted(d for d in s if s[d] is not None)
        if ds:
            meta["valid_from"] = ds[0]
        info = {"main": put_series(ind["key"], s, fq, meta, ind["名称"], revs) if s else None, "freq": fq}
        rk = ind.get("raw")
        if rk:
            rs = R.RAW_DERIVED[rk](S) if rk in R.RAW_DERIVED else (S.get(rk) or {})
            if ind["key"] == "ex_netflow":
                rs = R.s_cum_netflow(S)
            if rs:
                info["raw"] = put_series(f"{ind['key']}-level", rs, "d", {"name_zh": ind["名称"], "name_en": ind["EN"]}, ind["名称"] + "（水平）", revs)
        out[ind["key"]] = info
    # 数据源历史回改：7 天以前的数据变动超过 0.5% 记一笔（更正记录页「数据源历史回改」小节）
    if revs:
        old = load(REV_PATH, []) or []
        old += revs
        with open(REV_PATH, "w", encoding="utf-8") as fh:
            json.dump(old[-500:], fh, ensure_ascii=False, indent=1)
        print(f"  数据源历史回改：{len(revs)} 条（{', '.join(r['指标'] for r in revs[:8])}）")
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


def zone_rules(ind):
    """每个区间的边界文字：默认按代码「v < 上界」写；有「界」字段的（代码里用 ≤ / 分类函数判定的）照它写。"""
    fmt = R.FMT[ind["fmt"]]
    cuts = ind["cuts"]
    if ind.get("界"):
        return [T(a, b) for a, b in zip(ind["界"], ind.get("界EN") or ind["界"])]
    out, prev = [], None
    for c in cuts:
        ub = c[0]
        out.append(f"< {fmt(ub)}" if prev is None else (f"{fmt(prev)} ~ {fmt(ub)}" if ub is not None else f"≥ {fmt(prev)}"))
        prev = ub if ub is not None else prev
    return out


def rec_wait(rec):
    return T(f"满 {rec['required']} 天后给出（已记录 {rec['days']} / {rec['required']} 天）",
             f"Shown after {rec['required']} days ({rec['days']} / {rec['required']} recorded)")


def zone_table(ind, j, stt, rec=None):
    cuts = ind["cuts"]
    if ind["key"] in OWN_PCT:
        return ('<div class="tw"><table><tbody><tr><td class="l wrap">'
                + T(f"只看自身历史分位：< 20 分位 = 自身历史低位，20–80 = 中段，> 80 = 自身历史高位；满 {R.RECORD_DAYS} 天后给出区间判定。",
                    f"Own-history percentile only: <20 low, 20–80 mid, >80 high; zones are judged after {R.RECORD_DAYS} days.") + "</td></tr></tbody></table></div>")
    if len(cuts) == 1:
        return ""
    waiting = rec and not rec["done"]
    share = {z[0]: z[3] for z in (stt or {}).get("区间占比", [])}
    rows = ""
    jz = short_zone(j["区间"]) if j else None
    for c, rng in zip(cuts, zone_rules(ind)):
        pc = share.get(c[1])
        zc = short_zone(c[1])
        cur = bool(jz and (jz == zc or jz.startswith(zc) or (ind["key"] == "real13" and zc == "平台" and "平台" in jz)))
        if waiting:
            bar = ""
        else:
            bar = (f'<span class="zbar" style="width:{max(2, pc * 1.4):.0f}px;background:var({TONE_VAR[c[3]]})"></span>{pc:.1f}%' if pc is not None else "—")
        rows += (f'<tr class="{"cur" if cur else ""}"><td class="l">{tone_chip(T(c[1], c[2]), c[3])}{" ◀ " + T("当前", "now") if cur else ""}</td>'
                 f'<td>{esc(rng)}</td>' + ("" if waiting else f'<td class="l" style="min-width:180px">{bar}</td>') + '</tr>')
    if ind["key"] == "real13":
        rows += (f'<tr><td class="l wrap" colspan="3" style="color:var(--ink2)">'
                 + T("「平台」再按水平分：≥ 1.0% = 高位平台，< 1.0% = 低位平台。", "'Plateau' splits by level: ≥1.0% high, <1.0% low.") + "</td></tr>")
    th3 = "" if waiting else f'<th class="l">{T("历史上落在这个区间的时间占比", "Share of history in this zone")}</th>'
    tail = f'<p class="tnote">{T("区间判定用固定阈值，照常给出；历史占比", "Zones use fixed thresholds and are shown now; the historical share is ")}{esc(rec_wait(rec))}。</p>' if waiting else ""
    return (f'<div class="tw"><table><thead><tr><th class="l">{T("区间", "Zone")}</th><th>{T("规则（判定序列）", "Rule")}</th>{th3}</tr></thead>'
            f'<tbody>{rows}</tbody></table></div>{tail}')


def range_block(S, ind, j, stt, since, why=""):
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
    why_t = f"{T('起点：', 'Start: ')}{esc(why)}。" if why else ""
    return f"""<div class="stats">
<div><div class="k">{T("当前读数", "Current")}</div><div class="v">{esc(j["显示"]) if j else "—"}</div><div class="s">{T("历史第", "Percentile")} {f"{cur_p:.0f}" if cur_p is not None else "—"}{T(" 百分位", "")}</div></div>
<div><div class="k">{T("正常波动范围（p10–p90）", "Normal range (p10–p90)")}</div><div class="v">{esc(fmt(stt["p10"]))} ~ {esc(fmt(stt["p90"]))}</div><div class="s">{T("历史上 80% 的时间在这里", "80% of history")}</div></div>
<div><div class="k">{T("常见区间（p25–p75）", "Typical (p25–p75)")}</div><div class="v">{esc(fmt(stt["p25"]))} ~ {esc(fmt(stt["p75"]))}</div><div class="s">{T("中位", "median")} {esc(fmt(stt["p50"]))}</div></div>
<div><div class="k">{T("历史极值", "Extremes")}</div><div class="v">{esc(fmt(stt["min"]))} ~ {esc(fmt(stt["max"]))}</div><div class="s">{esc(win)}</div></div>
</div>{gauge}
<p class="tnote">{T("统计窗口：", "Window: ")}{esc(win)}。{why_t}{T("L1 宏观指标按研究的方法规则只用 2018 年以后；链上周期类从 2012 年起；百分比变化类再排除早期基数过小的时段（规则见「口径与规则 · 统计窗口」）。分位只描述读数在自己历史里的位置，不是买卖信号。",
                                                "L1 macro gauges use post-2018 data (method rule); on-chain cycle gauges start in 2012; percentage-change gauges also drop the early small-base period (see Methodology · statistics window). Percentiles describe position in history — not trade signals.")}</p>"""


def feedback_btn(title):
    """G10：一键在 X 上 @ 站长，带上当前页面标题和链接。"""
    acct = SITE_CFG.get("反馈账号", "Uncle_Onchain")
    url = f"https://{DOMAIN}{U(G['url'])}"
    text = T(f"@{acct} 反馈：{title} ", f"@{acct} Feedback: {title} ")
    from urllib.parse import quote
    href = f"https://x.com/intent/post?text={quote(text)}&url={quote(url)}"
    return f'<a class="btn ghost fb" href="{href}" target="_blank" rel="noopener">✎ {T("反馈 / 纠错", "Feedback / report an error")}</a>'


def rec_bar(rec):
    if not rec:
        return ""
    pct = min(100, rec["days"] / rec["required"] * 100)
    n, req = rec["days"], rec["required"]
    since = T(f"自 {rec['since']} 起开始记录", f"recording since {rec['since']}") if rec.get("since") else ""
    txt = T(f"已记录 {n} / {req} 天 · 满 {req} 天后给出区间判定", f"Recording · {n} / {req} days · zone judgment after {req} days")
    if rec["done"]:
        txt = T(f"已记录 {n} 天", f"{n} days recorded")
    chip = f'<span class="chip t-warn"><i></i>{T("记录中", "Recording")}</span>' if not rec["done"] else ""
    return (f'<div class="recbar">{chip}<div class="rb"><i style="width:{pct:.0f}%"></i></div>'
            f'<span class="rt">{txt}{" · " + since if since else ""}</span></div>')


# ---------------------------------------------------------------- 统一的空状态（G5）：图标 + 状态名 + 一句话原因 + 预计 / 条件
EMPTY_KIND = {"pending": ("待接入", "Pending", "◌"), "recording": ("记录中", "Recording", "◔"), "delay": ("延迟", "Delayed", "⏱"),
              "prep": ("筹备中", "In preparation", "◇"), "none": ("暂无内容", "Nothing yet", "○"), "retired": ("已停用", "Retired", "⊘")}


def empty_state(kind, title, reason, cond, progress=None, raw=False):
    zh, en, ic = EMPTY_KIND.get(kind, EMPTY_KIND["none"])
    pr = f'<div class="rb"><i style="width:{progress:.0f}%"></i></div>' if progress is not None else ""
    cond_h = (cond if raw else esc(cond)) if cond else ""
    return (f'<div class="es es-{kind}"><span class="ic" aria-hidden="true">{ic}</span><div><b>{esc(T(zh, en))} · {esc(title)}</b>'
            f'<p>{esc(reason)}</p>{f"<p class=c>{cond_h}</p>" if cond_h else ""}{pr}</div></div>')


def asof_txt(d, as_of):
    """卡片上的数据日期：超过 30 天或跨年时写完整年份（G8）。"""
    if not d:
        return "—"
    if as_of and (d[:4] != as_of[:4] or R.days_between(d, as_of) > 30):
        return d
    return d[5:]


def ind_layer_list(layer):
    return sorted([x for x in R.INDICATORS if x["层"] == layer], key=lambda x: x["序"])


def build_indicator_pages(L, S, logs, files):
    as_of = G["as_of"]
    halv = [{"date": d, "label": T("减半", "halving")} for d in ("2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20")]
    for ind in R.INDICATORS:
        key, meta = ind["key"], R.LAYERS[ind["层"]]
        name = T(ind["名称"], ind["EN"])
        j = G["JBY"].get(key)
        rec = R.recording_info(S, ind)
        waiting = rec and not rec["done"]
        since, why, why_en = R.stats_window(S, ind)
        stt = None if waiting else (R.history_stats(S, ind, since) or R.history_stats(S, ind))
        f = files.get(key) or {}
        cuts = ind["cuts"]
        lines = []
        if key not in OWN_PCT:
            for n, c in enumerate(cuts):
                if c[0] is not None:
                    nxt = cuts[n + 1]
                    lines.append({"v": round(c[0], 6), "label": "↑ " + short_zone(T(nxt[1], nxt[2]))[:9], "tone": nxt[3]})
        zone = [] if key in OWN_PCT or len(cuts) == 1 else [{"ub": c[0], "n": T(c[1], c[2]), "t": c[3]} for c in cuts]
        l2 = ind["层"] == 2
        rngs = ["1Y", "3Y", "5Y", "ALL"] + (["CYC"] if l2 else [])
        shade = [{"to": since, "label": T(why, why_en)}] if since else []
        mk = halv if l2 else []
        btc = files.get("_btc")
        charts = ""
        fresh = T("数据源每周更新" if ind.get("freq") == "w" else "数据源每日更新", "updated weekly" if ind.get("freq") == "w" else "updated daily")
        if f.get("main"):
            cfg = {"v2": True, "src": f["main"], "fmt": ind["fmt"], "ranges": rngs, "range": "ALL", "group": "d", "lines": lines, "zone": zone,
                   "zero": ind["fmt"] in ("pcts", "pp", "xs", "btcs", "usds"), "clip": True, "clipFrom": since, "shade": shade, "markers": mk, "btc": btc,
                   "weekly": ind.get("freq") == "w", "cyc": G.get("CYC"), "hint": "",
                   "series": [{"k": "v", "n": name, "c": "s1", "area": ind["fmt"] in ("btcs", "usds")}]}
            if stt:
                cfg["band"] = {k: stt[k] for k in ("p10", "p25", "p50", "p75", "p90")}
            charts += (f'<h2>{T("判定序列 · 全部历史", "Judged series · full history")} <span class="sub">{esc(T(ind["依据"], ind["依据EN"]))} · '
                       f'{T("虚线 = 区间分界；底色 = 区间（绿 = 历史上偏多 / 红 = 偏空 / 黄 = 留意）；蓝色带 = 正常波动范围；灰底 = 不计入统计", "dashed = zone boundaries; tint = zone bias (green = tailwind / red = headwind / yellow = watch); blue band = normal range; grey = excluded from statistics")}</span></h2>'
                       f'<div class="card chartcard">{chart_div(cfg)}</div>')
        if f.get("raw"):
            rt = RAW_TITLE.get(key, (ind["名称"], ind["EN"]))
            rawfmt = "btcs" if key == "ex_netflow" else ind.get("rawfmt", "x")
            lg = key in ("ndx13", "ex_balance") or rawfmt in ("usd", "idx") and key not in ("netliq13",)
            cfg = {"v2": True, "src": f["raw"], "fmt": rawfmt, "ranges": rngs, "range": "ALL", "group": "d", "log": lg, "shade": shade, "markers": mk,
                   "note": T("对数坐标：同样的高度代表同样的涨跌幅，比如 1 万→2 万和 5 万→10 万一样高。", "Log scale: equal heights mean equal percentage moves — 10k→20k is as tall as 50k→100k.") if lg else "",
                   "zero": rawfmt in ("btcs", "usds"), "cyc": G.get("CYC"), "series": [{"k": "v", "n": T(rt[0], rt[1]), "c": "s3", "area": rawfmt == "btcs"}]}
            if key == "real13":
                cfg["lines"] = [{"v": 1.0, "label": T("1.0% 高位线", "1.0% line"), "tone": "warn"}]
            charts += f'<h2>{esc(T(rt[0], rt[1]))}</h2><div class="card chartcard">{chart_div(cfg)}</div>'
        if btc:
            charts += (f'<h2>{T("对照：BTC 价格（对数坐标）", "For reference: BTC price (log scale)")} <span class="sub">{T("同一时间轴，悬停联动", "same time axis, linked hover")}</span></h2>'
                       f'<div class="card chartcard">{chart_div({"v2": True, "src": btc, "fmt": "price", "log": True, "ranges": rngs, "range": "ALL", "group": "d", "markers": mk, "cyc": G.get("CYC"), "series": [{"k": "v", "n": "BTC", "c": "s2"}]})}</div>')
        if not f.get("main"):
            charts = empty_state("pending", T("暂无数据", "No data yet"), T("数据源接通后的下一次每日运行会生成。", "Appears after the next daily run once the source is connected."), "") + charts
        head = ""
        if j:
            stale = f' · <span class="t-warn">{T("滞后", "lag")} {R.days_between(j["截至"], as_of)} {T("天", "days")}</span>' if j["过期"] else ""
            head = (f'<div class="glass verdict"><div class="body"><div class="lbl">{T("当前读数", "Current reading")} · {T("截至", "as of")} {j["截至"]} · {fresh}{stale}</div>'
                    f'<div class="txt" style="font-family:var(--mono);font-size:26px">{esc(j["显示"])}</div>'
                    
                    + ("" if (waiting and key in OWN_PCT) else f'<div class="chips">{tone_chip(LF(j, "区间"), j["tone"])}<span class="chip">{esc(LF(j, "依据"))}</span></div>')
                    + f'{rec_bar(rec)}</div></div>')
        itp = R.interpret(S, ind, j, stt, since) if j and not waiting else None
        itp_h = f'<div class="card interp"><b>{T("当前解读", "What this reading means")}</b><p>{esc(T(*itp))}</p></div>' if itp else ""
        zt = zone_table(ind, j, stt, rec)
        rb = range_block(S, ind, j, stt, since, T(why, why_en))
        sw = R.zone_switches(S, ind) if not waiting else []
        sw_h = ""
        if sw:
            trs = "".join(f'<tr><td class="l">{x["日期"]}</td><td class="l">{esc(short_zone(T(x["从"], x["从EN"])))} → {tone_chip(short_zone(T(x["到"], x["到EN"])), x["tone"])}</td>'
                          f'<td>{x["天数"]}{T(" 天", "d")}{T("（持续中）", " (ongoing)") if x["进行中"] else ""}</td><td>{R.FMT["price"](x["BTC"]) if x["BTC"] else "—"}</td></tr>' for x in sw)
            sw_h = (f'<h2>{T("状态切换记录", "Zone switches")} <span class="sub">{T("最近 10 次", "last 10")}</span></h2><div class="tw"><table><thead><tr><th class="l">{T("日期", "Date")}</th>'
                    f'<th class="l">{T("从 → 到", "From → to")}</th><th>{T("持续", "Lasted")}</th><th>{T("当时 BTC", "BTC then")}</th></tr></thead><tbody>{trs}</tbody></table></div>')
        sib = ind_layer_list(ind["层"])
        k = sib.index(ind)
        prv = sib[k - 1] if k > 0 else None
        nxt_ = sib[k + 1] if k + 1 < len(sib) else None
        pager = (f'<div class="pager">' + (f'<a href="{ind_href(prv["key"])}">← {esc(T(prv["名称"], prv["EN"]))}</a>' if prv else "<span></span>")
                 + f'<a href="{U("/macro/")}#layer-{ind["层"]}">{T("回到", "Back to ")} L{ind["层"]}</a>'
                 + (f'<a href="{ind_href(nxt_["key"])}">{esc(T(nxt_["名称"], nxt_["EN"]))} →</a>' if nxt_ else "<span></span>") + "</div>")
        lvl = T(ind["级别"], LEVEL_EN.get(ind["级别"], "")) + (f" · {T(ind['级别注'], ind['级别注EN'])}" if ind.get("级别注") else "")
        ref = f'<span class="chip">{T("出处", "Source study")}{CN}{esc(T(ind["出处"], ind["出处EN"]))}</span>' if ind.get("出处") else ""
        note_mvrv = (f'<div class="note">{T("2026-10-08 起按新口径展示：原单指标卡已并入 L2 状态机，这里是状态机的输入之一。见", "Shown under the new rules since 2026-10-08: the old single-gauge card was folded into the L2 state machine; this is one of its inputs. See ")}'
                     f'<a href="{U("/corrections/")}">{T("更正记录", "Corrections")}</a>{T("。", ".")}</div>') if key == "mvrv" else ""
        vf = ""
        if l2 and f.get("main"):
            ds = sorted(d for d in R.series_of(S, ind))
            if ds:
                vf = f'<p class="tnote">{T(f"这个指标从 {ds[0]} 起才有值（数据源起点或均线 / 滚动窗口攒满所需天数）。", f"This gauge has values from {ds[0]} (data start or the days needed to fill its window).")}</p>'
        rec_note = ""
        body = f"""{crumbs([(T("宏观仪表盘", "Macro"), "/macro/"), (f'L{ind["层"]} · {T(meta["名称"], meta["EN"])}', f'/macro/#layer-{ind["层"]}'), (name, None)])}
{note_mvrv}
<div class="ph"><div><div class="eyebrow">L{ind["层"]} · {esc(T(ind.get("组") or meta["名称"], ind.get("组EN") or meta["EN"]))}</div>
<h1>{esc(name)}</h1><p class="lede">{esc(T(ind["说明"], ind["说明EN"]))}</p>
<div class="chips" style="margin-top:10px"><span class="chip">{T("来源", "Source")}{CN}{esc(src_t(ind["来源"]))}</span><span class="chip">{T("级别", "Level")}{CN}{esc(lvl)}</span>{grade_chip(ind.get("等级"), ind)}{ref}</div></div></div>
{head}
{itp_h}
<h2>{T("这个数字落在哪：区间规则与历史占比", "Zones: rules and how often each occurred")}</h2>{zt or empty_state("none", T("只看趋势", "Trend only"), T("这个指标没有区间判定，只看走势。", "This gauge has no zones; read the trend."), "")}
<h2>{T("正常波动范围", "Normal range")}</h2>{rb or empty_state("recording", T("历史还不够长", "History still short"), T("自录指标，从开始记录那天起逐日积累。", "Self-recorded, accumulating daily since recording began."), rec_wait(rec) if rec else T("样本不足。", "Not enough data."))}
{charts}
{vf}
{sw_h}
{pager}
<div class="pgfoot"><p class="tnote">{T("区间规则和证据等级的出处见", "Rules and evidence grades: ")}<a href="{U("/methodology/")}">{T("口径与规则", "Methodology")}</a>{T("；规则改动记在", "; rule changes are logged in ")}<a href="{U("/corrections/")}">{T("更正记录", "Corrections")}</a>{T("。", ".")}</p>{feedback_btn(name)}</div>"""
        emit(f"macro/{key}/index.html", f"{name} · {T('宏观仪表盘', 'Macro')} · {T(BRAND, BRAND_EN)}", body, active="macro", chart=True,
             desc=(f"{name} {j['显示']} · {T(j['区间'], j['区间EN'])} · " if j else "") + T(ind["说明"], ind["说明EN"]))
    # 已停用指标：轻量说明页（D5），旧推特链接不落到空页面
    for ind in R.RETIRED:
        name = T(ind["名称"], ind["EN"])
        body = f"""{crumbs([(T("宏观仪表盘", "Macro"), "/macro/"), (f'L{ind["层"]} · {T(R.LAYERS[ind["层"]]["名称"], R.LAYERS[ind["层"]]["EN"])}', f'/macro/#layer-{ind["层"]}'), (name, None)])}
<div class="ph"><div><div class="eyebrow">{T("已停用", "Retired")}</div><h1>{esc(name)}</h1></div></div>
{empty_state("retired", T(f"这个指标已于 {ind['停用']} 停用", f"Retired on {ind['停用']}"), T(ind["原因"], ind["原因EN"]),
             f'{T("相关内容现在在：", "Now covered in: ")}<a href="{U(ind["去处"])}">{esc(T(ind["去处名"], ind["去处名EN"]))}</a> · <a href="{U("/corrections/")}">{T("详见更正记录", "see Corrections")}</a>', raw=True)}
<div class="pgfoot">{feedback_btn(name)}</div>"""
        emit(f"macro/{ind['key']}/index.html", f"{name} · {T('已停用', 'Retired')} · {T(BRAND, BRAND_EN)}", body, active="macro",
             desc=T(f"{ind['名称']} 已于 {ind['停用']} 停用：{ind['原因']}", f"{ind['EN']} was retired on {ind['停用']}: {ind['原因EN']}"))


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
<div class="card" style="padding:14px 18px;font-size:13px;color:var(--ink2)">Arc {esc(arc.get("日期") or "")}{CN}{T("发射台合计", "launchpads")} <b class="num">{f_usd(arc.get("发射台手续费"))}</b> ·
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
    d = obj.get("日期") or obj.get("止") or ""
    notes = []
    if obj.get("版本") != 2:
        if LANG["v"] == "en":
            return '<div class="note">This entry was written before bilingual logs (and under the pre-2026-10-02 L1 rules), so it is shown in Chinese.</div>'
        if obj.get("类型") == "日":
            notes.append("本篇按 2026-10-02 之前的旧 L1 规则写成")
    if obj.get("类型") == "日" and d and d < "2026-10-08":
        notes.append(T("本篇的 L2 按 2026-10-08 之前的旧规则（MVRV Z-Score 区间）写成，综合研判只由 L1 和 L4 组合",
                       "L2 in this entry follows the pre-2026-10-08 rule (MVRV Z-Score zone) and the overall read combined only L1 and L4"))
    if not notes:
        return ""
    return f'<div class="note">{esc("；".join(notes) if LANG["v"] == "zh" else "; ".join(notes))}{T("。按冻结规则保持原样，规则变更见", ". Kept as written under the freeze rule; see ")}<a href="{U("/corrections/")}">{T("更正记录", "Corrections")}</a>{T("。", ".")}</div>'


RULE_SEP = [("2026-10-02", "规则变更：L1 宏观层重建，此前日志按旧规则", "Rule change: L1 rebuilt; earlier logs follow the old rules"),
            ("2026-10-04", "规则变更：L1-B 加密资金通道修订", "Rule change: L1-B crypto funding channels revised"),
            ("2026-10-08", "规则变更：L2 改为状态机，此前的 L2 结论按旧规则（MVRV Z-Score 区间）", "Rule change: L2 became a state machine; earlier L2 verdicts follow the old rule (MVRV Z-Score zone)")]


def build_journal(S, logs, weeks, months, sd):
    idx = {lg["日期"]: i for i, lg in enumerate(logs)}
    for lg in logs:
        i = idx[lg["日期"]]
        prev_ = logs[i - 1]["日期"] if i > 0 else None
        next_ = logs[i + 1]["日期"] if i + 1 < len(logs) else None
        layers = ""
        for lay in lg["层"]:
            l2s = lg.get("L2") if lay["层"] == 2 else None
            if l2s:
                txt = l2s.get("摘要") if LANG["v"] == "zh" else l2s.get("摘要EN")
                body_ = (f'<div class="card l2sum" style="padding:12px 16px">'
                         + "".join(f"<div>{esc(x)}</div>" for x in (txt or "").split("\n"))
                         + (f'<div class="tnote">⚠ {T("当天 L2 数据源有延迟，用了缓存。", "L2 used cached data that day.")}</div>' if l2s.get("数据延迟") else "")
                         + "</div>")
                if lay.get("读数"):
                    body_ += readings_table(lay)
            else:
                body_ = readings_table(lay)
            if lay["层"] == 1:
                body_ += l1_raw(lg)
            layers += f'<h3>L{lay["层"]} · {esc(LF(lay, "名称"))} {tone_chip(LF(lay, "结论"), lay["tone"])}</h3>{body_}'
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
        srcs = "".join(tone_chip(f'{T(k, SRC_EN.get(k, k))} {"✓" if v.get("ok") else "✗"}', "up" if v.get("ok") else "dn") for k, v in (lg.get("数据源") or {}).items())
        nm_en = {**{x["名称"]: x["EN"] for x in R.REGISTRY}, "L2 周期状态机": "L2 cycle state machine", "BTC 未平仓合约（7 日变化）": "BTC open interest (7d change)"}
        miss = (f'<p class="tnote">{T("当天缺失的核心指标：", "Core indicators missing that day: ")}{esc(T("、".join(lg["核心缺失"]), ", ".join(nm_en.get(x, x) for x in lg["核心缺失"])))}</p>'
                if lg.get("核心缺失") else "")
        patch = (f'<p class="tnote">⚠ {T("本篇为补录：首次生成于", "Re-run: first generated")} {esc(lg.get("首次生成UTC") or "")} UTC'
                 f'{T("，当天数据源晚到后按冻结规则覆盖一次。", ", overwritten once after late data per the freeze rule.")}</p>') if lg.get("补录") else ""
        heroes, cards = hero_cards(S, lg["日期"], sd if lg is logs[-1] else None)
        share_obj = {"title": T(f"链上终端 · {lg['日期']} 解读", f"Onchain terminal · {lg['日期']}"), "date": lg["日期"], "sub": LF(lg["综合"], "一句话"),
                     "html": share_payload_home(lg.get("综合"), cards, lg.get("预警")), "file": f"uncleonchain-journal-{lg['日期']}.png"}
        no_cm = empty_state("none", T("今天没有人工点评", "No hand-written note today"), T("上面是规则化自动解读。", "The above is rule-based."), "")
        pager_prev = f'<a href="{U("/journal/" + prev_ + "/")}">← {prev_}</a>' if prev_ else '<span></span>'
        pager_next = f'<a href="{U("/journal/" + next_ + "/")}">{next_} →</a>' if next_ else '<span></span>'
        body = f"""{crumbs([(T("解读日志", "Journal"), "/journal/"), (lg["日期"], None)])}
<div class="ph"><div><div class="eyebrow">Daily Log · {T("每日解读", "daily")}</div><h1>{lg["日期"]} {T("解读日志", "log")}</h1></div>
<div class="stamp">{T("解读生成", "Log generated")} <b>{esc(lg["生成时间UTC"])} UTC</b><br>{T("写入即冻结 · 规则见「口径与规则」", "Frozen once written · rules in Methodology")}</div></div>
{old_note(lg)}
{verdict_block(lg, link=True)}
{patch}
<h2>{T("大叔点评", "Uncle's note")}</h2>{f'<div class="cmt article">{cm}</div>' if cm else no_cm}
<h2>{T("异动预警", "Alerts")}</h2>{alert_board(lg, title=T("当日预警", "Alerts of the day"), share_id="shareLog")}
<h2>{T("四层读数", "Four-layer readings")} <span class="sub">{T("当天冻结值；最新值见宏观仪表盘", "frozen that day; latest values on the Macro dashboard")}</span></h2>{layers}
{miss}
{lp_html}
<h2>{T("数据源状态", "Data sources")}</h2><div class="src">{srcs}</div>
<div class="pager">{pager_prev}<a href="{U("/journal/")}">{T("全部日志", "All logs")}</a>{pager_next}</div>"""
        js = f"<script>function shareLog(){{ucShare({json.dumps(share_obj, ensure_ascii=False)})}}</script>"
        emit(f'journal/{lg["日期"]}/index.html', f'{lg["日期"]} {T("解读日志", "log")} · {T(BRAND, BRAND_EN)}', body, active="journal", share=True,
             scripts=js, desc=LF(lg["综合"], "一句话"))

    def review_note(rv):
        hits = [(d, zh, en) for d, zh, en in RULE_SEP if rv["起"] <= d <= rv["止"]]
        if not hits:
            return ""
        t = "；".join(f"{d} {zh}" for d, zh, en in hits) if LANG["v"] == "zh" else "; ".join(f"{d} {en}" for d, zh, en in hits)
        return (f'<div class="note">{T("注：这期间有规则变更——", "Note: rules changed during this period — ")}{esc(t)}{T("。下面各层结论的切换有一部分是规则变更所致，不是市场变化（见", ". Some verdict switches below come from the rule change, not the market (see ")}'
                f'<a href="{U("/corrections/")}">{T("更正记录", "Corrections")}</a>{T("）。", ").")}</div>')

    def review_page(rv, kind_slug, title):
        rows = "".join(f'<tr><td class="l">{esc(LF(x, "名称"))}</td><td>{esc(x["期初"])}</td><td>{esc(x["期末"])}</td><td>{esc(x["变化"])}</td>'
                       f'<td>{esc(x["低"])} ~ {esc(x["高"])}</td><td class="l">{esc(short_zone(LF(x, "期初区间")))} → {tone_chip(short_zone(LF(x, "期末区间")), x["tone"])}</td></tr>'
                       for x in rv["指标"])
        vrows = "".join(f'<tr><td class="l">L{v["层"]} · {esc(LF(v, "名称"))}</td><td class="l">{esc(en_fix(v["期初"]) or v["期初"])} → {esc(en_fix(v["期末"]) or v["期末"])}</td>'
                        f'<td class="l wrap">{esc(T("、", ", ").join(f"{en_fix(k) or k}×{n}" for k, n in v["分布"].items()) or "—")}</td>'
                        f'<td>{v["切换次数"]}</td></tr>' for v in rv["结论"])
        al = "".join(f'<li><span class="d">{a["日期"][5:]}</span><span class="lv {"h" if a["级别"] == "高" else "m"}">{T(a["级别"], "H" if a["级别"] == "高" else "M")}</span>{esc(alert_text(a))}</li>' for a in rv["预警"])
        lp = rv.get("发射台") or {}
        prow = "".join(f'<tr><td class="l">{esc(p["名称"])}</td><td>{f_usd(p["期间"])}</td><td>{f_usd(p["上期"])}</td>'
                       f'<td>{fmt_delta(p["变化"], pct_input=True)}</td></tr>' for p in lp.get("平台") or [])
        cm = commentary(rv["标签"])
        no_cm = empty_state("none", T("人工复盘点评待补充", "No hand-written review yet"), T("规则化复盘见下方。", "The rule-based review is below."), "")
        no_al = empty_state("none", T("期间没有触发预警", "No alerts"), T("阈值规则见「口径与规则」。", "Thresholds are in Methodology."), "")
        return f"""{crumbs([(T("解读日志", "Journal"), "/journal/"), (title, None)])}
<div class="ph"><div><div class="eyebrow">{kind_slug.title()} Review</div><h1>{esc(title)}</h1>
<p class="lede">{rv["起"]} ~ {rv["止"]} · {T("期间日志", "logs")} {rv["日志天数"]} {T("篇", "")}</p></div><div class="stamp">{T("生成于", "Generated")} <b>{esc(rv["生成时间UTC"])} UTC</b></div></div>
{old_note(rv)}
{review_note(rv)}
<div class="glass verdict"><div class="body"><div class="lbl">{T("一句话复盘", "Summary")}</div><div class="txt">{esc(en_fix(LF(rv, "一句话")) or "(Chinese only — written before bilingual logs)")}</div></div></div>
<h2>{T("大叔点评", "Uncle's note")}</h2>{f'<div class="cmt article">{cm}</div>' if cm else no_cm}
<h2>{T("核心指标区间变化", "Core indicators over the period")}</h2><div class="tw"><table><thead><tr><th class="l">{T("指标", "Indicator")}</th><th>{T("期初", "Start")}</th><th>{T("期末", "End")}</th><th>{T("变化", "Change")}</th><th>{T("区间低 ~ 高", "Low ~ high")}</th><th class="l">{T("区间判定", "Zone")}</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>{T("各层结论分布", "Verdicts by layer")}</h2><div class="tw"><table><thead><tr><th class="l">{T("层", "Layer")}</th><th class="l">{T("期初 → 期末", "Start → end")}</th><th class="l">{T("分布（天数）", "Distribution (days)")}</th><th>{T("切换次数", "Switches")}</th></tr></thead><tbody>{vrows}</tbody></table></div>
<h2>{T("发射台", "Launchpads")} <span class="sub">Top60 {f_usd(lp.get("赛道期间合计"))} · {T("较上期", "vs prior")} {fmt_delta(lp.get("赛道变化"), pct_input=True)}</span></h2>
<div class="tw"><table><thead><tr><th class="l">{T("平台", "Platform")}</th><th>{T("期间手续费", "Fees")}</th><th>{T("上期", "Prior")}</th><th>{T("变化", "Change")}</th></tr></thead><tbody>{prow}</tbody></table></div>
<h2>{T("期间预警", "Alerts")}{T("（", " (")}{len(rv["预警"])}{T("）", ")")}</h2>{f'<div class="card"><ul class="alerts">{al}</ul></div>' if al else no_al}"""

    for wk in weeks:
        t_ = T(f'{wk["标签"]} 周复盘', f'{wk["标签"]} weekly review')
        emit(f'journal/week/{wk["标签"]}/index.html', f'{t_} · {T(BRAND, BRAND_EN)}', review_page(wk, "week", t_), active="journal", desc=LF(wk, "一句话"))
    for mo in months:
        t_ = T(f'{mo["标签"]} 月复盘', f'{mo["标签"]} monthly review')
        emit(f'journal/month/{mo["标签"]}/index.html', f'{t_} · {T(BRAND, BRAND_EN)}', review_page(mo, "month", t_), active="journal", desc=LF(mo, "一句话"))

    # ---- 日志列表（P4）：按月分组；规则变更那天插分隔行；和前一天不同的层高亮；标题和前一天相同时变浅
    by_month = {}
    rlog = list(reversed(logs))
    first_v2 = next((lg["日期"] for lg in logs if lg.get("版本") == 2), None)
    place = {"2026-10-02": first_v2 or "2026-10-02"}         # L1 重建当天的日志还是旧规则写的，分隔行放到第一篇新规则日志下面
    for n, lg in enumerate(rlog):
        prev = rlog[n + 1] if n + 1 < len(rlog) else None
        pl = {x["层"]: x.get("短") for x in (prev or {}).get("层", [])}
        same = prev and LF(prev["综合"], "一句话") == LF(lg["综合"], "一句话")
        chips = " ".join(f'<span class="chip t-{x["tone"]}{" hl" if prev and pl.get(x["层"]) != x.get("短") else ""}"><i></i>{esc(en_fix(LF(x, "短")) or "—")}</span>' for x in lg["层"])
        line = en_fix(LF(lg["综合"], "一句话")) or "(Chinese only — written before bilingual logs)"
        row = (f'<li class="{"same" if same else ""}"><span class="d">{lg["日期"]}<small>{T("生成", "gen.")} {esc((lg.get("生成时间UTC") or "")[11:16])} UTC</small></span>'
               f'<span><a href="{U("/journal/" + lg["日期"] + "/")}">{esc(line)}</a>'
               f'{" <em class=samel>" + T("同前一日", "same as the day before") + "</em>" if same else ""}<span class="s">{chips}</span></span>'
               f'<span class="x chip">{len(lg.get("预警") or [])} {T("条预警", "alerts")}</span></li>')
        seps = list(RULE_SEP)
        if (lg.get("综合") or {}).get("规则") == "四层合成" and not ((prev or {}).get("综合") or {}).get("规则") == "四层合成":
            seps.append((lg["日期"], "规则变更：综合研判改为四层合成，此前日志只由 L1 和 L4 组合", "Rule change: the overall read now combines all four layers; earlier logs combined only L1 and L4"))
        for d, zh, en in seps:
            pd_ = place.get(d, d)
            anc = "2026-10-08-comp" if "四层合成" in zh else d
            rid = "2026-10-08-comp" if "四层合成" in zh else d
            if lg["日期"] == pd_ or (prev and prev["日期"] < pd_ < lg["日期"]):
                row += f'<li class="rsep" id="rule-{rid}"><span class="d">{d}</span><span>⚑ {esc(T(zh, en))} · <a href="{U("/corrections/")}#rc-{anc}">{T("见更正记录", "see Corrections")}</a></span></li>'
        by_month.setdefault(lg["日期"][:7], []).append(row)
    cur_m = max(by_month) if by_month else None
    dl = "".join(f'<details class="card mgrp"{" open" if m == cur_m else ""}><summary>{m} <span class="sub">{sum(1 for r in rows if "rsep" not in r)} {T("篇", "logs")}</span></summary><ul class="list">{"".join(rows)}</ul></details>'
                 for m, rows in sorted(by_month.items(), reverse=True))
    wl = "".join(f'<li><span class="d">{w["标签"]}</span><span><a href="{U("/journal/week/" + w["标签"] + "/")}">{esc(en_fix(LF(w, "一句话")) or "(Chinese only)")}</a>'
                 f'<span class="s">{w["起"]} ~ {w["止"]}{T("（含规则变更）", " (includes a rule change)") if any(w["起"] <= d <= w["止"] for d, *_ in RULE_SEP) else ""}</span></span></li>' for w in reversed(weeks))
    ml = "".join(f'<li><span class="d">{m["标签"]}</span><span><a href="{U("/journal/month/" + m["标签"] + "/")}">{esc(en_fix(LF(m, "一句话")) or "(Chinese only — written before bilingual logs)")}</a></span></li>' for m in reversed(months))
    e1 = empty_state("none", T("还没有月复盘", "No monthly review yet"), T("第一篇月复盘会在下个月 1 日自动生成。", "The first monthly review comes on the 1st."), "")
    e2 = empty_state("none", T("还没有周复盘", "No weekly review yet"), T("第一篇周复盘会在下周一自动生成。", "The first weekly review comes next Monday."), "")
    e3 = empty_state("none", T("还没有日志", "No logs yet"), T("第一篇日志会在下一次每日运行时写入。", "The first log comes with the next daily run."), "")
    body = f"""<div class="ph"><div><div class="eyebrow">Journal</div><h1>{T("解读日志", "Journal")}</h1>
<p class="lede">{T(f"日更每天 UTC {MAIN_TIME} 定时运行（推送代码时也会额外跑一次），按「口径与规则」里公开的规则写一篇解读日志：综合研判（四层合成）、四层读数、发射台、异动预警。<b>写入即冻结</b>——历史日志不改，唯一例外是当天数据源晚到、重跑后核心缺失变少，会覆盖一次并标「补录」。每周一出上一周的周复盘，每月 1 日出上个月的月复盘。规则变更的日子在列表里有分隔行。",
                   f"The daily run at {MAIN_TIME} UTC (plus an extra run whenever code is pushed) writes a rule-based log from the public rules in Methodology: the overall read, four-layer readings, launchpads and alerts. <b>Frozen once written</b> — the only exception is a same-day re-run with fewer missing core inputs, marked 'Re-run'. Weekly reviews come out on Mondays, monthly ones on the 1st. Rule-change days are marked in the list.")}</p></div></div>
<h2>{T("每日解读", "Daily logs")}</h2>{dl or e3}
<h2>{T("周复盘", "Weekly reviews")}</h2>{f'<div class="card"><ul class="list">{wl}</ul></div>' if wl else e2}
<h2>{T("月复盘", "Monthly reviews")}</h2>{f'<div class="card"><ul class="list">{ml}</ul></div>' if ml else e1}"""
    emit("journal/index.html", T(f"解读日志 · {BRAND}", f"Journal · {BRAND_EN}"), body, active="journal",
         desc=T("每日规则化解读 + 周复盘 + 月复盘，写入即冻结，公开可查。", "Daily rule-based logs plus weekly and monthly reviews, frozen once written."))


# ---------------------------------------------------------------- 口径 / 更正 / 关于
L1_RULES_ZH = """<p style="margin:0 0 8px"><b style="color:var(--ink)">L1 宏观流动性</b>（2026-10-02 起，依据《BTC 全周期宏观相关性与归因研究》）：L1 管周到月的波动、节奏和风险预算，不管方向。</p>
<ul style="margin:0 0 10px;padding-left:20px"><li><b>顺风</b>：乐观度 z &gt; 0 且 BAA 信用利差 13 周收窄，实际利率没有急升。</li>
<li><b>中性偏谨慎</b>：实际利率急升（13 周 ≥ +0.40pp）单独出现——框架里风险预算降一档、不加仓。</li>
<li><b>逆风</b>：实际利率急升 且（BAA / NFCI 13 周转紧 或 乐观度 z &lt; 0），或流动性闸门触发（净流动性 13 周 ≤ −2.72% 且美元 13 周走强）——框架里名义风险预算 ×0.7，两项不叠乘。</li>
<li><b>中性</b>：其余情况。高收益利差 13 周走阔 ≥ 0.30pp 时加「警戒」（先行提示，本站阈值，未经回测）。</li></ul>
<p style="margin:0 0 8px"><b>L1-B 加密资金通道（只确认、不预测）</b>：稳定币主线（去重 = 总量 − 支付/机构 − 生息/合成）、交易子弹（剔除 Tron，并列含 Tron 口径）、现货 ETF（趋势确认，滞后）、期货升水（CME 与 Deribit 并列）和资金轮动矩阵（ETF 13 周 × 交易子弹 13 周：共振 / 换手 / 承接 / 双撤）。和价格同向 = 确认，背离 = 提示，不进档位判定。</p>
<p style="margin:0 0 8px">实际利率不再是 L1 的第一指标（第一指标是乐观度），改作“状态变量”：它决定当下落在情境矩阵的哪一行，再和信用条件一起定档。每条规则「能否改交易参数」逐条照抄宏观总文档 §10.2，见下方「L1 规则清单」。13 周变化统一按周五收盘对齐（取当周最后可得值）。阈值只用 2018 年以后的数据定。</p>"""
L1_RULES_EN = """<p style="margin:0 0 8px"><b style="color:var(--ink)">L1 Macro liquidity</b> (since 2026-10-02, based on the BTC full-cycle macro attribution study): L1 sets volatility, pacing and risk budget over weeks to months, not direction.</p>
<ul style="margin:0 0 10px;padding-left:20px"><li><b>Tailwind</b>: optimism z &gt; 0 and the BAA spread narrowing over 13 weeks, with no real-yield surge.</li>
<li><b>Neutral-cautious</b>: a real-yield surge (13w ≥ +0.40pp) on its own — one notch less risk budget, no adds.</li>
<li><b>Headwind</b>: a surge plus (BAA/NFCI tightening or optimism z &lt; 0), or the liquidity gate (net liquidity 13w ≤ −2.72% with a stronger dollar) — nominal risk budget ×0.7, not compounded.</li>
<li><b>Neutral</b>: everything else. An 'alert' tag is added when the high-yield spread widens ≥ 0.30pp over 13 weeks (early warning; this site's threshold, not back-tested).</li></ul>
<p style="margin:0 0 8px"><b>L1-B crypto funding channels (confirm, don't predict)</b>: stablecoin main line (de-dup = total − payment − yield/synthetic), trading bullets (ex-Tron, with an incl.-Tron lens), spot ETFs (trend confirmation, lagging), futures basis (CME and Deribit side by side) and the rotation matrix (ETF 13w × trading bullets 13w). Agreement with price confirms, divergence warns; not part of the regime verdict.</p>
<p style="margin:0 0 8px">The real yield is no longer L1's first gauge (optimism is); it is a state variable that picks the row of the scenario matrix and sets the regime together with credit. Whether each rule may change trading parameters is copied rule by rule from §10.2 of the macro study — see the L1 rule list below. 13-week changes are aligned to Friday closes. Thresholds use post-2018 data only.</p>"""
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


L1_RULE_LIST = load(os.path.join(ROOT, "config", "l1_rules.json"), {}) or {}


DIR_EN = {"偏多": "leaning up", "防顶": "top watch", "待确认": "unconfirmed", "偏空": "leaning down"}
TIER_EN = {"顺风": "Tailwind", "中性": "Neutral", "中性偏谨慎": "Neutral-cautious", "逆风": "Headwind", "警戒": "Alert (add-on)"}


def comp_rules_html():
    """综合研判怎么来（M11）：四段分工 + 一句话拼接规则 + 当前短句表（直接读 config/composite.json）。"""
    C = R.综合.load_cfg()
    rows2 = "".join(f"<tr><td class='l'>{esc(T(R.L2_STATES[k][0], R.L2_STATES[k][1]))}</td><td class='l'>{esc(T(v['方向'], DIR_EN.get(v['方向'], v['方向'])))}</td><td class='l wrap'>{esc(T(v['一句话'], v['一句话EN']))}</td></tr>"
                    for k, v in C["L2"].items() if k in R.L2_STATES)
    rows1 = "".join(f"<tr><td class='l'>{esc(T(k, TIER_EN.get(k, k)))}</td><td class='l wrap'>{esc(T(v.get('一句话') or '（不进一句话）', v.get('一句话EN') or '(not in the line)'))}</td><td class='l wrap'>{esc(T(v['分段'], v['分段EN']))}</td></tr>"
                    for k, v in C["L1"].items() if not k.startswith("_"))
    tiers = ("顺风", "中性", "中性偏谨慎", "逆风")
    rows3 = "".join(f"<tr><td class='l'>{esc(T(d, DIR_EN.get(d, d)))}</td>" + "".join(f"<td class='l wrap'>{esc(T(*C['动作'][d][t]))}</td>" for t in tiers) + "</tr>" for d in ("偏多", "防顶", "待确认", "偏空"))
    trig = "".join(f"<li>{esc(T(r['条件'], r.get('条件EN', r['条件'])))} → {esc(T(r['中文'], r['英文']))}</li>" for r in C["逆风原因"])
    p1 = T("综合研判按研究里定下的分工四层合成：<b>L2 给方向的底色</b>；<b>L1 管节奏和风险预算</b>，不管方向；<b>L3 看筹码</b>和周期方向是一致还是背离；<b>L4 只描述短期温度</b>，不改变动作（L4 还没完成研究）。",
           "The overall read combines four layers along the study's division of labour: <b>L2 sets the direction</b>; <b>L1 sets pace and risk budget</b>, not direction; <b>L3 checks</b> whether flows agree with the cycle; <b>L4 only describes short-term temperature</b> and never changes the action (its research is not finished).")
    p2 = T("一句话 =「{方向句}；{但}{节奏句}，{动作}。{筹码背离提示}{短期提示}」：方向偏多而 L1 是中性偏谨慎 / 逆风，或方向偏空 / 防顶而 L1 是顺风时加「但」；动作只来自 L1 的风险预算规则和 L2 研究写定的交接原则「方向上不急于看空，节奏上不追高、按 L1 的风险预算分批」；L3 和方向背离时追加一句；L4 不是中性时追加短期温度。一句话超过 60 字先去掉短期提示，再去掉背离提示（四段里仍然完整显示）。",
           "One line = '{direction}; {but} {pace} — {action}. {flow divergence} {short term}': 'but' is added when the direction leans up while L1 is cautious/headwind, or leans down / top-risk while L1 is a tailwind; actions come only from L1's risk-budget rules and the L2 hand-over principle ('no rush to turn bearish on direction; no chasing on pace, scale in per L1's budget'); a divergence note is added when L3 disagrees; L4 adds its temperature when not neutral. Lines over 60 characters drop the short-term note first, then the divergence note (both stay in the paragraphs).")
    p3 = T("「节奏上不追高」只出现在「方向偏多 + L1 偏紧」的组合里（L2 研究 §4 交接原则）；「可它改变不了熊市的深度」出自宏观总文档：熊市跌多深按周期成熟度排序、和利率冲击无关。短句全文见 config/composite.json。",
           "“No chasing” only appears when the direction leans up and L1 is tight (L2 study §4 hand-over principle); “it won't change how deep a bear market goes” comes from the macro study: bear depth ranks with cycle maturity, not rate shocks. Full phrases are in config/composite.json.")
    th = "".join(f"<th class='l'>{esc(T(t, TIER_EN.get(t, t)))}</th>" for t in tiers)
    return (f'<div class="card mcard"><p>{p1}</p><p>{p2}</p>'
            f'<h4>{T("表 1 · L2 方向", "Table 1 · L2 direction")}</h4><div class="tw"><table><thead><tr><th class="l">{T("L2 状态", "L2 state")}</th><th class="l">{T("方向", "Direction")}</th><th class="l">{T("一句话用", "Line phrase")}</th></tr></thead><tbody>{rows2}</tbody></table></div>'
            f'<h4>{T("表 2 · L1 节奏", "Table 2 · L1 pace")}</h4><div class="tw"><table><thead><tr><th class="l">{T("档位", "Regime")}</th><th class="l">{T("一句话用", "Line phrase")}</th><th class="l">{T("分段用", "Paragraph")}</th></tr></thead><tbody>{rows1}</tbody></table></div>'
            f'<p class="tnote">{T("逆风的触发原因（多个同时成立只取最前面一条）：", "Headwind triggers (first match wins):")}</p><ul class="tnote">{trig}</ul>'
            f'<h4>{T("表 3 · 动作（方向 × L1 档位）", "Table 3 · Action (direction × L1 regime)")}</h4><div class="tw"><table><thead><tr><th class="l">{T("方向", "Direction")}</th>{th}</tr></thead><tbody>{rows3}</tbody></table></div>'
            f'<p class="tnote">{p3}</p></div>')


def build_methodology():
    lp_rows = "".join(f"<tr><td class='l'>{esc(k)}</td><td class='l wrap'>{esc(v)}</td></tr>" for k, v in LP_RULES[LANG["v"]])
    S = G["S"]
    macro = ""
    for i, meta in R.LAYERS.items():
        trs, seen_etf = "", False
        for ind in ind_layer_list(i):
            if ind["key"] in ("etf13", "etf28"):          # 两个窗口描述相同，合并成一行
                if seen_etf:
                    continue
                seen_etf = True
                nm = T("现货 ETF 净流入（13 周 / 4 周两个窗口）", "Spot ETF net flow (13-week and 4-week windows)")
            else:
                nm = T(ind["名称"], ind["EN"])
            zr = zone_rules(ind)
            zones = "；".join(f"{T(c[1], c[2])} {r}" for c, r in zip(ind["cuts"], zr)) if len(ind["cuts"]) > 1 else T("只看趋势", "trend only")
            if ind["key"] in OWN_PCT:
                zones = T(f"自身历史分位：< 20 低位 / 20–80 中段 / > 80 高位（满 {R.RECORD_DAYS} 天）", f"own-history percentile: < 20 low / 20–80 mid / > 80 high (after {R.RECORD_DAYS} days)")
            lvl = T(ind["级别"], LEVEL_EN.get(ind["级别"], "")) + (f" · {T(ind['级别注'], ind['级别注EN'])}" if ind.get("级别注") else "")
            ref = f"<br><span class='stamp' style='text-align:left'>{esc(T(ind['出处'], ind['出处EN']))}</span>" if ind.get("出处") else ""
            trs += (f"<tr><td class='l'><a href='{ind_href(ind['key'])}'><b>{esc(nm)}</b></a><br><span class='stamp' style='text-align:left'>{esc(src_t(ind['来源']))}</span>{ref}</td>"
                    f"<td class='l'>{esc(lvl)}{('<br>' + grade_chip(ind.get('等级'), ind)) if ind.get('等级') else ''}</td>"
                    f"<td class='l wrap'>{esc(T(ind['说明'], ind['说明EN']))}</td>"
                    f"<td class='l wrap'>{T('按', 'By ')}{esc(T(ind['依据'], ind['依据EN']))}{CN}{esc(zones)}</td></tr>")
        if i == 2:
            trs = (f"<tr><td class='l'><a href='{U('/macro/')}#layer-2'><b>{T('L2 周期状态机', 'L2 cycle state machine')}</b></a><br><span class='stamp' style='text-align:left'>Coin Metrics · bitview.space</span></td>"
                   f"<td class='l'>{T('层结论', 'layer verdict')}</td><td class='l wrap'>{T('六个状态 + 14 条信号（底部区 6 / 底部确认 6 / 顶部风险 2）+ 13 条关键价位，每条信号带证据等级和研究文档章节。下面 6 个指标是状态机的输入。', 'Six states + 14 signals (6 bottom-zone / 6 confirmation / 2 top-risk) + 13 key levels; each signal carries its evidence grade and study section. The six gauges below feed it.')}</td>"
                   f"<td class='l wrap'>{T('状态转换规则见上方「层结论怎么来」', 'Transition rules: see How layer verdicts are made above')}</td></tr>") + trs
        macro += (f"<h3>L{i} · {esc(T(meta['名称'], meta['EN']))}{T('（', ' (')}{esc(T(meta['问'], meta['问EN']))}{T('？）', '?)')}</h3><div class='tw'><table><thead><tr><th class='l'>{T('指标', 'Indicator')}</th>"
                  f"<th class='l'>{T('级别 / 证据', 'Level / evidence')}</th><th class='l'>{T('怎么读', 'How to read')}</th><th class='l'>{T('区间规则', 'Zones')}</th></tr></thead><tbody>{trs}</tbody></table></div>")
    # L1 规则清单（宏观总文档 §10.2，逐条照抄）
    perm = L1_RULE_LIST.get("权限", {})
    pdef = "".join(f"<li><b>{esc(T(k, {'只做系数': 'Coefficient only', '只做记录': 'Record only', '禁止使用': 'Do not use', '方法规则': 'Method rule'}[k]))}</b>{CN}{esc(T(*v))}</li>" for k, v in perm.items())
    rrows = "".join(f"<tr><td>{esc(r['#'])}</td><td class='l wrap'><b>{esc(T(r['规则'], r['规则EN']))}</b></td><td class='l wrap'>{esc(T(r['怎么用'], r['怎么用EN']))}</td>"
                    f"<td class='l wrap'>{esc(T(r['可靠程度'], r['可靠程度EN']))}</td><td class='l'><b>{esc(T(r['能否改交易参数'], r['能否改交易参数EN']))}</b></td></tr>"
                    for r in L1_RULE_LIST.get("rules", []))
    sched_rows = "".join(f"<tr><td class='l'>{esc(T(x['名称'], x['EN']))}</td><td>UTC {esc(x['时间'])}</td><td class='l wrap'>{esc(T(x['覆盖'], x['覆盖EN']))}</td><td class='l'><code>.github/workflows/{esc(x['文件'])}</code></td></tr>" for x in SCHED)
    win_rows = ""
    for ind in R.INDICATORS:
        since, why, why_en = R.stats_window(S, ind)
        ds = sorted(d for d, v in R.series_of(S, ind).items() if v is not None)
        win_rows += (f"<tr><td class='l'><a href='{ind_href(ind['key'])}'>{esc(T(ind['名称'], ind['EN']))}</a></td><td>{ds[0] if ds else '—'}</td>"
                     f"<td>{since or (ds[0] if ds else '—')}</td><td class='l wrap'>{esc(T(why, why_en)) or T('全部历史', 'full history')}</td></tr>")
    pend = "".join(f"<tr><td class='l'>L{p['层']}</td><td class='l'>{esc(T(p['名称'], p['EN']))}</td><td class='l wrap'>{esc(T(p['原因'], p['原因EN']))}</td><td class='l'>{esc(T(p.get('计划', '—'), p.get('计划EN', '—')))}</td></tr>" for p in R.PENDING)
    retired = "".join(f"<tr><td class='l'><a href='{ind_href(p['key'])}'>{esc(T(p['名称'], p['EN']))}</a></td><td>{p['停用']}</td><td class='l wrap'>{esc(T(p['原因'], p['原因EN']))}</td></tr>" for p in R.RETIRED)
    banned = "".join(f"<tr><td class='l wrap'>{esc(T(a, b))}</td><td class='l wrap'>{esc(T(c, d))}</td></tr>" for a, b, c, d in R.BANNED)
    body = f"""{crumbs([(T("口径与规则", "Methodology"), None)])}<h1>{T("口径与规则", "Methodology")}</h1>
<p class="lede">{T("解读日志里的每一个判断都来自下面这些公开规则。规则改动会在更正记录里留痕，历史日志不跟着改。", "Every judgement in the logs comes from the public rules below. Rule changes are logged in Corrections; past logs are never rewritten.")}</p>
<nav class="anch static">{"".join(f'<a href="#{h}">{t}</a>' for t, h in ((T("层结论", "Verdicts"), "verdicts"), (T("综合研判", "Overall read"), "comp"), (T("L1 规则清单", "L1 rules"), "l1rules"), (T("标签说明", "Tags"), "legend"), (T("更新时间", "Schedule"), "schedule"), (T("统计窗口", "Stats window"), "window"), (T("指标与区间", "Indicators"), "indicators"), (T("预警阈值", "Alerts"), "alerts")))}</nav>
<h2 id="verdicts">{T("层结论怎么来", "How layer verdicts are made")}</h2>
<div class="card mcard">
{T(L1_RULES_ZH, L1_RULES_EN)}
<p style="margin:0 0 8px"><b style="color:var(--ink)">L2 {T("周期", "Cycle")}</b>{CN}{T("规则化状态机（l2/l2_signals.py，《BTC周期层L2研究》§7）逐日推进：新高 → 牛市；减半后 480~600 天或 MVRV ≥ 2 且价/200 周均 ≥ 2 → 牛市·顶部风险区；回撤 ≥ 20% → 牛市回撤·待确认（收窄到 10% 内回到牛市）；回撤 ≥ 35% 且新高已过 90 天、减半已过 450 天 → 熊市；熊市里底部区信号 ≥ 2 条 → 熊底区；离最低点 +40% 且最低点已过 90 天，或四条短期成本线连续 7 天站上且本轮出现过分龄底部确认 → 熊末→牛初；收盘跌破本轮最低收盘则退回熊市。数据：Coin Metrics 社区接口 + bitview.space。层结论 = 当天状态。",
"A rule-based state machine (l2/l2_signals.py, L2 cycle study §7) stepped day by day: new high → bull; halving +480–600 days or MVRV ≥ 2 with price/200W MA ≥ 2 → bull top-risk; drawdown ≥ 20% → bull pullback (back to bull inside 10%); ≥ 35% with the high ≥ 90 days old and the halving ≥ 450 days old → bear; ≥ 2 bottom-zone signals in a bear → bottom zone; +40% from a ≥ 90-day-old low, or 7 days above four short-term cost lines with an age-band confirmation this cycle → late bear → early bull; a close below the cycle low reverts to bear. Data: Coin Metrics community API + bitview.space. Layer verdict = the state of the day.")}</p>
<p style="margin:0 0 8px"><b style="color:var(--ink)">L3 {T("筹码", "Coin flows")}</b>{CN}{T("以交易所 BTC 7 日净流量为准：< −2,000 枚 = 净流出（筹码离开交易所），> +2,000 枚 = 净流入（留意抛压），其余进出均衡。交易所余额 30 日变化只展示趋势。L3 数据维度正在重做。", "Based on 7-day exchange net flow: < −2,000 BTC = outflow, > +2,000 = inflow (watch selling), otherwise balanced. Exchange balance change is shown as trend only. L3 is being rebuilt.")}</p>
<p style="margin:0"><b style="color:var(--ink)">L4 {T("情绪", "Sentiment")}</b>{CN}{T("恐慌贪婪（−2~+2）、资金费率（−1~+2）、未平仓 7 日变化（−1~+1）合计 ≥ 3 过热、1~2 偏热、≤ −2 偏冷，其余中性。L4 还没完成研究，只描述温度。", "Fear & greed (−2..+2), funding (−1..+2) and 7-day OI change (−1..+1): ≥ 3 hot, 1–2 warm, ≤ −2 cool, otherwise neutral. L4 research is unfinished; it only describes temperature.")}</p></div>
<h2 id="comp">{T("综合研判怎么来", "How the overall read is made")}</h2>{comp_rules_html()}
<h2 id="l1rules">{T("L1 规则清单（宏观总文档 §10.2，逐条照抄）", "L1 rule list (macro study §10.2, copied rule by rule)")}</h2>
<div class="card mcard"><p>{T("「能否改交易参数」分四种：", "“May it change trading parameters” has four values:")}</p><ul>{pdef}</ul></div>
<div class="tw" style="margin-top:10px"><table><thead><tr><th>#</th><th class="l">{T("规则", "Rule")}</th><th class="l">{T("怎么用", "How to use")}</th><th class="l">{T("可靠程度", "Reliability")}</th><th class="l">{T("能否改交易参数", "Trading parameters")}</th></tr></thead><tbody>{rrows}</tbody></table></div>
<h2 id="legend">{T("标签说明", "What the tags mean")}</h2><p class="tnote">{T("「级别」和「证据等级」是两个维度：级别说这个指标在本层判定里起什么作用，证据等级说它在研究里被检验到什么程度。", "Level and evidence grade are two separate dimensions: level is the gauge's role in the layer verdict, evidence grade is how well the research has tested it.")}</p>{tag_legend()}
<h2 id="schedule">{T("更新时间", "Update schedule")}</h2>
<div class="tw"><table><thead><tr><th class="l">{T("任务", "Job")}</th><th>{T("时间", "Time")}</th><th class="l">{T("覆盖哪些数据", "Covers")}</th><th class="l">{T("配置", "Config")}</th></tr></thead><tbody>{sched_rows}</tbody></table></div>
<p class="tnote">{esc(T(SITE_CFG.get("推送重跑", ""), SITE_CFG.get("推送重跑EN", "")))}{T("页面上「解读生成」是当天日志冻结的时间，「数据更新」是页面读数最后一次刷新的时间。", " 'Log generated' is when the day's log was frozen; 'Data updated' is when the page's readings were last refreshed.")}</p>
<h2 id="window">{T("统计窗口", "Statistics window")}</h2>
<div class="card mcard"><ol><li>{T("L1 宏观指标：只用 2018 年以后（方法规则：2010–2017 宏观对 BTC 没有解释力）。", "L1 macro gauges: post-2018 only (method rule: macro had no explanatory power in 2010–2017).")}</li>
<li>{T("链上周期类（L2 估值与持有者、L3 交易所）：2012-01-01 起；有效起点更晚的取有效起点。", "On-chain cycle gauges (L2 valuation & holders, L3 exchanges): from 2012-01-01, or the first valid day if later.")}</li>
<li>{T("百分比变化类（L1-B 稳定币系列、交易所余额 30 日变化等）：从上面的起点往后若仍有 |变化率| > 100% 的点，推迟到此后再也没有的第一天（早期基数过小）。", "Percentage-change gauges (L1-B stablecoin lines, 30-day exchange balance change, etc.): pushed to the first day after which no |change| > 100% occurs (small early base).")}</li>
<li>{T("图上照样展示统计起点之前的数据，铺灰底并注明原因；每个详情页写明实际统计窗口。", "Earlier data stays on the charts with a grey background and a note; every indicator page states its actual window.")}</li></ol></div>
<details class="card fold"><summary>{T("各指标的数据起点与统计起点", "Data start and statistics start per gauge")}</summary><div class="tw" style="margin:0;border:0"><table><thead><tr><th class="l">{T("指标", "Gauge")}</th><th>{T("数据起点", "Data from")}</th><th>{T("统计起点", "Stats from")}</th><th class="l">{T("原因", "Why")}</th></tr></thead><tbody>{win_rows}</tbody></table></div></details>
<h2 id="alerts">{T("异动预警阈值", "Alert thresholds")}</h2>
<div class="card mcard">{T("核心指标区间切换 · L1 档位切换 · L2 周期状态切换 / L2 信号亮灭 · 交易所单日 BTC 净流量 ≥ 5,000 枚 · 资金费率正负翻转 · VIX 穿越 20 · 发射台赛道单日 ±25% · 发射台当日第一易主 · 深度追踪平台日环比超 ±60%。",
                                                                                      "Core zone changes · L1 regime change · L2 state change / L2 signal on-off · ≥ 5,000 BTC exchange net flow in a day · funding sign flip · VIX crossing 20 · launchpad sector ±25% in a day · new #1 launchpad · deep-tracked platform ±60% DoD.")}</div>
<h2 id="indicators">{T("宏观四层 · 指标与区间", "Indicators and zones")}</h2>{macro}
<h2>{T("研究里测过、不再使用的说法", "Claims tested and dropped")}</h2><div class="tw"><table><thead><tr><th class="l">{T("说法", "Claim")}</th><th class="l">{T("原因", "Why")}</th></tr></thead><tbody>{banned}</tbody></table></div>
<h2>{T("框架里暂未接入的指标", "Not yet connected")}</h2><div class="tw"><table><thead><tr><th class="l">{T("层", "Layer")}</th><th class="l">{T("指标", "Indicator")}</th><th class="l">{T("原因", "Reason")}</th><th class="l">{T("计划数据源", "Planned source")}</th></tr></thead><tbody>{pend}</tbody></table></div>
<h2>{T("已停用的指标", "Retired gauges")}</h2><div class="tw"><table><thead><tr><th class="l">{T("指标", "Gauge")}</th><th>{T("停用日", "Retired")}</th><th class="l">{T("原因", "Why")}</th></tr></thead><tbody>{retired}</tbody></table></div>
<h2>{T("解读日志规则", "Log rules")}</h2>
<div class="card mcard">{T(f"日志日期 = 解读当天（UTC），日更每天 UTC {MAIN_TIME} 运行，每个读数带自己的数据日期（FRED 按美国工作日、NFCI 周度、交易所余额约有 2 周滞后，超过容忍天数标 ⚠）。写入即冻结；同一天重跑且核心缺失变少才覆盖一次并标「补录」。周复盘按 ISO 周（周一至周日），月复盘按自然月；切换发生在规则变更当天的，注明「规则变更所致」。人工点评放在 content/journal/，单独标注。网站其他位置展示日志内容时标「日志 · 冻结时间」，读数和最新值不同以最新值为准。",
                                                                                   f"Log date = UTC day of the run (the daily run is at {MAIN_TIME} UTC); each reading carries its own data date (FRED on US business days, NFCI weekly, exchange balance ~2 weeks late; stale readings get ⚠). Frozen once written; a same-day re-run only overwrites when fewer core inputs are missing, marked 'Re-run'. Weekly reviews follow ISO weeks, monthly ones calendar months; switches on a rule-change day are labelled as such. Wherever log content appears elsewhere it is marked with its freeze time; the latest values win.")}</div>
<h2>{T("发射台口径", "Launchpad conventions")}</h2><div class="tw"><table><tbody>{lp_rows}</tbody></table></div>"""
    emit("methodology/index.html", T(f"口径与规则 · {BRAND}", f"Methodology · {BRAND_EN}"), body, active="methodology")


def build_corrections(sd, fixes):
    rows = "".join(f"<tr><td class='l'>{esc(f['日期'])}</td><td>{f['旧值']:,.0f} → {f['新值']:,.0f}</td>"
                   f"<td class='l'>{esc(T(f.get('口径', ''), {'事件': 'event'}.get(f.get('口径', ''), f.get('口径', ''))))}</td><td>{esc(f['修正时间UTC'][:10])}</td></tr>"
                   for f in sorted(fixes, key=lambda x: x["日期"], reverse=True)[:60])
    S = G["S"]
    rule_rows = ""
    for c in sorted(R.RULE_CHANGES, key=lambda c: c["日期"], reverse=True):
        anc = c.get("锚") or c["日期"]
        cl = next((v["version"] for v in CHANGELOG if any(i.get("corrections_anchor") == "#rc-" + anc for i in v["items"])), None)
        jr = "2026-10-08-comp" if anc == "2026-10-08-comp" else c["日期"]
        links = ((f'<br><a href="{U("/journal/")}#rule-{jr}">{T("日志分隔行", "journal marker")}</a>' if anc != "2026-10-08-stats" else "<br>")
                 + (f' · <a href="{U("/changelog/")}#v{cl}">{T("更新日志", "changelog")} {cl}</a>' if cl else ""))
        extra = ""
        if anc == "2026-10-08-stats":
            trs = ""
            for ind in R.INDICATORS:
                old, new = R.stats_window_old(S, ind), (R.stats_window(S, ind)[0])
                ds = sorted(d for d, v in R.series_of(S, ind).items() if v is not None)
                new = new or (ds[0] if ds else None)
                if old and new and old != new:
                    trs += f"<tr><td class='l'>{esc(T(ind['名称'], ind['EN']))}</td><td>{old}</td><td>{new}</td></tr>"
            extra = (f'<details class="fold"><summary>{T("受影响指标：旧 → 新统计起点", "Affected gauges: old → new start")}</summary><div class="tw"><table><thead><tr><th class="l">{T("指标", "Gauge")}</th>'
                     f'<th>{T("旧起点", "Old")}</th><th>{T("新起点", "New")}</th></tr></thead><tbody>{trs}</tbody></table></div></details>') if trs else ""
        rule_rows += (f"<tr id='rc-{anc}'><td class='l'>{esc(c['日期'])}{links}</td><td class='l'>{esc(T(c['范围'], c['EN范围']))}</td>"
                      f"<td class='l wrap'>{esc(T(c['内容'], c['EN']))}{extra}</td><td class='l wrap'>{esc(T(c.get('原因') or '—', c.get('原因EN') or '—'))}</td></tr>")
    d0 = (sd or {}).get("日期") or ""
    rev = [a for a in (sd or {}).get("异常", []) if "修订" in a or "延迟" in a]
    rn = (f"<h2>{T('近期数据源变动', 'Recent data-source changes')}</h2><div class='card'><ul class='alerts'>" + "".join(f"<li><span class='d'>{esc(d0)}</span>{esc(a if LANG['v'] == 'zh' else 'Launchpad source note (details on the launchpad page, Chinese only)')}</li>" for a in rev) + "</ul></div>") if rev else ""
    revs = load(REV_PATH, []) or []
    rv_rows = "".join(f"<tr><td class='l'>{esc(r['检测日'])}</td><td class='l'>{esc(r.get('名称') or r['指标'])}</td><td>{esc(r['起'])} ~ {esc(r['止'])}</td><td>{r['点数']}</td><td>{r['最大变动']:+.2f}%（{esc(r['日期'])}）</td></tr>"
                      for r in reversed(revs[-80:]))
    rv_html = (f'<div class="tw"><table><thead><tr><th class="l">{T("检测日", "Detected")}</th><th class="l">{T("指标", "Gauge")}</th><th>{T("影响区间", "Range")}</th><th>{T("点数", "Points")}</th><th>{T("最大变动", "Largest change")}</th></tr></thead><tbody>{rv_rows}</tbody></table></div>'
               if rv_rows else empty_state("none", T("还没有检测到回改", "No revisions detected yet"), T("每天生成数据时和前一天比较：7 天以前的数据变动超过 0.5% 就记一笔。", "Every build compares with the previous files: changes over 0.5% to data more than 7 days old are logged here."), ""))
    none_ = '<tr><td class="l" colspan="4">' + T("暂无", "None") + '</td></tr>'
    body = f"""{crumbs([(T("更正记录", "Corrections"), None)])}<h1>{T("更正记录", "Corrections")}</h1>
<p class="lede">{T("数据源事后修订、PONS 销毁口径重算、规则调整，全部留痕，不覆盖不删除。每条规则变更写明为什么改，并链到日志里的分隔行和更新日志。", "Source revisions, PONS burn recalculations and rule changes — all logged, nothing overwritten. Each rule change says why, and links to the journal marker and the changelog.")}</p>
<h2>{T("规则变更", "Rule changes")}</h2><div class="tw"><table><thead><tr><th class="l">{T("日期", "Date")}</th><th class="l">{T("范围", "Scope")}</th><th class="l">{T("改了什么", "What changed")}</th><th class="l">{T("原因", "Why")}</th></tr></thead><tbody>{rule_rows}</tbody></table></div>
{rn}
<h2>{T("数据源历史回改（自动记录）", "Source history revisions (automatic)")}</h2>
<p class="tnote">{T("Coin Metrics、bitview 等会回头修正历史数据。解读日志里的冻结值和现在图上的值对不上时，可以在这里查。", "Coin Metrics, bitview and others revise history. When a frozen log value differs from today's chart, look here.")}</p>{rv_html}
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


def build_changelog():
    blocks = ""
    for v in CHANGELOG:
        lis = ""
        for i in v["items"]:
            link = f' <a href="{U("/corrections/")}{i["corrections_anchor"]}">{T("见更正记录", "see Corrections")}</a>' if i.get("corrections_anchor") else ""
            lis += f'<li><span class="cltag cl-{i["type"]}">{esc(T(*CL_TYPE[i["type"]]))}</span><span>{esc(T(i["zh"], i["en"]))}{link}</span></li>'
        blocks += (f'<section class="card clv" id="v{esc(v["version"])}"><div class="clh"><b>{esc(v["version"])}</b><span class="stamp">{esc(v["date"])}'
                   f'{" · " + T("已弹窗提示", "announced") if v.get("notify") else ""}</span></div><h3>{esc(T(v["title_zh"], v["title_en"]))}</h3><ul class="cl">{lis}</ul></section>')
    body = f"""{crumbs([(T("更新日志", "Changelog"), None)])}<h1>{T("更新日志", "Changelog")}</h1>
<p class="lede">{T("每一版按实际上线的内容写，新版本在最前面。「数据口径」类改动同时写进更正记录。", "Each version lists what actually shipped, newest first. Data changes are also logged in Corrections.")}</p>
{blocks}"""
    emit("changelog/index.html", T(f"更新日志 · {BRAND}", f"Changelog · {BRAND_EN}"), body, active="changelog")
    if LANG["v"] == "zh":
        with open(os.path.join(SITE, "changelog.json"), "w", encoding="utf-8") as fh:
            json.dump(CHANGELOG, fh, ensure_ascii=False, indent=1)


def build_404():
    emit("404.html", T(f"页面不存在 · {BRAND}", f"Not found · {BRAND_EN}"),
         f'<h1>{T("页面不存在", "Page not found")}</h1><p class="lede">{T("链接可能过期了，回", "The link may be outdated. Back to the ")}<a href="{U("/")}">{T("终端总览", "overview")}</a>{T("看看。", ".")}</p>')


def build_misc(logs, weeks, months):
    os.makedirs(os.path.join(SITE, "assets"), exist_ok=True)
    for k, v in ASSET_SRC.items():
        with open(os.path.join(SITE, "assets", k), "w", encoding="utf-8") as fh:
            fh.write(v)
    write("_headers", HEADERS)
    # 已停用指标的旧链接现在有自己的说明页（D5），不再 301 到宏观页
    rd = os.path.join(SITE, "_redirects")
    if os.path.exists(rd):
        os.remove(rd)
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: https://{DOMAIN}/sitemap.xml\n")
    urls = ["/", "/macro/", "/launchpad/", "/rotation/", "/narrative/", "/reports/", "/journal/", "/methodology/", "/corrections/", "/about/",
            "/launchpad/report/", "/launchpad/report/archive/"]
    urls += [f"/macro/{x['key']}/" for x in R.INDICATORS + R.RETIRED] + ["/changelog/"]
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


def write_latest(S, rs):
    """/data/latest.json（附录 C）：全站当前读数的唯一来源，迷你走势线日度 365 个点、周度 52 个点。"""
    tlog = G.get("TODAY_LOG") or {}
    m = {}
    for x in rs:
        ind = R.IND[x["key"]]
        s = R.series_of(S, ind)
        ds = sorted(d for d in s if s[d] is not None and d <= x["截至"])
        wk = ind.get("freq") == "w"
        ds = ds[-52:] if wk else [d for d in ds if R.days_between(d, x["截至"]) < 365]
        rec = R.recording_info(S, ind)
        m[x["key"]] = {"layer": f"L{ind['层']}", "value": r6(x["值"]), "display": x["显示"], "asof": x["截至"], "stale": x["过期"],
                       "zone_label_zh": x["区间"], "zone_label_en": x["区间EN"], "bias": R.BIAS.get(x["tone"], "neutral"),
                       "tier": LEVEL_EN.get(ind["级别"], ind["级别"]), "evidence": ind.get("等级"),
                       "recording": ({"days": rec["days"], "required": rec["required"], "since": rec["since"]} if rec and not rec["done"] else None),
                       "spark": ({"freq": "W", "dates": ds, "values": [r6(s[d]) for d in ds]} if wk else
                                 {"freq": "D", "start": ds[0] if ds else None, "values": [r6(s.get(d)) for d in (_days(ds[0], ds[-1]) if ds else [])]})}
    out = {"generated_at": (G.get("更新") or "").replace(" ", "T") + ":00Z", "journal_frozen_at": ((tlog.get("生成时间UTC") or "").replace(" ", "T") + ":00Z") if tlog else None,
           "as_of": G["as_of"], "layers": {f"L{i}": {"verdict_zh": v.get("结论"), "verdict_en": v.get("结论EN"), "short_zh": v.get("短"), "short_en": v.get("短EN"),
                                                    "bias": R.BIAS.get(v.get("tone"), "neutral")} for i, v in G["VS"].items()},
           "composite": {"zh": (G["COMP"] or {}).get("一句话"), "en": (G["COMP"] or {}).get("一句话EN")}, "metrics": m}
    with open(os.path.join(SITE, "data", "latest.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))


def main():
    sd = load(os.path.join(BUILD, "网站素材.json"))
    if not sd:
        print(f"⛔ 没找到 {os.path.join(BUILD, '网站素材.json')}，先跑 出看板.py")
        sys.exit(1)
    L, S = load_macro()
    logs, weeks, months = load_logs("日"), load_logs("周"), load_logs("月")
    for lg in logs:
        for lay in lg.get("层", []):
            if lay.get("短") and lay.get("短EN"):
                SHORT_EN.setdefault(lay["短"], lay["短EN"])
    rot = load(os.path.join(DATA, "板块台账.json"), {}) or {}
    matrix = load(os.path.join(DATA, "发射台矩阵.json"))
    fixes = load(os.path.join(DATA, "销毁修正记录.json"), []) or []
    G["今天"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    G["L2"] = load(os.path.join(DATA, "l2", "l2_latest.json"))
    G["L2S"] = load(os.path.join(DATA, "l2", "l2_series.json"))
    G["L2LIVE"] = load(os.path.join(DATA, "l2", "l2_live.json"), []) or []
    R.attach_l2(S, G["L2S"])
    upd = [(L.get("更新时间UTC") or sd.get("生成时间UTC") or "")[:16].replace("T", " "), (G["L2"] or {}).get("updated_utc") or ""]
    G["更新"] = max(upd)
    os.makedirs(SITE, exist_ok=True)
    # ---- 全站「当前读数」唯一来源（G3）：这一次构建里所有页面都读同一份 rs / 层结论 / 综合研判
    as_of = G["今天"]
    G["S"], G["as_of"] = S, as_of
    rs = [x for x in (R.judge(S, ind, as_of) for ind in R.INDICATORS) if x]
    G["RS"], G["JBY"] = rs, {x["key"]: x for x in rs}
    G["VS"] = {i: R.layer_verdict(i, rs, G["L2"]) for i in R.LAYERS}
    G["COMP"] = R.综合.compose(G["VS"], rs, G["L2"])
    G["TODAY_LOG"] = logs[-1] if logs else None
    G["PREV_LOG"] = next((lg for lg in reversed(logs) if lg["日期"] < as_of), None)
    G["CHANGES"] = R.alerts(rs, G["PREV_LOG"], R.launchpad_summary(sd), G["VS"][1], G["L2"])
    btc = S.get("btc_price") or {}
    nov = {d: v for d, v in btc.items() if "2022-11-01" <= d <= "2022-11-30" and v}
    G["CYC"] = min(nov, key=nov.get) if nov else "2022-11-21"
    # 走势数据（两种语言共用）：全历史序列放 data/series/（归档按月保留，不删）；其余旧文件清掉重写
    dd = os.path.join(SITE, "data")
    if os.path.isdir(dd):
        for x in os.listdir(dd):
            if x != SERIES_DIR:
                pth = os.path.join(dd, x)
                shutil.rmtree(pth) if os.path.isdir(pth) else os.remove(pth)
    files = write_indicator_data(S)
    G["FILES"] = files
    write_latest(S, rs)
    os.makedirs(os.path.join(SITE, "data", "l2"), exist_ok=True)
    for fn in ("l2_latest.json", "l2_history.json", "l2_live.json"):
        if os.path.exists(os.path.join(DATA, "l2", fn)):
            shutil.copyfile(os.path.join(DATA, "l2", fn), os.path.join(SITE, "data", "l2", fn))
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
        build_changelog()
        build_404()
    LANG["v"] = "zh"
    build_misc(logs, weeks, months)
    n = sum(1 for _, _, fs in os.walk(SITE) for f in fs if f == "index.html")
    print(f"网站已生成到 {SITE}（{n} 个页面，中英各一套；日志 {len(logs)} 篇、周复盘 {len(weeks)}、月复盘 {len(months)}、报告 {len(ALL_REPORTS)}）")


if __name__ == "__main__":
    main()
