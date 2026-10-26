"""Export only question content, never student data, for a three-shard Luna batch."""
import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config import Settings
from app.question_annotation import Annotation, source_fingerprint


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['export'])
    p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--database',type=Path)
    args=p.parse_args();folder=args.directory
    if any((folder/f'input-{i}.jsonl').exists() for i in range(3)):
        p.error('输入分片已存在，拒绝覆盖原始标注依据；请使用新批次目录')
    path=(args.database or Settings().database_path).resolve()
    folder.mkdir(parents=True,exist_ok=True);files=[];counts=[0,0,0]
    try:
        files=[(folder/f'input-{i}.jsonl').open('x') for i in range(3)]
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            for (raw,) in db.execute("SELECT data FROM bank_questions WHERE subject='math' AND stage='junior' AND status!='superseded' ORDER BY id"):
                q=json.loads(raw);i=int(hashlib.sha256(q['id'].encode()).hexdigest()[:8],16)%3
                files[i].write(json.dumps({'question_id':q['id'],'source_sha256':source_fingerprint(q),'question':q},ensure_ascii=False)+'\n')
                counts[i]+=1
        (folder/'schema.json').write_text(json.dumps(Annotation.model_json_schema(),ensure_ascii=False,indent=2))
        print(json.dumps({'counts':counts,'directory':str(folder.resolve())},ensure_ascii=False))
    finally:
        for f in files:f.close()


if __name__=='__main__':main()
