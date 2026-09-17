# ADR 0005 — Snapshot canonique v2 et pilote ORL séparé

**Statut :** accepté  
**Date :** 17 septembre 2026

## Contexte

Le snapshot `v0.2.0` et `semantic_v1` couvrent les maladies rares. Le Knowledge Model v2 existe
comme contrat, mais aucun constructeur ni snapshot médical v2 n'est publié. Les sources proposées
pour la médecine générale restent soumises à des autorisations et à une revue clinique.

## Décision

- Le pipeline v1 et `v0.2.0` restent inchangés.
- Un constructeur canonique v2 est développé d'abord sur des fixtures entièrement inventées.
- Le premier snapshot médical v2 éventuel portera l'identifiant `v0.5.0` et restera séparé de
  `v0.2.0`.
- Son périmètre sera un mini-différentiel ORL ambulatoire adulte limité à angine,
  rhinopharyngite, sinusite et otite.
- Une fixture ou une construction de CI n'est jamais appelée snapshot médical de référence.
- Le registre v2 accepte les artefacts publics ou déposés manuellement, sans identifiants ni
  secrets d'accès.
- Aucun manifeste `v0.5.0` n'est créé tant que les licences, droits de transformation,
  redistribution et revues cliniques ne sont pas validés.
- `general_v1` produira une compatibilité déterministe et non une probabilité. Le moteur de sécurité
  restera séparé.

## Alternatives considérées

- **Snapshot rare + ORL unifié :** rejeté pour v0.5 afin de limiter migration, licences et risques
  de double comptage.
- **Attendre toutes les autorisations avant de coder :** rejeté ; le pipeline et le raisonnement
  peuvent être validés sur des données inventées.
- **Publier un snapshot synthétique `v0.5.0` :** rejeté, car il créerait une confusion avec une
  référence médicale.

## Conséquences

- Deux versions de manifeste et de pipeline coexistent explicitement.
- Les artefacts protégés restent locaux et vérifiés par hash.
- Le travail technique peut atteindre les checkpoints A à D pendant l'audit externe.
- Le `NO-GO` juridique ou clinique bloque la publication réelle, sans invalider les composants
  logiciels testés.

## Sources et licences concernées

SNOMED CT France et les documents HAS ORL restent des candidats conditionnels. Cette ADR
n'autorise aucun téléchargement, aucune ingestion réelle et aucune redistribution.
