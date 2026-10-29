"""Run in a persistent private directory, then publish only the customer export."""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlparse
from export_site import export

HERE = Path(__file__).resolve().parent

def run(runtime, output, report_only=False):
    runtime = Path(runtime).expanduser().resolve()
    checkout = HERE.parents[1]
    if runtime == checkout or checkout in runtime.parents:
        raise ValueError('运行目录须在Git checkout之外，防止checkout clean删除历史和raw')
    if not (runtime / 'state.json').is_file() or not (runtime / 'raw/http').is_dir():
        raise ValueError('请先把private-seed.tar.gz解压到持久运行目录；禁止无基线发布累计数据')
    (runtime / 'charts').mkdir(exist_ok=True)
    with (runtime / '.daily.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for p in (HERE / 'collector').glob('*.py'):
            shutil.copy2(p, runtime / p.name)
        shutil.copytree(HERE / 'collector/tests', runtime / 'tests', dirs_exist_ok=True)
        for name in ['config.json', 'mint_candidates.json', 'mint_verified_rules.json']:
            if not (runtime / name).exists():
                shutil.copy2(HERE / 'collector' / name, runtime / name)
        config = json.loads((runtime / 'config.json').read_text())
        if not report_only:
            proxy = os.environ.get('AGENT_ID_PROXY', '')
            parsed = urlparse(proxy)
            if parsed.scheme not in ['http', 'https'] or not parsed.hostname:
                raise ValueError('须设置Runner实际可达的AGENT_ID_PROXY；不能把其他电脑localhost当成此Runner')
            config['proxy'] = proxy
            config['proxy_status'] = '部署Runner显式配置代理；无直连后备'
            (runtime / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2))
        with (runtime / 'test_log.txt').open('w') as f:
            subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                           cwd=runtime, stdout=f, stderr=subprocess.STDOUT, check=True)
        commands = ['--report'] if report_only else ['--daily', '--report']
        for command in commands:
            subprocess.run([sys.executable, 'monitor_agent_id.py', command], cwd=runtime, check=True)
        run = json.loads((runtime / 'last_run.json').read_text())
        today = dt.datetime.now(dt.timezone.utc).date().isoformat()
        if not report_only and (run['run_date'] != today or len(run['processed_dates']) != 1):
            raise ValueError('本次采集不是当前UTC运行日的单日更新')
        export(runtime, output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--report-only', action='store_true', help='仅验证并离线导出已有快照；不更新数据日期')
    args = parser.parse_args()
    run(args.runtime, args.output, args.report_only)
