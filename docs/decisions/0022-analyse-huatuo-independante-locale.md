# ADR 0022 — Hypothèses Huatuo indépendantes et facultatives

Date : 29 septembre 2026. Statut : expérimentation logicielle, non clinique.

## Décision

Un bouton explicite, affiché **après** un résultat Latros, peut lancer le GGUF HuatuoGPT-3-27B
via le même transport llama.cpp local que Qwen. Le serveur est limité à `127.0.0.1`, sans proxy,
télémétrie ni appel distant ; les modèles sont chargés séquentiellement. L'absence du GGUF ou du
serveur n'empêche jamais le différentiel Latros ni sa consultation.

Le prompt est construit par **liste autorisée** : `PatientContext` intégral (identité locale,
âge, description, allergies, antécédents, traitements déclarés), `ClinicalCaseV2` intégral
(observations, textes source, réponses aux questions ordinaires et à la vérification), puis
les précisions structurées. Le backend n'appelle pas `load_run`, `load_run_summary` ou
`load_candidate_detail` dans ce chemin et n'inclut jamais candidat, rang, score, contribution
ou reçu Latros. Le résultat Huatuo n'alimente ni le cas ni le moteur.

La réponse du modèle doit respecter un petit contrat JSON : au plus cinq hypothèses avec motif
et incertitude, incertitudes générales et limites. Les pourcentages visibles sont refusés.
L'artefact local conserve le prompt d'entrée autorisé, la réponse brute, la sortie structurée,
la version de prompt et le hash du cas ; le transport UI n'expose pas le prompt ni la réponse
brute. Si les données du cas changent, l'ancienne analyse est affichée comme périmée, sans
recalcul automatique.

## Limites et sécurité

Il s'agit d'une **seconde sortie expérimentale**, pas d'un arbitre du différentiel ni d'une
validation clinique. Le modèle peut produire une hypothèse erronée ou une formulation
inappropriée malgré le format demandé ; aucune conclusion de triage, d'urgence, de traitement
ou de probabilité ne doit en être tirée. Les statuts restent
`clinical_validation: false`, `publishable: false`, `research_unreviewed: true` et
`safety_status: not_evaluated`. Les données sont sensibles, locales, non chiffrées et ignorées
par Git ; ne pas utiliser avec de vrais dossiers patients dans cet état.
