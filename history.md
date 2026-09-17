# Historique de Latros

Ce fichier est le journal de continuité du projet. Il décrit ce qui a été décidé et effectivement réalisé, afin de pouvoir reprendre la discussion sans déduire l'état du projet à partir du code seul.

Dernière mise à jour : 17 septembre 2026.

## État actuel en une phrase

Latros est aujourd'hui un prototype local de recherche, utilisable en ligne de commande, qui prend un cas clinique **déjà structuré en identifiants HPO**, classe des maladies rares ORPHA selon une compatibilité sémantique explicable, puis propose une question discriminante. Il n'est ni un chatbot, ni une interface patient, ni un outil de triage ou de diagnostic clinique validé.

Référence actuelle des données : **`v0.2.0`**, nom du jalon « Premier snapshot médical » dans le [plan d'implémentation](docs/plan.md). Le paquet est à la version `0.4.0` ; aucun snapshot médical v2 n'est publié. L'ancien snapshot `latros-kb-0002` est conservé.

## Décisions de cadrage antérieures

- Le projet a été renommé **Latros** ; le nom initial était ClinAtlas.
- La cible à long terme reste un système local, offline-first, avec un moteur médical explicable qui fonctionne sans LLM.
- Les trois états d'un signe sont distincts : `present`, `absent`, `unknown`.
- La provenance, la version, la licence et les identifiants originaux doivent être conservés à chaque étape.
- La première audience est l'équipe recherche/développement, pas des patients.
- Le premier périmètre est les maladies rares, car HPO/Mondo/Orphadata sont structurés pour ce cas.
- MedASR et toute intégration vocale sont retirés du périmètre à la demande de l'utilisateur. Aucune évaluation de MedASR n'a été réalisée dans cette tranche.
- MedGemma est reporté à une couche future facultative de NLP/explication, après validation du moteur pur. TxGemma est reporté à un module thérapeutique séparé, futur et non clinique dans l'état actuel.
- Aucune interface, API web, Docker, LLM local, modèle téléchargé, entraînement, audio ou recommandation thérapeutique n'a été développé dans cette tranche.

La vision complète, y compris les futures pistes LLM, est dans [projet.md](projet.md). Les décisions applicables à la tranche actuelle sont dans [ADR 0001](docs/decisions/0001-socle-recherche.md).

## Dépôt et manière de travailler

- Dépôt GitHub privé : `GaetanAff/Latros`.
- Branche stable : `main`, actualisée avec le socle v0.1–v0.3 et le cadrage v0.4 accepté.
- Implémentation v0.4 effectuée sur `feat/v0.4-clinical-knowledge-model`.
- Commit de la tranche : `d7ef85c6fe41c19828318662b8968425abffe6a9` — 16 septembre 2026.
- Pull request ouverte, sans fusion dans `main` : [#1 — Socle local : données rares, moteur clinique pur et questions adaptatives](https://github.com/GaetanAff/Latros/pull/1).
- La CI GitHub Linux et Windows est verte pour cette pull request.
- Le dossier local non suivi `FUTUR INTERFACE/` était présent dans l'espace de travail et n'a été ni lu, ni modifié, ni ajouté au commit.

Les règles de contribution sont dans [CONTRIBUTING.md](CONTRIBUTING.md) : branche par fonctionnalité, pull request, `main` stable, aucune donnée de santé ou base brute dans Git.

## Ce qui a été implémenté

### Fondation technique — v0.1.0 intégrée dans la tranche v0.3.0

- Paquet Python `src/latros`, compatible Python 3.11.
- Dépendances verrouillées avec `uv` dans `uv.lock`.
- Contrats Pydantic, CLI Typer, DuckDB/Parquet, `httpx`, `orjson`, `lxml`.
- Qualité : pytest, Ruff, mypy et CI GitHub sous Linux/Windows.
- Commandes de sources :

  ```text
  latros sources list
  latros sources validate
  latros sources fetch --source <id> --release <version>
  ```

- Les artefacts sont téléchargés vers `data/raw/<source>/<release>/`, jamais versionnés dans Git.
- Chaque fichier est vérifié par SHA-256. Les sources doivent avoir une version, une licence et une URL HTTPS immuable ; les URLs `latest`, `main` et `master` sont refusées.
- Les téléchargements incomplets restent en `.part` et peuvent être relancés. Un fichier déjà complet mais corrompu n'est jamais écrasé silencieusement.
- [sources/registry.yaml](sources/registry.yaml) est le registre versionné des sources, licences, attributions, produits, dépendances amont et hashes.

### Premier snapshot médical — v0.2.0 intégrée dans la tranche v0.3.0

Sources importées, et seulement celles-ci :

| Source | Version épinglée | Rôle effectif |
| --- | --- | --- |
| HPO | 2026-09-01 | Concepts HPO, synonymes, identifiants alternatifs, hiérarchie `is_a` |
| Mondo | 2026-09-01 | Concepts de maladies, synonymes et mappings ORPHA documentés |
| Orphadata product 4 EN/FR | archive juillet 2026, commit `463f51d0...` | Associations ORPHA–HPO, fréquences, libellés de source et provenance bilingue |

Sources explicitement reportées : HPOA, Monarch, UMLS, DDXPlus, MedGen, Disease Ontology, Symptom Ontology, Wikidata, Synthea, SemMedDB et les autres jeux mentionnés dans la phase de conception.

Les tables canoniques sont :

```text
source_release
concept
term
external_identifier
hierarchy_edge
mapping
disease_phenotype_assertion
```

Principes appliqués :

- Identifiants internes déterministes ; les identifiants HPO, MONDO et ORPHA restent conservés.
- Les maladies candidats restent des identités ORPHA. Un `exactMatch` Mondo est affiché séparément ; un simple `xref` n'est jamais transformé en équivalence.
- Les fréquences restent sans perte : compte `k/n`, pourcentage, intervalle, catégorie, exclusion ou absence de valeur.
- Chaque assertion garde son record source, release, fichiers et hashes, langues, fréquence, référence et chaîne d'ingestion.
- Les enregistrements EN/FR de même record sont vérifiés puis coalescés : ils ne comptent pas comme deux preuves indépendantes.
- Un libellé HPO resté anglais dans le document Orphadata français est conservé comme anglais, au lieu d'être présenté à tort comme une traduction française.
- Un concept HPO obsolète sans remplacement exact est conservé dans les données avec un avertissement, mais ne participe pas au raisonnement. Un lien `consider` n'est pas inventé comme une équivalence.
- Des fréquences contradictoires pour un même couple maladie–phénotype, venant de records distincts, sont conservées et exposées ; elles sont exclues des pénalités et de la sélection des questions.

Le manifeste canonique de la première livraison était [latros-kb-0002.json](manifests/latros-kb-0002.json). Il est conservé ; la référence actuelle est [v0.2.0.json](manifests/v0.2.0.json), établie avec les mêmes données sous le nom du jalon du plan. Les snapshots complets sont locaux et ignorés par Git.

Résultat du build réel effectué le 16 septembre 2026 :

| Table | Lignes |
| --- | ---: |
| `source_release` | 3 |
| `concept` | 60 928 |
| `term` | 195 396 |
| `external_identifier` | 64 976 |
| `hierarchy_edge` | 71 018 |
| `mapping` | 23 022 |
| `disease_phenotype_assertion` | 116 664 |

Le build a signalé 19 avertissements de données, notamment un concept HPO obsolète non résoluble avec certitude et 18 couples maladie–phénotype à fréquence contradictoire. Aucun de ces problèmes n'est caché ou corrigé arbitrairement.

La reconstruction depuis les sources locales et le manifeste a été vérifiée : mêmes comptes, mêmes hashes logiques et mêmes fichiers Parquet. Le fichier DuckDB sert de runtime local en lecture seule. Ses octets pouvant varier malgré des tables identiques, son hash d'intégrité est stocké dans un reçu local `integrity.json`, distinct du manifeste canonique versionné.

### Moteur clinique pur et interrogatoire — v0.3.0

Le contrat `ClinicalCase` contient :

- `case_id` ;
- `age` et `sex` facultatifs, stockés mais **ignorés** par le score actuel ;
- observations HPO avec `present`, `absent`, `unknown` ;
- historique des réponses aux questions, limité à 12, sans répétition.

Le moteur `semantic_v1` fait actuellement ceci :

1. Valide et résout les identifiants HPO, identifiants alternatifs et remplacements uniques. Les synonymes textuels sont stockés dans la base mais la CLI ne les interprète pas encore.
2. Refuse les incohérences simples, par exemple un signe enfant présent avec son parent explicitement absent.
3. Génère des candidats ORPHA ayant au moins une annotation compatible avec un signe présent, en utilisant la hiérarchie HPO.
4. Calcule un contenu informationnel à partir du corpus du snapshot.
5. Pour chaque signe présent, prend la meilleure similarité Resnik avec les annotations positives de chaque maladie ; les contributions positives sont moyennées.
6. Pénalise un signe explicitement absent uniquement si la maladie l'attend avec une fréquence exploitable. Les fréquences absentes ne deviennent jamais une absence implicite.
7. Traite les exclusions sources comme contradictions lorsqu'un signe exclu est présent.
8. Retourne les 20 premiers candidats, avec score brut, rang, contributions, contradictions, assertions, fréquences, provenance, mappings Mondo exacts, conflits de fréquence et signes importants encore inconnus.

Le score est explicitement nommé **compatibility**. Il n'est ni une probabilité, ni un posterior, ni un pourcentage diagnostique. Prévalence, âge, sexe, temporalité, facteurs de risque et résultats biologiques ne sont pas encore utilisés.

Le module `question_v1` :

- considère les dix premiers candidats ;
- exige une fréquence connue pour couvrir au moins 60 % de leur poids interne ;
- estime une réduction d'entropie pour choisir le prochain signe ;
- départage par couverture, contenu informationnel, puis identifiant HPO ;
- ne pose pas à nouveau une question déjà répondue, même avec `unknown` ;
- s'arrête après 12 questions, avec moins de deux candidats, ou sans question admissible ;
- retourne toujours `safety_status: not_evaluated`.

Les poids internes du questionnement sont uniquement un outil d'utilité : ils ne sont pas présentés comme probabilités de maladies. La méthode complète, équations et limites sont dans [docs/methodology.md](docs/methodology.md).

## Commandes disponibles maintenant

Après installation avec `uv sync --locked --python 3.11`, lancer ces commandes avec `uv run --offline --no-sync` (omettre `--offline` pour les téléchargements) ou depuis l'environnement virtuel activé :

```text
latros sources list
latros sources validate
latros sources fetch --source hpo --release 2026-09-01
latros sources fetch --source mondo --release 2026-09-01
latros sources fetch --source orphadata --release 2026-07

latros data build --snapshot v0.2.0
latros data inspect --snapshot v0.2.0

latros diagnose --snapshot v0.2.0 --case examples/case.synthetic.json
latros question next --snapshot v0.2.0 --case examples/case.synthetic.json
```

L'exemple [case.synthetic.json](examples/case.synthetic.json) est inventé. Il sert seulement à démontrer le format d'entrée. La CLI ne comprend pas encore une phrase libre telle que « j'ai mal à l'oreille » : cette future normalisation reste hors de la tranche actuelle.

## Vérifications effectuées

- 56 tests automatisés réussis localement.
- Ruff : réussi.
- mypy strict : réussi.
- Schémas Pydantic exportés et vérifiés : réussi.
- Validation du registre : réussie.
- CI GitHub Ubuntu et Windows : réussie.
- Tests réseau : les fixtures bloquent tout accès réseau ; aucune base médicale réelle n'est téléchargée en CI.
- Tests de pipeline : hashes, corruption, reprise de téléchargement, import bilingue, provenance, mappings, cycles, concepts obsolètes, snapshot partiellement présent et reconstruction.
- Tests moteur : Resnik, états présent/absent/inconnu, neutralité de `unknown`, pénalités, conflits, limites de question, non-répétition et départage déterministe.
- Test sur snapshot complet : 1 473 candidats pour le cas synthétique, retour limité aux 20 premiers, provenance présente pour les contributions, réponse `unknown` neutre et question non répétée.

## Sécurité, confidentialité et limites

- `safety_status` est systématiquement `not_evaluated` : il n'existe aucun moteur de drapeaux rouges.
- Une liste de candidats vide ne signifie pas « pas de problème médical ».
- Les résultats ne doivent pas être montrés comme un diagnostic ni utilisés pour prendre une décision de soins.
- Les tests valident le logiciel, pas la justesse médicale ni l'équité clinique.
- Les sources brutes, Parquet, DuckDB, données patient, modèles, secrets et résultats de cas restent ignorés par Git.
- Le dépôt contient seulement code, documentation, registre, schémas, manifeste et fixtures inventées.
- Les licences HPO, Mondo et Orphadata sont indépendantes de la licence du code. HPO est marqué comme restreint dans le registre ; les fichiers de données ne sont pas redistribués dans le dépôt.

## Suites possibles hors du plan initial — à discuter

Avant toute nouvelle implémentation, choisir et documenter le prochain sujet :

1. Évaluation scientifique du moteur sur des cas synthétiques puis un benchmark autorisé et indépendant.
2. Politique d'abstention, périmètre de sécurité et exigences cliniques avant toute interface patient.
3. Ajout raisonné d'HPOA, Monarch ou d'une autre source, avec stratégie de non-double-comptage.
4. Amélioration du score : corrélations entre signes, temporalité, âge, sexe, prévalence, incertitude sur les fréquences et calibrage.
5. Normalisation du texte libre et rôle futur, mesurable et remplaçable, d'un LLM local tel que MedGemma.
6. Évaluation séparée d'un LLM seul, du moteur pur et d'un système hybride.

Ne pas commencer ces chantiers simultanément : le choix le plus prudent est de valider d'abord la qualité et les limites du moteur pur sur un protocole d'évaluation écrit.

## Journal des livraisons

### 16 septembre 2026 — Première tranche et historique

- `d7ef85c` : implémentation des trois jalons du plan, avec le premier snapshot référencé `latros-kb-0002` et le paquet Python `0.3.0`.
- `0172228` : création de ce journal et explication de l'état du prototype ; aucune fonctionnalité du moteur ajoutée.
- Publication dans la pull request #1, sur `feat/clinical-foundation` ; pas de fusion automatique dans `main`.

### 16 septembre 2026 — Étape 2, référence v0.2.0 et suivi du plan

Demande : poursuivre la deuxième étape, utiliser les noms du plan pour les snapshots et actualiser les documents à chaque livraison.

Constat : les importeurs et le snapshot de l'étape 2 existaient déjà, tout comme le moteur de l'étape 3. Cette livraison établit la référence `v0.2.0` à partir des mêmes versions HPO/Mondo/Orphadata. L'ancien snapshot reste disponible et son manifeste est inchangé. Aucune nouvelle source ni fonction clinique n'est ajoutée.

Documents actualisés : README (commandes et référence actuelle), ce journal, `projet.md`, `CONTRIBUTING.md` ; ajout de `docs/plan.md` pour suivre les trois jalons et d'`AGENTS.md` pour rendre la mise à jour documentaire explicite lors des prochaines interventions.

Deux précisions de l'historique sont corrigées : MedASR a été retiré à la demande de l'utilisateur, sans évaluation de ce modèle dans cette tranche ; la CLI résout des identifiants alternatifs HPO, pas encore des synonymes saisis en texte libre.

Validation de livraison :

- Construction de `v0.2.0` par la CLI et inspection vérifiant les fichiers canoniques et le reçu d'intégrité runtime.
- Sept tables identiques à `latros-kb-0002` : mêmes sources, comptes, hashes logiques, hashes Parquet, règles et avertissements. Seul l'identifiant du snapshot diffère dans les manifestes.
- Reconstruction hors ligne depuis le manifeste épinglé et les sources locales : manifeste reconstruit strictement identique.
- Hash de contenu : `1dca4e8f69925e3f49f87c3266c2a05005423ff7b70ad0df5864f735979f7d4a`.
- 14 tests d'intégration du pipeline réussis à cette étape. La suite complète de 56 tests est également exécutée par la CI à chaque publication de la branche.
- Anciens manifestes et code du moteur inchangés ; données générées exclues de Git. Le README indique la branche à cloner tant que la pull request #1 n'est pas fusionnée.

Cette livraison complète la même tranche sur `feat/clinical-foundation`, dans la pull request #1. La publication concerne les documents et le manifeste `v0.2.0`, jamais les bases locales.

### 17 septembre 2026 — Cadrage de v0.4 Clinical Knowledge Model

Demande : préparer la prochaine évolution de Latros sans coder, conserver un suivi durable de chaque étape et confirmer que la limitation actuelle aux maladies rares n'est pas la cible définitive du projet.

Un [cahier des charges dédié](docs/v0.4-clinical-knowledge-model.md) est créé sur la branche `docs/v0.4-clinical-knowledge-model`. Il décrit les invariants, le futur modèle clinique, le Knowledge Model, la provenance, le non-double-comptage, l'architecture multi-stratégies, les tests, les critères d'acceptation et les checkpoints `v0.4-A` à `v0.4-H`.

Décision de périmètre : le snapshot `v0.2.0` et `semantic_v1` restent spécialisés maladies rares. Ils ne couvrent pas correctement une plainte courante comme fièvre et mal de gorge. `v0.4` doit préparer l'architecture générale sans import massif ; `v0.5` doit réaliser une première extension étroite vers la médecine générale avec des sources auditées et une stratégie dédiée. Les futurs référentiels ne seront sélectionnés qu'après analyse de leur rôle, licence, provenance, dépendances et risque de double comptage.

Cette livraison est uniquement documentaire : aucun code, schéma, test, manifeste ou snapshot de données n'est modifié. Le socle actuel et la référence `v0.2.0` restent inchangés.

### 17 septembre 2026 — Première veille des ressources de médecine générale

Une liste proposée par un autre LLM est vérifiée avant d'être ajoutée au plan. Le cahier des charges distingue désormais les terminologies, classifications, mappings, standards d'échange, assertions cliniques, recommandations, cas synthétiques, données réelles restreintes et applications complètes.

Corrections importantes : SNOMED CT est une terminologie clinique et non une matrice de probabilités ; les mappings SNOMED–ICD servent à la classification et au reporting, pas à déduire une maladie depuis un symptôme ; FHIR est un standard d'échange ; HealthBench contient des conversations réalistes générées ou adversariales et non 5 000 conversations de patients réels ; ClinicDx est une application LLM/RAG à surveiller, pas une base de connaissances validée.

Les jeux Kaggle « Symptoms to diseases », Mendeley « Disease and symptoms dataset 2023 » et SymbiPredict sont conservés comme pistes d'exploration uniquement. Leur format et leur licence déclarée ne compensent pas une provenance médicale insuffisante. DDXPlus est mieux documenté et peut devenir un benchmark synthétique de `v0.5`, mais pas la vérité clinique du moteur. Synthea, WHO SMART Guidelines, LOINC/UCUM, MIMIC-IV et les autres ressources sont répartis entre les étapes `v0.5` à `v0.9` selon leur rôle.

Cette veille ne télécharge et n'intègre aucune donnée. Toute adoption future exige un audit record par record de la provenance, des licences, des dépendances, des biais et de l'indépendance de l'évaluation.

### 17 septembre 2026 — Décision d'agrégation multi-sources

Le cahier des charges prévoit désormais une vue détaillée par source et un agrégat global. Une moyenne simple est exclue : les scores hétérogènes ne sont pas directement comparables, une source absente reste neutre et les republications d'une même preuve sont regroupées avant agrégation. Les poids devront être versionnés, justifiés par domaine et validés avec des tests d'ablation sur un corpus indépendant.

Les résultats resteront des compatibilités tant qu'ils ne seront pas calibrés pour une population clinique définie et validés sur un jeu externe. Aucun score non calibré ne devra être affiché comme pourcentage ou probabilité diagnostique. Cette décision est uniquement documentaire ; aucun moteur ou snapshot n'est modifié.

### 17 septembre 2026 — Intégration de l'agrégation au contrat des snapshots

Le cahier des charges impose désormais que tout futur manifeste publie le périmètre clinique, les dépendances entre sources, les familles de preuves non indépendantes, les règles de normalisation et de déduplication ainsi que les stratégies et profils d'agrégation compatibles. Chaque exécution devra conserver les hash du snapshot et du profil de raisonnement afin de reproduire le score global et les contributions par source.

Une modification de la connaissance imposera un nouvel identifiant de snapshot. Une modification limitée au moteur, aux poids ou à la calibration conservera éventuellement le snapshot mais recevra une nouvelle version de profil. Le manifeste `v0.2.0` reste immuable et n'est pas migré rétroactivement. Aucun code, donnée ou snapshot n'est modifié dans cette livraison documentaire.

### 17 septembre 2026 — v0.4-B, frontières et non-régression

Le cadrage v0.4 est approuvé. Les ADR 0002, 0003 et 0004 fixent respectivement les contrats
cliniques v2, le Knowledge Model canonique et la séparation entre stratégies, profils, snapshots
et reçus d'exécution. Deux tests d'or vérifient l'égalité octet par octet des sorties complètes de
`semantic_v1` et `question_v1` sur les fixtures inventées.

Cette livraison n'ajoute encore aucun contrat runtime v2 et ne change aucun résultat clinique. Le
snapshot `v0.2.0`, son manifeste, les sept tables et les formats publics v1 restent inchangés.

### 17 septembre 2026 — v0.4-C, ClinicalCaseV2 et migration

Le contrat historique devient explicitement `ClinicalCaseV1` tout en conservant l'alias public
`ClinicalCase`. Le nouveau `ClinicalCaseV2` est versionné et sépare le texte source, les propositions
d'extraction non utilisables pour scorer, les observations confirmées et les réponses aux questions.
Il couvre les onze catégories cliniques prévues, des valeurs typées, la temporalité, les unités, la
sévérité, la localisation, la latéralité, le sujet, l'acquisition, la provenance et les corrections.

Les combinaisons incohérentes d'état clinique et d'évaluation sont refusées. Une impossibilité
d'évaluation est représentée par `unknown + unable_to_assess`. Une correction contradictoire doit
référencer explicitement l'observation remplacée. Toute origine non directement déclarative exige
une référence traçable.

Un chargeur distingue v1 sans `schema_version`, v2 explicite et versions inconnues refusées. La
migration HPO v1 → v2 est déterministe et idempotente. Le schéma JSON v2 est versionné. Quatorze
tests dédiés portent la suite à 72 tests verts ; Ruff, formatage, mypy strict et export des schémas
sont également verts. La CLI, `semantic_v1`, les sorties v1 et le snapshot `v0.2.0` restent
fonctionnellement inchangés.

### 17 septembre 2026 — v0.4-D, Knowledge Model et projection v1

Le Knowledge Model v2 introduit des contrats séparés pour les releases et artefacts sources, les
records bruts, les concepts et terminologies, les mappings, les assertions sources et canoniques,
leurs dérivations, les familles de preuves et les dépendances. Un mapping, même exact, reste un
objet terminologique et ne produit jamais implicitement une assertion diagnostique.

Les identités sources incluent la release, les hashes d'artefacts, le localisateur du record et son
ordinal. L'identité canonique exclut libellés et provenance pour permettre une déduplication
auditée. Les doublons sources sont conservés, mais une signature canonique identique issue de la
même source partage une famille de preuve. Une dépendance inconnue empêche l'agrégation par défaut.

L'adaptateur du snapshot v1 expose HPO/Mondo/Orphadata sous ces contrats sans réécrire ses sept
tables. Les provenances EN/FR deviennent deux artefacts d'une seule assertion source. Les schémas
`knowledge-model-v2.schema.json` et `canonical-tables-v2.json` sont versionnés. Six tests dédiés
portent la suite à 78 tests verts. Aucun snapshot médical v2 n'est publié et `v0.2.0` reste intact.

### 17 septembre 2026 — v0.4-E, stratégies et compatibilité semantic_v1

Quatre protocoles séparent désormais génération de candidats, scoring, sélection de questions et
construction d'explications. Leur descripteur rend explicites les capacités, contrats acceptés,
relations utilisées, nature du score et séparation du futur moteur de sécurité. Le profil
`semantic_v1-default` est versionné, hashé et compatible avec les manifests de schéma v1.

L'adaptateur `SemanticV1Adapter` appelle directement le moteur et la sélection de questions
historiques. Sa projection depuis `ClinicalCaseV2` n'utilise que les observations HPO confirmées,
actives et non remplacées ; elle rapporte les types ou terminologies ignorés et ne lit jamais les
propositions d'extraction. Des observations temporelles actives multiples pour le même concept sont
refusées plutôt que fusionnées.

Les sorties du cas v1 et de sa migration v2 sont strictement identiques dans les tests. Six tests
supplémentaires portent la suite à 84 tests verts, sans modification de `Engine.rank`,
`Engine.diagnose`, `question_v1`, des formats CLI v1 ou du snapshot `v0.2.0`.

### 17 septembre 2026 — v0.4-F, résultats explicables et reçus

Les résultats v2 distinguent désormais classement, abstention et périmètre. La couverture compte
les observations confirmées supportées, rend chaque donnée ignorée visible et ne traite jamais une
proposition comme observation. Les candidats exposent leurs contributions favorables,
défavorables et inconnues, leurs assertions et provenances, ainsi que les sous-totaux par source et
famille de preuve. Le score conserve le nom `semantic_v1.compatibility`, non calibré.

Les questions v2 publient leur justification, gain heuristique attendu, couverture, sources et
assertions. La réponse d'interface `unable_to_assess` est explicitement permise et correspond à
`unknown + unable_to_assess` dans le cas clinique. Le statut du moteur de sécurité reste séparé et
fixé à `not_evaluated`.

Chaque exécution v2 inclut un reçu déterministe avec empreinte du cas, hashes du manifeste et du
contenu de connaissance, profil et paramètres, sources ou familles réellement utilisées, mappings,
transformations et version logicielle. La CLI choisit automatiquement la sortie historique pour
v1 et la sortie v2 pour un cas v2 ; des options explicites permettent de forcer le contrat. Huit
tests supplémentaires portent la suite à 92 tests verts. Aucun reçu n'est persisté, aucun manifeste
historique ou calcul de `semantic_v1` n'est modifié.

### 17 septembre 2026 — v0.4-G, audit des sources ORL de v0.5

L'audit officiel de SNOMED CT France et de la fiche HAS sur l'angine aiguë adulte est consigné dans
`docs/source-audits/v0.5-orl.md`. L'édition nationale française de juin 2026 est confirmée comme
terminologie candidate, mais son téléchargement et son implémentation exigent affiliation et
licence nationale. La redistribution d'alignements ou dérivés et le modèle de sous-licence de
Latros doivent être clarifiés avec le NRC.

La fiche HAS contient un premier ensemble structurable, mais elle a été élaborée avec plusieurs
organisations tierces. Les mentions légales excluent de la réutilisation libre les contenus grevés
de droits tiers. Une autorisation écrite, une curation atomique et deux relectures dont une clinique
sont donc des prérequis. DDXPlus est maintenu comme benchmark synthétique éventuel uniquement.

La décision `v0.5` est un `NO-GO` temporaire pour les données réelles. Des fixtures et importeurs
synthétiques peuvent être préparés, mais aucun snapshot ou score de médecine générale ne doit être
publié avant levée de toutes les conditions. Aucun téléchargement, ingestion, manifeste ou snapshot
n'a été créé pendant cet audit.

### 17 septembre 2026 — v0.4-H, clôture de Clinical Knowledge Model

La version du paquet passe à `0.4.0`. Le profil de raisonnement versionné est inclus dans la
distribution Python et reste contrôlé par son hash. La revue finale vérifie la suite complète, les
tests d'or v1, Ruff, le formatage, mypy strict, les schémas exportés et la construction du paquet.

Les checkpoints A à H sont terminés. Le snapshot et le manifeste `v0.2.0` restent immuables ; aucun
snapshot médical v2 n'est publié. La maquette, le logo local non suivi, les données sources, les
artefacts générés et toute donnée patient restent hors de la branche. La prochaine ingestion réelle
reste bloquée par le `NO-GO` v0.5 documenté ; seules les fixtures synthétiques ou la levée formelle
des conditions de licence et de revue sont autorisées.
