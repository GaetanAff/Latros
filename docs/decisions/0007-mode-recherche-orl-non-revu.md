# ADR 0007 — Mode local ORL non revu

**Statut :** accepté pour la recherche locale ; publication clinique toujours bloquée

**Date :** 18 septembre 2026

## Contexte

Le paquet ORL E3 est techniquement complet mais ses 17 assertions et 10 mappings restent
`pending_review`. Le gate officiel doit continuer à interdire `v0.5.0`, tandis que le développement
du pipeline, de `general_v1` et de la future interface a besoin d'un corpus réel local.

## Décision

- `v0.5.0` reste exclusivement soumis au gate de publication et à la double revue prévue.
- Le suffixe `-dev-unreviewed` réserve une classe d'identifiants non cliniques. Le premier est
  `v0.5.0-dev-unreviewed`.
- Sa construction exige l'option volontaire `--allow-unreviewed-research-data`. Cette option est
  refusée pour tout autre identifiant et ne peut jamais produire `v0.5.0`.
- Le paquet source doit être techniquement `ready_for_human_review`. L'override ne contourne ni les
  licences, ni les hashes, ni la provenance, ni les seuils de contenu, ni les erreurs techniques.
- Le constructeur ne modifie aucun fichier de revue. Le manifeste liste les IDs pending, le nombre
  réel de reviewers, l'override, les limites et `publishable: false`.
- `general_v1-orl-unreviewed` est un profil d'ingénierie. Son poids NHS égal à `1.0` n'est pas une
  validation clinique ; nidirect reste dans cette famille et NLM à dépendance inconnue est exclu.
- Chaque diagnostic et chaque question portent `research_unreviewed: true`; leur reçu répète le
  snapshot, le statut, les comptes pending et l'override. `safety.status` reste `not_evaluated`.

## Alternatives considérées

- **Desserrer le gate officiel :** rejeté, car cela confondrait disponibilité technique et revue
  clinique.
- **Copier les lignes en `approved` dans un paquet de développement :** rejeté comme falsification
  de l'état source.
- **Rester uniquement sur fixtures inventées :** insuffisant pour tester l'intégration du corpus et
  les contraintes réelles de provenance.

## Conséquences

- Un résultat expérimental ne peut pas être sérialisé sans marqueur explicite cohérent avec son reçu.
- Les mappings `exact/equivalent` résolus peuvent servir à la résolution technique tout en conservant
  `pending_review`; les autres relations restent non scorantes.
- Le manifeste expérimental peut être versionné, mais ses Parquet, DuckDB, captures et reçus locaux
  restent hors Git. Il ne constitue pas un snapshot clinique de référence.
- `v0.5-F` et `v0.5-G` restent bloqués et v0.5 n'est pas déclarée terminée.

## Sources et licences concernées

Le mode réutilise strictement les reçus, licences, hashes et restrictions du paquet
[`curation/v0.5-orl`](../../curation/v0.5-orl/README.md). Il n'accorde aucun droit supplémentaire et
ne versionne aucune capture protégée.
