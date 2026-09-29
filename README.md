# Latros

<p align="center">
  <img src="docs/assets/latros-logo.svg" alt="Latros" width="420">
</p>

Prototype **interne de recherche** pour explorer des raisonnements cliniques structurés. Les moteurs
sont locaux et explicables, sans LLM. L'interface web propose désormais un parcours simple et
conserve la console R&D en mode expert. Elle n'est pas une interface patient validée.

L'[audit documentaire d'extension généraliste](docs/reports/general-medicine-source-expansion.md)
compare des distributions officielles et leurs droits avant toute ingestion. Il ne télécharge
ni n'ajoute aucune source médicale, ne change aucun snapshot et ne constitue pas une validation
clinique. Les permissions et la revue humaine restent des préalables.

Le mode simple v4 expérimental commence par un profil de session local (nom ou pseudonyme, âge),
puis Symptômes → Précisions/Questions → Résultats. Seul l'âge rejoint le cas moteur ; les
antécédents/allergies facultatifs ne sont pas interprétés. Un symptôme sélectionné est ajouté
`present` en un clic. L'atlas local compte 47 vues et 37 illustrations (30 nouvelles hors tête),
avec zones SVG séparées et survol lié aux boutons de région. Images générées, non validées
anatomiquement. Voir [rapport produit](docs/reports/ui-v4-product-flow.md),
[rapport atlas](docs/reports/ui-atlas-v4.md), [audit des questions](docs/reports/ui-v4-question-quality.md)
et [documentation UI](docs/modern-ui.md).

Le parcours simple propose désormais **FR / DE / EN**, mémorisés localement. La recherche
accepte synonymes, accents, préfixes et un lexique grand public versionné (160 concepts avec
affichage FR/DE activé sur les 11 671 observations recherchables du snapshot local). Les traductions/désignations sont uniquement
de l'affichage ; les termes non traduits restent signalés **EN** et les IDs/reçus sont inchangés.
Voir le [rapport multilingue](docs/reports/ui-i18n-local-search.md). Aucun service de traduction,
NLP ou nouvelle connaissance médicale n'est introduit.

La [recherche locale v2](docs/reports/ui-search-v2.md) utilise un index BM25 temporaire et un
fuzzy borné sur les alias explicites : benchmark offline 63/63 cibles préparées au top 1 et
aucune suggestion pour 15 formulations négatives. Ce jeu recoupe les alias ajoutés ; il ne
mesure pas encore le rappel d'utilisateurs indépendants. Aucun embedding ni service externe.

Le mode simple offre une navigation **Corps → Tête → Sinus** et d'autres régions, 37 illustrations locales générées
avec overlays SVG indépendants et 47 vues (oreille, thorax, abdomen, urinaire et membres inclus),
une recherche permanente et un thème clair/sombre. Les observations d'une région sont résolues
contre le snapshot actif avant affichage. Les autres régions disposent désormais de planches
dédiées. Les images ne sont pas anatomiquement validées. Carte et recherche ajoutent la même
observation, une seule fois, avec état présent initialement, puis modifiable en absent/inconnu.
`/expert` reste la console R&D complète. Voir le
[rapport anatomique et audit de couverture](docs/reports/ui-anatomy-vnext.md) et
la [documentation UI](docs/modern-ui.md).

Voir le [rapport atlas v3](docs/reports/ui-atlas-v3.md) et l'[ADR 0018](docs/decisions/0018-illustrations-locales-et-overlays.md)
pour les hashes/provenance des images, les mesures et le lexique `ui-display-3`.
Les 80 nouvelles traductions sont des propositions UX éditoriales, non relues humainement.
Pour préparer une vraie revue linguistique locale (11 671 lignes, décisions vides) :

```text
uv run --offline --no-sync python scripts/export_ui_translation_review.py --output-dir data/staging/ui-atlas-translation-review
```

Le questionnaire General-first / Rare-second et les illustrations ont été développés dans
deux PR distinctes ([#19](https://github.com/GaetanAff/Latros/pull/19) et
[#20](https://github.com/GaetanAff/Latros/pull/20)), puis intégrés ensemble. Lancer depuis
`main` synchronisé permet de conserver et relire les sessions du nouveau parcours ; une
ancienne branche UI seule ne reconnaît pas leur champ `consultation`.
Les liens JS/CSS sont versionnés par leur contenu pour éviter de réutiliser une ancienne UI
en cache après la mise à jour ; recharger la page ne supprime pas les sessions locales.

> **Aucun triage n'est effectué.** Toutes les analyses retournent `safety_status: not_evaluated`. Les scores sont des compatibilités sémantiques, jamais des probabilités ou des diagnostics validés. Ne pas utiliser ce prototype pour conseiller un patient.

La version `0.6.0` ajoute une interface locale et des sessions reprenables au Clinical Knowledge
Model, sans modifier les moteurs. Les contrats cliniques et de connaissances, stratégies
versionnées, couverture, abstention, sorties explicables et reçus reproductibles restent la source
de vérité. Voir le [journal des ADR](docs/decisions/README.md), la
[méthodologie](docs/methodology.md) et [vision du projet](docs/projet.md).

Le [plan et son avancement](docs/plan.md) distingue fondation `v0.1.0`, premier snapshot médical `v0.2.0`, moteur pur `v0.3.0` et modèle général `v0.4.0`. Le snapshot de référence reste **`v0.2.0`** : v0.4 est une évolution logicielle et contractuelle, pas une nouvelle publication de données. Le [journal du projet](docs/history.md) conserve les réalisations et vérifications datées.

Pour installer, lancer l'interface et réaliser deux essais guidés, suivre le
**[tutoriel complet](docs/tuto.md)**. L'[index de la documentation](docs/README.md) explique où se
trouvent ensuite la roadmap, les ADR, les audits et les contrats.

> **Périmètre critique : la seule référence médicale publiée reste maladies rares.** Le snapshot
> officiel `v0.2.0` ne couvre pas la médecine générale. Le snapshot ORL
> `v0.5.0-dev-unreviewed` décrit ci-dessous est uniquement un outil local d'ingénierie, non relu et
> non validé cliniquement ; il ne doit jamais être utilisé comme différentiel clinique.

Les futurs snapshots multi-sources devront publier leur périmètre, leurs dépendances, leurs règles de déduplication et leurs profils de raisonnement compatibles. Le snapshot de connaissance et le profil d'agrégation seront versionnés séparément puis liés par leurs hashes dans chaque exécution ; `v0.2.0` reste immuable.

`v0.6` a livré l'interface interne de test R&D : elle saisit un `ClinicalCaseV2`, exécute
les moteurs déjà disponibles et inspecte leurs résultats, sources, contradictions, couverture et
statuts de validation. Elle n'est ni une interface patient, ni un produit médical validé, ni une
nouvelle logique clinique. Son implémentation autonome et versionnée se trouve sous
`src/latros/ui/`. L'ancienne maquette locale ayant servi d'inspiration a été supprimée après la
livraison ; aucun composant actif n'en dépend. Une vue Knowledge Graph avancée reste planifiée
comme projection interactive et fidèle des données, assertions, sources et contributions
existantes.

La trajectoire `v0.7` inclut explicitement les médicaments : exposition observée, substance active,
produit commercialisé, classe thérapeutique et assertions médicales sourcées resteront des objets
distincts. Cette préparation ne constitue ni une recommandation de traitement, ni une fonction de
prescription ; le détail est consigné dans le [cahier v0.4](docs/v0.4-clinical-knowledge-model.md).

La fabrique `v0.7` suit
[fabrique généraliste souveraine](docs/decisions/0009-fabrique-souveraine-generaliste.md). Une source
n'entre dans le pipeline que sous forme de distribution locale épinglée et vérifiée par SHA-256 ;
seule la commande explicite `sources fetch` peut utiliser Internet. MedlinePlus Health Topics XML,
MeSH XML et une release locale Monarch constituent maintenant, avec HPO, Mondo, DOID et Orphadata,
le premier snapshot `v0.7.0-general-dev-unreviewed`. Il est local, reproductible et consommable par
`general_v1`, mais reste une base de recherche **non relue, non validée et non publiable**. CDC est
différé tant qu'aucun export généraliste officiel adapté n'est disponible. Voir l'[audit des
distributions](docs/source-audits/v0.7-sovereign-general.md) et le [rapport de
couverture](docs/reports/v0.7-general-coverage.md).

Le durcissement technique `v0.7-F2` lit désormais le DuckDB v2 par requêtes ciblées pour
`general_v1` et la recherche de concepts de l'interface. Il ne change ni le snapshot, ni le
profil, ni la mathématique du score. Les sept diagnostics et questions synthétiques du vrai
snapshot sont comparés octet pour octet aux sorties précédentes ; voir le
[rapport de performance](docs/reports/v0.7-runtime-performance.md).
Le durcissement `v0.7-F3` réduit ensuite le diagnostic réel après question de 292 à 15,6 s
sur le grand cas fictif mesuré, sans changer les sorties ni le snapshot. Le transport complet
de 3 650 candidats reste à 23,6 s : voir le [rapport F3](docs/reports/v0.7-f3-runtime-latency.md).
`v0.7-F4` conserve ensuite ce résultat complet et immuable sur disque, mais la vue simple
reçoit une projection de 20 candidats au maximum et charge le détail au clic. Sur le grand
cas fictif, la réponse initiale passe d'environ 206 Mo à 14 Ko et la route de 22,9 à 18,5 s ;
le calcul et l'écriture du run restent le goulet principal. Voir le
[rapport F4](docs/reports/v0.7-f4-result-transport.md).
Le profilage `v0.7-F5` montre que l'écriture du run entier prend ~0,35 s sur le grand cas,
contre ~11,7 s pour l'extraction des lignes candidates. Latros conserve donc le format F4 et
réutilise des tables temporaires DuckDB de lecture : la route mesurée passe de 19,1 à 12,7 s
sur le même protocole, et de 5,7 à 4,3 s pour le cas respiratoire. Les sorties d'or restent
identiques ; voir le [rapport F5](docs/reports/v0.7-f5-run-persistence.md).
`v0.7-F6` réduit ensuite la matérialisation Python des assertions nécessaires au scoring,
sans changer le run complet ni sa provenance. Sur le grand cas fictif du même protocole,
la route passe de 12,54 à 9,50 s et le pic RSS de 3,15 à 2,86 Go ; voir le
[rapport F6](docs/reports/v0.7-f6-evidence-materialization.md).
Le durcissement runtime v0.7 s'arrête ici, sauf régression importante. La passe technique
[`v0.7-G4`](docs/reports/v0.7-g4-medlineplus-extraction-quality.md) rejoue l'extraction
MedlinePlus depuis le ZIP local épinglé et produit un **jeu candidat expérimental** filtré par
contexte lexical, avec journal d'exclusions et nouveau G2. Elle ne modifie pas le snapshot,
`general_v1` ni les statuts médicaux ; aucune assertion n'est approuvée automatiquement.

L'audit préparatoire `v0.7-G0`, vérifié et accepté sur le plan technique/méthodologique,
mesure la composition réelle du corpus sans valider ses assertions :
14 661 des 15 611 maladies documentées ont un lien structurel Orphanet ou génétique, tandis que
la prévalence et la couverture de la médecine courante demeurent inconnues. Les limites de
MedlinePlus, les dépendances Monarch et l'échantillon de revue sont détaillés dans le
[rapport de qualité](docs/reports/v0.7-general-quality-audit.md). `v0.7-G` reste à faire.

Les jeux de travail [`v0.7-G1/G2`](docs/reports/v0.7-g-targeted-review.md) et leur dispositif
de revue sont vérifiés et prêts sur le plan technique/méthodologique. Ils préparent une revue
humaine ciblée des mappings MedlinePlus, assertions et dépendances de provenance, mais ne valident
aucune assertion ; le protocole G3 est défini, sans évaluation indépendante réalisée. Un
[outil séparé de revue locale](docs/v0.7-g-review-ui.md) permet de parcourir les trois exports et
de journaliser des décisions humaines sans modifier le snapshot. Après l'export des jeux, lancer
`uv run --offline --no-sync python scripts/run_v07_g_review.py` puis ouvrir
`http://127.0.0.1:8765/`. Aucune décision médicale n'est fournie ou préremplie par l'outil.

Le workflow [`v0.7-G5`](docs/reports/v0.7-g5-human-adjudication.md) ajoute les 7 736 candidates
G4, leur contexte source et l'avant/après technique. Il sépare catégorie, décision humaine,
double revue et adjudication ; 180 rejets et 180 retenues sont préparés pour contrôle humain.
Après génération des exports G1/G2 et G4 :

```text
uv run --offline --no-sync python scripts/prepare_v07_g5_adjudication.py
uv run --offline --no-sync python scripts/run_v07_g_review.py --adjudication
```

Les six exports de revue et le journal hashé restent locaux sous `data/staging/v0.7-g5/`.
`retained`, accord ou adjudication ne promeuvent rien dans le snapshot. Il faut encore organiser
de vraies revues qualifiées G1/G2 et une évaluation indépendante G3.

`v0.5` reste historiquement incomplet sur `main`. Ses checkpoints techniques A à D définissent le registre,
le manifeste, le constructeur, les importeurs et le premier raisonneur général. Le paquet ORL réel
reste intégralement `pending_clinical_review`. Un chemin séparé permet désormais de l'importer et de
le scorer localement sous l'identité non ambiguë `v0.5.0-dev-unreviewed`, uniquement après override
explicite. Cela ne crée pas `v0.5.0`, ne change aucun statut de revue et ne clôt ni F ni G.

Le constructeur v2 produit les treize tables canoniques, leurs Parquet déterministes et un runtime
DuckDB en lecture seule. La CI le vérifie sur un mini-corpus fictif nommé `test-v2` ; le corpus réel
pending peut aussi être construit localement dans le mode non validé, sans redistribuer ses captures.

Le registre v2 peut décrire un sous-ensemble RF2 et un paquet JSONL d'assertions curées. Les sources
protégées utilisent `manual_local` : l'opérateur acquiert le fichier sous sa licence, puis Latros
vérifie son emplacement et son hash sans stocker de secret. La CLI détecte automatiquement les
registres et manifestes v1 ou v2. Aucun registre SNOMED/HAS réel n'est encore versionné.

Le registre v2 exige maintenant, pour tout nouveau build, producteur, rôle fermé, release ou identité
de capture, date, URL, hash, format, licence, droits de transformation/redistribution, restrictions
et importeur. Les anciens manifestes restent lisibles. Le nouveau
[contrat de candidate assertion](schemas/candidate-assertion-v1.schema.json) conserve extraction,
mappings proposés, temporalité, contexte, quantité/unité, famille de preuve, groupe de dépendance,
review status et chaîne de transformation sans modifier les tables canoniques publiées.
Le [contrat de topic MedlinePlus](schemas/medlineplus-topic-record-v1.schema.json) conserve les
identifiants MeSH et les locators avant toute extraction.

`general_v1` classe les conditions déclarées par un snapshot v2 à partir d'assertions explicites,
normalise d'abord les contributions au niveau des familles de preuves et publie une compatibilité
comprise entre `-1` et `1`. Cette valeur n'est jamais une probabilité. Le moteur refuse les cas sans
âge adulte exploitable, à couverture insuffisante ou avec moins de deux observations évaluées. Il
ignore numériquement `unknown`, `not_assessed` et `unable_to_assess`, expose les sources séparément
et ne propose une question que si des polarités opposées distinguent réellement plusieurs candidats.
Le profil par défaut reste destiné au corpus fictif `test-v2`. Le profil
[`general_v1-orl-unreviewed`](profiles/general_v1-orl-unreviewed.json) est lié exclusivement au
snapshot de développement : son poids NHS est un choix d'ingénierie non validé, et les dépendances
NLM inconnues restent exclues de l'agrégat. Un profil clinique de référence attend toujours le `GO`.

## Interface locale R&D — v0.6

Construire d'abord les snapshots locaux nécessaires, puis lancer :

```powershell
uv run --offline --no-sync latros --root . ui
```

Latros ouvre `http://127.0.0.1:8765/`. Cette page est maintenant le parcours simple de recherche
locale ; la console R&D complète reste à `http://127.0.0.1:8765/expert`. Le port peut être changé et l'ouverture automatique
désactivée :

```powershell
uv run --offline --no-sync latros --root . ui --port 8766 --no-open
```

Le parcours simple privilégie désormais `v0.7.0-general-dev-unreviewed + general_question_v2` :
profil **expérimental mono-source MedlinePlus G4**, non validé/non publiable, distinct de
`general_v1` dont l'exclusion `unknown` reste inchangée. Après les résultats généraux, un clic
explicite permet `rare_question_v1`, même cas, résultats et compteurs séparés. Budgets logiciels
6 / 12, sans valeur médicale validée. Rejouer le JSONL G4 épinglé offline avant usage ; voir le
[rapport General/Rare](docs/reports/general-first-rare-second.md) et l'[ADR 0017](docs/decisions/0017-consultations-generale-et-rare-versionnees.md).
Il guide des informations patient vers la sélection explicite de symptômes, les questions
fournies par le backend, les résultats non probabilistes et leurs détails facultatifs. Une
description libre facultative peut maintenant produire des **propositions** via Qwen3.5 local ;
le patient doit les confirmer avant qu'elles deviennent des observations. Le modèle ne pose pas
de diagnostic et son extraction n'est pas cliniquement validée.
Après les premiers résultats généraux, « Vérifier ces possibilités » est une étape facultative :
au plus six questions **au total** sur les éléments non évalués des cinq premières hypothèses.
Le résultat initial reste visible sans répondre. Une réponse produit ensuite un nouveau run,
sans altérer le premier ; les contradictions ne sont montrées qu'après évaluation réelle et ne
sont ni exclusion absolue ni probabilité. La phase rare reste distincte. Voir
[ADR 0021](docs/decisions/0021-verification-facultative-des-resultats.md).
Un snapshot absent est signalé ; les libellés du catalogue local peuvent être en anglais. Voir
[la documentation du parcours simple](docs/modern-ui.md) et [l'ADR 0011](docs/decisions/0011-parcours-simple-local.md).

Le GGUF Qwen et `llama-server.exe` restent hors du dépôt. Sur cette machine, Latros détecte
les chemins locaux connus ; ailleurs, définir `LATROS_LLAMA_SERVER` et `LATROS_QWEN_MODEL`.
Le serveur est lancé à la demande sur `127.0.0.1` sans réseau extérieur ; en cas d'absence du
modèle, la recherche et l'anatomie continuent. Le texte sensible est conservé dans `sessions/`
non chiffré et ignoré par Git. Voir [ADR 0020](docs/decisions/0020-interpretation-locale-des-symptomes.md).

La console experte permet uniquement les couples compatibles, notamment `v0.2.0 + semantic_v1` et
`v0.5.0-dev-unreviewed + general_v1` ainsi que
`v0.7.0-general-dev-unreviewed + general_v1`. Elle crée un `ClinicalCaseV2`, recherche les concepts
réellement présents dans le snapshot, conserve les cinq situations d'évaluation, lance le backend
et affiche candidats, compatibilité brute, couverture, abstention, contributions, contradictions,
sources, familles, mappings, provenance et reçu.

Les sessions sont sauvegardées sous `sessions/<session_id>/`. L'état courant est dans
`session.json`; chaque analyse et question est conservée comme run immuable avec une copie exacte du
cas et du résultat. Ce dossier est ignoré par Git. Il n'est ni chiffré ni adapté aux dossiers
médicaux réels.

Le snapshot expérimental garde un panneau impossible à masquer avec
`research_unreviewed: true`, `clinical_validation: false`, `publishable: false` et ses comptes
pending. `safety_status: not_evaluated` reste affiché et ne constitue aucune conclusion de
sécurité. Le serveur écoute uniquement sur la boucle locale, ne contient ni télémétrie, ni CDN, ni
appel externe. Le détail est dans [la documentation v0.6](docs/v0.6-rd-interface.md) et
[l'ADR 0008](docs/decisions/0008-interface-locale-rd-et-sessions.md).
Le parcours complet, écran par écran, est disponible dans le [tutoriel](docs/tuto.md).

`v0.4-D` fournit désormais le [schéma canonique v2](schemas/knowledge-model-v2.schema.json) et
la liste de ses [tables conceptuelles](schemas/canonical-tables-v2.json). L'adaptateur v1 est une
projection en lecture seule : il distingue enregistrements sources, assertions canoniques et
dérivations, conserve chaque provenance bilingue et ne transforme jamais un mapping en preuve
clinique. Les répétitions sémantiques restent auditables comme lignes sources mais partagent une
famille de preuve ; elles ne deviennent donc pas plusieurs confirmations indépendantes. Ces
contrats sont validés sur fixtures inventées et ne constituent pas un nouveau snapshot médical.

`v0.4-E` ajoute des interfaces séparées pour génération de candidats, scoring, questionnement et
explication, ainsi qu'un [profil `semantic_v1` hashé](profiles/semantic_v1.json). L'adaptateur v2
n'extrait que les observations HPO confirmées et actives ; les propositions et types non supportés
ne participent jamais au score. Le calcul historique n'a pas été déplacé : l'adaptateur appelle
toujours `Engine` et `question_v1`, dont les sorties v1 restent protégées par les tests d'or.

L'[audit des sources ORL de v0.5](docs/source-audits/v0.5-orl.md) conclut à un `NO-GO`
temporaire pour toute ingestion réelle : SNOMED France exige les licences adaptées et le modèle de
redistribution doit être clarifié ; la fiche HAS coélaborée avec des tiers exige une autorisation
écrite et une double revue clinique. Le contrôle final ajoute qu'un corpus doit couvrir les quatre
candidats avec au moins deux assertions diagnostiques explicites et une assertion discriminante par
candidat ; ce minimum n'est pas démontré. Aucun dataset moins fiable ne le remplace automatiquement.

L'[audit alternatif v0.5-E2](docs/source-audits/v0.5-orl-open-sources.md) conserve ce résultat
historique mais ne fait plus dépendre le pilote de SNOMED/HAS. DOID et Mondo peuvent préparer les
identités ; des pages NHS/nidirect et certaines synthèses publiques MedlinePlus fournissent les
assertions proposées. Le paquet [`curation/v0.5-orl`](curation/v0.5-orl/README.md) contient 17
assertions et 10 mappings avec artefacts, empreintes et provenance vérifiés. Les quatre candidats
atteignent le seuil technique, mais toutes les lignes sont encore `pending_review` : le gate
retourne `ready_for_human_review` et bloque publication, export, profil ORL final et snapshot.
CDC reste hors du paquet tant que la redistribution internationale n'est pas clarifiée. MeSH,
les articles A.D.A.M. et les sources sans droit de transformation sont exclus.

Le [dossier de revue](docs/reviews/v0.5-orl/README.md) expose chaque assertion, mapping, famille et
blocage. Les commandes suivantes ne créent aucune approbation :

```text
uv run --offline --no-sync latros curation review-workbook --package curation/v0.5-orl
uv run --offline --no-sync latros curation audit --package curation/v0.5-orl
uv run --offline --no-sync latros curation audit --package curation/v0.5-orl --require-publishable
```

La troisième commande doit échouer jusqu'à présence de deux revues attestées par assertion, dont
une par un clinicien compétent, ainsi que la revue des mappings.

### Deux chemins v0.5 strictement séparés

Le chemin de recherche locale doit être activé volontairement :

```text
uv run --offline --no-sync latros data build --snapshot v0.5.0-dev-unreviewed --allow-unreviewed-research-data
uv run --offline --no-sync latros data inspect --snapshot v0.5.0-dev-unreviewed
uv run --offline --no-sync latros diagnose --snapshot v0.5.0-dev-unreviewed --strategy general_v1 --case examples/case.orl-unreviewed.json
uv run --offline --no-sync latros question next --snapshot v0.5.0-dev-unreviewed --strategy general_v1 --case examples/case.orl-unreviewed.json
```

Les douze artefacts épinglés doivent déjà être présents localement aux chemins consignés dans le
paquet. Sans le flag, le build est refusé. Le flag est lui-même refusé pour tout identifiant qui ne
se termine pas par `-dev-unreviewed`, en particulier `v0.5.0`. Le
[manifeste expérimental](manifests/v0.5.0-dev-unreviewed.json) porte
`validation_status: unreviewed`, `intended_use: local_research_only`, `publishable: false`, les 17
assertions et 10 mappings pending ainsi que `reviewer_count: 0`. Chaque résultat et reçu répète ce
statut avec `research_unreviewed: true`; `general_v1.compatibility` reste une compatibilité et
`safety.status` reste `not_evaluated`.

Le chemin officiel demeure inchangé :

```text
uv run --offline --no-sync latros data build --snapshot v0.5.0
```

Cette commande échoue sur le gate de publication jusqu'aux vraies validations humaines prévues.

## Installation

Prérequis : Git, Python 3.11 et [uv](https://docs.astral.sh/uv/getting-started/installation/) (version utilisée en CI : `0.12.15`). L'installation initiale des dépendances et le téléchargement des sources nécessitent Internet. Ces commandes s'exécutent depuis la racine du dépôt sous PowerShell ou un shell Unix.

```text
git clone https://github.com/GaetanAff/Latros.git
cd Latros
uv sync --locked --python 3.11
uv run --no-sync latros --help
uv run --no-sync latros sources validate
```

Le dépôt est privé : Git doit disposer de votre authentification GitHub. `v0.6` est déjà fusionnée
dans `main` ; le travail `v0.7` est développé sur une branche avant revue de sa pull request.
`uv.lock` fixe les dépendances ; ne pas le mettre à jour pour reconstruire un snapshot historique.
Pour récupérer les évolutions : `git pull --ff-only`, puis `uv sync --locked`.

## Télécharger les sources épinglées

Consulter les conditions de chaque produit dans [sources/registry.yaml](sources/registry.yaml). Une licence d'ontologie ne couvre pas nécessairement les annotations d'une autre source. HPOA et les annotations OMIM ne sont pas importées.

```text
uv run --no-sync latros sources list
uv run --no-sync latros sources fetch --source hpo --release 2026-09-01
uv run --no-sync latros sources fetch --source mondo --release 2026-09-01
uv run --no-sync latros sources fetch --source orphadata --release 2026-07
```

Le registre fournit versions, URLs officielles, produits, attributions, restrictions et SHA-256 attendus. Aucun lien `latest`. Les fichiers aboutissent à `data/raw/<source>/<release>/`, avec un manifeste local. Les fichiers complets déjà vérifiés sont réutilisés. Après interruption, relancer la commande : le fichier `.part` repart de zéro, sans retélécharger les autres fichiers valides. Un hash incorrect ou un fichier existant corrompu provoque un refus, sans écrasement du fichier complet.

Le registre généraliste est séparé et s'utilise explicitement :

```text
uv run --no-sync latros --registry sources/registry-general-v0.7.yaml sources validate
uv run --no-sync latros --registry sources/registry-general-v0.7.yaml sources fetch --source medlineplus --release 2026-09-19
uv run --no-sync latros --registry sources/registry-general-v0.7.yaml sources fetch --source mesh --release 2026
uv run --no-sync latros --registry sources/registry-general-v0.7.yaml sources fetch --source monarch --release 2026-09-02
```

Après acquisition de ses sept sources, le build et le runtime ne nécessitent plus Internet :

```text
uv run --offline --no-sync latros --registry sources/registry-general-v0.7.yaml data build --snapshot v0.7.0-general-dev-unreviewed --allow-unreviewed-research-data
uv run --offline --no-sync latros --registry sources/registry-general-v0.7.yaml data inspect --snapshot v0.7.0-general-dev-unreviewed
uv run --offline --no-sync latros diagnose --snapshot v0.7.0-general-dev-unreviewed --strategy general_v1 --case examples/general/respiratory-common.json
uv run --offline --no-sync latros question next --snapshot v0.7.0-general-dev-unreviewed --strategy general_v1 --case examples/general/respiratory-common.json
uv run --offline --no-sync latros --root . ui --no-open
```

Les dumps restent sous `data/raw/` et les tables/runtime générés sous `data/`; ils sont ignorés par
Git. Seuls le registre, le manifeste, les hashes, les importeurs, les schémas, les tests et la
documentation sont versionnés. Le runtime `general_v1` conserve le DuckDB vérifié en lecture seule
et ne matérialise que les assertions des candidats concernés. Le catalogue UI interroge lui aussi
DuckDB sans charger l'ensemble du modèle canonique en Python. Pour vérifier les sorties du vrai
snapshot contre les empreintes de l'ancienne implémentation et mesurer la mémoire :

```text
uv run --offline --no-sync python scripts/compare_general_v1_runtime.py --output data/staging/v0.7-f2/check.json --expected tests/golden/v0.7-general-v1-sha256.json
uv run --offline --no-sync python scripts/profile_general_v1_runtime.py --output data/staging/v0.7-f2/profile.json
```

Le second script refuse toute connexion réseau. Les sorties de ces commandes restent locales et
ignorées par Git ; le rapport de performance versionné résume les mesures reproductibles.

Pour reproduire l'audit quantitatif préparatoire et son échantillon local non revu, avec le
snapshot v0.7 déjà construit :

```text
uv run --offline --no-sync python scripts/audit_v07_general_quality.py --with-diagnostic-ties
```

Les sorties sont écrites sous `data/staging/v0.7-g0/` et ignorées par Git ; aucune assertion
ne devient approuvée par cette commande.

Pour générer localement les jeux de revue G1/G2 à partir du même snapshot figé :

```text
uv run --offline --no-sync python scripts/prepare_v07_g_review.py
```

Les trois CSV et leur résumé sont placés sous `data/staging/v0.7-g/`, ignoré par Git. Les colonnes
de décision et d'identité des réviseurs sont vides. Aucun mapping suggéré n'est promu dans le
snapshot par cette commande. Une relance accepte des sorties identiques mais refuse d'écraser
un fichier de revue modifié ; `--output-dir` reste limité à `data/staging/`.

| Source | Version | Utilisation |
| --- | --- | --- |
| [HPO](https://github.com/obophenotype/human-phenotype-ontology/releases/tag/v2026-09-01) | 2026-09-01 | Concepts, synonymes et hiérarchie HPO |
| [Mondo](https://github.com/monarch-initiative/mondo/releases/tag/v2026-09-01) | 2026-09-01 | Maladies, synonymes et mappings ORPHA |
| [Orphadata Science](https://sciences.orphadata.com/phenotypes/) | archive juillet 2026 | Associations maladie–HPO, fréquences et libellés EN/FR |

Les produits Orphadata sont fixés au commit `463f51d0db1d754b53e96027dd098a3d96a9c79c` de l'[archive officielle](https://github.com/Orphanet/Orphadata_aggregated/tree/463f51d0db1d754b53e96027dd098a3d96a9c79c). Date d'archive : 29 juin 2026 ; « juillet 2026 » est le nom de livraison du producteur.

## Construire et inspecter hors ligne

```text
uv run --offline --no-sync latros data build --snapshot v0.2.0
uv run --offline --no-sync latros data inspect --snapshot v0.2.0
```

Les sept tables canoniques sont publiées dans `data/canonical/v0.2.0/*.parquet`. Le runtime `data/runtime/v0.2.0/knowledge.duckdb` est ouvert en lecture seule par le moteur. Le [manifeste v0.2.0](manifests/v0.2.0.json) contient sources, hashes, comptes, version du code, transformations et avertissements. Cette référence reprend les mêmes données que l'ancien [latros-kb-0002](manifests/latros-kb-0002.json), conservé pour les reconstructions historiques. Le nouveau snapshot est construit séparément ; l'ancien manifeste n'est pas réécrit.

Un clone qui possède le manifeste mais pas les données reconstruit le snapshot et vérifie l'égalité du résultat. Aucun téléchargement pendant `build`. Un snapshot existant n'est jamais écrasé : un changement de sources ou d'implémentation nécessite un nouvel identifiant conforme au [plan](docs/plan.md), par exemple `v0.2.1` pour une révision de ce jalon. Un échec d'import produit un rapport local dans `data/failures/`, sans publier le snapshot.

L'étape 2 contient 60 928 concepts et 116 664 assertions maladie–phénotype. Le manifeste conserve 19 avertissements : un concept HPO inactif et 18 couples à fréquences contradictoires. Les règles de conservation et d'exclusion du calcul sont décrites ci-dessous et dans l'ADR.

Les hashes logiques portent sur les lignes triées et les hashes Parquet sur leurs fichiers : ils doivent être identiques à la reconstruction. Les octets du conteneur DuckDB peuvent différer malgré des données identiques ; son SHA-256 sert uniquement à détecter une corruption locale, dans `data/runtime/<snapshot>/integrity.json`, ignoré par Git. Le moteur vérifie ce reçu à chaque ouverture. Conserver le code et les dépendances verrouillées ; ne pas remplacer un manifeste historique pour masquer une dérive.

## Interroger le moteur

L'exemple est **inventé**, sans patient réel. La CLI attend des identifiants HPO, pas du texte libre.

```text
uv run --offline --no-sync latros diagnose --snapshot v0.2.0 --case examples/case.synthetic.json
uv run --offline --no-sync latros question next --snapshot v0.2.0 --case examples/case.synthetic.json
uv run --offline --no-sync latros diagnose --snapshot v0.2.0 --case examples/case.synthetic-v2.json
```

Format d'entrée :

```json
{
  "case_id": "experience-synthetique",
  "age": 22,
  "sex": "unknown",
  "observations": [
    {"concept_id": "HP:0001250", "status": "present"},
    {"concept_id": "HP:0000256", "status": "present"},
    {"concept_id": "HP:0001249", "status": "unknown"}
  ],
  "question_history": []
}
```

Ce JSON non versionné reste le contrat `ClinicalCaseV1`. Le nouveau schéma
[`ClinicalCaseV2`](schemas/clinical-case-v2.schema.json) est disponible pour préparer symptômes,
signes, temporalité, constantes, biologie, traitements, antécédents, risques, examens, imagerie et
contexte familial. Il porte obligatoirement `"schema_version": 2`, sépare les textes sources, les
propositions d'extraction et les observations confirmées, et ne contient aucune déduction du
moteur. La CLI accepte v1 et v2, mais ne transforme jamais silencieusement un fichier v1 : la
migration explicite reste disponible pour les appelants qui veulent conserver un cas v2.

`--strategy semantic_v1` est la stratégie par défaut. `--output-contract auto` conserve exactement
la sortie historique pour un cas v1 et retourne le nouveau contrat pour un cas v2. Les options
explicites `--output-contract v1` et `--output-contract v2` permettent de choisir le format. La
sortie v2 déclare périmètre, couverture, données utilisées ou ignorées, abstention, arguments par
source et famille de preuve, `safety.status: not_evaluated` et un reçu reproductible. Son agrégat
porte `scale_id: semantic_v1.compatibility` et n'est ni un pourcentage ni une probabilité.

Le reçu contient les hashes exacts du manifeste de connaissance et du profil de raisonnement, les
paramètres effectifs, sources et familles réellement utilisées, mappings, transformations et
version logicielle. Il est inclus dans le JSON de réponse mais n'est jamais persisté automatiquement.

Le résultat contient les 20 premiers candidats, rang, score brut, contributions favorables/défavorables, assertions sources, fréquences et informations encore inconnues. Les candidats gardent leurs identités ORPHA ; les équivalences Mondo explicites sont listées séparément. Âge et sexe sont conservés dans le contrat mais ignorés par le score.

Pour répondre, copier le cas dans `patient-data/` (ignoré par Git ; uniquement des cas synthétiques dans cette phase). Ajouter à `question_history` l'identifiant effectivement proposé et une réponse, par exemple :

```json
{"concept_id": "HP:0001252", "answer": "unknown"}
```

Relancer les commandes avec ce fichier. La CLI est sans session : l'appelant conserve l'historique, Latros ne modifie pas le cas. Si une observation du même concept existe, elle doit porter le même état. `unknown` ne change pas les scores mais empêche de reposer la question. Arrêt à 12 réponses ou sans question informative admissible. Sans signe présent exploitable : liste vide, pas de résultat rassurant.

Pour isoler les données : `latros --root <dossier> --registry <chemin-absolu-du-registre> ...`. Les options globales précèdent la sous-commande. `--case` est relatif au répertoire courant, pas à `--root`. JSON sur stdout ; erreurs sur stderr avec code de sortie non nul. Aucun cas ou résultat enregistré automatiquement. Attention aux redirections de sorties sensibles.

## Méthode et limites

Voir [les équations et règles détaillées](docs/methodology.md) : contenu informationnel du corpus, maximum de similarité Resnik par signe présent, moyenne positive et pénalités d'absence à fréquence connue. Aucun a priori épidémiologique, aucune prévalence, aucun posterior.

Les questions utilisent une réduction d'entropie **heuristique**, avec des poids internes dérivés des scores. Au moins 60 % du poids des dix premiers candidats doit disposer d'une fréquence pour le signe. Les fréquences manquantes ne deviennent jamais des absences.

L'import conserve et signale les fréquences contradictoires entre enregistrements distincts : elles ne servent ni aux pénalités ni aux questions. Un phénotype obsolète sans remplacement exact est conservé mais exclu du calcul. Les versions EN/FR d'un même enregistrement ne comptent qu'une fois. Les libellés HPO anglais présents dans le produit français restent identifiés comme anglais lorsqu'ils correspondent à un libellé anglais connu.

**Limites :** biais maladies rares et annotations, signes corrélés, temporalité/contexte encore peu
utilisés, questions techniques, aucune validation clinique. Les tests synthétiques vérifient le
logiciel, pas sa justesse médicale. L'interface v0.6 n'ajoute ni LLM, MedGemma, TxGemma, moteur de
sécurité, audio, entraînement ou conseil thérapeutique.

## Développement et tests

```text
uv run --offline --no-sync ruff check .
uv run --offline --no-sync ruff format --check .
uv run --offline --no-sync mypy
uv run --offline --no-sync python scripts/export_schemas.py --check
uv run --offline --no-sync pytest
```

La CI Linux/Windows utilise uniquement les petits jeux inventés de `tests/conftest.py`, bloque le réseau pendant les tests et ne télécharge aucune base médicale. Les [schémas](schemas/) se régénèrent avec `python scripts/export_schemas.py` ; Pydantic vérifie en plus les contraintes inter-champs non exprimées en JSON Schema.

```text
src/latros/sources/     registre et téléchargement vérifié
src/latros/knowledge/   fréquences, importeurs, validation et snapshots
src/latros/clinical/    contrat ClinicalCase
src/latros/reasoning/   stratégies, profils, semantic_v1, sorties v2 et reçus
src/latros/application/ orchestration partagée entre CLI et interface
src/latros/ui/          serveur loopback, sessions, parcours simple et console experte
src/latros/cli.py       commandes publiques
docs/                   tutoriel, roadmap, historique, vision, ADR, audits et revues
sources/               registre épinglé (versionné)
schemas/               contrats exportés (versionnés)
profiles/              profils de raisonnement versionnés et hashés
manifests/             références de reconstruction (versionnées)
data/                  sources et snapshots locaux (ignorés)
sessions/              cas et historique de runs locaux (ignorés)
tests/                 fixtures synthétiques et tests hors ligne
```

Suivre [CONTRIBUTING.md](CONTRIBUTING.md) : branches de fonctionnalité, pull requests et `main`
stable. `0.6.0` reste un prototype de recherche, pas une certification médicale.

## Confidentialité et licences

Ne jamais envoyer sur GitHub les sources brutes, snapshots, données patient, poids de modèles ou secrets. Seuls code, documentation, registre, schémas, manifestes et fixtures inventées sont versionnés. `.gitignore` limite les accidents mais n'est pas un contrôle d'accès : vérifier chaque diff.

Attributions : Human Phenotype Ontology Consortium ; Mondo Disease Ontology contributors ; Orphadata, INSERM/Orphanet. Les licences des sources sont indépendantes de celle du code. Aucune licence de redistribution du code n'a encore été choisie ; le dépôt reste privé. La conservation locale d'une source ne dispense pas de respecter ses conditions.
