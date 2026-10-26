"""Freeze the locally audited senior bank; does not deploy or publish remotely."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.senior_bank import validate_peer, batch_files, BASE_RELEASE_FILES, FOUNDATION_RELEASE_FILES
from scripts.audit_senior_bank import audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-foundations',action='store_true')
    args=parser.parse_args()
    data = ROOT / 'app/data'
    existing=data/'senior_release.json'
    if (existing.exists() and json.loads(existing.read_text()).get('schema_version')==2
            and not args.include_foundations):
        raise SystemExit('已有基础题发布清单，请使用 --include-foundations，避免降级冻结范围。')
    coverage = audit(args.include_foundations)
    if not coverage['complete']:
        raise SystemExit('教材覆盖或独立复核未通过，拒绝冻结发布。')
    for filename,peerfile in batch_files(args.include_foundations):
        peer=json.loads((data/peerfile).read_text())
        validate_peer(json.loads((data/filename).read_text()),peer)
    names=sorted(BASE_RELEASE_FILES | (FOUNDATION_RELEASE_FILES if args.include_foundations else set()))
    release = {'schema_version': 2 if args.include_foundations else 1, 'ready_for_import': True,
               'files': {n: hashlib.sha256((data / n).read_bytes()).hexdigest() for n in names},
               'selected': sum(b['selected'] for b in coverage['books']),
               'chapters': sum(len(b['units']) for b in coverage['books']),
               'review': 'Two Luna item reviews; not teacher certification.'}
    if args.include_foundations:
        f=coverage['foundations']
        release['foundations']={'questions':f['selected'],'skills':len(f['skills']),
                               'goals':len(f['goals'])}
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=data,
                prefix='senior_release.', suffix='.tmp', delete=False) as stream:
            temp = Path(stream.name)
            json.dump(release, stream, ensure_ascii=False, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        temp.replace(data / 'senior_release.json')
    finally:
        if temp and temp.exists(): temp.unlink()
    print(json.dumps({'ready_for_import': True, 'selected': release['selected'],
                      'chapters': release['chapters']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
