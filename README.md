# Model Vault – UGREEN DXP4800 Pro

> **Archivstand 15.10.2026: P0 + P1 abgeschlossen, 15 Modell-Repositories, ca. 123,19 GiB im letzten Downloadplan, Offline-SHA-256-Prüfung erfolgreich.**  
> Der Betreiber hat Downloadabschluss, Hashprüfung und `sudo docker compose down` bestätigt. **Der Container und das Dashboard sind nun bewusst abgeschaltet**, die Daten bleiben erhalten.  
> [Abschlussbericht P0 + P1](docs/ARCHIVE_STATUS_2026-10-15.md) · [P0-Zwischenabschluss](docs/ARCHIVE_STATUS_2026-10-14.md).  
> Die Größe 123,19 GiB und die 254 Dateien stammen aus der letzten detaillierten *Zwischenstatus*-Ausgabe; der vollständige finale Status wurde nicht übermittelt. Archivierung ist kein End-to-End-Inferenztest oder unabhängiges Backup.


## Drei öffentliche GGUFs für B52-Vergleich (OPEN3)

Separates Tier `OPEN3`: Huihui GLM-5.3-Flash Abliterated UD-IQ2_XXS (vier Teile + Vision), ggml-org GLM-5.3-Flash Q2_K_S (zwei Teile + MTP Q4_0 + Vision) und audreyt DeepSeek V4.1 Flash 1017 Maya-XS Abliterated (eine ds4-spezifische GGUF). Zusammen ca. 585 GB, mindestens 650 GB freier Platz erforderlich. Die bereits archivierten GLM-Maya-S24/M bleiben erhalten und werden **nicht** erneut geladen. [Runbook](docs/PUBLIC_THREE_GGUF_2026-10.md) · [NAS-Starthelfer](tools/start-open3-nas.sh). Keine Registrierung für die öffentlich sichtbaren Quell-Repos erkennbar; echte Transfers auf dem NAS noch nicht getestet.

## OrcaRouter DeepSeek V4.1 Abliterated (ORCA)

Separates **ORCA**-Tier für die gegatete Mix-256G-Fassung (7 GGUF-Dateien, Engram enthalten) und die Kalibrierungsdatei `imatrix.gguf` – zusammen ca. 348 GB. **Langfristige Sicherung, kein B52-Strata-Test:** 235,8 GB Gewichte im Arbeitsspeicher ohne Engram; andere Quantisierung als unser ISTA-DeepSeek. Zugangsbedingungen bei Hugging Face zuerst annehmen und `HF_TOKEN` nur in der lokalen `.env` setzen. [Kurzanleitung](docs/ORCA_DEEPSEEK_V41_ARCHIVE_2026-10.md).

## P0: DeepSeek V4.1-Flash 1017 mit Strata

Neues isoliertes Tier `DS41` für die **IQ2_XS**-Quantisierung mit vier Backbone-GGUFs, Engram-Tabelle und Unsloth-DSpark-Q8_0-Drafter; ca. **274 GB** Gesamtarchiv. Alle Downloads laufen über den bestehenden Model Vault und ändern keine Strata- oder llama-swap-Konfiguration. [Vorgehen und B52-Testplan](docs/DEEPSEEK_V41_PRIORITY_2026-10.md). **Wichtig:** Strata Terminal 0.2.4.1 + eigener `strata-dsv41`-Engine benötigt; diese Software ist noch nicht auf B52 eingerichtet. Der Download beginnt erst, wenn die lokale `.env` auf `SELECT_TIERS=DS41` gesetzt und der NAS-Dienst bewusst neu gestartet wird. Laufende ABL-Downloads zuvor prüfen.

## Neue Abliterated-Auswahl (ABL)

Sechs gezielt ausgewählte GGUF-Modelle inklusive passender MTP-/Bildmodule liegen im separaten Katalog-Tier `ABL` (kein Download allein durch den GitHub-Commit). Anleitung für das NAS und SHA256-Nachprüfung: [Abliterated six-model archive](docs/ABLITERATED_SIX_2026-10.md). `SELECT_TIERS=ABL` wählen, bevor der Vault bewusst neu gestartet wird. P0/P1 bleiben unberührt.

Private/offline-capable model archive: pinned Hugging Face commits, resumable HTTP downloads, SHA-256 manifests, live dashboard and CLI status. **Only scripts belong in GitHub; model weights, credentials and status live on the NAS.**

## UGREEN first setup

1. Find the **data** volume, not the system overlay. On this UGREEN: `/volume1` is a 19 TB btrfs volume.
2. The example data root is `/volume1/ModelVault`; you must have NAS-user write permission. Prefer creating dedicated **ModelVault** and **docker** shared folders in UGOS UI so permissions are correct.
3. Auf UGOS ist `git` nicht installiert. Für **eine Neuinstallation** das GitHub-Archiv direkt beziehen (kein Überschreiben einer bestehenden lokalen `.env`):

```sh
cd /volume1/docker
mkdir -p model_vault
cd model_vault
curl -fL --retry 3 -o model_vault-main.tar.gz https://github.com/KodjoV/model_vault/archive/refs/heads/main.tar.gz
tar -tzf model_vault-main.tar.gz >/dev/null
tar -xzf model_vault-main.tar.gz --strip-components=1
rm model_vault-main.tar.gz
chmod +x start.sh status.sh nas-layout.sh
./nas-layout.sh
sudo ./start.sh /volume1/ModelVault
```

Bestehende Installation: **nicht blind entpacken** (insbesondere die lokal erzeugte `.env` behalten). Docker benötigt hier `sudo`, weil `B52_Admin` nicht Mitglied der Gruppe `docker` ist. Der Download läuft anschließend dauerhaft im Container.

`start.sh` uses host port **8790** by default (internal port 8787; avoids the existing b52-dashboard on host port 8787), and auto-creates a local `.env` password, refuses a data path off `/volume1`, and checks btrfs and write access. Container files are explicitly world-readable inside the image for UID 1000 operation. `models.json` is baked into the image to avoid UGOS ACL issues on bind-mounted source files; rebuild the image when changing model selections. It uses Compose if available; otherwise Docker build/run directly, so Compose is **not required**. Docker itself must be accessible to the current user. An isolated `DOCKER_CONFIG` avoids using the NAS account's broken `~/.docker/config.json`.

## Betriebszustand: Archiv-Modus / Downloader bei Bedarf

Nach erfolgreichem P0-/P1-Download wurde der Container mit `sudo docker compose down` heruntergefahren. Das ist der **gewünschte Ruhezustand**: kein dauerhaft laufendes Dashboard; Modelle, `.vault/`, Image, Skripte und lokale Konfiguration bleiben erhalten.

```sh
cd /volume1/docker/model_vault
./status.sh                             # Zuletzt gespeicherter Status, nicht live
sudo docker ps -a --filter name=model-vault
sudo ./start.sh /volume1/ModelVault     # Nur für neuen Downloadlauf
sudo docker compose down               # Nach Abschluss wieder abschalten
```

Eine erfolgreiche SHA-256-Kontrolle anhand gespeicherter Manifeste ist vom Betreiber bestätigt. Ein separater Restore-Test und eine unabhängige Sicherung bleiben offen.

## Progress (nur bei aktivem Container)

Go to `http://NAS-IP:8790` on LAN/Tailscale, log in as **vault**, and get the password from `.env` (`grep '^UI_PASSWORD=' .env`). Browser updates every 3 seconds and shows overall GiB, percent, model/file completions, MiB/s, ETA, errors, disk capacity. You can pause/resume/retry from dashboard.

In SSH session:

```sh
./status.sh
export DOCKER_CONFIG="$(pwd)/.docker-local"
docker logs -f --tail=50 model-vault
```

Status and `.part` downloads persist under `/volume1/ModelVault/.vault` and `/volume1/ModelVault/models`. NAS restart resumes the downloader; no ChatGPT session needs to remain open.

## Paths

- `docker/model_vault`: cloned GitHub source and local `.env` only.
- `ModelVault/models/ORG/REPO/`: saved model files, same namespace as HF.
- `ModelVault/.vault/`: plan, status, logs and pause flags.

P0 umfasst acht archivierte Repository-Einträge: YuE2 (+ VAE), ACE-Step 1.5, MiniMax Music 3 (ausgewählte INT8-Pipeline-Komponenten) sowie Qwen Image 2.1 und ausgewählte GGUF-/Turbo-Komponenten. **P1 ist ebenfalls archiviert:** Whisper Large V3 und Turbo, Qwen3-ASR, Parakeet, Qwen3-TTS, Kokoro und MiniCPM-V. Die sieben P1-Einträge sind in `models.json` vorbereitet und wurden mit lokalem `SELECT_TIERS=P0,P1` heruntergeladen; Neuinstallationen wählen standardmäßig weiterhin P0. Details: [Abschlussbericht](docs/ARCHIVE_STATUS_2026-10-15.md). Licenses (including non-commercial/research restrictions) still apply. Krea gated models are *not* auto-bypassed. For legitimate access, set `HF_TOKEN` locally in `.env`; never commit it.

## Security and limitations

The web server uses Basic authentication **over HTTP**. Never port-forward port 8790. Use only trusted LAN/Tailscale or an HTTPS reverse proxy. NAS RAID1 is not a true independent backup; copy irreplaceable snapshots separately. Hugging Face repos can change, vanish, or rate-limit; plan stores an immutable revision and hash evidence. A recorded local SHA-256 is not the same as verification against the publisher unless upstream LFS SHA is known.

Version 1: Unit-Tests für Resume/Dashboard liegen vor. **P0** war am 14.10.2026 in `status.sh` mit 77,16 GiB / 111 Dateien abgeschlossen; am **15.10.2026** wurde vom Betreiber der Abschluss von **P0 + P1**, eine erfolgreiche SHA-256-Prüfung sowie die Abschaltung des Containers bestätigt. Die unabhängige Wiederherstellung auf einem zweiten Medium und die End-to-End-Modell-Ausführung sind noch nicht validiert.

## Eintrag in die private Forgejo-Heimarchitektur

Das maßgebliche Architektur-Repository ist **`homelab-architecture` in Forgejo**. Die zwei deutschsprachigen Einträge wurden beim P0-Abschluss bereits nach Forgejo übertragen; **nach P1 ist eine gezielte Aktualisierung beider Dateien erforderlich**:

- [Inventar / Abhängigkeiten](integrations/homelab-architecture/inventory/model-vault.md) → `inventory/model-vault.md`
- [Betriebs-Runbook](integrations/homelab-architecture/runbooks/model-vault.md) → `runbooks/model-vault.md`

Auf dem NAS läuft Forgejo über Port **3002**. Übertragungswerkzeug: [tools/publish-to-forgejo.py](tools/publish-to-forgejo.py). Das Programm verwendet die **lokale** Forgejo-API über `127.0.0.1:3002` und fragt einen Forgejo-Token bei `--apply` verdeckt im Terminal ab; es speichert ihn nicht. Standardmäßig nur Vorschau, keine Schreibaktion:

```sh
cd /volume1/docker/model_vault
mkdir -p tools
curl -fLsS --retry 3 https://raw.githubusercontent.com/KodjoV/model_vault/main/tools/publish-to-forgejo.py -o tools/publish-to-forgejo.py
python3 tools/publish-to-forgejo.py
python3 tools/publish-to-forgejo.py --apply --update --repo forgejo_admin/homelab-architecture
```

Wenn der Forgejo-Eigentümer anders heißt, `--repo EIGENTÜMER/homelab-architecture` verwenden. Eine bestehende abweichende Datei wird standardmäßig **nicht überschrieben**. Spätere Aktualisierungen erfordern `--apply --update` und können nur den von uns gekennzeichneten Eintrag aktualisieren. Die **P1-Aktualisierung** in Forgejo ist **erst nach erfolgreicher Skriptausführung** abgeschlossen. Es werden keine Modellgewichte, Tokens oder lokalen `.env`-Dateien übertragen.
