# Journal des décisions d'architecture

Ce dossier contient les décisions qui modifient durablement Latros : périmètre clinique, sources de données, licences, modèle de données, stratégie de raisonnement, sécurité, évaluation et choix techniques.

Décisions acceptées :

- [0001 — Socle local maladies rares et moteur pur](0001-socle-recherche.md) ;
- [0002 — Contrats cliniques v2 et compatibilité v1](0002-clinical-contracts-v2.md) ;
- [0003 — Knowledge Model canonique v2](0003-canonical-knowledge-v2.md) ;
- [0004 — Stratégies, profils et reçus d'exécution](0004-reasoning-artifacts.md) ;
- [0005 — Snapshot canonique v2 et pilote ORL séparé](0005-snapshot-v2-et-pilote-orl.md) ;
- [0006 — Sources ouvertes du pilote ORL](0006-sources-ouvertes-pilote-orl.md) ;
- [0007 — Mode local ORL non revu](0007-mode-recherche-orl-non-revu.md).
- [0008 — Interface locale R&D et sessions reproductibles](0008-interface-locale-rd-et-sessions.md).
- [0009 — Fabrique de connaissances généraliste souveraine](0009-fabrique-souveraine-generaliste.md).
- [0010 — Runtime v2 DuckDB paresseux](0010-runtime-v2-duckdb-paresseux.md).
- [0011 — Parcours simple local et console experte conservée](0011-parcours-simple-local.md).
- [0012 — Outil local de revue humaine G1/G2](0012-outil-local-de-revue-humaine.md).
- [0013 — Projections HTTP paresseuses des résultats immuables](0013-transport-paresseux-des-resultats.md).
- [0015 — Affichage multilingue et alias séparés de la connaissance](0015-affichage-multilingue-local.md).

Utiliser un fichier par décision, par exemple :

```text
0001-perimetre-clinique-initial.md
```

Chaque décision devrait contenir :

```text
Titre
Statut : proposé / accepté / remplacé
Contexte
Décision
Alternatives considérées
Conséquences
Sources et licences concernées
Date
```
