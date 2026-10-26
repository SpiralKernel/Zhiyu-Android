import json
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.curriculum import NODES
from app.db import connect, initialize
from app.main import create_app
from app.questions import grade, make_question, parse_number, validate_question


@pytest.fixture
def settings(tmp_path):
    return Settings(auth_required=False, database_path=tmp_path / "test.sqlite3", deepseek_api_key="", _env_file=None)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def assigned(client, knowledge="addition"):
    response = client.post("/api/v1/practice/next", json={"knowledge_id": knowledge})
    assert response.status_code == 200, response.text
    return response.json()


def stored_question(settings, attempt):
    with connect(settings.database_path) as db:
        return json.loads(db.execute("SELECT data FROM questions WHERE id=?", (attempt["question"]["id"],)).fetchone()[0])


@pytest.mark.parametrize("node", [n["id"] for n in NODES])
def test_generated_answers_and_error_rules(node):
    # 每个模板覆盖 250 套参数；验证准确数值、独立不变量和常见错答诊断。
    for index in range(250):
        q = make_question(node, index)
        assert validate_question(q)
        assert grade(q, q["answer"])["correct"]
        for error in q["common_errors"]:
            result = grade(q, error["answer"])
            assert not result["correct"]
            assert result["error"]["code"] == error["code"]


@pytest.mark.parametrize("text,result", [("−3", -3),("１／２", Fraction(1,2)),("0.50",Fraction(1,2)),("-1 / -2",Fraction(1,2)),(".5",Fraction(1,2))])
def test_exact_numeric_equivalence(text, result):
    assert parse_number(text) == result


@pytest.mark.parametrize("text", ["1/0", "x=3", "NaN", "2**100", "__import__('os')", "", "3cm", "1e9000"])
def test_unsafe_and_ambiguous_answers_rejected(text):
    with pytest.raises(ValueError):
        parse_number(text)


def test_full_learning_flow_and_idempotency(client, settings):
    assert client.get("/api/v1/student").json()["completed"] == 0
    attempt = assigned(client)
    assert "answer" not in attempt["question"] and "steps" not in attempt["question"]
    assert assigned(client)["attempt_id"] == attempt["attempt_id"]
    q = stored_question(settings, attempt)
    url = f"/api/v1/attempts/{attempt['attempt_id']}/answer"
    result = client.post(url, json={"answer":q["answer"]})
    assert result.status_code == 200 and result.json()["correct"]
    assert result.json()["evidence_weight"] == 1
    assert client.post(url, json={"answer":q["answer"]}).json() == result.json()
    assert client.post(url, json={"answer":"99999"}).status_code == 409
    student = client.get("/api/v1/student").json()
    assert student["completed"] == 1
    state = next(n for n in student["knowledge"] if n["id"] == "addition")
    assert state["attempts"] == 1 and state["status"] == "证据不足"
    assert len(client.get("/api/v1/history").json()["items"]) == 1
    with connect(settings.database_path) as db:
        # 提交触发补题，使可用题数恢复为 6。
        assert db.execute("SELECT COUNT(*) FROM questions WHERE knowledge_id='addition' AND json_extract(data,'$.difficulty')<3 AND json_extract(data,'$.provenance.family') IS NULL").fetchone()[0] == 7


def test_hints_lower_weight_and_invalid_input_does_not_mutate(client, settings):
    attempt = assigned(client, "power")
    url = f"/api/v1/attempts/{attempt['attempt_id']}"
    q = stored_question(settings, attempt)
    assert client.post(url+"/answer",json={"answer":"1/0"}).status_code == 422
    assert client.get("/api/v1/student").json()["completed"] == 0
    assert client.post(url+"/hint").status_code == 200
    result = client.post(url+"/answer",json={"answer":q["answer"]}).json()
    assert result["assisted"] and result["evidence_weight"] == .35


def test_switching_topic_closes_old_assignment(client):
    a = assigned(client,"absolute")
    b = assigned(client,"segment")
    assert a["attempt_id"] != b["attempt_id"]
    assert client.post(f"/api/v1/attempts/{a['attempt_id']}/answer",json={"answer":"2"}).status_code == 409


def test_error_pattern_and_unknown_error(client, settings):
    a = assigned(client, "multiply")
    q = stored_question(settings,a)
    result = client.post(f"/api/v1/attempts/{a['attempt_id']}/answer",json={"answer":q["common_errors"][0]["answer"]}).json()
    assert result["error"]["code"] == "product_sign"
    assert client.get("/api/v1/student").json()["weak_patterns"][0]["count"] == 1
    a = assigned(client,"multiply")
    result = client.post(f"/api/v1/attempts/{a['attempt_id']}/answer",json={"answer":"99999"}).json()
    assert result["error"]["code"] == "unclassified"


def test_restart_preserves_records_and_does_not_duplicate_seeds(client, settings):
    a = assigned(client)
    client.post(f"/api/v1/attempts/{a['attempt_id']}/answer",json={"answer":"99999"})
    with connect(settings.database_path) as db:
        count = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    initialize(settings.database_path)
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get("/api/v1/student").json()["completed"] == 1
        assert restarted.get("/api/v1/health").json()["question_count"] == count


def test_parallel_double_submit_counts_once(client, settings):
    a = assigned(client)
    q = stored_question(settings,a)
    def send(_):
        return client.post(f"/api/v1/attempts/{a['attempt_id']}/answer",json={"answer":q["answer"]})
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(send, range(4)))
    assert all(r.status_code == 200 for r in responses)
    assert client.get("/api/v1/student").json()["completed"] == 1


def test_rules_tutor_and_rate_limit(client):
    a = assigned(client,"linear")
    url = f"/api/v1/attempts/{a['attempt_id']}/tutor"
    for _ in range(12):
        result = client.post(url,json={"message":"我应该先做哪一步？"})
        assert result.status_code == 200 and result.json()["provider"] == "rules"
    assert client.post(url,json={"message":"再说一下"}).status_code == 429
    assert client.post(url,json={"message":"   "}).status_code == 422


def test_deepseek_contract_and_context_minimization(settings, monkeypatch):
    requests=[]
    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,url,**kwargs):
            requests.append((url,kwargs))
            return httpx.Response(200,json={"choices":[{"message":{"content":json.dumps({"reply":"先找出等量关系。","check_question":"等式两边如何保持相等？"})}}]},request=httpx.Request("POST",url))
    monkeypatch.setattr("app.tutor.httpx.AsyncClient",FakeClient)
    settings.deepseek_api_key="test-key-not-real"
    with TestClient(create_app(settings)) as c:
        a=assigned(c,"linear")
        result=c.post(f"/api/v1/attempts/{a['attempt_id']}/tutor",json={"message":"帮我想一步"}).json()
        assert result["provider"] == "deepseek"
        url,kwargs=requests[0]
        assert url == "https://api.deepseek.com/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer test-key-not-real"
        context=kwargs["json"]["messages"][1]["content"]
        assert "reference_solution" not in context and "nickname" not in context
        assert "test-key-not-real" not in c.get("/api/v1/health").text


@pytest.mark.parametrize("mode",["http_error","bad_json","empty_choices","wrong_shape"])
def test_deepseek_failures_fallback_without_secrets(settings, monkeypatch, mode):
    class FakeClient:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,url,**kwargs):
            payload={"choices":[]} if mode=="empty_choices" else {"choices":[{"message":{"content":"broken" if mode=="bad_json" else "{}"}}]}
            return httpx.Response(401 if mode=="http_error" else 200,json=payload,request=httpx.Request("POST",url))
    monkeypatch.setattr("app.tutor.httpx.AsyncClient",FakeClient)
    settings.deepseek_api_key="secret-test-key"
    with TestClient(create_app(settings)) as c:
        a=assigned(c)
        result=c.post(f"/api/v1/attempts/{a['attempt_id']}/tutor",json={"message":"这一步怎么想"})
        assert result.status_code == 200 and result.json()["provider"] == "rules"
        assert "secret-test-key" not in result.text


def test_unknown_resources_and_static_frontend(client):
    assert client.post("/api/v1/practice/next",json={"knowledge_id":"unknown"}).status_code == 404
    assert client.post("/api/v1/attempts/unknown/answer",json={"answer":"1"}).status_code == 404
    assert client.get("/").status_code == 200
    assert client.get("/static/js/student.js").status_code == 200
    assert client.get("/api/v1/student").headers["Cache-Control"] == "no-store"
