# ADR 0006 — Sources ouvertes du pilote ORL

**Statut :** accepté pour la préparation ; publication bloquée

**Date :** 17 septembre 2026

## Contexte

L'audit initial de `v0.5-E` a conclu à un `NO-GO` pour le couple SNOMED CT France / HAS. Cette
décision reste dans l'historique, mais le premier snapshot ORL ne doit plus dépendre de la levée de
ces deux blocages.

## Décision

- Les checkpoints techniques `v0.5-A` à `v0.5-D` sont conservés sans changement.
- Le snapshot `v0.5.0`, s'il est ultérieurement autorisé, n'utilisera pas SNOMED CT.
- Latros conserve des identifiants canoniques internes. DOID est la terminologie primaire lorsque
  sa granularité est exacte ; Mondo complète les concepts et mappings secondaires lorsqu'ils
  existent. Pour la sinusite aiguë générique et l'otite moyenne aiguë générique, aucun concept humain
  externe exact n'a été confirmé dans les releases auditées : le concept Latros reste distinct et
  ses liens DOID/Mondo sont `broader` ou `narrower`, jamais promus en équivalence.
- MeSH est différé : il n'est pas nécessaire au premier lot et ses termes d'entrée ne sont pas tous
  des synonymes stricts.
- Les assertions cliniques candidates viennent en priorité de NHS, CDC et des synthèses publiques
  MedlinePlus. nidirect complète l'OMA mais reste une republication de la famille NHS.
- Une terminologie, un xref ou un mapping ne crée jamais une assertion clinique.
- Le texte source n'est pas republié en masse. Seules des assertions atomiques, leurs qualificatifs
  et leur provenance peuvent entrer dans le Knowledge Model après revue.
- Le nouvel audit E2 est la référence de sélection. L'ancien audit E reste la référence historique
  de la stratégie SNOMED/HAS.
- L'audit E2 n'autorise pas F : la double revue dont un clinicien et la vérification juridique des
  assertions distribuées restent obligatoires.

## Alternatives considérées

- **Attendre SNOMED/HAS :** rejeté comme dépendance obligatoire ; leurs blocages restent documentés.
- **Employer MeSH comme troisième terminologie dès v0.5 :** rejeté pour éviter mappings et
  dépendances sans bénéfice nécessaire au périmètre.
- **Ingestions A.D.A.M./Healthdirect/CC BY-ND :** rejetées sans permission explicite.
- **Publier un corpus non relu :** rejeté ; `pending_clinical_review` n'est pas un snapshot médical.

## Conséquences

- L'importeur RF2 synthétique de `v0.5-C` reste testé et disponible, mais une future adaptation
  DOID/Mondo sera un commit séparé après validation du corpus.
- Les concepts trop larges ou trop étroits restent reliés par des mappings qualifiés, sans score.
- Les pages NHS/nidirect apparentées partagent une famille de preuve ; les dépendances MedlinePlus
  inconnues restent non agrégeables.
- `v0.5-F` et `v0.5-G` restent bloqués tant que la checklist E2 n'est pas entièrement satisfaite.

## Sources et licences concernées

Voir [`docs/source-audits/v0.5-orl-open-sources.md`](../source-audits/v0.5-orl-open-sources.md) pour
les releases, hashes, licences, pages cliniques, exclusions et matrice de couverture.
