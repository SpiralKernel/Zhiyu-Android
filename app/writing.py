"""Private per-attempt vector drafts. Saving a draft never creates grading evidence."""
import json
import os
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.db import connect
from app.identity import student_id

Coordinate = Annotated[float, Field(ge=0, le=1400, allow_inf_nan=False)]
Pressure = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]

class Stroke(BaseModel):
    model_config = ConfigDict(extra='forbid')
    width: float = Field(default=3, ge=1, le=12, allow_inf_nan=False)
    points: list[tuple[Coordinate, Coordinate, Pressure]] = Field(min_length=1, max_length=8000)

class Draft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    strokes: list[Stroke] = Field(default_factory=list, max_length=2000)

    @model_validator(mode='after')
    def bounded(self):
        if sum(len(s.points) for s in self.strokes) > 60000:
            raise ValueError('这张答题纸已满，请提交或清空后继续')
        if any(p[0] > 1000 for s in self.strokes for p in s.points):
            raise ValueError('笔迹超出纸面')
        return self


def create_router(settings):
    router = APIRouter(prefix='/api/v1/writing', tags=['答题纸'])

    def path_for(source, attempt):
        try:
            if str(uuid.UUID(attempt)) != attempt:
                raise ValueError()
        except ValueError:
            raise HTTPException(404, '作答不存在') from None
        table = 'bank_attempts' if source == 'bank' else 'attempts'
        with connect(settings.database_path) as db:
            if not db.execute(f'SELECT 1 FROM {table} WHERE id=? AND student_id=?', (attempt, student_id())).fetchone():
                raise HTTPException(404, '作答不存在')
        return settings.database_path.parent / 'writing' / student_id() / f'{source}-{attempt}.json'

    @router.get('/{source}/{attempt}')
    def read(source: Literal['bank','verified'], attempt: str):
        path = path_for(source, attempt)
        return json.loads(path.read_text()) if path.exists() else {'strokes': []}

    @router.put('/{source}/{attempt}')
    def write(source: Literal['bank','verified'], attempt: str, body: Draft):
        path = path_for(source, attempt)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        try:
            with temporary.open('x') as stream:
                os.chmod(temporary, 0o600)
                stream.write(body.model_dump_json())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        return {'saved': True}

    return router
