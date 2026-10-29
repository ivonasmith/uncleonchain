import copy
import unittest
from export_site import daily_core

class ExportTests(unittest.TestCase):
    def setup_data(self):
        p=dict(platform='A', complete=True, curve_volume_bnb='0.1', curve_trade_count=2, new_launches=1, graduated_today=0)
        s=dict(days={'2026-10-27':dict(A=dict(complete=True,cumulative_ids=100,daily_new_ids=10),B=[p])})
        t=[dict(platform='A',timestamp=1793059200,tx='0xa',log_index=1,actor='0xabc',side='buy',curve_bnb_wei=50*10**15),
           dict(platform='A',timestamp=1793059201,tx='0xb',log_index=1,actor='0xABC',side='sell',curve_bnb_wei=50*10**15)]
        return s,t
    def test_buy_and_sell_same_actor_count_once(self):
        s,t=self.setup_data();r=daily_core(s,t,'2026-10-28')[0];self.assertEqual(r['trading_addresses'],1);self.assertEqual(r['volume_bnb'],'0.1')
    def test_mint_is_not_a_trade(self):
        s,t=self.setup_data();t.append(dict(platform='A',timestamp=1793059202,side='mint'));self.assertEqual(daily_core(s,t,'2026-10-28')[0]['trading_addresses'],1)
    def test_missing_trade_universe_is_unknown(self):
        s,t=self.setup_data();self.assertIsNone(daily_core(s,t[:1],'2026-10-28')[0]['trading_addresses'])
    def test_volume_mismatch_is_unknown(self):
        s,t=self.setup_data();t[0]['curve_bnb_wei']=1;self.assertIsNone(daily_core(s,t,'2026-10-28')[0]['volume_bnb'])
    def test_complete_zero_is_zero(self):
        s,t=self.setup_data();s['days']['2026-10-27']['B'][0].update(curve_trade_count=0,curve_volume_bnb='0');r=daily_core(s,[],'2026-10-28')[0];self.assertEqual(r['trading_addresses'],0);self.assertEqual(r['volume_bnb'],'0')
    def test_unknown_platform_not_zero(self):
        s,t=self.setup_data();s['days']['2026-10-27']['B'][0]['complete']=False;r=daily_core(s,t,'2026-10-28')[0];self.assertIsNone(r['volume_bnb']);self.assertEqual(r['scope'],[])
    def test_duplicate_log_not_double_counted(self):
        s,t=self.setup_data();t.append(copy.deepcopy(t[0]));self.assertEqual(daily_core(s,t,'2026-10-28')[0]['volume_bnb'],'0.1')
    def test_current_day_not_exported(self):
        s,t=self.setup_data();self.assertEqual(daily_core(s,t,'2026-10-27'),[])

if __name__=='__main__':unittest.main()
