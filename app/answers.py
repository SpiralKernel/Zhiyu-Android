"""有界、精确的答案解析；不执行学生输入，不使用浮点近似判等。"""
import ast
import re
import unicodedata
from fractions import Fraction


def normalized(text):
    text = unicodedata.normalize('NFKC', text).strip().replace('−', '-').replace('﹣', '-')
    if not text or len(text) > 64:
        raise ValueError('答案长度应为 1—64 个字符。')
    return text


def linear_expression(text):
    """返回 x 的系数与常数项；仅允许一次式及常数四则运算。"""
    source = re.sub(r'\s+', '', normalized(text)).replace('×', '*').replace('÷', '/').replace('^', '**')
    source = re.sub(r'(?<=\d)(?=x|\()|(?<=\))(?=x|\()|(?<=x)(?=\()', '*', source)
    try:
        tree = ast.parse(source, mode='eval')
        if len(list(ast.walk(tree))) > 40:
            raise ValueError('代数式过于复杂。')

        def visit(node):
            if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
                token = ast.get_source_segment(source, node)
                if not re.fullmatch(r'\d+(?:\.\d*)?|\.\d+', token):
                    raise ValueError('常数请使用十进制数或分数。')
                return Fraction(0), Fraction(token)
            if isinstance(node, ast.Name) and node.id == 'x':
                return Fraction(1), Fraction(0)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                a, b = visit(node.operand)
                return (a, b) if isinstance(node.op, ast.UAdd) else (-a, -b)
            if isinstance(node, ast.BinOp):
                a, b = visit(node.left)
                c, d = visit(node.right)
                if isinstance(node.op, ast.Add):
                    return a+c, b+d
                if isinstance(node.op, ast.Sub):
                    return a-c, b-d
                if isinstance(node.op, ast.Mult) and not a*c:
                    return a*d+b*c, b*d
                if isinstance(node.op, ast.Div) and c == 0 and d != 0:
                    return a/d, b/d
            raise ValueError('请填写只含 x、数字、括号和加减乘除的一次代数式。')

        return visit(tree.body)
    except (SyntaxError, ZeroDivisionError, OverflowError, RecursionError) as exc:
        raise ValueError('代数式格式无效；例如 3x+2 或 2*(x+1)。') from exc


def parse_answer(q, text):
    from app.questions import parse_number
    mode = q.get('answer_mode', 'numeric')
    if mode == 'expression':
        return linear_expression(text)
    text = normalized(text)
    if mode == 'scientific':
        source = re.sub(r'\s+', '', text).replace('×', '*')
        match = re.fullmatch(r'([+-]?(?:\d+(?:\.\d+)?|\.\d+))(?:[x*]10\^|[eE])([+-]?\d{1,2})', source)
        if not match or abs(int(match[2])) > 12:
            raise ValueError('请填写科学记数法，例如 3.2×10^5 或 3.2e5。')
        coefficient, exponent = parse_number(match[1]), int(match[2])
        return coefficient * Fraction(10)**exponent, 1 <= abs(coefficient) < 10
    if mode == 'decimal':
        if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?', text):
            raise ValueError('请填写十进制近似数，并保留题目要求的小数位数。')
        return parse_number(text), len(text.split('.')[1]) if '.' in text else 0
    return parse_number(text)


def equivalent(q, left, right):
    return parse_answer(q, left) == parse_answer(q, right)
