"""Math full-review contracts and checkpoints; never writes the question bank.

Mirrors the junior physics full review protocol (app/physics_full_review.py):
two complete rounds of independent, source-pinned per-question review plus
adjudication records for disagreements. Model review never certifies an answer
as teacher-reviewed and never fabricates scores or curriculum scope.
"""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from app.question_annotation import Knowledge, StrictModel


class ReviewedPart(StrictModel):
    prompt: str = Field(min_length=1, max_length=12000)
    answer: str = Field(min_length=1, max_length=12000)
    solution: list[str] = Field(min_length=1, max_length=30)
    knowledge: list[str] = Field(min_length=1, max_length=20)
    fine_types: list[str] = Field(min_length=1, max_length=20)
    evidence: list[str] = Field(min_length=1, max_length=20)


class Finding(StrictModel):
    question_id: str
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    decision: Literal['pass', 'exclude', 'unresolved']
    reason: str = Field(min_length=1, max_length=5000)
    independent_solution: list[str] = Field(min_length=1, max_length=30)
    answer: str = Field(default='', max_length=12000)
    answer_matches_source: bool = False
    source_comparison: str = Field(min_length=1, max_length=4000)
    response_format: Literal['single_choice', 'multiple_choice', 'fill_blank', 'calculation', 'proof', 'application', 'composite', 'short_answer'] = 'short_answer'
    knowledge: Knowledge = Field(default_factory=Knowledge)
    fine_types: list[str] = Field(default_factory=list, max_length=20)
    parts: list[ReviewedPart] = Field(default_factory=list, max_length=30)
    conditions: list[str] = Field(default_factory=list, max_length=20)
    remaining_issues: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode='after')
    def completed_pass(self):
        if self.decision == 'pass':
            if not self.answer_matches_source or not self.answer or not self.parts or not self.fine_types or not self.knowledge.primary:
                raise ValueError('通过必须有独立答案、来源比较及逐问证据与具体标签')
            if 'fine_type_pending' in self.fine_types:
                raise ValueError('粗泛占位标签不能算审核通过')
        return self


class PeerFinding(StrictModel):
    question_id: str
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    decision: Literal['accept', 'exclude', 'unresolved', 'revise']
    independent_solution: list[str] = Field(min_length=1, max_length=30)
    reason: str = Field(min_length=1, max_length=5000)
    correction: Finding | None = None

    @model_validator(mode='after')
    def consistent_correction(self):
        if self.decision == 'revise' and self.correction is None:
            raise ValueError('修订意见必须附完整修订结果')
        if self.correction is not None:
            if self.decision != 'revise':
                raise ValueError('仅修订意见可以附替代结果')
            if (self.correction.question_id, self.correction.source_sha256) != (self.question_id, self.source_sha256):
                raise ValueError('修订结果必须绑定同一题目和来源哈希')
        return self


class Adjudication(StrictModel):
    question_id: str
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    primary_record_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    peer_record_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: Literal['review-agent', 'orchestrator']
    decision: Literal['pass', 'exclude', 'unresolved']
    reason: str = Field(min_length=1, max_length=5000)
    independent_solution: list[str] = Field(min_length=1, max_length=30)
    finding: Finding | None = None

    @model_validator(mode='after')
    def bound_result(self):
        if self.decision == 'pass' and self.finding is None:
            raise ValueError('裁定通过必须附完整最终标注')
        if self.finding is not None and (
            self.finding.question_id != self.question_id or self.finding.source_sha256 != self.source_sha256
            or self.finding.decision != self.decision
        ):
            raise ValueError('裁定标注必须绑定同题同来源同决定')
        return self


def record_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def inspect_batch(directory: str | Path) -> dict:
    """Validate saved work and enumerate exact remaining IDs for resumption.

    An accepted peer agrees with the primary decision, which may be exclusion.
    Disagreements remain for adjudication, even if the peer proposes a pass.
    Missing output files are valid checkpoints; malformed/duplicate/stale rows
    are errors, never silently skipped. Inputs and model outputs stay untouched.
    """
    directory = Path(directory)
    manifest_raw = (directory / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    sizes = manifest['shards']
    if (not sizes or any(type(n) is not int or n <= 0 for n in sizes)
            or type(manifest['total']) is not int or sum(sizes) != manifest['total']):
        raise ValueError('清单题数与分片不一致')
    sources, primary, peers = {}, {}, {}
    hashes = {'manifest.json': hashlib.sha256(manifest_raw).hexdigest()}
    shards = []

    def rows(name, optional=False):
        path = directory / name
        if optional and not path.exists():
            return []
        raw = path.read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        result = []
        for line_number, line in enumerate(raw.decode('utf-8').splitlines(), 1):
            if not line.strip():
                raise ValueError(f'{name}:{line_number}: 空记录')
            try:
                result.append(json.loads(line))
            except ValueError as exc:
                raise ValueError(f'{name}:{line_number}: JSON 无效') from exc
        return result

    # First validate the entire input universe before interpreting any outputs.
    for shard, expected in enumerate(sizes):
        inputs = rows(f'input-{shard}.jsonl')
        if len(inputs) != expected:
            raise ValueError(f'分片 {shard} 的输入题数不符')
        ids = []
        for item in inputs:
            qid = item['question_id']
            if not isinstance(qid, str) or not qid or qid in sources:
                raise ValueError(f'输入题号为空或重复：{qid}')
            for key in ('source_sha256', 'current_sha256'):
                if not isinstance(item[key], str) or not re.fullmatch(r'[0-9a-f]{64}', item[key]):
                    raise ValueError(f'{qid}: {key} 无效')
            if (not isinstance(item['question'], dict)
                    or not isinstance(item['current_snapshot_id'], str) or not item['current_snapshot_id']):
                raise ValueError(f'{qid}: 缺少题目或快照')
            sources[qid] = item
            ids.append(qid)
        shards.append({'shard': shard, 'total': expected, 'ids': ids})

    for shard in shards:
        allowed = set(shard['ids'])
        for prefix, model, target in (('primary', Finding, primary), ('peer', PeerFinding, peers)):
            name = f'{prefix}-{shard["shard"]}.jsonl'
            for line_number, raw in enumerate(rows(name, optional=True), 1):
                item = model.model_validate(raw)
                if item.question_id not in allowed or item.question_id in target:
                    raise ValueError(f'{name}:{line_number}: 题号不属于分片或重复')
                if item.source_sha256 != sources[item.question_id]['source_sha256']:
                    raise ValueError(f'{name}:{line_number}: 来源哈希不符')
                target[item.question_id] = item
    if set(peers) - set(primary):
        raise ValueError('交叉复核记录没有对应初审记录')
    adjudications = {}
    for raw in rows('adjudications.jsonl', optional=True):
        item = Adjudication.model_validate(raw)
        qid = item.question_id
        if qid in adjudications or qid not in primary or qid not in peers:
            raise ValueError('裁定题号重复或缺少双轮审核')
        if (item.source_sha256 != sources[qid]['source_sha256']
                or item.primary_record_sha256 != record_hash(primary[qid].model_dump())
                or item.peer_record_sha256 != record_hash(peers[qid].model_dump())):
            raise ValueError('裁定绑定的来源或审核意见已变化')
        adjudications[qid] = item

    # Supplemental, record-bound attribution lets later Luna rounds coexist
    # with the original export model without rewriting earlier evidence.
    reviewer_models = {'primary': {}, 'peer': {}, 'adjudication': {}}
    provenance_path = directory / 'review-provenance.json'
    if provenance_path.exists():
        raw = provenance_path.read_bytes()
        hashes['review-provenance.json'] = hashlib.sha256(raw).hexdigest()
        provenance = json.loads(raw)
        if provenance.get('schema_version') != 1:
            raise ValueError('审核模型来源清单版本无效')
        targets = {'primary': primary, 'peer': peers, 'adjudication': adjudications}
        for entry in provenance.get('records', []):
            round_name, qid = entry.get('round'), entry.get('question_id')
            if round_name not in targets or qid not in targets[round_name]:
                raise ValueError('审核模型来源记录缺少对应审核意见')
            if qid in reviewer_models[round_name]:
                raise ValueError('审核模型来源记录重复')
            supported = entry.get('model') in {'gpt-6-luna', 'opencode/deepseek-v4.1-flash-free'}
            if (entry.get('model') == 'orchestrator' and round_name == 'adjudication'
                    and targets[round_name][qid].reviewer == 'orchestrator'):
                supported = True
            if not supported:
                raise ValueError('审核模型来源记录模型不受支持')
            if entry.get('record_sha256') != record_hash(targets[round_name][qid].model_dump()):
                raise ValueError('审核模型来源记录绑定的审核意见已变化')
            if round_name == 'peer' and 'primary_record_sha256' in entry:
                if entry['primary_record_sha256'] != record_hash(primary[qid].model_dump()):
                    raise ValueError('独立复核时读取的初审意见已变化，需要重新复核')
            reviewer_models[round_name][qid] = entry['model']

    primary_counts = Counter(item.decision for item in primary.values())
    peer_counts = Counter(item.decision for item in peers.values())
    agreed = Counter()
    adjudication, integration_holds = [], []
    for qid, peer in peers.items():
        if peer.decision == 'accept':
            agreed[primary[qid].decision] += 1
        elif qid not in adjudications:
            proposed = peer.correction.decision if peer.correction else peer.decision
            if proposed != primary[qid].decision or proposed == 'pass':
                adjudication.append(qid)
    for qid, item in primary.items():
        if qid in adjudications:
            adjudicated = adjudications[qid]
            if adjudicated.decision != 'pass':
                continue
            item = adjudicated.finding
        if item.decision != 'pass':
            continue
        source = sources[qid]['question']
        kind = source.get('kind')
        choice = {'single_choice', 'multiple_choice'}
        reasons = []
        if ((kind in choice and item.response_format != kind)
                or (kind not in choice and item.response_format in choice)):
            reasons.append('作答形式与来源类型冲突，需要修订草稿')
        if source.get('has_missing_assets'):
            reasons.append('来源带缺图标志，需要核实材料')
        if reasons:
            integration_holds.append({'question_id': qid, 'reasons': reasons})

    for shard in shards:
        ids = shard.pop('ids')
        shard.update(
            primary_done=sum(qid in primary for qid in ids),
            peer_done=sum(qid in peers for qid in ids),
            primary_remaining=[qid for qid in ids if qid not in primary],
            peer_remaining=[qid for qid in ids if qid not in peers],
            peer_available=[qid for qid in ids if qid in primary and qid not in peers],
        )
    return {
        'total': manifest['total'], 'model': manifest['model'],
        'base_revision': manifest['base_revision'], 'human_reviewed': False,
        'primary_done': len(primary), 'peer_done': len(peers),
        'primary_decisions': dict(primary_counts), 'peer_decisions': dict(peer_counts),
        'agreed_decisions': dict(agreed), 'adjudication_required': adjudication,
        'adjudication_done': len(adjudications),
        'integration_holds': integration_holds,
        'all_reviews_complete': len(primary) == len(peers) == len(sources),
        'writes_bank': False, 'bank_application_status': 'not_checked',
        'file_sha256': hashes, 'shards': shards,
        'reviewer_models': reviewer_models,
    }
