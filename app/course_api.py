"""课程目标与学习进度接口，供网页与安卓端共同使用。"""
from fastapi import APIRouter, Query

from app import courses, preferences
from app.db import connect


def create_router(settings):
    router = APIRouter(prefix="/api/v1/courses", tags=["阶段学习目标"])

    @router.get("/preferences")
    def current_preferences():
        with connect(settings.database_path) as db:
            return preferences.get(db)

    @router.post("/preferences")
    def save_preferences(body: preferences.LearningPreferences):
        with connect(settings.database_path) as db:
            return preferences.save(db, body)

    @router.get("")
    def catalog(subject: str = Query("math", max_length=30)):
        with connect(settings.database_path) as db:
            return {**courses.catalog(subject), "setting": courses.get_setting(db, subject)}

    @router.post("/setting")
    def setting(body: courses.CourseSetting):
        with connect(settings.database_path) as db:
            return courses.set_setting(db, body)

    @router.get("/report")
    def report(subject: str = Query("math", max_length=30), book_id: str | None = Query(None, max_length=80),
               unit_id: str | None = Query(None, max_length=100)):
        with connect(settings.database_path) as db:
            return courses.report(db, subject, book_id, unit_id)

    return router
