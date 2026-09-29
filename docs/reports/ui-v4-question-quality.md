# Questions généralistes — audit UX reproductible

28 septembre 2026. Ce rapport évalue l'ordre et la lisibilité du questionnaire expérimental,
non la justesse des maladies proposées.

Le script `uv run --offline --no-sync python scripts/benchmark_question_quality.py` utilise le
snapshot local et 14 cas fictifs couvrant tête, ORL, respiratoire, digestif, urinaire,
musculosquelettique et symptômes généraux. Les réponses de simulation sont `unknown`, budget
maximal de six questions. Résultat conservé sous `data/staging/question-quality/` (ignoré Git).

| Observation initiale | Première question (label source EN) | Questions | Arrêt |
| --- | --- | ---: | --- |
| Céphalée | Pain | 6 | Budget |
| Rhume | Dyspnea | 6 | Budget |
| Sinus | Pain | 6 | Budget |
| Toux | Dyspnea | 6 | Budget |
| Fièvre | Fatigue | 6 | Budget |
| Mal de gorge | Fever | 6 | Budget |
| Douleur abdominale | Jaundice | 6 | Budget |
| Diarrhée | Pain | 6 | Budget |
| Douleur thoracique | Loss of consciousness | 6 | Budget |
| Douleur articulaire | Acholic stools | 6 | Budget |
| Fatigue | Pain | 6 | Budget |
| Vertiges | Pain | 6 | Budget |
| Douleur lombaire | Aucune | 0 | Preuve insuffisante |
| Symptôme urinaire | Aucune | 0 | Preuve insuffisante |

Aucune répétition de concept n'a été observée dans ces séquences. En revanche, plusieurs
premières questions sont trop génériques ou peu proches du motif. Le questionnaire est
expérimental mono-source : ce benchmark **ne** valide **pas** une politique clinique. Nous
n'avons donc changé ni `general_question_v2`, ni `general_v1`, ni les scores. Une politique
future de pertinence et un jeu d'évaluation indépendant, revus humainement, restent nécessaires.
L'écran v4 améliore la présentation, le compteur et le saut vers les résultats, pas la qualité
clinique intrinsèque des questions backend.
