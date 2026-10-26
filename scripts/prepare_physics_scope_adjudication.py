#!/usr/bin/env python3
"""Dump unresolved peer revisions as self-contained adjudication bundles."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.physics_scope_review import (  # noqa: E402
    ScopeAdjudication, record_hash, validate_finding, validate_peer,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.directory.resolve()
    manifest = json.loads((root / 'manifest.json').read_text())
    catalog = json.loads((root / 'catalog.json').read_text())
    plan = json.loads((root / 'run-plan.json').read_text())
    adjudicated = set()
    path = root / 'adjudications.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                adjudicated.add(ScopeAdjudication.model_validate_json(line).question_id)
    bundles = []
    for shard, size in manifest['shards'].items():
        sources = [json.loads(line) for line in (root / f'input-{shard}.jsonl').read_text().splitlines() if line.strip()]
        for unit_start in range(0, size, 10):
            unit = f'{unit_start // 10:03d}'
            primary_path = root / f'primary-{shard}' / f'{unit}.jsonl'
            peer_path = root / f'peer-{shard}' / f'{unit}.jsonl'
            if not primary_path.exists() or not peer_path.exists():
                continue
            primary = [json.loads(line) for line in primary_path.read_text().splitlines() if line.strip()]
            peers = [json.loads(line) for line in peer_path.read_text().splitlines() if line.strip()]
            unit_key = f'{shard}:{unit}'
            expected_peer_model = plan.get('peer_unit_models', {}).get(
                unit_key, plan.get('peer_models', {}).get(shard, plan.get('review_model', 'gpt-6-luna')))
            for raw_primary, raw_peer, source in zip(primary, peers, sources[unit_start:unit_start + 10]):
                first = validate_finding(raw_primary, source, catalog)
                peer = validate_peer(raw_peer, first, source, catalog,
                                     expected_model=expected_peer_model)
                if peer.decision != 'revise' or peer.question_id in adjudicated:
                    continue
                assert peer.correction is not None
                bundles.append({
                    'question_id': source['question_id'],
                    'shard': shard,
                    'unit': unit,
                    'snapshot_sha256': source['snapshot_sha256'],
                    'primary_record_sha256': record_hash(first.model_dump()),
                    'peer_record_sha256': record_hash(peer.model_dump()),
                    'source': source,
                    'primary': first.model_dump(),
                    'peer': peer.model_dump(),
                })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(b, ensure_ascii=False, separators=(',', ':')) + '\n' for b in bundles))
    print(json.dumps({'bundles': len(bundles), 'output': str(args.output), 'already_adjudicated': len(adjudicated)},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
