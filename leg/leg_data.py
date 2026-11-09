#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
leg_data.py —— 网站「涨跌腿追踪 + 山寨整体涨跌腿 + 山寨轮动窗口」的数据文件生成器（schema 4）

用法（零配置，直接跑）：
    python3 leg_data.py                  # 拉全历史日线（Coin Metrics 2010-07-18 起 + 币安 2017-08-17 起），
                                         # 自动保存 leg_latest.json（当前读数）和 leg_history.json（逐条涨腿/跌腿历史）
    python3 leg_data.py --no-early       # 只用币安（2017-08 起），更快；历史文件会标注覆盖范围不完整
    python3 leg_data.py --asof 2026-09-27   # 回放：只用到这一天的收盘，用来和当天海报核对
    python3 leg_data.py --alt-scan       # 同上，另外打印山寨指数在 10/15/20/25/30% 阈值下的腿数对比（确认 ALT_THR 用）
    python3 leg_data.py --alt-refetch    # 山寨候选币全部重新下载
    python3 leg_data.py --alt-from-cache # 山寨篮子用上次存的 leg_alt_cache.csv，不重新下载
    python3 leg_data.py --no-alt         # 不算山寨整体（只出 BTC + 山寨窗口）
    python3 leg_data.py --selftest       # 离线自测（合成数据），不联网
    python3 leg_data.py --csv 日线.csv   # 离线：用 date,close 两列的 csv，不联网

输出文件（都在本脚本所在文件夹；环境变量 LEG_OUT / LEG_HIST_OUT 可改路径）：
  leg_latest.json   当前读数。BTC 这一腿永远是「涨腿」或「跌腿」之一（direction=up/down），不再有「没有涨腿」的空状态。
  leg_history.json  全部历史涨腿/跌腿逐条记录 + 全部行情的分布统计（页面详情页用）。
                    schema 4 新增 alt_leg（山寨整体当前这一腿，等权篮子指数，ALT_THR=15%）；取数失败时为 null。
                    leg_history.json 新增 alt（山寨整体逐条腿 + 分布 + 牛熊拆开，牛熊借用 BTC 周期口径）。
  leg_alt_cache.csv  山寨候选币日线（收盘+成交额；每次运行自动保存并增量更新，首次下载约 5~10 分钟；供 --alt-from-cache 回放用）。
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
  山寨整体涨跌腿：把「动态篮子」做成等权、每日再平衡的指数（成员规则见 ALT_* 常量：每月 1 日按 30 日成交额排名评定进出，约 50~75 个币；
        停牌/崩盘立刻剔除；全程只用评定日以前的数据，已下架的币从币安历史归档补回，所以没有「只留幸存者」的偏差），
        用和 BTC 完全相同的折线规则，阈值放大到 ALT_THR=15%（山寨对 BTC 的 β 约 1.25~1.9）。每天山寨整体也必在涨腿或跌腿之中。
        这是「山寨整体在哪条腿」的读数，和下面的「山寨窗口」（BTC 点火后的交易时钟）是两回事，两个都展示。
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

# ---- 山寨整体（动态篮子指数）----
ALT_THR = 0.15        # 山寨涨腿/跌腿反向确认幅度（BTC 是 10%；山寨对 BTC 的 β 约 1.25~1.9，按 ~1.5 倍取 15%；用 --alt-scan 看 10/15/20/25/30% 的对比）
ALT_MIN_COINS = 8     # 指数起算条件：当天至少 8 个成员有「连续两天」收盘
# 篮子成员规则（每月 1 日按「前一天及以前」的数据重新评定，全程只用当时已知的数据，不看后来的结果）：
ALT_N_ENTER = 50      # 进：30 日成交额中位数排名 ≤ 50（BTC、ETH、稳定币、包装币不参与排名）
ALT_N_KEEP = 75       # 留：老成员排名 ≤ 75 就不踢（缓冲带，避免在 50 名边缘天天进出）
ALT_VOL_ENTER = 2e6   # 进：30 日成交额中位数 ≥ 200 万美元/天
ALT_VOL_KEEP = 5e5    # 留：≥ 50 万美元/天，低于就出
ALT_MIN_AGE = 90      # 进：币安上市满 90 天
ALT_VOL_WIN = 30      # 成交额统计窗口（天）；窗口内至少要有 20 天有数据
ALT_STALE = 3         # 连续 3 天没有 K 线（停牌/下架）→ 立刻出，不等月初
ALT_COLLAPSE = 0.10   # 收盘价 ≤ 自己近 90 天最高收盘的 10%（跌掉 90%）→ 立刻出；崩盘那几天的跌幅已经算进指数
ALT_COLLAPSE_WIN = 90
ALT_STABLE_BAND = (0.97, 1.03)   # 近 90 天收盘全在这个区间 → 视为稳定币，不入篮
# 静态剔除：BTC/ETH（不是山寨）、稳定币、法币、包装币/质押凭证、黄金币。其余稳定币由上面的价格带规则兜底。
ALT_EXCLUDE = set("""BTC ETH WBTC WBETH BETH STETH WSTETH CBETH RETH WEETH BNSOL USDC FDUSD TUSD BUSD USDP DAI USDS USDE USD1 PYUSD UST
 AEUR EUR EURI GBP TRY BRL ARS UAH PLN RON CZK ZAR JPY MXN COP IDR NGN RUB PAXG XAUT""".split())
# 取不到币安全量币种名单时的保底种子（正常不会用到）
ALT_SEED = ("BNB XRP SOL TRX DOGE ADA LINK AVAX DOT LTC BCH ATOM UNI NEAR ETC XLM FIL ALGO AAVE OP ARB INJ SUI APT TIA "
            "ENA PENDLE CAKE ZEC TAO RENDER JUP RAY HBAR ICP VET SAND MANA AXS THETA EOS XTZ NEO IOTA DASH ONT ZIL ENJ CHZ "
            "GRT CRV SNX COMP MKR LDO ETHFI ONDO SEI WLD FET TON").split()
ALT_MIN_SYMBOLS = 100  # 取到数据的币种少于这个数 → 不出山寨整体读数
# 代币化股票 / ETF（NVDAB、TSLAB、QQQB…）：币安 2026-06-11 起上线，名字 = 股票代码 + B。不是山寨，不进篮子。
# 站点 2026-11-09 加（校准时发现 10～11 月有 8 个按成交额进了前 50）。规则只看「B 结尾 + 首根日线在这天及以后」。
ALT_STOCK_FROM = dt.date(2026, 6, 11)


def _excluded(sym, first_day):
    return sym in ALT_EXCLUDE or (sym.endswith("B") and first_day >= ALT_STOCK_FROM)

class _Thr:
    """临时把全局 THR 换成别的阈值（山寨用 ALT_THR），退出时还原。"""
    def __init__(self, x):
        self.x = x

    def __enter__(self):
        global THR
        self.old, THR = THR, self.x

    def __exit__(self, *a):
        global THR
        THR = self.old


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


ARCHIVE_LIST = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
ARCHIVE_BASE = "https://data.binance.vision"


def _get_bytes(url, tries=3):
    last = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "leg-data/1.0"}), timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (400, 403, 404):
                raise
            last = e
        except Exception as e:  # noqa
            last = e
        time.sleep(1.5 * (k + 1))
    raise last


def _day_of(ms):
    if ms > 10 ** 14:          # 2025 年起归档文件的时间戳是微秒
        ms //= 1000
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()


def parse_archive_zip(blob):
    """data.binance.vision 的月度日线 zip → {date: (close, quote_volume)}。"""
    import io
    import zipfile
    out = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for name in z.namelist():
            if not name.endswith(".csv"):
                continue
            for line in z.read(name).decode().splitlines():
                f = line.split(",")
                if len(f) < 8 or not f[0].strip().isdigit():
                    continue
                out[_day_of(int(f[0]))] = (float(f[4]), float(f[7]))
    return out


def list_usdt_bases():
    """币安历史上出现过的所有 *USDT 现货币种（含已下架）。来源：exchangeInfo（现在在交易的）+ data.binance.vision 归档目录（含已下架）。"""
    import re
    import urllib.parse
    bases, notes = set(), []
    for host in HOSTS:
        try:
            info = _get(f"{host}/api/v3/exchangeInfo", tries=2)
            bases |= {x["baseAsset"] for x in info["symbols"] if x["quoteAsset"] == "USDT"}
            notes.append("exchangeInfo")
            break
        except Exception:  # noqa
            continue
    try:
        marker = ""
        while True:
            url = f"{ARCHIVE_LIST}?delimiter=/&prefix=data/spot/monthly/klines/&max-keys=1000" + (f"&marker={urllib.parse.quote(marker)}" if marker else "")
            txt = _get_bytes(url).decode()
            for name in re.findall(r"<Prefix>data/spot/monthly/klines/([A-Z0-9]+)/</Prefix>", txt):
                if name.endswith("USDT"):
                    bases.add(name[:-4])
            nm = re.search(r"<NextMarker>(.*?)</NextMarker>", txt)
            if "<IsTruncated>true</IsTruncated>" in txt and nm:
                marker = nm.group(1)
            else:
                break
        notes.append("archive")
    except Exception as e:  # noqa
        print(f"  ⚠ 归档目录没取到（{e}），已下架的币可能缺", file=sys.stderr)
    return bases, notes


def candidate_symbols(bases):
    """去掉静态剔除名单和杠杆代币（BTCUP/BTCDOWN 之类）。"""
    out = []
    for b in sorted(bases):
        if b in ALT_EXCLUDE:
            continue
        if any(b.endswith(sfx) and b[:-len(sfx)] in bases for sfx in ("UP", "DOWN", "BULL", "BEAR")):
            continue
        out.append(b)
    return out


def fetch_symbol_api(sym, start_ms):
    """币安 API 日线 → {date: (close, quote_volume)}；币安 API 没有这个交易对（已下架）返回 None。"""
    now_ms = int(time.time() * 1000)
    err = None
    for host in HOSTS:
        try:
            rows, cur = [], start_ms
            while True:
                data = _get(f"{host}/api/v3/klines?symbol={sym}USDT&interval=1d&startTime={cur}&limit=1000", tries=2)
                if not data:
                    break
                rows += data
                cur = data[-1][0] + 86400000
                if len(data) < 1000 or cur > now_ms:
                    break
            return {_day_of(r[0]): (float(r[4]), float(r[7])) for r in rows if r[6] < now_ms}
        except urllib.error.HTTPError as e:   # 400 = API 里没有这个交易对
            if e.code == 400:
                return None
            err = e
        except Exception as e:  # noqa
            err = e
    raise RuntimeError(f"{sym}USDT 取数失败：{err}")


def fetch_symbol_archive(sym, since=None):
    """已下架币的历史：data.binance.vision 月度日线归档。"""
    import re
    keys, marker = [], ""
    import urllib.parse
    while True:
        url = f"{ARCHIVE_LIST}?prefix=data/spot/monthly/klines/{sym}USDT/1d/&max-keys=1000" + (f"&marker={urllib.parse.quote(marker)}" if marker else "")
        txt = _get_bytes(url).decode()
        ks = re.findall(r"<Key>([^<]+\.zip)</Key>", txt)
        keys += ks
        if "<IsTruncated>true</IsTruncated>" in txt and ks:
            marker = ks[-1]
        else:
            break
    out = {}
    for k in sorted(keys):
        m = re.search(r"-(\d{4})-(\d{2})\.zip$", k)
        if since and m and (int(m.group(1)), int(m.group(2))) < (since.year, since.month):
            continue
        try:
            out.update(parse_archive_zip(_get_bytes(f"{ARCHIVE_BASE}/{k}")))
        except Exception as e:  # noqa
            print(f"  ⚠ {sym} {k}: {e}", file=sys.stderr)
    return out


def fetch_symbol(sym, old=None):
    """取一个币。old = 缓存里已有的 {date:(close,qv)}（有就只补新的）。返回 (data, source)。"""
    start = dt.datetime.strptime(FETCH_FROM, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    if old:
        start = dt.datetime.combine(max(old) + dt.timedelta(days=1), dt.time(), dt.timezone.utc)
    api = fetch_symbol_api(sym, int(start.timestamp() * 1000))
    if api:
        return api, "api"
    if api is None or not old:       # API 里没有 → 去归档找
        arc = fetch_symbol_archive(sym, since=start.date())
        if arc:
            return arc, "archive"
    return {}, "none"


def fetch_alt_coins(symbols, cache, refetch=False, workers=6):
    """取全部候选币日线（增量：缓存里已有的只补新的；缓存里最后一根早于 14 天前的视为已下架，不再请求）。
    返回 (coins{sym:{date:(close,qv)}}, cov)。"""
    from concurrent.futures import ThreadPoolExecutor
    today = dt.datetime.now(dt.timezone.utc).date()
    coins = {k: dict(v) for k, v in cache.items()}
    todo = []
    for sym in symbols:
        old = coins.get(sym)
        if old and not refetch and (today - max(old)).days > 14:
            continue
        todo.append(sym)
    stats = {"api": 0, "archive": 0, "none": 0, "failed": []}

    def job(sym):
        try:
            return sym, fetch_symbol(sym, None if refetch else coins.get(sym))
        except Exception as e:  # noqa
            return sym, ({}, f"failed:{e}")

    print(f"  山寨候选 {len(symbols)} 个币，需要取数 {len(todo)} 个（首次约 5~10 分钟，之后增量很快）…", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for k, (sym, (d, src)) in enumerate(ex.map(job, todo), 1):
            if src.startswith("failed"):
                stats["failed"].append(sym)
            else:
                stats[src] += 1
                if d:
                    coins.setdefault(sym, {}).update(d)
            if k % 50 == 0:
                print(f"    {k}/{len(todo)} …", file=sys.stderr)
    coins = {k: v for k, v in coins.items() if len(v) > 0}
    cov = {"universe": len(symbols), "with_data": len(coins), "from_api": stats["api"], "from_archive": stats["archive"],
           "no_data": stats["none"], "failed": stats["failed"][:40]}
    return coins, cov


def _alt_cache_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "leg_alt_cache.csv")


def save_alt_cache(coins):
    with open(_alt_cache_path() + ".tmp", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "symbol", "close", "qvol"])
        for sym, d in coins.items():
            for k in sorted(d):
                w.writerow([k.isoformat(), sym, d[k][0], d[k][1]])
    os.replace(_alt_cache_path() + ".tmp", _alt_cache_path())


def load_alt_cache():
    coins = {}
    if not os.path.exists(_alt_cache_path()):
        return coins
    with open(_alt_cache_path(), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            coins.setdefault(r["symbol"], {})[dt.date.fromisoformat(r["date"])] = (float(r["close"]), float(r.get("qvol") or 0))
    return coins


def alt_rules():
    return {"n_enter": ALT_N_ENTER, "n_keep": ALT_N_KEEP, "vol_enter_usd": ALT_VOL_ENTER, "vol_keep_usd": ALT_VOL_KEEP,
            "min_age_days": ALT_MIN_AGE, "vol_window_days": ALT_VOL_WIN, "stale_days": ALT_STALE,
            "collapse_pct": round(ALT_COLLAPSE * 100), "collapse_window_days": ALT_COLLAPSE_WIN,
            "stable_band": list(ALT_STABLE_BAND), "rebalance": "monthly", "min_coins": ALT_MIN_COINS,
            "excluded": sorted(ALT_EXCLUDE), "stock_tokens": f"名字以 B 结尾且 {ALT_STOCK_FROM} 起上市的代币化股票 / ETF 不入篮"}


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _alt_state(c, first, rd):
    """币 c 在评定日 rd 的状态（只用 rd 之前的数据）。返回 (问题标签或 None, 30 日成交额中位数)。"""
    one = dt.timedelta(days=1)
    if (rd - first).days < ALT_MIN_AGE:
        return "young", 0.0
    if not any((rd - one * i) in c for i in range(1, ALT_STALE + 1)):
        return "delisted", 0.0
    vols = [c[rd - one * i][1] for i in range(1, ALT_VOL_WIN + 1) if (rd - one * i) in c]
    if len(vols) < ALT_VOL_WIN * 2 // 3:
        return "thin", 0.0
    px = [c[rd - one * i][0] for i in range(1, ALT_COLLAPSE_WIN + 1) if (rd - one * i) in c]
    if len(px) >= 30 and min(px) >= ALT_STABLE_BAND[0] and max(px) <= ALT_STABLE_BAND[1]:
        return "stable", 0.0
    last = next(c[rd - one * i][0] for i in range(1, ALT_STALE + 1) if (rd - one * i) in c)
    if px and last <= ALT_COLLAPSE * max(px):
        return "collapse", _median(vols)
    return None, _median(vols)


def build_alt_index(coins, dates):
    """动态篮子的等权、每日再平衡指数（基期 100）。dates 是 BTC 的日期轴（只取币安时期）。
    成员：每月 1 日按规则评定（进/留/出），期间遇到停牌或崩盘立刻剔除；全程只用评定日以前的数据（无前视）。
    当天收益 = 成员里「昨天和今天都有收盘」的币的日收益的简单平均。
    返回 (idates, levels, n_per_day, info)；info 含 members（现在的成员）、events（进出记录）、n_ever（历史上进过篮子的币数）。"""
    one = dt.timedelta(days=1)
    first = {k: min(v) for k, v in coins.items() if v}
    members, joined, events, last_rank = set(), {}, [], {}
    ever = set()
    idates, lv, ns = [], [], []
    level, started = 100.0, False

    def recon(rd):
        ranked = []
        for sym, c in coins.items():
            if not c or _excluded(sym, first[sym]):
                continue
            why, vol = _alt_state(c, first[sym], rd)
            if why is None:
                ranked.append((sym, vol))
        ranked.sort(key=lambda x: -x[1])
        rank = {sym: (i + 1, vol) for i, (sym, vol) in enumerate(ranked)}
        new = set()
        for sym in members:
            r = rank.get(sym)
            if r and r[0] <= ALT_N_KEEP and r[1] >= ALT_VOL_KEEP:
                new.add(sym)
        for sym, (r, vol) in rank.items():
            if sym not in members and r <= ALT_N_ENTER and vol >= ALT_VOL_ENTER:
                new.add(sym)
        for sym in sorted(members - new):
            r = rank.get(sym)
            if r is None:
                reason = _alt_state(coins[sym], first[sym], rd)[0] or "rank"
            else:
                reason = "rank" if r[0] > ALT_N_KEEP else "volume"
            events.append({"date": rd.isoformat(), "symbol": sym, "action": "exit", "reason": reason})
        for sym in sorted(new - members):
            events.append({"date": rd.isoformat(), "symbol": sym, "action": "join", "reason": "rank", "rank": rank[sym][0]})
            joined[sym] = rd.isoformat()
            ever.add(sym)
        members.clear(); members.update(new)
        last_rank.clear(); last_rank.update(rank)

    for k in range(1, len(dates)):
        d0, d1 = dates[k - 1], dates[k]
        if (d1 - d0).days != 1:
            continue
        if d1.day == 1 or not members:
            recon(d1)
        for sym in sorted(members):                     # 期间自动出：停牌/下架、崩盘
            c = coins[sym]
            why = None
            if not any((d0 - one * i) in c for i in range(0, ALT_STALE)):
                why = "delisted"
            else:
                px = [c[d0 - one * i][0] for i in range(0, ALT_COLLAPSE_WIN) if (d0 - one * i) in c]
                lastpx = next(c[d0 - one * i][0] for i in range(0, ALT_STALE) if (d0 - one * i) in c)
                if px and lastpx <= ALT_COLLAPSE * max(px):
                    why = "collapse"
            if why:
                members.discard(sym)
                events.append({"date": d1.isoformat(), "symbol": sym, "action": "exit", "reason": why})
        rets = [coins[s][d1][0] / coins[s][d0][0] - 1 for s in members if d0 in coins[s] and d1 in coins[s] and coins[s][d0][0] > 0]
        if not started:
            if len(rets) < ALT_MIN_COINS:
                continue
            idates.append(d0); lv.append(level); ns.append(len(rets)); started = True
        r = sum(rets) / len(rets) if len(rets) >= 3 else 0.0
        level *= 1 + r
        idates.append(d1); lv.append(level); ns.append(len(rets))
    mem = [{"symbol": s, "rank": last_rank.get(s, (None, 0))[0], "vol_m": round(last_rank.get(s, (None, 0))[1] / 1e6, 1), "joined": joined.get(s)}
           for s in members]
    mem.sort(key=lambda m: (m["rank"] is None, m["rank"] or 0))
    return idates, lv, ns, {"members": mem, "events": events, "n_ever": len(ever)}


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


def alt_leg_block(adates, alevels, ns, cov, binfo):
    """山寨整体当前这一腿（动态篮子指数，ALT_THR 反向确认）。结构同 btc_leg_block；level 类字段是指数点位（基期 100），页面只该用百分比。"""
    with _Thr(ALT_THR):
        b = btc_leg_block(adates, alevels)
    L = b["leg"]
    if L and "btc_close" in L:
        L["idx_close"] = L.pop("btc_close")
    b["basket"] = {"threshold_pct": ALT_THR * 100, "coins_today": ns[-1], "n_members": len(binfo["members"]), "n_ever": binfo["n_ever"],
                   "members": binfo["members"], "rules": alt_rules(), "recent_changes": binfo["events"][-20:], "coverage": cov,
                   "index_from": adates[0].isoformat(), "asof": adates[-1].isoformat(),
                   "note": "动态篮子：每月 1 日按 30 日成交额排名评定进出，停牌/崩盘立刻剔除；等权、每日再平衡；对 USDT。"}
    return b


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


def _grp(sel):
    ups = [l for l in sel if l["dir"] == "up"]
    downs = [l for l in sel if l["dir"] == "down"]
    return {"up": {"n": len(ups), "days": _stats([l["days"] for l in ups]), "gain_pct": _stats([l["pct"] for l in ups])},
            "down": {"n": len(downs), "days": _stats([l["days"] for l in downs]), "drop_pct": _stats([-l["pct"] for l in downs])}}


def alt_history_block(adates, alevels, btc_dates, btc_closes, ns, cov, binfo):
    """山寨整体的逐条涨腿/跌腿 + 分布。牛熊标注直接借 BTC 的周期口径（按腿终点日），这样两边「牛市/熊市」是同一把尺子。"""
    with _Thr(ALT_THR):
        st = scan_legs(alevels)
        legs = []
        reg, _ = cycle_regime(btc_dates, btc_closes)
        rmap = dict(zip(btc_dates, reg))
        for d, s_, e_ in st["legs"]:
            r = _leg_rec(d, adates, alevels, s_, e_)
            r["regime"] = rmap.get(adates[e_], "bull")
            legs.append(r)
        cur = None
        if st["mode"] in ("up", "down"):
            s_, e_ = (st["up_start"], st["hi_i"]) if st["mode"] == "up" else (st["down_start"], st["lo_i"])
            cur = _leg_rec(st["mode"], adates, alevels, s_, e_, ongoing=True)
    return {"threshold_pct": ALT_THR * 100, "index_from": adates[0].isoformat(), "asof": adates[-1].isoformat(),
            "basket": {"n_now": len(binfo["members"]), "n_ever": binfo["n_ever"], "rules": alt_rules(), "changes": binfo["events"][-300:], "coverage": cov},
            "note": "山寨整体 = 动态篮子指数（对 USDT）；牛熊标注借用 BTC 周期口径。",
            "summary": {"completed_legs": len(legs), "up": _grp(legs)["up"], "down": _grp(legs)["down"],
                        "by_regime": {"bull": _grp([l for l in legs if l["regime"] == "bull"]),
                                      "bear": _grp([l for l in legs if l["regime"] == "bear"])}},
            "legs": legs, "current": cur}


_REPORT = []


def _say(line=""):
    print(line)
    _REPORT.append(line)


def save_report():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leg_alt_report.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(_REPORT) + "\n")
    return path


def alt_scan(adates, alevels):
    """不同阈值下的对比，用来确认 ALT_THR 取得合不合适。"""
    _say(f"【山寨指数折线阈值对比】指数 {adates[0]} ~ {adates[-1]}，{len(alevels)} 天")
    _say("阈值   完整腿数  涨腿中位天数/幅度   跌腿中位天数/跌幅   当前方向（第几天）")
    for thr in (0.10, 0.15, 0.20, 0.25, 0.30):
        with _Thr(thr):
            st = scan_legs(alevels)
            ls = [_leg_rec(d, adates, alevels, a, b) for d, a, b in st["legs"]]
            up = [l for l in ls if l["dir"] == "up"]
            dn = [l for l in ls if l["dir"] == "down"]
            md = lambda xs: (round(_quantile(xs, .5), 1) if xs else None)
            cur = ("涨腿", (adates[-1] - adates[st["up_start"]]).days) if st["mode"] == "up" else (("跌腿", (adates[-1] - adates[st["down_start"]]).days) if st["mode"] == "down" else ("-", 0))
            _say(f"{int(thr*100):>3}%   {len(ls):>5}    {md([l['days'] for l in up])}天/+{md([l['pct'] for l in up])}%      "
                 f"{md([l['days'] for l in dn])}天/{md([l['pct'] for l in dn])}%      {cur[0]} 第{cur[1]}天")


def _alt_ranked(coins, first, rd):
    """评定日 rd 的合格候选币，按 30 日成交额中位数从高到低 → [(sym, vol)]。和 build_alt_index 里评定用的是同一套资格。"""
    out = []
    for sym, c in coins.items():
        if not c or _excluded(sym, first[sym]):
            continue
        why, vol = _alt_state(c, first[sym], rd)
        if why is None:
            out.append((sym, vol))
    out.sort(key=lambda x: -x[1])
    return out


def alt_calib(coins, last_date):
    """校准用：不同年份第 25/50/75/100/150 名的 30 日成交额中位数是多少，现在的成交额门槛卡不卡得住。
    先看数据再定门槛——别拍脑袋。"""
    first = {k: min(v) for k, v in coins.items() if v}
    pts = []
    for y in range(2018, last_date.year + 1):
        for m in (1, 7):
            d = dt.date(y, m, 1)
            if d <= last_date:
                pts.append(d)
    pts.append(last_date + dt.timedelta(days=1))
    _say("【山寨篮子成交额校准】30 日日均成交额中位数（百万美元/天），按评定日只用之前的数据；名次 = 候选币里的名次（BTC/ETH/稳定币等不计）")
    _say(f"现在的门槛：进 = 前 {ALT_N_ENTER} 名且 ≥ {ALT_VOL_ENTER/1e6:g}M；留 = 前 {ALT_N_KEEP} 名且 ≥ {ALT_VOL_KEEP/1e6:g}M")
    _say("评定日       合格币数   #25     #50     #75    #100    #150   前50名里<进门槛  前75名里<留门槛")
    r75 = []
    for d in pts:
        rk = _alt_ranked(coins, first, d)
        if not rk:
            continue
        at = lambda n: (rk[n - 1][1] / 1e6 if len(rk) >= n else None)
        f = lambda v: f"{v:6.1f}" if v is not None else "     -"
        below_e = sum(1 for _, v in rk[:ALT_N_ENTER] if v < ALT_VOL_ENTER)
        below_k = sum(1 for _, v in rk[:ALT_N_KEEP] if v < ALT_VOL_KEEP)
        _say(f"{d}  {len(rk):>7}  {f(at(25))}  {f(at(50))}  {f(at(75))}  {f(at(100))}  {f(at(150))}   {below_e:>10}        {below_k:>10}")
        if at(75) is not None:
            r75.append(at(75))
    if r75:
        _say(f"第 75 名的成交额：历次评定中位数 {_median(r75):.1f}M、最低 {min(r75):.1f}M、最高 {max(r75):.1f}M；最近一次 {r75[-1]:.1f}M")
        _say("读法：如果第 75 名一直远高于现在的「留」门槛，这个门槛就是摆设（该按第 75 名的某个比例设，或干脆不设绝对门槛只用名次）。")


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

    grp = _grp
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
def build(dates, closes, alt=None):
    for a, b in zip(dates, dates[1:]):
        if (b - a).days != 1:
            print(f"⚠ 日线不连续：{a} → {b}，天数计算可能偏差", file=sys.stderr)
            break
    return {"schema": 4,
            "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "asof": dates[-1].isoformat(),
            "source": "Coin Metrics PriceUSD (2010-07-18~2017-08-16) + Binance spot BTCUSDT 1d (2017-08-17~, closed candles, UTC)",
            "btc_leg": btc_leg_block(dates, closes),
            "alt_leg": alt,          # 山寨整体涨腿/跌腿；取数失败或 --no-alt 时为 null，页面显示「山寨整体数据未生成」
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
    al = o.get("alt_leg")
    if al and al.get("leg"):
        L2 = al["leg"]
        if al["direction"] == "up":
            print(f"[山寨整体 涨腿] 起点 {L2['start_date']}（{L2['confirm_date']} 确认） 第 {L2['day']} 天  +{L2['gain_pct']}%  腿内最大回撤 {L2['max_dd_pct']}%（阈值 {al['basket']['threshold_pct']:.0f}%，今日 {al['basket']['coins_today']} 个币）")
        else:
            print(f"[山寨整体 跌腿] 起点（高点）{L2['start_date']}（{L2['confirm_date']} 确认） 第 {L2['day']} 天  −{L2['drop_pct']}%  距高点 {L2['from_peak_pct']}%  反弹确认线距现价 +{L2['to_reversal_pct']}%（阈值 {al['basket']['threshold_pct']:.0f}%，今日 {al['basket']['coins_today']} 个币）")
        B2 = al["basket"]
        print(f"        上一腿：{al['prev_leg']}")
        print(f"        篮子现有 {B2['n_members']} 个币（历史上共进过 {B2['n_ever']} 个）：{' '.join(m['symbol'] for m in B2['members'])}")
        print(f"        取数：候选 {B2['coverage']['universe']}，有数据 {B2['coverage']['with_data']}（API {B2['coverage']['from_api']}、归档补回 {B2['coverage']['from_archive']}），失败 {B2['coverage']['failed']}")
        for ev in B2["recent_changes"][-8:]:
            print(f"          {ev['date']} {'进' if ev['action']=='join' else '出'} {ev['symbol']}  {ev['reason']}")
    else:
        print("[山寨整体] 未生成")
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
    # 6) 山寨动态篮子：只用评定日以前的数据；新币不进、稳定币不进、崩盘/停牌立刻出，崩盘的跌幅算进指数
    days = [dt.date(2020, 1, 1) + dt.timedelta(days=i) for i in range(420)]
    px = lambda i, g=1.002: 100.0 * g ** i
    coins = {f"C{k}": {days[i]: (px(i), 1e7) for i in range(420)} for k in range(10)}
    dead = {}                                                  # 第 200 天起每天 ×0.7，第 230 天后没有 K 线
    for i in range(231):
        dead[days[i]] = (px(i) if i < 200 else px(199) * 0.7 ** (i - 199), 1e7)
    coins["DEAD"] = dead
    coins["HALT"] = {days[i]: (50.0, 1e7) for i in range(300)}     # 价格不动，第 300 天起没有 K 线（停牌/下架）
    coins["STB"] = {days[i]: (1.0 + 0.001 * (i % 3), 1e7) for i in range(420)}    # 稳定币
    coins["NEW"] = {days[i]: (10.0, 1e7) for i in range(380, 420)}                # 刚上市，不满 90 天
    coins["LOWV"] = {days[i]: (px(i), 1e3) for i in range(420)}                   # 成交额太低
    idates, lv, ns, info = build_alt_index(coins, days)
    ev = info["events"]
    joins = {e["symbol"] for e in ev if e["action"] == "join"}
    assert "STB" not in joins and "NEW" not in joins and "LOWV" not in joins and {"DEAD", "HALT", "C0"} <= joins, joins
    assert idates[0] >= days[89], f"不满 90 天不能进篮子，指数 {idates[0]} 起算太早"
    xd = {e["symbol"]: e for e in ev if e["action"] == "exit"}
    assert xd["DEAD"]["reason"] == "collapse" and dt.date.fromisoformat(xd["DEAD"]["date"]) < days[230], xd["DEAD"]
    assert xd["HALT"]["reason"] == "delisted" and dt.date.fromisoformat(xd["HALT"]["date"]) <= days[304], xd["HALT"]
    r = [lv[i + 1] / lv[i] - 1 for i in range(len(lv) - 1)]
    assert min(r) < -0.015, "崩盘那几天的跌幅应该算进指数"
    assert {m["symbol"] for m in info["members"]} == {f"C{k}" for k in range(10)}, info["members"]
    assert info["members"][0]["rank"] is not None and info["n_ever"] == len(joins)
    # 归档 zip 解析（2025 年起时间戳是微秒）
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("X-1d-2025-03.csv", "1740787200000000,1,2,0.5,1.5,100,1740873599999999,150.5,10,50,75,0\n1740873600000,1,2,0.5,1.7,100,1740959999999,170.5,10,50,75,0\n")
    got = parse_archive_zip(buf.getvalue())
    assert got == {dt.date(2025, 3, 1): (1.5, 150.5), dt.date(2025, 3, 2): (1.7, 170.5)}, got
    assert candidate_symbols({"BTC", "ETH", "USDC", "SOL", "BTCUP", "BTCDOWN", "XRP"}) == ["SOL", "XRP"]
    # 7) 山寨用 15% 阈值：+12% 的摆动在 BTC 口径(10%)是腿、在山寨口径不是；THR 用完要还原
    zig = [100, 101, 112, 111, 99, 98, 113, 114]            # 12% 涨、再回落 ~11.6%
    assert len(scan_legs(zig)["legs"]) >= 1
    with _Thr(ALT_THR):
        assert scan_legs(zig)["legs"] == [] and THR == ALT_THR
    assert THR == 0.10
    cov = {"universe": 12, "with_data": 12, "from_api": 12, "from_archive": 0, "no_data": 0, "failed": []}
    bi = {"members": [{"symbol": "C0", "rank": 1, "vol_m": 10.0, "joined": "2020-04-01"}], "events": [], "n_ever": 1}
    zig2 = [100.0] * 3 + [100 + 3 * k for k in range(1, 13)] + [136 - 6 * k for k in range(1, 8)]   # 涨到 136（+36%），再回落到 94（−31%）
    zd2 = [_d(i) for i in range(len(zig2))]
    ab = alt_leg_block(zd2, zig2, [9] * len(zig2), cov, bi)
    assert ab["direction"] == "down" and ab["leg"]["drop_pct"] > 15 and ab["prev_leg"]["dir"] == "up", ab
    assert ab["basket"]["threshold_pct"] == 15.0 and "idx_close" in ab["leg"] and ab["basket"]["rules"]["n_enter"] == 50
    ah = alt_history_block(zd2, zig2, zd2, zig2, [9] * len(zig2), cov, bi)
    assert ah["summary"]["completed_legs"] >= 1 and ah["current"]["ongoing"] and ah["legs"][0]["regime"] in ("bull", "bear")
    print("selftest OK：涨腿 起点确认/回撤/结束/徽章边界；跌腿 起点/跌幅/反弹确认线/回到涨腿；历史逐条；山寨窗口 pending/build/trim/closing/cleared/stopped/idle/去重；山寨动态篮子（入选/剔除/崩盘/停牌/稳定币/新币）/归档解析/15%阈值/还原")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof")
    ap.add_argument("--csv")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--no-early", action="store_true", help="不取 2010~2017 的 Coin Metrics 早期历史，只用币安")
    ap.add_argument("--no-alt", action="store_true", help="不算山寨整体涨跌腿（只出 BTC 和山寨窗口）")
    ap.add_argument("--alt-calib", action="store_true", help="打印各年份第 25/50/75/100/150 名的成交额，校准入选/保留的成交额门槛；结果同时存 leg_alt_report.txt")
    ap.add_argument("--alt-refetch", action="store_true", help="山寨候选币全部重新下载（默认增量：只补缓存里没有的新日期）")
    ap.add_argument("--alt-from-cache", action="store_true", help="山寨篮子用上次存的 leg_alt_cache.csv，不重新下载（回放/调阈值时用）")
    ap.add_argument("--alt-scan", action="store_true", help="打印山寨指数在 10/15/20/25/30%% 阈值下的腿数对比，用来确认 ALT_THR")
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
    alt_blk, alt_hist = None, None
    if not a.no_alt and not a.csv:
        try:
            cache = load_alt_cache()
            if a.alt_from_cache:
                coins, cov = cache, {"universe": len(cache), "with_data": len(cache), "from_api": 0, "from_archive": 0, "no_data": 0, "failed": []}
            else:
                print("取山寨篮子候选币…", file=sys.stderr)
                bases, notes = list_usdt_bases()
                if not bases:
                    bases = set(cache) or set(ALT_SEED)
                    print("  ⚠ 币种名单没取到，改用缓存/保底种子", file=sys.stderr)
                coins, cov = fetch_alt_coins(candidate_symbols(bases), cache, refetch=a.alt_refetch)
                if len(coins) >= ALT_MIN_SYMBOLS:
                    save_alt_cache(coins)
            if len(coins) < ALT_MIN_SYMBOLS:
                raise RuntimeError(f"只取到 {len(coins)} 个币的数据，低于 {ALT_MIN_SYMBOLS}，不出山寨整体读数")
            bi = [k for k, d in enumerate(dates) if d >= dt.date.fromisoformat(FETCH_FROM)]
            cut_d = dates[-1]
            coins = {k: {d: c for d, c in v.items() if d <= cut_d} for k, v in coins.items()}
            idates, lv, ns, binfo = build_alt_index(coins, dates[bi[0]:])
            if len(lv) < 400:
                raise RuntimeError("山寨指数不足 400 天")
            alt_blk = alt_leg_block(idates, lv, ns, cov, binfo)
            alt_hist = alt_history_block(idates, lv, dates, closes, ns, cov, binfo)
            if a.alt_calib:
                alt_calib(coins, cut_d)
            if a.alt_scan:
                alt_scan(idates, lv)
            if _REPORT:
                print("报告已保存：", save_report())
        except Exception as e:  # noqa
            print(f"⚠ 山寨整体涨跌腿没有生成：{e}\n  → leg_latest.json 里 alt_leg=null，其余照常输出", file=sys.stderr)
    out = build(dates, closes, alt_blk)
    hist = history_block(dates, closes, coverage)
    if alt_hist:
        hist["alt"] = alt_hist
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
