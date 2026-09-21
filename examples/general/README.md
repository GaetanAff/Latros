# Cas synthétiques généralistes

Ces cas servent uniquement aux tests logiciels de `general_v1`. Ils ne représentent aucun patient
réel et ne constituent ni des vignettes validées, ni des benchmarks cliniques. Le cas ORL historique
reste `examples/case.orl-unreviewed.json`.

| Fichier | Intention technique |
| --- | --- |
| `respiratory-common.json` | tableau respiratoire banal structuré |
| `ambiguous-febrile.json` | observations non spécifiques et candidats concurrents |
| `outside-corpus.json` | concept local volontairement non résolu |
| `insufficient.json` | une seule observation, donc abstention attendue |
| `empty.json` | aucune observation, donc abstention attendue |
| `contradictory.json` | signes présents et absents pour exercer les contradictions |
| `rare-multisystem.json` | cas multi-système hors du pilote ORL |

