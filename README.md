# UGREEN Model Vault · V1

Ein selektiver, wiederaufnehmbarer Hugging-Face-Downloader mit dauerhaftem NAS-Archiv und lokaler Live-Webansicht. **Alle Bytes liegen auf dem NAS.** Auf GitHub gehören nur die Skripte, niemals Modelldaten, Passwörter oder Tokens.

## Schnellstart auf der UGREEN

Voraussetzung: UGREEN Docker/Compose installiert, genug Platz auf der Archivfreigabe. Im NAS-Terminal:

```bash
# ZIP auf UGREEN entpacken, in das Verzeichnis mit start.sh wechseln
chmod +x start.sh
./start.sh /ABSOLUTER/PFAD/ZUR/NAS-FREIGABE/ModelVault
```

Dabei wird einmalig `.env` mit einem zufälligen Passwort erzeugt und das Archivverzeichnis angelegt. Danach baut `start.sh` ein Docker-Image und startet den **P0-Download automatisch**. Die Großmodelle liegen unter `.../ModelVault/models/ORG/REPO/`; Statusdateien unter `.../ModelVault/.vault/`.

Öffne von einem Gerät **im vertrauenswürdigen Heimnetz oder per Tailscale**:

```
http://NAS-IP:8787
Benutzer: vault
Passwort: Wert UI_PASSWORD in der Datei .env
```

Die Browseransicht aktualisiert alle drei Sekunden; sie zeigt **übertragene und insgesamt geplante GiB, Gesamtprozent, abgeschlossene/ausgewählte Modelle, verifizierte Dateien, MiB/s, Restzeitschätzung, freien NAS-Speicher, aktive Dateien und Fehler**. Während der Planung ist der Gesamtumfang bewusst als *noch unbekannt* markiert. Die Restzeit ist nur eine momentane Schätzung und kann schwanken.

## Pausieren, fortsetzen, Neustart

Die Oberfläche hat **Pause**, **Fortsetzen** und **Fehler erneut versuchen**. Pause wird als Flag auf dem NAS gespeichert. Download schreibt `.part`-Dateien und kann nach `docker compose restart`, NAS-Neustart oder Netzwerkabbruch fortsetzen. Abgeschlossene Dateien werden vor dem `complete`-Status mit SHA-256 geprüft. Die Hugging-Face-Git-Revision wird beim Planen fixiert und im Archiv hinterlegt.

```bash
docker compose ps
docker compose logs --tail=100 -f
# Gesamtdaten ohne Browser:
cat /ABSOLUTER/PFAD/ZUR/NAS-FREIGABE/ModelVault/.vault/status.json
# gut lesbare Kurzfassung:
./status.sh
# Nach Aenderung an .env oder models.json:
docker compose up -d --build
```

## Was wird zuerst geladen?

`.env`: `SELECT_TIERS=P0` standardmäßig. P0: YuE2 + VAE, ACE-Step 1.5, eine optimierte MiniMax Music3 Variante, zwei Qwen-Image-2.1-Turbo-Komponenten plus abenzerps-GGUF, zusätzlich der **vollständige offizielle Qwen-Image-2.1-Checkpoint** samt Pipeline-Dateien. Groessen ermittelt das Programm **vor dem Download automatisch aus der Hugging-Face-Dateiliste**, statt ungeprüfte geschätzte GB-Werte zu verwenden. Die Qwen-Image-Duplikate sichern absichtlich Original plus abgeleitete Varianten getrennt.

P1 spaeter aktivieren:

```bash
# .env mit beliebigem Editor aendern:
SELECT_TIERS=P0,P1
# anschliessend:
docker compose up -d
```

P1: Whisper v3 Turbo + v3, Qwen3 ASR, Parakeet, Qwen3 TTS, Kokoro, MiniCPM Vision. Krea ist wegen des offiziellen Freigabegates in `models.json` standardmaessig deaktiviert. **Keine Umgehung von Gating.** Fuer autorisierte Downloads kannst du `HF_TOKEN=hf_...` in `.env` setzen; anschliessend Compose neu starten. Das Token gehoert nicht ins Git-Repo.

Zu den Modell-IDs und Auswahlmustern: `models.json`. Falls ein Dateimuster im Repository inzwischen nicht mehr existiert, wird das Modell sichtbar als `blocked` statt faelschlich als vollstaendig behandelt. Ein blockiertes Modell kannst du nach Korrektur mit dem Retry-Knopf erneut planen lassen. Bereits geplante Revisionen und Dateilisten bleiben gepinnt (Aenderungen an bestehenden Listen werden nicht ungefragt auf neue Revisionen umgestellt).

## NAS/Betrieb/Sicherheit

- Docker-NAS-Freigabe muss fuer die lokale User/Group-ID mit Schreibzugriff verfuegbar sein (automatisch `id -u`/`id -g` beim ersten Start). Bei Berechtigungsfehlern keinen globalen `chmod 777` einsetzen; Freigabe/ACL gezielt korrigieren.
- `BIND_IP=0.0.0.0` ist nur fuer Heim-LAN/Tailscale gedacht, **niemals** Port 8787 ins Internet weiterleiten. Dashboard nutzt HTTP Basic; wenn Zugang ueber fremde Netze gewuenscht ist, Tailscale/HTTPS-Proxy oder SSH-Tunnel nutzen. Fuer lokalen Tunnel `BIND_IP=127.0.0.1` setzen.
- NAS-RAID1 ist kein zweites Backup. Die wertvollsten Gewichte spaeter auf ein unabhaengiges Medium kopieren.
- Das Archiv besitzt SHA256-Manifestdateien, aber die Remote-Pruessumme ist nur bei vorhandenem LFS SHA256 verifizierbar. Andernfalls wird zunaechst die lokale Hashsumme aufgezeichnet. Beides wird korrekt gekennzeichnet.
- Die Laufzeit gewaehlt: zwei parallele Dateien (`WORKERS=2`, maximal 4); bei Rate-Limit auf 1 reduzieren.
- Beim Pausieren werden laufende Antworten nach dem naechsten Download-Chunk angehalten. `docker compose down` stoppt den Container, **loescht aber die archivierten Dateien auf der Freigabe nicht**.
- Lizenzbedingungen bleiben bestehen (insbesondere Qwen-Image Research, YuE2 NC, MiniMax Community). Archivierung = Sicherung, nicht Aufhebung der Lizenz.
- Fuer spaetere git-Transfer: Erstelle ein **separates privates** Repo `model-vault` unter GitHub und committe nur die Dateien aus diesem ZIP. `.gitignore` schliesst `.env` aus. Im Git-Repo selbst liegen keinerlei Gewichte.

## Bekannte Grenzen

1. Bei Unterbrechungen funktioniert Resume fuer Hugging Face-Datei-URLs, sofern der Server HTTP Range unterstuetzt. Ignoriert er Range, wird die betreffende Datei vollstaendig neu heruntergeladen (sicher, aber langsam).
2. Groesse, ETA und HTTP-Werte werden aus Metadaten und lokaler Dateiablage berechnet; bei gesperrtem Metadaten-Endpunkt kann der Gesamtumfang noch nicht ermittelt werden. Solche Faelle werden sichtbar als `blocked` markiert.
3. Die urspruengliche Quelle kann spaeter verschwinden. Deshalb werden Revision, Gewichtedateien, README, Konfigurationsdateien und Herkunft in `MODEL_VAULT_MANIFEST.json` archiviert. Fuer langfristige Reproduzierbarkeit solltest du spaeter noch **Softwarelaufzeit/ComfyUI-Workflows und GitHub-Code** spiegeln.
4. Version 1 ist fuer den UGREEN-Dockerbetrieb und das lokale Netz gebaut. Die tatsaechlichen externen Downloads konnten in dieser Chat-Umgebung nicht mit hunderten GiB probeweise ausgefuehrt werden. Ein lokaler Resume-/Dashboard-Test ist enthalten.
