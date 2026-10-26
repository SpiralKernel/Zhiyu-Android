"""Conservative prerequisites plus a separate review before learning claims."""
import re
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app import ai_policy

SENSITIVE = {"difficulty", "guided_success", "understanding_check", "reviewed_success"}
CHECKED = {"guided_success", "understanding_check"}
SELF_REPORT = re.compile(r"不会|不懂|没(?:有)?(?:懂|明白|学会)|不(?:太)?(?:理解|明白|会做)|搞不懂|算不出|不知道怎么|看不懂")
ACK = re.compile(r"^[\s，。！？,.!?]*(?:(?:我|好的?|懂了|明白了|会了|知道了|谢谢|嗯|哦|是的|对的|可以)[\s，。！？,.!?]*)+$")


class Decision(BaseModel):
    candidate_index: int = Field(ge=0, le=2)
    verdict: Literal["supported", "unsupported", "uncertain"]
    evidence_quote: str = Field(default="", max_length=500)
    reason: str = Field(min_length=1, max_length=600)


class Review(BaseModel):
    decisions: list[Decision] = Field(default_factory=list, max_length=3)


def prerequisite(proposal, evidence, last_check=None):
    """Return an explicit rejection reason; uncertainty must never become mastery."""
    quote = proposal.evidence_quote.strip()
    text = evidence.get(proposal.evidence_source, "")
    if ai_policy.boundary_reason(text):
        return "instruction_not_learning_evidence"
    if not quote or quote not in text:
        return "quote_not_in_selected_source"
    if proposal.evidence_source == "image_answer" and not evidence.get("image_confirmed"):
        return "image_not_confirmed"
    if proposal.kind == "self_report" and not SELF_REPORT.search(quote):
        return "no_explicit_self_report"
    if proposal.kind == "self_report" and re.search(r"不是不会|并非不懂|已经(?:会|懂)|没有不懂", quote):
        return "negated_self_report"
    if proposal.kind == "self_report" and re.search(r"(?:同学|朋友|他|她|小明).{0,8}(?:不会|不懂|没懂)", text) and not re.search(r"我.{0,6}(?:不会|不懂|没懂)", text):
        return "other_person_is_not_student"
    if proposal.kind in SENSITIVE:
        if proposal.kind == 'reviewed_success' and not evidence.get('image_confirmed'):
            return 'reviewed_work_not_confirmed'
        if ACK.fullmatch(quote):
            return "instruction_or_acknowledgement"
        # A request for an explanation is not evidence of an attempted solution.
        if (proposal.evidence_source == "message" and
                re.search(r"[?？]|是什么|怎么(?:做|算|理解)|为什么", text) and
                not re.search(r"[=＝≠<>≤≥]|我(?:算|写|认为|觉得)|因为.+所以", quote)):
            return "question_without_student_work"
        if proposal.kind == "difficulty" and SELF_REPORT.search(quote) and not re.search(r"[=＝≠<>≤≥]", quote):
            return "self_report_is_not_observed_error"
        if proposal.kind in CHECKED:
            if not last_check or proposal.check_message_id != last_check["message_id"]:
                return "missing_prior_check"
            answer = text.strip(" \n，。！？,.!?")
            if not answer or ACK.fullmatch(answer):
                return "no_substantive_check_answer"
            if (len(answer) >= 8 and answer in last_check.get("teacher_reply", "")) or answer == last_check["question"]:
                return "copied_teacher_text"
    return None


async def validate(settings, proposals, evidence, context, last_check=None):
    from app.bank_ai import request_json

    accepted, rejected, candidates = [], [], []
    for index, proposal in enumerate(proposals):
        reason = prerequisite(proposal, evidence, last_check)
        if reason:
            rejected.append({"candidate_index": index, "reason": reason})
        elif proposal.kind in SENSITIVE:
            candidates.append((index, proposal))
        else:
            # Do not preserve a free-form model diagnosis for an interest/self-report.
            note = "正在了解这个题型，尚未判断掌握情况。" if proposal.kind == "question_interest" else "学生自述有困难，仍需作答验证。"
            accepted.append((proposal.model_copy(update={"note": note}), {"method": "source_rules"}))
    if not candidates:
        return accepted, rejected
    check = {k: last_check[k] for k in ('message_id', 'question')} if last_check else None
    payload = {"subject":context.get("subject","math"),"book_id":context.get("book_id"),"student_evidence": evidence, "current_question": context.get("current_question"),
               "last_check": check, "stage_goals": context["stage_goals"],
               "type_catalog": context["type_catalog"],
               "candidates": [{"candidate_index": i, **p.model_dump(exclude={"note"})} for i, p in candidates]}
    try:
        review = await request_json(settings, ai_policy.messages(ai_policy.OBSERVER, payload), Review)
    except HTTPException:
        rejected.extend({"candidate_index": i, "reason": "review_unavailable"} for i, _ in candidates)
        return accepted, rejected
    counts = {i: sum(d.candidate_index == i for d in review.decisions) for i, _ in candidates}
    decisions = {d.candidate_index: d for d in review.decisions}
    for index, proposal in candidates:
        decision = decisions.get(index)
        if counts[index] != 1 or decision.verdict != "supported" or decision.evidence_quote != proposal.evidence_quote:
            rejected.append({"candidate_index": index, "reason": "review_not_supported"})
            continue
        accepted.append((proposal.model_copy(update={"note": decision.reason[:500]}),
                         {"method": "independent_ai_review", "reason": decision.reason,
                          "check_message_id": last_check["message_id"] if proposal.kind in CHECKED else None}))
    return accepted, rejected
