import json

import pytest

from app.math_full_review import Finding, PeerFinding, inspect_batch, record_hash


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))


def finding(qid, decision='exclude'):
    value = dict(question_id=qid, source_sha256='a' * 64, decision=decision,
                 reason='独立计算与来源冲突', independent_solution=['(-2)-(-3)=1'],
                 source_comparison='来源写-1，独立计算1')
    if decision == 'pass':
        value.update(answer='A', answer_matches_source=True, response_format='single_choice',
                     knowledge={'primary': ['有理数的减法运算']}, fine_types=['有理数减法转加法计算'],
                     parts=[dict(prompt='(-2)-(-3)的结果', answer='A', solution=['(-2)-(-3)=(-2)+3=1'],
                                 knowledge=['有理数的减法运算'], fine_types=['有理数减法转加法计算'],
                                 evidence=['1与选项A一致'])])
    return value


def peer(qid, decision='accept', correction=None):
    return dict(question_id=qid, source_sha256='a' * 64, decision=decision,
                independent_solution=['(-2)+3=1'], reason='独立核对来源与初审', correction=correction)


@pytest.fixture
def batch(tmp_path):
    (tmp_path / 'manifest.json').write_text(json.dumps(dict(
        total=2, shards=[2], model='opencode/deepseek-v4.1-flash-free', base_revision='test')))
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


def test_luna_model_attribution_is_bound_to_normalized_review_record(batch):
    write_rows(batch/'primary-0.jsonl',[finding('q1')])
    output=peer('q1')
    write_rows(batch/'peer-0.jsonl',[output])
    entry={'round':'peer','question_id':'q1','model':'gpt-6-luna',
        'record_sha256':record_hash(PeerFinding.model_validate(output).model_dump())}
    path=batch/'review-provenance.json'
    path.write_text(json.dumps({'schema_version':1,'records':[entry]}))
    result=inspect_batch(batch)
    assert result['model']=='opencode/deepseek-v4.1-flash-free'
    assert result['reviewer_models']['peer']=={'q1':'gpt-6-luna'}
    assert 'review-provenance.json' in result['file_sha256']
    from app.math_full_import import reviewer_model
    assert reviewer_model(result,'primary','q1')==result['model']
    assert reviewer_model(result,'peer','q1')=='gpt-6-luna'
    output['reason']='内容改变后不能继承原审核者绑定'
    write_rows(batch/'peer-0.jsonl',[output])
    with pytest.raises(ValueError,match='审核意见已变化'):inspect_batch(batch)


def test_peer_attribution_can_pin_the_actual_primary_read_by_reviewer(batch):
    initial=finding('q1')
    write_rows(batch/'primary-0.jsonl',[initial])
    output=peer('q1');write_rows(batch/'peer-0.jsonl',[output])
    entry={'round':'peer','question_id':'q1','model':'gpt-6-luna',
        'record_sha256':record_hash(PeerFinding.model_validate(output).model_dump()),
        'primary_record_sha256':record_hash(Finding.model_validate(initial).model_dump())}
    (batch/'review-provenance.json').write_text(json.dumps({'schema_version':1,'records':[entry]}))
    assert inspect_batch(batch)['peer_done']==1
    initial['reason']='初审修订后不能继承旧版本复核的接受意见'
    write_rows(batch/'primary-0.jsonl',[initial])
    with pytest.raises(ValueError,match='初审意见已变化'):inspect_batch(batch)


@pytest.mark.parametrize('fault',['unknown_record','duplicate','unsupported_model'])
def test_invalid_model_attribution_is_rejected(batch,fault):
    write_rows(batch/'primary-0.jsonl',[finding('q1')])
    output=peer('q1');write_rows(batch/'peer-0.jsonl',[output])
    entry={'round':'peer','question_id':'q1','model':'gpt-6-luna',
        'record_sha256':record_hash(PeerFinding.model_validate(output).model_dump())}
    entries=[entry]
    if fault=='unknown_record':entry['question_id']='unknown'
    if fault=='duplicate':entries.append(dict(entry))
    if fault=='unsupported_model':entry['model']='teacher'
    (batch/'review-provenance.json').write_text(json.dumps({'schema_version':1,'records':entries}))
    with pytest.raises(ValueError):inspect_batch(batch)


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


def test_adjudication_binds_both_rounds_and_stale_evidence_is_rejected(batch):
    write_rows(batch / 'primary-0.jsonl', [finding('q1')])
    write_rows(batch / 'peer-0.jsonl', [peer('q1', 'revise', finding('q1', 'pass'))])
    primary = Finding.model_validate(finding('q1'))
    reviewed = PeerFinding.model_validate(peer('q1', 'revise', finding('q1', 'pass')))
    adjudication = dict(question_id='q1', source_sha256='a' * 64,
                        primary_record_sha256=record_hash(primary.model_dump()),
                        peer_record_sha256=record_hash(reviewed.model_dump()),
                        reviewer='orchestrator', decision='exclude', reason='裁定维持排除',
                        independent_solution=['(-2)-(-3)=1'])
    write_rows(batch / 'adjudications.jsonl', [adjudication])
    assert inspect_batch(batch)['adjudication_done'] == 1
    write_rows(batch / 'primary-0.jsonl', [finding('q1') | {'reason': '修改后的说明'}])
    with pytest.raises(ValueError):
        inspect_batch(batch)


def test_adjudicated_pass_must_carry_complete_finding(batch):
    with pytest.raises(ValueError):
        from app.math_full_review import Adjudication
        Adjudication.model_validate(dict(question_id='q1', source_sha256='a' * 64,
                                         primary_record_sha256='c' * 64, peer_record_sha256='d' * 64,
                                         reviewer='review-agent', decision='pass', reason='裁定通过',
                                         independent_solution=['(-2)+3=1']))


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
