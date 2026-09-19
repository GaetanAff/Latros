"use strict";

const state = {
  capabilities: null,
  sessions: [],
  session: null,
  selectedConcept: null,
  resultRun: null,
  questionRun: null,
};

const byId = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.message || `Erreur HTTP ${response.status}`);
  }
  return payload;
}

function showToast(message, error = false) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.classList.toggle("error", error);
  toast.classList.add("visible");
  window.setTimeout(() => toast.classList.remove("visible"), 3400);
}

function setBusy(busy) {
  ["run-analysis", "next-question", "save-case", "apply-selection", "add-observation"]
    .forEach((id) => { byId(id).disabled = busy; });
}

function compatibleSelections() {
  return (state.capabilities?.compatible_selections || []).filter((item) => item.available);
}

function snapshotById(snapshotId) {
  return (state.capabilities?.snapshots || []).find((item) => item.snapshot_id === snapshotId);
}

async function boot() {
  try {
    state.capabilities = await api("/internal/v1/capabilities");
    const sessionPayload = await api("/internal/v1/sessions");
    state.sessions = sessionPayload.items;
    if (!state.sessions.length) {
      state.session = await api("/internal/v1/sessions", {
        method: "POST",
        body: JSON.stringify({ display_name: "Session R&D 1" }),
      });
    } else {
      state.session = state.sessions[0];
    }
    await refreshSessions();
    populateSelectionControls();
    renderSession();
    await loadLatestRuns();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshSessions() {
  const payload = await api("/internal/v1/sessions");
  state.sessions = payload.items;
  const select = byId("session-select");
  select.innerHTML = state.sessions.map((item) => (
    `<option value="${escapeHtml(item.session_id)}">${escapeHtml(item.display_name)} · r${item.revision}</option>`
  )).join("");
  if (state.session) select.value = state.session.session_id;
}

function populateSelectionControls() {
  const selections = compatibleSelections();
  const snapshots = state.capabilities.snapshots;
  const snapshotSelect = byId("snapshot-select");
  snapshotSelect.innerHTML = snapshots.map((snapshot) => {
    const available = selections.some((item) => item.snapshot_id === snapshot.snapshot_id);
    return `<option value="${escapeHtml(snapshot.snapshot_id)}" ${available ? "" : "disabled"}>${escapeHtml(snapshot.snapshot_id)} · ${escapeHtml(snapshot.runtime_status)}</option>`;
  }).join("");
  const availableSnapshots = selections.map((item) => item.snapshot_id);
  if (state.session?.selection && availableSnapshots.includes(state.session.selection.snapshot_id)) {
    snapshotSelect.value = state.session.selection.snapshot_id;
  } else if (availableSnapshots.length) {
    snapshotSelect.value = availableSnapshots[0];
  }
  populateStrategies();
}

function populateStrategies() {
  const snapshot = byId("snapshot-select").value;
  const strategies = compatibleSelections().filter((item) => item.snapshot_id === snapshot);
  const strategySelect = byId("strategy-select");
  strategySelect.innerHTML = strategies.map((item) => (
    `<option value="${escapeHtml(item.strategy_id)}">${escapeHtml(item.strategy_id)}</option>`
  )).join("");
  if (state.session?.selection?.snapshot_id === snapshot) {
    strategySelect.value = state.session.selection.strategy_id;
  }
  byId("apply-selection").disabled = strategies.length === 0;
  renderSnapshotStatus(snapshot);
}

function renderSnapshotStatus(snapshotId) {
  const snapshot = snapshotById(snapshotId);
  const panel = byId("snapshot-status");
  if (!snapshot) {
    panel.textContent = "Aucun snapshot compatible disponible.";
    return;
  }
  panel.classList.toggle("validation-unreviewed", snapshot.research_unreviewed);
  panel.innerHTML = `
    <strong>${escapeHtml(snapshot.snapshot_id)}</strong><br>
    Runtime : ${escapeHtml(snapshot.runtime_status)}<br>
    Validation : ${escapeHtml(snapshot.validation_status || "non déclarée")}<br>
    Usage : ${escapeHtml(snapshot.intended_use || "recherche locale")}<br>
    Publiable : ${snapshot.publishable === true ? "oui" : "non"}
  `;
}

function renderSession() {
  if (!state.session) return;
  byId("save-status").textContent = `Sauvegarde locale · révision ${state.session.revision} · aucun envoi réseau`;
  const context = state.session.clinical_case.subject_context || {};
  const age = context.age;
  byId("age-input").value = age?.kind === "quantity" ? age.value : "";
  byId("sex-select").value = context.sex || "";
  renderObservations();
  if (state.session.selection) {
    byId("snapshot-select").value = state.session.selection.snapshot_id;
    populateStrategies();
    byId("strategy-select").value = state.session.selection.strategy_id;
  }
  renderValidation();
}

function renderObservations() {
  const allObservations = state.session?.clinical_case?.observations || [];
  const superseded = new Set(allObservations.map((item) => item.supersedes).filter(Boolean));
  const observations = allObservations.filter((item) => !superseded.has(item.observation_id));
  const labels = {
    present: "présent / évalué",
    absent: "absent / évalué",
    assessed: "inconnu / évalué",
    not_assessed: "non évalué",
    unable_to_assess: "impossible à évaluer",
  };
  byId("observation-list").innerHTML = observations.length ? observations.map((item) => {
    const stateLabel = item.clinical_status === "unknown" ? labels[item.evaluation_status] : labels[item.clinical_status];
    return `<div class="observation-item">
      <div><strong>${escapeHtml(item.concept.coding.display || item.concept.coding.code)}</strong><br>
      <span class="muted">${escapeHtml(item.kind)} · ${escapeHtml(stateLabel)}</span></div>
      <button type="button" data-remove-observation="${escapeHtml(item.observation_id)}" aria-label="Retirer">×</button>
    </div>`;
  }).join("") : '<p class="hint">Aucune observation confirmée.</p>';
}

function renderValidation(result = state.resultRun?.result) {
  const panel = byId("validation-panel");
  const content = byId("validation-content");
  const snapshot = snapshotById(state.session?.selection?.snapshot_id);
  const receipt = result?.run_receipt;
  const unreviewed = Boolean(result?.research_unreviewed || snapshot?.research_unreviewed);
  panel.classList.toggle("validation-unreviewed", unreviewed);
  if (unreviewed) {
    content.innerHTML = `
      <strong>DONNÉES NON REVUES — RECHERCHE LOCALE UNIQUEMENT</strong>
      <div class="code">research_unreviewed: true</div>
      <div class="code">clinical_validation: false</div>
      <div class="code">publishable: false</div>
      <p>${escapeHtml(receipt?.unreviewed_assertion_count ?? snapshot?.unreviewed_assertion_count ?? 0)} assertions non revues ·
      ${escapeHtml(receipt?.unreviewed_mapping_count ?? snapshot?.unreviewed_mapping_count ?? 0)} mappings non revus</p>
    `;
  } else if (snapshot) {
    content.innerHTML = `<strong>${escapeHtml(snapshot.validation_status || "Statut non déclaré")}</strong>`;
  } else {
    content.textContent = "Aucun snapshot sélectionné.";
  }
}

async function newSession() {
  const count = state.sessions.length + 1;
  state.session = await api("/internal/v1/sessions", {
    method: "POST",
    body: JSON.stringify({ display_name: `Session R&D ${count}` }),
  });
  state.resultRun = null;
  state.questionRun = null;
  await refreshSessions();
  populateSelectionControls();
  renderSession();
  resetResults();
}

async function loadSession(sessionId) {
  state.session = await api(`/internal/v1/sessions/${encodeURIComponent(sessionId)}`);
  state.resultRun = null;
  state.questionRun = null;
  populateSelectionControls();
  renderSession();
  resetResults();
  await loadLatestRuns();
}

async function loadLatestRuns() {
  if (state.session?.latest_diagnose) {
    state.resultRun = await api(`/internal/v1/sessions/${encodeURIComponent(state.session.session_id)}/runs/${encodeURIComponent(state.session.latest_diagnose.run_id)}`);
    renderResult(state.resultRun.result);
  }
  if (state.session?.latest_question) {
    state.questionRun = await api(`/internal/v1/sessions/${encodeURIComponent(state.session.session_id)}/runs/${encodeURIComponent(state.session.latest_question.run_id)}`);
    renderQuestion(state.questionRun.result);
  }
}

async function applySelection() {
  const snapshotId = byId("snapshot-select").value;
  const strategyId = byId("strategy-select").value;
  state.session = await api(`/internal/v1/sessions/${encodeURIComponent(state.session.session_id)}/selection`, {
    method: "PUT",
    body: JSON.stringify({ revision: state.session.revision, snapshot_id: snapshotId, strategy_id: strategyId }),
  });
  state.selectedConcept = null;
  byId("selected-concept").textContent = "Aucun concept sélectionné";
  byId("concept-results").innerHTML = "";
  renderSession();
  await refreshSessions();
  showToast("Sélection compatible enregistrée.");
}

function caseFromForm() {
  const clinicalCase = structuredClone(state.session.clinical_case);
  const ageValue = byId("age-input").value.trim();
  const sex = byId("sex-select").value;
  clinicalCase.subject_context = {};
  if (ageValue !== "") {
    const parsed = Number(ageValue);
    if (!Number.isFinite(parsed) || parsed < 0) throw new Error("Âge invalide.");
    clinicalCase.subject_context.age = {
      kind: "quantity", value: parsed, comparator: "eq", unit: "year",
      system: "http://unitsofmeasure.org", code: "a",
    };
  }
  if (sex) clinicalCase.subject_context.sex = sex;
  return clinicalCase;
}

async function saveCase() {
  state.session = await api(`/internal/v1/sessions/${encodeURIComponent(state.session.session_id)}/case`, {
    method: "PUT",
    body: JSON.stringify({ revision: state.session.revision, clinical_case: caseFromForm() }),
  });
  renderSession();
  await refreshSessions();
  showToast("ClinicalCaseV2 sauvegardé localement.");
}

async function searchConcepts() {
  if (!state.session.selection) throw new Error("Appliquez d’abord un moteur et un snapshot.");
  const query = byId("concept-query").value;
  const selection = state.session.selection;
  const params = new URLSearchParams({ snapshot: selection.snapshot_id, strategy: selection.strategy_id, q: query, limit: "20" });
  const payload = await api(`/internal/v1/concepts?${params.toString()}`);
  byId("concept-results").innerHTML = payload.items.length ? payload.items.map((item, index) => (
    `<button type="button" class="concept-option" data-concept-index="${index}">
      ${escapeHtml(item.label)}<small>${escapeHtml(item.code)} · ${escapeHtml(item.observation_kind)}</small>
    </button>`
  )).join("") : '<p class="hint">Aucun concept compatible.</p>';
  byId("concept-results").dataset.items = JSON.stringify(payload.items);
}

async function addObservation() {
  if (!state.selectedConcept) throw new Error("Sélectionnez un concept du snapshot.");
  const axes = {
    present: ["present", "assessed", null],
    absent: ["absent", "assessed", null],
    unknown: ["unknown", "assessed", "unknown_to_subject"],
    not_assessed: ["unknown", "not_assessed", "not_asked"],
    unable_to_assess: ["unknown", "unable_to_assess", "unable_to_assess"],
  }[byId("observation-state").value];
  const concept = state.selectedConcept;
  const observation = {
    kind: concept.observation_kind,
    observation_id: `observation-${crypto.randomUUID()}`,
    concept: {
      concept_id: concept.concept_id,
      coding: { system: concept.system, code: concept.code, display: concept.label },
    },
    clinical_status: axes[0],
    evaluation_status: axes[1],
    uncertainty_reason: axes[2],
    acquisition_method: "reported",
    provenance: { provenance_id: `provenance-${crypto.randomUUID()}`, origin_type: "patient_report" },
  };
  const clinicalCase = caseFromForm();
  clinicalCase.observations.push(observation);
  state.session = await api(`/internal/v1/sessions/${encodeURIComponent(state.session.session_id)}/case`, {
    method: "PUT",
    body: JSON.stringify({ revision: state.session.revision, clinical_case: clinicalCase }),
  });
  state.selectedConcept = null;
  byId("selected-concept").textContent = "Aucun concept sélectionné";
  byId("concept-results").innerHTML = "";
  renderSession();
  await refreshSessions();
}

async function removeObservation(observationId) {
  const clinicalCase = caseFromForm();
  clinicalCase.observations = clinicalCase.observations.filter((item) => item.observation_id !== observationId && item.supersedes !== observationId);
  clinicalCase.question_history = clinicalCase.question_history.filter((item) => item.resulting_observation_id !== observationId);
  state.session = await api(`/internal/v1/sessions/${encodeURIComponent(state.session.session_id)}/case`, {
    method: "PUT",
    body: JSON.stringify({ revision: state.session.revision, clinical_case: clinicalCase }),
  });
  renderSession();
  await refreshSessions();
}

async function runAnalysis() {
  if (!state.session.selection) throw new Error("Appliquez un moteur et un snapshot.");
  await saveCase();
  const payload = await api(`/internal/v1/sessions/${encodeURIComponent(state.session.session_id)}/analyses`, {
    method: "POST",
    body: JSON.stringify({ revision: state.session.revision }),
  });
  state.session = payload.session;
  state.resultRun = payload.run;
  renderSession();
  renderResult(payload.run.result);
  await refreshSessions();
}

async function askNextQuestion() {
  if (!state.session.selection) throw new Error("Appliquez un moteur et un snapshot.");
  await saveCase();
  const payload = await api(`/internal/v1/sessions/${encodeURIComponent(state.session.session_id)}/questions/next`, {
    method: "POST",
    body: JSON.stringify({ revision: state.session.revision }),
  });
  state.session = payload.session;
  state.questionRun = payload.run;
  renderSession();
  renderQuestion(payload.run.result);
  await refreshSessions();
}

async function answerQuestion(answer) {
  if (!state.questionRun) return;
  state.session = await api(`/internal/v1/sessions/${encodeURIComponent(state.session.session_id)}/questions/answer`, {
    method: "POST",
    body: JSON.stringify({ revision: state.session.revision, question_run_id: state.questionRun.run_id, answer }),
  });
  renderSession();
  await refreshSessions();
  showToast("Réponse enregistrée comme observation confirmée.");
}

function renderResult(result) {
  byId("safety-status").textContent = result.safety?.status || "not_evaluated";
  renderValidation(result);
  const coverage = result.coverage || {};
  const receipt = result.run_receipt || {};
  byId("run-meta").innerHTML = `${escapeHtml(receipt.snapshot_id)}<br>${escapeHtml(receipt.strategy_id)} · ${escapeHtml(receipt.profile_id)}`;
  let summary = `<div class="summary-grid">
    <div class="metric"><span>Statut</span><strong>${escapeHtml(result.status)}</strong></div>
    <div class="metric"><span>Périmètre</span><strong>${escapeHtml(result.scope_status)}</strong></div>
    <div class="metric"><span>Couverture</span><strong>${escapeHtml(Number(coverage.coverage_ratio || 0).toFixed(2))}</strong></div>
    <div class="metric"><span>Observations</span><strong>${escapeHtml(coverage.supported_observation_count || 0)} / ${escapeHtml(coverage.confirmed_observation_count || 0)}</strong></div>
  </div>`;
  if (result.abstention) {
    summary += `<div class="abstention"><strong>Abstention : ${escapeHtml(result.abstention.reason)}</strong><br>${escapeHtml(result.abstention.explanation)}</div>`;
  }
  const inputs = coverage.inputs || [];
  if (inputs.length) {
    summary += `<div class="details-section"><strong>Entrées utilisées ou ignorées</strong>${inputs.map((item) => (
      `<div class="contribution ${item.disposition === "used" ? "favorable" : "unknown"}">${escapeHtml(item.input_id)} · ${escapeHtml(item.disposition)} · ${escapeHtml(item.reason)}</div>`
    )).join("")}</div>`;
  }
  summary += `<details class="details-section"><summary><strong>Reçu d’exécution reproductible</strong></summary><pre class="code">${escapeHtml(JSON.stringify(receipt, null, 2))}</pre></details>`;
  byId("result-summary").className = "";
  byId("result-summary").innerHTML = summary;
  byId("candidate-list").innerHTML = (result.candidates || []).map((candidate, index) => (
    `<button type="button" class="candidate-card" data-candidate-index="${index}">
      <span class="rank">${escapeHtml(candidate.rank)}</span>
      <span><strong>${escapeHtml(candidate.label)}</strong><br><small class="muted">${escapeHtml(candidate.candidate_id)}</small></span>
      <span class="score"><strong>${escapeHtml(candidate.aggregate.value)}</strong><small>${escapeHtml(candidate.aggregate.scale_id)}<br>compatibilité non calibrée</small></span>
    </button>`
  )).join("");
  if (result.candidates?.length) renderCandidate(result.candidates[0], 0);
  else byId("candidate-details").innerHTML = '<div class="empty-state">Aucun candidat : le moteur s’est abstenu.</div>';
}

function renderCandidate(candidate, index) {
  document.querySelectorAll(".candidate-card").forEach((element, candidateIndex) => element.classList.toggle("selected", candidateIndex === index));
  const contributionBlock = (title, items, direction) => `
    <div class="details-section"><h3>${title} (${items.length})</h3>${items.length ? items.map((item) => (
      `<div class="contribution ${direction}"><strong>${escapeHtml(item.finding)}</strong><br>
      observation ${escapeHtml(item.observation)} · valeur ${item.value === null ? "inconnue" : escapeHtml(item.value)}<br>
      ${escapeHtml(item.reason)}<br><span class="code">assertion: ${escapeHtml((item.assertion_ids || []).join(", "))}</span><br>
      <span class="code">source: ${escapeHtml(item.source_release_id)} · famille: ${escapeHtml(item.evidence_family_id)}</span>
      <details><summary>Provenance</summary><pre class="code">${escapeHtml(JSON.stringify(item.provenance || [], null, 2))}</pre></details></div>`
    )).join("") : '<p class="hint">Aucune contribution.</p>'}</div>`;
  byId("candidate-details").innerHTML = `
    <h3>#${escapeHtml(candidate.rank)} ${escapeHtml(candidate.label)}</h3>
    <div class="status-card"><strong>${escapeHtml(candidate.aggregate.value)}</strong> · ${escapeHtml(candidate.aggregate.scale_id)}<br>
    <span class="muted">Type : ${escapeHtml(candidate.aggregate.kind)} · calibré : ${candidate.aggregate.calibrated ? "oui" : "non"}</span></div>
    ${contributionBlock("Arguments favorables", candidate.favorable || [], "favorable")}
    ${contributionBlock("Arguments défavorables / contradictions", candidate.unfavorable || [], "unfavorable")}
    ${contributionBlock("Informations importantes inconnues", candidate.unknown || [], "unknown")}
    <div class="details-section"><h3>Sources et familles</h3>${(candidate.source_views || []).map((item) => (
      `<div class="contribution"><span class="code">${escapeHtml(item.source_release_id)}</span><br>
      Familles : ${escapeHtml((item.evidence_family_ids || []).join(", "))}<br>
      Sous-total : ${escapeHtml(item.subtotal)} · ${escapeHtml(item.scale_id)}</div>`
    )).join("") || '<p class="hint">Aucune source utilisée.</p>'}</div>
    <div class="details-section"><h3>Mappings</h3><p class="code">${escapeHtml((candidate.terminology_mappings || []).join(", ") || "aucun")}</p></div>
    <div class="details-section"><h3>Contradictions de fréquence</h3><p class="code">${escapeHtml((candidate.frequency_conflicts || []).join(", ") || "aucune")}</p></div>
  `;
}

function renderQuestion(result) {
  renderValidation(result);
  if (result.status === "stopped" || !result.question) {
    byId("question-panel").className = "abstention";
    byId("question-panel").innerHTML = `<strong>Interrogatoire arrêté</strong><br>${escapeHtml(result.stop_reason || "no_question")}`;
    return;
  }
  const question = result.question;
  const answers = [
    ["present", "Présent"], ["absent", "Absent"], ["unknown", "Je ne sais pas"],
    ["not_assessed", "Non évalué"], ["unable_to_assess", "Impossible à évaluer"],
  ];
  byId("question-panel").className = "question-box";
  byId("question-panel").innerHTML = `
    <strong>${escapeHtml(question.text)}</strong>
    <p>${escapeHtml(question.justification)}</p>
    <p class="code">${escapeHtml(question.concept.code)} · assertions ${escapeHtml((question.assertion_ids || []).join(", "))}</p>
    <div class="answer-buttons">${answers.map(([value, label]) => `<button type="button" data-question-answer="${value}">${label}</button>`).join("")}</div>
  `;
}

function resetResults() {
  byId("result-summary").className = "empty-state";
  byId("result-summary").textContent = "Lancez une analyse pour inspecter couverture, abstention et candidats.";
  byId("candidate-list").innerHTML = "";
  byId("candidate-details").className = "empty-state";
  byId("candidate-details").textContent = "Sélectionnez un candidat pour examiner ses contributions et sa provenance.";
  byId("question-panel").className = "empty-state";
  byId("question-panel").textContent = "Aucune question demandée.";
  byId("run-meta").textContent = "";
  byId("safety-status").textContent = "not_evaluated";
}

function guarded(action) {
  return async (...args) => {
    setBusy(true);
    try { await action(...args); }
    catch (error) { showToast(error.message, true); }
    finally { setBusy(false); }
  };
}

byId("theme-toggle").addEventListener("click", () => {
  const dark = document.documentElement.dataset.theme === "dark";
  document.documentElement.dataset.theme = dark ? "light" : "dark";
  localStorage.setItem("latros-ui-theme", dark ? "light" : "dark");
});
document.documentElement.dataset.theme = localStorage.getItem("latros-ui-theme") || "light";
byId("new-session").addEventListener("click", guarded(newSession));
byId("session-select").addEventListener("change", (event) => guarded(loadSession)(event.target.value));
byId("snapshot-select").addEventListener("change", populateStrategies);
byId("apply-selection").addEventListener("click", guarded(applySelection));
byId("save-case").addEventListener("click", guarded(saveCase));
byId("concept-search").addEventListener("click", guarded(searchConcepts));
byId("concept-query").addEventListener("keydown", (event) => { if (event.key === "Enter") guarded(searchConcepts)(); });
byId("concept-results").addEventListener("click", (event) => {
  const button = event.target.closest("[data-concept-index]");
  if (!button) return;
  const items = JSON.parse(byId("concept-results").dataset.items || "[]");
  state.selectedConcept = items[Number(button.dataset.conceptIndex)];
  byId("selected-concept").textContent = `${state.selectedConcept.label} · ${state.selectedConcept.code} · ${state.selectedConcept.observation_kind}`;
});
byId("add-observation").addEventListener("click", guarded(addObservation));
byId("observation-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-observation]");
  if (button) guarded(removeObservation)(button.dataset.removeObservation);
});
byId("run-analysis").addEventListener("click", guarded(runAnalysis));
byId("next-question").addEventListener("click", guarded(askNextQuestion));
byId("candidate-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-candidate-index]");
  if (!button || !state.resultRun) return;
  const index = Number(button.dataset.candidateIndex);
  renderCandidate(state.resultRun.result.candidates[index], index);
});
byId("question-panel").addEventListener("click", (event) => {
  const button = event.target.closest("[data-question-answer]");
  if (button) guarded(answerQuestion)(button.dataset.questionAnswer);
});

boot();
