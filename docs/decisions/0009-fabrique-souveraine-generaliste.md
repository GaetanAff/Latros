# ADR 0009 — Fabrique de connaissances généraliste souveraine

Statut : accepté
Date : 20 septembre 2026

## Contexte

Le snapshot publié `v0.2.0` couvre principalement les maladies rares et le corpus
`v0.5.0-dev-unreviewed` est un pilote ORL étroit, non validé, dont les douze captures ne doivent
plus constituer la fondation de la médecine générale. Latros doit étendre sa couverture sans devenir
un client d'API médicale ni perdre les invariants des ADR 0001 à 0008.

## Décision

- La souveraineté locale est un invariant d'architecture. Seule une commande explicite
  `sources fetch` peut accéder au réseau. Build, inspection, raisonnement, questions, interface et
  consultation de provenance utilisent exclusivement des artefacts locaux vérifiés.
- Toute source du pipeline principal possède une release ou une identité de capture figée, une URL
  officielle, un nom de fichier, un SHA-256 attendu, une licence, des droits de transformation et de
  redistribution audités, un importeur identifié et une date de récupération.
- Les rôles médicaux sont fermés et explicites. Terminologie, classification, benchmark et données
  synthétiques ne deviennent jamais des preuves cliniques par simple présence d'une relation.
- La chaîne est séparée en `raw source -> parsed source record -> candidate assertion -> normalized
  assertion -> usable assertion`. Un candidat produit par agent reste non validé jusqu'à une revue
  humaine enregistrée. Seuls les mappings résolus `exact/equivalent` pourront devenir scorables.
- MedlinePlus Health Topics XML est la première source d'assertions candidates. MeSH XML sert à
  l'indexation et aux mappings. Monarch KG est une source agrégée dont la provenance primaire et les
  dépendances doivent être conservées. Aucun moteur spécifique à une source n'est créé.
- `general_v1` reste le moteur cible ; ses mathématiques, son abstention, sa couverture, ses familles
  de preuves et son vocabulaire de compatibilité non probabiliste ne sont pas reconstruits.
- Le premier identifiant réservé est `v0.7.0-general-dev-unreviewed`. Il ne désigne aucun snapshot
  publié et ne sera créé qu'après acquisition locale, normalisation et manifeste complet. Le pilote
  ORL reste un corpus historique de régression, sans dépendance du futur snapshot généraliste.
- CDC est marqué `NOT SUITABLE FOR SOVEREIGN INGESTION` tant qu'aucune distribution officielle,
  générale, figée et juridiquement réutilisable n'est identifiée. Les API et le crawl du site ne
  sont pas des contournements acceptables.

## Compatibilité

Les manifestes v2 déjà publiés restent immuables et lisibles. Les champs souverains ajoutés au type
de paquet source sont optionnels lors de la lecture d'un ancien manifeste, mais obligatoires quand
un nouveau `RegistryV2` est validé pour un build. Les tables canoniques v2 ne sont pas modifiées par
le contrat de staging des candidats.

## Conséquences

- Les gros dumps restent sous `data/raw/` et hors Git.
- Un registre ne peut pas utiliser `latest`, `main` ou `master` comme identité de release.
- La reproductibilité nécessite de conserver les artefacts acquis ; une page qui ne garde que les
  six dernières captures impose une identité locale date + URL + hash.
- Les futures mesures LOINC/UCUM conservent valeur et unité ; elles ne sont pas aplaties en HPO.
- DDXPlus et Synthea restent respectivement benchmark et données synthétiques de test.

## Alternatives rejetées

- Requêtes runtime vers CDC, MedlinePlus, Monarch ou NLM.
- Extraction automatique de tout texte MedlinePlus en connaissance approuvée.
- Double comptage d'une assertion primaire republiée par Monarch.
- Réutilisation du corpus ORL comme socle artificiel de médecine générale.
