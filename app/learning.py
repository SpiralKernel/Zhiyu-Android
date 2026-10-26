import json
import uuid
import random
from datetime import datetime, timezone

from fastapi import HTTPException

from app.curriculum import NODES, NODE_MAP
from app.db import audit, dumps, now, replenish
from app.questions import grade, parse_number, public_question
from app.question_types import template_type_id, type_profile

from app.identity import student_id


def profile(db) -> dict:
    rows = {r["knowledge_id"]: dict(r) for r in db.execute("SELECT * FROM mastery WHERE student_id=?", (student_id(),))}
    imported = list(db.execute("SELECT e.*,i.data FROM import_evidence e JOIN import_items i ON e.item_id=i.id WHERE e.student_id=?", (student_id(),)))
    for evidence in imported:
        ids = json.loads(evidence["knowledge_ids"])
        for key in ids:
            state = rows.setdefault(key, {"success": 0, "failure": 0, "attempts": 0, "last_seen": None})
            state["success" if evidence["verdict"] == "correct" else "failure"] += evidence["weight"] / len(ids)
            state["attempts"] += 1
            state["imported_attempts"] = state.get("imported_attempts", 0) + 1
            state["last_seen"] = max(state.get("last_seen") or "", evidence["created_at"])
    knowledge = []
    for node in NODES:
        state = rows.get(node["id"], {})
        count = state.get("attempts", 0)
        probability = (1 + state.get("success", 0)) / (2 + state.get("success", 0) + state.get("failure", 0))
        status = "尚未练习" if count == 0 else "证据不足" if count < 3 else "掌握较稳" if probability >= .8 else "需要巩固" if probability < .6 else "正在进步"
        knowledge.append({**node, "attempts": count, "mastery": round(probability, 3) if count else None,
                          "status": status, "last_seen": state.get("last_seen"), "imported_attempts": state.get("imported_attempts", 0)})
    results = [json.loads(r["result"]) for r in db.execute(
        "SELECT result FROM attempts WHERE student_id=? AND status='submitted'", (student_id(),))]
    errors = {}
    for r in results:
        if r["error"]:
            e = r["error"]
            errors.setdefault(e["code"], {"code": e["code"], "feedback": e["feedback"], "count": 0})["count"] += 1
    for evidence in imported:
        if evidence["verdict"] == "incorrect":
            for key in json.loads(evidence["knowledge_ids"]):
                code = "imported:" + key
                errors.setdefault(code, {"code": code, "feedback": f"试卷核对发现：{NODE_MAP[key]['name']}需要进一步巩固", "count": 0})["count"] += 1
    return {"student_id": student_id(), "nickname": "学习者", "grade": 7, "term": 1,
            "knowledge": knowledge, "question_types": type_profile(db, student_id()), "completed": len(results) + len(imported),
            "practice_completed": len(results), "imported_completed": len(imported),
            "correct": sum(r["correct"] for r in results) + sum(e["verdict"] == "correct" for e in imported),
            "weak_patterns": sorted(errors.values(), key=lambda x: -x["count"])[:6],
            "assessment_note": "掌握度是启发式估计；不足 3 次不判定掌握。提示正确权重 0.35；已核对试卷权重 0.5，多知识点均分。空题、不确定题不计错；重复导入不重复计证据。"}


def recommend(db):
    states = {n["id"]: n for n in profile(db)["knowledge"]}
    external_weak = db.execute("SELECT knowledge_ids FROM import_evidence WHERE student_id=? AND verdict='incorrect' ORDER BY created_at DESC LIMIT 20", (student_id(),))
    for evidence in external_weak:
        for key in json.loads(evidence["knowledge_ids"]):
            if (states[key]["mastery"] or 0) >= .8:
                continue
            original = key
            while states[key]["prerequisites"]:
                missing = [p for p in states[key]["prerequisites"] if states[p]["attempts"] < 2 or (states[p]["mastery"] or 0) < .6]
                if not missing:
                    break
                key = missing[0]
            return key, f"试卷显示“{states[original]['name']}”需要巩固，先练习“{states[key]['name']}”。"
    eligible = [n for n in states.values() if all(
        states[p]["attempts"] >= 2 and (states[p]["mastery"] or 0) >= .6 for p in n["prerequisites"])]
    def priority(n):
        # 先做少量诊断，发现薄弱点时回补，间隔较久的点适当提前复习。
        age = 0
        if n["last_seen"]:
            age = min(30, (datetime.now(timezone.utc) - datetime.fromisoformat(n["last_seen"])).days)
        return (n["mastery"] if n["mastery"] is not None else .45) + min(n["attempts"], 8) * .025 - age * .005
    node = min(eligible or list(states.values()), key=priority)
    reason = "先做一道基础诊断，了解你的起点。" if node["attempts"] == 0 else "根据已有答题证据，继续巩固这个知识点。"
    return node["id"], reason


def get_attempt(db, attempt_id: str):
    row = db.execute("SELECT * FROM attempts WHERE id=? AND student_id=?", (attempt_id, student_id())).fetchone()
    if not row:
        raise HTTPException(404, "练习记录不存在")
    from app.training import get_plan
    training = db.execute('SELECT plan_id FROM training_items WHERE attempt_id=?', (attempt_id,)).fetchone()
    if training:
        get_plan(db, training['plan_id'])
    question = json.loads(db.execute("SELECT data FROM questions WHERE id=?", (row["question_id"],)).fetchone()[0])
    return row, question


def next_question(db, knowledge_id: str | None, difficulty: int | None = None, allow_challenge: bool = False, question_type_id: str | None = None):
    db.execute("BEGIN IMMEDIATE")
    reason = "你选择了专项练习。"
    if knowledge_id and knowledge_id not in NODE_MAP:
        raise HTTPException(404, "知识点不存在")
    active = db.execute("SELECT * FROM attempts WHERE student_id=? AND status='assigned'", (student_id(),)).fetchone()
    inactive={r[0] for r in db.execute("SELECT local_id FROM content_installed_items WHERE family='original' AND active=0 AND local_id LIKE 'remote:%'")}
    if active:
        row, q = get_attempt(db, active["id"])
        compatible = q['id'] not in inactive and (question_type_id or q.get('provenance',{}).get('family') != 'foundations')
        if compatible and (knowledge_id is None or q["knowledge_id"] == knowledge_id) and (difficulty is None or q["difficulty"]==difficulty) and (not question_type_id or template_type_id(q)==question_type_id):
            result=public_question(q);result["type_id"]=template_type_id(q)
            return {"attempt_id": row["id"], "question": result, "reason": "继续完成当前练习。", "hint_used": bool(row["hint_used"])}
        db.execute("UPDATE attempts SET status='skipped' WHERE id=?", (row["id"],))
    if not knowledge_id:
        knowledge_id, reason = recommend(db)
    replenish(db)
    selected_difficulty=(3 if question_type_id.startswith("challenge:") else None) if question_type_id else (difficulty or (3 if allow_challenge and random.random()<.15 else None))
    candidates = db.execute("""SELECT q.data FROM questions q WHERE q.knowledge_id=? ORDER BY
        (SELECT COUNT(*) FROM attempts a WHERE a.question_id=q.id AND a.student_id=?) ASC,
        q.created_at,q.id""", (knowledge_id, student_id()))
    candidates=[json.loads(r[0]) for r in candidates if json.loads(r[0])['id'] not in inactive]
    if not question_type_id:
        candidates=[q for q in candidates if q.get('provenance',{}).get('family')!='foundations']
    candidates=[q for q in candidates if (q["difficulty"]==selected_difficulty if selected_difficulty else q["difficulty"]<3) and (not question_type_id or template_type_id(q)==question_type_id)]
    if not candidates:
        raise HTTPException(404, "当前知识点或题型暂无所选难度的题目，请换一个范围")
    # 优先未做题；同一证据数量下随机选择，避免每人固定顺序。
    counts={r["question_id"]:r["n"] for r in db.execute("SELECT question_id,COUNT(*) n FROM attempts WHERE student_id=? GROUP BY question_id",(student_id(),))}
    least=min(counts.get(q["id"],0) for q in candidates)
    q=random.choice([q for q in candidates if counts.get(q["id"],0)==least])
    if q["difficulty"]==3:reason+=" 这一题是随机挑战变式，会单独记录题型表现。"
    attempt_id = str(uuid.uuid4())
    db.execute("INSERT INTO attempts(id,student_id,question_id,assigned_at) VALUES(?,?,?,?)",
               (attempt_id, student_id(), q["id"], now()))
    result=public_question(q);result["type_id"]=template_type_id(q)
    return {"attempt_id": attempt_id, "question": result, "reason": reason, "hint_used": False}


def submit(db, attempt_id: str, answer: str):
    db.execute("BEGIN IMMEDIATE")
    row, q = get_attempt(db, attempt_id)
    if row["status"] == "submitted":
        from app.answers import equivalent
        if not equivalent(q, row['answer'], answer):
            raise HTTPException(409, "这道练习已经提交，请开始下一题")
        return json.loads(row["result"])
    if row["status"] != "assigned":
        raise HTTPException(409, "这道练习已经跳过")
    return record_answer(db, attempt_id, q, answer, bool(row["hint_used"]))


def record_answer(db, attempt_id, q, answer, assisted=False):
    """调用者持有事务及作答行；诊断与普通练习共用判分、去重和证据写入。"""
    from app.training import grading_context
    training = grading_context(db, attempt_id, assisted)
    result = grade(q, answer)
    weight = .35 if assisted and result["correct"] else 1.0
    # 同一道题的重复作答保留记录，但不重复增加掌握证据。
    repeated = db.execute("SELECT 1 FROM attempts WHERE student_id=? AND question_id=? AND status='submitted' AND id!=? LIMIT 1",
                          (student_id(), q["id"], attempt_id)).fetchone() is not None
    result.update(assisted=assisted, evidence_weight=0 if repeated else weight,
                  knowledge_id=q["knowledge_id"], question_type_id=template_type_id(q), repeated_question=repeated)
    if training:
        result.update(training)
        if not training['independent_eligible']:
            result['evidence_weight'] = 0
    db.execute("UPDATE attempts SET status='submitted',answer=?,result=?,submitted_at=? WHERE id=?",
               (answer, dumps(result), now(), attempt_id))
    if not repeated and (not training or result['evidence_weight'] > 0):
        db.execute("""INSERT INTO mastery(student_id,knowledge_id,success,failure,attempts,last_seen) VALUES(?,?,?,?,1,?)
            ON CONFLICT(student_id,knowledge_id) DO UPDATE SET
            success=success+excluded.success,failure=failure+excluded.failure,attempts=attempts+1,last_seen=excluded.last_seen""",
                   (student_id(), q["knowledge_id"], weight if result["correct"] else 0, 0 if result["correct"] else 1, now()))
    audit(db, "attempt_submitted", {"attempt_id": attempt_id, "correct": result["correct"], "weight": result["evidence_weight"]})
    replenish(db)
    return result


def history(db):
    rows = db.execute("""SELECT a.id,a.answer,a.result,a.submitted_at,q.data FROM attempts a
        JOIN questions q ON a.question_id=q.id WHERE student_id=? AND status='submitted'
        ORDER BY submitted_at DESC LIMIT 50""", (student_id(),))
    return [{"attempt_id": r["id"], "answer": r["answer"], "result": json.loads(r["result"]),
             "question": public_question(json.loads(r["data"])), "submitted_at": r["submitted_at"]} for r in rows]
