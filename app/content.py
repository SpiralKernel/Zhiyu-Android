"""离线题库更新协议v1：冻结完整快照、SHA256校验、原子安装，不传学生数据。"""
import asyncio
import hashlib
import json
import secrets
import uuid
from urllib.parse import urlsplit
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app import bank, courses
from app.admin import Draft, require_admin, validate_publish
from app.course_catalog import VERSION as CURRICULUM_VERSION
from app.db import audit, connect, dumps, now
from app.identity import scope

MAX_PACKAGE = 25 * 1024 * 1024


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()


def checksum(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def release(db):
    return db.execute('SELECT * FROM content_releases ORDER BY version DESC LIMIT 1').fetchone()


def manifest(row):
    return {'schema_version':1, 'publisher_id':row['publisher_id'], 'version':row['version'],
            'checksum':row['checksum'], 'item_count':row['item_count'],
            'curriculum_version':CURRICULUM_VERSION, 'created_at':row['created_at']}


class Package(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: int
    publisher_id: str = Field(min_length=36, max_length=36)
    version: int = Field(ge=1)
    curriculum_version: str
    items: list[dict] = Field(max_length=60000)
    retired: list[dict] = Field(default_factory=list,max_length=100000)


class Manifest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1]
    publisher_id: str = Field(min_length=36,max_length=36)
    version: int = Field(ge=1)
    checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    item_count: int = Field(ge=0,le=60000)
    curriculum_version: str = Field(max_length=100)
    created_at: str = Field(max_length=100)


async def remote_manifest(settings):
    try:
        value=Manifest.model_validate_json(await fetch(settings,'manifest'))
        uuid.UUID(value.publisher_id)
        return value.model_dump()
    except ValueError:
        raise HTTPException(502,'远程版本清单无效') from None


def original_valid(q):
    from app.challenges import validate_challenge
    from app.questions import validate_question
    try:
        return bool(q.get('stem') and q.get('hint') and
                    (validate_challenge(q) if q.get('provenance',{}).get('kind')=='original_challenge_template' else
                     validate_question(q) if q.get('provenance',{}).get('kind')=='original_template' else False))
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        return False


def publish_release(db):
    db.execute('BEGIN IMMEDIATE')
    pid = db.execute("SELECT value FROM content_meta WHERE key='publisher_id'").fetchone()
    if not pid:
        pid = str(uuid.uuid4());db.execute("INSERT INTO content_meta VALUES('publisher_id',?)",(pid,))
    else:pid = pid[0]
    items = []
    for row in db.execute("SELECT data FROM bank_questions WHERE status IN ('ready','reference') AND json_extract(data,'$.can_practice')=1 AND (json_extract(data,'$.provenance.teacher_reviewed')=1 OR json_extract(data,'$.provenance.kind')='original_rule_core' OR json_extract(data,'$.quality.calibration.status')='ai_reviewed') ORDER BY id"):
        q = json.loads(row[0])
        # 人工、规则及受约束AI标定分别校验；AI标定仍不认证独立学情。
        from app.diagnostic_core import verified as core_verified
        from app.calibration import calibrated
        if not core_verified(q) and not calibrated(q):
            try:validate_publish(Draft.model_validate(q),q)
            except (ValueError,HTTPException):continue
        items.append({'family':'bank', 'data':q})
    for row in db.execute('SELECT data FROM questions ORDER BY id'):
        q = json.loads(row[0])
        if original_valid(q):items.append({'family':'original','data':q})
    previous = release(db)
    retired=[{'id':r['id'],'evidence_invalidated':bool(json.loads(r['data']).get('evidence_invalidated'))}
             for r in db.execute("SELECT id,data FROM bank_questions WHERE status='superseded' ORDER BY id")]
    if previous and json.loads(previous['data'])['items'] == items and json.loads(previous['data']).get('retired',[])==retired:
        return manifest(previous)
    version = (previous['version']+1) if previous else 1
    package = {'schema_version':1, 'publisher_id':pid, 'version':version,
               'curriculum_version':CURRICULUM_VERSION, 'items':items, 'retired':retired}
    payload = encoded(package)
    if len(payload)>MAX_PACKAGE:raise ValueError('更新包超过25MiB，请先缩减题集；本版不支持分包')
    digest = hashlib.sha256(payload).hexdigest()
    db.execute('INSERT INTO content_releases VALUES(?,?,?,?,?,?)',(version,pid,digest,len(items),payload.decode(),now()))
    audit(db,'content_release',{'version':version,'items':len(items),'checksum':digest})
    return manifest(release(db))


def install_package(db, raw, expected):
    try:
        return _install_package(db, raw, expected)
    except BaseException:
        db.rollback()
        raise


def _install_package(db, raw, expected):
    if len(raw)>MAX_PACKAGE:raise ValueError('更新包超过25MiB')
    if hashlib.sha256(raw).hexdigest()!=expected['checksum']:raise ValueError('更新包校验失败，未修改题库')
    package = Package.model_validate_json(raw)
    if package.schema_version!=1 or package.curriculum_version!=CURRICULUM_VERSION:
        raise ValueError('更新包协议或课程版本不兼容，请先升级应用')
    uuid.UUID(package.publisher_id)
    if package.publisher_id!=expected['publisher_id'] or package.version!=expected['version'] or len(package.items)!=expected['item_count']:
        raise ValueError('更新包与版本清单不一致')
    validated=[];seen=set()
    for item in package.items:
        if set(item)!={'family','data'} or item['family'] not in {'bank','original'} or not isinstance(item['data'],dict):
            raise ValueError('更新包题目结构无效')
        q = item['data'];qid=q.get('id')
        if not isinstance(qid,str) or not 1<=len(qid)<=200 or (item['family'],qid) in seen:
            raise ValueError('更新包题目编号缺失或重复')
        seen.add((item['family'],qid))
        if item['family']=='original':
            if not original_valid(q):raise ValueError('原创题独立数学核验失败')
        else:
            from app.diagnostic_core import verified as core_verified
            rule=core_verified(q)
            from app.calibration import calibrated
            local_review=calibrated(q)
            if not rule and not local_review:
                form=Draft.model_validate(q);validate_publish(form,q)
            if (not rule and not local_review and not q.get('provenance',{}).get('teacher_reviewed')) or not q.get('can_practice') or q.get('status') not in {'ready','reference'}:
                raise ValueError('更新包含未经审核或已撤下的来源题')
        validated.append((item['family'],q))
    retired={}
    for entry in package.retired:
        if set(entry)!={'id','evidence_invalidated'} or not isinstance(entry['id'],str) or len(entry['id'])>200 or not isinstance(entry['evidence_invalidated'],bool):
            raise ValueError('更新包撤题标记无效')
        retired[entry['id']]=entry['evidence_invalidated']
    db.execute('BEGIN IMMEDIATE')
    installed=db.execute('SELECT * FROM content_installs WHERE publisher_id=?',(package.publisher_id,)).fetchone()
    if installed and package.version<installed['version']:raise ValueError('拒绝降级题库版本')
    if installed and package.version==installed['version']:
        if installed['checksum']!=expected['checksum']:raise ValueError('同一版本的校验和发生变化')
        return {'updated':False,'version':package.version,'items':0}
    own_pid=db.execute("SELECT value FROM content_meta WHERE key='publisher_id'").fetchone()
    if own_pid and own_pid[0]==package.publisher_id:raise ValueError('不能把本站发布内容作为远程题库重复安装')
    pid=package.publisher_id;namespace='remote:'+pid+':'
    previous={ (r['family'],r['remote_id']):dict(r) for r in db.execute('SELECT * FROM content_installed_items WHERE publisher_id=?',(pid,))}
    db.execute('UPDATE content_installed_items SET active=0 WHERE publisher_id=?',(pid,))
    source_id='remote:'+pid
    db.execute('INSERT OR IGNORE INTO bank_sources VALUES(?,?,?)',(source_id,dumps({'publisher_id':pid,'transport':'content-v1'}),now()))
    changed=[]
    for family, original in validated:
        q=dict(original);remote_id=q['id'];old=previous.get((family,remote_id))
        table='bank_questions' if family=='bank' else 'questions'
        local_id=old['local_id'] if old else namespace+remote_id
        if family=='original':
            # 与打包时已有的同一原创题共用记录，避免重复计分。
            digest=hashlib.sha256(q['stem'].encode()).hexdigest()
            native=db.execute('SELECT id,data FROM questions WHERE content_hash=?',(digest,)).fetchone()
            if native:
                if json.loads(native['data'])['answer']!=q['answer']:raise ValueError('原创题答案与本机同题冲突')
                local_id=native['id']
        q['id']=local_id
        if family=='bank':
            tags=[]
            for kind,field in [('knowledge','knowledge_tags'),('type','type_tags')]:
                for label in dict.fromkeys(q[field]):
                    origin='model_review' if q.get('quality',{}).get('calibration') else 'source' if q.get('provenance',{}).get('kind')=='original_rule_core' else 'teacher'
                    tid=bank.register_tag(db,q['subject'],q.get('stage','junior'),kind,label,origin)
                    tags.append({'id':tid,'kind':kind,'label':label,'origin':origin})
            q['tags']=tags
        existing=db.execute('SELECT data FROM '+table+' WHERE id=?',(local_id,)).fetchone()
        if existing:
            stored=json.loads(existing[0])
            # 同一快照不可被换答案；撤下后允许恢复相同原始快照的状态。
            comparable=dict(stored)
            for field in ['status','can_practice']:comparable.pop(field,None)
            candidate=dict(q)
            for field in ['status','can_practice']:candidate.pop(field,None)
            if family=='bank' and comparable!=candidate:raise ValueError('远端修改了已发布题目快照，请发布新题目版本')
            if family=='bank':db.execute('UPDATE bank_questions SET status=?,data=? WHERE id=?',(q['status'],dumps(q),local_id))
        elif family=='original':
            db.execute('INSERT INTO questions VALUES(?,?,?,?,?)',(local_id,q['knowledge_id'],digest,dumps(q),now()))
        else:
            db.execute('INSERT INTO bank_questions VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (local_id,source_id,q['subject'],q.get('stage','junior'),q['kind'],q['status'],q['difficulty'],checksum(q),dumps(q),now()))
            db.executemany('INSERT INTO bank_question_tags VALUES(?,?)',[(local_id,t['id']) for t in tags]);changed.append(local_id)
        db.execute('INSERT INTO content_installed_items VALUES(?,?,?,?,1) ON CONFLICT(publisher_id,family,remote_id) DO UPDATE SET local_id=excluded.local_id,active=1',(pid,family,remote_id,local_id))
    from app.admin import supersede
    for key,old in previous.items():
        if key not in seen and old['family']=='bank':supersede(db,old['local_id'],invalidate=retired.get(old['remote_id'],False))
    courses.sync_questions(db,changed)
    db.execute('INSERT INTO content_installs VALUES(?,?,?,?) ON CONFLICT(publisher_id) DO UPDATE SET version=excluded.version,checksum=excluded.checksum,installed_at=excluded.installed_at',
               (pid,package.version,expected['checksum'],now()))
    audit(db,'content_installed',{'publisher_id':pid,'version':package.version,'items':len(validated)})
    return {'updated':True,'version':package.version,'items':len(validated)}


def source_settings(settings):
    url=settings.content_source_url.rstrip('/');parts=urlsplit(url)
    if not url or not settings.content_source_key:raise HTTPException(409,'尚未配置远程题库源；当前在线题库已直接使用后台发布内容')
    if parts.username or parts.password or parts.query or parts.fragment or (parts.scheme!='https' and not (parts.scheme=='http' and parts.hostname in {'127.0.0.1','localhost','::1'})):
        raise HTTPException(422,'题库源须为HTTPS地址，本机测试可用回环HTTP')
    return url,{'Authorization':'Bearer '+settings.content_source_key}


async def fetch(settings, path):
    url,headers=source_settings(settings)
    try:
        async with httpx.AsyncClient(timeout=35,follow_redirects=False) as client:
            async with client.stream('GET',url+'/api/v1/content/feed/'+path,headers=headers) as response:
                if response.status_code!=200:raise HTTPException(502,'远程题库暂不可用或更新凭证无效')
                content=bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content)>MAX_PACKAGE:raise HTTPException(502,'远程更新包超过25MiB')
                return bytes(content)
    except httpx.HTTPError:
        raise HTTPException(502,'连接远程题库失败，原题库未修改') from None


def create_router(settings):
    router=APIRouter(prefix='/api/v1/content',tags=['题库联网更新'])
    slots=asyncio.Semaphore(1)

    def feed_access(request):
        if scope() and scope().get('is_admin'):
            require_admin(settings);return
        key=settings.content_feed_key
        if len(key)<32 or not secrets.compare_digest(request.headers.get('authorization',''), 'Bearer '+key):
            raise HTTPException(401,'需要题库更新凭证')

    @router.get('/status')
    def status():
        with connect(settings.database_path) as db:
            row=release(db)
            installs=[dict(r) for r in db.execute('SELECT publisher_id,version,installed_at FROM content_installs')]
        return {'remote_configured':bool(settings.content_source_url and settings.content_source_key),
                'release':manifest(row) if row else None, 'installed':installs}

    @router.get('/check')
    async def check():
        if settings.mobile_mode:
            from app.mobile_content import check as mobile_check
            return await mobile_check(settings)
        if not settings.content_source_url:return {**status(),'available':False,'message':'当前在线题库直接使用已发布内容，无需下载。'}
        data=await remote_manifest(settings)
        with connect(settings.database_path) as db:
            installed=db.execute('SELECT version,checksum FROM content_installs WHERE publisher_id=?',(data.get('publisher_id',''),)).fetchone()
        available=not installed or data['version']>installed['version']
        return {**status(),'available':available,'remote':data,'message':'发现新的题库版本。' if available else '题库已是最新版本。'}

    @router.post('/update')
    async def update():
        async with slots:
            if settings.mobile_mode:
                from app.mobile_content import update as mobile_update
                return await mobile_update(settings)
            expected=await remote_manifest(settings)
            raw=await fetch(settings,'package?version='+str(expected['version']))
            with connect(settings.database_path) as db:return install_package(db,raw,expected)

    @router.post('/publish')
    def publish():
        require_admin(settings)
        with connect(settings.database_path) as db:return publish_release(db)

    @router.get('/feed/manifest')
    def feed_manifest(request: Request):
        feed_access(request)
        with connect(settings.database_path) as db:row=release(db)
        if not row:raise HTTPException(404,'尚未发布更新包')
        return manifest(row)

    @router.get('/feed/package')
    def feed_package(request: Request,version: int=Query(default=0,ge=0)):
        feed_access(request)
        with connect(settings.database_path) as db:
            row=db.execute('SELECT * FROM content_releases WHERE version=?',(version,)).fetchone() if version else release(db)
        if not row:raise HTTPException(404,'更新包不存在')
        return Response(row['data'].encode(),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="ai-teacher-content-v{row["version"]}.json"','ETag':'"'+row['checksum']+'"'})

    return router
