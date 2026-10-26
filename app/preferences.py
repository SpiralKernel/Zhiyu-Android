"""学生当前学习范围及练习偏好；各科学期进度仍由 courses 管理。"""
import json

from app import courses
from app.bank import SUBJECTS
from app.course_catalog import BOOK_MAP, UNITS
from app.db import audit, dumps


class LearningPreferences(courses.CourseSetting):
    limit_course: bool = True
    allow_challenge: bool = True


def get(db):
    from app.identity import scope, book_id
    if scope():
        book = BOOK_MAP[book_id()]
        return {"subject":"math","book_id":book_id(),"unit_id":None,"limit_course":True,"allow_challenge":True,
                "scope":{"subject_name":"数学","stage_label":f"{book['grade']}年级 · {'上学期' if book['term']==1 else '下学期'}"}}
    row = db.execute("SELECT data FROM student_preferences WHERE student_id=current_student()").fetchone()
    value = json.loads(row[0]) if row else {"subject": "math", "limit_course": True, "allow_challenge": True}
    value = {**value, **courses.get_setting(db, value["subject"])}
    book = BOOK_MAP[value["book_id"]]
    return {**value, "scope": {"subject_name": SUBJECTS[value["subject"]],
        "stage_label": f"{book['grade']}年级 · {'上学期' if book['term'] == 1 else '下学期'}",
        "unit_name": UNITS[value["unit_id"]]["name"] if value["unit_id"] else "整册 / 本学期",
        "edition": book["edition"], "scope_note": book["scope_note"]}}


def save(db, body):
    courses.validate_scope(body.subject, body.book_id, body.unit_id)
    db.execute("BEGIN IMMEDIATE")
    courses.set_setting(db, courses.CourseSetting(subject=body.subject, book_id=body.book_id, unit_id=body.unit_id))
    db.execute("INSERT INTO student_preferences VALUES(current_student(),?) ON CONFLICT(student_id) DO UPDATE SET data=excluded.data",
               (dumps({"subject": body.subject, "limit_course": body.limit_course, "allow_challenge": body.allow_challenge}),))
    audit(db, "learning_preferences_changed", body.model_dump())
    return get(db)
