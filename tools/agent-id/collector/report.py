"""Offline reporting only: no HTTP and no model-generated market conclusions."""
import base64
import collections
import csv
import datetime as dt
import html
import io
import json
import math
import os
from pathlib import Path
import statistics
from core import day,timestamp,mean_complete,direction

def load(p,default):return json.loads(p.read_text()) if p.exists() else default
def dump(p,data):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2))
def show(v):
    if v is None:return 'U'
    if isinstance(v,(dict,list)):
        def nested(x):return 'U' if x is None else ({k:nested(a) for k,a in x.items()} if isinstance(x,dict) else ([nested(a) for a in x] if isinstance(x,list) else x))
        return json.dumps(nested(v),ensure_ascii=False)
    return str(v)
def html_table(rows,columns):
    esc=html.escape;out='<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(c)+'</th>' for c in columns)+'</tr></thead><tbody>'
    for row in rows:
        out+='<tr>'+''.join('<td>'+('<a href="'+esc(str(row.get(c)),quote=True)+'">'+esc(str(row[c]))+'</a>' if c in ['url','具体页面或接口URL'] and isinstance(row.get(c),str) and row[c].startswith('https://') else esc(show(row.get(c))))+'</td>' for c in columns)+'</tr>'
    return out+'</tbody></table></div>'
def reading_html(title,content):
    css='''*{box-sizing:border-box}body{margin:0;background:#f4f6f8;color:#172c3a;font:15px/1.75 system-ui,-apple-system,"PingFang SC",sans-serif}header{padding:25px 4vw;background:#173447;color:white}header a{color:#9bded1}main{max-width:1450px;margin:auto;padding:24px 4vw}h1{font-size:29px}h2{margin-top:36px}a{color:#08786f;overflow-wrap:anywhere}.notice{padding:16px 20px;background:#fff2ce;border-left:4px solid #ad7f16}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.chart{background:white;border:1px solid #dce4ea;border-radius:12px;overflow:hidden}.chart img{width:100%;display:block}.chart p{padding:0 18px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;background:white;font-size:12px}td,th{padding:10px 12px;border-bottom:1px solid #dde6eb;text-align:left;vertical-align:top;min-width:100px;overflow-wrap:anywhere}th{background:#e8f0f4}details{padding:12px;margin:12px 0;background:white;border:1px solid #dce4ea;border-radius:8px}summary{cursor:pointer}nav{display:flex;gap:15px;flex-wrap:wrap;margin:20px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:20px;border:1px solid #dce4ea}footer{color:#667b88;margin-top:40px}.metrics{display:flex;gap:20px;flex-wrap:wrap}.metrics div{padding:12px 20px;background:white;border:1px solid #dde6eb;border-radius:10px}.metrics b{display:block;font-size:28px}input{padding:12px;width:100%;font:inherit;border:1px solid #bed0da;border-radius:8px}@media(max-width:850px){.grid{grid-template-columns:1fr}main{padding:16px}h1{font-size:25px}}@media print{nav,input{display:none}.grid{display:block}.chart{break-inside:avoid}body{background:white}}'''
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>'+css+'</style></head><body><header><h1>'+html.escape(title)+'</h1><p>只读监控 · 仅数据、图和校验 · UTC</p></header><main>'+content+'</main></body></html>'

def charts(root,state,outcomes,weekly,hourly):
    os.environ.setdefault('MPLCONFIGDIR',str(root/'.mplcache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.font_manager import FontProperties
    font=Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
    if not font.exists():
        for candidate in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc']:
            if Path(candidate).exists():font=Path(candidate);break
    if font.exists():
        from matplotlib import font_manager
        font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'axes.unicode_minus':False,'font.size':9,'figure.facecolor':'white','axes.spines.top':False,'axes.spines.right':False})
    days=sorted(state['days']);x=np.arange(len(days));labels=[d[5:] for d in days];data=[state['days'][d] for d in days]
    nan=lambda v:np.nan if v is None else float(v)
    (root/'charts').mkdir(parents=True,exist_ok=True)
    saved=[]
    def setup(title):
        fig,ax=plt.subplots(figsize=(11,4.6),layout='constrained');ax.set_title(title,loc='left',fontsize=12,pad=16);ax.grid(axis='y',alpha=.16);return fig,ax
    def dates_ax(ax):
        ax.set_xticks(x);ax.set_xticklabels(labels,rotation=35,ha='right');ax.set_xlabel('UTC date')
    def note(ax,values):
        if not any(v is not None and not (isinstance(v,float) and math.isnan(v)) for v in values):ax.text(.5,.5,'U — 无完整可发布数据；未补零',transform=ax.transAxes,ha='center',color='#8a6219',fontsize=12)
    def save(fig,name,title,caption):
        p=root/'charts'/(name+'.png');fig.savefig(p,dpi=150);plt.close(fig);saved.append(dict(file=p.name,title=title,caption=caption,data_uri='data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()))
    title='1 · 每日新增 Agent ID、累计与 7 日均线';fig,ax=setup(title)
    v=[d['A'].get('daily_new_ids') for d in data];ax.bar(x,[nan(a) for a in v],color='#239a8c',label='新增');ax.plot(x,[nan(d['A'].get('ma7_new_ids')) for d in data],color='#d18d2a',marker='o',label='7日均线')
    ay=ax.twinx();ay.plot(x,[nan(d['A'].get('cumulative_ids')) for d in data],color='#3a72a5',label='累计');ax.set_ylabel('IDs / day');ay.set_ylabel('累计 IDs');dates_ax(ax);ax.legend(loc='upper left');ay.legend(loc='upper right');note(ax,v)
    if not any(d['A'].get('cumulative_ids') is not None for d in data):ay.set_yticks([]);ay.set_ylabel('累计 IDs：U')
    save(fig,'01_identity',title,'只发布完整 UTC 日；缺日为断点。累计缺少完整历史基线时为 U。')
    title='2 · 已观察起点首 7 天逐小时注册（最早起点核验状态见校验表）';fig,ax=setup(title)
    hv=[r['new_ids'] for r in hourly];xx=np.arange(len(hourly));ax.bar(xx,[nan(v) for v in hv],width=.8,color='#367caa');ax.set_xticks(xx[::24]);ax.set_xticklabels([r['date'] for r in hourly][::24],rotation=25);ax.set_ylabel('IDs / hour');note(ax,hv)
    save(fig,'02_hourly',title,'小时使用 UTC；某日读取不完整时该日 24 个小时全为 U。')
    platforms=sorted({p['platform'] for d in data for p in d.get('B',[])})
    title='3 · 每日新发币数，按平台分开';fig,ax=setup(title);bottom=np.zeros(len(days));any_values=[]
    for platform in platforms:
        raw=[next((p.get('new_launches') for p in d['B'] if p['platform']==platform),None) for d in data];any_values+=raw
        if not any(v is not None for v in raw):continue
        valid=[i for i,v in enumerate(raw) if v is not None];ax.bar(x[valid],[float(raw[i]) for i in valid],bottom=bottom[valid],label=platform)
        for i in valid:bottom[i]+=float(raw[i])
    dates_ax(ax);ax.set_ylabel('已读取平台的新发币（非生态总量）');note(ax,any_values)
    if any(v is not None for v in any_values):ax.legend(fontsize=6,ncol=3)
    save(fig,'03_launches',title,'堆叠仅包含该日完整读取的平台，是已核子集。未知平台不绘制、日表保留U；图中合计不代表生态总量。')
    title='4 · 按创建日队列的 24h / 72h / 7d 毕业率';fig,ax=setup(title);values=[]
    for platform in platforms:
        for hours in [24,72,168]:
            rows=[next((p for p in d['B'] if p['platform']==platform),{}) for d in data];cs=[r.get('cohort_'+str(hours)+'h',{}) for r in rows];ys=[r.get('ratio') for r in cs];values+=ys
            if any(y is not None for y in ys):
                ax.plot(x,[nan(y) for y in ys],marker='o',label=platform+'/'+str(hours)+'h')
                for i,c in enumerate(cs):
                    if c.get('ratio') is not None:ax.annotate(str(c['numerator'])+'/'+str(c['denominator']),(i,c['ratio']),fontsize=7)
    dates_ax(ax);ax.set_ylabel('graduates / launch cohort');note(ax,values)
    if any(v is not None for v in values):ax.legend(fontsize=6)
    save(fig,'04_cohorts',title,'右删失、发行集合不完整、零分母均为 U；有效点标分子/分母。')
    title='5 · 各平台内盘成交 BNB / 日';fig,ax=setup(title);values=[]
    for platform in platforms:
        ys=[next((p.get('curve_volume_bnb') for p in d['B'] if p['platform']==platform),None) for d in data];values+=ys
        if any(y is not None for y in ys):ax.plot(x,[nan(y) for y in ys],marker='o',label=platform)
    dates_ax(ax);ax.set_ylabel('BNB');note(ax,values)
    if any(v is not None for v in values):ax.legend(fontsize=6)
    save(fig,'05_volume',title,'非 BNB 计价和缺失活动不换填为 BNB；USD 只用单一币安闭合日 K。')
    title='6 · active_id_wallets 与 activation_rate';fig,ax=setup(title);ay=ax.twinx();v=[d.get('C',{}).get('active_id_wallets') for d in data]
    ax.plot(x,[nan(y) for y in v],marker='o',color='#228e80',label='active IDs');ay.plot(x,[nan(d.get('C',{}).get('activation_rate')) for d in data],color='#d2942d',marker='s',label='activation rate');dates_ax(ax);ax.set_ylabel('active ID addresses');ay.set_ylabel('active / cumulative IDs');note(ax,v)
    target_scope=data[-1].get('C',{}).get('observed_products') if data else None
    observed=[d.get('C',{}).get('observed_active_id_wallets') if d.get('C',{}).get('observed_products')==target_scope else None for d in data];rates=[d.get('C',{}).get('observed_activation_lower_bound') if d.get('C',{}).get('observed_products')==target_scope else None for d in data]
    if any(y is not None for y in observed):
        ax.plot(x,[nan(y) for y in observed],marker='o',linestyle='--',color='#6a70aa',label='已核产品：活跃ID下界');ay.plot(x,[nan(y) for y in rates],marker='s',linestyle='--',color='#aa7254',label='已核产品：激活率下界')
        for t in list(ax.texts):t.remove()
    ax.legend(loc='upper left',fontsize=7);ay.legend(loc='upper right',fontsize=7)
    save(fig,'06_activation',title,'全生态覆盖不足时主指标为U；虚线仅为已核产品实测下界，按同一产品范围绘制，范围变化处断开。产品范围见C日表。')
    title='7 · 前 1 / 10 / 100 地址门禁成交额占比';fig,ax=setup(title);values=[]
    for n in [1,10,100]:
        v=[d.get('C',{}).get('top'+str(n)+'_volume_share') for d in data];values+=v;ax.plot(x,[nan(y) for y in v],marker='o',label='Top '+str(n))
    dates_ax(ax);ax.set_ylabel('share');note(ax,values);ax.legend()
    save(fig,'07_concentration',title,'同一来源、已验证活动与 BNB 分母；分母为零时比例 U。')
    title='8 · 毕业后 D1 / D7 相对毕业价分布';fig,ax=setup(title);values=[]
    for n,pos in [(1,0),(7,1)]:
        ratios=[float(t['D'+str(n)])/float(t['graduation_price']) for t in outcomes if t.get('D'+str(n)) is not None and t.get('graduation_price') and not t.get('not_daily')];values+=ratios
        if ratios:ax.scatter([pos+(i-len(ratios)/2)*.015 for i in range(len(ratios))],ratios,alpha=.75)
        ax.text(pos,.04,'n='+str(len(ratios)),transform=ax.get_xaxis_transform(),ha='center')
    ax.set_xlim(-.3,1.3);ax.set_xticks([0,1]);ax.set_xticklabels(['D1 / graduation','D7 / graduation']);ax.set_ylabel('price ratio');note(ax,values)
    save(fig,'08_outcomes',title,'单币点图保留实际样本；平台/队列周中位数样本 n<5 为 U。')
    return saved

def build(root,config):
    root=Path(root);state=load(root/'state.json',{'days':{}});run=load(root/'last_run.json',{});errors=load(root/'data'/'gaps.json',[]);outcomes=load(root/'data'/'outcomes.json',[]);weekly=load(root/'data'/'outcome_weekly.json',[])
    days=sorted(state.get('days',{}));last=days[-1] if days else None;complete_days=[d for d in days if state['days'][d]['A'].get('complete')];cutoff=complete_days[-1] if complete_days else 'U'
    snapshot=load(root/'data'/'snapshots.json',[]);mints=load(root/'data'/'mint_registry.json',[]);mint_summary=load(root/'data'/'mint_summary.json',[]);facts=[];missing_counts=collections.Counter();utc=dt.datetime.now(dt.timezone.utc).isoformat()
    def fact(module,date,field,value,grade,urls=None,raw=None,blocks=None,rpc=None):
        url=urls if isinstance(urls,str) else (' ; '.join(urls) if urls else None)
        refs=raw if isinstance(raw,list) else ([raw] if raw else [])
        times=[raw_times[p] for p in refs if p in raw_times]
        if not times:times=[url_times[u] for u in (urls if isinstance(urls,list) else [urls]) if u in url_times]
        facts.append(dict(字段=module+'/'+date+'/'+field,值=show(value),证据级=grade,具体页面或接口URL=url or 'U',读取时间UTC=max(times) if times else 'U',raw=refs,blocks=blocks,rpc=rpc))
        if value is None:missing_counts[(date,module)]+=1
    # Actual-request set comes only from immutable raw request envelopes.
    request_urls=set();raw_times={};url_times={}
    for f in (root/'raw'/'http').glob('*.json'):
        r=load(f,{})
        if r.get('attempts'):
            request_urls.add(r.get('url'));raw_times[str(f.relative_to(root))]=r['read_utc'];url_times[r['url']]=max(url_times.get(r['url'],''),r['read_utc'])
    for f in (root/'raw').glob('*.json'):
        r=load(f,{})
        if r.get('read_utc') and (r.get('status') or r.get('error')):
            request_urls.add(r.get('url'));raw_times[str(f.relative_to(root))]=r['read_utc'];url_times[r['url']]=max(url_times.get(r['url'],''),r['read_utc'])
    for date in days:
        row=state['days'][date];a=row['A'];blocks=[a.get('start_block'),a.get('end_block')];rpc=a.get('rpc');sources=[rpc] if rpc in request_urls else None
        for f in ['daily_new_ids','cumulative_ids','ma7_new_ids','agent_id_holders','busiest_hour_share','sequence_name_share_e4']:
            fact('A',date,f,a.get(f),'E4' if f=='sequence_name_share_e4' else 'E1',sources,a.get('raw'),blocks,rpc)
        fact('A',date,'区块范围',blocks if all(v is not None for v in blocks) else None,'E1',sources,a.get('raw'),blocks,rpc)
        for b in row.get('B',[]):
            for f in ['new_launches','graduated_today','cumulative_graduated','curve_volume_bnb','curve_trade_count','unique_buyers','unique_creators','creators_ge3','median_raised_bnb','raised_lt1_share','taxed_share','dev_prebuy_share']:
                fact('B/'+b['platform'],date,f,b.get(f),'E1',sources,b.get('raw'),blocks,b.get('rpc'))
            for f in ['raised_lt1_share','taxed_share','dev_prebuy_share']:
                for k in ['numerator','denominator']:fact('B/'+b['platform'],date,f+'_'+k,b.get(f+'_'+k),'E1',sources,b.get('raw'),blocks,b.get('rpc'))
            for h in [24,72,168]:
                c=b.get('cohort_'+str(h)+'h',{})
                for k in ['numerator','denominator','ratio']:fact('B/'+b['platform'],date,'cohort_'+str(h)+'h_'+k,c.get(k),'E1',sources,b.get('raw'),blocks,b.get('rpc'))
        for f in ['active_id_wallets','activation_rate','top1_volume_share','top10_volume_share','top100_volume_share','multi_product_share']:fact('C',date,f,row.get('C',{}).get(f),'E1',sources,blocks=blocks,rpc=rpc)
        for f in ['observed_active_id_wallets','observed_activation_lower_bound','observed_multi_product_numerator','observed_multi_product_denominator','observed_multi_product_share','observed_products','identity_unknown_addresses']:fact('C已核产品下界',date,f,row.get('C',{}).get(f),'E1',sources,row.get('C',{}).get('raw'),blocks=blocks,rpc=rpc)
        for e in row.get('E',[]):
            fields=['mint_or_claim_transactions','participating_ids','cumulative_share']+(['total_minted','mints_last24h','mint_speed_per_hour','linear_sellout_date_e4'] if e['project']=='HashDroids' else [])
            for f in fields:fact('E/'+e['project'],date,f,e.get(f),'E4' if f.endswith('_e4') else 'E1',sources,blocks=blocks,rpc=rpc)
        p=row.get('bnb_price',{});fact('BNB价格',date,'BNBUSDT_UTC日收盘',p.get('close_usdt'),'E3',p.get('url') if p.get('url') in request_urls else None,[p['raw']] if p.get('raw') else [])
    for o in outcomes:
        date=o.get('created_date') or 'U'
        for f in ['status','price_currency','graduation_price','dex_seed_price_bnb','tax_rate','curve_fee_bps','first_dex_open','D0','D1','D3','D7','token_holder_addresses','top10_holder_share']:
            chain_field=f in ['graduation_price','dex_seed_price_bnb','tax_rate','curve_fee_bps'] and not o.get('not_daily')
            url=o.get('graduation_evidence_url') if chain_field else o.get('url')
            fact('D/'+o['platform']+'/'+o['address'],date,f,o.get(f),'E1' if chain_field else 'E3',url if url in request_urls else None,(o.get('graduation_raw') or o.get('raw')) if chain_field else o.get('raw'))
    for r in mints:
        for f in ['contract','total_supply','minted','price_tiers','source_verified','source_match_type','gate_verified','owner_can_change_price','owner_can_pause','requires_approval','approval_scope','requires_typedData','soulbound','first_secondary_listing_utc','floor_D0','floor_D1','floor_D3','floor_D7','trades_today','changed_free_to_paid','floor_drawdown_gt90','discovery_date']:
            value=r.get(f)
            if f=='gate_verified' and value is False:value=None # pending gate review is U, not proven absence
            grade=('E1' if r.get('gate_verified') and f in ['minted','total_supply','price_tiers','gate_verified'] else ('E4' if f=='discovery_date' else r.get('grade','E4')))
            urls=[u for u in [r.get('url'),r.get('rpc') if grade=='E1' else None] if u in request_urls]
            fact('G/'+r['project'],r['date'],f,value,grade,urls,r.get('raw'),[r.get('start_block'),r.get('end_block')],r.get('rpc'))
    for r in mint_summary:
        urls=sorted({x['url'] for x in mints if x['date']==r['date'] and x.get('url') in request_urls})
        for f in ['confirmed_gate_denominator','floor_available_numerator','floor_available_share','ecosystem_project_denominator','ecosystem_floor_available_share','D7_D0_sample_n','D7_D0_median']:fact('G汇总',r['date'],f,r.get(f),'E4',urls)
    for row in weekly:
        matching=[o for o in outcomes if o['platform']==row['platform'] and o.get('created_date') and not o.get('not_daily')]
        urls=sorted({o['url'] for o in matching if o.get('url') in request_urls})
        for field in ['D1_n','D1_median','D7_n','D7_median']:fact('D汇总/'+row['platform'],row['cohort_week'],field,row.get(field),'E3',urls)
    mint_rules=load(root/'data'/'mint_source_rules.json',[])
    for r in mint_rules:
        for field,value in r.items():
            if field not in ['url','raw','grade','read_utc']:fact('G源码规则/'+r['project'],r['read_utc'][:10],field,value,r['grade'],r['url'],r['raw'])
    rule_snapshots=load(root/'data'/'rule_snapshots.json',[])
    for item in config['rules_pages']:
        for date in days+[run.get('run_date',utc[:10])]:
            history=next((r for r in rule_snapshots if r['date']==date and r['url']==item['url']),{})
            observed=bool(history)
            fact('F/'+item['id'],date,'页面SHA256',history.get('sha256') if observed else None,item.get('grade','E2'),item['url'] if item['url'] in request_urls else None,[history['raw']] if observed and history.get('raw') else [])
        for date in days:
            if not any(r['date']==date and r['url']==item['url'] for r in rule_snapshots):errors.append(dict(module='F/'+item['id'],date=date,reason='历史UTC日未取得页面快照/哈希基线，不能用当前页面回填',url=None,blocks=None,rpc=None))
    for r in load(root/'data'/'explorer_source_checks.json',[]):fact('源码核验/'+r['project'],run.get('run_date',utc[:10]),'BscScan读取结果',r.get('status'),'E3',r['url'] if r['url'] in request_urls else None,[r['raw']] if r.get('raw') else [])
    # One disclosure row; never relabel Agent IDs as total Agentic Wallets.
    fact('披露点',run.get('run_date',utc[:10]),'Agentic Wallet 总数',None,'E2')
    for f in load(root/'data'/'run_facts.json',[]):
        urls=[u for u in (f.get('url') or []) if u in request_urls];fact('核验',run.get('run_date',utc[:10]),f['field'],f['value'],f['evidence'],urls,f.get('raw'))
    first=state.get('global_first_registration')
    fact('A核验',run.get('run_date',utc[:10]),'部署起全日志证明的首条注册',first,'E1',first.get('rpc') if first and first.get('rpc') in request_urls else None,first.get('raw') if first else None)
    # First seven days relative to the observed, not yet globally proven, start.
    hourly=[];start=config['backfill_observed_start']
    for offset in range(7):
        date=(dt.date.fromisoformat(start)+dt.timedelta(days=offset)).isoformat();a=state.get('days',{}).get(date,{}).get('A',{});counts=collections.Counter(dt.datetime.fromtimestamp(r['timestamp'],dt.timezone.utc).hour for r in a.get('registrations',[]))
        for h in range(24):hourly.append(dict(date=date,hour=h,new_ids=counts[h] if a.get('complete') else None,start_block=a.get('start_block'),end_block=a.get('end_block'),rpc=a.get('rpc')))
    dump(root/'data'/'first7_hourly.json',hourly)
    mint_events=load(root/'data'/'hashdroids_mints.json',[]);by_token={r['token_id']:r for r in mint_events};epochs=[]
    for epoch in range(32):
        token=epoch*256+1;event=by_token.get(token,{})
        e=dict(epoch=epoch,first_token_id=token,first_mint_timestamp=event.get('timestamp'),first_mint_utc=dt.datetime.fromtimestamp(event['timestamp'],dt.timezone.utc).isoformat() if event else None,block=event.get('block'),tx=event.get('tx'),rpc=event.get('rpc'))
        epochs.append(e);fact('E/HashDroids',run.get('run_date',utc[:10]),'epoch_'+str(epoch)+'_first_mint_timestamp',e['first_mint_timestamp'],'E1',e['rpc'] if e.get('rpc') in request_urls else None,event.get('raw'),blocks=[e['block'],e['block']],rpc=e['rpc'])
    dump(root/'data'/'hashdroids_epochs.json',epochs)
    dump(root/'facts.json',facts);columns=['字段','值','证据级','具体页面或接口URL','读取时间UTC']
    with (root/'facts.tsv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,delimiter='\t',extrasaction='ignore');w.writeheader();w.writerows(facts)
    (root/'facts.txt').write_text(' | '.join(columns)+'\n'+'\n'.join(' | '.join(str(r[k]).replace('|','｜').replace('\n','\\n') for k in columns) for r in facts)+'\n')
    tables={'identity_daily':[state['days'][d]['A'] for d in days],'platform_daily':[r for d in days for r in state['days'][d].get('B',[])],'participation_daily':[state['days'][d].get('C',{}) for d in days],'noncurve_daily':[r for d in days for r in state['days'][d].get('E',[])]}
    for name,rows in tables.items():
        dump(root/'data'/(name+'.json'),rows)
        columns2=list(dict.fromkeys(k for r in rows for k in r if k not in ['raw','registrations','transfers']))
        with (root/'data'/(name+'.csv')).open('w',newline='') as f:
            w=csv.writer(f);w.writerow(columns2);w.writerows([[show(r.get(k)) for k in columns2] for r in rows])
    nU=sum(x['值']=='U' for x in facts)
    gap_md='# Agent ID 监控缺口\n\n所有日期为UTC。未请求的计划接口不冒充证据URL。\n\n| 模块 | 日期 | 原因 | 区块范围 | RPC | 已请求URL |\n|---|---|---|---|---|---|\n'
    gap_md+=''.join('| '+ ' | '.join(show(e.get(k)).replace('|','｜').replace('\n',' ') for k in ['module','date','reason','blocks','rpc','url'])+' |\n' for e in errors)
    (root/'gaps.md').write_text(gap_md)
    (root/'gaps.html').write_text(reading_html('数据缺口',html_table(errors,['module','date','reason','blocks','rpc','url'])))
    summary='# Agent ID 每日记录\n\n仅记录数值、与此前7个完整UTC日均值的方向、变更及缺口。U不计算方向。\n'
    summaries=[]
    for i,date in enumerate(days):
        row=state['days'][date];summary+='\n## '+date+' UTC\n\n';summary+='| 模块/字段 | 当日值 | 对前7日均值方向 |\n|---|---|---|\n'
        fields=[('A/daily_new_ids',row['A'].get('daily_new_ids'),[state['days'][d]['A'].get('daily_new_ids') for d in days[:i][-7:]]),('A/agent_id_holders',row['A'].get('agent_id_holders'),[state['days'][d]['A'].get('agent_id_holders') for d in days[:i][-7:]]),('C/active_id_wallets',row.get('C',{}).get('active_id_wallets'),[state['days'][d].get('C',{}).get('active_id_wallets') for d in days[:i][-7:]])]
        scope=row.get('C',{}).get('observed_products')
        for field in ['observed_active_id_wallets','observed_activation_lower_bound']:
            fields.append(('C已核产品下界/'+field,row.get('C',{}).get(field),[state['days'][d].get('C',{}).get(field) if state['days'][d].get('C',{}).get('observed_products')==scope else None for d in days[:i][-7:]]))
        for p in row.get('B',[]):
            for field in ['new_launches','graduated_today','curve_volume_bnb']:
                prev=[next((r.get(field) for r in state['days'][d]['B'] if r['platform']==p['platform']),None) for d in days[:i][-7:]];fields.append(('B/'+p['platform']+'/'+field,p.get(field),prev))
        for e in row.get('E',[]):fields.append(('E/'+e['project']+'/mint_or_claim_transactions',e.get('mint_or_claim_transactions'),[next((r.get('mint_or_claim_transactions') for r in state['days'][d].get('E',[]) if r['project']==e['project']),None) for d in days[:i][-7:]]))
        gs=next((r for r in mint_summary if r['date']==date),{})
        for field in ['confirmed_gate_denominator','floor_available_numerator','floor_available_share','D7_D0_sample_n','D7_D0_median']:
            fields.append(('G/'+field,gs.get(field),[next((r.get(field) for r in mint_summary if r['date']==d),None) for d in days[:i][-7:]]))
        ds=[float(o['D1'])/float(o['graduation_price']) for o in outcomes if o.get('created_date')==date and not o.get('not_daily') and o.get('D1') is not None and o.get('graduation_price')]
        fields.append(('D/创建日队列D1有效样本数',len(ds),[]));fields.append(('D/创建日队列D1相对毕业价中位数',statistics.median(ds) if len(ds)>=5 else None,[]))
        fs=[r for r in rule_snapshots if r['date']==date]
        fields.append(('F/已取得哈希的页面数',len(fs) if fs else None,[]))
        for field,value,prev in fields:
            direct=direction(value,prev);summary+='| '+field+' | '+show(value)+' | '+show(direct)+' |\n';summaries.append(dict(date=date,field=field,value=value,direction=direct))
        for module in ['A','B','C','D','E','F','G']:summary+='\n'+module+' 当日U字段数：'+str(sum(n for (d,m),n in missing_counts.items() if d==date and m.split('/')[0]==module))+'。'
        gs=next((r for r in mint_summary if r['date']==date),None)
        if gs:summary+='\n\nG 免费铸造登记：'+show(gs)+'\n'
        reasons=[e['module']+': '+e['reason'] for e in errors if e['date']==date];summary+='\n\nU原因：'+'；'.join(dict.fromkeys(reasons))+'\n'
    changes=load(root/'data'/'rule_changes.json',[]);summary+='\n## F 实际变更检测日\n\n'+('\n'.join(show(x) for x in changes) or 'U（尚无可比较的成功基线；不是“没有变化”）')+'\n'
    (root/'daily_summary.md').write_text(summary);dump(root/'data'/'daily_summary.json',summaries)
    (root/'daily_summary.html').write_text(reading_html('Agent ID 每日记录','<p>全部日期UTC。只记录；缺失不计算方向。</p>'+html_table(summaries,['date','field','value','direction'])+'<h2>F 变更</h2>'+html_table(changes,['change_date','url','snippet','keywords'])))
    ims=charts(root,state,outcomes,weekly,hourly)
    coverage=load(root/'data'/'reconciliation.json',{})
    b_families={p['platform'].split('-')[0] for d in days for p in state['days'][d].get('B',[]) if p.get('new_launches') is not None}
    d_families={o['platform'].split('-')[0] for o in outcomes if not o.get('not_daily') and any(o.get('D'+str(n)) is not None for n in [0,1,3,7])}
    criteria=[dict(check='身份全序列对账与ownerOf抽样',status=coverage.get('status','U')),dict(check='从首条注册至昨日无静默缺日',status=('PASS' if state.get('pre_start_complete') and len(complete_days)==len(days) else 'U（观察起点覆盖；全历史仍待证实）')),dict(check='B至少两个不同平台系列的完整UTC日真实指标',status='PASS' if len(b_families)>=2 else 'NOT MET'),dict(check='D至少两个不同平台系列的毕业后历史价格',status='PASS' if len(d_families)>=2 else 'NOT MET'),dict(check='8张PNG趋势图',status='PASS' if len(ims)==8 else 'FAIL'),dict(check='至少9个合成测试',status='见test_log.txt，独立测试日志'),dict(check='全部采集请求经已实测代理',status='PASS' if config.get('proxy') else 'PENDING')]
    dump(root/'validation.json',dict(as_of=last,criteria=criteria,U_count=nU,fact_rows=len(facts),reconciliation=coverage))
    questions=['G的地板价D0从铸造开放日还是首次有效二级挂牌日算起？当前未指定，不代填地板历史。','B的单币募集中位数覆盖当日新发队列，还是当日全部仍在曲线中的币？当前采用当日新发队列的日末募集额。','C的活动地址按链上事件的买家/铸造接收方，还是交易发送方？当前按适配器明确的事件参与者，并核验其Agent ID；中继发送方不自动计入。']
    content='<p class="notice"><strong>数据截至 UTC '+html.escape(show(last))+'（日历覆盖）；身份层已完整读取截至 '+cutoff+'。</strong> U 不表示零。代理状态：'+html.escape(config.get('proxy_status','已配置'))+'。本次缺口与未达标项均列出，不生成参与结论或买卖建议。</p>'
    content+='<nav><a href="daily_summary.html">每日记录</a><a href="gaps.html">缺口</a><a href="facts.txt">逐行事实</a><a href="facts.tsv">五列事实TSV</a><a href="facts.json">事实JSON</a><a href="test_log.txt">测试日志</a><a href="artifact_verification.html">文件校验</a><a href="validation.json">采集达标检查</a><a href="README.html">运行说明</a></nav>'
    content+='<div class="metrics"><div><b>'+str(len(days))+'</b>显式UTC日行</div><div><b>'+str(len(facts))+'</b>字段行</div><div><b>'+str(nU)+'</b>U字段</div><div><b>8</b>图表</div></div><h2>趋势图</h2><div class="grid">'
    for im in ims:content+='<article class="chart"><img alt="'+html.escape(im['title'],quote=True)+'" src="'+im['data_uri']+'"><p>'+html.escape(im['caption'])+'</p></article>'
    content+='</div><h2>模块摘要</h2><ul>'
    latest=state['days'][last] if last else {};last_a=latest.get('A',{});last_c=latest.get('C',{});last_e={r['project']:r for r in latest.get('E',[])};last_g=next((r for r in mint_summary if r['date']==last),{})
    formal=[o for o in outcomes if not o.get('not_daily')]
    module_lines=[('A',f'首条注册 {show(days[0] if days else None)}；截至 {show(last)} 累计 {show(last_a.get("cumulative_ids"))}，持有地址 {show(last_a.get("agent_id_holders"))}；对账 {coverage.get("status","U")}。'),('B',f'完整读取的平台系列 {len(b_families)} 个；AgentPad已入表，其他平台逐项U；两平台达标线尚未达到。'),('C',f'全生态活跃数U；已核产品下界 {show(last_c.get("observed_active_id_wallets"))} 个Agent ID地址，覆盖 '+show(last_c.get('observed_products'))+'。'),('D',f'正式创建队列 {len(formal)} 币；独立当前候选快照 {len(outcomes)-len(formal)} 币；取得毕业后历史价格的平台系列 {len(d_families)} 个，D7不足龄U。'),('E',f'HashDroids累计 {show(last_e.get("HashDroids",{}).get("total_minted"))}/8192，当日新增 {show(last_e.get("HashDroids",{}).get("mint_or_claim_transactions"))}；Ptah POA累计 {show(last_e.get("Ptah-POA",{}).get("total_minted"))}；其他项目U。'),('F',f'已保存页面哈希 {len(rule_snapshots)} 条；仅有首次基线时变更为U，不称没有变化。'),('G',f'铸造候选 {len({r["project"] for r in mints})} 项；已核门禁子集地板可用 {show(last_g.get("floor_available_numerator"))}/{show(last_g.get("confirmed_gate_denominator"))}；生态全集分母及D7/D0中位数U。')]
    content+=''.join('<li><b>'+m+'</b> '+html.escape(line)+'</li>' for m,line in module_lines)+'</ul><h2>达标检查</h2>'+html_table(criteria,['check','status'])
    content+='<h2>当前来源快照（未完，不进入日趋势）</h2>'
    sr=[dict(source=s['source'],read_utc=s['read_utc'],index_count=len(s['items']),graduated_snapshot=sum(bool(t.get('curve',t).get('graduated')) for t in s['items']),status=s['date_status'],url=s['url']) for s in snapshot]
    content+=html_table(sr,['source','read_utc','index_count','graduated_snapshot','status','url'])
    for title,rows,cols in [('A身份日表',tables['identity_daily'],['date','daily_new_ids','cumulative_ids','ma7_new_ids','agent_id_holders','busiest_hour_share','sequence_name_share_e4','start_block','end_block','rpc']),('B平台日表',tables['platform_daily'],['date','platform','new_launches','graduated_today','cumulative_graduated','curve_volume_bnb','curve_trade_count','unique_buyers','unique_creators','start_block','end_block','rpc','reason']),('D结局',outcomes,['platform','address','created_date','graduated_date','status','price_currency','graduation_price','dex_seed_price_bnb','tax_rate','curve_fee_bps','first_dex_open','D0','D1','D3','D7','token_holder_addresses','top10_holder_share','url']),('E非曲线',tables['noncurve_daily'],['date','project','mint_or_claim_transactions','participating_ids','cumulative_share','total_minted','mints_last24h','linear_sellout_date_e4','start_block','end_block','rpc']),('F规则变更',changes,['change_date','url','snippet','keywords'])]:content+='<details><summary>'+title+'</summary>'+html_table(rows,cols)+'</details>'
    comparison=load(root/'data'/'source_comparison.json',[])
    content+='<details><summary>独立RPC序列重叠日对照（不拼接）</summary>'+html_table(comparison,['date','old_rpc','old_daily_new_ids','new_rpc','new_daily_new_ids','equal','old_read_utc','new_read_utc'])+'</details>'
    content+='<details><summary>C 全生态指标与已核产品下界</summary>'+html_table(tables['participation_daily'],['date','active_id_wallets','activation_rate','top1_volume_share','top10_volume_share','top100_volume_share','multi_product_share','observed_products','observed_active_id_wallets','observed_activation_lower_bound','observed_multi_product_numerator','observed_multi_product_denominator','observed_multi_product_share','identity_unknown_addresses','start_block','end_block','rpc'])+'</details>'
    content+='<details><summary>D 按平台/创建周：毕业后相对价格与样本数</summary>'+html_table(weekly,['platform','cohort_week','D1_n','D1_median','D7_n','D7_median'])+'</details>'
    content+='<h2>G · 免费铸造登记</h2><p>候选发现与门禁核实分开。地板可用比例仅限已核子集，生态全集分母及比例仍为U。免费转付费按方法分支记录；地板价U的项目保留。</p>'+html_table(mint_summary,['date','candidate_count','confirmed_gate_denominator','floor_available_numerator','floor_available_share','ecosystem_project_denominator','ecosystem_floor_available_share','D7_D0_sample_n','D7_D0_median','U_floor_candidates'])
    content+='<details><summary>HashDroids每个epoch首铸时间戳</summary>'+html_table(epochs,['epoch','first_token_id','first_mint_timestamp','first_mint_utc','block','tx','rpc'])+'</details>'
    content+='<details><summary>G逐项目、逐日字段</summary>'+html_table(mints,['date','project','contract','total_supply','minted','price_tiers','source_verified','source_verified_read_date','source_match_type','owner_can_change_price','owner_can_pause','requires_approval','approval_scope','requires_typedData','soulbound','first_secondary_listing_utc','floor_D0','floor_D1','floor_D3','floor_D7','trades_today','changed_free_to_paid','floor_drawdown_gt90','reason'])+'</details>'
    content+='<h2>G 已核实的源码固定规则</h2><p>这是源码核验读取时点的规则表，不能替代历史日末已铸数；合约签名要求不等于前端请求已核实。</p>'+html_table(mint_rules,['project','address','source_total_supply_cap','source_free_quota','source_paid_quota','source_price_tiers','owner_can_change_price','owner_can_pause','contract_mint_requires_erc20_approval','contract_mint_requires_typedData','read_utc','url'])
    content+='<h2>真正影响读数的3个口径疑问</h2><ol>'+''.join('<li>'+html.escape(q)+'</li>' for q in questions)+'</ol><footer>HTML整理 '+utc+'；不冒充数据截止日。单文件内嵌全部图，离线可读。没有冻结评分改动。</footer>'
    (root/'dashboard.html').write_text(reading_html('Agent ID 生态监控',content))
    dump(root/'report_metrics.json',dict(UTC_calendar_through=last,identity_complete_through=cutoff,fact_rows=len(facts),U_count=nU,charts=8,module_lines=module_lines,questions=questions))
    from verify_outputs import verify
    result=verify(root,quiet=True)
    if result['status']!='PASS':raise ValueError('保存文件校验未通过，见artifact_verification.html')
    return {'facts':len(facts),'U':nU,'charts':len(ims)}
