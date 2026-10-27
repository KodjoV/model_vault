#!/usr/bin/env bash
# Model Vault: one-command activation of OPEN3 (public GLM5.3 + DeepSeek).
# No changes to B52, llama-swap or Strata. Only the existing Vault container.
set -euo pipefail
umask 077
cd /volume1/docker/model_vault

for file in .env models.json compose.yaml start.sh; do
  test -f "$file" || { echo "STOP: $file fehlt"; exit 1; }
done
test -d /volume1/ModelVault/.vault && test -d /volume1/ModelVault/models || {
  echo "STOP: ModelVault-Datenordner fehlen"; exit 1;
}
test "$(stat -f -c %T /volume1/ModelVault)" = btrfs || {
  echo "STOP: NAS-Ziel ist nicht btrfs"; exit 1;
}
for command in curl python3 sudo; do
  command -v "$command" >/dev/null || { echo "STOP: $command fehlt"; exit 1; }
done
sudo -v
sudo docker compose version >/dev/null || {
  echo "STOP: Docker Compose fehlt; kein sicherer Rebuild"; exit 1;
}
# Enough space for ~585 GB files + 10% reserve.
python3 - <<'PY'
from pathlib import Path
import re
import shutil
env = Path(".env").read_text(encoding="utf-8")
if len(re.findall(r"(?m)^SELECT_TIERS=", env)) != 1:
    raise SystemExit("STOP: SELECT_TIERS muss genau einmal gesetzt sein.")
available = shutil.disk_usage("/volume1/ModelVault").free
if available < 650_000_000_000:
    raise SystemExit(f"STOP: Nur {available / 1e9:.1f} GB frei; mindestens 650 GB benoetigt.")
print(f"NAS: {available / 1e9:.1f} GB frei.")
PY

# Do not interrupt another active Model Vault download.
if [ "$(sudo docker inspect -f '{{.State.Running}}' model-vault 2>/dev/null || true)" = true ]; then
  python3 - <<'PY'
import json
from pathlib import Path
p = Path("/volume1/ModelVault/.vault/status.json")
if not p.is_file():
    raise SystemExit("STOP: Container laeuft ohne pruefbaren Status.")
data = json.loads(p.read_text(encoding="utf-8"))
if data.get("phase") not in ("idle", "complete") or not data.get("verified_complete"):
    raise SystemExit("STOP: Vorheriger Download ist noch aktiv oder nicht fertig.")
PY
fi

# This is a fixed reviewed GitHub commit, not a moving branch.
PIN="f454ed979b26347f0b69fbf71e63236a28b3b1c8"
BASE="https://raw.githubusercontent.com/KodjoV/model_vault/$PIN"
new_config="$(mktemp ./models.json.open3.XXXXXXXX)"
mkdir -p tools
new_audit="$(mktemp ./tools/verify-abliterated.open3.XXXXXXXX)"
trap 'rm -f "$new_config" "$new_audit"' EXIT
curl -fLsS --retry 3 --connect-timeout 15 --max-time 120 "$BASE/models.json" -o "$new_config"
curl -fLsS --retry 3 --connect-timeout 15 --max-time 120 "$BASE/tools/verify-abliterated.py" -o "$new_audit"

python3 - "$new_config" "$new_audit" <<'PY'
import ast
import json
import sys
from pathlib import Path
old = json.loads(Path("models.json").read_text(encoding="utf-8"))["models"]
new = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["models"]
old_ids = {m["repo"] for m in old}
new_ids = {m["repo"] for m in new}
if not old_ids.issubset(new_ids):
    raise SystemExit("STOP: Neues models.json wuerde alte Modelleintraege entfernen.")
selected = {m["repo"]: m for m in new if m.get("tier") == "OPEN3" and m.get("enabled", True)}
expected = {
    "huihui-ai/Huihui-GLM-5.3-Flash-abliterated-GGUF": 5,
    "ggml-org/GLM-5.3-Flash-GGUF": 4,
    "audreyt/DeepSeek-V4.1-Flash-Abliterated-GGUF": 1,
}
if {k: len(v["required_patterns"]) for k, v in selected.items()} != expected:
    raise SystemExit("STOP: OPEN3-Pflichtdateien unerwartet.")
for model in selected.values():
    if not set(model["required_patterns"]).issubset(set(model["allow_patterns"])):
        raise SystemExit("STOP: Pflichtdatei nicht ausgewahlt.")
    if "*" in model["allow_patterns"]:
        raise SystemExit("STOP: Unerwartete Vollauswahl.")
ast.parse(Path(sys.argv[2]).read_text(encoding="utf-8"))
print("OPEN3: drei Repos und alle Pflichtdateien OK.")
PY

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
cp -p .env ".env.before-open3-$stamp"
cp -p models.json "models.json.before-open3-$stamp"
if [ -f tools/verify-abliterated.py ]; then
  cp -p tools/verify-abliterated.py "tools/verify-abliterated.py.before-open3-$stamp"
fi

python3 - <<'PY'
from pathlib import Path
import os
import re
p = Path(".env")
text = p.read_text(encoding="utf-8")
updated = re.sub(r"(?m)^SELECT_TIERS=.*$", "SELECT_TIERS=OPEN3", text)
temp = Path(".env.open3.tmp")
temp.write_text(updated, encoding="utf-8")
os.chmod(temp, p.stat().st_mode & 0o777)
temp.replace(p)
PY
mv "$new_config" models.json
mv "$new_audit" tools/verify-abliterated.py
chmod 644 models.json tools/verify-abliterated.py

sudo ./start.sh /volume1/ModelVault
sudo docker ps --filter name=model-vault --format 'table {{.Names}}\t{{.Status}}'
./status.sh
echo "Dashboard: http://192.168.178.104:8790"
echo "Nach Abschluss: python3 tools/verify-abliterated.py --tier OPEN3 --root /volume1/ModelVault"
