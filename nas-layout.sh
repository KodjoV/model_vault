#!/bin/sh
set -eu
# UGREEN DXP4800: Datenvolume /volume1, niemals das Systemvolume.
[ "$(df -T /volume1 | awk 'NR==2{print $2}')" = "btrfs" ] || exit 1
mkdir -p /volume1/Docker /volume1/ModelVault
mkdir -p /volume1/ModelVault/models /volume1/ModelVault/.vault
printf 'Code: /volume1/Docker\nModelle: /volume1/ModelVault\n'
