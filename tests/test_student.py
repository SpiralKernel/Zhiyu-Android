"""带真实会话的学生流程：归属、阶段边界、独立证据门槛与 AI 不加分。"""
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import bank, bank_ai
from app.config import Settings
from app.db import connect, initialize, now, dumps
from app.main import create_app
from app.questions import make_question


@pytest.fixture
def setup(tmp_path):
    settings=Settings(database_path=tmp_path/'accounts.sqlite3',deepseek_api_key='test-only',_env_file=None)
    with TestClient(create_app(settings)) as client:
        yield client,settings


def register(client,name='alice',grade=7,term=1):
    r=client.post('/api/v1/auth/register',json={'username':name,'password':'test-pass-123','nickname':name,'grade':grade,'term':term})
    assert r.status_code==201,r.text
    return r.json()


def test_private_deployment_disables_registration_but_keeps_existing_login(tmp_path):
    settings=Settings(database_path=tmp_path/'private.sqlite3',_env_file=None)
    with TestClient(create_app(settings)) as client:
        register(client)
    private=settings.model_copy(update={'registration_enabled':False})
    with TestClient(create_app(private),base_url='https://learning.example') as client:
        assert client.get('/api/v1/auth/session').json()['registration_enabled'] is False
        response=client.post('/api/v1/auth/register',json={'username':'bob','password':'test-pass-123','grade':7,'term':1})
        assert response.status_code==403
        with connect(settings.database_path) as db:
            assert db.execute('SELECT count(*) FROM accounts').fetchone()[0]==1
        response=client.post('/api/v1/auth/login',json={'username':'alice','password':'test-pass-123'},headers={'Origin':'https://learning.example'})
        assert response.status_code==200
        assert 'Secure' in response.headers['set-cookie']
        assert client.get('/api/v1/study/home').status_code==200
        assert client.post('/api/v1/auth/stage',json={'grade':8,'term':1},headers={'Origin':'https://other.example'}).status_code==403


def home(client):
    r=client.get('/api/v1/study/home');assert r.status_code==200,r.text
    return r.json()


def answer(client,settings,tid='m7a:subtract-negative',wrong=False,hint=False):
    r=client.post('/api/v1/study/next',json={'type_id':tid});assert r.status_code==200,r.text
    a=r.json()
    with connect(settings.database_path) as db:
        q=json.loads(db.execute('SELECT data FROM questions WHERE id=?',(a['question']['id'],)).fetchone()[0])
    if hint:
        assert client.post(f"/api/v1/attempts/{a['attempt_id']}/hint").status_code==200
    value='999999' if wrong else q['answer']
    r=client.post(f"/api/v1/attempts/{a['attempt_id']}/answer",json={'answer':value});assert r.status_code==200,r.text
    return a,r.json()


def type_state(client,tid='m7a:subtract-negative'):
    return next(t for t in home(client)['types'] if t['id']==tid)


def source(qid,grade=7,term=1,knowledge='绝对值',written=False,reviewed=False):
    return {'id':qid,'subject':'math','stage':'junior','grade':grade,'term':term,'stem':'核验题 '+qid,'options':[] if written else [{'key':'A','text':'1'},{'key':'B','text':'2'}],
      'kind':'reference' if written else 'single_choice','status':'reference' if written else 'ready','answer':'完整过程' if written else 'A','steps':['由条件可得。'],'difficulty':1,
      'knowledge_tags':[knowledge],'type_tags':['负数的绝对值'],'tags_source':'source','provenance':{'teacher_reviewed':reviewed}}


def test_student_choice_entry_respects_stage_and_does_not_inflate_trusted_evidence(setup):
    client,settings=setup
    register(client)
    with connect(settings.database_path) as db:
        bank.import_records(db,'choice-test',[source('junior-choice'),
            source('future-choice',grade=9,term=1,knowledge='二次函数')],{})
    response=client.post('/api/v1/study/next',json={'choice':True,'allow_challenge':False})
    assert response.status_code==200,response.text
    work=response.json()
    assert work['source']=='bank' and work['question']['id']=='junior-choice'
    assert work['question']['answer_mode']=='choice' and 'answer' not in work['question']
    result=client.post(f"/api/v1/bank/attempts/{work['attempt_id']}/answer",json={'answer':'A'})
    assert result.status_code==200 and result.json()['correct']
    assert home(client)['completed']==1
    assert sum(t['independent_count'] for t in home(client)['types'])==0
    assert client.post('/api/v1/study/next',json={'choice':True,'written':True}).status_code==422
    assert client.post('/api/v1/auth/stage',json={'grade':8,'term':1}).status_code==200
    assert client.post('/api/v1/study/next',json={'choice':True}).status_code==404


def test_annotation_upgrade_preserves_history_and_does_not_count_same_item_twice(setup):
    from app.math_quality import annotate
    client,settings=setup
    register(client)
    raw=source('reviewed-source',reviewed=True)
    raw['provenance'].update(dataset='quality-test',source_id='stable-source-id')
    with connect(settings.database_path) as db:
        bank.import_records(db,'quality-test',[raw],{})
    work=client.post('/api/v1/study/next',json={'choice':True}).json()
    first=client.post(f"/api/v1/bank/attempts/{work['attempt_id']}/answer",json={'answer':'A'}).json()
    assert first['evidence_weight']==1
    assert type_state(client,'m7a:absolute')['independent_count']==1
    with connect(settings.database_path) as db:
        bank.import_records(db,'quality-test',[annotate(raw)],{})
    assert client.get(f"/api/v1/bank/attempts/{work['attempt_id']}").status_code==200
    assert home(client)['completed']==1
    assert type_state(client,'m7a:absolute')['independent_count']==1
    again=client.post('/api/v1/study/next',json={'choice':True}).json()
    assert again['question']['id']!=work['question']['id']
    second=client.post(f"/api/v1/bank/attempts/{again['attempt_id']}/answer",json={'answer':'A'}).json()
    assert second['repeated'] and second['evidence_weight']==0
    assert type_state(client,'m7a:absolute')['independent_count']==1
    report=client.get('/api/v1/reports?period=all').json()
    assert report['summary']['attempts']==2 and report['summary']['independent']==1
    assert client.post('/api/v1/auth/stage',json={'grade':8,'term':1}).status_code==200
    assert client.get(f"/api/v1/bank/attempts/{work['attempt_id']}").status_code==403


def test_login_wall_and_first_account_inherits_legacy_only(setup):
    client,settings=setup
    with connect(settings.database_path) as db:
        q=make_question('addition',0)
        db.execute("INSERT INTO attempts(id,student_id,question_id,status,assigned_at,submitted_at,answer,result) VALUES('old','demo',?,'submitted',?,?,?,?)",(q['id'],now(),now(),q['answer'],dumps({'correct':True,'evidence_weight':1})))
    assert client.get('/api/v1/auth/session').json()['needs_setup']
    for path in ('/api/v1/study/home','/api/v1/student','/api/v1/bank/questions','/api/v1/imports'):
        assert client.get(path).status_code==401
    assert register(client)['inherited_records']
    assert home(client)['completed']==1
    assert client.get('/api/v1/auth/session').json()['student']['student_id']=='demo'
    cookie=client.cookies.get('teacher_session')
    with connect(settings.database_path) as db:
        assert db.execute('SELECT token_hash FROM auth_sessions').fetchone()[0]!=cookie
        assert db.execute('SELECT password_hash FROM accounts').fetchone()[0]!='test-pass-123'
    assert client.post('/api/v1/auth/logout').status_code==200
    assert not register(client,'bob')['inherited_records']
    assert home(client)['completed']==0
    assert client.post('/api/v1/auth/logout').status_code==200
    assert client.post('/api/v1/auth/login',json={'username':'alice','password':'test-pass-123'}).status_code==200
    assert home(client)['completed']==1


def test_sessions_and_attempts_are_isolated(setup):
    client,settings=setup
    register(client)
    a,_=answer(client,settings)
    alice=client.cookies.get('teacher_session')
    register(client,'bob')
    bob=client.cookies.get('teacher_session')
    assert type_state(client)['independent_count']==0
    assert client.post(f"/api/v1/attempts/{a['attempt_id']}/answer",json={'answer':'2'}).status_code==404
    client.cookies.set('teacher_session',alice)
    assert type_state(client)['independent_count']==1
    client.cookies.set('teacher_session',bob)
    assert home(client)['completed']==0


def test_stage_filter_enforced_even_without_client_filter(setup):
    client,settings=setup
    with connect(settings.database_path) as db:
        bank.import_records(db,'scope',[source('seven'),source('wrong-grade',8),source('wrong-term',7,2),source('eight',8,1,'全等三角形')],{})
    register(client)
    assert [b['id'] for b in client.get('/api/v1/courses').json()['books']]==['math-7-1']
    assert {q['id'] for q in client.get('/api/v1/bank/questions').json()['items']}=={'seven'}
    for body in ({'course_book_id':'math-8-1'},{'subject':'physics'},{'stage':'senior'}):
        assert client.post('/api/v1/bank/next',json=body).status_code==403
    assert client.post('/api/v1/bank/next',json={'question_id':'wrong-grade'}).status_code==404
    a=client.post('/api/v1/bank/next',json={'question_id':'seven'}).json()
    assert client.post('/api/v1/courses/setting',json={'subject':'math','book_id':'math-9-1'}).status_code==403
    assert client.post('/api/v1/study/next',json={'unit_id':'math-8-1:u1'}).status_code==403
    assert client.post('/api/v1/auth/stage',json={'grade':8,'term':1}).status_code==200
    assert home(client)['book_id']=='math-8-1'
    assert home(client)['completed']==0
    assert {q['id'] for q in client.get('/api/v1/bank/questions').json()['items']}=={'eight'}
    assert client.get(f"/api/v1/bank/attempts/{a['attempt_id']}").status_code==403
    assert client.post('/api/v1/practice/next',json={}).status_code==403
    assert client.get('/api/v1/courses?subject=physics').status_code==403
    assert client.post('/api/v1/auth/stage',json={'grade':7,'term':1}).status_code==200
    assert client.get(f"/api/v1/bank/attempts/{a['attempt_id']}").status_code==200


def test_five_different_independent_questions_gate_ai_and_retest(setup,monkeypatch):
    client,settings=setup
    register(client)
    calls=[]
    async def fake(settings,messages,schema,vision=False):
        calls.append((messages,vision));return schema(reply='先把减去负数改写为加相反数。',check_question='负号表示哪个运算？')
    monkeypatch.setattr(bank_ai,'request_json',fake)
    for i in range(4):
        answer(client,settings,wrong=True)
        assert type_state(client)['status']=='证据不足'
    body={'type_id':'m7a:subtract-negative','message':'帮我补强'}
    assert client.post('/api/v1/study/ai/chat',json=body).status_code==409
    assert not calls
    answer(client,settings,wrong=True)
    state=type_state(client)
    assert state['independent_count']==5 and state['ai_ready'] and state['status']=='需要补强'
    before=home(client)['completed']
    assert client.post('/api/v1/study/ai/chat',json=body).json()['score_recorded'] is False
    assert home(client)['completed']==before and type_state(client)['independent_count']==5
    assert len(client.get('/api/v1/study/ai/messages?type_id=m7a:subtract-negative').json()['items'])==1
    for _ in range(3):answer(client,settings)
    assert type_state(client)['status']=='需要补强'
    assert type_state(client)['retest_count']==3
    for _ in range(3):answer(client,settings)
    assert type_state(client)['status']=='表现稳定'
    assert type_state(client)['retest_count']==6
    assert client.post('/api/v1/study/ai/chat',json=body).status_code==409
    register(client,'bob')
    assert client.get('/api/v1/study/ai/messages?type_id=m7a:subtract-negative').json()['items']==[]
    assert type_state(client)['independent_count']==0


def test_hint_duplicates_and_unreviewed_sources_do_not_fill_gate(setup):
    client,settings=setup
    register(client)
    a,result=answer(client,settings,hint=True)
    assert type_state(client)['independent_count']==0
    assert client.post(f"/api/v1/attempts/{a['attempt_id']}/answer",json={'answer':result['answer']}).status_code==200
    assert type_state(client)['independent_count']==0
    with connect(settings.database_path) as db:
        bank.import_records(db,'unreviewed',[source('unreviewed-'+str(i)) for i in range(5)],{})
    for i in range(5):
        a=client.post('/api/v1/bank/next',json={'question_id':'unreviewed-'+str(i)}).json()
        assert client.post(f"/api/v1/bank/attempts/{a['attempt_id']}/answer",json={'answer':'B'}).status_code==200
    state=type_state(client,'m7a:absolute')
    assert state['recorded']==5 and state['independent_count']==0 and not state['ai_ready']
    for path in ('/api/v1/student','/api/v1/bank/profile','/api/v1/math/coverage'):
        assert client.get(path).status_code==403
    assert client.post('/api/v1/bank/plan',json={}).status_code==403
    assert client.post(f"/api/v1/attempts/{a['attempt_id']}/tutor",json={'message':'绕过题量'}).status_code==403


def test_photo_coaching_gate_and_no_mastery_write(setup,monkeypatch):
    client,settings=setup
    register(client)
    out=io.BytesIO();Image.new('RGB',(80,80),'white').save(out,format='PNG')
    calls=[]
    async def fake(settings,messages,schema,vision=False):
        calls.append(vision);return schema(reply='先看题目里的符号。',check_question='应该先做哪一步？')
    monkeypatch.setattr(bank_ai,'request_json',fake)
    def photo():return client.post('/api/v1/study/ai/photo',data={'type_id':'m7a:subtract-negative'},files={'files':('q.png',out.getvalue(),'image/png')})
    assert photo().status_code==409
    for _ in range(5):answer(client,settings,wrong=True)
    before=home(client)['completed']
    assert photo().json()['score_recorded'] is False and calls==[True]
    assert home(client)['completed']==before


def test_cookie_logout_csrf_and_login_throttle(setup):
    client,settings=setup
    response=client.post('/api/v1/auth/register',json={'username':'alice','password':'test-pass-123','grade':7,'term':1})
    cookie=response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    old=client.cookies.get('teacher_session')
    assert client.post('/api/v1/auth/stage',json={'grade':9,'term':2},headers={'origin':'https://attacker.invalid'}).status_code==403
    assert client.post('/api/v1/auth/logout').status_code==200
    client.cookies.set('teacher_session',old)
    assert client.get('/api/v1/study/home').status_code==401
    client.cookies.clear()
    for _ in range(10):
        assert client.post('/api/v1/auth/login',json={'username':'alice','password':'wrong-pass'}).status_code==401
    assert client.post('/api/v1/auth/login',json={'username':'alice','password':'test-pass-123'}).status_code==429


def test_ai_failure_does_not_create_evidence(setup,monkeypatch):
    client,settings=setup;register(client)
    for _ in range(5):answer(client,settings,wrong=True)
    from fastapi import HTTPException
    async def fail(*args,**kwargs):raise HTTPException(502,'模拟网络失败')
    monkeypatch.setattr(bank_ai,'request_json',fail)
    before=home(client)
    assert client.post('/api/v1/study/ai/chat',json={'type_id':'m7a:subtract-negative','message':'帮我补强'}).status_code==502
    assert home(client)==before
    assert client.get('/api/v1/study/ai/messages?type_id=m7a:subtract-negative').json()['items']==[]


def test_owner_context_does_not_leak_between_concurrent_requests(setup):
    client,settings=setup;register(client)
    answer(client,settings)
    alice=client.cookies.get('teacher_session')
    register(client,'bob',8,2)
    bob=client.cookies.get('teacher_session')
    from concurrent.futures import ThreadPoolExecutor
    def read(pair):
        token,book=pair
        r=client.get('/api/v1/study/home',headers={'cookie':'teacher_session='+token})
        assert r.status_code==200
        value=r.json()
        assert value['book_id']==book
        assert value['completed']==(1 if book=='math-7-1' else 0)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(read,[(alice,'math-7-1'),(bob,'math-8-2')]*8))


def test_import_pages_and_written_reviews_are_owned(setup,monkeypatch):
    client,settings=setup;register(client)
    out=io.BytesIO();Image.new('RGB',(80,80),'white').save(out,format='PNG')
    imported=client.post('/api/v1/imports',data={'mode':'completed'},files={'files':('paper.png',out.getvalue(),'image/png')})
    assert imported.status_code==201,imported.text
    material_id=imported.json()['id']
    with connect(settings.database_path) as db:
        bank.import_records(db,'written',[source('written',written=True)],{})
    a=client.post('/api/v1/bank/next',json={'question_id':'written'}).json()
    async def fake(settings,messages,schema,vision=False):
        return schema(transcribed_answer='步骤',verdict='correct',reason='参考答案一致',confidence='high')
    monkeypatch.setattr(bank_ai,'request_json',fake)
    review=client.post(f"/api/v1/bank/attempts/{a['attempt_id']}/assess",data={'answer':'步骤'}).json()
    assert review['status']=='review'
    assert client.post(f"/api/v1/bank/attempts/{a['attempt_id']}/confirm",json={'review_id':review['id'],'reviewed':True,'verdict':'correct','transcribed_answer':'步骤','count_evidence':True}).status_code==200
    assert type_state(client,'m7a:absolute')['independent_count']==0
    register(client,'bob')
    assert client.get('/api/v1/imports').json()['items']==[]
    assert client.get(f'/api/v1/imports/{material_id}').status_code==404
    assert client.get(f'/api/v1/imports/{material_id}/pages/1').status_code==404
    assert client.delete(f'/api/v1/imports/{material_id}').status_code==404
    assert client.get(f"/api/v1/bank/attempts/{a['attempt_id']}").status_code==404
    assert client.post(f"/api/v1/bank/attempts/{a['attempt_id']}/confirm",json={'review_id':review['id'],'reviewed':True,'verdict':'correct','transcribed_answer':'步骤'}).status_code==404


def test_ai_new_type_gets_unknown_state_without_credible_score(setup):
    client,settings=setup;register(client)
    q=source('new-ai-type',reviewed=True)
    q.update(type_tags=['移项后漏除系数的方程题'],tags_source='ai')
    with connect(settings.database_path) as db:
        bank.import_records(db,'new-ai-type',[q],{})
    a=client.post('/api/v1/bank/next',json={'question_id':q['id']}).json()
    assert client.post(f"/api/v1/bank/attempts/{a['attempt_id']}/answer",json={'answer':'B'}).status_code==200
    state=next(t for t in home(client)['types'] if t['name']=='移项后漏除系数的方程题')
    assert state['recorded']==1 and state['status']=='未评估' and not state['ai_ready']
