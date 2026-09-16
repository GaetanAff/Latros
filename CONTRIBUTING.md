# Contribuer à Latros

## Périmètre actuel

Le socle de recherche maladies rares est autorisé par le plan d'implémentation et [ADR 0001](docs/decisions/0001-socle-recherche.md). Python 3.11, uv, Pydantic, Typer, DuckDB/Parquet sont retenus pour cette tranche. Pas d'interface patient, de LLM, de triage ou de données patient réelles. La vision de phase 0 reste documentée dans `projet.md` mais n'interdit plus l'implémentation de ce périmètre.

## Avant une modification

1. Vérifier si le sujet est déjà traité dans [projet.md](projet.md).
2. Créer ou commenter une issue pour les décisions qui modifient le périmètre, les données, les licences ou la sécurité clinique.
3. Documenter les arbitrages importants dans `docs/decisions/`.
4. Ne jamais committer de données personnelles, de poids de modèles, de jeux de données sous licence restrictive ou de secrets.
5. Suivre [docs/plan.md](docs/plan.md) pour le périmètre de chaque jalon et les noms de snapshots (`v0.2.0` pour le premier snapshot médical).

## Documentation à chaque livraison

Actualiser `history.md`, `README.md` et `docs/plan.md` avec les changements réellement effectués, les commandes utilisables, les vérifications et les limites. Ajouter une entrée datée à l'historique sans effacer les anciennes réalisations. Mettre également à jour `projet.md`, les ADR, schémas, registre ou manifestes lorsque leurs informations changent. Une demande de discussion seule n'implique pas de modification du code.

Les références de snapshots reprennent les versions du plan. Un identifiant publié est immuable ; une révision reçoit un nouvel identifiant documenté. La version du paquet Python et celle d'un snapshot restent distinctes.

## Principes de qualité

- Conserver la provenance et la version des connaissances médicales.
- Distinguer explicitement `present`, `absent` et `unknown`.
- Ne pas appeler « probabilité » un score non calibré.
- Séparer le triage de sécurité du diagnostic différentiel.
- Garder les fonctions LLM remplaçables et mesurables face au moteur pur.
- Préserver une exécution locale possible.

## Pull requests

Garder `main` stable : une branche par fonctionnalité, puis une pull request. Ne pas fusionner sans revue. Exécuter les contrôles du README et régénérer les schémas si les contrats changent. Un changement de sources ou d'implémentation de référence exige un nouvel identifiant de snapshot ; ne pas remplacer les anciens manifestes pour masquer une dérive.

Une pull request doit expliquer :

- le problème résolu ;
- les limites et hypothèses ;
- les données ou licences concernées ;
- les tests ou vérifications réalisés ;
- l'impact éventuel sur la sécurité, la confidentialité ou l'explicabilité.
