#!/usr/bin/env python3
"""机制拆解卡（TAO、WLD）取数探测：只打印，不写仓库。在 Actions 里跑（要 TAOSTATS_KEY / COINALYZE_KEY / ETHERSCAN_KEY）。"""
import json, os, time, urllib.parse, urllib.request

def get(url, headers=None):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "uncleonchain-mech/1.0", **(headers or {})})
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:  # noqa
        return -1, str(e)

def show(tag, url, headers=None, n=900):
    st, body = get(url, headers)
    print(f"\n=== {tag} [{st}] {url.split('?')[0]}\n{body[:n]}")
    return st, body

TS = os.environ.get("TAOSTATS_KEY", "").strip()
CZ = os.environ.get("COINALYZE_KEY", "").strip()
ES = os.environ.get("ETHERSCAN_KEY", "").strip()
print("keys:", {"taostats": bool(TS), "coinalyze": bool(CZ), "etherscan": bool(ES)})

# ---- taostats（路径不确定，逐个试）
h = {"Authorization": TS, "accept": "application/json"}
for path in ["/api/stats/latest/v1", "/api/price/latest/v1?asset=tao", "/api/subnet/latest/v1?limit=3",
             "/api/dtao/pool/latest/v1?limit=3", "/api/account/latest/v1?limit=10&order=balance_total_desc",
             "/api/block/v1?limit=1"]:
    show("taostats", "https://api.taostats.io" + path, h)
    time.sleep(1.2)

# ---- Coinalyze：找 TAO / WLD 的币安永续代码，再取持仓与资金费率
st, body = get("https://api.coinalyze.net/v1/future-markets", {"api_key": CZ})
syms = []
try:
    for m in json.loads(body):
        if m.get("base_asset") in ("TAO", "WLD") and m.get("is_perpetual") and m.get("exchange") == "A" and m.get("quote_asset") == "USDT":
            syms.append(m["symbol"])
except Exception as e:  # noqa
    print("future-markets 解析失败", st, body[:300])
print("\ncoinalyze 永续：", syms)
t1 = int(time.time()); t0 = t1 - 10 * 86400
for ep, extra in (("open-interest-history", "&convert_to_usd=true"), ("funding-rate-history", "")):
    if syms:
        show("coinalyze " + ep, f"https://api.coinalyze.net/v1/{ep}?symbols={','.join(syms)}&interval=daily&from={t0}&to={t1}{extra}", {"api_key": CZ}, 1200)
        time.sleep(1.6)

# ---- Etherscan V2：WLD 官方地址余额（以太坊 1 / Optimism 10 / World Chain 480）
WLD = {1: "0x163f8C2467924be0ae7B5347228CABF260318753", 10: "0xdC6fF44d5d932Cbd77B52E5612Ba0529DC6226F1", 480: "0x2cFc85d8E48F8EAB294be644d9E25C3030863003"}
WALLETS = {"基金会冷钱包": "0xc534a745bFfaF9466Ed7B47fA23B0177b99A3e77", "World Assets": "0x59a0f98345f54bAB245A043488ECE7FCecD7B596",
           "TFH 历史解锁①": "0x0D4CA2FF883D429cE4372Eeb056EFAFab181CcE7", "TFH 历史解锁②": "0xFB7F100ED6793FCD63E6E9F201bE9Aa567B2C9cC",
           "社区解锁①": "0x1770bd8186AAd27Df9B050D65f86CF2cdC92C296"}
for cid, tok in WLD.items():
    q = urllib.parse.urlencode({"chainid": cid, "module": "stats", "action": "tokensupply", "contractaddress": tok, "apikey": ES})
    show(f"etherscan supply chain {cid}", "https://api.etherscan.io/v2/api?" + q, n=300)
    time.sleep(0.3)
    for nm, a in WALLETS.items():
        q = urllib.parse.urlencode({"chainid": cid, "module": "account", "action": "tokenbalance", "contractaddress": tok, "address": a, "tag": "latest", "apikey": ES})
        st, body = get("https://api.etherscan.io/v2/api?" + q)
        print(f"etherscan chain {cid} {nm}: [{st}] {body[:160]}")
        time.sleep(0.3)
