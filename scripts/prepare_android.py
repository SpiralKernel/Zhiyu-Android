"""Stage runtime, UI and a verified public seed, without any private runtime data."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.mobile_content import MAX_BYTES, verify_manifest


def prepare(seed_dir=None):
    seed_dir = seed_dir or ROOT / 'output/android/seed'
    manifest_raw = (seed_dir / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    expected = verify_manifest(manifest)
    raw = (seed_dir / f"bank-{expected['version']}.jsonl.gz").read_bytes()
    if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != expected['sha256']:
        raise ValueError('Question bank SHA256 mismatch')
    generated = ROOT / 'android/generated'
    app = generated / 'python/app'
    if app.exists():
        shutil.rmtree(app)
    shutil.copytree(ROOT / 'app', app, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    assets = generated / 'assets/runtime'
    web = assets / 'web'
    if web.exists():
        shutil.rmtree(web)
    shutil.copytree(ROOT / 'web', web)
    seed = assets / 'seed'
    if seed.exists():
        shutil.rmtree(seed)
    seed.mkdir(parents=True)
    (seed / 'manifest.json').write_bytes(manifest_raw)
    # AAPT transparently expands .gz assets; .bank preserves the signed gzip bytes.
    (seed / f"bank-{expected['version']}.bank").write_bytes(raw)
    print(f'Staged {expected["count"]} offline questions; no .env, account DB, private keys or uploads')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-dir', type=Path)
    prepare(parser.parse_args().seed_dir)
