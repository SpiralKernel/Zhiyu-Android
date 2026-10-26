"""Automatic file ingestion uses the existing calibration gate, with fake inference."""
import asyncio
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app import bank_ingest
from app.bank_ingest import IngestService, parse_file
from app.calibration import calibrated
from app.config import Settings
from app.db import connect, now
from app.main import create_app
from test_calibration import make_report
from test_student import register

BASE='/api/v1/admin/ingest'


@pytest.fixture
def setup(tmp_path,monkeypatch):
    settings=Settings(database_path=tmp_path/'db.sqlite3',local_audit_enabled=True,local_audit_model='test-local:8b',_env_file=None)
    async def tags(self,url,**kwargs):
        assert url=='http://127.0.0.1:11434/api/tags'
        return httpx.Response(200,json={'models':[{'name':'test-local:8b'}]},request=httpx.Request('GET',url))
    async def run(task_path,output,engine,model,**kwargs):
        assert model=='test-local:8b'
        task=json.loads(task_path.read_text())
        report=make_report(task)
        if kwargs.get('on_progress'):await kwargs['on_progress'](report)
        return report
    monkeypatch.setattr(httpx.AsyncClient,'get',tags)
    monkeypatch.setattr(bank_ingest,'run_task',run)
    with TestClient(create_app(settings)) as client:
        register(client)
        with connect(settings.database_path) as db:
            db.execute("INSERT INTO admin_accounts SELECT student_id,? FROM accounts WHERE username='alice'",(now(),))
        yield client,settings


def upload(client,records=None,**data):
    records=records or [{'stem':'计算 -5 - (-4)。','reference_answer':'-1'}]
    return client.post(BASE+'/jobs',data={'book_id':'math-7-1',**data},files={'files':('questions.json',json.dumps(records).encode(),'application/json')})


def finished(client,jid):
    for _ in range(100):
        value=client.get(BASE+'/jobs/'+jid).json()
        if value['status'] not in {'queued','running'}:return value
        time.sleep(.01)
    raise AssertionError('worker did not finish')


def test_file_automatically_validates_and_publishes(setup):
    client,settings=setup
    response=upload(client);assert response.status_code==202,response.text
    value=finished(client,response.json()['id'])
    assert value['status']=='completed' and value['counts']['published']==1
    assert 'result' not in value['items'][0]
    with connect(settings.database_path) as db:
        question=json.loads(db.execute("SELECT data FROM bank_questions WHERE source_id='local-calibration'").fetchone()[0])
        assert calibrated(question)
        assert question['provenance']['teacher_reviewed'] is False
        assert question['quality']['calibration']['independent_eligible'] is False
    assert client.get(BASE+'/jobs').json()['items'][0]['counts']['published']==1


def test_disagreement_remains_out_of_bank(setup,monkeypatch):
    client,settings=setup
    async def run(task_path,output,engine,model,**kwargs):
        report=make_report(json.loads(task_path.read_text()),lambda a,b,j:j.update(verdict='hold',answers_agree=False))
        await kwargs['on_progress'](report)
        return report
    monkeypatch.setattr(bank_ingest,'run_task',run)
    value=finished(client,upload(client).json()['id'])
    assert value['counts']['hold']==1 and value['counts']['published']==0
    assert value['items'][0]['issues']


def test_admin_permission_and_disabled_default(setup):
    client,settings=setup
    with connect(settings.database_path) as db:db.execute('DELETE FROM admin_accounts')
    assert client.get(BASE+'/jobs').status_code==403
    assert upload(client).status_code==403
    with connect(settings.database_path) as db:db.execute("INSERT INTO admin_accounts SELECT student_id,? FROM accounts WHERE username='alice'",(now(),))
    settings.local_audit_enabled=False
    assert client.get(BASE+'/status').json()['enabled'] is False
    assert upload(client).status_code==409
    assert Settings(_env_file=None).local_audit_enabled is False


def test_uninstalled_model_and_malformed_files_rejected(setup):
    client,_=setup
    assert upload(client,model='not-installed').status_code==409
    assert client.post(BASE+'/jobs',data={'book_id':'math-7-1'},files={'files':('bad.json',b'{broken')}).status_code==422
    assert upload(client,[{'id':'dup','stem':'1+1'},{'id':'dup','stem':'2+2'}]).status_code==422
    assert client.post(BASE+'/jobs',data={'book_id':'math-7-1'},files={'files':('bad.exe',b'bad')}).status_code==422
    assert client.get(BASE+'/jobs/not-a-uuid').status_code==404
    assert client.get(BASE+'/example').json()['stem']=='计算 -5 - (-4)。'


def test_stop_and_resume_preserve_task(setup,monkeypatch):
    client,_=setup
    actual=bank_ingest.run_task
    async def blocking(*args,**kwargs):await asyncio.sleep(3600)
    monkeypatch.setattr(bank_ingest,'run_task',blocking)
    value=upload(client).json();jid=value['id']
    stopped=client.post(BASE+f'/jobs/{jid}/stop').json()
    assert stopped['status']=='interrupted'
    monkeypatch.setattr(bank_ingest,'run_task',actual)
    assert client.post(BASE+f'/jobs/{jid}/resume').status_code==200
    assert finished(client,jid)['counts']['published']==1
    assert client.post(BASE+f'/jobs/{jid}/resume').status_code==409


def test_restart_marks_queued_jobs_interrupted(setup):
    client,settings=setup
    value=finished(client,upload(client).json()['id'])
    service=IngestService(settings)
    state=service.read(value['id']);state['status']='running';service.save(state)
    service.recover()
    assert service.read(value['id'])['status']=='interrupted'
    assert service.view(value['id'])['counts']['published']==1


def test_text_parsing_retains_full_stems_and_separate_answers():
    sources=parse_file('习题.txt','1. 计算 -5 - (-4)。\n答案：-1\n2. 计算 1+2。\n答案：3'.encode())
    assert len(sources)==2
    assert sources[0].stem=='计算 -5 - (-4)。' and sources[0].reference_answer=='-1'
    assert sources[1].stem=='计算 1+2。'
    assert 'SHA256:' in sources[0].source_label
    assert parse_file('one.json',b'{"stem":"1+1","answer":"2"}')[0].reference_answer=='2'
    with pytest.raises(ValueError,match='公共题干'):
        parse_file('shared.txt','阅读公共条件\n1. 第一问\n2. 第二问'.encode())
    with pytest.raises(ValueError):parse_file('empty.txt',b'')
    with pytest.raises(ValueError):parse_file('bad.jsonl',b'not json')


def test_pdf_extraction_rejects_image_pages(monkeypatch):
    class Page:
        images=[]
        def extract_text(self):return '1. Calculate -5-(-4).'
    class Reader:
        is_encrypted=False
        pages=[Page()]
    monkeypatch.setattr(bank_ingest,'PdfReader',lambda _:Reader())
    assert parse_file('paper.pdf',b'pdf-test')[0].stem=='1. Calculate -5-(-4).'
    Page.images=['diagram']
    with pytest.raises(ValueError,match='扫描页或题图'):parse_file('paper.pdf',b'pdf-test')
