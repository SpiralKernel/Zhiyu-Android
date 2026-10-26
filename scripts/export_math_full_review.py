#!/usr/bin/env python3
"""Export current playable junior math snapshots for dual-round AI review.

Pins every question by source fingerprint and full snapshot hash. Refuses to
overwrite an existing export so earlier review evidence stays reproducible.
Run from the repository root:

    .venv/bin/python scripts/export_math_full_review.py --directory data/annotations/math-full-20261016
"""
import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings  # noqa: E402
from app.db import connect  # noqa: E402
from app.math_full_import import REVIEW_MODEL  # noqa: E402
from app.physics_review import snapshot_hash  # noqa: E402
from app.question_annotation import source_fingerprint  # noqa: E402

SHARDS = 5
SELECTION = """
SELECT id, source_id, status, data FROM bank_questions
WHERE subject='math' AND stage='junior' AND status IN ('ready','reference')
  AND json_extract(data,'$.can_practice')=1
  AND COALESCE(json_extract(data,'$.annotation.review.answer_status'),'') != 'checked'
  AND COALESCE(json_extract(data,'$.provenance.kind'),'') != 'original_rule_core'
  AND COALESCE(json_extract(data,'$.provenance.teacher_reviewed'),0) != 1
  AND json_extract(data,'$.quality.model_review') IS NULL
ORDER BY id
"""


def base_revision():
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return 'unknown'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory if args.directory.is_absolute() else ROOT / args.directory

    if directory.exists() and any(directory.glob('input-*.jsonl')):
        raise SystemExit('导出目录已存在输入分片，禁止覆盖；请使用新目录，避免覆盖本次审查依据。')

    settings = Settings()
    entries = []
    with connect(settings.database_path) as db:
        for row in db.execute(SELECTION):
            q = json.loads(row['data'])
            qid = q.get('annotation_source_question_id') or q['id']
            if qid != row['id'] and row['id'].rsplit(':', 1)[0] != qid:
                raise SystemExit(f'快照 ID 与来源题号不一致：{qid} / {row["id"]}')
            entries.append({
                'question_id': qid,
                'source_sha256': source_fingerprint({**q, 'id': qid}),
                'current_snapshot_id': row['id'],
                'current_sha256': snapshot_hash(q),
                'question': q,
            })
    ids = [entry['question_id'] for entry in entries]
    if len(ids) != len(set(ids)):
        raise SystemExit('导出题号重复，拒绝导出')

    total = len(entries)
    size, remainder = divmod(total, SHARDS)
    sizes = [size + (1 if index < remainder else 0) for index in range(SHARDS)]
    kinds = Counter(entry['question']['kind'] for entry in entries)
    directory.mkdir(parents=True, exist_ok=True)
    position = 0
    for shard, expected in enumerate(sizes):
        chunk = entries[position:position + expected]
        position += expected
        with (directory / f'input-{shard}.jsonl').open('w') as stream:
            for entry in chunk:
                stream.write(json.dumps(entry, ensure_ascii=False, separators=(',', ':')) + '\n')
    manifest = {
        'total': total, 'shards': sizes, 'kinds': dict(kinds),
        'base_revision': base_revision(),
        'scope': '当前可练习初中数学题；已排除既有独立核验题（规则核心/精选）与已检查答案题',
        'model': REVIEW_MODEL, 'human_reviewed': False,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'selection': ' '.join(SELECTION.split()),
    }
    (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'directory': str(directory), **manifest}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
