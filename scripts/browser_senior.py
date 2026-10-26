"""Exercise the shipped senior bank in a temporary app with a local mock model.

Real questions, authentication, selection, grading, photo upload and report APIs;
the model is mocked. No real student database or paid model calls are used.
"""
import io
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
from PIL import Image
from playwright.sync_api import sync_playwright, expect

from app.course_catalog import BOOKS
from app.db import connect, initialize
from app.senior_bank import import_batch, validate_peer, prepare_batch
from scripts.browser_student import free_port
from scripts.audit_senior_bank import audit

ROOT=Path(__file__).resolve().parents[1]


class MockAI(BaseHTTPRequestHandler):
    def do_POST(self):
        request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        context=json.loads(request['messages'][1]['content'])['learning_material']
        parts=context.get('question_annotation',{}).get('parts',[])
        result={'transcribed_answer':context.get('student_text',''), 'verdict':'correct',
            'reason':'本地模拟模型，仅验证界面与保存流程。','confidence':'high',
            'part_feedback':[{'part_id':p['id'],'verdict':'correct','reason':'模拟逐问反馈。',
                'evidence_quote':p['reference_answer'][:100]} for p in parts]}
        payload=json.dumps({'choices':[{'message':{'content':json.dumps(result,ensure_ascii=False)}}]}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(payload)
    def log_message(self,*args):pass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-foundations',action='store_true')
    args=parser.parse_args()
    coverage=audit(args.include_foundations)
    if not coverage['complete']:raise SystemExit('完整覆盖与独立复核门槛尚未通过')
    peerfile='senior_foundations_peer_review.json' if args.include_foundations else 'senior_peer_review.json'
    suffix='foundations' if args.include_foundations else 'luna'
    peer=json.loads((ROOT/'app/data'/peerfile).read_text())
    values=[json.loads((ROOT/f'app/data/senior_{s}_{suffix}.json').read_text()) for s in ('math','physics')]
    for value in values:validate_peer(value,peer)
    chrome=shutil.which('google-chrome-stable') or shutil.which('chromium')
    if not chrome:raise SystemExit('需要本机Chrome')
    previews=Path(os.environ.get('AI_TEACHER_PREVIEW_DIR','/tmp/ai-teacher-senior-real-previews'));previews.mkdir(parents=True,exist_ok=True)
    port,model_port=free_port(),free_port();url=f'http://127.0.0.1:{port}'
    model=ThreadingHTTPServer(('127.0.0.1',model_port),MockAI)
    threading.Thread(target=model.serve_forever,daemon=True).start()
    with tempfile.TemporaryDirectory(prefix='senior-bank-browser-') as temp:
        path=Path(temp)/'test.sqlite3';initialize(path)
        for value in values:
            with connect(path) as db:import_batch(db,value)
        if args.include_foundations:
            # Some foundation chapters intentionally use written tasks only.
            # Keep the existing reviewed choice pool, but require written work
            # below to come from the newly added foundation batch.
            original_peer=json.loads((ROOT/'app/data/senior_peer_review.json').read_text())
            for subject in ('math','physics'):
                original=json.loads((ROOT/f'app/data/senior_{subject}_luna.json').read_text())
                validate_peer(original,original_peer)
                choice_batch=copy.deepcopy(original)
                choice_batch['items']=[i for i in original['items'] if i['decision']=='passed'
                    and i['question']['kind'] in {'single_choice','multiple_choice'}]
                with connect(path) as db:import_batch(db,choice_batch)
        env={**os.environ,'DATABASE_PATH':str(path),'AUTH_REQUIRED':'true','DIAGNOSTIC_CORE_ENABLED':'false',
            'AI_PROVIDER':'deepseek','AI_API_KEY':'local-mock-only','AI_MODEL':'mock','AI_VISION_MODEL':'mock',
            'AI_BASE_URL':f'http://127.0.0.1:{model_port}','REGISTRATION_REQUIRES_INVITE':'false'}
        process=subprocess.Popen([str(ROOT/'.venv/bin/uvicorn'),'app.main:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],
            cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            with httpx.Client(trust_env=False) as client:
                for _ in range(200):
                    if process.poll() is not None:raise RuntimeError(process.stderr.read().decode())
                    try:
                        if client.get(url+'/api/v1/health').status_code==200:break
                    except httpx.ConnectError:pass
                    time.sleep(.1)
                else:raise RuntimeError('临时服务启动超时')
            completed=[];errors=[]
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=chrome,headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':390,'height':844})
                page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(url);expect(page.get_by_role('heading',name='建立你的学习空间')).to_be_visible()
                # Render every released stem/option, not only random examples.
                render_cases=[]
                for value in values:
                    records,_=prepare_batch(value)
                    for q in records:
                        if q['status']=='quarantine':continue
                        for label,text in [('stem',q['stem']),*[(o['key'],o['text']) for o in q['options']]]:
                            render_cases.append({'id':q['annotation_source_question_id'],'field':label,'text':text})
                formula_errors=page.evaluate(r'''cases => {
                    const errors=[];
                    for(const c of cases){
                        const n=document.createElement('div');n.textContent=c.text;
                        renderMathInElement(n,{delimiters:[{left:'$$',right:'$$',display:true},
                            {left:'\\[',right:'\\]',display:true},{left:'$',right:'$',display:false},
                            {left:'\\(',right:'\\)',display:false}],throwOnError:false,trust:false});
                        n.querySelectorAll('.katex').forEach(k=>k.remove());
                        if(n.querySelector('.katex-error') || /\\(?:frac|prime|qquad|sqrt|left|right|begin)\b/.test(n.textContent))
                            errors.push({...c,remaining:n.textContent});
                    }
                    return errors;
                }''',render_cases)
                assert not formula_errors,json.dumps(formula_errors,ensure_ascii=False)
                page.get_by_label('用户名',exact=True).fill('senior-browser')
                page.get_by_label('密码',exact=True).fill('test-pass-123')
                page.get_by_label('称呼',exact=True).fill('验证学生')
                page.get_by_label('学段',exact=True).select_option('senior')
                page.get_by_label('高中教材册次',exact=True).select_option('math-senior-compulsory-1')
                page.get_by_role('button',name='创建并开始学习',exact=True).click()
                expect(page.get_by_role('heading',name='先从一个问题开始。')).to_be_visible()
                for book in [b for b in BOOKS if b.get('stage')=='senior']:
                    r=page.request.post(url+'/api/v1/auth/stage',data={'stage':'senior','subject':book['subject'],'book_id':book['id']})
                    assert r.status==200,r.text()
                    page.reload();expect(page.get_by_role('heading',name='先从一个问题开始。')).to_be_visible()
                    page.get_by_role('tab',name='题库',exact=True).click()
                    for mode in ('choice','written'):
                        page.get_by_label('作答方式',exact=True).select_option(mode)
                        with page.expect_response(lambda r:r.url.endswith('/study/next')) as response:
                            page.get_by_role('button',name='开始练习',exact=True).click()
                        work=response.value.json();assert response.value.status==200,work
                        with connect(path) as db:q=json.loads(db.execute('SELECT data FROM bank_questions WHERE id=?',(work['question']['id'],)).fetchone()[0])
                        assert q['stage']=='senior' and q['curriculum_book_id']==book['id']
                        if args.include_foundations and mode=='written':
                            assert q.get('foundation_skill_ids'),q['id']
                        assert 'reference_answer' not in json.dumps(work['question'].get('annotation',{}))
                        if mode=='choice':
                            for index,option in enumerate(q['options']):
                                if option['key'] in q['answer']:page.locator('.choice').nth(index).click()
                            page.get_by_role('button',name='提交答案',exact=True).click()
                        else:
                            parts=q['annotation']['parts']
                            if len(parts)>1:
                                for index,part in enumerate(parts,1):page.get_by_label(f'第 {index} 问解答',exact=True).fill(part['reference_answer'])
                            else:page.get_by_label('完整解答',exact=True).fill(parts[0]['reference_answer'])
                            picture=io.BytesIO();Image.new('RGB',(220,150),'white').save(picture,format='PNG')
                            page.get_by_label('上传手写答案',exact=True).set_input_files({'name':'mock-answer.png','mimeType':'image/png','buffer':picture.getvalue()})
                            page.get_by_role('button',name='提交 AI 评阅',exact=True).click()
                            expect(page.get_by_role('heading',name='核对 AI 评阅')).to_be_visible()
                            page.get_by_label('你确认的结果',exact=True).select_option('correct')
                            page.get_by_text('我已核对图片转写与评价',exact=True).click()
                            page.get_by_role('button',name='确认并保存',exact=True).click()
                        expect(page.get_by_role('heading',name='这道题答对了。')).to_be_visible()
                        if not page.evaluate('document.documentElement.scrollWidth<=innerWidth'):
                            print('overflow source',q['annotation_source_question_id'],flush=True)
                            print(page.evaluate("[...document.querySelectorAll('body *')].filter(n=>n.getBoundingClientRect().right>innerWidth+1).slice(0,15).map(n=>({tag:n.tagName,class:String(n.className),text:n.textContent.slice(0,60)}))"),flush=True)
                            page.screenshot(path=previews/'overflow.png',full_page=True)
                            raise AssertionError((book['id'],mode,'overflow'))
                        page.screenshot(path=previews/(book['id']+'-'+mode+'.png'),full_page=True,animations='disabled')
                    report=page.request.get(url+'/api/v1/reports?period=all').json()
                    assert report['stage']=='senior' and report['summary']['attempts']==2 and report['summary']['independent']==0
                    assert page.request.get(url+'/api/v1/reports/pdf').status==200
                    completed.append({'book_id':book['id'],'choice':'passed','written_photo':'passed','report_pdf':'passed'})
                    print('实际题目界面通过',book['id'],flush=True)
                assert not errors,errors;browser.close()
            folder='senior-foundations-20261016' if args.include_foundations else 'senior-20261015'
            out=ROOT/'data/annotations'/folder/'browser-verification.json'
            out.parent.mkdir(parents=True,exist_ok=True)
            out.write_text(json.dumps({'model':'local mock, not a model-accuracy evaluation','books':completed,
                'page_errors':errors,'viewport':390,'real_student_records_created':0},ensure_ascii=False,indent=2))
        finally:
            process.terminate();process.wait(timeout=10);model.shutdown();model.server_close()


if __name__=='__main__':main()
