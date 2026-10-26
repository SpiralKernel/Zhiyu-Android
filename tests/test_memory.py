"""Time-travel and integration tests of student memory, not LLM accuracy tests."""
import copy
import io
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import ai_policy, bank_ai, memory, observations
from app.config import Settings
from app.db import connect
from app.main import create_app
from app.observations import Observation
from app.teacher import Reply

BASE = datetime(2030, 1, 10, 12, tzinfo=timezone.utc)


def event(index, days=0, correct=True, identity=None):
    return {'identity':identity or str(index), 'attempt_id':str(index),
            'time':(BASE+timedelta(days=days)).isoformat(), 'correct':correct,
            'stem':'求负数的绝对值', 'answer':'3', 'source':'verified_template'}


def note(index='n', kind='difficulty', days=0, quote='|-3|=-3'):
    return {'id':index,'type_id':'m7a:absolute','type_name':'负数的绝对值',
            'kind':kind,'created_at':(BASE+timedelta(days=days)).isoformat(),
            'evidence_quote':quote,'note':'学生将距离算成负数。',
            'policy_version':ai_policy.VERSION,'validation':{'method':'independent_ai_review'},
            'confidence':'medium'}


def test_difficulty_resolves_only_after_new_correct_items_on_multiple_days():
    original=note()
    for values in ([event(1,1)], [event(i,1) for i in range(3)],
                   [event(1,1),event(2,2,False),event(3,3),event(4,4)],
                   [event(i,i,identity='same-question') for i in range(1,5)]):
        assert memory.project([original],values,BASE+timedelta(days=5))[0]['memory_status']=='active'
    values=[event(1,1),event(2,1),event(3,2)]
    result=memory.project([original],values,BASE+timedelta(days=3))[0]
    assert result['memory_status']=='resolved' and result['resolved_by']==['1','2','3']
    assert result['resolved_at']==values[-1]['time']
    assert original==note()  # immutable source facts


def test_later_errors_do_not_resurrect_resolved_historical_claim():
    values=[event(i,i) for i in range(1,4)]+[event(4,4,False)]
    result=memory.project([note()],values,BASE+timedelta(days=5))[0]
    assert result['memory_status']=='resolved' and result['resolved_by']==['1','2','3']
    group={'evidence':values,'_all_learning_notes':[note()]}
    memory.apply(group,BASE+timedelta(days=5))
    assert group['practice_memory']['4']['memory_status']=='active'


@pytest.mark.parametrize('kind,ttl',list(memory.TTL_DAYS.items()))
def test_time_decay_expires_claim_but_keeps_source(kind,ttl):
    original=note(kind=kind)
    before=memory.project([original],[],BASE+timedelta(days=ttl)-timedelta(seconds=1))[0]
    after=memory.project([original],[],BASE+timedelta(days=ttl))[0]
    assert before['memory_status'] in {'active','pending'}
    assert after['memory_status']=='expired' and after['evidence_quote']==original['evidence_quote']
    assert after['last_confirmed_at']==original['created_at']
    middle=memory.project([original],[],BASE+timedelta(days=ttl/2))[0]
    assert middle['freshness']=='aging' and middle['memory_confidence']=='low'


def test_recent_errors_have_more_weight_than_old_successes():
    values = [event(1, -60), event(2, -60), event(3, 0, False), event(4, 0, False)]
    result = memory.practice_summary(values, BASE)
    assert result['weighted_error_rate'] == .8  # old success weighs 1/4 each
    assert result['effective_count'] == 2.5 and result['recent_independent_count'] == 2
    assert memory.practice_summary(values, BASE.replace(hour=15)) == result


def test_time_weighting_still_rejects_duplicate_and_future_evidence():
    values = [event(1, -30, identity='same'), event(2, 0, identity='same'), event(3, 1)]
    result = memory.practice_summary(values, BASE)
    assert result['sample_count'] == 1 and result['effective_count'] == .5


def test_eight_attempts_do_not_override_a_history_of_repeated_errors(setup):
    client, settings = setup
    for _ in range(5):
        answer(client, settings, wrong=True)
    for _ in range(3):
        answer(client, settings)
    value = get_type(client)
    assert value['independent_count'] == 8
    assert value['evidence_summary']['weighted_error_rate'] == .625
    assert value['status'] == '需要补强'


def test_only_duplicate_claims_supersede_not_different_errors_or_interest():
    notes=[note('first'),note('duplicate',days=1),note('different',days=2,quote='|-5|=0'),
           note('interest','question_interest',3,quote='绝对值是什么？')]
    result={n['id']:n for n in memory.project(notes,[],BASE+timedelta(days=4))}
    assert result['first']['memory_status']=='superseded'
    assert result['first']['superseded_by']=='duplicate'
    assert result['duplicate']['memory_status']==result['different']['memory_status']=='active'
    group={'evidence':[],'_all_learning_notes':notes}
    assert memory.apply(group,BASE+timedelta(days=4))['learning_status']=='需要巩固'


def test_unreviewed_and_invalid_time_claims_cannot_become_current_diagnoses():
    old=note('old');old['policy_version']='obsolete-policy'
    invalid=note('invalid');invalid['created_at']='bad'
    future=note('future',days=2)
    result=memory.project([old,invalid,future],[],BASE)
    assert {n['memory_status'] for n in result}=={'legacy_unverified','invalid_time'}


def test_guided_success_is_not_independent_resolution_or_review():
    group={'evidence':[],'_all_learning_notes':[note(),note('ok','guided_success',1,'因为距离是3')]}
    memory.apply(group,BASE+timedelta(days=2))
    assert group['learning_status']=='需要巩固'
    assert group['review']['last_verified_at'] is None and not group['review']['due']


def test_spacing_grows_by_dates_not_same_day_farming_and_error_resets():
    same_day=[event(i) for i in range(20)]
    assert memory.review(same_day,BASE)['interval_days']==1
    spaced=[event(1),event(2,1),event(3,2)]
    assert memory.review(spaced,BASE+timedelta(days=2))['interval_days']==7
    assert memory.review(spaced+[event(4,3,False)],BASE+timedelta(days=3))['interval_days']==1
    assert not memory.review(spaced,BASE+timedelta(days=8))['due']
    assert memory.review(spaced,BASE+timedelta(days=9))['due']
    assert memory.review([event(1,1)],BASE)['last_verified_at'] is None


def test_timezone_dates_and_invalid_evidence():
    a=event(1);a['time']='2030-01-10T23:30:00+08:00'
    b=event(2);b['time']='2030-01-10T16:30:00+00:00'  # next Beijing day
    invalid=event(3);invalid['time']='not-a-time'
    assert memory.review([b,invalid,a],BASE+timedelta(days=1))['interval_days']==3


def recalled_type(tid,name,notes=(),evidence=()):
    group={'id':tid,'name':name,'can_do':name,'evidence':list(evidence),
           '_all_learning_notes':list(notes),'independent_count':len(evidence),'status':'证据不足'}
    memory.apply(group,BASE+timedelta(days=2))
    group['current_status']=memory.current_status(group)
    return group


def test_retrieval_is_relevant_bounded_and_reading_never_refreshes_verification():
    absolute=recalled_type('m7a:absolute','负数的绝对值',[note()], [event(1)])
    others=[recalled_type(str(i),'三角形全等'+str(i),[note(str(i),quote='三角形')]) for i in range(30)]
    source=copy.deepcopy(absolute)
    for delay in (3,20,60):
        value=memory.retrieve([absolute]+others,'绝对值为什么不能为负数？',at=BASE+timedelta(days=delay))
        assert [t['id'] for t in value['items']]==['m7a:absolute']
        assert value['items'][0]['review']['last_verified_at']==event(1)['time']
        if delay>=30:assert value['items'][0]['learning_notes']==[]
    assert absolute==source
    assert len(memory.retrieve(others,'继续',limit=100,at=BASE)['items'])<=16
    assert not memory.retrieve(others,'继续',limit=0,at=BASE)['items']
    assert not memory.retrieve(others,'继续',context_budget=10,at=BASE)['items']


def test_many_interest_notes_do_not_push_real_error_out_of_memory_budget():
    notes=[note()]+[note('interest-'+str(i),'question_interest',1,quote='问题'+str(i)) for i in range(20)]
    item=recalled_type('m7a:absolute','负数的绝对值',notes)
    value=memory.retrieve([item],'绝对值',at=BASE+timedelta(days=2))
    assert any(n['kind']=='difficulty' for n in value['items'][0]['learning_notes'])


@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setattr(memory,'clock',lambda:BASE)
    settings=Settings(database_path=tmp_path/'memory.sqlite3',deepseek_api_key='test-only',_env_file=None)
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/v1/auth/register',json={'username':'memory','password':'test-memory-123','grade':7,'term':1}).status_code==201
        yield client,settings


def add_note(settings,kind='difficulty',days=0):
    value=Observation(type_id='m7a:absolute',type_name='负数的绝对值',kind=kind,
                      evidence_quote='|-3|=-3',note='将距离写成负数。')
    with connect(settings.database_path) as db:
        saved=observations.save(db,[value],None,'|-3|=-3',validation={'method':'independent_ai_review'})[0]
        db.execute('UPDATE learning_observations SET created_at=? WHERE id=?',((BASE+timedelta(days=days)).isoformat(),saved['id']))
    return saved['id']


def answer(client,settings,days=0,wrong=False,hint=False):
    response=client.post('/api/v1/study/next',json={'type_id':'m7a:absolute','allow_challenge':False})
    assert response.status_code==200,response.text
    work=response.json()
    with connect(settings.database_path) as db:
        question=json.loads(db.execute('SELECT data FROM questions WHERE id=?',(work['question']['id'],)).fetchone()[0])
    if hint:assert client.post('/api/v1/attempts/'+work['attempt_id']+'/hint').status_code==200
    response=client.post('/api/v1/attempts/'+work['attempt_id']+'/answer',json={'answer':'9999999' if wrong else question['answer']})
    assert response.status_code==200,response.text
    with connect(settings.database_path) as db:
        db.execute('UPDATE attempts SET submitted_at=? WHERE id=?',((BASE+timedelta(days=days)).isoformat(),work['attempt_id']))
    return work


def get_type(client):
    return next(t for t in client.get('/api/v1/study/home').json()['types'] if t['id']=='m7a:absolute')


def test_lifecycle_end_to_end_preserves_events_and_assisted_work_does_not_resolve(setup,monkeypatch):
    client,settings=setup;oid=add_note(settings,days=-4)
    for _ in range(3):answer(client,settings,days=-3,hint=True)
    assert get_type(client)['learning_status']=='需要巩固'
    for days in (-2,-2,-1):answer(client,settings,days=days)
    value=get_type(client)
    assert value['independent_count']==3 and value['memory_history'][0]['memory_status']=='resolved'
    assert value['learning_status'] is None
    with connect(settings.database_path) as db:
        assert db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==6
        assert db.execute('SELECT dismissed FROM learning_observations WHERE id=?',(oid,)).fetchone()[0]==0
    assert client.post('/api/v1/teacher/observations/'+oid+'/dismiss').status_code==200
    assert get_type(client)['memory_history']==[]


def test_expiry_retrieval_report_invalidation_and_read_only_access(setup,monkeypatch):
    client,settings=setup;oid=add_note(settings)
    calls=[]
    async def fake(settings,messages,schema,vision=False):
        material=json.loads(messages[1]['content'])['learning_material'];calls.append(material)
        if schema is Reply:return Reply(reply='绝对值是到原点的距离。')
        return schema(summary='这次记录了一个具体计算错误。',uncertainty='仍需独立检查。')
    monkeypatch.setattr(bank_ai,'request_json',fake)
    first=client.post('/api/v1/reports/analyze',json={'period':'all'}).json()
    assert first['analysis_source']=='ai'
    fingerprint=first['fingerprint']
    assert client.post('/api/v1/teacher/chat',json={'message':'绝对值怎么求？'}).status_code==200
    recalled=calls[-1]['memory_context']
    assert recalled['items'][0]['learning_notes'][0]['id']==oid
    with connect(settings.database_path) as db:
        before=tuple(db.execute('SELECT * FROM learning_observations WHERE id=?',(oid,)).fetchone())
    monkeypatch.setattr(memory,'clock',lambda:BASE+timedelta(days=31))
    for _ in range(3):
        assert client.post('/api/v1/teacher/chat',json={'message':'绝对值怎么求？'}).status_code==200
        assert not any(t['learning_notes'] for t in calls[-1]['memory_context']['items'])
    report=client.get('/api/v1/reports?period=all').json()
    assert report['analysis_source']=='rules' and report['fingerprint']!=fingerprint
    old=next(e for e in report['evidence'] if e['id']=='note:'+oid)
    assert old['memory_status']=='expired'
    from app.reports import eligible_focus
    assert not eligible_focus(old)
    assert get_type(client)['learning_status']=='待重新确认'
    with connect(settings.database_path) as db:
        assert tuple(db.execute('SELECT * FROM learning_observations WHERE id=?',(oid,)).fetchone())==before


def test_due_review_preserves_historical_success_and_drives_practice_report_pdf(setup,monkeypatch):
    client,settings=setup
    for days in (-6,-6,-6,-5,-5):answer(client,settings,days=days)
    value=get_type(client)
    assert value['status']=='表现稳定' and value['current_status']=='建议复测'
    assert value['review']['last_verified_at']==(BASE-timedelta(days=5)).isoformat()
    report=client.get('/api/v1/reports?period=all').json()
    assert report['review_queue'][0]['type_id']=='m7a:absolute'
    assert report['summary']['stable_types']==0 and report['summary']['review_due_types']==1
    assert not report['rule_analysis']['strengths']
    for chapter in report['chapters']:
        assert chapter['total']==sum(chapter[k] for k in ('stable','weak','learning','unknown'))
    next_work=client.post('/api/v1/study/next',json={'allow_challenge':False}).json()
    assert next_work['type_name']=='负数的绝对值'
    assert next_work['question']['difficulty']<3
    pdf=client.get('/api/v1/reports/pdf?period=all')
    text=''.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert '值得再检查一下' in text and '建议复测' in text
    answer(client,settings)
    assert get_type(client)['current_status']=='表现稳定'
    assert client.get('/api/v1/reports?period=all').json()['review_queue']==[]


def test_memory_is_scoped_to_student_and_stage_before_retrieval(setup,monkeypatch):
    client,settings=setup;oid=add_note(settings)
    captured=[]
    async def fake(settings,messages,schema,vision=False):
        captured.append(json.loads(messages[1]['content'])['learning_material'])
        return Reply(reply='先看当前问题。')
    monkeypatch.setattr(bank_ai,'request_json',fake)
    alice=client.cookies.get('teacher_session')
    assert client.post('/api/v1/auth/stage',json={'grade':8,'term':1}).status_code==200
    assert client.post('/api/v1/teacher/chat',json={'message':'绝对值','type_id':'m7a:absolute'}).status_code==200
    assert captured[-1]['memory_context']['items']==[]
    assert client.post('/api/v1/auth/register',json={'username':'other','password':'test-memory-123','grade':7,'term':1}).status_code==201
    assert client.post('/api/v1/teacher/chat',json={'message':'绝对值','type_id':'m7a:absolute'}).status_code==200
    assert not any(n['id']==oid for t in captured[-1]['memory_context']['items'] for n in t['learning_notes'])
    assert client.post('/api/v1/teacher/observations/'+oid+'/dismiss').status_code==404
    client.cookies.set('teacher_session',alice)
    assert client.post('/api/v1/auth/stage',json={'grade':7,'term':1}).status_code==200
    assert get_type(client)['observation_count']==1


def test_report_cache_expires_from_time_alone_without_new_activity(setup,monkeypatch):
    client,settings=setup;add_note(settings)
    calls=[]
    async def fake(settings,messages,schema,vision=False):
        calls.append(messages)
        return schema(summary='观察到一次计算错误，仍需复测。',uncertainty='单次线索不代表掌握程度。')
    monkeypatch.setattr(bank_ai,'request_json',fake)
    first=client.post('/api/v1/reports/analyze',json={'period':'all'}).json()
    assert first['analysis_source']=='ai'
    assert client.get('/api/v1/reports?period=all').json()['fingerprint']==first['fingerprint']
    monkeypatch.setattr(memory,'clock',lambda:BASE+timedelta(days=31))
    later=client.get('/api/v1/reports?period=all').json()
    assert later['analysis_source']=='rules' and later['fingerprint']!=first['fingerprint']
    assert len(calls)==1 and later['summary']['observations']==1


def test_resolved_and_expired_notes_cannot_justify_current_report_focus(setup,monkeypatch):
    client,settings=setup;oid=add_note(settings,days=-4)
    for days in (-3,-2,-1):answer(client,settings,days=days)
    async def fake(settings,messages,schema,vision=False):
        return schema(summary='有困难',focus=[{'type_id':'m7a:absolute','finding':'仍然不会绝对值','evidence_ids':['note:'+oid]}],uncertainty='仍需检查。')
    monkeypatch.setattr(bank_ai,'request_json',fake)
    result=client.post('/api/v1/reports/analyze',json={'period':'all'})
    assert result.status_code==502
    report=client.get('/api/v1/reports?period=all').json()
    assert report['analysis_source']=='rules'
    assert next(e for e in report['evidence'] if e['id']=='note:'+oid)['memory_status']=='resolved'


def test_old_thread_displays_current_lifecycle_without_rewriting_messages(setup,monkeypatch):
    client,settings=setup
    from app.observation_guard import Review
    async def fake(settings,messages,schema,vision=False):
        if schema is Review:
            value=json.loads(messages[1]['content'])['learning_material']
            return Review(decisions=[{'candidate_index':c['candidate_index'],'verdict':'supported','evidence_quote':c['evidence_quote'],'reason':'距离非负。'} for c in value['candidates']])
        return Reply(reply='距离非负。',observations=[Observation(type_id='m7a:absolute',type_name='负数的绝对值',kind='difficulty',evidence_quote='|-3|=-3',note='距离算成负数。')])
    monkeypatch.setattr(bank_ai,'request_json',fake)
    response=client.post('/api/v1/teacher/chat',json={'message':'我算|-3|=-3'}).json()
    with connect(settings.database_path) as db:
        db.execute('UPDATE learning_observations SET created_at=?',((BASE-timedelta(days=4)).isoformat(),))
        from app.study import state
        recalled=memory.retrieve(state(db)['types'],'绝对值')
        assert recalled['items'][0]['learning_notes'][0]['message_id']==response['message_id']
        assert recalled['items'][0]['learning_notes'][0]['source']=='conversation'
        before=db.execute('SELECT response FROM teacher_messages WHERE id=?',(response['message_id'],)).fetchone()[0]
    for days in (-3,-2,-1):answer(client,settings,days=days)
    thread=client.get('/api/v1/teacher/threads/'+response['thread_id']).json()
    assert thread['items'][0]['response']['observations'][0]['memory_status']=='resolved'
    with connect(settings.database_path) as db:
        assert db.execute('SELECT response FROM teacher_messages WHERE id=?',(response['message_id'],)).fetchone()[0]==before


def test_new_reviewed_error_flags_old_stability_without_rewriting_practice_score(setup,monkeypatch):
    client,settings=setup
    for _ in range(5):answer(client,settings)
    assert get_type(client)['current_status']=='表现稳定'
    add_note(settings)
    value=get_type(client)
    assert value['status']=='表现稳定' and value['current_status']=='待独立验证'
    assert client.get('/api/v1/reports?period=all').json()['summary']['stable_types']==0
    monkeypatch.setattr(memory,'clock',lambda:BASE+timedelta(days=2))
    for days in (1,1,2):answer(client,settings,days=days)
    assert get_type(client)['current_status']=='表现稳定'
