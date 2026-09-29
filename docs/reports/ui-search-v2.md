# Recherche locale v2 — benchmark de découvrabilité

28 septembre 2026. Mesure de sélection explicite de concepts, **pas** de pertinence clinique.

## Protocole

`uv run --offline --no-sync python scripts/benchmark_ui_search_v2.py --modes existing bm25 bm25_fuzzy`
interroge le vrai snapshot `v0.7.0-general-dev-unreviewed` avec réseau bloqué. Les 78 formulations
FR/DE/EN comprennent 63 recherches dont le concept cible est supporté et 15 formulations
absentes ou négatives. Les cibles sont des choix éditoriaux explicites du banc d'essai, non des
synonymes automatiquement approuvés. Les mesures sont chaudes, après préparation commune du
catalogue ; elles ne mesurent pas le premier lancement du service.

| Mode | Top 1 / 63 | Top 3 / 63 | Sans résultat supporté | Suggestions sur négatifs / 15 | Médiane chaude |
| --- | ---: | ---: | ---: | ---: | ---: |
| Historique | 62 | 63 | 0 | 2 | 0,203 s |
| BM25 lexical | 60 | 60 | 3 | 0 | 0,204 s |
| BM25 + fuzzy prudent | 63 | 63 | 0 | 0 | 0,207 s |

Le mode retenu combine correspondances exactes, synonymes/alias versionnés, préfixes,
classement lexical BM25 et fuzzy borné. Les négations évidentes ne sont pas interprétées comme
des symptômes présents. La recherche reste DuckDB locale, sur les concepts actifs/supportés ;
elle ne charge pas tout le catalogue en modèles Python et n'ajoute aucune assertion médicale.
Un index lexical dérivé en mémoire reste lié à l'instance du repository, pas au snapshot publié.

Un modèle d'embeddings local n'est pas retenu : sur ce banc, le lexical/fuzzy atteint déjà les
cibles et l'embedding ajouterait poids, reproductibilité, faux voisins sémantiques et revue
éditoriale sans gain démontré. Cette conclusion est limitée aux 78 requêtes, qui doivent être
étendues et revues par de vrais utilisateurs. Un préfixe ressemblant à une négation peut rester
sans suggestion ; c'est une prudence, pas une compréhension du langage libre. Le texte saisi
ne crée jamais une observation avant choix explicite d'une suggestion.

Les 63 cibles reprennent largement les alias éditoriaux ajoutés avec cette tranche. Le 63/63
mesure donc surtout la non-régression du lexique préparé, **pas** un rappel utilisateur sur un
jeu indépendant. Un test en aveugle sur de nouvelles formulations et une revue linguistique et
médicale humaine sont nécessaires avant toute allégation de qualité produit.

Couverture réelle : 11 671 concepts recherchables, 11 671 labels EN, aucune désignation FR/DE
native dans ce catalogue ; lexique UX local pour 160 concepts FR et 160 DE (173 alias FR,
167 DE). Il reste 11 511 concepts sans traduction FR/DE. Le fallback EN est visible. Ces
traductions sont des propositions d'affichage non revues cliniquement et ne changent jamais l'ID.
