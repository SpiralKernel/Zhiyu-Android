"""Append independently solved, item-read GAOKAO-Bench physics problems."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.datasets import iter_dataset
from app.question_annotation import Annotation, source_fingerprint

REV = "6dbb24f8d8439041e5431c4c184a582182a6ce9c"
BATCH = "senior-20261015-physics-gaokao-1"

# GAOKAO normalized physics source indices and item-specific solutions/rubrics.
# Unknown marks are intentionally not assigned points.
DETAIL = {
    65: {
        "book":"physics-senior-compulsory-1","goals":["physics-senior-compulsory-1:u2:g1"],
        "knowledge":["匀变速直线运动", "平均速度与分段运动模型"],
        "fine":"联立100m与200m分段路程方程求加速时间、最大速度和加速度",
        "parts":[
          {"id":"p1","prompt":"求加速所用时间和100m比赛中的最大速率。","answer":"来源答案：t≈1.29s，v≈11.24m/s；独立解算未舍入值约t=1.2889s，v=11.241m/s。",
           "steps":["设加速时间t、最大速度v。100m赛跑距离方程为(1/2)vt+v(9.69−0.15−t)=100。","200m赛跑距离方程为(1/2)vt+0.96v(19.30−0.15−t)=200。","联立得t=0.696/0.54≈1.2889s，v≈11.241m/s，按题目精度分别约为1.29s、11.24m/s。"],"knowledge":["匀变速直线运动"],"fine":"由两组分段路程方程联立求运动参数",
           "rubric":[("建立两场比赛路程式","正确列出100m与200m路程方程。","加速段按初速0、末速v的匀加速平均速度计算。"),("联立求解","得到t约1.29s、v约11.24m/s。","秒和m/s单位正确。")],"errors":["漏减反应时间；将200m后的平均速率误当最大速率。"]},
          {"id":"p2","prompt":"求起跑后的匀加速加速度，结果保留两位小数。","answer":"来源答案8.71m/s²；由未舍入联立解计算约8.72m/s²，来源末位与直接复算不一致。",
           "steps":["用未舍入联立解的最大速率约11.241m/s及加速时间约1.2889s。","a=v/t≈8.722m/s²，保留两位小数为8.72m/s²。","来源解析先把t、v舍入至1.29s、11.24m/s后求比值，得到约8.71m/s²；题目没有明确后续计算是否必须使用已舍入中间值。"],"knowledge":["匀变速直线运动"],"fine":"由同一加速阶段末速度和时间求加速度并处理中间值舍入",
           "rubric":[("加速度关系","使用a=v/t。","取自同一加速阶段。"),("精度处理","说明使用未舍入解得约8.72m/s²，并识别来源8.71的舍入差异。","不掩盖来源与复算结果差异。")],"errors":["将四舍五入中间量当精确值而不说明。"]}],
        "level":3,"basis":"联立两场比赛的分段运动方程，并需判断源解答中间舍入对最后一位的影响。",
    },
    75: {
        "book": "physics-senior-compulsory-1", "goals": ["physics-senior-compulsory-1:u2:g1"],
        "knowledge": ["匀变速直线运动的位移", "反应时间与安全距离"],
        "fine": "先由晴天反应距离和刹车位移求减速度，再建立雨天安全距离方程并取正根",
        "parts": [{"id":"p1","prompt":"求雨天安全行驶的最大速度。","answer":"20 m/s",
          "steps":["晴天车速108km/h=30m/s。反应距离30×1=30m，制动距离120−30=90m。","由v²=2a₀s，晴天制动减速度a₀=30²/(2×90)=5m/s²；雨天a=(2/5)a₀=2m/s²。","雨天安全距离满足v×1+v²/(2×2)=120，即v²+4v−480=0。取正根v=20m/s。"],
          "knowledge":["匀变速直线运动的位移"],"fine":"含反应时间的分段停车距离计算",
          "rubric":[("晴天制动参数","正确换算30m/s并由120m安全距离扣除30m反应距离，得a₀=5m/s²。","列出晴天反应距离、制动距离和v₀²=2a₀s。"),("雨天参数与方程","得雨天减速度2m/s²，建立v+v²/4=120。","显示雨天反应位移与刹车位移两项。"),("速度与物理范围","取正根20m/s并给出速度单位。","舍弃负根并报告m/s。")],
          "errors":["把反应距离漏算或将反应时间用于制动阶段。","把速度108km/h误当108m/s。"]}],
        "level":2,"basis":"需要从晴天条件反求减速度，再处理反应与制动两段运动并解二次方程；来源给出完整条件。",
    },
    87: {
        "book":"physics-senior-selective-1","goals":["physics-senior-selective-1:u1:g2"],
        "knowledge":["动量定理与质量流率", "匀减速直线运动"],
        "fine":"用质量流率与动量定理求水柱冲击力，再联立竖直运动求悬停高度",
        "parts":[
          {"id":"p1","prompt":"求喷泉单位时间喷出的水的质量。","answer":"ρSv₀",
           "steps":["单位时间流过喷口的水体积为Sv₀。","乘以水密度ρ，得到质量流率ṁ=ρSv₀。"],"knowledge":["质量流率"],"fine":"截面积与流速求体积流率和质量流率",
           "rubric":[("体积流率","写出每秒水体积Sv₀。","用喷口横截面积乘喷出速度。"),("质量流率","乘以密度得到ρSv₀。","量纲为kg/s。")],"errors":["将质量流率误写成ρS/v₀。"]},
          {"id":"p2","prompt":"求玩具稳定悬停时其底面相对喷口的高度h。","answer":"h=(ρ²S²v₀⁴−M²g²)/(2ρ²S²v₀²g)",
           "steps":["水从喷口上升至玩具底面，v²=v₀²−2gh。","单位时间水质量ṁ=ρSv₀，水竖直速度由v变为0；水对玩具的向上冲击力大小为ṁv。","悬停平衡要求ṁv=Mg，得v=Mg/(ρSv₀)。","代回运动学关系得h=[v₀²−M²g²/(ρ²S²v₀²)]/(2g)，即题给等价表达式。稳定悬停前提保证该高度可达。"],
           "knowledge":["动量定理与质量流率","竖直上抛运动"],"fine":"连续水流速度改变产生的动量通量支撑玩具并反推高度",
           "rubric":[("水柱速度与高度关系","列出v²=v₀²−2gh。","明确上升过程重力使水速减小。"),("动量通量与平衡","建立冲击力ṁv=Mg，并使用ṁ=ρSv₀。","写明单位时间质量乘速度变化率。"),("代数联立","得到题给h表达式，符号及量纲一致。","把v=Mg/(ρSv₀)正确代入。")],"errors":["把水流质量流率误当总水质量。","忽略水流速度变化而直接令冲击力为零。"]}],
        "level":3,"basis":"需把连续流质量率、动量通量、受力平衡和匀减速运动组合建模；悬停是题设前提。",
    },
    92: {
        "book":"physics-senior-compulsory-2","goals":["physics-senior-compulsory-2:u4:g1"],
        "knowledge":["重力势能与机械能", "动能定理", "阻力做功"],
        "fine":"计算再入飞船不同位置机械能并用动能定理求阻力功",
        "parts":[
          {"id":"p1","prompt":"求飞船着地前瞬间的机械能。","answer":"4.0×10⁸ J",
           "steps":["地面为重力势能零点，落地前机械能等于动能。","E=mv²/2=(8.00×10⁴)(100²)/2=4.0×10⁸J。"],"knowledge":["动能与重力势能"],"fine":"地面势能零点下由落地速度求机械能",
           "rubric":[("机械能表达式","说明落地时势能为零，E=mv²/2。","使用题设100m/s着地速度。"),("计算和单位","结果4.0×10⁸J。","质量用kg，能量用J。")],"errors":["将高度160km对应势能加到落地时能量。"]},
          {"id":"p2","prompt":"求飞船进入大气层时的机械能。","answer":"2.4×10¹² J",
           "steps":["E=mv₁²/2+mgH。","动能为2.25×10¹²J，重力势能为1.2544×10¹¹J。","合计2.37544×10¹²J，按两位有效数字为2.4×10¹²J。"],"knowledge":["机械能与重力势能"],"fine":"高空速度与高度共同确定机械能并按有效数字取值",
           "rubric":[("动能项","计算½mv₁²=2.25×10¹²J。","代入质量及7500m/s。"),("势能项与合计","加入mgH，结果约2.4×10¹²J。","g=9.8m/s²，H=1.60×10⁵m，有效数字合理。")],"errors":["忽略进入大气层时的重力势能。","把高度单位km未换成m。"]},
          {"id":"p3","prompt":"求从离地600m处至着地前克服阻力所做的功。","answer":"9.7×10⁸ J",
           "steps":["600m处速度为入大气层速度的2.0%，即150m/s。","以600m处为初态、落地为末态：mgh−W阻=½mv₃²−½mv₂²。","W阻=mgh+½m(v₂²−v₃²)=9.704×10⁸J，取两位有效数字为9.7×10⁸J。"],"knowledge":["动能定理与阻力做功"],"fine":"由过程机械能减少量求克服阻力所做功",
           "rubric":[("中间速度","求得600m处速度150m/s。","使用题给2.0%比例。"),("功的关系和结果","正确列动能定理并求9.7×10⁸J。","克服阻力功按正值报告。")],"errors":["把阻力功的代数符号与克服阻力所做功的正值混淆。","漏掉600m处的初动能。"]}],
        "level":2,"basis":"三个小问分别使用机械能定义、重力势能和动能定理；数据与有效数字均给出。",
    },
    96: {
        "book":"physics-senior-selective-1","goals":["physics-senior-selective-1:u1:g2"],
        "knowledge":["竖直上抛运动", "动量守恒定律", "能量守恒"],
        "fine":"由初动能求上升至最高点时间，结合爆炸瞬间动量和能量守恒求碎片最高点",
        "parts":[
          {"id":"p1","prompt":"求烟花弹从地面上升至爆炸所经历的时间。","answer":"(1/g)√(2E/m)",
           "steps":["初动能E=mv₀²/2，故v₀=√(2E/m)。","上升至最高点速度变为零，v₀−gt=0。","t=√(2E/m)/g。"],"knowledge":["竖直上抛运动与动能"],"fine":"动能转换初速度后求竖直上抛到最高点时间",
           "rubric":[("初速度","由E=mv₀²/2得v₀=√(2E/m)。","明确E为初动能。"),("到达最高点时间","使用v=v₀−gt=0并得目标表达式。","重力加速度g置于分母。")],"errors":["把动能写成mv₀²；漏掉平方根。"]},
          {"id":"p2","prompt":"求爆炸后向上运动部分距地面的最大高度。","answer":"2E/(mg)",
           "steps":["爆炸前上升到最高点高度h₁=v₀²/(2g)=E/(mg)。","爆炸时间极短，系统竖直动量守恒；两等质量碎片总动量为零，所以两者速率相等且方向相反。","爆炸后总动能E均分，两碎片各自速度大小仍为v₀=√(2E/m)；向上碎片继续上升h₂=v₀²/(2g)=E/(mg)。","最大高度h=h₁+h₂=2E/(mg)。"],"knowledge":["动量守恒定律","机械能与竖直上抛"],"fine":"利用爆炸瞬间动量守恒及碎片动能分配计算继续上升高度",
           "rubric":[("爆炸前高度","由初始动能得到h₁=E/(mg)。","使用机械能守恒或v₀²=2E/m。"),("爆炸条件","说明总动量为零使两等质量碎片等速反向，结合总动能E。","爆炸瞬间忽略重力冲量。"),("末高度","求h₂=E/(mg)，与h₁相加得2E/(mg)。","报告相对地面的最大高度。")],"errors":["忽略爆炸前已经上升的高度。","认为总动能E是每一碎片各自的动能。"]}],
        "level":3,"basis":"综合运动学、动量守恒、能量分配及高度叠加，需辨认爆炸的短时过程。",
    },
    101: {
        "book":"physics-senior-selective-3","goals":["physics-senior-selective-3:u1:g2"],
        "knowledge":["油膜法估测分子大小", "单分子层模型"],
        "fine":"按油膜法实验顺序说明稀释目的、液滴体积测量和油膜面积测量",
        "parts":[
          {"id":"p1","prompt":"将纯油酸稀释成一定浓度油酸酒精溶液的目的是什么？","answer":"使油酸易在水面形成单分子层油膜。","steps":["稀释可使少量油酸较易铺展，便于形成单分子层油膜。"],"knowledge":["油膜法实验模型"],"fine":"说明稀释油酸的实验目的","rubric":[("稀释目的","指出帮助油酸铺展并形成单分子层油膜。","答案同时体现铺展性和单分子层条件。")],"errors":["称稀释是为了改变油酸分子直径。"]},
          {"id":"p2","prompt":"如何测出一滴已知浓度溶液中纯油酸的体积？","answer":"量取1mL溶液并数出滴数，再结合浓度求一滴中的纯油酸体积。","steps":["将1mL溶液逐滴加入量筒，记录总滴数N。","每滴溶液体积为1/N mL，再乘溶液中油酸体积分数得到纯油酸体积。"],"knowledge":["实验测量与体积分数"],"fine":"用已知浓度和滴数求单滴纯油酸体积","rubric":[("滴数测量","说明量取已知总体积并逐滴计数。","给出1mL与滴数N。"),("单滴纯油酸体积","将单滴溶液体积乘油酸浓度。","浓度含义和单位匹配。")],"errors":["把一滴溶液总体积当作纯油酸体积。"]},
          {"id":"p3","prompt":"为了得到油酸分子的直径，还需测量什么物理量？","answer":"单分子层油膜的面积。","steps":["单分子层近似为厚度d的薄层，油酸体积V≈Sd。","已由溶液浓度和滴数求得V，故还需测量油膜面积S，再算d=V/S。"],"knowledge":["单分子层模型与几何测量"],"fine":"用单分子层油膜面积和油酸体积估算分子尺度","rubric":[("待测量识别","指出油膜面积S。","不得重复回答已知液滴体积。"),("模型关系","用d=V/S说明用途。","明确单分子层近似。")],"errors":["测量水面总面积而非油膜覆盖面积。"]}],
        "level":2,"basis":"实验方案题要求按实验顺序区分模型假设、体积测量和面积测量。",
    },
    103: {
        "book":"physics-senior-compulsory-1","goals":["physics-senior-compulsory-1:u4:g1","physics-senior-compulsory-1:u2:g1"],
        "knowledge":["牛顿第二定律", "匀变速直线运动"],
        "fine":"根据升力正比速度平方反求载货后起飞速度，再由匀加速位移求加速度和时间",
        "parts":[
          {"id":"p1","prompt":"求装载货物后的起飞离地速度。","answer":"78 m/s",
           "steps":["起飞时升力等于重力，kv₁²=mg。","装载前后k不变，速度平方与质量成正比：v₂²/v₁²=m₂/m₁。","v₂=66√(1.69×10⁵/1.21×10⁵)=78m/s（按题设数据取整数）。"],"knowledge":["牛顿第二定律与平衡条件"],"fine":"由升力模型和起飞平衡关系推算载荷变化后的起飞速度",
           "rubric":[("起飞条件","写出kv²=mg。","指出升力等于重力时离地。"),("比例计算","正确建立v₂=v₁√(m₂/m₁)，得78m/s。","同一k且质量使用SI数值。")],"errors":["认为速度与质量成正比；忘记开平方。"]},
          {"id":"p2","prompt":"装载后飞机从静止匀加速滑行1521m离地，求加速度和滑行时间。","answer":"a=2 m/s²；t=39 s",
           "steps":["使用v²=2ax，a=78²/(2×1521)=2m/s²。","使用v=at，t=78/2=39s。"],"knowledge":["匀变速直线运动"],"fine":"用位移速度关系与速度时间关系求匀加速滑行参数",
           "rubric":[("加速度","由v²=2ax得2m/s²。","初速度为零，位移1521m。"),("时间","由v=at得39s。","使用装载后起飞速度78m/s。")],"errors":["将位移公式中的2漏掉；把km/h和m/s混用。"]}],
        "level":2,"basis":"小问分别使用比例模型和匀加速公式，计算步骤短但有模型转换。",
    },
    108: {
        "book":"physics-senior-compulsory-2","goals":["physics-senior-compulsory-2:u4:g1"],
        "knowledge":["动能定理", "碰撞前后动能比", "恒力做功与牛顿第二定律"],
        "fine":"先由相同碰撞动能比反求拍球功，再联立恒力做功和运动学求施力",
        "parts":[
          {"id":"p1","prompt":"求运动员拍球过程中对篮球所做的功。","answer":"4.5 J",
           "steps":["第一次下落碰撞前动能E₁=mgh₁=10.8J；第一次反弹碰撞后动能E₂=mgh₂=7.2J。","每次碰撞前后动能比相同，E₄/E₃=E₂/E₁=2/3。第二次反弹到1.5m，E₄=mgh₄=9J，故碰撞前E₃=13.5J。","拍球前从h₃落下的重力势能为mgh₃=9J，故拍球做功W=E₃−mgh₃=4.5J。"],"knowledge":["动能定理与重力势能"],"fine":"用相同碰撞能量比建立两次下落能量关系",
           "rubric":[("第一次碰撞能量比","正确得到E₂/E₁=2/3。","用mgh₁、mgh₂计算。"),("第二次碰撞前动能","由反弹高度求E₄=9J，并得E₃=13.5J。","使用相同碰撞前后动能比。"),("拍球做功","扣除下落重力势能9J，得4.5J。","功的数值及正号正确。")],"errors":["把碰撞前后动能比方向倒置。","漏掉拍球前下落的重力做功。"]},
          {"id":"p2","prompt":"求运动员拍球时对篮球的作用力大小。","answer":"9 N",
           "steps":["取向下为正，拍球期间合力F+mg=ma，故a=F/m+g。","篮球由静止开始，作用时间t=0.20s，位移x=at²/2。","拍球功W=Fx=F(F/m+g)t²/2。代入W=4.5J、m=0.60kg、g=10m/s²、t=0.20s，解得正根F=9N。"],"knowledge":["牛顿第二定律与恒力功"],"fine":"将拍球力、重力、匀加速位移和已知做功联立",
           "rubric":[("动力学及位移关系","列出a=(F+mg)/m及x=at²/2。","方向约定和初速度为零正确。"),("功方程与解","列出W=Fx并求正根9N。","单位N，舍去不符合拍球方向的根。")],"errors":["把手对球的力误当作合力ma。","只用W=F×球下落距离，忽略作用时间内的动力学。"]}],
        "level":3,"basis":"结合两次碰撞的能量比例、动能定理、恒力功和牛顿第二定律，需消去运动位移。",
    },
}


def criterion_rows(rows):
    return [{"id":f"c{i}","description":f"{label}：{description}","points":None,"evidence_required":evidence}
            for i,(label,description,evidence) in enumerate(rows,1)]


def main():
    items = [q for q in iter_dataset(ROOT / "data/sources", "gaokao") if q["subject"] == "physics"]
    manifest = json.loads((ROOT / "data/sources/gaokao/DOWNLOAD.json").read_text())
    file_shas = {x["path"]:x["sha256"] for x in manifest["files"]}
    records=[]; audit=[]
    for i, detail in DETAIL.items():
        q=copy.deepcopy(items[i])
        source_name=q["provenance"]["source_file"]
        path=next(p for p in file_shas if Path(p).name==source_name)
        q["stage"]="senior"
        q["provenance"].update(download_revision=REV,file_sha256=file_shas[path])
        q["provenance"]["source_file"]=path
        q["provenance"]["url"]=f"https://github.com/OpenLMLab/GAOKAO-Bench/blob/{REV}/{path}"
        q["curriculum_book_id"]=detail["book"]
        q["curriculum_goal_ids"]=detail["goals"]
        source_sha=source_fingerprint(q)
        parts=[]; independent=[]
        for part in detail["parts"]:
            steps=part["steps"]
            independent.extend(steps)
            parts.append({"id":part["id"],"prompt":part["prompt"],"reference_answer":part["answer"],
                "solution_steps":steps,"knowledge_tags":part["knowledge"],"type_tags":[part["fine"]],
                "depends_on":[],"points":None,"rubric":criterion_rows(part["rubric"]),
                "common_errors":[{"description":e,"knowledge_tags":part["knowledge"],"type_tags":[part["fine"]]} for e in part["errors"]]})
        # One source item has a reproducible rounding discrepancy in its second result.
        pending=i==65
        issues=["source_answer_rounding_conflict"] if pending else []
        annotation={"schema_version":1,"response_format":"composite",
            "knowledge":{"primary":detail["knowledge"],"supporting":[],"prerequisites":[]},
            "fine_types":[detail["fine"]],
            "difficulty":{"level":detail["level"],"basis":detail["basis"],"origin":"luna","calibrated":False},
            "curriculum":{"grade":None,"term":None,"book_id":detail["book"],"goal_ids":detail["goals"],
                "scope_status":"candidate","basis":"按经核目录映射高中物理主适用册和目标；原题未给年级、学期或版次信息。"},
            "answer_spec":{"mode":"multipart","accepted_answers":[p["answer"] for p in detail["parts"]],
                "equivalence":"manual","constraints":["代数式接受等价形式；数值答案使用题目给定单位与有效数字要求。"],"unit":None,"tolerance":None},
            "parts":parts,
            "grading":{"mode":"ai_rubric","full_score":None,"allow_alternative_methods":True,"uncertainty_policy":"review_required"},
            "review":{"status":"candidate","answer_status":"conflict" if pending else "checked","issues":issues,
                "method":"item_read","notes":"逐题阅读题干、选项/小问、源答案与解析并独立复算；逐问步骤和评分证据已记录。Luna候选，不代表教师审核。"},
            "origin":{"model":"gpt-6-luna","batch_id":BATCH}}
        Annotation.model_validate(annotation)
        decision="pending" if pending else "passed"
        conflict=["来源第二小问将已四舍五入的t=1.29s、v=11.24m/s相除得8.71m/s²；直接由未舍入方程解得约8.72m/s²，精度约定不足以裁决来源答案。"] if pending else []
        rationale=" | ".join(independent)
        records.append({"question_id":q["id"],"source_sha256":source_sha,"decision":decision,
            "quarantine_original":pending,"question":q,"annotation":annotation,
            "independent_solution":independent,"source_conflicts":conflict,
            "remaining_issues":issues,"rationale":rationale})
        audit.append({"question_id":q["id"],"source_sha256":source_sha,"decision":decision,
            "source_index":i,"topic":detail["knowledge"],"source_answer":q["answer"],
            "independent_solution":independent,"source_conflicts":conflict,"rationale":rationale})
    path=ROOT/"app/data/senior_physics_gaokao_1.json"
    batch={"batch_id":BATCH,"source_manifest":[{"path":p,"revision":REV,"sha256":h,
        "license":"Apache-2.0","source_url":"https://github.com/OpenLMLab/GAOKAO-Bench"}
        for p,h in sorted(file_shas.items()) if "Physics_" in p],"items":records}
    path.write_text(json.dumps(batch,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    aud=ROOT/"data/annotations/senior-20261015/physics-gaokao-review.jsonl"
    aud.parent.mkdir(parents=True,exist_ok=True)
    aud.write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in audit)+"\n",encoding="utf-8")
    # Keep the startup import file cumulative; replace only this source batch on rerun.
    target=ROOT/"app/data/senior_physics_luna.json"
    current=json.loads(target.read_text())
    current["items"]=[x for x in current["items"] if x["question"]["provenance"].get("dataset")!="gaokao"]+records
    known={(x.get("path"),x.get("sha256")) for x in current["source_manifest"]}
    current["source_manifest"] += [x for x in batch["source_manifest"] if (x["path"],x["sha256"]) not in known]
    current["batch_id"]="senior-20261015-physics-cumulative-2"
    save_batch(target,current)
    print(f"wrote GAOKAO batch {len(records)} ({sum(x['decision']=='passed' for x in records)} passed, {sum(x['decision']=='pending' for x in records)} pending)")


if __name__=="__main__": main()
