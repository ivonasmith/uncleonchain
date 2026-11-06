"""Daily public source-availability checks. Never auto-admits a trading adapter."""
import concurrent.futures
import json
import re
from pathlib import Path

def refresh(root,config,client,date):
    root=Path(root)
    if client.offline:return []
    checks_path=root/'data'/'mint_source_checks.json'
    mint_checks=json.loads(checks_path.read_text()) if checks_path.exists() else []
    checked={x['project']:x for x in mint_checks};rules=json.loads((root/'mint_verified_rules.json').read_text());tasks=[]
    for p in config['platforms']:
        if not p.get('enabled') and p.get('address'):tasks.append(dict(project=p['id'],address=p['address'],kind='platform'))
    for p in json.loads((root/'mint_candidates.json').read_text()):
        if p.get('address') and not checked.get(p['id'],{}).get('source_verified') and p['id'] not in rules:tasks.append(dict(project=p['id'],address=p['address'],kind='mint'))
    def one(task):
        address=task['address'];out={**task,'date':date,'source_verified':None,'gate_verified':None,'enabled':False}
        if not re.fullmatch('0x[0-9a-fA-F]{40}',address):out['reason']='地址格式未通过，未请求';return out
        url='https://sourcify.dev/server/v2/contract/56/'+address+'?fields=all';out['url']=url
        try:
            data,rec=client.json(url,scope=date);matches={k:data.get(k) for k in ['creationMatch','runtimeMatch']};verified=all(v in ['match','exact_match'] for v in matches.values())
            out.update(source_verified=True if verified else None,source_match_type=matches,is_proxy=data.get('proxyResolution',{}).get('isProxy'),implementations=data.get('proxyResolution',{}).get('implementations',[]),raw=[rec['raw_file']],read_utc=rec['read_utc'],grade='E3',abi_getters=[a['name'] for a in data.get('abi',[]) if a['type']=='function'],reason='源码匹配可审阅；尚未审阅门禁、权限和事件全集，保持不启用' if verified else '未取得creation/runtime匹配；代理实现及门禁需另核')
        except Exception as e:
            out['reason']=str(e)
            rec=next((r for r in reversed(client.records) if r.get('url')==url),None)
            if rec:out.update(raw=[rec['raw_file']],read_utc=rec['read_utc'])
        return out
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(one,tasks))
    prior_path=root/'data'/'source_availability.json';prior=json.loads(prior_path.read_text()) if prior_path.exists() else []
    history={(r['date'],r['project']):r for r in prior}
    for row in rows:
        history[(date,row['project'])]=row
        if row['kind']=='mint':checked[row['project']]=row
    checks_path.write_text(json.dumps(list(checked.values()),ensure_ascii=False,indent=2));prior_path.write_text(json.dumps(list(history.values()),ensure_ascii=False,indent=2))
    return [dict(module='发现/'+r['project'],date=date,reason=r['reason'],url=r.get('url'),rpc=None,blocks=None) for r in rows if r.get('source_verified')]

if __name__=='__main__':
    from datetime import datetime,timezone
    from transport import Client
    root=Path(__file__).parent;config=json.loads((root/'config.json').read_text());c=Client(root,config['proxy']);out=refresh(root,config,c,datetime.now(timezone.utc).date().isoformat());print('sources newly readable/pending review',len(out),'network requests',c.request_count,'cache hits',c.cache_hits)
