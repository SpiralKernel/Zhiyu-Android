import json
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.db import connect
from app.app_settings import request_ai,RuntimeSettings


def test_local_registration_connection_privacy_and_account_isolation(tmp_path):
    settings=Settings(database_path=tmp_path/'app.sqlite3',mobile_mode=True,registration_requires_invite=True,_env_file=None)
    with TestClient(create_app(settings)) as client:
        assert not client.get('/api/v1/auth/session').json()['registration_requires_invite']
        assert client.post('/api/v1/auth/register',json={'username':'alice','password':'password123'}).status_code==201
        assert client.get('/api/v1/auth/session').json()['student']['is_admin']
        data={'provider':'deepseek','model':'deepseek-flash','api_key':'test-secret-only'}
        saved=client.post('/api/v1/settings/connections',json=data)
        assert saved.status_code==200,saved.text
        cid=saved.json()['id']
        assert 'test-secret-only' not in saved.text
        state=client.get('/api/v1/settings').json()
        assert state['profile']['selected_connection']==cid and state['connections'][0]['has_key']
        with connect(settings.database_path) as db:
            raw=db.execute('SELECT data FROM ai_connections WHERE id=?',(cid,)).fetchone()[0]
        assert 'test-secret-only' not in raw
        assert client.put('/api/v1/settings/appearance',json={'skin':'forest','custom':{}}).status_code==200
        assert client.get('/api/v1/settings').json()['profile']['skin']=='forest'
        assert client.put('/api/v1/settings/appearance',json={'skin':'custom','custom':{'ink':'url(bad)'}}).status_code==422
        client.post('/api/v1/auth/logout',json={})
        client.post('/api/v1/auth/register',json={'username':'bobby','password':'password123'})
        assert client.get('/api/v1/settings').json()['connections']==[]
        assert client.post(f'/api/v1/settings/connections/{cid}/activate',json={}).status_code==404
        assert client.post(f'/api/v1/settings/connections/{cid}/test',json={}).status_code==404


def test_request_config_does_not_mutate_shared_server_settings():
    base=Settings(deepseek_api_key='server-only',_env_file=None);wrapped=RuntimeSettings(base)
    token=request_ai.set({'ai_provider':'mimo','deepseek_api_key':'personal-only'})
    try:
        assert wrapped.deepseek_api_key=='personal-only'
        assert wrapped.completion_options(42)=={'max_completion_tokens':42,'thinking':{'type':'disabled'}}
        assert base.deepseek_api_key=='server-only'
    finally:request_ai.reset(token)
    assert wrapped.deepseek_api_key=='server-only'


def test_device_token_guards_local_server(tmp_path):
    settings=Settings(database_path=tmp_path/'device.sqlite3',mobile_mode=True,mobile_token='private-device-token',_env_file=None)
    with TestClient(create_app(settings)) as client:
        assert client.get('/').status_code==403
        client.cookies.set('teacher_device_token','private-device-token')
        assert client.get('/').status_code==200
        assert client.get('/api/v1/auth/session').status_code==200
