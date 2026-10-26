"""Validate a hash-pinned Luna batch before atomically creating question snapshots."""
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

from pydantic import Field

from app import bank
from app.db import audit
from app.question_annotation import Annotation, StrictModel, source_fingerprint, validate_for_question

BATCH_SIZE = 128


class Entry(StrictModel):
    question_id: str = Field(min_length=1, max_length=200)
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    decision: Literal['annotate', 'exclude']
    reason: str = Field(min_length=1, max_length=3000)
    annotation: Annotation | None


def iter_entries(paths):
    """Validate lazily so large batches do not retain every Pydantic object."""
    seen = set()
    for path in paths:
        with Path(path).open() as stream:
            for line_no, line in enumerate(stream, 1):
                if not line.strip():continue
                try:
                    e = Entry.model_validate_json(line)
                    if e.question_id in seen:raise ValueError('题号重复')
                    if (e.decision == 'annotate') != (e.annotation is not None):raise ValueError('处理决定和标注不一致')
                    if e.annotation and (e.annotation.review.status != 'candidate' or e.annotation.review.method == 'teacher'):
                        raise ValueError('Luna 批量结果只能为待审核候选')
                    seen.add(e.question_id)
                except ValueError as exc:
                    raise ValueError(f'{Path(path).name}:{line_no}: {exc}') from exc
                yield e


def load_entries(paths):
    return list(iter_entries(paths))


def apply_batch(db, entries, *, dry_run=True, subject='math', transaction=True):
    """Whole batch succeeds or rolls back. Existing answers/student records are immutable."""
    if subject not in {'math','physics'}:raise ValueError('不支持的批量标注学科')
    counts = Counter(total=0); plans = defaultdict(list); seen = set()
    buffered = 0

    def flush():
        for dataset, records in plans.items():
            manifest = json.loads(db.execute('SELECT manifest FROM bank_sources WHERE id=?',(dataset,)).fetchone()[0])
            bank.import_records(db, dataset, records, manifest, transaction=False)
            from app.admin import supersede
            for q in records:
                if q.get('annotation_exclusion'):
                    supersede(db,q['id'],invalidate=True)
        plans.clear()
    # A write lock closes the gap between fingerprint validation and snapshot creation.
    if not dry_run:
        if transaction:db.execute('BEGIN IMMEDIATE')
        elif not db.in_transaction:raise ValueError('批量标注必须处于调用方事务中')
    try:
        current = {}
        for row in db.execute("SELECT id,source_id,json_extract(data,'$.annotation_source_question_id') original_id FROM bank_questions WHERE subject=? AND stage='junior' AND status!='superseded'",(subject,)):
            current[row['original_id'] or row['id']] = (row['source_id'], row['id'])
        for e in entries:
            counts['total'] += 1
            if e.question_id in seen:raise ValueError(f'题号重复：{e.question_id}')
            seen.add(e.question_id)
            if e.question_id not in current:raise ValueError(f'来源题不存在或已被其它修订替换：{e.question_id}')
            dataset, qid = current[e.question_id]
            q = json.loads(db.execute('SELECT data FROM bank_questions WHERE id=?',(qid,)).fetchone()[0])
            pinned = {**q, 'id':e.question_id}
            if source_fingerprint(pinned) != e.source_sha256:raise ValueError(f'来源内容已变化，拒绝贴标：{e.question_id}')
            if q.get('provenance',{}).get('teacher_reviewed'):
                raise ValueError(f'人工审核内容不能被候选批次覆盖：{e.question_id}')
            value = e.annotation.model_dump() if e.annotation else None
            if q.get('annotation_source_sha256') == e.source_sha256 and q.get('annotation') == value and q.get('annotation_exclusion') == (e.reason if e.decision=='exclude' else None):
                counts['unchanged'] += 1;continue
            if value:
                a = validate_for_question(value, q)
                if q['status']=='quarantine' or q.get('has_missing_assets') or q.get('quality',{}).get('answer_check',{}).get('status')=='failed':
                    raise ValueError(f'无效题必须剔除，不能靠新标注放开：{e.question_id}')
                if a.review.answer_status == 'checked':raise ValueError('批量候选不可擅自认证来源答案')
                counts['annotated'] += 1
                counts[a.review.method] += 1
                counts['parts_pending'] += int('part_answer_pending' in a.review.issues)
                counts['rubric_pending'] += int('rubric_pending' in a.review.issues)
                counts['fine_type_pending'] += int('fine_type_pending' in a.review.issues)
                counts['score_pending'] += int(a.grading.full_score is None)
            else:counts['excluded'] += 1
            if dry_run:continue
            new = copy.deepcopy(q)
            new.update(annotation=value, annotation_source_question_id=e.question_id,
                       annotation_source_sha256=e.source_sha256, annotation_exclusion=e.reason if e.decision=='exclude' else None)
            if value:
                old = new.get('fine_type_annotations', [])
                existing = {t['label'] for t in old}
                new['fine_type_annotations'] = old + [dict(label=t, origin='luna', basis='structured_candidate', needs_review=True)
                                                      for t in a.fine_types if t not in existing]
            else:
                new.update(status='quarantine', can_practice=False, evidence_invalidated=True)
                new['issues'] = list(dict.fromkeys([*new.get('issues',[]), 'annotation_excluded']))
            # An annotation revision uses the existing immutable quality upgrade path.
            new['quality'] = {**new.get('quality',{}), 'annotation_schema_version':1}
            if subject in {'physics','math'}:
                # A different annotation is not covered by an earlier dual review.
                new['quality'].pop('model_review',None)
            if subject=='physics' and value and 'fine_type_pending' in a.review.issues:
                new['quality']['flags']=list(dict.fromkeys([*new['quality'].get('flags',[]),'fine_type_pending']))
            elif subject=='physics':
                # A precise annotation or exclusion no longer has this blocker.
                # Retaining it would disable practice and cause reimport churn.
                flags=[f for f in new['quality'].get('flags',[]) if f!='fine_type_pending']
                if flags:new['quality']['flags']=flags
                else:new['quality'].pop('flags',None)
            plans[dataset].append(new)
            buffered += 1
            if buffered >= BATCH_SIZE:
                flush();buffered = 0
        if not dry_run:
            flush()
            audit(db, subject+'_annotation_batch', dict(counts))
        return dict(counts)
    except BaseException:
        if not dry_run:db.rollback()
        raise
