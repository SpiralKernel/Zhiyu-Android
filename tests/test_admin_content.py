import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
import pytest
from fastapi.testclient import TestClient

from app import bank, content
from app.admin import grant_admin
from app.config import Settings
from app.db import connect, initialize
from app.main import create_app


def register(client,name):
    r=client.post('/api/v1/auth/register',json={'username':name,'password':'testing-pass-123','grade':7,'term':1,'is_admin':True})
    assert r.status_code==201,r.text


@pytest.fixture
def editor(tmp_path):
    settings=Settings(database_path=tmp_path/'editor.sqlite3',content_feed_key='feed-key-test-'+'x'*40,_env_file=None)
    with TestClient(create_app(settings),base_url='https://editor.example') as client:
        register(client,'maintainer')
        with connect(settings.database_path) as db:grant_admin(db,'maintainer')
        yield client,settings


def form(**changes):
    return {'subject':'math','grade':7,'term':1,'stem':'求 -3 的绝对值，选择正确结果。',
            'kind':'single_choice','options':[{'key':'A','text':'3'},{'key':'B','text':'-3'}],
            'answer':'A','steps':['绝对值表示到原点的距离，因此结果为3。'],
            'knowledge_tags':['绝对值'],'type_tags':['负数的绝对值'],
            'curriculum_goal_ids':['math-7-1:u1:g3'],'difficulty':1,'difficulty_basis':'只需根据绝对值概念直接求值。',**changes}


def test_structured_annotation_requires_review_and_survives_content_package(editor):
    client,settings=editor
    from test_question_annotations import annotation
    value=form(kind='reference',options=[],stem='计算 1+2，写出过程。',answer='3',steps=['1+2=3。'],
               knowledge_tags=['有理数加法'],type_tags=['有理数加法求值'],curriculum_goal_ids=['math-7-1:u2:g1'])
    value['annotation']=annotation()
    publish(client,new_draft(client,value),422)
    value['annotation']['review'].update(status='reviewed',method='teacher',answer_status='checked',issues=['rubric_pending'])
    publish(client,new_draft(client,value),422)
    value['annotation']['review']['issues']=[]
    good=publish(client,new_draft(client,value))
    q=client.get('/api/v1/admin/question',params={'family':'bank','id':good['published_id']}).json()
    assert q['annotation']['parts'][0]['rubric'][0]['points']==2
    manifest,raw=export(client)
    package=json.loads(raw)
    assert next(i['data'] for i in package['items'] if i['data']['id']==good['published_id'])['annotation']==q['annotation']


def new_draft(client, value=None):
    r=client.post('/api/v1/admin/drafts',json={});assert r.status_code==201,r.text
    draft=r.json()
    r=client.put('/api/v1/admin/drafts/'+draft['id'],json={'revision':draft['revision'],'form':value or form()})
    assert r.status_code==200,r.text
    return r.json()


def publish(client,draft,expected=200):
    r=client.post('/api/v1/admin/drafts/'+draft['id']+'/publish',json={'revision':draft['revision'],'reviewed':True,'review_note':'已核对定义、参考答案及册次目标。'})
    assert r.status_code==expected,r.text
    return r.json()


def export(client):
    r=client.post('/api/v1/content/publish',json={});assert r.status_code==200,r.text
    manifest=r.json()
    r=client.get('/api/v1/content/feed/package',params={'version':manifest['version']})
    assert r.status_code==200,r.text
    return manifest,r.content


def test_admin_is_explicit_not_claimable_by_registration_and_revocation_is_immediate(tmp_path):
    settings=Settings(database_path=tmp_path/'accounts.sqlite3',_env_file=None)
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/v1/admin/dashboard').status_code==401
        register(client,'alice')
        assert not client.get('/api/v1/auth/session').json()['student']['is_admin']
        assert client.get('/api/v1/admin/dashboard').status_code==403
        assert client.post('/api/v1/content/publish',json={}).status_code==403
        with connect(settings.database_path) as db:grant_admin(db,'alice')
        assert client.get('/api/v1/admin/dashboard').status_code==200
        with connect(settings.database_path) as db:grant_admin(db,'alice',revoke=True)
        assert client.get('/api/v1/admin/catalog').status_code==403


def test_editor_validation_and_drafts_are_not_visible_to_students(editor):
    client,settings=editor
    draft=new_draft(client)
    assert client.get('/api/v1/bank/questions').json()['total']==0
    assert client.get('/api/v1/admin/questions?family=draft').json()['total']==1
    for changes in [{'curriculum_goal_ids':['math-8-1:u1:g1']},{'answer':'C'},{'type_tags':['选择题']},{'steps':[]},{'grade':None},{'difficulty_basis':''}]:
        bad=new_draft(client,form(**changes));publish(client,bad,422)
    assert client.post('/api/v1/admin/drafts/'+draft['id']+'/publish',json={'revision':draft['revision'],'reviewed':False,'review_note':'没有人工核对'}).status_code==422
    good=publish(client,draft)
    assert good['state']=='published'
    assert client.get('/api/v1/bank/questions').json()['total']==1
    assert client.get('/api/v1/admin/dashboard').json()['totals']['reviewed']==1
    with connect(settings.database_path) as db:
        links=db.execute('SELECT goal_id,data FROM course_question_links WHERE question_id=?',(good['published_id'],)).fetchall()
        assert [r['goal_id'] for r in links]==form()['curriculum_goal_ids']
        assert not json.loads(links[0]['data'])['needs_review']


def test_question_revision_and_withdrawal_preserve_old_answers_and_learning_records(editor):
    client,settings=editor;draft=publish(client,new_draft(client))
    attempt=client.post('/api/v1/study/next',json={'choice':True}).json()
    result=client.post(f"/api/v1/bank/attempts/{attempt['attempt_id']}/answer",json={'answer':'A'}).json()
    assert result['correct']
    updated=client.put('/api/v1/admin/drafts/'+draft['id'],json={'revision':draft['revision'],'form':form(answer='B',options=[{'key':'A','text':'-3'},{'key':'B','text':'3'}])}).json()
    assert client.get('/api/v1/admin/question',params={'family':'bank','id':draft['published_id']}).json()['answer']=='A'
    current=publish(client,updated)
    assert current['published_id']!=draft['published_id']
    saved=client.get(f"/api/v1/bank/attempts/{attempt['attempt_id']}").json()
    assert saved['result']==result and saved['question']['id']==draft['published_id']
    next_attempt=client.post('/api/v1/study/next',json={'choice':True}).json()
    second=client.post(f"/api/v1/bank/attempts/{next_attempt['attempt_id']}/answer",json={'answer':'B'}).json()
    assert second['correct'] and second['evidence_weight']==0
    response=client.post('/api/v1/admin/drafts/'+draft['id']+'/withdraw',json={'revision':current['revision']})
    assert response.status_code==200
    assert client.post('/api/v1/study/next',json={'choice':True}).status_code==404
    assert client.get(f"/api/v1/bank/attempts/{attempt['attempt_id']}").json()['result']==result


def test_optimistic_revision_prevents_concurrent_lost_updates(editor):
    client,settings=editor;draft=new_draft(client);barrier=Barrier(2)
    def save(stem):
        barrier.wait(timeout=5)
        return client.put('/api/v1/admin/drafts/'+draft['id'],json={'revision':draft['revision'],'form':form(stem=stem)}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(save,['修改窗口甲','修改窗口乙']))
    assert sorted(results)==[200,409]


def test_source_correction_is_versioned_and_missing_assets_cannot_be_published(editor):
    client,settings=editor
    raw={**form(),'id':'source-test','stage':'junior','status':'ready','tags_source':'source','provenance':{'dataset':'source-test','source_id':'stable-id','license':'original'}}
    with connect(settings.database_path) as db:bank.import_records(db,'source-test',[raw,{**raw,'id':'missing','stem':'见图解题。','has_missing_assets':True}],{})
    draft=client.post('/api/v1/admin/drafts',json={'family':'bank','question_id':'source-test'}).json()
    assert client.post('/api/v1/admin/drafts',json={'family':'bank','question_id':'source-test'}).json()['id']==draft['id']
    current=publish(client,draft)
    with connect(settings.database_path) as db:
        assert db.execute('SELECT status FROM bank_questions WHERE id=?',('source-test',)).fetchone()[0]=='superseded'
        q=json.loads(db.execute('SELECT data FROM bank_questions WHERE id=?',(current['published_id'],)).fetchone()[0])
        assert q['provenance']['source_id']=='stable-id' and q['provenance']['license']=='original'
    missing=client.post('/api/v1/admin/drafts',json={'family':'bank','question_id':'missing'}).json()
    publish(client,missing,422)


def test_release_is_frozen_idempotent_protected_and_contains_only_question_content(editor):
    client,settings=editor;publish(client,new_draft(client));new_draft(client,form(stem='未发布草稿'))
    manifest,raw=export(client)
    assert export(client)[0]==manifest
    assert hashlib.sha256(raw).hexdigest()==manifest['checksum']
    package=json.loads(raw)
    assert set(package)=={'schema_version','publisher_id','version','curriculum_version','items','retired'}
    assert sum(i['family']=='bank' for i in package['items'])==1
    assert all('password' not in i['data'] and 'student_id' not in i['data'] for i in package['items'])
    client.post('/api/v1/auth/logout')
    assert client.get('/api/v1/content/feed/package').status_code==401
    assert client.get('/api/v1/content/feed/manifest',headers={'Authorization':'Bearer wrong'}).status_code==401
    assert client.get('/api/v1/content/feed/manifest',headers={'Authorization':'Bearer '+settings.content_feed_key}).json()==manifest


def test_atomic_install_idempotency_withdrawals_and_local_data_preservation(editor,tmp_path):
    client,settings=editor;draft=publish(client,new_draft(client));manifest,raw=export(client)
    target=tmp_path/'offline.sqlite3';initialize(target)
    with connect(target) as db:
        before=db.execute('SELECT * FROM students').fetchall()
        result=content.install_package(db,raw,manifest)
        assert result['updated']
    with connect(target) as db:
        assert content.install_package(db,raw,manifest)['updated'] is False
        assert [tuple(r) for r in db.execute('SELECT * FROM students')]==[tuple(r) for r in before]
        assert db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]==1
    client.post('/api/v1/admin/drafts/'+draft['id']+'/withdraw',json={'revision':draft['revision']})
    next_manifest,next_raw=export(client)
    assert next_manifest['version']==manifest['version']+1
    with connect(target) as db:content.install_package(db,next_raw,next_manifest)
    with connect(target) as db:
        assert db.execute("SELECT count(*) FROM bank_questions WHERE status='superseded'").fetchone()[0]==1
        with pytest.raises(ValueError,match='降级'):content.install_package(db,raw,manifest)


def test_corrupt_or_incompatible_packages_never_advance_version(editor,tmp_path):
    client,settings=editor;publish(client,new_draft(client));manifest,raw=export(client)
    target=tmp_path/'offline.sqlite3';initialize(target)
    with connect(target) as db:
        with pytest.raises(ValueError,match='校验'):content.install_package(db,raw+b' ',manifest)
    bad=json.loads(raw);bad['items'][-1]['data']['answer']='INVALID'
    bad_raw=content.encoded(bad);bad_manifest={**manifest,'checksum':hashlib.sha256(bad_raw).hexdigest()}
    with connect(target) as db:
        with pytest.raises(ValueError):content.install_package(db,bad_raw,bad_manifest)
    with connect(target) as db:
        assert db.execute('SELECT count(*) FROM content_installs').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]==0


def test_frontend_can_check_and_install_from_authenticated_remote_feed(editor,tmp_path,monkeypatch):
    publisher,settings=editor;publish(publisher,new_draft(publisher));manifest,raw=export(publisher)
    target=Settings(database_path=tmp_path/'client.sqlite3',content_source_url='https://editor.example',content_source_key=settings.content_feed_key,_env_file=None)
    real_client=httpx.AsyncClient
    monkeypatch.setattr(content.httpx,'AsyncClient',lambda **kwargs:real_client(transport=httpx.ASGITransport(app=publisher.app),**kwargs))
    with TestClient(create_app(target)) as client:
        register(client,'student')
        check=client.get('/api/v1/content/check');assert check.status_code==200,check.text
        assert check.json()['available']
        update=client.post('/api/v1/content/update',json={});assert update.status_code==200,update.text
        assert update.json()['updated']
        assert not client.get('/api/v1/content/check').json()['available']
        assert client.post('/api/v1/study/next',json={'choice':True}).status_code==200
        assert client.get('/api/v1/admin/dashboard').status_code==403


def test_v10_migration_preserves_account_and_does_not_grant_admin(tmp_path):
    path=tmp_path/'v10.sqlite3';settings=Settings(database_path=path,_env_file=None)
    with TestClient(create_app(settings)) as client:register(client,'old-student')
    with connect(path) as db:
        before=tuple(db.execute('SELECT * FROM accounts').fetchone())
        for table in ['bank_editor_events','bank_editor_items','admin_accounts','content_meta','content_releases','content_installs','content_installed_items']:
            db.execute('DROP TABLE '+table)
        db.execute('PRAGMA user_version=10')
    initialize(path)
    with connect(path) as db:
        assert tuple(db.execute('SELECT * FROM accounts').fetchone())==before
        assert db.execute('SELECT count(*) FROM admin_accounts').fetchone()[0]==0
        assert db.execute('PRAGMA user_version').fetchone()[0]==16


def test_correcting_bad_reference_answer_keeps_history_but_retires_unreliable_evidence(editor,tmp_path):
    client,settings=editor;draft=publish(client,new_draft(client,form(answer='B')))
    initial,raw=export(client)
    target=tmp_path/'retirement.sqlite3';initialize(target)
    with connect(target) as db:content.install_package(db,raw,initial)
    work=client.post('/api/v1/study/next',json={'choice':True}).json()
    result=client.post(f"/api/v1/bank/attempts/{work['attempt_id']}/answer",json={'answer':'A'}).json()
    assert not result['correct']
    changed=client.put('/api/v1/admin/drafts/'+draft['id'],json={'revision':draft['revision'],'form':form(answer='A')}).json()
    publish(client,changed)
    with connect(settings.database_path) as db:
        old=json.loads(db.execute('SELECT data FROM bank_questions WHERE id=?',(draft['published_id'],)).fetchone()[0])
        assert old['evidence_invalidated'] and old['answer']=='B'
    assert client.get('/api/v1/reports').json()['summary']['independent']==0
    fresh=client.post('/api/v1/study/next',json={'choice':True}).json()
    corrected=client.post(f"/api/v1/bank/attempts/{fresh['attempt_id']}/answer",json={'answer':'A'}).json()
    assert corrected['correct'] and corrected['evidence_weight']==1
    assert client.get(f"/api/v1/bank/attempts/{work['attempt_id']}").json()['result']==result
    latest,raw=export(client)
    with connect(target) as db:content.install_package(db,raw,latest)
    with connect(target) as db:
        old=json.loads(db.execute("SELECT data FROM bank_questions WHERE status='superseded'").fetchone()[0])
        assert old['evidence_invalidated'] and old['answer']=='B'


def test_failed_install_after_inserts_rolls_back_whole_transaction(editor,tmp_path):
    client,settings=editor;publish(client,new_draft(client));manifest,raw=export(client)
    target=tmp_path/'rollback.sqlite3';initialize(target)
    with connect(target) as db:content.install_package(db,raw,manifest)
    package=json.loads(raw);package['version']+=1
    first=next(i for i in package['items'] if i['family']=='bank')
    new=json.loads(json.dumps(first));new['data']['id']='different-snapshot';new['data']['stem']='求 -5 的绝对值。'
    package['items'].insert(0,new)
    first['data']['answer']='B'  # 有效结构但非法重写已安装快照。
    raw=content.encoded(package)
    next_manifest={**manifest,'version':package['version'],'item_count':len(package['items']),'checksum':hashlib.sha256(raw).hexdigest()}
    with connect(target) as db:
        with pytest.raises(ValueError,match='快照'):content.install_package(db,raw,next_manifest)
    with connect(target) as db:
        assert db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]==1
        assert db.execute('SELECT version FROM content_installs').fetchone()[0]==manifest['version']
