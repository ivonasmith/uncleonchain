#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性探测：每条候选链的免费公共节点 / Alchemy 能不能做「不指定合约地址」的全链铸币日志查询。
输出一张表（打到日志里）：哪个节点能用、每 1,000 个块有多少铸币事件、出块速度 → 估算每天要多少次调用。
只读，不写任何数据文件。用法：python3 pipeline/探测节点.py
"""
import json, os, time, urllib.request

TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ZERO = "0x" + "0" * 64
KEY = os.environ.get("ALCHEMY_KEY", "").strip()
UA = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (launchpad-probe)"}

# 链：[公共节点...]，Alchemy 网络名（猜的就让它报错，探测就是为了知道）
CAND = {
    "ethereum": (["https://eth.llamarpc.com", "https://cloudflare-eth.com", "https://ethereum-rpc.publicnode.com", "https://eth.drpc.org", "https://rpc.ankr.com/eth"], "eth-mainnet"),
    "xlayer": (["https://rpc.xlayer.tech", "https://xlayerrpc.okx.com", "https://xlayer.drpc.org"], "xlayer-mainnet"),
    "monad": (["https://rpc.monad.xyz", "https://rpc1.monad.xyz", "https://monad.drpc.org"], "monad-mainnet"),
    "hyperevm": (["https://rpc.hyperliquid.xyz/evm", "https://hyperliquid.drpc.org"], "hyperliquid-mainnet"),
    "ink": (["https://rpc-gel.inkonchain.com", "https://rpc-qnd.inkonchain.com", "https://ink.drpc.org"], "ink-mainnet"),
    "polygon": (["https://polygon-rpc.com", "https://polygon.drpc.org", "https://polygon-bor-rpc.publicnode.com"], "polygon-mainnet"),
    "arbitrum": (["https://arb1.arbitrum.io/rpc", "https://arbitrum.drpc.org"], "arb-mainnet"),
    "avalanche": (["https://api.avax.network/ext/bc/C/rpc", "https://avalanche.drpc.org"], "avax-mainnet"),
    "sonic": (["https://rpc.soniclabs.com", "https://sonic.drpc.org"], "sonic-mainnet"),
    "unichain": (["https://mainnet.unichain.org", "https://unichain.drpc.org"], "unichain-mainnet"),
    "megaeth": (["https://mainnet.megaeth.com/rpc", "https://carrot.megaeth.com/rpc"], "megaeth-mainnet"),
    "plasma": (["https://rpc.plasma.to"], "plasma-mainnet"),
    "stable": (["https://rpc.stable.xyz"], "stable-mainnet"),
    "mantle": (["https://rpc.mantle.xyz", "https://mantle.drpc.org"], "mantle-mainnet"),
    "optimism": (["https://mainnet.optimism.io", "https://optimism.drpc.org"], "opt-mainnet"),
    "zksync": (["https://mainnet.era.zksync.io"], "zksync-mainnet"),
    "abstract": (["https://api.mainnet.abs.xyz"], "abstract-mainnet"),
    "berachain": (["https://rpc.berachain.com", "https://berachain.drpc.org"], "berachain-mainnet"),
    # 已接入的四条，作对照
    "bsc": (["https://bsc-dataseed.bnbchain.org", "https://bsc.drpc.org"], "bnb-mainnet"),
    "base": (["https://mainnet.base.org", "https://base.drpc.org"], "base-mainnet"),
    "robinhood": (["https://rpc.mainnet.chain.robinhood.com"], "robinhood-mainnet"),
    "arc": (["https://rpc.mainnet.arc.io"], "arc-mainnet"),
}


def rpc(url, method, params, timeout=40):
    req = urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(), headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.load(r)
    if "error" in j:
        raise RuntimeError(str(j["error"].get("message") or j["error"])[:90])
    return j["result"]


def probe(url):
    t = time.time()
    try:
        head = int(rpc(url, "eth_blockNumber", []), 16)
        b = rpc(url, "eth_getBlockByNumber", [hex(head - 5), False])
        b0 = rpc(url, "eth_getBlockByNumber", [hex(head - 1005), False])
        spb = (int(b["timestamp"], 16) - int(b0["timestamp"], 16)) / 1000
    except Exception as e:
        return {"ok": False, "错误": f"基础调用失败：{e}"[:110]}
    for span in (1000, 200, 50):
        try:
            logs = rpc(url, "eth_getLogs", [{"fromBlock": hex(head - 10 - span), "toBlock": hex(head - 10), "topics": [TRANSFER, ZERO]}])
            per_day = len(logs) / span * (86400 / spb) if spb else 0
            return {"ok": True, "秒/块": round(spb, 3), "块/天": int(86400 / spb) if spb else None, "铸币事件/天(估)": int(per_day),
                    "单次跨度": span, "耗时": round(time.time() - t, 1)}
        except Exception as e:
            err = str(e)
    return {"ok": False, "秒/块": round(spb, 3), "错误": f"无地址日志查询失败：{err}"[:110]}


def main():
    rows = []
    for chain, (pubs, alc) in CAND.items():
        res = []
        for u in pubs:
            r = probe(u)
            res.append(("公共", u, r))
            if r["ok"]:
                break
        if KEY and alc:
            res.append(("Alchemy", alc, probe(f"https://{alc}.g.alchemy.com/v2/{KEY}")))
        rows.append((chain, res))
    print("\n================ 探测结果 ================")
    for chain, res in rows:
        free = next((x for x in res if x[0] == "公共" and x[2]["ok"]), None)
        alc = next((x for x in res if x[0] == "Alchemy"), None)
        verdict = "免费可用" if free else ("只能 Alchemy" if alc and alc[2]["ok"] else "都不行")
        print(f"\n[{chain}] → {verdict}")
        for kind, u, r in res:
            name = u if kind == "公共" else f"Alchemy {u}"
            print(f"   {'✔' if r['ok'] else '✘'} {name}  {json.dumps(r, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
