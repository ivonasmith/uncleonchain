#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
leg_data.py —— 网站「涨腿追踪 + 山寨轮动窗口」的数据文件生成器（schema 2）

用法（零配置，直接跑）：
    python3 leg_data.py                  # 拉币安日线，算两块读数，自动保存 leg_latest.json 到本脚本所在文件夹
    python3 leg_data.py --asof 2026-09-27   # 回放：只用到这一天的收盘，用来和当天海报核对
    python3 leg_data.py --selftest       # 离线自测（合成数据），不联网
    python3 leg_data.py --csv 日线.csv   # 离线：用 date,close 两列的 csv，不联网

输出文件：leg_latest.json（与本脚本同一文件夹；环境变量 LEG_OUT 可改路径）。
口径：只用已收盘的 UTC 日线收盘价（币安现货 BTCUSDT），当天未收盘的那根不算。

规则全部来自《加密行情律动-规律清单》V13 / 《山寨补涨板块轮动预警框架》V4 / 《热币分析操作规格》v6.5：
  涨腿：收盘从摆动低点反向走出 10%，才确认该低点是涨腿起点；起点确认后天数/涨幅每天重算；
        收盘从高点回落 10%，这一轮结束。腿内最大回撤 = 腿内「当时的最高收盘 → 之后收盘」的最大回落。
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
FETCH_FROM = "2017-08-17"
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
    return {"mode": mode, "up_start": up_start, "hi_i": hi_i, "legs": legs}


def btc_leg_block(dates, closes):
    st = scan_legs(closes)
    n = len(closes)
    if st["mode"] != "up":
        ups = [l for l in st["legs"] if l[0] == "up"]
        last = None
        if ups:
            _, s, e = ups[-1]
            last = {"start_date": dates[s].isoformat(), "end_date": dates[e].isoformat(),
                    "days": (dates[e] - dates[s]).days, "gain_pct": round((closes[e] / closes[s] - 1) * 100, 1)}
        return {"status": "none", "leg": None, "badge": None, "last_leg": last}
    s, h = st["up_start"], st["hi_i"]
    confirm = next(j for j in range(s + 1, n) if _ge(closes[j], closes[s] * (1 + THR)))
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
    return {"status": "active", "leg": leg, "badge": badge, "last_leg": None}


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
    return {"schema": 2,
            "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "asof": dates[-1].isoformat(),
            "source": "Binance spot BTCUSDT 1d (closed candles, UTC)",
            "btc_leg": btc_leg_block(dates, closes),
            "alt_window": alt_window_block(dates, closes)}


def save(obj):
    path = os.environ.get("LEG_OUT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "leg_latest.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def summarize(o):
    b, a = o["btc_leg"], o["alt_window"]
    print(f"数据截至 {o['asof']}")
    if b["status"] == "active":
        L = b["leg"]
        print(f"[BTC涨腿] 起点 {L['start_date']} 收 {L['start_close']:,.2f}（{L['confirm_date']} 确认） 第 {L['day']} 天  "
              f"+{L['gain_pct']}%（最高收盘 {L['high_close']:,.2f} @ {L['high_date']}）  腿内最大回撤 {L['max_dd_pct']}%（{L['max_dd_date']}）  徽章={b['badge']['zh'] if b['badge'] else '无'}")
    else:
        print(f"[BTC涨腿] 当前没有进行中的涨腿；上一轮 {b['last_leg']}")
    print(f"[山寨窗口] stage={a['stage']} 点火={a['ignition_date']} D0={a['d0_date']} N={a['n']} 距清零={a['days_to_clear']} "
          f"提前关闭={a['stopped_date']} 关闭线={a['stop_line']}")


# ---------------------------- 自测（合成数据，离线） ----------------------------
def _d(i):
    return dt.date(2026, 1, 1) + dt.timedelta(days=i)


def selftest():
    # 1) 涨腿：100 → 90（确认下跌腿）→ 99（≥90×1.1，确认涨腿，起点=90）→ 120 → 112/110 → 108（回落10%，结束）
    c = [100, 90, 99, 105, 120, 112, 110]
    dates = [_d(i) for i in range(len(c))]
    r = btc_leg_block(dates, c)
    L = r["leg"]
    assert r["status"] == "active" and L["start_date"] == _d(1).isoformat() and L["start_close"] == 90.0, r
    assert L["confirm_date"] == _d(2).isoformat() and L["day"] == 5, L
    assert L["gain_pct"] == 33.3 and L["high_close"] == 120.0 and L["high_date"] == _d(4).isoformat(), L
    assert L["max_dd_pct"] == 8.3 and L["max_dd_date"] == _d(6).isoformat(), L
    assert r["badge"] is None
    c2 = c + [108]
    r2 = btc_leg_block([_d(i) for i in range(len(c2))], c2)
    assert r2["status"] == "none" and r2["last_leg"]["days"] == 3 and r2["last_leg"]["gain_pct"] == 33.3, r2
    # 腿内回撤没到10% → 仍在继续
    c3 = c + [109]
    assert btc_leg_block([_d(i) for i in range(len(c3))], c3)["status"] == "active"
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
    print("selftest OK：涨腿 起点确认/回撤/结束/徽章边界；山寨窗口 pending/build/trim/closing/cleared/stopped/idle/去重")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof")
    ap.add_argument("--csv")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        sys.exit(0)
    dates, closes = load_csv(a.csv) if a.csv else fetch_daily()
    if a.asof:
        cut = dt.date.fromisoformat(a.asof)
        pairs = [(d, c) for d, c in zip(dates, closes) if d <= cut]
        dates, closes = [p[0] for p in pairs], [p[1] for p in pairs]
    out = build(dates, closes)
    summarize(out)
    print("已保存：", save(out))

"""
ACCEPTANCE —— 上线前必须用 --asof 回放，和海报当时的读数逐项核对（不一致就先别上线，把差异告诉站长）
  python3 leg_data.py --asof 2026-09-27
      期望：起点 2026-06-30 收 58,624.71，2026-07-14 确认；第 89 天；+47.8%；
            最高收盘 86,620.00 @ 2026-09-21；腿内最大回撤 6.9% @ 2026-09-15；徽章=无（第 90 天起才亮）
  python3 leg_data.py --asof 2026-09-28        期望：第 90 天，徽章「多头只减不加」
  python3 leg_data.py --asof 2026-09-26        期望：山寨窗口 stage=cleared，D0=2026-08-27（D0+30=09-26）
  python3 leg_data.py --asof 2026-09-25        期望：stage=closing，N=29
  若 D0 差一天 → 改 D0_INCLUDE_IGNITION；若涨腿起点/确认日差一天 → 改 THR_EQ；
  以海报当时实际显示的数字为准，不是以本脚本为准。
"""
