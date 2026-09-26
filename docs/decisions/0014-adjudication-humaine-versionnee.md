# ADR 0014 — Adjudication humaine versionnée et isolée

Date : 26 septembre 2026. Statut : accepté pour le workflow technique de revue, pas pour une
validation clinique.

## Contexte et décision

G4 filtre des candidates expérimentales. Son statut ne constitue pas une décision médicale.
L'outil séparé de l'ADR 0012 doit accueillir deux avis indépendants sans écraser le premier et
exposer une adjudication distincte. Un simple champ approve/reject est insuffisant.

Le journal conserve la chaîne SHA-256 et le stockage JSONL append-only. Les événements de
`schema_version: 2` séparent `category`, `final_decision` et `stage`. Ils lient identité déclarée,
horodatage UTC, ligne et CSV épinglés ; une adjudication lie également les hashes des derniers
avis de chaque reviewer. Elle exige deux reviewers distincts, un adjudicateur différent et une
justification. Un nouvel avis rend l'ancienne adjudication obsolète dans la projection sans
effacer l'événement. L'accord inclut catégorie, décision et relation proposée de mapping.

Les événements v1 restent lisibles et exportables ; ils ne sont pas convertis en double revue.
Le mode historique reste disponible. G5 utilise un nouveau dossier local : les CSV G1/G2 sont
copiés octet pour octet, jamais annotés ou réécrits. Aucun journal existant n'est migré ou effacé
automatiquement. Toute reprise d'un ancien journal requiert la conservation des exports épinglés.

## Alternatives et conséquences

Un tableur mutable et un champ unique « dernière décision » ont été écartés : ils perdent la
traçabilité du désaccord. Une base multi-utilisateur avec authentification n'est pas introduite
pour cet outil mono-instance local ; l'identité, les qualifications et l'indépendance sont
self-attested et doivent être organisées/contrôlées par l'équipe humaine. L'UI masque les avis
des autres reviewers en étape indépendante, mais ce n'est pas une barrière d'authentification.
La hash chain détecte une altération incohérente, pas une falsification signée ni une troncature
du journal complet. Il faut sauvegarder les exports et le journal.

Les six projections d'export restent hors du snapshot. Aucun accord, approve ou adjudication
ne déclenche de promotion ; une nouvelle release revue exigera un processus séparé. Aucun
statut médical, source primaire ou licence n'est changé. Les fichiers dérivés restent ignorés.
