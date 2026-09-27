# ADR 0017 — General-first expérimental / Rare-second opt-in

Date : 27 septembre 2026. Statut : accepté pour expérimentation logicielle, **non clinique**.
Référence : issue #18 et clarification utilisateur autorisant un profil mono-source séparé.

## Cause et décision

`general_v1` choisit globalement le finding aux polarités explicitement opposées dans le corpus
mixte, sans politique de consultation courante ni conditionnement au tableau initial. Sur
rhinorrhée, la déficience intellectuelle sépare beaucoup d'annotations rares. Ce n'est pas un
problème de traduction. Les assertions MedlinePlus `unknown` restent exclues de son agrégat.

Conserver intégralement `general_v1`, `semantic_v1` et leurs goldens ; ajouter :

- `general_question_v2` : MedlinePlus `2026-09-19`, candidates retained G4 non revues/sans reviewer,
  mappings résolus exact/equivalent. Exclusion des maladies marquées par les hiérarchies
  MONDO:0003847 / DOID:630, identités ORPHA ou mappings Orphanet résolus exact/equivalent.
  Absence de marqueur n'est **pas** preuve de prévalence courante.
- `rare_question_v1` : Orphadata et Monarch d'amont explicite OMIM/Orphanet. Périmètre orienté
  rare, pas recensement exhaustif ni preuve de prévalence.

Les projections sont des tables TEMP sur une connexion DuckDB **read-only**. Snapshot et
manifeste restent inchangés. Après création de TEMP, qualifier le catalogue original explicitement :
`main` seul peut résoudre une table temporaire de même nom. Profils : extensions explicites liant
hash du snapshot + profil parent compatible hashé, pas compatibilité rétroactive ajoutée au
manifeste. Le profil général épingle aussi le JSONL retained G4 ; absent/corrompu : refus, pas fetch.

## Mono-source, pas plusieurs preuves indépendantes

Dans le NOUVEAU profil seulement, une unique famille éditoriale MedlinePlus est éligible
numériquement. Sa dépendance reste `unknown`, `aggregatable: false` pour l'indépendance,
`single_source_numeric_eligible: true`, `clinical_source_count: 1`. Plusieurs assertions sont
moyennées au sein de cette seule famille avec les contributions existantes +1/-1 ; aucun poids
de plusieurs sources, aucune calibration/probabilité, aucun `approved`. La règle historique
d'exclusion `unknown` est intacte.

MedlinePlus exprime les manifestations par `has_symptom`. La projection générale compare les
observations supportées à cette relation sans modifier leur codage/kind dans `ClinicalCaseV2` ;
la transformation figure au reçu. Convention source expérimentale, pas nouvelle assertion médicale.

## Questions / arrêt

Candidats conditionnés aux findings évalués du cas dans chaque périmètre. MedlinePlus n'a pas
de négatifs explicites : jamais convertir une annotation manquante en exclusion. La politique
générale classe la **variation de documentation** `min(documented, candidates-documented)`,
puis documentation décroissante et ID canonique. Ce n'est ni un gain informationnel calibré ni
un discriminant validé. Rare utilise des polarités explicitement opposées, conditionnées au cas.

Exclure concepts actifs déjà renseignés (même inconnus/non évaluables) et réponses conservées
dans `question_history`. Pas de follow-up implicite. Arrêt : âge inexploitable/hors périmètre,
absence de question admissible, budget atteint ou demande de résultats. Budgets initiaux 6 / 12,
configurables dans un profil hashé (borne logicielle 1–20), **pas seuils médicaux**. Aucune
politique de durée/stabilité/gain clinique inventée.

## Sessions / UX / limites

Un même `ClinicalCaseV2`, compteurs et runs distincts. Résultats généraux constituent une fin.
Rare exige un POST explicite après un résultat général correspondant au cas courant. Jamais
enchaîné automatiquement ; résultats séparés, jamais triés ensemble par score. Édition manuelle
pendant rare : recommencer général, anciens runs immuables. `consultation.workflow_version: 1`
est optionnel et backward-compatible. CLI `--strategy rare_question_v1` constitue un opt-in explicite.

Même `ResearchApplicationService`, `/expert` et ancien moteur conservés. Aucun raisonnement
frontend. HPO reste vocabulaire canonique. Source générale étroite, nombreux ex aequo, questions
encore génériques, pas de fréquence populationnelle ni validation des mappings. G1/G2 humains
et G3 indépendant restent requis. Tous les statuts du snapshot et safety restent inchangés.
