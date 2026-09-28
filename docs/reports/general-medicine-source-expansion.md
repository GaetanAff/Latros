# Audit d'extension des connaissances de médecine générale

Date de consultation des sources officielles : **27–28 septembre 2026**.
Statut : audit documentaire préparatoire, **aucune acquisition ni ingestion médicale**.
Les recommandations ci-dessous concernent la faisabilité technique et les droits affichés,
pas une validation juridique définitive, une efficacité diagnostique ou une autorisation clinique.

## Conclusion opérationnelle

Il n'existe pas, parmi les distributions vérifiées ici, de remplacement prêt à l'emploi d'une
base propriétaire de symptom checker. Le nombre de relations ou la disponibilité d'un PDF ne
garantissent ni droits de transformation/redistribution, ni utilité différentielle, ni indépendance.
La voie la plus défendable est une **curation ciblée de documents admissibles**, avec mappings,
qualificateurs, provenance primaire et vraie revue humaine, plutôt qu'une nouvelle extraction
massive de simples mentions de symptômes.

Priorités proposées, sans ingestion autorisée par ce rapport :

1. Terminer la revue G1/G2/G5 des données MedlinePlus déjà acquises et mesurer les trous par
   domaine avant de choisir des documents supplémentaires.
2. Auditer un petit lot d'articles de synthèse/diagnostic **PMC CC BY ou CC0**, puis des titres
   **Bookshelf OA** et rapports **AHRQ** dont les droits sont effectivement fermés document par
   document. Extraire des candidates, jamais des assertions automatiquement approuvées.
3. Étudier **Wikidata CC0 pour découvrabilité/mappings**, et ses relations référencées comme
   pistes de curation. Ce n'est pas un corpus clinique validé et une référence n'est pas un
   transfert des droits du texte référencé.
4. Différer NHS/CDC comme fondations généralistes faute de distribution adaptée identifiée ;
   demander des permissions explicites pour NICE, MSF, HAS coédité et AWMF avant transformation.
5. Garder WHO SMART dans un audit séparé de règles/protocoles, compatible avec la roadmap,
   sans transformer des workflows thérapeutiques en matrice de diagnostic.

## Point de départ réel dans Latros

Le [rapport General/Rare](general-first-rare-second.md) mesure **142 maladies, 684 assertions
canoniques, 706 assertions sources et 210 findings** pour `general_question_v2`. Ce profil
mono-source MedlinePlus utilise seulement les candidates G4 `retained` techniquement résolues
et exclut des marqueurs rares/génétiques explicites. Il n'atteste pas que ces maladies sont
fréquentes. Une seule famille éditoriale reste une seule source, pas 706 confirmations indépendantes.

Le [G0](v0.7-general-quality-audit.md) identifie la forte orientation structurelle rare/génétique
du corpus global ; [G4](v0.7-g4-medlineplus-extraction-quality.md) conserve 2 212 candidates,
en place 4 056 en revue et en rejette 1 468 pour l'extraction automatique ;
[G5](v0.7-g5-human-adjudication.md) organise les décisions, mais n'en invente aucune.
Les exemples de rangs surprenants et les questions générales comme Pain/Fatigue sont des limites
déjà mesurées, pas un problème que davantage de labels UI corrigerait.

Référence inchangée : `v0.7.0-general-dev-unreviewed`, SHA-256 de contenu
`bfda708aba44dcc5d12896ac7523d9d6bb577dea53bdc3810e499c15f64b1fb0`.
`general_v1`, `semantic_v1`, goldens, mappings et assertions historiques ne sont pas modifiés.
`clinical_validation: false`, `publishable: false`, `research_unreviewed: true` et
`safety_status: not_evaluated` restent inchangés. Aucun reviewer ni statut `approved` n'est ajouté.

## Critères de décision

- **GO technique limité** : une distribution locale officielle et des droits appropriés peuvent
  permettre un prototype de staging du sous-ensemble nommé, après inscription au registre et
  autorisation distincte de l'acquisition. Cela ne permet pas le scoring clinique ou la publication.
- **NO-GO actuel** : pas de preuve suffisante de droit, de distribution souveraine ou de pertinence
  pour le rôle souhaité. Ce verdict n'affirme pas qu'une permission future serait impossible.
- Une source **NC**, **ND**, à territorialité limitée ou avec droits tiers non fermés n'est pas
  assimilée à une distribution librement transformable/redistribuable du futur produit Latros.
- Un service cloud peut héberger le **fichier acquis explicitement** ; il ne doit pas devenir une
  dépendance du build/runtime. Aucun connecteur cloud, client d'API médical ou crawler n'est proposé.
- Les documents consultés par le navigateur sont des preuves documentaires ; aucun dump clinique
  n'a été téléchargé sous `data/raw/`, aucune release/source réelle ni hash fictif n'a été créé.

## Matrice des distributions et droits

Les liens d'une ligne documentent sa distribution et/ou ses conditions. Les détails et restrictions
correspondants sont exposés ensuite. « Langues » indique l'offre observée, pas un compte exhaustif.

| Source / producteur | Rôle possible | Local/bulk officiellement documenté | Langues utiles | Décision technique actuelle |
| --- | --- | --- | --- | --- |
| MedlinePlus Health Topics / NLM — déjà acquis | `clinical_assertion_source` | [XML/ZIP datés complets](https://medlineplus.gov/xml.html) | EN, ES ; pas FR/DE complets | GO limité aux summaries autorisés et jeu de curation ; pas aux liens tiers |
| Wikidata / communauté Wikimedia | `aggregated_knowledge`, terminologie d'affichage séparée | [JSON/RDF hebdomadaires](https://www.wikidata.org/wiki/Wikidata:Database_download), CC0 structuré | Labels/alias multilingues, dont FR/DE/EN, disponibilité par item | GO staging/mappings/UX ; NO-GO vérité clinique automatique |
| Wikipedia / communautés Wikimedia | `clinical_assertion_source` candidate, non autorité clinique | [exports XML compressés](https://wikitech.wikimedia.org/wiki/MediaWiki_Content_File_Exports), [CC BY-SA 4.0 et exceptions](https://foundation.wikimedia.org/wiki/Terms_of_Use) | Éditions FR/DE/EN | NO-GO ingestion clinique directe ; GO de faisabilité seulement si obligations SA/attribution fermées |
| PMC Article Datasets / NLM + auteurs/éditeurs | `clinical_assertion_source` candidate | [inventaire + fichiers HTTPS/S3 officiels](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/), licence par article | Principalement EN, variable par document | GO limité à une allowlist CC BY/CC0 vérifiée, hors droits tiers |
| Bookshelf OA / NLM + éditeurs | `clinical_assertion_source` candidate | [NLM LitArch FTP OA](https://www.ncbi.nlm.nih.gov/books/about/ftp/?report=reader), fichiers sources par titre | Principalement EN, variable par titre | GO limité aux titres à droits fermés ; NO-GO « tout Bookshelf » |
| AHRQ / agence américaine + contractants | `clinical_assertion_source` candidate | [rapports électroniques](https://www.ahrq.gov/research/publications/index.html), PDF ; pas de KG généraliste identifié | EN, ressources ES distinctes | GO conditionnel pour rapports individuellement admissibles, pas pour tous les articles financés |
| WHO SMART / OMS et dépendances | `safety_rule_source` ou protocole futur | [packages de release SMART Base 1.0.0](https://smart.who.int/base/1.0.0/downloads.html), TGZ/JSON/XML/CSV | EN ; langues selon package | GO audit package par package ; NO-GO permission uniforme ou différentiel généraliste automatique |
| NHS Health A–Z / DHSC, NHS | `clinical_assertion_source` candidate | [syndication principalement API](https://digital.nhs.uk/developer/api-catalogue/nhs-website-content) ; aucun dump généraliste daté identifié ici | EN ; traductions tierces non présumées couvertes | NO-GO fondation souveraine actuelle malgré OGL partielle |
| NICE / NICE et coéditeurs | Recommandations / candidates cliniques | PDF, [syndication et licence](https://www.nice.org.uk/reusing-our-content/nice-uk-open-content-licence) ; pas de package adapté et libre démontré | EN, traductions à permissions propres | NO-GO France/produit généraliste sans autorisation applicable |
| HAS / HAS et coéditeurs | Recommandations / candidates cliniques | [PDF officiels et mentions légales](https://www.has-sante.fr/jcms/c_518191/fr/mentions-legales) ; captures possibles, pas de dump généraliste identifié | FR | NO-GO global ; audit/permission document par document requis |
| MSF Medical Guidelines / MSF | Manuel clinique / candidates | [manuel PDF officiel](https://medicalguidelines.msf.org/sites/default/files/2025-07/guideline-170-en.pdf) | EN ; éditions/traductions à vérifier séparément | NO-GO transformation/redistribution sans permission préalable |
| AWMF / groupes de sociétés savantes | Guidelines / candidates cliniques | [registre et PDFs](https://www.awmf.org/leitlinien), [droits par groupe auteur](https://www.awmf.org/regelwerk/urheberinnen-und-verwertungsrechte-von-leitlinien) | DE principalement | NO-GO général ; permission du détenteur applicable requise |
| OpenStax A&P 2e / Rice University et contributeurs | Anatomie pédagogique, pas base différentielle | [PDF officiel ; licence actuelle NC-SA](https://openstax.org/books/anatomy-and-physiology-2e/pages/preface) | EN pour le titre audité | NO-GO cœur redistribuable sans restriction commerciale ; faible valeur diagnostique |
| SemMedDB / NLM LHNCBC | `aggregated_knowledge` extraite automatiquement | [release finale VER43 2024, CSV/MySQL, compte UTS](https://lhncbc.nlm.nih.gov/temp/SemRep_SemMedDB_SKR/SemMedDB_download.html) | Prédicats/concepts et phrases EN principalement | NO-GO ouvert par défaut : droits UMLS à fermer, extraction non validée, maintenance arrêtée |
| CDC / programmes CDC — piste déjà différée | Statistiques ciblées ou futures candidates | Datasets ciblés, pas de dump généraliste identifié par [audit v0.7](../source-audits/v0.7-sovereign-general.md) | Variable | NOT SUITABLE FOR SOVEREIGN INGESTION pour le cœur généraliste actuel |

## Observations documentaires déterminantes

### MedlinePlus : améliorer l'existant avant multiplier les amonts

NLM distingue summaries Health Topics réutilisables et contenus tiers protégés, dont l'encyclopédie
et des images. Un lien du XML n'autorise pas l'import de sa cible. Les XML anglais/espagnols
contiennent résumé, MeSH, groupes et sites liés ; seules les dernières captures sont exposées.
Conserver la capture déjà épinglée, ne pas la remplacer silencieusement par la production courante.
La valeur immédiate est la revue de rôle clinique/mappings et une curation explicite de temporalité
ou de facteurs réellement présents ; l'absence de mention n'est jamais un négatif.
[Règles NLM](https://medlineplus.gov/about/using/usingcontent/),
[distribution](https://medlineplus.gov/xml.html), [structure XML](https://medlineplus.gov/xmldescription.html).

### Wikidata et Wikipedia : complément ouvert, pas autorité clinique

Wikidata recommande JSON/RDF et publie son contenu structuré sous CC0. Sa propriété
`P780` décrit des symptômes/signes possibles, sans fréquence ou négatif automatiquement exploitable.
Préserver références, qualifiers, rang et IDs de statements ; dédupliquer l'amont d'une relation
republiée. Un label multilingue peut être une **candidate UX**, pas une validation de traduction
ou un mapping médical exact. [Dump/licence](https://www.wikidata.org/wiki/Wikidata:Database_download),
[P780](https://www.wikidata.org/wiki/Property:P780).

Wikipedia dispose d'exports par wiki et d'une transition vers les nouveaux Content File Exports.
Ils ne sont pas un dump clinique spécifique. La licence textuelle, les attributions, exceptions et
obligations de partage des adaptations doivent être conservées ; les médias ont leurs propres droits.
Pinner wiki/date/fichiers/SHA-256 et IDs de révision, jamais interroger Wikipedia ou SPARQL au runtime.
Pas de présomption que les éditions FR/DE/EN sont équivalentes, indépendantes ou médicalement relues.
[Exports officiels](https://wikitech.wikimedia.org/wiki/MediaWiki_Content_File_Exports),
[conditions de réutilisation](https://foundation.wikimedia.org/wiki/Terms_of_Use).

### PMC : ne pas concevoir un importeur autour d'un ancien FTP disparu

La documentation NLM actualisée indique que les anciens packages bulk FTP/cloud ont été retirés
la semaine du 24 août 2026. Il n'existe plus de baseline XML/TXT multimillion d'articles.
Les fichiers individuels officiels restent accessibles par HTTPS/S3 sans compte, avec inventaire.
**Le numéro de version d'article n'immobilise pas ses octets** : les fichiers peuvent changer sous
le même préfixe. Il faut une capture locale inventaire + métadonnées + fichiers + SHA-256, pas le seul PMCID.
[Distribution et versioning NLM](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/).

Les droits varient par article, même dans OA ; le dépôt global ne vaut pas licence globale.
Une allowlist initiale CC0/CC BY réduit les cas NC/ND/SA, sans dispenser d'inspecter les éléments
tiers. Retenir de petites revues diagnostiques et études pertinentes, pas toutes les publications,
préprints ou observations de cas. Article, population, méthode et références primaires demeurent
inspectables, avec groupement des republications. [OA et moyens autorisés](https://pmc.ncbi.nlm.nih.gov/tools/openftlist/),
[copyright et tiers](https://pmc.ncbi.nlm.nih.gov/about/copyright/).

### Bookshelf et AHRQ : droits à l'échelle du document

Bookshelf fournit un sous-ensemble OA et un service NLM LitArch pour ses fichiers sources.
Le site lisible gratuitement n'est pas intégralement admissible au téléchargement automatique ;
le guide réserve celui-ci au service prévu. Des titres peuvent avoir des licences restrictives.
Vérifier chaque livre/chapter/figure, son éditeur, l'édition et la licence avant une sélection.
Les contrôles directs HTML ont rencontré une page de contrôle navigateur ; la disponibilité réelle
des artefacts et leurs droits restent donc à tester lors d'une future acquisition autorisée.
[Service OA](https://www.ncbi.nlm.nih.gov/books/about/ftp/?report=reader),
[guide officiel téléchargeable](https://www.ncbi.nlm.nih.gov/sites/books/about/pdf/Bookshelf_NBK554843.pdf).

AHRQ publie des rapports électroniques et explique dans ses consignes les notices de domaine public,
les productions contractuelles et les cas de contenus protégés. Cela ne rend pas libres tous les
articles de grantees ni les tableaux tiers. Une présélection de rapports de diagnostic à notice
compatible est envisageable ; il ne s'agit pas d'un export de relations maladie-symptôme.
Une URL PDF peut être capturée/hashée, mais son identité éditoriale et les droits doivent être
enregistrés avant ingestion. [Publications](https://www.ahrq.gov/research/publications/index.html),
[consignes de publication/copyright](https://www.ahrq.gov/sites/default/files/publications/files/pcguide1.pdf).

### WHO SMART : distinguer plateforme, contenu et dépendances

SMART Base `1.0.0` dispose de packages de release et affiche CC BY 3.0 IGO sur sa page licence,
mais son inventaire IP inclut des ressources NC-SA ; le Starter Kit `2.0.0` annonce pour sa part
CC BY-NC-SA 3.0 IGO pour le contenu et BSD-3-Clause pour certains codes. Il serait incorrect
d'appliquer la licence du code à toutes les recommandations ou celle de Base à tout WHO SMART.
Audit transitif package/resource/dependency obligatoire. Base est un socle de conformité, pas une
liste exhaustive de maladies courantes ; un DAK spécialisé doit prouver ses droits et son périmètre.
[Downloads Base](https://smart.who.int/base/1.0.0/downloads.html),
[licence Base](https://smart.who.int/base/1.0.0/license.html),
[IP/dépendances Base](https://smart.who.int/base/1.0.0/index.html),
[licences Starter Kit](https://smart.who.int/ig-starter-kit/v2.0.0/license.html).

### NHS, NICE, HAS, MSF et AWMF : accès public n'est pas autorisation globale

NHS annonce OGL pour certains contenus, avec exclusions et conditions spécifiques pour adaptations,
copies datées et rafraîchissement. La syndication consultée est API ; aucun dump Health A–Z
officiel figé adapté n'a été trouvé. Ne pas réintroduire un runtime NHS, ni un crawl général.
Les anciennes captures ORL ne deviennent pas une nouvelle fondation.
[Conditions/exclusions NHS](https://www.nhs.uk/our-policies/terms-and-conditions/),
[syndication officielle](https://digital.nhs.uk/developer/api-catalogue/nhs-website-content),
[conditions de syndication](https://developer.api.nhs.uk/documents/NHS.UK%20Syndication%20Terms%2030-11-22.pdf).

NICE limite sa licence ouverte au Royaume-Uni, exclut CKS/BNF et certains droits tiers, et interdit
l'adaptation de recommandations/algorithmes désignés. Les usages IA demandent aussi une permission
distincte. Cela ne permet pas de supposer une licence France pour Latros, même sans LLM actuel.
[Licence NICE et conditions](https://www.nice.org.uk/reusing-our-content/nice-uk-open-content-licence).

HAS autorise certaines informations publiques sous conditions mais exclut les droits tiers ;
la coélaboration d'une recommandation exige son propre contrôle. Les PDFs sont des artefacts
acquérables, pas une preuve de redistribution de dérivés. Le NO-GO historique ORL n'est pas levé.
[Mentions HAS](https://www.has-sante.fr/jcms/c_518191/fr/mentions-legales),
[audit précédent](../source-audits/v0.5-orl.md).

Le PDF MSF consulté exige une permission préalable pour reproduction, traduction et adaptation.
Son intérêt clinique potentiel ne contourne pas cette condition.
[Manuel officiel MSF, notice de copyright](https://medicalguidelines.msf.org/sites/default/files/2025-07/guideline-170-en.pdf).
AWMF précise que les droits appartiennent aux groupes auteurs et que de nouveaux usages demandent
leur consentement ; la mise en ligne d'un PDF ne transmet pas ces droits à Latros.
[Politique AWMF](https://www.awmf.org/regelwerk/urheberinnen-und-verwertungsrechte-von-leitlinien).

### OpenStax et SemMedDB : deux raccourcis à éviter

La préface actuelle d'Anatomy and Physiology 2e annonce **CC BY-NC-SA 4.0**, et des demandes de
permission pour les usages commerciaux/IA. Ne pas recycler une mention ancienne CC BY provenant
d'un miroir. L'anatomie pédagogique peut aider une documentation autorisée, mais ne fournit pas
un différentiel généraliste prêt à scorer. [Préface/licence](https://openstax.org/books/anatomy-and-physiology-2e/pages/preface).

SemMedDB propose la release finale VER43, données jusqu'au 8 mai 2024, CSV/MySQL avec compte UTS,
et annonce l'arrêt de maintenance des outils fin 2024. Les CUIs et droits de sources UMLS ne sont
pas une licence ouverte uniforme. Les prédications sont extraites automatiquement de littérature,
pas des assertions cliniquement validées : négation, rôle, population et doublons exigent contrôle.
Pas d'acquisition ni de contournement du compte/licence.
[Distribution finale officielle](https://lhncbc.nlm.nih.gov/temp/SemRep_SemMedDB_SKR/SemMedDB_download.html),
[licence UMLS](https://www.nlm.nih.gov/research/umls/knowledge_sources/metathesaurus/release/license_agreement.html).

## Plan de sélection par domaine — travail futur

Ces priorités ne prétendent pas mesurer la couverture des nouvelles sources : aucun corpus n'a été
acquis ou parcouru intégralement pour les quantifier. Elles définissent les **questions d'audit**.

| Domaine prioritaire | Contenu à rechercher dans documents admissibles | Risque de mauvaise transformation à tester |
| --- | --- | --- |
| ORL / respiratoire | Chronologie, manifestations positives, distinction localisé/diffus, diagnostics concurrents | Complication ou comparaison prise pour symptôme ; générique Pain |
| Digestif / urinaire | Localisation, durée, symptômes associés, population et signes/examens réellement documentés | Symptôme d'un autre organe ; mot d'un test ou traitement pris comme signe |
| Musculosquelettique / rhumatologie | Site, latéralité, temporalité, mécanisme explicitement qualifié | Navigation anatomique prise pour localisation clinique ; facteur pris pour diagnostic |
| Dermatologie / neuro courante | Description/localisation, chronologie, contexte et exclusions explicites | Motif lexical HPO sans rôle manifestation ; rare dominé par général |
| Cardiovasculaire / endocrino / infectieux | Manifestations, population, mesures conservées, facteurs et négatifs publiés | Association de risque transformée en manifestation ; fréquence lexicale prise pour prévalence |

Séparer systématiquement `has_symptom`, `has_sign`, `risk_factor`, `associated_lab`, contexte,
onset/durée, fréquence et polarité. Une absence documentaire ne donne jamais `excluded`.
Une mesure conserve valeur, unité et timestamp ; une recommandation de test ne prouve pas
que le résultat de ce test caractérise chaque patient de la maladie.

## Gate avant tout futur GO d'acquisition/ingestion

1. Désigner le document/release exact et son rôle ; pour chaque élément, consigner éditeur,
   auteurs, licence/notice applicable, attribution, droit d'adaptation, redistribution, traduction,
   restrictions et dépendances tierces. Conserver le texte de la permission lorsque nécessaire.
2. Résoudre une URL officielle de fichier/version/commit ; créer une identité de capture si l'amont
   peut modifier les mêmes URLs. Le hash ne remplace pas l'édition, la licence ou la provenance.
3. Télécharger seulement après autorisation distincte ; stocker l'artefact, sa metadata et SHA-256
   localement. Pinner toute dépendance nécessaire, sans appeler l'API d'amont pendant le build.
4. Parser vers records fidèles, puis candidates auditées ; mappings ambigus/broader/narrower/related
   non scorants. Garder source locator, transformation, extraction et statut `unreviewed`.
5. Examiner avec humains qualifiés rôle clinique, négation, population, temporalité, dépendances et
   double comptage. Une deuxième plateforme hébergeant le même document reste le même amont.
6. Constituer G3 indépendamment de la connaissance ; distinguer test logiciel, évaluation
   expérimentale et vraie validation. Une fixture synthétique générée depuis les assertions n'est
   pas une validation indépendante.
7. Toute intégration de nouvelles connaissances reçoit un **nouvel identifiant de snapshot** et
   manifeste ; ne jamais réécrire la référence actuelle ou convertir automatiquement les décisions
   de staging en `approved`.

## Limites et vérifications de cette tranche

- Sources primaires officielles seulement ; consultation documentaire web, liens de droits et
  distributions enregistrés dans ce rapport. Certains accès Bookshelf et AHRQ ont été limités par
  le navigateur ; aucune disponibilité non testée n'est maquillée en acquisition réussie.
- Aucun fichier médical brut, donnée patient, artefact d'amont, modèle ou secret ajouté au dépôt.
- Aucun nombre inventé de maladies, assertions ou langues pour les nouvelles sources.
- Aucun benchmark de justesse clinique, aucun reviewer/qualification/décision simulé.
- Aucune donnée/interface propriétaire Ada copiée ; l'inspiration du parcours UX ne donne aucun
  droit à ses contenus ou données.
- Livrable documentaire uniquement ; la préparation, les permissions et la curation sont les
  prochaines étapes. G1/G2/G5 humains et G3 indépendant restent nécessaires.
