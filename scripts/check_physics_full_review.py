"""Read-only review validation. Optional checkpoint contains no student data."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.physics_full_review import inspect_batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--checkpoint', type=Path, help='保存已校验的统计、文件哈希及待审题号')
    args = parser.parse_args()
    result = inspect_batch(args.directory)
    result['validated_at'] = datetime.now(timezone.utc).isoformat()
    if args.checkpoint:
        # A checkpoint must not overwrite an input or model's evidence file.
        protected = {p.resolve() for p in args.directory.iterdir() if p.name != 'checkpoint.json'}
        if args.checkpoint.resolve() in protected:
            parser.error('断点路径不可覆盖审核输入或原始结果')
        tmp = args.checkpoint.with_name(args.checkpoint.name + '.tmp')
        protected.add(args.checkpoint.resolve())
        if tmp.resolve() in protected:
            parser.error('断点临时路径不可覆盖审核输入或原始结果')
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        tmp.replace(args.checkpoint)
    summary = {k: v for k, v in result.items() if k not in {'file_sha256', 'shards', 'adjudication_required', 'integration_holds'}}
    summary['adjudication_required'] = len(result['adjudication_required'])
    summary['integration_holds'] = len(result['integration_holds'])
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
