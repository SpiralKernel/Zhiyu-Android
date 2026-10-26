#!/usr/bin/env python3
"""Reproducible rule-assisted candidate annotations for math shard 1.

This script does not claim full mathematical verification. Twenty selected
items have additional item_read refinements; all other candidates are marked
rule_assisted and source_only.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.question_annotation import Annotation, source_fingerprint, validate_for_question

INPUT = ROOT / 'data/annotations/math-20261011/input-1.jsonl'
OUTPUT = ROOT / 'data/annotations/math-20261011/output-1.jsonl'
EXAMPLES = ROOT / 'app/data/math_annotation_examples_1.json'
BATCH = 'math-20261011-shard1'
MANUALLY_FOUND_CONFLICTS = {
    'bank:cjeval:57a1c6b42a132950f04c97ac:a557e3b59f82': '第（2）问来源答案为3.6升而解析算为4.4升；第（3）问答案为62.2元而解析合计64.4元。',
    'bank:cjeval:9574289be6a4cdb7336b8757:f1deb96fc1a3': '路程绝对值合计57千米，按2.8升/千米应为159.6升，来源解析与答案均写152.6升。',
}

# These 20 records were individually read for the stem, source answer and
# supplied solution. Their notes add task-specific tags and evidence criteria.
ITEM_READ = {
    0: ('数轴上定距点的绝对值建模', ['数轴', '有理数', '绝对值方程'], '将距离转化为绝对值方程，并同时保留点在给定点左右两侧的解。', '只取向右移动方向而漏掉另一个等距点。'),
    22: ('相反意义量中的收入支出符号辨析', ['正负数', '相反意义的量'], '将收入的正号约定用于解释负金额，再核对所述方向与数值。', '把负数误解为较小收入，或混淆支出金额与收入金额。'),
    80: ('数轴距离性质的多问探究', ['绝对值', '数轴距离', '分类讨论'], '第（1）问计算绝对差；第（2）问解释距离对象；第（3）（4）问利用绝对值的分段或距离和下界。', '把距离恒等式误作不等式；分段时漏掉端点或整数个数。'),
    130: ('相反意义量的方向与符号填空', ['正负数', '相反意义的量'], '先依据正方向，再将负号解释为反方向，保留长度单位。', '只写“负数”而未回答具体方向和距离。'),
    390: ('负整数定义的条件辨析', ['有理数', '整数', '负数'], '逐项检查数值是否小于零且属于整数，再选出同时满足两个条件的数。', '把负分数误认为负整数，或把零归入负数。'),
    450: ('分式等式命题的真假判断', ['分式', '等式性质', '命题真假'], '检查分母非零条件，并由互为倒数相等推出原数相等或构造反例。', '忽略分母不能为零的定义域。'),
    600: ('平面直线平行判定命题辨析', ['平行线', '命题真假'], '结合平面内两条直线不相交的判定条件判断命题。', '把空间中异面直线的情形套入平面几何。'),
    751: ('盈利亏损百分率的符号表示', ['正负数', '百分率'], '沿用盈利为正的约定，把亏损的绝对量写成负百分数。', '只改写数值或遗漏百分号。'),
    906: ('二次函数顶点式读取顶点坐标', ['二次函数', '顶点式'], '将顶点式与 y=a(x-h)^2+k 对照，读出顶点 (h,k) 并核对符号。', '把括号中的 -h 直接当成横坐标。'),
    1203: ('有理数大小比较与最大值选择', ['有理数', '数轴顺序'], '将四个数按数轴顺序比较，选择最大者并核对选项。', '比较负数时误认为绝对值较大的数更大。'),
    1351: ('二次函数与 x 轴交点个数判定', ['二次函数', '一元二次方程', '判别式'], '令 y=0，将交点问题转成一元二次方程，并用判别式判断根的个数。', '未将参数系数关系代入判别式，或把相切算成两个交点。'),
    1502: ('盐与盐水质量百分率计算', ['百分数', '质量比'], '用盐的质量除以盐水总质量，再化为百分数。', '把盐质量作为分母，或误将水质量当成盐水质量。'),
    1651: ('因式分解编码规则的代数应用', ['因式分解', '代数式求值'], '按给定分解式逐因式代入数值，再依题目编码规则拼接。', '忽略因式顺序或把多项式值与因式值混同。'),
    1807: ('比例线段组辨析', ['比例线段', '比例式'], '检查四条线段的比值是否相等，注意同一比例式中的对应顺序。', '交叉配对次序错误，或只比较两条线段的大小。'),
    1951: ('相似三角形影长测高应用', ['相似三角形', '比例', '实际测量'], '用同一时刻的高与影长建立相似比，再计入地面影长和墙面影长。', '漏加投在墙上的影长，或把高影比倒置。'),
    2100: ('正切值化简三角比式', ['锐角三角函数', '代数化简'], '分子分母同除以 cos α，使用 tan α 的已知值化简并检查分母非零。', '只对分子使用正切替换，导致式子不等价。'),
    2272: ('坐标轴上三角形面积反求点坐标', ['平面直角坐标系', '三角形面积'], '以已知点 AB 为底，利用点 C 到 x 轴的水平距离确定面积，再解坐标。', '误把 C 限定在某一侧而漏掉另一解。'),
    2400: ('分式不等式的符号区间求解', ['分式不等式', '临界点', '符号分析'], '先移项通分，找分子与分母零点，分区间判号并排除使分母为零的点。', '同乘含未知数的分母而未讨论符号，或纳入不可取端点。'),
    2551: ('平行四边形第三顶点坐标分类', ['平行四边形', '坐标几何'], '根据三点作为不同顶点的可能次序，利用对角线中点或向量关系枚举坐标。', '默认给定三点相邻次序，遗漏其它合法顶点。'),
    2850: ('摸球可能性比较与等可能调整', ['概率', '等可能性'], '比较红黑球数量判断较大概率；再分配新增六球使最终两类数量相等。', '只让新增球数相等，未让袋中总数相等。'),
}
ITEM_READ_PARTS = {
    80: [
        ('计算两个有理数的差，写出去括号与绝对值化简，得到数轴距离。','符号处理错误导致把两个相反数相减为3。'),
        ('指出两个绝对值分别表示 x 与 -2 的距离，并按题意说明距离对象。','把 x+2 误读为 x 与正2的距离。'),
        ('利用两点距离和在区间内为3的性质，列出区间内整数并计数。','把恒成立区间端点漏掉，或把实数解个数和整数解个数混淆。'),
        ('用两点间距离和不小于端点距离，说明最小值为两个定点间距，并指出可取到该值的区间。','只在一个端点代值，漏掉两定点之间整段都能取到最小值。'),
    ],
    2850: [
        ('比较红球与黑球的数量（或概率分数），据此说明哪种颜色摸到的可能性大。','只比较颜色类别而没有比较各自球数。'),
        ('设新增红、黑球数并用总数量相等的条件列等式，同时满足新增总数为6，解出分配数。','误把新增红球数与新增黑球数设为相等，或忘记原袋中已有5红7黑。'),
    ],
}

def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()

def knowledge_leaf(tag):
    return clean(re.split(r'\s*(?:->|＞|/|／)\s*',str(tag))[-1])

def excluded_reason(q):
    quality = q.get('quality') or {}
    flags = set(quality.get('flags') or [])
    ans_status = (quality.get('answer_check') or {}).get('status')
    issues = set(q.get('issues') or [])
    if q.get('id') in MANUALLY_FOUND_CONFLICTS:
        return '人工阅读发现来源答案冲突：' + MANUALLY_FOUND_CONFLICTS[q['id']]
    if q.get('status') == 'quarantine':
        return '来源状态为quarantine；题目已被质量流程隔离，保留原因为：' + '、'.join(sorted(issues or flags) or ['来源隔离'])
    if ans_status in {'failed', 'conflict'} or flags.intersection({'mathematical_answer_contradiction','conflicting_source_answers','solution_choice_conflict'}):
        return '来源答案核验标记为冲突/失败，避免将矛盾答案作为练习参考。'
    if q.get('has_missing_assets'):
        return '题目依赖的图形或选项图片在来源中缺失，无法仅凭现有题干作答。'
    if not clean(q.get('stem')):
        return '题干为空或缺失，无法确定所问任务。'
    if not clean(q.get('answer')):
        return '来源未提供参考答案，且当前候选格式不能安全建立逐问答案和判分依据。'
    if flags.intersection({'invalid_choice_options_or_answer','duplicate_option_content','invalid_options'}) or issues.intersection({'invalid_choice_options_or_answer','answer_not_in_options','invalid_options'}):
        return '选择题选项或答案存在来源质量标记，选项与答案关系不可靠。'
    return None

def source_parts(stem, answer):
    # Only explicit numbered subquestion markers; require two or more so that
    # coordinates, function notation, and isolated labels do not split a task.
    pat = re.compile(r'(?<![A-Za-z0-9])(?:（[1-9]）|\([1-9]\)|[①②③④⑤⑥⑦⑧⑨])')
    # If a stem includes a worked example, only inspect markers after the last
    # explicit task-introduction cue; an example's own (1)/(2) must not split it.
    cues=('请探究','请回答','请解决','解决下列问题','请根据以上','求以下','解下列','请计算','请证明','完成下列')
    starts=[stem.rfind(cue) for cue in cues if stem.rfind(cue)>=0]
    task_start=max(starts) if starts else 0
    found = [m for m in pat.finditer(stem) if m.start() >= task_start]
    if len(found) < 2 or '选项:' in stem or '选项：' in stem:
        return [('main', clean(stem), clean(answer))], False
    def marker_info(m):
        token=m.group()
        if token.startswith('①') or token in '①②③④⑤⑥⑦⑧⑨':
            return int('①②③④⑤⑥⑦⑧⑨'.index(token))+1, 'circled'
        n=int(re.search(r'[1-9]',token).group())
        return n, 'paren'
    info=[marker_info(m) for m in found]
    marks=[m.group() for m in found]
    nums=[x[0] for x in info]
    styles=[x[1] for x in info]
    if len(found)>30 or len(set(nums))!=len(nums) or nums!=list(range(1,len(nums)+1)) or len(set(styles))!=1:
        return [('main', clean(stem), clean(answer))], False
    chunks=[]
    prefix=stem[:found[0].start()].strip()
    for i,m in enumerate(found):
        end=found[i+1].start() if i+1<len(found) else len(stem)
        body=stem[m.end():end].strip(' \n\r:：、')
        if prefix:
            body=prefix+'\n'+body
        if body:
            chunks.append((m.group(), body))
    if len(chunks)<2:
        return [('main', clean(stem), clean(answer))], False
    # Parenthesized numbers without an actual subtask (for example a range
    # written as (1)-(2)) are mathematical notation, not question boundaries.
    action=re.compile(r'计算|求|解|证明|求证|判断|说明|写出|填|确定|作图|作出|画|表示|列出|找出|比较|化简|估计|补充|探究|求出|分析|是否|回答|完成|求得|分类|可能性大|怎样|哪些|哪个|多少|几何|相同|满足|对应|最大|最小|哪一|哪天|所在|不变|变化')
    if not any(action.search(body) for _,body in chunks) and not action.search(prefix[-100:]):
        return [('main', clean(stem), clean(answer))], False
    # Match answer chunks only when an equally sized, explicit sequence occurs.
    afound=list(pat.finditer(answer))
    ainfo=[marker_info(m) for m in afound]
    answers=[]
    if len(afound)==len(chunks) and [x.group() for x in afound]==marks[:len(afound)] and [x[0] for x in ainfo]==list(range(1,len(afound)+1)) and len({x[1] for x in ainfo})==1:
        for i,m in enumerate(afound):
            end=afound[i+1].start() if i+1<len(afound) else len(answer)
            answers.append(clean(answer[m.end():end]).strip(' \n\r:：、'))
    elif len(chunks)==1:
        answers=[clean(answer)]
    else:
        answers=[None]*len(chunks)
    return [(m, body, answers[i]) for i,(m,body) in enumerate(chunks)], len(chunks)>1 and any(a is None for a in answers)

def response_format(q, stem, subq_count):
    if q.get('kind') in {'single_choice','multiple_choice'}:
        return q['kind']
    raw=' '.join(q.get('type_tags') or [])
    s=stem
    if subq_count > 1:
        return 'composite'
    if '填空' in raw or re.search(r'_{2,}|（\s*）|\(\s*\)|__', s):
        return 'fill_blank'
    if re.search(r'证明|求证|证明如下', s) and not re.search(r'判断|计算|作图|求值|求出|解方程',s):
        return 'proof'
    if re.search(r'应用|实际|某人|某校|某商店|行程|利润|收费|工程|增长|购买|高度|测量|概率', s):
        return 'application'
    if re.search(r'计算|求解|解方程|解不等式|分式不等式|化简|求值|求出|求(?:\$|x|y|m|n|面积|周长|概率)', s):
        return 'calculation'
    return 'short_answer'

def type_detail(q, fmt, stem, read_note=None):
    know=[clean(x) for x in q.get('knowledge_tags',[]) if clean(x)]
    if read_note:
        detail=read_note[0]
    else:
        s=stem
        if '分式不等式' in s or ('不等式' in s and re.search(r'/|\\frac',s)):
            detail='分式不等式符号区间求解'
        elif '方程组' in s and ('二元' in s or re.search(r'\{.*=',s)):
            detail='二元一次方程组消元求解'
        elif '抛物线' in s and '顶点' in s:
            detail='二次函数顶点式读取顶点坐标'
        elif '判别式' in s or ('图象与' in s and '交点' in s and '二次函数' in s):
            detail='二次函数与坐标轴交点个数判定'
        elif ('概率' in s or '摸到' in s or '随机' in s) and ('比较' in s or '可能性' in s):
            detail='按基本事件数比较随机事件概率'
        elif '有理数' in s and ('最大' in s or '最小' in s or '大小' in s):
            detail='有理数数轴顺序比较'
        elif '相似' in s and ('影' in s or '高度' in s):
            detail='相似三角形影长比例测高'
        elif '因式分解' in s and ('密码' in s or '因式' in s):
            detail='因式分解后代值编码'
        elif '比例线段' in ' '.join(know) or '成比例' in s:
            detail='比例线段对应比值验证'
        elif '百分比' in s or '百分率' in s:
            detail='百分率的部分量与总量计算'
        elif '数轴' in s and ('距离' in s or '单位长度' in s):
            detail='数轴两点距离的绝对值建模'
        elif fmt in {'single_choice','multiple_choice'} and know and len(knowledge_leaf(know[0]))>3 and not any(w in knowledge_leaf(know[0]) for w in ('代数','几何','算术','计数','数论','解析几何','度量几何学','能力','思想','应用题','选择题','填空题','解答题')):
            detail=f'{knowledge_leaf(know[0])}的条件辨析'
        elif fmt=='fill_blank' and know and len(knowledge_leaf(know[0]))>3 and not any(w in knowledge_leaf(know[0]) for w in ('代数','几何','算术','计数','数论','解析几何','度量几何学','能力','思想')):
            detail=f'{knowledge_leaf(know[0])}关系辨析'
        else:
            detail=''
    return [detail] if detail else []

def part_labels(labels, prompt, multipart):
    """Avoid copying all question-level tags onto every numbered subquestion."""
    if not multipart:
        return labels[:20]
    p=prompt.lower()
    concept_words=('数轴','绝对值','有理数','正负数','相反意义','方程','不等式','函数','概率','相似','比例','坐标','三角','圆','统计','整式','因式','几何','面积','运算','分类','命题','百分','行程','收费')
    matched=[]
    for label in labels:
        terms=[w for w in concept_words if w in label]
        if terms and any(w in p for w in terms): matched.append(label)
    return matched[:20]

def rubric_evidence(prompt, fmt):
    s=prompt
    if fmt in {'single_choice','multiple_choice'}:
        return '依据题设逐项核对所需定义或性质，说明所选选项满足条件，并能排除不符合条件的选项。'
    if any(w in s for w in ('证明','求证')):
        return '写出所用定义、定理或已知条件，逐步建立推理关系，并明确推出题目要求证明的结论。'
    if any(w in s for w in ('概率','可能性','摸到','随机')):
        return '明确等可能基本事件或各类结果数，列出有利结果数与总数，并化为所求概率或可能性比较。'
    if any(w in s for w in ('多少米','几千米','收费','耗油','人数','实际','某人','某校','行驶','高为','影长')):
        return '从题设数据和正负/单位约定建立对应算式或比例关系，计算目标量，并在结论中保留正确对象与单位。'
    if any(w in s for w in ('不等式','取值范围','最大值','最小值')):
        return '写出等价变形或临界点，按符号/区间条件求解，并核查端点、定义域及题目要求的取值范围。'
    if any(w in s for w in ('方程','求解')):
        return '列出与题设等价的方程或方程组，展示消元/代入等关键变形，并将所得解代回原条件核验。'
    if any(w in s for w in ('坐标','三角形','线段','角','圆','平行')):
        return '指出所用几何性质或坐标关系，写出可核对的等式/比例关系，再推出所求几何量或坐标。'
    if any(w in s for w in ('计算','化简','求值')):
        return '展示关键运算次序和等价变形，遵守符号、乘方及运算法则，并写出化简后的结果。'
    if any(w in s for w in ('填','记作','表示')):
        return '根据题目给出的定义、正方向或表示规则逐步对应所求量，并给出符合题意的完整表达。'
    return '明确使用的定义或已知关系，写出可核对的推理/计算步骤，并据此给出所求结论。'

def build(q, idx):
    reason=excluded_reason(q)
    if reason:
        return {'decision':'exclude','reason':reason,'annotation':None}
    stem=clean(q['stem']); answer=clean(q.get('answer'))
    chunks,pending=source_parts(q['stem'],q.get('answer',''))
    fmt=response_format(q,stem,len(chunks))
    read_note=ITEM_READ.get(idx)
    source_knowledge=[clean(x) for x in q.get('knowledge_tags',[]) if clean(x)]
    all_knowledge=list(dict.fromkeys(source_knowledge+(read_note[1] if read_note else [])))[:20]
    # Keep labels as supplied, then add a task/method-specific candidate label.
    fine=type_detail(q,fmt,stem,read_note)
    primary=all_knowledge[:min(5,len(all_knowledge))]
    support=all_knowledge[5:]
    prerequisites=[]
    for tag in all_knowledge:
        if any(k in tag for k in ('方程','函数','三角','概率','相似','因式','有理数','数轴','几何')):
            prerequisites.append(tag)
    issues=[]
    if pending: issues.append('part_answer_pending')
    if q.get('has_missing_assets') is False and ('<ImageHere>' in q.get('stem','') or re.search(r'如图|见图|图\s*[（(]?[一二三四1-9]',q.get('stem',''))):
        issues.append('requires_asset_review')
    if not q.get('steps'): issues.append('source_solution_missing')
    # Even a source-side checker pass is not a complete mathematical review.
    issues.append('answer_not_independently_checked')
    if q.get('can_practice') is False:
        issues.append('source_not_practice_ready')
    issues.append('score_pending')
    if read_note is None:
        issues.append('rubric_pending')
    if (read_note is None and not fine) or 'fine_type_pending' in set((q.get('quality') or {}).get('flags') or []):
        issues.append('fine_type_pending')
    if q.get('difficulty_basis')=='source_scale_uncalibrated':
        difficulty_basis='来源难度标签保留但未经本批题库校准。'
    else:
        difficulty_basis='保留来源难度值；本批次未重新校准。'
    parts=[]
    for pi,(marker,prompt,part_answer) in enumerate(chunks):
        pid='main' if marker=='main' else f'p{pi+1}'
        is_read=read_note is not None
        solution=[]
        if part_answer:
            # Source steps are preserved as evidence, without certifying them.
            for st in q.get('steps',[])[:8]:
                st=clean(st)
                if st and (len(chunks)==1 or marker in st or re.search(r'第?'+str(pi+1)+r'问|\('+str(pi+1)+r'\)|（'+str(pi+1)+r'）',st)):
                    solution.append(st[:1200])
            if not solution and len(chunks)==1:
                solution=[clean(st)[:1200] for st in q.get('steps',[])[:5] if clean(st)]
        if is_read and idx in ITEM_READ_PARTS:
            criterion,errors=ITEM_READ_PARTS[idx][min(pi,len(ITEM_READ_PARTS[idx])-1)]
        else:
            criterion=read_note[2] if is_read else rubric_evidence(prompt,fmt)
            errors=read_note[3] if is_read else '注意检查符号、运算顺序、定义域与题目所要求的单位/对象，避免只写结论而缺少可核对依据。'
        pknow=part_labels(all_knowledge,prompt,len(chunks)>1)
        ptypes=part_labels(fine,prompt,len(chunks)>1)
        if len(chunks)>1 and (not pknow or not ptypes) and 'part_tags_pending' not in issues:
            issues.append('part_tags_pending')
        if is_read and idx==80:
            labels=['绝对值距离的数值计算','数轴上距离对象辨析','绝对值和的整数解计数','两点距离和的最小值']
            ptypes=[labels[min(pi,3)]]
        if is_read and idx==2850:
            ptypes=['摸球概率大小比较','使两类球数相等的数量分配'][min(pi,1):min(pi,1)+1]
        if len(chunks)>1 and (not pknow or not ptypes) and 'part_tags_pending' not in issues:
            issues.append('part_tags_pending')
        part={
            'id':pid,'prompt':prompt[:30000],
            'reference_answer':part_answer if not pending else None,
            'solution_steps':solution[:40],
            'knowledge_tags':pknow,
            'type_tags':ptypes,
            'depends_on':[],
            'points':None,
            'rubric':[{'id':'evidence-1','description':criterion,'points':None,'evidence_required':'展示可核对的关键算式、推理关系或结论依据。'}],
            'common_errors':[{'description':errors,'knowledge_tags':pknow[:8],'type_tags':ptypes[:8]}],
        }
        parts.append(part)
    kind=q.get('kind')
    if kind in {'single_choice','multiple_choice'}:
        mode='choice'; equivalence='exact';
        accepted=[answer]
    else:
        mode={'fill_blank':'text','calculation':'expression','proof':'text','application':'text','composite':'multipart','short_answer':'text'}[fmt]
        equivalence='manual'; accepted=[]
    options=q.get('options') or []
    if kind in {'single_choice','multiple_choice'} and options:
        accepted=[answer]
    grade=q.get('grade') if q.get('grade') in (7,8,9) else None
    term=q.get('term') if q.get('term') in (1,2) else None
    is_read=read_note is not None
    val={
        'schema_version':1,'response_format':fmt,
        'knowledge':{'primary':primary,'supporting':support,'prerequisites':list(dict.fromkeys(prerequisites))[:20]},
        'fine_types':fine,
        'difficulty':{'level':q.get('difficulty') if q.get('difficulty') in (1,2,3) else 2,'basis':difficulty_basis,'origin':'source','calibrated':False},
        'curriculum':{'grade':grade,'term':term,'goal_ids':[],'scope_status':'source' if grade is not None or term is not None else 'unknown','basis':'仅保留来源明确提供的年级与学期；不依据minimum_book推断册次。' if grade is None or term is None else '年级与学期均沿用来源字段，未经教材范围复核。'},
        'answer_spec':{'mode':mode,'accepted_answers':accepted,'equivalence':equivalence,'constraints':[],'unit':None,'tolerance':None},
        'parts':parts,
        'grading':{'mode':'manual','full_score':None,'allow_alternative_methods':True,'uncertainty_policy':'review_required'},
        'review':{'status':'candidate','answer_status':'source_only','issues':issues,'method':'item_read' if is_read else 'rule_assisted','notes':('逐题阅读题干、参考答案与来源解析；未独立校验答案。' if is_read else '由来源字段及规则辅助生成候选标注，未逐题由模型核验。')+' 来源标签保留；分值未由来源明确提供时留空。'},
        'origin':{'model':'gpt-6-luna','batch_id':BATCH}
    }
    Annotation.model_validate(val)
    validate_for_question(val,q)
    return {'decision':'annotate','reason':'题干与参考答案可形成候选练习；答案仅标记为来源提供，仍待人工审核。','annotation':val}

def main():
    rows=[json.loads(s) for s in INPUT.open(encoding='utf-8') if s.strip()]
    out=[]; counts={'annotate':0,'exclude':0,'item_read':0,'part_answer_pending':0,'requires_asset_review':0}
    for idx,row in enumerate(rows):
        q=row['question']; ann=build(q,idx)
        if row['source_sha256'] != source_fingerprint(q):
            raise ValueError(f'source fingerprint mismatch at line {idx+1}')
        result={'question_id':row['question_id'],'source_sha256':row['source_sha256'],**ann}
        if ann['decision']=='annotate':
            counts['annotate']+=1
            counts['item_read']+=ann['annotation']['review'].get('method')=='item_read'
            counts['part_answer_pending']+=('part_answer_pending' in ann['annotation']['review']['issues'])
            counts['requires_asset_review']+=('requires_asset_review' in ann['annotation']['review']['issues'])
        else: counts['exclude']+=1
        out.append(json.dumps(result,ensure_ascii=False,separators=(',',':')))
    OUTPUT.write_text('\n'.join(out)+'\n',encoding='utf-8')
    EXAMPLES.parent.mkdir(parents=True,exist_ok=True)
    examples=[]
    for i in ITEM_READ:
        row=rows[i]; built=build(row['question'],i)
        if built['decision']=='annotate':
            examples.append({'question_id':row['question_id'],'source_sha256':row['source_sha256'],'question':row['question'],'annotation':built['annotation']})
    EXAMPLES.write_text(json.dumps(examples,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(counts,ensure_ascii=False))

if __name__=='__main__': main()
