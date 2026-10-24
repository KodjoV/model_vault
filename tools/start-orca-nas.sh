#!/usr/bin/env bash
# One-command NAS archive for gated OrcaRouter DeepSeek V4.1 Mix-256G.
# Use only after accepting the model gate on Hugging Face.
set -euo pipefail
umask 077
cd /volume1/docker/model_vault

for path in .env models.json compose.yaml start.sh; do
  test -f "$path" || { echo "STOP: $path fehlt."; exit 1; }
done
test -d /volume1/ModelVault/.vault && test -d /volume1/ModelVault/models || {
  echo "STOP: NAS ModelVault fehlt."; exit 1;
}
test "$(stat -f -c %T /volume1/ModelVault)" = btrfs || {
  echo "STOP: Archiv ist nicht auf btrfs."; exit 1;
}

for cmd in python3 curl sudo; do
  command -v "$cmd" >/dev/null || { echo "STOP: $cmd fehlt."; exit 1; }
done
sudo -v
sudo docker compose version >/dev/null || {
  echo "STOP: Docker Compose fehlt; sicherer Neustart nicht moeglich."; exit 1;
}

python3 - <<'PY'
import re
from pathlib import Path
import shutil
import sys
env = Path(".env").read_text(encoding="utf-8")
matches = re.findall(r"(?m)^HF_TOKEN=(.*)$", env)
if len(matches) != 1 or matches[0].strip().strip('"'') in ("", "None"):
    sys.exit("STOP: Dieses Hugging-Face-Repo ist gated. Zuerst Zugang auf "
             "huggingface.co/orcarouter/DeepSeek-V4.1-Flash-1017-abliterated-GGUF "
             "annehmen und HF_TOKEN in lokaler .env setzen. Token nie posten.")
if len(re.findall(r"(?m)^SELECT_TIERS=", env)) != 1:
    sys.exit("STOP: SELECT_TIERS muss genau einmal in .env stehen.")
free = shutil.disk_usage("/volume1/ModelVault").free
if free < 380_000_000_000:
    sys.exit(f"STOP: Nur {free / 1e9:.1f} GB frei; mindestens 380 GB benoetigt.")
print("Freier Platz:", round(free / 1e9, 1), "GB")
PY

# Refuse to interrupt an active Vault transfer. Do not rely only on Docker 'Up'.
if [ "$(sudo docker inspect -f '{{.State.Running}}' model-vault 2>/dev/null || true)" = true ]; then
  python3 - <<'PY'
import json
from pathlib import Path
import sys
p = Path("/volume1/ModelVault/.vault/status.json")
if not p.is_file():
    sys.exit("STOP: Model Vault laeuft, kein Status bekannt. Erst pruefen.")
state = json.loads(p.read_text(encoding="utf-8"))
if state.get("phase") not in ("complete", "idle") or not state.get("verified_complete"):
    sys.exit("STOP: Vorherige Auswahl noch nicht bestaetigt komplett. "
             "Kein laufender Download wird unterbrochen.")
print("Vorheriger Download abgeschlossen.")
PY
fi

SOURCE_COMMIT="e46d508800fe822e51c8a053d4368f7118771fc6"
BASE="https://raw.githubusercontent.com/KodjoV/model_vault/$SOURCE_COMMIT"
next_catalog="$(mktemp ./models.json.orca.XXXXXXXX)"
mkdir -p tools
next_audit="$(mktemp ./tools/verify-abliterated.orca.XXXXXXXX)"
trap 'rm -f "$next_catalog" "$next_audit"' EXIT
curl -fLsS --retry 3 --connect-timeout 15 --max-time 180 "$BASE/models.json" -o "$next_catalog"
curl -fLsS --retry 3 --connect-timeout 15 --max-time 180 "$BASE/tools/verify-abliterated.py" -o "$next_audit"

python3 - "$next_catalog" "$next_audit" <<'PY'
import ast
import json
from pathlib import Path
import sys
new = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["models"]
old = json.loads(Path("models.json").read_text(encoding="utf-8"))["models"]
previous = {m["repo"] for m in old}
new_ids = {m["repo"] for m in new}
if not previous.issubset(new_ids):
    sys.exit("STOP: Neue Auswahl wuerde bestehende Katalogeintraege entfernen.")
orca = [m for m in new if m.get("tier") == "ORCA" and m.get("enabled", True)]
if len(orca) != 1 or orca[0]["repo"] != "orcarouter/DeepSeek-V4.1-Flash-1017-abliterated-GGUF":
    sys.exit("STOP: Unerwartete ORCA-Auswahl.")
files = orca[0]["required_patterns"]
expected = {
    f"Mix-256G/DeepSeek-V4.1-Flash-1017-abliterated-Mix-256G-{i:05d}-of-00007.gguf"
    for i in range(1, 8)
} | {"imatrix.gguf"}
if set(files) != expected or not expected.issubset(set(orca[0]["allow_patterns"])):
    sys.exit("STOP: ORCA-Dateiauswahl stimmt nicht.")
if set(orca[0]["allow_patterns"]) != expected | {"README.md"}:
    sys.exit("STOP: Unerwartete zusaetzliche Download-Dateien.")
ast.parse(Path(sys.argv[2]).read_text(encoding="utf-8"))
print("ORCA: 7 GGUF-Teile + imatrix + README, Auswahl OK.")
PY

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
cp -p .env ".env.before-orca-$stamp"
cp -p models.json "models.json.before-orca-$stamp"
if [ -f tools/verify-abliterated.py ]; then
  cp -p tools/verify-abliterated.py "tools/verify-abliterated.py.before-orca-$stamp"
fi

python3 - <<'PY'
from pathlib import Path
import os
import re
p = Path(".env")
old = p.read_text(encoding="utf-8")
updated = re.sub(r"(?m)^SELECT_TIERS=.*$", "SELECT_TIERS=ORCA", old)
temp = Path(".env.orca.tmp")
temp.write_text(updated, encoding="utf-8")
os.chmod(temp, p.stat().st_mode & 0o777)
temp.replace(p)
PY

mv "$next_catalog" models.json
mv "$next_audit" tools/verify-abliterated.py
chmod 644 models.json tools/verify-abliterated.py
echo "ORCA Tier gespeichert. Starte den bestehenden Vault ..."
sudo ./start.sh /volume1/ModelVault
sudo docker ps --filter name=model-vault --format 'table {{.Names}}\t{{.Status}}'
./status.sh
echo
echo "Dashboard: http://192.168.178.104:8790"
echo "Nach Abschluss: python3 tools/verify-abliterated.py --tier ORCA --root /volume1/ModelVault"
