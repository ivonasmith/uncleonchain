#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读 PONS 销毁（Robinhood Chain，Chain ID 4663）

口径（2026-09-26 起，统一成一种方法）：
  逐日销毁 = 销毁地址 dEaD 在「次日 00:00 UTC 前最后一个区块」的 balanceOf
            − 前一日同一时点的 balanceOf
  也就是按 UTC 日界切的链上状态差额，和 DefiLlama 的 UTC 日完全对齐。
  旧流程混用了「11:00 UTC 两次读数的差」和「事件扫描」两种口径，同一天两者对不上
  （2026-09-17 补跑时发现），这里改成日界余额，一天一个确定值，不再需要手动补 销毁逐日.json。

  归档节点不可用时自动退回事件口径：Transfer→dEaD 事件在同样的日界区块区间内加总，结果等价。
  ⚠️ 2026-09-26 实测公共节点连前一天的历史状态都不给（"historical state ... is not available"），
     所以日常实际走的是事件口径。首跑重算结果里 09-16 日末累计 312,793,919 与 Polar 当时用历史块单独
     读到的 09-16 24:00 UTC 余额完全一致，两种方法互相印证。

⛔ 销毁是转到 dEaD，不是调用 burn()。totalSupply() 恒为 10 亿不会减少 → 市值一律 burn-adjusted。

用法：
  python3 读销毁.py                          # 日常：从 销毁累计.json 的下一天补到昨天
  python3 读销毁.py --rebuild-from 2026-08-23 # 重算一段历史（结果与旧值不一致的写进 销毁修正记录.json）
产出：销毁累计.json、销毁逐日.json、销毁台账.json（追加一条实时读数）、销毁修正记录.json
"""
import sys, time, datetime as dt
from common import post_json, load, save, today_utc, shift, day_start_ts

RPC = "https://rpc.mainnet.chain.robinhood.com"      # 不带 User-Agent 会 403
PONS = "0x39dBED3a2bd333467115dE45665cC57F813C4571"
DEAD = "0x000000000000000000000000000000000000dEaD"
SEL_BALANCEOF, SEL_TOTALSUPPLY, SEL_DECIMALS = "0x70a08231", "0x18160ddd", "0x313ce567"
TOPIC_TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TOPIC_DEAD = "0x" + "0" * 24 + DEAD[2:].lower()
SHARD = 500_000
_ts = {}


def rpc(method, params):
    d = post_json(RPC, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in d:
        raise RuntimeError(d["error"])
    return d["result"]


def ts_of(n):
    if n not in _ts:
        _ts[n] = int(rpc("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)
    return _ts[n]


def last_block_before(T, head):
    """最大的块号 n，使 ts(n) < T（即 T 这个 UTC 日界之前的最后一个块）"""
    if ts_of(head) < T:
        return head
    known = sorted(_ts.items())
    lo, hi = 0, head
    for n, t in known:                        # 用已知点收窄区间
        if t < T and n > lo:
            lo = n
        if t >= T and n < hi:
            hi = n
    if lo == 0:                               # 没有下界：按约 0.101 秒/块往回估
        g = max(1, head - int((ts_of(head) - T) / 0.101) - 50_000)
        while ts_of(g) >= T:
            g = max(1, g - 400_000)
        lo = g
    while hi - lo > 1:
        tl, th = ts_of(lo), ts_of(hi)
        if hi - lo > 64 and th > tl:          # 先插值，后二分
            mid = lo + int((T - tl) / (th - tl) * (hi - lo))
            mid = min(max(mid, lo + 1), hi - 1)
        else:
            mid = (lo + hi) // 2
        if ts_of(mid) < T:
            lo = mid
        else:
            hi = mid
    return lo


def call(sel, arg=None, block="latest"):
    data = sel + (arg.lower().replace("0x", "").rjust(64, "0") if arg else "")
    tag = hex(block) if isinstance(block, int) else block
    return int(rpc("eth_call", [{"to": PONS, "data": data}, tag]), 16)


def events_sum(b_from, b_to, dec):
    """(b_from, b_to] 区间内 Transfer→dEaD 的总量"""
    tot, lo = 0, b_from + 1
    while lo <= b_to:
        hi = min(lo + SHARD - 1, b_to)
        for g in rpc("eth_getLogs", [{"address": PONS, "topics": [TOPIC_TRANSFER, None, TOPIC_DEAD],
                                     "fromBlock": hex(lo), "toBlock": hex(hi)}]):
            tot += int(g["data"], 16)
        time.sleep(0.2)
        lo = hi + 1
    return tot / 10 ** dec


def main():
    rebuild = None
    if "--rebuild-from" in sys.argv:
        rebuild = sys.argv[sys.argv.index("--rebuild-from") + 1]

    dec = call(SEL_DECIMALS)
    head = int(rpc("eth_blockNumber", []), 16)
    burned_now = call(SEL_BALANCEOF, DEAD) / 10 ** dec
    supply = call(SEL_TOTALSUPPLY) / 10 ** dec

    # ---------- 1. 实时读数进台账（审计用） ----------
    ledger = load("销毁台账.json", [])
    rec = {
        "读取时间UTC": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "区块": head, "decimals": dec,
        "销毁地址持仓": burned_now, "totalSupply": supply,
        "burn_adjusted流通": supply - burned_now,
        "totalSupply高估比例": supply / (supply - burned_now) - 1,
    }
    if ledger:
        rec["较上次新增销毁"] = burned_now - ledger[-1]["销毁地址持仓"]
        rec["上次读取"] = ledger[-1]["读取时间UTC"]
    ledger.append(rec)
    save("销毁台账.json", ledger, indent=1)

    # ---------- 2. 按 UTC 日界补齐逐日销毁 ----------
    cum = load("销毁累计.json", {})          # {日期: {"累计": 日末余额, "区块": 日末最后一个块}}
    daily = load("销毁逐日.json", {})
    fixes = load("销毁修正记录.json", [])
    yesterday = shift(today_utc(), -1)
    if rebuild:
        start = rebuild
    elif cum:
        start = shift(max(cum), 1)
    else:
        start = yesterday
    days = []
    d = start
    while d <= yesterday:
        days.append(d)
        d = shift(d, 1)
    if not days:
        print("销毁逐日已是最新，最后一天", max(cum) if cum else "-")
        return

    need = [shift(start, -1)] + days
    blk = {}
    for d in need:
        blk[d] = last_block_before(day_start_ts(shift(d, 1)), head)
    mode = "日界余额"
    bal = {}
    try:
        for d in need:
            bal[d] = call(SEL_BALANCEOF, DEAD, blk[d]) / 10 ** dec
    except Exception as e:                        # 节点不给历史状态 → 事件口径
        print("  历史 balanceOf 不可用，改用事件口径：", str(e)[:120])
        mode = "事件"
        after = events_sum(blk[yesterday], head, dec)       # 昨天日末之后到现在
        bal[yesterday] = burned_now - after
        for i in range(len(need) - 1, 0, -1):
            d, p = need[i], need[i - 1]
            bal[p] = bal[d] - events_sum(blk[p], blk[d], dec)

    for i, d in enumerate(days):
        p = need[i]
        burn = bal[d] - bal[p]
        old = daily.get(d)
        if old is not None and abs(old - burn) > max(1.0, 0.005 * abs(burn)):
            fixes.append({"日期": d, "旧值": old, "新值": burn, "差": burn - old,
                          "口径": mode, "修正时间UTC": rec["读取时间UTC"]})
        daily[d] = burn
        cum[d] = {"累计": bal[d], "区块": blk[d], "口径": mode}
        print(f"  {d}  当日销毁 {burn:>14,.0f}  日末累计 {bal[d]:>16,.0f}  区块 {blk[d]}")

    save("销毁累计.json", dict(sorted(cum.items())), indent=1)
    save("销毁逐日.json", dict(sorted(daily.items())), indent=1)
    save("销毁修正记录.json", fixes, indent=1)
    print(f"口径 {mode}；补齐 {days[0]} → {days[-1]}；实时持仓 {burned_now:,.0f}（占 {burned_now/supply:.1%}）")
    n_fix = sum(1 for f in fixes if f["修正时间UTC"] == rec["读取时间UTC"])
    if n_fix:
        print(f"  ⚠️ 本次有 {n_fix} 天与旧值不一致，已写入 销毁修正记录.json")


if __name__ == "__main__":
    main()
