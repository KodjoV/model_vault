#!/usr/bin/env bash
# Initialisierung auf dem NAS: kein sudo, keine Aenderungen an bestehenden Diensten.
set -euo pipefail
if [ "$#" -ne 1 ]; then echo "Aufruf: ./nas-layout.sh /ABSOLUTER/PFAD/ZUM/DATENVOLUME"; exit 2; fi
BASE="${1%/}"
case "$BASE" in /*) ;; *) echo "Nur absolute Datenvolume-Pfade zulaessig" >&2; exit 2;; esac
if [ ! -d "$BASE" ] || [ ! -w "$BASE" ]; then
 echo "Verzeichnis existiert nicht oder ist nicht beschreibbar: $BASE" >&2; exit 1
fi
if [ "$BASE" = / ] || [ "$BASE" = /root ] || [ "$BASE" = /etc ] || [ "$BASE" = /usr ] || [ "$BASE" = /var ]; then
 echo "Pfad nicht sicher: $BASE" >&2; exit 1
fi
mkdir -p "$BASE/docker" "$BASE/ModelVault/models" "$BASE/ModelVault/.vault"
if [ ! -w "$BASE/docker" ] || [ ! -w "$BASE/ModelVault" ]; then echo "Zugriffsrechte pruefen" >&2; exit 1; fi
printf "Ordner erstellt:\n  %s/docker\n  %s/ModelVault/models\n  %s/ModelVault/.vault\n" "$BASE" "$BASE" "$BASE"
