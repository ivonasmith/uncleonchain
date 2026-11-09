"""GitHub-hosted orchestration. No wallet, signing, trading or deployment credentials."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent


def load(p):
    return json.loads(Path(p).read_text())


REFRESH_KEYS = ('gang_adapter', 'agentpads')  # 由代码维护的配置段：每次以仓库为准
POOL_IDENTITY = 'bsc-56-public-first-pool-v1'
# 公共节点的探测窗口：2026-10-20 第一个 2000 块（当天注册 3 万多条，窗口里一定有注册日志）。
# 节点要是对这段返回空，说明它没存这么老的历史却不报错，直接剔除，防止少算。
PROBE_FROM = 128646423


def pool_members(env):
    public = [u.strip() for u in env.get('AGENT_ID_RPC_PUBLIC', '').split('|') if u.strip()]
    fallback = env.get('AGENT_ID_RPC_FALLBACK', '').strip()
    return public, fallback


def configure(runtime, env):
    proxy, rpc = env.get('AGENT_ID_PROXY', ''), env.get('AGENT_ID_RPC_URL', '')
    public, fallback = pool_members(env)
    if not rpc and (public or fallback):
        # 公共免费节点优先，带 key 的节点只兜底。所有成员都是同一条 BSC 链（chainId 56），来源身份按「池」算。
        members = public + ([fallback] if fallback else [])
        if any(urlsplit(u).scheme != 'https' or not urlsplit(u).hostname for u in members):
            raise ValueError('RPC pool members must be HTTPS endpoints')
        rpc = 'pool:' + '|'.join(members)
        identity_source = POOL_IDENTITY
    else:
        identity_source = rpc
    p, r = urlsplit(proxy), urlsplit(rpc)
    if proxy != 'direct':  # 'direct' = explicit user-approved direct connection, never an implicit fallback
        if p.scheme not in ('http', 'https') or not p.hostname:
            raise ValueError('AGENT_ID_PROXY must be a runner-reachable HTTP proxy or the explicit value direct')
        if p.hostname.lower() in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('GitHub-hosted runner cannot use your computer localhost proxy')
    if not rpc.startswith('pool:') and (r.scheme != 'https' or not r.hostname):
        raise ValueError('AGENT_ID_RPC_URL must be an archival BSC HTTPS endpoint')
    identity = hashlib.sha256(identity_source.encode()).hexdigest()
    old = runtime / 'source_identity.json'
    if old.exists() and load(old)['rpc_sha256'] != identity:
        raise ValueError('RPC source changed; refuse to splice histories. Start a separate full rebuild.')
    old.write_text(json.dumps({'rpc_sha256': identity}))
    config = load(runtime / 'config.json')
    config.update(proxy=proxy, rpc=rpc, mint_rpc=rpc, block_rpc=rpc,
                  proxy_status='GitHub云端直连（用户明确同意）' if proxy == 'direct' else 'GitHub显式配置代理，无直连后备')
    if env.get('AGENT_ID_LOG_CHUNK'):  # provider getLogs block-range limit (Alchemy: 2000)
        config['rpc_log_chunk'] = int(env['AGENT_ID_LOG_CHUNK'])
    (runtime / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2))
    return config


def probe_pool(client, config, env):
    """Keep public members that really serve old registry logs; the keyed fallback always stays last."""
    from transport import Unavailable
    public, fallback = pool_members(env)
    scope = 'probe-' + dt.datetime.now(dt.timezone.utc).date().isoformat()
    arg = dict(address=config['registry']['address'], fromBlock=hex(PROBE_FROM), toBlock=hex(PROBE_FROM + 1999))
    live = []
    for url in public:
        try:
            cid, _ = client.rpc(url, 'eth_chainId', [], scope)
            logs, _ = client.rpc(url, 'eth_getLogs', [arg], scope)
            ok = int(cid, 16) == 56 and isinstance(logs, list) and len(logs) > 0
            why = '' if ok else 'chainId/empty logs (no history for 2026-10-20)'
        except (Unavailable, ValueError) as e:
            ok, why = False, redact(str(e))[:200]
        print('public RPC', urlsplit(url).hostname, 'OK' if ok else 'skipped: ' + why)
        if ok:
            live.append(url)
    members = live + ([fallback] if fallback else [])
    if not members:
        raise ValueError('no usable BSC RPC: public nodes failed the history probe and no fallback key is configured')
    print('fallback key node', 'configured' if fallback else 'not configured')
    return 'pool:' + '|'.join(members)


def served_by(runtime, since):
    """Count this run's successful RPC requests per host (hostnames only, never keys)."""
    counts = {}
    for f in (runtime / 'raw' / 'http').glob('*.json'):
        if f.stat().st_mtime < since:
            continue
        try:
            rec = load(f)
        except Exception:
            continue
        if rec.get('ok') and isinstance(rec.get('json'), dict) and rec['json'].get('method'):
            host = urlsplit(rec.get('url', '')).hostname or '?'
            counts[host] = counts.get(host, 0) + 1
    return counts


def needs_backfill(state, start, through):
    day, end = dt.date.fromisoformat(start), dt.date.fromisoformat(through)
    while day <= end:
        row = state.get('days', {}).get(day.isoformat(), {})
        if not row.get('A', {}).get('complete') or row.get('A', {}).get('cumulative_ids') is None:
            return True
        day += dt.timedelta(days=1)
    return False


def publish_gate(runtime, output, yesterday):
    audit = load(runtime / 'data/reconciliation.json')
    verify = load(runtime / 'artifact_verification.json')
    data = load(output / 'core_series.json')
    if audit['status'] != 'PASS' or verify['status'] != 'PASS':
        raise ValueError('private validation or identity reconciliation failed; no publication')
    row = data['rows'][-1]
    fields = ('cumulative_ids', 'new_ids', 'trading_addresses', 'volume_bnb', 'new_launches', 'graduated')
    if row['date'] != yesterday or any(row.get(k) is None for k in fields):
        raise ValueError('latest closed UTC day has unknown core metrics; keep previous website data')
    if row.get('event_reconciliation') != 'PASS' or not row.get('scope'):
        raise ValueError('trade universe did not reconcile')
    if any('rpc' in r for r in data['rows']):
        raise ValueError('public output contains private RPC endpoint')
    return row


def private_values():
    return [v for v in (os.environ.get(k, '') for k in ('AGENT_ID_RPC_URL', 'AGENT_ID_PROXY', 'AGENT_ID_RPC_FALLBACK', 'ALCHEMY_KEY', 'AGENT_ID_STATE_KEY')) if v and v != 'direct']


def redact(text):
    for v in private_values():
        text = text.replace(v, '***')
    return text


def command(runtime, args, log, clean_env=False):
    env = None
    if clean_env:  # self-tests must not inherit this run's repair switch (it changes cache-retry behaviour)
        env = {k: v for k, v in os.environ.items() if k != 'AGENT_ID_RETRY_FAILED_SCOPE'}
    with (runtime / log).open('w') as f:
        done = subprocess.run(args, cwd=runtime, stdout=f, stderr=subprocess.STDOUT, env=env)
    if done.returncode:
        # 失败时把日志尾巴脱敏后打出来（密钥、节点 key 一律替换成 ***），不然 checkpoint 加密后没人能看原因
        tail = (runtime / log).read_text(errors='replace').splitlines()[-40:]
        print('---- ' + log + ' (last 40 lines, redacted) ----\n' + redact('\n'.join(tail)), file=sys.stderr)
        raise subprocess.CalledProcessError(done.returncode, args[1:3])


def run(runtime, output):
    runtime, output = Path(runtime).resolve(), Path(output).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    if output == runtime or runtime in output.parents:
        raise ValueError('public output must be outside private runtime')
    # Code comes from checkout; state and immutable raw come from the encrypted checkpoint.
    src = HERE / 'collector'
    shutil.copytree(src, runtime, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', 'config.json'))
    if not (runtime / 'config.json').exists():
        shutil.copy2(src / 'config.json', runtime / 'config.json')
    else:
        # 运行时 config 来自加密 checkpoint（含采集过程写回的状态），不整体覆盖；
        # 但仓库新加的配置段（如 gang_adapter）和适配器定义要带进来，否则新代码读不到。
        repo_cfg, run_cfg = load(src / 'config.json'), load(runtime / 'config.json')
        changed = False
        for key, value in repo_cfg.items():
            if key not in run_cfg or key in REFRESH_KEYS:
                if run_cfg.get(key) != value:
                    run_cfg[key] = value
                    changed = True
        if changed:
            (runtime / 'config.json').write_text(json.dumps(run_cfg, ensure_ascii=False, indent=2))
    config = configure(runtime, os.environ)
    if (runtime / 'state.json').exists():
        os.environ['AGENT_ID_RETRY_FAILED_SCOPE'] = os.environ.get('GITHUB_RUN_ID', 'manual') + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    sys.path.insert(0, str(runtime))
    from transport import Client
    client = Client(runtime, config['proxy'])
    if config['rpc'].startswith('pool:'):
        config['rpc'] = probe_pool(client, config, os.environ)
        config.update(mint_rpc=config['rpc'], block_rpc=config['rpc'])
        (runtime / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2))
    started = dt.datetime.now(dt.timezone.utc).timestamp()
    chain_id, _ = client.rpc(config['rpc'], 'eth_chainId', [])
    if int(chain_id, 16) != 56:
        raise ValueError('configured RPC is not BSC chain 56')
    client.rpc(config['rpc'], 'eth_getBlockByNumber', [hex(config['registry']['deployment_block']), False])
    client.rpc(config['rpc'], 'eth_getLogs', [dict(address=config['registry']['address'], fromBlock=hex(config['registry']['deployment_block']), toBlock=hex(config['registry']['deployment_block']))])
    (runtime / 'charts').mkdir(exist_ok=True)
    (runtime / 'data').mkdir(exist_ok=True)  # 空目录首跑：discovery 直接往 data/ 写文件，不会自己建
    today = dt.datetime.now(dt.timezone.utc).date()
    yesterday = (today - dt.timedelta(days=1)).isoformat()
    state = load(runtime / 'state.json') if (runtime / 'state.json').exists() else {'days': {}}
    command(runtime, [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], 'test_log.txt', clean_env=True)
    # One-time bootstrap / explicit catch-up; normal daily collection remains yesterday only.
    missing = needs_backfill(state, config['backfill_observed_start'], yesterday)
    args = [sys.executable, 'monitor_agent_id.py', '--backfill' if missing else '--daily']
    if missing and state['days']:
        args.append('--reprocess')
        os.environ['AGENT_ID_RETRY_FAILED_SCOPE'] = os.environ.get('GITHUB_RUN_ID', 'manual') + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    command(runtime, args, 'collection_log.txt')
    command(runtime, [sys.executable, 'monitor_agent_id.py', '--report'], 'offline_report_log.txt')
    # Stage export outside repository; failed validation cannot overwrite the live website snapshot.
    stage = runtime.parent / 'agent-id-customer-stage'
    command(runtime, [sys.executable, 'web_export/export_site.py', '--runtime', '.', '--output', str(stage)], 'export_log.txt')
    command(runtime, [sys.executable, '-m', 'unittest', 'discover', '-s', 'web_export', '-p', 'test_export.py', '-v'], 'customer_export_test_log.txt', clean_env=True)
    command(runtime, ['node', 'web_export/verify_frontend.cjs', str(stage / 'index.html')], 'customer_frontend_check_log.txt')
    row = publish_gate(runtime, stage, yesterday)
    secrets = private_values()
    for path in stage.rglob('*'):
        if path.is_file() and any(s and s.encode() in path.read_bytes() for s in secrets):
            raise ValueError('private endpoint appeared in public files')
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(stage, output)
    print(json.dumps({'date': yesterday, 'scope': row['scope'], 'gate': 'PASS', 'mode': 'backfill' if missing else 'daily',
                      'rpc_served': served_by(runtime, started)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--runtime', required=True); p.add_argument('--output', required=True)
    a = p.parse_args()
    try:
        run(a.runtime, a.output)
    except Exception as e:
        # Detailed logs stay only in the encrypted checkpoint, never in public build logs.
        print('Agent ID update failed (' + type(e).__name__ + ': ' + redact(str(e))[:500] + '); no new public data accepted.', file=sys.stderr)
        sys.exit(1)
