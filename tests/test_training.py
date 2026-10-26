"""Exercise real endpoints and old submit paths; mock only the planning model."""
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import bank_ai
from app.config import Settings
from app.db import connect
from app.main import create_app
from app.training import Proposal
from test_student import register, answer, type_state


TID = 'm7a:subtract-negative'
BASE = '/api/v1/study/training-plans'


@pytest.fixture
def setup(tmp_path):
    settings = Settings(database_path=tmp_path/'training.sqlite3', deepseek_api_key='test-only', _env_file=None)
    with TestClient(create_app(settings)) as client:
        register(client)
        yield client, settings


def plan(client, tid=TID):
    response = client.post(BASE, json={'type_id': tid})
    assert response.status_code == 200, response.text
    return response.json()


def next_work(client, pid):
    response = client.post(f'{BASE}/{pid}/next', json={})
    assert response.status_code == 200, response.text
    return response.json()


def submit(client, settings, work):
    table = 'questions' if work['source'] == 'verified' else 'bank_questions'
    with connect(settings.database_path) as db:
        q = json.loads(db.execute(f'SELECT data FROM {table} WHERE id=?', (work['question']['id'],)).fetchone()[0])
    prefix = '/api/v1' if work['source'] == 'verified' else '/api/v1/bank'
    # Existing answer API accepts no client-supplied phase or evidence weight.
    response = client.post(f"{prefix}/attempts/{work['attempt_id']}/answer", json={'answer': q['answer']})
    assert response.status_code == 200, response.text
    assert client.post(f"{prefix}/attempts/{work['attempt_id']}/answer", json={'answer': q['answer']}).json() == response.json()
    return response.json()


def test_full_training_uses_ai_plan_but_only_independent_retests_change_state(setup, monkeypatch):
    client, settings = setup
    for _ in range(5):
        answer(client, settings, wrong=True)
    calls = []
    async def propose(_settings, messages, schema, **kwargs):
        assert schema is Proposal
        assert 'candidates' in messages[1]['content']
        calls.append(messages)
        return Proposal(type_id=TID, difficulty=1, reason='近期独立题连续出错，先检查减去负数的符号。')
    monkeypatch.setattr(bank_ai, 'request_json', propose)
    before = type_state(client)['independent_count']
    with connect(settings.database_path) as db:
        mastery_before = [tuple(r) for r in db.execute('SELECT * FROM mastery ORDER BY student_id,knowledge_id')]
    p = plan(client)
    assert p['training_count'] == 3 and p['retest_count'] == 2 and p['book_id'] == 'math-7-1'
    assert len(calls) == 1
    assert plan(client)['id'] == p['id'] and len(calls) == 1
    ids = set()
    for pos in range(5):
        value = next_work(client, p['id'])
        w = value['work']
        assert w['position'] == pos + 1 and 'answer' not in w['question']
        assert w['question']['difficulty'] == 1
        assert w['question']['id'] not in ids
        ids.add(w['question']['id'])
        assert next_work(client, p['id'])['work'] == w
        result = submit(client, settings, w)
        assert result['training_phase'] == ('training' if pos < 3 else 'retest')
        assert result['evidence_weight'] == (0 if pos < 3 else 1)
        assert type_state(client)['independent_count'] == before + max(0, pos - 2)
        if pos < 3:
            with connect(settings.database_path) as db:
                assert [tuple(r) for r in db.execute('SELECT * FROM mastery ORDER BY student_id,knowledge_id')] == mastery_before
    final = next_work(client, p['id'])
    assert final['work'] is None and final['plan']['status'] == 'completed'
    assert final['plan']['independent_retests'] == 2
    assert type_state(client)['status'] != '表现稳定'  # Two right answers cannot erase five wrong ones.


def test_insufficient_evidence_is_diagnostic_and_resumable_across_restart(setup, monkeypatch):
    client, settings = setup
    async def forbidden(*args, **kwargs):
        pytest.fail('No weakness to ask a model to train')
    monkeypatch.setattr(bank_ai, 'request_json', forbidden)
    p = plan(client)
    assert p['mode'] == 'diagnostic' and p['training_count'] == 0
    w = next_work(client, p['id'])['work']
    with TestClient(create_app(settings)) as other:
        assert other.post('/api/v1/auth/login', json={'username':'alice', 'password':'test-pass-123'}).status_code == 200
        assert other.get(BASE).json()['plan']['id'] == p['id']
        assert next_work(other, p['id'])['work']['attempt_id'] == w['attempt_id']
        assert submit(other, settings, w)['evidence_weight'] == 1


def test_hint_retest_zero_weight_scope_and_cancel(setup):
    client, settings = setup
    p = plan(client)
    w = next_work(client, p['id'])['work']
    assert client.post(f"/api/v1/attempts/{w['attempt_id']}/hint").status_code == 200
    result = submit(client, settings, w)
    assert result['evidence_weight'] == 0 and not result['independent_eligible']
    assert type_state(client)['independent_count'] == 0
    assert client.post('/api/v1/auth/stage', json={'grade':8,'term':1}).status_code == 200
    assert client.get(f"{BASE}/{p['id']}").status_code == 404
    assert client.post(f"{BASE}/{p['id']}/next", json={}).status_code == 404
    assert client.post('/api/v1/auth/stage', json={'grade':7,'term':1}).status_code == 200
    w = next_work(client, p['id'])['work']
    assert client.post(f"{BASE}/{p['id']}/cancel", json={}).json()['status'] == 'cancelled'
    assert client.post(f"/api/v1/attempts/{w['attempt_id']}/answer", json={'answer':'1'}).status_code == 409
    assert type_state(client)['independent_count'] == 0
    assert client.post('/api/v1/auth/logout', json={}).status_code == 200
    register(client, 'bob')
    assert client.get(f"{BASE}/{p['id']}").status_code == 404


def test_out_of_scope_ai_plan_and_client_override_rejected(setup, monkeypatch):
    client, settings = setup
    for _ in range(5):
        answer(client, settings, wrong=True)
    async def invalid(*args, **kwargs):
        return Proposal(type_id='math-9-1:fake', difficulty=2, reason='直接练高中内容')
    monkeypatch.setattr(bank_ai, 'request_json', invalid)
    assert client.post(BASE, json={'type_id':TID}).status_code == 409
    assert client.get(BASE).json()['plan'] is None
    assert client.post(BASE, json={'type_id':TID,'book_id':'math-9-1','evidence_weight':1}).status_code == 422
    assert client.post(BASE, json={'type_id':'math-9-1:fake'}).status_code == 409


def test_provider_failure_uses_labelled_rules_plan(setup, monkeypatch):
    client, settings = setup
    for _ in range(5):
        answer(client, settings, wrong=True)
    async def unavailable(*args, **kwargs):
        raise HTTPException(502, 'unavailable')
    monkeypatch.setattr(bank_ai, 'request_json', unavailable)
    p = plan(client)
    assert p['provider'] == 'rules' and p['ai_reason'] is None and p['mode'] == 'training'


def test_changed_question_and_previously_exposed_retest_do_not_score(setup):
    client, settings = setup
    p = plan(client)
    w = next_work(client, p['id'])['work']
    with connect(settings.database_path) as db:
        q = json.loads(db.execute('SELECT data FROM questions WHERE id=?',(w['question']['id'],)).fetchone()[0])
        q['stem'] += ' changed'
        db.execute('UPDATE questions SET data=? WHERE id=?', (json.dumps(q),q['id']))
    assert client.post(f"/api/v1/attempts/{w['attempt_id']}/answer", json={'answer':q['answer']}).status_code == 409
    assert type_state(client)['independent_count'] == 0
    client.post(f"{BASE}/{p['id']}/cancel", json={})
    p = plan(client)
    w = next_work(client, p['id'])['work']
    # Exposure in another practice is not a fresh test, even if it was skipped.
    with connect(settings.database_path) as db:
        db.execute("INSERT INTO attempts(id,student_id,question_id,status,assigned_at) SELECT 'other-exposure',student_id,question_id,'skipped',assigned_at FROM attempts WHERE id=?", (w['attempt_id'],))
    result = submit(client, settings, w)
    assert result['evidence_weight'] == 0 and not result['independent_eligible']
    assert type_state(client)['independent_count'] == 0


def test_reviewed_choice_fallback_training_has_zero_evidence(setup, monkeypatch):
    from collections import defaultdict
    from app import bank, training
    from test_student import source
    client, settings = setup
    for _ in range(5):
        answer(client, settings, tid='m7a:absolute', wrong=True)
    with connect(settings.database_path) as db:
        bank.import_records(db, 'training-reviewed', [source(f'training-choice-{i}', reviewed=True) for i in range(7)], {})
    monkeypatch.setattr(training, 'practice_pool', lambda db: defaultdict(list))
    async def propose(*args, **kwargs):
        return Proposal(type_id='m7a:absolute', difficulty=1, reason='独立题的绝对值符号连续出错。')
    monkeypatch.setattr(bank_ai, 'request_json', propose)
    p = plan(client, 'm7a:absolute')
    for pos in range(5):
        w = next_work(client, p['id'])['work']
        assert w['source'] == 'bank'
        result = submit(client, settings, w)
        assert result['evidence_weight'] == (0 if pos < 3 else 1)
    assert type_state(client, 'm7a:absolute')['independent_count'] == 7


def test_cancel_releases_unseen_reservations(setup, monkeypatch):
    from collections import defaultdict
    from app import training
    client, _ = setup
    p = plan(client)
    assert client.post(f"{BASE}/{p['id']}/cancel", json={}).status_code == 200
    with connect(setup[1].database_path) as db:
        qs = [json.loads(r[0]) for r in db.execute('SELECT q.data FROM questions q JOIN training_items i ON i.question_id=q.id WHERE i.plan_id=?', (p['id'],))]
    monkeypatch.setattr(training, 'practice_pool', lambda db: defaultdict(list, {TID: qs}))
    # Only cancelled unshown questions remain in this test pool.
    p2 = plan(client)
    assert p2['status'] == 'active'


def test_physics_core_bank_uses_existing_choice_grading(setup):
    from app.diagnostic_core import seed
    client, settings = setup
    with connect(settings.database_path) as db:
        seed(db)
    assert client.post('/api/v1/auth/stage', json={'grade':8,'term':1,'subject':'physics'}).status_code == 200
    tid = client.get('/api/v1/study/home').json()['types'][0]['id']
    p = plan(client, tid)
    assert p['book_id'] == 'physics-8-1'
    w = next_work(client, p['id'])['work']
    assert w['source'] == 'bank' and w['question']['answer_mode'] == 'choice'
    assert submit(client, settings, w)['evidence_weight'] == 1
    t = next(t for t in client.get('/api/v1/study/home').json()['types'] if t['id'] == tid)
    assert t['independent_count'] == 1
