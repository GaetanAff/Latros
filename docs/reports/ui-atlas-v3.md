# Anatomie illustrée locale v3 et couverture linguistique

27 septembre 2026 — branche indépendante `codex/anatomy-atlas-local-v3`, base
`31ae93262a1a1e601d61eaa8af66f2e10f339139` après fusion de #17. Issue #18.
Le parcours généraliste/rare et ses profils expérimentaux sont dans la PR séparée #19.
Ce rapport ne revendique aucune validation clinique ou anatomique.

## Navigation et fichiers

35 vues implémentées : corps ; tête ; sinus, yeux, oreilles (externe/moyenne/interne), nez,
bouche, gorge, mâchoire ; cou ; thorax (poumons, cœur, paroi) ; abdomen (épigastre,
intestins, foie/navigation) ; bassin/urinaire ; bras (épaule, coude, poignet), mains ; jambes
(hanche, cuisse, genou, jambe inférieure, cheville), pieds. Pas de région génitale inventée.

Les sept images `*-atlas-v1.png` pèsent ensemble 17 151 071 octets. Le registre versionné
`src/latros/ui/assets/anatomy/illustrations.json` porte les tailles, hashes, dimensions,
statuts et briefs de chaque fichier. Ce registre n'est pas un manifeste de snapshot médical.
Corps/tête/sinus/nez/bouche-gorge : 1024 × 1536 ; oreille/œil : 1280 × 1280.

Images semi-réalistes originales générées avec l'outil de génération intégré, sans texte,
labels ou watermark, palette naturelle et fond transparent. Tête sert de référence stylistique
aux vues suivantes. Les briefs sont des spécifications documentées, pas une promesse de
reproduction pixel à pixel ou un enregistrement exhaustif des paramètres internes du générateur.
Les originaux sont conservés ; aucune édition Python des images. Les overlays teal/sauge,
labels, hover, sélection et focus sont indépendants. Un zoom est un viewport, pas une déformation.
Voir l'[ADR 0018](../decisions/0018-illustrations-locales-et-overlays.md) pour l'audit
de l'alternative Servier CC BY 4.0 et les limites de la série générée.

Les régions sont des catégories de découvrabilité, jamais des associations diagnostiques.
Une douleur générique affichée dans une région reste générique ; aucun qualificatif de site
corporel n'est déduit. Un finding peut être présent dans plusieurs vues. Les identités ambiguës
ou inexistantes sont masquées et ne sont jamais remappées arbitrairement.

## Audit linguistique réel

Mesure par `scripts/audit_ui_presentation.py`, snapshot existant ouvert read-only.

| Mesure | #17 | Cette tranche |
| --- | ---: | ---: |
| Observations recherchables / labels EN natifs | 11 671 | 11 671 |
| Concepts avec affichage FR | 65 | 139 |
| Concepts avec affichage DE | 65 | 139 |
| Désignations natives FR / DE dans ce catalogue | 0 / 0 | 0 / 0 |
| Alias FR / DE actifs | 72 / 69 | 146 / 143 |
| Concepts sans traduction FR/DE | 11 606 | 11 532 |
| Questions localisées potentielles FR/DE | 65 | 139 |
| Références éditoriales désactivées pour ambiguïté | 5 | 11 |

Le lexique contient 150 propositions ; 139 seulement s'activent après résolution unique et
égalité du label source local. Les nouvelles références ambiguës désactivées sont
HP:0001542, HP:0001656, HP:0002357, HP:0000959, HP:0002255, HP:0001393, en plus des cinq
historiques. Aucune préférence arbitraire, aucun mapping médical nouveau.
Les codes historiques céphalée/ID gardent leurs IDs canoniques résolus, sans correction du snapshot.

Les 80 ajouts ont `editorial_draft_requires_human_language_review`, provenance UI et reviewer nul.
Ils ne constituent pas 80 décisions linguistiques ou médicales humaines. Formulations libres
sélectionnées explicitement : nez qui coule/Schnupfen/runny nose, mal à la gorge/Halsschmerzen/
sore throat, mal au ventre/Bauchschmerzen/stomach pain, tête qui tourne/mir ist schwindelig/dizzy,
mal de tête/Kopfschmerzen/headache, nez bouché/verstopfte Nase/blocked nose. Nouveaux exemples :
respiration sifflante/pfeifende Atmung/wheezing, mal au coude/Ellenbogenschmerzen/elbow pain.
« Tête qui tourne » demande confirmation du finding affiché (vertige), sans interprétation NLP.
Une pression auriculaire ou sinusienne sans concept exact supporté n'est pas forcée vers une douleur.

Questions naturelles ajoutées pour le discriminant Wheezing : « Votre respiration est-elle
sifflante ? » / « Pfeift es beim Atmen? ». Les autres termes peuvent garder une formulation
explicite « Présentez-vous ce signe… » plutôt qu'une paraphrase sémantique non vérifiée.
IDs, source anglaise et `question_id` restent intacts. Labels de maladies non traduits restent EN.

## Pipeline de revue linguistique

```text
uv run --offline --no-sync python scripts/export_ui_translation_review.py --output-dir data/staging/ui-atlas-translation-review
```

Export déterministe de **11 671 lignes**, avec label source, ID canonique, draft local éventuel,
provenance/statut et décisions FR/DE/reviewer/commentaire nuls. Deux rejeux produisent le même
SHA-256 `a3792edfffcf18d768a9cd8aba64d2e0e181224ee37ff0c1b105ba95034e29ef`.
Il refuse d'écraser un export différent ; il n'importe aucune décision, ne génère pas de
traductions massives et ne modifie pas le snapshot. Une vraie revue linguistique peut désormais
compléter ce jeu ; le passage au lexique versionné reste une modification explicite séparée.

## Performance et protocole

Commandes reproductibles sans réseau externe :

```text
uv run --offline --no-sync python scripts/benchmark_ui_presentation.py --phase-breakdown
uv run --offline --no-sync python scripts/audit_ui_presentation.py
uv run --offline --no-sync python scripts/compare_general_v1_runtime.py --output data/staging/atlas-golden.json --expected tests/golden/v0.7-general-v1-sha256.json
```

| Recherche | #17 historique | Lexique 150 initial | Après petits ajustements |
| --- | ---: | ---: | ---: |
| Froid ouverture/intégrité/préparation/requête | 6,776 s | 8,276 s | 7,810 s |
| Ouverture/intégrité | 2,657 s (passage séparé) | 2,590 s | 2,590 s |
| Préparation SQL présentation | 3,781 s (passage séparé) | 5,467 s | 5,009 s |
| Requête/labels | 0,230 s (passage séparé) | 0,219 s | 0,212 s |
| Médianes chaudes, 18 formulations | 0,181–0,250 s | 0,168–0,355 s | 0,162–0,215 s |

Les chiffres #17 sont historiques, pas un A/B contrôlé même jour. La nouvelle préparation
reste plus lente ; **aucun gain froid global n'est revendiqué**. L'insertion groupée remplace
les centaines de transactions d'alias ; la résolution privée bornée du lexique se fait en
une seule requête, avec limite publique de navigation toujours à 100. Pas de nouveau format
de runtime, ni warm-up qui bloque le démarrage, ni réduction du contrôle d'intégrité. Corps et
Tête ne préchargent pas DuckDB. L'image courante seule est chargée, pas les sept PNG au démarrage.

## Vérifications et limites

225 tests Python et 14 frontend verts localement, Ruff/format/mypy strict, schémas et registre ; CI
Linux/Windows exécutée après push. Les sept diagnostics/questions d'or complets réels sont
identiques à la référence relue pour #17. Aucun fichier de reasoning, profil, build historique,
manifest, golden ou schéma scientifique modifié par cette branche.

Contrôle navigateur sur cas fictif : Corps → Tête → Sinus au clavier, ajout absent explicite,
anatomie puis recherche sans doublon, langue changée en session, recherche allemande Wheezing,
Oreille interne, mobile 390 × 844, dark mode, absence de scroll horizontal. Stockage de test
isolé pour ne pas demander à cette branche basée sur main de lire les sessions du futur
contrat General/Rare de #19. Une copie temporaire du merge-tree propre des deux PR passe
**233 tests Python et 16 frontend** sans mélanger les branches. La CI a détecté un import de
script dépendant de `python -m pytest` ; le test charge désormais le fichier explicitement,
et la commande exacte `pytest` est relancée. Aucun test n'est supprimé pour contourner l'échec.

Hash canonique inchangé :
`bfda708aba44dcc5d12896ac7523d9d6bb577dea53bdc3810e499c15f64b1fb0`.
`clinical_validation: false`, `publishable: false`, `research_unreviewed: true`,
`safety_status: not_evaluated`. Aucune décision clinique humaine inventée.

Principales limites : 11 532 concepts sans FR/DE ; illustrations anatomiquement non relues ;
organes hors tête seulement zoomés du corps ; recherche froide encore ~8 s ; G1/G2 humains
et G3 indépendant nécessaires. La navigation n'est pas un atlas ni une validation de ranking.
`FUTUR INTERFACE/` reste entièrement ignoré, non inspecté et non modifié.

## Intégration et lancement normal — 27 septembre 2026

Après fusion de #19, #20 est remise à jour sur main. Les 11 sessions habituelles sont
lisibles sans changement de leurs hashes : l'ancienne branche atlas seule refusait le champ
`consultation` d'une session General/Rare et faisait échouer la liste entière avec HTTP 422.
Les sessions isolées des premiers essais visuels n'avaient pas couvert ce cas d'intégration.

Le navigateur Brave conservait aussi d'anciens JS/CSS : l'API fournissait la nouvelle navigation,
mais l'overlay vide restait sans illustration. Les deux pages HTML sont désormais non cachées
et tous leurs JS/CSS portent le SHA-256 de leur contenu dans l'URL. Aucune purge de données
navigateur ni modification de session. Le rechargement normal affiche l'image locale.

235 tests Python et 16 frontend verts, tous les contrôles qualité verts et les sept goldens
réels historiques identiques. Diagnostic/question généralistes réels testés sans réseau,
`research_unreviewed: true` et safety `not_evaluated`. Le snapshot reste immuable et non validé.
