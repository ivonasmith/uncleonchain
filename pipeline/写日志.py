#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解读日志 · 每日一篇 + 每周复盘 + 每月复盘（规则化自动解读，GitHub Actions 里跑，不消耗 Claude 额度）

读：data/宏观台账.json（拉宏观.py）、data/l2/l2_latest.json（l2/l2_daily.py，L2 周期状态机）、build/网站素材.json（出看板.py，发射台部分）、已有日志
写：data/解读日志/日/<YYYY-MM-DD>.json   日期 = 解读当天（UTC）；每个读数自带「截至」数据日期
    data/解读日志/周/<YYYY-Www>.json     ISO 周（周一到周日），周一跑时补出上一周
    data/解读日志/月/<YYYY-MM>.json      每月 1 日补出上个月

冻结规则（公开记录的可信度来自不改历史）：
  一篇日志写入后不再重写；唯一例外是同一天重跑时核心指标缺得更少（数据源当天晚到），
  这时覆盖并标记「补录」，保留首次生成时间。周 / 月复盘同理，写过就不再动。
  人工点评不写进这里——放 content/journal/，出网站时拼到对应页面，随时可改。
"""
import os, json, glob
from common import DATA, OUT, load, today_utc
import 宏观规则 as R

J = os.path.join(DATA, "解读日志")
for sub in ("日", "周", "月"):
    os.makedirs(os.path.join(J, sub), exist_ok=True)


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def all_daily():
    return [read(p) for p in sorted(glob.glob(os.path.join(J, "日", "*.json")))]


def main():
    L = load("宏观台账.json", {}) or {}
    S = L.get("序列") or {}
    sd_path = os.path.join(OUT, "网站素材.json")
    sd = read(sd_path) if os.path.exists(sd_path) else None
    today = today_utc()

    logs = all_daily()
    prev = [x for x in logs if x["日期"] < today]
    prev_log = prev[-1] if prev else None
    new = R.daily_log(today, S, sd, prev_log, L.get("源状态"), load("l2/l2_latest.json"))
    p = os.path.join(J, "日", f"{today}.json")
    if os.path.exists(p):
        old = read(p)
        # 规则版本不同（比如 2026-10-02 的 L1 改版）时核心指标清单也不同，不拿来比，旧日志原样冻结
        if old.get("版本") == new.get("版本") and len(new["核心缺失"]) < len(old.get("核心缺失", [])):
            new["补录"] = True
            new["首次生成UTC"] = old.get("首次生成UTC") or old.get("生成时间UTC")
            write(p, new)
            print(f"日志 {today} 补录（核心缺失 {len(old.get('核心缺失', []))} → {len(new['核心缺失'])}）")
        else:
            print(f"日志 {today} 已存在，冻结不改")
    else:
        write(p, new)
        print(f"日志 {today} 已写入：{new['综合']['一句话']}")

    logs = all_daily()
    if not logs:
        return
    start = logs[0]["日期"]

    # 周复盘：从日志开始那一周起，每个已经结束的 ISO 周各一篇
    cur_week = R.week_label(today)
    wk = R.week_label(start)
    d = start
    done = set()
    while True:
        wk = R.week_label(d)
        if wk >= cur_week:
            break
        if wk not in done:
            done.add(wk)
            wp = os.path.join(J, "周", f"{wk}.json")
            if not os.path.exists(wp):
                write(wp, R.weekly_review(wk, S, logs, sd))
                print(f"周复盘 {wk} 已写入")
        d = R.shift(d, 7)
        if R.week_label(d) == wk:
            d = R.shift(d, 1)

    # 月复盘：从日志开始那个月起，每个已经结束的自然月各一篇
    cur_month = today[:7]
    m = start[:7]
    while m < cur_month:
        mp = os.path.join(J, "月", f"{m}.json")
        if not os.path.exists(mp):
            write(mp, R.monthly_review(m, S, logs, sd))
            print(f"月复盘 {m} 已写入")
        y, mm = map(int, m.split("-"))
        m = f"{y + (mm == 12)}-{mm % 12 + 1:02d}"


if __name__ == "__main__":
    main()
