# ADR 0008 — Interface locale R&D et sessions reproductibles

**Statut :** accepté
**Date :** 18 septembre 2026

## Contexte

Latros expose déjà `ClinicalCaseV2`, `semantic_v1`, `general_v1`, les sorties explicables v2 et le
snapshot expérimental `v0.5.0-dev-unreviewed`. Leur manipulation exigeait cependant des fichiers
JSON et la CLI. La tranche v0.6 doit fournir un outil interne de test sans créer de logique médicale,
sans transformer l'interface en API publique et sans masquer les limites des connaissances.

Une maquette locale fictive a servi de référence visuelle pendant la conception. Les actifs utiles
ont été recréés dans le paquet versionné ; aucune donnée, aucun score et aucun comportement fictif
n'ont été repris. Après livraison, le dossier de maquette a été supprimé : l'interface active est
entièrement autonome sous `src/latros/ui/`.

## Décision

Latros ajoute une interface web locale composée de :

- FastAPI et Uvicorn, liés exclusivement à `127.0.0.1` par la commande `latros ui` ;
- pages Jinja2, CSS et JavaScript natif servis par le paquet Python, sans Node, CDN ou télémétrie ;
- une couche `ResearchApplicationService` commune à la CLI et à l'interface ;
- un transport interne versionné `/internal/v1`, qui ne constitue pas l'API publique prévue en
  v0.10 ;
- une découverte des seuls couples snapshot/stratégie compatibles ;
- un catalogue de concepts filtré par les types réellement acceptés par la stratégie ;
- des sessions locales versionnées sous `sessions/`, avec état courant et historique de runs
  immuables.

La CLI et l'interface appellent exactement les mêmes stratégies. Le navigateur ne calcule aucun
score, ne fabrique aucune question et ne déduit aucune relation clinique. Les réponses aux
questions sont converties côté serveur en observations `ClinicalCaseV2` avec provenance
`question_response`.

## Persistance des sessions

Chaque session utilise le contrat `ui-session-v1` et la structure suivante :

```text
sessions/<session_id>/
  session.json
  runs/
    <compteur>-diagnose-<receipt>.json
    <compteur>-question-<receipt>.json
```

`session.json` contient le cas courant, la sélection snapshot/stratégie/profil et les références aux
derniers runs. Chaque fichier de run conserve une copie exacte du cas, de la sélection et du résultat
v2 avec son reçu. Les mutations sont atomiques, utilisent une révision optimiste et refusent les
identifiants de chemin non sûrs. Les runs existants ne sont jamais écrasés.

Le dossier `sessions/` est ignoré par Git. Il peut contenir des cas sensibles et ne doit jamais être
versionné. v0.6 ne promet ni chiffrement au repos, ni comptes, ni contrôle d'accès multi-utilisateur.
Les seules préférences conservées dans `localStorage` sont visuelles ; les cas et résultats restent
dans les fichiers locaux Latros.

## Garde-fous d'interface

- Le serveur n'offre aucune option d'écoute publique, aucune CORS et aucune documentation OpenAPI.
- Les origines de mutation et les en-têtes `Host` sont limités à la boucle locale.
- Une politique CSP interdit les scripts, styles et connexions externes.
- `safety.status = not_evaluated` reste affiché sans conclusion de sécurité.
- Une compatibilité garde sa valeur et son `scale_id` ; elle n'est jamais affichée comme une
  probabilité.
- Tout résultat issu de `v0.5.0-dev-unreviewed` affiche le statut non revu, l'usage local, le refus
  de publication et les comptes d'assertions/mappings en attente.
- Le gate officiel de `v0.5.0`, les statuts de revue et les moteurs historiques ne changent pas.

## Alternatives considérées

### Application monopage avec chaîne Node

Écartée pour v0.6 : elle ajoute un second écosystème, un build et davantage de dépendances avant que
les besoins d'interface soient stabilisés.

### Application purement statique appelant la CLI

Écartée : un navigateur ne doit ni lancer des processus ni réimplémenter la découverte des contrats.
Le petit serveur local fournit une frontière testable et maintient la logique côté Python.

### Framework de dashboard Python

Écarté : les abstractions et dépendances supplémentaires compliqueraient l'évolution vers une
interface plus riche et le futur Knowledge Graph.

## Conséquences

L'interface fonctionne hors ligne sous Windows et Linux, reste remplaçable et facilite le debug des
moteurs. FastAPI, Uvicorn et Jinja2 deviennent des dépendances du paquet. Les contrats internes ne
sont pas promis comme API stable externe.

La visualisation Knowledge Graph avancée reste reportée. Une future vue pourra projeter les
identifiants stables observation → contribution → candidat et observation → assertion → source,
mais elle ne devra créer aucune arête absente des données ou du reçu.

## Sources et licences concernées

Aucune nouvelle source médicale. Le logo officiel du dépôt est copié dans les actifs du paquet. Les
sessions et snapshots générés restent locaux et hors Git.
