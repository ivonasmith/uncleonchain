#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性探测：不用 Etherscan key，能不能查到 BSC 等链上合约的名字 / 公开标签。只读。
来源：Sourcify v2（开源验证库）、BscScan / Basescan 网页上的公开标签与合约名、链上 name()。"""
import json, os, re, urllib.request

ADDRS = {"bsc": ["0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0", "0x641c1c78c256d4aa6d7e73c5fc0cddef035c6666",
                 "0x5c952063c7fc8610ffdb798152d69f0b9550762b", "0x37dc44b63a0a31058a72ab0b5e53e20a1716395e",
                 "0x2bebed4be8c8f46c17776c71d7a6a45dbc5cab29"],
         "robinhood": ["0x1cbaf24d53fe930fce8eff149fa797d2611da149", "0x641c1c78c256d4aa6d7e73c5fc0cddef035c6666"]}
CHAIN_ID = {"bsc": 56, "robinhood": 4663, "base": 8453}
SCAN = {"bsc": "https://bscscan.com", "base": "https://basescan.org"}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36", "Accept": "text/html,application/json"}


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)[:80]


for chain, addrs in ADDRS.items():
    for a in addrs:
        out = {}
        st, body = get(f"https://sourcify.dev/server/v2/contract/{CHAIN_ID[chain]}/{a}?fields=compilation")
        if st == 200:
            try:
                out["sourcify"] = (json.loads(body).get("compilation") or {}).get("name")
            except Exception:
                out["sourcify"] = "解析失败"
        else:
            out["sourcify"] = f"HTTP {st}"
        if chain in SCAN:
            st, body = get(f"{SCAN[chain]}/address/{a}")
            tag = re.search(r'(?:Public Name Tag|data-bs-title="Public Name Tag")[^<]*</[^>]+>\s*<[^>]+>\s*([^<]{2,80})<', body)
            title = re.search(r"<title>\s*([^<]{0,160})</title>", body)
            cname = re.search(r"Contract Name:?\s*</[^>]+>\s*<[^>]+>\s*([^<]{2,80})<", body)
            out["scan"] = {"HTTP": st, "标题": (title.group(1).strip() if title else None), "公开标签": tag and tag.group(1).strip(),
                           "合约名": cname and cname.group(1).strip(), "疑似拦截": ("cloudflare" in body.lower() or "just a moment" in body.lower())}
        print(chain, a, json.dumps(out, ensure_ascii=False))
