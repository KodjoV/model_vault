#!/usr/bin/env python3
"""Read-only Flash-Next GGUF download monitor for UGREEN NAS.

Reads only stat() metadata of seven expected GGUF/.part files. No network,
logs, hashes, process interaction or writes. Safe to run during active curl.

Examples:
  python3 -B tools/flash-next-status.py           # one snapshot, ~4s sampling
  python3 -B tools/flash-next-status.py --watch   # refresh every five seconds
  python3 -B tools/flash-next-status.py --once --sample 2
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
import time

DEFAULT_ROOT = Path(
    "/volume1/ModelVault/models/unsloth/Qwen3.8-Flash-Next-GGUF"
)

# Names and sizes are pinned to download-flash-next-quants.py / Strata docs.
MANIFEST = {
    "UD-IQ4_XS": (
        ("Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf", 10946624),
        ("Qwen3.8-Flash-Next-UD-IQ4_XS-00002-of-00003.gguf", 49835229856),
        ("Qwen3.8-Flash-Next-UD-IQ4_XS-00003-of-00003.gguf", 43836407744),
    ),
    "UD-Q4_K_XL": (
        ("Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf", 10946624),
        ("Qwen3.8-Flash-Next-UD-Q4_K_XL-00002-of-00004.gguf", 49859583136),
        ("Qwen3.8-Flash-Next-UD-Q4_K_XL-00003-of-00004.gguf", 49376141504),
        ("Qwen3.8-Flash-Next-UD-Q4_K_XL-00004-of-00004.gguf", 12087983520),
    ),
}

@dataclass(frozen=True)
class FileState:
    index: int
    expected: int
    bytes_present: int
    kind: str  # final, partial, missing, invalid, inaccessible
    age: float | None

@dataclass(frozen=True)
class TierState:
    name: str
    files: tuple[FileState, ...]
    @property
    def total(self):
        return sum(x.expected for x in self.files)
    @property
    def downloaded(self):
        return sum(min(x.expected, x.bytes_present) for x in self.files)
    @property
    def complete(self):
        return sum(x.kind == "final" for x in self.files)
    @property
    def current(self):
        return next((x for x in self.files if x.kind != "final"), None)

def inspect(root: Path, now: float):
    tiers = []
    for name, entries in MANIFEST.items():
        files = []
        for i, (filename, expected) in enumerate(entries, 1):
            final = root / name / filename
            part = root / name / (filename + ".part")
            state = FileState(i, expected, 0, "missing", None)
            try:
                if final.is_symlink() or part.is_symlink():
                    state = FileState(i, expected, 0, "invalid", None)
                elif final.is_file():
                    st = final.stat()
                    kind = "final" if st.st_size == expected else "invalid"
                    state = FileState(
                        i, expected, max(0, st.st_size), kind,
                        max(0., now - st.st_mtime)
                    )
                elif part.is_file():
                    st = part.stat()
                    kind = "partial" if st.st_size <= expected else "invalid"
                    state = FileState(
                        i, expected, max(0, st.st_size), kind,
                        max(0., now - st.st_mtime)
                    )
            except OSError:
                state = FileState(i, expected, 0, "inaccessible", None)
            files.append(state)
        tiers.append(TierState(name, tuple(files)))
    return tuple(tiers)

def bar(frac: float, width=28):
    frac = min(max(frac, 0.), 1.)
    blocks = round(frac * width)
    return "[" + "#" * blocks + "-" * (width - blocks) + "]"

def interval(seconds):
    if seconds is None or seconds < 0:
        return "—"
    sec = int(seconds)
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m {sec % 60}s"
    return f"{sec // 3600}h {(sec % 3600) // 60}m"

def bytes_gb(n):
    return f"{n / 1e9:.2f} GB"

def rate_for(name, current, previous, elapsed):
    if not previous or elapsed <= 0:
        return None
    before = next(t for t in previous if t.name == name)
    delta = current.downloaded - before.downloaded
    return delta / elapsed if delta > 0 else None

def fmt_rate(rate):
    return f"{rate / 1e6:.2f} MB/s" if rate is not None else "noch nicht messbar"

def print_status(tiers, prior, elapsed):
    print("=== FLASH-NEXT: DOWNLOADSTATUS ===")
    print(f"Stand: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')} (NAS-Lokalzeit)")
    total_bytes = sum(t.total for t in tiers)
    downloaded = sum(t.downloaded for t in tiers)
    print(f"Gesamt  {bar(downloaded / total_bytes)} "
          f"{100*downloaded/total_bytes:5.1f}%  "
          f"{bytes_gb(downloaded)} / {bytes_gb(total_bytes)}")
    print()
    for t in tiers:
        print(f"{t.name:<11}{bar(t.downloaded/t.total)} "
              f"{100*t.downloaded/t.total:5.1f}%")
        print(f"  {bytes_gb(t.downloaded)} / {bytes_gb(t.total)}"
              f" · fertige Shards: {t.complete}/{len(t.files)}")
        active = t.current
        if active is None:
            print("  Status: Alle Finaldateien vorhanden (Groessen stimmen).")
            print("  Hashwerte hier nicht erneut geprueft.")
            print()
            continue
        if active.kind == "invalid":
            print(f"  Status: WARNUNG: Shard {active.index}/{len(t.files)} "
                  "hat unplausible Groesse oder ist ein Symlink.")
        elif active.kind == "inaccessible":
            print(f"  Status: Shard {active.index}/{len(t.files)} nicht lesbar.")
        elif active.kind == "missing":
            print(f"  Naechster Shard: {active.index}/{len(t.files)} noch nicht angelegt.")
        else:
            print(f"  Aktuell: Shard {active.index}/{len(t.files)} "
                  f"{bar(active.bytes_present / active.expected, 18)} "
                  f"{100*active.bytes_present/active.expected:5.1f}%")
            print(f"  Shard: {bytes_gb(active.bytes_present)} / "
                  f"{bytes_gb(active.expected)}")
            if active.bytes_present >= active.expected:
                print("  Datei vollstaendig geschrieben; "
                      "eventuell laufende SHA256-Pruefung.")
            elif active.age is not None:
                print(f"  Letzte Dateiaenderung: vor {interval(active.age)}")
        rate = rate_for(t.name, t, prior, elapsed)
        print(f"  Gemessener Zuwachs: {fmt_rate(rate)}")
        if rate:
            print(f"  Restzeit fuer {t.name}: ca. "
                  f"{interval((t.total - t.downloaded) / rate)} "
                  "(grobe Schaetzung)")
        elif active.kind == "partial":
            print("  Hinweis: kein Zuwachs im Messintervall; "
                  "moeglicherweise Pause, Retry oder Pruefung.")
        print()
    rate = None
    if prior and elapsed > 0:
        delta = downloaded - sum(t.downloaded for t in prior)
        if delta > 0:
            rate = delta / elapsed
    if rate:
        print(f"Gesamtrate: {fmt_rate(rate)}"
              f" · Restzeit beide Quants: ca. {interval((total_bytes-downloaded)/rate)}")
    print("Nur Dateigroessen, keine Hashpruefung; "
          "der Downloadprozess wird nicht beeinflusst.")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                    help=argparse.SUPPRESS)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--watch", action="store_true",
                      help="Aktualisiert die Anzeige alle 5 Sekunden bis Strg+C.")
    mode.add_argument("--once", action="store_true",
                      help="Einmalige Abfrage (Standard).")
    ap.add_argument("--interval", type=float, default=5.0,
                    help="Sekunden zwischen Watch-Aktualisierungen (Standard: 5).")
    ap.add_argument("--sample", type=float, default=4.0,
                    help="Sekunden Messintervall bei einmaliger Abfrage (Standard: 4).")
    args = ap.parse_args()
    if not args.root.is_dir():
        print("STOP: Erwartetes Flash-Next-Modellverzeichnis nicht gefunden.",
              file=sys.stderr)
        return 2
    if not (1 <= args.interval <= 3600 and 1 <= args.sample <= 3600):
        print("STOP: Messintervall muss zwischen 1 und 3600 s liegen.",
              file=sys.stderr)
        return 2
    try:
        prior = inspect(args.root, time.time())
        previous_time = time.monotonic()
        if not args.watch:
            time.sleep(args.sample)
            current = inspect(args.root, time.time())
            print_status(current, prior, time.monotonic() - previous_time)
            return 0
        while True:
            current = inspect(args.root, time.time())
            if sys.stdout.isatty():
                print("\033[2J\033[H", end="")
            print_status(current, prior if previous_time != 0 else None,
                         max(time.monotonic()-previous_time, 0))
            sys.stdout.flush()
            prior = current
            previous_time = time.monotonic()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStatusanzeige beendet. Download laeuft unabhaengig weiter.")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
