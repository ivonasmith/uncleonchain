# -*- coding: utf-8 -*-
"""
L4 情绪与衍生品层·每日自动更新（网站用）
  依据：项目文档《BTC情绪衍生品层L4研究》（2026-10-13）。只有一条规则改动作，其余是温度描述和观察项。
  1) 取数（都能在 GitHub Actions 的美国机房访问；Binance / Bybit 接口在美国访问不了，不用）
       价格、流通量、交易所余额：Coin Metrics 社区接口
       资金费率（按优先级，第一个取到的为准）：Coinalyze 的 Binance BTCUSDT 永续（需要免费 key，放在 COINALYZE_KEY）→ BitMEX XBTUSD → OKX BTC-USDT-SWAP → Deribit BTC-PERPETUAL
            换源时用和历史重叠的日子自动校准比例，校准相关不够就不用这个源
       聚合 OI、聚合清算：Coinalyze（同一篮子主流合约，和研究一致；没有 key 就跳过这两项）
       季度合约升水：Deribit（研究用的是 Binance 币本位季度合约，2026-10-13 起换源，历史分位仍用研究数据）
       CME 升水：Yahoo BTC=F ÷ Coinbase 美东 16 点前后现货
       恐慌贪婪：alternative.me；DVOL：Deribit；CME 杠杆基金净头寸：CFTC
  2) 计算：资金费率 30 日均（年化）< 0 = 信号（已验证·方向）；其余读数给过去 730 天分位，分档描述；观察项（假设）只列出
  3) 输出：output/l4_latest.json（今日结论）、output/l4_history.json（近 400 天）
用法：python l4_daily.py
某个数据源暂时取不到时：用上次缓存继续算，并在 json 里标 data_status.stale = true。
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("L4_OUT_DIR", HERE / "output"))
CACHE = Path(os.environ.get("L4_CACHE_DIR", HERE / "cache"))
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)
CZ_KEY = os.environ.get("COINALYZE_KEY", "").strip()
CM = "https://community-api.coinmetrics.io/v4"
CZ = "https://api.coinalyze.net/v1"
UA = {"User-Agent": "Mozilla/5.0 (uncleonchain L4 daily)"}
S = requests.Session()
NOTES, STATUS = [], {}

# ---------------- 研究定下的参数（改动前先改研究文档） ----------------
PCT_WIN, PCT_MIN = 730, 365             # 滚动分位窗口：过去 730 天，至少 365 个观测
OI_BASKET = ['BTC-PERPETUAL.2', 'BTC-USD.8', 'BTCUSD.6', 'BTCUSDT.6', 'BTCUSDT_PERP.3', 'BTCUSDT_PERP.4', 'BTCUSDT_PERP.A',
             'BTCUSDT_PERP.F', 'BTCUSD_PERP.3', 'BTCUSD_PERP.4', 'BTCUSD_PERP.A', 'BTC_USDC-PERPETUAL.2']
LIQ_BASKET = ['BTCUSD.6', 'BTCUSDT.6', 'BTCUSDT_PERP.3', 'BTCUSDT_PERP.4', 'BTCUSDT_PERP.A', 'BTCUSDT_PERP.F',
              'BTCUSD_PERP.3', 'BTCUSD_PERP.4', 'BTCUSD_PERP.A']
BANDS = [(90, "过热", "overheated"), (70, "偏热", "warm"), (30, "中性", "normal"), (10, "偏冷", "cool"), (-1, "极冷", "cold")]

SIGNAL_EVIDENCE = dict(
    name_zh="资金费率 30 日均转负（空头拥挤）", name_en="30-day avg funding below zero (crowded shorts)", grade="已验证·方向",
    stat_zh="31 次独立事件，之后 30 天上涨 74%（同年代同周期状态对照 58%，p=0.054），平均多涨 7.8 个百分点，回撤更浅；三个年代方向一致，72 组参数 68 组同向。L2 为熊市时效果弱（8 次 50%）",
    rule_zh="不开新空；L2 不在熊市时，允许在 L1 风险预算内分批加。不放大风险预算", ref="§4.1、§5.1")
THERMO = [  # key, 中文名, 英文名, 单位, 小数位, 等级, 一句话证据
    ("fund_ma30", "资金费率 30 日均（年化）", "Funding 30d avg (ann.)", "%", 1, "描述",
     "费率高不预示回调：高分位之后方向在年代间翻转（2018-21 超额 −14.3，2022-26 +7.6）"),
    ("fund_ma7", "资金费率 7 日均（年化）", "Funding 7d avg (ann.)", "%", 1, "描述", "同上，7 日均噪声更大"),
    ("qbasis", "季度合约年化升水", "Quarterly basis (ann.)", "%", 1, "描述", "升水高不是顶部信号（9 次超额 +6.0）"),
    ("cme_prem", "CME 升水", "CME premium", "%", 2, "描述", "升水高之后无超额（42 次 −0.2）"),
    ("agg_oi_chg7", "全市场 OI 7 日变化（BTC 计）", "Aggregated OI 7d change (BTC)", "%", 1, "描述",
     "OI 快速堆积之后没有更深回撤，快速出清之后也没有反弹"),
    ("agg_oi_mcap", "全市场 OI ÷ 市值", "Aggregated OI / market cap", "%", 2, "描述", "杠杆率高样本太少（8 次）"),
    ("fng", "恐慌贪婪指数", "Fear & Greed", "", 0, "描述", "极值反着做不成立：极度贪婪之后反而偏强"),
    ("dvol", "DVOL（30 天隐含波动）", "DVOL (30d implied vol)", "", 1, "描述", "低隐含波动之后不是大行情，反而更平静"),
]
WATCH_EVIDENCE = {
    "big_liq": ("大清算日之后偏强", "Strength after big liquidation days", "单日清算 ÷ 全市场 OI 进入过去两年高 10%：25 次，之后 30 天上涨 72%（对照 51%，p=0.03）。只有 2022 年后数据，清算数据被交易所低估"),
    "cme_low": ("CME 升水低之后偏弱", "Weakness after low CME premium", "进入低 10%：2022-26 年 23 次，上涨 30%（对照 53%）；2018-21 年没有这个现象"),
    "qbasis_low": ("季度合约贴水 / 低升水之后偏强", "Strength after low/negative quarterly basis", "升水 < 0：7 次，上涨 71%（对照 49%）；低 10% 分位 2024 年后 12 次 75%"),
    "dvol_low": ("低隐含波动之后略偏弱", "Slightly weaker after low DVOL", "DVOL 低 10%：24 次，上涨 42%（对照 58%），之后波动更小"),
    "elr_low": ("预计杠杆率低之后偏强", "Strength after low estimated leverage", "聚合 OI ÷ 交易所余额低 10%：10 次，上涨 80%（对照 58%），只有 2022 年后"),
    "lev_drop": ("CME 杠杆基金大幅加空之后偏弱", "Weakness after leveraged funds add shorts", "净头寸 4 周变化低 10%：13 次，上涨 31%（对照 52%）；可能主要反映基差套利盘进出"),
}


def get(url, params=None, headers=None, timeout=60, tries=3):
    if os.environ.get("L4_OFFLINE"):                     # 本地离线测试用
        raise RuntimeError("离线测试")
    last = None
    for i in range(tries):
        try:
            r = S.get(url, params=params, headers={**UA, **(headers or {})}, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
            if r.status_code in (401, 403, 451):
                break
        except Exception as e:
            last = str(e)[:100]
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url.split('?')[0][:80]} → {last}")


def today_utc():
    return pd.Timestamp(os.environ.get("L4_TODAY") or datetime.now(timezone.utc).date())


def daily(ts_ms, values, how="sum"):
    s = pd.Series(values, index=pd.to_datetime(ts_ms, unit="ms")).astype(float)
    g = s.groupby(s.index.normalize())
    return g.sum() if how == "sum" else g.mean()


# ---------------- 取数（每个函数返回按日期索引的 Series / DataFrame，只取最近一段） ----------------
def f_coinmetrics(days=200):
    t0 = (today_utc() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    j = get(f"{CM}/timeseries/asset-metrics", {"assets": "btc", "metrics": "PriceUSD,SplyCur,SplyExNtv",
                                               "frequency": "1d", "start_time": t0, "page_size": 10000}).json()
    df = pd.DataFrame(j["data"])
    df.index = pd.to_datetime(df.time).dt.tz_localize(None).dt.normalize()
    out = pd.DataFrame({"price": pd.to_numeric(df.PriceUSD, errors="coerce"), "supply": pd.to_numeric(df.SplyCur, errors="coerce")})
    if "SplyExNtv" in df:
        out["ex_bal"] = pd.to_numeric(df.SplyExNtv, errors="coerce")
    return out


def f_coinbase_daily(days=120):
    t1 = today_utc() + pd.Timedelta(days=1)
    t0 = t1 - pd.Timedelta(days=days)
    d = get("https://api.exchange.coinbase.com/products/BTC-USD/candles",
            {"granularity": 86400, "start": t0.isoformat(), "end": t1.isoformat()}).json()
    df = pd.DataFrame(d, columns=["ts", "low", "high", "open", "close", "volume"])
    return pd.Series(df.close.values, index=pd.to_datetime(df.ts, unit="s").dt.normalize()).sort_index()


def fund_coinalyze():
    if not CZ_KEY:
        raise RuntimeError("没有 COINALYZE_KEY")
    t1 = int(time.time()); t0 = t1 - 150 * 86400
    d = get(f"{CZ}/funding-rate-history", {"symbols": "BTCUSDT_PERP.A", "interval": "daily", "from": t0, "to": t1},
            headers={"api_key": CZ_KEY}).json()
    h = pd.DataFrame(d[0]["history"])
    return pd.Series(h.c.astype(float).values, index=pd.to_datetime(h.t, unit="s").dt.normalize())   # 单位由校准处理


def fund_bitmex():
    t0 = (today_utc() - pd.Timedelta(days=150)).strftime("%Y-%m-%d")
    d = get("https://www.bitmex.com/api/v1/funding", {"symbol": "XBTUSD", "count": 500, "startTime": t0}).json()
    df = pd.DataFrame(d)
    return daily(pd.to_datetime(df.timestamp).astype("int64") // 10**6, df.fundingRate)


def fund_okx():
    rows, after = [], ""
    for _ in range(6):
        p = {"instId": "BTC-USDT-SWAP", "limit": 100}
        if after:
            p["after"] = after
        d = get("https://www.okx.com/api/v5/public/funding-rate-history", p).json().get("data", [])
        if not d:
            break
        rows += d
        after = d[-1]["fundingTime"]
        time.sleep(0.3)
    df = pd.DataFrame(rows)
    rate = pd.to_numeric(df.get("realizedRate", df.fundingRate), errors="coerce").fillna(pd.to_numeric(df.fundingRate))
    return daily(df.fundingTime.astype("int64"), rate)


def fund_deribit():
    t1 = int(time.time() * 1000); t0 = t1 - 150 * 86400 * 1000
    d = get("https://www.deribit.com/api/v2/public/get_funding_rate_history",
            {"instrument_name": "BTC-PERPETUAL", "start_timestamp": t0, "end_timestamp": t1}).json()["result"]
    df = pd.DataFrame(d)
    return daily(df.timestamp, df.interest_8h, how="mean") * 3


FUND_SOURCES = [("Coinalyze·Binance BTCUSDT", fund_coinalyze), ("BitMEX XBTUSD", fund_bitmex),
                ("OKX BTC-USDT-SWAP", fund_okx), ("Deribit BTC-PERPETUAL", fund_deribit)]


def cz_history(endpoint, symbols, extra=None):
    if not CZ_KEY:
        raise RuntimeError("没有 COINALYZE_KEY")
    t1 = int(time.time()); t0 = t1 - 150 * 86400
    rows = []
    for i in range(0, len(symbols), 20):
        d = get(f"{CZ}/{endpoint}", {"symbols": ",".join(symbols[i:i + 20]), "interval": "daily", "from": t0, "to": t1,
                                     **(extra or {})}, headers={"api_key": CZ_KEY}).json()
        for s in d:
            for h in s.get("history", []):
                rows.append(dict(symbol=s["symbol"], **h))
        time.sleep(1.6)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df.t, unit="s").dt.normalize()
    return df


def f_coinalyze_oi_liq():
    oi = cz_history("open-interest-history", OI_BASKET, {"convert_to_usd": "true"})
    n = oi.groupby("date").symbol.nunique()
    oi_usd = oi.groupby("date").c.sum()[n == len(OI_BASKET)]           # 篮子不齐的日子不算，避免跳变
    lq = cz_history("liquidation-history", LIQ_BASKET, {"convert_to_usd": "true"})
    return pd.DataFrame({"agg_oi_usd": oi_usd, "liq_long": lq.groupby("date").l.sum(), "liq_short": lq.groupby("date").s.sum()})


def f_deribit_qbasis():
    idx = get("https://www.deribit.com/api/v2/public/get_index_price", {"index_name": "btc_usd"}).json()["result"]["index_price"]
    fut = get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency", {"currency": "BTC", "kind": "future"}).json()["result"]
    insts = get("https://www.deribit.com/api/v2/public/get_instruments", {"currency": "BTC", "kind": "future", "expired": "false"}).json()["result"]
    exp = {i["instrument_name"]: i["expiration_timestamp"] for i in insts if i.get("settlement_period") in ("quarter", "month")}
    now = time.time() * 1000
    best = None
    for f in fut:
        nm = f["instrument_name"]
        if nm not in exp or "PERPETUAL" in nm:
            continue
        dte = (exp[nm] - now) / 86400000
        if 28 <= dte <= 120 and f.get("mark_price"):
            b = (f["mark_price"] / idx - 1) * 365 / dte * 100
            if best is None or dte < best[0]:
                best = (dte, b)
    if best is None:
        raise RuntimeError("没有剩余 28~120 天的季度合约")
    return pd.Series({today_utc(): best[1]})


def f_cme():
    j = get("https://query1.finance.yahoo.com/v8/finance/chart/BTC%3DF", {"range": "3mo", "interval": "1d"}).json()["chart"]["result"][0]
    fut = pd.Series(j["indicators"]["quote"][0]["close"], index=pd.to_datetime(j["timestamp"], unit="s").normalize()).dropna()
    fut = fut[~fut.index.duplicated(keep="last")]
    rows = []
    t1 = pd.Timestamp.now(tz="UTC").tz_localize(None).floor("h")
    for k in range(4):                                   # Coinbase 小时线每次最多 300 根
        a, b = t1 - pd.Timedelta(hours=300 * (k + 1)), t1 - pd.Timedelta(hours=300 * k)
        rows += get("https://api.exchange.coinbase.com/products/BTC-USD/candles",
                    {"granularity": 3600, "start": a.isoformat(), "end": b.isoformat()}).json()
        time.sleep(0.4)
    h = pd.DataFrame(rows, columns=["ts", "low", "high", "open", "close", "volume"]).drop_duplicates("ts")
    h["time"] = pd.to_datetime(h.ts, unit="s")
    ref = h[h.time.dt.hour == 20].set_index(h[h.time.dt.hour == 20].time.dt.normalize()).close
    return ((fut / ref.reindex(fut.index)) - 1).dropna() * 100


def f_fng():
    d = get("https://api.alternative.me/fng/", {"limit": 200, "format": "json"}).json()["data"]
    return pd.Series([float(x["value"]) for x in d], index=pd.to_datetime([int(x["timestamp"]) for x in d], unit="s").normalize())


def f_dvol():
    t1 = int(time.time() * 1000); t0 = t1 - 200 * 86400 * 1000
    d = get("https://www.deribit.com/api/v2/public/get_volatility_index_data",
            {"currency": "BTC", "start_timestamp": t0, "end_timestamp": t1, "resolution": "1D"}).json()["result"]["data"]
    return pd.Series([r[4] for r in d], index=pd.to_datetime([r[0] for r in d], unit="ms").normalize())


def f_cftc():
    for ds in ("gpe5-46if", "6dca-aqww"):
        try:
            d = get(f"https://publicreporting.cftc.gov/resource/{ds}.json",
                    {"cftc_contract_market_code": "133741", "$limit": 30, "$order": "report_date_as_yyyy_mm_dd DESC"}).json()
            df = pd.DataFrame(d)
            for c in ("lev_money_positions_long", "lev_money_positions_short", "open_interest_all"):
                df[c] = pd.to_numeric(df[c], errors="coerce")
            v = (df.lev_money_positions_long - df.lev_money_positions_short) / df.open_interest_all * 100
            idx = pd.to_datetime(df.report_date_as_yyyy_mm_dd) + pd.Timedelta(days=4)   # 周二数据、周五发布
            return pd.Series(v.values, index=idx).sort_index()
        except Exception as e:
            last = e
    raise RuntimeError(f"CFTC 取不到：{last}")


# ---------------- 合并到长期面板 ----------------
def load_panel():
    p = CACHE / "l4_panel.csv"
    seed = pd.read_csv(HERE / "l4_seed.csv", parse_dates=["date"]).set_index("date")
    if p.exists():
        cur = pd.read_csv(p, parse_dates=["date"]).set_index("date")
        cur = cur.combine_first(seed)
    else:
        cur = seed.copy()
    return cur.sort_index()


def put(panel, col, s, refresh_days=3):
    """新数据只填空白日子，最近 refresh_days 天允许覆盖（交易所事后修订）；研究时期的历史不改"""
    if s is None or len(s) == 0:
        return panel
    s = s.dropna()
    s = s[~s.index.duplicated(keep="last")]
    if col not in panel:
        panel[col] = np.nan
    panel = panel.reindex(panel.index.union(s.index))
    cut = today_utc() - pd.Timedelta(days=refresh_days)
    old = panel[col]
    fill = s[(s.index >= cut) | old.reindex(s.index).isna().values]
    panel.loc[fill.index, col] = fill.values
    return panel


def calibrate(panel, src):
    """用和面板已有数据重叠的日子，算新源到面板口径的比例 k（过原点回归）；返回 (k, 相关, 重叠天数)"""
    old = panel["funding_d"].dropna()
    ov = src.index.intersection(old.index)
    if len(ov) < 30:
        return None
    x = src.loc[ov].rolling(7, min_periods=5).mean().dropna()
    y = old.loc[x.index].rolling(7, min_periods=5).mean().dropna()
    x = x.loc[y.index]
    if len(x) < 20 or (x ** 2).sum() == 0:
        return None
    k = float((x * y).sum() / (x ** 2).sum())
    return k, float(np.corrcoef(x, y)[0, 1]), int(len(ov))


def update_funding(panel):
    calib_p = CACHE / "funding_calib.json"
    calib = json.load(open(calib_p)) if calib_p.exists() else {}
    for name, fn in FUND_SOURCES:
        try:
            raw = fn().dropna()
            raw = raw[raw.index < today_utc()]                  # 只要完整日
            if len(raw) < 20:
                raise RuntimeError("数据太少")
        except Exception as e:
            NOTES.append(f"资金费率源 {name} 取不到：{str(e)[:70]}")
            continue
        c = calibrate(panel, raw)
        if c is not None:
            k, r, n = c
            if r < 0.5 or not (0 < k < 1e4):
                NOTES.append(f"资金费率源 {name} 和历史对不上（相关 {r:.2f}），不用")
                continue
            calib[name] = dict(k=k, corr=round(r, 3), overlap_days=n, date=str(today_utc().date()))
        elif name in calib:
            k = calib[name]["k"]
        else:
            NOTES.append(f"资金费率源 {name} 和历史重叠不足 30 天，无法校准，不用")
            continue
        json.dump(calib, open(calib_p, "w"), ensure_ascii=False, indent=1)
        STATUS["funding"] = f"ok（{name}，校准比例 {calib[name]['k']:.4g}，相关 {calib[name]['corr']}）"
        return put(panel, "funding_d", raw * calib[name]["k"]), name
    STATUS["funding"] = "stale"
    return panel, None


def pct_rank(s, win=PCT_WIN, mn=PCT_MIN):
    v = s.values
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        if np.isnan(v[i]):
            continue
        h = v[max(0, i - win + 1):i + 1]
        h = h[~np.isnan(h)]
        if len(h) >= mn:
            out[i] = (h <= v[i]).mean() * 100
    return pd.Series(out, index=s.index)


def band(p):
    if p is None or np.isnan(p):
        return None, None
    for th, zh, en in BANDS:
        if p >= th:
            return zh, en
    return BANDS[-1][1], BANDS[-1][2]


def fnum(x, nd=1):
    return None if x is None or pd.isna(x) else round(float(x), nd)


def read_l2():
    cands = [os.environ.get("L4_L2_JSON", ""), str(OUT.parent / "l2" / "l2_latest.json"), str(HERE.parent / "site_l2" / "output" / "l2_latest.json")]
    for c in cands:
        if c and Path(c).exists():
            try:
                j = json.load(open(c, encoding="utf-8"))
                return j["state"]["code"], j["state"]["name_zh"]
            except Exception:
                pass
    NOTES.append("没读到 L2 状态（l2_latest.json），信号用法按“不分状态”写")
    return None, None


# ---------------- 主流程 ----------------
def main():
    t = today_utc()
    panel = load_panel()
    jobs = [("price", f_coinmetrics, None), ("coinalyze", f_coinalyze_oi_liq, None), ("qbasis", f_deribit_qbasis, "qbasis"),
            ("cme", f_cme, "cme_raw"), ("fng", f_fng, "fng"), ("dvol", f_dvol, "dvol"), ("cftc", f_cftc, "lev_net")]
    for name, fn, col in jobs:
        try:
            r = fn()
            if isinstance(r, pd.DataFrame):
                for c in r.columns:
                    panel = put(panel, c, r[c])
            else:
                panel = put(panel, col, r)
            STATUS[name] = "ok"
        except Exception as e:
            STATUS[name] = "stale"
            NOTES.append(f"{name} 取不到：{str(e)[:80]}")
            if name == "price":
                try:
                    panel = put(panel, "price", f_coinbase_daily()); STATUS[name] = "ok（Coinbase 备用）"
                except Exception as e2:
                    NOTES.append(f"Coinbase 价格也取不到：{str(e2)[:60]}")
    panel, fund_src = update_funding(panel)
    panel = panel[panel.index < t]                               # 只用完整日
    panel.reset_index().rename(columns={"index": "date"}).to_csv(CACHE / "l4_panel.csv", index=False)

    P = panel.copy()
    P["supply"] = P.supply.ffill()
    P["lev_net"] = P.lev_net.ffill(limit=10)
    P["fund_ma7"] = P.funding_d.rolling(7, min_periods=5).mean() * 365 * 100
    P["fund_ma30"] = P.funding_d.rolling(30, min_periods=20).mean() * 365 * 100
    P["fund_z90"] = (P.funding_d.rolling(7, min_periods=5).mean() - P.funding_d.rolling(90, min_periods=60).mean()) / P.funding_d.rolling(90, min_periods=60).std()
    P["cme_prem"] = P.cme_raw.rolling(5, min_periods=3).mean()
    P["agg_oi_btc"] = P.agg_oi_usd / P.price
    P["agg_oi_chg7"] = (P.agg_oi_btc / P.agg_oi_btc.shift(7) - 1) * 100
    P["agg_oi_mcap"] = P.agg_oi_usd / (P.price * P.supply) * 100
    P["liq_total_oi"] = (P.liq_long + P.liq_short) / P.agg_oi_usd * 100
    P["elr"] = P.agg_oi_btc / P.ex_bal.ffill(limit=5)
    P["lev_net_chg4w"] = P.lev_net - P.lev_net.shift(28)
    pcts = {c: pct_rank(P[c]) for c in ("fund_ma30", "fund_ma7", "qbasis", "cme_prem", "agg_oi_chg7", "agg_oi_mcap", "fng", "dvol",
                                         "liq_total_oi", "elr", "lev_net_chg4w")}

    BASE = {"fund_ma30": "funding_d", "fund_ma7": "funding_d", "cme_prem": "cme_raw", "agg_oi_chg7": "agg_oi_usd",
            "agg_oi_mcap": "agg_oi_usd", "liq_total_oi": "liq_long", "elr": "agg_oi_usd"}

    def last(col, maxage=5):
        """最新一个“底层数据还新鲜”的值：滚动均值在底层数据断了之后还会继续算，所以按底层列的最后日期判断"""
        b = P[BASE.get(col, col)].dropna()
        if b.empty or (t - b.index[-1]).days > maxage + 1:
            return None, None
        s = P[col].dropna()
        s = s[s.index <= b.index[-1]]
        return (s.iloc[-1], s.index[-1]) if len(s) else (None, None)

    def lastpct(col):
        v, d = last(col, maxage=10 if col == "qbasis" else 5)
        return None if d is None else pcts[col].get(d)

    # ---- 信号 ----
    f30, f30d = last("fund_ma30")
    l2code, l2name = read_l2()
    on = f30 is not None and f30 < 0
    neg = (P.fund_ma30 < 0) & P.funding_d.notna()
    days_on, since = 0, None
    if on:
        run = neg[::-1].cumprod()
        days_on = int(run.sum()); since = str(run[run == 1].index.min().date())
    if not on:
        use = ("最近一次为负：" + str(neg[neg].index.max().date())) if neg.any() else ""
        if f30 is None:
            use = "资金费率数据延迟，今天不判断。" + use
    elif l2code == "BEAR":
        use = "L2 为熊市：只执行“不开新空”，不据此抄底（熊市里历史 8 次只有 50% 上涨）"
    else:
        use = SIGNAL_EVIDENCE["rule_zh"]
    signal = dict(on=bool(on), value_pct=fnum(f30, 2), data_date=str(f30d.date()) if f30d is not None else None,
                  days_on=days_on, since=since, l2_state=l2name, funding_source=fund_src, use_zh=use, **SIGNAL_EVIDENCE)

    # ---- 温度 ----
    thermo = []
    for key, zh, en, unit, nd, grade, ev in THERMO:
        v, d = last(key, maxage=10 if key == "qbasis" else 5)
        p = lastpct(key)
        bz, be = band(p)
        thermo.append(dict(key=key, name_zh=zh, name_en=en, value=fnum(v, nd), unit=unit, data_date=str(d.date()) if d is not None else None,
                           pct_730d=fnum(p, 0), band_zh=bz, band_en=be, grade=grade, stat_zh=ev))
    tm = {x["key"]: x for x in thermo}
    lev_ps = [x["pct_730d"] for k, x in tm.items() if k in ("fund_ma30", "agg_oi_mcap") and x["pct_730d"] is not None]
    sen_p = tm["fng"]["pct_730d"]
    lev_p = float(np.mean(lev_ps)) if lev_ps else None
    comp = [p for p in (lev_p, sen_p) if p is not None]
    overall_p = float(np.mean(comp)) if comp else None
    lev_b = band(lev_p)[0]; sen_b = band(sen_p)[0]
    extreme = max([x for x in thermo if x["pct_730d"] is not None and x["key"] in ("fund_ma30", "agg_oi_mcap", "agg_oi_chg7", "fng")],
                  key=lambda x: abs(x["pct_730d"] - 50), default=None)
    key_read = f"{extreme['name_zh']} {extreme['value']}{extreme['unit']}，过去两年第 {int(extreme['pct_730d'])} 分位" if extreme else ""
    if on:
        level, one = "信号", "资金费率转负，空头拥挤：短期不追空"
        para = f"资金费率 30 日均 {f30:.1f}%（年化），已连续 {days_on} 天为负：空头拥挤，历史上之后一两个月偏强（已验证·方向）。用法：{use}"
    else:
        level = "过热" if (overall_p or 0) >= 85 else "偏热" if (overall_p or 0) >= 65 else "偏冷" if overall_p is not None and overall_p <= 35 else "中性"
        one = {"过热": "短期杠杆和情绪过热", "偏热": "短期杠杆和情绪偏热", "偏冷": "短期情绪偏冷", "中性": ""}[level]
        para = (f"杠杆{lev_b or '—'}、情绪{sen_b or '—'}（{key_read}）。这是一支温度计，不是方向标：费率高、恐慌贪婪极值、OI 堆积都没有通过检验，不改动作。"
                if level != "中性" else f"短期温度中性：杠杆{lev_b or '—'}、情绪{sen_b or '—'}（{key_read}）。只作描述。")

    # ---- 观察项（假设） ----
    def recent(col, cond, days=3):
        s = pcts[col].dropna()
        s = s[s.index >= t - pd.Timedelta(days=days)]
        return bool(cond(s).any()) if len(s) else False
    qb, _ = last("qbasis", maxage=10)
    watch_on = {
        "big_liq": recent("liq_total_oi", lambda s: s >= 90),
        "cme_low": recent("cme_prem", lambda s: s <= 10),
        "qbasis_low": (qb is not None and qb < 0) or recent("qbasis", lambda s: s <= 10, days=7),
        "dvol_low": recent("dvol", lambda s: s <= 10),
        "elr_low": recent("elr", lambda s: s <= 10),
        "lev_drop": recent("lev_net_chg4w", lambda s: s <= 10, days=7),
    }
    watch = [dict(key=k, on=watch_on[k], name_zh=v[0], name_en=v[1], grade="假设", stat_zh=v[2]) for k, v in WATCH_EVIDENCE.items()]

    data_date = max([x for x in [f30d] + [pd.Timestamp(x["data_date"]) for x in thermo if x["data_date"]] if x is not None], default=None)
    lines = [f"L4 情绪与衍生品（数据截至 {data_date.date() if data_date is not None else '—'}）",
             f"信号：资金费率 30 日均 {'%.1f%%' % f30 if f30 is not None else '—'}（年化）→ " + (f"亮（连续 {days_on} 天）。用法：{use}" if on else f"不亮。{use}"),
             f"温度：{para}"]
    w_on = [w["name_zh"] for w in watch if w["on"]]
    lines.append("观察项（假设，不改动作）：" + ("、".join(w_on) if w_on else "无"))

    stale = [k for k, v in STATUS.items() if str(v).startswith("stale")]
    latest = dict(
        layer="L4", updated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), data_date=str(data_date.date()) if data_date is not None else None,
        conclusion=dict(level=level, one_liner_zh=one, paragraph_zh=para, key_reading_zh=key_read,
                        leverage_band_zh=lev_b, sentiment_band_zh=sen_b, composite_pct=fnum(overall_p, 0)),
        signal=signal, thermometer=thermo, watch=watch, summary_zh="\n".join(lines),
        method_zh="分位 = 今天的值在过去 730 天里排第几（只用当时以前的数据）。≥90 过热、70~90 偏热、30~70 中性、10~30 偏冷、≤10 极冷。只有“资金费率 30 日均转负”一条通过检验、会改动作；其余是描述。依据《BTC情绪衍生品层L4研究》",
        data_status=dict(stale=bool(stale), detail=STATUS, notes=NOTES))
    json.dump(latest, open(OUT / "l4_latest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    H = P[P.index >= t - pd.Timedelta(days=400)]
    hist = []
    for i, r in H.iterrows():
        hist.append(dict(date=str(i.date()), price=fnum(r.price, 0), fund_ma30=fnum(r.fund_ma30, 2), fund_ma7=fnum(r.fund_ma7, 2),
                         signal=None if pd.isna(r.fund_ma30) else bool(r.fund_ma30 < 0), qbasis=fnum(r.qbasis, 2), cme_prem=fnum(r.cme_prem, 2),
                         agg_oi_chg7=fnum(r.agg_oi_chg7, 2), agg_oi_mcap=fnum(r.agg_oi_mcap, 3), liq_total_oi=fnum(r.liq_total_oi, 3),
                         fng=fnum(r.fng, 0), dvol=fnum(r.dvol, 1),
                         **{f"pct_{k}": fnum(pcts[k].get(i), 0) for k in ("fund_ma30", "agg_oi_mcap", "fng", "dvol")}))
    json.dump(hist, open(OUT / "l4_history.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(latest["summary_zh"])
    print("\n数据状态：", latest["data_status"])


if __name__ == "__main__":
    main()
