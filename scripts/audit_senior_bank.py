"""Report actual textbook/chapter coverage; never treat claimed coverage as proof."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.course_catalog import BOOKS, GOALS
from app.question_annotation import Annotation
from app.senior_bank import prepare_batch, digest, batch_files, validate_peer
from app.bank import content_hash


def audit(include_foundations=False):
    records, decisions, errors = [], Counter(), []
    peers={}
    for filename,peerfile in batch_files(include_foundations):
        path = ROOT / 'app/data' / filename
        if not path.exists():
            errors.append(f'{filename}: batch missing');continue
        try:
            value=json.loads(path.read_text());qs,_=prepare_batch(value)
            peer=json.loads((ROOT/'app/data'/peerfile).read_text())
            validate_peer(value,peer)
            peers.update({p['question_id']:p for p in peer.get('items',[])})
            records.extend(qs)
            decisions.update(i['decision'] for i in value['items'])
        except (OSError,ValueError,KeyError,TypeError) as e:
            errors.append(f'{filename}: {e}')
    unique, deduplicated = {}, []
    for q in records:
        if q['status']=='quarantine':continue
        key=content_hash(q)
        if key in unique:
            errors.append('duplicate content: '+unique[key]['annotation_source_question_id']+' / '+q['annotation_source_question_id'])
        else:
            unique[key]=q;deduplicated.append(q)
    records=deduplicated
    books=[]
    for b in BOOKS:
        if b.get('stage')!='senior':continue
        qs=[q for q in records if q.get('curriculum_book_id')==b['id'] and q['status']!='quarantine']
        units=[]
        for unit in b['units']:
            candidates=[q for q in qs if any(GOALS[g]['unit_id']==unit['id'] for g in q.get('curriculum_goal_ids',[]) if g in GOALS)]
            peer_checked=[]
            for q in candidates:
                p=peers.get(q['annotation_source_question_id'],{})
                if (p.get('decision')=='passed' and p.get('source_sha256')==q['annotation_source_sha256']
                        and p.get('annotation_sha256')==digest(Annotation.model_validate(q['annotation']).model_dump())):
                    peer_checked.append(q)
            units.append({'id':unit['id'],'name':unit['name'],'selected':len(candidates),
                'peer_checked':len(peer_checked),'minimum':5,'remaining':max(0,5-len(peer_checked))})
        formats=Counter(q['annotation']['response_format'] for q in qs)
        books.append({'id':b['id'],'title':b['title'],'selected':len(qs),
            'formats':dict(formats),'difficulty':dict(Counter(q['difficulty'] for q in qs)),
            'units':units})
    result={'schema_version':1,'scope':'senior math BNU compulsory/selective; physics PEP compulsory/selective',
        'decisions':dict(decisions),'errors':errors,'books':books,
        'complete':not errors and all(u['remaining']==0 for b in books for u in b['units'])
            and len(books)==10 and all(b['formats'].get('single_choice',0)+b['formats'].get('multiple_choice',0)>0
                and any(b['formats'].get(k,0)>0 for k in ('fill_blank','calculation','application','proof','composite','short_answer')) for b in books),
        'note':'Five peer-checked questions per chapter are a minimum content gate, not full skill/experiment mastery certification.'}
    if include_foundations:
        from app.senior_foundations import audit_foundations
        foundation=audit_foundations(ROOT/'app/data')
        result['foundations']=foundation
        result['complete']=result['complete'] and foundation['complete']
        result['errors'].extend(foundation['errors'])
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path)
    p.add_argument('--include-foundations',action='store_true')
    p.add_argument('--require-complete',action='store_true')
    args=p.parse_args();value=audit(args.include_foundations)
    if args.output is None:
        folder='senior-foundations-20261016' if args.include_foundations else 'senior-20261015'
        args.output=ROOT/'data/annotations'/folder/'coverage.json'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    temp=args.output.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2));temp.replace(args.output)
    summary={'selected':sum(b['selected'] for b in value['books']),
        'chapters':sum(len(b['units']) for b in value['books']),
        'chapters_ready':sum(u['remaining']==0 for b in value['books'] for u in b['units']),
        'errors':value['errors'],'complete':value['complete']}
    if args.include_foundations:
        f=value['foundations'];summary.update(foundation_questions=f['selected'],
            foundation_skills=len(f['skills']),foundation_skills_ready=sum(s['remaining']==0 for s in f['skills']),
            curriculum_goals=len(f['goals']),curriculum_goals_ready=sum(g['skills']>=2 and
                g['skills_ready']==g['skills'] for g in f['goals']))
    print(json.dumps(summary,ensure_ascii=False))
    if args.require_complete and not value['complete']:raise SystemExit(1)
