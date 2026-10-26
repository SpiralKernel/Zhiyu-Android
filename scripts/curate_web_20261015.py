import json,re,hashlib
from pathlib import Path
from html import unescape
from html.parser import HTMLParser
from app.question_annotation import Annotation,source_fingerprint
root=Path('data/source-cache/tizhuang-20261015')
class Plain(HTMLParser):
 def __init__(self):super().__init__();self.out=[]
 def handle_starttag(self,tag,attrs):
  if tag in ('br','p','div','tr'):self.out.append('\n')
  if tag=='td':self.out.append(' | ')
  if tag=='sup':self.out.append('^{')
  if tag=='sub':self.out.append('_{')
  if tag=='input':self.out.append('______')
 def handle_endtag(self,tag):
  if tag in ('sup','sub'):self.out.append('}')
  if tag in ('p','div','tr'):self.out.append('\n')
 def handle_data(self,v):self.out.append(v)
def clean(s):
 p=Plain();p.feed(str(s));return re.sub(r'\n{3,}','\n\n',unescape(''.join(p.out))).strip()
# scope IDs refer to checked content, not simply the remote chapter bucket.
# Notes below are editorial AI checks; no item is marked teacher reviewed.
picks={
20736622:('physics-8-1','u1:g1','异单位速度排序',1,['36 km/h=10 m/s；54 km/h=15 m/s。','10<15<20，所以从小到大为运动员、汽车、羚羊，选C。']),
20744489:('physics-8-1','u1:g1','以车为参照物判断相对运动',2,['以卡车为参照物，旅游车相对速度等于旅游车速度减卡车速度。','A、B、C可使旅游车相对向后；D中旅游车向前更快，相对向前，故“不可能”项为D。']),
25949691:('physics-8-1','u4:g1','水面反射与水中物体折射辨析',2,['水底和鱼在水面折射成像，看起来比实际浅；倒影来自反射。','平面镜物像到镜面等距，物距1km时物像距2km；正确项为D。']),
17908547:('physics-8-1','u6:g1','多仪器测量操作辨析',2,['排水法可测不溶于水且能浸没的石块体积；刻度尺的刻度线侧紧靠被测边，故A、B正确。','天平称量过程中通过增减砝码、移动游码平衡，不能再调平衡螺母；温度计玻璃泡不能接触容器壁底，C、D错误。']),
32675107:('physics-8-2','u2:g1','平衡力与相互作用力辨析',2,['相对路旁树木骑行时位置变化；停止蹬车后因阻力而减速，A、B错误。','重力和支持力作用于同一静止物体，大小相等、方向相反，属于平衡力；相互作用力分作用于两个物体，选D。']),
7336855:('physics-8-2','u3:g1','大气压随高度变化解释气球膨胀',1,['随高度增加，大气压总体减小，气球外部压强降低。','内部气体向外膨胀，超过球囊承受范围时胀裂，选B；不是外部大气把它压裂。']),
22168633:('physics-8-2','u4:g1','排水浮力与悬浮密度两问计算',2,['水的密度取1000 kg/m³，排水重0.5N，故V排=0.5/(1000×10)=5×10^(-5) m³。','物体完全浸没，V物=V排；质量55g=0.055kg，ρ物=0.055/(5×10^(-5))=1100kg/m³。','恰好悬浮时ρ盐水=ρ物，故盐水密度1100 kg/m³。']),
21586561:('physics-8-2','u5:g1','人体尺度与功率数量级估算',2,['按体重约500N、站立面积约0.04m²估算压强约12500Pa，人体在空气中的浮力约0.65N。','从1楼到3楼上升约6m，P≈500×6/10=300W，C合理。','鸡蛋重约0.5N，举高约2m，做功约1J，D的100J偏大。']),
29927185:('physics-9-1','u1:g1','热量过程量与热值特性辨析',2,['热值是燃料的特性，不因燃烧充分与否改变；热量描述能量传递的过程，不能说物体“含有热量”。','壶中水升温时内能增大；现实加热存在损失。题目问“不正确”，选A、B。']),
27264122:('physics-9-1','u5:g1','并联电阻变化与导体电阻条件',2,['验电器利用同种电荷排斥；比较导线电阻须同时考虑材料、温度、长度和横截面积，A、B错误。','家庭用电器并联，正常两端电压相同，C正确；并联支路增多总电阻减小，D错误。']),
35579384:('math-7-1','u1:g3','绝对值等于自身的非负数判别',1,['x≥0时|x|=x；x<0时|x|=−x≠x。','满足条件的是0和正数，选D。']),
26350566:('math-7-1','u2:g1','四项有理数加减与符号处理',1,['第1问：23−17−(−7)+(−16)=23−17+7−16=−3。','第2问：12−(−18)+(−7)−15=12+18−7−15=8。']),
22797920:('math-7-1','u3:g1','乘法代数式的数量关系解释',1,['数字与字母并列表示乘法。','5a表示5与a的积，或a的5倍。']),
13907195:('math-7-1','u4:g3','负号去括号逐项变号辨误',1,['括号前是负号，括号内每一项均改变符号。','−(2x+y−z)=−2x−y+z，原式错误。']),
36395090:('math-7-2','u6:g1','统计调查中的个体与观测量',1,['调查对象是学生的体重，总体是3000名学生的体重，样本是抽取的200名学生的体重。','个体是每名学生的体重，不是学生本人；样本容量是200。题目问错误项，选B。']),
}
raws={};locations={}
for path in sorted(root.glob('questions-*.json')):
 payload=json.loads(path.read_text())
 for q in payload['result'].get('items',[]):raws[q['id']]=q;locations[q['id']]=(path,payload)
sample=root/'sample-physics-motion.json'
for q in json.loads(sample.read_text())['items']:
 raws[q['id']]=q;locations[q['id']]=(sample,{'filters':{'subject_id':8,'grade_id':301,'edition_id':142,'chapter_id':181160},'chapter':{'name':'第1章 机械运动'}})
records=[];decisions=[]
for sid,q in raws.items():
 path,payload=locations[sid]
 rawhash=hashlib.sha256(json.dumps(q,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 if sid not in picks:
  if not q.get('answer'):reason='缺可直接核对的来源答案，暂不精选；不猜补。'
  elif q.get('has_images') or '<img' in str(q):reason='带公式/图示资源或解析含图片，需要单独核图，暂不精选。'
  else:reason='题型、表述或解析仍有疑点，暂不精选，保留原始材料供复查。'
  if sid==20749554:reason='来源标为单选却返回B|D，且参照物选项表述条件不充分。'
  if sid==5074875:reason='来源解析错误地称圆锥轴截面为直角三角形，不进入精选。'
  if sid==15883300:reason='缺少电压填空且把安全电压说成无条件安全，题干与适用条件不足。'
  decisions.append({'source_id':sid,'raw_sha256':rawhash,'decision':'exclude_from_curated','reason':reason});continue
 bid,goal,label,level,steps=picks[sid];subject,grade,term=bid.split('-');answer=clean(q['answer'])
 kind='multiple_choice' if '多选' in q['question_type'] else 'single_choice' if q['options'] else 'reference'
 if sid==22168633:answer='（1）5×10^(-5) m³；（2）1100 kg/m³。'
 if q['options']:answer=''.join(c for c in answer if c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
 options=[{'key':k,'text':clean(v)} for k,v in q['options'].items()]
 stem=clean(q['title'])
 record={'id':'tizhuang-curated:'+str(sid),'subject':subject,'stage':'junior','grade':int(grade),'term':int(term),'kind':kind,'status':'ready' if options else 'reference','stem':stem,'options':options,'answer':answer,'steps':steps,'difficulty':level,'difficulty_raw':q['difficulty'],'difficulty_basis':'项目按所需推理步骤标注，未沿用来源0—5量表；未经经验校准。','type_tags':[label],'knowledge_tags':[label],'tags_source':'ai','issues':[], 'curriculum_goal_ids':[bid+':'+goal],
 'provenance':{'dataset':'tizhuang-curated-20261015','source_id':str(sid),'source_url':'https://tizhuang.qcscience.cc','source_paper':q.get('source'),'source_content_hash':q.get('content_hash'),'raw_sha256':rawhash,'retrieved_at':'2026-10-15','teacher_reviewed':False,'curation_method':'codex_item_read_and_recompute'},
 'quality':{'curated':True,'curated_method':'codex_item_read_and_recompute','needs_teacher_review':True,'diagnostic_eligible':False,'source_filters':payload['filters']}}
 mode='choice' if options else 'numeric' if sid==26350566 else 'text'
 partdefs=[('p1','计算23−17−(−7)+(−16)。','−3',[steps[0]]),('p2','计算12−(−18)+(−7)−15。','8',[steps[1]])] if sid==26350566 else [('p1','计算物体体积。','5×10^(-5) m³',[steps[0]]),('p2','计算恰好悬浮时盐水密度。','1100 kg/m³',steps[1:])] if sid==22168633 else [('p1','按题目要求作答。',answer,steps)]
 record['annotation']=Annotation.model_validate({'response_format':kind if options else 'calculation' if sid in (26350566,22168633) else 'fill_blank','knowledge':{'primary':[label]},'fine_types':[label],'difficulty':{'level':level,'basis':record['difficulty_basis']},'curriculum':{'grade':int(grade),'term':int(term),'goal_ids':record['curriculum_goal_ids'],'scope_status':'candidate','basis':'根据章目录和题目内容逐题核对；AI标注，待教师确认。'},'answer_spec':{'mode':mode if len(partdefs)==1 else 'multipart','accepted_answers':[answer],'equivalence':'exact' if options else 'rubric','constraints':['仅为精选学习反馈；不计可信独立题量。']},'parts':[{'id':pid,'prompt':prompt,'reference_answer':ans,'solution_steps':st,'knowledge_tags':[label],'type_tags':[label],'rubric':[{'id':'r1','description':'核对符号、单位、关系与最终结论；接受等价解法。','evidence_required':'学生作答内容'}],'common_errors':[{'description':'忽略题目的限定条件、符号或单位。','knowledge_tags':[label]}]} for pid,prompt,ans,st in partdefs], 'grading':{'mode':'objective' if options else 'ai_rubric'},'review':{'status':'candidate','answer_status':'checked','method':'item_read','notes':'由Codex阅读与复算；与原来源答案一致，但不代表教师审核。'},'origin':{'model':'codex','batch_id':'web-curation-20261015'}}).model_dump()
 records.append(record);decisions.append({'source_id':sid,'raw_sha256':rawhash,'decision':'curated_candidate','question_id':record['id'],'book_id':bid,'goal_ids':record['curriculum_goal_ids'],'reason':'逐题阅读与复算；保留原始数据，teacher_reviewed=false。'})
Path('app/data/curated_web_20261015.json').write_text(json.dumps({'version':'20261015-1','source':'https://github.com/weishao2/tizhuang-agent-skills','records':records,'decisions':decisions},ensure_ascii=False,indent=2)+'\n')
print('raw',len(raws),'curated',len(records),'excluded',len(decisions)-len(records))
