#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OKX 上币公告正文解析：开盘时间 + 交易对。纯函数，不联网，可单测（python3 alpha/okx_parse.py）。

OKX 公告的 pTime 是发布时间，不是开盘时间（GRVT：pTime 03:00 UTC，正文开盘 15:00 UTC），开盘时间只能从正文取。
正文有三种写法（2026-11-16 在 Actions 上取样）：
  ① 全球站 USDT：「CARDS /USDT spot trading will open at Jun 25, 2026 12:00 UTC」（先交易对，后「月 日, 年 时:分 UTC」）
  ② 全球站 USDT：「RE/USDT spot trading will open at 14:00 UTC on June 18, 2026」（时间在前，月份全拼）
  ③ OKX US 的 USD 对：「… in our spot trading at Jul 30, 2026 15:00 UTC: GRVT/USD」（先时间，后交易对）
USD 报价的是 OKX US 的交易对，全球站公开 K 线接口里没有，窗口不算（venue = okx_us）。
"""
import datetime as dt, re

PAIR = r"([A-Z0-9]{1,15}) ?/ ?(USDT|USDC|USD|EUR|BTC)\b"
MON = r"([A-Z][a-z]{2,8}) (\d{1,2}), (\d{4})"


def _ms(mon, day, year, hm):
    fmt = "%b %d %Y %H:%M" if len(mon) <= 3 else "%B %d %Y %H:%M"
    return int(dt.datetime.strptime(f"{mon} {day} {year} {hm}", fmt).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def parse_open(txt):
    """→ [(base, quote, open_ms, venue)]，venue = okx | okx_us；同一交易对只留第一次出现。"""
    out, seen = [], set()

    def add(b, q, t):
        if (b, q) not in seen:
            seen.add((b, q))
            out.append((b, q, t, "okx_us" if q == "USD" else "okx"))

    # ① 交易对 + spot trading will open at 月 日, 年 时:分 UTC
    for m in re.finditer(PAIR + r" (?:spot )?trading (?:will )?open(?:s)? at " + MON + r" (\d{1,2}:\d{2}) ?UTC", txt):
        add(m.group(1), m.group(2), _ms(m.group(3), m.group(4), m.group(5), m.group(6)))
    # ② 时:分 UTC on 月 日, 年
    for m in re.finditer(PAIR + r" (?:spot )?trading (?:will )?open(?:s)? at (\d{1,2}:\d{2}) UTC on " + MON, txt):
        add(m.group(1), m.group(2), _ms(m.group(4), m.group(5), m.group(6), m.group(3)))
    # ③ in our spot trading at 月 日, 年 时:分 UTC : 交易对[, 交易对…]
    m = re.search(r"in our spot trading at " + MON + r" (\d{1,2}:\d{2}) ?UTC ?:? ?((?:" + PAIR + r"[, ]*)+)", txt)
    if m:
        t = _ms(m.group(1), m.group(2), m.group(3), m.group(4))
        for b, q in re.findall(PAIR, m.group(5)):
            add(b, q, t)
    return out


def _selftest():
    iso = lambda t: dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    cases = [
        ("is introducing the following USD trading pairs in our spot trading at Jul 30, 2026 15:00 UTC: GRVT/USD OKX team", [("GRVT", "USD", "2026-07-30 15:00", "okx_us")]),
        ("in our spot trading at Jul 27, 2026 12:00 UTC : AEON /USD OKX team", [("AEON", "USD", "2026-07-27 12:00", "okx_us")]),
        ("CARDS deposits will open at Jun 25, 2026 02:00 UTC . CARDS /USDT pre-open will take place from from 11:00 to 12:00 UTC on Jun 25, 2026 . CARDS /USDT spot trading will open at Jun 25, 2026 12:00 UTC . CARDS withdrawals", [("CARDS", "USDT", "2026-06-25 12:00", "okx")]),
        ("RE deposits will open at 02:00 UTC on June 18, 2026. RE/USDT spot trading will open at 14:00 UTC on June 18, 2026. RE premarket", [("RE", "USDT", "2026-06-18 14:00", "okx")]),
        ("GRAM/USDT spot trading will open at 10:00 UTC on June 17, 2026. Margin GRAM/USDT margin trading enabled at 11:00 UTC", [("GRAM", "USDT", "2026-06-17 10:00", "okx")]),
        ("OKX to support VELODROME crypto migration ... delisted between 3:00 and 4:00 UTC on October 30, 2026", []),
    ]
    bad = 0
    for txt, want in cases:
        got = [(b, q, iso(t), v) for b, q, t, v in parse_open(txt)]
        ok = got == want
        bad += not ok
        print("OK " if ok else "BAD", got if ok else (got, "应为", want))
    return bad


if __name__ == "__main__":
    raise SystemExit(_selftest())
