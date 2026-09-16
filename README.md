# Latros

Prototype **interne de recherche** pour classer des maladies rares à partir de phénotypes HPO structurés. Moteur local et explicable, sans LLM, sans serveur et sans interface patient.

> **Aucun triage n'est effectué.** Toutes les analyses retournent `safety_status: not_evaluated`. Les scores sont des compatibilités sémantiques, jamais des probabilités ou des diagnostics validés. Ne pas utiliser ce prototype pour conseiller un patient.

La version de développement `0.3.0` regroupe le socle technique, le pipeline de données et le moteur pur. Voir [ADR 0001](docs/decisions/0001-socle-recherche.md) pour les décisions, [méthodologie](docs/methodology.md) pour les calculs et [projet.md](projet.md) pour la vision à long terme.

## Installation

Prérequis : Git, Python 3.11 et [uv](https://docs.astral.sh/uv/getting-started/installation/) (version utilisée en CI : `0.12.15`). L'installation initiale des dépendances et le téléchargement des sources nécessitent Internet. Ces commandes s'exécutent depuis la racine du dépôt sous PowerShell ou un shell Unix.

```text
git clone https://github.com/GaetanAff/Latros.git
cd Latros
uv sync --locked --python 3.11
uv run --no-sync latros --help
uv run --no-sync latros sources validate
```

Le dépôt est privé : Git doit disposer de votre authentification GitHub. `uv.lock` fixe les dépendances ; ne pas le mettre à jour pour reconstruire un snapshot historique. Pour récupérer les évolutions : `git pull --ff-only`, puis `uv sync --locked`.

## Télécharger les sources épinglées

Consulter les conditions de chaque produit dans [sources/registry.yaml](sources/registry.yaml). Une licence d'ontologie ne couvre pas nécessairement les annotations d'une autre source. HPOA et les annotations OMIM ne sont pas importées.

```text
uv run --no-sync latros sources list
uv run --no-sync latros sources fetch --source hpo --release 2026-09-01
uv run --no-sync latros sources fetch --source mondo --release 2026-09-01
uv run --no-sync latros sources fetch --source orphadata --release 2026-07
```

Le registre fournit versions, URLs officielles, produits, attributions, restrictions et SHA-256 attendus. Aucun lien `latest`. Les fichiers aboutissent à `data/raw/<source>/<release>/`, avec un manifeste local. Les fichiers complets déjà vérifiés sont réutilisés. Après interruption, relancer la commande : le fichier `.part` repart de zéro, sans retélécharger les autres fichiers valides. Un hash incorrect ou un fichier existant corrompu provoque un refus, sans écrasement du fichier complet.

| Source | Version | Utilisation |
| --- | --- | --- |
| [HPO](https://github.com/obophenotype/human-phenotype-ontology/releases/tag/v2026-09-01) | 2026-09-01 | Concepts, synonymes et hiérarchie HPO |
| [Mondo](https://github.com/monarch-initiative/mondo/releases/tag/v2026-09-01) | 2026-09-01 | Maladies, synonymes et mappings ORPHA |
| [Orphadata Science](https://sciences.orphadata.com/phenotypes/) | archive juillet 2026 | Associations maladie–HPO, fréquences et libellés EN/FR |

Les produits Orphadata sont fixés au commit `463f51d0db1d754b53e96027dd098a3d96a9c79c` de l'[archive officielle](https://github.com/Orphanet/Orphadata_aggregated/tree/463f51d0db1d754b53e96027dd098a3d96a9c79c). Date d'archive : 29 juin 2026 ; « juillet 2026 » est le nom de livraison du producteur.

## Construire et inspecter hors ligne

```text
uv run --offline --no-sync latros data build --snapshot latros-kb-0002
uv run --offline --no-sync latros data inspect --snapshot latros-kb-0002
```

Les sept tables canoniques sont publiées dans `data/canonical/latros-kb-0002/*.parquet`. Le runtime `data/runtime/latros-kb-0002/knowledge.duckdb` est ouvert en lecture seule par le moteur. Le [manifeste](manifests/latros-kb-0002.json) contient sources, hashes, comptes, version du code, transformations et avertissements. Le numéro 0001 correspondait à une reconstruction préparatoire locale, non publiée.

Un clone qui possède le manifeste mais pas les données reconstruit le snapshot et vérifie l'égalité du résultat. Aucun téléchargement pendant `build`. Un snapshot existant n'est jamais écrasé : changement de sources ou d'implémentation ⇒ nouvel identifiant, par exemple `latros-kb-0003`. Un échec d'import produit un rapport local dans `data/failures/`, sans publier le snapshot.

Les hashes logiques portent sur les lignes triées et les hashes Parquet sur leurs fichiers : ils doivent être identiques à la reconstruction. Les octets du conteneur DuckDB peuvent différer malgré des données identiques ; son SHA-256 sert uniquement à détecter une corruption locale, dans `data/runtime/<snapshot>/integrity.json`, ignoré par Git. Le moteur vérifie ce reçu à chaque ouverture. Conserver le code et les dépendances verrouillées ; ne pas remplacer un manifeste historique pour masquer une dérive.

## Interroger le moteur

L'exemple est **inventé**, sans patient réel. La CLI attend des identifiants HPO, pas du texte libre.

```text
uv run --offline --no-sync latros diagnose --snapshot latros-kb-0002 --case examples/case.synthetic.json
uv run --offline --no-sync latros question next --snapshot latros-kb-0002 --case examples/case.synthetic.json
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

**Limites :** biais maladies rares et annotations, signes corrélés, temporalité/contexte non utilisés, questions techniques, aucune validation clinique. Les tests synthétiques vérifient le logiciel, pas sa justesse médicale. Aucun LLM, MedGemma, TxGemma, moteur de sécurité, audio, interface, entraînement ou conseil thérapeutique dans cette version.

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
src/latros/reasoning/   semantic_v1 et questions adaptatives
src/latros/cli.py       commandes publiques
sources/               registre épinglé (versionné)
schemas/               contrats exportés (versionnés)
manifests/             références de reconstruction (versionnées)
data/                  sources et snapshots locaux (ignorés)
tests/                 fixtures synthétiques et tests hors ligne
```

Suivre [CONTRIBUTING.md](CONTRIBUTING.md) : branches de fonctionnalité, pull requests et `main` stable. Les trois jalons du plan sont réunis ici ; `0.3.0` n'est pas une certification médicale.

## Confidentialité et licences

Ne jamais envoyer sur GitHub les sources brutes, snapshots, données patient, poids de modèles ou secrets. Seuls code, documentation, registre, schémas, manifestes et fixtures inventées sont versionnés. `.gitignore` limite les accidents mais n'est pas un contrôle d'accès : vérifier chaque diff.

Attributions : Human Phenotype Ontology Consortium ; Mondo Disease Ontology contributors ; Orphadata, INSERM/Orphanet. Les licences des sources sont indépendantes de celle du code. Aucune licence de redistribution du code n'a encore été choisie ; le dépôt reste privé. La conservation locale d'une source ne dispense pas de respecter ses conditions.
