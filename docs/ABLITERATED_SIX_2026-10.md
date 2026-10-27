# Abliterated six-model archive – NAS Model Vault

Status: catalog and verifier prepared on GitHub; **no NAS download or inference was run**.
The existing Model Vault keeps model weights out of GitHub. No new downloader,
no llama-swap configuration change, no Strata configuration change.

## Selection

Enable tier `ABL` **alone** with `SELECT_TIERS=ABL`. This leaves the already
archived `P0`/`P1` catalogs unchanged and prevents unexpected re-downloads.

| Repository | Required files | Notes |
| --- | --- | --- |
| `abliterant/Qwen3.8-27B-RANA-abliterated-GGUF` | Q4_K_M, mtp-Q8_0, mmproj-BF16 | A matching MTP draft head exists; no server is started |
| `Guile/Qwen3.8-27B-Humanlike-Chat-GGUF` | Q4_K_M | Text only; no guessed MTP |
| `wangzhang/gemma-4-26B-A4B-it-abliterix-GGUF` | Q4_K_M, mmproj-f16 | External EAGLE-3 for base Gemma is not proven compatible |
| `huihui-ai/Huihui-Qwythos-9B-Claude-Mythos-5-1M-abliterated-GGUF` | Q6_K, mmproj-BF16 | Context length claim not tested on B52 |
| `huihui-ai/Huihui-Qwen3.8-27B-Coder390-EfficientThink-abliterated-GGUF` | IQ3_S1, mmproj-BF16, allocation note | Not an inference configuration |
| `huihui-ai/Huihui-Qwen3.8-Flash-Next-abliterated-v2-GGUF` | Swift IQ3_S both GGUF shards, Swift mmproj | Needs its own tested Strata pack before inference |

Full exact paths live in `models.json` `required_patterns`. Other
formats and quants are excluded. Small metadata files are selected if present.

## Revisions and integrity

The existing `vault.py` resolves a **full immutable 40-digit Hugging Face SHA
at planning time**. It writes that SHA into
`/volume1/ModelVault/.vault/plan.json`, retains it for retries and writes
`MODEL_VAULT_MANIFEST.json` into each model directory.
This archive does **not** preclaim unverified revision IDs in the catalog.
Once planned, the SHA must not be silently replaced by `main`.

The downloader uses the existing Hugging Face API for inventory and HTTP Range
for transfers. **It does not require the `hf` CLI.** The downloader computes
SHA256 for files and checks against the Hugging Face LFS SHA256 when exposed.
For Xet or small files without a publisher SHA, the local digest is recorded
but cannot be called independent publisher verification.

`tools/verify-abliterated.py` reads and hashes all model files again. It does
not download, fix or delete files. `upstream LFS=x/y` reports exactly how many
were checked against publisher-provided LFS hashes.

## Update an existing NAS checkout (only after reviewing the PR)

**Do not extract a tarball over the existing installation.** Preserve `.env`,
`.vault`, the Docker setup and old archives. The NAS may not have git.

To test this still-unmerged PR, fetch the proposed files from the branch:

```sh
cd /volume1/docker/model_vault || exit 1
BRANCH=feature/abliterated-six-models-20261023
BASE="https://raw.githubusercontent.com/KodjoV/model_vault/$BRANCH"
curl -fLsS --retry 3 "$BASE/models.json" -o models.json.ABL.new || exit 1
python3 -m json.tool models.json.ABL.new >/dev/null || exit 1
cp -p models.json models.json.before-ABL-20261023 || exit 1
mv models.json.ABL.new models.json || exit 1
mkdir -p tools
curl -fLsS --retry 3 "$BASE/tools/verify-abliterated.py" -o tools/verify-abliterated.py || exit 1
python3 -m py_compile tools/verify-abliterated.py || exit 1
python3 - <<'PY'
import json
with open("models.json", encoding="utf-8") as f:
    models = json.load(f)["models"]
abl = [m for m in models if m["tier"] == "ABL"]
assert len(abl) == 6 and all(m["enabled"] for m in abl)
print("ABL catalog OK: 6 models")
PY
```

Set **only** `SELECT_TIERS=ABL` in the local, private `.env` after saving its
previous value. Do not print `.env` or commit it. Example manual edit:
`nano /volume1/docker/model_vault/.env`.

Before starting, check that Docker Compose is present and previous Model Vault
is stopped as expected:

```sh
cd /volume1/docker/model_vault || exit 1
sudo docker compose version
sudo docker ps -a --filter name=model-vault
grep '^SELECT_TIERS=' .env
df -h /volume1/ModelVault
```

Then, only when ready for the NAS to download the six models:

```sh
sudo ./start.sh /volume1/ModelVault
./status.sh
```

The `start.sh` Compose branch rebuilds the image, so it picks up the changed
`models.json`. On this NAS Docker access previously needed `sudo`.
The service remains on the existing local Dashboard port 8790. It **must not**
be port-forwarded to the public internet. The previous archived models and
sha-pinned plans remain under the same vault root.

Verify when all six models show complete:

```sh
cd /volume1/docker/model_vault || exit 1
python3 tools/verify-abliterated.py --root /volume1/ModelVault
sudo docker compose down
```

The offline SHA256 verification reads roughly 160 GB, so it may take some time.
After stopping, restore the previous `SELECT_TIERS` in the local `.env` if
you want later default runs to use a different selection.

## B52 and optional acceleration

- RANA: archive the exact in-repo `mtp-*.gguf`; first confirm B52's llama.cpp
  supports `--spec-type draft-mtp`, then test in a separate instance.
- Humanlike: no documented matching MTP or vision module.
- Gemma: do not pair a base-model EAGLE-3 draft with abliterated weights until
  correctness and speed are measured.
- Coder390 and Qwythos: archive the known files, avoid inventing drafters.
- Flash-Next v2: archival GGUFs are **not** a Strata pack; do not bypass
  checksums, repoint the existing IQ3/UD engine or change llama-swap.

Never run untrusted models or tools with NAS admin permissions or sensitive
tokens. NAS RAID1 is not an independent backup. Make a verified second copy
before calling the archive resilient.
