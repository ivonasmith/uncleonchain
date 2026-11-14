"""币安全口径成交额（按币汇总，美元，UTC 日）——核心选币观测台「成交额榜」用。

大叔 2026-11-14：一个币的成交额不只是 USDT 现货和 U 本位永续，要按币安全部市场算。
  现货  = 全部在交易的现货对（USDT / USDC / USD1 / U / FDUSD / BTC / ETH / BNB / 法币 TRY、JPY、EUR…），
          计价币按当天收盘折成美元（稳定币也按自己对 USDT 的收盘折，不假设 = 1）；折不出美元的计价币不算并记进覆盖率。
  合约  = U 本位（USDT、USDC 保证金；永续 + 交割）+ 币本位（永续 + 交割，成交量按标的币数 × 当天收盘折美元），
          来自 data.binance.vision 公开归档（fapi 在美国机房 451）。1000PEPE、1MBABYDOGE 这类按 1 枚口径并回原币。
只算在币安现货有交易对的币：合约归档没有标的类型字段，美股 / 黄金 / 指数合约分不出来，大叔定「直接去掉」。
增量缓存在 core/cache/（actions/cache，不进仓库）：首次回填几分钟，之后每天只补新的一天。
"""
import datetime as dt
import json
import os
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

STABLE_Q = {"USDT", "USDC", "USD1", "U", "FDUSD", "TUSD", "USDP", "DAI", "RLUSD", "USDS", "BFUSD", "XUSD", "USDE", "BUSD"}


def _days(a, b):
    a, b = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    return [(a + dt.timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


# ---------------------------------------------------------------- 现货：全部计价对
def spot_all(C, usdt_rows, window, today):
    """C = core_daily 模块（取数函数）；usdt_rows = {base: [(date, close, qv)]}（主流程已取过的 USDT 对，limit=400）。
    返回 (spot_usd{base:{date:usd}}, cov{...})。"""
    info = C.spot_get("/api/v3/exchangeInfo?permissions=SPOT")
    pairs = {s["symbol"]: (s["baseAsset"], s["quoteAsset"]) for s in info["symbols"] if s["status"] == "TRADING"}
    fp = os.path.join(C.CACHE, "spot_pairs.json")
    cache = json.load(open(fp)) if os.path.exists(fp) else {}
    start = (today - dt.timedelta(days=window + 3)).isoformat()
    quotes = {q for _, q in pairs.values()}
    # 非 USDT 计价对 + 折汇率要用的 USDT 对（USDCUSDT、EURUSDT、USDTTRY…：这些币不在主流程的 USDT 名单里）
    todo = [p for p, (b, q) in pairs.items() if q != "USDT" or (b not in usdt_rows and (b in quotes or b in STABLE_Q))]

    def job(p):
        old = cache.get(p) or {}
        lim = 6 if old and max(old) >= (today - dt.timedelta(days=4)).isoformat() else window + 5
        try:
            d = C.spot_get(f"/api/v3/klines?symbol={urllib.parse.quote(p)}&interval=1d&limit={lim}")
        except Exception as e:  # noqa
            return p, e
        new = dict(old)
        for k in d or []:
            day = C.D(k[0])
            if day < today.isoformat():
                new[day] = [float(k[4]), float(k[7])]
        return p, {k: v for k, v in new.items() if k >= start}
    data = {}
    with ThreadPoolExecutor(10) as ex:
        for p, r in ex.map(job, todo):
            if isinstance(r, Exception):
                C.ERR.append(f"现货 {p}: {r}")
                if cache.get(p):
                    data[p] = cache[p]
            elif r:
                data[p] = r
    os.makedirs(C.CACHE, exist_ok=True)
    json.dump(data, open(fp, "w"), separators=(",", ":"))
    for b, rows in usdt_rows.items():
        data[b + "USDT"] = {d: [c, q] for d, c, q in rows if d >= start}
        pairs.setdefault(b + "USDT", (b, "USDT"))

    def fx(q):
        """计价币 → 美元：{date: rate}；USDT 记为 1。"""
        if q == "USDT":
            return None
        if q + "USDT" in data:
            return {d: v[0] for d, v in data[q + "USDT"].items()}
        if "USDT" + q in data:
            return {d: 1 / v[0] for d, v in data["USDT" + q].items() if v[0]}
        if "BTC" + q in data and "BTCUSDT" in data:     # 没有 USDT 对的法币（如 JPY）：用 BTC 交叉汇率
            bu, bq = data["BTCUSDT"], data["BTC" + q]
            return {d: bu[d][0] / bq[d][0] for d in bq if d in bu and bq[d][0]}
        return {}
    rates = {}
    spot_usd, tot, miss = {}, 0.0, {}
    for p, rows in data.items():
        if p not in pairs:
            continue
        b, q = pairs[p]
        if q not in rates:
            rates[q] = fx(q)
        r = rates[q]
        for d, (c, qv) in rows.items():
            usd = qv if r is None else (qv * r[d] if d in r else None)
            if usd is None:
                miss[q] = miss.get(q, 0) + 1
                continue
            spot_usd.setdefault(b, {})
            spot_usd[b][d] = spot_usd[b].get(d, 0) + usd
            tot += usd
    cov = {"pairs": len(data), "quotes": sorted({q for _, q in pairs.values()}), "quotes_unconverted": sorted(q for q, v in rates.items() if v == {}),
           "missing_rate_days": miss}
    return spot_usd, cov


# ---------------------------------------------------------------- 合约：U 本位 + 币本位（公开归档）
def _s3_list(C, prefix):
    import xml.etree.ElementTree as ET
    out, marker = [], ""
    while True:
        b = C.get(f"{C.S3}?prefix={prefix}&delimiter=/&marker={urllib.parse.quote(marker)}", raw=True)
        root = ET.fromstring(b)
        ns = {"s": root.tag.split("}")[0][1:]}
        for p in root.findall("s:CommonPrefixes/s:Prefix", ns):
            out.append(p.text.rstrip("/").split("/")[-1])
        nxt = root.find("s:NextMarker", ns)
        if nxt is None or not nxt.text:
            break
        marker = nxt.text
    return out


def _arch(C, path):
    """归档 zip → {date: (close, quote_volume)}。"""
    import csv, io, zipfile
    b = C.get(f"{C.ARCH}/{path}", raw=True, tries=2)
    if not b:
        return None
    z = zipfile.ZipFile(io.BytesIO(b))
    rows = {}
    for line in csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8")):
        if line and line[0].isdigit():
            rows[C.D(int(line[0]))] = (float(line[4]), float(line[7]))
    return rows


def fut_base(kind, sym):
    """合约名 → 原币名。um：BTCUSDT、1000PEPEUSDC、BTCUSDT_261225；cm：BTCUSD_PERP、ETHUSD_261225。"""
    s = sym.split("_")[0]
    s = s[:-4] if kind == "um" and s.endswith(("USDT", "USDC")) else s[:-3] if s.endswith("USD") else s
    return re.sub(r"^(1000000|10000|1000|1M)", "", s)


def fut_all(C, window, today):
    """返回 (fut_usd{base:{date:usd}}, last_day, cov)。只留最新一天还有归档的合约（= 仍在交易）。"""
    os.makedirs(C.CACHE, exist_ok=True)
    fp = os.path.join(C.CACHE, "fut_all.json")
    cache = json.load(open(fp)) if os.path.exists(fp) else {}
    last = None
    for k in range(1, 5):
        d = (today - dt.timedelta(days=k)).isoformat()
        if _arch(C, f"data/futures/um/daily/klines/BTCUSDT/1d/BTCUSDT-1d-{d}.zip"):
            last = d
            break
    if not last:
        raise RuntimeError("合约归档找不到最近 4 天的 BTCUSDT 日线")
    start = (dt.date.fromisoformat(last) - dt.timedelta(days=window + 3)).isoformat()
    want = _days(start, last)
    syms = [("um", s) for s in _s3_list(C, "data/futures/um/daily/klines/") if s.split("_")[0].endswith(("USDT", "USDC"))]
    syms += [("cm", s) for s in _s3_list(C, "data/futures/cm/daily/klines/")]
    # 交割合约：已到期的目录还在，先按名字里的到期日筛掉
    syms = [(k, s) for k, s in syms if "_" not in s or s.endswith("_PERP") or ("20" + s.split("_")[1][:6]) >= last.replace("-", "")[:8]]

    def path(kind, s, d, monthly=False):
        q = urllib.parse.quote(s)
        return f"data/futures/{kind}/{'monthly' if monthly else 'daily'}/klines/{q}/1d/{q}-1d-{d}.zip"

    def job(ks):
        kind, s = ks
        key = f"{kind}:{s}"
        try:
            have = {d: tuple(v) for d, v in (cache.get(key) or {}).items()}
            got = _arch(C, path(kind, s, last))
            if not got:
                return key, None
            have.update(got)
            miss = [d for d in want if d not in have]
            if len(miss) > 20:
                for ym in sorted({d[:7] for d in miss if d[:7] < last[:7]}):
                    have.update(_arch(C, path(kind, s, ym, True)) or {})
                miss = [d for d in want if d not in have]
            for d in miss:
                have.update(_arch(C, path(kind, s, d)) or {})
            return key, {d: v for d, v in have.items() if d >= start}
        except Exception as e:  # noqa
            return key, e
    data = {}
    with ThreadPoolExecutor(12) as ex:
        for key, r in ex.map(job, syms):
            if isinstance(r, Exception):
                C.ERR.append(f"合约 {key}: {r}")
            elif r:
                data[key] = r
    json.dump(data, open(fp, "w"), separators=(",", ":"))
    fut_usd, n = {}, {"um": 0, "cm": 0}
    for key, rows in data.items():
        kind, s = key.split(":", 1)
        n[kind] += 1
        b = fut_base(kind, s)
        cur = fut_usd.setdefault(b, {})
        for d, (c, qv) in rows.items():
            cur[d] = cur.get(d, 0) + (qv * c if kind == "cm" else qv)   # 币本位 quote_volume 单位是标的币
    return fut_usd, last, {"contracts": n}
