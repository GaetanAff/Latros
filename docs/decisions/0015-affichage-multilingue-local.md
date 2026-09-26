# ADR 0015 — Affichage multilingue local, séparé de la connaissance

Date : 26 septembre 2026. Statut : accepté pour la couche UX interne de recherche.

## Contexte

Les labels canoniques principalement anglais rendent la sélection explicite difficile en FR/DE.
Les traduire dans le snapshot ou transformer des formulations libres en observations reviendrait
à changer la connaissance ou à simuler le NLP v0.9, hors périmètre.

## Décision

Le parcours simple possède un catalogue UI FR/DE/EN embarqué et un lexique d'affichage versionné
distinct. Les désignations locales existantes de la langue sont prioritaires ; neuf concepts HPO
ont des formulations/questionnements explicites et audités techniquement contre IDs/labels sources.
Une identité absente, ambiguë ou dont le label attendu diverge désactive l'alias. Les autres termes
restent dans leur langue source anglaise, avec fallback EN visible. Pas de traduction automatique.

La recherche consulte une projection SQL temporaire dérivée du snapshot read-only, limitée aux
observations déjà supportées. Synonymes et alias facilitent la découverte, **pas** le scoring ni
un mapping clinique exact. Le fuzzy à distance d'édition un est limité aux alias explicites, à
partir de cinq caractères et à un seul concept cible ; les ambiguïtés sont écartées. La personne
confirme un concept précis, notamment « sensation de rotation » pour les formulations de vertige.

Les endpoints internes de présentation sont distincts des résultats/runs et de l'ancien endpoint
de concepts expert. Les observations soumises gardent le coding/label source ; question ID,
question scientifique, profil, reçu et résultat ne sont jamais traduits dans le stockage. Les
tables temporaires vivent avec les deux repositories déjà bornés, aucune copie globale Pydantic
ou catalogue massif côté navigateur. Réinitialisation à la fermeture/changement de snapshot ;
redémarrer le serveur après modification du lexique embarqué.

## Alternatives et conséquences

API de traduction, embeddings/LLM, alias massifs générés et modifications du snapshot sont exclus.
Jinja2/JS natif de l'ADR 0011 reste adapté ; Node n'est ajouté que pour les tests frontend en CI.
La couverture de traduction médicale est partielle et ne représente aucune validation clinique.
La console experte conserve les données sources. Aucun statut de recherche, safety ou publication
ne change, aucune source médicale externe n'est ajoutée.
