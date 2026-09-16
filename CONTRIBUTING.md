# Contribuer à Latros

## Règle de phase 0

Le projet est encore en conception. Toute modification doit préserver l'absence de choix technique définitif et ne doit pas introduire de moteur diagnostique, d'importateur de données ou de traitement de données patient sans décision d'architecture explicite.

## Avant une modification

1. Vérifier si le sujet est déjà traité dans [projet.md](projet.md).
2. Créer ou commenter une issue pour les décisions qui modifient le périmètre, les données, les licences ou la sécurité clinique.
3. Documenter les arbitrages importants dans `docs/decisions/`.
4. Ne jamais committer de données personnelles, de poids de modèles, de jeux de données sous licence restrictive ou de secrets.

## Principes de qualité

- Conserver la provenance et la version des connaissances médicales.
- Distinguer explicitement `present`, `absent` et `unknown`.
- Ne pas appeler « probabilité » un score non calibré.
- Séparer le triage de sécurité du diagnostic différentiel.
- Garder les fonctions LLM remplaçables et mesurables face au moteur pur.
- Préserver une exécution locale possible.

## Pull requests

Une pull request doit expliquer :

- le problème résolu ;
- les limites et hypothèses ;
- les données ou licences concernées ;
- les tests ou vérifications réalisés ;
- l'impact éventuel sur la sécurité, la confidentialité ou l'explicabilité.

