# ADR 0003 — Knowledge Model canonique v2

Statut : accepté.

Date : 17 septembre 2026.

## Contexte

Les sept tables actuelles décrivent correctement le snapshot rare v1 mais confondent encore le
format source Orphadata avec la relation canonique maladie–phénotype. Plusieurs sources futures
pourront republier une même preuve ou utiliser des terminologies différentes.

## Décision

- Séparer `SourceAssertion`, `CanonicalAssertion` et `ReasoningContribution`.
- Conserver chaque enregistrement source et relier les doublons sémantiques à une assertion
  canonique sans suppression destructive.
- Stocker les mappings dans un contrat distinct avec direction et relation
  `exact | equivalent | broader | narrower | related | unresolved`; un mapping ne constitue pas
  une preuve diagnostique.
- Utiliser un vocabulaire fermé de relations cliniques v2 : symptôme, signe, facteur de risque,
  laboratoire, examen, imagerie, âge typique, sexe typique et complication.
- Identifier une assertion source par release, artefact, record et ordinal; identifier une
  assertion canonique par sa signature normalisée versionnée.
- Déclarer les familles de preuves et les dépendances `primary`, `derived_from`, `republication`,
  `shared_upstream` ou `unknown`.
- Exclure par défaut une dépendance inconnue d'un agrégat multi-source, tout en conservant sa vue
  séparée.
- Exposer `v0.2.0` par un adaptateur de lecture; ne pas migrer ni réécrire son manifeste.

## Alternatives considérées

Fusionner les concepts sur xref ou compter chaque base comme un vote créerait de fausses identités
et de faux consensus. Une table clé/valeur unique rendrait les relations et valeurs impossibles à
valider.

## Conséquences

Le schéma v2 est d'abord vérifié avec des fixtures inventées. Aucun snapshot médical v2 n'est
publié pendant v0.4. Les futures sources doivent déclarer leurs dépendances avant de participer à
un score agrégé.

