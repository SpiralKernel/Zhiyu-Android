import pytest

from app.calibration_catalog import catalog
from app.course_catalog import GOALS
from app.physics_textbooks import DATA, alignment_candidates, requirements, types_for_book


@pytest.mark.parametrize('bid,count', [('physics-8-1',28), ('physics-8-2',24),
                                      ('physics-9-1',25), ('physics-9-2',15)])
def test_all_sections_are_available_to_ai_and_controlled_calibration(bid, count):
    r = requirements(bid)
    assert sum(len(c['sections']) for c in r['chapters']) == count
    ids = {t['id']: t for t in catalog(bid)['tags']}
    for t in types_for_book(bid):
        assert ids[t['id']]['kind'] == 'type'
        assert ids['k:'+t['goal_id']]['kind'] == 'knowledge'
        assert t['goal_id'] in GOALS
        assert GOALS[t['goal_id']]['book_id'] == bid
    assert r['physical_book_id'] == ('physics-9-all' if bid.startswith('physics-9') else bid)


def test_complete_volumes_practices_and_prerequisites():
    chapters = [c for b in DATA['books'] for c in b['chapters']]
    assert [c['number'] for c in chapters] == list(range(1,23))
    sections = [s for c in chapters for s in c['sections']]
    assert len(sections) == 92 and len({s['id'] for s in sections}) == 92
    assert sum('practice' in s['modes'] for s in sections) == 12
    seen = set()
    for s in sections:
        assert set(s['prerequisites']) <= seen
        assert s['pdf_page'] > s['printed_page']
        seen.add(s['id'])


def test_no_future_physics_types_or_answer_based_scope_inference():
    assert not any(t['id'].startswith('ft:phys:c17:') for t in catalog('physics-8-1')['tags'])
    q = dict(subject='physics', stage='junior', stem='根据题中数据回答问题',
             answer='欧姆定律', steps=['电磁感应'], knowledge_tags=[])
    assert alignment_candidates(q) == []
    assert alignment_candidates({**q, 'subject':'math', 'stem':'欧姆定律'}) == []
    hits = alignment_candidates({**q, 'knowledge_tags':['欧姆定律']})
    assert any(h['section_id'] == 'phys:c17:s2' for h in hits)
    assert all(h['status'] == 'lexical_candidate' for h in hits)


def test_matching_does_not_mutate_scope_or_upgrade_candidates():
    q = dict(subject='physics', stage='junior', grade=None, term=None,
             stem='比较电功率和机械功率', knowledge_tags=['电功率','机械功率'])
    hits = alignment_candidates(q)
    assert {h['physical_book_id'] for h in hits} >= {'physics-8-2','physics-9-all'}
    assert q['grade'] is None and q['term'] is None
    assert requirements('math-7-1') is None


@pytest.mark.parametrize('bid', ['physics-8-1','physics-8-2','physics-9-1','physics-9-2'])
def test_question_help_context_contains_selected_volume_only(tmp_path, bid):
    from app import courses
    from app.db import connect, initialize
    path = tmp_path / 'context.sqlite3'
    initialize(path)
    with connect(path) as db:
        context = courses.context(db, 'physics', book_id=bid)
    r = context['textbook_requirements']
    assert r and r['chapters']
    assert all(c['book_id'] == bid for c in r['chapters'])


def test_free_question_ai_receives_textbook_requirements_and_fixed_types(tmp_path, monkeypatch):
    import json
    from fastapi.testclient import TestClient
    from app import bank_ai
    from app.config import Settings
    from app.main import create_app
    captured = []
    async def fake(settings, messages, schema, vision=False):
        captured.append(messages)
        return schema(reply='请先说明电压与电流对应的元件。', check_question='电阻温度是否保持不变？', observations=[])
    monkeypatch.setattr(bank_ai, 'request_json', fake)
    settings = Settings(database_path=tmp_path/'teacher.sqlite3', deepseek_api_key='test-only', _env_file=None)
    with TestClient(create_app(settings)) as client:
        r = client.post('/api/v1/auth/register', json={'username':'phys-student','password':'test-pass-123',
                        'grade':9,'term':1,'subject':'physics','nickname':'p'})
        assert r.status_code == 201, r.text
        r = client.post('/api/v1/courses/preferences', json={'subject':'physics','book_id':'physics-9-1'})
        assert r.status_code == 200, r.text
        r = client.post('/api/v1/teacher/chat', json={'message':'欧姆定律如何理解？'})
        assert r.status_code == 200, r.text
    material = json.loads(captured[0][1]['content'])['learning_material']
    assert material['textbook_requirements']['physical_book_id'] == 'physics-9-all'
    ids = {t['id'] for t in material['type_catalog']}
    assert 'ft:phys:c17:s2:calculation' in ids
    assert 'ft:phys:c20:s6:concept' not in ids
