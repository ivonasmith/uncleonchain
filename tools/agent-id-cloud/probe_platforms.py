"""摸底：未启用平台在某一个 UTC 日里实际发了哪些链上事件（只读，只打印汇总，不写网站）。

用法（Actions 手动触发 agent-id-probe.yml）：
  python tools/agent-id-cloud/probe_platforms.py --from-block N --to-block M
节点：AGENT_ID_RPC_FALLBACK（带 key 的兜底节点，日志里自动打码）。事件签名查 openchain / 4byte 公共签名库。
"""
import argparse
import collections
import concurrent.futures
import json
import os
from pathlib import Path
import urllib.request

HERE = Path(__file__).resolve().parent
RPC = os.environ.get('AGENT_ID_RPC_FALLBACK') or os.environ.get('AGENT_ID_RPC_URL')
IMPL_SLOT = '0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc'  # EIP-1967


def post(url, body, timeout=30):
    req = urllib.request.Request(url, json.dumps(body).encode(), {'Content-Type': 'application/json', 'User-Agent': 'uncleonchain-probe/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rpc(method, params):
    for _ in range(4):
        try:
            out = post(RPC, {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})
            if 'error' in out:
                raise RuntimeError(out['error'])
            return out['result']
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(str(last)[:200])


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'uncleonchain-probe/1.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def event_name(topic):
    try:
        d = get('https://api.openchain.xyz/signature-database/v1/lookup?filter=true&event=' + topic)
        hits = d['result']['event'].get(topic) or []
        if hits:
            return ' | '.join(h['name'] for h in hits[:3])
    except Exception:  # noqa: BLE001
        pass
    try:
        d = get('https://www.4byte.directory/api/v1/event-signatures/?hex_signature=' + topic)
        if d.get('results'):
            return ' | '.join(r['text_signature'] for r in d['results'][:3])
    except Exception:  # noqa: BLE001
        pass
    return '?'


def logs(address, a, b, chunk=2000):
    spans = [(x, min(b, x + chunk - 1)) for x in range(a, b + 1, chunk)]
    out, errors = [], 0

    def one(span):
        return rpc('eth_getLogs', [{'address': address, 'fromBlock': hex(span[0]), 'toBlock': hex(span[1])}])
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for fut in [pool.submit(one, s) for s in spans]:
            try:
                out += fut.result()
            except Exception:  # noqa: BLE001
                errors += 1
    return out, errors


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--from-block', type=int, required=True)
    p.add_argument('--to-block', type=int, required=True)
    p.add_argument('--extra', default='', help='comma-separated extra addresses')
    p.add_argument('--http', default='', help='comma-separated public URLs to print (cross-check sources)')
    p.add_argument('--dump', default='', help='addr:n[,addr:n] print first n raw logs of addr in the block range (plus tx to/from)')
    p.add_argument('--calls', default='', help='to:calldata[,…] eth_call at latest, print raw result')
    p.add_argument('--four', action='store_true', help='Four.meme agent-bit census over the block range')
    p.add_argument('--count', default='', help='comma-separated addresses: only count logs per topic0 in range (no dump)')
    a = p.parse_args()
    for url in [u for u in a.http.split(',') if u.strip()]:
        try:
            base, _, grep = url.strip().partition('#grep=')
            req = urllib.request.Request(base, headers={'User-Agent': 'Mozilla/5.0 uncleonchain-probe', 'Accept': '*/*'})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode('utf-8', 'replace')
            if not grep:
                print('HTTP', base, r.status, body[:3000])
            else:
                import re as _re
                text = _re.sub(r'<script.*?</script>|<style.*?</style>', ' ', body, flags=_re.S)
                links = sorted(set(_re.findall(r'href="(/[a-z]{2}/flap[^"#]*)"', text)))
                text = _re.sub(r'<[^>]+>', ' ', text); text = _re.sub(r'\s+', ' ', text)
                print('HTTP', base, r.status, 'chars', len(text))
                seen_pos = -10**9
                shown = 0
                for m in _re.finditer(grep, text, _re.I):
                    if m.start() - seen_pos < 400 or shown >= 25:
                        continue
                    seen_pos = m.start(); shown += 1
                    print('   …', text[max(0, m.start() - 200):m.end() + 200])
        except Exception as e:  # noqa: BLE001
            print('HTTP', url, 'ERROR', str(e)[:300])
    for item in [c for c in a.calls.split(',') if c.strip()]:
        to, data = item.strip().split(':')
        try:
            print('CALL', to, data[:10], rpc('eth_call', [{'to': to, 'data': data}, 'latest']))
        except Exception as e:  # noqa: BLE001
            print('CALL', to, data[:10], 'ERROR', str(e)[:200])
    for item in [c for c in a.dump.split(',') if c.strip()]:
        parts = item.strip().split(':')
        addr, n = parts[0], parts[1]
        rows, errs = logs(addr, a.from_block, a.to_block)
        if len(parts) > 2:  # addr:n:topicPrefix — only logs whose topic0 starts with it
            rows = [r for r in rows if r['topics'] and r['topics'][0].startswith(parts[2].lower())]
        print(f'DUMP {addr} logs={len(rows)} errs={errs}')
        for r in rows[:int(n)]:
            tx = rpc('eth_getTransactionByHash', [r['transactionHash']])
            print('  ', json.dumps({'block': int(r['blockNumber'], 16), 'tx': r['transactionHash'], 'from': tx.get('from'), 'to': tx.get('to'),
                                    'input4': (tx.get('input') or '')[:10], 'value': int(tx.get('value', '0x0'), 16), 'topics': r['topics'], 'data': r['data'][:1200]}))
    for addr in [c.strip() for c in a.count.split(',') if c.strip()]:
        rows, errs = logs(addr, a.from_block, a.to_block)
        by = collections.Counter(r['topics'][0] for r in rows if r['topics'])
        print(f'COUNT {addr} logs={len(rows)} errs={errs} bytes~{sum(len(r["data"]) for r in rows)//2}')
        for t, n in by.most_common(15):
            print(f'   {n:7d} {t} {event_name(t)}')
    if a.four:
        # Four.meme：区间内 TokenCreate 的币逐个读 _tokenInfos，数 template 第 85 位；再看这些 Agent 币的创建交易发给了谁
        tm, create = '0x5c952063c7fc8610FFDB798152D69F0B9550762b', '0x396d5e902b675b032348d3d2e9517ee8f0c4a926603fbc075d3d282ff00cad20'
        rows, errs = logs(tm, a.from_block, a.to_block)
        made = [r for r in rows if r['topics'][0] == create]
        agents, tos = [], collections.Counter()
        for r in made:
            tok = '0x' + r['data'][2 + 64 + 24:2 + 128]
            raw = rpc('eth_call', [{'to': tm, 'data': '0xe684626b' + tok[2:].zfill(64)}, 'latest'])
            tpl = int(raw[2 + 128:2 + 192], 16)
            if (tpl >> 85) & 1:
                agents.append(tok)
                tx = rpc('eth_getTransactionByHash', [r['transactionHash']])
                tos[(tx.get('to') or '').lower()] += 1
        print(f'FOUR creates={len(made)} agent_bit85={len(agents)} errs={errs} create_tx_to={tos.most_common(5)} sample={agents[:3]}')
        tpl_hist = collections.Counter()
        for r in made[:60]:
            tok = '0x' + r['data'][2 + 64 + 24:2 + 128]
            raw = rpc('eth_call', [{'to': tm, 'data': '0xe684626b' + tok[2:].zfill(64)}, 'latest'])
            tpl_hist[hex(int(raw[2 + 128:2 + 192], 16))] += 1
        print('FOUR template values (first 60 creates):', tpl_hist.most_common(12))
        return
    if a.dump or a.count or a.calls:
        return
    if a.from_block <= 0:
        return
    cfg = json.loads((HERE / 'collector/config.json').read_text())
    targets = [(x['id'], x['address']) for x in cfg['platforms'] + cfg['noncurve'] if x.get('address')]
    targets += [('pending', x['address']) for x in cfg.get('pending_discoveries', []) if x.get('address')
                and x['address'].lower() not in {t[1].lower() for t in targets}
                and x['address'].lower() not in ('0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
                                                 '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c',   # WBNB
                                                 '0x10ed43c718714eb63d5aa57b78b54704e256024e')]  # Pancake router
    targets += [('extra', x.strip()) for x in a.extra.split(',') if x.strip()]
    names, report = {}, []
    for pid, addr in targets:
        impl = rpc('eth_getStorageAt', [addr, IMPL_SLOT, 'latest'])
        impl = '0x' + impl[-40:] if int(impl, 16) else None
        code = rpc('eth_getCode', [addr, 'latest'])
        rows, errs = logs(addr, a.from_block, a.to_block)
        by = collections.Counter(r['topics'][0] for r in rows if r['topics'])
        txs = {r['transactionHash'] for r in rows}
        for t in by:
            if t not in names:
                names[t] = event_name(t)
        report.append({'id': pid, 'address': addr, 'impl': impl, 'code_bytes': (len(code) - 2) // 2,
                       'logs': len(rows), 'txs': len(txs), 'chunk_errors': errs,
                       'events': [{'topic0': t, 'name': names[t], 'count': n} for t, n in by.most_common(12)]})
        print(f"\n== {pid} {addr} impl={impl} code={(len(code)-2)//2}B logs={len(rows)} txs={len(txs)} chunk_errors={errs}")
        for t, n in by.most_common(12):
            print(f"   {n:6d}  {t[:10]}…  {names[t]}")
    print('\nJSON ' + json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
