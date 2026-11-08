#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发射台日更 · 新发射台线索（链上扫描之外的补充 + 给候选补身份）→ data/onchain/solana.json、data/onchain/线索.json

1. GeckoTerminal 发射台 / DEX 目录：Solana、BSC、Base、Robinhood Chain、Arc 每天比对，新冒出来的条目记「首次出现」。
   GeckoTerminal 会把知名前端单独列出来（Bags.fm、letsbonk.fun、Boop.fun 等），新收录的入口在这里先看到。
2. Solana 公共发币设施上的前端拆分（Solana 没有「一个发射台一个工厂合约」，多数新台子是在公共设施上套前端）：
   · Meteora DBC：池子账户偏移 72 = 配置账户，配置偏移 40 = 合作方（手续费接收地址）→ 按合作方合并成一个前端
   · Raydium LaunchLab：池子偏移 173 = 平台配置，平台配置里存着平台名字和官网 → 自动起名
   样本 = GeckoTerminal 上该设施近 24 小时最活跃的池子（GeckoTerminal 已经单独列出的前端不在这里），每天各取最多 200 个。
3. DEX Screener 最新代币资料：简介里自称提供发币 / 发射服务的项目（launchpad、token launcher、bonding curve、fair launch、发射台）。
4. 补身份：链上扫出的候选工厂 / Solana 前端，拿样本币去 DEX Screener 看挂在哪个交易所（dexId）、
   官网域名是否在多个样本币上重复出现（那多半是发射台自己的域名）；再用地址、名字去 GitHub 搜公开代码（需要 GITHUB_TOKEN）。
   查不到就留空，不猜。

免费接口都有限流：GeckoTerminal 每分钟约 30 次（这里每次间隔 2.5 秒），DEX Screener 每分钟 60～300 次。
"""
import json, os, re, sys, time, base64, datetime as dt, urllib.request, urllib.error, urllib.parse
from collections import Counter, defaultdict
from common import DATA, today_utc, shift

GT = "https://api.geckoterminal.com/api/v2"
DS = "https://api.dexscreener.com"
SOL_RPC = ["https://api.mainnet-beta.solana.com"]
if os.environ.get("ALCHEMY_KEY"):
    SOL_RPC.append(f"https://solana-mainnet.g.alchemy.com/v2/{os.environ['ALCHEMY_KEY'].strip()}")
GT_NETS = {"solana": "Solana", "bsc": "BSC", "base": "Base", "robinhood": "Robinhood Chain", "arc": "Arc", "eth": "Ethereum",
           "arbitrum": "Arbitrum", "optimism": "Optimism", "polygon_pos": "Polygon", "avax": "Avalanche", "x-layer": "X Layer",
           "mantle": "Mantle", "zksync": "zkSync Era"}
DS_CHAIN = {"robinhood": "robinhood", "bsc": "bsc", "base": "base", "arc": "arc", "solana": "solana"}
DBC, LAUNCHLAB = "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN", "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj"
POOL_PAGES = 10            # GeckoTerminal 每页 20 个池子
KEYWORDS = ("launchpad", "token launcher", "launch platform", "bonding curve", "fair launch", "发射台", "发币平台", "memecoin launcher")
OUT = os.path.join(DATA, "onchain")
UA = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (launchpad-daily)"}
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58(b):
    n, s = int.from_bytes(b, "big"), ""
    while n:
        n, r = divmod(n, 58)
        s = B58[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + s


def http(url, data=None, headers=None, tries=5, pause=0.0):
    h = dict(UA, **(headers or {}))
    if data is not None:
        h["Content-Type"] = "application/json"
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=h)
            with urllib.request.urlopen(req, timeout=60) as r:
                out = json.load(r)
            if pause:
                time.sleep(pause)
            return out
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code == 429:
                time.sleep(15 * (i + 1))
                continue
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:
            last = str(e)[:120]
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url.split('?')[0][:80]} → {last}")


def gt(path):
    return http(GT + path, pause=2.5)


def sol_accounts(keys):
    out = []
    for i in range(0, len(keys), 100):
        part, res = keys[i:i + 100], None
        for url in SOL_RPC:
            try:
                j = http(url, {"jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts", "params": [part, {"encoding": "base64"}]})
                res = j["result"]["value"]
                break
            except Exception:
                continue
        out += res if res is not None else [None] * len(part)
    return [base64.b64decode(a["data"][0]) if a else None for a in out]


def load(name, default):
    p = os.path.join(OUT, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def save(name, obj):
    json.dump(obj, open(os.path.join(OUT, name), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------- 1. GeckoTerminal 目录
def gt_directory(clues, end):
    dirs = clues.setdefault("目录", {})
    for net, nm in GT_NETS.items():
        try:
            ids, p = {}, 1
            while p <= 5:
                j = gt(f"/networks/{net}/dexes?page={p}")
                for x in j.get("data") or []:
                    ids[x["id"]] = x["attributes"]["name"]
                if not (j.get("links") or {}).get("next"):
                    break
                p += 1
        except Exception as e:
            print(f"  GeckoTerminal 目录 {nm} 失败：{e}")
            continue
        d = dirs.setdefault(net, {})
        init = not d
        for k, v in ids.items():
            if k not in d:
                d[k] = {"名称": v, "首次出现": "基线" if init else end}
        print(f"  GeckoTerminal 目录 {nm}：{len(ids)} 个（{'建基线' if init else '新增 ' + str(sum(1 for x in d.values() if x['首次出现'] == end))}）")


# ---------------------------------------------------------------- 2. Solana 公共设施上的前端
def gt_pools(dex):
    out = []
    for p in range(1, POOL_PAGES + 1):
        try:
            j = gt(f"/networks/solana/dexes/{dex}/pools?page={p}&sort=h24_tx_count_desc")
        except Exception as e:
            print(f"  GeckoTerminal {dex} 第 {p} 页失败：{e}")
            break
        page = j.get("data") or []
        out += page
        if len(page) < 20:                 # 这个接口不给 next 链接，翻到不满一页为止
            break
    seen, uniq = set(), []
    for x in out:
        a = x["attributes"]["address"]
        if a not in seen:
            seen.add(a)
            uniq.append(x)
    return uniq


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _cstr(b):
    return b.split(b"\0")[0].decode("utf-8", errors="ignore").strip()


def _url(u):
    u = (u or "").strip()
    if not u or " " in u or "." not in u:
        return None
    return u if u.startswith("http") else "https://" + u


def platform_name(data):
    """LaunchLab 平台配置（PlatformConfig）里的名字、官网、图标：固定字段 name [112:176]、web [176:432]、img [432:688]
    （2026-11-08 对 Float 配置实测）。老版本 / 长度不够时退回「官网链接前那段可读文字」的猜法。"""
    data = data or b""
    if len(data) >= 688:
        name, web, img = _cstr(data[112:176]), _url(_cstr(data[176:432])), _url(_cstr(data[432:688]))
        if web and re.search(r"\.(png|jpe?g|gif|webp|svg)(\?|$)|img|image|attachments|catbox", web, re.I):
            web, img = None, img or web                # 有人把图标填进了官网栏
        if name or web:
            return (name[:40] or None), web, img
    m = re.search(rb"https?://[\x21-\x7e]{4,}", data)
    if not m:
        return None, None, None
    web = m.group(0).decode(errors="ignore")
    runs = [r.decode(errors="ignore").strip() for r in re.findall(rb"[\x20-\x7e]{2,}", data[:m.start()])]
    runs = [r for r in runs if re.search(r"[A-Za-z]{2}", r)]
    return (runs[-1][:40] if runs else None), web, None


def solana_frontends():
    res = {}
    for dex, prog, off in (("meteora-dbc", DBC, 72), ("raydium-launchlab", LAUNCHLAB, 173)):
        pools = gt_pools(dex)
        if not pools:
            continue
        datas = sol_accounts([x["attributes"]["address"] for x in pools])
        ref = {}
        for x, d in zip(pools, datas):
            if d and len(d) >= off + 32:
                ref[x["attributes"]["address"]] = b58(d[off:off + 32])
        keys = sorted(set(ref.values()))
        cfg = dict(zip(keys, sol_accounts(keys)))
        groups = {}
        for x in pools:
            a = x["attributes"]["address"]
            k = ref.get(a)
            if not k:
                continue
            c = cfg.get(k) or b""
            if dex == "meteora-dbc":
                gid = b58(c[40:72]) if len(c) >= 72 else k          # 合作方（手续费接收地址）
                name, web, img = None, None, None
            else:
                gid = k
                name, web, img = platform_name(c)
            g = groups.setdefault(gid, {"名称": name, "官网": web, "图标": img, "池": 0, "成交额": 0.0, "笔数": 0, "配置": set(), "样本": [], "_币": []})
            at = x["attributes"]
            g["池"] += 1
            g["成交额"] += _num((at.get("volume_usd") or {}).get("h24"))
            tx = (at.get("transactions") or {}).get("h24") or {}
            g["笔数"] += int(tx.get("buys") or 0) + int(tx.get("sells") or 0)
            g["配置"].add(k)
            base = (((x.get("relationships") or {}).get("base_token") or {}).get("data") or {}).get("id", "")
            if len(g["样本"]) < 3 and base.startswith("solana_"):
                g["样本"].append(base[7:])
            if base.startswith("solana_"):
                g["_币"].append(base[7:])
        for v in groups.values():                   # 发射台常给币地址定制后缀（pump、bonk、BAGS…）：样本里过半同后缀就记下
            sfx = Counter(t[-4:] for t in v.pop("_币"))
            top = sfx.most_common(1)
            v["后缀"] = top[0][0] if top and top[0][1] >= 2 and top[0][1] >= 0.6 * sum(sfx.values()) else None
        res[dex] = {"样本池": len(pools), "前端": {k: dict(v, 配置=len(v["配置"]), 成交额=round(v["成交额"])) for k, v in
                                                  sorted(groups.items(), key=lambda kv: -kv[1]["成交额"])}}
        print(f"  Solana {dex}：样本池 {len(pools)}，前端 {len(groups)}")
    return res


# ---------------------------------------------------------------- 3. DEX Screener 最新代币资料
def ds_self_described(clues, end):
    try:
        xs = http(f"{DS}/token-profiles/latest/v1")
    except Exception as e:
        print(f"  DEX Screener 代币资料失败：{e}")
        return
    hits = clues.setdefault("自称发射台", {})
    n = 0
    for x in xs if isinstance(xs, list) else []:
        desc = (x.get("description") or "").lower()
        if any(k in desc for k in KEYWORDS):
            key = f'{x.get("chainId")}:{(x.get("tokenAddress") or "").lower()}'
            if key not in hits:
                hits[key] = {"日期": end, "链": x.get("chainId"), "代币": x.get("tokenAddress"), "简介": (x.get("description") or "")[:200],
                             "链接": [l.get("url") for l in (x.get("links") or []) if l.get("url")][:5], "页面": x.get("url")}
                n += 1
    # 只留 60 天
    cut = shift(end, -60)
    for k in [k for k, v in hits.items() if v["日期"] < cut]:
        del hits[k]
    print(f"  DEX Screener 自称发射台：新增 {n}，共 {len(hits)}")


# ---------------------------------------------------------------- 4. 补身份
def ds_tokens(chain, addrs):
    out = []
    for i in range(0, len(addrs), 30):
        try:
            j = http(f"{DS}/tokens/v1/{chain}/{','.join(addrs[i:i + 30])}", pause=0.4)
            out += j if isinstance(j, list) else []
        except Exception:
            pass
    return out


def domain(u):
    try:
        h = urllib.parse.urlparse(u).netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


SOCIAL = ("x.com", "twitter.com", "t.me", "discord.gg", "discord.com", "youtube.com", "tiktok.com", "instagram.com", "github.com", "medium.com")


def identify(chain, samples):
    """样本币 → DEX Screener：最常见的 dexId、在多个样本上重复出现的官网域名（发射台自己的域名）。"""
    pairs = ds_tokens(DS_CHAIN.get(chain, chain), samples)
    dex, doms = Counter(), Counter()
    for p in pairs:
        dex[p.get("dexId")] += 1
        info = p.get("info") or {}
        ds_ = {domain(w.get("url", "")) for w in (info.get("websites") or [])}
        ds_ |= {domain(s.get("url", "")) for s in (info.get("socials") or []) if s.get("url")}
        for d in ds_:
            if d and not any(d == s or d.endswith("." + s) for s in SOCIAL):
                doms[d] += 1
    rep = [d for d, c in doms.most_common(3) if c >= 2]
    return {"dexId": dex.most_common(1)[0][0] if dex else None, "重复域名": rep}


EXPLORER_API = {"robinhood": "https://explorer.chain.robinhood.com/api/v2", "arc": "https://explorer.arc.io/api/v2",
                "base": "https://base.blockscout.com/api/v2", "ethereum": "https://eth.blockscout.com/api/v2",
                "optimism": "https://optimism.blockscout.com/api/v2", "arbitrum": "https://arbitrum.blockscout.com/api/v2",
                "polygon": "https://polygon.blockscout.com/api/v2", "ink": "https://explorer.inkonchain.com/api/v2"}


EIP1967 = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
PROXY_NAMES = {"TransparentUpgradeableProxy", "ERC1967Proxy", "BeaconProxy", "UUPSProxy", "Proxy", "AdminUpgradeabilityProxy", "OptimizedTransparentUpgradeableProxy"}
CHAIN_ID = {"bsc": 56, "base": 8453, "ethereum": 1, "arbitrum": 42161, "optimism": 10, "polygon": 137, "robinhood": 4663, "arc": 5042,
            "xlayer": 196, "monad": 143, "hyperevm": 999, "ink": 57073, "abstract": 2741, "berachain": 80094, "avalanche": 43114,
            "sonic": 146, "mantle": 5000, "plasma": 9745, "zksync": 324, "unichain": 130, "stable": 988, "megaeth": 4326}
GT_NET = {"bsc": "bsc", "base": "base", "ethereum": "eth", "arbitrum": "arbitrum", "optimism": "optimism", "polygon": "polygon_pos",
          "robinhood": "robinhood", "arc": "arc", "avalanche": "avax", "xlayer": "x-layer", "mantle": "mantle", "zksync": "zksync"}


def _rpc_url(chain):
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("oc", os.path.join(os.path.dirname(os.path.abspath(__file__)), "拉链上新台.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        ch = m.CHAINS.get(chain) or {}
        if ch.get("公共"):
            return ch["公共"]
        if ch.get("alchemy") and m.KEY:
            return f"https://{ch['alchemy']}.g.alchemy.com/v2/{m.KEY}"
    except Exception:
        pass
    return None


def implementation(chain, a):
    """EIP-1967 代理：读存储槽拿实现合约地址。"""
    url = _rpc_url(chain)
    if not url:
        return None
    try:
        j = http(url, {"jsonrpc": "2.0", "id": 1, "method": "eth_getStorageAt", "params": [a, EIP1967, "latest"]}, tries=2)
        v = j.get("result") or "0x0"
        return ("0x" + v[-40:]) if int(v, 16) else None
    except Exception:
        return None


def sourcify(chain, a):
    cid = CHAIN_ID.get(chain)
    if not cid:
        return None
    try:
        j = http(f"https://sourcify.dev/server/v2/contract/{cid}/{a}?fields=compilation", tries=2, pause=0.2)
        return (j.get("compilation") or {}).get("name")
    except Exception:
        return None


ETHERSCAN_KEY = os.environ.get("ETHERSCAN_KEY", "").strip()
ES_STATE = {"失败": 0, "最后错误": None}


def etherscan_name(chain, a):
    """Etherscan V2（一个 key 查几十条链）：已验证合约名；代理合约顺着 Implementation 再查一次。
    注意免费档有的链不开放（返回 NOTOK），这时退回 Sourcify 等，错误记在 ES_STATE 里写进日志。"""
    cid = CHAIN_ID.get(chain)
    if not (ETHERSCAN_KEY and cid) or ES_STATE["失败"] >= 5:      # 连续失败 5 次（多半是额度 / 不开放）就不再调
        return None

    def one(addr):
        q = urllib.parse.urlencode({"chainid": cid, "module": "contract", "action": "getsourcecode", "address": addr, "apikey": ETHERSCAN_KEY})
        j = http(f"https://api.etherscan.io/v2/api?{q}", tries=2, pause=0.25)       # 免费档每秒 5 次
        if str(j.get("status")) != "1":
            ES_STATE["失败"] += 1
            ES_STATE["最后错误"] = f"{chain}: {str(j.get('result') or j.get('message'))[:120]}"
            return None, None
        ES_STATE["失败"] = 0
        r = (j.get("result") or [{}])[0]
        return (r.get("ContractName") or None), (r.get("Implementation") or None)
    try:
        nm, imp = one(a)
        if imp and (not nm or nm in PROXY_NAMES):
            nm2, _ = one(imp)
            nm = nm2 or nm
        return nm if nm and nm not in PROXY_NAMES else None
    except Exception as e:
        ES_STATE["失败"] += 1
        ES_STATE["最后错误"] = str(e)[:120]
        return None


def contract_name(chain, a):
    """合约名，依次试：Etherscan（有 key 时）→ Blockscout 验证名（带实现合约）→ Sourcify → 是代理就读 EIP-1967 实现合约再查 Sourcify。"""
    nm0 = etherscan_name(chain, a)
    if nm0:
        return nm0
    api = EXPLORER_API.get(chain)
    if api:
        try:
            j = http(f"{api}/addresses/{a}", tries=2, pause=0.3)
            impl = [i.get("name") for i in (j.get("implementations") or []) if i.get("name")]
            nm = impl[0] if impl else (j.get("name") if j.get("is_verified") else None)
            if nm and nm not in PROXY_NAMES:
                return nm
        except Exception:
            pass
    nm = sourcify(chain, a)
    if nm and nm not in PROXY_NAMES:
        return nm
    imp = implementation(chain, a)
    if imp:
        nm2 = sourcify(chain, imp)
        if nm2 and nm2 not in PROXY_NAMES:
            return nm2
    return None


def gt_dex(chain, samples):
    """样本币在 GeckoTerminal 上挂在哪个交易所（发射台曲线池常直接标平台名，如 four-meme）。"""
    net = GT_NET.get(chain)
    if not net:
        return None
    c = Counter()
    for t in samples[:2]:
        try:
            j = gt(f"/networks/{net}/tokens/{t}/pools?page=1")
        except Exception:
            continue
        for p in j.get("data") or []:
            c[(((p.get("relationships") or {}).get("dex") or {}).get("data") or {}).get("id")] += 1
    top = [d for d, _ in c.most_common() if d and not d.startswith(("uniswap", "pancakeswap", "aerodrome", "sushiswap"))]
    return top[0] if top else None


def github(q):
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok:
        return None
    try:
        j = http("https://api.github.com/search/code?q=" + urllib.parse.quote(q) + "&per_page=5",
                 headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}, tries=2, pause=7)
        return [{"仓库": i["repository"]["full_name"], "文件": i["path"], "链接": i["html_url"]} for i in (j.get("items") or [])[:3]]
    except Exception:
        return None


def enrich(clues, end, sol):
    """给候选补身份：链上工厂近 7 天新币 ≥ 30 的、Solana 前端成交额前列的。每个候选只查一次（结果缓存 14 天）。"""
    ids = clues.setdefault("身份", {})
    todo = []
    chains = sorted(f[:-5] for f in os.listdir(OUT) if f.endswith(".json") and f not in ("solana.json", "线索.json", "ai_agent.json"))
    for chain in chains:
        p = os.path.join(OUT, f"{chain}.json")
        if not os.path.exists(p):
            continue
        db = json.load(open(p, encoding="utf-8"))
        days = db.get("逐日") or {}
        w7 = sorted(days)[-7:]
        agg, smp = Counter(), defaultdict(list)
        for d in w7:
            for a, v in days[d]["工厂"].items():
                agg[a] += v[0]
                smp[a] += [t for t in v[2] if t not in smp[a]]
        for a, n in agg.most_common(15):
            if n >= 30:
                todo.append((chain, a, smp.get(a) or []))
    for dex, blk in (sol or {}).items():
        for gid, g in list(blk["前端"].items())[:10]:
            todo.append(("solana", gid, g.get("样本") or []))
    gt_left = 40                                     # GeckoTerminal 限流：每天最多给 40 个没名字的候选查交易所
    gh_left = 8                                      # GitHub 代码搜索限流严，每天最多查 8 个
    for chain, a, smp in todo:
        key = f"{chain}:{a}"
        old = ids.get(key)
        if old and old.get("日期", "") >= shift(end, -13) and old.get("查名v") == 3:
            continue
        r = identify(chain, smp[:30]) if smp else {"dexId": None, "重复域名": []}
        if chain != "solana":
            r["合约名"] = contract_name(chain, a)
            if not r["合约名"] and gt_left > 0:
                r["交易所"] = gt_dex(chain, [t for t in smp if t != a])
                gt_left -= 1
        if gh_left > 0:
            r["GitHub"] = github(a)
            gh_left -= 1
        r["日期"] = end
        r["查名v"] = 3                               # v2：Sourcify + 代理实现合约 + GeckoTerminal；v3：加 Etherscan；旧记录重查
        ids[key] = r
    named = sum(1 for v in ids.values() if v.get("合约名"))
    print(f"  补身份：候选 {len(todo)}，已有记录 {len(ids)}，查到合约名 {named}"
          + (f"；Etherscan {'未配置' if not ETHERSCAN_KEY else ('正常' if not ES_STATE['最后错误'] else '有报错：' + ES_STATE['最后错误'])}"))


# ---------------------------------------------------------------- 5. AI Agent 叙事的发射台（重点关注）
AI_STRONG = re.compile(r"ai[- ]?agents?|agentic|autonomous ai|launch(?:es|ing)? (?:and trade )?ai|tokeni[sz]e[sd]? ai|agent launchpad|ai idols?|virtuals", re.I)
AI_WEAK = re.compile(r"\b(?:ai|a\.i\.|llm|gpt|aigc)\b|ai-(?:powered|audited|generated)", re.I)
AI_LAUNCH = re.compile(r"launch|tokeni[sz]|bonding curve|fair launch|issuance", re.I)


def ai_agents(end):
    """DefiLlama 全部协议：Launchpad 类目按介绍分强相关 / 待确认；AI Agents 类目里做发币 / 代币化的也列入；人工名单修正。"""
    try:
        meta = http("https://api.llama.fi/protocols", tries=3)
        ov = http("https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true", tries=3)
    except Exception as e:
        print(f"  AI Agent 名单失败：{e}")
        return
    cp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "ai_agent_launchpads.json")
    cfg = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}
    fees = {p.get("slug"): p for p in ov.get("protocols") or []}
    inc, exc = cfg.get("包含") or {}, cfg.get("排除") or {}
    rows = []
    for m in meta:
        slug, cat = m.get("slug"), m.get("category")
        if not slug or slug in exc:
            continue
        txt = " ".join([m.get("name") or "", m.get("description") or ""])
        tier = None
        if slug in inc:
            tier = inc[slug].get("档") or "强相关"
        elif cat == "Launchpad":
            tier = "强相关" if AI_STRONG.search(txt) else ("待确认" if AI_WEAK.search(txt) else None)
        elif cat == "AI Agents" and AI_LAUNCH.search(txt) and AI_STRONG.search(txt):
            tier = "强相关"
        if not tier:
            continue
        f = fees.get(slug) or {}
        rows.append({"slug": slug, "名称": m.get("name"), "类目": cat, "档": tier, "链": (m.get("chains") or f.get("chains") or [])[:4],
                     "介绍": (m.get("description") or "")[:200], "官网": m.get("url"), "推特": m.get("twitter"),
                     "当日": f.get("total24h"), "7日": f.get("total7d"), "30日": f.get("total30d"), "备注": (inc.get(slug) or {}).get("备注")})
    rows.sort(key=lambda r: (r["档"] != "强相关", -(r["30日"] or 0)))
    old = load("ai_agent.json", {})
    first = old.get("首次出现") or {}
    init = not first
    for r in rows:
        first.setdefault(r["slug"], "基线" if init else end)
        r["首次出现"] = first[r["slug"]]
    save("ai_agent.json", {"日期": end, "更新UTC": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"), "平台": rows, "首次出现": first})
    print(f"  AI Agent 发射台：强相关 {sum(r['档'] == '强相关' for r in rows)}，待确认 {sum(r['档'] == '待确认' for r in rows)}")


def main():
    os.makedirs(OUT, exist_ok=True)
    end = shift(today_utc(), -1)
    clues = load("线索.json", {})
    gt_directory(clues, end)
    sol = {}
    try:
        sol = solana_frontends()
    except Exception as e:
        print(f"  Solana 前端拆分失败：{e}")
    if sol:
        sdb = load("solana.json", {"链": "Solana", "浏览器": "https://solscan.io", "逐日": {}})
        sdb["逐日"][end] = sol
        sdb["逐日"] = {k: v for k, v in sorted(sdb["逐日"].items()) if k >= shift(end, -120)}
        first = {}
        ds = sorted(sdb["逐日"])
        cut = shift(ds[0], 2)
        for d in ds:
            for dex, blk in sdb["逐日"][d].items():
                for gid in blk["前端"]:
                    first.setdefault(f"{dex}:{gid}", "基线" if d <= cut else d)
        sdb["首次出现"] = first
        sdb["更新UTC"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
        save("solana.json", sdb)
    ai_agents(end)
    ds_self_described(clues, end)
    try:
        enrich(clues, end, sol)
    except Exception as e:
        print(f"  补身份失败：{e}")
    clues["更新UTC"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    save("线索.json", clues)


if __name__ == "__main__":
    main()
