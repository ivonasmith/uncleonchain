#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""链上大叔研究台 · 静态网站生成器
读：build/网站素材.json（出看板.py 产出，发射台日更的正文/图表/CSS）
    content/posts/*.md 或 *.html（人写的板块文章，宏观/轮动/叙事币三块靠这个）
写：site/ 下的全部静态页面（首页、四个板块、日更归档、口径、更正记录、关于）

设计语言：编辑体报告风（Georgia/Songti SC 衬线大标题、暖白底、金色强调色、蓝/红/绿三色 callout、
KPI 方块、SVG 手绘图表），和用户推特分析报告 / 交易计划表同一套视觉系统，定义在 REPORT_CSS 里，
全站（首页、四板块、口径、更正记录、关于）与发射台看板嵌入页共用。

四个板块，写作方式不同：
  发射台日更   全自动，出看板.py 每天产出，这里只负责套壳发布 + 存档一份到 launchpad/<日期>/
  宏观流动性   半自动占位，等接入指标后走和发射台一样的自动产出（也接受 content/posts/macro 手写深度报告）
  板块轮动复盘 纯手写：稿子放进 content/posts/rotation/，跑一次本脚本就发布
  叙事币埋伏   纯手写：同上，放进 content/posts/narrative/

文章有两种来源，同一个目录，按扩展名自动识别：
  .md    轻量笔记。文件名任意，格式：
         ---
         标题: ...
         日期: 2026-09-28
         摘要: 一句话，列表页用
         ---
         正文（支持基本 Markdown：# 标题、**粗体**、*斜体*、`代码`、- 列表、> 引用、[链接](url)；
         也可以直接写整段原样 HTML，比如用 REPORT_CSS 里的 .callout/.kpis/.hook 拼组件）
  .html  完整定制报告（比如 Polar/Claude 生成的、带 SVG 图表的分析长文）。整份自解释的 HTML，
         保留它自己的 <style>，本脚本只提取 <body> 内容并套站点导航/页脚；标题/日期/摘要从文件
         <head> 里的 <!--meta 标题: ...\n日期: ...\n摘要: ...--> 注释读，没写就退回 <title> 和文件时间。

用法：
  python3 出网站.py            # 读 build/网站素材.json + content/posts/，全量重建 site/
退出码：0 正常；1 缺少 build/网站素材.json（先跑 出看板.py）
"""
import os, sys, re, json, glob, html, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # 仓库根目录
BUILD = os.path.join(ROOT, "build")
CONTENT = os.path.join(ROOT, "content", "posts")
SITE = os.path.join(ROOT, "site")

BRAND = "链上大叔研究台"
BRAND_EN = "Uncle Onchain"
SLOGAN = "宏观流动性 → BTC/ETH → 板块轮动 → 发射台 / 低位叙事"
DOMAIN = "uncleonchain.com"
TWITTER = "@Uncle_Web3PM"
DISCLAIMER = "本站只给数据和复盘记录，不构成任何投资建议；不对任何交易结果负责。"

PILLARS = [
    {"slug": "launchpad", "nav": "发射台日更", "icon": "🚀",
     "desc": "pump.fun、Pons、StonkFun、Flap 逐日手续费与协议收入，PONS 链上销毁与回购市盈率，Arc 链整链观察。",
     "auto": True, "planned": False},
    {"slug": "macro", "nav": "宏观流动性", "icon": "🌊",
     "desc": "美元流动性、美债利率、稳定币供给这些宏观指标，和 BTC / ETH 的相关系数——先看水位，再看币价。",
     "auto": False, "planned": True},
    {"slug": "rotation", "nav": "板块轮动复盘", "icon": "🔄",
     "desc": "高波动窗口里板块轮动的交易复盘：进出场理由、事后对错、当时没看到的信息。",
     "auto": False, "planned": False},
    {"slug": "narrative", "nav": "叙事币埋伏", "icon": "🔍",
     "desc": "低位叙事币的观察笔记：为什么进、仓位怎么摆、后续怎么跟踪——过程记录，不是喊单。",
     "auto": False, "planned": False},
]
PMAP = {p["slug"]: p for p in PILLARS}


def load(p, default=None):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def esc(s):
    return html.escape(str(s), quote=False)


# ---------------------------------------------------------------- Markdown（够用就行，不追求覆盖全部语法；
#                                                                     一段以 < 开头的原样 HTML 直接透传，不转义）
def md_inline(s):
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", s)
    s = re.sub(r"`([^`]+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def md_to_html(src):
    lines, out, para, ul, quote, raw = src.split("\n"), [], [], [], [], []

    def flush_para():
        if para:
            out.append(f"<p>{md_inline(' '.join(para))}</p>")
            para.clear()

    def flush_ul():
        if ul:
            out.append("<ul>" + "".join(f"<li>{md_inline(x)}</li>" for x in ul) + "</ul>")
            ul.clear()

    def flush_quote():
        if quote:
            out.append(f"<blockquote>{md_inline(' '.join(quote))}</blockquote>")
            quote.clear()

    def flush_raw():
        if raw:
            out.append("\n".join(raw))
            raw.clear()

    in_raw = False
    for ln in lines:
        t = ln.strip()
        if in_raw:
            if not t:
                flush_raw(); in_raw = False
            else:
                raw.append(ln)
            continue
        if not t:
            flush_para(); flush_ul(); flush_quote(); continue
        if t.startswith("<"):                                    # 原样 HTML 透传（比如手拼 .callout/.kpis）
            flush_para(); flush_ul(); flush_quote()
            raw.append(ln); in_raw = True
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", t)
        if m:
            flush_para(); flush_ul(); flush_quote()
            n = len(m.group(1)) + 1        # 文章内标题从 h2 起，别盖过页面 h1
            out.append(f"<h{n}>{md_inline(m.group(2))}</h{n}>")
            continue
        if t.startswith("- "):
            flush_para(); flush_quote(); ul.append(t[2:]); continue
        if t.startswith(">"):
            flush_para(); flush_ul(); quote.append(t.lstrip("> ")); continue
        flush_ul(); flush_quote(); para.append(t)
    flush_para(); flush_ul(); flush_quote(); flush_raw()
    return "\n".join(out)


def parse_post_md(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if not m:
        return None
    meta = {}
    for ln in m.group(1).split("\n"):
        if ":" in ln:
            k, v = ln.split(":", 1)
            meta[k.strip()] = v.strip()
    body = m.group(2).strip()
    slug = re.sub(r"[^a-z0-9\-]+", "-", os.path.splitext(os.path.basename(path))[0].lower()).strip("-")
    meta.setdefault("标题", slug)
    meta.setdefault("日期", dt.date.today().isoformat())
    meta.setdefault("摘要", "")
    meta.update({"slug": slug, "kind": "md", "html": md_to_html(body), "css": ""})
    return meta


def parse_post_html(path):
    """完整定制报告（Polar/Claude 生成的自解释 HTML）：保留它自己的 <style>，只提取 <body> 内容套站点壳。
    标题/日期/摘要从 <!--meta 标题: ...\\n日期: ...\\n摘要: ...--> 注释读，没写就退回 <title> / 文件时间。"""
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


def parse_post(path):
    return parse_post_html(path) if path.endswith(".html") else parse_post_md(path)


def load_posts(pillar_slug):
    d = os.path.join(CONTENT, pillar_slug)
    posts = []
    if os.path.isdir(d):
        for f in sorted(glob.glob(os.path.join(d, "*.md")) + glob.glob(os.path.join(d, "*.html"))):
            p = parse_post(f)
            if p:
                posts.append(p)
    posts.sort(key=lambda p: p["日期"], reverse=True)
    return posts


ALL_POSTS = {p["slug"]: load_posts(p["slug"]) for p in PILLARS}

# ---------------------------------------------------------------- 壳（导航 / 页脚 / CSS，四个板块共用）
# 编辑体报告风：和用户推特分析报告 / 交易计划表同一套视觉系统——Georgia/Songti SC 细衬线大标题、
# 暖白底、金色强调、蓝/红/绿三色 callout、KPI 方块、手绘 SVG 图表。深色模式按同一套关系换色。
SITE_CSS = r"""
:root{--bg:#fffefc;--panel:#f7f4ee;--ink:#26221e;--ink2:#3d3730;--muted:#7a736b;--rule:#ece7e0;--rule2:#d8d2c9;
--accent:#8a6d1f;--accent-soft:#fdf9ef;--card:#ffffff;
--blue:#15628f;--blue-soft:#eef5fa;--red:#c02128;--red-soft:#fdf4f4;--green:#3f6b4c;--green-soft:#f4faf5;
color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#18140f;--panel:#221d16;--ink:#efe9e0;--ink2:#cfc6b8;
--muted:#9c9284;--rule:#332c22;--rule2:#463c2e;--accent:#dcae4b;--accent-soft:#2b2416;--card:#1f1a13;
--blue:#6fa9ec;--blue-soft:#182430;--red:#ef7d7a;--red-soft:#301a19;--green:#7dbf94;--green-soft:#152a1c;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#18140f;--panel:#221d16;--ink:#efe9e0;--ink2:#cfc6b8;--muted:#9c9284;--rule:#332c22;
--rule2:#463c2e;--accent:#dcae4b;--accent-soft:#2b2416;--card:#1f1a13;
--blue:#6fa9ec;--blue-soft:#182430;--red:#ef7d7a;--red-soft:#301a19;--green:#7dbf94;--green-soft:#152a1c;color-scheme:dark}
*{box-sizing:border-box}
html,body{background:var(--bg)}
body{margin:0;color:var(--ink);font:16px/1.72 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
a{color:inherit}
.site-nav{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--rule);
display:flex;align-items:center;gap:20px;padding:14px 20px;flex-wrap:wrap}
.site-nav .brand{font:400 17px/1 Georgia,"Songti SC","STSong",serif;text-decoration:none;color:var(--ink);white-space:nowrap}
.site-nav .links{display:flex;gap:16px;flex-wrap:wrap;font-size:13.5px}
.site-nav .links a{text-decoration:none;color:var(--ink2)}
.site-nav .links a:hover,.site-nav .links a.on{color:var(--accent)}
.wrap{max-width:900px;margin:0 auto;padding-inline:20px;padding-block:40px 72px}
.wrap.wide{max-width:1180px}
.eyebrow{font-size:12px;letter-spacing:.14em;color:var(--accent);font-weight:600;text-transform:uppercase}
h1{font:400 40px/1.24 Georgia,"Songti SC","STSong",serif;letter-spacing:-.3px;margin:8px 0 10px;text-wrap:balance}
h2{font:400 26px/1.32 Georgia,"Songti SC","STSong",serif;letter-spacing:-.2px;margin:40px 0 8px}
h3{font:600 16.5px/1.4 -apple-system,"PingFang SC",sans-serif;margin:26px 0 8px}
.meta{color:var(--muted);font-size:13px;padding-bottom:22px;border-bottom:2px solid var(--ink)}
.lede{font-size:16.5px;color:var(--ink2);max-width:66ch;margin:0 0 8px}
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--rule);
border:1px solid var(--rule);border-radius:10px;overflow:hidden;margin-top:30px}
.card{background:var(--card);padding:22px 24px;text-decoration:none;color:inherit;display:block}
.card:hover{background:var(--panel)}
.card .ic{font-size:21px}
.card h3{margin:9px 0 5px;font:600 17px/1.3 -apple-system,"PingFang SC",sans-serif}
.card p{margin:0;color:var(--ink2);font-size:13.5px;line-height:1.6}
.card .tag{display:inline-block;margin-top:11px;font-size:11px;letter-spacing:.4px;color:var(--muted);
border:1px solid var(--rule2);border-radius:999px;padding:2px 10px}
.card .tag.live{color:var(--accent);border-color:var(--accent)}
.postlist{list-style:none;padding:0;margin:20px 0}
.postlist li{padding:16px 0;border-bottom:1px solid var(--rule)}
.postlist a{text-decoration:none;font:600 16px/1.4 -apple-system,"PingFang SC",sans-serif}
.postlist a:hover{color:var(--accent)}
.postlist .d{color:var(--muted);font-size:12.5px;font-family:ui-monospace,Menlo,monospace;margin-right:10px}
.postlist .s{display:block;color:var(--ink2);font-size:13.5px;margin-top:4px}
.empty{background:var(--panel);border-radius:8px;padding:22px 24px;color:var(--ink2);font-size:14px;margin-top:18px}
.article{max-width:70ch}
.article p{margin:0 0 14px}
.article blockquote{margin:0 0 14px;padding:8px 18px;border-left:3px solid var(--accent);color:var(--ink2);background:var(--panel);border-radius:0 8px 8px 0}
.article code{background:var(--panel);padding:1px 5px;border-radius:4px;font-family:ui-monospace,Menlo,monospace;font-size:.9em}
.article ul{padding-left:22px}
.article li{margin:0 0 7px}
.datelist{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.datelist a{font-size:13px;font-family:ui-monospace,Menlo,monospace;padding:5px 12px;border:1px solid var(--rule2);
border-radius:999px;text-decoration:none;color:var(--ink2)}
.datelist a:hover{color:var(--accent);border-color:var(--accent)}
.tbl{overflow-x:auto;margin-top:10px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:8px 10px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:11.5px;letter-spacing:.5px;text-transform:uppercase}
td.num,th.num{text-align:right;font-family:ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}
tr:hover td{background:var(--panel)}
.site-footer{border-top:1px solid var(--rule);color:var(--muted);font-size:12.5px;padding:24px 20px;text-align:center}
.site-footer a{color:var(--muted)}

/* ---- 报告组件：md 文章里可以直接手拼这些 class，出看板.py 生成的 .html 报告自带同名/同构组件 ---- */
.lead{font-size:18px;line-height:1.7;color:var(--ink2);margin:0 0 24px}
.tldr{border:1px solid var(--rule2);border-radius:8px;padding:22px 26px;margin:0 0 30px;background:var(--accent-soft)}
.tldr h4{margin:0 0 14px;font:700 13px/1 -apple-system,sans-serif;letter-spacing:1.2px;color:var(--accent);text-transform:uppercase}
.tldr ol{margin:0;padding-left:20px;font-size:15.5px}
.tldr li{margin:0 0 9px}
.hook{border:1px solid var(--rule2);border-left:5px solid var(--blue);border-radius:8px;padding:26px 30px;margin:0 0 24px;
background:linear-gradient(160deg,var(--blue-soft) 0%,var(--accent-soft) 100%)}
.hook .q{font:400 28px/1.3 Georgia,"Songti SC",serif;margin:0 0 14px;color:var(--blue)}
.hook p{font-size:16px;margin:0 0 12px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--rule2);
border:1px solid var(--rule2);border-radius:8px;overflow:hidden;margin:24px 0 28px}
.kpi{background:var(--blue-soft);padding:16px 14px}
.kpi .k{font-size:11px;letter-spacing:.6px;color:var(--muted);text-transform:uppercase;margin-bottom:5px}
.kpi .v{font:400 26px/1.1 Georgia,serif;letter-spacing:-.4px}
.kpi .s{font-size:12px;color:var(--muted);margin-top:3px}
.callout{border-left:3px solid var(--accent);background:var(--accent-soft);padding:16px 20px;margin:22px 0;font-size:15px}
.callout h4{margin:0 0 7px;font-size:13.5px;letter-spacing:.4px;color:var(--accent);font-weight:700}
.callout.blue{border-color:var(--blue);background:var(--blue-soft)} .callout.blue h4{color:var(--blue)}
.callout.red{border-color:var(--red);background:var(--red-soft)} .callout.red h4{color:var(--red)}
.callout.gray,.callout.green{border-color:var(--green);background:var(--green-soft)} .callout.gray h4,.callout.green h4{color:var(--green)}
.callout p:last-child{margin:0}
.chart-fig{margin:22px 0 28px;padding:0}
.chart-cap{font:600 14.5px/1.45 -apple-system,"PingFang SC",sans-serif;color:var(--ink);margin:0 0 10px;
padding-left:11px;border-left:3px solid var(--accent)}
.chart-fig svg{display:block;width:100%;height:auto}
.fnote{font-size:12.5px;color:var(--muted);margin-top:8px;line-height:1.6}
.sign{margin-top:40px;border:1.5px solid var(--ink);padding:18px 22px;display:flex;
justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}
.sign .l{font-size:14px;color:var(--ink2);max-width:520px}
.sign .r{text-align:right;line-height:1.35}
.sign .nm{font:400 16px Georgia,"Songti SC",serif;color:var(--ink)}
.sign .hd2{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--muted);margin-top:2px}

@media (max-width:720px){.cards{grid-template-columns:1fr}h1{font-size:29px}
.kpis{grid-template-columns:repeat(2,1fr)}.kpi .v{font-size:22px}}
"""
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700&'
         'family=Noto+Sans+SC:wght@400;500;600;700&display=swap">')


def nav(active=""):
    items = "".join(f'<a href="/{p["slug"]}/" class="{"on" if p["slug"]==active else ""}">{esc(p["nav"])}</a>'
                     for p in PILLARS)
    items += (f'<a href="/methodology/" class="{"on" if active=="methodology" else ""}">口径</a>'
              f'<a href="/corrections/" class="{"on" if active=="corrections" else ""}">更正记录</a>'
              f'<a href="/about/" class="{"on" if active=="about" else ""}">关于</a>')
    return f'<nav class="site-nav"><a class="brand" href="/">{esc(BRAND)}</a><div class="links">{items}</div></nav>'


FOOTER = (f'<footer class="site-footer">{esc(BRAND)}（{BRAND_EN}）｜ {esc(TWITTER)} ｜ 数据源：DefiLlama · '
          f'CoinGecko · GeckoTerminal · DexScreener · Robinhood Chain / Arc 链上节点<br>{esc(DISCLAIMER)}</footer>')


def page(title, body, active="", desc="", extra_head="", wide=False):
    d = esc(desc or SLOGAN)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{d}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{d}">
<meta property="og:type" content="website">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
{FONTS}
<style>{SITE_CSS}</style>
{extra_head}
</head>
<body>
{nav(active)}
<div class="wrap{' wide' if wide else ''}">
{body}
</div>
{FOOTER}
</body>
</html>
"""


def write(rel, html_text):
    p = os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(html_text)


def dd(s):
    return f"{s[5:7]}-{s[8:10]}"


# ---------------------------------------------------------------- 首页
def build_home(site_data):
    cards = ""
    for p in PILLARS:
        if p["slug"] == "launchpad" and site_data:
            tag = f'<span class="tag live">日更 · 截至 {site_data["日期"]}</span>'
        elif p["planned"]:
            tag = '<span class="tag">筹备接入</span>'
        else:
            n = len(ALL_POSTS[p["slug"]])
            tag = f'<span class="tag live">{n} 篇</span>' if n else '<span class="tag">敬请期待</span>'
        cards += (f'<a class="card" href="/{p["slug"]}/"><div class="ic">{p["icon"]}</div>'
                  f'<h3>{esc(p["nav"])}</h3><p>{esc(p["desc"])}</p>{tag}</a>')
    snap = ""
    if site_data:
        snap = (f'<h2>今日一览 · {site_data["日期"]}</h2><p class="lede" style="font-size:14px">'
                f'{esc(site_data["一句话"])}</p><p><a href="/launchpad/">看完整日更 →</a></p>')
    body = f"""<div class="eyebrow">链上一级市场与宏观数据研究</div>
<h1>{esc(BRAND)}</h1>
<p class="lede">{esc(SLOGAN)}。一个 web3 链上数据分析师的公开台账：宏观流动性怎么传导到 BTC / ETH，
板块怎么轮动，发射台每天赚多少钱，叙事币在哪个位置埋伏——只给数据和过程记录，不给买卖建议。</p>
<div class="cards">{cards}</div>
{snap}"""
    write("index.html", page(BRAND, body, desc=SLOGAN))


# ---------------------------------------------------------------- 板块落地页（含手写文章列表）
def build_pillar_landing(p, site_data):
    posts = ALL_POSTS[p["slug"]]
    extra = ""
    if p["slug"] == "launchpad" and site_data:
        extra = (f'<div class="empty">最新一期是 {site_data["日期"]}（UTC 完整日），'
                 f'<a href="/launchpad/">点开看完整看板</a>；下面是往期归档。</div>')
    if posts:
        li_parts = []
        for x in posts:
            summary_html = f'<span class="s">{esc(x["摘要"])}</span>' if x["摘要"] else ""
            li_parts.append(f'<li><span class="d">{esc(x["日期"])}</span>'
                             f'<a href="/{p["slug"]}/{x["slug"]}/">{esc(x["标题"])}</a>{summary_html}</li>')
        postlist = f'<ul class="postlist">{"".join(li_parts)}</ul>'
    elif p["planned"]:
        postlist = '<div class="empty">这块还在筹备接入宏观指标，会做成和发射台一样的自动日更 / 周更。</div>'
    else:
        postlist = '<div class="empty">这块是手写复盘，还没有发第一篇。写好会第一时间发在这里。</div>'
    body = f"""<div class="eyebrow">{esc(p["icon"])} 板块</div>
<h1>{esc(p["nav"])}</h1>
<p class="lede">{esc(p["desc"])}</p>
{extra}
{postlist}"""
    write(f'{p["slug"]}/index.html', page(f'{p["nav"]} · {BRAND}', body, active=p["slug"], desc=p["desc"]))


def build_posts(p):
    for x in ALL_POSTS[p["slug"]]:
        backlink = f'<p style="margin-top:32px"><a href="/{p["slug"]}/">← 返回{esc(p["nav"])}</a></p>'
        if x["kind"] == "html":
            # 完整定制报告：已经自带 h1/meta/正文排版，不再套 eyebrow/h1，只加返回链接；
            # 它自己的 <style> 放进 extra_head，比 SITE_CSS 晚出现，同选择器优先用它的，保真度不丢。
            body = x["html"] + backlink
            extra_head = f"<style>{x['css']}</style>" if x["css"] else ""
        else:
            body = (f'<div class="eyebrow">{esc(p["nav"])}</div>\n<h1>{esc(x["标题"])}</h1>\n'
                    f'<div class="meta">{esc(x["日期"])}</div>\n'
                    f'<div class="article" style="margin-top:22px">{x["html"]}</div>\n{backlink}')
            extra_head = ""
        write(f'{p["slug"]}/{x["slug"]}/index.html',
              page(f'{x["标题"]} · {BRAND}', body, active=p["slug"], desc=x["摘要"], extra_head=extra_head))


# 发射台看板嵌入网站时的重上色：出看板.py 自己那份 CSS（给 Notion/Artifact 用）保持不动，
# 这段只在网站版的 <style> 里跟在它后面，把同名的 CSS 变量和字体规则改成编辑体报告的暖色系。
LAUNCHPAD_OVERRIDE = r"""
:root{--bg:#fffefc;--panel:#f7f4ee;--ink:#26221e;--ink2:#3d3730;--muted:#7a736b;--rule:#ece7e0;--rule2:#d8d2c9;
--grid:#f4f1ec;--accent:#8a6d1f;--accent-soft:#fdf9ef;--up:#15628f;--dn:#c02128;
--s1:#15628f;--s2:#c02128;--s3:#3f6b4c;--s4:#8a6d1f;--s7:#5a4b7a;--sk:#9a938a;
--good:#3f6b4c;--warn:#8a6d1f;color-scheme:light}
body{font-family:-apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
h1{font:400 36px/1.2 Georgia,"Songti SC","STSong",serif}
h2{font:400 22px/1.3 Georgia,"Songti SC","STSong",serif}
"""


# ---------------------------------------------------------------- 发射台 · 今日文字解读（编辑体报告，存档用）
def build_launchpad_report(site_data):
    """完整的叙事版报告（出看板.py 原样产出的那份，含口径提醒、回购市盈率解释这些文字），
    挪到 /launchpad/report/，作为终端式总览页之外「看数据背后怎么想」的深度阅读入口。"""
    css = (site_data["css"]
           + "\nfigure.chart{margin:0;min-width:0}.plot{position:relative;overflow-x:auto}"
             ".plot svg{display:block;width:100%;min-width:520px;height:auto}"
           + LAUNCHPAD_OVERRIDE)   # 站点版重上色，跟在 出看板.py 自己的 CSS 后面，同选择器后来居上
    extra_head = f'<style>{css}</style>'
    inner = site_data["正文"]
    scripts = f'<script type="application/json" id="chart-data">{site_data["chart_json"]}</script><script>{site_data["js"]}</script>'
    dated_note = (f'<p style="margin:14px 0 0;font-size:13px;color:var(--muted)">'
                  f'← <a href="/launchpad/">发射台总览</a> ｜ 这一期永久存档在 '
                  f'<a href="/launchpad/report/{site_data["日期"]}/">/launchpad/report/{site_data["日期"]}/</a>'
                  f' ｜ <a href="/launchpad/report/archive/">看全部往期 →</a></p>')
    full_body = f'<div class="wrap">{inner}{dated_note}</div>{scripts}'
    html_out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>发射台日更 · 文字解读 · {site_data["日期"]} · {esc(BRAND)}</title>
<meta name="description" content="{esc(site_data["一句话"])}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
{FONTS}
<style>{SITE_CSS}</style>
{extra_head}
</head>
<body>
{nav("launchpad")}
{full_body}
{FOOTER}
</body>
</html>
"""
    write("launchpad/report/index.html", html_out)
    write(f'launchpad/report/{site_data["日期"]}/index.html', html_out)
    dates = sorted([d for d in os.listdir(os.path.join(SITE, "launchpad", "report"))
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", d)], reverse=True)
    links = "".join(f'<a href="/launchpad/report/{d}/">{d}</a>' for d in dates)
    arc_body = (f'<div class="eyebrow">🚀 板块</div><h1>发射台日更 · 文字解读往期</h1>'
                f'<p class="lede">共 {len(dates)} 期，UTC 完整日为单位，每天一期。</p>'
                f'<div class="datelist">{links}</div>')
    write("launchpad/report/archive/index.html", page("发射台日更文字解读往期 · " + BRAND, arc_body, active="launchpad"))


# ---------------------------------------------------------------- 发射台 · 终端式仪表盘（总览 + 个股页）
# 参照 DefiLlama /fees 和 Token Terminal 的信息架构：深色、高密度、货币化数字用等宽字体，
# 一张跨链排行榜（总数据）+ 逐个平台的详情页（分数据），而不是把叙事报告直接当首页。
TERMINAL_CSS = r"""
:root[data-theme="dark"]{--bg:#0b0e14;--panel:#121722;--card:#121722;--ink:#e7eaf0;--ink2:#b7bfcc;
--muted:#7c8598;--rule:#1e2531;--rule2:#2a3242;--accent:#e2b357;--accent-soft:#221b0f;
--up:#2ecc8f;--dn:#f0555a;--up-soft:#12251d;--dn-soft:#2a1517;color-scheme:dark}
body{font-family:-apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
h1{font:400 32px/1.25 Georgia,"Songti SC","STSong",serif}
.term-hero{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:10px 20px;margin-top:6px}
.term-updated{color:var(--muted);font-size:12.5px;font-family:ui-monospace,Menlo,monospace}
.term-kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;background:var(--rule);
border:1px solid var(--rule);border-radius:10px;overflow:hidden;margin:22px 0 30px}
.term-kpi{background:var(--card);padding:14px 16px}
.term-kpi .k{font-size:10.5px;letter-spacing:.5px;color:var(--muted);text-transform:uppercase;margin-bottom:6px}
.term-kpi .v{font:600 21px/1.15 ui-monospace,Menlo,monospace;letter-spacing:-.3px}
.term-kpi .s{font-size:11.5px;color:var(--muted);margin-top:4px}
.term-tabs{display:flex;gap:6px;margin:28px 0 4px;flex-wrap:wrap}
.term-tabs a{font-size:12.5px;padding:6px 13px;border-radius:999px;border:1px solid var(--rule2);
color:var(--ink2);text-decoration:none}
.term-tabs a.on,.term-tabs a:hover{border-color:var(--accent);color:var(--accent)}
.term-table-wrap{overflow-x:auto;margin-top:14px;border:1px solid var(--rule);border-radius:10px}
table.term{border-collapse:collapse;width:100%;font-size:13px;min-width:760px}
table.term th{background:var(--panel);color:var(--muted);font-weight:600;font-size:10.5px;letter-spacing:.5px;
text-transform:uppercase;padding:10px 12px;text-align:right;border-bottom:1px solid var(--rule);white-space:nowrap}
table.term th.l{text-align:left}
table.term td{padding:10px 12px;border-bottom:1px solid var(--rule);text-align:right;font-family:ui-monospace,Menlo,monospace;
font-variant-numeric:tabular-nums;white-space:nowrap}
table.term td.l{text-align:left;font-family:-apple-system,"PingFang SC",sans-serif}
table.term tr:last-child td{border-bottom:none}
table.term tr:hover td{background:var(--panel)}
table.term a.nm{color:var(--ink);text-decoration:none;font-weight:600}
table.term a.nm:hover{color:var(--accent)}
table.term .rk{color:var(--muted);font-size:12px;width:1%}
.badge{display:inline-block;font-size:10.5px;padding:2px 8px;border-radius:999px;margin-left:8px;
border:1px solid currentColor;opacity:.85;vertical-align:1px}
.badge.solana{color:#b891ff}.badge.robinhood{color:#4c9be8}.badge.bsc{color:#e2b357}
.badge.arc{color:#37c9d6}.badge.other{color:#8b93a7}
.d{font-variant-numeric:tabular-nums}.d.up{color:var(--up)}.d.dn{color:var(--dn)}
.spk{display:block;width:88px;height:26px;margin-left:auto}
.term-plot{overflow-x:auto}
.term-svg{display:block;width:100%;min-width:520px;height:auto}
.term-svg .gl{stroke:var(--rule);stroke-width:1}
.term-svg .ax{fill:var(--muted);font-size:10.5px;font-family:ui-monospace,Menlo,monospace}
.term-legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12.5px;color:var(--ink2);margin:14px 0 8px}
.term-legend .lg-item{display:inline-flex;align-items:center;gap:6px}
.term-legend .lg-item i{width:10px;height:10px;border-radius:2px;display:inline-block}
.term-legend .lg-item b{color:var(--ink);font-family:ui-monospace,Menlo,monospace}
.term-note{background:var(--panel);border-radius:8px;padding:14px 18px;margin:18px 0;font-size:13px;color:var(--ink2)}
.term-back{display:inline-block;margin-top:26px;font-size:13px;color:var(--muted);text-decoration:none}
.term-back:hover{color:var(--accent)}
@media(max-width:720px){.term-kpis{grid-template-columns:repeat(2,1fr)}}
"""


def fmt_usd(v):
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e9:
        return f"${v/1e9:.2f}B"
    if a >= 1e6:
        return f"${v/1e6:.2f}M"
    if a >= 1e3:
        return f"${v/1e3:.1f}K"
    return f"${v:,.0f}"


def fmt_tok(v):
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e6:
        return f"{v/1e6:.2f}M"
    if a >= 1e3:
        return f"{v/1e3:.1f}K"
    return f"{v:,.0f}"


def fmt_delta(v):
    if v is None:
        return '<span class="d">—</span>'
    cls = "up" if v > 0 else ("dn" if v < 0 else "")
    arrow = "▲" if v > 0 else ("▼" if v < 0 else "·")
    return f'<span class="d {cls}">{arrow} {abs(v)*100:.1f}%</span>'


def fmt_pct(v, dp=1):
    return "—" if v is None else f"{v*100:.{dp}f}%"


CHAIN_BADGE = {"Solana": "solana", "Robinhood Chain": "robinhood", "Arc": "arc"}


def chain_badge(chain):
    cls = CHAIN_BADGE.get(chain, "bsc" if "BSC" in (chain or "") else "other")
    return f'<span class="badge {cls}">{esc(chain)}</span>'


def spark_svg(vals, color="#e2b357", w=88, h=26):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return f'<svg class="spk" viewBox="0 0 {w} {h}"></svg>'
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or (abs(hi) or 1)
    n = len(vals)
    pts = " ".join(f"{w*i/(n-1):.1f},{h-(v-lo)/rng*h*0.86-h*0.07:.1f}" for i, v in enumerate(vals))
    return (f'<svg class="spk" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.6" '
            f'stroke-linejoin="round" stroke-linecap="round"/></svg>')


PALETTE = ["#e2b357", "#4c9be8", "#2ecc8f", "#f0555a", "#b891ff", "#37c9d6"]


def trend_chart(series, dates, h=250, fmt="usd"):
    """series: [(名称, {日期: 数值}), ...]；静态多线图，无 hover，端点标最新值——够用，避免整套悬停脚本的复杂度。"""
    W, L, R, T, B = 860, 54, 16, 16, 34
    pw, ph = W - L - R, h - T - B
    vals = [v for _, s in series for v in s.values() if v is not None]
    if not vals or len(dates) < 2:
        return '<div class="empty">暂无足够数据画图</div>'
    top = max(vals) * 1.08 or 1
    n = len(dates)

    def X(i):
        return L + (pw * i / (n - 1) if n > 1 else pw / 2)

    def Y(v):
        return T + ph * (1 - v / top)

    grid = ""
    for k in range(5):
        val = top * k / 4
        y = Y(val)
        lab = fmt_usd(val) if fmt == "usd" else (fmt_tok(val) if fmt == "tok" else f"{val:,.1f}")
        grid += (f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" class="gl"/>'
                 f'<text x="{L-8}" y="{y+4:.1f}" class="ax" text-anchor="end">{lab}</text>')
    xlabs = ""
    step = max(1, n // 6)
    for i in range(0, n, step):
        xlabs += f'<text x="{X(i):.1f}" y="{T+ph+20}" class="ax" text-anchor="middle">{dates[i][5:]}</text>'
    lines, legend = "", ""
    for idx, (name, s) in enumerate(series):
        c = PALETTE[idx % len(PALETTE)]
        pts, last_v, last_x = [], None, None
        for i, d in enumerate(dates):
            v = s.get(d)
            if v is None:
                continue
            pts.append(f"{X(i):.1f},{Y(v):.1f}")
            last_v, last_x = v, X(i)
        if len(pts) >= 2:
            lines += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{c}" stroke-width="1.8" stroke-linejoin="round"/>'
        if last_v is not None:
            lines += f'<circle cx="{last_x:.1f}" cy="{Y(last_v):.1f}" r="3" fill="{c}"/>'
        val_str = fmt_usd(last_v) if fmt == "usd" else (fmt_tok(last_v) if fmt == "tok" else f"{last_v:,.2f}")
        legend += f'<span class="lg-item"><i style="background:{c}"></i>{esc(name)} <b>{val_str}</b></span>'
    svg = f'<svg viewBox="0 0 {W} {h}" class="term-svg">{grid}{lines}{xlabs}</svg>'
    return f'<div class="term-legend">{legend}</div><div class="term-plot">{svg}</div>'


def launchpad_page(title, body, active_tab, desc=""):
    return page(f'{title} · {BRAND}', body, active="launchpad", desc=desc, extra_head=f"<style>{TERMINAL_CSS}</style>",
                wide=True).replace('<html lang="zh-CN">', '<html lang="zh-CN" data-theme="dark">')


def _rank_rows(site_data):
    """合并主力 4 家 + Arc 发射台，统一排行榜行；主力算赛道份额，Arc 项没有共同分母就不算份额。"""
    rows = []
    for x in site_data["平台"]:
        rows.append({"slug": x["slug"], "名称": x["名称"], "链": x["链"], "delayed": x["延迟"],
                     "当日": x["当日手续费"], "日环比": x["日环比"], "7日均": x["7日均"],
                     "份额": x["占赛道份额"], "spark": list(x["手续费序列"].values())[-30:],
                     "detail": f'/launchpad/platforms/{x["slug"]}/'})
    for z in site_data.get("Arc", {}).get("发射台", []):
        rows.append({"slug": z["slug"], "名称": z["名称"], "链": "Arc", "delayed": False,
                     "当日": z["当日手续费"], "日环比": None, "7日均": (z["7日"] / 7 if z["7日"] else None),
                     "份额": None, "spark": list(z["手续费序列"].values())[-30:],
                     "detail": f'/launchpad/platforms/arc-{z["slug"]}/'})
    rows.sort(key=lambda r: -(r["7日均"] or 0))
    return rows


def build_launchpad_overview(site_data):
    if not site_data:
        write("launchpad/index.html", page("发射台总览 · " + BRAND, '<h1>发射台总览</h1><div class="empty">还没有产出，先跑一次 出看板.py。</div>', active="launchpad"))
        return
    rk = _rank_rows(site_data)
    tot = site_data["赛道Top60"]
    tot_series = tot["序列"]
    tot_vals = list(tot_series.values())
    tot_delta = None
    if len(tot_vals) >= 2 and tot_vals[-2]:
        tot_delta = (tot_vals[-1] - tot_vals[-2]) / tot_vals[-2]
    leader = rk[0] if rk else None
    kpis = "".join([
        f'<div class="term-kpi"><div class="k">赛道 Top60 · 当日</div><div class="v">{fmt_usd(tot["当日"])}</div>'
        f'<div class="s">{fmt_delta(tot_delta)}</div></div>',
        f'<div class="term-kpi"><div class="k">追踪协议</div><div class="v">{tot.get("协议数") or "—"}</div>'
        f'<div class="s">Launchpad 类目全部</div></div>',
        f'<div class="term-kpi"><div class="k">当日份额第一</div><div class="v" style="font-size:16px">{esc(leader["名称"]) if leader else "—"}</div>'
        f'<div class="s">{fmt_usd(leader["当日"]) if leader else "—"}</div></div>',
        f'<div class="term-kpi"><div class="k">PONS 当日销毁</div><div class="v">{fmt_usd(site_data["PONS当日销毁USD"])}</div>'
        f'<div class="s">{fmt_tok(site_data["PONS当日销毁"])} 枚</div></div>',
        f'<div class="term-kpi"><div class="k">Arc 发射台合计</div><div class="v">{fmt_usd(site_data["Arc"].get("发射台手续费"))}</div>'
        f'<div class="s">{site_data["Arc"].get("升级条件") or "—"}</div></div>',
    ])
    trs = ""
    for i, r in enumerate(rk, 1):
        share = fmt_pct(r["份额"]) if r["份额"] is not None else "—"
        val = '<span class="badge other">延迟</span>' if r["delayed"] else fmt_usd(r["当日"])
        trs += (f'<tr><td class="rk">{i}</td>'
                f'<td class="l"><a class="nm" href="{r["detail"]}">{esc(r["名称"])}</a>{chain_badge(r["链"])}</td>'
                f'<td>{val}</td><td>{fmt_delta(r["日环比"])}</td><td>{fmt_usd(r["7日均"])}</td>'
                f'<td>{share}</td><td>{spark_svg(r["spark"])}</td></tr>')
    trend_dates = (sorted(set().union(*[x["手续费序列"].keys() for x in site_data["平台"]]))
                   if site_data["平台"] else list(tot_series.keys()))
    trend = trend_chart([(NAME_OF(x["slug"], x["名称"]), x["手续费序列"]) for x in site_data["平台"]],
                         trend_dates, fmt="usd") if site_data["平台"] else ""
    body = f"""<div class="eyebrow">🚀 板块 · 终端总览</div>
<div class="term-hero"><h1>发射台总览</h1><div class="term-updated">数据截至 {site_data["日期"]}（UTC 完整日）· 生成于 {esc(site_data["生成时间UTC"])} UTC</div></div>
<p class="lede">pump.fun / Pons / StonkFun / Flap 四家主力，加 Arc 链上 {len(site_data.get("Arc",{}).get("发射台",[]))} 家发射台，
按 7 日均手续费统一排行——总数据看赛道，点进每一行看单个平台的分数据。</p>
<div class="term-kpis">{kpis}</div>
<h2 style="font-size:19px">全市场排行</h2>
<div class="term-table-wrap"><table class="term">
<tr><th class="l">#</th><th class="l">平台</th><th>当日手续费</th><th>日环比</th><th>7日均</th><th>赛道份额</th><th>30 日走势</th></tr>
{trs}
</table></div>
<div class="term-note">赛道份额分母是 DefiLlama Launchpad 类目 Top60 当日总量，只对可比的主力平台算；Arc 上的发射台不在同一个分母里（Arc 是独立生态），份额栏留空不代表没有量。延迟标记表示数据源当天还没出数，不是 0。</div>
<h2 style="font-size:19px">主力四家 · 90 天手续费走势</h2>
{trend}
<p style="margin-top:28px"><a href="/launchpad/report/">→ 看今天的文字解读（口径提醒、回购市盈率、Arc 升级条件全解释）</a></p>"""
    write("launchpad/index.html", launchpad_page("发射台总览", body, "overview", desc=site_data["一句话"]))


def NAME_OF(slug, fallback):
    m = {"pump.fun": "pump.fun", "pons-v1": "Pons V1", "pons-v2": "Pons V2", "stonkfun": "StonkFun", "flap-sh": "Flap"}
    return m.get(slug, fallback)


def build_launchpad_platforms(site_data):
    if not site_data:
        return
    for x in site_data["平台"]:
        sym = x.get("估值符号")
        val = site_data.get("估值", {}).get(sym) if sym else None
        kpis = "".join([
            f'<div class="term-kpi"><div class="k">当日手续费</div><div class="v">{fmt_usd(x["当日手续费"]) if not x["延迟"] else "延迟"}</div>'
            f'<div class="s">{fmt_delta(x["日环比"])}</div></div>',
            f'<div class="term-kpi"><div class="k">7 日均</div><div class="v">{fmt_usd(x["7日均"])}</div>'
            f'<div class="s">{fmt_delta(x["7日均环比"])}</div></div>',
            f'<div class="term-kpi"><div class="k">当日协议收入</div><div class="v">{fmt_usd(x["当日收入"])}</div>'
            f'<div class="s">分账比率 {fmt_pct(x["分账比率"])}</div></div>',
            f'<div class="term-kpi"><div class="k">赛道份额</div><div class="v">{fmt_pct(x["占赛道份额"])}</div>'
            f'<div class="s">距单日峰值 {fmt_pct(x["距单日峰值"])}</div></div>',
            f'<div class="term-kpi"><div class="k">累计手续费</div><div class="v">{fmt_usd(x["累计"])}</div>'
            f'<div class="s">单日峰值 {x["峰值日"] or "—"}</div></div>',
        ])
        dates = sorted(set(x["手续费序列"]) | set(x["收入序列"]))
        chart = trend_chart([("手续费", x["手续费序列"]), ("协议收入", x["收入序列"])], dates, fmt="usd")
        val_block = ""
        if val:
            val_block = f"""<h2 style="font-size:19px">估值（{sym}）</h2>
<div class="term-kpis" style="grid-template-columns:repeat(3,1fr)">
<div class="term-kpi"><div class="k">burn-adjusted 市值</div><div class="v">{fmt_usd(val.get("市值"))}</div></div>
<div class="term-kpi"><div class="k">收入市盈率</div><div class="v">{val.get("收入市盈率") and f'{val["收入市盈率"]:.2f}x' or "—"}</div></div>
<div class="term-kpi"><div class="k">回购市盈率</div><div class="v">{val.get("回购市盈率") and f'{val["回购市盈率"]:.2f}x' or "—"}</div>
<div class="s">回购收益率 {fmt_pct(val.get("回购收益率"))}</div></div>
</div>"""
        body = f"""<div class="eyebrow">🚀 发射台 · 分数据</div>
<div class="term-hero"><h1>{esc(x["名称"])}{chain_badge(x["链"])}</h1>
<div class="term-updated">数据截至 {site_data["日期"]}</div></div>
<div class="term-kpis">{kpis}</div>
<h2 style="font-size:19px">手续费 / 协议收入走势</h2>
{chart}
{val_block}
<a class="term-back" href="/launchpad/">← 返回发射台总览</a>"""
        write(f'launchpad/platforms/{x["slug"]}/index.html',
              launchpad_page(f'{x["名称"]} · 发射台', body, x["slug"]))
    for z in site_data.get("Arc", {}).get("发射台", []):
        dates = sorted(z["手续费序列"])
        kpis = "".join([
            f'<div class="term-kpi"><div class="k">当日手续费</div><div class="v">{fmt_usd(z["当日手续费"])}</div></div>',
            f'<div class="term-kpi"><div class="k">7 日合计</div><div class="v">{fmt_usd(z["7日"])}</div></div>',
            f'<div class="term-kpi"><div class="k">30 日合计</div><div class="v">{fmt_usd(z["30日"])}</div></div>',
            f'<div class="term-kpi"><div class="k">7 日 DEX 成交</div><div class="v">{fmt_usd(z["7日DEX"])}</div></div>',
        ])
        chart = trend_chart([("手续费", z["手续费序列"])], dates, fmt="usd")
        body = f"""<div class="eyebrow">🚀 发射台 · 分数据</div>
<div class="term-hero"><h1>{esc(z["名称"])}{chain_badge("Arc")}</h1>
<div class="term-updated">数据截至 {site_data["日期"]}</div></div>
<div class="term-kpis" style="grid-template-columns:repeat(4,1fr)">{kpis}</div>
<h2 style="font-size:19px">手续费走势</h2>
{chart}
<div class="term-note">Arc 上不少发射台的 swap 走 Uniswap 底层池，DEX 成交记在 Uniswap 名下而不是发射台名下，这里的「DEX 成交」系统性偏低，看手续费更可靠。</div>
<a class="term-back" href="/launchpad/">← 返回发射台总览</a>"""
        write(f'launchpad/platforms/arc-{z["slug"]}/index.html',
              launchpad_page(f'{z["名称"]}（Arc）· 发射台', body, f'arc-{z["slug"]}'))


# ---------------------------------------------------------------- 口径 / 更正记录 / 关于
def build_methodology(site_data):
    rows = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in [
        ("统计口径", "全部用手续费（fees），不用成交量；成交量口径覆盖不全，会系统性低估份额。"),
        ("统计周期", "只报「昨天」这一个 UTC 完整日；当天数据永远不完整，不进正文。"),
        ("延迟处理", "某个数据源没出昨天的数，标「延迟」，不拿旧值顶替、不记 0。"),
        ("Flap 单独看", "税代币模型，费用来自转账税，和其他平台的手续费口径不可直接比大小。"),
        ("StonkFun 比较", "跨平台比较一律用协议收入（revenue），不用 fees，避免系统性低估。"),
        ("PONS 销毁", "转到 0x…dEaD 地址，不是调用 burn()，totalSupply 不会减少，市值一律按 burn-adjusted 流通计。"),
        ("估值口径", "市值 = burn-adjusted 流通市值；年化协议收入/回购额取近 30 日滚动合计外推，不足 30 天标注。"),
        ("绝不做的事", "不拿历史峰值和现在比来判断一个平台是否「死了」；只给数据，不给买卖建议。"),
    ])
    body = f"""<div class="eyebrow">方法论</div><h1>口径与统计方法</h1>
<p class="lede">这页固定不变，发射台看板里的「九 · 口径与已知缺口」是每天数据层面的具体缺口，这里是长期不变的统计原则。</p>
<div class="tbl"><table><tr><th>项目</th><th>说明</th></tr>{rows}</table></div>"""
    write("methodology/index.html", page("口径与统计方法 · " + BRAND, body, active="methodology"))


def build_corrections(site_data, fixes):
    rows = "".join(f"<tr><td>{esc(f['日期'])}</td><td>{f['旧值']:,.0f} → {f['新值']:,.0f}</td>"
                    f"<td>{esc(f.get('口径',''))}</td><td>{esc(f['修正时间UTC'][:10])}</td></tr>"
                    for f in sorted(fixes, key=lambda x: x["日期"], reverse=True)[:60])
    rev_note = ""
    if site_data and site_data.get("异常"):
        rev = [a for a in site_data["异常"] if "修订" in a or "延迟" in a]
        if rev:
            rev_note = "<h2>近期数据源变动</h2><ul>" + "".join(f"<li>{esc(a)}</li>" for a in rev) + "</ul>"
    body = f"""<div class="eyebrow">透明记录</div><h1>更正记录</h1>
<p class="lede">数据源事后修订、PONS 销毁口径重算的差额，全部留痕，不覆盖不删除。</p>
{rev_note}
<h2>PONS 逐日销毁重算记录</h2>
<div class="tbl"><table><tr><th>日期</th><th>旧值 → 新值</th><th>口径</th><th>修正时间</th></tr>{rows or '<tr><td colspan="4">暂无</td></tr>'}</table></div>"""
    write("corrections/index.html", page("更正记录 · " + BRAND, body, active="corrections"))


def build_about():
    body = f"""<div class="eyebrow">关于</div><h1>关于{esc(BRAND)}</h1>
<p class="lede">{esc(SLOGAN)}</p>
<p>写这个站的人是一个做了很久 web3 一级市场的交易者，现在把工作方式搬到台面上：
宏观流动性怎么影响 BTC / ETH，板块怎么轮动，发射台每天赚多少钱、钱从哪来，
低位叙事币在哪个阶段埋伏——都留成公开的过程记录，而不是事后诸葛亮的复盘。</p>
<p>{esc(DISCLAIMER)}</p>
<p>Twitter：{esc(TWITTER)} ｜ 站点：{esc(DOMAIN)}</p>"""
    write("about/index.html", page("关于 · " + BRAND, body, active="about"))


# ---------------------------------------------------------------- 杂项：404 / robots / sitemap / favicon
def build_misc():
    write("404.html", page("页面不存在 · " + BRAND,
          '<h1>页面不存在</h1><p class="lede">链接可能过期了，回<a href="/">首页</a>看看。</p>'))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: https://{DOMAIN}/sitemap.xml\n")
    urls = ["/", "/methodology/", "/corrections/", "/about/"] + [f'/{p["slug"]}/' for p in PILLARS]
    for p in PILLARS:
        urls += [f'/{p["slug"]}/{x["slug"]}/' for x in ALL_POSTS[p["slug"]]]
    if os.path.isdir(os.path.join(SITE, "launchpad", "report")):
        urls += [f"/launchpad/report/{d}/" for d in os.listdir(os.path.join(SITE, "launchpad", "report"))
                 if re.match(r"^\d{4}-\d{2}-\d{2}$", d)]
        urls.append("/launchpad/report/archive/")
    if os.path.isdir(os.path.join(SITE, "launchpad", "platforms")):
        urls += [f"/launchpad/platforms/{d}/" for d in os.listdir(os.path.join(SITE, "launchpad", "platforms"))]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "".join(f"<url><loc>https://{DOMAIN}{u}</loc></url>\n" for u in sorted(set(urls))) + "</urlset>\n")
    write("sitemap.xml", xml)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" '
           'fill="#8a5a00"/><text x="32" y="43" font-size="30" font-family="Georgia,serif" fill="#fbfbfa" '
           'text-anchor="middle">链</text></svg>')
    write("favicon.svg", svg)
    write("CNAME", DOMAIN + "\n")


def main():
    sd_path = os.path.join(BUILD, "网站素材.json")
    site_data = load(sd_path)
    if not site_data:
        print(f"⛔ 没找到 {sd_path}，先跑 python3 出看板.py（并设 LP_OUT=build）")
        sys.exit(1)
    fixes = load(os.path.join(ROOT, "data", "销毁修正记录.json"), []) or []
    os.makedirs(SITE, exist_ok=True)
    build_home(site_data)
    build_launchpad_overview(site_data)
    build_launchpad_platforms(site_data)
    build_launchpad_report(site_data)
    for p in PILLARS:
        if p["slug"] == "launchpad":
            continue
        build_pillar_landing(p, site_data)
        build_posts(p)
    build_methodology(site_data)
    build_corrections(site_data, fixes)
    build_about()
    build_misc()
    n_pages = sum(len(files) for _, _, files in os.walk(SITE) if True)
    print(f"网站已生成到 {SITE}（{sum(1 for _,_,fs in os.walk(SITE) for f in fs if f=='index.html')} 个页面 + 归档）")


if __name__ == "__main__":
    main()
