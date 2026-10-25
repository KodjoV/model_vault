#!/usr/bin/env python3
"""Safe, resumable Nanbeige4.3-33B GGUF download for the UGREEN Model Vault.

Usage:
  python3 -B tools/download-nanbeige43.py --plan
  python3 -B tools/download-nanbeige43.py --queue
  python3 -B tools/download-nanbeige43.py --download
  python3 -B tools/download-nanbeige43.py --verify

--queue waits until known existing NAS Model Vault download processes
finish, plus a quiet interval, then downloads. It does not alter or
restart the existing download process. If none can be detected, --queue
refuses to guess. Run with nohup if you want it to survive SSH logout.

No additional packages: Python stdlib + installed curl.
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
import time

BASE = Path("/volume1/ModelVault")
REPO = "AtomicChat/Nanbeige4.3-33B-GGUF"
NAME = "Nanbeige4.3-33B-AD-IQ4_XS.gguf"
ROOT = BASE / "models" / REPO / "AD-IQ4_XS"
FINAL = ROOT / NAME
PART = ROOT / (NAME + ".part")
LOCK = ROOT / ".nanbeige43-download.lock"
SIZE = 20_347_792_384
SHA256 = "47793d95e80b69f46edce427f0676487b4e4fe58b093248300b42f6d9d775481"
URL = f"https://huggingface.co/{REPO}/resolve/main/{NAME}"
SPARE = 5_000_000_000


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def is_regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def check_roots() -> None:
    if not BASE.is_dir() or not (BASE / "models").is_dir():
        raise RuntimeError("Model Vault root/models missing")
    if ROOT.is_symlink() or FINAL.is_symlink() or PART.is_symlink() or LOCK.is_symlink():
        raise RuntimeError("Symlink in download target; refusing")


def proc_birth(pid: int) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        return raw.rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def known_downloaders() -> dict[int, str]:
    """Identify only known Vault downloaders. Never print raw commands."""
    result = {}
    me = os.getpid()
    for ent in Path("/proc").iterdir():
        if not ent.name.isdecimal():
            continue
        pid = int(ent.name)
        if pid == me:
            continue
        try:
            args = [
                x.decode("utf-8", "replace")
                for x in (ent / "cmdline").read_bytes().split(b"\0") if x
            ]
        except (OSError, PermissionError):
            continue
        if not args:
            continue
        exe = Path(args[0]).name.lower()
        script = [
            a.lower() for a in args[1:]
            if (a.startswith("/") and
                ("/model_vault/" in a.lower() or "/modelvault/" in a.lower()) and
                "download" in Path(a).name.lower() and
                (a.endswith(".py") or a.endswith(".sh")))
        ]
        is_script = bool(script) and exe in ("python", "python3", "bash", "sh", "env", "busybox")
        is_curl = exe in ("curl", "wget", "aria2c", "hf") and (
            any("/volume1/ModelVault/" in a for a in args)
            and any("huggingface.co" in a for a in args)
        )
        # Never count ourselves, even if started as /usr/bin/python3.
        if (is_script and any("download-nanbeige43.py" not in a for a in script)) or is_curl:
            born = proc_birth(pid)
            if born is not None:
                result[pid] = born
    return result


def plan() -> None:
    print("=== NANBEIGE 4.3 VAULT PLAN ===")
    print("Quant: AD-IQ4_XS")
    print(f"Expected: {SIZE / 1e9:.2f} GB")
    if BASE.is_dir():
        print(f"Vault available: {shutil.disk_usage(BASE).free / 1e9:.2f} GB")
    if FINAL.exists():
        print("Final file: present" if is_regular(FINAL) else "Final file: invalid type")
        if is_regular(FINAL):
            print("Size:", "PASS" if FINAL.stat().st_size == SIZE else "MISMATCH")
    else:
        print("Final file: not yet present")
    if PART.exists():
        print("Part file: %.2f GB" % (PART.stat().st_size / 1e9) if is_regular(PART) else "Part file: invalid type")
    else:
        print("Part file: none")
    print("Recognized active Vault download processes:", len(known_downloaders()))
    print("Plan reads metadata only; no services modified.")


def verify() -> bool:
    check_roots()
    if not is_regular(FINAL):
        print("SHA256: MISSING")
        return False
    if FINAL.stat().st_size != SIZE:
        print("SHA256: SIZE FAIL")
        return False
    ok = sha256(FINAL) == SHA256
    print("SHA256:", "PASS" if ok else "FAIL", flush=True)
    return ok


def download() -> None:
    check_roots()
    if shutil.which("curl") is None:
        raise RuntimeError("curl not present")
    ROOT.mkdir(parents=True, exist_ok=True)
    if ROOT.is_symlink():
        raise RuntimeError("Target directory symlink")
    with LOCK.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another Nanbeige downloader holds the lock") from exc
        if FINAL.exists():
            if verify():
                print("ALREADY VERIFIED; no download needed.", flush=True)
                return
            raise RuntimeError("Existing final file invalid; refusing overwrite")
        if PART.exists() and not is_regular(PART):
            raise RuntimeError("Part file is not a regular file")
        existing = PART.stat().st_size if PART.exists() else 0
        if existing > SIZE:
            raise RuntimeError("Part file exceeds expected size")
        needed = SIZE - existing
        if shutil.disk_usage(BASE).free < needed + SPARE:
            raise RuntimeError("Insufficient free space including 5 GB reserve")
        if existing < SIZE:
            print(f"Downloading {NAME} ({needed / 1e9:.2f} GB remaining)", flush=True)
            p = subprocess.run([
                "curl", "--fail", "--location", "--silent", "--show-error",
                "--continue-at", "-", "--retry", "30", "--retry-delay", "30",
                "--connect-timeout", "40", "--speed-time", "120",
                "--speed-limit", "1024", "--output", str(PART), URL
            ], check=False)
            if p.returncode:
                raise RuntimeError(f"curl failed with status {p.returncode}; .part retained")
        if PART.stat().st_size != SIZE:
            raise RuntimeError("Downloaded size mismatch; .part retained")
        print("Verifying pinned SHA256...", flush=True)
        if sha256(PART) != SHA256:
            raise RuntimeError("SHA256 mismatch; .part retained")
        # Never replace a pre-existing final file.
        if FINAL.exists():
            raise RuntimeError("Final file appeared during download; refusing overwrite")
        os.link(PART, FINAL)
        PART.unlink()
        print("DONE: Nanbeige4.3-33B AD-IQ4_XS, SHA256 PASS", flush=True)


def queue() -> None:
    initial = known_downloaders()
    if not initial:
        raise RuntimeError(
            "No recognized running Vault download process. Cannot safely infer queue order. "
            "Use --plan and identify the active downloader before queueing."
        )
    print(f"QUEUED: waiting for {len(initial)} recognized Vault downloader(s)", flush=True)
    quiet_since = None
    while True:
        active = known_downloaders()
        if active:
            quiet_since = None
        else:
            if quiet_since is None:
                quiet_since = time.monotonic()
                print("Vault idle; confirming 45 seconds of quiet...", flush=True)
            elif time.monotonic() - quiet_since >= 45:
                break
        time.sleep(15)
    print("Known downloaders finished. Starting Nanbeige.", flush=True)
    download()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    actions = ap.add_mutually_exclusive_group(required=True)
    for name in ("plan", "verify", "download", "queue"):
        actions.add_argument("--" + name, action="store_true")
    args = ap.parse_args()
    if args.plan:
        plan()
    elif args.verify:
        return 0 if verify() else 2
    elif args.queue:
        queue()
    else:
        download()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as exc:
        print("STOP:", str(exc).splitlines()[0][:180], file=sys.stderr)
        raise SystemExit(2)
