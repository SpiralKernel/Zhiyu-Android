"""Structured AI feedback is advisory; numerical scores require reviewed rubrics."""
from typing import Literal

from pydantic import Field

from app.question_annotation import StrictModel, Annotation


class PartFeedback(StrictModel):
    part_id: str = Field(min_length=1, max_length=80)
    verdict: Literal['correct','incorrect','partial','uncertain']
    reason: str = Field(min_length=1, max_length=2000)
    evidence_quote: str = Field(default='', max_length=2000)


class CriterionFeedback(StrictModel):
    part_id: str = Field(min_length=1, max_length=80)
    criterion_id: str = Field(min_length=1, max_length=80)
    verdict: Literal['met','not_met','uncertain']
    evidence_quote: str = Field(default='', max_length=2000)
    reason: str = Field(min_length=1, max_length=2000)


def feedback_detail(q, assessment):
    if not q.get('annotation'):return None
    a = Annotation.model_validate(q['annotation'])
    ids = {p.id for p in a.parts}
    supplied = [f.part_id for f in assessment.part_feedback]
    issues = []
    if len(supplied)!=len(set(supplied)) or set(supplied)!=ids:
        issues.append('part_feedback_incomplete')
    part_feedback = [f.model_dump() for f in assessment.part_feedback if f.part_id in ids]
    if any(f['verdict']=='uncertain' for f in part_feedback):issues.append('part_uncertain')
    if assessment.verdict=='correct' and any(f['verdict']!='correct' for f in part_feedback):
        issues.append('overall_verdict_conflict')
    known = {(p.id,c.id):c for p in a.parts for c in p.rubric}
    seen = set(); criteria = []
    transcription = ''.join(assessment.transcribed_answer.split())
    for f in assessment.criterion_feedback:
        key = (f.part_id, f.criterion_id)
        if key not in known or key in seen:
            issues.append('criterion_feedback_invalid');continue
        seen.add(key)
        item = f.model_dump();quote = ''.join(f.evidence_quote.split())
        if f.verdict!='uncertain' and (not quote or quote not in transcription):
            item['verdict']='uncertain';issues.append('criterion_evidence_unverified')
        if item['verdict']=='uncertain':issues.append('criterion_uncertain')
        item['points'] = known[key].points
        criteria.append(item)
    reviewed = bool(q.get('provenance',{}).get('teacher_reviewed') and a.review.status=='reviewed'
                    and a.review.method=='teacher' and a.review.answer_status=='checked'
                    and not a.review.issues)
    complete = bool(a.grading.full_score is not None and known and seen==set(known)
                    and all(c.points is not None for c in known.values()))
    score = None
    if reviewed and complete and not issues and assessment.confidence=='high' and assessment.verdict!='uncertain':
        score = sum(known[(f['part_id'],f['criterion_id'])].points for f in criteria if f['verdict']=='met')
        if (assessment.verdict=='correct' and score!=a.grading.full_score) or (assessment.verdict=='incorrect' and score!=0):
            score=None;issues.append('score_verdict_conflict')
    return {'part_feedback':part_feedback, 'criterion_feedback':criteria, 'score':score,
            'full_score':a.grading.full_score if reviewed else None,
            'status':'ai_suggestion' if score is not None else 'review_required',
            'annotation_review':a.review.status, 'issues':list(dict.fromkeys(issues)),
            'notice':'AI 逐问反馈待核对；候选标注或缺少完整分值时不生成数值成绩。'}
