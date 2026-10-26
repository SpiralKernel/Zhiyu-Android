import io
import json
import shutil

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter

from app.config import Settings
from app.db import connect, initialize
from app.main import create_app
from app.materials import PageRecognition, normalized_image, prepare_pages, recognize_page, storage


@pytest.fixture
def settings(tmp_path):
    return Settings(auth_required=False, database_path=tmp_path/"materials.sqlite3", deepseek_api_key="fake-material-test-key", _env_file=None)


@pytest.fixture
def client(settings, monkeypatch):
    async def recognize(*args):
        return PageRecognition.model_validate({"items":[
            {"label":"1","stem":"计算 -8 − (-7)。","student_answer":"-15","reference_answer":"-1","knowledge_ids":["addition"],"suggested_verdict":"incorrect","confidence":"high","reason":"减去负数应改为加正数。","steps":["先改写为 -8+7。"]},
            {"label":"2","stem":"计算 |-7|。","student_answer":"7","reference_answer":"7","knowledge_ids":["absolute"],"suggested_verdict":"correct","confidence":"high","reason":"绝对值为非负距离。","steps":["计算到原点的距离。"]},
            {"label":"3","stem":"解 2x+1=7。","student_answer":"[看不清]","reference_answer":"x=3","knowledge_ids":["linear"],"suggested_verdict":"uncertain","confidence":"low","reason":"学生答案不清晰。","steps":[]},
        ]})
    monkeypatch.setattr("app.materials.recognize_page",recognize)
    with TestClient(create_app(settings)) as c:
        yield c


def image_bytes():
    out=io.BytesIO()
    Image.new("RGB",(300,400),"white").save(out,"PNG")
    return out.getvalue()


def upload(client, mode="completed"):
    response=client.post("/api/v1/imports",files=[("files",("paper.png",image_bytes(),"image/png"))],data={"mode":mode})
    assert response.status_code==201,response.text
    return response.json()


def recognized(client, mode="completed"):
    value=upload(client,mode)
    assert client.post(f"/api/v1/imports/{value['id']}/recognize").status_code==202
    value=client.get(f"/api/v1/imports/{value['id']}").json()
    assert value["status"]=="review",value
    return value


def confirmation(value):
    return {"items":[{**i,"verdict":i["suggested_verdict"],"reviewed":True,"count_evidence":i["suggested_verdict"] in {"correct","incorrect"}} for i in value["items"]]}


def test_upload_preview_review_confirm_and_targeted_recommendation(client, settings):
    value=recognized(client)
    assert client.get("/api/v1/student").json()["completed"]==0
    assert client.get(value["pages"][0]["url"]).headers["content-type"]=="image/jpeg"
    assert value["items"][0]["verdict"]=="uncertain"
    result=client.post(f"/api/v1/imports/{value['id']}/confirm",json=confirmation(value))
    assert result.status_code==200,result.text
    report=result.json()["report"]
    assert report["counts"]=={"correct":1,"incorrect":1,"unanswered":0,"uncertain":1}
    assert report["modules"][0]["knowledge_id"]=="addition"
    student=client.get("/api/v1/student").json()
    assert student["completed"]==2 and student["correct"]==1 and student["imported_completed"]==2
    addition=next(n for n in student["knowledge"] if n["id"]=="addition")
    assert addition["mastery"]==.4 and addition["imported_attempts"]==1
    assert "试卷显示" in student["recommendation"]["reason"]
    # 再次确认是幂等的，没有重复证据。
    client.post(f"/api/v1/imports/{value['id']}/confirm",json=confirmation(value))
    assert client.get("/api/v1/student").json()["completed"]==2


def test_duplicate_material_does_not_double_count(client):
    for _ in range(2):
        value=recognized(client)
        result=client.post(f"/api/v1/imports/{value['id']}/confirm",json=confirmation(value)).json()
    assert client.get("/api/v1/student").json()["completed"]==2
    assert sum(i.get("duplicate",False) for i in result["items"])==2


@pytest.mark.parametrize("invalid",["not_reviewed","missing_item","duplicate_item","uncertain_counted","unknown_knowledge","empty_answer","empty_reference"])
def test_confirmation_rejects_invalid_evidence_atomically(client,invalid):
    value=recognized(client)
    body=confirmation(value)
    if invalid=="not_reviewed": body["items"][-1]["reviewed"]=False
    elif invalid=="missing_item": body["items"].pop()
    elif invalid=="duplicate_item": body["items"][-1]=body["items"][0]
    elif invalid=="uncertain_counted": body["items"][-1]["count_evidence"]=True
    elif invalid=="unknown_knowledge": body["items"][-1]["knowledge_ids"]=["not-real"]
    elif invalid=="empty_answer": body["items"][1]["student_answer"]=""
    elif invalid=="empty_reference": body["items"][1]["reference_answer"]=""
    response=client.post(f"/api/v1/imports/{value['id']}/confirm",json=body)
    assert response.status_code==422,response.text
    assert client.get("/api/v1/student").json()["completed"]==0
    assert client.get(f"/api/v1/imports/{value['id']}").json()["status"]=="review"


def test_blank_material_cannot_assess_student(client):
    value=recognized(client,"blank")
    body=confirmation(value)
    assert client.post(f"/api/v1/imports/{value['id']}/confirm",json=body).status_code==422
    for item in body["items"]:
        item.update(verdict="unanswered",count_evidence=False,student_answer="")
    result=client.post(f"/api/v1/imports/{value['id']}/confirm",json=body)
    assert result.status_code==200
    assert client.get("/api/v1/student").json()["completed"]==0


def test_delete_retracts_import_evidence_preserves_practice(client, settings):
    a=client.post("/api/v1/practice/next",json={"knowledge_id":"absolute"}).json()
    client.post(f"/api/v1/attempts/{a['attempt_id']}/answer",json={"answer":"9999"})
    value=recognized(client)
    client.post(f"/api/v1/imports/{value['id']}/confirm",json=confirmation(value))
    assert client.get("/api/v1/student").json()["completed"]==3
    assert client.delete(f"/api/v1/imports/{value['id']}").status_code==200
    student=client.get("/api/v1/student").json()
    assert student["completed"]==1 and student["imported_completed"]==0
    assert client.get(f"/api/v1/imports/{value['id']}").status_code==404
    assert not (storage(settings)/value["id"]).exists()


def test_image_validation_and_metadata_normalization(client):
    assert client.post("/api/v1/imports",files={"files":("fake.jpg",b"<script>alert(1)</script>","image/jpeg")}).status_code==422
    assert client.post("/api/v1/imports",files={"files":("paper.png",image_bytes(),"image/png")},data={"mode":"wrong"}).status_code==422
    with Image.open(io.BytesIO(normalized_image(image_bytes()))) as image:
        assert image.format=="JPEG" and not image.getexif()


@pytest.mark.skipif(not shutil.which("pdftoppm"),reason="需要 Poppler")
def test_pdf_range_and_password_validation():
    writer=PdfWriter()
    for _ in range(3): writer.add_blank_page(width=200,height=280)
    content=io.BytesIO();writer.write(content)
    pages=prepare_pages([("book.pdf",content.getvalue())],2,3)
    assert len(pages)==2 and "第 2 页" in pages[0][0]
    with pytest.raises(ValueError,match="有效"):
        prepare_pages([("book.pdf",content.getvalue())],3,4)
    writer.encrypt("password")
    encrypted=io.BytesIO();writer.write(encrypted)
    with pytest.raises(ValueError,match="加密"):
        prepare_pages([("book.pdf",encrypted.getvalue())])


def test_pdf_page_limit():
    writer=PdfWriter()
    for _ in range(9):writer.add_blank_page(width=200,height=280)
    content=io.BytesIO();writer.write(content)
    if shutil.which("pdftoppm"):
        with pytest.raises(ValueError,match="8 页"):
            prepare_pages([("book.pdf",content.getvalue())])


def test_recognition_failure_is_retryable_and_no_phantom_mastery(client,monkeypatch):
    async def broken(*args):raise ValueError("识图请求超时，请重试")
    monkeypatch.setattr("app.materials.recognize_page",broken)
    value=upload(client)
    client.post(f"/api/v1/imports/{value['id']}/recognize")
    result=client.get(f"/api/v1/imports/{value['id']}").json()
    assert result["status"]=="failed" and "超时" in result["error"]
    assert client.get("/api/v1/student").json()["completed"]==0
    assert client.post(f"/api/v1/imports/{value['id']}/recognize").status_code==202


def test_recovery_and_migration_from_version_one(settings):
    with TestClient(create_app(settings)) as c:
        value=upload(c)
        with connect(settings.database_path) as db:
            db.execute("UPDATE imports SET status='processing' WHERE id=?",(value["id"],))
    with TestClient(create_app(settings)) as c:
        assert c.get(f"/api/v1/imports/{value['id']}").json()["status"]=="failed"
        a=c.post("/api/v1/practice/next",json={"knowledge_id":"absolute"}).json()
        c.post(f"/api/v1/attempts/{a['attempt_id']}/answer",json={"answer":"9999"})
    with connect(settings.database_path) as db:
        for table in ("student_preferences","course_settings","course_question_links","course_mapping_state","bank_messages","bank_reviews","bank_attempts","bank_question_tags","bank_taxonomy","bank_questions","bank_sources","import_messages","import_evidence","import_items","import_pages","imports","question_types","challenge_state"):
            db.execute(f"DROP TABLE {table}")
        db.execute("PRAGMA user_version=1")
    with TestClient(create_app(settings)) as c:
        assert c.get("/api/v1/student").json()["completed"]==1
        assert c.get("/api/v1/imports").json()["items"]==[]


def test_vision_payload_and_guardrails(settings,monkeypatch):
    initialize(settings.database_path)
    captured=[]
    class FakeClient:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            captured.append(kwargs["json"])
            content={"items":[{"stem":"计算 [看不清]+2。","student_answer":"3","reference_answer":"3","knowledge_ids":["addition","fake"],"suggested_verdict":"correct","confidence":"high"}]}
            return httpx.Response(200,json={"choices":[{"message":{"content":json.dumps(content)}}]},request=httpx.Request("POST",url))
    monkeypatch.setattr("app.materials.httpx.AsyncClient",FakeClient)
    import asyncio
    result=asyncio.run(recognize_page(settings,normalized_image(image_bytes()),"completed"))
    assert result.items[0].suggested_verdict=="uncertain" and result.items[0].knowledge_ids==["addition"]
    blocks=captured[0]["messages"][-1]["content"]
    assert blocks[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    result=asyncio.run(recognize_page(settings,normalized_image(image_bytes()),"blank"))
    assert result.items[0].student_answer=="" and result.items[0].suggested_verdict=="unanswered"


def test_pre_confirmation_tutoring_reduces_evidence_even_if_client_omits_flag(client,settings,monkeypatch):
    async def reply(*args):return {"reply":"先想想距离。","check_question":"距离为什么非负？","provider":"deepseek"}
    monkeypatch.setattr("app.materials.discuss_item",reply)
    value=recognized(client)
    item=value["items"][1]
    url=f"/api/v1/imports/{value['id']}/items/{item['id']}/tutor"
    assert client.post(url,json={"message":"帮我想一步"}).status_code==200
    body=confirmation(value)
    client.post(f"/api/v1/imports/{value['id']}/confirm",json=body)
    with connect(settings.database_path) as db:
        weight=db.execute("SELECT weight FROM import_evidence WHERE item_id=?",(item["id"],)).fetchone()[0]
    assert weight==.175
