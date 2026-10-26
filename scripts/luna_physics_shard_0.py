#!/usr/bin/env python3
"""Reproducibly create candidate annotations for physics input shard 0.

No network/API calls are made. All labels are candidates derived from the source;
the small item_read set is stored in app/data/physics_annotation_examples_0.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.question_annotation import Annotation, source_fingerprint
from app.math_annotations import Entry
SOURCE = ROOT / 'data/annotations/physics-20261012/input-0.jsonl'
OUTPUT = ROOT / 'data/annotations/physics-20261012/output-0.jsonl'
EXAMPLES = ROOT / 'app/data/physics_annotation_examples_0.json'
BATCH = 'physics-20261012-input-0'

# These are direct source/solution inconsistencies found during item reading.
EXCLUSIONS = {
    'bank:cjeval:e2fda4bb218d4aba805d5f9d':
        '来源答案与解析冲突：答案写0.2A、1C，解析按三节电池串联应得0.15A、0.75C；需核对原题电池连接条件与答案。',
    'bank:cjeval:a7d2e8bd2a4b59b9b9114ce1':
        '来源答案与解析数值冲突：答案热量4.905×10^5 J，给定c、质量和温差计算应为4.92×10^5 J；答案、效率随之需核对。',
    'bank:cjeval:31ded231f3e578a602a18cfd':
        '来源答案与解析冲突：答案标ABD，解析称A-D均正确又称只有C正确；多选正确项无法确定。',
    'bank:cjeval:02f5b1c8e5f1a10d0446cc9d':
        '题干称潜水器“悬浮”，按平衡条件应有浮力等于重力，但来源答案写重力大于浮力；状态条件与答案冲突，需核对。',
    'bank:cjeval:1f4623829ffa2138d0ce7925':
        '来源参考答案缺失，且题目要求说明步骤；无法形成可核对的作答目标，需补齐来源答案后再纳入。',
}

def load_rows():
    return [json.loads(line) for line in SOURCE.open(encoding='utf-8') if line.strip()]

def response_format(q):
    kind = q.get('kind')
    if kind in ('single_choice', 'multiple_choice'):
        return kind
    labels = ' '.join(q.get('type_tags') or [])
    stem = q.get('stem') or ''
    if '证明题' in labels or '证明' in stem and '推导' not in stem:
        return 'proof'
    numbered = re.findall(r'(?:\([一二三四五六七八九十0-9]+\)|（[一二三四五六七八九十0-9]+）|[①②③④⑤⑥⑦⑧⑨])', stem)
    if len(numbered) >= 2:
        return 'composite'
    if '计算题' in labels or re.search(r'求|计算|多少(?:J|m|秒|千克|米|N|A|V|Ω|Pa)', stem):
        return 'calculation'
    if '填空题' in labels or '__' in stem or '____' in stem:
        return 'fill_blank'
    if '实验' in stem or '设计' in stem or '应用' in labels:
        return 'application'
    if '简答题' in labels or '解释' in stem or '说明原因' in stem:
        return 'short_answer'
    return 'short_answer'

def fine_type(q, fmt):
    tags = q.get('type_tags') or []
    stem = q.get('stem') or ''
    if fmt == 'single_choice': return ['判断物理陈述并选择唯一符合项']
    if fmt == 'multiple_choice': return ['辨析多项物理陈述并选择全部符合项']
    if '单位换算' in stem or '单位转换' in stem:
        return ['按量纲关系进行物理量单位换算']
    if '实验' in stem or '设计' in stem:
        return ['依据题设器材设计物理探究步骤并说明可观察证据']
    if '计算题' in tags:
        if '串联' in stem and '电阻' in stem: return ['串联等效电阻与欧姆定律求电流或电功']
        if '密度' in stem or '密度' in ' '.join(q.get('knowledge_tags') or []): return ['使用密度关系式结合题设测量量求物质密度']
        if '效率' in stem: return ['根据有用输出与总输入计算物理过程效率']
        if '压强' in stem: return ['依据压力和受力面积计算压强并换算单位']
        if '速度' in stem: return ['依据路程和时间计算平均速度并统一单位']
        return ['从题设物理量选择关系式并进行有单位的定量计算']
    if '填空题' in tags or '__' in stem:
        if '单位' in stem or '换算' in stem: return ['填写物理量单位或完成单位换算']
        return ['根据物理规律补全题设物理量、现象或关系']
    if '证明题' in tags: return ['依据已知物理规律建立关系并完成推导']
    if '简答题' in tags or '解释' in stem:
        return ['用相关物理规律解释题设现象并指出因果关系']
    # Generic source tags are retained as knowledge, but are not promoted into a method label.
    return ['fine_type_pending']

def candidate_constraints(q, fmt):
    stem = q.get('stem') or ''
    source_text = stem + '\n' + '\n'.join(q.get('steps') or [])
    constraints = []
    if fmt in ('calculation', 'composite') or '计算题' in (q.get('type_tags') or []):
        constraints.append('计算时先统一公式中涉及的单位；只按题干给定的数据和条件作答，不预设未说明的精度或容差。')
        if re.search(r'kW\s*[·.]?\s*h|千瓦时|度电', source_text):
            constraints.append('涉及kW·h与J时按1 kW·h=3.6×10⁶ J换算；若题设功率、时间使用kW和h，可统一在kW·h中计算。')
        if re.search(r'\b(?:mL|L)\b|升|毫升', source_text):
            constraints.append('体积参与国际单位制计算时将L换算为m³、mL换算为m³；若用水质量，须有题设密度或明确采用水的密度。')
        if re.search(r'km/h|km／h|公里每小时', source_text):
            constraints.append('速度代入SI公式前将km/h换算为m/s，或在全程中保持单位一致。')
        if re.search(r'\bmin\b|分钟|小时|\b[0-9.]+\s*h\b', source_text):
            constraints.append('时间代入以W为单位的功率公式前换算为秒；若结果保留h，须与功率单位匹配。')
        if re.search(r'cm|毫米|纳米|μm|微米', source_text):
            constraints.append('长度换算按题目目标单位统一后再代入，不直接混用cm、mm、μm、nm与m。')
        if re.search(r'℃|摄氏度', source_text):
            constraints.append('热量计算使用温度变化量Δt=末温−初温；不将摄氏温度本身当作温差。')
        if re.search(r'额定', stem):
            constraints.append('额定电压或额定功率只在题干明确的额定工作状态下使用。')
        for phrase in ('假设温度对电阻的影响可忽略不计', '忽略热量损失', '不考虑能量损失', '假设燃油完全燃烧', '燃料完全燃烧', 'g取10N/kg', 'g=10N/kg', '平坦道路上匀速行驶', '匀速直线运动'):
            if phrase in stem:
                constraints.append('适用题设条件：' + phrase + '。')
    if fmt == 'application' or any(x in source_text for x in ('实验', '探究', '测量')):
        constraints.append('实验或应用作答按题干给出的器材、步骤和条件描述；写明可观察或可记录的物理量/现象。控制变量只按题设明示要求，不补造未给出的变量。')
    return list(dict.fromkeys(constraints))[:20]

def candidate_rubric(q, fmt):
    stem = q.get('stem') or ''
    typetags = q.get('type_tags') or []
    has_calc = fmt in ('calculation', 'composite') or '计算题' in typetags
    has_exp = fmt == 'application' or any(x in stem for x in ('实验', '探究', '測量'))
    rubric = []
    if has_calc:
        rubric.extend([
            {'id':'method_evidence','description':'识别题设所求量与适用物理规律，列出关系式并按已知量代入；具体步骤和替代方法待核。','points':None,'evidence_required':'学生解答中的物理关系式、代入量及必要的单位换算。'},
            {'id':'result_evidence','description':'给出符合题干条件的结果并标明物理单位；数值、有效数字与分值待核。','points':None,'evidence_required':'学生解答中的最终数值、方向/判断（如题目要求）及单位。'},
        ])
    if has_exp:
        rubric.append({'id':'procedure_evidence','description':'按题干提供的器材和条件说明可执行的步骤，并指出可观察或记录的物理量/现象；控制变量要求待核。','points':None,'evidence_required':'学生解答中的操作步骤、观测/记录项目及题设要求的变量控制。'})
    return rubric

def base_annotation(q, method='rule_assisted', details=None):
    fmt = response_format(q)
    ktags = list(dict.fromkeys(q.get('knowledge_tags') or []))
    stem = q.get('stem') or q.get('display_stem') or ''
    candidate_types = fine_type(q, fmt)
    if method == 'rule_assisted':
        candidate_types = ['fine_type_pending']
    answer = q.get('answer')
    conflict = q.get('id') in EXCLUSIONS
    if answer and answer.strip() in ('见解析所示', '见解析', '略', '无'):
        answer = None
    issues = ['rubric_pending']
    if not q.get('knowledge_tags'):
        issues.append('knowledge_tags_pending')
    if not answer:
        issues.append('part_answer_pending')
    if q.get('has_missing_assets'):
        issues.append('required_asset_missing')
    if conflict:
        issues.extend(['source_answer_conflict', 'exclude_from_practice'])
        answer = None
    if method == 'rule_assisted' or 'fine_type_pending' in candidate_types: issues.append('fine_type_pending')
    # Whole-question part is retained unless source labels explicitly provide reliable splits.
    part = {
        'id': 'whole', 'prompt': stem, 'reference_answer': answer,
        'solution_steps': list(q.get('steps') or []),
        'knowledge_tags': ktags[:20], 'type_tags': candidate_types,
        'depends_on': [], 'points': None, 'rubric': candidate_rubric(q, fmt), 'common_errors': [],
    }
    if re.search(r'\([一二三四五六七八九十0-9]+\)|（[一二三四五六七八九十0-9]+）', stem) and answer:
        issues.append('subquestion_alignment_pending')
    mode = 'choice' if fmt in ('single_choice', 'multiple_choice') else ('numeric' if fmt == 'calculation' else ('proof' if fmt == 'proof' else 'text'))
    if fmt == 'composite': mode = 'multipart'
    annotation = {
        'schema_version': 1, 'response_format': fmt,
        'knowledge': {'primary': ktags[:1], 'supporting': ktags[1:], 'prerequisites': []},
        'fine_types': candidate_types,
        'difficulty': {'level': q.get('difficulty') if q.get('difficulty') in (1,2,3) else 2,
                       'basis': q.get('difficulty_basis') or f"来源难度标记：{q.get('difficulty_raw') or '未提供'}；未经实测校准。",
                       'origin': 'source', 'calibrated': False},
        'curriculum': {'grade': None, 'term': None, 'goal_ids': [], 'scope_status': 'unknown', 'basis': '输入年级与学期未知。'},
        'answer_spec': {'mode': mode, 'accepted_answers': [answer] if answer and mode == 'choice' else [],
                        'equivalence': 'exact' if mode == 'choice' else 'manual', 'constraints': candidate_constraints(q, fmt), 'unit': None, 'tolerance': None},
        'parts': [part],
        'grading': {'mode': 'objective' if mode == 'choice' else 'manual', 'full_score': None,
                    'allow_alternative_methods': True, 'uncertainty_policy': 'review_required'},
        'review': {'status': 'candidate', 'answer_status': 'source_only', 'issues': issues,
                   'method': method, 'notes': details or ('仅按来源元数据生成规则辅助候选；参考答案与解析未核验，得分点待人工建立。' if method == 'rule_assisted' else '')},
        'origin': {'model': 'gpt-6-luna', 'batch_id': BATCH},
    }
    return Annotation.model_validate(annotation).model_dump()

def main():
    rows = load_rows()
    examples = json.loads(EXAMPLES.read_text(encoding='utf-8')) if EXAMPLES.exists() else {}
    out = []
    for row in rows:
        q = row['question']
        fingerprint = source_fingerprint(q)
        if row.get('source_sha256') and row['source_sha256'] != fingerprint:
            raise ValueError(f"输入来源哈希不匹配: {row['question_id']}")
        decision = 'exclude' if q.get('has_missing_assets') or q.get('id') in EXCLUSIONS or q.get('status') == 'quarantine' else 'annotate'
        extra = examples.get(row['question_id'])
        if extra and extra.get('source_sha256') != row.get('source_sha256'):
            raise ValueError(f"逐题样例来源哈希已变化: {row['question_id']}")
        annotation = (extra['annotation'] if extra else base_annotation(q)) if decision == 'annotate' else None
        if annotation:
            annotation['answer_spec']['constraints'] = list(dict.fromkeys([
                *annotation['answer_spec'].get('constraints', []), *candidate_constraints(q, annotation['response_format'])
            ]))[:20]
            if not annotation['parts'][0].get('rubric'):
                annotation['parts'][0]['rubric'] = candidate_rubric(q, annotation['response_format'])
        reason = (EXCLUSIONS.get(q.get('id')) or ('题目依赖的图表或附件缺失，无法完整作答。' if q.get('has_missing_assets') else
                  ('来源选项未可靠解析，原记录缺少结构化选项，无法保证选择题完整呈现。' if q.get('status') == 'quarantine' else
                   ('逐题阅读后的候选细化；答案仍标记为 source_only，得分点待核。' if extra else '来源字段规则辅助生成候选；答案未核验，评分细则待补。'))))
        entry = Entry.model_validate({'question_id': row['question_id'], 'source_sha256': row['source_sha256'],
                                      'decision': decision, 'reason': reason, 'annotation': annotation})
        out.append(entry.model_dump_json())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text('\n'.join(out) + '\n', encoding='utf-8')
    print(f'wrote {len(out)} candidate entries to {OUTPUT}')

if __name__ == '__main__':
    main()
