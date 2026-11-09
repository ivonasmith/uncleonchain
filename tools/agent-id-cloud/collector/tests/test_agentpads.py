import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agentpads

E = 10**18
CFG = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
REG = CFG['registry']['address'].lower()


def w(*xs):
    return '0x' + ''.join((x[2:].zfill(64) if isinstance(x, str) else hex(x)[2:].zfill(64)) for x in xs)


def log(addr, topic, data, n):
    return dict(address=addr, topics=[topic], data=data, blockNumber=hex(100 + n), logIndex=hex(n), transactionHash='0x%064x' % n)


class FakeRpc:
    logs_by_key = []
    infos = {}
    def __init__(self, config): self.calls = 0
    def logs(self, address, topics, a, b, chunk=2000): return list(self.logs_by_key)
    def call(self, method, params):
        tok = '0x' + params[0]['data'][-40:]
        agent, quote = self.infos[tok]
        return w(tok, quote, (1 << 85) | 3 if agent else 3)


class AgentPadsTests(unittest.TestCase):
    def run_key(self, key, logs, infos=None):
        old = agentpads.Rpc
        FakeRpc.logs_by_key, FakeRpc.infos = logs, infos or {}
        agentpads.Rpc = FakeRpc
        try:
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / 'data').mkdir()
                state = {'days': {'2026-11-08': {'A': {'start_block': 100, 'end_block': 200}}}}
                cfg = dict(CFG, rpc='pool:https://x.example')
                return agentpads.collect(tmp, cfg, None, '2026-11-09', ['2026-11-08'], state, key)
        finally:
            agentpads.Rpc = old

    def test_four_counts_only_agent_created_tokens(self):
        T = CFG['agentpads']['four']['topics']; tm = CFG['agentpads']['four']['address']
        agent, normal, me = '0x' + 'aa' * 20, '0x' + 'bb' * 20, '0x' + 'cc' * 20
        logs = [log(tm, T['create'], w(me, agent, 1, 0, 0, 0, 0, 0), 1),
                log(tm, T['buy'], w(agent, me, 1, 5, 99 * E // 100, E // 100, 0, 0), 2),
                log(tm, T['sell'], w(agent, me, 1, 5, E // 2, E // 200, 0, 0), 3),
                log(tm, T['buy'], w(normal, me, 1, 5, 7 * E, 0, 0, 0), 4)]
        r = self.run_key('four', logs, {agent: (True, '0x' + '0' * 40), normal: (False, '0x' + '0' * 40)})
        row = r['rows'][0]
        self.assertTrue(row['complete'])
        self.assertEqual((row['new_launches'], row['curve_trade_count'], row['curve_volume_bnb']), (1, 2, '1.5'))

    def test_flap_counts_only_agent_id_gated_tokens(self):
        T = CFG['agentpads']['flap']['topics']; portal = CFG['agentpads']['flap']['address']
        gated, other, nft2, me = '0x' + 'aa' * 20, '0x' + 'bb' * 20, '0x' + 'dd' * 20, '0x' + 'cc' * 20
        logs = [log(portal, T['gated'], w(gated, REG), 1),
                log(portal, T['gated'], w(other, nft2), 2),
                log(portal, T['create'], w(1, me, 1, gated, 0, 0, 0), 3),
                log(portal, T['buy'], w(1, gated, me, 5, E, E // 100, 1), 4),
                log(portal, T['sell'], w(1, gated, me, 5, E // 2 - E // 200, E // 200, 1), 5),
                log(portal, T['buy'], w(1, other, me, 5, 9 * E, 0, 1), 6),
                log(portal, T['graduate'], w(gated, '0x' + '11' * 20, 1, 1), 7)]
        row = self.run_key('flap', logs)['rows'][0]
        self.assertEqual((row['new_launches'], row['curve_trade_count'], row['curve_volume_bnb'], row['graduated_today']), (1, 2, '1.5', 1))


if __name__ == '__main__':
    unittest.main()
