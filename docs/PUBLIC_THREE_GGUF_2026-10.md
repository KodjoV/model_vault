# OPEN3 – three public GGUF archives for B52 comparison

**GitHub preparation only. No NAS download, B52 installation, llama-swap or Strata change occurred.**

## What you already have

Your earlier Project Maya GLM-5.3-Flash builds:
- `peasantsmith/GLM-5.3-Flash-Maya-GGUF/Maya-S24`, 94.7 GB, specially tuned for a 24 GB GPU;
- `peasantsmith/GLM-5.3-Flash-Maya-GGUF/Maya-M`, 116 GB, higher precision for code and tools.

User reported these downloads complete on NAS on Oct 21, 2026. They are **not**
in the new OPEN3 tier and will not be downloaded again.

## New tier (all publicly listed; no HF account required as far as verified)

| Repo | Exact data, selected by `models.json` | Approx. GB | Runtime notes |
| --- | --- | ---: | --- |
| `huihui-ai/Huihui-GLM-5.3-Flash-abliterated-GGUF` | `UD-IQ2_XXS/GLM-5.3-Flash-UD-IQ2_XXS-00001..00004-of-00004.gguf`, `mmproj-model-bf16.gguf` | 103.2 | Abliterated; test in isolated llama.cpp |
| `ggml-org/GLM-5.3-Flash-GGUF` | `GLM-5.3-Flash-Q2_K_S-00001..00002-of-00002.gguf`, `mtp-GLM-5.3-Flash-Q4_0.gguf`, `mmproj-GLM-5.3-Flash-Q8_0.gguf` | 115.6 | Non-abliterated quality baseline; Q4_0 MTP sidecar for draft test |
| `audreyt/DeepSeek-V4.1-Flash-Abliterated-GGUF` | `DeepSeek-V4.1-Flash-1017-Maya-XS-Abliterated.gguf` | 365.7 | DwarfStar/ds4-specific GGUF with disk Engram; not generic llama.cpp or Strata |

Additionally archive `README.md` when available. Total ~585 GB; allow **650 GB free**.
The DeepSeek file has a publisher-listed SHA256:
`f414995b3797f77009634fac995f50834e70393771f9423fca984c892503b42a`.
The main Vault downloader verifies upstream LFS SHA256 when available. For
Xet-stored objects upstream LFS SHA may be absent: verify the published
DeepSeek SHA256 separately using `sha256sum` after the download.

## NAS operation

Use the existing Model Vault infrastructure only. All three source repositories
were publicly viewable without account; actual anonymous weight transfers still
require a live download check. No Hugging Face CLI needed: the Vault already
uses the Hugging Face API and range-based HTTP downloads.

The one-command helper `tools/start-open3-nas.sh` checks 650 GB space, preserves
old local `.env` / `models.json`, avoids interrupting active transfers, reads
a pinned GitHub revision, validates expected selections, switches to
`SELECT_TIERS=OPEN3` and starts the **existing** NAS downloader via Compose.

It does **not** edit the other tiers P0, P1, ABL, DS41, ORCA. `vault.py` pins
each HF repository's exact 40-character commit at the first planning step in
`/volume1/ModelVault/.vault/plan.json` and saves a manifest and SHA256SUMS file
in each archived repository.

Once downloads finish, audit every byte:

```sh
cd /volume1/docker/model_vault || exit 1
python3 tools/verify-abliterated.py --tier OPEN3 --root /volume1/ModelVault
# Independent published DeepSeek hash:
sha256sum /volume1/ModelVault/models/audreyt/DeepSeek-V4.1-Flash-Abliterated-GGUF/DeepSeek-V4.1-Flash-1017-Maya-XS-Abliterated.gguf
# Expected value:
# f414995b3797f77009634fac995f50834e70393771f9423fca984c892503b42a
sudo docker compose down
```

Read-only audit verifies all saved local SHA256 values and any recorded upstream
LFS SHA256. The explicit published DeepSeek hash is a further source comparison.

## Test order on B52

1. Start with your existing Maya-S24 and Maya-M to benchmark 24 GB VRAM and 128 GB RAM.
2. Then test Huihui UD-IQ2_XXS in an isolated llama.cpp server; compare
   actual code tasks, refusal rate, tool-use format, speed, and memory.
3. Test ggml Q2_K_S as non-abliterated reference. Try Q4_0 MTP only after
   the simple run works; speculative decoding correctness needs validation.
4. DeepSeek Maya-XS is **archive-first**. Its GGUF uses ds4-specific tensor
   layout, ~107.35 GiB resident weights plus disk-only Engram tables and
   ~365.7 GB on SSD. Nvidia/Linux performance on B52 is unverified.

Sources:
- https://huggingface.co/peasantsmith/GLM-5.3-Flash-Maya-GGUF
- https://huggingface.co/huihui-ai/Huihui-GLM-5.3-Flash-abliterated-GGUF/tree/main/UD-IQ2_XXS
- https://huggingface.co/ggml-org/GLM-5.3-Flash-GGUF/tree/main
- https://huggingface.co/audreyt/DeepSeek-V4.1-Flash-Abliterated-GGUF
