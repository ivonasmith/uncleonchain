"""SEC 对加密产品的最终批准 / 否决期限：自动从 Federal Register 官方接口扫出来（免费、不用 key）。

只收「最终」期限：SEC 在 Federal Register 上发的延期通知里写明
  "designates <日期> as the date by which the Commission shall either approve or disapprove the proposed rule change"
且后面**没有** "or institute proceedings"（那种到期还能再拖，不是二元结果，不收）。
排除：之后已经出了批准 / 否决令、或交易所撤回（Federal Register 上的撤回 / 批准文件，或 SEC 文件页标 WITHDRAWN）。
相关性：通知全文里出现加密关键词（bitcoin / ether / crypto / digital asset / solana …）。
输出给 cal_daily.reg_events 合并，type=REG。抓不到时用上次成功结果并在 data_status 里标 stale。
"""
import os, re, json, time, datetime as dt

FR_API = "https://www.federalregister.gov/api/v1/documents.json"
UA = {"User-Agent": "uncleonchain.com calendar bot (bot@uncleonchain.com)"}   # SEC 公平访问要求写明身份
CRYPTO = re.compile(r"(?i)\b(bitcoin|ether(eum)?|crypto(currency|currencies)?|crypto[- ]asset|digital (asset|commodit)\w*|solana|sol\b|xrp|staking|"
                    r"dogecoin|litecoin|avalanche|cardano|polkadot|hedera|hbar|chainlink|sui|tron|jito\w*)\b")
DEADLINE = re.compile(r"designates\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4}),?\s+as\s+the\s+date\s+by\s+which\s+the\s+Commission\s+(?:shall|should|will)\s+"
                      r"(?:either\s+)?approve\s+or\s+disapprove(,?\s+or\s+institute\s+proceedings)?", re.S)
FILE_NO = re.compile(r"File\s+No\.?\s+(SR-[A-Za-z]+-\d{4}-\d+)")
RESOLVED_TITLE = re.compile(r"(?i)order (granting|approving|disapproving)|withdrawal|notice of withdrawal")


def _get(url, params=None, tries=3):
    import requests
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=40)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except Exception as ex:
            last = type(ex).__name__
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url[:60]} {last}")


def _search(term, since, until=None, per_page=100, max_pages=10):
    out = []
    for page in range(1, max_pages + 1):
        params = [("conditions[agencies][]", "securities-and-exchange-commission"), ("conditions[term]", term),
                  ("conditions[publication_date][gte]", since), ("per_page", per_page), ("order", "newest"), ("page", page)]
        if until:
            params.append(("conditions[publication_date][lte]", until))
        params += [("fields[]", f) for f in ("title", "publication_date", "document_number", "html_url")]
        js = _get(FR_API, params=params).json()
        out += js.get("results") or []
        if not js.get("next_page_url"):
            break
    return out


def _text(doc, cache_dir):
    """全文（缓存：Federal Register 文件发出后不变）"""
    p = os.path.join(cache_dir, f"{doc['document_number']}.txt")
    if os.path.exists(p):
        return open(p, encoding="utf-8").read()
    # 全文取 govinfo（政府出版局，同一份 Federal Register 文件）；federalregister.gov 的全文链接会把程序访问转到人机验证页
    import html as _h
    raw = _get(f"https://www.govinfo.gov/content/pkg/FR-{doc['publication_date']}/html/{doc['document_number']}.htm").text
    t = _h.unescape(re.sub(r"<[^>]+>", " ", raw))
    os.makedirs(cache_dir, exist_ok=True)
    open(p, "w", encoding="utf-8").write(t)
    return t


def _product(title):
    """从标题里取产品名：'... To List and Trade Shares of the VanEck JitoSOL ETF Under Nasdaq Rule ...' → 'VanEck JitoSOL ETF'"""
    m = re.search(r"(?i)list and trade (?:(?:the )?shares of )?(?:the )?(.+?)(?:,? (?:under|pursuant to|on the exchange) |$)", title)
    if m:
        return m.group(1).strip(" .")[:120]
    m = re.search(r"(?i)proposed rule change(?:,? as modified by [^,]+,?)? (?:to )?(.+)$", title)
    return (m.group(1) if m else title).strip(" .")[:120]


def sec_deadlines(today, horizon_days, cache_dir, live=True):
    """返回 (events, info)。events：窗口内仍悬而未决的最终期限；info：扫描摘要（给 data_status）。网络失败抛异常。
    live=False 回测用：只用 today 当天及以前的 Federal Register 文件，不看 SEC 文件页（那是今天的状态）。"""
    since = (today - dt.timedelta(days=300)).isoformat()
    docs = {d["document_number"]: d for d in _search('"Longer Period" "approve or disapprove"', since, today.isoformat())}
    txt_dir = os.path.join(cache_dir, "fr_text")
    found, skipped = [], []
    for d in sorted(docs.values(), key=lambda x: x["publication_date"]):
        if "longer period" not in d["title"].lower():   # 只有延期通知会写最终期限，其他文件不下载全文
            continue
        t = re.sub(r"\s+", " ", _text(d, txt_dir))
        m, fn = DEADLINE.search(t), FILE_NO.search(t)
        if not m or not fn or not CRYPTO.search(t):
            continue
        try:
            date = dt.datetime.strptime(m.group(1).replace("  ", " "), "%B %d, %Y").date()
        except ValueError:
            continue
        rec = dict(file_no=fn.group(1).upper(), date=date, final=not m.group(2), doc=d, product=_product(d["title"]))
        if not (today <= date <= today + dt.timedelta(days=horizon_days)):
            continue
        if not rec["final"]:
            skipped.append(f"{rec['file_no']} {date}（可再启动审议程序，不是最终期限）")
            continue
        found.append(rec)
    # 同一文件号只留最新一份通知
    latest = {}
    for r in found:
        if r["file_no"] not in latest or r["doc"]["publication_date"] > latest[r["file_no"]]["doc"]["publication_date"]:
            latest[r["file_no"]] = r
    events = []
    for fno, r in latest.items():
        # 之后有没有批准 / 否决 / 撤回
        later = [x for x in _search(f'"{fno}"', r["doc"]["publication_date"], today.isoformat())
                 if x["document_number"] != r["doc"]["document_number"] and RESOLVED_TITLE.search(x["title"])]
        # 别的文件也会引用这个文件号：只认文件头里自己的 File No. 就是它的
        hit = next((x for x in later if (FILE_NO.search(re.sub(r"\s+", " ", _text(x, txt_dir))[:3000]) or [None, ""])[1].upper() == fno), None)
        if hit:
            skipped.append(f"{fno}（{hit['publication_date']} 已出结果 / 撤回）"); continue
        if not live:
            events.append(_event(r)); continue
        try:
            page = _get(f"https://www.sec.gov/rules-regulations/self-regulatory-organization-rulemaking/{fno.lower()}").text
            if re.search(r"WITHDRAWN on \d", page):
                skipped.append(f"{fno}（SEC 页面标 WITHDRAWN）"); continue
            if re.search(r"(?i)Order (Granting|Approving|Disapproving)", page):
                skipped.append(f"{fno}（SEC 页面已有批准 / 否决令）"); continue
        except Exception:
            pass   # SEC 页面取不到不影响：Federal Register 已查过
        events.append(_event(r))
    info = dict(scanned=len(docs), deadlines=len(events), skipped=skipped)
    return events, info


def _event(r):
    p, fno = r["product"], r["file_no"]
    return dict(
            date=r["date"].isoformat(), auto="sec",
            title_zh=f"SEC 对 {p} 的最终批准 / 否决期限", title_en=f"SEC final approve/disapprove deadline: {p}",
            what_zh=f"SEC 依法必须在这天前对 {fno} 作出批准或否决（不能再延期），可能提前公布；只给到日期，没有钟点。没做过历史波动检验，没有统计数字。",
            what_en=f"Statutory final date for the SEC to approve or disapprove {fno} (no further extension); a decision can come earlier. Date only. Not tested against BTC prices.",
            source_url=r["doc"]["html_url"], file_no=fno)


if __name__ == "__main__":
    ev, info = sec_deadlines(dt.datetime.now(dt.timezone.utc).date(), 60, os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache"))
    print(json.dumps(dict(events=ev, info=info), ensure_ascii=False, indent=1))
