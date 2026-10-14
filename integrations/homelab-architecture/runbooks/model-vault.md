<!-- Managed bootstrap entry: Model Vault. Canonical copy lives in Forgejo homelab-architecture. -->
# Runbook: Model Vault auf UGREEN

**Dienst:** `model-vault` · **Host:** UGREEN DXP4800 Pro  
**Stand:** 14.10.2026 · **Code:** https://github.com/KodjoV/model_vault

## Status und Fortschritt

```bash
cd /volume1/docker/model_vault
./status.sh
sudo env DOCKER_CONFIG="$PWD/.docker-local" docker ps --filter name=model-vault
sudo env DOCKER_CONFIG="$PWD/.docker-local" docker logs --tail 80 model-vault
```

Weboberfläche: `http://<NAS-IP>:8790`. Benutzername `vault`; Passwort **nur lokal** in `.env` (nicht in Forgejo dokumentieren).

**Erfolgsmessung P0 (14.10.2026, 15:55:42 UTC):** 100,0 %, 77,16 GiB / 77,16 GiB; 8/8 Repos; 111/111 Dateien. `complete` bezieht sich auf die konfigurierte Auswahl.

## Betriebsstart / Neustart

```bash
cd /volume1/docker/model_vault
sudo ./start.sh /volume1/ModelVault
```

`start.sh` berücksichtigt vorhandene `.env` und verwendet Docker Compose, falls verfügbar. Das Container-Image wird aus `Dockerfile` gebaut. Docker benötigt in dieser Installation `sudo` (Socket `root:docker`, Benutzer nicht in Gruppe `docker`).

Wenn das Dashboard keine Antwort liefert, Container und Logs prüfen:

```bash
sudo env DOCKER_CONFIG="$PWD/.docker-local" docker compose ps
sudo env DOCKER_CONFIG="$PWD/.docker-local" docker logs --tail 100 model-vault
```

## Wiederanlauf, Daten und Prüfsummen

- Code und Konfiguration: `/volume1/docker/model_vault`
- Konfiguration `.env` privat halten; **nicht ersetzen** bei Updates.
- Dateidaten: `/volume1/ModelVault/models`; Betriebsstatus: `/volume1/ModelVault/.vault`.
- `.part`-Dateien zeigen unvollständige Downloads an; nicht manuell aufräumen, solange ein Download läuft.
- `plan.json`, `status.json` und SHA-256-Manifest/Metadaten bei Backup mit aufnehmen.
- Nach NAS-Neustart sollte Docker den Dienst automatisch starten (`restart: unless-stopped`).
- Erfolgreicher Dateidownload ist **kein** End-to-End-Inferenztest. Unabhängiger Restore-Test steht noch aus.

## GitHub aktualisieren ohne installiertes Git

```bash
cd /volume1/docker/model_vault
curl -fL --retry 3 -o model_vault-main.tar.gz \
  https://github.com/KodjoV/model_vault/archive/refs/heads/main.tar.gz

tar -tzf model_vault-main.tar.gz >/dev/null
# Achtung: NICHT blind über bestehende .env oder laufende Konfiguration entpacken.
# Vor Update: alte Codeversion sichern, laufenden Dienst planen/stoppen;
# danach Skripte selektiv oder über temporäres Verzeichnis übernehmen und neu bauen.
```

## Bekannte UGREEN-Besonderheiten

1. `/volume1` = Btrfs-Datenvolume; Systemoverlay nicht für Modellgewichte verwenden.
2. Freigabe heißt **`docker`** (nicht `Docker`).
3. `df -T` zeigt bei langem Mapper-Gerätenamen umbrochene Zeilen; Btrfs zuverlässig mit `stat -f -c %T /volume1/ModelVault` bestimmen.
4. Docker-API-Socket `root:docker`; `B52_Admin` hat keinen direkten Socketzugriff: `sudo` einsetzen, **keine** pauschalen Socket-Rechte.
5. Host-Port **8787** ist bereits durch `b52-dashboard` belegt. Model Vault verwendet **8790 → 8787**.
6. Ursprünglich `/app/vault.py: Permission denied` durch UGOS-ACL-bedingte Image-Dateimodi; `Dockerfile` setzt nun Leserechte im Image. `models.json` wird ins Image kopiert; nach Planänderung Containerimage neu bauen.

## Weitere Stufen

Die Konfiguration `models.json` definiert P0 und P1. P1 enthält Whisper, Qwen3-ASR, Parakeet, Qwen3-TTS, Kokoro, MiniCPM-V; Krea Raw bleibt gesperrt, bis legitimer Zugang vorliegt.

P1 **nicht** durch Änderung allein als abgeschlossen dokumentieren – erst nach neuer Statusausgabe.
