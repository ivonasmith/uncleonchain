#!/usr/bin/env python3
"""大叔的「龙头与轮动」复盘（rotation_data_*.json，2026-11-07 生成）→ data/core/rotation.json（网站「拉盘复盘」页读）。
原件放 core/research/，这里只做字段挑选和换算，不改任何数字。新一期复盘：把新文件放进 core/research/ 再跑
  python3 core/rotation_import.py core/research/rotation_data_N.json
口径（照原件）：锚点 = BTC 拉升起点；龙头 = 锚点前比 BTC 多涨 10 个百分点以上且锚点后 30 天收益不低于 BTC；
先行后掉队 = 只满足前一条；后发跟涨 = 只满足后一条；落后 = 都不满足。综合分 = 0.3×启动早晚 + 0.3×区间收益 + 0.2×均线 + 0.2×周线 MACD。
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "research", "rotation_data_4.json")
d = json.load(open(src, encoding="utf-8"))
btc = next(x for x in d["coins"] if x["symbol"] == "BTC")
bpre, b30 = btc["anchor"]["pre_ret"], btc["anchor"]["r30"]
CLS = {"龙头（先行且续强）": "lead", "先行后掉队": "fade", "后发跟涨": "follow", "落后": "lag"}
r = lambda x, n=4: None if x is None else round(x, n)
coins = []
for x in d["coins"]:
    a = x.get("anchor") or {}
    coins.append({"sym": x["symbol"], "name": x.get("name"), "rank": x.get("cg_rank"), "mcap": x.get("mcap"),
                  "cls": CLS.get(x.get("anchor_class")), "queue": x.get("queue"), "pre": r(a.get("pre_ret")), "pre_rel": r((a.get("pre_ret") or 0) - bpre),
                  "r30": r(a.get("r30")), "r7": r(a.get("r7")), "ret_end": r(x.get("ret_end")), "ret_now": r(x.get("ret_now")), "max_rally": r(x.get("max_rally")),
                  "peak_date": x.get("peak_date"), "from_peak": r(x.get("from_peak_now")), "up50": x.get("up50"), "up20": x.get("up20"),
                  "structure": (x.get("structure") or "").split("（")[0], "ma200_now": (x.get("ma200") or {}).get("above_now"),
                  "ma200_dist": r((x.get("ma200") or {}).get("dist_now")), "comp": r(x.get("composite"), 3), "scores": x.get("scores"),
                  "low_act": x.get("low_activity"), "turn": r((x.get("turnover") or {}).get("median"), 0),
                  "path": [[p[0], round(p[1], 1)] for p in (x.get("path") or [])]})
out = {"meta": dict(d["meta"], source=os.path.basename(src), btc_pre=bpre, btc_r30=b30, btc_ret_end=btc.get("ret_end"), btc_ret_now=btc.get("ret_now")),
       "skipped": d.get("skipped", []), "coins": coins}
dst = os.path.join(os.path.dirname(HERE), "data", "core", "rotation.json")
json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"{len(coins)} 个币 → {dst}（{os.path.getsize(dst)//1024} KB）")
