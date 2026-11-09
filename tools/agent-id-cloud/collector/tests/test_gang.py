import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gang
from keccak import keccak

E = 10**18
U5 = 'uint256,uint256,uint256,uint256,uint256'
WB = '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c'


def T(s): return '0x' + keccak(s.encode())
def a32(a): return '0x' + '0' * 24 + a[2:]
def w(*xs): return '0x' + ''.join(hex(x)[2:].zfill(64) for x in xs)


class GangTests(unittest.TestCase):
    def run_day(self, quote, extra=()):
        cfg = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
        pad = cfg['gang_adapter']['pads'][0].lower()
        tok, actor, ts = '0x' + 'ab' * 20, '0x' + 'cd' * 20, 86400 * 20000
        logs = [
            dict(address=pad, topics=[T('Created(address,address,string,string,string,address,address,uint256)'), a32(tok), a32(actor), a32(quote)], data=w(0, 0, 0, 0, 0), blockNumber=hex(150), logIndex='0x0', transactionHash='0x1', blockHash='0xb', blockTimestamp=hex(ts + 10)),
            dict(address=pad, topics=[T('Buy(address,address,' + U5 + ')'), a32(tok), a32(actor)], data=w(99 * E // 100, E // 100, 0, 5, 6), blockNumber=hex(151), logIndex='0x1', transactionHash='0x2', blockHash='0xb', blockTimestamp=hex(ts + 20)),
            dict(address=pad, topics=[T('Sell(address,address,' + U5 + ')'), a32(tok), a32(actor)], data=w(5, E // 200, 0, E // 2 - E // 200, 6), blockNumber=hex(152), logIndex='0x2', transactionHash='0x3', blockHash='0xb', blockTimestamp=hex(ts + 30)),
        ] + list(extra)

        class FakeChain:
            def __init__(s, *a): pass
            def rpc(s, m, p, dyn=False):
                if m == 'eth_blockNumber': return hex(1000)
                if m == 'eth_getCode': return '0x60' if p[0].lower() == pad else '0x'
                raise gang.Unavailable('no registry')
            def logs(s, addrs, a, b, topics, chunk, depth):
                return [l for l in logs if a <= int(l['blockNumber'], 16) <= b], True, []
            def time(s, b): return 0
        old, gang.Chain = gang.Chain, FakeChain
        try:
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / 'data').mkdir()
                d = '2024-10-04'
                state = {'days': {d: {'A': {'start_block': 100, 'end_block': 200}}}}
                return gang.collect(tmp, cfg, None, '2099-01-01', [d], state), pad
        finally:
            gang.Chain = old

    def test_gross_volume_launch_and_actor(self):
        r, _ = self.run_day(WB)
        row = r['rows'][0]
        self.assertTrue(row['complete'])
        self.assertEqual(row['curve_volume_bnb'], '1.5')
        self.assertEqual((row['curve_trade_count'], row['new_launches'], row['unique_buyers']), (2, 1, 1))

    def test_stable_quote_counts_trades_not_bnb(self):
        r, _ = self.run_day('0x' + '11' * 20)
        row = r['rows'][0]
        self.assertEqual((row['curve_volume_bnb'], row['curve_trade_count'], row['non_bnb_quote_trades']), ('0', 2, 2))

    def test_trade_on_unseen_token_is_unknown(self):
        cfg_pad = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())['gang_adapter']['pads'][0].lower()
        stray = dict(address=cfg_pad, topics=[T('Buy(address,address,' + U5 + ')'), a32('0x' + 'ee' * 20), a32('0x' + 'cd' * 20)], data=w(1, 0, 0, 1, 1), blockNumber=hex(160), logIndex='0x3', transactionHash='0x4', blockHash='0xb', blockTimestamp=hex(86400 * 20000 + 40))
        r, _ = self.run_day(WB, [stray])
        self.assertFalse(r['rows'][0]['complete'])


if __name__ == '__main__':
    unittest.main()
