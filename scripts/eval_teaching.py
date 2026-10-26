"""Synthetic teaching checks. Offline by default; --live uses configured API only.

All accounts, discussions and observations live in a temporary database. Results
contain synthetic examples and no key. Automated evidence checks are separate
from the human rubric for mathematical correctness and teaching quality.
"""
import argparse
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from app import ai_policy
from app.config import Settings
from app.db import connect, dumps, now
from app.main import create_app
from app.observation_guard import Review
from app.teacher import Reply


def image_bytes(case):
    image=Image.new('RGB',(700,220),'white');draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',30)
    draw.text((25,30),'Q: Find |-3|.',fill='black',font=font)
    draw.text((25,105),'Student: |-3| = '+('???' if case['image']=='unclear' else '-3'),fill='black',font=font)
    out=io.BytesIO();image.save(out,'PNG');return out.getvalue()


def seed_check(settings,case):
    if not case.get('prior_check'):return None,None
    tid,mid=str(uuid.uuid4()),str(uuid.uuid4())
    response={'reply':case.get('teacher_reply','先从数轴到原点的距离思考。'),'check_question':case['prior_check'],'observations':[],
              'recognized_question':'','thread_id':tid,'message_id':mid,'images':[]}
    with connect(settings.database_path) as db:
        db.execute("INSERT INTO teacher_threads VALUES(?,'demo','math-7-1','评测检查','{}',?,?)",(tid,now(),now()))
        db.execute('INSERT INTO teacher_messages VALUES(?,?,?,?,?,?)',(mid,tid,'seed','请解释绝对值。',dumps(response),now()))
    return tid,mid


def simulated(case,check_id):
    async def fake(settings,messages,schema,vision=False):
        value=json.loads(messages[1]['content'])['learning_material']
        if schema is Review:
            return schema(decisions=[{'candidate_index':c['candidate_index'],'verdict':case.get('review','unsupported'),
                'evidence_quote':c['evidence_quote'],'reason':'模拟复核：仅验证学情写入规则，不代表真实模型质量。'} for c in value['candidates']])
        return Reply(reply='模拟教学回复。',check_question='请解释为什么距离非负。',
            recognized_question='求-3的绝对值。' if vision else '',
            transcribed_answer='|-3|=-3' if vision and case.get('image')=='wrong' else '',
            image_answer_status='clear' if vision and case.get('image')=='wrong' else 'no_answer',
            observations=[{'type_id':'' if case.get('new_type') else 'm7a:absolute',
                'type_name':case.get('new_type','负数的绝对值'),'definition':'分析绝对值作用范围和距离的非负性。',
                'goal_id':'math-7-1:u1:g3','kind':case['proposal_kind'],'evidence_quote':case['quote'],
                'evidence_source':case.get('source','message'),'check_message_id':check_id or '',
                'note':'模拟授课模型提出的学习判断。'}])
    return fake


def run_case(case,live):
    with tempfile.TemporaryDirectory(prefix='teacher-eval-') as temp:
        settings=Settings(database_path=Path(temp)/'eval.sqlite3')
        if not live:settings.deepseek_api_key='eval-test-only'
        with TestClient(create_app(settings)) as client:
            assert client.post('/api/v1/auth/register',json={'username':'synthetic_eval','password':'evaluation-only-123','grade':7,'term':1}).status_code==201
            tid,mid=seed_check(settings,case)
            def requests():
                if case.get('image'):
                    r=client.post('/api/v1/teacher/photo',data={'message':case['message']},files={'files':('synthetic.png',image_bytes(case),'image/png')})
                else:
                    r=client.post('/api/v1/teacher/chat',json={'message':case['message'],'thread_id':tid})
                if r.status_code!=200:return r,None
                first=r.json()
                if case.get('confirm_answer'):
                    r=client.post(f"/api/v1/teacher/threads/{first['thread_id']}/messages/{first['message_id']}/confirm-image",json={
                        'reviewed':True,'recognized_question':'求-3的绝对值。','student_answer':case['confirm_answer']})
                return r,first
            if live:r,first=requests()
            else:
                with patch('app.bank_ai.request_json',simulated(case,mid)):r,first=requests()
            value=r.json();kinds={n['kind'] for n in value.get('observations',[])}
            checks={'response_ok':r.status_code==200,'forbidden_absent':not(kinds & set(case.get('forbidden',[]))),
                    'required_present':set(case.get('required',[]))<=kinds,
                    'no_independent_score':client.get('/api/v1/study/home').json()['completed']==0}
            if case.get('confirm_answer'):
                checks['photo_unconfirmed_no_diagnosis']=first is not None and not any(n['kind'] in {'difficulty','reviewed_success','understanding_check','guided_success'} for n in first.get('observations',[]))
            return {'case_id':case['id'],'automated_pass':all(checks.values()),'checks':checks,
                    'observed_kinds':sorted(kinds),'reply':value.get('reply'),'state_update':value.get('state_update'),
                    'http_status':r.status_code,'manual_review':{'status':'pending','rubric':case['rubric']}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='调用本机配置的模型；只写临时数据库')
    parser.add_argument('--limit',type=int,default=0,help='最多运行多少样例，0表示全部')
    parser.add_argument('--cases',type=Path,default=ROOT/'tests/fixtures/teaching_evals.json')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.live and not Settings().deepseek_api_key:raise SystemExit('未配置API Key，未执行真实评测。')
    cases=json.loads(args.cases.read_text())
    if args.limit>0:cases=cases[:args.limit]
    results=[]
    for case in cases:
        result=run_case(case,args.live);results.append(result)
        print(case['id']+': '+('PASS' if result['automated_pass'] else 'REVIEW/FAIL'),flush=True)
    output=args.output or ROOT/'output/evals'/('teaching-'+('live-' if args.live else 'offline-')+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'mode':'live' if args.live else 'simulated','policy_version':ai_policy.VERSION,
        'model':Settings().deepseek_model if args.live else 'simulated','case_count':len(results),
        'automated_pass_count':sum(r['automated_pass'] for r in results),
        'mathematical_and_pedagogical_quality':'requires human review; automated checks do not measure overall accuracy',
        'results':results},ensure_ascii=False,indent=2))
    print('结果：'+str(output),flush=True)
    if not all(r['automated_pass'] for r in results):raise SystemExit(1)


if __name__=='__main__':main()
