"""La Veille — génère l'édition du matin.

Étapes :
  1. Recherche : Claude fouille le web (outil web_search côté serveur) et rédige un dossier de recherche.
  2. Rédaction : Claude transforme le dossier en édition structurée (JSON validé par schéma).
  3. Rendu : l'édition est mise en page (render.py) et écrite dans docs/ pour GitHub Pages.

Usage :
  python generate.py                      # édition du jour (nécessite ANTHROPIC_API_KEY)
  python generate.py --fixture f.json     # rendu seul, à partir d'une édition déjà rédigée (aucun appel API)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from render import publish_edition, load_index

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"

MODEL = os.environ.get("VEILLE_MODEL", "claude-opus-5-5")
EFFORT_RESEARCH = os.environ.get("VEILLE_EFFORT_RESEARCH", "high")
EFFORT_WRITING = os.environ.get("VEILLE_EFFORT_WRITING", "high")
MAX_SEARCHES = int(os.environ.get("VEILLE_MAX_SEARCHES", "40"))
TZ = ZoneInfo(os.environ.get("VEILLE_TZ", "Europe/Paris"))

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def date_fr(d: datetime) -> str:
    return f"{JOURS[d.weekday()].capitalize()} {d.day} {MOIS[d.month - 1]} {d.year}"


# --------------------------------------------------------------------------- prompts

READER = """Le lecteur est francophone, exigeant, de formation technique. Il veut de la technique, pas de la vulgarisation :
architectures, chiffres exacts, ordres de grandeur, seuils réglementaires, structures de deals, mécanismes de cause à effet.
Ses centres d'intérêt, qui forment les quatre rubriques du journal :
- Robotique (modèles VLA et fondation, manipulation, humanoïdes, perception, actionneurs, déploiements industriels, levées du secteur)
- Technologies (IA, semi-conducteurs, packaging, photonique, mémoire, calcul, énergie, quantique, spatial)
- Géopolitique (conflits, énergie, contrôle des exportations et des investissements, diplomatie, alliances)
- Entrepreneuriat & capital (levées notables, structures de tours, IPO, M&A, marchés, taux, agenda macro)"""

RESEARCH_SYSTEM = f"""Tu es le chef de la recherche d'un quotidien personnel, « La Veille ».
{READER}

Ta tâche : produire un dossier de recherche sur l'actualité des dernières 24 à 48 heures, qui servira à rédiger l'édition du matin.

Méthode :
- Commence par des recherches larges par rubrique pour repérer les sujets importants des deux derniers jours.
- Retiens 3 à 4 sujets par rubrique, plus quelques brèves. Privilégie ce qui a une portée technique, industrielle ou stratégique réelle.
- Pour chaque sujet retenu, fais au moins une recherche de second niveau pour obtenir le détail technique et, si possible, la source primaire
  (communiqué, dépôt réglementaire type 8-K, papier arXiv, texte officiel, déclaration publique).
- Relève aussi : les chiffres de marché du dernier jour de cotation (indices, taux, pétrole, etc.) et l'agenda des jours à venir.
- Ne reprends pas un sujet déjà couvert dans les éditions précédentes (liste fournie), sauf fait nouveau ; dans ce cas précise ce qui a changé.

Format du dossier (texte, pas de JSON) : une section par rubrique ; pour chaque sujet : les faits datés, les chiffres, le détail technique,
les points de désaccord entre sources, et la liste des URL consultées avec le nom du média. Signale clairement ce qui n'est pas confirmé.
N'invente rien : si une information manque, écris qu'elle manque."""

WRITING_SYSTEM = f"""Tu es le rédacteur en chef de « La Veille », un quotidien personnel au format journal papier.
{READER}

À partir du dossier de recherche fourni, rédige l'édition complète en français, au format JSON imposé.

Règles éditoriales :
- Style : phrases directes, vocabulaire technique exact, pas de remplissage ni de formules creuses. Pas de vulgarisation.
- « À la une » (lead) : le sujet le plus important du jour, traité en profondeur (5 à 7 paragraphes), avec un encadré technique
  (box) qui explique un mécanisme, et éventuellement une formule ou un calcul (formula, sinon chaîne vide), plus un « À surveiller » (watch).
- Chaque rubrique (robotique, technologies, geopolitique, capital, dans cet ordre) contient : un article long (size "wide",
  4 à 6 paragraphes, avec encadré), puis 2 à 3 articles courts (size "normal", 2 à 3 paragraphes, encadré facultatif),
  et 2 à 4 brèves. Chaque brève tient en une ou deux phrases et dit pourquoi le fait compte.
- Encadrés : titre du type « Sous le capot : … » quand tu expliques un mécanisme, « Analyse : … » pour une lecture personnelle.
  Le contexte technique que tu ajoutes de tes propres connaissances va dans les encadrés, jamais présenté comme un fait sourcé.
- Pour un champ facultatif sans contenu, mets une chaîne vide ("") ou une liste vide.
- Rigueur : n'invente aucun fait, chiffre, nom ni citation absent du dossier. Signale explicitement les chiffres divergents
  et les informations non confirmées (dans le texte et dans reliability_note).
- reliability : "primaire" si au moins une source primaire, "concordantes" si plusieurs médias indépendants concordent,
  "secondaire" sinon. Les sources (name, url) sont reprises du dossier, uniquement des URL réelles qui y figurent.
- ticker : exactement 5 chiffres clés du jour (value courte, ex. "−11,6 %", "92,57 $"), avec trend up/down/flat et une note courte.
- side : « Le chiffre » (figure_value très court + figure_text d'une ou deux phrases), un agenda de 3 à 5 échéances, et 3 enseignements
  concrets pour un entrepreneur (takeaways).
- Mise en forme autorisée dans les textes : **gras** et *italique*, rien d'autre (pas de HTML, pas de liens dans le texte).
- notification_summary : une ligne de moins de 140 caractères qui cite les 2 ou 3 sujets principaux, très court."""

# --------------------------------------------------------------------------- schéma de sortie

_SOURCE = {"type": "object", "properties": {"name": {"type": "string"}, "url": {"type": "string"}},
           "required": ["name", "url"], "additionalProperties": False}
_BOX = {"type": "object",
        "properties": {"title": {"type": "string"}, "paragraphs": {"type": "array", "items": {"type": "string"}},
                       "formula": {"type": "string"}},
        "required": ["title", "paragraphs", "formula"], "additionalProperties": False}
_STORY = {"type": "object",
          "properties": {
              "kicker": {"type": "string"}, "headline": {"type": "string"}, "dek": {"type": "string"},
              "size": {"type": "string", "enum": ["wide", "normal"]},
              "paragraphs": {"type": "array", "items": {"type": "string"}},
              "box": _BOX, "watch": {"type": "string"},
              "reliability": {"type": "string", "enum": ["primaire", "concordantes", "secondaire"]},
              "reliability_note": {"type": "string"},
              "sources": {"type": "array", "items": _SOURCE}},
          "required": ["kicker", "headline", "dek", "size", "paragraphs", "box", "watch", "reliability",
                       "reliability_note", "sources"],
          "additionalProperties": False}
EDITION_SCHEMA = {
    "type": "object",
    "properties": {
        "coverage": {"type": "string", "description": "Période couverte, ex. « 22 – 23 nov. »"},
        "ticker": {"type": "array", "items": {
            "type": "object",
            "properties": {"label": {"type": "string"}, "value": {"type": "string"},
                           "trend": {"type": "string", "enum": ["up", "down", "flat"]}, "note": {"type": "string"}},
            "required": ["label", "value", "trend", "note"], "additionalProperties": False}},
        "lead": _STORY,
        "side": {"type": "object", "properties": {
            "figure_value": {"type": "string"}, "figure_text": {"type": "string"},
            "agenda": {"type": "array", "items": {
                "type": "object", "properties": {"when": {"type": "string"}, "what": {"type": "string"}},
                "required": ["when", "what"], "additionalProperties": False}},
            "takeaways": {"type": "array", "items": {"type": "string"}}},
            "required": ["figure_value", "figure_text", "agenda", "takeaways"], "additionalProperties": False},
        "sections": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "enum": ["robotique", "technologies", "geopolitique", "capital"]},
                "subtitle": {"type": "string"},
                "stories": {"type": "array", "items": _STORY},
                "briefs": {"type": "array", "items": {
                    "type": "object", "properties": {"title": {"type": "string"}, "text": {"type": "string"}},
                    "required": ["title", "text"], "additionalProperties": False}},
                "brief_sources": {"type": "array", "items": _SOURCE}},
            "required": ["id", "subtitle", "stories", "briefs", "brief_sources"], "additionalProperties": False}},
        "notification_summary": {"type": "string"},
    },
    "required": ["coverage", "ticker", "lead", "side", "sections", "notification_summary"],
    "additionalProperties": False,
}

# --------------------------------------------------------------------------- appels API


def _client():
    import anthropic
    return anthropic.Anthropic(max_retries=4, timeout=1800)


def _stream(client, **kwargs):
    """Requête en streaming, avec repli serveur en cas de refus de sécurité."""
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        thinking={"type": "adaptive"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        **kwargs,
    ) as stream:
        return stream.get_final_message()


def _text(message) -> str:
    return "".join(b.text for b in message.content if getattr(b, "type", None) == "text")


def _usage_line(label, message):
    u = message.usage
    print(f"  [{label}] tokens entrée={u.input_tokens} sortie={u.output_tokens} stop={message.stop_reason}", flush=True)


def research(client, today: datetime, previous_headlines: list[str]) -> str:
    prev = "\n".join(f"- {h}" for h in previous_headlines) or "(aucune)"
    user = (f"Nous sommes le {date_fr(today)} ({today:%Y-%m-%d}), heure de Paris. "
            f"Couvre l'actualité de la veille et de l'avant-veille.\n\n"
            f"Sujets déjà traités dans les dernières éditions :\n{prev}\n\n"
            f"Produis le dossier de recherche.")
    messages = [{"role": "user", "content": user}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_SEARCHES}]

    for attempt in range(8):  # reprises après pause_turn
        msg = _stream(client, system=RESEARCH_SYSTEM, messages=messages, tools=tools,
                      output_config={"effort": EFFORT_RESEARCH})
        _usage_line(f"recherche {attempt + 1}", msg)
        if msg.stop_reason == "refusal":
            raise RuntimeError(f"Recherche refusée : {msg.stop_details}")
        if msg.stop_reason == "pause_turn":
            messages = [{"role": "user", "content": user}, {"role": "assistant", "content": msg.content}]
            continue
        dossier = _text(msg).strip()
        if not dossier:
            raise RuntimeError("Le dossier de recherche est vide.")
        return dossier
    raise RuntimeError("La recherche n'a pas abouti après 8 reprises.")


def write_edition(client, dossier: str, today: datetime, number: int) -> dict:
    user = (f"Édition N° {number}, {date_fr(today)}.\n\n<dossier>\n{dossier}\n</dossier>\n\n"
            f"Rédige l'édition complète au format demandé.")
    msg = _stream(client, system=WRITING_SYSTEM, messages=[{"role": "user", "content": user}],
                  output_config={"effort": EFFORT_WRITING,
                                 "format": {"type": "json_schema", "schema": EDITION_SCHEMA}})
    _usage_line("rédaction", msg)
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"Rédaction refusée : {msg.stop_details}")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("Rédaction tronquée (max_tokens atteint).")
    return json.loads(_text(msg))


# --------------------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="Édition JSON déjà rédigée : rendu seul, sans appel API")
    ap.add_argument("--date", help="Date de l'édition (AAAA-MM-JJ), par défaut aujourd'hui")
    args = ap.parse_args()

    today = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=TZ) if args.date else datetime.now(TZ)
    index = load_index(DOCS)
    if any(e["date"] == f"{today:%Y-%m-%d}" for e in index):
        number = next(e["number"] for e in index if e["date"] == f"{today:%Y-%m-%d}")  # régénération du jour
    else:
        number = max((e["number"] for e in index), default=0) + 1

    if args.fixture:
        edition = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY manquante.", file=sys.stderr)
            return 1
        client = _client()
        previous = [h for e in index[:5] for h in e.get("headlines", [])]
        print(f"Recherche ({MODEL}, effort {EFFORT_RESEARCH}, {MAX_SEARCHES} recherches max)…", flush=True)
        dossier = research(client, today, previous)
        (ROOT / "last-dossier.md").write_text(dossier, encoding="utf-8")
        print(f"Rédaction de l'édition N° {number}…", flush=True)
        edition = write_edition(client, dossier, today, number)

    edition["number"] = number
    edition["date"] = f"{today:%Y-%m-%d}"
    edition["date_label"] = date_fr(today)
    path = publish_edition(DOCS, edition)
    print(f"Édition N° {number} écrite : {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
