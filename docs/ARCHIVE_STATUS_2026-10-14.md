# Model Vault – Archivierungsnachweis P0

**Zeitpunkt der Beobachtung:** 14.10.2026, 15:55:42 UTC (17:55:42 MESZ).  
**Quelle:** Ausgabe `./status.sh` auf UGREEN DXP4800 Pro, vom Betreiber bereitgestellt.  
**Status:** `complete`, **100,0 %**, **77,16 GiB / 77,16 GiB**, **8/8** Repository-Einträge, **111/111** Dateien im Zustand `verified`.  
**Verfügbarer Speicher beim Statuslauf:** 17.080,29 GiB.

| Modell-Repository | Belegter Speicher | Archivart |
| --- | ---: | --- |
| `m-a-p/YuE2-3B` | 6,79 GiB | Vollständige Auswahl laut `models.json` (`*`) |
| `m-a-p/YuE2-Vae` | 0,49 GiB | Vollständige Auswahl laut `models.json` (`*`) |
| `ACE-Step/Ace-Step1.5` | 9,40 GiB | Vollständige Auswahl laut `models.json` (`*`) |
| `Comfy-Org/MiniMax-Music-3` | 11,10 GiB | **Ausgewählte** INT8-/VAE-/Textencoder-Komponenten; nicht gesamtes Repository |
| `abenzerps/Qwen-Image-2.1-Uncensored-GGUF` | 5,47 GiB | **Ausgewählte** Q6_K-GGUF-Komponente; Name ist kein Nachweis veränderter Gewichte |
| `AtomicChat/Qwen-Image-2.1-Turbo-Uncensored-GGUF` | 8,01 GiB | **Ausgewählte** Q5_K-GGUF-Komponente, modifizierter Encoder laut Modellauswahl |
| `AtomicChat/Qwen-Image-2.1-Turbo-GGUF` | 5,03 GiB | **Ausgewählte** Q5_K-GGUF-Denoiser-Komponente |
| `Qwen/Qwen-Image-2.1` | 30,86 GiB | Vollständige Auswahl laut `models.json` (`*`) |

**Gesamt:** 77,16 GiB. Gerundete Einzelwerte müssen nicht exakt zur gerundeten Gesamtsumme addieren.

## Was die 100 % bedeuten

Die Anzeige bestätigt den **Abschluss des konfigurierten P0-Downloadplans** samt lokalem Dateiverifikationsstatus. Sie bestätigt **nicht**, dass jedes archivierte Modell unmittelbar einsatzbereit ist, dass Zusatzkomponenten oder Workflows vorhanden sind, oder dass sämtliche ursprünglich veröffentlichten Varianten gespeichert wurden.

Der Download-Dienst speichert bei der Planung die Hugging-Face-Commitrevisionen und lokale SHA-256-Prüfsummen in `.vault/`. Die Statusausgabe wurde als Betreiberbefund dokumentiert; eine **unabhängige erneute Offline-Prüfung** und ein **Wiederherstellungstest auf separatem Datenträger** sind noch nicht nachgewiesen. Lizenz- und Nutzungsbeschränkungen bleiben bestehen.

## Reproduzierbarkeit

- Software: [KodjoV/model_vault](https://github.com/KodjoV/model_vault), `main`
- Modellplan: [models.json](https://github.com/KodjoV/model_vault/blob/main/models.json)
- Originale auf NAS: `/volume1/ModelVault/models/<org>/<repo>/`
- Metadaten, Plan, Status: `/volume1/ModelVault/.vault/`
- Anzeige im LAN: `http://NAS-IP:8790` (Basic Auth)
- CLI: `cd /volume1/docker/model_vault && ./status.sh`

**Empfohlener nächster Meilenstein:** P1 (Whisper, ASR, TTS, Vision) separat planen und starten; unabhängige Sicherung der einzigartigen P0-Modelle festlegen.
