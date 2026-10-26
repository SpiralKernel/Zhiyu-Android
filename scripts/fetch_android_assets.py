"""Fetch pinned public build inputs; never fetch an account DB or a signing secret."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.mobile_content import MAX_BYTES, verify_manifest

RELEASE = 'https://github.com/SpiralKernel/Zhiyu-Android/releases/download/v0.8.1/'


def prepare(source=None):
    def read(name, limit):
        if source:
            path = source / name
            if path.stat().st_size > limit:
                raise ValueError('Build input is too large: ' + name)
            return path.read_bytes()
        import httpx
        with httpx.Client(timeout=90, follow_redirects=True) as client:
            with client.stream('GET', RELEASE + name) as response:
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > limit:
                        raise ValueError('Build input is too large: ' + name)
                    chunks.append(chunk)
                return b''.join(chunks)

    manifest_raw = read('manifest.json', 8192)
    manifest = json.loads(manifest_raw)
    expected = verify_manifest(manifest)
    name = f"bank-{expected['version']}.jsonl.gz"
    bank = read(name, MAX_BYTES)
    if hashlib.sha256(bank).hexdigest() != expected['sha256']:
        raise ValueError('Question bank SHA256 mismatch')
    # Verify every input before replacing the build cache.
    wheels = []
    for item in json.loads((ROOT / 'android/wheels/checksums.json').read_text()):
        raw = read(item['name'], 32 * 1024 * 1024)
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Native wheel SHA256 mismatch: ' + item['name'])
        wheels.append((item['name'], raw))
    seed = ROOT / 'output/android/seed'
    seed.mkdir(parents=True, exist_ok=True)
    (seed / name).write_bytes(bank)
    (seed / 'manifest.json').write_bytes(manifest_raw)
    for filename, raw in wheels:
        (ROOT / 'android/wheels' / filename).write_bytes(raw)
    print(f'Verified bank {expected["version"]}: {expected["count"]} questions; {len(wheels)} Android wheels')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, help='Use previously downloaded release attachments instead of network')
    prepare(parser.parse_args().source_dir)
