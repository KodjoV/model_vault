# GLM-5.3-Flash: Maya-S24 und Maya-M auf dem NAS laden

Stand: 19.10.2026. Eigenständiges Download-Skript, **kein Eingriff** in laufende oder archivierte Model-Vault-Jobs.

- [Skript](../tools/download-glm53-maya.sh)
- [Quelle: Project Maya v1.1.16](https://github.com/mw00/project-maya/releases/tag/v1.1.16)
- [Gewichte auf Hugging Face](https://huggingface.co/peasantsmith/GLM-5.3-Flash-Maya-GGUF)

## Ziel

Zwei vollständige Quantisierungen aus **demselben** Hugging-Face-Repo:

| Ordner | Datenmenge | Dateien |
| --- | ---: | ---: |
| `Maya-S24/` | ca. 94,7 GB | 3 GGUF |
| `Maya-M/` | ca. 116 GB | 3 GGUF |

Zusammen 210,7 GB. Platzkontrolle verlangt etwa 220 GB (einschließlich einer Reserve).
Das Skript lädt erst S24, dann M, nutzt `curl -C -` für abgebrochene Downloads und prüft jede fertige Datei gegen die SHA-256-Werte aus `mw00/project-maya` Version v1.1.16. Es überschreibt keine fertigen Dateien und startet keine Inferenz.

Beide Varianten liegen in einem gemeinsamen Hugging-Face-Repository. Die vorhandene `models.json` kann ein Repository nur einmal auswählen. Darum bleibt dieser Download bewusst von der alten P0/P1-Archivierung getrennt.

## Auf dem UGREEN-NAS holen

UGOS hat auf dieser Installation **kein Git**. Deshalb per GitHub-Rohdatei holen; die laufende Model-Vault-Installation nicht entpacken oder überschreiben:

```sh
cd /volume1/docker/model_vault
curl -fL --retry 3 \
  https://raw.githubusercontent.com/KodjoV/model_vault/main/tools/download-glm53-maya.sh \
  -o download-glm53-maya.sh
sh -n download-glm53-maya.sh
```

## Nachts starten

Für die Nacht vom 19. auf den 20. Oktober 2026 einen **einmaligen** NAS-Zeitauftrag für 02:00 Uhr erstellen; Befehl:

```sh
sh /volume1/docker/model_vault/download-glm53-maya.sh \
  /volume1/ModelVault/models/peasantsmith/GLM-5.3-Flash-Maya-GGUF \
  >> /volume1/ModelVault/maya-glm53-download.log 2>&1
```

Das Zeitfenster ist nur ein Vorschlag, **kein bereits angelegter Zeitauftrag**.

Bei Bedarf direkt starten:

```sh
sh /volume1/docker/model_vault/download-glm53-maya.sh
```

Bei einem Abbruch denselben Befehl erneut ausführen. Fertige Dateien werden über SHA-256 erkannt, `.part`-Dateien fortgesetzt. Eine fehlerhafte fertige Datei oder nicht passende Prüfsumme führt zum Abbruch, nicht zum Überschreiben. Für den späteren Einsatz auf b52 Dateien auf dessen lokale NVMe kopieren.

### Wichtige Grenzen

- Voraussetzung: Datenvolume `/volume1` (UGREEN), existierender Ordner `/volume1/ModelVault/models/peasantsmith` und Schreibrechte.
- Voraussetzungen: `curl`, `sha256sum`, `df`, `du`, `awk`, `sh`.
- Das Skript lädt nur die GGUF-Gewichte, **nicht** das optionale Vision-Modul oder DFlash2.
- Modelle brauchen freien Speicherplatz und lang laufende Verbindung. Bei 100 Mbit/s dauern 210,7 GB allein rechnerisch mindestens etwa 4,7 Stunden (ohne Protokoll-Overhead).
- Kein unabhängiges Backup: Das Downloadziel liegt auf demselben NAS.

