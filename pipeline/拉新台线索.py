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
GT_NETS = {"solana": "Solana", "bsc": "BSC", "base": "Base", "robinhood": "Robinhood Chain", "arc": "Arc"}
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


def platform_name(data):
    """LaunchLab 平台配置里的名字和官网（在官网链接前面那段可读文字）。"""
    m = re.search(rb"https?://[\x21-\x7e]{4,}", data or b"")
    if not m:
        return None, None
    web = m.group(0).decode(errors="ignore")
    runs = [r.decode(errors="ignore").strip() for r in re.findall(rb"[\x20-\x7e]{2,}", data[:m.start()])]
    runs = [r for r in runs if re.search(r"[A-Za-z]{2}", r)]
    return (runs[-1][:40] if runs else None), web


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
                name, web = None, None
            else:
                gid = k
                name, web = platform_name(c)
            g = groups.setdefault(gid, {"名称": name, "官网": web, "池": 0, "成交额": 0.0, "笔数": 0, "配置": set(), "样本": [], "_币": []})
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
                "base": "https://base.blockscout.com/api/v2"}


def contract_name(chain, a):
    """Blockscout：已验证合约名（代理合约取实现合约名）。BSC 没有免费的 Blockscout，留空。"""
    api = EXPLORER_API.get(chain)
    if not api:
        return None
    try:
        j = http(f"{api}/addresses/{a}", tries=2, pause=0.3)
    except Exception:
        return None
    impl = [i.get("name") for i in (j.get("implementations") or []) if i.get("name")]
    return impl[0] if impl else (j.get("name") if j.get("is_verified") else None)


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
    for chain in ("robinhood", "bsc", "base", "arc"):
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
    gh_left = 8                                      # GitHub 代码搜索限流严，每天最多查 8 个
    for chain, a, smp in todo:
        key = f"{chain}:{a}"
        old = ids.get(key)
        if old and old.get("日期", "") >= shift(end, -13):
            continue
        r = identify(chain, smp[:30]) if smp else {"dexId": None, "重复域名": []}
        if chain != "solana":
            r["合约名"] = contract_name(chain, a)
        if gh_left > 0:
            r["GitHub"] = github(a)
            gh_left -= 1
        r["日期"] = end
        ids[key] = r
    print(f"  补身份：候选 {len(todo)}，已有记录 {len(ids)}")


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
    ds_self_described(clues, end)
    try:
        enrich(clues, end, sol)
    except Exception as e:
        print(f"  补身份失败：{e}")
    clues["更新UTC"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    save("线索.json", clues)


if __name__ == "__main__":
    main()
