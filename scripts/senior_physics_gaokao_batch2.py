"""Item-read GAOKAO-Bench choice questions for undercovered senior topics."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.datasets import iter_dataset
from app.question_annotation import Annotation,source_fingerprint
from app.senior_bank import save_batch

REV="6dbb24f8d8439041e5431c4c184a582182a6ce9c"
BATCH="senior-20261015-physics-gaokao-2"

# (knowledge, fine type, answer, checked solution, difficulty, basis,
# chapter book/unit/goal). Each selected original stem and options were read.
ROWS={
2:("万有引力、同步卫星与平均密度","由卫星圆轨道周期关系比较不同密度行星的同步周期","B",[
"地球同步卫星轨道半径r₁=R₁+6R₁=7R₁，周期T₁=24h。另一行星r₂=R₂+2.5R₂=3.5R₂。",
"圆轨道有T²=4π²r³/(GM)，球体质量M=(4/3)πρR³，因此T²∝(r/R)³/ρ。",
"T₂²/T₁²=(3.5/7)³×(ρ₁/ρ₂)=(1/8)×2=1/4，故T₂=12h，选B。"],2,"使用圆轨道周期关系和密度表达式比较同步周期，关键是把轨道半径写为距行星中心的距离。","physics-senior-compulsory-2",3,2),
8:("惯性与牛顿第一定律","辨析惯性定义及合外力为零时速度矢量保持不变","AD",[
"惯性是物体保持原有运动状态的性质，A正确。",
"合外力为零时物体可以静止，也可以沿直线匀速运动，B错误。",
"匀速率圆周运动速度方向持续变化，不能称为惯性保持，C错误。",
"不受力的运动物体保持原速度和方向，即匀速直线运动，D正确；选AD。"],1,"按惯性定义与牛顿第一定律逐项判断，不需要代数计算。","physics-senior-compulsory-1",4,1),
13:("圆周运动与弯道摩擦","辨析倾斜弯道的重力支持力合力及非设计速度时轮胎摩擦趋势","AC",[
"在临界设计速度v_c下没有向内外滑动趋势，路面需外侧高、内侧低；重力与支持力的合力提供向心力，A正确。",
"低于v_c时车辆有向内侧滑动的趋势，但静摩擦力会阻止该趋势，题述‘便会向内侧滑动’过于绝对，B错误。",
"高于v_c时需要更大的向心力，轮胎静摩擦力朝弯道内侧，车辆对外侧路面/轮缘有挤压趋势，C正确。",
"低于v_c时趋势相反，不会挤压外轨，D错误；正确项A、C，对应题源答案AC。"],2,"需区别理想设计速度下的受力分解和偏离该速度时摩擦力对滑动趋势的约束。","physics-senior-compulsory-2",2,2),
16:("平抛运动与机械能守恒","由抛出点动能等于重力势能求落地速度方向","B",[
"设抛出点水平速度为v₀、高度为h。题设½mv₀²=mgh。",
"机械能守恒给出落地速度v²=v₀²+2gh=2v₀²。",
"竖直速度分量满足v_y²=2gh=v₀²，水平分量仍为v₀，因此tanθ=v_y/v₀=1，θ=π/4，选B。"],2,"分解平抛运动并使用机械能守恒；题目已给出抛出点能量关系。","physics-senior-compulsory-2",1,2),
20:("洛伦兹力与带电粒子圆周运动","比较带电粒子进入较弱磁场后的半径与角速度","B",[
"粒子速度垂直磁场，洛伦兹力提供向心力：qvB=mv²/r，所以r=mv/(|q|B)。",
"磁场减弱后粒子速率不变（洛伦兹力不做功），轨道半径增大。角速度ω=v/r=|q|B/m减小，选B。"],2,"由洛伦兹力与向心力关系分别比较半径、角速度，并确认磁力不改变速率。","physics-senior-selective-2",1,2),
24:("电容器与介质","恒压直流连接下移出电介质对电荷量和场强的影响","D",[
"电容器仍接恒压电源，极板电压U不变；移出云母使相对介电常数减小，C=εS/d减小。",
"Q=CU，故极板电荷量减小。板间距d与电压U不变，匀强场E=U/d不变，选D。"],2,"需要依次用介质对电容的影响、恒压条件和板间场强关系判断。","physics-senior-compulsory-3",2,1),
28:("电势与等势面","利用电场线与等势面正交关系辨析等势面性质","B",[
"静电场中电场方向沿电势降低最快的方向，电场线与等势面处处垂直，B正确。",
"不同电势的等势面不能相交；等势面上场强大小未必相同。负电荷由高电势移至低电势时电势能增加、电场力做负功。故选B。"],1,"直接使用静电场中电势变化和等势面的定义关系。","physics-senior-compulsory-3",2,1),
29:("匀变速直线运动","根据动能倍数与平均速度求匀加速运动加速度","B",[
"动能变为9倍意味着速度大小变为3倍；速度增大，若初速为u则末速3u。",
"匀加速位移s=(u+3u)t/2=2ut，故u=s/(2t)。",
"a=(3u−u)/t=2u/t=s/t²，选B。"],2,"结合动能速度平方关系、匀变速平均速度和速度变化定义求a。","physics-senior-compulsory-1",2,2),
31:("平抛运动的水平与竖直分运动","解释相同高度水平抛球越过球网的时间差","C",[
"两球从相同高度水平抛出且忽略空气阻力，竖直运动相同，下降同一高度所用时间相同。",
"从发球点到球网的水平距离相同，水平速度较大时通过该距离所需时间更短，在此期间竖直下落更少，因此更容易越网。选C。"],1,"将平抛运动分解为相互独立的水平匀速与竖直自由落体。","physics-senior-compulsory-2",1,2),
33:("核反应与质量亏损","由核反应方程质量亏损计算聚变释放能量","B",[
"核反应前总质量为2×2.0136u=4.0272u；反应后总质量为3.0150u+1.0087u=4.0237u。",
"质量亏损Δm=0.0035u。释放能量ΔE=Δmc²=0.0035×931MeV≈3.26MeV≈3.3MeV，选B。"],2,"先核对反应前后核子守恒并求质量亏损，再用题给u与MeV换算。","physics-senior-selective-3",5,2),
36:("光电效应方程","由光电效应方程比较频率、遏止电压、最大初动能与逸出功","BC",[
"同一金属逸出功W₀相同，E_k=hν−W₀，频率较高时最大初动能较大，故B正确。",
"遏止电压满足E_k=eU_c，故U_a<U_b推出E_ka<E_kb，C正确。",
"频率较高时遏止电压应更高，A错误；hν−E_k=W₀恒定，D应取等号而非大于。答案BC。"],2,"逐项应用爱因斯坦光电效应方程和遏止电压关系。","physics-senior-selective-3",4,2),
37:("动能定理与匀加速运动","判断初速为零恒加速度列车动能与位移的比例关系","B",[
"动能定理W合=ΔE_k。启动阶段合力恒定时，W合=F合x，因此动能与位移成正比。",
"又E_k=½ma²t²与时间平方成正比，和速度平方成正比，也和动量平方成正比；不是与这些量本身成正比。选B。"],1,"将动能定理与给定初速度为零的匀加速条件结合，比较变量的幂次。","physics-senior-compulsory-2",4,1),
42:("开普勒第三定律与卫星周期","由圆轨道半径比求卫星周期比","C",[
"两颗地球卫星绕同一中心天体运行，开普勒第三定律T²∝r³。",
"半径比r_P:r_Q=16:4=4:1，周期比T_P:T_Q=(4:1)^(3/2)=8:1，选C。"],1,"对同一中心天体的圆轨道直接使用开普勒第三定律。","physics-senior-compulsory-2",3,2),
45:("斜面受力与滑动摩擦","沿斜面方向列匀速平衡求最大物块质量","A",[
"物块匀速上滑，沿斜面合力为零；绳张力平衡重力沿斜面分量和向下的滑动摩擦力。",
"T=mg sin30°+μmg cos30°=mg/2+(√3/3)mg(√3/2)=mg。",
"T_max=1500N且g=10m/s²，m_max=150kg，选A。"],2,"需正确确定摩擦方向并分解重力，利用匀速条件和最大张力。","physics-senior-compulsory-1",3,2),
47:("楞次定律与能量守恒","说明楞次定律反映感应过程中的能量守恒","D",[
"感应电流产生的磁场总阻碍磁通量变化；要维持磁通量变化，外界必须做功。",
"外界机械能转化为电能等其他能量，体现能量守恒，选D。"],1,"将楞次定律的阻碍效果与感应过程中的能量转化联系。","physics-senior-compulsory-3",5,2),
48:("万有引力与行星圆轨道","根据向心加速度和轨道速率随半径的关系排序","A",[
"绕同一太阳做圆周运动时a=GM/r²、v=√(GM/r)。",
"已知R金<R地<R火，因此a金>a地>a火且v金>v地>v火。只有A正确。"],1,"用万有引力提供向心力，分别导出a、v与轨道半径的单调关系。","physics-senior-compulsory-2",3,1),
49:("动量定理与安全气囊","解释缓冲装置延长作用时间和增大受力面积的作用","D",[
"司机碰撞前后动量变化由初末速度决定，安全气囊不能减少该动量变化量。",
"气囊延长碰撞时间，依据冲量定理可减小平均冲击力；气囊增大接触面积，降低单位面积受力，故D正确。"],1,"用动量定理解释缓冲时间并区分总力与单位面积压力。","physics-senior-selective-1",1,1),
54:("动量守恒与连续反冲","由多次物块反弹和再次推动建立运动员速度界限","BC",[
"设运动员质量M、物块质量m=4kg、每次推出速度v=5m/s。系统初始动量为零；墙的弹性碰撞使物块速度反向。",
"逐次对推物块过程列动量守恒，第n次后可得Mv_n=(2n−1)mv。",
"n=7时仍能追上要求v_7<v，得到M>52kg；n=8时不能再追上对应v_8≥v，第8次退行速度题设为严格大于5m/s，故300/M>5，得到M<60kg。范围52kg<M<60kg，选B、C。"],3,"需要把推物块过程与挡板弹性反射分开建模，再用第7、8次条件限定质量。","physics-senior-selective-1",1,2),
59:("动能定理、冲量与摩擦","由撤力后的滑行数据求摩擦因数、拉力冲量并判定选项","BC",[
"撤力后物体由v₀滑行2s₀停止，a₂=−v₀²/(4s₀)，故μg=v₀²/(4s₀)，C正确。",
"撤力前从静止滑行s₀到v₀，合加速度a₁=v₀²/(2s₀)。由F−μmg=ma₁得F=3mv₀²/(4s₀)，为摩擦力的3倍；D错误。",
"拉力作用时间由平均速度得t₁=2s₀/v₀，拉力冲量Ft₁=3mv₀/2，B正确。",
"拉力做功Fs₀=3mv₀²/4，不是½mv₀²，A错误；答案BC。"],3,"联立撤力后滑动减速和撤力前匀加速数据，进一步核查功与冲量。","physics-senior-compulsory-2",4,1),
63:("半衰期与指数衰变","由总数和中间时刻剩余数求两种核素初始数量及后续剩余数","C",[
"设半衰期t₀的初始原子核数为x，半衰期2t₀的为y，则x+y=N。",
"经过2t₀后，x剩x/4，y剩y/2；方程x/4+y/2=N/3，解得x=2N/3、y=N/3。",
"经过4t₀后，前者剩x/16，后者剩y/4，总数=N/24+N/12=N/8，选C。"],2,"建立两种半衰期的独立指数衰变方程并联立初始占比。","physics-senior-selective-3",5,1),
}

def main():
    bank=[q for q in iter_dataset(ROOT/"data/sources","gaokao") if q["subject"]=="physics"]
    manifest=json.loads((ROOT/"data/sources/gaokao/DOWNLOAD.json").read_text())
    file_shas={x["path"]:x["sha256"] for x in manifest["files"]}
    records=[];audit=[]
    for idx,(knowledge,fine,answer,solution,level,basis,bid,unit,goal) in ROWS.items():
        q=copy.deepcopy(bank[idx]); source_name=q["provenance"]["source_file"]
        source_file=next(p for p in file_shas if Path(p).name==source_name)
        q["stage"]="senior"; q["curriculum_book_id"]=bid
        q["curriculum_goal_ids"]=[f"{bid}:u{unit}:g{goal}"]
        q["provenance"].update(source_file=source_file,download_revision=REV,file_sha256=file_shas[source_file],
             url=f"https://github.com/OpenLMLab/GAOKAO-Bench/blob/{REV}/{source_file}")
        assert q["answer"]==answer,(idx,q["id"],q["answer"],answer)
        srcsha=source_fingerprint(q)
        response=q["kind"]
        accepted=list(answer) if response=="multiple_choice" else [answer]
        annotation={"schema_version":1,"response_format":response,
          "knowledge":{"primary":[knowledge],"supporting":[],"prerequisites":[]},
          "fine_types":[fine],"difficulty":{"level":level,"basis":basis,"origin":"luna","calibrated":False},
          "curriculum":{"grade":None,"term":None,"book_id":bid,"goal_ids":q["curriculum_goal_ids"],"scope_status":"candidate",
             "basis":f"按核对过的高中物理目录映射到主册{bid}及对应单元目标；题源未提供年级、学期或教材版次。"},
          "answer_spec":{"mode":"choice","accepted_answers":accepted,"equivalence":"exact","constraints":["按选项作答；多选题需完整选出所有正确项。"],"unit":None,"tolerance":None},
          "parts":[{"id":"whole","prompt":q["stem"],"reference_answer":answer,"solution_steps":solution,
             "knowledge_tags":[knowledge],"type_tags":[fine],"depends_on":[],"points":None,
             "rubric":[{"id":"choice_evidence","description":f"答案{answer}；"+"；".join(solution),"points":None,"evidence_required":"作答选项与各项物理关系判断一致。"}],
             "common_errors":[{"description":e,"knowledge_tags":[knowledge],"type_tags":[fine]} for e in _errors(idx)]}],
          "grading":{"mode":"objective","full_score":None,"allow_alternative_methods":True,"uncertainty_policy":"review_required"},
          "review":{"status":"candidate","answer_status":"checked","issues":[],"method":"item_read",
             "notes":"逐题阅读题干、全部选项、来源答案和解析，并独立复算/判析；本记录为Luna候选，不表示教师审核。"},
          "origin":{"model":"gpt-6-luna","batch_id":BATCH}}
        Annotation.model_validate(annotation)
        decision="pending" if idx==13 else "passed"
        if idx==13:
            annotation["review"]["answer_status"]="pending"
            annotation["review"]["issues"]=["原始选项C出现‘高度限度’，物理语义疑为‘速度限度’，但无法仅凭本地题源确认，选项含义影响作答。"]
        records.append({"question_id":q["id"],"source_sha256":srcsha,"decision":decision,"quarantine_original":decision!="passed",
           "question":q,"annotation":annotation,"independent_solution":solution,
           "source_conflicts":["选项C‘高度限度’疑似OCR错字；需回到清晰原件确认是否为‘速度限度’。"] if idx==13 else [],
           "remaining_issues":["选项C关键字疑似OCR错误，无法可靠确认正确选项集合。"] if idx==13 else [],
           "rationale":("题目其余内容可读，但选项C关键字损坏会改变物理含义，暂不判定通过。" if idx==13 else " | ".join(solution))})
        audit.append({"question_id":q["id"],"source_sha256":srcsha,"decision":decision,"source_index":idx,
           "topic":knowledge,"source_answer":q["answer"],"independent_solution":solution,"rationale":" | ".join(solution)})
    sm=[{"path":p,"revision":REV,"sha256":v,"license":"Apache-2.0","source_url":"https://github.com/OpenLMLab/GAOKAO-Bench"}
        for p,v in sorted(file_shas.items()) if "Physics_" in p]
    out={"batch_id":BATCH,"source_manifest":sm,"items":records}
    (ROOT/"app/data/senior_physics_gaokao_2.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    p=ROOT/"data/annotations/senior-20261015/physics-gaokao-2-review.jsonl";p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in audit)+"\n")
    target=ROOT/"app/data/senior_physics_luna.json"; current=json.loads(target.read_text())
    ids={x["question_id"] for x in records}
    current["items"]=[x for x in current["items"] if x["question_id"] not in ids]+records
    known={(x.get("path"),x.get("sha256")) for x in current["source_manifest"]}
    current["source_manifest"] += [x for x in sm if (x["path"],x["sha256"]) not in known]
    current["batch_id"]="senior-20261015-physics-cumulative-3"
    save_batch(target,current)
    print(f"wrote {len(records)} GAOKAO choices")

def _errors(i):
    return {
      2:["把卫星离地高度当作轨道半径；漏乘密度比。"],
      8:["把没有合外力理解为只能静止。","把速率不变的圆周运动误当速度矢量不变。"],
      13:["混淆内外轨高度；忽略车速偏离设计值时静摩擦的约束作用。"],
      16:["只使用抛体运动公式而漏掉题设动能势能条件。","误把落地速度方向当成位移方向。"],
      20:["认为洛伦兹力会改变粒子速率。","把轨道半径增大误判为角速度增大。"],
      24:["移出介质后仍认为电容量不变。","忽略电源连接使电压保持不变。"],
      28:["认为同一等势面各点场强必相同。","忽略负电荷电势能随电势升高而降低。"],
      29:["把动能变为9倍误认为速度变为9倍。","把位移平均速度关系中的平均速度误作初速度。"],
      31:["把较快水平速度误认为会改变竖直自由落体时间。","把水平距离固定误成运动时间固定。"],
      33:["质量差计算漏掉生成物一侧的中子质量。","把u直接当成MeV而不乘931MeV/c²。"],
      36:["把遏止电压和最大初动能关系方向弄反。","忽略同一金属逸出功相同。"],
      37:["认为动能与速度或时间成正比而忽略平方关系。","误把合力做功写成与时间成正比。"],
      42:["把半径比直接当周期比。","忘记开平方而误算成64:1。"],
      45:["把摩擦力方向取为沿斜面向上。","漏掉重力垂直斜面分量对摩擦力的影响。"],
      47:["将楞次定律只与电阻定律或欧姆定律关联。"],
      48:["将向心加速度与速度随轨道半径的变化关系混淆。"],
      49:["认为安全气囊能减小司机的总动量变化量。","把延长作用时间对平均力的影响方向弄反。"],
      54:["把物块在挡板反射后的速度方向或次数条件弄错。","遗漏第7次仍可追上、第8次不可追上的双边界。"],
      59:["只分析撤力前阶段，忽略撤力后的减速距离。","把合力冲量误当拉力冲量。"],
      63:["把两种核素合并成一个统一半衰期。","对经历2t₀和4t₀的衰变次数计算错误。"],
    }[i]

if __name__=="__main__":main()
