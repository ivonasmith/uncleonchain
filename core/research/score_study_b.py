#!/usr/bin/env python3
"""评分研究 M3b：扩大样本（不限币安上市）。研究用，不接网站。结果 → core/research/score_study_m3b.json

==== 判定标准（2026-11-14 跑之前写死，跑完不改）====
样本：DefiLlama 有协议收入、母协议登记了 gecko_id 的全部代币（不限交易所），每月 1 日 t 入选条件只用 t 之前的数据：
  ① 前 30 天协议收入 ≥ 10 万美元；② coins.llama.fi 在 t−1 有价格；③ 前 30 天里不同价格的天数 ≥ 20（剔除没成交的僵尸价格）；
  ④ 不是稳定币 / BTC / ETH 及其包装币。
价格：coins.llama.fi（DefiLlama 汇总价，coingecko:<id>），日频。
结果：t−1 到 t+h−1 的收益（h = 30 / 60 / 90）。
时段：2021-01 ～ 2024-06 定方向（样本内），2024-07 ～ 2026-10 只检验（样本外）。
指标：每月 Spearman IC；60 / 90 天用不重叠月份算 t；偏 IC = 读数排名对“收入规模（log 30 天收入）排名 + 近 30 天涨跌排名”回归取残差后的 IC；
  五档单调 = 样本外五档平均超额与档位的秩相关。每月 ≥ 20 个币才算这个月。
方向：有先验的按先验（收入增长、价值捕获、抽成率、收入领先价格、业务量增长 = 越高越好）；没有先验的（技术面）用样本内 IC 符号。
通过 = 样本外 30 天 IC（按方向）> 0 且 t ≥ 2，60 天同号，五档单调 ≥ 0.7；证伪 = 样本外 30 天 IC < 0 且 t ≤ −1；其余未通过。
R3（价格跑在收入前面 > 30pp）0/1 检验：每月标记组 − 未标记组平均收益（各 ≥ 5 个币）；通过 = 样本外均值 < 0 且 t ≤ −2、60 天同号；证伪 = 均值 > 0 且 t ≥ 1。
"""
import json, math, os, statistics as st, sys
import datetime as dt
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_study as S   # noqa: E402  复用取数、读数、统计函数（M2 模式，不触发它的 main）

C = S.C
START, TRAIN_END, MIN_REV, MIN_N = "2021-01-01", "2024-06-30", 100_000, 20
S.MIN_REV30 = MIN_REV          # factors() 里的入选门槛
S.LP_FROM = "2020-06-01"
FK = ["rev_7v30", "rev_30v30", "rev_90v90", "holder_share", "take_rate", "rev_lead", "act_30v30", "dist_ma200", "dd120", "pos30"]
STABLE = S.STABLE | {"USDE", "SUSDE", "USD0", "FRAX", "GHO", "CRVUSD", "LUSD", "WEETH", "RETH", "CBETH", "MSOL", "JITOSOL", "BNSOL"}


def build():
    protos = S.cached("protocols_all", lambda: [{k: p.get(k) for k in ("symbol", "gecko_id", "slug", "parentProtocol", "category")} for p in C.get(f"{C.LLAMA}/protocols")], 240)
    ov = S.cached("ov_rev", lambda: C.get(f"{C.LLAMA}/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue")["protocols"], 240)
    allt = {x["slug"]: x.get("totalAllTime") or 0 for x in ov if x.get("slug")}
    par = {}
    for p in protos:
        sy = (p.get("symbol") or "").upper()
        if not sy or sy == "-" or sy in STABLE or p.get("category") in S.SKIP_CAT:
            continue
        slug = (p.get("parentProtocol") or "").replace("parent#", "") or p["slug"]
        par[slug] = par.get(slug, 0) + allt.get(p["slug"], 0)
    slugs = sorted(s for s, v in par.items() if v >= 2_000_000)
    C.log(f"累计协议收入 ≥ 200 万美元的母协议 {len(slugs)} 个")
    fees = dict(ThreadPoolExecutor(8).map(lambda sl: (sl, S.cached(f"fees_{sl}", lambda: S.llama_fees(sl), 240)), slugs))
    uni = {}
    seen = set()
    for sl, f in sorted(fees.items(), key=lambda kv: -sum((kv[1].get("revenue") or {}).values())):
        m = f.get("meta") or {}
        gid, sy = m.get("gecko"), (m.get("symbol") or "").upper()
        if not gid or gid in seen or sy in STABLE:
            continue
        seen.add(gid)
        uni[sl] = {"slug": sl, "sym": sy or sl, "gecko": gid, "f": f, "mc": {}, "tvl": {}}
    def pj(sl):
        g = uni[sl]["gecko"]
        return sl, S.cached(f"lp_{g}_2020-06", lambda: S.llama_price(g), 240)
    for sl, lp in ThreadPoolExecutor(8).map(pj, list(uni)):
        uni[sl]["px"] = {d: [p, None] for d, p in lp.items() if p}
    uni = {k: v for k, v in uni.items() if v["px"]}
    C.log(f"有 gecko_id 且有价格的：{len(uni)} 个")
    return uni


def alive(u, t):
    ps = [u["px"].get(S.day(t, -i), [None])[0] for i in range(1, 31)]
    return len({round(p, 10) for p in ps if p}) >= 20


def main():
    uni = build()
    last = max(max(u["px"]) for u in uni.values())
    dates, d = [], dt.date.fromisoformat(START)
    while d.isoformat() <= last:
        dates.append(d.isoformat())
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    panel = {}
    for t in dates:
        rows = {}
        for sl, u in uni.items():
            if not alive(u, t):
                continue
            o = S.factors(u, t)
            if not o or o.get("ret30") is None:
                continue
            r30 = S.win(u["f"]["revenue"], t, 30)
            o["_size"] = math.log(max(sum(r30), 1))
            for h in (30, 60, 90):
                p1 = u["px"].get(S.day(t, h - 1))
                o[f"_fwd{h}"] = (p1[0] / o["_px"] - 1) * 100 if p1 else None
            rows[sl] = o
        panel[t] = rows
    C.log("每月样本：" + " ".join(str(len(panel[t])) for t in dates))
    res = {}
    for fk in FK:
        out = {"name": S.NAME[fk], "group": S.GROUP[fk], "prior": S.PRIOR[fk]}
        for h in (30, 60, 90):
            ics, pics, qs = [], [], []
            for t in dates:
                rows = [(o[fk], o[f"_fwd{h}"], o["_size"], o["ret30"]) for o in panel[t].values() if o.get(fk) is not None and o.get(f"_fwd{h}") is not None]
                if len(rows) < MIN_N or len({r[0] for r in rows}) < 3:
                    continue
                fx, fy = S.rank([r[0] for r in rows]), S.rank([r[1] for r in rows])
                ics.append((t, S.corr(fx, fy), len(rows)))
                pics.append((t, S.corr(S.rank(S.resid(fx, [S.rank([r[2] for r in rows]), S.rank([r[3] for r in rows])])), fy), len(rows)))
                med = st.median(r[1] for r in rows)
                order = sorted(range(len(rows)), key=lambda i: rows[i][0])
                qs.append((t, [st.mean(rows[i][1] - med for i in order[q * len(rows) // 5:(q + 1) * len(rows) // 5]) for q in range(5)]))
            step = {30: 1, 60: 2, 90: 3}[h]

            def summ(sel):
                xs = [x for x in sel if x[1] is not None]
                if not xs:
                    return None
                v = [x[1] for x in xs[::step]]
                tt = S.tstat(v)
                return {"months": len(xs), "ic": round(st.mean(x[1] for x in xs), 4), "t": None if tt is None else round(tt, 2),
                        "hit": round(sum(1 for x in xs if x[1] > 0) / len(xs) * 100), "n": round(st.mean(x[2] for x in xs), 1)}
            qte = [q for t, q in qs if t > TRAIN_END]
            qm = [round(st.mean(q[i] for q in qte), 2) for i in range(5)] if qte else None
            out[h] = {"train": summ([x for x in ics if x[0] <= TRAIN_END]), "test": summ([x for x in ics if x[0] > TRAIN_END]),
                      "ptrain": summ([x for x in pics if x[0] <= TRAIN_END]), "ptest": summ([x for x in pics if x[0] > TRAIN_END]),
                      "q_test": qm, "mono": round(S.corr(S.rank([0, 1, 2, 3, 4]), S.rank(qm)), 2) if qm and len(set(qm)) > 1 else None}
        dirn = S.PRIOR[fk] or ((1 if out[30]["train"]["ic"] > 0 else -1) if out[30].get("train") else 0)
        te30, te60 = out[30].get("test"), out[60].get("test")
        if not te30 or not dirn:
            v = "样本不足"
        elif te30["ic"] * dirn > 0 and (te30["t"] or 0) * dirn >= 2 and te60 and te60["ic"] * dirn > 0 and (out[30]["mono"] or 0) * dirn >= 0.7:
            v = "通过"
        elif te30["ic"] * dirn < 0 and (te30["t"] or 0) * dirn <= -1:
            v = "证伪"
        else:
            v = "未通过"
        out["direction"], out["verdict"] = dirn, v
        res[fk] = out
        C.log(f"{fk:13s} {v:4s} 方向 {dirn:+d} 样本内 {(out[30]['train'] or {}).get('ic')} 样本外 {te30 and te30['ic']} t {te30 and te30['t']} 60天 {te60 and te60['ic']} 偏IC {(out[30]['ptest'] or {}).get('ic')} 单调 {out[30]['mono']} 五档 {out[30]['q_test']}")
    # R3 0/1
    r3 = {}
    for h in (30, 60, 90):
        diffs = []
        for t in dates:
            fl = [o[f"_fwd{h}"] for o in panel[t].values() if o.get("flag_r3") == 1 and o.get(f"_fwd{h}") is not None]
            nf = [o[f"_fwd{h}"] for o in panel[t].values() if o.get("flag_r3") == 0 and o.get(f"_fwd{h}") is not None]
            if len(fl) >= 5 and len(nf) >= 5:
                diffs.append((t, st.mean(fl) - st.mean(nf)))
        step = {30: 1, 60: 2, 90: 3}[h]
        for nm, sel in (("train", [x for x in diffs if x[0] <= TRAIN_END]), ("test", [x for x in diffs if x[0] > TRAIN_END])):
            if sel:
                tt = S.tstat([x[1] for x in sel[::step]])
                r3.setdefault(h, {})[nm] = {"months": len(sel), "diff": round(st.mean(x[1] for x in sel), 2), "t": None if tt is None else round(tt, 2)}
    te, te60 = (r3.get(30) or {}).get("test"), (r3.get(60) or {}).get("test")
    r3["verdict"] = "样本不足" if not te else "通过" if te["diff"] < 0 and (te["t"] or 0) <= -2 and te60 and te60["diff"] < 0 else "证伪" if te["diff"] > 0 and (te["t"] or 0) >= 1 else "未通过"
    C.log(f"R3 0/1：{r3['verdict']} {json.dumps(r3, ensure_ascii=False)}")
    meta = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "dates": [dates[0], dates[-1]], "train_end": TRAIN_END,
            "universe": len(uni), "per_month": {t: len(panel[t]) for t in dates},
            "holder_coins_per_month": {t: sum(1 for o in panel[t].values() if (o.get("holder_share") or 0) > 0) for t in dates}}
    json.dump(C.clean({"meta": meta, "factors": res, "r3": r3}), open(os.path.join(HERE, "score_study_m3b.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    C.log("完成")


if __name__ == "__main__":
    main()
