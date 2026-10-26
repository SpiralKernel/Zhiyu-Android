"""七年级挑战变式：使用分数精确计算，并通过不同等式路径核验。"""
import hashlib
import random
from fractions import Fraction as F

from app.questions import parse_number


def validate_challenge(q):
    p, y, k = q["parameters"], parse_number(q["answer"]), q["knowledge_id"]
    a,b,c,x = (p[key] for key in ("a","b","c","x"))
    checks = {
        "opposite": lambda: y+c+b==a,
        "absolute": lambda: y*(-a-c)==c-a,
        "addition": lambda: (y+F(c,a))*a*b == -a*a+b*b,
        "multiply": lambda: y*c == a*b,
        "power": lambda: y+c*c == -a*a+b*b*b,
        "substitution": lambda: y-c == a*x*x-b*x,
        "like_terms": lambda: y == a-b+2*c,
        "brackets": lambda: y+a*x == c+a*b,
        "linear": lambda: F(a*y-b,c)-y == parse_number(p["rhs"]),
        "word_equation": lambda: a*y+b*(y+c)==p["total"],
        "segment": lambda: y*2==a+b,
        "angle": lambda: y*(a+1)+b==180,
    }
    return q["difficulty"]==3 and checks[k]() and len(q["steps"])>=2


def make_challenge(knowledge_id,index):
    rng=random.Random(int.from_bytes(hashlib.sha256(f"challenge-v1:{knowledge_id}:{index}".encode()).digest(),"big"))
    a,b,c,x=rng.randint(3,9),rng.randint(2,8),rng.randint(2,7),rng.randint(-5,-1)
    p=dict(a=a,b=b,c=c,x=x)
    if knowledge_id=="opposite":
        stem=f"数轴上点 A 表示 −{a}。先把 A 向右平移 {b} 个单位得到 B，再将 B 关于原点对称得到 C。已知 D 在 C 左侧 {c} 个单位，D 表示哪个数？"
        answer=a-b-c
        steps=[f"B 表示 −{a}+{b}={b-a}。",f"C 表示 {a-b}；向左再减 {c}，D 表示 {answer}。"]
        hint="按移动、对称、再移动的顺序画出数轴，逐步跟踪符号。"
    elif knowledge_id=="absolute":
        stem=f"已知 |x|={a} 且 x<0，求 (x+{c})/(x−{c}) 的值。"
        answer=F(-a+c,-a-c)
        steps=[f"由 |x|={a} 且 x<0 得 x=−{a}。",f"代入原式并约分，得到 {answer}。"]
        hint="先用符号条件确定 x，再代入分式；分母不能为零。"
    elif knowledge_id=="addition":
        stem=f"计算 −{a}/{b} − (−{b}/{a}) − {c}/{a}。"
        answer=-F(a,b)+F(b,a)-F(c,a)
        steps=["先把减去负分数转为加正分数。",f"通分后合并分子并约分，结果为 {answer}。"]
        hint="先处理符号，再把所有分数通分。"
    elif knowledge_id=="multiply":
        stem=f"计算 (−{a}/{b}) ÷ (−{c}/{b*b})。"
        answer=F(a*b,c)
        steps=["两个负数相除，结果为正；除以一个非零数等于乘它的倒数。",f"约分后得到 {a*b}/{c}，结果为 {answer}。"]
        hint="除法先变乘倒数，再考虑约分。"
    elif knowledge_id=="power":
        stem=f"计算 −{a}² − (−{b})³ − {c}²。"
        answer=-a*a+b*b*b-c*c
        steps=[f"−{a}²=−{a*a}，(−{b})³=−{b*b*b}。",f"再计算加减，结果为 {answer}。"]
        hint="分别确认两个负号是否在底数的括号内，再算乘方。"
    elif knowledge_id=="substitution":
        stem=f"当 x={x} 时，求 {a}x²−{b}x+{c} 的值。"
        answer=a*x*x-b*x+c
        steps=[f"代入 x=({x})，先计算平方，x²={x*x}。",f"注意减去负的乘积，最终得到 {answer}。"]
        hint="平方的底数是整个 x；先平方，再乘法和加减。"
    elif knowledge_id=="like_terms":
        stem=f"整式 {a}x−{b}y−({b}x−{c}y)+{c}x+{c}(x−y) 化简后，x 的系数是多少？"
        answer=a-b+2*c
        steps=[f"展开括号后，仅收集含 x 的项：{a}x−{b}x+{c}x+{c}x。",f"合并系数，得到 {answer}。含 y 的项不能并入。"]
        hint="先去括号，然后把 x 项和 y 项分开。"
    elif knowledge_id=="brackets":
        stem=f"当 x={x} 时，求 {c}−[{a}x−{a}({b}−x)]+{a}x 的值。"
        answer=c+a*b-a*x
        steps=[f"中括号内先展开，原式化简为 {c}+{a*b}−{a}x。",f"代入 x={x}，结果为 {answer}。"]
        hint="从最内层括号开始，外层的负号作用到每一项。"
    elif knowledge_id=="linear":
        if a==c:a+=2;p["a"]=a
        answer=F(x,2)
        rhs=F(a*answer-b,c)-answer;p["rhs"]=str(rhs)
        stem=f"解方程 ({a}x−{b})/{c} − x = {rhs}，求 x。"
        steps=[f"两边同乘 {c} 后展开，得到 ({a}−{c})x−{b}={c}×({rhs})。",f"合并、移项并除以系数，x={answer}；代入原方程检验。"]
        hint="先去分母，但别漏乘等号两侧的每一项。"
    elif knowledge_id=="word_equation":
        answer=rng.randint(3,12);total=a*answer+b*(answer+c);p["total"]=total
        stem=f"甲本每本 {a} 元，乙本每本 {b} 元。买的乙本比甲本多 {c} 本，总共花 {total} 元。甲本买了几本？"
        steps=[f"设甲本买 x 本，乙本为 x+{c} 本，列方程 {a}x+{b}(x+{c})={total}。",f"展开并解方程得 x={answer}，再检查两种本数与总费用。"]
        hint="先用同一个未知数表示两种数量，再写总费用。"
    elif knowledge_id=="segment":
        stem=f"A、B、C 在同一直线上，顺序为 A—B—C，AB={a} cm，BC={b} cm。M 是 AB 的中点，N 是 BC 的中点。求 MN（只填数值）。"
        answer=F(a+b,2)
        steps=[f"沿直线，MN=MB+BN={a}/2+{b}/2。",f"所以 MN={answer} cm。"]
        hint="先按题给顺序标点，MN 可以分成哪两段？"
    elif knowledge_id=="angle":
        stem=f"两个角互补，较大的角是较小角的 {a} 倍再多 {b}°。求较小的角（只填数值）。"
        answer=F(180-b,a+1)
        steps=[f"设较小角为 x°，列方程 x+{a}x+{b}=180。",f"解得 x={answer}，检查两角的和为 180°。"]
        hint="互补给出角的和，倍数关系给出较大角的表达式。"
    else:raise ValueError("未知知识点")
    q=dict(id=f"challenge-{knowledge_id}-v1-{index}",knowledge_id=knowledge_id,stem=stem,answer=str(answer),
           steps=steps,hint=hint,parameters=p,difficulty=3,question_type="challenge:"+knowledge_id,
           common_errors=[],rubric={"max_score":1,"criterion":"精确数值等价；挑战题的解题过程暂不自动评分。"},
           provenance={"kind":"original_challenge_template","template_version":"1","verification":"independent_math_invariant","teacher_reviewed":False})
    if not validate_challenge(q):raise ValueError(f"挑战题校验失败：{q['id']}")
    return q
