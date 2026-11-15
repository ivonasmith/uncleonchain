#!/usr/bin/env python3
"""Alpha 雷达 · 每周复盘数据（每周一由定时会话跑，结果进 data/alpha/weekly/ 并同步 Notion「Alpha 雷达」入口）。

统计窗口：上周一 00:00 到本周一 00:00（UTC，完整 7 天）。只读清洗层 / 应用层文件，不请求接口：
  线索：新增（按来源）、状态变化（status_history）、发币（token_seen）
  事件流：新增条数（按来源）、发现延迟中位数（基线条目不算）
  数据源：各源失败天数（alpha_history 的 src_ok）
  看板：可投资 / 预警 / 拒绝 数量，和上周快照比的进出
  A4：研究观察组 / 对照组样本数、最早定档日、距第 90 天还差几天
  门槛复核：无币收入榜 30 天收入分位（P25 / P50 / P75 / P90），给「10 万美元门槛要不要调」攒依据
输出：data/alpha/weekly/<YYYY-Www>.json + .md；data/alpha/weekly/opps_<周>.json（看板快照，下周比对用）
用法：python3 alpha/weekly.py [--week 2026-W46]
"""
import json, os, statistics as st, sys
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
D = os.path.join(ROOT, "data", "alpha")
W = os.path.join(D, "weekly")


def load(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def q(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    f = int(k)
    return xs[f] + (xs[min(f + 1, len(xs) - 1)] - xs[f]) * (k - f)


def main():
    if "--week" in sys.argv:
        y, w = sys.argv[sys.argv.index("--week") + 1].split("-W")
        end = dt.date.fromisocalendar(int(y), int(w), 1) + dt.timedelta(days=7)
    else:
        t = dt.datetime.now(dt.timezone.utc).date()
        end = t - dt.timedelta(days=t.weekday())          # 本周一
    start = end - dt.timedelta(days=7)
    iy, iw, _ = start.isocalendar()
    tag = f"{iy}-W{iw:02d}"
    s0, e0 = start.isoformat(), end.isoformat()
    inwk = lambda d: d and s0 <= d[:10] < e0

    leads = (load(os.path.join(D, "alpha_leads.json"), {}) or {}).get("leads", {})
    hist = load(os.path.join(D, "alpha_history.json"), []) or []
    feed = (load(os.path.join(D, "alpha_feed.json"), {}) or {}).get("items", {})
    opps = load(os.path.join(D, "opps.json"), {}) or {}
    latest = load(os.path.join(D, "alpha_latest.json"), {}) or {}

    new = [v for v in leads.values() if inwk(v["first_seen"]) and not v.get("baseline")]
    status = [(v["name"], h["status"], h["date"]) for v in leads.values() for h in v.get("status_history", []) if inwk(h["date"])]
    token = [v["name"] for v in leads.values() if inwk(v.get("token_seen"))]
    fnew = [x for x in feed.values() if inwk(x["first_seen"])]
    delays = [x["delay_h"] for x in fnew if x.get("delay_h") is not None]
    hw = [h for h in hist if inwk(h["date"])]
    fails = {}
    for h in hw:
        for k, ok in (h.get("src_ok") or {}).items():
            fails.setdefault(k, 0)
            fails[k] += 0 if ok else 1
    prev = load(os.path.join(W, f"opps_{(start - dt.timedelta(days=7)).isocalendar()[0]}-W{(start - dt.timedelta(days=7)).isocalendar()[1]:02d}.json"), None)
    cur = {o["id"]: o["bucket"] for o in opps.get("opps", [])}
    moves = []
    if prev:
        for k, b in cur.items():
            if prev.get(k) != b:
                moves.append({"id": k, "from": prev.get(k), "to": b})
    watch = [v for v in leads.values() if any(h["status"] == "研究观察" for h in v.get("status_history", []))]
    first_watch = min((h["date"] for v in watch for h in v["status_history"] if h["status"] == "研究观察"), default=None)
    ctrl = [v for v in leads.values() if v["key"].startswith("g:") and v not in watch]
    revs = [r["rev30"] for r in latest.get("tokenless", [])]
    out = {
        "week": tag, "from": s0, "to": e0, "days_with_data": len(hw),
        "leads": {"new": len(new), "by_source": {s: sum(1 for v in new if s in v["source"]) for s in ("tokenless_rev", "new_listing")},
                  "new_names": [v["name"] for v in new][:40], "status_changes": [{"name": n, "status": s, "date": d} for n, s, d in status], "token_launch": token, "total": len(leads)},
        "feed": {"new": len(fnew), "by_source": {s: sum(1 for x in fnew if x["src"] == s) for s in ("ethresearch", "snapshot", "binance")},
                 "delay_median_h": round(st.median(delays), 1) if delays else None},
        "sources_fail_days": fails,
        "board": {"counts": opps.get("counts"), "moves": moves, "prev_snapshot": bool(prev)},
        "a4": {"watch_n": len(watch), "control_n": len(ctrl), "first_watch": first_watch,
               "days_to_d90": (dt.date.fromisoformat(first_watch) + dt.timedelta(days=90) - end).days if first_watch else None,
               "judgeable": len(watch) >= 20 and len(ctrl) >= 20},
        "threshold": {"n": len(revs), "p25": q(revs, .25), "p50": q(revs, .5), "p75": q(revs, .75), "p90": q(revs, .9), "current_usd": 100000},
        "framework": opps.get("framework"), "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    os.makedirs(W, exist_ok=True)
    json.dump(out, open(os.path.join(W, f"{tag}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(cur, open(os.path.join(W, f"opps_{tag}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    fm = lambda v: "—" if v is None else f"${v / 1e6:.2f}M" if v >= 1e6 else f"${v / 1e3:.0f}K"
    md = [f"# Alpha 雷达周复盘 {tag}（{s0} – {e0}，UTC）", "",
          f"有数据的天数 {len(hw)} / 7。框架 {out['framework']}。", "",
          "## 线索", f"- 新增 {len(new)} 条（无币收入榜 {out['leads']['by_source']['tokenless_rev']}、新上架 {out['leads']['by_source']['new_listing']}），台账累计 {len(leads)}",
          f"- 状态变化 {len(status)} 次" + ("：" + "；".join(f"{n} → {s}" for n, s, _ in status[:20]) if status else ""),
          f"- 发币 {len(token)} 个" + ("：" + "、".join(token) if token else ""), "",
          "## 事件流", f"- 新增 {len(fnew)} 条（论坛 {out['feed']['by_source']['ethresearch']}、治理 {out['feed']['by_source']['snapshot']}、Binance {out['feed']['by_source']['binance']}）",
          f"- 发现延迟中位数 {out['feed']['delay_median_h'] if out['feed']['delay_median_h'] is not None else '—'} 小时", "",
          "## 数据源", "- " + ("；".join(f"{k} 失败 {v} 天" for k, v in fails.items() if v) or "全部正常"), "",
          "## 机会看板", f"- 可投资 {(out['board']['counts'] or {}).get('invest')} · 预警观察 {(out['board']['counts'] or {}).get('watch')} · 拒绝 {(out['board']['counts'] or {}).get('reject')}",
          "- " + ("分栏变化：" + "；".join(f"{m['id']} {m['from']} → {m['to']}" for m in moves) if moves else ("和上周相比没有分栏变化" if prev else "第一周，没有上周快照可比")), "",
          "## A4 前瞻验证进度", f"- 研究观察组 {len(watch)} 个，对照组 {len(ctrl)} 个；最早定档 {first_watch or '—'}" + (f"，距第 90 天还有 {out['a4']['days_to_d90']} 天" if out['a4']['days_to_d90'] is not None else ""),
          f"- {'两组都满 20 个，可以判' if out['a4']['judgeable'] else '样本不够，记录中（两组都要 ≥ 20）'}", "",
          "## 门槛复核（无币收入榜 30 天收入）", f"- {len(revs)} 个：P25 {fm(out['threshold']['p25'])} · 中位 {fm(out['threshold']['p50'])} · P75 {fm(out['threshold']['p75'])} · P90 {fm(out['threshold']['p90'])}；现行门槛 $100K（攒满 4 周再决定要不要调）", "",
          "## 本周结论 / 规则调整", "- （复盘会话填写：哪些判断被证实或推翻、要不要改规则；改规则要写进框架版本和更新日志）"]
    open(os.path.join(W, f"{tag}.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
