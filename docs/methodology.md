# Méthode : semantic_v1 et question_v1

Cette spécification décrit un comportement calculé, **pas une validité clinique démontrée**. Les données du cas sont déjà structurées. Aucune extraction de texte libre ni inférence de signe absent.

## Données, identités et provenance

Les sept tables sont définies dans [canonical-tables.json](../schemas/canonical-tables.json). Fréquences et provenances imbriquées sont stockées comme chaînes JSON et exposées comme objets dans la CLI.

L'identifiant interne d'un concept est le SHA-256 d'un tuple contenant son identifiant externe avec namespace, précédé d'un type. Il ne dépend pas du libellé ou de l'ordre d'import. Une assertion est identifiée par sa source et son identifiant de record. Chaque ligne est reliée à une release, à ses licences et artefacts via `source_release`.

HPO/Mondo apportent les classes de leur namespace, termes, identifiants alternatifs, remplacements et arêtes `is_a`. Les axiomes OWL complexes et arêtes inter-ontologies ne sont pas interprétés. Les mappings ORPHA restent des liens qualifiés avec leur expression source. Leurs cibles sont des références externes, pas des clés étrangères exigeant que toute maladie Mondo existe dans product4.

Les maladies associées sont des concepts ORPHA ; Mondo ne les fusionne pas automatiquement. Les maladies sans annotation product4 ne sont pas candidates. EN/FR de même identifiant doivent porter la même assertion ; les deux provenances restent présentes sans double comptage. HPO obsolète sans remplacement exact : conservé dans les tables, exclu du moteur, refusé comme entrée clinique.

Chaque assertion conserve identifiants originaux, polarité, fréquence structurée, release, langues des artefacts, hashes, records, libellés de fréquence, référence Orphanet et chaîne d'ingestion. Les publications individuelles ne sont pas inventées si le produit ne les fournit pas. Le qualificatif source « diagnostic criterion » est conservé mais non pondéré.

La validation bloque références internes inconnues, cycles, records répétés, traductions contradictoires, fréquences invalides et provenance absente. Des records distincts du producteur peuvent partager un couple maladie–phénotype : ils ne sont jamais additionnés comme des votes indépendants. Si leurs fréquences diffèrent, le couple est signalé et sa fréquence ne sert ni aux pénalités ni aux questions.

## Fréquences

Le contrat préserve `count` (k/n), `percentage`, `interval`, `category`, `excluded`, `missing`, leurs valeurs brutes et bornes. Product4 utilise des catégories : 100 %, 80–99 %, 30–79 %, 5–29 %, 1–4 %, exclusion à 0 %. Exclusion et valeur manquante sont différentes.

Lorsqu'un scalaire est nécessaire, `f` est défini ainsi :

- compte : `(k + 1) / (n + 2)`, lissage Beta(1,1), en conservant k/n original ;
- pourcentage : valeur / 100 ;
- intervalle/catégorie : milieu des bornes ;
- exclusion : 0 ;
- manquante ou en conflit : inutilisable.

Ces approximations ne sont ni des incertitudes calibrées ni des probabilités diagnostiques. Le milieu d'une catégorie n'est pas une estimation épidémiologique publiée. Des études de sensibilité sur les bornes restent à effectuer.

## Cas et candidats

`ClinicalCase` contient identifiant pseudonyme, âge/sexe optionnels, observations HPO et historique des questions. États : `present`, `absent`, `unknown`. Doublons et réponses contradictoires sont refusés. Aliases et remplacements uniques sont résolus ; présence d'un enfant avec absence explicite d'un ancêtre HPO est incohérente et refusée.

Un candidat doit avoir une annotation positive qui est un ancêtre ou un descendant d'un signe présent, égalité incluse. Un simple ancêtre commun lointain ne suffit pas. Cette restriction peut manquer les maladies correspondant seulement par des termes frères ; ce compromis de rappel devra être mesuré.

Le corpus IC contient les maladies avec au moins une annotation positive active. Une maladie compte une fois par terme propagé, indépendamment du nombre d'assertions ou de langues.

## Score de compatibilité

Soit `D` le nombre de maladies du corpus et `D(t)` le nombre de maladies annotées à `t` ou à ses descendants :

```text
IC(t) = -ln(D(t) / D)
Resnik(x, y) = max IC(a), pour a ancêtre commun de x et y (eux-mêmes inclus)
positif(d) = moyenne, sur les signes présents x, du maximum Resnik(x, y)
             sur les annotations positives y de d
score(d) = positif(d) - pénalités_absences(d) - pénalités_exclusions(d)
```

Un terme jamais annoté a conventionnellement IC = 0 ; aucune pseudofréquence de maladie n'est inventée. Les signes sans contribution positive comptent dans le dénominateur. Les égalités sont départagées par identifiant de manière déterministe.

Pour un signe explicitement absent `x`, seules les annotations de `d` à `x` ou à ses descendants constituent une contradiction. Un signe frère ou une annotation à un ancêtre ne permet pas d'affirmer que le signe précis était attendu. Prendre la fréquence utilisable maximale `f`, puis pénaliser de `IC(x) × f`. Les pénalités sont **additionnées**, coefficient 1. Une absence sans fréquence ne modifie aucune contribution, y compris celles des autres absences.

Si un signe présent `x` contredit une exclusion source de `x` ou d'un ancêtre, appliquer une pénalité `IC(x) / nombre_de_signes_présents` (une seule par signe). Aucun bonus à une absence conforme à une exclusion. Une exclusion sans IC positif peut être affichée comme contradiction avec contribution nulle.

Les scores peuvent être négatifs et dépasser 1. Ils ne se comparent pas directement entre snapshots dont les corpus IC diffèrent. Âge, sexe, prévalence, durée et risques ne sont pas utilisés. Des signes corrélés ou ancêtre/enfant peuvent surpondérer un même phénomène : ce n'est pas un modèle d'indépendance clinique validé.

Les 20 premiers candidats sont triés par score décroissant puis identifiant ORPHA. Chaque contribution expose observation, phénotype source, ancêtre de correspondance, règle, montant, assertion justificative, fréquence et provenance. La fréquence affichée dans un argument Resnik est contextuelle : elle n'entre pas dans le calcul positif. Les conflits restent exposés.

## Question adaptative

1. Garder les dix premiers candidats ; poids internes par softmax des scores, température fixe 1. Ce ne sont **pas des probabilités de maladie**.
2. Chercher leurs signes non interrogés. Exclure ceux déjà présents/absents/inconnus, les ancêtres impliqués par une présence, les descendants impliqués par une absence, les inactifs et la racine HPO.
3. Utiliser uniquement des fréquences directement annotées au signe, sans propagation hiérarchique de fréquence. Un couple en conflit est non couvert.
4. Exiger au moins 60 % du poids couvert. Une exclusion explicite est connue à 0 ; aucune annotation n'est pas une exclusion.
5. Poser `p = somme(w × f) / couverture`. Pour les candidats sans fréquence, utiliser `p` comme vraisemblance auxiliaire de oui : leur poids reste neutre après oui ou non. Ce remplacement ne modifie jamais la base.
6. Calculer `IG = H(w) - p × H(w_si_oui) - (1-p) × H(w_si_non)` en bits, dans ce modèle auxiliaire. Écarter gain ≤ `1e-12` et p égal à 0 ou 1.
7. Trier par gain décroissant, couverture décroissante, IC décroissant puis identifiant HPO croissant.

Cet IG ne simule pas exactement le prochain classement `semantic_v1`. L'asymétrie entre similarité positive et pénalité fréquentielle négative peut limiter l'utilité réelle. Un lookahead recalculant le score serait une autre méthode à évaluer. La possibilité d'une réponse inconnue n'est pas probabilisée faute de données.

Une réponse `unknown` ne change pas le score et bloque ce signe pour le reste du cas. Arrêt après 12 questions enregistrées, moins de deux candidats ou aucune question informative admissible. L'appelant conserve l'historique ; Latros ne stocke pas de session patient.

## Reproductibilité et évaluation

Le manifeste fixe entrées, versions, code, transformations, comptes et hashes. Vérification des sources avant import, tri des lignes et une seule thread DuckDB stabilisent les Parquet canoniques. Un clone sans données reconstruit à partir du registre et du manifeste. Le code et le verrou des dépendances doivent être conservés pour comparer les Parquet octet par octet. Le conteneur DuckDB n'est pas binaire-déterministe sur le corpus complet : son hash est vérifié via un reçu local `integrity.json`, distinct du manifeste canonique versionné. L'identité reproductible du snapshot est celle de ses tables et de leurs hashes, pas de l'allocation interne du conteneur runtime.

Les tests synthétiques hors réseau prouvent des invariants logiciels, pas une capacité diagnostique. L'évaluation future devra utiliser des cas indépendants des assertions et mesurer rappel des candidats, rang de référence, robustesse aux signes manquants/erronés, sous-groupes, stabilité et nombre des questions. Les maladies non représentées doivent constituer un jeu d'évaluation séparé.

Avant une interface patient : revue clinique, abstention, sécurité indépendante, confidentialité et examen du cadre applicable. Ni une liste vide ni l'absence de drapeau rouge ne vaut évaluation : ici, la sécurité est toujours **non évaluée**.
