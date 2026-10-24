# Automatische Folge-Downloads: DS41 → OPEN3

Dieser Helfer startet **keinen Download sofort**, wenn der aktuelle Model Vault
noch arbeitet. Er wartet bis die **aktuell gewählte Gruppe** vollständig fertig
ist (`phase=complete`, `verified_complete=true` und aktueller Status).

Danach startet er den bereits vorhandenen Docker-Downloader **einmal** neu mit
`SELECT_TIERS=DS41,OPEN3`. Die Reihenfolge im bestehenden `models.json` ist
DS41 zuerst und OPEN3 danach. Schon vollständig archivierte Modelle werden
auf Basis des vorhandenen, SHA-geprüften Downloadplans übersprungen.

Der Helfer fügt nur die bereits im Github-PR enthaltenen fünf Repo-Einträge
(2× DS41, 3× OPEN3) hinzu. Er nimmt **nicht** das gated ORCA-Tier auf.

## Ein Befehl auf dem NAS

```sh
cd /volume1/docker/model_vault && \
curl -fLsS --retry 3 \
  https://raw.githubusercontent.com/KodjoV/model_vault/7213e1e9343c51a79e140faad83ba5b97806ea8d/tools/queue-next-vault.py \
  -o tools/queue-next-vault.py && \
sudo python3 tools/queue-next-vault.py install
```

`7213e1e9343c51a79e140faad83ba5b97806ea8d` durch den geprüften vollen Commit aus dem GitHub-PR ersetzen.
Der Befehl lädt nur einen kleinen Helfer herunter und startet einen vom
SSH-Fenster getrennten Prozess auf dem NAS. Er ändert zu diesem Zeitpunkt weder
`.env`, den laufenden Container noch llama-swap oder Strata.

## Status prüfen

```sh
cat /volume1/ModelVault/.vault/model-queue-status.json
tail -n 25 /volume1/ModelVault/.vault/model-queue.log
```

- `waiting`: aktueller Download läuft noch bzw. wird geprüft.
- `switching`: letzte Prüfung und Übergabe an den Vault.
- `started`: der Container wurde mit `DS41,OPEN3` gestartet.
- `blocked`: kein Wechsel vorgenommen oder Rollback versucht; Log lesen.

Der Helfer prüft die noch fehlende Datenmenge grob mit Modellgrößen und vorhandenen
Dateien, verlangt zusätzlich eine Speicherreserve und sichert die lokale
`.env`, `models.json` und den vorhandenen Archivprüfer, bevor er Änderungen
vornimmt. Das aktuelle Vault-Archiv in `/volume1/ModelVault/models/` bleibt
unverändert. Das Skript führt nur einen Übergang aus; den Fortschritt danach
zeigt wie gewohnt das bestehende Dashboard unter Port 8790.

**Grenzen:** Der Warteschlangen-Prozess läuft unabhängig vom SSH-Fenster,
übersteht aber keinen NAS-Neustart. Danach den obigen Installationsbefehl
erneut ausführen. Bei pausiertem oder fehlerhaftem aktuellen Download wartet
er weiter bzw. stoppt sicher; er überspringt keine Fehler. Der Vault selbst
kann abgebrochene Daten-Downloads fortsetzen.

Nach Abschluss des neuen Batches per Read-only-Hashprüfung:

```sh
cd /volume1/docker/model_vault
python3 tools/verify-abliterated.py --tier DS41 --root /volume1/ModelVault
python3 tools/verify-abliterated.py --tier OPEN3 --root /volume1/ModelVault
```

Voraussetzung ist der bisherige NAS-Code mit Docker Compose und eine
`/volume1`-Archivfreigabe auf btrfs; Git auf dem NAS wird nicht benötigt.
