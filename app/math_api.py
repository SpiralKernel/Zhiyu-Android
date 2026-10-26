"""七上数学题型地图、覆盖与诊断接口。"""
import json
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app import learning, math_learning
from app.db import connect
from app.math_catalog import TYPE_MAP


class Start(BaseModel):
    size: int = Field(default=10, ge=1, le=14)
    unit_id: str | None = Field(default=None, max_length=100)


class Answer(BaseModel):
    position: int = Field(ge=0, le=13)
    answer: str = Field(min_length=1, max_length=64)


class Practice(BaseModel):
    type_id: str = Field(max_length=100)


def create_router(settings):
    router = APIRouter(prefix="/api/v1/math", tags=["七上数学诊断"])

    @router.get("/coverage")
    def coverage(unit_id: str | None = Query(None, max_length=100)):
        with connect(settings.database_path) as db:
            return math_learning.coverage(db, unit_id)

    @router.get("/diagnostics")
    def sessions():
        with connect(settings.database_path) as db:
            return {"items": [{"id":r["id"],"status":r["status"],"created_at":r["created_at"],
                "unit_id":json.loads(r["data"])["unit_id"]} for r in db.execute(
                "SELECT * FROM math_diagnostics WHERE student_id=current_student() ORDER BY created_at DESC,id DESC LIMIT 20")]}

    @router.post("/diagnostics")
    def start(body: Start):
        with connect(settings.database_path) as db:
            return math_learning.start(db, body.size, body.unit_id)

    @router.get("/diagnostics/{session_id}")
    def session(session_id: str):
        with connect(settings.database_path) as db:
            return math_learning.session_view(db, session_id)

    @router.post("/diagnostics/{session_id}/answer")
    def answer(session_id: str, body: Answer):
        with connect(settings.database_path) as db:
            return math_learning.answer(db, session_id, body.position, body.answer)

    @router.post("/diagnostics/{session_id}/cancel")
    def cancel(session_id: str):
        with connect(settings.database_path) as db:
            return math_learning.cancel(db, session_id)

    @router.post("/practice")
    def practice(body: Practice):
        t = TYPE_MAP.get(body.type_id)
        if not t:
            raise HTTPException(422,"请选择七上数学已有题型")
        from app.foundations import CATALOG
        foundation = body.type_id.removeprefix('m7a:')
        if not t["legacy_type_ids"] and foundation not in CATALOG:
            raise HTTPException(404,"该题型还缺核验题，暂不能开始专项练习")
        legacy_id = t["legacy_type_ids"][0] if t['legacy_type_ids'] else body.type_id
        key = legacy_id.split(":")[1] if t['legacy_type_ids'] else CATALOG[foundation][0]
        with connect(settings.database_path) as db:
            return learning.next_question(db,key,question_type_id=legacy_id)

    return router
