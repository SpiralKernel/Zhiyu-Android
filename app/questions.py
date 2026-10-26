"""原创的参数化数值题；用独立校验路径验证答案后才可发布。"""
import hashlib
import random
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from app.curriculum import NODE_MAP

TEMPLATE_VERSION = "1"


def parse_number(text: str) -> Fraction:
    """仅接收一个精确数值，不执行表达式或任意代码。"""
    text = unicodedata.normalize("NFKC", text).strip().replace("−", "-").replace("﹣", "-")
    if len(text) > 64 or not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*/\s*[+-]?\d+)?", text):
        raise ValueError("请输入一个数值，例如 -3、0.5 或 1/2；本题不需要填写单位或等号。")
    try:
        if "/" in text:
            a, b = text.split("/")
            return Fraction(Decimal(a.strip())) / Fraction(int(b.strip()))
        return Fraction(Decimal(text))
    except (ValueError, ZeroDivisionError, InvalidOperation, OverflowError) as exc:
        raise ValueError("数值格式无效，分母不能为零。") from exc


def validate_question(q: dict) -> bool:
    """独立数学不变量校验；不使用模型答案充当正确性证据。"""
    if q.get('provenance', {}).get('family') == 'foundations':
        from app.foundations import validate_foundation
        return validate_foundation(q)
    p, answer, k = q["parameters"], parse_number(q["answer"]), q["knowledge_id"]
    a, b, c = p["a"], p["b"], p["c"]
    checks = {
        "opposite": lambda: answer + a == 0,
        "absolute": lambda: answer >= 0 and answer * answer == a * a,
        "addition": lambda: answer + b == a,
        "multiply": lambda: answer / a == b,
        "power": lambda: answer + a * a == 0 if p["variant"] == 0 else answer == a * a,
        "substitution": lambda: answer - c == a * b,
        "like_terms": lambda: answer * 2 == a * 2 + b * 2,
        "brackets": lambda: answer + a * p["x"] == p["original_c"] + b,
        "linear": lambda: a * answer + b == c,
        "word_equation": lambda: a * answer + b == c and answer > 0,
        "segment": lambda: 2 * answer == c,
        "angle": lambda: answer + a == (90 if p["variant"] == 0 else 180),
    }
    return k in NODE_MAP and checks[k]() and 1 <= q["difficulty"] <= 3 and len(q["steps"]) >= 2


def make_question(knowledge_id: str, index: int) -> dict:
    digest = hashlib.sha256(f"{TEMPLATE_VERSION}:{knowledge_id}:{index}".encode()).digest()
    rng = random.Random(int.from_bytes(digest, "big"))
    a, b, c = rng.randint(2, 12), rng.randint(2, 9), rng.randint(2, 15)
    variant = index % 2
    errors = []
    if knowledge_id == "opposite":
        a = -a
        stem, answer = f"数轴上表示 {a} 的点，关于原点对称的点表示哪个数？", -a
        steps = ["关于原点对称的两个点表示互为相反数的两个数。", f"相反数之和为 0，所以答案是 {-a}。"]
        hint = "想一想：两个相反数相加等于多少？"
        errors = [(a, "opposite_unchanged", "保留了原数的符号；相反数需要改变符号。")]
    elif knowledge_id == "absolute":
        a = -a
        stem, answer = f"计算 |{a}|。", abs(a)
        steps = ["绝对值表示数轴上一个点到原点的距离。", f"距离不为负，|{a}| = {abs(a)}。"]
        hint = "到原点的距离可以是负数吗？"
        errors = [(a, "absolute_sign", "绝对值是距离，结果不能为负数。")]
    elif knowledge_id == "addition":
        a, b = -a, -b
        stem, answer = f"计算 {a} − ({b})。", a - b
        steps = [f"减去 {b}，等于加上它的相反数 {-b}。", f"{a} + {-b} = {answer}。"]
        hint = "先把减法改写成加上减数的相反数。"
        errors = [(a + b, "subtract_negative", "减去负数时，应先把它转化为加正数。")]
    elif knowledge_id == "multiply":
        a, b = -a, -b
        stem, answer = f"计算 ({a}) × ({b})。", a * b
        steps = ["两个负数相乘，积为正数。", f"将绝对值相乘：{-a} × {-b} = {answer}。"]
        hint = "先确定符号，再计算绝对值的乘积。"
        errors = [(-answer, "product_sign", "两个负数相乘时，积应为正数。")]
    elif knowledge_id == "power":
        stem = f"计算 −{a}²。" if variant == 0 else f"计算 (−{a})²。"
        answer = -(a * a) if variant == 0 else a * a
        steps = (["没有括号时，先算平方，再取相反数。", f"−({a} × {a}) = {answer}。"] if variant == 0 else
                 ["括号表明底数是一个负数，平方表示两个相同的底数相乘。", f"(−{a}) × (−{a}) = {answer}。"])
        hint = "看看负号是否在平方的括号里面。"
        errors = [(-answer, "power_brackets", "检查负号是否属于底数；括号会改变乘方的范围。")]
    elif knowledge_id == "substitution":
        b = -b
        stem, answer = f"当 x = {b} 时，求 {a}x + {c} 的值。", a * b + c
        steps = [f"将 x 替换成 ({b})：{a} × ({b}) + {c}。", f"先乘后加，得到 {answer}。"]
        hint = "代入负数时先加括号，再按照运算顺序计算。"
        errors = [(a * -b + c, "substitution_sign", "代入的是负数，乘法时需要保留它的负号。")]
    elif knowledge_id == "like_terms":
        stem, answer = f"合并 {a}x + {b}x，结果是 kx。求 k。", a + b
        steps = ["这两项字母及其指数相同，是同类项。", f"只把系数相加，k = {a} + {b} = {answer}。"]
        hint = "可以把 x 想成同一种物品，只把物品的个数相加。"
        errors = [(a * b, "coefficient_multiply", "合并同类项需要加减系数，这里不是相乘。")]
    elif knowledge_id == "brackets":
        answer = rng.randint(-6, 8)
        stem = f"将 {c} − ({a}x − {b}) 化简后，代入 x = {answer}，求值。"
        target = c - (a * answer - b)
        # 本题答案是代数式的值；验证路径通过原式代入。
        steps = [f"括号前是负号，每一项变号，得到 {c} − {a}x + {b}。", f"代入 x = {answer}，得到 {target}。"]
        hint = "括号前的负号，要作用到括号里的每一项。"
        errors = [(c - a * answer - b, "bracket_second_sign", "去括号时，第二项的负号也应改变。")]
        c_original, x_value = c, answer
        answer = target
    elif knowledge_id in {"linear", "word_equation"}:
        answer = rng.randint(1, 12)
        c = a * answer + b
        if knowledge_id == "linear":
            stem = f"解方程 {a}x + {b} = {c}，求 x。"
            steps = [f"等式两边同时减去 {b}，得到 {a}x = {c - b}。", f"两边同时除以 {a}，x = {answer}；代回原式成立。"]
            hint = "先让含 x 的项单独留在等式一边。"
            errors = [(Fraction(c + b, a), "transpose_sign", "去掉左边的常数项时，两边都应减去它。")]
        else:
            stem = f"一本练习本 {a} 元，另付一次配送费 {b} 元，一共花了 {c} 元。买了几本练习本？"
            steps = [f"设买了 x 本，根据总费用列方程：{a}x + {b} = {c}。", f"先减去配送费，再除以单价，x = ({c} − {b}) ÷ {a} = {answer}。"]
            hint = "总费用中，有哪一部分与本数无关？"
            errors = [(Fraction(c, a), "fixed_fee", "先从总费用中减去一次配送费，再计算本数。")]
    elif knowledge_id == "segment":
        c = 2 * a
        stem, answer = f"M 是线段 AB 的中点，AB = {c} cm，求 AM 的长度（只填数值）。", a
        steps = ["中点将线段分成长度相等的两部分。", f"AM = AB ÷ 2 = {c} ÷ 2 = {answer} cm。"]
        hint = "中点把整条线段分成几等份？"
        errors = [(c, "midpoint_half", "AM 是整条线段的一半。")]
    elif knowledge_id == "angle":
        a = rng.randint(15, 80)
        total, word = (90, "余角") if variant == 0 else (180, "补角")
        stem, answer = f"一个角是 {a}°，求它的{word}（只填数值）。", total - a
        steps = [f"互为{word}的两个角的和为 {total}°。", f"所求角 = {total}° − {a}° = {answer}°。"]
        hint = f"先回忆：两个角互为{word}时，它们的和是多少度？"
        errors = [((180 if variant == 0 else 90) - a, "complement_supplement", "余角的和是 90°，补角的和是 180°。")]
    else:
        raise ValueError("未知知识点")
    params = dict(a=a, b=b, c=c, variant=variant)
    if knowledge_id == "brackets":
        params.update(x=x_value, original_c=c_original)
    q = dict(id=f"{knowledge_id}-v{TEMPLATE_VERSION}-{index}", knowledge_id=knowledge_id,
             stem=stem, answer=str(answer), steps=steps, hint=hint, parameters=params,
             difficulty=2 if knowledge_id in {"brackets", "word_equation", "power"} else 1,
             question_type=knowledge_id, rubric={"max_score": 1, "criterion": "数值与标准答案精确等价；本版本不自动评分解题过程。"},
             common_errors=[dict(answer=str(value), code=code, feedback=feedback)
                            for value, code, feedback in errors if value != answer],
             provenance={"kind": "original_template", "template_version": TEMPLATE_VERSION,
                         "verification": "independent_math_invariant", "teacher_reviewed": False})
    if not validate_question(q):
        raise ValueError(f"题目数学校验失败：{q['id']}")
    return q


def grade(q: dict, value: str) -> dict:
    if q.get('provenance', {}).get('family') == 'foundations':
        from app.answers import equivalent
        correct = equivalent(q, value, q['answer'])
        feedback = {'expression':'请检查数量关系、括号以及固定费用；形式不同但恒等的一次式可以判对。',
                    'scientific':'检查数值、10的指数以及系数范围：系数的绝对值须大于等于1且小于10。',
                    'decimal':'检查四舍五入结果及小数位数；末尾0也表示精确程度。'}
        return dict(correct=correct, score=int(correct), max_score=1, answer=q['answer'],
                    steps=q['steps'], rubric=q['rubric'], error=None if correct else {
                        'code':'unclassified','feedback':feedback.get(q['answer_mode'],'答案还不正确，请对照条件和解析检查；单次错答不能确定具体错误原因。')})
    parsed = parse_number(value)
    correct = parsed == parse_number(q["answer"])
    error = None
    if not correct:
        error = next((e for e in q["common_errors"] if parse_number(e["answer"]) == parsed), None)
        error = error or {"code": "unclassified", "feedback": "答案还不正确。建议对照解析逐步检查；目前证据不足以确定具体错误原因。"}
    return dict(correct=correct, score=int(correct), max_score=1, answer=q["answer"],
                steps=q["steps"], error=error, rubric=q["rubric"])


def public_question(q: dict) -> dict:
    return {key: q[key] for key in ("id", "knowledge_id", "stem", "difficulty", "question_type", "provenance", "answer_mode", "diagram") if key in q}
