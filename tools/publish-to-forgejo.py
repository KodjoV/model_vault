#!/usr/bin/env python3
"""One-time, conservative publication of Model Vault docs into private Forgejo homelab-architecture.

Default = preview only. --apply prompts for a token without echoing or storing it.
Uses Forgejo over NAS loopback HTTP (no LAN plaintext token transfer).
Does not overwrite existing different files unless --update is explicitly supplied.
No Python third-party dependencies, Git CLI, or NAS access needed from ChatGPT.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:3002"
DEFAULT_REPO = "forgejo_admin/homelab-architecture"
SOURCE = "https://raw.githubusercontent.com/KodjoV/model_vault/main/integrations/homelab-architecture"
FILES = (
    ("inventory/model-vault.md", "inventory/model-vault.md"),
    ("runbooks/model-vault.md", "runbooks/model-vault.md"),
)
MARKER = "<!-- Managed bootstrap entry: Model Vault."

def get_bytes(url, token=None):
    headers = {"User-Agent": "ModelVault-Forgejo-Publisher/1.0"}
    if token:
        headers["Authorization"] = "token " + token
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return response.read()

def api_request(api, method, relative, token, payload=None, allow_404=False):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json", "User-Agent": "ModelVault-Forgejo-Publisher/1.0",
               "Authorization": "token " + token}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(api + relative, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except HTTPError as exc:
        if exc.code == 404 and allow_404:
            return None, 404
        if exc.code in (401, 403):
            raise RuntimeError("Forgejo-API verweigert Zugriff (Token oder Berechtigung prüfen)") from exc
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError("Forgejo HTTP " + str(exc.code) + ": " + body) from exc

def repo_path(owner, name):
    return "/repos/" + quote(owner, safe="") + "/" + quote(name, safe="")

def main():
    parser = argparse.ArgumentParser(description="Model Vault: Dokumentation nach Forgejo übertragen")
    parser.add_argument("--apply", action="store_true", help="Daten in Forgejo schreiben; Token wird lokal abgefragt")
    parser.add_argument("--update", action="store_true", help="Eigene existierende Dokumentationsdateien aktualisieren")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Forgejo Zielowner/repo")
    args = parser.parse_args()
    if args.update and not args.apply:
        parser.error("--update benötigt --apply")
    if args.repo.count("/") != 1 or any(not part.strip() for part in args.repo.split("/")):
        parser.error("--repo muss owner/name lauten")
    owner, name = args.repo.split("/")
    print("Quelle: " + SOURCE)
    print("Ziel: Forgejo " + args.repo + " (NAS loopback port 3002)")
    docs = []
    for source_path, dest_path in FILES:
        url = SOURCE + "/" + source_path
        content = get_bytes(url)
        text = content.decode("utf-8")
        if not text.startswith(MARKER):
            raise RuntimeError("Unerwarteter Quellinhalt: " + url)
        docs.append((dest_path, content))
        print(" - " + dest_path + " (" + str(len(content)) + " Bytes)")
    if not args.apply:
        print("\nNUR VORSCHAU. Für das einmalige Einspielen --apply verwenden.")
        return 0

    token = getpass.getpass("Forgejo-API-Token (nur lokal, Eingabe unsichtbar): ").strip()
    if not token:
        raise RuntimeError("Leerer Token")
    api = BASE_URL + "/api/v1"
    base = repo_path(owner, name)
    info, _ = api_request(api, "GET", base, token)
    if info.get("full_name") and info["full_name"].casefold() != args.repo.casefold():
        raise RuntimeError("Unerwartetes Repository, Abbruch: " + info["full_name"])
    branch = info.get("default_branch")
    if not branch:
        raise RuntimeError("Forgejo meldet keinen Default-Branch")
    print("Repo gefunden, Zielbranch:", branch)

    # Check all remote paths before the first write.
    actions = []
    for path, content in docs:
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        remote, status = api_request(api, "GET", base + "/contents/" + encoded + "?ref=" + quote(branch, safe=""), token, allow_404=True)
        if status == 404:
            actions.append(("create", path, encoded, content, None))
        else:
            if not isinstance(remote, dict) or remote.get("type") != "file":
                raise RuntimeError("Zielpfad existiert, ist aber keine Datei: " + path)
            orig = base64.b64decode(remote.get("content") or "")
            if orig == content:
                actions.append(("same", path, encoded, content, None))
                continue
            if not orig.decode("utf-8", errors="replace").startswith(MARKER):
                raise RuntimeError("Fremde Datei an Zielpfad: " + path + "; keine Überschreibung")
            if not args.update:
                raise RuntimeError("Ziel enthält ältere Dokumentation (" + path + "). Für Aktualisierung erneut mit --apply --update ausführen.")
            actions.append(("update", path, encoded, content, remote.get("sha")))
    for action, path, encoded, content, sha in actions:
        if action == "same":
            print("Unverändert:", path)
            continue
        payload = {"content": base64.b64encode(content).decode("ascii"),
                   "message": "docs(homelab): update Model Vault archive inventory and runbook",
                   "branch": branch}
        if sha:
            payload["sha"] = sha
        method = "POST" if action == "create" else "PUT"
        _, status = api_request(api, method, base + "/contents/" + encoded, token, payload)
        print("Forgejo:", action, path, "HTTP", status)
    print("\nDokumentation übertragen. Quellcode und Modellgewichte wurden nicht verändert.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, HTTPError, URLError, ValueError, OSError) as exc:
        print("FEHLER:", str(exc), file=sys.stderr)
        sys.exit(1)
