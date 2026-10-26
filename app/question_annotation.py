"""Versioned question annotations. Candidate labels never certify an answer or score."""
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class ErrorPattern(StrictModel):
    description: str = Field(min_length=1, max_length=1000)
    knowledge_tags: list[str] = Field(default_factory=list, max_length=12)
    type_tags: list[str] = Field(default_factory=list, max_length=12)


class Criterion(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=2000)
    points: float | None = Field(default=None, gt=0, le=1000)
    evidence_required: str = Field(default='', max_length=2000)


class Part(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=30000)
    reference_answer: str | None = Field(default=None, max_length=12000)
    solution_steps: list[str] = Field(default_factory=list, max_length=40)
    knowledge_tags: list[str] = Field(default_factory=list, max_length=20)
    type_tags: list[str] = Field(default_factory=list, max_length=20)
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    points: float | None = Field(default=None, gt=0, le=1000)
    rubric: list[Criterion] = Field(default_factory=list, max_length=40)
    common_errors: list[ErrorPattern] = Field(default_factory=list, max_length=12)


class Knowledge(StrictModel):
    primary: list[str] = Field(default_factory=list, max_length=20)
    supporting: list[str] = Field(default_factory=list, max_length=20)
    prerequisites: list[str] = Field(default_factory=list, max_length=20)


class Difficulty(StrictModel):
    level: int = Field(ge=1, le=3)
    basis: str = Field(min_length=1, max_length=2000)
    origin: Literal['source', 'luna', 'teacher', 'model'] = 'source'
    calibrated: Literal[False] = False


class Curriculum(StrictModel):
    grade: int | None = Field(default=None, ge=7, le=12)
    term: int | None = Field(default=None, ge=1, le=2)
    book_id: str | None = Field(default=None, max_length=100)
    goal_ids: list[str] = Field(default_factory=list, max_length=20)
    scope_status: Literal['source', 'candidate', 'unknown', 'reviewed'] = 'unknown'
    basis: str = Field(default='', max_length=2000)


class AnswerSpec(StrictModel):
    mode: Literal['choice', 'numeric', 'expression', 'text', 'multipart', 'proof'] = 'text'
    accepted_answers: list[str] = Field(default_factory=list, max_length=30)
    equivalence: Literal['exact', 'numeric', 'symbolic', 'semantic', 'rubric', 'manual'] = 'manual'
    constraints: list[str] = Field(default_factory=list, max_length=20)
    unit: str | None = Field(default=None, max_length=100)
    tolerance: float | None = Field(default=None, ge=0, le=1000)


class Grading(StrictModel):
    mode: Literal['objective', 'ai_rubric', 'manual'] = 'manual'
    full_score: float | None = Field(default=None, gt=0, le=1000)
    allow_alternative_methods: bool = True
    uncertainty_policy: Literal['review_required'] = 'review_required'


class Review(StrictModel):
    status: Literal['candidate', 'reviewed', 'ai_reviewed'] = 'candidate'
    answer_status: Literal['source_only', 'checked', 'conflict', 'unknown'] = 'source_only'
    issues: list[str] = Field(default_factory=list, max_length=40)
    method: Literal['rule_assisted', 'item_read', 'teacher'] = 'rule_assisted'
    notes: str = Field(default='', max_length=3000)


class Origin(StrictModel):
    model: str = Field(default='gpt-6-luna', max_length=100)
    batch_id: str = Field(default='', max_length=100)


class Annotation(StrictModel):
    schema_version: Literal[1] = 1
    response_format: Literal['single_choice', 'multiple_choice', 'fill_blank', 'calculation', 'proof', 'application', 'composite', 'short_answer']
    knowledge: Knowledge = Field(default_factory=Knowledge)
    fine_types: list[str] = Field(default_factory=list, max_length=20)
    difficulty: Difficulty
    curriculum: Curriculum = Field(default_factory=Curriculum)
    answer_spec: AnswerSpec = Field(default_factory=AnswerSpec)
    parts: list[Part] = Field(default_factory=list, max_length=30)
    grading: Grading = Field(default_factory=Grading)
    review: Review = Field(default_factory=Review)
    origin: Origin = Field(default_factory=Origin)

    @model_validator(mode='after')
    def consistent_parts(self):
        ids = [p.id for p in self.parts]
        if len(ids) != len(set(ids)):
            raise ValueError('小问编号不可重复')
        for i, p in enumerate(self.parts):
            if any(d not in ids[:i] for d in p.depends_on):
                raise ValueError('小问只能依赖前面已有的小问')
            keys = [c.id for c in p.rubric]
            if len(keys) != len(set(keys)):
                raise ValueError('同一小问的得分点编号不可重复')
            if p.points is not None and p.rubric and all(c.points is not None for c in p.rubric):
                if abs(sum(c.points for c in p.rubric) - p.points) > 1e-8:
                    raise ValueError('得分点分值之和须等于小问分值')
        if self.grading.full_score is not None:
            if not self.parts or any(p.points is None for p in self.parts):
                raise ValueError('整题分值需要完整的小问分值')
            if abs(sum(p.points for p in self.parts) - self.grading.full_score) > 1e-8:
                raise ValueError('小问分值之和须等于整题分值')
        return self


def source_fingerprint(q):
    fields = ('id', 'subject', 'stage', 'stem', 'options', 'answer', 'steps', 'grade', 'term', 'knowledge_tags', 'type_tags', 'difficulty', 'provenance')
    raw = json.dumps({k: q.get(k) for k in fields}, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def public_annotation(value, reveal=False):
    """Never send reference answers, rubrics or diagnostic hints before submission."""
    a = Annotation.model_validate(value)
    if reveal:
        return a.model_dump()
    return {'schema_version':1, 'response_format':a.response_format,
            'parts':[{'id':p.id, 'prompt':p.prompt} for p in a.parts]}


def validate_for_question(value, q, published=False):
    a = Annotation.model_validate(value)
    expected = q.get('kind')
    if expected in {'single_choice', 'multiple_choice'}:
        if a.response_format != expected or a.answer_spec.mode != 'choice':
            raise ValueError('选择题的作答形式与原题不符')
    elif a.response_format in {'single_choice','multiple_choice'}:
        raise ValueError('过程题不能仅靠标注改成选择题')
    stage = q.get('stage')
    grades = [grade for grade in (q.get('grade'), a.curriculum.grade) if grade is not None]
    if stage == 'junior' and any(not 7 <= grade <= 9 for grade in grades):
        raise ValueError('初中题目与结构化标注的年级必须在七至九年级')
    if stage == 'senior' and any(not 10 <= grade <= 12 for grade in grades):
        raise ValueError('高中题目与结构化标注的年级必须在十至十二年级')
    if q.get('curriculum_book_id') and a.curriculum.book_id != q['curriculum_book_id']:
        raise ValueError('结构化标注与题目主适用册次不一致')
    if a.curriculum.book_id:
        from app.course_catalog import BOOK_MAP
        book = BOOK_MAP.get(a.curriculum.book_id)
        if not book or book['subject'] != q.get('subject') or book.get('stage') != stage:
            raise ValueError('课程册次与题目科目或学段不一致')
    if a.curriculum.goal_ids:
        from app.course_catalog import GOALS
        if stage == 'senior' and not a.curriculum.book_id:
            raise ValueError('高中课程目标需要指定主适用册次')
        bid = a.curriculum.book_id or q.get('curriculum_book_id')
        if not bid and stage == 'junior' and q.get('grade') is not None and q.get('term') is not None:
            bid = f"{q.get('subject')}-{q['grade']}-{q['term']}"
        for goal_id in a.curriculum.goal_ids:
            target = GOALS.get(goal_id)
            if (not target or target['subject'] != q.get('subject')
                    or target.get('stage', 'junior') != stage
                    or (bid and target['book_id'] != bid)):
                raise ValueError('课程目标与题目科目、学段或主适用册次不一致')
    if 'curriculum_goal_ids' in q and set(a.curriculum.goal_ids) != set(q.get('curriculum_goal_ids') or []):
        raise ValueError('结构化标注与题目课程目标不一致')
    if published:
        if a.review.status != 'reviewed' or a.review.method != 'teacher':
            raise ValueError('发布结构化标注前须人工核对并标为已审核')
        if a.review.answer_status in {'conflict','unknown'}:
            raise ValueError('答案冲突或未知，不能发布')
        if a.response_format not in {'single_choice','multiple_choice'}:
            if not a.parts or any(not p.reference_answer or not p.rubric for p in a.parts):
                raise ValueError('过程题需要逐问参考答案和判分依据')
        if a.curriculum.grade != q.get('grade') or a.curriculum.term != q.get('term'):
            raise ValueError('结构化标注与题目册次不一致')
    return a
