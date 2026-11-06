"""Module G. Candidate discovery is separate from verified gate coverage."""
import argparse
import datetime as dt
import json
from pathlib import Path
import statistics
from decimal import Decimal
from transport import Client,Unavailable,utc_now
from eth import Chain,source_metadata,selector
from core import timestamp,resolve_price

def load(p,default):return json.loads(p.read_text()) if p.exists() else default
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2))

def check_owner(row,rule,chain,block,errors):
    fields=['owner_can_change_price','owner_can_pause']
    if not any(rule.get(f) is True for f in fields):return
    try:
        owner=chain.rpc('eth_call',[{'to':row['contract'],'data':selector('owner()')},hex(block)])
        if len(owner)!=66:raise Unavailable('owner()响应形状异常')
        row['owner_address']='0x'+owner[-40:];active=int(owner,16)!=0
        for f in fields:
            if rule.get(f) is not None:row[f]=bool(rule[f] and active)
    except Exception as e:
        for f in fields:
            if rule.get(f) is True:row[f]=None
        row['owner_state_reason']=str(e)
        errors.append({'module':'G/'+row['project']+'/owner','date':row['date'],'reason':str(e),'url':chain.url,'rpc':chain.url,'blocks':[row['start_block'],row['end_block']]})
    row['raw']+=chain.sources

def collect(root,config,dates,client=None,scope=None):
    root=Path(root);scope=scope or dt.datetime.now(dt.timezone.utc).date().isoformat();client=client or Client(root,config.get('proxy'))
    candidates=load(root/'mint_candidates.json',[]);overrides=load(root/'mint_verified_rules.json',{})
    source_checks={r['project']:r for r in load(root/'data'/'mint_source_checks.json',[])}
    calendar=load(root/'state.json',{}).get('days',{})
    state=load(root/'data'/'mint_registry.json',[]);index={(r['date'],r['project']):r for r in state};errors=[]
    chain=Chain(client,config.get('mint_rpc',config.get('block_rpc',config['rpc'])),scope,config['confirmations']);head=None
    if config.get('proxy'):
        try:head=chain.head()
        except Exception as e:errors.append({'module':'G','date':scope,'reason':str(e)})
    for date in dates:
        for p in candidates:
            rule=overrides.get(p['id'],{});a=rule.get('address',p.get('address'))
            r=dict(date=date,project=p['id'],name=p['name'],contract=a,total_supply=None,minted=None,price_tiers=None,source_verified=None,gate_verified=False,owner_can_change_price=None,owner_can_pause=None,requires_approval=None,requires_typedData=None,first_secondary_listing_utc=None,floor_D0=None,floor_D1=None,floor_D3=None,floor_D7=None,trades_today=None,changed_free_to_paid=None,floor_drawdown_gt90=None,discovery_date=p.get('discovery_date'),discovery_method=p.get('discovery_method'),start_block=None,end_block=None,rpc=chain.url,grade='E4',url=p.get('origin_url'),raw=[],read_utc=utc_now(),reason=None)
            if not a or not rule:
                check=source_checks.get(p['id'],{})
                if check.get('source_verified'):
                    r.update(source_verified=True,source_verified_read_date=check['read_utc'][:10],url=check['url'],raw=check.get('raw',[]),grade='E3')
                    if check.get('raw'):
                        envelope=load(root/check['raw'][0],{});metadata=json.loads(envelope.get('body','{}'))
                        r['source_match_type']={'creation':metadata.get('creationMatch'),'runtime':metadata.get('runtimeMatch')}
                r['reason']='候选尚未逐项完成源码、实际Registry指针、价格及市场核验；不是已确认免费项目'
                if check.get('url'):r['url']=check['url']
                if check.get('reason'):r['reason']='源码读取：'+check['reason']+'；'+r['reason']
                errors.append({'module':'G/'+p['id'],'date':date,'reason':r['reason'],'url':r['url'],'rpc':chain.url,'blocks':[None,None]})
                index[(date,p['id'])]=r;continue
            try:
                meta,rec=source_metadata(client,a,allow_match=rule.get('source_policy')=='sourcify_match');r.update(source_verified=True,source_verified_read_date=rec['read_utc'][:10],source_match_type={'creation':meta['creationMatch'],'runtime':meta['runtimeMatch']},grade='E3',url=rec['url'],raw=[rec['raw_file']])
                for field in ['owner_can_change_price','owner_can_pause','requires_approval','requires_typedData']:r[field]=rule.get(field)
                if rule.get('from_complete_E'):
                    project=rule.get('from_complete_E_project','HashDroids')
                    e=next((e for e in load(root/'state.json',{}).get('days',{}).get(date,{}).get('E',[]) if e['project']==project),{})
                    if not e.get('complete') or e.get('total_minted') is None:raise Unavailable(project+'完整E日志/日末总数未取得')
                    count=e['total_minted'];r.update(gate_verified=True,total_supply=8192,minted=count,start_block=e['start_block'],end_block=e['end_block'],rpc=e['rpc'])
                    r['raw']+=e.get('raw',[])
                    r['price_tiers']={'free_quota':0,'paid_quota':8192,'epoch_size':256,'next_price_bnb':str(Decimal('.0025')+min(count//256,31)*Decimal('.0002')),'scope':'总量未满时的下一份报价；MINT_PRICE+epoch×PRICE_STEP；满额后不可铸造'}
                    if project=='Ptah-POA':
                        parameters=load(root/'data'/'ptah_poa_parameters.json',[])
                        prices=[x for x in parameters if x['event']=='SeriesPriceSet' and x['date']<=date]
                        last=max(prices,key=lambda x:(x['block'],x['log_index'])) if prices else None
                        r['total_supply']=None;r['soulbound']=True
                        r['price_tiers']={'free_method':'mint()','free_native_value':0,'paid_method':'mintSeries(uint16,uint8)','paid_price_atomic':last['values']['price'] if last else None,'paid_currency_contract':e.get('paid_token_contract'),'fixed_supply_cap':None,'scope':'随机铸造免费；选系列为另一个可收费方法；源码无固定总量上限，免费和付费档的份数未预设；未将付费分支误记为免费转付费'}
                        r['approval_scope']='mint()无需授权；mintSeries/changeSeries在seriesPrice>0时需要支付代币授权'
                        ordered=sorted(prices,key=lambda x:(x['block'],x['log_index']))
                        r['changed_free_to_paid']=any(left['values']['price']==0 and right['values']['price']>0 and right['date']==date for left,right in zip(ordered,ordered[1:]))
                        r['price_tiers']['transition_scope']='mintSeries收费分支；随机mint仍为0，两个方法分开记录'
                    r['reason']='地板价、首个二级挂牌和二级成交笔数U：未取得可验证市场接口；合约mint路径无额外签名，不证明前端行为'
                    if project=='Ptah-POA':r['reason']='固定总量U：源码无固定总量上限；免费mint无授权/typedData，收费分支另列；灵魂绑定，转账/烧毁/授权均revert，不能常规挂单；二级挂牌、地板和成交U。Sourcify为match而非exact_match；BscScan验证状态仍U（被拦）'
                    check_owner(r,rule,chain,e['end_block'],errors)
                    errors.append({'module':'G/'+p['id'],'date':date,'reason':r['reason'],'url':r['url'],'rpc':r['rpc'],'blocks':[r['start_block'],r['end_block']]})
                    index[(date,p['id'])]=r;continue
                if head is None:raise Unavailable('链头U')
                known=calendar.get(date,{}).get('A',{})
                if known.get('rpc')==chain.url and known.get('start_block') is not None and known.get('end_block') is not None:
                    start,b=known['start_block'],known['end_block']
                else:
                    b=chain.boundary(timestamp(date)+86400,int(meta['deployment']['blockNumber']),head)-1
                    start=chain.boundary(timestamp(date),int(meta['deployment']['blockNumber']),head)
                if b>head-config['confirmations']:raise Unavailable('未满15确认')
                r.update(start_block=start,end_block=b)
                if b<int(meta['deployment']['blockNumber']):raise Unavailable('本次验证的合约部署日在该日之后；历史日末参数U，不将当前参数回写过去')
                pointer=chain.rpc('eth_call',[{'to':a,'data':selector(rule['registry_getter'])},hex(b)])
                registry='0x'+pointer[-40:]
                if registry.lower()!=config['registry']['address'].lower():raise Unavailable('实际Registry指针不匹配')
                if not rule.get('source_gate_reviewed'):raise Unavailable('mint门禁路径未完成源码审阅')
                r['gate_verified']=True;r['total_supply']=chain.call_uint(a,rule.get('cap_getter','MAX_SUPPLY()'),b);r['minted']=chain.call_uint(a,rule.get('minted_getter','totalSupply()'),b)
                price=chain.call_uint(a,rule.get('price_getter','PRICE()'),b)
                r['price_tiers']={'free':'有' if price==0 else '无（该已核实固定档）','paid_bnb':str(Decimal(price)/10**18),'scope':'当日末区块；不把单档套到多档合约'}
                for field in ['owner_can_change_price','owner_can_pause','requires_approval','requires_typedData']:r[field]=rule.get(field)
                check_owner(r,rule,chain,b,errors)
                # No market is inferred from transfer logs: first listing != first sale != transfer.
                market=rule.get('market_daily_url')
                if market:
                    data,mrec=client.json(market.format(date=date));r['raw'].append(mrec['raw_file'])
                    r['first_secondary_listing_utc']=data.get('first_listing_utc');r['trades_today']=data.get('transaction_count')
                    for n in [0,1,3,7]:r['floor_D'+str(n)]=resolve_price(data.get('floor_D'+str(n),[]))
                previous=[x for (d,i),x in index.items() if i==p['id'] and d<date];prev=max(previous,key=lambda x:x['date']) if previous else None
                if prev and prev.get('price_tiers'):
                    prevprice=prev['price_tiers'].get('paid_bnb')
                    if prevprice is not None:r['changed_free_to_paid']=Decimal(prevprice)==0 and price>0
                if r['floor_D0'] is not None and r['floor_D7'] is not None and Decimal(r['floor_D0'])>0:r['floor_drawdown_gt90']=Decimal(r['floor_D7'])/Decimal(r['floor_D0'])<Decimal('.1')
                r['raw']+=chain.sources
            except Exception as e:r['reason']=str(e);errors.append({'module':'G/'+p['id'],'date':date,'reason':str(e),'url':r['url'],'rpc':chain.url,'blocks':[r['start_block'],r['end_block']]})
            index[(date,p['id'])]=r
    rows=list(index.values());dump(root/'data'/'mint_registry.json',rows)
    summaries=[]
    for date in sorted({r['date'] for r in rows}):
        allrows=[r for r in rows if r['date']==date];verified=[r for r in allrows if r['gate_verified']];valid=[r for r in verified if r.get('floor_D0') is not None];ratios=[float(r['floor_D7'])/float(r['floor_D0']) for r in verified if r.get('floor_D7') is not None and r.get('floor_D0') and float(r['floor_D0'])>0]
        summaries.append(dict(date=date,candidate_count=len(allrows),confirmed_gate_denominator=len(verified),floor_available_numerator=len(valid) if verified else None,floor_available_share=len(valid)/len(verified) if verified else None,ecosystem_project_denominator=None,ecosystem_floor_available_share=None,D7_D0_sample_n=len(ratios),D7_D0_median=statistics.median(ratios) if len(ratios)>=5 else None,denominator_scope='范围为已核门禁项目；其他未核候选单列，生态全集未知',U_floor_candidates=sum(r['floor_D0'] is None for r in allrows)))
    dump(root/'data'/'mint_summary.json',summaries);return rows,errors

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--date',required=True);a=p.parse_args();root=Path(__file__).parent;c=load(root/'config.json',{});collect(root,c,[a.date])
