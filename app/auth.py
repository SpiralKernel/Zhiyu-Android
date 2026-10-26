"""本地账号与不透明会话；首次注册原子认领旧 demo 数据。"""
import hashlib
import hmac
import re
import secrets
import time
import unicodedata
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, model_validator
from typing import Literal

from app.db import connect, now
from app.identity import scope, student_id

COOKIE = 'teacher_session'


class Credentials(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=128)


class Stage(BaseModel):
    grade: int | None = Field(default=7, ge=7, le=12)
    term: int | None = Field(default=1, ge=1, le=2)
    subject: Literal['math','physics'] = 'math'
    stage: Literal['junior','senior'] = 'junior'
    book_id: str | None = Field(default=None, max_length=80)

    @model_validator(mode='after')
    def valid_course(self):
        if self.stage == 'senior':
            from app.course_catalog import BOOK_MAP
            book = BOOK_MAP.get(self.book_id)
            if not book or book.get('stage') != 'senior' or book['subject'] != self.subject:
                raise ValueError('请选择该科目的高中教材册次')
            self.grade, self.term = None, None
            return self
        if self.grade not in {7,8,9} or self.term not in {1,2}:
            raise ValueError('请选择初中年级和学期')
        if self.book_id and self.book_id != f'{self.subject}-{self.grade}-{self.term}':
            raise ValueError('册次与初中学习阶段不符')
        if self.subject=='physics' and self.grade<8:
            raise ValueError('人教版物理从八年级开始；提前学习请选择八上。')
        return self


class Registration(Credentials, Stage):
    nickname: str = Field(default='学习者', min_length=1, max_length=30)
    invitation_code: str = Field(default='', max_length=128)


class AccountProfile(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    nickname: str = Field(min_length=1, max_length=30)


def username(value):
    value = unicodedata.normalize('NFKC', value).strip().casefold()
    if not re.fullmatch(r'[\w.-]{2,40}', value):
        raise HTTPException(422, '用户名使用 2—40 个汉字、字母、数字、点或下划线')
    return value


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def identity(db, token):
    if not token or len(token) > 200:
        return None
    row = db.execute('''SELECT s.student_id,p.grade,p.term,COALESCE(ss.subject,'math') AS subject,a.username,t.nickname,
        COALESCE(ls.stage,'junior') AS stage,ls.book_id,
        EXISTS(SELECT 1 FROM admin_accounts ad WHERE ad.student_id=s.student_id) AS is_admin FROM auth_sessions s
        JOIN student_scopes p ON p.student_id=s.student_id JOIN accounts a ON a.student_id=s.student_id
        JOIN students t ON t.id=s.student_id LEFT JOIN student_subjects ss ON ss.student_id=s.student_id
        LEFT JOIN student_learning_scopes ls ON ls.student_id=s.student_id
        WHERE s.token_hash=? AND s.expires>?''', (digest(token), time.time())).fetchone()
    if not row:
        return None
    value = dict(row)
    if value['stage'] == 'senior':
        from app.course_catalog import BOOK_MAP
        book = BOOK_MAP.get(value['book_id'])
        if not book or book.get('stage') != 'senior' or book['subject'] != value['subject']:
            return None
        value.update(grade=None, term=None, book_title=book['title'])
    return value


def session(db, owner, response, request):
    token = secrets.token_urlsafe(32)
    db.execute('DELETE FROM auth_sessions WHERE expires<?', (time.time(),))
    db.execute('INSERT INTO auth_sessions VALUES(?,?,?)', (digest(token), owner, time.time()+7*86400))
    response.set_cookie(COOKIE, token, max_age=7*86400, httponly=True, samesite='strict', secure=request.url.scheme=='https', path='/')


def create_router(settings):
    router = APIRouter(prefix='/api/v1/auth', tags=['学生账号'])

    @router.put('/profile')
    def update_profile(body: AccountProfile):
        name = username(body.username)
        nickname = body.nickname.strip()
        if not nickname:
            raise HTTPException(422, '请填写称呼')
        with connect(settings.database_path) as db:
            db.execute('BEGIN IMMEDIATE')
            other = db.execute('SELECT student_id FROM accounts WHERE username=?', (name,)).fetchone()
            if other and other['student_id'] != student_id():
                raise HTTPException(409, '该用户名已存在')
            db.execute('UPDATE accounts SET username=? WHERE student_id=?', (name, student_id()))
            db.execute('UPDATE students SET nickname=? WHERE id=?', (nickname, student_id()))
        return {'student': {**(scope() or {}), 'username': name, 'nickname': nickname}}

    @router.get('/session')
    def status():
        with connect(settings.database_path) as db:
            needs_setup = db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0] == 0
        from app.course_catalog import BOOKS
        available_books = [{'id':b['id'],'subject':b['subject'],'title':b['title'],'stage':'senior'}
                           for b in BOOKS if b.get('stage') == 'senior']
        return {'authenticated': bool(scope()), 'student': scope(), 'needs_setup': needs_setup, 'mobile':settings.mobile_mode,
                'available_books': available_books,
                'registration_enabled': settings.registration_enabled,
                'registration_requires_invite': settings.registration_requires_invite and not settings.mobile_mode}

    @router.post('/register', status_code=201)
    def register(body: Registration, request: Request, response: Response):
        if not settings.registration_enabled:
            raise HTTPException(403, '当前学习空间只允许已有学生登录')
        name = username(body.username)
        salt = secrets.token_hex(16)
        hashed = password_hash(body.password, salt)
        with connect(settings.database_path) as db:
            db.execute('BEGIN IMMEDIATE')
            invite_hash = None
            if settings.registration_requires_invite and not settings.mobile_mode:
                from app.invites import code_hash
                invite_hash = code_hash(body.invitation_code)
                if not db.execute('SELECT 1 FROM registration_invites WHERE code_hash=? AND consumed_at IS NULL', (invite_hash,)).fetchone():
                    raise HTTPException(403, '请输入有效且未使用的邀请码')
            if db.execute('SELECT 1 FROM accounts WHERE username=?', (name,)).fetchone():
                raise HTTPException(409, '该用户名已存在')
            first = db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0] == 0
            owner = 'demo' if first else str(uuid.uuid4())
            if first:
                db.execute('UPDATE students SET nickname=? WHERE id=?', (body.nickname.strip() or '学习者', owner))
            else:
                db.execute('INSERT INTO students VALUES(?,?,?)', (owner, body.nickname.strip() or '学习者', now()))
            db.execute('INSERT INTO accounts VALUES(?,?,?,?,?)', (name, owner, salt, hashed, now()))
            # Legacy junior scope is retained separately; senior books have no
            # universal school-year/semester mapping.
            db.execute('INSERT INTO student_scopes VALUES(?,?,?)', (owner, body.grade or 7, body.term or 1))
            db.execute('INSERT INTO student_subjects VALUES(?,?)',(owner,body.subject))
            db.execute('INSERT INTO student_learning_scopes VALUES(?,?,?)',(owner,body.stage,body.book_id))
            if settings.mobile_mode:
                db.execute('INSERT OR IGNORE INTO admin_accounts VALUES(?,?)', (owner, now()))
            if invite_hash:
                changed = db.execute('UPDATE registration_invites SET consumed_at=?,used_by=? WHERE code_hash=? AND consumed_at IS NULL', (now(), owner, invite_hash)).rowcount
                if changed != 1:
                    raise HTTPException(403, '请输入有效且未使用的邀请码')
            session(db, owner, response, request)
        return {'authenticated': True, 'inherited_records': first}

    @router.post('/login')
    def login(body: Credentials, request: Request, response: Response):
        name = username(body.username)
        with connect(settings.database_path) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM login_failures WHERE created<?', (time.time()-900,))
            if db.execute('SELECT COUNT(*) FROM login_failures WHERE username=?', (name,)).fetchone()[0] >= 10:
                raise HTTPException(429, '尝试次数较多，请 15 分钟后再试')
            row = db.execute('SELECT * FROM accounts WHERE username=?', (name,)).fetchone()
            hashed = password_hash(body.password, row['salt'] if row else '00'*16)
            valid = bool(row and hmac.compare_digest(hashed, row['password_hash']))
            if valid:
                db.execute('DELETE FROM login_failures WHERE username=?', (name,))
                session(db, row['student_id'], response, request)
            else:
                db.execute('INSERT INTO login_failures VALUES(?,?)', (name, time.time()))
        if not valid:
            raise HTTPException(401, '用户名或密码不正确')
        return {'authenticated': True}

    @router.post('/logout')
    def logout(request: Request, response: Response):
        with connect(settings.database_path) as db:
            db.execute('DELETE FROM auth_sessions WHERE token_hash=?', (digest(request.cookies.get(COOKIE,'')),))
        response.delete_cookie(COOKIE, path='/')
        return {'authenticated': False}

    @router.post('/stage')
    def stage(body: Stage):
        with connect(settings.database_path) as db:
            if body.stage == 'junior':
                db.execute('UPDATE student_scopes SET grade=?,term=? WHERE student_id=?', (body.grade,body.term,student_id()))
            db.execute('INSERT INTO student_subjects VALUES(?,?) ON CONFLICT(student_id) DO UPDATE SET subject=excluded.subject',(student_id(),body.subject))
            db.execute('INSERT INTO student_learning_scopes VALUES(?,?,?) ON CONFLICT(student_id) DO UPDATE SET stage=excluded.stage,book_id=excluded.book_id', (student_id(),body.stage,body.book_id))
            # 保留旧记录，只重置当前选择范围。
            db.execute('DELETE FROM course_settings WHERE student_id=?', (student_id(),))
            db.execute('DELETE FROM student_preferences WHERE student_id=?', (student_id(),))
        return {'grade': body.grade, 'term': body.term, 'subject':body.subject,'stage':body.stage,'book_id':body.book_id}

    return router
