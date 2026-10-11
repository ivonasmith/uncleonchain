# -*- coding: utf-8 -*-
"""
L3 筹码层·每日自动更新（网站用）
  依据《BTC筹码层L3研究》（2026-10-11）和《L3网页数据维度规格》：只有三条规则通过检验——
    A1 短期持有者成本 +1σ = 上方压力区（已验证·方向）
    A2 短期持有者成本 = 参考支撑（已验证·方向，2018 年后衰减）
    A3 低波动 + 筹码集中 = 大波动预警（已验证·方向，只说幅度不说方向）
  其余（筹码地图、短期持有者状态、交易所 / 大户 / 散户流向）只作同步描述。
  1) 取数：Coin Metrics 社区接口（价格、交易所余额与流量）+ bitview.space（STH 成本、成本线、STH 盈亏、地址分层、URPD）——都免费、无需账号
  2) 输出：l3_latest.json（今天的读数）、l3_history.json（每天追加一行，样本外记录，写入后不改、不回填）、
          l3_series.json（全历史，网站图和指标详情页用）、l3_conc.json（筹码集中度：2012 年起每周日一张 URPD 种子 + 每日追加）
用法：python l3/l3_daily.py   （GitHub Actions 每天 UTC 02:47，排在 L2 之后，见 .github/workflows/l3-daily.yml）
参数（研究里定的，改参数前先改研究文档）：
"""
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

SIGMA_WIN = 1460          # STH-MVRV 均值 / 标准差的滚动窗口（天）
VOL_TH = 40.0             # 30 天年化波动 < 40% 才算低波动
CONC_TH = 12.0            # 现价 ±5% 内持币占比 ≥ 12% 才算集中
ZONE = 0.02               # 压力区 / 碰线：±2%
BREAK = 0.03              # 有效突破：连续 3 天越过线 3%
FROM_SIDE = 0.05          # 碰线前 20 天内至少一天在线的另一侧 ≥ 5%
LOOK = 30                 # 碰线后看 30 天
SEED_FROM = "2012-01-01"  # 集中度种子起点（每周日一张）
BIN = math.log(1.0095)    # 筹码地图：约 0.95% 一档（对数分箱）

HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("L3_OUT_DIR", HERE / "output"))
CACHE = Path(os.environ.get("L3_CACHE_DIR", HERE / "cache"))
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)
CM = os.environ.get("L3_CM_BASE", "https://community-api.coinmetrics.io/v4")
BV = os.environ.get("L3_BV_BASE", "https://bitview.space")
UA = {"User-Agent": "Mozilla/5.0 (uncleonchain L3 daily)"}
OFFLINE = os.environ.get("L3_OFFLINE") == "1"          # 本地测试：只用缓存
SEED_BUDGET = float(os.environ.get("L3_SEED_MINUTES", "14")) * 60   # 每次运行补种子最多花多少秒（首跑分几天补完）
NOTES = []
SESSION = requests.Session()


def get(url, timeout=90, tries=3):
    if OFFLINE:
        raise RuntimeError("offline")
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


def today_utc():
    return pd.Timestamp(os.environ.get("L3_TODAY") or datetime.now(timezone.utc).date())


# ---------------------------------------------------------------- 取数
def fetch_cm():
    metrics = ["PriceUSD", "SplyExNtv", "FlowInExNtv", "FlowOutExNtv"]
    rows, url = [], (f"{CM}/timeseries/asset-metrics?assets=btc&metrics={','.join(metrics)}"
                     f"&frequency=1d&start_time=2010-07-01&page_size=10000")
    while url:
        j = get(url).json()
        rows += j.get("data", [])
        url = j.get("next_page_url")
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df.time).dt.tz_localize(None).dt.normalize()
    for m in metrics:
        if m not in df:
            df[m] = np.nan
    return df.set_index("date")[metrics].apply(pd.to_numeric, errors="coerce").sort_index()


# bitview 日线序列 → 列名；同一指标可能有几种命名，依次试
BV_SERIES = {
    "price_close": ("bv_price", []),
    "sth_realized_price": ("sth_rp", []),
    "true_market_mean": ("tmmp", []),
    "realized_price": ("rp", []),
    "lth_realized_price": ("lth_rp", []),
    "sth_supply_in_profit": ("sth_sip", ["sth_supply_in_profit_btc"]),
    "sth_supply": ("sth_supply", ["sth_supply_btc"]),
    "sth_sopr_24h": ("sth_sopr", ["sth_sopr"]),
    "sth_asopr_24h": ("sth_asopr", ["sth_asopr"]),
    "addrs_1k_btc_to_10k_btc_supply": ("a_1k_10k", []),
    "addrs_10k_btc_to_100k_btc_supply": ("a_10k_100k", []),
    "addrs_over_100k_btc_supply": ("a_100k", []),
    "addrs_under_1btc_supply": ("a_u1", []),
}


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
    for name, (col, alts) in BV_SERIES.items():
        got = None
        for cand in [name] + alts:
            try:
                got = fetch_bv_values(cand)
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
    # 日期对齐（和 L2 同一套）：bitview 数组不带日期，末尾对齐后用价格和 Coin Metrics 比对，找误差最小的偏移
    n = len(vals["bv_price"])
    today = today_utc()
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
    status = {"coinmetrics": "ok", "bitview": "ok", "bitview_missing": [], "urpd": "ok"}
    try:
        cm = fetch_cm()
        cm.to_csv(CACHE / "cm.csv")
    except Exception as e:
        if not (CACHE / "cm.csv").exists():
            raise SystemExit(f"Coin Metrics 取不到、也没有缓存：{e}")
        status["coinmetrics"] = f"失败，用缓存：{e}"
        cm = pd.read_csv(CACHE / "cm.csv", parse_dates=["date"]).set_index("date")
    try:
        bv, miss, err = fetch_bv(cm.PriceUSD.dropna())
        status["bitview_missing"] = miss
        if err > 0.02:
            status["bitview"] = f"日期对齐误差偏大（{err * 100:.1f}%），请检查"
        old = pd.read_csv(CACHE / "bv.csv", parse_dates=["date"]).set_index("date") if (CACHE / "bv.csv").exists() else None
        if old is not None:
            for c in old.columns:
                if c not in bv.columns:
                    bv[c] = old[c].reindex(bv.index)
        bv.index.name = "date"
        bv.to_csv(CACHE / "bv.csv")
    except Exception as e:
        if not (CACHE / "bv.csv").exists():
            raise SystemExit(f"bitview 取不到、也没有缓存：{e}")
        status["bitview"] = f"失败，用缓存：{e}"
        bv = pd.read_csv(CACHE / "bv.csv", parse_dates=["date"]).set_index("date")
    return cm, bv, status


# ---------------------------------------------------------------- URPD（筹码分布）
def urpd_url(date=None, agg="log500"):
    return f"{BV}/api/urpd/all{'/' + date if date else ''}?agg={agg}"


def urpd_buckets(j):
    """→ (日期, 收盘价, [(价格下限, 持币量)])；剔除价格为 0 的远古币。"""
    bs = j.get("buckets") or []
    rows = [(float(b["price_floor"]), float(b["supply"])) for b in bs if b.get("price_floor") and float(b["price_floor"]) > 0.01 and b.get("supply")]
    return j.get("date"), float(j.get("close") or 0), rows


def concentration(close, rows):
    tot = sum(s for _, s in rows)
    if not tot or not close:
        return None
    near = sum(s for p, s in rows if close * 0.95 <= p <= close * 1.05)
    return near / tot * 100


def fetch_urpd_latest():
    p = CACHE / "urpd_latest.json"
    try:
        j = get(urpd_url(), timeout=120).json()
        json.dump(j, open(p, "w"))
        return j, "ok"
    except Exception as e:
        if p.exists():
            return json.load(open(p)), f"失败，用缓存：{e}"
        return None, f"失败：{e}"


def update_conc(latest_j):
    """l3_conc.json：{日期: 集中度%}。种子 = 2012 年起每周日一张（可续跑，每次最多花 SEED_BUDGET 秒）；每天再追加当天的。"""
    p = OUT / "l3_conc.json"
    conc = json.load(open(p, encoding="utf-8")) if p.exists() else {}
    if latest_j:
        d, close, rows = urpd_buckets(latest_j)
        c = concentration(close, rows)
        if d and c is not None:
            conc[d] = round(c, 3)
    if not OFFLINE:
        try:
            dates = get(f"{BV}/api/urpd/all/dates", timeout=60).json()
            want = [d for d in dates if d >= SEED_FROM and pd.Timestamp(d).dayofweek == 6 and d not in conc]
            t0, n = time.time(), 0
            for d in want:
                if time.time() - t0 > SEED_BUDGET:
                    break
                try:
                    _, close, rows = urpd_buckets(get(urpd_url(d), timeout=60, tries=2).json())
                    c = concentration(close, rows)
                    if c is not None:
                        conc[d] = round(c, 3)
                        n += 1
                except Exception:
                    continue
            left = len([d for d in want if d not in conc])
            if n or left:
                NOTES.append(f"筹码集中度种子：本次补 {n} 张，还差 {left} 张")
        except Exception as e:
            NOTES.append(f"URPD 日期列表取不到：{e}")
    conc = dict(sorted(conc.items()))
    json.dump(conc, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    s = pd.Series({pd.Timestamp(k): v for k, v in conc.items()}, dtype=float).sort_index()
    return s


def chip_map(latest_j, price):
    """B1：最新一张 URPD → 约 0.95% 一档；按 ±1% 平滑后在现价 ±50% 内排名：前 5% = 密集区，后 30% = 稀疏区；输出现价 ±30%。"""
    if not latest_j:
        return None
    d, close, rows = urpd_buckets(latest_j)
    if not rows:
        return None
    acc = {}
    for p_, s in rows:
        k = math.floor(math.log(p_) / BIN)
        acc[k] = acc.get(k, 0.0) + s
    lo50, hi50 = math.floor(math.log(price * 0.5) / BIN), math.floor(math.log(price * 1.5) / BIN)
    ks = list(range(lo50, hi50 + 1))
    raw_ = np.array([acc.get(k, 0.0) for k in ks])
    sm = np.convolve(raw_, np.ones(3) / 3, mode="same")          # ±1 档 ≈ ±1%
    hi_cut, lo_cut = np.quantile(sm, 0.95), np.quantile(sm, 0.30)
    tot = sum(s for _, s in rows)
    bins = []
    for k, r, m in zip(ks, raw_, sm):
        lo, hi = math.exp(k * BIN), math.exp((k + 1) * BIN)
        if hi < price * 0.7 or lo > price * 1.3:
            continue
        cls = "dense" if m >= hi_cut else ("sparse" if m <= lo_cut else "mid")
        bins.append({"lo": round(lo, 2), "hi": round(hi, 2), "supply": round(float(r), 1), "cls": cls})
    walls, cur = [], None
    for b in bins:                                              # 相邻的密集档合成一段（描述用）
        if b["cls"] == "dense":
            if cur and abs(cur["hi"] - b["lo"]) < 1:
                cur["hi"], cur["supply"] = b["hi"], cur["supply"] + b["supply"]
            else:
                cur = {"lo": b["lo"], "hi": b["hi"], "supply": b["supply"]}
                walls.append(cur)
        else:
            cur = None
    for w in walls:
        w["share_pct"] = round(w["supply"] / tot * 100, 2)
        w["supply"] = round(w["supply"])
    return {"date": d, "close": close, "total_supply": round(tot), "bins": bins, "dense_ranges": walls}


# ---------------------------------------------------------------- 计算
def build(cm, bv, conc):
    idx = cm.PriceUSD.dropna().index
    if len(bv) and "bv_price" in bv:              # Coin Metrics 当天还没更新：用 bitview 价格补最后一两天
        extra = bv.bv_price[bv.index > idx.max()].dropna()
        idx = idx.union(extra.index[:2])
    bv = bv.reindex(idx)
    F = pd.DataFrame(index=idx)
    F["price"] = cm.PriceUSD.reindex(idx).fillna(bv.get("bv_price"))
    for c in ("sth_rp", "tmmp", "rp", "lth_rp"):
        F[c] = bv.get(c)
    F = F.ffill(limit=3)
    F["sth_mvrv"] = F.price / F.sth_rp
    roll = F.sth_mvrv.rolling(SIGMA_WIN, min_periods=365)
    F["k1s"] = roll.mean() + roll.std()
    F["p1s"] = F.sth_rp * F.k1s
    F["p1s_gap"] = (F.p1s / F.price - 1) * 100
    F["sth_gap"] = (F.sth_rp / F.price - 1) * 100
    lr = np.log(F.price).diff()
    F["vol30"] = lr.rolling(30, min_periods=25).std() * math.sqrt(365) * 100
    F["conc"] = conc.reindex(idx) if len(conc) else np.nan
    cf = F.conc.ffill(limit=7)                    # 种子是每周一张：一周内沿用最近一张
    F["warn"] = np.where(cf.notna() & F.vol30.notna(), ((F.vol30 < VOL_TH) & (cf >= CONC_TH)).astype(float), np.nan)
    if {"sth_sip", "sth_supply"} <= set(bv.columns):
        F["sth_psip"] = bv.sth_sip / bv.sth_supply * 100
    for c, k in (("sth_sopr", "sth_sopr7"), ("sth_asopr", "sth_asopr7")):
        if c in bv:
            F[k] = bv[c].rolling(7, min_periods=5).mean()
    F["ex_bal"] = cm.SplyExNtv.reindex(idx)
    F["ex_bal4w"] = (F.ex_bal / F.ex_bal.shift(28) - 1) * 100
    F["ex_net4w"] = (cm.FlowInExNtv - cm.FlowOutExNtv).reindex(idx).rolling(28, min_periods=28).sum()
    wh = [c for c in ("a_1k_10k", "a_10k_100k", "a_100k") if c in bv]
    if len(wh) == 3:
        F["whale"] = bv[wh].sum(axis=1, min_count=3)
        F["whale4w"] = F.whale - F.whale.shift(28)
        F["whale4w_pct"] = (F.whale / F.whale.shift(28) - 1) * 100
    if "a_u1" in bv:
        F["retail"] = bv.a_u1
        F["retail4w"] = F.retail - F.retail.shift(28)
        F["retail4w_pct"] = (F.retail / F.retail.shift(28) - 1) * 100
    return F


def touches(F, line, side, start="2012-01-01"):
    """碰线事件（研究 §3.1）。side='res'：从下方涨到线 ±2%（之前一天在线下方 >2%、过去 20 天至少一天在线下方 ≥5%）；
    之后 30 天内连续 3 天收盘越过线 3% = 被突破，否则守住。side='sup' 镜像。同一条线同一方向 20 天内只记一次。"""
    p, l = F.price.values, F[line].values
    ds = F.index
    out, last = [], -999
    s0 = ds.searchsorted(pd.Timestamp(start))
    for i in range(max(s0, 21), len(p)):
        if not (np.isfinite(l[i]) and np.isfinite(l[i - 1])) or i - last < 20:
            continue
        r = p[i] / l[i] - 1
        if abs(r) > ZONE:
            continue
        rp_ = p[i - 1] / l[i - 1] - 1
        win = p[i - 20:i] / l[i - 20:i] - 1
        if side == "res" and not (rp_ < -ZONE and np.nanmin(win) <= -FROM_SIDE):
            continue
        if side == "sup" and not (rp_ > ZONE and np.nanmax(win) >= FROM_SIDE):
            continue
        last = i
        res, rd, run = "open", None, 0
        for j in range(i + 1, min(i + 1 + LOOK, len(p))):
            x = p[j] / l[j] - 1 if np.isfinite(l[j]) else 0
            run = run + 1 if (x > BREAK if side == "res" else x < -BREAK) else 0
            if run >= 3:
                res, rd = "broken", str(ds[j].date())
                break
        if res == "open" and i + LOOK < len(p):
            res = "held"
        out.append({"date": str(ds[i].date()), "price": round(float(p[i]), 2), "line": round(float(l[i]), 2), "result": res, "result_date": rd})
    return out


def position(f):
    p, a, s = f.price, f.p1s, f.sth_rp
    if p >= a * (1 + ZONE):
        return "above", "在 +1σ 压力区上方（已冲过）", "Above the +1σ pressure zone (broke through)"
    if p >= a * (1 - ZONE):
        return "in_zone", "正在 +1σ 压力区里", "Inside the +1σ pressure zone"
    if p >= s:
        return "between", "在 STH 成本和 +1σ 压力区之间", "Between the STH cost and the +1σ pressure zone"
    return "below", "在 STH 成本下方（短期持有者整体浮亏）", "Below the STH cost (short-term holders under water)"


def r(v, d=2):
    return None if v is None or (isinstance(v, float) and not np.isfinite(v)) or pd.isna(v) else round(float(v), d)


def _sig(v):
    if v is None or pd.isna(v) or np.isinf(v):
        return None
    v = float(v)
    if v == 0:
        return 0
    return round(v, 5 - int(np.floor(np.log10(abs(v)))))


SERIES = ["price", "sth_rp", "p1s", "tmmp", "rp", "lth_rp", "p1s_gap", "sth_gap", "sth_mvrv", "vol30", "conc", "warn",
          "sth_psip", "sth_sopr7", "sth_asopr7", "ex_bal", "ex_bal4w", "ex_net4w", "whale", "whale4w", "whale4w_pct", "retail", "retail4w", "retail4w_pct"]


def write_series(F, t):
    start = F.price.dropna().index[0]
    idx = pd.date_range(start, t, freq="D")
    G = F.reindex(idx)
    out = {"start": str(start.date()), "end": str(t.date()), "freq": "D", "series": {}, "valid_from": {}}
    for k in SERIES:
        s = G[k] if k in G else pd.Series(np.nan, index=idx)
        out["series"][k] = [_sig(v) for v in s.tolist()]
        fv = s.first_valid_index()
        out["valid_from"][k] = str(fv.date()) if fv is not None else None
    json.dump(out, open(OUT / "l3_series.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


def append_history(row):
    """样本外记录：每个数据日只记第一次，写入后不改、不回填。"""
    p = OUT / "l3_history.json"
    h = json.load(open(p, encoding="utf-8")) if p.exists() else []
    if not any(x["date"] == row["date"] for x in h):
        h.append(row)
        h.sort(key=lambda x: x["date"])
        json.dump(h, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def fmt0(v):
    return "—" if v is None else f"{v:,.0f}"


def main():
    cm, bv, status = load_or_fetch()
    uj, ust = fetch_urpd_latest()
    status["urpd"] = ust
    conc = update_conc(uj)
    F = build(cm, bv, conc)
    F = F[F.price.notna() & F.sth_rp.notna()]
    t = F.index[-1]
    f = F.iloc[-1]
    code, pos_zh, pos_en = position(f)
    tz1 = touches(F, "p1s", "res")
    tz2 = touches(F, "sth_rp", "sup")
    cser = conc.dropna()
    c_now = float(cser.iloc[-1]) if len(cser) else None
    c_date = str(cser.index[-1].date()) if len(cser) else None
    c22 = cser[cser.index >= "2022-01-01"]
    c_rank = round(float((c22 <= c_now).mean() * 100)) if c_now is not None and len(c22) > 20 else None
    vol = r(f.vol30, 1)
    warn_on = bool(vol is not None and c_now is not None and vol < VOL_TH and c_now >= CONC_TH)
    if c_date and (t - pd.Timestamp(c_date)).days > 7:
        warn_on, NOTES[:0] = False, [f"筹码集中度最新一张是 {c_date}，超过 7 天，预警按「不亮」处理"]
    price = float(f.price)
    p1s, sth = float(f.p1s), float(f.sth_rp)
    st_zh = {"above": "已冲过", "in_zone": "正在压力区", "between": "在下方", "below": "在下方"}[code]
    st_en = {"above": "broken through", "in_zone": "in the zone", "between": "below", "below": "below"}[code]
    g = lambda v: None if v is None else round((v / price - 1) * 100, 1)
    stale = [k for k, v in status.items() if k != "bitview_missing" and v != "ok"] + (["bitview 部分序列"] if status["bitview_missing"] else [])
    line_zh = (f"L3：STH 成本 {fmt0(sth)}｜+1σ 压力区 {fmt0(p1s)}（{g(p1s):+.1f}%）｜大波动预警 {'亮' if warn_on else '不亮'}"
               f"（波动 {vol:.0f}%，集中度 {c_now:.1f}%）" if vol is not None and c_now is not None else
               f"L3：STH 成本 {fmt0(sth)}｜+1σ 压力区 {fmt0(p1s)}（{g(p1s):+.1f}%）｜大波动预警 —（集中度暂缺）")
    line_en = (f"L3: STH cost {fmt0(sth)} | +1σ pressure zone {fmt0(p1s)} ({g(p1s):+.1f}%) | large-move warning {'ON' if warn_on else 'off'}"
               f" (vol {vol:.0f}%, concentration {c_now:.1f}%)" if vol is not None and c_now is not None else
               f"L3: STH cost {fmt0(sth)} | +1σ pressure zone {fmt0(p1s)} ({g(p1s):+.1f}%) | large-move warning — (concentration missing)")
    latest = dict(
        updated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), data_date=str(t.date()), price=r(price),
        position=dict(code=code, zh=pos_zh, en=pos_en),
        p1s=dict(value=r(p1s), lo=r(p1s * (1 - ZONE)), hi=r(p1s * (1 + ZONE)), pct_from_price=g(p1s), k=r(f.k1s, 3),
                 status_zh=st_zh, status_en=st_en, touches=tz1[-5:], n_touches=len(tz1),
                 hold_rate_zh="碰到后 30 天不被突破 63%（对照 42%）；2018 年后 72%（对照 44%）",
                 hold_rate_en="Not broken within 30 days of a touch 63% of the time (placebo 42%); since 2018 72% (44%)", evidence="已验证·方向"),
        sth=dict(value=r(sth), pct_from_price=g(sth), touches=tz2[-5:], n_touches=len(tz2),
                 hold_rate_zh="回落到这里后 30 天守住 60.5%（对照 38.5%）；2018 年后 47%（对照 41%），接近随机",
                 hold_rate_en="Held within 30 days of a pullback 60.5% (placebo 38.5%); since 2018 47% (41%) — close to random",
                 evidence="已验证·方向（近年衰减）"),
        sth_13=r(sth * 1.3),
        warning=dict(on=warn_on, vol30=vol, vol_th=VOL_TH, conc=r(c_now, 1), conc_th=CONC_TH, conc_date=c_date, conc_rank_2022=c_rank,
                     evidence="已验证·方向",
                     text_zh="接下来 30 天大概率出现 15% 左右的单边，方向不定。只说幅度，不说方向。",
                     text_en="A one-way move of about 15% within 30 days is more likely than usual; direction unknown. Magnitude only, not direction."),
        lines=dict(tmmp=r(f.tmmp), rp=r(f.rp), lth_rp=r(f.lth_rp)),
        sth_state=dict(sth_mvrv=r(f.sth_mvrv, 3), sth_psip=r(f.get("sth_psip"), 1), sth_sopr7=r(f.get("sth_sopr7"), 3),
                       sth_asopr7=r(f.get("sth_asopr7"), 3), trend_zone=bool(pd.notna(f.sth_mvrv) and f.sth_mvrv >= 1.3)),
        flows=dict(ex_bal=r(f.get("ex_bal"), 0), ex_bal4w_pct=r(f.get("ex_bal4w"), 2), ex_net4w=r(f.get("ex_net4w"), 0),
                   whale=r(f.get("whale"), 0), whale4w=r(f.get("whale4w"), 0), whale4w_pct=r(f.get("whale4w_pct"), 2),
                   retail=r(f.get("retail"), 0), retail4w=r(f.get("retail4w"), 0), retail4w_pct=r(f.get("retail4w_pct"), 2)),
        chip_map=chip_map(uj, price),
        daily_line_zh=line_zh, daily_line_en=line_en,
        data_status=dict(stale=bool(stale), detail=status, notes=NOTES),
        params=dict(sigma_window_days=SIGMA_WIN, vol_threshold=VOL_TH, conc_threshold=CONC_TH, zone=ZONE, break_=BREAK, look_days=LOOK),
        method="依据《BTC筹码层L3研究》（2026-10-11）：只有 STH 成本 +1σ（压力区）、STH 成本（参考支撑）、低波动 + 筹码集中（大波动预警）三条通过检验，最高到「已验证·方向」；其余只作同步描述。数据为 UTXO 口径，和 Glassnode 等平台数值会有差异。",
    )
    json.dump(latest, open(OUT / "l3_latest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_series(F, t)
    append_history(dict(date=str(t.date()), price=r(price), sth_rp=r(sth), p1s=r(p1s), position=code, vol30=vol,
                        conc=r(c_now, 2), conc_date=c_date, warning=warn_on, recorded_utc=latest["updated_utc"]))
    print(line_zh)
    print("位置：", pos_zh, "｜数据状态：", latest["data_status"])


if __name__ == "__main__":
    main()
