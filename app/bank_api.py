"""供网页与未来安卓客户端复用的全科题库接口。"""
import asyncio
import json

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import ai_policy, bank, bank_ai, courses
from app.db import connect, dumps, now
from app.materials import MAX_FILE, MAX_TOTAL
from app.identity import subject_id, stage_id


class Answer(BaseModel):
    answer: str = Field(min_length=1, max_length=40)


class Message(BaseModel):
    message: str = Field(min_length=1, max_length=1600)


def create_router(settings):
    router = APIRouter(prefix="/api/v1/bank", tags=["全科题库"])
    assessment_slots = asyncio.Semaphore(1)
    tutor_slots = asyncio.Semaphore(1)

    @router.get("/catalog")
    def catalog():
        with connect(settings.database_path) as db:
            return bank.catalog(db)

    @router.get("/export")
    def export():
        with connect(settings.database_path) as db:
            attempts=[]
            for row in db.execute("SELECT * FROM bank_attempts WHERE student_id=current_student() AND status='submitted' ORDER BY submitted_at"):
                value=dict(row)
                value["result"]=json.loads(value["result"])
                q=json.loads(db.execute("SELECT data FROM bank_questions WHERE id=?",(value["question_id"],)).fetchone()[0])
                value["question"]=bank.public(q)
                review=db.execute("SELECT data FROM bank_reviews WHERE attempt_id=?",(value["id"],)).fetchone()
                value["review"]=json.loads(review[0]) if review else None
                attempts.append(value)
            return {"attempts":attempts,"note":"图片文件不包含在 JSON 中，请使用完整备份保存手写照片。"}

    @router.get("/tags")
    def tags(subject: str | None = None, stage: str | None = None, query: str = Query("", max_length=200)):
        with connect(settings.database_path) as db:
            return bank.tags(db, subject or subject_id(), stage or stage_id(), query)

    @router.get("/questions")
    def questions(subject: str | None = None, stage: str | None = None, tag_id: str | None = None, difficulty: int | None = Query(None, ge=1, le=3),
                  answer_mode: str | None = None, source_id: str | None = None, query: str = Query("", max_length=200),
                  course_book_id: str | None = Query(None, max_length=80), course_unit_id: str | None = Query(None, max_length=100),
                  limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0, le=100000)):
        selection = bank.Selection(subject=subject or subject_id(), stage=stage or stage_id(), tag_id=tag_id, difficulty=difficulty, answer_mode=answer_mode, source_id=source_id,
                                   course_book_id=course_book_id, course_unit_id=course_unit_id)
        with connect(settings.database_path) as db:
            return bank.search(db, selection, query, limit, offset)

    @router.get("/profile")
    def profile(subject: str | None = None, stage: str = "junior"):
        with connect(settings.database_path) as db:
            return bank.profile(db, subject or subject_id(), stage)

    @router.post("/next")
    def practice(body: bank.Selection):
        with connect(settings.database_path) as db:
            return bank.next_question(db, body)

    @router.post("/plan")
    async def plan(body: bank.Selection):
        # 仅发送标签与学习证据供模型挑选，筛选和分配仍由后端执行。
        with connect(settings.database_path) as db:
            bank.clauses(body)
            available=bank.tags(db,body.subject,body.stage,limit=200)["items"]
            summary=bank.profile(db,body.subject,body.stage)
            weak=summary["tags"][:20]
            candidates={t["id"]:t for t in available}
            for t in weak:
                row=db.execute("SELECT * FROM bank_taxonomy WHERE id=?",(t["id"],)).fetchone()
                if row:candidates[t["id"]]=dict(row)
            where,args=bank.clauses(body,playable=True)
            eligible={r[0] for r in db.execute("SELECT DISTINCT qt.tag_id FROM bank_question_tags qt JOIN bank_questions q ON qt.question_id=q.id WHERE "+where,args)}
            if body.tag_id:
                row=db.execute("SELECT * FROM bank_taxonomy WHERE id=?",(body.tag_id,)).fetchone()
                if row:candidates[row["id"]]=dict(row)
            candidates={key:t for key,t in candidates.items() if key in eligible}
            if body.tag_id:
                candidates={key:t for key,t in candidates.items() if key==body.tag_id}
            if not candidates:
                raise HTTPException(404,"当前范围没有可选择的标签")
            course_context = courses.context(db, body.subject, book_id=body.course_book_id, unit_id=body.course_unit_id) if body.stage in {"junior","senior"} else None
        prompt="根据中学生当前科目与教材范围的有效作答证据，从给定标签目录选出下一步应练的细分知识点或题型。结合课程阶段要求与前置知识，先诊断未测目标，再补有证据的漏洞。待诊断不等于不会；缺题目标不能伪装成已掌握。少量证据只做诊断，不夸大掌握。必须返回目录中真实tag_id，不能创建标签或题目。输出JSON {tag_id:目录ID,difficulty:1到3,reason:简短中文推荐理由}。"
        context={"subject":body.subject,"course_requirements":course_context,"evidence":weak,"tags":[{k:t[k] for k in ("id","kind","label")} for t in candidates.values()]}
        async with tutor_slots:
            choice=await bank_ai.request_json(settings,ai_policy.messages(prompt,context,content="请选择下一步练习。"),bank_ai.Plan)
        if choice.tag_id not in candidates:
            raise HTTPException(502,"模型选择的标签不在目录内，请重试或手动选择")
        selection=body.model_copy(update={"tag_id":choice.tag_id,"difficulty":body.difficulty or choice.difficulty})
        with connect(settings.database_path) as db:
            try:
                result=bank.next_question(db,selection)
            except HTTPException as exc:
                if exc.status_code!=404 or body.difficulty:raise
                db.rollback()
                result=bank.next_question(db,selection.model_copy(update={"difficulty":None}))
        return {**result,"recommendation":choice.model_dump()}

    @router.get("/attempts/{attempt_id}")
    def attempt(attempt_id: str):
        with connect(settings.database_path) as db:
            row, q = bank.get_attempt(db, attempt_id)
            review = db.execute("SELECT data FROM bank_reviews WHERE attempt_id=?", (attempt_id,)).fetchone()
            messages = [{"message": r["user_message"], "response": json.loads(r["response"])} for r in db.execute("SELECT * FROM bank_messages WHERE attempt_id=? ORDER BY id", (attempt_id,))]
            return {"attempt_id": attempt_id, "question": bank.public(q), "status": row["status"],
                    "result": json.loads(row["result"]) if row["result"] else None,
                    "review": json.loads(review[0]) if review else None, "messages": messages}

    @router.post("/attempts/{attempt_id}/answer")
    def answer(attempt_id: str, body: Answer):
        with connect(settings.database_path) as db:
            return bank.answer_choice(db, attempt_id, body.answer)

    @router.post("/attempts/{attempt_id}/assess")
    async def assess(attempt_id: str, answer: str = Form("", max_length=12000), files: list[UploadFile] | None = File(None)):
        if not settings.deepseek_api_key:
            raise HTTPException(503, "请先在服务端配置 AI Key")
        if len(files or []) > 4:
            raise HTTPException(422, "每题最多上传 4 张解答图片")
        contents, total = [], 0
        for file in files or []:
            content = await file.read(MAX_FILE + 1)
            total += len(content)
            if len(content) > MAX_FILE or total > MAX_TOTAL:
                raise HTTPException(413, "单张图片最多20MB，合计最多40MB")
            contents.append(content)
        async with assessment_slots:
            return await bank_ai.assess(settings, attempt_id, answer, contents)

    @router.post("/attempts/{attempt_id}/confirm")
    def confirm(attempt_id: str, body: bank_ai.Confirmation):
        with connect(settings.database_path) as db:
            return bank_ai.confirm(db, attempt_id, body)

    @router.get("/attempts/{attempt_id}/pages/{file_name}")
    def page(attempt_id: str, file_name: str):
        with connect(settings.database_path) as db:
            bank.get_attempt(db, attempt_id)
            row = db.execute("SELECT data FROM bank_reviews WHERE attempt_id=?", (attempt_id,)).fetchone()
            if not row or file_name not in json.loads(row[0]).get("files", []):
                raise HTTPException(404, "解答图片不存在")
        return FileResponse(bank_ai.answer_storage(settings) / attempt_id / file_name, media_type="image/jpeg")

    @router.post("/attempts/{attempt_id}/tutor")
    async def tutor(attempt_id: str, body: Message):
        if not body.message.strip():
            raise HTTPException(422, "请输入想讨论的问题")
        async with tutor_slots:
            with connect(settings.database_path) as db:
                db.execute("BEGIN IMMEDIATE")
                row, q = bank.get_attempt(db, attempt_id)
                if row["status"] == "skipped":
                    raise HTTPException(409, "这道题已切换，请在当前作答中提问")
                previous = list(db.execute("SELECT * FROM bank_messages WHERE attempt_id=? ORDER BY id", (attempt_id,)))
                if len(previous) >= 12:
                    raise HTTPException(429, "本题已讨论12轮，请先整理思路")
                if row["status"] == "assigned" and not ai_policy.boundary_reason(body.message):
                    db.execute("UPDATE bank_attempts SET assisted=1 WHERE id=?", (attempt_id,))
                related = {t["id"] for t in q["tags"]}
                summary = [t for t in bank.profile(db, q["subject"], q["stage"])["tags"] if t["id"] in related]
                q["course_context"] = courses.context(db, q["subject"], q) if q["stage"] in {"junior","senior"} else None
            result = await bank_ai.tutor(settings, q, body.message, previous, row["status"] == "submitted", summary)
            with connect(settings.database_path) as db:
                db.execute("INSERT INTO bank_messages(attempt_id,user_message,response,created_at) VALUES(?,?,?,?)", (attempt_id, body.message, dumps(result), now()))
            return result

    return router
