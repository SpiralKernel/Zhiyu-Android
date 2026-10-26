"""Fetch bounded senior physics supplements using the existing guest quota.

Never rotates identities or imports a question. Raw responses, filters and hashes
remain in ignored data/. Existing files make retries resumable without new usage.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import zipfile

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://tizhuang.qcscience.cc/api'


def public_sources(download=False):
    manifest=json.loads((ROOT/'app/data/senior_source_manifests.json').read_text())
    checked=0
    with httpx.Client(timeout=120,follow_redirects=True) as client:
        for source in manifest['sources']:
            base=ROOT/'data/sources'/source['id']
            missing=[]
            for entry in source['files']:
                path=Path(entry['path'])
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('来源缓存路径无效')
                target=base/path
                if target.exists():
                    if hashlib.sha256(target.read_bytes()).hexdigest()!=entry['sha256']:
                        raise ValueError('来源文件指纹不符：'+str(target))
                    checked+=1
                else:missing.append(entry)
            if missing and not download:
                raise FileNotFoundError(f"{source['id']} 缺少{len(missing)}份固定来源文件；使用 --source public 下载")
            blobs={}
            if missing and source.get('archive'):
                archive=source['archive'];r=client.get(archive['url']);r.raise_for_status()
                if hashlib.sha256(r.content).hexdigest()!=archive['sha256']:
                    raise ValueError('来源归档指纹不符')
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    names={str(Path(*Path(n).parts[1:])):n for n in z.namelist() if not n.endswith('/')}
                    for entry in missing:blobs[entry['path']]=z.read(names[entry['path']])
            elif missing:
                for entry in missing:
                    r=client.get(entry['url']);r.raise_for_status();blobs[entry['path']]=r.content
            for entry in missing:
                if hashlib.sha256(blobs[entry['path']]).hexdigest()!=entry['sha256']:
                    raise ValueError('下载内容与固定清单不符：'+entry['path'])
            for entry in missing:
                target=base/entry['path'];target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(blobs[entry['path']]);checked+=1
            # Adapters can replay the same metadata on a clean local checkout.
            meta=base/'DOWNLOAD.json'
            if download and not meta.exists():
                meta.write_text(json.dumps(source,ensure_ascii=False,indent=2))
    print('固定来源文件校验通过：',checked)


def fetch(directory, credential, per_chapter=2):
    trial = json.loads(credential.read_text())
    headers = {'X-Trial-Token':trial['trial_token']}
    directory.mkdir(parents=True, exist_ok=True)
    count = 0
    with httpx.Client(timeout=40) as client:
        for kind, grade in [('compulsory',10100),('compulsory',10200),('compulsory',10300),
                            ('selective',30100),('selective',30200),('selective',30300)]:
            meta = directory / f'chapters-{grade}.json'
            if not meta.exists():
                r=client.get(BASE+'/v1/meta/chapters',params={'subject_id':8,'grade_id':grade,'edition_id':85})
                r.raise_for_status();meta.write_text(r.text)
            rows = [r for r in json.loads(meta.read_text()) if r['parent_id']==0
                    and r['grade_id']==grade and r['edition_id']==85 and r['subject_id']==8]
            for row in rows:
                target = directory / f"questions-{grade}-{row['id']}.json"
                if target.exists():
                    continue
                if count + per_chapter > 54:
                    raise ValueError('本次最多申请54题，不轮换访客身份')
                params={'subject_id':8,'phase_id':3,'grade_id':grade,'edition_id':85,
                        'chapter_id':row['id'],'has_images':'false','limit':per_chapter,'random_order':'true'}
                r=client.get(BASE+'/v1/trial/questions',params=params,headers=headers)
                if r.status_code in (401,403,429):
                    print('停止下载，服务端状态',r.status_code,'；保留断点，不更换身份')
                    return
                r.raise_for_status()
                payload={'retrieved_at':datetime.now(timezone.utc).isoformat(),
                    'url':BASE+'/v1/trial/questions','filters':params,'chapter':row,
                    'curriculum_book_id':f"physics-senior-{kind}-{grade//100%10}",
                    'response_sha256':hashlib.sha256(r.content).hexdigest(), 'result':r.json()}
                target.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
                count+=per_chapter
                print(grade,row['name'],'返回',len(payload['result'].get('items',[])),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=['verify','public','tizhuang'],default='verify')
    parser.add_argument('--directory',type=Path,default=ROOT/'data/source-cache/tizhuang-senior-20261015')
    parser.add_argument('--credential',type=Path,default=ROOT/'data/source-cache/tizhuang-20261015/trial.json')
    args=parser.parse_args()
    if args.source=='tizhuang':fetch(args.directory,args.credential)
    else:public_sources(download=args.source=='public')
