# ADR 0019 — Profil local de session et précisions structurées

Date : 28 septembre 2026. Statut : expérimental, non clinique.

## Décision

Le mode simple commence par Informations, puis Symptômes, Précisions/Questions et Résultats.
Le profil `PatientContext` version 1 est optionnel dans les anciennes sessions et local au
`ResearchSession`. Prénom et nom (ou pseudonymes) identifient uniquement la session locale ;
ils ne sont pas copiés dans `ClinicalCaseV2`, ses runs, reçus ou moteur. L'âge est le seul champ
projeté vers `subject_context.age`, car les stratégies actuelles en ont besoin. Aucune création
de compte ni synchronisation distante.

Allergies, maladies connues, traitements et antécédents sont facultatifs, saisis explicitement
élément par élément et marqués `self_reported / captured_not_evaluated`. Ils ne sont ni
normalisés par NLP ni convertis en observations ou preuves. Sexe, taille, poids, tabac et alcool
ne sont pas demandés faute d'usage défini. La présence d'un champ ne constitue pas une
vérification médicale.

La définition `reported-observation-context-v1`, émise par le backend, permet d'enregistrer
durée ISO 8601, intensité déclarée et côté déclaré d'une observation présente. L'ID et le
concept de l'observation sont conservés. Durée et côté utilisent les champs existants du
`ClinicalCaseV2` ; l'intensité non codée reste uniquement dans les réponses de session — aucun
ID HPO de sévérité inventé. La définition porte une provenance technique et le statut
`engineering_definition_not_clinically_validated`. `general_v1`, `semantic_v1` et les deux
politiques General/Rare ne sont pas modifiés. Les stratégies actuelles n'utilisent pas ces
précisions pour classer des hypothèses.

## Limites et sécurité

La capture est générique, pas un interrogatoire spécifique validé pour la céphalée ou une
autre maladie. Aucun site anatomique n'est proposé sans mapping canonique résolu. Les
réponses peuvent être ignorées ; elles ne sont pas réclamées comme discriminants cliniques.
Les sessions existantes restent lisibles, les runs antérieurs immuables, l'ancien `/expert`
inchangé et la sécurité reste `not_evaluated`. Ces informations personnelles locales ne doivent
jamais être versionnées. Une future exploitation par un assistant local nécessitera un contrat,
un consentement et des tests séparés.
