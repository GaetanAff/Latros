# ADR 0020 — Proposition locale de symptômes, confirmation humaine

Date : 29 septembre 2026. Statut : accepté pour expérimentation logicielle, non clinique.

## Contexte et décision

La recherche par terme reste disponible, mais un patient peut décrire plusieurs symptômes en
langage libre. Un Qwen3.5 local peut extraire des **propositions**, jamais des observations
cliniques directement. Le champ narratif est enregistré dans le profil local ; l'inférence ne
commence qu'après la sauvegarde de ce profil. La sortie du modèle est non fiable : le backend
vérifie que chaque segment figure exactement dans le texte, recherche seulement des concepts
actifs et supportés par le snapshot, et présélectionne uniquement un match lexical sans égalité.
Une confirmation explicite du patient est requise avant toute insertion dans `ClinicalCaseV2`.

Les contrats existants `SourceStatement`, `ObservationProposal` et `ClinicalObservation`
conservent le texte, le segment, la méthode et l'ID canonique. `accepted` signifie ici que le
patient a confirmé une proposition d'extraction, **pas** qu'une assertion médicale a été revue.
Aucune confiance clinique n'est attribuée ; le champ technique requis est à `0` et annoté
comme non calibré. Les propositions non confirmées ne sont pas scorées.

## Isolation

Le serveur llama.cpp est lancé à la demande sur `127.0.0.1`, sans proxy, MCP, interface web ni
appel de téléchargement. Un seul GGUF est chargé à la fois. Les chemins sont configurables par
variables locales ; les poids restent hors Git. Le navigateur n'appelle que l'API Latros.
`general_v1`, les snapshots, les statuts de validation et les questions restent inchangés.
La description et les observations sont des données sensibles conservées dans `sessions/`,
ignoré par Git mais non chiffré. Ne pas utiliser avec de vrais dossiers patients.

## Limites

Une extraction peut manquer un symptôme, mal comprendre une négation ou produire un terme
ambigu. Le patient peut refuser/corriger chaque suggestion ; recherche et anatomie restent
fonctionnelles si le modèle est absent. Cette étape ne crée aucune connaissance clinique et
ne constitue pas une validation de Qwen en médecine.
