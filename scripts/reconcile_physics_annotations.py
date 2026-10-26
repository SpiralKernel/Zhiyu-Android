"""Replay source-pinned physics cross-audits without changing original answers."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.math_annotations import load_entries
from scripts.reconcile_math_annotations import reconcile


def main():
    directory=ROOT/'data/annotations/physics-20261012'
    paths=sorted(directory.glob('output-*.jsonl'))
    entries=load_entries(paths)
    findings=[]
    for name in ('physics_annotation_cross_audit.json','physics_annotation_cross_audit_1.json',
                 'physics_annotation_cross_audit_2.json','physics_annotation_parent_audit.json'):
        findings.extend(json.loads((ROOT/'app/data'/name).read_text()))
    result=reconcile(entries,findings)
    for path in paths:
        original=load_entries([path]);temporary=path.with_suffix('.next')
        temporary.write_text(''.join(result[e.question_id].model_dump_json()+'\n' for e in original))
        temporary.replace(path)
    print(json.dumps(dict(total=len(result),annotated=sum(e.decision=='annotate' for e in result.values()),
                         excluded=sum(e.decision=='exclude' for e in result.values()))))


if __name__=='__main__':main()
