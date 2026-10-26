"""Production core bootstrap, provenance, physics flows and subject isolation."""
import copy
import io
import json
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from app import bank_ai, content
from app.config import Settings
from app.db import connect, initialize
from app.diagnostic_core import CATALOG, canonical, verified, types_for_book
from app.main import create_app

@pytest.mark.parametrize('key',CATALOG)
def test_core_constraints_and_content_tampering(key):
    for i in range(6):
        q=copy.deepcopy(canonical(key,i));assert verified(q)
        for field,value in [('stem',q['stem']+'条件改变'),('answer',next(o['key'] for o in q['options'] if o['key']!=q['answer'])),('term',3-q['term']),('curriculum_goal_ids',['math-9-1:u1:g1'])]:
            bad=copy.deepcopy(q);bad[field]=value;assert not verified(bad)
        bad=copy.deepcopy(q);bad['annotation']['parts'][0]['reference_answer']='Z';assert not verified(bad)
        bad=copy.deepcopy(q);bad['evidence_invalidated']=True;assert not verified(bad)
        bad=copy.deepcopy(q);bad['core_spec']['index']=1000000000;assert not verified(bad)

@pytest.fixture
def setup(tmp_path):
    settings=Settings(database_path=tmp_path/'learn.sqlite3',diagnostic_core_enabled=True,deepseek_api_key='test-only',_env_file=None)
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/v1/auth/register',json={'username':'alice','password':'local-test-pass','grade':7,'term':1}).status_code==201
        yield client,settings

def switch(client,bid):
    s,g,t=bid.split('-');r=client.post('/api/v1/auth/stage',json={'subject':s,'grade':int(g),'term':int(t)})
    assert r.status_code==200,r.text

def stored(settings,qid):
    with connect(settings.database_path) as db:return json.loads(db.execute('SELECT data FROM bank_questions WHERE id=?',(qid,)).fetchone()[0])

@pytest.mark.parametrize('bid',['physics-8-1','physics-8-2','physics-9-1','physics-9-2','math-7-2'])
def test_core_has_enough_questions_and_real_independent_state(setup,bid):
    client,settings=setup;switch(client,bid);tid=types_for_book(bid)[0]['id']
    home=client.get('/api/v1/study/home').json();assert home['book_id']==bid and home['completed']==0
    ids=[]
    for i in range(5):
        r=client.post('/api/v1/study/next',json={'type_id':tid,'allow_challenge':False});assert r.status_code==200,r.text
        a=r.json();q=stored(settings,a['question']['id']);assert verified(q) and q['id'] not in ids;ids.append(q['id'])
        assert not {'core_spec','answer','steps'} & a['question'].keys()
        answer=next(o['key'] for o in q['options'] if o['key']!=q['answer']) if i<2 else q['answer']
        url=f"/api/v1/bank/attempts/{a['attempt_id']}/answer"
        result=client.post(url,json={'answer':answer});assert result.status_code==200,result.text
        assert result.json()['evidence_weight']==1
        assert client.post(url,json={'answer':answer}).json()==result.json()
    t=next(t for t in client.get('/api/v1/study/home').json()['types'] if t['id']==tid)
    assert t['independent_count']==5 and t['ai_ready'] and t['status']=='需要补强'
    report=client.get('/api/v1/reports?period=all').json()
    assert report['summary']['independent']==5 and report['subject']==bid.split('-')[0]
    switch(client,'math-7-1')
    assert client.get('/api/v1/study/home').json()['completed']==0
    assert client.post(url,json={'answer':answer}).status_code==403
    switch(client,bid)
    assert client.get('/api/v1/reports?period=all').json()['summary']['independent']==5


def test_physics_teacher_hints_memory_report_and_new_type(setup,monkeypatch):
    client,settings=setup;switch(client,'physics-8-1');t=types_for_book('physics-8-1')[0];calls=[]
    async def fake(settings,messages,schema,vision=False):
        ctx=json.loads(messages[1]['content'])['learning_material'];calls.append(ctx)
        from app.observation_guard import Review
        if schema is Review:
            return schema(decisions=[{'candidate_index':c['candidate_index'],'verdict':'supported','evidence_quote':c['evidence_quote'],'reason':'速度应为路程除以时间，学生使用了乘法。'} for c in ctx['candidates']])
        return schema(reply='平均速度等于总路程除以总时间。',check_question='120米用时30秒，平均速度是多少？',observations=[{'type_id':t['id'],'type_name':t['name'],'goal_id':t['goal_id'],'kind':'difficulty','evidence_quote':'我算120×30=3600','note':'待独立检查'}])
    monkeypatch.setattr(bank_ai,'request_json',fake)
    a=client.post('/api/v1/study/next',json={'type_id':t['id']}).json();q=stored(settings,a['question']['id'])
    r=client.post('/api/v1/teacher/chat',json={'source':'bank','attempt_id':a['attempt_id'],'message':'我算120×30=3600'});assert r.status_code==200,r.text
    assert r.json()['observations'] and all(c['subject']=='physics' for c in calls)
    thread=r.json()['thread_id']
    result=client.post(f"/api/v1/bank/attempts/{a['attempt_id']}/answer",json={'answer':q['answer']}).json()
    assert result['assisted']
    state=next(x for x in client.get('/api/v1/study/home').json()['types'] if x['id']==t['id'])
    assert state['independent_count']==0 and state['observation_count']==1
    pdf=client.get('/api/v1/reports/pdf');assert pdf.status_code==200,pdf.text[:100]
    text=''.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert '物理' in text
    switch(client,'math-7-1');assert client.get('/api/v1/teacher/threads/'+thread).status_code==404
    assert not any(x.get('observation_count') for x in client.get('/api/v1/study/home').json()['types'])
    assert client.post('/api/v1/auth/stage',json={'subject':'physics','grade':7,'term':1}).status_code==422


def test_core_update_package_never_forges_teacher_review(tmp_path):
    publisher=tmp_path/'p.sqlite3';receiver=tmp_path/'r.sqlite3'
    initialize(publisher,with_diagnostic_core=True);initialize(receiver)
    with connect(publisher) as db:
        manifest=content.publish_release(db);raw=db.execute('SELECT data FROM content_releases').fetchone()[0].encode()
        core=[q for q in json.loads(raw)['items'] if q['family']=='bank'];assert len(core)==len(CATALOG)*6
        assert all(not q['data']['provenance']['teacher_reviewed'] for q in core)
    with connect(receiver) as db:content.install_package(db,raw,manifest)
    with connect(receiver) as db:
        qs=[json.loads(r[0]) for r in db.execute('SELECT data FROM bank_questions')]
        assert len(qs)==len(CATALOG)*6 and all(verified(q) for q in qs)
        assert all(all(t['origin']!='teacher' for t in q['tags']) for q in qs)
    with connect(receiver) as db:assert not content.install_package(db,raw,manifest)['updated']
