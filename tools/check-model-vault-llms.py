#!/usr/bin/env python3
"""Read-only UGREEN Model Vault inventory for GLM, DeepSeek and Qwen Flash-Next.

Reports only public model-family names, quant labels, sizes and shard status.
No log content, paths, credentials or host details printed. No downloads.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import argparse
import os
import re

ROOT = Path("/volume1/ModelVault/models")
MIN_SHARD = 4096  # Valid final GGUF shards can be smaller than 1 GB; check magic too.
QUANTS = (
    "IQ2_XXS_S", "IQ3_XXS", "IQ3_XS", "IQ3_S", "IQ3_M",
    "IQ4_XS", "IQ4_NL", "IQ4_S", "IQ4_M", "Q3_K_XL",
    "Q3_K_L", "Q3_K_M", "Q3_K_S", "Q4_K_M", "Q4_K_S",
    "Q4_0", "Q4_1", "Q5_K_M", "Q5_K_S", "Q5_0", "Q5_1",
    "Q6_K", "Q8_0", "IQ2_XXS", "IQ2_XS", "IQ2_S",
    "IQ2_M", "IQ1_S", "IQ1_M", "BF16", "F16", "F32",
)
Q_RE = re.compile(
    r"(?<![A-Za-z0-9])(" + "|".join(map(re.escape, QUANTS)) + r")(?![A-Za-z0-9])",
    re.I,
)
SHARD_RE = re.compile(r"-(\d{5})-of-(\d{5})\.gguf(?:\.part)?$", re.I)
MAYA = {
    "Maya-S24": ("GLM-5.3-Flash-Maya-S24-IQ2_XXS_S", "IQ2_XXS_S", 94.7),
    "Maya-M": ("GLM-5.3-Flash-Maya-M-IQ2_S", "IQ2_S", 116.0),
}
HIGHER_CANDIDATES = {
    "IQ3_M", "IQ4_XS", "IQ4_NL", "IQ4_S", "IQ4_M",
    "Q3_K_L", "Q3_K_XL", "Q4_K_M", "Q4_K_S", "Q4_0", "Q4_1",
    "Q5_K_M", "Q5_K_S", "Q5_0", "Q5_1", "Q6_K", "Q8_0",
    "F16", "BF16", "F32",
}

def family(label):
    name = label.lower()
    if "deepseek" in name:
        return "DeepSeek"
    if "glm" in name:
        return "GLM"
    if "qwen" in name and "flash" in name and "next" in name:
        return "Qwen Flash-Next"
    return None

def quant(name):
    found = Q_RE.search(name)
    return found.group(1).upper() if found else "UNKNOWN"

def gb(n):
    return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.1f} MB"

def valid_magic(file):
    try:
        with file.open("rb") as stream:
            return stream.read(4) == b"GGUF"
    except OSError:
        return False

def plausible(group):
    required = set(range(1, group["expected"] + 1))
    return (set(group["files"]) == required
            and not group["parts"]
            and all(size >= MIN_SHARD and ok for size, ok in group["files"].values()))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    root = parser.parse_args().root
    if not root.is_dir():
        print("STOP: Model Vault data root is not accessible; no changes.")
        return 2

    groups = {}
    inaccessible = []
    unreadable = 0
    for current, dirs, files in os.walk(
        root, followlinks=False, onerror=lambda exc: inaccessible.append(type(exc).__name__)
    ):
        dirs[:] = [d for d in dirs if not d.startswith(".")
                   and not (Path(current) / d).is_symlink()]
        directory = Path(current)
        relative = str(directory.relative_to(root))
        for filename in files:
            lower = filename.lower()
            if not (lower.endswith(".gguf") or lower.endswith(".gguf.part")):
                continue
            label = relative + "/" + filename
            f = family(label)
            if not f:
                continue
            full = directory / filename
            if full.is_symlink():
                continue
            try:
                size = full.stat().st_size
            except OSError:
                unreadable += 1
                continue
            match = SHARD_RE.search(filename)
            index, total = (int(match.group(1)), int(match.group(2))) if match else (1, 1)
            if index < 1 or total < 1 or index > total:
                continue
            stem = SHARD_RE.sub(".gguf", filename) if match else filename
            key = (relative, stem)
            group = groups.setdefault(key, {
                "family": f, "quant": quant(stem), "expected": total,
                "files": {}, "parts": {},
            })
            group["expected"] = max(group["expected"], total)
            partial = lower.endswith(".part")
            group["parts" if partial else "files"][index] = (
                size, False if partial else valid_magic(full)
            )

    print("=== MODEL VAULT: READ-ONLY INVENTORY ===")
    print(f"Matching GGUF groups: {len(groups)}; unreadable files: {unreadable}; "
          f"inaccessible directories: {len(inaccessible)}")
    print("Classification is NOT a SHA256 or runtime compatibility check.")
    print()
    print("GLM-5.3-Flash Maya (separate downloader; 3 shards per variant):")
    for variant, (stem, q, expected_gb) in MAYA.items():
        found = [
            x for (directory, filename), x in groups.items()
            if (variant.lower() in directory.lower() or variant.lower() in filename.lower())
            and stem.lower() in filename.lower()
        ]
        finalized = sum(len(x["files"]) for x in found)
        parts = sum(len(x["parts"]) for x in found)
        size = sum(s for x in found for s, _ in x["files"].values())
        complete = len(found) == 1 and plausible(found[0]) and (
            size >= expected_gb * 0.90 * 1e9
        )
        status = ("SIZE-PLAUSIBLE (not hash-verified)" if complete
                  else "PARTIAL/UNVERIFIED" if found else "NOT FOUND")
        print(f"  {variant} [{q}]: {status}; GGUF={finalized}/3, "
              f".part={parts}, final bytes={gb(size)}, expected ~{expected_gb} GB")
    print()

    ds = [
        x for (directory, filename), x in groups.items()
        if x["family"] == "DeepSeek"
        and all(term in (directory + "/" + filename).lower()
                for term in ("v4.1", "flash", "1017"))
    ]
    print(f"DeepSeek V4.1 Flash 1017: {len(ds)} quant/shard groups, "
          f"{sum(plausible(x) for x in ds)} with plausible complete shards")
    print()

    for f in ("DeepSeek", "GLM", "Qwen Flash-Next"):
        selected = [x for x in groups.values() if x["family"] == f]
        summary = defaultdict(lambda: [0, 0, 0, 0, 0])
        for group in selected:
            # Complete/incomplete, finished/partial shards, final bytes.
            values = summary[group["quant"]]
            values[0 if plausible(group) else 1] += 1
            values[2] += len(group["files"])
            values[3] += len(group["parts"])
            values[4] += sum(s for s, _ in group["files"].values())
        print(f"{f}: {len(selected)} groups")
        if not selected:
            print("  No matching GGUF or partial GGUF found.")
        for q, (complete, incomplete, shards, parts, size) in sorted(summary.items()):
            print(f"  {q}: plausible-complete={complete}, incomplete={incomplete}, "
                  f"shards={shards}, .part={parts}, final bytes={gb(size)}")

    higher = sorted({
        x["quant"] for x in groups.values()
        if x["family"] == "Qwen Flash-Next"
        and x["quant"] in HIGHER_CANDIDATES and plausible(x)
    })
    print()
    print("Qwen Flash-Next quantization candidates above current IQ3_S:")
    print("  " + (", ".join(higher) if higher else "NONE FOUND"))
    print("A plausible file set must still pass independent SHA256 and engine tests.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
