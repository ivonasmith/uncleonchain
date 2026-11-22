#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发射台「量的质量」· 交易者 / 发币人（试点：BSC 上的 Four.meme、Flap）→ data/onchain/平台交易者.json

接口约定《发射台板块 → Alpha 雷达》字段优先级 4。2026-11-16 起试点两家，读平台合约自己的买卖 / 创建事件，按 UTC 完整日：
  交易者  当天内盘（曲线）买卖的不同钱包数。事件里记的买方 / 卖方是合约（交易机器人、路由）的，逐笔回查交易发起钱包（tx.from）；
          EIP-7702 委托的钱包（代码以 0xef0100 开头）算普通钱包。毕业后到 DEX 上的成交不算 —— 下限
  发币人  当天创建事件里不同的发币地址（同样把合约换成交易发起钱包）
  前10地址笔数占比  笔数最多的 10 个钱包占全部买卖笔数的比例。成交额口径要统一计价币（每个币报价币不同），还没做，前10地址成交占比 = null
  7d      最近 7 天去重（逐日地址集合在 pipeline/cache/traders/，走 actions/cache）；缓存里不满 7 天就是 null，「覆盖天数」写明
节点：BSC 公共节点（publicnode 优先，env BSC_RPC 可改，逗号分隔），一天 ~19 万块，5000 块一段。
时间预算 TRADERS_TIME 秒（默认 900；Flap 一天约 10 万笔要回查发起钱包，单天 5～8 分钟）：每天要么扫完整天要么不记，没扫完的下次接着扫；最多往回补 2 天（公共节点只留约 2 天日志，更早的块返回空，任何一段为空整天不记）。
逐日结果只追加（自录数据，不可再生，见 docs/备份方案.md）。
"""
import os, sys, json, gzip, time, datetime as dt, urllib.request
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA

OUT = os.path.join(DATA, "onchain", "平台交易者.json")
CACHE = os.environ.get("TRADERS_CACHE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "traders")
RPCS = [u for u in (os.environ.get("BSC_RPC") or "https://bsc-rpc.publicnode.com,https://bsc-dataseed.bnbchain.org").split(",") if u]
BUDGET = int(os.environ.get("TRADERS_TIME", "900"))
CHUNK = 5000
BACK = int(os.environ.get("TRADERS_BACK", "2"))   # 公共节点只留约 2 天日志，往回最多补 2 天

# slug = DefiLlama slug（和 平台质量.json 同一套）。字段位置 = topics[1:] + data 的 32 字节字（两家这几个事件都没有 indexed 参数）
PLATFORMS = {
    "four.meme": {"name": "Four.meme", "address": "0x5c952063c7fc8610FFDB798152D69F0B9550762b",
                  "topics": {"create": "0x396d5e902b675b032348d3d2e9517ee8f0c4a926603fbc075d3d282ff00cad20",
                             "buy": "0x7db52723a3b2cdd6164364b3b766e65e540d7be48ffa89582956d8eaebe62942",
                             "sell": "0x0a5575b3648bae2210cee56bf33254cc1ddfbc7bf637c0af2ac18b14fb1bae19"},
                  "creator": 0, "trader": 1,
                  "scope": "TokenManager2 0x5c95…762b 的内盘买卖（TokenPurchase / TokenSale）和 TokenCreate；字段位置同 tools/agent-id-cloud agentpads"},
    "flap-sh": {"name": "Flap", "address": "0xe2cE6ab80874Fa9Fa2aAE65D277Dd6B8e65C9De0",
                "topics": {"create": "0x504e7f360b2e5fe33cbaaae4c593bc55305328341bf79009e43e0e3b7f699603",
                           "buy": "0xa800a2038683844fac66747f771bfdfae862eb28b16bcfa387afa9fbacce8ff7",
                           "sell": "0x03a4693e592f5e75dc7c136acb39b146d2b4966c0e509c34f362dee02b3b861a"},
                "creator": 1, "trader": 2,
                "scope": "BSC Portal 0xe2cE…9De0 的内盘买卖和 TokenCreated；Flap 另一个 BSC 工厂和 Robinhood 链没扫"},
}


def load(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


class RPC:
    def __init__(self):
        self.i = 0

    def _post(self, body):
        last = None
        for k in range(len(RPCS) * 3):
            u = RPCS[(self.i + k // 3) % len(RPCS)]
            try:
                r = urllib.request.Request(u, json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "uncleonchain-launchpad"})
                return json.load(urllib.request.urlopen(r, timeout=90))
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(1 + k % 3)
        raise RuntimeError(f"BSC 节点都失败：{last}")

    def call(self, m, p):
        j = self._post({"jsonrpc": "2.0", "id": 1, "method": m, "params": p})
        if "error" in j:
            raise RuntimeError(j["error"])
        return j["result"]

    deadline = None   # 超过就抛错，这天不记（main 设）

    def batch(self, calls, size=100):
        out = []
        t0 = time.time()
        for i in range(0, len(calls), size):
            if self.deadline and time.time() > self.deadline:
                raise RuntimeError(f"超时间预算（批量 {i}/{len(calls)}）")
            if i and i % 20000 == 0:
                print(f"    批量 {calls[0][0]} {i}/{len(calls)}（{time.time() - t0:.0f} 秒）", flush=True)
            part = calls[i:i + size]
            for t in range(4):
                j = self._post([{"jsonrpc": "2.0", "id": n, "method": m, "params": p} for n, (m, p) in enumerate(part)])
                if isinstance(j, list) and len(j) == len(part) and not any("error" in x for x in j):
                    break
                time.sleep(2 + t)
            else:
                raise RuntimeError(f"批量请求失败：{(j if not isinstance(j, list) else [x for x in j if 'error' in x][:1])}")
            out += [x["result"] for x in sorted(j, key=lambda x: x["id"])]
        return out


def block_at(rpc, t, head):
    """时间戳 ≥ t 的第一个块（二分）。"""
    ts = lambda b: int(rpc.call("eth_getBlockByNumber", [hex(b), False])["timestamp"], 16)
    lo, hi = max(1, head - 3_000_000), head
    while lo < hi:
        m = (lo + hi) // 2
        if ts(m) < t:
            lo = m + 1
        else:
            hi = m
    return lo


def words(l):
    return [t[2:] for t in l["topics"][1:]] + [l["data"][2 + 64 * i: 66 + 64 * i] for i in range((len(l["data"]) - 2) // 64)]


def addr(w):
    return "0x" + w[-40:].lower()


def scan_day(rpc, cfg, a, b, kinds):
    T = cfg["topics"]
    inv = {v: k for k, v in T.items()}
    logs, x = [], a
    while x <= b:
        y = min(b, x + CHUNK - 1)
        part = rpc.call("eth_getLogs", [{"address": cfg["address"], "topics": [list(T.values())], "fromBlock": hex(x), "toBlock": hex(y)}])
        # 公共节点只留约 2 天日志，更早的块不报错、直接返回空：两家每 5000 块（约 37 分钟）都有几百上千笔，一段为空就当节点没数据，整天不记
        if not part:
            raise RuntimeError(f"块 {x}–{y} 没返回日志（超出节点保留范围？）")
        logs += part
        x = y + 1
    trades, creates = [], []
    for l in logs:
        k, w = inv.get(l["topics"][0]), words(l)
        if k in ("buy", "sell"):
            trades.append((addr(w[cfg["trader"]]), l["transactionHash"]))
        elif k == "create":
            creates.append((addr(w[cfg["creator"]]), l["transactionHash"]))
    # 事件里的地址是不是合约：没查过的批量 getCode（7702 委托钱包算钱包）
    need = sorted({a for a, _ in trades + creates} - set(kinds))
    for a_, code in zip(need, rpc.batch([("eth_getCode", [a_, "latest"]) for a_ in need], 50)):
        kinds[a_] = "c" if len(code) > 2 and not code.startswith("0xef0100") else "w"
    hs = sorted({h for a_, h in trades + creates if kinds[a_] == "c"})
    frm = {}
    for h, tx in zip(hs, rpc.batch([("eth_getTransactionByHash", [h]) for h in hs])):
        if tx:
            frm[h] = tx["from"].lower()
    real = lambda a_, h: a_ if kinds[a_] == "w" else frm.get(h)
    tw = [real(a_, h) for a_, h in trades]
    cw = [real(a_, h) for a_, h in creates]
    cnt = Counter(t for t in tw if t)
    return {"trades": len(trades), "via_contract": sum(1 for a_, _ in trades if kinds[a_] == "c"),
            "unresolved": sum(1 for t in tw if not t), "creates": len(creates),
            "traders": sorted(cnt), "creators": sorted({c for c in cw if c}),
            "top10": sum(n for _, n in cnt.most_common(10)), "logs": len(logs)}


def cache_path(slug, d):
    return os.path.join(CACHE, slug, f"{d}.json.gz")


def main():
    t0 = time.time()
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    out = load(OUT, {}) or {}
    plats = out.setdefault("平台", {})
    kinds = {}
    rpc = RPC()
    try:
        head = int(rpc.call("eth_blockNumber", []), 16)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ BSC 节点连不上，交易者这次不扫：{e}")
        return
    days = [(today - dt.timedelta(days=i)).isoformat() for i in range(BACK, 0, -1)]
    bounds = {}
    for slug, cfg in PLATFORMS.items():
        p = plats.setdefault(slug, {"逐日": {}})
        p["名称"], p["范围"] = cfg["name"], cfg["scope"]
        for d in days:
            if d in p["逐日"]:
                continue
            if time.time() - t0 > BUDGET:
                print(f"  {slug} {d}：超时间预算，下次接着扫")
                break
            if d not in bounds:
                t = int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp())
                bounds[d] = (block_at(rpc, t, head), block_at(rpc, t + 86400, head) - 1)
            a, b = bounds[d]
            s = time.time()
            rpc.deadline = t0 + BUDGET + 120   # 已开扫的一天多给 2 分钟收尾，再超就整天不记
            try:
                r = scan_day(rpc, cfg, a, b, kinds)
            except Exception as e:  # noqa: BLE001
                print(f"  ⚠️ {slug} {d} 扫描失败，这天不记：{e}")
                continue
            os.makedirs(os.path.dirname(cache_path(slug, d)), exist_ok=True)
            with gzip.open(cache_path(slug, d), "wt", encoding="utf-8") as f:
                json.dump({"traders": r["traders"], "creators": r["creators"]}, f)
            p["逐日"][d] = {"块": [a, b], "买卖笔数": r["trades"], "合约下单笔数": r["via_contract"], "未解析笔数": r["unresolved"],
                          "交易者": len(r["traders"]), "发币": r["creates"], "发币人": len(r["creators"]),
                          "前10地址笔数占比": round(r["top10"] / r["trades"], 4) if r["trades"] else None}
            print(f"  {slug} {d}：{r['trades']} 笔 · 交易者 {len(r['traders'])} · 发币 {r['creates']} / 发币人 {len(r['creators'])}"
                  f" · 合约下单 {r['via_contract']}（{time.time() - s:.0f} 秒）")
        # 汇总：1d = 最近一个扫完的日子；7d = 最近 7 个扫过的日子里缓存还在的去重
        ds = sorted(p["逐日"])
        if not ds:
            continue
        last = ds[-1]
        win = [d for d in ds if d > (dt.date.fromisoformat(last) - dt.timedelta(days=7)).isoformat()]
        tr, cr, cov = set(), set(), 0
        for d in win:
            try:
                with gzip.open(cache_path(slug, d), "rt", encoding="utf-8") as f:
                    z = json.load(f)
                tr |= set(z["traders"])
                cr |= set(z["creators"])
                cov += 1
            except Exception:
                pass
        p["汇总"] = {"数据日": last, "交易者1d": p["逐日"][last]["交易者"], "发币人1d": p["逐日"][last]["发币人"],
                   "前10地址笔数占比1d": p["逐日"][last]["前10地址笔数占比"],
                   "交易者7d": len(tr) if cov >= 7 else None, "发币人7d": len(cr) if cov >= 7 else None, "覆盖天数": cov}   # 攒满 7 天才出 7d，不拿几天冒充
    out["说明"] = ("发射台「量的质量」交易者 / 发币人试点（2026-11-16）：读平台合约的买卖 / 创建事件，按 UTC 完整日；"
                 "事件地址是合约的换成交易发起钱包；只算内盘（曲线）成交，毕业后 DEX 成交不算，下限。逐日只追加。")
    out["更新UTC"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    done = ", ".join(f"{k} 到 {(v.get('汇总') or {}).get('数据日')}" for k, v in plats.items())
    print(f"平台交易者：{done}（{time.time() - t0:.0f} 秒）")


if __name__ == "__main__":
    main()
