# Paquet de curation ORL v0.5

Ce répertoire versionne des interprétations structurées et leur provenance, pas les pages sources.
Son statut est `pending_clinical_review`.

- `manifest.json` : périmètre, seuils et empreinte de la représentation locale des segments ;
- `sources.json` : reçus d'artefacts, licences, attributions, dépendances et hashes ;
- `concepts.jsonl` : quatre candidats internes et les observations utilisées ;
- `mappings.jsonl` : mappings DOID/Mondo qualifiés, tous en attente de revue ;
- `assertions.jsonl` : 17 assertions atomiques en attente de double revue ;
- `reviewers.jsonl` et `reviews.jsonl` : volontairement vides tant qu'aucune preuve humaine
  réelle n'existe.

Les captures sources, la représentation exacte des segments et les attestations restent sous
`data/raw/` et `review-attestations/`, tous deux ignorés par Git. Le gate vérifie leurs hashes.

DOID et Mondo servent uniquement à la terminologie. NHS, nidirect et les résumés Health Topics
MedlinePlus autorisés sont les seules sources d'assertions présentes. Les pages CDC ont été
écartées du paquet distribuable en attendant une clarification juridique applicable à la
redistribution internationale. nidirect est classé comme republication NHS ; MedlinePlus reste
non agrégeable lorsque sa dépendance est inconnue.

Voir [le dossier de revue](../../docs/reviews/v0.5-orl/README.md) pour les commandes et le workflow.

Tant qu'une case manque, aucun manifeste officiel `v0.5.0` n'est autorisé. Pour l'ingénierie locale,
le paquet peut toutefois alimenter `v0.5.0-dev-unreviewed` avec l'override explicite
`--allow-unreviewed-research-data`. Ce chemin conserve toutes les lignes `pending_review`, ne crée
aucun reviewer et marque manifeste, profil et résultats comme non validés et non publiables.
