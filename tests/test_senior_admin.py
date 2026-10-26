"""Pure admin form and publication validation for senior scopes."""
import pytest

from app.admin import Draft, validate_publish
from app.course_catalog import BOOK_MAP


def base_form(stage, subject, book_id):
    book = BOOK_MAP[book_id]
    goal = book['units'][0]['goals'][0]['id']
    return Draft(
        stage=stage, subject=subject,
        grade=None if stage == 'senior' else book['grade'],
        term=None if stage == 'senior' else book['term'],
        curriculum_book_id=book_id if stage == 'senior' else None,
        stem='在给定条件下判断结论。', kind='reference', answer='结论成立',
        steps=['依据定义逐步判断。'], knowledge_tags=['定义'],
        type_tags=['根据定义判断结论'], curriculum_goal_ids=[goal],
        difficulty=1, difficulty_basis='步骤少，直接使用本章定义。',
    )


def test_senior_admin_form_uses_explicit_book_and_null_progress_fields():
    form = base_form('senior', 'math', 'math-senior-compulsory-1')
    assert form.grade is None and form.term is None
    assert form.curriculum_book_id == 'math-senior-compulsory-1'
    validate_publish(form, {})


def test_senior_admin_rejects_goal_from_other_book_or_subject():
    form = base_form('senior', 'math', 'math-senior-compulsory-1')
    other_book = BOOK_MAP['math-senior-compulsory-2']
    form.curriculum_goal_ids = [other_book['units'][0]['goals'][0]['id']]
    with pytest.raises(ValueError, match='本册对应'):
        validate_publish(form, {})

    form = base_form('senior', 'math', 'math-senior-compulsory-1')
    form.curriculum_book_id = 'physics-senior-compulsory-1'
    with pytest.raises(ValueError, match='科目和学段匹配'):
        validate_publish(form, {})


def test_junior_defaults_and_existing_grade_term_publication_stay_compatible():
    form = base_form('junior', 'math', 'math-7-1')
    assert Draft(subject='math').stage == 'junior'
    validate_publish(form, {})
