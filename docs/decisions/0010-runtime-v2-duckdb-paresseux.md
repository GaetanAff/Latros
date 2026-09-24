# ADR 0010 — Lecture paresseuse du runtime canonique v2

Statut : accepté pour `v0.7-F2`
Date : 24 septembre 2026

## Contexte

`v0.7.0-general-dev-unreviewed` est un snapshot figé de 385 886 assertions canoniques. Sa
lecture historique désérialisait les treize tables DuckDB et retenait plus de 2,6 millions
d'objets Pydantic ; la stratégie créait ensuite plusieurs index Python. La première recherche UI
prenait environ 57 s et le premier diagnostic multi-système atteignait 10,97 Go de RSS.
`store_v2.py` participe au hash du pipeline de construction : le modifier pour réécrire le runtime
rendrait la reconstruction du snapshot historique incompatible.

## Décision

- Conserver intégralement le DuckDB, les Parquet, le manifeste, les hashes et le constructeur
  canonique v2. Aucun nouvel identifiant de snapshot n'est nécessaire car aucune connaissance ni
  structure de snapshot n'est modifiée.
- Ajouter un repository de lecture séparé, ouvrant DuckDB en lecture seule après la vérification
  forte existante des artefacts. Les requêtes SQL y sont centralisées.
- Résoudre les observations et les mappings par requêtes ciblées ; présélectionner uniquement les
  conditions avec une contribution numérique possible dans une famille agrégeable permise par le
  profil. La génération publique conserve ses IDs et métadonnées historiques.
- Charger les assertions, dérivations et métadonnées de provenance uniquement pour ces candidats.
  Les questions discriminantes et le catalogue de concepts UI sont calculés côté DuckDB sans
  charger globalement `CanonicalKnowledgeV2`.
- Garder l'ancienne stratégie complète comme oracle de régression ; comparer les sorties JSON
  complètes du vrai snapshot et les contrats synthétiques, sans modifier la mathématique de
  `general_v1`.
- Limiter à deux repositories le cache du service et vérifier, avant réutilisation, que les
  attributs des fichiers initialement hashés restent inchangés. Une modification détectée échoue
  fermée. Fermer les connexions à l'éviction et à l'arrêt de l'interface.

## Conséquences et limites

La souveraineté offline et les statuts de validation restent inchangés. Le runtime historique
stocke principalement des couples `id/payload_json` : certaines requêtes doivent encore scanner
et extraire du JSON, et le résultat complet de centaines de candidats avec provenance occupe de
la mémoire. Ce durcissement ne change ni les règles de questionnement, ni la calibration, ni la
validation clinique. Une éventuelle projection runtime indexée serait une décision séparée avec
nouvel identifiant de snapshot si elle modifie le build ou les artefacts figés.
