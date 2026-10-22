"""发射台活动温度 · 周期全览（每日更新）。

数据：研究快照 content/cycle/snapshot.json（2021-09 起，截至 2026-10-17，sha256 见 manifest）+ 之后每天接
发射台矩阵（data/发射台矩阵.json「历史」，DefiLlama Launchpad 类目逐日手续费合计；接缝处两源逐日差 <3%）。
热潮识别规则与研究侧一致（7 日平均、前 28 天中位数为常态、1.5 倍连续 3 天开始、1.2 倍以内或峰值 6 成以下连续 7 天结束、
峰值 8 成以上为最热区间），2026-10-22 用本文件重算快照区间，27 轮全部字段逐一对上。
"""
import datetime as dt
import hashlib
import json
import statistics
from pathlib import Path
from 周期仪表盘 import dashboard

RULES = {'smooth': 7, 'baseline_days': 28, 'trigger': 1.5, 'entry_confirm': 3, 'return_to': 1.2, 'drawdown_to': 0.6, 'exit_confirm': 7, 'plateau': 0.8}


def quantile(values, p):
    v = sorted(values)
    if not v:
        return None
    h = (len(v) - 1) * p
    i = int(h)
    return v[i] + (v[min(i + 1, len(v) - 1)] - v[i]) * (h - i)


def reading(points):
    by = {p[0]: p[2] for p in points}
    day = points[-1][0]
    date = dt.date.fromisoformat(day)
    def previous(n):
        return by.get((date - dt.timedelta(days=n)).isoformat())
    value = by[day]
    history = [previous(n) for n in range(1, 731)]
    history = [v for v in history if v is not None]
    lo, hi = (quantile(history, .05), quantile(history, .95)) if len(history) >= 365 else (None, None)
    score = 100 * (value - lo) / (hi - lo) if value is not None and lo is not None and hi > lo else None
    old = previous(7)
    delta = value / old - 1 if value is not None and old is not None and old > 0 else None
    recent = [previous(n) for n in range(1, 29)]
    base = quantile(recent, .5) if all(v is not None for v in recent) else None
    pulse = value / base if value is not None and base is not None and base > 0 else None
    return dict(date=day,value=value,low=lo,high=hi,position=score,direction_change=delta,pulse=pulse,reference_days=len(history))


def detect_events(points):
    """热潮识别。常态 = 当天之前 28 个 7 日平均的中位数（固定在启动那天）。"""
    D = lambda x: dt.date.fromisoformat(x)
    dates = [p[0] for p in points]; m = [p[2] for p in points]; n = len(m); R = RULES
    def base_at(i):
        w = [x for x in m[max(0, i - R['baseline_days']):i] if x is not None]
        return statistics.median(w) if len(w) >= R['baseline_days'] else None
    out = []; i = 0
    while i < n:
        b = base_at(i)
        if b is None or not b > 0 or i + R['entry_confirm'] - 1 >= n or not all(m[j] is not None and m[j] >= R['trigger'] * b for j in range(i, i + R['entry_confirm'])):
            i += 1
            continue
        start = i; peak = i; pv = m[i]; cnt = 0; endi = None; reason = None; j = i + 1
        while j < n:
            if m[j] is not None and m[j] > pv:
                pv = m[j]; peak = j
            c1 = m[j] is not None and m[j] <= R['return_to'] * b
            c2 = m[j] is not None and m[j] <= R['drawdown_to'] * pv
            cnt = cnt + 1 if (c1 or c2) else 0
            if cnt == R['exit_confirm']:
                endi = j; reason = 'baseline_return' if c1 else 'sustained_drawdown'
                break
            j += 1
        last = endi if endi is not None else n - 1
        lo = peak
        while lo - 1 >= start and m[lo - 1] is not None and m[lo - 1] >= R['plateau'] * pv:
            lo -= 1
        hi = peak
        while hi + 1 <= last and m[hi + 1] is not None and m[hi + 1] >= R['plateau'] * pv:
            hi += 1
        out.append({'id': len(out) + 1, 'start': dates[start], 'confirmed': dates[start + R['entry_confirm'] - 1], 'peak': dates[peak], 'end': dates[last],
                    'status': 'ended' if endi is not None else 'ongoing', 'reason': reason, 'baseline': b, 'peak_value': pv, 'multiple': pv / b,
                    'rise_days': (D(dates[peak]) - D(dates[start])).days, 'plateau_start': dates[lo], 'plateau_end': dates[hi], 'plateau_days': hi - lo + 1,
                    'fall_days': (D(dates[last]) - D(dates[peak])).days if endi is not None else None, 'days': (D(dates[last]) - D(dates[start])).days + 1, 'series': 'fees'})
        if endi is None:
            break
        i = endi + 1
    return out


_LIVE = {}


def live_data(root, matrix):
    """快照 + 矩阵日更拼成每日序列，重算热潮。"""
    key = (str(root), (matrix or {}).get('日期'))
    if key in _LIVE:
        return _LIVE[key]
    src = Path(root) / 'content/cycle/snapshot.json'
    snap = json.loads(src.read_text())
    manifest = json.loads((src.parent / 'manifest.json').read_text())
    assert hashlib.sha256(src.read_bytes()).hexdigest() == manifest['sha256'], 'Cycle snapshot hash mismatch'
    s = dict(snap['series']['fees'])
    pts = [list(p) for p in s['points']]
    cut = snap['cutoff']
    n0 = len(pts)
    hist = (matrix or {}).get('历史') or {}
    tail = sorted(d for d in hist if d > cut)
    if tail:
        day = dt.date.fromisoformat(cut)
        end = dt.date.fromisoformat(tail[-1])
        while day < end:
            day += dt.timedelta(days=1)
            v = hist.get(day.isoformat())
            pts.append([day.isoformat(), float(sum(v.values())) if v else None, None, len(v) if v else 0])
        raws = [p[1] for p in pts]
        for i in range(n0, len(pts)):
            w = raws[i - 6:i + 1]
            pts[i][2] = sum(w) / 7 if len(w) == 7 and all(x is not None for x in w) else None
    s['points'] = pts
    s['last'] = pts[-1][0]
    s['valid_days'] = sum(1 for p in pts if p[1] is not None)
    s['missing_days'] = sum(1 for p in pts if p[1] is None)
    s['events'] = detect_events(pts)
    keep = [e for e in s['events'] if e['end'] <= cut and e['status'] == 'ended']
    ref = snap['series']['fees']['events']
    s['events_match_snapshot'] = [(e['start'], e['end']) for e in keep] == [(e['start'], e['end']) for e in ref]
    if not s['events_match_snapshot']:
        print('⚠️ 周期：重算的历史热潮和研究快照对不上，检查规则')
    data = {'schema': snap['schema'], 'cutoff': s['last'], 'snapshot_cutoff': cut, 'primary_rules': RULES, 'mode': 'daily', 'series': {'fees': s}}
    _LIVE.clear()
    _LIVE[key] = (data, manifest, src)
    return _LIVE[key]


def build(g):
    T, esc = g['T'], g['esc']
    data, manifest, src = g['G']['CYC_DATA']
    out = Path(g['SITE']) / 'data/cycle'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'snapshot.json').write_bytes(src.read_bytes())
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    s = data['series']['fees']
    (out / 'live.json').write_text(json.dumps({'cutoff': data['cutoff'], 'snapshot_cutoff': data['snapshot_cutoff'], 'rules': data['primary_rules'],
                                                'points': s['points'], 'events': s['events']}, ensure_ascii=False))
    r = reading(s['points'])
    (out / 'readings.json').write_text(json.dumps({'fees': r}, ensure_ascii=False, indent=2))

    points = s['points']
    srcj = g['write_data']('cycle/fees.json', [p[0] for p in points], {'raw': {p[0]: p[1] for p in points}, 'mean': {p[0]: p[2] for p in points}})
    chart = g['chart_div']({'src': srcj, 'fmt': 'usd', 'ranges': ['3M', '1Y', 'ALL'], 'range': '1Y',
                            'series': [{'k': 'raw', 'n': T('每天', 'Daily'), 'c': 's2'}, {'k': 'mean', 'n': T('7 日平均', '7d average'), 'c': 's1'}],
                            'note': T(f'{data["snapshot_cutoff"]} 及以前来自研究快照，之后接矩阵页每天拉的同一类目合计（接缝处两源逐日差 3% 以内）。缺数据的日子留空，不补零。',
                                      f'Research snapshot through {data["snapshot_cutoff"]}, then the same category total pulled daily for the matrix page (sources differ <3% at the seam). Missing days stay blank.')})
    start = dt.date.fromisoformat(s['first']); end = dt.date.fromisoformat(s['last']); total = max(1, (end - start).days)
    strips = []
    for e in s['events']:
        left = 100 * (dt.date.fromisoformat(e['start']) - start).days / total
        width = 100 * ((dt.date.fromisoformat(e['end']) - dt.date.fromisoformat(e['start'])).days + 1) / total
        title = esc(f'{e["start"]} → {e["end"]} · {e["days"]} ' + T('天', 'days'))
        strips.append(f'<span title="{title}" style="position:absolute;left:{left:.4f}%;width:{max(.3, min(width, 100 - left)):.4f}%;height:18px;background:var(--cyc-summer);opacity:{1 if e["status"] == "ended" else .45}"></span>')
    st_txt = lambda e: T('已结束', 'Ended') if e['status'] == 'ended' else T('进行中', 'Ongoing')
    rows = ''.join(f'<tr><td>{e["start"]}</td><td>{e["peak"]}</td><td>{e["end"] if e["status"] == "ended" else "—"}</td><td>{e["days"]}</td><td>{e["multiple"]:.1f}×</td><td>{st_txt(e)}</td></tr>' for e in reversed(s['events']))
    cols = ''.join('<th>' + T(a, b) + '</th>' for a, b in [('起来', 'Start'), ('最热', 'Hottest'), ('结束', 'End'), ('持续天数', 'Days'), ('最热时是常态的', 'Peak vs norm'), ('状态', 'Status')])
    history = f'''<section id="fees" style="scroll-margin-top:80px"><h2>{T('历史全览：发射台每天收多少手续费', 'History: daily launchpad fees')}</h2>
<div class="card cycle-box">{chart}<p style="margin:14px 0 6px">{T(f'{s["first"][:4]} 年以来的每一轮热潮（色块 = 一轮，从起来到结束）', f'Every wave since {s["first"][:4]} (each block = one wave)')}</p><div style="position:relative;height:18px;background:var(--line);border-radius:4px;overflow:hidden">{''.join(strips)}</div><small style="color:var(--muted)">{s['first']} → {s['last']}</small></div>
<details><summary>{T('展开每一轮热潮', 'Show every wave')} ({len(s['events'])})</summary><div style="overflow:auto"><table><thead><tr>{cols}</tr></thead><tbody>{rows}</tbody></table></div></details></section>'''

    dashboard_html = dashboard(data, reading, T, esc, out, g.get('CYCLE_MONEY', ''))
    scope = T('DefiLlama「Launchpad」类目（早年含融资型发射平台，不全是 MEME）；新平台上线、旧平台加链或数据回填都会改变合计。各平台费率不同，手续费份额不等于成交份额。DEX 成交、DOGE 地址这类背景数据不并进来。',
              'DefiLlama Launchpad category (early years include fundraising launchpads, not only MEME). New venues, added chains or backfills change the total. Fee rates differ, so fee share is not volume share. DEX volume and DOGE addresses are not mixed in.')
    body = f'''<style>.cycle-box{{padding:18px}}</style>
<div class="ph"><div><div class="eyebrow">Launchpad activity temperature</div><h1>{T('发射台活动温度 · 周期全览', 'Launchpad activity temperature · cycles')}</h1><p class="lede">{T('先看现在多热，再看这一轮走到哪，最后对照过去每一轮。', 'How hot it is now, where this wave stands, then every past wave.')}</p></div><div class="stamp">{T('每日更新', 'Updated daily')}<br>{T('数据截至', 'Data as of')} <b>{data['cutoff']}</b> UTC</div></div>
{dashboard_html}
{history}
<details style="margin:20px 0"><summary>{T('数据范围与下载', 'Data scope and downloads')}</summary><p>{scope}</p>
<a href="/data/cycle/live.json" download>{T('下载每日序列与每轮热潮', 'Download daily series and waves')}</a> · <a href="/data/cycle/readings.json" download>{T('下载今天的读数', 'Download today’s reading')}</a> · <a href="/data/cycle/snapshot.json" download>{T('研究快照（截至 ' + data['snapshot_cutoff'] + '）', 'Research snapshot (to ' + data['snapshot_cutoff'] + ')')}</a> · <a href="/data/cycle/manifest.json" download>{T('来源与校验值', 'Provenance and SHA256')}</a> · <a href="https://defillama.com/">DefiLlama</a></details>'''
    g['emit']('launchpad/cycle/index.html', T('发射台活动温度 · 周期全览', 'Launchpad activity temperature · cycles'), body, active='launchpad', chart=True,
              desc=T('MEME 发射台现在多热、处在哪个阶段、这一轮走到哪；每日更新。', 'How hot MEME launchpads are, which stage, and where this wave stands; updated daily.'))
