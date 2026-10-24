#!/usr/bin/env python3
"""Queue DS41 then OPEN3 on the existing UGREEN Model Vault without stopping current downloads.

Install: sudo python3 tools/queue-next-vault.py install
Status:  cat /volume1/ModelVault/.vault/model-queue-status.json
This detached process survives SSH logout but NOT a NAS reboot.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.request import Request, urlopen

CODE = Path("/volume1/docker/model_vault")
VAULT = Path("/volume1/ModelVault")
DOT = VAULT / ".vault"
STATUS = DOT / "status.json"
QUEUE_STATUS = DOT / "model-queue-status.json"
LOG = DOT / "model-queue.log"
LOCK = DOT / "model-queue.lock"
PENDING = DOT / "model-queue-pending.json"
VERIFY_PENDING = DOT / "model-queue-verify.pending.py"
PIN = "4544759629c94cf85d2257f32649961e99de9c66"
SOURCE = f"https://raw.githubusercontent.com/KodjoV/model_vault/{PIN}"
TIERS = ("DS41", "OPEN3")
EXPECTED_REPOS = {
    "DS41": {
        "ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF",
        "unsloth/DeepSeek-V4.1-Flash-1017-GGUF",
    },
    "OPEN3": {
        "huihui-ai/Huihui-GLM-5.3-Flash-abliterated-GGUF",
        "ggml-org/GLM-5.3-Flash-GGUF",
        "audreyt/DeepSeek-V4.1-Flash-Abliterated-GGUF",
    },
}
# Estimates, not remote metadata. Leave 15% reserve beyond missing bytes.
ESTIMATED_BYTES = {"DS41": 274_000_000_000, "OPEN3": 585_000_000_000}


def record(state: str, **kwargs):
    previous = {}
    if QUEUE_STATUS.is_file():
        try:
            previous = json.loads(QUEUE_STATUS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    document = {**previous, "state": state,
                "updated_utc": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid(), "tiers": list(TIERS), **kwargs}
    tmp = QUEUE_STATUS.with_suffix(".new")
    tmp.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    tmp.replace(QUEUE_STATUS)
    print(f"{document['updated_utc']} {state} {kwargs}", flush=True)


def require_environment():
    if os.geteuid() != 0:
        raise RuntimeError("Start mit sudo: sudo python3 tools/queue-next-vault.py install")
    for path in [CODE / "models.json", CODE / ".env", CODE / "start.sh",
                 CODE / "compose.yaml", VAULT / "models", DOT]:
        if not path.exists():
            raise RuntimeError(f"Bestehender Vault-Pfad fehlt: {path}")
    if subprocess.check_output(["stat", "-f", "-c", "%T", str(VAULT)],
                               text=True).strip() != "btrfs":
        raise RuntimeError("Vault-Ziel muss btrfs auf dem Datenvolume sein")
    subprocess.run(["docker", "compose", "version"], cwd=CODE, check=True,
                   stdout=subprocess.DEVNULL)


def remote_text(name: str) -> str:
    url = f"{SOURCE}/{name}"
    with urlopen(Request(url, headers={"User-Agent": "ModelVault-Queue/1.0"}), timeout=45) as reply:
        result = reply.read(2_000_001)
    if len(result) > 2_000_000:
        raise RuntimeError("GitHub-Datei zu gross")
    return result.decode("utf-8")


def selected(catalog: dict) -> dict:
    result = {}
    for item in catalog.get("models", []):
        tier = item.get("tier")
        if tier not in TIERS:
            continue
        repo = item["repo"]
        if repo in result:
            raise RuntimeError("Doppelter Vault-Repo-Eintrag: " + repo)
        if item.get("enabled") is not True:
            raise RuntimeError("Vault-Eintrag deaktiviert: " + repo)
        required, allowed = item.get("required_patterns", []), item.get("allow_patterns", [])
        if not required or "*" in allowed or not set(required).issubset(set(allowed)):
            raise RuntimeError("Unerwartete Pflichtdateien: " + repo)
        result[repo] = item
    for tier, names in EXPECTED_REPOS.items():
        got = {repo for repo, item in result.items() if item["tier"] == tier}
        if got != names:
            raise RuntimeError(f"Repo-Menge fuer {tier} stimmt nicht: {got}")
    return result


def merged_catalog() -> dict:
    original = json.loads((CODE / "models.json").read_text(encoding="utf-8"))
    pending = json.loads(PENDING.read_text(encoding="utf-8"))
    wanted = selected(pending)
    old_by_name = {item["repo"]: item for item in original["models"]}
    if len(old_by_name) != len(original["models"]):
        raise RuntimeError("Lokaler Katalog enthaelt doppelte Eintraege")
    for name, item in wanted.items():
        if name in old_by_name:
            if item != old_by_name[name]:
                raise RuntimeError("Abweichende lokale Auswahl nicht ueberschreiben: " + name)
        else:
            original["models"].append(item)
    # Recheck against the merged selection.
    selected(original)
    return original


def docker_running() -> bool:
    p = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", "model-vault"],
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return p.returncode == 0 and p.stdout.strip() == "true"


def finished_status() -> bool:
    if (DOT / "paused").exists() or not STATUS.is_file():
        return False
    try:
        data = json.loads(STATUS.read_text(encoding="utf-8"))
        stamp = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return False
        age = abs((datetime.now(timezone.utc) - stamp).total_seconds())
        return (
            age < 120 and data.get("phase") == "complete"
            and data.get("verified_complete") is True
            and data.get("all_models", 0) > 0 and not data.get("active")
        )
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError):
        return False


def missing_bytes(merged: dict) -> int:
    existing = {}
    for model in merged["models"]:
        if model.get("tier") not in TIERS or not model.get("enabled"):
            continue
        repo = model["repo"]
        subtotal = 0
        for name in model["required_patterns"]:
            root = VAULT / "models" / repo
            path = root / name
            partial = path.with_name(path.name + ".part")
            if path.is_file() and not path.is_symlink():
                subtotal += path.stat().st_size
            elif partial.is_file() and not partial.is_symlink():
                subtotal += partial.stat().st_size
        existing[repo] = subtotal
    outstanding = 0
    for tier, estimates in ESTIMATED_BYTES.items():
        already = sum(existing.get(r, 0) for r in EXPECTED_REPOS[tier])
        outstanding += max(0, estimates - already)
    return outstanding


def store_file(target: Path, content: str, mode: int):
    temp = target.with_name(target.name + ".queue.new")
    temp.write_text(content, encoding="utf-8")
    os.chmod(temp, mode)
    os.replace(temp, target)


def activate():
    merged = merged_catalog()
    needed = missing_bytes(merged)
    free = shutil.disk_usage(VAULT).free
    minimum = int(needed * 1.15) + 12_000_000_000
    if free < minimum:
        raise RuntimeError(
            f"Zu wenig NAS-Platz: frei {free / 1e9:.1f} GB, benoetigt "
            f"mindestens {minimum / 1e9:.1f} GB (Schaetzung)")
    env_path = CODE / ".env"
    env = env_path.read_text(encoding="utf-8")
    if len(re.findall(r"(?m)^SELECT_TIERS=", env)) != 1:
        raise RuntimeError("SELECT_TIERS muss genau einmal in .env stehen")
    if docker_running() and not finished_status():
        raise RuntimeError("Laufender Vault ist nicht mehr als vollstaendig bestaetigt")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_env = CODE / f".env.before-queue-{stamp}"
    backup_catalog = CODE / f"models.json.before-queue-{stamp}"
    backup_verifier = CODE / f"tools/verify-abliterated.py.before-queue-{stamp}"
    old_verifier = CODE / "tools/verify-abliterated.py"
    shutil.copy2(env_path, backup_env)
    shutil.copy2(CODE / "models.json", backup_catalog)
    if old_verifier.is_file():
        shutil.copy2(old_verifier, backup_verifier)
    selection = re.sub(r"(?m)^SELECT_TIERS=.*$", "SELECT_TIERS=DS41,OPEN3", env)
    record("switching", free_gb=round(free / 1e9, 2), missing_estimated_gb=round(needed / 1e9, 2))
    try:
        store_file(CODE / "models.json", json.dumps(merged, indent=2) + "\n", 0o644)
        store_file(old_verifier, VERIFY_PENDING.read_text(encoding="utf-8"), 0o644)
        store_file(env_path, selection, env_path.stat().st_mode & 0o777)
        subprocess.run(["bash", str(CODE / "start.sh"), str(VAULT)],
                       cwd=CODE, check=True, timeout=600)
    except Exception:
        # Restore local files. Do not attempt a second implicit container restart.
        shutil.copy2(backup_env, env_path)
        shutil.copy2(backup_catalog, CODE / "models.json")
        if backup_verifier.is_file():
            shutil.copy2(backup_verifier, old_verifier)
        raise
    record("started", selection="DS41,OPEN3",
           message="Bestehender Vault laedt neue Auswahl; ABL/ORCA bleiben unangetastet")


def worker():
    with LOCK.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Queue-Watcher laeuft bereits; kein zweiter Start.", flush=True)
            return
        record("waiting", message="Warte auf Abschluss des aktuell laufenden Model Vault")
        initially_running = docker_running()
        last_log = time.monotonic()
        seen_once = False
        while True:
            running = docker_running()
            if initially_running and not running:
                raise RuntimeError("Alter Vault gestoppt, bevor Abschluss gesichert war; keine Uebernahme")
            if not running and not initially_running:
                # Already stopped: only switch if the final on-disk status
                # still reports a successful completed selection.
                data = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.is_file() else {}
                if data.get("phase") != "complete" or data.get("verified_complete") is not True:
                    raise RuntimeError("Alter Vault gestoppt, letzter Status nicht komplett")
                break
            done = finished_status()
            if done and seen_once:
                break
            seen_once = done
            if time.monotonic() - last_log > 300:
                print("Warte weiter; bestehende Downloads bleiben unveraendert", flush=True)
                last_log = time.monotonic()
            time.sleep(45)
        if docker_running() and not finished_status():
            raise RuntimeError("Status vor Umschalten nicht mehr komplett")
        activate()


def install():
    require_environment()
    # Check before writing shared pending files. Existing queue must not be changed.
    if QUEUE_STATUS.exists():
        old = json.loads(QUEUE_STATUS.read_text(encoding="utf-8"))
        if old.get("state") in ("waiting", "switching") and old.get("pid"):
            try:
                os.kill(old["pid"], 0)
                cmdline = Path(f"/proc/{old['pid']}/cmdline").read_bytes()
                if b"queue-next-vault.py" in cmdline:
                    print(f"Queue bereits aktiv (PID {old['pid']})")
                    return
            except (ProcessLookupError, PermissionError, FileNotFoundError):
                pass
    # Fetch and validate now, while the current downloader runs unchanged.
    catalog = remote_text("models.json")
    verifier = remote_text("tools/verify-abliterated.py")
    selected(json.loads(catalog))
    if '"OPEN3": 3' not in verifier or '"DS41": 2' not in verifier:
        raise RuntimeError("Archivpruefer fehlt oder ist veraltet")
    PENDING.write_text(catalog, encoding="utf-8")
    VERIFY_PENDING.write_text(verifier, encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "worker"],
            cwd=CODE, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True)
    document = {
        "state": "waiting", "pid": proc.pid,
        "tiers": list(TIERS), "catalog_commit": PIN,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
    }
    QUEUE_STATUS.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"Queue eingerichtet (PID {proc.pid}). SSH kann geschlossen werden.")
    print(f"Status: cat {QUEUE_STATUS}")
    print(f"Log:    tail -f {LOG}")
    print("Hinweis: Bei NAS-Neustart muss der Watcher erneut gestartet werden.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "worker"])
    args = parser.parse_args()
    require_environment()
    if args.action == "install":
        install()
    else:
        try:
            worker()
        except Exception as exc:
            record("blocked", error=str(exc))
            raise


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"STOP: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
