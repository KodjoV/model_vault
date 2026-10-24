# P0: DeepSeek V4.1-Flash-1017 GSQ-RCO on B52

Status: source selection committed on GitHub. **No NAS download, Strata setup or B52 test executed by ChatGPT.**

## Why this is P0

Source: [ISTA-DASLab DeepSeek V4.1](https://huggingface.co/ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/blob/main/README.md).
The new DeepSeek architecture needs Strata **0.2.4.1 Terminal** and a separate signed
`strata-dsv41` engine package. The existing B52 Qwen engine cannot run this model
just because it runs Flash-Next; **do not point llama-swap to new GGUFs yet**.
Strata docs: https://github.com/Niko1221/Strata/blob/main/docs/DEEPSEEK41.md

## Vault download plan (isolated)

In `models.json` there are two repos in the isolated `DS41` tier:

1. `ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF`: **IQ2_XS** backbone,
   4 GGUF shards (155.23 GB), shared `DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf`
   (110.60 GB), RCO tensor-allocation list, README.
2. `unsloth/DeepSeek-V4.1-Flash-1017-GGUF`: exact
   `dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf` drafter (~7.98 GB)
   and its docs. **No other Unsloth quants.**

Total ~274 GB plus small text files. IQ2_XS was selected over IQ2_XXS
because Strata's fixed-text comparisons give **smaller loss on code and agents**:
IQ2_XS code +3.2% and agent +2.2% perplexity vs original; IQ2_XXS +8.6%
and +5.3%. The ISTA model card only shows task scores for IQ1_M and IQ2_XXS.
Neither benchmark is a B52 test.

The existing `vault.py` resolves each repo's immutable full 40-character
commit SHA when first planned; records it in `.vault/plan.json`, checks LFS SHA256
when exposed, hashes every file, and creates per-model manifests. Do not confuse
a local SHA256 with an independent upstream SHA256 when no remote LFS hash is
available.

The two repos will be kept in their own standard paths:

- `/volume1/ModelVault/models/ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/`
- `/volume1/ModelVault/models/unsloth/DeepSeek-V4.1-Flash-1017-GGUF/`

### NAS: apply proposed GitHub branch

The earlier six-model PR is still unmerged; **use its precise branch commit**.
Do not overwrite `.env`, previous models, `.vault`, or Docker definitions.
Check for active ABL downloads first. Switching tiers restarts only the
Model Vault container; incomplete `.part` downloads are resumable.

```sh
cd /volume1/docker/model_vault || exit 1
sudo docker ps -a --filter name=model-vault
./status.sh
df -h /volume1/ModelVault
```

Download the updated `models.json` from the PR's final reviewed commit, to
`models.json.next` and validate JSON before moving it. Always retain a local
backup of the previous catalog. The first execution must be an explicit user
choice because it can restart an ongoing download.

Set only `SELECT_TIERS=DS41` in private `.env`, and check:

```sh
grep '^SELECT_TIERS=' /volume1/docker/model_vault/.env
cd /volume1/docker/model_vault || exit 1
sudo ./start.sh /volume1/ModelVault
./status.sh
```

This launches the existing container that uses HTTPS + HTTP Range/resume and
the existing local dashboard; it does **not** need the Hugging Face CLI.
The selected four shards, Engram, and DSpark arrive on NAS. No GPU service starts.

After all DS41 downloads are complete, rehash both archives with the shared read-only verifier:

```sh
cd /volume1/docker/model_vault || exit 1
python3 tools/verify-abliterated.py --tier DS41 --root /volume1/ModelVault
```

This reads the entire ~274 GB and stops on any missing, changed, or wrong-size file.
It also verifies against any upstream LFS SHA256 recorded in the manifests.
 Save the two full revision SHA values
from `MODEL_VAULT_MANIFEST.json`. For files with a publisher-provided
SHA256, compare them against it; where it is absent, keep the recorded local
digest and note the limitation.

```sh
cd /volume1/docker/model_vault || exit 1
./status.sh
sudo docker compose down
```

Restore the previous `SELECT_TIERS` later if desired. Docker is meant to
remain down after archive completion.

## B52 testing (after verified NAS archive)

1. Verify 128 GB RAM, RTX 3090 Ti 24 GB, enough free NVMe space and **current
   installed Strata version**. Do not assume existing 0.2 beta is 0.2.4.1.
2. **Preserve** existing Strata Qwen packs, configs, ports 8080/8091 and
   llama-swap. Make a **separate DeepSeek test installation/config**, without
   changing Qwen binaries until tested. Use official signed `strata-dsv41`
   package. Strata Terminal 0.2.4.1 fixes missing DeepSeek preparation scripts.
3. Transfer the four backbone shards and Engram from NAS to the same local
   B52 test model directory. Transfer the DSpark GGUF from its separate Vault
   repo there too; this is a runtime **copy**, not a NAS archive mutation.
   Use rsync over SSH with the **actual verified NAS shared-folder paths**,
   since the previously attempted `/volume1/ModelVault` rsync path failed.
4. On a verified isolated Strata 0.2.4.1 installation, use its
   `./setup.sh --family deepseek41 --gguf-dir DIR` setup flow; follow the
   prompts and verify `strata-dsv41 --pack-info` / included smoke test.
   **Never** add `--skip-tensors`, `--dense-override`, or a checksum bypass.
5. Start on a dedicated unused local port and keep Pi off until smoke passes.
   Benchmark against existing Flash-Next IQ3_S using identical prompts, context,
   seeds where available, and real code tasks. Record prefill/decode t/s,
   prompt length, cache, wall time, energy Wh, task success and tool behavior.
   Try DSpark `auto` first; test off/on only after a working baseline.
6. For the first trials use context 8192 (Strata's default), then 32K/64K.
   Do **not** assume the claimed 1M context is usable with 128 GB RAM.

Strata's public measurements on RTX 3060 12 GB report roughly 8-10 token/s
on code; no validated B52/3090 Ti performance yet. This is an exploratory
**quality-first**, not speed-first, model. Production swap requires evidence
from our Agentic8 tasks and performance tests.

## Safety

No NAS admin model execution. No public exposure of the API or dashboard.
No copying tokens into a public repo. Never merge or change `llama-swap`
before an isolated test. The 24 GB RTX 3090 Ti is enough VRAM for a test,
but model speed/quality on this PC remains unverified.
