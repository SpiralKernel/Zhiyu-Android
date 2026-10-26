"""Local GPU worker; does not load student-teacher API configuration or execute model code."""
import argparse
import asyncio
import ipaddress
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.calibration import (Finding, Judgment, Report, Result, Round, Source, check_task,
                             create_job, digest, evaluate, get_task, import_report, prompt, publish, output_schema, recorded_prompt, finding_issues)
from app.db import connect, now
from app.ai_transport import completion_content


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.next')
    with tmp.open('w') as f:
        os.chmod(tmp,0o600);json.dump(value,f,ensure_ascii=False,indent=2)
    tmp.replace(path)


class LocalModel:
    def __init__(self,base_url='http://127.0.0.1:11434',backend='ollama',timeout=300,context_size=16384,allow_remote=False,api_key='',temperature=0.6,max_tokens=8192,thinking=None,provider='compatible'):
        parts=urlsplit(base_url)
        if parts.scheme not in {'http','https'} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('模型地址须为不含凭据、查询参数的HTTP(S)地址')
        try:loopback=parts.hostname=='localhost' or ipaddress.ip_address(parts.hostname).is_loopback
        except ValueError:loopback=False
        if not loopback and not allow_remote:raise ValueError('默认仅连接本机模型；局域网服务需显式使用--allow-remote')
        self.base=base_url.rstrip('/');self.backend=backend;self.timeout=timeout;self.context=context_size
        if not 0<=temperature<=2 or not 1024<=max_tokens<=32768:raise ValueError('采样温度或输出长度超出范围')
        self.api_key=api_key;self.digests={}
        self.temperature=temperature;self.max_tokens=max_tokens;self.thinking=thinking
        self.provider=provider

    async def inspect(self,model):
        headers={'Authorization':'Bearer '+self.api_key} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=15,trust_env=False,headers=headers) as client:
                r=await client.get(self.base+('/api/tags' if self.backend=='ollama' else '/models'))
                r.raise_for_status();data=r.json()
                if self.backend=='ollama':
                    self.digests.update({m['name']:m.get('digest','') for m in data['models']})
                    present=model in self.digests or model+':latest' in self.digests
                else:present=model in {m['id'] for m in data['data']}
                if not present:raise ValueError('模型未安装或模型名称不匹配：'+model)
        except httpx.HTTPError:raise ValueError('无法连接本地模型服务，请启动服务并检查地址') from None

    async def ask(self,messages,schema,model,role,format_schema=None):
        headers={'Authorization':'Bearer '+self.api_key} if self.api_key else {}
        # Redact transport exception URLs/bodies and never persist keys or raw HTTP responses.
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout,trust_env=False,headers=headers) as client:
                    if self.backend=='ollama':
                        payload={'model':model,'stream':False,'format':format_schema or schema.model_json_schema(),
                                 'options':{'num_ctx':self.context,'num_predict':self.max_tokens,'temperature':self.temperature,'top_p':0.95,'top_k':20,'seed':17 if role=='primary' else 89},
                                 'messages':to_ollama(messages)}
                        if self.thinking is not None:payload['think']=self.thinking
                        r=await client.post(self.base+'/api/chat',json=payload);r.raise_for_status();raw=r.json()
                        if not raw.get('done') or raw.get('done_reason')=='length':raise ValueError('输出未完成')
                        content=raw['message']['content']
                    else:
                        options={'max_completion_tokens' if self.provider in {'mimo','openai'} else 'max_tokens':self.max_tokens}
                        if self.provider!='openai':options['temperature']=self.temperature
                        if self.provider=='mimo':options['thinking']={'type':'disabled'}
                        r=await client.post(self.base+'/chat/completions',json={'model':model,'messages':messages,
                                'stream':False,**options,'response_format':{'type':'json_object'}})
                        r.raise_for_status();raw=r.json();content=completion_content(raw)
                    value=schema.model_validate_json(content)
                    served=raw.get('model')
                    if not isinstance(served,str) or not served:raise ValueError('模型服务没有返回实际模型名称')
                    return Round(role=role,requested_model=model,served_model=served,model_digest=self.digests.get(model,self.digests.get(model+':latest','')),
                                 backend=self.backend,context_size=self.context,created_at=now(),prompt_sha256=digest(messages),output=value.model_dump(),
                                 generation={'temperature':self.temperature,'max_tokens':self.max_tokens,'thinking':self.thinking})
            except (httpx.HTTPError,ValueError,KeyError,TypeError):
                if attempt:raise ValueError('本地模型请求失败、输出截断或不符合标定协议；本题保留待处理') from None


def to_ollama(messages):
    result=[]
    for m in messages:
        if isinstance(m['content'],str):result.append(m);continue
        result.append({'role':m['role'],'content':'\n'.join(c['text'] for c in m['content'] if c['type']=='text'),
                       'images':[c['image_url']['url'].split(',',1)[1] for c in m['content'] if c['type']=='image_url']})
    return result


async def finding_round(task,item,engine,model,role):
    corrections=[]
    for attempt in range(3):
        messages=recorded_prompt(task,item,role,corrections=corrections)
        record=await engine.ask(messages,Finding,model,role,format_schema=output_schema(task,role,item))
        record.corrections=list(corrections)
        if task.get('protocol_version',1)<2:return record
        issues=finding_issues(Finding.model_validate(record.output),Source.model_validate(item['source']),task['catalog'])
        if not issues or attempt==2:return record
        corrections.append(record.output)
        print(f'  {role} 协议纠正 {attempt+1}/2：'+issues[0][:180],flush=True)
    return record


async def run_task(task_path,output,engine,model,peer_model=None,vision_model=None,retry_failed=False,on_progress=None):
    task=json.loads(Path(task_path).read_text());check_task(task)
    output=Path(output);old={}
    if output.exists():
        previous=Report.model_validate_json(output.read_text())
        if previous.task_sha256!=task['task_sha256'] or previous.catalog_sha256!=task['catalog']['sha256'] or previous.job_id!=task['job_id']:
            raise ValueError('已有结果属于其他任务，不能覆盖')
        old={r.question_id:r for r in previous.items}
        if len(old)!=len(previous.items) or set(old)-{i['question_id'] for i in task['items']}:raise ValueError('已有结果题号无效')
        for i in task['items']:
            if i['question_id'] in old and old[i['question_id']].source_sha256!=i['source_sha256']:raise ValueError('已有结果来源哈希不匹配')
    models={vision_model if i['source']['images'] else m for i in task['items'] for m in (model,peer_model or model)}-{None}
    for m in models:await engine.inspect(m)
    rows=[]
    for i in task['items']:
        prior=old.get(i['question_id'])
        if prior and (not retry_failed or not prior.error):
            rows.append(prior);continue
        r=Result(protocol_version=task.get('protocol_version',1),question_id=i['question_id'],source_sha256=i['source_sha256'])
        try:
            if i['source']['requires_assets'] and not i['source']['images']:raise ValueError('必要题图缺失，请补齐后建立新任务')
            if i['source']['images'] and not vision_model:raise ValueError('图片题需配置--vision-model；文字模型不能替代识图')
            primary=vision_model if i['source']['images'] else model
            peer=vision_model if i['source']['images'] else peer_model or model
            a=await finding_round(task,i,engine,primary,'primary')
            b=await finding_round(task,i,engine,peer,'peer')
            j=await engine.ask(prompt(task,i,'judge',[a.output,b.output]),Judgment,primary,'judge',format_schema=output_schema(task,'judge'))
            r.rounds=[a,b,j]
        except ValueError as exc:r.error=str(exc)
        rows.append(r)
        report=Report(job_id=task['job_id'],task_sha256=task['task_sha256'],catalog_sha256=task['catalog']['sha256'],items=rows)
        write_json(output,report.model_dump())
        if on_progress is not None:await on_progress(report)
        try:
            assessment=evaluate(i,r,task['catalog']);state=assessment['status']
            detail='；'.join(assessment.get('issues',[])[:3])
        except (ValueError,KeyError):state='hold';detail='无法按协议解析'
        print(f'{len(rows)}/{len(task["items"])} {i["question_id"]}: {state}'+(' · '+detail if detail else ''),flush=True)
    report=Report(job_id=task['job_id'],task_sha256=task['task_sha256'],catalog_sha256=task['catalog']['sha256'],items=rows)
    write_json(output,report.model_dump())
    return report


def main():
    parser=argparse.ArgumentParser(description='本地AI习题标定：导出→双轮盲解/核对→导入→纳入练习')
    sub=parser.add_subparsers(dest='command',required=True)
    export=sub.add_parser('export');export.add_argument('--database',type=Path,required=True);export.add_argument('--book',required=True)
    export.add_argument('--input',type=Path,help='新题JSON数组或JSONL，可包含图片data URL');export.add_argument('--limit',type=int,default=10)
    export.add_argument('--output',type=Path,required=True)
    run=sub.add_parser('run');run.add_argument('--task',type=Path,required=True);run.add_argument('--output',type=Path,required=True)
    run.add_argument('--model',default='qwen3.5:9b');run.add_argument('--peer-model');run.add_argument('--vision-model')
    run.add_argument('--backend',choices=['ollama','openai'],default='ollama');run.add_argument('--base-url',default='http://127.0.0.1:11434')
    run.add_argument('--timeout',type=float,default=300);run.add_argument('--context-size',type=int,default=16384)
    run.add_argument('--temperature',type=float,default=0.6);run.add_argument('--max-tokens',type=int,default=8192)
    run.add_argument('--thinking',choices=['auto','on','off'],default='auto',help='auto保留模型自身默认思考模式')
    run.add_argument('--api-key-env',default='LOCAL_AUDIT_API_KEY');run.add_argument('--allow-remote',action='store_true');run.add_argument('--retry-failed',action='store_true')
    ingest=sub.add_parser('import');ingest.add_argument('--database',type=Path,required=True);ingest.add_argument('--report',type=Path,required=True);ingest.add_argument('--publish',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='run':
            if not 1<=args.timeout<=1800 or not 1024<=args.context_size<=131072:raise ValueError('超时或上下文设置超出范围')
            engine=LocalModel(args.base_url,args.backend,args.timeout,args.context_size,args.allow_remote,os.environ.get(args.api_key_env,''),args.temperature,args.max_tokens,{'auto':None,'on':True,'off':False}[args.thinking])
            asyncio.run(run_task(args.task,args.output,engine,args.model,args.peer_model,args.vision_model,args.retry_failed))
        else:
            if not args.database.is_file():raise ValueError('数据库不存在，请先启动新版应用建立题库')
            with connect(args.database) as db:
                if db.execute('PRAGMA user_version').fetchone()[0]!=15:raise ValueError('请先启动新版应用，完成数据库升级到15')
                db.execute('BEGIN IMMEDIATE')
                if args.command=='export':
                    if args.output.exists():raise ValueError('任务输出已存在，拒绝覆盖')
                    if not 1<=args.limit<=100:raise ValueError('每批1—100题')
                    sources=None
                    if args.input:
                        text=args.input.read_text();raw=json.loads(text) if text.lstrip().startswith('[') else [json.loads(line) for line in text.splitlines() if line.strip()]
                        sources=[Source.model_validate(v) for v in raw]
                    task=create_job(db,args.book,sources,limit=args.limit);write_json(args.output,task)
                    print('任务已导出：'+str(args.output))
                else:
                    report=Report.model_validate_json(args.report.read_text());value=import_report(db,report)
                    if args.publish:value=publish(db,report.job_id)
                    print(json.dumps(value['counts'],ensure_ascii=False))
    except (ValueError,OSError) as exc:parser.exit(1,str(exc)+'\n')


if __name__=='__main__':main()
