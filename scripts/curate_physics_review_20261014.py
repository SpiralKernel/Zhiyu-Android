"""Reproduce the adjudicated first physics review; does not open student databases."""
import copy
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.admin import Draft
from app.physics_review import ReviewItem, snapshot_hash, validate_proposal
from app.question_annotation import Annotation, source_fingerprint

DATA=ROOT/'app/data'
INPUT=ROOT/'data/annotations/physics-audit-20261014'


def part(prompt, answer, steps, tags, types, evidence):
    return dict(id='pending',prompt=prompt,reference_answer=answer,solution_steps=steps,
                knowledge_tags=tags,type_tags=types,depends_on=[],points=None,
                rubric=[dict(id='c'+str(i+1),description=s,evidence_required=s,points=None) for i,s in enumerate(evidence)],common_errors=[])


def rebuild(form, *, answer, steps, tags, types, parts, fmt=None, kind=None):
    form.update(answer=answer,steps=steps,knowledge_tags=tags,type_tags=types)
    if kind:form['kind']=kind
    a=form['annotation']
    a['knowledge']={'primary':tags,'supporting':[],'prerequisites':[]}
    a['fine_types']=types
    for i,p in enumerate(parts):p['id']='p'+str(i+1)
    a['parts']=parts
    if fmt:a['response_format']=fmt
    mode='choice' if form['kind']!='reference' else 'multipart' if len(parts)>1 else 'numeric'
    a['answer_spec'].update(mode=mode,accepted_answers=[answer] if mode=='choice' else [],equivalence='exact' if mode=='choice' else 'manual')
    a['grading']['mode']='objective' if mode=='choice' else 'manual'
    return form


def main():
    inputs={}
    for name in ('B1-input.jsonl','B3-input.jsonl','B4-input.jsonl','B4-reserves.jsonl','B2-materials-extra-input.jsonl'):
        for line in (INPUT/name).read_text().splitlines():
            r=json.loads(line);inputs[r['question_id']]=r
    rows=[]
    for name in ('b1_revised','b3','b4','b4_extra','materials'):
        rows.extend(json.loads((DATA/f'physics_audit_{name}_20261014.json').read_text()))
    if len({r['question_id'] for r in rows})!=len(rows):raise ValueError('审核题号重复')
    records={r['question_id']:r for r in rows}
    def get(suffix):return records['bank:cjeval:'+suffix]

    # Repaired choice forms must change both legacy kind and annotation format.
    for suffix in ('31ded231f3e578a602a18cfd','40aba870202cca5176a2a368','4ca94c187a461ffafb1e62fb','b45f6cb9ad58d2a5998d1bbf'):
        f=get(suffix)['proposed_form'];f['kind']=f['annotation']['response_format']
    get('40aba870202cca5176a2a368')['proposed_form']['stem']='实例：①针孔相机成像；②通过潜望镜观察的像；③用放大镜观察物体的像；④幻灯机在屏幕上的像；⑤照相机在感光元件上的像。下列成像分类哪项正确？'

    # B3: correct the reviewed draft, not the original reference answer.
    r=get('69bae0c949076edff9dd6b68');f=r['proposed_form'];f['kind']='single_choice'
    lines=['A：放热可能经历等温物态变化，不必降温。','B：比热容还与物质状态有关，不能说仅由种类决定。',
           'C：破镜分开后分子作用范围不足，不能归因为排斥力。','D：热传递取决于温差，不取决于总内能大小；小而热的物体可以向大而冷的物体传热。']
    rebuild(f,answer='D',steps=lines,tags=['比热容与物态','热传递方向与温度'],types=['辨析比热容状态依赖及热传递的温差条件'],
            parts=[part('选出唯一正确的物理陈述。','D',lines,['比热容与物态','热传递方向与温度'],['辨析比热容状态依赖及热传递的温差条件'],lines)],fmt='single_choice')
    r['independent_solution']=lines;r['source_conflicts'].append('来源BD把仅取决于种类的B当真；字面上B不成立，修订答案D。')
    r['quarantine_original']=True
    r=get('3d6c72967d1566354fc642f5');f=r['proposed_form']
    f['stem']='按标准大气压下冰水混合物0℃、沸水100℃标定。'+f['stem']
    f['annotation']['answer_spec']['constraints'].append('校准采用标准大气压的0℃、100℃两点，示值与实际温度为线性关系。')
    r['resolved_findings'].append('仅在修订草稿中补明常压校准假设；T=100(r+0.7)/103，r=-6时约-5.1456℃，T=r时23.333…℃。')
    r=get('32297f27bd60755f22d6dfdb');f=r['proposed_form']
    f['stem']='下列实验描述及由该观察足以支持的结论，哪些正确？'
    f['steps'][0]='A的观察同时可能有桌面固体和空气传播路径，未隔离路径，不能据此证明空气传声。'
    f['annotation']['parts'][0]['solution_steps']=list(f['steps'])
    f['options'][-1]['text']='无材料损失时将铁块锻造成铁片，质量不变，说明质量不因形状改变而改变。'
    for c in f['annotation']['parts'][0]['rubric']:
        if '固体' in c['description'] or '固体' in c['evidence_required']:
            c.update(description='A未隔离固体与空气传播路径，不能据此推出空气传声。',evidence_required='说明存在多条传播路径，观察不足以区分介质；B/C/D分别用蒸发吸热、凸透镜会聚与无损失质量不变判断。')
    r['resolved_findings'].append('限定为观察足以支持的结论；不宣称该实验排除了空气传播。')
    r=get('132956f695796c5cec94b57c');r['quarantine_original']=True
    r['proposed_form']['stem']='以整灯接220V市电的输入端为电流和功率测量对象。'+r['proposed_form']['stem']
    r['source_conflicts'].append('原题未限定LED台灯供电电压；若按低压灯头测电流，0.5A也可能正常。草稿明确220V整灯输入口径，原题待核。')
    r=get('aed752cce2c4841050937f68');r['quarantine_original']=True
    r=get('c355e201ff53d6b07b32dcbb');f=r['proposed_form']
    f['annotation']['answer_spec']['constraints'].append('a、b两列也可交换为总厚度/mm和纸张数，只要单位、厚度=总厚度/张数的关系自洽。')
    for p in f['annotation']['parts']:
        if '平均' in p['prompt']:
            for c in p['rubric']:
                c['description']=c['description'].replace('减小误差','减小随机误差');c['evidence_required']=c['evidence_required'].replace('减小误差','减小随机误差')
    r=get('f4979e80f78fb9e19f1cb3c7');r['proposed_form']['stem']=r['proposed_form']['stem'].replace('环境声音强度','环境声级')

    # B4: two peer-detected mismatches and an ambiguous direction must not survive.
    r=get('0f14d0a37daae83abceb3553');r['quarantine_original']=True
    r['proposed_form']['stem']+='请明确按每千克售价比较，计算中采用题给各季密度及相同瓶容积。'
    r['source_conflicts'].append('来源写夏季价格高；每瓶和每千克两种口径均为冬季更高，故原题继续隔离。')
    r=get('03559a73661ef3530190e032');r['proposed_form']['answer']='A'
    r['resolved_findings'].append('修正AI草稿把500N作为选项答案的错误：整题、可接受答案和小问均统一为A。')
    r=get('059e4830fd7d55850b6f4d95');f=r['proposed_form']
    steps=['V酒精=600×75%=450mL，V水=150mL。','m酒精=0.8×450=360g，m水=1×150=150g。',
           '忽略混合体积变化，ρ混合=(360+150)/600=0.85g/cm³=850kg/m³。']
    rebuild(f,answer='酒精360g，水150g；消毒液密度0.85g/cm³',steps=steps,tags=['密度公式','混合物质量与体积'],
            types=['按体积分数分配体积并用质量加和求混合液密度'],parts=[
              part('（1）求酒精和水的质量。','酒精360g，水150g',steps[:2],['密度公式','体积分数'],['由体积分数求组分体积再求质量'],steps[:2]),
              part('（2）求消毒液密度。','0.85g/cm³（850kg/m³）',steps[2:],['混合物密度'],['忽略混合体积变化后用总质量除以总体积'],steps[2:])],fmt='composite')
    r['independent_solution']=steps;r['resolved_findings'].append('废弃错配的长度测量答案、知识标签、解析和rubric，按本题密度任务全部重建。')
    r=get('18dc93d19b53f3f94b77610e');f=r['proposed_form']
    steps=['铝材料体积V=1.35/2700=0.0005m³，小于外体积0.0012m³，故空心。','空腔体积0.0012-0.0005=0.0007m³；取水密度1000kg/m³，注水质量0.7kg，总质量1.35+0.7=2.05kg。']
    f['stem']+='取水的密度为1000kg/m³。'
    rebuild(f,answer='空心；注水后总质量2.05kg',steps=steps,tags=['密度公式','空心物体的质量和体积'],types=['由材料体积与外体积比较判断空心','由空腔体积求注水质量再质量加和'],parts=[part('判断铝球是否空心。','空心',steps[:1],['密度公式','空心判断'],['由材料体积与外体积比较判断空心'],steps[:1]),part('空腔注满水后求总质量。','2.05kg',steps[1:],['体积差与质量加和'],['由空腔体积求注水质量再质量加和'],steps[1:])],fmt='composite')
    r['resolved_findings'].append('把原题的判断任务和注水质量任务分别建立小问，避免将两问计成一个单问。')
    r=get('03899a2d29af25def87c89c7');f=r['proposed_form'];r['quarantine_original']=True
    f['stem']='在有月光的夜晚，为避免踩入水平地面上的积水，比较迎着月光和背着月光行走时积水与粗糙路面的明暗，选择正确策略。'
    for o in f['options']:o['text']=o['text'].replace('逆光','背着月光')
    f['steps']=['迎着月光观察时，水平水面的镜面反射光较易进入眼睛，积水显亮，应避开亮处。',
                '背着月光观察时，水面镜面反射光不易入眼，粗糙路面有漫反射，积水相对暗，应避开暗处。故选A。']
    f['annotation']['parts'][0]['solution_steps']=f['steps']
    for c in f['annotation']['parts'][0]['rubric']:
        c.update(description='区分镜面反射和漫反射，并对应迎月光避亮、背月光避暗。',evidence_required='解释迎光水面较亮、背光水面较暗；选择A。')
    r['source_conflicts'].append('原选项把迎着月光与逆光混用，方位不明确；仅在草稿中显式改成背着月光。')
    r=get('046b3adee8cd2544f15b766c');r['proposed_form']['options'][-1]['text']='质量相同的实心固体，体积较大的材料密度较小。'
    r['resolved_findings'].append('草稿限定D为实心固体，避免物体外形体积与材料体积混淆。')
    r=get('0524072734cc0280f72572eb');f=r['proposed_form']
    f['stem']='填写换算后的单位符号：（1）某微小颗粒直径0.1μm=100__；（2）某款电动自行车的设计最高速度25000m/h=25__。'
    f['annotation']['parts'][0]['prompt']='把0.1μm换算为100，填写相应单位符号。'
    f['annotation']['parts'][1]['prompt']='把25000m/h换算为25，填写相应速度单位符号。'
    f['steps']=['0.1μm=100nm，故第一空nm。','25000m/h=25km/h，故第二空km/h。']
    for p,step in zip(f['annotation']['parts'],f['steps']):
        p['solution_steps']=[step]
        for c in p['rubric']:c.update(description=step,evidence_required=step)
    r['resolved_findings'].append('仅在草稿中改为给定设计速度的单位题，不再把历史法规当作现行规范。')
    r=get('0541fa3adbf5ce6c460fe45a');f=r['proposed_form']
    labels=[('时间单位换算','小时换算为秒乘3600'),('质量单位换算','千克换算为克乘1000'),
            ('长度单位换算','千米换算为米乘1000'),('体积单位换算','毫升与立方厘米等量换算'),
            ('速度单位换算','千米每小时换算为米每秒除以3.6'),('密度单位换算','克每立方厘米换算为千克每立方米乘1000')]
    f['type_tags']=[t for _,t in labels];f['annotation']['fine_types']=f['type_tags']
    for p,(k,t) in zip(f['annotation']['parts'],labels):p['knowledge_tags']=[k];p['type_tags']=[t]

    # B2: four image flags can be checked from their existing text tables.
    r=get('510843fdebf1a63d2eeac469');f=r['proposed_form']
    f['stem']=f['stem'].replace('轻质圆柱容器','上口敞开、允许水自然溢出的轻质圆柱容器')
    r['independent_solution']=['取草稿明确的g=9.8：初始水质量1000×0.03×0.4=12kg，底压1000×9.8×0.4=3920Pa。',
      '由水底压强增加147Pa，液面上升147/(1000×9.8)=0.015m。新增容水体积0.03×0.015=0.00045m³。',
      '排水体积0.0015m³大于新增容水体积，故溢水体积0.00105m³、质量1.05kg；不要求初始装满。',
      '容器对地压强增980Pa对应净质量增加980×0.03/9.8=3kg，球质量4.05kg，密度2700kg/m³。']
    f['steps']=r['independent_solution'];f['annotation']['parts'][2]['solution_steps']=r['independent_solution'][1:]
    r['resolved_findings'].append('表中两压差均已在来源文本；由体积差推出溢水，不采纳二审所提与液面上升矛盾的“初始满容器”条件。')
    r=get('506bcfb4572253919ff7c6bb');f=r['proposed_form'];original=inputs[r['question_id']]['question']['stem']
    f['stem']=original.replace('说明书如图所示','说明书的参数如下方文字表所列')+'\n取c水=4.2×10³J/(kg·℃)、ρ水=1000kg/m³；最后一问可给单位面积入射功率或1s内1m²获得的能量。'
    a=f['annotation'];p3=a['parts'][2];p4=a['parts'][3]
    p3['reference_answer']='4.2×10⁶J；约1944.44W/m²（等价于1s内1m²获得约1944.44J）'
    p3['solution_steps']=list(dict.fromkeys(p3['solution_steps']+p4['solution_steps']))
    p3['rubric']=[dict(id='heat',description='Q=cmΔT计算水每小时吸热量。',evidence_required='Q=4200×100×10=4.2×10⁶J。',points=None),
                 dict(id='irradiance',description='由效率和面积、时间求入射功率面密度。',evidence_required='4.2×10⁶/(0.4×1.5×3600)=1944.44，单位W/m²；或明确1s、1m²对应的J。',points=None)]
    a['parts']=a['parts'][:3];f['answer']='控制变量法；黑色；4.2×10⁶J及约1944.44W/m²'
    r['resolved_findings'].append('保留完整文字实验表和说明书参数；第3问两个所求量合在原小问中，不虚构第4问。')
    for suffix in ('6629661604548bd778178685','2724e1f8b5fc7ded04fa682b'):
        f=get(suffix)['proposed_form']
        f['stem']=f['stem'].replace('以80km/h行驶','以80km/h匀速行驶').replace('为使(2)(3)唯一，草稿补充行驶速度恒定。','')
        f['stem']=f['stem'].replace('草稿显式补充地面附近g=10N/kg。','地面附近取g=10N/kg。')
    r=get('1b3df8e6f035b7479c4ca962');r['proposed_form']['stem']=r['proposed_form']['stem'].replace('面积120m²墙体原用','原用')
    # The ordinary passive-drag model gives a repair, while the original key stays isolated.
    r=get('8aef648b72b5b72f1f636e58');q=inputs[r['question_id']]['question']
    f=copy.deepcopy(get('40aba870202cca5176a2a368')['proposed_form']);f['options']=copy.deepcopy(q['options'])
    f['stem']='球竖直上抛后只受重力和空气阻力，无其他物体对球做正功。M、N对应运动中两次观测时刻：M动能6J、重力势能9J；N动能10J、重力势能3J。判断下列哪项正确。'
    steps=['EM=6+9=15J，EN=10+3=13J；空气阻力使机械能不增加，故M先于N。',
           'N重力势能更小，即位置更低；在M之后经过更低的N，N处于下降阶段。','N动能更大故速度更大；A、B、C错误，D正确。']
    rebuild(f,answer='D',steps=steps,tags=['机械能与阻力做功','动能和重力势能'],types=['利用阻力耗能与高度变化判别运动先后和上下降阶段'],
            parts=[part('依据两个时刻的能量判断运动状态，选择正确项。','D',steps,['机械能与阻力做功','重力势能与高度'],['利用阻力耗能与高度变化判别运动阶段'],steps)],fmt='single_choice',kind='single_choice')
    r.update(decision='repair_draft',proposed_form=f,independent_solution=steps,
             rationale='来源CD中的C与耗能条件及解析自己的先后说明冲突。修订草稿明确仅重力与空气阻力，正确D；非守恒本身不构成物理错误。')

    final=[]
    for row in rows:
        r=records[row['question_id']];src=inputs[r['question_id']];q=src['current']
        if src['source_sha256']!=r['source_sha256'] or source_fingerprint({**q,'id':r['question_id']})!=r['source_sha256']:raise ValueError('来源绑定变化')
        r.setdefault('source_conflicts',[]);r.setdefault('resolved_findings',[])
        quarantine=(r['batch'] in {'B1','B2'} or r['decision']!='repair_draft' or r.get('quarantine_original',False))
        r['quarantine_original']=quarantine;r['current_sha256']=snapshot_hash(q)
        r['peer_reviewers']=['gpt-6-luna (separate review turn)','Codex (adjudication)']
        f=r.get('proposed_form')
        if f:
            a=Annotation.model_validate(f['annotation']).model_dump();f['annotation']=a;a['review'].update(status='candidate',method='item_read',answer_status='unknown' if quarantine else 'source_only',
                   issues=['teacher_answer_review_pending','curriculum_unknown','score_unknown'])
            a['review']['notes']+='\n本稿为AI独立复算及交叉复核后的修订建议，未获人工审批；题干新增条件、答案改动须逐项核对。'
            a['origin']['batch_id']='physics-audit-20261014'
            if f['kind']!='reference':
                f['stem']=re.split(r'选项\s*[:：]',f['stem'])[0].strip()
                a['answer_spec'].update(mode='choice',accepted_answers=[f['answer']],equivalence='exact')
                for p in a['parts']:p['reference_answer']=f['answer']
            f=Draft.model_validate(f).model_dump();r['proposed_form']=f
        # Raw AI records stay immutable evidence; only this adjudicated artifact is importable.
        allowed=set(ReviewItem.model_fields);r={k:v for k,v in r.items() if k in allowed}
        item=ReviewItem.model_validate(r)
        try:validate_proposal(item)
        except Exception:
            print('invalid_proposal',item.question_id,item.proposed_form.kind,item.proposed_form.annotation.response_format);raise
        final.append(item.model_dump())
    output=DATA/'physics_review_adjudicated_20261014.json'
    output.write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'reviewed':len(final),'drafts':sum(bool(r['proposed_form']) for r in final),
                     'quarantine_decisions':sum(r['quarantine_original'] for r in final)}))


if __name__=='__main__':main()
