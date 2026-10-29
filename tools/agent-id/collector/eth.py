"""Small ABI reader, no signing or account support."""
import json
import concurrent.futures
from pathlib import Path
from transport import Unavailable

# Reuse the repository's audited-against-known-selectors pure Keccak implementation.
# Copied into this directory at build time; no runtime dependency on C28.
from keccak import selector,keccak

def event_topic(abi):
    types=','.join(x['type'] for x in abi['inputs'])
    if '(' in types or 'tuple' in types:raise ValueError('tuple events require an explicit adapter')
    return '0x'+keccak((abi['name']+'('+types+')').encode())

def word_value(kind,word,data=None):
    if kind.startswith('uint'):return int.from_bytes(word,'big')
    if kind.startswith('int'):return int.from_bytes(word,'big',signed=True)
    if kind=='address':return '0x'+word[-20:].hex()
    if kind=='bool':return bool(int.from_bytes(word,'big'))
    if kind=='bytes32':return '0x'+word.hex()
    if kind=='string' and data is not None:
        off=int.from_bytes(word,'big');size=int.from_bytes(data[off:off+32],'big')
        if off+32+size>len(data):raise ValueError('ABI string outside response')
        return data[off+32:off+32+size].decode()
    raise ValueError('Unsupported ABI type '+kind)

def decode_event(log,abi):
    data=bytes.fromhex(log['data'][2:]);out={};di=0;ti=1
    for spec in abi['inputs']:
        if spec.get('indexed'):
            word=bytes.fromhex(log['topics'][ti][2:]);ti+=1;value=word_value(spec['type'],word)
        else:
            word=data[di*32:(di+1)*32];di+=1
            if len(word)!=32:raise ValueError('truncated ABI data')
            value=word_value(spec['type'],word,data)
        out[spec['name']]=value
    return out

class Chain:
    def __init__(self,client,rpc,scope,confirmations=15):
        self.client=client;self.url=rpc;self.scope=scope;self.confirmations=confirmations;self.times={};self.sources=[]
    def rpc(self,m,p,dynamic=False):
        value,rec=self.client.rpc(self.url,m,p,self.scope if dynamic else 'immutable');self.sources.append(rec['raw_file']);return value
    def head(self):return int(self.rpc('eth_blockNumber',[],True),16)
    def block(self,n):
        b=self.rpc('eth_getBlockByNumber',[hex(n),False]);self.times[n]=int(b['timestamp'],16);return b
    def time(self,n):
        if n not in self.times:self.block(n)
        return self.times[n]
    def boundary(self,ts,lo,hi):
        """First block with timestamp >= ts. Returns hi+1 if ts is beyond head."""
        left,right=lo,hi+1
        while left<right:
            mid=(left+right)//2
            if self.time(mid)<ts:left=mid+1
            else:right=mid
        return left
    def logs(self,addresses,start,end,topics=None,chunk=1000,depth=2):
        if end<start:return [],True,[]
        wanted={a.lower() for a in (addresses if isinstance(addresses,list) else [addresses])}
        requested_topics=set((topics[0] if isinstance(topics[0],list) else [topics[0]])) if topics and len(topics)==1 else None
        if requested_topics is not None:
            for view in getattr(self.client,'log_views',[]):
                if view['rpc']==self.url and view['start']<=start and end<=view['end'] and wanted.issubset(view['addresses']) and requested_topics.issubset(view['topics']):
                    self.sources+=view['raw']
                    selected=[r for r in view['rows'] if r['address'].lower() in wanted and start<=int(r['blockNumber'],16)<=end and r['topics'][0] in requested_topics]
                    return selected,view['complete'],view['errors']
        allrows=[];errors=[]
        def part(a,b,level):
            arg=dict(address=addresses,fromBlock=hex(a),toBlock=hex(b))
            if topics:arg['topics']=topics
            try:return self.rpc('eth_getLogs',[arg])
            except Unavailable as e:
                text=str(e)
                # Subdivide only provider range/result limits; do not bypass 403/429/challenges.
                if level and b>a and any(s in text.lower() for s in ['maximum block range','too many results','response size','query returned more']):
                    m=(a+b)//2;return part(a,m,level-1)+part(m+1,b,level-1)
                errors.append(dict(start=a,end=b,rpc=self.url,reason=text));return []
        spans=[(a,min(end,a+chunk-1)) for a in range(start,end+1,chunk)]
        # Independent ranges, bounded concurrency; each exact request remains cached.
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(part,a,b,depth) for a,b in spans]
            for future in futures:
                allrows.extend(future.result())
                if errors:
                    for pending in futures:pending.cancel()
                    break # a partial day is never published as a count
        return allrows,not errors,errors
    def call_uint(self,address,signature,block,args=''):
        raw=self.rpc('eth_call',[dict(to=address,data=selector(signature)+args),hex(block)])
        if len(raw)!=66:raise Unavailable('Unexpected uint call shape')
        return int(raw,16)

def source_metadata(client,address,scope='immutable',allow_match=False):
    url='https://sourcify.dev/server/v2/contract/56/'+address+'?fields=all';data,rec=client.json(url,scope=scope)
    accepted={'exact_match','match'} if allow_match else {'exact_match'}
    if data.get('creationMatch') not in accepted or data.get('runtimeMatch') not in accepted:raise Unavailable('未取得creation/runtime '+('match或exact_match' if allow_match else 'exact_match'))
    return data,rec
