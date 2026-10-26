"""Validate cumulative physics scope evidence; --apply creates a SQLite backup first."""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import connect
from app.physics_scope_writeback import apply_scope, resolved_findings


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    p.add_argument('--db', type=Path, default=Path('data/ai-teacher.sqlite3'))
    p.add_argument('--expected-reviewed', type=int, required=True)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    _, _, findings, _ = resolved_findings(args.directory)
    if len(findings) != args.expected_reviewed:
        raise ValueError('双轮完成数不符，拒绝应用')
    backup = None
    if args.apply:
        backup = args.output.parent / ('before-scope-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.sqlite3')
        backup.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True) as src:
            with sqlite3.connect(backup) as dst:
                src.backup(dst)
        backup.chmod(0o600)
    with connect(args.db) as db:
        result = apply_scope(db, args.directory, dry_run=not args.apply)
    result['backup'] = str(backup.resolve()) if backup else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'questions'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
