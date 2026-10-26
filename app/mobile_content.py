"""Signed, content-only offline bank: no accounts, keys, uploads or learning records."""
import base64
import gzip
import hashlib
import json
from pathlib import Path

import httpx
from fastapi import HTTPException
from app.db import connect, dumps, audit

MAX_BYTES=40*1024*1024
PUBLIC_KEY=Path(__file__).parent/'data/mobile-bank-public.pem'
FEED='https://121-40-146-217.sslip.io/mobile-bank/'


def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


def verify_manifest(value):
    v=dict(value);signature=v.pop('signature',None)
    if v.get('schema')!=1 or type(v.get('version')) is not int or v['version']<1 or not isinstance(signature,str):raise ValueError('更新清单无效')
    data=canonical(v);key=PUBLIC_KEY.read_text()
    try:
        from java import jclass
        valid=bool(jclass('org.aiteacher.offline.UpdateVerifier').verify(base64.b64encode(data).decode(),signature,key))
        if not valid:raise ValueError('更新签名无效')
    except ImportError:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.exceptions import InvalidSignature
        try:load_pem_public_key(key.encode()).verify(base64.b64decode(signature),data,padding.PKCS1v15(),hashes.SHA256())
        except (InvalidSignature,ValueError,TypeError):raise ValueError('更新签名无效') from None
    return v


def installed(db):
    row=db.execute("SELECT value FROM content_meta WHERE key='mobile_bank_version'").fetchone()
    return int(row[0]) if row else 0


def install(db, raw, manifest):
    expected=verify_manifest(manifest)
    if len(raw)>MAX_BYTES or hashlib.sha256(raw).hexdigest()!=expected.get('sha256'):raise ValueError('更新包校验失败')
    if expected['version']<=installed(db):return {'updated':False,'version':installed(db)}
    from app.bank import content_hash
    from app.courses import sync_questions
    db.execute('BEGIN IMMEDIATE');count=0;changed=[];seen=set();retired=set();total=0
    try:
        import io
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:
            while line:=f.readline(4*1024*1024+1):
                total+=len(line)
                if len(line)>4*1024*1024 or total>200*1024*1024:raise ValueError('题库更新包过大')
                x=json.loads(line);kind=x['kind'];row=x.get('row')
                if kind=='source':db.execute('INSERT OR IGNORE INTO bank_sources VALUES(?,?,?)',row)
                elif kind=='tag':db.execute('INSERT OR IGNORE INTO bank_taxonomy VALUES(?,?,?,?,?,?,?)',row)
                elif kind=='retired':retired={tuple(v) for v in x['hashes']}
                elif kind=='question':
                    q=json.loads(row[8]);qid=q['id']
                    if qid!=row[0] or qid in seen or q['subject'] not in {'math','physics'}:raise ValueError('题库编号或科目无效')
                    seen.add(qid)
                    old=db.execute('SELECT data FROM bank_questions WHERE id=?',(qid,)).fetchone()
                    if old:
                        saved=json.loads(old[0]);immutable=('stem','options','answer','steps','kind')
                        if any(saved.get(k)!=q.get(k) for k in immutable):raise ValueError('题目内容变化，需新建题目版本以保留历史')
                        if not saved.get('quality',{}).get('mobile_release'):continue
                    q.setdefault('quality',{})['mobile_release']={'version':expected['version']}
                    row[8]=dumps(q)
                    if old:db.execute('UPDATE bank_questions SET source_id=?,subject=?,stage=?,kind=?,status=?,difficulty=?,content_hash=?,data=? WHERE id=?',(*row[1:9],qid))
                    else:db.execute('INSERT INTO bank_questions VALUES(?,?,?,?,?,?,?,?,?,?)',row)
                    db.execute('DELETE FROM bank_question_tags WHERE question_id=?',(qid,))
                    db.executemany('INSERT INTO bank_question_tags VALUES(?,?)',[(qid,t['id']) for t in q.get('tags',[])])
                    count+=1;changed.append(qid)
                else:raise ValueError('更新包行类型无效')
        if len(seen)!=expected['count']:raise ValueError('题库条目数量不符')
        for qid,data in db.execute('SELECT id,data FROM bank_questions'):
            q=json.loads(data)
            if q.get('quality',{}).get('mobile_release') and (q['subject'],content_hash(q)) in retired:
                q.update(status='superseded',can_practice=False,evidence_invalidated=True)
                db.execute("UPDATE bank_questions SET status='superseded',data=? WHERE id=?",(dumps(q),qid))
        for start in range(0,len(changed),200):sync_questions(db,changed[start:start+200],force=True)
        db.execute("INSERT INTO content_meta VALUES('mobile_bank_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(expected['version']),))
        if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('题库外键校验失败')
        audit(db,'mobile_bank_install',{'version':expected['version'],'count':count,'sha256':expected['sha256']})
        db.commit()
    except BaseException:db.rollback();raise
    return {'updated':True,'version':expected['version'],'count':count}


async def remote_manifest():
    try:
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
            r=await client.get(FEED+'manifest.json');r.raise_for_status()
        if len(r.content)>8192:raise ValueError()
        value=r.json();verify_manifest(value);return value
    except (httpx.HTTPError,ValueError,KeyError):raise HTTPException(502,'暂时无法检查更新，离线做题不受影响') from None


async def check(settings):
    value=await remote_manifest()
    with connect(settings.database_path) as db:current=installed(db)
    available=value['version']>current
    return {'available':available,'remote':{'version':value['version'],'count':value['count']},'message':'发现新题库' if available else '题库已是最新版本'}


async def update(settings):
    value=await remote_manifest();version=value['version']
    with connect(settings.database_path) as db:
        if version<=installed(db):return {'updated':False,'version':installed(db)}
    try:
        async with httpx.AsyncClient(timeout=90,follow_redirects=False) as client:
            async with client.stream('GET',FEED+f'bank-{version}.jsonl.gz') as r:
                r.raise_for_status();parts=[];total=0
                async for chunk in r.aiter_bytes():
                    total+=len(chunk)
                    if total>MAX_BYTES:raise ValueError('更新包过大')
                    parts.append(chunk)
        from starlette.concurrency import run_in_threadpool
        def apply():
            import sqlite3
            path=settings.database_path;backup=path.parent/'backups'/f'before-mobile-update-{version}.sqlite3';backup.parent.mkdir(exist_ok=True)
            with sqlite3.connect(path) as src,sqlite3.connect(backup) as dst:src.backup(dst)
            backup.chmod(0o600)
            with connect(path) as db:return install(db,b''.join(parts),value)
        return await run_in_threadpool(apply)
    except (httpx.HTTPError,ValueError):raise HTTPException(502,'题库更新未完成，原题库和学习记录已保留') from None
