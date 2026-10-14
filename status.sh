#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .env ]; then echo '.env fehlt. Erst ./start.sh /pfad ausfuehren.' >&2; exit 1; fi
set -a; source .env; set +a
if [ ! -f "$VAULT_PATH/.vault/status.json" ]; then echo 'Noch kein Status; siehe docker compose logs'; exit 1; fi
python3 - "$VAULT_PATH/.vault/status.json" <<'PY'
import json,sys
s=json.load(open(sys.argv[1]))
gib=lambda b:'? ' if b is None else f'{b/(1024**3):.2f} GiB'
print(f"{s['updated_at']}  |  {s['phase']}  |  {s['percent'] if s['percent'] is not None else '?'} %")
print(f"Gesamt: {gib(s['downloaded_bytes'])} / {gib(s['expected_bytes'])}")
print(f"Modelle: {s['complete_models']}/{s['all_models']} | Verifiziert: {s['verified_files']}/{s['all_files'] if s['all_files'] is not None else '?'} Dateien")
print(f"Speed: {s['speed_bytes_second'] / 1048576:.2f} MiB/s | frei: {gib(s['free_disk_bytes'])}")
print(f"ETA: {round(s['eta_seconds']/60)} min" if s['eta_seconds'] is not None else 'ETA: noch nicht moeglich')
for m in s['models']:
 print(f" - {m['status']:12} {m['repo']}: {gib(m['bytes'])}/{gib(m['total'])}" + ('  FEHLER: '+m['error'] if m['error'] else ''))
PY
