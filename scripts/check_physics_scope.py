"""Read-only checkpoint for controlled junior physics scope review."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.physics_scope_review import inspect_batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--checkpoint', action='store_true')
    args = parser.parse_args()
    result = inspect_batch(args.directory)
    if args.checkpoint:
        temp = args.directory/'checkpoint.json.tmp'
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        temp.replace(args.directory/'checkpoint.json')
    print(json.dumps({k:v for k,v in result.items() if k != 'file_sha256'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
