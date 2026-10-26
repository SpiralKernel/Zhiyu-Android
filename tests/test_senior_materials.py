"""A senior OCR request must use the selected volume, never 'junior None grade'."""
import asyncio
import json

import httpx

from app.config import Settings
from app.course_catalog import BOOK_MAP
from app.db import initialize
from app.identity import current
from app.materials import recognize_page


def test_senior_ocr_context_and_goal_filtering(tmp_path,monkeypatch):
    settings=Settings(database_path=tmp_path/'ocr.sqlite3',deepseek_api_key='mock-only',_env_file=None)
    initialize(settings.database_path)
    bid='physics-senior-selective-2'
    goal=BOOK_MAP[bid]['units'][1]['goals'][0]['id'];captured=[]
    def handle(request):
        captured.append(json.loads(request.content))
        item={'label':'1','stem':'100匝线圈磁通量由0.01Wb变为0.03Wb，用时0.1s，求平均感应电动势。',
            'student_answer':'20V','reference_answer':'20V','knowledge_ids':['addition'],
            'goal_ids':[goal,'math-7-1:u1:g1'],'question_type_name':'由磁通量变化率求平均感应电动势',
            'suggested_verdict':'correct','confidence':'high'}
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'items':[item],'note':''})}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(handle)))
    token=current.set({'student_id':'demo','subject':'physics','stage':'senior','book_id':bid,'grade':None,'term':None})
    try:result=asyncio.run(recognize_page(settings,b'test-image','completed'))
    finally:current.reset(token)
    context=json.loads(captured[0]['messages'][1]['content'])['learning_material']
    assert context['stage']=='senior' and context['book_id']==bid and context['subject']=='physics'
    assert 'None年级' not in captured[0]['messages'][0]['content']
    assert BOOK_MAP[bid]['title'] in captured[0]['messages'][0]['content']
    assert result.items[0].goal_ids==[goal] and result.items[0].knowledge_ids==[]
