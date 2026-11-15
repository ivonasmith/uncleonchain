#!/usr/bin/env python3
"""Alpha 雷达每日自动补证（Grok API）。2026-11-15 起替代定时云端会话（那种会话挂不上仓库、推不上去，还占大叔的 Claude 额度）。

在 alpha-daily 里跑：alpha_daily.py 生成 data/alpha/research_queue.json → 本脚本按队列顺序补证 → opps.py 并入。
  · 调用照 pipeline/写平台介绍.py：xAI Responses 接口 + x_search / web_search，max_turns 封顶。
  · 预算（alpha_config.json 的 grok）：每天 daily_usd、每月 monthly_usd。花费按接口返回的 cost_in_usd_ticks 记账
    （data/alpha/research_cost.json，按月累计）。到月度线就停，并把 alert 写进账本，工作流标红（GitHub 发邮件提醒大叔）。
  · 结果写 alpha/review/grok_<UTC 日期>_checks.json（reviewer = grok-auto），格式同 research_queue.json 的 schema。
  · 写入前机器检查：verdict 只能三种；拒绝必须有一手证据（官网 / 文档 / 官方 X / 链上浏览器），否则降为待核验；
    分数超出范围的作废记 U；没有来源的分数记 U。
没配 XAI_API_KEY 就跳过。本地试：XAI_API_KEY=... python3 alpha/grok_research.py --dry --n 1
"""
import os, re, sys, json, time, datetime as dt, urllib.request, urllib.error, concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "alpha")
COST = os.path.join(OUT, "research_cost.json")


def load(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


CFG = (load(os.path.join(HERE, "alpha_config.json"), {}) or {}).get("grok") or {}
MODEL = os.environ.get("XAI_MODEL") or CFG.get("model", "grok-4.7")
MAX_TURNS = CFG.get("max_turns", 2)
CALL_LIMIT = CFG.get("call_limit_s", 360)
FW = load(os.path.join(HERE, "framework.json"), {})

SYSTEM = """你是「链上大叔研究台」Alpha 雷达的研究员，给一个新协议 / 新玩法补证。只研究正规项目；只给事实和过程记录，不写买入、卖出、仓位、止损、目标价，不写「值得关注 / 有潜力」。

做法：
1. 用 web_search 查官网、文档、官方公告、DefiLlama 协议页；用 x_search 查官方 X 账号和讨论它的帖子。每条事实都要有链接。
2. 查不到写 "U"，说法互相矛盾写「说法不一」并给两边链接。不要用你自己的记忆补，不要估。KOL 的吹捧不算事实。
3. 一手证据 = 官网、官方文档、官方 X 账号、合约 / 链上浏览器、DefiLlama 方法论。媒体报道、聚合站、别人的帖子都是二手。
4. 「已有代币」本身不是拒绝理由：kind = tokenless 的如果查到其实已经有代币，写进 token_stance 和 missing，verdict 给待核验；
   kind = surge / site / manual 的本来就可能有代币，照常研究它的新玩法。
5. verdict 只能是：研究观察（对象明确、有可证伪假设、没查到否决项）/ 待核验（关键事实缺失或冲突，写清缺什么）/ 拒绝（身份错误、已确认风险、
   不是对普通人开放的正规项目）。拒绝必须有一手证据；只有二手证据的最多给待核验。
6. 分数按下面的锚点给，每个分数都要 why（为什么是这一档）和 src（链接）；没依据就写 U，不要凑。M（新参与机制：这个玩法新在哪）最重要，优先查。
   TM（团队）有已证实的不良记录（跑路、欺诈、重大事故未处理）给 -1。还没代币的 TE 写 NA。
7. 资金参与方式 entry 从 buy / stake / points / use / presale / mine / none 里选（none = 暂时没有资金入口），写 entry_why 并带链接。
   积分计划要写清积分能换什么、有没有公布兑换规则。
8. 中文大白话、短句。one_liner 30 字以内。每个文字字段 150 字以内，missing 最多 6 条，evidence 最多 10 条。
9. 只输出一个 JSON 对象，不要任何别的文字，不要 Markdown 代码块。"""


def anchors():
    out = []
    for g in ("mech", "part", "invest"):
        for it in (FW.get("scores", {}).get(g) or {}).get("items", []):
            if it.get("private"):
                continue
            a = " / ".join(f"{i}={x}" for i, x in enumerate(it["anchors"]))
            pen = "；" + "；".join(f"{k}={v}" for k, v in (it.get("penalty") or {}).items()) if it.get("penalty") else ""
            out.append(f"{it['k']} {it['name']}（{it.get('q', '')}）：{a}{pen}")
    return "\n".join(out)


def _text(data):
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"].strip()
    parts = []
    for item in data.get("output") or []:
        if item.get("type") == "message":
            parts += [b.get("text") for b in item.get("content") or [] if b.get("type") == "output_text" and b.get("text")]
    return "\n".join(parts).strip()


def _json(text):
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            return json.loads(t[i:j + 1])
        raise


def call(key, prompt):
    body = {"model": MODEL, "input": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            "tools": [{"type": "web_search"}, {"type": "x_search"}], "max_turns": MAX_TURNS}
    req = urllib.request.Request("https://api.x.ai/v1/responses", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "uncleonchain-alpha-research"})
    try:
        with urllib.request.urlopen(req, timeout=CALL_LIMIT) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {e.read().decode('utf-8', 'ignore')[:200]}")
    u = data.get("usage") or {}
    ticks = u.get("cost_in_usd_ticks")
    usd = ticks / 1e10 if isinstance(ticks, (int, float)) and ticks > 0 else None
    tools = u.get("server_side_tool_usage_details") or {}
    meta = {"model": data.get("model") or MODEL, "in": u.get("input_tokens"), "out": u.get("output_tokens"),
            "x_posts": tools.get("x_posts_fetched"), "searches": (tools.get("x_search_calls") or 0) + (tools.get("web_search_calls") or 0), "usd": usd}
    text = _text(data)
    if not text:
        raise RuntimeError("没有返回正文", meta)
    return _json(text), meta


FIRST_HAND = re.compile(r"defillama\.com|etherscan|bscscan|solscan|basescan|arbiscan|explorer|github\.com|docs\.|gitbook|/docs", re.I)


def clean(item, r, now):
    """机器检查：不合格的字段改成 U / 降级，并在 missing 里写明。"""
    note = []
    r = {k: v for k, v in r.items() if k != "reviewer"}
    r.update(key=item["key"], name=r.get("name") or item["name"], reviewer="grok-auto", checked_utc=now)
    v = r.get("verdict")
    if v not in ("研究观察", "待核验", "拒绝"):
        note.append(f"结论「{v}」不在三种之内，改为待核验")
        r["verdict"] = "待核验"
    ev = [e for e in r.get("evidence") or [] if isinstance(e, dict) and str(e.get("url", "")).startswith("http")]
    r["evidence"] = ev[:10]
    off = (item.get("url") or "").split("//")[-1].split("/")[0].replace("www.", "")
    first = [e for e in ev if FIRST_HAND.search(e["url"]) or (off and off in e["url"]) or "x.com/" in e["url"] and (r.get("official_x") or "") and r["official_x"].lstrip("@").lower() in e["url"].lower()]
    if r["verdict"] == "拒绝" and not first:
        note.append("拒绝没有一手证据，降为待核验")
        r["verdict"] = "待核验"
    sc = {}
    for k, s in (r.get("scores") or {}).items():
        if not isinstance(s, dict):
            continue
        val, lo, hi = s.get("v"), (-1 if k == "TM" else 0), (3 if k in ("TM", "TE") else 4)
        if isinstance(val, str) and re.fullmatch(r"-?\d", val):
            val = int(val)
        if val in ("U", "NA"):
            sc[k] = {"v": val, "why": s.get("why") or "", "src": s.get("src") or ""}
        elif isinstance(val, int) and lo <= val <= hi and str(s.get("src", "")).startswith("http") and s.get("why"):
            sc[k] = {"v": val, "why": str(s["why"])[:200], "src": s["src"]}
        else:
            note.append(f"{k} 分数没有来源或超出范围，记 U")
            sc[k] = {"v": "U", "why": "", "src": ""}
    r["scores"] = sc
    if note:
        r["missing"] = (r.get("missing") or []) + ["（机器检查）" + x for x in note]
    return r


def main():
    dry = "--dry" in sys.argv
    n_max = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else CFG.get("max_items", 8)
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        print("自动补证：没配 XAI_API_KEY，跳过")
        return 0
    q = load(os.path.join(OUT, "research_queue.json"), {}) or {}
    now = dt.datetime.now(dt.timezone.utc)
    today, month = now.date().isoformat(), now.strftime("%Y-%m")
    ledger = load(COST, {}) or {}
    M = ledger.setdefault(month, {"usd": 0.0, "calls": 0, "items": 0, "days": {}})
    D = M["days"].setdefault(today, {"usd": 0.0, "calls": 0})
    day_cap, month_cap = CFG.get("daily_usd", 0.5), CFG.get("monthly_usd", 5)
    if M["usd"] >= month_cap:
        msg = f"本月补证花费 ${M['usd']:.2f} 已到上限 ${month_cap}，暂停。要继续就在 alpha/alpha_config.json 的 grok.monthly_usd 调高。"
        print("::warning::" + msg)
        ledger["alert"] = {"at": now.isoformat(timespec="seconds"), "msg": msg}
        json.dump(ledger, open(COST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return 0
    # 最近 7 天补过的跳过（新发现除外）
    recent = set()
    cut = (now - dt.timedelta(days=7)).isoformat()
    rd = os.path.join(HERE, "review")
    for fn in os.listdir(rd):
        if fn.endswith("_checks.json"):
            for c in load(os.path.join(rd, fn), []) or []:
                if (c.get("checked_utc") or "") >= cut:
                    recent.add(c.get("key"))
                if not fn.startswith("grok_") and (c.get("checked_utc") or "") >= (now - dt.timedelta(days=30)).isoformat():
                    recent.add(c.get("key"))   # Codex / 人工 30 天内核对过的不重复补
    todo = [i for i in q.get("items", []) if i["key"] not in recent][:n_max]
    path = os.path.join(rd, f"grok_{today}_checks.json")
    done = load(path, []) or []
    keys_done = {c["key"] for c in done}
    tmpl = json.dumps(q.get("schema", {}), ensure_ascii=False)
    A = anchors()
    stop = 0
    for it in todo:
        if it["key"] in keys_done:
            continue
        if D["usd"] >= day_cap or M["usd"] >= month_cap:
            print(f"到预算线（今天 ${D['usd']:.2f} / ${day_cap}，本月 ${M['usd']:.2f} / ${month_cap}），停")
            stop = 1
            break
        prompt = (f"要补证的对象：\n{json.dumps(it, ensure_ascii=False)}\n\n评分锚点（0 起算）：\n{A}\n\n"
                  f"交付格式（按这个 JSON 结构填，key 原样照抄；另加 official_x 字段写官方 X 账号，查不到写 U）：\n{tmpl}")
        t0 = time.time()
        ex = cf.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(call, key, prompt)
        try:
            r, meta = fut.result(timeout=CALL_LIMIT + 30)
        except Exception as e:
            print(f"  {it['name']}: 失败 {str(e)[:200]}")
            if "401" in str(e) or "403" in str(e):
                print("::warning::xAI key 无效或没权限，自动补证停")
                break
            continue
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
        usd = meta.get("usd") or 0
        D["usd"] += usd; D["calls"] += 1; M["usd"] += usd; M["calls"] += 1; M["items"] += 1
        r = clean(it, r, now.isoformat(timespec="seconds"))
        r["_usage"] = meta
        print(f"  {it['name']}: {r['verdict']} · M={r['scores'].get('M', {}).get('v', 'U')} · {time.time() - t0:.0f} 秒 · ${usd:.3f} · 输入 {meta.get('in')} 输出 {meta.get('out')} 搜索 {meta.get('searches')}")
        if dry:
            print(json.dumps(r, ensure_ascii=False, indent=1))
            continue
        done.append(r)
        json.dump(done, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    M["usd"], D["usd"] = round(M["usd"], 4), round(D["usd"], 4)
    if M["usd"] >= month_cap:
        ledger["alert"] = {"at": now.isoformat(timespec="seconds"), "msg": f"本月补证花费 ${M['usd']:.2f}，已到上限 ${month_cap}"}
    if not dry:
        json.dump(ledger, open(COST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"自动补证：今天 {D['calls']} 次 ${D['usd']:.3f}；本月 {M['calls']} 次 ${M['usd']:.3f} / ${month_cap}；队列 {q.get('n')} 个" + ("（预算停）" if stop else ""))
    return 0   # 到上限不在这里报错（免得后面重算网站的步骤被跳过）；工作流最后一步读账本的 alert 再标红


if __name__ == "__main__":
    sys.exit(main())
