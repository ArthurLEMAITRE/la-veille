# La Veille

Quotidien personnel du matin : robotique, technologies, géopolitique, entrepreneuriat & capital.
Chaque jour, GitHub Actions lance `generate.py`, qui :

1. fait une recherche web approfondie sur les dernières 24 à 48 heures (Claude + outil `web_search`) ;
2. rédige l'édition en JSON structuré (texte technique, sources, niveau de fiabilité) ;
3. la met en page façon journal papier dans `docs/`, publiée par GitHub Pages ;
4. envoie une notification sur ton téléphone via [ntfy](https://ntfy.sh).

Le site est une app web installable : sur le téléphone, « Ajouter à l'écran d'accueil » lui donne une icône et un affichage plein écran.

## Mise en place (une fois, environ 20 minutes)

### 1. Créer le dépôt GitHub
1. Crée un compte sur https://github.com si tu n'en as pas.
2. Crée un nouveau dépôt nommé `la-veille`, **public** (GitHub Pages est gratuit pour les dépôts publics), sans README.
3. Dans ce dossier, envoie les fichiers (remplace `PSEUDO` par ton identifiant GitHub) :
   ```
   git init -b main
   git add .
   git commit -m "La Veille"
   git remote add origin https://github.com/PSEUDO/la-veille.git
   git push -u origin main
   ```

### 2. Clé API Anthropic
1. Va sur https://console.anthropic.com, crée une clé dans **API Keys** et ajoute du crédit dans **Billing**.
2. Fixe une limite de dépense mensuelle (Billing → Limits) : c'est ta garantie contre une mauvaise surprise.
3. Sur GitHub : dépôt → **Settings → Secrets and variables → Actions → New repository secret**
   - Nom : `ANTHROPIC_API_KEY`, valeur : ta clé.

### 3. Notifications sur le téléphone (ntfy)
1. Installe l'app **ntfy** (Play Store ou App Store).
2. Dans l'app, « S'abonner à un sujet » avec un nom long et imprévisible (c'est lui qui protège tes notifications).
3. Sur GitHub, ajoute un second secret : nom `NTFY_TOPIC`, valeur : ce même nom de sujet.

### 4. Activer le site
Dépôt → **Settings → Pages** → Source : *Deploy from a branch* → Branch : `main`, dossier `/docs` → Save.
L'adresse du journal sera `https://PSEUDO.github.io/la-veille/`.

### 5. Tester
Dépôt → onglet **Actions** → « Édition du matin » → **Run workflow**. Une édition prend environ 10 à 20 minutes.
Ensuite, elle part toute seule chaque matin à 5 h UTC (6 h à Paris en hiver, 7 h en été).

### 6. Installer l'app sur le téléphone
Ouvre l'adresse du journal :
- **iPhone (Safari)** : bouton Partager → « Sur l'écran d'accueil ».
- **Android (Chrome)** : menu ⋮ → « Installer l'application » ou « Ajouter à l'écran d'accueil ».

## Réglages

| Quoi | Où |
|---|---|
| Heure de publication | `.github/workflows/edition.yml`, ligne `cron` (heure UTC) |
| Modèle de recherche | Variable de dépôt `VEILLE_RESEARCH_MODEL` (Settings → Secrets and variables → Actions → Variables). Par défaut `claude-haiku-5-5`. |
| Modèle de rédaction | Variable `VEILLE_WRITING_MODEL`. Par défaut `claude-sonnet-5-5` ; `claude-haiku-5-5` pour réduire encore le coût, `claude-opus-5-5` pour la meilleure qualité (bien plus cher). |
| Plafond de dépense par édition | Variable `VEILLE_MAX_COST_USD`, par défaut `1.00`. L'édition s'arrête dès que le coût estimé le dépasse (la dernière requête en cours peut le dépasser de quelques dizaines de centimes). |
| Recherches web par rubrique | Variable `VEILLE_SEARCHES_PER_SECTION`, par défaut `5` (4 rubriques, donc 20 recherches au plus). |
| Centres d'intérêt, ton, structure | Les textes `READER`, `RESEARCH_SYSTEM` et `WRITING_SYSTEM` dans `generate.py` |
| Mise en page | `template.html` (styles) et `render.py` (structure) |

## Coût
Il n'y a que l'API Anthropic à payer ; GitHub Actions, GitHub Pages et ntfy sont gratuits à cet usage.
Avec les réglages par défaut (Haiku pour la recherche, Sonnet pour la rédaction, 20 recherches au plus), une édition est estimée
entre 0,40 $ et 0,90 $, recherches web comprises, soit environ 12 à 27 $ par mois. Le journal de chaque exécution (onglet Actions)
affiche le coût estimé de chaque étape. Compare-le avec la console Anthropic après quelques jours.

Pourquoi la recherche est découpée : dans une requête avec outil de recherche, tout le contexte (y compris les pages déjà lues) est
refacturé à chaque nouvelle recherche. Une seule longue requête de 40 recherches coûte donc très cher ; quatre requêtes courtes de
5 recherches, avec un modèle économique, coûtent une fraction de ce prix.

## En local
```
pip install -r requirements.txt
python generate.py --fixture fixtures/edition-2026-11-23.json --date 2026-11-23   # rendu seul, sans API
python -m http.server 8765 --directory docs                                       # puis http://localhost:8765
```

## Fichiers
- `generate.py` : recherche, rédaction, orchestration.
- `render.py` + `template.html` : mise en page et archives.
- `notify.py` : notification ntfy.
- `docs/` : le site publié (éditions, archives, manifest, service worker, icônes).
- `fixtures/` : l'édition N° 1 au format JSON, pour tester le rendu.
