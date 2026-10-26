import json

import pytest
from fastapi.testclient import TestClient

from app import bank, courses
from app.bank_ai import Plan
from app.config import Settings
from app.course_catalog import BOOKS, GOALS, VERSION
from app.db import connect, initialize
from app.main import create_app
from app.tutor import TutorContent


def question(qid, knowledge, subject="math", **extra):
    return {"id": "bank:course:" + qid, "subject": subject, "stage": "junior", "grade": None, "term": None,
            "stem": qid + "：请选择正确结论。", "kind": "single_choice", "status": "ready",
            "options": [{"key": "A", "text": "正确"}, {"key": "B", "text": "错误"}], "answer": "A",
            "steps": ["根据条件判断。"], "difficulty": 1, "knowledge_tags": [knowledge], "type_tags": ["类型" + qid],
            "tags_source": "source", "provenance": {"dataset": "course-test", "source_id": qid}, **extra}


@pytest.fixture
def setup(tmp_path):
    settings = Settings(auth_required=False, database_path=tmp_path / "course.sqlite3", deepseek_api_key="local-only", _env_file=None)
    with TestClient(create_app(settings)) as client:
        with connect(settings.database_path) as db:
            bank.import_records(db, "course-test", [question("absolute", "绝对值"), question("quadratic", "二次函数"),
                question("unmapped", "未映射知识"), question("senior", "绝对值", stage="senior"),
                question("reading", "文章内容概括", "chinese")], {})
        yield client, settings


def test_catalog_has_stages_and_verifiable_requirements(setup):
    client, _ = setup
    assert len([b for b in BOOKS if b['stage']=='junior']) == 56
    assert len([g for g in GOALS.values() if g.get('stage','junior')=='junior']) == 196
    for subject in bank.SUBJECTS:
        result = client.get("/api/v1/courses", params={"subject": subject}).json()
        assert result["books"] and result["version"] == VERSION
        for book in result["books"]:
            assert book["sources"] and book["basis"] in {"pep_toc_verified", "standard_progression", "local_toc_verified"}
            assert book["stage_outcomes"]
            assert all(g["can_do"] and g["checks"] for u in book["units"] for g in u["goals"])
    assert client.get("/api/v1/courses?subject=music").status_code == 422
    assert {b["grade"] for b in BOOKS if b["subject"] == "chemistry"} == {9}
    assert {b["grade"] for b in BOOKS if b["subject"] == "biology"} == {7, 8}


def test_local_textbook_review_does_not_promote_a_different_edition(setup):
    client, settings = setup
    books = {b["id"]: b for b in client.get("/api/v1/courses?subject=math").json()["books"]}
    for bid in ("math-7-1", "math-7-2", "math-8-1", "math-8-2"):
        book = books[bid]
        assert book["basis"] == "pep_toc_verified"
        assert book["textbook_review"]["edition_year"] is None
        assert len(book["units"]) == len(book["textbook_review"]["chapters"])
        assert all(u["textbook_chapter"]["unit_id"] == u["id"] for u in book["units"])
    alternate = books["math-9-2"]
    assert alternate["basis"] == "standard_progression"
    assert alternate["textbook_review"]["alignment"] == "different_chapter_arrangement"
    assert alternate["textbook_review"]["chapters"][0]["name"] == "反比例函数"
    assert alternate["units"][0]["name"] == "相似"
    assert all(c["unit_id"] is None for c in alternate["textbook_review"]["chapters"])
    with connect(settings.database_path) as db:
        context = courses.context(db, "math", book_id="math-9-2")
    assert context["basis"] == "standard_progression"
    assert context["textbook_review"]["alignment"] == "different_chapter_arrangement"
    assert "尚未切换" in context["textbook_review"]["note"]


def test_setting_persists_and_cross_subject_unit_rejected(setup):
    client, settings = setup
    body = {"subject": "math", "book_id": "math-8-2", "unit_id": "math-8-2:u2"}
    assert client.post("/api/v1/courses/setting", json=body).status_code == 200
    assert client.get("/api/v1/courses").json()["setting"] == body
    assert client.post("/api/v1/courses/setting", json={**body, "book_id": "chinese-8-2"}).status_code == 422
    assert client.post("/api/v1/courses/setting", json={**body, "unit_id": "math-7-1:u1"}).status_code == 422
    initialize(settings.database_path)
    assert client.get("/api/v1/courses").json()["setting"] == body


def test_learning_preferences_persist_with_separate_subject_progress(setup):
    client, settings = setup
    defaults = client.get("/api/v1/courses/preferences").json()
    assert defaults["subject"] == "math" and defaults["limit_course"] and defaults["allow_challenge"]
    math = {"subject": "math", "book_id": "math-8-2", "unit_id": "math-8-2:u3", "limit_course": False, "allow_challenge": False}
    assert client.post("/api/v1/courses/preferences", json=math).status_code == 200
    chemistry = {**math, "subject": "chemistry", "book_id": "chemistry-9-1", "unit_id": None}
    assert client.post("/api/v1/courses/preferences", json=chemistry).status_code == 200
    initialize(settings.database_path)
    current = client.get("/api/v1/courses/preferences").json()
    assert all(current[key] == value for key, value in chemistry.items())
    assert current["scope"]["subject_name"] == "化学" and current["scope"]["stage_label"] == "9年级 · 上学期"
    assert client.get("/api/v1/courses?subject=math").json()["setting"] == {k:math[k] for k in ("subject", "book_id", "unit_id")}


def test_invalid_preferences_do_not_change_any_saved_settings(setup):
    client, _ = setup
    before = client.get("/api/v1/courses/preferences").json()
    for change in ({"book_id": "chinese-7-1"}, {"unit_id": "math-8-2:u1"}, {"book_id": ""}, {"subject": "music"}):
        result = client.post("/api/v1/courses/preferences", json={**before, **change})
        assert result.status_code == 422
        assert client.get("/api/v1/courses/preferences").json() == before


def test_version_five_upgrade_retains_course_progress(setup):
    client, settings = setup
    body = {"subject": "math", "book_id": "math-8-2", "unit_id": "math-8-2:u3"}
    client.post("/api/v1/courses/setting", json=body)
    with connect(settings.database_path) as db:
        db.execute("DROP TABLE student_preferences")
        db.execute("PRAGMA user_version=5")
    initialize(settings.database_path)
    result = client.get("/api/v1/courses/preferences").json()
    assert all(result[key] == value for key, value in body.items())


def test_course_filter_uses_knowledge_mapping_not_stem_or_guessed_grade(setup):
    client, settings = setup
    result = client.get("/api/v1/bank/questions", params={"subject": "math", "course_book_id": "math-7-1", "course_unit_id": "math-7-1:u1"}).json()
    assert [q["id"] for q in result["items"]] == ["bank:course:absolute"]
    assert result["items"][0]["grade"] is None
    assert client.get("/api/v1/bank/questions?subject=chinese&course_book_id=math-7-1").status_code == 422
    assert client.post("/api/v1/bank/next", json={"subject": "math", "course_book_id": "math-7-1", "question_id": "bank:course:quadratic"}).status_code == 404
    with connect(settings.database_path) as db:
        q = json.loads(db.execute("SELECT data FROM bank_questions WHERE id='bank:course:absolute'").fetchone()[0])
        assert q["knowledge_tags"] == ["绝对值"] and q["grade"] is None


def test_unassessed_missing_questions_and_one_answer_are_not_mastery(setup):
    client, _ = setup
    before = client.get("/api/v1/courses/report").json()
    assert before["summary"]["unassessed"] == before["summary"]["total"]
    assert all(g["mastery"] is None and g["status"] == "待诊断" for g in before["goals"])
    assert before["summary"]["no_questions"] > 0
    a = client.post("/api/v1/bank/next", json={"question_id": "bank:course:absolute"}).json()
    client.post(f"/api/v1/bank/attempts/{a['attempt_id']}/answer", json={"answer": "A"})
    after = client.get("/api/v1/courses/report").json()
    target = next(g for g in after["goals"] if g["name"] == "绝对值")
    assert target["attempts"] == 1 and target["status"] == "证据不足"
    assert client.get("/api/v1/courses/report?subject=chinese").json()["summary"]["diagnosed"] == 0
    again = client.post("/api/v1/bank/next", json={"question_id": "bank:course:absolute"}).json()
    client.post(f"/api/v1/bank/attempts/{again['attempt_id']}/answer", json={"answer": "A"})
    assert next(g for g in client.get("/api/v1/courses/report").json()["goals"] if g["name"] == "绝对值")["attempts"] == 1


def test_existing_math_answers_supply_only_related_course_evidence(setup):
    client, _ = setup
    a = client.post("/api/v1/practice/next", json={"knowledge_id": "absolute", "difficulty": 1}).json()
    client.post(f"/api/v1/attempts/{a['attempt_id']}/answer", json={"answer": "99999"})
    report = client.get("/api/v1/courses/report").json()
    goals = [g for g in report["goals"] if g["attempts"]]
    assert len(goals) == 1 and goals[0]["name"] == "绝对值" and goals[0]["failure_weight"] == 1
    assert client.get("/api/v1/student").json()["completed"] == 1


def test_ai_selection_receives_goals_and_cannot_escape_course_scope(setup, monkeypatch):
    client, _ = setup
    captured = []
    async def fake(settings, messages, schema, vision=False):
        value = json.loads(messages[1]["content"])["learning_material"]; captured.append(value)
        return Plan(tag_id=value["tags"][0]["id"], difficulty=1, reason="按当前目标诊断。")
    monkeypatch.setattr("app.bank_ai.request_json", fake)
    result = client.post("/api/v1/bank/plan", json={"course_book_id": "math-7-1", "course_unit_id": "math-7-1:u1"}).json()
    assert result["question"]["id"] == "bank:course:absolute"
    assert captured[0]["course_requirements"]["grade"] == 7
    assert captured[0]["course_requirements"]["goals"][0]["checks"]
    assert captured[0]["course_requirements"]["stage_outcomes"]
    quadratic = next(t for q in client.get("/api/v1/bank/questions").json()["items"] if q["id"] == "bank:course:quadratic" for t in q["tags"])
    async def outside(*args, **kwargs):
        return Plan(tag_id=quadratic["id"], difficulty=1, reason="不合法的跨阶段选择。")
    monkeypatch.setattr("app.bank_ai.request_json", outside)
    assert client.post("/api/v1/bank/plan", json={"course_book_id": "math-7-1"}).status_code == 502


def test_tutor_receives_selected_stage_and_outside_scope_notice(setup, monkeypatch):
    client, _ = setup
    client.post("/api/v1/courses/setting", json={"subject": "math", "book_id": "math-9-1", "unit_id": None})
    captured = []
    async def fake(settings, messages, schema, vision=False):
        captured.append(json.loads(messages[1]["content"])["learning_material"])
        return TutorContent(reply="先检查这个前置概念。", check_question="距离能为负吗？")
    monkeypatch.setattr("app.bank_ai.request_json", fake)
    a = client.post("/api/v1/bank/next", json={"question_id": "bank:course:absolute"}).json()
    response = client.post(f"/api/v1/bank/attempts/{a['attempt_id']}/tutor", json={"message": "讲一下"})
    assert response.status_code == 200
    context = captured[0]["course_requirements"]
    assert context["grade"] == 9 and context["question_relation"] == "当前目标范围外或尚未映射"
    assert "answer" not in captured[0]["question"]


def test_superseded_questions_keep_evidence_after_mapping_rebuild(setup):
    client, settings = setup
    a = client.post("/api/v1/bank/next", json={"question_id": "bank:course:absolute"}).json()
    client.post(f"/api/v1/bank/attempts/{a['attempt_id']}/answer", json={"answer": "A"})
    with connect(settings.database_path) as db:
        db.execute("UPDATE bank_questions SET status='superseded' WHERE id='bank:course:absolute'")
        db.execute("DELETE FROM course_question_links")
        db.execute("DELETE FROM course_mapping_state")
        courses.sync_questions(db)
    goal = next(g for g in client.get("/api/v1/courses/report").json()["goals"] if g["name"] == "绝对值")
    assert goal["attempts"] == 1 and goal["question_count"] == 0
    assert client.get("/api/v1/bank/questions?course_book_id=math-7-1").json()["total"] == 0


def test_mapping_is_idempotent_and_rebuilds_after_label_change(setup):
    _, settings = setup
    with connect(settings.database_path) as db:
        n = db.execute("SELECT COUNT(*) FROM course_question_links").fetchone()[0]
        assert courses.sync_questions(db) == 0
        assert db.execute("SELECT COUNT(*) FROM course_question_links").fetchone()[0] == n
        row = db.execute("SELECT data FROM bank_questions WHERE id='bank:course:absolute'").fetchone()
        q = json.loads(row[0]); q["knowledge_tags"] = ["未映射知识"]
        db.execute("UPDATE bank_questions SET data=? WHERE id=?", (json.dumps(q), q["id"]))
        assert courses.sync_questions(db, [q["id"]]) == 1
        assert not db.execute("SELECT 1 FROM course_question_links WHERE question_id=?", (q["id"],)).fetchone()


def test_version_four_migration_preserves_answers(setup):
    client, settings = setup
    a = client.post("/api/v1/bank/next", json={"question_id": "bank:course:absolute"}).json()
    result = client.post(f"/api/v1/bank/attempts/{a['attempt_id']}/answer", json={"answer": "A"}).json()
    with connect(settings.database_path) as db:
        for table in ("course_question_links", "course_mapping_state", "course_settings", "student_preferences"):
            db.execute("DROP TABLE " + table)
        db.execute("PRAGMA user_version=4")
    initialize(settings.database_path)
    with connect(settings.database_path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 16
        assert json.loads(db.execute("SELECT result FROM bank_attempts WHERE id=?", (a["attempt_id"],)).fetchone()[0]) == result
        assert db.execute("SELECT COUNT(*) FROM course_question_links").fetchone()[0] > 0


def test_practical_targets_do_not_claim_mastery_from_choice_questions(setup):
    client, settings = setup
    with connect(settings.database_path) as db:
        bank.import_records(db, "course-test", [question(f"measure{i}", "长度测量", "physics") for i in range(4)], {})
    for i in range(4):
        a = client.post("/api/v1/bank/next", json={"subject": "physics", "question_id": f"bank:course:measure{i}"}).json()
        client.post(f"/api/v1/bank/attempts/{a['attempt_id']}/answer", json={"answer": "A"})
    goal = next(g for g in client.get("/api/v1/courses/report?subject=physics").json()["goals"] if g["attempts"])
    assert goal["attempts"] == 4 and goal["practical"] and goal["status"] == "继续检查"
