# ADR 0021 — Vérification facultative après les premiers résultats

Date : 29 septembre 2026. Statut : accepté pour expérimentation logicielle, non clinique.

## Décision

Après un premier run généraliste complet, `result_verification_v1` peut proposer au plus six
questions **sur l'ensemble de la session**. La politique lit uniquement les détails des cinq
premiers candidats du run immuable. Elle retient les findings `present` encore non observés,
éligibles numériquement selon le profil existant, documentés chez une partie seulement de ces
candidats, puis les ordonne par variation de documentation et ID. Elle résout chaque ID contre
le catalogue actif ; une résolution absente, ambiguë ou non supportée est écartée. Il ne s'agit
ni d'une mesure d'information clinique ni d'une validation de pertinence.
Seuls les codes ayant une formulation explicite dans le lexique UX local (code et libellé source
identiques) peuvent être posés : cette restriction conservatrice évite des descripteurs bruts
comme « Central », au prix de questions moins nombreuses. Le lexique n'est pas une revue
clinique des assertions du snapshot.

Chaque question est neutre : présent, absent, inconnu ou passer. Une réponse crée une
`QuestionResponseV2` et une observation canoniques dans **le même** `ClinicalCaseV2`. Les
concepts déjà observés ou répondus sont exclus ; la session conserve aussi un compteur et les
concepts posés pour éviter les répétitions après une édition du cas. La liste et le cas de base
sont conservés dans un plan local immuable, séparé du run et du snapshot. Si le cas change hors
des réponses au plan, celui-ci est refusé comme périmé.

L'utilisateur peut voir les résultats initiaux sans cette étape et arrêter la vérification à
tout moment. Après réponse, l'analyse générale habituelle produit un **nouveau run complet** ;
le premier n'est ni modifié ni remplacé. Les réponses restent corrigibles ou supprimables via
le cas, puis une nouvelle analyse peut être lancée. La phase rare et son questionnaire ne
participent jamais à cette politique.

## Invariants et limites

Un finding non évalué n'est ni absent ni contradictoire. Une réponse négative peut devenir une
contribution défavorable selon les mathématiques **inchangées** de `general_question_v2` ; elle
n'est jamais une exclusion absolue ou une probabilité. `general_v1`, `semantic_v1`, les
snapshots, les statuts médicaux et les sorties d'or restent inchangés. L'heuristique n'a pas été
validée par des cliniciens et ne détecte pas les urgences. Les plans et réponses locaux dans
`sessions/` sont sensibles, non chiffrés et ignorés par Git.
