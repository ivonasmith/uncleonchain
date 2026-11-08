"""美国国会对加密相关法案的二元表决：自动从 api.congress.gov（国会图书馆官方接口，要 CONGRESS_API_KEY）扫。

收两类（都有官方日期，结果二元）：
  1. 委员会表决会：参院 Business Meeting、众院 Markup / Meeting（不收 Hearing 听证），状态是已排期 / 改期；
     会议标题或关联法案标题出现加密关键词。官方给了钟点（UTC），time_utc 照写。
  2. 总统签署期限：加密相关法案「Presented to President」后 10 天（星期日不算）内必须签署或否决。
不收：院会表决（官方接口里没有提前排期，由每周人工核对补）。
"""
import os, re, time, datetime as dt

API = "https://api.congress.gov/v3"
# 只认核心词：「blockchain」「Clarity Act」之类会误中执法工具、部落管辖、助学金等无关法案（2026 年回测实测）
CRYPTO = re.compile(r"(?i)\b(crypto\w*|digital asset\w*|digital commodit\w*|stablecoin\w*|bitcoin|virtual currenc\w*|"
                    r"central bank digital currency|CBDC|tokeni[sz]\w*)\b")
VOTE_TYPES = re.compile(r"(?i)markup|business meeting|^meeting$")
CH_ZH = {"House": "众院", "Senate": "参院"}


class Client:
    def __init__(self, key):
        import requests
        self.s = requests.Session()
        self.s.headers.update({"X-Api-Key": key, "User-Agent": "uncleonchain.com calendar bot (bot@uncleonchain.com)"})
        self.calls = 0

    def get(self, url, **params):
        params.setdefault("format", "json")
        last = None
        for i in range(3):
            try:
                self.calls += 1
                r = self.s.get(url if url.startswith("http") else API + url, params=params, timeout=40)
                if r.status_code == 200:
                    return r.json()
                last = f"HTTP {r.status_code}"
                if r.status_code in (401, 403):
                    break
            except Exception as ex:
                last = type(ex).__name__
            time.sleep(2 * (i + 1))
        raise RuntimeError(f"congress.gov {url[:70]} {last}")

    def pages(self, path, key, max_pages=20, **params):
        out, url = [], path
        params = dict(params, limit=250)
        for _ in range(max_pages):
            js = self.get(url, **params)
            out += js.get(key) or []
            nxt = (js.get("pagination") or {}).get("next")
            if not nxt:
                break
            url, params = nxt, {}
        return out


def _name(c, code, chamber, cache):
    k = f"{chamber}/{code}"
    if k not in cache:
        try:
            cache[k] = c.get(f"/committee/{chamber.lower()}/{code}")["committee"].get("name") or code
        except Exception:
            cache[k] = code
    return cache[k]


def _bill(c, b, cache):
    k = f"{b['congress']}/{b['type'].lower()}/{b['number']}"
    if k not in cache:
        js = c.get(f"/bill/{k}")["bill"]
        cache[k] = dict(label=f"{b['type'].upper().replace('HR', 'H.R.').replace('S', 'S.', 1) if b['type'].upper() in ('HR', 'S') else b['type'].upper()} {b['number']}",
                        title=js.get("title") or "", url=f"https://www.congress.gov/bill/{b['congress']}th-congress/"
                        + {"hr": "house-bill", "s": "senate-bill", "hjres": "house-joint-resolution", "sjres": "senate-joint-resolution"}.get(b["type"].lower(), "bill") + f"/{b['number']}")
    return cache[k]


def _sign_deadline(presented):
    """宪法第一条第七款：10 天（星期日除外）"""
    d, n = presented, 0
    while n < 10:
        d += dt.timedelta(days=1)
        if d.weekday() != 6:
            n += 1
    return d


def congress_votes(today, horizon_days, key, congress=None):
    """返回 (events, info)。网络 / key 出错抛异常。"""
    c = Client(key)
    congress = congress or (119 + (today.year - 2025) // 2)
    lo, hi = today, today + dt.timedelta(days=horizon_days)
    names, bills = {}, {}
    events, seen_meet, skipped = [], 0, []
    # 1) 委员会表决会：会议一般提前一两周发布，取最近 45 天更新过的
    since = (dt.datetime.combine(today, dt.time()) - dt.timedelta(days=45)).strftime("%Y-%m-%dT00:00:00Z")
    for m in c.pages(f"/committee-meeting/{congress}", "committeeMeetings", fromDateTime=since,
                     toDateTime=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")):
        d = c.get(m["url"])["committeeMeeting"]
        seen_meet += 1
        try:
            when = dt.datetime.strptime(d["date"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        except Exception:
            continue
        if not (lo <= when.date() <= hi) or not VOTE_TYPES.search(d.get("type") or ""):
            continue
        if (d.get("meetingStatus") or "").lower() not in ("scheduled", "rescheduled"):
            continue
        rel = [_bill(c, b, bills) for b in ((d.get("relatedItems") or {}).get("bills") or [])]
        hit = [b for b in rel if CRYPTO.search(b["title"])]
        if not hit and not CRYPTO.search(d.get("title") or ""):
            continue
        cm = [_name(c, x["systemCode"], d["chamber"], names) for x in d.get("committees") or []]
        com = " / ".join(cm) or d["chamber"]
        lab = "、".join(b["label"] for b in hit) or (d.get("title") or "")[:80]
        lab_en = ", ".join(b["label"] for b in hit) or (d.get("title") or "")[:80]
        detail = "；".join(f"{b['label']}《{b['title'][:90]}》" for b in hit)
        events.append(dict(
            date=when.date().isoformat(), time_utc=when.strftime("%Y-%m-%d %H:%M"), auto="congress",
            title_zh=f"{CH_ZH.get(d['chamber'], d['chamber'])}{com}开会表决：{lab}",
            title_en=f"{d['chamber']} {com} votes: {lab_en}",
            what_zh=f"委员会表决会（{d.get('type')}），议程含加密相关法案：{detail or d.get('title', '')[:160]}。表决结果是二元的（通过 / 不通过送院会）。会议可能改期或取消，以官方页面为准。没做过历史波动检验，没有统计数字。",
            what_en=f"Committee {d.get('type')} with crypto-related items: {', '.join(b['label'] for b in hit) or d.get('title', '')[:120]}. Binary outcome (reported or not). May be rescheduled. Not tested against BTC prices.",
            source_url=f"https://www.congress.gov/event/{congress}th-congress/{d['chamber'].lower()}-event/{d['eventId']}"))
    # 2) 总统签署期限：最近 20 天更新过、最新动作是「Presented to President」的加密法案
    since_b = (dt.datetime.combine(today, dt.time()) - dt.timedelta(days=20)).strftime("%Y-%m-%dT00:00:00Z")
    signed = 0
    for b in c.pages(f"/bill/{congress}", "bills", max_pages=30, fromDateTime=since_b, sort="updateDate+desc"):
        la = b.get("latestAction") or {}
        if "presented to president" not in (la.get("text") or "").lower() or not CRYPTO.search(b.get("title") or ""):
            continue
        try:
            pres = dt.date.fromisoformat(la["actionDate"])
        except Exception:
            continue
        dl = _sign_deadline(pres)
        if not (lo <= dl <= hi):
            continue
        signed += 1
        info = _bill(c, dict(congress=b["congress"], type=b["type"], number=b["number"]), bills)
        events.append(dict(
            date=dl.isoformat(), auto="congress",
            title_zh=f"总统签署 / 否决期限：{info['label']}", title_en=f"Presidential sign/veto deadline: {info['label']}",
            what_zh=f"{info['label']}《{info['title'][:120]}》{pres.isoformat()} 呈送总统，按宪法 10 天（星期日除外）内签署或否决，随时可能提前签。没做过历史波动检验。",
            what_en=f"{info['label']} presented to the President on {pres.isoformat()}; 10 days (Sundays excepted) to sign or veto. May be signed earlier. Not tested against BTC prices.",
            source_url=info["url"]))
    events.sort(key=lambda e: (e["date"], e.get("time_utc", "")))
    return events, dict(meetings=seen_meet, events=len(events), sign_deadlines=signed, calls=c.calls, skipped=skipped)


if __name__ == "__main__":
    import json, sys
    t = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.datetime.now(dt.timezone.utc).date()
    ev, info = congress_votes(t, 60, os.environ.get("CONGRESS_API_KEY", "proxy-injected"))
    print(json.dumps(dict(info=info, events=ev), ensure_ascii=False, indent=1))
