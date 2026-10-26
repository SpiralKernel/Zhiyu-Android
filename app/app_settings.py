"""Per-account appearance and encrypted AI connections; offline-first mobile support."""
import asyncio
import base64
import io
import json
import os
import uuid
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from app.db import connect, dumps
from app.identity import student_id, book_id

PROVIDERS = [
    dict(id='deepseek', name='DeepSeek', url='https://api.deepseek.com', model='deepseek-flash', logo='deepseek'),
    dict(id='mimo', name='小米 MiMo', url='https://api.xiaomimimo.com/v1', model='mimo-v2.6-flash', logo='mimo'),
    dict(id='qwen', name='通义千问', url='https://dashscope.aliyuncs.com/compatible-mode/v1', model='qwen-plus', logo='qwen'),
    dict(id='doubao', name='豆包', url='https://ark.cn-beijing.volces.com/api/v3', model='', logo='doubao'),
    dict(id='kimi', name='Kimi', url='https://api.moonshot.cn/v1', model='', logo='kimi'),
    dict(id='glm', name='智谱 GLM', url='https://open.bigmodel.cn/api/paas/v4', model='', logo='zhipu'),
    dict(id='siliconflow', name='硅基流动', url='https://api.siliconflow.cn/v1', model='', logo='siliconcloud'),
    dict(id='openai', name='OpenAI', url='https://api.openai.com/v1', model='', logo='openai'),
    dict(id='compatible', name='兼容接口', url='', model='', logo=''),
]
PROVIDER_MAP = {p['id']:p for p in PROVIDERS}
request_ai = ContextVar('personal_ai_options', default=None)


class RuntimeSettings:
    def __init__(self, base):
        self.base = base
    def __getattr__(self, name):
        options = request_ai.get()
        if options is not None and name in options:
            return options[name]
        return getattr(self.base, name)
    def completion_options(self, limit):
        if self.ai_provider == 'mimo':
            return {'max_completion_tokens':limit, 'thinking':{'type':'disabled'}}
        if self.ai_provider == 'openai':
            return {'max_completion_tokens':limit}
        return {'max_tokens':limit}
    @property
    def provider_name(self):
        return PROVIDER_MAP.get(self.ai_provider,{}).get('name',self.ai_provider)


def crypt(settings, value, decrypt=False):
    if settings.mobile_mode:
        try:
            from java import jclass
            vault = jclass('org.aiteacher.offline.SecretVault')
            return str(vault.decrypt(value) if decrypt else vault.encrypt(value))
        except ImportError:
            # Desktop integration tests explicitly supply their own standard vault.
            pass
    from cryptography.fernet import Fernet
    path = settings.database_path.parent / '.connections.key'
    try:
        with path.open('xb') as f:
            os.chmod(path, 0o600)
            f.write(Fernet.generate_key())
    except FileExistsError:
        pass
    key = Fernet(path.read_bytes())
    return key.decrypt(value.encode()).decode() if decrypt else key.encrypt(value.encode()).decode()


def profile(db):
    row=db.execute('SELECT data FROM app_profiles WHERE student_id=?',(student_id(),)).fetchone()
    return json.loads(row[0]) if row else {'skin':'paper','custom':{},'selected_connection':None}


def save_profile(db, value):
    db.execute('INSERT INTO app_profiles VALUES(?,?) ON CONFLICT(student_id) DO UPDATE SET data=excluded.data', (student_id(), dumps(value)))


def public_connection(value):
    return {k:v for k,v in value.items() if k not in {'secret'}} | {'has_key':bool(value.get('secret'))}


def active_options(settings, connection_id=None):
    with connect(settings.database_path) as db:
        p=profile(db)
        row=db.execute('SELECT data FROM ai_connections WHERE id=? AND student_id=?', (connection_id or p.get('selected_connection'),student_id())).fetchone()
    if not row:
        if connection_id:raise ValueError('原审核连接已删除，请重新建立任务')
        return {'deepseek_api_key':''} if settings.mobile_mode else None
    q=json.loads(row[0])
    return {'ai_provider':q['provider'],'deepseek_base_url':q['base_url'],
            'deepseek_model':q['model'],'deepseek_vision_model':q.get('vision_model',''),
            'deepseek_api_key':crypt(settings,q['secret'],True)}


class Connection(BaseModel):
    id: str | None = None
    provider: str = Field(max_length=30)
    name: str = Field(default='',max_length=60)
    base_url: str = Field(default='',max_length=500)
    model: str = Field(min_length=1,max_length=150)
    vision_model: str = Field(default='',max_length=150)
    api_key: str = Field(default='',max_length=4096,repr=False)


def checked_url(url, mobile=False):
    p=urlsplit(url.rstrip('/'))
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise HTTPException(422,'接口地址须为 HTTPS Base URL，不含账号、参数或片段')
    if not mobile and p.hostname not in {urlsplit(x['url']).hostname for x in PROVIDERS if x['url']}:
        # The public web deployment must not become an arbitrary-URL proxy.
        raise HTTPException(422,'自定义兼容地址仅在离线安卓版中启用')
    return url.rstrip('/')


class Appearance(BaseModel):
    skin: str = Field(default='paper',pattern='^(paper|rose|forest|ocean|lavender|custom)$')
    custom: dict[str,str] = Field(default_factory=dict,max_length=4)
    theme: Literal['system','light','dark'] = 'system'
    font_size: Literal['small','normal','medium','large','xlarge'] = 'normal'


class PracticePreferences(BaseModel):
    format: Literal['numeric','choice','written'] = 'numeric'
    unit: str = Field(default='',max_length=100)
    challenge: bool = True


def create_router(settings):
    router=APIRouter(prefix='/api/v1/settings',tags=['应用设置'])
    @router.get('')
    def status():
        with connect(settings.database_path) as db:
            p=profile(db)
            connections=[public_connection(json.loads(x[0])) for x in db.execute('SELECT data FROM ai_connections WHERE student_id=?',(student_id(),))]
        return {'profile':p,'connections':connections,'providers':PROVIDERS,'mobile':settings.mobile_mode}
    @router.put('/appearance')
    def appearance(body:Appearance):
        import re
        allowed={'background','paper','ink','accent'}
        if any(k not in allowed or not re.fullmatch('#[0-9a-fA-F]{6}',v) for k,v in body.custom.items()):
            raise HTTPException(422,'请选择有效的六位颜色')
        with connect(settings.database_path) as db:
            p=profile(db);p.update(skin=body.skin,custom=body.custom,theme=body.theme,font_size=body.font_size);save_profile(db,p)
        return p
    @router.put('/practice')
    def practice(body:PracticePreferences):
        from app.course_catalog import BOOK_MAP
        if body.unit and body.unit not in {u['id'] for u in BOOK_MAP[book_id()]['units']}:
            raise HTTPException(422,'章节不属于当前册次')
        with connect(settings.database_path) as db:
            p=profile(db)
            saved=p.setdefault('practice',{})
            saved[book_id()]=body.model_dump()
            save_profile(db,p)
        return body.model_dump()
    @router.post('/connections')
    def save_connection(body:Connection):
        if body.provider not in PROVIDER_MAP:raise HTTPException(422,'请选择接口厂商')
        preset=PROVIDER_MAP[body.provider]
        url=checked_url(body.base_url or preset['url'],settings.mobile_mode)
        with connect(settings.database_path) as db:
            old=db.execute('SELECT data FROM ai_connections WHERE id=? AND student_id=?',(body.id,student_id())).fetchone() if body.id else None
            if body.id and not old:raise HTTPException(404,'连接不存在')
            saved=json.loads(old[0]) if old else {}
            supplied_key=body.api_key.strip()
            secret=crypt(settings,supplied_key) if supplied_key else saved.get('secret')
            if not secret:raise HTTPException(422,'请输入 API Key')
            if not supplied_key and saved and (saved['provider']!=body.provider or saved['base_url']!=url):
                raise HTTPException(422,'更换厂商或地址时请重新输入 Key')
            q={'id':body.id or str(uuid.uuid4()),'provider':body.provider,'name':body.name.strip() or preset['name'],
               'base_url':url,'model':body.model.strip(),'vision_model':body.vision_model.strip(),'secret':secret}
            if not q['model']:raise HTTPException(422,'请输入模型名称')
            db.execute('INSERT INTO ai_connections VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(q['id'],student_id(),dumps(q)))
            p=profile(db);p['selected_connection']=q['id'];save_profile(db,p)
        return public_connection(q)
    @router.post('/connections/{cid}/activate')
    def activate(cid:str):
        with connect(settings.database_path) as db:
            if not db.execute('SELECT 1 FROM ai_connections WHERE id=? AND student_id=?',(cid,student_id())).fetchone():raise HTTPException(404,'连接不存在')
            p=profile(db);p['selected_connection']=cid;save_profile(db,p)
        return {'selected_connection':cid}
    @router.delete('/connections/{cid}')
    def remove(cid:str):
        with connect(settings.database_path) as db:
            db.execute('DELETE FROM ai_connections WHERE id=? AND student_id=?',(cid,student_id()))
            p=profile(db)
            if p.get('selected_connection')==cid:p['selected_connection']=None;save_profile(db,p)
        return {'deleted':True}
    @router.post('/connections/{cid}/test')
    async def test(cid:str):
        with connect(settings.database_path) as db:
            row=db.execute('SELECT data FROM ai_connections WHERE id=? AND student_id=?',(cid,student_id())).fetchone()
        if not row:raise HTTPException(404,'连接不存在')
        q=json.loads(row[0]);key=crypt(settings,q['secret'],True)
        try:
            async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:
                r=await client.post(q['base_url']+'/chat/completions',headers={'Authorization':'Bearer '+key},
                                   json={'model':q['model'],'messages':[{'role':'user','content':'Reply OK.'}],
                                         'stream':False})
                r.raise_for_status()
                if not r.json().get('choices'):raise ValueError()
        except (httpx.HTTPError,ValueError):raise HTTPException(502,'连接未通过，请检查 Key、模型名称和接口地址') from None
        return {'connected':True}
    @router.put('/avatar')
    async def avatar(file:UploadFile=File(...)):
        raw=await file.read(5*1024*1024+1)
        if len(raw)>5*1024*1024:raise HTTPException(413,'头像最多5MB')
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.width*image.height>20_000_000:raise ValueError()
                image=ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),(256,256));out=io.BytesIO();image.save(out,'JPEG',quality=85)
        except Exception:raise HTTPException(422,'请选择有效的 JPG、PNG 或 WebP 图片') from None
        directory=settings.database_path.parent/'avatars';directory.mkdir(exist_ok=True)
        path=directory/(student_id()+'.jpg');path.write_bytes(out.getvalue());path.chmod(0o600)
        return {'avatar':True}
    @router.get('/avatar')
    def get_avatar():
        path=settings.database_path.parent/'avatars'/(student_id()+'.jpg')
        if not path.exists():raise HTTPException(404,'尚未设置头像')
        return Response(path.read_bytes(),media_type='image/jpeg',headers={'Cache-Control':'no-store'})
    return router
