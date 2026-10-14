# Model Vault – UGREEN DXP4800 Pro

Private/offline-capable model archive: pinned Hugging Face commits, resumable HTTP downloads, SHA-256 manifests, live dashboard and CLI status. **Only scripts belong in GitHub; model weights, credentials and status live on the NAS.**

## UGREEN first setup

1. Find the **data** volume, not the system overlay. On this UGREEN: `/volume1` is a 19 TB btrfs volume.
2. The example data root is `/volume1/ModelVault`; you must have NAS-user write permission. Prefer creating dedicated **ModelVault** and **Docker** shared folders in UGOS UI so permissions are correct.
3. In terminal, from a writable shared folder:

```sh
cd /volume1/Docker
 git clone https://github.com/KodjoV/model_vault.git
 cd model_vault
chmod +x start.sh status.sh
./start.sh /volume1/ModelVault
```

`start.sh` auto-creates a local `.env` password, refuses a data path off `/volume1`, and checks btrfs and write access. It uses Compose if available; otherwise Docker build/run directly, so Compose is **not required**. Docker itself must be accessible to the current user. An isolated `DOCKER_CONFIG` avoids using the NAS account's broken `~/.docker/config.json`.

## Progress

Go to `http://NAS-IP:8787` on LAN/Tailscale, log in as **vault**, and get the password from `.env` (`grep '^UI_PASSWORD=' .env`). Browser updates every 3 seconds and shows overall GiB, percent, model/file completions, MiB/s, ETA, errors, disk capacity. You can pause/resume/retry from dashboard.

In SSH session:

```sh
./status.sh
export DOCKER_CONFIG="$(pwd)/.docker-local"
docker logs -f --tail=50 model-vault
```

Status and `.part` downloads persist under `/volume1/ModelVault/.vault` and `/volume1/ModelVault/models`. NAS restart resumes the downloader; no ChatGPT session needs to remain open.

## Paths

- `Docker/model_vault`: cloned GitHub source and local `.env` only.
- `ModelVault/models/ORG/REPO/`: saved model files, same namespace as HF.
- `ModelVault/.vault/`: plan, status, logs and pause flags.

P0 starts with eight repositories: YuE2, ACE-Step 1.5, MiniMax Music 3, original and selected Qwen Image 2.1 components (see `models.json`). P1 is prepared but disabled by default: Whisper, ASR, TTS, vision. Licenses (including non-commercial/research restrictions) still apply. Krea gated models are *not* auto-bypassed. For legitimate access, set `HF_TOKEN` locally in `.env`; never commit it.

## Security and limitations

The web server uses Basic authentication **over HTTP**. Never port-forward port 8787. Use only trusted LAN/Tailscale or an HTTPS reverse proxy. NAS RAID1 is not a true independent backup; copy irreplaceable snapshots separately. Hugging Face repos can change, vanish, or rate-limit; plan stores an immutable revision and hash evidence. A recorded local SHA-256 is not the same as verification against the publisher unless upstream LFS SHA is known.

This is version 1: local resume and dashboard unit tests pass, but a multi-100GiB run against all live upstream endpoints has not been validated yet.
