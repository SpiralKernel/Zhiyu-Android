"""Textbook-scoped senior learning through actual authenticated API routes."""
import io
import json

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import bank_ai
from app.config import Settings
from app.db import connect
from app.main import create_app
from app.senior_bank import import_batch
from test_senior_bank import batch


def test_senior_book_switching_practice_memory_pdf_and_junior_history(tmp_path,monkeypatch):
    settings=Settings(database_path=tmp_path/'learn.sqlite3',diagnostic_core_enabled=False,
                      deepseek_api_key='mock-only',_env_file=None)
    with TestClient(create_app(settings)) as client:
        r=client.post('/api/v1/auth/register',json={'username':'senior-test','password':'local-test-pass','grade':7,'term':1})
        assert r.status_code==201,r.text
        session=client.get('/api/v1/auth/session').json()
        assert len(session['available_books'])==10
        original=client.get('/api/v1/study/home').json()
        bid='math-senior-compulsory-1'
        r=client.post('/api/v1/auth/stage',json={'stage':'senior','subject':'math','book_id':bid})
        assert r.status_code==200,r.text
        student=client.get('/api/v1/auth/session').json()['student']
        assert student['stage']=='senior' and student['grade'] is None and student['term'] is None
        with connect(settings.database_path) as db:import_batch(db,batch())
        home=client.get('/api/v1/study/home').json();assert home['book_id']==bid
        r=client.post('/api/v1/study/next',json={'allow_challenge':False});assert r.status_code==200,r.text
        work=r.json();assert work['question']['stage']=='senior'
        assert 'answer' not in work['question'] and 'reference_answer' not in work['question']['annotation']['parts'][0]
        url=f"/api/v1/bank/attempts/{work['attempt_id']}/answer"
        r=client.post(url,json={'answer':'A'});assert r.status_code==200,r.text
        assert r.json()['assessment_source']=='source_answer'
        state=client.get('/api/v1/study/home').json()
        assert state['completed']==1 and not any(t['independent_count'] for t in state['types'])
        assert client.get('/api/v1/bank/questions').status_code==200
        assert client.get('/api/v1/bank/questions?stage=junior').status_code==403
        assert client.get('/api/v1/bank/questions?subject=physics').status_code==403
        goal=batch()['items'][0]['annotation']['curriculum']['goal_ids'][0]
        calls=[]
        async def fake(settings,messages,schema,vision=False):
            ctx=json.loads(messages[1]['content'])['learning_material'];calls.append(ctx)
            return schema(reply='交集是两个集合共有的元素。',check_question='A={2,3}，B={3,4}的交集是什么？',
                observations=[{'type_name':'按枚举法求两集合的交集','goal_id':goal,
                    'kind':'question_interest','evidence_quote':'交集怎么求','note':'主动询问交集的计算方法。'}])
        monkeypatch.setattr(bank_ai,'request_json',fake)
        r=client.post('/api/v1/teacher/chat',json={'message':'交集怎么求'})
        assert r.status_code==200,r.text
        assert r.json()['observations'] and calls[0]['stage']=='senior' and calls[0]['book_id']==bid
        thread=r.json()['thread_id']
        report=client.get('/api/v1/reports?period=all').json()
        assert report['stage']=='senior' and report['book_title'] and report['summary']['independent']==0
        pdf=client.get('/api/v1/reports/pdf');assert pdf.status_code==200
        text=''.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
        assert 'None年级' not in text and '必修' in text
        next_book='math-senior-selective-2'
        assert client.post('/api/v1/auth/stage',json={'stage':'senior','subject':'math','book_id':next_book}).status_code==200
        assert client.get('/api/v1/study/home').json()['completed']==0
        assert client.get('/api/v1/teacher/threads/'+thread).status_code==404
        assert client.post(url,json={'answer':'A'}).status_code==403
        assert client.post('/api/v1/auth/stage',json={'stage':'senior','subject':'physics','book_id':bid}).status_code==422
        assert client.post('/api/v1/auth/stage',json={'subject':'math','grade':7,'term':1}).status_code==200
        assert client.get('/api/v1/study/home').json()['completed']==original['completed']


def test_senior_registration_and_physics_book_selection(tmp_path):
    settings=Settings(database_path=tmp_path/'register.sqlite3',diagnostic_core_enabled=False,_env_file=None)
    with TestClient(create_app(settings)) as client:
        r=client.post('/api/v1/auth/register',json={'username':'physics-student','password':'local-test-pass',
            'stage':'senior','subject':'physics','book_id':'physics-senior-selective-3'})
        assert r.status_code==201,r.text
        home=client.get('/api/v1/study/home');assert home.status_code==200,home.text
        assert home.json()['book_id']=='physics-senior-selective-3'


def test_senior_teacher_publication_and_remote_update_keep_stage(tmp_path):
    from app.admin import grant_admin
    from app.content import install_package
    from app.db import initialize
    settings=Settings(database_path=tmp_path/'publish.sqlite3',diagnostic_core_enabled=False,_env_file=None)
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/v1/auth/register',json={'username':'editor','password':'local-test-pass'}).status_code==201
        with connect(settings.database_path) as db:
            grant_admin(db,'editor');import_batch(db,batch(),transaction=False)
            qid=db.execute("SELECT id FROM bank_questions WHERE stage='senior'").fetchone()[0]
        r=client.post('/api/v1/admin/drafts',json={'family':'bank','question_id':qid})
        assert r.status_code==201,r.text
        draft=r.json();form=draft['form']
        assert form['stage']=='senior' and form['curriculum_book_id']=='math-senior-compulsory-1'
        form['annotation']['review'].update(status='reviewed',method='teacher',answer_status='checked')
        r=client.put('/api/v1/admin/drafts/'+draft['id'],json={'revision':draft['revision'],'form':form})
        assert r.status_code==200,r.text
        draft=r.json()
        r=client.post('/api/v1/admin/drafts/'+draft['id']+'/publish',json={'revision':draft['revision'],
            'reviewed':True,'review_note':'核对集合共同元素、选项、解答及册次目标。'})
        assert r.status_code==200,r.text
        published=r.json()['published_id']
        r=client.post('/api/v1/content/publish',json={});assert r.status_code==200,r.text
        manifest=r.json();raw=client.get('/api/v1/content/feed/package',params={'version':manifest['version']}).content
    receiver=tmp_path/'receiver.sqlite3';initialize(receiver)
    with connect(receiver) as db:install_package(db,raw,manifest)
    with connect(receiver) as db:
        row=db.execute("SELECT stage,data FROM bank_questions WHERE stage='senior'").fetchone()
        assert row and row['stage']=='senior'
        q=json.loads(row['data']);assert q['curriculum_book_id']=='math-senior-compulsory-1'
        assert q['id'].endswith(published) and q['provenance']['teacher_reviewed']
        assert {r[0] for r in db.execute('SELECT stage FROM bank_taxonomy WHERE id IN (SELECT tag_id FROM bank_question_tags WHERE question_id=?)',(q['id'],))}=={'senior'}


def test_senior_written_assessment_receives_volume_and_rubric(tmp_path,monkeypatch):
    from app.question_annotation import source_fingerprint
    value=batch();item=value['items'][0]
    item['question'].update(kind='reference',options=[],answer='{2}')
    item['source_sha256']=source_fingerprint(item['question'])
    item['annotation'].update(response_format='calculation')
    item['annotation']['answer_spec'].update(mode='text',equivalence='rubric',accepted_answers=['{2}'])
    item['annotation']['parts'][0]['reference_answer']='{2}'
    settings=Settings(database_path=tmp_path/'written.sqlite3',diagnostic_core_enabled=False,
                      deepseek_api_key='mock-only',_env_file=None)
    calls=[]
    async def fake(settings,messages,schema,vision=False):
        calls.append(json.loads(messages[1]['content'])['learning_material'])
        return schema(transcribed_answer='两个集合共同元素只有2。',verdict='correct',reason='共同元素枚举正确。',
            confidence='high',part_feedback=[{'part_id':'p1','verdict':'correct','reason':'正确取共同元素。','evidence_quote':'共同元素只有2'}])
    monkeypatch.setattr(bank_ai,'request_json',fake)
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/v1/auth/register',json={'username':'written-student','password':'local-test-pass',
            'stage':'senior','subject':'math','book_id':'math-senior-compulsory-1'}).status_code==201
        with connect(settings.database_path) as db:import_batch(db,value)
        r=client.post('/api/v1/study/next',json={'written':True});assert r.status_code==200,r.text
        path='/api/v1/bank/attempts/'+r.json()['attempt_id']
        r=client.post(path+'/assess',data={'answer':'两个集合共同元素只有2。'})
        assert r.status_code==200,r.text
        assert calls[0]['course_requirements']['book_id']=='math-senior-compulsory-1'
        assert calls[0]['question_annotation']['parts'][0]['rubric']
        review=r.json()
        r=client.post(path+'/confirm',json={'review_id':review['id'],'reviewed':True,'verdict':'correct',
            'transcribed_answer':'两个集合共同元素只有2。','count_evidence':False})
        assert r.status_code==200,r.text
        report=client.get('/api/v1/reports?period=all').json()
        assert report['summary']['attempts']==1 and report['summary']['independent']==0
