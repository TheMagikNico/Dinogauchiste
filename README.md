# Dinogauchiste – newsletter web (société française)

Site statique, 3 pages : `index.html` (24 h), `semaine.html` (7 jours), `mois.html` (30 jours).
Pas de publicité, pas de traceur, pas de script tiers (politique CSP dans chaque page).

## Mise en ligne gratuite (GitHub Pages)

1. Créez un dépôt GitHub public et envoyez-y tout ce dossier.
2. Réglages › Pages › Source : branche `main`, dossier `/docs`.
3. Onglet Actions › « Mise à jour des articles » › Run workflow (première collecte).
   Ensuite la collecte se relance toute seule chaque heure ; les pages rechargent `data.json` toutes les 5 minutes.
4. (Optionnel) Réglages › Secrets › `ANTHROPIC_API_KEY` : résumés reformulés de 5 à 8 phrases.
   Sans clé, le résumé est l'extrait fourni par le flux RSS du média.

Alternatives gratuites : Cloudflare Pages ou Netlify (dossier publié : `docs`).

## Choix des sources

Modifiez `sources.json` (nom, URL du flux RSS, `society_only`, `enabled`).
Les URLs de flux n'ont pas pu être testées à la création : un flux en erreur est ignoré et signalé dans le journal de l'Action.

## Test local

    pip install -r requirements.txt
    python build.py --demo     # données factices
    python build.py            # collecte réelle
    cd docs && python -m http.server

## Limites à connaître

- Un RSS ne contient souvent qu'un extrait (surtout Mediapart, Le Monde diplomatique) : le « détail » est alors court et renvoie vers la source.
- Les images sont chargées depuis le site du média (liens directs).
- Le bloqueur protège ce site ; une fois chez le média, ses publicités reviennent : utilisez uBlock Origin.
