# Latros

## Document de conception — phase 0

**Statut actualisé le 18 septembre 2026 :** ce document conserve la vision initiale. Une première tranche interne de recherche est désormais autorisée et implémentée : maladies rares, CLI Python 3.11, HPO/Mondo/Orphadata, moteur `semantic_v1` et questions adaptatives. Voir [README](../README.md) et [ADR 0001](decisions/0001-socle-recherche.md) pour les choix applicables. Les autres composants ci-dessous restent prospectifs.

**Suivi des étapes :** le [plan d'implémentation](plan.md) décrit les jalons livrés `v0.1.0` à `v0.4.0`, la tranche `v0.5` encore non validée cliniquement et l'interface R&D `v0.6`. Les checkpoints techniques A à D de v0.5 sont implémentés sur des données entièrement inventées, y compris le pipeline canonique v2 et `general_v1`. Le `NO-GO` historique de E pour SNOMED/HAS est conservé. L'audit E2 retient DOID/Mondo et des sources ouvertes ; E3 matérialise un paquet réel de 17 assertions et 10 mappings, avec provenance et gate automatiques. Il reste intégralement `pending_review`. E4 permet de le construire localement sous l'identité explicite `v0.5.0-dev-unreviewed`, avec override volontaire et marquage non validé dans chaque résultat ; aucune validation humaine n'est inventée et le snapshot officiel `v0.5.0` reste bloqué. Le [cahier des charges de `v0.4`](v0.4-clinical-knowledge-model.md) documente le modèle général ; les [ADR 0005](decisions/0005-snapshot-v2-et-pilote-orl.md), [0006](decisions/0006-sources-ouvertes-pilote-orl.md) et [0007](decisions/0007-mode-recherche-orl-non-revu.md) encadrent les deux chemins ORL. `v0.6` ajoute une console web strictement locale, le service applicatif commun CLI/UI et des sessions reprenables avec runs immuables, selon l'[ADR 0008](decisions/0008-interface-locale-rd-et-sessions.md). Elle ne change aucun raisonnement médical. L'ancienne maquette locale a été supprimée après la livraison : l'interface officielle est autonome sous `src/latros/ui/`. Les extensions de temporalité, biologie, constantes, risques et médicaments passent en `v0.7`, le safety en `v0.8`, le NLP/LLM en `v0.9` et l'API/FHIR/interopérabilité en `v0.10`. Le snapshot clinique de référence reste `v0.2.0` et le paquet Python est `0.6.0`. [history.md](history.md), le README et le plan sont actualisés à chaque livraison.

**Évolution visuelle planifiée :** après le socle simple de v0.6, l’interface R&D pourra évoluer
vers une visualisation Knowledge Graph / « cerveau médical » inspirée des graphes Obsidian. Elle
servira à explorer, avec navigation, clusters, filtres et zoom, les relations réelles entre
observations, symptômes, signes, candidats, maladies rares ou courantes, assertions, contradictions,
terminologies, sources, provenance et questions discriminantes. Cette vue sera seulement une
projection interactive des données et du raisonnement existants : elle ne créera ni relation, ni
preuve, ni conclusion médicale supplémentaire.

**Objectif de la phase :** définir l'architecture scientifique, les responsabilités des composants, le modèle de données, les règles de provenance, les méthodes d'évaluation et les limites du projet avant de télécharger des jeux de données ou de coder le moteur.

---

## 1. Vision générale

Latros est une application médicale locale, *offline first*, inspirée du fonctionnement d'un symptom checker interactif comme Ada Health.

L'utilisateur doit pouvoir :

1. décrire librement ses symptômes par texte ;
2. faire corriger ou confirmer les informations comprises par le système ;
3. répondre progressivement à des questions médicales pertinentes ;
4. obtenir un diagnostic différentiel structuré ;
5. comprendre les arguments favorables et défavorables à chaque hypothèse ;
6. consulter les sources ayant conduit à chaque conclusion ;
7. comparer un moteur clinique pur, un LLM seul et une approche hybride.

Latros ne doit pas être un simple chatbot auquel on demande : « quelle maladie correspond à ces symptômes ? »

Le cœur du projet doit rester un moteur médical structuré, explicable et testable. L'IA générative constitue une couche complémentaire et remplaçable.

### Flux cible

```text
Description libre
        ↓
Extraction des informations cliniques
        ↓
Normalisation terminologique
        ↓
Confirmation ou correction par l'utilisateur
        ↓
Moteur de sécurité ───────► alerte ou orientation si nécessaire
        │
        ▼
Génération d'un diagnostic différentiel
        ↓
Sélection de la question la plus utile
        ↓
Mise à jour de l'état clinique et des scores
        ↓
Répétition jusqu'au critère d'arrêt
        ↓
Résultat structuré, explicable et sourcé
```

---

## 2. Principes fondamentaux

### 2.1 Le moteur doit pouvoir fonctionner sans LLM

Le mode **Pure Clinical Engine** prend une entrée structurée et produit un différentiel sans utiliser de modèle génératif.

```json
{
  "age": 22,
  "sex": "male",
  "present": [],
  "absent": [],
  "unknown": [],
  "risk_factors": []
}
```

La sortie doit distinguer le score calculé, les preuves, les contradictions et les informations manquantes.

```json
{
  "differential": [
    {
      "disease": "MONDO:...",
      "score": 0.71,
      "score_type": "compatibility",
      "supporting_evidence": [],
      "contradicting_evidence": [],
      "important_unknowns": []
    }
  ]
}
```

### 2.2 Un score n'est pas automatiquement une probabilité

Les bases maladie–phénotype fournissent principalement des fréquences du type :

```text
P(symptôme | maladie)
```

Elles ne fournissent généralement pas tout ce qui est nécessaire pour calculer :

```text
P(maladie | symptômes, âge, sexe, contexte)
```

Une probabilité diagnostique exige notamment :

- une prévalence adaptée à la population et au contexte de soins ;
- la fréquence du signe chez les personnes qui n'ont pas la maladie ;
- la prise en compte des dépendances entre signes ;
- les biais de recrutement des sources ;
- une calibration sur des cohortes représentatives.

Tant que ces éléments ne sont pas réunis et validés, le système doit parler de :

- score de compatibilité ;
- rang différentiel ;
- niveau de soutien ;
- ou score relatif interne.

Il ne doit pas afficher une pseudo-probabilité clinique comme « pneumonie : 72 % ».

### 2.3 Le triage est différent du diagnostic

Le moteur de sécurité doit être indépendant du classement diagnostique.

Une situation grave peut être peu probable tout en nécessitant une action immédiate. Les drapeaux rouges ne doivent donc pas être traités comme de simples symptômes pondérés dans le différentiel.

### 2.4 La provenance doit être conservée à la granularité de l'assertion

Chaque fait médical doit pouvoir répondre à :

> Qui affirme cette relation, dans quelle version, sur quelle population, avec quelle preuve et à partir de quelle référence ?

### 2.5 Le système doit pouvoir s'abstenir

Latros doit pouvoir indiquer :

- informations insuffisantes ;
- différentiel trop large ;
- données contradictoires ;
- concept non reconnu ;
- cas hors périmètre ;
- besoin d'une évaluation médicale réelle.

---

## 3. Architecture conceptuelle

L'architecture devrait séparer la construction de la connaissance et l'exécution clinique.

### 3.1 Fabrique de connaissances

Cette partie pourra utiliser Internet lors des mises à jour.

```text
Sources brutes versionnées
        ↓
Contrôle des licences et intégrité
        ↓
Validation des formats
        ↓
Normalisation proche de la source
        ↓
Résolution des identifiants et mappings
        ↓
Conservation des assertions et provenances
        ↓
Contrôles de qualité
        ↓
Construction d'un snapshot clinique versionné
```

### 3.2 Runtime clinique local

```text
Texte
        ↓
NLP / extraction clinique
        ↓
État clinique structuré
        ├──► moteur de sécurité
        └──► générateur de candidats
                  ↓
             moteur de classement
                  ↓
          moteur de questions
                  ↓
            moteur d'explication
```

Le runtime doit pouvoir utiliser un snapshot en lecture seule, reproductible et indépendant des formats changeants des sources originales.

---

## 4. Séparation des modules

### 4.1 `terminology`

Responsabilités :

- concepts médicaux ;
- libellés préférés ;
- synonymes ;
- traductions ;
- hiérarchies ;
- mappings exacts, larges, étroits ou associés ;
- gestion des concepts obsolètes, fusionnés ou divisés.

### 4.2 `knowledge`

Responsabilités :

- associations maladie–phénotype ;
- facteurs de risque ;
- épidémiologie ;
- âge d'apparition ;
- évolution ;
- critères diagnostiques ;
- exclusions ;
- références et provenance.

### 4.3 `clinical-state`

Responsabilités :

- patient ;
- épisode clinique courant ;
- observations présentes, absentes ou inconnues ;
- temporalité ;
- contexte ;
- valeurs mesurées ;
- origine et certitude de chaque observation.

### 4.4 `nlp`

Responsabilités :

- extraction depuis le texte ;
- négation ;
- temporalité ;
- latéralité ;
- intensité ;
- résolution terminologique ;
- génération de candidats de mapping ;
- repérage du fragment de texte justificatif.

### 4.5 `candidate-generator`

Responsabilité : produire une liste à rappel élevé de maladies ou syndromes compatibles, sans chercher encore à les classer parfaitement.

### 4.6 `reasoning-engine`

Responsabilités :

- appliquer les règles ;
- combiner les preuves ;
- calculer les scores ;
- pénaliser les contradictions ;
- conserver la trace de chaque contribution.

### 4.7 `question-engine`

Responsabilités :

- générer les questions candidates ;
- estimer leurs réponses possibles ;
- calculer leur utilité attendue ;
- éviter les répétitions ;
- appliquer les critères d'arrêt.

### 4.8 `safety-engine`

Responsabilités :

- détecter des combinaisons critiques ;
- appliquer des seuils sur les constantes ;
- reconnaître les situations imposant une orientation ;
- fonctionner sans dépendre exclusivement d'un LLM.

### 4.9 `explanation-engine`

Responsabilités :

- construire l'explication structurée ;
- relier chaque argument à une observation et à une assertion ;
- exposer les conflits et inconnues ;
- permettre une reformulation en langage naturel.

### 4.10 `llm-adapter`

Interface indépendante permettant de remplacer MedGemma, Qwen, Gemma, Llama, Mistral ou un autre modèle sans modifier le moteur clinique.

### 4.11 `evaluation`

Responsabilités :

- cas de référence ;
- comparaison des modes ;
- métriques diagnostiques ;
- métriques de triage ;
- métriques d'interrogatoire ;
- calibration ;
- reproductibilité ;
- analyses par sous-groupe.

---

## 5. Modèle de données médical

Deux objets différents doivent absolument rester séparés :

1. l'observation réalisée chez un patient ;
2. l'assertion d'une source à propos d'une maladie.

### 5.1 Observation clinique

```json
{
  "observation_id": "obs-123",
  "episode_id": "episode-42",
  "concept_id": "HP:...",
  "status": "present",
  "certainty": "asserted",
  "temporality": {
    "onset": "2026-09-13",
    "duration_days": 3,
    "course": "intermittent"
  },
  "body_site": "ear",
  "laterality": "right",
  "severity": null,
  "value": null,
  "unit": null,
  "experiencer": "patient",
  "source": {
    "type": "patient_utterance",
    "text_span": "mal à l'oreille droite depuis trois jours"
  }
}
```

Les qualificatifs ne doivent pas être fusionnés artificiellement dans le concept. « Douleur de l'oreille droite depuis trois jours » devrait être une douleur auriculaire avec latéralité et temporalité, pas nécessairement un nouveau concept composite.

### 5.2 Assertion de connaissance

```json
{
  "assertion_id": "assertion-456",
  "subject": "MONDO:...",
  "predicate": "has_phenotype",
  "object": "HP:...",
  "frequency": {
    "representation": "categorical_interval",
    "lower": 0.30,
    "upper": 0.79
  },
  "qualifiers": {
    "sex": null,
    "onset": null,
    "population": null,
    "clinical_setting": null
  },
  "evidence": {
    "code": "PCS",
    "reference": "PMID:...",
    "curation": "manual"
  },
  "provenance": {
    "original_source": "Orphadata",
    "ingestion_source": "Monarch",
    "source_release": "2026-07",
    "original_record_id": "..."
  }
}
```

### 5.3 Entités principales

Le modèle conceptuel devrait pouvoir représenter :

```text
Concept
ExternalIdentifier
ConceptMapping
Label
Synonym
Translation
HierarchyEdge
Source
SourceRelease
LicenceRecord
KnowledgeAssertion
EvidenceItem
Reference
FrequencyObservation
Patient
ClinicalEpisode
ClinicalObservation
Measurement
RiskFactorObservation
Question
Answer
ReasoningRun
ScoreContribution
SafetyAssessment
Explanation
```

---

## 6. Présent, absent et inconnu

Le raisonnement clinique doit au minimum distinguer :

```text
present
absent
unknown
```

Le moteur d'interrogatoire devrait conserver des états plus précis :

```text
not_asked
unknown_to_patient
uncertain
not_applicable
unable_to_assess
```

Plusieurs peuvent être ramenés à `unknown` pour le calcul, mais ils ne sont pas équivalents pour choisir la question suivante.

Règles :

- le silence ne signifie jamais `absent` ;
- « je ne sais pas » ne signifie jamais `absent` ;
- une absence doit être explicitement affirmée ou mesurée ;
- « absent aujourd'hui mais présent hier » nécessite une temporalité ;
- le LLM ne doit pas inventer une négation ;
- une observation douteuse doit conserver sa certitude.

---

## 7. Temporalité et contexte

La temporalité ne doit pas être réduite à un champ `duration_days` unique.

Le modèle devra pouvoir représenter :

- début brutal ou progressif ;
- date ou intervalle d'apparition ;
- durée ;
- intermittent ou continu ;
- fréquence des épisodes ;
- amélioration, aggravation ou stabilité ;
- récidive ;
- relation avec un déclencheur ;
- séquence entre plusieurs symptômes.

Le contexte devra être extensible pour :

- âge ;
- sexe pertinent cliniquement ;
- grossesse ;
- antécédents ;
- médicaments ;
- allergies ;
- tabac et alcool ;
- voyages ;
- contacts infectieux ;
- traumatisme ;
- chirurgie ;
- vaccinations ;
- facteurs génétiques ;
- profession et expositions ;
- environnement et contexte géographique.

Les mesures devront inclure une valeur, une unité, une méthode, une date, une plage de référence éventuelle et une provenance.

---

## 8. Identifiants et mappings

MONDO et HPO sont de bons identifiants préférentiels, mais ils ne devraient pas constituer les seules clés primaires internes.

```text
concept_key             clé interne immuable
preferred_external_id   identifiant externe préféré et versionné
external_identifier     MONDO, HPO, ORPHA, DOID, UMLS, etc.
mapping_type            exact / broad / narrow / related
mapping_confidence
mapping_evidence
valid_from_release
valid_to_release
status                  active / obsolete / merged / split
```

Une clé interne permet de conserver l'historique lorsqu'un concept externe est :

- rendu obsolète ;
- fusionné ;
- divisé ;
- remappé ;
- corrigé.

Les CUI UMLS ou MedGen ne doivent pas être supposés immuables. MedGen indique que certains CUI peuvent changer lors des mises à jour de l'UMLS.

Un mapping doit être une assertion qualifiée, pas seulement une paire d'identifiants.

---

## 9. Fusion de plusieurs bases

Les assertions originales doivent coexister avant toute agrégation.

```text
Assertion source A
Assertion source B
Assertion source C
        ↓
Vue agrégée calculée, versionnée et réversible
```

### 9.1 Éviter le faux consensus

Trois occurrences ne constituent pas nécessairement trois confirmations indépendantes.

```text
Orphadata
  └── repris par HPO
       └── repris par Monarch
```

Il peut s'agir d'une seule assertion passant par plusieurs canaux.

Il faut conserver :

- la source originale ;
- la source d'ingestion ;
- la référence primaire ;
- l'identifiant de l'assertion originale ;
- la famille de données ;
- la chaîne de dérivation ;
- le type de curation ;
- la version.

### 9.2 Politique initiale possible

1. Regrouper les assertions dérivées de la même origine.
2. Limiter la contribution maximale d'une même famille de sources.
3. Conserver les désaccords au lieu de les masquer.
4. Ne comparer que les fréquences portant sur des populations compatibles.
5. Diminuer la confiance lorsque la taille de cohorte est inconnue.
6. Produire une agrégation réversible pointant vers chaque assertion source.

Une méthode de fusion statistique définitive ne doit pas être choisie avant l'étude des données réelles.

---

## 10. Fréquences et incertitude

Le format interne doit conserver la représentation originale :

```text
exact_count       7/13
point_estimate    22 %
interval          30–79 %
category          fréquent
expert_excluded   exclusion par consensus ou curation
missing           fréquence non fournie
```

```json
{
  "kind": "count",
  "numerator": 7,
  "denominator": 13,
  "point": 0.538,
  "lower": null,
  "upper": null,
  "population": "...",
  "reference": "PMID:...",
  "method": "published_cohort"
}
```

Principes :

- un compte `k/n` peut ultérieurement être régularisé par un modèle bêta-binomial ;
- un intervalle doit rester un intervalle ou une distribution ;
- une catégorie ne doit pas être remplacée silencieusement par son milieu ;
- une fréquence manquante n'est ni zéro ni 0,5 ;
- `0/2` et `0/200` ne sont pas des preuves équivalentes ;
- une exclusion d'expert n'est pas identique à une fréquence observée de `0/n`.

---

## 11. Évaluation des sources envisagées

| Source | Rôle recommandé | Limites ou précautions |
|---|---|---|
| Monarch Knowledge Graph | Accélérateur d'intégration, exploration, mappings et génération de candidats | Agrège déjà d'autres sources ; risque majeur de double comptage |
| HPO et `phenotype.hpoa` | Noyau phénotypique, fréquences, apparition, modificateurs et négatifs | Fort biais vers les maladies rares et mendéliennes ; droits particuliers pour certaines annotations issues d'OMIM |
| Orphadata Science | Excellente source rare, fréquences et données multilingues | Couverture centrée sur les maladies rares |
| Mondo | Colonne vertébrale des concepts de maladie et des mappings qualifiés | Ontologie de maladie, pas base diagnostique complète |
| DDXPlus | Étude de l'interrogatoire, prototypes et benchmark | Patients synthétiques, 49 pathologies, générateur fondé sur une base propriétaire |
| Disease Ontology | Taxonomie, définitions et vérification de mappings | Partiellement redondante avec Mondo |
| Symptom Ontology | Vocabulaire complémentaire de signes et symptômes | Couverture, maintenance et adéquation clinique à évaluer |
| MedGen | Mappings génétiques et terminologiques | Agrégateur orienté génétique ; CUI susceptibles d'évoluer |
| Columbia Disease-Symptom KB | Baseline historique de maladies courantes | 150 maladies, notes d'hospitalisation de 2004, associations de cooccurrence |
| Wikidata | Alias, traductions et identifiants externes | Qualité variable ; ne pas utiliser comme preuve clinique primaire |
| Synthea | Tests FHIR, parcours patient et intégration système | Données simulées ; ne valide pas l'exactitude clinique |
| UMLS | Mapper terminologique puissant | Licence individuelle et restrictions propres à certains vocabulaires |
| SemMedDB | Découverte de relations et enrichissement expérimental | Extraction automatique bruitée, UMLS requis, dernière version annoncée comme finale |

### 11.1 Positionnement conseillé

**Socle terminologique initial à étudier :**

- Mondo pour les maladies ;
- HPO pour les phénotypes ;
- Orphadata pour les maladies rares ;
- Monarch comme accélérateur et source intégrée, sans le compter comme preuve indépendante.

**Sources secondaires :**

- Disease Ontology ;
- Symptom Ontology ;
- MedGen ;
- Wikidata.

**Sources pour les tests et l'évaluation :**

- DDXPlus ;
- Synthea ;
- Columbia KB avec prudence.

**Sources exploratoires :**

- SemMedDB ;
- littérature automatiquement extraite.

### 11.2 Lacune actuelle

L'ensemble est particulièrement fort pour les maladies rares, génétiques et les mappings, mais moins complet pour :

- la médecine générale ;
- les infections courantes ;
- les urgences ;
- les plaintes fonctionnelles ;
- les effets indésirables médicamenteux ;
- les probabilités en soins primaires.

Des catégories supplémentaires devront être étudiées :

- constatations cliniques générales, éventuellement SNOMED CT selon les droits applicables ;
- examens et analyses avec LOINC ;
- unités avec UCUM ;
- médicaments avec RxNorm ou ATC ;
- recommandations cliniques versionnées pour les drapeaux rouges ;
- données épidémiologiques contextualisées.

---

## 12. Moteur de diagnostic différentiel

Une architecture en deux étapes est préférable.

### 12.1 Génération de candidats

Objectif : rappel élevé.

Signaux possibles :

- correspondances directes ;
- ancêtres et descendants ontologiques ;
- similarité phénotypique ;
- âge et sexe ;
- contexte ;
- facteurs de risque ;
- règles spécifiques ;
- catégories syndromiques.

### 12.2 Classement

Une première formulation explicable pourrait être :

```text
score(d) =
    prior(d | âge, sexe, contexte)
  + preuves positives
  + preuves négatives
  + facteurs de risque
  + compatibilité temporelle
  - contradictions
  - pénalités de dépendance
```

Une formulation probabiliste future pourrait utiliser :

```text
log score(d) = log prior(d) + Σ poids_i × log LR_i
```

Mais un likelihood ratio nécessite également une estimation de la fréquence du signe hors de la maladie. Les seules fréquences HPO ou Orphadata ne suffisent donc pas.

### 12.3 Baselines à comparer

Avant de choisir une méthode définitive :

1. règles déterministes ;
2. similarité sémantique ou phénotypique ;
3. score pondéré explicite ;
4. modèle probabiliste simple avec hypothèses documentées ;
5. modèle appris seulement si des données appropriées existent.

### 12.4 Dépendances entre symptômes

Un modèle naïf risque de surcompter des manifestations corrélées, par exemple :

```text
infection respiratoire
  ├── toux
  ├── expectoration
  └── encombrement bronchique
```

Le projet devra étudier :

- regroupements de caractéristiques ;
- variables latentes syndromiques ;
- plafonnement des contributions proches ;
- modèles graphiques ;
- correction empirique lors de la calibration.

---

## 13. Moteur de questions adaptatives

L'entropie est une base utile, mais ne doit pas être le seul objectif.

```text
utilité(question) =
    réduction attendue d'incertitude
  + valeur de sécurité
  + impact sur l'orientation ou la conduite
  - coût cognitif
  - difficulté de réponse
  - redondance
```

Ordre de priorité recommandé :

```text
question de sécurité pertinente
        >
question modifiant la conduite
        >
question maximisant seulement l'information diagnostique
```

Le moteur doit :

- accepter `oui`, `non`, `incertain`, `je ne sais pas` et les réponses catégorielles ;
- éviter de demander plusieurs variantes du même signe ;
- ne pas demander au patient une interprétation qu'il ne peut pas raisonnablement fournir ;
- tenir compte de la pénibilité ou de la sensibilité d'une question ;
- arrêter lorsque l'information attendue devient faible ;
- arrêter et orienter lorsqu'une règle de sécurité le demande.

---

## 14. Moteur de sécurité clinique

Le moteur de sécurité doit être déterministe ou au minimum disposer d'une couche déterministe indépendante.

Il devra pouvoir analyser :

- douleur thoracique sévère ;
- détresse respiratoire ;
- déficit neurologique aigu ;
- altération importante de la conscience ;
- hémorragie importante ;
- constantes vitales critiques ;
- grossesse et symptômes à risque ;
- âge extrême et signes associés ;
- combinaisons de signes à haut risque.

Chaque règle devra conserver :

- sa source clinique ;
- sa version ;
- sa population cible ;
- ses exceptions ;
- le niveau d'urgence ;
- le message utilisateur ;
- les tests associés.

Le moteur de sécurité doit être évalué séparément avec une priorité donnée à la sensibilité et au risque de sous-triage.

---

## 15. Rôle du LLM

### 15.1 Fonctions autorisées initialement

#### Extraction clinique

Transformer le langage libre en observations structurées en conservant :

- le fragment de texte ;
- le concept candidat ;
- la négation ;
- la temporalité ;
- la certitude ;
- l'ambiguïté.

#### Reformulation

Transformer une question structurée en question naturelle, sans modifier son sens clinique.

#### Clarification

Formuler une question neutre lorsqu'un concept ou un qualificatif est ambigu.

#### Explication

Verbaliser une justification déjà produite par le moteur, sans créer de nouvelles preuves.

### 15.2 Fonctions à ne pas lui confier seul

- calculer le score final du mode moteur pur ;
- déterminer seul une urgence ;
- inventer une fréquence ;
- transformer une information inconnue en absence ;
- compléter silencieusement le dossier ;
- fournir une référence qui n'existe pas dans la base ;
- masquer un désaccord entre sources.

### 15.3 Niveaux hybrides

```text
H0 : entrée structurée + moteur pur
H1 : LLM pour l'extraction + moteur pur
H2 : moteur pur + LLM pour les questions et explications
H3 : LLM rerankant les résultats du moteur
```

`H3` doit être considéré comme un système expérimental différent : le résultat final n'est plus celui du moteur pur.

---

## 16. Intégration envisagée de MedGemma 1.5

### 16.1 Positionnement

MedGemma est une famille de modèles médicaux à poids accessibles proposée dans le programme Health AI Developer Foundations de Google. MedGemma 1.5 existe actuellement en version 4B multimodale.

Ses capacités annoncées couvrent notamment :

- texte médical ;
- compréhension de dossiers électroniques ;
- extraction de données de comptes rendus biologiques ;
- images médicales 2D ;
- ensembles de coupes CT ou IRM ;
- séries temporelles de radiographies thoraciques ;
- histopathologie ;
- localisation anatomique.

Le modèle 4B est présenté comme suffisamment compact pour des scénarios hors ligne. Les besoins matériels réels dépendront néanmoins de la quantification, du contexte, des images et du moteur d'inférence. Aucun budget matériel précis ne doit être arrêté sans benchmark local.

### 16.2 Rôles possibles dans Latros

MedGemma 1.5 pourrait être évalué comme :

1. extracteur d'observations cliniques depuis le texte ;
2. normalisateur proposant des concepts candidats ;
3. parseur de documents ou résultats biologiques ;
4. générateur de questions naturelles ;
5. générateur d'explications fidèles aux preuves ;
6. modèle du bras expérimental « LLM seul » ;
7. composant hybride recevant les sorties structurées du moteur ;
8. futur module multimodal expérimental pour la recherche.

### 16.3 Ce qu'il ne doit pas devenir

MedGemma ne doit pas devenir :

- la base médicale ;
- le calculateur implicite des probabilités ;
- le moteur unique de drapeaux rouges ;
- une source non traçable de nouvelles relations maladie–symptôme ;
- un interprète d'imagerie présenté comme clinique sans validation spécialisée.

Google indique explicitement que MedGemma est un modèle de départ destiné aux développeurs, qu'il n'est pas encore de niveau clinique et qu'il nécessite une validation et souvent une adaptation pour l'usage précis envisagé.

### 16.4 Texte contre multimodalité

Pour la première version de Latros, la partie texte est beaucoup plus directement utile que l'imagerie.

L'imagerie devrait rester un module futur séparé parce qu'elle ajoute :

- de nouveaux risques cliniques ;
- de nouveaux formats comme DICOM ;
- des exigences de prétraitement ;
- des évaluations par modalité ;
- des questions de qualité d'image ;
- un périmètre réglementaire plus lourd.

Une bonne séparation serait :

```text
MedGemma texte
    └── NLP, documents, explications, comparaison LLM

MedGemma multimodal
    └── piste de recherche indépendante et désactivée par défaut
```

### 16.5 Versions à comparer

La documentation actuelle distingue :

- MedGemma 1.5 4B multimodal ;
- MedGemma 1 27B texte ;
- MedGemma 1 27B multimodal.

Le modèle 4B favorise l'expérimentation locale. Les variantes 27B peuvent être plus performantes pour certaines tâches textuelles mais exigent davantage de ressources. Ce choix devra être fondé sur des mesures Latros, pas uniquement sur MedQA.

### 16.6 Licence et distribution

Les modèles HAI-DEF sont utilisables sous leurs conditions propres. Les dépôts Hugging Face peuvent être soumis à acceptation et collecte des coordonnées de l'utilisateur.

Latros devra enregistrer :

- la version exacte du modèle ;
- les conditions HAI-DEF applicables ;
- la provenance des poids ;
- le hash des fichiers ;
- les éventuelles restrictions de redistribution ;
- le modèle de base et les adaptations locales.

Il vaut mieux parler de modèle à poids accessibles ou *open-weight* que de supposer qu'il possède une licence logicielle permissive classique.

---

## 17. Intégration envisagée de TxGemma

### 17.1 Positionnement

TxGemma est une collection de modèles à poids accessibles de Google, construite sur Gemma 2 et spécialisée dans le développement de produits thérapeutiques. Les variantes officielles existent en plusieurs tailles, notamment 2B, 9B et 27B, avec des variantes de prédiction et des variantes conversationnelles.

TxGemma est conçu pour traiter des informations relatives à :

- petites molécules ;
- protéines ;
- acides nucléiques ;
- maladies ;
- lignées cellulaires ;
- cibles thérapeutiques ;
- propriétés utiles au développement de médicaments.

Ses usages annoncés couvrent des tâches de classification, de régression et de génération liées au développement thérapeutique. Il peut être exécuté localement pour l'expérimentation.

### 17.2 Place dans Latros

TxGemma ne répond pas au même besoin que MedGemma.

```text
MedGemma
    └── compréhension clinique, texte médical, documents et imagerie

TxGemma
    └── recherche thérapeutique, molécules, protéines et développement de médicaments
```

TxGemma ne doit donc pas participer au diagnostic différentiel principal ni au choix des questions posées au patient.

Il pourrait être étudié ultérieurement dans un module de recherche séparé pour :

- explorer des relations maladie–cible–molécule ;
- classer ou prédire certaines propriétés thérapeutiques ;
- analyser des données de recherche préclinique ;
- comparer des hypothèses de repositionnement de médicaments ;
- construire des expériences de recherche pharmaceutique reproductibles.

### 17.3 Limites de périmètre

TxGemma ne doit pas être utilisé pour :

- recommander directement un traitement à un patient ;
- prescrire ou ajuster une posologie ;
- inférer des contre-indications sans base clinique validée ;
- transformer une prédiction moléculaire en recommandation clinique ;
- remplacer des données pharmacologiques, toxicologiques ou d'essais cliniques ;
- modifier le classement diagnostique du moteur principal.

Une prédiction de propriété thérapeutique n'est pas une preuve d'efficacité ou de sécurité chez l'humain.

### 17.4 Architecture proposée

TxGemma devrait rester derrière une frontière de recherche explicite :

```text
Moteur clinique Latros
        │
        └── résultats diagnostiques structurés

Module thérapeutique expérimental séparé
        ├── données moléculaires et biologiques dédiées
        ├── TxGemma
        ├── références et provenance propres
        └── sorties marquées « recherche uniquement »
```

Les résultats de TxGemma ne devraient jamais être injectés silencieusement dans le moteur clinique. Toute passerelle future devra être explicite, versionnée, validée et désactivable.

### 17.5 Évaluation

TxGemma devra être évalué sur des tâches correspondant exactement à son usage, avec :

- séparation stricte des jeux d'entraînement et de test ;
- comparaison avec des modèles spécialisés et des baselines simples ;
- métriques adaptées à chaque tâche de classification ou régression ;
- contrôle des fuites de données et des analogues moléculaires proches ;
- estimation de l'incertitude ;
- validation externe ;
- analyse de la reproductibilité ;
- interdiction d'extrapoler une performance de benchmark vers un bénéfice clinique.

### 17.6 Licence et exécution locale

TxGemma est distribué sous les conditions de Health AI Developer Foundations. L'accès aux poids via Hugging Face nécessite l'acceptation de ces conditions.

Latros devra conserver :

- la variante exacte utilisée ;
- sa taille et son type, prédiction ou conversation ;
- la version des poids ;
- les conditions d'utilisation ;
- les adaptations locales ;
- les données utilisées pour l'évaluation ;
- les hashes et paramètres d'inférence.

---

## 18. Comparaison moteur pur, LLM et système hybride

Comparer uniquement trois listes finales mélangerait plusieurs causes d'erreur.

Une erreur peut venir :

- de l'extraction ;
- du mapping ;
- du classement ;
- du choix des questions ;
- de la reformulation.

### 18.1 Protocole factoriel recommandé

| Entrée | Extraction | Raisonnement | Questions | Explication |
|---|---|---|---|---|
| annotations humaines | humaine | moteur | moteur | structurée |
| texte brut | MedGemma | moteur | moteur | structurée |
| texte brut | MedGemma | MedGemma | MedGemma | MedGemma |
| texte brut | MedGemma | hybride | moteur ou hybride | MedGemma contrainte |

Cette matrice permet d'attribuer les erreurs à un composant.

### 18.2 Paramètres à figer

Pour chaque expérience :

- modèle et version ;
- quantification ;
- moteur d'inférence ;
- prompt ;
- température et paramètres de génération ;
- version de la base ;
- version des mappings ;
- règles de sécurité ;
- matériel ;
- graines aléatoires lorsque possible.

### 18.3 Métriques

#### Diagnostic différentiel

- rappel du diagnostic correct dans le top 1, 3, 5 et 10 ;
- rang réciproque moyen ;
- NDCG ou métrique de qualité du classement ;
- couverture des diagnostics plausibles ;
- taux d'hypothèses non supportées.

#### Probabilités éventuelles

- Brier score ;
- log loss ;
- courbes de calibration ;
- Expected Calibration Error ;
- calibration par sous-groupe.

#### Sécurité

- sensibilité des drapeaux rouges ;
- taux de sous-triage ;
- taux de sur-triage ;
- temps ou nombre de questions avant détection.

#### Interrogatoire

- nombre de questions ;
- information gagnée par question ;
- taux de questions redondantes ;
- taux d'abandon ;
- compréhension et réponse possible par le patient.

#### NLP

- exactitude des concepts ;
- négation ;
- temporalité ;
- latéralité ;
- valeurs et unités ;
- impact clinique des erreurs.

#### Robustesse et équité

- âge ;
- sexe ;
- langue ;
- niveau de littératie ;
- formulations familières ;
- informations contradictoires.

---

## 19. Explicabilité

Chaque résultat devrait être accompagné d'un objet de preuve.

```json
{
  "candidate": "MONDO:...",
  "score_type": "compatibility",
  "score": 0.71,
  "contributions": [
    {
      "observation_id": "obs-1",
      "direction": "supporting",
      "magnitude": 0.18,
      "assertion_ids": ["assertion-456"]
    }
  ],
  "contradictions": [],
  "important_unknowns": [],
  "knowledge_snapshot": "2026-09-01",
  "reasoner_version": "baseline-1"
}
```

L'explication textuelle, générée ou non, doit être une vue de cet objet.

Elle doit montrer :

- les arguments favorables ;
- les arguments défavorables ;
- les données manquantes ;
- les sources ;
- les conflits entre sources ;
- les hypothèses du modèle ;
- les mappings ambigus ;
- la version de la connaissance ;
- le type réel du score.

Un LLM ne doit pas inventer a posteriori une justification plausible mais absente du calcul.

---

## 20. Provenance et reproductibilité

Chaque source devra conserver :

```text
nom
version
date de publication
date de récupération
URL ou emplacement
hash du fichier
licence
conditions de redistribution
identifiant externe
schéma ou version de format
pipeline d'import utilisé
```

Chaque exécution du moteur devra conserver :

```text
version du snapshot
version du moteur
version des règles de sécurité
version des modèles
paramètres
entrée structurée
sortie
trace des contributions
```

Les contrôles de qualité de la fabrique de données devraient inclure :

- intégrité référentielle ;
- identifiants obsolètes ;
- conflits de mappings ;
- chaînes de provenance cassées ;
- fréquences invalides ;
- doublons probables ;
- changements importants entre versions ;
- compatibilité des licences ;
- rapports de couverture.

---

## 21. Stockage local

Sans choisir définitivement une technologie, la structure logique peut être :

```text
medical-data/
  raw/
    source/version/fichiers-originaux
  staging/
    données nettoyées proches de la source
  canonical/
    concepts, mappings, assertions, provenance
  runtime/
    snapshot optimisé et dérivations

patient-data/
  épisodes cliniques protégés et séparés

models/
  manifestes, poids et configurations autorisés
```

Un graphe logique n'impose pas Neo4j. Les relations peuvent initialement être stockées dans des tables d'arêtes.

À évaluer plus tard :

- Parquet pour les données intermédiaires ;
- DuckDB pour la construction, les contrôles et l'analyse ;
- SQLite ou DuckDB en lecture seule pour le runtime ;
- base graphe uniquement si des requêtes multi-sauts centrales le justifient.

Les données patient ne doivent jamais être mélangées au snapshot médical distribuable.

---

## 22. Sécurité informatique et confidentialité

*Offline first* ne signifie pas automatiquement sécurisé.

Le projet devra prévoir :

- séparation connaissance/données patient ;
- chiffrement des données sensibles ;
- suppression contrôlée ;
- limitation des journaux ;
- absence de données médicales dans les logs techniques ;
- gestion des modèles et fichiers téléchargés ;
- vérification des hashes ;
- mise à jour signée ou vérifiable ;
- audit local ;
- sauvegardes et politique de rétention ;
- protection contre les injections de prompt dans les documents importés.

---

## 23. Limites scientifiques et risques

### 23.1 Biais de couverture

Les sources rares et génétiques peuvent surreprésenter des maladies rares dans un contexte de symptômes courants.

### 23.2 Biais de publication

Les cas inhabituels et manifestations remarquables sont davantage publiés.

### 23.3 Dépendance des sources

Plusieurs bases peuvent republier la même assertion.

### 23.4 Fréquences non comparables

Des cohortes hospitalières, pédiatriques, génétiques et de soins primaires ne peuvent pas être fusionnées naïvement.

### 23.5 Absence de vraies données négatives

Une manifestation non mentionnée dans une source n'est pas forcément absente.

### 23.6 Corrélation des symptômes

Additionner plusieurs signes liés peut produire une confiance artificielle.

### 23.7 Données synthétiques

DDXPlus et Synthea sont utiles pour le développement, mais ne remplacent pas une validation clinique réelle.

### 23.8 Hallucinations et variabilité des LLM

MedGemma ou un autre LLM peut produire une réponse convaincante mais fausse, omettre un détail ou modifier son résultat entre exécutions.

### 23.9 Faux sentiment de précision

Une interface affichant des pourcentages détaillés peut sembler plus fiable que les données sous-jacentes.

### 23.10 Déplacement de distribution

Un système évalué sur des vignettes structurées peut échouer sur des patients réels, avec comorbidités, langage imprécis et informations manquantes.

### 23.11 Automation bias

Un utilisateur ou professionnel peut accorder trop de confiance à une liste bien présentée.

---

## 24. Cadre clinique et réglementaire

Latros doit se présenter comme un outil d'aide à l'orientation ou à la recherche, pas comme un diagnostic certain.

Cependant, un simple avertissement ne détermine pas à lui seul le statut réglementaire. Si le logiciel fournit des informations destinées à des décisions diagnostiques ou thérapeutiques, il peut relever du règlement européen relatif aux dispositifs médicaux.

Le règlement européen 2017/745, notamment sa règle 11, classe les logiciels selon l'impact potentiel des décisions prises à partir de leurs informations. La conception doit donc anticiper :

- gestion des risques ;
- traçabilité ;
- validation clinique ;
- contrôle des versions ;
- cybersécurité ;
- surveillance des performances ;
- définition précise de l'usage prévu.

La qualification juridique exacte devra être examinée avec des spécialistes si le projet dépasse le stade de recherche.

---

## 25. Périmètre de la phase 0

### À faire

- définir le premier domaine clinique ;
- définir la population et l'utilisateur cible ;
- définir la sortie et son vocabulaire ;
- formaliser le modèle de données ;
- formaliser les niveaux de provenance ;
- classifier les sources par rôle ;
- définir les modes pur, LLM et hybrides ;
- définir le protocole d'évaluation ;
- définir les règles de sécurité conceptuelles ;
- analyser les licences et dépendances ;
- établir un registre des décisions d'architecture.

### À ne pas faire encore

- télécharger toutes les bases ;
- écrire les importeurs ;
- créer la base finale ;
- coder le moteur diagnostique ;
- choisir définitivement les technologies ;
- entraîner ou adapter un modèle ;
- créer l'interface ;
- présenter des performances cliniques.

---

## 26. Décisions fondamentales à discuter

1. Quel est le premier périmètre clinique : médecine générale, ORL, maladies rares, urgences ou autre ?
2. L'utilisateur cible est-il le grand public, un étudiant, un chercheur ou un professionnel ?
3. Le résultat est-il un score de compatibilité, une priorité clinique, une orientation ou une probabilité calibrée ?
4. À quel niveau de granularité les maladies doivent-elles être comparées ?
5. Comment séparer précisément le différentiel du triage ?
6. Comment identifier les sources dépendantes ?
7. Quel schéma commun utiliser pour les observations ?
8. Comment représenter et propager l'incertitude ?
9. Quelles fonctions exactes sont autorisées au LLM ?
10. L'imagerie fait-elle partie du projet ou d'une piste de recherche séparée ?
11. TxGemma doit-il rester hors périmètre ou alimenter un module de recherche thérapeutique séparé ?
12. Quelles performances minimales doivent être atteintes avant chaque changement de phase ?
13. Quel usage prévu souhaite-t-on revendiquer à terme ?

---

## 27. Recommandation de trajectoire

### Étape A — spécification

- modèle clinique ;
- provenance ;
- identité des concepts ;
- périmètre ;
- protocole expérimental.

### Étape B — preuve de concept étroite

- petit sous-ensemble clinique ;
- entrée structurée manuellement ;
- moteur pur simple ;
- explications déterministes ;
- aucun LLM nécessaire.

### Étape C — comparaison des raisonnements

- plusieurs baselines du moteur ;
- MedGemma comme bras LLM ;
- protocole reproductible ;
- aucun résultat présenté comme validé cliniquement.

### Étape D — langage naturel

- extraction MedGemma ou autre ;
- confirmation utilisateur ;
- tests de négation, temporalité et ambiguïté.

### Étape E — extension

- laboratoires ;
- documents ;
- médicaments ;
- éventuellement imagerie dans un module séparé ;
- éventuellement TxGemma dans un module thérapeutique de recherche séparé.

---

## 28. Conclusion actuelle

Latros repose sur une direction saine : connaissance structurée au centre, IA générative à la périphérie, exécution locale et comparaison expérimentale des approches.

Les points les plus importants à préserver sont :

1. ne pas confondre compatibilité et probabilité ;
2. conserver les assertions originales avant toute fusion ;
3. reconnaître les dépendances entre bases ;
4. séparer triage, diagnostic, NLP et explication ;
5. utiliser MedGemma comme composant remplaçable, jamais comme vérité clinique ;
6. maintenir TxGemma dans un module thérapeutique expérimental séparé ;
7. mesurer séparément chaque étape du système ;
8. prévoir la reproductibilité et la réglementation dès la conception.

MedGemma 1.5 est particulièrement intéressant pour l'extraction médicale locale, les documents, les comparaisons LLM et, plus tard, la multimodalité. TxGemma peut compléter le projet dans un espace de recherche thérapeutique clairement isolé, mais ne doit pas intervenir dans le diagnostic différentiel principal ni produire de recommandations de traitement au patient.

### Invariant ajouté — souveraineté locale

La fabrique de connaissances de Latros repose exclusivement sur des distributions officielles
téléchargeables, figées et vérifiées. Après acquisition initiale, reconstruire un snapshot, lancer
les moteurs, poser les questions et utiliser l'interface ne doit provoquer aucun accès réseau. Les
API externes ne constituent pas une architecture de données acceptable. MedlinePlus XML, MeSH XML
et les releases Monarch ouvrent la première extension généraliste ; le pilote ORL reste un corpus
historique de régression.

---

## 29. Sources de référence consultées

### Ontologies et connaissances

- [Téléchargements du Monarch Knowledge Graph](https://monarchinitiative.org/kg/downloads)
- [Documentation du Monarch Knowledge Graph](https://monarch-app.monarchinitiative.org/)
- [HPO — format `phenotype.hpoa`](https://obophenotype.github.io/human-phenotype-ontology/annotations/phenotype_hpoa/)
- [HPO — représentation des fréquences et annotations négatives](https://obophenotype.github.io/human-phenotype-ontology/annotations/frequency/)
- [Orphadata Science — phénotypes associés aux maladies rares](https://sciences.orphadata.com/phenotypes/)
- [Mondo — présentation et principes de mapping](https://mondo.monarchinitiative.org/)
- [Mondo — téléchargements et licence](https://mondo.monarchinitiative.org/pages/download/)
- [DDXPlus — documentation du jeu de données](https://github.com/mila-iqia/ddxplus/blob/main/README.md)
- [MedGen — traitement des données et stabilité des mappings](https://www.ncbi.nlm.nih.gov/medgen/docs/data/)
- [Symptom Ontology — OBO Foundry](https://obofoundry.org/ontology/symp.html)
- [Human Disease Ontology](https://github.com/DiseaseOntology/HumanDiseaseOntology)
- [UMLS — présentation et accès](https://www.nlm.nih.gov/research/umls/index.html)
- [Synthea — générateur de patients synthétiques](https://github.com/synthetichealth/synthea)
- [Columbia Disease-Symptom Knowledge Database](https://impact.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html)
- [SemMedDB — téléchargement et statut](https://lhncbc.nlm.nih.gov/temp/SemRep_SemMedDB_SKR/SemMedDB_download.html)
- [Wikidata — licence des données structurées](https://www.wikidata.org/wiki/Wikidata%3ALicensing)

### MedGemma et TxGemma

- [Documentation MedGemma](https://developers.google.com/health-ai-developer-foundations/medgemma)
- [Documentation TxGemma](https://developers.google.com/health-ai-developer-foundations/txgemma)
- [Exécution locale de TxGemma](https://developers.google.com/health-ai-developer-foundations/txgemma/get-started)
- [Carte du modèle TxGemma](https://huggingface.co/google/txgemma-27b-chat)
- [Health AI Developer Foundations](https://developers.google.com/health-ai-developer-foundations)

### Cadre européen

- [Règlement européen 2017/745 relatif aux dispositifs médicaux](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32017R0745)
- [MDCG 2019-11 rev.1 — qualification et classification des logiciels médicaux](https://health.ec.europa.eu/latest-updates/update-mdcg-2019-11-rev1-qualification-and-classification-software-regulation-eu-2017745-and-2025-06-17_en)
- [MDCG 2020-1 — évaluation clinique des logiciels médicaux](https://health.ec.europa.eu/system/files/2020-09/md_mdcg_2020_1_guidance_clinic_eva_md_software_en_0.pdf)
