# Documentation de Latros

Ce répertoire rassemble la documentation durable du projet. Le `README.md` à la racine reste la
porte d'entrée courte ; les détails sont rangés ici par rôle.

## Démarrer et utiliser

- [Tutoriel complet](tuto.md) : installation, snapshots, interface, essais guidés, sessions,
  interprétation des résultats et dépannage.
- [Interface R&D v0.6](v0.6-rd-interface.md) : contrat et limites de la console locale.
- [Parcours simple local](modern-ui.md) : sélection explicite, questions, résultats et mode expert.
- [Méthodologie](methodology.md) : calcul historique de `semantic_v1` et limites scientifiques.
- [Couverture généraliste v0.7](reports/v0.7-general-coverage.md) : métriques réelles du snapshot
  souverain DEV, comparaison ORL et limites de performance/validation.

## Suivre le projet

- [Plan et avancement](plan.md) : roadmap v0.1 à v0.10 et checkpoints.
- [Historique](history.md) : journal chronologique de ce qui a réellement été livré et vérifié.
- [Vision du projet](projet.md) : ambition d'ensemble et cahier prospectif.
- [Clinical Knowledge Model v0.4](v0.4-clinical-knowledge-model.md) : cahier des charges du modèle
  clinique et de connaissances général.

## Décisions, sources et revues

- [ADR](decisions/README.md) : décisions d'architecture numérotées et immuables.
- [Audits de sources](source-audits/README.md) : licences, provenance et décisions `GO/NO-GO`.
- [Dossier de revue ORL](reviews/v0.5-orl/README.md) : assertions en attente de revue humaine.
- [Audit souverain v0.7](source-audits/v0.7-sovereign-general.md) : distributions exactes,
  hashes, licences et décision CDC.

## Contrats machine-readable

Les contrats et références exécutables restent volontairement hors de `docs/` :

- `schemas/` : schémas JSON exportés ;
- `manifests/` : manifestes de snapshots ;
- `profiles/` : profils de raisonnement ;
- `sources/` : registres de sources ;
- `curation/` : paquets structurés et statuts de revue ;
- `examples/` : cas exclusivement synthétiques.

Les données brutes, snapshots construits, sessions et données patient ne sont jamais de la
documentation versionnée et restent ignorés par Git.
