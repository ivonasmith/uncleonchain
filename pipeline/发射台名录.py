#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发射台名录：把链上扫到的工厂（EVM）和前端（Solana）按「同一个发射台」合并，配上名字、logo、叙事。

两种用法：
  · 出网站.py import 本模块，用 collect() 拿名录条目、narrative() 拿叙事文字与标签、logo_src() 拿图标；
  · 日更直接跑 `python3 pipeline/发射台名录.py`：存一份 DefiLlama 发射台 / AI Agents 类目的介绍（data/onchain/llama_meta.json），
    再给名录里有官网的条目抓官网（标题、简介、X 账号、图标），图标存 data/onchain/logo/，结果写 data/onchain/档案.json。
叙事优先级：config/launchpad_profiles.json 人工写的一句话（中文）> DefiLlama 介绍 > 官网自述；标签 = 人工标签 ∪ 按关键词自动打的标签。
自动摘录的英文只是平台自己的说法，页面上标明来源，没核实。
"""
import os, re, json, time, hashlib, urllib.request, urllib.parse, datetime as dt
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.abspath(os.environ.get("LP_DATA") or os.path.join(ROOT, "data"))
OC = os.path.join(DATA, "onchain")
LOGO_DIR = os.path.join(OC, "logo")
UA = {"User-Agent": "Mozilla/5.0 (compatible; uncleonchain-launchpad-directory)", "Accept": "text/html,application/xhtml+xml,*/*"}

MIN_EVM_7D = 30           # EVM 工厂进名录：近 7 天新币 ≥ 30
MIN_SOL_24H = 10000       # Solana 前端进名录：样本池 24h 成交额 ≥ $10K
REFRESH_DAYS = 14         # 官网资料 14 天重抓一次
FETCH_CAP = 60            # 每次最多抓几个官网
INFRA_NAMES = {"entrypoint", "uniswapv2router02", "multicall3", "hyperproxy", "transparentupgradeableproxy", "erc1967proxy", "proxy"}
GENERIC_NAMES = {"tokenfactory", "factory", "launchpad", "launchpadfactory", "portal", "standardlaunchfactory", "erc20factory"}
FACILITY = {"meteora-dbc": "Meteora DBC", "raydium-launchlab": "Raydium LaunchLab"}
OWN = "自有合约"
SKIP_FILES = ("solana.json", "线索.json", "ai_agent.json", "档案.json", "llama_meta.json", "平台资料.json")

# 叙事标签：中文名 → (英文名, 正则)。英文自述 / 介绍里命中就打上
TAGS = {
    "AI Agent": ("AI Agent", r"\bai[- ]?agents?\b|agentic|autonomous ai|launch(?:es|ing)? (?:and trade )?ai|tokeni[sz]e[sd]? ai|agent launchpad|ai idols?|erc-8004|\bagents? (?:launch|deploy|trade)"),
    "代币化股票 / RWA": ("Tokenized stocks / RWA", r"tokeni[sz]ed (?:stocks?|equit|assets?)|\bstocks?\b|equities|\brwa|real[- ]world asset|pre-?ipo|commodit|xstocks?|\bnvda\b|\btsla\b"),
    "持币分红": ("Holder rewards", r"holders? (?:get paid|earn|rewards?|are paid)|pays? holders|reflections?|dividends?|rewards? (?:to|for) holders|yield to holders"),
    "回购销毁": ("Buyback & burn", r"buy ?backs?|buy back|\bburn(?:s|ed|ing)?\b"),
    "创作者分成": ("Creator fees", r"creator (?:fees?|rewards?|royalt)|royalt(?:y|ies)|creators? (?:earn|keep|get)|earn (?:fees|royalties)"),
    "公平发射 / 反狙击": ("Fair launch / anti-snipe", r"fair[- ]launch|anti[- ]?snip|no (?:presale|dev allocation|admin keys|free allocation)|bundl(?:e|ing) protection|rug[- ]?proof"),
    "税币": ("Tax tokens", r"tax[- ]tokens?|\b(?:buy|sell)[ /-]tax|\btaxed\b|\btax\b"),
    "社交 / 内容币": ("Social / content coins", r"social|every post|creator coins?|stream(?:er|ing)\b|tweet|reply to any|content coins?"),
    "众筹 / 预售": ("Raise / presale", r"crowdfund|presale|\braise\b|raising|\bico\b"),
    "交易返现 / 空投": ("Cashback / airdrops", r"cash ?back|rebates?|airdrops? (?:to|for) (?:top )?traders|volume rewards|trading rewards"),
    "隐私币": ("Privacy coins", r"privacy|zcash|\bzec\b|monero|\bxmr\b"),
    "游戏 / 对战": ("Games / battles", r"\bgam(?:e|es|ing)\b|\bbattles?\b"),
    "预测市场": ("Prediction markets", r"prediction market"),
    "Apple Pay / 法币入金": ("Apple Pay / fiat", r"apple pay|credit card"),
    "Meme 通用": ("General memecoins", r"(?!x)x"),
    "玩法创新": ("Novel mechanics", r"(?!x)x"),              # 只人工打
    "基础设施 / 协议": ("Infrastructure / protocol", r"(?!x)x"),
}
_TAG_RE = {k: re.compile(v[1], re.I) for k, v in TAGS.items()}
_CACHE = {}


def load(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _cached(name, path):
    if name not in _CACHE:
        _CACHE[name] = load(path, {}) or {}
    return _CACHE[name]


def profiles():
    return _cached("prof", os.path.join(ROOT, "config", "launchpad_profiles.json"))


def factory_labels():
    return _cached("lab", os.path.join(ROOT, "config", "launchpad_factories.json"))


def llama_meta():
    return _cached("llama", os.path.join(OC, "llama_meta.json"))


def dossier():
    return _cached("dos", os.path.join(OC, "档案.json"))


def domain(u):
    try:
        u = u if "://" in (u or "") else "https://" + (u or "")
        h = urllib.parse.urlparse(u).netloc.lower().split(":")[0]
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def slugify(s):
    out = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return out or hashlib.md5((s or "x").encode()).hexdigest()[:8]


def _match_profile(prof, idents):
    idents = {i.lower() for i in idents if i}
    for pid, p in prof.items():
        if pid.startswith("_"):
            continue
        keys = {pid.lower(), (p.get("名称") or "").lower(), domain(p.get("官网") or "")} | {m.lower() for m in p.get("匹配") or []}
        keys.discard("")
        if idents & keys:
            return pid
    return None


def _match_llama(meta, name, dom, prof_entry):
    if prof_entry and prof_entry.get("defillama") in meta:
        return prof_entry["defillama"]
    if dom:
        for slug, m in meta.items():
            if domain(m.get("url") or "") == dom:
                return slug
    n = (name or "").lower()
    if n:
        for slug, m in meta.items():
            if (m.get("名称") or "").lower() == n:
                return slug
    return None


def collect():
    """名录条目（已合并）。每条：key、profile、名称、官网、图标源、链、设施、地址[(链, 地址, 浏览器)]、
    近7日新币 / 前7日新币（EVM）、24h成交额 / 样本池（Solana）、发币人、首次出现、defillama。"""
    prof = profiles()
    lab = factory_labels()
    ids = (load(os.path.join(OC, "线索.json"), {}) or {}).get("身份") or {}
    meta = llama_meta()
    ents = {}

    def put(idents, name, chain, **kw):
        if name:
            name = re.sub(r"\s+\d+(?:\.\d+)?%$", "", name.strip()) or name    # 「Tracer 1%」「Tracer 2.5%」= 同一平台不同费率
            idents = set(idents) | {name}
        pid = _match_profile(prof, idents)
        dom = domain(kw.get("官网") or "")
        n = (name or "").lower()
        if pid:
            key = pid
        elif dom:
            key = dom
        elif n.replace(" ", "") in GENERIC_NAMES:
            key = f"{chain}:{kw['地址'][0][1]}"
        else:
            key = slugify(n)
        e = ents.setdefault(key, {"key": key, "profile": pid, "名称": None, "官网": None, "图标源": None, "链": [], "设施": [], "地址": [],
                                  "近7日新币": 0, "前7日新币": 0, "24h成交额": 0, "样本池": 0, "发币人": 0, "_首次": []})
        if name and (not e["名称"] or len(name) < len(e["名称"])):
            e["名称"] = name
        e["官网"] = e["官网"] or kw.get("官网")
        e["图标源"] = e["图标源"] or kw.get("图标")
        if chain not in e["链"]:
            e["链"].append(chain)
        for f in kw.get("设施") or []:
            if f not in e["设施"]:
                e["设施"].append(f)
        e["地址"] += kw.get("地址") or []
        for k in ("近7日新币", "前7日新币", "24h成交额", "样本池"):
            e[k] += kw.get(k) or 0
        e["发币人"] = max(e["发币人"], kw.get("发币人") or 0)
        e["_首次"].append(kw.get("首次出现") or "基线")

    # EVM 工厂（近 7 天）
    for f in sorted(os.listdir(OC)) if os.path.isdir(OC) else []:
        if not f.endswith(".json") or f in SKIP_FILES:
            continue
        chain = f[:-5]
        db = load(os.path.join(OC, f), {}) or {}
        days = db.get("逐日") or {}
        if not days:
            continue
        ds = sorted(days)
        w7, p7 = set(ds[-7:]), set(ds[-14:-7])
        agg = defaultdict(lambda: [0, 0, 0])
        for d in ds:
            for a, v in (days[d].get("工厂") or {}).items():
                if d in w7:
                    agg[a][0] += v[0]
                    agg[a][2] = max(agg[a][2], v[1])
                elif d in p7:
                    agg[a][1] += v[0]
        known = dict(lab.get("*") or {}, **(lab.get(chain) or {}))
        first = db.get("首次出现") or {}
        for a, (n7, p7n, ppl) in agg.items():
            if n7 < MIN_EVM_7D:
                continue
            tag = known.get(a) or {}
            if tag.get("类型") in ("基础设施", "忽略"):
                continue
            idt = ids.get(f"{chain}:{a}") or {}
            cname = idt.get("合约名")
            if cname and cname.lower() in INFRA_NAMES:
                continue
            dom = (idt.get("重复域名") or [None])[0]
            name = tag.get("名称") or cname or dom
            idents = {f"{chain}:{a}", tag.get("名称"), cname, dom, domain(tag.get("官网") or "") or None}
            if not name and not _match_profile(prof, idents):
                continue
            put(idents, name, chain, 官网=tag.get("官网") or (f"https://{dom}" if dom else None), 设施=[OWN],
                地址=[(chain, a, db.get("浏览器") or "")], 近7日新币=n7, 前7日新币=p7n, 发币人=ppl, 首次出现=first.get(a, "基线"))

    # Solana 前端（最近一天的样本）
    sdb = load(os.path.join(OC, "solana.json"), {}) or {}
    if sdb.get("逐日"):
        end = max(sdb["逐日"])
        sfirst = sdb.get("首次出现") or {}
        for dex, blk in sdb["逐日"][end].items():
            for gid, g in (blk.get("前端") or {}).items():
                if (g.get("成交额") or 0) < MIN_SOL_24H:
                    continue
                idt = ids.get(f"solana:{gid}") or {}
                web = g.get("官网")
                if web and re.search(r"\.(png|jpe?g|gif|webp|svg)(\?|$)|img-proxy|attachments|catbox", web, re.I):
                    web = None                       # 老数据里有人把图标填进了官网栏
                dom = domain(web) if web else (idt.get("重复域名") or [None])[0]
                name = g.get("名称") or dom
                idents = {f"solana:{gid}", g.get("名称"), dom}
                if not name and not _match_profile(prof, idents):
                    continue
                put(idents, name, "solana", 官网=web or (f"https://{dom}" if dom else None), 图标=g.get("图标"),
                    设施=[FACILITY.get(dex, dex)], 地址=[("solana", gid, sdb.get("浏览器") or "https://solscan.io")],
                    样本池=g.get("池") or 0, 首次出现=sfirst.get(f"{dex}:{gid}", "基线"), **{"24h成交额": g.get("成交额") or 0})

    out = []
    for e in ents.values():
        fs = e.pop("_首次")
        e["首次出现"] = "基线" if (not fs or "基线" in fs) else min(fs)
        p = prof.get(e["profile"]) if e["profile"] else None
        if p:
            e["名称"] = p.get("名称") or e["名称"]
            e["官网"] = p.get("官网") or e["官网"]
        e["defillama"] = _match_llama(meta, e["名称"], domain(e["官网"] or ""), p)
        out.append(e)
    return out


def auto_tags(*texts):
    t = " ".join(x for x in texts if x)
    return [k for k, r in _TAG_RE.items() if r.search(t)]


def _dos(e):
    """档案按名录 key 存；key 变了（比如后来加了人工档案）就按官网域名找回原来那条。"""
    d = dossier()
    if e["key"] in d:
        return d[e["key"]]
    dom = domain(e.get("官网") or "")
    if dom:
        for v in d.values():
            if domain(v.get("官网") or "") == dom:
                return v
    return {}


def _ds_blurb(e):
    """没官网资料时：DEX Screener「自称发射台」里以这个名字开头的自述（如 UPPIN）。"""
    nm = (e.get("名称") or "").strip()
    if len(nm) < 3:
        return None
    hits = _cached("clues", os.path.join(OC, "线索.json")).get("自称发射台") or {}
    r = re.compile(r"^\W*" + re.escape(nm) + r"\b", re.I)
    for h in sorted(hits.values(), key=lambda h: h.get("日期", ""), reverse=True):
        if r.search(h.get("简介") or ""):
            return h["简介"][:400]
    return None


def narrative(e, lang="zh"):
    """→ (一句话, 来源说明, 标签列表, X 账号)。"""
    prof = profiles().get(e.get("profile") or "", {})
    meta = llama_meta().get(e.get("defillama") or "", {})
    dos = _dos(e)
    site, llama = dos.get("简介") or "", meta.get("介绍") or ""
    tags = list(prof.get("标签") or [])
    if not prof.get("只用人工标签"):
        extra = "" if site else (_ds_blurb(e) or "")
        cname = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", e.get("名称") or "")     # TaxRWAERC20LaunchpadFactory → Tax RWAERC20 …
        for t in auto_tags(prof.get("叙事EN"), llama, site, extra, cname):
            if t not in tags:
                tags.append(t)
    if lang == "en":
        tags = [TAGS[t][0] if t in TAGS else t for t in tags]
    if prof.get("叙事"):
        txt = prof["叙事"] if lang == "zh" else (prof.get("叙事EN") or prof["叙事"])
        src = (prof.get("来源") or "人工整理") if lang == "zh" else (prof.get("来源EN") or "Curated")
    elif llama:
        txt, src = llama, ("DefiLlama 介绍（英文原文）" if lang == "zh" else "DefiLlama description")
    elif site:
        txt, src = site, ("官网自述（英文原文，未核实）" if lang == "zh" else "From its website (unverified)")
    elif _ds_blurb(e):
        txt, src = _ds_blurb(e), ("DEX Screener 上的项目自述（英文原文，未核实）" if lang == "zh" else "Self-description on DEX Screener (unverified)")
    else:
        txt, src = "", ""
    x = prof.get("X") or meta.get("X") or dos.get("X")
    return txt, src, tags, x


def logo_src(e):
    """页面用的图标：本地缓存（/img/lp/…）> 远程（人工 / DefiLlama 图标 / LaunchLab 配置里的图）> None（页面画首字母）。"""
    dos = _dos(e)
    if dos.get("图标文件") and os.path.exists(os.path.join(LOGO_DIR, dos["图标文件"])):
        return "/img/lp/" + dos["图标文件"]
    meta = llama_meta().get(e.get("defillama") or "", {})
    prof = profiles().get(e.get("profile") or "", {})
    return prof.get("logo") or meta.get("logo") or e.get("图标源")


# ---------------------------------------------------------------- 日更：抓 DefiLlama 介绍 + 官网资料 + 图标
def _get(url, limit=1_500_000, timeout=15, accept=None):
    h = dict(UA)
    if accept:
        h["Accept"] = accept
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.read(limit), r.headers.get("Content-Type", ""), r.geturl()


def fetch_llama_meta():
    try:
        raw, _, _ = _get("https://api.llama.fi/protocols", limit=300_000_000, timeout=90, accept="application/json")
        ps = json.loads(raw)
    except Exception as e:
        print(f"  DefiLlama 协议资料失败：{e}")
        return
    out = {}
    for p in ps:
        if p.get("category") not in ("Launchpad", "AI Agents"):
            continue
        out[p.get("slug") or slugify(p.get("name"))] = {"名称": p.get("name"), "url": p.get("url") or None, "X": p.get("twitter") or None,
                                                         "logo": p.get("logo") or None, "介绍": (p.get("description") or "").strip()[:400] or None,
                                                         "类目": p.get("category")}
    with open(os.path.join(OC, "llama_meta.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0, sort_keys=True)
    _CACHE.pop("llama", None)
    print(f"  DefiLlama 发射台 / AI Agents 资料 {len(out)} 条")


def _clean(s):
    import html as H
    return re.sub(r"\s+", " ", H.unescape(s or "")).strip()


class PageMeta:
    """从 HTML 里抠 title / description / og / icon / X 账号（不引第三方库）。"""
    def __init__(self, html_, base):
        h = html_[:400_000]
        self.title = _clean((re.search(r"<title[^>]*>(.*?)</title>", h, re.I | re.S) or [None, ""])[1])
        self.metas = {}
        for m in re.finditer(r"<meta\s[^>]*>", h, re.I):
            tag = m.group(0)
            k = re.search(r'(?:name|property)\s*=\s*["\']([^"\']+)["\']', tag, re.I)
            v = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag, re.I)
            if k and v:
                self.metas.setdefault(k.group(1).lower(), _clean(v.group(1)))
        icons = []
        for m in re.finditer(r"<link\s[^>]*>", h, re.I):
            tag = m.group(0)
            rel = (re.search(r'rel\s*=\s*["\']([^"\']+)["\']', tag, re.I) or [None, ""])[1].lower()
            href = (re.search(r'href\s*=\s*["\']([^"\']+)["\']', tag, re.I) or [None, ""])[1]
            if "icon" in rel and href and not href.startswith("data:"):
                size = re.search(r'sizes\s*=\s*["\'](\d+)', tag, re.I)
                icons.append((0 if "apple-touch" in rel else 1, -(int(size.group(1)) if size else 0), urllib.parse.urljoin(base, href)))
        self.icons = [u for _, _, u in sorted(icons)]
        xs = re.findall(r'https?://(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{2,15})(?=["\'/?#])', h)
        xs = [x for x in xs if x.lower() not in ("intent", "share", "home", "i", "search", "hashtag", "x", "twitter", "messages")]
        self.x = Counter(xs).most_common(1)[0][0] if xs else None

    def desc(self):
        for k in ("og:description", "description", "twitter:description"):
            if self.metas.get(k):
                return self.metas[k][:400]
        return None


def _save_logo(key, urls):
    os.makedirs(LOGO_DIR, exist_ok=True)
    base = slugify(key)[:40]
    for u in urls:
        if not u or not u.startswith("http"):
            continue
        try:
            raw, ct, _ = _get(u, limit=400_000, timeout=15, accept="image/*")
        except Exception:
            continue
        ct = ct.lower()
        path = u.lower().split("?")[0]
        ext = ("svg" if "svg" in ct else "png" if "png" in ct else "jpg" if "jpeg" in ct or "jpg" in ct else "webp" if "webp" in ct
               else "gif" if "gif" in ct else "ico" if "icon" in ct or path.endswith(".ico") else None)
        if not ext or len(raw) < 100 or len(raw) >= 400_000:
            continue
        if ext == "svg" and (b"<script" in raw.lower() or b"<svg" not in raw[:3000].lower()):
            continue
        fn = f"{base}-{hashlib.md5(raw).hexdigest()[:8]}.{ext}"
        for old in os.listdir(LOGO_DIR):              # 同一个发射台只留最新一张
            if old.startswith(base + "-") and old != fn:
                os.remove(os.path.join(LOGO_DIR, old))
        with open(os.path.join(LOGO_DIR, fn), "wb") as f:
            f.write(raw)
        return fn, u
    return None, None


def fetch_dossiers():
    ents = collect()
    dos = dossier()
    today = dt.date.today().isoformat()
    stale = (dt.date.today() - dt.timedelta(days=REFRESH_DAYS)).isoformat()
    prof, meta = profiles(), llama_meta()
    ents.sort(key=lambda e: -(e["近7日新币"] * 50 + e["24h成交额"]))     # 先抓活跃的
    n = ok = 0
    for e in ents:
        old = dos.get(e["key"]) or _dos(e)
        if old.get("日期", "") >= stale and old.get("官网") == e.get("官网"):
            continue
        if n >= FETCH_CAP:
            break
        n += 1
        site = e.get("官网")
        rec = {"日期": today, "官网": site}
        m = None
        if site:
            try:
                raw, ct, final = _get(site)
                if "html" in ct.lower() or raw[:300].lstrip().lower().startswith((b"<!doctype", b"<html")):
                    m = PageMeta(raw.decode("utf-8", errors="ignore"), final)
                    rec.update({"标题": m.title[:160] or None, "简介": m.desc(), "X": m.x})
                    ok += 1
            except Exception as ex:
                rec["错误"] = str(ex)[:120]
        p, lm = prof.get(e.get("profile") or "", {}), meta.get(e.get("defillama") or "", {})
        cands = [p.get("logo"), lm.get("logo"), e.get("图标源")]
        if m:
            cands += m.icons[:3] + [m.metas.get("og:image")]
        if site:
            cands.append(urllib.parse.urljoin(site, "/favicon.ico"))
        fn, src = _save_logo(e["key"], cands)
        if fn:
            rec.update({"图标文件": fn, "图标来源": src})
            if old.get("图标文件") and old["图标文件"] != fn and os.path.exists(os.path.join(LOGO_DIR, old["图标文件"])):
                os.remove(os.path.join(LOGO_DIR, old["图标文件"]))      # 名录 key 改了以后旧文件名的图标
        elif old.get("图标文件"):
            rec.update({"图标文件": old["图标文件"], "图标来源": old.get("图标来源")})
        dos[e["key"]] = rec
        time.sleep(0.3)
    with open(os.path.join(OC, "档案.json"), "w", encoding="utf-8") as f:
        json.dump(dos, f, ensure_ascii=False, indent=0, sort_keys=True)
    print(f"  发射台档案：名录 {len(ents)} 个，本次抓 {n} 个官网（成功 {ok}），有图标 {sum(1 for v in dos.values() if v.get('图标文件'))} 个")


# ---------------------------------------------------------------- 平台二级页面的资料（DefiLlama 协议详情 + 官网）
PLATFORM_MIN_SHARE = 0.001     # 近 30 日或近 7 日手续费份额 ≥ 0.1% 的平台做二级页面
PLATFORM_REFRESH = 7


def platform_slugs(matrix):
    P = matrix.get("协议") or []
    t30 = sum(p.get("30日") or 0 for p in P) or 1
    t7 = sum(p.get("7日") or 0 for p in P) or 1
    return [p["slug"] for p in P if (p.get("30日") or 0) / t30 >= PLATFORM_MIN_SHARE or (p.get("7日") or 0) / t7 >= PLATFORM_MIN_SHARE]


def platform_info():
    return _cached("pinfo", os.path.join(OC, "平台资料.json"))


def _ts(v):
    try:
        return dt.datetime.fromtimestamp(int(v), dt.timezone.utc).date().isoformat()
    except Exception:
        return None


def fetch_platform_details(cap=45):
    matrix = load(os.path.join(DATA, "发射台矩阵.json"), {}) or {}
    slugs = platform_slugs(matrix)
    info = dict(platform_info())
    stale = (dt.date.today() - dt.timedelta(days=PLATFORM_REFRESH)).isoformat()
    today = dt.date.today().isoformat()
    n = 0
    for slug in slugs:
        if (info.get(slug) or {}).get("日期", "") >= stale or n >= cap:
            continue
        n += 1
        rec = {"日期": today}
        try:
            raw, _, _ = _get(f"https://api.llama.fi/protocol/{urllib.parse.quote(slug)}", limit=50_000_000, timeout=60, accept="application/json")
            d = json.loads(raw)
            rec.update({
                "名称": d.get("name"), "官网": d.get("url") or None, "X": d.get("twitter") or None, "GitHub": d.get("github") or [],
                "介绍": (d.get("description") or "").strip() or None, "代币": d.get("symbol") if d.get("symbol") not in (None, "-", "None") else None,
                "gecko_id": d.get("gecko_id") or None, "市值": d.get("mcap") or None, "审计数": d.get("audits"), "审计链接": d.get("audit_links") or [],
                "上线DefiLlama": _ts(d.get("listedAt")), "母协议": d.get("parentProtocolSlug") or None, "分叉自": d.get("forkedFrom") or [],
                "链": d.get("chains") or [], "合约": d.get("address") or None,
                "融资": [{"日期": _ts(r.get("date")), "轮次": r.get("round"), "金额百万": r.get("amount"), "领投": r.get("leadInvestors") or [],
                          "其他": r.get("otherInvestors") or [], "来源": r.get("source")} for r in d.get("raises") or []],
                "安全事件": [{"日期": _ts(h.get("date")), "类型": h.get("classification"), "手法": h.get("technique"), "金额": h.get("amount"),
                            "来源": h.get("source")} for h in d.get("hacks") or []],
                "大事记": [[_ts(h[0]), h[1]] for h in d.get("hallmarks") or [] if isinstance(h, list) and len(h) == 2],
            })
        except Exception as ex:
            rec["错误"] = f"DefiLlama 协议详情：{str(ex)[:100]}"
        try:
            raw, _, _ = _get(f"https://api.llama.fi/summary/fees/{urllib.parse.quote(slug)}?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true",
                             limit=20_000_000, timeout=60, accept="application/json")
            f = json.loads(raw)
            meth = f.get("methodology") or {}
            rec["口径"] = {k: meth[k] for k in ("Fees", "Revenue", "HoldersRevenue", "ProtocolRevenue", "SupplySideRevenue") if meth.get(k)}
            rec["口径代码"] = f.get("methodologyURL") or None
        except Exception as ex:
            rec.setdefault("错误", f"DefiLlama 手续费口径：{str(ex)[:100]}")
        if rec.get("官网"):
            try:
                raw, ct, final = _get(rec["官网"])
                if "html" in ct.lower() or raw[:300].lstrip().lower().startswith((b"<!doctype", b"<html")):
                    m = PageMeta(raw.decode("utf-8", errors="ignore"), final)
                    rec.update({"官网标题": m.title[:160] or None, "官网简介": m.desc(), "官网X": m.x})
            except Exception as ex:
                rec["官网错误"] = str(ex)[:120]
        info[slug] = rec
        time.sleep(0.4)
    with open(os.path.join(OC, "平台资料.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, ensure_ascii=False, indent=0, sort_keys=True)
    _CACHE.pop("pinfo", None)
    print(f"  平台资料：够门槛 {len(slugs)} 个，本次更新 {n} 个")


def platform_narrative(slug, name, url, lang="zh"):
    """二级页面的一句话：人工档案（defillama 字段或名字 / 域名对上）> DefiLlama 介绍 > 官网自述。→ (文字, 来源, 标签, 档案 id)"""
    prof = profiles()
    pid = next((k for k, v in prof.items() if not k.startswith("_") and v.get("defillama") == slug), None) \
        or _match_profile(prof, {name, domain(url or "") or None})
    info = platform_info().get(slug) or {}
    e = {"key": slug, "profile": pid, "defillama": slug, "名称": name, "官网": url}
    txt, src, tags, _ = narrative(e, lang)
    if not prof.get(pid or "", {}).get("叙事"):
        site = info.get("官网简介")
        llama = info.get("介绍")
        if llama:
            txt, src = llama, ("DefiLlama 介绍（英文原文）" if lang == "zh" else "DefiLlama description")
        elif site:
            txt, src = site, ("官网自述（英文原文，未核实）" if lang == "zh" else "From its website (unverified)")
        extra = auto_tags(llama, site, " ".join((info.get("口径") or {}).values()))
        en = {k: v[0] for k, v in TAGS.items()}
        for t in extra:
            t2 = en.get(t, t) if lang == "en" else t
            if t2 not in tags:
                tags.append(t2)
    return txt, src, tags, pid


if __name__ == "__main__":
    fetch_llama_meta()
    fetch_dossiers()
    fetch_platform_details()
