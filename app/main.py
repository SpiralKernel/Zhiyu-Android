import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import ROOT, Settings
from app.curriculum import NODES, UNITS, VERSION
from app.db import audit, connect, dumps, initialize, now
from app.learning import get_attempt, history, next_question, profile, recommend, submit
from app.tutor import respond
from app import ai_policy, materials
from app.question_types import template_type_id
from app.bank_api import create_router
from app.course_api import create_router as create_course_router
from app.math_api import create_router as create_math_router
from app import courses, auth
from app.identity import current, book_id, scope


class PracticeRequest(BaseModel):
    knowledge_id: str | None = Field(default=None, max_length=50)
    difficulty: int | None = Field(default=None, ge=1, le=3)
    allow_challenge: bool = False
    question_type_id: str | None = Field(default=None,max_length=80)


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=64)


class TutorRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)


def create_app(settings: Settings | None = None):
    from app.app_settings import RuntimeSettings, active_options, request_ai
    settings = RuntimeSettings(settings or Settings())

    from app.bank_ingest import IngestService
    ingest_service = IngestService(settings)

    @asynccontextmanager
    async def lifespan(app):
        initialize(settings.database_path, with_diagnostic_core=settings.diagnostic_core_enabled)
        with connect(settings.database_path) as db:
            db.execute("UPDATE imports SET status='failed',error='服务重启中断了识别，请重试。' WHERE status='processing'")
            for row in db.execute("SELECT attempt_id,data FROM bank_reviews WHERE json_extract(data,'$.status')='processing'").fetchall():
                value=json.loads(row["data"])
                value.update(status="failed",error="服务重启中断了评阅，请重新提交解答。")
                db.execute("UPDATE bank_reviews SET data=? WHERE attempt_id=?",(dumps(value),row["attempt_id"]))
        ingest_service.recover()
        try:
            yield
        finally:
            await ingest_service.close()

    app = FastAPI(title="知域 · 中学数理学习", version="0.8.1", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(auth.create_router(settings))
    from app.study import create_router as study_router
    app.include_router(study_router(settings))
    from app.training import create_router as training_router
    app.include_router(training_router(settings))
    from app.teacher import create_router as teacher_router
    from app.reports import create_router as reports_router
    app.include_router(teacher_router(settings))
    app.include_router(reports_router(settings))
    app.include_router(create_router(settings))
    app.include_router(create_course_router(settings))
    app.include_router(create_math_router(settings))
    from app.admin import create_router as admin_router
    from app.content import create_router as content_router
    app.include_router(admin_router(settings))
    from app.calibration import create_router as calibration_router
    app.include_router(calibration_router(settings))
    from app.bank_ingest import create_router as ingest_router
    app.include_router(ingest_router(settings, ingest_service))
    app.include_router(content_router(settings))
    from app.app_settings import create_router as app_settings_router
    app.include_router(app_settings_router(settings))
    from app.writing import create_router as writing_router
    app.include_router(writing_router(settings))
    tutor_slots = asyncio.Semaphore(1)
    vision_slots = asyncio.Semaphore(1)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.middleware("http")
    async def security_headers(request, call_next):
        if request.url.path.startswith(('/api/v1/admin/calibration','/api/v1/admin/ingest')) and request.method=='POST':
            try:length=int(request.headers.get('content-length','0'))
            except ValueError:return JSONResponse(status_code=400,content={'detail':'无效的请求长度'})
            if length>25*1024*1024:return JSONResponse(status_code=413,content={'detail':'标定任务或结果最多25MiB，请拆批'})
        if (request.url.path == "/api/v1/imports" or request.url.path.endswith(("/assess","/photo"))) and request.method == "POST":
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "无效的上传长度"})
            if length > materials.MAX_TOTAL + 1024 * 1024:
                return JSONResponse(status_code=413, content={"detail": "每次上传总大小不能超过 40MB"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.middleware("http")
    async def student_identity(request, call_next):
        if settings.mobile_mode and settings.mobile_token:
            import hmac
            if not hmac.compare_digest(request.cookies.get('teacher_device_token',''),settings.mobile_token):
                return JSONResponse(status_code=403,content={'detail':'请从应用内打开'})
        value = None
        if settings.auth_required and request.url.path.startswith('/api/'):
            if request.method not in {'GET','HEAD','OPTIONS'}:
                origin = request.headers.get('origin')
                if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
                    return JSONResponse(status_code=403,headers={"Cache-Control":"no-store"},content={'detail':'请从本站提交请求'})
            with connect(settings.database_path) as db:
                value = auth.identity(db,request.cookies.get(auth.COOKIE))
            public = {'/api/v1/health','/api/v1/auth/session','/api/v1/auth/register','/api/v1/auth/login','/api/v1/auth/logout'}
            public |= {'/api/v1/content/feed/manifest','/api/v1/content/feed/package'}
            if not value and request.url.path not in public:
                return JSONResponse(status_code=401,content={'detail':'请先登录自己的学习账号'},headers={'Cache-Control':'no-store'})
        token = current.set(value)
        ai_token = request_ai.set(active_options(settings) if value or not settings.auth_required else None)
        try:
            path = request.url.path
            if value:
                # 旧诊断/百分比接口作为维护能力保留；学生统一走 study 的证据规则。
                if path in {'/api/v1/student','/api/v1/history','/api/v1/bank/profile','/api/v1/bank/export','/api/v1/courses/report','/api/v1/bank/plan'} or path.startswith('/api/v1/math/') or path.endswith('/tutor'):
                    return JSONResponse(status_code=403,headers={"Cache-Control":"no-store"},content={'detail':'请使用题库与 AI补强学习入口'})
                if book_id() != 'math-7-1' and any(path.startswith('/api/v1/'+prefix) for prefix in ('practice','attempts','curriculum')):
                    return JSONResponse(status_code=403,headers={"Cache-Control":"no-store"},content={'detail':'该旧接口仅支持七年级上册，请使用当前阶段题库'})
            return await call_next(request)
        finally:
            request_ai.reset(ai_token)
            current.reset(token)

    @app.get("/api/v1/health")
    def health():
        with connect(settings.database_path) as db:
            count = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        return {"status": "ok", "ai_configured": bool(settings.deepseek_api_key),
                "provider": settings.ai_provider,
                "model": settings.deepseek_model, "question_count": count,
                "curriculum_version": VERSION, "mode": "student_accounts" if settings.auth_required else "local_single_student"}

    @app.post("/api/v1/imports", status_code=201)
    async def upload_material(files: list[UploadFile] = File(...), mode: str = Form("completed"),
                              page_start: int = Form(1), page_end: int = Form(0)):
        if mode not in {"completed", "blank"} or page_start < 1 or page_end < 0:
            raise HTTPException(422, "请选择材料类型和有效页码")
        if not 1 <= len(files) <= 8:
            raise HTTPException(422, "每次请选择 1—8 个文件")
        content, total = [], 0
        for file in files:
            value = await file.read(materials.MAX_FILE + 1)
            if len(value) > materials.MAX_FILE:
                raise HTTPException(413, "单个文件不能超过 20MB")
            total += len(value)
            if total > materials.MAX_TOTAL:
                raise HTTPException(413, "每次上传总大小不能超过 40MB")
            content.append((file.filename or "上传文件", value))
        import_id = await run_in_threadpool(materials.create_import, settings, content, mode, page_start, page_end)
        with connect(settings.database_path) as db:
            return materials.get_import(db, import_id)

    @app.get("/api/v1/imports")
    def list_materials():
        with connect(settings.database_path) as db:
            rows = db.execute("SELECT id,title,mode,status,page_count,error,created_at FROM imports WHERE student_id=current_student() AND book_id=? ORDER BY created_at DESC LIMIT 100",(book_id(),))
            return {"items": [dict(r) for r in rows]}

    @app.get("/api/v1/imports/{import_id}")
    def get_material(import_id: str):
        with connect(settings.database_path) as db:
            return materials.get_import(db, import_id)

    @app.get("/api/v1/imports/{import_id}/pages/{page_number}")
    def material_page(import_id: str, page_number: int):
        with connect(settings.database_path) as db:
            materials.require_import(db, import_id)
            row = db.execute("SELECT file_name FROM import_pages WHERE import_id=? AND page_number=?", (import_id, page_number)).fetchone()
            if not row:
                raise HTTPException(404, "页面不存在")
        return FileResponse(materials.storage(settings) / import_id / row["file_name"], media_type="image/jpeg")

    @app.post("/api/v1/imports/{import_id}/recognize", status_code=202)
    def recognize_material(import_id: str, background_tasks: BackgroundTasks):
        if not settings.deepseek_api_key:
            raise HTTPException(503, "请先在服务端配置 AI Key，再进行识图")
        with connect(settings.database_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = materials.require_import(db, import_id)
            if row["status"] not in {"uploaded", "failed"}:
                raise HTTPException(409, "当前材料正在识别或已经识别，请查看结果")
            if db.execute("SELECT COUNT(*) FROM imports WHERE status='processing'").fetchone()[0] >= 2:
                raise HTTPException(429, "已有两份材料正在识别，请等待完成")
            db.execute("UPDATE imports SET status='processing',error=NULL WHERE id=?", (import_id,))
        background_tasks.add_task(materials.process_import, settings, import_id, vision_slots)
        return {"id": import_id, "status": "processing"}

    @app.post("/api/v1/imports/{import_id}/confirm")
    def confirm_material(import_id: str, body: materials.Confirmation):
        with connect(settings.database_path) as db:
            return materials.confirm_import(db, import_id, body)

    @app.post("/api/v1/imports/{import_id}/items/{item_id}/tutor")
    async def material_tutor(import_id: str, item_id: str, body: materials.MaterialMessage):
        if not body.message.strip():
            raise HTTPException(422, "请输入想讨论的问题")
        async with tutor_slots:
            with connect(settings.database_path) as db:
                db.execute("BEGIN IMMEDIATE")
                row = materials.require_import(db, import_id)
                item_row = db.execute("SELECT data FROM import_items WHERE import_id=? AND id=?", (import_id, item_id)).fetchone()
                if not item_row:
                    raise HTTPException(404, "题目不存在")
                item = json.loads(item_row["data"])
                previous = list(db.execute("SELECT * FROM import_messages WHERE item_id=? ORDER BY id", (item_id,)))
                if len(previous) >= 12:
                    raise HTTPException(429, "本题已讨论 12 轮，请休息一下")
                student_profile=profile(db)
                summary = {"knowledge":[{k: n[k] for k in ("id", "attempts", "mastery", "status")} for n in student_profile["knowledge"] if n["id"] in item["knowledge_ids"]],
                           "question_type":[{k:t[k] for k in ("name","attempts","mastery","status")} for t in student_profile["question_types"] if t["id"]==item.get("question_type_id")]}
                # 核对前讨论同样算辅助，最终确认时降低正确证据权重。
                if row["status"] != "confirmed":
                    item["assisted"] = True
                    db.execute("UPDATE import_items SET data=? WHERE id=?", (dumps(item), item_id))
            result = await materials.discuss_item(settings, item, body.message, previous, summary, row["status"] == "confirmed")
            with connect(settings.database_path) as db:
                db.execute("INSERT INTO import_messages(item_id,user_message,response,created_at) VALUES(?,?,?,?)", (item_id, body.message, dumps(result), now()))
            return result

    @app.get("/api/v1/imports/{import_id}/items/{item_id}/messages")
    def material_messages(import_id: str, item_id: str):
        with connect(settings.database_path) as db:
            materials.require_import(db, import_id)
            if not db.execute("SELECT 1 FROM import_items WHERE import_id=? AND id=?", (import_id, item_id)).fetchone():
                raise HTTPException(404, "题目不存在")
            return {"items": [{"message": r["user_message"], "response": json.loads(r["response"])} for r in db.execute("SELECT * FROM import_messages WHERE item_id=? ORDER BY id", (item_id,))]}

    @app.delete("/api/v1/imports/{import_id}")
    def delete_material(import_id: str):
        with connect(settings.database_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = materials.require_import(db, import_id)
            if row["status"] == "processing":
                raise HTTPException(409, "正在识别的材料暂不能删除，请等待完成")
            db.execute("DELETE FROM import_messages WHERE item_id IN (SELECT id FROM import_items WHERE import_id=?)", (import_id,))
            db.execute("DELETE FROM learning_observations WHERE student_id=current_student() AND json_extract(data,'$.source') LIKE ?",("import:"+import_id+":%",))
            for table in ("import_evidence", "import_items", "import_pages", "imports"):
                db.execute(f"DELETE FROM {table} WHERE {'id' if table == 'imports' else 'import_id'}=?", (import_id,))
            audit(db, "material_deleted", {"import_id": import_id})
        import shutil
        shutil.rmtree(materials.storage(settings) / import_id, ignore_errors=True)
        return {"deleted": True}

    @app.get("/api/v1/curriculum")
    def curriculum():
        return {"version": VERSION, "grade": 7, "term": 1, "units": UNITS, "knowledge": NODES,
                "note": "项目自编七年级上册起步范围；非完整教材，章节顺序可按教材版本调整。"}

    @app.get("/api/v1/student")
    def student():
        with connect(settings.database_path) as db:
            result = profile(db)
            knowledge_id, reason = recommend(db)
            bank_summary=[dict(r) for r in db.execute("SELECT q.subject,q.stage,COUNT(*) completed,SUM(json_extract(a.result,'$.correct')) correct FROM bank_attempts a JOIN bank_questions q ON q.id=a.question_id WHERE a.student_id=current_student() AND a.status='submitted' GROUP BY q.subject,q.stage")]
        return {**result, "recommendation": {"knowledge_id": knowledge_id, "reason": reason},"bank_summary":bank_summary,
                "all_completed":result["completed"]+sum(s["completed"] for s in bank_summary),"all_correct":result["correct"]+sum(s["correct"] or 0 for s in bank_summary)}

    @app.post("/api/v1/practice/next")
    def practice(body: PracticeRequest):
        with connect(settings.database_path) as db:
            return next_question(db, body.knowledge_id, body.difficulty, body.allow_challenge, body.question_type_id)

    @app.post("/api/v1/attempts/{attempt_id}/answer")
    def answer(attempt_id: str, body: AnswerRequest):
        with connect(settings.database_path) as db:
            return submit(db, attempt_id, body.answer)

    @app.post("/api/v1/attempts/{attempt_id}/hint")
    def hint(attempt_id: str):
        with connect(settings.database_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row, q = get_attempt(db, attempt_id)
            if row["status"] != "assigned":
                raise HTTPException(409, "请在作答前使用提示")
            db.execute("UPDATE attempts SET hint_used=1 WHERE id=?", (attempt_id,))
            return {"hint": q["hint"], "assisted": True}

    @app.post("/api/v1/attempts/{attempt_id}/tutor")
    async def tutor(attempt_id: str, body: TutorRequest):
        if not body.message.strip():
            raise HTTPException(422, "请输入想讨论的问题")
        async with tutor_slots:
            with connect(settings.database_path) as db:
                db.execute("BEGIN IMMEDIATE")
                row, q = get_attempt(db, attempt_id)
                if row["status"] == "skipped":
                    raise HTTPException(409, "这道练习已经跳过")
                previous = list(db.execute("SELECT user_message,response FROM tutor_messages WHERE attempt_id=? ORDER BY id", (attempt_id,)))
                if len(previous) >= 12:
                    raise HTTPException(429, "这道题已讨论 12 轮，建议休息一下或开始下一题")
                if row["status"] == "assigned" and not ai_policy.boundary_reason(body.message):
                    db.execute("UPDATE attempts SET hint_used=1 WHERE id=?", (attempt_id,))
                student_profile=profile(db)
                state = next(n for n in student_profile["knowledge"] if n["id"] == q["knowledge_id"])
                summary = {k: state[k] for k in ("attempts", "mastery", "status")}
                relevant_type=next((t for t in student_profile["question_types"] if t["id"]==template_type_id(q)),None)
                summary["question_type"]={k:relevant_type[k] for k in ("name","attempts","mastery","status")} if relevant_type else None
                summary["difficulty"]=q["difficulty"]
            with connect(settings.database_path) as db:
                q["course_context"] = courses.context(db, "math", q)
            result = await respond(settings, q, body.message, summary, previous, submitted=row["status"] == "submitted")
            with connect(settings.database_path) as db:
                db.execute("INSERT INTO tutor_messages(attempt_id,user_message,response,created_at) VALUES(?,?,?,?)",
                           (attempt_id, body.message, dumps(result), now()))
                audit(db, "tutor_response", {"attempt_id": attempt_id, "provider": result["provider"]})
            return result

    @app.get("/api/v1/history")
    def attempts():
        with connect(settings.database_path) as db:
            return {"items": history(db)}

    app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "web/index.html")

    @app.get('/admin', include_in_schema=False)
    def admin_page():
        return FileResponse(ROOT / 'web/admin.html')

    return app


app = create_app()
