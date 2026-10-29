#!/usr/bin/env python3
"""python monitor_agent_id.py --backfill / --daily / --report

All outbound access uses config.proxy. Nothing signs, connects accounts or broadcasts.
Missing data is None in JSON and U in reading outputs. Protocol-specific adapters are
admitted only after matched source, gate, event semantics and universe checks.
"""
import argparse
import base64
import collections
import datetime as dt
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
import traceback
import urllib.parse

from core import *
from transport import Client,Unavailable,utc_now
from eth import Chain,source_metadata,event_topic,decode_event,selector

ROOT=Path(__file__).resolve().parent
def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));tmp.replace(path)
def load(path,default):return json.loads(Path(path).read_text()) if Path(path).exists() else default
def dates(a,b):
    a=dt.date.fromisoformat(a);b=dt.date.fromisoformat(b)
    while a<=b:yield a.isoformat();a+=dt.timedelta(days=1)
def url_requested(client,url):return any(r.get('url')==url for r in client.records)

class Monitor:
    def __init__(self,args):
        self.args=args;self.config=load(ROOT/'config.json',{});self.run_date=args.as_of or dt.datetime.now(UTC).date().isoformat()
        if self.run_date>dt.datetime.now(UTC).date().isoformat():raise ValueError('--as-of不能超过当前UTC日；本地日历日期不可代替UTC日界')
        self.cutoff=timestamp(self.run_date);self.yesterday=(dt.date.fromisoformat(self.run_date)-dt.timedelta(days=1)).isoformat()
        self.client=Client(ROOT,self.config.get('proxy'),args.offline,self.config.get('http_timeout',15))
        self.chain=Chain(self.client,self.config['rpc'],self.run_date,self.config['confirmations']);self.errors=[];self.facts=[];self.current_sources=[]
        self.state=load(ROOT/'state.json',{'days':{},'owners':{},'history_complete':False,'contracts':{},'rule_history':{}})
        self.tokens=load(ROOT/'data'/'tokens.json',[]);self.trades=load(ROOT/'data'/'trades.json',[])
    def gap(self,module,date,reason,url=None,blocks=None):
        self.errors.append(dict(module=module,date=date,reason=str(reason),url=url if url and url_requested(self.client,url) else None,blocks=blocks,rpc=self.chain.url))
    def fact(self,field,value,grade='E1',urls=None,raw=None):
        urls=urls or [];urls=[u for u in urls if url_requested(self.client,u)]
        self.facts.append(dict(field=field,value=value,evidence=grade,url=urls or None,read_utc=utc_now(),raw=raw or []))
    def checked_metadata(self,address,source_policy='exact'):
        meta,rec=source_metadata(self.client,address,allow_match=source_policy=='sourcify_match');self.current_sources.append(rec)
        return meta,rec
    def bootstrap(self):
        """Record only actual requests. A verified ERC20 is not a verified gate."""
        registry=self.config['registry'];address=registry['address']
        try:
            m,r=self.checked_metadata(address);names=[e['name'] for e in m['abi'] if e['type']=='event']
            self.fact('Registry/注册与mint事件',{'events':names,'registration_events':['Registered','AdminRegistered'],'mint_transfer':{'event':'Transfer','from':ZERO},'NameRegistered_present':'NameRegistered' in names},'E3',[r['url']],[r['raw_file']])
            self.state['registry_metadata_raw']=r['raw_file'];self.state['registry_verified']=True
        except Exception as e:self.gap('A',self.yesterday,'注册表源码/ABI校验未完成: '+str(e),registry['source_url'])
        # GitHub code search is unauthenticated read-only; 401/403 remains a gap.
        try:
            data,rec=self.client.json(self.config['discovery_url'],scope=self.run_date)
            candidates=load(ROOT/'candidates.json',[]);existing={c.get('url') for c in candidates}
            for item in data.get('items',[]):
                if item.get('html_url') not in existing:
                    candidate=dict(discovered_date=self.run_date,url=item.get('html_url'),evidence='E4',status='pending_source_and_gate_verification',repository=item.get('repository',{}).get('full_name'));candidates.append(candidate)
                    # Search matches are candidates, never automatic live adapters.
                    content_url=item.get('url')
                    if content_url and content_url.startswith('https://api.github.com/'):
                        try:
                            content,source_rec=self.client.json(content_url,scope=self.run_date)
                            text=base64.b64decode(content['content']).decode() if content.get('encoding')=='base64' else ''
                            discovered=[a for a in set(re.findall(r'0x[0-9a-fA-F]{40}\b',text)) if a.lower()!=address.lower()]
                            pending=self.config.setdefault('pending_discoveries',[]);seen={p['address'].lower() for p in pending}
                            for found in discovered:
                                if found.lower() not in seen:pending.append(dict(address=found,discovered_date=self.run_date,url=content_url,raw=source_rec['raw_file'],grade='E4',enabled=False,reason='代码搜索线索；未核验源码/Agent ID门禁/事件全集，不进入正式统计'))
                            dump(ROOT/'config.json',self.config)
                        except Exception as e:self.gap('发现',self.run_date,'匹配代码读取失败: '+str(e),content_url)
            dump(ROOT/'candidates.json',candidates)
            if data.get('incomplete_results'):self.gap('发现',self.run_date,'GitHub代码搜索声明incomplete_results',rec['url'])
        except Exception as e:self.gap('发现',self.run_date,str(e),self.config['discovery_url'])
        from discovery import refresh as refresh_sources
        self.errors.extend(refresh_sources(ROOT,self.config,self.client,self.run_date))
    def bounds(self,date,head):
        dep=self.config['registry']['deployment_block']
        a=self.chain.boundary(timestamp(date),dep,head);b=self.chain.boundary(timestamp(date)+86400,dep,head)-1
        if b>head-self.config['confirmations']:raise Unavailable('当日末区块尚未15确认；未入库')
        return a,b
    def first_record_audit(self):
        # A known observed record is independently requested, not accepted from the old snapshot.
        tx='0x64882fa2daca503fcfd54d5035b37812d300e6535b748f44aa16ff3bd3d3344e'
        try:
            receipt=self.chain.rpc('eth_getTransactionReceipt',[tx]);logs=[x for x in receipt['logs'] if x['address'].lower()==self.config['registry']['address'].lower() and x['topics'][0].lower() in [REGISTERED,ADMIN]]
            if not logs:raise Unavailable('已知交易不包含指定注册事件')
            n=int(receipt['blockNumber'],16);observed=day(self.chain.time(n));r=registration(logs[0])
            self.fact('A/首条注册记录（全历史前缀完整读取）' if self.state.get('pre_start_complete') else 'A/已核验最早观察记录（未证全历史）',dict(date=observed,block=n,tx=tx,registration=r),'E1',[self.chain.url],list(self.chain.sources))
            if observed!=self.config['claimed_agent_id_launch']:self.fact('A/上线日期冲突',{'status':'冲突','verified_observed_registration':observed,'third_party_claimed_launch':self.config['claimed_agent_id_launch'],'global_first_registration':self.state.get('global_first_registration'),'claimed_date_source':'用户提供第三方待核起点，具体原文链接U'},'E4',[],[])
            self.state['observed_first_registration']=observed
        except Exception as e:self.gap('A',self.yesterday,'第一记录核验: '+str(e),self.chain.url)
    def prefetch_day(self,bounds):
        """One same-RPC complete log universe; consumers filter without re-requesting."""
        addresses=[self.config['registry']['address']];topics={REGISTERED,ADMIN,TRANSFER}
        for p in self.config['platforms']+self.config['noncurve']:
            if not p.get('enabled'):continue
            meta,_=self.checked_metadata(p['address'],p.get('source_policy','exact'))
            names=set(p.get('events',{})) if 'events' in p else {p['activity_event']}|set(p.get('aux_events',[]))
            topics.update(event_topic(e) for e in meta['abi'] if e['type']=='event' and e['name'] in names);addresses.append(p['address'])
        a,b=bounds;rows,ok,errors=self.chain.logs(addresses,a,b,[sorted(topics)],self.config['rpc_log_chunk'],self.config['max_adaptive_depth'])
        if not hasattr(self.client,'log_views'):self.client.log_views=[]
        self.client.log_views.append(dict(rpc=self.chain.url,start=a,end=b,addresses={a.lower() for a in addresses},topics=topics,rows=rows,complete=ok,errors=errors,raw=list(dict.fromkeys(self.chain.sources))))
    def collect_identity(self,date,bounds):
        a,b=bounds;logs,complete,errs=self.chain.logs(self.config['registry']['address'],a,b,[[REGISTERED,ADMIN,TRANSFER]],self.config['rpc_log_chunk'],self.config['max_adaptive_depth'])
        for e in errs:self.gap('A',date,e['reason'],self.chain.url,[e['start'],e['end']])
        # BSC clients may include canonical blockTimestamp in each log. Preserve it;
        # do not make a separate HTTP request per mint when timestamp is already raw.
        for row in logs:
            n=int(row['blockNumber'],16)
            try:
                if row.get('blockTimestamp'):
                    self.chain.times[n]=int(row['blockTimestamp'],16)
                elif n not in self.chain.times:self.chain.time(n)
            except Exception as e:complete=False;self.gap('A',date,'注册事件区块时间缺失: '+str(e),self.chain.url,bounds);break
        # Confirm log timestamp/hash at both edges; logs are already restricted to
        # head-15. A mismatch invalidates the entire day instead of choosing a fork.
        for row in ([logs[0],logs[-1]] if logs else []):
            try:
                n=int(row['blockNumber'],16);block=self.chain.block(n)
                if block['hash'].lower()!=row['blockHash'].lower():raise Unavailable('确认区块hash不符（重组）')
                if row.get('blockTimestamp') and int(row['blockTimestamp'],16)!=int(block['timestamp'],16):raise Unavailable('日志时间戳与区块头冲突')
            except Exception as e:complete=False;self.gap('A',date,'区块边界校验: '+str(e),self.chain.url,bounds)
        previous=(dt.date.fromisoformat(date)-dt.timedelta(days=1)).isoformat();prior=self.state['days'].get(previous,{}).get('A',{}).get('cumulative_ids')
        prior_owners=self.state.get('owners') if self.state.get('owners_date')==previous and self.state.get('history_complete') else None
        # No genesis baseline is invented. Require a successful pre-start scan to establish it.
        if date==self.config['backfill_observed_start'] and self.state.get('pre_start_complete'):prior=0;prior_owners={}
        result,owners=identity_day(date,logs,complete,self.chain.times,prior,prior_owners)
        result.update(start_block=a,end_block=b,rpc=self.chain.url,complete=complete,read_utc=utc_now(),raw=list(dict.fromkeys(self.chain.sources)))
        if complete:
            regs=[]
            for row in dedup_logs(logs):
                r=registration(row)
                if r:r['timestamp']=self.chain.times[r['block']];regs.append(r)
            result['registrations']=regs;result['transfers']=dedup_logs([x for x in logs if x['topics'][0].lower()==TRANSFER])
            if regs and date==self.config['backfill_observed_start'] and self.state.get('pre_start_complete'):
                first=min(regs,key=lambda r:r['block']);self.state['global_first_registration']=dict(date=date,block=first['block'],tx=first['tx'],kind=first['kind'],timestamp=first['timestamp'],rpc=self.chain.url,proof='部署至日初完整前缀+首日完整日志',raw=result['raw'])
        if owners is not None:self.state.update(owners=owners,owners_date=date,history_complete=True)
        else:self.state['history_complete']=False
        return result
    def establish_baseline(self,head):
        start=self.config['backfill_observed_start'];a=self.config['registry']['deployment_block']
        try:
            b=self.chain.boundary(timestamp(start),a,head)-1
            logs,ok,errs=self.chain.logs(self.config['registry']['address'],a,b,[[REGISTERED,ADMIN,TRANSFER]],self.config['rpc_log_chunk'],0)
            if not ok:raise Unavailable(str(errs))
            # If older registrations exist, expand start rather than dropping them.
            regs=[r for x in logs if (r:=registration(x))]
            if regs:
                earliest=min(r['block'] for r in regs);found=day(self.chain.time(earliest));self.config['backfill_observed_start']=found
                # The complete deployment-to-old-start scan already proves that
                # no earlier registration exists before this first event.
                self.state['pre_start_complete']=True
                self.state['global_first_registration']=dict(date=found,block=earliest,rpc=self.chain.url,proof='完整部署起日志扫描',raw=list(dict.fromkeys(self.chain.sources)))
                dump(ROOT/'config.json',self.config)
            else:self.state['pre_start_complete']=True
        except Exception as e:self.state['pre_start_complete']=False;self.gap('A',start,'起点前历史不完整，累计与末区块持有地址不能对账: '+str(e),self.chain.url,[a,None])
    def platform(self,p,date,bounds):
        blank=platform_day([],[],date,False);blank.update(platform=p['id'],date=date,start_block=bounds[0] if bounds else None,end_block=bounds[1] if bounds else None,rpc=p.get('rpc',self.chain.url),complete=False,reason=p.get('reason'))
        if not p.get('enabled') or not bounds:
            self.gap('B/'+p['id'],date,p.get('reason','区块范围缺失'));return blank
        # An enabled adapter must name a verified contract, explicit event roles and field mapping.
        try:
            meta,rec=self.checked_metadata(p['address']);abi={e['name']:e for e in meta['abi'] if e['type']=='event'}
            required=p['events'];wanted=[abi[n] for n in required]
            rows,ok,errs=self.chain.logs(p.get('event_addresses',p['address']),*bounds,[[event_topic(e) for e in wanted]],self.config['rpc_log_chunk'],1)
            if not ok:raise Unavailable(str(errs))
            bytopic={event_topic(e):e for e in wanted};tokens=[];trades=[];log_sources=[]
            for record in self.client.records:
                request=record.get('json') or {}
                targets=request.get('params',[{}])[0].get('address',[]) if request.get('method')=='eth_getLogs' else []
                targets=targets if isinstance(targets,list) else [targets]
                if record['url']==self.chain.url and request.get('method')=='eth_getLogs' and p['address'].lower() in [a.lower() for a in targets]:
                    arg=request['params'][0];log_sources.append((int(arg['fromBlock'],16),int(arg['toBlock'],16),record['raw_file']))
            for row in dedup_logs(rows):
                e=bytopic[row['topics'][0].lower()];values=decode_event(row,e);rule=required[e['name']];kind=rule['role'];fields=rule['fields'];v={name:values[src] for name,src in fields.items()}
                ts=int(row['blockTimestamp'],16) if row.get('blockTimestamp') else self.chain.time(int(row['blockNumber'],16));v.update(timestamp=ts,tx=row['transactionHash'],block=int(row['blockNumber'],16),platform=p['id'],raw=rec['raw_file'])
                v['raw']=[rec['raw_file']]+list(dict.fromkeys(f for a,b,f in log_sources if a<=v['block']<=b))
                if kind=='create':v['created_ts']=ts;tokens.append(v)
                elif kind in ('buy','sell'):
                    v['side']=kind;v['bnb']=float(Decimal(v['amount'])/Decimal(10**18)) if p.get('quote_asset')=='native_bnb' else None;trades.append(v)
                elif kind=='graduate':
                    found=next((t for t in self.tokens+tokens if t.get('address','').lower()==v.get('address','').lower()),None)
                    if found:found['graduated_ts']=ts;found['graduation_price']=v.get('price');found['pair']=v.get('pair')
            self.tokens.extend(tokens);self.trades.extend(trades)
            all_tokens=list({(t['platform'],t['address'].lower()):t for t in self.tokens}.values());all_trades=list({(t['platform'],t['tx'],t.get('side')):t for t in self.trades}.values())
            self.tokens=all_tokens;self.trades=all_trades
            # Complete trade/address universe must be declared and verified, not inferred from factory events.
            all_complete=bool(p.get('complete_trade_universe'))
            result=platform_day(all_tokens,all_trades,date,all_complete)
            if not all_complete:
                result['new_launches']=len(tokens);result['unique_creators']=len({t.get('creator') for t in tokens if t.get('creator')})
            blank.update(result,complete=all_complete,launch_events_complete=True,source_grade='E1',raw=list(dict.fromkeys(self.chain.sources)),reason=None if all_complete else '创建事件完整；交易地址集合尚未证明完整')
            for hours in [24,72,168]:blank['cohort_'+str(hours)+'h']=cohort(all_tokens,date,hours,self.cutoff,all_complete)
            return blank
        except Exception as e:self.gap('B/'+p['id'],date,str(e),self.chain.url,bounds);blank['reason']=str(e);return blank
    def participation(self,date,platforms,noncurve,bounds):
        result=dict(date=date,active_id_wallets=None,activation_rate=None,top1_volume_share=None,top10_volume_share=None,top100_volume_share=None,multi_product_share=None,start_block=bounds[0] if bounds else None,end_block=bounds[1] if bounds else None,rpc=self.chain.url,coverage='全生态指标要求全部配置产品覆盖；已核产品下界另列')
        known={p['platform'] for p in platforms if p.get('complete')}|{p['project'] for p in noncurve if p.get('complete')}
        result.update(observed_active_id_wallets=None,observed_activation_lower_bound=None,observed_multi_product_numerator=None,observed_multi_product_denominator=None,observed_multi_product_share=None,observed_products=sorted(known),identity_unknown_addresses=None)
        if not bounds or not known:return result
        activities=[t for t in self.trades if day(t['timestamp'])==date and t['platform'] in known]
        activities += [t for p in noncurve if p['project'] in known for t in p.get('activities',[])]
        positions={r['holder'].lower():r for d,row in self.state['days'].items() if d<=date for r in row['A'].get('registrations',[])}
        eligible=set();unknown=set();products=collections.defaultdict(set);volumes=collections.defaultdict(Decimal)
        for t in activities:
            actor=t.get('actor','').lower();proved=t.get('identity_source_proven',False);registration=positions.get(actor)
            if not proved and registration:
                if registration['block']<t['block']:proved=True
                elif registration['block']==t['block']:
                    if registration.get('log_index') is not None and t.get('log_index') is not None:proved=registration['log_index']<t['log_index']
                    else:unknown.add(actor)
            if proved:
                eligible.add(actor);products[actor].add(t['platform'])
                amount=Decimal(t['curve_bnb_wei'])/10**18 if t.get('curve_bnb_wei') is not None else Decimal(str(t.get('bnb',0)))
                volumes[actor]+=amount
            elif registration is None and not self.state.get('history_complete'):unknown.add(actor)
        n=len(eligible);cum=self.state['days'].get(date,{}).get('A',{}).get('cumulative_ids');multi=sum(len(p)>=2 for p in products.values());shares=top_shares(volumes)
        result.update(observed_active_id_wallets=n,observed_activation_lower_bound=n/cum if cum else None,observed_multi_product_numerator=multi,observed_multi_product_denominator=n,observed_multi_product_share=multi/n if n else None,identity_unknown_addresses=len(unknown),raw=list(dict.fromkeys(p for item in platforms+noncurve for p in item.get('raw',[]))))
        if all(p.get('complete') for p in platforms+noncurve) and self.state.get('history_complete') and not unknown:
            result.update(active_id_wallets=n,activation_rate=n/cum if cum else None,top1_volume_share=shares['1'],top10_volume_share=shares['10'],top100_volume_share=shares['100'],multi_product_share=multi/n if n else None)
        return result
    def noncurve(self,p,date,bounds):
        result=dict(project=p['id'],date=date,mint_or_claim_transactions=None,participating_ids=None,cumulative_share=None,total_minted=None,supply_cap=8192 if p['id']=='HashDroids' else None,mints_last24h=None,mint_speed_per_hour=None,linear_sellout_date_e4=None,start_block=bounds[0] if bounds else None,end_block=bounds[1] if bounds else None,rpc=self.chain.url,complete=False)
        if not p.get('enabled') or not bounds:self.gap('E/'+p['id'],date,p.get('reason','区块范围缺失'));return result
        try:
            meta,rec=self.checked_metadata(p['address'],p.get('source_policy','exact'));event=next(a for a in meta['abi'] if a['type']=='event' and a['name']==p['activity_event'])
            auxiliary=[a for a in meta['abi'] if a['type']=='event' and a['name'] in p.get('aux_events',[])]
            topics=[[event_topic(a) for a in [event]+auxiliary]] if auxiliary else [event_topic(event)]
            rows,ok,errs=self.chain.logs(p['address'],*bounds,topics,self.config['rpc_log_chunk'],1)
            if not ok:raise Unavailable(str(errs))
            ids=set();txs=set();activities=[];mint_records=[];log_sources=[]
            for record in self.client.records:
                request=record.get('json') or {}
                targets=request.get('params',[{}])[0].get('address',[]) if request.get('method')=='eth_getLogs' else []
                targets=targets if isinstance(targets,list) else [targets]
                if record['url']==self.chain.url and request.get('method')=='eth_getLogs' and p['address'].lower() in [a.lower() for a in targets]:
                    arg=request['params'][0];log_sources.append((int(arg['fromBlock'],16),int(arg['toBlock'],16),record['raw_file']))
            # HashDroids' exact-match source has an immutable registry and its
            # sole mine path checks msg.sender's ID before emitting Mined.
            # This proves identity at execution, without unavailable archive state.
            source_proven=False
            if p['id']=='HashDroids':
                source='\n'.join(s.get('content','') for s in meta['sources'].values())
                if 'IAgentIdRegistry public immutable agentRegistry' not in source or 'if (agentRegistry.balanceOf(msg.sender) == 0) revert NotVerifiedAgent();' not in source:raise Unavailable('HashDroids源码门禁假设变化')
                pointer=self.chain.rpc('eth_call',[{'to':p['address'],'data':selector('agentRegistry()')},'latest'])
                if ('0x'+pointer[-40:]).lower()!=self.config['registry']['address'].lower():raise Unavailable('HashDroids不可变Registry指针不匹配')
                source_proven=True
            if p['id']=='Ptah-POA':
                source='\n'.join(s.get('content','') for s in meta['sources'].values())
                for required in ['IHandleRegistry public immutable handleRegistry','bool public immutable requireHandle','string memory handle = handleRegistry.handleOf(account);','if (bytes(handle).length == 0) revert NoHandle(account);','emit Minted(msg.sender, h, tokenId, s, v, ill, seed);']:
                    if required not in source:raise Unavailable('Ptah POA已审阅门禁路径改变')
                pointer=self.chain.rpc('eth_call',[{'to':p['address'],'data':selector('handleRegistry()')},'latest'])
                required=self.chain.rpc('eth_call',[{'to':p['address'],'data':selector('requireHandle()')},'latest'])
                if ('0x'+pointer[-40:]).lower()!=self.config['registry']['address'].lower() or int(required,16)!=1:raise Unavailable('Ptah POA实际Registry/requireHandle不符合门禁要求')
                source_proven=True
                token=self.chain.rpc('eth_call',[{'to':p['address'],'data':selector('usdt()')},'latest']);result['paid_token_contract']='0x'+token[-40:]
                aux_by_topic={event_topic(a):a for a in auxiliary};aux_rows=[]
                for row in dedup_logs(rows):
                    abi=aux_by_topic.get(row['topics'][0].lower())
                    if abi:
                        aux_rows.append(dict(event=abi['name'],values=decode_event(row,abi),block=int(row['blockNumber'],16),log_index=int(row['logIndex'],16),tx=row['transactionHash'],date=date,rpc=self.chain.url,raw=list(dict.fromkeys(f for a,b,f in log_sources if a<=int(row['blockNumber'],16)<=b))))
                old=load(ROOT/'data'/'ptah_poa_parameters.json',[]);dump(ROOT/'data'/'ptah_poa_parameters.json',[r for r in old if r['date']!=date]+aux_rows)
            for row in dedup_logs(rows):
                if row['topics'][0].lower()!=event_topic(event):continue
                value=decode_event(row,event);actor=value[p['actor_field']];block=int(row['blockNumber'],16)
                if source_proven or self.chain.call_uint(self.config['registry']['address'],'balanceOf(address)',block,actor[2:].zfill(64))>0:
                    ids.add(actor);txs.add(row['transactionHash']);ts=int(row['blockTimestamp'],16) if row.get('blockTimestamp') else self.chain.time(block)
                    activities.append(dict(actor=actor,block=block,timestamp=ts,platform=p['id'],bnb=0,identity_source_proven=source_proven))
                    if p['id'] in ['HashDroids','Ptah-POA']:mint_records.append(dict(token_id=value['tokenId'],timestamp=ts,block=block,tx=row['transactionHash'],miner=actor,date=date,rpc=self.chain.url,raw=list(dict.fromkeys(f for a,b,f in log_sources if a<=block<=b))))
            cum=self.state['days'].get(date,{}).get('A',{}).get('cumulative_ids')
            result.update(mint_or_claim_transactions=len(txs),participating_ids=len(ids),cumulative_share=len(ids)/cum if cum else None,complete=True,activities=activities,raw=list(dict.fromkeys(self.chain.sources))+[rec['raw_file']])
            if p['id']=='HashDroids':
                old=load(ROOT/'data'/'hashdroids_mints.json',[]);old=[r for r in old if r['date']!=date];dump(ROOT/'data'/'hashdroids_mints.json',old+mint_records)
                total=max(r['token_id'] for r in mint_records) if mint_records else self.chain.call_uint(p['address'],'totalMinted()',bounds[1]);result.update(total_minted=total,mints_last24h=len(rows),mint_speed_per_hour=len(rows)/24)
                if len(rows)>0:result['linear_sellout_date_e4']=dt.datetime.fromtimestamp(timestamp(date)+86400+(8192-total)*86400/len(rows),UTC).date().isoformat()
            if p['id']=='Ptah-POA':
                old=load(ROOT/'data'/'ptah_poa_mints.json',[]);dump(ROOT/'data'/'ptah_poa_mints.json',[r for r in old if r['date']!=date]+mint_records)
                if mint_records:result['total_minted']=max(r['token_id'] for r in mint_records)
                result['source_match_type']={'creation':meta['creationMatch'],'runtime':meta['runtimeMatch']}
            return result
        except Exception as e:self.gap('E/'+p['id'],date,str(e),self.chain.url,bounds);return result
    def bnb_price(self,date):
        params=urllib.parse.urlencode({'symbol':'BNBUSDT','interval':'1d','startTime':timestamp(date)*1000,'endTime':(timestamp(date)+86400)*1000-1,'limit':1});url=self.config['bnb_klines_url']+'?'+params
        try:
            arr,rec=self.client.json(url)
            if len(arr)!=1 or arr[0][0]!=timestamp(date)*1000 or arr[0][6]>=self.cutoff*1000:raise Unavailable('BNB日K缺失或未闭合')
            return dict(date=date,close_usdt=arr[0][4],grade='E3',url=url,raw=rec['raw_file'])
        except Exception as e:self.gap('BNB价格',date,str(e),url);return dict(date=date,close_usdt=None,grade='E3',url=url if url_requested(self.client,url) else None)
    def snapshots(self):
        results=[]
        for src in self.config['snapshot_sources']:
            try:
                url=src['url'];items=[];seen=set();complete=False
                for page in range(100):
                    data,rec=self.client.json(url,scope=self.run_date)
                    rows=data if isinstance(data,list) else data.get('items',[])
                    for t in rows:
                        a=t.get('address','').lower()
                        if a and a not in seen:items.append(t);seen.add(a)
                    if isinstance(data,list) or not data.get('hasMore'):complete=True;break
                    nxt=data.get('nextOffset')
                    if nxt is None:raise Unavailable('hasMore但nextOffset缺失')
                    url=src['url'].split('?')[0]+'?offset='+str(nxt)+'&limit=50'
                results.append(dict(source=src['id'],items=items,index_pages_complete=complete,grade='E3',read_utc=rec['read_utc'],date_status='未完/当前快照；不进入完整UTC日日序列',url=src['url'],raw=[r['raw_file'] for r in self.client.records if r['url'].split('?')[0]==src['url'].split('?')[0]]))
            except Exception as e:self.gap('B/D来源快照',self.run_date,src['id']+': '+str(e),src['url'])
        dump(ROOT/'data'/'snapshots.json',results);return results
    def outcomes(self):
        rows=[];observations=load(ROOT/'data'/'price_observations.json',{})
        for t in self.tokens:
            created=t.get('created_ts');age=(self.cutoff-created)/3600 if created is not None else None
            status='已毕业' if t.get('graduated_ts') is not None else ('未毕业（创建时间U）' if age is None else ('未毕业' if age>=72 else '未毕业/未满72h'))
            d=dict(platform=t['platform'],address=t['address'],created_date=day(created) if created is not None else None,graduated_date=day(t['graduated_ts']) if t.get('graduated_ts') is not None else None,graduation_price=t.get('graduation_price'),price_currency=t.get('price_currency','USD'),dex_seed_price_bnb=t.get('dex_seed_price_bnb'),first_dex_open=None,D0=None,D1=None,D3=None,D7=None,agent_id_holders=None,token_holder_addresses=None,top10_holder_share=None,status=status,source='GeckoTerminal',url=None)
            adapter=next((p for p in self.config['platforms'] if p['id']==t['platform']),{})
            d.update(url=self.chain.url,raw=t.get('raw',[]),source='已验证创建事件；价格接口尚未取得',graduation_evidence_url=self.chain.url,graduation_raw=t.get('graduation_raw'),tax_rate=t.get('token_transfer_tax_rate'),curve_fee_bps=t.get('curve_fee_bps'))
            if not t.get('graduated_ts') and not (adapter.get('complete_trade_universe') or t.get('graduation_status_complete')):
                d.update(status=None,status_reason='毕业事件全集未完整读取，不能据缺失事件断言未毕业',created_age_hours=age)
            if not t.get('pair'):
                self.gap('D',self.yesterday,t['address']+' 未核实唯一首个DEX池，不猜池、不跨池拼接');rows.append(d);continue
            currency='token' if d['price_currency']=='BNB' else 'usd'
            base=self.config['gecko_base']+'/networks/bsc/pools/'+t['pair'];url=base+'/ohlcv/day?aggregate=1&limit=1000&currency='+currency+'&token='+t['address']+'&before_timestamp='+str(self.cutoff)
            try:
                payload,rec=self.client.json(url,scope=self.yesterday);d.update(url=url,raw=rec['raw_file']);prices=collections.defaultdict(list)
                if currency=='token' and payload.get('meta',{}).get('quote',{}).get('address','').lower()!='0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c':raise Unavailable('GeckoTerminal报价资产不是WBNB；不混合BNB与USD价格')
                for candle in payload['data']['attributes']['ohlcv_list']:
                    if candle[0]+86400<=self.cutoff and candle[5]>0:prices[day(candle[0])].append(candle[4])
                observation_key=t['pair'].lower()+'/'+t['address'].lower()+'/'+d['price_currency']
                observed=observations.setdefault(observation_key,{})
                for price_day,values in prices.items():
                    bucket=observed.setdefault(price_day,[])
                    for value in values:
                        if not any(x['raw']==rec['raw_file'] and str(x['value'])==str(value) for x in bucket):bucket.append(dict(value=value,raw=rec['raw_file'],url=url,read_utc=rec['read_utc']))
                d['raw']=sorted({rec['raw_file']}|{x['raw'] for bucket in observed.values() for x in bucket})
                if d['graduated_date']:
                    for n in [0,1,3,7]:
                        target=(dt.date.fromisoformat(d['graduated_date'])+dt.timedelta(days=n)).isoformat();d['D'+str(n)]=resolve_price([x['value'] for x in observed.get(target,[])])
                        if len({str(x['value']) for x in observed.get(target,[])})>1:self.gap('D',target,t['address']+' 同池同报价资产日收盘冲突，价格U',url)
                # Day OHLC open is NOT proof of the first ever DEX execution. Remains U.
                valid=[float(v) for v in [d['D0'],d['D1'],d['D3'],d['D7']] if v is not None]
                if d['graduation_price'] and valid and valid[-1]/float(d['graduation_price'])<0.1:d['status']='归零（相对毕业价下跌>90%，用户标签）'
            except Exception as e:self.gap('D',self.yesterday,str(e),url)
            rows.append(d)
        # Do not omit known ungraduated source-index candidates. Keep source segregation.
        for snap in load(ROOT/'data'/'snapshots.json',[]):
            for t in snap['items']:
                c=t.get('curve',t);created=t.get('createdAt');rows.append(dict(platform=snap['source'],address=t['address'],created_at=created,status='已毕业（项目索引快照）' if c.get('graduated') else '未毕业（项目索引快照，72h年龄待核）',graduation_price=None,first_dex_open=None,D0=None,D1=None,D3=None,D7=None,token_holder_addresses=None,top10_holder_share=None,source='项目索引快照/门禁待核',url=snap['url'],raw=snap['raw'],not_daily=True))
        dump(ROOT/'data'/'price_observations.json',observations)
        dump(ROOT/'data'/'outcomes.json',rows)
        grouped=collections.defaultdict(list)
        for t in rows:
            if not t.get('created_date') or t.get('not_daily'):continue
            date=dt.date.fromisoformat(t['created_date']);week=(date-dt.timedelta(days=date.weekday())).isoformat();grouped[(t['platform'],week)].append(t)
        stats=[]
        for (platform,week),tokens in grouped.items():
            row=dict(platform=platform,cohort_week=week)
            for n in [1,7]:
                vals=[float(t['D'+str(n)])/float(t['graduation_price']) for t in tokens if t.get('D'+str(n)) is not None and t.get('graduation_price')]
                row['D'+str(n)+'_n']=len(vals);row['D'+str(n)+'_median']=statistics.median(vals) if len(vals)>=5 else None
            stats.append(row)
        dump(ROOT/'data'/'outcome_weekly.json',stats)
    def rules(self):
        changes=[];snapshots=load(ROOT/'data'/'rule_snapshots.json',[])
        for item in self.config['rules_pages']:
            try:
                rec=self.client.request(item['url'],scope=self.run_date);body=rec['body'];digest=hashlib.sha256(body.encode()).hexdigest();prev=self.state['rule_history'].get(item['id'])
                plain=re.sub(r'<script\b.*?</script>|<style\b.*?</style>','',body,flags=re.S|re.I);plain=re.sub('<[^>]+>',' ',plain);plain=re.sub(r'\s+',' ',plain).strip()
                change=None
                if prev and prev['sha256']!=digest:
                    matcher=difflib.SequenceMatcher(None,prev.get('text',''),plain);fragments=[]
                    for tag,i,j,a,b in matcher.get_opcodes():
                        if tag!='equal':fragments.append('旧:'+prev.get('text','')[i:j]+' 新:'+plain[a:b])
                    snippet=(' | '.join(fragments) or '原文哈希变化；提取正文无文本差异，不能据此认定规则变更')[:200];keywords=[k for k in ['每账号','每钱包','KYC','费用','税率','毕业','限额','wallet','account','fee','tax','graduat','limit'] if k.lower() in snippet.lower()]
                    change=dict(change_date=self.run_date,url=item['url'],snippet=snippet,keywords=keywords,old_sha256=prev['sha256'],sha256=digest,raw=rec['raw_file']);changes.append(change)
                self.state['rule_history'][item['id']]=dict(date=self.run_date,sha256=digest,text=plain,raw=rec['raw_file'],url=item['url'])
                previous_observation=next((r for r in snapshots if r['date']==self.run_date and r['url']==item['url']),{})
                snapshots.append(dict(date=self.run_date,id=item['id'],url=item['url'],sha256=digest,read_utc=rec['read_utc'],raw=rec['raw_file'],comparison_available=bool((prev and prev['date']<self.run_date) or previous_observation.get('comparison_available')),grade=item['grade']))
            except Exception as e:self.gap('F',self.run_date,item['id']+': '+str(e),item['url'])
        old=load(ROOT/'data'/'rule_changes.json',[]);dump(ROOT/'data'/'rule_changes.json',list({(r['change_date'],r['url'],r['sha256']):r for r in old+changes}.values()))
        dump(ROOT/'data'/'rule_snapshots.json',list({(r['date'],r['url']):r for r in snapshots}.values()))
    def audit(self):
        seq=[r['A'] for _,r in sorted(self.state['days'].items())];complete=bool(seq) and self.state.get('pre_start_complete') and all(r.get('complete') and r.get('cumulative_ids') is not None and r.get('agent_id_holders') is not None for r in seq)
        sums=sum(r['daily_new_ids'] for r in seq) if complete else None;cum=seq[-1].get('cumulative_ids') if seq else None;owners=len(set(self.state.get('owners',{}).values())) if complete else None
        delta=abs(sums-owners)/max(sums,1) if complete else None;sample=[]
        if complete:
            for token,owner in sorted(self.state['owners'].items())[:10]:
                try:raw=self.chain.rpc('eth_call',[dict(to=self.config['registry']['address'],data=selector('ownerOf(uint256)')+token[2:]),hex(seq[-1]['end_block'])]);sample.append(dict(token=token,expected=owner,actual=address_topic(raw),matches=address_topic(raw)==owner))
                except Exception as e:sample.append(dict(token=token,error=str(e),matches=None))
        ok=bool(complete and sums==cum==owners and all(x.get('matches') for x in sample))
        report=dict(status='PASS' if ok else 'U/NOT_RECONCILED',sum_daily_new_ids=sums,cumulative_ids=cum,unique_transfer_holders=owners,difference_ratio=delta,threshold_exceeded=delta>.005 if delta is not None else None,ownerOf_samples=sample,reason=None if ok else '全历史覆盖/累计基线/ownerOf样本不完整；未改参数凑数')
        dump(ROOT/'data'/'reconciliation.json',report)
    def run(self):
        if self.args.report:
            from report import build
            build(ROOT,self.config);return
        self.bootstrap();head=None
        if self.client.proxy:
            try:head=self.chain.head()
            except Exception as e:self.gap('区块',self.yesterday,str(e),self.chain.url)
        if self.args.backfill and head is not None:self.establish_baseline(head);self.first_record_audit()
        span=list(dates(self.config['backfill_observed_start'],self.yesterday)) if self.args.backfill else [self.yesterday]
        for date in span:
            if date in self.state['days'] and not self.args.reprocess:continue
            bounds=None
            if head is not None:
                try:bounds=self.bounds(date,head)
                except Exception as e:self.gap('区块',date,str(e),self.chain.url)
            else:self.gap('区块',date,'代理待确认/离线/链头不可读；区块范围U')
            if bounds:
                if self.config.get('prefetch_daily_logs'):self.prefetch_day(bounds)
                a=self.collect_identity(date,bounds)
            else:a=dict(date=date,daily_new_ids=None,cumulative_ids=None,agent_id_holders=None,busiest_hour_share=None,sequence_name_share_e4=None,start_block=None,end_block=None,rpc=self.chain.url,complete=False,read_utc=utc_now(),raw=[])
            past=[r['A'].get('daily_new_ids') for d,r in sorted(self.state['days'].items()) if d<date][-6:]
            a['ma7_new_ids']=mean_complete(past+[a['daily_new_ids']]);self.state['days'][date]={'A':a}
            ps=[self.platform(p,date,bounds) for p in self.config['platforms']];es=[self.noncurve(p,date,bounds) for p in self.config['noncurve']]
            self.state['days'][date].update(B=ps,E=es,C=self.participation(date,ps,es,bounds),bnb_price=self.bnb_price(date))
            dump(ROOT/'state.json',self.state);print('saved closed-calendar UTC date',date,'A',a['daily_new_ids'],'blocks',bounds,flush=True)
        if self.config.get('agentpad_child_adapter'):
            try:
                from agentpad import collect as collect_agentpad
                pad=collect_agentpad(ROOT,self.config,self.client,self.run_date,span,self.state)
                for row in pad['rows']:
                    rows=self.state['days'][row['date']]['B'];self.state['days'][row['date']]['B']=[row if r['platform']=='AgentPad' else r for r in rows]
                admitted=[t for t in pad['tokens'] if (t.get('created_ts') is not None and t['created_ts']<self.cutoff) or t.get('first_observed_ts') is not None]
                self.tokens=[t for t in self.tokens if t['platform']!='AgentPad']+admitted
                self.trades=[t for t in self.trades if t['platform']!='AgentPad']+pad['trades'];self.errors.extend(pad['errors'])
                for date in span:self.state['days'][date]['C']=self.participation(date,self.state['days'][date]['B'],self.state['days'][date]['E'],(self.state['days'][date]['A'].get('start_block'),self.state['days'][date]['A'].get('end_block')) if self.state['days'][date]['A'].get('start_block') is not None else None)
            except Exception as e:
                for date in span:self.gap('B/AgentPad-children',date,str(e),self.chain.url)
        self.snapshots();self.outcomes();self.rules();self.audit()
        from free_mints import collect as collect_mints
        _,g_errors=collect_mints(ROOT,self.config,span,self.client,self.run_date);self.errors.extend(g_errors)
        dump(ROOT/'data'/'tokens.json',self.tokens);dump(ROOT/'data'/'trades.json',self.trades)
        existing=load(ROOT/'data'/'gaps.json',[])
        if self.args.reprocess:
            # Keep old attempt history, while current gaps reflect the new full
            # recomputation rather than stale offline failures that are resolved.
            history=load(ROOT/'data'/'gap_attempt_history.json',[])
            dump(ROOT/'data'/'gap_attempt_history.json',list({(e['module'],e['date'],e['reason']):e for e in history+existing}.values()))
            existing=[e for e in existing if e['date'] not in span]
        dump(ROOT/'data'/'gaps.json',list({(e['module'],e['date'],e['reason']):e for e in existing+self.errors}.values()))
        dump(ROOT/'data'/'run_facts.json',self.facts);dump(ROOT/'state.json',self.state)
        dump(ROOT/'last_run.json',dict(run_date=self.run_date,processed_dates=span,proxy=self.client.proxy,source_rpc=self.chain.url,mode='backfill' if self.args.backfill else 'daily',offline=self.args.offline,reprocess=self.args.reprocess,network_requests=self.client.request_count,cache_hits=self.client.cache_hits,errors=len(self.errors),data_gap_count=len(self.errors),fatal_errors=0,finished_utc=utc_now(),status='incomplete' if self.errors else 'collected'))
        from report import build
        build(ROOT,self.config)

def main():
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--backfill',action='store_true');mode.add_argument('--daily',action='store_true');mode.add_argument('--report',action='store_true')
    p.add_argument('--offline',action='store_true');p.add_argument('--as-of',help='UTC date; defaults to current UTC date');p.add_argument('--reprocess',action='store_true',help='recompute existing days from cache; never bypass proxy or raw cache')
    args=p.parse_args()
    try:Monitor(args).run()
    except Exception:
        (ROOT/'error.log').write_text(traceback.format_exc());raise

if __name__=='__main__':main()
