# ADR 0013 — Projections HTTP paresseuses des résultats immuables

Date : 25 septembre 2026. Statut : accepté pour l'interface locale de recherche.

## Contexte

`general_v1` peut produire plusieurs milliers de candidats et environ 206 Mo de JSON complet.
La vue simple n'affiche que les premiers rangs. Envoyer tout le run à chaque diagnostic ou reprise
consomme du temps, de la mémoire navigateur et du trafic loopback sans améliorer l'explication.

## Décision

Le run scientifique complet reste enregistré localement, immuable et disponible par la route
historique du mode expert. Une projection distincte (`view=summary` ou `/summary`) expose au plus
20 candidats, les statuts, la couverture et des contributions abrégées. Une route de détail lit
un candidat complet à la demande. Le frontend ne calcule ni rang, ni score, ni question.

Pour les nouveaux diagnostics, un index auxiliaire local contient les offsets des candidats
dans le JSON complet et son SHA-256. L'index est vérifié avant lecture ; les anciens runs sans
index restent lisibles par le chemin complet. Il n'est pas un nouveau snapshot et ne modifie
ni les résultats `general_v1`, ni leur reçu. Les deux vues utilisent les mêmes sessions locales.

## Conséquences

- Le parcours simple et sa reprise ne téléchargent plus le résultat intégral. Le détail est
  chargé seulement au clic ; `/expert` conserve l'accès au run complet.
- Le JSON du run est écrit sous forme compacte pour les nouveaux runs, mais sa valeur et son
  contrat sont identiques. Aucun run historique ni manifeste n'est réécrit.
- Le calcul du moteur et la persistance du run entier restent nécessaires avant la réponse ;
  cette décision réduit principalement le transport et le coût du navigateur, pas le coût
  intrinsèque du diagnostic.
- Un run historique sans index reste lisible via le chemin complet ; la corruption d'un index
  existant bloque la projection au lieu de fournir un détail potentiellement incohérent.
