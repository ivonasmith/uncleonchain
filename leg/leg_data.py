#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
leg_data.py —— 网站「涨跌腿追踪 + 山寨轮动窗口」的数据文件生成器（schema 3）

用法（零配置，直接跑）：
    python3 leg_data.py                  # 拉全历史日线（Coin Metrics 2010-07-18 起 + 币安 2017-08-17 起），
                                         # 自动保存 leg_latest.json（当前读数）和 leg_history.json（逐条涨腿/跌腿历史）
    python3 leg_data.py --no-early       # 只用币安（2017-08 起），更快；历史文件会标注覆盖范围不完整
    python3 leg_data.py --asof 2026-09-27   # 回放：只用到这一天的收盘，用来和当天海报核对
    python3 leg_data.py --selftest       # 离线自测（合成数据），不联网
    python3 leg_data.py --csv 日线.csv   # 离线：用 date,close 两列的 csv，不联网

输出文件（都在本脚本所在文件夹；环境变量 LEG_OUT / LEG_HIST_OUT 可改路径）：
  leg_latest.json   当前读数。BTC 这一腿永远是「涨腿」或「跌腿」之一（direction=up/down），不再有「没有涨腿」的空状态。
  leg_history.json  全部历史涨腿/跌腿逐条记录 + 全部行情的分布统计（页面详情页用）。
  leg_early_cache.csv  2010-07-18~2017-08-16 的 Coin Metrics 日线缓存（这段历史不会变，只下载一次）。
口径：只用已收盘的 UTC 日线收盘价（2017-08-17 起币安现货 BTCUSDT，之前 Coin Metrics PriceUSD），当天未收盘的那根不算。
      数据截至 = 最后一根已收盘 UTC 日线。UTC 11-08 这根要到北京时间 11-09 08:00 才收盘，所以北京时间 11-09 早上读数仍是「截至 11-07」，这是对的。

规则全部来自《加密行情律动-规律清单》V13 / 《山寨补涨板块轮动预警框架》V4 / 《热币分析操作规格》v6.5：
  涨腿：收盘从摆动低点反向走出 10%，才确认该低点是涨腿起点；起点确认后天数/涨幅每天重算；
        收盘从高点回落 10%，这一轮结束。腿内最大回撤 = 腿内「当时的最高收盘 → 之后收盘」的最大回落。
  跌腿（对称）：涨腿结束的那个高点就是跌腿起点（收盘较高点回落 10% 当天确认）；天数从高点日算，
        跌幅 = 高点收盘到目前最低收盘；收盘从最低收盘反弹 10% → 跌腿结束，反弹的低点成为新涨腿起点。
        所以每天 BTC 必在「一条涨腿」或「一条跌腿」之中，整个行情都被覆盖（不分牛熊）。
        徽章：天数 > 89 才亮「多头只减不加」（规格 P0：超过 89 天且腿内回撤未达 10%）。
  山寨窗口：BTC 收盘 10 日涨幅 ≥15% 记为点火（距上一次点火不足 45 天不重复计）；
        点火当天起 7 天内（含点火日）最高收盘日 = D0；D0 要等这 7 天走完才定；
        D0+24 起只减不加，D0+28 起临近清零，D0+30 清零；
        D0 之后 BTC 收盘 < D0 收盘×0.90 → 窗口提前关闭（V4 §0-1，已验证）。

⚠ 下面三处在文档里写得不够死，脚本按「常见读法」实现，上线前必须用 --asof 回放和海报核对（见文末 ACCEPTANCE）：
  ① 10% 是「≥10%」还是「>10%」           → 常量 THR_EQ（默认含等号）
  ② D0 的 7 天窗口是否含点火当天          → 常量 D0_INCLUDE_IGNITION（默认含）
  ③ 「45 天内不重复」边界是 ≥45 还是 >45  → 常量 IGN_GAP（默认 i - last >= 45）
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

# ---------------------------- 参数 ----------------------------
THR = 0.10            # 涨腿/跌腿反向确认幅度
THR_EQ = True         # True: 收盘 ≥ 低点×1.10 / ≤ 高点×0.90 即触发
LINE_DAYS = 89        # 89 天提示线
IGN_GAIN, IGN_LOOKBACK, IGN_GAP, D0_WINDOW = 0.15, 10, 45, 7
D0_INCLUDE_IGNITION = True
STOP_RATIO = 0.90
T_TRIM, T_CLOSING, T_CLEAR = 24, 28, 30
FETCH_FROM = "2017-08-17"            # 币安 BTCUSDT 日线最早一天
EARLY_FROM, EARLY_TO = "2010-07-18", "2017-08-16"   # 之前用 Coin Metrics
CM_URL = ("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD"
          "&frequency=1d&start_time={a}&end_time={b}&page_size=10000")
HOSTS = ["https://data-api.binance.vision", "https://api.binance.com", "https://api1.binance.com"]
EPS = 1e-9


def _ge(c, x):  # c >= x（带浮点容差；THR_EQ=False 时改为严格大于）
    return c >= x * (1 - EPS) if THR_EQ else c > x * (1 + EPS)


def _le(c, x):
    return c <= x * (1 + EPS) if THR_EQ else c < x * (1 - EPS)


# ---------------------------- 取数 ----------------------------
def _get(url, tries=3):
    last = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "leg-data/1.0"}), timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa
            last = e
            time.sleep(1.5 * (k + 1))
    raise last


def fetch_daily():
    """返回 (dates[date], closes[float])，只含已收盘的日线。"""
    start_ms = int(dt.datetime.strptime(FETCH_FROM, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    now_ms = int(time.time() * 1000)
    err = None
    for host in HOSTS:
        try:
            rows, cur = [], start_ms
            while True:
                data = _get(f"{host}/api/v3/klines?symbol=BTCUSDT&interval=1d&startTime={cur}&limit=1000")
                if not data:
                    break
                rows += data
                cur = data[-1][0] + 86400000
                if len(data) < 1000 or cur > now_ms:
                    break
            rows = [r for r in rows if r[6] < now_ms]            # 丢掉未收盘的那根
            dates = [dt.datetime.fromtimestamp(r[0] / 1000, dt.timezone.utc).date() for r in rows]
            closes = [float(r[4]) for r in rows]
            if len(closes) > 1000:
                return dates, closes
        except Exception as e:  # noqa
            err = e
    raise RuntimeError(f"币安日线取数失败：{err}")


def _cache_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "leg_early_cache.csv")


def fetch_early():
    """2010-07-18 ~ 2017-08-16 的 Coin Metrics 日线收盘（PriceUSD）。有缓存直接用；取到后自动存缓存。"""
    cp = _cache_path()
    if os.path.exists(cp):
        d, c = load_csv(cp)
        if len(c) > 2000:
            return d, c
    data = _get(CM_URL.format(a=EARLY_FROM, b=EARLY_TO))
    rows = [(dt.date.fromisoformat(r["time"][:10]), float(r["PriceUSD"])) for r in data.get("data", []) if r.get("PriceUSD")]
    rows.sort()
    if len(rows) < 2000:
        raise RuntimeError(f"Coin Metrics 只返回 {len(rows)} 天，早期历史不完整")
    with open(cp + ".tmp", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "close"])
        for d, c in rows:
            w.writerow([d.isoformat(), c])
    os.replace(cp + ".tmp", cp)
    return [r[0] for r in rows], [r[1] for r in rows]


def fetch_all(early=True):
    """全历史 = 早期（Coin Metrics）+ 币安。早期取不到时退回只用币安，并返回 coverage='partial'。"""
    bd, bc = fetch_daily()
    if not early:
        return bd, bc, "partial"
    try:
        ed, ec = fetch_early()
    except Exception as e:  # noqa
        print(f"⚠ 早期历史（Coin Metrics）取数失败：{e}\n  → 只用币安 2017-08 起的数据；leg_history.json 会标注 coverage=partial，统计和文档的 305 条腿对不上是正常的", file=sys.stderr)
        return bd, bc, "partial"
    keep = [(d, c) for d, c in zip(ed, ec) if d < bd[0]]
    return [k[0] for k in keep] + bd, [k[1] for k in keep] + bc, "full"


def load_csv(path):
    dates, closes = [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            dates.append(dt.date.fromisoformat(row["date"][:10]))
            closes.append(float(row["close"]))
    return dates, closes


# ---------------------------- 涨腿 ----------------------------
def scan_legs(closes):
    """10% 反向确认的折线扫描。返回 dict(mode, up_start, hi_i, legs[(dir,start,end)])"""
    n = len(closes)
    lo_i = hi_i = 0
    mode, up_start, down_start, legs = None, None, None, []
    for i in range(1, n):
        c = closes[i]
        if mode is None:
            if _ge(c, closes[lo_i] * (1 + THR)):
                mode, up_start, hi_i = "up", lo_i, i
            elif _le(c, closes[hi_i] * (1 - THR)):
                mode, down_start, lo_i = "down", hi_i, i
            else:
                if c < closes[lo_i]:
                    lo_i = i
                if c > closes[hi_i]:
                    hi_i = i
        elif mode == "up":
            if c > closes[hi_i]:
                hi_i = i
            elif _le(c, closes[hi_i] * (1 - THR)):
                legs.append(("up", up_start, hi_i))
                mode, down_start, lo_i = "down", hi_i, i
        else:
            if c < closes[lo_i]:
                lo_i = i
            elif _ge(c, closes[lo_i] * (1 + THR)):
                legs.append(("down", down_start, lo_i))
                mode, up_start, hi_i = "up", lo_i, i
    return {"mode": mode, "up_start": up_start, "hi_i": hi_i, "down_start": down_start, "lo_i": lo_i, "legs": legs}


def _confirm_idx(direction, closes, s):
    """起点 s 之后第一次满足 10% 反向确认的那天（up：收盘 ≥ 起点×1.1；down：收盘 ≤ 起点×0.9）。"""
    n = len(closes)
    if direction == "up":
        return next((j for j in range(s + 1, n) if _ge(closes[j], closes[s] * (1 + THR))), None)
    return next((j for j in range(s + 1, n) if _le(closes[j], closes[s] * (1 - THR))), None)


def _leg_rec(direction, dates, closes, s, e, ongoing=False):
    c = _confirm_idx(direction, closes, s)
    return {"dir": direction, "start_date": dates[s].isoformat(), "end_date": dates[e].isoformat(),
            "confirm_date": dates[c].isoformat() if c is not None else None,
            "start_close": round(closes[s], 2), "end_close": round(closes[e], 2),
            "days": (dates[e] - dates[s]).days,
            "pct": round((closes[e] / closes[s] - 1) * 100, 1), "ongoing": ongoing}


def _prev_leg(st, dates, closes, want):
    for d, s, e in reversed(st["legs"]):
        if d == want:
            r = _leg_rec(d, dates, closes, s, e)
            return {k: r[k] for k in ("dir", "start_date", "end_date", "days", "pct")}
    return None


def btc_leg_block(dates, closes):
    """BTC 当前这一腿。direction: up / down / none（none 只在历史不足 10% 摆动时出现）。"""
    st = scan_legs(closes)
    n = len(closes)
    if st["mode"] == "up":
        s, h = st["up_start"], st["hi_i"]
        confirm = _confirm_idx("up", closes, s)
        runmax, max_dd, max_dd_i = closes[s], 0.0, s
        for j in range(s, n):
            runmax = max(runmax, closes[j])
            dd = (runmax - closes[j]) / runmax
            if dd > max_dd + 1e-12:
                max_dd, max_dd_i = dd, j
        day = (dates[-1] - dates[s]).days
        leg = {"start_date": dates[s].isoformat(), "start_close": round(closes[s], 2),
               "confirm_date": dates[confirm].isoformat(), "day": day,
               "gain_pct": round((closes[h] / closes[s] - 1) * 100, 1),
               "high_close": round(closes[h], 2), "high_date": dates[h].isoformat(),
               "max_dd_pct": round(max_dd * 100, 1), "max_dd_date": dates[max_dd_i].isoformat()}
        badge = {"zh": "多头只减不加", "en": "Longs: trim only"} if day > LINE_DAYS else None
        return {"direction": "up", "leg": leg, "badge": badge, "prev_leg": _prev_leg(st, dates, closes, "down")}
    if st["mode"] == "down":
        s, lo = st["down_start"], st["lo_i"]
        confirm = _confirm_idx("down", closes, s)
        rev = closes[lo] * (1 + THR)
        leg = {"start_date": dates[s].isoformat(), "start_close": round(closes[s], 2),
               "confirm_date": dates[confirm].isoformat(), "day": (dates[-1] - dates[s]).days,
               "drop_pct": round((closes[s] - closes[lo]) / closes[s] * 100, 1),
               "low_close": round(closes[lo], 2), "low_date": dates[lo].isoformat(),
               "btc_close": round(closes[-1], 2),
               "from_peak_pct": round((closes[-1] / closes[s] - 1) * 100, 1),
               "reversal_line": round(rev, 2),
               "to_reversal_pct": round((rev / closes[-1] - 1) * 100, 1)}
        return {"direction": "down", "leg": leg, "badge": None, "prev_leg": _prev_leg(st, dates, closes, "up")}
    return {"direction": "none", "leg": None, "badge": None, "prev_leg": None}


# ---------------------------- 牛熊标注（周期口径，移植自 leg_rules_backtest.py） ----------------------------
def cycle_regime(days, close):
    """周期口径：顶 = 之后 365 天内没被超过的历史新高（数据末尾不足 365 天但已过 267 天且没被超过，也算顶，标“暂定”）；
    底 = 顶之后到下一次突破该顶之前的最低收盘。顶→底之间每天算 bear，其余算 bull。
    注意这是事后口径（要等底部走出来才知道），所以只用来给历史腿分类、算分布，不能当实时信号。"""
    n = len(days)
    ath_idx, m = [], -1
    for i in range(n):
        if close[i] > m:
            m = close[i]
            ath_idx.append(i)
    tops = []
    for k, i in enumerate(ath_idx):
        nxt = ath_idx[k + 1] if k + 1 < len(ath_idx) else None
        gap = (days[nxt] - days[i]).days if nxt is not None else (days[-1] - days[i]).days
        if nxt is None:
            if gap >= 267:
                tops.append((i, True))
        elif gap > 365:
            tops.append((i, False))
    reg = ["bull"] * n
    marks = []
    for ti, provisional in tops:
        end = n
        for j in range(ti + 1, n):
            if close[j] > close[ti]:
                end = j
                break
        bi = min(range(ti + 1, end), key=lambda j: close[j]) if end > ti + 1 else ti
        for j in range(ti + 1, bi + 1):
            reg[j] = "bear"
        marks.append((ti, bi, provisional))
    return reg, marks


# ---------------------------- 历史：逐条涨腿/跌腿 + 分布 ----------------------------
def _quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def _stats(xs):
    if not xs:
        return None
    return {"p25": round(_quantile(xs, .25), 1), "p50": round(_quantile(xs, .5), 1), "p75": round(_quantile(xs, .75), 1),
            "p90": round(_quantile(xs, .9), 1), "max": round(max(xs), 1)}


def history_block(dates, closes, coverage="full"):
    """全部已走完的涨腿/跌腿逐条记录；每条带牛熊标注（周期口径，按腿的终点日归类）。
    summary.all = 不分牛熊；summary.by_regime = 牛/熊 × 涨/跌 四组。分位数插值法同 numpy 默认。"""
    st = scan_legs(closes)
    reg, marks = cycle_regime(dates, closes)
    idx = {d: i for i, d in enumerate(dates)}
    legs = []
    for d, s_, e_ in st["legs"]:
        r = _leg_rec(d, dates, closes, s_, e_)
        r["regime"] = reg[e_]
        legs.append(r)
    cur = None
    if st["mode"] == "up":
        cur = _leg_rec("up", dates, closes, st["up_start"], st["hi_i"], ongoing=True)
    elif st["mode"] == "down":
        cur = _leg_rec("down", dates, closes, st["down_start"], st["lo_i"], ongoing=True)

    def grp(sel):
        ups = [l for l in sel if l["dir"] == "up"]
        downs = [l for l in sel if l["dir"] == "down"]
        return {"up": {"n": len(ups), "days": _stats([l["days"] for l in ups]), "gain_pct": _stats([l["pct"] for l in ups])},
                "down": {"n": len(downs), "days": _stats([l["days"] for l in downs]), "drop_pct": _stats([-l["pct"] for l in downs])}}

    allg = grp(legs)
    return {"schema": 2,
            "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "asof": dates[-1].isoformat(),
            "coverage": {"mode": coverage, "from": dates[0].isoformat(), "to": dates[-1].isoformat(), "days": len(dates)},
            "threshold_pct": THR * 100,
            "regime_basis": "周期口径：顶=之后365天没被超过的历史新高，底=顶之后到下一次突破前的最低收盘；顶→底算熊，其余算牛；按腿的终点日归类。事后口径，只用于分类历史，不是实时信号。",
            "regime_now": reg[-1],
            "cycles": [{"top_date": dates[t].isoformat(), "top_close": round(closes[t], 2), "bottom_date": dates[b_].isoformat(),
                        "bottom_close": round(closes[b_], 2), "provisional": pv} for t, b_, pv in marks],
            "note": "days = 起点日到终点日的日历天数；pct 涨腿为正、跌腿为负；ongoing=true 是还没走完的当前这一腿（不进统计）。",
            "summary": {"completed_legs": len(legs), "total_legs_incl_current": len(legs) + (1 if cur else 0),
                        "up": allg["up"], "down": allg["down"],
                        "by_regime": {"bull": grp([l for l in legs if l["regime"] == "bull"]),
                                      "bear": grp([l for l in legs if l["regime"] == "bear"])}},
            "legs": legs, "current": cur}


# ---------------------------- 山寨轮动窗口 ----------------------------
def find_ignitions(closes):
    ign, last = [], None
    for i in range(IGN_LOOKBACK, len(closes)):
        if closes[i] / closes[i - IGN_LOOKBACK] - 1 >= IGN_GAIN - EPS and (last is None or i - last >= IGN_GAP):
            ign.append(i)
            last = i
    return ign


def alt_window_block(dates, closes):
    n = len(closes)
    base = {"stage": "idle", "ignition_date": None, "d0_date": None, "d0_close": None, "n": None,
            "days_to_clear": None, "clear_date": None, "stop_line": None, "stopped_date": None,
            "btc_close": round(closes[-1], 2), "btc_vs_stop_pct": None}
    ign = find_ignitions(closes)
    if not ign:
        return base
    i0 = ign[-1]
    base["ignition_date"] = dates[i0].isoformat()
    lo = i0 if D0_INCLUDE_IGNITION else i0 + 1
    hi = min(i0 + D0_WINDOW, n - 1)
    d0 = max(range(lo, hi + 1), key=lambda j: (closes[j], -j))     # 并列取最早
    base.update({"d0_date": dates[d0].isoformat(), "d0_close": round(closes[d0], 2)})
    if (n - 1) < i0 + D0_WINDOW:
        base["stage"] = "pending"                                  # D0 还没定（临时值）
        return base
    N = (n - 1) - d0
    stop_line = closes[d0] * STOP_RATIO
    stopped = next((j for j in range(d0 + 1, min(n - 1, d0 + T_CLEAR) + 1) if closes[j] < stop_line - EPS), None)
    base.update({"n": N, "days_to_clear": max(0, T_CLEAR - N),
                 "clear_date": (dates[d0] + dt.timedelta(days=T_CLEAR)).isoformat(),
                 "stop_line": round(stop_line, 2),
                 "stopped_date": dates[stopped].isoformat() if stopped is not None else None,
                 "btc_vs_stop_pct": round((closes[-1] / stop_line - 1) * 100, 1)})
    if N >= T_CLEAR:
        base["stage"] = "cleared"
    elif stopped is not None:
        base["stage"] = "stopped"
    elif N >= T_CLOSING:
        base["stage"] = "closing"
    elif N >= T_TRIM:
        base["stage"] = "trim"
    else:
        base["stage"] = "build"
    return base


# ---------------------------- 主流程 ----------------------------
def build(dates, closes):
    for a, b in zip(dates, dates[1:]):
        if (b - a).days != 1:
            print(f"⚠ 日线不连续：{a} → {b}，天数计算可能偏差", file=sys.stderr)
            break
    return {"schema": 3,
            "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "asof": dates[-1].isoformat(),
            "source": "Coin Metrics PriceUSD (2010-07-18~2017-08-16) + Binance spot BTCUSDT 1d (2017-08-17~, closed candles, UTC)",
            "btc_leg": btc_leg_block(dates, closes),
            "alt_window": alt_window_block(dates, closes)}


def save(obj, kind="latest"):
    env, name = ("LEG_OUT", "leg_latest.json") if kind == "latest" else ("LEG_HIST_OUT", "leg_history.json")
    path = os.environ.get(env) or os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if kind == "latest":
            json.dump(obj, f, ensure_ascii=False, indent=2)
        else:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)
    return path


def summarize(o, h=None):
    b, a = o["btc_leg"], o["alt_window"]
    print(f"数据截至 {o['asof']}")
    L = b["leg"]
    if b["direction"] == "up":
        print(f"[BTC 涨腿] 起点 {L['start_date']} 收 {L['start_close']:,.2f}（{L['confirm_date']} 确认） 第 {L['day']} 天  "
              f"+{L['gain_pct']}%（最高收盘 {L['high_close']:,.2f} @ {L['high_date']}）  腿内最大回撤 {L['max_dd_pct']}%（{L['max_dd_date']}）  徽章={b['badge']['zh'] if b['badge'] else '无'}")
    elif b["direction"] == "down":
        print(f"[BTC 跌腿] 起点（高点）{L['start_date']} 收 {L['start_close']:,.2f}（{L['confirm_date']} 确认） 第 {L['day']} 天  "
              f"−{L['drop_pct']}%（最低收盘 {L['low_close']:,.2f} @ {L['low_date']}）  现价 {L['btc_close']:,.2f}（距高点 {L['from_peak_pct']}%）  "
              f"反弹确认线 {L['reversal_line']:,.2f}（距现价 +{L['to_reversal_pct']}%）")
    else:
        print("[BTC] 历史不足 10% 摆动，方向未定")
    print(f"        上一腿：{b['prev_leg']}")
    print(f"[山寨窗口] stage={a['stage']} 点火={a['ignition_date']} D0={a['d0_date']} N={a['n']} 距清零={a['days_to_clear']} "
          f"提前关闭={a['stopped_date']} 关闭线={a['stop_line']}")
    if h:
        sm, cv = h["summary"], h["coverage"]
        print(f"[历史] {cv['from']} ~ {cv['to']}，{cv['days']} 天（{cv['mode']}）；已走完 {sm['completed_legs']} 条腿"
              f"（含当前这条共 {sm['total_legs_incl_current']}）；涨腿 {sm['up']['n']} 条，跌腿 {sm['down']['n']} 条")
        print(f"        涨腿天数 {sm['up']['days']}")
        print(f"        跌腿天数 {sm['down']['days']}  跌幅% {sm['down']['drop_pct']}")
        br = sm["by_regime"]
        print("        牛熊拆开（周期口径）：" + "；".join(f"{'牛' if r=='bull' else '熊'}市 涨{br[r]['up']['n']}/跌{br[r]['down']['n']}" for r in ('bull', 'bear')) + f"；今天归类={h['regime_now']}")
        print("        核对：--asof 2026-09-27 时应为 5,916 天、已走完 305 条腿；牛市涨 103 / 牛市跌 99 / 熊市涨 49 / 熊市跌 54")


# ---------------------------- 自测（合成数据，离线） ----------------------------
def _d(i):
    return dt.date(2026, 1, 1) + dt.timedelta(days=i)


def selftest():
    # 1) 涨腿：100 → 90（确认下跌腿）→ 99（≥90×1.1，确认涨腿，起点=90）→ 120 → 112/110 → 108（回落10%，结束）
    c = [100, 90, 99, 105, 120, 112, 110]
    dates = [_d(i) for i in range(len(c))]
    r = btc_leg_block(dates, c)
    L = r["leg"]
    assert r["direction"] == "up" and L["start_date"] == _d(1).isoformat() and L["start_close"] == 90.0, r
    assert L["confirm_date"] == _d(2).isoformat() and L["day"] == 5, L
    assert L["gain_pct"] == 33.3 and L["high_close"] == 120.0 and L["high_date"] == _d(4).isoformat(), L
    assert L["max_dd_pct"] == 8.3 and L["max_dd_date"] == _d(6).isoformat(), L
    assert r["badge"] is None
    c2 = c + [108]
    r2 = btc_leg_block([_d(i) for i in range(len(c2))], c2)
    # 涨腿结束 → 当前就是跌腿（起点=腿顶日 _d(4)，收 120，07 确认；最低收盘 108）
    assert r2["direction"] == "down", r2
    D = r2["leg"]
    assert D["start_date"] == _d(4).isoformat() and D["start_close"] == 120.0 and D["confirm_date"] == _d(7).isoformat(), D
    assert D["day"] == 3 and D["drop_pct"] == 10.0 and D["low_close"] == 108.0 and D["from_peak_pct"] == -10.0, D
    assert D["reversal_line"] == 118.8 and D["to_reversal_pct"] == 10.0, D
    assert r2["prev_leg"]["dir"] == "up" and r2["prev_leg"]["days"] == 3 and r2["prev_leg"]["pct"] == 33.3, r2
    # 跌腿里继续创新低，反弹线跟着下移；反弹 ≥10% → 回到涨腿，起点 = 最低点
    c_dn = c2 + [100]
    Dn = btc_leg_block([_d(i) for i in range(len(c_dn))], c_dn)["leg"]
    assert Dn["low_close"] == 100.0 and Dn["drop_pct"] == 16.7 and Dn["reversal_line"] == 110.0, Dn
    c_rb = c_dn + [105, 110]
    Rb = btc_leg_block([_d(i) for i in range(len(c_rb))], c_rb)
    assert Rb["direction"] == "up" and Rb["leg"]["start_close"] == 100.0 and Rb["leg"]["confirm_date"] == _d(10).isoformat(), Rb
    assert Rb["prev_leg"]["dir"] == "down" and Rb["prev_leg"]["pct"] == -16.7, Rb
    # 历史：已走完的腿逐条（up 90→120；down 120→100），当前 up 进行中
    H = history_block([_d(i) for i in range(len(c_rb))], c_rb)
    assert [l["dir"] for l in H["legs"]] == ["down", "up", "down"] and H["current"]["dir"] == "up" and H["current"]["ongoing"], H["legs"]
    assert H["summary"]["up"]["n"] == 1 and H["summary"]["down"]["n"] == 2 and H["summary"]["completed_legs"] == 3, H["summary"]
    # 腿内回撤没到10% → 仍在继续
    c3 = c + [109]
    assert btc_leg_block([_d(i) for i in range(len(c3))], c3)["direction"] == "up"
    # 2) 徽章：天数 > 89 才亮
    long_c = [100, 90, 99] + [100 + k * 0.5 for k in range(1, 100)]
    dts = [_d(i) for i in range(len(long_c))]
    for cut, expect in ((91, None), (92, "多头只减不加")):       # day = idx-1：idx90 → day 89；idx91 → day 90
        r = btc_leg_block(dts[:cut], long_c[:cut])
        got = r["badge"]["zh"] if r["badge"] else None
        assert r["leg"]["day"] == cut - 2 and got == expect, (cut, r["leg"]["day"], got)
    # 3) 山寨窗口：平 → 急拉 → D0 → 阶段边界
    base = [100.0] * 20
    ramp = [104, 108, 112, 116, 120, 118, 119, 118, 118, 118]          # i=20..29；i=23 收 116，10 天前收 100 → 点火
    flat = [118.0] * 60
    c = base + ramp + flat
    dates = [_d(i) for i in range(len(c))]
    ign = find_ignitions(c)
    assert ign == [23], ign
    d0_idx = max(range(23, 31), key=lambda j: (c[j], -j))              # 点火日起 7 天内（含点火日）最高收盘 120 → i=24
    assert d0_idx == 24 and c[d0_idx] == 120, d0_idx
    pend = alt_window_block(dates[:28], c[:28])
    assert pend["stage"] == "pending" and pend["d0_date"] == _d(d0_idx).isoformat(), pend
    # D0 要等点火后 7 天走完才定：最早在 i=30 确定，此时 N=6；之前一天（i=29）仍是 pending
    assert alt_window_block(dates[:30], c[:30])["stage"] == "pending"
    for N, st in ((6, "build"), (23, "build"), (24, "trim"), (27, "trim"), (28, "closing"), (29, "closing"), (30, "cleared"), (45, "cleared")):
        k = d0_idx + N + 1
        r = alt_window_block(dates[:k], c[:k])
        assert r["stage"] == st and r["n"] == N and r["days_to_clear"] == max(0, 30 - N), (N, r)
    # 4) 提前关闭：D0=120，关闭线108；N=10 时收盘 107
    c_stop = list(c)
    c_stop[d0_idx + 10] = 107
    r = alt_window_block(dates[:d0_idx + 16], c_stop[:d0_idx + 16])
    assert r["stage"] == "stopped" and r["stopped_date"] == _d(d0_idx + 10).isoformat() and r["stop_line"] == 108.0, r
    r = alt_window_block(dates[:d0_idx + 31], c_stop[:d0_idx + 31])
    assert r["stage"] == "cleared" and r["stopped_date"] is not None, r
    # 5) 45 天内第二次急拉不重复计
    c_two = base + ramp + [118.0] * 5 + [130, 140, 150] + [150.0] * 10
    assert len(find_ignitions(c_two)) == 1
    # 6) 无点火 → idle
    assert alt_window_block([_d(i) for i in range(40)], [100.0] * 40)["stage"] == "idle"
    print("selftest OK：涨腿 起点确认/回撤/结束/徽章边界；跌腿 起点/跌幅/反弹确认线/回到涨腿；历史逐条；山寨窗口 pending/build/trim/closing/cleared/stopped/idle/去重")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof")
    ap.add_argument("--csv")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--no-early", action="store_true", help="不取 2010~2017 的 Coin Metrics 早期历史，只用币安")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        sys.exit(0)
    coverage = "full"
    if a.csv:
        dates, closes = load_csv(a.csv)
    else:
        dates, closes, coverage = fetch_all(early=not a.no_early)
    if a.asof:
        cut = dt.date.fromisoformat(a.asof)
        pairs = [(d, c) for d, c in zip(dates, closes) if d <= cut]
        dates, closes = [p[0] for p in pairs], [p[1] for p in pairs]
    out = build(dates, closes)
    hist = history_block(dates, closes, coverage)
    summarize(out, hist)
    print("已保存：", save(out, "latest"))
    print("已保存：", save(hist, "history"))

"""
ACCEPTANCE —— 上线前必须用 --asof 回放，和海报当时的读数逐项核对（不一致就先别上线，把差异告诉站长）
  python3 leg_data.py --asof 2026-09-27
      期望：起点 2026-06-30 收 58,624.71，2026-07-14 确认；第 89 天；+47.8%；
            最高收盘 86,620.00 @ 2026-09-21；腿内最大回撤 6.9% @ 2026-09-15；徽章=无（第 90 天起才亮）
  python3 leg_data.py --asof 2026-09-28        期望：第 90 天，徽章「多头只减不加」
  python3 leg_data.py --asof 2026-09-26        期望：山寨窗口 stage=cleared，D0=2026-08-27（D0+30=09-26）
  python3 leg_data.py --asof 2026-09-25        期望：stage=closing，N=29
  python3 leg_data.py --asof 2026-09-27   的历史部分：应显示「5,916 天」、已走完 305 条腿（已用 Polar 原件 leg_rules_legs.csv 逐条核对过，305 条的起止日期和天数全部一致）；牛熊拆开：牛市涨 103 / 牛市跌 99 / 熊市涨 49 / 熊市跌 54
  python3 leg_data.py（今天）  期望：BTC 当前是跌腿，起点 = 2026-09-21 收 86,620.00（回落到 ≤77,958 的那天确认）；上一腿 = 涨腿 06-30→09-21，83 天，+47.8%
  若 D0 差一天 → 改 D0_INCLUDE_IGNITION；若涨腿起点/确认日差一天 → 改 THR_EQ；
  以海报当时实际显示的数字为准，不是以本脚本为准。
"""
