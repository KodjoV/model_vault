#!/usr/bin/env python3
"""Pinned read-only audit / optional download of the *1017 abliterated* Q2_K GGUF.

Usage (NAS):
  python3 -B tools/download-ds41-1017-abliterated-q2.py --plan
  python3 -B tools/download-ds41-1017-abliterated-q2.py --verify
  python3 -B tools/download-ds41-1017-abliterated-q2.py --download

No changes to the existing Vault container, manifests, other models, b52,
or any services. --download creates only a new model subdirectory and a
local lock; it downloads .part files one at a time and checks SHA256 before
publishing. It never overwrites an existing completed file.

Expected sizes and SHA256 values: Hugging Face LFS pointer records at commit
c957bb4c5f006101e2207b7a8c0c45e61e7aa0e3.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

BASE = Path("/volume1/ModelVault")
REPO = "mrfakename/DeepSeek-V4.1-Flash-1017-abliterated-GGUF"
REV = "c957bb4c5f006101e2207b7a8c0c45e61e7aa0e3"
ROOT = BASE / "models" / REPO / "Q2_K"
LOCK = ROOT / ".ds41-1017-abliterated-q2.lock"
SPARE = 10_000_000_000
FILES = (
    ("DeepSeek-V4.1-Flash-1017-Q2_K-00001-of-00010.gguf", 29520562752,
     "588c1ea87e710ee3295da47e3bd324d1c8eb2a3ac01c1f2c4b88a513ef45ab2c"),
    ("DeepSeek-V4.1-Flash-1017-Q2_K-00002-of-00010.gguf", 29514794400,
     "4e3617fd2d180466d34de5b12cfc76033313070295040c7bed7ce7711bfd08f2"),
    ("DeepSeek-V4.1-Flash-1017-Q2_K-00003-of-00010.gguf", 29514794432,
     "adfd980162017948aa00d4709476f339183f140548197e87868353c5915ed72b"),
    ("DeepSeek-V4.1-Flash-1017-Q2_K-00004-of-00010.gguf", 29514794432,
     "7c4cd3c0f87c739e81a177c7bab96ec84995f43c05e936b0f88e9ed1fc2bfc53"),
    ("DeepSeek-V4.1-Flash-1017-Q2_K-00005-of-00010.gguf", 29514794432,
     "5a99539a1d60fae089a3404f2b1f2972b7cfe3a09a431c20baffa06b451cca3f"),
    ("DeepSeek-V4.1-Flash-1017-Q2_K-00006-of-00010.gguf", 29514794432,
     "fefc9d72435ec610c909ebaa1173086b6b86df7ccf5b7d3598b180e1447345d3"),
    ("DeepSeek-V4.1-Flash-1017-Q2_K-00007-of-00010.gguf", 19676529664,
     "54c8c2da27231aa9f0146a953e20152cd33b49ef266a7884984485e10452c4f7"),
    ("DeepSeek-V4.1-Flash-1017-Q2_K-00008-of-00010.gguf", 32256518304,
     "e61eed64f68ffa270a951c9f39b0f291449b4864717f845b50087cad55ab9b8c"),
    ("DeepSeek-V4.1-Flash-1017-Q2_K-00009-of-00010.gguf", 32257401504,
     "52abe6197a0d9ef11af621f98674f9544d385fa54d274cfc3e679c590c28f8e5"),
    ("DeepSeek-V4.1-Flash-1017-Q2_K-00010-of-00010.gguf", 3230432448,
     "73fe9177ebb784dd6ad6dcb5a27a58b9e9af09773f767d75bca9b5f0cdb1006c"),
)
TOTAL = sum(size for _, size, _ in FILES)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_paths() -> None:
    if not BASE.is_dir() or not (BASE / "models").is_dir():
        raise RuntimeError("Vault or models directory missing")
    if ROOT.is_symlink() or LOCK.is_symlink() or (BASE / "models" / REPO).is_symlink():
        raise RuntimeError("Unsafe symlink found")
    for name, _, _ in FILES:
        if (ROOT / name).is_symlink() or (ROOT / (name + ".part")).is_symlink():
            raise RuntimeError("Unsafe file symlink found")


def plan() -> None:
    check_paths()
    complete = 0
    part = 0
    left = 0
    for name, expected, _ in FILES:
        final = ROOT / name
        temp = ROOT / (name + ".part")
        if final.exists():
            if not final.is_file() or final.stat().st_size != expected:
                raise RuntimeError("Existing final file has invalid type/size; refusing to continue")
            complete += 1
        elif temp.exists():
            if not temp.is_file() or temp.stat().st_size > expected:
                raise RuntimeError("Existing part file has invalid type/size")
            part += 1
            left += expected - temp.stat().st_size
        else:
            left += expected
    print("=== DEEPSEEK V4.1 FLASH 1017 ABLITERATED Q2_K ===")
    print("Source revision: c957bb4 (pinned)")
    print(f"Total: {TOTAL/1e9:.2f} GB / files: {len(FILES)}")
    print(f"Complete-size files: {complete}/10 (not hash-verified)")
    print(f"Partial files: {part}; remaining: {left/1e9:.2f} GB")
    print(f"Vault free: {shutil.disk_usage(BASE).free/1e9:.2f} GB")
    print("Only local metadata read; no downloads or service changes.")


def verify() -> bool:
    check_paths()
    failures = 0
    for idx, (name, size, digest) in enumerate(FILES, 1):
        final = ROOT / name
        if not final.is_file() or final.stat().st_size != size:
            print(f"Shard {idx}/10: MISSING/SIZE FAIL", flush=True)
            failures += 1
            continue
        good = sha256(final) == digest
        print(f"Shard {idx}/10: {'PASS' if good else 'SHA256 FAIL'}", flush=True)
        failures += 0 if good else 1
    print("Overall:", "10/10 PASS" if not failures else f"{failures} invalid", flush=True)
    return failures == 0


def download() -> None:
    check_paths()
    if not shutil.which("curl"):
        raise RuntimeError("curl not installed")
    outstanding = 0
    for name, size, _ in FILES:
        final = ROOT / name
        temp = ROOT / (name + ".part")
        if final.exists():
            if not final.is_file() or final.stat().st_size != size:
                raise RuntimeError("Invalid final file; refusing overwrite")
        elif temp.exists():
            if not temp.is_file() or temp.stat().st_size > size:
                raise RuntimeError("Invalid part file")
            outstanding += size - temp.stat().st_size
        else:
            outstanding += size
    if shutil.disk_usage(BASE).free < outstanding + SPARE:
        raise RuntimeError("Insufficient disk space including 10 GB reserve")
    ROOT.mkdir(parents=True, exist_ok=True)
    if ROOT.is_symlink():
        raise RuntimeError("Unsafe target directory")
    with LOCK.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another instance holds the lock") from exc
        for idx, (name, size, digest) in enumerate(FILES, 1):
            final = ROOT / name
            temp = ROOT / (name + ".part")
            if final.exists():
                if final.is_file() and final.stat().st_size == size and sha256(final) == digest:
                    print(f"Shard {idx}/10: ALREADY VERIFIED", flush=True)
                    continue
                raise RuntimeError(f"Shard {idx}/10: existing final file invalid; refusing overwrite")
            if temp.exists() and (not temp.is_file() or temp.stat().st_size > size):
                raise RuntimeError(f"Shard {idx}/10: unsafe or oversized part file")
            if not temp.exists() or temp.stat().st_size < size:
                url = f"https://huggingface.co/{REPO}/resolve/{REV}/Q2_K/{name}"
                print(f"Shard {idx}/10: downloading/resuming", flush=True)
                cmd = [
                    "curl", "--fail", "--location", "--silent", "--show-error",
                    "--proto", "=https", "--proto-redir", "=https",
                    "--continue-at", "-", "--retry", "30", "--retry-delay", "30",
                    "--connect-timeout", "40", "--speed-time", "120",
                    "--speed-limit", "1024", "--output", str(temp), url
                ]
                result = subprocess.run(cmd, check=False)
                if result.returncode:
                    raise RuntimeError(f"Shard {idx}/10: curl failed ({result.returncode}); .part retained")
            if not temp.is_file() or temp.stat().st_size != size:
                raise RuntimeError(f"Shard {idx}/10: size mismatch; .part retained")
            if sha256(temp) != digest:
                raise RuntimeError(f"Shard {idx}/10: SHA256 FAIL; .part retained")
            if final.exists():
                raise RuntimeError(f"Shard {idx}/10: final file appeared; refusing overwrite")
            os.link(temp, final)
            temp.unlink()
            print(f"Shard {idx}/10: SHA256 PASS", flush=True)
    print("DONE: DeepSeek V4.1 Flash 1017 Abliterated Q2_K, 10/10 PASS", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    for mode in ("plan", "verify", "download"):
        g.add_argument("--" + mode, action="store_true")
    args = p.parse_args()
    if args.plan:
        plan()
    elif args.verify:
        return 0 if verify() else 2
    else:
        download()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as exc:
        print("STOP:", str(exc).splitlines()[0][:180], file=sys.stderr)
        raise SystemExit(2)
