"""Item-read circuit/energy questions transcribed from a public teacher edition."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.question_annotation import Annotation,source_fingerprint
from app.senior_bank import save_batch
URL='https://zy.21cnjy.com/25195674';TITLE='《学霸笔记 同步精讲》电源的电动势和内阻、闭合电路欧姆定律（教师版）';DATE='2026-10-15';BOOK='physics-senior-compulsory-3'
DATA=[
 {'slug':'battery-emf-internal-resistance','stem':'一电池外电路断开时的路端电压为3 V，接上8 Ω的负载电阻后路端电压降为2.4 V，则可以判定电池的电动势E和内电阻r为','options':[('A','E=2.4 V，r=1 Ω'),('B','E=3 V，r=2 Ω'),('C','E=2.4 V，r=2 Ω'),('D','E=3 V，r=1 Ω')],'answer':'B','kind':'single_choice','knowledge':'闭合电路欧姆定律与电动势内阻','fine':'利用开路电压和负载端电压求电源电动势及内阻','difficulty':2,'basis':'用开路状态得到电动势，再以带载电流和内电压列式求内阻。','parts':[('whole','B',['开路时电流为零，端电压等于电动势，因此E=3V。','接8Ω负载时I=U/R=2.4/8=0.30A，内电压E−U=0.60V。','r=(E−U)/I=0.60/0.30=2Ω，选B。'],['开路时E=3V并求带载电流','用内电压与电流之比求r=2Ω'],['把开路端电压误认为有内阻压降。','使用E而非负载端电压计算负载电流。'])]},
 {'slug':'terminal-voltage-internal-resistance','stem':'电动势为2 V的电源跟一个阻值R=9 Ω的电阻接成闭合电路，理想电压表测得电源两端电压为1.8 V，则电源的内阻为多少？','options':[],'answer':'1 Ω','kind':'short_answer','knowledge':'闭合电路欧姆定律与内电压','fine':'由负载电流和电源内电压求电源内阻','difficulty':1,'basis':'由负载电压求电流，再将电源内电压除以电流。','parts':[('whole','1 Ω',['理想电压表读出路端电压U=1.8V，负载电流I=U/R=1.8/9=0.20A。','电源内电压U内=E−U=2.0−1.8=0.20V。','r=U内/I=0.20/0.20=1Ω。'],['得到负载电流0.20A','由内电压0.20V求得r=1Ω'],['把端电压当成内电压。','误用总电动势除以负载电流。'])]},
 {'slug':'emf-external-internal-energy','stem':'将电动势为3 V的电源接入电路中，测得电源两极间的电压为2.4 V，当电路中有6 C的电荷流过时，分别求：(1)有多少其他形式的能转化为电能；(2)外电路中有多少电能转化为其他形式的能；(3)内电路中有多少电能转化为其他形式的能。','options':[],'answer':'(1)18 J；(2)14.4 J；(3)3.6 J','kind':'calculation','knowledge':'闭合电路能量转化与电动势','fine':'按电动势、端电压及电荷量计算电源、外电路、内电路能量','difficulty':2,'basis':'分别用电动势与端电压乘通过电荷量，并用能量守恒核验内耗。','parts':[('part1','18 J',['电源非静电力做功并转化的电能W源=Eq=3×6=18J。'],['写出W源=Eq并得18J'],['误用端电压代替电动势。']),('part2','14.4 J',['外电路能量转化W外=Uq=2.4×6=14.4J。'],['写出W外=Uq并得14.4J'],['把电源内压降用于外电路。']),('part3','3.6 J',['内电路电能转化W内=W源−W外=18−14.4=3.6J；也可由(E−U)q验证。'],['由能量守恒得3.6J并核验内电压'],['把内电路损耗加到外电路能量上。'])]},
 {'slug':'emf-lead-acid-battery','stem':'一组铅蓄电池的电动势为4.8 V、内阻不为零，以下说法正确的是（多选）','options':[('A','电路中每通过1 C电荷量，铅蓄电池能把4.8 J的化学能转变为电能'),('B','体积大的铅蓄电池比体积小的铅蓄电池的电动势大'),('C','电路中每通过1 C电荷量，铅蓄电池内部非静电力做功为4.8 J'),('D','该铅蓄电池把其他形式能转化为电能的本领比一节电动势为1.5 V的干电池强')],'answer':'ACD','kind':'multiple_choice','knowledge':'电动势定义与电源功能','fine':'由电动势解释单位电荷的能量转化并区分电动势与电池体积','difficulty':1,'basis':'结合W=Eq判断每库仑电荷的功及电动势所表征的电源转化本领。','parts':[('whole','ACD',['电动势E=W非/q，q=1C时W非=4.8J；电池将其他形式能转为电能，A、C成立。','电动势由电源自身性质决定，不由体积决定，B错误。','4.8V大于1.5V，表征该电池每单位电荷转化能量的本领更强，D成立。','答案为ACD。'],['依据W=Eq判断A、C','说明E与体积无关并判断D，选ACD'],['把电动势当作电源容量或体积的度量。','将非静电力做功与负载端获得能量混同。'])]}
]
def main():
 records=[];manifest=[];audit=[]
 for x in DATA:
  excerpt={'stem':x['stem'],'options':x['options'],'answer':x['answer'],'source_url':URL,'source_id':x['slug']}
  esha=hashlib.sha256(json.dumps(excerpt,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  qid='bank:web-21jy-'+x['slug'];opts=[{'key':k,'text':v} for k,v in x['options']]
  q={'id':qid,'subject':'physics','stage':'senior','grade':None,'term':None,'stem':x['stem'],'options':opts,'answer':x['answer'],'kind':x['kind'],'has_missing_assets':False,'steps':[],'provenance':{'dataset':'21世纪教育网公开教师版练习页','source_id':x['slug'],'source_file':URL,'download_revision':DATE,'file_sha256':esha,'url':URL,'license':'unknown; public page; redistribution terms not confirmed','page_title':TITLE,'captured_excerpt_sha256':esha},'curriculum_book_id':BOOK,'curriculum_goal_ids':[f'{BOOK}:u4:g2']}
  qsha=source_fingerprint(q); fmt=x['kind']; parts=[];ind=[]
  for pid,ans,steps,rub,errors in x['parts']:
   ind+=steps;parts.append({'id':pid,'prompt':x['stem'] if pid in ('whole','part1') else pid,'reference_answer':ans,'solution_steps':steps,'knowledge_tags':[x['knowledge']],'type_tags':[x['fine']],'depends_on':[],'points':None,'rubric':[{'id':f'{pid}-r{j+1}','description':r,'points':None,'evidence_required':r} for j,r in enumerate(rub)],'common_errors':[{'description':e,'knowledge_tags':[x['knowledge']],'type_tags':[x['fine']]} for e in errors]})
  accepted=[x['answer']] if fmt=='single_choice' else list(x['answer']) if fmt=='multiple_choice' else [x['answer']]
  ann={'schema_version':1,'response_format':fmt,'knowledge':{'primary':[x['knowledge']],'supporting':[],'prerequisites':[]},'fine_types':[x['fine']],'difficulty':{'level':x['difficulty'],'basis':x['basis'],'origin':'luna','calibrated':False},'curriculum':{'grade':None,'term':None,'book_id':BOOK,'goal_ids':q['curriculum_goal_ids'],'scope_status':'candidate','basis':'公开页面为教科版必修三电源电动势与闭合电路内容；按人教版同科课程主题对应compulsory-3 u4:g2映射。年级、学期及版次未推断。'},'answer_spec':{'mode':'choice' if fmt in ('single_choice','multiple_choice') else 'text','accepted_answers':accepted,'equivalence':'exact' if fmt in ('single_choice','multiple_choice') else 'semantic','constraints':['选择题按选项作答；计算题要求量纲及关系式成立。'],'unit':None,'tolerance':None},'parts':parts,'grading':{'mode':'objective' if fmt in ('single_choice','multiple_choice') else 'ai_rubric','full_score':None,'allow_alternative_methods':True,'uncertainty_policy':'review_required'},'review':{'status':'candidate','answer_status':'checked','issues':[],'method':'item_read','notes':'逐题读取公开教师版的题干、答案及解析并独立复算。Luna候选，不表示教师审核。'},'origin':{'model':'gpt-6-luna','batch_id':'senior-20261015-physics-web-comp3-1'}}
  Annotation.model_validate(ann)
  rationale='；'.join(ind)
  records.append({'question_id':qid,'source_sha256':qsha,'decision':'passed','quarantine_original':False,'question':q,'annotation':ann,'independent_solution':ind,'source_conflicts':[],'remaining_issues':[],'rationale':rationale})
  manifest.append({'path':URL+'#'+x['slug'],'revision':DATE,'sha256':esha,'license':'unknown; public page; redistribution terms not confirmed','source_url':URL})
  audit.append({'question_id':qid,'source_sha256':qsha,'decision':'passed','source_excerpt_sha256':esha,'source_url':URL,'independent_solution':ind,'rationale':rationale})
 batch={'batch_id':'senior-20261015-physics-web-comp3-1','source_manifest':manifest,'items':records}
 (ROOT/'app/data/senior_physics_web_comp3_1.json').write_text(json.dumps(batch,ensure_ascii=False,indent=2)+'\n')
 out=ROOT/'data/annotations/senior-20261015/physics-web-comp3-1-review.jsonl';out.parent.mkdir(parents=True,exist_ok=True);out.write_text('\n'.join(json.dumps(a,ensure_ascii=False) for a in audit)+'\n')
 target=ROOT/'app/data/senior_physics_luna.json';cur=json.loads(target.read_text());ids={r['question_id'] for r in records};cur['items']=[i for i in cur['items'] if i['question_id'] not in ids]+records;cur['source_manifest'] += [m for m in manifest if (m['path'],m['sha256']) not in {(a['path'],a['sha256']) for a in cur['source_manifest']}];cur['batch_id']='senior-20261015-physics-cumulative-9';save_batch(target,cur)
 print('wrote',len(records),'record(s); source excerpt hashes',[x['sha256'] for x in manifest])
if __name__=='__main__':main()
