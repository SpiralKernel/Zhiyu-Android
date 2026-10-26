#!/usr/bin/env python3
"""Rebuild candidate annotations for physics input-1; no network or student data."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.math_annotations import Entry
from app.question_annotation import Annotation, source_fingerprint

SOURCE = ROOT / 'data/annotations/physics-20261012/input-1.jsonl'
OUTPUT = ROOT / 'data/annotations/physics-20261012/output-1.jsonl'
EXAMPLES = ROOT / 'app/data/physics_annotation_examples_1.json'
BATCH = 'physics-20261012-input-1'
KNOWN_SOURCE_CONFLICTS = {
    # The key is pinned to input-1 and was manually checked against both stem and solution.
    'bank:cjeval:40aba870202cca5176a2a368': '来源答案为BC，但逐例判断只有①④⑤为实像，选项C正确；①小孔成像不属于折射成像，选项B错误，②③反射成像也不成立，选项A错误。题目正确答案应为C，与来源答案和解析结论冲突。',
}

KNOWLEDGE_AREAS = [
 ('力学', ('力','运动','速度','机械','功','压强','浮力','密度','质量','长度','重力','摩擦','惯性','杠杆','滑轮','机械能','弹簧','测量力')),
 ('热学', ('热','温度','内能','比热','热值','汽化','液化','升华','凝华','熔化','凝固','分子热运动')),
 ('光学', ('光','透镜','成像','反射','折射','色散','凸透镜','平面镜')),
 ('声学', ('声','音调','响度','音色','噪声','振动')),
 ('电学', ('电','电流','电压','电阻','电功','电能','电功率','磁','欧姆','串联','并联','家庭电路')),
 ('测量与实验', ('测量','刻度尺','温度计','天平','量筒','实验','误差','读数','控制变量')),
]
KIND_MAP = {'单选题':'single_choice','多选题':'multiple_choice','填空题':'fill_blank','计算题':'calculation','简答题':'short_answer','实验题':'composite','作图题':'short_answer','证明题':'proof'}
MARKER = re.compile(r'(?:^|\n)\s*[（(]\s*([一二三四五六七八九十\d]+)\s*[）)]\s*')

def area_for(tags, stem):
    text = ' '.join(tags) + ' ' + stem
    scores = [(sum(text.count(w) for w in words), area) for area, words in KNOWLEDGE_AREAS]
    return max(scores)[1] if max(scores)[0] else '物理基础'

def format_for(q):
    if q['kind'] in ('single_choice','multiple_choice'):
        return q['kind'], 'choice'
    labels = q.get('type_tags') or []
    label = labels[0] if labels else ''
    if label in ('单选题', '多选题'):
        # The batch importer enforces the parsed legacy kind.  Preserve the
        # source's choice-like label as a review issue instead of changing kind.
        return 'short_answer', 'text'
    for word, kind in KIND_MAP.items():
        if word in label: return kind, 'numeric' if kind == 'calculation' else ('proof' if kind=='proof' else 'text')
    return 'short_answer', 'text'

def extract_parts(stem, answer, tags, fine):
    # Split only explicit consecutively numbered question prompts.  Answer lines are
    # aligned only when their count is exactly the same; otherwise keep one pending part.
    matches = list(MARKER.finditer(stem))
    nums = [m.group(1) for m in matches]
    expected = [str(i) for i in range(1, len(nums)+1)]
    if len(matches) >= 2 and nums == expected:
        prompts = [stem[m.end():matches[i+1].start()].strip() if i+1 < len(matches) else stem[m.end():].strip() for i,m in enumerate(matches)]
        answers = [x.strip() for x in re.split(r'\n+', answer.strip()) if x.strip()]
        if len(answers) == len(prompts):
            return [{'id':f'p{i+1}','prompt':p or stem,'reference_answer':answers[i], 'knowledge_tags':tags[:1], 'type_tags':fine[:4], 'points':None,'rubric':[]} for i,p in enumerate(prompts)], False
        return [{'id':'p1','prompt':stem,'reference_answer':None,'knowledge_tags':tags[:1],'type_tags':fine[:4]}], True
    return [{'id':'p1','prompt':stem,'reference_answer':answer or None,'knowledge_tags':tags[:1],'type_tags':fine[:4]}], not bool(answer)

def build(q, method='rule_assisted'):
    fmt, mode = format_for(q)
    stem = q.get('stem') or ''
    answer = str(q.get('answer') or '').strip()
    rawtags = [str(x) for x in q.get('knowledge_tags',[]) if x]
    area = area_for(rawtags, stem)
    primary = rawtags[:1] or [area]
    fine = []
    labels = q.get('type_tags') or []
    if '计算' in ' '.join(labels):
        fine = [f'依据{primary[0]}选用关系式并代入物理量计算']
    elif '填空' in ' '.join(labels):
        fine = [f'识别{primary[0]}概念、关系或物理量并填写结果']
    elif q['kind'] == 'single_choice':
        fine = [f'辨析{primary[0]}相关物理规律并判断单一正确选项']
    elif q['kind'] == 'multiple_choice' or '多选' in ' '.join(labels):
        fine = [f'逐项判断{primary[0]}相关物理规律并选出全部正确项']
    elif any(x in stem for x in ('实验','探究','测量','读数')):
        fine = [f'围绕{primary[0]}实验读取证据并说明结论']
    else:
        fine = [f'解释或描述{primary[0]}相关物理现象与规律']
    # Rule-derived labels are only broad routing hints.  None has been read
    # against its individual task, so every rule_assisted fine type needs review.
    pending_fine = method == 'rule_assisted' or not rawtags or any(len(x) < 3 for x in primary)
    if pending_fine: fine = []
    parts, part_pending = extract_parts(stem, answer, rawtags, fine)
    issues = ['rubric_pending']
    if q['kind'] == 'reference' and (q.get('type_tags') or [''])[0] in ('单选题','多选题'):
        issues.append('response_format_pending')
    if part_pending: issues.append('part_answer_pending')
    if pending_fine: issues.append('fine_type_pending')
    constraints = ['候选参考答案来自来源字段，未独立核验。']
    unit = None
    if any(x in stem for x in ('单位','换算','多少米','多少千米','多少秒','多少小时')): constraints.append('按题干要求写出物理量单位；单位换算须保持量纲一致。')
    if any(x in stem for x in ('图','如图')): constraints.append('需结合来源图示核对条件与读数。')
    if any(x in stem for x in ('g取','忽略','正常工作','匀速','光滑','不计')): constraints.append('公式适用条件以题干给出的理想化条件为准。')
    if mode == 'choice':
        accepted = [answer] if answer else []
        equivalence = 'exact'
    else:
        accepted = [answer] if answer else []
        equivalence = 'manual'
    level = q.get('difficulty') if q.get('difficulty') in (1,2,3) else 1
    basis = q.get('difficulty_basis') or '来源未提供可校准难度；本候选未做实测校准。'
    a = {
      'response_format':fmt,
      'knowledge':{'primary':primary,'supporting':rawtags[1:9],'prerequisites':[]},
      'fine_types':fine,
      'difficulty':{'level':level,'basis':basis+' 来源等级未经实测校准。','origin':'source','calibrated':False},
      'curriculum':{'grade':q.get('grade'),'term':q.get('term'),'scope_status':'source' if q.get('grade') or q.get('term') else 'unknown','basis':'年级与学期仅取来源字段；来源未给出则保持未知。'},
      'answer_spec':{'mode':mode,'accepted_answers':accepted,'equivalence':equivalence,'constraints':constraints,'unit':unit,'tolerance':None},
      'parts':parts,
      'grading':{'mode':'objective' if mode=='choice' else 'manual','full_score':None,'allow_alternative_methods':True,'uncertainty_policy':'review_required'},
      'review':{'status':'candidate','answer_status':'source_only','issues':issues,'method':method,'notes':'规则生成候选；来源答案和判分依据未核验，需教师复核。'},
      'origin':{'model':'gpt-6-luna','batch_id':BATCH},
    }
    return Annotation.model_validate(a).model_dump()

def main():
    examples = {x['question_id']: x for x in json.loads(EXAMPLES.read_text())}
    total=0
    with SOURCE.open() as src, OUTPUT.open('w') as out:
        for line in src:
            row=json.loads(line); q=row['question']; qid=row['question_id']
            if source_fingerprint(q)!=row['source_sha256']:raise ValueError('输入来源哈希变化：'+qid)
            sample=examples.get(qid)
            if sample and sample['source_sha256']!=row['source_sha256']:raise ValueError('逐题样例来源变化：'+qid)
            reason=None
            if qid in KNOWN_SOURCE_CONFLICTS:
                reason=KNOWN_SOURCE_CONFLICTS[qid]
            elif q.get('has_missing_assets'):
                reason='题干明确依赖图示/实验记录但必要资源缺失，无法可靠作答。'
            elif not q.get('answer'):
                reason='来源参考答案缺失，且无法据题干可靠恢复答案。'
            elif 'invalid_options' in q.get('issues',[]) and q.get('kind') in ('single_choice','multiple_choice') and not q.get('options'):
                reason='来源选项解析无效且结构化选项缺失，无法逐项判断。'
            if sample:
                annotation=sample['annotation']; reason=sample.get('exclude_reason', reason)
            elif reason:
                annotation=None
            else:
                annotation=build(q)
            e=Entry(question_id=qid,source_sha256=row['source_sha256'],decision='exclude' if reason else 'annotate',reason=reason or '来源题可形成待审核候选；答案仍为来源答案，需核验评分标准。',annotation=annotation)
            out.write(e.model_dump_json(exclude_none=False)+'\n'); total+=1
    print(f'wrote {total} entries to {OUTPUT}')

if __name__=='__main__': main()
