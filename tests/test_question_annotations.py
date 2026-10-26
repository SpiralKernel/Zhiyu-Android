import copy
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import bank, bank_ai
from app.annotation_grading import feedback_detail
from app.config import Settings
from app.db import connect, initialize
from app.main import create_app
from app.math_annotations import Entry, apply_batch, load_entries, iter_entries
from app.question_annotation import Annotation, source_fingerprint, validate_for_question


def question(qid='written', **changes):
    return dict(id=qid,subject='math',stage='junior',grade=7,term=1,stem='计算 1+2，写出过程。',kind='reference',
                options=[],answer='3',steps=['1+2=3。'],difficulty=1,knowledge_tags=['有理数加法'],type_tags=['有理数加法求值'],
                status='reference',provenance={'dataset':'annotation-test','source_id':qid},quality={'version':'test'},**changes)


def annotation(**changes):
    return Annotation.model_validate(dict(response_format='calculation',difficulty={'level':1,'basis':'一次加法'},
        curriculum={'grade':7,'term':1,'goal_ids':['math-7-1:u2:g1']},
        parts=[{'id':'p1','prompt':'计算 1+2。','reference_answer':'3','knowledge_tags':['有理数加法'],
                'type_tags':['有理数加法求值'],'points':2,'rubric':[{'id':'c1','description':'正确相加得到3','points':2}]}],
        grading={'mode':'ai_rubric','full_score':2},**changes)).model_dump()


def entry(q, *, decision='annotate', value=None, reason='形成候选标注'):
    return Entry(question_id=q['id'],source_sha256=source_fingerprint(q),decision=decision,reason=reason,
                 annotation=(value or annotation()) if decision=='annotate' else None)


@pytest.fixture
def db_path(tmp_path):
    path=tmp_path/'annotations.sqlite3';initialize(path)
    with connect(path) as db:bank.import_records(db,'annotation-test',[question()],{})
    return path


def test_annotation_rejects_bad_scores_duplicate_ids_and_cyclic_dependencies():
    a=annotation();a['parts'][0]['rubric'][0]['points']=1
    with pytest.raises(ValidationError):Annotation.model_validate(a)
    a=annotation();a['parts'][0]['depends_on']=['p1']
    with pytest.raises(ValidationError):Annotation.model_validate(a)
    a=annotation();a['parts'].append(copy.deepcopy(a['parts'][0]))
    with pytest.raises(ValidationError):Annotation.model_validate(a)
    a=annotation();a['parts'][0]['points']=float('nan')
    with pytest.raises(ValidationError):Annotation.model_validate(a)


def test_annotation_choice_compatibility_and_candidate_cannot_publish():
    with pytest.raises(ValueError):validate_for_question(annotation(),question(),published=True)
    q=question();q['kind']='single_choice'
    with pytest.raises(ValueError):validate_for_question(annotation(),q)


def test_batch_failure_is_atomic_and_rejects_stale_source(db_path):
    with connect(db_path) as db:
        bank.import_records(db,'annotation-test',[question('second')],{})
    with connect(db_path) as db:
        before=db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]
        stale=entry(question('second'));stale.source_sha256='0'*64
        with pytest.raises(ValueError):apply_batch(db,[entry(question()),stale],dry_run=False)
        assert db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]==before
        assert db.execute("SELECT status FROM bank_questions WHERE id='written'").fetchone()[0]=='reference'


def test_batch_rolls_back_snapshots_if_later_dataset_import_fails(db_path,monkeypatch):
    other=question('other');other.update(stem='计算2+3。',answer='5',provenance={'dataset':'other','source_id':'other'})
    with connect(db_path) as db:bank.import_records(db,'other',[other],{})
    original=bank.import_records
    def fail_second(db,dataset,records,manifest,**kwargs):
        if dataset=='other':raise RuntimeError('模拟第二个来源写入失败')
        return original(db,dataset,records,manifest,**kwargs)
    monkeypatch.setattr(bank,'import_records',fail_second)
    with connect(db_path) as db:
        with pytest.raises(RuntimeError):apply_batch(db,[entry(question()),entry(other)],dry_run=False)
        assert db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]==2
        assert all(json.loads(r[0]).get('annotation') is None for r in db.execute('SELECT data FROM bank_questions'))


def test_streaming_batch_rolls_back_flushed_snapshots_on_late_invalid_input(db_path,tmp_path,monkeypatch):
    from app import math_annotations
    monkeypatch.setattr(math_annotations,'BATCH_SIZE',1)
    q=question('other');q.update(stem='计算1+3。',answer='4')
    with connect(db_path) as db:bank.import_records(db,'annotation-test',[q],{})
    file=tmp_path/'stream.jsonl'
    file.write_text(entry(question()).model_dump_json()+'\n'+entry(q).model_dump_json()+'\ninvalid JSON\n')
    calls=[];original=bank.import_records
    def record_import(*args,**kwargs):
        calls.append(len(args[2]))
        return original(*args,**kwargs)
    monkeypatch.setattr(bank,'import_records',record_import)
    with connect(db_path) as db:
        with pytest.raises(ValueError):apply_batch(db,iter_entries([file]),dry_run=False)
        assert calls==[1,1]
        assert db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]==2
        assert all(json.loads(r[0]).get('annotation') is None for r in db.execute('SELECT data FROM bank_questions'))


def test_batch_idempotency_snapshot_history_and_source_reimport(db_path):
    q=question();e=entry(q)
    with connect(db_path) as db:
        w=bank.next_question(db,bank.Selection());row,stored=bank.get_attempt(db,w['attempt_id'])
        bank.finish(db,row,stored,'3','correct',.5)
    with connect(db_path) as db:
        assert apply_batch(db,[e],dry_run=True)['annotated']==1
        assert db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]==1
        assert apply_batch(db,[e],dry_run=False)['annotated']==1
    with connect(db_path) as db:
        assert apply_batch(db,[e],dry_run=False)['unchanged']==1
    with connect(db_path) as db:
        assert bank.import_records(db,'annotation-test',[q],{})['duplicates']==1
        rows=db.execute('SELECT data,status FROM bank_questions').fetchall()
        assert len(rows)==2
        current=json.loads(next(r['data'] for r in rows if r['status']!='superseded'))
        assert current['annotation']['review']['status']=='candidate'
        assert bank.evidence_identity(q)==bank.evidence_identity(current)
        old=json.loads(db.execute("SELECT data FROM bank_questions WHERE id='written'").fetchone()[0])
        assert 'annotation' not in old and old['answer']=='3'
        assert db.execute('SELECT count(*) FROM bank_attempts WHERE result IS NOT NULL').fetchone()[0]==1
        public=bank.public(current)
        assert 'answer' not in public
        assert set(public['annotation'])=={'schema_version','response_format','parts'}
        assert set(public['annotation']['parts'][0])=={'id','prompt'}


def test_exclusion_removes_practice_and_persists_across_source_reimport(db_path):
    e=entry(question(),decision='exclude',reason='参考解析与运算结果矛盾')
    with connect(db_path) as db:assert apply_batch(db,[e],dry_run=False)['excluded']==1
    with connect(db_path) as db:
        result=bank.import_records(db,'annotation-test',[question()],{})
        assert result['duplicates']==1
        assert bank.search(db,bank.Selection())['total']==0
        current=json.loads(db.execute("SELECT data FROM bank_questions WHERE status='quarantine'").fetchone()[0])
        assert current['annotation_exclusion']==e.reason and not current['can_practice']


def test_loader_rejects_duplicate_ids_and_fake_teacher_review(tmp_path):
    file=tmp_path/'batch.jsonl';e=entry(question()).model_dump_json()
    file.write_text(e+'\n'+e+'\n')
    with pytest.raises(ValueError):load_entries([file])
    e=entry(question()).model_dump();e['annotation']['review']['status']='reviewed'
    file.write_text(json.dumps(e)+'\n')
    with pytest.raises(ValueError):load_entries([file])


def test_cross_audit_exclusion_is_idempotent_and_source_pinned():
    from scripts.reconcile_math_annotations import reconcile
    e=entry(question());finding={'question_id':e.question_id,'source_sha256':e.source_sha256,'action':'exclude','reason':'解析有算术矛盾'}
    out=reconcile([e],[finding])
    assert out[e.question_id].decision=='exclude' and out[e.question_id].annotation is None
    assert reconcile(list(out.values()),[finding])==out
    finding['source_sha256']='0'*64
    with pytest.raises(ValueError):reconcile([e],[finding])


def assessment(**changes):
    return bank_ai.Assessment(transcribed_answer='1+2=3',verdict='correct',reason='相加结果为3',confidence='high',
        part_feedback=[{'part_id':'p1','verdict':'correct','reason':'结果正确','evidence_quote':'1+2=3'}],
        criterion_feedback=[{'part_id':'p1','criterion_id':'c1','verdict':'met','reason':'呈现结果','evidence_quote':'1+2=3'}],**changes)


def reviewed_question():
    q=question();q['annotation']=annotation();q['provenance']['teacher_reviewed']=True
    q['annotation']['review'].update(status='reviewed',method='teacher',answer_status='checked')
    return q


def test_candidates_never_produce_numeric_scores():
    q=question();q['annotation']=annotation()
    d=feedback_detail(q,assessment())
    assert d['score'] is None and d['full_score'] is None and d['annotation_review']=='candidate'
    assert feedback_detail(reviewed_question(),assessment())['score']==2


@pytest.mark.parametrize('mutation',['missing','unknown','duplicate','quote','partial','low','pending'])
def test_reviewed_rubric_requires_complete_unambiguous_verifiable_evidence(mutation):
    q=reviewed_question();a=assessment()
    if mutation=='missing':a.criterion_feedback=[]
    if mutation=='unknown':a.criterion_feedback[0].criterion_id='invented'
    if mutation=='duplicate':a.criterion_feedback*=2
    if mutation=='quote':a.criterion_feedback[0].evidence_quote='模型捏造的学生文字'
    if mutation=='partial':a.part_feedback[0].verdict='partial'
    if mutation=='low':a.confidence='low'
    if mutation=='pending':q['annotation']['review']['issues']=['rubric_pending']
    assert feedback_detail(q,a)['score'] is None


def test_ai_receives_rubric_and_edited_transcription_invalidates_score(db_path,monkeypatch):
    settings=Settings(auth_required=False,database_path=db_path,deepseek_api_key='test-only',_env_file=None)
    with connect(db_path) as db:
        q=reviewed_question();q['id']='rubric';q['stem']='计算 1+2 并说明加法过程。'
        bank.import_records(db,'annotation-test',[q],{})
    captured=[]
    async def fake(settings,messages,schema,vision=False):
        captured.append(messages);return assessment()
    monkeypatch.setattr(bank_ai,'request_json',fake)
    with TestClient(create_app(settings)) as client:
        w=client.post('/api/v1/bank/next',json={'question_id':'rubric'}).json()
        assert 'reference_answer' not in json.dumps(w['question']['annotation'])
        path=f"/api/v1/bank/attempts/{w['attempt_id']}"
        r=client.post(path+'/assess',data={'answer':'1+2=3'})
        assert r.status_code==200,r.text
        review=r.json();assert review['assessment']['grading_detail']['score']==2
        assert 'question_annotation' in captured[0][1]['content']
        result=client.post(path+'/confirm',json={'review_id':review['id'],'reviewed':True,'verdict':'correct',
            'transcribed_answer':'3','count_evidence':False}).json()
        assert result['explanation']['grading_detail'] is None and result['explanation']['feedback_stale']
        assert result['evidence_weight']==0 and result['annotation']['parts'][0]['reference_answer']=='3'
