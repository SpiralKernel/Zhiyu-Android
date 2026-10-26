import json

import pytest
from fastapi.testclient import TestClient

from app import bank
from app.config import Settings
from app.db import connect, initialize
from app.main import create_app
from app.math_catalog import ALIAS_MAP, LEGACY_MAP, TYPES, resolve_type
from app.materials import RecognizedItem
from app.question_types import BASE_TYPES, CHALLENGE_TYPES, register_ai_type


@pytest.fixture
def setup(tmp_path):
    settings = Settings(auth_required=False, database_path=tmp_path/'math.sqlite3', deepseek_api_key='', _env_file=None)
    with TestClient(create_app(settings)) as client:
        yield client, settings


def stored(settings, qid):
    with connect(settings.database_path) as db:
        return json.loads(db.execute('SELECT data FROM questions WHERE id=?',(qid,)).fetchone()[0])


def test_map_covers_all_original_types_without_claiming_external_review(setup):
    client, settings = setup
    initial = client.get('/api/v1/math/coverage').json()
    assert initial['summary']=={'types':37,'with_verified_questions':37,'diagnosable':37,'missing_verified':0,'unassessed':37}
    assert len(LEGACY_MAP)==len(BASE_TYPES)+len(CHALLENGE_TYPES)
    assert len({t['id'] for t in TYPES})==37
    assert all(resolve_type('',alias)==t['id'] for t in TYPES for alias in t['aliases'])
    with connect(settings.database_path) as db:
        bank.import_records(db,'test',[{'id':'bank:unreviewed','subject':'math','stage':'junior','grade':None,'term':None,
            'stem':'选择正确的科学记数法。','kind':'single_choice','status':'ready','answer':'A',
            'options':[{'key':'A','text':'正确'},{'key':'B','text':'错误'}],'steps':[], 'difficulty':1,
            'knowledge_tags':['科学记数法'],'type_tags':['选择题'],'tags_source':'source','provenance':{'dataset':'test'}}],{})
    value = client.get('/api/v1/math/coverage').json()
    t = next(t for t in value['types'] if t['id']=='m7a:scientific')
    assert t['candidate_goal_questions']==1 and t['verified_questions']>=18 and t['status']=='待诊断'
    assert len(t['verified_structures'])==3
    assert client.post('/api/v1/math/practice',json={'type_id':t['id']}).status_code==200


def test_registry_reuses_alias_and_keeps_unknown_ai_types_pending(setup):
    _, settings = setup
    with connect(settings.database_path) as db:
        assert register_ai_type(db,RecognizedItem(stem='题目',question_type_name='负数减去负数'),'test')=='template:addition'
        assert register_ai_type(db,RecognizedItem(stem='题目',question_type_id='m7a:scientific',question_type_name='科学记数法'),'test')=='m7a:scientific'
        tid = register_ai_type(db,RecognizedItem(stem='题目',question_type_name='复杂的新结构'),'test')
        item = json.loads(db.execute('SELECT data FROM question_types WHERE id=?',(tid,)).fetchone()[0])
        assert item['needs_review'] and item['source']=='ai'
        assert resolve_type(tid,item['name']) is None


def test_diagnostic_samples_six_chapters_and_resumes_without_answers(setup):
    client, _ = setup
    s = client.post('/api/v1/math/diagnostics',json={}).json()
    assert s['total']==10 and s['answered']==0
    assert len({t['type_id'] for t in s['items']})==10
    from app.math_catalog import TYPE_MAP
    assert len({TYPE_MAP[t['type_id']]['unit_id'] for t in s['items']})==6
    assert 'answer' not in s['current']['question'] and 'steps' not in s['current']['question']
    assert all(t['result'] is None and 'answer' not in t for t in s['items'])
    assert client.post('/api/v1/math/diagnostics',json={}).json()['id']==s['id']
    assert len(client.get('/api/v1/math/diagnostics').json()['items'])==1
    assert client.post('/api/v1/math/diagnostics',json={'unit_id':'math-7-1:u2'}).status_code==409
    assert client.post('/api/v1/math/diagnostics',json={'unit_id':'math-8-1:u1'}).status_code==422


def test_full_diagnostic_writes_shared_evidence_and_recommends_followup(setup):
    client, settings = setup
    s = client.post('/api/v1/math/diagnostics',json={}).json()
    first = s['current']['type_id']
    for n in range(s['total']):
        current = s['current'];q=stored(settings,current['question']['id'])
        response=client.post(f'/api/v1/math/diagnostics/{s["id"]}/answer',json={'position':current['position'],'answer':'999999' if n==0 else q['answer']})
        assert response.status_code==200,response.text
        s=response.json()
    assert s['status']=='completed' and s['current'] is None and s['summary']['correct']==9
    assert s['summary']['measured_types']==10 and s['summary']['unmeasured_types']==27
    assert s['recommendations'][0]['type_id']==first and s['recommendations'][0]['available']
    student=client.get('/api/v1/student').json()
    assert student['completed']==10 and student['correct']==9
    assert len(client.get('/api/v1/history').json()['items'])==10
    c=client.get('/api/v1/math/coverage').json()
    assert sum(t['attempts'] for t in c['types'])==10
    assert all(t['status']=='证据不足' for t in c['types'] if t['attempts'])
    r=client.get('/api/v1/courses/report').json()
    assert any(g['attempts'] for g in r['goals'])
    a=client.post('/api/v1/math/practice',json={'type_id':s['recommendations'][0]['type_id']})
    assert a.status_code==200 and 'answer' not in a.json()['question']


def test_diagnostic_answer_retries_bounds_and_invalid_input_are_atomic(setup):
    client, settings=setup
    s=client.post('/api/v1/math/diagnostics',json={'size':3}).json();url=f'/api/v1/math/diagnostics/{s["id"]}/answer'
    for body,code in [({'position':0,'answer':'1/0'},422),({'position':1,'answer':'2'},409),({'position':13,'answer':'2'},404)]:
        assert client.post(url,json=body).status_code==code
        assert client.get(f'/api/v1/math/diagnostics/{s["id"]}').json()['answered']==0
        assert client.get('/api/v1/student').json()['completed']==0
    q=stored(settings,s['current']['question']['id']);body={'position':0,'answer':q['answer']}
    assert client.post(url,json=body).status_code==200
    assert client.post(url,json=body).json()['answered']==1
    assert client.post(url,json={'position':0,'answer':'999999'}).status_code==409
    assert client.get('/api/v1/student').json()['completed']==1
    ended=client.post(f'/api/v1/math/diagnostics/{s["id"]}/cancel',json={}).json()
    assert ended['status']=='cancelled' and ended['answered']==1 and ended['summary']['correct']==1
    assert client.post(url,json={'position':1,'answer':'2'}).status_code==409
    assert client.post('/api/v1/math/diagnostics',json={'size':3}).json()['id']!=s['id']


def test_diagnostic_does_not_replace_regular_practice_and_deduplicates_shared_question(setup):
    client, settings=setup
    regular=client.post('/api/v1/practice/next',json={'knowledge_id':'opposite'}).json()
    s=client.post('/api/v1/math/diagnostics',json={'size':1,'unit_id':'math-7-1:u1'}).json()
    with connect(settings.database_path) as db:
        db.execute('UPDATE math_diagnostic_items SET question_id=? WHERE session_id=?',(regular['question']['id'],s['id']))
        assert db.execute('SELECT status FROM attempts WHERE id=?',(regular['attempt_id'],)).fetchone()[0]=='assigned'
    q=stored(settings,regular['question']['id'])
    client.post(f'/api/v1/math/diagnostics/{s["id"]}/answer',json={'position':0,'answer':q['answer']})
    r=client.post(f'/api/v1/attempts/{regular["attempt_id"]}/answer',json={'answer':q['answer']})
    assert r.status_code==200 and r.json()['evidence_weight']==0 and r.json()['repeated_question']
    t=next(t for t in client.get('/api/v1/math/coverage').json()['types'] if t['id']=='m7a:opposite')
    assert t['attempts']==1


def test_diagnostic_persists_after_restart_and_keeps_old_records(setup):
    client, settings=setup
    s=client.post('/api/v1/math/diagnostics',json={'size':2}).json()
    client.post(f'/api/v1/math/diagnostics/{s["id"]}/answer',json={'position':0,'answer':'999999'})
    initialize(settings.database_path)
    with TestClient(create_app(settings)) as other:
        saved=other.get(f'/api/v1/math/diagnostics/{s["id"]}').json()
        assert saved['answered']==1 and saved['current']['position']==1
        assert other.get('/api/v1/student').json()['completed']==1
        with connect(settings.database_path) as db:
            assert db.execute('PRAGMA user_version').fetchone()[0]==16


def test_coverage_excludes_corrupt_and_unrecognized_question_sources(setup):
    client, settings=setup
    before=client.get('/api/v1/math/coverage').json()
    with connect(settings.database_path) as db:
        row=db.execute("SELECT id,data FROM questions WHERE knowledge_id='opposite' AND json_extract(data,'$.difficulty')<3 LIMIT 1").fetchone()
        q=json.loads(row['data']);q['answer']='999999';db.execute('UPDATE questions SET data=? WHERE id=?',(json.dumps(q),row['id']))
    after=client.get('/api/v1/math/coverage').json()
    counts=lambda value:next(t['verified_questions'] for t in value['types'] if t['id']=='m7a:opposite')
    assert counts(after)==counts(before)-1
    for _ in range(5):
        s=client.post('/api/v1/math/diagnostics',json={'size':1,'unit_id':'math-7-1:u1'}).json()
        assert s['current']['question']['id']!=row['id']
        client.post(f'/api/v1/math/diagnostics/{s["id"]}/cancel',json={})


def test_unit_diagnostic_respects_limits_and_no_fake_questions(setup):
    client,_=setup
    s=client.post('/api/v1/math/diagnostics',json={'size':14,'unit_id':'math-7-1:u3'}).json()
    assert s['total']==3 and {t['type_id'] for t in s['items']}=={'m7a:substitution','m7a:expression-model','m7a:quadratic-substitution'}
    for body in ({'size':0},{'size':15},{'unit_id':"x' OR 1=1"}):
        assert client.post('/api/v1/math/diagnostics',json=body).status_code==422
    assert client.get('/api/v1/math/diagnostics/missing').status_code==404
