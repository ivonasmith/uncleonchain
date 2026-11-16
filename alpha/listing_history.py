#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交易所全历史上币复盘（先做 Binance 现货）：拉全部交易对（含已下架），第一根日线 = 上币日，
算上线后 7 / 30 / 90 天回报和 BTC 超额，按 BTC 牛熊周期、涨跌腿、L2 状态分组。口径见 alpha/research/交易所上币回报研究.md。

做法（大叔 11-16 定：直接拉交易所所有币种的数据）：
  1. 币种全集 = 币安官方归档 data.binance.vision 的现货月度 K 线目录（含已下架的币，没有幸存者偏差）。
  2. 每个交易对的第一根日线：还在交易的走 data-api.binance.vision（startTime=0），已下架的读归档目录里最早的月文件。
  3. 一个币的上币日 = 它所有交易对（USDT / BUSD / USDC / FDUSD / TUSD / BTC / ETH / BNB 计价）里最早的那根。
     早期很多币先上 BTC 对，BTC / ETH / BNB 计价的价格用当天该币的 USDT 收盘价换算成美元。
  4. 起点（主口径，大叔 11-17 定）= 开盘后第 15 分钟的收盘价（普通用户开盘 15 分钟内能买到）；另列开盘 1 小时收盘价作对照；
     第一笔开盘价只作上限读数。开盘时刻 = 上币当天第一根 1 分钟 K 线。回报 = 第 7 / 30 / 90 天日线收盘相对起点；
     90 天内最高点涨幅和出现在第几天；BTC 同期涨跌和超额。
  5. 分组：上币日处在哪条 BTC 涨 / 跌腿、牛 / 熊阶段（data/leg/leg_history.json，事后划分：腿的起止是走完才确认的）；
     另给「当时已确认的腿」（confirm_date ≤ 上币日的最近一条，交易时实际能知道的）；L2 状态（data/l2/l2_series.json，状态机有确认滞后，比如 2021-05 大跌后到 11 月才翻回牛市）；年份。
     90 天最高点按日收盘价取（不用日内最高价，避开冷门交易对的插针），不含上币当天。
剔除：杠杆代币（UP / DOWN / BULL / BEAR）、稳定币、法币、2026-06-11 起 B 结尾的代币化股票（项目规则）、交易所开张头两周的首批币。
已知偏差：改名 / 迁移（如 MATIC→POL）会被当成新币（标 rename_suspect，待名单剔除）；首日 K 线可能不满 24 小时。
输出 data/alpha/listing_history_binance.json（逐币）+ listing_regime_stats.json（分组统计）。缓存 data/alpha/cache_listing_first.json。
用法：python3 alpha/listing_history.py [--limit N]
"""
import bisect, csv, datetime as dt, io, json, os, re, statistics as st, sys, time, urllib.error, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.environ.get("LP_DATA", os.path.join(ROOT, "data"))
OUT = os.path.join(DATA, "alpha")
CACHE = os.path.join(OUT, "cache_listing_first.json")
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix={p}&marker={m}"
KL = "https://data-api.binance.vision/api/v3/klines?symbol={s}&interval=1d&startTime={t}&limit={n}"
ZIP = "https://data.binance.vision/data/spot/monthly/klines/{s}/1d/{s}-1d-{ym}.zip"
USDQ = ("USDT", "BUSD", "USDC", "FDUSD", "TUSD")
CRYPTOQ = ("BTC", "ETH", "BNB")
QUOTES = sorted(USDQ + CRYPTOQ + ("TRY", "EUR", "BRL", "GBP", "AUD", "RUB", "UAH", "NGN", "ZAR", "BIDR", "IDRT", "BKRW", "DAI", "PAX", "USDP", "USDS", "VAI", "XRP", "TRX", "DOGE", "DOT", "JPY", "PLN", "RON", "ARS", "COP", "MXN", "CZK", "AEUR", "UST", "GYEN", "BVND", "USD1", "U"), key=len, reverse=True)
STABLE = {"USDT", "BUSD", "USDC", "FDUSD", "TUSD", "USDP", "PAX", "DAI", "USDS", "USDSB", "SUSD", "UST", "USTC", "EUR", "AEUR", "EURI", "GBP", "AUD", "TRY", "BRL", "RUB", "BIDR", "IDRT", "BKRW", "GYEN", "BVND", "VAI", "USD1", "XUSD", "RLUSD", "U", "PYUSD", "USDE", "BFUSD"}
LAUNCH_END = "2017-07-28"   # 币安 2017-07-14 开张，头两周的首批币不算「新上币」
STOCK_FROM = "2026-06-11"
WINDOWS = (7, 30, 90)
STATE_NAMES = ["BULL", "BULL_RISK", "BULL_PULLBACK", "BEAR", "BEAR_ZONE", "RECOVERY"]


def get(url, raw=False, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=40) as r:
                b = r.read()
            return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            time.sleep(1 + 2 * i)
        except Exception:
            time.sleep(1 + 2 * i)
    return None


def s3_list(prefix):
    """S3 目录：返回 (子目录, 文件 key) 两个列表"""
    dirs, keys, marker = [], [], ""
    while True:
        b = get(S3.format(p=prefix, m=marker), raw=True)
        if not b:
            break
        x = b.decode("utf-8", "replace")
        dirs += re.findall(r"<CommonPrefixes><Prefix>([^<]+)</Prefix></CommonPrefixes>", x)
        keys += re.findall(r"<Key>([^<]+)</Key>", x)
        if "<IsTruncated>true</IsTruncated>" not in x:
            break
        m = re.search(r"<NextMarker>([^<]+)</NextMarker>", x)
        marker = m.group(1) if m else (dirs[-1] if dirs else keys[-1])
    return dirs, keys


def split(sym):
    for q in QUOTES:
        if sym.endswith(q) and len(sym) > len(q):
            return sym[:-len(q)], q
    return None, None


def day(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d")


def daily_rows(sym, first_ms, n=100):
    """从 first_ms 起 n 根日线：(open_ms, o, h, l, c)。还在交易的走 data-api，已下架的读归档月文件"""
    k = get(KL.format(s=sym, t=first_ms, n=n))
    if k:
        return [(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4])) for x in k]
    rows, d0 = [], dt.datetime.fromtimestamp(first_ms / 1000, dt.timezone.utc)
    for i in range(5):
        y, m = d0.year + (d0.month - 1 + i) // 12, (d0.month - 1 + i) % 12 + 1
        b = get(ZIP.format(s=sym, ym=f"{y}-{m:02d}"), raw=True)
        if not b:
            continue
        try:
            z = zipfile.ZipFile(io.BytesIO(b))
            for r in csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), "utf-8")):
                if r and r[0].isdigit():
                    t = int(r[0])
                    t = t // 1000 if t > 10 ** 14 else t   # 2025 起归档时间戳是微秒
                    rows.append((t, float(r[1]), float(r[2]), float(r[3]), float(r[4])))
        except Exception:
            continue
    rows = sorted({r[0]: r for r in rows if r[0] >= first_ms}.values())
    return rows[:n]


ZIP1M = "https://data.binance.vision/data/spot/monthly/klines/{s}/1m/{s}-1m-{ym}.zip"
KL1M = "https://data-api.binance.vision/api/v3/klines?symbol={s}&interval=1m&startTime={t}&limit={n}"


def minutes(sym, day_ms, n=120):
    """上币当天起的 1 分钟 K 线（第一根 = 开盘那一分钟）：(open_ms, o, h, l, c)。还在交易的走 data-api，已下架的读当月归档"""
    k = get(KL1M.format(s=sym, t=day_ms, n=n))
    if k:
        return [(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4])) for x in k]
    ym = dt.datetime.fromtimestamp(day_ms / 1000, dt.timezone.utc).strftime("%Y-%m")
    b = get(ZIP1M.format(s=sym, ym=ym), raw=True)
    rows = []
    if b:
        try:
            z = zipfile.ZipFile(io.BytesIO(b))
            for r in csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), "utf-8")):
                if r and r[0].isdigit():
                    t = int(r[0]); t = t // 1000 if t > 10 ** 14 else t
                    if t >= day_ms:
                        rows.append((t, float(r[1]), float(r[2]), float(r[3]), float(r[4])))
                        if len(rows) >= n:
                            break
        except Exception:
            pass
    return rows


def minute_close(sym, ms):
    """某一分钟的收盘价（BTC / ETH / BNB 换算美元、BTC 同期起点用）"""
    k = get(KL1M.format(s=sym, t=ms, n=1))
    return float(k[0][4]) if k and int(k[0][0]) == ms else None


def first_candle(sym, cache):
    """交易对第一根日线的开盘时刻（毫秒）；取不到 None。结果缓存"""
    if sym in cache:
        return cache[sym]
    v = None
    k = get(KL.format(s=sym, t=0, n=1))
    if k:
        v = int(k[0][0])
    else:
        _, keys = s3_list(f"data/spot/monthly/klines/{sym}/1d/")
        months = sorted(m for kk in keys for m in re.findall(r"-1d-(\d{4}-\d{2})\.zip$", kk))
        if months:
            b = get(ZIP.format(s=sym, ym=months[0]), raw=True)
            if b:
                try:
                    z = zipfile.ZipFile(io.BytesIO(b))
                    for r in csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), "utf-8")):
                        if r and r[0].isdigit():
                            t = int(r[0])
                            v = t // 1000 if t > 10 ** 14 else t
                            break
                except Exception:
                    pass
    cache[sym] = v
    return v


def usd_closes(sym):
    """BTC / ETH / BNB 的 USDT 日收盘全历史 {日期: 收盘}"""
    out, t = {}, 0
    while True:
        k = get(KL.format(s=sym, t=t, n=1000))
        if not k:
            break
        for x in k:
            out[day(int(x[0]))] = float(x[4])
        if len(k) < 1000:
            break
        t = int(k[-1][0]) + 86400000
    return out


def regime_tools():
    legs = json.load(open(os.path.join(DATA, "leg", "leg_history.json"), encoding="utf-8"))["legs"]
    l2 = json.load(open(os.path.join(DATA, "l2", "l2_series.json"), encoding="utf-8"))
    l2_start = dt.date.fromisoformat(l2["start"])
    states = l2["series"]["state"]

    def leg_at(d):
        for g in legs:
            if g["start_date"] <= d <= (g["end_date"] or "9999") or (g.get("ongoing") and d >= g["start_date"]):
                return g
        return None

    def leg_known(d):   # 交易时实际能知道的：确认日 ≤ 当天的最近一条腿
        c = [g for g in legs if (g.get("confirm_date") or "9999") <= d]
        return max(c, key=lambda g: g["confirm_date"]) if c else None

    def l2_at(d):
        i = (dt.date.fromisoformat(d) - l2_start).days
        return STATE_NAMES[states[i]] if 0 <= i < len(states) and states[i] is not None else None

    return leg_at, leg_known, l2_at


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 4)


def summary(rows):
    out = {"n": len(rows)}
    for key in ("r7", "r30", "r90", "x30", "x90", "peak90"):
        xs = [r[key] for r in rows if r.get(key) is not None]
        out[key] = {"n": len(xs), "p25": pct(xs, .25), "p50": pct(xs, .5), "p75": pct(xs, .75),
                    "mean": round(sum(xs) / len(xs), 4) if xs else None,
                    "below0": round(sum(1 for x in xs if x < 0) / len(xs), 4) if xs else None}
    pd = [r["peak90_day"] for r in rows if r.get("peak90_day") is not None]
    out["peak90_day_p50"] = pct(pd, .5)
    out["level"] = "可看分布（n≥20）" if len(rows) >= 20 else "样本不足（n<20），只列数字"
    return out


def main():
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    os.makedirs(OUT, exist_ok=True)
    try:
        cache = json.load(open(CACHE, encoding="utf-8"))
    except Exception:
        cache = {}
    dirs, _ = s3_list("data/spot/monthly/klines/")
    syms = [d.rstrip("/").rsplit("/", 1)[-1] for d in dirs]
    print("归档里的现货交易对：", len(syms))
    bases = {}
    for s in syms:
        b, q = split(s)
        if not b or q not in USDQ + CRYPTOQ:
            continue
        if b in STABLE or re.search(r"(UP|DOWN|BULL|BEAR)$", b) and len(b) > 4:
            continue
        bases.setdefault(b, []).append((s, q))
    print("候选币（去掉稳定币、杠杆代币、只有法币对的）：", len(bases))
    items = sorted(bases.items())[:limit] if limit else sorted(bases.items())
    n_done = 0
    for b, pairs in items:
        for s, q in pairs:
            first_candle(s, cache)
            n_done += 1
            if n_done % 200 == 0:
                json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
                print("  已查第一根日线", n_done)
            time.sleep(0.03)
    json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
    px = {q: usd_closes(q + "USDT") for q in CRYPTOQ}
    leg_at, leg_known, l2_at = regime_tools()
    coins = []
    for b, pairs in items:
        cand = [(cache.get(s), s, q) for s, q in pairs if cache.get(s)]
        if not cand:
            continue
        QP = ("USDT", "BUSD", "USDC", "FDUSD", "TUSD", "BTC", "BNB", "ETH")
        t0, sym, q = min(cand, key=lambda x: (x[0], QP.index(x[2])))   # 同一天按 USDT → BUSD → USDC → FDUSD → TUSD → BTC → BNB → ETH 选
        d0 = day(t0)
        row = {"asset": b, "pair": sym, "quote": q, "listed": d0, "pairs": len(pairs)}
        if d0 <= LAUNCH_END:
            row["excluded"] = "开张首批"
        elif b.endswith("B") and d0 >= STOCK_FROM and len(b) >= 3:
            row["excluded"] = "代币化股票"
        if "excluded" not in row:
            mins = minutes(sym, t0)
            rows = daily_rows(sym, t0, 100)
            conv = (lambda dd: 1.0) if q in USDQ else (lambda dd, qq=q: px[qq].get(dd))
            if len(mins) >= 60 and rows:
                ft = mins[0][0]                                   # 开盘那一分钟
                by = {m[0]: m for m in mins}
                m15, m60 = by.get(ft + 14 * 60000), by.get(ft + 59 * 60000)
                qk = (lambda ms: 1.0) if q in USDQ else (lambda ms, qq=q: minute_close(qq + "USDT", ms))
                f15, f60, f0 = (m15 and qk(m15[0])), (m60 and qk(m60[0])), qk(ft)
                if m15 and f15:
                    ref = m15[4] * f15
                    row.update(open_minute_utc=dt.datetime.fromtimestamp(ft / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                               first_open_usd=round(mins[0][1] * (f0 or 0), 8), ref15_usd=round(ref, 8),
                               ref60_usd=round(m60[4] * f60, 8) if m60 and f60 else None,
                               first15_vs_open=round(ref / (mins[0][1] * f0) - 1, 4) if f0 else None)
                    usd = [(day(r[0]), r[2] * (conv(day(r[0])) or 0), r[4] * (conv(day(r[0])) or 0)) for r in rows]
                    usd = [u for u in usd if u[2] > 0]
                    b15 = minute_close("BTCUSDT", m15[0])
                    row["days"] = len(usd)
                    for w in WINDOWS:
                        if len(usd) > w:
                            row[f"r{w}"] = round(usd[w][2] / ref - 1, 4)
                            if row.get("ref60_usd"):
                                row[f"r{w}_from60"] = round(usd[w][2] / row["ref60_usd"] - 1, 4)
                            b1 = px["BTC"].get(usd[w][0])
                            if b15 and b1:
                                row[f"btc{w}"] = round(b1 / b15 - 1, 4)
                                row[f"x{w}"] = round(row[f"r{w}"] - row[f"btc{w}"], 4)
                    win = usd[1:91]   # 不含上币当天：当天日线最高价含开盘尖峰，15 分钟后的当天高点只有日线算不出，先不计
                    if win:
                        hi = max(win, key=lambda u: u[2])   # 按日收盘取最高（冷门交易对的单根插针不算）
                        row["peak90"] = round(hi[2] / ref - 1, 4)
                        row["peak90_day"] = usd.index(hi)
                else:
                    row["excluded"] = "取不到第 15 分钟价格"
            else:
                row["excluded"] = "取不到上线当天 1 分钟 K 线"
        g, k = leg_at(d0), leg_known(d0)
        row.update(leg_dir=g and g["dir"], leg_regime=g and g["regime"], leg_start=g and g["start_date"],
                   known_leg_dir=k and k["dir"], known_leg_regime=k and k["regime"], l2_state=l2_at(d0), year=d0[:4])
        coins.append(row)
    # 改名 / 迁移嫌疑：同一天有别的币最后一根日线（粗筛，待名单核实）——这里只标首日就有多交易对的
    for r in coins:
        if r.get("pairs", 0) >= 3 and r["listed"] > LAUNCH_END:
            r["multi_pair_day1"] = True
    ok = [r for r in coins if "excluded" not in r and r.get("r7") is not None]
    groups = {}
    for name, keyf in (("牛熊 × 涨跌腿（事后划分）", lambda r: f"{r['leg_regime']}·{r['leg_dir']}"),
                       ("当时已确认的腿", lambda r: f"{r['known_leg_regime']}·{r['known_leg_dir']}"),
                       ("L2 状态", lambda r: r["l2_state"]), ("年份", lambda r: r["year"]), ("全部", lambda r: "全部")):
        sub = {}
        for r in ok:
            sub.setdefault(str(keyf(r)), []).append(r)
        groups[name] = {k: summary(v) for k, v in sorted(sub.items())}
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    note = ("起点 = 开盘后第 15 分钟收盘价（主口径，大叔 11-17 定：普通用户开盘 15 分钟内能买到；另列 1 小时）；BTC / ETH / BNB 计价已换算成美元；超额 = 币 − BTC 同期；"
            "牛熊 × 涨跌腿是事后划分（腿走完才确认），「当时已确认的腿」才是交易时能知道的；中位数为主口径，平均数只作旁注；n < 20 不下结论")
    json.dump({"generated": now, "exchange": "Binance", "market": "现货", "note": note,
               "n": {"coins": len(coins), "used": len(ok), "excluded": sum(1 for r in coins if "excluded" in r)}, "coins": coins},
              open(os.path.join(OUT, "listing_history_binance.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump({"generated": now, "exchange": "Binance", "market": "现货", "note": note, "groups": groups},
              open(os.path.join(OUT, "listing_regime_stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"币 {len(coins)} 个，进统计 {len(ok)} 个")
    for name, sub in groups.items():
        print("==", name)
        for k, s in sub.items():
            f = lambda x: "U" if x is None else f"{x:+.1%}"
            print(f"  {k:<24} n={s['n']:<4} 7天中位 {f(s['r7']['p50'])} 30天中位 {f(s['r30']['p50'])} 90天中位 {f(s['r90']['p50'])} "
                  f"30天超额中位 {f(s['x30']['p50'])} 30天低于起点 {s['r30']['below0'] if s['r30']['below0'] is not None else 'U'} "
                  f"90天内最高中位 {f(s['peak90']['p50'])} 第{s['peak90_day_p50']}天 {s['level']}")


if __name__ == "__main__":
    main()
