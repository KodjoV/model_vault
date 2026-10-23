#!/usr/bin/env python3
"""Offline SHA256 audit for the six ABL archives in Model Vault.

Reads only; never repairs or starts downloads. No third-party packages needed.
Usage: python3 tools/verify-abliterated.py [--root /volume1/ModelVault]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

ABL_TIER = "ABL"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def safe_rel(name: str) -> Path:
    p = PurePosixPath(name)
    if (
        not name or p.is_absolute() or "\\" in name
        or any(s in ("", ".", "..") for s in name.split("/"))
    ):
        raise ValueError(f"Unsafe path: {name!r}")
    return Path(*p.parts)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_one(root: Path, model: dict) -> tuple[int, int, int]:
    repo = model["repo"]
    safe_rel(repo)
    directory = root / "models" / repo
    manifest_path = directory / "MODEL_VAULT_MANIFEST.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError(f"{repo}: missing/unsafe manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    revision = manifest.get("revision", "")
    if manifest.get("repo") != repo or not HEX40.fullmatch(revision):
        raise ValueError(f"{repo}: wrong repo or non-commit revision in manifest")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError(f"{repo}: manifest has no files")
    names = {record.get("path") for record in files}
    if len(names) != len(files):
        raise ValueError(f"{repo}: duplicate file names in manifest")
    required = set(model.get("required_patterns", []))
    if not required.issubset(names):
        raise ValueError(f"{repo}: missing required files: {sorted(required - names)}")

    checked = remote_matched = total_bytes = 0
    base = directory.resolve(strict=True)
    for record in files:
        name = record["path"]
        safe_rel(name)
        path = directory / name
        # Reject local symlinks, including symlinks in intermediate folders.
        for ancestor in [path, *path.parents]:
            if ancestor == directory.parent:
                break
            if ancestor.is_symlink():
                raise ValueError(f"{repo}: symlink in path {name}")
        if not path.is_file() or not path.resolve().is_relative_to(base):
            raise ValueError(f"{repo}: missing/unsafe file {name}")
        size = record.get("size")
        digest = record.get("sha256")
        if not isinstance(size, int) or size < 0 or path.stat().st_size != size:
            raise ValueError(f"{repo}: size mismatch: {name}")
        if not isinstance(digest, str) or not HEX64.fullmatch(digest):
            raise ValueError(f"{repo}: missing SHA256: {name}")
        actual = sha256_file(path)
        if actual != digest:
            raise ValueError(f"{repo}: SHA256 mismatch: {name}")
        upstream = record.get("lfs_sha256")
        if upstream is not None:
            if not isinstance(upstream, str) or not HEX64.fullmatch(upstream):
                raise ValueError(f"{repo}: malformed upstream digest: {name}")
            if actual != upstream:
                raise ValueError(f"{repo}: upstream LFS SHA256 mismatch: {name}")
            remote_matched += 1
        checked += 1
        total_bytes += size
    print(f"OK {repo} @{revision[:12]} | files={checked} | "
          f"upstream LFS checked={remote_matched}/{checked} | "
          f"size={total_bytes / (1024**3):.2f} GiB", flush=True)
    return checked, remote_matched, total_bytes


def run(root: Path, catalog: Path) -> int:
    data = json.loads(catalog.read_text(encoding="utf-8"))
    models = [m for m in data["models"] if m.get("tier") == ABL_TIER and m.get("enabled", True)]
    if len(models) != 6:
        raise ValueError(f"Expected 6 ABL repos, got {len(models)}")
    total_files = total_upstream = total_bytes = 0
    failures = []
    for model in models:
        try:
            files, upstream, size = verify_one(root, model)
            total_files += files
            total_upstream += upstream
            total_bytes += size
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            print(f"FAIL {model['repo']}: {e}", file=sys.stderr, flush=True)
            failures.append(model["repo"])
    print(f"SUMMARY OK={len(models) - len(failures)}/6 | "
          f"files={total_files} | upstream LFS={total_upstream}/{total_files} | "
          f"size={total_bytes / (1024**3):.2f} GiB", flush=True)
    if total_upstream < total_files:
        print("NOTE: Files without upstream LFS hashes were checked against the "
              "stored local manifest only; this is not independent publisher verification.",
              flush=True)
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/volume1/ModelVault"))
    parser.add_argument("--catalog", type=Path,
                        default=Path(__file__).resolve().parents[1] / "models.json")
    args = parser.parse_args()
    return run(args.root, args.catalog)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"STOP: {error}", file=sys.stderr)
        sys.exit(2)
