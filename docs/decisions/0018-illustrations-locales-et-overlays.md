# 0018 — Illustrations locales indépendantes des overlays

Statut : accepté. Date : 27 septembre 2026. Issue : #18.

## Contexte

L'ADR 0016 a livré des schémas techniques pour Corps → Tête → Sinus. Le parcours reste
valide mais les silhouettes ne répondent pas à la demande d'illustrations de qualité produit.
Une image ne doit pas introduire de logique clinique ni rendre les hitboxes dépendantes de
coordonnées de pixels CSS variables. Le chantier de politiques General/Rare est séparé (#19).

## Décision

Sept PNG originaux générés forment la série `latros-atlas-1`, stockée entièrement dans le
paquet UI. Un SVG local indépendant compose l'image avec ses dimensions originales, des
groupes `data-region` focusables et des rectangles transparents. Les labels restent du HTML
localisé. `viewBox` effectue les zooms sans déformer ni modifier les fichiers PNG.

`ui-anatomy-2` contient 35 vues, leurs parents/enfants, image, canvas, viewport et hitboxes
dans le repère de l'image du parent. Les références HPO sont des raccourcis UI explicites,
potentiellement multirégions ; seuls les concepts actifs, supportés et non ambigus sont affichés.
Une sélection ne déduit ni `body_site`, ni maladie, ni relation causale. Recherche, anatomie et
question continuent à utiliser l'Observation canonique existante.

Le registre `illustrations.json` fige version, taille, SHA-256, brief et statut généré/non
validé. Le chargement vérifie les hashes avec un cache borné à huit fichiers, invalidé par
taille/mtime/ctime/hash. Aucun fetch, CDN, police externe ou build Node n'est nécessaire.
Les anciens SVG sont conservés comme traces techniques, mais ne servent plus au parcours.

## Alternatives examinées

- [Servier Medical Art](https://smart.servier.com/how-to-cite-servier-medical-art/) fournit
  des illustrations sous CC BY 4.0 : adaptation et redistribution sont permises avec
  attribution. Les [kits](https://smart.servier.com/image-kits-by-category/) ORL et
  ophtalmologie sont des distributions téléchargeables. Cette option est juridiquement
  exploitable ; elle n'est pas rejetée pour une absence de licence. Ses diagrammes pédagogiques
  et kits séparés ne constituent pas la série frontale semi-réaliste demandée ici.
- Une série originale générée est retenue pour sa cohérence visuelle. Aucune image Servier
  ou provenant d'un atlas tiers n'est copiée. Le statut « généré » n'est ni une garantie
  d'exactitude anatomique, ni une allégation de validation clinique ou d'exclusivité juridique.
- Des liens vers des images distantes ou des hitboxes absolues CSS sont écartés : runtime
  souverain et accessibilité. Un format vectoriel pour les *overlays* reste conservé.

## Conséquences

Les sept illustrations sont corps, tête, sinus, nez, oreille, œil et bouche/gorge. Oreille et
œil utilisent une coupe latérale/oblique pour rendre l'intérieur lisible ; ce n'est pas une
série strictement frontale pour ces deux vues. Les vues thorax/organes/abdomen/bassin/membres
utilisent des zooms du corps entier, pas quinze nouvelles planches d'atlas détaillées.
Les illustrations nécessitent une future relecture anatomique humaine. Leur avertissement
est visible dans les trois langues. La génération n'est pas reproductible bit à bit ; les
*fichiers livrés*, eux, sont locaux et vérifiables par leurs hashes.

Le lexique `ui-display-3` propose 80 traductions éditoriales supplémentaires explicitement
non relues humainement, sans nouveau concept clinique. L'export local versionné de revue
linguistique contient le label source, la proposition et des décisions humaines vides.
La majorité du catalogue demeure en fallback EN. Aucun jalon de validation médicale n'est
franchi ; G1/G2 humains et G3 indépendant restent obligatoires.
