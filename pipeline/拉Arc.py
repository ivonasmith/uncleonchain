#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发射台日更 · Arc 链整链观察（对标 Robinhood Chain）→ Arc数据.json

Arc（Circle，Chain ID 5042，gas = USDC）2026-09-16 主网上线。DefiLlama 上线当天 fees/dex 指标为空，
之后已索引进来（2026-09-26 核实：fees 与 dexs 两个 overview 都有协议列表，含 Tolly、Argus World 等发射台）。

每天拉三样，两条链各一份：
  全链手续费   overview/fees/{chain}      链上全部协议的 fees 加总（应用层，不是 gas）
  全链 DEX 成交 overview/dexs/{chain}
  TVL          v2/historicalChainTvl/{chain}
并按 DefiLlama 的 category == "Launchpad" 拆出发射台合计与逐家逐日。

⚠️ Arc 上不少发射台的 swap 走 Uniswap V3/V4 底层池，成交额记在 Uniswap 名下而不是发射台名下，
   所以「发射台 DEX 成交」系统性偏低；发射台看 fees 更可靠。Dune 口径与 DefiLlama 口径对不上是已知问题。
"""
import datetime as dt, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from common import get, day, today_utc, save

CHAINS = ["Arc", "Robinhood Chain"]


def overview(kind, chain):
    c = urllib.parse.quote(chain)
    try:
        return get(f"https://api.llama.fi/overview/{kind}/{c}"
                   "?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=false", tries=3)
    except Exception as e:
        print(f"  {chain} {kind} 失败：{e}")
        return None


def chart(pairs, today):
    out = {}
    for row in pairs or []:
        t, v = row[0], row[1]
        k = day(t)
        if k < today:
            out[k] = out.get(k, 0) + (v or 0)
    return out


def split(ov, today):
    """返回 (全链逐日, 协议元数据{name: {...}}, 协议逐日{name: {day: v}})"""
    if not ov:
        return {}, {}, {}
    meta = {}
    for p in ov.get("protocols") or []:
        m = {"名称": p.get("displayName") or p.get("name"), "slug": p.get("slug"),
             "类目": p.get("category"), "24h": p.get("total24h"), "7d": p.get("total7d"),
             "30d": p.get("total30d")}
        for key in {p.get("name"), p.get("displayName")} - {None}:
            meta[key] = m
    per = {}
    for row in ov.get("totalDataChartBreakdown") or []:
        t, brk = row[0], row[1]
        k = day(t)
        if k >= today or not isinstance(brk, dict):
            continue
        for name, v in brk.items():
            if isinstance(v, dict):                 # 个别版本是 {链: {协议: 值}}
                for n2, v2 in v.items():
                    per.setdefault(n2, {})[k] = per.setdefault(n2, {}).get(k, 0) + (v2 or 0)
            else:
                per.setdefault(name, {})[k] = per.setdefault(name, {}).get(k, 0) + (v or 0)
    return chart(ov.get("totalDataChart"), today), meta, per


def norm(x):
    return (x or "").lower().replace(" ", "").replace("-", "")


def backfill(ov, per, tot, kind, chain, today, min7d=500):
    """⚠️ DefiLlama 链级 overview 的逐日图（totalDataChart / breakdown）会漏掉部分协议 ——
    2026-09-26 实测 Arc 漏了 Argus World（Arc 最大的发射台）、Wonk Fun、Foci，Robinhood Chain 漏了 Pons V1、NOXA 等。
    这些协议在 protocols 列表里有 total24h，逐日数据要逐个去 summary 接口补回来，否则整链与发射台合计都会严重偏低。"""
    if not ov:
        return []
    seen = {norm(n) for n in per}
    miss = [p for p in ov.get("protocols") or []
            if norm(p.get("name")) not in seen and norm(p.get("displayName")) not in seen
            and (p.get("total7d") or 0) >= min7d and p.get("slug")
            and p.get("category") not in ("Chain", "Rollup", "Foundation")   # 链自身的 gas、基金会分成不算应用层手续费
            # 成交额只补真正撮合的协议：交易终端 / 聚合器 / 钱包的成交是转发给 DEX 的，补进来就重复计算
            and (kind == "fees" or p.get("category") in ("Dexs", "Launchpad"))]
    dtype = "dailyFees" if kind == "fees" else "dailyVolume"

    def one(p):
        try:
            d = get(f"https://api.llama.fi/summary/{kind}/{p['slug']}?dataType={dtype}", tries=3)
        except Exception:
            return p, {}
        out = {}
        brk = d.get("totalDataChartBreakdown") or []
        for row in brk:
            k = day(row[0])
            if k >= today:
                continue
            for ch, v in (row[1] or {}).items():
                if norm(ch) == norm(chain):
                    out[k] = out.get(k, 0) + (sum(v.values()) if isinstance(v, dict) else (v or 0))
        if not brk and (p.get("chains") or []) == [chain]:      # 单链协议没有 breakdown 时用总图
            for t, v in d.get("totalDataChart") or []:
                if day(t) < today:
                    out[day(t)] = out.get(day(t), 0) + (v or 0)
        return p, out
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(one, miss))
    added = []
    for p, series in res:
        if not series:
            continue
        name = p.get("displayName") or p.get("name")
        per[name] = series
        for k, v in series.items():
            tot[k] = tot.get(k, 0) + v
        added.append(name)
    return added


def main():
    today = today_utc()
    out = {"生成时间UTC": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "口径": "DefiLlama overview/fees、overview/dexs、historicalChainTvl；UTC 日，剔除当天不完整点",
           "链": {}}
    for chain in CHAINS:
        f_ov, v_ov = overview("fees", chain), overview("dexs", chain)
        f_tot, f_meta, f_per = split(f_ov, today)
        v_tot, v_meta, v_per = split(v_ov, today)
        f_add = backfill(f_ov, f_per, f_tot, "fees", chain, today)
        v_add = backfill(v_ov, v_per, v_tot, "dexs", chain, today)
        if f_add or v_add:
            print(f"  {chain}：overview 逐日图漏掉的协议已逐个补回 —— fees {len(f_add)} 家 {f_add[:6]}，dex {len(v_add)} 家 {v_add[:6]}")
        try:
            tvl_raw = get(f"https://api.llama.fi/v2/historicalChainTvl/{urllib.parse.quote(chain)}", tries=3)
            tvl = {day(r["date"]): r["tvl"] for r in tvl_raw if day(r["date"]) < today}
        except Exception as e:
            print(f"  {chain} TVL 失败：{e}")
            tvl = {}
        lp_names = sorted({n for n, m in {**v_meta, **f_meta}.items() if m.get("类目") == "Launchpad"})
        lp_fees, lp_dex = {}, {}
        for n in lp_names:
            for k, v in f_per.get(n, {}).items():
                lp_fees[k] = lp_fees.get(k, 0) + v
            for k, v in v_per.get(n, {}).items():
                lp_dex[k] = lp_dex.get(k, 0) + v
        launchpads = {}
        for n in lp_names:
            m = f_meta.get(n) or v_meta.get(n) or {}
            key = m.get("名称") or n
            e = launchpads.setdefault(key, {"slug": m.get("slug"), "fees": {}, "dex": {}})
            for k, v in f_per.get(n, {}).items():
                e["fees"][k] = e["fees"].get(k, 0) + v
            for k, v in v_per.get(n, {}).items():
                e["dex"][k] = e["dex"].get(k, 0) + v
        out["链"][chain] = {
            "全链手续费": f_tot, "全链DEX成交": v_tot, "TVL": tvl,
            "发射台手续费": lp_fees, "发射台DEX成交": lp_dex,
            "发射台": launchpads,
            "发射台数量": len(launchpads),
            "补回协议": {"fees": f_add, "dex": v_add},
        }
        last = max(f_tot) if f_tot else "-"
        print(f"  {chain:16s} 手续费天数 {len(f_tot):3d}  DEX 天数 {len(v_tot):3d}  TVL 天数 {len(tvl):3d}"
              f"  发射台 {len(launchpads)} 家  最后一天 {last}")
    save("Arc数据.json", out)
    print("写入 Arc数据.json")


if __name__ == "__main__":
    main()
