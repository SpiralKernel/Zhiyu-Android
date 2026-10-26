"""Controlled IDs for offline calibration; source-bank/model labels are never a catalog."""
import hashlib
import json
from pathlib import Path

from app.course_catalog import BOOK_MAP, GOALS
from app.math_catalog import TYPES
from app.diagnostic_core import types_for_book

VERSION = 'calibration-tags-2026.10.17-1'

# Maintained task definitions, not labels promoted from imported questions.
EXTRA = {
 'math-7-2': [('u1:g1','parallel-proof','平行线判定与角关系证明','区分平行的判定条件和已知平行后的角关系。'),
              ('u1:g2','translation','平移距离方向与对应点','依据对应点确定平移方向和距离。')],
 'math-8-1': [('u1:g1','triangle-angle','三角形内外角计算','依据内角和与外角关系列式求角。'),
              ('u1:g1','triangle-side','三角形三边关系与范围','用两边之和大于第三边确定边长范围。'),
              ('u2:g1','congruence','全等三角形判定及对应关系','写出充分的全等条件并核对对应顶点。'),
              ('u3:g1','isosceles','等腰三角形边角关系','结合等边对等角及三线合一的适用条件推理。'),
              ('u3:g1','symmetry','轴对称与垂直平分线','利用对称点、对称轴或垂直平分线性质。'),
              ('u4:g1','power','幂的运算法则与整式乘法','明确底数与指数，按法则展开并合并同类项。'),
              ('u5:g1','factor','提公因式与公式法分解因式','提取公因式或识别平方差、完全平方结构。'),
              ('u6:g1','fraction','分式化简与运算','保留分母非零条件，约分或通分后计算。'),
              ('u6:g1','fraction-equation','分式方程去分母并验根','去分母不漏项，解整式方程后排除增根。')],
 'math-8-2': [('u1:g1','radical','二次根式化简与运算','核对被开方数非负，化简后合并同类根式。'),
              ('u2:g1','pythagoras','勾股定理求边与逆定理判定','确认直角或验证边长平方关系。'),
              ('u3:g1','quadrilateral','特殊四边形性质与判定','区分性质和判定，使用充分条件进行证明。'),
              ('u4:g1','function','函数关系式与自变量范围','从数量关系建立函数并考虑实际定义域。'),
              ('u5:g1','linear-function','一次函数解析式与图象应用','用点或情境求系数，并解释图象和交点。'),
              ('u6:g1','statistics','平均数中位数众数与方差','按数据求统计量并说明各统计量的意义。')],
 'math-9-1': [('u1:g1','quadratic','一元二次方程求解与根的条件','选择配方、公式或因式分解，检查判别式及实际范围。'),
              ('u2:g1','parabola','二次函数顶点交点与最值','确定解析式、顶点和定义域，讨论情境最值。'),
              ('u3:g1','inverse','反比例函数解析式与图象','利用乘积不变求参数并解释象限和变化。'),
              ('u4:g1','rotation','旋转对应点与中心对称','核对旋转中心、方向、角度和对应关系。'),
              ('u5:g1','circle','圆周角圆心角与弦的关系','确认同弧等条件，使用圆中角弦关系。'),
              ('u6:g1','tangent','圆的切线判定与性质','以过切点的半径垂直切线等充分条件推理。')],
 'math-9-2': [('u1:g1','similar','相似三角形判定与比例求值','对应顶点一致，依据充分条件建立对应边比例。'),
              ('u2:g1','trigonometry','锐角三角函数与解直角三角形','确定对边邻边斜边，结合角度和实际单位求值。'),
              ('u3:g1','views','三视图与几何体对应关系','对齐主视左视俯视的尺寸与位置。'),
              ('u4:g1','probability','列表树状图与等可能概率','明确样本空间及等可能条件，避免重复和遗漏。'),
              ('u4:g2','model','综合情境建模与条件检验','明确假设、建立关系、求解并验证实际条件。')],
}


def catalog(book_id):
    if book_id not in BOOK_MAP:
        raise ValueError('未知教材册次')
    book = BOOK_MAP[book_id]
    tags = []
    order=list(BOOK_MAP)
    for gid,g in GOALS.items():
        other=BOOK_MAP[g['book_id']]
        if other['subject']!=book['subject']:continue
        if book.get('stage','junior')=='junior':
            if other.get('stage','junior')!='junior' or (other.get('grade',0),other.get('term',0))>(book.get('grade',0),book.get('term',0)):continue
        elif other.get('stage')=='senior' and order.index(g['book_id'])>order.index(book_id):continue
        tags.append({'id':'k:'+gid,'kind':'knowledge','name':g['name'],
                     'definition':g.get('can_do') or g['name'], 'aliases':g.get('aliases',[]),
                     'goal_ids':[gid], 'book_id':g['book_id']})
    types = TYPES if book_id == 'math-7-1' else types_for_book(book_id)
    for t in types:
        tags.append({'id':t['id'],'kind':'type','name':t['name'],'definition':t['can_do'],
                     'aliases':t.get('aliases',[]),'goal_ids':[t['goal_id']], 'book_id':book_id})
    if book['subject'] == 'physics' and book.get('stage', 'junior') == 'junior':
        from app.physics_textbooks import types_for_book as textbook_types
        for t in textbook_types(book_id):
            tags.append({'id':t['id'],'kind':'type','name':t['name'],'definition':t['can_do'],
                         'aliases':t['aliases'],'goal_ids':[t['goal_id']], 'book_id':book_id,
                         'section_id':t['section_id']})
    for goal,key,name,definition in EXTRA.get(book_id,[]):
        tags.append({'id':f'ft:{book_id}:{key}','kind':'type','name':name,'definition':definition,
                     'aliases':[],'goal_ids':[book_id+':'+goal],'book_id':book_id})
    if book.get('stage')=='senior':
        skills=Path(__file__).parent/'data'/f'senior_{book["subject"]}_foundation_skills.json'
        if skills.is_file():
            for skill in json.loads(skills.read_text())['skills']:
                if skill['book_id']==book_id:
                    tags.append({'id':skill['id'],'kind':'type','name':skill['name'],'definition':skill['requirement'],
                                 'aliases':[],'goal_ids':skill['goal_ids'],'book_id':book_id})
    if book['subject']=='math':
        for key,name,definition in [('sign','符号处理错误','学生算式中可定位的正负号或变号错误。'),
              ('domain','未检查取值条件','忽略分母非零、根式非负或实际范围等必要条件。'),
              ('operation','运算规则使用错误','能明确指出所用法则或运算次序与本题条件不符。'),
              ('correspondence','几何对应关系错误','混淆已命名的对应顶点、边、角或图形位置。')]:
            tags.append({'id':'err:math:'+key,'kind':'error','name':name,'definition':definition,
                         'aliases':[],'goal_ids':[], 'book_id':book_id})
        for key,name in [('equation','方程建模'),('cases','分类讨论'),('substitution','代入检验'),('equivalence','等价变形')]:
            tags.append({'id':'method:math:'+key,'kind':'method','name':name,'definition':'本题解法实际使用'+name+'，仅作为方法标签。',
                         'aliases':[],'goal_ids':[], 'book_id':book_id})
    data={'schema_version':1,'version':VERSION,'book_id':book_id,'subject':book['subject'],
          'stage':book.get('stage','junior'),'tags':tags}
    if book['subject'] == 'physics' and book.get('stage', 'junior') == 'junior':
        from app.physics_textbooks import VERSION as textbook_version
        data['version'] = VERSION + ':' + textbook_version
    data['sha256']=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return data


def selection(tags, ids, kind):
    if len(ids)!=len(set(ids)):
        raise ValueError('标签ID重复')
    result=[]
    for tid in ids:
        tag=tags.get(tid)
        if not tag or tag['kind']!=kind:
            raise ValueError('标签不存在、类别错误或超出当前册次：'+tid)
        result.append(tag)
    return result
