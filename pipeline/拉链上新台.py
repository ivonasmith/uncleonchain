#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发射台日更 · 链上自动发现新发射台 → data/onchain/<链>.json

不靠 DefiLlama、不靠 KOL 名单：每天扫前一个 UTC 完整日（UTC+0）链上全部「从 0 地址铸币」事件，
挑出「一次铸出整数供应量」的新币（发射台发的币几乎都是 10 亿 / 1 亿这种整数；LP 份额、稳定币增发不是），
再看发这个币的交易调用的是哪个合约 —— 那就是「发币工厂」（发射台的路由 / 工厂合约）。
按工厂统计每天：新币数、发币人数（查过交易的那部分）、样本币。和历史比，网站上标新出现、正在起量的工厂。

  · 交易 to 为空 = 个人直接部署合约发币，不算发射台，单独计数。
  · 通用基础设施（账户抽象入口、多重调用等）和已知发射台的名字在 config/launchpad_factories.json；漏掉的、认错的大叔在这里补。
  · 节点：Robinhood Chain、Arc 用公共节点，失败自动改用 Alchemy；BSC、Base 的公共节点不接受「不指定合约地址」的日志查询，
    只能用 Alchemy（GitHub Secret ALCHEMY_KEY，key 放在网址里）。
  · 省额度：新币先按「铸给谁」分组（日志里自带，不花调用），每组只抽几笔交易认工厂，每天每条链最多查 TX_CAP 笔交易。
    发币人数因此是「查过的交易里有几个不同发币人」，是下限。
  · 只要昨天的数；之前的每次往回补 1 天，最多补到 BACKFILL_TARGET 天前（太久的平台多半没活下来，没意义）。

用法：python3 拉链上新台.py [robinhood|bsc|base|arc ...]
"""
import json, os, sys, time, datetime as dt, urllib.request, urllib.error
from collections import defaultdict, Counter
from common import DATA, today_utc, shift

TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ZERO = "0x" + "0" * 64
ROUND = 10 ** 21          # 整数供应量：18 位小数下是 1,000 枚的整数倍
BACKFILL_TARGET = 14      # 往回最多补到几天前
BACKFILL_PER_RUN = 1      # 每次日更顺带补几天旧的
BASELINE_DAYS = 3         # 数据最早几天里就出现的工厂记「基线」（早就存在，不算新）
KEEP_DAYS = 120
SAMPLES = 3               # 每个工厂每天留几个样本币
PER_GROUP = 3             # 每个「铸给谁」分组抽几笔交易认工厂
TX_CAP = 4000             # 每条链每天最多查几笔交易
UA = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (launchpad-daily)"}
KEY = os.environ.get("ALCHEMY_KEY", "").strip()

CHAINS = {
    "robinhood": {"名称": "Robinhood Chain", "公共": "https://rpc.mainnet.chain.robinhood.com", "alchemy": "robinhood-mainnet",
                  "浏览器": "https://explorer.chain.robinhood.com", "跨度": 30000},
    # BSC / Base 一天铸币事件上百万条：每小时只扫前 10 分钟（全天 1/6），计数 ×6 估算并标「抽样」——发现新工厂够用，省额度省时间
    "bsc": {"名称": "BSC", "公共": None, "alchemy": "bnb-mainnet", "浏览器": "https://bscscan.com", "跨度": 2000, "抽样": 6},
    "base": {"名称": "Base", "公共": None, "alchemy": "base-mainnet", "浏览器": "https://basescan.org", "跨度": 2000, "抽样": 6},
    "arc": {"名称": "Arc", "公共": "https://rpc.mainnet.arc.io", "alchemy": "arc-mainnet", "浏览器": "https://explorer.arc.io", "跨度": 5000},
}
OUT_DIR = os.path.join(DATA, "onchain")
CALLS = Counter()         # 每个节点今天调用了多少次（看 Alchemy 额度用）
CHAIN_BUDGET = 20 * 60    # 每条链每次最多跑 20 分钟，超时就停，不拖垮日更
DEADLINE = [0.0]


class Timeout(RuntimeError):
    pass


class RpcError(RuntimeError):
    pass


def _post(url, payload, timeout=120, tries=4):
    body = json.dumps(payload).encode()
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=UA), timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (401, 403):
                break
        except Exception as e:
            last = str(e)[:120]
        time.sleep(2 * (i + 1))
    raise RuntimeError(last)


class Node:
    def __init__(self, url, label):
        self.url, self.label = url, label

    def call(self, method, params):
        if DEADLINE[0] and time.time() > DEADLINE[0]:
            raise Timeout("超过本链时间上限")
        CALLS[self.label] += 1
        j = _post(self.url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        if "error" in j:
            raise RpcError(str(j["error"].get("message") or j["error"]))
        return j["result"]

    def batch(self, calls, size=50):
        out = []
        for i in range(0, len(calls), size):
            part = calls[i:i + size]
            CALLS[self.label] += len(part)
            try:
                j = _post(self.url, [{"jsonrpc": "2.0", "id": k, "method": m, "params": p} for k, (m, p) in enumerate(part)])
                res = {x.get("id"): x.get("result") for x in j} if isinstance(j, list) else {}
            except Exception:
                res = {}
            out += [res.get(k) for k in range(len(part))]
        return out


def nodes_for(ch):
    ns = []
    if ch["公共"]:
        ns.append(Node(ch["公共"], "公共"))
    if KEY and ch["alchemy"]:
        ns.append(Node(f"https://{ch['alchemy']}.g.alchemy.com/v2/{KEY}", "Alchemy"))
    return ns


def first_block_at(n, ts, hi):
    """时间戳 ≥ ts 的第一个块（二分）。"""
    lo = 1
    while lo < hi:
        mid = (lo + hi) // 2
        if int(n.call("eth_getBlockByNumber", [hex(mid), False])["timestamp"], 16) >= ts:
            hi = mid
        else:
            lo = mid + 1
    return lo


def _logs(n, a, b):
    try:
        return n.call("eth_getLogs", [{"fromBlock": hex(a), "toBlock": hex(b), "topics": [TRANSFER, ZERO]}])
    except RpcError as e:
        m = str(e).lower()
        if b > a and any(k in m for k in ("exceed", "limit", "too many", "spans", "range", "10000", "response size")):
            mid = (a + b) // 2
            return _logs(n, a, mid) + _logs(n, mid + 1, b)
        raise


def scan_day(n, ch, d):
    t0 = int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp())
    head = int(n.call("eth_blockNumber", []), 16)
    b0 = first_block_at(n, t0, head)
    b1 = first_block_at(n, t0 + 86400, head) - 1
    k = ch.get("抽样") or 1
    logs = []
    if k > 1:                                    # 每小时只扫开头 1/k 的块
        per_h = (b1 - b0 + 1) / 24
        spans = [(int(b0 + h * per_h), int(b0 + h * per_h + per_h / k) - 1) for h in range(24)]
    else:
        spans = [(b0, b1)]
    for a0, a1 in spans:
        x = a0
        while x <= a1:
            y = min(a1, x + ch["跨度"] - 1)
            logs += _logs(n, x, y)
            x = y + 1
    # 每个币取它这一天的第一笔铸币交易；那笔交易里铸出的合计是整数供应量才算「新发的币」；记下铸得最多的接收方
    first_tx, amt, to_amt = {}, defaultdict(int), defaultdict(Counter)
    for l in logs:
        tok, h = l["address"].lower(), l["transactionHash"]
        first_tx.setdefault(tok, h)
        if first_tx[tok] != h or l.get("data") in (None, "0x", ""):
            continue
        try:
            v = int(l["data"], 16)
        except ValueError:
            continue
        amt[tok] += v
        if len(l.get("topics") or []) > 2:
            to_amt[tok]["0x" + l["topics"][2][-40:]] += v
    new = {t: h for t, h in first_tx.items() if amt[t] > 0 and amt[t] % ROUND == 0}
    # 按「铸给谁」分组；每组抽 PER_GROUP 笔交易认工厂；单币一组（每个币一个曲线合约那种）按剩余额度逐个查
    groups = defaultdict(list)
    for t in new:
        groups[(to_amt[t].most_common(1) or [("?", 0)])[0][0]].append(t)
    order = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    want, budget = [], TX_CAP
    for g, toks in order:
        k = min(len(toks), PER_GROUP)
        if budget < k:
            break
        want += toks[:k]
        budget -= k
    hs = sorted({new[t] for t in want})
    txs = dict(zip(hs, n.batch([("eth_getTransactionByHash", [h]) for h in hs])))
    fac = {}
    direct = unknown = 0
    for g, toks in order:
        seen = [txs.get(new[t]) for t in toks[:PER_GROUP] if new[t] in txs]
        seen = [s for s in seen if s]
        if not seen:
            unknown += len(toks)
            continue
        tos = Counter((s.get("to") or "").lower() for s in seen)
        to = tos.most_common(1)[0][0]
        if not to:
            direct += len(toks)
            continue
        f = fac.setdefault(to, {"币": 0, "人": set(), "样本": []})
        f["币"] += len(toks)
        f["人"].update((s.get("from") or "").lower() for s in seen if (s.get("to") or "").lower() == to)
        for t in toks:
            if len(f["样本"]) < SAMPLES:
                f["样本"].append(t)
    # 只发了 1 个币的合约（多是个人用的路由 / 一次性合约）只记个数，不落明细，控制文件大小；候选门槛是 7 天 ≥ 30 个币，不影响发现
    keep = {a: v for a, v in fac.items() if v["币"] >= 2}
    if k > 1:                                    # 抽样：数量按比例放大成全天估算；只发了 1 个币的不放大
        for v in keep.values():
            v["币"] *= k
        return {"块": [b0, b1], "抽样": k, "铸币事件": len(logs) * k, "新币": len(new) * k, "直接部署": direct * k, "未识别": unknown * k,
                "查交易": len(hs), "单币合约": len(fac) - len(keep),
                "工厂": {a: [v["币"], len(v["人"]), v["样本"]] for a, v in sorted(keep.items(), key=lambda kv: -kv[1]["币"])}}
    return {"块": [b0, b1], "铸币事件": len(logs), "新币": len(new), "直接部署": direct, "未识别": unknown,
            "查交易": len(hs), "单币合约": len(fac) - len(keep),
            "工厂": {a: [v["币"], len(v["人"]), v["样本"]] for a, v in sorted(keep.items(), key=lambda kv: -kv[1]["币"])}}


def run_chain(key, ch):
    path = os.path.join(OUT_DIR, f"{key}.json")
    db = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    db.update({"链": ch["名称"], "浏览器": ch["浏览器"]})
    days = db.setdefault("逐日", {})
    ns = nodes_for(ch)
    if not ns:
        db["状态"] = "待接入：缺 Alchemy key（GitHub Secret ALCHEMY_KEY）"
        json.dump(db, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        print(f"  {ch['名称']}：{db['状态']}")
        return
    end = shift(today_utc(), -1)
    todo = [end] if end not in days else []
    old, d = [], shift(end, -1)                    # 往回补：从最近的缺口开始，每次 BACKFILL_PER_RUN 天
    while d >= shift(end, -(BACKFILL_TARGET - 1)) and len(old) < BACKFILL_PER_RUN:
        if d not in days:
            old.append(d)
        d = shift(d, -1)
    err, used = None, None
    for d in todo + old:
        t = time.time()
        r = None
        for n in ns:                               # 公共节点优先，失败换 Alchemy
            try:
                r = scan_day(n, ch, d)
                used = n.label
                break
            except Exception as e:
                err = f"{d} {n.label}：{str(e)[:160]}"
                print(f"  {ch['名称']} {d} {n.label} 失败：{e}")
        if r is None:
            break
        r["节点"] = used
        days[d] = r
        err = None
        print(f"  {ch['名称']} {d}（{used}）：铸币事件 {r['铸币事件']:,}，新币 {r['新币']:,}，工厂 {len(r['工厂'])}，"
              f"直接部署 {r['直接部署']}，未识别 {r['未识别']}，查交易 {r['查交易']}（{time.time() - t:.0f} 秒）")
    for d in [d for d in days if d < shift(end, -KEEP_DAYS)]:
        del days[d]
    db["逐日"] = dict(sorted(days.items()))
    # 首次出现：所有已扫日子里最早出现的那天；落在数据最早 BASELINE_DAYS 天内的记「基线」
    ds = sorted(days)
    first = {}
    if ds:
        cut = shift(ds[0], BASELINE_DAYS - 1)
        for d in ds:
            for a in days[d]["工厂"]:
                first.setdefault(a, "基线" if d <= cut else d)
    db["首次出现"] = first
    db["状态"] = "ok" if not err else f"失败：{err}"
    db["更新UTC"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    db["调用"] = dict(CALLS)
    json.dump(db, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    only = [a for a in sys.argv[1:] if a in CHAINS]
    for key, ch in CHAINS.items():
        if only and key not in only:
            continue
        CALLS.clear()
        DEADLINE[0] = time.time() + CHAIN_BUDGET
        try:
            run_chain(key, ch)
        except Exception as e:           # 一条链挂了不影响别的链，也不拦日更
            print(f"  {ch['名称']} 失败：{e}")


if __name__ == "__main__":
    main()
