#!/usr/bin/env python3
"""Self-check one review unit before finishing. Never mutates the files.

    .venv/bin/python scripts/validate_math_findings.py \
        --unit data/annotations/math-full-20261016/units/primary/shard-00-unit-000.jsonl \
        --output <同目录 .out.jsonl> --round primary

Prints per-decision counts and exits 0 only when every line is valid, every
unit question is covered exactly once, and every source hash matches.

裁定单元：--round adjudication；primary/peer 记录哈希由本脚本按争议单元
现场注入（与 collect-adjudications 行为一致），审核员输出无需自带这两个字段。
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.math_full_review import Adjudication, Finding, PeerFinding, record_hash  # noqa: E402

MODELS = {'primary': Finding, 'peer': PeerFinding, 'adjudication': Adjudication}
DISPUTE_DECISIONS = {'pass', 'exclude', 'unresolved'}


def validate_candidate(item, unit_row, question=None):
    """Check the proposed passing annotation, including an accepted primary."""
    from app.math_full_import import annotation_for

    candidate = item
    if isinstance(item, PeerFinding):
        candidate = (Finding.model_validate(unit_row['primary']) if item.decision == 'accept'
                     else item.correction if item.decision == 'revise' else None)
    elif isinstance(item, Adjudication):
        candidate = item.finding
    if candidate is None or candidate.decision != 'pass':
        return
    generic = {'运算能力', '分析和解决问题能力', '综合', '数与式', '选择题', '单选题', '填空题'}
    labels = candidate.knowledge.primary + candidate.fine_types
    for part in candidate.parts:
        labels += part.knowledge + part.fine_types
    if any(label.strip() in generic for label in labels):
        raise ValueError('知识/细题型仍含能力词或泛标签，须按题目实际任务修订')
    annotation_for(candidate, question or unit_row['question'], 'math-full-review-validation')


def load(path):
    rows = []
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            raise ValueError(f'第 {number} 行为空行')
        try:
            rows.append(json.loads(line))
        except ValueError as exc:
            raise ValueError(f'第 {number} 行不是合法 JSON：{exc}')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--round', choices=['primary', 'peer', 'adjudication'], default='primary')
    parser.add_argument('--strict-annotation', action='store_true',
                        help='同时检查拟通过的完整标注；复核accept也检查其初审标注')
    args = parser.parse_args()
    model = MODELS[args.round]
    errors = []
    try:
        unit_rows = load(args.unit)
    except ValueError as exc:
        print(f'单元输入无法读取：{exc}')
        return 2
    try:
        out_rows = load(args.output)
    except ValueError as exc:
        print(f'输出文件无法读取：{exc}')
        return 2
    expected = {}
    unit_by_id = {row['question_id']: row for row in unit_rows}
    source_questions = {}
    match = re.match(r'shard-(\d+)-unit-', args.unit.name)
    if args.strict_annotation and match:
        source_path = args.unit.resolve().parents[2] / f'input-{int(match[1])}.jsonl'
        if source_path.exists():
            source_questions = {row['question_id']: row['question'] for row in load(source_path)}
    for row in unit_rows:
        expected[row['question_id']] = row.get('source_sha256')
    seen = {}
    decisions = Counter()
    for number, raw in enumerate(out_rows, 1):
        if args.round == 'adjudication' and isinstance(raw, dict):
            row = unit_by_id.get(raw.get('question_id'))
            if not row or 'primary' not in row or 'peer' not in row:
                errors.append(f'第 {number} 行：争议单元里找不到该题的 primary/peer 记录：{raw.get("question_id")}')
                continue
            raw.setdefault('reviewer', 'review-agent')
            raw['primary_record_sha256'] = record_hash(Finding.model_validate(row['primary']).model_dump())
            raw['peer_record_sha256'] = record_hash(PeerFinding.model_validate(row['peer']).model_dump())
        try:
            item = model.model_validate(raw)
        except Exception as exc:
            errors.append(f'第 {number} 行结构无效：{exc}')
            continue
        if item.question_id not in expected:
            errors.append(f'第 {number} 行题号不在单元内：{item.question_id}')
            continue
        if item.question_id in seen:
            errors.append(f'第 {number} 行题号重复：{item.question_id}')
            continue
        if item.source_sha256 != expected[item.question_id]:
            errors.append(f'第 {number} 行来源哈希与单元输入不符：{item.question_id}')
            continue
        seen[item.question_id] = item
        decisions[item.decision] += 1
        if args.strict_annotation:
            try:
                validate_candidate(item, unit_by_id[item.question_id],
                                   source_questions.get(item.question_id))
            except Exception as exc:
                errors.append(f'第 {number} 行通过标注不可入库：{item.question_id}：{exc}')
    for qid in expected:
        if qid not in seen:
            errors.append(f'缺少题目记录：{qid}')
    if errors:
        print('\n'.join(errors))
        print(f'\n未通过：{len(errors)} 处问题，已覆盖 {len(seen)}/{len(expected)} 题')
        return 1
    print(f'OK：{len(seen)} 题全部有效，决定分布 {dict(decisions)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
