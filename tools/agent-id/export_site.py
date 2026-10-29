"""Export a customer dashboard from recorded data; no network or wallet access."""
import argparse
import csv
import datetime as dt
from decimal import Decimal
import hashlib
import json
import re
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
UTC = dt.timezone.utc

def load(path):
    return json.loads(path.read_text())

def daily_core(state, trades, run_date):
    """Counts are unknown unless the complete event universe reconciles."""
    by_day = {}
    dedup = {}
    for t in trades:
        if t.get('side') not in ('buy', 'sell'):
            continue
        key = (t['platform'], t['tx'], t['log_index'])
        if key in dedup and dedup[key] != t:
            raise ValueError('conflicting duplicate trade')
        dedup[key] = t
    for t in dedup.values():
        date = dt.datetime.fromtimestamp(t['timestamp'], UTC).date().isoformat()
        by_day.setdefault(date, []).append(t)
    rows = []
    for date, record in sorted(state['days'].items()):
        if date >= run_date:
            continue
        a = record['A']
        platforms = [p for p in record.get('B', []) if p.get('complete') is True
                     and p.get('curve_volume_bnb') is not None
                     and p.get('curve_trade_count') is not None]
        scope = sorted(p['platform'] for p in platforms)
        events = [t for t in by_day.get(date, []) if t['platform'] in scope]
        expected = sum(p['curve_trade_count'] for p in platforms)
        complete = bool(platforms) and len(events) == expected and all(
            t.get('actor') and t.get('curve_bnb_wei') is not None for t in events)
        volume = sum((Decimal(p['curve_volume_bnb']) for p in platforms), Decimal(0))
        actual = sum((int(t['curve_bnb_wei']) for t in events), 0)
        complete = complete and Decimal(actual) / Decimal(10**18) == volume
        launches_known = bool(platforms) and all(p.get('new_launches') is not None for p in platforms)
        graduates_known = bool(platforms) and all(p.get('graduated_today') is not None for p in platforms)
        rows.append(dict(
            date=date,
            cumulative_ids=a.get('cumulative_ids') if a.get('complete') else None,
            new_ids=a.get('daily_new_ids') if a.get('complete') else None,
            trading_addresses=len({t['actor'].lower() for t in events}) if complete else None,
            volume_bnb=str(volume) if complete else None,
            new_launches=sum(p['new_launches'] for p in platforms) if launches_known else None,
            graduated=sum(p['graduated_today'] for p in platforms) if graduates_known else None,
            scope=scope,
            start_block=a.get('start_block'), end_block=a.get('end_block'), rpc=a.get('rpc'),
            grade='E1', event_reconciliation='PASS' if complete else 'U',
        ))
    return rows

def export(runtime, output):
    runtime, output = Path(runtime).resolve(), Path(output).resolve()
    if output.exists() and any(output.iterdir()) and not (output / '.agent-id-generated').exists():
        raise ValueError('拒绝覆盖未标记为Agent ID生成目录的现有内容')
    state, run = load(runtime / 'state.json'), load(runtime / 'last_run.json')
    rows = daily_core(state, load(runtime / 'data/trades.json'), run['run_date'])
    if not rows:
        raise ValueError('没有完整UTC日行')
    payload = dict(schema_version=1, data_through_utc=rows[-1]['date'],
                   generated_utc=dt.datetime.now(UTC).isoformat(),
                   source_read_through_utc=run.get('finished_utc'), rows=rows,
                   coverage='注册为完整注册表；交易/发币为scope列出的完整已核平台子集，不代表全生态',
                   definitions=dict(trading_addresses='当日买卖事件独立参与地址；不是只买入地址，不含单纯铸造/领取，不是Agentic Wallet总数',
                                    volume_bnb='已核曲线买卖成交额，扣除平台费；不含二级DEX及其他未核平台',
                                    new_launches='已核工厂当日创建数；不表示每个创建者均受ID门禁',
                                    missing='null显示U，图上断点；完整读取的零显示0'))
    # Keep each customer metric's detailed proof in the private runtime, not the homepage.
    audit = []; envelope_times = {}
    for row in rows:
        source = state['days'][row['date']]
        for field in ['cumulative_ids','new_ids','trading_addresses','volume_bnb','new_launches','graduated']:
            records = [source['A']] if field in ['cumulative_ids','new_ids'] else [p for p in source.get('B',[]) if p['platform'] in row['scope']]
            refs = set()
            for record in records:
                raw = record.get('raw',[])
                refs.update([raw] if isinstance(raw,str) else raw)
            for ref in refs:
                if ref not in envelope_times:
                    path = runtime/ref
                    envelope_times[ref] = load(path).get('read_utc') if path.is_file() else None
            times = [envelope_times[ref] for ref in refs if envelope_times[ref]]
            audit.append(dict(field=row['date']+'/'+field, value=row[field], grade='E1',
                url=row['rpc'], read_utc=max(times) if times else None,
                raw=sorted(refs), blocks=[row['start_block'],row['end_block']], scope=row['scope']))
    (runtime/'customer_metrics_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    with (runtime/'customer_metrics_audit.tsv').open('w',newline='') as f:
        writer=csv.writer(f,delimiter='\t');writer.writerow(['字段','值','证据级','具体页面或接口URL','读取时间UTC'])
        for fact in audit:writer.writerow([fact['field'],'U' if fact['value'] is None else fact['value'],fact['grade'],fact['url'] or 'U',fact['read_utc'] or 'U'])
    template = (HERE / 'customer-dashboard.html').read_text()
    embedded = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c')
    css = re.search(r'<style>([\s\S]*?)</style>', template).group(1)
    js = re.search(r'<script>([\s\S]*?)</script>', template).group(1).replace('/*__AGENT_DATA__*/null', "JSON.parse(document.getElementById('agent-data').textContent)")
    html = re.sub(r'<style>[\s\S]*?</style>', '<link rel="stylesheet" href="./style.css">', template)
    html = re.sub(r'<script>[\s\S]*?</script>', lambda _: '<script type="application/json" id="agent-data">'+embedded+'</script><script src="./app.js" defer></script>', html)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.agent-export-') as tmp:
        stage = Path(tmp)
        (stage / '.agent-id-generated').write_text('owned namespace\n')
        (stage / 'index.html').write_text(html)
        (stage / 'app.js').write_text(js)
        (stage / 'style.css').write_text(css)
        (stage / 'core_series.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        (stage / 'health.json').write_text(json.dumps(dict(data_through_utc=rows[-1]['date'],
              collection_status=run.get('status'), identity_reconciliation=load(runtime / 'data/reconciliation.json')['status'],
              complete_platforms=rows[-1]['scope'], chart_count=6, U_policy='unknown is not zero'), ensure_ascii=False, indent=2))
        files = {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in stage.rglob('*') if p.is_file()}
        (stage / 'asset_manifest.json').write_text(json.dumps(files, indent=2))
        if any(p.stat().st_size > 25 * 1024**2 for p in stage.rglob('*') if p.is_file()):
            raise ValueError('有文件超过Cloudflare Pages 25 MiB单文件限制')
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(stage, output)
    print(json.dumps(dict(output=str(output), through=rows[-1]['date'], rows=len(rows), charts=6), ensure_ascii=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    export(args.runtime, args.output)
