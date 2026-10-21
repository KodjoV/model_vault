#!/usr/bin/env python3
"""Pinned, resumable UGREEN NAS downloads for Unsloth Flash-Next GGUF variants.

  python3 download-flash-next-quants.py --plan
  python3 download-flash-next-quants.py --download UD-IQ4_XS
  python3 download-flash-next-quants.py --download UD-Q4_K_XL
  python3 download-flash-next-quants.py --verify

No model load, no service changes, no changes to P0/P1 manifests.
Download manifests from Niko1221/Strata v0.2.0-beta docs/UNSLOTH_Q4.md;
pinned upstream HF revision per Strata's setup.py.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

BASE = Path('/volume1/ModelVault')
REPO = 'unsloth/Qwen3.8-Flash-Next-GGUF'
ROOT = BASE / 'models' / REPO
REV = '38bb39ee97821de2c9009abb7e93950eec396e66'
SPARE = 10_000_000_000

# (shard filename, exact file length in bytes, pinned SHA-256)
MANIFEST = {
    'UD-IQ4_XS': [
        ('Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf', 10946624, '5ce89370720f8bf90890f439361282104c1aa1482d4013bb9a50923e758e71a4'),
        ('Qwen3.8-Flash-Next-UD-IQ4_XS-00002-of-00003.gguf', 49835229856, '577a38a2392b40ca2193cea502e1d92f60b8cd370675d308e0ec21885d9daaa7'),
        ('Qwen3.8-Flash-Next-UD-IQ4_XS-00003-of-00003.gguf', 43836407744, 'd4634e6d84f0ebb0940be15c90d3790bf6464e3dea3a1cddc567dc0e83ad8833'),
    ],
    'UD-Q4_K_XL': [
        ('Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf', 10946624, '4448186216b3af4cc558bbce2c3213f01608f8f8b2e5267a9767971dd3ec8082'),
        ('Qwen3.8-Flash-Next-UD-Q4_K_XL-00002-of-00004.gguf', 49859583136, '3f342f1c1580473f1ee94ddd5b28206e8c07a70fa1a366f59d1d6c922919a6c9'),
        ('Qwen3.8-Flash-Next-UD-Q4_K_XL-00003-of-00004.gguf', 49376141504, '56758f40269cad5cd9b0d3d6fbae0f40f6d5be6de49e4ab392dbe83157d9cbd3'),
        ('Qwen3.8-Flash-Next-UD-Q4_K_XL-00004-of-00004.gguf', 12087983520, '753bda48b98ba4f1636134a90a967de1b2d3908a236c026e464777342e53510a'),
    ],
}

def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def partial_need(path, expected):
    if path.is_file() and not path.is_symlink() and path.stat().st_size == expected:
        return 0
    part = path.with_name(path.name + '.part')
    if part.is_file() and not part.is_symlink():
        return max(0, expected - min(part.stat().st_size, expected))
    return expected

def plan():
    print('=== FLASH-NEXT VAULT PLAN (read-only) ===')
    for tier, entries in MANIFEST.items():
        done = 0
        partial = 0
        remaining = 0
        for name, size, _ in entries:
            path = ROOT / tier / name
            done += int(path.is_file() and not path.is_symlink() and path.stat().st_size == size)
            part = path.with_name(path.name + '.part')
            partial += int(part.is_file() and not part.is_symlink())
            remaining += partial_need(path, size)
        total = sum(e[1] for e in entries)
        print(f'{tier}: {total/1e9:.2f} GB, size-plausible shards {done}/{len(entries)}, '
              f'partial shards {partial}, missing download bytes ~{remaining/1e9:.2f} GB')
    if BASE.is_dir():
        print(f'NAS free space: {shutil.disk_usage(BASE).free/1e9:.2f} GB')
    else:
        print('NAS share absent; cannot download')
    print('No files read in full; --verify hashes all finished shards.')

def verify(tiers):
    print('=== PINNED SHA256 CHECK ===', flush=True)
    bad = 0
    for tier in tiers:
        for i, (name, size, digest) in enumerate(MANIFEST[tier], 1):
            path = ROOT / tier / name
            if not path.is_file() or path.is_symlink():
                print(f'{tier} {i}/{len(MANIFEST[tier])}: MISSING', flush=True)
                bad += 1
                continue
            if path.stat().st_size != size:
                print(f'{tier} {i}/{len(MANIFEST[tier])}: SIZE MISMATCH', flush=True)
                bad += 1
                continue
            good = sha256(path) == digest
            print(f'{tier} {i}/{len(MANIFEST[tier])}: ' + ('PASS' if good else 'SHA256 FAIL'), flush=True)
            bad += int(not good)
    print('Result:', 'ALL PASS' if bad == 0 else f'{bad} missing/invalid shards', flush=True)
    return bad == 0

def download(tier):
    if not BASE.is_dir() or not (BASE / 'models').is_dir():
        raise RuntimeError('ModelVault data share or models directory not found; no download started')
    if shutil.which('curl') is None:
        raise RuntimeError('curl command not installed')
    entries = MANIFEST[tier]
    pathlist = [(ROOT / tier / name, name, size, digest) for name, size, digest in entries]
    outstanding = sum(partial_need(path, size) for path, _, size, _ in pathlist)
    free = shutil.disk_usage(BASE).free
    if free < outstanding + SPARE:
        raise RuntimeError(f'Not enough free space: need ~{(outstanding+SPARE)/1e9:.2f} GB '
                           f'including reserve, available {free/1e9:.2f} GB')
    print(f'Downloading {tier}: {len(entries)} pinned GGUF shards; '
          f'~{outstanding/1e9:.2f} GB remaining; no inference will be started.', flush=True)
    for i, (path, name, size, digest) in enumerate(pathlist, 1):
        partial = path.with_name(path.name + '.part')
        if path.is_symlink() or partial.is_symlink():
            raise RuntimeError(f'Symlinks not permitted for tier {tier} shard {i}')
        if path.is_file():
            if path.stat().st_size == size and sha256(path) == digest:
                print(f'{tier} {i}/{len(entries)}: ALREADY VERIFIED', flush=True)
                continue
            raise RuntimeError(f'Existing final file invalid: {tier} shard {i}; refusing overwrite')
        path.parent.mkdir(parents=True, exist_ok=True)
        if partial.exists() and partial.stat().st_size > size:
            raise RuntimeError(f'Oversized .part file: {tier} shard {i}; refusing modification')
        url = f'https://huggingface.co/{REPO}/resolve/{REV}/{tier}/{name}'
        print(f'{tier} {i}/{len(entries)}: DOWNLOADING {size/1e9:.2f} GB', flush=True)
        proc = subprocess.run([
            'curl', '--fail', '--location', '--silent', '--show-error',
            '--continue-at', '-', '--retry', '30', '--retry-delay', '30',
            '--connect-timeout', '40', '--speed-time', '120', '--speed-limit', '1024',
            '--output', str(partial), url,
        ], check=False)
        if proc.returncode != 0:
            raise RuntimeError(f'{tier} shard {i}: curl failed (exit {proc.returncode}); .part retained')
        if partial.stat().st_size != size or sha256(partial) != digest:
            raise RuntimeError(f'{tier} shard {i}: SIZE/SHA256 mismatch; .part retained')
        os.replace(partial, path)
        print(f'{tier} {i}/{len(entries)}: SHA256 VERIFIED', flush=True)
    print(f'{tier}: DONE, all {len(entries)} GGUF shards verified. Model server untouched.', flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--verify', action='store_true')
    mode.add_argument('--download', choices=MANIFEST)
    args = parser.parse_args()
    if args.plan:
        plan()
    elif args.verify:
        if not verify(MANIFEST):
            return 2
    else:
        download(args.download)
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as exc:
        if isinstance(exc, RuntimeError):
            print('STOP:', str(exc).split(';')[0][:200], file=sys.stderr)
        else:
            print('STOP: operating system error; see locally without sharing private paths', file=sys.stderr)
        raise SystemExit(2)
