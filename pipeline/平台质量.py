#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发射台日更 · 平台量的质量 → data/onchain/平台质量.json（+ 平台质量_history.json）

接口约定（2026-11-15，发射台板块 → Alpha 雷达）：Alpha 机会卡要回答「量从哪来、量是不是真的、激励结束后还剩多少」，
发射台类平台的这些数据由发射台板块补，Alpha 只读。按 DefiLlama slug（= 发射台矩阵.json 协议[].slug）出：

  发币    工厂合约当天新铸整数供应量的币（拉链上新台.py），1d = 最近一个扫完的 UTC 日，7d = 最近 7 个扫过的日子合计
  发币人  查过交易的不同发币地址（每天单独数，取 7 天里最多的一天）—— 下限
  存活    某天发的币，7～8 天后用 GeckoTerminal 查：近 24 小时还有成交的几个、市值（没有就用 FDV）过 10 万美元的几个
  交易者  要扫每笔交易事件，还没接 —— null（页面显示「待接入」）
  事件    人工登记 config/launchpad_events.json，必须带日期和官方出处

规矩：拿不到写 null，不估；抽样扫描的链（每小时只扫 1/k 的块）发币数是 ×k 放大的，字段里标「估算」。
只追加历史：存活批次查过一次就记进 history，不再改。
"""
import os, json, time, datetime as dt, urllib.request, urllib.error
from collections import defaultdict
from common import DATA, today_utc, shift

OC = os.path.join(DATA, "onchain")
OUT = os.path.join(OC, "平台质量.json")
HIST = os.path.join(OC, "平台质量_history.json")
EVENTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "launchpad_events.json")
GT = "https://api.geckoterminal.com/api/v2"
GT_NET = {"bsc": "bsc", "base": "base", "ethereum": "eth", "arbitrum": "arbitrum", "optimism": "optimism", "polygon": "polygon_pos",
          "robinhood": "robinhood", "arc": "arc", "xlayer": "x-layer", "mantle": "mantle", "zksync": "zksync", "elysium": "elysium",
          "monad": "monad", "hyperevm": "hyperevm", "ink": "ink", "abstract": "abstract", "berachain": "berachain", "sonic": "sonic",
          "unichain": "unichain", "megaeth": "megaeth", "plasma": "plasma", "stable": "stable"}
SURV_DAYS = 7          # 发出后几天查
SURV_MAX = 20          # 每个平台每批查几个币（GeckoTerminal 逐个币查池子：批量接口不带曲线阶段的池子）
MCAP_LINE = 100_000
SURV_TIME = int(os.environ.get("SURV_TIME") or 8 * 60)    # 存活查询每次最多跑 8 分钟（日更这一步限 15 分钟），没查完的明天接着查
UA = {"User-Agent": "Mozilla/5.0 (launchpad-daily)", "Accept": "application/json"}


def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


_last = [0.0]
_gap = [2.2]            # 两次请求间隔；遇到 429 自动放慢（最多 8 秒一次）


class Late(RuntimeError):
    pass


def gt_pools(net, addr, end_at):
    """GeckoTerminal 一个币的全部池子（含发射台曲线池）→ [attributes]；没收录返回 []。失败抛异常。"""
    url = f"{GT}/networks/{net}/tokens/{addr}/pools"
    for i in range(4):
        if time.time() > end_at:
            raise Late("到时间了")
        wait = _gap[0] - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            j = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))
            return [x["attributes"] for x in j.get("data") or []]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            if e.code == 429 and i < 3:
                _gap[0] = min(8.0, _gap[0] * 1.6)
                print(f"    GeckoTerminal 429，等 {20 * (i + 1)} 秒", flush=True)
                time.sleep(min(20 * (i + 1), max(0, end_at - time.time())))
                continue
            raise
        except Exception:
            if i < 3:
                time.sleep(5)
                continue
            raise


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    import importlib.util, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location("名录", os.path.join(os.path.dirname(os.path.abspath(__file__)), "发射台名录.py"))
    lib = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lib)
    matrix = load(os.path.join(DATA, "发射台矩阵.json"), {}) or {}
    slugs = {p["slug"] for p in matrix.get("协议") or []}
    hist = load(HIST, {}) or {}
    batches = hist.setdefault("存活批次", {})
    daily = hist.setdefault("逐日", {})
    events = {k: v for k, v in (load(EVENTS, {}) or {}).items() if not k.startswith("_")}

    # 平台 slug → [(链, 工厂地址)]：用名录的合并结果（档案 / 名字 / 域名对上 DefiLlama 的）
    addr = defaultdict(list)
    for e in lib.collect():
        s = e.get("defillama")
        if s and s in slugs:
            addr[s] += [(c, a) for c, a, _ in e.get("地址") or [] if c != "solana"]
    chains = {c: load(os.path.join(OC, f"{c}.json"), {}) or {} for c in {c for v in addr.values() for c, _ in v}}

    out, jobs = {}, []
    for slug in sorted({k for k, v in addr.items() if v} | set(events)):
        fs = addr.get(slug) or []
        rec = {}
        if fs:
            n1 = n7 = 0
            ppl, coins = defaultdict(int), defaultdict(int)
            last, est, ks = [], False, set()
            for c, a in fs:
                days = chains[c].get("逐日") or {}
                ds = sorted(days)[-7:]
                if not ds:
                    continue
                last.append(ds[-1])
                for d in ds:
                    v = (days[d].get("工厂") or {}).get(a)
                    if v:
                        n7 += v[0]
                        ppl[d] += v[1]
                        coins[d] += v[0]
                        if d == ds[-1]:
                            n1 += v[0]
                    if days[d].get("抽样"):
                        est = True
                        ks.add(days[d]["抽样"])
            dd = min(last) if last else None
            kk = "、".join(f"1/{k}" for k in sorted(ks))
            cal = "工厂合约当天新铸整数供应量的币（拉链上新台.py），下限" + (f"；这条链每小时只扫 {kk} 的块，数量按比例放大，是估算" if est else "")
            rec["数据日"] = dd
            rec["发币"] = {"1d": n1, "7d": n7, "估算": est, "工厂": [f"{c}:{a}" for c, a in fs], "口径": cal, "来源": "链上"}
            # 扫描按「铸给谁」分组、每组只抽 3 笔交易认工厂：所有币都铸给同一个曲线合约的平台（Montra 这类）一天只看得到 1～3 个发币人，
            # 这个下限没意义，不写（null），写原因
            top = max(ppl.values()) if ppl else None
            dtop = max(ppl, key=ppl.get) if ppl else None
            grouped = top is not None and coins[dtop] >= 30 and top < 0.1 * coins[dtop]     # 查到的发币人不到当天币数的一成 = 只抽到几笔
            rec["发币人"] = {"7d": None if grouped else top, "来源": "待接入" if grouped else "链上",
                          "口径": ("这家的币都铸给同一个合约，扫描每组只抽 3 笔交易认工厂，查到的发币人不到当天币数的一成，数不出来；要逐个币查创建交易才行" if grouped else
                                 "查过交易的不同发币地址；每天单独数，取 7 天里最多的一天（没记 7 天去重），下限")}
            # 存活：批次 = 最近扫过的日子往前 7 天；当天没查到就先显示最近一批查过的
            rec["存活"] = surv = {"批次": None, "发出": None, "样本": None, "7天后仍有交易": None, "市值过10万美元": None,
                                  "口径": f"批次那天发的币里抽 {SURV_MAX} 个，发出后 7～8 天逐个用 GeckoTerminal 查它的全部池子（含发射台曲线池）："
                                        "近 24 小时有买卖的个数、市值（没有就用 FDV）≥ 10 万美元的个数；GeckoTerminal 没收录的池子看不到，算没交易，下限",
                                  "来源": "GeckoTerminal（链上样本 + 第三方行情）"}
            mine = batches.setdefault(slug, {})
            if mine:
                surv.update(mine[max(mine)])
            if dd:
                b = shift(dd, -SURV_DAYS)
                if b not in mine:
                    sample, sent, label, boot = [], 0, b, False
                    for c, a in fs:
                        sv = ((chains[c].get("存活样本") or {}).get(b) or {}).get(a) or []
                        sample += [(c, t) for t in sv]
                        v = ((chains[c].get("逐日") or {}).get(b) or {}).get("工厂", {}).get(a)
                        sent += v[0] if v else 0
                    if not sample:                     # 存活样本 11-15 才开始留：之前用每天 3 个的旧样本，拼 7 天
                        boot, label, sent = True, f"{shift(b, -6)}～{b}", 0
                        for i in range(7):
                            d = shift(b, -i)
                            for c, a in fs:
                                v = ((chains[c].get("逐日") or {}).get(d) or {}).get("工厂", {}).get(a)
                                if v:
                                    sample += [(c, t) for t in v[2]]
                                    sent += v[0]
                    sample = sample[:SURV_MAX]
                    if sample and all(c in GT_NET for c, _ in sample):
                        jobs.append((max(mine) if mine else "", slug, b, label, boot, sent, sample))
                    elif sample:
                        surv["来源"] = "待接入（GeckoTerminal 没有这条链）"
        rec["交易者"] = {"1d": None, "7d": None, "前10地址成交占比": None, "口径": "要逐笔扫交易事件，每条链不一样，还没接", "来源": "待接入"}
        rec["事件"] = sorted(events.get(slug) or [], key=lambda x: x.get("日期") or "")
        out[slug] = rec
        if rec.get("发币"):
            daily.setdefault(rec["数据日"], {})[slug] = {"发币1d": rec["发币"]["1d"], "发币7d": rec["发币"]["7d"], "发币人7d": rec["发币人"]["7d"]}

    def save():
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        json.dump({"更新UTC": now, "说明": "发射台板块 → Alpha 雷达接口（2026-11-15）。null = 待接入，不估。", "平台": out},
                  open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        hist["更新UTC"] = now
        hist["逐日"] = dict(sorted(daily.items()))
        json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    save()                                         # 发币数先落盘：存活查询超时也不丢
    # 存活：GeckoTerminal 限速狠（Actions 上也 429），每次限时 SURV_TIME，最久没查的平台先查；查完一个存一次
    calls, done, end_at = 0, 0, time.time() + SURV_TIME
    for _, slug, b, label, boot, sent, sample in sorted(jobs):
        if time.time() > end_at:
            break
        try:
            live = big = seen = 0
            for c, t in sample:
                ps = gt_pools(GT_NET[c], t, end_at)
                calls += 1
                seen += bool(ps)
                tx = sum(((p.get("transactions") or {}).get("h24") or {}).get(k) or 0 for p in ps for k in ("buys", "sells"))
                mc = max([_num(p.get("market_cap_usd")) or _num(p.get("fdv_usd")) or 0 for p in ps] or [0])
                live += tx > 0
                big += mc >= MCAP_LINE
        except Exception as ex:
            print(f"  {slug} 存活没查完：{str(ex)[:120]}", flush=True)
            continue
        res = {"批次": label, "发出": sent or None, "样本": len(sample), "收录": seen, "7天后仍有交易": live,
               "市值过10万美元": big, "查询日": today_utc()}
        if boot:
            res["说明"] = "早期批次：每个工厂每天只留了 3 个样本币，这里把 7 天的样本拼成一批，币龄 7～14 天"
        batches[slug][b] = res                     # 同一批次不再重查
        out[slug]["存活"].update(res)
        done += 1
        save()
        print(f"  {slug} 存活 {label}：{live}/{len(sample)} 还在交易，{big} 个市值过 10 万（GeckoTerminal 累计 {calls} 次）", flush=True)
    n_s = sum(1 for v in out.values() if (v.get("存活") or {}).get("7天后仍有交易") is not None)
    print(f"  平台质量：{len(out)} 个平台（有发币数 {sum(1 for v in out.values() if v.get('发币'))}，有存活 {n_s}；"
          f"今天新查 {done} / 待查 {len(jobs)}），GeckoTerminal 调用 {calls} 次")


if __name__ == "__main__":
    main()
