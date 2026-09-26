# Parcours simple FR/DE/EN et recherche locale

26 septembre 2026. Chantier UI indépendant de G5, après fusion de #14 dans `main`.
Il améliore la découvrabilité, **pas la connaissance médicale ni la qualité clinique**.
Snapshot, `general_v1`, `semantic_v1`, reçus et sorties scientifiques sont inchangés ;
`clinical_validation: false`, `publishable: false`, `research_unreviewed: true` et
`safety_status: not_evaluated` demeurent protégés. Aucun reviewer ou avis clinique n'est inventé.

## I18n et données d'affichage

`i18n.js` embarque les textes du parcours simple : accueil, navigation, âge, questions, états
de chargement/erreur, avertissements, résultats, détails, historique et reprise. FR/DE/EN est
conservé en localStorage. Pas d'API de traduction, CDN, télémétrie ou asset distant. Les détails
techniques et la console experte gardent les contrats sources lisibles, non réécrits.

`display-lexicon.json` (`ui-display-1`) est un lexique éditorial **d'affichage/sélection explicite**,
distinct des connaissances et des revues humaines. Neuf IDs HPO ont été vérifiés dans le DuckDB
local : rhinorrhée HP:0031417, pharyngalgie HP:0033050, douleur abdominale HP:0002027,
vertige HP:0002321, fièvre HP:0001945, toux HP:0012735, céphalée HP:0002315,
congestion nasale HP:0001742 et nausée HP:0002018. Il n'y a aucune génération massive ni
approbation clinique de ces textes. Les alias ne sont pas de nouveaux concepts/mappings.

Les désignations multilingues déjà présentes sont privilégiées dans la langue demandée ; le
snapshot possède notamment des désignations françaises Orphadata, mais pas de traduction
allemande générale. Faute de désignation ou entrée locale, label source anglais et indicateur
EN explicite. Les IDs restent identiques. La proposition « tête qui tourne / mir ist schwindelig /
dizzy » affiche **vertige, sensation de rotation** pour demander une confirmation plus précise,
pas pour assimiler silencieusement toutes les formes d'étourdissement à ce concept.

## Recherche et contrats

Le repository de présentation centralise le SQL. Sa projection temporaire reprend les concepts
actifs, relations symptom/sign/exam et priorités de type historiques ; toutes leurs désignations,
synonymes, alternate labels et codes sont recherchables. Le snapshot est ouvert read-only ;
ni assertion ni table persistante n'est écrite. Les alias ne sont activés que pour un ID source
non ambigu et un label preferred anglais attendu. Un alias absent d'un snapshot n'est pas créé.

Normalisation déterministe : casse, accents, ß/ss, ponctuation/traits d'union, pluriel final simple.
Ordre : exact preferred local, synonyme/alias exact, préfixe local, tokens locaux, fuzzy prudent,
fallback anglais. Sous-chaînes/tokens facilitent seulement les suggestions. Fuzzy limité au
lexique public explicite : une édition, longueur ≥5, un seul concept cible, sinon aucune suggestion
fuzzy. Pas d'expansion clinique via la hiérarchie. Confirmation toujours requise.

Les endpoints `/internal/v1/presentation/concepts`, `/labels` et `/question` projettent seulement
l'affichage ; limites 1–50 suggestions, 100 labels, 120 caractères de recherche. Les champs
`display_label`, `display_language`, `display_origin`, `display_lexicon_version`,
`fallback_english`, `question_text` ne remplacent jamais le label/coding scientifique. L'ancien
endpoint expert reste compatible. Les observations envoyées utilisent le label source anglais,
pas sa traduction ; le changement de langue ne sauvegarde pas le cas et ne recalcule rien.
Le question ID original et son texte/label anglais sont accessibles dans un panneau technique.

Les tables SQL temporaires sont liées au repository du snapshot, borné à deux repositories
existants. Vérification forte à l'ouverture, contrôle des attributs déjà vérifiés à chaque appel.
Pas de cache global illimité de résultats/traductions ; 100 labels au plus pour la projection
courante du navigateur. Redémarrage du serveur requis si le lexique embarqué est modifié.

## Mesures reproductibles offline

```text
uv run --offline --no-sync python scripts/benchmark_ui_presentation.py
uv run --offline --no-sync python scripts/compare_general_v1_runtime.py --output data/staging/ui-i18n-golden.json --expected tests/golden/v0.7-general-v1-sha256.json
node --test tests/frontend/checker-i18n.test.cjs
```

Sur ce Windows, networking bloqué par le script, trois répétitions chaudes par formulation :

| Recherche | FR médiane | DE médiane | EN médiane |
| --- | ---: | ---: | ---: |
| Nez qui coule / Schnupfen / runny nose | 0,218 s | 0,211 s | 0,163 s |
| Mal à la gorge / Halsschmerzen / sore throat | 0,217 s | 0,211 s | 0,164 s |
| Mal au ventre / Bauchschmerzen / stomach pain | 0,214 s | 0,213 s | 0,162 s |
| Tête qui tourne / mir ist schwindelig / dizzy | 0,214 s | 0,215 s | 0,158 s |

Première recherche d'un processus : **6,687 s**, ouverture, vérification forte et préparation
SQL incluses. Ce n'est pas une promesse de recherche instantanée à froid. Les suggestions sont
débouncées à 220 ms ; aucun préchargement de milliers de concepts dans le navigateur.

## Vérifications et limites

206 tests Python, quatre tests frontend Node, Ruff/format, mypy strict, schémas et registre
verts localement. Tests mêmes IDs FR/DE/EN, synonymes/accents/pluriels, limites, fallback,
collision fuzzy refusée, langues sources prioritaires, mêmes question IDs/runs, snapshot
read-only et réseau externe bloqué. Les sept diagnostics/questions d'or du snapshot réel
conservent leurs hashes exacts. La CI Linux/Windows exécute Python et Node 22 (tests uniquement).

Contrôle navigateur réel : sélection française, passage allemand sans perdre le concept,
seconde recherche allemande, âge fictif, question backend avec fallback EN visible, résultats,
détails et historique/reprise. Viewport mobile 390×844, palette conservée et zones tactiles ≥44 px.
Ce contrôle est un test logiciel fictif, pas une évaluation clinique ou un dossier patient.

La couverture de traduction clinique reste partielle. Les formulations grand public doivent
être surveillées/relues avant un usage patient ; aucune validation médicale n'est revendiquée.
G1/G2 humains et G3 indépendant restent nécessaires. Ajouter un terme d'affichage nécessite une
édition versionnée, contrôle de l'ID/label existant, non-collision et tests ; jamais une nouvelle
assertion médicale par traduction.
