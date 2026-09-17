# Plan d'implémentation et avancement

Référence : plan « Premières étapes de Latros — socle de données et moteur clinique pur » demandé par l'utilisateur. État au 17 septembre 2026.

Les trois jalons avaient été implémentés ensemble dans la première tranche. La reprise de l'étape 2 consiste à vérifier sa livraison et à établir le snapshot sous le nom du jalon, `v0.2.0`. Elle ne correspond pas à l'ajout de nouvelles sources ou de fonctions cliniques.

## Jalons du plan

| Étape | Nom du plan | État logiciel | Référence des données |
| --- | --- | --- | --- |
| 1 | Fondation technique — `v0.1.0` | Implémentée : paquet, CLI sources, registre, téléchargements vérifiés, verrou et CI | Aucun snapshot médical nécessaire à ce jalon |
| 2 | Premier snapshot médical — `v0.2.0` | Implémentée ; référence versionnée alignée sur le nom du plan | `manifests/v0.2.0.json` |
| 3 | Moteur pur et interrogatoire — `v0.3.0` | Implémentée dans le paquet `0.3.0` ; évaluation clinique non réalisée | Le moteur utilise le snapshot `v0.2.0` |
| 4 | Clinical Knowledge Model — `v0.4` | `v0.4-G` livré : audit v0.5 terminé avec `NO-GO` temporaire documenté | La référence reste `v0.2.0` ; aucun snapshot médical v2 publié |

Il s'agit des étapes du plan, pas d'une série de releases GitHub publiées. Aucun tag ou changement de version rétroactif du paquet n'est nécessaire pour identifier un snapshot. L'évaluation clinique et les fonctionnalités futures restent à discuter séparément.

## Étape 4 — Clinical Knowledge Model

Le [cahier des charges de v0.4](v0.4-clinical-knowledge-model.md) est la référence de la prochaine tranche. Son objectif est de généraliser les contrats cliniques et de connaissances, la provenance, la gestion des doublons et l'architecture des stratégies sans importer massivement de nouvelles bases ni casser `semantic_v1`.

La limitation actuelle aux maladies rares est explicite. Le snapshot HPO/Mondo/Orphadata ne couvre pas un tableau de médecine courante tel que fièvre et mal de gorge. `v0.4` prépare l'extension ; une première couverture étroite de médecine générale, avec des sources auditées et une stratégie dédiée, est prévue pour `v0.5`.

L'étape est suivie par checkpoints `v0.4-A` à `v0.4-H` dans le cahier des charges. Le cadrage
`v0.4-A` est approuvé et `v0.4-B` fixe les frontières dans les ADR 0002 à 0004. Deux tests d'or
figent les sorties complètes de `semantic_v1` et `question_v1`. `v0.4-C` livre le contrat clinique
v2, ses états séparés, ses observations typées, ses propositions et sa migration explicite depuis
v1. `v0.4-D` ajoute les contrats des treize tables canoniques futures et une projection en lecture
seule des sept tables historiques. Assertions sources, assertions canoniques, mappings,
dérivations, dépendances et familles de preuves y restent séparés. `v0.4-E` enveloppe ensuite le
moteur historique derrière quatre interfaces et un profil hashé, sans changer ses mathématiques.
`v0.4-F` expose les contrats v2 par la CLI en mode automatique ou explicite, avec couverture,
abstention, preuves par source et reçu déterministe. Le format v1 par défaut d'un cas v1 reste
strictement identique. Aucun snapshot n'est modifié.

`v0.4-G` vérifie les pages officielles ANS, SNOMED International et HAS. SNOMED CT France reste la
terminologie candidate et la recommandation HAS le corpus d'assertions candidat, mais l'ingestion
est en `NO-GO` jusqu'à résolution des licences, droits tiers, redistribution et revue clinique. Le
détail et les critères de sortie sont conservés dans
[`docs/source-audits/v0.5-orl.md`](source-audits/v0.5-orl.md).

Une première veille des ressources de médecine générale est intégrée au cahier des charges. Elle sépare terminologies, classifications, standards d'échange, sources d'assertions, règles cliniques, jeux synthétiques et benchmarks. Les matrices Kaggle/Mendeley ne sont pas retenues comme connaissance clinique tant que leur provenance n'est pas démontrée ; SNOMED CT, ICD, FHIR, LOINC, UCUM, UMLS, DDXPlus, Synthea, WHO SMART Guidelines, HealthBench, MIMIC-IV et ClinicDx sont positionnés selon leur rôle et une étape éventuelle, sans décision d'intégration anticipée.

Les futurs manifestes devront aussi déclarer le périmètre, les dépendances entre sources, les familles de preuves, les règles de déduplication et les profils de raisonnement compatibles. Le snapshot et le profil d'agrégation resteront versionnés séparément mais seront liés par leurs hashes dans chaque exécution. La référence historique `v0.2.0` ne sera pas réécrite.

## Étape 2 — périmètre livré

- [x] HPO `2026-09-01`, Mondo `2026-09-01`, Orphadata product4 EN/FR `2026-07`, URLs épinglées et SHA-256 attendus dans le registre.
- [x] Import des concepts, termes, hiérarchies, mappings et associations avec identifiants internes déterministes et identifiants sources conservés.
- [x] Sept tables : `source_release`, `concept`, `term`, `external_identifier`, `hierarchy_edge`, `mapping`, `disease_phenotype_assertion`.
- [x] Fréquences sans perte : k/n, pourcentage, intervalle, catégorie, exclusion, manquante.
- [x] Source, release, record, langue, polarité, fréquence et chaîne d'ingestion conservés pour chaque assertion.
- [x] Artefacts Parquet et runtime DuckDB utilisé en lecture seule, locaux et ignorés par Git.
- [x] Manifeste versionné avec sources, hashes, comptes, règles de transformation, erreurs et avertissements.
- [x] Rejet des identifiants internes non résolus, fréquences invalides, records dupliqués, provenance absente, conflits EN/FR et cycles hiérarchiques.
- [x] Reconstruction hors ligne et égalité des hashes canoniques vérifiées avec les mêmes sources et dépendances verrouillées.

Un concept obsolète qui existe dans HPO mais n'a pas de remplacement exact reste inactif ; un identifiant réellement inconnu bloque le build. Deux records distincts du producteur peuvent avoir des fréquences contradictoires : leurs assertions sont conservées et signalées, leurs fréquences sont écartées des pénalités/questions. Ces précisions sont actées dans [ADR 0001](decisions/0001-socle-recherche.md).

## Convention de nommage des snapshots

- Référence de l'étape 2 : **`v0.2.0`** dans `--snapshot`, `manifests/v0.2.0.json`, `data/canonical/v0.2.0/` et `data/runtime/v0.2.0/`.
- Une révision du même jalon reçoit une nouvelle version, par exemple `v0.2.1`, et une entrée dans ce plan et dans l'historique.
- Chaque nouveau jalon de données reçoit un nom documenté avant sa livraison. Un changement de moteur seul n'impose pas de renommer la base existante utilisée pour l'analyse ; reconstruire avec un code différent peut en revanche nécessiter une nouvelle référence, car le manifeste fixe le hash du code de construction.
- Le nom d'un snapshot et `latros_version` désignent deux choses différentes. Ici, `snapshot: v0.2.0` est construit avec le paquet `latros_version: 0.3.0`.
- Un snapshot publié et son manifeste restent immuables. `latros-kb-0002` est une ancienne référence conservée ; `v0.2.0` est une construction distincte dont les hashes de contenu et Parquet doivent être identiques.
- Les IDs libres des fixtures ou expériences locales restent possibles ; seuls les noms des références livrées suivent cette convention.

## Vérifications de la référence v0.2.0

Le manifeste [v0.2.0.json](../manifests/v0.2.0.json) est la source des comptes et des hashes. La construction par la CLI, l'inspection vérifiant les hashes, la comparaison avec `latros-kb-0002` et une reconstruction depuis le manifeste seul et les sources locales ont réussi. Les sept tables et leurs hashes sont identiques ; le nouveau manifeste ne diffère de l'ancien que par son identifiant. Les 14 tests d'intégration du pipeline ont également réussi.

Les données canoniques sont reproductibles ; le checksum du conteneur DuckDB, dont les octets internes peuvent varier, est enregistré séparément dans un reçu local. Les 19 avertissements du snapshot initial restent présents. Les tests synthétiques du pipeline vérifient ses refus d'entrées invalides ; ils ne mesurent pas la justesse médicale du moteur.

## Mise à jour à chaque livraison

Actualiser ensemble [history.md](../history.md), [README.md](../README.md) et ce plan : état réel des jalons, noms de snapshots, commandes, décisions, vérifications et limites. Si un contrat, une source ou une règle d'import change, actualiser également le schéma, le registre, le manifeste ou l'ADR concernés. Garder les réalisations antérieures dans le journal daté.
