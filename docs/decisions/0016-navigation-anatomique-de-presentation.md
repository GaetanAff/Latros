# 0016 — Navigation anatomique séparée de la connaissance

Statut : accepté. Date : 26 septembre 2026.

## Contexte

Après fusion des PR #15 (G5) et #16 (affichage multilingue), le parcours simple doit offrir
une exploration anatomique sans inférer de symptômes, de localisation clinique ou de diagnostic.
La console `/expert`, les contrats, les runs complets et les snapshots restent inchangés.

## Décision

Conserver FastAPI/Jinja2 et JavaScript natif local. Un arbre UI versionné `ui-anatomy-1`
référence des SVG locaux, des parents/enfants, des libellés FR/DE/EN et des IDs HPO potentiels.
Il n'est ni une hiérarchie clinique, ni une source d'assertions. Première implémentation :
Corps → Tête → Sinus ; les autres régions sont des points de navigation explicitement inachevés.

L'endpoint de présentation résout les références par identité externe non ambiguë, contre les
observations actives réellement supportées du snapshot. Une absence ou ambiguïté masque l'item.
Le SQL reste dans le repository de présentation, ouvert sur le runtime read-only.
Recherche et anatomie utilisent le même `ConceptOption` canonique et la même construction
d'`Observation`, sans remplir `body_site` ou déduire un symptôme du seul clic sur une région.

Le navigateur maintient une seule observation par `concept_id`. L'état présent/absent/inconnu
reste explicite. Les liens anatomiques d'observations utilisent les IDs canoniques résolus,
pas une comparaison fragile des codes primaires historiques et des codes de navigation.
Une modification du cas quitte l'écran d'une question/résultat antérieur ; elle ne réécrit
aucun run. Une reprise sans modification conserve les observations et l'historique des réponses.

Le code est séparé en modules API, état, i18n, recherche, observations, anatomie, questions,
résultats et historique. La recherche reste disponible sur tous les écrans. SVG et thèmes
sont locaux ; Inter embarquée reste utilisée, aucun asset distant n'est introduit.

## Alternatives

- Raster et coordonnées cliquables : écartés pour accessibilité, stabilité et responsive.
- Associations anatomiques ajoutées au Knowledge Model : écartées ; cette tranche est une
  classification de navigation seulement, sans nouvelle connaissance médicale.
- React/Vite : aucun besoin démontré pour ces trois niveaux ; pas de nouveau build frontend.
- Traduction/fuzzy massifs : écartés ; lexique explicite versionné, ambiguïtés refusées,
  fallback EN visible, aucune traduction distante ou interprétation du texte libre.

## Conséquences et limites

L'extension d'une région demande configuration/SVG et références UI vérifiées, pas un nouveau
moteur. Les figures sont des schémas de navigation, pas un atlas médical. Les observations
affichées ne constituent pas une liste de critères diagnostiques d'une maladie de cette région.
Les traductions et alias restent éditoriaux, séparés de la validation clinique G1/G2/G3.
Les garde-fous `research_unreviewed`, non-publication et urgences non évaluées restent visibles.
Ni sources médicales, ni licences, ni schémas scientifiques, ni snapshot ne sont modifiés.
