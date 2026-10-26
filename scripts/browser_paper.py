"""Isolated student UI acceptance: paper themes, practice-first navigation and figures.

Uses a temporary database and mock AI; never changes real student records.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer

import httpx
from playwright.sync_api import expect, sync_playwright

from app import bank
from app.db import connect, initialize
from scripts.browser_student import MockAI, free_port, png

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/evals/paper-ui'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    chrome = shutil.which('google-chrome-stable') or shutil.which('chromium')
    if not chrome:
        raise SystemExit('需要本机 Chrome')
    port, ai_port = free_port(), free_port()
    url = f'http://127.0.0.1:{port}'
    server = ThreadingHTTPServer(('127.0.0.1', ai_port), MockAI)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    checks, errors = [], []
    with tempfile.TemporaryDirectory(prefix='teacher-paper-') as temp:
        db_path = Path(temp) / 'test.sqlite3'
        initialize(db_path)
        question = {
            'id':'paper-choice', 'subject':'math', 'stage':'junior', 'grade':7, 'term':1,
            'stem':'如图，数轴上的点 A 表示 $-3$，则 $|{-3}|$ 的值为（　）。',
            'kind':'single_choice', 'status':'ready',
            'options':[{'key':k,'text':v} for k,v in [('A','3'),('B','−3'),('C','0'),('D','6')]],
            'answer':'A','steps':['绝对值是数轴上的点到原点的距离。','点 A 到原点的距离为 3。'],
            'difficulty':1,'knowledge_tags':['绝对值'],'type_tags':['负数的绝对值'],
            'tags_source':'source','provenance':{},'assets':['/paper-test-figure.svg'],
        }
        written = {**question,'id':'paper-written','stem':'M 是线段 AB 的中点，AB=10cm。（1）求 AM；（2）求 MB。写出过程。',
                   'kind':'reference','status':'reference','options':[],'answer':'AM=5cm，MB=5cm',
                   'annotation':{'schema_version':1,'response_format':'composite','difficulty':{'level':1,'basis':'中点关系'},
                     'parts':[{'id':pid,'prompt':prompt,'reference_answer':'5cm','knowledge_tags':['线段中点'],
                               'type_tags':['线段中点关系求长度'],'rubric':[{'id':'midpoint','description':'根据中点定义计算长度'}]}
                              for pid,prompt in [('p1','求 AM，并说明依据。'),('p2','求 MB，并说明依据。')]]}}
        with connect(db_path) as db:
            bank.import_records(db,'paper-browser',[question,written],{})
        env = {**os.environ,'DATABASE_PATH':str(db_path),'AUTH_REQUIRED':'true','DIAGNOSTIC_CORE_ENABLED':'false',
               'REGISTRATION_REQUIRES_INVITE':'false','AI_PROVIDER':'deepseek','AI_API_KEY':'browser-test-only',
               'AI_BASE_URL':f'http://127.0.0.1:{ai_port}','AI_MODEL':'mock','AI_VISION_MODEL':'mock'}
        process = subprocess.Popen([str(ROOT/'.venv/bin/uvicorn'),'app.main:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            with httpx.Client(trust_env=False) as client:
                for _ in range(120):
                    if process.poll() is not None:
                        raise RuntimeError(process.stderr.read().decode())
                    try:
                        if client.get(url+'/api/v1/health').status_code == 200: break
                    except httpx.ConnectError: pass
                    time.sleep(.1)
                else: raise RuntimeError('临时服务启动超时')
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=chrome,headless=True,args=['--no-sandbox'])
                page = browser.new_page(viewport={'width':1440,'height':1000},color_scheme='light')
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.set_default_timeout(15000)
                # Real bank API with deterministic exercise format, plus a served image fixture.
                page.route('**/api/v1/study/next', lambda route:route.continue_(post_data=json.dumps({**route.request.post_data_json,'choice':True,'written':False})))
                svg='<svg xmlns="http://www.w3.org/2000/svg" width="640" height="150" viewBox="0 0 640 150"><rect width="640" height="150" fill="white"/><path d="M50 82H590m-9-6 9 6-9 6M155 76v12M320 76v12M485 76v12" stroke="#40362e" fill="none" stroke-width="2"/><circle cx="155" cy="82" r="4" fill="#aa7058"/><g fill="#40362e" font-size="18" font-family="serif" text-anchor="middle"><text x="155" y="58">A</text><text x="155" y="115">−3</text><text x="320" y="115">0</text><text x="485" y="115">3</text></g></svg>'
                page.route('**/paper-test-figure.svg',lambda route:route.fulfill(content_type='image/svg+xml',body=svg))
                page.goto(url)
                expect(page.get_by_role('heading',name='创建账号',exact=True)).to_be_visible()
                page.screenshot(path=OUT/'login-light.png',full_page=True)
                page.get_by_label('用户名',exact=True).fill('paper_student')
                page.get_by_label('密码',exact=True).fill('test-paper-123')
                page.get_by_label('称呼',exact=True).fill('小林')
                page.get_by_role('button',name='创建账号',exact=True).click()
                expect(page.locator('#work')).to_be_visible()
                expect(page.locator('.question-asset')).to_be_visible()
                assert page.locator('.question-asset').evaluate('(img)=>img.complete && img.naturalWidth>0')
                assert page.locator('.question-stem .katex').count()>0
                expect(page.locator('.tabs')).to_have_count(0)
                assert page.request.get(url+'/api/v1/study/home').json()['completed']==0
                checks.append('registration_opens_real_exercise')
                page.screenshot(path=OUT/'exercise-light-desktop.png',full_page=True)
                page.get_by_role('button',name='放大题图',exact=True).click()
                expect(page.get_by_role('dialog',name='题目附图')).to_be_visible()
                page.keyboard.press('Escape')
                expect(page.get_by_role('dialog')).to_have_count(0)
                checks.append('figure_load_and_zoom')
                page.locator('.choice').first.click()
                page.get_by_role('button',name='问 AI',exact=True).last.click()
                expect(page.get_by_role('dialog',name='这道题的 AI老师')).to_be_visible()
                page.get_by_label('就这道题向 AI 提问',exact=True).fill('看看我这一步')
                page.get_by_role('button',name='发送问题',exact=True).click()
                expect(page.get_by_role('dialog').locator('.message').last).to_contain_text('绝对值表示')
                page.get_by_role('button',name='关闭问答',exact=True).click()
                expect(page.locator('.choice input').first).to_be_checked()
                checks.append('context_ai_preserves_answer')
                page.get_by_role('button',name='提交',exact=True).click()
                expect(page.get_by_role('heading',name='这道题答对了。')).to_be_visible()
                checks.append('real_answer_submission')

                def menu(label):
                    page.get_by_label('打开菜单',exact=True).click()
                    page.locator('.menu-list').get_by_role('button',name=label,exact=True).click()

                menu('外观')
                page.get_by_label('主题',exact=True).select_option('dark')
                expect(page.locator('html')).to_have_attribute('data-theme','dark')
                page.keyboard.press('Escape')
                page.get_by_role('button',name='下一题',exact=True).click()
                expect(page.locator('.choices')).to_be_visible()
                page.screenshot(path=OUT/'exercise-dark-desktop.png',full_page=True)
                page.reload()
                expect(page.locator('#work')).to_be_visible()
                expect(page.locator('html')).to_have_attribute('data-theme','dark')
                checks.append('theme_persistence')
                menu('外观')
                page.get_by_label('主题',exact=True).select_option('system')
                page.emulate_media(color_scheme='light')
                expect(page.locator('html')).to_have_attribute('data-theme','light')
                page.emulate_media(color_scheme='dark')
                expect(page.locator('html')).to_have_attribute('data-theme','dark')
                page.get_by_label('主题',exact=True).select_option('light')
                page.get_by_label('字号',exact=True).select_option('large')
                expect(page.locator('html')).to_have_attribute('data-font','large')
                page.get_by_label('字号',exact=True).select_option('normal')
                page.keyboard.press('Escape')
                checks.append('system_theme_and_font')
                for width in (390,320):
                    page.set_viewport_size({'width':width,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    menu('练习设置')
                    expect(page.get_by_role('dialog',name='设置')).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    page.keyboard.press('Escape')
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path=OUT/'exercise-light-mobile.png',full_page=True)
                page.get_by_role('button',name='问 AI',exact=True).last.click()
                expect(page.get_by_role('dialog',name='这道题的 AI老师')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=OUT/'ai-mobile.png',full_page=True)
                page.get_by_role('button',name='关闭问答',exact=True).click()
                menu('账号')
                expect(page.get_by_role('dialog')).to_contain_text('小林')
                assert 'null' not in page.get_by_role('dialog').inner_text()
                page.keyboard.press('Escape')
                menu('我的学情')
                expect(page.get_by_role('heading',name='我的学情',exact=True)).to_be_visible()
                menu('习题导入')
                expect(page.get_by_label('选择练习图片或PDF',exact=True)).to_be_attached()
                menu('提问记录')
                expect(page.locator('.history-list')).to_be_visible()
                menu('学情报告')
                expect(page.locator('.report-page')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=OUT/'report-mobile.png',full_page=True)
                checks.append('mobile_menu_all_destinations')
                # Actual settings control bank selection for written multipart questions.
                page.unroute('**/api/v1/study/next')
                menu('练习设置')
                page.get_by_label('作答方式',exact=True).select_option('written')
                page.get_by_role('dialog',name='设置').get_by_role('button',name='开始练习',exact=True).click()
                expect(page.get_by_label('第 1 问解答',exact=True)).to_be_visible()
                page.get_by_label('第 1 问解答',exact=True).fill('AM=5cm')
                page.get_by_label('第 2 问解答',exact=True).fill('MB=5cm')
                page.get_by_label('上传手写答案',exact=True).set_input_files({'name':'answer.png','mimeType':'image/png','buffer':png()})
                expect(page.locator('.answer-photo')).to_contain_text('1 张图片')
                page.get_by_role('button',name='提交 AI 评阅',exact=True).click()
                expect(page.get_by_role('heading',name='核对 AI 评阅',exact=True)).to_be_visible()
                page.screenshot(path=OUT/'written-mobile.png',full_page=True)
                checks.append('written_parts_photo_and_assessment')
                # Verify fallback and retry; image fixture remains isolated from the real bank.
                page.locator('.question-asset').evaluate('(img)=>img.src="/missing-paper-image.png"')
                expect(page.get_by_text('题图加载失败',exact=True)).to_be_visible()
                page.get_by_role('button',name='重试',exact=True).click()
                expect(page.locator('.question-asset')).to_be_visible()
                checks.append('figure_failure_retry')
                menu('练习设置')
                page.get_by_label('作答方式',exact=True).select_option('numeric')
                page.get_by_role('dialog',name='设置').get_by_role('button',name='开始练习',exact=True).click()
                expect(page.get_by_label('你的答案',exact=True)).to_be_visible()
                page.get_by_label('你的答案',exact=True).fill('1/0')
                page.get_by_role('button',name='提交',exact=True).click()
                expect(page.get_by_role('alert')).to_contain_text('分母不能为零')
                expect(page.get_by_label('你的答案',exact=True)).to_have_value('1/0')
                checks.append('numeric_validation_preserves_draft')
                assert not errors, errors
                browser.close()
            result={'checks':checks,'javascript_errors':errors}
            (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
            print(json.dumps(result,ensure_ascii=False,indent=2))
        finally:
            process.terminate()
            process.wait(timeout=15)
            server.shutdown()


if __name__=='__main__':
    main()
