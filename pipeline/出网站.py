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


# 时间（2026-11-06 定）：后端统计一律 UTC+0（UTC 完整日，UTC 0 点收盘）；
# 前端显示按语言区域换算：中文站新加坡时间（UTC+8），英文站美东时间（随夏令时）
from zoneinfo import ZoneInfo                                             # noqa: E402
SG_TZ, ET_TZ = ZoneInfo("Asia/Singapore"), ZoneInfo("America/New_York")
MON_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _utc(s):
    s = str(s or "").strip().replace("T", " ").replace("Z", "")[:16]
    try:
        if len(s) == 5:                                   # 只有「HH:MM」（定时任务）：按今天换算，夏令时随日期
            d = dt.datetime.now(dt.timezone.utc).date()
            return dt.datetime.fromisoformat(f"{d} {s}").replace(tzinfo=dt.timezone.utc)
        return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _en_clock(x):
    return f"{(x.hour % 12) or 12}:{x.minute:02d} {'AM' if x.hour < 12 else 'PM'}"


def TT(s, date=True):
    """UTC 时刻 → 中文「新加坡时间 10-29 18:20」/ 英文「Oct 29, 6:20 AM ET」。date=False 只写钟点（定时任务）。"""
    t = _utc(s)
    if t is None:
        return esc(s or "—")
    b, e = t.astimezone(SG_TZ), t.astimezone(ET_TZ)
    zh = "新加坡时间 " + (b.strftime("%m-%d %H:%M") if date else b.strftime("%H:%M"))
    en = ((f"{MON_EN[e.month - 1]} {e.day}, " if date else "") + _en_clock(e) + " ET")
    return T(zh, en)


def TCLOSE(d):
    """数据日 D 的收盘 = D+1 日 UTC 0 点：中文「10-28 收盘（新加坡时间 10-29 08:00）」/ 英文「Oct 28 close (8:00 PM ET)」。"""
    try:
        day = dt.date.fromisoformat(str(d)[:10])
    except ValueError:
        return esc(d or "—")
    t = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0), dt.timezone.utc)
    b, e = t.astimezone(SG_TZ), t.astimezone(ET_TZ)
    return T(f"{day.strftime('%m-%d')} 收盘（新加坡时间 {b.strftime('%m-%d %H:%M')}）", f"{MON_EN[day.month - 1]} {day.day} close ({_en_clock(e)} ET)")


def TDAY(d):
    """数据日 D（UTC 完整日）的截止：中文「截至新加坡时间 10-29 08:00」/ 英文「through Oct 28, 8:00 PM ET」。"""
    try:
        day = dt.date.fromisoformat(str(d)[:10])
    except ValueError:
        return esc(d or "—")
    t = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0), dt.timezone.utc)
    b, e = t.astimezone(SG_TZ), t.astimezone(ET_TZ)
    return T(f"截至新加坡时间 {b.strftime('%m-%d %H:%M')}", f"through {MON_EN[e.month - 1]} {e.day}, {_en_clock(e)} ET")


def TLOC(s):
    """事件时刻（UTC）→ 中文「11-06 21:30」（新加坡时间）/ 英文「Nov 6 8:30 AM」（美东），列表用的短写法。"""
    t = _utc(s)
    if t is None:
        return "", ""
    b, e = t.astimezone(SG_TZ), t.astimezone(ET_TZ)
    return T(b.strftime("%m-%d"), f"{MON_EN[e.month - 1]} {e.day}"), T(b.strftime("%H:%M"), _en_clock(e))


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
    "legs": '<path d="M1.5 13l3.5-4 2.5 2 6-7.5"/><path d="M10 3.5h3.5V7"/>',
    "calendar": '<path d="M2.5 3.5h11v10h-11z"/><path d="M2.5 6.5h11M5.5 2v3M10.5 2v3M5 9h1.5M7.75 9h1.5M10.5 9H12M5 11.5h1.5M7.75 11.5h1.5"/>',
    "macro": '<path d="M1.5 10.5c1.6-3.2 3.2-3.2 4.8 0s3.2 3.2 4.8 0c.9-1.8 1.9-2.6 2.9-2.2M1.5 5.5c1.6-3.2 3.2-3.2 4.8 0s3.2 3.2 4.8 0"/>',
    "launchpad": '<path d="M3 14V8.5M8 14V2.5M13 14V6"/><path d="M1.5 14h13"/>',
    "aiagent": '<rect x="3" y="4.5" width="10" height="8.5" rx="2"/><path d="M8 2v2.5M6 8.2v1M10 8.2v1M1.5 8.5v2M14.5 8.5v2"/>',
    "rotation": '<path d="M13.2 6A5.5 5.5 0 0 0 3.1 5.4M2.8 10a5.5 5.5 0 0 0 10.1.6M13.4 2.6v3.5H9.9M2.6 13.4V9.9h3.5"/>',
    "core": '<path d="M8 1.8l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.6l-3.8 2 .7-4.3-3.1-3 4.3-.6z"/>',
    "narrative": '<circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="2.4"/><path d="M8 8l4.2-4.2"/>',
    "alpha": '<circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="2.4"/><path d="M8 8l4.2-4.2"/>',
    "rwa": '<rect x="2.5" y="6.5" width="11" height="7.5" rx="1"/><path d="M1.5 6.5 8 2l6.5 4.5M5.5 9v2.5M8 9v2.5M10.5 9v2.5"/>',
    "reports": '<path d="M3 1.8h7l3 3v9.4H3z"/><path d="M10 1.8v3h3M5.5 11.5V9.5M8 11.5V7.5M10.5 11.5V8.5"/>',
    "journal": '<path d="M3.5 1.8h9v12.4h-9z"/><path d="M6 5h4M6 8h4M6 11h2.5"/>',
    "methodology": '<path d="M2 12.5 12.5 2l1.5 1.5L3.5 14H2z"/><path d="M9.5 5l1.5 1.5M7.5 7l1 1M5.5 9l1.5 1.5"/>',
    "corrections": '<path d="M2.5 8.5l3.5 3.5 7.5-8"/>',
    "about": '<circle cx="8" cy="5.2" r="2.8"/><path d="M2.5 14c.9-2.9 2.9-4.2 5.5-4.2s4.6 1.3 5.5 4.2"/>',
}
NAV_MAIN = [("home", "/", "终端总览", "Overview"), ("macro", "/macro/", "宏观仪表盘", "Macro"),
            ("calendar", "/calendar/", "事件日历", "Calendar"), ("launchpad", "/launchpad/", "发射台矩阵", "Launchpads"), ("aiagent", "/ai-agent/", "AI Agent", "AI Agent"), ("rotation", "/rotation/", "板块轮动", "Rotation"),
            ("core", "/core/", "核心选币", "Core Picks"), ("alpha", "/alpha/", "Alpha 雷达", "Alpha Radar"), ("rwa", "/rwa/", "RWA", "RWA"), ("reports", "/reports/", "分析报告", "Reports"),
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


# 报告分类（报告页顶部的筛选按钮；报告 meta 里写「分类: BTC」，可写多个，逗号隔开）
REPORT_CATS = ["BTC", "MEME", "RWA", "AI Agent"]
REPORT_FILTER_JS = """<script>(function(){var bs=document.querySelectorAll('#rcats .pill'),cs=document.querySelectorAll('#rlist .rcard'),em=document.getElementById('rempty');
function go(c){var n=0;bs.forEach(function(b){b.classList.toggle('on',b.dataset.c===c)});cs.forEach(function(x){var ok=c==='all'||(' '+x.dataset.cat+' ').indexOf(' '+c+' ')>=0;x.style.display=ok?'':'none';if(ok)n++});
em.style.display=n?'none':'';}
bs.forEach(function(b){b.addEventListener('click',function(){go(b.dataset.c);history.replaceState(null,'',b.dataset.c==='all'?location.pathname:'#'+encodeURIComponent(b.dataset.c))})});
var h=decodeURIComponent(location.hash.slice(1));go([].some.call(bs,function(b){return b.dataset.c===h})?h:'all');})();</script>"""


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
        meta["分类列表"] = [x.strip() for x in re.split(r"[,，、]", meta.get("分类") or "") if x.strip() in REPORT_CATS]
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
        tag = ""
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
<div class="sfoot"><div class="live"><i></i>{T('数据更新', 'Updated')} {TT(upd)}</div>
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

LEG_WEB = os.path.join(ROOT, "leg", "web")                              # 涨腿追踪：设计稿拆出来的脚本和样式（页面 + 首页卡片共用）
ASSET_SRC = {"site.css": ST.SITE_CSS, "ui.js": ST.UI_JS, "share.js": ST.SHARE_JS, "chart.js": ST.CHART_JS,
             "leg.js": open(os.path.join(LEG_WEB, "leg.js"), encoding="utf-8").read(),
             "leg.css": open(os.path.join(LEG_WEB, "leg.css"), encoding="utf-8").read(),
             "core.js": open(os.path.join(ROOT, "core", "web", "core.js"), encoding="utf-8").read(),
             "core.css": open(os.path.join(ROOT, "core", "web", "core.css"), encoding="utf-8").read(),
             "alpha.js": open(os.path.join(ROOT, "alpha", "web", "alpha.js"), encoding="utf-8").read(),
             "alpha.css": open(os.path.join(ROOT, "alpha", "web", "alpha.css"), encoding="utf-8").read()}
ASSET_URL = {k: f"/assets/{k}?v={hashlib.md5(v.encode('utf-8')).hexdigest()[:10]}" for k, v in ASSET_SRC.items()}

# Cloudflare Pages 缓存规则：样式脚本带版本号可以长缓存；走势数据一小时；页面本身每次都向服务器确认
HEADERS = """/assets/*
  Cache-Control: public, max-age=2592000
/data/*
  Cache-Control: public, max-age=3600
/ai-agent/monitor/*
  Cache-Control: public, max-age=0, must-revalidate
/*
  X-Content-Type-Options: nosniff
"""


def stats_tag():
    """访问统计（Umami Cloud，无 cookie）。ID 在 config/site.json「统计」；data-domains 限定正式域名，本地预览 / 截图不计数。"""
    uid = (SITE_CFG.get("统计") or {}).get("umami_id")
    return f'\n<script defer src="https://cloud.umami.is/script.js" data-website-id="{esc(uid)}" data-domains="{DOMAIN}"></script>' if uid else ""


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
{extra_head}{stats_tag()}
</head>
<body>
{nav_html(active)}
<main class="main"><div class="mi{' narrow' if narrow else ''}">
{body}
</div>
<footer class="foot"><span>{esc(T(BRAND + "（" + BRAND_EN + "）", BRAND_EN))}</span><a href="{X_URL}">{esc(TWITTER)}</a>
<span>{T('本站数据来源', 'Data sources')}{CN}DefiLlama · CoinMetrics · bitview.space · Binance · FRED · Farside · Yahoo · alternative.me · Hyperliquid · Deribit · CoinGecko{T('（', ' (')}<a href="{U('/methodology/')}">{T('口径与规则', 'methodology')}</a>{T('）', ')')}</span>
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
<ul><li><b>L1 宏观流动性</b>：风险预算该松还是紧</li><li><b>L2 周期定位</b>：处在四年周期的哪一段</li><li><b>L3 筹码结构</b>：哪些价位真的有人在守、接下来波动会不会放大</li><li><b>L4 情绪衍生品</b>：短期会不会过热超调</li></ul>
<p>每层给一个结论，最后汇总成「综合研判」。</p>
<p><b>怎么看</b>：先看顶部的综合研判 → 切换 L1~L4 看每层结论和依据 → 点任意指标卡，看它的全部历史、区间规则和历史上落在每个区间的比例。</p>
<p>数据每天 {esc(t)} 自动更新，解读日志写入即冻结、公开可查。每个指标都标了<a href="{U('/methodology/')}#legend">证据等级</a>；拿不到真实数据的标「待接入」，不用近似值顶替。</p>
<p>本站还在持续迭代，很多地方不完善。发现问题或有建议，欢迎在 X 上找 <a href="{X_URL}" target="_blank" rel="noopener">@Uncle_Onchain</a>。</p>
<p class="muted">本站只提供数据和过程记录，不构成投资建议。</p>""",
                f"""<h2 id="ucg-t">Welcome to Uncle Onchain Terminal</h2><p>A top-down, 4-layer BTC framework, updated automatically every day:</p>
<ul><li><b>L1 Macro Liquidity</b>: should the risk budget be loose or tight?</li><li><b>L2 Cycle Position</b>: where are we in the four-year cycle?</li><li><b>L3 Supply Structure</b>: which levels are really defended, and will moves get bigger?</li><li><b>L4 Sentiment &amp; Derivatives</b>: is the short term overheating?</li></ul>
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
             "Near": "near", "Aptos": "aptos", "Hedera": "hedera", "OP Mainnet": "optimism", "ZKsync Era": "era",
             "Elysium Kinetiq": "elysium"}
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
    """「新加坡时间 10:17（L2）、11:40（日更）」这类文案（英文站写美东时间），全站共用。"""
    parts = [(f"{TT(x['时间'], False)}（{x['名称']}）", f"{TT(x['时间'], False)} ({x['EN']})") for x in SCHED]
    en = [p[1] for p in parts]
    return T("、".join(p[0] for p in parts), (", ".join(en[:-1]) + " and " + en[-1]) if len(en) > 1 else "".join(en))


def times_line(log):
    """「解读生成 … · 数据更新 …」：区分日志冻结时间和页面读数的刷新时间。"""
    gen = (log or {}).get("生成时间UTC")
    return (T("解读生成", "Log generated") + f" <b>{TT(gen)}</b> · " + T("数据更新", "Data updated") + f" <b>{TT(G.get('更新'))}</b>")


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
    """首页四张核心卡：稳定币主线 / 发射台赛道 / 筹码压力区（L3）/ 情绪。"""
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
    l3 = G.get("L3")
    jp = R.judge(S, R.IND["l3_p1s"], as_of) if "l3_p1s" in R.IND else None
    if R.l3_ok(l3):
        a3, w3 = l3["p1s"], l3.get("warning") or {}
        on = bool(w3.get("on"))
        cards.append((T("上方压力区 · STH 成本 +1σ", "Pressure zone · STH cost +1σ"), "L3", f'${a3["value"]:,.0f}',
                      T(f'离收盘价 {_pc(a3["pct_from_price"])} · 大波动预警{"亮" if on else "不亮"}', f'{_pc(a3["pct_from_price"])} vs price · large-move warning {"on" if on else "off"}'),
                      "warn" if (on or l3["position"]["code"] == "in_zone") else "neutral", (jp or {}).get("走势", [])[-30:], ind_href("l3_p1s")))
    else:
        cards.append((T("上方压力区 · STH 成本 +1σ", "Pressure zone · STH cost +1σ"), "L3", "—", T("等待首次运行", "Awaiting first run"), "neutral", [], ind_href("l3_p1s")))
    l4 = G.get("L4")
    if R.l4_ok(l4):
        sg, c4 = l4.get("signal") or {}, l4["conclusion"]
        v = sg.get("value_pct")
        lv = R.L4_LEVELS[c4["level"]]
        cards.append((T("BTC 短期杠杆与情绪温度", "BTC short-term leverage & sentiment"), "L4", esc(T(c4["level"], lv[3].capitalize())),
                      (T("资金费率数据延迟 · 信号今天不判断", "Funding data delayed · no signal call today") if R.l4_funding_stale(l4) else
                       T(f'资金费率 30 日均 {"—" if v is None else f"{v:+.2f}%"} · 信号{"亮" if sg.get("on") else "不亮"}', f'Funding 30d avg {"—" if v is None else f"{v:+.2f}%"} · signal {"on" if sg.get("on") else "off"}')),
                      lv[2], [x.get("fund_ma30") for x in (G.get("L4H") or [])[-30:] if x.get("fund_ma30") is not None], U("/macro/") + "#layer-4"))
    else:
        cards.append((T("BTC 短期杠杆与情绪温度", "BTC short-term leverage & sentiment"), "L4", "—", T("等待首次运行", "Awaiting first run"), "neutral", [], U("/macro/") + "#layer-4"))
    out = ""
    for k, tag, v, s, tone, sp, href in cards:
        out += (f'<a class="glass hero" href="{href}"><div class="k">{esc(k)}<span>{esc(tag)}</span></div>'
                f'<div class="v t-{tone}">{v}</div><div class="s">{s}</div>{spark(sp, tone, 200, 34, area=True)}</a>')
    return out, cards


# ---------------------------------------------------------------- 综合研判（M11）：一句话 + 四段（方向 / 节奏 / 筹码 / 短期）
LAYER_TAB = {1: ("L1", "宏观流动性", "Macro Liquidity"), 2: ("L2", "周期定位", "Cycle Position"), 3: ("L3", "筹码结构", "Supply Structure"),
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
            f'</details>') if full else ""
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
        l4 = G.get("L4")
        if i == 4 and R.l4_ok(l4):
            sg, c4 = l4.get("signal") or {}, l4["conclusion"]
            v = sg.get("value_pct")
            items = (f'<li><span>{T("资金费率 30 日均", "Funding 30d avg")}</span><b class="t-{"up" if sg.get("on") else "neutral"}">{T("数据延迟 · 今天不判断", "delayed · no call today") if R.l4_funding_stale(l4) else ("—" if v is None else f"{v:+.2f}%".replace("-", chr(0x2212))) + " · " + (T("信号亮", "signal on") if sg.get("on") else T("信号不亮", "signal off"))}</b></li>'
                     f'<li><span>{T("杠杆", "Leverage")}</span><b>{esc(T(c4.get("leverage_band_zh") or "—", R.BAND_EN.get(c4.get("leverage_band_zh"), "—")))}</b></li>'
                     f'<li><span>{T("情绪", "Sentiment")}</span><b>{esc(T(c4.get("sentiment_band_zh") or "—", R.BAND_EN.get(c4.get("sentiment_band_zh"), "—")))}</b></li>')
        elif i == 2 and l2 and l2.get("signals"):
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
            lp_rows += (f'<tr><td class="rk">{i}</td><td class="l"><span class="pname">{esc(p["名称"])}{carry_chip(p.get("数据日")) if p.get("沿用") else ""}</span></td>'
                        f'<td class="l">{ch}</td><td>{f_usd(p["当日"])}</td><td>{p["当日"]/tot*100:.1f}%</td><td>{fmt_delta(p.get("日环比"), pct_input=True)}</td></tr>')
    lp_tbl = (f'<div class="tw"><table><thead><tr><th class="l">#</th><th class="l">{T("平台", "Platform")}</th><th class="l">{T("链", "Chain")}</th>'
              f'<th>{T("当日手续费", "Fees (day)")}</th><th>{T("手续费份额", "Fee share")}</th><th>{T("日环比", "DoD")}</th></tr></thead><tbody>{lp_rows}</tbody></table></div>'
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
        fz = f'<span class="chip frz">{T("日志", "log")} · {TT(lg.get("生成时间UTC"))} {T("冻结", "frozen")}</span>' if n == 0 else ""
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
</div>
<div class="stamp">{times_line(tlog)}</div></div>
{comp_block(comp, None, tlog, full=False)}
<h2>{T("今日变化", "What changed today")} <span class="sub">{esc(ch_base)}</span><span class="sp"></span><button class="btn" onclick="shareHome()">📸 {T("生成今日长图", "Share image")}</button></h2>
<div class="card board changes">{ch_html}</div>
<div class="grid g4" style="margin-top:14px">{heroes}</div>
<h2>{T("四层信号灯", "Four-layer signals")} <span class="sub">{T("点进去看每层结论、依据和每个指标的全部历史", "Click through for each layer's verdict, evidence and every gauge's full history")}</span></h2>
{signal_tiles(G["VS"], G["JBY"], G.get("L2"))}
{leg_home_card()}
{core_home_card()}
{alpha_home_card()}
{aia_home_card()}
{rwa_home_card()}
{cal_home_card(G.get("CAL"))}
<div class="grid g2" style="margin-top:22px;align-items:start">
<div><h2 style="margin-top:12px">{T("发射台矩阵 · 当日 Top6", "Launchpads · top 6 today")} {cycle_tag()} <a class="sub" href="{U("/launchpad/")}">{T("全部", "All")} {len((matrix or {}).get("协议", []))} {T("个协议 →", "protocols →")}</a></h2>{lp_tbl}</div>
<div><h2 style="margin-top:12px">{T("板块轮动 · 24h 领涨", "Rotation · 24h leaders")} <a class="sub" href="{U("/rotation/")}">{T("看全部 →", "See all →")}</a></h2>{cats}</div>
</div>
{reports_block}
<h2>{T("解读日志", "Journal")} <a class="sub" href="{U("/journal/")}">{T("全部日志与复盘 →", "All logs and reviews →")}</a></h2>
{jl}"""
    js = f"<script>function shareHome(){{ucShare({json.dumps(share_obj, ensure_ascii=False)})}}</script>"
    emit("index.html", T(f"{BRAND} · 链上数据情报终端", f"{BRAND_EN} · Onchain research terminal"), body, active="home", share=True,
         scripts=js + leg_assets()[1], extra_head=leg_assets()[0] + f'<link rel="stylesheet" href="{ASSET_URL["core.css"]}">',
         desc=LF(comp or {}, "一句话") or T(SLOGAN, SLOGAN_EN))


def ind_card(ind, j, as_of, extra=""):
    """指标卡（全站一个组件；L2 六张卡和 L1/L3/L4 同一套样式）。"""
    name = T(ind["名称"], ind["EN"])
    lvl = T(ind["级别"], LEVEL_EN.get(ind["级别"], ind["级别"])) + (f" · {T(ind['级别注'], ind['级别注EN'])}" if ind.get("级别注") else "")
    head = (f'<div class="top"><span class="nm">{esc(name)}<span class="grade lv" data-tag="{esc(ind["级别"])}" tabindex="0">{esc(lvl)}</span>'
            f'{grade_chip(ind.get("等级"))}</span>')
    obs = (" obs" if ind["级别"] == "观察" else "") + (" core" if ind["级别"] == "核心" else " aux")
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
    """按注册表的分组和顺序出卡片（M12）。视觉层级：核心指标用完整卡片；辅助 / 观察 / 描述用紧凑小卡；
    整组都不是核心的，合并折叠成最后一组「辅助与观察（不进本层判定）」。"""
    inds = ind_layer_list(layer)
    groups = []
    for ind in inds:
        if (ind["组"], ind["组EN"]) not in groups:
            groups.append((ind["组"], ind["组EN"]))
    out, folded, n_fold = [], "", 0
    for g in groups:
        gi = [x for x in inds if x["组"] == g[0]]
        core = [x for x in gi if x["级别"] == "核心"]
        aux = [x for x in gi if x["级别"] != "核心"]
        card = lambda x: ind_card(x, G["JBY"].get(x["key"]), as_of, extra_fn(x) if extra_fn else "")
        aux_h = f'<div class="grid g4 auxgrid">{"".join(card(x) for x in aux)}</div>' if aux else ""
        if core:
            out.append((g, f'<div class="grid g4">{"".join(card(x) for x in core)}</div>' + aux_h))
        else:
            folded += f'<div class="auxg">{esc(T(*g))}</div>' + aux_h
            n_fold += len(aux)
    if folded:
        out.append((("辅助与观察（不进本层判定）", "Auxiliary & watch (not in the verdict)"),
                    f'<details class="auxfold"><summary>{T(f"展开 {n_fold} 项", f"Show {n_fold} items")}</summary>{folded}</details>'))
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
LAYER_RULE_DATES = {1: ("2026-10-02", "2026-10-04"), 2: ("2026-10-08",), 3: ("2026-10-11",)}


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


def ruler_svg(price, levels, h=460, w=440, date=None):
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
    out.append(f'<text x="{w - 6}" y="{yp - 6:.1f}" text-anchor="end" class="rnl">{T("收盘价", "Close")} ${price:,.0f}</text>')
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
            f'<p class="tnote" style="margin:0 0 4px"><b>{T("收盘价", "Close")} ${price:,.0f}</b> · {TCLOSE(l2.get("data_date"))}</p><div class="r6">{ruler_svg(price, key6, date=l2.get("data_date"))}</div><div class="r13">{ruler_svg(price, lv, h=560, date=l2.get("data_date"))}</div>'
            f'<p class="tnote">{T("价格用", "Price = ")}{TCLOSE(l2.get("data_date"))}{T("，括号里的百分比都相对这个收盘价。对数刻度，按真实价格距离摆放；绿色 = 收盘价下方的支撑，红色 = 上方的压力。价位都由 l2_daily.py 每天算好，网页只展示（均衡价格为近似值）。", "; the percentages are measured from this close. Log scale, placed by real price distance; green = supports below, red = resistance above. All levels come from l2_daily.py; the page only displays them (balanced price is approximate).")}</p></div>'
            f'<details class="card fold"><summary>{T("13 条关键价位表", "All 13 levels (table)")}</summary><div class="tw" style="margin:0;border:0"><table><thead><tr><th class="l">{T("价位", "Level")}</th>'
            f'<th>{T("价格", "Value")}</th><th>{T("离收盘价", "vs close")}</th></tr></thead><tbody>{rows}</tbody></table></div></details>')


def l2_card_extra(ind):
    """L2 卡片与 14 条信号保持一致：信号靠 30 天记忆仍亮、而当前读数已不满足时，卡片上写明。"""
    for x in (G.get("L2") or {}).get("signals") or []:
        if x.get("metric") == ind["key"] and x.get("on") and x.get("now_true") is False and x.get("last_true"):
            return T(f"（对应信号仍亮：30 天记忆，最近一次满足 {x['last_true']}）", f" (signal still on: 30-day memory, last met {x['last_true']})")
    return ""


def l2_tab(l2, as_of):
    if not l2 or (l2.get("state") or {}).get("code") not in R.L2_STATES:
        return empty_state("pending", T("L2 周期状态机 · 等待首次运行", "L2 cycle state machine · awaiting first run"),
                           T(f"每天{TT(L2_TIME, False)}由 GitHub Actions 运行 l2/l2_daily.py 生成。", f"Generated daily at {TT(L2_TIME, False)} by l2/l2_daily.py."), "")
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
            f' · {T("运行", "run")} {TT(l2.get("updated_utc"))} {chips}</div>'
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


# ---------------------------------------------------------------- L3 筹码层（只读 data/l3/*.json 展示，规则和计算都在 l3/l3_daily.py）
L3_TIME = next((x["时间"] for x in SCHED if x["文件"] == "l3-daily.yml"), "02:47")
L4_TIME = next((x["时间"] for x in SCHED if x["文件"] == "l4-daily.yml"), "03:17")
L3_RES = {"held": ("守住", "Held", "up"), "broken": ("被突破", "Broken", "dn"), "open": ("进行中", "Ongoing", "neutral")}
L3_NOT_SHOWN = [
    ("「筹码墙 = 强支撑 / 强压力」", "'Supply wall = strong support / resistance'", "同距离比较，筹码墙守住率和真空区的差在各年代正负相反，2022 年后筹码墙更容易被穿过", "At equal distance the wall-vs-gap hold-rate difference flips sign across eras; since 2022 walls are crossed more easily", "§4.3"),
    ("「真空区 / 断层必回补」", "'Gaps always get filled'", "价格更常回到筹码密集区，不是回补真空区", "Price returns to dense zones more often, not to gaps", "§4.3"),
    ("分龄成本线（1-3M、3-6M、6-12M、1-2Y、<10Y）、<1 个月成本当支撑压力", "Age-band cost lines and <1-month cost as support/resistance", "不比对照线好，<1 个月成本明显更差", "No better than placebo lines; the <1-month cost is clearly worse", "§4.1"),
    ("STH-SOPR / aSOPR = 1、STH 盈亏比 = 1 当多空分界", "STH-SOPR / aSOPR = 1 or STH P/L ratio = 1 as the bull/bear line", "穿越后收益和同状态普通日子没区别", "Returns after crossing match ordinary days in the same state", "§4.5"),
    ("「交易所余额下降 / 鲸鱼增持 → 要涨」", "'Falling exchange balances / whales buying → up'", "只有同步关系，没有提前量", "Coincident only, no lead", "§4.6"),
    ("MVRV 一年均值带、STH 成本 −1σ、MVRV 历史均值线", "MVRV one-year mean bands, STH cost −1σ, historical-mean MVRV line", "不显著", "Not significant", "§4.2"),
    ("AVIV 价位带", "AVIV price bands", "免费数据口径复现不了", "Cannot be reproduced on free data", "§4.2"),
    ("矿工储备", "Miner reserves", "没有提前量；数据源需要付费 token，网页不接", "No lead; the source needs a paid token, not wired", "§4.6"),
    ("具体分析师的价位判断", "Specific analysts' price levels", "624 个价位整体不比同距离随机价位准", "624 levels were overall no more accurate than random levels at the same distance", "§4.7"),
]
L3_NOTE = ("只展示通过历史检验的规则。对照组是形状一样、位置不同的假线；大多数链上成本线和筹码密集区作支撑压力都不比假线强，所以只作描述。数据为 UTXO 口径，数值和 Glassnode 等平台会有差异。样本有限，所有结论最高到「已验证·方向」，不构成投资建议。",
           "Only rules that passed historical tests are shown. The control group is placebo lines of the same shape at a different level; most on-chain cost lines and dense supply zones do no better than placebos as support or resistance, so they are descriptive only. Data is UTXO-based and will differ from Glassnode and similar platforms. Samples are limited; every conclusion is at most 'validated · direction'. Not investment advice.")


def l3_card_extra(ind):
    l3 = G.get("L3") or {}
    if ind["key"] == "l3_p1s" and (l3.get("p1s") or {}).get("lo"):
        a = l3["p1s"]
        return T(f"；压力区 ${a['lo']:,.0f} ~ ${a['hi']:,.0f}", f"; zone ${a['lo']:,.0f}–${a['hi']:,.0f}")
    if ind["key"] == "l3_conc" and (l3.get("warning") or {}).get("conc_date"):
        w = l3["warning"]
        rk = f"，2022 年以来第 {w['conc_rank_2022']} 百分位" if w.get("conc_rank_2022") is not None else ""
        rk_en = f", {w['conc_rank_2022']}th percentile since 2022" if w.get("conc_rank_2022") is not None else ""
        return T(f"（{w['conc_date']} 的筹码分布{rk}）", f" (URPD of {w['conc_date']}{rk_en})")
    return ""


def _m0(v):
    return "—" if v is None else f"${v:,.0f}"


def _pc(v):
    return "—" if v is None else f"{v:+.1f}%".replace("-", "−")


def l3_posbar(l3):
    """价格位置条：对数横轴，标 STH 成本、+1σ 压力区（±2% 色带）、STH-MVRV 1.3、现价。"""
    p, a, s = l3["price"], l3["p1s"], l3["sth"]
    s13 = l3.get("sth_13")
    pts = [x for x in (p, a["value"], s["value"], s13) if x]
    lo, hi = math.log(min(pts) * 0.93), math.log(max(pts) * 1.05)
    X = lambda v: (math.log(v) - lo) / (hi - lo) * 100
    mk = lambda v, cls, zh, en, up=False: (f'<div class="pb-m {cls}{" up" if up else ""}" style="left:{X(v):.2f}%"><i></i>'
                                            f'<span><b>{esc(T(zh, en))}</b>{_m0(v)}</span></div>')
    zone = f'<div class="pb-zone" style="left:{X(a["lo"]):.2f}%;width:{X(a["hi"]) - X(a["lo"]):.2f}%"></div>'
    s13m = mk(s13, "s13", "STH-MVRV 1.3（趋势区起点·假设）", "STH-MVRV 1.3 (trend zone, hypothesis)") if s13 else ""
    return (f'<div class="card l3pos"><div class="eb">L3 {T("价格位置", "price position")} · {T("数据日", "data date")} {esc(l3.get("data_date") or "—")}'
            f' · {T("运行", "run")} {TT(l3.get("updated_utc"))}'
            + (f' <span class="chip l2stale">{T("数据延迟 · 用了缓存", "Data delayed · cached")}</span>' if (l3.get("data_status") or {}).get("stale") else "")
            + f'</div><h3 class="st">{esc(T(l3["position"]["zh"], l3["position"]["en"]))}</h3>'
            f'<div class="pbar">{zone}{mk(s["value"], "sth", "STH 成本", "STH cost")}{mk(a["value"], "p1s", "+1σ 压力区", "+1σ zone", True)}{s13m}'
            f'{mk(p, "px", "收盘价", "Close")}</div><p class="tnote" style="margin-top:4px">{T("价格用", "Price = ")}{TCLOSE(l3.get("data_date"))}</p>'
            f'<p class="tnote">{T("色带 = +1σ 压力区（上下 2%），是一个区域，不是一根精确的线。L3 只回答价位和波动幅度，方向看 L2，节奏看 L1。", "The band is the +1σ pressure zone (±2%) — a zone, not a precise line. L3 only covers levels and move size; direction comes from L2, pace from L1.")}</p></div>')


def l3_touch_rows(xs):
    rows = ""
    for x in reversed(xs):
        zh, en, tone = L3_RES.get(x["result"], ("—", "—", "neutral"))
        rd = f' <span class="d">{x["result_date"][5:]}</span>' if x.get("result_date") else ""
        rows += (f'<tr><td>{x["date"]}</td><td>{_m0(x["price"])}</td><td>{_m0(x["line"])}</td>'
                 f'<td class="l">{tone_chip(T(zh, en), tone)}{rd}</td></tr>')
    return (f'<div class="tw"><table class="l3t"><thead><tr><th>{T("碰线日", "Touch")}</th><th>{T("收盘价", "Close")}</th><th>{T("当天线位", "Line")}</th>'
            f'<th class="l">{T("30 天结果", "30-day result")}</th></tr></thead><tbody>{rows or "<tr><td colspan=4>—</td></tr>"}</tbody></table></div>')


def l3_main_cards(l3):
    a, w = l3["p1s"], l3.get("warning") or {}
    st_tone = "warn" if l3["position"]["code"] == "in_zone" else "neutral"
    left = (f'<div class="card l3main"><div class="top"><span class="nm">{T("上方压力区 · STH 成本 +1σ", "Pressure zone above · STH cost +1σ")}</span>{grade_chip("已验证·方向")}</div>'
            f'<div class="v">{_m0(a["value"])} <span class="sub">{T("离收盘价", "vs close")} {_pc(a["pct_from_price"])}</span></div>'
            f'<div class="b">{T("压力区", "Zone")} {_m0(a["lo"])} ~ {_m0(a["hi"])} · {tone_chip(T(a["status_zh"], a["status_en"]), st_tone)}</div>'
            f'<p class="tnote">{esc(T(a["hold_rate_zh"], a["hold_rate_en"]))}{T("。用法：多单止盈参考、追高提醒；不当挂单位；冲过去站上 STH-MVRV 1.3 不据此做空。", ". Use: a take-profit reference and a no-chasing reminder; not an order level; no shorting once price breaks through and holds STH-MVRV 1.3.")}</p>'
            f'<div class="sub2">{T("最近 5 次碰线（从下方碰到压力区）", "Last 5 touches (from below)")}</div>{l3_touch_rows(a.get("touches") or [])}</div>')
    on = bool(w.get("on"))
    vol, conc = w.get("vol30"), w.get("conc")
    vb = min(100, (vol or 0) / 100 * 100)
    cb = min(100, (conc or 0) / 25 * 100)
    rk = T(f"，2022 年以来第 {w['conc_rank_2022']} 百分位", f", {w['conc_rank_2022']}th pct since 2022") if w.get("conc_rank_2022") is not None else ""
    right = (f'<div class="card l3main l3warn{" on" if on else ""}"><div class="top"><span class="nm">{T("大波动预警", "Large-move warning")}</span>{grade_chip("已验证·方向")}</div>'
             f'<div class="lamp"><i></i><b>{T("亮", "ON") if on else T("不亮", "Off")}</b></div>'
             + (f'<p class="big">{esc(T(w.get("text_zh") or "", w.get("text_en") or ""))}</p>' if on else
                f'<p class="big quiet0">{T("条件没同时满足：要 30 天波动低于 40%、且筹码集中度不低于 12%。", "Conditions not both met: 30-day volatility below 40% and supply concentration at least 12%.")}</p>')
             + f'<div class="meter"><div class="ml"><span>{T("30 天年化波动", "30-day volatility")}</span><b>{"—" if vol is None else f"{vol:.1f}%"}</b><em>{T("低于 40% 才算", "counts below 40%")}</em></div>'
             f'<div class="mb"><span style="width:{vb:.1f}%" class="{"ok" if vol is not None and vol < 40 else ""}"></span><i style="left:40%"></i></div></div>'
             f'<div class="meter"><div class="ml"><span>{T("筹码集中度（现价 ±5%）", "Concentration (price ±5%)")}</span><b>{"—" if conc is None else f"{conc:.1f}%"}</b><em>{T("不低于 12% 才算", "counts at 12%+")}</em></div>'
             f'<div class="mb"><span style="width:{cb:.1f}%" class="{"ok" if conc is not None and conc >= 12 else ""}"></span><i style="left:48%"></i></div></div>'
             f'<p class="tnote">{T("只说幅度，不说方向：亮灯后顺着 MA200 趋势做并不更准，所以只用于「该做的风控照做」——逐笔确认止损、盯衰竭信号。", "Magnitude only, not direction: following the MA200 trend after the light is no more accurate, so it only means doing the risk control you should — confirm every stop, watch for exhaustion.")}'
             f'{T("集中度数据日 ", " Concentration as of ")}{esc(w.get("conc_date") or "—")}{rk}{T("。", ".")}</p></div>')
    return f'<div class="grid g2 l3mains">{left}{right}</div>'


def l3_chipmap(l3):
    cmap = l3.get("chip_map") or {}
    bins = cmap.get("bins") or []
    if not bins:
        return empty_state("none", T("筹码分布 · 等待数据", "Supply map · awaiting data"), T("l3_daily.py 取到 URPD 后显示。", "Shown once l3_daily.py fetches a URPD."), "")
    p = l3["price"]
    lo, hi = math.log(bins[0]["lo"]), math.log(bins[-1]["hi"])
    W, H, B = 1000, 220, 22
    X = lambda v: (math.log(v) - lo) / (hi - lo) * W
    mx = max(b["supply"] for b in bins) or 1
    bars = ""
    for b in bins:
        x0, x1 = X(b["lo"]), X(b["hi"])
        h = b["supply"] / mx * (H - B - 8)
        cls = {"dense": "dn0", "sparse": "sp0"}.get(b["cls"], "md0")
        bars += (f'<rect class="{cls}" x="{x0:.1f}" y="{H - B - h:.1f}" width="{max(0.5, x1 - x0 - 0.6):.1f}" height="{h:.1f}">'
                 f'<title>${b["lo"]:,.0f} ~ ${b["hi"]:,.0f}: {b["supply"]:,.0f} BTC</title></rect>')
    ticks = ""
    for f in (0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3):
        v = p * f
        if bins[0]["lo"] * 1.03 <= v <= bins[-1]["hi"] / 1.03:
            ticks += f'<text class="ax" x="{X(v):.1f}" y="{H - 6}" text-anchor="middle">{"$" + format(round(v, -2), ",.0f") if f != 1.0 else T("现价", "price")}</text>'
    px = X(p)
    svg = (f'<svg class="l3map" viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" aria-label="{esc(T("筹码分布", "Supply distribution"))}">'
           f'{bars}<line class="pxl" x1="{px:.1f}" x2="{px:.1f}" y1="0" y2="{H - B}"/>{ticks}</svg>')
    walls = "；".join(f'${w["lo"]:,.0f} ~ ${w["hi"]:,.0f}（{w["supply"]:,} BTC，{w["share_pct"]}%）' for w in cmap.get("dense_ranges") or [])
    walls_en = "; ".join(f'${w["lo"]:,.0f}–${w["hi"]:,.0f} ({w["supply"]:,} BTC, {w["share_pct"]}%)' for w in cmap.get("dense_ranges") or [])
    leg = (f'<div class="l2leg"><span><i class="dn0"></i>{T("密集区（平滑后前 5%）", "Dense (top 5% after smoothing)")}</span>'
           f'<span><i class="md0"></i>{T("一般", "Normal")}</span><span><i class="sp0"></i>{T("稀疏区（后 30%）", "Sparse (bottom 30%)")}</span>'
           f'<span><i class="pxi"></i>{T("现价", "Price")}</span></div>')
    note = T("每枚币按最后一次在链上移动时的价格分档。密集区更像「磁铁 + 换手区」，不是墙：同距离比较，筹码墙作支撑压力和真空区的差在各年代正负相反，2022 年后筹码墙更容易被穿过；「真空区必回补」也不成立。",
             "Each coin is bucketed by the price at which it last moved. Dense zones behave like magnets and turnover areas, not walls: at equal distance the wall-vs-gap difference as support/resistance flips sign across eras, walls are crossed more easily since 2022, and “gaps always fill” does not hold.")
    return (f'<div class="card chartcard"><h3 style="margin-top:0">{T("筹码分布（描述）· 现价 ±30%", "Supply distribution (descriptive) · price ±30%")} '
            f'<span class="sub">URPD · {esc(cmap.get("date") or "—")} · {T("约 0.95% 一档", "~0.95% per bucket")}</span></h3>{leg}{svg}'
            f'<p class="tnote">{T("密集区：", "Dense zones: ")}{esc(T(walls, walls_en) or "—")}。'
            f'{note}</p></div>')


def l3_charts():
    ser = G.get("L3S")
    if not ser:
        return ""
    if "L3CHART" not in G:
        d0 = dt.date.fromisoformat(ser["start"])
        start = "2012-01-01"

        def col(k, f=None):
            vals = ser["series"].get(k) or []
            out = {}
            for i, v in enumerate(vals):
                d = (d0 + dt.timedelta(days=i)).isoformat()
                if v is not None and d >= start:
                    out[d] = f(v) if f else v
            return out
        p1 = col("p1s")
        G["L3CHART"] = put_multi("l3_chart", {"price": col("price"), "sth_rp": col("sth_rp"), "p1s": p1,
                                              "p1s_hi": {d: v * 1.02 for d, v in p1.items()}, "p1s_lo": {d: v * 0.98 for d, v in p1.items()},
                                              "tmmp": col("tmmp"), "warn": col("warn", lambda v: int(v))})
        G["L3VOL"] = put_multi("l3_volconc", {"vol30": col("vol30"), "conc": col("conc")})
    states = [None, {"n": T("大波动预警亮", "Large-move warning on"), "c": "warn"}]
    cfg = {"v2": True, "src": G["L3CHART"], "fmt": "price", "log": True, "ranges": ["1Y", "3Y", "5Y", "ALL"], "range": "1Y", "group": "l3c",
           "stk": "warn", "states": states, "toggle": True, "last": False,
           "note": T("对数坐标。橙色细线之间 = +1σ 压力区（上下 2%）；底色 = 当天大波动预警亮（历史日子按同一规则回算，属于样本内）。真实市场均价是 L2 的周期状态线，不作支撑压力。",
                     "Log scale. Between the orange lines = the +1σ pressure zone (±2%); shading = days with the large-move warning on (past days recomputed with the same rule, in-sample). The true market mean is an L2 cycle-state line, not support or resistance."),
           "series": [{"k": "price", "n": T("BTC 价格", "BTC price"), "c": "ink", "w": 2.0},
                      {"k": "p1s", "n": T("STH 成本 +1σ（压力区）", "STH cost +1σ (pressure zone)"), "c": "warn", "w": 1.6},
                      {"k": "p1s_hi", "n": T("压力区上沿 +2%", "Zone top +2%"), "c": "warn", "w": 0.7},
                      {"k": "p1s_lo", "n": T("压力区下沿 −2%", "Zone bottom −2%"), "c": "warn", "w": 0.7},
                      {"k": "sth_rp", "n": T("STH 成本（参考支撑）", "STH cost (reference support)"), "c": "s3", "w": 1.4},
                      {"k": "tmmp", "n": T("真实市场均价（L2 状态线）", "True market mean (L2 state line)"), "c": "s9", "w": 1.0}]}
    vcfg = {"v2": True, "src": G["L3VOL"], "fmt": "pct1", "ranges": ["1Y", "3Y", "5Y", "ALL"], "range": "1Y", "group": "l3c", "h": 220,
            "lines": [{"v": 40, "label": T("波动 40%", "vol 40%"), "tone": "warn"}, {"v": 12, "label": T("集中度 12%", "conc 12%"), "tone": "warn"}],
            "note": T("预警 = 30 天波动低于 40% 且集中度不低于 12%。集中度 2012 年起每周日一张筹码分布，之后每天一张。",
                      "Warning = 30-day volatility below 40% and concentration at least 12%. Concentration uses one URPD every Sunday since 2012, daily afterwards."),
            "series": [{"k": "vol30", "n": T("30 天年化波动", "30-day volatility"), "c": "s1"}, {"k": "conc", "n": T("筹码集中度（±5%）", "Concentration (±5%)"), "c": "s2"}]}
    return (f'<div class="card chartcard" style="margin-top:12px"><h3 style="margin-top:0">{T("价格 + STH 成本 + 压力区 + 预警日", "Price + STH cost + pressure zone + warning days")}</h3>'
            + chart_div(cfg) + f'<h3>{T("30 天波动与筹码集中度", "30-day volatility and supply concentration")}</h3>' + chart_div(vcfg) + "</div>")


def l3_tab(l3, as_of):
    if not R.l3_ok(l3):
        return empty_state("pending", T("L3 筹码层 · 等待首次运行", "L3 supply layer · awaiting first run"),
                           T(f"每天{TT(L3_TIME, False)}由 GitHub Actions 运行 l3/l3_daily.py 生成（第一次运行会补 2012 年以来每周一张的筹码分布，可能要分几天补完）。",
                             f"Generated daily at {TT(L3_TIME, False)} by l3/l3_daily.py (the first runs back-fill one URPD per week since 2012 and may take a few days)."), "")
    groups = cards_by_group(3, as_of, l3_card_extra)
    cards = "".join(f'<h3 id="grp-3-{n}">{esc(T(*g))}</h3>{c}' for n, (g, c) in enumerate(groups))
    sth = l3.get("sth") or {}
    sup = (f'<details class="raw l3d"><summary>{T("STH 成本（参考支撑）最近 5 次碰线", "STH cost (reference support): last 5 touches")}</summary>'
           f'<p class="tnote">{esc(T(sth.get("hold_rate_zh") or "", sth.get("hold_rate_en") or ""))}</p>{l3_touch_rows(sth.get("touches") or [])}</details>')
    line = T(l3.get("daily_line_zh") or "", l3.get("daily_line_en") or "")
    return (l3_posbar(l3) + l3_main_cards(l3) + sup + cards + l3_chipmap(l3) + l3_charts()
            + f'<p class="tnote">{T("每日一行：", "Daily line: ")}<code>{esc(line)}</code></p>')


def exetf_block(S):
    """交易所 + 现货 ETF 持币：堆叠图 + 最近 30 天「交易所流出的币去哪了」一句描述（不推方向）。"""
    ex, etf, tot = S.get("ex_balance") or {}, S.get("etf_btc") or {}, R.s_exetf(S)
    if not etf or not tot:
        return ""
    d1 = max(tot)
    d0 = R.shift(d1, -30)
    k0 = max([d for d in tot if d <= d0] or [None]) if any(d <= d0 for d in tot) else None
    line = ""
    if k0:
        eds = sorted(etf)
        def etf_at(d):
            i = R.bisect.bisect_right(eds, d) - 1
            return etf[eds[i]] if i >= 0 else None
        dex, detf = ex[d1] - ex[k0], etf_at(d1) - etf_at(k0)
        dtot = dex + detf
        f = lambda v: f"{v:+,.0f}".replace("-", "\u2212")
        if dex < 0 and detf > 0:
            share = min(100, detf / -dex * 100)
            zh = (f"{k0} → {d1}：交易所 {f(dex)} 枚，同期 ETF {f(detf)} 枚，合计 {f(dtot)} 枚。交易所流出的币里约 {share:.0f}% 的量和 ETF 增持对得上"
                  + ("；合计也在减少，其余多半去了链上自托管。" if dtot < 0 else "。"))
            en = (f"{k0} → {d1}: exchanges {f(dex)} BTC, ETFs {f(detf)} BTC, combined {f(dtot)} BTC. About {share:.0f}% of the exchange outflow is matched by ETF buying"
                  + ("; the total fell too, so the rest most likely went to on-chain self-custody." if dtot < 0 else "."))
        else:
            zh = f"{k0} → {d1}：交易所 {f(dex)} 枚，ETF {f(detf)} 枚，合计 {f(dtot)} 枚。"
            en = f"{k0} → {d1}: exchanges {f(dex)} BTC, ETFs {f(detf)} BTC, combined {f(dtot)} BTC."
        line = f'<p class="exetf-line">{esc(T(zh, en))}</p>'
    if "EXETF" not in G:
        eds = sorted(etf)
        ff = {}
        for d in sorted(ex):
            if d < "2023-10-01":
                continue
            i = R.bisect.bisect_right(eds, d) - 1
            ff[d] = etf[eds[i]] if i >= 0 and R.days_between(eds[i], d) <= 4 else (0 if d < eds[0] else None)
        G["EXETF"] = put_multi("exetf_chart", {"ex": {d: v for d, v in ex.items() if d >= "2023-10-01"}, "etf": ff})
    cfg = {"v2": True, "src": G["EXETF"], "fmt": "btc", "stack": True, "ranges": ["1Y", "ALL"], "range": "ALL", "group": "l3",
           "series": [{"k": "ex", "n": T("交易所余额", "Exchange balance"), "c": "s3"}, {"k": "etf", "n": T("现货 ETF 持币", "Spot ETF holdings"), "c": "s1"}],
           "note": T("ETF 持币 = 合计净资产 ÷ 当天 BTC 参考价（TFTC · The Commoner ETF Tracker，CC BY 4.0）；交易所余额来自 CoinMetrics，免费档约晚 2~3 周。只作同步描述。",
                     "ETF holdings = total net assets ÷ that day's BTC reference price (TFTC · The Commoner ETF Tracker, CC BY 4.0); exchange balances from CoinMetrics, ~2–3 weeks late on the free tier. Coincident description only.")}
    return (f'<div class="card chartcard" style="margin-top:12px"><h3 style="margin-top:0">{T("交易所 + 现货 ETF 持币 · 链上和链下合起来看", "Exchanges + spot ETFs · on- and off-chain together")} '
            f'<span class="sub">{T("合计", "Total")} {tot[d1]:,.0f} BTC · {d1}</span></h3>' + line + chart_div(cfg) + "</div>")


def l3_tail():
    banned = "".join(f'<li><b>{esc(T(a, b))}</b><span>{esc(T(c, d))}</span><em>{e}</em></li>' for a, b, c, d, e in L3_NOT_SHOWN)
    rep = next((r for r in ALL_REPORTS if "l3" in r["slug"] or "supply" in r["slug"]), None)
    rel = f'<p class="tnote">{T("相关研究：", "Related research: ")}<a href="{U("/reports/" + rep["slug"] + "/")}">{esc(LF(rep, "标题"))}</a></p>' if rep else ""
    return (f'<details class="raw l3d" style="margin-top:14px"><summary>{T("不展示 / 不再使用的说法（研究里测过不成立）", "Not shown / no longer used (failed in the study)")}</summary><ul class="l3ban">{banned}</ul></details>'
            + rel + f'<p class="l2disc">{esc(T(*L3_NOTE))}</p>')


# ---------------------------------------------------------------- L4 情绪衍生品层（只读 data/l4/*.json 展示，规则和计算都在 l4/l4_daily.py）
L4_LEV = ("fund_ma30", "fund_ma7", "qbasis", "cme_prem", "agg_oi_chg7", "agg_oi_mcap")
L4_SEN = ("fng", "dvol")
L4_STAT_EN = {
    "fund_ma30": "High funding does not predict pullbacks: after high percentiles the direction flips across eras (2018-21 excess −14.3, 2022-26 +7.6)",
    "fund_ma7": "Same as above; the 7-day average is noisier",
    "qbasis": "A high basis is not a top signal (9 cases, excess +6.0)",
    "cme_prem": "No excess return after a high premium (42 cases, −0.2)",
    "agg_oi_chg7": "Fast OI build-ups were not followed by deeper drawdowns, nor fast flushes by rebounds",
    "agg_oi_mcap": "Too few high-leverage samples (8)",
    "fng": "Fading extremes does not work: extreme greed was followed by strength, if anything",
    "dvol": "Low implied vol was followed by calmer markets, not big moves",
}
L4_WATCH_EN = {
    "big_liq": "Liquidations ÷ aggregated OI in the top 10% of two years: 25 cases, up 72% over 30 days (control 51%, p=0.03). Data only since 2022; exchanges under-report liquidations",
    "cme_low": "Bottom 10%: 23 cases in 2022-26, up 30% (control 53%); not seen in 2018-21",
    "qbasis_low": "Basis < 0: 7 cases, up 71% (control 49%); bottom-10% percentile since 2024: 12 cases, 75%",
    "dvol_low": "DVOL bottom 10%: 24 cases, up 42% (control 58%), calmer afterwards",
    "elr_low": "Aggregated OI ÷ exchange balance bottom 10%: 10 cases, up 80% (control 58%), only since 2022",
    "lev_drop": "Net position 4-week change bottom 10%: 13 cases, up 31% (control 52%); may mostly reflect basis-trade flows",
}
L4_NOTE = ("只有「资金费率 30 日均转负」一条通过了历史检验，会改变动作；其余读数只描述温度。费率高要回调、恐慌是买点、OI 堆积会瀑布、低波动是大行情前夜，这些常见说法用我们的口径检验都不成立。分位 = 今天的值在过去两年里排第几。样本有限，最高到「已验证·方向」，不构成投资建议。",
           "Only '30-day average funding below zero' passed historical testing and changes the action; every other reading only describes temperature. 'High funding means a pullback', 'fear is a buy', 'OI build-ups cause cascades', 'low volatility precedes big moves' — common claims that did not hold in our tests. Percentile = where today's value ranks over the past two years. Samples are limited; the highest grade is 'validated · direction'. Not investment advice.")
L4_BAND_TONE = {"过热": "warn", "偏热": "warn", "中性": "neutral", "偏冷": "cool", "极冷": "cool"}


def l4_fmt(x):
    v, u = x.get("value"), x.get("unit") or ""
    if v is None:
        return "—"
    s_ = f"{v:,.2f}" if abs(v) < 10 and u == "%" else (f"{v:,.1f}" if u == "%" else f"{v:,.1f}".rstrip("0").rstrip("."))
    return (s_ + u).replace("-", "−") if s_.startswith("-") else s_ + u


def l4_last_neg():
    for h in reversed(G.get("L4H") or []):
        if h.get("fund_ma30") is not None and h["fund_ma30"] < 0:
            return h["date"]
    return None


def l4_signal_card(l4):
    sg = l4.get("signal") or {}
    det = (l4.get("data_status") or {}).get("detail") or {}
    stale = det.get("funding") not in (None,) and not str(det.get("funding", "")).startswith("ok")
    on = bool(sg.get("on")) and not stale
    v = sg.get("value_pct")
    # 0 线刻度：−10% ~ +30% 年化映射到 0~100
    pos = None if v is None else max(0.0, min(100.0, (v + 10) / 40 * 100))
    zero = 25.0
    if stale:
        state = f'<div class="lamp"><i></i><b>{T("今天不判断", "No call today")}</b></div><p class="big quiet0">{T("资金费率数据延迟，今天不判断，不拿旧值顶替。", "Funding data is delayed; no call today and no stale value substituted.")}</p>'
    elif on:
        state = (f'<div class="lamp"><i></i><b>{T("亮", "ON")}</b><span class="dd">{T("已连续", "for")} {sg.get("days_on")} {T("天", "days")}{T("（自 ", " (since ")}{esc(sg.get("since") or "—")}{T("）", ")")}</span></div>'
                 f'<p class="big">{esc(T(sg.get("use_zh") or "", "No new shorts; when L2 is not in a bear market, scaling in within the L1 budget is allowed. The risk budget does not grow."))}</p>')
    else:
        ln = l4_last_neg()
        state = (f'<div class="lamp"><i></i><b>{T("不亮", "Off")}</b><span class="dd">{T("最近一次为负：", "Last negative: ")}{esc(ln or T("近 400 天没有", "none in 400 days"))}</span></div>'
                 f'<p class="big quiet0">{T("资金费率 30 日均在 0 以上，不改动作。", "The 30-day average is above zero; no change to the action.")}</p>')
    bar = ""
    if pos is not None:
        bar = (f'<div class="zbar"><span class="neg" style="width:{zero}%"></span><i class="z" style="left:{zero}%"></i><b class="pt" style="left:{pos:.1f}%"></b></div>'
               f'<div class="zlab"><span>−10%</span><span style="left:{zero}%">0</span><span>+30%</span></div>')
    src = sg.get("funding_source") or det.get("funding") or "—"
    return (f'<div class="card l3main l3warn l4sig{" on" if on else ""}{" stale" if stale else ""}"><div class="top"><span class="nm">{esc(T(sg.get("name_zh") or "资金费率 30 日均转负（空头拥挤）", sg.get("name_en") or "30-day avg funding below zero (crowded shorts)"))}</span>{grade_chip("已验证·方向")}</div>'
            f'<div class="v">{"—" if v is None else (f"{v:+.2f}%".replace("-", chr(0x2212)))} <span class="sub">{T("30 日均 · 年化", "30-day avg · annualized")}</span></div>{bar}{state}'
            f'<p class="tnote">{esc(T(sg.get("stat_zh") or "", "31 independent events: up 74% of the time over the next 30 days (same era & cycle-state control 58%, p=0.054), 7.8 pp more on average, with shallower drawdowns; same direction in all three eras, 68 of 72 parameter sets agree. Weak when L2 is in a bear market (8 cases, 50%)."))}'
            f'{T(" 数据源：", " Source: ")}{esc(src)}{T("；数据日 ", "; data date ")}{esc(sg.get("data_date") or l4.get("data_date") or "—")}</p></div>')


def l4_thermo(x):
    p = x.get("pct_730d")
    band = x.get("band_zh") or "—"
    tone = L4_BAND_TONE.get(band, "neutral")
    ticks = "".join(f'<i style="left:{t}%"></i>' for t in (10, 30, 70, 90))
    if p is None:
        pbar = f'<div class="b">{T("历史不足两年，暂不给分位", "Less than two years of history; no percentile yet")}</div>'
    else:
        pbar = f'<div class="pbar4">{ticks}<b style="left:{p:.0f}%"></b></div><div class="b">{T("过去两年第", "2-year percentile ")} {p:.0f}{T(" 分位", "")}</div>'
    stale = x.get("value") is None
    return (f'<div class="card ind l4t{" pendc" if stale else ""}"><div class="top"><span class="nm">{esc(T(x["name_zh"], x.get("name_en") or x["name_zh"]))}</span>'
            f'{tone_chip(T(band, x.get("band_en") or band), tone) if not stale else ""}</div>'
            f'<div class="v">{esc(l4_fmt(x))}</div>{pbar if not stale else "<div class=b>" + T("数据延迟 · 截至 ", "Data delayed · as of ") + esc(x.get("data_date") or "—") + "</div>"}'
            f'<div class="ft"><span>{grade_chip("描述读数")}</span></div><p class="l4why">{esc(T(x.get("stat_zh") or "", L4_STAT_EN.get(x["key"], "")))}</p></div>')


def l4_chart():
    h = G.get("L4H") or []
    if len(h) < 30:
        return ""
    if "L4CHART" not in G:
        G["L4CHART"] = put_multi("l4_chart", {"price": {x["date"]: x.get("price") for x in h}, "sig": {x["date"]: (1 if x.get("signal") or (x.get("fund_ma30") is not None and x["fund_ma30"] < 0) else 0) for x in h},
                                              "f30": {x["date"]: x.get("fund_ma30") for x in h}, "f7": {x["date"]: x.get("fund_ma7") for x in h}})
    live = "2026-10-22"
    mk = [{"date": live, "type": "live", "label": T(f"← 研究回放 ｜ 实时记录 {live} 起 →", f"← research replay | live from {live} →")}]
    states = [None, {"n": T("资金费率 30 日均为负", "30-day funding below zero"), "c": "up"}]
    c1 = {"v2": True, "src": G["L4CHART"], "fmt": "price", "log": True, "ranges": ["1Y", "ALL"], "range": "ALL", "group": "l4c", "stk": "sig", "states": states,
          "markers": mk, "last": False, "series": [{"k": "price", "n": T("BTC 价格", "BTC price"), "c": "ink", "w": 1.8}],
          "note": T("底色 = 资金费率 30 日均为负的日子（信号亮）。", "Shading = days when the 30-day average funding was below zero (signal on).")}
    c2 = {"v2": True, "src": G["L4CHART"], "fmt": "pct1", "ranges": ["1Y", "ALL"], "range": "ALL", "group": "l4c", "zero": True, "h": 200, "markers": mk,
          "series": [{"k": "f30", "n": T("资金费率 30 日均（年化）", "Funding 30-day avg (ann.)"), "c": "s1", "w": 1.8}, {"k": "f7", "n": T("7 日均", "7-day avg"), "c": "s9", "w": 1.0}]}
    return (f'<div class="card chartcard" style="margin-top:12px"><h3 style="margin-top:0">{T("价格 + 资金费率 30 日均", "Price + 30-day average funding")}</h3>'
            + chart_div(c1) + chart_div(c2) + "</div>")


def l4_tab(l4, as_of):
    if not R.l4_ok(l4):
        return empty_state("pending", T("L4 情绪衍生品层 · 等待首次运行", "L4 sentiment layer · awaiting first run"),
                           T(f"每天{TT(L4_TIME, False)}由 GitHub Actions 运行 l4/l4_daily.py 生成。", f"Generated daily at {TT(L4_TIME, False)} by l4/l4_daily.py."), "")
    c = l4["conclusion"]
    th = {x["key"]: x for x in l4.get("thermometer") or []}
    lev = "".join(l4_thermo(th[k]) for k in L4_LEV if k in th)
    sen = "".join(l4_thermo(th[k]) for k in L4_SEN if k in th)
    ws = sorted(l4.get("watch") or [], key=lambda x: not x.get("on"))
    watch = "".join(f'<li class="{"on" if x.get("on") else ""}"><b>{esc(T(x["name_zh"], x.get("name_en") or x["name_zh"]))}</b>'
                    f'<span class="chip{" t-warn" if x.get("on") else ""}"><i></i>{T("亮", "on") if x.get("on") else T("未亮", "off")}</span>'
                    f'<em>{T("假设 · 不改动作", "hypothesis · no action")}</em><span class="s">{esc(T(x.get("stat_zh") or "", L4_WATCH_EN.get(x["key"], "")))}</span></li>' for x in ws)
    n_on = sum(1 for x in ws if x.get("on"))
    head = (f'<div class="card l3pos l4head"><div class="eb">L4 {T("BTC 短期杠杆与情绪温度", "BTC short-term leverage & sentiment temperature")} · {T("数据日", "data date")} {esc(l4.get("data_date") or "—")}'
            f' · {T("运行", "run")} {TT(l4.get("updated_utc"))}'
            + (f' <span class="chip l2stale">{T("部分数据延迟", "Some data delayed")}</span>' if (l4.get("data_status") or {}).get("stale") else "")
            + f'</div><div class="l4nums"><span>{T("杠杆", "Leverage")}<b>{esc(T(c.get("leverage_band_zh") or "—", R.BAND_EN.get(c.get("leverage_band_zh"), "—")))}</b></span>'
            f'<span>{T("情绪", "Sentiment")}<b>{esc(T(c.get("sentiment_band_zh") or "—", R.BAND_EN.get(c.get("sentiment_band_zh"), "—")))}</b></span>'
            f'<span>{T("综合分位", "Composite pct")}<b>{c.get("composite_pct", "—")}</b></span></div></div>')
    faq = [(T("分位怎么算？", "How is the percentile computed?"), T("今天的值在过去 730 天里排第几，只用当时以前的数据；≥90 过热、70~90 偏热、30~70 中性、10~30 偏冷、≤10 极冷。分档是描述，阈值是判断，不是检验出来的。", "Where today's value ranks over the past 730 days, using only data available at the time; ≥90 hot, 70–90 warm, 30–70 normal, 10–30 cool, ≤10 cold. The bands are descriptive; the cut-offs are judgement, not test results.")),
           (T("为什么费率高不算信号？", "Why isn't high funding a signal?"), T("高分位之后的方向在年代之间翻转（2018-21 超额 −14.3 个百分点，2022-26 +7.6），站不住。只有费率转负（空头拥挤）之后偏强、三个年代方向一致。", "After high percentiles the direction flips across eras (2018-21 excess −14.3 pp, 2022-26 +7.6) — it does not hold. Only negative funding (crowded shorts) was followed by strength, consistently in all three eras.")),
           (T("为什么替换掉旧温度计？", "Why replace the old thermometer?"), T("旧版（未平仓 7 日变化 > 资金费率 > 恐慌贪婪打分）没有经过检验，而且是单一交易所口径。新版每个读数都测过，测不出优势的只作描述。", "The old version (OI 7-day change > funding > Fear & Greed score) was never tested and used a single venue. Every reading in the new version was tested; those without an edge are descriptive only.")),
           (T("数据源和换源", "Sources and fallbacks"), T("资金费率：Coinalyze 的 Binance 永续，取不到依次换 BitMEX、OKX、Deribit，换源时用重叠日子自动校准；季度升水 Deribit；CME 升水 Yahoo + Coinbase；全市场 OI 与清算 Coinalyze；恐慌贪婪 alternative.me；DVOL Deribit。", "Funding: Binance perp via Coinalyze, then BitMEX, OKX, Deribit, auto-calibrated on overlapping days; quarterly basis from Deribit; CME premium from Yahoo + Coinbase; aggregated OI and liquidations from Coinalyze; Fear & Greed from alternative.me; DVOL from Deribit."))]
    faq_h = "".join(f'<details class="faq card"><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in faq)
    return (head + f'<div class="grid g2 l3mains">{l4_signal_card(l4)}<div class="card l3main"><div class="top"><span class="nm">{T("今天怎么读", "How to read today")}</span></div>'
            f'<p class="l4para">{esc(T(c.get("paragraph_zh") or "", R.综合.load_cfg()["L4"].get(c["level"], {}).get("分段EN", "").format(value="—", days="—", reading=c.get("key_reading_zh") or "")))}</p>'
            f'<p class="tnote">{esc(T(c.get("key_reading_zh") or "", ""))}</p></div></div>'
            + f'<h3 id="grp-4-0">{T("温度计 · 杠杆（只作描述）", "Thermometer · leverage (descriptive)")}</h3><div class="grid g3">{lev}</div>'
            + f'<h3 id="grp-4-1">{T("温度计 · 情绪（只作描述）", "Thermometer · sentiment (descriptive)")}</h3><div class="grid g3">{sen}</div>'
            + f'<details class="raw l3d l4watch"><summary>{T(f"观察项（假设，不改动作）· 亮 {n_on}/{len(ws)}", f"Watch items (hypotheses, no action) · {n_on}/{len(ws)} on")}</summary><ul>{watch}</ul></details>'
            + l4_chart()
            + f'<details class="raw l3d"><summary>{T("方法与 FAQ", "Method & FAQ")}</summary><div class="faqs" style="margin-top:8px">{faq_h}</div></details>'
            + f'<p class="l2disc">{esc(T(*L4_NOTE))}</p>')


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
        l3 = G.get("L3") or {}
        a, s_ = l3.get("p1s") or {}, l3.get("sth") or {}
        return T(f"收盘站上压力区上沿（{_m0(a.get('hi'))}）= 冲过压力区；进入 {_m0(a.get('lo'))} ~ {_m0(a.get('hi'))} = 在压力区；跌破 STH 成本（{_m0(s_.get('value'))}）= STH 成本下方。"
                 "大波动预警：30 天波动低于 40% 且筹码集中度不低于 12% 时亮。线每天随 STH 成本移动。",
                 f"A close above the zone top ({_m0(a.get('hi'))}) = through the zone; inside {_m0(a.get('lo'))}–{_m0(a.get('hi'))} = in the zone; below the STH cost ({_m0(s_.get('value'))}) = below STH cost. "
                 "Large-move warning: on when 30-day volatility is below 40% and supply concentration is at least 12%. The lines move daily with the STH cost.")
    return T("资金费率 30 日均跌破 0 = 信号（空头拥挤，唯一会改动作的一条）；否则按杠杆分位（费率 30 日均、OI ÷ 市值的平均）和情绪分位（恐慌贪婪）再平均：≥ 85 过热、65~85 偏热、≤ 35 偏冷、其余中性。分档是描述，不是检验出来的。",
             "30-day average funding below zero = signal (crowded shorts — the only action-changing rule); otherwise the leverage percentile (funding 30-day avg and OI ÷ market cap) and the sentiment percentile (Fear & Greed) are averaged: ≥ 85 hot, 65–85 warm, ≤ 35 cool, otherwise normal. The bands describe; they were not tested.")


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
        return chip("l3_p1s") + chip("l3_vol30") + chip("l3_conc")
    l4 = G.get("L4") or {}
    if not R.l4_ok(l4):
        return ""
    sg = l4.get("signal") or {}
    v = sg.get("value_pct")
    out = f'<a class="chip t-{"up" if sg.get("on") else "neutral"}" href="#layer-4"><i></i>{T("资金费率 30 日均", "Funding 30d avg")} {"—" if v is None else f"{v:+.2f}%".replace("-", chr(0x2212))}</a>'
    c = l4["conclusion"]
    return out + f'<span class="chip"><i></i>{T("杠杆", "Leverage")} {esc(T(c.get("leverage_band_zh") or "—", R.BAND_EN.get(c.get("leverage_band_zh"), "—")))} · {T("情绪", "sentiment")} {esc(T(c.get("sentiment_band_zh") or "—", R.BAND_EN.get(c.get("sentiment_band_zh"), "—")))}</span>'


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


def src_summary(st):
    ok = sum(1 for v in st.values() if v.get("ok"))
    bad = [k for k, v in st.items() if not v.get("ok")]
    tone = "up" if not bad else "warn"
    head = T(f"数据源 {ok}/{len(st)} 正常", f"Data sources {ok}/{len(st)} OK") + (T("：" + "、".join(bad) + " 延迟", ": " + ", ".join(SRC_EN.get(k, k) for k in bad) + " delayed") if bad else "")
    return f'<details class="srcd"><summary>{tone_chip(head, tone)}</summary><div class="src">{src_chips(st)}</div></details>'


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
            if i == 3:
                content = l3_tab(G.get("L3"), as_of) + pending_block(3)
            if i == 3 and S.get("ex_netflow"):
                cum = R.s_cum_netflow(S)
                first = min(cum)
                f = G["FILES"]
                content += ('<div class="card chartcard" style="margin-top:12px">'
                            + f'<h3 style="margin-top:0">{T("交易所 BTC 累计净流量 · 全部历史（只作描述；向下 = 币在持续离开交易所）", "Cumulative exchange BTC net flow · full history (down = coins leaving)")}</h3>'
                            + chart_div({"v2": True, "src": f["ex_netflow"]["raw"], "fmt": "btcs", "ranges": ["1Y", "3Y", "5Y", "ALL"], "range": "ALL", "group": "l3", "zero": True,
                                         "series": [{"k": "v", "n": T("累计净流量", "Cumulative net flow"), "c": "s1", "area": True}],
                                         "note": T(f"从 {first} 起逐日累加流入 − 流出（CoinMetrics flash 口径）。", f"Inflow − outflow summed daily since {first}.")})
                            + f'<h3>{T("交易所 BTC 余额 · 全部历史", "Exchange BTC balance · full history")} <a class="sub" href="{ind_href("ex_balance")}">{T("看区间与分位 →", "Zones & percentiles →")}</a></h3>'
                            + chart_div({"v2": True, "src": f["ex_balance"]["raw"], "fmt": "btc", "log": True, "ranges": ["1Y", "3Y", "5Y", "ALL"], "range": "ALL", "group": "l3",
                                         "series": [{"k": "v", "n": T("交易所余额", "Exchange balance"), "c": "s3"}]}) + "</div>")
                content += exetf_block(S)
            if i == 3:
                content += l3_tail() if R.l3_ok(G.get("L3")) else ""
            if i == 4:
                obs = content
                content = l4_tab(G.get("L4"), as_of) + (f'<details class="raw l3d obsfold"><summary>{T("山寨轮动观察（不属于 L4 研究，不进判定）", "Altcoin rotation watch (outside the L4 study, not in the verdict)")}</summary>{obs}</details>' if obs.strip() else "")
            if False:
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
{leg_macro_card()}
<div class="hzrow"><span class="hz">{T("长期 · 周期", "Long term · cycle")}</span>{T("按月看：处在四年周期的哪一段、风险预算该松还是紧", "In months: where we are in the four-year cycle, and how loose or tight the risk budget should be")}</div>
{comp_block(comp, prev_comp, tlog, full=True)}
{leg_short_context()}
{cal_next_line(G.get("CAL"))}
{src_summary(st)}
<div id="tabs-anchor"></div><div class="tabwrap"><nav class="tabs" role="tablist" aria-label="{T("四层", "Four layers")}" data-tabs>{tabs}</nav></div>
<details class="legend-d"><summary>{T("标签说明", "What the tags mean")}</summary>{tag_legend()}</details>
{panels}
{deep}"""
    emit("macro/index.html", T(f"宏观四层仪表盘 · {BRAND}", f"Macro dashboard · {BRAND_EN}"), body, active="macro", chart=True,
         extra_head=leg_assets()[0], scripts=leg_assets()[1],
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
<h1>{esc(name)}</h1><p class="lede keep">{esc(T(ind["说明"], ind["说明EN"]))}</p>
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
    """全网手续费汇总：Top8（跨链排行的近 7 日手续费排序，颜色按实体固定）+ 其他。返回 (数据路径, 拆解表数据)。"""
    hist = matrix.get("历史") or {}
    ds = sorted(d for d in hist if hist[d])
    if len(ds) < 2:
        return None, None
    names = {p["slug"]: p["名称"] for p in matrix["协议"]}
    agg = {}
    for d in ds[-90:]:
        for s, v in hist[d].items():
            agg[s] = agg.get(s, 0) + (v or 0)
    top = lp_top8(matrix, hist)
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
        rows.append({"slug": s, "名称": names.get(s, s) if s != "_other" else T("其他", "Other"), "c": f"s{k + 1}" if s != "_other" else "s9",
                     "今": a, "昨": b, "变": a - b, "份额今": a / t1 * 100 if t1 else None, "份额昨": b / t0 * 100 if t0 else None})
    car = (matrix.get("沿用") or {})
    return path, {"cfg": cfg_series, "d1": d1, "d0": d0, "t1": t1, "t0": t0, "rows": rows, "起": ds[0], "天数": len(ds),
                  "沿用": {"d1": dict(car.get(d1, {})), "d0": dict(car.get(d0, {}))}, "名称": names}


# ---------------------------------------------------------------- 发射台：钱在哪（按链 / 按平台的份额，读矩阵日更数据；周期页和矩阵页同一套配色）
def _proto_chain(p):
    c30 = p.get("分链30日") or {}
    if c30:
        k = max(c30, key=c30.get)
    else:
        k = CHAIN_KEY.get((p.get("链") or ["other"])[0], "other")
    return k if k in MAIN_CHAINS else "other"


def money_where(matrix):
    hist = (matrix or {}).get("历史") or {}
    ds = sorted(d for d in hist if hist[d])
    if len(ds) < 40:
        return ""
    names = {p["slug"]: p["名称"] for p in matrix["协议"]}
    pch = {p["slug"]: _proto_chain(p) for p in matrix["协议"]}
    agg90 = {}
    for d in ds[-90:]:
        for s, v in hist[d].items():
            agg90[s] = agg90.get(s, 0) + (v or 0)
    top = lp_top8(matrix, hist)          # 和矩阵页汇总图、跨链排行同一个排序 → 同一套平台色
    pcol = {s: f"s{k + 1}" for k, s in enumerate(top)}

    def window(end_i):
        w = ds[max(0, end_i - 6):end_i + 1]
        by_p, by_c = {}, {}
        for d in w:
            for s, v in hist[d].items():
                v = v or 0
                key = s if s in pcol else "_other"
                by_p[key] = by_p.get(key, 0) + v
                c = pch.get(s, "other")
                by_c[c] = by_c.get(c, 0) + v
        return by_p, by_c, w
    n = len(ds) - 1
    p_now, c_now, w_now = window(n)
    p_old, c_old, _ = window(n - 30)
    tn, to = sum(p_now.values()) or 1, sum(p_old.values()) or 1

    def bar(now, old, keys, col, name):
        segs, leg = "", ""
        for k in keys:
            a = now.get(k, 0) / tn * 100
            b = old.get(k, 0) / to * 100
            d = a - b
            segs += f'<i style="width:{a:.2f}%;background:var(--{col(k)})" title="{esc(name(k))} {a:.1f}%"></i>'
            leg += (f'<span><i style="background:var(--{col(k)})"></i>{esc(name(k))} <b>{a:.1f}%</b>'
                    f'<em class="{"t-up" if d >= 0.05 else "t-dn" if d <= -0.05 else ""}">{d:+.1f}pp</em></span>')
        return f'<div class="chainbar">{segs}</div><div class="chainleg mw">{leg}</div>'
    ch_keys = [k for k in ["solana", "bsc", "robinhood", "base"] if c_now.get(k)] + ["other"]
    c_now2 = {k: c_now.get(k, 0) for k in ch_keys[:-1]}
    c_now2["other"] = tn - sum(c_now2.values())
    c_old2 = {k: c_old.get(k, 0) for k in ch_keys[:-1]}
    c_old2["other"] = to - sum(c_old2.values())
    chain_bar = bar(c_now2, c_old2, ch_keys, lambda k: "c-" + k, lambda k: chain_name(k) if k != "other" else T("其他", "Other"))
    plat_bar = bar(p_now, p_old, top + ["_other"], lambda k: pcol.get(k, "s9"), lambda k: names.get(k, k) if k != "_other" else T("其他", "Other"))
    # 近 90 天按链份额堆叠图
    cs = {k: {} for k in ch_keys}
    for d in ds[-90:]:
        row = {}
        for s, v in hist[d].items():
            c = pch.get(s, "other")
            c = c if c in ch_keys else "other"
            row[c] = row.get(c, 0) + (v or 0)
        for k in ch_keys:
            cs[k][d] = row.get(k, 0)
    src = write_data("launchpad/chain_share90.json", ds[-90:], cs)
    cfg = {"src": src, "fmt": "usd", "stack": True, "mode": "pct", "ranges": ["ALL"], "range": "ALL",
           "series": [{"k": k, "n": chain_name(k) if k != "other" else T("其他", "Other"), "c": "c-" + k} for k in ch_keys]}
    return (f'<section id="money"><h2>{T("钱在哪", "Where the money is")} <span class="sub">{T("近 7 日手续费份额 · 括号外是和 30 天前比变了几个百分点", "7-day fee share · change vs 30 days earlier in pp")}</span></h2>'
            f'<div class="card mwcard"><div class="stamp">{T("数据日", "Data date")} <b>{ds[-1]}</b> · {T("矩阵日更（DefiLlama Launchpad 逐日手续费）", "matrix daily data (DefiLlama Launchpad daily fees)")}</div>'
            f'<h4>{T("按链（手续费份额）", "By chain (fee share)")}</h4>{chain_bar}<h4>{T("按平台（手续费份额 · 前 8 名 + 其他）", "By platform (fee share · top 8 + other)")}</h4>{plat_bar}'
            f'<h4>{T("近 90 天按链手续费份额", "Chain fee share, last 90 days")}</h4>{chart_div(cfg)}'
            f'<p class="tnote">{T("份额只说明钱在各链、各平台之间怎么分；赛道整体冷暖看上面的仪表。多链协议按近 30 日手续费最多的那条链归类。", "Shares only show how money splits across chains and platforms; for the sector as a whole, read the dial above. Multi-chain protocols are assigned to their largest chain by 30-day fees.")}</p></div></section>')


def cycle_summary():
    """发射台活动温度（每日）：温度数值 · 档位 · 阶段 · 数据日期。首页标签、矩阵页共用。"""
    c = G.get("CYC_DATA")
    if not c:
        return None
    import 周期观察 as CO
    import 周期仪表盘 as CD
    r = CO.reading(c[0]["series"]["fees"]["points"])
    st = CD.state(r)
    return {"temp": r["position"], "band": CD.band(r["position"]), "stage": (st[1], st[2]), "date": r["date"]}


def cycle_hero():
    """矩阵页顶部：先看赛道温度，再看细节。"""
    c = G.get("CYC_DATA")
    if not c:
        return ""
    import 周期观察 as CO
    import 周期仪表盘 as CD
    more = f'<a class="cd-more" href="{U("/launchpad/cycle/")}">{T("全部历史大图、这一轮走到哪、各阶段一般持续多久 →", "Full-history chart, this wave and stage durations →")}</a>'
    return CD.hero(c[0], CO.reading, T, esc, more, TDAY(c[0]['cutoff']))


def cycle_tag():
    c = G.get("CYC_SUM")
    if not c or c["temp"] is None:
        return ""
    t = max(0, min(100, c["temp"]))
    return (f'<a class="cyctag" href="{U("/launchpad/cycle/")}">{T("发射台活动温度", "Launchpad activity temperature")} <b>{t:.1f}</b> {esc(T(*c["band"]))} · '
            f'{esc(T(*c["stage"]))}{T("（截至 ", " (as of ")}{c["date"][5:]}{T("）", ")")} →</a>')


NEW_DAYS = 30        # 首次出现在近 30 天内的算「新上榜」


def new_listings(matrix):
    """DefiLlama Launchpad 类目新上榜：首次出现在近 NEW_DAYS 天的协议，按首次出现日期倒序。"""
    if not matrix:
        return []
    cut = (dt.date.fromisoformat(matrix["日期"]) - dt.timedelta(days=NEW_DAYS)).isoformat()
    xs = [p for p in matrix["协议"] if (p.get("首次出现") or "基线") != "基线" and p["首次出现"] >= cut]
    return sorted(xs, key=lambda p: (p["首次出现"], p.get("7日") or 0), reverse=True)


def new_chip(p):
    return f'<span class="chip t-cool carry" title="{esc(T("DefiLlama Launchpad 类目首次出现：", "First seen in DefiLlama Launchpad: ") + str(p.get("首次出现")))}">{T("新", "new")} {esc(str(p.get("首次出现"))[5:])}</span>'


def new_listings_html(matrix):
    xs = new_listings(matrix)
    head = (f'<h2 id="newlp">{T("新上榜", "New listings")} <span class="sub">{T(f"DefiLlama Launchpad 类目近 {NEW_DAYS} 天新出现的平台；「起量」= 近 7 日手续费 ≥ $1,000 且是前 7 日的 2 倍以上", f"Platforms new to DefiLlama Launchpad in the last {NEW_DAYS} days; ramping = 7-day fees ≥ $1,000 and at least 2× the prior 7 days")}</span></h2>')
    if not xs:
        return head + f'<div class="card" style="padding:12px 16px"><p class="tnote" style="margin:0">{T(f"近 {NEW_DAYS} 天没有新平台进入 DefiLlama Launchpad 类目。DefiLlama 收录有滞后，更早的新台子看「链上新发射台」。", f"No new platform entered DefiLlama Launchpad in the last {NEW_DAYS} days. DefiLlama lags; see on-chain discovery for earlier signals.")}</p></div>'
    trs = ""
    for p in xs:
        d7, p7 = p.get("7日") or 0, p.get("上7日") or 0
        ramp = d7 >= 1000 and (p7 == 0 or d7 >= 2 * p7)
        g = (f"{(d7 / p7 - 1) * 100:+.0f}%" if p7 >= 100 else ("—" if not d7 else T("新起", "new")))   # 前 7 日 < $100 时百分比没意义
        rchip = f'<span class="chip t-up carry">{T("起量", "ramping")}</span>' if ramp else ""
        trs += (f'<tr><td class="l"><span class="pname"><a href="https://defillama.com/protocol/{esc(p["slug"])}" target="_blank" rel="noopener">{esc(p["名称"])}</a>'
                f'{rchip}</span></td>'
                f'<td class="l">{"".join(chain_badge(c) for c in (p.get("链") or [])[:3])}</td><td>{esc(p["首次出现"])}</td>'
                f'<td>{f_usd(p.get("当日"))}</td><td>{f_usd(d7)}</td><td>{g}</td><td>{f_usd(p.get("30日"))}</td><td>{f_usd(p.get("累计"))}</td></tr>')
    return (head + f'<div class="tw"><table><thead><tr><th class="l">{T("平台", "Platform")}</th><th class="l">{T("链", "Chain")}</th><th>{T("首次出现", "First seen")}</th>'
            f'<th>{T("当日手续费", "Fees (day)")}</th><th>{T("近 7 日手续费", "Fees (7d)")}</th><th>{T("较前 7 日", "vs prior 7d")}</th><th>{T("30 日手续费", "Fees (30d)")}</th><th>{T("累计手续费", "Fees (all-time)")}</th></tr></thead><tbody>{trs}</tbody></table></div>'
            + f'<p class="tnote">{T("首次出现 = 第一次在 DefiLlama Launchpad 类目里看到它的日子（2026-11-06 起每天记录；之前已在名单里的按「第一天有手续费」回推近 60 天）。", "First seen = the first day we saw it in DefiLlama Launchpad (logged daily since 2026-11-06; for platforms already listed, back-dated from their first day with fees within 60 days).")}</p>')


# ---------------------------------------------------------------- 发射台：链上自动发现的新发射台（拉链上新台.py → data/onchain/）
def oc_chain_list():
    """链上扫描覆盖的 EVM 链：data/onchain/ 里有几条列几条，按最近一天新币数从多到少。"""
    out = []
    d = os.path.join(DATA, "onchain")
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.endswith(".json") or f in ("solana.json", "线索.json", "ai_agent.json", "档案.json", "llama_meta.json", "平台资料.json"):
            continue
        db = load(os.path.join(d, f)) or {}
        days = db.get("逐日") or {}
        last = days[max(days)].get("新币", 0) if days else -1
        out.append((f[:-5], db.get("链") or f[:-5], last))
    return [(k, nm) for k, nm, _ in sorted(out, key=lambda x: -x[2])]
OC_NEW_DAYS = 14          # 首次出现在近 14 天内的工厂算「新出现」
OC_MIN_7D = 30            # 进候选名单的门槛：近 7 天新币 ≥ 30 个


def oc_labels():
    lab = load(os.path.join(ROOT, "config", "launchpad_factories.json")) or {}
    return lab


def oc_summary(key, lab):
    """一条链的工厂汇总：近 7 天 / 前 7 天新币数、发币人数（下限）、首次出现、标签、样本。"""
    db = load(os.path.join(DATA, "onchain", f"{key}.json"))
    if not db:
        return None
    days = db.get("逐日") or {}
    ds = sorted(days)
    if not ds:
        return {"db": db, "rows": [], "end": None, "days": 0}
    end = ds[-1]
    e = dt.date.fromisoformat(end)
    w7 = [(e - dt.timedelta(days=i)).isoformat() for i in range(7)]
    p7 = [(e - dt.timedelta(days=i)).isoformat() for i in range(7, 14)]
    agg = {}
    for d in ds:
        for a, v in days[d]["工厂"].items():
            x = agg.setdefault(a, {"7日": 0, "前7日": 0, "人7日": 0, "昨日": 0, "样本": [], "活跃天": 0})
            if d in w7:
                x["7日"] += v[0]; x["人7日"] += v[1]; x["活跃天"] += 1
                x["样本"] = (v[2] + x["样本"])[:3] if d == end else (x["样本"] or v[2])[:3]
            elif d in p7:
                x["前7日"] += v[0]
            if d == end:
                x["昨日"] = v[0]
    first = db.get("首次出现") or {}
    known = dict(lab.get("*") or {}, **(lab.get(key) or {}))
    ids = (load(os.path.join(DATA, "onchain", "线索.json")) or {}).get("身份") or {}
    rows = []
    for a, x in agg.items():
        tag = known.get(a) or {}
        if tag.get("类型") in ("基础设施", "忽略"):
            continue
        fs = first.get(a, "基线")
        new = fs != "基线" and fs >= (e - dt.timedelta(days=OC_NEW_DAYS - 1)).isoformat()
        cov = len([d for d in p7 if d in days]) == 7
        ramp = x["7日"] >= 50 and cov and x["7日"] >= 2 * max(x["前7日"], 1)
        idt = ids.get(f"{key}:{a}") or {}
        nm_ = tag.get("名称") or idt.get("合约名") or (f'{idt["交易所"]}（交易所标签）' if idt.get("交易所") else None)
        rows.append(dict(addr=a, name=nm_, first=fs, new=new, ramp=ramp, cov=cov,
                         gh=idt.get("GitHub") or [], dom=idt.get("重复域名") or [], **x))
    rows.sort(key=lambda r: -r["7日"])
    return {"db": db, "rows": rows, "end": end, "days": len(ds)}


def _oc_chips(r):
    out = ""
    if r["new"]:
        out += f'<span class="chip t-cool carry">{T("新", "new")} {esc(r["first"][5:])}</span>'
    if r["ramp"]:
        out += f'<span class="chip t-up carry">{T("起量", "ramping")}</span>'
    return out


def _oc_addr(exp, a, kind="address"):
    return f'<a href="{esc(exp)}/{kind}/{esc(a)}" target="_blank" rel="noopener"><code>{esc(a[:6])}…{esc(a[-4:])}</code></a>'


def _oc_first(fs):
    return T("基线", "baseline") if fs == "基线" else esc(fs)


def onchain_html():
    lab = oc_labels()
    chains = oc_chain_list()
    sums = {k: oc_summary(k, lab) for k, _ in chains}
    if not any(sums.values()):
        return ""
    unnamed = T("未命名合约", "unnamed contract")
    cand, blocks = [], ""
    for key, nm in chains:
        sm = sums[key]
        if not sm:
            continue
        db = sm["db"]
        exp = db.get("浏览器") or ""
        st = db.get("状态") or ""
        for r in sm["rows"]:
            if (r["new"] or r["ramp"]) and r["7日"] >= OC_MIN_7D and r["addr"] not in r["样本"]:   # 工厂地址本身出现在样本币里 = 代币自己在铸，不算发射台
                cand.append((nm, exp, r))
        if not sm["rows"]:
            note = st if LANG["v"] == "zh" else ("Pending: needs the Alchemy key (GitHub secret ALCHEMY_KEY)" if st.startswith("待接入") else st)
            blocks += f'<div class="card ocb" style="padding:12px 16px"><b>{esc(nm)}</b> <span class="sub">{esc(note)}</span></div>'
            continue
        last = (db.get("逐日") or {}).get(sm["end"]) or {}
        trs = ""
        for r in sm["rows"][:10]:
            prev = f'{r["前7日"]:,}' if r["cov"] else "—"
            extra = "".join(f' <a href="{esc(g["链接"])}" target="_blank" rel="noopener">GitHub ↗</a>' for g in r["gh"][:1]) + \
                    "".join(f' <span class="sub">{esc(d)}</span>' for d in r["dom"][:2])
            trs += (f'<tr><td class="l">{esc(r["name"]) if r["name"] else unnamed}{_oc_chips(r)}<br><small>{_oc_addr(exp, r["addr"])}{extra}</small></td>'
                    f'<td>{r["昨日"]:,}</td><td>{r["7日"]:,}</td><td>{prev}</td><td>≥{r["人7日"]:,}</td><td>{_oc_first(r["first"])}</td></tr>')
        meta = T(f"{sm['end']} · 新币 {last.get('新币', 0):,} · 个人直接部署 {last.get('直接部署', 0):,} · 已积累 {sm['days']} 天 · 节点 {last.get('节点', '—')}",
                 f"{sm['end']} · new tokens {last.get('新币', 0):,} · direct deploys {last.get('直接部署', 0):,} · {sm['days']} days so far · node {last.get('节点', '—')}")
        if st and st != "ok":
            meta += " · " + esc(st[:80])
        blocks += (f'<details class="card fold ocb"{" open" if key == "robinhood" else ""}><summary><b>{esc(nm)}</b> <span class="sub">{meta}</span></summary>'
                   f'<div class="tw"><table><thead><tr><th class="l">{T("发币工厂（前 10）", "Token factory (top 10)")}</th><th>{T("昨日新币", "Yesterday")}</th>'
                   f'<th>{T("近 7 日", "7d")}</th><th>{T("前 7 日", "Prior 7d")}</th><th>{T("发币人（近 7 日）", "Creators (7d)")}</th><th>{T("首次出现", "First seen")}</th></tr></thead>'
                   f'<tbody>{trs}</tbody></table></div></details>')
    if cand:
        cand.sort(key=lambda c: -c[2]["7日"])
        ctr = ""
        for nm, exp, r in cand:
            samples = " ".join(_oc_addr(exp, t, "token") for t in r["样本"])
            ctr += (f'<tr><td class="l">{esc(r["name"]) if r["name"] else unnamed}{_oc_chips(r)}<br><small>{_oc_addr(exp, r["addr"])}</small></td>'
                    f'<td class="l">{esc(nm)}</td><td>{r["7日"]:,}</td><td>≥{r["人7日"]:,}</td><td>{_oc_first(r["first"])}</td><td class="l">{samples}</td></tr>')
        top = (f'<div class="tw"><table><thead><tr><th class="l">{T("候选工厂", "Candidate factory")}</th><th class="l">{T("链", "Chain")}</th><th>{T("近 7 日新币", "New tokens 7d")}</th>'
               f'<th>{T("发币人", "Creators")}</th><th>{T("首次出现", "First seen")}</th><th class="l">{T("样本币", "Sample tokens")}</th></tr></thead><tbody>{ctr}</tbody></table></div>')
    else:
        top = (f'<div class="card" style="padding:12px 16px"><p class="tnote" style="margin:0">'
               f'{T("目前没有符合条件的新工厂（近 14 天首次出现或正在起量，且近 7 天新币 ≥ 30 个）。数据还在积累中。", "No factory meets the bar yet (first seen in the last 14 days or ramping, with ≥ 30 new tokens in 7 days). Data is still accumulating.")}</p></div>')
    head = (f'<h2 id="oclp">{T("链上新发射台 · 自动发现", "New launchpads on-chain · auto-detected")} '
            f'<span class="sub">{T("不等 DefiLlama 收录：每天扫前一个 UTC 日的新币，按发币合约归到「工厂」", "Without waiting for DefiLlama: each day we scan the previous UTC day for new tokens and group them by the contract that created them")}</span></h2>')
    note = T("新币 = 一笔交易里一次铸出整数供应量（1,000 枚的整数倍）的代币；工厂 = 发币交易调用的合约；个人直接部署合约发的币单独计数、不算工厂。"
             "发币人是抽查交易里不同发币地址的个数，是下限。「新」= 近 14 天首次出现；「起量」= 近 7 天新币 ≥ 50 且是前 7 天的 2 倍以上。"
             "账户抽象入口、多重调用等通用合约已排除；工厂名字来自已验证合约名或人工补录，没有的显示「未命名合约」。只说明链上在发什么，不是推荐。",
             "New token = minted in a round supply (a multiple of 1,000) in one transaction; factory = the contract the creating transaction called; tokens deployed directly by individuals are counted apart. "
             "Creators = distinct creating addresses among sampled transactions (a lower bound). New = first seen in the last 14 days; ramping = ≥ 50 new tokens in 7 days and at least 2× the prior 7 days. "
             "Generic contracts (account-abstraction entry points, multicall) are excluded; names come from verified contracts or manual labels, otherwise “unnamed contract”. Describes what is being launched; not a recommendation.")
    return head + top + blocks + f'<p class="tnote">{note}</p>' + solana_html() + clues_html()


def solana_html():
    """Solana：公共发币设施（Meteora DBC、Raydium LaunchLab）上的前端，按合作方 / 平台配置拆分；同名的合并。"""
    db = load(os.path.join(DATA, "onchain", "solana.json"))
    if not db or not db.get("逐日"):
        return ""
    end = max(db["逐日"])
    first = db.get("首次出现") or {}
    lab = (oc_labels().get("solana") or {})
    cut = (dt.date.fromisoformat(end) - dt.timedelta(days=OC_NEW_DAYS - 1)).isoformat()
    rows = {}
    for dex, blk in db["逐日"][end].items():
        for gid, g in blk["前端"].items():
            nm = (lab.get(gid) or {}).get("名称") or g.get("名称")
            k = (dex, nm) if nm else (dex, gid)
            r = rows.setdefault(k, {"dex": dex, "名称": nm, "id": gid, "官网": g.get("官网"), "池": 0, "成交额": 0, "后缀": g.get("后缀"),
                                    "首次": first.get(f"{dex}:{gid}", "基线"), "样本": []})
            r["池"] += g["池"]
            r["成交额"] += g["成交额"]
            r["样本"] = (r["样本"] + g.get("样本", []))[:3]
            f = first.get(f"{dex}:{gid}", "基线")
            if "基线" in (f, r["首次"]):
                r["首次"] = "基线"
            else:
                r["首次"] = min(f, r["首次"])
    xs = sorted(rows.values(), key=lambda r: -r["成交额"])[:20]
    dexn = {"meteora-dbc": "Meteora DBC", "raydium-launchlab": "Raydium LaunchLab"}
    trs = ""
    for r in xs:
        new = r["首次"] != "基线" and r["首次"] >= cut
        nm = esc(r["名称"]) if r["名称"] else T("未命名前端", "unnamed front end")
        if r["官网"]:
            nm = f'<a href="{esc(r["官网"])}" target="_blank" rel="noopener">{nm}</a>'
        chips = f'<span class="chip t-cool carry">{T("新", "new")} {esc(r["首次"][5:])}</span>' if new else ""
        hint = T(f"币地址后缀 {r['后缀']}", f"mint suffix {r['后缀']}") if r.get("后缀") else ""
        samples = " ".join(f'<a href="https://dexscreener.com/solana/{esc(t)}" target="_blank" rel="noopener"><code>{esc(t[:5])}…</code></a>' for t in r["样本"])
        trs += (f'<tr><td class="l">{nm}{chips}<br><small><a href="https://solscan.io/account/{esc(r["id"])}" target="_blank" rel="noopener"><code>{esc(r["id"][:6])}…</code></a> {esc(hint)}</small></td>'
                f'<td class="l">{dexn.get(r["dex"], r["dex"])}</td><td>{r["池"]}</td><td>{f_usd(r["成交额"])}</td><td>{_oc_first(r["首次"])}</td><td class="l">{samples}</td></tr>')
    n = sum(len(b["前端"]) for b in db["逐日"][end].values())
    return (f'<details class="card fold ocb" open><summary><b>Solana</b> <span class="sub">{end} · '
            + T(f"公共发币设施上的前端 {n} 个（样本：各设施近 24 小时最活跃的 200 个池子）", f"{n} front ends on shared launch infrastructure (sample: the 200 most active pools per venue in 24h)")
            + f'</span></summary><div class="tw"><table><thead><tr><th class="l">{T("前端（合作方 / 平台配置）", "Front end (partner / platform config)")}</th><th class="l">{T("设施", "Venue")}</th>'
            f'<th>{T("样本池", "Pools")}</th><th>{T("24h 成交额", "24h volume")}</th><th>{T("首次出现", "First seen")}</th><th class="l">{T("样本币", "Samples")}</th></tr></thead><tbody>{trs}</tbody></table></div>'
            f'<p class="tnote" style="margin:8px 14px">{T("Solana 的新发射台多半是在 Meteora DBC、Raydium LaunchLab 这类公共设施上套前端，链上调用的是同一个程序，区别在各自的配置：DBC 按配置里的合作方（手续费接收地址）合并，LaunchLab 按平台配置（里面存着平台名字和官网）。GeckoTerminal 已单独列出的前端（Bags.fm、letsbonk.fun 等）不在这张表里，看下面的「新收录入口」。", "New Solana launchpads are mostly front ends on shared venues like Meteora DBC and Raydium LaunchLab: same program on-chain, different configs. DBC is grouped by the config partner (fee receiver), LaunchLab by platform config (which stores the platform name and site). Front ends GeckoTerminal already lists separately (Bags.fm, letsbonk.fun, …) are not here; see new entries below.")}</p></details>')


def clues_html():
    c = load(os.path.join(DATA, "onchain", "线索.json")) or {}
    out = ""
    dirs = c.get("目录") or {}
    netn = {"solana": "Solana", "bsc": "BSC", "base": "Base", "robinhood": "Robinhood Chain", "arc": "Arc"}
    new = [(net, k, v) for net, d in dirs.items() for k, v in d.items() if v.get("首次出现") not in (None, "基线")]
    new.sort(key=lambda x: x[2]["首次出现"], reverse=True)
    base_n = sum(len(d) for d in dirs.values())
    if dirs:
        li = "".join(f'<li><b>{esc(v["名称"])}</b> <span class="sub">{esc(netn.get(net, net))} · {esc(v["首次出现"])}</span> '
                     f'<a href="https://www.geckoterminal.com/{esc(net)}/{esc(k)}/pools" target="_blank" rel="noopener">GeckoTerminal ↗</a></li>' for net, k, v in new[:20])
        out += (f'<h3>{T("GeckoTerminal 新收录的发射台 / 交易入口", "New launchpad / DEX entries on GeckoTerminal")}</h3>'
                + (f'<div class="card" style="padding:10px 16px"><ul class="plain">{li}</ul></div>' if li else
                   f'<p class="tnote">{T(f"已建基线（五条链共 {base_n} 个条目），之后每天新冒出来的会列在这里。", f"Baseline recorded ({base_n} entries across five chains); new ones will be listed here.")}</p>'))
    hits = sorted((c.get("自称发射台") or {}).values(), key=lambda x: x.get("日期", ""), reverse=True)[:12]
    if hits:
        li = "".join(f'<li><a href="{esc(h.get("页面") or "#")}" target="_blank" rel="noopener"><code>{esc((h.get("代币") or "")[:8])}…</code></a> '
                     f'<span class="sub">{esc(h.get("链") or "")} · {esc(h.get("日期") or "")}</span><br><small>{esc(h.get("简介") or "")}</small></li>' for h in hits)
        out += (f'<h3>{T("DEX Screener · 自称提供发币服务的项目", "DEX Screener · projects describing themselves as launchpads")}</h3>'
                f'<div class="card" style="padding:10px 16px"><ul class="plain">{li}</ul></div>'
                f'<p class="tnote">{T("从 DEX Screener 最新代币资料里按关键词（launchpad、token launcher、bonding curve、fair launch、发射台）筛出来的，只是自我介绍，没核实，大部分是噪音；有链上实际发币记录的才会出现在上面的工厂表里。", "Keyword matches (launchpad, token launcher, bonding curve, fair launch) in DEX Screener’s latest token profiles; self-descriptions, unverified and mostly noise. Only those with real on-chain launches show up in the factory tables above.")}</p>')
    return out


def discovery_stats():
    """入口卡片和二级页面共用：四条 EVM 链 + Solana 的汇总数字。"""
    lab = oc_labels()
    out = {"chains": [], "factories": 0, "cand": [], "sol": 0, "sol_top": None, "end": None, "dirs_new": 0}
    for key, nm in oc_chain_list():
        sm = oc_summary(key, lab)
        if not sm or not sm["end"]:
            continue
        last = (sm["db"].get("逐日") or {}).get(sm["end"]) or {}
        out["chains"].append((key, nm, last.get("新币", 0)))
        out["end"] = max(out["end"] or "", sm["end"])
        act = [r for r in sm["rows"] if r["7日"] >= OC_MIN_7D]
        out["factories"] += len(act)
        out["cand"] += [(nm, r) for r in act if r["new"] or r["ramp"]]
    sdb = load(os.path.join(DATA, "onchain", "solana.json")) or {}
    if sdb.get("逐日"):
        e = max(sdb["逐日"])
        fr = [(g, dex) for dex, b in sdb["逐日"][e].items() for g in b["前端"].values()]
        out["sol"] = len(fr)
        byname = {}
        for g, _ in fr:                                  # 同一个平台开多个配置：按名字合并后再比
            if g.get("名称"):
                x = byname.setdefault(g["名称"], {"名称": g["名称"], "成交额": 0})
                x["成交额"] += g["成交额"]
        out["sol_top"] = max(byname.values(), key=lambda g: g["成交额"]) if byname else None
    c = load(os.path.join(DATA, "onchain", "线索.json")) or {}
    out["dirs_new"] = sum(1 for d in (c.get("目录") or {}).values() for v in d.values() if v.get("首次出现") not in (None, "基线"))
    out["cand"].sort(key=lambda x: -x[1]["7日"])
    return out


def discovery_card():
    st = discovery_stats()
    if not st["chains"]:
        return ""
    tot = sum(n for _, _, n in st["chains"]) or 1
    tile = lambda k, v, sub, cls="": (f'<div class="dc-t{cls}"><small>{k}</small><b>{v}</b><span>{sub}</span></div>')
    nch = len(st["chains"])
    tiles = (tile(T("昨日链上新币", "New tokens yesterday"), f"{tot:,}", T(f"{nch} 条 EVM 链 · {st['end']}", f"{nch} EVM chains · {st['end']}"))
             + tile(T("在发币的工厂", "Active factories"), f"{st['factories']:,}", T("近 7 天新币 ≥ 30 个", "≥ 30 new tokens in 7d"))
             + tile(T("候选", "Candidates"), f"{len(st['cand']):,}", T("新出现或起量", "new or ramping"), " hot" if st["cand"] else "")
             + tile(T("Solana 前端", "Solana front ends"), f"{st['sol']:,}", T("Meteora DBC · LaunchLab", "Meteora DBC · LaunchLab")))
    cs = sorted(st["chains"], key=lambda x: -x[2])
    head, rest = cs[:5], cs[5:]
    if rest:
        head = head + [("other", T(f"其他 {len(rest)} 条链", f"{len(rest)} other chains"), sum(n for _, _, n in rest))]
    col = lambda k: k if k in MAIN_CHAINS else "other"
    bar = "".join(f'<i style="width:{n / tot * 100:.2f}%;background:var(--c-{col(k)})" title="{esc(nm)} {n:,}"></i>' for k, nm, n in head)
    leg = "".join(f'<span><i style="background:var(--c-{col(k)})"></i>{esc(nm)} <b>{n:,}</b></span>' for k, nm, n in head)
    if st["cand"]:
        picks = [(nm, r["name"] or T("未命名合约", "unnamed contract"), T(f"近 7 日 {r['7日']:,} 个新币", f"{r['7日']:,} new tokens in 7d")) for nm, r in st["cand"][:3]]
        pick_h = T("最值得看", "Worth a look")
    else:
        picks = []
        if st["sol_top"]:
            g = st["sol_top"]
            picks.append(("Solana", g["名称"], T(f"24h 成交 {f_usd(g['成交额'])}", f"24h volume {f_usd(g['成交额'])}")))
        pick_h = T("目前还没有候选 · 成交最高的前端", "No candidates yet · busiest front end")
    pk = "".join(f'<li><span class="badge b-other">{esc(c)}</span> <b>{esc(n)}</b> <small>{esc(d)}</small></li>' for c, n, d in picks)
    note = T("数据只积累了几天，开头几天出现的都算「已有」，之后新冒出来的才进候选。", "Only a few days of data so far: everything seen in the first days counts as existing; only later arrivals become candidates.") if not st["cand"] else ""
    ai = ai_agent_html(compact=True)
    ai_line = ""
    if ai:
        strong, f30 = ai
        top3 = "、".join(r["名称"] for r in sorted(strong, key=lambda r: -(r.get("30日") or 0))[:3]) if LANG["v"] == "zh" else \
            ", ".join(r["名称"] for r in sorted(strong, key=lambda r: -(r.get("30日") or 0))[:3])
        ai_line = (f'<div class="dc-ai"><span class="chip t-up">AI Agent</span> '
                   + T(f"AI Agent 叙事发射台 <b>{len(strong)}</b> 个，近 30 天手续费 <b>{f_usd(f30)}</b>（{esc(top3)}…）",
                       f"<b>{len(strong)}</b> AI-agent launchpads, 30-day fees <b>{f_usd(f30)}</b> ({esc(top3)}…)") + '</div>')
    return (f'<a class="card dcard" href="{U("/launchpad/discovery/")}"><div class="dc-h"><div><div class="eyebrow">{T("新发射台监控 · 链上自动发现", "New launchpad monitor · on-chain discovery")}</div>'
            f'<h3>{T(f"不等 DefiLlama 收录：每天扫 {nch} 条 EVM 链的新币 + Solana 发射台前端", f"Before DefiLlama lists them: daily scans of new tokens on {nch} EVM chains, plus Solana launch front ends")}</h3></div>'
            f'<span class="btn dc-go">{T("进入监控 →", "Open monitor →")}</span></div>'
            f'<div class="dc-g">{tiles}</div>{ai_line}<div class="chainbar">{bar}</div><div class="chainleg">{leg}</div>'
            + (f'<div class="dc-p"><small>{pick_h}</small><ul>{pk}</ul></div>' if pk else "")
            + (f'<p class="tnote" style="margin:6px 0 0">{note}</p>' if note else "") + '</a>')


AI_NAME = re.compile(r"agent|\bai\b|^ai|ai$", re.I)
SCAN_KEY = {"hyperliquid": "hyperevm", "avax": "avalanche", "era": "zksync"}      # DefiLlama 分链键 → 本站扫描链名
NON_EVM = {"ton", "tron", "aptos", "sui", "near", "hedera", "injective", "starknet", "cardano", "algorand", "stellar", "bitcoin", "ripple", "cosmos"}
COVER_MIN, PAID_MIN = 0.0001, 0.005     # 0.01%：免费节点能扫就接；0.5%：只能付费扫的才报给大叔决定


def ai_agent_html(compact=False):
    """AI Agent 叙事的发射台：DefiLlama 规则识别 + 人工名单；再加链上扫出来、名字带 Agent / AI 的工厂和前端。"""
    d = load(os.path.join(DATA, "onchain", "ai_agent.json")) or {}
    rows = d.get("平台") or []
    if not rows:
        return ""
    end = d.get("日期") or ""
    cut = (dt.date.fromisoformat(end) - dt.timedelta(days=29)).isoformat() if end else ""
    strong = [r for r in rows if r["档"] == "强相关"]
    if compact:
        f30 = sum(r.get("30日") or 0 for r in strong)
        return strong, f30
    trs = ""
    for r in rows:
        nm = esc(r["名称"] or r["slug"])
        if r.get("官网"):
            nm = f'<a href="{esc(r["官网"])}" target="_blank" rel="noopener">{nm}</a>'
        tier = f'<span class="chip {"t-up" if r["档"] == "强相关" else "t-neutral"} carry">{T(r["档"], "strong" if r["档"] == "强相关" else "to confirm")}</span>'
        new = (f'<span class="chip t-cool carry">{T("新", "new")} {esc(r["首次出现"][5:])}</span>'
               if r.get("首次出现") not in (None, "基线") and r["首次出现"] >= cut else "")
        chains = "".join(chain_badge(c) for c in (r.get("链") or [])[:3])
        trs += (f'<tr><td class="l">{nm}{tier}{new}<br><small>{esc(r.get("介绍") or "")[:120]}</small></td><td class="l">{chains}</td>'
                f'<td class="l"><small>{esc(r.get("类目") or "")}</small></td><td>{f_usd(r.get("当日"))}</td><td>{f_usd(r.get("7日"))}</td><td>{f_usd(r.get("30日"))}</td></tr>')
    # 链上扫出来、名字带 Agent / AI 的工厂和前端（没有手续费数据，列新币数）
    oc = []
    lab = oc_labels()
    for key, nm in oc_chain_list():
        sm = oc_summary(key, lab)
        for r in (sm or {}).get("rows", []):
            if r.get("name") and AI_NAME.search(r["name"]):
                oc.append((nm, r["name"], T(f"近 7 日新币 {r['7日']:,}", f"{r['7日']:,} new tokens in 7d")))
    sdb = load(os.path.join(DATA, "onchain", "solana.json")) or {}
    if sdb.get("逐日"):
        for dex, b in sdb["逐日"][max(sdb["逐日"])].items():
            for g in b["前端"].values():
                if g.get("名称") and AI_NAME.search(g["名称"]):
                    oc.append(("Solana", g["名称"], T(f"24h 成交 {f_usd(g['成交额'])}", f"24h volume {f_usd(g['成交额'])}")))
    ocl = "".join(f'<li><span class="badge b-other">{esc(c)}</span> <b>{esc(n)}</b> <small>{esc(x)}</small></li>' for c, n, x in oc)
    return (f'<h2 id="aiagent">{T("AI Agent 发射台 · 重点关注", "AI Agent launchpads · focus")} <span class="sub">'
            + T(f"强相关 {len(strong)} 个 · 待确认 {len(rows) - len(strong)} 个 · 数据 DefiLlama {end}", f"{len(strong)} strong · {len(rows) - len(strong)} to confirm · DefiLlama {end}")
            + '</span></h2>'
            f'<div class="tw"><table><thead><tr><th class="l">{T("平台", "Platform")}</th><th class="l">{T("链", "Chain")}</th><th class="l">{T("DefiLlama 类目", "Category")}</th>'
            f'<th>{T("当日手续费", "Fees (day)")}</th><th>{T("7 日手续费", "Fees (7d)")}</th><th>{T("30 日手续费", "Fees (30d)")}</th></tr></thead><tbody>{trs}</tbody></table></div>'
            + (f'<div class="card" style="padding:10px 16px;margin-top:10px"><small class="sub">{T("链上扫描里名字带 Agent / AI 的工厂和前端", "On-chain factories and front ends named Agent / AI")}</small><ul class="plain">{ocl}</ul></div>' if ocl else "")
            + f'<p class="tnote">{T("怎么认：DefiLlama「Launchpad」类目里项目介绍明确写 AI agent、agentic、launch AI 的算「强相关」，只提到 AI（如 AI 审计、AI 生成内容）的算「待确认」；「AI Agents」类目里做发币 / 代币化 Agent 的（如 Virtuals）也列入。人工修正在 config/ai_agent_launchpads.json，可以加也可以排除。只说明叙事归类，不是推荐。", "How: in DefiLlama’s Launchpad category, descriptions that clearly say AI agent / agentic / launch AI are “strong”; those only mentioning AI (AI audits, AI-generated content) are “to confirm”; AI Agents-category projects that launch or tokenize agents (e.g. Virtuals) are included. Manual overrides in config/ai_agent_launchpads.json. Narrative tagging only; not a recommendation.")}</p>')


def coverage_html():
    """链覆盖：各链近 30 天发射台手续费份额（DefiLlama）× 本站是否在扫，按门槛标状态。"""
    m = load(os.path.join(DATA, "发射台矩阵.json")) or {}
    c30 = {}
    for p in m.get("协议") or []:
        for k, v in (p.get("分链30日") or {}).items():
            c30[k] = c30.get(k, 0) + (v or 0)
    tot = sum(c30.values()) or 1
    scanned = {k for k, _ in oc_chain_list()} | {"solana"}
    trs = ""
    for k, v in sorted(c30.items(), key=lambda kv: -kv[1]):
        sh = v / tot
        sk = SCAN_KEY.get(k, k)
        db = load(os.path.join(DATA, "onchain", f"{sk}.json")) or {}
        if sk in scanned and not db.get("逐日") and str(db.get("状态", "")).startswith("失败"):
            stt, cls = T("没扫通 · 免费节点太慢 / 限流；只能付费，份额没到 0.5% 不开", "not scanned · free nodes too slow / rate-limited; paid only, below the 0.5% bar"), "t-cool"
        elif k == "hyperliquid" and sk in scanned:
            stt, cls = T("部分 · 只扫 HyperEVM（HyperCore 上的发射台不在内）", "partial · HyperEVM only (HyperCore launchpads not covered)"), "t-cool"
        elif sk in scanned:
            stt, cls = T("已扫描", "scanned"), "t-up"
        elif sh >= COVER_MIN:
            if k in NON_EVM:
                stt, cls = T("达门槛 · 非 EVM，需单独开发", "above bar · non-EVM, needs its own build"), "t-warn"
            else:
                stt, cls = T("达门槛 · 待接入", "above bar · to add"), "t-warn"
        else:
            continue
        trs += f'<tr><td class="l">{esc(chain_name(k))}</td><td>{sh * 100:.2f}%</td><td>{f_usd(v)}</td><td class="l"><span class="chip {cls}">{stt}</span></td></tr>'
    return (f'<h2 id="coverage">{T("链覆盖", "Chain coverage")} <span class="sub">{T("哪些链在扫、哪些该接（按近 30 天发射台手续费份额）", "Which chains we scan and which to add (by 30-day launchpad fee share)")}</span></h2>'
            f'<div class="tw"><table><thead><tr><th class="l">{T("链", "Chain")}</th><th>{T("30 日手续费份额", "30d fee share")}</th><th>{T("30 日手续费", "30d fees")}</th><th class="l">{T("状态", "Status")}</th></tr></thead><tbody>{trs}</tbody></table></div>'
            f'<p class="tnote">{T("门槛：近 30 天发射台手续费占全网 ≥ 0.01% 的链，免费节点能扫就接入；只能付费才能扫的，份额 ≥ 0.5% 才提出来由大叔决定。已接入、份额低于门槛的免费链保留（不花钱，链刚起量时能更早看到）。TON、Tron、Aptos 等非 EVM 链发币机制不同，要单独开发。份额来自 DefiLlama Launchpad 类目分链数据。", "Bar: chains with ≥ 0.01% of 30-day launchpad fees are added when a free node can scan them; chains that need a paid node are raised for a decision only at ≥ 0.5%. Free chains already added stay even below the bar. Non-EVM chains (TON, Tron, Aptos…) need their own build. Shares from DefiLlama’s per-chain Launchpad data.")}</p>')


# ---------------------------------------------------------------- 发射台名录（logo + 名字 + 叙事；发射台名录.py 合并链上工厂与 Solana 前端）
CHAIN_LABEL = {"solana": "Solana", "bsc": "BSC", "base": "Base", "robinhood": "Robinhood", "arc": "Arc", "ethereum": "Ethereum", "ink": "Ink", "elysium": "Elysium",
               "optimism": "Optimism", "xlayer": "X Layer", "monad": "Monad", "arbitrum": "Arbitrum", "stable": "Stable", "plasma": "Plasma"}


def _lp_avatar(e, src):
    nm = e.get("名称") or "?"
    if src:
        return f'<img class="lpc-logo" src="{esc(src)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.replaceWith(Object.assign(document.createElement(\'span\'),{{className:\'lpc-logo lpc-av\',textContent:\'{esc(nm[:1].upper())}\'}}))">'
    hue = int(hashlib_md5(nm)[:2], 16) * 360 // 256
    return f'<span class="lpc-logo lpc-av" style="--h:{hue}">{esc(nm[:1].upper())}</span>'


def hashlib_md5(s):
    import hashlib
    return hashlib.md5((s or "").encode()).hexdigest()


def directory_html():
    try:
        import 发射台名录 as DIR
    except Exception as ex:
        print(f"  名录模块加载失败：{ex}")
        return ""
    ents = DIR.collect()
    if not ents:
        return ""
    lang = LANG["v"]
    sol_end = None
    sdb = load(os.path.join(DATA, "onchain", "solana.json")) or {}
    if sdb.get("逐日"):
        sol_end = max(sdb["逐日"])
    ref = dt.date.fromisoformat(sol_end) if sol_end else dt.date.today()
    cut = (ref - dt.timedelta(days=OC_NEW_DAYS - 1)).isoformat()
    cards = {"sol": [], "evm": []}
    chains_seen = []
    for e in ents:
        txt, src, tags, x = DIR.narrative(e, lang)
        logo = DIR.logo_src(e)
        nm = e["名称"] or "—"
        chs = [CHAIN_LABEL.get(c, c) for c in e["链"]]
        for c in e["链"]:
            if c not in chains_seen:
                chains_seen.append(c)
        fac = [T(f, "own contract") if f == DIR.OWN else f for f in e["设施"]]
        chips = ""
        if e["首次出现"] != "基线" and e["首次出现"] >= cut:
            chips += f'<span class="chip t-cool carry">{T("新", "new")} {esc(e["首次出现"][5:])}</span>'
        if e["近7日新币"] >= 50 and e["近7日新币"] >= 2 * max(e["前7日新币"], 1) and e["前7日新币"] > 0:
            chips += f'<span class="chip t-up carry">{T("起量", "ramping")}</span>'
        tg = "".join(f'<span class="lpc-tag{" ai" if t == "AI Agent" else ""}">{esc(t)}</span>' for t in tags)
        if txt:
            body = f'<p class="lpc-n">{esc(txt)}</p><p class="lpc-src">{T("出处：", "Source: ")}{esc(src)}</p>'
        else:
            body = f'<p class="lpc-n lpc-none">{T("还没查到介绍：官网资料每天自动抓，抓到后显示在这里。", "No description yet: the site is fetched daily and its blurb will show here.")}</p>'
        ai_ = DIR.ai_for(e)
        aic_ = (ai_ or {}).get("内容") or {}
        if aic_:
            sx = "zh" if lang == "zh" else "en"
            li = lambda xs: "".join(f"<li>{esc(x)}</li>" for x in xs[:5])  # noqa: E731
            parts = []
            if aic_.get(f"selling_points_{sx}"):
                parts.append(f'<b>{T("卖点", "Selling points")}</b><ul>{li(aic_[f"selling_points_{sx}"])}</ul>')
            if aic_.get(f"fee_split_{sx}"):
                parts.append(f'<b>{T("手续费怎么分", "Fee split")}</b><p>{esc(aic_[f"fee_split_{sx}"])}</p>')
            if aic_.get(f"token_{sx}"):
                parts.append(f'<b>{T("平台币", "Token")}</b><p>{esc(aic_[f"token_{sx}"])}</p>')
            if aic_.get(f"risks_{sx}"):
                parts.append(f'<b>{T("风险与疑点", "Risks")}</b><ul>{li(aic_[f"risks_{sx}"])}</ul>')
            srcs_ = [x for x in aic_.get("sources") or [] if str(x.get("url", "")).startswith("http")][:4]
            if srcs_:
                parts.append(f'<b>{T("来源", "Sources")}</b><p>' + " · ".join(
                    f'<a href="{esc(x["url"])}" target="_blank" rel="noopener nofollow">{esc((x.get("note") or DIR.domain(x["url"]))[:24])}</a>' for x in srcs_) + "</p>")
            if parts:
                body += (f'<details class="lpc-more"><summary>{T("卖点、分账、风险（Grok 整理，未核实）", "Selling points, fees, risks (Grok, unverified)")}</summary>'
                         + "".join(parts) + "</details>")
        mets = []
        if e["24h成交额"]:
            mets.append(f'{T("24h 成交额", "24h volume")} <b>{f_usd(e["24h成交额"])}</b>')
            mets.append(f'{T("样本池", "pools")} <b>{e["样本池"]:,}</b>')
        if e["近7日新币"]:
            mets.append(f'{T("近 7 日新币", "new tokens 7d")} <b>{e["近7日新币"]:,}</b>')
            if e["发币人"]:
                mets.append(f'{T("发币人", "creators")} <b>≥{e["发币人"]:,}</b>')
        mets.append(f'{T("首次出现", "first seen")} <b>{_oc_first(e["首次出现"])}</b>')
        links = []
        if e.get("官网"):
            links.append(f'<a href="{esc(e["官网"])}" target="_blank" rel="noopener">{T("官网", "Site")} ↗</a>')
        if x:
            links.append(f'<a href="https://x.com/{esc(x)}" target="_blank" rel="noopener">X ↗</a>')
        if e.get("defillama"):
            links.append(f'<a href="https://defillama.com/protocol/{esc(e["defillama"])}" target="_blank" rel="noopener">DefiLlama ↗</a>')
        for c, a, exp in e["地址"][:3]:
            u = f"https://solscan.io/account/{a}" if c == "solana" else f"{exp}/address/{a}"
            links.append(f'<a href="{esc(u)}" target="_blank" rel="noopener"><code>{esc(a[:6])}…</code></a>')
        q = " ".join([nm, e.get("官网") or "", " ".join(chs), " ".join(tags), " ".join(f for f in e["设施"]), e["key"]]).lower()
        card = (f'<div class="lpc card" data-ch="{esc(" ".join(e["链"]))}" data-q="{esc(q)}">'
                f'<div class="lpc-h">{_lp_avatar(e, logo)}<div class="lpc-t"><div class="lpc-name">{esc(nm)}{chips}</div>'
                f'<div class="lpc-sub">{esc(" · ".join(chs))} · {esc(" / ".join(fac))}</div></div></div>'
                f'{f"<div class=lpc-tags>{tg}</div>" if tg else ""}{body}'
                f'<div class="lpc-m">{" · ".join(mets)}</div><div class="lpc-l">{" ".join(links)}</div></div>')
        score = e["24h成交额"] if e["链"] == ["solana"] else e["近7日新币"]
        cards["sol" if e["链"] == ["solana"] else "evm"].append((-score, card))
    order = ["solana", "bsc", "robinhood", "base", "arc"] + [c for c in chains_seen if c not in ("solana", "bsc", "robinhood", "base", "arc")]
    fbtn = f'<button type="button" class="lpf on" data-f="">{T("全部", "All")}</button>' + "".join(
        f'<button type="button" class="lpf" data-f="{esc(c)}">{esc(CHAIN_LABEL.get(c, c))}</button>' for c in order if c in chains_seen)
    grid = lambda xs: '<div class="lpg">' + "".join(c for _, c in sorted(xs, key=lambda t: t[0])) + "</div>"
    js = ("<script>(function(){var r=document.getElementById('lpdir');if(!r)return;var q=r.querySelector('.lps'),f='';"
          "function go(){var s=(q.value||'').trim().toLowerCase(),n=0;r.querySelectorAll('.lpc').forEach(function(c){"
          "var ok=(!s||c.dataset.q.indexOf(s)>=0)&&(!f||(' '+c.dataset.ch+' ').indexOf(' '+f+' ')>=0);c.style.display=ok?'':'none';if(ok)n++;});"
          "r.querySelectorAll('.lpsec').forEach(function(x){x.style.display=x.querySelector('.lpc:not([style*=\"none\"])')?'':'none';});"
          "r.querySelector('.lpn').textContent=n;}"
          "q.addEventListener('input',go);r.querySelectorAll('.lpf').forEach(function(b){b.addEventListener('click',function(){"
          "r.querySelectorAll('.lpf').forEach(function(x){x.classList.remove('on')});b.classList.add('on');f=b.dataset.f;go();});});})();</script>")
    n = len(ents)
    head = (f'<h2 id="directory">{T("发射台名录", "Launchpad directory")} <span class="sub">'
            + T(f"链上扫到、认得出名字的发射台 {n} 个：是什么、什么叙事、多活跃", f"{n} launchpads seen on-chain that we can name: what they are, their angle, how active")
            + '</span></h2>')
    tools = (f'<div class="lpbar"><input class="lps" type="search" placeholder="{T("搜名字、官网、叙事（如 float、股票、AI）", "Search name, site or angle (e.g. float, stocks, AI)")}">'
             f'<div class="lpfs">{fbtn}</div><span class="sub">{T("显示", "showing")} <b class="lpn">{n}</b></span></div>')
    secs = ""
    if cards["sol"]:
        secs += (f'<div class="lpsec"><h3>{T("Solana 发射台前端", "Solana launch front ends")} <span class="sub">{T("按样本池 24h 成交额排", "by 24h volume in sampled pools")}</span></h3>'
                 + grid(cards["sol"]) + "</div>")
    if cards["evm"]:
        secs += (f'<div class="lpsec"><h3>{T("EVM 链发射台", "EVM launchpads")} <span class="sub">{T("按近 7 日新币数排", "by new tokens in 7 days")}</span></h3>'
                 + grid(cards["evm"]) + "</div>")
    note = T("名录 = 链上扫到的发币工厂（EVM 近 7 日新币 ≥ 30）和 Solana 公共设施上的前端（样本池 24h 成交额 ≥ $1 万）里，认得出名字的那些；同一个平台的多个合约 / 配置合并成一张卡。"
             "叙事优先用人工整理的一句话（写明出处），没有的用 DefiLlama 介绍或官网自述（英文原文，未核实）；标签按介绍里的关键词自动打。"
             "logo 每天从官网 / DefiLlama 自动抓。Solana 的指标是样本池的成交额，EVM 的是新币数，两边不能直接比。认不出名字的合约在下面「未识别的发币合约」里。只说明是什么，不是推荐。",
             "Directory = the token factories we scan on EVM chains (≥ 30 new tokens in 7 days) and Solana front ends on shared venues (≥ $10K 24h volume in sampled pools) that we can name; multiple contracts/configs of one platform are merged into one card. "
             "The angle uses a curated one-liner with its source where we have one, otherwise the DefiLlama description or the site’s own blurb (unverified); tags come from keywords. "
             "Logos are fetched daily from sites / DefiLlama. Solana is measured by sampled-pool volume and EVM by new tokens; the two aren’t comparable. Unnamed contracts are listed further down. Describes what they are; not a recommendation.")
    return f'<section id="lpdir">{head}{tools}{secs}<p class="tnote">{note}</p></section>{js}'


def build_launchpad_discovery():
    st = discovery_stats()
    ld, dst = os.path.join(DATA, "onchain", "logo"), os.path.join(SITE, "img", "lp")     # 发射台 logo（发射台名录.py 抓的）
    if os.path.isdir(ld) and LANG["v"] == "zh":
        shutil.rmtree(dst, ignore_errors=True)
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(ld):
            shutil.copyfile(os.path.join(ld, f), os.path.join(dst, f))
    body = (crumbs([(T("发射台矩阵", "Launchpads"), "/launchpad/"), (T("新发射台监控", "New launchpad monitor"), None)])
            + f'<div class="ph"><div><div class="eyebrow">Launchpad · {T("链上自动发现", "on-chain discovery")}</div><h1>{T("新发射台监控", "New launchpad monitor")}</h1>'
            + f'<p class="lede">{T("DefiLlama 收录有滞后。这里直接从链上看谁在批量发币：每天扫前一个 UTC 日的新币，按发币合约归到「工厂」；Solana 按公共发币设施上的配置拆出各个前端。只说明链上在发什么，不是推荐。", "DefiLlama lags. Here we read the chain directly: each day we scan the previous UTC day for new tokens and group them by the contract that created them; on Solana we split shared launch venues by config. Describes what is being launched; not a recommendation.")}</p></div>'
            + f'<div class="stamp">{T("数据截至", "Data as of")} <b>{esc(st["end"] or "—")}</b>{T("（UTC 完整日）", " (UTC)")}</div></div>'
            + directory_html() + ai_agent_html()
            + f'<h2 id="raw">{T("未识别的发币合约 · 扫描明细", "Unidentified factories · scan details")} <span class="sub">{T("认不出名字的工厂、各链前 10、Solana 全部前端、其他线索；点开看", "factories we can’t name yet, top 10 per chain, all Solana front ends, other leads — expand to view")}</span></h2>'
            + f'<details class="card fold"><summary><b>{T("展开扫描明细", "Show scan details")}</b></summary><div style="padding:0 14px 14px">' + onchain_html() + '</div></details>'
            + coverage_html())
    emit("launchpad/discovery/index.html", f'{T("新发射台监控", "New launchpad monitor")} · {T(BRAND, BRAND_EN)}', body, active="launchpad",
         desc=T("链上自动发现新发射台：Robinhood Chain、BSC、Base、Arc 每日新币按发币工厂统计，Solana 发射台前端拆分。", "On-chain discovery of new launchpads: daily new tokens by factory on Robinhood Chain, BSC, Base and Arc, plus Solana launch front ends."))


def lp_top8(matrix, hist):
    """汇总趋势图、当日变化拆解、「钱在哪」共用的前 8 名：和下面「跨链排行」默认视图一致，按近 7 日手续费（DefiLlama total7d）排序；
    只取逐日历史里有数的平台。颜色按这个排序给，三处同一套平台色。"""
    have = set().union(*[set(v) for v in hist.values()]) if hist else set()
    ps = sorted((p for p in matrix["协议"] if p["slug"] in have), key=lambda p: -(p.get("7日") or 0))
    return [p["slug"] for p in ps[:8]]


def carry_map(matrix, d=None):
    """{slug: 实际沿用的那天}：DefiLlama 在 d（默认矩阵日期）还没出数、矩阵用它最后一天的值顶上的平台。"""
    if not matrix:
        return {}
    return dict((matrix.get("沿用") or {}).get(d or matrix.get("日期"), {}))


def carry_chip(last):
    """「沿用 11-04」小标：数值是该平台最后一个有数的日子，不是当天。"""
    tip = T(f"DefiLlama 还没出这家当天的数，这里是它 {last} 的值；补出后自动换成真实值。规则见口径页「延迟平台」。",
            f"DefiLlama has not published this platform's day yet; this is its {last} value, replaced automatically once published. See Methodology › delayed platforms.")
    return f'<span class="chip t-warn carry" title="{esc(tip)}">{T("沿用", "carried")} {esc(str(last)[5:])}</span>'


def breakdown_html(bk):
    if not bk:
        return ""
    t1, t0 = bk["t1"], bk["t0"]
    dt_ = t1 - t0
    trs = ""
    for r in sorted(bk["rows"], key=lambda r: (r["c"] == "s9", -r["今"])):          # 「其他」固定放最后
        dsh = (r["份额今"] - r["份额昨"]) if r["份额今"] is not None and r["份额昨"] is not None else None
        cy = (bk.get("沿用") or {}).get("d1", {}).get(r.get("slug")) or (bk.get("沿用") or {}).get("d0", {}).get(r.get("slug"))
        trs += (f'<tr><td class="l"><span class="pname"><i style="width:10px;height:10px;border-radius:2px;background:var(--{r["c"]});display:inline-block"></i>{esc(r["名称"])}{carry_chip(cy) if cy else ""}</span></td>'
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
    cy1 = (bk.get("沿用") or {}).get("d1", {})
    if cy1:
        nm = dict(bk.get("名称") or {})
        lst = "、".join(nm.get(k, k) for k in cy1) if LANG["v"] == "zh" else ", ".join(nm.get(k, k) for k in cy1)
        s += T(f"（{lst} 当天 DefiLlama 还没出数，按它最后一天的值计入，份额变化可能失真。）",
               f" ({lst}: not yet published by DefiLlama for this day; its last value is used, so share changes may be off.)")
    return (f'<p class="tnote" style="font-size:13px;color:var(--ink2)">{esc(s)}</p>'
            f'<div class="tw"><table><thead><tr><th class="l">{T("平台", "Platform")}</th><th>{bk["d1"]}</th><th>{bk["d0"]}</th><th>{T("变化", "Change")}</th>'
            f'<th>{T("手续费份额", "Fee share")}</th><th>{T("份额变化", "Share Δ")}</th></tr></thead><tbody>{trs}'
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
    PSLUGS = platform_page_slugs(matrix)
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
    car = {p["slug"]: p.get("数据日") for p in matrix["协议"] if p.get("沿用")}
    NEWS = new_listings(matrix)
    car_amt = sum(p.get("当日") or 0 for p in matrix["协议"] if p["slug"] in car)
    car_note = (T(f"含 {len(car)} 家沿用前一日 · 占 {car_amt / tot_day * 100:.1f}%", f"incl. {len(car)} carried over · {car_amt / tot_day * 100:.1f}%")
                if car else "")
    lead_ch = main[0] if main else None
    kpis = [
        (T("全类目当日手续费", "All launchpads · day"), f_usd(tot_day), fmt_delta((tot_day / tot_prev - 1) if tot_prev else None) + " " + T("日环比", "DoD")
         + (f'<br><span class="carrynote">{car_note}</span>' if car_note else "")),
        (T("7 日 / 30 日合计", "7d / 30d"), f_usd(tot_7), f"{T('30 日', '30d')} {f_usd(tot_30)}"),
        (T("当日活跃协议", "Active protocols"), f"{active_n}", T(f"DefiLlama Launchpad 类目共 {len(matrix['协议'])} 个", f"{len(matrix['协议'])} in DefiLlama's category")),
        (T("当日第一", "#1 today"), esc(lead["名称"]), f'{f_usd(lead.get("当日"))} · {T("占", "")} {(lead.get("当日") or 0)/tot_day*100:.1f}%'
         + (" " + carry_chip(car[lead["slug"]]) if lead["slug"] in car else "")),
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
        if link:
            nm = f'<a href="{link}">{esc(p["名称"])}</a> <span class="deep">{T("深度", "deep")}</span>'
        elif p["slug"] in PSLUGS:
            nm = f'<a href="{U("/launchpad/platforms/" + p["slug"] + "/")}">{esc(p["名称"])}</a>'
        else:
            nm = f'<a href="https://defillama.com/protocol/{esc(p["slug"])}" target="_blank" rel="noopener" title="{esc(T("份额不到 0.1% 且还没有介绍，直接看 DefiLlama", "Under 0.1% share and no write-up yet: opens DefiLlama"))}">{esc(p["名称"])} ↗</a>'
        logo = f'<img src="{esc(p["logo"])}" alt="" loading="lazy" referrerpolicy="no-referrer">' if p.get("logo") else '<img alt="">'
        if p.get("沿用"):
            nm += carry_chip(p.get("数据日"))
        if p in NEWS:
            nm += new_chip(p)
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
                                   "note": T(f"DefiLlama Launchpad 类目 Top60 逐日手续费（{bk['起']} 起，{bk['天数']} 天），前 8 名和下面「跨链排行」一样按近 7 日手续费排序、颜色跟着平台走，其余并入「其他」。口径是手续费不是成交量：各平台费率不同，份额按手续费算。",
                                             f"Daily fees of DefiLlama's top-60 launchpads since {bk['起']} ({bk['天数']} days). Top 8 by 7-day fees, same order as the cross-chain ranking below, colors per platform, the rest folded into Other. Fees, not volume: fee rates differ by venue.")})
                      + f'</div><h3>{T("当日手续费变化拆解", "Day-over-day fee breakdown")} <span class="sub" style="font-weight:400;color:var(--muted)">{bk["d0"]} → {bk["d1"]}</span></h3>{breakdown_html(bk)}')
    first_arc = str(((arc.get("发射台") or [{}])[0]).get("slug", ""))
    body = f"""<div class="ph"><div><div class="eyebrow">Launchpad Matrix</div><h1>{T("发射台矩阵", "Launchpad matrix")}</h1>
<p class="lede">{T(f"DefiLlama Launchpad 类目全部 {len(matrix['协议'])} 个协议：先看全网汇总趋势（赛道水多没多、资金在哪些平台之间挪），再看跨链排行和每个平台的市场份额。口径统一用手续费（fees），日期是 UTC 完整日。",
                   f"All {len(matrix['协议'])} protocols in DefiLlama's Launchpad category: the sector-wide trend first (is money flowing in, and between which venues), then the cross-chain ranking with market share. Fees, UTC full days.")}</p></div>
<div class="stamp">{T("数据截至", "Data as of")} <b>{matrix["日期"]}</b>{T("（UTC 完整日）", " (UTC)")}<br>{T("生成", "Generated")} <b>{TT(matrix.get("生成时间UTC"))}</b></div></div>
{cycle_hero()}
<div class="grid g5" id="lpk">{kh}</div>
{discovery_card()}
{new_listings_html(matrix)}
{total_html}
<div class="card" style="padding:14px 16px;margin-top:22px"><div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;font-size:12.5px"><b>{T("生态份额 · 当日手续费按链拆分", "Chain share · today's fees by chain")}</b><span class="stamp">{T("多链协议按 DefiLlama 分链数据精确拆分", "Multi-chain protocols split by DefiLlama's per-chain data")}</span></div>
<div class="chainbar">{bar}</div><div class="chainleg">{leg}</div></div>
<h2 id="rank">{T("跨链排行 · 手续费市场份额", "Cross-chain ranking · fee market share")} <span class="sub">{T("按手续费（fees）排，不是成交量；份额条 = 手续费占当前筛选范围合计的百分比，颜色 = 主力所在链；链接会记住当前筛选，可直接分享", "Ranked by fees, not volume; share bar = % of the filtered fee total, color = main chain; the URL keeps your filters")}</span></h2>
<div class="glass fbar">
<div class="fg"><span class="fl">{T("生态", "Chain")}</span>{chain_pills}</div>
<div class="fg"><span class="fl">{T("周期", "Period")}</span><button class="pill" data-f="p" data-v="d1">{T("当日", "Day")}</button><button class="pill on" data-f="p" data-v="d7">{T("7 日", "7d")}</button><button class="pill" data-f="p" data-v="d30">{T("30 日", "30d")}</button></div>
<div class="fg"><span class="fl">{T("金额档", "Tier")}</span><button class="pill on" data-f="tier" data-v="all">{T("全部", "All")}</button><button class="pill" data-f="tier" data-v="big">{T("主力", "Major")} ≥$100K</button><button class="pill" data-f="tier" data-v="mid">{T("腰部", "Mid")} $10K–100K</button><button class="pill" data-f="tier" data-v="small">{T("黑马", "Small")} &lt;$10K</button></div>
<span class="fcount" id="fcount"></span><button class="btn" onclick="shareMatrix()">📸 {T("生成今日排行长图", "Share ranking image")}</button>
</div>
<div class="tw scroll"><table id="mx"><thead><tr><th class="l">#</th><th class="l">{T("协议", "Protocol")}</th><th class="l">{T("链", "Chain")}</th><th class="l">{T("手续费份额", "Fee share")}</th><th data-col="d1">{T("当日手续费", "Fees (day)")}</th><th>{T("日环比", "DoD")}</th>
<th data-col="d7">{T("7 日手续费", "Fees (7d)")}</th><th data-col="d30">{T("30 日手续费", "Fees (30d)")}</th><th>{T("30 日手续费走势", "30d fee trend")}</th></tr></thead><tbody>{rows}</tbody></table></div>
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
          .replace("%SHARE%", T("手续费份额", "Fee share")).replace("%DOD%", T("日环比", "DoD")).replace("%TITLE%", T("发射台矩阵", "Launchpad matrix"))
          .replace("%SRC%", T("数据：DefiLlama · 口径：手续费", "Data: DefiLlama · fees")))
    emit("launchpad/index.html", T(f"发射台矩阵 · 跨链 Launchpad 手续费排行 · {BRAND}", f"Launchpad matrix · cross-chain fees · {BRAND_EN}"), body,
         active="launchpad", share=True, chart=True, scripts=js,
         desc=T(f'{matrix["日期"]} 发射台全类目当日手续费 {f_usd(tot_day)}，第一 {lead["名称"]}。', f'{matrix["日期"]}: launchpad fees {f_usd(tot_day)}, #1 {lead["名称"]}.'))


# ---------------------------------------------------------------- 平台二级页面（份额 ≥ 0.1%）：数据 + 产品与基本面 + 官网入口 + 数据来源
METH_LABEL = {"Fees": ("手续费", "Fees"), "Revenue": ("协议收入", "Revenue"), "HoldersRevenue": ("给持币人（回购 / 分红）", "To holders (buyback / dividends)"),
              "ProtocolRevenue": ("留给协议 / 团队", "Kept by protocol / team"), "SupplySideRevenue": ("给创作者等供给方", "To creators / supply side")}


def _pdir():
    import 发射台名录 as DIR
    return DIR


def platform_page_slugs(matrix):
    try:
        DIR = _pdir()
        known = {p["slug"] for p in (matrix or {}).get("协议") or []}
        return (set(DIR.platform_slugs(matrix or {})) | set(DIR.platform_info())          # 只要进过 0.1% 就一直有二级页面
                | {k for k in DIR.ai_notes() if k in known})                               # 有 Grok 介绍的也有（大叔 11-14：既然有了就填上）
    except Exception as ex:
        print(f"  平台二级页面名单失败：{ex}")
        return set()


def platform_links_html(p, info):
    url = info.get("官网") or None
    x = info.get("X") or info.get("官网X")
    btn = []
    if url:
        btn.append(f'<a class="btn pri" href="{esc(url)}" target="_blank" rel="noopener">{T("访问官网 · 体验产品", "Visit the site · try the product")} ↗</a>')
    if x:
        btn.append(f'<a class="btn" href="https://x.com/{esc(x)}" target="_blank" rel="noopener">X @{esc(x)} ↗</a>')
    btn.append(f'<a class="btn" href="https://defillama.com/protocol/{esc(p["slug"])}" target="_blank" rel="noopener">{T("DefiLlama 数据源", "DefiLlama source")} ↗</a>')
    for g in (info.get("GitHub") or [])[:2]:
        btn.append(f'<a class="btn" href="https://github.com/{esc(g)}" target="_blank" rel="noopener">GitHub {esc(g)} ↗</a>')
    if info.get("gecko_id"):
        btn.append(f'<a class="btn" href="https://www.coingecko.com/coins/{esc(info["gecko_id"])}" target="_blank" rel="noopener">CoinGecko ↗</a>')
    return f'<div class="pbtns">{"".join(btn)}</div>'


def platform_profile_html(p):
    """产品与基本面：一句话 + 叙事标签 + 基本信息 + 收费分账口径 + 融资 / 安全事件 / 大事记 + 数据来源。"""
    slug = p["slug"]
    try:
        DIR = _pdir()
        info = DIR.platform_info().get(slug) or {}
        txt, src, tags, pid = DIR.platform_narrative(slug, p["名称"], info.get("官网"), LANG["v"])
        prof = DIR.profiles().get(pid or "", {}) if pid else {}
    except Exception as ex:
        print(f"  平台资料读取失败 {slug}：{ex}")
        info, txt, src, tags, prof = {}, "", "", [], {}
        DIR = None
    ai = ((load(os.path.join(DATA, "onchain", "平台AI介绍.json")) or {}).get(slug) or {})
    aic = ai.get("内容") or {}
    sfx = "zh" if LANG["v"] == "zh" else "en"
    if aic.get(f"one_liner_{sfx}") and not prof.get("叙事"):         # 没有人工一句话时，用 AI 的（中文站不再挂英文原文）
        txt = aic[f"one_liner_{sfx}"]
        src = (T(f"Grok（网页版）整理（{ai.get('日期')}），未人工核实，来源见下方「AI 研究摘要」", f"Compiled by Grok (web) ({ai.get('日期')}), not verified by us; sources in the AI summary below")
               if ai.get("方式") == "手动" else
               T(f"AI 根据 DefiLlama、官网与文档整理（{ai.get('日期')}），未人工核实", f"AI summary of DefiLlama, the site and docs ({ai.get('日期')}), not verified by us"))
    tg = "".join(f'<span class="lpc-tag{" ai" if t == "AI Agent" else ""}">{esc(t)}</span>' for t in tags)
    one = (f'<p class="pp-one">{esc(txt)}</p><p class="lpc-src">{T("出处：", "Source: ")}{esc(src)}</p>' if txt else
           f'<p class="pp-one lpc-none">{T("DefiLlama 和官网都没给介绍。", "Neither DefiLlama nor the site gives a description.")}</p>')
    na = T("—", "—")
    team = prof.get("团队") if LANG["v"] == "zh" else (prof.get("团队EN") or prof.get("团队"))
    rows = [
        (T("链", "Chains"), " ".join(chain_badge(c) for c in p.get("链") or []) or na),
        (T("代币", "Token"), esc(info["代币"]) + (f' · {T("市值", "mcap")} {f_usd(float(info["市值"]))}' if info.get("市值") else "") if info.get("代币") else T("DefiLlama 没记代币", "no token listed")),
        (T("上 DefiLlama", "Listed on DefiLlama"), esc(info.get("上线DefiLlama") or (p.get("首次出现") if p.get("首次出现") not in (None, "基线") else na))),
        (T("母协议", "Parent"), esc(info.get("母协议") or na)),
        (T("审计", "Audits"), (" ".join(f'<a href="{esc(a)}" target="_blank" rel="noopener">{T("报告", "report")} {i + 1} ↗</a>' for i, a in enumerate(info.get("审计链接") or []))
                              or (T("DefiLlama 记 0 份", "0 on DefiLlama") if str(info.get("审计数")) in ("0", "None", "") else esc(str(info.get("审计数")))))),
        (T("团队", "Team"), esc(team) if team else (T("见下方「AI 研究摘要 · 团队与背景」", "See “AI research summary · Team & backing” below") if aic.get(f"team_{sfx}") else
                                                   T("DefiLlama 不收录团队信息；看官网和 X 的自我介绍，本站还没核实", "DefiLlama has no team data; see the site and X — not verified by us"))),
    ]
    fund = info.get("融资") or []
    if fund:
        fr = "".join(f'<li>{esc(r.get("日期") or "")} · {esc(r.get("轮次") or "")}'
                     + (f' · ${r["金额百万"]:,.0f}M' if r.get("金额百万") else "")
                     + (f' · {T("领投", "lead")} {esc(", ".join(r["领投"]))}' if r.get("领投") else "")
                     + (f' · {T("参投", "with")} {esc(", ".join(r["其他"][:6]))}' if r.get("其他") else "") + "</li>" for r in fund)
        rows.append((T("融资", "Raises"), f'<ul class="plain">{fr}</ul>'))
    else:
        rows.append((T("融资", "Raises"), T("DefiLlama 没有融资记录", "none recorded on DefiLlama")))
    hk = info.get("安全事件") or []
    rows.append((T("安全事件", "Security incidents"), "".join(
        f'<div>{esc(h.get("日期") or "")} · {esc(h.get("类型") or "")}{" · " + esc(h["手法"]) if h.get("手法") else ""}{" · " + f_usd(h["金额"]) if h.get("金额") else ""}</div>' for h in hk)
        if hk else T("DefiLlama 没有记录", "none recorded on DefiLlama")))
    dl = "".join(f'<div class="pp-k">{k}</div><div class="pp-v">{v}</div>' for k, v in rows)
    meth = info.get("口径") or {}
    mt = "".join(f'<div class="pm-k">{T(*METH_LABEL[k])}</div><div class="pm-v">{esc(meth[k])}</div>' for k in METH_LABEL if meth.get(k))
    mblock = (f'<h3>{T("钱怎么收、怎么分", "How fees are charged and split")} <span class="sub">{T("DefiLlama 口径原文（英文）：最能看出产品机制", "DefiLlama methodology (original): the clearest view of the mechanics")}</span></h3>'
              f'<div class="card pm">{mt}</div>') if mt else ""
    aiblock = ""
    if aic:
        def _ul(xs):
            return "<ul class=\"plain\">" + "".join(f"<li>{esc(x)}</li>" for x in xs) + "</ul>" if xs else T("无", "none")
        arows = [(T("核心卖点", "Selling points"), _ul(aic.get(f"selling_points_{sfx}") or [])),
                 (T("和其他发射台的区别", "How it differs"), esc(aic.get(f"differentiation_{sfx}") or "")),
                 (T("手续费怎么分", "Fee split"), esc(aic.get(f"fee_split_{sfx}") or "")),
                 (T("平台币", "Token"), esc(aic.get(f"token_{sfx}") or "")),
                 (T("团队与背景", "Team & backing"), esc(aic.get(f"team_{sfx}") or "")),
                 (T("风险与疑点", "Risks & open questions"), _ul(aic.get(f"risks_{sfx}") or [])),
                 (T("资料里没有的", "Not in the sources"), _ul(aic.get(f"unknowns_{sfx}") or []))]
        KIND = {"official": T("官方", "official"), "x": "X", "web": T("网页", "web")}
        srcs_ = [x for x in (aic.get("sources") or []) if isinstance(x, dict) and str(x.get("url", "")).startswith("http")]
        if srcs_:
            arows.append((T("来源", "Sources"), "<ul class=\"plain\">" + "".join(
                f'<li><span class="lpc-tag">{esc(KIND.get(x.get("kind"), x.get("kind") or ""))}</span> <a href="{esc(x["url"])}" target="_blank" rel="noopener nofollow">{esc((x.get("note") or x["url"])[:80])}</a></li>'
                for x in srcs_[:12]) + "</ul>"))
        def _host(u):
            return re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
        read = "".join(f' <a href="{esc(u)}" target="_blank" rel="noopener">{esc(_host(u))}</a>' for u in (ai.get("官网已读") or [])[:3])
        manual = ai.get("方式") == "手动"
        aiblock = (f'<h3 id="ai">{T("AI 研究摘要", "AI research summary")}</h3><p class="tnote" style="margin-top:-4px">'
                   + (T(f"Grok（网页版）用官网、DefiLlama、X 和网页搜索整理，搜来的说法都附链接；查不到写「资料未提及」。整理于 {esc(ai.get('日期') or '')}，未人工核实，不是推荐。",
                        f"Compiled by Grok (web) from the site, DefiLlama, X and web search, with links for every claim; anything not found is marked. {esc(ai.get('日期') or '')}; not verified by us, not a recommendation.") if manual else '')
                   + ("" if manual else T(f"Grok 以本站收集的资料为底（DefiLlama 协议详情与口径、本站手续费数据、官网和文档正文{('，读了' + read) if read else ''}），团队和近况另用 X / 网页搜索补，搜来的都附链接；查不到写「资料未提及」。生成于 {esc(ai.get('日期') or '')}，未人工核实，不是推荐。",
                       f"Grok worked from the material we collected (DefiLlama details and methodology, our fee data, the site and docs{('; read' + read) if read else ''}), adding team and recent news from X / web search with links; anything not found is marked. Generated {esc(ai.get('日期') or '')}; not verified by us, not a recommendation."))
                   + '</p><div class="card pm">' + "".join(f'<div class="pm-k">{k}</div><div class="pm-v">{v}</div>' for k, v in arows if v) + "</div>")
    hm = info.get("大事记") or []
    hblock = (f'<h3>{T("大事记", "Milestones")} <span class="sub">DefiLlama</span></h3><ul class="plain">'
              + "".join(f'<li>{esc(a or "")} · {esc(b)}</li>' for a, b in hm) + "</ul>") if hm else ""
    srcs = [f'<a href="https://defillama.com/protocol/{esc(slug)}" target="_blank" rel="noopener">DefiLlama · {esc(p["名称"])}</a>']
    if info.get("口径代码"):
        srcs.append(f'<a href="{esc(info["口径代码"])}" target="_blank" rel="noopener">{T("DefiLlama 统计代码", "DefiLlama adapter code")}</a>')
    if info.get("官网"):
        srcs.append(f'<a href="{esc(info["官网"])}" target="_blank" rel="noopener">{T("官网", "official site")}</a>')
    note = T(f"数据来源：{' · '.join(srcs)}。手续费、协议收入、分账口径、融资、安全事件都是 DefiLlama 的数据，本站每天同步；产品介绍的出处见上方。资料更新于 {esc(info.get('日期') or '—')}。只说明是什么，不是推荐。",
             f"Sources: {' · '.join(srcs)}. Fees, revenue, methodology, raises and incidents are DefiLlama data synced daily; the description’s source is noted above. Profile updated {esc(info.get('日期') or '—')}. Describes what it is; not a recommendation.")
    return (f'<h2 id="profile">{T("产品与基本面", "Product & fundamentals")}</h2>'
            f'<div class="card pp">{f"<div class=lpc-tags>{tg}</div>" if tg else ""}{one}<div class="pp-grid">{dl}</div></div>'
            f'{aiblock}{mblock}{hblock}<p class="tnote">{note}</p>')


def build_platform_pages(matrix, deep_slugs):
    if not matrix:
        return
    slugs = platform_page_slugs(matrix) - set(deep_slugs)
    if not slugs:
        return
    P = matrix["协议"]
    hist = matrix.get("历史") or {}
    t30 = sum(p.get("30日") or 0 for p in P) or 1
    t7 = sum(p.get("7日") or 0 for p in P) or 1
    rank30 = {p["slug"]: i + 1 for i, p in enumerate(sorted(P, key=lambda p: -(p.get("30日") or 0)))}
    rank7 = {p["slug"]: i + 1 for i, p in enumerate(sorted(P, key=lambda p: -(p.get("7日") or 0)))}
    car = {p["slug"]: p.get("数据日") for p in P if p.get("沿用")}
    tpl = lambda k, v, s="": f'<div class="glass hero"><div class="k">{k}</div><div class="v" style="font-size:21px">{v}</div><div class="s">{s}</div></div>'  # noqa: E731
    for p in P:
        if p["slug"] not in slugs:
            continue
        slug = p["slug"]
        try:
            info = _pdir().platform_info().get(slug) or {}
        except Exception:
            info = {}
        vs = lambda a, b: fmt_delta((a / b - 1) if a and b else None)  # noqa: E731
        k = (tpl(T("当日手续费", "Fees (day)"), f_usd(p.get("当日")), fmt_delta(p.get("日环比"), pct_input=True) + " " + T("日环比", "DoD")
                 + (" " + carry_chip(car[slug]) if slug in car else ""))
             + tpl(T("近 7 日手续费", "Fees (7d)"), f_usd(p.get("7日")), vs(p.get("7日"), p.get("上7日")) + " " + T("较前 7 日", "vs prior 7d"))
             + tpl(T("近 30 日手续费", "Fees (30d)"), f_usd(p.get("30日")), vs(p.get("30日"), p.get("上30日")) + " " + T("较前 30 日", "vs prior 30d"))
             + tpl(T("手续费份额", "Fee share"), f'{(p.get("7日") or 0) / t7 * 100:.2f}%', T(f"近 7 日 · 第 {rank7[slug]} 名；30 日 {(p.get('30日') or 0) / t30 * 100:.2f}% · 第 {rank30[slug]} 名",
                                                                                            f"7d · #{rank7[slug]}; 30d {(p.get('30日') or 0) / t30 * 100:.2f}% · #{rank30[slug]}"))
             + tpl(T("累计手续费", "Cumulative fees"), f_usd(p.get("累计")), T("首次出现 ", "first seen ") + esc(T("基线", "baseline") if p.get("首次出现") in (None, "基线") else p["首次出现"])))
        ser = {d: hist[d][slug] for d in sorted(hist) if hist[d].get(slug) is not None}
        chart = ""
        if ser:
            dates = sorted(ser)
            src_ = write_data(f'launchpad/m-{slug}.json', dates, {"f": ser})
            chart = (f'<div class="card" style="padding:14px 18px;margin-top:14px"><h3 style="margin-top:0">{T("每日手续费", "Daily fees")}</h3>'
                     + chart_div({"src": src_, "fmt": "usd", "ranges": ["1M", "3M", "6M", "ALL"], "range": "3M" if len(dates) > 90 else "ALL",
                                  "series": [{"k": "f", "n": T("手续费", "Fees"), "c": "s1", "area": True}]}) + "</div>")
        hv = (hist.get(p.get("数据日") or "") or {}).get(slug)
        if hv and p.get("当日") and abs(hv / p["当日"] - 1) > 0.05 and slug not in car:
            gap = T(f"注意：DefiLlama 两个接口对 {p['数据日']} 给的数不一样——汇总接口（上面「当日」）{f_usd(p['当日'])}，逐日序列（下图）{f_usd(hv)}；近 7 日合计和逐日序列一致。等 DefiLlama 自己对齐，本站不替它选。",
                    f"Note: DefiLlama’s two endpoints disagree for {p['数据日']}: the summary (“day” above) says {f_usd(p['当日'])}, the daily series (chart) {f_usd(hv)}; the 7-day total matches the series. We show both rather than pick one.")
            chart += f'<p class="tnote">{gap}</p>'
        c30 = p.get("分链30日") or {}
        cb = ""
        if len(c30) > 1:
            tt = sum(c30.values()) or 1
            cb = (f'<h3>{T("分链（近 30 日手续费）", "By chain (30d fees)")}</h3><div class="tw"><table><tbody>'
                  + "".join(f'<tr><td class="l">{esc(chain_name(c))}</td><td>{f_usd(v)}</td><td>{v / tt * 100:.1f}%</td></tr>' for c, v in sorted(c30.items(), key=lambda kv: -kv[1]))
                  + "</tbody></table></div>")
        logo = f'<img class="ph-logo" src="{esc(p["logo"])}" alt="" referrerpolicy="no-referrer">' if p.get("logo") else ""
        body = f"""{crumbs([(T("发射台矩阵", "Launchpads"), "/launchpad/"), (T("跨链排行", "Ranking"), "/launchpad/#rank"), (p["名称"], None)])}
<div class="ph"><div><div class="eyebrow">Launchpad · {T("平台", "platform")}</div><h1>{logo}{esc(p["名称"])} {"".join(chain_badge(c) for c in (p.get("链") or [])[:4])}</h1></div>
<div class="stamp">{T("数据截至", "Data as of")} <b>{esc(p.get("数据日") or matrix.get("日期") or "")}</b>{T("（UTC 完整日）", " (UTC)")}</div></div>
{platform_links_html(p, info)}
<div class="grid g5">{k}</div>
{chart}{cb}
{platform_profile_html(p)}"""
        emit(f'launchpad/platforms/{slug}/index.html', f'{p["名称"]} · {T("发射台", "Launchpad")} · {T(BRAND, BRAND_EN)}', body,
             active="launchpad", chart=True, desc=T(f'{p["名称"]}：近 7 日手续费 {f_usd(p.get("7日"))}，产品介绍、收费分账、融资与官网入口。',
                                                   f'{p["名称"]}: 7-day fees {f_usd(p.get("7日"))}; product, fee split, raises and official links.'))


def _deep_profile(x, matrix):
    """深度追踪页也挂上官网入口 + 产品与基本面（和普通平台页同一套）。"""
    p = next((q for q in (matrix or {}).get("协议") or [] if q["slug"] == x["slug"]), None)
    if not p:
        return ""
    try:
        info = _pdir().platform_info().get(p["slug"]) or {}
    except Exception:
        info = {}
    return platform_profile_html(p)


def _deep_links(x, matrix):
    p = next((q for q in (matrix or {}).get("协议") or [] if q["slug"] == x["slug"]), None)
    if not p:
        return ""
    try:
        info = _pdir().platform_info().get(p["slug"]) or {}
    except Exception:
        info = {}
    return platform_links_html(p, info)


def build_launchpad_platforms(sd, matrix=None):
    build_platform_pages(matrix, [x["slug"] for x in (sd or {}).get("平台", [])])
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
{_deep_links(x, matrix)}
<div class="grid g5">{k}</div>
<div class="card" style="padding:14px 18px;margin-top:14px"><h3 style="margin-top:0">{T("手续费 / 协议收入", "Fees / revenue")}</h3>{chart}</div>
{vb}{_deep_profile(x, matrix)}"""
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
    ("巨鲸埋伏", "Whale positioning", "BTC 层面的筹码分布、短期持有者成本和交易所流量已在宏观第三层上线；山寨币层面需要逐币持仓分布，筹备中。",
     "BTC supply distribution, STH cost and exchange flows are live in macro L3; altcoin holder distribution is in preparation."),
]


# ---------------------------------------------------------------- 事件日历（只读 data/cal/cal_latest.json；规则和检验在 cal/）
CAL_GRADE = {"已验证·波动": ("g-v", "Validated · volatility"), "已证伪": ("g-x", "Falsified"), "未检验": ("g-o", "Untested")}


def cal_grade(g):
    cls, en = CAL_GRADE.get(g, ("", g))
    return f'<span class="grade {cls}{" dashed" if g == "未检验" else ""}">{esc(T(g, en))}</span>'


def cal_next_line(cal):
    """宏观页综合研判下面那一行：下一个 BTC 事件。"""
    b = (cal or {}).get("btc") or {}
    ev = next((e for e in b.get("events") or [] if e.get("emphasis") and (e.get("days_until") or 0) >= 0), None)
    if not ev:
        return ""
    zh = b.get("next_zh") or ""
    d = ev.get("days_until")
    en = f'Next: {ev.get("title_en")}, {"today" if d == 0 else f"in {d} day" + ("s" if d != 1 else "")} ({ev.get("time_utc")} UTC)'
    return f'<p class="calnext"><a href="{U("/calendar/")}">{esc(T(zh, en))} →</a></p>'


def cal_home_card(cal):
    xs = (cal or {}).get("next7") or []
    if not xs:
        return ""
    rows = ""
    for x in xs[:6]:
        btc = x.get("tab") == "btc"
        badge = cal_grade(x.get("grade")) if btc else f'<span class="grade g-o">{T("行业动向", "Industry")}</span>'
        if btc and x.get("time_utc"):
            d_, h_ = TLOC(x["time_utc"])
            when = f'{d_} {h_}{T(" 新加坡", " ET")}'
        else:
            when = esc((x.get("date") or "")[5:])
        rows += (f'<li><a href="{U("/calendar/")}#{"btc" if btc else "web3"}"><span class="d">{when}</span>'
                 f'<b>{esc(T(x.get("title_zh") or x.get("title") or "", x.get("title_en") or x.get("title") or ""))}</b>{badge}</a></li>')
    return (f'<h2>{T("未来 7 天", "Next 7 days")} <a class="sub" href="{U("/calendar/")}">{T("事件日历 →", "Calendar →")}</a></h2>'
            f'<div class="card calhome"><ul>{rows}</ul></div>')


# ---------------------------------------------------------------- 核心选币观测台（数据 core/core_daily.py → data/core/；页面由 core/web/core.js 渲染）
CORE_L2_PASS = ("BEAR_ZONE", "RECOVERY")      # 闸门 1：熊底区或熊末→牛初才过（大叔原型的建仓闸门）


def core_gates():
    """三道闸门里读本站数据的两道：L2 周期状态、L1 净流动性闸门（13 周 ≤ −2.72% 且美元走强，同 宏观规则 的判定）。"""
    st_ = ((G.get("L2") or {}).get("state") or {})
    code = st_.get("code")
    l2 = {"code": code, "ok": code in CORE_L2_PASS, "since": st_.get("since"),
          "name_zh": (R.L2_STATES.get(code) or ("",))[0] if code else None, "name_en": (R.L2_STATES.get(code) or ("", ""))[1] if code else None} if code else None
    j = G.get("JBY") or {}
    nl, us = j.get("netliq13"), j.get("usd13")
    liq = None
    if nl and nl.get("值") is not None:
        liq = {"netliq": nl["值"], "usd": us.get("值") if us else None, "asof": nl.get("截至"),
               "tripped": nl["值"] <= -2.72 and us is not None and (us.get("值") or 0) > 0}
    return {"l2": l2, "liq": liq}


def write_core_data():
    """data/core → site/data/core（构建时注入闸门）。"""
    src = os.path.join(DATA, "core")
    d = load(os.path.join(src, "core_latest.json"))
    G["CORE"] = d
    if not d:
        return
    out = os.path.join(SITE, "data", "core")
    os.makedirs(os.path.join(out, "series"), exist_ok=True)
    d = dict(d, gates=core_gates())
    with open(os.path.join(out, "core_latest.json"), "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, separators=(",", ":"))
    for fn in ("core_history.json", "rotation.json", "score_backtest.json"):
        if os.path.exists(os.path.join(src, fn)):
            shutil.copyfile(os.path.join(src, fn), os.path.join(out, fn))
    for fn in os.listdir(os.path.join(src, "series")) if os.path.isdir(os.path.join(src, "series")) else []:
        shutil.copyfile(os.path.join(src, "series", fn), os.path.join(out, "series", fn))


def core_home_card():
    d = G.get("CORE")
    if not d:
        return ""
    cs = d.get("coins") or {}
    pool = [c for c in cs.values() if c.get("track") == "pool"]
    wr = [c for c in pool if ((c.get("fees") or {}).get("revenue") or {}).get("d7v30") is not None]
    up = sum(1 for c in wr if c["fees"]["revenue"]["d7v30"] > 0)
    m = d.get("market") or {}
    b30 = (m.get("bench") or {}).get("r30") or {}
    vb = m.get("vol") or {}
    fp = lambda x: "—" if x is None else f"{x:+.1f}%"
    lead = sorted((c for c in wr if c["fees"]["revenue"]["d7v30"] > 0), key=lambda c: -c["fees"]["revenue"]["d7v30"])
    tops = " ".join(f'<a href="{U("/core/")}#coin/{esc(c["sym"])}">{esc(c["sym"])} <b>{c["fees"]["revenue"]["d7v30"]:+.0f}%</b></a>' for c in lead) or T("无", "none")
    ent = "、".join(x["sym"] for x in vb.get("entrants") or []) or T("无", "none")
    return (f'<h2>{T("核心选币观测", "Core picks monitor")} <span class="sub">{T("基本面 · 资金面 · 技术面，只做条件检查", "Fundamentals · flows · technicals; condition checks only")}</span>'
            f' <a class="sub" href="{U("/core/")}">{T("进观测台 →", "Open →")}</a></h2>'
            f'<div class="card core-home"><div class="row"><span>{T("观测池收入 7 日均 > 30 日均", "Pool revenue 7d > 30d")} <b>{up} / {len(wr)}</b></span>'
            f'<span>{T("观测池 30 日中位", "Pool 30d median")} <b>{fp(b30.get("pool_med"))}</b> · {T("全市场篮子", "market basket")} <b>{fp(b30.get("ew_med"))}</b></span>'
            f'<span>{T("成交额新进榜", "Volume entrants")} <b>{esc(ent)}</b></span></div>'
            f'<div class="row" style="margin-top:6px">{T("收入 7 日均在上升的：", "Revenue 7d avg rising: ")}{tops}</div>'
            f'<div class="row" style="margin-top:6px;font-size:12px;color:var(--muted)">{T("数据日", "Data day")} {esc(d.get("last_complete_day") or "")} · {T("只摆读数，不打分（评分回测没通过）", "Readings only, no score (the score failed its backtest)")}</div></div>')


def core_md(src):
    """评分研究立项书（core/research/评分研究立项.md）→ HTML：标题、段落、- / 1. 列表（缩进 = 子项）、表格、**粗体**、`代码`。"""
    out, lst, tbl, para, hn = [], [], [], [], [0]

    def flush():
        if para:
            out.append(f"<p>{md_inline(' '.join(para))}</p>"); para.clear()
        if lst:
            # lst: [(缩进, 是否编号, 文本)]；缩进 ≥ 2 的挂到上一个顶层项下面
            top = []
            for ind, num, txt in lst:
                if ind >= 2 and top:
                    top[-1][2].append(txt)
                else:
                    top.append((num, txt, []))
            tag = "ol" if top[0][0] else "ul"
            h = "".join(f"<li>{md_inline(t)}" + (f'<ul class="plain">' + "".join(f"<li>{md_inline(x)}</li>" for x in sub) + "</ul>" if sub else "") + "</li>" for _, t, sub in top)
            out.append(f'<{tag} class="plain">{h}</{tag}>'); lst.clear()
        if tbl:
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in tbl if not re.match(r"^\|?\s*-{3}", r.strip())]
            out.append('<div class="scroll"><table class="rt"><thead><tr>' + "".join(f"<th>{md_inline(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:]) + "</tbody></table></div>")
            tbl.clear()
    for ln in src.split("\n"):
        t = ln.strip()
        if not t:
            flush(); continue
        if t.startswith("|"):
            if para or lst:
                flush()
            tbl.append(t); continue
        m = re.match(r"^(#{1,4})\s+(.*)", t)
        if m:
            flush(); hn[0] += 1
            out.append(f'<h{len(m.group(1)) + 1} id="h{hn[0]}">{md_inline(m.group(2))}</h{len(m.group(1)) + 1}>'); continue
        if t.startswith(">"):
            flush(); out.append(f'<div class="note">{md_inline(t[1:].strip())}</div>'); continue
        m = re.match(r"^(\s*)(?:-|(\d+)\.)\s+(.*)", ln)
        if m:
            if para or tbl:
                fl = lst[:]; lst.clear(); flush(); lst.extend(fl)
            lst.append((len(m.group(1)), bool(m.group(2)), m.group(3))); continue
        if lst and ln.startswith("  "):
            ind, tag, txt = lst[-1]; lst[-1] = (ind, tag, txt + " " + t); continue
        if lst or tbl:
            flush()
        para.append(t)
    flush()
    return "\n".join(out)


def build_core():
    cr = crumbs([(T("核心选币", "Core Picks"), None)])
    # 缓存版本号用生成时间（同一数据日重跑也会换新地址）；11-14 用数据日当版本号，CDN 把旧 JSON 又缓存了一小时，篮子来源字段读不到
    v = re.sub(r"[^0-9]", "", (G.get("CORE") or {}).get("generated") or "")
    body = f"""{cr}
<div class="ph"><div><div class="eyebrow">Core Picks Monitor</div><h1>{T("核心选币观测台", "Core picks monitor")}</h1></div></div>
<p class="lede">{T("回购 / 收入型协议和叙事标的的基本面（手续费、收入、持有人收入、业务量）、资金面（成交额、现货 + 永续排名）、技术面（均线、RSI、回撤）。每天自动更新；评分和规则判定全部是【假设】，只做条件检查和风险提示，不是买卖建议。",
                   "Fundamentals (fees, revenue, holder revenue, activity), flows (volume, spot + perp rank) and technicals (MAs, RSI, drawdown) for buyback / revenue protocols and narrative names. Updated daily; scores and rule checks are hypotheses for condition checks and risk alerts, not trade advice.")}</p>
<div class="core" id="core" data-src="/data/core/core_latest.json?v={v}" data-series="/data/core/series/" data-hist="/data/core/core_history.json" data-rot="/data/core/rotation.json" data-bt="/data/core/score_backtest.json"></div>
<template id="core-research">{core_md(open(os.path.join(ROOT, "core", "research", "评分研究立项.md"), encoding="utf-8").read())}</template>
<template id="core-rules">{core_md(open(os.path.join(ROOT, "core", "research", "选币规则_v1.md"), encoding="utf-8").read())}</template>
<noscript><p class="muted">{T("这一页需要开启 JavaScript。", "This page needs JavaScript.")}</p></noscript>"""
    emit("core/index.html", T(f"核心选币观测台 · {BRAND}", f"Core Picks Monitor · {BRAND_EN}"), body, active="core",
         extra_head=f'<link rel="stylesheet" href="{ASSET_URL["core.css"]}">', scripts=f'<script src="{ASSET_URL["core.js"]}" defer></script>',
         desc=T("核心标的的基本面、资金面、技术面每日观测：协议收入趋势、估值、解锁、成交额榜、均线与回撤，加建仓条件检查和风险提示。",
                "Daily fundamentals, flows and technicals for core assets: revenue trend, valuation, unlocks, volume board, MAs and drawdowns, with an entry checklist and risk alerts."))


# ---------------------------------------------------------------- Alpha 雷达（alpha/：雷达读 data/alpha/alpha_latest.json；方法论 / 案例库 / 进度读 alpha/research/*.md）
ALPHA_TABS = [("", "机会看板", "Board", "可投资机会 · 预警观察", "Investable · watchlist"),
              ("radar/", "雷达", "Radar", "数据从哪来", "Where leads come from"),
              ("cases/", "案例库", "Cases", "历史对照", "Historical reference")]
ALPHA_FW = [("framework/", "框架", "Framework"), ("eval/", "评估器", "Evaluator"), ("progress/", "检验与进度", "Validation & progress"), ("method/", "方法论原文", "Original text")]


def write_alpha_data():
    src = os.path.join(DATA, "alpha")
    G["ALPHA"] = load(os.path.join(src, "alpha_latest.json"))
    G["ALPHA_HIST"] = load(os.path.join(src, "alpha_history.json"), []) or []
    if not G["ALPHA"]:
        return
    G["OPPS"] = load(os.path.join(src, "opps.json"))
    out = os.path.join(SITE, "data", "alpha")
    os.makedirs(out, exist_ok=True)
    for fn in ("alpha_latest.json", "alpha_history.json", "alpha_leads.json", "opps.json", "opp_series.json", "research_queue.json", "case_metrics.json", "case_series.json"):
        if os.path.exists(os.path.join(src, fn)):
            shutil.copyfile(os.path.join(src, fn), os.path.join(out, fn))
    for fn in ("framework.json", "cases.json"):   # 框架与案例定义在 alpha/（单一来源），网页按同一份读
        shutil.copyfile(os.path.join(ROOT, "alpha", fn), os.path.join(out, fn))
    if os.path.isdir(os.path.join(src, "rev")):   # 机会卡逐日收入（走势图组件格式）
        shutil.copytree(os.path.join(src, "rev"), os.path.join(out, "rev"), dirs_exist_ok=True)
    cs = load(os.path.join(src, "case_series.json"), {}) or {}   # 案例：价格 ÷ P0（周线）、30 天手续费（周线）→ 走势图组件格式
    os.makedirs(os.path.join(out, "case"), exist_ok=True)
    for cid, v in cs.items():
        for sym, pts in (v.get("tokens") or {}).items():
            json.dump({"d": [a for a, _ in pts], "s": {"p": [b for _, b in pts]}}, open(os.path.join(out, "case", f"{cid}_{sym}.json"), "w"), separators=(",", ":"))
        if v.get("fees30"):
            json.dump({"d": [a for a, _ in v["fees30"]], "s": {"f": [b for _, b in v["fees30"]]}}, open(os.path.join(out, "case", f"{cid}_fees.json"), "w"), separators=(",", ":"))


ALPHA_ST = {"研究观察": ("t-up", "Watching"), "待核验": ("t-warn", "To verify"), "优先研究": ("t-up", "Priority"), "拒绝": ("t-dn", "Rejected")}


def alpha_checks():
    """外部补证（alpha/review/*_checks.json）：key → 最新一条。"""
    if "ALPHA_CHK" not in G:
        out, rd = {}, os.path.join(ROOT, "alpha", "review")
        for fn in sorted(os.listdir(rd)) if os.path.isdir(rd) else []:
            if fn.endswith("_checks.json"):
                for c in load(os.path.join(rd, fn), []) or []:
                    out[c["key"]] = c
        G["ALPHA_CHK"] = out
    return G["ALPHA_CHK"]


def alpha_status_chip(key):
    c = alpha_checks().get(key)
    if not c:
        return '<span class="tnote" style="margin:0">—</span>'
    cls, en = ALPHA_ST.get(c["verdict"], ("", c["verdict"]))
    return f'<a class="chip {cls}" href="{U("/alpha/opp/")}#{esc(key.split(":", 1)[1].replace("parent#", ""))}">{T(c["verdict"], en)}</a>'


def alpha_pool():
    chk = alpha_checks()
    if not chk:
        return f'<div class="note">{T("候选池还没有补证记录。", "No reviewed candidates yet.")}</div>'
    cur = {r["key"]: r for r in (G.get("ALPHA") or {}).get("tokenless") or []}
    U_ = lambda v: T("未知", "unknown") if v in (None, "", "U") else esc(str(v))
    def card(c):
        r = cur.get(c["key"])
        rv = f'{a_usd(r["rev30"])}' if r else T("已不在榜", "off the board")
        src = c.get("token_stance_src")
        stance = U_(c.get("token_stance")) + (f' · <a href="{esc(src)}" target="_blank" rel="noopener">{T("来源", "source")}</a>' if src and src != "U" else "")
        miss = "".join(f"<li>{esc(m)}</li>" for m in c.get("missing") or [])
        ev = " · ".join(f'<a href="{esc(e["url"])}" target="_blank" rel="noopener">{i}</a>' for i, e in enumerate(c.get("evidence") or [], 1) if str(e.get("url", "")).startswith("http"))
        row = lambda k, v: f'<div style="margin-top:6px"><span class="tnote" style="margin:0">{k}</span> {v}</div>'
        return (f'<div class="card" id="{esc(c["key"])}" style="padding:14px 18px;margin:0 0 12px;font-size:13.5px;line-height:1.7">'
                f'<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><b style="font-size:15px">{esc(c["name"])}</b>{alpha_status_chip(c["key"])}'
                f'<span class="tnote" style="margin:0">{T("30 天收入", "30d revenue")} {rv}</span></div>'
                + row(T("发币表态", "Token stance"), stance)
                + row(T("收入归谁", "Who gets revenue"), U_(c.get("revenue_who")))
                + row(T("刷量 / 补贴", "Wash / subsidy"), U_(c.get("wash_or_subsidy")))
                + row(T("普通人的角色", "Role for users"), U_(c.get("user_role")))
                + row(T("最强反方", "Strongest counter"), U_(c.get("counter")))
                + row(T("为什么是这一档", "Why this status"), U_(c.get("verdict_reason")))
                + (f'<details style="margin-top:6px"><summary class="tnote" style="margin:0;cursor:pointer">{T("还没查清的", "Still unknown")}（{len(c.get("missing") or [])}）</summary><ul style="margin:6px 0 0;padding-left:20px">{miss}</ul></details>' if miss else "")
                + f'<div class="tnote">{T("核对", "Checked")} {esc((c.get("checked_utc") or "")[:10])} · {T("证据", "Evidence")} {ev}</div></div>')
    order = ["研究观察", "待核验", "优先研究", "拒绝"]
    secs = ""
    for st in order:
        xs = sorted((c for c in chk.values() if c["verdict"] == st), key=lambda c: -((cur.get(c["key"]) or {}).get("rev30") or 0))
        if xs:
            secs += f'<h2>{T(st, ALPHA_ST[st][1])} <span class="sub">{len(xs)}</span></h2>' + "".join(card(c) for c in xs)
    return (f'<div class="note">{T("第一批：无币协议收入榜前 30 名，Codex 2026-11-14 补证。「研究观察」= 对象明确、有可证伪的假设、还没查到否决项；「待核验」= 关键事实缺失或互相冲突。两档都不是推荐，也不代表会空投；同一档内按当前 30 天收入排，不打分。", "First batch: the top 30 of the tokenless revenue board, reviewed by Codex on 2026-11-14. “Watching” = clear object, a falsifiable hypothesis, no veto found yet; “To verify” = key facts missing or conflicting. Neither is a recommendation or an airdrop signal; ordered by current 30d revenue, no scores.")}</div>'
            + (ZH_ONLY if LANG["v"] == "en" else "") + secs)


ALPHA_FEED_SRC = {"ethresearch": ("研究论坛", "Research forum", "ethresear.ch"), "snapshot": ("治理提案", "Governance", "Snapshot"), "binance": ("上所公告", "Listing", "Binance")}


def alpha_feed_html(d):
    fs = d.get("feed") or []
    st = d.get("sources") or {}
    def cell(x):
        e = x.get("extra") or {}
        if x["src"] == "snapshot":
            return esc(f'{e.get("space") or ""}') + (f' · {T("投票截止", "vote ends")} {TT(e["end"])}' if e.get("end") else "")
        if x["src"] == "ethresearch":
            return T(f'{e.get("posts") or 0} 帖 · {e.get("views") or 0} 次浏览', f'{e.get("posts") or 0} posts · {e.get("views") or 0} views')
        return ""
    rows = "".join(
        f'<tr><td class="l">{T(*ALPHA_FEED_SRC[x["src"]][:2])}</td><td>{TT(x["created"])}</td>'
        f'<td class="wrap" style="min-width:260px;text-align:left"><a href="{esc(x["url"])}" target="_blank" rel="noopener">{esc(x["title"])}</a></td>'
        f'<td class="wrap" style="text-align:left;color:var(--muted)">{cell(x)}</td>'
        f'<td>{"—" if x.get("delay_h") is None else (str(round(x["delay_h"])) + T(" 小时", "h"))}</td></tr>' for x in fs)
    health = " · ".join(f'{ALPHA_FEED_SRC[k][2]} {T("正常", "ok") if (st.get(k) or {}).get("ok") else T("今天失败", "failed today")}' for k in ALPHA_FEED_SRC)
    return (f'<h2>{T("事件流", "Event feed")} <span class="sub">{T("研究论坛新帖 · 治理提案 · 上所公告，最近 14 天", "New research posts · governance proposals · listings, last 14 days")} · {len(fs)}</span></h2>'
            f'<p class="tnote">{T("只摆原始事件，不判断。ethresear.ch 只收新开的帖（旧帖被顶上来不算）；Snapshot 只收关注数 ≥ 1000 的空间、标题含收费 / 回购 / 激励 / 升级等词的提案，投票结束不等于执行；Binance 只收上币、Launchpool、空投和新永续，剔除 TradFi 永续和代币化股票，公告时间不等于开盘时间。发现延迟 = 本站首次抓到的时间 − 原始发布时间（11-14 首次接入的为基线，不算延迟）。Bybit、Upbit 在美国机房被拦，暂未接入。", "Raw events, no judgement. ethresear.ch: newly opened topics only; Snapshot: spaces with ≥ 1,000 followers and titles about fees / buybacks / incentives / upgrades — a vote ending is not execution; Binance: listings, Launchpool, airdrops and new perps, excluding TradFi perps and tokenized stocks — announcement time is not trading start. Discovery delay = first fetched here − original publish time (the 11-14 first fetch is the baseline). Bybit and Upbit block US data centres and are not connected yet.")}</p>'
            + (f'<div class="tw scroll"><table><thead><tr><th style="text-align:left">{T("来源", "Source")}</th><th>{T("发布", "Published")}</th><th style="text-align:left">{T("标题", "Title")}</th><th style="text-align:left">{T("备注", "Notes")}</th><th>{T("发现延迟", "Delay")}</th></tr></thead><tbody>{rows}</tbody></table></div>' if fs else f'<div class="note">{T("最近 14 天没有符合条件的事件。", "No matching events in the last 14 days.")}</div>')
            + f'<p class="tnote">{T("来源状态", "Source status")}：{health}</p>')


def a_usd(v):
    if v is None:
        return "—"
    a = abs(v)
    return (f"${v / 1e9:.2f}B" if a >= 1e9 else f"${v / 1e6:.2f}M" if a >= 1e6 else f"${v / 1e3:.0f}K" if a >= 1e3 else f"${v:.0f}")


def alpha_head(cur):
    fw = cur in [p for p, _, _ in ALPHA_FW]
    tabs = "".join(f'<a role="tab" href="{U("/alpha/" + p)}" class="tab{" on" if p == cur else ""}"><span class="tn">{T(zh, en)}</span><span class="ts">{T(dz, de)}</span></a>'
                   for p, zh, en, dz, de in ALPHA_TABS)
    tabs += f'<a role="tab" href="{U("/alpha/framework/")}" class="tab{" on" if fw else ""}" style="flex:0 0 auto;min-width:0"><span class="tn">{T("框架与方法", "Framework")}</span><span class="ts">{T("打分规则 · 工具", "Rules · tools")}</span></a>'
    name = next((T(zh, en) for p, zh, en, _, _ in ALPHA_TABS if p == cur), None) or next((T(zh, en) for p, zh, en in ALPHA_FW if p == cur), "")
    cr = crumbs([(T("Alpha 雷达", "Alpha Radar"), "/alpha/" if cur else None)] + ([(T("框架与方法", "Framework"), "/alpha/framework/")] if fw and cur != "framework/" else []) + ([(name, None)] if cur else []))
    sub = ""
    if fw:
        sub = '<div class="ax-sub">' + "".join(f'<a href="{U("/alpha/" + p)}" class="{"on" if p == cur else ""}">{T(zh, en)}</a>' for p, zh, en in ALPHA_FW) + "</div>"
    return (f'{cr}<div class="ph"><div><div class="eyebrow">Alpha Radar</div><h1>{T("Alpha 雷达", "Alpha radar")}</h1>'
            f'<p class="lede">{T("新协议、新产品、新机制、没发币但有真实收入的协议：每挖到一个，按同一套框架拆解打分（系统按数据打能打的，研究补其余的，未知记 U）。资金能参与的进「可投资机会」，暂时不能的进「预警观察」。只研究正规项目，不按分数排名，不是买卖建议。", "New protocols, products and mechanisms, plus tokenless protocols with real revenue, each scored on one framework (system rules + research; unknowns stay U). Capital-accessible ones are Investable, the rest Watchlist. Established projects only; no rankings; not trade advice.")}</p></div></div>'
            f'<div class="tabwrap"><nav class="tabs" role="tablist">{tabs}</nav></div>{sub}')


def alpha_framework_html():
    """框架页：直接从 alpha/framework.json 生成（单一来源），把方法论的维度、流程、打分规则做成可浏览的结构。"""
    fw = load(os.path.join(ROOT, "alpha", "framework.json"))
    if not fw:
        return ""
    e = esc
    sec = lambda k, title, s, body: f'<section class="fwsec" id="{k}"><h3>{e(title)}<span class="sec">{e(s or "")}</span></h3>{body}</section>'
    cards = lambda items, f: '<div class="cards">' + "".join(f'<div class="card">{f(x)}</div>' for x in items) + "</div>"
    ladder = lambda anchors: f'<div class="ladder{" l4" if len(anchors) == 4 else ""}">' + "".join(f'<div><span class="n">{i}</span>{e(a)}</div>' for i, a in enumerate(anchors)) + "</div>"
    c = fw["classes"]
    h = (f'<div class="ax">{ZH_ONLY if LANG["v"] == "en" else ""}<p class="small muted">{T("框架版本", "Version")} {e(fw["version"])} · {e(fw["asof"])} · {e(fw["source"])} · '
         f'<a href="{U("/alpha/method/")}">{T("方法论原文", "Original text")}</a> · <a href="/data/alpha/framework.json">framework.json</a></p>'
         f'<div class="note">{e(fw["scope"])}</div>'
         '<div class="flow">' + "".join(f'<a href="#{x["k"]}"><b>{e(x["name"])}</b><span>{e(x["out"])}</span></a>' for x in fw["flow"]) + "</div>")
    # 1 发现
    h += sec("discover", "1 · 发现线索", "三", f'<p class="small">{T("发现层的任务是尽早保留异常，不当场完成所有判断。低门槛登记、高门槛执行分开。本站雷达现在接了：无币协议收入榜、新上架协议、研究论坛新帖、治理提案、上所公告；每条记原始发布时间和本站发现时间。", "")} <a href="{U("/alpha/radar/")}">{T("看雷达 →", "Radar →")}</a></p>')
    # 2 对象
    u = fw["unit"]
    body = f'<p class="small"><b>{e(u["text"])}</b></p>' + "".join(f'<p class="small muted" style="margin:2px 0">· {e(n)}</p>' for n in u["notes"])
    for k in ("stage", "attribute", "mode"):
        body += f'<p class="small" style="margin:10px 0 4px"><b>{e(c[k]["name"])}</b> <span class="muted">决定：{e(c[k]["decides"])}</span></p><div class="opts">' + "".join(f'<span class="opt{" oos" if o.get("out_of_scope") else ""}" style="cursor:default">{e(o["name"])}</span>' for o in c[k]["opts"]) + "</div>"
    h += sec("object", "2 · 确定研究对象", u["sec"] + " / 二.2 / 二.6", body)
    # 3 价值来源
    body = f'<p class="small muted">{e(c["business"]["rule"])}</p>' + cards(c["business"]["opts"], lambda o: f'<b>{e(o["name"])}</b><p><em>为什么有人付费</em> {e(o["why"])}</p><p><em>重点观察</em> {e(o["watch"])}</p><p><em>不能推出</em> {e(o["not_infer"])}</p>')
    body += f'<h4>{e(c["right"]["name"])}</h4><p class="small muted">{e(c["right"]["rule"])}</p>' + cards(c["right"]["opts"], lambda o: f'<b>{e(o["name"])}</b><p><em>优先核对</em> {e(o["basis"])}</p><p><em>比较方式</em> {e(o["compare"])}</p>')
    body += f'<h4>{e(c["capture_case"]["name"])}</h4>' + cards(c["capture_case"]["opts"], lambda o: f'<b>{e(o["name"])}</b><p>{e(o["then"])}</p>')
    body += f'<h4>{e(c["opportunity"]["name"])}</h4><p class="small muted">{e(c["opportunity"]["rule"])}</p>' + cards(c["opportunity"]["opts"], lambda o: f'<b>{e(o["name"])}</b><p><em>收益来源</em> {e(o["source"])}</p><p><em>必须验证</em> {e(o["core"])}</p>')
    body += f'<h4>{e(c["path"]["name"])}</h4><div class="opts">' + "".join(f'<span class="opt" style="cursor:default">{e(o["name"])}</span>' for o in c["path"]["opts"]) + f'</div><p class="small muted">{e(c["path"]["rule"])}</p>'
    en_ = fw["entry"]
    body += f'<h4>{e(en_["name"])}</h4><p class="small muted">{e(en_["rule"])}</p><div class="opts">' + "".join(f'<span class="opt{"" if o.get("watch") else " on"}" style="cursor:default">{e(o["name"])}</span>' for o in en_["opts"]) + "</div>"
    q = fw["questions"]
    body += f'<h4>{e(q["name"])}</h4>' + cards(q["items"], lambda o: f'<b>{e(o["axis"])}</b><p>{e(o["name"])}</p><p><em>{e(o["hint"])}</em></p>')
    h += sec("value", "3 · 识别价值来源", "一 / 二.3–二.5", body)
    # 4 参与优势与评分
    s = fw["scores"]
    body = f'<p class="small muted">{e(s["rule"])}</p>'
    for g in ("mech", "part", "token", "invest"):
        if g not in s:
            continue
        body += f'<h4>{e(s[g]["name"])} <span class="small muted">{e(s[g]["sec"])} · {e(s[g]["applies"])} · 每项 0–{s[g]["max"]}</span></h4>'
        for it in s[g]["items"]:
            body += f'<div style="margin:8px 0"><b>{e(it["k"])} · {e(it["name"])}</b>{" <span class=" + chr(34) + "tag" + chr(34) + ">执行相关 · 不公开</span>" if it.get("private") else ""} <span class="small muted">{e(it.get("q", ""))}</span>{ladder(it["anchors"])}</div>'
    if s.get("invest"):
        body += f'<p class="small muted">{e(s["invest"]["note"])}。<b>{e(s["invest"]["facts"]["name"])}</b>：{e(s["invest"]["facts"]["rule"])}（{e("、".join(s["invest"]["facts"]["fields"]))}）</p>'
    body += f'<div class="card small"><b>区间与覆盖</b>：{e(s["formula"]["interval"])}<br>例：{e(s["formula"]["example"])}' + "".join(f'<br><b>{e(p["name"])}</b>：{e(p["rule"])}（{e(p["note"])}）' for p in s["promote"]) + "</div>"
    ar = fw["auto_rules"]
    body += f'<h4 id="auto">{e(ar["name"])} <span class="small muted">{e(ar["sec"])}</span></h4><p class="small muted">{e(ar["rule"])}</p><div class="tw"><table><tbody>' + "".join(f'<tr><td class="l"><b>{e(o["name"])}</b></td><td class="l" style="white-space:normal">{e(o["how"])}</td></tr>' for o in ar["items"]) + "</tbody></table></div>"
    cm = fw["category_map"]
    biz = {o["k"]: o["name"] for o in c["business"]["opts"]}
    body += '<details class="card" style="margin-top:8px"><summary class="small">DefiLlama 类目 → 需求来源映射表</summary>' + "".join(f'<p class="small"><b>{e(biz.get(k, k))}</b>：{e("、".join(v))}</p>' for k, v in cm.items() if not k.startswith("_")) + "</details>"
    h += sec("advantage", "4 · 评分：机制与当前参与优势", "六 / 附录一", body)
    # 5 门槛
    g = fw["gates"]
    h += sec("safety", "5 · " + g["name"], g["sec"], f'<p class="small muted">{e(g["state_rule"])}</p>' + cards(g["items"], lambda o: f'<b>{e(o["name"])}</b>' + "".join(f'<p>· {e(x)}</p>' for x in o["checks"]) + f'<p><em>{e(o["unknown_rule"])}</em></p>' + ('<p><em>个人执行，网站不公开</em></p>' if o.get("private") else "")))
    # 6 判断
    d = fw["deep"]; sx = fw["six"]; st = fw["states"]; v = fw["valuation"]; r = fw["reflexive"]
    body = cards(d["items"], lambda o: f'<b>{e(o["name"])}</b><p>{e(o["prompt"])}</p>')
    body += f'<h4>{e(sx["name"])}</h4>' + cards(sx["items"], lambda o: f'<b>{e(o["name"])}</b><p>{e(o["need"])}</p>') + f'<p class="small muted">{e(sx["counter"])}</p>'
    body += f'<h4>{e(v["name"])} <span class="small muted">{e(v["sec"])}</span></h4><div class="tw"><table><thead><tr><th class="l">研究对象</th><th class="l">优先指标</th><th class="l">避免的误用</th></tr></thead><tbody>' + "".join(f'<tr><td class="l"><b>{e(o["name"])}</b></td><td class="l" style="white-space:normal">{e(o["use"])}</td><td class="l" style="white-space:normal">{e(o["avoid"])}</td></tr>' for o in v["rows"]) + "</tbody></table></div>" + "".join(f'<p class="small muted" style="margin:2px 0">· {e(m)}</p>' for m in v["metrics"])
    body += f'<h4>{e(r["name"])}</h4><p class="small">{e(r["loop"])}</p><p class="small"><b>核心比较：</b>{e(r["core"])}</p>' + cards(r["items"], lambda o: f'<b>{e(o["name"])}</b><p><em>观测</em> {e(o["watch"])}</p><p><em>转折</em> {e(o["turn"])}</p>') + f'<p class="small muted">压力情景：{e(" / ".join(r["stress"]))}</p>'
    for k in ("community", "listing", "environment"):
        body += f'<h4>{e(fw[k]["name"])} <span class="small muted">{e(fw[k]["sec"])}</span></h4>' + "".join(f'<p class="small" style="margin:2px 0">· {e(x)}</p>' for x in fw[k]["items"])
    body += f'<h4>{e(st["name"])}</h4><div class="states">' + "".join(f'<div class="card{" priv" if o.get("private") else ""}"><b>{e(o["name"])}</b><p class="small" style="margin:4px 0"><em class="muted">进入</em> {e(o["enter"])}</p><p class="small" style="margin:4px 0"><em class="muted">下一步</em> {e(o["next"])}</p>{"<p class=" + chr(34) + "small muted" + chr(34) + ">不公开</p>" if o.get("private") else ""}</div>' for o in st["items"]) + f'</div><p class="small muted">{e(st.get("infer", ""))}</p>'
    h += sec("judge", "6 · 形成判断", "五 / 七 / 八–十 / 十一.1 / 四.1", body)
    # 7 监控
    m = fw["monitor"]
    body = '<div class="tw"><table><thead><tr><th class="l">监控面</th><th class="l">什么变化值得重开判断</th><th class="l">应输出什么</th></tr></thead><tbody>' + "".join(f'<tr><td class="l"><b>{e(o["name"])}</b></td><td class="l" style="white-space:normal">{e(o["trigger"])}</td><td class="l" style="white-space:normal">{e(o["out"])}</td></tr>' for o in m["planes"]) + "</tbody></table></div>"
    body += f'<p class="small muted">{e(m["rule"])}</p>' + cards(m["cadence"], lambda o: f'<b>{e(o["name"])}</b><p>{e(o["do"])}</p>')
    h += sec("monitor", "7 · " + m["name"], m["sec"], body)
    # 8 检验
    vf = fw["verify"]; ev = fw["evidence"]; oc = fw["outcomes"]
    body = "".join(f'<p class="small" style="margin:4px 0">· {e(x)}</p>' for x in vf["items"])
    body += f'<h4>{e(ev["name"])}</h4><div class="tw"><table><thead><tr><th class="l">证据类别</th><th class="l">能支持</th><th class="l">不能独自支持</th></tr></thead><tbody>' + "".join(f'<tr><td class="l"><b>{e(o["name"])}</b></td><td class="l" style="white-space:normal">{e(o["can"])}</td><td class="l" style="white-space:normal">{e(o["cannot"])}</td></tr>' for o in ev["items"]) + "</tbody></table></div>"
    body += f'<h4 id="outcomes">{e(oc["name"])} <span class="small muted">{e(oc["sec"])}</span></h4><p class="small">{e(oc["purpose"])}</p>' + "".join(f'<p class="small" style="margin:4px 0"><b>{e(o["name"])}</b>：{e(o["how"])}</p>' for o in oc["dims"]) + f'<p class="small"><b>怎么找相似案例</b>：{e(oc["match"])}</p><ul class="cav">' + "".join(f"<li>{e(x)}</li>" for x in oc["caveats"]) + f'</ul><p class="small"><a href="{U("/alpha/cases/")}">{T("看案例库 →", "Cases →")}</a></p>'
    h += sec("verify", "8 · 用结果检验方法", vf["sec"] + " / 附录三 / 十五", body)
    return h + "</div>"


def alpha_home_card():
    d = G.get("ALPHA")
    if not d:
        return ""
    ev = d.get("events") or []
    nr = sum(1 for e in ev if e["type"] == "new_rank")
    tk = sum(1 for e in ev if e["type"] == "token")
    base = d.get("baseline_day")
    st = (d.get("ledger") or {}).get("status") or {}
    lead = " ".join(f'<span>{esc(r["name"])} <b>{a_usd(r["rev30"])}</b></span>' for r in (d.get("tokenless") or [])[:5])
    return (f'<h2>{T("Alpha 雷达", "Alpha radar")} <span class="sub">{T("没发币但有收入的协议 · 新协议", "Tokenless protocols with revenue · new protocols")}</span>'
            f' <a class="sub" href="{U("/alpha/")}">{T("进雷达 →", "Open →")}</a></h2>'
            f'<div class="card core-home"><div class="row"><span>{T("无币协议（30 天收入 ≥ 10 万美元）", "Tokenless (30d revenue ≥ $100K)")} <b>{len(d.get("tokenless") or [])}</b></span>'
            f'<span>{T("最近 14 天新上架", "Listed in last 14d")} <b>{len(d.get("listings") or [])}</b></span>'
            f'<span>{T("今天首次进榜", "New today")} <b>{nr}</b> · {T("发币", "launched a token")} <b>{tk}</b></span>'
            f'<span><a href="{U("/alpha/pool/")}">{T("候选池", "Pool")}</a> {T("研究观察", "watching")} <b>{st.get("研究观察", 0)}</b> · {T("待核验", "to verify")} <b>{st.get("待核验", 0)}</b></span></div>'
            f'<div class="row" style="margin-top:6px">{T("收入前五：", "Top 5 by revenue: ")}{lead}</div>'
            f'<div class="row" style="margin-top:6px;font-size:12px;color:var(--muted)">{T("数据日", "Data day")} {esc(d.get("asof") or "")} · {T(f"台账从 {base} 起记，首日为基线", f"ledger since {base}; first day is the baseline")}</div></div>')


def build_alpha():
    d = G.get("ALPHA") or {}
    desc = T("Alpha 雷达：DefiLlama 上没发币但有真实收入的协议、最近上架的新协议，加线索台账、方法论和历史案例。只研究正规项目，不是买卖建议。",
             "Alpha radar: tokenless protocols with real revenue on DefiLlama, newly listed protocols, a lead ledger, the screening framework and historical cases. Established projects only; not trade advice.")
    # 雷达
    if d:
        ev = d.get("events") or []
        evn = {t: [e for e in ev if e["type"] == t] for t in ("new_rank", "token", "new_listing")}
        base = d.get("baseline_day")
        is_base = base == (d.get("generated") or "")[:10]
        evh = ""
        if is_base:
            evh = f'<div class="note">{T(f"今天（{base}）是台账第一天：表里全部记为基线，从明天起才会出现「首次进榜」和「发币」事件。", f"Today ({base}) is the ledger baseline; first-entry and token-launch events start tomorrow.")}</div>'
        else:
            def names(xs):
                return "、".join(esc(e["name"]) for e in xs[:12]) + (T(f" 等 {len(xs)} 个", f" and {len(xs) - 12} more") if len(xs) > 12 else "") if xs else T("无", "none")
            evh = (f'<div class="card" style="margin:0 0 18px;padding:12px 16px;font-size:13px">'
                   f'<div><b>{T("首次进无币收入榜", "New on the tokenless revenue board")}</b> · {names(evn["new_rank"])}</div>'
                   f'<div style="margin-top:4px"><b>{T("发币（首次发现时无币，现在有代币）", "Launched a token (tokenless when first seen)")}</b> · {names(evn["token"])}</div>'
                   f'<div style="margin-top:4px;color:var(--muted)">{T("新上架", "Newly listed")} {len(evn["new_listing"])} {T("个，见下表", "— see table below")}</div></div>')
        if d.get("stale"):
            evh = f'<div class="note">{T("今天数据源没取到，下表沿用上次结果。", "Source failed today; tables carry the last result.")}</div>' + evh
        chg = lambda v: '<span class="muted">' + T("新", "new") + "</span>" if v is None else f'<span style="color:var(--{"up" if v >= 0 else "dn"})">{v:+.0f}%</span>'
        trs = "".join(
            f'<tr><td class="rk">{i}</td><td class="wrap" style="min-width:180px;text-align:left"><a href="https://defillama.com/protocol/{esc(r["slug"] or "")}" target="_blank" rel="noopener">{esc(r["name"])}</a>'
            + (f'<div class="tnote" style="margin:2px 0 0;white-space:normal">{esc("、".join(r["children"][:3]))}{"…" if len(r["children"]) > 3 else ""}</div>' if len(r["children"]) > 1 else "")
            + f'</td><td class="l">{esc(r["category"] or "")}</td><td class="l">{esc(" · ".join(r["chains"]))}</td><td>{a_usd(r["rev30"])}</td><td>{chg(r["chg30"])}</td><td>{esc(r.get("first_seen") or "")}</td>'
            + f'<td class="l">{alpha_status_chip(r["key"])}</td></tr>'
            for i, r in enumerate(d.get("tokenless") or [], 1))
        lrs = "".join(
            f'<tr><td>{esc(r["listed"])}</td><td class="l"><a href="https://defillama.com/protocol/{esc(r["slug"] or "")}" target="_blank" rel="noopener">{esc(r["name"])}</a></td>'
            f'<td class="l">{esc(r["category"] or "")}</td><td class="l">{esc(" · ".join(r["chains"]))}</td><td>{a_usd(r["tvl"]) if r["tvl"] else "—"}</td><td class="l">{T("有", "yes") if r["token"] else T("无", "no")}</td></tr>'
            for r in d.get("listings") or [])
        lg = d.get("ledger") or {}
        src_ok = all(v.get("ok") for v in (d.get("sources") or {}).values())
        radar = (evh
                 + f'<h2>{T("没发币、有收入的协议", "Tokenless protocols with revenue")} <span class="sub">{T("近 30 天协议收入 ≥ 10 万美元，按母协议合并", "30d protocol revenue ≥ $100K, merged by parent")} · {len(d.get("tokenless") or [])}</span></h2>'
                 + f'<p class="tnote">{T("「没发币」= DefiLlama 上本协议和母协议都没登记代币，不等于确认不发币，也不等于会空投。已剔除稳定币发行方、交易所、CeDeFi、区块构建者和传统金融产品。环比 = 近 30 天 ÷ 前 30 天 − 1。", "“Tokenless” = no token registered on DefiLlama for the protocol or its parent; not a confirmation of no token, nor of an airdrop. Stablecoin issuers, CEXs, CeDeFi, block builders and TradFi products excluded. Change = last 30d ÷ prior 30d − 1.")}</p>'
                 + f'<div class="tw scroll"><table><thead><tr><th>#</th><th style="text-align:left">{T("协议", "Protocol")}</th><th style="text-align:left">{T("类目", "Category")}</th><th style="text-align:left">{T("主要链", "Chains")}</th><th>{T("30 天收入", "30d revenue")}</th><th>{T("环比", "Change")}</th><th>{T("首次进榜", "First seen")}</th><th style="text-align:left">{T("机会卡", "Card")}</th></tr></thead><tbody>{trs}</tbody></table></div>'
                 + f'<h2>{T("新上架协议", "Newly listed protocols")} <span class="sub">{T("DefiLlama 最近 14 天收录", "Added to DefiLlama in the last 14 days")} · {len(d.get("listings") or [])}</span></h2>'
                 + f'<p class="tnote">{T("收录日不是部署日，更不是能参与的日子；TVL 是存量，不是收入。", "Listing date is not deployment date or participation date; TVL is a stock, not revenue.")}</p>'
                 + f'<div class="tw scroll"><table><thead><tr><th>{T("收录日", "Listed")}</th><th style="text-align:left">{T("协议", "Protocol")}</th><th style="text-align:left">{T("类目", "Category")}</th><th style="text-align:left">{T("主要链", "Chains")}</th><th>TVL</th><th style="text-align:left">{T("代币", "Token")}</th></tr></thead><tbody>{lrs}</tbody></table></div>'
                 + alpha_feed_html(d)
                 + f'<h2>{T("线索台账", "Lead ledger")} <span class="sub">{T("保留全部分母：只追加，不删除", "All denominators kept: append-only")}</span></h2>'
                 + f'<div class="card" style="padding:12px 16px;font-size:13px">{T("累计登记", "Logged")} <b>{lg.get("n", 0)}</b> · {T("来自无币收入榜", "from revenue board")} <b>{lg.get("tokenless_rev", 0)}</b> · {T("来自新上架", "from new listings")} <b>{lg.get("new_listing", 0)}</b> · {T("之后发币", "later launched a token")} <b>{lg.get("token_seen", 0)}</b>'
                 + f' · <a href="/data/alpha/alpha_leads.json">{T("下载台账 JSON", "Ledger JSON")}</a></div>'
                 + f'<p class="tnote">{T("数据日", "Data day")} {esc(d.get("asof") or "")} · {T("生成于", "Generated")} {TT(d.get("generated"))} · {T("来源 DefiLlama（协议列表、协议收入）", "Source: DefiLlama (protocols, revenue)")}{"" if src_ok else " · " + T("有数据源失败", "a source failed")}</p>')
    else:
        radar = f'<div class="note">{T("雷达数据还没生成。", "Radar data not generated yet.")}</div>'
    ver = re.sub(r"[^0-9]", "", (G.get("OPPS") or {}).get("generated") or "")
    css = f'<link rel="stylesheet" href="{ASSET_URL["alpha.css"]}">'
    js = f'<script src="{ASSET_URL["alpha.js"]}" defer></script>'
    zh_only = ZH_ONLY if LANG["v"] == "en" else ""
    app = lambda mode: f'{zh_only}<div class="ax" id="alpha-app" data-mode="{mode}" data-v="{ver}"><p class="muted">{T("加载中…", "Loading…")}</p></div><noscript><p class="muted">{T("这一页需要开启 JavaScript。", "This page needs JavaScript.")}</p></noscript>'
    page_ = lambda rel, p, title, body: emit(rel, T(f"{title} · Alpha 雷达 · {BRAND}", f"{title} · Alpha Radar · {BRAND_EN}"), alpha_head(p) + body, active="alpha", desc=desc, extra_head=css, scripts=js, chart=True)
    page_("alpha/index.html", "", T("机会看板", "Board"), app("board"))
    emit("alpha/opp/index.html", T(f"Alpha 雷达 · {BRAND}", f"Alpha Radar · {BRAND_EN}"),   # 旧的单张机会卡链接 → 看板同一张卡
         f'<p><a href="{U("/alpha/")}">{T("机会卡已并入机会看板 →", "Cards now live on the board →")}</a></p><script>location.replace("{U("/alpha/")}"+location.hash)</script>', active="alpha")
    page_("alpha/radar/index.html", "radar/", T("雷达", "Radar"), radar)
    page_("alpha/cases/index.html", "cases/", T("案例库", "Cases"), app("cases"))
    page_("alpha/framework/index.html", "framework/", T("框架", "Framework"), alpha_framework_html())
    page_("alpha/eval/index.html", "eval/", T("评估器", "Evaluator"), app("eval"))
    emit("alpha/pool/index.html", T(f"Alpha 雷达 · {BRAND}", f"Alpha Radar · {BRAND_EN}"), f'<p><a href="{U("/alpha/")}">{T("候选池已并入机会看板 →", "The pool moved to the board →")}</a></p>',
         active="alpha", extra_head=f'<meta http-equiv="refresh" content="0; url={U("/alpha/")}">')
    for p, fn, toc in (("method/", "Alpha标的筛选研究体系.md", True), ("progress/", "研究进度.md", False)):   # 二级：框架与方法
        src = open(os.path.join(ROOT, "alpha", "research", fn), encoding="utf-8").read()
        nav = ""
        if toc:   # 目录：只列一级章节（## 开头），锚点和 core_md 的 h 编号一致
            k, items = 0, []
            for ln in src.split("\n"):
                m = re.match(r"^(#{1,4})\s+(.*)", ln.strip())
                if m:
                    k += 1
                    if len(m.group(1)) == 2:
                        items.append(f'<a href="#h{k}">{esc(m.group(2))}</a>')
            nav = '<details class="card" style="padding:10px 16px;margin:0 0 16px"><summary>' + T("目录", "Contents") + '</summary><div style="display:flex;flex-direction:column;gap:4px;margin-top:8px;font-size:13px">' + "".join(items) + "</div></details>"
        name = next(T(zh, en) for q, zh, en in ALPHA_FW if q == p)
        emit(f"alpha/{p}index.html", T(f"{name} · Alpha 雷达 · {BRAND}", f"{name} · Alpha Radar · {BRAND_EN}"),
             alpha_head(p) + zh_only + nav + f'<div class="article alpha-doc">{core_md(src)}</div>', active="alpha", desc=desc)


# ---------------------------------------------------------------- 涨腿追踪（只读 data/leg/leg_latest.json；规则在 leg/leg_data.py，文案与统计在 leg/web/leg.js）

# ---------------------------------------------------------------- RWA（rwa/：看板读 data/rwa/rwa_latest.json；研究标的读其中 research 段（来自 rwa/research/watchlist.json）；方法框架 / 进度读 rwa/research/*.md）
RWA_TABS = [("", "看板", "Board", "规模 · 谁在收钱 · 平台币", "Size · who earns · tokens"),
            ("watch/", "研究标的", "Watchlist", "判断卡 · 待核问题", "Judgment cards · open questions"),
            ("library/", "研究库", "Library", "记录 · 合约 · 市场", "Records · contracts · markets"),
            ("method/", "方法框架", "Framework", "身份 · 口径 · 证据", "Identity · metrics · evidence"),
            ("progress/", "研究进度", "Progress", "阶段 · 审查 · 外部任务", "Stages · review · tasks")]
RWA_STATE = {"pending_recheck": ("待重核", "Pending re-check", "warn"), "watch": ("观察", "Watch", "cool"),
             "waiting_evidence": ("等待证据", "Waiting for evidence", "cool"), "conditions_met": ("条件齐备", "Conditions met", "up"),
             "invalidated": ("已失效", "Invalidated", "dn"), "historical": ("历史", "Historical", "")}
RWA_PT = {"issued": ("已发平台币", "Platform token issued"), "declared_none": ("明确声明不发", "Declared no token"),
          "unverified": ("平台币未确认", "Platform token unverified"), "tradfi": ("传统机构产品", "TradFi product"), "n/a": ("不适用", "N/A")}
RWA_CSS = """<style>
.rwa3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 8px}
.rwa3 .card{padding:14px 16px}.rwa3 h3{margin:0 0 8px;font-size:13px;color:var(--muted);font-weight:600;letter-spacing:.3px}
.rwa3 .big{font:600 22px/1.25 var(--mono);margin:2px 0 6px}.rwa3 ul{margin:0;padding-left:16px;font-size:13px;line-height:1.7}
.rwafun{display:flex;flex-direction:column;gap:6px;font-size:13px}.rwafun .r{display:flex;align-items:center;gap:8px}
.rwafun .lb{flex:0 0 96px;color:var(--ink2)}.rwafun .tr{flex:1;height:10px;background:var(--wash);border:1px solid var(--line);border-radius:5px;overflow:hidden}
.rwafun .tr i{display:block;height:100%;background:var(--cool)}.rwafun .v{flex:0 0 74px;text-align:right;font-family:var(--mono)}
.rwabars{display:flex;flex-direction:column;gap:2px}.rwabar{display:grid;grid-template-columns:minmax(150px,220px) 1fr 92px;gap:10px;align-items:center;padding:8px 4px;border-bottom:1px solid var(--line)}
.rwabar .nm{font-size:13.5px}.rwabar .nm small{display:block;color:var(--muted);font-size:11.5px;margin-top:2px;line-height:1.5}
.rwabar .tr{height:12px;background:var(--wash);border-radius:6px;overflow:hidden}.rwabar .tr i{display:block;height:100%;background:var(--up);opacity:.75}
.rwabar .tr i.w{background:var(--warn)}.rwabar .v{text-align:right;font-family:var(--mono);font-size:13px}.rwabar .v small{display:block;font-size:11px}
.rwacards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.rwacard{padding:14px 16px}.rwacard h3{margin:0 0 6px;font-size:15px}
.rwacard .chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px}.rwacard dl{display:grid;grid-template-columns:86px 1fr;gap:4px 10px;margin:8px 0;font-size:12.5px}
.rwacard dt{color:var(--muted)}.rwacard dd{margin:0}.rwacard ul{margin:4px 0 0;padding-left:16px;font-size:12.5px;line-height:1.7}
.rwacard details{margin-top:8px;font-size:12px;color:var(--ink2)}
.libf{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}.libf input,.libf select{background:var(--card);color:var(--ink);border:1px solid var(--line2);border-radius:8px;padding:7px 10px;font:inherit;font-size:13px}
.libf input{flex:1 1 220px}.lib{border-bottom:1px solid var(--line)}.lib>summary{display:grid;grid-template-columns:minmax(160px,1.4fr) 1fr 1fr 130px;gap:10px;align-items:center;padding:9px 6px;cursor:pointer;list-style:none;font-size:13px}
.lib>summary::-webkit-details-marker{display:none}.lib>summary:hover,.lib>summary:focus-visible{background:var(--hover)}.lib>summary .nm b{font-weight:600}.lib>summary .nm small{display:block;color:var(--muted);font-size:11.5px}
.lib .bd{padding:4px 10px 14px;font-size:12.5px;line-height:1.7}.lib .bd table{font-size:12px}.lib .mono{font-family:var(--mono);font-size:11.5px;word-break:break-all}.lib .bd h4{margin:10px 0 4px;font-size:12.5px;color:var(--muted);font-weight:600}
.libsum{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;padding:12px 16px}.libsum b{font-family:var(--mono)}
@media (max-width:820px){.lib>summary{grid-template-columns:1fr auto}.lib>summary .c3,.lib>summary .c4{display:none}}
@media (max-width:820px){.rwa3,.rwacards{grid-template-columns:1fr}.rwabar{grid-template-columns:1fr 84px}.rwabar .tr{grid-column:1/3;grid-row:2}}
</style>"""


def write_rwa_data():
    src = os.path.join(DATA, "rwa")
    G["RWA"] = load(os.path.join(src, "rwa_latest.json"))
    G["RWA_HIST"] = load(os.path.join(src, "rwa_history.json"), []) or []
    if not G["RWA"]:
        return
    out = os.path.join(SITE, "data", "rwa")
    os.makedirs(out, exist_ok=True)
    pub = {k: v for k, v in G["RWA"].items() if k != "asset_ids"}
    with open(os.path.join(out, "rwa_latest.json"), "w", encoding="utf-8") as f:
        json.dump(pub, f, ensure_ascii=False, indent=1)
    shutil.copyfile(os.path.join(src, "rwa_history.json"), os.path.join(out, "rwa_history.json"))
    G["RWA_LIB"] = load(os.path.join(src, "universe.json"))
    if G["RWA_LIB"]:
        shutil.copyfile(os.path.join(src, "universe.json"), os.path.join(out, "universe.json"))


def rwa_head(cur):
    tabs = "".join(f'<a role="tab" href="{U("/rwa/" + p)}" class="tab{" on" if p == cur else ""}"><span class="tn">{T(zh, en)}</span><span class="ts">{T(dz, de)}</span></a>'
                   for p, zh, en, dz, de in RWA_TABS)
    name = next(T(zh, en) for p, zh, en, _, _ in RWA_TABS if p == cur)
    cr = crumbs([("RWA", "/rwa/" if cur else None)] + ([(name, None)] if cur else []))
    return (f'{cr}<div class="ph"><div><div class="eyebrow">Real-World Assets</div><h1>{T("RWA 现实资产", "RWA · real-world assets")}</h1>'
            f'<p class="lede">{T("把基金、国债、黄金、股票、信贷搬上链的整条产业链：规模在哪、谁付费谁收钱、哪些有平台币、研究标的的判断和待核问题。资产币、平台币、传统机构产品分开记；只摆读数、证据和未知项，不是买卖建议。", "The whole chain that brings funds, treasuries, gold, stocks and credit onchain: where the size is, who pays and who earns, which have platform tokens, and research judgments with open questions. Asset tokens, platform tokens and TradFi products are kept apart; readings, evidence and unknowns only — not trade advice.")}</p></div></div>'
            f'<div class="tabwrap"><nav class="tabs" role="tablist">{tabs}</nav></div>')


def rwa_cat(d, cid):
    return next((c for c in (d or {}).get("categories") or [] if c.get("id") == cid and not c.get("missing")), None)


def rwa_home_card():
    d = G.get("RWA")
    if not d:
        return ""
    t = d.get("totals") or {}
    rs = (d.get("research") or {})
    tre, gold = rwa_cat(d, "tokenized-treasuries"), rwa_cat(d, "tokenized-gold")
    v = lambda c: a_usd(c.get("mcap")) if c else "—"
    return (f'<h2>RWA <span class="sub">{T("现实资产上链：规模 · 谁在收钱 · 研究标的", "Real-world assets: size · who earns · watchlist")}</span>'
            f' <a class="sub" href="{U("/rwa/")}">{T("进看板 →", "Open →")}</a></h2>'
            f'<div class="card core-home"><div class="row"><span>{T("代币化国债", "Tokenized treasuries")} <b>{v(tre)}</b></span>'
            f'<span>{T("代币化黄金", "Tokenized gold")} <b>{v(gold)}</b></span>'
            f'<span>{T("链上 RWA 协议 30 天手续费", "Onchain RWA fees, 30d")} <b>{a_usd(t.get("fees30_onchain"))}</b> → {T("归代币持有人", "to token holders")} <b>{a_usd(t.get("hrev30_onchain"))}</b></span></div>'
            f'<div class="row" style="margin-top:6px;font-size:12px;color:var(--muted)">{T("研究标的", "Watchlist")} {len(rs.get("items") or [])} {T("条，全部待重核（研究库迁入中）", "items, all pending re-check (library migration in progress)") if all(i["current"].get("state") == "pending_recheck" for i in rs.get("items") or []) else ""}'
            f' · {T("采样", "Sampled")} {TT(d.get("cg_sampled"))} · CoinGecko / DefiLlama</div></div>')


def rwa_link(kind, slug):
    from urllib.parse import quote
    if not slug:
        return None
    return (f"https://defillama.com/protocol/{quote(str(slug), safe='')}" if kind == "llama" else f"https://www.coingecko.com/en/coins/{quote(str(slug), safe='')}")


def rwa_a(text, href):
    return f'<a href="{esc(href)}" target="_blank" rel="noopener noreferrer">{esc(text)}</a>' if href else esc(text)


def rwa_tok(r):
    st, tk = r.get("token_status"), r.get("token") or {}
    sym = esc(tk.get("symbol") or "")
    if st == "registered":
        return f'<span class="chip" data-tag="rwa_tok_reg">{T("登记代币", "Token")} {sym}</span>'
    if st == "asset_token":
        return f'<span class="chip t-cool" data-tag="rwa_tok_asset">{T("资产币", "Asset token")} {sym}</span>'
    if st == "tradfi":
        return f'<span class="chip" data-tag="rwa_tradfi">{T("传统机构", "TradFi")}</span>'
    return f'<span class="chip t-warn" data-tag="rwa_tok_none">{T("未登记 ≠ 无币", "None listed ≠ no token")}</span>'


def rwa_pct(v):
    if v is None:
        return '<span class="muted">—</span>'
    return f'<span style="color:var(--{"up" if v >= 0 else "dn"})">{v:+.1f}%</span>'


def rwa_board(d):
    if not d:
        return f'<div class="note">{T("RWA 数据还没生成。", "RWA data not generated yet.")}</div>'
    src = d.get("sources") or {}
    warn = ""
    for k, nm in (("coingecko", "CoinGecko"), ("defillama", "DefiLlama")):
        s = src.get(k) or {}
        if s and not s.get("ok"):
            warn += f'<div class="note">{nm} {T("这次没取到，下面沿用上次成功的结果（", "failed this run; showing the last good result (")}{TT(s.get("last_ok")) if s.get("last_ok") else T("无", "none")}{T("）。", ").")}</div>'
    t = d.get("totals") or {}
    cats = [c for c in d.get("categories") or [] if not c.get("missing")]
    assets = [c for c in cats if c.get("role") == "asset" and c.get("mcap")]
    hist = [h for h in G.get("RWA_HIST") or [] if h.get("cats")]
    prev = hist[-2] if len(hist) >= 2 else None
    # ① 发生什么
    big = sorted(assets, key=lambda c: -(c.get("mcap") or 0))
    def cname(c):
        return T(c["zh"], c["en"])
    happen = []
    tre = rwa_cat(d, "tokenized-treasuries")
    if tre:
        tp = (tre.get("top") or [{}])[0]
        happen.append(T(f"代币化国债 <b>{a_usd(tre['mcap'])}</b>，{tre['n']} 个币，最大 {esc(tp.get('sym'))} 占 {tp.get('share')}%",
                        f"Tokenized treasuries <b>{a_usd(tre['mcap'])}</b>, {tre['n']} tokens; largest {esc(tp.get('sym'))} is {tp.get('share')}%"))
    mv = [c for c in assets if c.get("chg24") is not None and not c.get("nested_in") and not c.get("overlap")]
    if mv:
        hi = max(mv, key=lambda c: abs(c["chg24"]))
        happen.append(T(f"24 小时市值变动最大：{cname(hi)} {rwa_pct(hi['chg24'])}（CoinGecko 口径，含价格变动）", f"Biggest 24h market-cap move: {cname(hi)} {rwa_pct(hi['chg24'])} (CoinGecko, includes price)"))
    conc = [c for c in assets if (c.get("top") or [{}])[0].get("share", 0) >= 90 and c.get("n", 0) <= 3]
    for c in conc:
        happen.append(T(f"{cname(c)} {a_usd(c['mcap'])} 几乎全是 {esc(c['top'][0]['sym'])} 一个，不能当行业规模读", f"{cname(c)} {a_usd(c['mcap'])} is almost entirely {esc(c['top'][0]['sym'])}; not an industry-size reading"))
    if prev:
        happen.append(T(f"上次采样 {TT(prev.get('cg_sampled'))}，变化见下方「规模」每行右侧", f"Previous sample {TT(prev.get('cg_sampled'))}; changes shown per row below"))
    else:
        happen.append(T("历史从今天开始逐日记录（不回填），满两次采样后显示「比上次」", "History is recorded daily from today (no backfill); “vs previous” appears from the second sample"))
    # ② 谁在收钱：漏斗，宽度按手续费归一
    f30 = t.get("fees30_onchain") or 0
    fun = "".join(f'<div class="r"><span class="lb">{lb}</span><span class="tr"><i style="width:{(v / f30 * 100) if f30 else 0:.1f}%"></i></span><span class="v">{a_usd(v)}</span></div>'
                  for lb, v in ((T("用户付的手续费", "Fees paid"), f30), (T("协议留下的", "Protocol revenue"), t.get("rev30_onchain") or 0), (T("归代币持有人", "To token holders"), t.get("hrev30_onchain") or 0)))
    # ③ 研究
    rs = d.get("research") or {}
    items = rs.get("items") or []
    mig = rs.get("migration") or {}
    cnt = rs.get("counts") or {}
    cnt_h = " · ".join(f'{T(RWA_STATE[k][0], RWA_STATE[k][1])} {v}' for k, v in cnt.items() if k in RWA_STATE)
    top3 = f"""<div class="rwa3">
<div class="card"><h3>{T("发生什么", "What's happening")}</h3><ul>{"".join(f"<li>{x}</li>" for x in happen)}</ul></div>
<div class="card"><h3>{T("谁在收钱 · 链上 RWA 协议近 30 天", "Who earns · onchain RWA protocols, 30d")}</h3><div class="rwafun">{fun}</div>
<p class="tnote" style="margin-top:8px">{T(f"{t.get('n_onchain', 0)} 个协议里只有 {t.get('n_hrev_pos', 0)} 个有持有人收入。传统机构产品（Grayscale ETF 管理费等）另有手续费 {a_usd(t.get('fees30_tradfi'))}，不算在内。", f"Only {t.get('n_hrev_pos', 0)} of {t.get('n_onchain', 0)} protocols pay token holders. TradFi products (Grayscale ETF fees etc.) add {a_usd(t.get('fees30_tradfi'))} in fees, excluded.")}</p></div>
<div class="card"><h3>{T("研究标的 · 现在能做什么", "Watchlist · what can be done now")}</h3><div class="big">{len(items)} <span style="font-size:13px;color:var(--muted)">{T("条", "items")}</span></div>
<div style="font-size:13px">{cnt_h}</div><p class="tnote" style="margin-top:6px">{esc(T(mig.get("note_zh", ""), mig.get("note_en", "")))}</p>
<p style="margin:6px 0 0;font-size:13px"><a href="{U("/rwa/watch/")}">{T("看判断卡和待核问题 →", "Judgment cards & open questions →")}</a></p></div>
</div>"""
    # 规模
    mx = max((c["mcap"] for c in assets), default=1)
    def bar(c):
        tp = (c.get("top") or [{}])[0]
        one = tp.get("share", 0) >= 90
        tags = []
        if c.get("nested_in"):
            tags.append(T("包含在「商品」里", "inside “commodities”"))
        if c.get("overlap"):
            tags.append(T("和「国债」大量重叠", "overlaps “treasuries”"))
        n = (("≥" if c.get("truncated") else "") + str(c.get("n")))
        sub = T(f"{n} 个币 · 最大 ", f"{n} tokens · top ") + rwa_a(tp.get("sym") or "", rwa_link("cg", tp.get("id"))) + f" {tp.get('share')}%"
        if tp.get("role"):
            sub += " · " + esc(T(tp["role"]["zh"], tp["role"]["en"]))
        if c.get("note_zh"):
            tags.append(T(c["note_zh"], c.get("note_en", "")))
        if tags:
            sub += " · " + " · ".join(tags)
        vs = ""
        if prev and prev["cats"].get(c["id"]) and c.get("mcap"):
            vs = f'<small>{T("比上次", "vs prev")} {rwa_pct((c["mcap"] / prev["cats"][c["id"]] - 1) * 100)}</small>'
        else:
            vs = f'<small>24h {rwa_pct(c.get("chg24"))}</small>'
        return (f'<div class="rwabar"><div class="nm">{esc(cname(c))}<small>{sub}</small></div>'
                f'<div class="tr" title="{esc(a_usd(c["mcap"]))}"><i class="{"w" if one else ""}" style="width:{c["mcap"] / mx * 100:.1f}%"></i></div>'
                f'<div class="v">{a_usd(c["mcap"])}{vs}</div></div>')
    bars = "".join(bar(c) for c in big)
    mixed = rwa_cat(d, "real-world-assets-rwa")
    mixed_cap = a_usd((mixed or {}).get("mcap"))
    # 谁在收钱表
    on = [r for r in d.get("protocols") or [] if r["kind"] == "onchain" and (r.get("fees30") or 0) > 0][:30]
    tf = [r for r in d.get("protocols") or [] if r["kind"] == "tradfi"]
    def prow(i, r):
        sub = ""
        if len(r.get("children") or []) > 1:
            sub = f'<div class="tnote" style="margin:2px 0 0;white-space:normal">{esc("、".join(r["children"][:3]))}{"…" if len(r["children"]) > 3 else ""}</div>'
        return (f'<tr><td class="rk">{i}</td><td class="wrap" style="min-width:170px;text-align:left">{rwa_a(r["name"], rwa_link("llama", r.get("slug")))}{sub}</td>'
                f'<td class="l">{esc(" · ".join(r.get("chains") or []))}</td><td>{a_usd(r.get("fees30"))}</td><td>{a_usd(r.get("rev30"))}</td>'
                f'<td>{a_usd(r.get("hrev30")) if r.get("hrev30") else "—"}</td><td>{rwa_pct(r.get("chg30"))}</td><td class="l">{rwa_tok(r)}</td></tr>')
    th = (f'<thead><tr><th>#</th><th style="text-align:left">{T("协议（按母协议合并）", "Protocol (by parent)")}</th><th style="text-align:left">{T("主要链", "Chains")}</th>'
          f'<th>{T("手续费", "Fees")}</th><th>{T("协议收入", "Revenue")}</th><th>{T("持有人收入", "Holders")}</th><th>{T("手续费环比", "Fees chg")}</th><th style="text-align:left">{T("代币身份", "Token identity")}</th></tr></thead>')
    ptbl = f'<div class="tw scroll"><table>{th}<tbody>{"".join(prow(i, r) for i, r in enumerate(on, 1))}</tbody></table></div>'
    ttbl = f'<div class="tw scroll"><table>{th}<tbody>{"".join(prow(i, r) for i, r in enumerate(tf, 1))}</tbody></table></div>' if tf else ""
    # 平台币
    pl = (d.get("platform") or [])[:25]
    plr = "".join(
        f'<tr><td class="rk">{i}</td><td class="wrap" style="min-width:160px;text-align:left">{rwa_a(p["name"], rwa_link("cg", p["id"]))} <span class="muted">{esc(p["sym"])}</span>'
        + (f'<div class="tnote" style="margin:2px 0 0;white-space:normal">{esc(T(p["role"]["zh"], p["role"]["en"]))}</div>' if p.get("role") else "")
        + f'</td><td>{a_usd(p.get("mcap"))}</td><td>{a_usd(p.get("fdv"))}</td><td>{a_usd(p.get("vol24"))}</td><td>{rwa_pct(p.get("chg24"))}</td></tr>'
        for i, p in enumerate(pl, 1))
    plc = rwa_cat(d, "rwa-protocol") or {}
    pltop = (plc.get("top") or [{}])[0]
    pl_cap, pl_sym, pl_sh = a_usd(plc.get("mcap")), esc(pltop.get("sym") or "—"), pltop.get("share")
    return (warn + top3
            + f'<h2>{T("规模 · 按资产类", "Size by asset class")} <span class="sub">{T("CoinGecko 分类市值 · 资产币", "CoinGecko category market cap · asset tokens")}</span></h2>'
            + f'<p class="tnote">{T("分类之间有包含和重叠，不求和。条宽按本表最大值等比；琥珀色 = 单个币占 90% 以上。CoinGecko 分类只覆盖它收录的币，许可制基金（只在白名单之间转让）常常缺价格或缺席，所以这里偏小，不是行业全量。", "Categories nest and overlap; not summed. Bar width is proportional to the largest row; amber = one token is over 90%. CoinGecko only covers tokens it lists; permissioned funds are often missing, so these figures understate the industry.")}</p>'
            + f'<div class="card" style="padding:6px 14px"><div class="rwabars">{bars}</div></div>'
            + (f'<p class="tnote">{T(f"CoinGecko 的「RWA」大类 {mixed_cap} 把资产币和平台币混在一起，只作参考。", f"CoinGecko’s “RWA” umbrella ({mixed_cap}) mixes asset and platform tokens; reference only.")}</p>' if mixed else "")
            + f'<h2>{T("谁在收钱", "Who earns")} <span class="sub">{T("DefiLlama · 近 30 天 · 链上 RWA 协议", "DefiLlama · last 30d · onchain RWA protocols")} · {len(on)}</span></h2>'
            + f'<p class="tnote">{T("手续费 = 用户付的总额（多数是基金管理费，归管理人）；协议收入 = 协议自己留下的；持有人收入 = 分给代币持有人的。「登记代币」是 DefiLlama 登记的代币，平台币身份还要研究层核对；「资产币」= 登记的其实是产品份额 / 黄金，不是平台币；「未登记 ≠ 无币」。环比 = 近 30 天 ÷ 前 30 天 − 1。", "Fees = total paid by users (mostly fund management fees to managers); revenue = what the protocol keeps; holders = paid to token holders. “Token” = registered on DefiLlama, platform-token identity still to be checked; “asset token” = the registered token is a product share / gold, not a platform token; “none listed ≠ no token”. Change = last 30d ÷ prior 30d − 1.")}</p>'
            + ptbl
            + (f'<h3 style="margin:18px 0 8px;font-size:14px">{T("传统机构产品（单列，不算进上面的合计）", "TradFi products (separate, not in the totals above)")}</h3>' + ttbl if ttbl else "")
            + f'<h2>{T("平台币 / 协议币", "Platform & protocol tokens")} <span class="sub">{T("CoinGecko「RWA Protocol」分类", "CoinGecko “RWA Protocol” category")} · {plc.get("n", "—")}</span></h2>'
            + f'<p class="tnote">{T(f"这个分类合计 {pl_cap}，其中 {pl_sym} 占 {pl_sh}%。平台币价格和底层资产规模不一定相关；身份特殊的在名字下面注明。", f"Category total {pl_cap}; {pl_sym} alone is {pl_sh}%. Platform-token prices need not track underlying asset size; special identities are noted under the name.")}</p>'
            + f'<div class="tw scroll"><table><thead><tr><th>#</th><th style="text-align:left">{T("代币", "Token")}</th><th>{T("流通市值", "Market cap")}</th><th>FDV</th><th>{T("24h 成交额", "24h volume")}</th><th>24h</th></tr></thead><tbody>{plr}</tbody></table></div>'
            + f'<p class="tnote">{T("CoinGecko 采样", "CoinGecko sampled")} {TT(d.get("cg_sampled"))} · {T("DefiLlama 30 天窗口截至", "DefiLlama 30d window to")} {esc(d.get("asof_llama") or "")} · {T("生成于", "Generated")} {TT(d.get("generated"))}'
            + f' · <a href="/data/rwa/rwa_latest.json">{T("下载 JSON", "JSON")}</a> · <a href="/data/rwa/rwa_history.json">{T("历史", "History")}</a></p>')


def rwa_watch(d):
    rs = (d or {}).get("research") or {}
    mig = rs.get("migration") or {}
    items = rs.get("items") or []
    lim = rs.get("stale_days", 14)
    head = (f'<div class="note">{esc(T(mig.get("note_zh", ""), mig.get("note_en", "")))} '
            f'{T(f"判断最后复核超过 {lim} 天的标「过期待复核」。", f"Judgments not re-checked for over {lim} days are marked stale.")}</div>')
    na = f'<span class="muted">{T("— 待复核后填写", "— to be filled after re-check")}</span>'
    cards = []
    for it in items:
        cur = it.get("current") or {}
        st = RWA_STATE.get(cur.get("state"), (cur.get("state") or "?", cur.get("state") or "?", "warn"))
        pt = it.get("platform_token") or {}
        ptl = RWA_PT.get(pt.get("status"), (pt.get("status") or "?", pt.get("status") or "?"))
        fresh = {"never": T("从未按原始来源复核", "never re-checked at source"), "stale": T(f"过期待复核（{it.get('age_days')} 天）", f"stale ({it.get('age_days')}d)"),
                 "fresh": T(f"{it.get('age_days')} 天前复核", f"re-checked {it.get('age_days')}d ago")}.get(it.get("fresh"), "")
        fld = lambda k: esc(T(cur.get(k + "_zh") or cur.get(k) or "", cur.get(k + "_en") or cur.get(k) or "")) or na
        oq = "".join(f"<li>{esc(q)}</li>" for q in it.get("open_questions") or [])
        facts = "".join(f'<li>{esc(f.get("claim"))} · {rwa_a(T("来源", "source"), f.get("src") if str(f.get("src", "")).startswith("https://") else None)} · {esc(f.get("checked_utc") or "")}</li>' for f in it.get("facts") or [])
        vers = "".join(f'<li>{esc(v.get("v"))} · {esc(T(RWA_STATE.get(v.get("state"), (v.get("state"),) * 2)[0], RWA_STATE.get(v.get("state"), (v.get("state"),) * 2)[1]))}'
                       + (f' · {T("原状态", "was")}「{esc(v["old_state"])}」' if v.get("old_state") else "") + "</li>" for v in it.get("versions") or [])
        lk = it.get("links") or {}
        links = " · ".join(x for x in (rwa_a(T("官网", "Official"), lk.get("official")) if str(lk.get("official") or "").startswith("https://") else "",
                                        rwa_a(T("来源", "Source"), lk.get("source")) if str(lk.get("source") or "").startswith("https://") else "",
                                        f'<a href="{U("/rwa/library/")}#{lib_anchor(it["library_rid"])}">{T("研究库记录", "Library record")}</a>' if it.get("library_rid") else "") if x)
        cards.append(
            f'<div class="card rwacard" id="{esc(it.get("id", "").replace(":", "-"))}"><h3>{esc(it.get("name"))}</h3><div class="chips">'
            f'<span class="chip{" t-" + st[2] if st[2] else ""}">{esc(T(st[0], st[1]))}</span><span class="chip">{esc(T(ptl[0], ptl[1]))}</span>'
            f'<span class="chip">{esc(fresh)}</span></div>'
            + (f'<div style="font-size:12px;margin:0 0 6px">{links}</div>' if links else "")
            + f'<div style="font-size:13px;line-height:1.7">{fld("why")}</div>'
            f'<dl><dt>{T("触发条件", "Trigger")}</dt><dd>{fld("trigger")}</dd><dt>{T("失效条件", "Invalidation")}</dt><dd>{fld("invalid")}</dd>'
            f'<dt>{T("谁能参与", "Eligibility")}</dt><dd>{fld("eligibility")}</dd><dt>{T("参与成本", "Cost")}</dt><dd>{fld("cost")}</dd><dt>{T("退出路径", "Exit")}</dt><dd>{fld("exit")}</dd></dl>'
            + (f'<div style="font-size:12.5px;color:var(--muted)">{T("已核事实", "Verified facts")}</div><ul>{facts}</ul>' if facts else "")
            + (f'<div style="font-size:12.5px;color:var(--muted);margin-top:6px">{T("待核问题", "Open questions")}</div><ul>{oq}</ul>' if oq else "")
            + (f'<details><summary>{T("平台币原始标注 · 判断版本", "Raw token label · versions")}</summary><div style="margin-top:6px">{esc(pt.get("raw") or "—")}</div><ul>{vers}</ul></details>')
            + "</div>")
    prob = rs.get("problems") or []
    pb = (f'<div class="note">{T("研究库校验提示：", "Library validation: ")}' + "；".join(esc(p) for p in prob) + "</div>") if prob else ""
    return head + pb + f'<div class="rwacards">{"".join(cards)}</div>' + f'<p class="tnote">{T("研究库更新于", "Library updated")} {esc(rs.get("updated_utc") or "")} · {T("任务包", "Task pack")}: rwa/review/README.md</p>'


def lib_anchor(rid):
    return "r-" + re.sub(r"[^a-z0-9]+", "-", str(rid).lower()).strip("-")


RWA_SEG_EN = {"fund": "Funds & treasuries", "equity": "Equities", "commodity": "Commodities", "credit": "Credit", "realestate": "Real estate",
              "collectible": "Collectibles", "stablecoin": "Stablecoins / deposits", "trading": "Trading & aggregation", "derivatives": "Derivatives",
              "settlement": "Issuance / settlement / custody", "identity": "Identity & compliance", "data": "Data / oracles", "other": "Other"}
RWA_ROLE = {"platform_token": ("平台币", "Platform token"), "asset_token": ("资产币", "Asset token"), "business": ("业务合约", "Business contract")}


def rwa_library():
    from collections import Counter
    L = G.get("RWA_LIB")
    if not L:
        return f'<div class="note">{T("研究库还没导入。", "Library not imported yet.")}</div>'
    c = L["counts"]
    segz = L.get("segments") or {}
    seg_name = lambda k: T(segz.get(k, k), RWA_SEG_EN.get(k, k))
    ptn = lambda k: T(*RWA_PT.get(k, (k, k)))
    pt_tone = {"issued": " t-cool", "declared_none": "", "tradfi": "", "unverified": " t-warn"}
    ent = {e["id"]: e for e in L["entities"]}
    summ = (f'<div class="card libsum"><span>{T("记录", "Records")} <b>{c["records"]}</b>（{T("主库", "main")} {c["main"]} + {T("发现队列", "discovery")} {c["discovery"]}{T("，其中缺 id 的旧记录", "; legacy without id")} {c["missing_id"]}）</span>'
            f'<span>{T("独立实体", "Entities")} <b>{c["entities"]}</b></span>'
            + "".join(f'<span>{ptn(k)} <b>{v}</b></span>' for k, v in sorted(c["pt"].items(), key=lambda t: -t[1]))
            + f'<span>{T("合约", "Contracts")} ' + " · ".join(f'{T(*RWA_ROLE.get(k, (k, k)))} <b>{v}</b>' for k, v in c["contracts"].items()) + '</span>'
            + f'<span>{T("DEX 池子", "DEX pools")} <b>{c["markets_dex"]}</b>（{T("挂上同链代币", "linked to a same-chain token")} {c["markets_dex_linked"]}）· {T("CEX 交易对", "CEX pairs")} <b>{c["markets_cex"]}</b></span></div>')
    r1n = c.get("r1_entities")
    note = (f'<p class="tnote">{T(f"实体按官网 / 产品页的主域名去重；数据平台、新闻稿、社交站的域名不当身份，没有官网的按 DefiLlama 母协议或单条记录算（Codex 原件按来源域名并成 {r1n} 个，把 41 个项目并成了「defillama.com」，已纠正）。分类按关键词粗分，可能有误。平台币状态是研究库原记录的映射，大多数是「未确认」，不等于没有。合约「核对级别」写的是原记录怎么来的：目录提示 ≠ 官方确认 ≠ 链上验证。", "Entities are deduplicated by official / product domain; data-platform, press-release and social domains are not identities. Segments are keyword-based and rough. Platform-token status maps the library’s original labels; most are “unverified”, which is not “none”. Contract check level says how the record was obtained: directory hint ≠ official ≠ onchain.")}</p>'
            f'<p class="tnote">{T("研究库导出于", "Exported")} {TT(L["source"].get("exported_utc"))} · {T("导入于", "Imported")} {TT(L.get("generated"))} · {T("这是研究底稿，记录里的说法大多没有逐条复核", "Research working file; most statements are not individually re-verified")} · <a href="/data/rwa/universe.json">JSON</a></p>')
    segs = Counter(x["segment"] for x in L["records"])
    fl = (f'<div class="libf" role="search"><input type="search" id="libq" placeholder="{T("搜名字 / symbol / 合约地址 / 链", "Search name / symbol / address / chain")}" aria-label="{T("搜索研究库", "Search library")}">'
          f'<select id="libseg" aria-label="{T("分类", "Segment")}"><option value="">{T("全部分类", "All segments")}</option>' + "".join(f'<option value="{k}">{esc(seg_name(k))}（{n}）</option>' for k, n in segs.most_common()) + '</select>'
          f'<select id="libpt" aria-label="{T("平台币状态", "Platform token")}"><option value="">{T("全部平台币状态", "Any token status")}</option>' + "".join(f'<option value="{k}">{esc(ptn(k))}</option>' for k in c["pt"]) + '</select>'
          f'<select id="libpool" aria-label="{T("来源", "Pool")}"><option value="">{T("主库 + 发现队列", "Main + discovery")}</option><option value="main">{T("主库", "Main")}</option><option value="discovery">{T("发现队列", "Discovery")}</option></select>'
          f'<span id="libn" class="muted" style="align-self:center;font-size:12.5px"></span></div>')
    def fmt_t(x):
        return esc(str(x)[:10]) if x else "—"
    def link(u, txt):
        return rwa_a(txt, u) if str(u or "").startswith("https://") else (esc(txt) if u else "")
    rows = []
    for x in sorted(L["records"], key=lambda r: (r["pool"] != "main", (r["name"] or "").lower())):
        e = ent.get(x["entity"]) or {}
        cts = "".join(f'<tr><td class="l">{esc(T(*RWA_ROLE.get(k["role"], (k["role"], k["role"]))))}{" · " + esc(k["sub"]) if k.get("sub") else ""}</td><td class="l">{esc(k.get("chain") or "—")}</td>'
                      f'<td class="l mono">{esc(k.get("address") or "—")}</td><td class="l">{esc(k.get("check") or "U")}</td><td class="l">{fmt_t(k.get("at"))}</td><td class="l">{link(k.get("src"), T("来源", "src"))}</td></tr>' for k in x["contracts"])
        mks = "".join(f'<tr><td class="l">{esc(m["venue"].upper())} · {esc(m.get("name") or "")}</td><td class="l">{esc(m.get("chain") or "—")}</td><td class="l">{esc(m.get("pair") or "")}</td>'
                      f'<td class="l mono">{esc(m.get("pool") or "—")}</td><td>{a_usd(m.get("liq")) if m.get("liq") is not None else "—"}</td><td class="l">{fmt_t(m.get("at"))}</td>'
                      f'<td class="l">{T("同链代币", "linked") if m.get("linked") else ("—" if m["venue"] == "cex" else T("未挂上", "unlinked"))}</td></tr>' for m in x["markets"])
        nts = "".join(f'<li>{fmt_t(n.get("at"))} · {esc(n.get("text"))} {link(n.get("src"), T("来源", "src"))}{" · " + esc(n["level"]) if n.get("level") else ""}</li>' for n in x["notes"])
        hay = " ".join([x["name"] or "", x.get("symbol") or "", " ".join(x["chains"] or []), " ".join(k.get("address") or "" for k in x["contracts"]), e.get("name") or "", x["rid"]]).lower()
        body = (f'<div>{T("实体", "Entity")}：{esc(e.get("name") or "")} <span class="muted">（{esc(e.get("domain") or e.get("basis") or "")}，{len(e.get("records") or [])} {T("条记录", "records")}）</span>'
                f' · {link(x.get("official"), T("官网", "Official"))} {link(x.get("source"), T("来源", "Source"))}</div>'
                + (f'<div>{T("业务", "Business")}：{esc(x["role_text"])}</div>' if x.get("role_text") else "")
                + f'<div class="muted">{T("平台币原标签", "Raw token label")} <span class="mono">{esc(x.get("pt_raw") or "—")}</span>'
                + (f' · symbol {esc(x["symbol"])}（{T("只作提示", "hint only")}）' if x.get("symbol") else "")
                + (f' · <span class="mono">{esc(x["symbol_role"])}</span>' if x.get("symbol_role") else "")
                + f' · {T("分类原文", "Raw segment")} {esc((x.get("segment_raw") or "—")[:60])} · {T("证据级别", "Evidence")} {esc(x.get("evidence") or "U")}</div>'
                + f'<div class="muted">{T("首次发现", "First seen")} {fmt_t(x.get("first_seen"))} · {T("最后检查", "Last checked")} {fmt_t(x.get("last_checked"))} · {T("资料核实", "Verified")} {fmt_t(x.get("verified_at"))} · {T("目录核实", "Directory checked")} {fmt_t(x.get("directory_checked"))}</div>'
                + (f'<h4>{T("合约", "Contracts")}</h4><div class="scroll"><table><thead><tr><th class="l">{T("角色", "Role")}</th><th class="l">{T("链", "Chain")}</th><th class="l">{T("地址", "Address")}</th><th class="l">{T("核对级别", "Check")}</th><th class="l">{T("时间", "At")}</th><th class="l"></th></tr></thead><tbody>{cts}</tbody></table></div>' if cts else "")
                + (f'<h4>{T("交易场所", "Markets")}</h4><div class="scroll"><table><thead><tr><th class="l">{T("场所", "Venue")}</th><th class="l">{T("链", "Chain")}</th><th class="l">{T("交易对", "Pair")}</th><th class="l">{T("池子 ID", "Pool ID")}</th><th>{T("流动性", "Liquidity")}</th><th class="l">{T("观测", "Observed")}</th><th class="l">{T("身份", "Identity")}</th></tr></thead><tbody>{mks}</tbody></table></div>' if mks else "")
                + (f'<h4>{T("研究记录（未复核）", "Research notes (not re-verified)")}</h4><ul>{nts}</ul>' if nts else ""))
        rows.append(f'<details class="lib" id="{lib_anchor(x["rid"])}" data-q="{esc(hay)}" data-seg="{x["segment"]}" data-pt="{esc(x["pt"])}" data-pool="{x["pool"]}">'
                    f'<summary><span class="nm"><b>{esc(x["name"])}</b><small>{esc(" · ".join(x["chains"][:3]))}{" …" if len(x["chains"]) > 3 else ""}</small></span>'
                    f'<span class="c2"><span class="chip{pt_tone.get(x["pt"], "")}">{esc(ptn(x["pt"]))}</span></span><span class="c3 muted">{esc(seg_name(x["segment"]))}</span>'
                    f'<span class="c4 muted" style="font-size:12px">{T("主库", "Main") if x["pool"] == "main" else T("发现", "Disc.")} · {fmt_t(x.get("first_seen"))}</span></summary><div class="bd">{body}</div></details>')
    js = """<script>(function(){const q=document.getElementById('libq'),s=document.getElementById('libseg'),p=document.getElementById('libpt'),o=document.getElementById('libpool'),n=document.getElementById('libn');
const rs=[...document.querySelectorAll('details.lib')];function f(){const t=q.value.trim().toLowerCase();let k=0;rs.forEach(r=>{const ok=(!t||r.dataset.q.includes(t))&&(!s.value||r.dataset.seg===s.value)&&(!p.value||r.dataset.pt===p.value)&&(!o.value||r.dataset.pool===o.value);r.hidden=!ok;if(ok)k++});n.textContent=k+' / '+rs.length}
[q,s,p,o].forEach(e=>e.addEventListener('input',f));f();const h=location.hash&&document.getElementById(location.hash.slice(1));if(h&&h.tagName==='DETAILS'){h.open=true;h.scrollIntoView()}})();</script>"""
    return summ + note + fl + f'<div class="card" style="padding:4px 10px">{"".join(rows)}</div>', js

def build_rwa():
    d = G.get("RWA") or {}
    desc = T("RWA 现实资产板块：代币化国债、黄金、股票、信贷的规模，RWA 协议的手续费、协议收入和持有人收入，平台币身份，研究标的判断卡。不是买卖建议。",
             "RWA board: size of tokenized treasuries, gold, stocks and credit; RWA protocol fees, revenue and holder revenue; platform-token identity; research judgment cards. Not trade advice.")
    emit("rwa/index.html", T(f"RWA · {BRAND}", f"RWA · {BRAND_EN}"), rwa_head("") + rwa_board(d), active="rwa", desc=desc, extra_head=RWA_CSS)
    emit("rwa/watch/index.html", T(f"研究标的 · RWA · {BRAND}", f"Watchlist · RWA · {BRAND_EN}"), rwa_head("watch/") + rwa_watch(d), active="rwa", desc=desc, extra_head=RWA_CSS)
    lib = rwa_library()
    lib_html, lib_js = lib if isinstance(lib, tuple) else (lib, "")
    emit("rwa/library/index.html", T(f"研究库 · RWA · {BRAND}", f"Library · RWA · {BRAND_EN}"), rwa_head("library/") + lib_html, active="rwa", desc=desc, extra_head=RWA_CSS, scripts=lib_js)
    zh_only = ZH_ONLY if LANG["v"] == "en" else ""
    for p, fn in (("method/", "方法框架.md"), ("progress/", "研究进度.md")):
        src = open(os.path.join(ROOT, "rwa", "research", fn), encoding="utf-8").read()
        name = next(T(zh, en) for q, zh, en, _, _ in RWA_TABS if q == p)
        emit(f"rwa/{p}index.html", T(f"{name} · RWA · {BRAND}", f"{name} · RWA · {BRAND_EN}"),
             rwa_head(p) + zh_only + f'<div class="article alpha-doc">{core_md(src)}</div>', active="rwa", desc=desc)


def leg_src(fn="leg_latest.json"):
    """数据文件链接带 ?v=<asof>（设计稿要求）；页面 / 卡片由 leg.js 取数渲染，停更判断在浏览器里按当天日期算。"""
    return f'/data/{fn}?v={esc((G.get("LEG") or {}).get("asof") or G["今天"])}'


LEG_SCALE_FROM = "2017-08-17"   # 卡片刻度只用币安时代已走完的腿（和实时读数同一数据源）


def leg_scale():
    """卡片刻度（大叔 11-14 定）：按 L2 当前状态选同阶段的历史腿（偏多 → 牛市阶段，偏空 → 熊市阶段；和「结合短期」同一口径），
    2017-08 起已走完的腿，给天数 / 幅度分位。写进 site/data/leg_latest.json 的 site_scale，leg.js 画刻度；不足 10 条不给。"""
    l2, hist = G.get("L2"), load(os.path.join(DATA, "leg", "leg_history.json"))
    code = ((l2 or {}).get("state") or {}).get("code")
    if not code or code not in R.L2_STATES or not hist:
        return None
    reg = "bull" if code in L2_BULLISH else "bear"
    out = {"phase": reg, "l2": {"code": code, "zh": R.L2_STATES[code][0], "en": R.L2_STATES[code][1]}, "from": LEG_SCALE_FROM,
           "note": "按 L2 当前状态选同阶段历史腿；阶段按价格周期事后划分（腿按终点日归类）；只是位置刻度，不是信号"}
    q = lambda v: {k: round(_qs(v, p), 1) for k, p in (("p25", .25), ("p50", .5), ("p75", .75), ("p90", .9))} | {"max": round(max(v), 1)}
    # 页面上说「比 N 条里的 M 条走得久 / 跌得深」，所以把每一组的天数、幅度原样带上（几十个数）
    grp = lambda xs: {"n": len(xs), "days": q([x["days"] for x in xs]), "pct": q([abs(x["pct"]) for x in xs]),
                      "days_all": sorted(x["days"] for x in xs), "pct_all": sorted(round(abs(x["pct"]), 1) for x in xs)}
    for d in ("up", "down"):
        xs = [x for x in hist.get("legs") or [] if x["dir"] == d and x.get("regime") == reg and not x.get("ongoing") and x["start_date"] >= LEG_SCALE_FROM]
        if len(xs) < 10:
            continue
        out[d] = grp(xs)
    # 山寨整体：同一个 L2 阶段，指数 2018-08 起全部已走完的腿（牛熊标注借用 BTC 周期口径）
    alt = (hist.get("alt") or {})
    for d in ("up", "down"):
        xs = [x for x in alt.get("legs") or [] if x["dir"] == d and x.get("regime") == reg and not x.get("ongoing")]
        if len(xs) >= 10:
            out.setdefault("alt", {"from": alt.get("index_from")})[d] = grp(xs)
    return out


def leg_assets():
    return (f'<link rel="stylesheet" href="{ASSET_URL["leg.css"]}">', f'<script src="{ASSET_URL["leg.js"]}" defer></script>')


def leg_home_card():
    return (f'<h2>{T("涨跌腿追踪 · BTC 与山寨整体", "Leg tracker · BTC & altcoins")} <a class="sub" href="{U("/leg-tracker/")}">{T("看规律说明 →", "How it works →")}</a></h2>'
            f'<div class="lg legh"><div id="leg-card" data-src="{leg_src()}" data-href="{U("/leg-tracker/")}">'
            f'<div class="card"><div class="empty">{T("读取中…", "Loading…")}</div></div></div></div>')


def leg_cycle_chart():
    """宏观页顶部「周期里的涨跌腿」（大叔 11-10 定）：BTC 价格按涨腿 / 跌腿分色，背景 = L2 周期状态。涨跌腿读 data/leg/leg_history.json，价格与状态读 l2_series（Coin Metrics 收盘）。"""
    ser, hist = G.get("L2S"), load(os.path.join(DATA, "leg", "leg_history.json"))
    if not ser or not hist or not hist.get("legs"):
        return ""
    if "LEGCHART" not in G:
        d0 = dt.date.fromisoformat(ser["start"])
        px = {(d0 + dt.timedelta(days=i)).isoformat(): v for i, v in enumerate(ser["series"].get("price") or []) if v}
        st = {(d0 + dt.timedelta(days=i)).isoformat(): v for i, v in enumerate(ser["series"].get("state") or []) if v is not None}
        legs = list(hist["legs"]) + ([hist["current"]] if hist.get("current") else [])
        up, dn = {}, {}
        for n, lg in enumerate(legs):
            a = lg["start_date"]
            b = legs[n + 1]["start_date"] if n + 1 < len(legs) else max(px)
            tgt = up if lg["dir"] == "up" else dn
            for d, v in px.items():
                if a <= d <= b:
                    tgt[d] = v
        start = "2012-01-01"
        cols = {"up": {d: v for d, v in up.items() if d >= start}, "dn": {d: v for d, v in dn.items() if d >= start},
                "st": {d: v for d, v in st.items() if d >= start}}
        G["LEGCHART"] = put_multi("leg_chart", cols)
    codes = ser.get("state_codes") or R.L2_ORDER
    short = {"BULL": ("牛市", "Bull"), "BULL_RISK": ("顶部风险", "Top risk"), "BULL_PULLBACK": ("牛市回撤", "Pullback"), "BEAR": ("熊市", "Bear"),
             "BEAR_ZONE": ("熊底区", "Bottom zone"), "RECOVERY": ("熊末→牛初", "Late bear→bull")}
    states = [{"n": T(R.L2_STATES[c][0], R.L2_STATES[c][1]), "s": T(*short.get(c, (R.L2_STATES[c][0], R.L2_STATES[c][1]))), "c": R.L2_STATES[c][4]} for c in codes]
    leg = "".join(f'<span><i style="background:var(--{R.L2_STATES[c][4]})"></i>{esc(T(R.L2_STATES[c][0], R.L2_STATES[c][1]))}</span>' for c in codes)
    cur = hist.get("current") or {}
    bl = ((G.get("LEG") or {}).get("btc_leg") or {})
    segpct = {"up": {x["start_date"]: x["pct"] for x in hist["legs"] if x["dir"] == "up"},
              "down": {x["start_date"]: x["pct"] for x in hist["legs"] if x["dir"] == "down"}}
    lastpct = (bl["leg"].get("gain_pct") if bl.get("direction") == "up" else -bl["leg"]["drop_pct"]) if bl.get("leg") and bl.get("direction") in ("up", "down") else None
    mk = [{"date": cur["start_date"], "label": T("这一腿起点", "current leg start")}] if cur.get("start_date") else []
    cfg = {"v2": True, "src": G["LEGCHART"], "fmt": "price", "log": True, "ranges": ["1Y", "3Y", "CYC", "ALL"], "range": "1Y", "cyc": G.get("CYC"),
           "stk": "st", "states": states, "markers": mk, "gaps": True, "last": False, "novals": True, "h": 360,
           "zoom": True, "stateLabels": True, "segLabels": True,
           "note": T("可以放大缩小：用图上方的 ＋ / － / ← / → 按钮，电脑上也可以直接在图上拖选一段放大，双击复位。对数坐标。线的颜色 = 当时在涨腿还是跌腿（收盘从高 / 低点反向走出 10% 换腿，按币安收盘价切）；背景色 = 当天的 L2 周期状态。价格线画的是 Coin Metrics 收盘价（和 L2 图同源），与币安收盘每天相差零点几个百分点。",
                     "Zoom with the + / − / ← / → buttons above the chart; on desktop you can also drag across the chart to zoom in, double-click to reset. Log scale. Line colour = up-leg or down-leg at the time (a 10% reversal off a high/low switches legs, cut on Binance closes); background = the L2 cycle state of the day. The line is the Coin Metrics close (same as the L2 chart), within a few tenths of a percent of Binance."),
           "series": [{"k": "up", "n": T("涨腿", "Up-leg"), "lab": T("涨腿", "Up"), "up": True, "c": "up", "w": 1.8,
                       "lastPct": lastpct if bl.get("direction") == "up" else None, "segPct": segpct["up"]},
                      {"k": "dn", "n": T("跌腿", "Down-leg"), "lab": T("跌腿", "Down"), "c": "dn", "w": 1.8,
                       "lastPct": lastpct if bl.get("direction") == "down" else None, "segPct": segpct["down"]}]}
    return (f'<div class="card chartcard legcyc"><div class="l2leg">{T("背景色 = 周期状态（L2）：", "Background = cycle state (L2): ")}{leg}</div>' + chart_div(cfg) + '</div>')


L2_BULLISH = {"BULL", "BULL_RISK", "BULL_PULLBACK", "RECOVERY", "BEAR_ZONE"}   # 说明句用：L2 状态偏多 / 偏空（只决定拿哪一组历史腿来比）


def _qs(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def leg_short_context():
    """综合研判下面「结合短期」（大叔 11-11 定 A 方案）：只用历史数据描述 BTC 这一腿的位置和历史上可能还剩多少空间，不写买卖动作。
    同类腿 = 和当前同方向、同一类周期阶段（L2 偏多 → 历史牛市阶段的腿，偏空 → 熊市阶段；阶段按价格周期事后划分）。每天按最新数据重算。"""
    l2, hist, cur = G.get("L2"), load(os.path.join(DATA, "leg", "leg_history.json")), (G.get("LEG") or {}).get("btc_leg") or {}
    code = ((l2 or {}).get("state") or {}).get("code")
    if not code or code not in R.L2_STATES or not hist or not cur.get("leg") or cur.get("direction") not in ("up", "down"):
        return ""
    bull, d, L = code in L2_BULLISH, cur["direction"], cur["leg"]
    reg = "bull" if bull else "bear"
    same = [x for x in hist.get("legs") or [] if x["dir"] == d and x.get("regime") == reg]
    if len(same) < 10:
        return ""
    day, mag = L["day"], (L["drop_pct"] if d == "down" else L["gain_pct"])
    mags, days = [abs(x["pct"]) for x in same], [x["days"] for x in same]
    m_med, d_med = _qs(mags, .5), _qs(days, .5)
    longer = sum(1 for x in days if x < day)
    # 「还剩多少空间」只拿 2017-08 起（币安时代，和实时读数同一数据源）的同类腿比：2010～2013 年的腿幅度大得多，会把空间算大
    recent = [abs(x["pct"]) for x in same if x["start_date"] >= "2017-08-17"]
    reached = [m for m in recent if m >= mag]
    phase = T("牛市阶段", "bull-phase") if bull else T("熊市阶段", "bear-phase")
    sname = T(R.L2_STATES[code][0], R.L2_STATES[code][1])
    lines = []
    if bull != (d == "up"):
        lines.append(T(f"长期周期在「{sname}」，短期在{'跌腿' if d == 'down' else '涨腿'}：两者不矛盾，{phase}里{'跌腿' if d == 'down' else '涨腿'}很常见（历史 {len(same)} 条）。",
                       f"The cycle is \"{sname}\" while the short-term leg is {'down' if d == 'down' else 'up'}: no contradiction; such legs are common in {phase} markets ({len(same)} in history)."))
    if d == "down":
        lines.append(T(f"现在是跌腿第 {day} 天，最深 −{mag:.1f}%。{phase}跌腿的中位是 {d_med:.0f} 天、−{m_med:.1f}%：这一条的时长比 {len(same)} 条里的 {longer} 条都长，跌幅只比其中 {sum(1 for m in mags if m < mag)} 条深。",
                       f"Day {day} of a down-leg, at most −{mag:.1f}%. The {phase} median is {d_med:.0f} days and −{m_med:.1f}%: this one is longer than {longer} of {len(same)}, but deeper than only {sum(1 for m in mags if m < mag)}."))
        if len(reached) >= 10:
            f50, f25, f75 = _qs(reached, .5), _qs(reached, .25), _qs(reached, .75)
            lines.append(T(f"2017 年以来{phase}里跌到这个深度的 {len(reached)} 条，最终跌幅中位 −{f50:.1f}%（一半在 −{f25:.1f}% 到 −{f75:.1f}% 之间）。"
                           f"按这个中位，这一腿还有约 {max(0, f50 - mag):.0f} 个百分点的下跌空间（一半情况在 {max(0, f25 - mag):.0f}～{max(0, f75 - mag):.0f} 个百分点）。",
                           f"Since 2017, the {len(reached)} {phase} down-legs that fell this far ended at a median of −{f50:.1f}% (half between −{f25:.1f}% and −{f75:.1f}%). "
                           f"At that median, about {max(0, f50 - mag):.0f} more points of downside (half the time {max(0, f25 - mag):.0f}–{max(0, f75 - mag):.0f})."))
    else:
        p75m, p75d = _qs(mags, .75), _qs(days, .75)
        tier = (T("属于涨得多、走得久的那一档", "in the big-and-long bracket") if mag > p75m and day > p75d else
                T("涨幅属于偏大的那一档", "a large move") if mag > p75m else T("时长属于偏久的那一档", "a long-running leg") if day > p75d else
                T("还在常见范围内", "still within the usual range"))
        lines.append(T(f"现在是涨腿第 {day} 天，+{mag:.1f}%。{phase}涨腿的中位是 {d_med:.0f} 天、+{m_med:.1f}%，前四分之一是 {p75d:.0f} 天以上、+{p75m:.1f}% 以上：这一条{tier}，时长比 {len(same)} 条里的 {longer} 条都长。",
                       f"Day {day} of an up-leg, +{mag:.1f}%. The {phase} median is {d_med:.0f} days and +{m_med:.1f}%; the top quarter is beyond {p75d:.0f} days and +{p75m:.1f}%: this one is {tier}, longer than {longer} of {len(same)}."))
        if len(reached) >= 10:
            f50, f25, f75 = _qs(reached, .5), _qs(reached, .25), _qs(reached, .75)
            lines.append(T(f"2017 年以来{phase}里涨到这个幅度的 {len(reached)} 条，最终涨幅中位 +{f50:.1f}%（一半在 +{f25:.1f}% 到 +{f75:.1f}% 之间）；"
                           f"按这个中位，从起点算还有约 {max(0, f50 - mag):.0f} 个百分点的上涨空间。收盘从高点回落 10%，这一腿就结束。",
                           f"Since 2017, the {len(reached)} {phase} up-legs that rose this far ended at a median of +{f50:.1f}% (half between +{f25:.1f}% and +{f75:.1f}%); "
                           f"at that median, about {max(0, f50 - mag):.0f} more points from the start. A 10% close-to-close pullback ends the leg."))
    note = T("只摆历史数字和位置，不是买卖建议。位置对比用 2010 年起全部同类腿；剩余空间只用 2017 年起的（早年腿的幅度大得多）。牛 / 熊阶段按价格周期事后划分，只用来归类历史腿；同类腿不到 10 条时不写。",
             "Historical numbers and position only, not trading advice. Position uses all comparable legs since 2010; remaining room uses legs since 2017 only (early legs were far larger). Bull/bear phases are assigned after the fact; skipped below 10 comparable legs.")
    body = "".join(f"<p>{esc(x)}</p>" for x in lines)
    return (f'<div class="lg"><div class="legbridge"><div class="lbt"><span class="hz">{T("结合短期", "Short-term context")}</span>'
            f'{T("BTC 这一腿在历史里的位置", "Where the current BTC leg sits in history")}</div>{body}<span>{esc(note)}</span></div></div>')


def leg_macro_card():
    """宏观页最上面（四层综合研判之上）：涨腿追踪 + 山寨窗口卡（同首页卡片，leg.js 渲染）。"""
    return (f'<div class="lg legh legm"><div class="legm-h"><span class="hz">{T("长期周期 × 短期波段", "Long-term cycle × short-term swings")}</span>{T("周期里的涨跌腿", "Legs inside the cycle")}'
            f'<a class="sub" href="{U("/leg-tracker/")}">{T("看规律说明 →", "How it works →")}</a></div>'
            + leg_cycle_chart()
            + f'<div class="hzrow"><span class="hz">{T("短期 · 波段", "Short term · swings")}</span>{T("按天看：BTC 和山寨整体这一波在涨还是在跌、走了多久，一条腿通常一到两周", "In days: whether BTC and altcoins are in an up- or down-leg and for how long; a leg usually lasts one to two weeks")}</div>'
            f'<div id="leg-card" data-src="{leg_src()}" data-href="{U("/leg-tracker/")}">'
            f'<div class="card"><div class="empty">{T("读取中…", "Loading…")}</div></div></div></div>')


def build_leg_tracker():
    """/leg-tracker/：设计稿 PAGE B。骨架在这里，文案 / 统计数字 / 当前读数由 leg.js 填。"""
    cr = crumbs([(T("宏观仪表盘", "Macro"), "/macro/"), (T("涨跌腿追踪", "Leg Tracker"), None)])
    tags = {k: f'<span class="tag {c}" data-i18n="tag_{k}"></span>' for k, c in (("ver", "ver"), ("desc", "desc"), ("hyp", "hyp"), ("fals", "fals"))}
    body = f"""{cr}
<div class="lg" id="leg-page" data-src="{leg_src()}" data-hist="{leg_src("leg_history.json")}">
<div class="ph"><div><div class="eyebrow">Leg Tracker</div><h1 data-i18n="h1">{T("涨跌腿追踪", "Leg Tracker")}</h1></div></div>
<p class="lead" data-i18n="lead"></p>
<div class="callout" data-i18n="callout"></div>
<nav class="chips" id="legChips"></nav>
<div id="liveMount"></div>
<section class="blk" id="how"><h2 data-i18n="how_h"></h2><ul class="plain" data-i18n="how_ul"></ul><p class="small" id="scaleNote"></p></section>
<section class="blk" id="def"><h2 data-i18n="def_h"></h2><div data-i18n="def_body"></div></section>
<section class="blk" id="len"><h2><span data-i18n="len_h"></span>{tags["desc"]}</h2><p data-i18n="len_p1"></p>
<div class="sw"><div id="lenPinMount"></div><div class="strip"><i style="width:25%"></i><i style="width:25%"></i><i style="width:25%"></i><i style="width:15%"></i><i style="width:10%"></i></div></div>
<div class="chipgrid" id="lenChips"></div><div class="live" id="lenLive" style="display:none"></div><p class="muted small" data-i18n="len_p2"></p></section>
<section class="blk" id="dd"><h2><span data-i18n="dd_h"></span>{tags["desc"]}</h2><p data-i18n="dd_p1"></p>
<div id="ddMeter"></div><div class="legendline" id="ddLegend"></div><div class="live" id="ddLive" style="display:none"></div><p class="muted small" data-i18n="dd_p2"></p></section>
<section class="blk" id="hist"><h2><span data-i18n="hist_h"></span>{tags["desc"]}</h2><div id="histMount"></div></section>
<section class="blk" id="l89"><h2><span data-i18n="l89_h"></span>{tags["hyp"]}</h2><p data-i18n="l89_p1"></p><div class="bars" id="l89Bars"></div>
<p class="muted small" data-i18n="l89_pre"></p><p data-i18n="l89_p2"></p><div class="callout" data-i18n="l89_falsify"></div></section>
<section class="blk" id="d45"><h2><span id="d45H"></span>{tags["hyp"]}</h2><p id="d45P1"></p><div class="bars" id="d45Bars"></div>
<p class="muted small" id="d45Exc"></p><p id="d45P2"></p><div class="callout" id="d45F"></div></section>
<section class="blk" id="false"><h2><span data-i18n="f_h"></span>{tags["fals"]}</h2><p data-i18n="f_intro"></p>
<h3 data-i18n="f1_h"></h3><table class="t" id="f1Table"></table><p data-i18n="f1_p"></p><h3 data-i18n="f2_h"></h3><p data-i18n="f2_p"></p><p class="muted small" data-i18n="f3_p"></p></section>
<section class="blk" id="method"><h2 data-i18n="m_h"></h2><ul class="plain" data-i18n="m_ul"></ul><p class="small muted" id="statsAsof"></p>
<p class="small">{tags["ver"]} <span class="muted" data-i18n="lg_ver"></span><br>{tags["desc"]} <span class="muted" data-i18n="lg_desc"></span><br>
{tags["hyp"]} <span class="muted" data-i18n="lg_hyp"></span><br>{tags["fals"]} <span class="muted" data-i18n="lg_fals"></span></p></section>
<div class="foot" data-i18n="disclaimer"></div>
</div>
<noscript><p class="muted">{T("这一页需要开启 JavaScript。", "This page needs JavaScript.")}</p></noscript>"""
    css, js = leg_assets()
    emit("leg-tracker/index.html", T(f"涨跌腿追踪 · {BRAND}", f"Leg Tracker · {BRAND_EN}"), body, active="macro", narrow=True,
         extra_head=css, scripts=js,
         desc=T("比特币每一条涨腿、跌腿走了多久、涨跌了多少，放到同一周期阶段的历史里看在什么位置：历史规律和当前读数。",
                "How long each BTC up- and down-leg lasts and how far it goes, compared with legs from the same cycle phase: historical patterns and current readings."))


AGENT_DIR = os.path.join(ROOT, "public", "ai-agent", "monitor")      # tools/agent-id 的导出目录（交接包原样）
AGENT_METRICS = [  # 键、中文、英文、格式、覆盖范围
    ("cumulative_ids", "累计 Agent ID", "Cumulative Agent IDs", "int", "reg"),
    ("new_ids", "当日新增 Agent ID", "New Agent IDs", "int", "reg"),
    ("trading_addresses", "当日交易地址", "Trading addresses", "int", "pad"),
    ("volume_bnb", "当日曲线成交额", "Curve volume", "bnb", "pad"),
    ("new_launches", "当日新发币", "New launches", "int", "pad"),
    ("graduated", "当日毕业币", "Graduations", "int", "pad"),
]


def agent_id_body(cr):
    """AI Agent · 币安 Agent ID 子页：六项核心数据（交接包 tools/agent-id 导出的 core_series.json）。cr = 页头（面包屑 + 标签页）。"""
    src = os.path.join(AGENT_DIR, "core_series.json")
    d = load(src)
    if not d or not d.get("rows"):
        return cr + empty_state("pending", T("币安 Agent ID · 等待数据", "Binance Agent ID · awaiting data"), T("tools/agent-id 导出后显示。", "Shown after tools/agent-id exports data."), "")
    # 原始客户页与数据一并发布，方便核查下载
    dst = os.path.join(SITE, "ai-agent", "monitor")
    if LANG["v"] == "zh" and os.path.isdir(AGENT_DIR):
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(AGENT_DIR, dst, ignore=shutil.ignore_patterns(".*"))
    health = load(os.path.join(AGENT_DIR, "health.json")) or {}
    rows = d["rows"]
    num = lambda v: None if v is None or v == "" else float(v)
    dates = [r["date"] for r in rows]
    thru = d.get("data_through_utc") or dates[-1]
    yday = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    lag = (dt.date.fromisoformat(yday) - dt.date.fromisoformat(thru)).days
    plats = " / ".join(health.get("complete_platforms") or ["AgentPad"])
    scope = {"reg": T("完整注册表", "Full registry"), "pad": T("已核平台", "Verified platforms")}  # 平台全名在页头说明里，卡片上只放短标签
    cards, charts = "", ""
    for k, zh, en, f, sc in AGENT_METRICS:
        vals = [num(r.get(k)) for r in rows]
        cur, prev = vals[-1], (vals[-2] if len(vals) > 1 else None)
        fmt = (lambda v: "U" if v is None else ((f"{v:.6f}".rstrip("0").rstrip(".") or "0") + " BNB" if v < 1 else f"{v:,.2f} BNB")) if f == "bnb" else (lambda v: "U" if v is None else f"{v:,.0f}")
        chg = ""
        if cur is not None and prev is not None and k != "cumulative_ids":
            dv = cur - prev
            chg = T("较前一日 ", "vs prior day ") + (("+" if dv > 0 else "") + (f"{dv:,.6f}".rstrip("0").rstrip(".") if f == "bnb" else f"{dv:,.0f}"))
        elif k == "cumulative_ids" and cur is not None and prev is not None:
            chg = T("较前一日 ", "vs prior day ") + f"+{cur - prev:,.0f}"
        cards += (f'<div class="glass hero"><div class="k">{esc(T(zh, en))} <span class="chip{" t-warn" if sc == "pad" else ""}">{esc(scope[sc])}</span></div>'
                  f'<div class="v" style="font-size:22px">{fmt(cur)}</div><div class="s">{esc(chg)}</div></div>')
        path = write_data(f"ai-agent/{k}.json", dates, {"v": {r["date"]: num(r.get(k)) for r in rows}})
        charts += (f'<div class="card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-size:15px">{esc(T(zh, en))} <span class="sub" style="font-weight:400;color:var(--muted)">{esc(scope[sc])}</span></h3>'
                   + chart_div({"src": path, "fmt": "bnb" if f == "bnb" else "int", "ranges": ["7D", "1M", "ALL"], "range": "ALL", "group": "aiagent", "gaps": True, "h": 200,
                                "zero": True, "series": [{"k": "v", "n": T(zh, en), "c": "s1", "area": True}]}) + '</div>')
    stale = (f' <span class="chip t-warn">{T(f"已 {lag} 天未更新", f"{lag} days behind")}</span>' if lag > 1 else "")
    # 分平台：最近 7 个完整日，每家交易地址 / 成交 BNB / 新发币 / 毕业（合计里同一地址跨平台只算一次）
    PLAT = {"Gang": T("Gang（Agent ID 门禁）", "Gang (Agent ID gated)"), "Flap-AgentID": T("Flap（Agent ID 门禁币）", "Flap (Agent ID-gated tokens)"),
            "Four.meme-Agent": T("Four.meme（Agent 创建的币，买卖不限 ID）", "Four.meme (Agent-created tokens; trading not ID-gated)"), "AgentPad": "AgentPad"}
    recent = [r for r in rows if r.get("by_platform")][-7:]
    names = sorted({k for r in recent for k in r["by_platform"]}, key=lambda k: ["Gang", "Flap-AgentID", "Four.meme-Agent", "AgentPad"].index(k) if k in PLAT else 9)
    bnbf = lambda v: "U" if v is None else (lambda x: f"{x:,.2f}" if x >= 1 else (f"{x:.4f}".rstrip("0").rstrip(".") or "0"))(float(v))
    intf = lambda v: "U" if v is None else f"{v:,.0f}"
    plat_tbl = ""
    if recent:
        head = "".join(f"<th>{esc(r['date'][5:])}</th>" for r in recent)
        trs = ""
        for nm in names:
            trs += f'<tr><td colspan="{len(recent) + 1}" style="text-align:left;padding-top:10px"><b>{esc(PLAT.get(nm, nm))}</b></td></tr>'
            for key, lab, fm in (("trading_addresses", T("交易地址", "Traders"), intf), ("volume_bnb", T("成交 BNB", "BNB volume"), bnbf),
                                 ("new_launches", T("新发币", "Launches"), intf), ("graduated", T("毕业", "Graduated"), intf)):
                cells = "".join(f"<td style=\"text-align:right;font-family:var(--mono)\">{fm((r['by_platform'].get(nm) or {}).get(key)) if nm in r['by_platform'] else '—'}</td>" for r in recent)
                trs += f'<tr><td style="text-align:left;white-space:nowrap;color:var(--muted)">{lab}</td>{cells}</tr>'
        plat_tbl = (f'<h2>{T("分平台（最近 7 天）", "By platform (last 7 days)")}</h2><div class="card" style="overflow-x:auto"><table class="l3t" style="min-width:560px">'
                    f'<thead><tr><th></th>{head}</tr></thead><tbody>{trs}</tbody></table>'
                    f'<p class="tnote">{T("合计里的交易地址按地址去重，同一地址在几家都交易只算一次，所以分平台相加会大于合计。Four.meme 一行是 Agent 钱包创建的币，买卖的人不一定持有 Agent ID。", "Total traders are de-duplicated across platforms, so per-platform figures can add up to more than the total. The Four.meme row covers tokens created by Agent wallets; their traders need not hold an Agent ID.")}</p></div>')
    defs = d.get("definitions") or {}
    body = f"""{cr}<div class="ph"><div><h2 style="margin:0">{T("币安 Agent ID 生态", "Binance Agent ID ecosystem")}</h2>
<p class="lede">{T("注册、交易地址、成交额与发币的每日趋势；只发布已经结束的 UTC 完整日，拿不到完整数据的日子标 U，不当 0。", "Daily registrations, trading addresses, volume and launches. Only finished UTC days are published; days without complete data show U, never 0.")}</p></div>
<div class="stamp">{T("数据截至", "Data through")} <b>{esc(thru)}</b>{stale}<br>{TDAY(thru)}</div></div>
<div class="note">{T(f"注册量来自完整的 Agent ID 注册表；交易地址、成交额、新发币和毕业目前只覆盖已核实的 {plats}，不代表全生态。", f"Registrations come from the full Agent ID registry; trading, volume, launches and graduations cover only the verified {plats} so far, not the whole ecosystem.")}</div>
<div class="grid g3" style="margin:14px 0 22px">{cards}</div>
{plat_tbl}
<h2>{T("每日趋势", "Daily trends")}</h2><div class="grid g2">{charts}</div>
<details class="card fold" style="margin-top:18px"><summary>{T("数据范围说明", "Scope and definitions")}</summary><ul class="tnote">
<li>{T("注册量来自完整 Agent ID 注册表；它不等于币安 Agentic Wallet 总量。", "Registrations come from the full Agent ID registry; this is not the number of Binance Agentic Wallets.")}</li>
<li>{T("交易地址 = 当日实际买卖的独立地址，不含仅铸造或领取的地址；同一地址同日多笔只算一次。", "Trading addresses = unique addresses that actually bought or sold that day; mint/claim-only addresses excluded; counted once per day.")}</li>
<li>{T("成交额 = 已核平台内盘（曲线）买卖金额，按含手续费的毛额、只算 BNB 计价的币，不含二级 DEX；新发币 = 已核平台当日创建的 Agent 币；毕业 = 当日从内盘迁到 DEX。", "Volume = buys and sells on the verified platforms' bonding curves, gross of fees, BNB-quoted tokens only, excluding secondary DEX trading; launches = Agent tokens created on verified platforms that day; graduations = tokens that moved from the curve to a DEX that day.")}</li>
<li>{T("各平台怎么认 Agent 币：Gang 全平台合约强制 Agent ID 门禁；Flap 只算发币时设了 Binance Agent ID 门禁的币；Four.meme 只算合约标记为 Agent 钱包创建的币（买卖不限 ID）；AgentPad 为已核工厂。", "How each platform's Agent tokens are identified: Gang enforces the Agent ID gate on every curve; Flap counts only tokens launched with the Binance Agent ID gate; Four.meme counts tokens its contract marks as created by an Agent wallet (trading not ID-gated); AgentPad is the verified factory.")}</li>
<li>{T("所有日期为 UTC 日；U 表示没取得完整数据，图上断开；0 表示完整读取后确实为 0。", "All dates are UTC days; U = incomplete data (gap in the chart); 0 = fully read and truly zero.")}</li>
<li>{T("采集状态", "Collection status")}: {esc(health.get("collection_status") or "—")} · {T("身份对账", "Identity reconciliation")}: {esc(health.get("identity_reconciliation") or "—")} · <a href="/ai-agent/monitor/core_series.json" download>{T("下载数据", "Download data")}</a></li>
</ul></details>"""
    return body


# ---------------------------------------------------------------- AI Agent 赛道（aiagent/：总览读 data/aiagent/*；币安 Agent ID 读 public/ai-agent/monitor；功能卡 / 进度读 aiagent/research/）
AIA_TABS = [("", "赛道总览", "Overview", "冷热 · 四层 · 市值 · 时间线", "Heat · layers · market · timeline"),
            ("agent-id/", "币安 Agent ID", "Binance Agent ID", "注册 · 发行 · 交易（链上）", "Registry · launches · trading"),
            ("launchpads/", "发射台功能卡", "Launchpad cards", "18 个版本 · 功能矩阵", "18 versions · feature matrix"),
            ("research/", "研究进度", "Progress", "缺口 · 口径 · 分工", "Gaps · rules · tasks")]
AIA_LAYER_TONE = {"launch": "t-warn", "commerce": "t-up", "defai": "t-cool", "infra": "t-neutral", "identity": "t-cool", "market": "t-neutral"}
AIA_LAYER_EXTRA = {"identity": ("身份 · 注册", "Identity"), "market": ("市场 · 代币", "Market · tokens")}


def aia_head(cur):
    tabs = "".join(f'<a role="tab" href="{U("/ai-agent/" + p)}" class="tab{" on" if p == cur else ""}"><span class="tn">{T(zh, en)}</span><span class="ts">{T(dz, de)}</span></a>'
                   for p, zh, en, dz, de in AIA_TABS)
    name = next(T(zh, en) for p, zh, en, _, _ in AIA_TABS if p == cur)
    cr = crumbs([("AI Agent", "/ai-agent/" if cur else None)] + ([(name, None)] if cur else []))
    return (f'{cr}<div class="ph"><div><div class="eyebrow">AI Agent</div><h1>{T("AI Agent 赛道监控", "AI Agent sector monitor")}</h1>'
            f'<p class="lede">{T("Web3 × AI Agent 的发展和机会：赛道在变热还是变冷、钱是投机还是真在买 Agent 的服务、哪里冒出了新机制。分四层看（发行 / 服务 / 资管 / 框架），加链上身份和代币市场。只摆读数、证据和未知项，不打分排名，不是买卖建议。", "Development and opportunities in Web3 × AI agents: is the sector heating or cooling, is money speculating or actually buying agent services, where are new mechanisms appearing. Four layers (launch / commerce / DeFAI / infra) plus on-chain identity and the token market. Readings, evidence and unknowns only — no scores, no rankings, not trade advice.")}</p></div></div>'
            f'<div class="tabwrap"><nav class="tabs" role="tablist">{tabs}</nav></div>')


def aia_int(v):
    return "U" if v is None else f"{v:,.0f}"


def aia_layer_name(k):
    lay = (G.get("AIA") or {}).get("_layers") or {}
    if k in lay:
        return T(lay[k]["zh"], lay[k]["en"])
    zh, en = AIA_LAYER_EXTRA.get(k, (k, k))
    return T(zh, en)


def write_aiagent_data():
    src = os.path.join(DATA, "aiagent")
    G["AIA"] = load(os.path.join(src, "aiagent_latest.json"))
    if G["AIA"]:
        G["AIA"]["_layers"] = (load(os.path.join(ROOT, "aiagent", "aiagent_config.json")) or {}).get("layers") or {}
    G["AIA_REG"] = load(os.path.join(ROOT, "aiagent", "aiagent_registry.json")) or {}
    out = os.path.join(SITE, "data", "aiagent")
    if G["AIA"]:
        os.makedirs(out, exist_ok=True)
        for fn in ("aiagent_latest.json", "aiagent_history.json", "fees_series.json"):
            if os.path.exists(os.path.join(src, fn)):
                shutil.copyfile(os.path.join(src, fn), os.path.join(out, fn))


def aia_pct(v, base=None, minbase=1000):
    """环比：基数（前 30 天）太小不显示；None = 新。"""
    if base is not None and base < minbase:
        return '<span class="muted">—</span>'
    if v is None:
        return f'<span class="muted">{T("新", "new")}</span>'
    return f'<span style="color:var(--{"up" if v >= 0 else "dn"})">{v:+.0f}%</span>'


def aia_fees_chart(d):
    """四层逐日手续费 → 7 日滚动合计（堆叠）。"""
    fs = load(os.path.join(DATA, "aiagent", "fees_series.json")) or {}
    D, L = fs.get("d") or [], fs.get("layers") or {}
    if not D:
        return ""
    ser = {}
    for k, vals in L.items():
        roll = {}
        for i in range(6, len(D)):
            w = vals[i - 6:i + 1]
            roll[D[i]] = sum(x or 0 for x in w) if all(x is not None for x in w) else None
        ser[k] = roll
    path = write_data("aiagent/fees_layers_7d.json", D[6:], ser)
    cols = {"launch": "s3", "commerce": "s1", "defai": "s2", "infra": "s4"}
    return chart_div({"src": path, "fmt": "usd", "stack": True, "ranges": ["3M", "6M", "1Y", "ALL"], "range": "1Y", "group": "aia", "h": 280,
                      "series": [{"k": k, "n": aia_layer_name(k), "c": cols.get(k, "s5"), "area": True} for k in L]})


def aia_overview():
    d, reg = G.get("AIA") or {}, G.get("AIA_REG") or {}
    if not d:
        return '<div class="note">' + T("赛道数据还没生成（aiagent/aiagent_daily.py）。", "Sector data not generated yet.") + '</div>'
    tot, lay, mk, aid = d.get("total") or {}, d.get("layers") or {}, d.get("market") or {}, d.get("agent_id") or {}
    cats = mk.get("categories") or {}
    ag = cats.get("ai-agents") or {}
    # 读数卡
    pos = tot.get("pctile_1y")
    c1 = (f'<div class="glass hero"><div class="k">{T("赛道手续费 · 近 30 天", "Sector fees · 30d")}</div><div class="v" style="font-size:22px">{a_usd(tot.get("f30"))}</div>'
          f'<div class="s">{T("比前 30 天", "vs prior 30d")} {aia_pct(tot.get("chg30"))} · {T("去掉最高一天", "ex-peak")} {aia_pct(tot.get("chg30_ex_peak"))}'
          + (f'<br>{T(f"在过去一年的 30 天合计里高于 {pos:.0f}% 的时候", f"Above {pos:.0f}% of rolling 30d totals in the past year")}' if pos is not None else "") + '</div></div>')
    c2 = (f'<div class="glass hero"><div class="k">{T("AI Agent 代币市值", "AI Agent token market cap")} <span class="chip">CoinGecko</span></div><div class="v" style="font-size:22px">{a_usd(ag.get("mcap"))}</div>'
          f'<div class="s">{T("24 小时", "24h")} {aia_pct(ag.get("chg24h"))} · {T("发射台代币", "Launchpad tokens")} {a_usd((cats.get("ai-agent-launchpad") or {}).get("mcap"))} · {T("框架代币", "Frameworks")} {a_usd((cats.get("ai-framework") or {}).get("mcap"))}</div></div>')
    nid, pid = aid.get("new_ids_7d"), aid.get("new_ids_prev7d")
    c3 = (f'<div class="glass hero"><div class="k">{T("币安 Agent ID 累计", "Binance Agent IDs")} <span class="chip">{T("链上", "on-chain")}</span></div>'
          f'<div class="v" style="font-size:22px">{aia_int(aid.get("cumulative_ids"))}</div>'
          f'<div class="s">{T("近 7 天新增", "New in 7d")} {aia_int(nid)}'
          + (f'（{T("前 7 天", "prior 7d")} {pid:,.0f}）' if pid is not None else "")
          + f' · {T("门禁发射台近 7 天发币", "Gated-pad launches 7d")} {aia_int(aid.get("launches_7d"))} · <a href="{U("/ai-agent/agent-id/")}">{T("详情", "details")}</a></div></div>')
    # 一句话：哪层在涨、哪层在跌（只说事实）
    parts = []
    for k in ("launch", "commerce", "defai", "infra"):
        x = lay.get(k) or {}
        if x.get("f30") is None:
            continue
        ch = x.get("chg30_ex_peak") if x.get("chg30_ex_peak") is not None else x.get("chg30")
        top = (f'{T("，最大一家", ", top: ")}{esc(x.get("top") or "")} {T("占", "")}{x["top_share"]:.0f}%' if (x.get("top_share") or 0) >= 50 else "")
        parts.append(f'{aia_layer_name(k)} {a_usd(x["f30"])}（{T("去峰环比", "ex-peak")} {aia_pct(ch)}{top}）')
    line = f'<div class="card" style="padding:12px 16px;margin:0 0 14px;font-size:13.5px">{T("近 30 天手续费按层：", "30d fees by layer: ")}' + "；".join(parts) + '</div>'
    # 事件
    ev = d.get("events") or []
    EVN = {"new_protocol": T("新进名单", "Newly tracked"), "dormant": T("手续费归零", "Fees went to zero"), "spike": T("单日事件", "Single-day spike")}
    evh = ""
    if ev:
        items = "".join(f'<li><span class="chip {"t-warn" if e["type"] != "new_protocol" else "t-up"}">{EVN.get(e["type"], e["type"])}</span> <b>{esc(e["name"])}</b> <small>{aia_layer_name(e["layer"])}'
                        + (T(f" · 最高一天占近 30 天的 {e['share']:.0f}%，看去峰环比", f" · top day = {e['share']:.0f}% of 30d; use ex-peak change") if e["type"] == "spike" else "")
                        + (T(" · 前 30 天有手续费，近 30 天为 0", " · fees in prior 30d, none in last 30d") if e["type"] == "dormant" else "") + '</small></li>' for e in ev)
        evh = f'<h2>{T("今天的变化", "Today’s changes")}</h2><div class="card" style="padding:10px 16px"><ul class="plain">{items}</ul></div>'
    elif d.get("baseline_day") == (d.get("generated") or "")[:10]:
        bd = d.get("baseline_day")
        evh = f'<div class="note">{T(f"今天（{bd}）是名单第一天，全部记为基线；从明天起新收录的协议会在这里提示。", "Today is the baseline; newly tracked protocols will be flagged from tomorrow.")}</div>'
    # 四层表
    lrows = ""
    for k in ("launch", "commerce", "defai", "infra"):
        x, m = lay.get(k) or {}, (d.get("_layers") or {}).get(k) or {}
        lrows += (f'<tr><td class="l"><span class="chip {AIA_LAYER_TONE.get(k, "")}">{aia_layer_name(k)}</span><br><small>{esc(T(m.get("desc_zh", ""), m.get("desc_en", "")))}</small></td>'
                  f'<td>{a_usd(x.get("f30"))}</td><td>{aia_pct(x.get("chg30"))}</td><td>{aia_pct(x.get("chg30_ex_peak"))}</td><td>{a_usd(x.get("med30"))}</td>'
                  f'<td>{x.get("n_active", 0)} / {x.get("n", 0)}</td><td class="l">{esc(x.get("top") or "—")}' + (f' <small>{x["top_share"]:.0f}%</small>' if x.get("top_share") is not None else "") + '</td></tr>')
    ltbl = (f'<div class="tw scroll"><table><thead><tr><th class="l">{T("层", "Layer")}</th><th>{T("30 天手续费", "30d fees")}</th><th>{T("环比", "Change")}</th><th>{T("去峰环比", "Ex-peak")}</th>'
            f'<th>{T("中位日", "Median day")}</th><th>{T("活跃 / 在册", "Active / tracked")}</th><th class="l">{T("最大一家", "Largest")}</th></tr></thead><tbody>{lrows}</tbody></table></div>')
    # 协议表
    prow = ""
    for r in d.get("protocols") or []:
        if r.get("status") != "ok" or not r.get("f30"):
            continue
        small = (r.get("f30") or 0) < 1000
        nm = f'<a href="https://defillama.com/protocol/{esc(r["slug"])}" target="_blank" rel="noopener">{esc(r["name"])}</a>'
        note = T(r.get("note_zh") or "", r.get("note_en") or "")
        prow += (f'<tr><td class="l wrap" style="min-width:170px">{nm}' + (f'<div class="tnote" style="margin:2px 0 0;white-space:normal">{esc(note)}</div>' if note else "")
                 + f'</td><td class="l"><span class="chip {AIA_LAYER_TONE.get(r["layer"], "")} carry">{aia_layer_name(r["layer"])}</span></td>'
                 f'<td class="l">{"".join(chain_badge(c) for c in (r.get("chains") or [])[:3])}</td><td>{a_usd(r.get("f30"))}</td>'
                 f'<td>{aia_pct(None if small else r.get("chg30"), r.get("p30") if r.get("chg30") is not None else None)}</td>'
                 f'<td>{aia_pct(None if small else r.get("chg30_ex_peak"), r.get("p30") if r.get("chg30_ex_peak") is not None else None)}</td>'
                 f'<td>{a_usd(r.get("med30"))}</td><td>{"—" if r.get("peak_share") is None else str(round(r["peak_share"])) + "%"}</td>'
                 f'<td>{esc(r.get("first_day") or "")}</td></tr>')
    quiet = [r for r in d.get("protocols") or [] if r.get("status") != "ok" or not r.get("f30")]
    qline = "、".join(esc(r["name"]) + ("" if r.get("status") == "ok" else T("（无适配器）", " (no adapter)")) for r in quiet)
    ref = d.get("reference") or {}
    rline = " · ".join(f'{esc(T(v["name"], k))} {a_usd(v.get("f30"))}' for k, v in ref.items())
    ptbl = (f'<div class="tw scroll"><table><thead><tr><th class="l">{T("协议", "Protocol")}</th><th class="l">{T("层", "Layer")}</th><th class="l">{T("链", "Chains")}</th>'
            f'<th>{T("30 天手续费", "30d fees")}</th><th>{T("环比", "Change")}</th><th>{T("去峰环比", "Ex-peak")}</th><th>{T("中位日", "Median day")}</th><th>{T("最高一天占比", "Top-day share")}</th><th>{T("有数起", "Since")}</th></tr></thead><tbody>{prow}</tbody></table></div>'
            + (f'<p class="tnote">{T("近 30 天手续费为 0 或没有适配器：", "Zero fees in 30d or no adapter: ")}{qline}</p>' if qline else "")
            + f'<p class="tnote">{T("量级参照（全平台，不进赛道合计，也不能归给 Agent 模式）：", "Scale reference (whole platforms; not in sector totals, not attributable to agent modes): ")}{rline}</p>')
    # 市场
    crow = "".join(f'<tr><td class="l">{esc(T(v["zh"], v["en"]))}</td><td>{a_usd(v.get("mcap"))}</td><td>{a_usd(v.get("vol24h"))}</td><td>{aia_pct(v.get("chg24h"))}</td></tr>' for v in cats.values())
    topn = mk.get("top") or []
    ts = mk.get("top_share") or {}
    trow = "".join(f'<tr><td class="rk">{i}</td><td class="l"><b>{esc(x["symbol"])}</b> <small>{esc(x["name"])}</small></td><td>{a_usd(x.get("mcap"))}</td><td>{aia_pct(x.get("chg7d"))}</td><td>{aia_pct(x.get("chg30d"))}</td>'
                   f'<td>{aia_pct(x.get("ath_chg"))}</td></tr>' for i, x in enumerate(topn[:10], 1))
    market = (f'<h2 id="market">{T("代币市场", "Token market")} <span class="sub">CoinGecko · {T("快照", "snapshot")} {TT(mk.get("snapshot_utc"))}</span></h2>'
              f'<div class="grid g2"><div class="tw scroll"><table><thead><tr><th class="l">{T("分类", "Category")}</th><th>{T("市值", "Market cap")}</th><th>{T("24h 成交", "24h volume")}</th><th>24h</th></tr></thead><tbody>{crow}</tbody></table></div>'
              f'<div class="tw scroll"><table><thead><tr><th>#</th><th class="l">{T("AI Agent 分类市值前十", "Top 10 in AI Agents")}</th><th>{T("市值", "Mcap")}</th><th>7d</th><th>30d</th><th>{T("距最高", "From ATH")}</th></tr></thead><tbody>{trow}</tbody></table></div></div>'
              + f'<p class="tnote">{T("CoinGecko 分类是第三方归类，同一个币可以在几个分类里，成分会变。免费接口没有分类历史，所以从 2026-11-14 起每天自录一次，满 90 天前只描述、不比高低。", "CoinGecko categories are third-party groupings and overlap; constituents change. No free category history, so we self-record daily from 2026-11-14 and only describe until 90 days accrue.")}'
              + (T(f" 前 30 名里第一名占 {ts['top1']:.0f}%、前五名占 {ts['top5']:.0f}%。", f" Within the top 30, #1 holds {ts['top1']:.0f}% and the top five {ts['top5']:.0f}%.") if ts.get("top1") is not None else "")
              + f' {T("列名单只为说明分类构成，不是推荐。", "Listed only to show what the category contains; not a recommendation.")}</p>')
    # 监控地图
    ST = {"live": ("t-up", T("已接", "Live")), "pending": ("t-warn", T("待接入", "Pending"))}
    mrows = ""
    for it in reg.get("monitor_map") or []:
        tone, lab = ST.get(it["status"], ("", it["status"]))
        nm = esc(T(it["zh"], it["en"]))
        if it.get("href"):
            nm = f'<a href="{U("/ai-agent/" + it["href"]) if it["href"].startswith("#") else U(it["href"])}">{nm}</a>' if not it["href"].startswith("#agent") else f'<a href="{U("/ai-agent/agent-id/")}">{nm}</a>'
        mrows += f'<tr><td class="l"><span class="chip {AIA_LAYER_TONE.get(it["layer"], "")} carry">{aia_layer_name(it["layer"])}</span></td><td class="l wrap">{nm}</td><td class="l"><span class="chip {tone}">{lab}</span></td><td class="l wrap"><small>{esc(T(it["src"], it.get("src_en") or it["src"]))}</small></td></tr>'
    mmap = (f'<h2 id="map">{T("监控地图", "Coverage map")} <span class="sub">{T("每一层看什么、接没接", "What each layer tracks and whether it is wired")}</span></h2>'
            f'<div class="tw scroll"><table><thead><tr><th class="l">{T("层", "Layer")}</th><th class="l">{T("监控项", "Item")}</th><th class="l">{T("状态", "Status")}</th><th class="l">{T("来源 / 卡在哪", "Source / blocker")}</th></tr></thead><tbody>{mrows}</tbody></table></div>'
            f'<p class="tnote">{T("待接入的项由 Codex 核数据源、Claude 接进日更，进度见", "Pending items: Codex verifies sources, Claude wires them in; see")} <a href="{U("/ai-agent/research/")}">{T("研究进度", "Progress")}</a>。</p>')
    # 时间线
    KIND = {"launch": ("t-up", T("上线", "Launch")), "stop": ("t-dn", T("停新 / 下线", "Stopped")), "pivot": ("t-warn", T("转型", "Pivot")), "peak": ("t-cool", T("峰值", "Peak"))}
    evs = sorted(reg.get("events") or [], key=lambda e: e["date"], reverse=True)
    tl = "".join(f'<li><span class="mono" style="display:inline-block;min-width:84px">{esc(e["date"])}</span> <span class="chip {KIND.get(e["kind"], ("", ""))[0]}">{KIND.get(e["kind"], ("", e["kind"]))[1]}</span> '
                 f'<b>{esc(e["who"])}</b> {esc(T(e["zh"], e["en"]))} <small class="muted">· {esc(e["grade"])} · {esc(e["src"])}</small></li>' for e in evs)
    timeline = (f'<h2 id="timeline">{T("生命周期时间线", "Lifecycle timeline")} <span class="sub">{T("上线 / 停新 / 转型 / 峰值，只收有日期和出处的", "Launches, stops, pivots, peaks — dated and sourced only")}</span></h2>'
                f'<div class="card" style="padding:10px 16px"><ul class="plain">{tl}</ul>'
                f'<p class="tnote">{T("证据：A 官方原文或可复算链上；B 第三方数据平台；C 媒体 / 社区 / 项目自述。还有", "Evidence: A official / reproducible on-chain; B third-party data; C media / community / self-reported. ")}{len(reg.get("open_items") or [])}{T(" 条日期待核，见研究进度。", " items await date checks; see Progress.")}'
                f' {T("人工核对于", "Checked")} {esc(reg.get("checked_utc") or "—")}</p></div>')
    src_ok = all(v.get("ok") for v in (d.get("sources") or {}).values())
    foot = (f'<p class="tnote">{T("手续费数据日", "Fee data day")} {esc(d.get("asof") or "")}（{TDAY(d.get("asof"))}）· {T("生成于", "Generated")} {TT(d.get("generated"))} · '
            f'{T("来源 DefiLlama 逐日手续费、CoinGecko 分类、本站 Agent ID 链上采集", "Sources: DefiLlama daily fees, CoinGecko categories, own Agent ID collector")}{"" if src_ok else " · " + T("有数据源失败，沿用上次结果", "a source failed; last result carried")}'
            f' · <a href="/data/aiagent/aiagent_latest.json">JSON</a> · <a href="/data/aiagent/fees_series.json">{T("逐日手续费", "Daily fees")}</a></p>')
    return (f'<div class="grid g3" style="margin:14px 0 14px">{c1}{c2}{c3}</div>{line}{evh}'
            f'<h2 id="fees">{T("四层手续费", "Fees by layer")} <span class="sub">{T("7 日滚动合计，堆叠", "7-day rolling sum, stacked")}</span></h2><div class="card" style="padding:14px 16px">{aia_fees_chart(d)}</div>'
            f'<p class="tnote">{T("手续费 ≠ 收入 ≠ 服务收入：发行层的手续费反映投机热度，服务层（Agent 雇 Agent、x402 按次付费、推理额度）才接近 Agent 在卖服务，而且还没剔除自付。去峰环比 = 两个 30 天窗口各去掉最高一天再比，防止单日事件带偏；前 30 天不到 1,000 美元的不显示环比。", "Fees ≠ revenue ≠ service revenue: launch-layer fees track speculation; the commerce layer (agent hiring, x402 pay-per-call, inference credits) is closer to agents selling services, and self-payment is not yet excluded. Ex-peak change drops the highest day from each 30d window; no change shown when the prior 30d is under $1,000.")}</p>'
            + ltbl + f'<h2>{T("协议明细", "Protocols")} <span class="sub">{T("按近 30 天手续费排序", "Sorted by 30d fees")}</span></h2>' + ptbl
            + market + timeline + mmap + foot)


AIA_CARD_LIVE = {"K02": ("bnb", "Gang"), "K03": ("bnb", "Gang"), "K04": ("bnb", "Gang"), "K05": ("bnb", "AgentPad"), "K06": ("bnb", "Flap-AgentID"),
                 "K07": ("bnb", "Four.meme-Agent"), "K09": ("fee", "virtuals-protocol"), "K10": ("fee", "clanker"), "K11": ("fee", "clanker"), "K12": ("fee", "bankr")}


def aia_card_live(kid):
    """功能卡上的「本站持续读数」：BNB 门禁平台读 Agent ID 采集（近 7 天），其他读 DefiLlama 手续费（近 30 天）。"""
    m = AIA_CARD_LIVE.get(kid)
    if not m:
        return ""
    if m[0] == "bnb":
        rows = [r for r in ((load(os.path.join(AGENT_DIR, "core_series.json")) or {}).get("rows") or []) if r.get("by_platform")][-7:]
        if not rows:
            return ""
        g = lambda k: [(r["by_platform"].get(m[1]) or {}).get(k) for r in rows]
        ok = lambda xs: all(x is not None for x in xs)
        tr, vo, la, gr = g("trading_addresses"), g("volume_bnb"), g("new_launches"), g("graduated")
        s = lambda xs, f=float: "U" if not ok(xs) else f"{sum(f(x) for x in xs):,.{2 if f is float else 0}f}"
        txt = T(f"近 7 天（{rows[0]['date'][5:]}～{rows[-1]['date'][5:]}）：交易地址合计 {s(tr, int)}、成交 {s(vo)} BNB、新发币 {s(la, int)}、毕业 {s(gr, int)}",
                f"Last 7 days ({rows[0]['date'][5:]}–{rows[-1]['date'][5:]}): traders {s(tr, int)}, volume {s(vo)} BNB, launches {s(la, int)}, graduations {s(gr, int)}")
        if kid in ("K02", "K03", "K04"):
            txt += T("（Gang 全平台，未按版本拆）", " (all of Gang; not split by version)")
        return f'<div class="note" style="margin:8px 0">{T("本站链上读数", "Our on-chain reading")} · {txt}</div>'
    r = next((x for x in (G.get("AIA") or {}).get("protocols") or [] if x["slug"] == m[1]), None)
    if not r or r.get("f30") is None:
        return ""
    return (f'<div class="note" style="margin:8px 0">{T("本站持续读数", "Our daily reading")} · {T("DefiLlama 近 30 天手续费", "DefiLlama 30d fees")} {a_usd(r["f30"])}，'
            f'{T("去峰环比", "ex-peak change")} {aia_pct(r.get("chg30_ex_peak"))}（{T("全平台 / 跨版本，不归给本卡的版本", "whole platform / all versions; not attributable to this card")}）</div>')


def aia_launchpads():
    cj = load(os.path.join(ROOT, "aiagent", "research", "launchpad_cards_v2.json")) or {}
    cards, srcs = cj.get("cards") or [], cj.get("sources") or {}
    if not cards:
        return ""
    GR = {"A": "t-up", "B": "t-cool", "C": "t-warn", "U": "t-neutral"}
    feats = list(cards[0]["flags"].keys())
    CELL = {"✓": ("var(--up)", "✓"), "✗": ("var(--dn)", "✗"), "U": ("var(--muted)", "·")}
    head = "".join(f'<th title="{esc(c["name"])} · {esc(c["version"])}"><a href="#{c["id"]}">{c["id"][1:]}</a></th>' for c in cards)
    mrows = ""
    for f in feats:
        cells = ""
        for c in cards:
            v = c["flags"].get(f, "U")
            col, ch = CELL.get(v, ("var(--muted)", v))
            cells += f'<td style="text-align:center;color:{col};font-weight:600">{ch}</td>'
        nyes = sum(1 for c in cards if c["flags"].get(f) == "✓")
        mrows += f'<tr><td class="l" style="white-space:nowrap">{esc(f)} <small class="muted">{nyes}</small></td>{cells}</tr>'
    legend = " · ".join(f'<b>{c["id"]}</b> {esc(c["name"])}' for c in cards)
    matrix = (f'<h2 id="matrix">{T("功能矩阵", "Feature matrix")} <span class="sub">{T("✓ 有支持证据 · ✗ 有明确相反证据 · · 未知；数字 = 有证据支持的版本数", "✓ supported · ✗ explicitly not · · unknown; number = versions with support")}</span></h2>'
              f'<div class="tw scroll"><table class="l3t" style="min-width:880px;font-size:12.5px"><thead><tr><th class="l">{T("功能", "Feature")}</th>{head}</tr></thead><tbody>{mrows}</tbody></table></div>'
              f'<p class="tnote">{legend}</p>'
              f'<p class="tnote">{T("「强制运行验证」「创建者审核」「持币使用权」「服务退款」「改费 / 暂停权限」18 个版本全是未知——也就是说，目前没有一家能证明发出来的 Agent 真在运行、持币人有什么权利、平台能不能单方面改规则。这是整个品类最大的空白。", "Mandatory run verification, creator review, holder usage rights, service refunds and fee / pause powers are unknown for all 18 versions: no platform can yet prove its agents actually run, what holders are entitled to, or whether the platform can change rules unilaterally. The biggest blank in the category.")}</p>')
    body = ""
    for c in cards:
        params = "".join(f'<tr><td class="l" style="white-space:nowrap">{esc(k)}</td><td class="l wrap">{esc(v)}</td></tr>' for k, v in (c.get("params") or {}).items())
        fields = "".join(f'<tr><td class="l" style="white-space:nowrap">{esc(k)}</td><td class="l wrap">{esc(v)}</td></tr>' for k, v in (c.get("fields") or {}).items() if k != "基本")
        ev = "".join(f'<li><b>{esc(k)}</b> {esc(v)}</li>' for k, v in (c.get("evidence") or {}).items())
        flow = " → ".join(esc(x) for x in c.get("flow") or [])
        sl = " ".join(f'<a href="{esc(srcs[s]["url"])}" target="_blank" rel="noopener">{esc(s)}</a><small class="muted">（{esc(srcs[s]["grade"])}）</small>' for s in c.get("source_ids") or [] if s in srcs)
        body += (f'<details class="card fold" id="{c["id"]}" style="margin:0 0 10px"><summary><b>{c["id"]}</b> {esc(c["name"])} <span class="chip {GR.get(c.get("grade"), "")}">{esc(c.get("grade") or "U")}</span> '
                 f'<small class="muted">{esc(c.get("chain") or "")} · {esc(c.get("version") or "")} · {esc(c.get("category") or "")}</small><br><small>{esc(c.get("status") or "")}</small></summary>'
                 + aia_card_live(c["id"])
                 + (f'<p class="tnote" style="margin:6px 0">{T("流程", "Flow")}：{flow}</p>' if flow else "")
                 + f'<div class="grid g2"><div><h4 style="margin:8px 0 4px">{T("参数", "Parameters")}</h4><div class="tw"><table><tbody>{params}</tbody></table></div>'
                 f'<h4 style="margin:12px 0 4px">{T("三层核验", "Three-layer check")}</h4><ul class="plain" style="font-size:13px">{ev}</ul></div>'
                 f'<div><h4 style="margin:8px 0 4px">{T("功能与边界", "Functions & limits")}</h4><div class="tw"><table><tbody>{fields}</tbody></table></div></div></div>'
                 f'<p class="tnote">{T("来源", "Sources")}：{sl} · {T("读取", "Read")} {esc((c.get("utc") or "")[:10])} · {esc(c.get("read") or "")}</p></details>')
    intro = (f'<div class="note">{T("Codex《AI Agent 发射台的功能与形态》v2（研究截止 2026-11-12），18 个版本 / 模式逐个拆：创建、定价、毕业、费用分账、服务履约和权限。卡片写入即冻结，新研究另起版本；卡片上「本站读数」是网站每天的持续读数，用来补卡片里「数据 U」的部分。证据：A 官方原文或可复算链上 · B 第三方数据平台 · C 媒体 / 社区 / 摘要 · U 未知。", "Codex research “AI Agent launchpads: functions and forms” v2 (cutoff 2026-11-12): 18 versions / modes broken down by creation, pricing, graduation, fee split, service delivery and permissions. Cards are frozen; the “our reading” lines are the site’s daily readings, filling the cards’ “data U”. Evidence: A official / reproducible on-chain · B third-party data · C media / community / summary · U unknown.")}'
             f' <a href="{U("/reports/2026-11-12-ai-agent-launchpad-v2/")}">{T("报告全文（含附件下载）→", "Full report (with attachments) →")}</a></div>')
    zh_only = ZH_ONLY if LANG["v"] == "en" else ""
    return zh_only + intro + matrix + f'<h2 id="cards">{T("版本卡", "Version cards")} <span class="sub">{T("点开看参数、功能与边界、三层核验", "Expand for parameters, functions and checks")}</span></h2>' + body


def build_ai_agent():
    desc = T("AI Agent 赛道监控：发行 / 服务 / 资管 / 框架四层手续费、AI Agent 代币市值、币安 Agent ID 链上数据、18 个发射台功能卡和生命周期时间线。只摆读数和证据，不是买卖建议。",
             "AI Agent sector monitor: fees across launch / commerce / DeFAI / infra, AI Agent token market cap, Binance Agent ID on-chain data, 18 launchpad feature cards and a lifecycle timeline. Readings and evidence only; not trade advice.")
    title = lambda zh, en: T(f"{zh} · AI Agent · {BRAND}", f"{en} · AI Agent · {BRAND_EN}")
    emit("ai-agent/index.html", T(f"AI Agent 赛道监控 · {BRAND}", f"AI Agent Monitor · {BRAND_EN}"), aia_head("") + aia_overview(), active="aiagent", chart=True, desc=desc)
    emit("ai-agent/agent-id/index.html", title("币安 Agent ID", "Binance Agent ID"), agent_id_body(aia_head("agent-id/")), active="aiagent", chart=True,
         desc=T("币安 Agent ID 生态：累计与新增 Agent ID、交易地址、曲线成交额、新发币与毕业的每日趋势。", "Binance Agent ID ecosystem: IDs, trading addresses, curve volume, launches and graduations, daily."))
    emit("ai-agent/launchpads/index.html", title("发射台功能卡", "Launchpad cards"), aia_head("launchpads/") + aia_launchpads(), active="aiagent", desc=desc)
    src = open(os.path.join(ROOT, "aiagent", "research", "研究进度.md"), encoding="utf-8").read()
    zh_only = ZH_ONLY if LANG["v"] == "en" else ""
    emit("ai-agent/research/index.html", title("研究进度", "Progress"), aia_head("research/") + zh_only + f'<div class="article alpha-doc">{core_md(src)}</div>',
         active="aiagent", desc=desc)


def aia_home_card():
    d = G.get("AIA")
    if not d:
        return ""
    tot, lay, aid = d.get("total") or {}, d.get("layers") or {}, d.get("agent_id") or {}
    ag = ((d.get("market") or {}).get("categories") or {}).get("ai-agents") or {}
    ls = " ".join(f'<span>{aia_layer_name(k)} <b>{a_usd((lay.get(k) or {}).get("f30"))}</b> {aia_pct((lay.get(k) or {}).get("chg30_ex_peak"))}</span>' for k in ("launch", "commerce", "defai", "infra"))
    return (f'<h2>{T("AI Agent 赛道", "AI Agent sector")} <span class="sub">{T("四层手续费 · 代币市值 · 币安 Agent ID", "Fees by layer · market cap · Binance Agent ID")}</span>'
            f' <a class="sub" href="{U("/ai-agent/")}">{T("进监控 →", "Open →")}</a></h2>'
            f'<div class="card core-home"><div class="row"><span>{T("赛道手续费（30 天）", "Sector fees (30d)")} <b>{a_usd(tot.get("f30"))}</b> {aia_pct(tot.get("chg30_ex_peak"))}</span>'
            f'<span>{T("AI Agent 代币市值", "AI Agent token mcap")} <b>{a_usd(ag.get("mcap"))}</b></span>'
            f'<span>{T("币安 Agent ID", "Binance Agent IDs")} <b>{aia_int(aid.get("cumulative_ids"))}</b></span></div>'
            f'<div class="row" style="margin-top:6px">{ls}</div>'
            f'<div class="row" style="margin-top:6px;font-size:12px;color:var(--muted)">{T("环比为去掉最高一天后的 30 天环比", "Changes are 30d ex-peak")} · {T("数据日", "Data day")} {esc(d.get("asof") or "")}</div></div>')


def build_calendar():
    cal = G.get("CAL")
    cr = crumbs([(T("事件日历", "Event calendar"), None)])
    if not cal:
        body = cr + empty_state("pending", T("事件日历 · 等待首次运行", "Event calendar · awaiting first run"), T("cal/cal_daily.py 每天运行后显示。", "Shown after cal/cal_daily.py runs."), "")
        emit("calendar/index.html", T(f"事件日历 · {BRAND}", f"Event calendar · {BRAND_EN}"), body, active="calendar")
        return
    b, w = cal.get("btc") or {}, cal.get("web3") or {}
    evs = b.get("events") or []
    nxt = next((e for e in evs if e.get("emphasis") and (e.get("days_until") or 0) >= 0), None)
    big = ""
    if nxt:
        im = nxt.get("impact") or {}
        usd = T(f"按现价约 ±${im['usd_typ']:,.0f}" if im.get("usd_typ") else "", f"about ±${im['usd_typ']:,.0f} at today's price" if im.get("usd_typ") else "")
        big = (f'<div class="card calbig"><div class="eb">{T("下一个已检验事件", "Next tested event")}</div>'
               f'<div class="row1"><h3>{esc(T(nxt["title_zh"], nxt["title_en"]))}</h3>{cal_grade(nxt.get("grade"))}</div>'
               f'<div class="cd" data-utc="{esc(nxt.get("time_utc") or "")}">—</div>'
               f'<div class="tz"><b>{TT(nxt.get("time_utc"))}</b></div>'
               f'<p class="imp"><b>{T("这次大概会晃多少：", "How much it may swing: ")}</b>{esc(T(im.get("text_zh") or "", im.get("text_en") or ""))} {esc(usd)}</p>'
               f'<p class="use"><b>{T("怎么用：", "How to use it: ")}</b>{esc(T(nxt.get("use_zh") or "", nxt.get("use_en") or ""))}</p></div>')
    # 会晃多大（幅度表）
    it = b.get("impact_table") or []
    mx = max([x.get("range_2h_typ_pct") or 0 for x in it] + [x.get("range_2h_normal_pct") or 0 for x in it] + [0.1])
    rows = ""
    for x in it:
        typ, nor = x.get("range_2h_typ_pct"), x.get("range_2h_normal_pct")
        lv = x.get("level_zh") or "—"
        tone = {"大": "warn", "中": "cool", "不放大": "neutral"}.get(lv, "neutral")
        rows += (f'<tr class="{"faint" if x.get("grade") == "已证伪" else ""}"><td class="l"><b>{esc(T(x["title_zh"], x["title_en"]))}</b> {cal_grade(x.get("grade"))}</td>'
                 f'<td class="l">{tone_chip(T(lv, x.get("level_en") or lv), tone)}</td>'
                 f'<td class="l"><div class="cmp"><span class="a" style="width:{(typ or 0) / mx * 100:.0f}%"></span><em>{T("公布时", "release")} {typ}%</em></div>'
                 f'<div class="cmp"><span class="n" style="width:{(nor or 0) / mx * 100:.0f}%"></span><em>{T("平时", "normal")} {nor}%</em></div></td>'
                 f'<td>{x.get("range_2h_big_pct")}%</td><td>{x.get("range_2h_max_pct")}%</td></tr>')
    table = (f'<div class="tw"><table class="calimp"><thead><tr><th class="l">{T("事件", "Event")}</th><th class="l">{T("波动影响", "Volatility")}</th>'
             f'<th class="l">{T("公布那两小时一般差多少 vs 平时", "Typical 2h range vs normal")}</th><th>{T("十次有一次超过", "1 in 10 above")}</th><th>{T("2022 年来最大", "Max since 2022")}</th></tr></thead><tbody>{rows}</tbody></table></div>'
             f'<p class="tnote">{esc(T(b.get("impact_note_zh") or "", "“High-low range” = how far BTC’s highest trade sits above its lowest in that window, up or down. 2.7% at $80,000 is about $2,000+ of swing."))}</p>')
    # 列表
    li = ""
    for e in evs:
        im = e.get("impact") or {}
        faint = e.get("grade") == "已证伪"
        loc_d, loc_t = TLOC(e.get("time_utc")) if e.get("time_utc") else (esc((e.get("date") or "")[:10]), "")   # 中文新加坡时间 / 英文美东
        note = T("（常见说法，数据不支持）", " (a common belief the data does not support)") if faint else ""
        usd = (T(f"，按现价约 ±${im['usd_typ']:,.0f}", f", about ±${im['usd_typ']:,.0f} at today's price") if im.get("usd_typ") else "")
        src = f' · <a href="{esc(e["source_url"])}" target="_blank" rel="noopener">{T("官方来源", "official source")} ↗</a>' if e.get("source_url") else ""
        li += (f'<details class="calrow{" faint" if faint else ""}"><summary><span class="d">{loc_d}</span><span class="t">{loc_t}</span>'
               f'<b>{esc(T(e["title_zh"], e["title_en"]))}{note}</b>{cal_grade(e.get("grade"))}<span class="lv">{esc(T(im.get("level_zh") or "—", im.get("level_en") or "—"))}</span>'
               f'<em>{T(str(e.get("days_until")) + " 天后", "in " + str(e.get("days_until")) + "d")}</em></summary>'
               f'<div class="body"><p>{esc(T(im.get("text_zh") or "", im.get("text_en") or ""))}{esc(usd)}</p><p>{esc(T(e.get("what_zh") or "", e.get("what_en") or ""))}</p>'
               f'<p><b>{T("怎么用：", "How to use it: ")}</b>{esc(T(e.get("use_zh") or "", e.get("use_en") or ""))}{src}</p></div></details>')
    # 方法表（按类型取一条的 stats）
    seen, mrows = set(), ""
    for e in evs:
        st = e.get("stats") or {}
        if e["type"] in seen or not st:
            continue
        seen.add(e["type"])
        pct = lambda v: "—" if v is None else f"{v * 100:.0f}%"
        mrows += (f'<tr><td class="l">{esc(T(e["title_zh"], e["title_en"]))}</td><td>{st.get("n", "—")}</td><td>{st.get("h2_ratio", "—")}</td><td>{pct(st.get("h2_share"))}</td>'
                  f'<td>{st.get("day_ratio", "—")}</td><td>{st.get("pre3_ratio", "—")}</td><td>{pct(st.get("up1_share"))}</td></tr>')
    method = (f'<details class="raw l3d"><summary>{T("方法与检验结果", "Method & test results")}</summary><p class="tnote">{esc(T(b.get("method_zh") or "", "Control: same weekday, within ±9 weeks, no other event, same time window. Range = high ÷ low. Eras 2015-17, 2018-21 and 2022-26 tested separately. Option expiry: Deribit, last Friday of the month, 08:00 UTC. Data: Coinbase BTC-USD hourly."))}'
              f' {esc(T(b.get("stats_asof_zh") or "", ""))}</p>'
              f'<div class="tw"><table><thead><tr><th class="l">{T("事件（2022 年以来）", "Event (since 2022)")}</th><th>{T("次数", "n")}</th><th>{T("2 小时振幅 ÷ 平时", "2h range ÷ normal")}</th><th>{T("放大比例", "share wider")}</th>'
              f'<th>{T("当天 ÷ 平时", "day ÷ normal")}</th><th>{T("前 3 天 ÷ 平时", "prior 3d ÷ normal")}</th><th>{T("次日上涨比例", "next day up")}</th></tr></thead><tbody>{mrows}</tbody></table></div></details>')
    btc_tab = (f'<p class="lede calintro">{esc(T(b.get("intro_zh") or "", b.get("intro_en") or ""))}</p>{big}'
               f'<h3>{T("会晃多大", "How big the swings are")}</h3>{table}<h3>{T("全部已录入事件", "All scheduled events")}</h3><div class="callist">{li}</div>{method}')
    # Web3
    wev = w.get("events") or []
    cats = w.get("categories") or []
    src_links = " · ".join(f'<a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["name"])}</a>' for s in w.get("sources") or [])
    if wev:
        TOKEN = {"代币事件", "解锁", "上所", "升级", "治理投票", "空投"}
        cat_en = {c["zh"]: c["en"] for c in cats}
        def wrow(e):
            dd = e.get("date_start") or ""
            de = e.get("date_end") or ""
            span = dd[5:] + (f" → {de[5:]}" if de and de != dd else "")
            coins = "".join(f'<span class="coin">{esc(c)}</span>' for c in e.get("coins") or [])
            grp = "token" if e.get("category") in TOKEN else "event"
            srcs = ", ".join(e.get("sources") or [e.get("source") or ""])
            return (f'<li class="w3 imp{e.get("importance", 1)}" data-g="{grp}" data-imp="{e.get("importance", 1)}" data-coins="{esc(" ".join(e.get("coins") or []).lower())}">'
                    f'<span class="d">{esc(span)}</span><span class="cat">{esc(T(e.get("category") or "", e.get("category_en") or cat_en.get(e.get("category"), "")))}</span>'
                    f'<a href="{esc(e.get("url") or "#")}" target="_blank" rel="noopener"><b>{esc(e.get("title") or "")}</b></a>{coins}'
                    f'<span class="city">{esc(e.get("city") or "")}</span><small>{esc(srcs)}</small></li>')
        ongoing = [e for e in wev if e.get("ongoing")]
        weeks = {}
        for e in wev:
            if e.get("ongoing"):
                continue
            d0 = dt.date.fromisoformat(e["date_start"])
            wk = (d0 - dt.timedelta(days=d0.weekday())).isoformat()
            weeks.setdefault(wk, []).append(e)
        lst = ""
        if ongoing:
            lst += f'<h4>{T("正在进行", "Ongoing")}</h4><ul class="w3l">{"".join(wrow(e) for e in ongoing)}</ul>'
        for wk in sorted(weeks):
            lst += f'<h4>{T(f"{wk[5:]} 这一周", f"Week of {wk[5:]}")}</h4><ul class="w3l">{"".join(wrow(e) for e in weeks[wk])}</ul>'
        filt = (f'<div class="w3f"><div class="fg"><button class="pill on" data-f="all">{T("全部", "All")}</button><button class="pill" data-f="event">{T("行业活动", "Industry events")}</button>'
                f'<button class="pill" data-f="token">{T("代币事件", "Token events")}</button></div>'
                f'<input type="search" class="w3s" placeholder="{T("按代币搜索，如 ETH", "Search a token, e.g. ETH")}"><label class="w3imp"><input type="checkbox"> {T("只看重要", "Important only")}</label></div>')
        web3_body = filt + f'<div class="w3wrap">{lst}</div>'
    else:
        web3_body = f'<div class="empty">{T("行业日历暂时取不到。", "The industry calendar is unavailable right now.")}</div>'
    web3_tab = (f'<p class="lede calintro">{esc(T(w.get("intro_zh") or "", w.get("intro_en") or ""))}</p>'
                f'<p class="tnote">{T("来源：", "Sources: ")}{src_links}</p>{web3_body}')
    upd = T("生成于 ", "Generated ") + TT(cal.get('generated_utc'))
    body = (cr + f'<div class="ph"><div><div class="eyebrow">Event Calendar</div><h1>{T("事件日历", "Event calendar")}</h1>'
            f'<p class="lede">{T("两张表分开看：比特币大事件是单独检验过波动的；Web3 行业动向只是汇总，没有做过价格检验。", "Two separate views: BTC events were individually tested for volatility; Web3 industry events are a digest with no price testing.")} <span class="tnote">{esc(upd)}</span></p></div></div>'
            f'<div class="tabwrap caltabs"><nav class="tabs" role="tablist">'
            f'<a role="tab" href="#btc" data-ct="btc" class="tab on"><span class="tn">{T("比特币大事件", "Bitcoin events")}</span><span class="ts">{T("已单独检验", "individually tested")}</span></a>'
            f'<a role="tab" href="#web3" data-ct="web3" class="tab w3t"><span class="tn">{T("Web3 行业动向", "Web3 industry")}</span><span class="ts">{T("汇总 · 未做价格检验", "digest · not price-tested")}</span></a></nav></div>'
            f'<section class="calp on" id="cal-btc">{btc_tab}</section><section class="calp w3p" id="cal-web3">{web3_tab}</section>')
    emit("calendar/index.html", T(f"事件日历 · {BRAND}", f"Event calendar · {BRAND_EN}"), body, active="calendar", scripts=CAL_JS,
         desc=T("美联储议息、CPI、非农公布前后 BTC 会晃多大（已检验），以及 Web3 行业会议与代币事件汇总。", "How much BTC swings around FOMC, CPI and payrolls (tested), plus a digest of Web3 conferences and token events."))


CAL_JS = r"""<script>
(function(){
const tabs=[...document.querySelectorAll('[data-ct]')];
function show(k){tabs.forEach(t=>t.classList.toggle('on',t.dataset.ct===k));document.querySelectorAll('.calp').forEach(p=>p.classList.toggle('on',p.id==='cal-'+k))}
tabs.forEach(t=>t.addEventListener('click',e=>{e.preventDefault();show(t.dataset.ct);history.replaceState(null,'','#'+t.dataset.ct)}));
if(location.hash==='#web3')show('web3');
const cd=document.querySelector('.calbig .cd');
function tick(){if(!cd||!cd.dataset.utc)return;const t=Date.parse(cd.dataset.utc.replace(' ','T')+':00Z')-Date.now();
 const zh=document.documentElement.lang.startsWith('zh');if(t<=0){cd.textContent=zh?'正在公布 / 已公布':'Released';return}
 const d=Math.floor(t/864e5),h=Math.floor(t%864e5/36e5),m=Math.floor(t%36e5/6e4);cd.textContent=zh?`还有 ${d} 天 ${h} 小时 ${m} 分`:`${d}d ${h}h ${m}m to go`}
tick();setInterval(tick,30000);
const wrap=document.querySelector('.w3wrap');if(!wrap)return;let g='all';
const s=document.querySelector('.w3s'),imp=document.querySelector('.w3imp input');
function apply(){const q=(s.value||'').trim().toLowerCase();wrap.querySelectorAll('li.w3').forEach(li=>{
 const ok=(g==='all'||li.dataset.g===g)&&(!q||li.dataset.coins.includes(q)||li.textContent.toLowerCase().includes(q))&&(!imp.checked||+li.dataset.imp>=2);li.style.display=ok?'':'none'});
 wrap.querySelectorAll('ul.w3l').forEach(u=>{const any=[...u.children].some(c=>c.style.display!=='none');u.style.display=any?'':'none';if(u.previousElementSibling)u.previousElementSibling.style.display=any?'':'none'})}
document.querySelectorAll('.w3f [data-f]').forEach(b=>b.addEventListener('click',()=>{g=b.dataset.f;document.querySelectorAll('.w3f [data-f]').forEach(x=>x.classList.toggle('on',x===b));apply()}));
s.addEventListener('input',apply);imp.addEventListener('change',apply);
})();
</script>"""


def build_narrative():
    """叙事埋伏 2026-11-14 并进 Alpha 雷达：旧链接留一页跳转。"""
    body = (f'<div class="ph"><div><h1>{T("叙事埋伏已并入 Alpha 雷达", "Narratives moved to Alpha Radar")}</h1></div></div>'
            f'<p><a href="{U("/alpha/")}">{T("去 Alpha 雷达 →", "Go to Alpha Radar →")}</a></p>')
    emit("narrative/index.html", T(f"Alpha 雷达 · {BRAND}", f"Alpha Radar · {BRAND_EN}"), body, active="alpha",
         extra_head=f'<meta http-equiv="refresh" content="0; url={U("/alpha/")}"><link rel="canonical" href="https://{DOMAIN}{U("/alpha/")}">')


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
        cat = " ".join(c.replace(" ", "_") for c in r["分类列表"])
        lst += (f'<a class="card rcard" data-cat="{esc(cat)}" href="{U("/reports/" + r["slug"] + "/")}"><span class="d">{esc(r["日期"])}</span><b>{esc(LF(r, "标题"))}</b>'
                f'<p>{esc(LF(r, "摘要"))}</p>{f"<div class=chips>{tags}</div>" if tags else ""}</a>')
    n = {c: sum(1 for r in ALL_REPORTS if c in r["分类列表"]) for c in REPORT_CATS}
    pills = (f'<button class="pill on" data-c="all">{T("全部", "All")}<small>{len(ALL_REPORTS)}</small></button>'
             + "".join(f'<button class="pill" data-c="{c.replace(" ", "_")}">{c}<small>{n[c]}</small></button>' for c in REPORT_CATS))
    how = T("周度节奏的深度报告：针对一个方向或议题做全方位分析，给出可以拿来做决策依据的结论。报告原样排版、跟随站点深浅色；写作当时的判断发布后不改，后续修正另起一篇。",
            "Weekly deep-dive reports: one theme analysed end to end, with conclusions usable as decision inputs. Original layout, following the site's light/dark theme. Frozen once published; corrections go in a new report.")
    zh_only = [r for r in ALL_REPORTS if not r.get("en_src") and r["kind"] != "md"]
    en_note = ('<div class="note">Reports marked 中文 are available in Chinese only for now.</div>' if LANG["v"] == "en" and zh_only else "")
    empty = '<div class="empty">' + T("第一篇报告整理好就发在这里。", "The first report will appear here.") + '</div>'
    body = f"""<div class="ph"><div><div class="eyebrow">Research Reports</div><h1>{T("分析报告", "Research reports")}</h1>
<p class="lede">{esc(how)}</p></div></div>
{en_note}
<div class="fbar" id="rcats" role="group" aria-label="{T("按分类筛选", "Filter by category")}">{pills}</div>
{f'<div class="grid g2" id="rlist">{lst}</div>' if lst else empty}
<div class="empty" id="rempty" style="display:none">{T("这个分类还没有报告，写好就发在这里。", "No reports in this category yet.")}</div>"""
    emit("reports/index.html", T(f"分析报告 · {BRAND}", f"Research reports · {BRAND_EN}"), body, active="reports", desc=how, scripts=REPORT_FILTER_JS)
    for r in ALL_REPORTS:
        cr = crumbs([(T("分析报告", "Reports"), "/reports/"), (LF(r, "标题"), None)])
        note = ZH_ONLY if LANG["v"] == "en" and not r.get("en_src") else ""
        if r["kind"] == "md":
            content = f'<div class="rbody"><div class="article">{r["html"]}</div></div>'
            scripts = ""
        else:
            # 整篇 HTML 原样放进 iframe（报告自己的样式不和站点互相干扰）；浅色用原文，深色用构建时自动换色的副本
            pdf = report_pdf(r, LANG["v"])
            dl = (f'<a class="btn-dl" href="report.pdf" download="uncleonchain-{r["slug"]}{".en" if pdf and pdf.endswith(".en.pdf") else ""}.pdf">'
                  f'{T("下载 PDF", "Download PDF")}</a>' if pdf else "")
            content = (f'<p class="tnote rtools">{dl}<a id="rf-open" href="raw.html" target="_blank" rel="noopener">{T("在新窗口全屏阅读 ↗", "Open full screen ↗")}</a></p>'
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


def report_pdf(r, lang):
    """content/reports/pdf/ 里这篇报告该给哪种语言的 PDF（只有浅色版，pipeline/出报告PDF.py 生成）；英文缺就给中文。"""
    d = os.path.join(REPORTS, "pdf")
    for name in ([r["slug"] + ".en.pdf"] if lang == "en" else []) + [r["slug"] + ".pdf"]:
        if os.path.exists(os.path.join(d, name)):
            return os.path.join(d, name)
    return None


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
            pdf = report_pdf(r, lang)
            if pdf:
                shutil.copyfile(pdf, os.path.join(base, "report.pdf"))


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
    if obj.get("类型") == "日" and d and d <= "2026-10-11" and not obj.get("L3"):
        notes.append(T("本篇的 L3 按 2026-10-11 之前的旧规则（交易所 7 日净流量）写成", "L3 in this entry follows the pre-2026-10-12 rule (7-day exchange net flow)"))
    if not notes:
        return ""
    return f'<div class="note">{esc("；".join(notes) if LANG["v"] == "zh" else "; ".join(notes))}{T("。按冻结规则保持原样，规则变更见", ". Kept as written under the freeze rule; see ")}<a href="{U("/corrections/")}">{T("更正记录", "Corrections")}</a>{T("。", ".")}</div>'


RULE_SEP = [("2026-10-02", "规则变更：L1 宏观层重建，此前日志按旧规则", "Rule change: L1 rebuilt; earlier logs follow the old rules"),
            ("2026-10-04", "规则变更：L1-B 加密资金通道修订", "Rule change: L1-B crypto funding channels revised"),
            ("2026-10-12", "规则变更：L3 筹码层重做（压力区位置 + 大波动预警），此前的 L3 结论按交易所 7 日净流量", "Rule change: L3 rebuilt (pressure-zone position + large-move warning); earlier L3 verdicts follow 7-day exchange net flow"),
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
        patch = (f'<p class="tnote">⚠ {T("本篇为补录：首次生成于", "Re-run: first generated")} {TT(lg.get("首次生成UTC"))}'
                 f'{T("，当天数据源晚到后按冻结规则覆盖一次。", ", overwritten once after late data per the freeze rule.")}</p>') if lg.get("补录") else ""
        heroes, cards = hero_cards(S, lg["日期"], sd if lg is logs[-1] else None)
        share_obj = {"title": T(f"链上终端 · {lg['日期']} 解读", f"Onchain terminal · {lg['日期']}"), "date": lg["日期"], "sub": LF(lg["综合"], "一句话"),
                     "html": share_payload_home(lg.get("综合"), cards, lg.get("预警")), "file": f"uncleonchain-journal-{lg['日期']}.png"}
        no_cm = empty_state("none", T("今天没有人工点评", "No hand-written note today"), T("上面是规则化自动解读。", "The above is rule-based."), "")
        pager_prev = f'<a href="{U("/journal/" + prev_ + "/")}">← {prev_}</a>' if prev_ else '<span></span>'
        pager_next = f'<a href="{U("/journal/" + next_ + "/")}">{next_} →</a>' if next_ else '<span></span>'
        body = f"""{crumbs([(T("解读日志", "Journal"), "/journal/"), (lg["日期"], None)])}
<div class="ph"><div><div class="eyebrow">Daily Log · {T("每日解读", "daily")}</div><h1>{lg["日期"]} {T("解读日志", "log")}</h1></div>
<div class="stamp">{T("解读生成", "Log generated")} <b>{TT(lg["生成时间UTC"])}</b><br>{T("写入即冻结 · 规则见「口径与规则」", "Frozen once written · rules in Methodology")}</div></div>
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
<p class="lede keep">{rv["起"]} ~ {rv["止"]} · {T("期间日志", "logs")} {rv["日志天数"]} {T("篇", "")}</p></div><div class="stamp">{T("生成于", "Generated")} <b>{TT(rv["生成时间UTC"])}</b></div></div>
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
        row = (f'<li class="{"same" if same else ""}"><span class="d">{lg["日期"]}<small>{T("生成", "gen.")} {TT(lg.get("生成时间UTC"))}</small></span>'
               f'<span><a href="{U("/journal/" + lg["日期"] + "/")}">{esc(line)}</a>'
               f'{" <em class=samel>" + T("同前一日", "same as the day before") + "</em>" if same else ""}<span class="s">{chips}</span></span>'
               f'<span class="x chip">{len(lg.get("预警") or [])} {T("条预警", "alerts")}</span></li>')
        seps = list(RULE_SEP)
        if (lg.get("综合") or {}).get("规则") == "四层合成" and not ((prev or {}).get("综合") or {}).get("规则") == "四层合成":
            seps.append((lg["日期"], "规则变更：综合研判改为四层合成，此前日志只由 L1 和 L4 组合", "Rule change: the overall read now combines all four layers; earlier logs combined only L1 and L4"))
        for d, zh, en in seps:
            pd_ = place.get(d, d)
            anc = "2026-10-08-comp" if "四层合成" in zh else ("2026-10-11-l3" if "L3" in zh else d)
            rid = anc
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
<p class="lede">{T(f"日更每天{TT(MAIN_TIME, False)}定时运行（推送代码时也会额外跑一次），按「口径与规则」里公开的规则写一篇解读日志：综合研判（四层合成）、四层读数、发射台、异动预警。<b>写入即冻结</b>——历史日志不改，唯一例外是当天数据源晚到、重跑后核心缺失变少，会覆盖一次并标「补录」。每周一出上一周的周复盘，每月 1 日出上个月的月复盘。规则变更的日子在列表里有分隔行。",
                   f"The daily run at {TT(MAIN_TIME, False)} (plus an extra run whenever code is pushed) writes a rule-based log from the public rules in Methodology: the overall read, four-layer readings, launchpads and alerts. <b>Frozen once written</b> — the only exception is a same-day re-run with fewer missing core inputs, marked 'Re-run'. Weekly reviews come out on Mondays, monthly ones on the 1st. Rule-change days are marked in the list.")}</p></div></div>
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
    p1 = T("综合研判按研究里定下的分工四层合成：<b>L2 给方向的底色</b>；<b>L1 管节奏和风险预算</b>，不管方向；<b>L3 只描述价格离筹码压力区多远、波动会不会放大</b>，不给方向；<b>L4 只描述短期温度</b>，不改变动作（L4 还没完成研究）。",
           "The overall read combines four layers along the study's division of labour: <b>L2 sets the direction</b>; <b>L1 sets pace and risk budget</b>, not direction; <b>L3 only describes how far price is from the supply pressure zone and whether moves may get bigger</b>, never direction; <b>L4 only describes short-term temperature</b> and never changes the action (its research is not finished).")
    p2 = T("一句话 =「{方向句}；{但}{节奏句}，{动作}。{筹码提示}{短期提示}」：方向偏多而 L1 是中性偏谨慎 / 逆风，或方向偏空 / 防顶而 L1 是顺风时加「但」；动作只来自 L1 的风险预算规则和 L2 研究写定的交接原则「方向上不急于看空，节奏上不追高、按 L1 的风险预算分批」；价格在 +1σ 压力区里或大波动预警亮时追加筹码提示（2026-10-11 起；之前是「筹码和周期方向背离」提示）；L4 不是中性时追加短期温度。一句话超过 60 字先去掉短期提示，再去掉筹码提示（四段里仍然完整显示）。",
           "One line = '{direction}; {but} {pace} — {action}. {supply note} {short term}': 'but' is added when the direction leans up while L1 is cautious/headwind, or leans down / top-risk while L1 is a tailwind; actions come only from L1's risk-budget rules and the L2 hand-over principle ('no rush to turn bearish on direction; no chasing on pace, scale in per L1's budget'); a supply note is added when price is inside the +1σ pressure zone or the large-move warning is on (since 2026-10-11; before that it was a 'flows diverge from the cycle' note); L4 adds its temperature when not neutral. Lines over 60 characters drop the short-term note first, then the supply note (both stay in the paragraphs).")
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
    sched_rows = "".join(f"<tr><td class='l'>{esc(T(x['名称'], x['EN']))}</td><td>{TT(x['时间'], False)}<br><small>UTC {esc(x['时间'])}</small></td><td class='l wrap'>{esc(T(x['覆盖'], x['覆盖EN']))}</td><td class='l'><code>.github/workflows/{esc(x['文件'])}</code></td></tr>" for x in SCHED)
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
<p class="lede keep">{T("解读日志里的每一个判断都来自下面这些公开规则。规则改动会在更正记录里留痕，历史日志不跟着改。", "Every judgement in the logs comes from the public rules below. Rule changes are logged in Corrections; past logs are never rewritten.")}</p>
<nav class="anch static">{"".join(f'<a href="#{h}">{t}</a>' for t, h in ((T("层结论", "Verdicts"), "verdicts"), (T("综合研判", "Overall read"), "comp"), (T("L1 规则清单", "L1 rules"), "l1rules"), (T("标签说明", "Tags"), "legend"), (T("更新时间", "Schedule"), "schedule"), (T("统计窗口", "Stats window"), "window"), (T("指标与区间", "Indicators"), "indicators"), (T("预警阈值", "Alerts"), "alerts")))}</nav>
<h2 id="verdicts">{T("层结论怎么来", "How layer verdicts are made")}</h2>
<div class="card mcard">
{T(L1_RULES_ZH, L1_RULES_EN)}
<p style="margin:0 0 8px"><b style="color:var(--ink)">L2 {T("周期", "Cycle")}</b>{CN}{T("规则化状态机（l2/l2_signals.py，《BTC周期层L2研究》§7）逐日推进：新高 → 牛市；减半后 480~600 天或 MVRV ≥ 2 且价/200 周均 ≥ 2 → 牛市·顶部风险区；回撤 ≥ 20% → 牛市回撤·待确认（收窄到 10% 内回到牛市）；回撤 ≥ 35% 且新高已过 90 天、减半已过 450 天 → 熊市；熊市里底部区信号 ≥ 2 条 → 熊底区；离最低点 +40% 且最低点已过 90 天，或四条短期成本线连续 7 天站上且本轮出现过分龄底部确认 → 熊末→牛初；收盘跌破本轮最低收盘则退回熊市。数据：Coin Metrics 社区接口 + bitview.space。层结论 = 当天状态。",
"A rule-based state machine (l2/l2_signals.py, L2 cycle study §7) stepped day by day: new high → bull; halving +480–600 days or MVRV ≥ 2 with price/200W MA ≥ 2 → bull top-risk; drawdown ≥ 20% → bull pullback (back to bull inside 10%); ≥ 35% with the high ≥ 90 days old and the halving ≥ 450 days old → bear; ≥ 2 bottom-zone signals in a bear → bottom zone; +40% from a ≥ 90-day-old low, or 7 days above four short-term cost lines with an age-band confirmation this cycle → late bear → early bull; a close below the cycle low reverts to bear. Data: Coin Metrics community API + bitview.space. Layer verdict = the state of the day.")}</p>
<p style="margin:0 0 8px"><b style="color:var(--ink)">L3 {T("筹码", "Supply")}</b>{CN}{T("按价格相对短期持有者成本 +1σ 压力区（上下 2%）的位置：收盘站上上沿 = 冲过压力区，进入 ±2% = 在压力区，压力区下方到 STH 成本之间 = 压力区下方，跌破 STH 成本 = STH 成本下方；30 天波动 < 40% 且筹码集中度 ≥ 12% 时追加「大波动预警」（2026-10-11 起，此前以交易所 7 日净流量为准）。交易所流量、大户 / 散户持币只作描述。", "By price position relative to the STH cost +1σ pressure zone (±2%): a close above the top = through the zone, inside ±2% = in the zone, between the zone and the STH cost = below the zone, under the STH cost = below STH cost; a 'large-move warning' is added when 30-day volatility < 40% and supply concentration ≥ 12% (since 2026-10-11; previously the 7-day exchange net flow). Exchange flows and whale/retail holdings are descriptive only.")}</p>
<p style="margin:0"><b style="color:var(--ink)">L4 {T("情绪", "Sentiment")}</b>{CN}{T("读 l4/l4_daily.py 的结论档：资金费率 30 日均跌破 0 = 信号（空头拥挤，唯一会改动作的规则，已验证·方向）；否则按杠杆和情绪的过去 730 天分位分为过热 / 偏热 / 中性 / 偏冷，只作描述（2026-10-22 起，此前是恐慌贪婪 + 资金费率 + 未平仓三项打分）。", "Reads the level from l4/l4_daily.py: 30-day average funding below zero = signal (crowded shorts, the only action-changing rule, validated · direction); otherwise leverage and sentiment 730-day percentiles band it as hot / warm / normal / cool, descriptive only (since 2026-10-22; previously a Fear & Greed + funding + OI score).")}</p></div>
<h2 id="comp">{T("综合研判怎么来", "How the overall read is made")}</h2>{comp_rules_html()}
<h2 id="l1rules">{T("L1 规则清单（宏观总文档 §10.2，逐条照抄）", "L1 rule list (macro study §10.2, copied rule by rule)")}</h2>
<div class="card mcard"><p>{T("「能否改交易参数」分四种：", "“May it change trading parameters” has four values:")}</p><ul>{pdef}</ul></div>
<div class="tw" style="margin-top:10px"><table><thead><tr><th>#</th><th class="l">{T("规则", "Rule")}</th><th class="l">{T("怎么用", "How to use")}</th><th class="l">{T("可靠程度", "Reliability")}</th><th class="l">{T("能否改交易参数", "Trading parameters")}</th></tr></thead><tbody>{rrows}</tbody></table></div>
<h2 id="legend">{T("标签说明", "What the tags mean")}</h2><p class="tnote">{T("「级别」和「证据等级」是两个维度：级别说这个指标在本层判定里起什么作用，证据等级说它在研究里被检验到什么程度。", "Level and evidence grade are two separate dimensions: level is the gauge's role in the layer verdict, evidence grade is how well the research has tested it.")}</p>{tag_legend()}
<h2 id="delayed">{T("延迟平台（发射台矩阵）", "Delayed platforms (launchpad matrix)")}</h2>
<div class="card mcard"><ul>
<li>{T("发射台矩阵只报前一个 UTC 完整日。DefiLlama 各家出数有先后：到我们取数时，个别平台（常见的有 pump.fun、StonkFun、LaunchLab）还没出这一天的数。", "The launchpad matrix reports the previous full UTC day. DefiLlama publishes platforms at different times; when we fetch, a few (often pump.fun, StonkFun, LaunchLab) may not have that day yet.")}</li>
<li>{T("判断办法：逐家拉 DefiLlama 逐日序列，最后一个有数的日子早于报告日，就是延迟平台。DefiLlama 汇总接口给这类平台的「当日」其实是它最后一天的值。", "How we detect it: we pull each platform's daily series; if its last day is earlier than the report day, it is delayed. DefiLlama's overview gives such platforms their last day's value as 'today'.")}</li>
<li>{T("矩阵排行、全类目合计、当日变化拆解和份额变化：先沿用该平台最后一天的值，避免合计和份额因为「没出数」被算成 0 而虚假下跌；同时在名字旁标「沿用 MM-DD」，头部指标写明沿用了几家、占当日合计多少。", "Matrix ranking, category total, day-over-day breakdown and share changes: the platform's last value is carried over, so totals and shares don't drop falsely because a day is missing; the name is tagged 'carried MM-DD' and the headline notes how many were carried and their share of the day's total.")}</li>
<li>{T("DefiLlama 补出真实值后，下一次日更自动换成真实值并去掉标记（保留 60 天内的沿用记录）。", "Once DefiLlama publishes the real value, the next daily run replaces it and drops the tag (carry records are kept for 60 days).")}</li>
<li>{T("深度追踪平台（逐日序列、周期温度等）不沿用：没出数就标「延迟」、留空，不拿旧值冒充新值。", "Deep-tracked platforms (daily series, cycle temperature, etc.) are never carried: a missing day is marked 'delayed' and left blank.")}</li>
</ul></div>
<h2 id="schedule">{T("更新时间", "Update schedule")}</h2>
<div class="card mcard"><p>{T("时间口径：后端统计一律用 UTC+0，所有数据按 UTC 完整日对齐，一天在 UTC 0 点收盘（新加坡时间 08:00）；价格一律用收盘价，不用脚本运行那一刻的盘中价。页面上显示的钟点按语言换算：中文站写新加坡时间（UTC+8），英文站写美东时间。定时任务在收盘后分批跑（数据源出数有先后），运行时刻不同，但读的是同一个收盘日。", "Time basis: all statistics use UTC+0. Data is aligned to full UTC days, each closing at 00:00 UTC (8:00 PM ET the previous day in summer, 7:00 PM in winter); prices always use that close, never an intraday price at run time. Clock times are displayed in US Eastern time on the English site and Singapore time (UTC+8) on the Chinese site. Jobs run in batches after the close because sources publish at different times, but they all read the same closing day.")}</p></div>
<div class="tw"><table><thead><tr><th class="l">{T("任务", "Job")}</th><th>{T("时间", "Time")}</th><th class="l">{T("覆盖哪些数据", "Covers")}</th><th class="l">{T("配置", "Config")}</th></tr></thead><tbody>{sched_rows}</tbody></table></div>
<p class="tnote">{esc(T(SITE_CFG.get("推送重跑", ""), SITE_CFG.get("推送重跑EN", "")))}{T("页面上「解读生成」是当天日志冻结的时间，「数据更新」是页面读数最后一次刷新的时间。", " 'Log generated' is when the day's log was frozen; 'Data updated' is when the page's readings were last refreshed.")}</p>
<h2 id="window">{T("统计窗口", "Statistics window")}</h2>
<div class="card mcard"><ol><li>{T("L1 宏观指标：只用 2018 年以后（方法规则：2010–2017 宏观对 BTC 没有解释力）。", "L1 macro gauges: post-2018 only (method rule: macro had no explanatory power in 2010–2017).")}</li>
<li>{T("链上周期类（L2 估值与持有者、L3 筹码层）：2012-01-01 起；有效起点更晚的取有效起点。", "On-chain cycle gauges (L2 valuation & holders, L3 supply): from 2012-01-01, or the first valid day if later.")}</li>
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
<div class="card mcard">{T(f"日志日期 = 解读当天（UTC 日期），日更每天{TT(MAIN_TIME, False)}运行，每个读数带自己的数据日期（FRED 按美国工作日、NFCI 周度、交易所余额约有 2 周滞后，超过容忍天数标 ⚠）。写入即冻结；同一天重跑且核心缺失变少才覆盖一次并标「补录」。周复盘按 ISO 周（周一至周日），月复盘按自然月；切换发生在规则变更当天的，注明「规则变更所致」。人工点评放在 content/journal/，单独标注。网站其他位置展示日志内容时标「日志 · 冻结时间」，读数和最新值不同以最新值为准。",
                                                                                   f"Log date = UTC day of the run (the daily run is at {TT(MAIN_TIME, False)}); each reading carries its own data date (FRED on US business days, NFCI weekly, exchange balance ~2 weeks late; stale readings get ⚠). Frozen once written; a same-day re-run only overwrites when fewer core inputs are missing, marked 'Re-run'. Weekly reviews follow ISO weeks, monthly ones calendar months; switches on a rule-change day are labelled as such. Wherever log content appears elsewhere it is marked with its freeze time; the latest values win.")}</div>
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
<p class="lede keep">{T("数据源事后修订、PONS 销毁口径重算、规则调整，全部留痕，不覆盖不删除。每条规则变更写明为什么改，并链到日志里的分隔行和更新日志。", "Source revisions, PONS burn recalculations and rule changes — all logged, nothing overwritten. Each rule change says why, and links to the journal marker and the changelog.")}</p>
<h2>{T("规则变更", "Rule changes")}</h2><div class="tw"><table><thead><tr><th class="l">{T("日期", "Date")}</th><th class="l">{T("范围", "Scope")}</th><th class="l">{T("改了什么", "What changed")}</th><th class="l">{T("原因", "Why")}</th></tr></thead><tbody>{rule_rows}</tbody></table></div>
{rn}
<h2>{T("数据源历史回改（自动记录）", "Source history revisions (automatic)")}</h2>
<p class="tnote">{T("Coin Metrics、bitview 等会回头修正历史数据。解读日志里的冻结值和现在图上的值对不上时，可以在这里查。", "Coin Metrics, bitview and others revise history. When a frozen log value differs from today's chart, look here.")}</p>{rv_html}
<h2>{T("PONS 逐日销毁重算记录", "PONS daily burn recalculations")}</h2><div class="tw"><table><thead><tr><th class="l">{T("日期", "Date")}</th><th>{T("旧值 → 新值", "Old → new")}</th><th class="l">{T("口径", "Basis")}</th><th>{T("修正时间", "Fixed")}</th></tr></thead>
<tbody>{rows or none_}</tbody></table></div>"""
    emit("corrections/index.html", T(f"更正记录 · {BRAND}", f"Corrections · {BRAND_EN}"), body, active="corrections")


def build_about():
    txt = T(f"""<p>写这个站的人在 web3 做了快十年，做过项目运营、产品设计，也做过 AMM DEX。现在把自己的研究方式搬到台面上：
先看宏观环境给多少风险预算，再看周期位置（贵不贵），再看筹码结构（哪些价位有人在守、波动会不会放大），再看情绪（会不会超调），最后落到发射台一级市场——每天赚多少钱、钱从哪来。</p>
<p>所有判断都按公开规则自动生成，每天一篇解读日志，写入即冻结；每周、每月再复盘一次；系统性的研究整理成分析报告。对了错了都留在这里，不做事后诸葛亮。</p>
<p>{esc(DISCLAIMER)}</p>
<p class="muted">访问统计：本站用 Umami 统计访问量和少量点击（生成长图、语言切换、报告是否读完等），只为了解哪些内容有人看。不用 cookie，不收集个人信息，不跨站追踪。</p>""", f"""<p>The author has spent close to ten years in web3 — operations, product design and an AMM DEX. This site puts the research process in public:
first how much risk budget the macro backdrop allows, then the cycle (cheap or expensive), supply structure (which levels are defended and whether moves will get bigger), sentiment (is it overshooting), and finally the launchpad primary market — how much money is made every day and where it comes from.</p>
<p>Every judgement is generated from public rules; one log per day, frozen once written; weekly and monthly reviews; deeper research as reports. Right or wrong, it all stays here.</p>
<p>{esc(DISCLAIMER_EN)}</p>
<p class="muted">Analytics: this site uses Umami to count visits and a few clicks (share image, language switch, whether a report was read to the end) to learn which content is useful. No cookies, no personal data, no cross-site tracking.</p>""")
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
<p class="lede keep">{T("每一版按实际上线的内容写，新版本在最前面。「数据口径」类改动同时写进更正记录。", "Each version lists what actually shipped, newest first. Data changes are also logged in Corrections.")}</p>
{blocks}"""
    emit("changelog/index.html", T(f"更新日志 · {BRAND}", f"Changelog · {BRAND_EN}"), body, active="changelog")
    if LANG["v"] == "zh":
        with open(os.path.join(SITE, "changelog.json"), "w", encoding="utf-8") as fh:
            json.dump(CHANGELOG, fh, ensure_ascii=False, indent=1)


def build_404():
    emit("404.html", T(f"页面不存在 · {BRAND}", f"Not found · {BRAND_EN}"),
         f'<h1>{T("页面不存在", "Page not found")}</h1><p class="lede keep">{T("链接可能过期了，回", "The link may be outdated. Back to the ")}<a href="{U("/")}">{T("终端总览", "overview")}</a>{T("看看。", ".")}</p>')


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
    urls = ["/", "/macro/", "/leg-tracker/", "/calendar/", "/launchpad/", "/ai-agent/", "/rotation/", "/alpha/", "/alpha/radar/", "/alpha/cases/", "/alpha/framework/", "/alpha/eval/", "/alpha/method/", "/alpha/progress/", "/reports/", "/journal/", "/methodology/", "/corrections/", "/about/",
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
    G["L3"] = load(os.path.join(DATA, "l3", "l3_latest.json"))
    G["L3S"] = load(os.path.join(DATA, "l3", "l3_series.json"))
    G["L3H"] = load(os.path.join(DATA, "l3", "l3_history.json"), []) or []
    R.attach_l3(S, G["L3S"])
    try:
        import 周期观察 as CO
        G["CYC_DATA"] = CO.live_data(ROOT, matrix) if matrix else None
    except Exception as e:  # noqa —— 周期数据坏了不影响其他页面
        print("周期数据失败：", e)
        G["CYC_DATA"] = None
    G["CYC_SUM"] = cycle_summary()
    G["L4"] = load(os.path.join(DATA, "l4", "l4_latest.json"))
    G["L4H"] = load(os.path.join(DATA, "l4", "l4_history.json"), []) or []
    G["CAL"] = load(os.path.join(DATA, "cal", "cal_latest.json"))
    G["LEG"] = load(os.path.join(DATA, "leg", "leg_latest.json"))
    upd = [(L.get("更新时间UTC") or sd.get("生成时间UTC") or "")[:16].replace("T", " "), (G["L2"] or {}).get("updated_utc") or ""]
    G["更新"] = max(upd)
    os.makedirs(SITE, exist_ok=True)
    # ---- 全站「当前读数」唯一来源（G3）：这一次构建里所有页面都读同一份 rs / 层结论 / 综合研判
    as_of = G["今天"]
    G["S"], G["as_of"] = S, as_of
    rs = [x for x in (R.judge(S, ind, as_of) for ind in R.INDICATORS) if x]
    G["RS"], G["JBY"] = rs, {x["key"]: x for x in rs}
    G["VS"] = {i: R.layer_verdict(i, rs, G["L2"], G["L3"], G["L4"]) for i in R.LAYERS}
    G["COMP"] = R.综合.compose(G["VS"], rs, G["L2"], G["L3"], G["L4"])
    G["TODAY_LOG"] = logs[-1] if logs else None
    G["PREV_LOG"] = next((lg for lg in reversed(logs) if lg["日期"] < as_of), None)
    G["CHANGES"] = R.alerts(rs, G["PREV_LOG"], R.launchpad_summary(sd), G["VS"][1], G["L2"], G["L3"], G["L4"])
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
    for sub, fns in (("l4", ("l4_latest.json", "l4_history.json")), ("cal", ("cal_latest.json",))):
        os.makedirs(os.path.join(SITE, "data", sub), exist_ok=True)
        for fn in fns:
            if os.path.exists(os.path.join(DATA, sub, fn)):
                shutil.copyfile(os.path.join(DATA, sub, fn), os.path.join(SITE, "data", sub, fn))
    os.makedirs(os.path.join(SITE, "data", "l3"), exist_ok=True)
    for fn in ("l3_latest.json", "l3_history.json"):
        if os.path.exists(os.path.join(DATA, "l3", fn)):
            shutil.copyfile(os.path.join(DATA, "l3", fn), os.path.join(SITE, "data", "l3", fn))
    for fn in ("l2_latest.json", "l2_history.json", "l2_live.json"):
        if os.path.exists(os.path.join(DATA, "l2", fn)):
            shutil.copyfile(os.path.join(DATA, "l2", fn), os.path.join(SITE, "data", "l2", fn))
    for fn in ("leg_latest.json", "leg_history.json"):
        if os.path.exists(os.path.join(DATA, "leg", fn)):
            shutil.copyfile(os.path.join(DATA, "leg", fn), os.path.join(SITE, "data", fn))
    if G.get("LEG"):   # 站点版多一个 site_scale（卡片刻度），原始数据 data/leg/leg_latest.json 不动
        with open(os.path.join(SITE, "data", "leg_latest.json"), "w", encoding="utf-8") as f:
            json.dump(dict(G["LEG"], site_scale=leg_scale()), f, ensure_ascii=False, indent=1)
    write_core_data()
    write_alpha_data()
    write_aiagent_data()
    write_rwa_data()
    copy_report_files()
    for lang in ("zh", "en"):
        LANG["v"] = lang
        build_home(sd, S, logs, weeks, months, rot, matrix)
        build_macro(L, S, logs)
        build_indicator_pages(L, S, logs, files)
        build_launchpad(sd, matrix)
        from 周期观察 import build as build_cycle
        globals()["CYCLE_MONEY"] = money_where(matrix)
        if G.get("CYC_DATA"):
            build_cycle(globals())
        build_launchpad_platforms(sd, matrix)
        build_launchpad_discovery()
        build_launchpad_report(sd)
        build_rotation(rot)
        build_narrative()
        build_calendar()
        build_leg_tracker()
        build_core()
        build_alpha()
        build_rwa()
        build_ai_agent()
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
