#!/usr/bin/env python3
"""机制拆解卡数据（博弈控盘型；先做 TAO、WLD）→ data/core/mech.json。只用标准库，在 Actions 里跑。
需要：TAOSTATS_KEY（taostats，免费档每分钟约 5 次）、COINALYZE_KEY（币安永续持仓 / 资金费率）、ETHERSCAN_KEY（以太坊 1、World Chain 480；Optimism 免费档不支持）。
事实底稿（静态部分）：core/research/TAO_WLD供给与排放核查_20261114_codex.md。拿不到的写“未取到”，不编。
"""
import json, os, sys, time, urllib.parse, urllib.request
import datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "core", "mech.json")
TS, CZ, ES = (os.environ.get(k, "").strip() for k in ("TAOSTATS_KEY", "COINALYZE_KEY", "ETHERSCAN_KEY"))
SRC = "core/research/TAO_WLD供给与排放核查_20261114_codex.md"
ERR = []


def get(url, headers=None, tries=3, wait=15):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "uncleonchain-mech/1.0", "accept": "application/json", **(headers or {})})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and i + 1 < tries:
                time.sleep(wait * (i + 1)); continue
            ERR.append(f"{url.split('?')[0]} HTTP {e.code}")
            return None
        except Exception as e:  # noqa
            ERR.append(f"{url.split('?')[0]} {e}")
            time.sleep(3)
    return None


def taostats(path):
    d = get("https://api.taostats.io" + path, {"Authorization": TS})
    time.sleep(13)                     # 免费档限速
    return (d or {}).get("data") or []


def coinalyze(symbol):
    t1 = int(time.time()); t0 = t1 - 35 * 86400
    oi = get(f"https://api.coinalyze.net/v1/open-interest-history?symbols={symbol}&interval=daily&from={t0}&to={t1}&convert_to_usd=true", {"api_key": CZ})
    time.sleep(2)
    fr = get(f"https://api.coinalyze.net/v1/funding-rate-history?symbols={symbol}&interval=daily&from={t0}&to={t1}", {"api_key": CZ})
    oi_h = (oi or [{}])[0].get("history") or []
    fr_h = (fr or [{}])[0].get("history") or []
    return {"oi_usd": oi_h[-1]["c"] if oi_h else None, "fund_last": fr_h[-1]["c"] if fr_h else None,
            "fund_30": sum(x["c"] for x in fr_h[-30:]) / len(fr_h[-30:]) if fr_h else None,
            "fund_neg_days": sum(1 for x in fr_h[-30:] if x["c"] < 0)}


def etherscan(chain, **q):
    q.update({"chainid": chain, "apikey": ES})
    d = get("https://api.etherscan.io/v2/api?" + urllib.parse.urlencode(q))
    time.sleep(0.3)
    return d.get("result") if d and d.get("status") == "1" else None


def core_latest():
    try:
        return json.load(open(os.path.join(ROOT, "data", "core", "core_latest.json"), encoding="utf-8"))
    except Exception:  # noqa
        return {}


def fmt(x, unit="", d=1):
    if x is None:
        return "未取到"
    a = abs(x)
    if a < 1:
        return "≈0" + unit
    s = f"{x/1e9:.{d}f}B" if a >= 1e9 else f"{x/1e6:.{d}f}M" if a >= 1e6 else f"{x/1e3:.{d}f}K" if a >= 1e3 else f"{x:.{d}f}"
    return s + unit


def pct(a, b):
    return f"{a / b * 100:.1f}%" if a is not None and b else "未取到"


def vol_row(latest, sym):
    for r in ((latest.get("market") or {}).get("vol") or {}).get("rows") or []:
        if r["sym"] == sym:
            return r
    return {}


def tao(latest):
    st = (taostats("/api/stats/latest/v1") or [{}])[0]
    pr = (taostats("/api/price/latest/v1?asset=tao") or [{}])[0]
    acc = taostats("/api/account/latest/v1?limit=10&order=balance_total_desc")
    R = 1e9
    issued, staked = float(st.get("issued", 0)) / R or None, float(st.get("staked", 0)) / R or None
    root_, alpha = float(st.get("staked_root", 0)) / R, float(st.get("staked_alpha", 0)) / R
    free = float(st.get("free", 0)) / R or None
    price = float(pr["price"]) if pr.get("price") else None
    mcap = float(pr["market_cap"]) if pr.get("market_cap") else None
    top10 = sum(float(a.get("balance_total") or 0) for a in acc) / R if acc else None
    cz = coinalyze("TAOUSDT_PERP.A")
    vr = vol_row(latest, "TAO")
    emit_day = 3600
    return {
        "asof": (st.get("timestamp") or "")[:10], "source": SRC + "；实时：taostats、Coinalyze、币安成交额榜",
        "summary": "大类：博弈控盘型 · 反身性（标签：AI 叙事、挖矿排放）。质押收益来自排放，没有外部收入回流 TAO；流通里大部分在质押或子网池里，自由余额是能直接卖的上限。",
        "sections": [
            {"title": "真正能卖的有多少", "rows": [
                ["已发行 / 最大供给", f"{fmt(issued)} / 21.0M", "taostats；按发行量减半（1,050 万、1,575 万…）"],
                ["质押合计（占已发行）", f"{fmt(staked)}（{pct(staked, issued)}）", "根网 + 子网池，不再相加"],
                ["其中根网质押", fmt(root_), "taostats staked_root"],
                ["其中子网池（alpha 质押折 TAO）", fmt(alpha), "池储备不等于固定期限锁仓"],
                ["自由余额（能直接卖的上限）", f"{fmt(free)}（{pct(free, issued)}）", "含交易所钱包"],
                ["前 10 大地址合计", f"{fmt(top10)}（{pct(top10, issued)}）", "按余额 + 质押估值；不等于 10 个人能立即卖出"]]},
            {"title": "排放 vs 真实收入", "rows": [
                ["理论日排放", f"{emit_day:,} TAO ≈ ${fmt(emit_day * price if price else None)} / 日", "0.5 TAO / 区块（2025-12 首次减半后）"],
                ["年化排放（按现价）", f"${fmt(emit_day * 365 * price if price else None)}", "排放主要以子网 alpha 奖励形式发给矿工 / 验证者 / 子网所有者"],
                ["回流 TAO 持有人的收入", "未查到", "子网回购的是各自的 alpha，不是 TAO；swap 费给区块作者"],
                ["已知子网对外收入", "Chutes（SN64）2026 Q2 约 $137 万（第三方 DefiLlama）", "全网统一口径未取到；第三方年化 2,020 万～7,000 万美元，范围差很大"]]},
            {"title": "是不是合约在带价格", "rows": [
                ["近 30 天合约成交占比", f"{vr.get('fut_share_30d', 0):.0f}%" if vr.get("fut_share_30d") is not None else "未取到", "币安全口径成交额榜"],
                ["币安永续持仓 ÷ 市值", f"${fmt(cz['oi_usd'])}（{pct(cz['oi_usd'], mcap)}）", "Coinalyze TAOUSDT_PERP"],
                ["资金费率（最近 / 30 天均）", f"{cz['fund_last']:.4f}% / {cz['fund_30']:.4f}%" if cz["fund_last"] is not None else "未取到", f"30 天里为负的天数 {cz['fund_neg_days']}"]]},
            {"title": "价格", "rows": [
                ["现价 / 市值", f"${price:,.2f} / ${fmt(mcap)}" if price and mcap else "未取到", "taostats"],
                ["30 天涨跌", f"{float(pr['percent_change_30d']):+.1f}%" if pr.get("percent_change_30d") else "未取到", "taostats"]]}],
        "flags": ["质押收益主要来自排放，不是外部现金收入；子网有收入、alpha 有回购，不等于 TAO 持有人拿到分红。",
                  "官方“无预挖、公平启动”，但不代表团队 / 基金会后来没有挖矿或买入所得，当前持有量未查到。",
                  "子网收入缺统一可核口径，排放 / 真实收入的精确倍数现在算不出。"]}


def wld(latest):
    cg = get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=worldcoin-wld") or [{}]
    cg = cg[0] if cg else {}
    price, circ, mcap = cg.get("current_price"), cg.get("circulating_supply"), cg.get("market_cap")
    T1, T480 = "0x163f8C2467924be0ae7B5347228CABF260318753", "0x2cFc85d8E48F8EAB294be644d9E25C3030863003"
    W = {"基金会冷钱包": "0xc534a745bFfaF9466Ed7B47fA23B0177b99A3e77", "World Assets 冷钱包": "0x59a0f98345f54bAB245A043488ECE7FCecD7B596",
         "TFH 历史解锁钱包①": "0x0D4CA2FF883D429cE4372Eeb056EFAFab181CcE7", "TFH 历史解锁钱包②": "0xFB7F100ED6793FCD63E6E9F201bE9Aa567B2C9cC",
         "社区解锁合约①": "0x1770bd8186AAd27Df9B050D65f86CF2cdC92C296", "社区解锁合约②": "0xaEE0360b73B5D01dad134f234d3a93adc1680e57",
         "社区解锁合约③": "0x938ceD2D1eE4AFB220929F96c2eB754C053C77F7", "社区解锁合约④": "0x5B5442C5fcEaE3b40C230C32a3Ffe924BcBe7D93"}
    bal = {}
    for nm, a in W.items():
        v1 = etherscan(1, module="account", action="tokenbalance", contractaddress=T1, address=a, tag="latest")
        v4 = etherscan(480, module="account", action="tokenbalance", contractaddress=T480, address=a, tag="latest")
        bal[nm] = (int(v1) / 1e18 if v1 is not None else None, int(v4) / 1e18 if v4 is not None else None)
    rows_bal = [[nm, f"以太坊 {fmt(b[0])} · World Chain {fmt(b[1])}", a[:6] + "…" + a[-4:]] for (nm, b), a in zip(bal.items(), W.values())]
    locked = sum((b[0] or 0) + (b[1] or 0) for nm, b in bal.items() if nm.startswith("社区解锁"))
    hold = get(f"https://eth.blockscout.com/api/v2/tokens/{T1}/holders") or {}
    known = {a.lower(): nm for nm, a in W.items()}
    top = [(h["address"]["hash"], int(h["value"]) / 1e18) for h in (hold.get("items") or [])[:10]]
    top_sum = sum(v for _, v in top) if top else None
    top_lab = "；".join(f"{known.get(a.lower(), a[:6] + '…' + a[-4:])} {fmt(v)}" for a, v in top[:5]) if top else "未取到"
    cz = coinalyze("WLDUSDT_PERP.A")
    vr = vol_row(latest, "WLD")
    unlock_day = 2_900_000
    return {
        "asof": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"), "source": SRC + "；实时：CoinGecko、Etherscan（以太坊 / World Chain）、Blockscout、Coinalyze、币安成交额榜",
        "summary": "大类：博弈控盘型 · 反身性（标签：空投激励、解锁抛压）。没有收入回流持币人；每天约 290 万枚常规解锁，2026-06 起停止新建空投周期。",
        "sections": [
            {"title": "真正能卖的有多少", "rows": [
                ["初始供给 / 流通", f"10.0B / {fmt(circ)}（{pct(circ, 1e10)}）", "流通取 CoinGecko；最早 2038 年后可治理增发，最高 1.5% / 年"],
                ["未流通", fmt(1e10 - circ if circ else None), "其中一部分已解锁但还没流通，不能都算锁仓"],
                ["社区解锁合约里的余额（4 个合约合计）", fmt(locked), "按官方公布的解锁合约地址查链上余额"]] + rows_bal},
            {"title": "排放 vs 真实收入", "rows": [
                ["常规解锁速度", f"约 290 万枚 / 日 ≈ ${fmt(unlock_day * price if price else None)} / 日", "社区约 160 万 + 团队和投资人约 130 万（2026-07-24 起）"],
                ["未来 12 个月常规解锁", f"约 10.6 亿枚 ≈ ${fmt(1.0585e9 * price if price else None)}", "按官方日速率估算；不含额外私募与储备"],
                ["回流持币人的收入", "未查到", "World ID 费用设计里协议费可用于运营或销毁，执行比例与流水未查到"]]},
            {"title": "是不是合约在带价格", "rows": [
                ["近 30 天合约成交占比", f"{vr.get('fut_share_30d', 0):.0f}%" if vr.get("fut_share_30d") is not None else "未取到", "币安全口径成交额榜"],
                ["币安永续持仓 ÷ 市值", f"${fmt(cz['oi_usd'])}（{pct(cz['oi_usd'], mcap)}）", "Coinalyze WLDUSDT_PERP"],
                ["资金费率（最近 / 30 天均）", f"{cz['fund_last']:.4f}% / {cz['fund_30']:.4f}%" if cz["fund_last"] is not None else "未取到", f"30 天里为负的天数 {cz['fund_neg_days']}"]]},
            {"title": "筹码在谁手里（以太坊）", "rows": [
                ["前 10 大持有地址合计", f"{fmt(top_sum)}（占初始供给 {pct(top_sum, 1e10)}）", "Blockscout；多为基金会 / 解锁合约，不等于可立即卖出"],
                ["前 5 名", top_lab, "已按官方地址表标注名称"]]},
            {"title": "价格", "rows": [["现价 / 市值", f"${price:,.4f} / ${fmt(mcap)}" if price and mcap else "未取到", "CoinGecko"]]}],
        "flags": ["约 62% 初始供给还没流通，其中一部分已解锁未流通，潜在供给释放大。",
                  "2026-06 起停止新建 / 续期空投周期，旧的用户发放模型失效，当前实际发放量要看链上领取记录。",
                  "做市商借币（历史 1,000 万枚，约定 2025-06 到期归还）现状没有公开对账。",
                  "World 的商业收入与 WLD 持有人收益不能画等号：已实现收入、销毁比例、回流记录都未查到。"]}


def main():
    latest = core_latest()
    out = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "coins": {}}
    for sym, fn in (("TAO", tao), ("WLD", wld)):
        try:
            out["coins"][sym] = fn(latest)
        except Exception as e:  # noqa
            ERR.append(f"{sym}: {e}")
            try:                                   # 这次取不到就沿用上次那张卡，标 stale
                prev = json.load(open(OUT, encoding="utf-8"))["coins"][sym]
                prev["stale"] = True
                out["coins"][sym] = prev
            except Exception:  # noqa
                pass
    out["errors"] = ERR
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
