# Historique de Latros

Ce fichier est le journal de continuité du projet. Il décrit ce qui a été décidé et effectivement réalisé, afin de pouvoir reprendre la discussion sans déduire l'état du projet à partir du code seul.

Dernière mise à jour : 16 septembre 2026.

## État actuel en une phrase

Latros est aujourd'hui un prototype local de recherche, utilisable en ligne de commande, qui prend un cas clinique **déjà structuré en identifiants HPO**, classe des maladies rares ORPHA selon une compatibilité sémantique explicable, puis propose une question discriminante. Il n'est ni un chatbot, ni une interface patient, ni un outil de triage ou de diagnostic clinique validé.

## Décisions de cadrage antérieures

- Le projet a été renommé **Latros** ; le nom initial était ClinAtlas.
- La cible à long terme reste un système local, offline-first, avec un moteur médical explicable qui fonctionne sans LLM.
- Les trois états d'un signe sont distincts : `present`, `absent`, `unknown`.
- La provenance, la version, la licence et les identifiants originaux doivent être conservés à chaque étape.
- La première audience est l'équipe recherche/développement, pas des patients.
- Le premier périmètre est les maladies rares, car HPO/Mondo/Orphadata sont structurés pour ce cas.
- MedASR et toute intégration vocale sont retirés du périmètre. En particulier, MedASR n'a pas été intégré en raison de son inadéquation pratique pour une première version destinée à des patients francophones.
- MedGemma est reporté à une couche future facultative de NLP/explication, après validation du moteur pur. TxGemma est reporté à un module thérapeutique séparé, futur et non clinique dans l'état actuel.
- Aucune interface, API web, Docker, LLM local, modèle téléchargé, entraînement, audio ou recommandation thérapeutique n'a été développé dans cette tranche.

La vision complète, y compris les futures pistes LLM, est dans [projet.md](projet.md). Les décisions applicables à la tranche actuelle sont dans [ADR 0001](docs/decisions/0001-socle-recherche.md).

## Dépôt et manière de travailler

- Dépôt GitHub privé : `GaetanAff/Latros`.
- Branche stable : `main`.
- Implémentation effectuée sur `feat/clinical-foundation`.
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

Le manifeste canonique versionné est [latros-kb-0002.json](manifests/latros-kb-0002.json). Le snapshot complet lui-même est local et ignoré par Git.

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

1. Valide et résout les identifiants HPO, synonymes et remplacements uniques.
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

Après installation avec `uv sync --locked --python 3.11` :

```text
latros sources list
latros sources validate
latros sources fetch --source hpo --release 2026-09-01
latros sources fetch --source mondo --release 2026-09-01
latros sources fetch --source orphadata --release 2026-07

latros data build --snapshot latros-kb-0002
latros data inspect --snapshot latros-kb-0002

latros diagnose --snapshot latros-kb-0002 --case examples/case.synthetic.json
latros question next --snapshot latros-kb-0002 --case examples/case.synthetic.json
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

## Prochaine discussion recommandée — sans coder

Avant toute nouvelle implémentation, choisir et documenter le prochain sujet :

1. Évaluation scientifique du moteur sur des cas synthétiques puis un benchmark autorisé et indépendant.
2. Politique d'abstention, périmètre de sécurité et exigences cliniques avant toute interface patient.
3. Ajout raisonné d'HPOA, Monarch ou d'une autre source, avec stratégie de non-double-comptage.
4. Amélioration du score : corrélations entre signes, temporalité, âge, sexe, prévalence, incertitude sur les fréquences et calibrage.
5. Normalisation du texte libre et rôle futur, mesurable et remplaçable, d'un LLM local tel que MedGemma.
6. Évaluation séparée d'un LLM seul, du moteur pur et d'un système hybride.

Ne pas commencer ces chantiers simultanément : le choix le plus prudent est de valider d'abord la qualité et les limites du moteur pur sur un protocole d'évaluation écrit.
