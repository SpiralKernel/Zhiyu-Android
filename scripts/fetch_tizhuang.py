"""Fetch a bounded PEP-2024 chapter sample; raw cache only, never auto-publish.
Run from the repository root. Guest credentials stay in ignored data/, mode 0600.
"""
import argparse
import json
import secrets
from pathlib import Path
import httpx

BASE='https://tizhuang.qcscience.cc/api'

def fetch(directory,per_chapter=1):
    directory.mkdir(parents=True,exist_ok=True)
    cache=directory/'trial.json'
    client=httpx.Client(timeout=35)
    if cache.exists():trial=json.loads(cache.read_text())
    else:
        cid=secrets.token_urlsafe(24)
        response=client.post(BASE+'/v1/trials',headers={'X-Anonymous-Client-ID':cid})
        response.raise_for_status();trial=response.json();trial['anonymous_client_id']=cid
        cache.write_text(json.dumps(trial));cache.chmod(0o600)
    headers={'X-Trial-Token':trial['trial_token']}
    requests=[]
    for sid,gid in [(8,301),(8,302),(8,400),(2,201),(2,202)]:
        meta=directory/f'chapters-{sid}-{gid}.json'
        if not meta.exists():
            r=client.get(BASE+'/v1/meta/chapters',params={'subject_id':sid,'grade_id':gid,'edition_id':142});r.raise_for_status();meta.write_text(r.text)
        rows=json.loads(meta.read_text());seen=set()
        for row in rows:
            if row['parent_id'] or row['grade_id']!=gid or not row['name'].strip().startswith('第'):continue
            name=row['name'].replace(' ','')
            if name in seen:continue
            seen.add(name)
            requests.append((sid,gid,row))
    if len(requests)*per_chapter>90:raise ValueError('最多90道，保留额度，不轮换游客身份')
    for sid,gid,row in requests:
        path=directory/f"questions-{sid}-{gid}-{row['id']}.json"
        if path.exists():continue
        params={'subject_id':sid,'grade_id':gid,'edition_id':142,'chapter_id':row['id'],'has_images':'false','limit':per_chapter,'random_order':'true'}
        r=client.get(BASE+'/v1/trial/questions',params=params,headers=headers)
        if r.status_code in (401,429):
            print('stop',r.status_code,'credential/quota; no retry');break
        r.raise_for_status();payload={'retrieved_at':'2026-10-15','url':BASE+'/v1/trial/questions','filters':params,'chapter':row,'result':r.json()}
        path.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
        print(sid,gid,row['name'],'returned',len(payload['result'].get('items',[])),flush=True)
    client.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=Path('data/source-cache/tizhuang-20261015'));parser.add_argument('--per-chapter',type=int,choices=(1,2),default=1)
    args=parser.parse_args();fetch(args.directory,args.per_chapter)
