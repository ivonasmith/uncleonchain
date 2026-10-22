"""Frozen, auditable descriptive release. No trading rule or daily freshness implied."""
import datetime as dt
import hashlib
import json
from pathlib import Path
from 周期仪表盘 import dashboard, gauge


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


def build(g):
    T, esc, U = g['T'], g['esc'], g['U']
    root = Path(g['ROOT'])
    source = root / 'content/cycle/snapshot.json'
    data = json.loads(source.read_text())
    manifest = json.loads((source.parent / 'manifest.json').read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest['sha256'], 'Cycle snapshot hash mismatch'
    out = Path(g['SITE']) / 'data/cycle'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'snapshot.json').write_bytes(source.read_bytes())
    (out / 'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    results, sections, nav = {}, [], []
    en_names = {'fees':'Launchpad category fees','dex':'DEX venue volume background','doge':'DOGE active-address background'}
    for key, s in data['series'].items():
        if key not in ('fees', 'dex'):
            continue  # 只看整个赛道的冷暖（10-22 定）：逐平台仪表不展示，快照与下载里的平台数据保留；DOGE 活跃地址不是 MEME 参与度
        r0 = reading(s['points']); results[key] = r0
        r = r0
        name = T(s['label'], en_names.get(key, key+' fees'))
        nav.append(f'<a class="btn" href="#{key}">{esc(name)}</a>')
        def number(v):
            if v is None: return '—'
            return g['f_usd'](v) if key != 'doge' else f'{v:,.0f}'
        score = r['position']
        dial = gauge(r, T)
        delta = r['direction_change']
        direction = T('升温','Rising') if delta is not None and delta >= .1 else T('降温','Falling') if delta is not None and delta <= -.1 else T('大致平稳','Broadly steady') if delta is not None else '—'
        change = f'{delta:+.1%}' if delta is not None else '—'
        pulse = f'{r["pulse"]:.2f}×' if r['pulse'] is not None else '—'
        finished = [e for e in s['events'] if e['status'] == 'ended']
        def span(field):
            vals = [e[field] for e in finished if e.get(field) is not None]
            if not vals: return '—'
            return f'{quantile(vals,.25):.1f}–{quantile(vals,.75):.1f}' + T(' 天',' days') + f' · n={len(vals)}'
        rows = ''.join(f'<tr><td>{e["start"]}</td><td>{e["confirmed"]}</td><td>{e["peak"]}</td><td>{e["end"]}</td><td>{e["days"]}</td><td>{e["plateau_days"]}</td><td>{T("已结束","Ended") if e["status"]=="ended" else T("未闭合/缺报截断","Open / truncated")}</td></tr>' for e in reversed(s['events']))
        points = s['points']
        src = g['write_data']('cycle/'+key+'.json', [p[0] for p in points], {'raw':{p[0]:p[1] for p in points},'mean':{p[0]:p[2] for p in points}})
        chart = g['chart_div']({'src':src,'fmt':'usd' if key != 'doge' else 'num','ranges':['3M','1Y','ALL'],'range':'ALL','series':[{'k':'raw','n':T('原始日值','Daily raw'),'c':'s2'},{'k':'mean','n':T('7日均值','7d mean'),'c':'s1'}],'note':T('缺报保留为空；原始极值保留，常态范围仅作参考。','Missing values remain null; extremes are retained. Typical range is a reference only.')})
        # Event strips use calendar coordinates, allowing chronology to be read before opening the table.
        start = dt.date.fromisoformat(s['first']);end = dt.date.fromisoformat(s['last']);total=max(1,(end-start).days)
        strips = []
        for e in s['events']:
            left=100*(dt.date.fromisoformat(e['start'])-start).days/total
            width=100*((dt.date.fromisoformat(e['end'])-dt.date.fromisoformat(e['start'])).days+1)/total
            title=esc(f'{e["start"]} → {e["end"]} | {e["status"]} | {e["days"]} '+T('天','days'))
            strips.append(f'<span title="{title}" style="position:absolute;left:{left:.4f}%;width:{min(width,100-left):.4f}%;height:18px;background:var(--ink2);opacity:{1 if e["status"]=="ended" else .35}"></span>')
        scope = T(s['scope'], 'Separate source population; not a whole-MEME or all-chain measure.')
        grid = '' if key == 'fees' else f'''<div class="cycle-grid"><div class="card cycle-box"><h3>{T('常态范围位置','Typical-range position')}</h3>{dial}<p>{number(r['low'])} → {number(r['high'])}</p><small>{T('过去730天的Q05—Q95；至少365个有效日。超出范围可小于0或大于100，不是历史排名。','Q05–Q95 of the prior 730 days; at least 365 valid days. May be below 0 or above 100; not a percentile rank.')}</small></div>
<div class="card cycle-box"><h3>{T('方向与近期活跃','Direction and recent activity')}</h3><strong style="font-size:28px">{direction} {change}</strong><p>{T('7日均值对比7天前','7d mean vs seven days earlier')}</p><p>{T('近期相对活跃','Recent relative activity')}: <b>{pulse}</b></p><small>{T('当前7日均值 ÷ 此前28日均值序列的中位数；1×为近期基线。','Current 7d mean / median of the preceding 28 daily means; 1× is the recent baseline.')}</small></div>
<div class="card cycle-box"><h3>{T('历史持续区间','Historical duration ranges')}</h3><p>{T('完整波段','Whole event')}: <b>{span('days')}</b></p><p>{T('高位区域','High region')}: <b>{span('plateau_days')}</b></p><small>{T('已结束事件的中间50%范围，跨时期口径可能变化；不是剩余时间或持币时长。','Middle 50% of ended events only; neither remaining time nor a holding period.')}</small></div></div>'''
        sections.append(f'''<section id="{key}" style="scroll-margin-top:80px"><h2>{esc(name)}</h2><p class="tnote">{esc(scope)} · {esc(s['source'])} · {s['first']} → {s['last']} · {T('序列有效日 / 整日缺报（不代表成分齐全）','Series valid / missing days (not component completeness)')}: {s['valid_days']} / {s['missing_days']}</p>
{grid}
<p>{T('快照7日均值','Snapshot 7d mean')}: <b>{number(r['value'])}</b> · {r['date']}</p><div class="card cycle-box">{chart}<p>{T('历史波段时间轴（浅色为未闭合/截断）','Historical events (faded: open / truncated)')}</p><div style="position:relative;height:18px;background:var(--line)">{''.join(strips)}</div><small>{s['first']} → {s['last']}</small></div>
<details><summary>{T('展开每轮事件与确认日期','Expand events and confirmation dates')} ({len(s['events'])})</summary><div style="overflow:auto"><table><thead><tr>{''.join('<th>'+T(a,b)+'</th>' for a,b in [('起点','Start'),('确认日','Confirmed'),('事后峰值','Ex-post peak'),('末日','Last day'),('波段天数','Event days'),('高位天数','High days'),('状态','Status')])}</tr></thead><tbody>{rows}</tbody></table></div></details></section>''')
    sections = [(f'<details class="raw l3d"><summary>{T("广义交易背景：DEX 成交（不是纯 MEME，不与发射台拼接）","Broad trading background: DEX volume (not pure MEME, not spliced with launchpads)")}</summary>{x}</details>' if 'id="dex"' in x else x) for x in sections]
    nav = [x for x in nav if '#dex' not in x]
    for key, s in data['series'].items():          # 下载里的平台读数照样保留
        if key not in results and key != 'doge':
            results[key] = reading(s['points'])
    (out/'readings.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    dashboard_html = dashboard(data, reading, T, esc, g['f_usd'], out, g.get('CYCLE_MONEY', ''))
    body = f'''<style>.cycle-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}.cycle-box{{padding:18px}}.cycle-grid h3{{margin-top:0}}.cycle-grid small{{color:var(--muted)}}@media(max-width:760px){{.cycle-grid{{grid-template-columns:1fr}}}}</style>
<div class="ph"><div><div class="eyebrow">Market participation · full review</div><h1>{T('市场参与刻度','Market participation')}</h1><p class="lede">{T('先看市场处在什么位置，再看方向，最后对照历史波段。','Read the market range, its direction, then compare historical events.')}</p></div><div class="stamp">{T('独立研究快照','Frozen research snapshot')}<br><b>{data['cutoff']} UTC</b><br>{T('非实时 · 不随主站日更','Not live · separate from daily site updates')}</div></div>
{dashboard_html}
<p style="display:flex;flex-wrap:wrap;gap:8px">{''.join(nav)}</p>{''.join(sections)}
<h2>{T('口径与可核查边界','Method and audit boundaries')}</h2><div class="card cycle-box"><p>{T('发射台类别早期包含融资型平台，DEX是全品类交易背景；两者不拼接成九年MEME指数。DOGE地址活动仅保留在原始研究附件，不进入本面板或温度判断。汇总可能受新增平台、旧平台新增链、版本升级和回填影响。固定旧平台名单也不等于经济范围不变。各平台费用规则不同，手续费份额不是交易份额。','Early launchpad data includes fundraising platforms; DEX covers many asset classes. They are not stitched into a nine-year MEME index. DOGE address activity is retained only in the original research attachment and excluded from this panel and temperature readings. New venues, chains, versions and backfills can alter aggregates—even with a fixed venue list. Fee share is not volume share.')}</p><p>{T('历史事件规则：7日平滑、28日参考底座、1.5倍连续3日确认启动；回到底座1.2倍以内或回落至运行峰值60%，持续7日确认结束。高位区域按峰值80%规则回看；起点、峰值和高位区间均含事后信息。不同平滑参数会改变持续天数，不据此给出逃顶日期。','Historical rules: 7d smoothing, 28d baseline, 1.5× for 3 days to confirm entry; at or below 1.2× baseline or 60% of the running peak for 7 days to confirm exit. High-region analysis uses an 80% peak rule. Starts, peaks and high regions include hindsight; smoothing changes durations. These are not exit deadlines.')}</p><p>{T('常态范围排除两端各5%仅用于标尺，不删除原始极值；平台不足365个有效历史日不出长期刻度。季节名为明确标注的试行展示规则，尚未验证为交易规律。','The scale excludes the outer 5% at each end, while retaining all raw extremes. Fewer than 365 valid historical days means no long-term scale. Season labels are provisional presentation rules, not validated trading findings.')}</p>
<a href="/data/cycle/snapshot.json" download>{T('下载完整输入与事件','Download input and events')}</a> · <a href="/data/cycle/readings.json" download>{T('下载本页计算值','Download computed readings')}</a> · <a href="/data/cycle/manifest.json" download>{T('来源与SHA256','Provenance and SHA256')}</a> · <a href="https://defillama.com/">DefiLlama</a> · <a href="https://community-api.coinmetrics.io/">CoinMetrics Community</a></div>'''
    g['emit']('launchpad/cycle/index.html',T('市场参与刻度 · 历史观察','Market participation · historical view'),body,active='launchpad',chart=True,desc=T('历史常态位置、活动方向与周期全览；独立研究快照。','Historical range, activity direction and cycle atlas; frozen research snapshot.'))
