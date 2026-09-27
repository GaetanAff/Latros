# Profil mono-source général expérimental / exploration rare

Audit logiciel du 26–27 septembre 2026, **pas une évaluation clinique**.
[ADR 0017](../decisions/0017-consultations-generale-et-rare-versionnees.md).

## Périmètre

Snapshot inchangé `v0.7.0-general-dev-unreviewed`, hash
`bfda708aba44dcc5d12896ac7523d9d6bb577dea53bdc3810e499c15f64b1fb0`.
G4 : 2 212 retained, 4 056 needs_human_review, 1 468 rejected. Seuls retained non revus/sans
reviewer au mapping exact/equivalent résolu entrent dans le général ; les deux autres lots sont
exclus de ce profil, **pas déclarés médicalement faux**. Marqueurs rares/génétiques exclus.

| Projection | Maladies | Assertions canoniques | Assertions sources | Findings |
| --- | ---: | ---: | ---: | ---: |
| Générale MedlinePlus G4 | 142 | 684 | 706 | 210 |
| Rare Orphadata / Monarch amont OMIM-Orphanet | 14 951 | 382 303 | 382 500 | — |

106 des 142 maladies sont mono-source dans le corpus original. Les 36 autres sont néanmoins
scorées ici **uniquement par MedlinePlus**. Une seule famille éditoriale `unknown`, pas 706 preuves
indépendantes. Aucun `approved`. La couverture G4 de 189 maladies n'est pas le périmètre du
profil : mappings techniques + exclusion structurelle la réduisent à 142. Pas de prévalence déduite.

## Reproduction offline

Avec artefacts et snapshot locaux figés :

```powershell
uv run --offline --no-sync python scripts/build_v07_g4_medlineplus_candidates.py --output-dir data/staging/v0.7-g4/quality-v2-release
uv run --offline --no-sync python scripts/benchmark_consultation_policies.py
uv run --offline --no-sync python scripts/compare_general_v1_runtime.py --output data/staging/general-rare-after-golden.json --expected data/staging/pr17-review-golden.json
```

JSONL retained épinglé : `78cdfd2d47f3b1fd7aa87f7f564442d7d5b606ed655fb593b8bc366e007cf9a7`.
Benchmark : connexions socket interdites ; metrics, IDs, questions et digests uniquement sous
`data/staging/consultation-policies/`, ignoré par Git. Cas inventés, âge 30, aucun patient réel.
Codes résolus consignés (ex. céphalée HP:0000266). Réponses de séquence toutes `unknown`.
Latences mêlent ouvertures/calcul : ce n'est pas une nouvelle optimisation F-runtime.

## Résultats réels

| Cas | Candidats ancien / général / rare | Première question générale | Première rare | Couverture générale / abstention |
| --- | --- | --- | --- | --- |
| Rhinorrhée seule | 0 / 0 / 0 | Wheezing | Functional motor deficit | 1 / moins de 2 findings évalués |
| Rhinorrhée + céphalée + congestion | 613 / 19 / 600 | Pain | Brain imaging abnormality | 1 / aucune |
| Fièvre + douleur pharyngée | 697 / 35 / 696 | Fatigue | Splenomegaly | 1 / aucune |
| Fièvre + toux | 839 / 43 / 830 | Pain | Splenomegaly | 1 / aucune |
| Dysurie + fièvre | 723 / 33 / 722 | Fatigue | Splenomegaly | 1 / aucune |
| Douleur abdominale + nausée | 1 048 / 24 / 1 021 | Fever | Intellectual disability | 1 / aucune |
| Fièvre + céphalée ambiguës | 1 082 / 39 / 1 069 | Fatigue | Vasculitis | 1 / aucune |
| Multisystémique rare | 799 / 0 / 799 | Aucune | Frontal bossing | 0 / aucun finding dans le périmètre général |

Ancien `general_v1` : déficience intellectuelle en première question des cas courants,
séparation **globale** du corpus mixte. Nouveau : uniquement documentation MedlinePlus G4
des candidats liés au cas. Rare ne pilote jamais les questions de la phase générale.
Les 7 séquences courantes atteignent 6 questions ; le multisystémique s'arrête à 0. Moyenne
5,25 sur 8 scénarios (6 sur les 7 courants), maximum 6, **0 répétition**. L'UI affiche une
borne restante du budget, pas une prévision médicale, et permet les résultats immédiats.

## Classement / limites : ne pas les masquer

Nouveau classement délibérément différent et versionné : rhume commun en tête du cas sinus,
grippe porcine du pharyngé, hépatite A du digestif, histoplasmose dans plusieurs cas avec fièvre.
**Aucun de ces rangs ne démontre une justesse clinique.** Nombreux scores +1 ex aequo, départagés
par nombre évalué puis ID déterministe. Fièvre concordante n'implique pas diagnostic probable.
Pas de négatifs explicites, fréquence, prévalence, calibration ou durée ; questions souvent
génériques. Annotation manquante jamais convertie en négatif. Rhinorrhée seule conserve une
abstention ; le multisystémique s'abstient en général et reste explorable en rare.

## Contrôles

- 229 tests Python et 15 frontend ; Ruff, format, mypy strict, schémas et registre verts.
- Sept diagnostics/questions historiques complets : digests exactement identiques à la revue #17.
  `semantic_v1` / `question_v1` inchangés.
- Navigateur HTTP local : rhinorrhée → Wheezing → inconnu → congestion, sans répétition.
- Opt-in, cas partagé, runs séparés immuables, reprise, détails lazy testés ; DuckDB read-only,
  fichier G4 absent/corrompu refusé, pas de fetch, cache borné à deux repositories.
- `clinical_validation: false`, `publishable: false`, `research_unreviewed: true`,
  `safety_status: not_evaluated` inchangés ; aucune revue fictive. CI Linux/Windows requise en PR.

Prochaine action scientifique : vraies revues humaines G1/G2/G5 puis G3 indépendant. Pas de
promotion automatique. Le chantier visuel reste une PR distincte et n'apporte pas de connaissance.
