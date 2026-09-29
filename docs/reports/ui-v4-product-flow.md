# Mode simple v4 — parcours produit expérimental

28 septembre 2026. Travail d'interface, non validation clinique.

- Ordre affiché : Informations → Symptômes → Questions → Résultats. Nouveau profil local
  obligatoire pour une nouvelle analyse simple : prénom/nom ou pseudonymes et âge. Les
  quatre listes de contexte sont facultatives, auto-déclarées et non évaluées.
- L'âge seul est projeté dans le même `ClinicalCaseV2` ; aucun nom ni antécédent non codé dans
  les sorties scientifiques. Révisions de session et stockage atomique existant.
- Un clic volontaire sur un finding anatomique ou une suggestion est `present` par défaut.
  L'état se modifie ensuite dans le récapitulatif. Les IDs et observations sont les mêmes.
- Précisions backend versionnées : durée, intensité déclarée et côté, selon une petite allowlist
  explicite de concepts HPO. Par exemple, toux ne propose que la durée ; un concept non
  configuré ne déclenche aucune sous-question. Écran facultatif après enregistrement des
  symptômes, « passer » possible. Leur capture n'ajoute aucune assertion ni politique de score.
  Pas de fausse localisation de céphalée.
- Header, progression, cartes, question et résultats utilisent une couche CSS locale dédiée.
  Résultat : rang/éléments réels, aucun pourcentage, détail scientifique à la demande. La
  section rare reste une action explicite après les résultats généraux ; `/expert` subsiste.
- La question adaptative reste celle du backend. L'explication « pourquoi cette question »
  indique honnêtement qu'il s'agit d'une proposition de politique expérimentale, sans
  prétendre à un gain informationnel ou à une validité clinique.

## Limites

Les champs optionnels ne modifient aucun raisonnement actuel. Le questionnaire de précisions
est borné à quelques symptômes et non spécifique à une maladie. Des scénarios cliniques réellement pertinents,
les traductions médicales et la revue humaine doivent être traités séparément. Snapshot
`v0.7.0-general-dev-unreviewed`, `clinical_validation: false`, `publishable: false`,
`research_unreviewed: true`, `safety_status: not_evaluated` demeurent inchangés.
