#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""平台二级页面的 AI 研究摘要（大叔 2026-11-12 定：只给进过 0.1% 份额的平台写）。

· 没配 ANTHROPIC_API_KEY（GitHub Secret）就跳过，页面照旧用 DefiLlama 介绍 / 官网自述。
· 资料只用我们自己收集的：DefiLlama 协议详情与手续费口径原文、融资 / 安全事件 / 大事记、本站手续费数据、
  人工档案（config/launchpad_profiles.json）、官网首页和文档页的正文。AI 不上网，资料里没有的写「资料未提及」。
· 资料没变就不重写（输入哈希），最长 30 天重写一次；每次最多写 MAX_PER_RUN 个。
· 结果 data/onchain/平台AI介绍.json，中英各一份，页面标明「AI 根据资料整理，未人工核实」。
"""
import os, re, json, html, hashlib, datetime as dt, urllib.parse

import 发射台名录 as DIR

MODEL = "claude-opus-5-5"
MAX_PER_RUN = 12
REWRITE_DAYS = 30
SITE_TEXT_MAX = 12000
OUT = os.path.join(DIR.OC, "平台AI介绍.json")

TEXT_FIELDS = ["one_liner", "differentiation", "fee_split", "token", "team"]
LIST_FIELDS = ["selling_points", "risks", "unknowns"]
SCHEMA = {
    "type": "object",
    "properties": {**{f"{k}_{l}": {"type": "string"} for k in TEXT_FIELDS for l in ("zh", "en")},
                   **{f"{k}_{l}": {"type": "array", "items": {"type": "string"}} for k in LIST_FIELDS for l in ("zh", "en")}},
    "required": [f"{k}_{l}" for k in TEXT_FIELDS + LIST_FIELDS for l in ("zh", "en")],
    "additionalProperties": False,
}

SYSTEM = """你是「链上大叔研究台」的研究员，给一个代币发射台（launchpad）写平台介绍，读者是想快速看懂这个平台的普通加密用户。

规则：
1. 只用下面「资料」里写到的事实。资料里没有的，写「资料未提及」/ "Not stated in the sources"，不要猜，不要用你自己的记忆补。
2. 不写任何买卖建议、价格预测或「值得关注 / 有潜力」之类的评价。只说它是什么、怎么运作、钱怎么分。
3. 中文用大白话，短句；英文简洁。数字照资料写，标明是哪一天 / 哪个口径。
4. 各字段：
   - one_liner：一句话说清它是什么、最大的不同是什么（40 字以内 / 25 words）。
   - selling_points：核心卖点 2～5 条，每条一句。
   - differentiation：和一般发射台（如 pump.fun 式联合曲线发币）比，机制上哪里不一样；资料不够就直说。
   - fee_split：手续费怎么收、怎么分（给协议 / 创作者 / 持币人回购 / 交易者返现等），按 DefiLlama 口径原文和官网说明归纳，写清比例和生效日期。
   - token：平台币（代码、用途、回购销毁）；没有就写没有。
   - team：团队、背后公司、融资方；资料里只有 X 账号或什么都没有，就如实写。
   - risks：资料里能看出来的风险或疑点（如安全事件、数据口径变化、刚上线、费用比例改过、只有一条链），没有就给空数组。
   - unknowns：想了解但资料里没有的关键信息（如审计、团队身份），最多 4 条。
5. _zh 字段写中文，_en 字段写对应英文，内容一致。"""


def _visible_text(raw):
    t = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def site_text(url):
    """官网首页正文 + 文档页（首页上 docs / gitbook / whitepaper 链接，或 /docs）的正文，截到 SITE_TEXT_MAX。"""
    if not url:
        return "", []
    parts, used = [], []
    try:
        raw, ct, final = DIR._get(url)
        page = raw.decode("utf-8", errors="ignore")
        parts.append(f"[官网首页 {final}]\n" + _visible_text(page)[:5000])
        used.append(final)
        docs = []
        for m in re.finditer(r'href\s*=\s*["\']([^"\']+)["\']', page, re.I):
            h = m.group(1)
            if re.search(r"docs?\b|gitbook|whitepaper|litepaper|faq|how-it-works", h, re.I) and not h.startswith(("mailto:", "#")):
                docs.append(urllib.parse.urljoin(final, h))
        docs = list(dict.fromkeys(docs))[:2] or [urllib.parse.urljoin(final, "/docs")]
        for d in docs:
            try:
                r2, _, f2 = DIR._get(d)
                txt = _visible_text(r2.decode("utf-8", errors="ignore"))
                if len(txt) > 200:
                    parts.append(f"[文档 {f2}]\n" + txt[:6000])
                    used.append(f2)
            except Exception:
                pass
    except Exception as ex:
        parts.append(f"[官网打不开：{str(ex)[:80]}]")
    return "\n\n".join(parts)[:SITE_TEXT_MAX], used


def materials(p, info, prof, share7, share30):
    lines = [f"平台：{p['名称']}（DefiLlama slug：{p['slug']}）",
             f"链：{', '.join(p.get('链') or [])}",
             f"本站数据（截至 {p.get('数据日')}，DefiLlama 手续费）：近 7 日 ${p.get('7日') or 0:,.0f}（全网发射台份额 {share7:.2%}），"
             f"近 30 日 ${p.get('30日') or 0:,.0f}（{share30:.2%}），累计 ${p.get('累计') or 0:,.0f}；首次出现在 DefiLlama 发射台类目：{p.get('首次出现') or '—'}"]
    for k in ("介绍", "官网", "X", "代币", "市值", "上线DefiLlama", "母协议", "审计数"):
        if info.get(k) not in (None, "", []):
            lines.append(f"DefiLlama {k}：{info[k]}")
    for k, v in (info.get("口径") or {}).items():
        lines.append(f"DefiLlama 手续费口径 {k}：{v}")
    for r in info.get("融资") or []:
        lines.append(f"融资：{json.dumps(r, ensure_ascii=False)}")
    for h in info.get("安全事件") or []:
        lines.append(f"安全事件：{json.dumps(h, ensure_ascii=False)}")
    for d, t in info.get("大事记") or []:
        lines.append(f"DefiLlama 大事记 {d}：{t}")
    if prof.get("叙事"):
        lines.append(f"本站人工整理（出处：{prof.get('来源')}）：{prof['叙事']}")
    if prof.get("团队"):
        lines.append(f"本站人工整理 团队：{prof['团队']}")
    return "\n".join(lines)


def main():
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print("  AI 平台介绍：没配 ANTHROPIC_API_KEY，跳过（页面用 DefiLlama 介绍 / 官网自述）")
        return
    import anthropic
    client = anthropic.Anthropic()
    matrix = DIR.load(os.path.join(DIR.DATA, "发射台矩阵.json"), {}) or {}
    P = {p["slug"]: p for p in matrix.get("协议") or []}
    t7 = sum(p.get("7日") or 0 for p in P.values()) or 1
    t30 = sum(p.get("30日") or 0 for p in P.values()) or 1
    infos = DIR.platform_info()
    out = DIR.load(OUT, {}) or {}
    prof_all = DIR.profiles()
    today = dt.date.today().isoformat()
    stale = (dt.date.today() - dt.timedelta(days=REWRITE_DAYS)).isoformat()
    slugs = sorted(set(DIR.platform_slugs(matrix)) | set(infos), key=lambda s: -((P.get(s) or {}).get("7日") or 0))
    n = fail = 0
    for slug in slugs:
        p = P.get(slug)
        if not p or n >= MAX_PER_RUN:
            continue
        info = infos.get(slug) or {}
        pid = next((k for k, v in prof_all.items() if not k.startswith("_") and v.get("defillama") == slug), None)
        prof = prof_all.get(pid or "", {})
        # 哈希只算「平台是什么」的资料，不算每天变的手续费数字
        base = materials({**p, "7日": 0, "30日": 0, "累计": 0, "数据日": ""}, info, prof, 0, 0)
        old = out.get(slug) or {}
        if old.get("日期", "") >= stale and old.get("资料哈希") == hashlib.sha256(base.encode()).hexdigest()[:16]:
            continue
        stext, used = site_text(info.get("官网"))
        mat = materials(p, info, prof, (p.get("7日") or 0) / t7, (p.get("30日") or 0) / t30)
        prompt = f"资料：\n{mat}\n\n官网与文档正文（平台自己的说法）：\n{stext or '（没抓到）'}"
        n += 1
        try:
            resp = client.beta.messages.create(
                model=MODEL, max_tokens=8000,
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                system=SYSTEM,
                output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.RateLimitError:
            print("  AI 平台介绍：限流，本次到此为止")
            break
        except anthropic.AuthenticationError:
            print("  AI 平台介绍：API key 无效，跳过")
            return
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as ex:
            print(f"  AI 平台介绍 {slug} 失败：{str(ex)[:120]}")
            fail += 1
            continue
        if resp.stop_reason != "end_turn":
            print(f"  AI 平台介绍 {slug}：没写完（{resp.stop_reason}），跳过")
            fail += 1
            continue
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            print(f"  AI 平台介绍 {slug}：返回不是 JSON，跳过")
            fail += 1
            continue
        out[slug] = {"日期": today, "模型": resp.model, "资料哈希": hashlib.sha256(base.encode()).hexdigest()[:16],
                     "官网已读": used, "资料截至": p.get("数据日"), "内容": data,
                     "用量": {"输入": resp.usage.input_tokens, "输出": resp.usage.output_tokens}}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
    tok_in = sum((v.get("用量") or {}).get("输入", 0) for v in out.values() if v.get("日期") == today)
    tok_out = sum((v.get("用量") or {}).get("输出", 0) for v in out.values() if v.get("日期") == today)
    print(f"  AI 平台介绍：本次写 {n - fail} 个、失败 {fail} 个，已有 {len(out)} 个；今天用量 输入 {tok_in:,} / 输出 {tok_out:,} tokens"
          f"（约 ${tok_in / 1e6 * 4 + tok_out / 1e6 * 20:.2f}）")


if __name__ == "__main__":
    main()
