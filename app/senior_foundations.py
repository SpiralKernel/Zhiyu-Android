"""Audit a fine-skill inventory against actual, independently reviewed exercises.

Coverage is a content inventory, never a student's mastery or a claim that a
written question certifies practical experimental ability.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path

from app.bank import content_hash
from app.course_catalog import GOALS
from app.senior_bank import DATA, prepare_batch, validate_peer, digest


def audit_foundations(data=DATA):
    data=Path(data)
    errors=[];items={};records={};skills={};goal_skills=defaultdict(set)
    goal_ids={g for g,v in GOALS.items() if '-senior-' in v['book_id']}
    try:
        peer=json.loads((data/'senior_foundations_peer_review.json').read_text())
        for subject in ('math','physics'):
            value=json.loads((data/f'senior_{subject}_foundations.json').read_text())
            validate_peer(value,peer)
            rows,_=prepare_batch(value)
            for item,q in zip(value['items'],rows):
                qid=item['question_id']
                if qid in items:raise ValueError('基础题来源编号重复：'+qid)
                items[qid]=item;records[qid]=q
            catalog=json.loads((data/f'senior_{subject}_foundation_skills.json').read_text())
            for skill in catalog['skills']:
                sid=skill['id']
                if sid in skills:raise ValueError('基础技能编号重复：'+sid)
                if not skill.get('name') or not skill.get('requirement'):
                    raise ValueError('基础技能缺少名称或要求：'+sid)
                if not skill.get('goal_ids') or any(g not in goal_ids or
                        GOALS[g]['subject']!=subject or GOALS[g]['book_id']!=skill['book_id']
                        for g in skill['goal_ids']):
                    raise ValueError('基础技能课程范围不符：'+sid)
                qids=skill.get('question_ids',[])
                if len(qids)!=len(set(qids)):raise ValueError('基础技能关联题号重复：'+sid)
                skills[sid]=skill
                if skill.get('role','required') not in {'required','prerequisite'}:
                    raise ValueError('未知基础技能作用：'+sid)
                if skill.get('role')!='prerequisite':
                    for g in skill['goal_ids']:goal_skills[g].add(sid)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        errors.append(str(exc))
    seen={};stem_seen={};selected=Counter();skill_counts={}
    # Detect duplicate stems even if someone changes the answer or annotation.
    for qid,q in records.items():
        if q['status']=='quarantine':continue
        key=content_hash(q)
        stem=digest([q['stage'], ''.join(q['stem'].split()), q.get('options',[])])
        if key in seen or stem in stem_seen:
            errors.append('基础题内容重复：'+qid)
        seen[key]=qid;stem_seen[stem]=qid
        selected[q['subject']]+=1
        assigned=items[qid].get('foundation_skill_ids',[])
        if len(assigned)!=1 or assigned[0] not in skills:
            errors.append('每道基础题需有一个有效主技能：'+qid)
        elif qid not in skills[assigned[0]].get('question_ids',[]):
            errors.append('题目与技能关联不对称：'+qid)
        if q['difficulty']>2:errors.append('挑战题不能代替基础题覆盖：'+qid)
    for sid,skill in skills.items():
        ready=[]
        for qid in skill.get('question_ids',[]):
            q=records.get(qid)
            if q is None:
                errors.append('技能关联了不存在的题：'+sid);continue
            if (q.get('curriculum_book_id')!=skill['book_id'] or
                    not set(skill['goal_ids']).issubset(q.get('curriculum_goal_ids',[])) or
                    items[qid].get('foundation_skill_ids')!=[sid]):
                errors.append('技能与题目课程/主技能不符：'+qid);continue
            if q['status']!='quarantine' and q['difficulty']<=2:ready.append(qid)
        skill_counts[sid]={'id':sid,'name':skill['name'],'book_id':skill['book_id'],
            'goal_ids':skill['goal_ids'],'minimum':2,'ready':len(ready),
            'remaining':max(0,2-len(ready))}
    goals=[{'id':g,'name':GOALS[g]['name'],'book_id':GOALS[g]['book_id'],
        'skills':len(goal_skills[g]),'skills_ready':sum(skill_counts[s]['remaining']==0
            for s in goal_skills[g])} for g in sorted(goal_ids)]
    complete=(not errors and len(skills)>0 and all(g['skills']>=2 and
        g['skills_ready']==g['skills'] for g in goals) and
        all(s['remaining']==0 for s in skill_counts.values()))
    return {'schema_version':1,'complete':complete,'errors':errors,
        'selected':dict(selected),'skills':list(skill_counts.values()),'goals':goals,
        'note':'Paper fundamentals inventory; not practical skills certification or student mastery.'}
