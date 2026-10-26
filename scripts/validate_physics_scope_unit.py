#!/usr/bin/env python3
"""Validate one physics scope primary/peer unit against frozen inputs and catalog."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.physics_scope_review import validate_finding, validate_peer  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--shard', choices=list('abc'), required=True)
    parser.add_argument('--unit', required=True, help='three-digit unit, e.g. 050')
    parser.add_argument('--round', choices=['primary', 'peer'], required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    unit = args.unit.zfill(3)
    manifest = json.loads((root / 'manifest.json').read_text())
    catalog = json.loads((root / 'catalog.json').read_text())
    plan = json.loads((root / 'run-plan.json').read_text()) if (root / 'run-plan.json').exists() else {}
    rows = [json.loads(line) for line in (root / f'input-{args.shard}.jsonl').read_text().splitlines() if line.strip()]
    start = int(unit) * 10
    sources = rows[start:start + 10]
    if not sources:
        raise SystemExit(f'unit {args.shard}:{unit} is outside input-{args.shard}')
    key = f'{args.shard}:{unit}'
    expected_reviewer = plan.get('primary_unit_reviewers', {}).get(
        key, plan.get('primary_reviewers', {}).get(args.shard, f'/root/physics_scope_{args.shard}'))
    expected_model = plan.get('primary_unit_models', {}).get(
        key, plan.get('primary_models', {}).get(args.shard, plan.get('review_model', 'gpt-6-luna')))
    primary_path = root / f'primary-{args.shard}' / f'{unit}.jsonl'
    if not primary_path.exists():
        raise SystemExit(f'missing primary output: {primary_path}')
    primary_records = [json.loads(line) for line in primary_path.read_text().splitlines() if line.strip()]
    if len(primary_records) != len(sources):
        raise SystemExit(f'{primary_path}: expected {len(sources)} lines, got {len(primary_records)}')
    primary = []
    counts = {}
    for raw, source in zip(primary_records, sources):
        item = validate_finding(raw, source, catalog)
        if item.reviewer != expected_reviewer or item.model != expected_model:
            raise SystemExit(f'{item.question_id}: reviewer/model mismatch, expected {expected_reviewer}/{expected_model}')
        primary.append(item)
        counts[item.decision] = counts.get(item.decision, 0) + 1

    if args.round == 'peer':
        path = root / f'peer-{args.shard}' / f'{unit}.jsonl'
        if not path.exists():
            raise SystemExit(f'missing output: {path}')
        records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if len(records) != len(sources):
            raise SystemExit(f'{path}: expected {len(sources)} lines, got {len(records)}')
        expected_peer_reviewer = plan.get('peer_unit_reviewers', {}).get(key)
        expected_peer_model = plan.get('peer_unit_models', {}).get(
            key, plan.get('peer_models', {}).get(args.shard, plan.get('review_model', 'gpt-6-luna')))
        if expected_peer_reviewer is None:
            raise SystemExit('run-plan has no peer reviewer for ' + key)
        peer_counts = {}
        for raw, source, first in zip(records, sources, primary):
            peer = validate_peer(raw, first, source, catalog, expected_model=expected_peer_model)
            if peer.reviewer != expected_peer_reviewer:
                raise SystemExit(f'{peer.question_id}: peer reviewer mismatch, expected {expected_peer_reviewer}')
            peer_counts[peer.decision] = peer_counts.get(peer.decision, 0) + 1
        counts = {'primary_' + k: v for k, v in counts.items()} | {'peer_' + k: v for k, v in peer_counts.items()}
    print(json.dumps({'unit': key, 'round': args.round, 'questions': len(primary), 'counts': counts}, ensure_ascii=False))


if __name__ == '__main__':
    main()
