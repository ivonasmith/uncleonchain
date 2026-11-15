#!/usr/bin/env python3
"""RWA 研究库导入：rwa/review/universe_export.json（Codex R1 交付）→ data/rwa/universe.json（网站「研究库」页签读这个）。

不改 Codex 交付原件，只做确定性的整理和纠错，全部规则写在这里、结果里留 raw：
  ① 实体去重：官网 / 产品页域名（取主域）；数据平台、新闻稿、社交站的域名不能当身份（R1 原件把 41 个项目并成「defillama.com」）。
     没有官网域名的：有 DefiLlama 母协议按母协议并，否则一条记录一个实体（宁可多不乱并）。
  ② 平台币四态：issued_* → issued；traditional_institution_* → tradfi；explicit_no_platform_token_* → declared_none（截至条款 / 提交时点）；
     explicit_no_governance_token_* → unverified（没有治理币 ≠ 没有平台币）；其余 unverified，认不出的进 unmapped。
  ③ 合约角色：原记录 symbol_role 写明「资产 / 存款凭证 / 稳定币，不是平台币」的，token_contracts 记 asset_token（R1 原件全记成 platform_token）；
     asset_contracts、business_contracts 照原角色；核对级别（官方 / 链上 / 目录提示）原样带上。
  ④ 市场：DEX 池子挂到同一记录、同一条链上的代币；CEX 交易对只挂到记录（symbol 只作提示，不跨记录匹配）。
  ⑤ 时间字段分开：首次发现 / 最后检查 / 资料核实 / 目录核实，不合成一个。
用法：python3 rwa/import_universe.py   （交付文件换版后重跑，再出网站）
"""
import json, os, re, hashlib
import datetime as dt
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "review", "universe_export.json")
OUT = os.path.join(ROOT, "data", "rwa", "universe.json")

NOT_IDENTITY = {"defillama.com", "llama.fi", "rwa.xyz", "coingecko.com", "coinmarketcap.com", "prnewswire.com", "businesswire.com", "globenewswire.com",
                "sec.gov", "x.com", "twitter.com", "medium.com", "github.com", "gitbook.io", "notion.site", "google.com", "linktr.ee", "dexscreener.com",
                "geckoterminal.com", "binance.com", "okx.com", "bybit.com", "coinbase.com", "etherscan.io", "solscan.io", "mirror.xyz", "substack.com",
                "reuters.com", "bloomberg.com", "theblock.co", "coindesk.com", "dune.com", "tokenterminal.com", "youtube.com", "t.me", "discord.gg"}
SEGMENTS = [  # (枚举, 中文, 关键词) 按顺序匹配 source_category / segment 原文 / 名字
    ("fund", "基金与国债", ["treasur", "t-bill", "tbill", "money market", "mmf", "fund", "国债", "基金", "货币"]),
    ("equity", "股票", ["stock", "equit", "xstock", "股票", "股权", "证券权益", "shares"]),
    ("commodity", "商品", ["gold", "silver", "commodit", "uranium", "黄金", "白银", "商品", "xau"]),
    ("credit", "信贷", ["credit", "lending", "loan", "heloc", "tranche", "信贷", "私贷", "债权", "借贷", "分层"]),
    ("realestate", "房地产", ["real estate", "realestate", "property", "reit", "房地产", "房产"]),
    ("collectible", "收藏品", ["collect", "trading card", "pokemon", " art ", "artwork", "收藏", "卡牌"]),
    ("stablecoin", "稳定币 / 存款", ["stablecoin", "deposit", "稳定币", "存款", "usd"]),
    ("trading", "交易与聚合", ["dex", "exchange", "otc", "aggregat", "amm", "交易", "聚合"]),
    ("derivatives", "衍生品", ["derivativ", "perp", "options", "衍生", "期权"]),
    ("settlement", "发行 / 结算 / 托管", ["settlement", "custod", "issuance", "transfer agent", "结算", "托管", "发行", "转让代理", "bridge", "跨链", "interop"]),
    ("identity", "身份合规", ["identity", "compliance", "kyc", "身份", "合规"]),
    ("data", "数据 / 预言机", ["oracle", "data provider", "data feed", "预言机", "数据", "估值"]),
]


def regdom(url):
    m = re.match(r"^https?://([^/:?#]+)", (url or "").strip().lower())
    if not m:
        return None
    parts = m.group(1).split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "gov", "ac") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def seg_of(*texts):
    t = " ".join(x for x in texts if isinstance(x, str)).lower()
    for k, zh, kws in SEGMENTS:
        if any(w in t for w in kws):
            return k
    return "other"


def pt_map(raw):
    r = (raw or "").lower()
    if r.startswith("issued"):
        return "issued"
    if r.startswith("traditional_institution"):
        return "tradfi"
    if r.startswith("explicit_no_platform_token"):
        return "declared_none"
    if r in ("unverified", "") or r.startswith("explicit_no_governance_token"):
        return "unverified"
    return None


def short(x, n=400):
    x = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    return x[:n]


def main():
    raw_bytes = open(SRC, "rb").read()
    u = json.loads(raw_bytes)
    R = u["raw"]["records"]
    problems, unmapped = [], []
    # ① 实体
    ent_of, ents = {}, {}
    for i, rec in enumerate(R):
        r = rec["raw"]
        rid = rec.get("id") or f"legacy:{rec['pool']}#{rec['index']}"
        dom = None
        for k in ("official_url", "official_product_url"):
            d = regdom(r.get(k))
            if d and d not in NOT_IDENTITY:
                dom = d
                break
        if dom:
            eid, basis = "ent:" + dom, "domain"
        elif r.get("parent_id"):
            eid, basis = "ent:llama-" + str(r["parent_id"]).replace("parent#", ""), "llama_parent"
        else:
            eid, basis = "ent:rec-" + re.sub(r"[^a-z0-9]+", "-", rid.lower()).strip("-"), "single_record"
        e = ents.setdefault(eid, {"id": eid, "basis": basis, "domain": dom, "records": [], "names": Counter()})
        e["records"].append(rid)
        e["names"][r.get("entity_name") or rec["name"]] += 1
        ent_of[rid] = eid
    # ② ③ ④ ⑤ 逐条
    out = []
    n_ct = Counter()
    for rec, prod in zip(R, u["products"]):
        r = rec["raw"]
        rid = rec.get("id") or f"legacy:{rec['pool']}#{rec['index']}"
        ptr = r.get("platform_token_status")
        pts = pt_map(ptr)
        if pts is None:
            pts = "unverified"
            unmapped.append({"record": rid, "raw": ptr})
        srole = (r.get("symbol_role") or "").lower()
        tok_role = "asset_token" if any(w in srole for w in ("asset", "deposit", "stablecoin")) else "platform_token"
        cts = []
        for c in r.get("token_contracts") or []:
            cts.append({"role": tok_role, "chain": c.get("chain"), "address": c.get("address"),
                        "check": c.get("verification") or c.get("evidence_level") or ("onchain" if c.get("onchain_verified") else None),
                        "src": c.get("source") or c.get("source_url"), "at": c.get("verified_at") or c.get("checked_at") or c.get("observed_at")})
        for c in r.get("asset_contracts") or []:
            cts.append({"role": "asset_token", "sub": c.get("role"), "chain": c.get("chain"), "address": c.get("address"),
                        "check": "onchain" if (c.get("block") or c.get("verified_slot")) else None, "src": c.get("source"), "at": c.get("verified_at")})
        for c in r.get("business_contracts") or []:
            cts.append({"role": "business", "sub": c.get("role"), "chain": c.get("chain") or (str(c.get("chain_id")) if c.get("chain_id") else None),
                        "address": c.get("address") or c.get("id"), "check": c.get("evidence_level") or c.get("evidence") or c.get("status"),
                        "src": c.get("source") or c.get("source_url"), "at": c.get("verified_at") or c.get("checked_at")})
        for c in cts:
            n_ct[c["role"]] += 1
            if not c.get("address"):
                problems.append(f"{rid}: 合约缺地址（{c['role']}）")
        chains_tok = {str(c.get("chain") or "").lower() for c in cts if c["role"] != "business"}
        mk = []
        for p in (r.get("dex_pools") or []) + (r.get("market_observations") or []):
            ch = str(p.get("chain") or "").lower()
            mk.append({"venue": "dex", "name": p.get("dex"), "chain": p.get("chain"), "pair": p.get("pair"),
                       "pool": p.get("pool_identifier") or p.get("pool_id"), "liq": p.get("liquidity_usd"), "vol24": p.get("volume_24h_usd"),
                       "at": p.get("observed_at") or p.get("verified_at") or p.get("source_as_of"), "src": p.get("source") or p.get("source_url"),
                       "linked": ch in chains_tok})
        for p in r.get("cex_markets") or []:
            mk.append({"venue": "cex", "name": p.get("exchange"), "pair": p.get("pair"), "at": p.get("observed_at"), "src": p.get("source"), "linked": False})
        dedup, seen = [], set()
        for m in mk:   # market_observations 是同一个池子的多次观测：只留最新一次
            k = (m["venue"], (m.get("pool") or "").lower(), m.get("pair"), m.get("name"))
            if k in seen:
                continue
            seen.add(k)
            dedup.append(m)
        notes = []
        for o in r.get("research_observations") or []:
            if isinstance(o, dict):
                notes.append({"at": o.get("observed_at") or o.get("event_date") or o.get("publication_date"), "text": short(o.get("note") or o.get("stage") or "", 600),
                              "src": o.get("source") or o.get("source_url"), "level": o.get("evidence_level")})
        out.append({
            "rid": rid, "pool": rec["pool"], "name": rec["name"], "entity": ent_of[rid],
            "segment": seg_of(r.get("source_category") if r.get("source_category") != "RWA" else None, prod.get("segment") if prod.get("segment") != "RWA" else None,
                              r.get("business_role"), rec["name"], r.get("description_source")),
            "segment_raw": prod.get("segment"), "role_text": short(r.get("business_role"), 200) if r.get("business_role") else None,
            "chains": r.get("chains") or [], "pt": pts, "pt_raw": ptr, "symbol": r.get("symbol_hint"), "symbol_role": r.get("symbol_role"),
            "evidence": r.get("evidence_level"), "tier": r.get("monitor_tier"), "stage": r.get("launch_stage"),
            "official": r.get("official_url") or r.get("official_product_url"), "source": r.get("source_url"),
            "first_seen": r.get("first_seen_at"), "last_checked": r.get("last_checked_at"), "verified_at": r.get("verified_at"),
            "directory_checked": r.get("directory_checked_at"), "regional": r.get("regional_restrictions"),
            "contracts": cts, "markets": dedup, "notes": notes, "questions": r.get("questions") if isinstance(r.get("questions"), list) else None})
    entities = []
    for e in ents.values():
        entities.append({"id": e["id"], "name": e["names"].most_common(1)[0][0], "basis": e["basis"], "domain": e["domain"], "records": e["records"]})
    entities.sort(key=lambda e: -len(e["records"]))
    mk_all = [m for x in out for m in x["markets"]]
    res = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": {"file": "rwa/review/universe_export.json", "sha256": hashlib.sha256(raw_bytes).hexdigest(), "exported_utc": u.get("exported_utc"),
                   "library_sha256": u.get("source_sha256"), "note": "Codex R1 交付；checked_utc 是导出时刻，不是逐条核实时间"},
        "counts": {"records": len(out), "main": sum(1 for x in out if x["pool"] == "main"), "discovery": sum(1 for x in out if x["pool"] == "discovery"),
                   "missing_id": sum(1 for x in out if x["rid"].startswith("legacy:")), "entities": len(entities),
                   "entities_by_basis": dict(Counter(e["basis"] for e in entities)), "r1_entities": u["counts"].get("entities"),
                   "pt": dict(Counter(x["pt"] for x in out)), "segment": dict(Counter(x["segment"] for x in out)),
                   "contracts": dict(n_ct), "markets": len(mk_all), "markets_dex_linked": sum(1 for m in mk_all if m["venue"] == "dex" and m["linked"]),
                   "markets_dex": sum(1 for m in mk_all if m["venue"] == "dex"), "markets_cex": sum(1 for m in mk_all if m["venue"] == "cex"),
                   "evidence": dict(Counter(x["evidence"] or "U" for x in out))},
        "entities": entities, "records": out, "unmapped": unmapped, "problems": problems,
        "segments": {k: zh for k, zh, _ in SEGMENTS} | {"other": "其他"},
    }
    if res["counts"]["records"] != u["counts"]["records"]:
        problems.append(f"记录数对不上：导出 {u['counts']['records']}，读到 {res['counts']['records']}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    c = res["counts"]
    print(f"记录 {c['records']}（主库 {c['main']} + 发现 {c['discovery']}，缺 id {c['missing_id']}）→ 实体 {c['entities']}（R1 原件 {c['r1_entities']}）{c['entities_by_basis']}")
    print(f"平台币 {c['pt']} · 合约 {c['contracts']} · 市场 DEX {c['markets_dex']}（挂上代币 {c['markets_dex_linked']}）CEX {c['markets_cex']}")
    print(f"分类 {c['segment']}")
    for p in problems[:20]:
        print("问题：", p)


if __name__ == "__main__":
    main()
