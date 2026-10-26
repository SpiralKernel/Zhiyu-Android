"""十二类原先只有挑战题的基础子任务；公式核验与生成分开。"""
from fractions import Fraction as F

CATALOG = {
 'axis-transform':('opposite',('先平移再对称','先对称再平移','关于指定点对称')),
 'absolute-condition':('absolute',('由符号确定分式','分式分母符号','绝对值条件代入')),
 'fraction-add':('addition',('异分母加法','减去负分数','三项分数加减')),
 'fraction-multiply':('multiply',('负分数相乘','分数除法','乘除顺序')),
 'power-mixed':('power',('幂前负号加法','负底数乘方减法','乘方与乘法顺序')),
 'quadratic-substitution':('substitution',('平方项与常数','平方项与一次项','平方二项式代入')),
 'multi-letter-terms':('like_terms',('相同字母项合并','不同字母项辨别','字母顺序变换')),
 'nested-brackets':('brackets',('两层负号','外层系数分配','内层系数分配')),
 'fraction-equation':('linear',('单分母方程','分式两边方程','括号与分母方程')),
 'two-products':('word_equation',('两商品等量','两商品差量','两商品倍量')),
 'two-midpoints':('segment',('连续两中点','内点两侧中点','两中点求全长')),
 'angle-model':('angle',('补角倍数','余角倍数','平角三分关系')),
}


def build(key,p):
    a,b,c,v=p['a'],p['b'],p['c'],p['variant'];x=-c
    if key=='axis-transform':
        stem=(f'数轴上点A表示−{a}。先向右平移{b}个单位，再关于原点对称，所得点表示哪个数？',f'数轴上点A表示−{a}。先关于原点对称，再向左平移{b}个单位，所得点表示哪个数？',f'数轴上点A表示−{a}，对称中心表示{b}，A关于该中心的对称点表示哪个数？')[v]
        ans=(a-b,a-b,2*b+a)[v]
    elif key=='absolute-condition':
        expressions=(f'(x+y)/(x−y)',f'(x−y)/(x+y)',f'(x+2y)/(x−y)')
        # v1 explicitly excludes zero denominator by using y=a+b.
        y=a+b
        stem=f'已知|x|={a}且x<0，|y|={y}且y>0，求{expressions[v]}。'
        ans=(F(-a+y,-a-y),F(-a-y,-a+y),F(-a+2*y,-a-y))[v]
    elif key=='fraction-add':
        stem=(f'计算 (−{a}/{b})+{c}/{b+1}。',f'计算 {a}/{b}−(−{c}/{b+1})。',f'计算 (−{a}/{b})+{c}/{b+1}−1。')[v]
        ans=(-F(a,b)+F(c,b+1),F(a,b)+F(c,b+1),-F(a,b)+F(c,b+1)-1)[v]
    elif key=='fraction-multiply':
        stem=(f'计算 (−{a}/{b})×(−{c}/{b+1})。',f'计算 (−{a}/{b})÷(−{c}/{b+1})。',f'计算 (−{a}/{b})÷({c}/{b+1})×(−2)。')[v]
        ans=(F(a*c,b*(b+1)),F(a*(b+1),b*c),F(2*a*(b+1),b*c))[v]
    elif key=='power-mixed':
        stem=(f'计算 −{a}²+{b}。',f'计算 (−{a})²−{b}。',f'计算 −{a}²+2×(−{b})。')[v]
        ans=(-a*a+b,a*a-b,-a*a-2*b)[v]
    elif key=='quadratic-substitution':
        expr=(f'{a}x²+{b}',f'x²+{a}x',f'(x+{a})²')[v]
        stem=f'当x={x}时，求{expr}的值。'
        ans=(a*x*x+b,x*x+a*x,(x+a)**2)[v]
    elif key=='multi-letter-terms':
        stem=(f'合并 {a}xy−{b}xy，所得xy项的系数是多少？',f'合并 {a}x²y+{b}xy²−{c}x²y，所得x²y项的系数是多少？',f'合并 {a}xy+{b}yx−{c}xy，所得xy项的系数是多少？')[v]
        ans=(a-b,a-c,a+b-c)[v]
    elif key=='nested-brackets':
        expr=(f'x−[{a}−({b}−x)]',f'{a}−2[({b}−x)−{c}]',f'{a}−[{b}−2(x−{c})]')[v]
        stem=f'当x={x}时，计算{expr}。'
        ans=(b-a,a-2*(b-x-c),a-b+2*(x-c))[v]
    elif key=='fraction-equation':
        target=c;right=F(target+a,b);right2=F(target+a,b)-F(target,b+1);right3=F(2*(target-a),b)
        stem=(f'解方程 (x+{a})/{b}={right}。',f'解方程 (x+{a})/{b}−x/{b+1}={right2}。',f'解方程 2(x−{a})/{b}={right3}。')[v]
        ans=target
    elif key=='two-products':
        count=c;other=(count,count+b,2*count)[v];total=a*count+(a+1)*other
        relation=('两种各买相同的数量',f'乙比甲多买{b}件','乙的数量是甲的2倍')[v]
        stem=f'甲每件{a}元，乙每件{a+1}元。{relation}，共付{total}元。甲买了多少件？'
        ans=count
    elif key=='two-midpoints':
        stem=(f'线段AB长{4*a}厘米，M为AB中点，N为AM中点。MN长多少厘米？',f'点C在线段AB内部，AC={2*a}厘米，CB={2*b}厘米。M、N分别是AC、CB的中点。MN长多少厘米？',f'M是AB中点，N是AM中点，已知MN={a}厘米。AB长多少厘米？')[v]
        ans=(a,a+b,4*a)[v]
    else:
        ratio=a;total=180 if v!=1 else 90
        stem=(f'两角互补，大角是小角的{ratio}倍。小角是多少度？',f'两角互余，大角是小角的{ratio}倍。小角是多少度？',f'三个相邻且不重叠的角组成平角，度数之比为1:{ratio}:{ratio+1}。最小的角是多少度？')[v]
        ans=F(total,ratio+1 if v<2 else 2*ratio+2)
    return stem,ans


def validate(key,p,value):
    """以等式约束或另一运算顺序检验答案，不读取生成器答案。"""
    a,b,c,v=p['a'],p['b'],p['c'],p['variant'];z=F(value);x=-c
    if key=='axis-transform':return (z+(-a+b)==0 if v==0 else z+b==a if v==1 else (z-a)/2==b)
    if key=='absolute-condition':
        xx,yy=-a,a+b
        return (z*(xx-yy)==xx+yy if v==0 else z*(xx+yy)==xx-yy if v==1 else z*(xx-yy)==xx+2*yy)
    if key=='fraction-add':return (z*b*(b+1)==-a*(b+1)+c*b if v==0 else z*b*(b+1)==a*(b+1)+c*b if v==1 else (z+1)*b*(b+1)==-a*(b+1)+c*b)
    if key=='fraction-multiply':return (z*b*(b+1)==a*c if v==0 else z*b*c==a*(b+1) if v==1 else z*b*c==2*a*(b+1))
    if key=='power-mixed':return (z+a*a==b if v==0 else z+b==(-a)*(-a) if v==1 else z+a*a==-2*b)
    if key=='quadratic-substitution':return (z-b==a*c*c if v==0 else z==c*(c-a) if v==1 else z==(a-c)*(a-c))
    if key=='multi-letter-terms':return (z+b==a if v==0 else z+c==a if v==1 else z+c==a+b)
    if key=='nested-brackets':return (z+a==b if v==0 else z==a-2*b+2*x+2*c if v==1 else z==a-b+2*x-2*c)
    if key=='fraction-equation':return (F(z+a,b)==F(c+a,b) if v==0 else F(z+a,b)-F(z,b+1)==F(c+a,b)-F(c,b+1) if v==1 else F(2*(z-a),b)==F(2*(c-a),b))
    if key=='two-products':
        other=(c,c+b,2*c)[v];target=a*c+(a+1)*other
        return (a*z+(a+1)*(z if v==0 else z+b if v==1 else 2*z)==target and z>=0 and z.denominator==1)
    if key=='two-midpoints':return (4*z==4*a if v==0 else 2*z==2*a+2*b if v==1 else z==4*a)
    if key=='angle-model':return z*(a+1 if v<2 else 2*a+2)==(90 if v==1 else 180) and z>0
    return False
