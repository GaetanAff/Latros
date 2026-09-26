# Parcours simple Latros — prototype local de recherche

Le serveur `latros ui` reste limité à `127.0.0.1`. La page `/` guide la personne par étapes :
symptômes explicites, âge, question du moteur, résultats, explication et historique. La console
R&D historique est conservée à `/expert`. Les deux vues utilisent le même backend et les mêmes
runs immuables.

## Utilisation

```powershell
uv run --offline --no-sync latros --root . ui --no-open
```

Ouvrir `http://127.0.0.1:8765/`, rechercher un terme présent dans le catalogue local et choisir
une suggestion. Le texte libre non sélectionné n'est pas interprété. L'âge est demandé parce que
`general_v1` exige actuellement un périmètre adulte ; l'absence d'âge peut provoquer une
abstention. Chaque question affichée vient du backend, y compris son arrêt. Les réponses et les
analyses sont sauvegardées dans `sessions/`, hors Git. L'historique peut reprendre une session
simple ; une session R&D trop riche renvoie vers `/expert` pour ne pas masquer ses entrées.

Les résultats montrent des rangs, jamais des pourcentages. Le panneau « Voir pourquoi » distingue
arguments favorables, contradictoires et non évalués. Les identifiants, compatibilités brutes,
sources, mappings, familles, provenance et reçus sont accessibles dans « Afficher les détails
techniques » et dans `/expert`. Aucun calcul clinique n'a été déplacé dans le navigateur.

## Limites et sécurité

- Le snapshot `v0.7.0-general-dev-unreviewed` reste non revu, non validé cliniquement et non
  publiable. Un rang n'est ni un diagnostic, ni une probabilité, ni une estimation de prévalence.
- `safety.status = not_evaluated` : les urgences ne sont pas évaluées. Aucun conseil de triage ne
  peut être déduit de l'interface.
- FR/DE/EN traduit le parcours simple localement ; les désignations sources et un petit lexique
  explicite d'affichage couvrent une partie des labels/questions. Les termes manquants sont
  indiqués EN, sans service externe ni NLP. L'absence d'un terme n'est pas une conclusion médicale.
- Les sessions sont locales mais non chiffrées. Ne pas utiliser de données personnelles réelles.
- La CSP ne permet que les assets et appels de même origine. Pas de CDN, télémétrie ou API externe.

## Vérification

Les tests `tests/test_ui_server.py` couvrent les écrans servis, les garde-fous locaux et les
contrats backend. Un contrôle navigateur doit couvrir le parcours sur mobile et desktop :
recherche, sélection, âge, question, résultat, détail, historique, reprise et mode expert, avec
toutes les requêtes hors boucle locale refusées. Les diagnostics de ce contrôle testent le
logiciel, jamais la validité clinique des résultats.

Le [rapport multilingue](reports/ui-i18n-local-search.md) et l'ADR 0015 précisent la séparation
affichage/connaissance, les alias, les fallbacks et les tests. La console experte conserve les
labels/contrats sources et ses fonctions historiques ; elle n'est pas une traduction de la base.
