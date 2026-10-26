"""Apply the checked cross-audit findings to Luna batch outputs, before import."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.math_annotations import Entry
from app.question_annotation import Annotation


def reconcile(entries, findings):
    records={e.question_id:e.model_copy(deep=True) for e in entries}
    for finding in findings:
        qid=finding['question_id'];e=records.get(qid)
        if not e or e.source_sha256!=finding['source_sha256']:
            raise ValueError('复核依据与标注来源不一致：'+qid)
        action=finding['action']
        if action=='exclude':
            e.decision='exclude';e.reason='交叉复核剔除：'+finding['reason'];e.annotation=None
        elif action in {'needs_review','correct_annotation'}:
            if e.annotation is None:raise ValueError('不能把已剔除题重新放开：'+qid)
            a=e.annotation.model_dump()
            if action=='correct_annotation':
                patch=finding.get('annotation_patch',{})
                if set(patch)-{'fine_types','parts'}:raise ValueError('不支持的标注修正字段')
                a.update(patch)
            else:
                a['review']['issues']=list(dict.fromkeys([*a['review']['issues'],'cross_audit_pending']))
            note='交叉复核：'+finding['reason']
            if note not in a['review']['notes']:
                a['review']['notes']=(a['review']['notes']+'\n'+note).strip()
            e.annotation=Annotation.model_validate(a)
        elif action!='no_issue_found':raise ValueError('未知复核处理动作')
        if e.annotation and e.annotation.review.status!='candidate':raise ValueError('复核不能自动人工审核')
    return records


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,default=ROOT/'data/annotations/math-20261011')
    p.add_argument('--findings',type=Path,default=ROOT/'app/data/math_annotation_cross_audit.json')
    args=p.parse_args();shards={}
    for path in sorted(args.directory.glob('output-*.jsonl')):
        shards[path]=[Entry.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()]
    if not shards:raise ValueError('没有候选分片')
    all_entries=[e for shard in shards.values() for e in shard]
    if len({e.question_id for e in all_entries})!=len(all_entries):raise ValueError('分片题号重复')
    records=reconcile(all_entries,json.loads(args.findings.read_text()))
    for path,entries in shards.items():
        temp=path.with_suffix('.tmp')
        temp.write_text('\n'.join(records[e.question_id].model_dump_json() for e in entries)+'\n')
        temp.replace(path)
    print(json.dumps({'total':len(records),'annotated':sum(e.decision=='annotate' for e in records.values()),'excluded':sum(e.decision=='exclude' for e in records.values())}))


if __name__=='__main__':main()
