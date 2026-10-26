"""Senior model evidence and source hashes must never turn into teacher proof."""
import copy
import json

import pytest

from app.db import connect, initialize
from app.course_catalog import BOOKS
from app.question_annotation import source_fingerprint
from app.senior_bank import import_batch, prepare_batch, validate_peer, digest
from app.question_annotation import Annotation


def batch():
    b = next(b for b in BOOKS if b['id']=='math-senior-compulsory-1')
    goal = b['units'][0]['goals'][0]['id']
    q = {'id':'source:senior:fixture', 'subject':'math','stage':'senior','grade':10,'term':None,
        'stem':'已知集合A={1,2}，B={2,3}，求A与B的交集。','kind':'single_choice',
        'options':[{'key':'A','text':'{2}'},{'key':'B','text':'{1,2,3}'}],
        'answer':'A','steps':['来源旧解析'], 'difficulty':1,'knowledge_tags':['集合'],
        'type_tags':[],'status':'ready','issues':[],
        'provenance':{'dataset':'test','source_id':'fixture','url':'https://example.com/source','license':'test'}}
    a = {'response_format':'single_choice','knowledge':{'primary':['集合交集']},
        'fine_types':['按元素枚举求两集合交集'],'difficulty':{'level':1,'basis':'直接枚举共同元素','origin':'luna'},
        'curriculum':{'grade':10,'book_id':b['id'],'goal_ids':[goal],'scope_status':'candidate','basis':'与集合目标对应'},
        'answer_spec':{'mode':'choice','accepted_answers':['A'],'equivalence':'exact'},
        'parts':[{'id':'p1','prompt':q['stem'],'reference_answer':'A','solution_steps':['共同元素只有2，所以选A。'],
            'rubric':[{'id':'r1','description':'取两集合共同的元素2'}]}],
        'review':{'status':'candidate','method':'item_read','answer_status':'checked'},
        'origin':{'model':'gpt-6-luna','batch_id':'test'}}
    return {'batch_id':'test','items':[{'question_id':q['id'],'source_sha256':source_fingerprint(q),
        'question':q,'decision':'passed','rationale':'逐个比较集合元素，唯一共同元素是2，与A一致。',
        'independent_solution':'A∩B={2}','source_conflicts':[],'remaining_issues':[], 'annotation':a}]}


def test_source_retained_without_forging_teacher_or_independent_score(tmp_path):
    path=tmp_path/'db.sqlite3';initialize(path)
    value=batch()
    with connect(path) as db:
        result=import_batch(db,value);assert result['inserted']==1
    with connect(path) as db:
        result=import_batch(db,value);assert result['inserted']==0
        q=json.loads(db.execute("SELECT data FROM bank_questions WHERE stage='senior'").fetchone()[0])
        assert q['quality']['source_snapshot']==value['items'][0]['question']
        assert q['provenance']['teacher_reviewed'] is False
        from app.diagnostic_core import trusted
        assert not trusted(q)
        assert q['can_practice'] and q['steps']==['共同元素只有2，所以选A。']
        assert db.execute('SELECT count(*) FROM course_question_links WHERE question_id=?',(q['id'],)).fetchone()[0]==1


@pytest.mark.parametrize('mutation',['answer','figure','conflict','goal','teacher','empty_rubric','source','controls','leak','duplicate_option'])
def test_reject_stale_or_unchecked_whole_batch(mutation,tmp_path):
    value=batch();i=value['items'][0]
    if mutation=='answer':i['question']['answer']='B'
    if mutation=='figure':i['question']['has_missing_assets']=True
    if mutation=='conflict':i['source_conflicts']=['推导与来源答案不同']
    if mutation=='goal':i['annotation']['curriculum']['goal_ids']=['physics-8-1:u1:g1']
    if mutation=='teacher':i['annotation']['review']['method']='teacher'
    if mutation=='empty_rubric':i['annotation']['parts'][0]['rubric']=[]
    if mutation=='source':i['source_sha256']='0'*64
    if mutation=='controls':i['annotation']['parts'][0]['solution_steps']=['错误转义\x0crac{1}{2}']
    if mutation=='leak':
        i['question']['stem']+='【答案】A'
        i['source_sha256']=source_fingerprint(i['question'])
    if mutation=='duplicate_option':
        i['question']['options'][1]['text']=i['question']['options'][0]['text']
        i['source_sha256']=source_fingerprint(i['question'])
    with pytest.raises(ValueError):prepare_batch(value)


def test_excluded_item_is_quarantined_not_deleted(tmp_path):
    value=batch();i=value['items'][0];i.update(decision='excluded',annotation=None,rationale='缺少图示，条件不足')
    i['question']['has_missing_assets']=True
    records,_=prepare_batch(value)
    assert records[0]['status']=='quarantine' and records[0]['quality']['source_snapshot']==i['question']


def test_peer_binding_rejects_stale_hash_and_pending_decisions():
    value=batch();i=value['items'][0]
    p={'question_id':i['question_id'],'source_sha256':i['source_sha256'],
        'annotation_sha256':digest(Annotation.model_validate(i['annotation']).model_dump()),
        'decision':'passed','reason':'共同元素只有2，与选项一致','independent_solution':'{1,2}∩{2,3}={2}'}
    validate_peer(value,{'items':[p]})
    for field,v in [('decision','pending'),('source_sha256','0'*64),('annotation_sha256','0'*64)]:
        bad=copy.deepcopy(p);bad[field]=v
        with pytest.raises(ValueError):validate_peer(value,{'items':[bad]})


def test_distinct_variable_case_is_not_collapsed_as_duplicate_options():
    value=batch();i=value['items'][0]
    i['question']['options']=[{'key':'A','text':'F/q'},{'key':'B','text':'F/Q'}]
    i['source_sha256']=source_fingerprint(i['question'])
    assert len(prepare_batch(value)[0])==1


def test_incomplete_quarantined_source_row_can_be_stored_for_audit(tmp_path):
    value=batch();i=value['items'][0]
    i.update(decision='pending',annotation=None,rationale='原题条件不足，不能核验答案')
    for field in ['difficulty','steps','knowledge_tags','type_tags']:
        i['question'].pop(field)
    i['source_sha256']=source_fingerprint(i['question'])
    path=tmp_path/'quarantine.sqlite3';initialize(path)
    with connect(path) as db:assert import_batch(db,value)['quarantine']==1
    with connect(path) as db:
        q=json.loads(db.execute("SELECT data FROM bank_questions WHERE stage='senior'").fetchone()[0])
        assert not q['can_practice'] and q['quality']['source_snapshot']==i['question']


def test_frozen_release_loads_all_books_and_rejects_changed_files(tmp_path,monkeypatch):
    import hashlib
    from pathlib import Path
    import app.senior_bank as senior
    source=Path(__file__).resolve().parents[1]/'app/data'
    data=tmp_path/'release';data.mkdir()
    names=['senior_math_luna.json','senior_physics_luna.json','senior_peer_review.json',
           'senior_curriculum.json','senior_source_manifests.json']
    for name in names:(data/name).write_bytes((source/name).read_bytes())
    release={'schema_version':1,'ready_for_import':True,
             'files':{n:hashlib.sha256((data/n).read_bytes()).hexdigest() for n in names}}
    (data/'senior_release.json').write_text(json.dumps(release))
    monkeypatch.setattr(senior,'DATA',data)
    path=tmp_path/'release.sqlite3';initialize(path)
    with connect(path) as db:
        senior.seed(db)
        rows=db.execute("SELECT id,data FROM bank_questions WHERE stage='senior'").fetchall()
        playable=[json.loads(r['data']) for r in rows if json.loads(r['data']).get('can_practice')]
        assert len(playable)==281
        assert len({q['curriculum_book_id'] for q in playable})==10
        before=dict((r['id'],r['data']) for r in rows)
        senior.seed(db)
        assert before==dict(db.execute("SELECT id,data FROM bank_questions WHERE stage='senior'"))
    changed=data/'senior_math_luna.json'
    changed.write_text(changed.read_text()+'\n')
    with connect(path) as db:
        with pytest.raises(ValueError,match='发生变化'):senior.seed(db)
        assert before==dict(db.execute("SELECT id,data FROM bank_questions WHERE stage='senior'"))
