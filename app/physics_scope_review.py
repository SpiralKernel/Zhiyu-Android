"""Source-pinned textbook-scope annotations; no bank or mastery writes."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import Field

from app.question_annotation import StrictModel

BOOK_ORDER = ['physics-8-1', 'physics-8-2', 'physics-9-1', 'physics-9-2']


def record_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


class ScopePart(StrictModel):
    index: int = Field(ge=1)
    type_ids: list[str] = Field(max_length=30)
    evidence_quote: str = Field(min_length=2, max_length=3000)
    basis: str = Field(min_length=4, max_length=3000)


class ScopeFinding(StrictModel):
    question_id: str
    snapshot_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    decision: Literal['aligned', 'hold']
    primary_book_id: Literal['physics-8-1', 'physics-8-2', 'physics-9-1', 'physics-9-2'] | None
    parts: list[ScopePart] = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=4, max_length=5000)
    issues: list[str] = Field(max_length=30)
    reviewer: str
    model: Literal['gpt-6-luna', 'opencode/deepseek-v4.1-flash-free', 'orchestrator']


class ScopePeer(StrictModel):
    question_id: str
    snapshot_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    primary_record_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    decision: Literal['accept', 'revise']
    reason: str = Field(min_length=4, max_length=5000)
    correction: ScopeFinding | None = None
    reviewer: str
    model: Literal['gpt-6-luna', 'opencode/deepseek-v4.1-flash-free']


class ScopeAdjudication(StrictModel):
    question_id: str
    snapshot_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    primary_record_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    peer_record_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: Literal['/root']
    model: Literal['orchestrator']
    reason: str = Field(min_length=4, max_length=5000)
    finding: ScopeFinding


def validate_finding(raw, source, catalog):
    item = ScopeFinding.model_validate(raw)
    if (item.question_id, item.snapshot_sha256) != (source['question_id'], source['snapshot_sha256']):
        raise ValueError('题号或来源快照哈希不匹配')
    parts = source['parts'] or [{'index':1, 'prompt':source['question']['stem']}]
    if [p.index for p in item.parts] != [p['index'] for p in parts]:
        raise ValueError('必须按原小问顺序完整覆盖，不能漏问或新增小问')
    books = set()
    for result, original in zip(item.parts, parts):
        if result.evidence_quote not in source['question']['stem'] and result.evidence_quote not in original['prompt']:
            raise ValueError('题干证据引文不属于本题或本小问')
        if len(result.type_ids) != len(set(result.type_ids)):
            raise ValueError('重复题型ID')
        if item.decision == 'aligned' and not result.type_ids:
            raise ValueError('通过归属的每问必须选择受控题型')
        for tid in result.type_ids:
            if tid not in catalog['types']:
                raise ValueError('未知或非固定题型ID：'+tid)
            books.add(catalog['types'][tid]['book_id'])
    if item.decision == 'aligned':
        if item.issues or item.primary_book_id is None:
            raise ValueError('通过归属不能同时存在未解决问题或缺少册次')
        if item.primary_book_id != max(books, key=BOOK_ORDER.index):
            raise ValueError('主学习阶段须为实际所需题型的最晚阶段')
    elif not item.issues:
        raise ValueError('留置必须记录具体问题')
    return item


def validate_peer(raw, primary, source, catalog, *, expected_model='gpt-6-luna'):
    peer = ScopePeer.model_validate(raw)
    if peer.question_id != source['question_id'] or peer.snapshot_sha256 != source['snapshot_sha256']:
        raise ValueError('复核来源不匹配')
    if peer.primary_record_sha256 != record_hash(primary.model_dump()):
        raise ValueError('复核未绑定当前初审内容')
    if peer.reviewer == primary.reviewer:
        raise ValueError('不能自行复核初审')
    if peer.model != expected_model:
        raise ValueError('复核模型归属不符')
    if (peer.decision == 'revise') != (peer.correction is not None):
        raise ValueError('修订必须有完整替代标注，接受不得附带修订')
    if peer.correction:
        corrected = validate_finding(peer.correction.model_dump(), source, catalog)
        if corrected.reviewer != peer.reviewer or corrected.model != peer.model:
            raise ValueError('修订作者必须是实际复核代理')
    return peer


def inspect_batch(directory):
    root = Path(directory)
    manifest = json.loads((root/'manifest.json').read_text())
    catalog_bytes = (root/'catalog.json').read_bytes()
    if hashlib.sha256(catalog_bytes).hexdigest() != manifest['catalog_sha256']:
        raise ValueError('受控标签库变化')
    catalog = json.loads(catalog_bytes)
    counts, pending, file_hashes = Counter(), [], {}
    file_hashes['manifest.json'] = hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()
    file_hashes['catalog.json'] = hashlib.sha256(catalog_bytes).hexdigest()
    plan_path = root/'run-plan.json'
    plan = json.loads(plan_path.read_text()) if plan_path.exists() else {}
    if plan_path.exists():
        file_hashes['run-plan.json'] = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    seen = set()
    reviewed = {}
    for shard, size in manifest['shards'].items():
        data = (root/f'input-{shard}.jsonl').read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest['input_sha256'][shard]:
            raise ValueError('冻结输入变化')
        file_hashes[f'input-{shard}.jsonl'] = hashlib.sha256(data).hexdigest()
        sources = [json.loads(line) for line in data.decode().splitlines()]
        if len(sources) != size:
            raise ValueError('输入题数不匹配')
        valid_units = {f'{i:03d}.jsonl' for i in range((size+9)//10)}
        for phase in ('primary', 'peer'):
            if any(p.name not in valid_units for p in (root/f'{phase}-{shard}').glob('*.jsonl')):
                raise ValueError('存在范围外的审核单元')
        for path in (root/f'peer-{shard}').glob('*.jsonl'):
            if not (root/f'primary-{shard}'/path.name).exists():
                raise ValueError('复核不能先于所绑定初审存在')
        for unit_start in range(0, size, 10):
            unit = f'{unit_start//10:03d}.jsonl'
            unit_key = f'{shard}:{Path(unit).stem}'
            expected_primary_reviewer = plan.get('primary_unit_reviewers', {}).get(
                unit_key, plan.get('primary_reviewers', {}).get(shard, f'/root/physics_scope_{shard}'))
            expected_primary_model = plan.get('primary_unit_models', {}).get(
                unit_key, plan.get('primary_models', {}).get(shard, plan.get('review_model', 'gpt-6-luna')))
            expected = sources[unit_start:unit_start+10]
            primary_path = root/f'primary-{shard}'/unit
            if not primary_path.exists():
                continue
            raw = primary_path.read_bytes()
            records = [json.loads(line) for line in raw.decode().splitlines()]
            if len(records) != len(expected):
                raise ValueError('初审单元题数不匹配：'+str(primary_path))
            file_hashes[str(primary_path.relative_to(root))] = hashlib.sha256(raw).hexdigest()
            primary = []
            for value, source in zip(records, expected):
                item = validate_finding(value, source, catalog)
                if (item.reviewer != expected_primary_reviewer or item.model != expected_primary_model
                        or item.question_id in seen):
                    raise ValueError('初审作者、模型或题号不符')
                seen.add(item.question_id)
                primary.append(item)
                counts['primary_done'] += 1
                counts['primary_'+item.decision] += 1
            peer_path = root/f'peer-{shard}'/unit
            if not peer_path.exists():
                continue
            raw = peer_path.read_bytes()
            records = [json.loads(line) for line in raw.decode().splitlines()]
            if len(records) != len(expected):
                raise ValueError('复核单元题数不匹配')
            file_hashes[str(peer_path.relative_to(root))] = hashlib.sha256(raw).hexdigest()
            expected_peer_reviewer = '/root/physics_scope_' + 'abc'[('abc'.index(shard)-1) % 3]
            expected_peer_reviewer = plan.get('peer_unit_reviewers', {}).get(unit_key, expected_peer_reviewer)
            expected_peer_model = plan.get('peer_unit_models', {}).get(
                unit_key, plan.get('peer_models', {}).get(shard, plan.get('review_model', 'gpt-6-luna')))
            for value, source, first in zip(records, expected, primary):
                peer = validate_peer(value, first, source, catalog, expected_model=expected_peer_model)
                if peer.reviewer != expected_peer_reviewer:
                    raise ValueError('复核实际代理归属不符')
                reviewed[peer.question_id] = (source, first, peer)
                counts['peer_done'] += 1
                counts['peer_'+peer.decision] += 1
                if peer.decision == 'revise':
                    pending.append(peer.question_id)
    adjudicated = {}
    adjudication_path = root/'adjudications.jsonl'
    if adjudication_path.exists():
        raw = adjudication_path.read_bytes()
        file_hashes['adjudications.jsonl'] = hashlib.sha256(raw).hexdigest()
        for line in raw.decode().splitlines():
            item = ScopeAdjudication.model_validate_json(line)
            if item.question_id in adjudicated or item.question_id not in reviewed:
                raise ValueError('裁定重复或未有完整两轮审核')
            source, first, peer = reviewed[item.question_id]
            if (item.snapshot_sha256 != source['snapshot_sha256']
                    or item.primary_record_sha256 != record_hash(first.model_dump())
                    or item.peer_record_sha256 != record_hash(peer.model_dump())):
                raise ValueError('裁定来源或两轮记录绑定过期')
            finding = validate_finding(item.finding.model_dump(), source, catalog)
            if finding.model == 'orchestrator' and finding.reviewer != '/root':
                raise ValueError('主任务修订归属错误')
            if finding.model != 'orchestrator' and finding.model_dump() not in [first.model_dump(),
                    peer.correction.model_dump() if peer.correction else None]:
                raise ValueError('不能将主任务新修订伪装为初审或复核原稿')
            adjudicated[item.question_id] = finding
    for qid, (_, first, peer) in reviewed.items():
        final = adjudicated.get(qid) or (first if peer.decision == 'accept' else None)
        if final:
            counts['final_'+final.decision] += 1
    pending = [qid for qid in pending if qid not in adjudicated]
    counts['adjudicated'] = len(adjudicated)
    return dict(total=manifest['total'], counts=dict(counts), pending_revisions=pending,
                primary_remaining=manifest['total']-counts['primary_done'],
                peer_remaining=manifest['total']-counts['peer_done'],
                file_sha256=file_hashes, writes_bank=False)
