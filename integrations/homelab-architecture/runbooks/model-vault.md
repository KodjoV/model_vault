<!-- Managed bootstrap entry: Model Vault. Canonical copy lives in Forgejo homelab-architecture. -->
# Runbook: Model Vault auf UGREEN

**Stand:** 15.10.2026 · **Zustand:** P0 + P1 abgeschlossen, Offline-SHA-256-Prüfung durch Betreiber als erfolgreich gemeldet, Docker-Container heruntergefahren.  
**Code:** https://github.com/KodjoV/model_vault · **Host:** UGREEN NASync DXP4800 Pro

## Ruhezustand (Normalbetrieb nach Archivierung)

Im Ruhezustand laufen **weder der Download-Dienst noch das Webdashboard**. Die gespeicherten Daten bleiben unabhängig vom Container erhalten:

- `/volume1/ModelVault/models/` – Modellgewichte und pro Repository `MODEL_VAULT_MANIFEST.json` / `MODEL_VAULT_SHA256SUMS.txt`
- `/volume1/ModelVault/.vault/` – Planung, letzter Status, Ereignislogs
- `/volume1/docker/model_vault/` – Docker-Konfiguration, Skripte, lokale `.env`

**P0:** 8 Repositories, 77,16 GiB, 111 Dateien (Live-Nachweis vom 14.10.2026).  
**P0 + P1:** 15 Repositories, 123,19 GiB und 254 Dateien als **zuletzt übermittelte Planwerte** vom 15.10.2026, 09:04:28 UTC. Anschließend Downloadende + SHA-256-Erfolg vom Betreiber bestätigt. Die abschließende detaillierte Statusausgabe wurde nicht mitgeteilt.  
**P1:** Whisper Large V3 + Turbo, Qwen3-ASR, Parakeet, Qwen3-TTS, Kokoro, MiniCPM-V. `krea/Krea-2-Raw` deaktiviert.

## Reiner Statuscheck ohne laufenden Container

```bash
cd /volume1/docker/model_vault
./status.sh
sudo docker ps -a --filter name=model-vault
```

**Achtung:** `./status.sh` liest die zuletzt persistierte `status.json` und zeigt deshalb **auch bei abgeschaltetem Container einen gespeicherten Abschlussstatus**, keine aktuelle Dienst-Lebendigkeit.

## Unabhängige SHA-256-Prüfung wiederholen

```bash
cd /volume1/ModelVault/models || exit 1
count=0
failed=0
while IFS= read -r -d '' sums; do
  count=$((count + 1))
  dir=$(dirname "$sums")
  if (cd "$dir" && sha256sum -c --quiet MODEL_VAULT_SHA256SUMS.txt); then
    echo "OK: $dir"
  else
    echo "FEHLER: $dir"
    failed=$((failed + 1))
  fi
done < <(find . -type f -name MODEL_VAULT_SHA256SUMS.txt -print0)
echo "Geprüfte Archive: $count | Fehler: $failed"
```

Bei fehlendem Manifest oder Fehlern **nicht** den gesamten Modellordner löschen; betroffene Datei und Revision gezielt untersuchen. Die SHA-256-Prüfung gegen eigene Manifeste ist kein separater Restore-Test.

## Downloadmodus bei Bedarf wieder aktivieren

```bash
cd /volume1/docker/model_vault
sudo ./start.sh /volume1/ModelVault
sudo docker logs --tail 80 model-vault
./status.sh
```

Das Skript bewahrt die bestehende `.env`; mit `SELECT_TIERS=P0,P1` sind beide Stufen ausgewählt. Bereits erfasste vollständige Dateien werden nach Größenkontrolle wiederverwendet. `models.json` ist ins Image eingebaut; bei Änderung der Modellauswahl mit Docker Compose neu bauen. Port **8790** ist dann das Dashboard (`http://<NAS-IP>:8790`, HTTP Basic Auth, User `vault`). Passwort ausschließlich aus lokaler `.env`, nicht in Forgejo speichern.

**Danach wieder herunterfahren:**

```bash
cd /volume1/docker/model_vault
sudo docker compose down
```

Entfernt nur den Compose-Container und das zugehörige Netzwerk, **nicht** die Modelle, den Plan oder das lokal gebaute Image. Ohne erneuten Start gibt es keinen laufenden Downloadserver.

## UGREEN-Spezifika

1. `/volume1` ist Btrfs; niemals Modellgewichte im OS-Overlay speichern.
2. Freigabe `/volume1/docker` (kleingeschrieben).
3. `stat -f -c %T /volume1/ModelVault` prüft den Dateisystemtyp zuverlässig; `df -T` kann umbrochene Mapper-Zeilen ausgeben.
4. Docker-Socket gehört `root:docker`; `B52_Admin` benötigt `sudo`.
5. Host-Port 8787 nutzt bereits `b52-dashboard`. Model Vault: 8790 (Host) → 8787 (Container).
6. `Dockerfile` setzt die Leserechte im Image explizit, da UGOS-ACLs andernfalls `/app/vault.py: Permission denied` auslösen konnten.
7. Für Code-Updates ohne Git: GitHub-Archiv zunächst in separaten temporären Ordner extrahieren und nur geänderte Dateien selektiv übernehmen; die lokale `.env` niemals überschreiben.

## Noch offen

- Unabhängiges Backup auf einem zweiten Medium und dokumentierter Wiederherstellungstest.
- Späterer Einsatz ausgewählter Modelle auf b52; Modellarchivierung garantiert keine vollständige Inferenz-Pipeline.
- Lizenzprüfung bei tatsächlicher Anwendung; RAID1 ist kein Offsite-Backup.
