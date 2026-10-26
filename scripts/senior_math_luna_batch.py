"""Build the manually read and independently checked sample for 2026-10-15.

The reviewed records below are intentionally explicit and bound to normalized
source fingerprints. Running this file never upgrades the unreviewed inventory.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.datasets import iter_dataset, source_manifest
from app.question_annotation import Annotation, source_fingerprint

BATCH = "senior-20261015-math-luna-01"
GOAL_BOOK_UNIT = {
    "sets_logic": ("math-senior-compulsory-1", 1), "inequalities": ("math-senior-compulsory-1", 1),
    "functions": ("math-senior-compulsory-1", 2), "exponential_logarithmic": ("math-senior-compulsory-1", 3),
    "trigonometry": ("math-senior-compulsory-2", 1), "plane_vectors": ("math-senior-compulsory-2", 2),
    "complex_numbers": ("math-senior-compulsory-2", 5), "solid_geometry": ("math-senior-compulsory-2", 6),
    "spatial_vectors": ("math-senior-selective-1", 3), "lines_circles": ("math-senior-selective-1", 1),
    "conics": ("math-senior-selective-1", 2), "statistics": ("math-senior-compulsory-1", 6),
    "probability": ("math-senior-compulsory-1", 7), "counting_binomial": ("math-senior-selective-1", 5),
    "sequences": ("math-senior-selective-2", 1), "derivatives": ("math-senior-selective-2", 2),
    "distributions_regression": ("math-senior-selective-1", 7),
}
GOAL_NUMBER = {
    "sets_logic": 1, "inequalities": 2, "functions": 2, "exponential_logarithmic": 1,
    "trigonometry": 2, "plane_vectors": 1, "complex_numbers": 1, "solid_geometry": 2,
    "spatial_vectors": 2, "lines_circles": 2, "conics": 2, "statistics": 2,
    "probability": 2, "counting_binomial": 1, "sequences": 2, "derivatives": 2,
    "distributions_regression": 1,
}

# Goal mappings are per-item where a broad topic spans multiple units. These
# are based on the demonstrated skill in each question, not merely source tags.
QUESTION_GOAL = {
    "bank:cmm:14505": "math-senior-compulsory-1:u1:g1",
    "bank:cmm:14996": "math-senior-compulsory-1:u1:g1",
    "bank:cmm:15358": "math-senior-compulsory-1:u1:g1",
    "bank:cmm:14290": "math-senior-compulsory-1:u2:g2",
    "bank:cmm:14294": "math-senior-compulsory-1:u2:g2",
    "bank:cmm:14405": "math-senior-compulsory-1:u3:g1",
    "bank:cmm:14384": "math-senior-compulsory-1:u3:g2",
    "bank:cmm:14403": "math-senior-compulsory-1:u3:g1",
    "bank:cmm:14441": "math-senior-compulsory-1:u5:g1",
    "bank:cmm:14459": "math-senior-compulsory-1:u5:g1",
    "bank:cmm:18679": "math-senior-compulsory-1:u4:g2",
    "bank:cmm:18704": "math-senior-compulsory-1:u4:g1",
    "bank:cmm:14583": "math-senior-compulsory-1:u4:g1",
    "bank:cmm:19269": "math-senior-compulsory-1:u4:g1",
    "bank:cmm:19699": "math-senior-compulsory-1:u4:g1",
    "bank:cmm:20491": "math-senior-compulsory-1:u4:g2",
    "bank:cmm:22029": "math-senior-selective-1:u6:g2",
    "bank:cmm:22030": "math-senior-selective-1:u6:g2",
    "bank:cmm:22166": "math-senior-selective-1:u6:g2",
    "bank:cmm:22168": "math-senior-selective-1:u6:g2",
    "bank:cmm:22169": "math-senior-selective-1:u6:g2",
    "bank:cmm:15375": "math-senior-compulsory-1:u5:g1",
    "bank:cmm:16530": "math-senior-compulsory-1:u6:g1",
    "bank:cmm:16532": "math-senior-compulsory-1:u6:g2",
    "bank:cmm:16791": "math-senior-compulsory-1:u7:g2",
    "bank:cmm:19028": "math-senior-compulsory-2:u1:g1",
    "bank:cmm:19131": "math-senior-compulsory-2:u1:g1",
    "bank:cmm:17705": "math-senior-compulsory-2:u2:g1",
    "bank:cmm:18362": "math-senior-compulsory-2:u2:g1",
    "bank:cmm:17703": "math-senior-compulsory-2:u2:g2",
    "bank:cmm:20533": "math-senior-compulsory-2:u5:g1",
    "bank:cmm:20532": "math-senior-compulsory-2:u5:g1",
    "bank:cmm:20557": "math-senior-compulsory-2:u5:g2",
    "bank:cmm:15417": "math-senior-compulsory-2:u6:g1",
    "bank:cmm:15442": "math-senior-compulsory-2:u6:g2",
    "bank:cmm:21316": "math-senior-selective-1:u3:g1",
    "bank:cmm:21318": "math-senior-selective-1:u3:g1",
    "bank:cmm:14352": "math-senior-compulsory-2:u3:g2",
    "bank:cmm:20162": "math-senior-selective-1:u4:g2",
    "bank:cmm:18257": "math-senior-compulsory-2:u4:g2",
    "bank:cmm:17495": "math-senior-compulsory-2:u4:g2",
    "bank:cmm:17560": "math-senior-compulsory-2:u4:g2",
    "bank:cmm:17481": "math-senior-compulsory-2:u4:g2",
    "bank:cmm:18202": "math-senior-compulsory-2:u4:g2",
    "bank:cmm:16465": "math-senior-selective-1:u1:g2",
    "bank:cmm:16707": "math-senior-selective-1:u1:g2",
    "bank:cmm:20305": "math-senior-selective-1:u2:g2",
    "bank:cmm:20292": "math-senior-selective-1:u2:g2",
    "bank:cmm:20068": "math-senior-selective-1:u2:g2",
    "bank:cmm:16682": "math-senior-selective-1:u5:g1",
    "bank:cmm:16977": "math-senior-selective-1:u5:g1",
    "bank:cmm:16753": "math-senior-selective-1:u7:g1",
    "bank:cmm:17067": "math-senior-selective-1:u7:g2",
    "bank:cmm:17068": "math-senior-selective-1:u7:g1",
    "bank:cmm:18524": "math-senior-selective-2:u1:g1",
    "bank:cmm:18521": "math-senior-selective-2:u1:g1",
    "bank:cmm:19402": "math-senior-selective-2:u1:g2",
    "bank:cmm:20119": "math-senior-selective-2:u2:g2",
    "bank:cmm:20192": "math-senior-selective-2:u2:g2",
    "bank:cmm:20114": "math-senior-selective-2:u2:g2",
    "bank:agieval-gaokao-mathqa:0": "math-senior-compulsory-1:u1:g1",
    "bank:agieval-gaokao-mathqa:2": "math-senior-compulsory-2:u2:g2",
    "bank:agieval-gaokao-mathqa:15": "math-senior-compulsory-2:u5:g2",
    "bank:agieval-gaokao-mathqa:16": "math-senior-compulsory-2:u2:g2",
    "bank:agieval-gaokao-mathqa:18": "math-senior-selective-1:u6:g1",
    "bank:agieval-gaokao-mathqa:29": "math-senior-selective-2:u1:g2",
    "bank:agieval-gaokao-mathqa:38": "math-senior-compulsory-2:u2:g2",
    "bank:agieval-gaokao-mathqa:51": "math-senior-compulsory-2:u5:g2",
    "bank:agieval-gaokao-mathqa:87": "math-senior-selective-1:u2:g2",
    "bank:agieval-gaokao-mathqa:104": "math-senior-selective-1:u5:g1",
    "bank:agieval-gaokao-mathqa:107": "math-senior-compulsory-2:u5:g2",
    "bank:agieval-gaokao-mathqa:161": "math-senior-selective-1:u5:g2",
    "bank:agieval-gaokao-mathqa:196": "math-senior-compulsory-2:u2:g2",
    "bank:agieval-gaokao-mathqa:19": "math-senior-selective-2:u2:g1",
    "bank:agieval-gaokao-mathqa:70": "math-senior-selective-1:u5:g1",
    "bank:agieval-gaokao-mathqa:76": "math-senior-compulsory-2:u6:g2",
    "bank:agieval-gaokao-mathqa:298": "math-senior-selective-1:u1:g2",
    "bank:agieval-gaokao-mathqa:303": "math-senior-selective-1:u2:g1",
    "bank:agieval-gaokao-mathqa:329": "math-senior-selective-1:u1:g2",
    "bank:agieval-gaokao-mathqa:340": "math-senior-selective-1:u6:g2",
    "bank:agieval-gaokao-mathqa:346": "math-senior-compulsory-1:u7:g2",
    "bank:agieval-gaokao-mathqa:348": "math-senior-selective-1:u2:g2",
    "bank:cmm:21303": "math-senior-selective-1:u3:g1",
    "bank:cmm:21317": "math-senior-selective-1:u3:g2",
    "bank:cmm:21321": "math-senior-selective-1:u3:g2",
    "bank:cmm:21322": "math-senior-selective-1:u3:g2",
    "bank:cmm:21002": "math-senior-selective-1:u3:g1",
    "bank:cmm:21003": "math-senior-selective-1:u3:g1",
    "bank:cmm:21004": "math-senior-selective-1:u3:g2",
    "bank:cmm:21005": "math-senior-selective-1:u3:g1",
    "bank:cmm:21282": "math-senior-selective-1:u3:g1",
    "bank:cmm:20250": "math-senior-compulsory-1:u2:g2",
    "bank:cmm:16561": "math-senior-compulsory-1:u6:g1",
    "bank:cmm:22330": "math-senior-compulsory-1:u6:g2",
    "bank:cmm:17239": "math-senior-compulsory-1:u6:g2",
    "bank:cmm:17062": "math-senior-compulsory-1:u6:g1",
    "bank:cmm:22344": "math-senior-compulsory-1:u7:g2",
    "bank:cmm:14860": "math-senior-compulsory-1:u2:g2",
    "bank:cmm:15025": "math-senior-compulsory-1:u2:g2",
    "bank:cmm:14553": "math-senior-compulsory-1:u4:g2",
    "bank:cmm:14734": "math-senior-compulsory-1:u3:g2",
    "bank:cmm:14446": "math-senior-compulsory-1:u5:g1",
    "bank:cmm:17421": "math-senior-compulsory-2:u1:g1",
    "bank:cmm:17450": "math-senior-compulsory-2:u1:g2",
    "bank:cmm:18104": "math-senior-compulsory-2:u1:g2",
    "bank:cmm:18489": "math-senior-compulsory-2:u3:g2",
    "bank:cmm:19491": "math-senior-compulsory-1:u5:g2",
    "bank:cmm:18614": "math-senior-selective-1:u4:g2",
    "bank:agieval-gaokao-mathqa:46": "math-senior-selective-1:u4:g2",
    "bank:cmm:18499": "math-senior-compulsory-2:u3:g2",
    "bank:cmm:18926": "math-senior-compulsory-2:u3:g2",
    "bank:cmm:18493": "math-senior-compulsory-2:u3:g2",
    "bank:cmm:14845": "math-senior-selective-1:u4:g2",
    "bank:cmm:20163": "math-senior-selective-1:u4:g2",
}


def crit(cid, desc, evidence):
    return {"id": cid, "description": desc, "points": None, "evidence_required": evidence}


def error(desc, tags, types):
    return {"description": desc, "knowledge_tags": tags, "type_tags": types}


def has_control(value):
    import re
    if isinstance(value, str):
        return bool(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value))
    if isinstance(value, dict):
        return any(has_control(v) for v in value.values())
    if isinstance(value, list):
        return any(has_control(v) for v in value)
    return False


def part(pid, prompt, answer, steps, tags, types, rubric, errors=None, deps=None):
    return {"id": pid, "prompt": prompt, "reference_answer": answer,
            "solution_steps": steps, "knowledge_tags": tags, "type_tags": types,
            "depends_on": deps or [], "points": None, "rubric": rubric,
            "common_errors": errors or []}


def ann(fmt, tags, fine, level, basis, answer_mode, parts, accepted=None, equivalence="manual"):
    value = {
        "schema_version": 1, "response_format": fmt,
        "knowledge": {"primary": tags, "supporting": [], "prerequisites": []},
        "fine_types": fine,
        "difficulty": {"level": level, "basis": basis, "origin": "luna", "calibrated": False},
        "curriculum": {"grade": None, "term": None, "goal_ids": [], "scope_status": "unknown", "basis": "未按题源资料推定年级、学期或册次；待正式教材映射后审核。"},
        "answer_spec": {"mode": answer_mode, "accepted_answers": accepted or [], "equivalence": equivalence,
                        "constraints": [], "unit": None, "tolerance": None},
        "parts": parts,
        "grading": {"mode": "ai_rubric", "full_score": None, "allow_alternative_methods": True,
                    "uncertainty_policy": "review_required"},
        "review": {"status": "candidate", "answer_status": "checked", "issues": [],
                   "method": "item_read", "notes": "逐题阅读题干和来源答案/解析，并独立推导复算；仍属候选标注，未作教师审核认证。"},
        "origin": {"model": "gpt-6-luna", "batch_id": BATCH},
    }
    Annotation.model_validate(value)
    return value


def reviewed(topic, tags, fine, level, basis, response_format, mode, prompts, answers,
             steps, criteria, independent, rationale, errors=None):
    """Compact authoring helper; the supplied reasoning and rubric stay item-specific."""
    parts = []
    for i, (prompt, answer, sol, rubric) in enumerate(zip(prompts, answers, steps, criteria), 1):
        parts.append(part(f"p{i}", prompt, answer, sol, tags, fine,
                          [crit(f"p{i}c{j}", desc, evidence) for j, (desc, evidence) in enumerate(rubric, 1)],
                          errors or []))
    value = ann(response_format, tags, fine, level, basis, mode, parts,
                accepted=answers if mode == "numeric" else None, equivalence="semantic")
    book, unit = GOAL_BOOK_UNIT[topic]
    # Curriculum IDs follow the catalog's normalized book:uN:gM form.
    goal = f"{book}:u{unit}:g{GOAL_NUMBER[topic]}"
    value["curriculum"] = {"grade": None, "term": None, "book_id": book, "goal_ids": [goal],
        "scope_status": "candidate", "basis": "与北师大版高中数学册内主题按题目所测知识点对齐；册内课程目标为宽口径候选，尚待教材目录代理最终核对。"}
    Annotation.model_validate(value)
    return {"topic": topic, "decision": "passed", "rationale": rationale,
            "independent_solution": independent, "annotation": value}


ITEMS = {
    "bank:cmm:14505": {
        "topic": "sets_logic", "decision": "passed",
        "rationale": "五个小问题干完整；逐项核对集合元素、数集/有序数对、偶数集等价、三角形包含关系和实数区间包含。来源解析与独立结果一致。",
        "independent_solution": "(1) 按来源采用的自然数约定，B={1}，故B为A的真子集。(2) A是实数集合，B是有序数对集合，不存在题目所定义的同类元素包含关系。(3) n遍历整数时2(n-1)也遍历全部整数，故两集合均为偶数集。(4) 等边三角形是三角形的真子类。(5) A=(-1,4)，B=(-∞,5)，故A真包含于B。",
        "annotation": ann("composite", ["集合的表示与集合间关系"], ["判断有限集、数集与点集的包含关系", "化简整数参数表示的集合并判断相等", "判断几何对象集合与区间集合的真包含"], 1,
          "逐小问使用元素定义、整数变量代换和区间包含即可完成；步骤短且无参数讨论。", "multipart", [
            part("p1", "判断(1) A与B的关系。", "B⊊A", ["由x∈N且x²=1得B={1}。", "A={-1,1}，故B⊊A。"], ["集合的表示与集合间关系"], ["由元素定义判断有限集包含"], [crit("p1c1", "确定B的元素为{1}", "从x²=1和自然数条件推出x=1"), crit("p1c2", "判定真子集", "说明{1}是{-1,1}的真子集")]),
            part("p2", "判断(2) A与B的关系。", "A与B无包含关系", ["A的元素是数；B的元素是有序数对。", "B中元素不属于A，A中元素也不属于B，故无包含关系。"], ["集合的表示与集合间关系"], ["辨析数集和点集元素"], [crit("p2c1", "辨析两集合的元素类型", "指出A中是数、B中是有序数对"), crit("p2c2", "给出包含关系结论", "说明双方均不包含")]),
            part("p3", "判断(3) P与Q的关系。", "P=Q", ["令m=n-1；n遍历Z时m也遍历Z。", "P和Q都表示所有偶数，故相等。"], ["集合的表示与集合间关系"], ["化简整数参数集合"], [crit("p3c1", "证明整数参数取值集合相同", "指出n↦n−1是Z到Z的双射"), crit("p3c2", "得出集合相等", "指出两者均为偶数集合")]),
            part("p4", "判断(4) A与B的关系。", "A⊊B", ["每个等边三角形都是三角形。", "存在非等边三角形，故包含关系为真包含。"], ["集合的表示与集合间关系"], ["依据几何分类判断真子集"], [crit("p4c1", "验证包含", "说明等边三角形属于三角形"), crit("p4c2", "验证真包含", "指出存在非等边三角形")]),
            part("p5", "判断(5) A与B的关系。", "A⊊B", ["B={x|x<5}=(-∞,5)，A=(-1,4)。", "A中每个数小于5，且如0属于B但不属于A，故A⊊B。"], ["集合的表示与集合间关系", "区间表示"], ["解一元一次不等式并比较区间"], [crit("p5c1", "化简B", "得到B=(-∞,5)"), crit("p5c2", "证明真包含", "验证A⊂B并举出B中不属于A的元素")]),
          ], equivalence="semantic"),
    },
    "bank:cmm:17705": {
        "topic": "plane_vectors", "decision": "passed",
        "rationale": "二维向量坐标运算与平行单位向量均可直接复算；题干、选项和图像状态完整，来源解析一致。",
        "independent_solution": "a+b=(2,1)，3a−2b=(1,−2)。4a−b=(3,−1)，其模为√10，故同方向和反方向单位向量分别为(3/√10,−1/√10)与(−3/√10,1/√10)。",
        "annotation": ann("composite", ["平面向量坐标运算", "向量的模与单位向量", "向量平行"], ["按坐标进行向量线性运算", "求给定非零向量的两个平行单位向量"], 1,
          "只涉及坐标分量线性运算、欧氏模和归一化；没有参数或多步证明。", "multipart", [
            part("p1", "求 a+b 与 3a−2b 的坐标。", "a+b=(2,1)，3a−2b=(1,−2)", ["逐分量相加：(1+1,0+1)=(2,1)。", "逐分量计算：(3−2,0−2)=(1,−2)。"], ["平面向量坐标运算"], ["向量坐标加减与数乘"], [crit("p1c1", "正确计算a+b", "得到坐标(2,1)"), crit("p1c2", "正确计算3a−2b", "得到坐标(1,−2)")]),
            part("p2", "求与4a−b平行的单位向量坐标。", "(3/√10,−1/√10)或(−3/√10,1/√10)", ["4a−b=(3,−1)，模为√(3²+(-1)²)=√10。", "沿该向量方向归一化，得(3/√10,−1/√10)；反向量也平行且为单位向量，故取相反数。"], ["平面向量坐标运算", "向量的模与单位向量", "向量平行"], ["由向量坐标求同向及反向单位向量"], [crit("p2c1", "求方向向量及其模", "得到(3,−1)和√10"), crit("p2c2", "归一化并考虑两种方向", "给出两个相反的单位向量")], [error("漏掉反方向的平行单位向量", ["向量平行", "单位向量"], ["列举平行单位向量"])]),
          ], equivalence="symbolic"),
    },
    "bank:cmm:18524": {
        "topic": "sequences", "decision": "passed",
        "rationale": "递推式取倒数后可等价变形为常差关系，首项和第11项结论均已独立验证，来源步骤一致。",
        "independent_solution": "令b_n=1/a_n。递推两边变形得(1−2a_n)/a_n=(2a_{n−1}+1)/a_{n−1}，即b_n−2=b_{n−1}+2，故b_n−b_{n−1}=4。b_1=5，所以b_n=4n+1，a_n=1/(4n+1)。a_1a_2=1/45=a_11，故是第11项。",
        "annotation": ann("composite", ["数列递推关系", "等差数列通项", "数列项的判定"], ["倒数换元将分式递推转化为等差数列", "利用通项判定给定数是否为数列项"], 2,
          "需识别倒数变量、正确变形递推式，并连续完成通项与项序判断；关键代数步骤多于基础计算。", "multipart", [
            part("p1", "证明{b_n}为等差数列。", "b_n=4n+1（n≥1），故为首项5、公差4的等差数列。", ["将给定等式两边除以a_na_{n−1}，得到1/a_n−2=1/a_{n−1}+2。", "于是b_n−b_{n−1}=4，且b_1=5。"], ["数列递推关系", "等差数列"], ["倒数换元与常差递推"], [crit("p1c1", "正确换元与变形", "推出b_n−b_{n−1}=4"), crit("p1c2", "确认等差数列", "给出首项5和公差4")]),
            part("p2", "判断a_1a_2是否为{a_n}中的项；若是，指出项数。", "是第11项。", ["由b_n=4n+1得a_n=1/(4n+1)。", "a_1a_2=(1/5)(1/9)=1/45；解1/(4n+1)=1/45得n=11，为正整数。"], ["等差数列通项", "数列项的判定"], ["由通项反求项序"], [crit("p2c1", "求出数列通项及乘积", "得到a_n=1/(4n+1)和a_1a_2=1/45"), crit("p2c2", "解项序并验证定义域", "得n=11∈N*")], [error("求出形式解后未检查n是否为正整数", ["数列项的判定"], ["由通项反求项序"])], ["p1"]),
          ], equivalence="semantic"),
    },
    "bank:cmm:20533": {
        "topic": "complex_numbers", "decision": "passed",
        "rationale": "按复数实部、虚部和复平面坐标逐问复算；纯虚数条件中的虚部非零要求已明确处理，来源答案一致。",
        "independent_solution": "z的实部为a²−4，虚部为a+2。(1)纯虚数要求a²−4=0且a+2≠0，解得a=2。(2)点坐标为(a²−4,a+2)，代入x+2y+1=0得a²+2a+1=0，故a=−1。",
        "annotation": ann("composite", ["复数的实部与虚部", "复数的几何意义"], ["依据纯虚数条件求参数并排除零复数", "将复数对应点代入直线方程求参数"], 1,
          "只需识别实部与虚部、应用纯虚数定义，并解一元二次方程；两问相互独立。", "multipart", [
            part("p1", "若z为纯虚数，求a。", "a=2", ["纯虚数要求实部为0且虚部不为0。", "a²−4=0给出a=±2；a+2≠0排除a=−2，故a=2。"], ["复数的实部与虚部"], ["由纯虚数条件确定实参数"], [crit("p1c1", "令实部为零", "得到a²−4=0"), crit("p1c2", "检查虚部非零", "排除a=−2并保留a=2")]),
            part("p2", "若z对应点在直线x+2y+1=0上，求a。", "a=−1", ["复数z对应点为(a²−4,a+2)。", "代入直线得a²−4+2(a+2)+1=0，即(a+1)²=0，故a=−1。"], ["复数的几何意义", "一元二次方程"], ["复平面坐标与直线条件"], [crit("p2c1", "确定复平面点坐标", "实部为横坐标、虚部为纵坐标"), crit("p2c2", "代入直线并求解", "得到唯一解a=−1")]),
          ], equivalence="numeric", accepted=["2", "-1"]),
    },
    "bank:cmm:14290": {
        "topic": "functions", "decision": "passed",
        "rationale": "用定义法独立验证(1)在开区间上的严格单调性，再据此求闭区间端点最值；来源解析与结论一致。",
        "independent_solution": "取1<x_1<x_2，则f(x_2)−f(x_1)=(x_2−x_1)(1−1/(x_1x_2))>0，故f递增。在[2,4]上仍递增，最小值f(2)=5/2，最大值f(4)=17/4。",
        "annotation": ann("composite", ["函数单调性", "函数在闭区间上的最值"], ["用定义法证明有理函数在区间上单调递增", "利用单调性求闭区间最值"], 2,
          "需要组织双变量差值并判断符号，再将开区间结论用于闭区间端点；论证链条清楚但含证明。", "multipart", [
            part("p1", "证明f(x)=x+1/x在(1,+∞)上递增。", "对任意1<x_1<x_2，有f(x_2)−f(x_1)=(x_2−x_1)(x_1x_2−1)/(x_1x_2)>0。", ["任取1<x_1<x_2。", "化简差值；x_2−x_1>0、x_1x_2−1>0、x_1x_2>0，故差值为正。"], ["函数单调性"], ["用定义法证明函数单调性"], [crit("p1c1", "建立定义法差值", "正确化简f(x_2)−f(x_1)"), crit("p1c2", "判断各因式符号", "利用1<x_1<x_2推出差值严格为正")]),
            part("p2", "求f在[2,4]上的最值。", "最小值5/2，最大值17/4。", ["[2,4]包含于(1,+∞)，故f在[2,4]递增。", "最小值f(2)=5/2，最大值f(4)=17/4。"], ["函数单调性", "函数在闭区间上的最值"], ["利用单调性比较区间端点函数值"], [crit("p2c1", "将单调区间结论用于[2,4]", "确认该区间上递增"), crit("p2c2", "计算端点值", "正确给出两端函数值和最值")], deps=["p1"]),
          ], equivalence="semantic"),
    },
    "bank:cmm:14405": {
        "topic": "exponential_logarithmic", "decision": "passed",
        "rationale": "逐项核对三个有理指数式；使用正底数幂、负指数和绝对值平方根规则复算，三项均与来源答案相符。",
        "independent_solution": "(1) 1+1/4·(9/4)^(-1/2)−1/10=1+1/6−1/10=16/15。(2) 5/3+100+9/16−3+37/48=100。(3) 0.064=0.4³，首项=5/2；(-7/8)^0=1；[(-2)^3]^(-4/3)=1/16；16^(-3/4)=1/8；|-0.01|^(1/2)=1/10，合计143/80。",
        "annotation": ann("calculation", ["实数指数幂的运算性质", "负整数指数幂与零指数幂", "分数指数幂"], ["混合运算中使用零指数、负指数和分数指数规则", "化为有理数后精确计算"], 1,
          "三小题主要考查幂运算规则与分数化简，均为直接计算；无参数或复杂推理。", "multipart", [
            part("p1", "计算第(1)式。", "16/15", ["混合数化为分数；零次幂为1。", "(9/4)^(-1/2)=2/3，故结果1+1/6−1/10=16/15。"], ["实数指数幂的运算性质"], ["零指数、负指数及分数指数混合运算"], [crit("p1c1", "正确处理各幂", "零次幂为1且负分数指数转为倒数平方根"), crit("p1c2", "完成有理数运算", "得到16/15")]),
            part("p2", "计算第(2)式。", "100", ["(25/9)^(1/2)=5/3，(64/27)^(-2/3)=9/16，0.1^(-2)=100，π^0=1。", "5/3+100+9/16−3+37/48=100。"], ["实数指数幂的运算性质"], ["分数指数幂与零次幂混合运算"], [crit("p2c1", "正确计算幂项", "得到5/3、9/16、100、1"), crit("p2c2", "正确合并有理数", "得到100")]),
            part("p3", "计算第(3)式。", "143/80", ["各项依次化为5/2、1、1/16、1/8、1/10。", "按原式符号计算：5/2−1+1/16+1/8+1/10=143/80。"], ["实数指数幂的运算性质", "绝对值"], ["负底数整数幂、复合分数指数与绝对值幂"], [crit("p3c1", "正确处理幂及绝对值项", "得到各项的正确数值"), crit("p3c2", "正确处理符号并求和", "得到143/80")], [error("把括号内负底数的偶次幂结果处理为负数", ["实数指数幂的运算性质"], ["负底数整数幂"]) ]),
          ], equivalence="numeric", accepted=["16/15", "100", "143/80"]),
    },
}

# Additional hand-read records. The answer steps and evidence criteria here were
# authored from the individual source question, not copied from screening rules.
ITEMS.update({
    "bank:cmm:20642": reviewed("inequalities", ["基本不等式", "代数不等式证明"], ["利用a+1/a的下界证明根式不等式", "平方前验证两边非负"], 2,
      "需先把两端写成t=a+1/a的函数并证明可平方，再用t≥2；等号条件可核验。", "proof", "proof",
      ["已知a>0，证明√(a²+1/a²)−√2 ≥ a+1/a−2。"],
      ["命题成立；等号当且仅当a=1。"],
      [["令t=a+1/a≥2。则a²+1/a²=t²−2。", "右端移项后要证√(t²−2)≥t−2+√2；右侧非负，因为t≥2。", "两边平方后差为(t²−2)−(t−2+√2)²=2(2−√2)(t−2)≥0。等号t=2，即a=1。"]],
      [[("建立代换并给出范围", "指出t=a+1/a且t≥2"), ("说明平方等价安全", "证明待比较右侧非负"), ("完成不等式并检查等号", "平方差化为非负量并给出a=1")]],
      "令t=a+1/a，根号内化为t²−2。t−2+√2≥√2−0? t≥2，故右端至少√2>0，可平方。平方差为2(2−√2)(t−2)≥0。等号需t=2，由a+1/a≥2取等条件a=1。",
      "逐项核对定义域、平方等价条件、平方差和等号条件；来源仅给结论提示，已独立完成证明。"),
    "bank:cmm:20757": reviewed("inequalities", ["不等式证明", "分析法"], ["将分式不等式等价转化为正因数交叉相乘", "补全分析法证明链"], 1,
      "只有正数条件下交叉相乘并化简，关键等价链仅一层。", "proof", "proof",
      ["a、b、m为正数且a<b，用分析法证明(a+m)/(b+m)>a/b，并补全中间不等式。"],
      ["bm>am。"],
      [["因b+m与b均为正数，原不等式等价于b(a+m)>a(b+m)。", "展开并消去ab，得到bm>am。", "m>0且b>a，故bm>am，原不等式成立。"]],
      [[("给出正因数条件", "指出b+m>0、b>0"), ("等价变形", "交叉相乘并化简到bm>am"), ("利用题设完成证明", "由m>0、b>a推出bm>am")]],
      "因b+m>0且b>0，可交叉相乘：b(a+m)>a(b+m)等价于ab+bm>ab+am，等价于m(b−a)>0，题设保证成立。",
      "题干中的空格为待补的完整不等式bm>am，来源答案和独立展开一致。"),
    "bank:cmm:14367": reviewed("inequalities", ["幂函数性质", "分数指数不等式"], ["由幂函数奇偶性和单调性确定参数", "在底数符号分区内解负指数不等式"], 3,
      "需要先由两个全局图像性质确定离散参数，再按两个底数正负分区解不等式并处理底数为零。", "calculation", "text",
      ["已知幂函数y=x^(3m−9)，m为正整数，其图象关于y轴对称且在(0,+∞)递减。求满足(a+1)^(−m/3)<(3−2a)^(−m/3)的a范围。"],
      ["a<−1 或 2/3<a<3/2。"],
      [["在正半轴递减要求指数3m−9<0；关于y轴对称要求指数为偶整数。正整数m<3且3m−9为偶数，故m=1。", "不等式两边底数均须非零，函数t↦t^(−1/3)在各自区间(−∞,0)、(0,+∞)递减。两底数均正时需a+1>3−2a>0，得到2/3<a<3/2；两底数均负时所需a+1>3−2a与a+1<0矛盾，无解；异号时仅可能a+1<0<3−2a，此时左边为负、右边为正，不等式恒成立，得a<−1。", "合并得a<−1或2/3<a<3/2；底数为零的a=−1、3/2不在定义域。"]],
      [[("确定m", "利用指数为负及偶整数同时得到m=1"), ("处理底数分区和单调方向", "穷尽底数正负并正确反向比较"), ("合并范围并排除无定义值", "最终范围与原式定义域相容")]],
      "m<3给m=1或2；指数3m−9需偶数，故m=1。函数t^-1/3在正、负半轴均递减，但跨过0不可直接比较。两底数均正时要a+1>3−2a且3−2a>0，得到(2/3,3/2)；两底数均负时要求a>2/3且a<−1，矛盾；异号且左底数负时不等式恒成立，条件给a<−1。",
      "该题答案经独立分区复算与来源范围相同；精确标出底数非零是必要的定义域条件。"),
    "bank:cmm:19028": reviewed("trigonometry", ["正弦定理与余弦定理", "三角恒等变换"], ["由余弦定理求角", "和角公式结合角范围求三角表达式最大值"], 2,
      "先由边长关系唯一确定B，再将目标化为单一角的正弦并结合开区间端点范围求最大值。", "composite", "multipart",
      ["已知△ABC满足a²+c²−ac=b²。(I)求B；(II)求cosA+cosC的最大值。", "同上第(II)问。"],
      ["B=π/3。", "最大值为1。"],
      [["由余弦定理，cosB=(a²+c²−b²)/(2ac)=1/2。B为三角形内角，故B=π/3。"], ["A+C=2π/3。cosA+cosC=2cos((A+C)/2)cos((A−C)/2)=cos((A−C)/2)≤1。A=C=π/3可取到1。"]],
      [[("正确使用余弦定理", "得到cosB=1/2"), ("确定内角", "取B=π/3而非其他同余角")], [("利用角和关系化简", "给出A+C=2π/3并化为余弦表达式"), ("证明上界可取", "证明不超过1且在A=C时取等")]],
      "余弦定理直接给cosB=1/2，故内角B=π/3。第二问用和差化积：cosA+cosC=2cos((A+C)/2)cos((A−C)/2)=cos((A−C)/2)≤1。取A=C=π/3时达到1。",
      "题干与来源解析完整；独立解法给出最大值可达性。"),
    "bank:cmm:19131": reviewed("trigonometry", ["正弦定理", "余弦定理", "三角形面积"], ["由边角关系求三角函数值", "SSS条件下用余弦定理求边并求面积"], 2,
      "两问依次使用正弦定理、余弦定理和面积公式，并需排除负边根。", "composite", "multipart",
      ["△ABC中A=60°，c=3a/7。(I)求sin C。", "若a=7，求△ABC面积。"],
      ["sin C=3√3/14。", "面积为6√3。"],
      [["由正弦定理sin C/c=sin A/a，代入c/a=3/7、sinA=√3/2。"], ["c=3。余弦定理a²=b²+c²−2bc cosA，得49=b²−3b+9，正根b=8。面积=bc sinA/2=6√3。"]],
      [[("应用正弦定理", "正确写出sinC/c=sinA/a"), ("代入并化简", "得到3√3/14")], [("正确求第三边", "由余弦定理得b=8并排除负根"), ("套用面积公式", "得到6√3")]],
      "sinC=(c/a)sinA=(3/7)(√3/2)=3√3/14。a=7时c=3，余弦定理b²−3b−40=0，正边长b=8，故面积为(1/2)·8·3·sin60°=6√3。",
      "两个小问均已独立计算；来源解答中二次方程的负根已明确排除。"),
    "bank:cmm:15417": reviewed("solid_geometry", ["空间点与平面"], ["根据四点共面性分类计数确定平面"], 1,
      "依据前三点定平面并按第四点共面或异面分类；只需完整枚举两种情况。", "short_answer", "text",
      ["空间四点中无任何三点共线时，可以确定几个平面？"], ["1个或4个。"],
      [["任取三点确定一个平面。若第四点在该平面内，四点共面，仅有一个平面；若第四点不在该平面内，每三个点分别确定一个平面，共有四个不同平面。"]],
      [[("分类讨论", "区分四点共面与不共面"), ("计数", "分别得到1个和4个平面")]],
      "不存在三点共线保证任意三点唯一确定平面。四点共面时所有三点组给出同一平面；不共面时四个三点组各给出不同平面。",
      "来源答案为1或4；两种情况均按点面位置独立枚举。"),
    "bank:cmm:15442": reviewed("solid_geometry", ["空间中平面的位置关系"], ["利用公共点与不重合判定两平面相交"], 1,
      "A给出公共点，B不在α证明所定平面不等于α；无需复杂空间构造。", "short_answer", "text",
      ["若A∈α、B∉α、C∉α，平面ABC与平面α的位置关系是什么？"], ["相交。"],
      [["A属于两平面，故两平面有公共点；B不属于α，所以平面ABC不等于α。两个不同平面有公共点时相交。"]],
      [[("确认公共点", "指出A同时属于α与平面ABC"), ("排除两平面重合", "由B∉α推出平面ABC≠α"), ("判定位置关系", "由两不同平面有公共点得相交")]],
      "A为公共点。若平面ABC等于α则B∈α，与已知矛盾，所以两平面不同且相交。",
      "题干所称平面ABC隐含A、B、C不共线；按其成立条件直接判定，来源结论相符。"),
    "bank:cmm:16465": reviewed("lines_circles", ["圆的标准方程", "圆心到直线的距离", "弦长"], ["结合圆与坐标轴相切条件设圆心参数", "使用弦心距和半弦长关系求圆方程"], 2,
      "需要设圆心参数、应用点到直线距离及勾股关系，并保留参数正负产生的两个圆。", "calculation", "multipart",
      ["圆C与y轴相切，圆心在x−3y=0上，直线y=x截得弦长2√7，求圆C方程。"],
      ["(x−3)²+(y−1)²=9，或(x+3)²+(y+1)²=9。"],
      [["设圆心(3m,m)，半径r=3|m|。圆心到y=x距离为|2m|/√2=√2|m|。", "弦长2√7，半弦长√7；由r²=(弦心距)²+7，得9m²=2m²+7，故m=±1。", "分别代入圆心与半径，得到两圆方程。"]],
      [[("设定圆心与半径", "由圆心在线上且与y轴相切得到(3m,m)、r=3|m|"), ("使用弦长关系解参", "得到9m²=2m²+7及m=±1"), ("写出全部圆方程", "给出m=1和m=−1两种结果")]],
      "圆心(3m,m)，半径3|m|；到y=x距离|m−3m|/√2=√2|m|。半弦长√7，因此9m²=2m²+7，m²=1，得到圆心(3,1)或(−3,−1)，半径3。",
      "来源解答和独立几何关系核算一致；保留两个参数符号对应的圆。"),
    "bank:cmm:16707": reviewed("lines_circles", ["圆的方程", "点到直线的距离", "圆的几何性质"], ["求圆心到直线距离", "按圆周弧长比例求点到直线距离小于定值的概率"], 2,
      "两问分别用点线距离公式及圆半径确定距离范围；涉及圆上均匀选点时须说明测度模型。", "composite", "multipart",
      ["圆C:x²+y²=12，直线4x+3y=25。(1)求圆心到直线的距离。", "圆C上均匀取一点P，求|P−(4,3)|<1的概率。"],
      ["(1)5。", "(2)1/6。"],
      [["圆心O=(0,0)，到直线4x+3y−25=0距离25/5=5。"], ["令u=(4x+3y)/5，为圆上点到原点的法向投影坐标，圆上均匀点的极角θ均匀分布，u=R cosθ，R=2√3。点到直线距离为|u−5|。因u∈[−2√3,2√3]且5−2√3<2，条件|u−5|<2等价于u>3。故cosθ>3/(2√3)=√3/2。", "该角范围总长为π/3；圆周总角度2π，概率=(π/3)/(2π)=1/6。"]],
      [[("使用点线距离公式", "得到圆心到直线距离5")], [("转化为圆上角度条件", "写出|Rcosθ−5|<2并化为cosθ>√3/2"), ("按弧长比例求概率", "角度总长π/3除以2π得到1/6")]],
      "圆上点的极角均匀分布。法向单位向量投影u=2√3cosθ，点线距离|u−5|<2。u≤2√3<5，故只需u>3，即cosθ>√3/2，对应圆周角长π/3，概率1/6。",
      "逐项复核了点线距离表达式、事件所在圆弧和圆周均匀模型，来源1/6与独立结果一致。", errors=None),
    "bank:cmm:20305": reviewed("conics", ["抛物线的定义与标准方程", "抛物线焦点与准线"], ["用抛物线定义由焦点距离反求参数", "由方程求点坐标"], 1,
      "题目给出横坐标与焦点距离，可用抛物线定义唯一求参数，再代入方程求对称的两个纵坐标。", "composite", "multipart",
      ["抛物线y²=−2px (p>0)上M的横坐标为−9，且MF=10，求抛物线方程。", "求点M坐标。"],
      ["y²=−4x。", "M=(−9,6)或(−9,−6)。"],
      [["焦点为(−p/2,0)，准线为x=p/2。抛物线上点到焦点等于到准线距离，故p/2+9=10，得p=2。"], ["代入y²=−4x及x=−9，得y²=36，所以y=±6。"]],
      [[("使用焦点准线定义", "写出到准线距离p/2+9=10"), ("求出标准方程", "得p=2及y²=−4x")], [("代入已知横坐标", "得到y²=36"), ("给出全部坐标", "包含y=±6两点")]],
      "抛物线方程y²=−2px的焦点、准线分别为(−p/2,0)、x=p/2。横坐标−9的点到准线距离为9+p/2，应等于焦点距离10，故p=2。再得y=±6。",
      "重新计算参数和两个对称点，来源结果一致。"),
    "bank:cmm:20292": reviewed("conics", ["抛物线标准方程", "二次函数最值"], ["利用抛物线约束将目标化为单变量二次函数并求最小值"], 1,
      "直接代入y²=4x，将目标化成x≥0上的二次函数；顶点在定义域外，最小值取边界。", "calculation", "numeric",
      ["点A(x,y)在抛物线y²=4x上，求z=x²+y²/2+3的最小值。"], ["3，当(x,y)=(0,0)时取得。"],
      [["由约束y²=4x得x≥0且z=x²+2x+3=(x+1)²+2。", "当x≥0时z随x递增，故x=0时取最小值3；对应y=0。"]],
      [[("代入曲线约束", "将y²/2化为2x并注明x≥0"), ("求边界最小值", "说明x=0可取且给出z=3")]],
      "z=x²+2x+3=(x+1)²+2，定义域x≥0，因此最小点是x=0，抛物线上对应y=0，最小值3。",
      "来源解析的单调性判断与配方复核一致。"),
    "bank:cmm:16753": reviewed("distributions_regression", ["线性回归", "最小二乘法回归直线性质"], ["利用回归直线经过样本中心求截距"], 1,
      "五个数据点均完整，给定斜率后由样本均值点在回归直线上直接求截距。", "fill_blank", "numeric",
      ["数据x为0,1,2,3,4，y为2,3,6,9,10。回归方程为ŷ=2.2x+â，求â。"], ["1.6。"],
      [["x均值为2，y均值为6。最小二乘回归直线经过(2,6)，故6=2.2·2+â，解得â=1.6。"]],
      [[("计算样本中心", "得到x均值2、y均值6"), ("代入回归直线性质", "用6=2.2×2+â求出1.6")]],
      "样本均值为(2,6)，代入经过样本中心的回归直线得截距6−4.4=1.6。",
      "数据表、斜率及待求参数均清晰；来源解答同算。"),
    "bank:cmm:17067": reviewed("distributions_regression", ["线性回归", "样本中心"], ["利用回归直线经过样本中心求含参数数据"], 1,
      "等间距x数据均值易算，回归直线经过样本中心给出一条线性方程确定a。", "calculation", "numeric",
      ["x数据为1,3,5,7；y数据为3a,7,9,5a。回归方程y=1.2x+3.2，求a。"], ["a=2。"],
      [["x均值为4，回归线预测样本均值为1.2·4+3.2=8。y均值=(3a+7+9+5a)/4=2a+4。", "令2a+4=8，得a=2。"]],
      [[("使用回归线经过样本中心", "求出样本y均值为8"), ("建立均值方程", "写出2a+4=8并解得a=2")]],
      "y均值=ŷ(4)=8；实际y均值=(8a+16)/4=2a+4，解得a=2。",
      "来源解析和独立均值计算一致。"),
    "bank:cmm:16791": reviewed("probability", ["古典概型", "对立事件"], ["用对立事件计算独立二元选择中的两类均出现概率"], 1,
      "四名专家独立等可能二选一，共16个等可能结果；仅两种结果未覆盖两天。", "fill_blank", "numeric",
      ["四位专家各自独立且等可能选择周一或周二，求两天都有专家参加的概率。"], ["7/8。"],
      [["总安排数为2⁴=16。未覆盖两天的情况只有全选周一或全选周二，共2种。", "所求概率=(16−2)/16=7/8。"]],
      [[("列出等可能样本空间规模", "得2⁴=16"), ("计算对立事件", "排除两种全选同一天的安排，得到7/8")]],
      "四个独立二元选择产生16种等可能安排；全周一或全周二共2种，所以概率14/16=7/8。",
      "独立性与等可能性均由题干给定，结果可直接复算。"),
    "bank:cmm:16682": reviewed("counting_binomial", ["排列与计数原理", "古典概型"], ["无重复数字组成两位数并用计数法求概率"], 1,
      "两位数由不同数字构成，按十位分类可计出总样本数和事件数。", "fill_blank", "numeric",
      ["从1,2,3,4,5,6中任取两个数字组成两位数，求该两位数大于50的概率。"], ["1/3。"],
      [["不重复取数，样本空间大小为6·5=30。十位为5时个位可为1,2,3,4,6，共5种；十位为6时个位可为1至5，共5种。", "有利结果10种，概率10/30=1/3。"]],
      [[("确认无重复样本空间", "总数为6×5=30"), ("按十位计数有利结果", "十位5或6，各有5种"), ("求概率", "得到1/3")]],
      "总数为排列数P(6,2)=30。大于50的有十位5或6且个位不相同的10个数，概率1/3。",
      "来源列出的30个基本事件和10个有利事件经逐项计数核对无误。"),
    "bank:cmm:16977": reviewed("counting_binomial", ["分类计数原理", "古典概型"], ["对三角形九九表按乘积大小分类计数"], 1,
      "口诀表共9+8+…+1条，逐行计数乘积不大于10的14条。", "fill_blank", "numeric",
      ["三角形九九表中任意取一句口诀，求乘积不大于10的概率。"], ["14/45。"],
      [["总口诀数为1+2+…+9=45。按较大乘数j=1至9逐行计数，乘积≤10的条数依次为1,2,3,2,2,1,1,1,1，共14条。", "等可能抽取一条，概率14/45。"]],
      [[("计数总样本", "得到45条口诀"), ("分类计数有利事件", "按较大乘数分行合计14条"), ("求概率", "得到14/45")]],
      "三角形表按最大因数n列出n个式子，总数45。逐行符合ij≤10的条数为1,2,3,2,2,1,1,1,1，总计14，故概率14/45。",
      "来源答案的14/45经按行穷举复核。"),
    "bank:cmm:20119": reviewed("derivatives", ["复合函数求导", "三角函数求导"], ["使用链式法则求三次复合函数导数"], 1,
      "外层三次幂与内层cos(2x)连续使用链式法则即可。", "calculation", "expression",
      ["求y=(1+cos2x)³的导数。"], ["y′=−6(1+cos2x)²sin2x。"],
      [["链式法则：y′=3(1+cos2x)²·(−2sin2x)=−6(1+cos2x)²sin2x。"]],
      [[("应用链式法则", "外层导数为3(1+cos2x)²"), ("处理内层复合项", "(cos2x)'=−2sin2x并合并系数")]],
      "对外层求导再乘内层导数，得−6(1+cos2x)^2 sin2x。与来源等价形式−48 sin x cos^5 x一致。",
      "题干完整；用恒等式1+cos2x=2cos²x可核验来源表达式等价。"),
    "bank:cmm:20192": reviewed("derivatives", ["指数函数求导", "导数研究函数单调性"], ["求指数函数与一次函数组合的导数并判定单调区间"], 1,
      "令a=0后导数符号由e^x−1决定，在实轴分段符号明确。", "composite", "multipart",
      ["f(x)=e^x−1−x−ax²，若a=0，求f的单调区间。"], ["在(−∞,0)递减，在(0,+∞)递增。"],
      [["a=0时f=e^x−1−x，f′=e^x−1。", "x<0时e^x<1故f′<0；x>0时e^x>1故f′>0。", "所以在(−∞,0)递减，在(0,+∞)递增。"]],
      [[("求导", "得到f′=e^x−1"), ("判断导数符号", "分别在0左右给出负、正"), ("给出区间", "正确写出两个开单调区间")]],
      "a=0后f′(x)=e^x−1，仅在x=0为零；导数在左侧负、右侧正，因此左减右增。",
      "来源解析与独立导数符号分析一致。"),
})

# A second hand-read tranche, chosen for complete stems and independently
# reproducible arithmetic or proofs. Each item below was checked against its
# own source text and solution rather than selected by a topic-only rule.
ITEMS.update({
    "bank:cmm:14996": reviewed("sets_logic", ["集合的交并补运算", "有限集合"], ["由方程解集构造集合", "有限全集中的交并补运算"], 1,
      "三个有限集均可显式列出，按元素逐步求交、补和并即可复核。", "composite", "multipart",
      ["在U={1,2,3,4,5,6,7,8}中，A={x|x²−3x+2=0}，B={x|1≤x≤5且x∈Z}，C={x|2<x<9且x∈Z}。求A∪(B∩C)。", "求(C_U B)∪(C_U C)。"],
      ["{1,2,3,4,5}", "{1,2,6,7,8}"],
      [["解方程得A={1,2}；B={1,2,3,4,5}，C={3,4,5,6,7,8}。", "B∩C={3,4,5}，与A取并得{1,2,3,4,5}。"], ["相对U取补：C_U B={6,7,8}，C_U C={1,2}。", "两补集并为{1,2,6,7,8}。"]],
      [[("列出各集合", "正确解方程并写出A、B、C的元素"), ("按运算次序求交并", "先得B∩C={3,4,5}再与A取并")], [("求相对补集", "以U为全集分别得到{6,7,8}和{1,2}"), ("求并集", "给出{1,2,6,7,8}")]],
      "A={1,2}, B={1,2,3,4,5}, C={3,4,5,6,7,8}。所以B∩C={3,4,5}，A∪(B∩C)={1,2,3,4,5}。补集分别为{6,7,8}、{1,2}，其并集为{1,2,6,7,8}。",
      "逐个解出有限集合并依照运算优先顺序计算；两问结果均与来源答案相符。"),
    "bank:cmm:15358": reviewed("sets_logic", ["集合的区间表示", "集合交并与参数"], ["按区间端点关系求集合交集", "利用区间覆盖条件求参数范围"], 2,
      "第一问求区间交；第二问把实数轴未被B覆盖的区间与A比较，严格端点决定开区间。", "composite", "multipart",
      ["A={x|a−4<x<a+4}，B={x|x>5或x<−1}。(1) a=1时求A∩B。", "(2)若A∪B=R，求a范围。"],
      ["(−3,−1)", "1<a<3"],
      [["a=1时A=(−3,5)，B=(−∞,−1)∪(5,+∞)。", "交集为(−3,−1)。"], ["B未覆盖的部分是[−1,5]；要使A覆盖这段且端点−1、5也属于A，需a−4<−1且a+4>5。", "解得a<3且a>1。"]],
      [[("正确写区间", "得到A=(−3,5)及B的两段"), ("求交集", "得到(−3,−1)")], [("识别未覆盖部分及端点", "确保−1和5均被A包含"), ("解严格不等式", "得到1<a<3")]],
      "a=1时A=(-3,5)，与B的交集=(-3,-1)。对并集覆盖，B之外的闭区间[-1,5]必须落在开区间A=(a-4,a+4)中，故a-4<-1且a+4>5，即1<a<3。",
      "特别检查并集条件的闭端点−1、5必须由A覆盖，因此参数不取端点；与来源解析一致。"),
    "bank:cmm:14294": reviewed("functions", ["函数方程", "函数单调性", "函数不等式"], ["由乘法型函数方程确定正值和倒数", "用差值证明严格单调", "借单调性解复合函数不等式"], 3,
      "三问依赖函数方程逐步推出正性、单调性，再转化为二次不等式，证明链条完整且含多步依赖。", "composite", "multipart",
      ["函数f:R→R满足f(0)≠0；x>0时f(x)>1；f(x+y)=f(x)f(y)。(1)证明x<0时0<f(x)<1。", "(2)判断并证明f在R上的单调性。", "(3)解f(x)f(2x−x²)>1。"],
      ["x<0时0<f(x)<1", "f在R上严格递增", "(0,3)"],
      [["令x=y=0得f(0)=f(0)²；结合非零得f(0)=1。", "对x<0有−x>0，且f(x)f(−x)=f(0)=1；因f(−x)>1，故f(x)=1/f(−x)∈(0,1)。"], ["任取x₁<x₂，则x₂−x₁>0，故f(x₂−x₁)>1。", "f(x₂)=f(x₂−x₁)f(x₁)>f(x₁)，其中f(x₁)>0由第(1)问及f(0)=1得出。"], ["由乘法方程，f(x)f(2x−x²)=f(3x−x²)。", "严格递增且f(0)=1，故该式大于1等价于3x−x²>0，即0<x<3。"]],
      [[("确定f(0)", "由方程与非零条件推出f(0)=1"), ("利用相反数关系", "使用f(x)f(−x)=1并得到0<f(x)<1")], [("任取有序自变量", "构造x₂−x₁>0"), ("比较函数值", "由方程和正性推出f(x₂)>f(x₁)")], [("合并函数方程", "把乘积写成f(3x−x²)"), ("用单调性转化并解不等式", "得3x−x²>0及(0,3)")]],
      "先由f(0)=f(0)^2及f(0)≠0得f(0)=1。x<0时f(x)f(−x)=1且f(−x)>1，所以0<f(x)<1。对x₁<x₂，f(x₂−x₁)>1且f(x₁)>0，故f(x₂)>f(x₁)。最后原式化为f(3x−x²)>f(0)，由严格递增等价于3x−x²>0，解为(0,3)。",
      "三个小问依赖关系已逐步检查；正性、严格不等号及二次不等式解集均与来源一致。"),
    "bank:cmm:14384": reviewed("exponential_logarithmic", ["指数函数值域"], ["指数函数复合线性函数的值域", "指数函数在受限定义域上的值域"], 1,
      "指数自变量的取值范围可直接确定；第二问用底数小于1的单调性得到端点值和渐近端。", "composite", "multipart",
      ["求y=2^(1−x)的值域。", "求y=(1/3)^(2x−1)，x∈[−1,+∞)的值域。"],
      ["(0,+∞)", "(0,27]"],
      [["当x取遍R时，1−x也取遍R；指数函数2^t的值域为(0,+∞)。"], ["x≥−1给出2x−1≥−3。底数1/3小于1，函数递减，最大值在x=−1时为(1/3)^−3=27，且x趋于无穷时函数趋于0但不取到。"]],
      [[("判断指数的取值范围", "指出1−x遍历R"), ("给出正值范围", "写出(0,+∞)")], [("变换指数范围", "得到2x−1∈[−3,+∞)"), ("结合单调性和端点", "得到最大值27且下端0不取")]],
      "第一式指数1−x遍历全部实数，故值域为(0,+∞)。第二式指数从−3增至无穷，而(1/3)^t递减；最大值27在x=−1取得，趋近0但永不等于0，值域(0,27]。",
      "独立检查指数范围、单调方向以及0是否可取，结果与来源答案一致。"),
    "bank:cmm:14403": reviewed("exponential_logarithmic", ["分数指数幂", "完全平方恒等式"], ["通过平方求a与倒数之和", "再次平方求二次对称和"], 1,
      "底数为正，连续平方两次即可得到所求对称式；等式变形无增根风险，因为只作恒等平方计算。", "composite", "multipart",
      ["已知√a+1/√a=√5，求a+a^−1。", "求a²+a^−2。"], ["3", "7"],
      [["两边平方：a+2+a^−1=5，得a+a^−1=3。"], ["再平方(a+a^−1)²=a²+2+a^−2=9，得a²+a^−2=7。"]],
      [[("平方并使用恒等式", "正确展开并求得3")], [("利用上一问结果再平方", "正确减去中间项2并求得7")]],
      "第一次平方得a+2+a^{-1}=5，所以a+a^{-1}=3。于是(a+a^{-1})²=a²+2+a^{-2}=9，故a²+a^{-2}=7。",
      "按题设正平方根等式逐次平方复核，来源两项数值一致。"),
    "bank:cmm:18362": reviewed("plane_vectors", ["向量坐标", "向量模与单位向量"], ["由两点坐标求位移向量", "单位化向量并保持方向"], 1,
      "坐标差为(5,12)，模为13；单位化得到唯一同向单位向量。", "fill_blank", "expression",
      ["A(−1,3)，B(4,15)，求与AB同向的单位向量。"], ["(5/13,12/13)"],
      [["AB=(4−(−1),15−3)=(5,12)，模为√(25+144)=13。", "同向单位向量为AB/|AB|=(5/13,12/13)。"]],
      [[("求向量坐标", "得到(5,12)"), ("求模并单位化", "得到模13及所求坐标")]],
      "AB=(5,12)，长度13，故唯一同向单位向量是(5/13,12/13)。",
      "直接由端点坐标复算向量和模，与来源结果一致。"),
    "bank:cmm:20532": reviewed("complex_numbers", ["复数相等", "实部与虚部"], ["将复数等式拆成实虚部方程组", "解二次方程并验证组合"], 1,
      "比较实部和虚部后得到两个简单方程，联立可完全枚举实数解。", "calculation", "multipart",
      ["实数x,y满足x²−y²+2xy i=2i，求(x,y)。"], ["(1,1)或(−1,−1)"],
      [["比较实部得x²−y²=0，即(x−y)(x+y)=0；比较虚部得xy=1。", "若x=y，则x²=1，得(1,1)、(−1,−1)；若x=−y，则−x²=1无实数解。"]],
      [[("比较实部和虚部", "列出x²−y²=0、xy=1"), ("穷尽方程组解", "得到两个同号解并排除异号分支")]],
      "实部为零、虚部为2给出x²=y²且xy=1。x=y时x²=1得两组解；x=−y将导致xy=−x²≤0，不可能等于1。",
      "对两个可能的因式分支逐一求解，来源答案完整且相符。"),
    "bank:cmm:18521": reviewed("sequences", ["等差数列", "等差数列性质"], ["以中间两项表示四项等差数列", "由和与中间项乘积求公差并枚举符号"], 2,
      "用中间值和公差参数化，和确定中点，乘积确定公差平方，因此有正负两种排列。", "calculation", "text",
      ["四个数成等差数列，和为26，第二个数与第三个数乘积为40，求这四数。"], ["2,5,8,11 或 11,8,5,2"],
      [["设四项依次为a−3d,a−d,a+d,a+3d。总和4a=26，故a=13/2。", "中间两项乘积a²−d²=40，故d²=9/4，d=±3/2。", "分别代入得到2,5,8,11或11,8,5,2。"]],
      [[("设等差参数", "正确写出以中心a及公差d表示的四项"), ("建立并求解条件", "由总和得a=13/2，由乘积得d=±3/2"), ("给出两种顺序", "列全正负公差对应的序列")]],
      "设四项对称写为a−3d,a−d,a+d,a+3d。4a=26得a=13/2；a²−d²=40得d²=9/4。取d=±3/2，得到两组反向排列。",
      "参数化后代回两项条件均成立；保留公差正负两种序列。"),
    "bank:cmm:16530": reviewed("statistics", ["分层抽样", "抽样比"], ["按总体层比例分配样本量", "由样本分层比例反推总体层人数"], 1,
      "两问都依赖同一抽样比；第二问先从总人数关系确定老年总体数，再换算样本数。", "composite", "multipart",
      ["大型、中型、小型超市分别200、400、1400家，分层抽样容量100，应抽中型超市多少家？", "职工共430人，青年160人，中年为老年人数的2倍。按分层抽样抽到青年32人，样本中老年多少人？"],
      ["20家", "18人"],
      [["总体数2000，抽样比100/2000=1/20。", "中型样本数400/20=20。"], ["设老年人数L，则L+2L=430−160=270，故L=90。", "青年样本比例32/160=1/5，老年样本90/5=18。"]],
      [[("计算抽样比", "得到1/20"), ("按层分配", "得到20家")], [("根据层人数关系求总体老年人数", "得到90人"), ("使用同一抽样比例", "得到18人")]],
      "超市总体2000家，抽样比0.05，中型抽20家。职工老年数L满足3L=270，L=90；样本比例32/160=0.2，老年样本为18人。",
      "两种分层抽样均独立计算比例，检查样本量与总体层比例一致。"),
    "bank:cmm:16532": reviewed("statistics", ["数据的集中趋势与离散程度", "方差与标准差"], ["辨析极差、方差和标准差的稳定性含义", "区分平均数与离散程度"], 1,
      "逐条依据统计量定义判别；极差、标准差、方差衡量离散程度，平均数本身不决定分散大小。", "short_answer", "text",
      ["判断四条说法正确的个数：(1)极差越小数据越集中稳定；(2)平均数越小数据越集中稳定；(3)标准差越小数据越集中稳定；(4)方差越小数据越集中稳定。"], ["3条"],
      [["(1)极差小意味着最大值与最小值差小，符合离散程度小；(2)平均数是位置量，大小不能说明离散程度，错误。", "(3)标准差和(4)方差都是离散程度指标，数值较小表示更集中稳定；所以正确的有3条。"]],
      [[("判断离散指标", "正确判断极差、标准差、方差三条"), ("辨析平均数", "指出平均数大小不能推出集中程度并计数为3")]],
      "极差、标准差、方差均描述离散程度，越小通常越集中；平均数描述中心位置，不决定离散程度。因此(1)(3)(4)正确，共3条。",
      "分别按统计量含义判断四句，结论与来源选项C及解析一致。"),
    "bank:cmm:20068": reviewed("conics", ["抛物线焦点弦", "韦达定理", "向量数量积"], ["设过焦点直线参数式并代入抛物线", "用根和根积计算两焦点弦端点向量积"], 2,
      "以斜率参数化过焦点直线，利用二次方程根和根积消去参数，结论对竖直线也需单独检验。", "proof", "expression",
      ["直线l与抛物线y²=4x交于不同A、B，且l过焦点，求OA·OB。"], ["−3"],
      [["若l非竖直，写为x=ty+1。代入得y²−4ty−4=0，故y₁+y₂=4t，y₁y₂=−4。", "A=(ty₁+1,y₁)，B=(ty₂+1,y₂)。点积=(ty₁+1)(ty₂+1)+y₁y₂=t²(−4)+t(4t)+1−4=−3。", "若l为竖直线x=1，则交点为(1,2)、(1,−2)，点积=1−4=−3。"]],
      [[("设置直线并列根关系", "对非竖直线得到根和4t、根积−4"), ("计算向量点积", "正确展开并消去t得到−3"), ("检查竖直焦点线", "单独代入验证结果仍为−3")]],
      "非竖直l写作x=ty+1，交点y坐标根和4t、根积−4；点积为t²(-4)+4t²+1-4=-3。竖直焦点线x=1的交点(1,±2)，点积亦为-3。",
      "来源解析有乘积展开下标笔误；我按A、B对应坐标分别复算，并补验竖直线这一未覆盖情形，结论仍为−3。"),
    "bank:cmm:16459": reviewed("solid_geometry", ["二面角", "三垂线与垂直关系"], ["取棱中点构造二面角平面角", "用三角形三边关系判定直角"], 2,
      "连接两等边三角形顶点与公共棱中点，证明为平面角后使用三边长度判直角。", "proof", "text",
      ["P在△ABC平面外，△PBC和△ABC均为边长2的正三角形，PA=√6，求二面角P−BC−A。"], ["90°"],
      [["取BC中点O，则AO⊥BC且PO⊥BC，因为两等边三角形的中线垂直底边。故∠POA为二面角的平面角。", "AO=PO=√3，PA=√6；由勾股逆定理，AO²+PO²=6=PA²，所以∠POA=90°。"]],
      [[("构造平面角", "证明AO与PO均垂直BC"), ("确定边长", "得到AO=PO=√3及PA=√6"), ("判定角度", "使用勾股逆定理得到90°")]],
      "BC中点O到A、P的距离均为√3，且OA、OP都垂直BC，因此∠AOP为所求二面角平面角。三边满足3+3=6，故该角为直角。",
      "确认棱中点处两条中线均垂直公共棱，再由三边长度确定夹角为90°。"),
    "bank:cmm:20114": reviewed("derivatives", ["多项式函数求导", "导数值"], ["逐项求多项式函数的导数", "代入指定自变量计算函数导数值"], 1,
      "多项式按幂函数求导规则逐项处理，再将x=−3代入；计算可直接验算。", "composite", "multipart",
      ["f(x)=2x³−3x²−5x+4，求f′(x)。", "求f′(−3)。"], ["6x²−6x−5", "67"],
      [["逐项求导： (2x³)'=6x²，(−3x²)'=−6x，(−5x)'=−5，常数项导数为0。"], ["代入x=−3：6·9−6·(−3)−5=54+18−5=67。"]],
      [[("逐项求导", "给出6x²−6x−5" )], [("代入并运算", "正确计算为67")]],
      "f'(x)=6x²−6x−5；f'(-3)=54+18−5=67。",
      "逐项求导及代入运算均已复核，与来源答案一致。"),
    "bank:cmm:17068": reviewed("distributions_regression", ["线性回归", "样本中心"], ["利用回归直线经过样本中心", "由均值关系求缺失观测值"], 2,
      "先求自变量均值，再令回归线经过样本中心；缺失值通过样本均值唯一确定。", "fill_blank", "numeric",
      ["p为6,10,14,18,22，对应y为62,m,44,28,14。回归线为ŷ=−3p+82.2，求m。"], ["53"],
      [["p均值为14，故回归直线在样本中心处的y均值为−3·14+82.2=40.2。", "y均值=(62+m+44+28+14)/5=(148+m)/5，令其等于40.2，得148+m=201，m=53。"]],
      [[("求x均值及样本中心关系", "得到p均值14且回归线预测中心纵坐标40.2"), ("建立缺失数据均值方程", "正确列式并求出m=53")]],
      "p均值14，回归线给出样本y均值40.2。其余四个y之和148，因此(148+m)/5=40.2，解得m=53。",
      "按回归线必过样本中心的性质复算缺失值，与来源步骤一致。"),
    "bank:cmm:14441": reviewed("functions", ["函数零点", "二分法"], ["用相邻异号函数值定位零点", "按精度要求进行四舍五入"], 1,
      "题给相邻试值在1.5562和1.5625处异号，根被夹在长度约0.0063的区间内，按0.01精度取1.56。", "fill_blank", "numeric",
      ["用二分法求3^x−x−4=0的一个近似解，精确到0.01。已知f(1.5562)≈−0.029，f(1.5625)≈0.003。"], ["1.56"],
      [["端点函数值异号，连续性保证该区间内有零点。", "区间[1.5562,1.5625]内的数四舍五入到百分位均为1.56（区间不跨越1.565或1.555边界）。"]],
      [[("确认根所在区间", "使用异号端点确定夹根区间"), ("按题目精度取近似值", "将根区间内值四舍五入到1.56")]],
      "函数连续且f(1.5562)<0<f(1.5625)，故零点在该区间内。此区间所有数按百分位四舍五入为1.56。",
      "按题给函数值验证异号，再检查指定精度下整个夹根区间的舍入值一致。"),
    "bank:cmm:14459": reviewed("functions", ["函数零点", "参数范围"], ["将方程解条件改写成参数函数值域", "利用单调性确定开区间值域"], 2,
      "将a表示为x的函数，在开区间(1,2)上严格递增；端点值不取，得到开区间参数范围。", "proof", "text",
      ["f(x)=4x²−4ax+a+2。方程f(x)=0在(1,2)内有实根，求a的范围。"], ["2<a<18/7"],
      [["对根x∈(1,2)，方程给a=(4x²+2)/(4x−1)，分母在此区间为正。", "记g(x)=(4x²+2)/(4x−1)，则g′(x)=8(2x+1)(x−1)/(4x−1)²>0。", "故g((1,2))=(g(1),g(2))=(2,18/7)，端点因x不取1、2而不取到。"]],
      [[("解出参数函数", "得到a=g(x)且分母正"), ("验证严格单调", "求导并证明g′>0于(1,2)"), ("计算开区间值域", "得到(2,18/7)并说明端点不取")]],
      "根条件等价于a=g(x)=(4x²+2)/(4x−1)，x∈(1,2)。导数为8(2x+1)(x−1)/(4x−1)²，区间内正，故a取值恰为(g(1),g(2))=(2,18/7)。",
      "不采用来源解析中不必要且表述不严的判别式分支；以根变量参数化并验证严格递增，得到相同开区间。"),
})

# Third tranche adds genuine logarithm, numerical-root and spatial-vector items.
ITEMS.update({
    "bank:cmm:18679": reviewed("exponential_logarithmic", ["对数函数图象", "基本不等式"], ["确定对数函数图象定点", "在乘积约束下用均值不等式求最值"], 2,
      "先由对数真数为1确定恒过点，再将直线条件化成正数约束并验证均值不等式取等条件。", "calculation", "numeric",
      ["函数y=log_a(x+3)−1 (a>0且a≠1)的图象恒过点A。若A在直线mx+ny+1=0上且mn>0，求1/m+2/n的最小值。"], ["8"],
      [["令x+3=1，得恒过点A=(−2,−1)。代入直线得2m+n=1。由mn>0且2m+n>0，推出m,n均为正。", "1/m+2/n=(2m+n)/m+2(2m+n)/n=4+n/m+4m/n。", "由AM-GM，n/m+4m/n≥4，故最小值8；当n/m=4m/n且2m+n=1时，m=1/4,n=1/2可取到。"]],
      [[("确定图象定点与线性约束", "得到A=(−2,−1)及2m+n=1"), ("判断参数正性", "使用mn>0与线性式正推出m,n>0"), ("用均值不等式并验证等号", "得到下界8且给出可行等号参数")]],
      "对数图象在x+3=1时恒过A=(-2,-1)，所以2m+n=1。mn>0且左端为正，m,n皆正。将目标写作4+n/m+4m/n，后两项乘积为4，和至少4，故最小8，在(m,n)=(1/4,1/2)取到。",
      "独立核对对数图象定点、参数符号、AM-GM下界及等号点可行性。"),
    "bank:cmm:18704": reviewed("exponential_logarithmic", ["对数运算性质", "基本不等式"], ["用对数和转化为正数乘积约束", "利用均值不等式求最小值并检验取等"], 1,
      "对数和合并后得到xy=10，代入消元后用一元均值不等式即可求出可达最小值。", "calculation", "numeric",
      ["已知lg x+lg y=1，求2/x+5/y的最小值。"], ["2"],
      [["定义域要求x,y>0，合并对数得lg(xy)=1，即xy=10。", "y=10/x，因此2/x+5/y=2/x+x/2≥2√((2/x)(x/2))=2；x=2,y=5时取等。"]],
      [[("合并对数并确定定义域", "得到x,y>0且xy=10"), ("消元后应用均值不等式", "得到下界2"), ("验证可达", "给出x=2,y=5满足约束")]],
      "由对数性质得xy=10。目标等于2/x+x/2，二项均正，乘积为1，故和至少2；取x=2、y=5时等号成立。",
      "检查对数真数正性、乘积约束与等号变量满足原条件。"),
    "bank:cmm:14583": reviewed("exponential_logarithmic", ["对数定义", "函数零点"], ["利用乘积为零求零点并检查定义域"], 1,
      "定义域为x>0且x≠3；分子乘积为零只给x=1，需确认不在排除点。", "fill_blank", "numeric",
      ["求函数f(x)=((x−1)ln x)/(x−3)的零点。"], ["1"],
      [["定义域要求x>0且x≠3。分子为零等价于x−1=0或ln x=0，两条件都给x=1。", "x=1属于定义域，故唯一零点为1。"]],
      [[("结合对数定义域", "写出x>0且排除x=3"), ("求分子零点并检查", "得到x=1且可取")]],
      "对数定义域x>0且分母x−3不为0。分子零当x=1或lnx=0，二者均为x=1；代入分母非零，唯一零点为1。",
      "独立核对定义域、两因子零点以及分母非零条件。"),
    "bank:cmm:15375": reviewed("functions", ["二分法", "函数零点"], ["判断端点和区间中点的函数值符号", "据异号区间更新夹根范围"], 1,
      "区间端点和中点的函数值符号可精确判断，按二分法保留异号一侧。", "fill_blank", "text",
      ["用二分法求ln x−2+x=0在[1,2]内的根。已取中点c=3/2，求下一个含根区间。"], ["(3/2,2)"],
      [["设f(x)=lnx−2+x。f(3/2)=ln(3/2)−1/2<0（因为3/2<√e），而f(2)=ln2>0。", "故中点与右端异号，下一含根区间为(3/2,2)。"]],
      [[("计算符号", "得到f(3/2)<0且f(2)>0"), ("执行二分更新", "保留异号端点区间(3/2,2)")]],
      "f(3/2)=ln(3/2)-1/2<0，因为ln(3/2)<ln√e=1/2；f(2)=ln2>0。因此下一次保留右半区间(3/2,2)。",
      "检验中点对数值的符号依据及二分法区间更新规则。"),
    "bank:cmm:21316": reviewed("spatial_vectors", ["空间向量", "直线与平面平行"], ["由端点求直线方向向量", "用方向向量垂直平面法向量确定选项"], 1,
      "方向向量为B−A，直线平行平面要求与法向量点积为零；选项D正是对应方程。", "single_choice", "choice",
      ["A(2,4,1), B(1,2,0)，平面α法向量为(a,b,c)，若AB∥α，选满足条件的关系式。"], ["D"],
      [["AB=B−A=(−1,−2,−1)。平行条件为AB·(a,b,c)=0，即−a−2b−c=0，等价于a+2b+c=0，选D。"]],
      [[("求方向向量并写垂直条件", "得到−a−2b−c=0"), ("匹配选项", "等价式a+2b+c=0对应D")]],
      "AB=(-1,-2,-1)，与法向量点积为−a−2b−c。令其为0，得到a+2b+c=0，因此选D。",
      "按原题点线平行的法向量判据复算选项D。"),
    "bank:cmm:21318": reviewed("spatial_vectors", ["空间向量", "直线与平面平行"], ["利用向量点积为零判定直线平行平面"], 1,
      "逐项计算方向向量与法向量点积，只有D为零。", "single_choice", "choice",
      ["若直线方向向量为a、平面法向量为μ，判断哪组可使l∥α。"], ["D"],
      [["直线平行平面需a·μ=0。A点积−2；B为6；C为1；D为1·0+(−1)·3+3·1=0，故选D。"]],
      [[("应用点积判据", "说明方向向量与法向量点积应为0"), ("逐项筛选", "算得A、B、C非零而D为0")]],
      "点线平行判据是方向向量垂直法向量。四项点积依次为−2、6、1、0，故只有D成立。",
      "逐项独立计算四组点积，来源答案D一致。"),
    "bank:cmm:14352": reviewed("functions", ["函数模型", "函数最值", "二次函数"], ["将实际问题中的分段投入建成函数", "通过换元求受约束收益最大值"], 2,
      "需将投入比例写成定义域受限的收益函数，再以平方根换元配方并检查顶点处于可行区间。", "composite", "multipart",
      ["合作社给两个大棚总投入200万元，每棚至少20万元。甲棚投入x万元时收益P=80+4√(2x)，乙棚投入a万元时收益Q=a/4+120。(1)求f(50)。(2)如何分配投入使总收益最大？"],
      ["f(50)=277.5万元。", "甲投入128万元、乙投入72万元，最大总收益282万元。"],
      [["x=50时乙投入150。P=80+4√100=120，Q=150/4+120=157.5，所以f(50)=277.5。"], ["令x为甲投入，则乙投入200−x，20≤x≤180。总收益f(x)=80+4√(2x)+(200−x)/4+120=−x/4+4√(2x)+250。", "令t=√x，则t∈[2√5,6√5]，f=−t²/4+4√2t+250=−(t−8√2)²/4+282。", "顶点t=8√2在允许区间内，故x=128，乙投入72，最大收益282。"]],
      [[("准确建模并代入", "分别计算两棚收益并求和为277.5" )], [("建立函数与可行域", "写出f(x)及20≤x≤180"), ("换元求最值", "令t=√x并正确配方"), ("检验最优点可行并解释实际量", "确认x=128在区间内，给出另一棚投入72及最大值282")]],
      "x=50时另一棚为150，收益为120+157.5=277.5。一般地，f(x)=−x/4+4√(2x)+250，20≤x≤180。取t=√x后，f=−(t−8√2)²/4+282；t=8√2对应x=128，满足投入约束，乙棚72，最大收益282。",
      "逐项复核题设收益函数、投入约束、换元配方和最优点可行性；该题只测纸笔建模和计算，不代表学生实际项目能力。"),
    "bank:cmm:20162": reviewed("functions", ["函数模型", "销售利润", "平方因式分解与全局最值"], ["根据需求增量建立利润函数", "用非负因式证明三次函数全局最大值"], 3,
      "需由增长规律建立销量和利润模型，并将利润与上界之差分解为非负因式；无需用后续微积分知识。", "composite", "multipart",
      ["某商品进价12元、售价20元时每天售48件。降价x元（0≤x≤8）时，每天多售件数与x²+x成正比，且降价3元时多售36件。(1)写出日利润函数。(2)求利润最大时的售价。"],
      ["f(x)=−3x³+21x²−24x+384，0≤x≤8。", "售价16元，最大日利润432元。"],
      [["设销量增量为k(x²+x)，由降价3元时多售36件得36=k(3²+3)，所以k=3。降价x元后单件利润为8−x，销量为48+3(x²+x)，故f(x)=(8−x)[48+3(x²+x)]=−3x³+21x²−24x+384，0≤x≤8。"], ["恒等变形：432−f(x)=3(x+1)(x−4)²。", "在0≤x≤8上，x+1>0且平方项非负，因此f(x)≤432；x=4时等号成立，最大日利润为432元。", "实际售价为20−4=16元。"]],
      [[("从销量变化求比例系数", "由36=k(3²+3)得k=3"), ("建立利润函数和可行域", "得到f(x)=−3x³+21x²−24x+384及0≤x≤8")], [("分解上界与利润之差", "得到432−f(x)=3(x+1)(x−4)²"), ("证明全局最大并验证等号", "证明f≤432且x=4取等"), ("换回售价", "售价16元")]],
      "由36=k(3²+3)得k=3，故f(x)=(8−x)[48+3(x²+x)]=−3x³+21x²−24x+384，0≤x≤8。恒等式432−f(x)=3(x+1)(x−4)²≥0，且x=4取等；最大利润432元，对应售价16元。",
      "从题设建立销量和利润模型，检查导数符号及区间端点，得全局最优售价；仅核验纸笔模型推理，不作为商业实践能力认证。"),
})

# Fourth tranche closes the first logarithm unit sample with source choices.
ITEMS.update({
    "bank:cmm:19269": reviewed("exponential_logarithmic", ["对数函数定义域", "根式函数定义域", "集合交集"], ["求根式与对数函数定义域并取交集"], 1,
      "根式给闭区间，对数真数要求严格正；交集端点一个包含、一个排除。", "single_choice", "choice",
      ["y=√(4−x²)的定义域为A，y=ln(1−x)的定义域为B，求A∩B。"], ["D"],
      [["4−x²≥0给−2≤x≤2；1−x>0给x<1。", "交集为[−2,1)，对应选项D。"]],
      [[("分别求定义域", "得到A=[−2,2]及B=(−∞,1)"), ("求交并匹配选项", "得到[−2,1)，选D")]],
      "根式定义域为[-2,2]，对数定义域为(-∞,1)。交集[-2,1)，与选项D一致。",
      "复核两个定义域的端点包含性和交集选项。"),
    "bank:cmm:19699": reviewed("exponential_logarithmic", ["对数运算性质", "等差数列定义"], ["将对数等差条件转为乘积等式", "对指数代换后解方程"], 2,
      "由三项成等差转化为对数等式，利用对数单调性去对数，再结合2^x正性取解。", "single_choice", "choice",
      ["若lg2、lg(2^x+1)、lg(2^x+5)成等差数列，求x。"], ["D"],
      [["等差中项给2lg(2^x+1)=lg2+lg(2^x+5)。", "令t=2^x>0，得(t+1)²=2(t+5)，即t²=9；由t>0得t=3。", "因此x=log₂3，对应D。"]],
      [[("使用等差中项和对数性质", "得到(2^x+1)²=2(2^x+5)"), ("解指数代换方程", "t>0推出t=3并得到x=log₂3"), ("选择选项", "匹配D")]],
      "设t=2^x>0。对数等差条件给(t+1)^2=2(t+5)，解t²=9；舍去负根，x=log₂3，选D。",
      "独立消去对数并检查指数代换t严格为正，答案D无冲突。"),
    "bank:cmm:20491": reviewed("exponential_logarithmic", ["对数函数单调性", "三段论推理"], ["辨析对数函数底数条件与单调性", "定位三段论前提错误"], 1,
      "三段论形式有效，小前提属实，但一般对数函数不总递增，底数小于1时递减。", "single_choice", "choice",
      ["推理：对数函数y=log_a x(a>0,a≠1)是增函数；y=log_(1/3)x是对数函数；所以它是增函数。结论错误的原因是什么？"], ["A"],
      [["小前提正确：底数1/3满足0<a≠1。三段论形式本身有效。", "大前提“所有对数函数都是增函数”错误；当0<a<1时对数函数递减。因此选A。"]],
      [[("辨析大前提", "指出底数在(0,1)时对数函数递减"), ("排除其他错误来源", "小前提正确且推理结构有效，选A")]],
      "对数函数单调性取决于底数：a>1时递增，0<a<1时递减。故大前提错误，而具体函数确是对数函数，三段论形式无误，选择A。",
      "按底数分类核验大前提为假，并对照其余两项排除推理形式或小前提错误。"),
})

# Preserve the original objective modes for multiple-choice source records.
for _qid in ("bank:cmm:19269", "bank:cmm:19699", "bank:cmm:20491"):
    _detail = ITEMS[_qid]
    _topic_tags = _detail["annotation"]["knowledge"]["primary"]
    _fine_types = _detail["annotation"]["fine_types"]
    _prompt = _detail["annotation"]["parts"][0]["prompt"]
    _steps = _detail["annotation"]["parts"][0]["solution_steps"]
    _ans = _detail["annotation"]["parts"][0]["reference_answer"]
    _detail["annotation"] = ann("single_choice", _topic_tags, _fine_types, 1,
        "逐题按对数定义域、运算性质或底数单调性分析，并匹配题源选项。", "choice",
        [part("p1", _prompt, _ans, _steps, _topic_tags, ["单项选择", "对数知识应用"],
            [crit("p1c1", "建立数学判断依据", "写明相应对数定义域、等式性质或单调性条件"), crit("p1c2", "选出原题正确选项", "推理结论与题源选项一致")])],
        accepted=[_ans], equivalence="exact")

# Preserve the original objective modes for multiple-choice source records.
for _qid in ("bank:cmm:21316", "bank:cmm:21318"):
    _detail = ITEMS[_qid]
    _topic_tags = _detail["annotation"]["knowledge"]["primary"]
    _fine_types = _detail["annotation"]["fine_types"]
    _prompt = _detail["annotation"]["parts"][0]["prompt"]
    _steps = _detail["annotation"]["parts"][0]["solution_steps"]
    _rationale = _detail["rationale"]
    _ans = _detail["annotation"]["parts"][0]["reference_answer"]
    _detail["annotation"] = ann("single_choice", _topic_tags, _fine_types, 1,
        "根据空间直线方向向量与平面法向量的垂直判据逐项计算。", "choice",
        [part("p1", _prompt, _ans, _steps, _topic_tags, ["单项选择", "空间向量判定"],
            [crit("p1c1", "列出向量平行判据", "指出方向向量与平面法向量点积为零"), crit("p1c2", "确定正确选项", "据独立点积运算匹配原选项")])],
        accepted=[_ans], equivalence="exact")

# Keep the original objective response mode for source records with choices.
_stat_tags = ["数据的集中趋势与离散程度", "方差与标准差"]
_stat_fine = ["辨析极差、方差和标准差的稳定性含义", "区分平均数与离散程度"]
ITEMS["bank:cmm:16532"]["annotation"] = ann(
    "single_choice", _stat_tags, _stat_fine, 1,
    "逐条依据统计量定义判别；极差、标准差、方差衡量离散程度，平均数本身不决定分散大小。",
    "choice", [part("p1", "选择正确说法个数对应的选项。", "C（正确说法共3条）",
        ["(1)极差小表示数据最大最小差较小，符合离散程度小。", "(2)平均数描述中心位置，不决定离散程度，错误。", "(3)标准差、(4)方差均衡量离散程度，越小越集中稳定；因此正确个数为3，对应C。"],
        _stat_tags, ["统计量概念辨析", "单项选择"],
        [crit("p1c1", "辨析四种统计量含义", "指出(1)(3)(4)涉及离散程度，(2)不涉及"), crit("p1c2", "对应原选项", "正确个数3并选择C")])],
    accepted=["C"], equivalence="exact")

# Five-source tranche for compulsory-2's trigonometric identities unit.
ITEMS.update({
    "bank:cmm:18257": reviewed("trigonometry", ["二倍角公式", "三角恒等变换"], ["利用余弦二倍角和正弦二倍角化简"], 1,
      "分子应用cos2θ，分母应用sin2θ；两角正好互补后约去非零正弦。", "single_choice", "choice",
      ["化简(cos²5°−sin²5°)/(sin40°cos40°)。"], ["B"],
      [["分子=cos10°，分母=(1/2)sin80°。因cos10°=sin80°，原式=2。", "对应选项B。"]],
      [[("使用二倍角公式", "得到分子cos10°、分母(1/2)sin80°"), ("利用互余关系并匹配", "化简为2并选B")]],
      "cos²5°−sin²5°=cos10°，sin40°cos40°=½sin80°，且cos10°=sin80°，商为2，选B。",
      "逐项使用双角公式并核对互余角关系。"),
    "bank:cmm:17495": reviewed("trigonometry", ["两角和差公式", "三角恒等变换"], ["将积化和差的余弦组合识别为差角余弦"], 1,
      "表达式是cos(A−B)恒等式，代入A=x+y、B=x−y即可。", "single_choice", "choice",
      ["化简sin(x+y)sin(x−y)+cos(x+y)cos(x−y)。"], ["B"],
      [["使用cos(A−B)=cosAcosB+sinAsinB，令A=x+y、B=x−y，得cos(2y)。", "对应选项B。"]],
      [[("辨认恒等式结构", "匹配cos(A−B)"), ("代入并选择", "得到cos2y，选B")]],
      "原式=cos[(x+y)−(x−y)]=cos2y，选B。",
      "按两角差余弦公式直接复核。"),
    "bank:cmm:17560": reviewed("trigonometry", ["两角和公式", "三角恒等变换"], ["展开和角并合并同角项"], 1,
      "先展开cos((x+y)+y)，与给定的2sin(x+y)siny合并后再用差角公式。", "single_choice", "choice",
      ["化简cos(x+2y)+2sin(x+y)siny。"], ["A"],
      [["展开第一项：cos(x+y)cosy−sin(x+y)siny。", "加上2sin(x+y)siny后为cos(x+y)cosy+sin(x+y)siny=cos((x+y)−y)=cosx，选A。"]],
      [[("展开和角公式", "得到cos(x+y)cosy−sin(x+y)siny"), ("合并并用差角公式", "得到cosx并选A")]],
      "展开后两个正弦乘积合并为+sin(x+y)siny；与cos(x+y)cosy组成cos((x+y)−y)=cosx，选A。",
      "独立展开并核验正负号和差角，来源答案A一致。"),
    "bank:cmm:17481": reviewed("trigonometry", ["诱导公式", "同角关系", "三角恒等变换"], ["利用诱导公式化简含π平移的三角式", "结合象限范围处理平方根主值"], 2,
      "需逐项使用奇偶性、周期性和互余关系；第一问保留原式定义域，第二问逐项化到平方和。", "composite", "multipart",
      ["化简：①[cos(α−π)/sin(π−α)]sin(α−π/2)cos(π/2+α)。", "②sin(−α−5π)cos(α−π/2)−sin(3π/2+α)cos(α−2π)。"],
      ["−cos²α（原式要求sinα≠0）", "1"],
      [["cos(α−π)=−cosα，sin(π−α)=sinα，sin(α−π/2)=−cosα，cos(π/2+α)=−sinα。", "相乘得(−cosα/sinα)(−cosα)(−sinα)=−cos²α。"], ["周期性得sin(−α−5π)=sin(−α−π)=sinα；又cos(α−π/2)=sinα，两项乘积为sin²α。", "sin(3π/2+α)=−cosα，cos(α−2π)=cosα；原式第二项前有减号，因此加cos²α。", "合并sin²α+cos²α=1。"]],
      [[("应用诱导公式", "四个因子符号均正确化简"), ("相乘并保留定义域", "得到−cos²α且指出分母要求sinα≠0")], [("化简第一项", "用周期、奇偶与互余关系得到sin²α"), ("化简第二项并注意外部负号", "得到加上的cos²α"), ("使用同角平方和", "结果为1")]],
      "①四个函数值分别为−cosα、sinα、−cosα、−sinα，连同分母相乘得−cos²α，且原式限sinα≠0。②第一乘积化为sin²α；第二个乘积是−(−cosα)(cosα)=cos²α，和为1。",
      "逐项复核诱导公式的象限符号、周期变换及第(1)问分母定义域。"),
    "bank:cmm:18202": reviewed("trigonometry", ["同角三角函数关系", "三角恒等变换"], ["利用平方和关系分组化简多角三角式"], 1,
      "按cos²β=1−sin²β分组，出现cos²β(sin²α+cos²α)+sin²β。", "fill_blank", "expression",
      ["化简sin²α+sin²β−sin²αsin²β+cos²αcos²β。"], ["1"],
      [["前三项写为sin²α(1−sin²β)+sin²β=sin²αcos²β+sin²β。", "加上cos²αcos²β，得cos²β(sin²α+cos²α)+sin²β=cos²β+sin²β=1。"]],
      [[("按平方和关系分组", "将1−sin²β化为cos²β"), ("再次使用平方和", "得到cos²β+sin²β=1")]],
      "表达式=cos²β(sin²α+cos²α)+sin²β=cos²β+sin²β=1。",
      "按同角平方和两次化简，核对交叉项符号。"),
})

# Five source-verified items for selective-1's probability distributions unit.
ITEMS.update({
    "bank:cmm:22029": reviewed("distributions_regression", ["二项分布", "期望与方差"], ["由二项分布的均值和方差反求参数"], 2,
      "将E(X)=np与D(X)=np(1−p)联立，利用两者比值求出p并核验n。", "single_choice", "choice",
      ["X~B(n,p)，若E(X)=5/4、D(X)=15/16，求p。"], ["A"],
      [["np=5/4且np(1−p)=15/16。两式相除得1−p=(15/16)/(5/4)=3/4，所以p=1/4。", "代回得n=5，满足参数条件，选择A。"]],
      [[("列出二项分布矩方程", "写出np=5/4及np(1−p)=15/16"), ("解出并检查参数", "得p=1/4、n=5并选A")]],
      "由np=5/4、np(1−p)=15/16，相除得1−p=3/4，故p=1/4；再得n=5，答案A。",
      "独立联立二项分布期望方差公式并验证n、p范围。"),
    "bank:cmm:22030": reviewed("distributions_regression", ["离散型随机变量分布列", "数学期望"], ["用概率归一化与期望方程求分布参数"], 1,
      "概率和为1给出a+b，期望条件给出另一线性方程，解唯一。", "single_choice", "choice",
      ["X取值−1,0,1,2的概率依次为0.2,a,b,0.3，且E(X)=0.8，求(a,b)。"], ["B"],
      [["概率总和为1得a+b=0.5。", "期望为−0.2+b+0.6=0.8，得b=0.4；于是a=0.1，选择B。"]],
      [[("建立概率和方程", "得a+b=0.5"), ("利用期望求参数", "得b=0.4、a=0.1并选B")]],
      "a+b=1−0.2−0.3=0.5。期望−0.2+b+0.6=0.8给b=0.4，所以a=0.1，选B。",
      "分别使用归一化条件和一阶矩条件求解，与原题选项B一致。"),
    "bank:cmm:22166": reviewed("distributions_regression", ["离散型随机变量分布列", "方差"], ["由概率和期望求未知概率", "计算离散随机变量方差"], 2,
      "两个约束唯一确定X=1与X=2的概率，随后按方差定义求值。", "single_choice", "choice",
      ["X取值0,1,2，P(X=0)=1/4且E(X)=1，求D(X)。"], ["C"],
      [["设P(X=1)=p、P(X=2)=q。p+q=3/4且p+2q=1，解得q=1/4、p=1/2。", "均值为1，故D(X)=1/4(0−1)²+1/2(1−1)²+1/4(2−1)²=1/2，选C。"]],
      [[("联立归一化和期望条件", "解得P(X=1)=1/2、P(X=2)=1/4"), ("按定义计算方差", "得到1/2并选C")]],
      "p+q=3/4、p+2q=1，解得q=1/4,p=1/2。围绕均值1计算方差为1/2，选C。",
      "检查概率归一化及均值，再独立按方差定义计算。"),
    "bank:cmm:22168": reviewed("distributions_regression", ["二项分布", "期望与方差"], ["由二项分布均值和方差求n、p"], 2,
      "由方差除以均值确定1−p，再使用np求n。", "single_choice", "choice",
      ["X~B(n,p)，期望为10、方差为8，求(n,p)。"], ["A"],
      [["np=10，np(1−p)=8，相除得1−p=0.8，故p=1/5。", "n=10/(1/5)=50，故选A。"]],
      [[("建立二项分布矩公式", "写出np=10及np(1−p)=8"), ("求解并匹配", "得到(50,1/5)对应A")]],
      "方差/期望=1−p=8/10=0.8，所以p=1/5，n=10/p=50，选A。",
      "以二项分布矩公式独立求得两参数并检查合理范围。"),
    "bank:cmm:22169": reviewed("distributions_regression", ["二项分布", "方差的线性变换"], ["计算二项分布方差", "利用D(aX+b)=a²D(X)"], 1,
      "二项分布方差为np(1−p)，平移不改变方差，乘2使方差乘4。", "single_choice", "choice",
      ["X~B(6,1/2)，求D(2X+1)。"], ["B"],
      [["D(X)=6·(1/2)·(1/2)=3/2。", "D(2X+1)=2²D(X)=6，选B。"]],
      [[("计算二项方差", "得到D(X)=3/2"), ("应用线性变换性质", "得到D(2X+1)=6并选B")]],
      "D(X)=np(1-p)=3/2，方差变换给D(2X+1)=4×3/2=6，选B。",
      "独立运用二项分布方差及线性变换性质，与来源答案一致。"),
})
for _qid in ("bank:cmm:22029", "bank:cmm:22030", "bank:cmm:22166", "bank:cmm:22168", "bank:cmm:22169"):
    _detail = ITEMS[_qid]
    _a = _detail["annotation"]
    _tags, _fine = _a["knowledge"]["primary"], _a["fine_types"]
    _prompt = _a["parts"][0]["prompt"]
    _steps = _a["parts"][0]["solution_steps"]
    _ans = _a["parts"][0]["reference_answer"]
    _detail["annotation"] = ann("single_choice", _tags, _fine, _a["difficulty"]["level"], _a["difficulty"]["basis"], "choice",
        [part("p1", _prompt, _ans, _steps, _tags, ["单项选择", "离散随机变量"],
            [crit("p1c1", "依据分布条件建立公式", "列式且计算正确"), crit("p1c2", "匹配原题选项", "选项与复算结果一致")])],
        accepted=[_ans], equivalence="exact")

# Selected AGIEval v1.1 math questions are normalized below while preserving
# their exact JSONL row in question.source_record and pinning the downloaded file.
AGIEVAL_MATH = {
    0: reviewed("sets_logic", ["集合的交集", "区间表示"], ["由集合条件求交集并匹配区间选项"], 1,
      "直接取同时满足x≥1与−1<x<2的实数；仅需比较区间端点。", "single_choice", "choice",
      ["求A={x|x≥1}与B={x|−1<x<2}的交集。"], ["D"],
      [["交集要求两个条件同时成立。", "结合x≥1及x<2得1≤x<2，对应D。"]],
      [[("求两个集合条件的共同解", "得1≤x<2"), ("匹配选项", "选择D")]],
      "交集为[1,2)，对应D。", "逐项读取完整题干和选项，按区间交集独立求得D。"),
    2: reviewed("plane_vectors", ["向量数量积", "充分必要条件"], ["判断数量积相等与向量相等之间的条件关系"], 2,
      "需分别验证必要性并构造非充分的反例。", "single_choice", "choice",
      ["非零向量a,b,c，判断a·c=b·c与a=b的条件关系。"], ["B"],
      [["若a=b，则对任意c都有a·c=b·c，故数量积相等是a=b的必要条件。", "反向不成立：取c=(1,0)、a=(0,0)、b=(0,1)，均为非零要求不满足a；改取a=(1,0),b=(1,1),c=(1,0)，三者均非零且数量积同为1，但a≠b。", "因此必要不充分，选B。"]],
      [[("证明必要性", "由a=b推出两边数量积相等"), ("验证非充分", "给出均非零且数量积相等但a≠b的反例"), ("确定选项", "必要不充分，对应B")]],
      "a=b必有a·c=b·c。反例取a=(1,0),b=(1,1),c=(1,0)，满足题设非零条件，数量积都为1而a≠b，故必要不充分，选B。", "独立验证两个方向并使用满足非零限制的反例。"),
    15: reviewed("complex_numbers", ["复数的几何表示", "复数乘法"], ["关于虚轴对称确定复数并计算乘积"], 2,
      "先由复平面关于虚轴的反射确定复数，再计算乘积。", "single_choice", "choice",
      ["点z₁=2+i关于虚轴对称的点对应z₂，求z₁z₂。"], ["A"],
      [["关于虚轴对称使实部变号、虚部不变，z₂=−2+i。", "(2+i)(−2+i)=−4+2i−2i+i²=−5，选A。"]],
      [[("确定对称点复数", "得z₂=−2+i"), ("完成复数乘法", "得乘积−5并匹配A")]],
      "虚轴反射将2+i变为−2+i，乘积为−5，选A。", "核对反射坐标规则及复数乘法。"),
    16: reviewed("plane_vectors", ["平面向量数量积", "向量模的平方"], ["由和差向量模平方之差求数量积"], 2,
      "使用恒等式|a+b|²−|a−b|²=4a·b反求数量积。", "single_choice", "choice",
      ["已知|a+b|=√10，|a−b|=√6，求a·b。"], ["A"],
      [["展开平方得|a+b|²−|a−b|²=4a·b。", "10−6=4a·b，故a·b=1，选A。"]],
      [[("列出模平方差恒等式", "正确得到4a·b"), ("代入求值", "得到1并选A")]],
      "4a·b=10−6=4，故a·b=1，选A。", "用坐标无关的模平方恒等式复算。"),
    18: reviewed("distributions_regression", ["条件概率", "随机事件概率"], ["由联合概率与边际概率求条件概率"], 2,
      "使用P(连续两天优)=P(次日优|今日优)P(今日优)求条件概率。", "single_choice", "choice",
      ["空气质量优的概率为0.75，连续两天均优的概率为0.60，求已知今日优时次日优的概率。"], ["A"],
      [["设G₁、G₂分别为两天空气质量优。条件概率P(G₂|G₁)=P(G₁∩G₂)/P(G₁)=0.60/0.75=0.8。", "对应选项A。"]],
      [[("列条件概率公式", "将联合概率除以今日优的概率"), ("计算并匹配", "得0.8，选A")]],
      "P(G₂|G₁)=0.60/0.75=0.8，选A。", "确认题目给的是连续两天均优的联合概率而非独立概率。"),
    29: reviewed("sequences", ["递推数列", "等比数列求和"], ["由一阶递推求首项公比及有限和"], 2,
      "递推关系化为等比数列，并用已知第二项反推首项。", "single_choice", "choice",
      ["数列满足3aₙ₊₁+aₙ=0且a₂=−4/3，求前10项和。"], ["C"],
      [["aₙ₊₁=−aₙ/3，公比q=−1/3。由a₂=a₁q=−4/3得a₁=4。", "S₁₀=4[1−(−1/3)¹⁰]/[1−(−1/3)]=3(1−3⁻¹⁰)，选C。"]],
      [[("识别递推公比并求首项", "得到q=−1/3、a₁=4"), ("应用等比数列求和", "得到3(1−3⁻¹⁰)并选C")]],
      "公比−1/3、首项4，S₁₀=3(1−3⁻¹⁰)，选C。", "代回a₂核验首项，并按等比求和式计算。"),
    38: reviewed("plane_vectors", ["平面向量数量积", "向量夹角"], ["由两向量坐标求夹角"], 2,
      "两向量均为单位向量，点积直接给出夹角余弦。", "single_choice", "choice",
      ["向量BA=(1/2,√3/2)、BC=(√3/2,1/2)，求∠ABC。"], ["A"],
      [["两向量模均为1，BA·BC=√3/4+√3/4=√3/2。", "因此cos∠ABC=√3/2，夹角为30°，选A。"]],
      [[("计算向量模与数量积", "模均为1且数量积√3/2"), ("由余弦值求角", "得30°并选A")]],
      "数量积为√3/2且两向量均为单位向量，夹角30°，选A。", "按顶点B对应的两条向量BA、BC计算夹角。"),
    87: reviewed("conics", ["双曲线标准方程", "渐近线与焦点"], ["由双曲线参数求焦点到渐近线距离"], 3,
      "需标准化方程求a²、b²、焦距及渐近线，再用点线距离公式。", "single_choice", "choice",
      ["双曲线x²−my²=3m（m>0），求右焦点到一条渐近线的距离。"], ["A"],
      [["化为x²/(3m)−y²/3=1，故a²=3m、b²=3、c²=3m+3，右焦点为(√(3m+3),0)。", "渐近线为y=±x/√m，即x∓√m y=0。点到直线距离为√(3m+3)/√(1+m)=√3。", "故选A。"]],
      [[("标准化并求焦点", "得到焦点横坐标√(3m+3)"), ("写出渐近线", "斜率为±1/√m"), ("计算点线距离", "化简为√3并选A")]],
      "a²=3m,b²=3,c²=3m+3。对渐近线x−√m y=0，距离为√(3m+3)/√(1+m)=√3，选A。", "独立化标准方程、求焦点与渐近线并验证距离与m无关。"),
    104: reviewed("counting_binomial", ["排列组合", "古典概型"], ["相邻限制下的组合计数与概率"], 2,
      "以两个0的位置作为等可能位置组合计数，并用插空法计有利位置。", "single_choice", "choice",
      ["将4个1和2个0随机排列，求两个0不相邻的概率。"], ["C"],
      [["把6个位置中选2个放置0，共C(6,2)=15种等可能位置。", "4个1形成5个空隙，选其中2个放0有C(5,2)=10种。", "概率为10/15=2/3，选C。"]],
      [[("计算总位置数", "得C(6,2)=15"), ("插空计有利位置", "得C(5,2)=10"), ("求概率", "化简为2/3并选C")]],
      "总数C(6,2)=15；4个1的5个间隙中选2个放0，有C(5,2)=10种，概率2/3，选C。", "按题意将相同数字的位置组合视为等可能，并确保0分置不同间隙。"),
    107: reviewed("complex_numbers", ["复数四则运算", "复数乘方"], ["先化简复数商再求平方"], 2,
      "需正确乘共轭化分母并完成复数平方。", "single_choice", "choice",
      ["计算[(3−i)/(1+i)]²。"], ["A"],
      [["(3−i)/(1+i)=(3−i)(1−i)/2=(2−4i)/2=1−2i。", "(1−2i)²=1−4i−4=−3−4i，选A。"]],
      [[("有理化复数商", "化为1−2i"), ("平方并整理", "得到−3−4i，选A")]],
      "复数商为1−2i，平方为−3−4i，选A。", "对分母乘共轭并复核虚部符号。"),
    161: reviewed("counting_binomial", ["二项式定理", "组合数性质"], ["利用相邻组合数比值解整数参数"], 2,
      "用C(2m+1,m)/C(2m,m)的精确比值建立方程。", "single_choice", "choice",
      ["已知13C(2m,m)=7C(2m+1,m)，求正整数m。"], ["B"],
      [["相邻组合数比值C(2m+1,m)/C(2m,m)=(2m+1)/(m+1)。", "13=7(2m+1)/(m+1)，故13m+13=14m+7，m=6，选B。"]],
      [[("写出相邻组合数比值", "得到(2m+1)/(m+1)"), ("解方程", "得m=6并选B")]],
      "比值为(2m+1)/(m+1)，解13=7(2m+1)/(m+1)得m=6，选B。", "用阶乘约分核验组合数比值，并验证m为正整数。"),
    196: reviewed("plane_vectors", ["平面向量数量积", "向量模的平方"], ["由线性组合模长方程求数量积"], 2,
      "将模平方展开为数量积方程并代入已知模长。", "single_choice", "choice",
      ["|a|=1、|b|=√3且|a−2b|=3，求a·b。"], ["C"],
      [["|a−2b|²=|a|²−4a·b+4|b|²。", "9=1−4a·b+12，故a·b=1，选项C。"]],
      [[("展开模平方", "建立9=1−4a·b+12"), ("解数量积", "得a·b=1并匹配C")]],
      "9=1−4a·b+12，故a·b=1，对应C。", "逐项将向量模平方展开，符号与系数均复算。"),
    19: reviewed("derivatives", ["导数的几何意义", "曲线切线"], ["由切线斜率确定参数"], 1,
      "在x=0处计算导数并与切线斜率比较。", "single_choice", "choice",
      ["曲线y=ax−ln(x+1)在(0,0)处的切线为y=2x，求a。"], ["D"],
      [["y'=a−1/(x+1)，故y'(0)=a−1。", "切线斜率为2，所以a−1=2，a=3，选D。"]],
      [[("求导并代入", "得斜率a−1"), ("匹配切线斜率", "解得a=3并选D")]],
      "f'(0)=a−1=2，故a=3，选D。", "逐项求导并用给定切点、切线斜率核对。"),
    46: reviewed("probability", ["数学建模", "不等式约束与整数决策"], ["将订单积压与服务能力建模并求最少人员数"], 2,
      "先把95%服务水平转成不超过1600份新订单时的完成约束，再建立整数人员容量不等式。", "single_choice", "choice",
      ["日常配货能力1200份，积压500份；次日新订单超过1600份的概率为0.05。每名志愿者每天配货50份，为使完成积压与次日订单的概率不低于0.95，至少需要多少人？"], ["B"],
      [["新订单不超过1600份的概率为0.95。为确保该事件发生时完成全部订单，需要总能力至少500+1600=2100份。", "若有n名志愿者，总能力为1200+50n。要求1200+50n≥2100，得n≥18。", "人数取满足条件的最小整数18，选B。"]],
      [[("将目标服务概率转成需求阈值", "采用0.95概率对应的新订单上界1600"), ("建立能力约束", "1200+50n≥500+1600"), ("求最小整数解", "n=18并选B")]],
      "需求不超过1600的概率是0.95。该情况下日能力需≥500+1600=2100，解1200+50n≥2100得最小整数n=18，选B。", "把概率阈值、积压量和每日产能转换为清晰的不等式并核验边界取等。"),
    70: reviewed("counting_binomial", ["组合计数", "古典概型"], ["用对立事件计含男女的三人选法概率"], 1,
      "从所有等可能组合中减去全男和全女两类不利情况。", "single_choice", "choice",
      ["20名男生、10名女生中任选3人，求选出的同学既有男生又有女生的概率。"], ["D"],
      [["总选法C(30,3)=4060。", "不利选法C(20,3)+C(10,3)=1140+120=1260。", "所求概率=(4060−1260)/4060=20/29，选D。"]],
      [[("计总组合数", "C(30,3)=4060"), ("计两类不利组合", "合计1260"), ("求概率", "化简为20/29并选D")]],
      "概率=[C(30,3)−C(20,3)−C(10,3)]/C(30,3)=20/29，选D。", "核对样本空间及两个互斥不利事件后独立约分。"),
    76: reviewed("solid_geometry", ["球的截面", "空间垂直平面"], ["由球内公共弦求垂直截面圆心距"], 2,
      "公共弦是两截平面的交线在球内的弦；先求球心到交线距离。", "single_choice", "choice",
      ["半径2的球被两个互相垂直的平面截得两圆，公共弦长2，求两圆圆心距。"], ["C"],
      [["设两平面交线为L。公共弦半长1，球心到L距离d满足1²+d²=2²，故d=√3。", "取L为z轴、球心(p,q,r)，两截面圆心为(0,q,r)和(p,0,r)，圆心距√(p²+q²)=d=√3。", "故选C。"]],
      [[("由公共弦求球心到交线距离", "得√3"), ("表达两个截面圆心", "证明其间距为球心到交线距离"), ("匹配选项", "选C")]],
      "设交线为z轴，半弦1给p²+q²=4−1=3；两截面圆心距为√(p²+q²)=√3，选C。", "用坐标说明垂直平面下两截面圆心距的几何关系。"),
    298: reviewed("lines_circles", ["圆的方程", "直线与圆交点"], ["由三点确定圆并求其与y轴弦长"], 2,
      "先由三点求圆心、半径，再与y轴联立求弦长。", "single_choice", "choice",
      ["过A(1,3)、B(4,2)、C(1,−7)的圆与y轴交于M、N，求MN。"], ["C"],
      [["AC的垂直平分线为y=−2，圆心设为(h,−2)。", "由到A、B距离相等，(h−1)²+25=(h−4)²+16，解得h=1，半径为5。", "圆方程为(x−1)²+(y+2)²=25。令x=0得(y+2)²=24，故MN=2√24=4√6，选C。"]],
      [[("用弦AC确定圆心纵坐标", "得y=−2"), ("等距条件求横坐标和半径", "得圆心(1,−2)、半径5"), ("联立y轴并求弦长", "4√6并选C")]],
      "圆心(1,−2)、半径5，y轴交点满足(y+2)²=24，弦长4√6，选C。", "独立由三点确定圆并核算两交点距离。"),
    303: reviewed("conics", ["抛物线标准方程", "焦半径"], ["由点到焦点距离及横坐标求参数"], 1,
      "利用焦点坐标和抛物线定义建立一元方程。", "single_choice", "choice",
      ["A在抛物线y²=2px (p>0)上，横坐标为9且到焦点距离为12，求p。"], ["C"],
      [["抛物线焦点为(p/2,0)，准线为x=−p/2。点A到焦点距离等于到准线距离，即9+p/2。", "9+p/2=12，解得p=6，选C。"]],
      [[("写出焦点、准线", "p/2及x=−p/2"), ("应用抛物线定义", "列出9+p/2=12"), ("解参并匹配", "p=6，选C")]],
      "焦半径=到准线距离=9+p/2=12，故p=6，选C。", "通过抛物线定义独立复算距离关系。"),
    329: reviewed("lines_circles", ["圆的几何性质", "圆心轨迹"], ["经过定点的定半径圆心的最短距离"], 1,
      "圆心到固定点的距离为1，使用反三角不等式并验证等号可达。", "single_choice", "choice",
      ["半径为1的圆经过(3,4)，求圆心到原点距离的最小值。"], ["A"],
      [["固定点P到原点距离OP=5，圆心O'满足O'P=1。", "OO'≥OP−O'P=4；令O'在射线OP上且距P为1即可取等，最小值4，选A。"]],
      [[("求OP", "得到5"), ("求最短圆心距并验证可达", "得4并选A")]],
      "OP=5，圆心在以P为圆心、半径1的圆上，离原点最近为5−1=4，选A。", "给出下界并指出沿OP方向可取到等号。"),
    340: reviewed("distributions_regression", ["二项分布", "期望与方差"], ["由二项方差及概率质量比较确定成功概率"], 2,
      "方差方程给出两个候选，再由二项概率比不等式选出参数。", "single_choice", "choice",
      ["X~B(10,p)，D(X)=2.4且P(X=4)<P(X=6)，求p。"], ["B"],
      [["10p(1−p)=2.4，得p=0.4或0.6。", "P(X=6)/P(X=4)=[p/(1−p)]²；该比值大于1要求p>1/2。", "因此p=0.6，选B。"]],
      [[("用方差确定候选", "得0.4或0.6"), ("用概率质量比较筛选", "推出p>1/2"), ("给出参数", "p=0.6并选B")]],
      "方差给p=0.4或0.6，P6/P4=[p/(1−p)]²>1只在p>1/2成立，故p=0.6，选B。", "用相邻二项概率精确约分，检查严格不等号方向。"),
    346: reviewed("probability", ["几何概型", "均匀随机到达"], ["用满足等待时间约束的区间长度求概率"], 1,
      "有利到达时段的总长度除以均匀样本空间总长度。", "single_choice", "choice",
      ["班车7:00、8:00、8:30发车；乘客均匀随机于7:50至8:30到达，等车不超过10分钟的概率是多少？"], ["B"],
      [["总到达时间段长40分钟。", "7:50至8:00到达可等到8:00；8:20至8:30到达可等到8:30。两段各长10分钟。", "概率=(10+10)/40=1/2，选B。"]],
      [[("确定总样本区间", "长40分钟"), ("确定有利区间", "两段共20分钟"), ("计算概率", "1/2并选B")]],
      "有利时段总长20分钟，样本时段长40分钟，概率1/2，选B。", "将到达时刻视为连续均匀分布，并逐段核验等候时间。"),
    348: reviewed("conics", ["抛物线定义", "弦长与焦参数"], ["用抛物线弦和准线截圆弦长确定焦参数"], 3,
      "分别对抛物线交点弦、准线交圆弦建立长度关系再联立。", "single_choice", "choice",
      ["以抛物线顶点为圆心的圆交抛物线于A、B，交准线于D、E；AB=4√2、DE=2√5，求焦点到准线距离。"], ["B"],
      [["设抛物线y²=4ax (a>0)，圆心为原点、半径R，焦点到准线距离为2a。AB长4√2，抛物线交点为(2/a,±2√2)，故R²=4/a²+8。", "准线x=−a与圆相交的弦DE长2√5，故R²−a²=5。联立得a⁴−3a²−4=0。", "令t=a²>0，(t−4)(t+1)=0，故a=2，焦点到准线距离2a=4，选B。"]],
      [[("设定焦参数和圆半径", "明确2a为所求距离"), ("用AB条件列半径", "得R²=4/a²+8"), ("用DE条件联立", "得a=2，所求4并选B")]],
      "AB给R²=4/a²+8，DE给R²−a²=5；解a⁴−3a²−4=0得正值a=2，焦点到准线距离4，选B。", "独立建立坐标模型，验证抛物线交点、圆弦及唯一正参数。"),
}
for _idx, _item in AGIEVAL_MATH.items():
    ITEMS[f"bank:agieval-gaokao-mathqa:{_idx}"] = _item

# Final targeted additions for the remaining curriculum-unit placements.
ITEMS.update({
    "bank:cmm:14731": reviewed("exponential_logarithmic", ["指数函数定义", "指数函数参数"], ["利用指数函数系数和底数条件确定参数"], 1,
      "先令指数函数的常数系数为1，再同时检查底数正且不等于1；仅需解一元二次方程并排除非法底数。", "single_choice", "choice",
      ["函数y=(a²−4a+4)aˣ是指数函数，求a。"], ["C"],
      [["指数函数必须写成y=c·bˣ且c=1、b>0、b≠1。", "(a−2)²=1，得a=1或3；a=1时底数为1，不符合指数函数定义，故a=3。"]],
      [[("使用指数函数定义", "令系数(a−2)²=1并要求底数a>0且a≠1"), ("求根并筛选", "候选1、3中排除1，保留3")]],
      "系数(a−2)²须为1，故a=1或3；指数底数不能为1，答案a=3。", "题目选项、定义条件和方程根逐项核查；答案C对应3。"),
    "bank:cmm:16766": reviewed("probability", ["古典概型", "对立事件"], ["用对立事件求抽球至少一个白球概率"], 1,
      "样本空间为等可能的五球三取组合，利用唯一的全红组合求补事件概率。", "single_choice", "choice",
      ["从3个红球、2个白球中任取3个，至少有1个白球的概率是多少？"], ["D"],
      [["总取法数为C(5,3)=10。", "没有白球只有一种取法，即取走全部3个红球，所以补事件概率为1/10。", "所求概率为1−1/10=9/10，选D。"]],
      [[("确定等可能样本空间", "总数C(5,3)=10"), ("计算对立事件", "全红只有1种"), ("取补", "概率9/10，选D")]],
      "十种三球组合等可能，其中仅一组全红；至少一白的概率为1−1/10=9/10。", "组合计数与来源逐项列出的10种结果一致，答案D。"),
    "bank:cmm:17039": reviewed("probability", ["互斥事件", "对立事件"], ["通过样本空间判别互斥与对立事件"], 2,
      "在四个等可能球对事件中分别判断交集是否为空，再检查并集是否覆盖样本空间。", "single_choice", "choice",
      ["从两个白球、两个黄球中任取2个。题干给出四组事件，问其中互斥而不对立的事件组数。"], ["A"],
      [["样本空间按颜色可分为WW、WY、YY三类。", "(1)至少一白与至少一黄交于WY，非互斥；(2)至少一黄包含全黄，非互斥；(3)恰一白与恰一黄是同一事件，非互斥。", "(4)至少一黄与全白互斥，但两事件并集覆盖全部结果，故互为对立。没有互斥而不对立的一组，答案0组(A)。"]],
      [[("列出颜色样本类型", "WW、WY、YY"), ("逐组检验交集", "前三组交集非空"), ("区分互斥与对立", "第四组互斥且并集为全空间"), ("计数", "互斥不对立共0组")]],
      "(1)(2)有交集，(3)为同事件，(4)互斥且互补；因此互斥但不对立的组数是0。", "用颜色类型穷举核对四组关系，避免把互斥与对立混为一谈。"),
    "bank:cmm:19368": reviewed("complex_numbers", ["复数共轭", "复数模"], ["由共轭方程求复数并计算模"], 1,
      "有理化求出共轭复数，取共轭得z，再由实部和虚部求模。", "single_choice", "choice",
      ["若复数z满足z̄(1−i)=2i，求|z|。"], ["A"],
      [["z̄=2i/(1−i)=2i(1+i)/2=−1+i。", "所以z=−1−i，|z|=√(1+1)=√2，选A。"]],
      [[("求共轭数", "有理化得z̄=−1+i"), ("还原z并求模", "z=−1−i且模√2")]],
      "z̄=−1+i，故z=−1−i，模为√2，选A。", "直接复数运算与题源解析独立一致。"),
    "bank:cmm:16439": reviewed("solid_geometry", ["空间直线与平面垂直", "异面直线"], ["判断含给定直线的垂面存在性与唯一性"], 2,
      "若异面直线m,n互相垂直，则过n上任一点有唯一垂直于m的平面且该平面包含n；若不垂直则不存在。", "single_choice", "choice",
      ["m、n为异面直线，过n且与m垂直的平面有何种数量？"], ["B"],
      [["若m⊥n，则过n上任一点作唯一垂直于m的平面；因n的方向垂直m，该平面可包含n，满足条件。", "若m不垂直n，则任何包含n的平面都含有n方向，法向量不可能平行于m，故不存在。", "可能一个或零个，因此至多一个，选B。"]],
      [[("分垂直与不垂直讨论", "涵盖m⊥n及m不垂直n"), ("判断存在数量", "分别为唯一一个和不存在"), ("选取正确概括", "至多一个")]],
      "m⊥n时恰有一个这样的平面；否则不存在，故数量至多一个，选B。", "按两异面直线是否垂直分情形，和来源解答一致。"),
    "bank:cmm:22451": reviewed("distributions_regression", ["离散型随机变量", "分布列", "数学期望"], ["由概率和为1补齐分布列后计算期望"], 1,
      "先用概率总和确定m，再按定义对三个取值求加权平均。", "single_choice", "choice",
      ["随机变量X取0,1,2,3的概率依次为8/27,4/9,m,1/27，求E(X)。"], ["B"],
      [["概率和为1，故m=1−8/27−12/27−1/27=6/27=2/9。", "E(X)=0·8/27+1·4/9+2·2/9+3·1/27=12/27+12/27+3/27=1，选B。"]],
      [[("补齐概率", "得m=2/9且概率和为1"), ("按定义求期望", "加权和为1")]],
      "m=2/9，期望为4/9+4/9+1/9=1，选B。", "用概率总和和离散期望定义独立复算，来源表格与选项清晰。"),
    "bank:cmm:22484": reviewed("distributions_regression", ["独立性检验", "回归直线", "中位数"], ["综合判断卡方检验、回归线性质及偶数个数据中位数"], 2,
      "三个判断分别依据卡方检验统计量、回归线过样本中心的性质及排序后取中间两数平均。", "single_choice", "choice",
      ["判断关于卡方观测值、回归直线及数据2,1,3,2,3,3的三个命题真值个数。"], ["D"],
      [["(1)独立性检验中观测统计量越大，越倾向拒绝独立性、认为有关，真。", "(2)含截距的最小二乘回归线过样本中心；可以不经过任一实际样本点，真。", "(3)排序为1,2,2,3,3,3，中位数=(2+3)/2=5/2，真。", "共有3个真命题，选D。"]],
      [[("判断卡方结论", "统计量增大对应更强关联证据"), ("判断回归线性质", "经过样本中心但不必经过样本观测"), ("计算中位数", "排序后中间值为2和3"), ("统计真命题", "共3个")]],
      "三条均为真：卡方值增大增强关联证据，回归线过样本中心，中位数为5/2，故3个，选D。", "分别依据定义和性质复核，题干数据及选项完整。"),
    "bank:cmm:16732": reviewed("distributions_regression", ["线性相关", "回归直线", "样本中心"], ["用正相关斜率和样本中心筛选线性回归方程"], 1,
      "正相关要求回归斜率为正；最小二乘回归线还须经过样本均值点。", "single_choice", "choice",
      ["变量x、y正相关，样本均值为x̄=3、ȳ=3.5，哪条线性回归方程可能成立？"], ["A"],
      [["正相关要求斜率为正，排除斜率为负的C、D。", "回归线须经过(3,3.5)：A给0.4·3+2.3=3.5；B给2·3−2.4=3.6，不经过均值点。故选A。"]],
      [[("利用相关方向", "只保留正斜率选项"), ("代入样本中心", "A满足、B不满足"), ("选出可能方程", "选择A")]],
      "正相关需正斜率；回归线过(3,3.5)。A代入得3.5，B得3.6，故A。", "复核斜率符号和回归线必过样本中心两项条件，原四个选项完整。"),
    "bank:agieval-gaokao-mathqa:8": reviewed("sequences", ["等差数列", "前n项和"], ["通过前项和关系求公差及指定项"], 2,
      "将等差数列的前n项和代入题给关系确定d，再求第五项。", "single_choice", "choice",
      ["等差数列前n项和为S_n，若3S_3=S_2+S_4且a_1=2，求a_5。"], ["B"],
      [["设公差为d，则S_2=4+d，S_3=6+3d，S_4=8+6d。", "代入得18+9d=12+7d，故d=−3。", "a_5=2+4d=−10，选B。"]],
      [[("列出相关前项和", "三式分别正确"), ("解公差", "由关系得d=−3"), ("求第五项", "a5=−10")]],
      "3(6+3d)=(4+d)+(8+6d)，解得d=−3，a5=2+4d=−10。", "逐项代入等差数列求和公式，答案B。"),
    "bank:agieval-gaokao-mathqa:345": reviewed("sequences", ["等差数列", "前n项和", "通项"], ["联立项和及单项条件求高项"], 2,
      "前九项和提供首项与公差的线性关系，结合第十项确定通项。", "single_choice", "choice",
      ["等差数列前9项和为27且a_10=8，求a_100。"], ["C"],
      [["S_9=9(a_1+a_9)/2=9(a_1+4d)=27，故a_1+4d=3。", "a_10=a_1+9d=8，两式相减得5d=5，d=1，a_1=−1。", "a_100=−1+99=98，选C。"]],
      [[("使用前九项和", "得到a1+4d=3"), ("结合第十项", "求出d=1、a1=−1"), ("求百项", "得98")]],
      "a1+4d=3且a1+9d=8，所以d=1、a1=−1，a100=98。", "独立联立两条条件后代回通项检验，答案C。"),
    "bank:agieval-gaokao-mathqa:304": reviewed("derivatives", ["导数", "曲线切线"], ["计算导函数并写出指定点切线方程"], 1,
      "多项式求导后代入x=1取得斜率，结合点斜式即可。", "single_choice", "choice",
      ["f(x)=x⁴−2x³的图象在(1,f(1))处的切线方程是什么？"], ["B"],
      [["f(1)=−1，f'(x)=4x³−6x²，故f'(1)=−2。", "点斜式y+1=−2(x−1)，化为y=−2x+1，选B。"]],
      [[("求切点与导数值", "得到(1,−1)及斜率−2"), ("写切线方程", "化简得到y=−2x+1")]],
      "切点(1,−1)，斜率f'(1)=−2，切线为y+1=−2(x−1)，即y=−2x+1。", "直接求导和点斜式计算，选项B。"),
    "bank:agieval-gaokao-mathqa:235": reviewed("lines_circles", ["圆的对称轴", "圆心到直线距离"], ["圆的对称轴经过圆心，用直线代入确定参数"], 1,
      "圆的任一对称轴经过圆心(a,0)，因此圆心满足给定直线方程。", "single_choice", "choice",
      ["直线2x+y−1=0是圆(x−a)²+y²=1的一条对称轴，求a。"], ["A"],
      [["圆心为(a,0)，圆的对称轴必须经过圆心。", "代入直线方程得2a−1=0，所以a=1/2，选A。"]],
      [[("识别圆心", "圆心坐标(a,0)"), ("利用轴过圆心", "解得a=1/2")]],
      "对称轴经过圆心(a,0)，故2a−1=0，a=1/2。", "使用圆的对称性直接核算，选项A。"),
})

QUESTION_GOAL.update({
    "bank:cmm:14731": "math-senior-compulsory-1:u3:g1",
    "bank:cmm:16766": "math-senior-compulsory-1:u7:g2",
    "bank:cmm:17039": "math-senior-compulsory-1:u7:g2",
    "bank:cmm:19368": "math-senior-compulsory-2:u5:g2",
    "bank:cmm:16439": "math-senior-compulsory-2:u6:g2",
    "bank:cmm:22451": "math-senior-selective-1:u6:g2",
    "bank:cmm:16732": "math-senior-selective-1:u7:g2",
    "bank:cmm:22484": "math-senior-selective-1:u7:g2",
    "bank:agieval-gaokao-mathqa:8": "math-senior-selective-2:u1:g2",
    "bank:agieval-gaokao-mathqa:345": "math-senior-selective-2:u1:g2",
    "bank:agieval-gaokao-mathqa:304": "math-senior-selective-2:u2:g2",
    "bank:agieval-gaokao-mathqa:235": "math-senior-selective-1:u1:g1",
})

ITEMS.update({
    "bank:cmm:21303": reviewed("spatial_vectors", ["空间向量", "向量垂直与直线夹角"], ["由方向向量数量积判断两直线夹角"], 1,
      "计算两个非零方向向量的数量积为零，即方向垂直；题目问直线夹角类别。", "single_choice", "choice",
      ["直线a、b的方向向量分别为e=(1,−2,−2)、n=(−2,−3,2)，判断位置关系。"], ["C"],
      [["e·n=1·(−2)+(−2)·(−3)+(−2)·2=−2+6−4=0。", "方向向量均非零且相互垂直，因此两直线方向垂直，选C。"]],
      [[("计算数量积", "正确得到0"), ("解释几何意义", "非零方向向量垂直，故选C")]],
      "e·n=0，两向量都是非零方向向量，故直线方向垂直，选C。", "题干及四项完整；独立计算点积，并确认两向量非零。"),
    "bank:cmm:21317": reviewed("spatial_vectors", ["空间向量", "平面法向量"], ["由三点确定平面并验证给定方向为法向量"], 2,
      "需检查给定向量与平面内两条相交方向向量均垂直。", "single_choice", "choice",
      ["A(1,0,0)、B(0,1,0)、C(0,0,1)，判断方向向量(1,1,1)的直线与平面ABC的位置关系。"], ["A"],
      [["平面内AB=(−1,1,0)，AC=(−1,0,1)，两者相交于A且不共线。", "(1,1,1)·AB=−1+1=0，(1,1,1)·AC=−1+1=0。", "因此给定方向垂直于平面ABC，直线与平面垂直，选A。"]],
      [[("构造平面内两方向向量", "正确写出AB、AC"), ("验证数量积", "两个点积均为0"), ("推出直线面垂直", "选A")]],
      "AB=(−1,1,0)、AC=(−1,0,1)，给定向量与二者点积均为0，故为平面法向量方向，直线垂直平面，选A。", "独立计算两个点积并用两条相交平面内直线判定。"),
    "bank:cmm:21321": reviewed("spatial_vectors", ["空间向量", "平面位置关系"], ["利用法向量数量积判断两平面垂直"], 1,
      "法向量非零且垂直时对应两平面垂直。", "single_choice", "choice",
      ["两平面法向量分别为a=(2,4,−3)、b=(−1,2,2)，判断平面位置关系。"], ["B"],
      [["a·b=2(−1)+4·2+(−3)2=−2+8−6=0。", "两平面法向量垂直，故两平面垂直，选B。"]],
      [[("计算法向量点积", "结果为0"), ("对应平面关系", "平面垂直，选B")]],
      "点积为−2+8−6=0，因此法向量互相垂直，平面垂直，选B。", "核对全部分量及乘积符号后依据法向量判定平面垂直。"),
    "bank:cmm:21322": reviewed("spatial_vectors", ["空间向量", "平面位置关系"], ["由两个平面的法向量垂直判断平面垂直"], 1,
      "两个非零法向量点积为0即可确定两平面垂直。", "single_choice", "choice",
      ["平面α、β的法向量分别为(1,2,0)、(2,−1,0)，判断两平面关系。"], ["C"],
      [["(1,2,0)·(2,−1,0)=2−2+0=0。", "两平面法向量垂直，故α⊥β，选C。"]],
      [[("计算法向量点积", "得到0"), ("推出平面垂直", "选C")]],
      "法向量点积2−2=0，所以两平面垂直，选C。", "独立核算点积并匹配原题选项。"),
    "bank:cmm:21002": reviewed("spatial_vectors", ["空间向量", "向量垂直"], ["用方向向量数量积判断直线垂直"], 1,
      "分别计算l₁与另外两条直线方向向量的点积，再核对唯一成立的垂直关系。", "single_choice", "choice",
      ["三条直线方向向量a=(4,−1,0)、b=(1,4,5)、c=(−3,12,−9)，选择正确的位置关系判断。"], ["A"],
      [["a·b=4−4+0=0，所以l₁⊥l₂。", "a·c=−12−12+0=−24≠0，所以l₁与l₃不垂直。", "符合A。"]],
      [[("计算第一组点积", "a·b=0"), ("排除第二种垂直关系", "a·c≠0"), ("匹配选项", "选择A")]],
      "a·b=0而a·c=−24，只有l₁⊥l₂，l₁不垂直l₃，选A。", "原题题干和选项齐全；来源解析为空，独立逐项计算方向向量点积。"),
    "bank:cmm:21003": reviewed("spatial_vectors", ["空间向量", "向量模与垂直"], ["由模长条件解参数并用垂直条件求和"], 2,
      "模长给出参数平方的两个分支，点积条件逐支确定y并计算x+y。", "single_choice", "choice",
      ["a=(2,4,x)、b=(2,y,2)，|a|=6且a⊥b，求x+y。"], ["A"],
      [["|a|²=4+16+x²=36，故x²=16，x=±4。", "a·b=4+4y+2x=0，即y=−1−x/2。", "x=4时y=−3，x+y=1；x=−4时y=1，x+y=−3，故选A。"]],
      [[("使用模长条件", "得到x=±4"), ("使用垂直条件", "得到y=−1−x/2"), ("枚举分支并匹配", "x+y为1或−3，选A")]],
      "x²=16，x=4时y=−3、和为1；x=−4时y=1、和为−3，选A。", "独立分解模长二次方程的两种可能，并分别代入点积条件。"),
    "bank:cmm:21004": reviewed("spatial_vectors", ["空间向量", "平面位置关系"], ["由平面法向量点积判断平面垂直"], 1,
      "法向量点积为零，直接得到两平面的垂直关系。", "single_choice", "choice",
      ["平面α、β的法向量u=(−2,2,5)、v=(6,−4,4)，判断两平面关系。"], ["B"],
      [["u·v=(−2)·6+2·(−4)+5·4=−12−8+20=0。", "故两平面法向量垂直，平面α与β垂直，选B。"]],
      [[("计算法向量点积", "得0"), ("解释平面关系", "两平面垂直，选B")]],
      "u·v=−12−8+20=0，故平面α、β垂直，选B。", "独立计算法向量点积并比对完整选项。"),
    "bank:cmm:21005": reviewed("spatial_vectors", ["空间直角坐标系", "点到坐标轴与坐标平面的距离"], ["求点在坐标平面的射影及其到原点距离"], 1,
      "投影到yOz平面令x坐标为零，再用三维距离公式。", "single_choice", "choice",
      ["A(1,2,3)在yOz平面的射影为B，求|OB|。"], ["B"],
      [["投影到yOz平面将x坐标改为0，故B=(0,2,3)。", "|OB|=√(0²+2²+3²)=√13，选B。"]],
      [[("确定正射影坐标", "B=(0,2,3)"), ("计算到原点距离", "√13并选B")]],
      "B=(0,2,3)，所以|OB|=√13，选B。", "按坐标平面定义求正射影，再独立计算欧氏距离。"),
    "bank:cmm:21282": reviewed("spatial_vectors", ["空间直角坐标系", "对称与两点距离"], ["关于坐标平面和坐标轴对称的坐标变换"], 1,
      "依次改变相应坐标符号，再用距离公式计算。", "single_choice", "choice",
      ["A(1,−2,3)关于xOz平面的对称点为B，关于x轴的对称点为C，求BC。"], ["B"],
      [["关于xOz平面反射只改变y坐标的符号，B=(1,2,3)。", "关于x轴旋转半周保持x不变并改变y、z符号，C=(1,2,−3)。", "BC=√((1−1)²+(2−2)²+(3−(−3))²)=6，选B。"]],
      [[("求两个对称点坐标", "B=(1,2,3)，C=(1,2,−3)"), ("应用空间距离公式", "得6并选B")]],
      "B=(1,2,3)，C=(1,2,−3)，二者距离6，选B。", "分别核对平面反射和x轴对称的坐标变化，再计算距离。"),
    "bank:cmm:20250": reviewed("functions", ["二次函数", "闭区间值域"], ["由顶点与区间端点求二次函数值域"], 1,
      "抛物线开口向上，顶点横坐标在闭区间内；最小值取顶点，最大值比较端点。", "single_choice", "choice",
      ["x∈[0,5]时，f(x)=3x²−4x+c，选择其值域。"], ["C"],
      [["f'(x)=6x−4，在x=2/3处为0；二次项系数正，故该点为区间内最小值点。", "比较端点值f(0)=c与f(5)=75−20+c=55+c，最大值为f(5)。", "值域为[f(2/3),f(5)]，选C。"]],
      [[("确定顶点和最小值", "顶点横坐标2/3且在区间内"), ("比较端点求最大值", "f(5)>f(0)"), ("写值域并匹配", "选C")]],
      "顶点x=2/3给最小值；端点比较f(5)=55+c>f(0)=c，值域[f(2/3),f(5)]，选C。", "独立验证顶点位于区间内部并比较两个端点值。"),
    "bank:cmm:16561": reviewed("statistics", ["频数与频率", "样本统计"], ["由频率和样本容量求组频数"], 1,
      "频数=频率×样本容量的直接计算。", "single_choice", "choice",
      ["样本容量为100，某组频率为0.3，求该组频数。"], ["C"],
      [["频数=0.3×100=30，选C。"]],
      [[("应用频数频率关系", "0.3乘以100"), ("给出整数频数", "30并选C")]],
      "频数为100×0.3=30，选C。", "直接复算频率与频数定义。"),
    "bank:cmm:22330": reviewed("statistics", ["标准差", "数据线性变换"], ["计算数据乘常数并平移后的标准差"], 1,
      "加常数不改变标准差，乘2使标准差乘|2|。", "single_choice", "choice",
      ["样本x₁,…,x₁₀的标准差为8，求数据2x₁−1,…,2x₁₀−1的标准差。"], ["C"],
      [["对所有数据加−1不改变标准差。", "所有数据乘2，标准差变为|2|×8=16，选C。"]],
      [[("处理平移", "指出标准差不变"), ("处理倍数", "标准差乘2，得16并选C")]],
      "线性变换y=2x−1的标准差为|2|×8=16，选C。", "独立使用标准差对线性变换的性质，区别方差与标准差比例。"),
    "bank:cmm:17239": reviewed("statistics", ["样本均值", "样本方差", "数据线性变换"], ["求数据仿射变换后的均值和方差"], 1,
      "均值按仿射变换变换，方差乘以系数平方。", "single_choice", "choice",
      ["数据均值3、方差1，变换为2xᵢ+3后，新均值和方差是多少？"], ["D"],
      [["均值为2·3+3=9。", "方差为2²·1=4，常数平移不影响方差。", "故为(9,4)，选D。"]],
      [[("计算新均值", "2·3+3=9"), ("计算新方差", "2²·1=4"), ("匹配选项", "选D")]],
      "新均值9，新方差4，故选D。", "分别用仿射变换下的均值与方差公式复算。"),
    "bank:cmm:17062": reviewed("statistics", ["分层抽样", "样本分配"], ["按各层总体比例分配样本量"], 1,
      "共同抽样比例为样本量除以总体量，各层按该比例分配。", "single_choice", "choice",
      ["共98台热水器，甲厂56台、乙厂42台；分层抽取14台，求两厂各抽多少台。"], ["B"],
      [["抽样比例14/98=1/7。", "甲抽56/7=8台，乙抽42/7=6台，选B。"]],
      [[("求统一抽样比例", "得到1/7"), ("按层分配样本", "甲8台乙6台，选B")]],
      "抽样比例1/7，故甲8台、乙6台，选B。", "复核两层人数之和98及分配样本量之和14。"),
    "bank:cmm:22344": reviewed("probability", ["古典概型", "对立事件"], ["用对立事件求至少一个白球概率"], 1,
      "从4球中摸2球的等可能组合中减去全黑这一种结果。", "single_choice", "choice",
      ["袋内有2白、2黑共4球，一次摸2球，求至少摸到1白球的概率。"], ["D"],
      [["总组合数C(4,2)=6。", "没有白球只可能是两黑球，组合数C(2,2)=1。", "至少一白的概率=1−1/6=5/6，选D。"]],
      [[("确定等可能样本空间", "共有6种两球组合"), ("计算对立事件", "全黑概率1/6"), ("用对立事件求概率", "5/6并选D")]],
      "总组合数6，全黑组合1，概率1−1/6=5/6，选D。", "按球的物理个体作为等可能结果计数，并用互补事件计算。"),
    "bank:cmm:14860": reviewed("functions", ["函数奇偶性", "函数定义域"], ["在对称定义域上按定义判断奇函数"], 1,
      "先确认定义域关于原点对称，再检验f(−x)=−f(x)。", "single_choice", "choice",
      ["判断f(x)=1/x−x的奇偶性。"], ["A"],
      [["定义域为R去掉0，关于原点对称。", "f(−x)=−1/x+x=−(1/x−x)=−f(x)，故f为奇函数，选A。"]],
      [[("验证定义域对称", "R去掉0仍关于原点对称"), ("检验奇偶定义", "证明f(−x)=−f(x)，选A")]],
      "f定义域对称且f(−x)=−f(x)，所以是奇函数，选A。", "按奇函数定义检查定义域和函数值关系。"),
    "bank:cmm:15025": reviewed("functions", ["二次函数", "闭区间值域"], ["配方确定闭区间内最小值并比较端点"], 1,
      "顶点横坐标位于区间内，且开口向上；最大值取两个端点中较大者。", "single_choice", "choice",
      ["x∈[1,4]时，f(x)=x²−3x+2，求值域。"], ["C"],
      [["配方得f(x)=(x−3/2)²−1/4，顶点位于区间内，最小值为−1/4。", "端点f(1)=0、f(4)=6，最大值6。", "值域为[−1/4,6]，选C。"]],
      [[("配方求顶点和最小值", "−1/4在x=3/2取到"), ("比较端点求最大值", "f(4)=6大于f(1)=0"), ("写出值域", "选C")]],
      "顶点给最小值−1/4；端点值0和6中最大为6，值域[−1/4,6]，选C。", "重新配方、确认顶点落在闭区间，并比较两端点。"),
    "bank:cmm:14553": reviewed("exponential_logarithmic", ["指数函数", "对数函数值域"], ["由指数函数值域推出对数复合函数值域"], 1,
      "3^x取遍正数，故3^x+1取值为(1,+∞)，再取以2为底的对数。", "single_choice", "choice",
      ["求f(x)=log₂(3ˣ+1)的值域。"], ["A"],
      [["3ˣ∈(0,+∞)，所以3ˣ+1∈(1,+∞)。", "log₂在正底数2>1下递增，将(1,+∞)映为(0,+∞)，端点0不取到，选A。"]],
      [[("确定内层取值范围", "得到(1,+∞)"), ("映射对数范围并检查端点", "得到(0,+∞)，选A")]],
      "3ˣ+1>1且可趋近1并任意增大，故对数值域为(0,+∞)，选A。", "核实3ˣ取遍全体正数及开端点不取到。"),
    "bank:cmm:14734": reviewed("exponential_logarithmic", ["指数函数", "绝对值函数"], ["由绝对值范围求指数函数在闭区间上的值域"], 1,
      "x∈[−1,2]时|x|取遍[0,2]，再利用底数大于1的指数函数递增。", "single_choice", "choice",
      ["求f(x)=2^{|x|−1}在[−1,2]上的值域。"], ["B"],
      [["在[−1,2]上，|x|的最小值为0（x=0取到），最大值为2（x=2取到）。", "指数函数2^{t−1}随t递增，故最小值2⁻¹=1/2，最大值2¹=2，值域[1/2,2]，选B。"]],
      [[("确定|x|取值范围", "为[0,2]且端点可达"), ("应用单调性计算函数值", "最小1/2、最大2，选B")]],
      "|x|∈[0,2]，故2^{|x|−1}∈[1/2,2]，选B。", "核查绝对值极值在原区间可达且指数函数单调递增。"),
    "bank:cmm:14446": reviewed("functions", ["零点存在定理", "二分法"], ["根据相邻二分区间端点函数值异号定位根"], 1,
      "最后给出的中点1.5和左端点1.25函数值异号，故零点位于其间。", "single_choice", "choice",
      ["用二分法求f(x)=3ˣ+3x−8在(1,2)内的根，已知f(1)<0、f(1.5)>0、f(1.25)<0，根在哪个区间？"], ["B"],
      [["连续函数f在1.25处小于0，在1.5处大于0。", "由零点存在定理，至少有根位于(1.25,1.5)；本题函数严格递增，故根唯一。选B。"]],
      [[("选取末次变号端点", "使用1.25与1.5"), ("应用零点存在定理", "得根在开区间内"), ("匹配区间选项", "选B")]],
      "f(1.25)<0<f(1.5)，连续性保证零点在(1.25,1.5)；f'(x)=ln3·3ˣ+3>0，因此唯一，选B。", "审读二分法给出的三次函数值，独立用变号定位并确认单调性。"),
    "bank:cmm:17421": reviewed("trigonometry", ["正弦函数", "函数值代入"], ["将图像点坐标代入正弦函数方程"], 1,
      "点在图像上意味着纵坐标等于该横坐标处函数值。", "single_choice", "choice",
      ["点M(π/2,−m)在y=sin x图象上，求m。"], ["C"],
      [["代入得−m=sin(π/2)=1，故m=−1，选C。"]],
      [[("代入横坐标求函数值", "sin(π/2)=1"), ("解出m", "−1并选C")]],
      "−m=1，故m=−1，选C。", "由图像点坐标定义代入并核对符号。"),
    "bank:cmm:17450": reviewed("trigonometry", ["三角函数诱导公式", "函数奇偶性"], ["化简复合余弦函数并判断奇偶性"], 1,
      "利用cos(π/2−x)=sin x化简后检验定义域与奇偶性。", "single_choice", "choice",
      ["判断y=cos(−x/2+π/2)的奇偶性。"], ["A"],
      [["由余弦偶性及诱导公式，cos(π/2−x/2)=sin(x/2)。", "sin(x/2)定义域为R且为奇函数，因此原函数为奇函数，选A。"]],
      [[("化简三角函数", "得到sin(x/2)"), ("判断奇偶性", "定义域对称且函数为奇，选A")]],
      "原式=cos(π/2−x/2)=sin(x/2)，为奇函数，选A。", "用恒等式化简并按定义域对称、函数值关系判定。"),
    "bank:cmm:18104": reviewed("trigonometry", ["三角函数周期", "余弦函数图象"], ["求形如cos(kx+φ)函数的最小正周期"], 1,
      "周期只由自变量系数绝对值决定，T=2π/|k|。", "single_choice", "choice",
      ["求f(x)=cos(2x−π/6)的最小正周期。"], ["B"],
      [["余弦函数cos u的基本周期为2π；自变量为2x−π/6，故最小正周期T=2π/2=π，选B。"]],
      [[("识别自变量系数", "k=2"), ("应用周期公式", "T=π并选B")]],
      "T=2π/2=π，选B。", "将相位平移与周期区分，按系数公式求最小正周期。"),
})

ITEMS.update({
    "bank:cmm:18489": reviewed("trigonometry", ["三角函数应用", "相对运动模型", "二次函数最值"], ["建立两船相对位置函数并求最近时刻"], 2,
      "将两船速度分解为平面向量，写相对位置平方关于时间的二次函数并求最小点。", "single_choice", "choice",
      ["岛B正南10千米处有甲船，甲以4km/h向北；乙从B以6km/h向北偏东60°航行。求两船距离最近时的航行时间。"], ["A"],
      [["取东、北为坐标轴，t小时后甲的位置为(0,−10+4t)，乙的位置为(3√3t,3t)。", "距离平方D²(t)=27t²+(10−t)²=28t²−20t+100。", "该二次函数在t=20/(56)=5/14小时取最小值，即150/7分钟，选A。"]],
      [[("建立坐标和速度分量", "乙的分量为东3√3、北3，甲北向4"), ("建立距离平方函数", "正确得到28t²−20t+100"), ("求最小距离时刻并换单位", "t=5/14小时=150/7分钟，选A")]],
      "两船相对位置为(3√3t,10−t)，距离平方28t²−20t+100，顶点t=5/14h=150/7min，选A。", "独立建立运动坐标模型、求二次函数顶点，并核对题源时间单位与选项。"),
    "bank:cmm:19491": reviewed("functions", ["二次函数模型", "利润最大化"], ["由售价与销量线性关系建立利润二次函数并求最值"], 2,
      "以提价x元为决策变量，建立利润函数后求顶点。", "single_choice", "choice",
      ["商品进价40元；售价50元时月销量500件。每提价1元月销量减少10件。求月利润最大的定价。"], ["D"],
      [["设提价x元，则销量500−10x、每件利润10+x，月利润P(x)=(500−10x)(10+x)=−10x²+400x+5000。", "抛物线开口向下，顶点在x=−400/(2·−10)=20。", "售价50+20=70元时利润最大，选D。"]],
      [[("建立销量和单件利润表达式", "分别为500−10x及10+x"), ("构造并求二次函数顶点", "x=20"), ("还原定价", "70元，选D")]],
      "P(x)=−10x²+400x+5000，顶点提价20元，最优售价70元，选D。", "将价格变化转换为销量和单位利润，再用顶点求全局最大。"),
    "bank:cmm:18614": reviewed("inequalities", ["线性规划模型", "资源约束", "目标函数"], ["把原料消耗和利润目标翻译为线性规划约束"], 2,
      "按单位产品资源消耗建立不超过库存的两条约束，并限定产量非负。", "single_choice", "choice",
      ["甲、乙产品单位产量分别耗原料A为a₁、a₂，原料B为b₁、b₂；库存为c₁、c₂，单位利润d₁、d₂。设产量x、y，目标利润z=d₁x+d₂y，选择正确约束模型。"], ["C"],
      [["原料A总耗量为a₁x+a₂y，不能超过库存c₁；原料B总耗量为b₁x+b₂y，不能超过c₂。", "产量非负：x≥0、y≥0。", "故约束为a₁x+a₂y≤c₁、b₁x+b₂y≤c₂、x≥0、y≥0，对应C。"]],
      [[("为两种原料分别列资源消耗", "写出a₁x+a₂y与b₁x+b₂y"), ("匹配库存限制方向", "消耗不得超过可用库存"), ("加入非负决策变量", "并选C")]],
      "每种原料的总消耗均不得超过其库存，且x、y非负，因此选C。", "逐项检查单位消耗系数下标、库存上限方向和变量可行域。"),
    "bank:cmm:18499": reviewed("trigonometry", ["解三角形的实际应用", "仰角与俯角"], ["由水平距离和观测角度求两楼高度"], 2,
      "用水平距离与仰角求甲楼高，再由俯角确定两楼顶高度差。", "single_choice", "choice",
      ["两楼水平距离20m；乙楼底看甲楼顶仰角60°，甲楼顶看乙楼顶俯角30°，求甲、乙楼高。"], ["A"],
      [["甲楼高度h甲=20tan60°=20√3m。", "两楼顶高度差为20tan30°=20/√3m，因此h乙=20√3−20/√3=40√3/3m。", "对应选项A。"]],
      [[("将观测角与水平距离转成直角三角形", "甲高由20tan60°给出"), ("解释俯角所对应高度差", "高度差为20tan30°"), ("求乙楼高度并匹配", "40√3/3m，选A")]],
      "h甲=20√3；顶端高度差=20/√3，所以h乙=20√3−20/√3=40√3/3，选A。", "把观测平面化为两直角三角形，并区分乙楼高度与楼顶高度差。"),
    "bank:cmm:18926": reviewed("trigonometry", ["正弦定理", "测量与行程建模"], ["由三角测量边长比求相同速度下行程时间"], 2,
      "利用三角形内角和确定第三角，以正弦定理求两条边的比，再用等速时间比。", "single_choice", "choice",
      ["海面三岛A、B、C满足∠ABC=30°、∠BAC=105°；从A到C需30分钟，同速时从A到B需多久？"], ["B"],
      [["∠ACB=180°−30°−105°=45°。", "正弦定理给AB/AC=sin45°/sin30°=√2。", "同速下时间与距离成正比，所需时间30√2≈42分钟，选B。"]],
      [[("确定第三角", "得到45°"), ("应用正弦定理比较两段距离", "AB/AC=√2"), ("换算行程时间", "约42分钟并选B")]],
      "第三角45°，AB/AC=sin45°/sin30°=√2；时间为30√2≈42分钟，选B。", "依据海岛位置建立三角形测量模型，核算角度、边长比及近似时间。"),
    "bank:cmm:18493": reviewed("trigonometry", ["仰角与俯角", "平行线角关系"], ["用水平线平行关系说明仰角等于俯角"], 1,
      "观察者处的水平线互相平行，视线为截线形成内错角。", "single_choice", "choice",
      ["从A处望B处的仰角为α，从B处望A处的俯角为β，判断α与β的关系。"], ["B"],
      [["将A、B处的水平线视为平行线，连线AB为截线。", "仰角α与俯角β是一对内错角，故α=β，选B。"]],
      [[("构造平行水平线", "指出两观察点水平线平行"), ("识别截线角关系", "仰角与俯角为内错角，α=β")]],
      "两处水平线平行，视线为截线，仰角和俯角相等，选B。", "该结论依赖同一水平基准，按几何平行线角关系核验。"),
    "bank:cmm:14845": reviewed("functions", ["二次函数模型", "离散最优化"], ["将两地销量分配转化为整数变量二次函数最值"], 2,
      "利用总销量约束消去一个变量，配方后比较相邻整数点。", "single_choice", "choice",
      ["甲地销售x辆利润−x²+21x万元，乙地销售x辆利润2x万元。两地共销售15辆，求最大总利润。"], ["C"],
      [["令甲地售x辆，则乙地售15−x辆，x为0至15的整数。", "总利润L=−x²+21x+2(15−x)=−x²+19x+30=−(x−19/2)²+481/4。", "实数顶点为9.5；整数x取9或10时取得最大值L=120万元，选C。"]],
      [[("用总量约束消元", "乙地销量为15−x"), ("建立并配方利润函数", "得到顶点x=9.5"), ("处理整数销量", "比较x=9与10，最大120万元，选C")]],
      "L=−x²+19x+30=−(x−9.5)²+120.25。x为整数，最近的9、10均取120万元，选C。", "特别保留销量为整数的现实约束，避免把连续顶点的120.25误当可实现利润。"),
    "bank:cmm:20163": reviewed("inequalities", ["分段收益模型", "利润最大化"], ["建立分段利润函数并用因式分解比较全局最值"], 3,
      "先扣除固定及单位成本，再以利润差分解证明x=300为前段全局上界的取等点，并比较另一段。", "single_choice", "choice",
      ["固定成本20000元、单位成本100元；收入R(x)=−x³/900+400x (0≤x≤390)，x>390时R=90090。求利润最大的年产量。"], ["D"],
      [["0≤x≤390时，利润P(x)=R−(20000+100x)=−x³/900+300x−20000。", "P(300)=40000，且P(300)−P(x)=(x−300)²(x+600)/900≥0，因此该区间全局最大在x=300取到。", "x>390时，P(x)=70090−100x<31090<40000。故全局最大产量为300，选D。"]],
      [[("扣除固定成本和单位成本", "正确写出两段利润函数"), ("证明第一段上界", "分解P(300)−P(x)并验证非负"), ("比较第二段", "其利润小于31090，低于40000"), ("给出决策", "产量300，选D")]],
      "前段利润P=−x³/900+300x−20000，且P(300)−P(x)=(x−300)²(x+600)/900≥0，取等于x=300。后段利润=70090−100x<31090，故全局最大产量300，选D。", "独立处理题设分段收入与总成本，用恒等式证明最优性，不调用未映射到本单元的导数。"),
})


def build(out: Path) -> dict:
    previous = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    root = ROOT / "data/sources"
    wanted = set(ITEMS)
    questions = {}
    for ds in ("cmm", "gaokao"):
        for q in iter_dataset(root, ds):
            if q["id"] in wanted:
                questions[q["id"]] = q
    agieval_ids = {int(qid.rsplit(":", 1)[1]) for qid in wanted if qid.startswith("bank:agieval-gaokao-mathqa:")}
    if agieval_ids:
        import hashlib, re, unicodedata
        rel = "data/v1_1/gaokao-mathqa.jsonl"
        path = root / "agieval-senior" / rel
        raw_bytes = path.read_bytes()
        dl = json.loads((root / "agieval-senior" / "DOWNLOAD.json").read_text(encoding="utf-8"))
        revision = dl["revision"]
        listed_sha = next(x["sha256"] for x in dl["files"] if x["path"] == rel)
        if hashlib.sha256(raw_bytes).hexdigest() != listed_sha:
            raise ValueError("AGIEval mathqa source changed from pinned manifest")
        rows = [json.loads(line) for line in raw_bytes.decode("utf-8").splitlines()]
        for idx in agieval_ids:
            row = rows[idx]
            stem = unicodedata.normalize("NFKC", row.get("question") or "")
            stem = re.sub(r"\\\\\s*$", "", stem).strip()
            options = []
            for i, rawopt in enumerate(row.get("options") or []):
                match = re.match(r"^\s*\(([A-D])\)\s*(.*)$", rawopt, re.S)
                if not match:
                    raise ValueError(f"unparseable AGIEval option at {idx}: {rawopt!r}")
                options.append({"key": match.group(1), "text": match.group(2).strip()})
            source_id = f"agieval-gaokao-mathqa:{idx}"
            q = {"id": f"bank:{source_id}", "subject": "math", "stage": "senior", "grade": None, "term": None,
                 "stem": stem, "options": options, "answer": row["label"], "kind": "single_choice",
                 "has_missing_assets": False, "steps": [], "status": "ready",
                 "provenance": {"dataset": "AGIEval v1.1 gaokao-mathqa", "source_id": source_id,
                    "source_file": rel, "download_revision": revision, "file_sha256": listed_sha,
                    "url": f"https://github.com/ruixiangcui/AGIEval/blob/{revision}/{rel}",
                    "license": dl.get("license"), "original_source": row.get("other", {}).get("source")},
                 "source_record": row}
            questions[q["id"]] = q
    if wanted != questions.keys():
        raise ValueError(f"source ids changed or missing: {sorted(wanted - questions.keys())}")
    manifest = {name: source_manifest(root, name) for name in ("cmm", "gaokao")}
    if agieval_ids:
        manifest["agieval_mathqa"] = {"revision": revision, "path": rel, "sha256": listed_sha,
            "count": len(rows), "license": dl.get("license"),
            "source_url": f"https://github.com/ruixiangcui/AGIEval/blob/{revision}/{rel}"}
    output_items = []
    for qid, details in ITEMS.items():
        q = questions[qid]
        if q.get("status") == "quarantine" or q.get("has_missing_assets"):
            raise ValueError(f"selected source became unsafe: {qid}")
        default_book, unit = GOAL_BOOK_UNIT[details["topic"]]
        goal_id = QUESTION_GOAL.get(qid, f"{default_book}:u{unit}:g{GOAL_NUMBER[details['topic']]}")
        book = goal_id.split(":u", 1)[0]
        annotation = json.loads(json.dumps(details["annotation"], ensure_ascii=False))
        annotation["curriculum"] = {"grade": None, "term": None, "book_id": book, "goal_ids": [goal_id],
            "scope_status": "candidate", "basis": "按题目实际测量的北师大版高中数学册内主题对齐；目标为目录宽口径候选，待目录代理最终核对。"}
        Annotation.model_validate(annotation)
        output_items.append({
            "question_id": qid,
            "source_sha256": source_fingerprint(q),
            "curriculum_book_id": book,
            "decision": details["decision"],
            "question": q,
            "independent_solution": details["independent_solution"],
            "source_conflicts": [],
            "remaining_issues": [],
            "rationale": details["rationale"],
            "curriculum_goal_ids": [goal_id],
            "annotation": annotation,
        })
        if has_control(q):
            output_items[-1].update({"decision": "pending", "annotation": None,
                "source_conflicts": [],
                "remaining_issues": ["规范化来源题的题干、选项或来源解析含公式转义控制字符；保留原始指纹并隔离，不能无损确认文本。"],
                "rationale": "逐题检查时发现题源文本带有公式转义控制字符。为避免静默修复后改变原题含义，暂列pending，需回到上游原始版本核源。"})
    if previous:
        if previous.get("batch_id") != BATCH:
            raise ValueError("existing file belongs to a different batch")
        by_id = {x["question_id"]: x for x in previous.get("items", [])}
        for item in output_items:
            old = by_id.get(item["question_id"])
            if old and old.get("source_sha256") != item["source_sha256"]:
                raise ValueError(f"existing reviewed record has stale fingerprint: {item['question_id']}")
            # Previously reviewed snapshots are immutable; don't silently replace them.
            if old:
                if has_control(old.get("question", {})):
                    old["decision"] = "pending"
                    old["annotation"] = None
                    old["source_conflicts"] = []
                    old["remaining_issues"] = ["规范化来源题的题干、选项或来源解析含公式转义控制字符；保留原始指纹并隔离，不能无损确认文本。"]
                    old["rationale"] = "逐题检查时发现题源文本带有公式转义控制字符。为避免静默修复后改变原题含义，暂列pending，需回到上游原始版本核源。"
                # Curriculum alignment was deliberately left pending in the first
                # six records; fill only these absent catalog fields after mapping.
                if (old.get("curriculum_book_id") != item.get("curriculum_book_id")
                        or (old.get("annotation") or {}).get("curriculum", {}).get("book_id") != item.get("curriculum_book_id")):
                    old["curriculum_book_id"] = item["curriculum_book_id"]
                    old["curriculum_goal_ids"] = item["curriculum_goal_ids"]
                    if old.get("annotation") is not None:
                        old["annotation"]["curriculum"] = item["annotation"]["curriculum"]
                # Repair the first tranche's source-response-format mismatch;
                # source questions with options must retain their original choice mode.
                if (old["question"].get("kind") in {"single_choice", "multiple_choice"}
                        and (old.get("annotation") or {}).get("response_format") != old["question"].get("kind")):
                    old["annotation"] = item["annotation"]
                # Correct a previously miscounted row-by-row explanation; the
                # source stem and answer were unchanged, but the checked steps were wrong.
                if item["question_id"] == "bank:cmm:16977":
                    old["independent_solution"] = item["independent_solution"]
                    old["annotation"] = item["annotation"]
                if item["question_id"] == "bank:cmm:20162":
                    old["independent_solution"] = item["independent_solution"]
                    old["annotation"] = item["annotation"]
                # Fine-type audit: update only the two reviewed annotations whose
                # labels were too short for the study question-type catalog.
                if item["question_id"] in {"bank:cmm:15358", "bank:cmm:20114"}:
                    old["annotation"] = item["annotation"]
            else:
                by_id[item["question_id"]] = item
        output_items = list(by_id.values())
        # These two source records contain JSON-decoded form feeds where LaTeX
        # fractions were intended. Their source fingerprints must remain exact;
        # exclude them from annotation output rather than silently repairing data.
        output_items = [x for x in output_items if x["question_id"] not in {"bank:cmm:21312", "bank:cmm:21313"}]
        # These records are unsafe despite the correct standalone calculations:
        # source formula/choice text is damaged or the stated condition is insufficient.
        for item in output_items:
            if item["question_id"] == "bank:cmm:21318":
                item["decision"] = "pending"
                item["annotation"] = None
                item["independent_solution"] = "a·μ=0 shows the direction vector is parallel to the plane normal, but does not distinguish a line strictly parallel to the plane from a line contained in the plane."
                item["source_conflicts"] = []
                item["remaining_issues"] = ["题目缺少直线不在平面内等条件；a·μ=0不能单独推出严格平行关系。"]
                item["rationale"] = "按严格的位置关系定义，该选择题条件不足；不猜原选项结论，暂列pending等待题源补充或排除。"
            if item["question_id"] in {"bank:cmm:22029", "bank:cmm:22030", "bank:cmm:22168"}:
                item["decision"] = "pending"
                item["annotation"] = None
                item["source_conflicts"] = []
                item["remaining_issues"] = ["题源选项中的公式/小数排版损坏，不能确认各选项的原始内容；保留题目和答案供后续核源，不进入passed。"]
                item["rationale"] = "尽管按题干能独立算出结果，但原始选项不完整或OCR破损；来源问项无法无损复核，故暂列pending。"
    result = {"batch_id": BATCH, "source_manifest": manifest,
              "screening_inventory": "data/annotations/senior-20261015/math/candidates.jsonl",
              "screening_program": "scripts/senior_math_candidates.py",
              "items": output_items,
              "coverage": {"reviewed_count": len(output_items),
                           "topics_reviewed": sorted({v["topic"] for v in ITEMS.values()}),
                           "required_topics": ["sets_logic", "inequalities", "functions", "exponential_logarithmic", "trigonometry", "plane_vectors", "complex_numbers", "solid_geometry", "spatial_vectors", "lines_circles", "conics", "statistics", "probability", "counting_binomial", "sequences", "derivatives", "distributions_regression"],
                           "complete": False,
                           "note": "This is a first checked sample. Missing topics and topic minimums remain open."}}
    out.parent.mkdir(parents=True, exist_ok=True)
    from app.senior_bank import save_batch
    save_batch(out, result)
    return result


if __name__ == "__main__":
    dest = ROOT / "app/data/senior_math_luna.json"
    print(json.dumps(build(dest), ensure_ascii=False, indent=2)[:1200])
