#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bybit 全历史上币复盘（只在 GitHub Actions 跑：Bybit API 在美国按国家拦，官方归档 public.bybit.com 能通）。口径同 alpha/listing_history.py / v3。

数据 = Bybit 官方现货逐笔成交归档 https://public.bybit.com/spot/<交易对>/<交易对>-YYYY-MM.csv.gz（按月一个文件）。
  上线时刻 = 第一个月文件里的第一笔成交；起点 = 上线后第 15 分钟内最后一笔成交价（≈ 第 15 分钟收盘）；日收盘 = 每个 UTC 日最后一笔。
  归档从 2022-11 开始：第一个文件就是归档首月的交易对，说明它在归档开始前已上线，剔除（标「归档开始前已上线」）。
  归档目录列的是有过成交的全部交易对，含已下架的，没有幸存者偏差（以目录为准，未逐个核实）。
只收 USDT 计价；剔除稳定币、杠杆代币、疑似代币化股票（同 listing_history_x.stock_suspect）。
用法：python3 alpha/listing_history_bybit.py [--limit N] [--minutes 280]
输出 data/alpha/listing_history_bybit.json（逐币 + 分组统计，格式同 listing_history_x）。
"""
import csv, datetime as dt, gzip, io, json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import listing_history as LH
from listing_history_x import stock_suspect

BASE = "https://public.bybit.com/spot/"
DAY = 86400000


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 + 3 * i)
        except Exception:
            time.sleep(2 + 3 * i)
    return None


def links(url):
    b = get(url)
    return re.findall(r'href="([^"?/][^"]*)"', b.decode("utf-8", "replace")) if b else []


def trades(sym, ym):
    """一个月的逐笔成交 → [(ts_ms, price)]（按时间升序）。自动识别表头里的时间 / 价格列"""
    b = get(f"{BASE}{sym}/{sym}-{ym}.csv.gz")
    if not b:
        return []
    rows = []
    rd = csv.reader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(b)), "utf-8"))
    head = next(rd, None)
    if not head:
        return []
    low = [h.strip().lower() for h in head]
    ti = next((i for i, h in enumerate(low) if h in ("timestamp", "time", "ts", "trade_time")), None)
    pi = next((i for i, h in enumerate(low) if h == "price"), None)
    if ti is None or pi is None:   # 没有表头：第一行就是数据，按常见列序 id,timestamp,price,volume,side
        ti, pi = 1, 2
        rows.append(head)
    out = []
    for r in rows + list(rd):
        try:
            t = float(r[ti]); p = float(r[pi])
        except Exception:
            continue
        t = int(t * 1000) if t < 1e11 else int(t)   # 秒 → 毫秒
        out.append((t, p))
    out.sort()
    return out


def main():
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    budget = int(args[args.index("--minutes") + 1]) * 60 if "--minutes" in args else 280 * 60
    t_start = time.time()
    syms = sorted(s.rstrip("/") for s in links(BASE) if s.endswith("/") or "USDT" in s)
    syms = [s for s in syms if s.endswith("USDT") and len(s) > 4]
    print("归档里的 USDT 现货交易对：", len(syms))
    # 归档首月：BTCUSDT 最早的文件
    btc_files = sorted(f for f in links(f"{BASE}BTCUSDT/") if f.endswith(".csv.gz"))
    archive_first = re.search(r"(\d{4}-\d{2})", btc_files[0]).group(1) if btc_files else "2022-11"
    print("归档首月：", archive_first, "样例文件：", btc_files[:2])
    if btc_files:   # 打印文件开头几行，核对格式
        b = get(f"{BASE}BTCUSDT/{btc_files[0]}")
        if b:
            print("文件格式样例：", gzip.decompress(b)[:300].decode("utf-8", "replace").splitlines()[:3])
    btc_usd = LH.usd_closes("BTCUSDT")
    leg_at, leg_known, l2_at = LH.regime_tools()
    coins = []
    todo = syms[:limit] if limit else syms
    for i, sym in enumerate(todo):
        if time.time() - t_start > budget:
            print("到时间预算，停在", i)
            break
        base = sym[:-4]
        if base in LH.STABLE or (re.search(r"(UP|DOWN|BULL|BEAR|[235]L|[235]S)$", base) and len(base) > 3):
            continue
        files = sorted(f for f in links(f"{BASE}{sym}/") if f.endswith(".csv.gz"))
        months = sorted(set(re.findall(r"-(\d{4}-\d{2})\.csv\.gz", " ".join(files))))
        if not months:
            continue
        row = {"asset": base, "pair": sym, "quote": "USDT"}
        if months[0] <= archive_first:
            row.update(listed=None, excluded="归档开始前已上线")
            coins.append(row)
            continue
        tr = trades(sym, months[0])
        if not tr:
            continue
        t0 = tr[0][0]
        d0 = LH.day(t0)
        row["listed"] = d0
        row["open_minute_utc"] = dt.datetime.fromtimestamp(t0 / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if stock_suspect(base, d0):
            row["excluded"] = "疑似代币化股票"
        else:
            p15 = [p for t, p in tr if t < t0 + 15 * 60000]
            ref = p15[-1] if p15 else None
            # 日收盘：从上线月起最多取 4 个月文件，够 91 天
            closes = {}
            for ym in months[:4]:
                tt = tr if ym == months[0] else trades(sym, ym)
                for t, p in tt:
                    closes[LH.day(t)] = p
                if len(closes) >= 92:
                    break
            path = sorted(closes.items())
            if ref and path:
                row.update(ref_type="15m(逐笔)", ref_usd=ref, days=len(path))
                b15 = LH.minute_close("BTCUSDT", (t0 + 14 * 60000) // 60000 * 60000)
                for w in LH.WINDOWS:
                    if len(path) > w:
                        row[f"r{w}"] = round(path[w][1] / ref - 1, 4)
                        b1 = btc_usd.get(path[w][0])
                        if b15 and b1:
                            row[f"x{w}"] = round(row[f"r{w}"] - (b1 / b15 - 1), 4)
                win = path[1:91]
                if win:
                    hi = max(win, key=lambda p: p[1])
                    row["peak90"] = round(hi[1] / ref - 1, 4)
                    row["peak90_day"] = path.index(hi)
            if "r7" not in row:
                row["excluded"] = "数据不足（上线不满 7 天或取不到成交）"
        g, k = leg_at(d0), leg_known(d0)
        row.update(leg_dir=g and g["dir"], leg_regime=g and g["regime"], known_leg_dir=k and k["dir"],
                   known_leg_regime=k and k["regime"], l2_state=l2_at(d0), year=d0[:4])
        coins.append(row)
        if i % 50 == 0:
            print("  ", i, "/", len(todo), round((time.time() - t_start) / 60, 1), "分钟")
    ok = [r for r in coins if "excluded" not in r]
    groups = {}
    for name, keyf in (("全部", lambda r: "全部"), ("牛熊 × 涨跌腿（事后划分）", lambda r: f"{r['leg_regime']}·{r['leg_dir']}"),
                       ("当时已确认的腿", lambda r: f"{r['known_leg_regime']}·{r['known_leg_dir']}"),
                       ("L2 状态", lambda r: r["l2_state"]), ("年份", lambda r: r["year"])):
        sub = {}
        for r in ok:
            sub.setdefault(str(keyf(r)), []).append(r)
        groups[name] = {k: LH.summary(v) for k, v in sorted(sub.items())}
    out = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "exchange": "bybit", "exchange_first_day": archive_first,
           "survivorship": "官方归档含已下架交易对；只覆盖 " + archive_first + " 之后上线的币", "complete": not limit and len(coins) > 0,
           "n": {"symbols": len(syms), "coins": len(coins), "used": len(ok), "ref_15m": len(ok), "ref_1h": 0,
                 "before_archive": sum(1 for r in coins if r.get("excluded") == "归档开始前已上线")},
           "groups": groups, "coins": coins}
    json.dump(out, open(os.path.join(LH.OUT, "listing_history_bybit.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    a = groups["全部"].get("全部") or {}
    print("bybit", json.dumps(out["n"], ensure_ascii=False), "30天中位", (a.get("r30") or {}).get("p50"), "90天中位", (a.get("r90") or {}).get("p50"))
    for r in ok[:10]:
        print("  ", r["pair"], r["listed"], r["open_minute_utc"], "r7", r.get("r7"), "r30", r.get("r30"), "r90", r.get("r90"))


if __name__ == "__main__":
    main()
