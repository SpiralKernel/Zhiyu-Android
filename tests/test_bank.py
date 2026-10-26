import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import bank
from app.bank_ai import Assessment
from app.config import Settings
from app.db import connect, initialize
from app.main import create_app


def record(id="choice", subject="math", kind="single_choice", **overrides):
    return {"id": "bank:test:"+id, "subject": subject, "stage": "junior", "grade": None, "term": None,
            "stem": "计算 1+2，选择正确结果。" if kind == "single_choice" else "阅读完整材料后，分步骤回答问题。",
            "kind": kind, "status": "ready" if kind == "single_choice" else "reference", "options": [{"key": "A", "text": "3"}, {"key": "B", "text": "4"}] if kind == "single_choice" else [],
            "answer": "A" if kind == "single_choice" else "先读材料，再列出理由。", "steps": ["根据条件分析。"], "difficulty": 1,
            "difficulty_raw": "容易", "knowledge_tags": ["有理数运算"], "type_tags": ["单选题"], "derived_type_tags": ["单选题 · 有理数运算"], "tags_source": "source",
            "source_tags": ["容易", "单选题"], "has_missing_assets": False, "provenance": {"dataset": "test", "source_id": id, "license": "test", "url": "https://example.com"}, **overrides}


@pytest.fixture
def settings(tmp_path):
    return Settings(auth_required=False, database_path=tmp_path/"test.sqlite3", deepseek_api_key="test-only", _env_file=None)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        with connect(settings.database_path) as db:
            bank.import_records(db, "test", [record(), record("reading", "chinese", "reference", stem="长阅读材料。"*200),
                record("science", "physics", "reference", stem="写出完整过程。"), record("missing", "biology", "reference", stem="如图判断。", has_missing_assets=True),
                record("senior", stage="senior", stem="高中题目。")], {"url": "https://example.com", "license": "test"})
        yield client


def start(client, subject="math", question_id=None, **filters):
    response = client.post("/api/v1/bank/next", json={"subject": subject, "question_id": question_id, **filters})
    assert response.status_code == 200, response.text
    return response.json()


def test_import_idempotency_source_tags_and_snapshot_versioning(client, settings):
    with connect(settings.database_path) as db:
        assert bank.import_records(db, "test", [record()], {})["duplicates"] == 1
        db.commit()
        modified = record(stem="计算 2+3。")
        assert bank.import_records(db, "test", [modified], {})["inserted"] == 1
        assert db.execute("SELECT COUNT(*) FROM bank_questions WHERE id LIKE 'bank:test:choice%'").fetchone()[0] == 2
        old=json.loads(db.execute("SELECT data FROM bank_questions WHERE id='bank:test:choice'").fetchone()[0])
        assert not old["can_practice"] and old["answer"]=="A"
    items = client.get("/api/v1/bank/questions").json()["items"]
    assert all("answer" not in q and "steps" not in q for q in items)
    assert any(t["label"] == "单选题 · 有理数运算" for q in items for t in q["tags"])


def test_selection_filters_grade_scope_and_missing_assets(client):
    result = client.get("/api/v1/bank/questions?subject=math").json()
    assert result["total"] == 1 and result["items"][0]["stage"] == "junior"
    a = start(client)
    assert start(client)["attempt_id"] == a["attempt_id"]
    assert client.post("/api/v1/bank/next", json={"subject": "biology"}).status_code == 404
    assert start(client)["attempt_id"] == a["attempt_id"]
    tags = client.get("/api/v1/bank/tags").json()["items"]
    assert start(client, tag_id=tags[0]["id"])["question"]["id"] == a["question"]["id"]
    assert client.get("/api/v1/bank/questions?subject=invalid").status_code == 422


def test_grouped_reading_conversion_is_versioned_and_idempotent(client, settings):
    with connect(settings.database_path) as db:
        converted = record(kind="reference", options=record()["options"], answer="A", stem=record()["stem"])
        assert bank.import_records(db, "test", [converted], {})["inserted"] == 1
    with connect(settings.database_path) as db:
        assert bank.import_records(db, "test", [converted], {})["duplicates"] == 1
        versions = db.execute("SELECT status,data FROM bank_questions WHERE id LIKE 'bank:test:choice%'").fetchall()
        assert len(versions) == 2
        assert sum(v["status"] == "superseded" for v in versions) == 1
        current = json.loads(next(v["data"] for v in versions if v["status"] != "superseded"))
        assert current["answer_mode"] == "written" and current["answer"] == "A"


def test_choice_grading_retry_repeat_and_subject_isolation(client):
    a = start(client); url = f"/api/v1/bank/attempts/{a['attempt_id']}/answer"
    assert client.post(url, json={"answer": "A<script>"}).status_code == 422
    result = client.post(url, json={"answer": "Ａ"}).json()
    assert result["correct"] and result["evidence_weight"] == 1
    assert client.post(url, json={"answer": "A"}).json() == result
    assert client.post(url, json={"answer": "B"}).status_code == 409
    assert client.get("/api/v1/bank/profile?subject=chinese").json()["completed"] == 0
    repeated = start(client)
    assert client.post(f"/api/v1/bank/attempts/{repeated['attempt_id']}/answer", json={"answer": "A"}).json()["evidence_weight"] == 0
    assert client.get("/api/v1/student").json()["completed"] == 0
    assert all(t["attempts"] == 1 for t in client.get("/api/v1/bank/profile").json()["tags"])


def test_multiselect_order_and_invalid_selection(client, settings):
    with connect(settings.database_path) as db:
        bank.import_records(db, "test", [record("multi", kind="multiple_choice", stem="多选示例", options=[{"key": "A", "text": "甲"}, {"key": "B", "text": "乙"}, {"key": "C", "text": "丙"}], answer="AC")], {})
    a = start(client, question_id="bank:test:multi"); url = f"/api/v1/bank/attempts/{a['attempt_id']}/answer"
    assert client.post(url, json={"answer": "D"}).status_code == 422
    assert client.post(url, json={"answer": "C,A"}).json()["correct"]


def mock_assessment(monkeypatch, verdict="correct", transcription="我的完整解答", propose=False):
    captured = []
    async def fake(settings, messages, schema, vision=False):
        captured.append((messages, vision))
        return Assessment(transcribed_answer=transcription, verdict=verdict, reason="逐步检查了条件和结论。", steps_feedback=["第一步成立。", "结论与参考一致。"], confidence="high", proposed_types=["自拟新结构"] if propose else [])
    monkeypatch.setattr("app.bank_ai.request_json", fake)
    return captured


def image_bytes():
    out = io.BytesIO(); Image.new("RGB", (300, 400), "white").save(out, "PNG"); return out.getvalue()


def test_written_photo_assessment_requires_review_and_preserves_tags(client, settings, monkeypatch):
    captured = mock_assessment(monkeypatch, propose=True)
    a = start(client, "chinese"); url = f"/api/v1/bank/attempts/{a['attempt_id']}"
    response = client.post(url+"/assess", data={"answer": "（1）我的回答。"}, files={"files": ("answer.png", image_bytes(), "image/png")})
    assert response.status_code == 200, response.text
    review = response.json()
    assert review["status"] == "review" and captured[0][1]
    assert captured[0][0][-1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert client.get("/api/v1/bank/profile?subject=chinese").json()["completed"] == 0
    assert client.get(url+"/pages/"+review["files"][0]).headers["content-type"] == "image/jpeg"
    body = {"review_id": review["id"], "reviewed": False, "verdict": "correct", "transcribed_answer": "我的完整解答"}
    assert client.post(url+"/confirm", json=body).status_code == 422
    body["reviewed"] = True
    result = client.post(url+"/confirm", json=body).json()
    assert result["evidence_weight"] == .5
    assert client.post(url+"/confirm", json=body).json() == result
    with connect(settings.database_path) as db:
        assert not db.execute("SELECT 1 FROM bank_taxonomy WHERE label='自拟新结构'").fetchone()
    profile = client.get("/api/v1/bank/profile?subject=chinese").json()
    assert profile["completed"] == 1 and profile["tags"][0]["mastery"] == .6


@pytest.mark.parametrize("verdict", ["partial", "uncertain"])
def test_partial_uncertain_and_illegible_do_not_score(client, monkeypatch, verdict):
    mock_assessment(monkeypatch, verdict=verdict, transcription="看不清" if verdict == "uncertain" else "部分完成")
    a = start(client, "physics"); url = f"/api/v1/bank/attempts/{a['attempt_id']}"
    review = client.post(url+"/assess", data={"answer": "我的步骤"}).json()
    result = client.post(url+"/confirm", json={"review_id": review["id"], "reviewed": True, "verdict": verdict, "transcribed_answer": review["assessment"]["transcribed_answer"]}).json()
    assert result["evidence_weight"] == 0
    assert client.get("/api/v1/bank/profile?subject=physics").json()["tags"] == []


def test_assessment_failure_no_phantom_score_and_retries(client, monkeypatch):
    async def fail(*args, **kwargs):
        from fastapi import HTTPException
        raise HTTPException(502, "模拟超时")
    monkeypatch.setattr("app.bank_ai.request_json", fail)
    a = start(client, "physics"); url = f"/api/v1/bank/attempts/{a['attempt_id']}"
    assert client.post(url+"/assess", data={"answer": "我的步骤"}).status_code == 502
    assert client.get(url).json()["review"]["status"] == "failed"
    assert client.get("/api/v1/bank/profile?subject=physics").json()["completed"] == 0
    mock_assessment(monkeypatch)
    assert client.post(url+"/assess", data={"answer": "我的步骤"}).status_code == 200


def test_photo_validation_and_wrong_mode_rejected(client):
    a = start(client, "physics"); url = f"/api/v1/bank/attempts/{a['attempt_id']}"
    assert client.post(url+"/assess", files={"files": ("bad.jpg", b"bad", "image/jpeg")}).status_code == 422
    assert client.post(url+"/assess", files=[("files", ("a.png", image_bytes(), "image/png"))]*5).status_code == 422
    assert client.post(url+"/answer", json={"answer": "A"}).status_code == 422


def test_tutoring_sets_assisted_weight_and_keeps_answer_out_of_prompt(client, monkeypatch):
    captured=[]
    async def fake(settings, q, message, previous, submitted, summary):
        captured.append((submitted, summary)); return {"reply": "先想一步", "check_question": "条件是什么？", "provider": "test"}
    monkeypatch.setattr("app.bank_ai.tutor", fake)
    a = start(client); url = f"/api/v1/bank/attempts/{a['attempt_id']}"
    assert client.post(url+"/tutor", json={"message": "帮助我"}).status_code == 200
    assert not captured[0][0]
    assert client.post(url+"/answer", json={"answer": "A"}).json()["evidence_weight"] == .35


def test_model_request_payload_sanitizes_failures(settings, monkeypatch):
    import asyncio
    from app.bank_ai import request_json
    from fastapi import HTTPException
    class Broken:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): raise httpx.ConnectError("secret-provider-body")
    monkeypatch.setattr("app.bank_ai.httpx.AsyncClient", Broken)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(request_json(settings, [], Assessment))
    assert exc.value.status_code == 502 and "secret" not in exc.value.detail


def test_ai_plan_accepts_only_catalog_tags(client,monkeypatch):
    from app.bank_ai import Plan
    known=client.get('/api/v1/bank/tags').json()['items'][0]['id']
    async def fake(*args,**kwargs):return Plan(tag_id=known,difficulty=1,reason='按已有证据先做诊断。')
    monkeypatch.setattr('app.bank_ai.request_json',fake)
    result=client.post('/api/v1/bank/plan',json={'subject':'math'}).json()
    assert result['recommendation']['tag_id']==known
    async def invalid(*args,**kwargs):return Plan(tag_id='invented',difficulty=1,reason='无效目录ID')
    monkeypatch.setattr('app.bank_ai.request_json',invalid)
    assert client.post('/api/v1/bank/plan',json={'subject':'math'}).status_code==502


def test_missing_type_can_be_created_without_grading(client,settings,monkeypatch):
    with connect(settings.database_path) as db:
        bank.import_records(db,'test',[record('untyped','physics','reference',stem='新解题结构',type_tags=[],derived_type_tags=[])],{})
    mock_assessment(monkeypatch,propose=True)
    a=start(client,'physics',question_id='bank:test:untyped')
    assert client.post(f"/api/v1/bank/attempts/{a['attempt_id']}/assess",data={'answer':'自己的解答'}).status_code==200
    profile=client.get('/api/v1/bank/profile?subject=physics').json()
    assert profile['completed']==0
    new=next(t for t in profile['tags'] if t['label']=='自拟新结构')
    assert new['mastery'] is None and new['status']=='尚未诊断'
