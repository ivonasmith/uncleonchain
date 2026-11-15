#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全站待办总表 + 每日检查（大叔 2026-11-15 定：一边一个定时任务）。

总调度 refresh.yml 的 publish 步骤每天跑一次，写：
  data/tasks.json        全站「要补什么」：每个板块按自己的规则出待办，标明 谁做（codex / claude / 大叔）、交到哪个文件、优先级
  data/check_report.json 全站「哪里不合格」：已交的补证 / 登记文件逐条机器检查（格式、取值范围、来源链接、过期没核对）
  data/tasks.md          上面两份的人读版
Codex 的定时任务每天先读 check_report 把自己交的问题改掉，再按 tasks 从上往下补，补完推 main；
下一档总调度自动并入网站并重新检查。要 Claude 改代码的条目（who = claude）攒着，Claude 的每周会话处理。

新板块接入：在 BOARDS 里加一个函数，返回 (tasks, issues)。只读各板块文件，不改任何东西。
用法：python3 pipeline/任务清单.py [--print]
"""
import glob, json, os, re, sys, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.abspath(os.environ.get("LP_DATA") or os.path.join(ROOT, "data"))
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date()


def load(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def rel(p):
    return os.path.relpath(p, ROOT)


def days_since(s):
    try:
        return (TODAY - dt.date.fromisoformat(str(s)[:10])).days
    except Exception:
        return None


def task(board, tid, title, who="codex", pri=2, deliver=None, ref=None, items=None, note=None):
    """pri：1 = 今天做，2 = 本周，3 = 有空再做。"""
    return {"board": board, "id": f"{board}:{tid}", "title": title, "who": who, "pri": pri, "deliver": deliver, "ref": ref,
            "items": items, "n": len(items) if isinstance(items, list) else None, "note": note}


def issue(board, file, msg, key=None, who="codex", level="warn"):
    return {"board": board, "file": file, "key": key, "msg": msg, "who": who, "level": level}


# ---------- 通用：任务包 README 里「## X → `交付文件`」的条目，交付文件不存在 = 待办 ----------
def readme_tasks(board, readme, who="codex", pri=2):
    out = []
    if not os.path.exists(readme):
        return out
    txt = open(readme, encoding="utf-8").read()
    for m in re.finditer(r"^##\s+(.+?)→\s*`([^`]+)`", txt, re.M):
        title, f = m.group(1).strip(), m.group(2).strip()
        base = os.path.dirname(readme)
        pat = os.path.join(ROOT, f) if "/" in f and os.path.isdir(os.path.join(ROOT, f.split("/")[0])) else os.path.join(base, f)
        pat = re.sub(r"YYYYMMDD|<[^>]+>|\{[^}]+\}", "*", pat)
        if not glob.glob(pat):
            out.append(task(board, "pkg:" + re.sub(r"\W+", "-", title)[:40], title, who, pri, deliver=rel(pat), ref=rel(readme)))
    return out


# ---------- Alpha 雷达 ----------
VERDICTS = {"研究观察", "待核验", "拒绝", "优先研究"}


def check_alpha_file(path, leads):
    iss, rows = [], load(path)
    f = rel(path)
    if not isinstance(rows, list):
        return [issue("alpha", f, "不是 JSON 数组或解析失败", level="error")]
    for c in rows:
        k = c.get("key")
        if not k:
            iss.append(issue("alpha", f, "缺 key", level="error")); continue
        if k not in leads:
            iss.append(issue("alpha", f, "key 不在线索台账里（拼错或不是看板上的卡）", k))
        if c.get("verdict") not in VERDICTS:
            iss.append(issue("alpha", f, f"verdict「{c.get('verdict')}」不在三种之内", k, level="error"))
        ev = [e for e in c.get("evidence") or [] if str((e or {}).get("url", "")).startswith("http")]
        if not ev:
            iss.append(issue("alpha", f, "没有任何证据链接", k))
        if c.get("verdict") == "拒绝" and not ev:
            iss.append(issue("alpha", f, "拒绝没有证据链接", k, level="error"))
        for sk, s in (c.get("scores") or {}).items():
            if not isinstance(s, dict):
                continue
            v = s.get("v")
            if v in ("U", "NA", None, ""):
                continue
            lo, hi = (-1, 3) if sk == "TM" else ((0, 3) if sk == "TE" else (0, 4))
            if not isinstance(v, int) or not (lo <= v <= hi):
                iss.append(issue("alpha", f, f"{sk} 分数 {v} 超出 {lo}–{hi}", k, level="error"))
            elif not str(s.get("src", "")).startswith("http"):
                iss.append(issue("alpha", f, f"{sk} 分数没有来源链接", k))
        if not c.get("checked_utc"):
            iss.append(issue("alpha", f, "缺 checked_utc", k))
    return iss


def board_alpha():
    T, I = [], []
    q = load(os.path.join(DATA, "alpha", "research_queue.json"), {}) or {}
    leads = (load(os.path.join(DATA, "alpha", "alpha_leads.json"), {}) or {}).get("leads", {})
    rd = os.path.join(ROOT, "alpha", "review")
    files = sorted(glob.glob(os.path.join(rd, "*_checks.json")))
    by_key, codex_keys = {}, set()
    for p in files:
        I += check_alpha_file(p, leads)
        for c in load(p, []) or []:
            if isinstance(c, dict) and c.get("key"):
                by_key[c["key"]] = (os.path.basename(p), c)
                if not os.path.basename(p).startswith("grok_"):
                    codex_keys.add(c["key"])
    items = [{"key": i["key"], "name": i["name"], "status": i.get("status"), "fresh": i.get("fresh"), "kind": i.get("kind")} for i in q.get("items", [])]
    if items:
        T.append(task("alpha", "research", f"机会卡补证（队列 {len(items)} 个，从上往下补，M 新参与机制优先查）", "codex", 1,
                      deliver=f"alpha/review/codex_{TODAY.isoformat()}_checks.json（JSON 数组，reviewer = codex）",
                      ref="data/alpha/research_queue.json（prompt / schema / items）", items=items[:40],
                      note="排序：手动线索 / 本站板块 ★ → 新发现 → 有参与入口 → 收入高。同一天多批追加进同一个文件。"))
    grok = [{"key": k, "name": c.get("name"), "verdict": c.get("verdict")} for k, (fn, c) in by_key.items() if fn.startswith("grok_") and k not in codex_keys]
    if grok:
        T.append(task("alpha", "review-grok", f"复核 Grok 自动补证（{len(grok)} 个，便宜模型结论偏乐观）", "codex", 1,
                      deliver=f"alpha/review/codex_{TODAY.isoformat()}_checks.json", ref="alpha/review/grok_*_checks.json", items=grok))
    due = []
    for k, (fn, c) in by_key.items():
        nr = c.get("next_review")
        if nr and days_since(nr) is not None and days_since(nr) >= 0:
            due.append({"key": k, "name": c.get("name"), "next_review": nr})
    if due:
        T.append(task("alpha", "due", f"到期复核（{len(due)} 个，补证里写的下次复核日已到）", "codex", 1,
                      deliver=f"alpha/review/codex_{TODAY.isoformat()}_checks.json", items=due))
    opps = (load(os.path.join(DATA, "alpha", "opps.json"), {}) or {}).get("opps", [])
    cmc = load(os.path.join(ROOT, "alpha", "cmc_slugs.json"), {}) or {}
    need = sorted({(o["data"].get("tok") or {}).get("gecko") for o in opps
                   if (o["data"].get("tok") or {}).get("gecko") and ((o["data"]["tok"].get("chart") or {}).get("name") != "币安") and o["data"]["tok"]["gecko"] not in cmc})
    if need:
        T.append(task("alpha", "cmc", f"CMC 页面地址核对登记（{len(need)} 个币）", "codex", 3, deliver="alpha/cmc_slugs.json",
                      ref="AGENTS.md 第 4 节 3b", items=need))
    if not os.path.exists(os.path.join(rd, "sources_people.json")):
        T.append(task("alpha", "people", "关键人名单核对（S2）", "codex", 2, deliver="alpha/review/sources_people.json", ref="alpha/review/sources_task.md"))
    cases = (load(os.path.join(ROOT, "alpha", "cases.json"), {}) or {}).get("cases", [])
    miss = [c["id"] for c in cases if c.get("tokens") and not any(t.get("circ_peak") for t in c["tokens"])]
    if miss:
        T.append(task("alpha", "cases-circ", f"历史案例峰值日流通量登记（{len(miss)} 个，估值改流通口径用）", "codex", 3, deliver="alpha/cases.json 每个 tokens[] 加 circ_peak {数量, 日期, 出处}",
                      ref="alpha/review/fable_findings_20261115.md 第 12 条", items=miss))
    ctl = [c for c in cases if c.get("control")]
    if len(ctl) < 10:
        T.append(task("alpha", "cases-control", f"补失败样本 / 同期对照组（现在 {len(ctl)} 个，目标 ≥ 10）", "codex", 3,
                      deliver="alpha/review/cases_control_<日期>.json（格式同 alpha/cases.json 的 cases[]，带 why_control 和出处）", ref="alpha/cases.json"))
    for m in (load(os.path.join(ROOT, "alpha", "manual_leads.json"), {}) or {}).get("leads", []):
        if not m.get("sources"):
            I.append(issue("alpha", "alpha/manual_leads.json", "手动线索没有出处", m.get("id")))
    cost = load(os.path.join(DATA, "alpha", "research_cost.json"), {}) or {}
    a = cost.get("alert") or {}
    if a.get("at", "")[:7] == TODAY.strftime("%Y-%m"):
        I.append(issue("alpha", "data/alpha/research_cost.json", a.get("msg", "补证花费到上限"), who="大叔", level="error"))
    T += readme_tasks("alpha", os.path.join(rd, "README.md"))
    return T, I


# ---------- 发射台 ----------
def board_launchpad():
    T, I = [], []
    Q = load(os.path.join(DATA, "onchain", "平台质量.json"), {}) or {}
    P = Q.get("平台") or {}
    ev = load(os.path.join(ROOT, "config", "launchpad_events.json"), {}) or {}
    mx = load(os.path.join(DATA, "发射台矩阵.json"), {}) or {}
    top = sorted(mx.get("协议") or [], key=lambda p: -(p.get("7日") or 0))[:25]
    no_ev = [{"slug": p["slug"], "name": p.get("名称")} for p in top if not ev.get(p["slug"])]
    if no_ev:
        T.append(task("launchpad", "events", f"关键事件登记（近 7 天手续费前 25 的平台里 {len(no_ev)} 家还没有）", "codex", 2,
                      deliver="config/launchpad_events.json（每条 日期 / 事 / 出处，必须官方出处）", ref="docs/接口_发射台给Alpha.md", items=no_ev))
    notes = load(os.path.join(DATA, "onchain", "平台AI介绍.json"), {}) or {}
    no_note = [{"slug": p["slug"], "name": p.get("名称")} for p in top if p["slug"] not in notes]
    if no_note:
        T.append(task("launchpad", "intro", f"平台介绍（前 25 里 {len(no_note)} 家没有）", "codex", 3, deliver="按 pipeline/导入平台介绍.py 的格式", items=no_note))
    pend = sorted({k for v in P.values() for k, x in v.items() if isinstance(x, dict) and x.get("来源") == "待接入"})
    if pend:
        T.append(task("launchpad", "quality-fields", f"平台质量待接入字段：{'、'.join(pend)}", "claude", 3, ref="docs/接口_发射台给Alpha.md 字段优先级 4"))
    for slug, v in P.items():
        d = days_since(v.get("数据日"))
        if d is not None and d > 3:
            I.append(issue("launchpad", "data/onchain/平台质量.json", f"数据日 {v.get('数据日')} 已过 {d} 天", slug, who="claude"))
    for slug, xs in ev.items():
        if slug.startswith("_"):
            continue
        for e in xs or []:
            if not str(e.get("出处", "")).startswith("http") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(e.get("日期", ""))):
                I.append(issue("launchpad", "config/launchpad_events.json", "事件缺日期或官方出处", slug))
    return T, I


# ---------- AI Agent / RWA / 龙头选币 / 事件日历 / 聪明钱 ----------
def board_aiagent():
    T = readme_tasks("aiagent", os.path.join(ROOT, "aiagent", "review", "README.md"))
    reg = load(os.path.join(ROOT, "aiagent", "aiagent_registry.json"), {}) or {}
    if reg.get("open_items"):
        T.append(task("aiagent", "open-items", f"监控地图待核事项（{len(reg['open_items'])} 条）", "codex", 3, deliver="aiagent/aiagent_registry.json", items=reg["open_items"]))
    return T, []


def board_rwa():
    return readme_tasks("rwa", os.path.join(ROOT, "rwa", "review", "README.md")), []


def board_core():
    T, I = [], []
    C = load(os.path.join(ROOT, "core", "core_config.json"), {}) or {}
    cards = C.get("cards") or {}
    no = [c["sym"] for c in C.get("coins") or [] if c.get("sym") not in cards]
    if no:
        T.append(task("core", "cards-draft", f"六问卡草稿（{len(no)} 个币没有核对过的卡；Codex 出草稿，大叔核对后才进 cards）", "codex", 3,
                      deliver="core/review/cards_draft_<日期>.json（键同 core_config.json 的 _cards_说明，每栏带出处）", ref="core/core_config.json _cards_说明", items=no))
        T.append(task("core", "cards-confirm", "核对六问卡草稿（只有大叔核对过的才算，R1 要七栏齐）", "大叔", 3, ref="core/review/cards_draft_*.json"))
    for c in cards.values() if isinstance(cards, dict) else []:
        nx = c.get("next")
        if nx and days_since(nx) is not None and days_since(nx) >= 0:
            T.append(task("core", "card-due:" + str(c.get("sym", "")), f"{c.get('sym')} 卡片到下一检查日", "codex", 2))
    T += readme_tasks("core", os.path.join(ROOT, "core", "review", "README.md"))
    return T, I


def board_cal():
    T, I = [], []
    R = load(os.path.join(ROOT, "cal", "reg_events.json"), {}) or {}
    d = days_since(R.get("checked_utc"))
    if d is None or d >= 7:
        T.append(task("cal", "reg-check", f"立法 / 外国议会表决核对（上次 {R.get('checked_utc') or '没有'}，每周一次）", "codex", 1 if (d or 99) >= 14 else 2,
                      deliver="cal/reg_events.json（改 checked_utc；不收的写进 excluded；每条官方来源）", ref="CLAUDE.md cal/ ③"))
    return T, I


def board_smartmoney():
    st = "立项阶段（S0），立项书定稿前不采集、不出页面"
    return [task("smartmoney", "s0", "聪明钱：等立项书定稿（主体 / 证据等级 / 入选规则写死后才开 S1）", "大叔", 3, ref="smartmoney/research/立项书.md", note=st)], []


def board_status():
    S = load(os.path.join(DATA, "refresh_status.json"), {}) or {}
    I = [issue("site", "data/refresh_status.json", f"交易数据未到：{x}", who="claude") for x in S.get("not_ready") or []]
    return [], I


BOARDS = [("alpha", "Alpha 雷达", board_alpha), ("launchpad", "发射台", board_launchpad), ("aiagent", "AI Agent", board_aiagent),
          ("rwa", "RWA", board_rwa), ("core", "龙头选币", board_core), ("cal", "事件日历", board_cal),
          ("smartmoney", "聪明钱", board_smartmoney), ("site", "全站数据状态", board_status)]


def main():
    tasks, issues, boards = [], [], []
    for k, name, fn in BOARDS:
        try:
            t, i = fn()
        except Exception as e:
            t, i = [], [issue(k, "pipeline/任务清单.py", f"这个板块的检查自己出错了：{str(e)[:160]}", who="claude", level="error")]
        tasks += t
        issues += i
        boards.append({"board": k, "name": name, "tasks": len(t), "issues": len(i)})
    tasks.sort(key=lambda x: (x["pri"], x["who"] != "codex", x["board"]))
    gen = NOW.isoformat(timespec="seconds")
    json.dump({"generated": gen, "boards": boards, "tasks": tasks,
               "how": "Codex 每天：先改 check_report.json 里 who=codex 的问题，再按 tasks 从上往下做 who=codex 的；交付文件推 main。who=claude 的攒给 Claude 每周处理，who=大叔 的等大叔。"},
              open(os.path.join(DATA, "tasks.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"generated": gen, "issues": issues, "n": len(issues), "errors": sum(1 for x in issues if x["level"] == "error")},
              open(os.path.join(DATA, "check_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    W = {"codex": "Codex", "claude": "Claude", "大叔": "大叔"}
    md = [f"# 全站待办与检查（{gen[:16].replace('T', ' ')} UTC 自动生成，别手改）", "",
          "| 板块 | 待办 | 问题 |", "|---|---|---|"] + [f"| {b['name']} | {b['tasks']} | {b['issues']} |" for b in boards] + ["", "## 待办", ""]
    for t in tasks:
        md.append(f"- **P{t['pri']} · {W.get(t['who'], t['who'])} · {t['board']}** {t['title']}" + (f" → `{t['deliver']}`" if t.get("deliver") else "") + (f"（参考 `{t['ref']}`）" if t.get("ref") else ""))
    md += ["", "## 检查出的问题", ""] + ([f"- [{x['level']}] {W.get(x['who'], x['who'])} · `{x['file']}`{' · ' + str(x['key']) if x.get('key') else ''}：{x['msg']}" for x in issues] or ["- 没有"])
    open(os.path.join(DATA, "tasks.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(f"全站待办 {len(tasks)} 条（Codex {sum(1 for t in tasks if t['who'] == 'codex')} / Claude {sum(1 for t in tasks if t['who'] == 'claude')} / 大叔 {sum(1 for t in tasks if t['who'] == '大叔')}），检查问题 {len(issues)} 条")
    if "--print" in sys.argv:
        print("\n".join(md))


if __name__ == "__main__":
    main()
