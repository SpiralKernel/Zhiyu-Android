import json

import pytest
from fastapi.testclient import TestClient

from app.challenges import make_challenge, validate_challenge
from app.config import Settings
from app.curriculum import NODES
from app.db import connect, initialize
from app.main import create_app
from app.materials import RecognizedItem
from app.question_types import register_ai_type, template_type_id
from app.questions import grade


@pytest.mark.parametrize("key",[n["id"] for n in NODES])
def test_challenge_variants(key):
    for index in range(200):
        q=make_challenge(key,index)
        q=json.loads(json.dumps(q))
        assert q["difficulty"]==3 and validate_challenge(q)
        assert grade(q,q["answer"])["correct"]
        assert template_type_id(q)=="challenge:"+key


def test_type_registry_scope_and_name_deduplication(tmp_path):
    settings=Settings(auth_required=False, database_path=tmp_path/"type.sqlite3",deepseek_api_key="",_env_file=None)
    initialize(settings.database_path)
    with connect(settings.database_path) as db:
        known=register_ai_type(db,RecognizedItem(stem="题目",question_type_name="负数减负数"),"source-test")
        assert known=="template:addition"
        item=RecognizedItem(stem="题目",question_type_name="绝对值分段讨论",question_type_description="按符号讨论绝对值",knowledge_ids=["absolute"])
        first=register_ai_type(db,item,"source-test")
        item.question_type_name="绝对值 分段讨论"
        assert register_ai_type(db,item,"source-test")==first
        assert register_ai_type(db,RecognizedItem(stem="题目"),"source-test") is None
    with TestClient(create_app(settings)) as client:
        t=next(t for t in client.get("/api/v1/student").json()["question_types"] if t["id"]==first)
        assert t["attempts"]==0 and t["status"]=="尚未诊断" and t["source"]=="ai"


def test_challenge_selection_and_fine_type_state(tmp_path,monkeypatch):
    settings=Settings(auth_required=False, database_path=tmp_path/"type.sqlite3",deepseek_api_key="",_env_file=None)
    with TestClient(create_app(settings)) as client:
        a=client.post("/api/v1/practice/next",json={"knowledge_id":"addition","difficulty":3}).json()
        assert a["question"]["difficulty"]==3 and a["question"]["type_id"]=="challenge:addition"
        with connect(settings.database_path) as db:
            q=json.loads(db.execute("SELECT data FROM questions WHERE id=?",(a["question"]["id"],)).fetchone()[0])
        client.post(f"/api/v1/attempts/{a['attempt_id']}/answer",json={"answer":q["answer"]})
        types={t["id"]:t for t in client.get("/api/v1/student").json()["question_types"]}
        assert types["challenge:addition"]["attempts"]==1
        assert types["template:addition"]["attempts"]==0
        monkeypatch.setattr("app.learning.random.random",lambda:0)
        a=client.post("/api/v1/practice/next",json={"knowledge_id":"addition","allow_challenge":True}).json()
        assert a["question"]["difficulty"]==3
        a=client.post("/api/v1/practice/next",json={"knowledge_id":"addition","question_type_id":"template:addition"}).json()
        assert a["question"]["type_id"]=="template:addition"


def test_existing_attempts_backfill_type_profiles_without_regrading(tmp_path):
    settings=Settings(auth_required=False, database_path=tmp_path/"type.sqlite3",deepseek_api_key="",_env_file=None)
    with TestClient(create_app(settings)) as client:
        a=client.post("/api/v1/practice/next",json={"knowledge_id":"opposite"}).json()
        with connect(settings.database_path) as db:
            q=json.loads(db.execute("SELECT data FROM questions WHERE id=?",(a["question"]["id"],)).fetchone()[0])
        client.post(f"/api/v1/attempts/{a['attempt_id']}/answer",json={"answer":q["answer"]})
    with TestClient(create_app(settings)) as client:
        student=client.get("/api/v1/student").json()
        assert student["completed"]==1
        t=next(t for t in student["question_types"] if t["id"]=="template:opposite")
        assert t["attempts"]==1 and t["correct"]==1
