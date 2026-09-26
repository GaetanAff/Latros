# Historique de Latros

Ce fichier est le journal de continuité du projet. Il décrit ce qui a été décidé et effectivement réalisé, afin de pouvoir reprendre la discussion sans déduire l'état du projet à partir du code seul.

Dernière mise à jour : 26 septembre 2026.

## État actuel en une phrase

Latros est aujourd'hui un prototype local de recherche utilisable en ligne de commande ou dans une
interface web simple avec console experte locale. Il prend des cas structurés, exécute `semantic_v1` sur le snapshot rare
ou `general_v1` sur les snapshots expérimentaux ORL et généraliste, expose les preuves et propose
éventuellement une question discriminante. Il n'est ni un chatbot, ni une interface patient, ni un
outil de triage ou de diagnostic clinique validé.

Référence médicale publiée : **`v0.2.0`**, nom du jalon « Premier snapshot médical » dans le
[plan d'implémentation](plan.md). Le paquet est à la version `0.6.0`. Le snapshot v2
`v0.5.0-dev-unreviewed` reste une expérience locale non publiable ; aucun snapshot clinique v2
validé n'est publié. `v0.7.0-general-dev-unreviewed` est le nouveau corpus généraliste DEV local,
également non publiable. L'ancien snapshot `latros-kb-0002` est conservé.

## Qualité d'extraction MedlinePlus `v0.7-G4` — 26 septembre 2026

- La PR #13 (F6) a été relue : scoring, candidats, scores, provenance, run complet, snapshot,
  compatibilité UI/sessions et fonctionnement offline inchangés ; goldens et CI Linux/Windows
  verts. Elle a été fusionnée dans `main` avant la branche G4. Les optimisations runtime v0.7
  s'arrêtent à F6 sauf régression importante.
- Le rejeu du ZIP MedlinePlus épinglé, à partir des terminologies du DuckDB figé en lecture
  seule, reproduit exactement 7 736 candidats et leur SHA-256 historique. L'audit lexical du
  G2 réel identifie modificateurs, auto-références, URLs, négations et contextes non
  symptomatiques ; cinq faux positifs fournis ont été retrouvés dans le XML.
- Un extracteur expérimental distinct du pipeline hashé classe 1 468 candidats en rejet
  d'extraction automatique, 4 056 en revue humaine et 2 212 retenus dans un nouveau jeu
  **non intégré**. Quatre contrôles plausibles restent conservés. Le G2 historique reste intact ;
  nouveau sample et journal des 7 736 décisions restent sous `data/staging/`.
- Les vérifications et limites sont consignées dans le
  [rapport G4](reports/v0.7-g4-medlineplus-extraction-quality.md). Ruff, format, mypy strict,
  schémas, registre et 197 tests sont verts ; le rejeu réel avec sockets bloquées produit le
  même hash. La PR #14 est ouverte avec CI Linux/Windows verte. G1/G2 humains et G3
  indépendant restent à faire ; aucun statut clinique n'a changé.

## Matérialisation compacte `v0.7-F6` — 26 septembre 2026

- La PR #12 (F5) a été revue et fusionnée dans `main` après CI Linux/Windows verte, 167 tests
  locaux et sorties d'or identiques. F6 part du `main` synchronisé sur une branche distincte.
- Trois stratégies ont été mesurées avant choix : join SQL complet (rapide isolément mais
  plus lent et plus gourmand en RAM une fois intégré), index dérivé (lecture chaude rapide,
  construction et gouvernance coûteuses), représentation interne compacte (retenue).
- Le gros cas fictif passe de 12,54 à 9,50 s HTTP et de 3 153 à 2 856 Mo de pic RSS ; le
  respiratoire de 4,17 à 3,89 s. Le résultat complet du gros cas conserve son SHA-256 et sa
  taille ; les sept diagnostics/questions d'or sont inchangés. Le rapport F6 détaille les
  mesures, la reproductibilité et la limite du run de 206 Mo.
- Ruff, format, mypy strict, schémas, registre, 168 tests locaux et CI Linux/Windows de la PR
  #13 sont verts. Aucun score, snapshot, provenance finale ou statut médical n'est changé.

## Clarification des préparations `v0.7-G0/G1/G2` — 25 septembre 2026

- L'audit G0, le jeu de revue des mappings G1, l'échantillonnage assertions/provenance G2 et
  l'outil local G1/G2 sont considérés vérifiés et acceptés **techniquement/méthodologiquement**.
  Les dépendances Monarch/Orphadata restent exposées, sans double approbation ni décision fictive.
- Les vraies décisions G1/G2 exigent encore des réviseurs humains qualifiés. Le protocole G3 est
  défini, mais aucun corpus indépendant n'a été évalué. Aucune allégation clinique n'en découle.
- Vérification documentaire de README, plan, rapport G et ADR 0009/0012 ; aucune modification
  de code, snapshot, mapping, assertion ou statut clinique dans cette clarification.

## Profilage et latence résiduelle `v0.7-F5` — 25 septembre 2026

- La PR #11 (F4) a été revue puis fusionnée dans `main` après CI Linux/Windows et 166 tests
  verts, avec 7/7 sorties d'or inchangées. F5 est isolée sur
  `codex/v0.7-f5-run-persistence` ; le dossier local `FUTUR INTERFACE/` reste hors Git.
- Une baseline sur trois cas fictifs mesure séparément DuckDB, scoring, Pydantic, écriture,
  renommages atomiques, réponse HTTP, tailles et RSS. Sur le grand cas, le run complet de
  206 Mo s'écrit en ~0,35 s ; `candidate_rows()` prend ~11,7 s. La refonte en shards ou base
  dédiée n'aurait pas traité le goulet principal.
- Le format F4 est donc conservé. Une sélection temporaire DuckDB réutilise les IDs et payloads
  candidats, sans liaison répétée de milliers d'IDs Python ni double scan. Le grand cas passe
  de 19,064 à 12,703 s HTTP, le respiratoire de 5,653 à 4,300 s ; les tailles des runs et les
  sorties d'or restent identiques. Le pic RSS du grand cas augmente d'environ 121 Mo.
- `v0.7-G` reste une revue humaine à faire. Aucun scoring, snapshot, reçu, statut clinique ou
  règle safety n'est modifié. La [mesure et les limites](reports/v0.7-f5-run-persistence.md)
  indiquent que la matérialisation d'environ 152 000 assertions/provenances par grand cas
  maintient la latence au-dessus de 10 s.

## Transport HTTP paresseux `v0.7-F4` — 25 septembre 2026

- Après revue technique et CI Linux/Windows verte, les PR #9 (F3) puis #10 (outil de revue)
  ont été fusionnées dans `main`. F4 part de ce `main` sur
  `codex/v0.7-f4-lazy-result-payload`, sans modifier snapshot, manifeste, profil ou scoring.
- La vue simple demande un résumé HTTP de 20 candidats au maximum, puis le détail et toute sa
  provenance au clic. Le run complet reste immuable sur disque et accessible par `/expert`.
  Un index auxiliaire d'offsets avec vérification SHA-256 évite de recharger ses 206 Mo pour
  le résumé ou le détail ; les anciens runs restent compatibles.
- Sur le grand cas fictif de 3 650 candidats, la route est passée de 22,912 à 18,538 s et la
  réponse initiale d'environ 206 Mo à 14 072 octets. Le détail mesure 198 312 octets et
  0,112 s. La baisse de mémoire/temps de parsing navigateur n'a pas été mesurée. Le diagnostic
  et l'écriture du run complet restent la limite principale.
- Tests de transport : résumé, limite top 20, détail exact, reprise, abstention, run/candidat
  absent, intégrité, accès expert complet. Le [rapport F4](reports/v0.7-f4-result-transport.md)
  donne le protocole et les limites. Les statuts `research_unreviewed: true`,
  `clinical_validation: false`, `publishable: false` et `safety: not_evaluated` sont inchangés.

## Outil de revue humaine G1/G2 — 25 septembre 2026

- Après fusion des PR #7 et #8 dans `main`, ce chantier est isolé sur
  `codex/v0.7-g-review-ui`, séparé du durcissement F3 et du symptom checker.
- Une interface locale et offline présente une ligne à la fois parmi les 1 327 pistes G1,
  120 assertions MedlinePlus G2 et 40 dépendances Monarch/Orphadata G2. Les trois CSV et le
  résumé sont vérifiés par SHA-256 ; une modification en cours de session bloque une décision.
- Chaque choix explicite requiert nom, identifiant et attestation du réviseur. Les événements
  horodatés sont ajoutés à un journal local chaîné par hash, sans effacer les corrections ;
  l'export déterministe reste hors Git. Aucun choix n'est prérempli, aucun reviewer n'est
  inventé dans les exports réels. Les identités des tests sont purement synthétiques.
- L'[ADR 0012](decisions/0012-outil-local-de-revue-humaine.md) et la
  [documentation](v0.7-g-review-ui.md) explicitent la frontière : aucune écriture dans le
  snapshot, aucun `approved` canonique ni changement de `clinical_validation` ou `publishable`.
  L'identité est déclarative ; la qualification doit être contrôlée humainement. G1/G2 et G3
  restent à réaliser par l'équipe clinique.
- Le vrai jeu d'exports a été ouvert sans décision : 1 327 / 120 / 40 lignes, zéro revue. Le
  parcours Edge à 390 et 1 280 px fonctionne sans débordement ni requête externe, sans action
  présélectionnée ; le changement de jeu et le passage à la ligne suivante ont été vérifiés.

## Latence du diagnostic `v0.7-F3` — 25 septembre 2026

- Les PR #7 (revue ciblée G1/G2, sans décision humaine) et #8 (parcours simple `/`, console
  `/expert`) ont été relues, synchronisées et fusionnées dans `main` après CI Linux/Windows verte.
  F3 est isolée sur `codex/v0.7-f3-runtime-latency` ; l'outil de revue humaine relève d'une autre
  branche.
- Le profil du vrai snapshot, sur une session fictive après réponse à une question, mesure
  292,123 s pour le diagnostic, dont 288,160 s dans `candidate_rows()` ; la question prend
  2,679 s. Des listes de ~26 000 identifiants passées comme paramètres DuckDB `VARCHAR[]`
  coûtaient ~16 s chacune, bien davantage que leurs requêtes.
- Les identifiants de dérivation, assertions sources et records sont désormais sélectionnés
  par tables temporaires et jointures DuckDB locales. Le même cas prend 15,629 s pour le
  diagnostic ; le cas respiratoire passe de 50,396 à 4,009 s. Les empreintes JSON avant/après
  et les sept cas d'or restent strictement identiques ; le snapshot, la formule et les statuts
  médicaux restent inchangés.
- Une requête HTTP locale complète sur le grand cas prend encore 23,59 s et renvoie ~206 Mo
  pour 3 650 candidats. Cette limite résiduelle est documentée, sans masquer la provenance ou
  réduire les résultats. Le [rapport F3](reports/v0.7-f3-runtime-latency.md) donne le protocole,
  les chiffres de mémoire et les commandes de reproduction.

## Parcours simple local et mode expert — 25 septembre 2026

- Après revue et fusion de la PR #6 (`v0.7-G0`) dans `main`, le chantier UI est isolé sur
  `codex/latros-modern-ui` ; la revue ciblée G utilise une autre branche/PR. Aucun snapshot,
  manifeste, profil ou moteur de raisonnement n'est modifié ici.
- `/` présente une sélection explicite des concepts locaux, l'âge, les questions fournies par
  `general_v1`, des résultats sans pourcentage, un détail facultatif et l'historique local.
  `/expert` conserve la console v0.6 et toutes ses inspections. Les deux vues utilisent les
  sessions/runs et le backend existants ; aucune extraction NLP ni règle clinique frontend.
- L'[ADR 0011](decisions/0011-parcours-simple-local.md) réévalue React/Vite et conserve pour cette
  tranche Jinja2/CSS/JavaScript natif, sans CDN, télémétrie, Node runtime ou nouvel asset distant.
  Les avertissements `research_unreviewed` et `safety.status = not_evaluated` restent visibles.
- Contrôles locaux : 151 tests Python verts, Ruff, mypy strict, schémas et registre v0.7 verts ;
  recherche et parcours mobile vérifiés dans Edge sur `127.0.0.1`, avec les requêtes hors boucle
  locale refusées. Diagnostic réel, détail, reprise de question, abstention sans âge et erreur de
  snapshot absent ont abouti ; une question a été répondue et a conduit à une seconde question.
  Après cette réponse, un autre diagnostic réel dépassait 120 s
  lors du contrôle navigateur : le chargement reste visible, mais cette latence du grand corpus
  est une limite technique à traiter séparément. Le test API synthétique question/réponse/analyse
  passe. Les trois sessions fictives de vérification ont été archivées sous `data/staging/`, hors
  Git, sans toucher aux sessions antérieures. Ces vérifications ne sont pas une validation clinique.
- Les libellés du catalogue sont parfois anglais. Le classement expérimental reste peu
  discriminant et sans prévalence ; aucune promotion clinique ou publication n'est autorisée.

## Préparation de la revue ciblée `v0.7-G1/G2/G3` — 25 septembre 2026

- Après revue du diff et nouvelle exécution des 150 tests, Ruff, format, mypy et schémas, la PR
  #6 (`v0.7-G0`) a été fusionnée dans `main` au commit `767b522`. La CI Linux et Windows était
  verte. Les chantiers médical et interface repartent de ce `main` sur deux branches distinctes.
- Un exporteur offline vérifie le snapshot immuable et le hash des 7 736 candidates MedlinePlus,
  interroge DuckDB en lecture seule, puis génère localement trois CSV et un classeur de revue.
  G1 couvre 689 topics bloqués (5 106 candidates) par 1 327 lignes d'hypothèses ou d'absence de
  piste : 334 topics ont au moins une piste lexicale ou xref MeSH, 355 aucune par ces méthodes.
- G2 échantillonne 120 candidates MedlinePlus éligibles et 40 assertions Monarch/Orphadata avec
  amonts, agrégateurs et dépendances. Les 120 candidates MedlinePlus sont toutes positives ; la
  source ne fournit aucun négatif. Aucune prévalence fiable ne permet d'attester une strate de
  maladies fréquentes. Les champs de décision et de réviseur sont vides.
- Le [protocole G3](reports/v0.7-g-targeted-review.md) sépare tests logiciels, évaluation
  expérimentale sur cas synthétiques indépendants et validation clinique humaine. Le corpus G3
  n'est pas constitué. En l'état, la décision méthodologique est `NO-GO` pour une publication
  clinique ; aucune décision humaine ni promotion `approved` n'a été simulée.
- Le snapshot `v0.7.0-general-dev-unreviewed`, son manifeste, le scoring et les statuts
  `clinical_validation: false`, `publishable: false`, `research_unreviewed: true` et
  `safety_status: not_evaluated` ne sont pas modifiés. Les CSV/classeur générés restent sous
  `data/staging/` et hors Git.
- La revue technique de la PR #7 a ajouté un garde-fou : une régénération byte-for-byte identique
  conserve les fichiers, mais un CSV/résumé modifié par un humain n'est jamais écrasé. Les sorties
  sont limitées à `data/staging/` ; un test vérifie explicitement le refus d'écrasement.
- Contrôles locaux : Ruff, format, mypy strict, export des schémas et 155 tests verts. Les trois
  CSV ont des SHA-256 identiques sur deux générations ; l'export réussit aussi avec les connexions
  socket bloquées. Le classeur a été inspecté et rendu feuille par feuille, sans erreur de formule.

## Audit structurel préparatoire `v0.7-G0` — 25 septembre 2026

- La PR #5 du durcissement `v0.7-F2` a été relue, contrôlée et fusionnée dans `main` au commit
  `2a736a1`. Le travail G0 a ensuite commencé sur la branche distincte
  `codex/v0.7-g0-quality-audit`.
- Un script reproductible interroge le vrai DuckDB v0.7 en lecture seule, sans charger le modèle
  canonique en Python et sans réseau. Il mesure sources, relations, polarités, densité par maladie,
  mappings, familles de preuve, dépendances, domaines et égalités de scores ; il prépare localement
  60 lignes stratifiées non revues, hors Git.
- Sur 15 611 maladies avec assertions, 14 661 sont liées structurellement à Orphanet ou à une
  hiérarchie génétique ; cette mesure n'est **pas** une estimation de prévalence. 193 ont une
  assertion MedlinePlus sans ces marqueurs et 757 restent non classées. 13 098 maladies ont au
  moins cinq assertions, 10 938 au moins dix et 7 286 au moins vingt.
- Les 7 736 candidats MedlinePlus comprennent 2 630 techniquement éligibles. Les 5 106 rejets
  proviennent du mapping maladie : 3 408 non résolus, 1 698 ambigus. MedlinePlus est la seule
  source de 163 maladies, mais sa famille `unknown` n'est pas agrégeable par `general_v1`.
  Monarch relaie 114 839 associations d'amont Orphanet ; 114 269 paires correspondent à
  Orphadata après crosswalk exact et ne constituent pas une corroboration indépendante.
- Seules 706 maladies portent un négatif. Le cas synthétique respiratoire produit 696 candidats,
  dont 692 au score `+1` ; aucune mathématique du moteur n'a été changée. Le
  [rapport G0](reports/v0.7-general-quality-audit.md) décrit la méthode, les limites, les
  domaines sous-couverts et l'organisation proposée de la revue humaine.
- Le snapshot et son hash `bfda708aba44dcc5d12896ac7523d9d6bb577dea53bdc3810e499c15f64b1fb0`
  restent immuables. Zéro assertion approuvée ; `clinical_validation: false`,
  `publishable: false`, `research_unreviewed: true` et `safety_status: not_evaluated` restent
  inchangés. `v0.7-G` reste à faire.
- Vérifications locales : Ruff, format, mypy strict, export des schémas, registre v0.7 et 150 tests
  passent. Deux exécutions du script sur le vrai snapshot produisent le même SHA-256 de
  l'échantillon de 60 lignes ; une troisième avec les connexions socket bloquées réussit aussi.
  Les sorties générées restent ignorées par Git.

## Durcissement runtime généraliste `v0.7-F2` — 24 septembre 2026

- Avant toute optimisation, le snapshot réel a été profilé : lecture complète des treize tables,
  2 681 410 modèles canoniques Pydantic retenus, recherche initiale d'environ 57 s, premier
  diagnostic multi-système d'environ 176 s et pic RSS mesuré à 10,97 Go. La vérification forte
  des fichiers prenait 1,20 s. Les sept diagnostics et questions synthétiques ont été figés par
  empreintes du JSON complet avant changement.
- Un repository DuckDB v2 en lecture seule interroge maintenant le runtime existant. Il résout
  les observations, présélectionne les candidats pouvant scorer, charge leurs seules assertions
  et provenances, et calcule la question discriminante côté DuckDB. Le catalogue de l'interface
  utilise des requêtes ciblées au lieu de rappeler `read_knowledge_v2()`.
- La stratégie `general_v1` garde ses mathématiques et son ancien chemin complet comme référence
  de comparaison dans les tests. Les sept diagnostics et les sept questions du snapshot réel ont
  les mêmes empreintes avant/après, reçus et provenance compris. Les tests synthétiques bloquent
  le réseau ; le profil réel refuse également toute connexion. L'intégrité forte initiale reste
  inchangée et un cache borné vérifie les attributs des fichiers à chaque réutilisation.
- Le snapshot `v0.7.0-general-dev-unreviewed`, son manifeste et son hash de contenu ne sont pas
  modifiés. Les statuts `unreviewed`, `clinical_validation: false`, `publishable: false` et
  `safety_status: not_evaluated` restent inchangés. `v0.7-G` n'a pas commencé.
- Les mesures détaillées, les commandes de reproduction, les contrôles et les limites résiduelles
  sont dans le [rapport runtime](reports/v0.7-runtime-performance.md). Le pilote ORL n'est pas
  restauré comme fondation de ce snapshot.
- Ruff, format, mypy, schémas, registres et 150 tests locaux passent. Le build/inspect de
  l'identifiant v0.7 existant réussit offline et conserve son hash. La console HTTP `127.0.0.1`
  a exécuté deux diagnostics, une question, la consultation de provenance, la reprise et le
  changement de snapshot ; le serveur a ensuite été arrêté.

## Premier snapshot généraliste souverain — 21 septembre 2026

- Le registre `sources/registry-general-v0.7.yaml` épingle sept sources et huit artefacts : HPO
  2026-09-01, Mondo 2026-09-01, DOID 2026-08-31, Orphadata 2026-07, MeSH 2026,
  MedlinePlus 2026-09-19 et Monarch KG 2026-09-02. Les tailles, URLs officielles, licences et
  SHA-256 exacts sont consignés ; aucun lien `latest` n'entre dans le manifeste.
- Les importeurs locaux ajoutent les descriptors, synonymes et hiérarchies MeSH sans assertion
  diagnostique, puis 266 957 associations Monarch maladie–phénotype avec source primaire,
  agrégateur et locator. Les assertions Orphanet republiées par Monarch partagent une famille de
  dépendance au lieu de compter comme confirmations indépendantes.
- Les 2 033 topics MedlinePlus anglais et espagnols sont conservés comme records. L'extracteur
  déterministe anglais produit 7 736 candidats HPO exacts ; 2 630 ont des mappings maladie et objet
  techniquement exacts, 5 106 restent rejetés/auditables, et aucun candidat n'est cliniquement
  approuvé. Les pages espagnoles ne sont pas soumises au matcher HPO anglais.
- Le snapshot `v0.7.0-general-dev-unreviewed` contient 106 835 concepts, 55 243 maladies,
  500 093 désignations, 47 423 mappings, 416 764 records sources, 386 251 assertions sources et
  385 886 assertions canoniques. Le manifeste porte `clinical_validation: false`,
  `publishable: false`, `research_unreviewed: true` et le hash de contenu
  `bfda708aba44dcc5d12896ac7523d9d6bb577dea53bdc3810e499c15f64b1fb0`.
- Un profil `general_v1-general-unreviewed` lie explicitement ce snapshot. Le service applicatif
  met en cache sa stratégie lourde dans un même processus. Sept cas synthétiques couvrent tableau
  respiratoire, ambiguïté, hors corpus, insuffisance, vide, contradictions et multi-système ; le
  pilote ORL reste une régression historique séparée.
- La reconstruction complète a réussi depuis `data/raw/` sans accès réseau. Les gros dumps, Parquet,
  DuckDB et candidats de staging restent ignorés par Git. Le rapport de couverture détaille les
  métriques et rappelle que ce corpus plus vaste n'est pas une validation médicale.
- Limite détectée : le chargement Python/Pydantic complet du runtime de près de 2 Go prend plusieurs
  minutes et peut dépasser 10 Go de mémoire lors du premier diagnostic. L'interface fonctionne et
  réutilise ensuite le cache, mais une lecture DuckDB paresseuse est nécessaire avant tout usage
  plus large.
- Vérifications finales : registre et schémas valides, Ruff et formatage verts, mypy strict sur 46
  fichiers, **146 tests** réussis avec blocage réseau, reconstruction complète puis second build
  idempotent au même hash de contenu, question adaptative réelle marquée `research_unreviewed` et
  `safety: not_evaluated`, interface locale HTTP 200 avec le couple v0.7/general_v1 disponible.

## Fondation de la fabrique souveraine généraliste — 20 septembre 2026

- `main` a été resynchronisée au commit `4025beb` puis le travail a commencé sur
  `codex/sovereign-general-kb`. Le dossier local non suivi `FUTUR INTERFACE/` a été préservé.
- L'ADR 0009 interdit les API médicales pendant build, runtime, diagnostic, questions, interface et
  consultation des sources. Seul un `sources fetch` explicite peut utiliser le réseau.
- L'audit officiel retient MedlinePlus Health Topics XML complet, MeSH XML annuel et les releases
  datées Monarch. CDC est marqué `NOT SUITABLE FOR SOVEREIGN INGESTION` pour cette tranche.
- Le registre v2 exige désormais, lors de sa validation, un producteur, un importeur, des rôles
  fermés et des droits de transformation documentés. Il accepte les formats MedlinePlus, MeSH,
  Monarch/KGX, JSONL et RDF nécessaires, ainsi qu'une identité de capture datée. Les champs restent
  optionnels lors de la lecture des anciens manifestes afin de préserver leur immutabilité.
- Un contrat séparé `CandidateAssertion` conserve source, locator, hashes, sujet/objet, prédicat,
  polarité, contexte, temporalité, quantité/unité, familles/dépendances, mappings proposés,
  extracteur, statut de revue et transformations. Un candidat d'agent n'est jamais utilisable ; une
  approbation exige des reviewers et des mappings résolus `exact/equivalent`.
- Un parseur streaming MedlinePlus lit uniquement un fichier XML local, refuse réseau et DTD,
  détecte les doublons et conserve titres, synonymes, MeSH, résumé, groupes, liens et locator exact.
  Il ne crée aucune assertion clinique approuvée.
- L'identifiant `v0.7.0-general-dev-unreviewed` est réservé mais non construit. Les dumps, hashes
  réels, importeurs MeSH/Monarch, normalisation, déduplication, profil et métriques restent à faire.
- Vérifications hors réseau : Ruff et formatage verts, mypy strict sur 43 fichiers, schémas à jour,
  **143 tests** réussis avec blocage de DNS, `create_connection` et des connexions socket hors
  loopback ; les sockets internes `127.0.0.1`/`::1` nécessaires à l'interface locale restent permis.
  L'ancien manifeste ORL reste lisible sans réécriture. Un démarrage réel de l'interface sur
  `127.0.0.1:8768` a retourné HTTP 200 avec le titre Latros et le statut safety visible.

## Tutoriel utilisateur et rangement documentaire — 19 septembre 2026

- Un [tutoriel complet](tuto.md) décrit l'installation, la reconstruction ou l'inspection des deux
  snapshots, deux essais guidés dans l'interface, les états d'observation, les questions
  adaptatives, les sessions, la lecture des résultats, les tests et le dépannage.
- Un [index documentaire](README.md) sépare démarrage, suivi du projet, décisions, audits, revues et
  contrats machine-readable.
- La vision, l'historique et le logo sont rangés respectivement sous `docs/projet.md`,
  `docs/history.md` et `docs/assets/latros-logo.svg`. Tous les liens et les consignes de continuité
  ont été ajustés ; la racine ne conserve que les entrées et fichiers techniques conventionnels.
- Cette réorganisation ne modifie aucun code, snapshot, profil, manifeste, corpus, statut de revue
  ou calcul médical. Les sessions et les données locales restent hors Git.
- L'ancienne maquette locale `FUTUR INTERFACE/`, non suivie par Git et désormais remplacée par
  l'implémentation autonome `src/latros/ui/`, a été supprimée à la demande du propriétaire. La règle
  d'ignorance correspondante a également été retirée. Cette suppression n'est pas récupérable par
  Git, puisque le dossier n'y avait jamais été versionné.
- Vérifications locales : tous les liens Markdown relatifs et le logo du README se résolvent,
  `git diff --check` est propre, Ruff et le formatage réussissent, mypy valide 41 fichiers, les
  schémas et le registre sont valides et les **138 tests** réussissent. Un démarrage réel sur le
  port local `8767` retourne HTTP 200 avec le titre R&D et l'avertissement non revu attendus.

## Interface locale R&D et sessions — 18 septembre 2026

- La branche `feat/v0.6-rd-interface` part du commit v0.5 documentaire `8321b12` et porte le paquet
  à `0.6.0` sans modifier les données ou les mathématiques de raisonnement.
- `ResearchApplicationService` devient l'orchestrateur commun de la CLI et de l'interface. Les
  sorties d'or v1 restent inchangées ; aucun score n'est calculé dans le navigateur.
- FastAPI/Uvicorn sert une console Jinja2/JavaScript native uniquement sur `127.0.0.1`. Il n'existe
  ni option d'écoute publique, ni CORS, OpenAPI, CDN, télémétrie ou appel Internet.
- La découverte n'autorise que les couples snapshot/stratégie compatibles et présents. Le catalogue
  ne propose que les concepts utilisables par le moteur sélectionné.
- L'éditeur couvre âge, sexe, observations confirmées et les distinctions `present`, `absent`,
  `unknown`, `not_assessed` et `unable_to_assess`. Une réponse adaptative devient une observation
  confirmée avec provenance `question_response` ; aucune question n'est inventée par l'UI.
- Les résultats affichent abstention, couverture, compatibilité non calibrée, contributions,
  contradictions, sources, familles, mappings, provenance et reçu. Safety reste
  `not_evaluated` et n'est jamais reformulé comme une assurance.
- Le panneau du snapshot ORL affiche sans masquage `research_unreviewed: true`,
  `clinical_validation: false`, `publishable: false`, 17 assertions et 10 mappings non revus. Le
  gate officiel `v0.5.0` et tous les statuts de revue restent inchangés.
- Les sessions utilisent le schéma `ui-session-v1`. L'état courant est écrit atomiquement dans
  `sessions/<id>/session.json`; chaque analyse/question est un run immuable qui garde le cas et le
  résultat v2 exacts. Le dossier reste hors Git et n'est pas présenté comme stockage sécurisé.
- À la livraison initiale, le dossier de maquette n'avait été ni modifié ni versionné. Le logo, la
  palette et certains motifs de panneaux ont été adaptés dans des actifs neufs sous
  `src/latros/ui/`; aucune donnée ou sortie fictive n'a été copiée. Le dossier a ensuite été
  supprimé le 19 septembre 2026.
- L'ADR 0008 et `docs/v0.6-rd-interface.md` documentent l'architecture, le transport interne, les
  sessions et les limites. Le Knowledge Graph avancé reste reporté.
- Vérifications locales : Ruff, formatage, mypy strict, schémas, syntaxe JavaScript, aide CLI, wheel
  contenant les actifs/profils et **138 tests** réussis. Un parcours réel temporaire sur
  `v0.5.0-dev-unreviewed` a produit un résultat marqué non revu avec safety `not_evaluated`. Le rendu
  desktop et le panneau non revu ont été vérifiés dans le navigateur local.
- La CI GitHub du commit `cd3a787` est verte sous Ubuntu et Windows au run `#35337846570` : Ruff,
  formatage, mypy, schémas, suite pytest et validation des sources ont tous réussi.

## Roadmap interface R&D et Knowledge Graph — 18 septembre 2026

- La roadmap future est décalée : **v0.6** est une interface interne R&D simple ; temporalité,
  biologie, constantes, risques et médicaments passent en **v0.7**, le safety/triage en **v0.8**, le
  NLP/LLM en **v0.9** et l’API/FHIR/interopérabilité en **v0.10**.
- La première v0.6 inspectera seulement les contrats et moteurs existants. Elle n’est ni une
  interface patient, ni un produit médical validé, ni une nouvelle logique clinique.
- Une vue Knowledge Graph avancée est planifiée comme évolution ultérieure, non bloquante pour la
  première v0.6. Elle devra projeter exclusivement les observations, concepts, assertions,
  contributions, mappings, sources et provenances réellement présents ; elle ne créera pas de
  relations ou preuves décoratives.
- À cette date, **FUTUR INTERFACE/** était encore ignoré par Git, intact et non versionné ; il
  n’avait été ni lu, ni modifié, ni ajouté pendant cette mise à jour documentaire. Il a été supprimé
  le 19 septembre 2026 après livraison de l'interface autonome.
- Vérification réalisée : git diff --check. Aucun code fonctionnel, snapshot, artefact médical ou
  donnée patient n’a été modifié.

## Identité visuelle — 17 septembre 2026

- Le logo officiel `latros-logo.svg` est versionné à la racine du dépôt et affiché dans le README.
- Il s'agit uniquement d'un actif de documentation : aucun contrat clinique, snapshot, moteur ou résultat de raisonnement n'est modifié.

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

La vision complète, y compris les futures pistes LLM, est dans [projet.md](projet.md). Les décisions applicables à la tranche actuelle sont dans [ADR 0001](decisions/0001-socle-recherche.md).

## Dépôt et manière de travailler

- Dépôt GitHub privé : `GaetanAff/Latros`.
- Branche stable : `main`, actualisée avec les jalons livrés v0.1 à v0.4.
- L'implémentation v0.4 a été effectuée sur `feat/v0.4-clinical-knowledge-model`, puis fusionnée par la [pull request #2](https://github.com/GaetanAff/Latros/pull/2).
- Commit de fusion dans `main` : `2315431ee62d9fce887812004c9fae89e5e5d20d` — 17 septembre 2026.
- Les quatre contrôles GitHub (push et pull request, Linux et Windows) sont réussis pour le commit final `920a882`.
- Le dossier local non suivi `FUTUR INTERFACE/` était présent dans l'espace de travail et n'a été ni lu, ni modifié, ni ajouté au commit.

Les règles de contribution sont dans [CONTRIBUTING.md](../CONTRIBUTING.md) : branche par fonctionnalité, pull request, `main` stable, aucune donnée de santé ou base brute dans Git.

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
- [sources/registry.yaml](../sources/registry.yaml) est le registre versionné des sources, licences, attributions, produits, dépendances amont et hashes.

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

Le manifeste canonique de la première livraison était [latros-kb-0002.json](../manifests/latros-kb-0002.json). Il est conservé ; la référence actuelle est [v0.2.0.json](../manifests/v0.2.0.json), établie avec les mêmes données sous le nom du jalon du plan. Les snapshots complets sont locaux et ignorés par Git.

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

Les poids internes du questionnement sont uniquement un outil d'utilité : ils ne sont pas présentés comme probabilités de maladies. La méthode complète, équations et limites sont dans [methodology.md](methodology.md).

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

L'exemple [case.synthetic.json](../examples/case.synthetic.json) est inventé. Il sert seulement à démontrer le format d'entrée. La CLI ne comprend pas encore une phrase libre telle que « j'ai mal à l'oreille » : cette future normalisation reste hors de la tranche actuelle.

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

Un [cahier des charges dédié](v0.4-clinical-knowledge-model.md) est créé sur la branche `docs/v0.4-clinical-knowledge-model`. Il décrit les invariants, le futur modèle clinique, le Knowledge Model, la provenance, le non-double-comptage, l'architecture multi-stratégies, les tests, les critères d'acceptation et les checkpoints `v0.4-A` à `v0.4-H`.

Décision de périmètre : le snapshot `v0.2.0` et `semantic_v1` restent spécialisés maladies rares. Ils ne couvrent pas correctement une plainte courante comme fièvre et mal de gorge. `v0.4` doit préparer l'architecture générale sans import massif ; `v0.5` doit réaliser une première extension étroite vers la médecine générale avec des sources auditées et une stratégie dédiée. Les futurs référentiels ne seront sélectionnés qu'après analyse de leur rôle, licence, provenance, dépendances et risque de double comptage.

Cette livraison est uniquement documentaire : aucun code, schéma, test, manifeste ou snapshot de données n'est modifié. Le socle actuel et la référence `v0.2.0` restent inchangés.

### 17 septembre 2026 — Première veille des ressources de médecine générale

Une liste proposée par un autre LLM est vérifiée avant d'être ajoutée au plan. Le cahier des charges distingue désormais les terminologies, classifications, mappings, standards d'échange, assertions cliniques, recommandations, cas synthétiques, données réelles restreintes et applications complètes.

Corrections importantes : SNOMED CT est une terminologie clinique et non une matrice de probabilités ; les mappings SNOMED–ICD servent à la classification et au reporting, pas à déduire une maladie depuis un symptôme ; FHIR est un standard d'échange ; HealthBench contient des conversations réalistes générées ou adversariales et non 5 000 conversations de patients réels ; ClinicDx est une application LLM/RAG à surveiller, pas une base de connaissances validée.

Les jeux Kaggle « Symptoms to diseases », Mendeley « Disease and symptoms dataset 2023 » et SymbiPredict sont conservés comme pistes d'exploration uniquement. Leur format et leur licence déclarée ne compensent pas une provenance médicale insuffisante. DDXPlus est mieux documenté et peut devenir un benchmark synthétique de `v0.5`, mais pas la vérité clinique du moteur. Synthea, WHO SMART Guidelines, LOINC/UCUM, MIMIC-IV et les autres ressources sont répartis entre les étapes `v0.5` à `v0.10` selon leur rôle.

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
snapshot médical v2 n'est publié. La maquette, les données sources, les artefacts générés et toute
donnée patient restent hors de la branche. Le logo officiel versionné est limité à la documentation.
La prochaine ingestion réelle reste bloquée par le `NO-GO` v0.5 documenté ; seules les fixtures
synthétiques ou la levée formelle des conditions de licence et de revue sont autorisées.

### 17 septembre 2026 — publication du logo et fusion de v0.4

Le logo officiel `latros-logo.svg` est ajouté au dépôt et affiché dans le README. Il ne modifie ni
le moteur, ni les contrats, ni les données médicales.

La pull request [#2 — v0.4 Clinical Knowledge Model](https://github.com/GaetanAff/Latros/pull/2)
est fusionnée dans `main` après réussite des contrôles GitHub Linux et Windows, pour les événements
`push` et `pull_request`. Le commit de fusion est `2315431ee62d9fce887812004c9fae89e5e5d20d`.

### 17 septembre 2026 — exigence médicaments et molécules (initialement v0.6, décalée en v0.7)

Le cahier des charges avait initialement placé en `v0.6` la distinction entre exposition rapportée
ou observée chez le patient,
la substance active, le produit ou la présentation commercialisée et la classe thérapeutique. Les
indications, effets indésirables, contre-indications, interactions et contraintes d'usage devront
être des assertions médicales séparées, versionnées et traçables jusqu'à leurs sources ; elles ne
seront jamais déduites d'un mapping ou d'un identifiant de produit.

ATC, RxNorm et un référentiel français de produits sont seulement des candidats à auditer avant toute
ingestion. Les critères obligatoires sont la couverture, l'autorité éditrice, la version, la licence,
la redistribution, les identifiants stables et la reproductibilité. Les tests restent synthétiques
tant que cette revue n'est pas close. Cette décision n'autorise ni prescription, ni calcul de dose,
ni recommandation de traitement, ni vérification d'interactions.

La roadmap du 18 septembre 2026 conserve intégralement cette exigence mais la décale en `v0.7` ;
`v0.6` devient d’abord une interface interne R&D sans nouvelle logique médicale.

### 17 septembre 2026 — v0.5-A, contrats du snapshot canonique v2

L'ADR 0005 retient un snapshot ORL adulte séparé de la référence maladies rares. Le registre v2
distingue artefacts HTTPS publics et dépôts manuels, refuse les URLs mobiles, les licences non
revues et les droits d'implémentation non confirmés. Il ne contient aucun mécanisme de stockage de
secrets.

Le manifeste v2 rend obligatoires le périmètre, la population, les sources, licences, dépendances,
familles de preuves, règles, tables, profils compatibles, restrictions de redistribution et hashes.
Deux schémas JSON sont exportés. Quatre tests synthétiques couvrent ces contrats ; aucun importeur,
artefact médical, manifeste `v0.5.0` ou snapshot réel n'est ajouté.

### 17 septembre 2026 — v0.5-B, constructeur canonique v2 synthétique

Un stockage v2 séparé publie les treize collections du Knowledge Model sous forme de tables Parquet
triées et d'un runtime DuckDB en lecture seule. Chaque ligne contient un identifiant stable et le
JSON canonique du contrat complet. Le manifeste lie hashes logiques, hashes Parquet, périmètre,
règles, sources et profils ; l'intégrité du conteneur DuckDB reste dans un reçu local distinct.

Le constructeur vérifie tous les artefacts bruts, l'alignement du registre et des objets sources,
l'immuabilité de l'identifiant, la reconstruction depuis un manifeste épinglé et les checksums au
chargement. Cinq tests supplémentaires emploient seulement des concepts et assertions inventés.
Le pipeline v1 n'est pas appelé ni modifié et aucun snapshot médical `v0.5.0` n'est créé.

### 17 septembre 2026 — v0.5-C, import RF2 et assertions curées

Un chargeur versionné distribue désormais registres et manifestes entre les pipelines v1 et v2.
La CLI peut valider, préparer, construire et inspecter un registre v2 sans modifier les commandes
historiques. Les artefacts `manual_local` doivent être acquis par l'opérateur et sont vérifiés par
hash ; aucun identifiant ou secret d'accès n'est enregistré.

L'importeur RF2 limité lit concepts actifs, descriptions et relations `is_a` d'un sous-ensemble
explicitement préparé. L'importeur JSONL exige une localisation source, un hash du texte, un
curateur et deux relecteurs distincts couvrant les rôles clinique et mapping. Il crée séparément
records, assertions sources, assertions canoniques, dérivations et familles de preuves. Les codes
inconnus, doublons, cycles, colonnes manquantes et revues invalides sont refusés.

Le schéma du paquet de curation est versionné. Sept tests supplémentaires portent la suite à 108
tests attendus après ajout des contrôles d'accès public et manuel. Toutes les données utilisées
restent inventées ; aucun mapping implicite ni contenu thérapeutique n'est importé.

### 17 septembre 2026 — v0.5-D, stratégie générale sur corpus fictif

`general_v1` est ajouté comme stratégie séparée de `semantic_v1`. Il accepte uniquement un
`ClinicalCaseV2` et un snapshot v2 compatible, résout les concepts identiques ou les mappings
`exact/equivalent`, puis compare les observations confirmées aux polarités explicites des assertions.
Les valeurs `unknown`, `not_assessed` et `unable_to_assess` restent sans contribution numérique.

Le score `general_v1.compatibility` est borné entre `-1` et `1`, non calibré et explicitement distinct
d'une probabilité. Les contributions sont moyennées par famille de preuve ; seules les familles
indépendantes et pondérées par le profil entrent dans l'agrégat. Les sources, contradictions,
mappings, éléments ignorés, couverture et reçus restent inspectables. Une dépendance inconnue est
visible mais exclue du score.

Le moteur s'abstient hors population adulte, sans âge exploitable, sous le seuil de couverture ou
avec moins de deux observations évaluées. Le questionnement exige des assertions de polarités
opposées entre au moins deux candidats ; l'absence d'assertion n'est jamais convertie en négation.
Neuf tests ciblés portent la suite à 117 tests verts. Les fixtures, libellés, codes, candidats et
familles de preuves sont entièrement inventés ; aucun snapshot médical `v0.5.0` n'est créé.

### 17 septembre 2026 — v0.5-E, audit final et décision NO-GO

Les pages officielles ANS confirment la release française SNOMED CT de juin 2026 au format RF2/OWL,
mais aussi l'obligation d'une licence d'affiliation pour l'implémentation, d'une licence nationale
pour l'édition française et d'un échange avec le NRC pour certains modèles de distribution ou
d'alignement. Aucune preuve d'acceptation ni réponse écrite applicable à Latros n'est disponible dans
le dossier projet.

La page HAS angine conserve des éléments diagnostiques potentiels, dont Mac Isaac et le TDR, mais
son objectif principal est l'antibiothérapie. Les renvois vers rhinopharyngite, sinusite et otite ne
démontrent pas un corpus différentiel suffisant. La règle de sortie exige désormais, pour chacun des
quatre candidats, au moins deux assertions diagnostiques explicites et une assertion discriminante,
avec droits vérifiés et double revue dont un clinicien. Les traitements, molécules, doses et durées
restent exclus.

Le checkpoint E est clos avec décision `NO-GO`. Les composants techniques A à D demeurent valides
sur fixtures, mais F (snapshot médical `v0.5.0`) et G (validation et clôture) ne sont pas commencés.
Aucun registre médical réel, contenu protégé, manifeste `v0.5.0` ou score clinique n'est publié.

Contrôles GitHub : le [run #30](https://github.com/GaetanAff/Latros/actions/runs/35229429576)
du checkpoint D et le [run #31](https://github.com/GaetanAff/Latros/actions/runs/35229684808)
du checkpoint E ont réussi sur `ubuntu-latest` et `windows-latest`. Les deux avertissements de la
plateforme concernent la transition Node.js interne aux actions GitHub, pas les tests Latros.

### 17 septembre 2026 — v0.5-E2, audit des sources ouvertes

La stratégie du premier snapshot ORL est réouverte sans modifier A à D et sans effacer le `NO-GO`
SNOMED/HAS. L'audit vérifie les releases et licences officielles de Disease Ontology, Mondo et
MeSH, puis les conditions de réutilisation NHS, nidirect, CDC et MedlinePlus. DOID `v2026-08-31`
(CC0) et Mondo `v2026-09-01` (CC BY 4.0) sont retenus pour préparer les identités et mappings ;
MeSH est juridiquement compatible mais différé comme inutile au premier lot.

La revue des pages cliniques produit une matrice condition × assertion × source × famille de
preuve. Le seuil de contenu candidat est atteignable pour les quatre conditions, mais les concepts
aigus doivent être revus explicitement et l'OMA adulte reste moins bien corroborée par des familles
indépendantes. Les pages nidirect issues du NHS sont classées `republication`, les dépendances NLM
non résolues restent non agrégeables et les articles A.D.A.M. sont exclus comme contenu protégé.

Le checkpoint E2 se clôt en `NO-GO` de publication : aucun paquet réel ne possède encore les
captures et hashes, mappings qualifiés, localisations record par record et deux reviewers distincts
dont un clinicien. La voie suivante est un corpus `pending_clinical_review`, pas F ou G. Aucun
registre réel, snapshot `v0.5.0`, profil clinique ou donnée protégée n'est ajouté.

Vérification locale : Ruff, formatage, mypy strict, export des schémas et les 117 tests réussissent.
Les tests d'or v1 et les composants v0.5-A à D restent inchangés.

Contrôle GitHub : le [run #33](https://github.com/GaetanAff/Latros/actions/runs/35233968223)
du checkpoint E2 a réussi sur `ubuntu-latest` et `windows-latest` en 1 min 20 s. Les deux
avertissements concernent la transition Node.js interne aux actions GitHub, pas les tests Latros.

### 17 septembre 2026 — v0.5-E3, corpus réel prêt pour revue humaine

Le paquet `curation/v0.5-orl` matérialise le corpus minimal adulte ambulatoire sans créer de
snapshot. Il contient 17 assertions atomiques : 4 pour la tonsillite aiguë, 5 pour le rhume, 4 pour
la rhinosinusite aiguë et 4 pour l'otite moyenne aiguë. Chaque candidat dépasse le seuil de deux
assertions et d'un discriminant. Les 19 concepts internes et 10 mappings DOID/Mondo conservent les
granularités : angine, pharyngite, tonsillite et pharyngite streptococcique ne sont pas fusionnées ;
les mappings plus larges ou plus étroits restent non scorants.

Douze reçus enregistrent URL, release, date d'accès, licence, attribution, chemin local et SHA-256.
Les captures complètes et la représentation exacte des segments restent dans `data/raw/`, hors
Git. Les assertions proviennent de NHS, de la republication nidirect classée dans la même famille
NHS, et des seules synthèses Health Topics MedlinePlus autorisées. Les dépendances NLM inconnues
restent non agrégeables. Les pages CDC sont retirées du paquet courant tant que la redistribution
internationale n'est pas juridiquement fermée ; ce retrait n'est jamais transformé en preuve
négative.

Un contrat de curation et trois commandes CLI ajoutent l'audit, le tableau de revue et l'export
approuvé. Le gate vérifie artefacts et hashes, droits de réutilisation, provenance record par
record, release/date/localisation, références, doublons, familles, dépendances, mappings, seuils,
hashes des décisions et attestations locales. Une modification après revue invalide la décision.
L'export vers l'importeur v2 est impossible tant que le gate ne passe pas.

Le dossier `docs/reviews/v0.5-orl/` liste chaque assertion et mapping ainsi que le rapport
machine-readable. Aucun reviewer, signature, qualification ou statut `approved` n'est inventé :
`reviewers.jsonl` et `reviews.jsonl` sont vides, les 17 assertions et 10 mappings sont
`pending_review`. Le verdict est `ready_for_human_review` mais `blocked` pour publication.
F et G ne commencent pas ; aucun profil ORL final, manifeste `v0.5.0` ou snapshot médical n'est
créé.

Cinq tests synthétiques supplémentaires vérifient le blocage du paquet pending, l'ouverture du gate
avec double revue attestée, l'invalidation après modification, le refus d'un artefact corrompu et
l'exclusion du contenu thérapeutique. Ruff, formatage, mypy strict, contrôle des schémas et les
122 tests réussissent localement sous Windows. Les tests d'or v1 restent inchangés.

Contrôle GitHub : le [run #35](https://github.com/GaetanAff/Latros/actions/runs/35264450810)
du checkpoint E3 a réussi sur `ubuntu-latest` en 27 s et `windows-latest` en 1 min 18 s.
L'avertissement de plateforme concerne uniquement la transition Node.js interne aux actions
GitHub.

### 18 septembre 2026 — v0.5-E4, mode ORL local explicitement non revu

Un chemin de recherche locale est ajouté sans modifier le gate officiel. La commande
`data build --snapshot v0.5.0-dev-unreviewed --allow-unreviewed-research-data` transforme le paquet
E3 pending en treize tables canoniques, Parquet déterministes et DuckDB local. Elle vérifie les
douze artefacts et leurs hashes, ainsi que les segments, licences, références, seuils et dépendances.
Sans flag, avec un autre suffixe ou avec l'identifiant officiel `v0.5.0`, l'override est refusé.

Le manifeste expérimental conserve la liste exacte des 17 assertions et 10 mappings
`pending_review`, `reviewer_count: 0`, `clinical_validation: false`,
`human_review_complete: false` et `publishable: false`. Les fichiers de revue restent byte-for-byte
inchangés. Les mappings exacts/équivalents résolus peuvent être utilisés techniquement sans être
présentés comme revus ; les relations plus larges/étroites et ambiguës restent non scorantes.

Le profil `general_v1-orl-unreviewed` est limité à ce snapshot. Son unique poids de famille est un
paramètre d'ingénierie ; nidirect reste une republication NHS et les dépendances NLM inconnues ne
sont pas agrégées. Diagnostics et questions portent `research_unreviewed: true`, répètent les
comptes pending dans leur reçu, gardent `general_v1.compatibility` non probabiliste et
`safety.status: not_evaluated`.

Trois tests supplémentaires couvrent l'override, la séparation du gate officiel, l'absence de faux
reviewer ou changement de statut et le marquage des résultats. Le manifeste expérimental et un cas
d'exemple synthétique sont versionnés ; les captures, Parquet, DuckDB et reçus d'intégrité restent
locaux et hors Git. E4 ne démarre ni F ni G : la publication clinique `v0.5.0` reste bloquée par les
revues humaines réelles. Ruff, formatage, mypy strict, schémas et les 125 tests réussissent
localement sous Windows avant push.
