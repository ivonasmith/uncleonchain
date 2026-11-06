"""Read-only AgentPad child-contract adapter; never broadcasts transactions."""
import concurrent.futures
import datetime as dt
import json
import re
import statistics
from decimal import Decimal
from pathlib import Path
from core import day,dedup_logs,platform_day,cohort,abi_string
from eth import Chain,source_metadata,selector,event_topic,decode_event
from transport import Unavailable

def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2))
def parse_events(source):
    events=[]
    for name,args in re.findall(r'event\s+(\w+)\s*\((.*?)\)\s*;',source,re.S):
        inputs=[]
        for arg in args.split(','):
            parts=arg.strip().split()
            if not parts:continue
            inputs.append(dict(name=parts[-1],type=parts[0],indexed='indexed' in parts))
        events.append(dict(type='event',name=name,inputs=inputs,anonymous=False))
    return events

def curve_reserve_wei(sold):
    total=10**27;h=66_666_666_666_666_666_666_666_667;r=5_333_333_333_333_333_333
    if not 0<=sold<=8*10**26:raise ValueError('sold outside reviewed curve')
    return r*(total+h)//(total+h-sold)-r

def curve_spot_bnb(sold):
    total=10**27;h=66_666_666_666_666_666_666_666_667;r=5_333_333_333_333_333_333
    if not 0<=sold<=8*10**26:raise ValueError('sold outside reviewed curve')
    depth=total+h-sold
    return str(Decimal(r*(total+h)*10**18//(depth*depth))/10**18)

def collect(root,config,client,scope,dates,state):
    root=Path(root);rpc=config['rpc'];chain=Chain(client,rpc,scope,config['confirmations']);errors=[]
    prior_path=root/'data'/'agentpad_adapter.json'
    prior=json.loads(prior_path.read_text()) if prior_path.exists() else {}
    if prior.get('rpc')!=rpc:prior={}
    old_tokens={t['address'].lower():t for t in prior.get('tokens',[])}
    address='0xb31e99882d23377a9Ea360f1C065AD7b53Fb8Ec5'
    meta,source=source_metadata(client,address)
    token_source=meta['sources']['src/AgentPadTokenV3.sol']['content']
    curve_source=meta['sources']['src/CurveMath.sol']['content']
    factory_source=meta['sources']['src/AgentPadFactoryV2.sol']['content']
    for text in ['new AgentPadTokenV3','allTokens.push(token)','emit TokenCreated(token, msg.sender']:
        if text not in factory_source:raise Unavailable('AgentPad factory source changed')
    for text in ['a == creator || IAgentIdRegistry(agentIdRegistry).balanceOf(a) > 0','super._update(from, to, value);','if (graduated) revert AlreadyGraduated();']:
        if text not in token_source:raise Unavailable('AgentPad child source assumptions changed')
    for text in ['TOTAL_SUPPLY = 1_000_000_000e18','SOLD_CAP = 800_000_000e18','R = 5_333_333_333_333_333_333','H = 66_666_666_666_666_666_666_666_667','FEE_BPS = 100;']:
        if text not in curve_source:raise Unavailable('AgentPad curve constants changed')
    wrapped=chain.rpc('eth_call',[{'to':address,'data':selector('wbnb()')},'latest'])
    if ('0x'+wrapped[-40:]).lower()!='0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c':raise Unavailable('AgentPad wrapped quote asset mismatch')
    count=int(chain.rpc('eth_call',[{'to':address,'data':selector('tokensCount()')},'latest'],True),16)
    if count>10000:raise Unavailable('AgentPad enumeration exceeds reviewed request budget')
    def enum(i):return '0x'+chain.rpc('eth_call',[{'to':address,'data':selector('allTokens(uint256)')+hex(i)[2:].zfill(64)},'latest'],True)[-40:]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:addresses=list(pool.map(enum,range(count)))
    if len(set(addresses))!=count or any(a=='0x'+'0'*40 for a in addresses):raise Unavailable('AgentPad enumeration invalid')
    tokens={}
    def read_token(a):
        result=dict(address=a,platform='AgentPad',created_ts=None,graduated_ts=None,creator=None,name=None,symbol=None,factory=address,graduated_at_snapshot=None,raw=[source['raw_file']])
        for key,signature in [('registry','agentIdRegistry()')]:
            value=chain.rpc('eth_call',[{'to':a,'data':selector(signature)},'latest'],True);result[key]='0x'+value[-40:]
        if result['factory'].lower()!=address.lower() or result['registry'].lower()!=config['registry']['address'].lower():raise Unavailable('AgentPad token factory/immutable registry mismatch '+a)
        old=old_tokens.get(a.lower(),{})
        for key in ['created_ts','created_tx','creator','name','symbol','graduated_ts','pair','graduation_price_bnb','dex_seed_price_bnb','graduation_price','price_currency','graduation_mode','graduation_raw','first_observed_ts']:
            if key in old:result[key]=old[key]
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for t in pool.map(read_token,addresses):tokens[t['address'].lower()]=t
    creation=next(e for e in meta['abi'] if e.get('name')=='TokenCreated')
    events=[creation]+[e for e in parse_events(token_source) if e['name'] in ['Buy','Sell','Graduated']]
    bytopic={event_topic(e):e for e in events};topics=[list(bytopic)];scan_addresses=[address]+addresses
    event_records=[e for e in prior.get('events',[]) if e['date'] not in dates];complete={r['date']:r.get('complete',False) for r in prior.get('rows',[])};raw_by_date={r['date']:r.get('raw',[]) for r in prior.get('rows',[])}
    render_dates=sorted(set(dates)|set(complete))
    for date in dates:
        a=state['days'].get(date,{}).get('A',{});start,end=a.get('start_block'),a.get('end_block')
        if start is None or end is None:
            complete[date]=False;errors.append(dict(module='B/AgentPad-children',date=date,reason='区块范围U，未猜测子合约活动',rpc=rpc,url=None,blocks=[start,end]));continue
        rows,ok,errs=chain.logs(scan_addresses,start,end,topics,config['rpc_log_chunk'],1)
        complete[date]=ok;raw_by_date[date]=list(dict.fromkeys(chain.sources))+[source['raw_file']]
        if not ok:
            for e in errs:errors.append(dict(module='B/AgentPad-children',date=date,reason=e['reason'],rpc=rpc,url=rpc,blocks=[e['start'],e['end']]))
            continue
        log_sources=[]
        for rec in client.records:
            request=rec.get('json') or {}
            if request.get('method')=='eth_getLogs' and request['params'][0].get('address')==scan_addresses:
                arg=request['params'][0];log_sources.append((int(arg['fromBlock'],16),int(arg['toBlock'],16),rec['raw_file']))
        for log in dedup_logs(rows):
            abi=bytopic[log['topics'][0].lower()];value=decode_event(log,abi);block=int(log['blockNumber'],16)
            ts=int(log['blockTimestamp'],16) if log.get('blockTimestamp') else chain.time(block)
            record=dict(event=abi['name'],values=value,token=log['address'].lower(),date=date,timestamp=ts,block=block,tx=log['transactionHash'],tx_index=int(log['transactionIndex'],16) if log.get('transactionIndex') is not None else None,log_index=int(log['logIndex'],16),raw=[source['raw_file']]+list(dict.fromkeys(f for a,b,f in log_sources if a<=block<=b)))
            event_records.append(record)
            if abi['name']=='TokenCreated':
                t=tokens.get(value['token'].lower())
                if t is None:raise Unavailable('enumeration missing confirmed TokenCreated '+value['token'])
                t.update(created_ts=ts,created_tx=log['transactionHash'],creator=value['creator'],name=value['name'],symbol=value['symbol'])
            else:
                t=tokens[record['token']];t['first_observed_ts']=min(t.get('first_observed_ts',ts),ts)
                if abi['name']=='Graduated':
                    terminal=curve_spot_bnb(8*10**26)
                    t.update(graduated_ts=ts,pair=value['venue'],graduation_price_bnb=terminal,dex_seed_price_bnb=str(Decimal(value['bnb'])/Decimal(value['tokens'])),graduation_price=terminal,price_currency='BNB',graduation_mode=value['mode'],graduation_raw=record['raw'])
    trades=[]
    for e in event_records:
        if e['event'] not in ['Buy','Sell']:continue
        v=e['values'];buy=e['event']=='Buy';amount=v['bnbIn'] if buy else v['bnbOut']+v['fee']
        actor=v['buyer'] if buy else v['seller'];creator=tokens[e['token']].get('creator')
        trades.append(dict(platform='AgentPad',address=e['token'],timestamp=e['timestamp'],block=e['block'],tx=e['tx'],tx_index=e.get('tx_index'),log_index=e['log_index'],actor=actor,side='buy' if buy else 'sell',bnb=float(Decimal(amount)/10**18),curve_bnb_wei=amount,fee_wei=v['fee'],new_sold=v['newSold'],raw=e['raw'],identity_source_proven=creator is not None and actor.lower()!=creator.lower()))
    out=[];cutoff=int(dt.datetime.combine(dt.date.fromisoformat(scope),dt.time(),dt.timezone.utc).timestamp())
    deployment_day=day(chain.time(int(meta['deployment']['blockNumber'])))
    for date in render_dates:
        a=state['days'][date]['A'];end_ts=int(dt.datetime.combine(dt.date.fromisoformat(date)+dt.timedelta(days=1),dt.time(),dt.timezone.utc).timestamp());known=[]
        for t in tokens.values():
            if t['created_ts'] is None:continue
            item=dict(t,taxed=False,dev_prebuy=any(x['tx']==t.get('created_tx') and x['actor'].lower()==t['creator'].lower() and x['side']=='buy' for x in trades))
            daily_trades=[x for x in trades if x['address']==t['address'].lower() and x['timestamp']<end_ts]
            last=max(daily_trades,key=lambda x:(x['block'],x['log_index'])) if daily_trades else None
            reserve=curve_reserve_wei(last['new_sold'] if last else 0);item['raised_eod_bnb']=float(Decimal(reserve)/10**18);item['raised_eod_wei']=reserve;known.append(item)
        row=platform_day(known,trades,date,complete.get(date,False));row.update(platform='AgentPad',date=date,start_block=a.get('start_block'),end_block=a.get('end_block'),rpc=rpc,raw=raw_by_date.get(date,[]),complete=complete.get(date,False),launch_events_complete=complete.get(date,False),reason='完整工厂名册+子币Buy/Sell/Graduated；创建者有ID豁免，不能称纯ID买家集合')
        if complete.get(date):
            daily=[x for x in trades if day(x['timestamp'])==date];row['curve_volume_bnb']=str(Decimal(sum(x['curve_bnb_wei'] for x in daily))/10**18)
            row['graduated_today']=sum(t['graduated_ts'] is not None and day(t['graduated_ts'])==date for t in tokens.values())
            history_complete=all(complete.get(d,False) for d in render_dates if deployment_day<=d<=date)
            row['cumulative_graduated']=sum(t['graduated_ts'] is not None and t['graduated_ts']<end_ts for t in tokens.values()) if history_complete else None
            new=[t for t in known if day(t['created_ts'])==date]
            if new:row['median_raised_bnb']=str(statistics.median([Decimal(t['raised_eod_wei']) for t in new])/10**18)
            for hours in [24,72,168]:
                # Observe through the declared window or cutoff, with no silent gaps.
                eligible=all(complete.get(d,False) for d in render_dates if date<=d<scope)
                row['cohort_'+str(hours)+'h']=cohort(known,date,hours,cutoff,eligible)
        out.append(row)
    for t in tokens.values():
        t['graduation_status_complete']=bool(t['created_ts'] is not None and all(complete.get(d,False) for d in render_dates if day(t['created_ts'])<=d<scope))
        t['token_transfer_tax_rate']=0;t['curve_fee_bps']=100
    result=dict(rows=out,tokens=list(tokens.values()),trades=trades,events=event_records,errors=errors,scope=scope,rpc=rpc,source=source['url'],source_raw=source['raw_file'],universe_count=count,universe_status='当前未完名册；只将已确认历史日志计入日行',volume_definition='Buy.bnbIn + Sell.(bnbOut+fee)：两侧均不含平台交易费；募集为源码reserveAt(newSold)，不含强制转入捐赠',raw=list(dict.fromkeys(chain.sources)))
    dump(root/'data'/'agentpad_adapter.json',result)
    return result

if __name__=='__main__':
    from transport import Client
    root=Path(__file__).parent;config=json.loads((root/'config.json').read_text());state=json.loads((root/'state.json').read_text());scope=dt.datetime.now(dt.timezone.utc).date().isoformat();c=Client(root,config['proxy'])
    result=collect(root,config,c,scope,sorted(state['days']),state);print('AgentPad',result['universe_count'],'tokens;',len(result['trades']),'curve trades; requests',c.request_count,'cache',c.cache_hits)
