"""题库维护：独立管理员、带修订号草稿、不可变题目快照与人工审核记录。"""
import hashlib
import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app import bank, courses
from app.course_catalog import BOOKS, BOOK_MAP, GOALS
from app.db import audit, connect, dumps, now
from app.question_annotation import Annotation, validate_for_question
from app.identity import scope, student_id


class Option(BaseModel):
    key: str = Field(pattern=r'^[A-Z]$')
    text: str = Field(min_length=1, max_length=4000)


class Draft(BaseModel):
    subject: str = 'math'
    stage: Literal['junior', 'senior'] = 'junior'
    grade: int | None = Field(default=None, ge=7, le=12)
    term: int | None = Field(default=None, ge=1, le=2)
    curriculum_book_id: str | None = Field(default=None, max_length=100)
    stem: str = Field(default='', max_length=30000)
    kind: Literal['single_choice', 'multiple_choice', 'reference'] = 'reference'
    options: list[Option] = Field(default_factory=list, max_length=26)
    answer: str = Field(default='', max_length=12000)
    steps: list[str] = Field(default_factory=list, max_length=40)
    knowledge_tags: list[str] = Field(default_factory=list, max_length=20)
    type_tags: list[str] = Field(default_factory=list, max_length=20)
    curriculum_goal_ids: list[str] = Field(default_factory=list, max_length=20)
    difficulty: int = Field(default=1, ge=1, le=3)
    difficulty_basis: str = Field(default='', max_length=2000)
    annotation: Annotation | None = None


class CreateDraft(BaseModel):
    family: Literal['bank', 'original'] | None = None
    question_id: str | None = Field(default=None, max_length=200)


class SaveDraft(BaseModel):
    revision: int = Field(ge=1)
    form: Draft


class Revision(BaseModel):
    revision: int = Field(ge=1)


class Publish(Revision):
    reviewed: bool = False
    review_note: str = Field(min_length=4, max_length=2000)


def require_admin(settings):
    if not scope():
        raise HTTPException(401, '请先登录管理员账号')
    with connect(settings.database_path) as db:
        if not db.execute('SELECT 1 FROM admin_accounts WHERE student_id=?', (student_id(),)).fetchone():
            raise HTTPException(403, '此账号没有题库维护权限')


def grant_admin(db, username, revoke=False):
    from app.auth import username as normalize
    row = db.execute('SELECT student_id FROM accounts WHERE username=?', (normalize(username),)).fetchone()
    if not row:
        raise ValueError('账号不存在，请先注册')
    if revoke:
        db.execute('DELETE FROM admin_accounts WHERE student_id=?', (row[0],))
    else:
        db.execute('INSERT OR IGNORE INTO admin_accounts VALUES(?,?)', (row[0], now()))
    audit(db, 'admin_role_changed', {'student_id': row[0], 'admin': not revoke})


def source_row(db, family, qid):
    table = 'bank_questions' if family == 'bank' else 'questions'
    row = db.execute('SELECT * FROM '+table+' WHERE id=?', (qid,)).fetchone()
    if not row:
        raise HTTPException(404, '题目不存在')
    return row, json.loads(row['data'])


def validate_publish(form, source):
    if source.get('annotation') and not form.annotation:
        raise ValueError('已有完整标注不能通过关闭标注跳过审核')
    if form.subject not in bank.SUBJECTS:
        raise ValueError('请选择已有科目')
    if form.stage == 'junior':
        if form.grade is None or form.grade > 9 or form.term is None:
            raise ValueError('初中题目需要选择七至九年级及学期')
        bid = f'{form.subject}-{form.grade}-{form.term}'
    else:
        if form.grade is not None and form.grade < 10:
            raise ValueError('高中题目的年级须为十至十二年级')
        bid = form.curriculum_book_id or ''
    if (bid not in BOOK_MAP or BOOK_MAP[bid]['subject'] != form.subject
            or BOOK_MAP[bid].get('stage', 'junior') != form.stage):
        raise ValueError('请选择与科目和学段匹配的教材册次')
    if not form.stem.strip() or not form.answer.strip() or not any(s.strip() for s in form.steps):
        raise ValueError('发布需要完整题干、参考答案和解析')
    for values, label in [(form.knowledge_tags, '知识点'), (form.type_tags, '具体题型')]:
        if not values or any(not v.strip() or len(v) > 150 for v in values):
            raise ValueError(f'请填写有效的{label}，每项不超过150字')
    if any(len(t.strip()) < 4 or t.strip() in {'单选题','多选题','选择题','解答题','计算题','阅读理解','single_choice','multiple_choice'} for t in form.type_tags):
        raise ValueError('题型应具体到考察方法，例如“负数的绝对值”，不能只写选择题或阅读理解')
    if not form.curriculum_goal_ids or any(g not in GOALS or GOALS[g]['book_id'] != bid
                                           or GOALS[g].get('stage', 'junior') != form.stage
                                           or GOALS[g]['subject'] != form.subject
                                           for g in form.curriculum_goal_ids):
        raise ValueError('请选择本册对应的课程目标')
    if not form.difficulty_basis.strip():
        raise ValueError('请说明难度判断依据')
    if any(len(s) > 4000 for s in form.steps):
        raise ValueError('每条解析最多4000字')
    if source.get('has_missing_assets'):
        raise ValueError('原题图片或材料缺失，补齐来源材料后再发布；不能仅通过改标签解除隔离')
    if form.kind != 'reference':
        q = {'options':[o.model_dump() for o in form.options], 'kind':form.kind}
        if len(q['options']) < 2 or len({o['key'] for o in q['options']}) != len(q['options']):
            raise ValueError('选择题需要至少两个不重复的选项')
        bank.canonical_choice(form.answer, q)
    elif form.options:
        raise ValueError('文字/过程题不应包含选择题选项')
    if form.annotation:
        a = validate_for_question(form.annotation, form.model_dump(), published=True)
        if a.review.issues:
            raise ValueError('完整标注仍有待审问题，请逐项处理后再发布')
        if form.kind != 'reference' and a.answer_spec.accepted_answers:
            q = {'options':[o.model_dump() for o in form.options], 'kind':form.kind}
            if any(bank.canonical_choice(v,q) != bank.canonical_choice(form.answer,q) for v in a.answer_spec.accepted_answers):
                raise ValueError('可接受选项答案与题目参考答案不一致')
        if a.difficulty.level != form.difficulty:
            raise ValueError('结构化标注与题目难度不一致')
        if set(a.curriculum.goal_ids) != set(form.curriculum_goal_ids):
            raise ValueError('结构化标注与课程目标不一致')


def draft_view(row):
    value = dict(row)
    data = json.loads(value.pop('data'))
    value.pop('source_hash', None)
    return {**value, 'form':data['form'], 'provenance':data['source'].get('provenance', {}),
            'has_missing_assets':bool(data['source'].get('has_missing_assets'))}


def locked_draft(db, item_id, revision):
    row = db.execute('SELECT * FROM bank_editor_items WHERE id=?', (item_id,)).fetchone()
    if not row:
        raise HTTPException(404, '草稿不存在')
    if row['revision'] != revision:
        raise HTTPException(409, '题目已被另一窗口更新，请重新打开后编辑')
    return row


def event(db, item_id, revision, action, form):
    db.execute('INSERT INTO bank_editor_events(item_id,revision,action,actor,data,created_at) VALUES(?,?,?,?,?,?)',
               (item_id, revision, action, student_id(), dumps(form), now()))
    audit(db, 'bank_editor_'+action, {'item_id':item_id, 'revision':revision, 'actor':student_id()})


def answer_basis(q):
    options=q.get('options',[])
    correct=sorted(bank.normalized(o['text']) for o in options if o['key'] in str(q.get('answer','')))
    return [bank.normalized(q.get('stem','')),q.get('kind'),
            sorted(bank.normalized(o['text']) for o in options),correct if options else bank.normalized(str(q.get('answer','')))]


def supersede(db, qid, replacement=None, invalidate=False):
    if not qid:
        return
    row = db.execute('SELECT data FROM bank_questions WHERE id=?', (qid,)).fetchone()
    if row:
        q = json.loads(row[0]);q.update(status='superseded', can_practice=False)
        if invalidate or (replacement and answer_basis(q)!=answer_basis(replacement)):
            q['evidence_invalidated']=True
        db.execute("UPDATE bank_questions SET status='superseded',data=? WHERE id=?", (dumps(q), qid))


def create_router(settings):
    router = APIRouter(prefix='/api/v1/admin', tags=['题库维护'], dependencies=[Depends(lambda:require_admin(settings))])

    @router.get('/catalog')
    def catalog():
        from app.math_catalog import TYPES
        return {'subjects':bank.SUBJECTS, 'books':BOOKS, 'math_types':TYPES}

    @router.get('/dashboard')
    def dashboard():
        with connect(settings.database_path) as db:
            totals = {name:db.execute(sql).fetchone()[0] for name, sql in {
                'students':'SELECT count(*) FROM accounts',
                'bank_questions':"SELECT count(*) FROM bank_questions WHERE status!='superseded'",
                'original_questions':'SELECT count(*) FROM questions',
                'reviewed':"SELECT count(*) FROM bank_questions WHERE status!='superseded' AND json_extract(data,'$.provenance.teacher_reviewed')=1",
                'ai_calibrated':"SELECT count(*) FROM bank_questions WHERE status NOT IN ('superseded','quarantine') AND json_extract(data,'$.quality.calibration.status')='ai_reviewed'",
                'drafts':"SELECT count(*) FROM bank_editor_items WHERE state='draft'",
                'attempts':"SELECT (SELECT count(*) FROM attempts WHERE status='submitted')+(SELECT count(*) FROM bank_attempts WHERE status='submitted')",
                'ai_questions':'SELECT count(*) FROM teacher_messages',
                'imports':'SELECT count(*) FROM imports'}.items()}
            annotations = {name:db.execute(sql).fetchone()[0] for name,sql in {
                'candidates':"SELECT count(*) FROM bank_questions WHERE status!='superseded' AND json_extract(data,'$.annotation.review.status')='candidate'",
                'excluded':"SELECT count(*) FROM bank_questions WHERE status='quarantine' AND json_extract(data,'$.annotation_exclusion') IS NOT NULL",
                'rubric_pending':"SELECT count(*) FROM bank_questions WHERE status!='superseded' AND EXISTS(SELECT 1 FROM json_each(data,'$.annotation.review.issues') WHERE value='rubric_pending')"}.items()}
            subjects = [dict(r) for r in db.execute("SELECT subject,count(*) total,sum(status='quarantine') quarantined,sum(json_extract(data,'$.provenance.teacher_reviewed')=1) reviewed FROM bank_questions WHERE status!='superseded' GROUP BY subject ORDER BY total DESC")]
            trend = [dict(r) for r in db.execute("""SELECT day,count(*) attempts FROM (
                SELECT substr(submitted_at,1,10) day FROM attempts WHERE status='submitted'
                UNION ALL SELECT substr(submitted_at,1,10) FROM bank_attempts WHERE status='submitted')
                WHERE day>=date('now','-13 days') GROUP BY day ORDER BY day""")]
            changes = [dict(r) for r in db.execute('SELECT e.id,e.item_id,e.revision,e.action,e.created_at,a.username FROM bank_editor_events e JOIN accounts a ON a.student_id=e.actor ORDER BY e.id DESC LIMIT 12')]
            release = db.execute('SELECT version,item_count,created_at FROM content_releases ORDER BY version DESC LIMIT 1').fetchone()
        return {'totals':totals, 'annotations':annotations, 'subjects':subjects, 'trend':trend, 'changes':changes, 'release':dict(release) if release else None}

    @router.get('/questions')
    def questions(family: Literal['bank','original','draft']='bank', query: str=Query('', max_length=200),
                  subject: str='', stage: Literal['','junior','senior']='',
                  grade: int | None=Query(None, ge=7, le=12), term: int | None=Query(None, ge=1, le=2),
                  status: str='', reviewed: Literal['all','pending','reviewed','calibrated']='all', difficulty: int | None=Query(None, ge=1, le=3),
                  limit: int=Query(20, ge=1, le=50), offset: int=Query(0, ge=0, le=200000)):
        table = {'bank':'bank_questions', 'original':'questions', 'draft':'bank_editor_items'}[family]
        prefix = '$.form.' if family == 'draft' else '$.'
        where, args = ['1=1'], []
        if family == 'bank' and status != 'superseded':where.append("status!='superseded'")
        if stage:
            if family == 'original':
                if stage != 'junior': where.append('1=0')
            else:
                where.append(f"json_extract(data,'{prefix}stage')=?");args.append(stage)
        for key, val in [('subject',subject),('grade',grade),('term',term),('difficulty',difficulty)]:
            if val is not None and val != '':
                if family=='original' and key in {'subject','grade','term'}:
                    where.append('?=?');args.extend([{'subject':'math','grade':7,'term':1}[key],val])
                else:where.append(f"json_extract(data,'{prefix}{key}')=?");args.append(val)
        if family=='bank' and reviewed!='all':
            if reviewed=='calibrated':where.append("json_extract(data,'$.quality.calibration.status')='ai_reviewed'")
            else:
                where.append("coalesce(json_extract(data,'$.provenance.teacher_reviewed'),0)=?");args.append(int(reviewed=='reviewed'))
        if status and family != 'original':where.append(('state' if family=='draft' else 'status')+'=?');args.append(status)
        if query:
            where.append(f"(id LIKE ? OR json_extract(data,'{prefix}stem') LIKE ? OR json_extract(data,'{prefix}type_tags') LIKE ?)");args.extend(['%'+query+'%']*3)
        sql = ' FROM '+table+' WHERE '+' AND '.join(where)
        with connect(settings.database_path) as db:
            total = db.execute('SELECT count(*)'+sql, args).fetchone()[0]
            items = []
            for row in db.execute('SELECT *'+sql+' ORDER BY id LIMIT ? OFFSET ?', [*args,limit,offset]):
                q = json.loads(row['data']);q = q['form'] if family == 'draft' else q
                items.append({'id':row['id'], 'stem':q.get('display_stem') or q['stem'], 'answer':str(q.get('answer','')),
                              'stage':q.get('stage','junior' if family=='original' else 'unknown'),
                              'subject':q.get('subject','math'), 'grade':q.get('grade',7 if family=='original' else None),
                              'term':q.get('term',1 if family=='original' else None),
                              'curriculum_book_id':q.get('curriculum_book_id'), 'difficulty':q['difficulty'],
                              'type_tags':q.get('type_tags',[]), 'state':row['state'] if family=='draft' else row['status'] if family=='bank' else 'verified',
                              'annotation_format':(q.get('annotation') or {}).get('response_format'),
                              'annotation_issues':(q.get('annotation') or {}).get('review',{}).get('issues',[]),
                              'annotation_exclusion':q.get('annotation_exclusion'),
                              'reviewed':bool(q.get('provenance',{}).get('teacher_reviewed')),
                              'ai_calibrated':q.get('quality',{}).get('calibration',{}).get('status')=='ai_reviewed'})
        return {'total':total, 'items':items}

    @router.get('/question')
    def question(family: Literal['bank','original'], id: str=Query(max_length=200)):
        with connect(settings.database_path) as db:
            _, q = source_row(db, family, id)
        return q

    @router.post('/drafts', status_code=201)
    def create(body: CreateDraft):
        if bool(body.family) != bool(body.question_id):raise HTTPException(422, '来源类型和题目编号须同时提供')
        with connect(settings.database_path) as db:
            db.execute('BEGIN IMMEDIATE')
            if body.question_id:
                existing = db.execute('SELECT * FROM bank_editor_items WHERE (source_kind=? AND source_id=?) OR published_id=?', (body.family,body.question_id,body.question_id)).fetchone()
                if existing:return draft_view(existing)
                _, source = source_row(db, body.family, body.question_id)
                if source.get('status') == 'superseded':raise HTTPException(409, '请编辑最新题目版本')
            else:source = {}
            values = {k:v for k,v in source.items() if k in Draft.model_fields}
            if body.family == 'original':
                from app.math_catalog import TYPE_MAP, resolve_type
                from app.question_types import template_type_id
                tid = resolve_type(template_type_id(source));t = TYPE_MAP.get(tid,{})
                values.update(subject='math', stage='junior', grade=7, term=1, curriculum_book_id=None,
                              kind='reference', options=[],
                              knowledge_tags=[GOALS[t['goal_id']]['name']] if t else [], type_tags=[t['name']] if t else [],
                              curriculum_goal_ids=[t['goal_id']] if t else [], answer=str(source['answer']))
            if isinstance(values.get('difficulty_basis'),dict):values['difficulty_basis']=dumps(values['difficulty_basis'])
            values['type_tags'] = values.get('type_tags') or source.get('derived_type_tags',[])
            form = Draft.model_validate(values).model_dump()
            item_id = str(uuid.uuid4());stamp = now()
            db.execute('INSERT INTO bank_editor_items VALUES(?,?,?,?,?,?,?,NULL,?)',
                       (item_id,body.family,body.question_id,hashlib.sha256(dumps(source).encode()).hexdigest(),1,dumps({'form':form,'source':source}),'draft',stamp))
            event(db,item_id,1,'created',form)
            return draft_view(db.execute('SELECT * FROM bank_editor_items WHERE id=?',(item_id,)).fetchone())

    @router.get('/drafts/{item_id}')
    def get(item_id: str):
        with connect(settings.database_path) as db:
            row = db.execute('SELECT * FROM bank_editor_items WHERE id=?',(item_id,)).fetchone()
            if not row:raise HTTPException(404,'草稿不存在')
            return {**draft_view(row), 'history':[dict(r) for r in db.execute('SELECT id,revision,action,created_at FROM bank_editor_events WHERE item_id=? ORDER BY id DESC LIMIT 30',(item_id,))]}

    @router.put('/drafts/{item_id}')
    def save(item_id: str, body: SaveDraft):
        with connect(settings.database_path) as db:
            db.execute('BEGIN IMMEDIATE');row=locked_draft(db,item_id,body.revision)
            data=json.loads(row['data']);data['form']=body.form.model_dump();revision=row['revision']+1
            db.execute("UPDATE bank_editor_items SET revision=?,data=?,state='draft',updated_at=? WHERE id=?",(revision,dumps(data),now(),item_id))
            event(db,item_id,revision,'saved',data['form'])
            return draft_view(db.execute('SELECT * FROM bank_editor_items WHERE id=?',(item_id,)).fetchone())

    @router.post('/drafts/{item_id}/publish')
    def publish(item_id: str, body: Publish):
        if not body.reviewed:raise HTTPException(422,'请确认已核对题干、答案、解析及标注')
        with connect(settings.database_path) as db:
            db.execute('BEGIN IMMEDIATE');row=locked_draft(db,item_id,body.revision)
            if row['state']=='published':return draft_view(row)
            data=json.loads(row['data']);form=Draft.model_validate(data['form']);source=data['source']
            validate_publish(form,source)
            if row['source_kind']=='bank' and not row['published_id']:
                _, current=source_row(db,'bank',row['source_id'])
                if hashlib.sha256(dumps(current).encode()).hexdigest()!=row['source_hash']:
                    raise HTTPException(409,'来源题已更新，请从最新版本重新建立草稿')
            qid=f'maint:{item_id}:{row["revision"]}'
            origin=source.get('provenance',{})
            q={**form.model_dump(), 'id':qid,
               'status':'reference' if form.kind=='reference' else 'ready',
               'answer_mode':'written' if form.kind=='reference' else 'choice',
               'tags_source':'teacher', 'can_practice':True, 'has_missing_assets':False, 'issues':[],
               'provenance':{**origin, 'dataset':origin.get('dataset') or 'maintenance',
                   'source_id':origin.get('source_id') or row['source_id'] or item_id,
                   'teacher_reviewed':True, 'review_note':body.review_note}}
            if origin.get('kind')=='original_rule_core':
                q['provenance'].update(kind='teacher_edited_rule_core',parent_rule_version=origin.get('version'))
            if form.kind!='reference':q['answer']=bank.canonical_choice(form.answer,q)
            q['tags']=[]
            for kind,field in [('knowledge','knowledge_tags'),('type','type_tags')]:
                for label in dict.fromkeys(q[field]):
                    tid=bank.register_tag(db,q['subject'],q['stage'],kind,label,'teacher')
                    q['tags'].append({'id':tid,'kind':kind,'label':label,'origin':'teacher'})
            db.execute('INSERT OR IGNORE INTO bank_sources VALUES(?,?,?)',('maintenance',dumps({'license':'mixed; retain per-question provenance'}),now()))
            digest=hashlib.sha256((qid+dumps(q)).encode()).hexdigest()
            db.execute('INSERT INTO bank_questions VALUES(?,?,?,?,?,?,?,?,?,?)',(qid,'maintenance',q['subject'],q['stage'],q['kind'],q['status'],q['difficulty'],digest,dumps(q),now()))
            db.executemany('INSERT INTO bank_question_tags VALUES(?,?)',[(qid,t['id']) for t in q['tags']])
            if row['source_kind']=='bank':supersede(db,row['source_id'],replacement=q)
            supersede(db,row['published_id'],replacement=q)
            courses.sync_questions(db,[qid])
            db.execute("UPDATE bank_editor_items SET state='published',published_id=?,updated_at=? WHERE id=?",(qid,now(),item_id))
            event(db,item_id,row['revision'],'published',{**q,'review_note':body.review_note})
            return draft_view(db.execute('SELECT * FROM bank_editor_items WHERE id=?',(item_id,)).fetchone())

    @router.post('/drafts/{item_id}/withdraw')
    def withdraw(item_id: str, body: Revision):
        with connect(settings.database_path) as db:
            db.execute('BEGIN IMMEDIATE');row=locked_draft(db,item_id,body.revision)
            if not row['published_id']:raise HTTPException(422,'此题尚未发布')
            supersede(db,row['published_id'],invalidate=True)
            revision=row['revision']+1
            db.execute("UPDATE bank_editor_items SET state='withdrawn',revision=?,updated_at=? WHERE id=?",(revision,now(),item_id))
            event(db,item_id,revision,'withdrawn',{})
            return draft_view(db.execute('SELECT * FROM bank_editor_items WHERE id=?',(item_id,)).fetchone())

    return router
