"""Offline synthetic memory timelines; no account, API key or student DB access."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import ai_policy, memory


def main():
    base=datetime(2030,1,1,12,tzinfo=timezone.utc)
    original={'id':'synthetic-difficulty','kind':'difficulty','type_id':'m7a:absolute',
              'type_name':'负数的绝对值','created_at':base.isoformat(),'evidence_quote':'|-3|=-3',
              'note':'将距离写成负数。','policy_version':ai_policy.VERSION,
              'validation':{'method':'independent_ai_review'},'confidence':'medium'}
    def event(index,offset,correct=True,identity=None):
        return {'attempt_id':str(index),'identity':identity or str(index),
                'time':(base+timedelta(days=offset)).isoformat(),'correct':correct}
    scenarios=[
        ('长期没有新证据',[],{0:'active',15:'active',30:'expired',60:'expired'}),
        ('跨天独立新题改善',[event(1,1),event(2,1),event(3,2)],{0:'active',1:'active',2:'resolved',30:'resolved'}),
        ('同一天集中刷题',[event(i,1) for i in range(1,11)],{1:'active',2:'active',30:'expired'}),
        ('重复同一道题',[event(i,i,identity='same') for i in range(1,8)],{7:'active',30:'expired'}),
        ('改善后出现新的错误',[event(1,1),event(2,1),event(3,2),event(4,3,False)],{2:'resolved',3:'resolved',30:'resolved'}),
    ]
    cases=[]
    for name,events,checks in scenarios:
        timeline=[]
        for offset,expected in checks.items():
            at=base+timedelta(days=offset)
            projected=memory.project([original],events,at)[0]
            assert projected['memory_status']==expected,(name,offset,projected)
            schedule=memory.review(events,at)
            timeline.append({'day':offset,'memory_status':projected['memory_status'],
                'freshness':projected['freshness'],'resolved_by':projected['resolved_by'],
                'last_verified_at':schedule['last_verified_at'],'review_due':schedule['due'],
                'interval_days':schedule['interval_days']})
        cases.append({'name':name,'passed':True,'timeline':timeline})
    output=Path(__file__).resolve().parents[1]/'output/evals/memory-latest.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'memory_version':memory.VERSION,'synthetic_only':True,
        'cases':cases,'passed':len(cases),'note':'程序规则测试，不是模型记忆准确率或教育效果评价。'},ensure_ascii=False,indent=2))
    print(f'{len(cases)}个合成时间线通过；结果：{output}')


if __name__=='__main__':main()
