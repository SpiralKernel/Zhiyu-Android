"""Server-owned training plans. Models select a bounded plan, never answers or mastery."""
import asyncio
import hashlib
import json
import random
import uuid
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import ai_policy, bank, bank_ai
from app.db import connect, dumps, now, replenish
from app.identity import book_id
from app.math_learning import practice_pool
from app.questions import public_question


class Proposal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type_id: str = Field(max_length=100)
    difficulty: int = Field(ge=1, le=2)
    count: Literal[3] = 3
    reason: str = Field(min_length=1, max_length=500)


class RequestPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type_id: str | None = Field(default=None, max_length=100)


def digest(q):
    return hashlib.sha256(json.dumps(q, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def get_plan(db, pid):
    row = db.execute('SELECT * FROM training_plans WHERE id=? AND student_id=current_student() AND book_id=?',
                     (pid, book_id())).fetchone()
    if not row:
        raise HTTPException(404, '当前阶段的训练计划不存在')
    return row


def item_result(db, item):
    if not item['attempt_id']:
        return None
    table = 'attempts' if item['source'] == 'verified' else 'bank_attempts'
    row = db.execute(f'SELECT result,status FROM {table} WHERE id=? AND student_id=current_student()',
                     (item['attempt_id'],)).fetchone()
    return json.loads(row['result']) if row and row['status'] == 'submitted' else None


def view(db, pid):
    row = get_plan(db, pid)
    items = list(db.execute('SELECT * FROM training_items WHERE plan_id=? ORDER BY position', (pid,)))
    results = [(item, item_result(db, item)) for item in items]
    finished = sum(r is not None for _, r in results)
    if finished == len(items) and row['status'] == 'active':
        db.execute("UPDATE training_plans SET status='completed' WHERE id=?", (pid,))
    retests = [r for i, r in results if i['phase'] != 'training' and r is not None]
    value = {'id': pid, 'book_id': row['book_id'], **json.loads(row['data']),
             'status': 'completed' if finished == len(items) else row['status'],
             'answered': finished, 'total': len(items),
             'training_answered': sum(r is not None and i['phase'] == 'training' for i, r in results),
             'retest_answered': len(retests), 'retest_correct': sum(bool(r['correct']) for r in retests),
             'independent_retests': sum(r.get('evidence_weight', 0) > 0 and not r.get('assisted') for r in retests),
             'note': '加练只记录学习过程；独立新题复测按原学情规则累积证据，完成一轮不等于掌握。'}
    return value


def pools(db, profile):
    """Only unseen, scoped, distinct, objectively gradable verified exercises."""
    from app.study import question_types
    from app.diagnostic_core import trusted, verified
    options = defaultdict(list)
    seen = {r[0] for r in db.execute('SELECT q.content_hash FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.student_id=current_student()')}
    seen.update(r[0] for r in db.execute("SELECT i.identity FROM training_items i JOIN training_plans p ON p.id=i.plan_id WHERE p.student_id=current_student() AND (p.status='active' OR i.attempt_id IS NOT NULL)"))
    seen.update(bank.evidence_identity(json.loads(r[0])) for r in db.execute('SELECT q.data FROM bank_attempts a JOIN bank_questions q ON q.id=a.question_id WHERE a.student_id=current_student()'))
    allowed = {t['id'] for t in profile['types']}
    if book_id() == 'math-7-1':
        replenish(db)
        hashes = {r['id']: r['content_hash'] for r in db.execute('SELECT id,content_hash FROM questions')}
        for tid, questions in practice_pool(db).items():
            for q in questions:
                identity = hashes[q['id']]
                if tid in allowed and identity not in seen and q['difficulty'] < 3:
                    options[(tid, q['difficulty'])].append(('verified', q, identity, 0))
    where, args = bank.clauses(bank.Selection(course_book_id=book_id(), answer_mode='choice'), playable=True)
    for row in db.execute('SELECT q.data FROM bank_questions q WHERE ' + where, args):
        q = json.loads(row[0])
        identity = bank.evidence_identity(q)
        if identity in seen or q['difficulty'] > 2 or not trusted(q):
            continue
        for t in question_types(db, q):
            if t['id'] in allowed and t.get('classification_reviewed', True):
                options[(t['id'], q['difficulty'])].append(('bank', q, identity, 0 if verified(q) else 1))
    for key, items in options.items():
        random.shuffle(items)
        items.sort(key=lambda i: i[3])  # Independently checked templates before reviewed bank.
        unique = {}
        for item in items:
            unique.setdefault(item[2], item)
        options[key] = list(unique.values())
    return options


def choices(db, requested):
    from app.study import state
    profile = state(db)
    available = pools(db, profile)
    candidates = []
    for t in profile['types']:
        if requested and t['id'] != requested:
            continue
        mode = 'training' if t['ai_ready'] else 'diagnostic'
        needed = 5 if mode == 'training' else 3
        for difficulty in (1, 2):
            if len(available[(t['id'], difficulty)]) >= needed:
                candidates.append({'type_id': t['id'], 'name': t['name'], 'difficulty': difficulty,
                                   'mode': mode, 'independent_count': t['independent_count'],
                                   'current_status': t['current_status'], 'evidence_summary': t['evidence_summary'],
                                   'recent_errors': [{'stem': e['stem'], 'student_answer': e['answer'], 'error': e['error']}
                                                     for e in t['evidence'][-5:] if not e['correct']]})
    if not candidates:
        raise HTTPException(409, '这个范围缺少足够的未见核验题，暂不能建立训练计划。请换个题型或继续普通练习。')
    weak = [c for c in candidates if c['mode'] == 'training']
    candidates = weak or candidates
    candidates.sort(key=lambda c: (c['independent_count'], c['difficulty'], c['type_id']))
    return candidates, available


def grading_context(db, attempt_id, assisted=False):
    """Called by every objective submit path, including legacy endpoints."""
    item = db.execute('SELECT * FROM training_items WHERE attempt_id=?', (attempt_id,)).fetchone()
    if not item:
        return None
    plan = get_plan(db, item['plan_id'])
    if plan['status'] != 'active':
        raise HTTPException(409, '这个训练计划已结束')
    for previous in db.execute('SELECT * FROM training_items WHERE plan_id=? AND position<?', (plan['id'], item['position'])):
        if item_result(db, previous) is None:
            raise HTTPException(409, '请按计划顺序作答')
    table = 'questions' if item['source'] == 'verified' else 'bank_questions'
    q = json.loads(db.execute(f'SELECT data FROM {table} WHERE id=?', (item['question_id'],)).fetchone()[0])
    if digest(q) != item['content_hash']:
        raise HTTPException(409, '题目内容已更新，请结束本轮后重新建立计划')
    if item['source'] == 'verified':
        exposed = db.execute('SELECT 1 FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.student_id=current_student() AND a.id!=? AND q.content_hash=?', (attempt_id, item['identity'])).fetchone() is not None
    else:
        exposed = any(bank.evidence_identity(json.loads(r[0])) == item['identity'] for r in db.execute('SELECT q.data FROM bank_attempts a JOIN bank_questions q ON q.id=a.question_id WHERE a.student_id=current_student() AND a.id!=?', (attempt_id,)))
    return {'training_plan_id': plan['id'], 'training_phase': item['phase'],
            'independent_eligible': item['phase'] != 'training' and not assisted and not exposed}


def create_router(settings):
    router = APIRouter(prefix='/api/v1/study/training-plans', tags=['训练与独立复测'])
    slots = asyncio.Semaphore(1)

    @router.get('')
    def active():
        with connect(settings.database_path) as db:
            row = db.execute("SELECT id FROM training_plans WHERE student_id=current_student() AND book_id=? AND status='active'", (book_id(),)).fetchone()
            return {'plan': view(db, row['id']) if row else None}

    @router.post('')
    async def create(body: RequestPlan):
        async with slots:
            with connect(settings.database_path) as db:
                row = db.execute("SELECT id FROM training_plans WHERE student_id=current_student() AND book_id=? AND status='active'", (book_id(),)).fetchone()
                if row:
                    value = view(db, row['id'])
                    if value['status'] == 'active':
                        return value
                candidates, _ = choices(db, body.type_id)
            chosen = candidates[0]
            provider = 'rules'
            proposal = None
            if chosen['mode'] == 'training' and settings.deepseek_api_key:
                prompt = ('为学生选择一轮加练计划。只能从后端给定候选中选type_id和difficulty，count固定3。'
                          '不得编题、提供答案、宣称掌握或修改学情。reason只说明真实证据，不能把加权错误率称为能力分。')
                try:
                    proposal = await bank_ai.request_json(settings, ai_policy.messages(prompt, {'candidates': candidates}), Proposal)
                except HTTPException as exc:
                    if exc.status_code not in {502, 503, 504}:
                        raise
                if proposal:
                    chosen = next((c for c in candidates if c['type_id'] == proposal.type_id and c['difficulty'] == proposal.difficulty), None)
                    if not chosen or ai_policy.boundary_reason(proposal.reason) or ai_policy.response_boundary_reason({'reply': proposal.reason}):
                        raise HTTPException(409, 'AI计划超出允许范围，未建立训练；请重试')
                    provider = settings.ai_provider
            # Recheck live evidence and stock after the model call; hold a write lock when reserving.
            with connect(settings.database_path) as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute("SELECT id FROM training_plans WHERE student_id=current_student() AND book_id=? AND status='active'", (book_id(),)).fetchone()
                if row:
                    return view(db, row['id'])
                current, available = choices(db, body.type_id)
                if not any(c['type_id'] == chosen['type_id'] and c['difficulty'] == chosen['difficulty'] and c['mode'] == chosen['mode'] for c in current):
                    raise HTTPException(409, '答题证据已变化，请重新生成计划')
                training = chosen['mode'] == 'training'
                data = {**chosen, 'training_count': 3 if training else 0, 'retest_count': 2 if training else 3,
                        'provider': provider, 'ai_reason': proposal.reason if proposal else None,
                        'reason': '近期独立题有重复错误，先加练，再用新题检查。' if training else '先用独立新题补充判断依据；本轮不预设薄弱点。',
                        'policy_version': 'training-2026.10.17-1'}
                pid = str(uuid.uuid4())
                db.execute("INSERT INTO training_plans VALUES(?,current_student(),?,'active',?,?)", (pid, book_id(), dumps(data), now()))
                for pos, (source, q, identity, _) in enumerate(available[(chosen['type_id'], chosen['difficulty'])][:5 if training else 3]):
                    phase = 'training' if training and pos < 3 else 'retest' if training else 'diagnostic'
                    db.execute('INSERT INTO training_items VALUES(?,?,?,?,?,?,?,NULL)', (pid, pos, source, q['id'], identity, digest(q), phase))
                return view(db, pid)

    @router.get('/{pid}')
    def retrieve(pid: str):
        with connect(settings.database_path) as db:
            return view(db, pid)

    @router.post('/{pid}/next')
    def next_item(pid: str):
        with connect(settings.database_path) as db:
            db.execute('BEGIN IMMEDIATE')
            value = view(db, pid)
            if value['status'] != 'active':
                return {'plan': value, 'work': None}
            item = next(i for i in db.execute('SELECT * FROM training_items WHERE plan_id=? ORDER BY position', (pid,)) if item_result(db, i) is None)
            table = 'questions' if item['source'] == 'verified' else 'bank_questions'
            row = db.execute(f'SELECT data FROM {table} WHERE id=?', (item['question_id'],)).fetchone()
            if not row or digest(json.loads(row[0])) != item['content_hash']:
                raise HTTPException(409, '题目内容已更新，请结束本轮后重新建立计划')
            q = json.loads(row[0])
            # Also check live publication and verifier status, not only the frozen digest.
            available = practice_pool(db) if item['source'] == 'verified' else None
            if available is not None and not any(x['id'] == q['id'] for x in available[value['type_id']]):
                raise HTTPException(409, '题目已撤下，请重新建立计划')
            if item['source'] == 'bank':
                where, args = bank.clauses(bank.Selection(), playable=True)
                if not db.execute('SELECT 1 FROM bank_questions q WHERE q.id=? AND ' + where, [q['id'], *args]).fetchone():
                    raise HTTPException(409, '题目已撤下，请重新建立计划')
            attempt = item['attempt_id'] or str(uuid.uuid4())
            attempts = 'attempts' if item['source'] == 'verified' else 'bank_attempts'
            db.execute(f"UPDATE {attempts} SET status='skipped' WHERE student_id=current_student() AND status='assigned' AND id!=?", (attempt,))
            if not item['attempt_id']:
                if item['source'] == 'verified':
                    db.execute('INSERT INTO attempts(id,student_id,question_id,hint_used,assigned_at) VALUES(?,current_student(),?,?,?)', (attempt, q['id'], int(item['phase'] == 'training'), now()))
                else:
                    db.execute("INSERT INTO bank_attempts(id,student_id,question_id,status,assisted,created_at) VALUES(?,current_student(),?,'assigned',?,?)", (attempt, q['id'], int(item['phase'] == 'training'), now()))
                db.execute('UPDATE training_items SET attempt_id=? WHERE plan_id=? AND position=?', (attempt, pid, item['position']))
            else:
                db.execute(f"UPDATE {attempts} SET status='assigned' WHERE id=? AND student_id=current_student()", (attempt,))
            question = {'answer_mode': 'numeric', **public_question(q)} if item['source'] == 'verified' else bank.public(q)
            return {'plan': value, 'work': {'source': item['source'], 'attempt_id': attempt, 'question': question,
                    'type_name': value['name'], 'training_plan_id': pid, 'training_phase': item['phase'], 'position': item['position'] + 1}}

    @router.post('/{pid}/cancel')
    def cancel(pid: str):
        with connect(settings.database_path) as db:
            db.execute('BEGIN IMMEDIATE')
            get_plan(db, pid)
            for item in db.execute('SELECT * FROM training_items WHERE plan_id=?', (pid,)):
                table = 'attempts' if item['source'] == 'verified' else 'bank_attempts'
                db.execute(f"UPDATE {table} SET status='skipped' WHERE id=? AND student_id=current_student() AND status='assigned'", (item['attempt_id'],))
            db.execute("UPDATE training_plans SET status='cancelled' WHERE id=? AND status='active'", (pid,))
            return view(db, pid)

    return router
