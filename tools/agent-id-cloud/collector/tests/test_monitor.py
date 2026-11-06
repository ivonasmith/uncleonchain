import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import *
from transport import Client,Unavailable

def log(n=100,idx=0,removed=False):
    return dict(blockNumber=hex(n),blockHash='0x'+'a'*64,transactionHash='0x'+'b'*64,logIndex=hex(idx),transactionIndex='0x0',topics=[TRANSFER,'0x'+'0'*64,'0x'+'0'*24+'1'*40,'0x'+'2'*64],data='0x',removed=removed)

class MonitorTests(unittest.TestCase):
    def test_zero_registration_complete(self):
        a,_=identity_day('2026-10-20',[],True,{},0,{})
        self.assertEqual(a['daily_new_ids'],0);self.assertEqual(a['agent_id_holders'],0)
    def test_failed_rpc_is_U(self):
        a,_=identity_day('2026-10-20',[],False,{},0,{})
        self.assertIsNone(a['daily_new_ids']);self.assertIsNone(a['cumulative_ids'])
    def test_utc_day_boundary(self):
        x=timestamp('2026-10-21');self.assertEqual(day(x-1),'2026-10-20');self.assertEqual(day(x),'2026-10-21')
    def test_duplicate_log(self):self.assertEqual(len(dedup_logs([log(),log()])),1)
    def test_reorg_15_confirmations(self):
        self.assertEqual(len(dedup_logs([log(100)],114)),0)
        self.assertEqual(len(dedup_logs([log(100)],115)),1)
        self.assertEqual(dedup_logs([log(100,removed=True)],115),[])
    def test_create_graduate_same_block(self):
        t=timestamp('2026-10-20');r=cohort([dict(created_ts=t,graduated_ts=t)],'2026-10-20',24,t+86400)
        self.assertEqual((r['numerator'],r['denominator'],r['ratio']),(1,1,1))
    def test_zero_tax(self):
        t=dict(created_ts=timestamp('2026-10-20'),taxed=False,dev_prebuy=False,creator='a',raised_eod_bnb=0)
        r=platform_day([t],[],'2026-10-20',True);self.assertEqual(r['taxed_share'],0);self.assertEqual(r['raised_lt1_share'],1)
    def test_empty_platform_complete(self):
        r=platform_day([],[],'2026-10-20',True);self.assertEqual(r['new_launches'],0);self.assertEqual(r['curve_volume_bnb'],0);self.assertIsNone(r['median_raised_bnb'])
    def test_empty_platform_unread(self):self.assertIsNone(platform_day([],[],'2026-10-20',False)['new_launches'])
    def test_censored_cohort(self):
        t=timestamp('2026-10-20');r=cohort([dict(created_ts=t,graduated_ts=None)],'2026-10-20',72,t+86400)
        self.assertIsNone(r['ratio']);self.assertIsNone(r['numerator']);self.assertEqual(r['denominator'],1)
    def test_two_prices_conflict(self):self.assertIsNone(resolve_price([1,2]));self.assertEqual(resolve_price([1,'1.0']),'1')
    def test_missing_ma_gap(self):self.assertIsNone(mean_complete([1,1,None,1,1,1,1]))
    def test_name_heuristic(self):self.assertEqual(sequence_name_ratio(['bot1','bot2','bot3','abc']),.75);self.assertIsNone(sequence_name_ratio([]))
    def test_top_share_zero_denominator(self):self.assertIsNone(top_shares({})['1'])
    def test_no_proxy_no_request(self):
        with tempfile.TemporaryDirectory() as t:
            c=Client(t)
            with self.assertRaises(Unavailable):c.request('https://example.org/')
            self.assertEqual(c.request_count,0)
    def test_cached_replay_never_calls_network(self):
        import hashlib,json
        with tempfile.TemporaryDirectory() as t:
            c=Client(t,proxy='http://test:7980',offline=True);request=dict(url='https://example.org/',method='GET',json=None,scope='immutable',proxy=c.proxy)
            key=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            (c.raw/(key+'.json')).write_text(json.dumps({**request,'ok':True,'body':'{"x":1}','read_utc':'2026-10-20T00:00:00Z'}))
            self.assertEqual(c.json(request['url'])[0],{'x':1});self.assertEqual(c.request_count,0);self.assertEqual(c.cache_hits,1)
    def test_decimal_directions_do_not_lexically_compare(self):
        self.assertEqual(direction('10',['2']*7),'上升');self.assertEqual(direction('2',['10']*7),'下降');self.assertIsNone(direction('2',['1',None,1,1,1,1,1]))
    def test_partial_source_requires_explicit_policy(self):
        from eth import source_metadata
        class Fake:
            def json(self,*a,**k):return {'creationMatch':'match','runtimeMatch':'match'},{}
        with self.assertRaises(Unavailable):source_metadata(Fake(),'0xexample')
        self.assertEqual(source_metadata(Fake(),'0xexample',allow_match=True)[0]['runtimeMatch'],'match')
    def test_proxy_without_creation_match_not_admitted(self):
        from eth import source_metadata
        class Fake:
            def json(self,*a,**k):return {'creationMatch':None,'runtimeMatch':'match'},{}
        with self.assertRaises(Unavailable):source_metadata(Fake(),'0xexample',allow_match=True)
    def test_agentpad_curve_reserve_and_bounds(self):
        from agentpad import curve_reserve_wei,curve_spot_bnb
        self.assertEqual(curve_reserve_wei(0),0);self.assertTrue(15*10**18<curve_reserve_wei(8*10**26)<=16*10**18)
        self.assertEqual(Decimal(curve_spot_bnb(8*10**26)),Decimal('0.000000079999999999'))
        with self.assertRaises(ValueError):curve_reserve_wei(8*10**26+1)
    def test_rpc_http200_rate_limit_retries_three_times(self):
        import json
        from unittest.mock import patch
        class Response:
            status=200;url='https://example.org/rpc';headers={}
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self):return json.dumps({'error':{'code':-32029,'message':'rate limit exceeded','data':{'retry_after_ms':1}}}).encode()
        class Opener:
            def open(self,*a,**k):return Response()
        with tempfile.TemporaryDirectory() as t,patch('transport.time.sleep'):
            c=Client(t,proxy='http://test:7980');c.opener=Opener()
            with self.assertRaises(Unavailable):c.rpc(Response.url,'eth_blockNumber',[])
            self.assertEqual(c.request_count,4)
            record=json.loads(next(c.raw.glob('*.json')).read_text());self.assertEqual(len(record['attempts']),4);self.assertFalse(record['ok'])
            with self.assertRaises(Unavailable):c.rpc(Response.url,'eth_blockNumber',[])
            self.assertEqual(c.request_count,4)
    def test_legacy_rate_repair_preserves_original_raw(self):
        import json,hashlib
        class Response:
            status=200;url='https://example.org/rpc';headers={}
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self):return b'{"jsonrpc":"2.0","id":1,"result":"0x10"}'
        class Opener:
            def open(self,*a,**k):return Response()
        with tempfile.TemporaryDirectory() as t:
            c=Client(t,proxy='http://test:7980');c.opener=Opener();body=dict(jsonrpc='2.0',id=1,method='eth_blockNumber',params=[]);request=dict(url=Response.url,method='POST',json=body,scope='immutable',proxy=c.proxy)
            key=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest();p=c.raw/(key+'.json');p.write_text(json.dumps({**request,'ok':True,'body':'{"error":{"code":-32029,"message":"rate limit exceeded"}}','read_utc':'2026-10-20T00:00:00Z','raw_file':'raw/http/'+p.name}))
            before=p.read_bytes();self.assertEqual(c.rpc(Response.url,'eth_blockNumber',[])[0],'0x10');self.assertEqual(p.read_bytes(),before);self.assertEqual(len(list(c.raw.glob('*.json'))),2)
            self.assertEqual(c.rpc(Response.url,'eth_blockNumber',[])[0],'0x10');self.assertEqual(c.request_count,1)
    def test_combined_log_view_filters_address_and_day(self):
        from types import SimpleNamespace
        from eth import Chain
        a=log(100);a['address']='0x'+'1'*40;b=log(200);b['address']='0x'+'2'*40
        view=dict(rpc='https://example.org/rpc',start=100,end=300,addresses={a['address'],b['address']},topics={TRANSFER},rows=[a,b],complete=True,errors=[],raw=['raw/fake.json'])
        chain=Chain(SimpleNamespace(log_views=[view]),view['rpc'],'test');rows,ok,errors=chain.logs(a['address'],100,199,[TRANSFER]);self.assertEqual(rows,[a]);self.assertTrue(ok)
    def test_observed_subset_never_published_as_global_activity(self):
        from monitor_agent_id import Monitor
        from types import SimpleNamespace
        m=Monitor.__new__(Monitor);m.chain=SimpleNamespace(url='https://example.org/rpc');m.trades=[];date='2026-10-20'
        m.state={'history_complete':True,'days':{date:{'A':{'cumulative_ids':100,'registrations':[dict(holder='actor',block=1,log_index=1)]}}}}
        e=dict(project='HashDroids',complete=True,activities=[dict(actor='actor',block=2,timestamp=timestamp(date),platform='HashDroids',bnb=0,identity_source_proven=True)])
        out=m.participation(date,[dict(platform='Unknown',complete=False)],[e],(1,10));self.assertIsNone(out['active_id_wallets']);self.assertEqual(out['observed_active_id_wallets'],1);self.assertEqual(out['observed_activation_lower_bound'],.01)
    def test_same_block_identity_must_precede_activity_log(self):
        from monitor_agent_id import Monitor
        from types import SimpleNamespace
        m=Monitor.__new__(Monitor);m.chain=SimpleNamespace(url='https://example.org/rpc');date='2026-10-20'
        m.state={'history_complete':True,'days':{date:{'A':{'cumulative_ids':1,'registrations':[dict(holder='actor',block=10,log_index=3)]}}}}
        m.trades=[dict(actor='actor',block=10,log_index=2,timestamp=timestamp(date),platform='AgentPad',bnb=1)]
        out=m.participation(date,[dict(platform='AgentPad',complete=True)],[],(1,10));self.assertEqual(out['active_id_wallets'],0)
        m.trades[0]['log_index']=4;out=m.participation(date,[dict(platform='AgentPad',complete=True)],[],(1,10));self.assertEqual(out['active_id_wallets'],1)

if __name__=='__main__':unittest.main(verbosity=2)
