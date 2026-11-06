import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from transport import Client, Unavailable


class CloudCacheTests(unittest.TestCase):
    def cache(self, client, *, blocked=False):
        body = {'jsonrpc': '2.0', 'id': 1, 'method': 'eth_blockNumber', 'params': []}
        req = dict(url='https://example.invalid/rpc', method='POST', json=body,
                   scope='immutable', proxy=client.proxy)
        key = hashlib.sha256(json.dumps(req, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        path = client.raw / (key + '.json')
        path.write_text(json.dumps({**req, 'ok': not blocked, 'reason': '被拦' if blocked else None,
                                   'body': '{"error":{"code":-32002,"message":"archive unavailable"}}',
                                   'read_utc': '2026-11-01T00:00:00Z', 'raw_file': 'raw/http/' + path.name}))
        return path

    def test_repair_versions_failed_rpc_preserving_original(self):
        class Response:
            status = 200; url = 'https://example.invalid/rpc'; headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"result":"0x38"}'
        class Opener:
            def open(self, *args, **kwargs): return Response()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'AGENT_ID_RETRY_FAILED_SCOPE': 'repair-2'}):
            c = Client(tmp, proxy='http://proxy.invalid:7890'); p = self.cache(c); original = p.read_bytes(); c.opener = Opener()
            self.assertEqual(c.rpc('https://example.invalid/rpc', 'eth_blockNumber', [])[0], '0x38')
            self.assertEqual(p.read_bytes(), original)
            self.assertEqual(c.rpc('https://example.invalid/rpc', 'eth_blockNumber', [])[0], '0x38')
            self.assertEqual(c.request_count, 1)
            self.assertEqual(len(list(c.raw.glob('*.json'))), 2)

    def test_repair_does_not_bypass_recorded_challenge(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'AGENT_ID_RETRY_FAILED_SCOPE': 'repair-2'}):
            c = Client(tmp, proxy='http://proxy.invalid:7890'); self.cache(c, blocked=True)
            with self.assertRaises(Unavailable): c.rpc('https://example.invalid/rpc', 'eth_blockNumber', [])
            self.assertEqual(c.request_count, 0)
