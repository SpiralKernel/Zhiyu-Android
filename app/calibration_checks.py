"""Bounded mathematical checks for calibration; unsupported questions remain AI-reviewed.

No eval, subprocess, symbolic code execution, or inference from reference solutions.
Only full, explicitly supported question forms are computed from the source.
"""
import re
import unicodedata
from fractions import Fraction


def math_text(value):
    value=unicodedata.normalize('NFKC',value).replace('−','-').replace('﹣','-')
    value=re.sub(r'\\(?:d?frac)\{([+-]?\d+)\}\{([+-]?\d+)\}',r'(\1/\2)',value)
    return value.replace('$','').strip()


def numeric_values(value,unit=None):
    """Parse only a complete scalar or unordered numeric answer, never prose/numeric substrings."""
    from app.answers import linear_expression
    if not isinstance(value,str) or len(value)>300:return None
    value=math_text(value)
    # Known temperature notation, including source LaTeX; no arbitrary unit guessing.
    value=re.sub(r'(?:\{\})?\^?\\circ\s*(?:\\text\{C\}|C)', '°C',value)
    if unit and value.endswith(unit):value=value[:-len(unit)].strip()
    elif value.endswith(('°C','℃')):value=re.sub(r'(?:°C|℃)$','',value).strip()
    value=value.strip('{} ')
    chunks=re.split(r'或|和|、|，|,|;',value)
    if not chunks or len(chunks)>30:return None
    values=[]
    try:
        for text in chunks:
            text=text.strip()
            if not text:return None
            for _ in range(4):
                match=re.search(r'\|([^|]{1,50})\|',text)
                if not match:break
                inner=numeric_values(match[1])
                if inner is None or len(inner)!=1:return None
                text=text[:match.start()]+'('+str(abs(next(iter(inner))))+')'+text[match.end():]
            if text.endswith('%'):
                a,b=linear_expression(text[:-1]);b/=100
            else:a,b=linear_expression(text)
            if a:return None
            values.append(b)
    except (ValueError,ZeroDivisionError,OverflowError):return None
    # Duplicate roots are a malformed answer, not an unordered set equivalent.
    return frozenset(values) if len(values)==len(set(values)) else None


def comparable(left,right,unit=None):
    a=numeric_values(left,unit);b=numeric_values(right,unit)
    return a==b if a is not None and b is not None else None


def source_checks(source,finding):
    if finding.decision!='pass' or source.images:return []
    classification=classification_checks(source,finding)
    if classification is not None:return classification
    if len(finding.parts)!=1:return []
    part=finding.parts[0];text=math_text(source.stem)
    text=re.sub(r'^(?:题目内容|问题描述)\s*[:：]\s*','',text)
    expected=None;basis=''
    # Fully anchored: extra conditions, diagrams, and multipart questions are not guessed.
    number=r'([+-]?(?:\d+(?:\.\d+)?|\.\d+))'
    m=re.fullmatch(r'在数轴上[，,]距离\s*'+number+r'\s*为\s*'+number+r'\s*个单位长度的点所表示的数是[_\s]+[。.]?',text)
    if m:
        center,distance=map(Fraction,m.groups())
        if distance>=0:expected=frozenset((center-distance,center+distance));basis='数轴定点距离'
    m=re.fullmatch(r'计算\s*[:：]?\s*(.{1,64}?)[。]?',text)
    if m:
        expression=m[1].rstrip('。').rstrip('=')
        values=numeric_values(expression)
        if values and len(values)==1:expected=values;basis='常数四则运算'
    if expected is None:return []
    if source.kind in {'single_choice','multiple_choice'}:
        choices={o.key for o in source.options if numeric_values(o.text)==expected}
        answer=set(part.answer.replace(' ','').replace('、','').replace(',',''))
        if not choices or answer!=choices:return ['来源独立复算不符（'+basis+'）：选项答案与计算值不一致']
    elif numeric_values(part.answer,part.answer_spec.unit)!=expected:
        return ['来源独立复算不符（'+basis+'）：应为'+ '或'.join(str(v) for v in sorted(expected))]
    return []


def classification_checks(source,finding):
    """Only the complete four-set rational classification form; no fuzzy topic matching."""
    text=re.sub(r'^(?:题目内容|问题描述)\s*[:：]\s*','',math_text(source.stem))
    match=re.fullmatch(r'将下列有理数填入对应的集合括号中[:：](.*?)正数集合\{([^{}]*)\}整数集合\{([^{}]*)\}分数集合\{([^{}]*)\}有理数集合\{([^{}]*)\}[。.]?',text)
    if not match or any(re.sub(r'</?u>|[\s_….]','',v) for v in match.groups()[1:]):return None
    values=numeric_values(match[1])
    if values is None:return None
    expected={'正数':frozenset(v for v in values if v>0),'整数':frozenset(v for v in values if v.denominator==1),
              '分数':frozenset(v for v in values if v.denominator!=1),'有理数':values}
    observed={}
    if len(finding.parts)==1:
        for label,answer in re.findall(r'(正数|整数|分数|有理数)集合\s*[:：]?\s*\{([^{}]*)\}',math_text(finding.parts[0].answer)):
            if label in observed:return ['来源独立复算不符（有理数分类）：答案集合重复']
            observed[label]=numeric_values(answer) if answer.strip() else frozenset()
    else:
        for part in finding.parts:
            labels=[key for key in expected if key+'集合' in part.prompt]
            if len(labels)!=1 or labels[0] in observed:return ['来源独立复算不符（有理数分类）：小问与集合对应不清']
            answer=math_text(part.answer)
            full=re.fullmatch(r'(?:正数|整数|分数|有理数)集合\s*[:：]?\s*\{([^{}]*)\}',answer)
            if full:answer=full[1]
            observed[labels[0]]=numeric_values(answer) if answer.strip('{} ') else frozenset()
    problems=[]
    for label,answer in expected.items():
        if observed.get(label)!=answer:
            problems.append('来源独立复算不符（有理数分类）：'+label+'集合应完整列出'+','.join(str(v) for v in sorted(answer)))
    return problems
