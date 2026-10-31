# Dinogauchiste – newsletter web (société française)

Site statique, 3 pages : `index.html` (24 h), `semaine.html` (7 jours), `mois.html` (30 jours).
Pas de publicité, pas de traceur, pas de script tiers (politique CSP dans chaque page).

## Choix des sources

Modifiez `sources.json` (nom, URL du flux RSS, `society_only`, `enabled`).
Les URLs de flux n'ont pas pu être testées à la création : un flux en erreur est ignoré et signalé dans le journal de l'Action.


## Limites à connaître

- Un RSS ne contient souvent qu'un extrait (surtout Mediapart, Le Monde diplomatique) : le « détail » est alors court et renvoie vers la source.
- Les images sont chargées depuis le site du média (liens directs).
- Le bloqueur protège ce site ; une fois chez le média, ses publicités reviennent : utilisez uBlock Origin.
