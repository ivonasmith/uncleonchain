"""Validate saved artifacts without making any network requests."""
import csv
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
from PIL import Image

def verify(root,quiet=False):
    root=Path(root);checks=[]
    def check(name,ok,detail):checks.append(dict(check=name,status='PASS' if ok else 'FAIL',detail=detail))
    urls=set();read_times=set();manifest=[]
    for p in sorted((root/'raw').rglob('*')):
        if not p.is_file():continue
        blob=p.read_bytes();manifest.append(dict(path=str(p.relative_to(root)),sha256=hashlib.sha256(blob).hexdigest(),bytes=len(blob)))
        if p.suffix=='.json':
            try:r=json.loads(blob)
            except Exception:continue
            if isinstance(r,dict) and ((r.get('attempts')) or (r.get('read_utc') and (r.get('status') or r.get('error')))):
                urls.add(r.get('url'));read_times.add(r.get('read_utc'))
    (root/'raw_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    with (root/'facts.tsv').open() as f:
        reader=csv.DictReader(f,delimiter='\t');columns=reader.fieldnames;rows=list(reader)
    check('五列事实表',columns==['字段','值','证据级','具体页面或接口URL','读取时间UTC'],str(len(rows))+' 行')
    bad_grade=[r['字段'] for r in rows if r['证据级'] not in ['E1','E2','E3','E4']]
    check('证据级仅E1至E4',not bad_grade,str(bad_grade[:5]))
    bad_url=[r['字段'] for r in rows for u in r['具体页面或接口URL'].split(' ; ') if u!='U' and u not in urls]
    check('所有证据URL均有本次实际请求信封',not bad_url,str(bad_url[:5]))
    invalid_time=[]
    for r in rows:
        if r['读取时间UTC']=='U':continue
        try:
            value=dt.datetime.fromisoformat(r['读取时间UTC'].replace('Z','+00:00'))
            if value.utcoffset()!=dt.timedelta(0) or r['读取时间UTC'] not in read_times:invalid_time.append(r['字段'])
        except ValueError:invalid_time.append(r['字段'])
    check('读取时间为UTC且非报告生成时间替代',not invalid_time,str(invalid_time[:5]))
    facts=json.loads((root/'facts.json').read_text());bad_raw=[p for r in facts for p in r.get('raw',[]) if not (root/p).is_file()]
    check('事实raw引用存在',not bad_raw,str(bad_raw[:5]))
    state=json.loads((root/'state.json').read_text());run=json.loads((root/'last_run.json').read_text());dates=sorted(state['days'])
    check('所有日行早于本次UTC日',all(d<run['run_date'] for d in dates),str(dates))
    missing=[]
    if dates:
        cursor=dt.date.fromisoformat(dates[0]);end=dt.date.fromisoformat(run['run_date'])
        while cursor<end:
            if cursor.isoformat() not in dates:missing.append(cursor.isoformat())
            cursor+=dt.timedelta(days=1)
    check('已观察起点到昨日无静默缺日',not missing,str(missing))
    images=list((root/'charts').glob('*.png'));bad_images=[]
    for p in images:
        try:
            with Image.open(p) as im:im.verify()
        except Exception:bad_images.append(p.name)
    check('8张PNG完整可解码',len(images)==8 and not bad_images,str(bad_images))
    body=(root/'dashboard.html').read_text()
    import re
    srcs=re.findall(r'<(?:img|script)[^>]+src=["\']([^"\']+)',body)
    check('离线看板图像自包含',len(srcs)==8 and all(s.startswith('data:image/png;base64,') for s in srcs),'无远程图像或脚本依赖')
    if run.get('network_requests')==0 and run.get('cache_hits',0)>0:check('缓存重算不重复请求',True,'network_requests=0; cache_hits='+str(run.get('cache_hits')))
    else:checks.append(dict(check='缓存重算不重复请求',status='NOT RUN',detail='本次为联网采集；离线重算日志另存，不将联网采集判为缓存失败'))
    import re
    tests=(root/'test_log.txt').read_text();count=re.search(r'Ran (\d+) tests',tests);check('至少9个合成测试全部通过',bool(count and int(count[1])>=9 and tests.rstrip().endswith('OK')),tests[-90:])
    payload=dict(read_utc=dt.datetime.now(dt.timezone.utc).isoformat(),checks=checks,raw_files=len(manifest),U_count=sum(r['值']=='U' for r in rows),status='PASS' if all(c['status'] in ['PASS','NOT RUN'] for c in checks) else 'FAIL',scope='文件、证据引用与缓存校验；不代表缺失数据或采集达标检查通过')
    (root/'artifact_verification.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    from report import reading_html,html_table
    (root/'artifact_verification.html').write_text(reading_html('保存文件与缓存校验','<p>'+html.escape(payload['scope'])+'</p><p><a href="dashboard.html">返回看板</a></p>'+html_table(checks,['check','status','detail'])))
    if not quiet:print(json.dumps(payload,ensure_ascii=False,indent=2))
    return payload

if __name__=='__main__':verify(Path(__file__).parent)
