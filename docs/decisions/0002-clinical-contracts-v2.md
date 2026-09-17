# ADR 0002 — Contrats cliniques v2 et compatibilité v1

Statut : accepté.

Date : 17 septembre 2026.

## Contexte

Le contrat historique `ClinicalCase` est volontairement limité aux observations HPO et ne sépare
pas l'état clinique, l'état d'évaluation, le texte source, les propositions d'extraction et les
observations confirmées. Il doit continuer à fonctionner sans réinterprétation pour
`semantic_v1`.

## Décision

- Le contrat historique devient `ClinicalCaseV1`; l'alias public `ClinicalCase` est conservé.
- Un document sans `schema_version` est exclusivement un cas v1. Le nouveau contrat porte
  `schema_version: 2`; toute autre version est refusée.
- `ClinicalCaseV2` sépare déclarations sources, propositions, observations confirmées, historique
  des questions et contexte du sujet. Les déductions restent dans les sorties du moteur.
- L'état clinique est `present | absent | unknown`. L'état d'évaluation est
  `assessed | not_assessed | unable_to_assess`. Une impossibilité d'évaluer est représentée par
  `unknown + unable_to_assess`, jamais par une absence.
- Les observations sont une union fermée de types cliniques partageant identité, concept, valeur,
  temporalité, localisation, méthode et provenance.
- Une proposition n'entre jamais dans le raisonnement avant confirmation.
- La migration v1 vers v2 est explicite, déterministe et conserve une provenance
  `legacy_case_v1_migration`.
- L'adaptateur `semantic_v1` ne projette que les observations HPO confirmées et refuse les états
  courants contradictoires d'un même concept.

## Alternatives considérées

Ajouter des champs optionnels au modèle v1 aurait modifié son schéma sans version explicite.
Utiliser un dictionnaire libre aurait supprimé les validations inter-champs. Faire de
`unable_to_assess` un quatrième état clinique aurait mélangé connaissance du fait et capacité à
l'évaluer.

## Conséquences

Les deux contrats coexistent. Les sorties v1 restent gelées. Les nouveaux champs sont
représentables avant d'être utilisés par un moteur. FHIR R4 inspire les types mais Latros ne devient
pas une implémentation FHIR.

