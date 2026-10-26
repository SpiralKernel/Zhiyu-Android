#!/usr/bin/env python3
"""Organize junior math full review into per-agent work units and merge results.

Workflow (see docs/junior-math-review-20261016.md):
  1. make --round primary        create small unit inputs from input-*.jsonl
  2. reviewers write <unit>.out.jsonl for their unit
  3. collect --round primary     validate units and write primary-<shard>.jsonl
  4. make --round peer / collect --round peer
  5. adjudication-plan / collect-adjudications for disagreements
  6. scripts/check_math_full_review.py validates the complete batch

Every command is read-only on the database and never rewrites reviewer output.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.math_full_review import Adjudication, Finding, PeerFinding, record_hash  # noqa: E402

PER_UNIT = 16

QUESTION_KEYS = ('id', 'subject', 'stage', 'grade', 'term', 'stem', 'options', 'answer', 'kind', 'steps',
                 'difficulty', 'difficulty_raw', 'knowledge_tags', 'type_tags', 'derived_type_tags',
                 'derived_knowledge_tags', 'fine_type_annotations', 'tags_source', 'source_tags',
                 'has_missing_assets', 'issues', 'status', 'can_practice', 'answer_mode', 'provenance', 'annotation')
ANNOTATION_KEYS = ('response_format', 'knowledge', 'fine_types', 'difficulty', 'curriculum', 'answer_spec', 'parts', 'grading', 'review')
PART_KEYS = ('id', 'prompt', 'reference_answer', 'solution_steps', 'knowledge_tags', 'type_tags', 'depends_on')


def reviewer_payload(question):
    """Content-relevant lens of the pinned snapshot; canonical hashes stay bound to the full record."""
    value = {key: question.get(key) for key in QUESTION_KEYS if key in question}
    annotation = value.get('annotation')
    if annotation:
        annotation = {key: annotation.get(key) for key in ANNOTATION_KEYS if key in annotation}
        annotation['parts'] = [{key: part.get(key) for key in PART_KEYS if key in part} for part in annotation.get('parts', [])]
        value['annotation'] = annotation
    return value


def load_jsonl(path):
    rows = []
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            raise SystemExit(f'{path}:{number}: 空行')
        rows.append(json.loads(line))
    return rows


def write_atomic(path, rows, model=None):
    text = ''.join(json.dumps(row.model_dump() if model else row, ensure_ascii=False, separators=(',', ':')) + '\n' for row in rows)
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(text)
    tmp.replace(path)


def shard_inputs(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    shards = []
    for number, expected in enumerate(manifest['shards']):
        rows = load_jsonl(directory / f'input-{number}.jsonl')
        if len(rows) != expected:
            raise SystemExit(f'input-{number}.jsonl 题数与 manifest 不符')
        shards.append(rows)
    if sum(manifest['shards']) != manifest['total']:
        raise SystemExit('manifest 题数不一致')
    return manifest, shards


def unit_layout(shards, per_unit=PER_UNIT):
    layout = defaultdict(list)
    for number, rows in enumerate(shards):
        for start in range(0, len(rows), per_unit):
            name = f'shard-{number:02d}-unit-{start // per_unit:03d}.jsonl'
            layout[number].append((name, rows[start:start + per_unit]))
    return layout


def round_model(round_name):
    return {'primary': Finding, 'peer': PeerFinding, 'adjudication': Adjudication}[round_name]


def make_units(args):
    directory = args.directory.resolve()
    manifest, shards = shard_inputs(directory)
    layout = unit_layout(shards)
    canonical = {}
    if args.round == 'peer':
        for number in layout:
            path = directory / f'primary-{number}.jsonl'
            if path.exists():
                for row in load_jsonl(path):
                    canonical[row['question_id']] = row
    units_dir = directory / 'units' / args.round
    units_dir.mkdir(parents=True, exist_ok=True)
    created = skipped = waiting = 0
    for number, units in layout.items():
        for name, rows in units:
            path = units_dir / name
            if path.exists():
                skipped += 1
                continue
            lines = []
            skip_unit = False
            for row in rows:
                if args.round == 'peer':
                    primary = canonical.get(row['question_id'])
                    if primary is None:
                        skip_unit = True
                        continue
                    lines.append({'question_id': row['question_id'], 'source_sha256': row['source_sha256'],
                                  'question': reviewer_payload(row['question']), 'primary': primary})
                else:
                    lines.append({**row, 'question': reviewer_payload(row['question'])})
            if skip_unit:
                waiting += 1
                continue
            write_atomic(path, lines)
            created += 1
    print(json.dumps({'round': args.round, 'created': created, 'already_existing': skipped,
                      'waiting_for_primary': waiting, 'units_dir': str(units_dir)}, ensure_ascii=False))


def collect(args):
    directory = args.directory.resolve()
    manifest, shards = shard_inputs(directory)
    layout = unit_layout(shards)
    units_dir = directory / 'units' / args.round
    model = round_model(args.round if args.round != 'adjudication' else 'adjudication')
    errors, done_units, collected = [], [], {}
    for number, units in layout.items():
        for name, rows in units:
            unit_path = units_dir / name
            if not unit_path.exists():
                continue
            out_path = units_dir / (name + '.out.jsonl')
            if not out_path.exists():
                continue
            expected_ids = [row['question_id'] for row in rows]
            seen = {}
            unit_ok = True
            try:
                out_rows = load_jsonl(out_path)
            except Exception as exc:
                errors.append(f'{out_path.name}: JSON 读取失败：{exc}')
                continue
            for line_number, raw in enumerate(out_rows, 1):
                try:
                    item = model.model_validate(raw)
                except Exception as exc:
                    errors.append(f'{out_path.name}:{line_number}: 结构无效：{exc}')
                    unit_ok = False
                    continue
                if item.question_id not in expected_ids:
                    errors.append(f'{out_path.name}:{line_number}: 题号不在单元内：{item.question_id}')
                    unit_ok = False
                    continue
                if item.question_id in seen:
                    errors.append(f'{out_path.name}:{line_number}: 题号重复：{item.question_id}')
                    unit_ok = False
                    continue
                source = next(row for row in rows if row['question_id'] == item.question_id)
                if item.source_sha256 != source['source_sha256']:
                    errors.append(f'{out_path.name}:{line_number}: 来源哈希不符：{item.question_id}')
                    unit_ok = False
                    continue
                seen[item.question_id] = item
            missing = [qid for qid in expected_ids if qid not in seen]
            if missing:
                errors.append(f'{out_path.name}: 缺少 {len(missing)} 题：{missing[:5]}')
                unit_ok = False
            if not unit_ok:
                continue
            done_units.append(name)
            collected.setdefault(number, []).extend((qid, seen[qid]) for qid in expected_ids)
    # Peer records must not precede their primary counterpart.
    if args.round == 'peer':
        for number in collected:
            primary_path = directory / f'primary-{number}.jsonl'
            primary_ids = {row['question_id'] for row in load_jsonl(primary_path)} if primary_path.exists() else set()
            collected[number] = [(qid, item) for qid, item in collected[number] if qid in primary_ids]
    for number, pairs in collected.items():
        rows = [item for _, item in pairs]
        write_atomic(directory / f'{args.round}-{number}.jsonl', rows, model=model)
    total_done = sum(len(pairs) for pairs in collected.values())
    total_expected = manifest['total']
    remaining_units = [name for number, units in layout.items() for name, _ in units
                       if name not in done_units and (units_dir / name).exists()]
    result = {'round': args.round, 'units_done': len(done_units), 'questions_collected': total_done,
              'questions_expected': total_expected, 'errors': errors,
              'next_units': remaining_units[:8], 'remaining_units': len(remaining_units)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        sys.exit(1)


def adjudication_plan(args):
    from app.math_full_review import inspect_batch
    directory = args.directory.resolve()
    report = inspect_batch(directory)
    incomplete = not report['all_reviews_complete']
    def load_optional(path):
        return load_jsonl(path) if path.exists() else []
    primary = {}
    for number in range(len(report['shards'])):
        for row in load_optional(directory / f'primary-{number}.jsonl'):
            primary[row['question_id']] = row
    peers = {}
    for number in range(len(report['shards'])):
        for row in load_optional(directory / f'peer-{number}.jsonl'):
            peers[row['question_id']] = row
    inputs = {}
    for number in range(len(report['shards'])):
        for row in load_optional(directory / f'input-{number}.jsonl'):
            inputs[row['question_id']] = row
    units_dir = directory / 'units' / 'adjudication'
    units_dir.mkdir(parents=True, exist_ok=True)
    created = skipped = 0
    for qid in report['adjudication_required']:
        name = f'dispute-{hashlib.sha1(qid.encode()).hexdigest()[:10]}.jsonl'
        path = units_dir / name
        if path.exists():
            skipped += 1
            continue
        row = inputs[qid]
        write_atomic(path, [{'question_id': qid, 'source_sha256': row['source_sha256'],
                             'question': row['question'], 'primary': primary[qid], 'peer': peers[qid]}])
        created += 1
    print(json.dumps({'adjudication_required': len(report['adjudication_required']),
                      'created': created, 'already_existing': skipped, 'incomplete_batch': incomplete,
                      'units_dir': str(units_dir)}, ensure_ascii=False))


def collect_adjudications(args):
    from app.math_full_review import inspect_batch
    directory = args.directory.resolve()
    units_dir = directory / 'units' / 'adjudication'
    primary, peers, sources = {}, {}, {}
    for path in sorted(directory.glob('input-*.jsonl')):
        for row in load_jsonl(path):
            sources[row['question_id']] = row
    for path in sorted(directory.glob('primary-*.jsonl')):
        for row in load_jsonl(path):
            primary[row['question_id']] = Finding.model_validate(row)
    for path in sorted(directory.glob('peer-*.jsonl')):
        for row in load_jsonl(path):
            peers[row['question_id']] = PeerFinding.model_validate(row)
    errors, records = [], []
    for path in sorted(units_dir.glob('*.out.jsonl')):
        for line_number, raw in enumerate(load_jsonl(path), 1):
            qid = raw.get('question_id')
            if qid not in primary or qid not in peers:
                errors.append(f'{path.name}:{line_number}: 缺少双轮记录：{qid}')
                continue
            raw.setdefault('reviewer', 'review-agent')
            raw['primary_record_sha256'] = record_hash(primary[qid].model_dump())
            raw['peer_record_sha256'] = record_hash(peers[qid].model_dump())
            try:
                records.append(Adjudication.model_validate(raw))
            except Exception as exc:
                errors.append(f'{path.name}:{line_number}: 结构无效：{exc}')
    # One adjudication per question; duplicates are an error.
    counts = Counter(item.question_id for item in records)
    duplicates = [qid for qid, count in counts.items() if count > 1]
    if duplicates:
        errors.append(f'裁定题号重复：{duplicates[:5]}')
        records = [item for item in records if counts[item.question_id] == 1]
    if records:
        existing = {}
        path = directory / 'adjudications.jsonl'
        if path.exists():
            for row in load_jsonl(path):
                item = Adjudication.model_validate(row)
                existing[item.question_id] = item
        for item in records:
            existing[item.question_id] = item
        ordered = [existing[qid] for qid in sources if qid in existing]
        write_atomic(path, ordered, model=Adjudication)
    print(json.dumps({'collected': len(records), 'errors': errors}, ensure_ascii=False, indent=2))
    if errors:
        sys.exit(1)


def status(args):
    directory = args.directory.resolve()
    manifest, shards = shard_inputs(directory)
    layout = unit_layout(shards)
    result = {'total': manifest['total']}
    for round_name in ('primary', 'peer', 'adjudication'):
        units_dir = directory / 'units' / round_name
        units = [name for units_ in layout.values() for name, _ in units_] if round_name != 'adjudication' else \
            [path.name for path in sorted(units_dir.glob('dispute-*.jsonl'))] if units_dir.exists() else []
        available = [name for name in units if (units_dir / name).exists()]
        done = [name for name in available if (units_dir / (name + '.out.jsonl')).exists()]
        canonical = sum(len(load_jsonl(path)) for path in sorted(directory.glob(f'{round_name}-*.jsonl'))) if round_name != 'adjudication' else \
            (len(load_jsonl(directory / 'adjudications.jsonl')) if (directory / 'adjudications.jsonl').exists() else 0)
        remaining = [name for name in available if name not in done]
        result[round_name] = {'units_total': len(units), 'units_available': len(available), 'units_done': len(done),
                              'canonical_rows': canonical, 'next_units': remaining[:6], 'remaining_units': len(remaining)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('command', choices=['make', 'collect', 'adjudication-plan', 'collect-adjudications', 'status'])
    parser.add_argument('--round', choices=['primary', 'peer'], default='primary')
    parser.add_argument('--per-unit', type=int, default=PER_UNIT)
    args = parser.parse_args()
    if args.command == 'make':
        make_units(args)
    elif args.command == 'collect':
        collect(args)
    elif args.command == 'adjudication-plan':
        adjudication_plan(args)
    elif args.command == 'collect-adjudications':
        collect_adjudications(args)
    else:
        status(args)


if __name__ == '__main__':
    main()
