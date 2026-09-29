"use strict";
// Versioned, local presentation strings. No medical inference or translation service.
(() => {
  const catalog = {
"verification_title": ["Vérifier ces possibilités","Diese Möglichkeiten prüfen","Check these possibilities"],
"verification_intro": ["Facultatif : quelques éléments non évalués des cinq premières possibilités. Une réponse négative n'exclut pas à elle seule une maladie.","Freiwillig: einige noch nicht geprüfte Merkmale der ersten fünf Möglichkeiten. Eine negative Antwort schließt eine Erkrankung nicht allein aus.","Optional: a few unassessed findings from the first five possibilities. A negative answer alone does not rule out a condition."],
"verification_start": ["Vérifier ces possibilités","Möglichkeiten prüfen","Check these possibilities"],
"verification_updated": ["Résultats actualisés. Le premier résultat reste conservé localement.","Ergebnisse aktualisiert. Das erste Ergebnis bleibt lokal gespeichert.","Results updated. The first result remains stored locally."],
"verification_back": ["← Revenir aux premiers résultats","← Zurück zu den ersten Ergebnissen","← Back to initial results"],
"verification_neutral": ["Répondez selon ce que vous savez aujourd'hui. Vous pourrez corriger votre réponse.","Antworten Sie nach Ihrem heutigen Kenntnisstand. Sie können Ihre Antwort korrigieren.","Answer based on what you know today. You can correct your answer."],
"verification_finish": ["Voir les résultats actualisés maintenant","Aktualisierte Ergebnisse jetzt anzeigen","Show updated results now"],
"verification_progress": ["Vérification {count} · au plus {maximum} au total","Prüfung {count} · höchstens {maximum} insgesamt","Check {count} · at most {maximum} in total"],
"verification_question": ["Avez-vous {label} ?","Haben Sie {label}?","Do you have {label}?"],
"verification_loading": ["Préparation locale des questions…","Lokale Vorbereitung der Fragen…","Preparing local questions…"],
"verification_missing_count": ["{count} élément(s) non évalué(s) ; ils ne sont pas des contradictions.","{count} nicht geprüfte Merkmale; sie sind keine Widersprüche.","{count} unassessed findings; they are not contradictions."],
"narrative_label": ["Décrivez vos symptômes avec vos mots (facultatif)","Beschreiben Sie Ihre Beschwerden in eigenen Worten (freiwillig)","Describe your symptoms in your own words (optional)"],
"narrative_placeholder": ["Par exemple : J’ai le nez qui coule et mal à la gorge…","Zum Beispiel: Meine Nase läuft und ich habe Halsschmerzen…","For example: I have a runny nose and a sore throat…"],
"narrative_note": ["Un modèle local peut proposer des symptômes ; vous les confirmerez avant l’analyse.","Ein lokales Modell kann Symptome vorschlagen; Sie bestätigen sie vor der Analyse.","A local model may suggest symptoms; you confirm them before analysis."],
"nlp_title": ["Symptômes repérés dans votre description","In Ihrer Beschreibung erkannte Symptome","Symptoms found in your description"],
"nlp_loading": ["Analyse locale de votre description en cours… Vous pouvez continuer à explorer.","Ihre Beschreibung wird lokal verarbeitet… Sie können weiter erkunden.","Processing your description locally… You can keep exploring."],
"nlp_unavailable": ["Le modèle local est indisponible. Ajoutez vos symptômes par recherche ou anatomie.","Das lokale Modell ist nicht verfügbar. Fügen Sie Symptome über Suche oder Anatomie hinzu.","The local model is unavailable. Add symptoms through search or anatomy."],
"nlp_review": ["Vérifiez ces propositions. Rien n’est ajouté avant votre confirmation.","Prüfen Sie diese Vorschläge. Vor Ihrer Bestätigung wird nichts hinzugefügt.","Review these suggestions. Nothing is added before you confirm."],
"nlp_no_match": ["Aucun symptôme fiable repéré. Utilisez la recherche ou l’anatomie.","Kein verlässliches Symptom erkannt. Nutzen Sie Suche oder Anatomie.","No reliable symptom found. Use search or anatomy."],
"nlp_choice": ["Concept proposé","Vorgeschlagenes Konzept","Suggested concept"],
"nlp_choose": ["Choisir un concept","Konzept auswählen","Choose a concept"],
"nlp_confirm": ["Confirmer les symptômes sélectionnés","Ausgewählte Symptome bestätigen","Confirm selected symptoms"],
"nlp_confirmed": ["Symptômes confirmés et ajoutés au cas.","Symptome bestätigt und zum Fall hinzugefügt.","Symptoms confirmed and added to the case."],
"nlp_saving": ["Enregistrement des symptômes confirmés…","Bestätigte Symptome werden gespeichert…","Saving confirmed symptoms…"],
"region_more": ["Voir plus","Mehr anzeigen","See more"],
"region_search": ["Rechercher dans cette région…","In dieser Region suchen…","Search this region…"],
"my_information": ["Mes informations","Meine Angaben","My information"],
"welcome_title": ["Bienvenue sur Latros","Willkommen bei Latros","Welcome to Latros"],
"welcome_lead": ["Quelques informations, puis vos symptômes. À votre rythme.","Einige Angaben, dann Ihre Symptome. In Ihrem Tempo.","A few details, then your symptoms. At your pace."],
"private_local": ["Privé et local","Privat und lokal","Private and local"],
"identity_note": ["Votre nom sert uniquement à identifier cette session locale. Un pseudonyme convient.","Ihr Name dient nur zur Kennzeichnung dieser lokalen Sitzung. Ein Pseudonym ist möglich.","Your name only identifies this local session. A pseudonym is fine."],
"first_name": ["Prénom","Vorname","First name"],
"last_name": ["Nom","Nachname","Last name"],
"first_name_placeholder": ["Prénom ou pseudonyme","Vorname oder Pseudonym","First name or pseudonym"],
"last_name_placeholder": ["Nom ou identifiant local","Nachname oder lokale Kennung","Last name or local identifier"],
"patient_name_error": ["Indiquez un nom et un prénom, ou des pseudonymes pour cette session locale.","Bitte geben Sie Vor- und Nachnamen oder Pseudonyme für diese lokale Sitzung ein.","Enter a first and last name, or pseudonyms for this local session."],
"background_title": ["Contexte personnel facultatif","Freiwilliger persönlicher Kontext","Optional personal background"],
"background_note": ["Ces informations restent séparées des observations. Le moteur actuel ne les évalue pas.","Diese Angaben bleiben von den Beobachtungen getrennt. Die aktuelle Strategie bewertet sie nicht.","These details stay separate from observations. The current engine does not evaluate them."],
"allergies_label": ["Allergies connues (déclarées)","Bekannte Allergien (selbst berichtet)","Known allergies (self-reported)"],
"conditions_label": ["Maladies connues (déclarées)","Bekannte Erkrankungen (selbst berichtet)","Known conditions (self-reported)"],
"medications_label": ["Traitements en cours (déclarés)","Aktuelle Medikamente (selbst berichtet)","Current medications (self-reported)"],
"history_label": ["Antécédents / opérations (déclarés)","Vorgeschichte / Eingriffe (selbst berichtet)","History / operations (self-reported)"],
"one_item_per_line": ["Un élément par ligne","Ein Eintrag pro Zeile","One item per line"],
"continue_symptoms": ["Continuer vers les symptômes →","Weiter zu den Symptomen →","Continue to symptoms →"],
"saving_information": ["Enregistrement local…","Wird lokal gespeichert…","Saving locally…"],
"refinement_count": ["Précision {count} sur {total}","Angabe {count} von {total}","Detail {count} of {total}"],
"refinement_lead": ["Quelques précisions facultatives sur ce que vous ressentez.","Einige freiwillige Angaben zu Ihren Beschwerden.","A few optional details about what you feel."],
"refinement_limit": ["Conservées localement, ces précisions ne sont pas encore utilisées pour classer les possibilités.","Diese Angaben werden lokal gespeichert und noch nicht zur Einordnung verwendet.","Stored locally, these details are not yet used for ranking."],
"duration_label": ["Depuis combien de temps ?","Seit wie langer Zeit?","For how long?"],
"duration_unit": ["Unité de durée","Zeiteinheit","Duration unit"],
"unit_hour": ["Heures","Stunden","Hours"],
"unit_day": ["Jours","Tage","Days"],
"unit_week": ["Semaines","Wochen","Weeks"],
"unit_month": ["Mois","Monate","Months"],
"unit_year": ["Années","Jahre","Years"],
"severity_label": ["Intensité ressentie","Empfundene Stärke","Perceived intensity"],
"laterality_label": ["Côté, si cela s’applique","Seite, falls zutreffend","Side, if applicable"],
"not_specified": ["Non précisé","Nicht angegeben","Not specified"],
"refine_mild": ["Légère","Leicht","Mild"],
"refine_moderate": ["Modérée","Mittel","Moderate"],
"refine_severe": ["Forte","Stark","Severe"],
"refine_left": ["Gauche","Links","Left"],
"refine_right": ["Droite","Rechts","Right"],
"refine_bilateral": ["Des deux côtés","Beidseitig","Both sides"],
"refine_midline": ["Au milieu","Mittig","Midline"],
"refine_not_applicable": ["Sans côté","Nicht zutreffend","Not applicable"],
"save_continue": ["Enregistrer et continuer","Speichern und weiter","Save and continue"],
"skip_refinements": ["Passer toutes les précisions","Alle Angaben überspringen","Skip all details"],
"duration_error": ["Indiquez une durée entière de 1 à 10 000 ou laissez le champ vide.","Geben Sie eine ganze Dauer von 1 bis 10 000 ein oder lassen Sie das Feld leer.","Enter a whole duration from 1 to 10,000 or leave it blank."],
"why_question": ["Pourquoi cette question ?","Warum diese Frage?","Why this question?"],
"question_policy_reason": ["La stratégie locale propose ce concept parmi les questions disponibles. Ce choix n’est pas validé cliniquement.","Die lokale Strategie schlägt dieses Konzept vor. Die Auswahl ist nicht klinisch validiert.","The local strategy proposes this concept. This choice is not clinically validated."],
"result_card_explanation": ["Cette possibilité est classée par compatibilité non calibrée avec les éléments renseignés.","Diese Möglichkeit wird nach unkalibrierter Übereinstimmung mit den Angaben eingeordnet.","This possibility is ranked by uncalibrated compatibility with the information entered."],
"no_favorable_short": ["Aucun élément en faveur affiché","Keine passenden Hinweise angezeigt","No supporting finding shown"],
"no_unfavorable_short": ["Aucune contradiction affichée","Kein Widerspruch angezeigt","No contradiction shown"],
"general_title": ["Questions de l’analyse générale","Fragen der allgemeinen Analyse","General analysis questions"],
"rare_title": ["Exploration des maladies rares","Erkundung seltener Erkrankungen","Rare disease exploration"],
"general_results": ["Résultats de l’analyse générale expérimentale","Ergebnisse der experimentellen allgemeinen Analyse","Experimental general analysis results"],
"rare_results": ["Résultats de l’exploration rare","Ergebnisse der Erkundung seltener Erkrankungen","Rare exploration results"],
"rare_cta": ["Explorer aussi les maladies rares","Auch seltene Erkrankungen erkunden","Also explore rare diseases"],
"rare_start": ["Explorer les maladies rares","Seltene Erkrankungen erkunden","Explore rare diseases"],
"rare_explanation": ["Cette exploration facultative pose des questions supplémentaires, parfois très spécifiques. Les résultats restent séparés et non validés.","Diese freiwillige Erkundung stellt zusätzliche, teils sehr spezifische Fragen. Ergebnisse bleiben getrennt und unvalidiert.","This optional exploration asks additional, sometimes very specific questions. Results remain separate and unvalidated."],
"rare_now": ["Afficher les résultats rares maintenant","Ergebnisse zu seltenen Erkrankungen jetzt anzeigen","Show rare results now"],
"bounded_question": ["Question {count} · limite {budget} · au plus {remaining} autres (budget, pas prévision médicale)","Frage {count} · Grenze {budget} · höchstens {remaining} weitere (Budget, keine medizinische Prognose)","Question {count} · limit {budget} · at most {remaining} more (budget, not medical prediction)"],
"local": ["Local","Lokal","Local"],
"anatomy_navigation": ["Navigation anatomique","Anatomische Navigation","Anatomical navigation"],
"search_and_observations": ["Recherche et observations","Suche und Beobachtungen","Search and observations"],
"theme": ["Changer le thème clair/sombre","Hell/dunkel umschalten","Toggle light/dark theme"],
"body": ["Corps","Körper","Body"],
"illustration_status": ["Illustrations générées, non validées anatomiquement. Navigation uniquement.","Generierte Illustrationen, anatomisch nicht validiert. Nur zur Navigation.","Generated illustrations, not anatomically validated. Navigation only."],
"explore": ["Explorez une région du corps","Erkunden Sie eine Körperregion","Explore a body region"],
"anatomy_hint": ["Cliquez sur une région ou utilisez la recherche. La carte aide à naviguer, pas à diagnostiquer.","Wählen Sie eine Region oder nutzen Sie die Suche. Die Karte dient der Navigation, nicht der Diagnose.","Select a region or use search. The map is navigation, not a diagnosis."],
"region_pending": ["Cette vue détaillée n’est pas encore disponible. La recherche reste accessible.","Diese Detailansicht ist noch nicht verfügbar. Die Suche bleibt zugänglich.","This detailed view is not available yet. Search is still available."],
"findings_prompt": ["Que constatez-vous ?","Was bemerken Sie?","What do you notice?"],
"region_empty": ["Aucune observation supportée n’est disponible pour cette région dans le snapshot actif.","Für diese Region sind im aktiven Snapshot keine unterstützten Beobachtungen verfügbar.","No supported observations are available for this region in the active snapshot."],
"present": ["Présent","Vorhanden","Present"],
"absent": ["Absent","Nicht vorhanden","Absent"],
"add_case": ["Ajouter au cas","Zum Fall hinzufügen","Add to case"],
"selected_title": ["Symptômes sélectionnés","Ausgewählte Symptome","Selected symptoms"],
"selected_empty": ["Ajoutez un symptôme depuis la carte ou la recherche.","Fügen Sie ein Symptom über die Karte oder Suche hinzu.","Add a symptom using the map or search."],
"case_changed": ["Observations modifiées. Relancez l’analyse ou demandez une nouvelle question.","Beobachtungen geändert. Analyse neu starten oder eine neue Frage anfordern.","Observations changed. Run the analysis again or request a new question."],
"analyze": ["Analyser avec Latros","Mit Latros analysieren","Analyse with Latros"],
"next_question": ["Question suivante","Nächste Frage","Next question"],
"added_case": ["Observation ajoutée. Vous pouvez continuer à explorer.","Beobachtung hinzugefügt. Sie können weiter erkunden.","Observation added. You can continue exploring."],
"region_loading": ["Chargement des observations locales…","Lokale Beobachtungen werden geladen…","Loading local observations…"],
"region_error": ["Observations indisponibles. Réessayez ou utilisez la recherche.","Beobachtungen nicht verfügbar. Erneut versuchen oder Suche nutzen.","Observations unavailable. Retry or use search."],
"navigate_region": ["Voir la région","Region anzeigen","View region"],
"anatomy_back": ["Revenir à la région précédente","Zur vorherigen Region","Back to previous region"],
"select_state": ["État de l’observation","Beobachtungsstatus","Observation status"],
"navigate_body": ["Explorer le corps","Körper erkunden","Explore the body"],
"search_open": ["Rechercher / symptômes","Suche / Symptome","Search / symptoms"],
"source_labels": ["Labels source conservés ; carte de navigation uniquement.","Originalbezeichnungen bleiben erhalten; Karte nur zur Navigation.","Source labels preserved; map is navigation only."],
  "title": [
    "Latros — Explorer ses symptômes",
    "Latros — Symptome erkunden",
    "Latros — Explore symptoms"
  ],
  "home": [
    "Qu’est-ce qui vous gêne ?",
    "Was belastet Sie?",
    "What is bothering you?"
  ],
  "history": [
    "Historique",
    "Verlauf",
    "History"
  ],
  "expert": [
    "Mode expert",
    "Expertenmodus",
    "Expert mode"
  ],
  "symptoms": [
    "Symptômes",
    "Symptome",
    "Symptoms"
  ],
  "information": [
    "Informations",
    "Informationen",
    "Information"
  ],
  "questions": [
    "Questions",
    "Fragen",
    "Questions"
  ],
  "results": [
    "Résultats",
    "Ergebnisse",
    "Results"
  ],
  "home_eyebrow": [
    "Une recherche locale, à votre rythme",
    "Lokal und in Ihrem Tempo",
    "Local, at your own pace"
  ],
  "home_lead": [
    "Choisissez les symptômes qui correspondent à ce que vous ressentez.",
    "Wählen Sie die Symptome, die Ihre Beschwerden beschreiben.",
    "Select the symptoms that describe how you feel."
  ],
  "search_label": [
    "Rechercher un symptôme",
    "Symptom suchen",
    "Search for a symptom"
  ],
  "search_placeholder": [
    "Rechercher un symptôme…",
    "Symptom suchen…",
    "Search for a symptom…"
  ],
  "search_hint": [
    "Sélectionnez une suggestion. Ce champ ne convertit pas le texte libre ; décrivez vos symptômes dans Informations.",
    "Wählen Sie einen Vorschlag. Dieses Feld wandelt Freitext nicht um; beschreiben Sie Ihre Beschwerden unter Angaben.",
    "Select a suggestion. This field does not interpret free text; describe your symptoms in Information."
  ],
  "continue": [
    "Continuer",
    "Weiter",
    "Continue"
  ],
  "terms_notice": [
    "Les termes proposés viennent de la base locale ; certaines formulations françaises peuvent encore manquer.",
    "Die Vorschläge stammen aus der lokalen Datenbank. Fehlende Übersetzungen werden als EN gekennzeichnet.",
    "Suggestions come from the local database. Missing translations are marked EN."
  ],
  "terms_updated": [
    "Les traductions sont locales. Les termes non traduits sont signalés EN ; confirmez toujours la suggestion.",
    "Übersetzungen sind lokal. Nicht übersetzte Begriffe sind mit EN markiert; bestätigen Sie immer den Vorschlag.",
    "Translations are local. Untranslated terms are marked EN; always confirm a suggestion."
  ],
  "back_symptoms": [
    "← Retour aux symptômes",
    "← Zurück zu den Symptomen",
    "← Back to symptoms"
  ],
  "one_at_a_time": [
    "Une information à la fois",
    "Eine Angabe nach der anderen",
    "One detail at a time"
  ],
  "age_title": [
    "Quel âge avez-vous ?",
    "Wie alt sind Sie?",
    "How old are you?"
  ],
  "adult_scope": [
    "Le moteur général actuel est limité aux adultes : sans âge exploitable, il peut s’abstenir.",
    "Die aktuelle allgemeine Strategie ist auf Erwachsene begrenzt. Ohne nutzbare Altersangabe kann sie sich enthalten.",
    "The current general strategy is limited to adults. Without usable age information it may abstain."
  ],
  "age_label": [
    "Âge en années",
    "Alter in Jahren",
    "Age in years"
  ],
  "age_placeholder": [
    "Votre âge",
    "Ihr Alter",
    "Your age"
  ],
  "skip_age": [
    "Je préfère ne pas répondre",
    "Ich möchte nicht antworten",
    "I prefer not to answer"
  ],
  "back": [
    "← Retour",
    "← Zurück",
    "← Back"
  ],
  "engine_question": [
    "Question du moteur",
    "Frage der Strategie",
    "Question from the engine"
  ],
  "question_title": [
    "Une question pour préciser",
    "Eine Frage zur Präzisierung",
    "A question to clarify"
  ],
  "yes": [
    "Oui",
    "Ja",
    "Yes"
  ],
  "no": [
    "Non",
    "Nein",
    "No"
  ],
  "unknown": [
    "Je ne sais pas",
    "Ich weiß es nicht",
    "I don't know"
  ],
  "skip": [
    "Passer",
    "Überspringen",
    "Skip"
  ],
  "unable": [
    "Impossible à évaluer",
    "Nicht beurteilbar",
    "Unable to assess"
  ],
  "results_now": [
    "Voir les résultats maintenant",
    "Jetzt Ergebnisse ansehen",
    "View results now"
  ],
  "complete": [
    "Analyse terminée",
    "Analyse abgeschlossen",
    "Analysis complete"
  ],
  "more": [
    "Voir plus de possibilités",
    "Weitere Möglichkeiten anzeigen",
    "Show more possibilities"
  ],
  "new_analysis": [
    "Nouvelle analyse",
    "Neue Analyse",
    "New analysis"
  ],
  "edit": [
    "Modifier mes informations",
    "Angaben bearbeiten",
    "Edit my information"
  ],
  "view_history": [
    "Voir l’historique",
    "Verlauf ansehen",
    "View history"
  ],
  "back_home": [
    "← Retour à l’accueil",
    "← Zurück zum Start",
    "← Back to home"
  ],
  "local_saved": [
    "Conservé sur cet ordinateur",
    "Auf diesem Computer gespeichert",
    "Stored on this computer"
  ],
  "history_lead": [
    "Reprenez une analyse enregistrée ou commencez-en une nouvelle.",
    "Setzen Sie eine gespeicherte Analyse fort oder beginnen Sie eine neue.",
    "Resume a saved analysis or start a new one."
  ],
  "service_unavailable": [
    "Service local indisponible",
    "Lokaler Dienst nicht verfügbar",
    "Local service unavailable"
  ],
  "cannot_continue": [
    "Latros ne peut pas continuer",
    "Latros kann nicht fortfahren",
    "Latros cannot continue"
  ],
  "retry": [
    "Réessayer",
    "Erneut versuchen",
    "Try again"
  ],
  "open_expert": [
    "Ouvrir le mode expert",
    "Expertenmodus öffnen",
    "Open expert mode"
  ],
  "emergency_title": [
    "Urgences non évaluées.",
    "Notfälle werden nicht bewertet.",
    "Emergencies are not evaluated."
  ],
  "safety": [
    "Cette version n’évalue pas encore les situations urgentes et ne remplace pas un avis médical.",
    "Diese Version bewertet keine Notfallsituationen und ersetzt keine ärztliche Beratung.",
    "This version does not evaluate emergencies and does not replace medical advice."
  ],
  "why": [
    "Pourquoi cette possibilité apparaît",
    "Warum diese Möglichkeit angezeigt wird",
    "Why this possibility appears"
  ],
  "close": [
    "Fermer",
    "Schließen",
    "Close"
  ],
  "loading": [
    "Chargement local…",
    "Lokal wird geladen…",
    "Loading locally…"
  ],
  "navigation": [
    "Navigation principale",
    "Hauptnavigation",
    "Main navigation"
  ],
  "steps": [
    "Étapes du parcours",
    "Schritte",
    "Steps"
  ],
  "suggestions": [
    "Suggestions de symptômes",
    "Symptomvorschläge",
    "Symptom suggestions"
  ],
  "answer_question": [
    "Répondre à la question",
    "Frage beantworten",
    "Answer the question"
  ],
  "home_aria": [
    "Latros, accueil",
    "Latros, Start",
    "Latros, home"
  ],
  "unreadable": [
    "Le service local a renvoyé une réponse illisible.",
    "Der lokale Dienst hat eine unlesbare Antwort gesendet.",
    "The local service returned an unreadable response."
  ],
  "local_error": [
    "Une erreur locale est survenue.",
    "Ein lokaler Fehler ist aufgetreten.",
    "A local error occurred."
  ],
  "http_error": [
    "Requête locale refusée ({status}). Détail technique : {message}",
    "Lokale Anfrage abgelehnt ({status}). Technisches Detail: {message}",
    "Local request refused ({status}). Technical detail: {message}"
  ],
  "slow": [
    "Le grand corpus demande encore du temps de calcul local…",
    "Der große Datenbestand benötigt noch lokale Rechenzeit…",
    "The large corpus still needs local processing time…"
  ],
  "research_unreviewed": [
    "Prototype de recherche locale — connaissances non revues, validation clinique absente et publication interdite. Ne pas utiliser pour une décision médicale.",
    "Lokaler Forschungsprototyp — ungeprüftes Wissen, keine klinische Validierung, nicht veröffentlichbar. Nicht für medizinische Entscheidungen verwenden.",
    "Local research prototype — unreviewed knowledge, no clinical validation, not publishable. Do not use for medical decisions."
  ],
  "research": [
    "Prototype de recherche locale. Cet outil ne remplace pas un avis médical.",
    "Lokaler Forschungsprototyp. Kein Ersatz für ärztliche Beratung.",
    "Local research prototype. This tool does not replace medical advice."
  ],
  "opening": [
    "Ouverture du service local…",
    "Lokaler Dienst wird geöffnet…",
    "Opening the local service…"
  ],
  "no_snapshot": [
    "Aucun snapshot general_v1 disponible. Vérifiez les fichiers locaux depuis le mode expert.",
    "Kein general_v1-Snapshot verfügbar. Prüfen Sie die lokalen Dateien im Expertenmodus.",
    "No general_v1 snapshot is available. Check local files in expert mode."
  ],
  "remove": [
    "Retirer {label}",
    "{label} entfernen",
    "Remove {label}"
  ],
  "no_concept": [
    "Aucun symptôme correspondant dans la base locale.",
    "Kein passendes Symptom in der lokalen Datenbank.",
    "No matching symptom in the local database."
  ],
  "searching": [
    "Recherche dans la base locale…",
    "Lokale Datenbank wird durchsucht…",
    "Searching the local database…"
  ],
  "choose": [
    "Choisissez un symptôme dans la liste.",
    "Wählen Sie ein Symptom aus der Liste.",
    "Choose a symptom from the list."
  ],
  "try_wording": [
    "Aucun terme correspondant. Essayez une autre formulation.",
    "Kein passender Begriff. Versuchen Sie eine andere Formulierung.",
    "No matching term. Try another wording."
  ],
  "search_unavailable": [
    "La recherche locale est indisponible.",
    "Die lokale Suche ist nicht verfügbar.",
    "Local search is unavailable."
  ],
  "added": [
    "Symptôme ajouté. Vous pouvez en rechercher un autre.",
    "Symptom hinzugefügt. Sie können ein weiteres suchen.",
    "Symptom added. You can search for another."
  ],
  "age_error": [
    "Indiquez un âge entier entre 0 et 130 ans, ou passez cette question.",
    "Geben Sie ein ganzzahliges Alter zwischen 0 und 130 an oder überspringen Sie die Frage.",
    "Enter a whole age between 0 and 130, or skip this question."
  ],
  "question_count": [
    "Question {count} proposée par Latros",
    "Frage {count} von Latros",
    "Question {count} from Latros"
  ],
  "documented": [
    "Observation documentée",
    "Dokumentierte Beobachtung",
    "Documented observation"
  ],
  "result_warning_unreviewed": [
    "Connaissances non revues et urgences non évaluées. Ces résultats ne constituent ni un diagnostic ni un avis médical.",
    "Ungeprüftes Wissen und keine Notfallbewertung. Diese Ergebnisse sind weder Diagnose noch ärztliche Beratung.",
    "Unreviewed knowledge and no emergency evaluation. These results are neither a diagnosis nor medical advice."
  ],
  "result_warning": [
    "Urgences non évaluées. Ces résultats ne constituent pas un diagnostic.",
    "Keine Notfallbewertung. Diese Ergebnisse sind keine Diagnose.",
    "Emergencies are not evaluated. These results are not a diagnosis."
  ],
  "abstention": [
    "Latros s’abstient de conclure avec les informations disponibles.",
    "Latros enthält sich einer Schlussfolgerung mit den verfügbaren Angaben.",
    "Latros abstains from concluding with the available information."
  ],
  "no_results": [
    "Aucune possibilité classée avec les informations disponibles.",
    "Keine eingeordnete Möglichkeit mit den verfügbaren Angaben.",
    "No ranked possibility with the available information."
  ],
  "result_intro": [
    "Plusieurs possibilités correspondent aux informations fournies. Leur rang n’est pas une probabilité et ne tient pas compte de la fréquence des maladies.",
    "Mehrere Möglichkeiten passen zu Ihren Angaben. Der Rang ist keine Wahrscheinlichkeit und berücksichtigt nicht die Häufigkeit der Krankheiten.",
    "Several possibilities match the information supplied. Rank is not a probability and does not account for disease frequency."
  ],
  "rank": [
    "Rang {rank}",
    "Rang {rank}",
    "Rank {rank}"
  ],
  "favorable": [
    "Éléments en faveur",
    "Passende Hinweise",
    "Supporting findings"
  ],
  "unfavorable": [
    "Éléments contradictoires",
    "Widersprüchliche Hinweise",
    "Contradictory findings"
  ],
  "contradiction": [
    "Contradiction :",
    "Widerspruch:",
    "Contradiction:"
  ],
  "see_why": [
    "Voir pourquoi",
    "Warum?",
    "See why"
  ],
  "no_missing": [
    "Aucune information manquante détaillée par le moteur.",
    "Die Strategie führt keine fehlenden Angaben im Detail auf.",
    "No missing information detailed by the engine."
  ],
  "missing_count": [
    "{count} élément(s) du modèle non évalué(s). Leur provenance est consultable dans les détails techniques.",
    "{count} Modellelement(e) nicht bewertet. Herkunft in den technischen Details einsehbar.",
    "{count} model item(s) not evaluated. Their provenance is available in technical details."
  ],
  "local_source": [
    "Source locale",
    "Lokale Quelle",
    "Local source"
  ],
  "why_candidate": [
    "Pourquoi {label} apparaît",
    "Warum {label} angezeigt wird",
    "Why {label} appears"
  ],
  "rank_notice": [
    "Possibilité classée au rang {rank} ; ce rang n’est pas une probabilité.",
    "Möglichkeit auf Rang {rank}; dieser Rang ist keine Wahrscheinlichkeit.",
    "Possibility ranked {rank}; this rank is not a probability."
  ],
  "no_favorable": [
    "Aucun élément favorable retenu.",
    "Keine passenden Hinweise berücksichtigt.",
    "No supporting finding retained."
  ],
  "no_contradiction": [
    "Aucune contradiction retenue dans les observations évaluées.",
    "Keine Widersprüche in den bewerteten Beobachtungen berücksichtigt.",
    "No contradiction retained in assessed observations."
  ],
  "not_evaluated": [
    "Informations non évaluées",
    "Nicht bewertete Angaben",
    "Information not evaluated"
  ],
  "sources": [
    "Sources principales",
    "Hauptquellen",
    "Main sources"
  ],
  "no_sources": [
    "Aucune source détaillée.",
    "Keine Quelle im Detail.",
    "No detailed source."
  ],
  "technical": [
    "Afficher les détails techniques",
    "Technische Details anzeigen",
    "Show technical details"
  ],
  "raw_score": [
    "Compatibilité brute non calibrée : {score}. Ne pas interpréter comme un risque ou une probabilité.",
    "Unkalibrierte Rohkompatibilität: {score}. Nicht als Risiko oder Wahrscheinlichkeit interpretieren.",
    "Uncalibrated raw compatibility: {score}. Do not interpret as risk or probability."
  ],
  "resume": [
    "Reprendre",
    "Fortsetzen",
    "Resume"
  ],
  "resume_expert": [
    "Ouvrir en mode expert",
    "Im Expertenmodus öffnen",
    "Open in expert mode"
  ],
  "saved_locally": [
    "conservé localement",
    "lokal gespeichert",
    "stored locally"
  ],
  "no_history": [
    "Aucune analyse enregistrée sur cet ordinateur.",
    "Keine Analyse auf diesem Computer gespeichert.",
    "No analysis stored on this computer."
  ],
  "advanced_session": [
    "Cette session contient des données avancées. Ouvrez-la dans le mode expert.",
    "Diese Sitzung enthält erweiterte Angaben. Öffnen Sie sie im Expertenmodus.",
    "This session contains advanced data. Open it in expert mode."
  ],
  "session_snapshot_missing": [
    "Le snapshot de cette session n’est plus disponible localement.",
    "Der Snapshot dieser Sitzung ist lokal nicht mehr verfügbar.",
    "This session's snapshot is no longer available locally."
  ],
  "prepare_questions": [
    "Préparation des questions locales…",
    "Lokale Fragen werden vorbereitet…",
    "Preparing local questions…"
  ],
  "analyse_answer": [
    "Analyse de la réponse…",
    "Antwort wird analysiert…",
    "Analysing the answer…"
  ],
  "calculating": [
    "Calcul des possibilités…",
    "Möglichkeiten werden berechnet…",
    "Calculating possibilities…"
  ],
  "loading_detail": [
    "Chargement du détail local…",
    "Lokale Details werden geladen…",
    "Loading local detail…"
  ],
  "opening_analysis": [
    "Ouverture de l’analyse locale…",
    "Lokale Analyse wird geöffnet…",
    "Opening local analysis…"
  ],
  "english_fallback": [
    "Traduction absente : label source anglais (EN).",
    "Keine Übersetzung: englische Originalbezeichnung (EN).",
    "Translation unavailable: English source label (EN)."
  ],
  "source_question": [
    "Question et concept source, IDs inchangés",
    "Originalfrage und Konzept, unveränderte IDs",
    "Source question and concept, unchanged IDs"
  ],
  "language": [
    "Langue",
    "Sprache",
    "Language"
  ]
};
  let language = "fr";
  try { const saved = localStorage.getItem("latros-language"); if (["fr","de","en"].includes(saved)) language = saved; } catch {}
  const t = (key, values = {}) => {
    const entry = catalog[key]; if (!entry) throw new Error("Unknown UI translation: " + key);
    let text = entry[{fr:0,de:1,en:2}[language]];
    for (const [name,value] of Object.entries(values)) text = text.replaceAll("{" + name + "}",String(value));
    return text;
  };
  const apply = () => {
    document.documentElement.lang = language;
    document.querySelectorAll("[data-i18n]").forEach(node => node.textContent = t(node.dataset.i18n));
    document.querySelectorAll("[data-i18n-placeholder]").forEach(node => node.placeholder = t(node.dataset.i18nPlaceholder));
    document.querySelectorAll("[data-i18n-aria]").forEach(node => node.setAttribute("aria-label",t(node.dataset.i18nAria)));
    document.querySelectorAll("[data-language]").forEach(node => node.setAttribute("aria-pressed",String(node.dataset.language === language)));
  };
  window.LatrosI18n = { t, apply, get language() { return language; },
    setLanguage(value) { if (!["fr","de","en"].includes(value)) throw new Error("Unsupported UI language"); language=value; try { localStorage.setItem("latros-language",value); } catch {} apply(); },
    catalogVersion: "ui-i18n-2"
  };
})();
