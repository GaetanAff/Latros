# ADR 0004 — Stratégies, profils et reçus d'exécution

Statut : accepté.

Date : 17 septembre 2026.

## Contexte

`semantic_v1` charge directement les tables v1 et retourne des dictionnaires JSON. Un futur moteur
général doit coexister avec lui sans modifier ses calculs ni présenter ses compatibilités comme des
probabilités.

## Décision

- Séparer génération de candidats, scoring, choix des questions et construction de l'explication
  derrière des protocoles stables.
- Conserver `semantic_v1` et `question_v1` derrière un adaptateur, avec sorties v1 strictement
  inchangées.
- Versionner séparément : manifeste de connaissances, profil de raisonnement et reçu d'exécution.
- Un profil déclare types d'observations, relations, échelle du score, paramètres, compatibilités,
  périmètre et critères d'abstention.
- Une combinaison snapshot/profil absente ou incompatible est refusée.
- La sortie v2 expose couverture, éléments ignorés, contributions par source et famille,
  abstention, sécurité séparée et reçu reproductible.
- Aucun agrégat hétérogène n'est une moyenne implicite; aucune compatibilité non calibrée n'est
  affichée comme pourcentage.
- Le reçu est retourné à l'appelant mais n'est jamais persisté automatiquement.

## Alternatives considérées

Transformer directement `Engine` en moteur général aurait risqué une régression de la méthode
rare. Mettre les paramètres du raisonneur dans le manifeste de données aurait forcé la publication
d'un nouveau snapshot pour un changement de moteur seul.

## Conséquences

Les sorties historiques sont protégées par des empreintes d'or. Les futurs manifests limitent leur
hash de build au pipeline de connaissances; le manifeste v1 historique reste immuable et conserve
son comportement de reconstruction avec la version logicielle historique.

