# Parcours simple Latros — prototype local de recherche

Depuis la politique [ADR 0017](decisions/0017-consultations-generale-et-rare-versionnees.md),
le parcours général expérimental `general_question_v2` s'arrête au plus après six questions,
ou plus tôt faute de question admissible / à la demande de résultats. Le compteur affiche la
borne logicielle restante, pas une prévision médicale. Résultats généraux = une fin ; CTA rare
facultatif ensuite. `rare_question_v1` a son compteur (budget 12) et sa propre liste, avec le
même cas déjà renseigné. Les questions proviennent exclusivement du backend ; les concepts
répondus, même inconnus, ne sont pas reposés. Éditer en rare recommence général ; runs conservés.
Voir le [rapport et les limites mono-source](reports/general-first-rare-second.md).

Le serveur `latros ui` reste limité à `127.0.0.1`. La page `/` guide la personne par étapes :
informations de session locales, symptômes explicites, précisions facultatives, question du moteur,
résultats, explication et historique. La console
R&D historique est conservée à `/expert`. Le mode simple propose maintenant la carte interactive
Corps → Tête → Sinus avec recherche toujours disponible et thème clair/sombre local.
Les deux vues utilisent le même backend et les mêmes
runs immuables.

Après les premiers résultats généraux, une vérification facultative peut poser jusqu'à six
questions neutres, issues des findings non évalués des cinq premiers candidats. Le plafond est
global à la session, pas par maladie ; réponses déjà données et concepts absents du catalogue
sont exclus. L'utilisateur peut s'arrêter et voir ses résultats à tout moment. Un nouveau run
immuable suit les réponses ; l'ancien reste disponible. Une information non évaluée n'est pas
une contradiction. La phase rare demeure distincte et facultative.

Sur l'écran de résultats, le panneau Huatuo affiche « En attente d'analyse IA » tant que
l'utilisateur n'a pas explicitement cliqué. Son analyse locale reçoit le profil et le cas
structurés mais aucun résultat Latros. Les hypothèses, motifs et incertitudes sont affichés
séparément ; si le cas change, l'ancienne analyse est marquée périmée et n'est pas relancée
automatiquement. Le panneau n'est ni un diagnostic, ni un triage, ni une validation humaine.

## Utilisation

Utiliser `main` synchronisé avec les deux livraisons #19 (General/Rare) et #20 (atlas).
Le champ optionnel `consultation` est conservé dans les sessions existantes ; l'ancienne
branche visuelle seule ne sait pas les lire et peut bloquer l'accueil avec HTTP 422.
Ne pas supprimer les sessions pour contourner cette incompatibilité de versions.
Les fichiers JS/CSS des deux modes portent un SHA-256 dans leur URL ; les pages HTML ne
sont pas cachées. Un rechargement charge ainsi la version locale courante sans purger
l'historique, les préférences de langue/thème ou les sessions.

```powershell
uv run --offline --no-sync latros --root . ui --no-open
```

Ouvrir `http://127.0.0.1:8765/`, renseigner un nom ou pseudonyme et l'âge, puis rechercher un
terme présent dans le catalogue local ou explorer une région. La liste d'une région ne montre que
les concepts réellement supportés ; un clic ajoute `present`. L'état reste modifiable ensuite.
Un concept ajouté par les deux voies n'est pas dupliqué. La description libre facultative du
profil peut être analysée par Qwen3.5 local : les segments sont proposés contre le catalogue
du snapshot, puis confirmés par le patient avant tout ajout. Aucun concept simplement suggéré
n'est scoré ; absence de modèle ou de correspondance n'empêche pas l'ajout manuel.
Le profil de session est local et non chiffré. Seul l'âge alimente actuellement le cas moteur ;
les allergies, traitements et antécédents facultatifs sont déclaratifs, sans analyse médicale.
Les précisions structurées ne sont proposées que pour une liste explicite de concepts et restent
facultatives ; elles ne modifient pas le score actuel. L'âge est demandé parce que
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

## Architecture anatomique

L'[ADR 0016](decisions/0016-navigation-anatomique-de-presentation.md) conserve Jinja2/JS natif
avec modules locaux API/état/i18n/recherche/observations/anatomie/questions/résultats/historique.
`assets/anatomy/navigation.json` est un arbre UI extensible ; ses codes potentiels sont résolus
par `/internal/v1/presentation/anatomy`, pas par des connaissances codées dans le frontend.
La version 3 de l'arbre contient 47 vues. Trente nouvelles illustrations portent la série à 37
images locales générées. Elles sont séparées
des overlays SVG focusables et des labels HTML FR/DE/EN. Les zooms ne déforment pas les images.
Oreille/œil sont des coupes ; des planches dédiées existent aussi hors tête. La carte n'ajoute
pas de `body_site` au cas. Ces images ne sont pas anatomiquement validées ; l'avertissement reste
visible. Voir l'ADR 0018 et le [rapport atlas v4](reports/ui-atlas-v4.md).

Sur mobile la recherche reste sticky et les observations apparaissent sous la carte ; un
raccourci ramène au champ. Changer d'observation depuis un résultat/question ramène à l'exploration
avant une nouvelle requête backend. Reprendre sans changement conserve l'historique des réponses
et leurs observations. Les éditions et traductions ne réécrivent jamais un run immuable.

Le [rapport UI vNext](reports/ui-anatomy-vnext.md) mesurait 65 concepts FR/DE actifs, explique les
ambiguïtés refusées, les références indisponibles et la latence froide restante (~7 s).
Les exemples ne constituent pas de nouveaux critères diagnostiques ou une validation clinique.

Le lexique UI active désormais 160 concepts FR/DE sur 11 671 ; les nouvelles
propositions ont une provenance explicite et un statut de brouillon éditorial non revu humainement.
Le script `export_ui_translation_review.py` produit un jeu local de revue avec décisions vides.
Les ambiguïtés ne sont jamais forcées. Aucun service de traduction, LLM ou nouvelle assertion.
La [recherche v2](reports/ui-search-v2.md) compare historique, BM25 et fuzzy prudent ;
l'index dérivé est local, sans embeddings ni dépendance réseau. Son benchmark recoupe les
alias éditoriaux ajoutés et ne remplace pas une évaluation indépendante.

Le [rapport produit v4](reports/ui-v4-product-flow.md) décrit le profil patient structuré et sa
frontière avec `ClinicalCaseV2`. L'[atlas v4](reports/ui-atlas-v4.md) documente les 47 nœuds et
37 visuels locaux. L'[audit des questions](reports/ui-v4-question-quality.md) documente la
pertinence encore insuffisante de plusieurs séquences. Ces nouveautés d'affichage ne valident
ni l'anatomie ni les résultats.
