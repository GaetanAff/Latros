# Mode simple anatomique et couverture FR/DE/EN

26 septembre 2026. Branche `codex/ui-anatomy-vnext`, issue de `main` après fusion de #15 et #16.
Chantier de présentation uniquement ; aucune décision G5 ou validation médicale n'est effectuée.

## Livraison

Corps → Tête → Sinus est navigable par SVG local, liens clavier et breadcrumb réversible.
Les callouts sont traduits. Les autres régions annoncent explicitement que leur vue détaillée
n'est pas disponible. La recherche demeure accessible sur tous les écrans, avec raccourci
mobile. Desktop : anatomie et panneau latéral ; mobile : recherche sticky, carte et panneau
d'observations empilés façon bottom sheet, sans tableau ni défilement horizontal intentionnel.
Ce panneau n'est pas un drawer modal ; la navigation anatomique n'implémente pas encore tout le corps.

L'arbre `assets/anatomy/navigation.json` et trois SVG dédiés sont une classification UI seulement.
`/internal/v1/presentation/anatomy` vérifie les références contre le catalogue supporté du
snapshot courant, en lecture seule. Le clic sur une région n'ajoute aucune observation.
La sélection d'un finding exige un état avant l'ajout ; recherche et anatomie convergent
vers le même ID/`Observation`, sans doublon, sans changement automatique de l'état existant.
Une observation peut être modifiée, retirée ou reliée à une région explicitement résolue.
Cette navigation ne renseigne pas implicitement la localisation clinique dans le cas.

Sinus possède cinq références UI effectivement résolues dans le corpus DEV : congestion nasale,
rhinorrhée, hyposmie, anosmie et céphalée. Elles servent à trouver des observations, **pas à
affirmer leur valeur diagnostique pour la sinusite**. « Pression dans les sinus », « oreilles
bouchées » et « Ohrdruck » n'ont pas de cible correspondante supportée identifiée dans ce catalogue ;
aucun alias vers une autre douleur ou maladie n'est inventé pour remplir la maquette.

Le frontend est réparti en `api`, `state`, `i18n`, `search`, `observations`, `anatomy`,
`questions`, `results`, `history` ; `checker.js` coordonne les écrans. La console `/expert`
est inchangée. Les résultats restent des résumés F4 avec détail lazy, jamais des pourcentages.
Les questions sont celles du backend, non celles illustrées par la maquette. Un changement
de langue ne modifie ni question ID, ni cas, ni run. Un changement d'observation quitte l'écran
de l'ancien résultat/question afin de ne pas l'associer aux nouvelles données non sauvegardées.

## Audit de couverture réel

La mesure porte uniquement sur les observations actives recherchables, pas sur tous les
106 835 concepts du snapshot. SQL et résolution d'identités existantes, aucun chargement global
en Pydantic ou traduction générative.

| Mesure | Avant (#16) | Après |
| --- | ---: | ---: |
| Concepts recherchables | 11 671 | 11 671 |
| Désignations EN natives | 11 671 | 11 671 |
| Désignations FR natives de ces observations | 0 | 0 |
| Désignations DE natives de ces observations | 0 | 0 |
| Concepts avec affichage FR local | 9 | 65 |
| Concepts avec affichage DE local | 9 | 65 |
| Alias FR activés | 16 | 72 |
| Alias DE activés | 13 | 69 |
| Alias EN activés | 17 | 73 |
| Observations sans traduction FR/DE | 11 662 | 11 606 |
| Questions potentielles avec fallback FR/DE | 11 662 | 11 606 |

Les derniers nombres sont une couverture **possible**, pas une fréquence observée des questions.
Les traductions françaises Orphadata des maladies ne traduisent pas automatiquement ces findings.
`ui-display-2` contient 70 références potentielles : cinq sont désactivées car leur identité
externe est ambiguë dans le snapshot : HP:0001676, HP:0000731, HP:0000747, HP:0001295,
HP:0002082. Aucun rapprochement clinique n'est effectué pour lever cette ambiguïté.
Les 65 concepts activés couvrent notamment nez, odorat, oreilles, yeux, douleur, peau,
respiration, digestif et urinaire ; ce n'est pas une couverture médicale exhaustive.
Les nouveaux libellés sont une rédaction UX technique à relire, pas une traduction clinique certifiée.

La recherche grand public vérifiée retrouve le même ID canonique en FR/DE/EN pour :
nez qui coule / Schnupfen / runny nose ; mal à la gorge / Halsschmerzen / sore throat ;
mal au ventre / Bauchschmerzen / stomach pain ; tête qui tourne / mir ist schwindelig / dizzy ;
mal de tête / Kopfschmerzen / headache ; nez bouché / verstopfte Nase / blocked nose.
Le libellé de vertige précise la **sensation de rotation**, pour confirmation utilisateur,
sans interpréter automatiquement toute sensation d'étourdissement.

Deux différences de code primaire historiques sont exposées par l'audit : HP:0002315
résout le concept Headache dont le catalogue retourne HP:0000266 ; HP:0001249 résout
Intellectual disability dont le catalogue retourne HP:0000730. Cette tranche ne change
pas ces choix historiques. Tests et navigation comparent l'ID canonique et conservent
le coding du catalogue, identique entre anatomie et recherche. Aucun code n'est réécrit.

## Performance, protocole et limites

Windows, dépendances verrouillées, même snapshot local, script bloquant les connexions réseau.
Un processus neuf pour la recherche froide ; trois répétitions par formulation pour les
médianes chaudes. Mesure de service, pas de temps total navigateur ; debounce UI 220 ms en sus.

| Mesure | Avant | Après |
| --- | ---: | ---: |
| Première recherche avec ouverture/intégrité/préparation | 6,830 s | 6,776 s |
| Médianes chaudes, douze formulations initiales | 0,172–0,231 s | 0,183–0,250 s |
| Médianes chaudes, céphalée/congestion ajoutées | non mesurées dans ce protocole | 0,181–0,237 s |

Un autre passage après a donné 6,626 s ; la variation ne démontre pas un gain froid significatif.
Les activations du lexique se résolvent maintenant dans une requête groupée, pas deux scans
par entrée. Aucun warm-up bloquant, cache global illimité ou nouveau format de snapshot.
La résolution des labels d'historique est différée à l'ouverture de l'historique, pas au landing.
La vérification forte et la projection SQL restent le coût froid principal ; aucun contrôle
d'intégrité n'est réduit. La carte Corps/Tête n'initialise pas le repository, ses références
étant vides. Le premier écran Sinus ou la première recherche peut donc encore attendre ~7 s.
Le passage `--phase-breakdown` mesure 2,657 s pour compatibilité/ouverture/intégrité,
3,781 s pour la préparation SQL de présentation et 0,230 s pour requête/labels (6,669 s
total). Cette mesure séparée ne remplace pas la comparaison directe avant/après.
Le cache d'affichage navigateur est limité à 100 labels ; les régions résolues sont liées
au snapshot actif, bornées par les 64 nœuds/100 références maximum de la configuration.

```text
uv run --offline --no-sync python scripts/audit_ui_presentation.py
uv run --offline --no-sync python scripts/benchmark_ui_presentation.py
uv run --offline --no-sync python scripts/benchmark_ui_presentation.py --phase-breakdown
uv run --offline --no-sync python scripts/compare_general_v1_runtime.py --output data/staging/ui-anatomy-after-golden.json --expected tests/golden/v0.7-general-v1-sha256.json
node --test tests/frontend/checker-i18n.test.cjs
```

## Vérifications scientifiques et UI

Les sept diagnostics/questions réels conservent leurs empreintes complètes d'or avant/après.
Les fichiers de moteur, de build historique, de profil et de manifeste ne sont pas modifiés.
Hash canonique conservé : `bfda708aba44dcc5d12896ac7523d9d6bb577dea53bdc3810e499c15f64b1fb0`.
`clinical_validation: false`, `publishable: false`, `research_unreviewed: true` et
`safety_status: not_evaluated` sont inchangés ; aucune décision clinique humaine inventée.

221 tests Python et 13 tests frontend Node verts localement, Ruff/format, mypy strict,
schémas et registre verts. Tests : navigation/breadcrumb/retour, mêmes IDs FR/DE/EN, corpus incomplet et
ambiguïté refusés, absence de duplication, états présent/absent/inconnu, langues persistantes,
questions/runs inchangés, reprise sans réécriture, édition d'un cas après résultat,
préservation du contexte sujet et de l'unité d'âge d'une session reprise tant que non édités,
thème local persistant, snapshots read-only et réseau externe bloqué. Les schémas et le registre
restent inchangés. Le contrôle navigateur utilise exclusivement des informations fictives :
aucun patient réel et aucune validation clinique. La CI Windows/Linux couvre Python et Node.

Limites principales : traduction FR/DE de la majorité du catalogue absente, anatomie détaillée
limitée à Tête/Sinus, dessins schématiques plutôt qu'atlas, recherche froide ~7 s, relecture UX
multilingue souhaitable. Le ranking médical et le biais rare/génétique de la base sont inchangés.
G1/G2 humains et G3 indépendant demeurent nécessaires. `FUTUR INTERFACE/` n'est ni utilisé,
inspecté, copié, ni modifié.
