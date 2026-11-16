#!/usr/bin/env python3
"""表达 + SEO 文案检查（docs/表达规范.md §2、§3；docs/SEO规范.md §2 板块约定 3）。

只扫 site/ 里的 index.html，列出可疑处和上下文，**由人判定**，脚本不替人下结论。

三类：
  1. 指令词（强）：不追高 / 加仓 / 减仓 / 风险预算 / 止损 / 止盈 / 抄底 / 不开新空 …
     - 在 <meta name="description"> 里出现 → 一律报（SEO 规范：description 不写操作性措辞，历史页也一样）
     - 在正文出现 → 豁免页（方法论、口径、日志、更正记录、复盘等）不报；其余页报
  2. 指令词（弱）：买入 / 卖出 / 建仓 / 建议 / 应该 …，只在非豁免页报。很多是产品说明里的正常用语，要人看上下文。
  3. 行话：P90 / σ / z 值 / STH / 闸门 等，只看正文开头 300 字（表达规范 §3「第一句不出现行话」）。

用法：python3 .claude/skills/uncleonchain-site-check/scripts/expr_check.py [site 目录=site] [--loose]
退出码：有「强」命中（非豁免页正文，或任何页的 description）返回 1，否则 0。
"""
import os, re, sys, html

STRONG = ["不追高", "追高", "加仓", "减仓", "调仓", "风险预算", "仓位倍数", "止损", "止盈", "抄底", "逃顶",
          "不开新空", "分批加", "分批买"]
LOOSE = ["买入", "卖出", "建仓", "建议", "应该", "仓位"]
JARGON = [r"P\d{2}\b", r"σ", r"z 值", r"\bz\s*[<>]", r"\bSTH\b", r"闸门", r"\bpp\b"]
# 历史 / 方法论 / 原文引用：这些页的指令词是引用或记录，不算违规（表达规范 §1 第三档的例外）
EXEMPT = ("journal", "corrections", "methodology", "method", "framework", "reports", "posts",
          "glossary", "changelog", "rotation", "report", "library", "data", "assets", "monitor")
SKIP = {"data", "assets", "monitor"}
# 否定句（「不作抄底信号」「不写买入、卖出」）是免责声明，不是指令：强命中里跳过，但计数列出
NEG = re.compile(r"(不作|不当|不写|不算|不是|不构成|不据此|不用|不做|不按|不许|不给|不出|不叫|不把)[^。；;]{0,8}$")


def visible(h):
    h = re.sub(r"(?is)<(script|style|template|nav|footer|aside)\b.*?</\1>", " ", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(h)).strip()


def ctx(t, m, n=22):
    return t[max(0, m.start() - n): m.end() + n].replace("\n", " ")


def is_exempt(rel):
    segs = rel.strip("/").split("/")
    return any(s in EXEMPT for s in segs)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    loose_on = "--loose" in sys.argv
    site = os.path.abspath(args[0] if args else "site")
    strong_hits, loose_hits, jargon_hits, negated = [], [], [], []
    n = 0
    for root, dirs, files in os.walk(site):
        dirs[:] = [d for d in dirs if d not in SKIP]
        if "index.html" not in files:
            continue
        rel = "/" + os.path.relpath(root, site).replace(os.sep, "/").strip(".") + "/"
        rel = re.sub(r"/+", "/", rel)
        h = open(os.path.join(root, "index.html"), encoding="utf-8", errors="ignore").read()
        if 'http-equiv="refresh"' in h:
            continue
        n += 1
        m = re.search(r'<meta name="description" content="([^"]*)"', h)
        desc = html.unescape(m.group(1)) if m else ""
        for w in STRONG:
            i = desc.find(w)
            if i >= 0 and not NEG.search(desc[max(0, i - 12): i]):
                strong_hits.append((rel, "description", w, desc[max(0, i - 22): i + len(w) + 22]))
        mm = re.search(r'(?s)<main class="main">(.*)</main>', h)
        body = visible(mm.group(1) if mm else h)
        if is_exempt(rel):
            continue
        for w in STRONG:
            for x in re.finditer(re.escape(w), body):
                if NEG.search(body[max(0, x.start() - 12): x.start()]):
                    negated.append((rel, w))
                    continue
                strong_hits.append((rel, "正文", w, ctx(body, x)))
        if loose_on:
            for w in LOOSE:
                for x in re.finditer(re.escape(w), body):
                    loose_hits.append((rel, w, ctx(body, x)))
        head = body[:300]
        for j in JARGON:
            for x in re.finditer(j, head):
                jargon_hits.append((rel, j, ctx(head, x, 14)))

    print(f"表达检查：{n} 页（豁免页 {', '.join(EXEMPT[:6])} 等不扫正文指令词）")
    print(f"\n【强】指令词 {len(strong_hits)} 处（description 或非豁免页正文）— 应改成状态 / 历史")
    for rel, where, w, c in strong_hits[:60]:
        print(f"  {rel}  [{where}] {w} ← …{c}…")
    if len(strong_hits) > 60:
        print(f"  …还有 {len(strong_hits) - 60} 处")
    print(f"（另有 {len(negated)} 处是否定句 / 免责声明，已跳过）")
    print(f"\n【行话】正文开头 300 字 {len(jargon_hits)} 处 — 第一句要大白话（表达规范 §3）")
    for rel, j, c in jargon_hits[:30]:
        print(f"  {rel}  {j} ← …{c}…")
    if loose_on:
        print(f"\n【弱】买入 / 卖出 / 建仓 / 建议 / 应该 {len(loose_hits)} 处 — 人工看是不是指令")
        for rel, w, c in loose_hits[:80]:
            print(f"  {rel}  {w} ← …{c}…")
    else:
        print("\n（弱指令词未列出；加 --loose 查看）")
    return 1 if strong_hits else 0


if __name__ == "__main__":
    sys.exit(main())
