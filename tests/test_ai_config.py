import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException

from app import bank_ai
from app.config import Settings


def test_generic_and_legacy_configuration_with_explicit_override(tmp_path,monkeypatch):
    path=tmp_path/'config.env'
    path.write_text('AI_PROVIDER=mimo\nAI_API_KEY=local-test-only\nAI_BASE_URL=https://api.xiaomimimo.com/v1\nAI_MODEL=mimo-v2.6-flash\nAI_VISION_MODEL=mimo-v2.6-flash\n')
    settings=Settings(_env_file=path)
    assert settings.ai_provider=='mimo' and settings.deepseek_model=='mimo-v2.6-flash'
    assert settings.deepseek_api_key=='local-test-only'
    assert 'local-test-only' not in repr(settings)
    assert Settings(_env_file=path,deepseek_api_key='constructor-test').deepseek_api_key=='constructor-test'
    monkeypatch.setenv('DEEPSEEK_API_KEY','environment-test')
    assert Settings(_env_file=path).deepseek_api_key=='environment-test'
    monkeypatch.delenv('DEEPSEEK_API_KEY')
    path.write_text('DEEPSEEK_API_KEY=legacy-test\nDEEPSEEK_MODEL=deepseek-flash\n')
    assert Settings(_env_file=path).deepseek_api_key=='legacy-test'


def test_mimo_structured_call_uses_its_own_budget_and_reports_provider(monkeypatch):
    seen=[]
    def handler(request):
        seen.append(json.loads(request.content))
        assert str(request.url)=='https://api.xiaomimimo.com/v1/chat/completions'
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'tag_id':'tag:sample','difficulty':1,'reason':'先检查基础。'})}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    settings=Settings(ai_provider='mimo',deepseek_api_key='test-only',deepseek_base_url='https://api.xiaomimimo.com/v1',
                      deepseek_model='mimo-v2.6-flash',deepseek_vision_model='mimo-v2.6-flash',_env_file=None)
    result=asyncio.run(bank_ai.request_json(settings,[{'role':'user','content':'输出JSON'}],bank_ai.Plan))
    assert result.tag_id=='tag:sample'
    assert seen[0]['model']=='mimo-v2.6-flash' and seen[0]['max_completion_tokens']==2200
    assert seen[0]['thinking']=={'type':'disabled'} and 'max_tokens' not in seen[0]
    assert Settings(_env_file=None).completion_options(2200)=={'max_tokens':2200}


@pytest.mark.parametrize('finish_reasons', [('length','stop'), ('length','length'), ('content_filter',)])
def test_valid_json_from_unfinished_completion_is_not_accepted(monkeypatch,caplog,finish_reasons):
    calls=[]
    def handler(request):
        reason=finish_reasons[len(calls)]
        calls.append(json.loads(request.content))
        return httpx.Response(200,json={'choices':[{'finish_reason':reason,'message':{'content':json.dumps(
            {'tag_id':'tag:sample','difficulty':1,'reason':'private-student-content'})}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    settings=Settings(deepseek_api_key='test-only',_env_file=None)
    if finish_reasons[-1]=='stop':
        result=asyncio.run(bank_ai.request_json(settings,[{'role':'user','content':'输出JSON'}],bank_ai.Plan))
        assert result.tag_id=='tag:sample'
    else:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(bank_ai.request_json(settings,[{'role':'user','content':'输出JSON'}],bank_ai.Plan))
        assert exc.value.status_code==502
    assert len(calls)==len(finish_reasons)
    assert 'private-student-content' not in caplog.text
    if len(calls)==2:assert 'format_repair' in calls[1]['messages'][-1]['content']
