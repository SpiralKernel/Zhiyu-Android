#!/usr/bin/env python3
"""Reproducibly generate Luna candidate annotations for math shard 0."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.question_annotation import Annotation

BASE = ROOT / 'data/annotations/math-20261011'
EXAMPLES = ROOT / 'app/data/math_annotation_examples_0.json'
INPUT = BASE / 'input-0.jsonl'
OUTPUT = BASE / 'output-0.jsonl'

def mode_for(q):
    if q.get('kind') in {'single_choice','multiple_choice'}: return 'choice'
    stem=q.get('stem','')
    if '证明' in stem: return 'proof'
    if any(x in stem for x in ('求值','计算','化简','解方程','解不等式')): return 'expression'
    if '__' in stem or '填空' in stem: return 'expression'
    return 'text'

def response(q, part_count=1):
    kind=q.get('kind')
    if kind in {'single_choice','multiple_choice'}: return ('single_choice' if kind=='single_choice' else 'multiple_choice')
    typ=' '.join(q.get('type_tags') or [])
    stem=q.get('stem','')
    if part_count>1 or '综合' in typ or '综合' in stem: return 'composite'
    if '填空' in typ or '__' in stem: return 'fill_blank'
    if '证明' in typ or '证明' in stem: return 'proof'
    if '应用' in typ or any(w in stem for w in ('实际问题','应用题','行程','销售','利润')): return 'application'
    if '计算' in typ or any(w in stem for w in ('计算','化简','解方程','解不等式')): return 'calculation'
    return 'short_answer'

def split_parts(q):
    # Split only explicit numbered subquestion markers in the stem.
    stem=q.get('stem') or ''
    answer=q.get('answer')
    matches=list(re.finditer(r'(?<![\w])(?:\([1-9]\d?\)|（[1-9]\d?）|[①②③④⑤⑥⑦⑧⑨⑩])', stem))
    if q.get('kind') in {'single_choice','multiple_choice'} or len(matches)<2:
        return [("main", stem, answer)]
    values=[]
    for m in matches:
        marker=m.group(); digits=re.search(r'\d+',marker)
        values.append(int(digits.group()) if digits else '①②③④⑤⑥⑦⑧⑨⑩'.index(marker)+1)
    if values != list(range(1,len(values)+1)):
        return [("main", stem, answer)]
    chunks=[]
    for n,m in enumerate(matches):
        end=matches[n+1].start() if n+1<len(matches) else len(stem)
        chunks.append((m.group(), stem[m.start():end].strip(), None))
    task_cues=('求','计算','解方程','解不等式','证明','求证','画出','作出','写出','指出','判断','说明','分析','估计','确定','比较','化简','求值','是多少','各多少','多少元','多少个','为何','为什么','怎样','至少','最多','的值','面积','周长','概率')
    if any(not any(cue in chunk for cue in task_cues) for _,chunk,_ in chunks):
        return [("main", stem, answer)]
    # Safe answer alignment only when line numbering exactly aligns.
    lines=[x.strip() for x in str(answer or '').splitlines() if x.strip()]
    if len(lines)==len(chunks) and all(re.match(r'^(?:\(?[1-9]\d?\)?[.、:：]|[①②③④⑤⑥⑦⑧⑨⑩])',x) for x in lines):
        chunks=[(pid,p,re.sub(r'^(?:\(?[1-9]\d?\)?[.、:：]|[①②③④⑤⑥⑦⑧⑨⑩])\s*','',lines[j])) for j,(pid,p,_) in enumerate(chunks)]
    return chunks

def rule_fine_types(stem, tags):
    broad={'代数','算术','几何','解析几何','度量几何学','组合几何学','画法几何学','计数','组合数学','竞赛数学','数学','应用题','综合题','代数式','有理数基础运算','图形与几何','函数','统计与概率','数与式','方程与不等式'}
    format_labels={'单选题','多选题','选择题','填空题','解答题','计算题','证明题','应用题','综合题','单项选择题','多项选择题'}
    leaves=[t for t in tags if t not in broad|format_labels and not re.fullmatch(r'(单选|多选|选择|填空|解答|计算|证明|应用|综合)(题|题型)?',t) and len(t)<80]
    if leaves: return leaves[:8]
    task_patterns=[('证明','依据条件证明几何或代数结论'),('求证','依据条件证明结论'),('解方程','方程求解'),('解不等式','不等式求解'),('化简','代数式化简'),('求值','代数式求值'),('计算','数与式运算'),('最值','最值问题'),('最大','最值问题'),('最小','最值问题'),('判断','命题或关系判断'),('求','根据条件求量或表达式'),('填空','依据条件填写数值或表达式')]
    for key,label in task_patterns:
        if key in stem: return [label]
    return ['根据题干条件确定所求数学量']

def is_specific_fine(label):
    broad={'代数','算术','几何','解析几何','度量几何学','组合几何学','画法几何学','计数','组合数学','竞赛数学','数学','应用题','综合题','代数式','有理数基础运算','图形与几何','函数','统计与概率','数与式','方程与不等式'}
    generic={'运算能力','数与式运算','方程求解','最值问题','根据条件求量或表达式','按题干任务确定的基础知识辨析'}
    return label not in broad|generic and not label.startswith(('根据题干条件','根据题干任务')) and len(label.strip())>=4

def matched_part_tags(prompt, tags):
    # Assign only explicitly relevant labels; an empty result is surfaced for review.
    needles=[x for x in re.split(r'[、，,；;：:（）()\s]+',prompt) if len(x)>=2]
    return [tag for tag in tags if any(n in tag or tag in n for n in needles)][:8]

def build(q, override):
    tags=[str(x).split('->')[-1].strip() for x in (q.get('knowledge_tags') or []) if x]
    typetags=[str(x) for x in (q.get('type_tags') or []) if x]
    stem=q.get('stem') or ''
    format_labels={'单选题','多选题','选择题','填空题','解答题','计算题','证明题','应用题','综合题','单项选择题','多项选择题'}
    fine=[x for x in (override.get('fine_types') or rule_fine_types(stem,tags)) if x not in format_labels and not re.fullmatch(r'(单选|多选|选择|填空|解答|计算|证明|应用|综合)(题|题型)?',x)]
    if not fine: fine=['根据题干条件确定所求数学量']
    answer=q.get('answer')
    steps=q.get('steps') or []
    explicit_parts=split_parts(q)
    partknowledge=override.get('part_knowledge') or {}
    errors=override.get('common_errors') or []
    parts=[]
    for i,(pid,prompt,panswer) in enumerate(explicit_parts):
        part_override=(override.get('parts') or [])
        pov=part_override[i] if i<len(part_override) else {}
        parttags=pov.get('knowledge_tags',partknowledge.get(pid,matched_part_tags(prompt,tags)))
        ans=pov.get('reference_answer', panswer if panswer else (answer if len(explicit_parts)==1 else None))
        rub=[]
        if pov.get('rubric'):
            rub=pov['rubric']
        parts.append({'id':f'p{i+1}', 'prompt':prompt, 'reference_answer':ans,
                      'solution_steps':(pov.get('solution_steps') or steps[:12]) if len(explicit_parts)==1 else pov.get('solution_steps',[]),
                      'knowledge_tags':parttags, 'type_tags':fine[:8], 'depends_on':[],
                      'points':None,'rubric':rub,'common_errors':errors[:5]})
    issues=[]
    if len(explicit_parts)>1 and any(p['reference_answer'] is None for p in parts): issues.append('part_answer_pending')
    if len(explicit_parts)>1 and any(not p['knowledge_tags'] for p in parts): issues.append('part_tags_pending')
    if any(not p['rubric'] for p in parts): issues.append('rubric_pending')
    issues.append('score_pending')
    if not all(is_specific_fine(x) for x in fine): issues.append('fine_type_pending')
    if q.get('quality',{}).get('answer_check',{}).get('status')=='partial_consistency': issues.append('source_answer_partial_consistency')
    if q.get('quality',{}).get('answer_check',{}).get('status')=='unchecked': answer_status='source_only'
    elif q.get('quality',{}).get('answer_check',{}).get('status')=='failed': answer_status='conflict'
    else: answer_status='source_only'
    grade=q.get('grade'); term=q.get('term')
    diff=q.get('difficulty')
    if not isinstance(diff,int) or diff not in (1,2,3): diff=2
    d_basis=q.get('difficulty_basis') or '保留来源难度值；原值未校准。'
    if 'uncalibrated' in d_basis or 'unknown_default' in d_basis: d_basis='保留来源难度字段；该值未校准。'
    a={'response_format':response(q,len(explicit_parts)),
       'knowledge':{'primary':tags[:12], 'supporting':[], 'prerequisites':override.get('prerequisites',[])},
       'fine_types':fine[:20],
       'difficulty':{'level':diff,'basis':d_basis,'origin':'source','calibrated':False},
       'curriculum':{'grade':grade if grade in (7,8,9) else None,'term':term if term in (1,2) else None,'goal_ids':[],
                     'scope_status':'source' if grade in (7,8,9) or term in (1,2) else 'unknown',
                     'basis':'年级和学期仅采用来源显式字段；未由最低册次推断。'},
       'answer_spec':{'mode':mode_for(q),'accepted_answers':([str(answer)] if answer and mode_for(q)=='choice' else []),
                      'equivalence':'exact' if mode_for(q)=='choice' else ('symbolic' if mode_for(q)=='expression' else 'manual'),
                      'constraints':[],'unit':None,'tolerance':None},
       'parts':parts,
       'grading':{'mode':'objective' if mode_for(q)=='choice' else ('ai_rubric' if any(p['rubric'] for p in parts) else 'manual'),
                  'full_score':None,'allow_alternative_methods':True,'uncertainty_policy':'review_required'},
       'review':{'status':'candidate','answer_status':answer_status,'issues':issues,
                 'method':'item_read' if override else 'rule_assisted',
                 'notes':override.get('notes','规则辅助：细题型与标签依据来源任务线索提取；参考答案仅沿用来源记录，source_reasoning 不构成完整判分细则；需人工核对。' if not override else '')},
       'origin':{'model':'gpt-6-luna','batch_id':'math-20261011-shard0'}}
    return Annotation.model_validate(a).model_dump()

def main():
    examples={(x['question_id'],x['source_sha256']):x for x in json.loads(EXAMPLES.read_text())}
    total=excluded=0
    with INPUT.open() as fi, OUTPUT.open('w') as fo:
        for i,line in enumerate(fi):
            row=json.loads(line); q=row['question']; total+=1
            flags=q.get('quality',{}).get('flags',[]); issues=q.get('issues',[])
            override=examples.get((row['question_id'],row['source_sha256']),{})
            reason=None
            if override.get('exclude_reason'): reason=override['exclude_reason']
            elif q.get('status')=='quarantine': reason='来源已隔离，题目存在明确质量问题。'
            elif q.get('quality',{}).get('answer_check',{}).get('status')=='failed' or flags and any(x in flags for x in ('conflicting_source_answers','mathematical_answer_contradiction','solution_choice_conflict')):
                reason='来源存在明确答案冲突或解析与答案矛盾，未能可靠解决。'
            elif q.get('has_missing_assets'): reason='来源标记 has_missing_assets=true，题目素材不完整，无法安全作答。'
            elif not str(q.get('stem') or '').strip(): reason='题干缺失，无法确定作答任务。'
            elif not str(q.get('answer') or '').strip(): reason='参考答案缺失，无法形成完整候选标注。'
            if reason:
                excluded+=1; out={'question_id':row['question_id'],'source_sha256':row['source_sha256'],'decision':'exclude','reason':reason,'annotation':None}
            else:
                ann=build(q,override); out={'question_id':row['question_id'],'source_sha256':row['source_sha256'],'decision':'annotate','reason':'内容可作答，形成候选标注。','annotation':ann}
            fo.write(json.dumps(out,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({'total':total,'excluded':excluded,'annotated':total-excluded,'item_read':sum(1 for x in examples.values() if not x.get('exclude_reason')),'output':str(OUTPUT)},ensure_ascii=False))

if __name__=='__main__': main()
