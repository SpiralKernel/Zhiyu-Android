"""七上数学标准题型：固定ID、明确解题结构，与来源标签/教材进度分别维护。"""
from app.question_types import BASE_TYPES, CHALLENGE_TYPES, normalize_name

VERSION = "math-types-2026.10.11"
BOOK_ID = "math-7-1"


def kind(key, name, goal, ability, templates=(), aliases=(), prerequisites=()):
    return {"id": "m7a:" + key, "name": name, "book_id": BOOK_ID,
            "goal_id": BOOK_ID + ":" + goal, "unit_id": BOOK_ID + ":" + goal.split(":")[0],
            "can_do": ability, "legacy_type_ids": list(templates),
            "aliases": list(dict.fromkeys([name, *aliases])),
            "prerequisites": ["m7a:" + p for p in prerequisites]}


TYPES = [
    kind("signed-quantity", "用正负数表示相反意义的量", "u1:g1", "解释正负号与基准的含义，正确表示数量。"),
    kind("rational-classification", "有理数分类与零的位置", "u1:g1", "区分整数与分数，说明零的分类。"),
    kind("opposite", "数轴对称求相反数", "u1:g2", "利用关于原点对称或两数之和为零求相反数。", ["template:opposite"], ["求一个数的相反数"]),
    kind("axis-transform", "数轴平移与对称复合", "u1:g2", "按先后顺序处理数轴上的平移和关于原点对称。", ["challenge:opposite"], prerequisites=["opposite"]),
    kind("compare", "借助数轴比较有理数大小", "u1:g2", "比较含负分数的有理数，解释负数的大小关系。"),
    kind("absolute", "负数的绝对值", "u1:g3", "用距离解释负数绝对值并求值。", ["template:absolute"], ["求负数的绝对值"]),
    kind("absolute-condition", "绝对值条件下的分式求值", "u1:g3", "由绝对值和符号条件确定未知数，再检验分母并求值。", ["challenge:absolute"], prerequisites=["absolute"]),
    kind("axis-distance", "数轴上两点的距离", "u1:g3", "结合点的位置与绝对值求距离，区分方向和距离。"),
    kind("subtract-negative", "负数减负数", "u2:g1", "把减去负数改写为加相反数，正确确定结果符号。", ["template:addition"], ["减去负数", "负数减去负数"], ["opposite"]),
    kind("fraction-add", "有理数分数混合加减", "u2:g1", "通分处理有理数分数加减，并保持符号一致。", ["challenge:addition"], prerequisites=["subtract-negative"]),
    kind("negative-product", "两个负数相乘", "u2:g2", "先确定积的符号，再计算绝对值的积。", ["template:multiply"], ["负数乘负数"]),
    kind("fraction-multiply", "带分数的乘除混合运算", "u2:g2", "处理分数乘除、倒数与混合运算中的符号。", ["challenge:multiply"], prerequisites=["negative-product"]),
    kind("power-sign", "幂前负号与平方", "u2:g3", "区分幂前的负号与底数，先乘方再取相反数。", ["template:power:0"]),
    kind("negative-base", "负数底数的平方", "u2:g3", "按括号确定负数底数，正确计算平方。", ["template:power:1"]),
    kind("power-mixed", "含负号和括号的乘方综合", "u2:g3", "明确乘方作用范围，按运算顺序计算。", ["challenge:power"], prerequisites=["power-sign", "negative-base"]),
    kind("scientific", "科学记数法表示与还原", "u2:g4", "确定系数与指数，检查还原后的数值。"),
    kind("approximate", "按精确度取近似数", "u2:g4", "按指定数位取近似值，说明精确程度。"),
    kind("expression-model", "列代数式表示数量关系", "u3:g1", "把文字关系写成代数式，解释字母及单位。"),
    kind("substitution", "一次代数式代入负数", "u3:g2", "代入负数时保留括号，正确求一次代数式的值。", ["template:substitution"]),
    kind("quadratic-substitution", "二次代数式代入求值", "u3:g2", "规范代入含平方的代数式，检查负号与乘方。", ["challenge:substitution"], prerequisites=["substitution", "negative-base"]),
    kind("polynomial-concept", "单项式多项式的系数与次数", "u4:g1", "区分系数、项和次数，正确处理负系数及常数项。"),
    kind("like-terms", "同类项系数相加", "u4:g2", "合并同类项时只加减系数，保持字母与指数。", ["template:like_terms"], ["同类项的系数合并"]),
    kind("multi-letter-terms", "多字母整式的系数提取", "u4:g2", "识别多字母同类项并提取合并后的系数。", ["challenge:like_terms"], prerequisites=["like-terms"]),
    kind("brackets", "负号去括号后求值", "u4:g3", "括号前是负号时逐项变号，再化简求值。", ["template:brackets"], ["负号去括号"], ["like-terms"]),
    kind("nested-brackets", "双重括号代入求值", "u4:g3", "逐层去括号并检查每一层符号，再代入求值。", ["challenge:brackets"], prerequisites=["brackets"]),
    kind("equality", "利用等式性质作等价变形", "u5:g1", "说明两边同时运算的条件，检验给定数是否为解。"),
    kind("linear", "ax+b=c 型方程", "u5:g2", "依据等式性质求解并代回检验。", ["template:linear"], ["ax+b=c型方程"]),
    kind("fraction-equation", "含括号与分母的一元一次方程", "u5:g2", "去分母不漏乘、去括号逐项处理，求解后检验。", ["challenge:linear"], prerequisites=["linear", "brackets"]),
    kind("fixed-cost", "含固定费用的购物建模", "u5:g3", "从单价、数量和固定费用建立等量关系，检验数量意义。", ["template:word_equation"], prerequisites=["linear"]),
    kind("two-products", "两类商品与数量关系建模", "u5:g3", "用数量关系表示两类商品，再依据总价列一元一次方程。", ["challenge:word_equation"], prerequisites=["fixed-cost"]),
    kind("geometry", "识别立体图形与展开图", "u6:g1", "根据点线面体及对应关系判断简单展开图。"),
    kind("midpoint", "已知全长求中点分段", "u6:g2", "用中点的等分关系计算线段长度。", ["template:segment"]),
    kind("two-midpoints", "两个中点的线段综合", "u6:g2", "根据点的顺序及两个中点条件建立线段关系。", ["challenge:segment"], prerequisites=["midpoint"]),
    kind("complement", "已知角求余角", "u6:g3", "用两角和为90度求余角并检查范围。", ["template:angle:0"]),
    kind("supplement", "已知角求补角", "u6:g3", "用两角和为180度求补角并检查范围。", ["template:angle:1"]),
    kind("angle-model", "角的倍数与补角建模", "u6:g3", "把倍数和补角关系转化为方程并解释角度。", ["challenge:angle"], prerequisites=["supplement", "linear"]),
    kind("angle-bisector", "角平分线与角的和差", "u6:g3", "标出角的对应关系，运用角平分及角的和差条件。"),
]
TYPE_MAP = {t["id"]: t for t in TYPES}
LEGACY_MAP = {key: t["id"] for t in TYPES for key in t["legacy_type_ids"]}
ALIAS_MAP = {normalize_name(alias): t["id"] for t in TYPES for alias in t["aliases"]}
assert len(TYPE_MAP) == len(TYPES) and len(LEGACY_MAP) == len(BASE_TYPES) + len(CHALLENGE_TYPES)


def resolve_type(type_id, name=""):
    return type_id if type_id in TYPE_MAP else LEGACY_MAP.get(type_id) or ALIAS_MAP.get(normalize_name(name))
