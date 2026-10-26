import json

import pytest

from app.physics_full_review import PeerFinding, inspect_batch


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))


def finding(qid, decision='exclude'):
    value = dict(question_id=qid, source_sha256='a' * 64, decision=decision,
                 reason='独立计算与来源冲突', independent_solution=['I=4/2=2A'],
                 source_comparison='来源写3A，独立计算2A')
    if decision == 'pass':
        value.update(answer='A', answer_matches_source=True, response_format='single_choice',
                     knowledge={'primary': ['欧姆定律']}, fine_types=['串联电路已知电压电阻求电流'],
                     parts=[dict(prompt='电流是多少', answer='A', solution=['I=4/2=2A'],
                                 knowledge=['欧姆定律'], fine_types=['欧姆定律求电流'], evidence=['2A对应A'])])
    return value


def peer(qid, decision='accept', correction=None):
    return dict(question_id=qid, source_sha256='a' * 64, decision=decision,
                independent_solution=['I=4/2=2A'], reason='独立核对来源与初审', correction=correction)


@pytest.fixture
def batch(tmp_path):
    (tmp_path / 'manifest.json').write_text(json.dumps(dict(
        total=2, shards=[2], model='gpt-6-luna', base_revision='test')))
    inputs = [dict(question_id=qid, source_sha256='a' * 64, current_sha256='b' * 64,
                   current_snapshot_id=qid, question={'kind': 'reference'}) for qid in ['q1', 'q2']]
    write_rows(tmp_path / 'input-0.jsonl', inputs)
    return tmp_path


def test_partial_checkpoint_records_exact_remaining_without_touching_evidence(batch):
    write_rows(batch / 'primary-0.jsonl', [finding('q1')])
    write_rows(batch / 'peer-0.jsonl', [peer('q1')])
    before = {p.name: p.read_bytes() for p in batch.iterdir()}
    result = inspect_batch(batch)
    assert result['primary_done'] == result['peer_done'] == 1
    assert result['agreed_decisions'] == {'exclude': 1}  # accept is not a passing answer
    assert result['shards'][0]['primary_remaining'] == ['q2']
    assert result['shards'][0]['peer_remaining'] == ['q2']
    assert not result['all_reviews_complete'] and not result['writes_bank']
    assert result['bank_application_status'] == 'not_checked'
    assert before == {p.name: p.read_bytes() for p in batch.iterdir()}


def test_missing_output_files_are_valid_partial_work(batch):
    result = inspect_batch(batch)
    assert result['primary_done'] == result['peer_done'] == 0
    assert result['shards'][0]['primary_remaining'] == ['q1', 'q2']


@pytest.mark.parametrize('fault', ['duplicate', 'unknown', 'hash', 'partial_json', 'orphan', 'manifest'])
def test_invalid_or_stale_work_is_not_counted_as_completed(batch, fault):
    items = [finding('q1')]
    if fault == 'duplicate':
        items.append(finding('q1'))
    if fault == 'unknown':
        items[0]['question_id'] = 'other'
    if fault == 'hash':
        items[0]['source_sha256'] = 'c' * 64
    if fault == 'orphan':
        write_rows(batch / 'peer-0.jsonl', [peer('q2')])
    if fault == 'manifest':
        value = json.loads((batch / 'manifest.json').read_text())
        value['total'] = 99
        (batch / 'manifest.json').write_text(json.dumps(value))
    write_rows(batch / 'primary-0.jsonl', items)
    if fault == 'partial_json':
        with (batch / 'primary-0.jsonl').open('a') as out:
            out.write('{"question_id":')
    with pytest.raises(ValueError):
        inspect_batch(batch)


def test_full_coverage_does_not_certify_unresolved_disagreements_or_human_review(batch):
    write_rows(batch / 'primary-0.jsonl', [finding('q1'), finding('q2')])
    write_rows(batch / 'peer-0.jsonl', [peer('q1'), peer('q2', 'revise', finding('q2', 'pass'))])
    result = inspect_batch(batch)
    assert result['all_reviews_complete']
    assert result['agreed_decisions'] == {'exclude': 1}
    assert result['adjudication_required'] == ['q2']
    assert not result['writes_bank'] and not result['human_reviewed']


def test_choice_conversion_is_held_for_source_repair(batch):
    write_rows(batch / 'primary-0.jsonl', [finding('q1', 'pass')])
    result = inspect_batch(batch)
    assert result['integration_holds'][0]['question_id'] == 'q1'


@pytest.mark.parametrize('fault', ['missing', 'wrong_id', 'wrong_hash', 'unexpected'])
def test_peer_corrections_must_bind_to_same_source(fault):
    value = peer('q1', 'revise', finding('q1'))
    if fault == 'missing':
        value['correction'] = None
    if fault == 'wrong_id':
        value['correction']['question_id'] = 'q2'
    if fault == 'wrong_hash':
        value['correction']['source_sha256'] = 'b' * 64
    if fault == 'unexpected':
        value['decision'] = 'accept'
    with pytest.raises(ValueError):
        PeerFinding.model_validate(value)
