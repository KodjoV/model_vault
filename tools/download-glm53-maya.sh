#!/bin/sh
# GLM-5.3-Flash Maya-S24 (94.7 GB) + Maya-M (116 GB).
# SHA256 hashes from mw00/project-maya v1.1.16 (maya.py).
# Runs independently of Model Vault's Docker container, with no credentials.
# Usage: sh tools/download-glm53-maya.sh [ABSOLUTE_TARGET_DIRECTORY]
# Default target retains Hugging Face's folder layout for later use with Maya.
set -eu

DEST=${1:-/volume1/ModelVault/models/peasantsmith/GLM-5.3-Flash-Maya-GGUF}
case "$DEST" in
  /volume1/*) ;;
  *) echo "ERROR: target must be under /volume1 (NAS data volume): $DEST" >&2; exit 2 ;;
esac
# Allow Model Vault's normal ORG/REPO tree to be created on first download.
# Still refuse an unknown missing share folder.
if [ ! -d "$(dirname "$DEST")" ]; then
  case "$DEST" in
    /volume1/ModelVault/*)
      if [ ! -d /volume1/ModelVault ]; then
        echo "ERROR: ModelVault data share not found: /volume1/ModelVault" >&2
        exit 2
      fi
      ;;
    *)
      echo "ERROR: parent folder does not exist: $(dirname "$DEST")" >&2
      exit 2
      ;;
  esac
fi
for cmd in curl sha256sum df du awk mkdir mv; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: missing tool: $cmd" >&2; exit 2; }
done
umask 022
mkdir -p "$DEST"

# Approx. 211 GB weights + 9 GB reserve. Count existing bytes in both target
# directories when resuming. No other Model Vault data is touched.
free_kb=$(df -Pk "$DEST" | awk 'NR == 2 {print $4}')
existing_kb=$(du -sk "$DEST/Maya-S24" "$DEST/Maya-M" 2>/dev/null | awk '{n += $1} END {print n+0}')
if [ -z "$free_kb" ] || [ "$((free_kb + existing_kb))" -lt 220000000 ]; then
  echo "ERROR: about 220 GB total capacity needed (download + reserve)." >&2
  echo "This check counts already present files in Maya-S24/Maya-M." >&2
  exit 3
fi

BASE=https://huggingface.co/peasantsmith/GLM-5.3-Flash-Maya-GGUF/resolve/main

fetch_file() {
  folder=$1
  filename=$2
  sha1=$3
  sha2=${4:-}
  mkdir -p "$DEST/$folder"
  target="$DEST/$folder/$filename"
  part="$target.part"

  if [ -f "$target" ]; then
    actual=$(sha256sum "$target" | awk '{print $1}')
    if [ "$actual" = "$sha1" ] || { [ -n "$sha2" ] && [ "$actual" = "$sha2" ]; }; then
      echo "ALREADY VERIFIED: $folder/$filename"
      return 0
    fi
    echo "ERROR: final file has wrong SHA256, not overwriting: $target" >&2
    return 1
  fi

  echo "DOWNLOADING: $folder/$filename"
  curl --fail --location --continue-at - --retry 30 --retry-delay 30 \
    --connect-timeout 40 --speed-time 120 --speed-limit 1024 \
    --output "$part" "$BASE/$folder/$filename"

  actual=$(sha256sum "$part" | awk '{print $1}')
  if [ "$actual" != "$sha1" ] && { [ -z "$sha2" ] || [ "$actual" != "$sha2" ]; }; then
    echo "ERROR: SHA256 mismatch: $part; preserved for diagnosis." >&2
    return 1
  fi
  mv "$part" "$target"
  echo "VERIFIED: $folder/$filename"
}

# First shards have two valid hashes (header-only revision, same tensor data).
# Maya-S24 (24 GB GPUs), then Maya-M.
fetch_file Maya-S24 GLM-5.3-Flash-Maya-S24-IQ2_XXS_S-00001-of-00003.gguf 8ebd5c74bcf65ece2a8699b7b6fd2b8d177f350ed252cee252fdd99b86a0138c 3dc347757686c1435eae36c4872f5c151191cc5063bc188ce699b97700aae076
fetch_file Maya-S24 GLM-5.3-Flash-Maya-S24-IQ2_XXS_S-00002-of-00003.gguf 4bd445da3a0128a9c5b32228c924e0a622aa4a132c7a8dc9a2c207a4beea8e34
fetch_file Maya-S24 GLM-5.3-Flash-Maya-S24-IQ2_XXS_S-00003-of-00003.gguf a6fd4e88007ac49b431c7d02be34e43ab7a09224d53a0c52782327613cb41917

fetch_file Maya-M GLM-5.3-Flash-Maya-M-IQ2_S-00001-of-00003.gguf 3f740d1b1022b4a0ddad50cd861bb071dd415bde94afa1292d0476641186c638 3ac0f066ec45af3432d59b33de49bdfb29156432b627240b35769c7d02cc6c02
fetch_file Maya-M GLM-5.3-Flash-Maya-M-IQ2_S-00002-of-00003.gguf 285951d2afa0cd98285b03d0dc4aa68d83daf1a6f4a2594fe40b0cdd27ade485
fetch_file Maya-M GLM-5.3-Flash-Maya-M-IQ2_S-00003-of-00003.gguf ebf1ce713f71207747e10eeebed87597969d8b5e1d9dd817420d2c2f7ca51e0e

echo "DONE: all 6 files downloaded and SHA256 verified; no model server started."
