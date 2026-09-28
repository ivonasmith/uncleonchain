#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发射台日更 · 公共函数
所有脚本共用：路径、带 UA 与退避的 HTTP、UTC 日期工具、JSON 读写、网络预检。
"""
import json, os, time, datetime as dt, urllib.request, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))           # 脚本所在目录
# 台账目录与产出目录可用环境变量改（GitHub 仓库里是 data/ 与 build/）；不设时与旧版一致：台账放脚本旁边，产出放 输出/
DATA = os.path.abspath(os.environ.get("LP_DATA") or BASE)
OUT = os.path.abspath(os.environ.get("LP_OUT") or os.path.join(BASE, "输出"))
os.makedirs(DATA, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (launchpad-daily)", "Accept": "application/json"}
CG_KEY = os.environ.get("COINGECKO_API_KEY")   # 可选：CoinGecko 免费 Demo key，共享 IP（如 GitHub Actions）上防 429

# 本工作流用到的全部外部域名（云端沙盒需要在网络白名单里放行）
HOSTS = {
    "api.llama.fi": "https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true",
    "api.coingecko.com": "https://api.coingecko.com/api/v3/ping",
    "api.geckoterminal.com": "https://api.geckoterminal.com/api/v2/networks?page=1",
    "api.dexscreener.com": "https://api.dexscreener.com/latest/dex/tokens/0x39dBED3a2bd333467115dE45665cC57F813C4571",
    "rpc.mainnet.chain.robinhood.com": None,   # JSON-RPC，单独用 POST 测
}


def get(url, timeout=60, tries=4, headers=None):
    """GET JSON。429 / 5xx / 网络抖动递增退避；400/404 直接抛（别重试坏 slug）。"""
    h = dict(UA)
    if CG_KEY and "api.coingecko.com" in url:
        h["x-cg-demo-api-key"] = CG_KEY
    if headers:
        h.update(headers)
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 404):
                raise
            time.sleep(2 * (i + 1) if e.code != 429 else 6 * (i + 1))
        except Exception as e:  # noqa
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def post_json(url, body, timeout=90, tries=5):
    data = json.dumps(body).encode()
    h = {"Content-Type": "application/json", "User-Agent": UA["User-Agent"]}   # 不带 UA 会 403
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=timeout) as r:
                return json.load(r)
        except Exception as e:  # RPC 会抛 HTTP 429（urllib 异常，不是 JSON error）
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def day(ts):
    """unix 秒 → YYYY-MM-DD（UTC）"""
    return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%d")


def today_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def shift(d, n):
    return (dt.date.fromisoformat(d) + dt.timedelta(days=n)).isoformat()


def day_start_ts(d):
    return int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp())


def load(name, default=None):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(name, obj, indent=None):
    p = os.path.join(DATA, name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
    os.replace(tmp, p)
    return p


def preflight(verbose=True):
    """逐个域名测一次连通。返回被拦截的域名列表。"""
    blocked = []
    for host, url in HOSTS.items():
        try:
            if url:
                urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read(64)
            else:
                post_json("https://rpc.mainnet.chain.robinhood.com",
                          {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []},
                          timeout=20, tries=2)
            ok = True
        except urllib.error.HTTPError as e:
            ok = e.code not in (403, 407)      # 403/407 基本是出口策略拦截
        except Exception:
            ok = False
        if not ok:
            blocked.append(host)
        if verbose:
            print(f"  {'OK ' if ok else '拦截'}  {host}")
    return blocked


if __name__ == "__main__":
    b = preflight()
    print("被拦截：", b or "无")
