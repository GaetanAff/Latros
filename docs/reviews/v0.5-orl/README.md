# Revue clinique du corpus ORL v0.5

Ce dossier prépare la revue humaine du plus petit corpus réel envisagé pour le pilote ORL adulte.
Il ne constitue ni un snapshot médical, ni une validation clinique, ni une autorisation de
publication.

État au 17 septembre 2026 :

- 17 assertions structurées en `pending_review` ;
- 10 mappings DOID/Mondo en `pending_review` ;
- 4 candidats couverts par au moins deux assertions et un discriminant ;
- 12 reçus d'artefacts locaux avec version, licence, date d'accès et SHA-256 ;
- 0 reviewer déclaré et 0 décision de revue ;
- statut automatique : `ready_for_human_review`, publication `blocked`.

Le rapport machine-readable est [`audit-report.json`](audit-report.json). Le
[tableau de revue](assertion-review.md) est généré depuis le paquet versionné et ne contient aucun
texte source long.

## Reproduire le contrôle

Les captures et représentations de segments sont locales et ignorées par Git. Après les avoir
placées aux chemins et hashes déclarés dans
[`curation/v0.5-orl/sources.json`](../../../curation/v0.5-orl/sources.json) :

```text
uv run --offline --no-sync latros curation review-workbook \
  --package curation/v0.5-orl \
  --destination docs/reviews/v0.5-orl/assertion-review.md

uv run --offline --no-sync latros curation audit \
  --package curation/v0.5-orl \
  --report docs/reviews/v0.5-orl/audit-report.json

uv run --offline --no-sync latros curation audit \
  --package curation/v0.5-orl \
  --require-publishable
```

La dernière commande doit actuellement échouer. L'export vers l'importeur v2 est également refusé
tant que le gate reste fermé.

## Procédure de revue réelle

Pour chaque assertion, les reviewers contrôlent le segment local, sa page, sa localisation, la
population, la relation, la polarité, les qualificatifs, la granularité du candidat, le mapping et
la famille de preuve. L'absence d'information dans une page ne devient jamais une assertion
négative.

1. Toute correction modifie d'abord l'assertion ou le mapping dans le paquet.
2. Le tableau est régénéré : le hash de l'enregistrement corrigé change.
3. Chaque reviewer réel produit une décision JSONL liée à ce hash exact.
4. Deux personnes distinctes doivent approuver chaque assertion, dont au moins un clinicien
   compétent ; un reviewer attesté pour le mapping doit aussi approuver.
5. L'attestation réelle de chaque reviewer est placée sous `review-attestations/`, ignoré par Git.
   Son chemin et son hash sont consignés dans `reviewers.jsonl`.
6. Une décision `approved_with_change` impose la correction puis une nouvelle décision
   `approved` sur le nouveau hash. Elle n'ouvre pas directement le gate.
7. Les statuts des enregistrements et du manifeste ne passent à `approved` /
   `approved_for_snapshot` qu'après présence des preuves correspondantes.

Les états autorisés sont `pending_review`, `approved`, `approved_with_change` et `rejected`.
Le logiciel n'invente jamais l'identité, la qualification, la signature ou la décision d'un
reviewer.

## Blocage restant

Les travaux techniques de F sont préparés, mais F et G ne sont pas commencés. Les éléments
bloquants sont exactement :

- les 17 doubles décisions d'assertion ;
- au moins une attestation de clinicien compétent et une attestation de rôle mapping ;
- les 10 décisions de mapping ;
- la promotion explicite du manifeste après toutes les revues.

Une fois ces éléments réellement disponibles, le gate pourra autoriser l'export JSONL approuvé.
Seulement ensuite pourront être créés le profil ORL réel et le snapshot immuable `v0.5.0`.
