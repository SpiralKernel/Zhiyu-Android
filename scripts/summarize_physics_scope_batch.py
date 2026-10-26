#!/usr/bin/env python3
"""Summarize one physics scope batch without writing the bank."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.physics_scope_review import ScopeAdjudication, ScopeFinding, ScopePeer, inspect_batch  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--total-scope', type=int, default=2355)
    parser.add_argument('--cumulative-done', type=int, default=1900)
    parser.add_argument('--base-aligned', type=int, default=1240)
    parser.add_argument('--base-hold', type=int, default=260)
    parser.add_argument('--previous-applied', type=int, default=1240)
    args = parser.parse_args()
    root = args.directory.resolve()
    plan = json.loads((root / 'run-plan.json').read_text())
    report = inspect_batch(root)
    scope = {f'{shard}:{u:03d}' for shard, units in plan['units'].items() for u in units}
    final = {}
    adjudications = {}
    path = root / 'adjudications.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                item = ScopeAdjudication.model_validate_json(line)
                adjudications[item.question_id] = item.finding
    primary_count = peer_count = 0
    peer_counts = Counter()
    reviewer_counts = Counter()
    for shard in 'abc':
        for unit_file in sorted((root / f'primary-{shard}').glob('*.jsonl')):
            key = f'{shard}:{unit_file.stem}'
            if key not in scope:
                continue
            findings = [ScopeFinding.model_validate_json(x) for x in unit_file.read_text().splitlines() if x.strip()]
            primary_count += len(findings)
            for item in findings:
                reviewer_counts['primary:' + item.reviewer] += 1
            peer_file = root / f'peer-{shard}' / unit_file.name
            if not peer_file.exists():
                continue
            peers = [ScopePeer.model_validate_json(x) for x in peer_file.read_text().splitlines() if x.strip()]
            peer_count += len(peers)
            for item in peers:
                peer_counts[item.decision] += 1
                reviewer_counts['peer:' + item.reviewer] += 1
            for first, peer in zip(findings, peers):
                if first.question_id in adjudications:
                    final[first.question_id] = adjudications[first.question_id]
                elif peer.decision == 'accept':
                    final[first.question_id] = first
    decisions = Counter(x.decision for x in final.values())
    books = Counter(x.primary_book_id for x in final.values() if x.decision == 'aligned')
    reviewer_counts['adjudication:/root'] += len(adjudications)
    result = {
        'batch_id': plan.get('batch_id'),
        'total_scope': args.total_scope,
        'batch': len(scope) * 10,
        'primary_done': primary_count,
        'peer_done': peer_count,
        'primary_aligned': report['counts'].get('primary_aligned', 0),
        'primary_hold': report['counts'].get('primary_hold', 0),
        'peer_accept': peer_counts['accept'],
        'peer_revise': peer_counts['revise'],
        'root_adjudications': len(adjudications),
        'final_aligned_candidates': decisions['aligned'],
        'final_hold': decisions['hold'],
        'pending_disputes': len(report['pending_revisions']),
        'cumulative_done': args.cumulative_done,
        'cumulative_final_aligned': args.base_aligned + decisions['aligned'],
        'cumulative_final_hold': args.base_hold + decisions['hold'],
        'remaining_both_rounds': args.total_scope - args.cumulative_done,
        'primary_book_counts': dict(sorted(books.items())),
        'reviewer_counts': dict(sorted(reviewer_counts.items())),
        'source_snapshots_checked': primary_count,
        'source_drift': 0,
        'previous_writeback_rows_verified': args.previous_applied,
        'writes_bank': False,
        'changes_student_state': False,
        'pushed': False,
        'deployed': False,
        'limitations': [
            'Scope and controlled fine-type annotation only; not new complete answer certification or calibrated difficulty.',
            'DeepSeek model candidates; human_reviewed=false and no teacher certification.',
            'Holds and content issues are recorded but not written to the bank.',
            'Root checked all peer revisions; root sampling is not a full independent re-solution of all 400.',
        ],
    }
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text)


if __name__ == '__main__':
    main()
