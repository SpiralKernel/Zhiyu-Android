"""Item-read AGIEval senior physics questions, pinned to its v1.1 source snapshot."""
from __future__ import annotations
import copy,hashlib,json,re,sys,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.question_annotation import Annotation,source_fingerprint
from app.senior_bank import save_batch
REV='84ab72d94318290aad2e4ec820d535a95a1f7552'; BATCH='senior-20261015-physics-agieval-1'
# idx -> (book, unit, goal, knowledge, fine type, difficulty, basis, steps, errors)
S={
12:('physics-senior-compulsory-3',4,2,'闭合电路欧姆定律与电动势内阻实验','比较伏安法、伏阻法和安阻法测电源参数的器材方案',2,'需根据已知电阻、电压/电流测量量评估能否拟合E、r；题目比较实验可测性。',
 ['伏安表加滑动变阻器可测多组端电压与电流，作U-I关系求电动势与内阻，方案A可行。','电压表配多个已知定值电阻，可由I=U/R取得外电流并建立U-I关系，方案B可行。','电流表和电阻箱给出已知外电阻与电流，可用E=I(R+r)求源参数，方案C可行。','两个电流表和滑动变阻器没有独立的电压读数或确定电阻来形成电压-电流关系，最难准确求E与r，选D。'],['把任何包含电流表的电路都误认为足以测电动势和内阻。','忽略实验中必须获得可确定的端电压或外电阻。']),
48:('physics-senior-selective-2',2,2,'涡流与楞次定律','判断磁铁在绝缘环叠成的导体筒中下落的速度变化',2,'楞次定律使涡流磁场阻碍磁通变化，磁铁受到随速度增大的电磁阻力并趋于终端速度。',
 ['磁铁下落时穿过每个闭合铜环的磁通量随位置改变，环中产生感应电流。','依楞次定律，感应磁场阻碍磁铁相对线圈的运动，产生向上的电磁阻力；下落速度增加时感应效应增强。','经过较长筒段后，电磁阻力趋近于重力，速度逐渐趋于稳定的终端值，符合C。'],['把铜环误认为绝缘而忽略感应电流。','认为磁铁下落时电磁力会帮助而非阻碍磁通变化。']),
73:('physics-senior-selective-3',1,2,'阿伏伽德罗常数与物质的量','估算全球同时清点1g水分子所需时间',2,'先用物质的量求粒子数，再除以全球每小时计数总量并换算成年。',
 ['1g水的物质的量约为1/18 mol，分子数N≈(1/18)×6×10²³≈3.3×10²²。','60亿人每小时合计可数6×10⁹×5000=3×10¹³个。','所需时间约为1.1×10⁹h，除以8760h/年约1.27×10⁵年，最接近10万年，选C。'],['把1g水的摩尔质量当作1g/mol。','漏掉60亿人同时计数的乘数。']),
83:('physics-senior-selective-2',3,2,'理想变压器与远距离输电','提高变压器匝数比时比较输电线损耗及损耗比',3,'先由匝数比求副边电压和线路电流，再用I²R推损耗。',
 ['忽略变压器损耗，副边电压U₂=kU，输送功率P固定，线路电流I=P/(kU)。','线路损耗P₁=I²R=(P/(kU))²R。','匝数比提高到nk后，线路电流变为原来的1/n，损耗变为原来的1/n²；因此P₁及P₂/P₁对应D。'],['把输电线电流与匝数比写成正比。','损耗只取一次方电流而非I²。']),
88:('physics-senior-compulsory-3',5,2,'电磁波传播与卫星通信','估算地面卫星电话经地球同步卫星中继的最短传播时延',3,'由月球轨道数据用开普勒第三定律估算地球同步轨道半径，再估计地面—卫星—地面的光程。',
 ['月球绕地周期27天、轨道半径3.8×10⁵km；同步周期1天。开普勒第三定律得r同步=3.8×10⁵×(1/27)^(2/3)km≈4.22×10⁴km。','扣除地球半径约6400km，同步卫星高度约3.58×10⁴km。地面经卫星到地面的最短总传播距离约2h≈7.16×10⁴km。','t≈7.16×10⁷m/(3×10⁸m/s)≈0.24s，最接近0.25s，选B。'],['误把单程地面到卫星当作完整通信链路。','将地球同步轨道半径误当作离地高度。']),
93:('physics-senior-selective-2',3,1,'理想变压器电压变换关系','由匝数比求输入电压变化所对应的输出电压变化',1,'理想变压器输入输出电压变化量之比等于匝数比。',
 ['理想变压器满足ΔU₂/ΔU₁=N₂/N₁=10。','输入电压增加20V，输出电压增加200V，选D。'],['把匝数比N₁:N₂=1:10误读为输出变化更小。']),
122:('physics-senior-selective-2',4,1,'电磁振荡、谐振与无线通信','辨析IC卡的LC谐振供能及读卡器与卡片通信',2,'LC电路的固有频率决定谐振响应，但偏离频率仍可有感应电流；卡片也能回传数据。',
 ['读卡器发射电磁波，在IC卡线圈中感生电流并给电容充电，能量来自读卡器电磁场而非卡内电池，A错。','LC回路在与其固有频率匹配时响应最强，但其他频率仍可在线圈中产生感应电流，B的“仅当”过强，C也错。','IC卡完成处理后需要向读卡器传输数据，D错误；题源标签B表示“仅当特定频率才能有效工作”，与理想谐振回路的响应峰值含义需谨慎，按高中谐振模型可理解为达到有效工作条件，答案B。'],['把谐振响应最大误认为其他频率完全没有感应电流。','误认为无源IC卡不能回传信息。']),
142:('physics-senior-selective-2',3,2,'远距离输电与线路损耗','由损耗变化目标反求输电电压',2,'固定输送功率和线路电阻时，线路损耗与输电电压平方成反比。',
 ['I=P/U，线路损耗P损=I²R=P²R/U²。','要使损耗变成原来的1/4，电压须增至原来的2倍，即440kV，选C。'],['认为损耗和电压成正比。','把损耗降为1/4误当电压升为4倍。']),
163:('physics-senior-selective-3',2,1,'理想气体温度、压强与分子运动','根据夜间降温和轮胎压强变化判断气体微观量',2,'密闭近似定容气体降温使平均平动动能和压强降低，粒子数密度不变。',
 ['轮胎近似封闭且容积变化小，夜间温度降低。','理想气体分子平均平动动能与绝对温度成正比，故平均动能更小，A正确。','气体分子数和体积近似不变，单位体积粒子数不变；不能断言所有分子的速率都减小；壁面平均作用力降低，B、C、D错误。'],['把压强降低解释为气体分子数减少。','把平均速率降低误说成每个分子速率都降低。']),
166:('physics-senior-selective-2',3,2,'变压器变比与实际输出电压','依据副线圈输出偏低判断匝数调整方向',2,'副边电压低于灯泡额定电压时，应增加副线圈匝数以提高变比。',
 ['当前副边2.5V低于额定3.8V，需提高副边电压。','变压器U₂/U₁≈N₂/N₁；仅增加副线圈匝数会提高副边电压，B符合。','只增加原线圈匝数会降低输出；原副匝数都加倍比值不变；并联灯泡不能抬高端电压。'],['通过增加原线圈匝数提高降压变压器输出。','认为增加负载并联支路会改变理想变压器变比。']),
173:('physics-senior-selective-2',3,2,'理想变压器、电功率与交流有效值','计算电动汽车充电变压器副边电流有效值和频率',2,'由正弦输入求有效值和频率，变比求副边有效电压，再用P=UI。',
 ['输入u=220√2sin(100πt)V，故U₁=220V有效值，角频率100πrad/s，f=50Hz。','匝数比N₁:N₂=1:2，副边有效电压U₂=440V。','I₂=P₂/U₂=8800/440=20A；理想变压器不改变频率，故50Hz，选A。'],['把220√2V峰值当成有效值。','认为变压器会改变交流频率。']),

99:('physics-senior-compulsory-3',2,2,'电容器、电荷量变化与电流','由电容器电压变化和时间求跨膜平均电流',2,'按Q=CU计算电荷变化，并用平均电流定义复算；此题将保留源标签冲突并隔离。',
 ['电势差从−70mV变为+30mV，变化量ΔU=0.100V。','电荷量变化ΔQ=CΔU=1.0×10⁻⁸×0.100=1.0×10⁻⁹C。','平均电流I=ΔQ/Δt=1.0×10⁻⁹/(2.0×10⁻³)=5.0×10⁻⁷A，即选项D；AGIEval标签标B（2×10⁻⁷A），与直接复算不符，故pending。'],['忽略电压由负变正，应取100mV变化。','把毫秒或毫伏单位换算错误。']),
110:('physics-senior-compulsory-2',1,2,'平抛运动与斜面相交','比较以不同比例水平初速度抛出后落在同一斜面上的速率',2,'用斜面几何关系求飞行时间，证明末速大小正比于水平初速度。',
 ['设斜面倾角为θ，水平初速度u的小球飞行t后落到斜面，竖直位移满足(1/2)gt²=(ut)tanθ。','因此t=2u tanθ/g，竖直末速度gt=2u tanθ；末速v=√(u²+g²t²)=u√(1+4tan²θ)。','同一斜面上比例因子相同，甲初速度v、乙初速度v/2，则落地速率之比为2:1，选A。'],['将水平射程误当作落地速率。','认为两球飞行时间相同，忽略抛出速度影响。']),
118:('physics-senior-selective-3',3,1,'热力学第一定律与内能变化','根据吸放热和气体做功判断内能变化的可能性',2,'用ΔU=Q−W判断各过程；热量或功单独一项不能决定内能变化符号。',
 ['吸热Q>0且对外做功W>0时，ΔU=Q−W；若Q>W，内能增加，因此C“可能增加”正确。','放热时内能还取决于做功，A不一定；对外做功时还取决于吸放热，B不一定。','放热Q<0且对外做功W>0时ΔU=Q−W<0，不可能不变，D错误。'],['把吸热必然等同内能增加。','混淆气体对外做功与外界对气体做功的符号。']),
131:('physics-senior-selective-3',1,1,'分子间作用力与布朗运动','辨析扩散、布朗运动与分子引力斥力的性质',2,'区分分子热运动的温度依赖、悬浮粒子布朗运动及分子力的共存。',
 ['扩散快慢与温度有关，A错误。','布朗运动是液体中悬浮微粒的无规则运动，不是液体分子本身的运动，B错误。','分子间同时存在引力和斥力，C正确。','分子力随间距的变化并非引力总是增大；引力通常在一定范围内随间距增大而减小，D错误。'],['将布朗运动等同液体分子热运动。','认为分子引力随距离增大总是增大。']),
156:('physics-senior-compulsory-2',2,2,'匀速圆周运动与周期关系','由合力随半径幂律和周期反比求指数n',2,'由F=mr(2π/T)²和T∝1/r推出F∝r³。',
 ['匀速圆周运动合力F=m(2π/T)²r。','已知T∝r⁻¹，则1/T²∝r²，故F∝r³。','与F∝rⁿ比较得n=3，选C。'],['把向心力表达式中的r放在分母。','遗漏周期平方导致幂次错误。']),
172:('physics-senior-selective-2',1,2,'回旋加速器与带电粒子动能','由质子获得的动能求非相对论速率',2,'先把电子伏特换算为焦耳，再使用经典动能公式。',
 ['K=1.5×10⁷eV×1.6×10⁻¹⁹J/eV=2.4×10⁻¹²J。','取质子质量m≈1.67×10⁻²⁷kg，由K=(1/2)mv²得v=√(2K/m)。','v≈√(4.8×10⁻¹²/1.67×10⁻²⁷)=5.36×10⁷m/s，约5.4×10⁷m/s，选C。'],['忘记将eV转换为焦耳。','将动能公式中的2或质量因子遗漏。']),

50:('physics-senior-compulsory-3',3,1,'电阻与传感器应用','辨析热敏电阻、光敏电阻和电阻在交直流电路中的作用',1,'根据传感器的非电学量到电学量转换原理以及纯电阻元件特性判断。',
 ['热敏电阻阻值随温度变化，可用于温度测控，A正确。','光敏电阻阻值随光照变化，可作为光电传感器，B正确。','电阻丝将电能转化为内能，可用于电热设备，C正确。','电阻可限制交直流电流，但不会像电容那样主要阻交流、通直流；D错误，选D。'],['把电阻与电容的交直流特性混淆。','把传感器输出的电阻变化误认为非电学量。']),
53:('physics-senior-compulsory-3',2,2,'带电粒子受电场力与阻力的终端运动','由零电压及正反电压下终端速度推断电荷受力',3,'先由无电场终端速度确定mg=kv，再由向上终端状态反求电场力并计算反向电压下净力。',
 ['无电压时雨滴以v向下匀速，故mg=kv。','电压为U时以v向上匀速，向上电场力需平衡重力与向下阻力，qE=mg+kv=2mg。','电压反向后电场力向下，合向下驱动力为mg+2mg=3mg。终端时阻力k v_终=3mg=3kv，故速率3v、方向向下，选C。'],['认为阻力方向固定而非总与速度反向。','忘记根据向上匀速状态确定电场力是2mg。']),
57:('physics-senior-compulsory-3',2,2,'平行板电容器、电容与场强','由电荷量和板间距变化比较电势差及场强',2,'孤立电容器C∝1/d，U=Q/C，E=U/d；逐项追踪Q、d与C的变化。',
 ['板间距减为d/2，C=εA/d变为2C；电荷量变为2Q。','U₂=(2Q)/(2C)=U₁。','E₂=U₂/(d/2)=2U₁/d=2E₁，因此选C。'],['认为电容器电量改变不影响电压。','只看板距减半而漏掉电量也加倍。']),
80:('physics-senior-compulsory-3',2,2,'电容器插入电介质与电势差','判断孤立带电电容器插入介质后的电容和电压变化',2,'电容增大且总电荷保持不变，由U=Q/C求电势差变化。',
 ['电容器已充电并保持电荷量及几何尺寸不变，插入介质使介电常数增加，因此C增大。','Q固定，U=Q/C随C增大而减小，选B。'],['误将孤立电容器当成仍接恒压电源。','认为介质会使电容减小。']),

11:('physics-senior-compulsory-3',5,2,'电磁波传播与机械波介质条件','区分真空电磁波传播、声波传播介质和光的传播条件',1,'逐项应用电磁波速率、机械波介质条件和光的传播特点。',
 ['电磁波在真空中以光速c传播，A正确。','空气中的声波是纵波，B错；声波也能在液体和固体中传播，C错；光在真空中可传播，不需要介质，D错。'],['把空气声波误判为横波。','认为声波只能在空气中传播。']),
54:('physics-senior-compulsory-3',5,2,'电磁波能量传播与辐射强度','根据球面微波功率密度阈值估算两种影响的最远距离',2,'用均匀球面波强度I=P/(4πr²)，分别代入两个阈值。',
 ['距各向均匀辐射源r处功率密度I=P/(4πr²)，故r=√(P/(4πI))。','神经混乱阈值250W/m²：r=√(3×10⁷/(4π×250))≈97.7m，约100m。','严重心肺影响阈值1000W/m²：r≈48.9m，约50m，选B。'],['遗漏球面面积4πr²。','误认为阈值越高对应距离越远。']),
61:('physics-senior-selective-2',1,2,'洛伦兹力与带电粒子在有界磁场中的圆周运动','由磁区弦长和速度偏转角求轨道半径及磁感应强度',3,'粒子圆弧偏转角为60°；以入口、出口同在半径R边界上列圆几何，得轨道半径√3R。',
 ['带电粒子在匀强磁场中做圆周运动，轨道半径ρ=mv₀/(qB)。','入射点与出射点的速度方向夹角60°，圆弧对应弦长2ρsin30°=ρ；由区域圆几何及两交点同在边界可得ρ=√3R（等价地，入口点切线与区域弦形成30°直角三角形）。','因此B=mv₀/(qρ)=mv₀/(√3qR)=√3mv₀/(3qR)，选A。'],['把粒子轨道半径误等于磁区半径。','漏掉偏转角对应的弦和切线几何关系。']),
134:('physics-senior-selective-2',1,2,'速度选择器与洛伦兹力','判断交叉匀强电磁场中直线运动和撤场后圆周运动的依赖量',2,'直线通过时电场力与磁场力抵消；移去电场后任意非零横向磁力使轨迹为圆，电荷符号和大小不影响“是否为圆周”。',
 ['匀速直线条件是qE与qv×B大小相等、方向相反，取决于场方向、场强和速度，A、B、D相关。','撤去电场后，磁场力始终垂直速度且大小不做功，提供向心力，带电粒子轨迹为圆；电荷正负改变转向，电荷量只改变半径，但不影响轨迹是否为圆周。','因此完成两种运动与粒子的电性和电荷量（在带电且非零磁场的既定前提下）无关，选C。'],['将电荷正负对旋转方向的影响误认为会改变圆周运动性质。','认为洛伦兹力会改变速率。']),

23:('physics-senior-selective-2',2,2,'楞次定律与能量守恒','辨析楞次定律体现的普遍物理规律',1,'感应电流的效果总是阻碍磁通量变化，体现能量守恒：若感应效应助长原变化会无中生有地持续获得能量。',
 ['楞次定律规定感应电流的磁场总阻碍引起感应电流的磁通量变化。','这种“阻碍”保证外界改变磁通时必须做功，机械能或其他能量转化为电能；因此其具体体现的是能量守恒定律，选D。'],['把楞次定律和电磁感应定律混同于欧姆定律。','只根据“磁”字联想到库仑定律。']),
144:('physics-senior-selective-2',1,1,'安培力与磁场方向','判断直导线安培力的方向和大小关系',1,'安培力F=BILsinθ，方向垂直于磁场与电流方向构成的平面；直角折线的合力还依赖折线几何。',
 ['直导线所受安培力方向遵从左手定则，必垂直于磁感应强度方向，因此B正确。','力的大小为BILsinθ，随导线与磁场方向夹角改变，C错误。','力方向也垂直于导线本身，A错误；折成直角后合力大小取决于两段长度和朝向，不能断言一定减半，D错误。'],['把安培力大小误认为与电流和磁场夹角无关。','将导线形状改变后简单按总长度比例判断合力。']),
151:('physics-senior-selective-2',3,1,'理想变压器电压与匝数关系','由原副边有效电压比求副线圈匝数',1,'理想变压器满足U₂/U₁=N₂/N₁。',
 ['理想变压器电压比等于匝数比，N₂=N₁(U₂/U₁)。','N₂=800×110/220=400匝，选B。'],['把电压比与匝数比倒置。','将输入电压和输出电压的比值方向取反。']),
8:('physics-senior-selective-3',4,2,'原子能级跃迁与光子能量','由两种激光波长比求原子跃迁能级差',2,'同一介质中光子能量E=hc/λ；用已知跃迁标定能级差比例。',
 ['跃迁光子能量等于能级差，ΔE∝1/λ。','ΔE₂=ΔE₁λ₁/λ₂=1.96×0.6328/3.39 eV≈0.366 eV。','最接近0.36eV，选D。'],['误将能级差与波长成正比。','单位换算虽可约去但比值顺序颠倒。']),
65:('physics-senior-selective-3',4,2,'氢原子能级与电离','求第一激发态电离所需光子的最大波长',2,'电离阈值光子能量等于第一激发态到连续能级的能量差；波长上限对应最小电离能。',
 ['基态能量E₁为负，第一激发态能量E₂=E₁/4。','将电子从n=2电离到能量零处，最小光子能量为0−E₂=−E₁/4。','λ_max=hc/(−E₁/4)=−4hc/E₁，选C。'],['用基态到电离的能量差，而非第一激发态到电离。','忽略E₁为负能量而漏掉符号。']),
96:('physics-senior-selective-3',4,2,'光电效应与逸出功','由入射光波长和光电子最大初动能求截止频率',3,'爱因斯坦光电方程W₀=hc/λ−K_max，再计算ν₀=W₀/h。',
 ['入射光子能量hc/λ=6.63×10⁻³⁴×3.00×10⁸/(300×10⁻⁹)≈6.63×10⁻¹⁹J。','逸出功W₀=E光−K_max≈6.63×10⁻¹⁹−1.28×10⁻¹⁹=5.35×10⁻¹⁹J。','截止频率ν₀=W₀/h≈8.07×10¹⁴Hz，选B。'],['把入射光频率当作截止频率。','忘记从光子能量中减去最大初动能得到逸出功。']),
}

def norm(s):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',s or '')).strip()
def main():
 srcpath=ROOT/'data/sources/agieval-senior/data/v1_1/gaokao-physics.jsonl'; rows=[json.loads(z) for z in srcpath.read_text().splitlines()]
 dl=json.loads((ROOT/'data/sources/agieval-senior/DOWNLOAD.json').read_text()); rel='data/v1_1/gaokao-physics.jsonl'; sha=next(x['sha256'] for x in dl['files'] if x['path']==rel)
 manifest=[{'path':rel,'revision':REV,'sha256':sha,'license':dl.get('license'),'source_url':f'https://github.com/ruixiangcui/AGIEval/blob/{REV}/{rel}'}]
 current=json.loads((ROOT/'app/data/senior_physics_luna.json').read_text()); oldstems=[]
 for it in current['items']:oldstems.append(norm(it['question'].get('stem','')))
 records=[];audit=[]
 for idx,(bid,unit,goal,knowledge,fine,level,basis,steps,errors) in S.items():
  raw=rows[idx]; stem=norm(raw['question']);
  if raw.get('passage'):stem=norm(raw['passage'])+'\n'+stem
  # Exact or high overlap duplicates are not reintroduced under a new source ID.
  key=re.sub(r'[^\w]','',stem).lower()
  new_qid='bank:agieval-gaokao-physics:'+str(idx)
  dup=next((it for it in current['items'] if it['question_id']!=new_qid and len(key)>=25 and __import__('difflib').SequenceMatcher(None,key,re.sub(r'[^\w]','',norm(it['question'].get('stem',''))).lower()).ratio()>=0.82),None)
  opts=[]
  for n,text in enumerate(raw.get('options') or []):
   m=re.match(r'^\s*\(?([A-E])\)?\s*',text)
   label=m.group(1) if m else chr(ord('A')+n)
   body=text[m.end():] if m else text
   opts.append({'key':label,'text':norm(body)})
  source_id=f'agieval-gaokao-physics:{idx}'
  q={'id':'bank:'+source_id,'subject':'physics','stage':'senior','grade':None,'term':None,'stem':stem,'options':opts,'answer':raw['label'],'kind':'single_choice','has_missing_assets':bool(re.search(r'<img|\\includegraphics|\[图片|缺图',stem,re.I)),'steps':[],'provenance':{'dataset':'AGIEval v1.1 gaokao-physics','source_id':source_id,'source_file':rel,'download_revision':REV,'file_sha256':sha,'url':f'https://github.com/ruixiangcui/AGIEval/blob/{REV}/{rel}','license':dl.get('license'),'original_source':raw.get('other',{}).get('source')},'curriculum_book_id':bid,'curriculum_goal_ids':[f'{bid}:u{unit}:g{goal}']}
  qsha=source_fingerprint(q)
  ann={'schema_version':1,'response_format':'single_choice','knowledge':{'primary':[knowledge],'supporting':[],'prerequisites':[]},'fine_types':[fine],'difficulty':{'level':level,'basis':basis,'origin':'luna','calibrated':False},'curriculum':{'grade':None,'term':None,'book_id':bid,'goal_ids':q['curriculum_goal_ids'],'scope_status':'candidate','basis':f'题源标注高考物理，按已核对的高中课程目录映射到{bid}:u{unit}:g{goal}；年级、学期与版次未推断。'},'answer_spec':{'mode':'choice','accepted_answers':[raw['label']],'equivalence':'exact','constraints':['按单选选项作答。'],'unit':None,'tolerance':None},'parts':[{'id':'whole','prompt':stem,'reference_answer':raw['label'],'solution_steps':steps,'knowledge_tags':[knowledge],'type_tags':[fine],'depends_on':[],'points':None,'rubric':[{'id':'answer_and_reasoning','description':f'正确选{raw["label"]}；'+'；'.join(steps),'points':None,'evidence_required':'答案选项与物理关系、代入计算一致。'}],'common_errors':[{'description':e,'knowledge_tags':[knowledge],'type_tags':[fine]} for e in errors]}],'grading':{'mode':'objective','full_score':None,'allow_alternative_methods':True,'uncertainty_policy':'review_required'},'review':{'status':'candidate','answer_status':'checked','issues':[],'method':'item_read','notes':'逐题审读题干、全部选项和原始标签；独立推导见步骤。Luna候选，不代表教师审核。'},'origin':{'model':'gpt-6-luna','batch_id':BATCH}}
  Annotation.model_validate(ann)
  decision='passed'; conflicts=[]; issues=[]; rationale='；'.join(steps)
  if dup:
   decision='excluded';conflicts=['AGIEval题干与累计库中已有题目的规范化题干重合，避免重复收录。'];issues=['重复题不作新增练习项。'];rationale=f'重复于{dup["question_id"]}，保留原题及已有复核记录。'
  if q['has_missing_assets']:
   decision='pending';conflicts=['题干含图片标记，当前纯文本快照无法核对图像信息。'];issues=['补齐并审阅图片后再决定是否纳入。'];ann['review']['answer_status']='unknown';ann['review']['issues']=issues;rationale='题干存在未核验图片，暂隔离。'
  if idx==99:
   decision='pending'; conflicts=['AGIEval源标签B与电容定义及平均电流计算结果D冲突。'];issues=['核对原始试卷/答案标签后再决定；独立复算为5×10⁻⁷A。'];ann['review']['answer_status']='conflict';ann['review']['issues']=issues;rationale='按ΔQ=CΔU、I=ΔQ/Δt复算为选项D，但固定源标签为B，暂隔离。'
  if idx==122:
   decision='pending'; conflicts=['B项“仅当读卡机发射特定频率时才能有效工作”未定义有效工作的阈值条件，谐振峰值与其他频率仍能感生电流之间存在适用范围措辞歧义。'];issues=['澄清“有效工作”是指达到可驱动芯片的能量阈值，还是仅指出现感应电流；题干未给出匹配/带宽条件，需明确后再使用。'];ann['review']['answer_status']='conflict';ann['review']['issues']=issues;ann['review']['notes']='逐题审读题干、选项及来源答案；B项“仅当特定频率”未定义有效工作的能量/响应阈值，与LC谐振时响应最强但离谐仍有感应电流的模型表述存在歧义，暂隔离。候选标注，不代表教师审核。';rationale='“有效工作”缺少判据，LC谐振模型下离谐仍有感应电流，B项的“仅当”无法由现有条件唯一判定，暂pending。'
  rec={'question_id':q['id'],'source_sha256':qsha,'decision':decision,'quarantine_original':decision!='passed','question':q,'annotation':ann,'independent_solution':steps,'source_conflicts':conflicts,'remaining_issues':issues,'rationale':rationale}
  records.append(rec);audit.append({'question_id':q['id'],'source_sha256':qsha,'source_index':idx,'source_label':raw['label'],'decision':decision,'rationale':rationale,'independent_solution':steps})
 batch={'batch_id':BATCH,'source_manifest':manifest,'items':records}
 out=ROOT/'app/data/senior_physics_agieval_1.json';out.write_text(json.dumps(batch,ensure_ascii=False,indent=2)+'\n')
 ap=ROOT/'data/annotations/senior-20261015/physics-agieval-1-review.jsonl';ap.parent.mkdir(parents=True,exist_ok=True);ap.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in audit)+'\n')
 target=ROOT/'app/data/senior_physics_luna.json';cur=json.loads(target.read_text());ids={x['question_id'] for x in records};cur['items']=[x for x in cur['items'] if x['question_id'] not in ids]+records;cur['source_manifest'] += [m for m in manifest if (m['path'],m['sha256']) not in {(x['path'],x['sha256']) for x in cur['source_manifest']}];cur['batch_id']='senior-20261015-physics-cumulative-7';save_batch(target,cur)
 print('wrote',len(records),'AGIEval records; decisions', {x:sum(y['decision']==x for y in records) for x in ('passed','excluded','pending')})
if __name__=='__main__':main()
