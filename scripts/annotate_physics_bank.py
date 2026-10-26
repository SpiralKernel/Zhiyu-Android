"""Export source questions for Luna without reading the student database."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.physics_bank import source_records
from app.question_annotation import Annotation,source_fingerprint


def export(directory,source_root,*,include_ceval=True):
    directory=Path(directory)
    if any((directory/f'input-{i}.jsonl').exists() for i in range(3)):
        raise ValueError('输入分片已存在，禁止覆盖审核依据')
    directory.mkdir(parents=True,exist_ok=True)
    counts=[0,0,0];files=[];seen=set()
    try:
        files=[(directory/f'input-{i}.jsonl').open('x') for i in range(3)]
        for q in source_records(source_root,include_ceval=include_ceval):
            if q['id'] in seen:raise ValueError('来源题号重复')
            seen.add(q['id'])
            i=2 if q['provenance']['dataset']=='ceval-physics' else int(hashlib.sha256(q['id'].encode()).hexdigest()[:8],16)%2
            files[i].write(json.dumps({'question_id':q['id'],'source_sha256':source_fingerprint(q),'question':q},ensure_ascii=False)+'\n')
            counts[i]+=1
        (directory/'schema.json').write_text(json.dumps(Annotation.model_json_schema(),ensure_ascii=False,indent=2))
        return counts
    finally:
        for f in files:f.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['export'])
    p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--source-root',type=Path,default=ROOT/'data/sources')
    args=p.parse_args()
    print(json.dumps({'counts':export(args.directory,args.source_root),'directory':str(args.directory.resolve())}))


if __name__=='__main__':main()
