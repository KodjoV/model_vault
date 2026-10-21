#!/usr/bin/env python3
"""Read-only forensic audit of the GLM Maya NAS downloader and its six GGUF shards.

Reads model-file metadata and (optionally) SHA256, bounded sanitized logs,
and optional user/root crontab contents without printing raw entries.
Does not start, stop, download, modify files or inspect private config.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import hashlib
import subprocess

BASE = Path("/volume1/ModelVault/models/peasantsmith/GLM-5.3-Flash-Maya-GGUF")
LOG = Path("/volume1/ModelVault/maya-glm53-download.log")
FILES = [
    ("S24", 1, "Maya-S24", "GLM-5.3-Flash-Maya-S24-IQ2_XXS_S-00001-of-00003.gguf",
     ("8ebd5c74bcf65ece2a8699b7b6fd2b8d177f350ed252cee252fdd99b86a0138c",
      "3dc347757686c1435eae36c4872f5c151191cc5063bc188ce699b97700aae076")),
    ("S24", 2, "Maya-S24", "GLM-5.3-Flash-Maya-S24-IQ2_XXS_S-00002-of-00003.gguf",
     ("4bd445da3a0128a9c5b32228c924e0a622aa4a132c7a8dc9a2c207a4beea8e34",)),
    ("S24", 3, "Maya-S24", "GLM-5.3-Flash-Maya-S24-IQ2_XXS_S-00003-of-00003.gguf",
     ("a6fd4e88007ac49b431c7d02be34e43ab7a09224d53a0c52782327613cb41917",)),
    ("M", 1, "Maya-M", "GLM-5.3-Flash-Maya-M-IQ2_S-00001-of-00003.gguf",
     ("3f740d1b1022b4a0ddad50cd861bb071dd415bde94afa1292d0476641186c638",
      "3ac0f066ec45af3432d59b33de49bdfb29156432b627240b35769c7d02cc6c02")),
    ("M", 2, "Maya-M", "GLM-5.3-Flash-Maya-M-IQ2_S-00002-of-00003.gguf",
     ("285951d2afa0cd98285b03d0dc4aa68d83daf1a6f4a2594fe40b0cdd27ade485",)),
    ("M", 3, "Maya-M", "GLM-5.3-Flash-Maya-M-IQ2_S-00003-of-00003.gguf",
     ("ebf1ce713f71207747e10eeebed87597969d8b5e1d9dd817420d2c2f7ca51e0e",)),
]

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(4 * 1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()

def fmtdate(seconds):
    return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M")

def show_files(check_hash):
    print("=== GLM MAYA: SIX EXPECTED SHARDS ===")
    variants = {"S24": [], "M": []}
    for variant, idx, directory, name, hashes in FILES:
        path = BASE / directory / name
        partial = BASE / directory / (name + ".part")
        if not path.is_file() or path.is_symlink():
            print(f"{variant} shard {idx}/3: MISSING" +
                  ("; .part exists" if partial.is_file() else ""))
            variants[variant].append(False)
            continue
        try:
            stat = path.stat()
            with path.open("rb") as stream:
                magic = stream.read(4) == b"GGUF"
            large = stat.st_size >= 4096
            valid = magic and large
            msg = (f"{variant} shard {idx}/3: {stat.st_size/1e9:.3f} GB, "
                   f"GGUF header={'OK' if magic else 'NO'}, "
                   f"mtime={fmtdate(stat.st_mtime)}")
            if partial.is_file():
                msg += ", EXTRA .part EXISTS"
            if check_hash:
                passed = sha256(path) in hashes
                msg += ", SHA256=" + ("PASS" if passed else "FAIL")
                valid = valid and passed
            print(msg)
            variants[variant].append(valid)
        except OSError:
            print(f"{variant} shard {idx}/3: READ ERROR")
            variants[variant].append(False)
    for variant, results in variants.items():
        print(f"{variant} files: {sum(results)}/3 "
              f"{'SHA256 VERIFIED' if check_hash else 'HEADER/SIZE PLAUSIBLE'}")
    if not check_hash:
        print("Note: run with --sha256 later for independent full-file hash checks "
              "(reads ~211 GB, potentially slow).")

def show_log():
    print()
    print("=== DOWNLOAD LOG (SANITIZED) ===")
    if not LOG.is_file():
        print("No expected scheduler log found. A manual run may use another output.")
        return
    try:
        size = LOG.stat().st_size
        with LOG.open("rb") as f:
            # Avoid reading an unbounded progress log with repeated CR progress updates.
            if size > 8_000_000:
                f.seek(-8_000_000, 2)
            tail = f.read().decode("utf-8", errors="replace")
        signals = [line.strip() for line in tail.replace("\r", "\n").split("\n")]
        counts = {k: 0 for k in
                  ("DOWNLOADING:", "VERIFIED:", "ALREADY VERIFIED:", "ERROR:", "DONE:")}
        last = None
        for line in signals:
            for key in counts:
                if line.startswith(key):
                    counts[key] += 1
                    last = key[:-1]
                    break
        print(f"Log exists: yes; size={size/1e6:.2f} MB; "
              f"last modified={fmtdate(LOG.stat().st_mtime)}")
        print("Recognized markers in last up-to-8MB: " +
              ", ".join(f"{k[:-1]}={v}" for k, v in counts.items()))
        print("Last recognized marker: " + (last or "none"))
        if counts["DONE:"]:
            print("Uploader script printed its terminal DONE status.")
        else:
            print("No terminal DONE marker found in inspected log segment.")
    except OSError:
        print("Log metadata/content not readable.")

def show_crontab():
    print()
    print("=== CRON VISIBILITY (NO ENTRY CONTENT SHOWN) ===")
    for label, cmd in (
        ("current user", ["crontab", "-l"]),
        ("root via passwordless sudo", ["sudo", "-n", "crontab", "-l"]),
    ):
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, timeout=4,
                               check=False)
            if p.returncode != 0:
                print(f"{label}: not readable / no entries")
            else:
                relevant = [line for line in p.stdout.splitlines()
                            if line.strip() and not line.lstrip().startswith("#")
                            and ("download-glm53-maya" in line.lower()
                                 or "glm-5.3-flash-maya" in line.lower())]
                print(f"{label}: {len(relevant)} GLM-Maya cron entries visible")
        except (OSError, subprocess.TimeoutExpired):
            print(f"{label}: not accessible")
    print("UGOS Task Scheduler can store tasks outside visible crontabs; "
          "zero matches does NOT prove no scheduled job existed.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha256", action="store_true",
                        help="Hash all six local model files against pinned upstream digests")
    args = parser.parse_args()
    show_files(args.sha256)
    show_log()
    show_crontab()

if __name__ == "__main__":
    main()
