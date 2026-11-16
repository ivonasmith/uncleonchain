import urllib.request, json, sys
C = {
 "OKX": "https://www.okx.com/api/v5/support/announcements?annType=announcements-new-listings&page=1",
 "Bybit": "https://api.bybit.com/v5/announcements/index?locale=en-US&type=new_crypto&limit=20",
 "Bitget": "https://api.bitget.com/api/v2/public/annoucements?annType=coin_listings&language=en_US",
 "Upbit": "https://api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=20&category=trade",
 "Bithumb": "https://feed.bithumb.com/notice?category=9&page=1",
 "Gate": "https://www.gate.com/announcements/newlisted",
 "Gate-api": "https://www.gate.com/api/web/v1/announcement/list?cate_id=newlisted&page=1&limit=20",
 "MEXC": "https://www.mexc.com/help/announce/api/en-US/section/15425930840734/articles?page=1&perPage=20",
 "Kraken": "https://blog.kraken.com/category/product/asset-listings/feed",
 "Coinbase": "https://www.coinbase.com/blog/landing/product",
 "KuCoin": "https://api.kucoin.com/api/v3/announcements?annType=new-listings&lang=en_US&pageSize=20",
 "HTX": "https://www.htx.com/-/x/support/public/getList/v2?page=1&limit=20&oneLevelId=360000031902&twoLevelId=360000039942&language=en-us",
}
for n, u in C.items():
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/html,*/*", "Accept-Language": "en-US"}), timeout=25)
        b = r.read()
        print(f"{n}: HTTP {r.status} · {len(b)} bytes · {r.headers.get('Content-Type','')[:30]} · {b[:(2200 if n in ('OKX','Bitget','KuCoin','HTX') else 260)].decode('utf-8','ignore')!r}")
    except Exception as e:
        body = ""
        try: body = e.read(160).decode("utf-8", "ignore")
        except Exception: pass
        print(f"{n}: 失败 {e} {body!r}")

import re
try:
    b = urllib.request.urlopen(urllib.request.Request(C["Kraken"], headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read().decode("utf-8", "ignore")
    for it in re.findall(r"<item>(.*?)</item>", b, re.S)[:3]:
        print("Kraken item:", re.sub(r"\s+", " ", re.sub(r"<content:encoded>.*?</content:encoded>|<description>.*?</description>", "", it, flags=re.S))[:500])
except Exception as e:
    print("Kraken item 失败", e)
for n, u in {"OKX-detail-kline": "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1m&limit=1", "Bitget-kline": "https://api.bitget.com/api/v2/spot/market/candles?symbol=BTCUSDT&granularity=1min&limit=1",
             "Bitget-p2": "https://api.bitget.com/api/v2/public/annoucements?annType=coin_listings&language=en_US&limit=5", "OKX-p2": "https://www.okx.com/api/v5/support/announcements?annType=announcements-new-listings&page=2"}.items():
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=25); b = r.read()
        print(f"{n}: HTTP {r.status} · {b[:400].decode('utf-8','ignore')!r}")
    except Exception as e:
        print(f"{n}: 失败 {e}")
