# Model Vault – P0 + P1: Archivierungsabschluss

**Datum:** 15.10.2026 · **Host:** UGREEN NASync DXP4800 Pro  
**Abschlussmeldung:** Betreiber bestätigt: P1-Download fertig, unabhängige SHA-256-Prüfung erfolgreich und `sudo docker compose down` ausgeführt.  
**Beobachtete letzte detaillierte Statusausgabe:** 15.10.2026, 09:04:28 UTC, während P1 noch heruntergeladen wurde.

## Umfang

- **15 ausgewählte Hugging-Face-Repositories**: 8 in P0 und 7 in P1.
- **123,19 GiB** erwartetes Gesamtvolumen und **254 Dateien** laut letzter detaillierter **Planungs-/Zwischenstatusausgabe** (`./status.sh`). Die exakten Endwerte aus dem finalen `status.sh`-Lauf wurden nicht übermittelt. Deshalb werden 123,19 GiB und 254 als **zuletzt gemeldete Planwerte**, nicht als separat nachgemessener Abschlussstatus, geführt.
- Der Betreiber bestätigt die **erfolgreiche Hashprüfung** des Bestands am 15.10.2026, ohne die Terminalausgabe des Hashlaufs zu übermitteln.
- Downloader und Webdashboard wurden danach mit `docker compose down` beendet. Code, Docker-Image, Modellgewichte, Manifeste und `.vault/` bleiben auf dem NAS gespeichert.

| Stufe | HF-Repository | Planwert, GiB | Auswahl |
| --- | --- | ---: | --- |
| P0 | `m-a-p/YuE2-3B` | 6,79 | Vollständige Dateiauswahl |
| P0 | `m-a-p/YuE2-Vae` | 0,49 | Vollständige Dateiauswahl |
| P0 | `ACE-Step/Ace-Step1.5` | 9,40 | Vollständige Dateiauswahl |
| P0 | `Comfy-Org/MiniMax-Music-3` | 11,10 | Nur festgelegte INT8-, VAE- und Textencoder-Dateien |
| P0 | `abenzerps/Qwen-Image-2.1-Uncensored-GGUF` | 5,47 | Ausgewählte Q6_K-GGUF-Datei; der Repositoryname allein belegt keine Modifikation |
| P0 | `AtomicChat/Qwen-Image-2.1-Turbo-Uncensored-GGUF` | 8,01 | Ausgewählte Q5_K-Komponenten |
| P0 | `AtomicChat/Qwen-Image-2.1-Turbo-GGUF` | 5,03 | Ausgewählte Q5_K-Komponenten |
| P0 | `Qwen/Qwen-Image-2.1` | 30,86 | Vollständige Dateiauswahl |
| P1 | `openai/whisper-large-v3-turbo` | 1,51 | Vollständige Dateiauswahl |
| P1 | `openai/whisper-large-v3` | 8,63 | Ausgewählte Dateien gemäß `models.json` |
| P1 | `Qwen/Qwen3-ASR-1.7B` | 4,38 | Vollständige Dateiauswahl |
| P1 | `nvidia/parakeet-tdt-0.6b-v3` | 5,34 | Vollständige Dateiauswahl |
| P1 | `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | 4,23 | Vollständige Dateiauswahl |
| P1 | `hexgrad/Kokoro-82M` | 0,34 | Vollständige Dateiauswahl |
| P1 | `openbmb/MiniCPM-V-4.7-35B-A3B-gguf` | 21,60 | Ausgewählte Q4_K_M-GGUF- und Begleitdateien |

Werte je Modell gerundet; Addition gerundeter Zeilen kann geringfügig von der Gesamtsumme abweichen.  
`krea/Krea-2-Raw` ist in `models.json` **deaktiviert**, benötigt legitimen Zugang und zählt **nicht** zum archivierten P1-Umfang.

## Datenorte und Betriebszustand

| Gegenstand | Ablage / Zustand |
| --- | --- |
| Modelle | `/volume1/ModelVault/models/<org>/<repo>/` |
| Plan, Status, Ereignislog | `/volume1/ModelVault/.vault/` |
| Manifest und SHA-256 je Repository | `MODEL_VAULT_MANIFEST.json` und `MODEL_VAULT_SHA256SUMS.txt` in jedem Modellverzeichnis |
| Code und lokale Konfiguration | `/volume1/docker/model_vault/`; `.env` privat, nicht committen |
| Docker | `model-vault`-Container/Compose-Netzwerk mit `sudo docker compose down` beendet |
| Dashboard | Port **8790** derzeit nicht durch Model Vault belegt; beim nächsten Start erreichbar |
| Start bei Bedarf | `cd /volume1/docker/model_vault && sudo ./start.sh /volume1/ModelVault` |
| Status im Ruhezustand | `./status.sh` liest den **zuletzt gespeicherten** Status, keine Live-Messung |

## Qualität und noch offene Punkte

- **Bestätigt durch den Betreiber:** Downloadabschluss P0 + P1; erneute Offline-SHA-256-Prüfung erfolgreich; Dienst abgeschaltet.
- **Nicht damit nachgewiesen:** End-to-End-Ausführung der Modelle, Vorhandensein sämtlicher Pipeline-Abhängigkeiten, Restore auf einem anderen Datenträger, zusätzliche Kopie außerhalb der NAS.
- SHA-256 gegen ein lokal gespeichertes Manifest prüft die Unverändertheit seit der Manifest-Erzeugung. Nur wenn das Manifest zusätzlich einen vertrauenswürdigen Upstream-LFS-Hash enthält und dieser verglichen wurde, ist es auch ein unabhängiger Upstream-Abgleich.
- Das Btrfs-RAID1 auf der UGREEN ersetzt **kein separates Backup**. Eine unabhängige Archivkopie ist als spätere Maßnahme offen.
- P0/P1 sind **Prioritäten für die Archivierung**, keine Inferenzdienste oder Qualitätsstufen.

Historischer P0-Zwischenabschluss vom 14.10.2026: [P0-Nachweis](ARCHIVE_STATUS_2026-10-14.md).  
Modellselektion und Include-Muster: [models.json](../models.json).
