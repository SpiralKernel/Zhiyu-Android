"""Atomically install complete, source-pinned AI physics reviews as candidates.

Model review never creates a teacher identity, certification or a numeric score.
Unresolved disagreements remain quarantined; source question text stays intact.
"""
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from fastapi import HTTPException

from app import bank
from app.db import audit, dumps, now
from app.physics_full_review import Adjudication, Finding, PeerFinding, inspect_batch
from app.physics_review import snapshot_hash
from app.question_annotation import Annotation, source_fingerprint, validate_for_question

BATCH_SIZE = 128


def load_bundle(directory):
    """Require two complete rounds and pin the exact bytes subsequently consumed."""
    directory = Path(directory)
    report = inspect_batch(directory)
    if not report['all_reviews_complete']:
        raise ValueError(f'全量初审与复核尚未完成：{report["primary_done"]}/{report["total"]} 初审，'
                         f'{report["peer_done"]}/{report["total"]} 复核')
    if report['model'] != 'gpt-6-luna':
        raise ValueError('本批必须使用明确授权的 Luna 审核记录')
    sources, primary, peers = {}, {}, {}
    for shard in report['shards']:
        for prefix, target, model in (('input', sources, None), ('primary', primary, Finding), ('peer', peers, PeerFinding)):
            name = f'{prefix}-{shard["shard"]}.jsonl'
            raw = (directory / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != report['file_sha256'][name]:
                raise ValueError('审核文件在校验后发生变化：' + name)
            for line in raw.decode('utf-8').splitlines():
                value = model.model_validate_json(line) if model else json.loads(line)
                target[value.question_id if model else value['question_id']] = value
    adjudications = {}
    if 'adjudications.jsonl' in report['file_sha256']:
        raw = (directory / 'adjudications.jsonl').read_bytes()
        if hashlib.sha256(raw).hexdigest() != report['file_sha256']['adjudications.jsonl']:
            raise ValueError('裁定文件在校验后发生变化')
        for line in raw.decode('utf-8').splitlines():
            item = Adjudication.model_validate_json(line)
            adjudications[item.question_id] = item
    return report, sources, primary, peers, adjudications


def resolve(primary, peer):
    """Agreement can mean exclusion. A disagreement is held, never promoted."""
    if peer.decision == 'accept':
        return primary.decision, primary.reason
    proposed = peer.correction.decision if peer.correction else peer.decision
    if proposed == primary.decision and proposed != 'pass':
        return proposed, primary.reason + '；复核：' + peer.reason
    return 'unresolved', '初审与独立复核有分歧，暂不开放：' + primary.reason + '；复核：' + peer.reason


def annotation_for(finding, question, batch_id):
    """No guessed curriculum, points, tolerance, dependencies or human approval."""
    choice = question['kind'] in {'single_choice', 'multiple_choice'}
    if choice:
        try:
            source_answer = bank.canonical_choice(str(question['answer']), question)
            if bank.canonical_choice(finding.answer, question) != source_answer:
                raise ValueError('独立答案与来源选项答案不符')
            if len(finding.parts) != 1 or bank.canonical_choice(finding.parts[0].answer, question) != source_answer:
                raise ValueError('选择题的小问答案与整题答案不符')
        except HTTPException as exc:
            raise ValueError('选择题答案必须为题目已有选项字母') from exc
    if finding.remaining_issues:
        raise ValueError('通过记录仍有未解决问题：' + '；'.join(finding.remaining_issues))
    if not question.get('stem', '').strip() or not str(question.get('answer', '')).strip():
        raise ValueError('题干或来源答案为空')
    placeholders = {
        '见解析', '详见解析', '略', '见解答', '详见解答', '见详解', '详见详解',
        '答案见解析', '参见解析', '见解题过程', '见图', '见图示',
    }
    if any(re.sub(r'[\s。．.!！:：]', '', line) in placeholders for line in str(question['answer']).splitlines()):
        raise ValueError('来源答案栏仅有占位文字，须先建立修订草稿')
    if question.get('status') == 'quarantine' or question.get('has_missing_assets'):
        raise ValueError('原题隔离或缺材料，不能靠新标注放开')
    if question.get('quality', {}).get('answer_check', {}).get('status') == 'failed':
        raise ValueError('来源质量检查失败，不能直接放开')
    if 'fine_type_pending' in finding.fine_types or any('fine_type_pending' in p.fine_types for p in finding.parts):
        raise ValueError('具体题型仍是占位标签')
    issues = ['curriculum_unknown'] if question.get('grade') is None or question.get('term') is None else []
    parts = [dict(
        id=f'p{index}', prompt=p.prompt, reference_answer=p.answer, solution_steps=p.solution,
        knowledge_tags=p.knowledge, type_tags=p.fine_types,
        rubric=[dict(id=f'c{n}', description=evidence, evidence_required=evidence)
                for n, evidence in enumerate(p.evidence, 1)],
    ) for index, p in enumerate(finding.parts, 1)]
    annotation = Annotation.model_validate(dict(
        response_format=finding.response_format, knowledge=finding.knowledge.model_dump(),
        fine_types=finding.fine_types,
        difficulty=dict(level=question['difficulty'], origin='source',
                        basis=question.get('difficulty_basis') or '来源难度，未经实测校准'),
        curriculum=dict(grade=question.get('grade'), term=question.get('term'), scope_status='unknown',
                        basis='本轮未核对教材册次及课程目标，保持来源范围'),
        answer_spec=dict(mode='choice' if choice else 'multipart' if len(parts) > 1 else
                         'proof' if finding.response_format == 'proof' else 'text',
                         accepted_answers=[finding.answer], equivalence='exact' if choice else 'rubric',
                         constraints=finding.conditions),
        parts=parts, grading=dict(mode='objective' if choice else 'ai_rubric'),
        review=dict(status='candidate', method='item_read', answer_status='source_only', issues=issues,
                    notes=('已完成 Luna 逐题审核及交叉复核，必要时附独立裁定；当前通过为候选，不代表教师认证。'
                           + finding.source_comparison)[:3000]),
        origin=dict(model='gpt-6-luna', batch_id=batch_id),
    ))
    return validate_for_question(annotation, question).model_dump()


def apply_full_batch(db, directory, *, batch_id='physics-full-20261014', dry_run=True):
    """Validate every exported snapshot before any writes, then commit as one batch."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', batch_id):
        raise ValueError('批次标识无效')
    report, sources, primary, peers, adjudications = load_bundle(directory)
    digest = snapshot_hash({'batch_id': batch_id, 'files': report['file_sha256']})
    if not dry_run:
        if db.in_transaction:
            raise ValueError('全量复核必须在独立事务中应用')
        db.execute('BEGIN IMMEDIATE')
    try:
        previous = db.execute("SELECT details FROM audit_events WHERE kind='physics_full_review_batch' "
                              "AND json_extract(details,'$.batch_id')=? ORDER BY id DESC LIMIT 1", (batch_id,)).fetchone()
        if previous:
            saved = json.loads(previous[0])
            if saved['digest'] != digest:
                raise ValueError('该批次已应用不同内容，请使用新的批次标识')
            return {**saved['result'], 'already_applied': True}

        counts = Counter(total=len(sources), passed=0, excluded=0, unresolved=0,
                         draft_rebases=0, published=0, adjudicated=len(adjudications))
        plans = []
        for qid, source in sources.items():
            row = db.execute('SELECT source_id,status,data FROM bank_questions WHERE id=?',
                             (source['current_snapshot_id'],)).fetchone()
            if not row:
                raise ValueError('当前审核快照不存在：' + qid)
            question = json.loads(row['data'])
            if (question.get('subject') != 'physics' or question.get('stage') != 'junior'
                    or row['status'] in {'superseded', 'quarantine'} or question.get('status') != row['status']):
                raise ValueError('不是当前有效初中物理快照：' + qid)
            if question.get('provenance', {}).get('teacher_reviewed'):
                raise ValueError('人工审核题不能被模型批次覆盖：' + qid)
            original_id = question.get('annotation_source_question_id') or question['id']
            if (original_id != qid or snapshot_hash(question) != source['current_sha256']
                    or source_fingerprint({**question, 'id': qid}) != source['source_sha256']):
                raise ValueError('来源或完整快照已变化：' + qid)
            decision, reason = resolve(primary[qid], peers[qid])
            finding = primary[qid]
            if qid in adjudications:
                decision, reason = adjudications[qid].decision, adjudications[qid].reason
                if adjudications[qid].finding is not None:
                    finding = adjudications[qid].finding
            annotation = None
            if decision == 'pass':
                try:
                    annotation = annotation_for(finding, question, batch_id)
                except ValueError as exc:
                    decision, reason = 'unresolved', '入库一致性检查待处理：' + str(exc)
            counts[{'pass': 'passed', 'exclude': 'excluded', 'unresolved': 'unresolved'}[decision]] += 1
            plans.append((qid, row['source_id'], decision, reason, annotation, finding))
            # Rebind metadata only; never replace an existing editable form.
            draft = db.execute("SELECT state,published_id,data,source_hash FROM bank_editor_items "
                               "WHERE source_kind='bank' AND source_id=?", (source['current_snapshot_id'],)).fetchone()
            if draft:
                if draft['state'] != 'draft' or draft['published_id']:
                    raise ValueError('来源已有关联发布内容，拒绝自动改绑：' + qid)
                if (draft['source_hash'] != hashlib.sha256(dumps(question).encode()).hexdigest()
                        or json.loads(draft['data']).get('source') != question):
                    raise ValueError('已有草稿绑定已变化，拒绝自动改绑：' + qid)
                counts['draft_rebases'] += 1
        if dry_run:
            return {**counts, 'dry_run': True, 'all_reviews_complete': True}

        buffered = defaultdict(list)
        pending = []

        def flush():
            for dataset, records in buffered.items():
                manifest = json.loads(db.execute('SELECT manifest FROM bank_sources WHERE id=?', (dataset,)).fetchone()[0])
                result = bank.import_records(db, dataset, records, manifest, transaction=False)
                if result['inserted'] != len(records):
                    raise ValueError('全量复核未为每题生成预期快照，整批回滚')
            for qid, old_id, decision in pending:
                versions = db.execute('SELECT id,data,status FROM bank_questions WHERE id=? OR (id>=? AND id<?)',
                                      (qid, qid + ':', qid + ';')).fetchall()
                current = [row for row in versions if row['status'] != 'superseded']
                if len(current) != 1:
                    raise ValueError('审核后当前快照不唯一：' + qid)
                new_id, new_data = current[0]['id'], json.loads(current[0]['data'])
                if decision != 'pass':
                    for row in versions:
                        value = json.loads(row['data'])
                        if not value.get('evidence_invalidated'):
                            value['evidence_invalidated'] = True
                            db.execute('UPDATE bank_questions SET data=? WHERE id=?', (dumps(value), row['id']))
                draft = db.execute("SELECT * FROM bank_editor_items WHERE source_kind='bank' AND source_id=?", (old_id,)).fetchone()
                if draft:
                    value = json.loads(draft['data'])
                    value['source'] = new_data
                    rebases = list(value.get('source_rebases', []))
                    rebases.append(dict(batch_id=batch_id, old_snapshot_id=old_id, new_snapshot_id=new_id))
                    value['source_rebases'] = rebases
                    db.execute('UPDATE bank_editor_items SET source_id=?,source_hash=?,revision=revision+1,data=?,updated_at=? WHERE id=?',
                               (new_id, hashlib.sha256(dumps(new_data).encode()).hexdigest(), dumps(value), now(), draft['id']))
            buffered.clear()
            pending.clear()

        for qid, dataset, decision, reason, annotation, finding in plans:
            source = sources[qid]
            question = json.loads(db.execute('SELECT data FROM bank_questions WHERE id=?', (source['current_snapshot_id'],)).fetchone()[0])
            value = copy.deepcopy(question)
            value.update(id=qid, annotation=annotation, annotation_source_question_id=qid,
                         annotation_source_sha256=source['source_sha256'],
                         annotation_exclusion=None if decision == 'pass' else reason[:3000])
            quality = value['quality']
            quality['annotation_schema_version'] = 1
            quality['model_review'] = dict(
                status={'pass': 'passed', 'exclude': 'excluded', 'unresolved': 'unresolved'}[decision],
                batch_id=batch_id, model='gpt-6-luna', human_reviewed=False,
                source_sha256=source['source_sha256'], original_snapshot_sha256=source['current_sha256'],
                primary_record_sha256=snapshot_hash(primary[qid].model_dump()),
                peer_record_sha256=snapshot_hash(peers[qid].model_dump()),
                annotation_sha256=snapshot_hash(annotation),
                primary_decision=primary[qid].decision, peer_decision=peers[qid].decision,
                reason=reason,
            )
            if qid in adjudications:
                quality['model_review']['adjudication'] = dict(
                    reviewer=adjudications[qid].reviewer, decision=adjudications[qid].decision,
                    record_sha256=snapshot_hash(adjudications[qid].model_dump()))
            flags = [f for f in quality.get('flags', []) if f != 'fine_type_pending']
            if flags:
                quality['flags'] = flags
            else:
                quality.pop('flags', None)
            if decision == 'pass':
                fine_types = dict.fromkeys(finding.fine_types + [t for part in finding.parts for t in part.fine_types])
                value['fine_type_annotations'] = [dict(label=t, origin='luna', basis='independent_model_review', needs_review=True)
                                                   for t in fine_types]
            else:
                value.update(status='quarantine', can_practice=False, evidence_invalidated=True)
                value['fine_type_annotations'] = [t for t in value.get('fine_type_annotations', []) if t['label'] != 'fine_type_pending']
                value['issues'] = list(dict.fromkeys([*value.get('issues', []), 'annotation_excluded']))
            buffered[dataset].append(value)
            pending.append((qid, source['current_snapshot_id'], decision))
            if len(pending) >= BATCH_SIZE:
                flush()
        flush()
        result = {**counts, 'dry_run': False, 'all_reviews_complete': True}
        audit(db, 'physics_full_review_batch', dict(batch_id=batch_id, digest=digest, result=result,
                                                   model_review_only=True, file_sha256=report['file_sha256']))
        return result
    except BaseException:
        if not dry_run:
            db.rollback()
        raise
