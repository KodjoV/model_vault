<!-- Managed bootstrap entry: Model Vault. Canonical copy lives in Forgejo homelab-architecture. -->
# Model Vault – Modellarchiv (UGREEN)

**Aktualisiert:** 15.10.2026 · **Stand:** P0 + P1 archiviert, vom Betreiber SHA-256-geprüft, Downloader/Dashboard danach bewusst abgeschaltet (`sudo docker compose down`).  
**Zweck:** Offline-fähige Archivierung ausgewählter Modellgewichte zur langfristigen Aufbewahrung und späteren Nutzung durch andere Systeme. **Kein eigener Inferenz-Server.**

## Einordnung in die Heimarchitektur

| Feld | Wert |
| --- | --- |
| Host | UGREEN NASync DXP4800 Pro, UGOS, Btrfs-Datenvolume `/volume1` |
| Container | `model-vault`, bei Bedarf per Docker Compose gestartet; **aktuell entfernt/gestoppt** |
| Quellcode | [GitHub: KodjoV/model_vault](https://github.com/KodjoV/model_vault) |
| Softwarepfad | `/volume1/docker/model_vault` (`docker` **kleingeschrieben**) |
| Datenfreigabe | `/volume1/ModelVault` |
| Gewichte | `/volume1/ModelVault/models/<org>/<repo>/` |
| Betriebsdaten | `/volume1/ModelVault/.vault/` (Plan, Status, Log, Downloadzustand) |
| Dashboard | Nur bei aktivem Container: `http://<NAS-IP>:8790` → interner Port 8787; Basic Auth `vault` |
| Netzwerk | Nur vertrauenswürdiges LAN/Tailscale; **keine Router-Portfreigabe** |
| Compose | `/volume1/docker/model_vault/compose.yaml` |
| Rechte | Docker über `sudo`, weil `B52_Admin` keine Socket-Rechte hat |
| Ressourcen | NAS-Speicher und Internet für Download; keine lokale GPU |
| Inferenz | Spätere Nutzung auf b52 oder weiteren Clients; **keine Integration hier nachgewiesen** |

## Archivinventar: P0 + P1

**Betreiberbestätigung 15.10.2026:** P1 abgeschlossen, Offline-SHA-256-Prüfung des Bestands erfolgreich, Docker Compose heruntergefahren.  
**Letzter übermittelter detaillierter Zwischenstatus:** 15.10.2026, 09:04:28 UTC; **123,19 GiB und 254 Dateien als Planwerte**, noch während des Downloads. Der letzte vollständige `status.sh`-Ausdruck wurde nicht übermittelt; die Werte deshalb nicht als separat nachgemessene Abschlusswerte darstellen.

| Stufe | Hugging-Face-Repository | Geplant, GiB | Archivart |
| --- | --- | ---: | --- |
| P0 | `m-a-p/YuE2-3B` | 6,79 | Vollständige Auswahl |
| P0 | `m-a-p/YuE2-Vae` | 0,49 | Vollständige Auswahl |
| P0 | `ACE-Step/Ace-Step1.5` | 9,40 | Vollständige Auswahl |
| P0 | `Comfy-Org/MiniMax-Music-3` | 11,10 | Ausgewählte ComfyUI-INT8- und VAE-Komponenten |
| P0 | `abenzerps/Qwen-Image-2.1-Uncensored-GGUF` | 5,47 | Ausgewählte Q6_K-Komponente; Modifikation durch Namen nicht belegt |
| P0 | `AtomicChat/Qwen-Image-2.1-Turbo-Uncensored-GGUF` | 8,01 | Ausgewählte Q5_K-Komponenten |
| P0 | `AtomicChat/Qwen-Image-2.1-Turbo-GGUF` | 5,03 | Ausgewählte Q5_K-Komponenten |
| P0 | `Qwen/Qwen-Image-2.1` | 30,86 | Vollständige Auswahl |
| P1 | `openai/whisper-large-v3-turbo` | 1,51 | Vollständige Auswahl |
| P1 | `openai/whisper-large-v3` | 8,63 | Ausgewählte Dateien gemäß `models.json` |
| P1 | `Qwen/Qwen3-ASR-1.7B` | 4,38 | Vollständige Auswahl |
| P1 | `nvidia/parakeet-tdt-0.6b-v3` | 5,34 | Vollständige Auswahl |
| P1 | `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | 4,23 | Vollständige Auswahl |
| P1 | `hexgrad/Kokoro-82M` | 0,34 | Vollständige Auswahl |
| P1 | `openbmb/MiniCPM-V-4.7-35B-A3B-gguf` | 21,60 | Ausgewählte Q4_K_M- und Begleitdateien |

**15 Repositories insgesamt.** Zahlen gerundet. `krea/Krea-2-Raw` bleibt deaktiviert und wurde nicht archiviert. `complete` bezieht sich nur auf die konfigurierte Modellauswahl, nicht auf nachgewiesene End-to-End-Ausführbarkeit.

## Datenhaltung, Sicherheit, noch offene Aufgaben

- Modellverzeichnisse enthalten `MODEL_VAULT_MANIFEST.json` und `MODEL_VAULT_SHA256SUMS.txt`. Offline-Prüfung wurde am 15.10.2026 als erfolgreich gemeldet.
- Dashboard im Ruhezustand **nicht verfügbar**. `./status.sh` liest zuletzt gespeicherte Daten, auch wenn der Container nicht mehr läuft.
- Passwort nur lokal in `/volume1/docker/model_vault/.env`; keine Secrets oder Gewichte in GitHub/Forgejo.
- Lizenz-, Gating- und Einsatzbedingungen gelten unabhängig von erfolgreichem Download.
- **Offen:** unabhängige Zweitkopie außerhalb dieses NAS und ein Restore-Test; Btrfs/RAID1 ist kein vollständiges Backup.
- Model Vault ersetzt nicht die separaten Backups von Paperless, KeePass, Nextcloud und Rechnern.

## Beziehungen

- **UGREEN → Btrfs `/volume1/ModelVault`** (dauerhafte Modellbibliothek)
- **UGREEN → Docker → Model Vault → Hugging Face** (nur beim Download eingeschaltet)
- **b52 → NAS-Modellbibliothek** (potenzielle spätere Modellnutzung; noch nicht als Integration bestätigt)
- **Forgejo `homelab-architecture`** = maßgebliche Architekturdokumentation; **GitHub `model_vault`** = Code und Archivierungsnachweise

**Betrieb:** `runbooks/model-vault.md` · **Modellplan:** https://github.com/KodjoV/model_vault/blob/main/models.json  
**Abschlussnachweis:** https://github.com/KodjoV/model_vault/blob/main/docs/ARCHIVE_STATUS_2026-10-15.md
