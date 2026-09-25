"use strict";

// Presentation only: all concept resolution, questions, scoring and safety state
// come from the loopback Latros API. No clinical rule is evaluated here.
const state = {
  capabilities: null,
  selection: null,
  sessions: [],
  session: null,
  selected: [],
  suggestions: [],
  resultRun: null,
  questionRun: null,
  questionCount: 0,
  searchSequence: 0,
  searchTimer: null,
  busyTimer: null,
  busy: false,
  visibleCount: 5,
};

const byId = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");
const sessionPath = () => `/internal/v1/sessions/${encodeURIComponent(state.session.session_id)}`;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  let payload;
  try { payload = await response.json(); }
  catch { throw new Error("Le service local a renvoyé une réponse illisible."); }
  if (!response.ok) throw new Error(payload.message || `Erreur HTTP ${response.status}`);
  return payload;
}

function notice(message) {
  byId("app-message").textContent = message;
  byId("app-message").hidden = !message;
}

function setBusy(busy, message = "Chargement local…") {
  state.busy = busy;
  window.clearTimeout(state.busyTimer);
  byId("loading-text").textContent = message;
  byId("loading-layer").hidden = !busy;
  byId("app-shell").setAttribute("aria-busy", String(busy));
  if (busy) {
    state.busyTimer = window.setTimeout(() => {
      byId("loading-text").textContent = "Le grand corpus peut nécessiter plus d’une minute de calcul local…";
    }, 15000);
  }
}

async function guarded(action, message = "Chargement local…") {
  if (state.busy) return;
  notice("");
  setBusy(true, message);
  try { await action(); }
  catch (error) { notice(error.message || "Une erreur locale est survenue."); }
  finally { setBusy(false); }
}

function showScreen(name) {
  ["home", "age", "question", "results", "history", "error"].forEach((screen) => {
    byId(`screen-${screen}`).hidden = screen !== name;
  });
  const steps = ["home", "age", "question", "results"];
  document.querySelectorAll("[data-progress]").forEach((element) => {
    const step = element.dataset.progress;
    element.classList.toggle("active", step === name);
    element.classList.toggle("done", steps.indexOf(step) < steps.indexOf(name) && steps.includes(name));
  });
  byId("nav-expert").href = state.session
    ? `/expert?session=${encodeURIComponent(state.session.session_id)}` : "/expert";
  window.scrollTo({ top: 0, behavior: "instant" });
}

function preferredSelection(capabilities) {
  const available = (capabilities.compatible_selections || [])
    .filter((item) => item.available && item.strategy_id === "general_v1");
  return available.find((item) => item.snapshot_id === "v0.7.0-general-dev-unreviewed")
    || available[0] || null;
}

function updateResearchNotice() {
  const snapshot = (state.capabilities?.snapshots || [])
    .find((item) => item.snapshot_id === state.selection?.snapshot_id);
  byId("research-banner").classList.toggle("unreviewed", Boolean(snapshot?.research_unreviewed));
  byId("research-banner").textContent = snapshot?.research_unreviewed
    ? "Prototype de recherche locale — connaissances non revues, validation clinique absente et publication interdite. Ne pas utiliser pour une décision médicale."
    : "Prototype de recherche locale. Cet outil ne remplace pas un avis médical.";
}

async function boot() {
  notice("");
  setBusy(true, "Ouverture du service local…");
  try {
    state.capabilities = await api("/internal/v1/capabilities");
    state.selection = preferredSelection(state.capabilities);
    if (!state.selection) {
      throw new Error("Aucun snapshot general_v1 disponible. Vérifiez les fichiers locaux depuis le mode expert.");
    }
    updateResearchNotice();
    const payload = await api("/internal/v1/sessions");
    state.sessions = payload.items || [];
    renderHistory();
    showScreen("home");
  } catch (error) {
    byId("error-text").textContent = error.message || "Le backend local est indisponible.";
    showScreen("error");
  } finally { setBusy(false); }
}

function renderSelected() {
  byId("selected-symptoms").innerHTML = state.selected.map((item, index) => `
    <span class="chip"><span>${escapeHtml(item.label)}</span>
      <button type="button" data-remove-index="${index}" aria-label="Retirer ${escapeHtml(item.label)}">×</button>
    </span>`).join("");
  byId("home-continue").disabled = state.selected.length === 0;
}

function renderSuggestions() {
  const panel = byId("symptom-suggestions");
  const query = byId("symptom-search").value.trim();
  if (query.length < 2) {
    panel.hidden = true;
    byId("symptom-search").setAttribute("aria-expanded", "false");
    return;
  }
  panel.innerHTML = state.suggestions.length
    ? state.suggestions.map((item, index) => `
      <button type="button" class="suggestion" role="option" data-suggestion-index="${index}">
        ${escapeHtml(item.label)}
      </button>`).join("")
    : '<div class="suggestion-empty">Aucun symptôme correspondant dans la base locale.</div>';
  panel.hidden = false;
  byId("symptom-search").setAttribute("aria-expanded", "true");
}

async function searchConcepts() {
  const query = byId("symptom-search").value.trim();
  const sequence = ++state.searchSequence;
  if (query.length < 2) {
    state.suggestions = [];
    renderSuggestions();
    byId("search-hint").textContent = "Sélectionnez une suggestion. La saisie libre n’est pas encore interprétée.";
    return;
  }
  byId("search-hint").textContent = "Recherche dans la base locale…";
  const params = new URLSearchParams({
    snapshot: state.selection.snapshot_id,
    strategy: state.selection.strategy_id,
    q: query,
    limit: "12",
  });
  try {
    const payload = await api(`/internal/v1/concepts?${params}`);
    if (sequence !== state.searchSequence) return;
    state.suggestions = payload.items || [];
    renderSuggestions();
    byId("search-hint").textContent = state.suggestions.length
      ? "Choisissez un symptôme dans la liste." : "Aucun terme correspondant. Essayez une autre formulation.";
  } catch (error) {
    if (sequence !== state.searchSequence) return;
    state.suggestions = [];
    renderSuggestions();
    byId("search-hint").textContent = "La recherche locale est indisponible.";
    notice(error.message);
  }
}

function selectSuggestion(index) {
  const item = state.suggestions[index];
  if (!item) return;
  if (!state.selected.some((selected) => selected.concept_id === item.concept_id)) {
    state.selected.push(item);
  }
  byId("symptom-search").value = "";
  state.suggestions = [];
  ++state.searchSequence;
  renderSuggestions();
  renderSelected();
  byId("search-hint").textContent = "Symptôme ajouté. Vous pouvez en rechercher un autre.";
  byId("symptom-search").focus();
}

function makeObservation(option) {
  return {
    kind: option.observation_kind,
    observation_id: `observation-${crypto.randomUUID()}`,
    concept: {
      concept_id: option.concept_id,
      coding: { system: option.system, code: option.code, display: option.label },
    },
    clinical_status: "present",
    evaluation_status: "assessed",
    acquisition_method: "reported",
    provenance: {
      provenance_id: `provenance-${crypto.randomUUID()}`,
      origin_type: "patient_report",
    },
  };
}

function ageContext() {
  const value = byId("patient-age").value.trim();
  if (value === "") return {};
  const age = Number(value);
  if (!Number.isInteger(age) || age < 0 || age > 130) {
    throw new Error("Indiquez un âge entier entre 0 et 130 ans, ou passez cette question.");
  }
  return {
    age: {
      kind: "quantity", value: age, comparator: "eq", unit: "year",
      system: "http://unitsofmeasure.org", code: "a",
    },
  };
}

async function ensureSession() {
  if (!state.session) {
    const title = state.selected.slice(0, 2).map((item) => item.label).join(", ")
      || "Nouvelle analyse";
    state.session = await api("/internal/v1/sessions", {
      method: "POST", body: JSON.stringify({ display_name: title.slice(0, 120) }),
    });
  }
  if (state.session.selection?.snapshot_id !== state.selection.snapshot_id
      || state.session.selection?.strategy_id !== state.selection.strategy_id) {
    state.session = await api(`${sessionPath()}/selection`, {
      method: "PUT",
      body: JSON.stringify({ revision: state.session.revision,
        snapshot_id: state.selection.snapshot_id, strategy_id: state.selection.strategy_id }),
    });
  }
  const clinicalCase = structuredClone(state.session.clinical_case);
  clinicalCase.subject_context = ageContext();
  clinicalCase.observations = state.selected.map(makeObservation);
  clinicalCase.question_history = [];
  state.session = await api(`${sessionPath()}/case`, {
    method: "PUT",
    body: JSON.stringify({ revision: state.session.revision, clinical_case: clinicalCase }),
  });
  state.resultRun = null;
  state.questionRun = null;
  state.questionCount = 0;
  byId("nav-expert").href = `/expert?session=${encodeURIComponent(state.session.session_id)}`;
}

async function askNextQuestion() {
  const payload = await api(`${sessionPath()}/questions/next`, {
    method: "POST", body: JSON.stringify({ revision: state.session.revision }),
  });
  state.session = payload.session;
  state.questionRun = payload.run;
  if (payload.run.result.status === "question" && payload.run.result.question) {
    state.questionCount += 1;
    renderQuestion(payload.run.result.question);
    showScreen("question");
  } else {
    await diagnose();
  }
}

function renderQuestion(question) {
  byId("question-count").textContent = `Question ${state.questionCount} proposée par Latros`;
  byId("question-text").textContent = question.text;
  byId("question-summary").textContent = state.selected.map((item) => item.label).join(" · ");
  const allowed = new Set(question.allowed_answers || ["present", "absent", "unknown"]);
  document.querySelectorAll("[data-answer]").forEach((button) => {
    button.hidden = !allowed.has(button.dataset.answer);
  });
}

async function answerQuestion(answer) {
  if (!state.questionRun?.run_id) return;
  const accepted = await api(`${sessionPath()}/questions/answer`, {
    method: "POST",
    body: JSON.stringify({ revision: state.session.revision,
      question_run_id: state.questionRun.run_id, answer }),
  });
  state.session = accepted;
  await askNextQuestion();
}

async function diagnose() {
  const payload = await api(`${sessionPath()}/analyses`, {
    method: "POST", body: JSON.stringify({ revision: state.session.revision }),
  });
  state.session = payload.session;
  state.resultRun = payload.run;
  renderResults();
  showScreen("results");
}

function observationLabel(contribution) {
  const observation = (state.session?.clinical_case?.observations || [])
    .find((item) => item.observation_id === contribution.observation);
  return observation?.concept?.coding?.display || "Observation documentée";
}

function contributionLabels(items, max = 2) {
  const labels = [...new Set((items || []).map(observationLabel))].slice(0, max);
  return labels.map((label) => `<li>${escapeHtml(label)}</li>`).join("");
}

function renderResults() {
  const result = state.resultRun?.result;
  if (!result) return;
  const candidates = result.candidates || [];
  const alert = byId("result-alert");
  const unreviewed = Boolean(result.research_unreviewed);
  alert.hidden = false;
  alert.textContent = unreviewed
    ? "Connaissances non revues et urgences non évaluées. Ces résultats ne constituent ni un diagnostic ni un avis médical."
    : "Urgences non évaluées. Ces résultats ne constituent pas un diagnostic.";
  if (!candidates.length || result.abstention) {
    byId("result-intro").textContent = candidates.length
      ? "Latros s’abstient de conclure avec les informations disponibles."
      : "Aucune possibilité classée avec les informations disponibles.";
  } else {
    byId("result-intro").textContent = "Plusieurs possibilités correspondent aux informations fournies. Leur rang n’est pas une probabilité et ne tient pas compte de la fréquence des maladies.";
  }
  const visible = candidates.slice(0, state.visibleCount);
  byId("result-list").innerHTML = visible.map((candidate, index) => {
    const favorable = contributionLabels(candidate.favorable);
    const unfavorable = contributionLabels(candidate.unfavorable);
    return `<article class="result-card"><div class="result-heading">
      <span class="rank-badge" aria-label="Rang ${escapeHtml(candidate.rank || index + 1)}">${escapeHtml(candidate.rank || index + 1)}</span>
      <h2>${escapeHtml(candidate.label)}</h2></div>
      ${favorable ? `<ul aria-label="Éléments en faveur">${favorable}</ul>` : ""}
      ${unfavorable ? `<ul aria-label="Éléments contradictoires"><li>Contradiction :</li>${unfavorable}</ul>` : ""}
      <button type="button" class="text-link" data-detail-index="${index}">Voir pourquoi</button>
    </article>`;
  }).join("");
  byId("show-more-results").hidden = candidates.length <= state.visibleCount;
}

function detailList(items, empty) {
  return items?.length
    ? `<ul class="detail-list">${[...new Set(items.map(observationLabel))].map((label) => `<li>${escapeHtml(label)}</li>`).join("")}</ul>`
    : `<p>${escapeHtml(empty)}</p>`;
}

function unknownDetails(items) {
  if (!items?.length) return "<p>Aucune information manquante détaillée par le moteur.</p>";
  const known = items.filter((item) => observationLabel(item) !== "Observation documentée");
  return known.length
    ? detailList(known, "")
    : `<p>${items.length} élément(s) du modèle non évalué(s). Leur provenance est consultable dans les détails techniques.</p>`;
}

function sourceLabel(source) {
  const release = source.source_release_id || "";
  const names = { monarch: "Monarch Knowledge Graph", orphadata: "Orphadata",
    medlineplus: "MedlinePlus", hpo: "HPO", mondo: "Mondo", doid: "DOID" };
  const [id, version] = release.split(":", 2);
  return `${names[id] || id || "Source locale"}${version ? ` (${version})` : ""}`;
}

function openDetail(index) {
  const candidate = state.resultRun?.result?.candidates?.[index];
  if (!candidate) return;
  const result = state.resultRun.result;
  byId("dialog-title").textContent = `Pourquoi ${candidate.label} apparaît`;
  byId("dialog-content").innerHTML = `
    <p>Possibilité classée au rang ${escapeHtml(candidate.rank)} ; ce rang n’est pas une probabilité.</p>
    <section class="detail-section"><h3>Éléments en faveur</h3>
      ${detailList(candidate.favorable, "Aucun élément favorable retenu.")}</section>
    <section class="detail-section"><h3>Éléments contradictoires</h3>
      ${detailList(candidate.unfavorable, "Aucune contradiction retenue dans les observations évaluées.")}</section>
    <section class="detail-section"><h3>Informations non évaluées</h3>
      ${unknownDetails(candidate.unknown)}</section>
    <section class="detail-section"><h3>Sources principales</h3>
      ${candidate.source_views?.length
    ? `<ul class="detail-list">${candidate.source_views.map((source) => `<li>${escapeHtml(sourceLabel(source))}</li>`).join("")}</ul>`
    : "<p>Aucune source détaillée.</p>"}</section>
    <details class="technical-details"><summary>Afficher les détails techniques</summary>
      <p>Compatibilité brute non calibrée : ${escapeHtml(candidate.aggregate?.value)}. Ne pas interpréter comme un risque ou une probabilité.</p>
      <pre>${escapeHtml(JSON.stringify({ candidate, run_receipt: result.run_receipt,
    selection: state.session?.selection, research_unreviewed: result.research_unreviewed,
    safety: result.safety }, null, 2))}</pre>
    </details>`;
  byId("result-dialog").showModal();
}

function sessionLabels(session) {
  const answerIds = new Set((session.clinical_case?.question_history || [])
    .map((item) => item.resulting_observation_id));
  return (session.clinical_case?.observations || [])
    .filter((item) => item.clinical_status === "present" && !answerIds.has(item.observation_id))
    .map((item) => item.concept?.coding?.display || item.concept?.coding?.code)
    .filter(Boolean);
}

function isSimpleCompatible(session) {
  const clinicalCase = session.clinical_case || {};
  const answerIds = new Set((clinicalCase.question_history || [])
    .map((item) => item.resulting_observation_id));
  return session.selection?.strategy_id === "general_v1"
    && !clinicalCase.subject_context?.sex
    && !(clinicalCase.source_statements || []).length
    && !(clinicalCase.observation_proposals || []).length
    && (clinicalCase.observations || []).every((item) =>
      answerIds.has(item.observation_id)
      || (["symptom", "sign", "exam"].includes(item.kind)
        && item.clinical_status === "present"
        && item.evaluation_status === "assessed"
        && item.acquisition_method === "reported"
        && item.certainty === "asserted"
        && item.experiencer === "patient"
        && !item.value && !item.temporal && !item.severity
        && !item.body_site && !item.laterality && !item.supersedes));
}

function renderHistory() {
  byId("history-list").innerHTML = state.sessions.length
    ? state.sessions.map((session) => {
      const labels = sessionLabels(session);
      const date = new Date(session.updated_at).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });
      const action = isSimpleCompatible(session)
        ? `<button type="button" class="button button-secondary" data-resume-id="${escapeHtml(session.session_id)}">Reprendre</button>`
        : `<a class="button button-secondary" href="/expert?session=${encodeURIComponent(session.session_id)}">Ouvrir en mode expert</a>`;
      return `<article class="history-card"><div><h2>${escapeHtml(labels.join(", ") || session.display_name)}</h2>
        <p>${escapeHtml(date)} · conservé localement</p></div>
        ${action}</article>`;
    }).join("")
    : '<p>Aucune analyse enregistrée sur cet ordinateur.</p>';
}

async function openHistory() {
  const payload = await api("/internal/v1/sessions");
  state.sessions = payload.items || [];
  renderHistory();
  showScreen("history");
}

function selectedFromSession(session) {
  const answerIds = new Set((session.clinical_case?.question_history || [])
    .map((item) => item.resulting_observation_id));
  return (session.clinical_case?.observations || [])
    .filter((item) => item.clinical_status === "present" && !answerIds.has(item.observation_id))
    .map((item) => ({
      concept_id: item.concept.concept_id,
      system: item.concept.coding.system,
      code: item.concept.coding.code,
      label: item.concept.coding.display || item.concept.coding.code,
      observation_kind: item.kind,
    }));
}

async function resumeSession(sessionId) {
  const session = await api(`/internal/v1/sessions/${encodeURIComponent(sessionId)}`);
  if (!isSimpleCompatible(session) || !session.selection?.snapshot_id) {
    throw new Error("Cette session contient des données avancées. Ouvrez-la dans le mode expert.");
  }
  const available = (state.capabilities.compatible_selections || []).find((item) =>
    item.available && item.snapshot_id === session.selection.snapshot_id
    && item.strategy_id === session.selection.strategy_id);
  if (!available) throw new Error("Le snapshot de cette session n’est plus disponible localement.");
  state.session = session;
  state.selection = available;
  state.selected = selectedFromSession(session);
  state.visibleCount = 5;
  state.questionCount = session.clinical_case?.question_history?.length || 0;
  updateResearchNotice();
  renderSelected();
  byId("patient-age").value = session.clinical_case?.subject_context?.age?.value ?? "";
  const diagnoseIsCurrent = session.latest_diagnose
    && (!session.latest_question || new Date(session.latest_diagnose.created_at)
      >= new Date(session.latest_question.created_at));
  if (diagnoseIsCurrent) {
    state.resultRun = await api(`${sessionPath()}/runs/${encodeURIComponent(session.latest_diagnose.run_id)}`);
    renderResults();
    showScreen("results");
  } else if (session.latest_question) {
    state.questionRun = await api(`${sessionPath()}/runs/${encodeURIComponent(session.latest_question.run_id)}`);
    const question = state.questionRun.result.question;
    const answered = (session.clinical_case?.question_history || [])
      .some((item) => item.question_id === question?.question_id);
    if (question && !answered) {
      state.questionCount += 1;
      renderQuestion(question);
      showScreen("question");
    } else {
      await askNextQuestion();
    }
  } else {
    showScreen("home");
  }
}

function newAnalysis() {
  state.session = null;
  state.resultRun = null;
  state.questionRun = null;
  state.selected = [];
  state.suggestions = [];
  state.visibleCount = 5;
  state.questionCount = 0;
  state.selection = preferredSelection(state.capabilities);
  byId("patient-age").value = "";
  byId("symptom-search").value = "";
  updateResearchNotice();
  renderSelected();
  renderSuggestions();
  showScreen("home");
}

byId("symptom-search").addEventListener("input", () => {
  window.clearTimeout(state.searchTimer);
  state.searchTimer = window.setTimeout(searchConcepts, 220);
});
byId("symptom-search").addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    byId("symptom-suggestions").hidden = true;
    byId("symptom-search").setAttribute("aria-expanded", "false");
  }
  if (event.key === "ArrowDown") {
    const first = byId("symptom-suggestions").querySelector("button");
    if (first) { first.focus(); event.preventDefault(); }
  }
});
byId("symptom-suggestions").addEventListener("click", (event) => {
  const button = event.target.closest("[data-suggestion-index]");
  if (button) selectSuggestion(Number(button.dataset.suggestionIndex));
});
byId("selected-symptoms").addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-index]");
  if (!button) return;
  state.selected.splice(Number(button.dataset.removeIndex), 1);
  renderSelected();
});
byId("home-continue").addEventListener("click", () => { notice(""); showScreen("age"); });
byId("age-continue").addEventListener("click", () => guarded(async () => {
  await ensureSession();
  await askNextQuestion();
}, "Préparation des questions locales…"));
byId("age-skip").addEventListener("click", () => guarded(async () => {
  byId("patient-age").value = "";
  await ensureSession();
  await askNextQuestion();
}, "Préparation des questions locales…"));
document.querySelectorAll("[data-answer]").forEach((button) => {
  button.addEventListener("click", () => guarded(() => answerQuestion(button.dataset.answer), "Analyse de la réponse…"));
});
byId("question-to-results").addEventListener("click", () => guarded(diagnose, "Calcul des possibilités…"));
byId("result-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-detail-index]");
  if (button) openDetail(Number(button.dataset.detailIndex));
});
byId("show-more-results").addEventListener("click", () => {
  state.visibleCount += 5;
  renderResults();
});
byId("close-dialog").addEventListener("click", () => byId("result-dialog").close());
byId("results-new").addEventListener("click", newAnalysis);
byId("results-edit").addEventListener("click", () => { notice(""); showScreen("home"); });
byId("results-history").addEventListener("click", () => guarded(openHistory));
byId("nav-history").addEventListener("click", () => guarded(openHistory));
byId("history-new").addEventListener("click", newAnalysis);
byId("history-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-resume-id]");
  if (button) guarded(() => resumeSession(button.dataset.resumeId), "Ouverture de l’analyse locale…");
});
document.querySelectorAll("[data-back]").forEach((button) => {
  button.addEventListener("click", () => { notice(""); showScreen(button.dataset.back); });
});
byId("retry-boot").addEventListener("click", boot);

boot();
