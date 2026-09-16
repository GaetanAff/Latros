# Consignes de continuité — Latros

Consulter `docs/plan.md`, `history.md` et `CONTRIBUTING.md` avant une nouvelle tranche de travail. Distinguer les fonctionnalités déjà implémentées des étapes futures discutées.

Pour chaque changement livré :

- Actualiser `history.md` avec une entrée datée : changements réels, décisions, vérifications effectuées et limites restantes. Préserver les entrées antérieures.
- Actualiser `README.md` et `docs/plan.md` pour que les commandes, références et états de jalons correspondent à la livraison.
- Actualiser les autres documents concernés (`projet.md`, ADR, schémas, registre, manifestes) lorsque leurs informations évoluent.
- Identifier les snapshots de référence par les versions du plan. Le premier snapshot médical est `v0.2.0`. La version du paquet Python est distincte.
- Garder les manifestes publiés immuables ; toute nouvelle référence est construite sous un nouvel identifiant. Conserver les anciennes références historiques.
- Ne pas versionner sources médicales brutes, bases générées, données patient, modèles ou secrets.

Une demande de discussion seule n'autorise pas à développer de nouvelles fonctionnalités. Ne pas inclure les changements locaux sans rapport avec la tâche dans les commits.
