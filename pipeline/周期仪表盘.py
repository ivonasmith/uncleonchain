"""Presentation vocabulary v1: descriptive labels, not validated trading regimes."""
import math
import json
import datetime as dt

COLORS = ['var(--cyc-t1)','var(--cyc-t2)','var(--cyc-t3)','var(--cyc-t4)','var(--cyc-t5)']   # 温度色带：CSS 变量，深浅主题各一套（网站样式.py）

def state(r):
    x, d = r['position'], r['direction_change']
    if x is None or d is None:
        return ('unknown','待积累','Insufficient history', 'var(--cyc-steady)')
    if d <= -.10:
        return ('autumn','退潮','Cooling', 'var(--cyc-autumn)')
    if x >= 70:
        return ('summer','盛夏','Summer', 'var(--cyc-summer)')
    if d >= .10:
        return ('spring','回暖','Warming', 'var(--cyc-spring)')
    if x <= 20:
        return ('winter','寒冬','Winter', 'var(--cyc-winter)')
    return ('steady','盘整','Consolidation', 'var(--cyc-steady)')

def gauge(r, T):
    x=r['position']; bands=[(0,20),(20,40),(40,60),(60,80),(80,100)]
    def point(v, radius=115):
        angle=math.pi*(1-v/100)
        return 160+radius*math.cos(angle),145-radius*math.sin(angle)
    paths=[]
    for i,(a,b) in enumerate(bands):
        ax,ay=point(a+.8);bx,by=point(b-.8)
        paths.append(f'<path d="M {ax:.3f} {ay:.3f} A 115 115 0 0 1 {bx:.3f} {by:.3f}" fill="none" style="stroke:{COLORS[i]}" stroke-width="20"/>')
    needle=''
    if x is not None:
        px,py=point(max(0,min(100,x)),96)
        needle=f'<path d="M160 145 L{px:.3f} {py:.3f}" stroke="currentColor" stroke-width="4" stroke-linecap="round"/><circle cx="160" cy="145" r="7" fill="currentColor"/>'
    label= T('暂无刻度','No reading') if x is None else f'{max(0,min(100,x)):.1f}'
    temp=T('历史不足','Insufficient history') if x is None else T('低温','Low') if x<=20 else T('偏凉','Cool') if x<40 else T('温和','Moderate') if x<60 else T('偏热','Warm') if x<80 else T('高热','High')
    raw=f'<small>{T("越界原始位置","Unclipped position")}: {x:.1f}</small>' if x is not None and (x<0 or x>100) else ''
    return f'''<div class="cd-gauge"><svg viewBox="0 0 320 190" role="img" aria-label="{T('活动温度','Activity temperature')} {label} {temp}">{''.join(paths)}{needle}<text x="36" y="178" fill="currentColor" font-size="12">0</text><text x="263" y="178" fill="currentColor" font-size="12">100</text></svg><div class="cd-score">{label}<small> / 100</small></div><b>{temp}</b>{raw}</div>'''

def dashboard(data, reading, T, esc, money, artifact_dir, money_html=''):
    s=data['series']['fees'];r=reading(s['points']);phase=state(r);x=r['position'];delta=r['direction_change']
    states=[('winter','寒冬','Winter','var(--cyc-winter)'),('spring','回暖','Warming','var(--cyc-spring)'),('summer','盛夏','Summer','var(--cyc-summer)'),('autumn','退潮','Cooling','var(--cyc-autumn)')]
    track=''.join(f'<div class="cd-season {"selected" if a==phase[0] else ""}" style="--season:{c}"><strong>{T(b,en)}</strong><small>{T(zh,eng)}</small></div>' for (a,b,en,c),(zh,eng) in zip(states,[('低位且未回暖','Low, not recovering'),('活动规模回升','Activity recovering'),('高位且未明显退潮','High, not sharply falling'),('活动规模明显回落','Activity declining')]))
    all_sequence=[]
    for i in range(len(s['points'])):
        seqr=reading(s['points'][:i+1]);all_sequence.append((s['points'][i][0],state(seqr)))
    sequence=all_sequence[-180:]
    runs=[]
    for date, st in all_sequence:
        if not runs or runs[-1]['state']!=st[0]:
            runs.append({'state':st[0],'start':date,'end':date,'days':1})
        else:
            runs[-1]['end']=date;runs[-1]['days']+=1
    valid_runs=[v for v in runs if v['state']!='unknown']
    complete_runs=valid_runs[1:-1] if len(valid_runs)>2 else []
    (artifact_dir/'stages.json').write_text(json.dumps({'version':'presentation-stages-v1','scope':'fees only; provisional descriptive rules','rules_in_priority_order':['missing: unknown','weekly change <= -0.10: autumn','position >= 70: summer','weekly change >= 0.10: spring','position <= 20: winter','otherwise: steady'],'daily':[{'date':date,'state':st[0]} for date,st in all_sequence],'runs':runs,'duration_inclusion':'all non-unknown runs excluding first and last; not independent market cycles'},ensure_ascii=False,indent=2))
    stage_rows=[]
    for code,zh,en,color in states+[('steady','盘整','Consolidation','var(--cyc-steady)')]:
        values=sorted(v['days'] for v in complete_runs if v['state']==code)
        def duration_q(p):
            h=(len(values)-1)*p;i=int(h);return values[i]+(values[min(i+1,len(values)-1)]-values[i])*(h-i)
        duration=f'{duration_q(.25):.1f}–{duration_q(.75):.1f}' if values else '—'
        stage_rows.append(f'<tr><td style="color:{color}">{T(zh,en)}</td><td>{len(values)}</td><td>{duration}</td></tr>')
    stage_table='<details><summary>'+T('各阶段历史上持续多久？（试行规则统计）','How long did stages last? (provisional-rule statistics)')+'</summary><div style="overflow:auto"><table><thead><tr><th>'+T('阶段','Stage')+'</th><th>'+T('完整状态段数','Complete runs')+'</th><th>'+T('中间50%天数','Middle 50%, days')+'</th></tr></thead><tbody>'+''.join(stage_rows)+'</tbody></table></div><p>'+T('从本序列可计算的全部历史重算；剔除首尾截断状态段。状态段不是独立行情，小幅阈值穿越也会切段；未加入迟滞和稳定性校准。仅描述标签持续时间，不预测剩余时间。','Recomputed over all available eligible history, excluding first and final censored runs. Runs are not independent cycles; threshold crossings split them. No hysteresis or stability calibration yet. Descriptive duration only, not remaining time.')+'</p></details>'
    age=0
    for date,st in reversed(sequence):
        if st[0]!=phase[0]:break
        age+=1
    strips=''.join(f'<span style="background:{st[3]};flex:1" title="{date} · {T(st[1],st[2])}"></span>' for date,st in sequence)
    episodes=s['events']; latest=episodes[-1] if episodes else None
    if latest:
        ongoing=latest['status']=='ongoing' and latest['end']==r['date']
        episode=f'''<p>{T('进行中的已识别波段','Open identified event') if ongoing else T('最近一轮已识别波段','Latest identified event')}: <b>{latest['start']} → {latest['end']}</b></p><p>{T('首次确认','First confirmed')}: {latest['confirmed']} · {T('高位区域','High region')}: {latest['plateau_start']} → {latest['plateau_end']}</p><p>{T('距该轮已观察峰值','Vs observed event peak')}: <b>{r['value']/latest['peak_value']-1:+.1%}</b> · {T('该事件已结束，不将其年龄当作当前周期进度','This event has ended; its age is not current-cycle progress') if not ongoing else T('仍在观察，最终峰值尚未知','Still observed; final peak unknown')}</p>'''
    else:episode=T('暂无已识别事件','No identified events')
    tiles=[];rise=fall=flat=0;eligible=0
    for key in ['pump.fun','four.meme','flap-sh','clanker','pons-v1','pons-v2']:
        sr=reading(data['series'][key]['points']);d=sr['direction_change'];st=state(sr)
        if sr['date']==r['date'] and d is not None:
            eligible+=1
            if d>=.1:rise+=1
            elif d<=-.1:fall+=1
            else:flat+=1
        change='—' if d is None else f'{d:+.1%}'
        tiles.append(f'<a class="card cd-platform" href="#{key}"><strong>{esc(key)}</strong><span style="color:{st[3]}">{T(st[1],st[2])}</span><b>{change}</b><small>{T("7日均值变化","7d mean change")} · {sr["date"]}</small></a>')
    summaries=[]
    for field,zh,en in [('days','完整波段','Whole event'),('rise_days','爬升时间','Rise'),('plateau_days','高位区域','High region'),('fall_days','峰值至结束','Peak to end')]:
        vals=sorted(e[field] for e in episodes if e['status']=='ended' and e.get(field) is not None)
        def q(p):
            h=(len(vals)-1)*p;i=int(h);return vals[i]+(vals[min(i+1,len(vals)-1)]-vals[i])*(h-i)
        summaries.append(f'<div><small>{T(zh,en)}</small><strong>{q(.25):.1f}–{q(.75):.1f}<small> {T("天","days")}</small></strong><small>n={len(vals)} · {T("中间50%","middle 50%")}</small></div>' if vals else '<div>—</div>')
    style='''<style>.cd-hero{display:grid;grid-template-columns:minmax(250px,1fr) 1.6fr;gap:24px;padding:24px}.cd-gauge{text-align:center;max-width:340px;margin:auto}.cd-gauge svg{width:100%;display:block}.cd-score{font-size:48px;font-weight:750;line-height:1.1}.cd-score small{font-size:15px;font-weight:400}.cd-gauge>b{display:block;font-size:20px;margin:8px}.cd-hero h2{font-size:36px;margin:8px 0}.cd-season-row,.cd-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:18px 0}.cd-season{padding:12px;border-bottom:3px solid var(--season);opacity:.6}.cd-season.selected{opacity:1;outline:1px solid var(--season);border-radius:8px}.cd-season small,.cd-summary small{display:block;color:var(--muted);font-size:12px}.cd-summary>div{padding:14px;border:1px solid var(--line);border-radius:12px}.cd-summary strong{display:block;font-size:24px}.cd-platforms{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.cd-platform{padding:16px;display:grid;gap:8px;color:var(--ink)}.cd-platform b{font-size:24px}.cd-platform small{color:var(--muted)}.cd-evidence{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.cd-evidence>div{padding:18px}.cd-evidence strong{font-size:25px}.cd-evidence p{color:var(--muted)}@media(max-width:760px){.cd-hero,.cd-evidence{grid-template-columns:1fr}.cd-platforms,.cd-season-row,.cd-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.cd-hero h2{font-size:30px}}</style>'''
    body=f'''{style}<nav style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:20px"><a class="btn" href="#environment">{T('环境仪表盘','Environment')}</a><a class="btn" href="#phase-position">{T('周期位置','Cycle position')}</a><a class="btn" href="#money">{T('钱在哪','Where the money is')}</a><a class="btn" href="#opportunity">{T('参与机会','Opportunity')}</a><a class="btn" href="#fees">{T('历史全览','History')}</a></nav>
<section id="environment" class="card cd-hero"><div><div class="eyebrow">{T('发射台活动温度 · 赛道手续费合计','Launchpad activity temperature · sector fees')}</div>{gauge(r,T)}</div><div><div class="eyebrow">{T('当前描述阶段 · 试行规则','Current descriptive stage · provisional')}</div><h2 style="color:{phase[3]}">{T(phase[1],phase[2])} · {T('活动降温中','Activity cooling') if phase[0]=='autumn' else T('观察市场变化','Observe activity')}</h2><p>{T('温度看高低，季节看变化。当前规模仍在历史常态区间内，但活动正在明显回落。','Temperature measures level; stage combines level and direction. Activity remains within its historical typical range but is declining.') if phase[0]=='autumn' and x is not None and 0<=x<=100 else T('阶段由活动水平与近期方向共同决定，不能解释为价格的牛熊或买卖信号。','Stage combines activity level and recent direction; it does not identify price regimes or trading signals.')}</p><div class="cd-summary"><div><small>{T('近一周变化','Weekly change')}</small><strong>{delta:+.1%}</strong></div><div><small>{T('近期基线倍数','Recent baseline')}</small><strong>{r['pulse']:.2f}×</strong></div><div><small>{T('标签连续保持','Consecutive label')}</small><strong>{'≥' if age==180 else ''}{age}<small>{T('天','days')}</small></strong></div><div><small>{T('数据日期','As of')}</small><strong style="font-size:18px">{r['date']}</strong></div></div><small>{T('当前是已覆盖发射台费用观察，不是全链MEME综合分，也不是赚钱概率。','Covered launchpad fees, not an all-chain MEME composite or profit probability.')}</small></div></section>
<div class="cd-season-row">{track}</div><p class="tnote">{T('四季是阅读标签，不按固定顺序循环；温和且方向平稳时标“盘整”。降温优先标退潮，因此低温也可能继续退潮。','Seasons are reading labels, not a fixed sequence. Moderate and stable activity is consolidation. Falling takes priority, so low activity may still be cooling.')}</p>
<section id="phase-position"><h2>{T('这一轮走到哪里了？','Where are we in the cycle?')}</h2><div class="card cycle-box">{episode}<b>{T('近180日阶段轨迹','Stage trail: last 180 days')}</b><div style="display:flex;height:22px;border-radius:6px;overflow:hidden;margin:14px 0" aria-label="{T('阶段轨迹','Stage trail')}">{strips}</div><small>{sequence[0][0]} → {sequence[-1][0]} · {T('按各日此前数据重算；源数据可能事后修订。标签天数不等于波段年龄。','Recomputed from each day’s prior history; sources may be revised. Label duration is not event age.')}</small></div>{stage_table}<div class="cd-summary">{''.join(summaries)}</div><p class="tnote">{T('这些范围来自全部已结束历史事件，尚未筛成与当下相似的独立行情；不是本轮剩余天数。高位日期和最终峰值属于事后复盘。','Ranges describe all ended events, not independently matched analogues or remaining days. High-region dates and final peaks use hindsight.')}</p></section>
{{MONEY}}
<section id="opportunity"><h2>{T('这样的环境，机会留给人多久？','What opportunities does this environment offer?')}</h2><div class="cd-evidence"><div class="card"><small>{T('采样基础','Sampling base')}</small><p><strong>1,060 + 299</strong></p><p>{T('原随机发行样本＋分环境补样，分列研究，不合并冒充全市场胜率。','Original random issuance sample plus regime supplements; analyzed separately, not pooled into a market win rate.')}</p></div><div class="card"><b>{T('分周期行为 · 已有统计','Regime behavior · descriptive results')}</b><p>{T('已比较不同环境的曲线成交集中与后续成交；结果依样本改变，不支持统一“6小时”纪律。','Curve-volume concentration and later trading compared across environments. Sample variation does not support a universal six-hour rule.')}</p></div><div class="card"><b>{T('盈利与强币 · 待验证','Profitability and strong tokens · pending')}</b><p>{T('成本后可退出收益、资金留存、强币诞生率与早期发现条件未过关；此处暂不显示参与评级或金狗名单。','Net executable returns, capital retention, strong-token incidence and early discovery criteria remain unvalidated. No participation rating or token shortlist yet.')}</p></div></div></section>
<details style="margin:20px 0"><summary>{T('仪表盘与阶段怎么计算？','How are the dial and stages calculated?')}</summary><p>{T('指针为历史Q05—Q95幅度位置，显示限制在0—100；越界原值另列。色带：0—20低温、20—40偏凉、40—60温和、60—80偏热、80—100高热。阶段按优先级：周变化≤−10%为退潮；否则位置≥70为盛夏；否则周变化≥10%为回暖；否则位置≤20为寒冬；其余盘整。缺值不分类。','Dial uses the historical Q05–Q95 amplitude position, displayed within 0–100 with unclipped values separately. Temperature bands are low, cool, moderate, warm and high at 20-point intervals. Stage priority: weekly change ≤−10% cooling; otherwise position ≥70 summer; otherwise change ≥10% warming; otherwise position ≤20 winter; otherwise consolidation. Missing values are unclassified.')}</p><p>{T('阶段映射是本次新增的可审阅展示规则，未经盈利或逃顶验证；不把旧事件的高位持续天数称为“盛夏时长”。','Stage mapping is a new reviewable display rule, not validated for profit or peak exits. Historical high-region duration is not called summer duration.')}</p><a href="/data/cycle/stages.json" download>{T('下载阶段规则与每日标签','Download stage rules and daily labels')}</a></details>'''
    return body.replace('{MONEY}', money_html)
