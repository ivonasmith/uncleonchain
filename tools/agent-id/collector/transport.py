"""Read-only HTTP/RPC, mandatory explicit proxy, immutable raw cache."""
import datetime as dt
import hashlib
import json
import time
import threading
from contextlib import nullcontext
import urllib.error
import urllib.request
from pathlib import Path

class Unavailable(RuntimeError):
    pass

def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

class Client:
    def __init__(self, root, proxy=None, offline=False, timeout=15):
        self.root=Path(root);self.raw=self.root/'raw'/'http';self.raw.mkdir(parents=True,exist_ok=True)
        self.proxy=proxy;self.offline=offline;self.timeout=timeout;self.request_count=0;self.cache_hits=0;self.records=[]
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':proxy,'http':proxy})) if proxy else None
        self.provider_lock=threading.RLock();self.provider_last=0

    @staticmethod
    def rpc_limit(body):
        try:
            data=json.loads(body);error=data.get('error') if isinstance(data,dict) else None
            return error if isinstance(error,dict) and (error.get('code') in [-32029,429] or 'rate limit' in error.get('message','').lower()) else None
        except Exception:return None

    def request(self,url,body=None,scope='immutable'):
        method='POST' if body is not None else 'GET'
        request={'url':url,'method':method,'json':body,'scope':scope,'proxy':self.proxy}
        key=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        path=self.raw/(key+'.json')
        # Preserve legacy HTTP-200/RPC-limit envelopes. A versioned repair records
        # the retries missing from the old implementation, without erasing raw.
        if path.exists():
            legacy=json.loads(path.read_text())
            if self.rpc_limit(legacy.get('body','')) and not legacy.get('rpc_rate_policy'):
                request.update(repair_policy='rpc-rate-v1',retry_of_raw=legacy.get('raw_file',str(path.relative_to(self.root))))
                key=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest();path=self.raw/(key+'.json')
        if path.exists():
            self.cache_hits+=1;rec=json.loads(path.read_text());self.records.append(rec)
            if rec.get('ok'):return rec
            raise Unavailable(rec.get('reason','cached failure'))
        if self.offline or not self.proxy:
            raise Unavailable('离线缓存缺失' if self.offline else '代理主机未确认；未联网，未直连')
        constrained=url=='https://rpc-bsc.blockmachine.io'
        with (self.provider_lock if constrained else nullcontext()):
            return self._fetch(url,body,request,key,path,constrained)

    def _fetch(self,url,body,request,key,path,constrained):
        attempts=[]
        for attempt in range(4): # initial request + three identical-address retries
            if constrained:
                delay=max(0,self.provider_last+1.2-time.monotonic())
                if delay:time.sleep(delay)
            item={'attempt':attempt+1,'read_utc':utc_now()}
            try:
                headers={'Accept':'application/json,text/html,text/plain','User-Agent':'agent-id-read-only-monitor/1.0'}
                data=None if body is None else json.dumps(body,separators=(',',':')).encode()
                if data is not None:headers['Content-Type']='application/json'
                self.request_count+=1
                with self.opener.open(urllib.request.Request(url,data=data,headers=headers),timeout=self.timeout) as response:
                    item.update(status=response.status,body=response.read().decode('utf-8',errors='replace'),final_url=response.url)
                    item['rate_headers']={k:v for k,v in response.headers.items() if k.lower().startswith(('x-ratelimit','ratelimit','x-cu-')) or k.lower()=='retry-after'}
            except urllib.error.HTTPError as e:
                item.update(status=e.code,body=e.read().decode('utf-8',errors='replace'),error=str(e))
                item['rate_headers']={k:v for k,v in (e.headers or {}).items() if k.lower().startswith(('x-ratelimit','ratelimit','x-cu-')) or k.lower()=='retry-after'}
            except Exception as e:
                item.update(status=None,body='',error=str(e))
            if constrained:self.provider_last=time.monotonic()
            text=item.get('body','').lower()
            challenge=any(s in text for s in ['cf-chl-','cf-turnstile','challenge-platform','verify you are human','captcha','just a moment...'])
            rpc_limit=self.rpc_limit(item.get('body',''));item['rpc_rate_limited']=bool(rpc_limit)
            item['blocked']=challenge or item.get('status') in (403,429) or bool(rpc_limit)
            attempts.append(item)
            if challenge:break # no challenge interaction or alternate-route bypass
            if item.get('status') not in (403,429) and not rpc_limit:break
            if attempt<3:
                retry_ms=(rpc_limit.get('data') or {}).get('retry_after_ms',0) if rpc_limit else 0
                retry_header=next((v for k,v in item.get('rate_headers',{}).items() if k.lower()=='retry-after'),'0')
                try:retry_seconds=float(retry_header)
                except ValueError:retry_seconds=0
                time.sleep(max(2**attempt,retry_ms/1000+1 if retry_ms else 0,retry_seconds))
        last=attempts[-1];ok=last.get('status')==200 and bool(last.get('body')) and not last.get('blocked')
        reason=('RPC限流：退避重试3次仍失败' if last.get('rpc_rate_limited') else ('被拦' if last.get('blocked') else last.get('error','空响应/非200'))) if not ok else None
        rec={**request,'key':key,'raw_file':str(path.relative_to(self.root)),'attempts':attempts,'ok':ok,'reason':reason,'read_utc':last['read_utc'],'body':last.get('body',''),'rpc_rate_policy':1}
        path.write_text(json.dumps(rec,ensure_ascii=False,indent=2));self.records.append(rec)
        if not ok:raise Unavailable(str(reason))
        return rec

    def json(self,url,body=None,scope='immutable'):
        rec=self.request(url,body,scope)
        try:return json.loads(rec['body']),rec
        except Exception as e:raise Unavailable('响应不是 JSON: '+str(e))

    def rpc(self,url,method,params,scope='immutable'):
        if method not in {'eth_chainId','eth_blockNumber','eth_getBlockByNumber','eth_getBlockByHash','eth_getLogs','eth_getCode','eth_call','eth_getTransactionReceipt','eth_getTransactionByHash'}:
            raise ValueError('read-only RPC allowlist rejected '+method)
        response,rec=self.json(url,{'jsonrpc':'2.0','id':1,'method':method,'params':params},scope)
        if 'error' in response:raise Unavailable('RPC '+str(response['error']))
        if response.get('result') is None:raise Unavailable('RPC null result')
        return response['result'],rec
