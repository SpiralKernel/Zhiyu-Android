"""Stage AI physics review proposals; only a human can publish reviewed content."""
import hashlib
import json
import uuid
from typing import Literal

from pydantic import Field

from app import bank
from app.admin import Draft
from app.db import audit, dumps, now
from app.math_annotations import Entry, apply_batch
from app.question_annotation import StrictModel, source_fingerprint, validate_for_question


class ReviewItem(StrictModel):
    question_id: str = Field(min_length=1, max_length=200)
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    current_snapshot_id: str = Field(min_length=1, max_length=200)
    current_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    batch: Literal['B1', 'B2', 'B3', 'B4']
    trial_group: str = ''
    reviewer: str
    peer_reviewers: list[str] = Field(default_factory=list)
    review_date: str = '2026-10-14'
    source_code_revision: str = Field(default='9c7381e4c778c59b787990f26064ad91d188110d', pattern=r'^[0-9a-f]{40}$')
    decision: Literal['repair_draft', 'keep_quarantined', 'insufficient_evidence']
    quarantine_original: bool = False
    independent_solution: list[str]
    source_conflicts: list[str] = Field(default_factory=list)
    resolved_findings: list[str] = Field(default_factory=list)
    remaining_issues: list[str]
    rationale: str = Field(min_length=1, max_length=8000)
    proposed_form: Draft | None = None


def snapshot_hash(q):
    return hashlib.sha256(json.dumps(q, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def validate_proposal(item):
    """Structure cannot prove correctness, but blocks fabricated approval and scores."""
    form = item.proposed_form
    if form is None:return
    if form.subject != 'physics' or form.grade is not None or form.term is not None or form.curriculum_goal_ids:
        raise ValueError('本批没有册次依据，不可猜填课程范围')
    if not form.stem.strip() or not form.answer.strip() or not form.steps or not form.type_tags:
        raise ValueError('修订草稿需要题干、答案、解析和具体题型')
    if not form.annotation:raise ValueError('精审草稿必须附完整标注')
    a = validate_for_question(form.annotation, form.model_dump())
    if a.review.status != 'candidate' or a.review.method != 'item_read' or a.review.answer_status not in {'source_only', 'unknown', 'conflict'}:
        raise ValueError('AI 复核不能认证人工审核或来源答案')
    if a.curriculum.grade is not None or a.curriculum.term is not None or a.curriculum.goal_ids:
        raise ValueError('结构化标注不可猜填册次')
    if not {'teacher_answer_review_pending', 'curriculum_unknown'}.issubset(a.review.issues):
        raise ValueError('草稿必须保留人工验答案及课程范围待审')
    if a.grading.full_score is not None or any(p.points is not None or any(c.points is not None for c in p.rubric) for p in a.parts):
        raise ValueError('来源未提供分值，不可虚构评分')
    if not a.parts or any(not p.reference_answer or not p.rubric or any(not c.evidence_required for c in p.rubric) for p in a.parts):
        raise ValueError('每问必须有参考答案和可观察的评阅证据')
    if form.kind != 'reference':
        question = form.model_dump()
        correct = bank.canonical_choice(form.answer, question)
        if not a.answer_spec.accepted_answers or any(bank.canonical_choice(v, question) != correct for v in a.answer_spec.accepted_answers):
            raise ValueError('草稿答案与选项判定不一致')
        if any(bank.canonical_choice(p.reference_answer, question) != correct for p in a.parts):
            raise ValueError('选择题小问答案与整题不一致')
    elif form.options:raise ValueError('过程题不应残留选择题选项')


def stage_batch(db, records, *, batch_id='physics-audit-20261014', dry_run=True):
    items = [ReviewItem.model_validate(r) for r in records]
    if not items or len({r.question_id for r in items}) != len(items):
        raise ValueError('精审清单为空或题号重复')
    digest = hashlib.sha256(json.dumps([r.model_dump() for r in items], ensure_ascii=False,
                                      sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if not dry_run:db.execute('BEGIN IMMEDIATE')
    try:
        previous = db.execute("SELECT details FROM audit_events WHERE kind='physics_review_batch' AND json_extract(details,'$.batch_id')=? ORDER BY id DESC LIMIT 1", (batch_id,)).fetchone()
        if previous:
            saved = json.loads(previous[0])
            if saved['digest'] != digest:raise ValueError('该审核批次已应用不同内容，请建立新批次')
            return {**saved['result'], 'already_applied': True}
        sources = {}; exclusions = []
        for item in items:
            validate_proposal(item)
            row = db.execute('SELECT data FROM bank_questions WHERE id=?', (item.current_snapshot_id,)).fetchone()
            if not row:raise ValueError('审核快照不存在：'+item.question_id)
            q = json.loads(row[0])
            if q['subject'] != 'physics' or q.get('stage') != 'junior' or q['status'] == 'superseded':
                raise ValueError('来源不是当前初中物理快照：'+item.question_id)
            if q.get('provenance', {}).get('teacher_reviewed'):
                raise ValueError('人工审核题不能被 AI 批次覆盖')
            if snapshot_hash(q) != item.current_sha256 or source_fingerprint({**q, 'id': item.question_id}) != item.source_sha256:
                raise ValueError('来源或标注快照已变化：'+item.question_id)
            sources[item.question_id] = q
            if item.quarantine_original or item.decision != 'repair_draft':
                reason = ('AI 独立复核仍待人工确认：'+item.rationale+'；'+'；'.join(item.source_conflicts))[:3000]
                exclusions.append(Entry(question_id=item.question_id, source_sha256=item.source_sha256,
                                        decision='exclude', reason=reason, annotation=None))
        result = {'total': len(items), 'drafts': 0, 'existing_drafts_preserved': 0,
                  'quarantine_decisions': len(exclusions), 'published': 0}
        if dry_run:
            result['drafts'] = sum(r.proposed_form is not None for r in items)
            return result
        if exclusions:apply_batch(db, exclusions, subject='physics', dry_run=False, transaction=False)
        for item in items:
            if item.proposed_form is None:continue
            # Bind a draft to the new quarantine snapshot, never the superseded source.
            row = db.execute("SELECT id,data FROM bank_questions WHERE subject='physics' AND status!='superseded' AND (json_extract(data,'$.annotation_source_question_id')=? OR id=?)", (item.question_id, item.question_id)).fetchone()
            if not row:raise ValueError('应用后来源快照缺失')
            q = json.loads(row['data'])
            existing = db.execute("SELECT id FROM bank_editor_items WHERE source_kind='bank' AND source_id=?", (row['id'],)).fetchone()
            if existing:
                result['existing_drafts_preserved'] += 1;continue
            form = item.proposed_form.model_dump()
            identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, 'AI-teacher:'+batch_id+':'+item.question_id))
            data = {'form': form, 'source': q,
                    'ai_review': {'batch_id': batch_id, 'question_id': item.question_id,
                                  'source_sha256': item.source_sha256, 'reviewer': item.reviewer,
                                  'peer_reviewers': item.peer_reviewers, 'human_approved': False}}
            # No administrator identity or human review event is fabricated.
            db.execute('INSERT INTO bank_editor_items VALUES(?,?,?,?,?,?,?,NULL,?)',
                       (identifier, 'bank', row['id'], hashlib.sha256(dumps(q).encode()).hexdigest(),
                        1, dumps(data), 'draft', now()))
            result['drafts'] += 1
        audit(db, 'physics_review_batch', {'batch_id': batch_id, 'digest': digest,
                                          'review_type': 'ai_proposal', 'result': result})
        return result
    except BaseException:
        if not dry_run:db.rollback()
        raise
