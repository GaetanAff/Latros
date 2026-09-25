# ADR 0012 — Isoler la revue humaine G1/G2 des snapshots et de l'interface utilisateur

Date : 25 septembre 2026. Statut : accepté pour l'outil de préparation de revue.

## Contexte

Les exports G1/G2 sont des pistes et échantillons **non revus**. Les annoter dans un classeur
expose les décisions à des écrasements accidentels et ne fournit pas naturellement un journal
append-only. Le parcours symptom checker ne doit pas devenir un outil de curation clinique.

## Décision

Un petit serveur FastAPI distinct, local sur `127.0.0.1`, lit les trois CSV G1/G2 épinglés par
hash. Il présente une ligne à la fois et exige une action explicite, une identité déclarée et
une attestation. Il écrit uniquement un journal JSONL local sous `data/staging/`, avec horodatage,
hash de ligne et chaîne de hashes. Il ne dispose d'aucun chemin d'écriture vers le snapshot,
le registre, le profil de raisonnement ou les sessions du symptom checker. Un export déterministe
permet de remettre les décisions à un processus de revue clinique ultérieur, distinct.

Le jeton de session, la restriction same-origin et la CSP protègent l'interface loopback contre
une requête web croisée ordinaire. Il n'y a ni CDN, ni API externe, ni télémétrie.

## Conséquences

- Les actions `approve_exact/equivalent` restent des décisions humaines **dans le journal** ;
  elles ne promeuvent aucun mapping ni assertion. G1/G2 ne sont pas terminés par l'existence de
  cet outil.
- La véritable identité et les qualifications ne peuvent être certifiées par une simple UI
  locale ; l'équipe de revue doit les contrôler et conserver l'export dans son cadre de gouvernance.
- Le journal peut être vérifié, mais la chaîne de hashes n'est pas une signature numérique ni un
  mécanisme multi-utilisateur concurrent. Une seule instance locale est prévue.
- Toute intégration future des décisions dans une nouvelle release exigera un pipeline audité,
  un nouvel identifiant de snapshot et une décision clinique explicite.
