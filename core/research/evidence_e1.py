#!/usr/bin/env python3
"""证据库 E1：从 DefiLlama dimension-adapters 源码里抽「回购 / 销毁 / 持有人收入 / 手续费去向」相关的地址和口径说明。
只读本地克隆（默认 /workspace/defillama/dimension-adapters），不联网。结果 → core/research/evidence_e1.json。
E1 = 第三方适配器写了什么（地址 + 文件行号 + 附近注释），不等于已核实；E2 再上链核对余额 / 转账记录。
"""
import json, os, re, sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/workspace/defillama/dimension-adapters"
HERE = os.path.dirname(os.path.abspath(__file__))
# 名单里的现金流有用型 + 原观测池（币 → 适配器文件名前缀）
MAP = {"HYPE": ["hyperliquid"], "PUMP": ["pumpdotfun", "pump-swap", "pump-fun"], "CAKE": ["pancakeswap"], "UNI": ["uniswap"],
       "AAVE": ["aave"], "RAY": ["raydium"], "JUP": ["jupiter"], "GMX": ["gmx"], "AERO": ["aerodrome"], "CRV": ["curve"],
       "PENDLE": ["pendle"], "SKY": ["sky", "maker"], "ENA": ["ethena"], "ETHFI": ["ether-fi", "etherfi"], "LDO": ["lido"],
       "MORPHO": ["morpho"], "RENDER": ["render"], "NEAR": ["near"], "LINK": ["chainlink"], "PYTH": ["pyth"], "ASTER": ["aster"],
       "BNB": ["bsc", "bnb"], "TRX": ["tron"], "VIRTUAL": ["virtuals", "virtual"]}
KW = re.compile(r"buy ?back|burn|holders?revenue|HoldersRevenue|treasury|staker|revenue ?share|fee ?(recipient|collector|receiver|wallet)|distribut", re.I)
EVM = re.compile(r"0x[0-9a-fA-F]{40}")
SOL = re.compile(r"(?<![0-9A-Za-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![0-9A-Za-z])")
DIRS = ["fees", "dexs", "aggregators", "aggregator-derivatives", "options", "incentives", "helpers"]


def files_for(prefixes):
    out = []
    for d in DIRS:
        base = os.path.join(REPO, d)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if any(name.lower().startswith(p) for p in prefixes):
                p = os.path.join(base, name)
                if os.path.isdir(p):
                    for r, _, fs in os.walk(p):
                        out += [os.path.join(r, f) for f in fs if f.endswith((".ts", ".js"))]
                elif name.endswith((".ts", ".js")):
                    out.append(p)
    return out


def scan(path):
    lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
    hits, notes = [], []
    for i, ln in enumerate(lines):
        win = " ".join(lines[max(0, i - 3): i + 4])
        addrs = EVM.findall(ln) + [a for a in SOL.findall(ln) if not a.isdigit() and re.search(r"[a-z]", a) and re.search(r"[A-Z]", a)]
        if addrs and KW.search(win):
            hits.append({"line": i + 1, "addr": sorted(set(addrs)), "ctx": ln.strip()[:200]})
        if KW.search(ln) and re.search(r"(//|\*|['\"`].{20,})", ln):
            notes.append({"line": i + 1, "text": ln.strip()[:240]})
    return hits, notes


def main():
    res = {"source": "DefiLlama/dimension-adapters（本地克隆）", "level": "E1 适配器写了什么，未上链核实", "coins": {}}
    for sym, pre in MAP.items():
        fs = files_for(pre)
        recs = []
        for f in fs:
            h, n = scan(f)
            if h or n:
                recs.append({"file": os.path.relpath(f, REPO), "addresses": h, "notes": n[:12]})
        res["coins"][sym] = {"files_scanned": len(fs), "records": recs,
                             "n_addr": len({a for r in recs for x in r["addresses"] for a in x["addr"]})}
        print(f"{sym:8s} 文件 {len(fs):3d}  有记录 {len(recs):3d}  地址 {res['coins'][sym]['n_addr']}")
    json.dump(res, open(os.path.join(HERE, "evidence_e1.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
