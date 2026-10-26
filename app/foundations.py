"""七上缺口题型的原创起步题；每类三个子任务，保留版本与实际覆盖边界。"""
import hashlib
import json
import random
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction as F

from app.answers import parse_answer

VERSION = '1'
CATALOG = {
    'signed-quantity': ('opposite', ('相对基准表示', '收支表示', '温度变化表示')),
    'rational-classification': ('opposite', ('整数分类', '非正整数分类', '非整数有理数分类')),
    'compare': ('opposite', ('数轴最左点', '负分数大小', '有理数排序位置')),
    'axis-distance': ('absolute', ('跨原点距离', '同侧距离', '已知距离与方向求坐标')),
    'scientific': ('power', ('大数科学记数法', '小数系数科学记数法', '科学记数法还原')),
    'approximate': ('power', ('正数四舍五入', '跨整数进位', '负数四舍五入')),
    'expression-model': ('substitution', ('含固定费用的代数式', '周长数量关系', '打折后的数量关系')),
    'polynomial-concept': ('like_terms', ('单项式系数', '单项式次数', '多项式次数')),
    'equality': ('linear', ('等式两边同加', '等式两边同除非零数', '等式两边同乘非零数')),
    'geometry': ('segment', ('展开图可折叠性', '正方体相对面', '正方体相邻面')),
    'angle-bisector': ('angle', ('角平分线求半角', '相邻角与角平分线', '相邻两角平分线夹角')),
}

from app.foundation_extensions import CATALOG as EXTRA_CATALOG, build as build_extra, validate as validate_extra
CATALOG.update(EXTRA_CATALOG)

# 有效网格和无效矩形网格均用整数坐标；标签仅用于标识面。
NETS = (
    ((0,1),(1,0),(1,1),(1,2),(1,3),(2,1)),
    ((0,0),(1,0),(1,1),(1,2),(1,3),(2,3)),
    ((0,0),(0,1),(1,1),(2,1),(2,2),(2,3)),
    ((0,0),(0,1),(0,2),(1,0),(1,1),(1,2)),
)


def folded_normals(cells):
    """逐个公共边旋转局部坐标架；重叠、环路矛盾、断连均不能构成正方体。"""
    points = {tuple(cell) for cell in cells}
    if len(points) != 6:
        return None
    first = next(iter(points))
    frames = {first: ((1,0,0),(0,1,0),(0,0,1))}
    pending = [first]
    neg = lambda v: tuple(-x for x in v)
    while pending:
        x, y = pending.pop()
        u, v, n = frames[(x,y)]
        for dx,dy,frame in ((1,0,(neg(n),v,u)),(-1,0,(n,v,neg(u))),
                            (0,1,(u,neg(n),v)),(0,-1,(u,n,neg(v)))):
            point = x+dx, y+dy
            if point not in points:
                continue
            if point in frames:
                if frames[point] != frame:
                    return None
            else:
                frames[point] = frame
                pending.append(point)
    normals = {point: frame[2] for point, frame in frames.items()}
    return normals if len(normals) == 6 and len(set(normals.values())) == 6 else None


def make_foundation(key, index):
    if key not in CATALOG or index < 0:
        raise ValueError('未知基础题型或参数编号')
    rng = random.Random(int.from_bytes(hashlib.sha256(f'foundation:{VERSION}:{key}:{index}'.encode()).digest(), 'big'))
    variant = index % 3
    a, b, c = (rng.randint(2, 18) for _ in range(3))
    p = {'index': index, 'variant': variant, 'a': a, 'b': b, 'c': c}
    mode, diagram = 'numeric', None
    if key in EXTRA_CATALOG:
        stem,answer=build_extra(key,p)
        steps=['先按题目的符号、位置或数量条件建立关系，再按运算顺序计算。', f'按所求量代入并核对关系，得到 {answer}。']
    elif key == 'signed-quantity':
        sign = rng.choice((-1, 1)); p['sign'] = sign
        if variant == 0:
            stem = f'规定高于基准的量记为正。某地比基准{"高" if sign>0 else "低"} {a} 米，用带符号的数表示这个相对高度（只填数值）。'
        elif variant == 1:
            stem = f'规定收入为正，支出为负。一笔{"收入" if sign>0 else "支出"}是 {a} 元，应记作多少元（只填数值）？'
        else:
            stem = f'规定温度上升记为正。一次温度{"上升" if sign>0 else "下降"} {a}℃，用带符号的数表示这次变化（只填数值）。'
        answer = sign*a
        steps = ['先确定题目规定的正方向，正负号表示方向或相反意义。', f'数量大小是 {a}，按约定应记作 {answer}。']
    elif key == 'rational-classification':
        values = [F(0), F(-a), F(b), F(-c, c+1), F(a, a+1), F(-rng.randint(20,40), 10)]
        rng.shuffle(values); p['values'] = list(map(str, values))
        predicate = (lambda x:x.denominator==1) if variant==0 else (lambda x:x.denominator==1 and x<=0) if variant==1 else (lambda x:x.denominator!=1)
        selected = [x for x in values if predicate(x)]
        word = ('整数', '非正整数（小于或等于0的整数）', '不是整数的有理数')[variant]
        stem = f'在 {"，".join(map(str,values))} 中，{word}有几个？'
        answer = len(selected)
        steps = ['分数约分后分母为1的是整数；0也是整数，但既不是正数也不是负数。', f'符合要求的数是 {"，".join(map(str,selected))}，共有 {answer} 个。']
    elif key == 'compare':
        values = rng.sample(sorted({F(-a),F(-b,b+1),F(-c,c+2),F(0),F(a,a+1),F(b)}),4)
        if variant == 1:
            values = [F(-n,n+1) for n in rng.sample(range(2,20),3)]
        rank = 0 if variant == 0 else len(values)-1 if variant==1 else 1
        p.update(values=list(map(str,values)), rank=rank)
        stem = (f'数轴上各点表示 {"，".join(map(str,values))}。最左侧的点表示哪个数？' if variant==0 else
                f'比较 {"，".join(map(str,values))}，其中最大的数是多少？' if variant==1 else
                f'将 {"，".join(map(str,values))} 从小到大排列，第2个数是多少？')
        answer = sorted(values)[rank]
        steps = ['数轴上越靠右的数越大；负数的绝对值越大，数反而越小。', f'从小到大为 {" < ".join(map(str,sorted(values)))}，所求数是 {answer}。']
    elif key == 'axis-distance':
        left, right = (-a,b) if variant==0 else (-a-b,-a)
        direction = rng.choice((-1,1)); p.update(left=left,right=right,direction=direction)
        if variant < 2:
            stem = f'数轴上 A、B 两点分别表示 {left}、{right}。AB 的距离是多少个单位长度？'
            answer = right-left
            steps = ['两点间的距离没有方向，为两坐标之差的绝对值。', f'AB = |{right}−({left})| = {answer}。']
        else:
            stem = f'数轴上 A 表示 {left}，B 在 A 的{"右" if direction>0 else "左"}侧，AB={b} 个单位长度。B 表示哪个数？'
            answer = left+direction*b
            steps = ['向右增加坐标，向左减小坐标；距离本身为非负数。', f'从 {left} 向指定方向移动 {b} 个单位，B 表示 {answer}。']
    elif key == 'scientific':
        coefficient = F(rng.randint(11,99),10) if variant==1 else F(rng.randint(1,9))
        exponent = rng.randint(2,8); value = coefficient*10**exponent
        coefficient_text = format(Decimal(coefficient.numerator)/Decimal(coefficient.denominator),'f')
        p.update(coefficient=str(coefficient),exponent=exponent,value=str(value))
        if variant < 2:
            mode = 'scientific'; answer = f'{coefficient_text}×10^{exponent}'
            stem = f'用科学记数法表示 {value}。填写 a×10^n，例如 3.2×10^5，且 1≤a<10。'
        else:
            answer = value
            stem = f'把 {coefficient}×10^{exponent} 还原为普通数（只填数值）。'
        steps = [f'系数取 {coefficient_text}，小数点移动 {exponent} 位，指数为 {exponent}。', f'检查 {coefficient_text}×10^{exponent} = {value}。']
    elif key == 'approximate':
        places = rng.randint(1,3); mode = 'decimal'
        if variant == 1:
            value = Decimal(a) + Decimal(1) - Decimal(4).scaleb(-places-1)
        else:
            value = Decimal(rng.randint(10001,99999)).scaleb(-4)
            if variant == 2:value = -value
        rounded = value.quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP)
        p.update(value=str(value),places=places); answer = format(rounded,f'.{places}f')
        stem = f'将 {value} 四舍五入，保留 {places} 位小数。答案须写出要求的小数位数（末尾的0也要保留）。'
        steps = [f'观察第 {places+1} 位小数，按四舍五入取到第 {places} 位。负数先处理绝对值再恢复符号。', f'近似数为 {answer}；末尾0用于表明精确程度。']
    elif key == 'expression-model':
        mode = 'expression'
        if variant==0:
            stem = f'每本练习本 {a} 元，另付固定配送费 {b} 元。买 x 本的总费用是多少元？用含 x 的代数式表示。'
            answer = f'{a}x+{b}'; steps = [f'x 本的书费为 {a}x 元。',f'加上一次配送费，总费用为 {answer} 元。']
        elif variant==1:
            stem = f'长方形长 x 厘米，宽 {a} 厘米。用含 x 的代数式表示周长（单位厘米）。'
            answer = f'2*(x+{a})'; steps = ['长方形周长等于长与宽之和的2倍。',f'代入数量关系，周长为 2(x+{a}) 厘米。']
        else:
            discount = rng.randint(2,9); p['discount']=discount
            stem = f'一件商品原价 x 元，先减 {a} 元，再按减价后的价格打 {discount} 折。用含 x 的代数式表示实付金额（x>{a}）。'
            answer = f'{discount}/10*(x-{a})'; steps = [f'减价后的价格是 x−{a} 元。',f'{discount}折表示乘 {discount}/10，实付金额为 ({answer}) 元。']
    elif key == 'polynomial-concept':
        m,n = rng.randint(1,4),rng.randint(1,4); coefficient = -F(a,b); p.update(m=m,n=n,coefficient=str(coefficient))
        if variant==0:
            stem = f'单项式 ({coefficient})x^{m}y^{n} 的系数是多少？';answer=coefficient
            steps = ['系数是单项式的数字因数，要包含它的负号。',f'系数为 {coefficient}，字母指数不属于系数。']
        elif variant==1:
            stem = f'单项式 -{a}x^{m}y^{n} 的次数是多少？';answer=m+n
            steps = ['单项式次数是所有字母指数的和，数字因数不参与。',f'次数是 {m}+{n}={answer}。']
        else:
            stem = f'多项式 {a}x^{m}y^{n}−{b}x^{m+n+1}+{c} 的次数是多少？';answer=m+n+1
            steps = [f'三项的次数分别是 {m+n}、{m+n+1}、0。',f'最高次项的次数是 {answer}，所以多项式为 {answer} 次。']
    elif key == 'equality':
        if variant==0:
            offset=rng.randint(-12,-1);p['offset']=offset
            stem=f'已知 x+{a}={b}。等式两边同时加 {offset}，得到 x+{a}+({offset})=□。方框内是多少？';answer=b+offset
            steps=['等式两边同时加同一个数，等式仍成立。',f'右边也必须加 {offset}，得到 {b}+({offset})={answer}。']
        elif variant==1:
            stem=f'已知 {a}x={b}。等式两边同时除以非零数 {a}，得到 x=□。方框内是多少？';answer=F(b,a)
            steps=['等式两边可以同时除以同一个非零数。',f'右边也除以 {a}，得到 {answer}。']
        else:
            stem=f'已知 (x−{a})/{b}={c}。两边同时乘 {b}，得到 x−{a}=□。方框内是多少？';answer=b*c
            steps=[f'等式两边同时乘 {b}；左边分母被约去。',f'右边也乘 {b}，得到 {b}×{c}={answer}。']
    elif key == 'geometry':
        valid = [net for net in NETS if folded_normals(net)]
        cells = rng.choice(NETS if variant==0 else valid)
        labels = rng.sample(range(1,10),6); first,second=rng.sample(range(6),2)
        normals = folded_normals(cells)
        p.update(cells=cells,labels=labels,first=first,second=second)
        diagram={'kind':'square_grid','cells':[{'x':x,'y':y,'label':str(label)} for (x,y),label in zip(cells,labels)],'caption':'相邻小正方形共享完整边；数字是面的标记。'}
        layout='；'.join(f'面{label}在第{x+1}列第{y+1}行' for (x,y),label in zip(cells,labels))
        if variant==0:
            stem=f'下面6个相同正方形能否沿公共边折成一个不重叠的正方体？能填1，不能填0。图形位置：{layout}。';answer=int(normals is not None)
            steps=['沿公共边试折，各面应对应正方体6个不同朝向；重叠或缺面都不行。', '各面可对应6个不同朝向，可以折成正方体。' if answer else '折叠时有面重叠或朝向冲突，不能折成正方体。']
        else:
            normal=normals[tuple(cells[first])]
            opposite=next(i for i,cell in enumerate(cells) if normals[tuple(cell)]==tuple(-v for v in normal))
            if variant==1:
                stem=f'下面是正方体展开图。与标有 {labels[first]} 的面相对的面标着哪个数字？图形位置：{layout}。';answer=labels[opposite]
                steps=['沿公共边折起，相对面的朝向相反，它们没有公共棱。',f'面 {labels[first]} 的相对面是面 {answer}。']
            else:
                stem=f'下面是正方体展开图。折好后，面 {labels[first]} 与面 {labels[second]} 是否共用一条棱？是填1，否填0。图形位置：{layout}。';answer=int(second!=opposite)
                steps=['正方体不同的两面若不是相对面，就共用一条棱。',f'这两个面{"相邻，共用一条棱" if answer else "相对，不共用棱"}，所以填 {answer}。']
    elif key == 'angle-bisector':
        angle=2*rng.randint(15,65); extra=rng.randint(10,35);p.update(angle=angle,extra=extra)
        if variant==0:
            stem=f'∠AOB={angle}°，射线 OC 在角内部且平分∠AOB。求∠AOC（只填度数）。';answer=F(angle,2)
            steps=['角平分线把一个角分成两个相等的角。',f'∠AOC={angle}°÷2={answer}°。']
        elif variant==1:
            stem=f'射线依次为 OA、OC、OB、OD，均在同一个小于180°的角∠AOD内部或边上。∠AOB={angle}°，OC 平分∠AOB，∠BOD={extra}°。求∠COD（只填度数）。';answer=F(angle,2)+extra
            steps=[f'∠COB={angle}°÷2={angle//2}°。',f'按射线顺序，∠COD=∠COB+∠BOD={answer}°。']
        else:
            stem=f'∠AOB={angle}°，∠BOC={extra}°，两角相邻且内部不重叠，∠AOC<180°。OM 平分∠AOB，ON 平分∠BOC。求∠MON（只填度数）。';answer=F(angle+extra,2)
            steps=[f'∠MOB={angle}/2，∠BON={extra}/2。',f'∠MON=∠MOB+∠BON=({angle}+{extra})/2={answer}°。']
    knowledge, structures = CATALOG[key]
    q={'id':f'foundation-{key}-v{VERSION}-{index}','knowledge_id':knowledge,'question_type':'m7a:'+key,
       'stem':stem,'answer':str(answer),'answer_mode':mode,'steps':steps,'hint':steps[0],'parameters':p,
       'difficulty':2 if variant==2 else 1,'common_errors':[],
       'rubric':{'max_score':1,'criterion':'按题目要求精确核验最终答案；不自动核验解题过程。'},
       'provenance':{'kind':'original_template','family':'foundations','template_version':VERSION,
                     'structure':structures[variant],'verification':'independent_math_invariant','teacher_reviewed':False}}
    if diagram:q['diagram']=diagram
    if not validate_foundation(q):raise ValueError(f'基础题核验失败：{q["id"]}')
    return q


def validate_foundation(q):
    """根据题干参数重算约束；不将生成时的答案缓存作为核验依据。"""
    key=q['question_type'].removeprefix('m7a:');p=q['parameters'];v=p['variant']
    if key not in CATALOG or v not in range(3) or q['knowledge_id']!=CATALOG[key][0]:return False
    a,b,c=p['a'],p['b'],p['c']
    actual=parse_answer(q,q['answer'])
    if key in EXTRA_CATALOG:
        return q['stem']==build_extra(key,p)[0] and validate_extra(key,p,actual) and q['difficulty'] in (1,2) and len(q['steps'])>=2
    if key=='signed-quantity':expected=p['sign']*a
    elif key=='rational-classification':
        values=list(map(F,p['values']))
        expected=sum(x.denominator==1 if v==0 else x.denominator==1 and x<=0 if v==1 else x.denominator!=1 for x in values)
    elif key=='compare':expected=sorted(map(F,p['values']))[p['rank']]
    elif key=='axis-distance':
        expected=abs(p['right']-p['left']) if v<2 else p['left']+p['direction']*b
    elif key=='scientific':
        value=F(p['value'])
        if F(p['coefficient'])*10**p['exponent']!=value:return False
        expected=(value,True) if v<2 else value
    elif key=='approximate':
        # 整数商/余数独立执行四舍五入，避免重复调用生成器的 Decimal.quantize。
        scaled=abs(F(p['value']))*10**p['places']; whole,rem=divmod(scaled.numerator,scaled.denominator)
        rounded=F(whole+int(2*rem>=scaled.denominator),10**p['places'])
        expected=(rounded*(-1 if F(p['value'])<0 else 1),p['places'])
    elif key=='expression-model':
        expected=(F(a),F(b)) if v==0 else (F(2),F(2*a)) if v==1 else (F(p['discount'],10),-F(p['discount']*a,10))
    elif key=='polynomial-concept':
        expected=F(p['coefficient']) if v==0 else p['m']+p['n'] if v==1 else max(p['m']+p['n'],p['m']+p['n']+1,0)
    elif key=='equality':expected=b+p['offset'] if v==0 else F(b,a) if v==1 else b*c
    elif key=='geometry':
        normals=folded_normals(p['cells'])
        if v==0:expected=int(normals is not None)
        elif not normals:return False
        else:
            origin=normals[tuple(p['cells'][p['first']])]; opposite=tuple(-n for n in origin)
            target=next(i for i,cell in enumerate(p['cells']) if normals[tuple(cell)]==opposite)
            expected=p['labels'][target] if v==1 else int(p['second']!=target)
    else:expected=F(p['angle'],2)+(p['extra'] if v==1 else F(p['extra'],2) if v==2 else 0)
    return actual==expected and q['difficulty'] in (1,2) and len(q['steps'])>=2


def replenish_foundations(db, minimum=6):
    """每个子任务保留6道未提交题；生成编号从既有快照恢复，无需覆盖旧题。"""
    from app.db import dumps, now
    added=0
    rows=db.execute("SELECT q.data,EXISTS(SELECT 1 FROM attempts a WHERE a.question_id=q.id AND a.student_id=current_student() AND a.status='submitted') done FROM questions q WHERE json_extract(q.data,'$.provenance.family')='foundations'").fetchall()
    available={key:[0,0,0] for key in CATALOG};indices={key:-1 for key in CATALOG}
    for row in rows:
        q=json.loads(row['data']);key=q['question_type'].removeprefix('m7a:')
        if key in CATALOG:
            indices[key]=max(indices[key],q['parameters']['index'])
            if not row['done']:available[key][q['parameters']['variant']]+=1
    for key in CATALOG:
        for _ in range(300):
            if min(available[key])>=minimum:break
            indices[key]+=1;index=indices[key];variant=index%3
            if available[key][variant]>=minimum:continue
            q=make_foundation(key,index)
            cursor=db.execute('INSERT OR IGNORE INTO questions VALUES(?,?,?,?,?)',
                (q['id'],q['knowledge_id'],hashlib.sha256(q['stem'].encode()).hexdigest(),dumps(q),now()))
            added+=cursor.rowcount;available[key][variant]+=cursor.rowcount
    return added
