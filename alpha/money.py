#!/usr/bin/env python3
"""机会卡的「成交与变现」（Codex 11-15 审阅 + 大叔点头：把成交、总手续费、协议收入、持币人收入拆开，算协议抽成，
上线不满 30 天的标「实际历史只有 N 天」，避免把激励窗口里的数字当成常态）。opps.py 调用，失败不影响出卡。

口径（DefiLlama summary 接口，按卡片的协议 / 母协议 slug）：
  成交   summary/dexs（没有再试 derivatives）的 total24h / total7d / total30d
  费用   summary/fees?dataType=dailyFees（用户付的全部费用，含给 LP / 创作者的）
  收入   dataType=dailyRevenue（协议留下的）
  持币人 dataType=dailyHoldersRevenue（分给代币持有人的：回购销毁、分红）
  协议抽成 = 30 天协议收入 ÷ 30 天成交；近 7 天占比 = 7 天成交 ÷ 30 天成交（没有成交用费用算）
"""
import json, time, urllib.request

UA = {"User-Agent": "uncleonchain-alpha/1.0"}


def _get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
            return json.load(r)
    except Exception:
        return None


def _t(d):
    if not d:
        return None
    return {k: d.get(k) for k in ("total24h", "total7d", "total30d")} if any(d.get(k) is not None for k in ("total24h", "total7d", "total30d")) else None


def one(slug):
    out = {}
    vol = _t(_get(f"https://api.llama.fi/summary/dexs/{slug}")) or _t(_get(f"https://api.llama.fi/summary/derivatives/{slug}"))
    out["vol"] = vol
    for k, dt_ in (("fees", "dailyFees"), ("rev", "dailyRevenue"), ("hold", "dailyHoldersRevenue")):
        out[k] = _t(_get(f"https://api.llama.fi/summary/fees/{slug}?dataType={dt_}"))
        time.sleep(0.2)
    v30 = (vol or {}).get("total30d")
    r30 = (out.get("rev") or {}).get("total30d")
    base = vol or out.get("fees") or {}
    out["take"] = round(r30 / v30, 5) if v30 and r30 is not None else None
    out["share7"] = round(base["total7d"] / base["total30d"], 3) if base.get("total30d") and base.get("total7d") is not None else None
    out["src"] = "DefiLlama"
    return out if any(out.get(k) for k in ("vol", "fees", "rev")) else None


def enrich(cards):
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        LPQ = (json.load(open(os.path.join(root, "data", "onchain", "平台质量.json"), encoding="utf-8")) or {}).get("平台") or {}
    except Exception:
        LPQ = {}
    cache = {}
    for c in cards:
        k, d = c["key"], c["data"]
        g = d.get("llama") or (k[2:] if k[:2] in ("g:", "s:") else None)
        slug = g[len("parent#"):] if g and g.startswith("parent#") else (d.get("slug") or g)
        # 发射台板块的平台质量（docs/接口_发射台给Alpha.md）；母协议卡（如 Pons）按子协议 slug 前缀找（pons-v2）
        lq = LPQ.get(d.get("slug") or "") or (LPQ.get(slug) if slug else None) or next((v for k2, v in LPQ.items() if slug and k2.startswith(slug + "-")), None)
        if lq:
            d["lpq"] = lq
        if not slug or ":" in slug:
            continue
        if slug not in cache:
            cache[slug] = one(slug)
        if cache[slug]:
            m = dict(cache[slug])
            age = (d.get("age") or {}).get("days")
            m["short_history"] = age if age is not None and age < 30 else None   # 实际历史不足 30 天：30 天数字其实只有这么多天
            d["money"] = m
