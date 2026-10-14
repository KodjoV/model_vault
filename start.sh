#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

usage() { echo "Aufruf: ./start.sh /volume1/ModelVault    (oder existierende .env verwenden)" >&2; exit 2; }
command -v docker >/dev/null 2>&1 || { echo "Docker CLI nicht gefunden" >&2; exit 1; }

# UGREEN: ignores the admin home's unreadable ~/.docker/config.json
export DOCKER_CONFIG="$(pwd -P)/.docker-local"
umask 077
mkdir -p "$DOCKER_CONFIG"
chmod 700 "$DOCKER_CONFIG"

if [ ! -f .env ]; then
  [ "$#" -ge 1 ] || usage
  VAULT_PATH="$1"
  case "$VAULT_PATH" in /volume1/*) ;; *) echo "Sicherheit: Modellgewichte nur in /volume1/..., nicht auf der Systempartition." >&2; exit 2 ;; esac
  case "$VAULT_PATH" in *'"'*|*'$'*|*'`'*|*'#'*|*$'\n'*|*' '* ) echo "Pfad bitte ohne Sonder- oder Leerzeichen waehlen." >&2; exit 2;; esac
  mkdir -p "$VAULT_PATH"
  VAULT_PATH="$(cd "$VAULT_PATH" && pwd -P)"
  case "$VAULT_PATH" in /volume1/*) ;; *) echo "Archivpfad zeigt nicht auf /volume1" >&2; exit 2 ;; esac
  # df -T may wrap long mapper device names on UGOS; stat reads the target filesystem directly.
  fs="$(stat -f -c %T "$VAULT_PATH" 2>/dev/null || true)"
  [ "$fs" = "btrfs" ] || { echo "ABBRUCH: Ziel ist '$fs', erwartet btrfs auf /volume1" >&2; exit 2; }
  touch "$VAULT_PATH/.modelvault-write-test-$$" || { echo "Archivfreigabe nicht beschreibbar" >&2; exit 1; }
  rm -f "$VAULT_PATH/.modelvault-write-test-$$"
  if command -v python3 >/dev/null 2>&1; then
    pass="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')"
  else
    pass="$(openssl rand -hex 24)"
  fi
  cat > .env <<ENV
# PRIVAT: niemals committen
VAULT_PATH="$VAULT_PATH"
PUID=$(id -u)
PGID=$(id -g)
BIND_IP=0.0.0.0
WEB_PORT=8790
UI_PASSWORD="$pass"
HF_TOKEN=
SELECT_TIERS=P0
WORKERS=2
PROGRESS_INTERVAL=3
ENV
  chmod 600 .env
  echo 'Zugangsdaten in .env erzeugt. Passwort niemals auf GitHub hochladen.'
fi

set -a
# Dieses Skript erwartet eine lokal erzeugte und kontrollierte .env.
source .env
set +a
case "$VAULT_PATH" in /volume1/*) ;; *) echo "ABBRUCH: VAULT_PATH muss in /volume1 liegen" >&2; exit 2 ;; esac
fs="$(stat -f -c %T "$VAULT_PATH" 2>/dev/null || true)"
[ "$fs" = btrfs ] || { echo "ABBRUCH: Archivziel ist ${fs:-unbekannt}, erwartet btrfs" >&2; exit 2; }
if ! docker info >/dev/null 2>&1; then
  echo 'Docker-Daemon nicht zugreifbar. Teste: DOCKER_CONFIG='"$DOCKER_CONFIG"' docker ps' >&2
  echo 'Bitte zuerst NAS-Benutzerrechte / Docker-Berechtigungen korrigieren; kein automatisches sudo.' >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  echo 'Docker Compose vorhanden: starte compose.yaml'
  docker compose up -d --build
else
  echo 'Docker Compose fehlt: verwende docker build + docker run.'
  if docker container inspect model-vault >/dev/null 2>&1; then
    if [ "$(docker inspect -f '{{.State.Running}}' model-vault)" = true ]; then
      echo 'model-vault läuft bereits. Keine Daten/Container überschrieben.'
      exit 0
    fi
    echo 'Vorhandener Container model-vault ist gestoppt. Starte ihn erneut.'
    docker start model-vault
  else
    docker build -t model-vault:local .
    docker run -d --name model-vault --restart unless-stopped \
      --user "${PUID}:${PGID}" \
      --read-only --cap-drop ALL --security-opt no-new-privileges \
      --tmpfs /tmp:rw,nosuid,nodev,size=128m \
      -p "${BIND_IP}:${WEB_PORT}:8787" \
      -v "${VAULT_PATH}:/vault" -v "$(pwd -P)/models.json:/app/models.json:ro" \
      -e "UI_PASSWORD=${UI_PASSWORD}" -e "HF_TOKEN=${HF_TOKEN:-}" \
      -e "SELECT_TIERS=${SELECT_TIERS:-P0}" \
      -e "WORKERS=${WORKERS:-2}" -e "PROGRESS_INTERVAL=${PROGRESS_INTERVAL:-3}" \
      model-vault:local
  fi
fi

echo "\nSTART erfolgreich. Browser: http://NAS-IP:${WEB_PORT} | User: vault"
echo "Passwort lokal: grep '^UI_PASSWORD=' .env"
echo "Logs: DOCKER_CONFIG=\"$DOCKER_CONFIG\" docker logs -f --tail=50 model-vault"
echo "Status: ./status.sh"
