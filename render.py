"""Mise en page d'une édition (JSON) en HTML façon journal papier, et gestion des archives dans docs/."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

TEMPLATE = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")

SECTION_NAMES = {
    "robotique": "Robotique",
    "technologies": "Technologies",
    "geopolitique": "Géopolitique",
    "capital": "Entrepreneuriat &amp; capital",
}
SECTION_ORDER = list(SECTION_NAMES)
RELIABILITY = {
    "primaire": ("p", "Source primaire"),
    "concordantes": ("c", "Sources concordantes"),
    "secondaire": ("s", "Secondaire"),
}


# --------------------------------------------------------------------------- texte

def fmt(text: str) -> str:
    """Échappe le texte puis applique **gras** et *italique*."""
    t = html.escape(text or "", quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    return t


def url(u: str) -> str:
    u = (u or "").strip()
    return html.escape(u, quote=True) if u.startswith(("http://", "https://")) else ""


def sources_html(sources, reliability: str = "", note: str = "") -> str:
    parts = []
    if reliability in RELIABILITY:
        cls, label = RELIABILITY[reliability]
        parts.append(f'<span class="tag {cls}">{label}</span>')
    links = []
    for s in sources or []:
        href = url(s.get("url", ""))
        name = fmt(s.get("name") or "source")
        links.append(f'<a href="{href}" rel="noopener">{name}</a>' if href else name)
    parts.append(" · ".join(links))
    if note:
        parts.append(". " + fmt(note) if links else fmt(note))
    return f'<p class="src">{"".join(parts)}</p>'


def box_html(box) -> str:
    if not box or not (box.get("title") or box.get("paragraphs")):
        return ""
    out = ['<div class="box">']
    if box.get("title"):
        out.append(f"<h4>{fmt(box['title'])}</h4>")
    paras = box.get("paragraphs") or []
    formula = (box.get("formula") or "").strip()
    if paras:
        out.append(f"<p>{fmt(paras[0])}</p>")
    if formula:
        out.append(f'<div class="eq">{html.escape(formula)}</div>')
    out.extend(f"<p>{fmt(p)}</p>" for p in paras[1:])
    out.append("</div>")
    return "".join(out)


# --------------------------------------------------------------------------- articles

def story_html(story, cls: str, heading: str = "h3") -> str:
    multi = any(c in cls.split() for c in ("wide", "half", "span3", "lead"))
    body = "".join(f"<p>{fmt(p)}</p>" for p in story.get("paragraphs") or []) + box_html(story.get("box"))
    out = [f'<article class="story {cls}">']
    if story.get("kicker"):
        out.append(f'<p class="kicker">{fmt(story["kicker"])}</p>')
    out.append(f"<{heading}>{fmt(story.get('headline', ''))}</{heading}>")
    if story.get("dek"):
        out.append(f'<p class="dek">{fmt(story["dek"])}</p>')
    out.append(f'<div class="cols">{body}</div>' if multi else body)
    if story.get("watch"):
        out.append(f'<p class="watch"><b>À surveiller.</b> {fmt(story["watch"])}</p>')
    out.append(sources_html(story.get("sources"), story.get("reliability", ""), story.get("reliability_note", "")))
    out.append("</article>")
    return "".join(out)


def briefs_html(section, cls: str) -> str:
    items = "".join(f"<li><b>{fmt(b['title'])}.</b> {fmt(b['text'])}</li>" for b in section.get("briefs") or [])
    return (f'<article class="story {cls}"><p class="kicker">Brèves</p><h3>En bref</h3>'
            f'<ul class="breves">{items}</ul>{sources_html(section.get("brief_sources"))}</article>')


def section_html(section) -> str:
    sid = section["id"]
    wides = [s for s in section.get("stories", []) if s.get("size") == "wide"]
    others = [("story", s) for s in section.get("stories", []) if s.get("size") != "wide"]
    if section.get("briefs"):
        others.append(("briefs", section))

    # Répartition en rangées complètes de 3 colonnes.
    n = len(others)
    classes = []
    for i in range(n):
        classes.append("row-start" if i % 3 == 0 else "")
    if n % 3 == 2:
        classes[-2] = "half row-start"
    elif n % 3 == 1:
        classes[-1] = "span3 row-start"

    parts = [story_html(s, "wide row-start") for s in wides]
    for (kind, item), cls in zip(others, classes):
        parts.append(story_html(item, cls) if kind == "story" else briefs_html(item, cls))

    return (f'<section class="rubrique" id="{sid}"><div class="rh"><h2>{SECTION_NAMES[sid]}</h2>'
            f'<span>{fmt(section.get("subtitle", ""))}</span></div><div class="grid">{"".join(parts)}</div></section>')


# --------------------------------------------------------------------------- page

def page(title: str, prefix: str, body: str) -> str:
    return TEMPLATE.replace("{{TITLE}}", html.escape(title)).replace("{{PREFIX}}", prefix).replace("{{BODY}}", body)


def masthead(edition, prefix: str, prev_link: str = "") -> str:
    nav_extra = f' · <a href="{prev_link}">Édition précédente</a>' if prev_link else ""
    return (
        f'<header class="mast"><div class="ear">N° {edition["number"]}<br>Édition du matin</div>'
        f'<h1><a href="{prefix}index.html">La Veille</a></h1>'
        f'<div class="ear r">Robotique · Technologies<br>Géopolitique · Capital</div></header>'
        f'<div class="dateline"><span>{fmt(edition["date_label"])}</span>'
        f'<span class="motto">Ce qui s\'est passé hier, et pourquoi ça compte.</span>'
        f'<span>Couverture : {fmt(edition.get("coverage", ""))} · <a href="{prefix}archives.html">Archives</a>{nav_extra}</span></div>'
    )


def edition_body(edition, prefix: str, prev_link: str = "") -> str:
    ticks = "".join(
        f'<div class="tick"><div class="l">{fmt(t["label"])}</div>'
        f'<div class="v {"up" if t.get("trend") == "up" else "dn" if t.get("trend") == "down" else ""}">{fmt(t["value"])}</div>'
        f'<div class="n">{fmt(t.get("note", ""))}</div></div>'
        for t in edition.get("ticker", [])[:5]
    )
    sections = sorted(edition.get("sections", []), key=lambda s: SECTION_ORDER.index(s["id"]))
    nav = '<a href="#une">À la une</a>' + "".join(
        f'<a href="#{s["id"]}">{SECTION_NAMES[s["id"]]}</a>' for s in sections)

    side = edition.get("side", {})
    agenda = "".join(f"<li><b>{fmt(a['when'])}</b><span>{fmt(a['what'])}</span></li>" for a in side.get("agenda", []))
    takeaways = "".join(f"<li>{fmt(t)}</li>" for t in side.get("takeaways", []))
    side_html = (
        f'<aside class="side"><div><h4>Le chiffre</h4><div class="big">{fmt(side.get("figure_value", ""))}</div>'
        f'<p style="margin:.4rem 0 0">{fmt(side.get("figure_text", ""))}</p></div>'
        f'<div><h4>Agenda</h4><ul class="agenda">{agenda}</ul></div>'
        f'<div class="box"><h4>Pour l\'entrepreneur</h4><ol class="takeaways">{takeaways}</ol></div></aside>'
    )

    lead = story_html(edition["lead"], "lead", heading="h2")
    colophon = (
        '<footer class="colophon"><div><h4>Méthode</h4><p>Édition compilée chaque matin par recherche web sur les 24 à 48 heures '
        'précédentes, puis rédigée par Claude. Les encadrés « Sous le capot » et « Analyse » apportent un contexte technique qui '
        'n\'est pas tiré des articles sources.</p></div>'
        '<div><h4>Fiabilité</h4><p><span class="tag p">Source primaire</span>dépôt réglementaire ou communiqué officiel. '
        '<span class="tag c">Sources concordantes</span>plusieurs médias indépendants. '
        '<span class="tag s">Secondaire</span>agrégateurs, chiffres divergents ou sans source primaire.</p></div>'
        f'<div><h4>Édition</h4><p>N° {edition["number"]} · {fmt(edition["date_label"]).lower()}. '
        f'<a href="{prefix}archives.html">Toutes les éditions</a>.</p></div></footer>'
    )
    return (masthead(edition, prefix, prev_link)
            + f'<div class="ticker" aria-label="Chiffres du jour">{ticks}</div>'
            + f'<nav class="rub" aria-label="Rubriques">{nav}</nav>'
            + f'<section class="une" id="une">{lead}{side_html}</section>'
            + "".join(section_html(s) for s in sections)
            + colophon)


def archives_body(index) -> str:
    items = "".join(
        f'<li><span class="num">N° {e["number"]}<br>{e["date"]}</span><div>'
        f'<a href="editions/{e["date"]}.html">{fmt(e["date_label"])}</a>'
        f'<p>{" · ".join(fmt(h) for h in e.get("headlines", [])[:5])}</p></div></li>'
        for e in index
    )
    return (
        '<header class="mast"><div class="ear">Archives</div><h1><a href="index.html">La Veille</a></h1>'
        '<div class="ear r">Toutes les éditions</div></header>'
        f'<div class="dateline"><span>{len(index)} édition(s)</span><span><a href="index.html">Dernière édition</a></span></div>'
        f'<ul class="archive">{items}</ul>'
    )


# --------------------------------------------------------------------------- écriture

def load_index(docs: Path) -> list[dict]:
    p = docs / "editions" / "index.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def headlines(edition) -> list[str]:
    hs = [edition["lead"]["headline"]]
    for s in edition.get("sections", []):
        hs += [st["headline"] for st in s.get("stories", [])]
    return hs


def publish_edition(docs: Path, edition: dict) -> Path:
    eds = docs / "editions"
    eds.mkdir(parents=True, exist_ok=True)
    date = edition["date"]

    index = [e for e in load_index(docs) if e["date"] != date]
    index.insert(0, {"date": date, "number": edition["number"], "date_label": edition["date_label"],
                     "headlines": headlines(edition), "summary": edition.get("notification_summary", "")})
    index.sort(key=lambda e: e["date"], reverse=True)
    pos = next(i for i, e in enumerate(index) if e["date"] == date)
    prev = index[pos + 1]["date"] if pos + 1 < len(index) else None

    title = f"La Veille · N° {edition['number']}"
    (eds / f"{date}.json").write_text(json.dumps(edition, ensure_ascii=False, indent=1), encoding="utf-8")
    (eds / f"{date}.html").write_text(
        page(title, "../", edition_body(edition, "../", f"{prev}.html" if prev else "")), encoding="utf-8")
    if pos == 0:  # la page d'accueil montre toujours la plus récente
        (docs / "index.html").write_text(
            page("La Veille", "", edition_body(edition, "", f"editions/{prev}.html" if prev else "")), encoding="utf-8")
    (eds / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    (docs / "archives.html").write_text(page("La Veille · Archives", "", archives_body(index)), encoding="utf-8")
    return eds / f"{date}.html"
