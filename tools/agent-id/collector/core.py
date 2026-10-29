"""Pure reducers. None is U. Source completeness is an input, never inferred."""
import collections
import datetime as dt
import re
from decimal import Decimal

UTC=dt.timezone.utc
REGISTERED='0x663d34a86c6277aafbd5c6912c96cc5df091e6702ea3ea91b8f378adcbd8a5e5'
ADMIN='0x30eec1fe44831cb1c3184c97424b7cc3ce97a1140c19f9e7bcb591019d215976'
TRANSFER='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
ZERO='0x'+'0'*40

def day(ts):return dt.datetime.fromtimestamp(int(ts),UTC).strftime('%Y-%m-%d')
def timestamp(date):return int(dt.datetime.combine(dt.date.fromisoformat(date),dt.time(),UTC).timestamp())

def dedup_logs(logs,confirmed_head=None,confirmations=15):
    rows={}
    for row in logs:
        if row.get('removed'):continue
        number=int(row['blockNumber'],16)
        if confirmed_head is not None and number>confirmed_head-confirmations:continue
        key=(row['blockHash'].lower(),row['transactionHash'].lower(),int(row['logIndex'],16))
        rows[key]=row
    return sorted(rows.values(),key=lambda x:(int(x['blockNumber'],16),int(x.get('transactionIndex','0x0'),16),int(x['logIndex'],16)))

def address_topic(word):return '0x'+word[-40:].lower()
def abi_string(data):
    b=bytes.fromhex(data.removeprefix('0x'));off=int.from_bytes(b[:32],'big');n=int.from_bytes(b[off:off+32],'big')
    if off+32+n>len(b):raise ValueError('invalid ABI string')
    return b[off+32:off+32+n].decode('utf-8')

def registration(log):
    if log['topics'][0].lower() not in (REGISTERED,ADMIN):return None
    return {'name':abi_string(log['data']),'holder':address_topic(log['topics'][2]),'token_id':log['topics'][1].lower(),'kind':'admin' if log['topics'][0].lower()==ADMIN else 'normal','tx':log['transactionHash'],'block':int(log['blockNumber'],16),'tx_index':int(log['transactionIndex'],16) if log.get('transactionIndex') is not None else None,'log_index':int(log['logIndex'],16)}

def transfer_owners(logs,initial=None):
    owners=dict(initial or {})
    for x in dedup_logs(logs):
        if x['topics'][0].lower()!=TRANSFER or len(x['topics'])!=4:continue # ERC721, not ERC20
        token=x['topics'][3].lower();to=address_topic(x['topics'][2])
        if to==ZERO:owners.pop(token,None)
        else:owners[token]=to
    return owners

def sequence_name_ratio(names):
    """E4: same nonempty prefix, >=3 distinct consecutive numeric suffixes on one UTC day."""
    groups=collections.defaultdict(list)
    for idx,n in enumerate(names):
        m=re.fullmatch(r'(.+?)(\d+)',n)
        if m:groups[m[1]].append((int(m[2]),idx))
    selected=set()
    for vals in groups.values():
        bynum=collections.defaultdict(list)
        for n,i in vals:bynum[n].append(i)
        run=[]
        for n in sorted(bynum):
            if run and n!=run[-1]+1:
                if len(run)>=3:selected.update(i for k in run for i in bynum[k])
                run=[]
            run.append(n)
        if len(run)>=3:selected.update(i for k in run for i in bynum[k])
    return len(selected)/len(names) if names else None

def mean_complete(values,n=7):
    return sum(values[-n:])/n if len(values)>=n and all(v is not None for v in values[-n:]) else None

def identity_day(date,logs,complete,block_times,prior_cumulative,prior_owners=None):
    blank=dict(date=date,daily_new_ids=None,cumulative_ids=None,agent_id_holders=None,busiest_hour_share=None,sequence_name_share_e4=None,admin_registrations=None)
    if not complete:return blank,None
    rows=dedup_logs(logs);regs=[]
    for x in rows:
        r=registration(x)
        if r:
            ts=block_times.get(r['block'])
            if ts is None or day(ts)!=date:return blank,None
            r['timestamp']=ts;regs.append(r)
    owners=transfer_owners(rows,prior_owners) if prior_owners is not None else None
    hours=collections.Counter(dt.datetime.fromtimestamp(r['timestamp'],UTC).hour for r in regs)
    blank.update(daily_new_ids=len(regs),cumulative_ids=(prior_cumulative+len(regs)) if prior_cumulative is not None else None,agent_id_holders=len(set(owners.values())) if owners is not None else None,busiest_hour_share=max(hours.values())/len(regs) if regs else None,sequence_name_share_e4=sequence_name_ratio([r['name'] for r in regs]),admin_registrations=sum(r['kind']=='admin' for r in regs))
    return blank,owners

def cohort(tokens,created_date,hours,cutoff,complete=True):
    rows=[t for t in tokens if day(t['created_ts'])==created_date]
    if not complete:return {'numerator':None,'denominator':None,'ratio':None,'reason':'发行集合未完整读取'}
    if not rows:return {'numerator':0,'denominator':0,'ratio':None,'reason':'空队列，分母0'}
    # Require every launch in the day's cohort to have its whole window observed.
    if any(t['created_ts']+hours*3600>cutoff for t in rows):return {'numerator':None,'denominator':len(rows),'ratio':None,'reason':'右删失'}
    numerator=sum(t.get('graduated_ts') is not None and t['created_ts']<=t['graduated_ts']<=t['created_ts']+hours*3600 for t in rows)
    return {'numerator':numerator,'denominator':len(rows),'ratio':numerator/len(rows),'reason':None}

def resolve_price(points):
    values={Decimal(str(p)) for p in points if p is not None}
    return str(next(iter(values))) if len(values)==1 else None

def top_shares(volumes):
    vals=sorted((Decimal(str(v)) for v in volumes.values()),reverse=True);total=sum(vals)
    return {str(n):float(sum(vals[:n])/total) if total>0 else None for n in (1,10,100)}

def direction(value,previous):
    if value is None or len(previous)!=7 or any(v is None for v in previous):return None
    baseline=sum(Decimal(str(v)) for v in previous)/7;current=Decimal(str(value))
    return '上升' if current>baseline else ('下降' if current<baseline else '持平')

def platform_day(tokens,trades,date,complete):
    fields=['new_launches','graduated_today','cumulative_graduated','curve_volume_bnb','curve_trade_count','unique_buyers','unique_creators','creators_ge3','median_raised_bnb','raised_lt1_share','taxed_share','dev_prebuy_share']
    fields += [f+'_'+k for f in ['raised_lt1_share','taxed_share','dev_prebuy_share'] for k in ['numerator','denominator']]
    out=dict.fromkeys(fields)
    if not complete:return out
    import statistics
    end=timestamp(date)+86400;new=[t for t in tokens if day(t['created_ts'])==date];daily=[t for t in trades if day(t['timestamp'])==date]
    creators=collections.Counter(t['creator'] for t in new if t.get('creator'))
    out.update(new_launches=len(new),graduated_today=sum(t.get('graduated_ts') is not None and day(t['graduated_ts'])==date for t in tokens),cumulative_graduated=sum(t.get('graduated_ts') is not None and t['graduated_ts']<end for t in tokens),curve_trade_count=len({t.get('tx','') for t in daily}),curve_volume_bnb=sum(t['bnb'] for t in daily) if all(t.get('bnb') is not None for t in daily) else None,unique_buyers=len({t['actor'] for t in daily if t.get('side')=='buy' and t.get('actor')}),unique_creators=len(creators),creators_ge3=sum(n>=3 for n in creators.values()))
    for field,source,fn in [('median_raised_bnb','raised_eod_bnb',lambda v:statistics.median(v)),('raised_lt1_share','raised_eod_bnb',lambda v:sum(x<1 for x in v)/len(v)),('taxed_share','taxed',lambda v:sum(bool(x) for x in v)/len(v)),('dev_prebuy_share','dev_prebuy',lambda v:sum(bool(x) for x in v)/len(v))]:
        # No source inference or silent exclusion of missing values.
        if new and all(t.get(source) is not None for t in new):out[field]=fn([t[source] for t in new])
        if field.endswith('_share'):
            out[field+'_denominator']=len(new)
            out[field+'_numerator']=0 if not new else (sum(t[source]<1 if field=='raised_lt1_share' else bool(t[source]) for t in new) if all(t.get(source) is not None for t in new) else None)
    return out
