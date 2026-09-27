# Plan d'implémentation et avancement

Référence : plan « Premières étapes de Latros — socle de données et moteur clinique pur » demandé par l'utilisateur. État au 27 septembre 2026.

Les trois jalons avaient été implémentés ensemble dans la première tranche. La reprise de l'étape 2 consiste à vérifier sa livraison et à établir le snapshot sous le nom du jalon, `v0.2.0`. Elle ne correspond pas à l'ajout de nouvelles sources ou de fonctions cliniques.

## Jalons du plan

### Parcours General-first / Rare-second — expérimentation du 27 septembre 2026

Implémenté séparément de `general_v1` : `general_question_v2` mono-source MedlinePlus retained
G4 (142 maladies, 684 assertions, une famille `unknown`) puis `rare_question_v1` sur demande
explicite. Budgets 6 / 12, anti-doublons, cas partagé, résultats séparés.
[Rapport](reports/general-first-rare-second.md), [ADR 0017](decisions/0017-consultations-generale-et-rare-versionnees.md).
Aucune revue clinique G1/G2 réalisée, G3 indépendant à faire, snapshot inchangé. Optimisation
runtime arrêtée après F6 sauf régression. Illustrations/navigation/traductions : chantier distinct,
intégré avec ces politiques après fusion de #19. L'intégration relit les sessions existantes
sans les supprimer ni ignorer le contrat `consultation` ; tests combinés : 235 Python et 16 frontend.
Les JS/CSS locaux sont liés à leurs hashes pour éviter une UI obsolète dans le cache navigateur.

| Étape | Nom du plan | État logiciel | Référence des données |
| --- | --- | --- | --- |
| 1 | Fondation technique — `v0.1.0` | Implémentée : paquet, CLI sources, registre, téléchargements vérifiés, verrou et CI | Aucun snapshot médical nécessaire à ce jalon |
| 2 | Premier snapshot médical — `v0.2.0` | Implémentée ; référence versionnée alignée sur le nom du plan | `manifests/v0.2.0.json` |
| 3 | Moteur pur et interrogatoire — `v0.3.0` | Implémentée dans le paquet `0.3.0` ; évaluation clinique non réalisée | Le moteur utilise le snapshot `v0.2.0` |
| 4 | Clinical Knowledge Model — `v0.4.0` | Terminée : checkpoints A–H livrés et revue finale verte | La référence reste `v0.2.0` ; aucun snapshot médical v2 publié |
| 5 | Snapshot ORL généraliste — `v0.5.0` | En cours : A–D terminés ; E historique en `NO-GO` ; E2 audité ; E3 prêt pour revue ; mode E4 local non validé disponible | Référence officielle toujours bloquée ; `v0.5.0-dev-unreviewed` est non publiable |
| 6 | Interface interne de test R&D — `v0.6` | Terminée et fusionnée dans `main` ; parcours simple expérimental ultérieur en chantier séparé | Console experte, sessions reprenables et projection simple des moteurs ; aucun produit médical validé ni nouvelle logique clinique |
| 7 | Fabrique souveraine généraliste — `v0.7` | D–F6, G0 et G4 technique terminés ; préparation G0/G1/G2 acceptée techniquement ; revue humaine G1/G2 et évaluation indépendante G3 à faire | `v0.7.0-general-dev-unreviewed` inchangé, non validé et non publiable ; biologie et médicaments restent futures |
| 8 | Safety / triage séparé — `v0.8` | Prévue | Composant indépendant du différentiel, avec périmètre et validation propres |
| 9 | NLP / LLM encadré — `v0.9` | Prévue | Structuration, reformulation et explication, jamais source implicite de connaissance |
| 10 | API, FHIR et interopérabilité — `v0.10` | Prévue | Exposition et échanges des contrats de domaine après validation des étapes précédentes |

Il s'agit des étapes du plan, pas d'une série de releases GitHub publiées. Aucun tag ou changement de version rétroactif du paquet n'est nécessaire pour identifier un snapshot. L'évaluation clinique et les fonctionnalités futures restent à discuter séparément.

## Étape 4 — Clinical Knowledge Model

Le [cahier des charges de v0.4](v0.4-clinical-knowledge-model.md) est la référence de conception et de livraison de cette tranche. Il a généralisé les contrats cliniques et de connaissances, la provenance, la gestion des doublons et l'architecture des stratégies sans importer massivement de nouvelles bases ni casser `semantic_v1`.

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

La stratégie de sources est ensuite réouverte sans effacer ce résultat. L'audit
[`v0.5-E2`](source-audits/v0.5-orl-open-sources.md) retient DOID/Mondo pour préparer les identités et
un corpus NHS/nidirect, CDC et MedlinePlus strictement filtré comme voie alternative. Le contenu
minimal est maintenant curé dans un paquet réel `pending_clinical_review`. Les pages CDC en sont
écartées tant que leurs conditions internationales ne sont pas fermées. Aucune assertion n'a encore
la double revue requise : la publication reste donc en `NO-GO`.

Une première veille des ressources de médecine générale est intégrée au cahier des charges. Elle sépare terminologies, classifications, standards d'échange, sources d'assertions, règles cliniques, jeux synthétiques et benchmarks. Les matrices Kaggle/Mendeley ne sont pas retenues comme connaissance clinique tant que leur provenance n'est pas démontrée ; SNOMED CT, ICD, FHIR, LOINC, UCUM, UMLS, DDXPlus, Synthea, WHO SMART Guidelines, HealthBench, MIMIC-IV et ClinicDx sont positionnés selon leur rôle et une étape éventuelle, sans décision d'intégration anticipée.

Les futurs manifestes devront aussi déclarer le périmètre, les dépendances entre sources, les familles de preuves, les règles de déduplication et les profils de raisonnement compatibles. Le snapshot et le profil d'agrégation resteront versionnés séparément mais seront liés par leurs hashes dans chaque exécution. La référence historique `v0.2.0` ne sera pas réécrite.

## Étape 5 — Snapshot ORL généraliste et `general_v1`

La décision est fixée par l'[ADR 0005](decisions/0005-snapshot-v2-et-pilote-orl.md). Le travail
avance sur deux pistes : pipeline et raisonnement testés sur données entièrement inventées ; audit
juridique et clinique séparé des sources réelles. `v0.5.0` sera un snapshot ORL adulte distinct de
`v0.2.0` ou ne sera pas publié.

| Checkpoint | État | Sortie attendue |
| --- | --- | --- |
| `v0.5-A` | Terminé | ADR, registre v2, manifeste v2 et schémas exportés |
| `v0.5-B` | Terminé | Constructeur reproductible des treize tables sur fixtures |
| `v0.5-C` | Terminé | Importeurs RF2 et assertions curées synthétiques |
| `v0.5-D` | Terminé | Stratégie déterministe `general_v1` sur mini-corpus fictif |
| `v0.5-E` | Terminé — `NO-GO` confirmé | Audit final SNOMED/HAS ORL ; conditions juridiques, cliniques et de couverture non satisfaites |
| `v0.5-E2` | Terminé — `NO-GO` de publication | Audit DOID/Mondo/MeSH et NHS/CDC/MedlinePlus ; matrice de couverture produite ; curation et double revue absentes |
| `v0.5-E3` | Terminé techniquement — revue humaine requise | 17 assertions, 10 mappings, artefacts/hashes, dossier de revue et gate formel ; `ready_for_human_review` |
| `v0.5-E4` | Terminé — recherche locale non validée | Snapshot `v0.5.0-dev-unreviewed`, override explicite, profil d'ingénierie et résultats toujours marqués non relus |
| `v0.5-F` | Bloqué par la double revue E3 | Snapshot médical réel `v0.5.0` |
| `v0.5-G` | Bloqué par `v0.5-F` | Validation clinique séparée et clôture |

`general_v1` accepte exclusivement `ClinicalCaseV2`, les concepts identiques ou les mappings
résolus `exact/equivalent`, et un snapshot canonique v2 qui déclare son profil. Son score
`general_v1.compatibility` reste une compatibilité non calibrée. Les assertions sont évaluées par
polarité explicite, moyennées dans chaque famille de preuve puis combinées seulement entre familles
indépendantes autorisées par le profil. La CLI expose le raisonnement et les questions en contrat v2,
avec couverture, abstention, sources, familles, mappings et reçu reproductible.

Le profil `general_v1-default` est actuellement lié au corpus inventé `test-v2`. Il sert à vérifier
les règles du moteur, pas à produire un résultat clinique. Le futur snapshot ORL devra disposer d'un
profil versionné dont les familles et poids correspondent exactement au corpus approuvé.

Le checkpoint E confirme que la fiche HAS angine, essentiellement orientée antibiothérapie, ne
suffit pas à documenter le différentiel fermé des quatre candidats. Chacun devra disposer d'au moins
deux assertions diagnostiques explicites et d'une assertion discriminante approuvées. Les licences
SNOMED, les droits de transformation/redistribution, la double revue et ce seuil de couverture ne
sont pas satisfaits : F et G ne doivent donc pas commencer.

Le checkpoint E2 confirme une voie juridiquement plus simple sans SNOMED. DOID `v2026-08-31` et
Mondo `v2026-09-01` sont compatibles avec un import versionné ; MeSH est différé. Les pages ouvertes
identifiées ont permis de préparer au moins deux assertions et un élément discriminant par candidat.

Le checkpoint E3 matérialise cette curation : 17 assertions atomiques et 10 mappings qualifiés,
captures locales et empreintes, provenance record par record, familles de preuves, dossier de revue
et gate de publication. Les pages CDC ne participent pas au paquet tant que leur redistribution
internationale n'est pas clarifiée ; nidirect reste une republication NHS et les dépendances NLM
inconnues ne sont pas agrégées. Les 17 assertions et 10 mappings sont tous `pending_review`.
Techniquement le paquet est `ready_for_human_review`, mais F reste interdit jusqu'à deux
approbations réelles par assertion, dont un clinicien compétent, et la revue des mappings.

Le checkpoint E4 ajoute un chemin local distinct sans modifier ce gate. La commande `data build`
exige `--allow-unreviewed-research-data` et un identifiant terminé par `-dev-unreviewed`. Le
manifeste, le profil et chaque reçu déclarent l'absence de validation clinique, les 17 assertions et
10 mappings non revus, zéro reviewer et `publishable: false`. Les statuts sources restent inchangés,
les mappings non exacts ne scorent pas, les dépendances NLM inconnues restent non agrégeables et le
moteur de sécurité reste `not_evaluated`. Ce mode sert aux tests de pipeline et d'interface ; il ne
commence ni F ni G et ne transforme pas le corpus en référence médicale.

## Étape v0.6 — interface interne de test R&D

`v0.6` est une interface locale réservée au développement et à la recherche. Elle n'est ni une
interface patient, ni un produit utilisateur, ni une interface médicale validée. Son unique rôle
est de rendre inspectables les contrats et moteurs déjà disponibles, sans introduire de nouvelle
logique médicale.

Son périmètre livré est le suivant :

- créer, reprendre et modifier simplement un `ClinicalCaseV2` dans une session locale ;
- lancer `general_v1` et, seulement lorsqu’un cas et un snapshot y sont compatibles, `semantic_v1` ;
- afficher les candidats, compatibilités non calibrées, couverture, arguments favorables et
  défavorables, contradictions, sources, provenance, reçu d’exécution et statut de validation ;
- rendre `safety_status` visible, y compris sa valeur actuelle `not_evaluated` ;
- accepter le snapshot expérimental `v0.5.0-dev-unreviewed` en conservant partout son avertissement,
  son statut non revu et ses limites ;
- demander la question suivante au moteur et enregistrer sa réponse comme observation confirmée ;
- conserver chaque analyse et question dans un historique immuable lié au cas et au reçu exacts.

Le choix d'architecture est fixé par l'[ADR 0008](decisions/0008-interface-locale-rd-et-sessions.md) :
FastAPI/Uvicorn sur `127.0.0.1`, pages Jinja2 et JavaScript natif, sans Node, CDN, télémétrie, CORS
ou option d'écoute publique. `ResearchApplicationService` est partagé avec la CLI ; le frontend ne
calcule aucun score. Le transport `/internal/v1` est interne à l'outil et n'anticipe pas l'API
publique de v0.10.

Les sessions utilisent le [schéma `ui-session-v1`](../schemas/ui-session-v1.schema.json), des
écritures atomiques et une révision optimiste. `session.json` conserve l'état courant ; `runs/`
conserve des copies immuables du cas, de la sélection et de chaque sortie v2. `sessions/` est hors
Git et ne promet ni chiffrement, ni comptes, ni stockage de dossiers médicaux réels.

| Checkpoint | Livraison | État |
| --- | --- | --- |
| `v0.6-A` | ADR, dépendances minimales et service applicatif partagé avec la CLI | Terminé |
| `v0.6-B` | Découverte des snapshots, compatibilités et catalogue de concepts | Terminé |
| `v0.6-C` | Sessions versionnées, sauvegarde atomique et runs immuables | Terminé |
| `v0.6-D` | Serveur loopback et transport interne sécurisé | Terminé |
| `v0.6-E` | Éditeur simple `ClinicalCaseV2` et cinq états d'évaluation | Terminé |
| `v0.6-F` | Résultats, abstention, provenance, questions et statuts non revus | Terminé |
| `v0.6-G` | Non-régression, packaging et documentation ; CI Windows/Linux après push | Terminé — contrôles locaux et CI GitHub Ubuntu/Windows verts au run `#35337846570` |

Une évolution ultérieure de cette interface devra prévoir une visualisation avancée de type
Knowledge Graph, « cerveau médical » ou graphe Obsidian. Elle devra rendre navigables, filtrables et
explorables par zoom, clusters et relations réelles les observations et symptômes, signes, maladies
rares ou courantes, candidats, assertions médicales, arguments favorables ou contradictoires,
concepts HPO/Mondo/DOID et autres terminologies, sources, provenance, questions discriminantes et
objets de raisonnement pertinents. Cette visualisation interactive sera une projection fidèle des
données et contributions réellement présentes dans Latros : elle ne pourra ni inventer une relation,
ni créer une preuve, ni modifier un score pour améliorer l’esthétique du graphe.

Cette vue avancée ne constitue pas un critère de livraison de la première interface **v0.6**. Le
socle livré conserve les identifiants d'observation, assertion, contribution, candidat, mapping et
source nécessaires à cette projection future ; le Knowledge Graph reste à cadrer et tester
séparément.

Elle ne doit pas créer de diagnostic, de promesse clinique, de règle de triage, de score
probabiliste, de source médicale ou de workflow de texte libre. L'ancienne maquette locale a été
supprimée après livraison de v0.6. L'interface officielle, ses actifs et ses comportements sont
désormais entièrement portés par `src/latros/ui/` et ne dépendent d'aucun dossier externe ou ignoré.

Les critères d’acceptation de cette tranche sont une séparation visible entre
snapshots validés et non revus, la fidélité aux sorties et reçus des moteurs existants, l’absence de
vocabulaire diagnostic/probabiliste et l’impossibilité de masquer l’état de sécurité ou les limites
de couverture. Les tests UI vérifient le logiciel et les garde-fous, jamais la justesse médicale.

### Parcours simple expérimental après v0.6

Un chantier UI distinct de `v0.7-G` ajoute une entrée mobile-first à `/` et conserve la console
v0.6 à `/expert`. Il réutilise les sessions, la recherche DuckDB ciblée, les questions et résultats
du backend. La sélection d'un symptôme reste explicite ; aucun NLP, score frontend, pourcentage
diagnostique ou triage n'est ajouté. Les alertes `research_unreviewed` et
`safety.status = not_evaluated` demeurent visibles. L'[ADR 0011](decisions/0011-parcours-simple-local.md)
réévalue Jinja2/JavaScript natif face à React/Vite ; la
[documentation UI](modern-ui.md) précise le parcours et ses limites. Ce prototype d'ergonomie ne
change ni le jalon v0.6 livré, ni le statut du snapshot v0.7, ni la revue clinique G.

L'extension [multilingue et recherche locale](reports/ui-i18n-local-search.md), fusionnée via
#16 après G5 #15, apporte FR/DE/EN pour le parcours simple, désignations locales et
lexique d'affichage limité, suggestions tolérantes et fallback anglais visible. Les concepts,
observations soumises, question IDs et résultats scientifiques restent inchangés ; v0.9 NLP
reste future. Node 22 sert uniquement aux tests frontend, jamais au runtime de Latros.

La tranche UI anatomique vNext implémente Corps → Tête → Sinus, SVG locaux et arbre de
navigation extensible, recherche permanente, états explicites sans doublon, thèmes et responsive.
L'extension atlas v3 ajoute sept images générées locales, 35 vues avec overlays indépendants
et zooms (oreilles, thorax, abdomen, urinaire, membres). Les organes hors tête n'ont pas encore
de planches dédiées. Les références sont résolues contre les
observations supportées du snapshot, jamais ajoutées comme assertions ou localisation clinique.
139 concepts ont un affichage FR/DE actif ; la majorité reste avec fallback EN.
L'[ADR 0016](decisions/0016-navigation-anatomique-de-presentation.md) et le
[rapport mesuré](reports/ui-anatomy-vnext.md) précisent architecture, coverage et limites.
Ce chantier ne commence ni G clinique, ni safety, ni v0.9 ; scoring et snapshot restent identiques.
Le [rapport atlas v3](reports/ui-atlas-v3.md) et l'[ADR 0018](decisions/0018-illustrations-locales-et-overlays.md)
documentent les images non validées anatomiquement, les traductions éditoriales à revoir et
l'export linguistique déterministe. Le questionnaire General/Rare est une tranche séparée (#19).

## Étape v0.7 — fabrique souveraine généraliste

L'[ADR 0009](decisions/0009-fabrique-souveraine-generaliste.md) fixe l'invariant offline-first et
l'[audit des distributions](source-audits/v0.7-sovereign-general.md) retient MedlinePlus XML, MeSH
XML et une release locale Monarch comme première cible. CDC est différé avec le statut
`NOT SUITABLE FOR SOVEREIGN INGESTION`. Le pilote ORL reste un corpus historique de régression et
ne sera pas restauré comme dépendance du nouveau snapshot.

| Checkpoint | État | Sortie attendue |
| --- | --- | --- |
| `v0.7-A` | Terminé | Audit officiel, ADR souverain et identifiant `v0.7.0-general-dev-unreviewed` réservé |
| `v0.7-B` | Terminé | Registre multi-source enrichi : rôles fermés, producteur, importeur, droits, capture et formats |
| `v0.7-C` | Terminé | Contrat séparé de candidate assertion et parseur local MedlinePlus sur fixtures inventées |
| `v0.7-D` | Terminé | Sept sources réelles épinglées ; MedlinePlus 2026-09-19, MeSH 2026 et Monarch 2026-09-02 vérifiés par hash |
| `v0.7-E` | Terminé | Importeurs locaux MeSH/Monarch, extraction candidate MedlinePlus, mappings exacts et déduplication/dépendances |
| `v0.7-F` | Terminé | Snapshot généraliste DEV, profil `general_v1`, rapport de couverture, cas synthétiques et reconstruction offline |
| `v0.7-F2` | Terminé — durcissement technique | Repository DuckDB v2 paresseux en lecture seule, catalogue UI ciblé, comparaison exacte des sorties et profil mémoire du snapshot existant |
| `v0.7-F3` | Terminé — latence runtime | Filtres volumineux dérivés dans DuckDB ; diagnostic après question mesuré de 292 à 15,6 s, sorties identiques ; transport complet encore 23,6 s sur le grand cas |
| `v0.7-F4` | Terminé — transport paresseux | Run complet conservé ; projection HTTP top 20 et détail candidat à la demande, 14 Ko initiaux et 18,5 s sur le grand cas fictif ; scoring inchangé |
| `v0.7-F5` | Terminé — profilage et latence résiduelle | Format du run F4 conservé après mesures ; tables temporaires DuckDB réutilisées, grand cas 19,1 → 12,7 s dans le protocole F5, cas courant 5,7 → 4,3 s, sorties d'or identiques |
| `v0.7-F6` | Terminé — matérialisation des preuves | Trois stratégies mesurées ; projection interne compacte retenue, grand cas 12,54 → 9,50 s et RSS 3,15 → 2,86 Go, résultat complet et goldens identiques |
| `v0.7-G0` | Audit terminé, vérifié et accepté techniquement | Audit SQL du corpus, des dépendances et des mappings ; échantillon stratifié non revu pour préparer G |
| `v0.7-G1` | Dispositif vérifié et prêt — décision humaine à faire | 689 topics MedlinePlus bloqués, pistes lexicales/MeSH non promues, aucune décision préremplie |
| `v0.7-G2` | Échantillonnage et provenance vérifiés, outil prêt — revue humaine à faire | 120 candidates MedlinePlus et 40 assertions Monarch/Orphadata ; décisions séparées du snapshot |
| `v0.7-G3` | Protocole défini — évaluation indépendante non réalisée | Cas non patients à rédiger/adjudique séparément du snapshot et des fixtures logiciels |
| `v0.7-G4` | Passe technique expérimentale terminée — revue humaine à faire | Rejeu exact du XML MedlinePlus local, filtre de rôle/contextes et nouveau G2 ; aucun candidat approuvé ni snapshot modifié |
| `v0.7-G5` | Workflow d'adjudication préparé — décisions humaines à faire | 7 736 items G4 contextualisés, double revue, adjudication distincte, contrôles déterministes 180 retenues / 180 rejets et exports séparés |
| `v0.7-G` | À faire | Revue clinique et décision distincte sur une éventuelle publication |

Le parseur MedlinePlus transforme uniquement le XML local en enregistrements sources fidèles. Le
premier extracteur déterministe applique des correspondances HPO anglaises exactes aux seuls topics
anglais, tout en conservant les 2 033 records anglais et espagnols. Les candidats techniquement
éligibles du snapshot DEV restent `unreviewed`; ils ne deviennent jamais `approved`. Seuls les
mappings résolus `exact/equivalent` participent au scoring. Les treize tables canoniques v2 et les
manifestes historiques ne sont pas réécrits. Les résultats chiffrés sont consignés dans le
[rapport v0.7](reports/v0.7-general-coverage.md).

`v0.7-F2` ne change pas les treize tables, le hash du pipeline de build, le profil ou le snapshot
figé. La CLI et l'interface utilisent un repository de lecture DuckDB en lecture seule pour
`general_v1` : résolution et candidats sont obtenus par requêtes ciblées, les assertions et leur
provenance ne sont matérialisées que pour les candidats scorables, et le catalogue ne charge plus
`CanonicalKnowledgeV2`. L'ancienne implémentation reste comme référence des tests ; les résultats
du snapshot réel sont comparés par empreintes du JSON complet. Le
[rapport de performance](reports/v0.7-runtime-performance.md) détaille mesures, limites et commandes.
Le [rapport F3](reports/v0.7-f3-runtime-latency.md) chiffre le goulet des grands paramètres
`VARCHAR[]` et l'amélioration sans changement du snapshot ni des résultats.
Le [rapport F4](reports/v0.7-f4-result-transport.md) chiffre la projection HTTP et l'index
local de détails : le résultat scientifique intégral reste immuable et accessible en mode expert.
Le [rapport F5](reports/v0.7-f5-run-persistence.md) établit que l'écriture du run n'est pas le
goulet, compare les options de stockage et documente l'optimisation ciblée du repository sans
nouveau format ni modification du snapshot.
Le [rapport F6](reports/v0.7-f6-evidence-materialization.md) compare joins SQL, index dérivé
et représentation compacte avant de retenir cette dernière. La provenance complète et le run
immuable restent obligatoires ; le snapshot et la mathématique ne changent pas.
Le durcissement runtime v0.7 s'arrête à F6 sauf régression importante. La passe G4
([rapport](reports/v0.7-g4-medlineplus-extraction-quality.md)) rejoue MedlinePlus depuis le ZIP
local vérifié, rejette 1 468 candidats à rôle lexical inadapté et met 4 056 candidats incertains
en revue humaine ; 2 212 candidats restent dans un **jeu expérimental**. Elle ne remplace ni le
snapshot existant ni les jeux G1/G2 historiques. La baisse de couverture technique est un risque
de faux négatifs à évaluer humainement, pas une validation médicale.
L'[audit structurel `v0.7-G0`](reports/v0.7-general-quality-audit.md) chiffre la forte liaison
Orphanet/génétique (14 661 des 15 611 maladies documentées), le goulet de mapping MedlinePlus
et les dépendances Monarch. Il ne déduit pas la prévalence d'une maladie de ses seules hiérarchies
et ne change ni le snapshot, ni le profil, ni les statuts de validation.
La revue clinique humaine `v0.7-G` n'a pas commencé.

Les [jeux et le protocole de revue ciblée](reports/v0.7-g-targeted-review.md) n'approuvent aucun
mapping ni assertion. Ils rendent vérifiables les 5 106 candidates MedlinePlus bloquées et les
dépendances Monarch/Orphadata. Le `NO-GO` actuel concerne toute publication clinique tant que
la revue qualifiée et le corpus d'évaluation indépendant manquent ; il ne change pas le statut
du snapshot. Les décisions humaines G1/G2 et l'évaluation G3 restent à réaliser.
Les exports identiques peuvent être régénérés, mais un CSV ou résumé annoté est protégé contre
l'écrasement accidentel ; le chemin de sortie reste sous `data/staging/`.
L'[outil de revue G1/G2](v0.7-g-review-ui.md), distinct du symptom checker, affiche une ligne à
la fois et conserve un journal local append-only. Son existence n'est ni une décision clinique,
ni le début d'une promotion du snapshot ; G1/G2 restent à faire par des réviseurs réels.
G5 étend cet outil par un [workflow d'adjudication](reports/v0.7-g5-human-adjudication.md),
sans nouveau filtre ni promotion. Les 4 056 items `needs_human_review` ouvrent la file ;
les contrôles des retenues/rejets ne mesurent pas une sensibilité clinique. G3 reste requis.

### Sous-tranches v0.7 — médicaments, temporalité et mesures cliniques

La future tranche `v0.7` devra distinguer l'exposition réellement rapportée ou observée chez le
patient, la substance active, le produit ou la présentation commercialisée et la classe
thérapeutique. Une indication, un effet indésirable, une contre-indication, une interaction ou une
contrainte d'usage sera une assertion médicale distincte, sourcée et versionnée ; ni un code de
produit, ni un mapping ne devront devenir une preuve diagnostique ou une recommandation implicite.

ATC, RxNorm et un référentiel français de produits seront évalués comme candidats de
normalisation, avec audit préalable de couverture, version, licence, redistribution, identifiants
et reproductibilité. Les premiers tests resteront synthétiques. Cette trajectoire ne crée pas de
fonction de prescription, de calcul de dose, de choix de traitement ou de contrôle d'interactions :
ces fonctions exigeraient un périmètre, des sources, des règles et une validation clinique propres.

Les mêmes exigences s’appliqueront aux résultats biologiques, constantes, unités, temporalité et
facteurs de risque : leur représentation est déjà préparée par les contrats, mais leur ingestion,
leur normalisation et leur usage clinique ne commenceront qu’après les audits propres à `v0.7`.

## Trajectoires v0.8 à v0.10

- **`v0.8` :** composant safety / triage versionné, séparé du différentiel et soumis à un périmètre,
  des sources et une validation clinique dédiés.
- **`v0.9` :** NLP / LLM limité à la proposition d’observations structurées, à la reformulation et à
  l’explication fidèle aux sorties déterministes ; aucune connaissance médicale implicite.
- **`v0.10` :** API, FHIR et interopérabilité, après stabilisation des contrats ; FHIR reste un
  format d’échange et non une base de connaissances ou un moteur clinique.

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

Actualiser ensemble [history.md](history.md), [README.md](../README.md) et ce plan : état réel des jalons, noms de snapshots, commandes, décisions, vérifications et limites. Si un contrat, une source ou une règle d'import change, actualiser également le schéma, le registre, le manifeste ou l'ADR concernés. Garder les réalisations antérieures dans le journal daté.
