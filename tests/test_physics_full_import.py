import copy
import hashlib
import json

import pytest

from app import bank, physics_full_import
from app.db import connect, dumps, initialize, now
from app.math_annotations import apply_batch
from app.physics_full_import import apply_full_batch
from app.physics_full_review import Finding, PeerFinding, record_hash
from app.physics_review import snapshot_hash
from app.question_annotation import source_fingerprint
from tests.test_physics_bank import label, physics


def rows(path, records):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records))


def read_rows(path):
    return list(map(json.loads, path.read_text().splitlines()))


@pytest.fixture
def prepared(tmp_path):
    path = tmp_path / 'db.sqlite3'
    initialize(path)
    one, two, math = physics('p1'), physics('p2'), physics('math')
    two.update(stem='电阻2Ω，电压4V，请列式求电流。', answer='3A')
    math['subject'] = 'math'
    with connect(path) as db:
        bank.import_records(db, 'physics-test', [one, two], {})
    with connect(path) as db:
        bank.import_records(db, 'math-test', [math], {})
    with connect(path) as db:
        apply_batch(db, [label(one, True), label(two, True)], subject='physics', dry_run=False)
    with connect(path) as db:
        current = [json.loads(r[0]) for r in db.execute("SELECT data FROM bank_questions WHERE subject='physics' AND status!='superseded' ORDER BY id")]
    directory = tmp_path / 'review'
    directory.mkdir()
    (directory / 'manifest.json').write_text(json.dumps(dict(total=2, shards=[2], model='gpt-6-luna', base_revision='a' * 40)))
    inputs, primary, peers = [], [], []
    for index, q in enumerate(current):
        qid = q['annotation_source_question_id']
        pin = source_fingerprint({**q, 'id': qid})
        inputs.append(dict(question_id=qid, source_sha256=pin, current_snapshot_id=q['id'], current_sha256=snapshot_hash(q),
                           question={k: q.get(k) for k in ('stem', 'kind', 'answer', 'steps', 'difficulty', 'grade', 'term')}))
        primary.append(dict(question_id=qid, source_sha256=pin, decision='pass' if index == 0 else 'exclude',
                            reason='独立计算2A，来源相符' if index == 0 else '来源3A与独立计算2A冲突',
                            independent_solution=['I=U/R=4/2=2A'], source_comparison='独立计算与来源逐问比较',
                            answer='2A', answer_matches_source=index == 0, response_format='calculation',
                            knowledge=dict(primary=['欧姆定律'], supporting=['电流与电阻关系']),
                            fine_types=['已知电压电阻用欧姆定律求电流'],
                            parts=[dict(prompt='计算电流', answer='2A', solution=['I=U/R=4/2=2A'],
                                        knowledge=['欧姆定律'], fine_types=['欧姆定律代入求电流'], evidence=['4V/2Ω=2A'])]))
        peers.append(dict(question_id=qid, source_sha256=pin, decision='accept',
                          independent_solution=['4V除以2Ω得到2A'], reason='独立计算后同意初审决定'))
    rows(directory / 'input-0.jsonl', inputs)
    rows(directory / 'primary-0.jsonl', primary)
    rows(directory / 'peer-0.jsonl', peers)
    return path, directory, [one, two]


def test_complete_review_is_candidate_immutable_and_source_reimport_idempotent(prepared):
    path, directory, original = prepared
    with connect(path) as db:
        before_math = [tuple(r) for r in db.execute("SELECT * FROM bank_questions WHERE subject='math'")]
        assert apply_full_batch(db, directory)['passed'] == 1
        assert db.execute("SELECT count(*) FROM audit_events WHERE kind='physics_full_review_batch'").fetchone()[0] == 0
    with connect(path) as db:
        result = apply_full_batch(db, directory, dry_run=False)
        assert result['passed'] == result['excluded'] == 1
        assert result['unresolved'] == result['published'] == 0
    with connect(path) as db:
        assert apply_full_batch(db, directory, dry_run=False)['already_applied']
        qs = {json.loads(r[0])['annotation_source_question_id']: json.loads(r[0])
              for r in db.execute("SELECT data FROM bank_questions WHERE subject='physics' AND status!='superseded'")}
        passed, excluded = qs['p1'], qs['p2']
        assert passed['can_practice'] and not excluded['can_practice']
        assert passed['quality']['model_review']['status'] == 'passed'
        assert passed['annotation']['review']['status'] == 'candidate'
        assert passed['annotation']['review']['method'] == 'item_read'
        assert passed['annotation']['review']['answer_status'] == 'source_only'
        assert not passed['provenance'].get('teacher_reviewed')
        assert passed['annotation']['curriculum']['grade'] is None
        assert passed['annotation']['grading']['full_score'] is None
        assert all(p['points'] is None for p in passed['annotation']['parts'])
        assert all(t['label'] != 'fine_type_pending' for t in passed['tags'])
        assert any(t['label'] == '电流与电阻关系' and t['origin'] == 'luna' for t in passed['tags'])
        shown = bank.public(passed, reveal=True)
        assert shown['steps_source'] == 'model_reviewed_annotation'
        assert shown['steps'] == ['I=U/R=4/2=2A']
        assert passed['steps'] == original[0]['steps']  # preserve source explanation
        assert 'steps' not in bank.public(passed)
        stale = copy.deepcopy(passed)
        stale['annotation']['parts'][0]['solution_steps'] = ['stale edit']
        assert 'steps_source' not in bank.public(stale, reveal=True)
        assert excluded['quality']['model_review']['status'] == 'excluded'
        assert excluded['status'] == 'quarantine' and excluded['answer'] == '3A'
        assert excluded['evidence_invalidated']
        assert all(json.loads(r[0]).get('evidence_invalidated') for r in db.execute(
            "SELECT data FROM bank_questions WHERE id='p2' OR id LIKE 'p2:%'"))
        assert [tuple(r) for r in db.execute("SELECT * FROM bank_questions WHERE subject='math'")] == before_math
        assert db.execute('SELECT count(*) FROM bank_editor_events').fetchone()[0] == 0
    raw_before = copy.deepcopy(original)
    with connect(path) as db:
        assert bank.import_records(db, 'physics-test', original, {})['duplicates'] == 2
        assert original == raw_before
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []


@pytest.mark.parametrize('change', ['source', 'snapshot', 'teacher', 'incomplete'])
def test_incomplete_or_stale_snapshot_has_no_writes(prepared, change):
    path, directory, _ = prepared
    inputs = read_rows(directory / 'input-0.jsonl')
    if change == 'source':
        inputs[-1]['source_sha256'] = '0' * 64
        rows(directory / 'input-0.jsonl', inputs)
    if change == 'snapshot':
        inputs[-1]['current_sha256'] = '0' * 64
        rows(directory / 'input-0.jsonl', inputs)
    if change == 'teacher':
        with connect(path) as db:
            q = json.loads(db.execute('SELECT data FROM bank_questions WHERE id=?', (inputs[-1]['current_snapshot_id'],)).fetchone()[0])
            q['provenance']['teacher_reviewed'] = True
            db.execute('UPDATE bank_questions SET data=? WHERE id=?', (dumps(q), q['id']))
    if change == 'incomplete':
        rows(directory / 'peer-0.jsonl', read_rows(directory / 'peer-0.jsonl')[:1])
    with connect(path) as db:
        before = [tuple(r) for r in db.execute('SELECT * FROM bank_questions')]
        with pytest.raises(ValueError):
            apply_full_batch(db, directory, dry_run=False)
        assert [tuple(r) for r in db.execute('SELECT * FROM bank_questions')] == before


def test_peer_disagreement_is_quarantined_not_auto_promoted(prepared):
    path, directory, _ = prepared
    peers = read_rows(directory / 'peer-0.jsonl')
    peers[0].update(decision='unresolved', reason='题面有歧义，不能确认唯一答案')
    rows(directory / 'peer-0.jsonl', peers)
    with connect(path) as db:
        result = apply_full_batch(db, directory, dry_run=False)
        assert result['passed'] == 0 and result['unresolved'] == 1
        value = json.loads(db.execute("SELECT data FROM bank_questions WHERE status!='superseded' AND json_extract(data,'$.annotation_source_question_id')='p1'").fetchone()[0])
        assert value['quality']['model_review']['status'] == 'unresolved'
        assert value['status'] == 'quarantine' and not value['can_practice']


def test_existing_draft_is_rebound_without_changing_its_form_or_human_history(prepared):
    path, directory, _ = prepared
    source = read_rows(directory / 'input-0.jsonl')[0]
    form = {'stem': '保留维护者的手工修订', 'annotation': {'custom': 'must remain'}}
    with connect(path) as db:
        q = json.loads(db.execute('SELECT data FROM bank_questions WHERE id=?', (source['current_snapshot_id'],)).fetchone()[0])
        data = dict(form=form, source=q, ai_review={'batch_id': 'old', 'human_approved': False})
        db.execute('INSERT INTO bank_editor_items VALUES(?,?,?,?,?,?,?,NULL,?)',
                   ('draft', 'bank', q['id'], hashlib.sha256(dumps(q).encode()).hexdigest(), 3, dumps(data), 'draft', now()))
    with connect(path) as db:
        assert apply_full_batch(db, directory, dry_run=False)['draft_rebases'] == 1
    with connect(path) as db:
        row = db.execute("SELECT * FROM bank_editor_items WHERE id='draft'").fetchone()
        value = json.loads(row['data'])
        assert value['form'] == form and value['ai_review'] == data['ai_review']
        assert row['revision'] == 4 and row['source_id'] != q['id']
        assert row['source_hash'] == hashlib.sha256(dumps(value['source']).encode()).hexdigest()
        assert value['source']['id'] == row['source_id']
        assert value['source_rebases'][0]['old_snapshot_id'] == q['id']
        assert db.execute('SELECT count(*) FROM bank_editor_events').fetchone()[0] == 0


def test_failure_after_snapshot_creation_rolls_back_all_versions(prepared, monkeypatch):
    path, directory, _ = prepared
    monkeypatch.setattr(physics_full_import, 'BATCH_SIZE', 1)
    def fail(*args, **kwargs):
        raise RuntimeError('模拟最终审计失败')
    monkeypatch.setattr(physics_full_import, 'audit', fail)
    with connect(path) as db:
        before = [tuple(r) for r in db.execute('SELECT * FROM bank_questions')]
        with pytest.raises(RuntimeError):
            apply_full_batch(db, directory, dry_run=False)
        assert [tuple(r) for r in db.execute('SELECT * FROM bank_questions')] == before


def test_changed_payload_cannot_reuse_applied_batch(prepared):
    path, directory, _ = prepared
    with connect(path) as db:
        apply_full_batch(db, directory, dry_run=False)
    primary = read_rows(directory / 'primary-0.jsonl')
    primary[0]['reason'] += '修改后的批次'
    rows(directory / 'primary-0.jsonl', primary)
    with connect(path) as db, pytest.raises(ValueError, match='不同内容'):
        apply_full_batch(db, directory, dry_run=False)


def test_changed_source_does_not_inherit_old_model_certainty(prepared):
    path, directory, original = prepared
    with connect(path) as db:
        apply_full_batch(db, directory, dry_run=False)
    changed = copy.deepcopy(original[0])
    changed.update(answer='4A', steps=['新来源已改变'])
    with connect(path) as db:
        assert bank.import_records(db, 'physics-test', [changed], {})['inserted'] == 1
        q = json.loads(db.execute("SELECT data FROM bank_questions WHERE status!='superseded' AND (id='p1' OR id LIKE 'p1:%')").fetchone()[0])
        assert 'model_review' not in q['quality']
        assert q.get('annotation') is None


def test_later_annotation_edit_does_not_inherit_prior_dual_review(prepared):
    path, directory, original = prepared
    with connect(path) as db:
        apply_full_batch(db, directory, dry_run=False)
    entry = label(original[0])
    entry.annotation.fine_types = ['电阻电压代入计算电流的不同标注']
    with connect(path) as db:
        apply_batch(db, [entry], subject='physics', dry_run=False)
    with connect(path) as db:
        q = json.loads(db.execute("SELECT data FROM bank_questions WHERE status!='superseded' AND json_extract(data,'$.annotation_source_question_id')='p1'").fetchone()[0])
        assert 'model_review' not in q['quality']
        assert 'fine_type_pending' not in q['quality'].get('flags', [])
        assert bank.import_records(db, 'physics-test', [original[0]], {})['duplicates'] == 1


def adjudicate_first(directory):
    first = read_rows(directory / 'primary-0.jsonl')[0]
    peer = read_rows(directory / 'peer-0.jsonl')[0]
    return dict(question_id=first['question_id'], source_sha256=first['source_sha256'],
                primary_record_sha256=record_hash(Finding.model_validate(first).model_dump()),
                peer_record_sha256=record_hash(PeerFinding.model_validate(peer).model_dump()),
                reviewer='codex-primary', decision='pass', reason='重新独立核算4V/2Ω=2A，与来源相符',
                independent_solution=['I=U/R=4/2=2A'], finding=first)


def test_adjudication_is_pinned_and_does_not_forge_human_approval(prepared):
    path, directory, _ = prepared
    adjudication = adjudicate_first(directory)
    rows(directory / 'adjudications.jsonl', [adjudication])
    with connect(path) as db:
        assert apply_full_batch(db, directory, dry_run=False)['adjudicated'] == 1
    with connect(path) as db:
        q = json.loads(db.execute("SELECT data FROM bank_questions WHERE status!='superseded' AND json_extract(data,'$.annotation_source_question_id')='p1'").fetchone()[0])
        assert q['quality']['model_review']['adjudication']['reviewer'] == 'codex-primary'
        assert q['quality']['model_review']['human_reviewed'] is False
        assert q['annotation']['review']['status'] == 'candidate'


@pytest.mark.parametrize('fault', ['primary', 'peer', 'source', 'finding'])
def test_stale_or_cross_question_adjudication_cannot_write(prepared, fault):
    path, directory, _ = prepared
    adjudication = adjudicate_first(directory)
    if fault in {'primary', 'peer'}:
        adjudication[f'{fault}_record_sha256'] = '0' * 64
    if fault == 'source':
        adjudication['source_sha256'] = '0' * 64
    if fault == 'finding':
        adjudication['finding']['question_id'] = 'p2'
    rows(directory / 'adjudications.jsonl', [adjudication])
    with connect(path) as db, pytest.raises(ValueError):
        apply_full_batch(db, directory, dry_run=False)


@pytest.mark.parametrize('source_answer', ['见解析。', 'A\n见解析'])
def test_placeholder_answer_is_held_even_if_models_both_accept(source_answer):
    from app.physics_full_import import annotation_for
    q = physics()
    q['answer'] = source_answer
    from tests.test_physics_full_review import finding
    value = finding('physics', 'pass')
    value['response_format'] = 'calculation'
    with pytest.raises(ValueError, match='占位文字'):
        annotation_for(Finding.model_validate(value), q, 'test')
