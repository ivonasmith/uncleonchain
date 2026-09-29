#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""链上大叔研究台 · 静态网站生成器（终端版）

产品结构（左侧常驻导航，每个板块独立 URL，方便从推特直链到具体页面）：
  /                 终端总览    综合研判 + 四张核心卡 + 四层信号灯 + 异动预警看台 + 发射台 / 板块 / 日志快照
  /macro/           宏观仪表盘  四层框架：流动性 → 周期 → 筹码 → 情绪，每个指标读数 + 区间 + 90 天走势
  /launchpad/       发射台矩阵  DefiLlama Launchpad 全类目跨链排行 + 生态切流 / 周期 / 金额档多维过滤 + 一键长图
                    /launchpad/platforms/<slug>/  深度追踪平台分数据（pump.fun / Pons / StonkFun / Flap / Arc）
                    /launchpad/report/            每日文字解读（出看板.py 原文）
  /rotation/        板块轮动    CoinGecko 类目逐日快照 + 手写复盘
  /narrative/       叙事埋伏    雷达（筹备中）+ 手写观察笔记
  /journal/         解读日志    每日自动解读（冻结存档）+ 周复盘 + 月复盘，公开
  /methodology/ /corrections/ /about/

读：build/网站素材.json（出看板.py）· data/宏观台账.json · data/板块台账.json · data/发射台矩阵.json
    data/解读日志/ · content/posts/<板块>/*.md|*.html · content/journal/*.md（人工点评）
写：site/

视觉：终端深色（底 #05070c · 卡片 #0b0e17 · 1px rgba(255,255,255,.06) 细线 · 涨/正向 #00ffcc · 跌/警告 #ff3366），
      品牌强调色取大叔头像的荧光青柠 #a3e635，只用在导航和按钮上，不用在数字上，避免和涨跌色混淆。
"""
import os, sys, re, json, glob, html, shutil, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 宏观规则 as R                                                     # noqa: E402

BUILD = os.path.abspath(os.environ.get("LP_OUT") or os.path.join(ROOT, "build"))
DATA = os.path.abspath(os.environ.get("LP_DATA") or os.path.join(ROOT, "data"))
SITE = os.path.abspath(os.environ.get("LP_SITE") or os.path.join(ROOT, "site"))
CONTENT = os.path.join(ROOT, "content", "posts")
JCONTENT = os.path.join(ROOT, "content", "journal")
ASSETS = os.path.join(ROOT, "assets")

BRAND = "链上大叔研究台"
BRAND_EN = "Uncle Onchain"
DOMAIN = "uncleonchain.com"
TWITTER = "@Uncle_Web3PM"
X_URL = "https://x.com/Uncle_Web3PM"
SLOGAN = "宏观流动性 → 周期位置 → 筹码结构 → 情绪 → 发射台一级市场，每天一篇公开解读日志"
DISCLAIMER = "本站只给数据和过程记录，不构成任何投资建议；不对任何交易结果负责。"

PILLARS = [
    {"slug": "macro", "nav": "宏观仪表盘", "desc": "四层框架：宏观流动性 → 周期定位 → 筹码结构 → 情绪衍生品，每个指标的读数、历史区间和走势。"},
    {"slug": "rotation", "nav": "板块轮动", "desc": "CoinGecko 类目逐日快照看资金在哪些赛道之间流动，加手写的轮动交易复盘。"},
    {"slug": "narrative", "nav": "叙事埋伏", "desc": "低位叙事币的观察笔记：为什么进、仓位怎么摆、后续怎么跟踪——过程记录，不是喊单。"},
]

ICON = {
    "home": '<path d="M2.5 2.5h4.5v4.5H2.5zM9 2.5h4.5v4.5H9zM2.5 9h4.5v4.5H2.5zM9 9h4.5v4.5H9z"/>',
    "macro": '<path d="M1.5 10.5c1.6-3.2 3.2-3.2 4.8 0s3.2 3.2 4.8 0c.9-1.8 1.9-2.6 2.9-2.2M1.5 5.5c1.6-3.2 3.2-3.2 4.8 0s3.2 3.2 4.8 0"/>',
    "launchpad": '<path d="M3 14V8.5M8 14V2.5M13 14V6"/><path d="M1.5 14h13"/>',
    "rotation": '<path d="M13.2 6A5.5 5.5 0 0 0 3.1 5.4M2.8 10a5.5 5.5 0 0 0 10.1.6M13.4 2.6v3.5H9.9M2.6 13.4V9.9h3.5"/>',
    "narrative": '<circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="2.4"/><path d="M8 8l4.2-4.2"/>',
    "journal": '<path d="M3.5 1.8h9v12.4h-9z"/><path d="M6 5h4M6 8h4M6 11h2.5"/>',
    "methodology": '<path d="M2 12.5 12.5 2l1.5 1.5L3.5 14H2z"/><path d="M9.5 5l1.5 1.5M7.5 7l1 1M5.5 9l1.5 1.5"/>',
    "corrections": '<path d="M2.5 8.5l3.5 3.5 7.5-8"/>',
    "about": '<circle cx="8" cy="5.2" r="2.8"/><path d="M2.5 14c.9-2.9 2.9-4.2 5.5-4.2s4.6 1.3 5.5 4.2"/>',
}
NAV_MAIN = [("home", "/", "终端总览"), ("macro", "/macro/", "宏观仪表盘"), ("launchpad", "/launchpad/", "发射台矩阵"),
            ("rotation", "/rotation/", "板块轮动"), ("narrative", "/narrative/", "叙事埋伏"), ("journal", "/journal/", "解读日志")]
NAV_MORE = [("methodology", "/methodology/", "口径与规则"), ("corrections", "/corrections/", "更正记录"), ("about", "/about/", "关于")]

G = {"更新": None}      # 侧边栏「数据更新」时间，main() 里填


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


def parse_post_md(path):
    meta, body = split_front(open(path, encoding="utf-8").read())
    if not meta:
        return None
    slug = re.sub(r"[^a-z0-9\-]+", "-", os.path.splitext(os.path.basename(path))[0].lower()).strip("-")
    meta.setdefault("标题", slug)
    meta.setdefault("日期", dt.date.today().isoformat())
    meta.setdefault("摘要", "")
    meta.update({"slug": slug, "kind": "md", "html": md_to_html(body.strip()), "css": ""})
    return meta


def parse_post_html(path):
    raw = open(path, encoding="utf-8").read()
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
    slug = re.sub(r"[^a-z0-9\-]+", "-", os.path.splitext(os.path.basename(path))[0].lower()).strip("-")
    m_body = re.search(r"<body[^>]*>(.*)</body>", raw, re.S)
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", raw, re.S))
    meta.update({"slug": slug, "kind": "html", "html": m_body.group(1) if m_body else raw, "css": css})
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


def commentary(key):
    """content/journal/<key>.md 的人工点评（可选）。"""
    p = os.path.join(JCONTENT, f"{key}.md")
    if not os.path.exists(p):
        return ""
    meta, body = split_front(open(p, encoding="utf-8").read())
    return md_to_html(body.strip())


# ---------------------------------------------------------------- 视觉系统
SITE_CSS = r"""
:root,:root[data-theme="dark"]{--bg:#05070c;--card:#0b0e17;--card2:#10141f;--line:rgba(255,255,255,.06);--line2:rgba(255,255,255,.11);
--ink:#e8ecf3;--ink2:#a7afc0;--muted:#6b7488;--up:#00ffcc;--dn:#ff3366;--warn:#ffb020;--cool:#5b8cff;--lime:#a3e635;
--up-bg:rgba(0,255,204,.08);--dn-bg:rgba(255,51,102,.09);--warn-bg:rgba(255,176,32,.09);--cool-bg:rgba(91,140,255,.10);
--panel:var(--card2);--rule:var(--line);--rule2:var(--line2);--accent:var(--lime);--accent-soft:rgba(163,230,53,.08);
--mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
--sans:Inter,"Noto Sans SC",-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
color-scheme:dark}
*{box-sizing:border-box}
html,body{background:var(--bg);margin:0}
body{color:var(--ink);font:14.5px/1.65 var(--sans);-webkit-font-smoothing:antialiased;min-height:100vh}
body:before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
background:radial-gradient(700px 420px at 12% -8%,rgba(0,255,204,.07),transparent 70%),
radial-gradient(640px 420px at 100% 108%,rgba(163,230,53,.05),transparent 70%)}
a{color:inherit}
a:hover{color:var(--lime)}
.num,.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
svg.ic{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round;flex:none}

/* ---- 外壳：左侧常驻导航 ---- */
.side{position:fixed;top:0;left:0;bottom:0;width:236px;z-index:30;background:rgba(7,9,15,.92);
border-right:1px solid var(--line);display:flex;flex-direction:column;padding:18px 14px;backdrop-filter:blur(12px)}
.brand{display:flex;align-items:center;gap:11px;text-decoration:none;padding:4px 6px 18px;border-bottom:1px solid var(--line);margin-bottom:14px}
.brand .av{width:38px;height:38px;border-radius:50%;box-shadow:0 0 0 1.5px var(--lime),0 0 18px rgba(163,230,53,.25)}
.brand b{display:block;font-size:15px;font-weight:700;letter-spacing:.2px;color:var(--ink)}
.brand i{display:block;font-style:normal;font-family:var(--mono);font-size:9.5px;letter-spacing:1.4px;color:var(--muted);margin-top:2px}
.snav{display:flex;flex-direction:column;gap:2px;flex:1;overflow-y:auto}
.sgrp{font-family:var(--mono);font-size:10px;letter-spacing:1.6px;color:var(--muted);padding:12px 10px 6px;text-transform:uppercase}
.snav a{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;text-decoration:none;color:var(--ink2);
font-size:13.5px;position:relative;transition:background .15s,color .15s}
.snav a:hover{background:rgba(255,255,255,.035);color:var(--ink)}
.snav a.on{background:rgba(163,230,53,.07);color:var(--ink)}
.snav a.on:before{content:"";position:absolute;left:-14px;top:7px;bottom:7px;width:3px;border-radius:0 3px 3px 0;background:var(--lime)}
.snav a.on svg.ic{color:var(--lime)}
.snav a .tag{margin-left:auto;font-family:var(--mono);font-size:9.5px;color:var(--muted);border:1px solid var(--line2);border-radius:4px;padding:0 5px}
.sfoot{border-top:1px solid var(--line);padding:14px 6px 0;font-size:11.5px;color:var(--muted);line-height:1.6}
.live{display:flex;align-items:center;gap:7px;font-family:var(--mono);font-size:10.5px;color:var(--ink2)}
.live i{width:7px;height:7px;border-radius:50%;background:var(--up);box-shadow:0 0 8px var(--up);animation:pulse 2.4s infinite}
@keyframes pulse{50%{opacity:.35}}
.sfoot a{display:inline-block;margin-top:8px;color:var(--ink2);text-decoration:none;font-family:var(--mono);font-size:11.5px}
.sfoot p{margin:8px 0 0;font-size:10.5px}
.main{margin-left:236px;position:relative;z-index:1;min-height:100vh;display:flex;flex-direction:column}
.mi{width:100%;max-width:1280px;margin:0 auto;padding:30px 36px 56px;flex:1}
.mi.narrow{max-width:900px}
.foot{border-top:1px solid var(--line);color:var(--muted);font-size:11.5px;padding:18px 36px;display:flex;gap:10px 22px;flex-wrap:wrap}
.foot a{color:var(--muted)}
.topbar{display:none}
.navtg{display:none}
@media (max-width:960px){
 .side{transform:translateX(-100%);transition:transform .2s;width:264px}
 .navtg:checked~.side{transform:none}
 .navtg:checked~.scrim{display:block}
 .scrim{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:25}
 .main{margin-left:0}
 .topbar{display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:20;padding:10px 16px;
  background:rgba(5,7,12,.9);border-bottom:1px solid var(--line);backdrop-filter:blur(10px)}
 .topbar label{cursor:pointer;display:flex;padding:6px;border:1px solid var(--line2);border-radius:8px}
 .topbar a{display:flex;align-items:center;gap:8px;text-decoration:none;font-weight:700;font-size:14px}
 .topbar img{width:26px;height:26px;border-radius:50%;box-shadow:0 0 0 1.5px var(--lime)}
 .topbar .d{margin-left:auto;font-family:var(--mono);font-size:10.5px;color:var(--muted)}
 .mi{padding:20px 16px 40px}
 .ph .stamp{text-align:left}
 .foot{padding:16px}
}

/* ---- 页头 ---- */
.ph{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:10px 24px;margin-bottom:22px}
.eyebrow{font-family:var(--mono);font-size:10.5px;letter-spacing:1.8px;color:var(--lime);text-transform:uppercase}
h1{font:700 26px/1.25 var(--sans);letter-spacing:-.2px;margin:6px 0 0}
h2{font:600 17px/1.35 var(--sans);margin:34px 0 12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
h2 .sub{font-weight:400;font-size:12.5px;color:var(--muted)}
h3{font:600 14.5px/1.4 var(--sans);margin:22px 0 8px}
.lede{color:var(--ink2);max-width:78ch;margin:10px 0 0;font-size:14px}
.stamp{font-family:var(--mono);font-size:11px;color:var(--muted);text-align:right;line-height:1.7}
.stamp b{color:var(--ink2);font-weight:500}

/* ---- 卡片 / 毛玻璃 ---- */
.glass{background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.01));border:1px solid var(--line);
border-radius:14px;backdrop-filter:blur(14px) saturate(140%);-webkit-backdrop-filter:blur(14px) saturate(140%);
box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px}
.grid{display:grid;gap:12px}
.g4{grid-template-columns:repeat(4,minmax(0,1fr))}.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
@media(max-width:1100px){.g4{grid-template-columns:repeat(2,minmax(0,1fr))}.g3{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.g4,.g3,.g2{grid-template-columns:1fr}}

.verdict{padding:20px 22px;display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-bottom:14px;position:relative;overflow:hidden}
.verdict:after{content:"";position:absolute;right:-60px;top:-60px;width:220px;height:220px;border-radius:50%;
background:radial-gradient(circle,rgba(0,255,204,.10),transparent 70%)}
.verdict .lbl{font-family:var(--mono);font-size:10px;letter-spacing:1.6px;color:var(--muted);text-transform:uppercase}
.verdict .txt{font-size:17px;font-weight:600;line-height:1.5;margin:6px 0 10px;max-width:70ch}
.verdict .body{flex:1;min-width:260px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;padding:3px 9px;border-radius:999px;
border:1px solid var(--line2);color:var(--ink2);white-space:nowrap}
.chip i{width:6px;height:6px;border-radius:50%;background:currentColor}
.t-up{color:var(--up)}.t-dn{color:var(--dn)}.t-warn{color:var(--warn)}.t-cool{color:var(--cool)}.t-neutral{color:var(--ink2)}
.chip.t-up{border-color:rgba(0,255,204,.35);background:var(--up-bg)}.chip.t-dn{border-color:rgba(255,51,102,.4);background:var(--dn-bg)}
.chip.t-warn{border-color:rgba(255,176,32,.4);background:var(--warn-bg)}.chip.t-cool{border-color:rgba(91,140,255,.45);background:var(--cool-bg)}

.hero{padding:16px 18px 12px;position:relative;overflow:hidden}
.hero .k{font-size:11.5px;color:var(--muted);display:flex;justify-content:space-between;gap:8px}
.hero .k span{font-family:var(--mono);font-size:10px;letter-spacing:.6px}
.hero .v{font:600 25px/1.2 var(--mono);letter-spacing:-.5px;margin:8px 0 4px}
.hero .s{font-size:12px;color:var(--ink2)}
.hero svg.spk{margin-top:10px;width:100%;height:34px}

.sig{padding:16px 18px;text-decoration:none;display:block;border-top:2px solid var(--line2)}
.sig:hover{background:var(--card2);color:inherit}
.sig .n{font-family:var(--mono);font-size:10px;letter-spacing:1.4px;color:var(--muted)}
.sig .q{font-size:12px;color:var(--muted);margin-top:2px}
.sig .v{font-size:15px;font-weight:600;margin:10px 0 8px;line-height:1.4}
.sig ul{list-style:none;margin:0;padding:0;font-size:12px;color:var(--ink2)}
.sig li{display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-top:1px dashed var(--line)}
.sig li b{font-family:var(--mono);font-weight:500;color:var(--ink)}
.sig.t-up{border-top-color:var(--up)}.sig.t-dn{border-top-color:var(--dn)}.sig.t-warn{border-top-color:var(--warn)}.sig.t-cool{border-top-color:var(--cool)}

/* ---- 异动预警看台 ---- */
.board{padding:0;overflow:hidden}
.board-hd{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid var(--line)}
.board-hd b{font-size:13.5px}
.board-hd .dot{width:8px;height:8px;border-radius:50%;background:var(--dn);box-shadow:0 0 10px var(--dn);animation:pulse 1.6s infinite}
.board-hd .sp{flex:1}
.ticker{overflow:hidden;white-space:nowrap;border-bottom:1px solid var(--line);background:rgba(255,255,255,.015);
-webkit-mask-image:linear-gradient(90deg,transparent,#000 6%,#000 94%,transparent);mask-image:linear-gradient(90deg,transparent,#000 6%,#000 94%,transparent)}
.ticker-track{display:inline-flex;gap:38px;padding:9px 0;animation:tick 70s linear infinite;font-family:var(--mono);font-size:12px}
.ticker:hover .ticker-track{animation-play-state:paused}
.ticker-track span{color:var(--ink2)}.ticker-track span b{color:var(--ink);font-weight:500}
@keyframes tick{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.ticker-track{animation:none}}
.alerts{list-style:none;margin:0;padding:6px 0}
.alerts li{display:flex;gap:12px;align-items:flex-start;padding:8px 16px;font-size:13px;border-bottom:1px solid var(--line)}
.alerts li:last-child{border-bottom:none}
.alerts .lv{font-family:var(--mono);font-size:10px;padding:1px 6px;border-radius:4px;flex:none;margin-top:2px}
.alerts .lv.h{color:var(--dn);background:var(--dn-bg);border:1px solid rgba(255,51,102,.35)}
.alerts .lv.m{color:var(--warn);background:var(--warn-bg);border:1px solid rgba(255,176,32,.35)}
.alerts .d{font-family:var(--mono);font-size:11px;color:var(--muted);flex:none;margin-top:1px}
.quiet{padding:14px 16px;color:var(--muted);font-size:13px}

.btn{display:inline-flex;align-items:center;gap:7px;font:600 12px/1 var(--sans);padding:8px 12px;border-radius:8px;
border:1px solid rgba(163,230,53,.5);color:var(--lime);background:rgba(163,230,53,.06);cursor:pointer;text-decoration:none;white-space:nowrap}
.btn:hover{background:rgba(163,230,53,.14);color:var(--lime)}
.btn.ghost{border-color:var(--line2);color:var(--ink2);background:transparent}
.btn.ghost:hover{color:var(--ink);border-color:var(--ink2)}
.toast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%) translateY(20px);opacity:0;z-index:99;
background:#11161f;border:1px solid var(--line2);color:var(--ink);padding:10px 16px;border-radius:10px;font-size:13px;transition:.25s;pointer-events:none}
.toast.on{opacity:1;transform:translateX(-50%)}

/* ---- 指标卡（宏观仪表盘） ---- */
.layer{margin-top:34px;scroll-margin-top:20px}
.layer-hd{display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px;margin-bottom:12px}
.layer-hd .no{font-family:var(--mono);font-size:11px;color:var(--lime);border:1px solid rgba(163,230,53,.4);border-radius:6px;padding:2px 7px}
.layer-hd h2{margin:0}
.layer-hd .why{font-size:12.5px;color:var(--muted);width:100%}
.ind{padding:14px 16px;display:flex;flex-direction:column;gap:6px;min-height:168px}
.ind .top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.ind .nm{font-size:13px;font-weight:600}
.ind .lv{font-family:var(--mono);font-size:9.5px;color:var(--muted);border:1px solid var(--line2);border-radius:4px;padding:0 5px;margin-left:6px;font-weight:400}
.ind .v{font:600 22px/1.2 var(--mono);letter-spacing:-.4px}
.ind .b{font-size:12px;color:var(--ink2)}
.ind .ft{margin-top:auto;display:flex;justify-content:space-between;gap:8px;font-size:10.5px;color:var(--muted);font-family:var(--mono)}
.ind .ft .stale{color:var(--warn)}
.ind svg.spk{width:100%;height:32px}
.ind details{font-size:12px;color:var(--muted)}
.ind summary{cursor:pointer;list-style:none;font-size:11px}
.ind summary::-webkit-details-marker{display:none}
.pend{padding:12px 14px;border:1px dashed var(--line2);border-radius:12px;font-size:12px;color:var(--muted)}
.pend b{display:block;color:var(--ink2);font-size:12.5px;margin-bottom:3px;font-weight:600}
.src{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}

/* ---- 表格 ---- */
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:13px}
th{font-size:10.5px;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);font-weight:600;text-align:right;
padding:10px 12px;border-bottom:1px solid var(--line);white-space:nowrap;background:rgba(255,255,255,.015)}
td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-family:var(--mono);font-variant-numeric:tabular-nums}
th.l,td.l{text-align:left}
td.l{font-family:var(--sans)}
tr:last-child td{border-bottom:none}
tbody tr:hover td{background:rgba(255,255,255,.025)}
td.rk{color:var(--muted);width:1%;font-size:11.5px}
th.hl{color:var(--lime)} td.hl{color:var(--ink);background:rgba(163,230,53,.035)}
.pname{display:flex;align-items:center;gap:9px;font-weight:600}
.pname img{width:18px;height:18px;border-radius:50%;background:#1a1f2b;flex:none}
.pname a{text-decoration:none}
.pname .deep{font-family:var(--mono);font-size:9px;color:var(--lime);border:1px solid rgba(163,230,53,.4);border-radius:3px;padding:0 4px;font-weight:500}
.badge{display:inline-block;font-family:var(--mono);font-size:10px;padding:1px 7px;border-radius:999px;border:1px solid currentColor;margin-left:4px;opacity:.9;font-weight:400}
.b-solana{color:#c084fc}.b-robinhood{color:#4ade80}.b-bsc{color:#fbbf24}.b-base{color:#60a5fa}.b-arc{color:#22d3ee}
.b-monad{color:#a78bfa}.b-ethereum{color:#94a3b8}.b-other{color:#7c8598}
.d.up{color:var(--up)}.d.dn{color:var(--dn)}.d{color:var(--ink2)}
svg.spk{display:block;width:92px;height:26px;margin-left:auto}
.tw.scroll{max-height:720px;overflow:auto}.tw.scroll thead th{position:sticky;top:0;z-index:2;background:#0d111b}
.tnote{font-size:12px;color:var(--muted);margin:10px 2px 0;line-height:1.7}

/* ---- 过滤器（发射台矩阵） ---- */
.fbar{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center;padding:12px 14px;margin:0 0 12px}
.fg{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.fg .fl{font-family:var(--mono);font-size:10px;letter-spacing:1.2px;color:var(--muted);text-transform:uppercase;margin-right:2px}
.pill{font:500 12px/1 var(--sans);padding:6px 10px;border-radius:7px;border:1px solid var(--line2);color:var(--ink2);background:transparent;cursor:pointer}
.pill:hover{color:var(--ink);border-color:rgba(255,255,255,.22)}
.pill.on{color:#05070c;background:var(--lime);border-color:var(--lime)}
.pill small{font-family:var(--mono);font-size:10px;opacity:.75;margin-left:4px}
.fcount{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--muted)}
.chainbar{display:flex;height:8px;border-radius:5px;overflow:hidden;margin:12px 0 6px;background:var(--card)}
.chainbar i{display:block;height:100%}
.chainleg{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:11.5px;color:var(--ink2)}
.chainleg span{display:inline-flex;align-items:center;gap:6px}.chainleg i{width:8px;height:8px;border-radius:2px}
.chainleg b{font-family:var(--mono);font-weight:500;color:var(--ink)}

/* ---- 图表 ---- */
.plot{overflow-x:auto}
.tsvg{display:block;width:100%;min-width:520px;height:auto}
.tsvg .gl{stroke:rgba(255,255,255,.06);stroke-width:1}
.tsvg .ax{fill:var(--muted);font-size:10.5px;font-family:var(--mono)}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12px;color:var(--ink2);margin:4px 0 8px}
.legend span{display:inline-flex;align-items:center;gap:6px}.legend i{width:10px;height:3px;border-radius:2px}
.legend b{font-family:var(--mono);color:var(--ink);font-weight:500}

/* ---- 列表 / 日志 ---- */
.list{list-style:none;margin:0;padding:0}
.list li{display:flex;gap:14px;align-items:baseline;padding:11px 16px;border-bottom:1px solid var(--line)}
.list li:last-child{border-bottom:none}
.list .d{font-family:var(--mono);font-size:11.5px;color:var(--muted);flex:none;min-width:92px}
.list a{text-decoration:none;font-weight:600}
.list .s{display:block;font-size:12.5px;color:var(--ink2);margin-top:3px;font-weight:400}
.list .x{margin-left:auto;flex:none}
.empty{padding:18px 20px;color:var(--ink2);font-size:13px;border:1px dashed var(--line2);border-radius:12px}
.pager{display:flex;justify-content:space-between;gap:10px;margin-top:26px;font-size:13px}
.pager a{text-decoration:none;color:var(--ink2)}
.cmt{border-left:3px solid var(--lime);padding:14px 18px;background:rgba(163,230,53,.04);border-radius:0 10px 10px 0;margin-top:12px}
.cmt p{margin:0 0 10px}.cmt p:last-child{margin:0}

/* ---- 板块轮动 ---- */
.cat{padding:13px 14px;display:flex;flex-direction:column;gap:4px}
.cat .nm{font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cat .v{font:600 19px/1.2 var(--mono)}
.cat .s{font-size:11px;color:var(--muted);font-family:var(--mono)}
.cat .t3{font-size:10.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cat.t-up{box-shadow:inset 0 2px 0 var(--up)}.cat.t-dn{box-shadow:inset 0 2px 0 var(--dn)}

/* ---- 文章（手写 md） ---- */
.article{max-width:74ch;font-size:15px;line-height:1.8}
.article p{margin:0 0 14px}
.article blockquote{margin:0 0 14px;padding:8px 18px;border-left:3px solid var(--lime);color:var(--ink2);background:rgba(255,255,255,.02);border-radius:0 8px 8px 0}
.article code{background:rgba(255,255,255,.06);padding:1px 5px;border-radius:4px;font-family:var(--mono);font-size:.88em}
.article ul{padding-left:22px}.article li{margin:0 0 7px}
.callout{border-left:3px solid var(--lime);background:rgba(163,230,53,.05);padding:14px 18px;margin:20px 0;border-radius:0 10px 10px 0}
.callout h4{margin:0 0 6px;font-size:13px;color:var(--lime)}
.callout.blue{border-color:var(--cool);background:var(--cool-bg)}.callout.blue h4{color:var(--cool)}
.callout.red{border-color:var(--dn);background:var(--dn-bg)}.callout.red h4{color:var(--dn)}
.callout.green,.callout.gray{border-color:var(--up);background:var(--up-bg)}.callout.green h4,.callout.gray h4{color:var(--up)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:20px 0}
.kpi{background:var(--card);padding:14px}.kpi .k{font-size:11px;color:var(--muted)}.kpi .v{font:600 22px/1.2 var(--mono)}.kpi .s{font-size:11.5px;color:var(--muted)}

/* ---- 分享长图舞台（屏幕外渲染，html2canvas 截图） ---- */
.sc{position:fixed;left:-12000px;top:0;width:1080px;padding:54px 56px 40px;background:#05070c;color:#e8ecf3;font-family:var(--sans);
background-image:radial-gradient(700px 400px at 0% 0%,rgba(0,255,204,.10),transparent 70%),radial-gradient(600px 400px at 100% 100%,rgba(163,230,53,.08),transparent 70%)}
.sc-hd{display:flex;align-items:center;gap:16px}
.sc-hd img{width:64px;height:64px;border-radius:50%;box-shadow:0 0 0 3px #a3e635}
.sc-hd b{display:block;font-size:26px}.sc-hd i{display:block;font-style:normal;font-family:var(--mono);font-size:16px;color:#8c94a6;margin-top:2px}
.sc-date{margin-left:auto;font-family:var(--mono);font-size:18px;color:#a7afc0;text-align:right}
.sc-title{font-size:40px;font-weight:700;margin:34px 0 8px;letter-spacing:-.5px}
.sc-sub{font-size:19px;color:#a7afc0;margin-bottom:24px;line-height:1.5}
.sc table{font-size:20px}.sc th{font-size:14px;padding:12px 14px}.sc td{padding:13px 14px}
.sc .sc-box{border:1px solid rgba(255,255,255,.08);border-radius:18px;background:#0b0e17;overflow:hidden;margin-bottom:22px}
.sc .sc-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}
.sc .sc-kpi{border:1px solid rgba(255,255,255,.08);border-radius:16px;background:#0b0e17;padding:18px}
.sc .sc-kpi .k{font-size:15px;color:#8c94a6}.sc .sc-kpi .v{font:600 30px/1.2 var(--mono);margin-top:8px}.sc .sc-kpi .s{font-size:15px;margin-top:4px}
.sc .sc-al{list-style:none;margin:0;padding:6px 0;font-size:19px}.sc .sc-al li{padding:11px 20px;border-bottom:1px solid rgba(255,255,255,.06)}
.sc .sc-al li:last-child{border:none}
.sc .chip{font-size:17px;padding:6px 14px}
.sc-ft{display:flex;gap:24px;align-items:center;margin-top:26px;padding-top:18px;border-top:1px solid rgba(255,255,255,.08);font-family:var(--mono);font-size:15px;color:#6b7488}
.sc-ft b{color:#a3e635;font-size:18px}
"""
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&'
         'family=JetBrains+Mono:wght@400;500;600&family=Noto+Sans+SC:wght@400;500;700&display=swap">')

SHARE_JS = r"""
(function(){
const H2C=['/assets/vendor/html2canvas.min.js','https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js','https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js'];
function toast(t){let e=document.querySelector('.toast');if(!e){e=document.createElement('div');e.className='toast';document.body.appendChild(e)}
 e.textContent=t;e.classList.add('on');clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove('on'),2600)}
function one(u){return new Promise((ok,no)=>{const s=document.createElement('script');s.src=u;s.onload=ok;s.onerror=()=>{s.remove();no()};document.head.appendChild(s)})}
async function lib(){if(window.html2canvas)return;for(const u of H2C){try{await one(u);if(window.html2canvas)return}catch(e){}}throw new Error('截图库加载失败，请检查网络')}
window.ucShare=async function(o){
 toast('正在生成长图…');
 const st=document.createElement('div');st.className='sc';
 st.innerHTML='<div class="sc-hd"><img src="/assets/avatar-96.png" alt=""><div><b>链上大叔研究台</b><i>uncleonchain.com · @Uncle_Web3PM</i></div>'+
  '<div class="sc-date">'+(o.date||'')+'</div></div><div class="sc-title">'+o.title+'</div>'+(o.sub?'<div class="sc-sub">'+o.sub+'</div>':'')+o.html+
  '<div class="sc-ft"><b>uncleonchain.com</b><span>@Uncle_Web3PM</span><span style="margin-left:auto">'+(o.src||'只给数据 · 不构成投资建议')+'</span></div>';
 document.body.appendChild(st);
 if(location.search.includes('sharepreview')){st.style.left='0';st.style.zIndex='999';return}
 try{await lib();await new Promise(r=>setTimeout(r,120));
  const c=await html2canvas(st,{scale:2,backgroundColor:'#05070c',useCORS:true,logging:false});
  const a=document.createElement('a');a.download=o.file||'uncleonchain.png';a.href=c.toDataURL('image/png');document.body.appendChild(a);a.click();a.remove();
  toast('长图已下载 ✓ 直接发推');
 }catch(e){toast('生成失败：'+e.message)}finally{st.remove()}
};
window.ucToast=toast;
})();
"""


def nav_html(active):
    def link(k, href, label):
        return f'<a href="{href}" class="{"on" if k == active else ""}">{icon(k)}{esc(label)}</a>'
    main = "".join(link(*x) for x in NAV_MAIN)
    more = "".join(link(*x) for x in NAV_MORE)
    upd = G.get("更新") or "—"
    return f"""<input type="checkbox" id="navtg" class="navtg">
<header class="topbar"><label for="navtg" aria-label="菜单"><svg viewBox="0 0 16 16" class="ic"><path d="M2 4h12M2 8h12M2 12h12"/></svg></label>
<a href="/"><img src="/assets/avatar-96.png" alt="">{esc(BRAND)}</a><span class="d">{esc(upd)} UTC</span></header>
<aside class="side">
<a class="brand" href="/"><img class="av" src="/assets/avatar-96.png" alt="链上大叔"><span><b>{esc(BRAND)}</b><i>UNCLE ONCHAIN · TERMINAL</i></span></a>
<nav class="snav"><div class="sgrp">Terminal</div>{main}<div class="sgrp">Records</div>{more}</nav>
<div class="sfoot"><div class="live"><i></i>数据更新 {esc(upd)} UTC</div>
<a href="{X_URL}" target="_blank" rel="noopener">𝕏 {esc(TWITTER)}</a><p>{esc(DISCLAIMER)}</p></div>
</aside><label for="navtg" class="scrim"></label>"""


def page(title, body, active="", desc="", extra_head="", narrow=False, share=False, scripts=""):
    d = esc(desc or SLOGAN)
    t = esc(title)
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{t}</title>
<meta name="description" content="{d}">
<meta name="theme-color" content="#05070c">
<meta property="og:title" content="{t}"><meta property="og:description" content="{d}">
<meta property="og:type" content="website"><meta property="og:site_name" content="{esc(BRAND)}">
<meta property="og:image" content="https://{DOMAIN}/assets/og.png">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:site" content="{TWITTER}">
<meta name="twitter:image" content="https://{DOMAIN}/assets/og.png">
<link rel="icon" href="/assets/favicon.ico" sizes="any"><link rel="icon" href="/assets/favicon-32.png" type="image/png" sizes="32x32">
<link rel="icon" href="/assets/favicon-192.png" type="image/png" sizes="192x192"><link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
{FONTS}
<style>{SITE_CSS}</style>
{extra_head}
</head>
<body>
{nav_html(active)}
<main class="main"><div class="mi{' narrow' if narrow else ''}">
{body}
</div>
<footer class="foot"><span>{esc(BRAND)}（{BRAND_EN}）</span><a href="{X_URL}">{esc(TWITTER)}</a>
<span>数据：DefiLlama · CoinMetrics · FRED · alternative.me · Hyperliquid · Deribit · CoinGecko · 链上节点</span><span>{esc(DISCLAIMER)}</span></footer>
</main>
{('<script>' + SHARE_JS + '</script>') if share else ''}
{scripts}
</body>
</html>
"""


def write(rel, text):
    p = os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


# ---------------------------------------------------------------- 格式与小图
f_usd = R.f_usd


def fmt_tok(v):
    if v is None:
        return "—"
    a = abs(v)
    return f"{v/1e6:.2f}M" if a >= 1e6 else (f"{v/1e3:.1f}K" if a >= 1e3 else f"{v:,.0f}")


def fmt_delta(v, pct_input=False):
    """v 为小数（0.05 = 5%）；pct_input=True 时 v 已是百分数。"""
    if v is None:
        return '<span class="d">—</span>'
    p = v if pct_input else v * 100
    cls = "up" if p > 0 else ("dn" if p < 0 else "")
    return f'<span class="d {cls}">{"▲" if p > 0 else ("▼" if p < 0 else "·")} {abs(p):.1f}%</span>'


def fmt_pct(v, dp=1):
    return "—" if v is None else f"{v*100:.{dp}f}%"


TONE_COLOR = {"up": "#00ffcc", "dn": "#ff3366", "warn": "#ffb020", "cool": "#5b8cff", "neutral": "#a7afc0"}


def spark(vals, color="#00ffcc", w=92, h=26, area=False):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return f'<svg class="spk" viewBox="0 0 {w} {h}"></svg>'
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or (abs(hi) or 1)
    n = len(vals)
    pts = [(w * i / (n - 1), h - (v - lo) / rng * h * .84 - h * .08) for i, v in enumerate(vals)]
    p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    fill = ""
    if area:
        gid = f"g{abs(hash((tuple(vals[-5:]), color))) % 10**8}"
        fill = (f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{color}" stop-opacity=".22"/>'
                f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
                f'<polygon points="0,{h} {p} {w},{h}" fill="url(#{gid})"/>')
    return (f'<svg class="spk" viewBox="0 0 {w} {h}" preserveAspectRatio="none">{fill}'
            f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linejoin="round" '
            f'stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>')


PALETTE = ["#00ffcc", "#5b8cff", "#ffb020", "#ff3366", "#c084fc", "#a3e635"]


def trend_chart(series, dates, h=250, fmt="usd", zero=True):
    """series: [(名称, {日期: 值})]。静态 SVG 多线图，端点标最新值。"""
    W, Lm, Rm, T, B = 880, 62, 16, 14, 30
    pw, ph = W - Lm - Rm, h - T - B
    vals = [v for _, s in series for d, v in s.items() if v is not None and d in set(dates)]
    if not vals or len(dates) < 2:
        return '<div class="empty">数据还在累积，暂时画不出图</div>'
    top = max(vals) * 1.06
    bot = 0 if zero else min(vals) * 0.97
    if top == bot:
        top = bot + 1
    n = len(dates)
    idx = {d: i for i, d in enumerate(dates)}
    X = lambda i: Lm + pw * i / (n - 1)              # noqa: E731
    Y = lambda v: T + ph * (1 - (v - bot) / (top - bot))  # noqa: E731
    fm = {"usd": f_usd, "price": lambda v: f"${v:,.0f}", "num": lambda v: (f"{v/1e3:,.0f}K" if abs(v) >= 1e4 else f"{v:,.1f}"), "pct": lambda v: f"{v:.1f}%"}[fmt]
    grid = ""
    for k in range(5):
        v = bot + (top - bot) * k / 4
        grid += (f'<line x1="{Lm}" y1="{Y(v):.1f}" x2="{Lm+pw}" y2="{Y(v):.1f}" class="gl"/>'
                 f'<text x="{Lm-8}" y="{Y(v)+4:.1f}" class="ax" text-anchor="end">{fm(v)}</text>')
    xl = "".join(f'<text x="{X(i):.1f}" y="{T+ph+20}" class="ax" text-anchor="middle">{dates[i][5:]}</text>'
                 for i in range(0, n, max(1, n // 6)))
    lines, leg = "", ""
    for k, (name, s) in enumerate(series):
        c = PALETTE[k % len(PALETTE)]
        pts = [(X(idx[d]), Y(v)) for d, v in sorted(s.items()) if d in idx and v is not None]
        if len(pts) >= 2:
            lines += (f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="none" stroke="{c}" '
                      f'stroke-width="1.7" stroke-linejoin="round"/>')
        if pts:
            lines += f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="3" fill="{c}"/>'
        last = [v for d, v in sorted(s.items()) if d in idx and v is not None]
        leg += f'<span><i style="background:{c}"></i>{esc(name)} <b>{fm(last[-1]) if last else "—"}</b></span>'
    return (f'<div class="legend">{leg}</div><div class="plot"><svg viewBox="0 0 {W} {h}" class="tsvg">'
            f'{grid}{lines}{xl}</svg></div>')


CHAIN_KEY = {"Solana": "solana", "BSC": "bsc", "Base": "base", "Robinhood Chain": "robinhood", "Arc": "arc", "Monad": "monad",
             "Ethereum": "ethereum", "X Layer": "xlayer", "Arbitrum": "arbitrum", "Avalanche": "avax", "Polygon": "polygon",
             "Hyperliquid L1": "hyperliquid", "TON": "ton", "Sonic": "sonic", "MegaETH": "megaeth", "Stable": "stable",
             "Unichain": "unichain", "Blast": "blast", "Linea": "linea", "Plasma": "plasma", "Ink": "ink", "Tron": "tron",
             "Near": "near", "Aptos": "aptos", "Hedera": "hedera", "OP Mainnet": "optimism", "ZKsync Era": "era"}
KEY_CHAIN = {v: k for k, v in CHAIN_KEY.items()}
MAIN_CHAINS = ["solana", "bsc", "robinhood", "base", "arc", "monad"]
CHAIN_COLOR = {"solana": "#c084fc", "bsc": "#fbbf24", "robinhood": "#4ade80", "base": "#60a5fa", "arc": "#22d3ee",
               "monad": "#a78bfa", "other": "#4b5364"}


def chain_badge(name):
    k = CHAIN_KEY.get(name, "")
    cls = k if k in ("solana", "robinhood", "bsc", "base", "arc", "monad", "ethereum") else ("bsc" if "BSC" in (name or "") else "other")
    short = {"Robinhood Chain": "Robinhood", "BSC + X Layer + Monad + RH": "BSC 系"}.get(name, name)
    return f'<span class="badge b-{cls}">{esc(short)}</span>'


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


def tone_chip(text, tone):
    return f'<span class="chip t-{tone}"><i></i>{esc(text)}</span>'


def hero_cards(S, as_of, sd):
    """首页四张核心卡：场外资金 / 发射台赛道 / 交易所筹码 / 情绪。"""
    cards = []
    r = R.reading(S, "stable_major", as_of)
    if r:
        net = r["变1"]
        cards.append(("稳定币 24h 净增发", "USDT+USDC", R.f_signed_usd(net),
                      f'30 日 {R.f_pct(r["涨30"], 2, True)} · 总量 {f_usd(r["值"])}', "up" if (net or 0) >= 0 else "dn", r["走势"]))
    else:
        cards.append(("稳定币 24h 净增发", "USDT+USDC", "—", "等待首次抓取", "neutral", []))
    if sd:
        tot = sd.get("赛道Top60") or {}
        seq = tot.get("序列") or {}
        ds = sorted(seq)
        chg = (seq[ds[-1]] / seq[ds[-2]] - 1) if len(ds) >= 2 and seq[ds[-2]] else None
        cards.append(("发射台赛道当日手续费", "Top60", f_usd(tot.get("当日")),
                      f'{fmt_delta(chg)} 日环比 · 截至 {sd["日期"]}', "up" if (chg or 0) >= 0 else "dn", [seq[d] for d in ds[-30:]]))
    f = R.reading(S, "ex_netflow", as_of)
    if f:
        w = R.sum_window(S, "ex_netflow", f["截至"], 7)
        cards.append(("交易所 BTC 净流量", "流入 − 流出", R.f_btc(f["值"], True),
                      f'7 日 {R.f_btc(w, True)} · {"净流出=提币" if (w or 0) < 0 else "净流入=潜在抛压"}',
                      "up" if (f["值"] or 0) < 0 else "dn", f["走势"][-30:]))
    else:
        cards.append(("交易所 BTC 净流量", "流入 − 流出", "—", "等待首次抓取", "neutral", []))
    g = R.judge(S, R.IND["fng"], as_of)
    if g:
        cards.append(("恐慌贪婪指数", "alternative.me", g["显示"], f'{g["区间"]} · 7 日前 {R.reading(S, "fng", as_of)["前7"] or "—"}',
                      g["tone"], g["走势"][-30:]))
    else:
        cards.append(("恐慌贪婪指数", "alternative.me", "—", "等待首次抓取", "neutral", []))
    out = ""
    for k, tag, v, s, tone, sp in cards:
        out += (f'<div class="glass hero"><div class="k">{esc(k)}<span>{esc(tag)}</span></div>'
                f'<div class="v t-{tone}">{v}</div><div class="s">{s}</div>{spark(sp, TONE_COLOR.get(tone, "#00ffcc"), 200, 34, area=True)}</div>')
    return out, cards


def verdict_block(log, link=True):
    if not log:
        return ('<div class="glass verdict"><div class="body"><div class="lbl">综合研判</div>'
                '<div class="txt">今日解读日志还没生成——宏观数据等待首次抓取（每天 UTC 10:20 自动跑）。</div></div></div>')
    tags = "".join(tone_chip(f'{lay["名称"]} · {lay["短"]}', lay["tone"]) for lay in log["层"])
    more = f'<a class="btn ghost" href="/journal/{log["日期"]}/">看今日完整解读 →</a>' if link else ""
    patch = '<span class="chip t-warn">补录</span>' if log.get("补录") else ""
    return (f'<div class="glass verdict"><div class="body"><div class="lbl">综合研判 · {log["日期"]} 解读日志 {patch}</div>'
            f'<div class="txt">{esc(log["综合"]["一句话"])}</div><div class="chips">{tags}</div></div>{more}</div>')


def signal_tiles(log):
    if not log:
        return ""
    out = ""
    for lay in log["层"]:
        meta = R.LAYERS[lay["层"]]
        items = "".join(f'<li><span>{esc(x["名称"])}</span><b class="t-{x["tone"]}">{esc(x["显示"])} · {esc(x["区间"])}</b></li>'
                        for x in [y for y in lay["读数"] if y["级别"] == "核心"][:3])
        out += (f'<a class="card sig t-{lay["tone"]}" href="/macro/#layer-{lay["层"]}"><div class="n">LAYER {lay["层"]} · {meta["频率"]}</div>'
                f'<div class="q">{esc(meta["名称"])}：{esc(meta["问"])}？</div><div class="v t-{lay["tone"]}">{esc(lay["结论"])}</div>'
                f'<ul>{items or "<li><span>数据不足</span></li>"}</ul></a>')
    return f'<div class="grid g4">{out}</div>'


def alert_board(log, title="异动预警看台", share_id=None):
    al = (log or {}).get("预警") or []
    ticker_items = []
    if log:
        for lay in log["层"]:
            for x in lay["读数"]:
                if x["级别"] == "核心":
                    ticker_items.append(f'<span>{esc(x["名称"])} <b class="t-{x["tone"]}">{esc(x["显示"])}</b> {esc(x["区间"])}</span>')
        lp = log.get("发射台") or {}
        for t in (lp.get("Top") or [])[:5]:
            ticker_items.append(f'<span>{esc(t["名称"])} 当日手续费 <b>{f_usd(t["当日"])}</b> '
                                f'{fmt_delta(t["日环比"], pct_input=True) if t.get("日环比") is not None else ""}</span>')
    track = "".join(ticker_items)
    ticker = f'<div class="ticker"><div class="ticker-track">{track}{track}</div></div>' if track else ""
    lis = "".join(f'<li><span class="lv {"h" if a["级别"] == "高" else "m"}">{"高" if a["级别"] == "高" else "中"}</span>{esc(a["文本"])}</li>' for a in al)
    body = f'<ul class="alerts">{lis}</ul>' if lis else '<div class="quiet">今天没有触发预警阈值（区间切换、稳定币单日 ±$1B、交易所单日 ±5,000 BTC、资金费率翻转、发射台异动等）。</div>'
    btn = f'<button class="btn" onclick="{share_id}()">📸 生成今日长图</button>' if share_id else ""
    return (f'<div class="card board"><div class="board-hd"><span class="dot"></span><b>{esc(title)}</b>'
            f'<span class="stamp">{(log or {}).get("日期", "")}</span><span class="sp"></span>{btn}</div>{ticker}{body}</div>')


def share_payload_home(log, cards):
    """首页 / 日志页长图内容（纯字符串，交给 ucShare 渲染）。"""
    k = "".join(f'<div class="sc-kpi"><div class="k">{esc(c[0])}</div><div class="v t-{c[4]}">{c[2]}</div></div>' for c in cards)
    chips = "".join(f'<span class="chip t-{lay["tone"]}" style="margin:0 8px 8px 0">{esc(lay["名称"])} · {esc(lay["短"])}</span>'
                    for lay in (log or {}).get("层", []))
    al = "".join(f'<li>{"🔴" if a["级别"] == "高" else "🟠"} {esc(a["文本"])}</li>' for a in (log or {}).get("预警", [])[:7])
    return (f'<div class="sc-kpis">{k}</div><div style="margin-bottom:20px">{chips}</div>'
            + (f'<div class="sc-box"><ul class="sc-al">{al}</ul></div>' if al else ""))


# ---------------------------------------------------------------- 首页：终端总览
def build_home(sd, S, logs, weeks, months, rot, matrix):
    today_log = logs[-1] if logs else None
    as_of = today_log["日期"] if today_log else (G.get("今天") or dt.date.today().isoformat())
    heroes, cards = hero_cards(S, as_of, sd)
    # 发射台 Top5（矩阵口径，全类目）
    lp_rows = ""
    if matrix:
        ps = sorted([p for p in matrix["协议"] if p.get("当日")], key=lambda p: -p["当日"])[:6]
        for i, p in enumerate(ps, 1):
            ch = "".join(chain_badge(c) for c in p["链"][:2])
            lp_rows += (f'<tr><td class="rk">{i}</td><td class="l"><span class="pname">{esc(p["名称"])}</span></td>'
                        f'<td class="l">{ch}</td><td>{f_usd(p["当日"])}</td><td>{fmt_delta(p.get("日环比"), pct_input=True)}</td></tr>')
    lp_tbl = (f'<div class="tw"><table><thead><tr><th class="l">#</th><th class="l">平台</th><th class="l">链</th><th>当日手续费</th>'
              f'<th>日环比</th></tr></thead><tbody>{lp_rows}</tbody></table></div>') if lp_rows else '<div class="empty">发射台数据待生成</div>'
    # 板块 Top6
    cats = ""
    if rot:
        last = rot[max(rot)]
        top = sorted(rot_clean(last)[0], key=lambda c: -c["24h"])[:6]
        for c in top:
            tone = "up" if c["24h"] >= 0 else "dn"
            cats += (f'<div class="card cat t-{tone}"><div class="nm">{esc(c["名称"])}</div>'
                     f'<div class="v t-{tone}">{c["24h"]:+.2f}%</div><div class="s">市值 {f_usd(c["市值"])}</div></div>')
    cats = f'<div class="grid g3">{cats}</div>' if cats else '<div class="empty">板块快照待生成</div>'
    # 日志列表
    items = ""
    for lg in reversed(logs[-6:]):
        n = len(lg.get("预警") or [])
        items += (f'<li><span class="d">{lg["日期"]}</span><span><a href="/journal/{lg["日期"]}/">每日解读</a>'
                  f'<span class="s">{esc(lg["综合"]["一句话"])}</span></span><span class="x chip">{n} 条预警</span></li>')
    for wk in reversed(weeks[-2:]):
        items += (f'<li><span class="d">{wk["标签"]}</span><span><a href="/journal/week/{wk["标签"]}/">周复盘</a>'
                  f'<span class="s">{esc(wk["一句话"])}</span></span></li>')
    for mo in reversed(months[-1:]):
        items += (f'<li><span class="d">{mo["标签"]}</span><span><a href="/journal/month/{mo["标签"]}/">月复盘</a>'
                  f'<span class="s">{esc(mo["一句话"])}</span></span></li>')
    jl = f'<div class="card"><ul class="list">{items}</ul></div>' if items else '<div class="empty">第一篇解读日志会在下一次每日运行时写入。</div>'
    share_obj = {"title": "今日链上终端 · 四层研判", "date": as_of,
                 "sub": (today_log or {}).get("综合", {}).get("一句话", ""), "html": share_payload_home(today_log, cards),
                 "file": f"uncleonchain-terminal-{as_of}.png"}
    body = f"""<div class="ph"><div><div class="eyebrow">Terminal Overview</div><h1>终端总览</h1>
<p class="lede">宏观流动性 → 周期位置 → 筹码结构 → 情绪，再落到发射台一级市场。每天 UTC 10:20 自动拉数、自动写解读日志，写入即冻结，公开可查。</p></div>
<div class="stamp">解读日期 <b>{as_of}</b><br>数据更新 <b>{esc(G.get("更新") or "—")} UTC</b></div></div>
{verdict_block(today_log)}
<div class="grid g4">{heroes}</div>
<h2>四层信号灯 <span class="sub">点进去看每个指标的读数、区间和走势</span></h2>
{signal_tiles(today_log) or '<div class="empty">宏观数据等待首次抓取。</div>'}
<h2>异动预警 <span class="sub">阈值规则见「口径与规则」</span></h2>
{alert_board(today_log, share_id="shareHome")}
<div class="grid g2" style="margin-top:22px;align-items:start">
<div><h2 style="margin-top:12px">发射台矩阵 · 当日 Top6 <a class="sub" href="/launchpad/">全部 {len((matrix or {}).get("协议", []))} 个协议 →</a></h2>{lp_tbl}</div>
<div><h2 style="margin-top:12px">板块轮动 · 24h 领涨 <a class="sub" href="/rotation/">看全部 →</a></h2>{cats}</div>
</div>
<h2>解读日志 <a class="sub" href="/journal/">全部日志与复盘 →</a></h2>
{jl}"""
    js = f"<script>function shareHome(){{ucShare({json.dumps(share_obj, ensure_ascii=False)})}}</script>"
    write("index.html", page(f"{BRAND} · 链上数据情报终端", body, active="home", share=True, scripts=js,
                             desc=(today_log or {}).get("综合", {}).get("一句话") or SLOGAN))


# ---------------------------------------------------------------- 宏观仪表盘
def build_macro(L, S, logs):
    log = logs[-1] if logs else None
    as_of = log["日期"] if log else G.get("今天")
    st = L.get("源状态") or {}
    src = "".join(tone_chip(f'{k} {"✓" if v.get("ok") else "✗"} {(v.get("最新日期") or "")[5:]}', "up" if v.get("ok") else "dn")
                  for k, v in st.items())
    sections = ""
    for i, meta in R.LAYERS.items():
        lay = next((x for x in (log or {}).get("层", []) if x["层"] == i), None)
        cards = ""
        for ind in [x for x in R.INDICATORS if x["层"] == i]:
            j = R.judge(S, ind, as_of) if as_of else None
            if not j:
                cards += (f'<div class="card ind"><div class="top"><span class="nm">{esc(ind["名称"])}<span class="lv">{ind["级别"]}</span></span></div>'
                          f'<div class="v t-neutral">—</div><div class="b">等待数据源（{esc(ind["来源"])}）</div>'
                          f'<details><summary>怎么读 ▸</summary>{esc(ind["说明"])}</details></div>')
                continue
            stale = f'<span class="stale">滞后 {R.days_between(j["截至"], as_of)} 天</span>' if j["过期"] else f'截至 {j["截至"][5:]}'
            cards += (f'<div class="card ind"><div class="top"><span class="nm">{esc(ind["名称"])}<span class="lv">{ind["级别"]}</span></span>'
                      f'{tone_chip(j["区间"], j["tone"])}</div><div class="v">{esc(j["显示"])}</div><div class="b">{esc(j["依据"])}</div>'
                      f'{spark(j["走势"], TONE_COLOR.get(j["tone"], "#a7afc0"), 240, 32, area=True)}'
                      f'<details><summary>怎么读 ▸</summary>{esc(ind["说明"])}</details>'
                      f'<div class="ft"><span>{esc(ind["来源"])}</span><span>{stale}</span></div></div>')
        pend = "".join(f'<div class="pend"><b>{esc(p["名称"])} · 待接入</b>{esc(p["原因"])}</div>' for p in R.PENDING if p["层"] == i)
        verdict = (f'{tone_chip(lay["结论"], lay["tone"])}' if lay else "")
        chart = ""
        if i == 1 and S.get("stable_major"):
            ds = sorted(S["stable_major"])[-365:]
            chart = ('<h3>USDT+USDC 总市值 · 1 年</h3>' +
                     trend_chart([("USDT+USDC", {d: S["stable_major"][d] for d in ds})], ds, zero=False))
        if i == 2 and S.get("btc_price") and S.get("realized_price"):
            ds = sorted(S["btc_price"])[-365:]
            chart = ('<h3>BTC 价格 vs 全网持币成本（Realized Price）· 1 年</h3>' +
                     trend_chart([("BTC 价格", {d: S["btc_price"][d] for d in ds}),
                                  ("Realized Price", {d: S["realized_price"].get(d) for d in ds})], ds, fmt="price", zero=False))
        if i == 3 and S.get("ex_netflow"):
            ds = sorted(S["ex_netflow"])[-120:]
            cum, acc = {}, 0
            for d in ds:
                acc += S["ex_netflow"][d]; cum[d] = acc
            chart = '<h3>交易所 BTC 累计净流量 · 120 天（向下 = 筹码持续离开交易所）</h3>' + trend_chart([("累计净流量(BTC)", cum)], ds, fmt="num", zero=False)
        if i == 4 and S.get("fng"):
            ds = sorted(S["fng"])[-365:]
            chart = '<h3>恐慌贪婪指数 · 1 年</h3>' + trend_chart([("F&G", {d: S["fng"][d] for d in ds})], ds, fmt="num")
        sections += f"""<section class="layer" id="layer-{i}">
<div class="layer-hd"><span class="no">L{i}</span><h2>{esc(meta["名称"])} <span class="sub">{esc(meta["问"])}？· {esc(meta["频率"])}</span></h2>{verdict}
<div class="why">{esc("；".join(lay["依据"])) if lay else ""}</div></div>
<div class="grid g4">{cards}</div>
{f'<div class="grid g4" style="margin-top:12px">{pend}</div>' if pend else ''}
{f'<div class="card" style="padding:14px 18px;margin-top:12px">{chart}</div>' if chart else ''}
</section>"""
    posts = ALL_POSTS["macro"]
    plist = "".join(f'<li><span class="d">{esc(x["日期"])}</span><span><a href="/macro/{x["slug"]}/">{esc(x["标题"])}</a>'
                    f'<span class="s">{esc(x["摘要"])}</span></span></li>' for x in posts)
    body = f"""<div class="ph"><div><div class="eyebrow">Macro · 4-Layer Framework</div><h1>宏观四层仪表盘</h1>
<p class="lede">大叔的四层框架：先看水（宏观流动性），再看贵不贵（周期定位），再看筹码在谁手里（交易所进出），最后看情绪会不会超调。
只放数据源免费、每天能更新、一眼能读懂的指标；框架里有但暂时没有稳定免费源的，明确标「待接入」，不拿近似值冒充。</p></div>
<div class="stamp">解读日期 <b>{as_of or "—"}</b><br>台账更新 <b>{esc(L.get("更新时间UTC") or "—")} UTC</b></div></div>
{verdict_block(log)}
<div class="src">{src}</div>
{sections}
<h2>宏观深度分析</h2>
{f'<div class="card"><ul class="list">{plist}</ul></div>' if plist else '<div class="empty">手写的宏观深度报告会发在这里。</div>'}"""
    write("macro/index.html", page(f"宏观四层仪表盘 · {BRAND}", body, active="macro", desc=(log or {}).get("综合", {}).get("一句话") or PILLARS[0]["desc"]))


# ---------------------------------------------------------------- 发射台矩阵
def group_of(chains):
    ks = [CHAIN_KEY.get(c, c.lower()) for c in chains]
    return ks


def build_launchpad(sd, matrix):
    if not matrix:
        write("launchpad/index.html", page(f"发射台矩阵 · {BRAND}", '<h1>发射台矩阵</h1><div class="empty">矩阵数据待生成（拉日度.py）。</div>', active="launchpad"))
        return
    ps = [p for p in matrix["协议"] if (p.get("30日") or 0) >= 1000 or (p.get("当日") or 0) >= 100]
    hist = matrix.get("历史") or {}
    hds = sorted(hist)[-30:]
    deep = {x["slug"]: f'/launchpad/platforms/{x["slug"]}/' for x in (sd or {}).get("平台", [])}
    # 按链汇总（分链当日 / 30 日精确拆分）
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
    bar = "".join(f'<i style="width:{ch_day[k]/tot_day*100:.2f}%;background:{CHAIN_COLOR[k]}" title="{KEY_CHAIN.get(k, k)}"></i>' for k in main)
    bar += f'<i style="width:{other/tot_day*100:.2f}%;background:{CHAIN_COLOR["other"]}"></i>'
    leg = "".join(f'<span><i style="background:{CHAIN_COLOR[k]}"></i>{esc(KEY_CHAIN.get(k, k))} <b>{f_usd(ch_day[k])}</b> {ch_day[k]/tot_day*100:.1f}%</span>' for k in main)
    leg += f'<span><i style="background:{CHAIN_COLOR["other"]}"></i>其他 <b>{f_usd(other)}</b> {other/tot_day*100:.1f}%</span>'
    active_n = sum(1 for p in matrix["协议"] if (p.get("当日") or 0) > 0)
    lead = max(matrix["协议"], key=lambda p: p.get("当日") or 0)
    lead_ch = main[0] if main else None
    kpis = [
        ("全类目当日手续费", f_usd(tot_day), fmt_delta((tot_day / tot_prev - 1) if tot_prev else None) + " 日环比"),
        ("7 日 / 30 日合计", f_usd(tot_7), f"30 日 {f_usd(tot_30)}"),
        ("当日活跃协议", f"{active_n}", f"DefiLlama Launchpad 类目共 {len(matrix['协议'])} 个"),
        ("当日第一", esc(lead["名称"]), f'{f_usd(lead.get("当日"))} · 占 {(lead.get("当日") or 0)/tot_day*100:.1f}%'),
        ("链份额第一", esc(KEY_CHAIN.get(lead_ch, lead_ch or "—")), f'{ch_day.get(lead_ch, 0)/tot_day*100:.1f}% 当日手续费' if lead_ch else ""),
    ]
    kh = "".join(f'<div class="glass hero"><div class="k">{k}</div><div class="v" style="font-size:21px">{v}</div><div class="s">{s}</div></div>' for k, v, s in kpis)
    rows = ""
    for p in ps:
        keys = [CHAIN_KEY.get(c, c.lower().replace(" ", "")) for c in p["链"]]
        grp = [k if k in MAIN_CHAINS else "other" for k in keys]
        sp = [hist[d].get(p["slug"]) for d in hds]
        link = deep.get(p["slug"])
        nm = (f'<a href="{link}">{esc(p["名称"])}</a> <span class="deep">深度</span>' if link else
              f'<a href="https://defillama.com/protocol/{esc(p["slug"])}" target="_blank" rel="noopener">{esc(p["名称"])}</a>')
        logo = f'<img src="{esc(p["logo"])}" alt="" loading="lazy" referrerpolicy="no-referrer">' if p.get("logo") else '<img alt="">'
        badges = "".join(chain_badge(c) for c in p["链"][:3]) + (f'<span class="badge b-other">+{len(p["链"])-3}</span>' if len(p["链"]) > 3 else "")
        attrs = {"name": p["名称"], "chains": ",".join(sorted(set(grp))), "chainnames": " / ".join(p["链"][:3]),
                 "d1": p.get("当日") or 0, "d7": p.get("7日") or 0, "d30": p.get("30日") or 0, "chg": p.get("日环比"),
                 "c1": json.dumps({k: round(v) for k, v in (p.get("分链当日") or {}).items()}),
                 "c30": json.dumps({k: round(v) for k, v in (p.get("分链30日") or {}).items()})}
        da = " ".join(f'data-{k}="{esc(v if v is not None else "")}"' for k, v in attrs.items())
        rows += (f'<tr {da}><td class="rk"></td><td class="l"><span class="pname">{logo}{nm}</span></td><td class="l">{badges}</td>'
                 f'<td data-col="d1" class="v1">{f_usd(p.get("当日"))}</td><td>{fmt_delta(p.get("日环比"), pct_input=True)}</td>'
                 f'<td data-col="d7" class="v7">{f_usd(p.get("7日"))}</td><td data-col="d30" class="v30">{f_usd(p.get("30日"))}</td>'
                 f'<td>{spark(sp, "#00ffcc" if (p.get("日环比") or 0) >= 0 else "#ff3366")}</td></tr>')
    chain_pills = '<button class="pill on" data-f="chain" data-v="all">全部</button>' + "".join(
        f'<button class="pill" data-f="chain" data-v="{k}">{esc(KEY_CHAIN.get(k, k))}<small>{ch_day[k]/tot_day*100:.0f}%</small></button>' for k in main
    ) + '<button class="pill" data-f="chain" data-v="other">其他链</button>'
    # 深度追踪平台（原 4 家 + Arc 自建链上口径）
    deep_rows = ""
    for x in (sd or {}).get("平台", []):
        deep_rows += (f'<tr><td class="l"><span class="pname"><a href="/launchpad/platforms/{x["slug"]}/">{esc(x["名称"])}</a></span></td>'
                      f'<td class="l">{chain_badge(x["链"])}</td><td>{"延迟" if x["延迟"] else f_usd(x["当日手续费"])}</td>'
                      f'<td>{fmt_delta(x["日环比"])}</td><td>{f_usd(x["7日均"])}</td><td>{f_usd(x["当日收入"])}</td>'
                      f'<td>{spark(list(x["手续费序列"].values())[-30:])}</td></tr>')
    arc = (sd or {}).get("Arc") or {}
    trend = ""
    if sd and sd.get("平台"):
        tds = sorted(set().union(*[x["手续费序列"].keys() for x in sd["平台"]]))[-90:]
        trend = trend_chart([(x["名称"], x["手续费序列"]) for x in sd["平台"]], tds)
    body = f"""<div class="ph"><div><div class="eyebrow">Launchpad Matrix</div><h1>发射台矩阵</h1>
<p class="lede">DefiLlama Launchpad 类目全部 {len(matrix['协议'])} 个协议的跨链手续费排行。按生态切流、按周期切换、按金额档筛黑马，
一键生成带水印的排行长图。口径统一用手续费（fees），日期是 UTC 完整日。</p></div>
<div class="stamp">数据截至 <b>{matrix["日期"]}</b>（UTC 完整日）<br>生成 <b>{esc(matrix.get("生成时间UTC", "")[:16].replace("T", " "))} UTC</b></div></div>
<div class="grid" style="grid-template-columns:repeat(5,minmax(0,1fr))" id="lpk">{kh}</div>
<div class="card" style="padding:14px 16px;margin-top:12px"><div style="display:flex;justify-content:space-between;font-size:12.5px"><b>生态份额 · 当日手续费按链拆分</b><span class="stamp">多链协议按 DefiLlama 分链数据精确拆分</span></div>
<div class="chainbar">{bar}</div><div class="chainleg">{leg}</div></div>
<h2>跨链排行 <span class="sub">点列名以外的筛选按钮切换视图；链接会记住当前筛选，可直接分享</span></h2>
<div class="glass fbar">
<div class="fg"><span class="fl">生态</span>{chain_pills}</div>
<div class="fg"><span class="fl">周期</span><button class="pill" data-f="p" data-v="d1">当日</button><button class="pill on" data-f="p" data-v="d7">7 日</button><button class="pill" data-f="p" data-v="d30">30 日</button></div>
<div class="fg"><span class="fl">金额档</span><button class="pill on" data-f="tier" data-v="all">全部</button><button class="pill" data-f="tier" data-v="big">主力 ≥$100K</button><button class="pill" data-f="tier" data-v="mid">腰部 $10K–100K</button><button class="pill" data-f="tier" data-v="small">黑马 &lt;$10K</button></div>
<span class="fcount" id="fcount"></span><button class="btn" onclick="shareMatrix()">📸 生成今日排行长图</button>
</div>
<div class="tw scroll"><table id="mx"><thead><tr><th class="l">#</th><th class="l">协议</th><th class="l">链</th><th data-col="d1">当日</th><th>日环比</th>
<th data-col="d7">7 日</th><th data-col="d30">30 日</th><th>30 日走势</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="tnote">金额档按当前选中周期的金额判断（选 7 日 / 30 日时按日均换算）。选了某条链时，当日和 30 日用 DefiLlama 分链数据精确拆分，
7 日按该协议 30 日分链占比折算（标 ≈）。「深度」= 本站逐日追踪的平台，点进去看协议收入、回购估值；其余链接到 DefiLlama。</p>
<h2>深度追踪平台 <span class="sub">逐日序列 + 协议收入 + 回购市盈率</span> <a class="sub" href="/launchpad/report/">看今日文字解读 →</a></h2>
<div class="tw"><table><thead><tr><th class="l">平台</th><th class="l">链</th><th>当日手续费</th><th>日环比</th><th>7 日均</th><th>当日协议收入</th><th>30 日走势</th></tr></thead><tbody>{deep_rows}</tbody></table></div>
<div class="card" style="padding:14px 18px;margin-top:12px"><h3 style="margin-top:0">深度追踪平台 · 90 天手续费</h3>{trend}</div>
<h2>Arc 整链观察 <span class="sub">本站链上节点自算口径（和 DefiLlama 口径不同，单独列）</span></h2>
<div class="card" style="padding:14px 18px;font-size:13px;color:var(--ink2)">Arc {esc(arc.get("日期") or "")}：发射台合计 <b class="num">{f_usd(arc.get("发射台手续费"))}</b> ·
全链手续费 <b class="num">{f_usd(arc.get("全链手续费"))}</b> · 升级条件 {esc(arc.get("升级条件") or "—")} ·
{len(arc.get("发射台") or [])} 家发射台，<a href="/launchpad/platforms/arc-{esc((arc.get("发射台") or [{}])[0].get("slug", ""))}/">逐个看 →</a></div>"""
    js = r"""<script>
(function(){
const tb=document.querySelector('#mx tbody'),rows=[...tb.rows],st={chain:'all',p:'d7',tier:'all'};
const pd={d1:1,d7:7,d30:30};
function fmt(v){const a=Math.abs(v);return a>=1e9?'$'+(v/1e9).toFixed(2)+'B':a>=1e6?'$'+(v/1e6).toFixed(2)+'M':a>=1e3?'$'+(v/1e3).toFixed(1)+'K':'$'+Math.round(v).toLocaleString()}
function val(r,p){const d=r.dataset,c=st.chain;
 if(c==='all')return +d[p]||0;
 const c1=JSON.parse(d.c1||'{}'),c30=JSON.parse(d.c30||'{}');
 const pick=(o)=>c==='other'?Object.entries(o).filter(([k])=>!MAIN.includes(k)).reduce((s,[,v])=>s+v,0):(o[c]||0);
 const t30=Object.values(c30).reduce((s,v)=>s+v,0)||1;
 if(p==='d1')return pick(c1); if(p==='d30')return pick(c30); return (+d.d7||0)*pick(c30)/t30;}
window.MAIN=%MAIN%;
function apply(){
 const vis=[];
 rows.forEach(r=>{const g=r.dataset.chains.split(',');
  const okC=st.chain==='all'||g.includes(st.chain);
  const v=val(r,st.p),avg=v/pd[st.p];
  const okT=st.tier==='all'||(st.tier==='big'&&avg>=1e5)||(st.tier==='mid'&&avg>=1e4&&avg<1e5)||(st.tier==='small'&&avg<1e4&&avg>0);
  r._v=v;r.style.display=(okC&&okT&&v>0)?'':'none';if(okC&&okT&&v>0)vis.push(r);
  if(st.chain!=='all'){r.querySelector('.v1').textContent=fmt(val(r,'d1'));r.querySelector('.v7').textContent='≈'+fmt(val(r,'d7'));r.querySelector('.v30').textContent=fmt(val(r,'d30'))}
  else{r.querySelector('.v1').textContent=fmt(+r.dataset.d1);r.querySelector('.v7').textContent=fmt(+r.dataset.d7);r.querySelector('.v30').textContent=fmt(+r.dataset.d30)}});
 vis.sort((a,b)=>b._v-a._v).forEach((r,i)=>{r.cells[0].textContent=i+1;tb.appendChild(r)});
 document.querySelectorAll('#mx [data-col]').forEach(c=>c.classList.toggle('hl',c.dataset.col===st.p));
 document.querySelectorAll('.pill[data-f]').forEach(b=>b.classList.toggle('on',st[b.dataset.f]===b.dataset.v));
 document.getElementById('fcount').textContent='显示 '+vis.length+' / '+rows.length;
 history.replaceState(null,'','#'+new URLSearchParams(st).toString());window._vis=vis;}
document.querySelectorAll('.pill[data-f]').forEach(b=>b.onclick=()=>{st[b.dataset.f]=b.dataset.v;apply()});
try{const h=new URLSearchParams(location.hash.slice(1));['chain','p','tier'].forEach(k=>{if(h.get(k))st[k]=h.get(k)})}catch(e){}
apply();
const lab={chain:{all:'全部生态',other:'其他链'},p:{d1:'当日',d7:'7 日',d30:'30 日'},tier:{all:'全部金额档',big:'主力 ≥$100K',mid:'腰部 $10K–100K',small:'黑马 <$10K'}};
window.shareMatrix=function(){
 const top=(window._vis||[]).slice(0,10);
 const cn=st.chain==='all'?lab.chain.all:(st.chain==='other'?lab.chain.other:(document.querySelector('.pill[data-v="'+st.chain+'"]').childNodes[0].textContent));
 let t='<div class="sc-box"><table><thead><tr><th class="l">#</th><th class="l">协议</th><th class="l">链</th><th>'+lab.p[st.p]+'手续费</th><th>日环比</th></tr></thead><tbody>';
 top.forEach((r,i)=>{const c=r.dataset.chg===''?null:+r.dataset.chg;
  t+='<tr><td class="rk">'+(i+1)+'</td><td class="l"><b>'+r.dataset.name+'</b></td><td class="l" style="color:#8c94a6">'+r.dataset.chainnames+'</td><td>'+((st.chain!=='all'&&st.p==='d7'&&r.dataset.chains.includes(','))?'≈':'')+fmt(r._v)+'</td><td class="d '+(c>0?'up':c<0?'dn':'')+'">'+(c==null?'—':(c>0?'▲ ':'▼ ')+Math.abs(c).toFixed(1)+'%')+'</td></tr>'});
 t+='</tbody></table></div>';
 const k=[...document.querySelectorAll('#lpk .hero')].slice(0,4).map(e=>'<div class="sc-kpi"><div class="k">'+e.querySelector('.k').textContent+'</div><div class="v">'+e.querySelector('.v').textContent+'</div></div>').join('');
 ucShare({title:'发射台矩阵 · '+lab.p[st.p]+'手续费 Top10',date:'%DATE%',sub:cn+' · '+lab.tier[st.tier]+' · DefiLlama Launchpad 类目 · 口径：手续费',
  html:'<div class="sc-kpis">'+k+'</div>'+t,file:'uncleonchain-launchpad-%DATE%.png',src:'数据：DefiLlama · 口径：fees'});
};
})();
</script>""".replace("%MAIN%", json.dumps(MAIN_CHAINS)).replace("%DATE%", matrix["日期"])
    write("launchpad/index.html", page(f"发射台矩阵 · 跨链 Launchpad 手续费排行 · {BRAND}", body, active="launchpad", share=True, scripts=js,
                                       desc=f'{matrix["日期"]} 发射台全类目当日手续费 {f_usd(tot_day)}，第一 {lead["名称"]}。'))


def build_launchpad_platforms(sd):
    if not sd:
        return
    tpl = lambda k, v, s="": f'<div class="glass hero"><div class="k">{k}</div><div class="v" style="font-size:21px">{v}</div><div class="s">{s}</div></div>'  # noqa: E731
    for x in sd["平台"]:
        sym = x.get("估值符号")
        val = (sd.get("估值") or {}).get(sym) if sym else None
        k = (tpl("当日手续费", "延迟" if x["延迟"] else f_usd(x["当日手续费"]), fmt_delta(x["日环比"]) + " 日环比")
             + tpl("7 日均", f_usd(x["7日均"]), fmt_delta(x["7日均环比"]) + " 周环比")
             + tpl("当日协议收入", f_usd(x["当日收入"]), f"分账比率 {fmt_pct(x['分账比率'])}")
             + tpl("赛道份额（Top60）", fmt_pct(x["占赛道份额"]), f"距单日峰值 {fmt_pct(x['距单日峰值'])}")
             + tpl("累计手续费", f_usd(x["累计"]), f"单日峰值 {x['峰值日'] or '—'}"))
        dates = sorted(set(x["手续费序列"]) | set(x["收入序列"]))
        chart = trend_chart([("手续费", x["手续费序列"]), ("协议收入", x["收入序列"])], dates)
        vb = ""
        if val:
            pe = lambda v: f"{v:.2f}x" if v else "—"  # noqa: E731
            vb = (f'<h2>估值（{sym}）</h2><div class="grid g3">'
                  + tpl("burn-adjusted 市值", f_usd(val.get("市值")))
                  + tpl("收入市盈率", pe(val.get("收入市盈率")))
                  + tpl("回购市盈率", pe(val.get("回购市盈率")), f"回购收益率 {fmt_pct(val.get('回购收益率'))}") + "</div>")
        body = f"""<div class="ph"><div><div class="eyebrow">Launchpad · 深度追踪</div><h1>{esc(x["名称"])} {chain_badge(x["链"])}</h1></div>
<div class="stamp">数据截至 <b>{sd["日期"]}</b></div></div>
<div class="grid" style="grid-template-columns:repeat(5,minmax(0,1fr))">{k}</div>
<div class="card" style="padding:14px 18px;margin-top:14px"><h3 style="margin-top:0">手续费 / 协议收入 · 180 天</h3>{chart}</div>
{vb}
<p style="margin-top:26px"><a class="btn ghost" href="/launchpad/">← 返回发射台矩阵</a></p>"""
        write(f'launchpad/platforms/{x["slug"]}/index.html', page(f'{x["名称"]} · 发射台 · {BRAND}', body, active="launchpad"))
    for z in (sd.get("Arc") or {}).get("发射台", []):
        k = (tpl("当日手续费", f_usd(z["当日手续费"])) + tpl("7 日合计", f_usd(z["7日"]))
             + tpl("30 日合计", f_usd(z["30日"])) + tpl("7 日 DEX 成交", f_usd(z["7日DEX"])))
        chart = trend_chart([("手续费", z["手续费序列"])], sorted(z["手续费序列"]))
        body = f"""<div class="ph"><div><div class="eyebrow">Launchpad · Arc 链上自算</div><h1>{esc(z["名称"])} {chain_badge("Arc")}</h1></div>
<div class="stamp">数据截至 <b>{sd["日期"]}</b></div></div>
<div class="grid g4">{k}</div>
<div class="card" style="padding:14px 18px;margin-top:14px"><h3 style="margin-top:0">手续费走势</h3>{chart}</div>
<p class="tnote">Arc 上不少发射台的 swap 走 Uniswap 底层池，DEX 成交记在 Uniswap 名下，这里的「DEX 成交」系统性偏低，看手续费更可靠。本页是本站链上节点自算口径，和 DefiLlama 数字可能不同。</p>
<p style="margin-top:20px"><a class="btn ghost" href="/launchpad/">← 返回发射台矩阵</a></p>"""
        write(f'launchpad/platforms/arc-{z["slug"]}/index.html', page(f'{z["名称"]}（Arc）· 发射台 · {BRAND}', body, active="launchpad"))


# 出看板.py 的叙事报告嵌入：它自带一套 CSS 变量，这里在同一选择器上覆盖成终端配色
REPORT_OVERRIDE = r"""
:root,:root[data-theme="dark"]{--bg:#05070c;--panel:#0b0e17;--ink:#e8ecf3;--ink2:#a7afc0;--muted:#6b7488;--rule:rgba(255,255,255,.07);
--rule2:rgba(255,255,255,.12);--grid:rgba(255,255,255,.06);--accent:#a3e635;--accent-soft:rgba(163,230,53,.07);--up:#00ffcc;--dn:#ff3366;
--s1:#00ffcc;--s2:#ff7a45;--s3:#5b8cff;--s4:#ffb020;--s7:#c084fc;--sk:#6b7488;--good:#00ffcc;--warn:#ffb020;color-scheme:dark}
.rpt body,.rpt{font-family:Inter,"Noto Sans SC",-apple-system,"PingFang SC",sans-serif}
.rpt h1{font:700 26px/1.25 Inter,"Noto Sans SC",sans-serif}.rpt h2{font:600 18px/1.35 Inter,"Noto Sans SC",sans-serif}
figure.chart{margin:0;min-width:0}.plot{position:relative;overflow-x:auto}.plot svg{display:block;width:100%;min-width:520px;height:auto}
"""


def build_launchpad_report(sd):
    if not sd:
        return
    extra = f'<style>{sd["css"]}\n{REPORT_OVERRIDE}</style>'
    scripts = f'<script type="application/json" id="chart-data">{sd["chart_json"]}</script><script>{sd["js"]}</script>'
    note = (f'<p class="tnote">← <a href="/launchpad/">发射台矩阵</a> ｜ 本期永久存档 <a href="/launchpad/report/{sd["日期"]}/">/launchpad/report/{sd["日期"]}/</a>'
            f' ｜ <a href="/launchpad/report/archive/">全部往期 →</a></p>')
    body = f'<div class="rpt">{sd["正文"]}{note}</div>'
    h = page(f'发射台日更 · 文字解读 · {sd["日期"]} · {BRAND}', body, active="launchpad", extra_head=extra, desc=sd["一句话"], scripts=scripts)
    write("launchpad/report/index.html", h)
    write(f'launchpad/report/{sd["日期"]}/index.html', h)
    ds = sorted([d for d in os.listdir(os.path.join(SITE, "launchpad", "report")) if re.match(r"^\d{4}-\d{2}-\d{2}$", d)], reverse=True)
    lis = "".join(f'<li><span class="d">{d}</span><a href="/launchpad/report/{d}/">发射台日更 · 文字解读</a></li>' for d in ds)
    write("launchpad/report/archive/index.html", page(f"发射台文字解读往期 · {BRAND}",
          f'<div class="eyebrow">Archive</div><h1>发射台文字解读 · 往期</h1><p class="lede">共 {len(ds)} 期，UTC 完整日为单位。</p>'
          f'<div class="card" style="margin-top:18px"><ul class="list">{lis}</ul></div>', active="launchpad", narrow=True))


# ---------------------------------------------------------------- 板块轮动 / 叙事埋伏
def post_list(slug):
    posts = ALL_POSTS[slug]
    if not posts:
        return '<div class="empty">还没有发第一篇。写好会第一时间发在这里。</div>'
    li = "".join(f'<li><span class="d">{esc(x["日期"])}</span><span><a href="/{slug}/{x["slug"]}/">{esc(x["标题"])}</a>'
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
            w = f' · 7 日 {(c["市值"]/p7[c["id"]]-1)*100:+.1f}%' if c["id"] in p7 and p7[c["id"]] else ""
            vc = f' · 成交额环比 {(c["成交额"]/v1[c["id"]]-1)*100:+.0f}%' if v1.get(c["id"]) else ""
            return (f'<div class="card cat t-{tone}"><div class="nm" title="{esc(c["名称"])}">{esc(c["名称"])}</div>'
                    f'<div class="v t-{tone}">{c["24h"]:+.2f}%</div><div class="s">市值 {f_usd(c["市值"])} · 成交 {f_usd(c["成交额"])}{w}{vc}</div>'
                    f'<div class="t3">{esc(" · ".join(c.get("前三") or []))}</div></div>')
        grid = "".join(card(c) for c in sorted(big, key=lambda c: -c["24h"])[:16])
        lose = "".join(card(c) for c in sorted(big, key=lambda c: c["24h"])[:8])
        meta = (f'快照 {dates[-1]} · 共 {len(last)} 个类目（市值 ≥ $50M），这里只看市值 ≥ $300M 的 {len(big)} 个 · '
                f'历史快照 {len(dates)} 天' + ("（满 7 天后显示 7 日轮动）" if not prev7 else "")
                + (" · 疑似成分调整、未进排行：" + "、".join(f"{c['名称']} {c['24h']:+.0f}%" for c in odd[:6]) if odd else ""))
    body = f"""<div class="ph"><div><div class="eyebrow">Sector Rotation</div><h1>板块轮动</h1>
<p class="lede">{esc(PILLARS[1]["desc"])} 类目口径来自 CoinGecko，一个币可以同时属于多个类目，看相对强弱，不要把类目市值加总。</p></div></div>
{f'<p class="tnote">{meta}</p>' if meta else ''}
<h2>24h 领涨赛道</h2>{f'<div class="grid g4">{grid}</div>' if grid else '<div class="empty">板块快照待生成。</div>'}
<h2>24h 领跌赛道</h2>{f'<div class="grid g4">{lose}</div>' if lose else ''}
<h2>轮动复盘</h2>{post_list("rotation")}"""
    write("rotation/index.html", page(f"板块轮动 · {BRAND}", body, active="rotation", desc=PILLARS[1]["desc"]))


RADAR = [
    ("Smart Money 钱包监控", "先从本站已有的链上管道做起：Robinhood Chain / Arc 发射台的大户地址逐笔追踪（RPC 已接通），再扩到 Solana / BSC。免费标签数据不稳定，不拿猜测当结论。"),
    ("未发币高热度协议雷达", "DefiLlama 协议列表里「没有代币」的协议 × 手续费 / TVL 增速做筛选，找有真实收入、还没发币的项目。"),
    ("巨鲸埋伏", "BTC 层面的交易所净流量已在宏观第三层上线；山寨币层面需要逐币持仓分布，筹备中。"),
]


def build_narrative():
    cards = "".join(f'<div class="pend"><b>{esc(t)} · 筹备中</b>{esc(d)}</div>' for t, d in RADAR)
    body = f"""<div class="ph"><div><div class="eyebrow">Narrative Radar</div><h1>叙事埋伏</h1>
<p class="lede">{esc(PILLARS[2]["desc"])}</p></div></div>
<h2>雷达 <span class="sub">数据源接通一个上线一个</span></h2><div class="grid g3">{cards}</div>
<h2>观察笔记</h2>{post_list("narrative")}"""
    write("narrative/index.html", page(f"叙事埋伏 · {BRAND}", body, active="narrative", desc=PILLARS[2]["desc"]))


def build_posts():
    for p in PILLARS:
        for x in ALL_POSTS[p["slug"]]:
            back = f'<p style="margin-top:30px"><a class="btn ghost" href="/{p["slug"]}/">← 返回{esc(p["nav"])}</a></p>'
            if x["kind"] == "html":
                body, extra = x["html"] + back, (f"<style>{x['css']}</style>" if x["css"] else "")
            else:
                body = (f'<div class="eyebrow">{esc(p["nav"])}</div><h1>{esc(x["标题"])}</h1><p class="stamp" style="text-align:left">{esc(x["日期"])}</p>'
                        f'<div class="article" style="margin-top:18px">{x["html"]}</div>{back}')
                extra = ""
            write(f'{p["slug"]}/{x["slug"]}/index.html',
                  page(f'{x["标题"]} · {BRAND}', body, active=p["slug"], desc=x["摘要"], extra_head=extra, narrow=x["kind"] == "md"))


# ---------------------------------------------------------------- 解读日志
def readings_table(lay):
    trs = "".join(f'<tr><td class="l">{esc(x["名称"])} <span class="badge b-other">{x["级别"]}</span></td><td>{esc(x["显示"])}</td>'
                  f'<td class="l">{tone_chip(x["区间"], x["tone"])}</td><td class="l" style="font-family:var(--sans);color:var(--ink2)">{esc(x["依据"])}</td>'
                  f'<td>{x["截至"][5:]}{" ⚠" if x["过期"] else ""}</td></tr>' for x in lay["读数"])
    return (f'<div class="tw"><table><thead><tr><th class="l">指标</th><th>读数</th><th class="l">区间</th><th class="l">依据</th><th>数据日</th></tr></thead>'
            f'<tbody>{trs or "<tr><td class=l colspan=5>数据不足</td></tr>"}</tbody></table></div>')


def build_journal(S, logs, weeks, months, sd):
    idx = {lg["日期"]: i for i, lg in enumerate(logs)}
    for lg in logs:
        i = idx[lg["日期"]]
        prev_ = logs[i - 1]["日期"] if i > 0 else None
        next_ = logs[i + 1]["日期"] if i + 1 < len(logs) else None
        layers = ""
        for lay in lg["层"]:
            layers += (f'<h3>L{lay["层"]} · {esc(lay["名称"])} {tone_chip(lay["结论"], lay["tone"])}</h3>{readings_table(lay)}')
        lp = lg.get("发射台") or {}
        lp_html = ""
        if lp:
            trs = "".join(f'<tr><td class="l">{esc(t["名称"])}</td><td class="l">{chain_badge(t["链"])}</td><td>{f_usd(t["当日"])}</td>'
                          f'<td>{fmt_delta(t["日环比"], pct_input=True)}</td><td>{R.f_pct(t["份额"], 1)}</td></tr>' for t in lp.get("Top") or [])
            lp_html = (f'<h2>发射台 <span class="sub">{lp.get("日期")} 完整日 · Top60 赛道 {f_usd(lp.get("赛道当日"))} '
                       f'{fmt_delta(lp.get("赛道日环比"), pct_input=True)}</span></h2>'
                       f'<div class="tw"><table><thead><tr><th class="l">平台</th><th class="l">链</th><th>当日手续费</th><th>日环比</th><th>赛道份额</th></tr></thead>'
                       f'<tbody>{trs}</tbody></table></div><p class="tnote">{esc(lp.get("一句话") or "")}</p>')
        cm = commentary(lg["日期"])
        srcs = "".join(tone_chip(f'{k} {"✓" if v.get("ok") else "✗"}', "up" if v.get("ok") else "dn") for k, v in (lg.get("数据源") or {}).items())
        miss = f'<p class="tnote">当天缺失的核心指标：{esc("、".join(lg["核心缺失"]))}</p>' if lg.get("核心缺失") else ""
        patch = f'<p class="tnote">⚠ 本篇为补录：首次生成于 {esc(lg.get("首次生成UTC") or "")} UTC，当天数据源晚到后按冻结规则覆盖一次。</p>' if lg.get("补录") else ""
        heroes, cards = hero_cards(S, lg["日期"], sd if lg is logs[-1] else None)
        share_obj = {"title": f"链上终端 · {lg['日期']} 解读", "date": lg["日期"], "sub": lg["综合"]["一句话"],
                     "html": share_payload_home(lg, cards), "file": f"uncleonchain-journal-{lg['日期']}.png"}
        body = f"""<div class="ph"><div><div class="eyebrow">Daily Log · 每日解读</div><h1>{lg["日期"]} 解读日志</h1></div>
<div class="stamp">生成于 <b>{esc(lg["生成时间UTC"])} UTC</b><br>写入即冻结 · 规则见「口径与规则」</div></div>
{verdict_block(lg, link=False)}
{patch}
<h2>大叔点评</h2>{f'<div class="cmt article">{cm}</div>' if cm else '<div class="empty">今天没有人工点评，上面是规则化自动解读。</div>'}
<h2>异动预警</h2>{alert_board(lg, title="当日预警", share_id="shareLog")}
<h2>四层读数</h2>{layers}
{miss}
{lp_html}
<h2>数据源状态</h2><div class="src">{srcs}</div>
<div class="pager">{f'<a href="/journal/{prev_}/">← {prev_}</a>' if prev_ else '<span></span>'}<a href="/journal/">全部日志</a>{f'<a href="/journal/{next_}/">{next_} →</a>' if next_ else '<span></span>'}</div>"""
        js = f"<script>function shareLog(){{ucShare({json.dumps(share_obj, ensure_ascii=False)})}}</script>"
        write(f'journal/{lg["日期"]}/index.html', page(f'{lg["日期"]} 解读日志 · {BRAND}', body, active="journal", share=True,
                                                     scripts=js, desc=lg["综合"]["一句话"]))

    def review_page(rv, kind_slug, title):
        rows = "".join(f'<tr><td class="l">{esc(x["名称"])}</td><td>{esc(x["期初"])}</td><td>{esc(x["期末"])}</td><td>{esc(x["变化"])}</td>'
                       f'<td>{esc(x["低"])} ~ {esc(x["高"])}</td><td class="l">{esc(x["期初区间"])} → {tone_chip(x["期末区间"], x["tone"])}</td></tr>'
                       for x in rv["指标"])
        vrows = "".join(f'<tr><td class="l">L{v["层"]} · {esc(v["名称"])}</td><td class="l">{esc(v["期初"])} → {esc(v["期末"])}</td>'
                        f'<td class="l" style="font-family:var(--sans)">{esc("、".join(f"{k}×{n}" for k, n in v["分布"].items()) or "—")}</td>'
                        f'<td>{v["切换次数"]}</td></tr>' for v in rv["结论"])
        al = "".join(f'<li><span class="d">{a["日期"][5:]}</span><span class="lv {"h" if a["级别"] == "高" else "m"}">{a["级别"]}</span>{esc(a["文本"])}</li>' for a in rv["预警"])
        lp = rv.get("发射台") or {}
        prow = "".join(f'<tr><td class="l">{esc(p["名称"])}</td><td>{f_usd(p["期间"])}</td><td>{f_usd(p["上期"])}</td>'
                       f'<td>{fmt_delta(p["变化"], pct_input=True)}</td></tr>' for p in lp.get("平台") or [])
        cm = commentary(rv["标签"])
        return f"""<div class="ph"><div><div class="eyebrow">{kind_slug.title()} Review</div><h1>{title}</h1>
<p class="lede">{rv["起"]} ~ {rv["止"]} · 期间日志 {rv["日志天数"]} 篇</p></div><div class="stamp">生成于 <b>{esc(rv["生成时间UTC"])} UTC</b></div></div>
<div class="glass verdict"><div class="body"><div class="lbl">一句话复盘</div><div class="txt">{esc(rv["一句话"])}</div></div></div>
<h2>大叔点评</h2>{f'<div class="cmt article">{cm}</div>' if cm else '<div class="empty">人工复盘点评待补充（content/journal/' + esc(rv["标签"]) + '.md）。</div>'}
<h2>核心指标区间变化</h2><div class="tw"><table><thead><tr><th class="l">指标</th><th>期初</th><th>期末</th><th>变化</th><th>区间低 ~ 高</th><th class="l">区间判定</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>各层结论分布</h2><div class="tw"><table><thead><tr><th class="l">层</th><th class="l">期初 → 期末</th><th class="l">分布（天数）</th><th>切换次数</th></tr></thead><tbody>{vrows}</tbody></table></div>
<h2>发射台 <span class="sub">赛道 Top60 期间合计 {f_usd(lp.get("赛道期间合计"))} · 较上期 {fmt_delta(lp.get("赛道变化"), pct_input=True)}</span></h2>
<div class="tw"><table><thead><tr><th class="l">平台</th><th>期间手续费</th><th>上期</th><th>变化</th></tr></thead><tbody>{prow}</tbody></table></div>
<h2>期间预警（{len(rv["预警"])} 条）</h2>{f'<div class="card"><ul class="alerts">{al}</ul></div>' if al else '<div class="empty">期间没有触发预警。</div>'}
<p style="margin-top:26px"><a class="btn ghost" href="/journal/">← 全部日志</a></p>"""

    for wk in weeks:
        write(f'journal/week/{wk["标签"]}/index.html', page(f'{wk["标签"]} 周复盘 · {BRAND}', review_page(wk, "week", f'{wk["标签"]} 周复盘'),
                                                        active="journal", desc=wk["一句话"]))
    for mo in months:
        write(f'journal/month/{mo["标签"]}/index.html', page(f'{mo["标签"]} 月复盘 · {BRAND}', review_page(mo, "month", f'{mo["标签"]} 月复盘'),
                                                         active="journal", desc=mo["一句话"]))
    dl = "".join(f'<li><span class="d">{lg["日期"]}</span><span><a href="/journal/{lg["日期"]}/">{esc(lg["综合"]["一句话"])}</a>'
                 f'<span class="s">{" ".join(tone_chip(x["短"], x["tone"]) for x in lg["层"])}</span></span>'
                 f'<span class="x chip">{len(lg.get("预警") or [])} 预警</span></li>' for lg in reversed(logs))
    wl = "".join(f'<li><span class="d">{w["标签"]}</span><span><a href="/journal/week/{w["标签"]}/">{esc(w["一句话"])}</a>'
                 f'<span class="s">{w["起"]} ~ {w["止"]}</span></span></li>' for w in reversed(weeks))
    ml = "".join(f'<li><span class="d">{m["标签"]}</span><span><a href="/journal/month/{m["标签"]}/">{esc(m["一句话"])}</a></span></li>' for m in reversed(months))
    body = f"""<div class="ph"><div><div class="eyebrow">Journal</div><h1>解读日志</h1>
<p class="lede">每天 UTC 10:20 自动拉数后，按「口径与规则」里公开的区间规则写一篇解读日志：四层读数、各层结论、综合研判、发射台、异动预警。
<b>写入即冻结</b>——历史日志不改，唯一例外是当天数据源晚到、重跑后核心缺失变少，会覆盖一次并标「补录」。
每周一自动出上一周的周复盘，每月 1 日出上个月的月复盘。大叔的人工点评单独标注，和自动解读分开。</p></div></div>
<h2>月复盘</h2>{f'<div class="card"><ul class="list">{ml}</ul></div>' if ml else '<div class="empty">第一篇月复盘会在下个月 1 日自动生成。</div>'}
<h2>周复盘</h2>{f'<div class="card"><ul class="list">{wl}</ul></div>' if wl else '<div class="empty">第一篇周复盘会在下周一自动生成。</div>'}
<h2>每日解读</h2>{f'<div class="card"><ul class="list">{dl}</ul></div>' if dl else '<div class="empty">第一篇日志会在下一次每日运行时写入。</div>'}"""
    write("journal/index.html", page(f"解读日志 · {BRAND}", body, active="journal", desc="每日规则化解读 + 周复盘 + 月复盘，写入即冻结，公开可查。"))


# ---------------------------------------------------------------- 口径 / 更正 / 关于
def build_methodology():
    lp_rows = "".join(f"<tr><td class='l'>{esc(k)}</td><td class='l' style='white-space:normal;font-family:var(--sans)'>{esc(v)}</td></tr>" for k, v in [
        ("统计口径", "发射台一律用手续费（fees），不用成交量；成交量口径覆盖不全，会系统性低估份额。"),
        ("统计周期", "只报「昨天」这一个 UTC 完整日；当天数据永远不完整，不进正文。"),
        ("发射台矩阵", "DefiLlama Launchpad 类目全部协议；多链协议的分链数字用 DefiLlama 分链拆分；30 日走势来自本站逐日台账。"),
        ("赛道份额", "深度追踪平台的份额分母是 Top60 当日总量（和文字解读一致）；矩阵页的份额分母是全类目。"),
        ("延迟处理", "某个数据源没出昨天的数，标「延迟」，不拿旧值顶替、不记 0。"),
        ("Flap / StonkFun", "Flap 是税代币模型、StonkFun 的 fees 只记平台自己那份，跨平台比较用协议收入。"),
        ("PONS 销毁", "转到 0x…dEaD 地址，不是调用 burn()，市值一律按 burn-adjusted 流通计。"),
        ("绝不做的事", "不拿历史峰值和现在比来判断一个平台是否「死了」；只给数据，不给买卖建议。"),
    ])
    macro = ""
    for i, meta in R.LAYERS.items():
        trs = ""
        for ind in [x for x in R.INDICATORS if x["层"] == i]:
            zones = "；".join(f"{a} → {b}" for a, b in ind["区间"])
            scored = "计分" if ind["级别"] == "核心" and ind["key"] not in ("fred_t10y2y", "realized_price", "nupl") else "不计分"
            trs += (f"<tr><td class='l'><b>{esc(ind['名称'])}</b><br><span class='stamp' style='text-align:left'>{esc(ind['来源'])}</span></td>"
                    f"<td class='l'>{ind['级别']} · {scored}</td><td class='l' style='white-space:normal;font-family:var(--sans)'>{esc(ind['说明'])}</td>"
                    f"<td class='l' style='white-space:normal;font-family:var(--sans)'>按{esc(ind['依据'])}：{esc(zones)}</td></tr>")
        macro += (f"<h3>L{i} · {esc(meta['名称'])}（{esc(meta['问'])}？）</h3><div class='tw'><table><thead><tr><th class='l'>指标</th>"
                  f"<th class='l'>级别</th><th class='l'>怎么读</th><th class='l'>区间规则</th></tr></thead><tbody>{trs}</tbody></table></div>")
    pend = "".join(f"<tr><td class='l'>L{p['层']}</td><td class='l'>{esc(p['名称'])}</td><td class='l' style='white-space:normal;font-family:var(--sans)'>{esc(p['原因'])}</td></tr>" for p in R.PENDING)
    body = f"""<div class="eyebrow">Methodology</div><h1>口径与规则</h1>
<p class="lede">解读日志里的每一个判断都来自下面这些公开规则。规则改动会在更正记录里留痕，历史日志不跟着改。</p>
<h2>层结论怎么来</h2>
<div class="card" style="padding:16px 20px;font-size:13.5px;color:var(--ink2)">
<p style="margin:0 0 8px"><b style="color:var(--ink)">L1 流动性</b>：核心指标（稳定币 30 日增速、实际利率 20 日变化、广义美元 20 日变化、期货升水）各打 −1~+2 分，合计 ≥2 扩张、≤−2 收缩，其余中性。利差只做衰退信号提示，不计分。</p>
<p style="margin:0 0 8px"><b style="color:var(--ink)">L2 周期</b>：以 MVRV Z-Score 所在区间为周期位置（缺失时退回 MVRV）。NUPL、Realized Price 与 MVRV 同源，只展示不重复计分。</p>
<p style="margin:0 0 8px"><b style="color:var(--ink)">L3 筹码</b>：以交易所 BTC 7 日净流量为准：净流出 = 筹码离开交易所，净流入 = 留意抛压。框架里的 URPD / STH 系列暂无免费源，明示待接入。</p>
<p style="margin:0"><b style="color:var(--ink)">L4 情绪</b>：恐慌贪婪（−2~+2）、资金费率（−1~+2）、未平仓 7 日变化（−1~+1）合计 ≥3 过热、1~2 偏热、≤−2 偏冷，其余中性。</p></div>
<h2>异动预警阈值</h2>
<div class="card" style="padding:16px 20px;font-size:13.5px;color:var(--ink2)">核心指标区间切换 · USDT+USDC 单日净增发 / 赎回 ≥ $1B · 交易所单日 BTC 净流量 ≥ 5,000 枚 ·
资金费率正负翻转 · 10Y 实际利率单日变动 ≥ 10bp · Pi Cycle Top 触发 · 发射台赛道单日 ±25% · 发射台当日第一易主 · 深度追踪平台日环比超 ±60%。</div>
<h2>宏观四层 · 指标与区间</h2>{macro}
<h2>框架里暂未接入的指标</h2><div class="tw"><table><thead><tr><th class="l">层</th><th class="l">指标</th><th class="l">原因 / 计划</th></tr></thead><tbody>{pend}</tbody></table></div>
<h2>解读日志规则</h2>
<div class="card" style="padding:16px 20px;font-size:13.5px;color:var(--ink2)">日志日期 = 解读当天（UTC），每个读数带自己的数据日期（FRED 按美国工作日、交易所余额约有 2 周滞后，超过容忍天数标 ⚠）。
写入即冻结；同一天重跑且核心缺失变少才覆盖一次并标「补录」。周复盘按 ISO 周（周一至周日），月复盘按自然月。人工点评放在 content/journal/，单独标注。</div>
<h2>发射台口径</h2><div class="tw"><table><tbody>{lp_rows}</tbody></table></div>"""
    write("methodology/index.html", page(f"口径与规则 · {BRAND}", body, active="methodology"))


def build_corrections(sd, fixes):
    rows = "".join(f"<tr><td class='l'>{esc(f['日期'])}</td><td>{f['旧值']:,.0f} → {f['新值']:,.0f}</td>"
                   f"<td class='l'>{esc(f.get('口径', ''))}</td><td>{esc(f['修正时间UTC'][:10])}</td></tr>"
                   for f in sorted(fixes, key=lambda x: x["日期"], reverse=True)[:60])
    rev = [a for a in (sd or {}).get("异常", []) if "修订" in a or "延迟" in a]
    rn = ("<h2>近期数据源变动</h2><div class='card'><ul class='alerts'>" + "".join(f"<li>{esc(a)}</li>" for a in rev) + "</ul></div>") if rev else ""
    body = f"""<div class="eyebrow">Corrections</div><h1>更正记录</h1>
<p class="lede">数据源事后修订、PONS 销毁口径重算、规则调整，全部留痕，不覆盖不删除。</p>{rn}
<h2>PONS 逐日销毁重算记录</h2><div class="tw"><table><thead><tr><th class="l">日期</th><th>旧值 → 新值</th><th class="l">口径</th><th>修正时间</th></tr></thead>
<tbody>{rows or '<tr><td class="l" colspan="4">暂无</td></tr>'}</tbody></table></div>"""
    write("corrections/index.html", page(f"更正记录 · {BRAND}", body, active="corrections"))


def build_about():
    body = f"""<div class="eyebrow">About</div>
<div style="display:flex;gap:18px;align-items:center;margin-top:8px"><img src="/assets/favicon-192.png" alt="" style="width:84px;height:84px;border-radius:50%;box-shadow:0 0 0 2px var(--lime)">
<div><h1>关于{esc(BRAND)}</h1><p class="stamp" style="text-align:left">{esc(DOMAIN)} · <a href="{X_URL}">{esc(TWITTER)}</a></p></div></div>
<div class="article" style="margin-top:22px">
<p>写这个站的人在 web3 做了快十年，做过项目运营、产品设计，也做过 AMM DEX。现在把自己的研究方式搬到台面上：
先看宏观流动性（水多不多），再看周期位置（贵不贵），再看筹码结构（谁在进出交易所），再看情绪（会不会超调），最后落到发射台一级市场——每天赚多少钱、钱从哪来。</p>
<p>所有判断都按公开规则自动生成，每天一篇解读日志，写入即冻结；每周、每月再复盘一次。对了错了都留在这里，不做事后诸葛亮。</p>
<p>{esc(DISCLAIMER)}</p></div>"""
    write("about/index.html", page(f"关于 · {BRAND}", body, active="about", narrow=True))


def build_misc(logs, weeks, months):
    write("404.html", page(f"页面不存在 · {BRAND}", '<h1>页面不存在</h1><p class="lede">链接可能过期了，回<a href="/">终端总览</a>看看。</p>'))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: https://{DOMAIN}/sitemap.xml\n")
    urls = ["/", "/macro/", "/launchpad/", "/rotation/", "/narrative/", "/journal/", "/methodology/", "/corrections/", "/about/",
            "/launchpad/report/", "/launchpad/report/archive/"]
    for p in PILLARS:
        urls += [f'/{p["slug"]}/{x["slug"]}/' for x in ALL_POSTS[p["slug"]]]
    rd = os.path.join(SITE, "launchpad", "report")
    if os.path.isdir(rd):
        urls += [f"/launchpad/report/{d}/" for d in os.listdir(rd) if re.match(r"^\d{4}-\d{2}-\d{2}$", d)]
    pd_ = os.path.join(SITE, "launchpad", "platforms")
    if os.path.isdir(pd_):
        urls += [f"/launchpad/platforms/{d}/" for d in os.listdir(pd_)]
    urls += [f'/journal/{x["日期"]}/' for x in logs] + [f'/journal/week/{x["标签"]}/' for x in weeks] + [f'/journal/month/{x["标签"]}/' for x in months]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "".join(f"<url><loc>https://{DOMAIN}{u}</loc></url>\n" for u in sorted(set(urls))) + "</urlset>\n")
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
    build_home(sd, S, logs, weeks, months, rot, matrix)
    build_macro(L, S, logs)
    build_launchpad(sd, matrix)
    build_launchpad_platforms(sd)
    build_launchpad_report(sd)
    build_rotation(rot)
    build_narrative()
    build_posts()
    build_journal(S, logs, weeks, months, sd)
    build_methodology()
    build_corrections(sd, fixes)
    build_about()
    build_misc(logs, weeks, months)
    n = sum(1 for _, _, fs in os.walk(SITE) for f in fs if f == "index.html")
    print(f"网站已生成到 {SITE}（{n} 个页面；日志 {len(logs)} 篇、周复盘 {len(weeks)}、月复盘 {len(months)}）")


if __name__ == "__main__":
    main()
