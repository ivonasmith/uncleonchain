#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发射台日更 · 拉日度序列
口径：全部用手续费(fees)，UTC 日聚合，剔除今天那根不完整的点。
产出 日度数据.json（每次全量重拉，DefiLlama 事后修订的历史值会自动跟上）

⚠️ slug ≠ module，只能用 slug。
⚠️ https://api.llama.fi/overview/launchpads 返回 500，不存在，别调。
"""
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from common import get, day, today_utc, shift, save

FOCUS = {
    "pump.fun": ("pump.fun", "Solana"),
    "pons-v1":  ("Pons V1", "Robinhood Chain"),
    "pons-v2":  ("Pons V2", "Robinhood Chain"),
    # 2026-09-26 新增。⚠️ DefiLlama 对 stonkfun 的 fees 只记平台自己那份（=revenue），
    # 与 pump.fun 的 fees（含创作者费）不同口径，横向比较一律用 revenue。
    "stonkfun": ("StonkFun", "Solana"),
    "flap-sh":  ("Flap sh", "BSC + X Layer + Monad + RH"),
}
# 已知返回 400，别重试
BAD = {"jup-studio", "bigpump", "seiyan-fun", "moonshot", "vectorfun", "daos.fun",
       "pools-trade", "ansem-io", "americafun", "user-fun"}


def series(slug, dtype):
    """返回 {YYYY-MM-DD: 美元}，已剔除今天；接口失败返回 None（区别于"真的是 0"）"""
    try:
        d = get(f"https://api.llama.fi/summary/fees/{slug}?dataType={dtype}", tries=3)
    except Exception:
        return None
    today = today_utc()
    out = {}
    for t, v in (d.get("totalDataChart") or []):
        k = day(t)
        if k >= today:            # 当天不完整，剔掉
            continue
        out[k] = out.get(k, 0) + (v or 0)
    return out


def main():
    expected = shift(today_utc(), -1)          # 应该拿到的最后一个完整日
    ov = get("https://api.llama.fi/overview/fees"
             "?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true")
    lp = [p for p in ov["protocols"] if p.get("category") == "Launchpad"]
    lp.sort(key=lambda p: p.get("total30d") or 0, reverse=True)
    top60 = [p["slug"] for p in lp[:60] if p.get("slug") and p["slug"] not in BAD]

    jobs = [(s, "dailyFees") for s in set(top60) | set(FOCUS)]
    jobs += [(s, "dailyRevenue") for s in FOCUS]
    with ThreadPoolExecutor(max_workers=8) as ex:      # 8 线程对 DefiLlama 没有限流问题
        res = dict(zip(jobs, ex.map(lambda j: series(*j), jobs)))

    # 赛道当日总量 = Top60 加总（尾部未计入，实际总量略高）
    total = {}
    for s in top60:
        for k, v in (res.get((s, "dailyFees")) or {}).items():
            total[k] = total.get(k, 0) + v

    # 分母覆盖检查：前一天有数、目标日没数的协议（DefiLlama 延迟）会让份额虚高
    prev = shift(expected, -1)
    missing = []
    for s in top60:
        m = res.get((s, "dailyFees")) or {}
        if prev in m and expected not in m and m[prev] > 0:
            missing.append({"slug": s, "前一日手续费": m[prev]})
    miss_share = (sum(x["前一日手续费"] for x in missing) / total[prev]) if total.get(prev) else 0

    data = {
        "生成时间UTC": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "口径": "手续费(fees)，UTC 日聚合，已剔除当天不完整点；赛道总量为 Top60 加总，尾部未计入",
        "期望最后一天": expected,
        "赛道Top60日总量": total,
        "赛道分母缺失": {"日期": expected, "缺失协议": missing, "缺失占前一日总量": miss_share},
        "平台": {},
        "接口失败": [f"{s}:{t}" for (s, t), v in res.items() if v is None and s in FOCUS],
    }
    for slug, (name, chain) in FOCUS.items():
        fees = res.get((slug, "dailyFees")) or {}
        data["平台"][slug] = {
            "名称": name, "链": chain,
            "fees": fees,
            "revenue": res.get((slug, "dailyRevenue")) or {},
            "累计": next((p.get("totalAllTime") for p in lp if p["slug"] == slug), None),
            "最后一天": max(fees) if fees else None,
            "延迟": (max(fees) if fees else "") < expected,
        }
    data["Top60数量"] = len(top60)
    data["Launchpad协议总数"] = len(lp)

    out = save("日度数据.json", data)
    print("写入", out, "期望最后一天", expected)
    for slug in FOCUS:
        p = data["平台"][slug]
        print(f"  {FOCUS[slug][0]:10s} 天数 {len(p['fees']):4d}  最后一天 {p['最后一天']}"
              + ("  ⚠️ 延迟" if p["延迟"] else ""))
    print("  赛道总量天数", len(total), " Top60", len(top60), " 全类目", len(lp),
          f" 分母缺失 {len(missing)} 家 占 {miss_share:.1%}")


if __name__ == "__main__":
    main()
