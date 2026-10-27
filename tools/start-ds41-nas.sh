#!/usr/bin/env bash
# Safely activate isolated DS41 tier in existing NAS Model Vault.
# Downloads only config and verifier from a pinned GitHub commit.
# Existing archives, .vault, llama-swap and Strata remain untouched.
set -euo pipefail
umask 077

cd /volume1/docker/model_vault
test -f .env && test -f models.json && test -f start.sh && test -f compose.yaml || {
  echo "STOP: Bestehende Model-Vault-Installation unvollstaendig." >&2; exit 1;
}
test -d /volume1/ModelVault/models && test -d /volume1/ModelVault/.vault || {
  echo "STOP: NAS-Archivpfade fehlen." >&2; exit 1;
}
test "$(stat -f -c %T /volume1/ModelVault)" = btrfs || {
  echo "STOP: ModelVault liegt nicht auf btrfs." >&2; exit 1;
}

command -v python3 >/dev/null
command -v curl >/dev/null
command -v sudo >/dev/null
sudo -v
sudo docker compose version >/dev/null || {
  echo "STOP: Docker Compose fehlt; kein sicheres Neubauen moeglich." >&2; exit 1;
}

# Estimate: selected archive ~274 GB (plus space for manifests and transfers).
free_kb="$(df -Pk /volume1/ModelVault | awk 'END {print $4}')"
if ! [[ "$free_kb" =~ ^[0-9]+$ ]] || (( free_kb < 300000000 )); then
  echo "STOP: Weniger als 300 GB frei oder Speicherplatz unbekannt." >&2
  exit 1
fi

SOURCE_COMMIT="996a2448095b9c9246db82a46d264688c7b56c23"
BASE="https://raw.githubusercontent.com/KodjoV/model_vault/$SOURCE_COMMIT"
new_catalog="$(mktemp ./models.json.ds41.XXXXXXXX)"
mkdir -p tools
new_verifier="$(mktemp ./tools/verify-abliterated.py.ds41.XXXXXXXX)"
trap 'rm -f "$new_catalog" "$new_verifier"' EXIT

curl -fLsS --retry 3 --connect-timeout 15 --max-time 180 \
  "$BASE/models.json" -o "$new_catalog"
curl -fLsS --retry 3 --connect-timeout 15 --max-time 180 \
  "$BASE/tools/verify-abliterated.py" -o "$new_verifier"

python3 - "$new_catalog" "$new_verifier" <<'PY'
import ast
import json
import sys
from pathlib import Path
catalog = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
selected = [m for m in catalog["models"] if m.get("tier") == "DS41" and m.get("enabled", True)]
assert {m["repo"] for m in selected} == {
    "ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF",
    "unsloth/DeepSeek-V4.1-Flash-1017-GGUF",
}, "Unexpected DS41 models"
for model in selected:
    assert set(model["required_patterns"]).issubset(set(model["allow_patterns"]))
    assert model["required_patterns"] and "*" not in model["allow_patterns"]
assert sum(len(m["required_patterns"]) for m in selected) == 7, "Expected 4 shards + Engram + allocation + DSpark"
ast.parse(Path(sys.argv[2]).read_text(encoding="utf-8"))
print("DS41 Auswahl: 2 Repos, 7 Pflichtdateien. Konfiguration OK.")
PY

# Keep local secrets private, no content printed. Never overwrite prior backups.
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
cp -p models.json "models.json.before-ds41-$stamp"
cp -p .env ".env.before-ds41-$stamp"
if test -f tools/verify-abliterated.py; then
  cp -p tools/verify-abliterated.py "tools/verify-abliterated.py.before-ds41-$stamp"
fi

# Preserve existing .env lines, UID permissions and credentials.
python3 - <<'PY'
from pathlib import Path
import os
import re
p = Path(".env")
text = p.read_text(encoding="utf-8")
assert len(re.findall(r"(?m)^SELECT_TIERS=", text)) == 1, "SELECT_TIERS muss genau einmal existieren"
new = re.sub(r"(?m)^SELECT_TIERS=.*$", "SELECT_TIERS=DS41", text)
temp = Path(".env.ds41.tmp")
temp.write_text(new, encoding="utf-8")
os.chmod(temp, p.stat().st_mode & 0o777)
temp.replace(p)
PY

mv -f "$new_catalog" models.json
mv -f "$new_verifier" tools/verify-abliterated.py
chmod 644 models.json tools/verify-abliterated.py
echo "Starte bestehenden Model Vault mit SELECT_TIERS=DS41 ..."
sudo ./start.sh /volume1/ModelVault
echo
echo "GESTARTET (Container bitte im Status pruefen):"
sudo docker ps --filter name=model-vault --format 'table {{.Names}}\t{{.Status}}'
./status.sh
echo
echo "Dashboard: http://192.168.178.104:8790"
echo "Nach Abschluss: python3 tools/verify-abliterated.py --tier DS41 --root /volume1/ModelVault"
