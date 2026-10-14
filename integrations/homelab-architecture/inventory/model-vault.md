<!-- Managed bootstrap entry: Model Vault. Canonical copy lives in Forgejo homelab-architecture. -->
# Model Vault – Modellarchiv (UGREEN)

**Bestätigt am:** 14.10.2026 · **Dienststatus:** P0-Download abgeschlossen; Docker-Anwendung aktiv laut Betreiberdiagnose; späterer Laufzeitstatus separat zu prüfen.  
**Zweck:** Offline-fähige Archivierung ausgewählter offener Modellgewichte als Schutz gegen gelöschte Repositories, Zugangsänderungen und nicht reproduzierbare Releases. **Kein Inferenz-Server.**

## Einordnung in die Heimarchitektur

| Feld | Wert |
| --- | --- |
| Host | UGREEN NASync DXP4800 Pro, UGOS, Btrfs-Datenvolume `/volume1` |
| Container | `model-vault` (Docker Compose, Image lokal gebaut aus Python 3.12 slim) |
| Quellcode | [GitHub: KodjoV/model_vault](https://github.com/KodjoV/model_vault) |
| Softwarepfad | `/volume1/docker/model_vault` (`docker` **kleingeschrieben**) |
| Datenfreigabe | `/volume1/ModelVault` |
| Gewichte | `/volume1/ModelVault/models/<HF-Organisation>/<HF-Repo>/` |
| Betriebsdaten | `/volume1/ModelVault/.vault/` (Plan, Status, Logs, Downloadzustand) |
| Dashboard | `http://<NAS-IP>:8790` → Container-Port 8787; Basic Auth `vault` |
| Netzwerk | Nur vertrauenswürdiges LAN/Tailscale; **keine Router-Portfreigabe** |
| Compose | `/volume1/docker/model_vault/compose.yaml` |
| Zugriff | Docker über `sudo`, weil `B52_Admin` keine Socket-Rechte hat |
| Ressourcen | NAS-Datenträger und Internet; keine lokale GPU erforderlich |
| Inferenz | Spätere Nutzung durch b52 oder weitere Clients, **nicht** Teil des Archivdienstes |

## Bestätigtes Inventar: P0

Aus `./status.sh` vom **14.10.2026, 15:55:42 UTC**:

- **100,0 % abgeschlossen**, **77,16 GiB / 77,16 GiB**
- **8 von 8 Modell-Repositories**
- **111 von 111 Dateien** im lokalen Status `verified`
- **17.080,29 GiB** freier Platz zum Messzeitpunkt

| HF-Repository | Archiviert | Art |
| --- | ---: | --- |
| `m-a-p/YuE2-3B` | 6,79 GiB | Vollständige Auswahl |
| `m-a-p/YuE2-Vae` | 0,49 GiB | Vollständige Auswahl |
| `ACE-Step/Ace-Step1.5` | 9,40 GiB | Vollständige Auswahl |
| `Comfy-Org/MiniMax-Music-3` | 11,10 GiB | Selektierte lokale ComfyUI-Komponenten |
| `abenzerps/Qwen-Image-2.1-Uncensored-GGUF` | 5,47 GiB | Selektierte Q6_K-Datei; nicht nachgewiesen „abliteriert“ |
| `AtomicChat/Qwen-Image-2.1-Turbo-Uncensored-GGUF` | 8,01 GiB | Selektierte Q5_K-Komponente |
| `AtomicChat/Qwen-Image-2.1-Turbo-GGUF` | 5,03 GiB | Selektierte Q5_K-Komponente |
| `Qwen/Qwen-Image-2.1` | 30,86 GiB | Vollständige Auswahl |

Einzelwerte sind gerundet. `complete` bedeutet Abschluss der **konfigurierten Downloadauswahl**, nicht automatischer Nachweis der lauffähigen End-to-End-Modellpipelines.

## Sicherheit, Datenhaltung und Grenzen

- Dashboard mit HTTP Basic Auth; Passwort ausschließlich in `/volume1/docker/model_vault/.env`, **niemals** in Repository, Tickets oder Logs kopieren.
- Original-Repositories, ausgewählte Quantisierungen, gültige Lizenzen und möglicher Gating-Status müssen separat unterschieden werden; Ablage ist keine zusätzliche Nutzungslizenz.
- Im `ModelVault`-Datenverzeichnis liegen Modelle, lokale SHA-256-Metadaten und angefangene `.part`-Downloads. Archivierte Gewichte nicht zu Git hinzufügen.
- Btrfs/RAID1 schützt vor einem Laufwerksausfall, **nicht** vor unbeabsichtigtem Löschen, Ransomware oder Ausfall des ganzen NAS. Eine unabhängige Zweitkopie steht noch aus.
- Persistenter Status `/volume1/ModelVault/.vault/status.json`. Download fortsetzbar nach Unterbrechungen.
- `ModelVault` ist **kein** Ersatz für den separaten Backup-Plan von Paperless, KeePass, Nextcloud und Rechnern.

## Abhängigkeiten / Beziehungen

- **UGREEN → Docker → Model Vault → Hugging Face** (Download-/Planungskette)
- **UGREEN → Btrfs `/volume1/ModelVault`** (dauerhafter Speicher)
- **b52 (LLM-/GPU-Rechner) → Model Vault** (potenzielle spätere Nutzung archivierter Gewichte; **noch keine Integration bestätigt**)
- **Forgejo `homelab-architecture`** ist die maßgebliche Heimarchitektur-Dokumentation, **GitHub `model_vault`** ist die Codequelle.

**Betrieb / Diagnose:** Siehe `runbooks/model-vault.md`.  
**Modellplan:** https://github.com/KodjoV/model_vault/blob/main/models.json
