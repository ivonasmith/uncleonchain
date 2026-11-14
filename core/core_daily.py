#!/usr/bin/env python3
"""核心选币观测台 · 日更数据（只用标准库）。

来源（大叔 2026-11-14 交付：Notion《核心标的基本面与叙事追踪》+ 观测台原型 obs.html + volume_rank.py）：
  基本面   DefiLlama 日度 手续费 / 协议收入 / 持有人收入 / DEX 成交额 / TVL（api.llama.fi）
  资金面   币安现货 USDT 日线成交额（data-api.binance.vision）+ U 本位永续日线（data.binance.vision 公开归档；fapi 在美国机房 451）
  技术面   币安现货收盘：MA20 / 50 / 200、RSI14、距 120 日高点、30 日区间位置
  估值     CoinGecko /coins/markets（流通量 / 总量 / FDV），按币安收盘折算；取不到退 DefiLlama 市值
  人工登记 core/core_config.json（分层、回购口径、叙事阶段、解锁、事件、证伪条件、风险记录、重大发现）

输出（UTC 完整日，只取 < 今天的日线）：
  data/core/core_latest.json      当前读数（不含长序列）
  data/core/series/<SYM>.json     单币长序列（详情页走势图）
  data/core/core_history.json     每天一行：各币评分 / 收盘 / 收入 7v30（样本外，不回填）
评分与规则判定全部是【假设】，只做排序和条件检查，不是买卖建议。

用法：python3 core/core_daily.py [--no-fut] [--no-market]
"""
import csv, io, json, math, os, re, statistics as st, sys, time, urllib.error, urllib.parse, urllib.request, zipfile
import datetime as dt
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.environ.get("CORE_OUT") or os.path.join(ROOT, "data", "core")
CACHE = os.path.join(HERE, "cache")
CFG = json.load(open(os.path.join(HERE, "core_config.json"), encoding="utf-8"))
SPOT = ["https://data-api.binance.vision", "https://api.binance.com", "https://api1.binance.com"]
ARCH = "https://data.binance.vision"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
LLAMA = "https://api.llama.fi"
CG = "https://api.coingecko.com/api/v3"
UA = {"User-Agent": "uncleonchain-core/1.0"}
N_RANK = 90            # 成交额榜窗口（天），同 volume_rank.py
BASKET = 50            # 全市场等权篮子：30 日均成交额前 50（不含 BTC）
MKT_ROWS = 80          # 全市场表：30 日均成交额前 80 + 观测池全部
EXCLUDE = set(CFG.get("exclude", []))
STOCK_FROM = "2026-06-11"   # 同 leg：B 结尾且 2026-06-11 起上市的代币化股票不算
ERR = []


def log(m):
    print(f"{dt.datetime.now(dt.timezone.utc):%H:%M:%S} {m}", file=sys.stderr, flush=True)


def get(url, tries=3, raw=False, timeout=30):
    err = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                b = r.read()
                return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            err = e
            if e.code in (400, 404):
                return None
            time.sleep((8 if e.code in (418, 429) else 2) * (i + 1))
        except Exception as e:  # noqa
            err = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{url[:120]}: {err}")


def spot_get(path):
    err = None
    for h in SPOT:
        try:
            return get(h + path, tries=2)
        except Exception as e:  # noqa
            err = e
    raise RuntimeError(err)


TODAY = dt.datetime.now(dt.timezone.utc).date()
D = lambda ts_ms: dt.datetime.fromtimestamp(ts_ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d")


def mean(a):
    a = [x for x in a if x is not None]
    return sum(a) / len(a) if a else None


def pct(a, b):
    return (a / b - 1) * 100 if a is not None and b not in (None, 0) else None


# ---------------------------------------------------------------- 币安现货日线
def spot_universe():
    info = spot_get("/api/v3/exchangeInfo?permissions=SPOT")
    bases = {s["baseAsset"] for s in info["symbols"] if s["status"] == "TRADING" and s["quoteAsset"] == "USDT"}
    out = []
    for b in sorted(bases):
        if b in EXCLUDE or any(b.endswith(x) and b[:-len(x)] in bases for x in ("UP", "DOWN", "BULL", "BEAR")):
            continue
        out.append(b)
    return out


def klines(base, limit=400):
    d = spot_get(f"/api/v3/klines?symbol={urllib.parse.quote(base)}USDT&interval=1d&limit={limit}")
    if not d:
        return None
    return [(D(k[0]), float(k[4]), float(k[7])) for k in d if D(k[0]) < TODAY.isoformat()]


def fetch_spot(bases, limit=400, workers=8):
    out = {}

    def job(b):
        try:
            return b, klines(b, limit)
        except Exception as e:  # noqa
            return b, e
    with ThreadPoolExecutor(workers) as ex:
        for b, r in ex.map(job, bases):
            if isinstance(r, Exception):
                ERR.append(f"现货 {b}: {r}")
            elif r:
                out[b] = r
    return out


# ---------------------------------------------------------------- 永续：data.binance.vision 公开归档（增量缓存）
def s3_symbols():
    syms, marker = [], ""
    while True:
        b = get(f"{S3}?prefix=data/futures/um/daily/klines/&delimiter=/&marker={marker}", raw=True)
        root = ET.fromstring(b)
        ns = {"s": root.tag.split("}")[0][1:]}
        for p in root.findall("s:CommonPrefixes/s:Prefix", ns):
            s = p.text.rstrip("/").split("/")[-1]
            if s.endswith("USDT") and "_" not in s:
                syms.append(s)
        nxt = root.find("s:NextMarker", ns)
        if nxt is None or not nxt.text:
            break
        marker = nxt.text
    return syms


def arch_rows(path):
    b = get(f"{ARCH}/{path}", raw=True, tries=2)
    if not b:
        return None
    z = zipfile.ZipFile(io.BytesIO(b))
    rows = {}
    for line in csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8")):
        if not line or not line[0].isdigit():
            continue
        rows[D(int(line[0]))] = float(line[7])
    return rows


def fut_volumes(window_days):
    """{合约: {日期: 成交额 USDT}}。只保留最新一天还有归档的合约（= 仍在交易）。"""
    os.makedirs(CACHE, exist_ok=True)
    fp = os.path.join(CACHE, "fut_daily.json")
    cache = json.load(open(fp)) if os.path.exists(fp) else {}
    # 最新一天：归档通常次日几小时内出，往前找 BTCUSDT 有文件的那天
    last = None
    for k in range(1, 5):
        d = (TODAY - dt.timedelta(days=k)).isoformat()
        if arch_rows(f"data/futures/um/daily/klines/BTCUSDT/1d/BTCUSDT-1d-{d}.zip"):
            last = d
            break
    if not last:
        raise RuntimeError("永续归档找不到最近 4 天的 BTCUSDT 日线")
    start = (dt.date.fromisoformat(last) - dt.timedelta(days=window_days + 3)).isoformat()
    syms = s3_symbols()
    log(f"永续归档：{len(syms)} 个合约目录，最新日 {last}")

    def day(sym, d):
        q = urllib.parse.quote(sym)
        return arch_rows(f"data/futures/um/daily/klines/{q}/1d/{q}-1d-{d}.zip") or {}

    def job(sym):
        try:
            have = dict(cache.get(sym, {}))
            got = day(sym, last)
            if not got:
                return sym, None          # 最新日没有 = 已下架 / 暂停
            have.update(got)
            days = [(dt.date.fromisoformat(start) + dt.timedelta(days=i)).isoformat()
                    for i in range((dt.date.fromisoformat(last) - dt.date.fromisoformat(start)).days)]
            miss = [d for d in days if d not in have]
            if len(miss) > 20:            # 缺得多：按月包补（当月之前的月份），再逐日补剩下的
                for ym in sorted({d[:7] for d in miss if d[:7] < last[:7]}):
                    q = urllib.parse.quote(sym)
                    have.update(arch_rows(f"data/futures/um/monthly/klines/{q}/1d/{q}-1d-{ym}.zip") or {})
                miss = [d for d in days if d not in have]
            for d in miss:
                if d[:7] == last[:7] or len(miss) <= 20:
                    have.update(day(sym, d))
            return sym, {d: v for d, v in have.items() if d >= start}
        except Exception as e:  # noqa
            return sym, e
    out = {}
    with ThreadPoolExecutor(12) as ex:
        for sym, r in ex.map(job, syms):
            if isinstance(r, Exception):
                ERR.append(f"永续 {sym}: {r}")
            elif r:
                out[sym] = r
    json.dump(out, open(fp, "w"))
    return out, last


def norm_fut(sym):
    b = sym[:-4]
    return re.sub(r"^(1000000|10000|1000|1M)", "", b)


# ---------------------------------------------------------------- DefiLlama
def llama_chart(path):
    d = get(f"{LLAMA}{path}")
    if not d:
        return {}
    return {dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"): v for t, v in (d.get("totalDataChart") or [])
            if dt.datetime.fromtimestamp(t, dt.timezone.utc).date() < TODAY and v is not None}


def win_stats(ser):
    """日序列 → 7 日均 / 30 日均 / 30 日合计 / 前 30 日合计 / 7v30 / 30 日环比。"""
    if not ser:
        return None
    ds = sorted(ser)
    v = [ser[d] for d in ds]
    if len(v) < 30:
        return None
    s30, p30 = sum(v[-30:]), (sum(v[-60:-30]) if len(v) >= 60 else None)
    a7, a30 = sum(v[-7:]) / 7, s30 / 30
    return {"last_day": ds[-1], "avg7": a7, "avg30": a30, "sum30": s30, "prev30": p30,
            "d7v30": pct(a7, a30), "mom30": pct(s30, p30) if p30 else None}


def tvl_series(slug):
    d = get(f"{LLAMA}/protocol/{slug}")
    if not d:
        return {}, None
    rows = d.get("tvl") or []
    out = {dt.datetime.fromtimestamp(r["date"], dt.timezone.utc).strftime("%Y-%m-%d"): r["totalLiquidityUSD"] for r in rows}
    return {k: v for k, v in out.items() if k < TODAY.isoformat()}, d.get("mcap")


def clean(x):
    """NaN / inf → None（JSON 里不许出现 NaN），小数统一 6 位有效数字以内。"""
    if isinstance(x, float):
        return None if math.isnan(x) or math.isinf(x) else float(f"{x:.6g}")
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    return x


def tail(ser, n=90):
    ds = sorted(ser)[-n:]
    return {"dates": ds, "vals": [round(ser[d], 2) for d in ds]}


# ---------------------------------------------------------------- 技术面
def sma(a, n):
    return [None if i < n - 1 else sum(a[i - n + 1:i + 1]) / n for i in range(len(a))]


def rsi(c, n=14):
    if len(c) <= n:
        return None
    g = [max(c[i] - c[i - 1], 0) for i in range(1, len(c))]
    l = [max(c[i - 1] - c[i], 0) for i in range(1, len(c))]
    ag, al = sum(g[:n]) / n, sum(l[:n]) / n
    for i in range(n, len(g)):
        ag, al = (ag * (n - 1) + g[i]) / n, (al * (n - 1) + l[i]) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def trend_label(last, m20, m50):
    if m20 is None or m50 is None:
        return "历史不足"
    if last > m20 and last > m50:
        return "多头排列（MA20、MA50 上方）" if m20 >= m50 else "修复中（站上 MA20、MA50，均线未金叉）"
    if last < m20 and last < m50:
        return "趋势已破（MA20、MA50 下方）"
    return "回调（跌破 MA20，守在 MA50 上方）" if last > m50 else "反弹（站上 MA20，仍在 MA50 下方）"


def ret(c, n):
    return pct(c[-1], c[-1 - n]) if len(c) > n else None


def price_stats(rows):
    ds, c, q = [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]
    m20, m50, m200 = sma(c, 20), sma(c, 50), sma(c, 200)
    last = c[-1]
    w30 = c[-30:]
    hi120 = max(c[-120:])
    lo30, hi30 = min(w30), max(w30)
    v7, v30 = mean(q[-7:]), mean(q[-30:])
    p = {"last": last, "date": ds[-1], "ma20": m20[-1], "ma50": m50[-1], "ma200": m200[-1], "rsi14": rsi(c[-150:]),
         "trend": trend_label(last, m20[-1], m50[-1]), "pos30": (last - lo30) / (hi30 - lo30) * 100 if hi30 > lo30 else None,
         "vol7": v7, "vol30": v30, "vol7v30": pct(v7, v30), "hi120": hi120, "dd120": pct(last, hi120),
         "vsMA200": pct(last, m200[-1]) if m200[-1] else None, "histDays": len(c),
         "r7": ret(c, 7), "ret30": ret(c, 30), "r90": ret(c, 90)}
    n = 250
    ser = {"dates": ds[-n:], "close": c[-n:], "vol": [round(x) for x in q[-n:]], "ma200": [None if x is None else round(x, 8) for x in m200[-n:]]}
    return p, ser


# ---------------------------------------------------------------- 评分（原型 obs.html 同一套，全部【假设】）
def band(x, hi, mid, low):
    return 3 if x >= hi else 2 if x >= mid else 1 if x >= low else 0


def score(c):
    m = []
    fr, fh, pr, v, a = c["fees"].get("revenue"), c["fees"].get("holders"), c.get("price"), c.get("val"), c.get("act")
    near = "（Intents 口径，与 NEAR 代币关系待核）" if c["sym"] == "NEAR" else ""
    fp = lambda x: "—" if x is None else f"{x:+.1f}%"
    if fr and fr["d7v30"] is not None and fr["mom30"] is not None:
        w = min(fr["d7v30"], fr["mom30"])
        m.append({"k": "R", "n": "收入趋势", "s": band(w, 10, -10, -30), "why": f"7日均对30日均 {fp(fr['d7v30'])}；30日环比 {fp(fr['mom30'])}；取更差者 {fp(w)}"})
    else:
        m.append({"k": "R", "n": "收入趋势", "s": None, "why": "无收入数据"})
    if c.get("hshare") is not None and fr and fr["sum30"] > 0:
        h = c["hshare"]
        m.append({"k": "C", "n": "价值捕获", "s": 3 if h >= 50 else 2 if h >= 20 else 1 if h > 0 else 0, "why": f"30日持有人收入占协议收入 {h:.0f}%{near}"})
    else:
        m.append({"k": "C", "n": "价值捕获", "s": None, "why": "无协议收入数据"})
    if v and v.get("mcap") and fr and fr["sum30"] > 0:
        if v.get("p_hr"):
            x = v["p_hr"]
            m.append({"k": "V", "n": "估值", "s": 3 if x < 15 else 2 if x < 30 else 1 if x < 60 else 0,
                      "why": f"市值 / 年化持有人收入 {x:.1f}x" + ("（口径不匹配：仅 Intents 收入对整个 NEAR 市值）" if near else "")})
        else:
            m.append({"k": "V", "n": "估值", "s": 0, "why": "持有人收入为 0，无回购，不给分"})
    else:
        m.append({"k": "V", "n": "估值", "s": None, "why": "缺市值或收入"})
    if pr and fr and fr["mom30"] is not None and pr.get("ret30") is not None:
        g = fr["mom30"] - pr["ret30"]
        m.append({"k": "D", "n": "价格×收入", "s": 3 if g >= 20 else 2 if g >= -20 else 1 if g >= -50 else 0,
                  "why": f"收入30日环比 {fp(fr['mom30'])} − 价格30日 {fp(pr['ret30'])} = {g:+.1f}pp（正值 = 收入领先价格）"})
    else:
        m.append({"k": "D", "n": "价格×收入", "s": None, "why": "缺价格或收入"})
    if a and a.get("d7v30") is not None and a.get("mom30") is not None:
        w = min(a["d7v30"], a["mom30"])
        m.append({"k": "B", "n": "业务量", "s": band(w, 10, -10, -30), "why": f"{a['label']}：7日均对30日均 {fp(a['d7v30'])}；30日环比 {fp(a['mom30'])}"})
    else:
        m.append({"k": "B", "n": "业务量", "s": None, "why": "无业务量口径"})
    u = c.get("unlock")
    if u and u.get("pct_circ") is not None:
        p = u["pct_circ"]
        m.append({"k": "S", "n": "供给", "s": 3 if p < 0.5 else 2 if p < 2 else 1 if p < 5 else 0, "why": f"30日内约 {p:.2f}% 流通量解锁"})
    else:
        m.append({"k": "S", "n": "供给", "s": None, "why": "已查：30日内无 ≥5% 解锁，具体值未取，不计分" if c.get("under5") else "未登记解锁数据"})
    sc = [x for x in m if x["s"] is not None]
    return {"mods": m, "n": len(sc), "total": round(sum(x["s"] for x in sc) / (3 * len(sc)) * 100) if sc else None}


# ---------------------------------------------------------------- 成交额榜（volume_rank.py 同一套口径）
def ranks(vol, days):
    out = {}
    for t in days:
        lst = sorted(((d[t], s) for s, d in vol.items() if d.get(t, 0) > 0), reverse=True)
        out[t] = {s: i + 1 for i, (_, s) in enumerate(lst)}
    return out


def rk_stats(rank, days, s):
    rk = [rank[t].get(s) for t in days]
    present = [r for r in rk if r]
    if not present:
        return None
    r7, pr = rk[-7:], rk[:-7]
    return {"cur": rank[days[-1]].get(s), "best": min(present), "med": st.median(present),
            "d30": sum(1 for r in present if r <= 30), "d50": sum(1 for r in present if r <= 50),
            "d30_recent7": sum(1 for r in r7 if r and r <= 30), "d30_prior": sum(1 for r in pr if r and r <= 30),
            "spark": rk[-30:]}


def volume_board(spot_q, fut_q):
    comb = {}
    for s in set(spot_q) | set(fut_q):
        d = {}
        for src in (spot_q.get(s, {}), fut_q.get(s, {})):
            for t, q in src.items():
                d[t] = d.get(t, 0) + q
        comb[s] = d
    common = sorted(set(t for d in spot_q.values() for t in d) & (set(t for d in fut_q.values() for t in d) if fut_q else set(t for d in spot_q.values() for t in d)))
    days = common[-N_RANK:]
    if not days:
        return None
    rs, rf, rc = ranks(spot_q, days), (ranks(fut_q, days) if fut_q else {}), ranks(comb, days)
    last, last30 = days[-1], days[-30:]
    rows = []
    for s in comb:
        c = rk_stats(rc, days, s)
        if not c:
            continue
        sv = sum(spot_q.get(s, {}).get(t, 0) for t in last30)
        fv = sum(fut_q.get(s, {}).get(t, 0) for t in last30)
        rows.append({"sym": s, "comb": c, "spot": (rk_stats(rs, days, s) or {}).get("cur"), "fut": (rk_stats(rf, days, s) or {}).get("cur") if fut_q else None,
                     "fut_share_30d": fv / (sv + fv) * 100 if fut_q and sv + fv > 0 else None,
                     "qv_today": comb[s].get(last), "qv30": (sv + fv) / 30})
    n = len(days)
    rows.sort(key=lambda r: (-r["comb"]["d30"], r["comb"]["med"]))
    reg = [r for r in rows if r["comb"]["d30"] >= 0.8 * n]
    ent = [r for r in rows if r["comb"]["cur"] and r["comb"]["cur"] <= 50 and r["comb"]["d30_prior"] <= 3 and r["comb"]["d30_recent7"] >= 2]
    ext = [r for r in rows if r["comb"]["d30_prior"] >= 0.5 * max(n - 7, 1) and r["comb"]["d30_recent7"] == 0]
    tot_s = sum(d.get(last, 0) for d in spot_q.values())
    tot_f = sum(d.get(last, 0) for d in fut_q.values())
    slim = lambda r: {"sym": r["sym"], "cur": r["comb"]["cur"], "med": r["comb"]["med"], "best": r["comb"]["best"], "d30": r["comb"]["d30"],
                      "spot": r["spot"], "fut": r["fut"], "fut_share_30d": r["fut_share_30d"], "qv_today": r["qv_today"], "spark": r["comb"]["spark"]}
    top = sorted((r for r in rows if r["comb"]["cur"]), key=lambda r: r["comb"]["cur"])[:50]
    return {"last_day": last, "window_days": n, "universe": {"spot": len(spot_q), "fut": len(fut_q)},
            "market_fut_share_pct": tot_f / (tot_s + tot_f) * 100 if fut_q and tot_s + tot_f else None,
            "regulars": [slim(r) for r in reg], "entrants": [slim(r) for r in ent], "exits": [slim(r) for r in ext],
            "top": [slim(r) for r in top], "by_sym": {r["sym"]: slim(r) for r in rows}}


# ---------------------------------------------------------------- 主流程
def main():
    no_fut, no_mkt = "--no-fut" in sys.argv, "--no-market" in sys.argv
    os.makedirs(os.path.join(OUT, "series"), exist_ok=True)
    coins_cfg = CFG["coins"]
    pool_syms = {c["sym"] for c in coins_cfg}
    # 1) 币安现货：全部 USDT 现货（全市场表 + 成交额榜 + 观测池）
    try:
        uni = spot_universe()
    except Exception as e:  # noqa
        ERR.append(f"现货 exchangeInfo: {e}")
        uni = []
    want = sorted(set(uni if not no_mkt else []) | pool_syms | {"BTC", "ETH"})
    log(f"现货日线：{len(want)} 个币")
    spot = fetch_spot(want)
    # 代币化股票（B 结尾、2026-06-11 起上市）不进全市场统计
    stock = {b for b, r in spot.items() if b.endswith("B") and r and r[0][0] >= STOCK_FROM and b not in pool_syms}
    btc = spot.get("BTC")
    bp, _ = price_stats(btc)
    last_day = btc[-1][0]
    # 2) CoinGecko
    cg = {}
    try:
        ids = ",".join(c["cg"] for c in coins_cfg if c.get("cg"))
        for x in get(f"{CG}/coins/markets?vs_currency=usd&ids={ids}&per_page=250") or []:
            cg[x["id"]] = x
    except Exception as e:  # noqa
        ERR.append(f"CoinGecko: {e}")
    # 3) 每个币
    coins, series_out = {}, {}
    for cf in coins_cfg:
        s = cf["sym"]
        c = {k: cf.get(k) for k in ("sym", "name", "tier", "tag", "note", "track", "sector", "pos", "stage", "basis", "asof")}
        c["llama"] = cf.get("llama")
        ser = {}
        fees = {}
        if cf.get("llama"):
            try:
                for key, dtp in (("fees", "dailyFees"), ("revenue", "dailyRevenue"), ("holders", "dailyHoldersRevenue")):
                    ch = llama_chart(f"/summary/fees/{cf['llama']}?dataType={dtp}&excludeTotalDataChartBreakdown=true")
                    ser[key] = ch
                    fees[key] = win_stats(ch)
            except Exception as e:  # noqa
                ERR.append(f"DefiLlama 费用 {s}: {e}")
        c["fees"] = fees
        fr, ff, fh = fees.get("revenue"), fees.get("fees"), fees.get("holders")
        c["take"] = fr["sum30"] / ff["sum30"] * 100 if fr and ff and ff["sum30"] else None
        c["hshare"] = (fh["sum30"] / fr["sum30"] * 100 if fh else None) if fr and fr["sum30"] else None
        llama_mcap = None
        act_ser = {}
        if cf.get("act") and cf.get("llama"):
            try:
                if cf["act"] == "dexs":
                    act_ser = llama_chart(f"/summary/dexs/{cf['llama']}?dataType=dailyVolume&excludeTotalDataChartBreakdown=true")
                    lab = "日成交额"
                else:
                    act_ser, llama_mcap = tvl_series(cf["llama"])
                    lab = "TVL"
                a = win_stats(act_ser)
                if a:
                    ds = sorted(act_ser)
                    a.update({"label": lab, "kind": cf["act"], "last": act_ser[ds[-1]],
                              "mom30": pct(a["avg30"], mean([act_ser[d] for d in ds[-60:-30]])) if lab == "TVL" and len(ds) >= 60 else a["mom30"]})
                c["act"] = a
            except Exception as e:  # noqa
                ERR.append(f"DefiLlama 业务量 {s}: {e}")
                c["act"] = None
        else:
            c["act"] = None
        rows = spot.get(s)
        if rows and len(rows) >= 30:
            p, pser = price_stats(rows)
            p["ret30vsBTC"] = p["ret30"] - bp["ret30"] if p["ret30"] is not None else None
            c["price"] = p
        else:
            c["price"], pser = None, None
            ERR.append(f"{s}: 币安现货无日线")
        # 供给与估值
        g = cg.get(cf.get("cg"))
        px = c["price"]["last"] if c["price"] else None
        val, sup = None, None
        if g and g.get("circulating_supply"):
            circ, tot, mx = g["circulating_supply"], g.get("total_supply"), g.get("max_supply")
            sup = {"circ": circ, "total": tot, "max": mx, "circ_ratio": circ / tot * 100 if tot else None,
                   "overhang_pct": (tot - circ) / circ * 100 if tot else None}
            k = (px / g["current_price"]) if px and g.get("current_price") else 1
            val = {"mcap": circ * px if px else g.get("market_cap"), "fdv": (g.get("fully_diluted_valuation") or 0) * k or None,
                   "src": "CoinGecko 供给 × 币安收盘", "rank": g.get("market_cap_rank")}
        elif llama_mcap:
            val = {"mcap": llama_mcap, "fdv": None, "src": "DefiLlama 市值"}
        if val and val.get("mcap"):
            mc = val["mcap"]
            hr = fh["sum30"] * 365 / 30 if fh else 0
            rv = fr["sum30"] * 365 / 30 if fr else 0
            val.update({"p_hr": mc / hr if hr > 0 else None, "p_rev": mc / rv if rv > 0 else None, "hr_yield": hr / mc * 100 if hr > 0 else None,
                        "p_rev_fd": val["fdv"] / rv if rv > 0 and val.get("fdv") else None,
                        "turnover30": c["price"]["vol30"] * 30 / mc * 100 if c["price"] else None})
        c["supply"], c["val"] = sup, val
        # 解锁（人工登记数量 × 收盘价）
        u = (CFG.get("unlocks") or {}).get(s)
        if u:
            u = dict(u)
            u["usd"] = u["tokens"] * px if px is not None else None
            u["pct_circ"] = u["tokens"] / sup["circ"] * 100 if sup and sup.get("circ") else None
            if u.get("actual_tokens") is not None:
                u["actual_usd"] = u["actual_tokens"] * px if px else None
            h30 = fh["sum30"] if fh else 0
            u["cover_paper"] = h30 / u["usd"] if u.get("usd") else None
            u["cover"] = h30 / u["actual_usd"] if u.get("actual_usd") else u["cover_paper"]
        c["unlock"], c["under5"] = u, s in (CFG.get("under5") or [])
        c["spark_rev"] = [round(ser["revenue"][d]) for d in sorted(ser["revenue"])[-30:]] if ser.get("revenue") else None
        c["spark_px"] = [x for x in (pser or {}).get("close", [])[-90:]] if pser else None
        c["sc"] = score(c)
        coins[s] = c
        ds = sorted(ser.get("fees") or {})[-120:]
        series_out[s] = {"sym": s, "fees": {"dates": ds, "fees": [ser["fees"].get(d) for d in ds],
                                            "revenue": [(ser.get("revenue") or {}).get(d) for d in ds],
                                            "holders": [(ser.get("holders") or {}).get(d) for d in ds]} if ds else None,
                         "act": dict(tail(act_ser, 120), label=c["act"]["label"]) if c.get("act") and act_ser else None,
                         "price": pser}
        log(f"{s}: 评分 {c['sc']['total']}（{c['sc']['n']}/6）")
    # 4) 全市场：基准篮子、错过记录、表格
    market = None
    if not no_mkt:
        rows = []
        for b, r in spot.items():
            if b in stock or b in EXCLUDE or len(r) < 31:
                continue
            c = [x[1] for x in r]
            if b not in pool_syms and r[-1][0] != last_day:
                continue
            if len(c) >= 90 and min(c[-90:]) >= 0.97 and max(c[-90:]) <= 1.03:
                continue   # 稳定币
            p, _ = price_stats(r)
            rows.append({"sym": b, "last": p["last"], "r7": p["r7"], "r30": p["ret30"], "r90": p["r90"], "dd120": p["dd120"],
                         "vsMA200": p["vsMA200"], "vol7v30": p["vol7v30"], "qv30": p["vol30"], "hist": p["histDays"],
                         "pool": b in pool_syms and next(x for x in coins_cfg if x["sym"] == b)["track"] == "pool",
                         "watch": b in pool_syms and next(x for x in coins_cfg if x["sym"] == b)["track"] == "watch",
                         "tag": (next((x for x in coins_cfg if x["sym"] == b), {}) or {}).get("tag", "")})
        rows.sort(key=lambda x: -(x["qv30"] or 0))
        bask = [x for x in rows if x["sym"] != "BTC"][:BASKET]
        bench = {}
        for k in ("r7", "r30", "r90"):
            v = [x[k] for x in bask if x[k] is not None]
            pv = [x[k] for x in bask if x["pool"] and x[k] is not None]
            nv = [x[k] for x in bask if not x["pool"] and x[k] is not None]
            bench[k] = {"btc": bp[{"r7": "r7", "r30": "ret30", "r90": "r90"}[k]], "ew_mean": mean(v), "ew_med": st.median(v) if v else None,
                        "pool_med": st.median(pv) if pv else None, "non_med": st.median(nv) if nv else None, "n_pool": len(pv)}
        top15 = [x["sym"] for x in sorted((x for x in bask if x["r30"] is not None), key=lambda x: -x["r30"])[:15]]
        top10_7 = [x["sym"] for x in sorted((x for x in bask if x["r7"] is not None), key=lambda x: -x["r7"])[:10]]
        # 收入线索：DefiLlama 协议名单按代币符号匹配（待核），近 30 日协议收入合计
        rev = {}
        try:
            protos = get(f"{LLAMA}/protocols") or []
            ov = get(f"{LLAMA}/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue") or {}
            r30 = {}
            for x in ov.get("protocols") or []:
                if x.get("total30d"):
                    r30[x.get("slug")] = r30.get(x.get("slug"), 0) + x["total30d"]
            for pr in protos:
                sy = (pr.get("symbol") or "").upper()
                if sy and sy != "-" and pr.get("slug") in r30:
                    rev[sy] = rev.get(sy, 0) + r30[pr["slug"]]
        except Exception as e:  # noqa
            ERR.append(f"DefiLlama 收入线索: {e}")
        show = rows[:MKT_ROWS] + [x for x in rows[MKT_ROWS:] if x["pool"] or x["watch"]]
        for x in show:
            x["rev30"] = rev.get(x["sym"])
        # 成交额榜
        vb = None
        try:
            spot_q = {b: {d: q for d, _, q in r if d < TODAY.isoformat()} for b, r in spot.items() if b not in stock and b not in EXCLUDE}
            fut_q = {}
            if not no_fut:
                fv, _ = fut_volumes(N_RANK + 5)
                for sym, dd in fv.items():
                    b = norm_fut(sym)
                    # 归档没有标的类型字段，美股 / 黄金永续（SNDK、XAU…）分不出来：只算币安现货也有 USDT 对的币
                    if b in EXCLUDE or b not in spot_q:
                        continue
                    cur = fut_q.setdefault(b, {})
                    for d, q in dd.items():
                        cur[d] = cur.get(d, 0) + q
            vb = volume_board(spot_q, fut_q)
            if not fut_q:
                ERR.append("永续成交额未取到：成交额榜只算现货")
        except Exception as e:  # noqa
            ERR.append(f"成交额榜: {e}")
        if vb:
            for x in show:
                r = vb["by_sym"].get(x["sym"])
                x["vrank"] = r["cur"] if r else None
            for s, c in coins.items():
                r = vb["by_sym"].get(s)
                c["vrank"] = {k: r[k] for k in ("cur", "med", "best", "d30", "spot", "fut", "fut_share_30d")} if r else None
            vb.pop("by_sym")
        market = {"date": last_day, "n_basket": len(bask), "bench": bench, "miss": {"top15_30d": top15, "top10_7d": top10_7,
                  "in_pool": [s for s in top15 if s in pool_syms and coins[s]["track"] == "pool"]}, "rows": show, "vol": vb,
                  "n_universe": len(rows), "stock_excluded": len(stock)}
    res = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "last_complete_day": last_day,
           "btc": {"last": bp["last"], "date": bp["date"], "ma200": bp["ma200"], "r7": bp["r7"], "r30": bp["ret30"], "r90": bp["r90"]},
           "coins": coins, "market": market, "manual": {k: CFG.get(k) for k in ("asof", "btc_floor", "events", "fals", "sixq", "risks", "findings")},
           "errors": ERR}
    json.dump(clean(res), open(os.path.join(OUT, "core_latest.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    for s, x in series_out.items():
        json.dump(clean(x), open(os.path.join(OUT, "series", f"{s}.json"), "w", encoding="utf-8"), separators=(",", ":"))
    # 5) 评分历史（每天一行，同日重跑覆盖，不回填）
    hp = os.path.join(OUT, "core_history.json")
    hist = json.load(open(hp, encoding="utf-8")) if os.path.exists(hp) else []
    hist = [h for h in hist if h["date"] != last_day]
    hist.append(clean({"date": last_day, "coins": {s: {"sc": c["sc"]["total"], "n": c["sc"]["n"], "px": c["price"]["last"] if c["price"] else None,
                                                 "rev7v30": (c["fees"].get("revenue") or {}).get("d7v30"),
                                                 "vrank": (c.get("vrank") or {}).get("cur")} for s, c in coins.items()}}))
    hist.sort(key=lambda h: h["date"])
    json.dump(hist, open(hp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    log(f"完成 {last_day}：{len(coins)} 个标的；错误 {len(ERR)} 条")
    for e in ERR[:30]:
        log("  ⚠️ " + e)


if __name__ == "__main__":
    main()
