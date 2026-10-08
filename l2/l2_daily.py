# -*- coding: utf-8 -*-
"""
L2 周期层·每日自动更新（网站用）
  1) 取数：Coin Metrics 社区接口（价格、已实现市值、供应）+ bitview.space（分龄成本、持有者、盈亏、币天销毁）——都免费、无需账号
  2) 算信号、跑状态机：和研究文档《BTC周期层L2研究》§7 完全同一套代码（l2_signals.py）
  3) 输出：output/l2_latest.json（今日结论 + 信号 + 关键价位）、output/l2_history.json（近 400 天状态与价位，画图用）
用法：python l2_daily.py        （每天跑一次；GitHub Actions 定时任务见 网站接入说明.md）
某个数据源暂时取不到时：用上次缓存的数据继续算，并在 json 里标出“数据延迟”，不会让网站空白。
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from l2_signals import features, signals, run_states, STATES  # noqa: E402

OUT = Path(os.environ.get("L2_OUT_DIR", HERE / "output"))
CACHE = Path(os.environ.get("L2_CACHE_DIR", HERE / "cache"))
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)
CM = os.environ.get("L2_CM_BASE", "https://community-api.coinmetrics.io/v4")
BV = os.environ.get("L2_BV_BASE", "https://bitview.space")
UA = {"User-Agent": "Mozilla/5.0 (uncleonchain L2 daily)"}
NOTES = []

# ---------------- 取数 ----------------
SESSION = requests.Session()


def get(url, timeout=90, tries=3):
    last = None
    for i in range(tries):
        try:
            r = SESSION.get(url, headers=UA, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)[:120]
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url[:90]} → {last}")


def fetch_cm():
    """Coin Metrics 社区接口。注意：已实现市值 CapRealUSD 不在免费接口里，用 市值 ÷ MVRV 推出来（和研究用的 01_fetch_core.py 一样）"""
    metrics = ["PriceUSD", "CapMrktCurUSD", "CapMVRVCur", "SplyCur"]
    rows, url = [], (f"{CM}/timeseries/asset-metrics?assets=btc&metrics={','.join(metrics)}"
                     f"&frequency=1d&start_time=2010-07-01&page_size=10000")
    while url:
        j = get(url).json()
        rows += j.get("data", [])
        url = j.get("next_page_url")
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df.time).dt.tz_localize(None).dt.normalize()
    df = df.set_index("date")[metrics].apply(pd.to_numeric, errors="coerce").sort_index()
    df["CapRealUSD"] = df.CapMrktCurUSD / df.CapMVRVCur
    return df[["PriceUSD", "CapRealUSD", "SplyCur"]]


def cm_from_bitview():
    """Coin Metrics 取不到时的备用：价格、已实现市值、供应都从 bitview 取（最后一个值按今天 UTC 对齐）"""
    today = pd.Timestamp(os.environ.get("L2_TODAY") or datetime.now(timezone.utc).date())
    cols = {}
    for name, col in (("price_close", "PriceUSD"), ("realized_cap", "CapRealUSD"), ("supply", "SplyCur")):
        v = fetch_bv_values(name)
        cols[col] = pd.Series(v.values, index=pd.date_range(end=today, periods=len(v), freq="D"))
    df = pd.DataFrame(cols)
    df.index.name = "date"
    return df.dropna(subset=["PriceUSD"])


BV_SERIES = {
    "price_close": "bv_price",
    "sth_realized_price": "sth_rp", "lth_realized_price": "lth_rp", "true_market_mean": "tmmp",
    "supply_in_profit_share": "psip", "lth_supply": "lth_supply", "supply": "bv_supply",
    "sth_realized_profit_sum_1y": "p1y_sth", "lth_realized_profit_sum_1y": "p1y_lth",
    "sth_realized_loss_sum_1y": "l1y_sth", "lth_realized_loss_sum_1y": "l1y_lth",
    "sth_coindays_destroyed": "cdd_sth", "lth_coindays_destroyed": "cdd_lth",
}
BANDS = {"1_3m": ["1m_to_2m", "2m_to_3m"], "3_6m": ["3m_to_4m", "4m_to_5m", "5m_to_6m"], "6_12m": ["6m_to_9m", "9m_to_1y"],
         "12_18m": ["1y_to_18m"], "18_24m": ["18m_to_2y"], "under_10y": ["under_10y"], "over_6m": ["over_6m"],
         "over_10y": ["over_10y"], "over_7y": ["over_7y"]}
for bs in BANDS.values():
    for b in bs:
        BV_SERIES[f"utxos_{b}_old_supply"] = f"S_{b}"
        BV_SERIES[f"utxos_{b}_old_realized_cap"] = f"R_{b}"


# 币天销毁：不带后缀的序列没有日线，改用“24 小时合计”，再不行用累计值做差
ALT = {f"{c}_coindays_destroyed": [(f"{c}_coindays_destroyed_sum_24h", None), (f"{c}_coindays_destroyed", None),
                                     (f"{c}_coindays_destroyed_cumulative", "diff")] for c in ("sth", "lth")}


def fetch_bv_values(name):
    for path in (f"/api/series/{name}/day1/data?from=0", f"/api/series/{name}/day1?from=0"):
        try:
            j = get(BV + path, timeout=120, tries=2).json()
        except Exception:
            continue
        v = j if isinstance(j, list) else next((j[k] for k in ("data", "values") if isinstance(j, dict) and isinstance(j.get(k), list)), None)
        if v and len(v) > 300:
            return pd.to_numeric(pd.Series(v), errors="coerce")
    raise RuntimeError(f"bitview {name} 取不到")


def fetch_bv(cm_price):
    vals, missing = {}, []
    for name, col in BV_SERIES.items():
        got = None
        for cand, how in ALT.get(name, [(name, None)]):     # 同一指标在 bitview 里可能有几种命名，依次试
            try:
                v = fetch_bv_values(cand)
                got = v.diff() if how == "diff" else v
                if cand != name:
                    NOTES.append(f"{name} 改用 {cand}")
                break
            except Exception:
                continue
        if got is None:
            missing.append(name)
        else:
            vals[col] = got
        time.sleep(0.2)
    if "bv_price" not in vals:
        raise RuntimeError("bitview 价格序列取不到，无法对齐日期")
    # 日期对齐：bitview 返回的是不带日期的数组，末尾对齐后用价格和 Coin Metrics 比对，找误差最小的偏移
    n = len(vals["bv_price"])
    today = pd.Timestamp(os.environ.get("L2_TODAY") or datetime.now(timezone.utc).date())
    best = (9.0, 0)
    for k in range(-6, 3):
        idx = pd.date_range(end=today + pd.Timedelta(days=k), periods=n, freq="D")
        s = pd.Series(vals["bv_price"].values, index=idx)
        both = pd.concat([s, cm_price], axis=1, join="inner").dropna().iloc[-1500:]
        both = both[(both.iloc[:, 0] > 0) & (both.iloc[:, 1] > 0)]
        if len(both) > 300:
            e = float(np.median(np.abs(np.log(both.iloc[:, 0] / both.iloc[:, 1]))))
            if e < best[0]:
                best = (e, k)
    NOTES.append(f"bitview 日期偏移 {best[1]} 天，与 Coin Metrics 价格中位误差 {best[0] * 100:.2f}%")
    out = {}
    for col, v in vals.items():
        idx = pd.date_range(end=today + pd.Timedelta(days=best[1]), periods=len(v), freq="D")
        out[col] = pd.Series(v.values, index=idx)
    return pd.DataFrame(out), missing, best[0]


def load_or_fetch():
    status = {"coinmetrics": "ok", "bitview": "ok", "bitview_missing": []}
    try:
        cm = fetch_cm(); cm.to_csv(CACHE / "cm.csv")
    except Exception as e:
        print(f"Coin Metrics 取数失败：{e}")
        cm = None
        if (CACHE / "cm.csv").exists():
            status["coinmetrics"] = f"失败，用缓存：{e}"
            cm = pd.read_csv(CACHE / "cm.csv", parse_dates=["date"]).set_index("date")
        else:
            try:
                cm = cm_from_bitview()
                status["coinmetrics"] = f"失败，改用 bitview 的价格/已实现市值/供应：{e}"
            except Exception as e2:
                print(f"bitview 备用也失败：{e2}")
    if cm is None:
        raise SystemExit("Coin Metrics 和 bitview 都取不到。请确认网络（代理）能打开 https://community-api.coinmetrics.io 和 https://bitview.space")
    try:
        bv, miss, err = fetch_bv(cm.PriceUSD)
        status["bitview_missing"] = miss
        if err > 0.02:
            status["bitview"] = f"日期对齐误差偏大（{err * 100:.1f}%），请检查"
        old = pd.read_csv(CACHE / "bv.csv", parse_dates=["date"]).set_index("date") if (CACHE / "bv.csv").exists() else None
        if old is not None:                 # 个别序列这次没取到 → 用缓存补上
            for c in old.columns:
                if c not in bv.columns:
                    bv[c] = old[c].reindex(bv.index)
        bv.index.name = "date"
        bv.to_csv(CACHE / "bv.csv")
    except Exception as e:
        status["bitview"] = f"失败，用缓存：{e}"
        bv = pd.read_csv(CACHE / "bv.csv", parse_dates=["date"]).set_index("date") if (CACHE / "bv.csv").exists() else pd.DataFrame()
    return cm, bv, status


def build_raw(cm, bv):
    idx = cm.PriceUSD.dropna().index
    if len(bv) and "bv_price" in bv:     # Coin Metrics 当天还没更新时，用 bitview 价格补最后一两天
        extra = bv.bv_price[bv.index > idx.max()].dropna()
        idx = idx.union(extra.index[:2])
    bv = bv.reindex(idx)
    raw = pd.DataFrame(index=idx)
    raw["price"] = cm.PriceUSD.reindex(idx).fillna(bv.get("bv_price"))
    raw["supply"] = cm.SplyCur.reindex(idx).ffill()
    raw["realized_cap"] = cm.CapRealUSD.reindex(idx).ffill()
    for c in ("sth_rp", "lth_rp", "tmmp", "lth_supply"):
        raw[c] = bv.get(c)
    if "psip" in bv:
        raw["psip"] = bv.psip / 100 if bv.psip.max() > 1.5 else bv.psip
    if {"p1y_sth", "p1y_lth", "l1y_sth", "l1y_lth"} <= set(bv.columns):
        raw["profit_1y"] = bv.p1y_sth + bv.p1y_lth
        raw["loss_1y"] = (bv.l1y_sth + bv.l1y_lth).abs()
    if {"cdd_sth", "cdd_lth"} <= set(bv.columns):
        raw["cdd"] = bv.cdd_sth + bv.cdd_lth
    for k, bs in BANDS.items():
        if all(f"S_{b}" in bv and f"R_{b}" in bv for b in bs):
            raw[f"s_{k}"] = sum(bv[f"S_{b}"] for b in bs)
            raw[f"r_{k}"] = sum(bv[f"R_{b}"] for b in bs)
    raw = raw.ffill(limit=3)
    # 单位自检：CVDD 应该是价格的几分之一；如果币天销毁是按聪计的，会大出 1 亿倍
    if "cdd" in raw:
        age = (raw.index - pd.Timestamp("2009-01-03")).days
        cv = ((raw.cdd.fillna(0) * raw.price).cumsum() / (age * 6_000_000)).iloc[-1]
        if cv > 50 * raw.price.iloc[-1]:
            raw["cdd"] = raw.cdd / 1e8
            NOTES.append("币天销毁按聪计，已换算成 BTC")
    return raw


# ---------------- 信号说明（网站展示用） ----------------
SIG = {
    "Z_盈利供应<50%": ("盈利供应占比 < 50%", "Percent supply in profit < 50%", "底部区", "已验证·方向", "§3.4 #10",
                    "一半以上的币处在浮亏，历轮熊底都出现过"),
    "Z_利润365<亏损365": ("一年已实现利润 < 已实现亏损", "1y realized profit < realized loss", "底部区", "已验证·方向", "§3.4 #3",
                     "过去一年市场卖币时亏的比赚的多，属于投降式卖出"),
    "Z_MVRV<1": ("MVRV < 1", "MVRV < 1", "底部区", "已证伪（固定阈值，本轮未触发）", "§2.2", "价格低于全网平均成本"),
    "Z_价<200周均": ("价格 < 200 周均线", "Price < 200-week MA", "底部区", "已验证·方向", "§2.4", "历史上之后一年几乎都上涨"),
    "Z_LTH占比>75%": ("长期持有者占比（剔除 >7 年）> 75%", "LTH supply share ex-7y > 75%", "底部区", "假设", "§3.5 #21",
                    "筹码集中到长期持有者手里，4 轮里 3 轮在熊底前后出现"),
    "Z_价≤1.3×CVDD": ("价格 ≤ 1.3 × CVDD", "Price ≤ 1.3 × CVDD", "底部区", "已验证（价格下限）", "§3.4 #12", "接近历史上从未跌破的价格下限"),
    "C_底后+40%且过90天": ("离本轮最低点 +40% 且最低点已过 90 天", "+40% from cycle low and low ≥ 90 days old", "底部确认",
                     "已验证·方向（4 次对 3 次）", "§2.5", "历史上唯一一次假信号在 2014 年"),
    "C_四大名右7天": ("价格连续 7 天站上 3-6 月成本、1-3 月成本、200 日均、短期持有者成本", "Price above 4 short-term cost lines for 7 days",
                "底部确认", "已验证·方向", "§3.5 #20", "熊底右侧确认；需要本轮已出现过分龄底部信号才算数"),
    "C_6-12M死叉12-18M(本轮)": ("6-12 月成本跌破 12-18 月成本（本轮已出现）", "6-12M cost < 12-18M cost (this cycle)", "底部确认",
                           "已验证·方向", "§3.5 #16", "历轮都在真实底后 −1~+31 天出现"),
    "C_三叉第三叉(本轮)": ("6-12 月成本跌破 1-2 年成本（本轮已出现）", "6-12M cost < 1-2Y cost (this cycle)", "底部确认", "已验证·方向",
                    "§3.5 #17", "三叉筑底的第三叉，出现在真实底前后 85 天内"),
    "C_绿黑比≥1(本轮)": ("6 月-10 年成本 ≥ 0-10 年成本（本轮已出现）", "6m-10y cost ≥ 0-10y cost (this cycle)", "底部确认",
                    "已验证·方向（本轮未触发）", "§3.5 #22", "熊市够深时才会出现"),
    "C_STH成本<LTH成本(本轮)": ("短期持有者成本跌破长期持有者成本（本轮已出现）", "STH cost < LTH cost (this cycle)", "底部确认",
                           "已验证·方向（本轮未触发）", "§3.4 #1", "熊市够深时才会出现"),
    "T_减半后480~600天": ("处在减半后 480~600 天", "Halving + 480~600 days", "顶部风险", "已验证·方向", "§2.1",
                     "后三轮都在减半后 525~546 天见顶"),
    "T_MVRV≥2且价/200周均≥2": ("MVRV ≥ 2 且 价格/200 周均 ≥ 2", "MVRV ≥ 2 and Price/200WMA ≥ 2", "顶部风险", "已验证·方向（2018 年后）",
                           "§2.4", "2018 年后，之后一年中位收益为负"),
}

LEVELS = [("ath", "历史最高收盘", "ATH"), ("rp_1_2y", "1-2 年持币成本", "1-2Y cost"), ("rp_6_12m", "6-12 月持币成本", "6-12M cost"),
          ("tmmp", "真实市场均价 TMMP", "True Market Mean"), ("sth_rp", "短期持有者成本", "STH cost"), ("rp_3_6m", "3-6 月持币成本", "3-6M cost"),
          ("ma200d", "200 日均线", "200D MA"), ("ma200w", "200 周均线", "200W MA"), ("cyc_low", "本轮最低收盘", "Cycle low"),
          ("rp", "全网平均成本（已实现价格）", "Realized price"), ("lth_rp", "长期持有者成本", "LTH cost"), ("cvdd", "CVDD 价格下限", "CVDD"),
          ("balanced", "均衡价格（近似）", "Balanced price (approx.)")]

NEXT = {
    "BULL": ("新高后的上升期。观察：是否进入减半后 480~600 天的见顶时间窗，或估值进入高估区。",
             "Uptrend after a new high. Watch the halving +480~600 day window and valuation."),
    "BULL_RISK": ("处在历史见顶时间窗或高估区：2018 年后这一状态之后一年中位收益为负，不追高，按 L1 风险预算减仓或收紧止盈。从新高回撤超过 20% 转为“牛市回撤·待确认”。",
                  "Historical top window / overvaluation. Since 2018 the following year has a negative median return."),
    "BULL_PULLBACK": ("从新高回撤超过 20%。回撤收窄到 10% 以内回到牛市；回撤超过 35% 且新高已过 90 天、减半已过 450 天则确认转熊。",
                      "Pullback >20% from the high; bear is confirmed at −35% with the high ≥90 days old."),
    "BEAR": ("熊市下跌期，之后一年中位收益为负。等待“底部区”信号出现两条以上。",
             "Bear market. Wait for at least two bottom-zone signals."),
    "BEAR_ZONE": ("熊底区：历史上之后一年中位 +68%、91% 为正，但区间内仍可能再跌 30% 以上。等待底部确认：离最低点 +40% 且最低点已过 90 天，或价格连续 7 天站上四条短期成本线。",
                  "Bottom zone. Historically +68% median 1y forward, but further drawdowns are common."),
    "RECOVERY": ("底部已确认，熊末→牛初。历史上之后一年中位 +152%、92% 为正，但期间出现 20~60% 回撤很常见。收盘跌破本轮最低点则退回熊市。",
                 "Bottom confirmed. Historically +152% median 1y forward; 20–60% drawdowns along the way are common."),
}


def fmt(x):
    return f"{x:,.0f}" if pd.notna(x) else "—"


def main():
    cm, bv, status = load_or_fetch()
    raw = build_raw(cm, bv)
    F = features(raw)
    S = signals(F)
    st = run_states(F, S)
    t = F.index[-1]
    f, s, code = F.iloc[-1], S.iloc[-1], st.iloc[-1]
    since = st[st != code].index.max()
    since = (since + pd.Timedelta(days=1)) if pd.notna(since) else st.index[0]
    prev_code = st.iloc[-2]

    sig_list = []
    for k, (zh, en, cat, grade, ref, note) in SIG.items():
        if k in S:
            on = bool(s[k])
            was = bool(S[k].iloc[-2])
            sig_list.append(dict(key=k, name_zh=zh, name_en=en, category=cat, evidence=grade, ref=ref, note=note, on=on,
                                 changed_today=(on != was)))
    price = f.price
    lv = []
    for k, zh, en in LEVELS:
        v = f.get(k)
        if pd.notna(v) and v > 0:
            lv.append(dict(key=k, name_zh=zh, name_en=en, value=round(float(v), 2), pct_from_price=round((v / price - 1) * 100, 1)))
    above = sorted([x for x in lv if x["value"] > price], key=lambda x: x["value"])[:3]
    below = sorted([x for x in lv if x["value"] <= price], key=lambda x: -x["value"])[:3]

    zone_on = [x["name_zh"] for x in sig_list if x["category"] == "底部区" and x["on"]]
    conf_on = [x["name_zh"] for x in sig_list if x["category"] == "底部确认" and x["on"]]
    risk_on = [x["name_zh"] for x in sig_list if x["category"] == "顶部风险" and x["on"]]
    flips = [("亮起：" if x["on"] else "熄灭：") + x["name_zh"] for x in sig_list if x["changed_today"]]
    name_zh = STATES[code][0]
    head = f"L2 周期状态：{name_zh}（自 {since.date()} 起，第 {(t - since).days + 1} 天）"
    lines = [head,
             f"价格 {fmt(price)}，距历史高点 {f.dd * 100:.1f}%，距本轮最低收盘 +{f.rebound * 100:.1f}%（最低点已过 {int(f.d_low)} 天），距上次减半 {int(f.d_halving)} 天。"]
    if code in ("BEAR", "BEAR_ZONE", "RECOVERY"):
        lines.append(f"底部区信号 {len(zone_on)}/6：{('、'.join(zone_on)) or '无'}。底部确认信号：{('、'.join(conf_on)) or '无'}。")
    else:
        lines.append(f"顶部风险信号：{('、'.join(risk_on)) or '无'}。")
    lines.append("上方关键价位：" + ("；".join(f"{x['name_zh']} {fmt(x['value'])}（+{x['pct_from_price']}%）" for x in above) or "无"))
    lines.append("下方关键价位：" + ("；".join(f"{x['name_zh']} {fmt(x['value'])}（{x['pct_from_price']}%）" for x in below) or "无"))
    if code != prev_code:
        lines.append(f"今日状态变化：{STATES[prev_code][0]} → {name_zh}。")
    if flips:
        lines.append("今日信号变化：" + "；".join(flips) + "。")
    lines.append("接下来：" + NEXT[code][0])

    stale = [k for k, v in status.items() if k != "bitview_missing" and v != "ok"] + (["bitview 部分序列"] if status["bitview_missing"] else [])
    latest = dict(
        updated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), data_date=str(t.date()),
        state=dict(code=code, name_zh=name_zh, desc_zh=STATES[code][1], since=str(since.date()), days=int((t - since).days + 1),
                   previous=STATES[prev_code][0] if code != prev_code else None, next_zh=NEXT[code][0], next_en=NEXT[code][1]),
        summary_zh="\n".join(lines),
        price=round(float(price), 2),
        cycle=dict(ath=round(float(f.ath), 2), drawdown_pct=round(float(f.dd) * 100, 1), days_since_ath=int(f.d_ath),
                   cycle_low=round(float(f.cyc_low), 2), rebound_pct=round(float(f.rebound) * 100, 1), days_since_low=int(f.d_low),
                   days_since_halving=int(f.d_halving), next_halving_est="2028-04-10"),
        valuation=dict(mvrv=round(float(f.mvrv), 3), price_to_200w=round(float(f.p_200w), 3),
                       psip_pct=round(float(f.psip) * 100, 1) if pd.notna(f.psip) else None,
                       realized_pl_ratio_1y=round(float(f.pl_365), 3) if pd.notna(f.pl_365) else None,
                       lth_share_ex7y_pct=round(float(f.lth_share_ex7y) * 100, 1) if pd.notna(f.lth_share_ex7y) else None,
                       green_black=round(float(f.green_black), 3) if pd.notna(f.green_black) else None),
        counts=dict(bottom_zone=int(s.zone_n), bottom_confirm_agebands=int(s.confirm_n)),
        signals=sig_list, levels=lv, levels_above=above, levels_below=below,
        data_status=dict(stale=bool(stale), detail=status, notes=NOTES),
        method="规则化状态机，口径见《BTC周期层L2研究》§7；证据等级见各信号 evidence 字段。历史回放：熊末→牛初之后一年中位 +152%（92% 为正），熊底区 +68%（91%），顶部风险区 −6%（47%），熊市 −36%（31%）。",
    )
    json.dump(latest, open(OUT / "l2_latest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    H = pd.concat([F[["price", "sth_rp", "lth_rp", "rp", "tmmp", "ma200w", "rp_3_6m", "rp_6_12m", "cvdd"]], st], axis=1).iloc[-400:]
    hist = [dict(date=str(i.date()), state=r.state, **{k: (round(float(r[k]), 2) if pd.notna(r[k]) else None)
                                                       for k in H.columns if k != "state"}) for i, r in H.iterrows()]
    json.dump(hist, open(OUT / "l2_history.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(latest["summary_zh"])
    print("\n数据状态：", latest["data_status"])


if __name__ == "__main__":
    main()
