#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发射台日更 · 回购市盈率与估值序列 → 估值序列.json

逐日累加，永不丢历史：每次按数据源能给的窗口全量重算，窗口以外的旧行原样保留
（CoinGecko 免费接口只给 365 天，用户要看 1–2 年，这个文件是本工作流最不能丢的资产）。

口径（写死，不要改）：
  市值       一律 burn-adjusted 流通市值。⛔ 不用 totalSupply，⛔ 不用 FDV。
  年化       近 30 日滚动合计 × 365 ÷ 30；不足 30 天按实际天数折算，并把「窗口不足30天」置 true。
  收入市盈率 = 市值 ÷ 年化协议收入
  回购市盈率 = 市值 ÷ 年化回购销毁额     ← 头条指标
  回购收益率 = 回购市盈率的倒数

平台币：
  PUMP   CoinGecko pump-fun 日度市值（真实流通市值）；回购额 DefiLlama pump.fun dailyHoldersRevenue
         （口径：链上销毁，汇总了 pump 全部产品线）。理论回购 = 协议收入 × 100%。
  STONK  2026-09-26 新增。CoinGecko stonk-3 日度市值；回购额 DefiLlama stonkfun dailyHoldersRevenue
         （口径：Jupiter 上买回 STONK、回到运营钱包的 swap）。理论回购 = 协议收入 × 60%
         —— 60% 是官网公布的政策，不是链上强制规则。
  PONS   GeckoTerminal 最深池日线收盘 × (10 亿 − 日末累计销毁)；回购额 = 当日销毁枚数 × 当日收盘价。
         理论回购 = 协议收入 × 80%（官方口径，人工在跑，非合约强制）。
         ⚠️ dailyHoldersRevenue / dailyProtocolRevenue 对 pons-v1 / pons-v2 都不存在，别去试。
  Flap   ⛔ 没有权益型平台币，市盈率不适用。bBroker（BSC 0xf1969F437Fe3C485468FB17B0d9861c24DCd7777）
         是 bBroker Vault 的 NFT 金库配套代币，价值来自金库分红而不是平台手续费，不能拿它算市盈率。
"""
import time, datetime as dt
from common import get, day, today_utc, load, save

PONS_POOL = "0x10cc6bd38112cac182db90b6a71d8bb5939526ba"   # PONS/WETH 1%，储备最深
PONS_TOTAL_SUPPLY = 1_000_000_000
CG_TOKENS = {   # 符号: (CoinGecko id, DefiLlama slug, 平台名, 链, 理论回购比例, 回购口径说明)
    "PUMP":  ("pump-fun", "pump.fun", "pump.fun", "Solana", 1.0,
              "DefiLlama dailyHoldersRevenue（官方说明：PUMP token buyback, sourced from onchain burns）"),
    "STONK": ("stonk-3", "stonkfun", "StonkFun", "Solana", 0.6,
              "DefiLlama dailyHoldersRevenue（Jupiter 上买回 STONK 的 swap；60% 为官网政策，非链上强制）"),
}


def llama(slug, dtype):
    try:
        d = get(f"https://api.llama.fi/summary/fees/{slug}?dataType={dtype}", tries=3)
    except Exception:
        return {}
    out = {}
    for t, v in (d.get("totalDataChart") or []):
        out[day(t)] = out.get(day(t), 0) + (v or 0)
    return out


def roll_ann(series, days_sorted, i, win=30):
    lo = max(0, i - win + 1)
    w = days_sorted[lo:i + 1]
    n = len(w)
    return (sum(series.get(d, 0) for d in w) * 365 / n, n) if n else (0, 0)


def build(mcap_fn, rev, bb, days_sorted, theory_ratio, qty_fn, price_fn=None):
    rows = []
    for i, d in enumerate(days_sorted):
        mc = mcap_fn(d)
        if not mc:
            continue
        ann_rev, n1 = roll_ann(rev, days_sorted, i)
        ann_bb, n2 = roll_ann(bb, days_sorted, i)
        day_rev, day_bb = rev.get(d, 0), bb.get(d, 0)
        rows.append({
            "日期": d, "市值": mc,
            "年化协议收入": ann_rev, "年化回购额": ann_bb,
            "收入市盈率": (mc / ann_rev) if ann_rev > 0 else None,
            "回购市盈率": (mc / ann_bb) if ann_bb > 0 else None,
            "回购收益率": (ann_bb / mc) if mc > 0 else None,
            "窗口天数": min(n1, n2), "窗口不足30天": min(n1, n2) < 30,
            "当日协议收入": day_rev, "当日回购额": day_bb,
            "当日回购占收入": (day_bb / day_rev) if day_rev > 0 else None,
            "当日理论回购额": day_rev * theory_ratio,
            "当日回购代币数": qty_fn(d),
            "价格": price_fn(d) if price_fn else None,
        })
    return rows


def merge(old_rows, new_rows):
    """新算的覆盖同日期；新窗口以前的旧行原样保留"""
    if not new_rows:
        return old_rows or []
    first = new_rows[0]["日期"]
    keep = [r for r in (old_rows or []) if r["日期"] < first]
    return keep + new_rows


def main():
    today = today_utc()
    prev = load("估值序列.json", {}) or {}
    prev_tok = prev.get("代币", {})
    tokens = {}

    # ---------- PUMP / STONK：CoinGecko 市值 + DefiLlama 收入与回购 ----------
    for sym, (cg, slug, plat, chain, ratio, bb_note) in CG_TOKENS.items():
        try:
            m = get(f"https://api.coingecko.com/api/v3/coins/{cg}/market_chart"
                    "?vs_currency=usd&days=365&interval=daily")
        except Exception as e:
            print(f"  {sym}: CoinGecko 失败 {e}，保留旧序列")
            if sym in prev_tok:
                tokens[sym] = prev_tok[sym]
            continue
        mcap = {day(t / 1000): v for t, v in m["market_caps"] if day(t / 1000) < today}
        px = {day(t / 1000): v for t, v in m["prices"] if day(t / 1000) < today}
        rev, bb = llama(slug, "dailyRevenue"), llama(slug, "dailyHoldersRevenue")
        ds = sorted(set(mcap) & (set(rev) | set(bb)))
        rows = build(lambda d: mcap.get(d), rev, bb, ds, ratio,
                     lambda d, bb=bb, px=px: (bb[d] / px[d]) if d in bb and px.get(d) else None,
                     lambda d, px=px: px.get(d))
        supply = None
        try:   # 核对 CoinGecko 的流通量是否已经扣掉销毁（burn-adjusted 口径的前提）
            time.sleep(2)
            c = get(f"https://api.coingecko.com/api/v3/coins/{cg}?localization=false&tickers=false"
                    "&market_data=true&community_data=false&developer_data=false")
            md = c.get("market_data") or {}
            supply = {"流通量": md.get("circulating_supply"), "总量": md.get("total_supply"),
                      "最大供应": md.get("max_supply"), "读取日": today}
        except Exception:
            pass
        tokens[sym] = {
            "平台": plat, "链": chain, "回购口径": bb_note, "理论回购比例": ratio,
            "价格与市值来源": f"CoinGecko {cg} 日度 market_chart（流通市值）",
            "供应快照": supply,
            "序列": merge((prev_tok.get(sym) or {}).get("序列"), rows),
        }
        time.sleep(2)   # CoinGecko 免费档限速

    # ---------- PONS：GeckoTerminal 价格 + 链上日末累计销毁 ----------
    try:
        gt = get(f"https://api.geckoterminal.com/api/v2/networks/robinhood/pools/{PONS_POOL}"
                 "/ohlcv/day?aggregate=1&limit=1000&currency=usd")
        pons_price = {day(o[0]): o[4] for o in gt["data"]["attributes"]["ohlcv_list"] if day(o[0]) < today}
    except Exception as e:
        print("  PONS: GeckoTerminal 失败", e)
        pons_price = {}
    v1, v2 = llama("pons-v1", "dailyRevenue"), llama("pons-v2", "dailyRevenue")
    pons_rev = {d: v1.get(d, 0) + v2.get(d, 0) for d in set(v1) | set(v2)}
    burn_daily = load("销毁逐日.json", {})
    cum_exact = load("销毁累计.json", {})
    ledger = load("销毁台账.json", [])
    bdays = sorted(burn_daily)
    # 日末累计：以最近一个精确日末值为锚，向前逐日倒推；没有精确值时退回台账最新读数
    if cum_exact:
        anchor_day = max(cum_exact)
        running = cum_exact[anchor_day]["累计"]
    else:
        anchor_day = bdays[-1] if bdays else None
        running = ledger[-1]["销毁地址持仓"] if ledger else 0
    cum = {}
    for d in reversed([x for x in bdays if x <= (anchor_day or "")]):
        cum[d] = running
        running -= burn_daily[d]
    pons_bb = {d: burn_daily[d] * pons_price[d] for d in bdays if d in pons_price}
    pons_days = sorted(set(pons_price) & set(cum))
    pons_rows = build(lambda d: (PONS_TOTAL_SUPPLY - cum[d]) * pons_price[d],
                      pons_rev, pons_bb, pons_days, 0.8, lambda d: burn_daily.get(d),
                      lambda d: pons_price.get(d))
    tokens["PONS"] = {
        "平台": "Pons V1+V2", "链": "Robinhood Chain", "理论回购比例": 0.8,
        "回购口径": "链上 Transfer→dEaD 当日销毁枚数 × 当日收盘价（人工执行，非合约强制）",
        "价格与市值来源": f"GeckoTerminal 池 {PONS_POOL} 日线 × (10亿 − 日末累计销毁)",
        "序列": merge((prev_tok.get("PONS") or {}).get("序列"), pons_rows),
    }

    order = ["PUMP", "PONS", "STONK"]
    out = {
        "生成时间UTC": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "口径": "市值为 burn-adjusted 流通市值；年化 = 近 30 日滚动合计 ×365÷30，不足 30 天按实际天数折算并标记",
        "代币": {k: tokens[k] for k in order if k in tokens},
        "Flap": "无捕获平台收入的股权型代币，市盈率不适用。bBroker（BSC 0xf1969F437Fe3C485468FB17B0d9861c24DCd7777）"
                "是 bBroker Vault 的 NFT 配套代币，价值来自 NFT 金库分红而非平台手续费，不能当 Flap 的股票看。",
        "扫描起点之前的存量销毁": running,
    }
    save("估值序列.json", out)
    for k, v in out["代币"].items():
        r = v["序列"]
        if not r:
            print(f"  {k}: 无数据")
            continue
        x = r[-1]
        print(f"  {k:5s} {x['日期']}  市值 ${x['市值']:,.0f}  收入PE {x['收入市盈率'] and round(x['收入市盈率'], 2)}"
              f"  回购PE {x['回购市盈率'] and round(x['回购市盈率'], 2)}"
              f"  回购收益率 {x['回购收益率'] and round(x['回购收益率'] * 100, 1)}%  （序列 {len(r)} 天，{r[0]['日期']} 起）")
        if v.get("供应快照"):
            print("        供应快照", v["供应快照"])


if __name__ == "__main__":
    main()
