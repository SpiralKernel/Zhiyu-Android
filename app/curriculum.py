"""项目编写的学习目标；不是教材或课标的逐字转录。"""

VERSION = "7a-2026.1"
SOURCE = "https://www.moe.gov.cn/srcsite/A26/s8001/202204/t20220420_619921.html"

# 教材章节顺序通过此处独立维护，不把课标学段要求误标为统一学期安排。
UNITS = [
    {"id": "rational", "name": "有理数", "description": "从数轴和符号出发，建立运算基础"},
    {"id": "algebra", "name": "整式的加减", "description": "用字母表示数量，理解合并与化简"},
    {"id": "equation", "name": "一元一次方程", "description": "根据等量关系解决实际问题"},
    {"id": "geometry", "name": "几何图形初步", "description": "认识线段、角及基本数量关系"},
]


def node(id, unit, name, goal, prerequisites, misconceptions, example):
    return dict(id=id, unit_id=unit, name=name, goal=goal,
                prerequisites=prerequisites, misconceptions=misconceptions,
                example=example, grade=7, term=1, stage="第四学段（7—9年级）",
                source=SOURCE, curriculum_version=VERSION)


NODES = [
    node("opposite", "rational", "数轴与相反数", "理解数轴方向与相反数；能求一个有理数的相反数。", [],
         ["把相反数与倒数混淆", "忽略负号"], "−6 的相反数是 6。"),
    node("absolute", "rational", "绝对值", "用到原点的距离解释绝对值，能计算有理数的绝对值。", ["opposite"],
         ["认为负数的绝对值仍是负数", "把距离理解为方向"], "|−4| = 4，距离不为负。"),
    node("addition", "rational", "有理数加减", "区分同号与异号相加；能把减法转化为加相反数。", ["absolute"],
         ["异号相加时符号错误", "减去负数未变号"], "−3 − (−5) = −3 + 5 = 2。"),
    node("multiply", "rational", "有理数乘除", "根据符号法则进行有理数乘除，理解除数不能为零。", ["addition"],
         ["同号相乘仍取负号", "漏判积的符号"], "(−3) × (−4) = 12。"),
    node("power", "rational", "乘方与运算顺序", "理解乘方的意义，区分括号中的负数与幂前的负号。", ["multiply"],
         ["混淆 −a² 与 (−a)²", "把乘方当成乘以指数"], "−3² = −9，而 (−3)² = 9。"),
    node("substitution", "algebra", "代数式求值", "用字母表示数，代入负数时能正确使用括号。", ["multiply"],
         ["代入负数时漏括号", "省略乘号后误读"], "x = −2 时，3x + 1 = −5。"),
    node("like_terms", "algebra", "同类项与整式加减", "识别同类项；合并时只加减系数，字母与指数不变。", ["substitution"],
         ["合并时把指数也相加", "不同类项直接相加"], "3x + 2x = 5x。"),
    node("brackets", "algebra", "去括号", "理解括号前是负号时，括号内每一项都要改变符号。", ["like_terms"],
         ["只改变括号中第一项的符号", "括号前负号遗漏"], "5 − (2x − 3) = 8 − 2x。"),
    node("linear", "equation", "解一元一次方程", "用等式性质解一元一次方程，并把解代回检验。", ["brackets"],
         ["移项不变号", "两边只对一边做运算"], "2x + 3 = 11，两边减 3 后除以 2，x = 4。"),
    node("word_equation", "equation", "列方程解决问题", "找出未知量和等量关系，列方程、求解并检查实际意义。", ["linear"],
         ["等量关系缺少固定费用", "求出中间量就停止"], "每本 4 元，另付 2 元，总价 18 元：4x + 2 = 18。"),
    node("segment", "geometry", "线段与中点", "理解两点间距离和线段中点，能计算共线线段的长度。", ["addition"],
         ["把一半与全长混淆", "未区分点的排列顺序"], "M 是 AB 的中点，AB = 10 时 AM = 5。"),
    node("angle", "geometry", "角与余角补角", "区分余角与补角，依据 90° 或 180° 的和求角度。", ["addition"],
         ["混淆余角与补角", "忽略角的和的条件"], "35° 的余角是 55°，补角是 145°。"),
]
NODE_MAP = {n["id"]: n for n in NODES}
