"""Senior textbook scopes, explicit mapping isolation, and grade validation."""
import hashlib
import json
from pathlib import Path

import pytest

from app.course_catalog import BOOK_MAP, BOOKS, GOALS, UNITS, VERSION
from app.courses import matched_goals
from app.question_annotation import validate_for_question

ROOT = Path(__file__).resolve().parents[1]
SENIOR_BOOK_IDS = {
    "math-senior-compulsory-1", "math-senior-compulsory-2",
    "math-senior-selective-1", "math-senior-selective-2",
    "physics-senior-compulsory-1", "physics-senior-compulsory-2",
    "physics-senior-compulsory-3", "physics-senior-selective-1",
    "physics-senior-selective-2", "physics-senior-selective-3",
}


def senior_fixture():
    data = json.loads((ROOT / "app/data/senior_curriculum.json").read_text())
    return data, [book for book in BOOKS if book["stage"] == "senior"]


def test_senior_textbooks_goals_sources_and_prerequisites_are_complete():
    data, books = senior_fixture()
    assert {book["book_id"] for book in data["books"]} == SENIOR_BOOK_IDS
    assert {book["id"] for book in books} == SENIOR_BOOK_IDS
    assert sum(len(book["units"]) for book in books) == 50
    assert sum(len(unit["goals"]) for book in books for unit in book["units"]) == 100
    # The final modeling chapter is present in the archived BNU PDF TOC.
    final = BOOK_MAP['math-senior-compulsory-1']['units'][-1]
    assert final['id']=='math-senior-compulsory-1:u8'
    assert final['name']=='数学建模活动（一）'
    assert VERSION != "junior-2026.10.15"

    for source in data["books"]:
        archive = ROOT / source["source_archive"]
        assert source["source_sha256"] in {item["sha256"] for item in source["sources"]}
        assert len(source["units"]) == len(BOOK_MAP[source["book_id"]]["units"])
        for unit in source["units"]:
            assert unit["id"] in UNITS
            assert UNITS[unit["id"]]["name"] == unit["name"]
            for goal in unit["goals"]:
                target = GOALS[goal["id"]]
                assert target["book_id"] == source["book_id"]
                assert target["subject"] == source["subject"]
                assert target["stage"] == "senior"
                assert goal["unit_id"] == unit["id"]
                assert set(goal["prerequisites"]) <= set(GOALS) | set(UNITS)
                assert goal["name"] not in {f"理解{unit['name']}的核心概念与表示", f"运用{unit['name']}的方法解决问题"}


def test_optional_local_textbook_archives_match_published_fingerprints():
    data, _ = senior_fixture()
    missing = [source['source_archive'] for source in data['books']
               if not (ROOT / source['source_archive']).is_file()]
    if missing:
        pytest.skip('Optional private textbook PDFs are not distributed with source')
    for source in data['books']:
        archive = ROOT / source['source_archive']
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == source['source_sha256']


def test_senior_explicit_mapping_requires_subject_stage_and_primary_book():
    own_book = "math-senior-compulsory-1"
    own_goal = BOOK_MAP[own_book]["units"][0]["goals"][0]["id"]
    other_math_goal = BOOK_MAP["math-senior-compulsory-2"]["units"][0]["goals"][0]["id"]
    physics_goal = BOOK_MAP["physics-senior-compulsory-1"]["units"][0]["goals"][0]["id"]
    question = {
        "stage": "senior", "subject": "math", "curriculum_book_id": own_book,
        "curriculum_goal_ids": [own_goal, other_math_goal, physics_goal],
    }
    assert [goal_id for goal_id, _ in matched_goals(question)] == [own_goal]
    assert matched_goals({**question, "subject": "physics"}) == []
    assert matched_goals({**question, "stage": "junior"}) == []
    assert matched_goals({**question, "curriculum_book_id": None}) == []


def test_junior_goal_matching_remains_scoped_to_junior_book():
    junior_book = BOOK_MAP["math-7-1"]
    junior_goal = junior_book["units"][0]["goals"][0]["id"]
    senior_goal = BOOK_MAP["math-senior-compulsory-1"]["units"][0]["goals"][0]["id"]
    q = {"stage": "junior", "subject": "math", "grade": 7, "term": 1,
         "curriculum_goal_ids": [junior_goal, senior_goal]}
    assert [goal_id for goal_id, _ in matched_goals(q)] == [junior_goal]
    assert matched_goals({**q, "stage": "senior"}) == []
    alias_q = {"stage": "junior", "subject": "math", "grade": 7, "term": 1,
               "knowledge_tags": ["绝对值"]}
    assert any(goal_id in GOALS for goal_id, _ in matched_goals(alias_q))


def annotation(grade, term, goal_ids=None, book_id=None):
    curriculum = {"grade": grade, "term": term, "goal_ids": goal_ids or []}
    if book_id:
        curriculum["book_id"] = book_id
    return {
        "response_format": "single_choice",
        "difficulty": {"level": 1, "basis": "用题目步骤和概念数量判断"},
        "answer_spec": {"mode": "choice"},
        "curriculum": curriculum,
    }


def question(stage, subject, grade, term, goal_ids=None, book_id=None):
    q = {"stage": stage, "subject": subject, "grade": grade, "term": term,
         "kind": "single_choice"}
    if goal_ids is not None:
        q["curriculum_goal_ids"] = goal_ids
    if book_id:
        q["curriculum_book_id"] = book_id
    return q


def test_structured_annotation_accepts_junior_and_senior_grade_ranges():
    junior = BOOK_MAP["math-7-1"]["units"][0]["goals"][0]["id"]
    senior = BOOK_MAP["physics-senior-selective-3"]["units"][0]["goals"][0]["id"]

    validate_for_question(annotation(7, 1, [junior]), question("junior", "math", 7, 1, [junior]))
    validate_for_question(
        annotation(12, None, [senior], "physics-senior-selective-3"),
        question("senior", "physics", 12, None, [senior], "physics-senior-selective-3"),
    )
    with pytest.raises(ValueError, match="初中题目"):
        validate_for_question(annotation(10, 1), question("junior", "math", 10, 1))
    with pytest.raises(ValueError, match="高中题目"):
        validate_for_question(annotation(9, 1), question("senior", "math", 9, 1))
    with pytest.raises(ValueError, match="高中课程目标需要指定主适用册次"):
        validate_for_question(annotation(10, None, [senior]), question("senior", "physics", 10, None, [senior]))
    with pytest.raises(ValueError, match="主适用册次"):
        validate_for_question(
            annotation(10, None, [senior], "physics-senior-compulsory-1"),
            question("senior", "physics", 10, None, [senior], "physics-senior-compulsory-1"),
        )
