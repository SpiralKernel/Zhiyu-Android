#!/usr/bin/env python3
"""Replayable rule-assisted candidate annotations for math shard 2.

This script preserves source answer claims as unverified candidate data.  It does
not certify mathematical correctness or grading scores.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.question_annotation import Annotation, source_fingerprint, validate_for_question  # noqa:E402

INPUT = ROOT / 'data/annotations/math-20261011/input-2.jsonl'
OUTPUT = ROOT / 'data/annotations/math-20261011/output-2.jsonl'
BATCH = 'math-20261011-shard2'

# These examples were read individually and have hand-written method labels,
# solution outlines, and checkable evidence. Row indices are stable in input-2.
READ = {
 0: dict(fine=['按定义辨认正负无理数与正实数'], prereq=['有理数与无理数的定义', '数的正负性'],
         steps=['比较各数与0的大小：-√3、-0.1010010001为负，π为正，0既非正也非负。',
                '√3为无理数；有限小数-0.1010010001为有理数。',
                '故负无理数是-√3；正实数包括π（题中只有π为正实数）。'],
         errors='把有限小数误判为无理数；把“实数”误当作“有理数”；将0归入正数或负数。'),
 1: dict(fine=['有向量求位移与路程费用'], prereq=['有理数加法', '绝对值表示路程', '单价×数量'],
         steps=['第(1)问将十段有向位移相加得+12千米，正号表示向东。',
                '第(2)问把各段位移取绝对值求总路程115千米；耗油11.5升，费用57.5元。'],
         errors='把位移和路程混用；路程未取各段绝对值；只乘油耗或漏乘单价。'),
 2: dict(fine=['用相反方向确定有向数符号'], prereq=['正负数表示相反意义的量'],
         steps=['约定向东为正，则相反方向向西取负号；长度8米保留，记作-8米。'],
         errors='只写8而漏负号；误把参照的+5带入答案。'),
 3: dict(fine=['由日变化量求累计产量与费用'], prereq=['有理数加法', '绝对值与实际数量', '单价计算'],
         steps=['前三天总产量为5000×3+150-250+350=15450个。',
                '星期六与星期二的产量差为(5000+400)-(5000-250)=650个。',
                '周总产量为5000×7+150-250+350-150-50+400+100=35700个；工资为35700×0.5=17850元。'],
         errors='将差异量当作实际量；累计时漏掉计划基数；金额漏乘单价。'),
 6: dict(fine=['化简带符号数并统计负数个数'], prereq=['有理数四则与乘方', '绝对值', '负号优先级'],
         steps=['分别化简各数：-(-2/5)=2/5，-48为负，15/4为正，0既非正非负，-(+5)=-5，-|-3000|=-3000。',
                '负数共有-48、-5、-3000三个，对应选项B。'],
         errors='误把-(-a)判为负数；将零计入负数；把-|-3000|误判为正数。'),
 9: dict(fine=['判断直线射线线段的基本性质'], prereq=['直线、射线、线段的定义'],
         steps=['直线无端点、两端可无限延伸；射线有一个端点，长度不能以有限长度度量。',
                '因此“射线是直线的一部分”正确，选B。'],
         errors='把射线当成可度量线段；认为直线可以比较长度；把延长线和线段端点混淆。'),
 11: dict(fine=['将收入支出转写为正负数'], prereq=['相反意义的量'],
          steps=['收入约定为正，支出与收入方向相反取负；-30元表示支出30元，选A。'],
          errors='把负号解释为收入减少到70元；混淆金额的符号与金额大小。'),
 12: dict(fine=['逐项化简乘方绝对值后判号'], prereq=['有理数乘方', '绝对值', '负号优先级'],
          steps=['依运算优先级逐项求值：-4.5为负，(1/2)^2为正，-3^2=-9为负，-|3|=-3为负，-(-3)=3为正，(-6)^2为正。',
                 '负数共有3个，选B。'],
          errors='把-3^2误算成9；把负号放进乘方底数；忽略绝对值后的外层负号。'),
 14: dict(fine=['化简选项表达式辨认负数'], prereq=['绝对值', '相反数'],
          steps=['A为正分数；B=-3为负；C=|-3|=3；D=-(-3)=3。', '只有B为负数，选B。'],
          errors='忽略绝对值非负；把双重负号仍视为负。'),
 16: dict(fine=['用绝对值距离求数轴上的两个位置'], prereq=['数轴', '绝对值表示两点距离'],
          steps=['设D表示x，距-4三个单位满足|x-(-4)|=3。',
                 '解得x=-4±3，即-1或-7，选B。'],
          errors='只向右移动；把距数轴点的距离误当成带符号差。'),
 19: dict(fine=['依据相反意义标注变化量'], prereq=['相反意义的量'],
          steps=['上涨约定为正，则下跌取负号；下跌50点表示为-50点。'],
          errors='只写50而漏负号；照抄上涨的正号。'),
 20: dict(fine=['依据相反意义确定支出数值'], prereq=['相反意义的量'],
          steps=['获得为正，花费为相反意义，花费30元记为-30元，选A。'],
          errors='把支出记为正；把30元与80元作差。'),
 21: dict(fine=['依据参照方向表示水位变化'], prereq=['相反意义的量'],
          steps=['高于正常水位约定为正，低于正常水位取负；低3米表示为-3米。'],
          errors='只写3而忽略方向符号。'),
 23: dict(fine=['将亏损表示为有向数'], prereq=['相反意义的量'],
          steps=['盈利为正，亏损为相反意义，亏损500元写作-500元。'],
          errors='将亏损金额写成正数；把净盈亏与亏损额混淆。'),
 24: dict(fine=['将水位下降转成负变化量'], prereq=['相反意义的量'],
          steps=['水位上升取正；下降方向相反，下降1米记为-1米。'],
          errors='把下降记为正数；误将已知上升量代入。'),
 26: dict(fine=['用相反意义判断损失数值'], prereq=['相反意义的量'],
          steps=['盈利为正，则损失方向相反，损失75元记为-75元，选A。'],
          errors='将损失记为正；将差额误作答案。'),
 28: dict(fine=['解释负温差的方向与大小'], prereq=['正负数表示相反意义的量'],
          steps=['上升记正，-4℃表示相反方向、变化量为4℃，即下降4℃，选B。'],
          errors='把负号看成温度为负4而非相对常温变化；误选下降3℃。'),
 29: dict(fine=['将水位下降对应到负数选项'], prereq=['相反意义的量'],
          steps=['上升记正，下降方向相反；下降4米记为-4米，选D。'],
          errors='混淆数值4和题中已知上升3；只改方向不改数值。'),
 13: dict(fine=['按借还方向累计库存变化'], prereq=['正负数表示相反意义的量', '有理数加减'],
          steps=['第一天净变化为-4+2=-2本，第二天净变化为-2+1=-1本。', '现存量为20+(-2)+(-1)=17本。'],
          errors='把借出、归还的符号颠倒；忽略初始20本。'),
 17: dict(fine=['比较相对基准的最大最小变化','合并每日变化求周期总量'], prereq=['有理数大小比较', '有理数加减', '基准量累计'],
          steps=['逐日比较变化量，最大为3日+0.8万人，最小为5日-0.6万人，差为1.4万人。',
                 '七日变化量和为1.1万人；七天游客总量为2×7+1.1=15.1万人。'],
          errors='将相对9月30日的变化值直接当作游客总数；总量只加变化和而漏乘基准2万人×7天。'),
}

PART_RE = re.compile(r'(?m)(?:^|[\s。；，：:？！!?）0-9])([（(])\s*([1-9][0-9]*)\s*([）)])\s*')
TASK_CUE = re.compile(r'求|证明|说明|计算|解出?|判断|比较|写出|填(?:写|出)?|指出|确定|画出|作出|作图|求作|选择|回答|分析|分类|化简|求证|解释|概括|给出|多少|哪个|哪些|何处|是否|请问')
RESPONSE_LABELS = {'单选题','多选题','填空题','计算题','解答题','证明题','选择题','应用题','composite','single_choice','multiple_choice','calculation','fill_blank','proof','application','short_answer'}

def valid_part_markers(stem):
    matches=[]; seen=set()
    for m in PART_RE.finditer(stem):
        if m.group(1)=='(' and m.group(3)!=')': continue
        if m.group(1)=='（' and m.group(3)!='）': continue
        n=m.group(2)
        if n in seen: continue
        seen.add(n); matches.append(m)
    nums=[int(m.group(2)) for m in matches]
    if len(nums)<2 or nums[0]!=1 or nums!=list(range(1,len(nums)+1)): return []
    if len({(m.group(1),m.group(3)) for m in matches})!=1: return []
    prompts=[]
    for i,m in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else len(stem)
        prompts.append(stem[m.end():end].strip(' \n，；。'))
    # Ignore formula parentheses and numbered references unless every marked
    # section has an explicit mathematical task in its prose.
    if any(not TASK_CUE.search(p[:180]) for p in prompts): return []
    return matches

def safe_task_types(labels):
    form=re.compile(r'单选题|多选题|填空题|计算题|解答题|证明题|选择题|应用题|single_choice|multiple_choice|calculation|fill_blank|proof|application|composite|short_answer',re.I)
    return [x for x in labels if x and x not in RESPONSE_LABELS and not form.search(x) and not re.search(r'[A-Za-z]',x)]

def choice_labels(q):
    labels = q.get('knowledge_tags') or q.get('derived_knowledge_tags') or []
    return [str(x).strip() for x in labels if str(x).strip()][:20]

def task_type(q, stem, read=None):
    if read: return read['fine']
    s = stem
    rules = [
      (r'证明|证(?:明|得)', '依据定义与已知条件完成证明'),
      (r'解方程|方程的解|求.*未知数|解不等式', '列式并求解方程或不等式'),
      (r'函数|反比例|一次函数|抛物线|二次函数', '利用函数关系求值或判断图象性质'),
      (r'统计图|频数|平均数|中位数|众数|概率|随机', '从统计数据计算特征量或概率'),
      (r'圆周角|圆心角|切线|弦|圆内接', '利用圆的性质求角度或线段'),
      (r'相似|全等|平行四边形|三角形|角平分线|垂直', '利用几何性质求量或判定关系'),
      (r'数轴|坐标|点.*移动|平移', '根据数轴或坐标变换求位置'),
      (r'应用题|路程|速度|利润|费用|油费|人数|增长|下降|实际', '建立数量关系解决实际问题'),
      (r'化简|求值|代数式|整式|因式分解', '按运算规则化简代数式或代入求值'),
      (r'面积|周长|体积|表面积', '利用几何度量公式计算'),
      (r'有理数|无理数|实数|正数|负数|绝对值', '依据数的定义化简并判断数的性质'),
      (r'计算|求.*值|等于', '按题设运算求出结果'),
    ]
    for pat, label in rules:
      if re.search(pat, s): return [label]
    # Source fine labels are preserved when they describe a task; otherwise use
    # a conservative statement of the observable response task.
    src = [str(x.get('label', '')).strip() for x in q.get('fine_type_annotations', [])
           if x.get('basis') not in {'source_knowledge_leaf','source_knowledge_pattern'} and x.get('label')]
    src=safe_task_types(src)
    if src: return src[:4]
    if q.get('kind') in {'single_choice','multiple_choice'}: return ['根据题干条件判断选项']
    return ['按题干要求求值或作答']

def response(q, stem):
    k = q.get('kind')
    if k in ('single_choice','multiple_choice'):
        return k, 'choice'
    tags = ' '.join(q.get('type_tags') or [])
    if q.get('kind') not in {'single_choice','multiple_choice'} and valid_part_markers(stem):
        return 'composite', 'multipart'
    if '证明' in tags or re.search(r'证明|说明理由', stem): return 'proof', 'proof'
    if '填空' in tags or re.search(r'_{2,}|__|填入|填空', stem): return 'fill_blank', 'text'
    if re.search(r'应用题|求.*费用|实际.*求|应用', tags + stem): return 'application', 'text'
    if '计算' in stem: return 'calculation', 'expression'
    if len(q.get('steps') or []) and re.search(r'求|计算|化简', stem): return 'calculation', 'expression'
    return 'short_answer', 'text'

def split_parts(stem, answer, steps, labels, types, read, allow_split=True):
    matches=valid_part_markers(stem)
    if not allow_split or len(matches) < 2:
        outline=(read['steps'] if read else steps[:6])
        criterion=('关键依据：'+'；'.join(outline[:4]))[:1800] if outline else ''
        return [dict(id='1', prompt=stem.strip() or '请作答。', reference_answer=answer,
                     solution_steps=outline, knowledge_tags=labels[:20], type_tags=types[:20],
                     rubric=[dict(id='evidence', description=criterion, points=None,
                                  evidence_required=criterion)] if answer and criterion else [],
                     common_errors=[dict(description=read['errors'],knowledge_tags=labels[:4],type_tags=types[:4])] if read else [])]
    spans=[]
    for i,m in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else len(stem)
        spans.append((m.group(2), stem[m.end():end].strip(' \n，；。')))
    ans_lines=[x.strip() for x in re.split(r'\n+', answer or '') if x.strip()]
    steptext=' '.join(steps)
    parts=[]
    for i,(num,prompt) in enumerate(spans):
        ans=None
        # Answer rows are mapped only when cardinality and ordering are explicit.
        if len(ans_lines)==len(spans): ans=ans_lines[i]
        elif answer and re.search(rf'(?:第\s*{num}\s*问|[{num}][、.：:])', answer):
            mm=re.search(rf'(?:第\s*{num}\s*问|[{num}][、.：:])\s*([^\n；]+)', answer)
            if mm: ans=mm.group(1).strip()
        part_steps=[]
        if read and read.get('steps') and len(read['steps'])==len(spans): part_steps=[read['steps'][i]]
        elif len(steps)>1 and len(steps)==len(spans): part_steps=steps[i:i+1]
        elif len(steps)==1:
            # Step text is partitioned only where source prose uses explicit
            # line-start numbered subanswers.
            sections=re.split(r'(?m)(?:^|\n)\s*[（(]([1-9][0-9]*)[）)]\s*',steps[0])
            numbered={sections[j]:sections[j+1].strip() for j in range(1,len(sections)-1,2)}
            if num in numbered and numbered[num]: part_steps=[numbered[num][:1800]]
        p_labels=[x for x in labels if x and x in prompt]
        p_types=[types[0]]
        if read and read.get('part_fine') and i<len(read['part_fine']): p_types=[read['part_fine'][i]]
        elif not read: p_types=task_type({},prompt,None)
        p_types=safe_task_types(p_types) or ['按本问要求作答']
        errs=[dict(description=read['errors'],knowledge_tags=p_labels[:4],type_tags=p_types[:4])] if read else []
        rubric=[]
        if ans and part_steps:
            criterion=('关键依据：'+'；'.join(part_steps))[:1800]
            rubric=[dict(id='evidence',description=criterion,points=None,evidence_required=criterion)]
        parts.append(dict(id=str(num),prompt=prompt or f'第{num}问',reference_answer=ans,solution_steps=part_steps,
                          knowledge_tags=p_labels[:20],type_tags=p_types[:20],depends_on=[],points=None,
                          rubric=rubric,common_errors=errs))
    return parts

def main():
    rows=[json.loads(line) for line in INPUT.open(encoding='utf-8') if line.strip()]
    out=[]; excludes=0; waiting=0; item_read=0
    for idx,row in enumerate(rows):
        q=row['question']; stem=str(q.get('stem') or '').strip(); answer=q.get('answer')
        flags=set(q.get('quality',{}).get('flags',[])); issues=set(q.get('issues',[]))
        exclude_reason=None
        if q.get('status')=='quarantine': exclude_reason='来源已标记quarantine；保留隔离状态。'
        elif q.get('has_missing_assets') or 'missing_figure' in flags or 'unresolved_image_placeholder' in flags:
            exclude_reason='题目依赖缺失图形或素材，当前文本不足以确定题意。'
        elif flags & {'mathematical_answer_contradiction','solution_choice_conflict','conflicting_source_answers','duplicate_option_content'}:
            exclude_reason='来源质量标记显示答案冲突或选项重复，暂不可作为有效候选。'
        elif not stem or not answer:
            exclude_reason='题干或参考答案缺失，无法形成可核对的候选标注。'
        # Manual arithmetic identifies the contradictory answer in this item.
        if idx==22: exclude_reason='人工核算发现源答案与题意矛盾：从±4平移+4再-5应为3或-5。'
        if exclude_reason:
            out.append(dict(question_id=row['question_id'],source_sha256=row['source_sha256'],decision='exclude',reason=exclude_reason,annotation=None)); excludes+=1; continue
        manual=READ.get(idx)
        labels=choice_labels(q)
        kinds=safe_task_types(task_type(q,stem,manual)) or ['按题干要求作答']
        fmt,mode=response(q,stem)
        if q.get('kind') in {'single_choice','multiple_choice'}:
            accepted=[str(answer).strip()]
        else: accepted=[str(answer).strip()]
        steps=list(q.get('steps') or [])
        if manual and idx==1: manual['part_fine']=['有向位移求终点位置','按总路程计算油费']
        if manual and idx==3: manual['part_fine']=['按计划量与增减量求累计产量','比较最大与最小日增减量','按周产量与计件单价计算工资']
        if manual and idx==17: manual['part_fine']=['比较最大最小游客变化并求差','按基准人数累计七日总量']
        parts=split_parts(stem,str(answer),steps,labels,kinds,manual,allow_split=q.get('kind') not in {'single_choice','multiple_choice'})
        issues_out=[]
        if any(p['reference_answer'] is None for p in parts):
            issues_out.append('part_answer_pending'); waiting+=sum(p['reference_answer'] is None for p in parts)
        if any(not p['rubric'] for p in parts) or manual is None: issues_out.append('rubric_pending')
        issues_out.append('score_pending')
        if kinds in (['根据题干条件判断选项'],['按题干要求求值或作答']):
            issues_out.append('fine_type_pending')
        if not steps and manual is None: issues_out.append('solution_steps_missing')
        # Missing scoring source is always explicit; no inferred points.
        if q.get('grade') is None or q.get('term') is None: pass
        curriculum_basis='册次/学期仅沿用来源字段；无来源值时保持unknown。'
        difficulty=q.get('difficulty') if q.get('difficulty') in (1,2,3) else 2
        basis=str(q.get('difficulty_basis') or 'source_scale_uncalibrated')
        if manual: basis += '；item_read复杂度：'+('需区分方向/位移与路程' if idx in (1,3) else '运算步骤与概念判别见人工阅读记录。')
        manual_notes='逐题阅读题干、源答案及解题步骤；已补充本题特定任务标签、答案推导和常见误区。' if manual else '规则辅助抽取来源答案、来源知识标签和题型；未逐题人工核验答案。'
        ansstatus='conflict' if flags & {'mathematical_answer_contradiction','solution_choice_conflict','conflicting_source_answers'} else 'source_only'
        if ansstatus=='conflict': issues_out.append('source_answer_conflict')
        a=Annotation.model_validate(dict(
          response_format=fmt,
          knowledge=dict(primary=labels[:20],supporting=[],prerequisites=(manual['prereq'] if manual else [])),
          fine_types=kinds,
          difficulty=dict(level=difficulty,basis=basis[:2000],origin='source'),
          curriculum=dict(grade=q.get('grade'),term=q.get('term'),goal_ids=[],scope_status='unknown',basis=curriculum_basis),
          answer_spec=dict(mode=mode,accepted_answers=accepted,equivalence=('numeric' if mode=='numeric' else ('symbolic' if mode=='expression' else ('rubric' if mode=='proof' else 'manual'))),constraints=[],unit=None,tolerance=None),
          parts=parts,
          grading=dict(mode='manual',full_score=None,allow_alternative_methods=True,uncertainty_policy='review_required'),
          review=dict(status='candidate',answer_status=ansstatus,issues=issues_out,method=('item_read' if manual else 'rule_assisted'),notes=manual_notes),
          origin=dict(model='gpt-6-luna',batch_id=BATCH)))
        validate_for_question(a.model_dump(),q)
        out.append(dict(question_id=row['question_id'],source_sha256=row['source_sha256'],decision='annotate',reason='保留为未发布候选；答案与评分仍需教师核对。',annotation=a.model_dump()))
        if manual: item_read+=1
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with OUTPUT.open('w',encoding='utf-8') as f:
        for x in out: f.write(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n')
    example_path=ROOT/'app/data/math_annotation_examples_2.json'
    example_path.parent.mkdir(parents=True,exist_ok=True)
    examples=[dict(question_id=x['question_id'],source_sha256=x['source_sha256'],
                   question=rows[i]['question'],annotation=x['annotation'])
              for i,x in enumerate(out) if x.get('annotation') and x['annotation']['review']['method']=='item_read']
    example_path.write_text(json.dumps(examples,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    pending_score_parts=sum(1 for x in out if x.get('annotation') for p in x['annotation']['parts'] if p.get('points') is None)
    print(json.dumps(dict(total=len(out),annotate=len(out)-excludes,exclude=excludes,item_read=item_read,part_answer_pending=waiting,
                          pending_score_parts=pending_score_parts,examples=len(examples),output=str(OUTPUT),examples_path=str(example_path)),ensure_ascii=False))

if __name__=='__main__': main()
