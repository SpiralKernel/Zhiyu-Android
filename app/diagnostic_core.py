"""Small original diagnostic bank. Exact laws, content pinning, no model/human impersonation.

Only final objective answers are verified. Parameter variants do not certify an
entire chapter, experimental competence or written reasoning.
"""
import hashlib
import json
from fractions import Fraction as F
from functools import lru_cache

VERSION='20261015-1'
DATASET='diagnostic-core-v1'
# key: (book, goal suffix, fine type, model)
CATALOG={
 'speed':('physics-8-1','u1:g1','平均速度与路程时间换算','product'),
 'echo':('physics-8-1','u2:g1','回声往返路程测距','echo'),
 'temperature':('physics-8-1','u3:g1','温度变化与带符号读数','difference'),
 'reflection':('physics-8-1','u4:g1','入射角与镜面夹角换算','angle'),
 'mirror':('physics-8-1','u4:g1','平面镜像距与物像距离','mirror'),
 'lens':('physics-8-1','u5:g1','凸透镜物距区间与成像性质','lens'),
 'density':('physics-8-1','u6:g1','质量体积与密度换算','product'),
 'gravity':('physics-8-2','u1:g1','重力质量与g的单位','product'),
 'balance':('physics-8-2','u2:g1','水平方向二力平衡计算','balance'),
 'pressure':('physics-8-2','u3:g1','固体压强压力与受力面积','product'),
 'hydrostatic':('physics-8-2','u3:g1','液体深度与压强','product'),
 'buoyancy':('physics-8-2','u4:g1','排液体积与阿基米德浮力','product'),
 'work':('physics-8-2','u5:g1','沿力方向位移与功','product'),
 'power':('physics-8-2','u5:g1','功率功与时间换算','product'),
 'lever':('physics-8-2','u6:g1','杠杆力臂与力矩平衡','lever'),
 'heat':('physics-9-1','u1:g1','无物态变化的比热容计算','product'),
 'fuel':('physics-9-1','u2:g1','完全燃烧的热量计算','product'),
 'current':('physics-9-1','u3:g1','并联电路干支路电流','sum'),
 'voltage':('physics-9-1','u4:g1','串联电路总分电压','sum'),
 'ohm':('physics-9-1','u5:g1','同一导体欧姆定律','product'),
 'electric-power':('physics-9-1','u6:g1','电功率电压与电流','product'),
 'electric-work':('physics-9-1','u6:g1','电功电功率与通电时间','product'),
 'wave':('physics-9-2','u3:g1','真空中电磁信号传播时间','product'),
 'energy':('physics-9-2','u4:g1','能量转化的效率与损耗','difference'),
 'parallel-angle':('math-7-2','u1:g1','平行线截角与角度关系','angle'),
 'root':('math-7-2','u2:g1','算术平方根与立方根','root'),
 'real':('math-7-2','u2:g2','实数大小与整数界定','root-floor'),
 'coordinate':('math-7-2','u3:g1','平移与点的横纵坐标','sum'),
 'simultaneous':('math-7-2','u4:g1','二元一次方程组消元求值','linear-system'),
 'model':('math-7-2','u4:g2','总数总价的二元方程建模','linear-system'),
 'inequality':('math-7-2','u5:g1','负系数不等式的整数解','inequality'),
 'statistics':('math-7-2','u6:g1','频数频率与样本数量','product'),
}


def number(x):
    x=F(x)
    return str(x.numerator) if x.denominator==1 else f'{x.numerator}/{x.denominator}'


def task(key,index):
    """Build a fully specified, non-diagram task and its private constraints."""
    v=index%3;a=2+index;b=3+index
    model=CATALOG[key][3];target=v
    if key=='speed':
        names=('路程','平均速度','运动时间');units=('m','m/s','s');values=(a*b,a,b);prefix='某物体沿直线运动。'
    elif key=='density':
        names=('质量','密度','体积');units=('g','g/cm³','cm³');values=(a*b,a,b);prefix='一个实心均匀物体。'
    elif key=='gravity':
        names=('重力','质量','g');units=('N','kg','N/kg');values=(10*a,a,10);target=index%2;prefix='某物体所处位置g=10 N/kg。'
    elif key=='pressure':
        names=('压力','压强','受力面积');units=('N','Pa','m²');values=(a*b,a,b);prefix='物体垂直作用于水平受力面，接触面受力均匀。'
    elif key=='hydrostatic':
        names=('液体压强','液体密度与g的乘积','距自由液面的竖直深度');units=('Pa','N/m³','m');values=(10000*a,10000,a);target=0 if index%2==0 else 2;prefix='静止水面敞开，ρ水=1000 kg/m³，g=10 N/kg，仅求水产生的压强。'
    elif key=='buoyancy':
        names=('浮力','液体密度与g的乘积','排开液体的体积');units=('N','N/m³','m³');values=(a,10000,F(a,10000));target=0 if index%2==0 else 2;prefix='物体浸在水中且不触底，ρ水=1000 kg/m³，g=10 N/kg。'
    elif key=='work':
        names=('拉力做的功','恒定拉力','沿拉力方向的位移');units=('J','N','m');values=(a*b,a,b);prefix='恒定拉力沿直线运动方向作用于物体。'
    elif key=='power':
        names=('做的功','平均功率','时间');units=('J','W','s');values=(a*b,a,b);prefix='某装置在一段时间内对外做功。'
    elif key=='heat':
        names=('吸收热量','质量','比热容与升高温度的乘积');units=('J','kg','J/kg');values=(4200*a*b,a,4200*b);target=0 if index%2==0 else 1;prefix=f'水升温{b}℃，未沸腾且没有物态变化，c水=4200 J/(kg·℃)。'
    elif key=='fuel':
        names=('放出的热量','燃料质量','热值');units=('J','kg','J/kg');values=(30000*a,a,30000);target=index%2;prefix='某种燃料完全燃烧，热值为30000 J/kg。'
    elif key=='ohm':
        names=('电压','电流','电阻');units=('V','A','Ω');values=(a*b,a,b);prefix='温度不变的定值电阻两端电压和通过它的电流满足欧姆定律。'
    elif key=='electric-power':
        names=('实际电功率','两端实际电压','通过的电流');units=('W','V','A');values=(a*b,a,b);prefix='某用电器稳定工作。'
    elif key=='electric-work':
        names=('消耗电能','恒定电功率','通电时间');units=('J','W','s');values=(a*b,a,b);prefix='某用电器以恒定功率工作。'
    elif key=='wave':
        names=('传播距离','传播速度','传播时间');units=('m','m/s','s');values=(300000000*a,300000000,a);target=0 if index%2==0 else 2;prefix='电磁信号在真空中传播，速度为300000000 m/s。'
    elif key=='statistics':
        names=('某组频数','样本总量','该组频率');units=('人','人','');values=(a,10*a,F(1,10));prefix='随机调查一个样本，各组互斥且覆盖全部样本。'
    elif key=='echo':
        names=('人与反射墙的距离','声速','听到回声的时间');units=('m','m/s','s');values=(170*a,340,a);prefix='人和墙都静止，声速340 m/s，从发声到听到回声计时。';target=0 if index%2==0 else 2
    elif key in {'temperature','energy'}:
        names=('末温','初温','升温量') if key=='temperature' else ('输入能量','有用能量','损失能量')
        units=('℃','℃','℃') if key=='temperature' else ('J','J','J')
        values=(a+b,-a,2*a+b) if key=='temperature' else (a+b,a,b)
        prefix='某液体温度从初温变化到末温。' if key=='temperature' else '某设备转化能量，有用部分和损失部分合计等于输入能量。'
    elif key in {'current','voltage','coordinate'}:
        if key=='current':names=('干路电流','第一支路电流','第二支路电流');units=('A','A','A');prefix='电路只有两条并联支路。'
        elif key=='voltage':names=('总电压','第一电阻电压','第二电阻电压');units=('V','V','V');prefix='电源两端串联两个电阻，忽略导线压降。'
        else:names=('平移后横坐标','平移前横坐标','向右平移距离');units=('','','');prefix='平面直角坐标系中一点只向右平移，纵坐标不变。'
        values=(a+b,a,b)
    elif key in {'reflection','parallel-angle'}:
        if key=='reflection':
            names=('入射角','入射光线与镜面的锐角','反射角');prefix='光在平面镜表面发生反射，角度均在入射面内。'
        else:names=('同旁内角甲','同旁内角乙','与甲相等的内错角');prefix='两条平行直线被第三条直线所截。'
        angle=10+5*index;values=(angle,(90 if key=='reflection' else 180)-angle,angle);units=('°','°','°');target=v
    elif key=='mirror':
        names=('物到镜面的距离','像到镜面的距离','物像距离');units=('m','m','m');values=(a,a,2*a);prefix='物体在竖直平面镜前，物点、像点沿镜面法线排列。'
    elif key=='balance':
        names=('向右拉力','向左摩擦力','水平合力');units=('N','N','N');values=(a,a,0);target=index%2;prefix='物体在水平面上匀速直线运动，水平方向只受向右拉力和向左摩擦力。'
    elif key=='lever':
        names=('动力','动力臂','阻力','阻力臂');units=('N','m','N','m');values=(a,b,b,a);target=index%4;prefix='理想杠杆平衡，忽略杠杆自身重力，两个力的力臂均为垂直距离。'
    elif key=='lens':
        f=10;u=(30,25,20,15,5,8)[index]
        value=0 if u>2*f else 1 if u==2*f else 2 if u>f else 3
        return f'薄凸透镜焦距为{f}cm，物体到透镜的距离为{u}cm。忽略透镜厚度，成像性质是哪一项？',F(value),{'model':'lens','f':f,'u':u},'',['比较物距与f、2f的位置，判断实虚、倒正与大小。',('物距大于2f：倒立、缩小、实像。','物距等于2f：倒立、等大、实像。','物距在f和2f之间：倒立、放大、实像。','物距小于f：正立、放大、虚像。')[value]]
    elif key=='root':
        exponent=2 if index%2==0 else 3;n=a**exponent
        stem=f'求{n}的{"算术平方根" if exponent==2 else "立方根"}。'
        return stem,F(a),{'model':model,'n':n,'exponent':exponent},'',['依根的定义，所求数的相应次幂应等于被开方数。',f'{a}^{exponent}={n}，结果为{a}。']
    elif key=='real':
        n=a*a+1;stem=f'√{n}位于哪两个相邻整数之间？请选择其中较小的整数。'
        return stem,F(a),{'model':model,'n':n},'',[f'{a}²<{n}<{a+1}²。',f'两个相邻整数为{a}和{a+1}，较小的是{a}。']
    elif key in {'simultaneous','model'}:
        x,y=a,b;total=x+y;cost=2*x+3*y
        stem=f'解方程组 x+y={total}，2x+3y={cost}，求x。' if key=='simultaneous' else f'买两种本子共{total}本，甲每本2元，乙每本3元，总价{cost}元，甲买了多少本？'
        return stem,F(x),{'model':model,'total':total,'cost':cost},'',['把两条数量约束联立，消去另一未知数。',f'x=3×{total}−{cost}={x}，代回两式检查。']
    else:
        stem=f'不等式−{a}x>−{a*b}的整数解中，最大的整数是多少？'
        return stem,F(b-1),{'model':model,'a':a,'b':b},'',['两边除以负数，不等号方向改变。',f'x<{b}，最大的整数为{b-1}。']
    known='，'.join(f'{n}为{number(z)}{u}' for i,(n,z,u) in enumerate(zip(names,values,units)) if i!=target)
    stem=prefix+known+f'。求{names[target]}（{units[target] or "只填数值"}）。'
    laws={'product':'第一量等于第二量与第三量的乘积。','echo':'声音走往返路程，2d=vt。','difference':'先明确初末或总分关系，注意温度变化的符号。','sum':'总量等于两部分之和。','angle':'以法线或平行线角关系为依据，不凭图形外观。','mirror':'像与物到镜面等距，物像距离为两距离之和。','balance':'匀速直线运动时合力为零，两水平力大小相等。','lever':'动力×动力臂=阻力×阻力臂。'}
    formula={'speed':'v=s/t；平均速度用全程路程除以全程时间。','density':'ρ=m/V，先统一质量和体积单位。','gravity':'G=mg，质量单位kg，g单位N/kg。','pressure':'p=F/S，受力面积使用m²。','hydrostatic':'p=ρgh，h是距自由液面的竖直深度。','buoyancy':'F浮=ρ液gV排，使用排开液体的体积。','work':'W=Fs，s沿力的方向。','power':'P=W/t。','heat':'Q=cmΔt，题目中没有发生物态变化。','fuel':'Q=mq，燃料完全燃烧。','ohm':'U=IR，同一导体、温度不变。','electric-power':'P=UI，用实际电压和实际电流。','electric-work':'W=Pt，时间单位s时能量单位J。','wave':'s=vt，题目给定真空传播速度。','statistics':'频数=样本总量×频率。'}
    if key in formula:laws[model]=formula[key]
    return stem,F(values[target]),{'model':model,'values':list(map(number,values)),'target':target,'key':key},units[target],[laws[model],f'代入已知量，所求量为{number(values[target])}{units[target]}；核对单位与适用条件。']


@lru_cache(maxsize=512)
def canonical(key,index):
    bid,gid,label,_=CATALOG[key];subject,grade,term=bid.split('-')
    stem,value,spec,unit,steps=task(key,index)
    distractors=[value+1,value-1,value+2]
    values=[value,*distractors];shift=(index+len(key))%4;values=values[shift:]+values[:shift]
    if key=='lens':
        values=list(map(F,range(4)));shift=index%4;values=values[shift:]+values[:shift]
        labels=('倒立、缩小、实像','倒立、等大、实像','倒立、放大、实像','正立、放大、虚像')
        options=[{'key':chr(65+i),'text':labels[int(z)]} for i,z in enumerate(values)]
    else:
        options=[{'key':chr(65+i),'text':number(z)+(unit or '')} for i,z in enumerate(values)]
    answer=chr(65+values.index(value))
    q={'id':f'core:{VERSION}:{key}:{index}','subject':subject,'stage':'junior','grade':int(grade),'term':int(term),
       'kind':'single_choice','status':'ready','stem':stem,'options':options,'answer':answer,'steps':steps,
       'difficulty':1 if index%3<2 else 2,'difficulty_raw':None,'difficulty_basis':'直接运用定义或单一物理/数学关系；未作经验难度校准。',
       'knowledge_tags':[label],'type_tags':[label],'tags_source':'source','issues':[],
       'curriculum_goal_ids':[bid+':'+gid],'core_spec':{'key':key,'index':index,'constraint':spec,'unit':unit},
       'provenance':{'kind':'original_rule_core','dataset':DATASET,'source_id':key+':'+str(index),'version':VERSION,
                     'verification':'independent_equation_constraint','teacher_reviewed':False}}
    q['annotation']={
      'response_format':'single_choice','knowledge':{'primary':[label]},'fine_types':[label],
      'difficulty':{'level':q['difficulty'],'basis':q['difficulty_basis']},'curriculum':{'grade':int(grade),'term':int(term),'basis':'教材章节主题对齐，规则核心题','scope_status':'reviewed','goal_ids':[bid+':'+gid]},
      'answer_spec':{'mode':'choice','accepted_answers':[answer],'equivalence':'exact','constraints':['只核验最终选项；不认证步骤、实验或整章掌握。'],'unit':unit or None},
      'parts':[{'id':'p1','prompt':stem,'reference_answer':answer,'solution_steps':steps,'knowledge_tags':[label],'type_tags':[label],
         'points':1,'rubric':[{'id':'r1','description':'选择满足题目已知条件及模型约束的选项。','points':1,'evidence_required':'最终选项'}],
         'common_errors':[{'description':'忽略符号、单位或模型的适用条件。','knowledge_tags':[label]}]}],
      'grading':{'mode':'objective','full_score':1},'review':{'status':'reviewed','answer_status':'checked','method':'rule_assisted','notes':'需运行时内容重建与独立等式校验；非教师审核。'},
      'origin':{'model':'rule-engine','batch_id':VERSION}}
    return q


def constraint(spec,z):
    """A second path checks the answer by substitution, not a cached expected value."""
    m=spec['model']
    if m=='lens':
        # Independent thin-lens equation is internal only. The lesson uses the
        # textbook's object-distance intervals, not a high-school prerequisite.
        image=F(spec['f']*spec['u'],spec['u']-spec['f']);magnification=abs(image/spec['u'])
        category=3 if image<0 else 0 if magnification<1 else 1 if magnification==1 else 2
        return z==category
    if m=='root':return z>=0 and z**spec['exponent']==spec['n']
    if m=='root-floor':return z.denominator==1 and z*z<spec['n']<(z+1)**2
    if m=='linear-system':return 2*z+3*(spec['total']-z)==spec['cost']
    if m=='inequality':return z.denominator==1 and -spec['a']*z>-spec['a']*spec['b'] and -spec['a']*(z+1)<=-spec['a']*spec['b']
    v=list(map(F,spec['values']));v[spec['target']]=z
    if m=='product':return v[0]==v[1]*v[2]
    if m=='echo':return 2*v[0]==v[1]*v[2]
    if m=='difference':return v[0]==v[1]+v[2]
    if m=='sum':return v[0]==v[1]+v[2]
    if m=='angle':return v[0]==v[2] and v[0]+v[1]==(90 if spec['key']=='reflection' else 180)
    if m=='mirror':return v[0]==v[1] and v[0]+v[1]==v[2]
    if m=='balance':return v[0]-v[1]==v[2]==0
    if m=='lever':return v[0]*v[1]==v[2]*v[3]
    return False


def verified(q):
    try:
        p=q['core_spec'];key,index=p['key'],p['index']
        if not isinstance(index,int) or not 0<=index<6 or key not in CATALOG:return False
        ref=canonical(key,index)
        if q.get('display_stem',q.get('stem'))!=q.get('stem') or q.get('has_missing_assets'):return False
        if 'tags' in q:
            import unicodedata
            expected=set()
            for kind,field in [('knowledge','knowledge_tags'),('type','type_tags')]:
                for label in ref[field]:
                    normalized=''.join(unicodedata.normalize('NFKC',label).split()).casefold()
                    tid='tag:'+hashlib.sha256(f"{ref['subject']}:junior:{kind}:{normalized}".encode()).hexdigest()[:24]
                    expected.add((tid,kind,label,'source'))
            if {(t['id'],t['kind'],t['label'],t['origin']) for t in q['tags']}!=expected:return False
        # Normalization adds annotation defaults and storage fields; compare every
        # educational field including complete normalized annotation, not a JSON flag.
        from app.question_annotation import Annotation
        for k in ('subject','stage','grade','term','kind','stem','options','answer','steps','difficulty','knowledge_tags','type_tags','curriculum_goal_ids','core_spec','provenance'):
            if q.get(k)!=ref[k]:return False
        if Annotation.model_validate(q['annotation'])!=Annotation.model_validate(ref['annotation']):return False
        text=next(o['text'] for o in q['options'] if o['key']==q['answer']);unit=p['unit']
        z=F(('倒立、缩小、实像','倒立、等大、实像','倒立、放大、实像','正立、放大、虚像').index(text)) if key=='lens' else F(text[:-len(unit)] if unit else text)
        return constraint(p['constraint'],z) and not q.get('evidence_invalidated')
    except (KeyError,ValueError,TypeError,StopIteration,ZeroDivisionError):return False


def trusted(q):
    return not q.get('evidence_invalidated') and (q.get('provenance',{}).get('teacher_reviewed') is True or verified(q))


def types_for_book(bid):
    from app.bank import normalized
    out=[]
    for key,(book,gid,label,_) in CATALOG.items():
        if book!=bid:continue
        subject=book.split('-')[0]
        tid='tag:'+hashlib.sha256(f'{subject}:junior:type:{normalized(label)}'.encode()).hexdigest()[:24]
        out.append({'id':tid,'name':label,'unit_id':bid+':'+gid.split(':')[0],'goal_id':bid+':'+gid,
                    'can_do':'在题目条件下独立运用这一关系；需另行核对书面过程和实验表现。','classification_reviewed':True})
    return out


def seed(db):
    from app import bank
    records=[json.loads(json.dumps(canonical(key,i),ensure_ascii=False)) for key in CATALOG for i in range(6)]
    if not all(verified(q) for q in records):raise ValueError('核心题没有通过独立约束核验')
    # Skip unchanged startup imports to avoid audit churn.
    existing={r['id'] for r in db.execute('SELECT id FROM bank_questions WHERE source_id=?',(DATASET,))}
    records=[q for q in records if q['id'] not in existing]
    if not records:return {'inserted':0}
    result=bank.import_records(db,DATASET,records,{'title':'人教初中数学物理·原创规则核心题','version':VERSION,'scope':'math-7-2,physics-8/9','origin':'original','verified':'runtime independent constraints; not teacher review'},transaction=False)
    for bid in {v[0] for v in CATALOG.values()}:
        b=bid.split('-')
        for t in types_for_book(bid):
            data={**t,'subject':b[0],'grade':int(b[1]),'term':int(b[2]),'source':'rule','needs_review':False,'description':t['can_do']}
            db.execute('INSERT OR IGNORE INTO question_types VALUES(?,?,?,?,?,?)',(t['id'],b[0],int(b[1]),int(b[2]),bank.normalized(t['name']),json.dumps(data,ensure_ascii=False)))
    return result
