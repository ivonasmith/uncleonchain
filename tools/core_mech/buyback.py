#!/usr/bin/env python3
"""回购 / 销毁 12 个月链上数量（证据库 E2 → E3）→ data/core/buyback.json。只用标准库，在 Actions 里跑（ALCHEMY_KEY）。
地址出处：core/research/evidence_e2.json（Codex 2026-11-14 核查）。每个币的计数规则写死在 MEASURES 里，跑之前定、跑完不改；改规则要在这里写原因。

计数原则（照 Codex 核查报告的口径）：
- 只数目标代币本身、窗口 [今天−365 天, 今天) UTC 内、能逐笔对上的链上记录；回购和销毁分开，不相加。
- 回购 = 目标代币从 DEX 结算合约（CoW / 交易对）转入官方回购地址；不是所有流入都算（国库调拨、赎回、往返不算）。
- 销毁 = 目标代币从官方地址转到销毁地址（0x…dEaD / 0x0），或 Solana 上对应账户的 Burn / BurnChecked 指令。
- 每条都附「其余流入」的对手方明细（diag），方便人工复核归因；取不全（翻页上限、接口报错）就标 partial，不当成完整数。
"""
import json, os, sys, time, urllib.request
import datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "core", "buyback.json")
KEY = os.environ.get("ALCHEMY_KEY", "").strip()
NET = {"eth": "eth-mainnet", "bnb": "bnb-mainnet", "arb": "arb-mainnet", "sol": "solana-mainnet"}
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
DEAD = ["0x000000000000000000000000000000000000dead", "0x0000000000000000000000000000000000000000"]
COW = "0x9008d19f58aabd9ed0d60971565aa8510560ab41"   # CoW Protocol GPv2Settlement（以太坊）
NOW = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
T0, T1 = NOW - dt.timedelta(days=365), NOW
ERR = []

TOK = {"UNI": ("eth", "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", 18), "LDO": ("eth", "0x5a98fcbea516cf06857215779fd812ca3bef1b32", 18),
       "AAVE": ("eth", "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9", 18), "ETHFI": ("eth", "0xfe0c30065b384f05761f15d0cc899d4f9f9cc0eb", 18),
       "SKY": ("eth", "0x56072c95faa701256059aa122697b133aded9279", 18), "CAKE": ("bnb", "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82", 18),
       "ASTER": ("bnb", "0x000ae314e2a2172a039b26378814c252734f556a", 18), "GMX": ("arb", "0xfc5a1a6eb076a2c7ad06ed22c90d7e710e35ad0a", 18),
       "JUP": ("sol", "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN", 6), "RAY": ("sol", "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", 6),
       "RENDER": ("sol", "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof", 8), "PUMP": ("sol", "pumpCmXqMfrsAkQ5r49WcJnRayYRqmXz6ae8H7H9Dfn", 6)}

# kind: buyback（回购）/ burn（销毁）/ hold（持仓变化，只作参考）
# EVM：to = 官方地址集合，src = 只数这些对手方转来的（None = 全部流入都列进 diag，但 qty 只认 src）
MEASURES = [
    # 11-15 改：Firepit 的 release 是调用者自己把 UNI 送去销毁（发送方 = 调用者），所以按「交易调用的合约 = Firepit」认，不按发送方
    {"sym": "UNI", "kind": "burn", "label": "以太坊 Firepit 交易里送去销毁的 UNI", "to": DEAD, "via_tx_to": ["0x0d5cd355e2abeb8fb1552f56c965b867346d6721"], "diag_all_to_dead": True},
    {"sym": "LDO", "kind": "buyback", "label": "CoW 成交转入回购 Safe / Aragon Agent 的 LDO", "to": ["0xf6f0732c1e9971497342c295141566e6f1a31e96", "0x3e40d73eb977dc6a537af587d48316fee66e9c8c"], "src": [COW]},
    {"sym": "AAVE", "kind": "buyback", "label": "CoW 成交转入 AFC / Collector / Swap Steward 的 AAVE",
     "to": ["0x22740deba78d5a0c24c58c740e3715ec29de1bfa", "0x464c71f6c2f760dda6093dcb91c24c39e5d6e18c", "0xb7d402138cb01bfe97d95181c849379d6ad14d19"], "src": [COW]},
    {"sym": "ETHFI", "kind": "buyback", "label": "CoW 成交转入基金会钱包 / 回购 Safe / 回购合约的 ETHFI",
     "to": ["0x2f5301a3d59388c509c65f8698f521377d41fd0f", "0x43f4ca92f7f378bcdcf1508b866b5b6c47d6408c", "0xa7b1d3a045fe9566513f3ecc858469640c88be29"], "src": [COW]},
    {"sym": "SKY", "kind": "buyback", "label": "（诊断）MCD_FLAP 相关的 SKY 流动", "to": ["0x374d9c3d5134052bc558f432afa1df6575f07407"], "src": [], "diag_only": True},
    {"sym": "CAKE", "kind": "burn", "label": "费用归集多签转去销毁地址的 CAKE", "to": DEAD, "frm": ["0xceba60280fb0ecd9a5a26a1552b90944770a4a0e"], "diag_all_to_dead": False},
    {"sym": "ASTER", "kind": "burn", "label": "buybackWalletToBurn 转去销毁地址的 ASTER（BNB Chain，候选地址）", "to": DEAD, "frm": ["0x5e4969c41ca9f9831468b98328a370b7abd5a397"]},
    {"sym": "ASTER", "kind": "buyback", "label": "（诊断）转入公开 buyback 钱包的 ASTER（BNB Chain；链归属未独立确认）", "to": ["0xa0edbabcb48034e368de286b49f9603c7afa1b60"], "src": [], "diag_only": True},
    {"sym": "GMX", "kind": "buyback", "label": "（诊断）进出 Arbitrum FeeHandler 的 GMX", "to": ["0x7eb417637a3e6d1c19e6d69158c47610b7a5d9b3"], "src": [], "diag_only": True},
    # Solana：owner = 官方地址，算该 owner 名下目标代币账户的流入 / Burn 指令
    {"sym": "JUP", "kind": "buyback", "label": "Litterbox 的 JUP 流入（回购持有）", "owner": ["6tZT9AUcQn4iHMH79YZEXSy55kDLQ4VbA3PMtfLVNsFX"]},
    {"sym": "RAY", "kind": "buyback", "label": "回购持仓地址的 RAY 流入", "owner": ["DdHDoz94o2WJmD9myRobHCwtx1bESpHTd4SSPe6VEZaz"]},
    {"sym": "RENDER", "kind": "burn", "label": "BME 销毁钱包名下 RENDER 账户的 Burn 指令", "owner": ["rbrnm7nPhfhBxPSh8qhRFrhB5MLnJGMNoyNQPvSi7vq"], "burn_only": True},
    {"sym": "PUMP", "kind": "buyback", "label": "（候选地址）8 个回购执行钱包的 PUMP 流入与 Burn", "owner": [
        "3vkpy5YHqnqJTnA5doWTpcgKyZiYsaXYzYM9wm8s3WTi", "88uq8JNL6ANwmow1og7VQD4hte73Jpw8qsUP77BtF6iE", "3YNxfRAEqKrGNCmx5JUfCD9er5djZToqSomzR2Yi8rqx",
        "99mRw3EzdJZWEUjgp1nrU4WeHsukUBjbh7gYE7pm4F3c", "9jHrTCwpDANHLNQz5cem6XLUBM8KiTWKe766Br6KVCXM", "2ifjKjqtETDeHXKsrRxeKWUuwUtXxNS4HepT6eftj6Qz",
        "78hoB7emUo7zF5kdNf9TFxzpLRKCy8Jgft5cu69Byuax", "G8CcfRffqZWHSAQJXLDfwbAkGE95SddUqVXnTrL4kqjm"], "candidate": True},
]
SOL_MAX_TX = int(os.environ.get("SOL_MAX_TX", "40000"))    # 每个代币账户最多拉多少笔交易，超了标 partial


def rpc(chain, method, params, tries=4):
    url = f"https://{NET[chain]}.g.alchemy.com/v2/{KEY}"
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read())
            if "error" in d:
                return None, d["error"].get("message", str(d["error"]))
            return d["result"], None
        except Exception as e:  # noqa
            if i + 1 == tries:
                return None, str(e)
            time.sleep(2 * (i + 1))


def block_at(chain, ts):
    head, e = rpc(chain, "eth_blockNumber", [])
    lo, hi = 1, int(head, 16)
    while lo < hi:
        mid = (lo + hi) // 2
        b, e = rpc(chain, "eth_getBlockByNumber", [hex(mid), False])
        if int(b["timestamp"], 16) < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def logs(chain, token, b0, b1, topic1=None, topic2=None):
    pad = lambda a: None if a is None else ["0x" + "0" * 24 + x[2:].lower() for x in a]
    out, a, span, partial = [], b0, 500_000, False
    while a < b1:
        b = min(a + span - 1, b1 - 1)
        res, e = rpc(chain, "eth_getLogs", [{"address": token, "fromBlock": hex(a), "toBlock": hex(b), "topics": [TRANSFER, pad(topic1), pad(topic2)]}])
        if e:
            if span > 2000:
                span //= 4; continue
            ERR.append(f"{chain} getLogs {a}-{b}: {e[:120]}"); partial = True; a = b + 1; continue
        out += res; a = b + 1
        if len(res) < 2000 and span < 500_000:
            span *= 2
    return out, partial


def ts_of(chain, bn, cache={}):
    k = (chain, bn)
    if k not in cache:
        b, _ = rpc(chain, "eth_getBlockByNumber", [hex(bn), False])
        cache[k] = int(b["timestamp"], 16) if b else None
    return cache[k]


def evm(m):
    chain, token, dec = TOK[m["sym"]]
    b0, b1 = block_at(chain, int(T0.timestamp())), block_at(chain, int(T1.timestamp()))
    res = {"chain": chain, "blocks": [b0, b1]}
    if m.get("via_tx_to"):                             # 销毁：交易调用对象是官方合约、代币转去销毁地址
        ls, partial = logs(chain, token, b0, b1, topic2=m["to"])
        via, qty, n, last, last_tx, by, big = {a.lower() for a in m["via_tx_to"]}, 0, 0, None, None, {}, []
        for l in ls:
            v, f = int(l["data"], 16) / 10 ** dec, "0x" + l["topics"][1][-40:]
            by[f] = by.get(f, 0) + v
            big.append((v, l["transactionHash"]))
            tx, e = rpc(chain, "eth_getTransactionByHash", [l["transactionHash"]])
            if e or not tx:
                partial = True; continue
            if (tx.get("to") or "").lower() in via:
                qty += v; n += 1; bn = int(l["blockNumber"], 16)
                if not last or bn > last:
                    last, last_tx = bn, l["transactionHash"]
        res.update(qty=qty, n=n, partial=partial, last=last and dt.datetime.fromtimestamp(ts_of(chain, last), dt.timezone.utc).strftime("%Y-%m-%d"), last_tx=last_tx,
                   diag={"all_to_burn_total": sum(by.values()), "by_sender_top": sorted(by.items(), key=lambda kv: -kv[1])[:10], "largest": sorted(big, reverse=True)[:5]})
        return res
    if m.get("frm"):                                   # 销毁：官方地址 → 销毁地址
        ls, partial = logs(chain, token, b0, b1, topic1=m["frm"], topic2=m["to"])
        qty = sum(int(l["data"], 16) for l in ls) / 10 ** dec
        res["largest"] = sorted(((int(l["data"], 16) / 10 ** dec, l["transactionHash"], "0x" + l["topics"][2][-40:]) for l in ls), reverse=True)[:5]
        last = max((int(l["blockNumber"], 16) for l in ls), default=None)
        res.update(qty=qty, n=len(ls), partial=partial, last=last and dt.datetime.fromtimestamp(ts_of(chain, last), dt.timezone.utc).strftime("%Y-%m-%d"),
                   last_tx=last and [l["transactionHash"] for l in ls if int(l["blockNumber"], 16) == last][0])
        if m.get("diag_all_to_dead"):
            allb, p2 = logs(chain, token, b0, b1, topic2=m["to"])
            by = {}
            for l in allb:
                f = "0x" + l["topics"][1][-40:]
                by[f] = by.get(f, 0) + int(l["data"], 16) / 10 ** dec
            res["diag"] = {"all_to_burn_total": sum(by.values()), "by_sender_top": sorted(by.items(), key=lambda kv: -kv[1])[:10]}
        return res
    ls, partial = logs(chain, token, b0, b1, topic2=m["to"])   # 流入官方地址的全部记录
    by, qty, n, last = {}, 0, 0, None
    src = {s.lower() for s in m.get("src") or []}
    for l in ls:
        f, v = "0x" + l["topics"][1][-40:], int(l["data"], 16) / 10 ** dec
        by[f] = by.get(f, 0) + v
        if f in src:
            qty += v; n += 1; last = max(last or 0, int(l["blockNumber"], 16))
    outl, p3 = logs(chain, token, b0, b1, topic1=m["to"])
    oby = {}
    for l in outl:
        t = "0x" + l["topics"][2][-40:]
        oby[t] = oby.get(t, 0) + int(l["data"], 16) / 10 ** dec
    res.update(partial=partial or p3, diag={"inflow_total": sum(by.values()), "inflow_by_sender_top": sorted(by.items(), key=lambda kv: -kv[1])[:10],
                                            "outflow_total": sum(oby.values()), "outflow_by_receiver_top": sorted(oby.items(), key=lambda kv: -kv[1])[:10]})
    if not m.get("diag_only"):
        res.update(qty=qty, n=n, last=last and dt.datetime.fromtimestamp(ts_of(chain, last), dt.timezone.utc).strftime("%Y-%m-%d"))
    return res


def sol_batch(sigs, size=50):
    """Alchemy 支持 JSON-RPC 批量；一次 50 笔，失败的单笔再试一次。"""
    url, out = f"https://{NET['sol']}.g.alchemy.com/v2/{KEY}", []
    for i in range(0, len(sigs), size):
        chunk = sigs[i:i + size]
        body = json.dumps([{"jsonrpc": "2.0", "id": k, "method": "getTransaction", "params": [sg, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]} for k, sg in enumerate(chunk)]).encode()
        got = {}
        for t in range(4):
            try:
                req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    got = {x["id"]: x.get("result") for x in json.loads(r.read())}
                break
            except Exception:  # noqa
                time.sleep(3 * (t + 1))
        for k, sg in enumerate(chunk):
            tx = got.get(k)
            if tx is None:
                tx, _ = rpc("sol", "getTransaction", [sg, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
            out.append(tx)
    return out


def sol(m):
    mint, dec = TOK[m["sym"]][1], TOK[m["sym"]][2]
    t0, t1 = int(T0.timestamp()), int(T1.timestamp())
    tot_in, tot_burn, n_in, n_burn, last, partial, accts, scanned, seen_from = 0, 0, 0, 0, None, False, [], 0, None
    by_src = {}
    for owner in m["owner"]:
        ta, e = rpc("sol", "getTokenAccountsByOwner", [owner, {"mint": mint}, {"encoding": "jsonParsed"}])
        if e:
            ERR.append(f"{m['sym']} {owner[:6]} 代币账户: {e[:100]}"); partial = True; continue
        for acc in [x["pubkey"] for x in ta["value"]]:
            accts.append(acc)
            sigs, before = [], None
            while True:
                p = {"limit": 1000}
                if before:
                    p["before"] = before
                r, e = rpc("sol", "getSignaturesForAddress", [acc, p])
                if e or not r:
                    if e:
                        ERR.append(f"{m['sym']} sigs: {e[:100]}"); partial = True
                    break
                sigs += [s for s in r if s.get("blockTime") and t0 <= s["blockTime"] < t1 and not s.get("err")]
                before = r[-1]["signature"]
                if r[-1].get("blockTime", t1) < t0 or len(r) < 1000:
                    break
                if len(sigs) >= SOL_MAX_TX:
                    partial = True; break
            sigs = sigs[:SOL_MAX_TX]
            if sigs:
                d0 = dt.datetime.fromtimestamp(min(x["blockTime"] for x in sigs), dt.timezone.utc).strftime("%Y-%m-%d")
                seen_from = min(seen_from or d0, d0)
            txs = sol_batch([x["signature"] for x in sigs])
            for s, tx in zip(sigs, txs):
                scanned += 1
                if not tx:
                    partial = True; continue
                meta = tx["meta"]
                keys = [k["pubkey"] if isinstance(k, dict) else k for k in tx["transaction"]["message"]["accountKeys"]]
                bal = lambda arr: sum(float(b["uiTokenAmount"]["uiAmount"] or 0) for b in arr if b["mint"] == mint and keys[b["accountIndex"]] == acc)
                d = bal(meta.get("postTokenBalances") or []) - bal(meta.get("preTokenBalances") or [])
                ins = list(tx["transaction"]["message"]["instructions"]) + [i for g in meta.get("innerInstructions") or [] for i in g["instructions"]]
                burned = sum(float(i["parsed"]["info"].get("amount") or i["parsed"]["info"].get("tokenAmount", {}).get("amount") or 0) / 10 ** dec
                             for i in ins if isinstance(i.get("parsed"), dict) and i["parsed"].get("type") in ("burn", "burnChecked")
                             and i["parsed"]["info"].get("account") == acc)
                if burned:
                    tot_burn += burned; n_burn += 1
                if d > 0 and not m.get("burn_only"):
                    tot_in += d; n_in += 1
                    signer = keys[0]
                    by_src[signer] = by_src.get(signer, 0) + d
                if burned or (d > 0 and not m.get("burn_only")):
                    day = dt.datetime.fromtimestamp(s["blockTime"], dt.timezone.utc).strftime("%Y-%m-%d")
                    last = max(last or day, day)
    res = {"chain": "sol", "accounts": accts, "tx_scanned": scanned, "seen_from": seen_from, "partial": partial, "burn_qty": tot_burn, "burn_n": n_burn,
           "diag": {"inflow_by_fee_payer_top": sorted(by_src.items(), key=lambda kv: -kv[1])[:10]}}
    if m.get("burn_only"):
        res.update(qty=tot_burn, n=n_burn, last=last)
    else:
        res.update(qty=tot_in, n=n_in, last=last)
    return res


def hype():
    """HyperCore Assistance Fund：公开 info 接口。当前 HYPE 余额（上线以来累计，不是 12 个月数）+ 能取到的成交记录覆盖区间。"""
    def info(body):
        req = urllib.request.Request("https://api.hyperliquid.xyz/info", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    A = "0xfefefefefefefefefefefefefefefefefefefefe"
    out = {"sym": "HYPE", "kind": "burn", "label": "Assistance Fund 持有的 HYPE（官方认定为已销毁）", "chain": "hypercore"}
    try:
        bal = info({"type": "spotClearinghouseState", "user": A})
        h = [b for b in bal.get("balances", []) if b["coin"] == "HYPE"]
        out["balance_now"] = float(h[0]["total"]) if h else None
    except Exception as e:  # noqa
        ERR.append(f"HYPE 余额: {e}")
    try:
        fills, start, end = [], int(T0.timestamp() * 1000), int(T1.timestamp() * 1000)
        while start < end:
            f = info({"type": "userFillsByTime", "user": A, "startTime": start, "endTime": end, "aggregateByTime": True})
            if not f:
                break
            fills += f
            nxt = max(x["time"] for x in f) + 1
            if nxt <= start or len(f) < 2000:
                break
            start = nxt
            time.sleep(0.3)
        hb = [x for x in fills if x["side"] == "B"]
        days = sorted({dt.datetime.fromtimestamp(x["time"] / 1000, dt.timezone.utc).strftime("%Y-%m-%d") for x in hb})
        out.update(fills=len(fills), buy_qty_seen=sum(float(x["sz"]) for x in hb), seen_from=days[0] if days else None, last=days[-1] if days else None,
                   partial=bool(days) and days[0] > T0.strftime("%Y-%m-%d"))
        if not out["partial"]:
            out.update(qty=out["buy_qty_seen"], n=len(hb))
    except Exception as e:  # noqa
        ERR.append(f"HYPE 成交: {e}")
    return out


def main():
    if not KEY:
        sys.exit("缺 ALCHEMY_KEY")
    only = set(sys.argv[1:])
    rows = []
    for m in MEASURES:
        if only and m["sym"] not in only:
            continue
        t = time.time()
        try:
            r = sol(m) if TOK[m["sym"]][0] == "sol" else evm(m)
        except Exception as e:  # noqa
            ERR.append(f"{m['sym']}: {e}"); r = {"partial": True}
        r.update({k: m[k] for k in ("sym", "kind", "label") if k in m}, candidate=m.get("candidate", False), diag_only=m.get("diag_only", False))
        rows.append(r)
        print(f"{m['sym']:7s} {m['kind']:8s} qty={r.get('qty')} n={r.get('n')} last={r.get('last')} partial={r.get('partial')} {time.time()-t:.0f}s", flush=True)
    if not only or "HYPE" in only:
        rows.append(hype())
        print("HYPE", {k: rows[-1].get(k) for k in ("balance_now", "fills", "buy_qty_seen", "seen_from", "last", "partial")}, flush=True)
    out = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "window": [T0.strftime("%Y-%m-%d"), T1.strftime("%Y-%m-%d")],
           "rules": "tools/core_mech/buyback.py 文件头", "rows": rows, "errors": ERR}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False)[:20000])


if __name__ == "__main__":
    main()
