#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据新鲜度状态（2026-11-15）：总调度 refresh.yml 用它决定这一档要不要跑，跑完写状态；
出网站把 data/refresh_status.json 原样复制到 /data/status.json，大叔的交易程序取数前先读它。

用法：
  python3 pipeline/数据状态.py --guard am|pm|retry|auto   # 打印 run=yes/no 和 slot=…（写进 $GITHUB_OUTPUT）
  python3 pipeline/数据状态.py --write SLOT [--outcomes JSON] [--run-url URL] [--started ISO]

口径：后端一律 UTC。「应有数据日」= UTC 昨天（昨天 0 点收盘的完整日）。
  交易用的模块（trading=True）全部到昨天 → ready_for_trading = true。
  am 档（UTC 00:05）时 Coin Metrics / DefiLlama 多半还没出昨天的数，L2 / L3 晚一天是正常的，pm 档补齐。
"""
import json, os, sys, datetime as dt

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(BASE, "data")
OUT = os.path.join(D, "refresh_status.json")


def _j(p):
    try:
        with open(os.path.join(D, p), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _d(s):
    return (s or "")[:10] or None


def modules(today):
    """每个模块的数据日（这批数据截至哪个 UTC 完整日）。日志按运行日命名，所以它的数据日 = 文件日 - 1。"""
    l2, l3, l4 = _j("l2/l2_latest.json"), _j("l3/l3_latest.json"), _j("l4/l4_latest.json")
    leg, core, alpha = _j("leg/leg_latest.json"), _j("core/core_latest.json"), _j("alpha/alpha_latest.json")
    aia, rwa, cal = _j("aiagent/aiagent_latest.json"), _j("rwa/rwa_latest.json"), _j("cal/cal_latest.json")
    logs = sorted(x[:10] for x in os.listdir(os.path.join(D, "解读日志", "日")) if x.endswith(".json")) if os.path.isdir(os.path.join(D, "解读日志", "日")) else []
    log_d = None
    if logs:
        log_d = (dt.date.fromisoformat(logs[-1]) - dt.timedelta(days=1)).isoformat()
    m = {
        "l2": {"name": "L2 周期", "data_date": _d(l2.get("data_date")), "updated_utc": l2.get("updated_utc"), "trading": True},
        "l3": {"name": "L3 筹码", "data_date": _d(l3.get("data_date")), "updated_utc": l3.get("updated_utc"), "trading": True},
        "l4": {"name": "L4 情绪", "data_date": _d(l4.get("data_date")), "updated_utc": l4.get("updated_utc"), "trading": True,
               "stale_source": bool((l4.get("data_status") or {}).get("stale"))},
        "leg": {"name": "涨跌腿", "data_date": _d(leg.get("asof")), "trading": True},
        "macro": {"name": "宏观 L1 + 解读日志", "data_date": log_d, "trading": True},
        "cal": {"name": "事件日历", "data_date": None, "updated_utc": cal.get("generated_utc"), "trading": True},
        "core": {"name": "核心选币", "data_date": _d(core.get("last_complete_day")), "updated_utc": core.get("generated")},
        "alpha": {"name": "Alpha 雷达", "data_date": _d(alpha.get("asof")), "updated_utc": alpha.get("generated")},
        "aiagent": {"name": "AI Agent", "data_date": _d(aia.get("asof")), "updated_utc": aia.get("generated")},
        "rwa": {"name": "RWA", "data_date": _d(rwa.get("asof_llama")), "updated_utc": rwa.get("generated")},
    }
    want = (today - dt.timedelta(days=1)).isoformat()
    for k, x in m.items():
        if k == "cal":   # 日历不是收盘数据：今天跑过就算新
            x["fresh"] = _d(x.get("updated_utc")) == today.isoformat()
        else:
            x["fresh"] = bool(x["data_date"]) and x["data_date"] >= want
    return m, want


def guard(slot, now):
    """am：今天 am 跑过就跳过；pm：今天 pm 跑过且交易数据齐了就跳过；retry：只在交易数据没齐时跑；auto = 兜底定时（按钟点归档）。"""
    if slot == "auto":
        slot = "am" if now.hour < 8 else "pm"
    st = _j("refresh_status.json")
    today = now.date().isoformat()
    done = (st.get("done") or {}).get(today, [])
    m, _w = modules(now.date())
    ready = all(x["fresh"] for x in m.values() if x.get("trading"))
    if slot == "am":
        run = "am" not in done
    elif slot == "pm":
        run = not ("pm" in done and ready)
    else:  # retry
        run = not ready
        slot = "pm"
    return run, slot, ready


def write(slot, outcomes, run_url, started, now):
    m, want = modules(now.date())
    st = _j("refresh_status.json")
    done = {k: v for k, v in (st.get("done") or {}).items() if k >= (now.date() - dt.timedelta(days=7)).isoformat()}
    today = now.date().isoformat()
    done.setdefault(today, [])
    if slot not in done[today]:
        done[today].append(slot)
    ready = all(x["fresh"] for x in m.values() if x.get("trading"))
    out = {
        "schema": 1,
        "note": "UTC。expected_data_date = 昨天（UTC 0 点收盘的完整日）。ready_for_trading = 交易用模块（trading=true）全部到 expected_data_date。",
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "slot": slot,
        "started_utc": started,
        "run_url": run_url,
        "expected_data_date": want,
        "ready_for_trading": ready,
        "not_ready": [k for k, x in m.items() if x.get("trading") and not x["fresh"]],
        "modules": m,
        "steps": outcomes,
        "done": done,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ("slot", "expected_data_date", "ready_for_trading", "not_ready")}, ensure_ascii=False))


def main():
    now = dt.datetime.now(dt.timezone.utc)
    a = sys.argv[1:]
    if "--guard" in a:
        run, slot, ready = guard(a[a.index("--guard") + 1], now)
        print(f"run={'yes' if run else 'no'}\nslot={slot}\nready={'yes' if ready else 'no'}")
        go = os.environ.get("GITHUB_OUTPUT")
        if go:
            with open(go, "a") as f:
                f.write(f"run={'yes' if run else 'no'}\nslot={slot}\n")
        return
    if "--write" in a:
        slot = a[a.index("--write") + 1]
        oc = {}
        if "--outcomes" in a:
            try:
                oc = json.loads(a[a.index("--outcomes") + 1])
            except Exception:
                oc = {}
        url = a[a.index("--run-url") + 1] if "--run-url" in a else None
        started = a[a.index("--started") + 1] if "--started" in a else None
        write(slot, oc, url, started, now)
        return
    m, want = modules(now.date())
    print("应有数据日", want)
    for k, x in m.items():
        print(f"{'✓' if x['fresh'] else '✗'} {k:8} {x.get('data_date') or '-':12} {x.get('updated_utc') or ''}")


if __name__ == "__main__":
    main()
