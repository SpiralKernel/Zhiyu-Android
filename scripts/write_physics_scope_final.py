#!/usr/bin/env python3
"""Write final physics-scope evidence, holds, and checkpoint without touching the bank."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.physics_scope_writeback import resolved_findings  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    catalog, sources, findings, report = resolved_findings(root)
    plan = json.loads((root / 'run-plan.json').read_text())
    order = []
    for shard, units in plan['units'].items():
        for unit in units:
            path = root / f'units/{shard}/{unit:03d}.jsonl'
            order.extend(json.loads(line)['question_id'] for line in path.read_text().splitlines() if line.strip())
    if len(order) != len(set(order)) or set(order) != set(findings):
        raise SystemExit('final question set does not match the 400-unit plan')
    catalog_sha = report['file_sha256']['catalog.json']
    final = []
    gaps = []
    for qid in order:
        finding = findings[qid]
        item = {
            'question_id': qid,
            'snapshot_sha256': sources[qid]['snapshot_sha256'],
            'catalog_sha256': catalog_sha,
            'scope_status': 'model_reviewed_candidate' if finding.decision == 'aligned' else 'hold',
            'finding': finding.model_dump(),
        }
        final.append(item)
        if finding.decision == 'hold':
            gaps.append({
                'question_id': qid,
                'snapshot_sha256': sources[qid]['snapshot_sha256'],
                'primary_book_id': finding.primary_book_id,
                'reason': finding.reason,
                'issues': finding.issues,
                'parts': [part.model_dump() for part in finding.parts],
            })
    (root / 'final.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False, separators=(',', ':')) + '\n' for x in final))
    (root / 'catalog-gaps.json').write_text(json.dumps(gaps, ensure_ascii=False, indent=2) + '\n')
    (root / 'checkpoint.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'final': len(final), 'aligned': sum(x['finding']['decision'] == 'aligned' for x in final),
                      'hold': len(gaps), 'catalog_sha256': catalog_sha}, ensure_ascii=False))


if __name__ == '__main__':
    main()
