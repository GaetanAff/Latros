# Tutoriel complet — installer et tester Latros v0.6

Ce guide explique comment lancer Latros, essayer ses deux moteurs et comprendre ce que montre
l'interface. Toutes les manipulations sont locales.

> **Attention : Latros est un prototype R&D, pas un dispositif médical.** Il ne réalise aucun
> triage (`safety_status: not_evaluated`), ne donne pas de diagnostic validé et ne doit pas servir à
> conseiller un patient. Utiliser uniquement des cas inventés pour ces essais.

## 1. Comprendre le fonctionnement en une minute

Latros ne demande pas à un LLM d'imaginer un diagnostic. Un cas structuré est comparé à un snapshot
de connaissances versionné par une stratégie déterministe :

```text
navigateur local
    ↓ ClinicalCaseV2
serveur v0.6 sur 127.0.0.1
    ↓
ResearchApplicationService (également utilisé par la CLI)
    ↓
snapshot DuckDB en lecture seule + profil de raisonnement
    ↓
semantic_v1 ou general_v1
    ↓
résultat explicable + provenance + reçu d'exécution
    ↓
session JSON locale et run immuable
```

Le navigateur ne calcule jamais un score. Il saisit un cas, appelle le backend local et affiche la
sortie produite par le moteur.

Deux couples sont aujourd'hui utiles :

| Snapshot | Stratégie | Usage |
| --- | --- | --- |
| `v0.2.0` | `semantic_v1` | Raisonnement phénotypique historique sur les maladies rares |
| `v0.5.0-dev-unreviewed` | `general_v1` | Pilote ORL adulte expérimental, non relu cliniquement |

L'interface interdit les couples incompatibles. Une compatibilité comprise entre `-1` et `1`
n'est ni une probabilité ni un pourcentage de maladie.

## 2. Prérequis

Utiliser Windows ou Linux avec :

- Git ;
- Python 3.11 ;
- `uv` ;
- un navigateur récent.

Vérifier les outils :

```powershell
git --version
python --version
uv --version
```

La version Python doit être 3.11.x. Les commandes suivantes sont écrites pour PowerShell mais sont
identiques dans un shell Linux, hormis le chemin du dossier.

## 3. Installer le projet

### Sur le poste où le dépôt existe déjà

```powershell
cd C:\Users\gaeta\Desktop\Latros
git switch feat/v0.6-rd-interface
git pull --ff-only
uv sync --locked --python 3.11
uv run --no-sync latros --help
```

`uv sync --locked` installe exactement les versions fixées dans `uv.lock`. Ne supprimer ni modifier
ce verrou pour tester un snapshot historique.

### Depuis un nouveau clone

```powershell
git clone https://github.com/GaetanAff/Latros.git
cd Latros
git switch feat/v0.6-rd-interface
uv sync --locked --python 3.11
uv run --no-sync latros sources validate
```

Le dépôt étant privé, GitHub doit être authentifié. Le clone contient le code, les manifestes et les
petites fixtures, mais pas les bases médicales brutes, les snapshots construits ou les sessions.

## 4. Vérifier les snapshots disponibles

Sur le poste de développement actuel, les deux runtimes sont déjà construits. Les commandes
suivantes doivent retourner leurs manifestes :

```powershell
uv run --offline --no-sync latros data inspect --snapshot v0.2.0
uv run --offline --no-sync latros data inspect --snapshot v0.5.0-dev-unreviewed
```

`--offline` garantit que l'opération n'utilise pas Internet. Si un runtime est absent, suivre la
section correspondante ci-dessous.

### 4.1 Construire `v0.2.0` sur un nouveau poste

Cette voie nécessite d'abord les trois sources épinglées :

```powershell
uv run --no-sync latros sources fetch --source hpo --release 2026-09-01
uv run --no-sync latros sources fetch --source mondo --release 2026-09-01
uv run --no-sync latros sources fetch --source orphadata --release 2026-07
uv run --offline --no-sync latros data build --snapshot v0.2.0
uv run --offline --no-sync latros data inspect --snapshot v0.2.0
```

Le téléchargement vérifie les SHA-256 déclarés dans `sources/registry.yaml`. La construction est
ensuite hors réseau et publie localement les Parquet et le runtime DuckDB.

### 4.2 Construire le snapshot ORL expérimental

Le dépôt ne redistribue pas les douze captures locales utilisées par la curation ORL. Elles doivent
être présentes aux chemins et avec les empreintes déclarés dans
`curation/v0.5-orl/sources.json`. Sur un poste autorisé où ces artefacts sont disponibles :

```powershell
uv run --offline --no-sync latros curation audit --package curation/v0.5-orl
uv run --offline --no-sync latros data build --snapshot v0.5.0-dev-unreviewed --allow-unreviewed-research-data
uv run --offline --no-sync latros data inspect --snapshot v0.5.0-dev-unreviewed
```

Le long flag est volontaire. Sans lui, la construction est refusée. Il ne peut jamais servir à
produire le snapshot officiel `v0.5.0`.

Le snapshot expérimental doit toujours annoncer :

- `validation_status: unreviewed` ;
- `clinical_validation: false` ;
- `publishable: false` ;
- 17 assertions et 10 mappings non revus ;
- `reviewer_count: 0` tant qu'aucune vraie revue n'existe.

Un nouveau clone sans les artefacts ORL peut tout de même tester `semantic_v1` avec `v0.2.0` et
exécuter toute la suite automatisée, qui utilise uniquement des données inventées.

## 5. Lancer l'interface

Depuis la racine du dépôt :

```powershell
uv run --offline --no-sync latros --root . ui
```

Le navigateur s'ouvre sur <http://127.0.0.1:8765/>. Conserver le terminal ouvert : il héberge le
serveur. Pour utiliser un autre port ou ouvrir l'adresse manuellement :

```powershell
uv run --offline --no-sync latros --root . ui --port 8766 --no-open
```

Arrêter le serveur avec `Ctrl+C` dans le terminal.

Le serveur écoute uniquement sur la boucle locale. Il n'existe pas d'option d'écoute publique, de
télémétrie, de CDN ou d'envoi automatique vers Internet.

## 6. Essai guidé 1 — pilote ORL expérimental

Cet essai reproduit le cas synthétique `examples/case.orl-unreviewed.json` dans l'interface.

1. Dans **Session**, cliquer sur `+` pour repartir d'une session vide si nécessaire.
2. Choisir le snapshot `v0.5.0-dev-unreviewed`.
3. Choisir la stratégie `general_v1`, puis cliquer sur **Appliquer**.
4. Saisir `30` dans **Âge** et choisir `Inconnu` pour le sexe.
5. Cliquer sur **Enregistrer le cas**.
6. Rechercher puis ajouter comme `Présent · évalué` :
   - `Runny nose` ;
   - `Nasal congestion` ;
   - `Sore throat`.
7. Cliquer sur **Lancer l'analyse**.

Le résultat attendu est un classement déterministe, sans abstention pour ce cas. L'écran doit aussi
afficher, sans possibilité de le masquer :

- `research_unreviewed: true` ;
- `clinical_validation: false` ;
- `publishable: false` ;
- 17 assertions et 10 mappings non revus ;
- `SAFETY STATUS: not_evaluated`.

Cliquer sur un candidat pour ouvrir ses contributions. Une ligne favorable ou défavorable doit
indiquer l'observation, l'assertion, la famille de preuve, la source et la provenance. Une source
dont la dépendance est inconnue peut rester visible tout en étant exclue de l'agrégat.

Pour obtenir exactement la sortie JSON par la CLI :

```powershell
uv run --offline --no-sync latros diagnose --snapshot v0.5.0-dev-unreviewed --strategy general_v1 --case examples/case.orl-unreviewed.json
```

## 7. Essai guidé 2 — moteur historique maladies rares

1. Créer une nouvelle session.
2. Choisir `v0.2.0` et `semantic_v1`, puis **Appliquer**.
3. Rechercher des concepts HPO, par exemple `Seizure`, `Microcephaly` et
   `Intellectual disability`.
4. Ajouter les deux premiers comme présents et le troisième comme inconnu.
5. Lancer l'analyse.

Les candidats gardent leurs identifiants ORPHA. Le score est une compatibilité sémantique historique
et non une probabilité. Pour comparer avec le contrat v1 d'origine :

```powershell
uv run --offline --no-sync latros diagnose --snapshot v0.2.0 --case examples/case.synthetic.json
uv run --offline --no-sync latros question next --snapshot v0.2.0 --case examples/case.synthetic.json
```

## 8. Choisir correctement l'état d'une observation

L'interface garde deux axes distincts. Le libellé choisi produit les combinaisons suivantes :

| Choix UI | `clinical_status` | `evaluation_status` | Sens |
| --- | --- | --- | --- |
| Présent · évalué | `present` | `assessed` | L'élément a été recherché et observé |
| Absent · évalué | `absent` | `assessed` | L'élément a été recherché et non observé |
| Inconnu · évalué | `unknown` | `assessed` | Le sujet ne connaît pas la réponse |
| Non évalué | `unknown` | `not_assessed` | L'élément n'a pas été recherché |
| Impossible à évaluer | `unknown` | `unable_to_assess` | L'évaluation ne peut pas être réalisée |

Les trois formes inconnues restent neutres pour le score. Ne pas utiliser `absent` pour dire « pas
encore demandé ».

## 9. Tester les questions adaptatives

Après avoir enregistré au moins deux observations évaluables :

1. cliquer sur **Question suivante** ;
2. lire la justification et les assertions affichées ;
3. répondre avec un des boutons proposés ;
4. relancer l'analyse.

La réponse devient une observation confirmée avec une provenance `question_response`. Si le moteur
affiche `insufficient_question_evidence`, cela signifie qu'aucune assertion explicite disponible ne
permet de départager correctement les candidats. L'interface n'invente jamais de question.

## 10. Comprendre l'écran de résultats

- **Rang** : ordre déterministe produit par la stratégie.
- **Compatibilité** : score interne sur l'échelle déclarée, jamais une probabilité.
- **Couverture** : part des observations confirmées que le snapshot sait réellement traiter.
- **Abstention** : refus explicite de classer lorsque le périmètre ou les données sont insuffisants.
- **Favorable/défavorable** : direction de la contribution d'une assertion explicite.
- **Inconnu** : information non évaluée ou non utilisable numériquement.
- **Contradiction** : conflit conservé et exposé, jamais effacé par une moyenne silencieuse.
- **Famille de preuve** : regroupement empêchant de compter plusieurs fois une republication.
- **Mapping** : correspondance terminologique ; il ne devient pas une preuve clinique.
- **Reçu** : snapshot, profil, stratégie, versions, hashes et données réellement utilisées.
- **Safety** : composant séparé ; sa valeur actuelle reste toujours `not_evaluated`.

## 11. Sauvegarder et reprendre une session

La sauvegarde est automatique :

```text
sessions/<session_id>/session.json
sessions/<session_id>/runs/<numéro>-diagnose-<reçu>.json
sessions/<session_id>/runs/<numéro>-question-<reçu>.json
```

Au prochain lancement, choisir la session dans la liste. `session.json` contient l'état courant et
chaque fichier sous `runs/` conserve une copie immuable du cas et du résultat exacts.

Le dossier `sessions/` est ignoré par Git, mais il n'est ni chiffré ni protégé par un compte.
N'utiliser que des cas inventés. Ne jamais le synchroniser ou le committer comme un dossier patient.

## 12. Tester sans l'interface

La CLI et l'interface utilisent le même service applicatif. Les commandes essentielles sont :

```powershell
uv run --offline --no-sync latros data inspect --snapshot v0.2.0
uv run --offline --no-sync latros diagnose --snapshot v0.2.0 --case examples/case.synthetic.json
uv run --offline --no-sync latros diagnose --snapshot v0.5.0-dev-unreviewed --strategy general_v1 --case examples/case.orl-unreviewed.json
uv run --offline --no-sync latros question next --snapshot v0.5.0-dev-unreviewed --strategy general_v1 --case examples/case.orl-unreviewed.json
```

Le JSON est écrit sur la sortie standard ; les erreurs utilisent la sortie d'erreur et un code non
nul. La CLI ne sauvegarde pas automatiquement les cas.

## 13. Lancer les contrôles développeur

Ces commandes n'utilisent que des fixtures synthétiques et doivent fonctionner hors ligne :

```powershell
uv run --offline --no-sync ruff check .
uv run --offline --no-sync ruff format --check .
uv run --offline --no-sync mypy
uv run --offline --no-sync python scripts/export_schemas.py --check
uv run --offline --no-sync pytest
uv run --offline --no-sync latros sources validate
```

La même suite est exécutée par GitHub Actions sous Ubuntu et Windows. Un test vert valide le
logiciel et ses contrats, pas la pertinence médicale des résultats.

## 14. Dépannage

### Le snapshot est indiqué comme indisponible

Vérifier d'abord :

```powershell
uv run --offline --no-sync latros data inspect --snapshot <identifiant>
```

Si la commande échoue, construire le snapshot avec ses sources locales. Un manifeste versionné ne
contient pas le runtime DuckDB.

### Le build ORL refuse de démarrer

Vérifier que :

- l'identifiant se termine exactement par `-dev-unreviewed` ;
- `--allow-unreviewed-research-data` est présent ;
- les douze artefacts locaux existent ;
- chaque SHA-256 correspond à `curation/v0.5-orl/sources.json`.

Le refus du snapshot officiel `v0.5.0` est normal tant que la revue humaine requise manque.

### `general_v1` s'abstient

Le pilote exige notamment un adulte, au moins deux observations évaluables et une couverture d'au
moins `0,50`. Les états inconnus sont volontairement neutres.

### Le port 8765 est déjà utilisé

```powershell
uv run --offline --no-sync latros --root . ui --port 8766
```

### Une modification semble perdue entre deux onglets

Les sessions utilisent une révision optimiste. Recharger l'onglet ou reprendre la session la plus
récente évite qu'un onglet ancien écrase une version plus récente.

### Le navigateur ne s'ouvre pas

Lancer avec `--no-open`, puis ouvrir manuellement l'adresse affichée dans le terminal.

## 15. Où trouver la suite

- [Documentation v0.6](v0.6-rd-interface.md) ;
- [plan et roadmap](plan.md) ;
- [historique des livraisons](history.md) ;
- [méthodologie des moteurs](methodology.md) ;
- [ADR de l'interface et des sessions](decisions/0008-interface-locale-rd-et-sessions.md) ;
- [index complet de la documentation](README.md).

Le Knowledge Graph avancé, la logique médicaments/biologie, le moteur safety, le NLP/LLM et FHIR
restent des étapes futures. La v0.6 expose uniquement ce que Latros sait réellement calculer et
tracer aujourd'hui.
