"""A chapter count cannot substitute for a reviewed fine-skill inventory."""
import copy
import json
from pathlib import Path

import pytest

from app import senior_foundations as foundations
from app.question_annotation import Annotation, source_fingerprint
from app.senior_bank import digest


def inventory(path,monkeypatch):
    source=Path(__file__).resolve().parents[1]/'app/data'
    peers=[];goals={}
    for subject in ('math','physics'):
        original=json.loads((source/f'senior_{subject}_luna.json').read_text())
        first=next(i for i in original['items'] if i['decision']=='passed')
        goal=first['annotation']['curriculum']['goal_ids'][0]
        goals[goal]=foundations.GOALS[goal]
        skills=[];items=[]
        for s in range(2):
            sid=f'{subject}:skill:{s}';qids=[]
            for n in range(2):
                item=copy.deepcopy(first);qid=f'fixture:{subject}:{s}:{n}'
                qids.append(qid);item['question_id']=qid
                item['question']['id']=qid
                item['question']['stem']+=f'（测试独立记录{s}-{n}）'
                item['source_sha256']=source_fingerprint(item['question'])
                item['annotation']['curriculum']['goal_ids']=[goal]
                item['annotation']['difficulty']['level']=1
                item['foundation_skill_ids']=[sid]
                items.append(item)
                peers.append({'question_id':qid,'decision':'passed','source_sha256':item['source_sha256'],
                    'annotation_sha256':digest(Annotation.model_validate(item['annotation']).model_dump()),
                    'reason':'独立验证测试记录','independent_solution':'测试用途，不作真实教学证据。'})
            skills.append({'id':sid,'name':f'测试技能{s}','book_id':goals[goal]['book_id'],
                'goal_ids':[goal],'requirement':'测试范围校验','question_ids':qids})
        (path/f'senior_{subject}_foundations.json').write_text(json.dumps({'batch_id':'fixture-'+subject,'items':items}))
        (path/f'senior_{subject}_foundation_skills.json').write_text(json.dumps({'skills':skills}))
    (path/'senior_foundations_peer_review.json').write_text(json.dumps({'items':peers}))
    monkeypatch.setattr(foundations,'GOALS',goals)


def change(path,name,fn):
    p=path/name;value=json.loads(p.read_text());fn(value);p.write_text(json.dumps(value))


def test_complete_requires_two_reviewed_tasks_per_fine_skill(tmp_path,monkeypatch):
    inventory(tmp_path,monkeypatch)
    report=foundations.audit_foundations(tmp_path)
    assert report['complete'] and not report['errors']
    assert report['selected']=={'math':4,'physics':4}
    assert all(g['skills_ready']==2 for g in report['goals'])


@pytest.mark.parametrize('problem',['missing_question','asymmetric','wrong_book','stale_peer',
    'missing_goal','duplicate_question','prerequisite_only'])
def test_cannot_claim_coverage_with_bad_links_or_stale_evidence(tmp_path,monkeypatch,problem):
    inventory(tmp_path,monkeypatch)
    skills='senior_math_foundation_skills.json'
    if problem=='missing_question':
        change(tmp_path,skills,lambda v:v['skills'][0]['question_ids'].pop())
    elif problem=='asymmetric':
        change(tmp_path,skills,lambda v:v['skills'][0]['question_ids'].append(v['skills'][1]['question_ids'][0]))
    elif problem=='wrong_book':
        change(tmp_path,skills,lambda v:v['skills'][0].update(book_id='physics-senior-compulsory-1'))
    elif problem=='stale_peer':
        change(tmp_path,'senior_foundations_peer_review.json',lambda v:v['items'][0].update(annotation_sha256='0'*64))
    elif problem=='missing_goal':
        goals=dict(foundations.GOALS)
        extra=copy.deepcopy(next(iter(goals.values())));extra['name']='尚无题的目标'
        goals['fixture-uncovered']=extra;monkeypatch.setattr(foundations,'GOALS',goals)
    elif problem=='prerequisite_only':
        change(tmp_path,skills,lambda v:[s.update(role='prerequisite') for s in v['skills']])
    else:
        def duplicate(v):
            a,b=v['items'][:2];b['question']['stem']=a['question']['stem']
            b['source_sha256']=source_fingerprint(b['question'])
            change(tmp_path,'senior_foundations_peer_review.json',lambda p:next(i for i in p['items'] if i['question_id']==b['question_id']).update(source_sha256=b['source_sha256']))
        change(tmp_path,'senior_math_foundations.json',duplicate)
    assert not foundations.audit_foundations(tmp_path)['complete']


def test_release_validates_last_batch_before_importing_anything(tmp_path,monkeypatch):
    import hashlib
    from app import senior_bank
    from app.db import connect,initialize
    inventory(tmp_path,monkeypatch)
    source=Path(__file__).resolve().parents[1]/'app/data'
    for name in senior_bank.BASE_RELEASE_FILES:
        (tmp_path/name).write_bytes((source/name).read_bytes())
    # The release file hashes are valid; the final batch's review is stale.
    change(tmp_path,'senior_foundations_peer_review.json',lambda v:v['items'][-1].update(source_sha256='0'*64))
    names=senior_bank.BASE_RELEASE_FILES|senior_bank.FOUNDATION_RELEASE_FILES
    release={'schema_version':2,'ready_for_import':True,
        'files':{n:hashlib.sha256((tmp_path/n).read_bytes()).hexdigest() for n in names}}
    (tmp_path/'senior_release.json').write_text(json.dumps(release))
    monkeypatch.setattr(senior_bank,'DATA',tmp_path)
    path=tmp_path/'atomic.sqlite3';initialize(path)
    with connect(path) as db:
        with pytest.raises(ValueError,match='独立复核'):senior_bank.seed(db)
        assert db.execute("SELECT count(*) FROM bank_questions WHERE stage='senior'").fetchone()[0]==0
