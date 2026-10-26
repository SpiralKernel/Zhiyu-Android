"""Draft ownership, durable strokes, account rename and no accidental grading."""
import json
from fastapi.testclient import TestClient
from app.config import Settings
from app.db import connect
from app.main import create_app


def test_private_drafts_persist_and_do_not_grade(tmp_path):
    settings=Settings(database_path=tmp_path/'draft.sqlite3', _env_file=None)
    with TestClient(create_app(settings)) as c:
        assert c.put('/api/v1/auth/profile',json={'username':'alice','nickname':'爱丽丝'}).status_code==401
        assert c.post('/api/v1/auth/register',json={'username':'alice','password':'password123'}).status_code==201
        work=c.post('/api/v1/study/next',json={}).json()
        # Study can return either a bank question or a verified template.
        endpoint=f"/api/v1/writing/{work['source']}/{work['attempt_id']}"
        assert c.get(endpoint).json()=={'strokes':[]}
        strokes={'strokes':[{'width':3,'points':[[100,200,.3],[150,250,.7]]}]}
        assert c.put(endpoint,json=strokes).status_code==200
        assert c.get(endpoint).json()==strokes
        assert c.put(endpoint,json={'strokes':[{'width':3,'points':[[1001,0,.5]]}]}).status_code==422
        assert c.put('/api/v1/writing/verified/not-an-id',json=strokes).status_code==404
        with connect(settings.database_path) as db:
            table='bank_attempts' if work['source']=='bank' else 'attempts'
            before=dict(db.execute(f'SELECT * FROM {table} WHERE id=?',(work['attempt_id'],)).fetchone())
        assert before['status']=='assigned' and before['result'] is None
        assert c.post('/api/v1/auth/logout',json={}).status_code==200
        c.post('/api/v1/auth/register',json={'username':'bobby','password':'password123'})
        assert c.get(endpoint).status_code==404
        assert c.put(endpoint,json=strokes).status_code==404
        c.post('/api/v1/auth/logout',json={})
        c.post('/api/v1/auth/login',json={'username':'alice','password':'password123'})
        changed=c.put('/api/v1/auth/profile',json={'username':'Alice.New','nickname':'小知'})
        assert changed.status_code==200,changed.text
        assert changed.json()['student']['username']=='alice.new'
        assert c.get(endpoint).json()==strokes
        assert c.put('/api/v1/auth/profile',json={'username':'bobby','nickname':'新名字'}).status_code==409
        assert c.put('/api/v1/auth/profile',json={'username':'alice.new','nickname':' '}).status_code==422
        c.post('/api/v1/auth/logout',json={})
        assert c.post('/api/v1/auth/login',json={'username':'alice','password':'password123'}).status_code==401
        assert c.post('/api/v1/auth/login',json={'username':'alice.new','password':'password123'}).status_code==200
    with TestClient(create_app(settings)) as c:
        c.post('/api/v1/auth/login',json={'username':'alice.new','password':'password123'})
        assert c.get(endpoint).json()==strokes


def test_all_font_sizes_are_saved(tmp_path):
    with TestClient(create_app(Settings(database_path=tmp_path/'font.sqlite3',_env_file=None))) as c:
        c.post('/api/v1/auth/register',json={'username':'alice','password':'password123'})
        assert c.put('/api/v1/settings/practice',json={'format':'written','unit':'','challenge':False}).status_code==200
        assert c.get('/api/v1/settings').json()['profile']['practice']['math-7-1']['format']=='written'
        assert c.put('/api/v1/settings/practice',json={'unit':'other-book-unit'}).status_code==422
        for size in ['small','normal','medium','large','xlarge']:
            r=c.put('/api/v1/settings/appearance',json={'skin':'lavender','font_size':size})
            assert r.status_code==200
            assert c.get('/api/v1/settings').json()['profile']['font_size']==size
