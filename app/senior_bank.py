"""Replayable senior selections: preserve source snapshots and model review evidence.

Only item-read, answer-checked selections can enter practice. Model review never
sets teacher_reviewed or certifies an independent diagnostic score.
"""
import copy
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path

from app import bank
from app.question_annotation import Annotation, source_fingerprint, validate_for_question

VERSION = 'senior-luna-20261015'
DATA = Path(__file__).parent / 'data'
BASE_RELEASE_FILES = {'senior_math_luna.json', 'senior_physics_luna.json',
    'senior_peer_review.json', 'senior_curriculum.json', 'senior_source_manifests.json'}
FOUNDATION_RELEASE_FILES = {'senior_math_foundations.json', 'senior_physics_foundations.json',
    'senior_math_foundation_skills.json', 'senior_physics_foundation_skills.json',
    'senior_foundations_peer_review.json'}


def batch_files(include_foundations=False):
    pairs = [(f'senior_{s}_luna.json', 'senior_peer_review.json') for s in ('math', 'physics')]
    if include_foundations:
        pairs += [(f'senior_{s}_foundations.json', 'senior_foundations_peer_review.json')
                  for s in ('math', 'physics')]
    return pairs


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()


def contains_controls(value):
    if isinstance(value, str):
        return bool(re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', value))
    if isinstance(value, dict):
        return any(contains_controls(v) for v in value.values())
    if isinstance(value, list):
        return any(contains_controls(v) for v in value)
    return False


def prepare_batch(value):
    """Validate the entire batch before any writes; fail closed on stale sources."""
    from app.course_catalog import GOALS
    if not isinstance(value.get('batch_id'), str) or not value['batch_id'].strip():
        raise ValueError('高中复核批次必须有稳定标识')
    items = value.get('items')
    if not isinstance(items, list) or not items:
        raise ValueError('高中复核批次不能为空')
    seen, records, decisions = set(), [], []
    for item in items:
        q = copy.deepcopy(item['question'])
        qid = item['question_id']
        if qid != q.get('id') or qid in seen:
            raise ValueError('来源题号重复或与快照不符')
        seen.add(qid)
        if q.get('stage') != 'senior' or q.get('subject') not in {'math', 'physics'}:
            raise ValueError('高中复核仅接收高中数学、物理')
        if source_fingerprint(q) != item.get('source_sha256'):
            raise ValueError('来源指纹不符，禁止套用陈旧标注')
        if not q.get('provenance', {}).get('url') or not q['provenance'].get('source_id'):
            raise ValueError('必须保留题目来源')
        decision = item.get('decision')
        if decision not in {'passed', 'pending', 'excluded'}:
            raise ValueError('未知复核结论')
        if not isinstance(item.get('rationale'), str) or not item['rationale'].strip():
            raise ValueError('每题必须保存复核理由')
        annotation = item.get('annotation')
        if annotation:
            q['curriculum_book_id'] = annotation.get('curriculum', {}).get('book_id')
            a = validate_for_question(annotation, q)
            if a.review.method == 'teacher' or a.review.status == 'reviewed':
                raise ValueError('Luna审核不能冒充教师审核')
            if a.origin.model != 'gpt-6-luna':
                raise ValueError('本批须保留真实Luna标注来源')
            q['annotation'] = a.model_dump()
        elif decision == 'passed':
            raise ValueError('可练题必须具有完整标注')
        goals = (q.get('annotation') or {}).get('curriculum', {}).get('goal_ids', [])
        if decision == 'passed':
            a = Annotation.model_validate(q['annotation'])
            if contains_controls([q, a.model_dump()]):
                raise ValueError('题目或标注含公式转义损坏的控制字符')
            if re.search(r'【(?:答案|解析|详解)】|(?:参考答案|正确答案)\s*[:：]', q.get('stem', '')):
                raise ValueError('题干可能混入答案或解析，需隔离核对')
            if a.review.method != 'item_read' or a.review.answer_status != 'checked':
                raise ValueError('可练题必须实际逐题阅读并核对答案')
            if not item.get('independent_solution') or item.get('source_conflicts') or item.get('remaining_issues'):
                raise ValueError('未复算或仍有冲突的题必须隔离')
            if q.get('has_missing_assets') or not q.get('stem') or not q.get('answer'):
                raise ValueError('缺图、缺题干或缺答案不能进入练习')
            if not a.knowledge.primary or not a.fine_types or not a.parts:
                raise ValueError('需有知识点、细题型和小问')
            if any(not p.reference_answer or not p.solution_steps or not p.rubric for p in a.parts):
                raise ValueError('每小问必须有答案、步骤和评分依据')
            if not goals or any(g not in GOALS or GOALS[g]['subject'] != q['subject']
                    or '-senior-' not in GOALS[g]['book_id'] for g in goals):
                raise ValueError('可练题必须对齐同科高中课程目标')
            if q['kind'] in {'single_choice', 'multiple_choice'}:
                # Variable case is semantic: Q/q, R/r and P/p may differ.
                texts = [''.join(unicodedata.normalize('NFKC',o['text']).split()) for o in q['options']]
                keys = [o['key'] for o in q['options']]
                if len(keys)<2 or len(set(keys))!=len(keys) or len(set(texts))!=len(texts) or not all(texts):
                    raise ValueError('选项重复或不完整')
                expected = bank.canonical_choice(q['answer'], q)
                if set(expected) != set(q['answer']):
                    raise ValueError('选择题答案不合法')
                q['status'] = 'ready'
                q['answer'] = expected
            else:
                q['status'] = 'reference'
                q['answer'] = '\n'.join(f"（{n}）{p.reference_answer}"
                    for n,p in enumerate(a.parts,1))
            q['knowledge_tags'] = list(dict.fromkeys([*a.knowledge.primary, *a.knowledge.supporting]))
            q['type_tags'] = a.fine_types
            q['difficulty'], q['difficulty_basis'] = a.difficulty.level, a.difficulty.basis
            q['steps'] = [step for part in a.parts for step in part.solution_steps]
        else:
            q['status'] = 'quarantine'
            # Incomplete source rows remain inspectable, but never become a
            # runnable exercise merely because storage needs these fields.
            for key,default in {'kind':'reference','stem':'','answer':'','options':[],
                    'steps':[],'knowledge_tags':[],'type_tags':[],'grade':None,'term':None,
                    'difficulty':2,'difficulty_raw':None,
                    'difficulty_basis':'来源难度未知；隔离题的维护默认值，未经校准。'}.items():
                q.setdefault(key,default)
        q['curriculum_goal_ids'] = goals
        q['annotation_source_question_id'] = qid
        q['annotation_source_sha256'] = item['source_sha256']
        review = {'status': decision, 'model': 'gpt-6-luna', 'batch_id': value['batch_id'],
            'source_sha256': item['source_sha256'], 'rationale': item['rationale'],
            'independent_solution': item.get('independent_solution'),
            'source_conflicts': item.get('source_conflicts', []),
            'remaining_issues': item.get('remaining_issues', []),
            'annotation_sha256': digest(q.get('annotation'))}
        if 'foundation_skill_ids' in item:
            skills = item['foundation_skill_ids']
            if (not isinstance(skills, list) or not skills or
                    any(not isinstance(s, str) or not s.strip() for s in skills)
                    or len(skills) != len(set(skills))):
                raise ValueError('基础题必须关联非空、不同的细技能标识')
            q['foundation_skill_ids'] = skills
            review['foundation_skill_ids'] = skills
        q['quality'] = {**q.get('quality', {}), 'version': VERSION,
            'model_review': review, 'source_snapshot': copy.deepcopy(item['question'])}
        q['provenance'] = {**q['provenance'], 'teacher_reviewed': False}
        q['tags_source'] = 'luna'
        # Source and annotation are both immutable; revised reviews get new IDs.
        q['id'] = 'bank:senior:' + digest([qid, item['source_sha256'], review])[:32]
        q['has_missing_assets'] = bool(q.get('has_missing_assets'))
        if decision != 'passed':
            q['issues'] = list(dict.fromkeys([*q.get('issues', []), 'senior_review_' + decision]))
        records.append(q)
        decisions.append({'source_id': qid, 'question_id': q['id'], 'decision': decision})
    return records, decisions


def import_batch(db, value, *, transaction=True):
    records, decisions = prepare_batch(value)
    source = 'senior-luna-' + digest(value['batch_id'])[:16]
    return bank.import_records(db, source, records, {'version': VERSION,
        'batch_id': value['batch_id'], 'source_manifest': value.get('source_manifest', []),
        'review_method': 'luna_item_read_not_teacher', 'decisions': decisions}, transaction=transaction)


def validate_peer(value, peer):
    """An old second-pass decision cannot bless a changed annotation or source."""
    indexed = {}
    for item in peer.get('items', []):
        if item['question_id'] in indexed:
            raise ValueError('独立复核台账题号重复')
        indexed[item['question_id']] = item
    for item in value['items']:
        if item['decision'] != 'passed':
            continue
        p = indexed.get(item['question_id'], {})
        expected = digest(Annotation.model_validate(item['annotation']).model_dump())
        if (p.get('decision') != 'passed' or p.get('source_sha256') != item['source_sha256']
                or p.get('annotation_sha256') != expected or not p.get('independent_solution')
                or not p.get('reason')):
            raise ValueError('缺少与当前题目和标注一致的独立复核：'+item['question_id'])


def save_batch(path, value):
    """Validate before replacing a cumulative ledger read by another reviewer."""
    prepare_batch(value)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                prefix=path.name+'.',suffix='.tmp',delete=False) as stream:
            temp=Path(stream.name)
            json.dump(value,stream,ensure_ascii=False,indent=2)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        if temp and temp.exists():temp.unlink()


def seed(db):
    release_path=DATA/'senior_release.json'
    if not release_path.exists():
        return []
    release=json.loads(release_path.read_text())
    if release.get('ready_for_import') is not True:
        return []
    version = release.get('schema_version')
    required = BASE_RELEASE_FILES | (FOUNDATION_RELEASE_FILES if version == 2 else set())
    if version not in {1,2} or set(release.get('files',{}))!=required:
        raise ValueError('高中题库发布清单不完整')
    for name,expected in release['files'].items():
        if hashlib.sha256((DATA/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('高中已审核题库文件发生变化，需要重新复核发布：'+name)
    prepared = []
    for filename, peerfile in batch_files(version == 2):
        value = json.loads((DATA / filename).read_text())
        peer = json.loads((DATA / peerfile).read_text())
        validate_peer(value, peer)
        records, decisions = prepare_batch(value)
        prepared.append((value, records, decisions))
    if version == 2:
        from app.senior_foundations import audit_foundations
        report = audit_foundations(DATA)
        if not report['complete']:
            raise ValueError('基础题技能覆盖未通过：' + '; '.join(report['errors'][:5]))
    results = []
    for value, records, decisions in prepared:
        source = 'senior-luna-' + digest(value['batch_id'])[:16]
        # A previously retired question must not be resurrected by startup.
        existing = {r[0] for r in db.execute('SELECT id FROM bank_questions WHERE source_id=?', (source,))}
        records = [q for q in records if q['id'] not in existing]
        if records:
            results.append(bank.import_records(db, source, records, {'version': VERSION,
                'batch_id': value['batch_id'], 'source_manifest': value.get('source_manifest', []),
                'review_method': 'luna_item_read_not_teacher', 'decisions': decisions}, transaction=False))
    return results


def types_for_book(db, bid):
    """Expose known fine types as unassessed, never as trusted classifications."""
    from app.course_catalog import GOALS
    rows = db.execute("""SELECT DISTINCT t.id,t.label,cl.goal_id FROM bank_taxonomy t
        JOIN bank_question_tags qt ON qt.tag_id=t.id
        JOIN bank_questions q ON q.id=qt.question_id
        JOIN course_question_links cl ON cl.question_id=q.id
        WHERE t.stage='senior' AND t.kind='type' AND q.stage='senior'
        AND q.status IN ('ready','reference') AND json_extract(q.data,'$.can_practice')=1
        AND json_extract(q.data,'$.curriculum_book_id')=? ORDER BY cl.goal_id,t.id""", (bid,))
    items = {}
    for r in rows:
        g = GOALS.get(r['goal_id'])
        if not g or g['book_id'] != bid:
            continue
        items.setdefault(r['id'], {'id':r['id'],'name':r['label'],'unit_id':g['unit_id'],
            'goal_id':g['id'],'can_do':g['can_do'],'classification_reviewed':False})
    return list(items.values())
