# ADR 0001 — Socle local maladies rares et moteur pur

Statut : accepté pour la première tranche, conformément au plan d'implémentation demandé.

Date : 16 septembre 2026.

## Contexte

Valider provenance, identités, fréquences et interrogatoire adaptatif avant la médecine générale ou les LLM. Les données structurées choisies décrivent surtout des maladies rares ; cela ne constitue pas une couverture représentative d'un symptom checker grand public.

## Décision

- Python 3.11, uv et verrou versionné ; Pydantic, Typer, httpx, orjson, lxml ; DuckDB/Parquet ; pytest, Ruff, mypy.
- HPO/Mondo du 1er septembre 2026 et Orphadata Science product4 EN/FR de l'archive juillet 2026. URLs épinglées, hashes obligatoires, registre séparé.
- Identifiants internes déterministes. Maladies ORPHA conservées séparément des concepts Mondo ; `exactMatch` explicite exposé, `xref` jamais converti en équivalence.
- Sept tables, validation avant publication par manifeste, runtime en lecture seule, aucune source brute sur GitHub.
- `semantic_v1` : compatibilité sémantique, aucune probabilité clinique. `question_v1` : entropie d'une distribution auxiliaire, pas de modèle bayésien validé.
- Remplacement unique des concepts HPO obsolètes suivi en conservant l'identifiant original. Sans remplacement : conservation inactive avec avertissement, exclusion du moteur. Identifiant inconnu ou remplacement ambigu : build bloqué.
- EN/FR d'une assertion coalescés après vérification. Enregistrements distincts contradictoires conservés, fréquence non utilisable pour pénalités/questions. Identifiant de record répété dans un même fichier : build bloqué.
- HPOA/Monarch/UMLS/DDXPlus et autres sources reportés. Ni Docker, API web, UI, audio, LLM, MedGemma, TxGemma ni entraînement dans cette tranche.
- `safety_status: not_evaluated` partout ; aucune utilisation patient.

## Précisions issues des données réelles

Orphadata référence un concept HPO obsolète sans `replaced_by` exact. L'identifiant existe dans HPO : il est conservé mais inactif. Un lien `consider` ne devient pas une équivalence.

Des couples maladie–phénotype possèdent des fréquences discordantes avec des identifiants de records distincts. Ce ne sont pas deux traductions ou un record répété. Le conflit reste visible ; aucune moyenne implicite ni sélection arbitraire n'est pratiquée.

Le fichier français ne garantit pas des termes HPO traduits : un libellé identique à un équivalent anglais connu reste `en`, indépendamment de la langue du document source.

La reconstruction complète produit des tables et Parquet identiques mais peut changer les octets internes du fichier DuckDB. Le manifeste versionné identifie donc les données canoniques ; l'intégrité du conteneur runtime est contrôlée séparément par un reçu local, jamais utilisé comme identité du snapshot.

## Alternatives et conséquences

Neo4j, des posteriors bayésiens, une fusion par xrefs ou un modèle génératif ne sont pas nécessaires à ce test initial. DuckDB/Parquet rendent les tables inspectables sans service permanent. Le pipeline charge toutefois les ontologies en mémoire ; une ingestion en flux pourra être ajoutée si les volumes augmentent.

Score et utilité des questions sont des bases expérimentales. Les coefficients, midpoints et softmax sont versionnés et devront être évalués. Les tests logiciels ne remplacent pas une évaluation clinique indépendante, un moteur de sécurité ou une revue du cadre applicable avant tout changement d'audience.

## Sources et licences

Voir [registre](../../sources/registry.yaml), [méthode](../methodology.md) et [README](../../README.md). HPO possède ses propres conditions ; Mondo et Orphadata sont attribués sous CC BY 4.0 dans le registre. Les fichiers sources et bases restent locaux, même pour le dépôt privé.
