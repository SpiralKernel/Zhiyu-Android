"""Seven item-read gap fills from pinned CMMLU and a public projectile item."""
from __future__ import annotations
import csv, copy, hashlib, json, sys, unicodedata
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.question_annotation import Annotation, source_fingerprint
from app.senior_bank import save_batch

REV='d6e7b716d8ac694f38969a6c0407437d1fded799'
CMMLU=ROOT/'data/sources/cmmlu-senior/data'
DEV='b0b6cf2222e11c18ca40f95606d75617092671ccb55cd34851137c111922eef2'
TEST='c21a1c6725d2933f0ebd52e1b300a9bb7d49e37097fbe58ad8c256da82bf5b91'

# source-file, row index, book, unit, goal, fine type, answer, steps, rubric, errors, level, basis
DETAIL={
 ('dev',2):('physics-senior-compulsory-1',1,1,'打点计时器纸带直接测得的位移','A',
  ['纸带上的相邻计数点位置可由刻度尺直接测量，位置差即该段位移。','平均速度还需除以计时器给出的时间间隔；瞬时速度和加速度还需由多段数据估算，故选A。'],
  ['指出纸带点迹间距可直接给出位移。','区分需计算得到的速度与加速度，选A。'],
  ['把纸带上的点迹直接当作瞬时速度或加速度。','忽略位移测量需要标尺。'],1,'区分直接测量量与由纸带数据计算的运动学量。'),
 ('test',46):('physics-senior-selective-3',3,2,'热力学第一定律与热机做功冲程','B',
  ['汽油机做功冲程中，高温高压燃气膨胀并对活塞做功，内能转化为机械能。','水沸腾时蒸汽膨胀冲开壶盖，同样由气体内能转化为机械功；故选B。','其余选项分别是摩擦生热、外界压缩气体和摩擦生热，能量转换方向不同。'],
  ['指出做功冲程是燃气膨胀对外做功。','对应蒸汽膨胀做功，选B。'],
  ['把压缩气体点火误认为做功冲程。','只注意物体运动而不判断能量转化方向。'],1,'将热机冲程的能量转化与具体气体膨胀做功情景对应。'),
 ('test',65):('physics-senior-selective-1',2,1,'单摆周期和振幅与初速度的关系','C',
  ['两单摆摆长相同且均作小角度振动，因此f=1/(2π)√(g/L)，f₁=f₂。','平衡位置初速度是最大速度，vmax=2πfA；频率相同且V₁>V₂，故A₁>A₂。','答案为C。'],
  ['依据摆长相同判断频率相同。','应用vmax=2πfA比较振幅，选C。'],
  ['把初速度大小当作决定单摆频率的因素。','忘记频率相同后振幅与最大速度成正比。'],1,'同一模型下由周期公式和最大速度关系比较频率与振幅。'),
 ('test',77):('physics-senior-selective-1',4,2,'波的衍射与波长尺度','A',
  ['声波绕过建筑物传播表明发生衍射；明显衍射通常要求障碍物或孔的尺度与波长相近，或波长更大。','声波波长远长于可见光波长，建筑物尺度相对声波波长较小，而相对光波波长极大，所以声波容易绕射、光波不明显，选A。'],
  ['指出该现象是衍射并说明衍射尺度条件。','比较声波和光波波长后选A。'],
  ['把差异归因于声波是纵波、光波是横波。','误认为传播速度大小决定绕射强弱。'],1,'应用衍射条件比较声波与光波在同一宏观障碍物附近的传播。'),
}

# Public, text-only question. Captured full title/options/answer from the cited page's indexed text.
PROJECTILE={
 'id':'bank:web-1010jiajiao-horizontal-projectile-freefall',
 'stem':'在同一高度有两个小球同时开始运动，一个水平抛出，另一个自由落下。在它们运动过程中的每一时刻，有（ ）',
 'options':[('A','加速度不同，速度相同'),('B','加速度相同，速度不同'),('C','下落高度相同，位移不同'),('D','下落高度不同，位移相同')],
 'answer':'B','book':'physics-senior-compulsory-2','unit':1,'goal':1,
 'knowledge':'平抛运动的分解与自由落体','fine':'比较水平抛出和自由落体的加速度、速度及位移',
 'steps':['忽略空气阻力时，两球均只受重力，加速度都为竖直向下的g。','同一时刻两球竖直速度相同，但水平抛出的小球另有非零水平速度，故两球速度矢量不同。','二者竖直下落高度相同，但水平抛出球还有水平位移，故总位移不同；选B。'],
 'rubric':['指出两者加速度均为g且方向相同。','指出平抛球有非零水平速度，因此速度不同，选B。'],
 'errors':['把加速度相同误认为速度相同。','把竖直下落高度等同于总位移大小。'],
 'basis':'逐时刻比较分运动：竖直分运动相同，平抛球另有水平分速度。',
 'url':'https://www.1010jiajiao.com/gzwl/shiti_id_e273f0f49f9e10c8990998a877ac835c',
}

def clean(s):
 return unicodedata.normalize('NFKC',str(s)).replace('\u3000',' ').strip()

def make_item(qid,stem,opts,answer,book,unit,goal,knowledge,fine,steps,rubric,errors,level,basis,provenance):
 q={'id':qid,'subject':'physics','stage':'senior','grade':None,'term':None,'stem':stem,
    'options':[{'key':k,'text':v} for k,v in opts],'answer':answer,'kind':'single_choice',
    'has_missing_assets':False,'steps':[], 'provenance':provenance,
    'curriculum_book_id':book,'curriculum_goal_ids':[f'{book}:u{unit}:g{goal}']}
 sh=source_fingerprint(q)
 part={'id':'p1','prompt':'判断正确选项。','reference_answer':answer,
       'solution_steps':steps,'knowledge_tags':[knowledge],'type_tags':[fine],
       'depends_on':[],'points':None,
       'rubric':[{'id':f'c{i+1}','description':r,'points':None,'evidence_required':r} for i,r in enumerate(rubric)],
       'common_errors':[{'description':e,'knowledge_tags':[knowledge],'type_tags':[fine]} for e in errors]}
 ann={'schema_version':1,'response_format':'single_choice','knowledge':{'primary':[knowledge],'supporting':[],'prerequisites':[]},
      'fine_types':[fine],'difficulty':{'level':level,'basis':basis,'origin':'luna','calibrated':False},
      'curriculum':{'grade':None,'term':None,'book_id':book,'goal_ids':q['curriculum_goal_ids'],'scope_status':'candidate','basis':'按题目直接考查的教材章节概念映射；不推断年级、学期或教师审核。'},
      'answer_spec':{'mode':'choice','accepted_answers':[answer],'equivalence':'exact','constraints':['按选项作答。'],'unit':None,'tolerance':None},
      'parts':[part],'grading':{'mode':'objective','full_score':None,'allow_alternative_methods':True,'uncertainty_policy':'review_required'},
      'review':{'status':'candidate','answer_status':'checked','issues':[],'method':'item_read','notes':'逐题阅读题干和选项，并独立复算或依据物理规律核对；候选标注不代表教师审核。'},
      'origin':{'model':'gpt-6-luna','batch_id':'senior-20261016-physics-gap-1'}}
 Annotation.model_validate(ann)
 return {'question_id':qid,'source_sha256':sh,'decision':'passed','quarantine_original':False,'question':q,'annotation':ann,
         'independent_solution':steps,'source_conflicts':[],'remaining_issues':[],
         'rationale':'逐项核查题干条件及四个选项；独立推导为：'+' '.join(steps)}

def main():
 rows={}
 for split in ('dev','test'):
  p=CMMLU/split/'high_school_physics.csv'
  with p.open(encoding='utf-8-sig',newline='') as f: rows[split]=list(csv.DictReader(f))
 items=[]; hashes={'dev':DEV,'test':TEST}
 for (split,i),(book,unit,goal,fine,answer,steps,rubric,errors,level,basis) in DETAIL.items():
  r=rows[split][i]; opts=[(k,clean(r[k])) for k in 'ABCD']
  stem=clean(r['Question']); qid=f'bank:cmmlu-senior-physics:{split}:{i}'
  if clean(r['Answer'])!=answer: raise ValueError(f'CMMLU answer mismatch {qid}: {r["Answer"]}')
  prov={'dataset':'CMMLU high_school_physics','source_id':qid,'source_file':f'data/{split}/high_school_physics.csv',
        'download_revision':REV,'file_sha256':hashes[split],
        'url':f'https://raw.githubusercontent.com/haonan-li/CMMLU/{REV}/data/{split}/high_school_physics.csv',
        'license':'CC-BY-NC-SA-4.0'}
  items.append(make_item(qid,stem,opts,answer,book,unit,goal,
    {'dev':{0:'位移与路程'} }.get(split,{}).get(i, fine),fine,steps,rubric,errors,level,basis,prov))
 p=PROJECTILE
 capture='在同一高度有两个小球同时开始运动，一个水平抛出，另一个自由落下。在它们运动过程中的每一时刻，有（ ）|A 加速度不同，速度相同|B 加速度相同，速度不同|C 下落高度相同，位移不同|D 下落高度不同，位移相同|答案 B'
 prov={'dataset':'1010jiajiao indexed question page','source_id':p['id'],'source_file':'web-capture:search-result-full-text',
       'download_revision':'2026-10-16','file_sha256':hashlib.sha256(capture.encode()).hexdigest(),
       'url':p['url'],'license':'unknown; public page; redistribution terms not confirmed'}
 items.append(make_item(p['id'],p['stem'],p['options'],p['answer'],p['book'],p['unit'],p['goal'],p['knowledge'],p['fine'],p['steps'],p['rubric'],p['errors'],1,p['basis'],prov))
 # Text-only circular-motion question, with no diagram-dependent quantities.
 circ={'id':'bank:web-ixuehai-circular-disk-friction-q9',
  'stem':'小物体P放在水平圆盘上随圆盘一起转动，下列关于小物体所受摩擦力f的叙述正确的是（ ）',
  'options':[('A','当圆盘匀速转动时，摩擦力f的大小跟物体P到轴O的距离成正比'),('B','圆盘转动时，摩擦力f方向总是指向轴O'),('C','圆盘匀速转动时，小物体受重力、支持力、摩擦力和向心力作用'),('D','当物体P到轴O距离一定时，摩擦力f的大小跟圆盘转动的角速度成正比')]}
 csteps=['圆盘匀速转动时角速度ω恒定，P随盘做半径r的匀速圆周运动。','水平面内静摩擦力提供向心力，f=mω²r，因此在m、ω相同条件下f与r成正比，A正确。','圆盘变速转动时摩擦力还需提供切向分力，方向不总指向轴；向心力是合力效果而非额外性质力；r固定时f与ω²成正比而非ω，B、C、D错误。']
 cp='匀速转盘上静摩擦力提供向心力，f=mω²r；逐项核验得到A。'
 cprov={'dataset':'ixuehai.cn high-school physics question','source_id':circ['id'],'source_file':'https://www.ixuehai.cn/html/3757.html#question-9',
  'download_revision':'2026-10-16','file_sha256':hashlib.sha256(('question9:'+circ['stem']+'|'+ '|'.join(v for _,v in circ['options'])+'|A').encode()).hexdigest(),
  'url':'https://www.ixuehai.cn/html/3757.html','license':'unknown; public page; redistribution terms not confirmed'}
 items.append(make_item(circ['id'],circ['stem'],circ['options'],'A','physics-senior-compulsory-2',2,2,'圆周运动向心力与静摩擦力','水平匀速转盘中静摩擦力的大小和方向',csteps,
  ['从匀速圆周运动列出f=mω²r并得A。','指出变速转动时摩擦力可有切向分量，向心力不是独立性质力，且固定半径时f∝ω²。'],
  ['将向心力当作与摩擦力并列的另一种力。','把f正比于ω²误认为正比于ω。'],2,'需区分合力效果、实际摩擦力方向及其对角速度的平方关系。',cprov))
 manifest=[{'path':f'data/{split}/high_school_physics.csv','sha256':hashes[split],'revision':REV} for split in ('dev','test')]
 manifest.append({'path':'web-capture:1010jiajiao-horizontal-projectile','sha256':prov['file_sha256'],'revision':'2026-10-16'})
 batch={'batch_id':'senior-20261016-physics-gap-1','source_manifest':manifest,'items':items}
 out=ROOT/'app/data/senior_physics_cmmlu_gap_1.json';out.write_text(json.dumps(batch,ensure_ascii=False,indent=2)+'\n')
 audit=ROOT/'data/annotations/senior-20261015/physics-cmmlu-gap-1-review.jsonl';audit.parent.mkdir(parents=True,exist_ok=True)
 audit.write_text('\n'.join(json.dumps({'question_id':x['question_id'],'source_sha256':x['source_sha256'],'decision':x['decision'],'rationale':x['rationale'],'independent_solution':x['independent_solution']},ensure_ascii=False) for x in items)+'\n')
 target=ROOT/'app/data/senior_physics_luna.json';cur=json.loads(target.read_text());ids={x['question_id'] for x in items}
 # Remove this script's previous duplicate-content attempt; the corresponding
 # legacy normalized records remain the single authoritative entries.
 ids.update({f'bank:cmmlu-senior-physics:{s}:{i}' for s,i in [('dev',0),('test',27),('test',30),('test',85),('test',1),('test',42),('test',36),('test',89),('test',15)]})
 cur['items']=[x for x in cur['items'] if x['question_id'] not in ids]+items
 known={(x.get('path'),x.get('sha256')) for x in cur.get('source_manifest',[])}
 cur.setdefault('source_manifest',[]).extend(x for x in manifest if (x.get('path'),x.get('sha256')) not in known)
 cur['batch_id']='senior-20261016-physics-cumulative-gap-1';save_batch(target,cur)
 print('added',len(items),[(x['question_id'],x['source_sha256']) for x in items])
if __name__=='__main__': main()
