# ADR 0011 — Parcours simple local et console experte conservée

**Statut :** accepté

**Date :** 25 septembre 2026

## Contexte

L'interface v0.6 est une console R&D utile, mais son écran initial expose snapshot, stratégie,
identifiants et reçus avant les symptômes. Le corpus v0.7 reste expérimental, non revu et dominé
structurellement par les maladies rares. Une expérience plus simple doit donc améliorer la
navigation sans suggérer une validation médicale absente.

## Décision

- `/` propose un parcours mobile-first : sélection explicite de concepts locaux, âge, questions
  du backend, résultats classés, explication facultative, historique et reprise.
- `/expert` conserve la console v0.6 et toutes ses fonctions. Les deux vues appellent le même
  `ResearchApplicationService` et le même transport interne ; aucun second moteur n'existe.
- Le parcours simple privilégie `v0.7.0-general-dev-unreviewed + general_v1` s'il est disponible.
  Un snapshot manquant produit une erreur explicite, sans substitution clinique silencieuse.
- Les contributions sont montrées au public par les libellés des observations confirmées ; leurs
  identifiants, valeurs brutes, familles, mappings, provenance et reçus restent dans un panneau
  technique facultatif. Les rangs et compatibilités ne sont jamais nommés probabilités.
- `research_unreviewed`, l'absence de validation clinique et `safety.status = not_evaluated`
  restent visibles. Aucun texte libre n'est interprété : seule la sélection d'une suggestion
  constitue une observation. Aucun asset ou service distant n'est requis.

## Réévaluation du choix frontend

React/TypeScript/Vite a été envisagé pour l'état multi-écran et les composants. Pour cette tranche,
les besoins tiennent dans une projection du contrat v2 et une petite machine d'états locale. Le
choix Jinja2/CSS/JavaScript natif de l'ADR 0008 reste donc proportionné : aucun second build,
aucune dépendance Node au runtime, aucun bundle distant et une continuité simple Windows/Linux.
Le nouveau script n'introduit ni calcul médical ni copie de catalogue. Si des interactions
complexes (NLP ou graphe de connaissances) rendent cette structure insuffisante, un nouvel ADR
réévaluera un frontend à composants sur mesures, sans réécrire le backend.

## Conséquences et limites

Les sessions locales existantes sont réutilisées. Une session dont les entrées avancées ne sont pas
représentables fidèlement dans le parcours simple s'ouvre en mode expert. Les données de session
restent non chiffrées ; il ne faut pas y saisir de dossier patient réel. Le jeu de symptômes
peut encore contenir des libellés anglais. Le corpus n'est pas une base validée de médecine
générale et le classement ne tient pas compte de la prévalence. Cette évolution est un prototype
d'ergonomie, pas une interface patient autorisée ni un changement de statut clinique.

## Sources et licences

Aucune nouvelle source médicale. Le logo SVG officiel déjà présent dans le paquet est réutilisé.
