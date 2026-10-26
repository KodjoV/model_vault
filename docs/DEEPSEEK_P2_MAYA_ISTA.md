# DeepSeek V4.1 Flash – P2 für den NAS Model Vault (26.10.2026)

Diese Änderung ist **nur vorbereitet** auf dem Branch \`models/deepseek-v41-p2-20261026\`. Keine NAS-Daten wurden geändert oder heruntergeladen. Bestehende P0/P1-Modelle, \`.env\`, \`/volume1/ModelVault/.vault/plan.json\` und Download-Queues nicht überschreiben.

## Aufnahme ins bestehende Archiv

Zwei unabhängige Repo-Einträge in \`models.json\`:

| SELECT_TIERS | Quelle | Inhalt | Grober Download |
|---|---|---|---|
| \`P2-MAYA\` | \`peasantsmith/DeepSeek-V4.1-Flash-1017-Maya-GGUF\` | Maya-XS 5 GGUF-Shards + Maya-S 6 GGUF-Shards + beide DSpark-Pakete | ca. 629 GB |
| \`P2-ISTA\` | \`ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF\` | IQ2_XXS 4 Backbone-Shards + Engram IQ4_NL | ca. 267 GB |

**Wichtig:** Maya-XS und Maya-S teilen ein Hugging-Face-Repository; Vault v1 erlaubt aus Absicherungsgründen nur **einen Archiveintrag pro Repo**. Das ist gut für einen konsistenten, gepinnten Snapshot, aber zunächst kein eigenständiger XS-only-Download. Für XS-only müsste Vaults Planner echte Teilarchiv-Erweiterungen oder eine separate, unveränderliche Download-Manifestdatei unterstützen. Nicht mit demselben Repo unter einem zweiten Tier in \`models.json\` duplizieren.

Quellen:
- Publisher: https://huggingface.co/peasantsmith/DeepSeek-V4.1-Flash-1017-Maya-GGUF
- Maya v1.1.28 Manifest mit SHA256: https://github.com/mw00/project-maya/blob/v1.1.28/tools/ds4/download_gguf.json
- ISTA: https://huggingface.co/ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF

Die Hugging-Face-Repo-Revision wird beim Vault-Plan gepinnt. Die Downloads werden gegen HF LFS SHA256 verifiziert, soweit vorhanden, und die Prüfsummen im Vault hinterlegt. Bei Maya liegen die Engram-Tabellen bereits in den letzten GGUF-Shards; keine separaten Engram-Doppel-Downloads erforderlich.

## Sichere Betriebsfolge

1. Auf NAS bei \`/volume1/docker/model_vault\` Status der **laufenden** Vault-Downloader/Queues prüfen. Nur wenn keine Vault-Arbeit aktiv ist, den Branch und die beiden Modelle in der lokalen \`models.json\` zusammenführen. **Bestehende \`.env\`, \`.vault/plan.json\` und \`models.json\` sichern.** Kein blindes \`git checkout\`/Tarball-Entpacken über die lokale Installation.
2. \`SELECT_TIERS=P2-MAYA\` (später \`P2-ISTA\`) **explizit** für einen isolierten Downloadlauf setzen. Vault-Image aktualisieren, weil Compose \`models.json\` ins Image kopiert. Nicht während aktiver anderer Downloads; bestehender Plan wird nur bei neuer Repository-ID erweitert.
3. Auf Abschluss und \`MODEL_VAULT_MANIFEST.json\` unter \`/volume1/ModelVault/models/ORG/REPO\` prüfen. \`status.sh\` zeigt Status; nach Verifikation kann der Container wieder gestoppt werden.
4. **Erst danach** auf B52 einen Teil/alle Shards per \`rsync\` über einen bestätigten SSH/NFS-Pfad kopieren (kein NAS-Pfad für B52 wird hier behauptet); SHA256 lokal erneut prüfen; aus lokalen Shards einen eigenen Maya-Pack für XS bzw. S bauen. Daraus getrennte \`maya-xs.json\` und \`maya-s.json\` erstellen.
5. Paths in \`/srv/strata-data/deepseek-v41/nightbench-v3/models.json\` unter \`xs\` und \`s\` registrieren. Dann \`--check-only --models ista,xs,s\`; den Modellvergleich mit gleicher Prompt-Suite je Quantisierung ausführen.

## Wichtig für die Benchmarks

Das bisherige B52-Hilfsskript \`b52-prepare-quant.sh xs|s\` lädt direkt auf B52. **Nicht verwenden, wenn NAS-first gewünscht ist.** Es ist keine Synchronisierung des Vaults. Das neue Vault-P2-Manifest wird unabhängig von \`Nightbench v3\` vorbereitet.

## Nur lesende NAS-Prüfung

\`\`\`bash
cd /volume1/docker/model_vault
./status.sh
sudo docker ps -a --filter name=model-vault
grep '^SELECT_TIERS=' .env
df -h /volume1/ModelVault
\`\`\`

Keine Anpassungen an laufenden Downloads und keine Veränderung an Nightbench v3 auf B52.
