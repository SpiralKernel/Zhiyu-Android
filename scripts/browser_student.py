"""当前学生浏览器验收：AI随时提问、即时求助、识图、学情/PDF与手机布局。"""
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
from PIL import Image
from playwright.sync_api import expect, sync_playwright

from app import bank
from app.db import connect, dumps, initialize
from app.math_learning import verified_pool

ROOT=Path(__file__).resolve().parents[1]
PREVIEWS=Path(os.environ.get('AI_TEACHER_PREVIEW_DIR',str(ROOT/'output/evals/student-ui')))


def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]


class MockAI(BaseHTTPRequestHandler):
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        system=data['messages'][0]['content'];user=data['messages'][-1]['content']
        user=user if isinstance(user,str) else user[0]['text']
        if '模拟网络失败' in user:
            self.send_response(502);self.end_headers();return
        if '为学生选择一轮加练计划' in system:
            content={'type_id':'m7a:subtract-negative','difficulty':1,'count':3,'reason':'近期独立题有重复错误，先检查减去负数的符号。'}
        elif '为家长生成' in system:
            value=json.loads(data['messages'][1]['content'])['learning_material'];notes=[e for e in value['evidence'] if e['id'] in value['focus_eligible_evidence_ids']]
            focus=[{'type_id':notes[-1]['type_id'],'finding':'对话与已核对练习显示，绝对值的距离含义还值得进一步检查。','evidence_ids':[notes[-1]['id']]}] if notes else []
            content={'summary':f"本期有{value['summary']['ai_questions']}次主动提问。请结合独立练习观察理解情况，提问本身不代表不会。",'strengths':[],'focus':focus,'parent_actions':['请孩子用数轴解释绝对值的含义。','先听推理，再核对答案。'],'next_steps':['独立尝试一道新的绝对值题。'],'uncertainty':'当前材料含对话和导入线索，不能替代充分的独立证据。'}
        elif '试卷识别助手' in system:
            content={'items':[{'label':'1','stem':'求-3的绝对值。','student_answer':'-3','reference_answer':'3','knowledge_ids':['absolute'],'question_type_id':'template:absolute','question_type_name':'负数的绝对值','suggested_verdict':'incorrect','confidence':'high','reason':'把距离写成了负数。','steps':['绝对值是到原点的距离。']}],'note':'已提取一道题。'}
        elif '学习证据复核员' in system:
            value=json.loads(data['messages'][1]['content'])['learning_material']
            content={'decisions':[{'candidate_index':c['candidate_index'],'verdict':'supported','evidence_quote':c['evidence_quote'],'reason':'这段作答将距离写成了负数，需要纠正符号。'} for c in value['candidates']]}
        elif '学习评阅助手' in system:
            content={'transcribed_answer':'根据中点关系，AM=5，MB=5。','verdict':'correct','reason':'中点把线段分成相等的两段。','confidence':'high',
                'part_feedback':[{'part_id':pid,'verdict':'correct','reason':'中点关系与长度计算正确。','evidence_quote':quote} for pid,quote in [('p1','AM=5'),('p2','MB=5')]]}
        else:
            value=json.loads(user);context=json.loads(data['messages'][1]['content'])['learning_material']
            confirmed=context.get('image_confirmed',False)
            quote=value['student_draft'][:100] if confirmed else value['message'][:100]
            content={'reply':'绝对值表示数轴上到原点的距离。距离不能是负数，所以要先看清数所在的位置。','check_question':'你能用距离解释-3的绝对值吗？','recognized_question':'求-3的绝对值。' if any(isinstance(m['content'],list) for m in data['messages']) else '',
              'transcribed_answer':'|-3|=-3' if any(isinstance(m['content'],list) for m in data['messages']) else '',
              'image_answer_status':'clear' if any(isinstance(m['content'],list) for m in data['messages']) else 'no_answer',
              'observations':[{'type_id':'m7a:absolute','type_name':'负数的绝对值','definition':'用距离解释绝对值。','goal_id':'math-7-1:u1:g3','kind':'difficulty' if confirmed else 'question_interest','evidence_source':'image_answer' if confirmed else 'message','evidence_quote':quote,'note':'正在了解绝对值的距离含义。'}]}
        payload=json.dumps({'choices':[{'message':{'content':json.dumps(content,ensure_ascii=False)}}]}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(payload)
    def log_message(self,*args):pass


def main():
    PREVIEWS.mkdir(parents=True,exist_ok=True)
    chrome=shutil.which('google-chrome-stable') or shutil.which('chromium')
    if not chrome:raise SystemExit('需要本机 Chrome')
    port,ai_port=free_port(),free_port();url=f'http://127.0.0.1:{port}'
    server=ThreadingHTTPServer(('127.0.0.1',ai_port),MockAI);threading.Thread(target=server.serve_forever,daemon=True).start()
    with tempfile.TemporaryDirectory(prefix='ai-teacher-ui-') as temp:
        db_path=Path(temp)/'test.sqlite3';initialize(db_path)
        q={'id':'written','subject':'math','stage':'junior','grade':7,'term':1,'stem':'M 是线段 AB 的中点，AB=10cm，求 AM，并写出过程。','kind':'reference','status':'reference','options':[],
           'answer':'AM=5cm','steps':['中点将线段分成相等的两段。','AM=AB÷2=5cm。'],'difficulty':1,'knowledge_tags':['线段中点'],'type_tags':['线段中点关系求长度'],'tags_source':'source','provenance':{}}
        choice={**q,'id':'choice','stem':'负数-3的绝对值是？','kind':'single_choice','status':'ready',
                'options':[{'key':'A','text':'3'},{'key':'B','text':'-3'}],'answer':'A',
                'knowledge_tags':['绝对值'],'type_tags':['负数的绝对值'],
                'steps':['绝对值表示数轴上到原点的距离，-3到原点的距离是3。']}
        q['stem']='M 是线段 AB 的中点，AB=10cm。（1）求 AM；（2）求 MB。写出过程。'
        q['answer']='AM=5cm，MB=5cm'
        q['annotation']={'schema_version':1,'response_format':'composite','difficulty':{'level':1,'basis':'根据中点定义求两段长度'},
            'parts':[{'id':pid,'prompt':prompt,'reference_answer':'5cm','knowledge_tags':['线段中点'],'type_tags':['线段中点关系求长度'],
                      'rubric':[{'id':'midpoint','description':'依据中点定义得到两段各等于AB的一半'}]} for pid,prompt in [('p1','求 AM，并说明依据。'),('p2','求 MB，并说明依据。')]]}
        with connect(db_path) as db:bank.import_records(db,'browser',[q,choice],{})
        env={**os.environ,'DATABASE_PATH':str(db_path),'AUTH_REQUIRED':'true','DIAGNOSTIC_CORE_ENABLED':'false','AI_PROVIDER':'deepseek',
             'AI_API_KEY':'browser-test-only','AI_BASE_URL':f'http://127.0.0.1:{ai_port}',
             'AI_MODEL':'mock','AI_VISION_MODEL':'mock'}
        process=subprocess.Popen([str(ROOT/'.venv/bin/uvicorn'),'app.main:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            with httpx.Client(trust_env=False) as client:
                for _ in range(100):
                    if process.poll() is not None:raise RuntimeError(process.stderr.read().decode())
                    try:
                        if client.get(url+'/api/v1/health').status_code==200:break
                    except httpx.ConnectError:pass
                    time.sleep(.1)
                else:raise RuntimeError('临时服务启动超时')
            errors=[]
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=chrome,headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1050},accept_downloads=True)
                page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append({'message':str(e),'stack':e.stack}));page.goto(url)
                try:expect(page.get_by_role('heading',name='创建账号')).to_be_visible()
                except Exception:
                    print('browser errors:',errors,flush=True)
                    print('session:',page.request.get(url+'/api/v1/auth/session').status,flush=True)
                    raise
                def menu(label):
                    page.get_by_label('打开菜单',exact=True).click()
                    page.locator('.menu-list').get_by_role('button',name=label,exact=True).click()
                def practice(kind=None):
                    menu('练习设置')
                    if kind: page.get_by_label('作答方式',exact=True).select_option(kind)
                    page.get_by_role('dialog',name='设置').get_by_role('button',name='开始练习',exact=True).click();expect(page.get_by_role('dialog',name='设置')).to_have_count(0)
                page.screenshot(path=PREVIEWS/'preview-student-login-desktop.png',full_page=True,animations='disabled')
                page.get_by_label('用户名',exact=True).fill('browser_student');page.get_by_label('密码',exact=True).fill('test-pass-123');page.get_by_label('称呼',exact=True).fill('小林')
                page.get_by_role('button',name='创建账号',exact=True).click()
                expect(page.locator('#work')).to_be_visible()
                expect(page.locator('.topbar')).to_be_visible();assert page.get_by_role('tab').count()==0
                menu('问 AI')
                assert page.request.get(url+'/api/v1/study/home').json()['completed']==0
                page.screenshot(path=PREVIEWS/'preview-teacher-home-desktop.png',full_page=True,animations='disabled')
                page.get_by_label('向 AI 提问',exact=True).fill('绝对值为什么不能是负数？');page.get_by_role('button',name='发送问题',exact=True).click()
                expect(page.get_by_text('已记录 · 正在了解这个题型，尚未判断掌握情况。',exact=True)).to_be_visible()
                assert page.request.get(url+'/api/v1/study/home').json()['completed']==0
                page.get_by_label('拍照问题目',exact=True).set_input_files({'name':'question.png','mimeType':'image/png','buffer':png()})
                page.get_by_label('向 AI 提问',exact=True).fill('这道图片题如何理解？');page.get_by_role('button',name='发送问题',exact=True).click()
                expect(page.locator('.recognized-question').first).to_be_visible()
                page.get_by_text('核对图片中的作答',exact=True).click()
                page.get_by_label('核对图片题干',exact=True).fill('求-3的绝对值。')
                page.get_by_label('核对图片作答',exact=True).fill('|-3|=-3')
                page.get_by_role('button',name='确认作答并分析',exact=True).click()
                expect(page.get_by_text('图片作答已核对，后续讨论会参考核对后的内容。',exact=True)).to_be_visible()
                assert page.request.get(url+'/api/v1/study/home').json()['completed']==0
                page.screenshot(path=PREVIEWS/'preview-teacher-chat-desktop.png',full_page=True,animations='disabled')
                page.get_by_label('向 AI 提问',exact=True).fill('模拟网络失败');page.get_by_role('button',name='发送问题',exact=True).click()
                expect(page.get_by_role('alert')).to_contain_text('AI 请求未完成');expect(page.get_by_label('向 AI 提问',exact=True)).to_have_value('模拟网络失败')
                page.get_by_role('button',name='新提问',exact=True).click()
                # 这段固定验证绝对值的无效数值与求助草稿；不依赖随机练习首题。
                page.route('**/api/v1/study/next',lambda route:route.continue_(post_data=json.dumps({**route.request.post_data_json,'type_id':'m7a:absolute'})))
                practice('numeric')
                expect(page.get_by_label('你的答案',exact=True)).to_be_visible();page.get_by_label('你的答案',exact=True).fill('-2')
                page.locator('#work').get_by_role('button',name='问 AI',exact=True).click();expect(page.get_by_role('dialog',name='这道题的 AI老师')).to_be_visible()
                page.get_by_label('就这道题向 AI 提问',exact=True).fill('看看我这一步');page.get_by_role('button',name='发送问题',exact=True).click()
                expect(page.get_by_role('dialog').locator('.message').last).to_contain_text('绝对值表示')
                page.get_by_role('button',name='关闭问答',exact=True).click();expect(page.get_by_label('你的答案',exact=True)).to_have_value('-2')
                page.get_by_label('你的答案',exact=True).fill('1/0');page.get_by_role('button',name='提交',exact=True).click();expect(page.get_by_role('alert')).to_contain_text('分母不能为零')
                expect(page.get_by_label('你的答案',exact=True)).to_have_value('1/0')
                page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.locator('#work').get_by_role('button',name='问 AI',exact=True).click();expect(page.get_by_role('dialog')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=PREVIEWS/'preview-teacher-drawer-mobile.png',full_page=False,animations='disabled')
                page.get_by_role('button',name='关闭问答',exact=True).click()
                page.unroute('**/api/v1/study/next')
                practice('written')
                expect(page.get_by_label('完整解答',exact=True)).to_be_visible();page.get_by_label('完整解答',exact=True).fill('由中点定义，AM=5。')
                page.get_by_label('第 1 问解答',exact=True).fill('AM=10÷2=5cm。')
                page.get_by_label('第 2 问解答',exact=True).fill('MB=AM=5cm。')
                page.get_by_label('上传手写答案',exact=True).set_input_files({'name':'answer.png','mimeType':'image/png','buffer':png()});page.get_by_role('button',name='提交 AI 评阅',exact=True).click()
                expect(page.get_by_role('heading',name='核对 AI 评阅')).to_be_visible()
                expect(page.get_by_role('heading',name='逐问反馈',exact=True)).to_be_visible()
                expect(page.get_by_text('当前提供文字反馈，分数待核对。',exact=True)).to_be_visible()
                page.screenshot(path=PREVIEWS/'preview-annotated-review-mobile.png',full_page=True,animations='disabled')
                page.get_by_label('你确认的结果',exact=True).select_option('correct');page.get_by_text('我已核对图片转写与评价',exact=True).click();page.get_by_role('button',name='确认并保存',exact=True).click()
                expect(page.get_by_role('heading',name='这道题答对了。')).to_be_visible()
                menu('练习设置');page.get_by_label('作答方式',exact=True).select_option('choice')
                page.get_by_role('dialog',name='设置').get_by_role('button',name='开始练习',exact=True).click();expect(page.get_by_role('dialog',name='设置')).to_have_count(0)
                expect(page.get_by_text('负数-3的绝对值是？',exact=True)).to_be_visible()
                page.locator('.choice').first.click()
                page.get_by_role('button',name='提交',exact=True).click()
                expect(page.get_by_role('heading',name='这道题答对了。')).to_be_visible()
                expect(page.get_by_text('参考答案：A. 3',exact=True)).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=PREVIEWS/'preview-bank-choice-mobile.png',full_page=True,animations='disabled')
                # 真实学生接口分配新题，验证不同答案输入和SVG几何图；只有AI为模拟。
                menu('练习设置');page.get_by_label('作答方式',exact=True).select_option('numeric');page.keyboard.press('Escape')
                target={'key':'expression-model'}
                page.route('**/api/v1/study/next',lambda route:route.continue_(post_data=json.dumps({**route.request.post_data_json,'type_id':'m7a:'+target['key'],'allow_challenge':False})))
                for key in ('expression-model','scientific','approximate','geometry'):
                    target['key']=key
                    with page.expect_response(lambda response:response.url.endswith('/api/v1/study/next')) as response:
                        practice('numeric')
                    work=response.value.json();q=work['question']
                    print('新题型界面：'+key+' / '+q['answer_mode'],flush=True)
                    expect(page.get_by_label('你的答案',exact=True)).to_be_visible()
                    if key=='geometry':
                        expect(page.locator('.question-diagram rect')).to_have_count(6)
                        page.screenshot(path=PREVIEWS/'preview-foundation-net-mobile.png',full_page=True,animations='disabled')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    with connect(db_path) as db:stored=json.loads(db.execute('SELECT data FROM questions WHERE id=?',(q['id'],)).fetchone()[0])
                    value=f"({stored['answer']})+0" if key=='expression-model' else stored['answer']
                    page.get_by_label('你的答案',exact=True).fill(value)
                    page.get_by_role('button',name='提交',exact=True).click()
                    expect(page.get_by_role('heading',name='这道题答对了。')).to_be_visible()
                page.unroute('**/api/v1/study/next')
                menu('习题导入');expect(page.get_by_role('heading',name='题目不用重新抄。')).to_be_visible()
                page.get_by_label('选择练习图片或PDF',exact=True).set_input_files({'name':'paper.png','mimeType':'image/png','buffer':png()});page.get_by_role('button',name='上传并预览',exact=True).click();page.get_by_role('button',name='开始识图',exact=True).click()
                expect(page.get_by_label('第1题题干',exact=True)).to_be_visible(timeout=15000);page.get_by_label('第1题评价',exact=True).select_option('incorrect');page.get_by_text('我已核对这道题',exact=True).click();page.get_by_role('button',name='保存核对结果',exact=True).click()
                expect(page.get_by_text('已保存核对结果，学习线索已更新。',exact=True)).to_be_visible()
                page.screenshot(path=PREVIEWS/'preview-import-current-mobile.png',full_page=True,animations='disabled')
                menu('学情报告');expect(page.get_by_role('heading',name='学习，一步一步看得见。')).to_be_visible()
                expect(page.get_by_text('已结合学习证据',exact=True)).to_be_visible(timeout=15000);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=PREVIEWS/'preview-parent-report-mobile.png',full_page=True,animations='disabled')
                page.set_viewport_size({'width':1440,'height':1050});page.screenshot(path=PREVIEWS/'preview-parent-report-desktop.png',full_page=True,animations='disabled')
                with page.expect_download() as download:page.get_by_role('link',name='导出 PDF',exact=True).click()
                demo=ROOT/'tmp/pdfs/report-demo-data.json';demo.parent.mkdir(parents=True,exist_ok=True);demo.write_text(json.dumps(page.request.get(url+'/api/v1/reports').json(),ensure_ascii=False))
                path=ROOT/'output/pdf/student-report-demo.pdf';path.parent.mkdir(parents=True,exist_ok=True);download.value.save_as(path)
                assert path.read_bytes().startswith(b'%PDF')
                page.get_by_label('报告时间',exact=True).select_option('month');expect(page.get_by_text('小林 · 7年级上册数学 · 最近30天',exact=True)).to_be_visible()
                # Add historical successes only to this disposable test DB,
                # proving time alone yields review advice instead of a failure.
                with connect(db_path) as db:
                    for i,q in enumerate(verified_pool(db)['m7a:absolute'][:5]):
                        stamp=(datetime.now(timezone.utc)-timedelta(days=40-i//3)).isoformat()
                        db.execute("INSERT INTO attempts(id,student_id,question_id,status,assigned_at,submitted_at,answer,result) VALUES(?,'demo',?,'submitted',?,?,?,?)",
                            (str(uuid.uuid4()),q['id'],stamp,stamp,q['answer'],dumps({'correct':True,'evidence_weight':1,'assisted':False})))
                page.get_by_label('报告时间',exact=True).select_option('all')
                expect(page.get_by_role('heading',name='值得再检查一下',exact=True)).to_be_visible()
                expect(page.get_by_text('建议复测',exact=True)).to_be_visible()
                expect(page.get_by_text('已结合学习证据',exact=True)).to_be_visible(timeout=15000)
                page.screenshot(path=PREVIEWS/'preview-memory-review-desktop.png',full_page=True,animations='disabled')
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=PREVIEWS/'preview-memory-review-mobile.png',full_page=True,animations='disabled')
                with page.expect_download() as download:page.get_by_role('link',name='导出 PDF',exact=True).click()
                download.value.save_as(ROOT/'output/pdf/memory-review-demo.pdf')
                menu('练习设置');page.get_by_label('年级',exact=True).select_option('8');page.get_by_role('dialog',name='设置').get_by_role('button',name='开始练习',exact=True).click();expect(page.get_by_role('dialog',name='设置')).to_have_count(0)
                expect(page.locator('.header-stage')).to_contain_text('8年级上册');expect(page.locator('.topbar')).to_be_visible()
                assert page.request.get(url+'/api/v1/teacher/threads').json()['items']==[]
                # Senior books use explicit volumes instead of a guessed semester.
                menu('练习设置')
                page.get_by_label('学段',exact=True).select_option('senior')
                page.get_by_label('高中教材册次',exact=True).select_option('math-senior-selective-2')
                assert not page.get_by_label('年级',exact=True).is_visible()
                page.screenshot(path=PREVIEWS/'preview-senior-settings-mobile.png',full_page=True,animations='disabled')
                page.get_by_role('dialog',name='设置').get_by_role('button',name='开始练习',exact=True).click();expect(page.get_by_role('dialog',name='设置')).to_have_count(0)
                assert page.request.get(url+'/api/v1/study/home').json()['book_id']=='math-senior-selective-2'
                assert page.request.get(url+'/api/v1/auth/session').json()['student']['stage']=='senior'
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                menu('练习设置')
                page.get_by_label('科目',exact=True).select_option('physics')
                page.get_by_label('高中教材册次',exact=True).select_option('physics-senior-selective-3')
                page.get_by_role('dialog',name='设置').get_by_role('button',name='开始练习',exact=True).click();expect(page.get_by_role('dialog',name='设置')).to_have_count(0)
                page.reload()
                expect(page.locator('.topbar')).to_be_visible()
                assert page.request.get(url+'/api/v1/study/home').json()['book_id']=='physics-senior-selective-3'
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                menu('账号');page.get_by_role('button',name='退出登录',exact=True).click();expect(page.get_by_role('heading',name='欢迎回来')).to_be_visible()
                page.get_by_role('button',name='新建学生',exact=True).click();page.get_by_label('用户名',exact=True).fill('second_student');page.get_by_label('密码',exact=True).fill('test-pass-123');page.get_by_role('button',name='创建账号',exact=True).click()
                expect(page.locator('#work')).to_be_visible()
                expect(page.locator('.topbar')).to_be_visible();assert page.request.get(url+'/api/v1/study/home').json()['completed']==0
                assert page.request.get(url+'/api/v1/teacher/threads').json()['items']==[]
                # Isolated new account: diagnosis first, then a bounded AI plan after real errors.
                page.route('**/api/v1/study/training-plans',lambda route:route.continue_(post_data=json.dumps({'type_id':'m7a:subtract-negative'})) if route.request.method=='POST' else route.continue_())
                menu('我的学情')
                page.get_by_role('button',name='安排下一轮',exact=True).click()
                expect(page.get_by_role('heading',name='独立诊断 / 复习',exact=True)).to_be_visible()
                page.get_by_role('button',name='开始 3 道独立新题',exact=True).click()
                for i in range(3):
                    expect(page.locator('.training-phase')).to_contain_text('独立复测')
                    current=page.request.post(url+'/api/v1/study/training-plans/'+page.request.get(url+'/api/v1/study/training-plans').json()['plan']['id']+'/next',data={}).json()['work']
                    with connect(db_path) as db:stored=json.loads(db.execute('SELECT data FROM questions WHERE id=?',(current['question']['id'],)).fetchone()[0])
                    page.get_by_label('你的答案',exact=True).fill(stored['answer'])
                    page.get_by_role('button',name='提交',exact=True).click()
                    expect(page.get_by_role('heading',name='这道题答对了。')).to_be_visible()
                    page.get_by_role('button',name='查看本轮结果' if i==2 else '继续本轮',exact=True).click()
                expect(page.locator('#work')).to_have_count(0)
                expect(page.locator('.training-card')).to_contain_text('本轮已完成')
                for _ in range(5):
                    work=page.request.post(url+'/api/v1/study/next',data={'type_id':'m7a:subtract-negative'}).json()
                    assert page.request.post(url+f"/api/v1/attempts/{work['attempt_id']}/answer",data={'answer':'999999'}).status==200
                page.reload()
                menu('我的学情')
                page.get_by_role('button',name='安排下一轮',exact=True).click()
                expect(page.get_by_role('heading',name='针对加练与独立复测',exact=True)).to_be_visible()
                page.get_by_role('button',name='开始 3 道加练 + 2 道复测',exact=True).click()
                pid=page.request.get(url+'/api/v1/study/training-plans').json()['plan']['id']
                for i in range(5):
                    expect(page.locator('.training-phase')).to_contain_text('加练' if i<3 else '独立复测')
                    current=page.request.post(url+f'/api/v1/study/training-plans/{pid}/next',data={}).json()['work']
                    if i==1:
                        page.reload()
                        expect(page.locator('.topbar')).to_be_visible()
                        menu('我的学情')
                        page.get_by_role('button',name='恢复本轮练习',exact=True).click()
                        assert page.request.post(url+f'/api/v1/study/training-plans/{pid}/next',data={}).json()['work']['attempt_id']==current['attempt_id']
                    with connect(db_path) as db:stored=json.loads(db.execute('SELECT data FROM questions WHERE id=?',(current['question']['id'],)).fetchone()[0])
                    page.get_by_label('你的答案',exact=True).fill(stored['answer'])
                    page.get_by_role('button',name='提交',exact=True).click()
                    expect(page.get_by_role('heading',name='这道题答对了。')).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    if i==0:page.screenshot(path=PREVIEWS/'preview-training-mobile.png',full_page=True,animations='disabled')
                    if i==3:page.screenshot(path=PREVIEWS/'preview-training-retest-mobile.png',full_page=True,animations='disabled')
                    page.get_by_role('button',name='查看本轮结果' if i==4 else '继续本轮',exact=True).click()
                expect(page.locator('#work')).to_have_count(0)
                expect(page.locator('.training-card')).to_contain_text('本轮已完成')
                expect(page.locator('.training-card')).to_contain_text('2 题计入有效独立证据')
                page.set_viewport_size({'width':1440,'height':1050})
                page.screenshot(path=PREVIEWS/'preview-training-result-desktop.png',full_page=True,animations='disabled')
                assert not errors,errors;browser.close()
            print('当前界面验收通过：零题答疑、拍照问题、自动学习线索、即时问答保留草稿、识图导入核对、AI学情/PDF导出、记忆到期复测提示、阶段及账号隔离、3题独立诊断、AI计划3题加练+2题复测、刷新恢复、390px布局。')
        finally:process.terminate();process.wait(timeout=10);server.shutdown();server.server_close()


def png():
    out=io.BytesIO();Image.new('RGB',(220,150),'white').save(out,format='PNG');return out.getvalue()


if __name__=='__main__':main()
