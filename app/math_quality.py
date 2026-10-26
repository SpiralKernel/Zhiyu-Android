"""可重放的数学题库标注与保守质检；不调用模型，不冒充教师审定。

来源标签不覆盖。规则标签只是候选；精确分数运算发现反例则隔离，
未支持的表达式保留未核验，不能通过字符串求值执行任意代码。
"""
import ast
import copy
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from fractions import Fraction

VERSION = "junior-math-quality-2026.10.11.2"

# Pattern, fine task, curriculum knowledge alias. These are candidate classifications,
# not an inference that all questions sharing a word have the same solution structure.
RULES = [
    (r"相反意义|正负数在实际|正数[、和，]负数的意义", "相反意义数量的符号表示", "正数和负数"),
    (r"有理数的分类|有理数的概念|属于.*有理数|有理数有.*个", "有理数与非有理数的分类辨析", "有理数的分类"),
    (r"数轴上两点.*距离|数轴.*相距", "数轴两点距离与绝对值建模", "数轴"),
    (r"数轴上的动点|数轴.*动点", "数轴动点的位置与距离关系", "数轴"),
    (r"相反数", "相反数的定义与性质辨析", "相反数"),
    (r"有理数大小比较|有理数的大小比较|比较.*负数.*大小", "有理数大小关系判断", "有理数的大小比较"),
    (r"绝对值.*方程", "绝对值方程的分类讨论", "绝对值"),
    (r"绝对值", "绝对值的意义与条件求值", "绝对值"),
    (r"科学[记计]数法", "科学记数法的指数与数位转换", "科学记数法"),
    (r"近似数|精确到|有效数字", "近似数与指定数位的精确度", "近似数"),
    (r"有理数.*混合运算", "有理数混合运算的顺序与符号", "有理数混合运算"),
    (r"有理数.*加[减法]|有理数的减法", "有理数加减的符号与运算律", "有理数加减"),
    (r"有理数.*乘[除法]|有理数的除法|倒数", "有理数乘除与倒数的条件", "有理数乘除"),
    (r"有理数.*乘方", "负数乘方的符号与作用范围", "有理数的乘方"),
    (r"列代数式|用字母表示数|代数式的意义", "数量关系的代数式表示", "列代数式"),
    (r"代数式.*求值|代数式的值|已知字母的值", "代数式代入与整体求值", "代数式的值"),
    (r"单项式.*系数|单项式.*次数|多项式.*项数|多项式.*次数", "整式的项、系数与次数识别", "单项式"),
    (r"同类项", "同类项识别及系数合并", "合并同类项"),
    (r"去括号|整式的加减", "去括号变号与整式化简", "整式的加减"),
    (r"等式.*性质|等式.*变形", "等式变形的运算条件判断", "等式的性质"),
    (r"一元一次方程.*应用|一元一次方程.*实际", "一元一次方程的情境建模", "一元一次方程的应用"),
    (r"解一元一次方程|一元一次方程的解法", "一元一次方程的等价变形求解", "一元一次方程"),
    (r"一元一次方程的概念|方程为一元一次方程|一元一次方程的是", "一元一次方程的结构识别", "一元一次方程的概念"),
    (r"线段.*中点|中点.*线段", "中点条件的线段和差计算", "线段的中点"),
    (r"角平分线", "角平分线条件的角度和差", "角平分线"),
    (r"余角|补角", "余角补角的和差与倍数关系", "余角和补角"),
    (r"展开图|几何体.*展开", "几何体展开图的面对应判断", "展开图"),
    (r"截一个几何体|截面", "几何体截面的形状判断", "几何体"),
    (r"直线.*射线|射线.*线段", "直线射线线段的端点与延伸", "直线射线线段"),
    (r"对顶角|同位角|内错角|同旁内角|平行线", "相交线和平行线中的角关系", "平行线"),
    (r"平面直角坐标系|点的坐标|坐标与图形", "坐标与点的位置关系", "平面直角坐标系"),
    (r"抽样调查|统计调查|频数|直方图", "统计调查与频数分布解释", "统计调查"),
    (r"二元一次方程组|加减消元|代入消元", "二元一次方程组的消元求解", "二元一次方程组"),
    (r"不等式组", "一元一次不等式组解集的交集", "一元一次不等式组"),
    (r"一元一次不等式", "一元一次不等式的变形与解集", "一元一次不等式"),
    (r"平方根|立方根|实数的运算", "实数根式的定义与混合运算", "实数"),
    (r"整式的乘除|幂的运算|乘法公式", "整式乘除与乘法公式应用", "整式的乘除"),
    (r"因式分解", "因式分解的方法选择与参数", "因式分解"),
    (r"分式方程", "分式方程的去分母与验根", "分式方程"),
    (r"分式.*化简|分式.*运算", "分式运算与分母非零条件", "分式"),
    (r"全等三角形|三角形全等", "全等三角形的对应与判定", "全等三角形"),
    (r"三角形内角和|三角形的外角|三角形的三边|多边形内角和", "三角形多边形的边角约束", "三角形内角和"),
    (r"轴对称", "轴对称的对应点与作图性质", "轴对称"),
    (r"二次根式", "二次根式的化简与运算条件", "二次根式"),
    (r"勾股定理|勾股数", "勾股定理与逆定理的条件", "勾股定理"),
    (r"平行四边形|矩形|菱形|正方形", "特殊四边形的性质与判定", "四边形"),
    (r"一次函数|正比例函数", "一次函数解析式与图象关系", "一次函数"),
    (r"平均数|中位数|众数|方差", "统计量计算与数据解释", "数据的分析"),
    (r"一元二次方程|根的判别式|根与系数", "一元二次方程的根与参数条件", "一元二次方程"),
    (r"二次函数|抛物线", "二次函数的图象性质与交点", "二次函数"),
    (r"反比例函数", "反比例函数的乘积与图象", "反比例函数"),
    (r"圆周角|圆心角|垂径定理|点与圆|扇形|弧长", "圆中的角弦弧关系与计算", "圆的有关性质"),
    (r"切线|直线与圆", "圆的切线判定与性质", "圆的切线"),
    (r"相似三角形|相似多边形|位似", "相似图形的对应比例与判定", "相似三角形"),
    (r"锐角三角函数|正弦|余弦|正切|解直角三角形", "锐角三角函数的边角对应", "锐角三角函数"),
    (r"三视图|正投影", "三视图的方向与尺寸对应", "三视图"),
    (r"概率|树状图|列表法", "等可能样本的计数与概率", "概率"),
]

# Lower bounds only. This does not assign a semester to an ungraded source.
LATER_TOPICS = [
    (9, r"一元二次方程|二次函数|抛物线|反比例函数|相似三角形|位似|圆周角|圆心角|垂径定理|圆的切线|锐角三角函数|正弦|余弦|正切"),
    (8, r"二次根式|因式分解|整式的乘除|全等三角形|勾股定理|分式方程|一次函数|平行四边形|矩形|菱形"),
]


def minimum_grade(q):
    text = '\n'.join(q.get('knowledge_tags', [])) + '\n' + q.get('stem', '')
    return next((grade for grade, pattern in LATER_TOPICS if re.search(pattern, text)), 7)


def minimum_book(q):
    text = '\n'.join(q.get('knowledge_tags', [])) + '\n' + q.get('stem', '')
    bounds = [
        ('math-9-2', r'相似三角形|相似多边形|位似|锐角三角函数|正弦|余弦|正切|三视图|正投影'),
        ('math-9-1', LATER_TOPICS[0][1]),
        ('math-8-2', r'二次根式|勾股定理|勾股数|一次函数|平行四边形|矩形|菱形|方差'),
        ('math-8-1', LATER_TOPICS[1][1] + r'|整式的乘法|幂的运算|三角形内角和|三角形的外角|轴对称'),
        ('math-7-2', r'二元一次|不等式|平方根|立方根|无理数|实数|平面直角坐标系|对顶角|同位角|内错角|平行线'),
    ]
    return next((book for book, pattern in bounds if re.search(pattern, text)), 'math-7-1')


def normalized(value):
    return "".join(unicodedata.normalize("NFKC", str(value)).split()).casefold()


def math_text(value):
    """Translate a deliberately small LaTeX subset; leave unknown commands invalid."""
    text = unicodedata.normalize("NFKC", value).replace("−", "-").replace("×", "*").replace("÷", "/")
    for command in (r"\left", r"\right", r"\displaystyle", r"\quad", r"\qquad", r"\,", r"\;", r"\!"):
        text = text.replace(command, "")
    text = re.sub(r"\\(?:mathrm|text)\s*\{\s*([a-z])\s*\}", r"\1", text)
    # Find balanced braces rather than silently truncating nested fractions.
    def group(start):
        while start < len(text) and text[start].isspace():
            start += 1
        if start >= len(text) or text[start] != "{":
            raise ValueError("fraction braces required")
        depth = 1
        for end in range(start + 1, len(text)):
            depth += (text[end] == "{") - (text[end] == "}")
            if depth == 0:
                return text[start + 1:end], end + 1
        raise ValueError("unbalanced fraction")
    for _ in range(30):
        match = re.search(r"\\(?:dfrac|tfrac|frac)\s*", text)
        if not match:
            break
        num, end = group(match.end())
        den, end = group(end)
        text = text[:match.start()] + f"(({num})/({den}))" + text[end:]
    for command, replacement in [(r"\times", "*"), (r"\cdot", "*"), (r"\div", "/")]:
        text = text.replace(command, replacement)
    return text.replace("$", "").replace("{", "(").replace("}", ")").replace("^", "**")


def exact_value(expression, variables=None):
    text = math_text(expression)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"(?<=[0-9a-z)])(?=[a-z(])", "*", text)
    text = re.sub(r"(?<=\))(?=\d)", "*", text)
    if len(text) > 400 or not re.fullmatch(r"[0-9a-z.+*/()\-]+", text):
        raise ValueError("unsupported expression")
    tree = ast.parse(text, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 100:
        raise ValueError("expression too large")
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            return Fraction(str(node.value))
        if isinstance(node, ast.Name) and variables and node.id in variables:
            return variables[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = visit(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            a, b = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): return a + b
            if isinstance(node.op, ast.Sub): return a - b
            if isinstance(node.op, ast.Mult): return a * b
            if isinstance(node.op, ast.Div): return a / b
            if isinstance(node.op, ast.Pow) and b.denominator == 1 and abs(b) <= 12 and abs(a) <= 10**12:
                return a ** int(b)
        raise ValueError("unsupported expression")
    return visit(tree.body)


def answer_check(q):
    """Only solve exact standalone numerical prompts; otherwise check given roots.

    A root satisfying equations is partial consistency, never full solution proof.
    Unsupported text / multiple subquestions abstain from full verification.
    """
    stem = re.sub(r"^题目内容\s*[:：]\s*", "", q['stem']).strip()
    stem = re.split(r"选项\s*[:：]", stem)[0].strip()
    base = {"status": "unchecked", "method": None}
    try:
        simple = math_text(stem).strip().rstrip('。.．?？').strip()
        simple = re.sub(r"\(\s*~?\s*\)$", "", simple).strip().rstrip('=').strip()
        match = re.fullmatch(r"(?:计算|求值|计算下列各式)\s*[:：]?\s*(.+?)(?:的(?:值|结果)(?:是|为)?|是|为)?", simple, re.S)
        unary = re.fullmatch(r"(.+?)的(相反数|绝对值|倒数)(?:是|为)", simple, re.S)
        scientific = None if re.search(r'精确|保留|有效数字', stem) else (
            re.search(r"(?:数字?|将|数据)\s*([0-9]+(?:\.[0-9]+)?)\s*(万|亿)?\s*用科学[记计]数法(?:可以)?表示为$", simple)
            or re.search(r"用科学[记计]数法表示\s*([0-9]+(?:\.[0-9]+)?)\s*(万|亿)?\s*为$", simple))
        if match or unary or scientific:
            method = 'exact_rational_arithmetic'
            if unary:
                value = exact_value(unary[1])
                expected = -value if unary[2]=='相反数' else abs(value) if unary[2]=='绝对值' else 1/value
                method = 'numeric_' + {'相反数':'opposite','绝对值':'absolute','倒数':'reciprocal'}[unary[2]]
            elif scientific:
                expected = Fraction(scientific[1]) * {'万':10000,'亿':100000000,None:1}[scientific[2]]
                method = 'scientific_notation_value_and_form'
            else:
                expected = exact_value(match[1].strip().rstrip('='))
            if q['kind'] == 'single_choice':
                values = {o['key']: exact_value(o['text']) for o in q['options']}
                valid_forms = set(values)
                if scientific:
                    valid_forms = set()
                    for o in q['options']:
                        form = re.sub(r'\s+', '', math_text(o['text']))
                        tree = ast.parse(form, mode='eval').body
                        if (isinstance(tree, ast.BinOp) and isinstance(tree.op, ast.Mult)
                                and isinstance(tree.right, ast.BinOp) and isinstance(tree.right.op, ast.Pow)
                                and exact_value(ast.unparse(tree.right.left)) == 10
                                and exact_value(ast.unparse(tree.right.right)).denominator == 1
                                and 1 <= abs(exact_value(ast.unparse(tree.left))) < 10):
                            valid_forms.add(o['key'])
                matches = [k for k, v in values.items() if v == expected and k in valid_forms]
                if len(matches) != 1:
                    return {"status": "failed", "method": method, "reason": "no_unique_correct_option", "computed": str(expected)}
                correct = q['answer'] == matches[0]
            elif q['kind'] == 'reference':
                if scientific:
                    return base  # Written notation needs the same coefficient-form check.
                correct = exact_value(q['answer']) == expected
            else:
                return base
            return {"status": "passed" if correct else "failed", "method": method, "computed": str(expected)}
        # Only extract an explicitly delimited source equation system. Do not search
        # loose fragments, which could omit a coefficient or a condition.
        systems = list(re.finditer(r"\\begin\{(cases|array|align|aligned)\}(.*?)\\end\{\1\}", stem, re.S))
        if len(systems) != 1:
            return base
        body = systems[0][2]
        body = re.sub(r"^\s*\{[clr| ]+\}", "", body).replace("&", "")
        equations = [s.strip().strip('。．') for s in re.split(r"\\\\|;|；", body) if s.strip()]
        if len(equations) not in {2, 3} or any(s.count('=') != 1 for s in equations):
            return base
        answer = math_text(q['answer'].strip().removeprefix('{').removesuffix('}'))
        assignments = re.findall(r"(?<![a-z])([xyab])\s*=\s*([^,;，；\n\\]+)", answer)
        values = {}
        for name, value in assignments:
            value = value.strip().rstrip('。．')
            # A rendered cases ending creates a ')' delimiter, not part of the value.
            if value.count(')') > value.count('('):
                return base
            parsed = exact_value(value)
            if name in values and values[name] != parsed:
                return base
            values[name] = parsed
        if len(values) < 2:
            return base
        residuals = []
        for equation in equations:
            lhs, rhs = equation.split('=')
            residuals.append(str(exact_value(lhs, values) - exact_value(rhs, values)))
        failed = any(Fraction(v) != 0 for v in residuals)
        return {"status": "failed" if failed else "partial_consistency", "method": "substitute_source_system",
                "assigned_values": {k: str(v) for k, v in values.items()}, "residuals": residuals}
    except (ValueError, TypeError, SyntaxError, ZeroDivisionError, OverflowError):
        return base


def annotate(q):
    q = copy.deepcopy(q)
    if q.get('subject') != 'math' or q.get('stage') != 'junior':
        return q
    annotations = []
    # Use precise source leaves first; do not turn ability/thinking/format labels into
    # knowledge points. CMM only supplies a broad domain and needs rule candidates.
    leaves = [t.split('->')[-1].strip() for t in q.get('knowledge_tags', [])
              if not any(x in t for x in ('->能力->', '->思想->', '->方法->'))]
    broad = {'算术', '代数', '度量几何学', '解析几何', '计数', '组合几何学', '画法几何学',
             '立体几何学', '变换几何', '组合数学', '逻辑题', '统计数学', '图论'}
    for label in dict.fromkeys(leaves):
        if label not in broad and len(label) >= 4:
            annotations.append({'label': label, 'origin': 'source_derived', 'basis': 'source_knowledge_leaf', 'needs_review': True})
    haystack = '\n'.join(q.get('knowledge_tags', []))
    use_stem = not annotations
    if use_stem:
        haystack += '\n' + q['stem']
    inferred = []
    for pattern, label, knowledge in RULES:
        if m := re.search(pattern, haystack):
            if not any(a['label'] == label for a in annotations):
                annotations.append({'label': label, 'origin': 'heuristic', 'basis': 'stem_pattern' if use_stem else 'source_knowledge_pattern',
                                    'matched': m[0], 'needs_review': True})
            if knowledge not in q.get('knowledge_tags', []):
                inferred.append(knowledge)
    q['fine_type_annotations'] = annotations
    q['derived_knowledge_tags'] = list(dict.fromkeys(inferred))
    q['curriculum_minimum_grade'] = minimum_grade(q)
    q['curriculum_minimum_book'] = minimum_book(q)
    check = answer_check(q)
    flags = []
    if check['status'] == 'failed': flags.append('mathematical_answer_contradiction')
    if not q.get('steps'): flags.append('missing_solution')
    if q.get('has_missing_assets'): flags.append('missing_figure')
    content = q['stem'] + '\n' + '\n'.join(o['text'] for o in q.get('options', []))
    if '<ImageHere>' in content: flags.append('unresolved_image_placeholder')
    options = q.get('options', [])
    if options and len({normalized(o['text']) for o in options}) != len(options):
        flags.append('option_figures_pending' if q.get('has_missing_assets') else 'duplicate_option_content')
    if not annotations: flags.append('fine_type_pending')
    # Explicit final-choice assertions are only a consistency signal, not a solver.
    conclusions = re.findall(r"(?:故选|故答案为|答案选|正确答案[为是])\s*[:：]?\s*(?:\$|\\(?:text|mathrm)\s*\{|\s)*([A-D])\b", '\n'.join(q.get('steps', [])))
    if q['kind'] == 'single_choice' and conclusions and set(conclusions) != {q['answer']}:
        flags.append('solution_choice_conflict')
    fatal = {'mathematical_answer_contradiction', 'duplicate_option_content', 'solution_choice_conflict'}
    if fatal.intersection(flags):
        q['status'] = 'quarantine'
    q['issues'] = list(dict.fromkeys([*q.get('issues', []), *flags]))
    q.setdefault('difficulty_basis', 'source_scale_uncalibrated' if q.get('difficulty_raw') is not None else 'unknown_default_not_calibrated')
    q['quality'] = {'version': VERSION, 'content_sha256': hashlib.sha256(json.dumps(
        {k: q.get(k) for k in ['stem', 'options', 'answer', 'steps', 'knowledge_tags']}, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        'answer_check': check, 'flags': flags, 'classification_reviewed': False,
        'solution_reviewed': False, 'practice_requires': ['solution', 'fine_type', 'complete_assets', 'no_contradiction'],
        'tier': 'quarantine' if q['status'] == 'quarantine' else
        'asset_pending' if q.get('has_missing_assets') else 'solution_pending' if not q.get('steps') else
        'rule_checked' if check['status'] == 'passed' else 'source_answer_only'}
    return q


def curate(records):
    """Batch check identical questions with conflicting answers before publishing any."""
    qs = [annotate(q) for q in records]
    identities = defaultdict(list)
    for q in qs:
        if q.get('subject') != 'math' or q.get('stage') != 'junior':
            continue
        identity = question_identity(q)
        identities[identity].append(q)
    for group in identities.values():
        def answer_key(q):
            answer = normalized(q['answer'])
            return ''.join(sorted(set(answer))) if q['kind']=='multiple_choice' else answer
        if len({answer_key(q) for q in group}) <= 1:
            continue
        for q in group:
            q['status'] = 'quarantine'
            q['issues'] = list(dict.fromkeys([*q.get('issues', []), 'conflicting_source_answers']))
            if q.get('quality'):
                q['quality']['tier'] = 'quarantine'
                q['quality']['flags'].append('conflicting_source_answers')
    return qs


def question_identity(q):
    """Do not merge different unavailable diagrams into a single question."""
    identity = normalized(q['stem']) + json.dumps(q.get('options', []), ensure_ascii=False, sort_keys=True)
    if q.get('has_missing_assets'):
        identity += json.dumps([q.get('provenance', {}).get('dataset'),
                                q.get('source_images') or q.get('provenance', {}).get('source_id')], sort_keys=True)
    return identity


def summarize(records):
    qs = list(records)
    return {'version': VERSION, 'questions': len(qs),
            'sources': dict(Counter(q['provenance']['dataset'] for q in qs)),
            'statuses': dict(Counter(q['status'] for q in qs)),
            'tiers': dict(Counter(q.get('quality', {}).get('tier', 'unprocessed') for q in qs)),
            'answer_checks': dict(Counter(q.get('quality', {}).get('answer_check', {}).get('status', 'unchecked') for q in qs)),
            'flags': dict(Counter(f for q in qs for f in q.get('quality', {}).get('flags', []))),
            'fine_types': len({a['label'] for q in qs for a in q.get('fine_type_annotations', [])}),
            'fine_type_annotated': sum(bool(q.get('fine_type_annotations')) for q in qs),
            'source_grade_known': sum(q.get('grade') is not None for q in qs),
            'difficulty_note': '来源等级与默认值尚未按真实学生正确率校准；未核验不表示答案正确。'}
