"""Two-function paper workspace: real file intake/calibration/storage, mock inference."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
from playwright.sync_api import sync_playwright, expect

from app import bank
from app.admin import grant_admin
from app.db import connect, initialize

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from test_calibration import finding
from app.calibration import Judgment


class MockOllama(BaseHTTPRequestHandler):
    def reply(self,value):
        raw=json.dumps(value,ensure_ascii=False).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        self.reply({'models':[{'name':'test-local:8b','digest':'test-digest'}]})
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        material=json.loads(body['messages'][1]['content'])
        question=material['question']
        if 'independent_findings' in material:
            value=Judgment(verdict='pass',source_complete=True,answers_agree=True,solutions_valid=True,tags_supported=True,
                           rubric_complete=True,scope_supported=True,source_answer='match',reason='两次解答一致，符合条件。').model_dump()
        else:
            value=finding(question).model_dump()
        time.sleep(.1)
        self.reply({'model':'test-local:8b','done':True,'done_reason':'stop','message':{'content':json.dumps(value,ensure_ascii=False)}})
    def log_message(self,*args):pass


def port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def main():
    output=ROOT/'output/evals/admin-paper';output.mkdir(parents=True,exist_ok=True)
    app_port,model_port=port(),port();url=f'http://127.0.0.1:{app_port}'
    server=ThreadingHTTPServer(('127.0.0.1',model_port),MockOllama)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    with tempfile.TemporaryDirectory(prefix='admin-paper-') as temp:
        path=Path(temp)/'test.sqlite3';initialize(path)
        with connect(path) as db:
            bank.import_records(db,'ui-sample',[{'id':'ui:reading','subject':'chinese','stage':'junior','grade':7,'term':1,
                'stem':'阅读下面的原创短文，结合文本回答问题。\n'+('清晨，孩子沿着河边走向学校。\n'*100),'kind':'reference','status':'reference',
                'options':[],'answer':'结合描写分析。','steps':['先找出描写。'],'difficulty':2,'knowledge_tags':['现代文阅读'],
                'type_tags':['人物描写作用'],'provenance':{'dataset':'ui-sample','license':'original'}}],{})
        env={**os.environ,'DATABASE_PATH':str(path),'AUTH_REQUIRED':'true','REGISTRATION_ENABLED':'true','REGISTRATION_REQUIRES_INVITE':'false',
             'AI_API_KEY':'','DEEPSEEK_API_KEY':'','LOCAL_AUDIT_ENABLED':'true','LOCAL_AUDIT_MODEL':'test-local:8b',
             'LOCAL_AUDIT_BASE_URL':f'http://127.0.0.1:{model_port}'}
        log=open(Path(temp)/'server.log','w')
        proc=subprocess.Popen([str(ROOT/'.venv/bin/python'),'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(app_port),'--no-access-log'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=url,trust_env=False) as client:
                for _ in range(100):
                    try:
                        if client.get('/api/v1/health').status_code==200:break
                    except httpx.HTTPError:pass
                    time.sleep(.1)
                else:raise RuntimeError('临时服务启动失败')
                assert client.post('/api/v1/auth/register',json={'username':'maintenance-demo','password':'browser-test-123','grade':7,'term':1}).status_code==201
            with connect(path) as db:grant_admin(db,'maintenance-demo')
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('google-chrome-stable') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1440,'height':1000},color_scheme='light');errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)+' '+str(e.stack)))
                debug=page.context.new_cdp_session(page)
                debug.send('Runtime.enable')
                debug.on('Runtime.exceptionThrown',lambda e:print('Exception location:',{k:e['exceptionDetails'].get(k) for k in ('text','url','lineNumber','columnNumber','scriptId','exception')},flush=True))
                page.set_default_timeout(12000)
                page.goto(url+'/admin')
                try:expect(page.get_by_label('用户名',exact=True)).to_be_visible()
                except Exception:
                    print('UI errors:',errors,'body:',page.locator('body').inner_text(),flush=True)
                    raise
                page.get_by_label('用户名',exact=True).fill('maintenance-demo');page.get_by_label('密码',exact=True).fill('browser-test-123')
                page.get_by_role('button',name='登录工作台',exact=True).click()
                expect(page.get_by_role('heading',name='题库',exact=True)).to_be_visible()
                expect(page.get_by_role('navigation',name='题库功能').get_by_role('button')).to_have_count(2)
                assert page.get_by_role('button',name='审核并发布').count()==0
                page.get_by_role('button',name='导入',exact=True).click()
                expect(page.get_by_label('审核模型',exact=True)).to_have_value('test-local:8b')
                page.screenshot(path=output/'import-light-desktop.png',full_page=True)
                fixture={'stem':'计算 -5 - (-4)。','reference_answer':'-1'}
                page.get_by_label('导入习题文件',exact=True).set_input_files({'name':'习题.jsonl','mimeType':'application/x-ndjson','buffer':json.dumps(fixture,ensure_ascii=False).encode()})
                expect(page.locator('.file-drop')).to_contain_text('习题.jsonl')
                page.get_by_role('button',name='交给 AI',exact=True).click()
                expect(page.locator('.job-total')).to_contain_text('已入库 1',timeout=20000)
                page.screenshot(path=output/'import-result-desktop.png',full_page=True)
                with connect(path) as db:
                    q=json.loads(db.execute("SELECT data FROM bank_questions WHERE source_id='local-calibration'").fetchone()[0])
                    assert q['provenance']['teacher_reviewed'] is False
                page.get_by_role('button',name='题库',exact=True).click()
                page.get_by_label('搜索题目',exact=True).fill('计算 -5 - (-4)。');page.get_by_role('button',name='搜索',exact=True).click()
                expect(page.locator('.bank-row')).to_have_count(1)
                expect(page.locator('.bank-row')).to_contain_text('AI 已标注')
                page.screenshot(path=output/'search-light-desktop.png',full_page=True)
                page.locator('.bank-row').click()
                expect(page.get_by_role('heading',name='题目标注',exact=True)).to_be_visible()
                expect(page.locator('.answer-section')).to_contain_text('-1')
                page.get_by_text('完整标注',exact=True).click()
                expect(page.locator('.calibration-command')).to_contain_text('response_format')
                assert page.get_by_role('button',name='保存草稿').count()==0
                page.screenshot(path=output/'annotation-light-desktop.png',full_page=True)
                page.get_by_role('button',name='切换主题',exact=True).click()
                expect(page.locator('html')).to_have_attribute('data-theme','dark')
                page.screenshot(path=output/'annotation-dark-desktop.png',full_page=True)
                page.reload()
                expect(page.get_by_role('heading',name='题库',exact=True)).to_be_visible()
                expect(page.locator('html')).to_have_attribute('data-theme','dark')
                page.set_viewport_size({'width':390,'height':844})
                page.get_by_role('button',name='导入',exact=True).click()
                expect(page.locator('.job-total')).to_contain_text('已入库 1')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=output/'import-dark-mobile.png',full_page=True)
                page.get_by_role('button',name='切换主题',exact=True).click()
                page.get_by_label('导入习题文件',exact=True).set_input_files({'name':'错误.txt','mimeType':'text/plain','buffer':b''})
                page.get_by_role('button',name='交给 AI',exact=True).click()
                expect(page.locator('.import-error')).to_be_visible()
                assert page.get_by_label('导入习题文件',exact=True).count()==1
                for width in (320,390):
                    page.set_viewport_size({'width':width,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=output/'import-light-mobile.png',full_page=True)
                page.get_by_role('button',name='题库',exact=True).click()
                page.get_by_label('搜索题目',exact=True).fill('阅读下面');page.get_by_role('button',name='搜索',exact=True).click()
                page.locator('.bank-row').first.click()
                expect(page.locator('.question-stem')).to_contain_text('沿着河边')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert not errors,errors
                browser.close()
                result={'two_navigation_entries':True,'file_to_ai_to_bank':True,'source_pinned_calibration':True,
                        'readonly_search_annotation':True,'theme_persistence':True,'invalid_file_feedback':True,
                        'long_reading_layout':True,'mobile_320_390':True,'javascript_errors':errors}
                (output/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
                print(json.dumps(result,ensure_ascii=False))
        finally:
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            log.close();server.shutdown()


if __name__=='__main__':main()
