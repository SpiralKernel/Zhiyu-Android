"""File intake and resumable local AI calibration. Existing calibration is the gate."""
import asyncio
import hashlib
import io
import json
import re
import uuid
import base64
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pypdf import PdfReader
from starlette.concurrency import run_in_threadpool

from app.calibration import Source, create_job, get_task, import_report, job_view, publish
from app.db import audit, connect, now
from app.local_calibration import LocalModel, run_task, write_json

MAX_FILE = 12 * 1024 * 1024
MAX_TOTAL = 24 * 1024 * 1024
MAX_ITEMS = 100


def text_sources(text, label):
    text = text.strip()
    if not text:
        raise ValueError('文件没有可读取的题目文字')
    # Only split explicit consecutive top-level question numbers. Never rewrite a stem.
    heads = list(re.finditer(r'(?m)^\s*(\d{1,3})[.．、]\s*', text))
    consecutive = len(heads) > 1 and [int(h[1]) for h in heads] == list(range(1, len(heads)+1))
    if consecutive:
        if text[:heads[0].start()].strip():
            raise ValueError('题号前有正文，请使用每行一道题的 JSONL 文件，避免漏掉公共题干')
        blocks = [text[h.end():heads[i+1].start() if i+1 < len(heads) else len(text)].strip() for i,h in enumerate(heads)]
    else:
        blocks = [text]
    sources = []
    for i, block in enumerate(blocks, 1):
        answer = re.search(r'(?m)^\s*(?:参考)?答案\s*[:：]\s*', block)
        stem, reference = (block[:answer.start()].strip(), block[answer.end():].strip()) if answer else (block, '')
        sources.append(Source(stem=stem, reference_answer=reference, source_label=f'{label} · {i}'))
    return sources


def parse_file(name, data):
    if not data or len(data) > MAX_FILE:
        raise ValueError('单个文件须为 1 字节至 12MB')
    name = Path(name or '习题').name[:200]
    suffix = Path(name).suffix.lower()
    label = name + ' · SHA256:' + hashlib.sha256(data).hexdigest()
    if suffix in {'.jpg','.jpeg','.png','.webp'}:
        from app.materials import normalized_image
        image=normalized_image(data)
        return [Source(stem='',images=['data:image/jpeg;base64,'+base64.b64encode(image).decode()],source_label=label)]
    if suffix == '.pdf':
        try:
            pdf = PdfReader(io.BytesIO(data))
            if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 50:
                raise ValueError('请上传未加密、最多 50 页的 PDF')
            from app.mobile_pdf import available, render_pages
            if available():
                if len(pdf.pages)>4:raise ValueError('PDF 请每批选择最多4页')
                from app.materials import normalized_image
                return [Source(images=['data:image/jpeg;base64,'+base64.b64encode(normalized_image(raw)).decode()],source_label=f'{label} · 第{n}页')
                        for n,raw in enumerate(render_pages(data,1,len(pdf.pages)),1)]
            pages = []
            for page in pdf.pages:
                text = (page.extract_text() or '').strip()
                # Text extraction cannot safely reconstruct diagrams or scanned pages.
                if not text or len(page.images):
                    from app.mobile_pdf import available, render_pages
                    if available():
                        if len(pdf.pages)>4:raise ValueError('含题图的PDF请每批选择最多4页')
                        from app.materials import normalized_image
                        return [Source(images=['data:image/jpeg;base64,'+base64.b64encode(normalized_image(raw)).decode()],source_label=f'{label} · 第{n}页')
                                for n,raw in enumerate(render_pages(data,1,len(pdf.pages)),1)]
                    raise ValueError('PDF 含扫描页或题图；请改用包含完整题图的 JSON / JSONL 文件')
                pages.append(text)
            text = '\n'.join(pages)
        except ValueError:
            raise
        except Exception:
            raise ValueError('无法读取 PDF，请检查文件') from None
        return text_sources(text, label)
    if suffix not in {'.json', '.jsonl', '.txt', '.md'}:
        raise ValueError('支持 JSON、JSONL、TXT、Markdown 和文字版 PDF')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError('文字文件请使用 UTF-8 编码') from None
    if suffix in {'.txt', '.md'}:
        return text_sources(text, label)
    try:
        raw = json.loads(text) if suffix == '.json' else [json.loads(line) for line in text.splitlines() if line.strip()]
        if isinstance(raw, dict):
            raw = raw.get('questions', raw.get('sources', [raw]))
        if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_ITEMS:
            raise ValueError('每批需要 1—100 道题')
        sources = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError('每道题须是含 stem 的 JSON 对象')
            item = dict(item)
            if 'answer' in item and 'reference_answer' not in item:
                item['reference_answer'] = item.pop('answer')
            item.setdefault('source_label', label)
            sources.append(Source.model_validate(item))
        return sources
    except json.JSONDecodeError:
        raise ValueError('文件不是有效的 JSON / JSONL') from None


class IngestService:
    def __init__(self, settings):
        self.settings = settings
        self.directory = settings.database_path.resolve().parent / 'bank-ingest'
        self.tasks = {}
        self.slot = asyncio.Semaphore(1)

    def path(self, jid):
        try:
            if str(uuid.UUID(jid)) != jid:
                raise ValueError()
        except ValueError:
            raise HTTPException(404, '导入任务不存在') from None
        return self.directory / jid

    def read(self, jid):
        try:
            state=json.loads((self.path(jid)/'state.json').read_text())
            if self.settings.mobile_mode:
                from app.identity import student_id
                if state.get('student_id')!=student_id():raise HTTPException(404,'导入任务不存在')
            return state
        except FileNotFoundError:
            raise HTTPException(404, '导入任务不存在') from None

    def save(self, state):
        write_json(self.path(state['id'])/'state.json', state)

    def recover(self):
        for path in self.directory.glob('*/state.json'):
            state = json.loads(path.read_text())
            if state['status'] in {'queued', 'running'}:
                state.update(status='interrupted', error='服务重启，已完成的题目保留，可继续任务')
                self.save(state)

    async def close(self):
        active = list(self.tasks.values())
        for task in active:
            task.cancel()
        await asyncio.gather(*active, return_exceptions=True)

    def view(self, jid):
        state = self.read(jid)
        with connect(self.settings.database_path) as db:
            job = job_view(db, jid)
        return {**state, 'counts':job['counts'], 'items':[
            {'question_id':i['question_id'], 'stem':i['stem'], 'status':i['status'],
             'published_id':i['published_id'], 'issues':(i['result'] or {}).get('evaluation', {}).get('issues', [])}
            for i in job['items']]}

    def enqueue(self, jid):
        if jid in self.tasks:
            raise HTTPException(409, '任务已在运行')
        state = self.read(jid)
        state.update(status='queued', error='')
        self.save(state)
        task = asyncio.create_task(self.execute(jid))
        self.tasks[jid] = task
        task.add_done_callback(lambda _:self.tasks.pop(jid, None))

    async def execute(self, jid):
        state = self.read(jid)
        try:
            async with self.slot:
                state.update(status='running', error='')
                self.save(state)
                if self.settings.mobile_mode:
                    from app.app_settings import active_options
                    options=active_options(self.settings,state.get('connection_id'))
                    if not options.get('deepseek_api_key'):raise ValueError('请先连接AI')
                    engine=LocalModel(base_url=options['deepseek_base_url'],backend='openai',allow_remote=True,
                                      api_key=options['deepseek_api_key'],timeout=300,provider=options['ai_provider'])
                else:
                    engine = LocalModel(base_url=self.settings.local_audit_base_url, timeout=1800)
                async def progress(report):
                    def include():
                        with connect(self.settings.database_path) as db:
                            db.execute('BEGIN IMMEDIATE')
                            import_report(db, report)
                            publish(db, jid)
                    await run_in_threadpool(include)
                report = await run_task(self.path(jid)/'task.json', self.path(jid)/'result.json', engine,
                                        state['model'], vision_model=state.get('vision_model') or None,
                                        on_progress=progress)
                await progress(report)
                state.update(status='completed', finished_at=now())
        except asyncio.CancelledError:
            state.update(status='interrupted', error='任务已暂停，已入库题目保留')
            raise
        except Exception:
            # Never surface paths, credentials, HTTP bodies or model hidden reasoning.
            state.update(status='failed', error='AI 审核未完成，请检查网络和 AI 连接后继续任务' if self.settings.mobile_mode else 'AI 处理未完成，请检查本地模型服务后继续任务')
        finally:
            self.save(state)


def create_router(settings, service):
    from app.admin import require_admin
    router = APIRouter(prefix='/api/v1/admin/ingest', tags=['AI文件入库'], dependencies=[Depends(lambda:require_admin(settings))])

    async def models():
        if settings.mobile_mode:
            return [settings.deepseek_model] if settings.deepseek_api_key else []
        if not settings.local_audit_enabled:
            return []
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                response = await client.get(settings.local_audit_base_url.rstrip('/')+'/api/tags')
                response.raise_for_status()
                return [m['name'] for m in response.json()['models']]
        except (httpx.HTTPError, ValueError, KeyError):
            return []

    @router.get('/example')
    def example():
        return Response(json.dumps({'stem':'计算 -5 - (-4)。','reference_answer':'-1'},ensure_ascii=False)+'\n',media_type='application/x-ndjson',headers={'Content-Disposition':'attachment; filename=questions.jsonl'})

    @router.get('/status')
    async def status():
        installed = await models()
        return {'enabled':settings.local_audit_enabled or settings.mobile_mode, 'models':installed,
                'model':settings.deepseek_model if settings.mobile_mode else settings.local_audit_model,
                'vision_model':settings.deepseek_vision_model if settings.mobile_mode else settings.local_audit_vision_model}

    @router.get('/jobs')
    def jobs():
        from app.identity import student_id
        states = sorted((s for p in service.directory.glob('*/state.json') if (s:=json.loads(p.read_text()))
                         and (not settings.mobile_mode or s.get('student_id')==student_id())),
                        key=lambda s:s['created_at'], reverse=True)[:20]
        return {'items':[service.view(s['id']) for s in states]}

    @router.get('/jobs/{jid}')
    def view(jid:str):
        return service.view(jid)

    @router.post('/jobs', status_code=202)
    async def upload(book_id:str=Form(...), model:str=Form(''), files:list[UploadFile]=File(...)):
        if not settings.local_audit_enabled and not settings.mobile_mode:
            raise HTTPException(409, '此服务尚未开启本地 AI 入库')
        selected = model or (settings.deepseek_model if settings.mobile_mode else settings.local_audit_model)
        if selected not in await models():
            raise HTTPException(409, '本地模型未启动或尚未安装')
        if not 1 <= len(files) <= 8:
            raise HTTPException(422, '每次选择 1—8 个文件')
        sources, names, total = [], [], 0
        for file in files:
            data = await file.read(MAX_FILE+1)
            total += len(data)
            if total > MAX_TOTAL:
                raise HTTPException(413, '每批文件合计最多 24MB')
            sources.extend(await run_in_threadpool(parse_file, file.filename, data))
            names.append(Path(file.filename or '习题').name[:200])
        if not 1 <= len(sources) <= MAX_ITEMS:
            raise HTTPException(422, '每批需要 1—100 道题，请拆分文件')
        if len({s.id for s in sources}) != len(sources):
            raise HTTPException(422, '文件中题目 ID 重复')
        def prepare():
            with connect(settings.database_path) as db:
                db.execute('BEGIN IMMEDIATE')
                task = create_job(db, book_id, sources, limit=len(sources))
                audit(db, 'bank_file_ingest', {'job_id':task['job_id'], 'files':names, 'model':selected})
            jid = task['job_id']
            write_json(service.path(jid)/'task.json', task)
            from app.identity import student_id
            from app.app_settings import profile
            with connect(settings.database_path) as db:connection_id=profile(db).get('selected_connection') if settings.mobile_mode else None
            service.save({'id':jid, 'student_id':student_id(), 'book_id':book_id, 'model':selected,
                          'connection_id':connection_id,
                          'vision_model':settings.deepseek_vision_model if settings.mobile_mode else settings.local_audit_vision_model,
                          'files':names, 'created_at':now(), 'status':'queued', 'error':''})
            return jid
        jid = await run_in_threadpool(prepare)
        service.enqueue(jid)
        return service.view(jid)

    @router.post('/jobs/{jid}/resume')
    async def resume(jid:str):
        if not settings.local_audit_enabled and not settings.mobile_mode:
            raise HTTPException(409, '此服务尚未开启本地 AI 入库')
        if service.read(jid)['status'] not in {'failed', 'interrupted'}:
            raise HTTPException(409, '只能继续未完成的任务')
        service.enqueue(jid)
        return service.view(jid)

    @router.post('/jobs/{jid}/stop')
    async def stop(jid:str):
        service.read(jid)
        task = service.tasks.get(jid)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            state=service.read(jid)
            if state['status'] in {'queued','running'}:
                state.update(status='interrupted',error='任务已暂停，已入库题目保留')
                service.save(state)
        return service.view(jid)

    return router
