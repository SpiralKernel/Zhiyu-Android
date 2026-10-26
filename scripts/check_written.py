"""一次真实图片评阅检查；使用原创题与临时数据库，会产生少量API用量。"""
import asyncio
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from PIL import Image,ImageDraw,ImageFont
from app import bank,bank_ai
from app.config import Settings
from app.db import initialize,connect


async def main():
    settings=Settings()
    if not settings.deepseek_api_key:raise SystemExit('请先配置DeepSeek Key')
    image=Image.new('RGB',(1200,700),'white');draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',42)
    for index,line in enumerate(['学生已经完成的解答','题目：解方程 2x+1=7。','我的过程：2x=7+1=8','所以：x=4']):draw.text((70,70+index*130),line,font=font,fill='black')
    out=io.BytesIO();image.save(out,'PNG')
    with tempfile.TemporaryDirectory(prefix='ai-teacher-written-real-') as temp:
        local=settings.model_copy(update={'database_path':Path(temp)/'test.sqlite3'})
        initialize(local.database_path)
        q={'id':'bank:test:written','subject':'math','stage':'junior','grade':None,'term':None,'stem':'解方程 2x+1=7，写出步骤。',
           'options':[],'answer':'x=3','steps':['两边同时减去1：2x=6。','两边同时除以2：x=3。'],'kind':'reference','status':'reference','difficulty':1,
           'knowledge_tags':['一元一次方程'],'type_tags':['移项解一元一次方程'],'tags_source':'source','issues':[],
           'provenance':{'dataset':'原创测试','url':'local-test','license':'original'}}
        with connect(local.database_path) as db:bank.import_records(db,'test',[q],{})
        with connect(local.database_path) as db:a=bank.next_question(db,bank.Selection())
        review=await bank_ai.assess(local,a['attempt_id'],'',[out.getvalue()])
        result=review['assessment']
        print(json.dumps({k:result[k] for k in ['verdict','transcribed_answer','reason','steps_feedback']},ensure_ascii=False,indent=2))
        assert result['verdict']=='incorrect','评阅建议与测试预期不符，请检查模型输出'
        with connect(local.database_path) as db:assert bank.profile(db)['completed']==0
        print('真实图片评阅通过，未核对前没有评分或掌握证据；实际学生数据库未修改。')


if __name__=='__main__':asyncio.run(main())
