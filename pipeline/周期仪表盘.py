"""发射台活动温度：仪表盘、阶段标签与周期全览的展示层。阶段是按规则自动贴的阅读标签，不是买卖信号。"""
import math
import json

COLORS = ['var(--cyc-t1)','var(--cyc-t2)','var(--cyc-t3)','var(--cyc-t4)','var(--cyc-t5)']   # 温度色带：CSS 变量，深浅主题各一套（网站样式.py）

# 阶段：代码、中文、英文、颜色、一句大白话（中 / 英）
STAGES = [('winter','寒冬','Winter','var(--cyc-winter)','冷清，也还没回暖','Quiet, not yet recovering'),
          ('spring','回暖','Warming','var(--cyc-spring)','近一周明显回升','Clearly picking up this week'),
          ('summer','盛夏','Summer','var(--cyc-summer)','很热，还没明显回落','Hot, not yet fading'),
          ('autumn','退潮','Cooling','var(--cyc-autumn)','近一周明显回落','Clearly fading this week'),
          ('steady','盘整','Steady','var(--cyc-steady)','不冷不热，变化不大','Middling and flat')]
STAGE = {s[0]: s for s in STAGES}

STYLE = '''<style>.cd-hero{display:grid;grid-template-columns:minmax(240px,1fr) 1.7fr;gap:28px;padding:24px;margin:0 0 22px}.cd-gauge{text-align:center;max-width:320px;margin:auto}.cd-gauge svg{width:100%;display:block}.cd-score{font-size:46px;font-weight:750;line-height:1.1;font-family:var(--mono)}.cd-score small{font-size:15px;font-weight:400;color:var(--muted)}.cd-gauge>b{display:block;font-size:19px;margin:6px 0 4px}.cd-gauge>small{display:block;color:var(--muted);font-size:12px}
.cd-stages{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:10px 0 14px}.cd-st{display:flex;align-items:center;padding:6px 12px;border-radius:999px;border:1px solid var(--line2);color:var(--muted);font-size:13px}.cd-st::before{content:"";width:8px;height:8px;border-radius:50%;background:var(--season);margin-right:7px;opacity:.7}
.cd-st.on{flex-direction:column;align-items:flex-start;justify-content:center;padding:12px 18px;border-radius:14px;border:1px solid var(--season);background:color-mix(in srgb,var(--season) 16%,transparent);color:var(--ink);min-width:150px}.cd-st.on::before{display:none}.cd-st.on b{font-size:30px;line-height:1.15;color:var(--season)}.cd-st.on small{font-size:13px;color:var(--ink2);margin-top:2px}
.cd-say{font-size:15px;line-height:1.7;margin:0 0 6px}.cd-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0}.cd-summary>div{padding:12px 14px;border:1px solid var(--line);border-radius:12px}.cd-summary small{display:block;color:var(--muted);font-size:12px}.cd-summary strong{display:block;font-size:22px;font-family:var(--mono);margin:2px 0}.cd-summary strong small{display:inline;font-size:13px;font-family:var(--sans)}
.cd-evidence{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.cd-evidence>div{padding:18px}.cd-evidence strong{font-size:25px}.cd-evidence p{color:var(--muted)}.cd-top{display:grid;grid-template-columns:minmax(240px,1fr) 1.7fr;gap:28px}.cd-hero{display:block!important}.cd-prog{position:relative;display:block;height:6px;border-radius:3px;background:var(--line2);margin:6px 0 2px;overflow:visible}.cd-prog i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--ink2)}.cd-prog em{position:absolute;top:-3px;width:2px;height:12px;background:var(--muted)}.cd-over{color:var(--warn)!important}.cd-long{margin-top:20px;padding-top:18px;border-top:1px solid var(--line)}.cd-lnow strong{font:700 26px var(--mono)}.cd-lnow small{color:var(--muted)}.cd-mini{width:100%;height:auto;max-height:190px;display:block;margin:8px 0}.cd-mini .cd-line{fill:none;stroke:var(--ink2);stroke-width:1.6}.cd-mini .cd-early{fill:var(--ink2);opacity:.07}.cd-mini .cd-2y{fill:var(--lime);opacity:.55}.cd-mini .cd-ml{font-size:13px;fill:var(--ink2)}.cd-mini .ax{font-size:12px;fill:var(--muted)}.cd-mini .cd-pk{fill:var(--warn)}.cd-mini .cd-now{fill:var(--lime);stroke:var(--card);stroke-width:1.5}.cd-lstats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:6px 0 8px}.cd-lstats>div{padding:10px 14px;border:1px solid var(--line);border-radius:12px}.cd-lstats small{display:block;color:var(--muted);font-size:12px}.cd-lstats b{display:block;font:700 22px var(--mono);margin:2px 0}.cd-both{font-size:15px;line-height:1.7;margin:14px 0 6px;color:var(--ink)}.cd-cov{display:block;color:var(--muted);font-size:12px;line-height:1.6}.cd-more{font-size:13px;color:var(--lime-ink);text-decoration:none}.cd-more:hover{text-decoration:underline}
@media(max-width:760px){.cd-miniw{overflow-x:auto;-webkit-overflow-scrolling:touch}.cd-miniw .cd-mini{min-width:680px;max-height:none}.cd-top{grid-template-columns:1fr;gap:16px}.cd-lstats{grid-template-columns:1fr}.cd-evidence{grid-template-columns:1fr}.cd-hero{grid-template-columns:1fr;padding:18px}.cd-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.cd-st.on{min-width:0;width:100%;order:-1}}</style>'''


def state(r):
    x, d = r['position'], r['direction_change']
    if x is None or d is None:
        return ('unknown','待积累','Insufficient history', 'var(--cyc-steady)')
    code = 'autumn' if d <= -.10 else 'summer' if x >= 70 else 'spring' if d >= .10 else 'winter' if x <= 20 else 'steady'
    return STAGE[code][:4]


def band(x):
    if x is None:
        return ('历史不足', 'Insufficient history')
    return ('低温','Low') if x <= 20 else ('偏凉','Cool') if x < 40 else ('温和','Moderate') if x < 60 else ('偏热','Warm') if x < 80 else ('高热','High')


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
    label= T('暂无','—') if x is None else f'{max(0,min(100,x)):.1f}'
    temp=T(*band(x))
    over='' if x is None or 0<=x<=100 else T(f'（实际 {x:.0f}，已超出刻度）', f' (actual {x:.0f}, off the scale)')
    return f'''<div class="cd-gauge"><svg viewBox="0 0 320 190" role="img" aria-label="{T('活动温度','Activity temperature')} {label} {temp}">{''.join(paths)}{needle}<text x="36" y="178" fill="currentColor" font-size="12">0</text><text x="263" y="178" fill="currentColor" font-size="12">100</text></svg><div class="cd-score">{label}<small> / 100</small></div><b>{temp}{over}</b><small>{T('0 ≈ 近 2 年常态下沿 · 100 ≈ 常态上沿','0 ≈ lower edge of the 2-year norm · 100 ≈ upper edge')} <button type="button" class="info" data-tip="{T('常态范围排除两端各 5% 的历史值；原始极值保留。分数是范围中的位置，不是历史排名或赚钱概率。','The normal range drops the top and bottom 5% of past values; raw extremes are kept. The score is a position within that range, not a historical rank or a profit probability.')}">i</button></small></div>'''


_SEQ = {}


def sequence(points, reading):
    """每天只用当天及以前的数据重算阶段（不偷看未来）。同一序列只算一次。"""
    key = (len(points), points[-1][0], points[-1][2])
    if key not in _SEQ:
        _SEQ.clear()
        _SEQ[key] = [(points[i][0], state(reading(points[:i+1]))) for i in range(len(points))]
    return _SEQ[key]


def stage_age(points, reading, code):
    age = 0
    for _, st in reversed(sequence(points, reading)):
        if st[0] != code:
            break
        age += 1
    return age


def stage_runs(points, reading):
    """每段连续阶段的天数；去掉第一段和最后一段（没走完 / 被截断）。"""
    runs = []
    for date, st in sequence(points, reading):
        if not runs or runs[-1]['state'] != st[0]:
            runs.append({'state': st[0], 'start': date, 'end': date, 'days': 1})
        else:
            runs[-1]['end'] = date; runs[-1]['days'] += 1
    valid = [v for v in runs if v['state'] != 'unknown']
    return runs, (valid[1:-1] if len(valid) > 2 else [])


def q(vals, p):
    h = (len(vals) - 1) * p; i = int(h)
    return vals[i] + (vals[min(i + 1, len(vals) - 1)] - vals[i]) * (h - i)


def usd(v):
    a = abs(v)
    return ('$%.2fM' % (v / 1e6)) if a >= 1e6 else ('$%.0fK' % (v / 1e3)) if a >= 1e3 else ('$%.0f' % v)


def mini_history(points, lv, T):
    """长周期小图：全部 7 日平均（线性），早期口径不同的一段打灰，标可比段最高、最低和当前点。"""
    pts = [(p[0], p[2]) for p in points if p[2] is not None]
    if len(pts) < 30 or not lv:
        return ''
    W, H, L, R, TP, B = 1000, 170, 8, 112, 34, 22
    import datetime as _dt
    t = lambda d: _dt.date.fromisoformat(d).toordinal()
    t0, t1 = t(pts[0][0]), t(pts[-1][0]); hi = max(v for _, v in pts) * 1.08
    X = lambda d: L + (W - L - R) * (t(d) - t0) / max(1, t1 - t0)
    Y = lambda v: TP + (H - TP - B) * (1 - v / hi)
    step = max(1, len(pts) // 300)
    path = 'M' + 'L'.join(f'{X(d):.1f},{Y(v):.1f}' for d, v in pts[::step] + [pts[-1]])
    ce = X(lv['comparable_from'])
    two = X(max(pts[0][0], (_dt.date.fromisoformat(pts[-1][0]) - _dt.timedelta(days=730)).isoformat()))
    yrs = ''.join(f'<text x="{X(f"{y}-01-01"):.1f}" y="{H - 5}" class="ax" text-anchor="middle">{y}</text>' for y in range(int(pts[0][0][:4]) + 1, int(pts[-1][0][:4]) + 1))
    def dot(d, v, cls, lab, anchor='middle', dx=0, dy=-8):
        return f'<circle cx="{X(d):.1f}" cy="{Y(v):.1f}" r="3.5" class="{cls}"/><text x="{X(d) + dx:.1f}" y="{Y(v) + dy:.1f}" text-anchor="{anchor}" class="cd-ml">{lab}</text>'
    return (f'<svg viewBox="0 0 {W} {H}" class="cd-mini" role="img" aria-label="{T("全部历史 7 日平均手续费", "All-history 7-day average fees")}">'
            f'<rect x="{L}" y="{TP}" width="{ce - L:.1f}" height="{H - TP - B}" class="cd-early"/>'
            f'<text x="{L + 4}" y="{TP + 11}" class="cd-ml">{T("早期 · 口径不同", "Early · different basis")}</text>'
            f'<rect x="{two:.1f}" y="18" width="{W - R - two:.1f}" height="3" class="cd-2y"/>'
            f'<text x="{two:.1f}" y="13" class="cd-ml">{T("近 2 年 · 温度参照范围", "Last 2 years · temperature reference")}</text>'
            f'<path d="{path}" class="cd-line"/>{yrs}'
            + dot(lv['peak']['date'], lv['peak']['mean7'], 'cd-pk', T('最高 ', 'Peak ') + usd(lv['peak']['mean7']), 'end', -8, 4)
            + dot(lv['current']['date'], lv['current']['mean7'], 'cd-now', T('现在 ', 'Now ') + usd(lv['current']['mean7']), 'start', 8, 4)
            + '</svg>')


def hero(data, reading, T, esc, link='', close=''):
    """第一屏：近期温度（近 2 年）+ 当前阶段（大字底色卡）+ 长周期位置（全部历史）。矩阵页顶部和周期页共用。"""
    s = data['series']['fees']; P = s['points']; r = reading(P); ph = state(r); x = r['position']; d = r['direction_change']
    lv = data.get('long'); cov = data.get('coverage')
    chips = []
    for code, zh, en, color, szh, sen in STAGES:
        if code == ph[0]:
            chips.append(f'<div class="cd-st on" style="--season:{color}"><b>{T(zh,en)}</b><small>{T(szh,sen)}</small></div>')
        else:
            chips.append(f'<span class="cd-st" style="--season:{color}" title="{esc(T(szh,sen))}">{T(zh,en)}</span>')
    age = stage_age(P, reading, ph[0])
    _, done = stage_runs(P, reading)
    durs = sorted(v['days'] for v in done if v['state'] == ph[0])
    if durs:
        lo_d, hi_d = q(durs, .25), q(durs, .75)
        fill = min(100, 100 * age / max(hi_d, 1)); mark = 100 * lo_d / max(hi_d, 1)
        typical = (f'<small>{T(f"这个阶段一般持续 {lo_d:.0f}–{hi_d:.0f} 天", f"Usually lasts {lo_d:.0f}–{hi_d:.0f} days")}</small>'
                   f'<span class="cd-prog" title="{esc(T(f"过去 {len(durs)} 次的中间一半", f"Middle half of the past {len(durs)} stretches"))}"><i style="width:{fill:.0f}%"></i><em style="left:{mark:.0f}%"></em></span>'
                   + (f'<small class="cd-over">{T("已超过一般时长", "Longer than usual")}</small>' if age > hi_d else ''))
    else:
        typical = f'<small>{T("历史次数不够，不给一般时长", "Too few past stretches")}</small>'
    tip = esc(T('阶段由「温度高低」和「近一周涨跌」按固定规则自动判定：近一周跌超 10% 为退潮；否则温度 ≥70 为盛夏；否则近一周涨超 10% 为回暖；否则温度 ≤20 为寒冬；其余为盘整。阶段是阅读标签，不按固定顺序轮转，也不是买卖信号。',
                'Stage = level + weekly direction, by fixed rules: weekly change ≤ −10% is Cooling; else temperature ≥ 70 is Summer; else change ≥ +10% is Warming; else temperature ≤ 20 is Winter; otherwise Steady. A reading label, not a fixed sequence or a trading signal.'))
    pulse = '—' if r['pulse'] is None else f"{r['pulse']:.2f}"
    dtxt = '—' if d is None else f'{d:+.1%}'
    # 覆盖：扫了多少发射台、多少链，计入的占类目手续费多少
    if cov and cov.get('share') is not None:
        warn = cov['share'] < .95
        covtxt = (T(f'扫描 DefiLlama 收录的全部 {cov["listed"]} 个发射台（{cov["chains_active"]} 条链），当日有手续费的 {cov["active"]} 个里计入 {cov["included"]} 个，占类目当日手续费 {cov["share"]:.2%}',
                    f'Scans all {cov["listed"]} launchpads DefiLlama lists ({cov["chains_active"]} chains); {cov["included"]} of the {cov["active"]} with fees that day are counted, {cov["share"]:.2%} of category fees')
                  + (T('；覆盖偏低，今天的升降温仅供参考', '; coverage is low, so read today\'s change with care') if warn else '') + T('。', '.'))
    else:
        covtxt = T('覆盖信息待接入。', 'Coverage pending.')
    # 长周期位置（全部历史 · 可比段）
    if lv:
        early = lv.get('early_platforms') or [0, 0]
        ltip = esc(T(f'{lv["first"]} 起的全部数据都画在图上；{lv["comparable_from"]} 之前只有 {early[0]}–{early[1]} 家融资型发射平台报数、金额小两个数量级，口径不同，所以比高低只用之后的可比段。可比段内报数的平台也从 7 家增到近 200 家，长周期读数只作描述，不合成分数。',
                     f'Everything since {lv["first"]} is drawn; before {lv["comparable_from"]} only {early[0]}–{early[1]} fundraising launchpads reported, two orders of magnitude smaller, so highs and lows use the comparable segment only. Reporting venues grew from 7 to ~200 within it, so these readings are descriptive and not combined into a score.'))
        long_card = (f'<div class="cd-long"><div class="eyebrow">{T("长周期位置 · 全部可用历史", "Long-run position · all available history")} '
                     f'<button type="button" class="info" data-tip="{ltip}">i</button></div>'
                     f'<div class="cd-lnow"><strong>{usd(lv["current"]["mean7"])}</strong><small>{T(" / 天 · 7 日平均 · ", " / day · 7d average · ")}{lv["current"]["date"]}</small></div>'
                     f'<div class="cd-miniw">{mini_history(P, lv, T)}</div>'
                     f'<div class="cd-lstats"><div><small>{T("比可比段最高", "Vs comparable peak")}</small><b>{lv["from_peak"]:+.0%}</b><small>{T("最高 ", "Peak ")}{usd(lv["peak"]["mean7"])} · {lv["peak"]["date"]}</small></div>'
                     f'<div><small>{T("常态下沿的", "Vs normal lower edge")}</small><b>{lv["x_q05"]:.1f}{T(" 倍", "×")}</b><small>{T("下沿 ", "Edge ")}{usd(lv["q05"])}{T("（第 5 百分位，不是谷底）", " (5th percentile, not the low)")}</small></div>'
                     f'<div><small>{T("可比段最低", "Comparable low")}</small><b>{usd(lv["trough"]["mean7"])}</b><small>{lv["trough"]["date"]}{T(" · pump.fun 刚开始报数", " · as pump.fun began reporting")}</small></div></div>'
                     f'<small class="cd-cov">{T("全部历史 ", "All history ")}{lv["first"]} → {lv["last"]}{T(" · 可比段 ", " · comparable from ")}{lv["comparable_from"]}{T(" 起（pump.fun 开始报数）", " (pump.fun starts reporting)")}</small></div>')
        both = (T(f'近 2 年看「{band(x)[0]}」；放到 {lv["comparable_from"][:7]} 以来的可比历史，比最高时低 {-lv["from_peak"]:.0%}，仍是常态下沿的 {lv["x_q05"]:.1f} 倍。',
                  f'"{band(x)[1]}" against the last two years; against comparable history since {lv["comparable_from"][:7]}, {-lv["from_peak"]:.0%} below the peak and still {lv["x_q05"]:.1f}× the normal lower edge.')
                if x is not None and lv.get('from_peak') is not None and lv.get('x_q05') else '')
    else:
        long_card = f'<div class="cd-long"><div class="eyebrow">{T("长周期位置 · 全部可用历史", "Long-run position · all history")}</div><p>{T("可比历史不足一年，暂不给长周期读数；全部历史见周期页大图。", "Less than a year of comparable history; see the full chart on the cycles page.")}</p></div>'
        both = ''
    return f'''{STYLE}<section id="environment" class="card cd-hero"><div class="cd-top"><div><div class="eyebrow">{T('近期温度 · 近 2 年','Recent temperature · last 2 years')}</div>{gauge(r,T)}</div>
<div><div class="eyebrow">{T('当前阶段','Current stage')} <button type="button" class="info" data-tip="{tip}">i</button></div><div class="cd-stages">{''.join(chips)}</div>
<div class="cd-summary"><div><small>{T('已在这个阶段','In this stage for')}</small><strong>{age}<small> {T('天','days')}</small></strong>{typical}</div><div><small>{T('近一周变化','Week over week')}</small><strong>{dtxt}</strong><small>{T('7 日平均对比一周前','7d average vs a week ago')}</small></div><div><small>{T('相对近一个月','Vs the past month')}</small><strong>{pulse}<small> {T('倍','×')}</small></strong><small>{T('1 倍 = 近四周的常态','1× = normal for the last 4 weeks')}</small></div><div><small>{T('数据日期','Data date')}</small><strong style="font-size:17px">{r['date']}</strong><small>{close or T('UTC 日 · 每日更新','UTC day · daily')}</small></div></div></div></div>
{long_card}
{f'<p class="cd-both">{both}</p>' if both else ''}<small class="cd-cov">{covtxt}{(' · ' + link) if link else ''}</small></section>'''


def dashboard(data, reading, T, esc, artifact_dir, money_html='', close='', history_html=''):
    s=data['series']['fees'];P=s['points'];r=reading(P);phase=state(r)
    all_sequence=sequence(P, reading)
    seq180=all_sequence[-180:]
    runs=[]
    for date, st in all_sequence:
        if not runs or runs[-1]['state']!=st[0]:
            runs.append({'state':st[0],'start':date,'end':date,'days':1})
        else:
            runs[-1]['end']=date;runs[-1]['days']+=1
    valid_runs=[v for v in runs if v['state']!='unknown']
    complete_runs=valid_runs[1:-1] if len(valid_runs)>2 else []
    (artifact_dir/'stages.json').write_text(json.dumps({'version':'presentation-stages-v1','scope':'fees only; descriptive rules','rules_in_priority_order':['missing: unknown','weekly change <= -0.10: autumn','position >= 70: summer','weekly change >= 0.10: spring','position <= 20: winter','otherwise: steady'],'daily':[{'date':date,'state':st[0]} for date,st in all_sequence],'runs':runs,'duration_inclusion':'all non-unknown runs excluding first and last; not independent market cycles'},ensure_ascii=False,indent=2))

    def q(vals, p):
        h=(len(vals)-1)*p;i=int(h);return vals[i]+(vals[min(i+1,len(vals)-1)]-vals[i])*(h-i)

    def rng(vals):
        return f'{q(vals,.25):.0f}–{q(vals,.75):.0f}' if vals else '—'

    first_year = complete_runs[0]['start'][:4] if complete_runs else s['first'][:4]
    stage_rows=[]
    for code,zh,en,color,szh,sen in STAGES:
        vals=sorted(v['days'] for v in complete_runs if v['state']==code)
        now = f' <span class="tag" style="color:{color}">{T("现在","now")}</span>' if code==phase[0] else ''
        stage_rows.append(f'<tr><td class="l"><b style="color:{color}">{T(zh,en)}</b>{now}<br><small style="color:var(--muted)">{T(szh,sen)}</small></td><td>{T(f"{len(vals)} 次", f"{len(vals)}")}</td><td><b>{rng(vals)}</b> {T("天","days")}</td></tr>')
    stage_table=(f'<div class="card cycle-box" style="margin:14px 0"><h3 style="margin-top:0">{T("每个阶段一般持续几天？","How long does each stage usually last?")}</h3>'
                 f'<div style="overflow:auto"><table><thead><tr><th class="l">{T("阶段","Stage")}</th><th>{T(f"{first_year} 年以来出现过","Times since " + first_year)}</th><th>{T("一般持续","Usually lasts")}</th></tr></thead><tbody>{"".join(stage_rows)}</tbody></table></div>'
                 + '<p class="tnote">' + T('「一般持续」= 把每次持续的天数从短到长排好，去掉最短和最长的各四分之一，剩下那一半落在这个范围。阶段在门槛附近来回一两天也会算一次，所以天数整体偏短。只说明过去，不代表这一次还剩几天。',
                                          '"Usually lasts" = the middle half of all past durations (shortest and longest quarter removed). Brief threshold crossings count as separate stretches, so durations skew short. Describes the past, not how long this one has left.') + '</p></div>')

    episodes=s['events']; latest=episodes[-1] if episodes else None
    ended=[e for e in episodes if e['status']=='ended']
    if latest:
        ongoing=latest['status']=='ongoing'
        vs = r['value']/latest['peak_value']-1 if r['value'] is not None else None
        if ongoing:
            episode = T(f'<p>这一轮热潮 <b>{latest["start"]}</b> 开始，{latest["confirmed"]} 确认，<b>目前还没结束</b>；到目前为止最热是 {latest["peak"]}，真正的最高点要事后才知道。</p>',
                        f'<p>The current wave started <b>{latest["start"]}</b> (confirmed {latest["confirmed"]}) and <b>is still running</b>; hottest so far on {latest["peak"]}. The real peak is only known afterwards.</p>')
        else:
            episode = T(f'<p>最近一轮热潮：<b>{latest["start"]}</b> 起来 → <b>{latest["peak"]}</b> 最热 → <b>{latest["end"]}</b> 结束，一共 {latest["days"]} 天，最热时是起点常态的 {latest["multiple"]:.1f} 倍。</p>',
                        f'<p>Latest wave: started <b>{latest["start"]}</b> → hottest <b>{latest["peak"]}</b> → ended <b>{latest["end"]}</b>, {latest["days"]} days, peaking at {latest["multiple"]:.1f}× its starting baseline.</p>')
        if vs is not None:
            episode += T(f'<p>现在的活跃度比那一轮最热时{"低" if vs<0 else "高"} <b>{abs(vs):.0%}</b>。</p>', f'<p>Activity now is <b>{abs(vs):.0%}</b> {"below" if vs<0 else "above"} that wave’s peak.</p>')
    else:
        episode=T('<p>还没有识别出完整的热潮。</p>','<p>No complete wave identified yet.</p>')
    strips=''.join(f'<span style="background:{st[3]};flex:1" title="{date} · {T(st[1],st[2])}"></span>' for date,st in seq180)
    legend=''.join(f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px"><i style="width:10px;height:10px;border-radius:2px;background:{c};display:inline-block"></i>{T(zh,en)}</span>' for _,zh,en,c,_a,_b in STAGES)

    summaries=[]
    for field,zh,en,dzh,den in [('days','整轮','Whole wave','从起来到退完','start to finish'),('rise_days','升温','Heating up','从起来到最热','start to hottest'),('plateau_days','最热那几天','Hottest stretch','不低于最高点 8 成','within 80% of the peak'),('fall_days','降温','Cooling off','从最热到退完','hottest to finish')]:
        vals=sorted(e[field] for e in ended if e.get(field) is not None)
        summaries.append(f'<div><small>{T(zh,en)}</small><strong>{rng(vals)}<small> {T("天","days")}</small></strong><small>{T(dzh,den)}</small></div>' if vals else '<div>—</div>')
    rhythm=(f'<h3>{T(f"一轮热潮通常怎么走？（过去 {len(ended)} 轮）", f"How does a wave usually go? (past {len(ended)} waves)")}</h3><div class="cd-summary">{"".join(summaries)}</div>'
            f'<p class="tnote">{T("同样取中间一半的范围。哪天最热只有事后才知道，这些数用来对照节奏，不是倒计时。","Middle half of past waves again. The hottest day is only known in hindsight; use this for rhythm, not as a countdown.")}</p>')

    body=f'''<nav style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:20px"><a class="btn" href="#environment">{T('现在多热','How hot now')}</a><a class="btn" href="#fees">{T('全部历史','All history')}</a><a class="btn" href="#phase-position">{T('这一轮走到哪','This wave')}</a><a class="btn" href="#money">{T('钱在哪','Where the money is')}</a><a class="btn" href="#opportunity">{T('参与机会','Opportunity')}</a></nav>
{hero(data, reading, T, esc, '', close)}
{{HISTORY}}
<section id="phase-position"><h2>{T('这一轮走到哪了？','Where is this wave?')}</h2><div class="card cycle-box">{episode}<b>{T('近 180 天每天的阶段','Stage for each of the last 180 days')}</b><div style="display:flex;height:22px;border-radius:6px;overflow:hidden;margin:12px 0 8px" aria-label="{T('阶段轨迹','Stage trail')}">{strips}</div><div style="font-size:12px;color:var(--muted)">{legend}<span>{seq180[0][0]} → {seq180[-1][0]}</span></div></div>{stage_table}{rhythm}</section>
{{MONEY}}
<section id="opportunity"><h2>{T('这种环境下，新币机会能留多久？','How long do new-token opportunities last in this environment?')}</h2><div class="cd-evidence"><div class="card"><small>{T('研究样本','Research sample')}</small><p><strong>1,060 + 299</strong></p><p>{T('1,060 个随机抽的新币，加 299 个按冷热环境补的样本，两组分开看，不合起来冒充全市场胜率。','1,060 randomly drawn new tokens plus 299 added per environment, analysed separately rather than pooled into a market-wide win rate.')}</p></div><div class="card"><b>{T('已经看到的','What we see so far')}</b><p>{T('不同冷热环境下，新币的成交集中在上线后多久并不一样，没有统一的「6 小时规律」。','How quickly a new token’s trading concentrates differs by environment; there is no universal “six-hour rule”.')}</p></div><div class="card"><b>{T('还没验证的','Not yet verified')}</b><p>{T('扣掉成本后能不能赚钱、强势币出现的概率、怎么提前发现，都还没过检验，所以这里不给参与评级，也不给名单。','Net-of-cost returns, how often strong tokens appear and how to spot them early are unverified, so there is no rating or shortlist here.')}</p></div></div></section>
<details style="margin:20px 0"><summary>{T('这些数是怎么算的？','How is this calculated?')}</summary><p>{T('温度：把过去两年每天的活跃度（发射台手续费的 7 日平均）放在一起，去掉最低和最高各 5% 的极端日，剩下的范围拉成 0–100，看现在落在哪。0–20 低温、20–40 偏凉、40–60 温和、60–80 偏热、80–100 高热。','Temperature: take the past two years of daily activity (7-day average launchpad fees), drop the lowest and highest 5% of days, stretch the rest to 0–100 and see where today lands. 0–20 low, 20–40 cool, 40–60 moderate, 60–80 warm, 80–100 high.')}</p><p>{T('阶段：近一周跌超 10% 为退潮；否则温度 ≥70 为盛夏；否则近一周涨超 10% 为回暖；否则温度 ≤20 为寒冬；其余为盘整。每天只用当天以前的数据判定。','Stage: weekly change ≤ −10% is Cooling; else temperature ≥ 70 Summer; else change ≥ +10% Warming; else temperature ≤ 20 Winter; otherwise Steady. Each day uses only data up to that day.')}</p><p>{T('热潮：7 日平均连续 3 天超过前四周常态（中位数）的 1.5 倍，算一轮开始；之后连续 7 天回到常态 1.2 倍以内、或跌到这一轮最高点的 6 成以下，算结束。「最热那几天」= 最高点前后不低于最高点 8 成的日子。','Wave: the 7-day average stays above 1.5× the prior four-week norm (median) for 3 days to start; it ends after 7 straight days back within 1.2× the norm or below 60% of the wave’s peak. “Hottest stretch” = days around the peak within 80% of it.')}</p><a href="/data/cycle/stages.json" download>{T('下载每日阶段','Download daily stages')}</a></details>'''
    return body.replace('{MONEY}', money_html).replace('{HISTORY}', history_html)
