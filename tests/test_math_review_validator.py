import pytest

from app.math_full_review import Finding, PeerFinding
from scripts.validate_math_findings import validate_candidate
from tests.test_math_full_import import math
from tests.test_math_full_review import finding, peer


def test_strict_validator_rejects_source_choice_mismatch():
    item = Finding.model_validate(finding('m1', 'pass'))
    with pytest.raises(ValueError, match='独立答案与来源选项答案不符'):
        validate_candidate(item, {'question': math(answer='B')})


def test_accept_does_not_hide_an_invalid_primary_part_answer():
    raw = finding('m1', 'pass')
    raw['parts'][0]['answer'] = '暂不能判定'
    with pytest.raises(ValueError, match='选择题答案必须'):
        validate_candidate(PeerFinding.model_validate(peer('m1')),
                           {'question': math(), 'primary': raw})


def test_complete_peer_correction_can_repair_the_invalid_part():
    raw = finding('m1', 'pass')
    item = PeerFinding.model_validate(peer('m1', 'revise', raw))
    validate_candidate(item, {'question': math()})


def test_generic_ability_label_cannot_become_a_question_type():
    raw = finding('m1', 'pass')
    raw['fine_types'] = ['运算能力']
    with pytest.raises(ValueError, match='泛标签'):
        validate_candidate(Finding.model_validate(raw), {'question': math()})


def test_exclusion_does_not_need_a_passing_annotation():
    validate_candidate(Finding.model_validate(finding('m1')), {'question': {}})
