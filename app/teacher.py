"""可随时提问的 AI 老师；答疑、拍照、题目上下文及对话学习线索。"""
import asyncio
import base64
import hashlib
import json
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Literal

from app import ai_policy, bank, bank_ai, learning, materials, memory, observations, observation_guard
from app.course_catalog import BOOK_MAP
from app.db import connect, dumps, now
from app.identity import book_id, subject_id
from app.math_catalog import TYPES, resolve_type
from app.observations import Observation
from app.question_types import template_type_id


class Context(BaseModel):
    source: str | None = Field(default=None,max_length=20)
    attempt_id: str | None = Field(default=None,max_length=60)
    import_id: str | None = Field(default=None,max_length=60)
    item_id: str | None = Field(default=None,max_length=60)


class Chat(Context):
    thread_id: str | None = Field(default=None,max_length=60)
    request_id: str = Field(default_factory=lambda:str(uuid.uuid4()),max_length=80)
    message: str = Field(min_length=1,max_length=1600)
    student_draft: str = Field(default='',max_length=12000)
    type_id: str | None = Field(default=None,max_length=100)


class Reply(BaseModel):
    reply: str = Field(min_length=1,max_length=6000)
    check_question: str = Field(default='',max_length=500)
    recognized_question: str = Field(default='',max_length=5000)
    observations: list[Observation] = Field(default_factory=list,max_length=3)
    transcribed_answer: str = Field(default='', max_length=12000)
    image_answer_status: Literal['clear', 'unclear', 'no_answer'] = 'no_answer'


class ConfirmImage(BaseModel):
    reviewed: bool
    recognized_question: str = Field(min_length=1, max_length=5000)
    student_answer: str = Field(min_length=1, max_length=12000)
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), max_length=80)


def require_thread(db, thread_id):
    row=db.execute('SELECT * FROM teacher_threads WHERE id=? AND student_id=current_student() AND book_id=?',(thread_id,book_id())).fetchone()
    if not row:raise HTTPException(404,'当前阶段的讨论不存在')
    return row


def resolve_context(db, value):
    if not value.source:
        if value.attempt_id or value.import_id or value.item_id:
            raise HTTPException(422,'请选择正确的题目来源')
        return None
    if value.source=='verified':
        if book_id()!='math-7-1':raise HTTPException(403,'该题不在当前学习阶段')
        row,q=learning.get_attempt(db,value.attempt_id)
        result={'source':'verified','attempt_id':row['id'],'stem':q['stem'],'submitted':row['status']=='submitted','type_id':resolve_type(template_type_id(q))}
        training=db.execute('SELECT plan_id,phase FROM training_items WHERE attempt_id=?',(row['id'],)).fetchone()
        if training:result.update(training_plan_id=training['plan_id'],training_phase=training['phase'],independent_if_helped=False)
        if row['status']=='submitted':result.update(answer=row['answer'],reference=q['answer'],steps=q['steps'])
        return result
    if value.source=='bank':
        row,q=bank.get_attempt(db,value.attempt_id)
        result={'source':'bank','attempt_id':row['id'],'stem':q['stem'],'options':q.get('options',[]),'submitted':row['status']=='submitted'}
        training=db.execute('SELECT plan_id,phase FROM training_items WHERE attempt_id=?',(row['id'],)).fetchone()
        if training:result.update(training_plan_id=training['plan_id'],training_phase=training['phase'],independent_if_helped=False)
        if row['status']=='submitted':result.update(answer=row['answer'],reference=q['answer'],steps=q['steps'])
        return result
    if value.source=='import':
        materials.require_import(db,value.import_id)
        row=db.execute('SELECT data FROM import_items WHERE id=? AND import_id=?',(value.item_id,value.import_id)).fetchone()
        if not row:raise HTTPException(404,'识别题目不存在')
        q=json.loads(row[0])
        return {'source':'import','import_id':value.import_id,'item_id':value.item_id,'stem':q['stem'],'diagram_description':q.get('diagram_description',''),'student_answer':q.get('student_answer',''),'submitted':bool(q.get('reviewed') and q.get('student_answer') and q.get('verdict') in {'correct','incorrect'}),'type_id':q.get('question_type_id')}
    raise HTTPException(422,'不支持的题目来源')


def mark_help(db, context):
    if not context:return
    if context['source']=='verified':
        db.execute("UPDATE attempts SET hint_used=1 WHERE id=? AND student_id=current_student() AND status='assigned'",(context['attempt_id'],))
    elif context['source']=='bank':
        db.execute("UPDATE bank_attempts SET assisted=1 WHERE id=? AND student_id=current_student() AND status='assigned'",(context['attempt_id'],))
    elif context['source']=='import':
        materials.require_import(db,context['import_id'])
        row=db.execute('SELECT data FROM import_items WHERE id=? AND import_id=?',(context['item_id'],context['import_id'])).fetchone()
        if row:
            data=json.loads(row[0]);data['assisted']=True
            db.execute('UPDATE import_items SET data=? WHERE id=?',(dumps(data),context['item_id']))


def storage(settings):
    return settings.database_path.resolve().parent/'teacher_images'


def image_context(db, thread_id):
    """Retain the latest photo topic even after the six-turn history window."""
    row=db.execute("SELECT response FROM teacher_messages WHERE thread_id=? AND json_array_length(response,'$.images')>0 ORDER BY created_at DESC,id DESC LIMIT 1",(thread_id,)).fetchone()
    if not row:return None
    photo=json.loads(row['response'])
    if photo.get('image_confirmation'):
        confirmed=db.execute('SELECT response FROM teacher_messages WHERE thread_id=? AND id=?',
            (thread_id,photo['image_confirmation']['message_id'])).fetchone()
        if confirmed:return json.loads(confirmed['response']).get('confirmed_image_context')
    if photo.get('recognized_question'):
        return {'source':'unconfirmed_image','stem':photo['recognized_question'],
                'student_answer':photo.get('transcribed_answer',''),'transcription_confirmed':False,
                'image_message_id':photo['message_id'],'submitted':False}
    return None


def create_router(settings):
    router=APIRouter(prefix='/api/v1/teacher',tags=['AI老师'])
    slots=asyncio.Semaphore(1)

    @router.get('/threads')
    def threads():
        with connect(settings.database_path) as db:
            return {'items':[dict(r) for r in db.execute('SELECT id,title,updated_at FROM teacher_threads WHERE student_id=current_student() AND book_id=? ORDER BY updated_at DESC LIMIT 30',(book_id(),))]}

    @router.get('/threads/{thread_id}')
    def thread(thread_id: str):
        with connect(settings.database_path) as db:
            row=require_thread(db,thread_id)
            messages=[{'id':r['id'],'message':r['message'],'response':json.loads(r['response']),'created_at':r['created_at']} for r in db.execute('SELECT * FROM teacher_messages WHERE thread_id=? ORDER BY created_at,id',(thread_id,))]
            from app.study import state
            current_notes={n['id']:n for t in state(db)['types'] for n in t.get('memory_history',[])}
            for message in messages:
                for note in message['response'].get('observations',[]):
                    stored=db.execute('SELECT dismissed FROM learning_observations WHERE id=? AND student_id=current_student()',(note['id'],)).fetchone()
                    note['dismissed']=bool(not stored or stored[0])
                    current=current_notes.get(note['id'])
                    if current:
                        note.update({k:current.get(k) for k in ('memory_status','resolved_at','resolved_by','superseded_by','expires_at','freshness')})
        return {'id':row['id'],'title':row['title'],'context':json.loads(row['context']),'items':messages}

    @router.post('/observations/{observation_id}/dismiss')
    def dismiss(observation_id: str):
        with connect(settings.database_path) as db:observations.dismiss(db,observation_id)
        return {'dismissed':True}

    async def discuss(body, images, confirmed_image=None):
        if not body.message.strip():raise HTTPException(422,'请输入想问的问题')
        async with slots:
            fingerprint = hashlib.sha256(dumps({**body.model_dump(),
                'images':[hashlib.sha256(im).hexdigest() for im in images],
                'confirmed_image':confirmed_image}).encode()).hexdigest()
            def retry(prior):
                response=json.loads(prior['response'])
                if prior['message']!=body.message or response.get('request_fingerprint',fingerprint)!=fingerprint:
                    raise HTTPException(409,'该请求已用于不同的消息、草稿或图片')
                return response
            with connect(settings.database_path) as db:
                original_image = None
                if confirmed_image:
                    require_thread(db,body.thread_id)
                    original_image=db.execute('SELECT response FROM teacher_messages WHERE id=? AND thread_id=?',
                        (confirmed_image['message_id'],body.thread_id)).fetchone()
                    if not original_image:raise HTTPException(404,'图片消息不存在')
                    original_image=json.loads(original_image['response'])
                    if not original_image.get('images'):raise HTTPException(422,'这条消息没有可核对的图片')
                    confirmation=original_image.get('image_confirmation')
                    if confirmation:
                        if confirmation['student_answer']!=body.student_draft or confirmation['recognized_question']!=confirmed_image['recognized_question']:
                            raise HTTPException(409,'这份图片作答已经核对；修改后请新开提问')
                        stored=db.execute('SELECT response FROM teacher_messages WHERE id=? AND thread_id=?',
                            (confirmation['message_id'],body.thread_id)).fetchone()
                        return json.loads(stored['response'])
                if not body.thread_id:
                    prior=db.execute('SELECT m.message,m.response FROM teacher_messages m JOIN teacher_threads t ON t.id=m.thread_id WHERE t.student_id=current_student() AND t.book_id=? AND m.request_id=?',(book_id(),body.request_id)).fetchone()
                    if prior:
                        return retry(prior)
                thread=require_thread(db,body.thread_id) if body.thread_id else None
                if thread:
                    prior=db.execute('SELECT message,response FROM teacher_messages WHERE thread_id=? AND request_id=?',(thread['id'],body.request_id)).fetchone()
                    if prior:
                        return retry(prior)
                saved_context=Context.model_validate(json.loads(thread['context'])) if thread else Context.model_validate(body.model_dump())
                context=resolve_context(db,saved_context)
                if context is None and thread and not images:
                    context=image_context(db,thread['id'])
                if confirmed_image:
                    context={'source':'confirmed_image','stem':confirmed_image['recognized_question'],
                             'student_answer':body.student_draft,'submitted':True,
                             'image_message_id':confirmed_image['message_id']}
                previous=db.execute('SELECT id,message,response FROM teacher_messages WHERE thread_id=? ORDER BY created_at DESC,id DESC LIMIT 6',(body.thread_id,)).fetchall() if thread else []
                if thread and db.execute('SELECT COUNT(*) FROM teacher_messages WHERE thread_id=?',(body.thread_id,)).fetchone()[0]>=60:
                    raise HTTPException(429,'这段讨论较长，请新开一次提问')
                from app.study import state
                summary=state(db)
                recalled=memory.retrieve(summary['types'],body.message+' '+body.student_draft+' '+(context or {}).get('stem',''),
                    focus_type_id=body.type_id or (context or {}).get('type_id'))
                current_types=recalled['items']
                catalog=[{'id':t['id'],'name':t['name'],'definition':t['can_do'],'goal_id':t['goal_id']} for t in TYPES] if book_id()=='math-7-1' else []
                book=BOOK_MAP[book_id()]
                from app.diagnostic_core import types_for_book
                catalog += [{'id':t['id'],'name':t['name'],'definition':t['can_do'],'goal_id':t['goal_id']} for t in types_for_book(book_id())]
                if book.get('stage') == 'senior':
                    from app.scoped_types import items
                    from app.senior_bank import types_for_book as senior_types
                    catalog += [{'id':t['id'],'name':t['name'],'definition':t['can_do'],'goal_id':t['goal_id']} for t in senior_types(db,book_id())]
                    catalog += [{'id':t['id'],'name':t['name'],'definition':t.get('description','')} for t in items(db)]
                else:
                    catalog += [{'id':r['id'],'name':json.loads(r['data'])['name'],'definition':json.loads(r['data']).get('description','')} for r in db.execute("SELECT id,data FROM question_types WHERE subject=? AND grade=? AND term=? AND json_extract(data,'$.source')='ai' LIMIT 80",(subject_id(),book['grade'],book['term']))]
                stage_goals=[{k:g[k] for k in ('id','name','can_do','checks','prerequisites')} for u in book['units'] for g in u['goals']]
            last_check = None
            if previous:
                latest=json.loads(previous[0]['response'])
                if latest.get('check_question') and ai_policy.history_turn(previous[0]['message'], latest, latest.get('student_draft', '')):
                    last_check={'message_id':previous[0]['id'],'question':latest['check_question'],
                                'teacher_reply':latest['reply']}
            material_context={'subject':subject_id(),'stage':book.get('stage','junior'),'book_id':book_id(),'book_title':book.get('title'),'grade':book['grade'],'term':book['term'],
                'stage_goals':stage_goals,'type_catalog':catalog,'student_state':current_types,
                'current_question':context,'focus_type_id':body.type_id,'last_check':last_check,
                'image_confirmed':bool(confirmed_image),'memory_context':recalled}
            if book.get('subject') == 'physics' and book.get('stage', 'junior') == 'junior':
                from app.physics_textbooks import requirements, types_for_book as textbook_types
                material_context['textbook_requirements'] = requirements(book_id())
                material_context['type_catalog'] += [
                    {'id':t['id'],'name':t['name'],'definition':t['can_do'],'goal_id':t['goal_id']}
                    for t in textbook_types(book_id())]
            history=[]
            for item in reversed(previous):
                answer=json.loads(item['response'])
                history.extend(ai_policy.history_turn(item['message'], answer, answer.get('student_draft', '')))
            content=dumps({'message':body.message,'student_draft':body.student_draft})
            if images:content=[{'type':'text','text':content}]+[{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(im).decode()}} for im in images]
            payload=ai_policy.messages(ai_policy.TEACHER,material_context,history,content)
            boundary = ai_policy.boundary_reason(body.message) or ai_policy.boundary_reason(body.student_draft)
            if boundary:
                reply = Reply.model_validate(ai_policy.boundary_reply(boundary))
            else:
                reply=await bank_ai.request_json(settings,payload,Reply,vision=bool(images))
                boundary = ai_policy.response_boundary_reason(reply)
                if boundary:
                    reply = Reply.model_validate(ai_policy.boundary_reply(boundary))
            if not images and not body.student_draft and observation_guard.ACK.fullmatch(body.message.strip()):
                # A polite acknowledgement cannot establish understanding, even in prose.
                reply.reply='不客气，我们用一个小问题再试试。'
                if not reply.check_question:
                    reply.check_question=last_check['question'] if last_check else '你能用自己的话解释刚才最关键的一步吗？'
            if not images:
                reply.transcribed_answer=''
                reply.image_answer_status='no_answer'
            elif not reply.transcribed_answer.strip() or '[看不清]' in reply.transcribed_answer:
                reply.image_answer_status='unclear' if reply.transcribed_answer else 'no_answer'
            evidence={'message':body.message,'student_draft':body.student_draft,
                      'image_answer':body.student_draft if confirmed_image else '',
                      'image_confirmed':bool(confirmed_image)}
            if boundary:
                accepted, rejected = [], [{'reason': boundary}]
            else:
                accepted,rejected=await observation_guard.validate(settings,reply.observations,evidence,material_context,last_check)
            thread_id=body.thread_id or str(uuid.uuid4());message_id=str(uuid.uuid4());timestamp=now()
            image_names=[]
            if images:
                directory=storage(settings)/thread_id;directory.mkdir(parents=True,exist_ok=True)
                for i,image in enumerate(images):
                    name=f'{message_id}-{i+1}.jpg';(directory/name).write_bytes(image);image_names.append(name)
            with connect(settings.database_path) as db:
                db.execute('BEGIN IMMEDIATE')
                if thread:require_thread(db,thread_id)
                else:db.execute('INSERT INTO teacher_threads VALUES(?,current_student(),?,?,?,?,?)',(thread_id,book_id(),body.message[:40],dumps(saved_context.model_dump()),timestamp,timestamp))
                result={**reply.model_dump(exclude={'observations'}),'thread_id':thread_id,'message_id':message_id,'provider':'rules' if boundary else settings.ai_provider,'score_recorded':False,'observations':[],
                        'policy_version':ai_policy.VERSION,'request_fingerprint':fingerprint,'student_draft':body.student_draft,
                        'boundary':{'version':ai_policy.BOUNDARY_VERSION,'blocked':bool(boundary),'reason':boundary},
                        'state_update':{'accepted':0,'rejected':rejected,
                            'review_unavailable':any(r['reason']=='review_unavailable' for r in rejected)},
                        'images':[{'name':name,'url':f'/api/v1/teacher/threads/{thread_id}/images/{name}'} for name in image_names]}
                db.execute('INSERT INTO teacher_messages VALUES(?,?,?,?,?,?)',(message_id,thread_id,body.request_id,body.message,dumps(result),timestamp))
                for proposal,validation in accepted:
                    proof={**validation,'evidence_source':proposal.evidence_source,
                           'image_message_id':confirmed_image['message_id'] if confirmed_image else None}
                    result['observations'].extend(observations.save(db,[proposal],message_id,
                        evidence[proposal.evidence_source],validation=proof))
                result['state_update']['accepted']=len(result['observations'])
                if confirmed_image and not boundary:
                    result['image_confirmation_of']=confirmed_image['message_id']
                    result['confirmed_image_context']=context
                    original_image['image_confirmation']={'message_id':message_id,
                        'recognized_question':confirmed_image['recognized_question'], 'student_answer':body.student_draft}
                    db.execute('UPDATE teacher_messages SET response=? WHERE id=? AND thread_id=?',
                        (dumps(original_image),confirmed_image['message_id'],thread_id))
                if not boundary:
                    mark_help(db,context)
                db.execute('UPDATE teacher_messages SET response=? WHERE id=?',(dumps(result),message_id))
                db.execute('UPDATE teacher_threads SET updated_at=? WHERE id=?',(timestamp,thread_id))
            return result

    @router.post('/threads/{thread_id}/messages/{message_id}/confirm-image')
    async def confirm_image(thread_id: str, message_id: str, body: ConfirmImage):
        if not body.reviewed or not body.student_answer.strip() or not body.recognized_question.strip():
            raise HTTPException(422,'请先核对图片中的题干和作答，再确认')
        return await discuss(Chat(thread_id=thread_id,request_id=body.request_id,
            message='请检查我核对后的图片作答。',student_draft=body.student_answer),[],
            {'message_id':message_id,'recognized_question':body.recognized_question})

    @router.post('/chat')
    async def chat(body: Chat):return await discuss(body,[])

    @router.post('/photo')
    async def photo(message: str=Form('请帮我理解这道题。',max_length=1600),thread_id: str|None=Form(None,max_length=60),request_id: str=Form('',max_length=80),
                    student_draft: str=Form('',max_length=12000),source: str|None=Form(None),attempt_id: str|None=Form(None),type_id: str|None=Form(None),
                    import_id: str|None=Form(None,max_length=60),item_id: str|None=Form(None,max_length=60),files: list[UploadFile]=File(...)):
        if not 1<=len(files)<=4:raise HTTPException(422,'请选择1—4张图片')
        if thread_id:
            with connect(settings.database_path) as db:require_thread(db,thread_id)
        images=[];total=0
        for file in files:
            data=await file.read(materials.MAX_FILE+1);total+=len(data)
            if len(data)>materials.MAX_FILE or total>materials.MAX_TOTAL:raise HTTPException(413,'单张图片最多20MB，合计最多40MB')
            images.append(materials.normalized_image(data))
        return await discuss(Chat(message=message,thread_id=thread_id,request_id=request_id or str(uuid.uuid4()),student_draft=student_draft,source=source,attempt_id=attempt_id,type_id=type_id,import_id=import_id,item_id=item_id),images)

    @router.get('/threads/{thread_id}/images/{name}')
    def image(thread_id: str,name: str):
        with connect(settings.database_path) as db:
            require_thread(db,thread_id)
            if not any(im['name']==name for r in db.execute('SELECT response FROM teacher_messages WHERE thread_id=?',(thread_id,)) for im in json.loads(r[0]).get('images',[])):
                raise HTTPException(404,'图片不存在')
        return FileResponse(storage(settings)/thread_id/name,media_type='image/jpeg')

    return router
