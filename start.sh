#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v docker >/dev/null 2>&1; then echo 'Docker fehlt. Bitte Docker auf der UGREEN bereitstellen.' >&2; exit 1; fi
if ! docker compose version >/dev/null 2>&1; then echo 'docker compose fehlt (Compose Plugin erforderlich).' >&2; exit 1; fi
if [ ! -e .env ]; then
  if [ "$#" -lt 1 ]; then echo 'Aufruf: ./start.sh /ABSOLUTER/NAS/PFAD/ModelVault'; exit 2; fi
  VAULT_PATH="$1"
  case "$VAULT_PATH" in /*) ;; *) echo 'Bitte absoluten Pfad angeben.' >&2; exit 2;; esac
  mkdir -p "$VAULT_PATH"
  VAULT_PATH="$(cd "$VAULT_PATH" && pwd -P)"
  case "$VAULT_PATH" in *'"'*|*'$'*|*'`'*|*'#'*|*$'\n'*)
    echo 'Bitte Archivpfad ohne Anfuehrungszeichen, Dollarzeichen, Backticks oder # waehlen.' >&2; exit 2;;
  esac
  if ! touch "$VAULT_PATH/.modelvault-write-test-$$"; then echo 'Kein Schreibrecht im Archivpfad.' >&2; exit 1; fi
  rm -f "$VAULT_PATH/.modelvault-write-test-$$"
  if command -v python3 >/dev/null 2>&1; then
    PASS="$(python3 -c 'import secrets;print(secrets.token_urlsafe(22))')"
  elif command -v openssl >/dev/null 2>&1; then
    PASS="$(openssl rand -hex 24)"
  else
    echo 'Fuer ein sicheres Passwort wird python3 oder openssl auf der NAS benoetigt.' >&2; exit 1
  fi
  PUID="$(id -u)"; PGID="$(id -g)"
  cat > .env <<ENV
# Von start.sh einmalig erstellt. NICHT nach GitHub committen!
VAULT_PATH="$VAULT_PATH"
PUID=$PUID
PGID=$PGID
# Im vertrauenswuerdigen Heimnetz via http://NAS-IP:8787; sonst SSH-Tunnel nutzen.
BIND_IP=0.0.0.0
WEB_PORT=8787
UI_PASSWORD=$PASS
HF_TOKEN=
SELECT_TIERS=P0
WORKERS=2
PROGRESS_INTERVAL=3
ENV
  chmod 600 .env
  echo 'Neue .env erzeugt. Zugangspasswort lokal in .env gespeichert.'
else
  echo 'Bestehende .env wird unveraendert verwendet.'
fi

docker compose up -d --build
printf '\nMODEL VAULT gestartet. Auf der UGREEN: http://NAS-IP:8787\n'
printf 'Benutzer: vault  |  Passwort: UI_PASSWORD aus .env\n'
printf 'STATUS: docker compose logs -f --tail=25\n'
printf 'PAUSE: Browser-Oberflaeche, Resume: Browser-Oberflaeche.\n'
