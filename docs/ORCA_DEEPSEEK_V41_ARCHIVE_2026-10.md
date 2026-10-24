# OrcaRouter DeepSeek V4.1 Flash 1017 Abliterated – NAS archive

Status: **GitHub catalog entry only** until the user runs the NAS starter.
The source repository is gated: https://huggingface.co/orcarouter/DeepSeek-V4.1-Flash-1017-abliterated-GGUF
Sign into Hugging Face, accept its access conditions and provide your own valid
read-access `HF_TOKEN` in the **existing local** `/volume1/docker/model_vault/.env`.
Do not paste tokens in chat or commit them.

## Exact selection

An independent tier `ORCA` in `models.json` selects only:

- `Mix-256G/DeepSeek-V4.1-Flash-1017-abliterated-Mix-256G-00001-of-00007.gguf`
- `Mix-256G/DeepSeek-V4.1-Flash-1017-abliterated-Mix-256G-00002-of-00007.gguf` (Engram)
- `Mix-256G/DeepSeek-V4.1-Flash-1017-abliterated-Mix-256G-00003-of-00007.gguf`
- `Mix-256G/DeepSeek-V4.1-Flash-1017-abliterated-Mix-256G-00004-of-00007.gguf`
- `Mix-256G/DeepSeek-V4.1-Flash-1017-abliterated-Mix-256G-00005-of-00007.gguf`
- `Mix-256G/DeepSeek-V4.1-Flash-1017-abliterated-Mix-256G-00006-of-00007.gguf`
- `Mix-256G/DeepSeek-V4.1-Flash-1017-abliterated-Mix-256G-00007-of-00007.gguf`
- `imatrix.gguf` (calibration/reproducibility, not needed at inference)
- `README.md` (if published)

The seven model files total ~346.5 GB, and imatrix ~1.58 GB;
allow **at least 380 GB free** before starting.

The smaller Mix-128G is **not** selected. According to the author the larger
build consumes 235.8 GB in memory excluding the Engram and needs ~256 GB host
memory or unified VRAM. B52 with 128 GB RAM and 24 GB GPU VRAM **cannot**
assume it runs. Mix-128G is nearer B52 memory but loses a lot of quality,
per the developer's held-out-token results. This task is archival first.

**Not interchangeable with prior ISTA DeepSeek GSQ-RCO Strata weights.**
This OrcaRouter mixed-precision GGUF targets llama.cpp with custom
DeepSeek-V4.1 support (the source card references PR #30817);
compatibility with our Strata release is unverified.
No vision module or DSpark drafter is supplied.

## Existing vault behavior

No second downloader. `vault.py` resolves and pins the full HF commit SHA
at planning, writes the plan into `/volume1/ModelVault/.vault/plan.json`,
performs resumable HTTP downloads, computes local SHA256 for every file,
and compares upstream LFS SHA256 where supplied.

Weight files go to
`/volume1/ModelVault/models/orcarouter/DeepSeek-V4.1-Flash-1017-abliterated-GGUF/`.

Use `tools/verify-abliterated.py --tier ORCA` **after** the downloads to
rehash files from the manifest. Local digests without a recorded upstream
LFS SHA256 do not count as independent publisher verification.

## One-command NAS start

On the existing UGREEN NAS over SSH, after accepting gated access and
setting `HF_TOKEN` in private `.env`, execute the pinned launcher from
the linked PR; do not use an unreviewed moving `main` branch:

```sh
cd /volume1/docker/model_vault && \
curl -fLsS --retry 3 https://raw.githubusercontent.com/KodjoV/model_vault/cd26da4cf37f2f57fd36bb78dc9cc40eddbabda4/tools/start-orca-nas.sh -o start-orca-nas.sh && \
bash start-orca-nas.sh
```

Replace `cd26da4cf37f2f57fd36bb78dc9cc40eddbabda4` with the reviewed GitHub commit from the final
PR response. This starter validates the catalog, checks free space and HF
token presence, preserves local backups of `.env` and `models.json`,
and runs the existing Compose service with `SELECT_TIERS=ORCA`.

When the downloads finish:

```sh
cd /volume1/docker/model_vault
python3 tools/verify-abliterated.py --tier ORCA --root /volume1/ModelVault
sudo docker compose down
```

Never share the local token, expose port 8790 to the internet,
or merge this GGUF into llama-swap/Strata configurations before
isolated compatibility tests. NAS RAID1 is not an independent backup.
