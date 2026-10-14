#!/bin/sh
set -eu
# UGREEN DXP4800 Pro: data volume /volume1; never use the OS overlay.
fs="$(stat -f -c %T /volume1 2>/dev/null || true)"
[ "$fs" = "btrfs" ] || { echo "ABBRUCH: /volume1 ist ${fs:-unbekannt}, erwartet btrfs" >&2; exit 1; }
# Shared folders must be created in UGOS. Never create shares here.
[ -d /volume1/docker ] || { echo "UGOS-Freigabe /volume1/docker fehlt" >&2; exit 1; }
[ -d /volume1/ModelVault ] || { echo "UGOS-Freigabe /volume1/ModelVault fehlt" >&2; exit 1; }
[ -w /volume1/docker ] || { echo "/volume1/docker ist nicht beschreibbar" >&2; exit 1; }
[ -w /volume1/ModelVault ] || { echo "/volume1/ModelVault ist nicht beschreibbar" >&2; exit 1; }
mkdir -p /volume1/ModelVault/models /volume1/ModelVault/.vault
printf 'Code: /volume1/docker/model_vault\nModelle: /volume1/ModelVault\n'
