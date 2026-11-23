"""Envoie la notification de la dernière édition sur le téléphone via ntfy (https://ntfy.sh).

Variables d'environnement :
  NTFY_TOPIC   nom du sujet ntfy (secret : quiconque le connaît peut lire tes notifications)
  NTFY_SERVER  serveur ntfy, par défaut https://ntfy.sh
  SITE_URL     adresse du journal, ex. https://pseudo.github.io/la-veille/
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

from render import load_index

DOCS = Path(__file__).parent / "docs"


def main() -> int:
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        print("NTFY_TOPIC absent : pas de notification.")
        return 0
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    site = os.environ.get("SITE_URL", "").strip()

    index = load_index(DOCS)
    if not index:
        print("Aucune édition à annoncer.", file=sys.stderr)
        return 1
    latest = index[0]
    message = latest.get("summary") or " · ".join(latest.get("headlines", [])[:3])

    payload = {
        "topic": topic,
        "title": f"La Veille N° {latest['number']} est prête",
        "message": message[:240],
        "tags": ["newspaper"],
    }
    if site:
        payload["click"] = site

    req = urllib.request.Request(server, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"Notification envoyée ({resp.status}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
