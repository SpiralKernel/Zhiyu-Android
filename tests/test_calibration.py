"""Calibration uses isolated accounts/DB and mocked model calls, never student data."""
import asyncio
import copy
import io
import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import bank, content
from app.calibration import (Finding, Judgment, Report, Result, Round, Source, calibrated,
                             digest, prompt, resolved_source)
from app.calibration_catalog import catalog
from app.config import Settings
from app.db import connect, now
from app.local_calibration import LocalModel, run_task, to_ollama, write_json
from app.main import create_app
from test_student import register

BASE='/api/v1/admin/calibration'
STEM='计算 -5 - (-4)。'


@pytest.fixture
def setup(tmp_path):
    settings=Settings(database_path=tmp_path/'calibration.sqlite3',_env_file=None)
    with TestClient(create_app(settings)) as client:
        register(client)
        with connect(settings.database_path) as db:
            db.execute("INSERT INTO admin_accounts SELECT student_id,? FROM accounts WHERE username='alice'",(now(),))
        yield client,settings


def task(client,sources=None):
    r=client.post(BASE+'/jobs',json={'book_id':'math-7-1','sources':sources or [{'id':'q1','stem':STEM,'reference_answer':'-1'}]})
    assert r.status_code==200,r.text
    return r.json()


def finding(source):
    choice=source['kind'] in {'single_choice','multiple_choice'}
    answer='A' if choice else '-1'
    return Finding(decision='pass',reason='条件齐全，可按减去相反数求解。',recognized_stem=source['stem'],
        response_format=source['kind'] if choice else 'calculation',difficulty=1,difficulty_basis='一次减去负数的基础计算。',
        parts=[{'id':'p1','prompt':source['stem'],'answer':answer,'solution':['减去负数等于加上它的相反数。','-5+4=-1。'],
            'primary':['k:math-7-1:u2:g1'],'types':['m7a:subtract-negative'],'tag_evidence':source['stem'],
            'rubric':[{'id':'sign','description':'正确改写减法并求值','evidence_required':'作答呈现减去负数转为加正数，结果为-1。'}],
            'answer_spec':{'mode':'choice' if choice else 'numeric','equivalence':'exact' if choice else 'numeric','accepted_answers':[answer]}}])


def make_report(t,change=None):
    rows=[]
    for item in t['items']:
        a=finding(item['source']).model_dump();b=copy.deepcopy(a)
        j=Judgment(verdict='pass',source_complete=True,answers_agree=True,solutions_valid=True,tags_supported=True,
                   rubric_complete=True,scope_supported=True,source_answer='match' if item['source']['reference_answer'] or item['source']['reference_answers'] else 'not_provided',reason='两次独立解法和标签依据一致。').model_dump()
        if change:change(a,b,j)
        rounds=[]
        for role,out in [('primary',a),('peer',b),('judge',j)]:
            messages=prompt(t,item,role,[a,b] if role=='judge' else None)
            rounds.append(Round(role=role,requested_model='test-local:8b',served_model='test-local:8b',backend='ollama',context_size=16384,
                                created_at=now(),prompt_sha256=digest(messages),output=out))
        rows.append(Result(protocol_version=t.get('protocol_version',1),question_id=item['question_id'],source_sha256=item['source_sha256'],rounds=rounds))
    return Report(job_id=t['job_id'],task_sha256=t['task_sha256'],catalog_sha256=t['catalog']['sha256'],items=rows)


def import_result(client,report):
    r=client.post(BASE+'/results?auto_publish=false',json=report.model_dump());assert r.status_code==200,r.text
    return r.json()


def test_catalog_has_stable_ids_and_no_future_knowledge():
    a=catalog('math-7-1');assert a==catalog('math-7-1')
    assert len({t['id'] for t in a['tags']})==len(a['tags'])
    assert all(t['book_id']=='math-7-1' for t in a['tags'])
    assert any(t['id']=='m7a:subtract-negative' for t in a['tags'])
    for bid in ('math-7-2','math-8-1','math-8-2','math-9-1','math-9-2','physics-8-1','math-senior-selective-2'):
        c=catalog(bid);assert any(t['kind']=='type' for t in c['tags'])
        assert all(t['definition'] for t in c['tags'])


def test_structured_output_limits_tag_ids_and_disallows_invented_scores(setup):
    from app.calibration import output_schema
    client,_=setup;t=task(client);schema=output_schema(t,'primary')
    fields=schema['$defs']['Part']['properties']
    assert fields['types']['items']['enum']==[v['id'] for v in t['catalog']['tags'] if v['kind']=='type']
    assert 'k:math-7-1:u2:g1' in fields['primary']['items']['enum']
    assert schema['$defs']['Criterion']['properties']['points']['type']=='null'


def test_routes_require_admin(setup):
    client,_=setup
    client.post('/api/v1/auth/logout',json={})
    assert client.get(BASE+'/catalog?book_id=math-7-1').status_code==401
    register(client,'bob')
    assert client.get(BASE+'/jobs').status_code==403
    assert client.post(BASE+'/jobs',json={'book_id':'math-7-1'}).status_code==403


def test_full_workflow_publishes_ai_review_without_teacher_or_mastery(setup):
    client,settings=setup
    t=task(client)
    report=make_report(t)
    result=import_result(client,report);assert result['counts']['ready']==1
    assert import_result(client,report)==result
    r=client.post(BASE+f'/jobs/{t["job_id"]}/publish',json={});assert r.status_code==200,r.text
    value=r.json();qid=value['items'][0]['published_id'];assert value['counts']['published']==1
    assert client.post(BASE+f'/jobs/{t["job_id"]}/publish',json={}).json()==value
    with connect(settings.database_path) as db:
        q=json.loads(db.execute('SELECT data FROM bank_questions WHERE id=?',(qid,)).fetchone()[0])
        assert calibrated(q) and q['annotation']['review']['status']=='ai_reviewed'
        assert q['provenance']['teacher_reviewed'] is False
        assert q['annotation']['origin']['model']=='test-local:8b'
        assert q['quality']['calibration']['tag_ids']['types']==['m7a:subtract-negative']
        assert db.execute('SELECT count(*) FROM bank_editor_events').fetchone()[0]==0
    assert client.get('/api/v1/admin/questions?reviewed=calibrated').json()['total']==1


def test_choice_feedback_does_not_become_independent_evidence(setup):
    client,settings=setup
    t=task(client,[{'id':'c1','stem':STEM,'kind':'single_choice','options':[{'key':'A','text':'-1'},{'key':'B','text':'-9'}],'reference_answer':'A'}])
    import_result(client,make_report(t));client.post(BASE+f'/jobs/{t["job_id"]}/publish',json={})
    r=client.post('/api/v1/study/next',json={'choice':True});assert r.status_code==200,r.text
    w=r.json();assert 'answer' not in w['question']
    result=client.post(f"/api/v1/bank/attempts/{w['attempt_id']}/answer",json={'answer':'A'}).json()
    assert result['correct'] and result['evidence_weight']==0 and result['assessment_source']=='local_ai_reference'
    assert sum(t['independent_count'] for t in client.get('/api/v1/study/home').json()['types'])==0


@pytest.mark.parametrize('failure',['tag','new_tag','answer','difficulty','rubric','source_answer'])
def test_bad_or_conflicting_calibration_stays_out_of_bank(setup,failure):
    client,settings=setup;t=task(client)
    def change(a,b,j):
        if failure=='tag':a['parts'][0]['types']=['invented:type']
        if failure=='new_tag':a['proposed_tags']=[{'kind':'type','name':'新题型','definition':'候选定义','reason':'现有库不覆盖'}]
        if failure=='answer':b['parts'][0]['answer']='-9';b['parts'][0]['answer_spec']['accepted_answers']=['-9']
        if failure=='difficulty':b['difficulty']=3
        if failure=='rubric':a['parts'][0]['rubric'][0]['points']=2
        if failure=='source_answer':j['source_answer']='conflict'
    value=import_result(client,make_report(t,change));assert value['counts']['hold']==1
    assert client.post(BASE+f'/jobs/{t["job_id"]}/publish',json={}).json()['counts']['published']==0
    with connect(settings.database_path) as db:
        assert db.execute("SELECT count(*) FROM bank_questions WHERE source_id='local-calibration'").fetchone()[0]==0
        assert not db.execute("SELECT 1 FROM bank_taxonomy WHERE label='新题型'").fetchone()


def test_hashes_prompt_binding_and_duplicate_results_rejected(setup):
    client,settings=setup;t=task(client);r=make_report(t)
    r.task_sha256='0'*64
    assert client.post(BASE+'/results',json=r.model_dump()).status_code==422
    r=make_report(t);r.items.append(r.items[0])
    assert client.post(BASE+'/results',json=r.model_dump()).status_code==422
    r=make_report(t);r.items[0].rounds[0].prompt_sha256='0'*64
    assert client.post(BASE+'/results',json=r.model_dump()).status_code==422
    with connect(settings.database_path) as db:assert db.execute('SELECT result FROM calibration_items').fetchone()[0] is None


def test_published_content_changes_invalidate_calibration(setup):
    client,settings=setup;t=task(client);import_result(client,make_report(t))
    qid=client.post(BASE+f'/jobs/{t["job_id"]}/publish',json={}).json()['items'][0]['published_id']
    with connect(settings.database_path) as db:
        q=json.loads(db.execute('SELECT data FROM bank_questions WHERE id=?',(qid,)).fetchone()[0])
        for field,value in [('answer','-9'),('stem','另外一道题'),('difficulty',3)]:
            changed=copy.deepcopy(q);changed[field]=value;assert not calibrated(changed)
        changed=copy.deepcopy(q);changed['annotation']['fine_types']=['随意标签'];assert not calibrated(changed)


def test_content_distribution_retains_ai_identity_and_excludes_tampered_records(setup,tmp_path):
    client,settings=setup;t=task(client);import_result(client,make_report(t))
    qid=client.post(BASE+f'/jobs/{t["job_id"]}/publish',json={}).json()['items'][0]['published_id']
    with connect(settings.database_path) as db:
        meta=content.publish_release(db);raw=db.execute('SELECT data FROM content_releases WHERE version=?',(meta['version'],)).fetchone()[0].encode()
        package=json.loads(raw);assert any(i['data']['id']==qid for i in package['items'])
    from app.db import initialize
    other=tmp_path/'other.sqlite3';initialize(other)
    with connect(other) as db:
        content.install_package(db,raw,meta)
        q=json.loads(db.execute("SELECT data FROM bank_questions WHERE json_extract(data,'$.quality.calibration.status')='ai_reviewed'").fetchone()[0])
        assert calibrated(q) and q['provenance']['teacher_reviewed'] is False
        assert all(t['origin']=='model_review' for t in q['tags'])


class FakeEngine:
    def __init__(self,task):self.task=task;self.messages=[];self.fail=False
    async def inspect(self,model):pass
    async def ask(self,messages,schema,model,role,**kwargs):
        self.messages.append(messages)
        if self.fail:raise ValueError('服务暂时不可用')
        r=make_report(self.task).items[0].rounds[['primary','peer','judge'].index(role)]
        r.prompt_sha256=digest(messages);return r


def test_worker_blind_rounds_do_not_receive_source_answers_or_peer_solution(setup,tmp_path):
    client,_=setup;t=task(client,[{'id':'q1','stem':STEM,'reference_answer':'SOURCE_ANSWER_SENTINEL','source_steps':['SOURCE_SOLUTION_SENTINEL']}])
    engine=FakeEngine(t);path=tmp_path/'task.json';out=tmp_path/'result.json';write_json(path,t)
    report=asyncio.run(run_task(path,out,engine,'test-local:8b'))
    assert len(engine.messages)==3 and not report.items[0].error
    for messages in engine.messages[:2]:
        text=json.dumps(messages)
        assert 'SOURCE_ANSWER_SENTINEL' not in text and 'SOURCE_SOLUTION_SENTINEL' not in text
        assert 'independent_findings' not in text
    assert 'SOURCE_ANSWER_SENTINEL' in json.dumps(engine.messages[2])
    assert out.stat().st_mode&0o777==0o600
    engine.messages=[];asyncio.run(run_task(path,out,engine,'test-local:8b'));assert engine.messages==[]


def test_worker_failure_checkpoints_and_can_retry(setup,tmp_path):
    client,_=setup;t=task(client);path=tmp_path/'task.json';out=tmp_path/'result.json';write_json(path,t)
    engine=FakeEngine(t);engine.fail=True
    failed=asyncio.run(run_task(path,out,engine,'test-local:8b'));assert failed.items[0].error
    engine.fail=False
    success=asyncio.run(run_task(path,out,engine,'test-local:8b',retry_failed=True));assert not success.items[0].error


def test_local_model_stays_on_loopback_by_default():
    LocalModel();LocalModel('http://localhost:1234/v1',backend='openai')
    with pytest.raises(ValueError):LocalModel('https://example.com/v1')
    with pytest.raises(ValueError):LocalModel('http://user:secret@localhost:1234')
    LocalModel('http://192.168.1.2:11434',allow_remote=True)


def test_image_payload_not_duplicated_into_model_text(setup):
    image=Image.new('RGB',(32,32),'white');b=io.BytesIO();image.save(b,format='PNG')
    url='data:image/png;base64,'+base64.b64encode(b.getvalue()).decode()
    client,_=setup;t=task(client,[{'stem':STEM,'images':[url]}]);m=prompt(t,t['items'][0],'primary')
    assert url not in m[1]['content'][0]['text']
    assert to_ollama(m)[1]['images']==[url.split(',')[1]]


def test_ollama_transport_records_actual_model_and_does_not_use_teacher_key(monkeypatch):
    monkeypatch.setenv('AI_API_KEY','teacher-key-should-not-be-sent')
    seen=[]
    def handle(request):
        seen.append(request);assert 'authorization' not in request.headers
        if request.method=='GET':return httpx.Response(200,json={'models':[{'name':'local:8b','digest':'model-file-digest'}]})
        data=json.loads(request.content);assert data['stream'] is False and data['format']['type']=='object'
        assert 'think' not in data and data['options']['temperature']==0.6
        assert data['options']['num_predict']==8192
        return httpx.Response(200,json={'model':'local:8b','done':True,'done_reason':'stop','message':{'content':json.dumps(finding({'kind':'reference','stem':STEM}).model_dump())}})
    actual=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:actual(transport=httpx.MockTransport(handle),**kwargs))
    async def work():
        engine=LocalModel();await engine.inspect('local:8b')
        return await engine.ask([{'role':'user','content':'合成题'}],Finding,'local:8b','primary')
    r=asyncio.run(work());assert r.served_model=='local:8b' and r.model_digest=='model-file-digest' and len(seen)==2
    assert r.generation['temperature']==0.6 and r.generation['thinking'] is None


def test_auto_choice_options_must_come_from_original_text(setup):
    client,_=setup
    def change(a,b,j):
        for f in (a,b):
            f['response_format']='single_choice';f['recognized_options']=[{'key':'A','text':'-1'},{'key':'B','text':'-9'}]
            f['parts'][0]['answer']='A';f['parts'][0]['answer_spec']={'mode':'choice','equivalence':'exact','accepted_answers':['A']}
    t=task(client,[{'id':'missing-options','stem':STEM}])
    assert import_result(client,make_report(t,change))['counts']['hold']==1
    t=task(client,[{'id':'provided-options','stem':STEM+' A.-1 B.-9'}])
    assert import_result(client,make_report(t,change))['counts']['ready']==1


def test_multipart_keeps_individual_answers_and_unknown_scores(setup):
    client,settings=setup
    stem='（1）计算 -5 - (-4)。（2）计算 -2 - (-1)。'
    t=task(client,[{'id':'multi','stem':stem,'reference_answers':{'p1':'-1','p2':'-1'}}])
    def change(a,b,j):
        for f in (a,b):
            f['response_format']='composite'
            p1=f['parts'][0];p1['prompt']='计算 -5 - (-4)。';p1['tag_evidence']=p1['prompt']
            p2=copy.deepcopy(p1);p2.update(id='p2',prompt='计算 -2 - (-1)。',tag_evidence='计算 -2 - (-1)。',solution=['减去负数改为加正数。','-2+1=-1。'])
            f['parts']=[p1,p2]
    assert import_result(client,make_report(t,change))['counts']['ready']==1
    result=client.post(BASE+f'/jobs/{t["job_id"]}/publish',json={}).json()
    with connect(settings.database_path) as db:
        q=json.loads(db.execute('SELECT data FROM bank_questions WHERE id=?',(result['items'][0]['published_id'],)).fetchone()[0])
        assert calibrated(q)
        assert [p['reference_answer'] for p in q['annotation']['parts']]==['-1','-1']
        assert q['annotation']['grading']['full_score'] is None
        assert all(c['points'] is None for p in q['annotation']['parts'] for c in p['rubric'])


def test_existing_bank_source_changes_abort_whole_publication(setup):
    client,settings=setup
    records=[{'id':f'legacy-{i}','stem':f'第{i+1}题：'+STEM,'subject':'math','stage':'junior','grade':7,'term':1,
              'kind':'single_choice','status':'ready','options':[{'key':'A','text':'-1'},{'key':'B','text':'-9'}],
              'answer':'A','steps':['减去负数等于加上相反数。'],'difficulty':1,
              'knowledge_tags':['有理数加减'],'type_tags':['负数减负数'],
              'provenance':{'dataset':'legacy-test','source_id':str(i)}} for i in range(2)]
    with connect(settings.database_path) as db:bank.import_records(db,'legacy-test',records,{})
    response=client.post(BASE+'/jobs',json={'book_id':'math-7-1','question_ids':['legacy-0','legacy-1']})
    assert response.status_code==200,response.text;t=response.json();assert len(t['items'])==2
    import_result(client,make_report(t))
    with connect(settings.database_path) as db:
        q=json.loads(db.execute("SELECT data FROM bank_questions WHERE id='legacy-1'").fetchone()[0])
        q['stem']+='来源已改';db.execute("UPDATE bank_questions SET data=? WHERE id='legacy-1'",(json.dumps(q),))
    assert client.post(BASE+f'/jobs/{t["job_id"]}/publish',json={}).status_code==422
    with connect(settings.database_path) as db:
        assert db.execute("SELECT count(*) FROM bank_questions WHERE source_id='local-calibration'").fetchone()[0]==0
        assert db.execute("SELECT status FROM bank_questions WHERE id='legacy-0'").fetchone()[0]=='ready'


def test_default_import_automatically_includes_passed_questions(setup):
    client,settings=setup;t=task(client);report=make_report(t)
    response=client.post(BASE+'/results',json=report.model_dump())
    assert response.status_code==200,response.text
    assert response.json()['counts']['published']==1
    again=client.post(BASE+'/results',json=report.model_dump())
    assert again.status_code==200
    assert again.json()['items'][0]['published_id']==response.json()['items'][0]['published_id']
    with connect(settings.database_path) as db:
        assert db.execute("SELECT count(*) FROM bank_questions WHERE source_id='local-calibration'").fetchone()[0]==1


def test_default_import_keeps_disagreement_out_of_bank(setup):
    client,settings=setup;t=task(client)
    report=make_report(t,lambda a,b,j:b.update(difficulty=3))
    response=client.post(BASE+'/results',json=report.model_dump())
    assert response.status_code==200,response.text
    assert response.json()['counts']['hold']==1
    assert response.json()['counts']['published']==0


def test_v2_schema_requires_observable_evidence_and_answer_spec(setup):
    from app.calibration import output_schema
    client,_=setup;t=task(client);assert t['protocol_version']==2
    schema=output_schema(t,'primary')
    criterion=schema['$defs']['Criterion']
    assert 'evidence_required' in criterion['required']
    assert criterion['properties']['evidence_required']['minLength']==1
    assert schema['$defs']['AnswerSpec']['properties']['accepted_answers']['minItems']==1


def test_numeric_sets_compare_exactly_without_extracting_numbers_from_prose():
    from app.calibration_checks import comparable,numeric_values
    assert comparable('-2或4','4和-2') is True
    assert comparable('-2或4','4和-3') is False
    assert comparable('25%','0.25') is True
    assert comparable('-5',r'-5{}^\circ \text{C}') is True
    assert numeric_values('x=2') is None
    assert numeric_values('参考答案是2') is None
    assert numeric_values('__import__("os").system("whoami")') is None
    assert numeric_values('2,2') is None


def test_v2_checks_text_multianswer_disagreement_even_when_judge_passes(setup):
    client,_=setup;t=task(client)
    def change(a,b,j):
        for f in (a,b):
            p=f['parts'][0];p['answer']='-2或4';p['answer_spec']={'mode':'text','equivalence':'exact','accepted_answers':['-2或4']}
        b['parts'][0]['answer']='-2或5';b['parts'][0]['answer_spec']['accepted_answers']=['-2或5']
    result=import_result(client,make_report(t,change))
    assert result['counts']['hold']==1
    assert any('独立数值或集合答案不一致' in x for x in result['items'][0]['result']['evaluation']['issues'])


def test_supported_axis_distance_recomputed_from_question_not_reference(setup):
    from app.calibration_checks import source_checks
    source=Source(stem='题目内容: 在数轴上，距离 $-12$ 为 4.5 个单位长度的点所表示的数是______。')
    f=finding({'kind':'reference','stem':source.stem})
    f.parts[0].answer='-7.5或-16.5';assert source_checks(source,f)==[]
    f.parts[0].answer='-7.5或-17.5';assert source_checks(source,f)
    source.stem+='还需满足另外一个条件。'
    assert source_checks(source,f)==[]  # Unsupported text never gets guessed.


def test_primary_knowledge_must_follow_selected_type_goal(setup):
    client,_=setup;t=task(client)
    def change(a,b,j):
        for f in (a,b):f['parts'][0]['primary'].append('k:math-7-1:u1:g1')
    result=import_result(client,make_report(t,change))
    assert result['counts']['hold']==1
    assert any('primary必须' in x for x in result['items'][0]['result']['evaluation']['issues'])


def test_worker_repairs_own_findings_without_leaking_other_round_or_reference(setup,tmp_path):
    from app.calibration import recorded_prompt
    client,_=setup;t=task(client,[{'id':'repair','stem':STEM,'reference_answer':'SOURCE_ANSWER_SENTINEL'}])
    class Repairs(FakeEngine):
        def __init__(self,t):super().__init__(t);self.calls={}
        async def ask(self,messages,schema,model,role,**kwargs):
            record=await super().ask(messages,schema,model,role,**kwargs)
            self.calls[role]=self.calls.get(role,0)+1
            if role!='judge' and self.calls[role]==1:
                record.output['parts'][0]['rubric'][0]['evidence_required']=''
            return record
    engine=Repairs(t);path=tmp_path/'task.json';out=tmp_path/'result.json';write_json(path,t)
    report=asyncio.run(run_task(path,out,engine,'test-local:8b'))
    assert engine.calls=={'primary':2,'peer':2,'judge':1}
    item=report.items[0];assert len(item.rounds[0].corrections)==1
    for round in item.rounds[:2]:
        m=recorded_prompt(t,t['items'][0],round.role,corrections=round.corrections)
        assert 'SOURCE_ANSWER_SENTINEL' not in json.dumps(m)
        assert 'independent_findings' not in json.dumps(m)
        assert digest(m)==round.prompt_sha256
    result=import_result(client,report)
    assert result['counts']['ready']==0  # Sentinel reference is deliberately non-numeric.
    tampered=report.model_copy(deep=True)
    tampered.items[0].rounds[0].corrections[0]['parts'][0]['answer']='-9'
    assert client.post(BASE+'/results',json=tampered.model_dump()).status_code==422


def test_retry_feedback_has_strict_bound_and_preserves_unfixed_record(setup,tmp_path):
    client,_=setup;t=task(client)
    class AlwaysInvalid(FakeEngine):
        async def ask(self,*args,**kwargs):
            r=await super().ask(*args,**kwargs)
            if r.role!='judge':r.output['parts'][0]['rubric'][0]['evidence_required']=''
            return r
    engine=AlwaysInvalid(t);path=tmp_path/'task.json';out=tmp_path/'result.json';write_json(path,t)
    report=asyncio.run(run_task(path,out,engine,'test-local:8b'))
    assert len(engine.messages)==7
    assert len(report.items[0].rounds[0].corrections)==2
    assert import_result(client,report)['counts']['hold']==1


def test_old_tasks_keep_original_prompt_and_idempotent_import(setup):
    from app.db import dumps
    client,settings=setup;t=task(client)
    t.pop('protocol_version');t['task_sha256']=digest({k:v for k,v in t.items() if k!='task_sha256'})
    with connect(settings.database_path) as db:db.execute('UPDATE calibration_jobs SET data=? WHERE id=?',(dumps(t),t['job_id']))
    report=make_report(t)
    legacy=report.model_dump()
    for item in legacy['items']:
        item.pop('protocol_version')
        for r in item['rounds']:r.pop('corrections');r.pop('generation')
    assert '标定协议v2' not in prompt(t,t['items'][0],'primary')[0]['content']
    response=client.post(BASE+'/results?auto_publish=false',json=legacy);assert response.status_code==200,response.text
    # Simulate a report persisted by the earlier application without new optional fields.
    with connect(settings.database_path) as db:
        value=json.loads(db.execute('SELECT result FROM calibration_items WHERE job_id=?',(t['job_id'],)).fetchone()[0])
        value['report']=legacy['items'][0]
        db.execute('UPDATE calibration_items SET result=? WHERE job_id=?',(dumps(value),t['job_id']))
    again=client.post(BASE+'/results?auto_publish=false',json=legacy)
    assert again.status_code==200,again.text


def test_new_task_rejects_old_protocol_output(setup):
    client,_=setup;t=task(client);report=make_report(t);report.items[0].protocol_version=1
    assert client.post(BASE+'/results',json=report.model_dump()).status_code==422


def test_rational_classification_checks_fraction_membership_independently():
    from app.calibration_checks import source_checks
    stem='将下列有理数填入对应的集合括号中：-4.6，+8，25%，0，-3/5，-6，-|-2|，-(-2.4)正数集合{__}整数集合{__}分数集合{__}有理数集合{__}'
    source=Source(stem=stem)
    f=finding({'kind':'reference','stem':stem})
    f.parts[0].answer='正数集合{8,25%,2.4}整数集合{8,0,-6,-2}分数集合{-4.6,25%,-3/5,2.4}有理数集合{-4.6,8,25%,0,-3/5,-6,-2,2.4}'
    assert source_checks(source,f)==[]
    original_stem=source.stem;source.stem=source.stem.replace('{__}','{<u>　　</u>…}')
    assert source_checks(source,f)==[]
    source.stem=original_stem
    f.parts[0].answer=f.parts[0].answer.replace('分数集合{-4.6,25%,-3/5,2.4}','分数集合{-4.6,25%,-3/5}')
    assert any('分数集合' in error for error in source_checks(source,f))
    f.parts=[copy.deepcopy(f.parts[0]) for _ in range(4)]
    answers=['8,25%,2.4','8,0,-6,-2','-4.6,25%,-3/5,2.4','-4.6,8,25%,0,-3/5,-6,-2,2.4']
    for p,label,answer in zip(f.parts,['正数','整数','分数','有理数'],answers):p.prompt=label+'集合';p.answer=answer
    assert source_checks(source,f)==[]


def test_printed_unit_must_not_be_duplicated_in_blank_answer(setup):
    from app.calibration import finding_issues
    client,_=setup;t=task(client)
    source=Source(stem='向南行驶5千米记作__千米。')
    f=finding({'kind':'reference','stem':source.stem})
    f.parts[0].prompt=source.stem;f.parts[0].answer='-5';f.parts[0].answer_spec.unit='千米'
    assert any('单位已印在空格后' in x for x in finding_issues(f,source,t['catalog']))
