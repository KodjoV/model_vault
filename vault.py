#!/usr/bin/env python3
"""Resumable Hugging Face model archive with durable total progress dashboard.

Metadata: huggingface_hub (immutable repository commit + file sizes + LFS SHA).
Transport: requests HTTP Range to .part then atomic replace. Per-file SHA256.
Runtime: standard ThreadingHTTPServer, background planner/downloader, JSON state.
No credentials are sent to the browser. Logs and status stay on the NAS.
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fnmatch
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import threading
import time
from urllib.parse import quote, urlparse

import requests
from huggingface_hub import HfApi

ROOT = Path(os.environ.get('VAULT_ROOT', '/vault')).resolve()
CONFIG = Path(os.environ.get('VAULT_CONFIG', '/app/models.json'))
DOT = ROOT / '.vault'
PLAN_FILE = DOT / 'plan.json'
STATUS_FILE = DOT / 'status.json'
LOG_FILE = DOT / 'events.log'
PAUSE_FILE = DOT / 'paused'
UI_PASSWORD = os.environ.get('UI_PASSWORD', '')
TIERS = {s.strip() for s in os.environ.get('SELECT_TIERS', 'P0').split(',') if s.strip()}
WORKERS = max(1, min(int(os.environ.get('WORKERS', '2')), 4))
INTERVAL = max(1, min(int(os.environ.get('PROGRESS_INTERVAL', '3')), 30))
HF_TOKEN = os.environ.get('HF_TOKEN', '').strip() or None
STOP = threading.Event()
RETRY = threading.Event()
LOCK = threading.RLock()
PLAN: dict = {'models': {}, 'created_at': ''}
RUNTIME: dict = {'active': {}, 'phase': 'starting', 'last_error': None}
STARTED = time.monotonic()
LAST_PROGRESS = None
SPEED_SAMPLES: list[tuple[float, int]] = []


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def atomic_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path.with_name(path.name + '.tmp')
    with target.open('w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    target.replace(path)


def load_json(path: Path, default):
    if path.exists():
        with path.open(encoding='utf-8') as f:
            return json.load(f)
    return default


def log(message: str):
    line = f'{now()} {message}'
    print(line, flush=True)
    try:
        with LOG_FILE.open('a', encoding='utf-8') as f:
            f.write(line + '\n')
    except OSError:
        pass


def save_plan():
    with LOCK:
        atomic_json(PLAN_FILE, PLAN)


def is_safe_path(path: str) -> bool:
    p = PurePosixPath(path)
    return bool(path) and not p.is_absolute() and all(part not in ('.', '..', '') for part in path.split('/')) and '\\' not in path


def local_path(repo: str, path: str) -> Path:
    if not is_safe_path(path):
        raise ValueError(f'Unsicherer Repo-Pfad: {path!r}')
    return ROOT / 'models' / repo / Path(path)


def wanted(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, p) for p in patterns)


def get_config() -> list[dict]:
    data = load_json(CONFIG, {})
    models = data.get('models', [])
    seen = set()
    out = []
    for model in models:
        repo = model['repo']
        if repo in seen:
            raise ValueError(f'Modell doppelt in models.json: {repo}')
        seen.add(repo)
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError(f'Ungueltiger HuggingFace Repo-Name: {repo}')
        if model.get('enabled', True) and model.get('tier', 'P0') in TIERS:
            out.append(model)
    return out


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({'User-Agent': 'ModelVault-NAS/1.0 (archival tool)'})
    if HF_TOKEN:
        s.headers['Authorization'] = f'Bearer {HF_TOKEN}'
    return s


def hf_url(repo: str, sha: str, name: str) -> str:
    return f'https://huggingface.co/{repo}/resolve/{sha}/{quote(name, safe="/")}?download=true'


def remote_size(s: requests.Session, url: str) -> int | None:
    try:
        r = s.head(url, allow_redirects=True, timeout=(20, 45))
        r.raise_for_status()
        # HF often includes X-Linked-Size for LFS; final CDN has Content-Length.
        for field in ('X-Linked-Size', 'Content-Length'):
            size = r.headers.get(field)
            if size and size.isdecimal():
                return int(size)
    except requests.RequestException:
        return None
    return None


def plan_one(api: HfApi, cfg: dict) -> dict:
    repo = cfg['repo']
    info = api.model_info(repo_id=repo, files_metadata=True, token=HF_TOKEN)
    sha = getattr(info, 'sha', None)
    if not sha or not re.fullmatch('[a-f0-9]{40}', sha):
        raise RuntimeError(f'Keine unveraenderliche 40-stellige Revision fuer {repo}')
    patterns = cfg.get('allow_patterns') or ['*']
    selected = [f for f in getattr(info, 'siblings', []) if wanted(f.rfilename, patterns)]
    if not selected:
        raise RuntimeError(f'Keine Dateien durch allow_patterns gefunden: {patterns}')
    for p in cfg.get('required_patterns', []):
        if not any(fnmatch.fnmatchcase(f.rfilename, p) for f in selected):
            raise RuntimeError(f'Pflicht-Dateimuster fehlt in {repo}: {p}')
    ss = session()
    files = []
    for f in sorted(selected, key=lambda item: item.rfilename):
        filename = f.rfilename
        if not is_safe_path(filename):
            raise RuntimeError(f'Unsicherer Dateiname von HuggingFace: {filename}')
        size = getattr(f, 'size', None)
        if size is None:
            size = remote_size(ss, hf_url(repo, sha, filename))
        if size is None or size < 0:
            raise RuntimeError(f'Keine Dateigroesse ermittelbar: {repo}/{filename} (Gesamtanzeige unzuverlaessig)')
        lfs = getattr(f, 'lfs', None)
        expected = lfs.get('sha256') if isinstance(lfs, dict) else None
        files.append({'path': filename, 'size': int(size), 'lfs_sha256': expected})
    return {
        'repo': repo, 'sha': sha, 'tier': cfg.get('tier', 'P0'),
        'note': cfg.get('note', ''), 'patterns': patterns,
        'license_card': str(getattr(getattr(info, 'card_data', None), 'license', '') or ''),
        'files': files, 'verified': {}, 'state': 'pending',
        'error': '', 'planned_at': now(), 'completed_at': None,
    }


def set_phase(phase: str, **kwargs):
    with LOCK:
        RUNTIME['phase'] = phase
        RUNTIME.update(kwargs)


def set_model(repo: str, state: str, error: str = ''):
    with LOCK:
        if repo in PLAN['models']:
            PLAN['models'][repo]['state'] = state
            PLAN['models'][repo]['error'] = error[:1200]
    save_plan()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            buf = f.read(8 * 1024 * 1024)
            if not buf:
                return digest.hexdigest()
            digest.update(buf)


class StopRequested(Exception):
    pass


class AuthenticationError(Exception):
    pass


def wait_while_paused():
    while PAUSE_FILE.exists() and not STOP.is_set():
        set_phase('paused')
        time.sleep(0.5)
    if STOP.is_set():
        raise StopRequested()


def download_file(repo: str, sha: str, file: dict, model: dict):
    filename, expected_size = file['path'], file['size']
    path = local_path(repo, filename)
    temp = path.with_name(path.name + '.part')
    path.parent.mkdir(parents=True, exist_ok=True)
    wait_while_paused()

    # Trust prior successfully verified file if size remains correct.
    with LOCK:
        previous = model['verified'].get(filename)
    if previous and path.is_file() and path.stat().st_size == expected_size:
        return

    # This can happen after crash exactly between rename and metadata write.
    # Hash it before deciding whether to redownload.
    if path.exists() and path.stat().st_size == expected_size:
        set_phase('verifying')
        hash_value = sha256_file(path)
        lfs = file.get('lfs_sha256')
        if lfs and lfs != hash_value:
            raise RuntimeError(f'SHA256 falsch: {repo}/{filename}; Datei bleibt zur Diagnose liegen')
        with LOCK:
            model['verified'][filename] = {'sha256': hash_value, 'bytes': expected_size, 'verified_at': now(), 'matched_remote_lfs_sha256': bool(lfs)}
        save_plan()
        return
    if path.exists() and path.stat().st_size != expected_size:
        raise RuntimeError(f'Vorhandene Datei mit falscher Groesse: {path}. Bitte manuell klaeren.')

    url = hf_url(repo, sha, filename)
    ss = session()
    attempts = 0
    while attempts < 10:
        wait_while_paused()
        offset = temp.stat().st_size if temp.exists() else 0
        if offset > expected_size:
            raise RuntimeError(f'.part groesser als Server-Datei: {temp}')
        if offset == expected_size:
            if expected_size == 0 and not temp.exists():
                temp.touch()
            break
        attempts += 1
        headers = {'Range': f'bytes={offset}-'} if offset else {}
        with LOCK:
            RUNTIME['phase'] = 'downloading'
            RUNTIME['active'][repo + '/' + filename] = {'offset': offset, 'size': expected_size, 'attempt': attempts}
        try:
            with ss.get(url, headers=headers, stream=True, timeout=(25, 90), allow_redirects=True) as response:
                if response.status_code in (401, 403):
                    raise AuthenticationError(f'HTTP {response.status_code} {repo}/{filename} (HF_TOKEN/Gating/Permission)')
                if response.status_code == 429:
                    raise requests.HTTPError(f'HTTP 429 Rate Limit fuer {repo}/{filename}')
                response.raise_for_status()
                if offset and response.status_code == 200:
                    # Server ignored Range. Restart file safely instead of appending corrupted bytes.
                    log(f'Range ignoriert, Download beginnt erneut: {repo}/{filename}')
                    offset = 0
                    temp.unlink(missing_ok=True)
                elif offset:
                    cr = response.headers.get('Content-Range', '')
                    if response.status_code != 206 or not cr.startswith(f'bytes {offset}-'):
                        raise RuntimeError(f'Ungueltige Range-Antwort {response.status_code} Content-Range={cr!r}')
                # Verify server total if available.
                cr = response.headers.get('Content-Range', '')
                if '/' in cr:
                    suffix = cr.rsplit('/', 1)[1]
                    if suffix.isdecimal() and int(suffix) != expected_size:
                        raise RuntimeError(f'Dateigroesse serverseitig geaendert: {repo}/{filename}')
                disk_free = shutil.disk_usage(ROOT).free
                if disk_free < min(expected_size - offset, 512 * 1024 * 1024) + 256 * 1024 * 1024:
                    raise RuntimeError(f'Zu wenig freier Speicher fuer {repo}/{filename}: {disk_free/2**30:.2f} GiB frei')
                mode = 'ab' if offset else 'wb'
                with temp.open(mode) as f:
                    count_since_sync = 0
                    for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                        if STOP.is_set():
                            raise StopRequested()
                        if PAUSE_FILE.exists():
                            break  # preserve part; outer loop waits and resumes with Range
                        if chunk:
                            f.write(chunk)
                            offset += len(chunk)
                            count_since_sync += len(chunk)
                            with LOCK:
                                if repo + '/' + filename in RUNTIME['active']:
                                    RUNTIME['active'][repo + '/' + filename]['offset'] = offset
                            if count_since_sync >= 32 * 1024 * 1024:
                                f.flush()
                                os.fsync(f.fileno())
                                count_since_sync = 0
                if temp.stat().st_size == expected_size:
                    break
                if PAUSE_FILE.exists():
                    attempts -= 1
                    continue
                log(f'Unterbrochen {repo}/{filename}; Resume bei {temp.stat().st_size:,}/{expected_size:,}')
        except AuthenticationError:
            raise
        except StopRequested:
            raise
        except (requests.RequestException, OSError) as ex:
            log(f'NETZ/IO Fehler {repo}/{filename}: {type(ex).__name__}: {ex} (Versuch {attempts}/10)')
        if attempts < 10:
            delay = min(5 * (2 ** min(attempts-1, 4)), 90)
            STOP.wait(delay)

    with LOCK:
        RUNTIME['active'].pop(repo + '/' + filename, None)
    if not temp.exists() or temp.stat().st_size != expected_size:
        raise RuntimeError(f'Download unvollstaendig {repo}/{filename}: {temp.stat().st_size if temp.exists() else 0}/{expected_size} Bytes')

    set_phase('verifying')
    calculated = sha256_file(temp)
    remote_hash = file.get('lfs_sha256')
    if remote_hash and calculated != remote_hash:
        raise RuntimeError(f'Checksum-Fehler {repo}/{filename}: erwartet {remote_hash}, erhalten {calculated}; .part bleibt erhalten')
    temp.replace(path)
    with LOCK:
        model['verified'][filename] = {'sha256': calculated, 'bytes': expected_size, 'verified_at': now(), 'matched_remote_lfs_sha256': bool(remote_hash)}
    save_plan()
    log(f'DATEI OK {repo}/{filename} ({expected_size / 2**30:.3f} GiB)')


def finish_model(repo: str, model: dict):
    if len(model['verified']) < len(model['files']):
        raise RuntimeError(f'Nur {len(model["verified"])}/{len(model["files"])} Dateien verifiziert')
    meta = {'repo': repo, 'revision': model['sha'], 'url': f'https://huggingface.co/{repo}/tree/{model["sha"]}',
            'captured': now(), 'license_card': model.get('license_card'), 'note': model['note'],
            'files': [{**f, **model['verified'].get(f['path'], {})} for f in model['files']]}
    dest = ROOT / 'models' / repo
    atomic_json(dest / 'MODEL_VAULT_MANIFEST.json', meta)
    sha = dest / 'MODEL_VAULT_SHA256SUMS.txt'
    sha.write_text(''.join(f'{model["verified"][f["path"]]["sha256"]}  {f["path"]}\n' for f in model['files']), encoding='utf-8')
    with LOCK:
        model['state'] = 'complete'
        model['completed_at'] = now()
        model['error'] = ''
    save_plan()
    log(f'MODELL KOMPLETT {repo} @ {model["sha"]}')


def plan_models() -> list[dict]:
    config = get_config()
    api = HfApi(token=HF_TOKEN)
    with LOCK:
        PLAN.setdefault('created_at', now())
        PLAN.setdefault('models', {})
    for n, cfg in enumerate(config, start=1):
        repo = cfg['repo']
        if repo in PLAN['models'] and PLAN['models'][repo].get('sha'):
            existing = PLAN['models'][repo]
            if existing.get('state') == 'complete':
                missing = [f['path'] for f in existing['files']
                           if not local_path(repo, f['path']).is_file()
                           or local_path(repo, f['path']).stat().st_size != f['size']]
                if missing:
                    log(f'INTEGRITAET: {repo} hat {len(missing)} fehlende/falsch grosse Dateien; erneuter Downloadversuch')
                    existing['state'] = 'pending'
                    for filename in missing:
                        existing['verified'].pop(filename, None)
                    save_plan()
            continue
        set_phase('planning', planning=f'{n}/{len(config)}', planning_repo=repo)
        try:
            log(f'PLAN {n}/{len(config)} {repo}')
            model = plan_one(api, cfg)
            with LOCK:
                PLAN['models'][repo] = model
            save_plan()
            log(f'PLAN OK {repo}: {len(model["files"])} Dateien, {sum(x["size"] for x in model["files"]) / 2**30:.2f} GiB')
        except Exception as exc:
            with LOCK:
                PLAN['models'][repo] = {'repo': repo, 'tier': cfg.get('tier'), 'note': cfg.get('note', ''),
                                       'state': 'blocked', 'error': f'{type(exc).__name__}: {exc}',
                                       'files': [], 'verified': {}}
            save_plan()
            log(f'PLAN BLOCKIERT {repo}: {type(exc).__name__}: {exc}')
    return config


def worker_loop():
    try:
        while not STOP.is_set():
            wait_while_paused()
            config = plan_models()
            errors = 0
            for cfg in config:
                if STOP.is_set():
                    raise StopRequested()
                wait_while_paused()
                repo = cfg['repo']
                with LOCK:
                    model = PLAN['models'].get(repo)
                if not model or model['state'] == 'blocked':
                    errors += 1
                    continue
                if model['state'] == 'complete':
                    continue
                if not model['files']:
                    errors += 1
                    continue
                set_model(repo, 'downloading')
                set_phase('downloading', current_repo=repo)
                log(f'START {repo} mit {WORKERS} parallelen Dateitransfers')
                try:
                    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                        futures = [pool.submit(download_file, repo, model['sha'], f, model)
                                   for f in model['files']]
                        failures = []
                        for future in as_completed(futures):
                            try:
                                future.result()
                            except StopRequested:
                                raise
                            except Exception as exc:
                                failures.append(str(exc))
                    if failures:
                        raise RuntimeError('; '.join(failures[:4]))
                    finish_model(repo, model)
                except StopRequested:
                    raise
                except Exception as exc:
                    errors += 1
                    set_model(repo, 'error', f'{type(exc).__name__}: {exc}')
                    log(f'MODELL FEHLER {repo}: {type(exc).__name__}: {exc}')
                finally:
                    with LOCK:
                        RUNTIME['active'] = {}
            set_phase('idle' if errors else 'complete', current_repo=None)
            if errors:
                log(f'{errors} Modelle blockiert/fehlerhaft; automatische Wiederholung in 10 Minuten oder via Retry-Knopf')
                for i in range(600):
                    if STOP.is_set() or RETRY.is_set():
                        break
                    time.sleep(1)
                RETRY.clear()
                # Re-plan blocked entries (access restored, transient metadata error or patterns changed).
                with LOCK:
                    for cfg in config:
                        repo = cfg['repo']
                        if PLAN['models'].get(repo, {}).get('state') == 'blocked':
                            del PLAN['models'][repo]
                save_plan()
            else:
                # Wait indefinitely, but wake on new selections/config after manual restart.
                while not STOP.is_set() and not RETRY.is_set():
                    time.sleep(1)
                RETRY.clear()
    except StopRequested:
        log('Stop angefordert; Teil-Downloads bleiben erhalten.')
        set_phase('stopped')
    except Exception as exc:
        log(f'WORKER ABGESTUERZT: {type(exc).__name__}: {exc}')
        set_phase('fatal', last_error=str(exc))


def collect_status() -> dict:
    global LAST_PROGRESS
    selected = get_config()
    with LOCK:
        active = dict(RUNTIME['active'])
        phase = RUNTIME['phase']
        current_repo = RUNTIME.get('current_repo')
        planning = RUNTIME.get('planning')
        last_error = RUNTIME.get('last_error')
        models_snap = json.loads(json.dumps(PLAN.get('models', {})))
    expected = 0
    downloaded = 0
    all_files = 0
    verified_files = 0
    all_models = len(selected)
    complete_models = 0
    detail = []
    unplanned = 0
    for cfg in selected:
        repo = cfg['repo']
        model = models_snap.get(repo)
        if not model or not model.get('sha'):
            unplanned += 1
            detail.append({'repo': repo, 'tier': cfg.get('tier'), 'status': model.get('state', 'planning') if model else 'planning',
                           'error': model.get('error', '') if model else '', 'bytes': 0, 'total': None,
                           'verified_files': 0, 'files': None})
            continue
        current = 0
        total = 0
        files = model['files']
        verified = model['verified']
        for f in files:
            path = local_path(repo, f['path'])
            part = path.with_name(path.name + '.part')
            size = int(f['size'])
            total += size
            value = path.stat().st_size if path.is_file() else 0
            if part.is_file():
                value = max(value, part.stat().st_size)
            current += min(value, size)
            if f['path'] in verified and path.is_file() and path.stat().st_size == size:
                verified_files += 1
        expected += total
        downloaded += current
        all_files += len(files)
        if model.get('state') == 'complete' and sum(1 for f in files if f['path'] in verified and local_path(repo, f['path']).is_file() and local_path(repo, f['path']).stat().st_size == f['size']) == len(files):
            complete_models += 1
        detail.append({'repo': repo, 'tier': model['tier'], 'status': model['state'], 'error': model.get('error', ''),
                       'bytes': current, 'total': total, 'files': len(files), 'verified_files': len(verified),
                       'revision': model['sha'], 'note': model.get('note', '')})
    ts = time.monotonic()
    # Keep ~30 seconds of recent samples; speed is measured download-rate, not verification throughput.
    SPEED_SAMPLES.append((ts, downloaded))
    SPEED_SAMPLES[:] = [x for x in SPEED_SAMPLES if ts - x[0] <= 30]
    speed = 0.0
    if len(SPEED_SAMPLES) > 1:
        elapsed = SPEED_SAMPLES[-1][0] - SPEED_SAMPLES[0][0]
        gain = SPEED_SAMPLES[-1][1] - SPEED_SAMPLES[0][1]
        if elapsed > 0:
            speed = max(0.0, gain / elapsed)
    complete_size = unplanned == 0
    percent = round(downloaded * 100 / expected, 2) if complete_size and expected > 0 else None
    remaining = max(0, expected - downloaded) if complete_size else None
    eta = int(remaining / speed) if remaining is not None and speed > 128 * 1024 else None
    free = shutil.disk_usage(ROOT).free
    payload = {
        'updated_at': now(), 'phase': 'paused' if PAUSE_FILE.exists() else phase, 'planning': planning,
        'current_repo': current_repo, 'all_models': all_models, 'complete_models': complete_models,
        'all_files': all_files if complete_size else None, 'verified_files': verified_files,
        'expected_bytes': expected if complete_size else None, 'planned_bytes': expected,
        'downloaded_bytes': downloaded, 'percent': percent, 'remaining_bytes': remaining,
        'speed_bytes_second': round(speed, 1), 'eta_seconds': eta, 'free_disk_bytes': free,
        'unplanned_models': unplanned, 'active': active, 'models': detail,
        'last_error': last_error, 'paused': PAUSE_FILE.exists(),
        'verified_complete': complete_models == all_models and all_models > 0,
    }
    return payload


def monitor_loop():
    while not STOP.is_set():
        try:
            status = collect_status()
            atomic_json(STATUS_FILE, status)
        except Exception as exc:
            log(f'STATUS-FEHLER: {type(exc).__name__}: {exc}')
        STOP.wait(INTERVAL)


HTML = r'''<!doctype html><html lang="de"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Model Vault – UGREEN</title><style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,sans-serif;background:#0c111c;color:#e8eef9}
body{max-width:1120px;margin:30px auto;padding:0 18px}h1{font-size:28px;letter-spacing:-.5px}
header, .line{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}
.box{background:#151d2d;border:1px solid #2a3548;border-radius:12px;padding:20px;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px}
.metric{background:#0e1624;padding:15px;border-radius:9px}.metric b{display:block;font-size:23px;font-variant-numeric:tabular-nums}
.muted{color:#9aaac2}.bar{height:15px;border-radius:20px;background:#293447;overflow:hidden}
.bar>div{height:100%;width:0%;background:#6b9cf4;transition:width .7s}.smallbar{height:7px;margin:6px 0 10px}
button{background:#273a58;color:#f5f8ff;border:1px solid #3b5278;border-radius:7px;padding:9px 16px;cursor:pointer}
button:hover{background:#36547f}.warn{color:#f2b571}.bad{color:#f48890}.ok{color:#7dd7ad}
.entry{border-top:1px solid #2b3748;padding:13px 0}.entry strong{overflow-wrap:anywhere}code{overflow-wrap:anywhere}
pre{white-space:pre-wrap;word-break:break-word;color:#a1b1c9;font-size:12px;max-height:240px;overflow:auto}
footer{color:#8ca0bb;font-size:13px;margin:25px 0}
</style></head><body>
<header><div><h1>Model Vault <small class="muted">/ UGREEN</small></h1><p class="muted">Dauerhaftes Archiv · Downloads mit Resume · verifizierte SHA256</p></div><div><button id="toggle">Pause</button> <button id="retry">Fehler erneut versuchen</button></div></header>
<div class="box"><div class="line"><h2>Gesamtfortschritt</h2><strong id="percent">–</strong></div>
<div class="bar"><div id="allbar"></div></div><p id="main">Status wird geladen …</p>
<div class="grid"><div class="metric"><span class="muted">Übertragen / Gesamt</span><b id="size">–</b></div>
<div class="metric"><span class="muted">Modelle komplett</span><b id="models">–</b></div>
<div class="metric"><span class="muted">Dateien verifiziert</span><b id="files">–</b></div>
<div class="metric"><span class="muted">Downloadrate</span><b id="speed">–</b></div>
<div class="metric"><span class="muted">Restzeit (Schätzung)</span><b id="eta">–</b></div>
<div class="metric"><span class="muted">Freier NAS-Speicher</span><b id="disk">–</b></div></div></div>
<div class="box"><h2>Modelle</h2><div id="entries"></div></div>
<div class="box"><h2>Aktive Downloads</h2><pre id="active">–</pre></div>
<div class="box"><h2>Letzte Ereignisse</h2><pre id="logs">–</pre></div>
<footer>Aktualisierung alle 3 Sekunden; Server-Zeitpunkt: <span id="time">–</span>. Nur im vertrauenswürdigen Netz/Tailscale betreiben. NAS-RAID ist kein Backup.</footer>
<script>
const el=x=>document.getElementById(x);
const gib=n=>n==null?'–':(n/1073741824).toFixed(2)+' GiB';
const duration=s=>{if(s==null)return '–';let h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h+'h '+m+'m';};
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let paused=false;
async function tick(){try{
 const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);
 const d=await r.json();paused=d.paused;
 el('percent').textContent=d.percent==null?'Planung läuft …':d.percent.toFixed(2)+' %';
 el('allbar').style.width=(d.percent||0)+'%';
 el('main').innerHTML='Phase: <b>'+esc(d.phase)+'</b> · '+
   (d.verified_complete?'<span class="ok">Alle ausgewählten Modelle vollständig archiviert und verifiziert</span>':
   'Downloads '+(d.unplanned_models?'· noch '+d.unplanned_models+' Modelle ohne ermittelten Umfang':'') );
 el('size').textContent=gib(d.downloaded_bytes)+' / '+gib(d.expected_bytes);
 el('models').textContent=d.complete_models+' / '+d.all_models;
 el('files').textContent=d.verified_files+' / '+(d.all_files==null?'…':d.all_files);
 el('speed').textContent=(d.speed_bytes_second/1048576).toFixed(1)+' MiB/s';
 el('eta').textContent=duration(d.eta_seconds);el('disk').textContent=gib(d.free_disk_bytes);
 el('toggle').textContent=d.paused?'Fortsetzen':'Pause';
 el('entries').innerHTML=d.models.map(m=>{
  let p=m.total?100*m.bytes/m.total:0,cls=['complete'].includes(m.status)?'ok':
  ['blocked','error'].includes(m.status)?'bad':'muted';
  return '<div class="entry"><div class="line"><strong>'+esc(m.repo)+'</strong><span class="'+cls+'">'+esc(m.status)+'</span></div>'+
   '<div class="bar smallbar"><div style="width:'+p.toFixed(2)+'%"></div></div><div class="line muted"><small>'+gib(m.bytes)+' / '+gib(m.total)+' · '+(m.verified_files||0)+' / '+(m.files==null?'…':m.files)+' Dateien geprüft</small><small>'+p.toFixed(1)+' %</small></div>'+
   (m.error?'<p class="bad">'+esc(m.error)+'</p>':'')+'</div>';
 }).join('');
 el('active').textContent=Object.keys(d.active).length?Object.entries(d.active).map(([k,v])=>k+' : '+gib(v.offset)+' / '+gib(v.size)+' (Versuch '+v.attempt+')').join('\n'):'Keine aktive Datei (Planung, Prüfung oder Leerlauf)';
 el('time').textContent=d.updated_at;
 const logs=await fetch('/api/logs',{cache:'no-store'});if(logs.ok) el('logs').textContent=await logs.text();
 }catch(e){el('main').innerHTML='<span class="bad">Verbindung unterbrochen: '+esc(e.message)+' – prüfe NAS/Docker.</span>';}}
async function action(path){await fetch(path,{method:'POST'});tick();}
el('toggle').onclick=()=>action(paused?'/api/resume':'/api/pause');
el('retry').onclick=()=>action('/api/retry');
tick();setInterval(tick,3000);
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    server_version = 'ModelVault/1.0'

    def auth_ok(self) -> bool:
        raw = self.headers.get('Authorization', '')
        if not raw.startswith('Basic '):
            return False
        try:
            import hmac
            user_pass = base64.b64decode(raw[6:], validate=True).decode('utf-8')
            return hmac.compare_digest(user_pass, 'vault:' + UI_PASSWORD)
        except (ValueError, UnicodeError):
            return False

    def respond(self, code: int, data: str | bytes, content_type: str = 'text/plain; charset=utf-8'):
        b = data if isinstance(data, bytes) else data.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(b)

    def _authorized(self):
        if self.auth_ok():
            return True
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="UGREEN Model Vault"')
        self.send_header('Content-Length', '0')
        self.end_headers()
        return False

    def do_GET(self):
        if not self._authorized():
            return
        endpoint = urlparse(self.path).path
        if endpoint == '/':
            self.respond(200, HTML, 'text/html; charset=utf-8')
        elif endpoint == '/api/status':
            self.respond(200, json.dumps(load_json(STATUS_FILE, collect_status())), 'application/json')
        elif endpoint == '/api/logs':
            if LOG_FILE.exists():
                with LOG_FILE.open(encoding='utf-8') as f:
                    from collections import deque
                    tail = ''.join(deque(f, maxlen=32))
            else:
                tail = ''
            self.respond(200, tail)
        else:
            self.respond(404, 'Not found')

    def do_POST(self):
        if not self._authorized():
            return
        endpoint = urlparse(self.path).path
        if endpoint == '/api/pause':
            PAUSE_FILE.write_text(now(), encoding='utf-8')
            log('PAUSE angefordert per Web')
        elif endpoint == '/api/resume':
            PAUSE_FILE.unlink(missing_ok=True)
            log('RESUME angefordert per Web')
        elif endpoint == '/api/retry':
            RETRY.set()
            log('RETRY angefordert per Web')
        else:
            return self.respond(404, 'Unknown action')
        self.respond(200, '{"ok":true}', 'application/json')

    def log_message(self, fmt, *args):
        # No credentials ever logged.
        pass


def shutdown(signum, frame):
    STOP.set()


def main():
    if not UI_PASSWORD or UI_PASSWORD.lower() in ('changeme', 'password', 'example'):
        raise SystemExit('UI_PASSWORD nicht oder unsicher gesetzt. Nutze ./start.sh.')
    ROOT.mkdir(parents=True, exist_ok=True)
    DOT.mkdir(parents=True, exist_ok=True)
    global PLAN
    PLAN = load_json(PLAN_FILE, {'created_at': now(), 'models': {}})
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    mode = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else 'serve'
    if mode == 'status':
        print(json.dumps(collect_status(), ensure_ascii=False, indent=2))
        return
    if mode == 'check-config':
        for item in get_config():
            print(item['tier'], item['repo'], item.get('allow_patterns', ['*']))
        return
    if mode != 'serve':
        raise SystemExit('Use serve|status|check-config')
    log('MODEL VAULT gestartet; alle Teil-Downloads bleiben auf dem NAS erhalten.')
    threading.Thread(target=monitor_loop, name='monitor', daemon=True).start()
    threading.Thread(target=worker_loop, name='downloader', daemon=True).start()
    server = ThreadingHTTPServer(('0.0.0.0', 8787), Handler)
    server.timeout = 1.0
    log('Web UI bereit auf Port 8787 (HTTP Basic Auth)')
    while not STOP.is_set():
        server.handle_request()
    server.server_close()
    log('Sauber heruntergefahren')


if __name__ == '__main__':
    main()