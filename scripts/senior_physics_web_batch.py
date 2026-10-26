"""Item-read web additions transcribed from a public teacher edition, with URL and excerpt fingerprints."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.question_annotation import Annotation, source_fingerprint
from app.senior_bank import save_batch
URL='https://zy.21cnjy.com/25306220'
TITLE='《学霸笔记 同步精讲》第4章 电磁振荡与电磁波：同步练习+单元测评（教师版）'
RETRIEVED='2026-10-15'
BOOK='physics-senior-selective-2'
# Transcribed from page sections 11.1 Q1, 11.2 Q3, and 14.1 Q1; all selected items have full text options and source answer in the teacher edition.
DATA=[
 ('lc-current-energy-transfer', '关于LC振荡电路中的振荡电流，下列说法正确的是', [
  ('A','振荡电流最大时，电容器两极板间的电场强度最大'),('B','振荡电流为零时，线圈中自感电动势为零'),('C','振荡电流增大的过程中，线圈中的磁场能转化为电场能'),('D','振荡电流减小的过程中，线圈中的磁场能转化为电场能')], 'D', '电磁振荡中的能量转化与相位', '根据LC回路电流变化判断电场能、磁场能的转化', 2,
  '需要辨别电流大小变化与磁场能变化关系，并区分电流为零时电流变化率并不为零。',
  ['电流最大时磁场能最大，电容器电场能为零，A错。','电流过零处电流变化最快，线圈自感电动势幅值最大，B错。','电流增大时磁场能增大，电场能转化为磁场能，C错。','电流减小时磁场能减少，转化为电场能，D正确。'],
  ['混淆振荡电流与电容器电场强度的相位。','把电流为零误认为电流变化率也为零。']),
 ('lc-frequency-adjustment', '要想增大LC振荡电路中产生的振荡电流的频率，可采用的方法是', [
  ('A','增大电容器两极板的间距'),('B','升高电容器的充电电压'),('C','增加线圈的匝数'),('D','在线圈中插入铁芯')], 'A', 'LC回路固有频率与电容电感', '通过调节电容或电感改变LC振荡频率', 2,
  '使用f=1/(2π√LC)及平行板电容、线圈电感随结构变化的关系逐项判断。',
  ['增大板间距使平行板电容C减小，固有频率f增大，A正确。','充电电压改变振幅，不改变理想LC固有频率，B错。','增加线圈匝数使L增大，频率降低，C错。','插入铁芯增大L，频率降低，D错。'],
  ['把振荡幅度或充电电压当成频率决定因素。','误判增加电感会提高频率。']),
 ('em-spectrum-properties', '关于电磁波谱，下列说法正确的是（多选）', [
  ('A','波长不同的电磁波在本质上完全相同'),('B','电磁波的波长若差异太大则会出现本质不同的现象'),('C','电磁波谱的频带很宽'),('D','电磁波的波长很短，所以电磁波谱的频带很窄')], 'AC', '电磁波谱与电磁波共同性质', '辨析电磁波谱波长差异及共同本质', 1,
  '区分电磁波的共同本质与不同波长引起的性质差异，并识别谱段范围。',
  ['不同波长的电磁波本质上都是电磁波，A正确；波长差异会使与物质作用、传播等表现不同，但不改变其本质，B错误。','电磁波谱从无线电波延伸至伽马射线，频带范围很宽，C正确。','电磁波并非都波长很短，且频带并不窄，D错误。','正确项为A、C。'],
  ['把波长差异造成的现象差异误作本质不同。','把“电磁波”局限理解为可见光。'])
]
def main():
 rows=[]; records=[]; manifest=[]
 for slug,stem,pairs,answer,knowledge,fine,level,basis,steps,errors in DATA:
  payload={'stem':stem,'options':pairs,'answer':answer,'source_url':URL,'section':slug}
  excerpt_sha=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  qid='bank:web-21jy-'+slug
  opts=[{'key':k,'text':v} for k,v in pairs]
  q={'id':qid,'subject':'physics','stage':'senior','grade':None,'term':None,'stem':stem,'options':opts,'answer':answer,'kind':'multiple_choice' if len(answer)>1 else 'single_choice','has_missing_assets':False,'steps':[],'provenance':{'dataset':'21世纪教育网公开教师版练习页','source_id':slug,'source_file':URL,'download_revision':RETRIEVED,'file_sha256':excerpt_sha,'url':URL,'license':'unknown; public page; redistribution terms not confirmed','page_title':TITLE,'captured_excerpt_sha256':excerpt_sha},'curriculum_book_id':BOOK,'curriculum_goal_ids':[f'{BOOK}:u4:g2']}
  qhash=source_fingerprint(q)
  fmt='multiple_choice' if len(answer)>1 else 'single_choice'
  ann={'schema_version':1,'response_format':fmt,'knowledge':{'primary':[knowledge],'supporting':[],'prerequisites':[]},'fine_types':[fine],'difficulty':{'level':level,'basis':basis,'origin':'luna','calibrated':False},'curriculum':{'grade':None,'term':None,'book_id':BOOK,'goal_ids':q['curriculum_goal_ids'],'scope_status':'candidate','basis':'来源页面标注为人教版高中物理选择性必修第二册第四章；映射本册u4:g2；不推断年级、学期或教材版次。'},'answer_spec':{'mode':'choice','accepted_answers':[answer] if fmt=='single_choice' else list(answer),'equivalence':'exact','constraints':['按选项作答；多选题答案为全部正确选项。'],'unit':None,'tolerance':None},'parts':[{'id':'whole','prompt':stem,'reference_answer':answer,'solution_steps':steps,'knowledge_tags':[knowledge],'type_tags':[fine],'depends_on':[],'points':None,'rubric':[{'id':'correct_answer_and_reasoning','description':f'选{answer}；'+'；'.join(steps),'points':None,'evidence_required':'所选项与LC关系、能量变化或电磁波谱性质一致。'}],'common_errors':[{'description':e,'knowledge_tags':[knowledge],'type_tags':[fine]} for e in errors]}],'grading':{'mode':'objective','full_score':None,'allow_alternative_methods':True,'uncertainty_policy':'review_required'},'review':{'status':'candidate','answer_status':'checked','issues':[],'method':'item_read','notes':'逐题读取公开教师版的题干、选项和答案解析，并独立依据高中物理关系复核。Luna候选，不代表教师审核。'},'origin':{'model':'gpt-6-luna','batch_id':'senior-20261015-physics-web-1'}}
  Annotation.model_validate(ann)
  rec={'question_id':qid,'source_sha256':qhash,'decision':'passed','quarantine_original':False,'question':q,'annotation':ann,'independent_solution':steps,'source_conflicts':[],'remaining_issues':[],'rationale':'；'.join(steps)}
  records.append(rec); rows.append({'question_id':qid,'source_sha256':qhash,'decision':'passed','source_excerpt_sha256':excerpt_sha,'source_url':URL,'independent_solution':steps,'rationale':rec['rationale']})
  manifest.append({'path':URL+'#'+slug,'revision':RETRIEVED,'sha256':excerpt_sha,'license':'unknown; public page; redistribution terms not confirmed','source_url':URL})
 batch={'batch_id':'senior-20261015-physics-web-1','source_manifest':manifest,'items':records}
 (ROOT/'app/data/senior_physics_web_1.json').write_text(json.dumps(batch,ensure_ascii=False,indent=2)+'\n')
 out=ROOT/'data/annotations/senior-20261015/physics-web-1-review.jsonl';out.parent.mkdir(parents=True,exist_ok=True);out.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n')
 target=ROOT/'app/data/senior_physics_luna.json'; cur=json.loads(target.read_text()); ids={r['question_id'] for r in records}; cur['items']=[i for i in cur['items'] if i['question_id'] not in ids]+records; cur['source_manifest'] += [m for m in manifest if (m['path'],m['sha256']) not in {(a['path'],a['sha256']) for a in cur['source_manifest']}]; cur['batch_id']='senior-20261015-physics-cumulative-8';save_batch(target,cur)
 print('wrote web batch',len(records),'records; excerpt sha256 values:',[x['sha256'] for x in manifest])
if __name__=='__main__':main()
