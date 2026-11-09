import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_cloud import configure, needs_backfill, publish_gate
from checkpoint import pack, unpack
from cryptography.fernet import Fernet, InvalidToken


class CloudTests(unittest.TestCase):
    def config_root(self, path):
        (path / 'config.json').write_text('{}')
        return {'AGENT_ID_PROXY': 'http://proxy.example:7890', 'AGENT_ID_RPC_URL': 'https://rpc.example/private-token'}

    def test_local_computer_proxy_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); env = self.config_root(root); env['AGENT_ID_PROXY'] = 'http://127.0.0.1:7980'
            with self.assertRaises(ValueError): configure(root, env)

    def test_missing_proxy_has_no_direct_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); env = self.config_root(root); env.pop('AGENT_ID_PROXY')
            with self.assertRaises(ValueError): configure(root, env)

    def test_explicit_direct_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); env = self.config_root(root); env['AGENT_ID_PROXY'] = 'direct'; env['AGENT_ID_LOG_CHUNK'] = '2000'
            config = configure(root, env)
            self.assertEqual(config['proxy'], 'direct'); self.assertEqual(config['rpc_log_chunk'], 2000)
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collector'))
            from transport import Client
            self.assertIsNotNone(Client(root, 'direct').opener)

    def test_public_first_pool_with_key_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); env = self.config_root(root); env.pop('AGENT_ID_RPC_URL'); env['AGENT_ID_PROXY'] = 'direct'
            env['AGENT_ID_RPC_PUBLIC'] = 'https://public-a.example|https://public-b.example'
            env['AGENT_ID_RPC_FALLBACK'] = 'https://keyed.example/v2/secret'
            config = configure(root, env)
            self.assertEqual(config['rpc'], 'pool:https://public-a.example|https://public-b.example|https://keyed.example/v2/secret')
            env['AGENT_ID_RPC_PUBLIC'] = 'https://public-b.example'
            configure(root, env)  # pool membership may change; same chain, same source identity
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collector'))
            from transport import Client, Unavailable
            client = Client(root, 'direct'); calls = []
            def fake(url, body=None, scope='immutable'):
                calls.append(url)
                if 'public-a' in url: raise Unavailable('pruned')
                return {'body': json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': '0x38'}), 'url': url}
            client.request = fake
            result, rec = client.rpc(config['rpc'], 'eth_chainId', [])
            self.assertEqual(result, '0x38'); self.assertEqual(calls, ['https://public-a.example', 'https://public-b.example'])
            self.assertEqual(rec['pool'], config['rpc'])

    def test_self_tests_do_not_inherit_repair_switch(self):
        import run_cloud
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'AGENT_ID_RETRY_FAILED_SCOPE': 'run-1'}):
            root = Path(tmp)
            run_cloud.command(root, [sys.executable, '-c', 'import os,sys; sys.exit(1 if "AGENT_ID_RETRY_FAILED_SCOPE" in os.environ else 0)'], 'log.txt', clean_env=True)

    def test_rpc_change_cannot_splice_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); env = self.config_root(root); configure(root, env)
            env['AGENT_ID_RPC_URL'] = 'https://other.example/key'
            with self.assertRaises(ValueError): configure(root, env)

    def test_blank_runtime_requires_first_backfill(self):
        self.assertTrue(needs_backfill({'days': {}}, '2026-11-01', '2026-11-02'))

    def test_gap_or_unknown_cumulative_requires_repair(self):
        state = {'days': {'2026-11-01': {'A': {'complete': True, 'cumulative_ids': 1}},
                          '2026-11-03': {'A': {'complete': True, 'cumulative_ids': None}}}}
        self.assertTrue(needs_backfill(state, '2026-11-01', '2026-11-03'))

    def test_complete_zero_does_not_force_backfill(self):
        state = {'days': {'2026-11-01': {'A': {'complete': True, 'cumulative_ids': 0}}}}
        self.assertFalse(needs_backfill(state, '2026-11-01', '2026-11-01'))

    def gate(self, runtime, public, value=1):
        (runtime / 'data').mkdir()
        (runtime / 'data/reconciliation.json').write_text('{"status":"PASS"}')
        (runtime / 'artifact_verification.json').write_text('{"status":"PASS"}')
        public.mkdir()
        row = dict(date='2026-11-01', cumulative_ids=1, new_ids=1, trading_addresses=value,
                   volume_bnb='0', new_launches=0, graduated=0, event_reconciliation='PASS', scope=['AgentPad'])
        (public / 'core_series.json').write_text(json.dumps({'rows': [row]}))

    def test_unknown_core_metric_blocks_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp); p = r / 'public'; self.gate(r, p, None)
            with self.assertRaises(ValueError): publish_gate(r, p, '2026-11-01')

    def test_fully_read_zero_can_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp); p = r / 'public'; self.gate(r, p, 0)
            self.assertEqual(publish_gate(r, p, '2026-11-01')['trading_addresses'], 0)

    def test_checkpoint_encrypts_and_restores_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'AGENT_ID_STATE_KEY': Fernet.generate_key().decode()}):
            r = Path(tmp); src = r / 'runtime'; src.mkdir(); blob = b'{"secret":"never-public"}'
            (src / 'state.json').write_bytes(blob); enc = r / 'runtime.enc'; pack(src, enc)
            self.assertNotIn(b'never-public', enc.read_bytes())
            unpack(enc.read_bytes(), r / 'restored')
            self.assertEqual((r / 'restored/state.json').read_bytes(), blob)

    def test_wrong_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp); (r / 'state.json').write_text('{}')
            with patch.dict(os.environ, {'AGENT_ID_STATE_KEY': Fernet.generate_key().decode()}): pack(r, r.parent / (r.name + '.enc'))
            enc = r.parent / (r.name + '.enc')
            try:
                with patch.dict(os.environ, {'AGENT_ID_STATE_KEY': Fernet.generate_key().decode()}):
                    with self.assertRaises(InvalidToken): unpack(enc.read_bytes(), r / 'other')
            finally: enc.unlink()

    def test_archive_traversal_rejected(self):
        key = Fernet.generate_key(); buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tar:
            entry = tarfile.TarInfo('../escape'); entry.size = 1; tar.addfile(entry, io.BytesIO(b'x'))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'AGENT_ID_STATE_KEY': key.decode()}):
            with self.assertRaises(ValueError): unpack(Fernet(key).encrypt(buf.getvalue()), Path(tmp))

    def test_preflight_raw_survives_before_state_exists(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'AGENT_ID_STATE_KEY': Fernet.generate_key().decode()}):
            r = Path(tmp); src = r / 'runtime'; (src / 'raw').mkdir(parents=True)
            (src / 'raw/error.json').write_text('{"error":"archive unavailable"}')
            enc = r / 'runtime.enc'; pack(src, enc); unpack(enc.read_bytes(), r / 'restored')
            self.assertEqual((r / 'restored/raw/error.json').read_text(), '{"error":"archive unavailable"}')
            self.assertFalse((r / 'restored/state.json').exists())
