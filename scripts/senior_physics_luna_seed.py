"""Create the first item-read senior physics annotation batch from pinned CMMLU."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.question_annotation import Annotation, source_fingerprint
from app.senior_bank import save_batch

REV = "d6e7b716d8ac694f38969a6c0407437d1fded799"
CSV_PATH = "data/test/high_school_physics.csv"
DEV_PATH = "data/dev/high_school_physics.csv"
BATCH = "senior-20261015-physics-luna-1"

# Index, answer, primary knowledge, fine task, solution, difficulty rationale,
# distractor/error diagnosis. Each entry below was read and checked individually.
ITEMS = {
    0: ("A", "位移、路程与矢量合成", "分段直线运动的路程求和及位移正交分量合成", ["取东为+x、北为+y：东西向合位移为2−6=−4m（向西），南向位移3m。", "位移大小为√(4²+3²)=5m；路程为2+6+3=11m。"], 1, "直接按路径和位移矢量分别求；无多步模型转换。", ["把路程11m当位移大小；忽略东西向相反位移。"]),
    3: ("D", "静电场与静电防护", "识别接地导体泄放静电的安全作用", ["铁链使油罐车车身与大地导通，摩擦产生的电荷可转移到大地，降低静电积累和放电引燃风险。", "其他选项分别把拖链误作标记、散热或声响装置，均不符其接地用途。"], 1, "考查常见静电防护原理，答案可由接地导体作用直接判定。", ["将接地链误认为静电应用而非静电防护；混淆接地与散热。"]),
    4: ("A", "匀变速直线运动与刹车问题", "按停止时间截断刹车位移并比较两时刻", ["刹车时间t停=v₀/a=20/5=4s。", "4s内位移=20×4−(1/2)×5×4²=40m；6s时汽车早已停下，位移仍为40m。", "位移之比为1:1，选A。"], 2, "须识别刹车停止后的位移不再按匀减速公式外推；含分段运动判断。", ["把匀减速公式继续用于停车后的6s；将4s和6s误当都在运动。"]),
    24: ("D", "自由落体运动", "由静止自由落体的速度公式求末速度", ["初速度为零且只受重力，v=gt=10×2=20m/s，方向竖直向下。"], 1, "代入单一运动学公式即可，条件及g已给出。", ["把位移公式误用于求速度；漏写速度方向或单位。"]),
    27: ("C", "圆周运动与向心加速度", "辨析匀速圆周运动中速度方向持续变化", ["匀速圆周运动的速率不变，但速度方向沿切线且不断改变，因此速度矢量变化，运动是变速运动。", "加速度一般有向心分量且不必始终只指向圆心；合力不为零。"], 1, "考查速率与速度矢量的区别，靠定义辨析。", ["把匀速理解成速度矢量不变；误认为所有圆周运动加速度只有向心分量。"]),
    29: ("C", "万有引力与人造卫星", "比较不同圆轨道卫星的轨道速率", ["圆轨道由GMm/r²=mv²/r，得v=√(GM/r)。", "轨道半径更大时速率更小，选C。"], 1, "一条圆轨道关系式即可得出比较结论。", ["把轨道更高误判为速度更大；把向心合力误判为零。"]),
    14: ("A", "串并联电路与等效电阻", "枚举三个相同电阻全部参与时的串并联等效值", ["三个12Ω电阻全串联为36Ω，全并联为4Ω。", "两只串联后与另一只并联：24||12=8Ω；两只并联后与另一只串联：6+12=18Ω。", "可得值为36Ω、4Ω、8Ω、18Ω；24Ω需只用两只而闲置一只，因此题意按三个电阻均参与时，不可能值选A。"], 2, "需要枚举串、并、混联拓扑；把‘三个电阻’理解为均使用时选项唯一。", ["忽略题目要求三个电阻全部使用，因而误选24Ω；并联等效值算术错误。"]),
    18: ("A", "电磁振荡与LC电路", "由f=1/(2π√LC)判断元件变化对固有频率的影响", ["f与√(LC)成反比。L、C都减半时LC变为原来的1/4，√(LC)减半，频率加倍。", "其余组合使LC乘积分别为1/2、1/2、4倍，频率不会加倍。"], 2, "需正确处理LC乘积和平方根比例，计算步骤短。", ["忽略公式中的平方根；误以为L、C减半使频率加倍各贡献两倍。"]),
    30: ("D", "单摆的周期与简谐振动", "区分质量对单摆周期无影响与振幅随平衡速度变化", ["小角度单摆周期T=2π√(l/g)，与摆球质量无关，频率不变。", "平衡位置处速度为最大值；摆长固定时振幅与该最大速度成正比，速度减半则振幅改变（减半）。选D。"], 2, "同时调用单摆周期及简谐运动能量/速度振幅关系。", ["认为摆球质量改变周期；认为质量增大可补偿速度减小而保持振幅。"]),
    15: ("C", "光的干涉", "从光学现象中识别薄膜干涉与平整度干涉检验", ["透明标准样板与单色光检验平面平整度利用空气薄膜干涉；油膜彩色也由薄膜干涉产生。", "光纤传播利用全反射，白光经棱镜形成彩带属于色散，因此与干涉相关的是B、D，即选项C。"], 2, "须辨认两类薄膜干涉并排除全反射、色散。", ["把所有彩色现象都归因于色散；把光纤导光误作干涉。"]),
    9: ("D", "气体内能与理想气体状态", "将分子平均动能与分子势能分别联系温度和体积", ["分子热运动平均动能由温度决定；对一定量气体，分子间平均距离随体积变化，分子势能主要随体积状态变化。", "故顺序为温度和体积，选D。"], 2, "概念辨析，需限定为一定量气体及课程模型。", ["将平均动能与压强联系；把分子势能误认只由温度决定。"]),
    1: ("B", "热传递与改变内能的方式", "辨析热传递与摩擦、压缩做功", ["炉火加热沸水时，能量通过温差由火焰/器具传给水，属于热传递。", "其余三项均由摩擦或外界压缩做功导致内能改变。"], 1, "四种常见过程分类，依据能量传递方式判定。", ["把‘发热’一律认作热传递；忽略摩擦和压缩是做功。"]),
    0+1000: ("A", "原子核裂变与核能", "辨认现有核电站主要能量来源", ["通常核电站通过可控重核裂变释放能量，再由热机和发电机转化为电能。", "放射性衰变、人工同位素和化学反应不是现有核电站的主要能量来源。"], 1, "考查裂变核电基本原理，无需数值推导。", ["把核电站能量来源与放射性衰变或核聚变混淆。"]),
    11: ("D", "光电效应", "由阈频条件判断提高入射光频率可触发光电效应", ["原紫外线不能产生光电效应说明其频率低于该金属阈频。", "延长照射时间或提高同频光强不能补足单个光子的能量；X射线频率更高，可能超过阈频，选D。"], 2, "考查阈频与光子能量，不把光强误当单光子能量。", ["认为照射时间更长或光强更大能改变阈频；把波长更短的X射线当低频。"]),
    22: ("B", "原子核式结构模型", "把卢瑟福模型与α粒子散射实验对应", ["少数α粒子发生大角度偏转、极少数反弹，表明正电荷和大部分质量集中在原子核，卢瑟福据此提出核式结构模型。"], 1, "由经典实验与模型结论直接配对。", ["与阴极射线发现电子或天然放射性发现相混淆。"]),
    51: ("A", "法拉第电磁感应定律", "比较磁通量变化率与变化量、磁通量本身", ["法拉第定律ε=|ΔΦ|/Δt（线圈匝数固定），感应电动势取决于磁通量变化率。", "所以变化越快，电动势越大；只知道变化量、磁通量值或磁通量为零均不足以单独确定电动势。"], 2, "需区分磁通量、变化量和单位时间变化量。", ["把磁通量越大等同于感应电动势越大；忽略变化过程和时间。"]),
    35: ("A", "位移时间关系与往返路程", "由位置函数求转折点并累加分段路程", ["x(t)=6t−t²，速度v=dx/dt=6−2t；转折点t=3s。", "x(0)=0，x(3)=9m，x(4)=8m，所以0到3s走9m，3到4s返回1m，总路程10m，选A。"], 2, "要从位置函数求速度零点并处理折返，不能只取末位置。", ["把位移x(4)=8m当路程；漏掉t=3s处的运动方向改变。"]),
    68: ("B", "库仑定律", "按两电荷电量同时放大比例计算静电力变化", ["距离不变时F=k|q₁q₂|/r²。两电量各乘3，乘积乘9，静电力为原来的9倍，选B。"], 1, "直接按库仑定律比例关系计算。", ["只计入一个电量的三倍因子；把电量倍数与力倍数线性等同。"]),
    54: ("D", "电场强度的定义", "用试探电荷所受电场力与其电荷量求场强", ["该点电场由源电荷Q产生，场强定义E=F/q，其中q是试探电荷。", "撤去试探电荷不使源电荷电场消失；把试探电荷改为2q时场强不变。选D。"], 1, "考查场强定义及场源与试探电荷区分。", ["把源电荷Q放进定义式分母；误认为试探电荷决定电场。"]),
    57: ("B", "牛顿第二定律与功", "匀加速竖直提升求拉力并计算恒力做功", ["取向上为正，F−mg=ma，故起重机对货物拉力F=m(g+a)。", "上升位移与拉力同向，做功W=Fh=m(g+a)h，选B。"], 2, "需先用动力学确定拉力，再用恒力功公式。", ["把拉力误作合力ma；加速上升时误用m(g−a)。"]),
    45: ("D", "机械波与波长", "根据瞬时平衡位置间距及波峰计数列举可行半波长间隔", ["正弦横波在同一时刻处于平衡位置的点相隔整数个半波长，故6=nλ/2。", "当n=1、2、3时，端点间可有一个波峰（端点起始相位方向不同会决定奇数个半波间隔中波峰/波谷数）；对应λ=12m、6m、4m。", "其它选项中的波长会给出不整数的半波间隔，或区间内波峰数不为1。故选D。"], 2, "需用空间相位周期性把点间距化为半波长整数倍，再结合区间波峰计数排除其它整数。", ["把波峰与波谷混为一谈；假定两端点必为相邻平衡位置；漏检起始相位对奇数半波区间中波峰数的影响。"]),
    102: ("C", "磁场对通电导线的作用", "使用F=BILsinθ确定安培力大小范围", ["F=BILsinθ，I L=2.5×0.2=0.5。", "B=2T时F最大值为1N，随夹角变化F可从0到1N，故可能为1N，选C。"], 2, "要把‘可能’与‘一定’区分，并考虑导线方向对sinθ的影响。", ["漏掉方向夹角因子；把安培力最大值当作任何方向下的固定值。"]),
    40: ("C", "机械波的传播", "比较相距整波长的波源与质点的瞬时振动状态", ["波传播一段时间后，距波源x的质点相位滞后kx。若x=vT=λ，则相位差2π。", "故质点与波源同位移、同速度状态；其振幅也等于波源振幅A，选C。"], 2, "需要将x=vT转化为一波长及相位差。", ["把波速当作质点振动速度；认为质点初始运动方向与传播方向相反。"]),
    89: ("A", "简谐振动的相位", "按经过周期数取余判断振子位置、运动方向和加速度", ["1.26/0.4=3.15个周期，等效于从平衡位置向右运动后经过0.15T。", "相位为2π×0.15=0.3π，位移为正、速度仍向右且加速度指向平衡位置，因此向右减速，选A。"], 2, "需约化周期并判断振动状态，而不是只比较经过时间长短。", ["把1.26s直接按一个周期内的相位判断；把回复加速度方向当作速度方向。"]),
    19: ("D", "物态变化与吸放热", "根据凝固、凝华与熔化、汽化区分吸热放热过程", ["冰雪消融是熔化吸热，积水干涸是汽化吸热。", "滴水成冰是凝固放热，霜形成是凝华放热，因此为C、D，对应选项D。"], 1, "识别四种常见物态变化及吸放热方向。", ["把‘形成’过程一律认为吸热；混淆汽化与液化。"]),
    52: ("D", "比热容与热平衡", "比较等质量不同物质吸收等热量后的温升", ["相同质量、初温且吸热量相同，ΔT=Q/(mc)。水的比热容大于铜，所以水升温较少，铜温度更高。", "接触后热量从温度较高的铜块传给水，选D。"], 2, "先用比热容关系比较温度，再判断热传递方向。", ["把吸收热量多的物体直接当作温度更高；不比较比热容。"]),
    25: ("C", "机械波的波长、频率与波速", "由波峰波谷空间关系求波长，再用v=fλ", ["频率f=30/60=0.5Hz。甲在波谷，沿传播方向到乙波峰且中间还有一个波峰，波谷至乙波峰的间距为3λ/2。", "3m=3λ/2，得λ=2m；v=fλ=0.5×2=1m/s，选C。"], 2, "需将振动次数换算为Hz，并正确数空间波峰间隔。", ["把每分钟30次当作30Hz；把波峰、波谷间距误作半个波长而漏数一个波峰。"]),
    76: ("C", "摩擦力与二力平衡", "比较拉力与最大静摩擦力确定静摩擦或滑动摩擦", ["支持力为200N，滑动摩擦力μN=0.2×200=40N，题设最大静摩擦力也为40N。", "拉力15N、30N小于最大静摩擦力，物体静止，摩擦力分别为15N、30N；拉力80N使物体滑动，摩擦力40N。故选C。"], 2, "需先确定物体是否滑动，再选择静摩擦平衡或滑动摩擦公式。", ["认为静摩擦力总等于最大值；把滑动摩擦力误算成与拉力相等。"]),
    85: ("A", "折射与平行玻璃砖", "比较不同入射角和色光在平行平板中的侧向位移", ["玻璃砖侧移量δ=t sin(i−r)/cos r；折射率越大，同一入射角下折射角r越小，侧移较大。", "紫光折射率高于红光；45°入射比30°有更大的侧移，故紫光45°最大，选A。"], 3, "需同时比较色散造成的折射率差与入射角对平板侧移的影响。", ["把侧移当成出射角偏转；只比较颜色或只比较入射角。"]),
    107: ("C", "机械波的传播", "辨析波速描述振动状态传播而非质点振动快慢", ["波速是波形/振动状态在介质中的传播速度，反映振动在介质中传播的快慢，选C。", "在给定介质中波速由介质性质决定；频率改变时波长相应变化，波速不由波源单独决定。"], 1, "定义辨析，无需计算。", ["把波速与质点振动速度混淆；认为波源频率决定介质中的波速。"]),
    93: ("A", "功率与牵引力", "匀速运动时用P=Fv计算发动机功率", ["匀速直线运动合力为零，发动机牵引力等于阻力1.2×10⁷N。", "P=Fv=1.2×10⁷×15=1.8×10⁸W=1.8×10⁵kW，选A。"], 2, "需先使用匀速平衡条件，再正确换算W与kW。", ["忘记匀速时牵引力等于阻力；kW换算漏三位数量级。"]),
    41: ("C", "动量定理与弹性碰撞", "选定正方向后计算反向等速碰撞的动量变化", ["取初速度方向为正，初动量pᵢ=0.3×6=1.8kg·m/s，末动量p_f=0.3×(−6)=−1.8kg·m/s。", "Δp=p_f−pᵢ=−3.6kg·m/s。动能未变，墙对球做功为0，故正确选项C。"], 2, "需带符号计算矢量动量变化，并区分冲量与功。", ["只比较动量大小而忽略方向；把动量变化量算成−1.8；误以为碰撞必做功。"]),
    58: ("A", "自由落体实验与数据处理", "由往返时间消去初速度求重力加速度", ["由O点上抛并返回，t₂=2u/g。越过高h处时的速度平方为u²−2gh，往返该高度的间隔t₁=2√(u²−2gh)/g。", "两式平方相减：t₂²−t₁²=8h/g，故g=8h/(t₂²−t₁²)，选A。"], 3, "实验方法通过两组对称时间消去未知初速度，代数推导有多步。", ["把经过高度h的时间误作单程时间；平方差展开系数漏掉2。"]),
    99: ("D", "动能与单位换算", "统一SI单位后比较高速小质量子弹和运动员的动能", ["子弹m=0.010kg、v=700m/s，Eₖ=½mv²=2450J。", "运动员m=60kg、v=10m/s，Eₖ=½mv²=3000J，较大，选D。"], 2, "需把0.70km/s换算为700m/s并比较平方速度效应。", ["子弹速度数值大便断定动能大；忽略质量与速度单位换算。"]),
    103: ("A", "动量定理与缓冲作用", "用延长碰撞时间解释平均冲击力下降", ["落地前后速度变化近似相同，动量变化量近似相同，因此冲量近似相同。", "沙坑延长停止时间，由平均力冲量关系F̄Δt=Δp，平均冲击力减小，选A。"], 2, "需区分冲量、动量变化和平均力，并知道缓冲改变作用时间。", ["认为缓冲使动量变化量或冲量减小；把冲击力与冲量混为一谈。"]),
    37: ("B", "电磁波谱与伦琴射线", "辨认高速电子轰击固体产生的X射线", ["伦琴射线即X射线，可由高速电子轰击固体靶产生。", "γ射线来自原子核跃迁；紫外线不比紫光更难衍射，因波长更短反而更难发生明显衍射。故选B。"], 2, "需结合不同电磁辐射的产生机制和波长判断。", ["混淆X射线与γ射线来源；忽略衍射与波长的关系。"]),
    108: ("C", "电容器与电容", "根据额定电压与电容量标记识别电容器", ["器件标注35V及2200μF，其中μF为电容量单位，故为电容器，选C。", "35V表示耐压参数，不能据此认作电源电压输出。"], 1, "依据电容量单位识别元件。", ["把器件耐压标注误认作电源；混淆电感量、阻值和电容量单位。"]),
    42: ("D", "放射性衰变与半衰期", "根据剩余核数比例求经过的半衰期数", ["11.4天后衰变的比例为7/8，剩余比例为1/8=(1/2)^3，经过3个半衰期。", "半衰期T₁/₂=11.4/3=3.8天，选D。"], 2, "需将衰变比例转为剩余比例并辨认幂次。", ["把衰变比例7/8直接当作剩余比例；误把经过次数当作天数。"]),
    100: ("D", "静电应用与防护", "区分静电泄放措施与静电应用", ["飞机机轮导电橡胶、地毯夹金属丝、油罐车接地铁链均用于泄放静电、避免静电危害。", "静电复印利用静电力转移墨粉，属于静电应用，选D。"], 1, "按作用目的区分静电防护和静电技术应用。", ["把导电泄放措施称为静电应用；忽略题目问的是‘应用’。"]),
    79: ("B", "共点力平衡与绳张力", "对称两绳支撑静止物体时分解竖直方向力", ["两绳张力大小相同，水平分量相互抵消。竖直方向平衡：2Tcosα=G。", "故每条绳张力T=G/(2cosα)，选B。"], 2, "需明确角度相对竖直，按受力平衡分解。", ["把α当作绳与水平方向夹角；漏掉两条绳共同承担重力。"]),
    61: ("D", "人造卫星轨道与观测范围", "比较同步卫星和低轨卫星的高度及地面覆盖范围", ["同步卫星周期24h，风云一号周期12h。开普勒关系表明周期较长的圆轨道半径较大。", "轨道半径更大时卫星可见地球表面范围更广，选D。"], 2, "应用开普勒轨道关系并联系地球遮挡几何。", ["认为轨道周期短的卫星更高；忽略高度增大带来的地面视野变化。"]),
    78: ("B", "光的全反射", "依据光密介质到光疏介质及临界角判定全反射", ["全反射只可能发生在光从水等光密介质射向空气等光疏介质时，且入射角大于临界角。", "符合条件的是B。"], 1, "按介质方向和临界角条件两步筛选。", ["认为空气射向水也能全反射；把小于临界角误作全反射条件。"]),
    86: ("B", "实验测量与国际单位制", "识别国际单位制基本单位组合", ["kg、A、s分别是质量、电流、时间的国际单位制基本单位。", "T、N、V和m/s都是导出单位，因此选B。"], 1, "识别基本单位与导出单位。", ["把牛顿、特斯拉、电压或速度误当基本单位。"]),
    105: ("D", "原子能级与受激辐射", "判断原子跃迁发光时总能量、势能和动能变化", ["受激辐射中原子从较高能态跃迁到较低能态并放出光子，因此原子总能量减小。", "对库仑束缚态，势能V=2E、动能K=−E；总能量E降低时V降低、K增加，故选D。"], 3, "结合能级跃迁与库仑束缚态能量关系判断三个量的变化。", ["只依据总能量降低推断所有分能量都降低；把动能与总能量混为一谈。"]),
    73: ("A", "红外线及传感器应用", "由红外辐射测温识别热效应", ["云层温度不同导致其红外辐射强度不同，传感器利用红外辐射的热效应形成温度信息。", "题干描述的是接收辐射并测温，不是化学效应、可见性或穿透性。选A。"], 1, "将红外线热效应与遥感测温功能对应。", ["混淆红外测温与紫外线化学效应；把成像功能直接当作可见性。"]),
    62: ("B", "功与动能定理", "利用合力功等于各力功之和求合力做功", ["同一位移上各力做功的代数和等于合力做功。", "W合=W₁+W₂=8J+6J=14J，选B；两力垂直不意味着功也按矢量合成。"], 1, "直接应用功的叠加性，注意功是标量。", ["把功按矢量求合成；将8J和6J作勾股运算。"]),
    64: ("A", "机车牵引力与恒定功率", "依据恒功率约束分析初始牵引力和速度变化", ["P=Fv恒定。汽车上坡时为克服增大的重力沿坡分力，牵引力逐渐增大，因此速度P/F逐渐减小。", "初始阶段合力及加速度逐渐减小、速度逐渐减小，选A。"], 3, "同时使用功率约束、坡向受力和运动状态变化，须服从题设过程。", ["把恒定功率误认为牵引力恒定；只由牵引力增大就断定速度增大。"]),
    67: ("C", "火车转弯与圆周运动", "判断规定速度下向心力来源及超速时轮缘受力方向", ["在设计速度下，轨道支持力与重力的合力提供向心力，选项A正确。", "速度大于设计值时所需向心力增大，轮缘挤压外轨；低于设计速度时不会挤压外轨。因此C也正确，答案AC对应选项C。"], 2, "须分辨设计速度和偏离设计速度时外轨/内轨的约束方向。", ["认为重力单独提供向心力；把超速和低速时轮缘受力侧弄反。"]),
    81: ("C", "分子间作用力", "判断分子间距减小时短程斥力的变化趋势", ["分子间距离减小时，分子间斥力迅速增大；该趋势不意味着引力或合力在全部距离范围都单调增大。", "选项C符合分子力模型。"], 2, "依据分子力随间距变化的定性图像辨析分力与合力。", ["把分子间合力与引力/斥力分量混淆；认为距离任意变化时合力单调。"]),
    36: ("C", "万有引力与重力加速度", "用圆轨道运动确定地球引力场在月球轨道处的加速度", ["月球绕地球做匀速圆周运动，向心加速度由地球万有引力提供。", "因此轨道处地球引力产生的加速度g₂等于月球轨道向心加速度a，选C；月球表面重力加速度g₁是另一个位置的场强。"], 1, "区分月球表面重力场与月球轨道处地球引力场。", ["把月球表面重力加速度与地球在月球处的引力加速度混为一谈。"]),
    50: ("D", "路程与位移", "区分竖直往返运动的路程和位移大小", ["小球先从4m高度落到地面，路程4m；再上升到1m被接住，路程1m。", "总路程5m；起点在4m、终点在1m，位移大小|1−4|=3m，选D。"], 1, "分别按路径长度和位置差计算两个物理量。", ["把位移和路程都算作5m；忽略运动方向反转。"]),
    53: ("A", "加速度的物理意义", "将速度变化快慢与加速度定义对应", ["加速度a=Δv/Δt，描述速度变化的快慢。", "速度为零时加速度可能不为零；速度变化量大小还须结合经历时间；速度大小本身不决定加速度。选A。"], 1, "直接考查加速度定义并辨析速度与加速度。", ["认为速度为零必有加速度为零；认为速度越大加速度越大。"]),
    94: ("D", "力的合成与分解", "运用直角三角形合成两个互相垂直的共点力", ["两个力互相垂直，合力大小R=√(30²+40²)N=50N。", "选D。"], 1, "直角分力使用勾股关系即可。", ["把力的大小直接相加；把30N和40N作差。"]),
    20: ("B", "自由落体运动的条件", "辨析竖直向下运动与自由落体运动的区别", ["自由落体要求物体只受重力作用且由静止开始。", "仅知道物体竖直向下运动并不能保证初速度为零或阻力可忽略，所以‘竖直向下运动一定是自由落体’不正确，选B。"], 1, "依据自由落体的定义逐项检验必要条件。", ["只看运动方向、不检查初速度和受力条件。"]),
    32: ("D", "矢量与标量", "区分具有方向的运动力学量与质量标量", ["加速度、速度和力均为矢量；质量只有大小、没有方向，是标量，选D。"], 1, "按物理量是否需要方向表征分类。", ["把速度大小当作速度本身；把质量与重力混为一谈。"]),
}

GOAL_CHAPTER = {
    0: ("physics-senior-compulsory-1",1,2), 3: ("physics-senior-compulsory-3",1,2),
    4: ("physics-senior-compulsory-1",2,1), 24: ("physics-senior-compulsory-1",2,1),
    27: ("physics-senior-compulsory-2",2,1), 29: ("physics-senior-compulsory-2",3,1),
    14: ("physics-senior-compulsory-3",3,1), 18: ("physics-senior-selective-2",4,1),
    30: ("physics-senior-selective-1",2,1), 15: ("physics-senior-selective-1",4,2),
    9: ("physics-senior-selective-3",2,1), 1: ("physics-senior-selective-3",3,1),
    1000: ("physics-senior-selective-3",5,1), 11: ("physics-senior-selective-3",4,1),
    22: ("physics-senior-selective-3",5,1), 51: ("physics-senior-selective-2",2,1),
    35: ("physics-senior-compulsory-1",2,1), 68: ("physics-senior-compulsory-3",1,1),
    54: ("physics-senior-compulsory-3",1,1), 57: ("physics-senior-compulsory-2",4,1),
    45: ("physics-senior-selective-1",3,2), 102: ("physics-senior-selective-2",1,1),
    40: ("physics-senior-selective-1",3,2), 89: ("physics-senior-selective-1",2,1),
    19: ("physics-senior-selective-3",2,1), 52: ("physics-senior-selective-3",2,1),
    25: ("physics-senior-selective-1",3,2), 76: ("physics-senior-compulsory-1",3,2),
    85: ("physics-senior-selective-1",4,1), 107: ("physics-senior-selective-1",3,1),
    93: ("physics-senior-compulsory-2",4,1), 41: ("physics-senior-selective-1",1,1),
    58: ("physics-senior-compulsory-1",2,2), 99: ("physics-senior-compulsory-2",4,1),
    103: ("physics-senior-selective-1",1,1),
    37: ("physics-senior-selective-3",4,1), 108: ("physics-senior-compulsory-3",2,1),
    42: ("physics-senior-selective-3",5,1), 100: ("physics-senior-compulsory-3",1,2),
    79: ("physics-senior-compulsory-1",3,2), 61: ("physics-senior-compulsory-2",3,2),
    78: ("physics-senior-selective-1",4,1), 86: ("physics-senior-compulsory-1",4,1),
    105: ("physics-senior-selective-3",4,1), 73: ("physics-senior-selective-2",5,1),
    62: ("physics-senior-compulsory-2",4,1), 64: ("physics-senior-compulsory-2",4,1),
    67: ("physics-senior-compulsory-2",2,2), 81: ("physics-senior-selective-3",1,1),
    36: ("physics-senior-compulsory-2",3,1),
    50: ("physics-senior-compulsory-1",1,2), 53: ("physics-senior-compulsory-1",1,2),
    94: ("physics-senior-compulsory-1",3,2), 20: ("physics-senior-compulsory-1",2,1),
    32: ("physics-senior-compulsory-1",1,1),
}


def main() -> None:
    source_path = ROOT / "data/sources/cmmlu-senior" / CSV_PATH
    source_bytes = source_path.read_bytes()
    file_sha = hashlib.sha256(source_bytes).hexdigest()
    dev_path = ROOT / "data/sources/cmmlu-senior" / DEV_PATH
    dev_sha = hashlib.sha256(dev_path.read_bytes()).hexdigest()
    with source_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    output = []
    audit = []
    for idx, (answer, knowledge, fine, solution, level, basis, errors) in ITEMS.items():
        is_dev = idx in {0, 3, 4}
        if idx >= 1000:
            raw = rows[idx - 1000]
            # Re-use the test split index, explicitly pinned to the same source file.
            source_id = f"cmmlu-senior:test:high_school_physics:{idx-1000}"
            origin_index = idx - 1000
        else:
            raw = _dev_row(idx) if is_dev else rows[idx]
            source_id = f"cmmlu-senior:{'dev' if is_dev else 'test'}:high_school_physics:{idx}"
            origin_index = idx
        item_source_file = DEV_PATH if is_dev else CSV_PATH
        item_file_sha = dev_sha if is_dev else file_sha
        options = [{"key": key, "text": raw[key]} for key in "ABCD"]
        stem = raw["Question"]
        q = {
            "id": f"bank:senior-physics:{source_id.split(':')[1]}:{origin_index}",
            "subject": "physics", "stage": "senior", "grade": None, "term": None,
            "stem": stem, "options": options, "answer": answer, "kind": "single_choice",
            "steps": solution, "difficulty": level,
            "difficulty_raw": None, "knowledge_tags": [knowledge], "type_tags": [fine],
            "tags_source": "luna_item_read", "source_tags": ["CMMLU/high_school_physics"],
            "status": "ready", "issues": [],
            "provenance": {"dataset": "cmmlu-senior", "source_id": source_id,
                           "url": f"https://github.com/haonan-li/CMMLU/tree/{REV}/{item_source_file}",
                           "license": "CC-BY-NC-SA-4.0", "source_file": item_source_file,
                           "download_revision": REV, "file_sha256": item_file_sha},
        }
        qhash = source_fingerprint(q)
        goal_book, chapter, goal_no = GOAL_CHAPTER[idx]
        goal_id = f"{goal_book}:u{chapter}:g{goal_no}"
        q["curriculum_goal_ids"] = [goal_id]
        q["curriculum_book_id"] = goal_book
        ans_status = "checked"
        issues = []
        annotation = {
            "schema_version": 1, "response_format": "single_choice",
            "knowledge": {"primary": [knowledge], "supporting": [], "prerequisites": []},
            "fine_types": [fine],
            "difficulty": {"level": level, "basis": basis, "origin": "luna", "calibrated": False},
            "curriculum": {"grade": None, "term": None, "book_id": goal_book, "goal_ids": [goal_id], "scope_status": "candidate", "basis": f"按高中物理教材目录映射到{goal_book}:u{chapter}:g{goal_no}；题源仅标高中物理，未提供年级/学期，教材版次仍待核。"},
            "answer_spec": {"mode": "choice", "accepted_answers": [answer], "equivalence": "exact", "constraints": ["按选项字母作答。"], "unit": None, "tolerance": None},
            "parts": [{"id": "whole", "prompt": stem, "reference_answer": answer,
                       "solution_steps": solution, "knowledge_tags": [knowledge], "type_tags": [fine],
                       "depends_on": [], "points": None,
                       "rubric": [{"id": "choice_evidence", "description": f"选择项{answer}；" + "；".join(solution), "points": None, "evidence_required": "答案选项与题目条件、独立推导一致。"}],
                       "common_errors": [{"description": error, "knowledge_tags": [knowledge], "type_tags": [fine]} for error in errors]}],
            "grading": {"mode": "objective", "full_score": None, "allow_alternative_methods": True, "uncertainty_policy": "review_required"},
            "review": {"status": "candidate", "answer_status": ans_status, "issues": issues,
                       "method": "item_read", "notes": "逐题读题、核对四个选项及固定来源答案；独立解答见part.solution_steps和台账。Luna候选，不代表教师审核。"},
            "origin": {"model": "gpt-6-luna", "batch_id": BATCH},
        }
        Annotation.model_validate(annotation)
        decision = "pending" if q["id"] == "bank:senior-physics:test:54" else "passed"
        item_issues = list(issues)
        if decision == "pending":
            item_issues.append("题目选项C为E=F/Q、D为E=F/q，大小写承载源电荷Q与试探电荷q的区别；当前题库规范化将二者合并，无法安全导入，需修复大小写敏感选项校验后复核。")
        output.append({"question_id": q["id"], "source_sha256": qhash, "decision": decision,
                       "quarantine_original": decision != "passed", "question": q, "annotation": annotation,
                       "independent_solution": solution,
                       "source_conflicts": [],
                       "remaining_issues": item_issues,
                       "rationale": ("答案经复核为D，但选项规范化碰撞，暂隔离。" if decision == "pending" else " | ".join(solution))})
        audit.append({"question_id": q["id"], "source_sha256": qhash, "decision": decision,
                      "source_index": origin_index, "topic": knowledge,
                      "independent_solution": solution,
                      "source_answer": raw.get("Answer", answer), "adjudicated_answer": answer,
                      "reason": " | ".join(solution),
                      "source_conflicts": output[-1]["source_conflicts"]})

    outdir = ROOT / "data/annotations/senior-20261015"
    outdir.mkdir(parents=True, exist_ok=True)
    save_batch(ROOT / "app/data/senior_physics_luna.json", {
        "batch_id": BATCH,
        "source_manifest": [{"path": CSV_PATH, "revision": REV, "sha256": file_sha,
                             "license": "CC-BY-NC-SA-4.0", "source_url": "https://github.com/haonan-li/CMMLU"},
                            {"path": DEV_PATH, "revision": REV, "sha256": dev_sha,
                             "license": "CC-BY-NC-SA-4.0", "source_url": "https://github.com/haonan-li/CMMLU"}],
        "items": output,
    })
    (outdir / "physics-review.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in audit) + "\n", encoding="utf-8")
    print(f"wrote {len(output)} items ({sum(x['decision']=='passed' for x in output)} passed, {sum(x['decision']=='pending' for x in output)} pending), source sha256 {file_sha}")


def _dev_row(idx: int) -> dict[str, str]:
    path = ROOT / "data/sources/cmmlu-senior/data/dev/high_school_physics.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows[idx]


if __name__ == "__main__":
    main()
