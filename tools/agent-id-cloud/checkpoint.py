"""Encrypted full-state persistence between ephemeral GitHub runners."""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile
from cryptography.fernet import Fernet

NAME = 'agent-id-encrypted-checkpoint'


def gh(args, binary=False):
    result = subprocess.run(['gh'] + args, capture_output=True, check=True)
    return result.stdout if binary else json.loads(result.stdout)


def cipher():
    key = os.environ.get('AGENT_ID_STATE_KEY', '')
    if not key:
        raise ValueError('missing AGENT_ID_STATE_KEY')
    return Fernet(key.encode())


def artifacts():
    repo = os.environ['GITHUB_REPOSITORY']
    items = gh(['api', f'repos/{repo}/actions/artifacts?name={NAME}&per_page=100'])['artifacts']
    return sorted(items, key=lambda a: a['id'], reverse=True)


def eligible(artifact):
    branch = os.environ['AGENT_ID_DEFAULT_BRANCH']
    if artifact.get('expired') or artifact.get('workflow_run', {}).get('head_branch') != branch:
        return False
    repo = os.environ['GITHUB_REPOSITORY']
    run = gh(['api', f"repos/{repo}/actions/runs/{artifact['workflow_run']['id']}"])
    return run.get('path') == '.github/workflows/agent-id-daily.yml' and run.get('event') in ('schedule', 'workflow_dispatch')


def pack(runtime, destination):
    runtime = Path(runtime).resolve()
    if not runtime.is_dir() or not any(runtime.iterdir()):
        raise ValueError('no runtime evidence to checkpoint')
    with tempfile.TemporaryFile() as archive:
        with tarfile.open(fileobj=archive, mode='w:gz') as tar:
            tar.add(runtime, arcname='runtime', filter=lambda i: None if '__pycache__' in Path(i.name).parts else i)
        archive.seek(0)
        encrypted = cipher().encrypt(archive.read())
    Path(destination).write_bytes(encrypted)


def unpack(blob, runtime):
    data = cipher().decrypt(blob)
    runtime = Path(runtime).resolve(); runtime.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
        members = tar.getmembers()
        for m in members:
            parts = Path(m.name).parts
            if not parts or parts[0] != 'runtime' or '..' in parts or Path(m.name).is_absolute() or m.issym() or m.islnk():
                raise ValueError('unsafe checkpoint member')
        with tempfile.TemporaryDirectory(dir=runtime.parent) as tmp:
            tar.extractall(tmp, filter='data')
            import shutil
            shutil.copytree(Path(tmp) / 'runtime', runtime, dirs_exist_ok=True)


def restore(runtime):
    cipher()  # Validate secret even before first run.
    for a in artifacts():
        if eligible(a):
            repo = os.environ['GITHUB_REPOSITORY']
            blob = gh(['api', f"repos/{repo}/actions/artifacts/{a['id']}/zip"], binary=True)
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                if z.namelist() != ['runtime.enc']:
                    raise ValueError('unexpected checkpoint layout')
                unpack(z.read('runtime.enc'), runtime)
            print('restored encrypted history')
            return
    print('no checkpoint: first run will independently backfill from registry start')


def prune():
    # Keep two complete immutable snapshots. Both contain the entire raw history.
    allowed = [a for a in artifacts() if eligible(a)]
    for a in allowed[2:]:
        subprocess.run(['gh', 'api', '--method', 'DELETE',
                        f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/artifacts/{a['id']}"], check=True,
                       stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['restore', 'pack', 'prune']); p.add_argument('--runtime'); p.add_argument('--output')
    a = p.parse_args()
    if a.mode == 'restore': restore(a.runtime)
    elif a.mode == 'pack': pack(a.runtime, a.output)
    else: prune()
