"""七上题型覆盖、可解释画像与持久化抽样诊断。诊断共用原判分及作答证据。"""
import json
import random
import uuid
from collections import Counter, defaultdict

from fastapi import HTTPException

from app import learning
from app.challenges import validate_challenge
from app.course_catalog import BOOK_MAP
from app.db import audit, dumps, now
from app.math_catalog import BOOK_ID, TYPES, TYPE_MAP, VERSION, resolve_type
from app.question_types import template_type_id
from app.questions import public_question, validate_question
from app.answers import parse_answer


def verified_pool(db):
    pools = defaultdict(list)
    for row in db.execute("SELECT data FROM questions"):
        q = json.loads(row['data'])
        try:
            origin = q.get('provenance', {}).get('kind')
            valid = (validate_challenge(q) if origin == 'original_challenge_template' else
                     validate_question(q) if origin == 'original_template' else False)
            tid = resolve_type(template_type_id(q)) if valid else None
        except (KeyError, ValueError, ZeroDivisionError, TypeError):
            tid = None
        if tid:
            pools[tid].append(q)
    return pools


def practice_pool(db):
    """已撤下的远端题不再分配，历史核验证据仍保留。"""
    inactive={r[0] for r in db.execute("SELECT local_id FROM content_installed_items WHERE family='original' AND active=0 AND local_id LIKE 'remote:%'")}
    return defaultdict(list,{tid:[q for q in items if q['id'] not in inactive] for tid,items in verified_pool(db).items()})


def states(db):
    evidence = defaultdict(list)
    seen = set()
    for row in db.execute("""SELECT a.*,q.data FROM attempts a JOIN questions q ON a.question_id=q.id
            WHERE a.student_id=current_student() AND a.status='submitted' ORDER BY a.submitted_at,a.id"""):
        result, q = json.loads(row['result']), json.loads(row['data'])
        tid = resolve_type(result.get('question_type_id') or template_type_id(q))
        identity = ('original', q['id'])
        if not tid or result.get('evidence_weight', 0) <= 0 or identity in seen:
            continue
        seen.add(identity)
        evidence[tid].append({'id': row['id'], 'source': 'practice', 'question_id': q['id'],
            'stem': q['stem'], 'answer': row['answer'], 'correct': result['correct'],
            'assisted': result.get('assisted', False), 'weight': result['evidence_weight'],
            'error': result.get('error'), 'submitted_at': row['submitted_at']})
    known = {r['id']: json.loads(r['data']) for r in db.execute('SELECT id,data FROM question_types')}
    for row in db.execute("""SELECT e.*,i.data FROM import_evidence e JOIN import_items i ON i.id=e.item_id
            WHERE e.student_id=current_student() ORDER BY e.created_at,e.item_id"""):
        item = json.loads(row['data'])
        registered = known.get(item.get('question_type_id'), {})
        tid = resolve_type(item.get('question_type_id'), registered.get('name', ''))
        identity = ('import', row['fingerprint'])
        if not tid or row['weight'] <= 0 or identity in seen:
            continue
        seen.add(identity)
        evidence[tid].append({'id': row['item_id'], 'source': 'import', 'question_id': None,
            'stem': item['stem'], 'answer': item.get('student_answer', ''), 'correct': row['verdict']=='correct',
            'assisted': bool(item.get('assisted', False)), 'weight': row['weight'], 'error': None,
            'submitted_at': row['created_at']})
    result = {}
    for t in TYPES:
        items = sorted(evidence[t['id']], key=lambda e: (e['submitted_at'], e['id']))
        success = sum(e['weight'] for e in items if e['correct'])
        failure = sum(e['weight'] for e in items if not e['correct'])
        estimate = round((1+success)/(2+success+failure), 3) if items else None
        independent = sum(not e['assisted'] for e in items)
        status = ('待诊断' if not items else '证据不足' if len(items)<3 else '需要巩固' if estimate<.6 else
                  '练习表现较稳' if len(items)>=5 and independent>=3 and estimate>=.8 and items[-1]['correct'] else '继续检查')
        errors = Counter(e['error']['feedback'] for e in items if e['error'])
        result[t['id']] = {'attempts':len(items), 'correct':sum(e['correct'] for e in items),
            'independent':independent, 'assisted':len(items)-independent, 'mastery':estimate, 'status':status,
            'recent':{'total':len(items[-5:]), 'correct':sum(e['correct'] for e in items[-5:])},
            'errors':[{'feedback':text,'count':n} for text,n in errors.most_common(3)],
            'evidence':list(reversed(items[-8:]))}
    return result


def validate_unit(unit_id):
    if unit_id and unit_id not in {u['id'] for u in BOOK_MAP[BOOK_ID]['units']}:
        raise HTTPException(422, '本轮题型地图与诊断仅支持七上数学的已有单元')


def coverage(db, unit_id=None):
    validate_unit(unit_id)
    pools, profile = verified_pool(db), states(db)
    candidates = {r['goal_id']:r['n'] for r in db.execute("""SELECT l.goal_id,COUNT(*) n FROM course_question_links l
        JOIN bank_questions q ON q.id=l.question_id WHERE l.goal_id LIKE 'math-7-1:%'
        AND q.status!='superseded' AND json_extract(q.data,'$.can_practice')=1 GROUP BY l.goal_id""")}
    items = []
    for t in TYPES:
        if unit_id and t['unit_id'] != unit_id:
            continue
        qs = pools[t['id']]
        levels = {str(n):sum(q['difficulty']==n for q in qs) for n in (1,2,3)}
        items.append({**t, **profile[t['id']], 'verified_questions':len(qs), 'difficulty_counts':levels,
            'verified_structures':sorted({q['provenance']['structure'] for q in qs if q.get('provenance',{}).get('structure')}),
            'candidate_goal_questions':candidates.get(t['goal_id'],0),
            'coverage_status':'可作抽样诊断' if levels['1']+levels['2'] else '有挑战题，需补基础题' if levels['3'] else '待补核验题'})
    return {'version':VERSION, 'book_id':BOOK_ID, 'unit_id':unit_id,
        'units':[{'id':u['id'],'name':u['name']} for u in BOOK_MAP[BOOK_ID]['units']], 'types':items,
        'summary':{'types':len(items), 'with_verified_questions':sum(bool(t['verified_questions']) for t in items),
            'diagnosable':sum(t['coverage_status']=='可作抽样诊断' for t in items),
            'missing_verified':sum(not t['verified_questions'] for t in items),
            'unassessed':sum(t['attempts']==0 for t in items)},
        'note':'核验题仅指通过独立数学规则校验的原创题；同一模板的参数变式不能代表完整题型覆盖。外部题库数量是关联知识目标的候选数，可在不同题型间重叠，尚未逐题确认细分题型。'}


def recommendations(db, type_ids=None):
    profile, pools = states(db), verified_pool(db)
    scope = [t for t in TYPES if type_ids is None or t['id'] in type_ids]
    # 实际错误优先复查，其次补尚未测过的结构。少量作答不宣布掌握。
    scope.sort(key=lambda t:(not any(not e['correct'] for e in profile[t['id']]['evidence'][:3]),
                             profile[t['id']]['attempts']>0, profile[t['id']]['mastery'] or 0, TYPES.index(t)))
    plans, selected = [], set()
    for t in scope:
        state = profile[t['id']]
        if state['status']=='练习表现较稳':
            continue
        target, reason = t, ('本次或近期有错误，先用另一道题检查同一解题结构。' if any(not e['correct'] for e in state['evidence'][:3]) else
                             '尚无足够证据，先做基础诊断。')
        for prerequisite in t['prerequisites']:
            p = profile[prerequisite]
            if p['attempts']<2 or (p['mastery'] or 0)<.6:
                target = TYPE_MAP[prerequisite]
                reason = f'练习“{t["name"]}”需要先检查“{target["name"]}”这一前置结构。'
                break
        available = pools[target['id']]
        if target['id'] in selected:
            continue
        selected.add(target['id'])
        plans.append({'type_id':target['id'], 'name':target['name'], 'reason':reason,
                      'available':bool(available), 'status':profile[target['id']]['status']})
        if len(plans)==4:
            break
    return plans


def get_session(db, session_id):
    row = db.execute("SELECT * FROM math_diagnostics WHERE id=? AND student_id=current_student()", (session_id,)).fetchone()
    if not row:
        raise HTTPException(404, '诊断记录不存在')
    return row


def session_view(db, session_id):
    session = get_session(db, session_id)
    meta = json.loads(session['data'])
    rows = list(db.execute('SELECT * FROM math_diagnostic_items WHERE session_id=? ORDER BY position', (session_id,)))
    items, current = [], None
    for row in rows:
        entry = {'position':row['position'], 'type_id':row['type_id'], 'type_name':meta['type_names'][row['type_id']],
                 'attempt_id':row['attempt_id'], 'result':None}
        q = json.loads(db.execute('SELECT data FROM questions WHERE id=?', (row['question_id'],)).fetchone()[0])
        if row['attempt_id']:
            attempt = db.execute('SELECT answer,result FROM attempts WHERE id=?', (row['attempt_id'],)).fetchone()
            entry.update(answer=attempt['answer'], result=json.loads(attempt['result']), stem=q['stem'])
        elif current is None and session['status']=='active':
            current = {**entry, 'question':public_question(q)}
        items.append(entry)
    measured = [t['type_id'] for t in items if t['result']]
    scoped = [t for t in TYPES if not meta['unit_id'] or t['unit_id']==meta['unit_id']]
    profile = states(db)
    return {'id':session_id, 'status':session['status'], 'book_id':session['book_id'], 'version':meta['version'],
        'unit_id':meta['unit_id'], 'total':len(items), 'answered':len(measured), 'current':current, 'items':items,
        'summary':{'correct':sum(bool(t['result'] and t['result']['correct']) for t in items),
            'measured_types':len(set(measured)), 'unmeasured_types':sum(t['id'] not in measured for t in scoped)},
        'recommendations':recommendations(db, measured) if measured else [],
        'type_states':[{**t, **profile[t['id']]} for t in scoped if t['id'] in measured],
        'note':'这是抽样诊断，不是整册达标考试；未抽到的题型保留待诊断，不把一道对题视为已掌握。暂停或结束不把未答题计错。'}


def start(db, size=10, unit_id=None):
    validate_unit(unit_id)
    db.execute('BEGIN IMMEDIATE')
    prior = db.execute("SELECT id,data FROM math_diagnostics WHERE student_id=current_student() AND book_id=? AND status='active'",(BOOK_ID,)).fetchone()
    if prior:
        if json.loads(prior['data'])['unit_id'] != unit_id:
            raise HTTPException(409, '已有另一范围的未完成诊断，请先继续或结束它')
        return session_view(db, prior['id'])
    profile, pools = states(db), verified_pool(db)
    groups = defaultdict(list)
    for t in TYPES:
        qs = [q for q in pools[t['id']] if q['difficulty']<3]
        if qs and (not unit_id or t['unit_id']==unit_id):
            groups[t['unit_id']].append(t)
    for group in groups.values():
        group.sort(key=lambda t:(profile[t['id']]['attempts'], profile[t['id']]['mastery'] or 0, TYPES.index(t)))
    selected = []
    while any(groups.values()) and len(selected)<size:
        for group in groups.values():
            if group and len(selected)<size:
                selected.append(group.pop(0))
    if not selected:
        raise HTTPException(404, '当前范围还缺可核验的基础诊断题')
    session_id, timestamp = str(uuid.uuid4()), now()
    meta = {'version':VERSION,'unit_id':unit_id,'type_names':{t['id']:t['name'] for t in selected}}
    db.execute("INSERT INTO math_diagnostics VALUES(?,current_student(),?,'active',?,?,?)",(session_id,BOOK_ID,dumps(meta),timestamp,timestamp))
    counts = {r['question_id']:r['n'] for r in db.execute("SELECT question_id,COUNT(*) n FROM attempts WHERE student_id=current_student() AND status='submitted' GROUP BY question_id")}
    for n,t in enumerate(selected):
        qs = [q for q in pools[t['id']] if q['difficulty']<3]
        least = min(counts.get(q['id'],0) for q in qs)
        q = random.choice([q for q in qs if counts.get(q['id'],0)==least])
        db.execute('INSERT INTO math_diagnostic_items VALUES(?,?,?,?,NULL)',(session_id,n,t['id'],q['id']))
    audit(db, 'math_diagnostic_started', {'id':session_id,'types':len(selected),'version':VERSION})
    return session_view(db, session_id)


def answer(db, session_id, position, text):
    db.execute('BEGIN IMMEDIATE')
    session = get_session(db, session_id)
    row = db.execute('SELECT * FROM math_diagnostic_items WHERE session_id=? AND position=?',(session_id,position)).fetchone()
    if not row:
        raise HTTPException(404, '诊断题目不存在')
    q = json.loads(db.execute('SELECT data FROM questions WHERE id=?',(row['question_id'],)).fetchone()[0])
    # 重试仅允许同一种符合题目要求的答案，不重复记录。
    try:
        value = parse_answer(q, text)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    if row['attempt_id']:
        previous = db.execute('SELECT answer FROM attempts WHERE id=?',(row['attempt_id'],)).fetchone()[0]
        if parse_answer(q, previous)!=value:
            raise HTTPException(409,'本题已提交，不能修改原作答')
        return session_view(db, session_id)
    first = db.execute('SELECT MIN(position) FROM math_diagnostic_items WHERE session_id=? AND attempt_id IS NULL',(session_id,)).fetchone()[0]
    if session['status']!='active' or first!=position:
        raise HTTPException(409,'请按顺序完成当前诊断题')
    attempt_id = str(uuid.uuid4())
    # 诊断没有普通练习的assigned行，因而不抢占/跳过正在进行的普通练习。
    db.execute("INSERT INTO attempts(id,student_id,question_id,status,assigned_at) VALUES(?,current_student(),?,'submitted',?)",(attempt_id,q['id'],now()))
    learning.record_answer(db,attempt_id,q,text)
    db.execute('UPDATE math_diagnostic_items SET attempt_id=? WHERE session_id=? AND position=?',(attempt_id,session_id,position))
    remaining = db.execute('SELECT COUNT(*) FROM math_diagnostic_items WHERE session_id=? AND attempt_id IS NULL',(session_id,)).fetchone()[0]
    db.execute('UPDATE math_diagnostics SET status=?,updated_at=? WHERE id=?',('active' if remaining else 'completed',now(),session_id))
    return session_view(db,session_id)


def cancel(db,session_id):
    db.execute('BEGIN IMMEDIATE')
    session = get_session(db,session_id)
    if session['status']=='active':
        db.execute("UPDATE math_diagnostics SET status='cancelled',updated_at=? WHERE id=?",(now(),session_id))
        audit(db,'math_diagnostic_cancelled',{'id':session_id})
    return session_view(db,session_id)
