"""Stage an immutable, hash-verified QwenW snapshot without executing its code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from gerald.qwenw import PACK, PROFILES, safe_path


def stage(source):
    source = Path(source).absolute()
    if not source.is_dir() or source.is_symlink() or source.is_junction():
        raise ValueError('Source must be a regular directory, not a link')
    if PACK.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(PACK.resolve()):
        raise ValueError('Source and managed import must be separate')
    if PACK.exists():
        raise ValueError('Managed snapshot already exists; it is immutable. Use --install to reuse it.')
    records, directories = [], []
    for folder, dirs, files in os.walk(source, followlinks=False):
        for name in dirs:
            path = Path(folder) / name
            if path.is_symlink() or path.is_junction():
                raise ValueError('Linked directories are not imported')
            directories.append(path.relative_to(source).as_posix())
        for name in files:
            path = Path(folder) / name
            if path.is_symlink() or path.is_junction() or path.stat().st_size > 1048576:
                raise ValueError('Linked/oversized files are not imported')
            records.append((path.relative_to(source).as_posix(), path.read_bytes()))
    if len(records) > 256 or sum(len(data) for _, data in records) > 16777216:
        raise ValueError('Import exceeds 256 files / 16 MiB')
    paths = {path for path, _ in records}
    for profile in PROFILES:
        if f'agents/{profile}.md' not in paths:
            raise ValueError(f'Missing required profile {profile}')
    # Validate every destination before copying anything. Originals are untouched.
    for relative, _ in records:
        safe_path(PACK / 'source', relative)
    for relative in directories:
        safe_path(PACK / 'source', relative)
    for relative in directories:
        safe_path(PACK / 'source', relative).mkdir(parents=True, exist_ok=True)
    for relative, data in records:
        target = safe_path(PACK / 'source', relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
    manifest = {'version': 1, 'source': str(source), 'staged_at': time.time(), 'directories': directories,
        'files': [{'path': p, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for p, data in records]}
    (PACK / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return {'staged_files': len(records), 'destination': str(PACK), 'originals_preserved': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--install', action='store_true', help='Register staged profiles with the running dashboard')
    parser.add_argument('--url', default='http://127.0.0.1:8765')
    args = parser.parse_args()
    if not args.source and not args.install:
        parser.error('Specify --source and/or --install')
    if args.source:
        print(json.dumps(stage(args.source), indent=2))
    if args.install:
        import httpx
        with httpx.Client(timeout=30, trust_env=False) as client:
            response = client.post(args.url.rstrip('/') + '/api/packs/qwenw/install')
            response.raise_for_status()
            data = response.json()
            print(json.dumps({'created': data['created'], 'profiles': data['profiles'], 'revision': data['revision']}, indent=2))


if __name__ == '__main__':
    main()
