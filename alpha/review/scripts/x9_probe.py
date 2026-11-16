#!/usr/bin/env python3
"""X9 read-only endpoint probe for GitHub Actions.
Prints HTTP status and the first 200 response characters for each URL.
"""
import urllib.request

URLS = {
    "okx_announcements": "https://www.okx.com/api/v5/support/announcements?annType=listing&locale=en-US&page=1&limit=2",
    "okx_1m_history": "https://www.okx.com/api/v5/market/history-candles?instId=BTC-USDT&bar=1m&limit=2",
    "bitget_announcements": "https://api.bitget.com/api/v2/public/annoucements?language=en_US&annType=coin_listings&limit=2",
    "bitget_1m_history": "https://api.bitget.com/api/v2/spot/market/history-candles?symbol=BTCUSDT&granularity=1min&limit=2",
    "bithumb_notices": "https://feed-api.bithumb.com/v1/notices?count=2",
    "kucoin_announcements": "https://api.kucoin.com/api/v3/announcements?currentPage=1&pageSize=2&annType=new-listings&lang=en_US",
    "htx_listing_page": "https://www.htx.com/en-us/support/list/360000039942/",
    "kraken_rss": "https://blog.kraken.com/feed/",
}

for name, url in URLS.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "uncleonchain-x9-probe/1.0"})
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read(200).decode("utf-8", "replace")
            print(f"{name}\t{response.status}\t{body}")
    except Exception as exc:
        print(f"{name}\tU\t{type(exc).__name__}: {exc}")
