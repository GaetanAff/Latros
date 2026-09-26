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
  displayLabels: {},
  screen: 'home',
  bootErrorKey: 'service_unavailable',
};

const byId = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");
const t = (key, values = {}) => window.LatrosI18n.t(key, values);
const locale = () => window.LatrosI18n.language;
const sessionPath = () => `/internal/v1/sessions/${encodeURIComponent(state.session.session_id)}`;

async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  }); } catch { throw new Error(t("service_unavailable")); }
  let payload;
  try { payload = await response.json(); }
  catch { throw new Error(t("unreadable")); }
  if (!response.ok) throw new Error(t("http_error", {status: response.status, message: payload.message || payload.error || ""}));
  return payload;
}

function notice(message) {
  byId("app-message").textContent = message;
  byId("app-message").hidden = !message;
}

function setBusy(busy, message = t("loading")) {
  state.busy = busy;
  window.clearTimeout(state.busyTimer);
  byId("loading-text").textContent = message;
  byId("loading-layer").hidden = !busy;
  byId("app-shell").setAttribute("aria-busy", String(busy));
  if (busy) {
    state.busyTimer = window.setTimeout(() => {
      byId("loading-text").textContent = t("slow");
    }, 15000);
  }
}

async function guarded(action, message = t("loading")) {
  if (state.busy) return;
  notice("");
  setBusy(true, message);
  try { await action(); }
  catch (error) { notice(error.message || t("local_error")); }
  finally { setBusy(false); }
}

function showScreen(name) {
  state.screen = name;
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
    ? t("research_unreviewed")
    : t("research");
}

async function boot() {
  state.bootErrorKey = "service_unavailable";
  notice("");
  setBusy(true, t("opening"));
  try {
    state.capabilities = await api("/internal/v1/capabilities");
    state.selection = preferredSelection(state.capabilities);
    if (!state.selection) {
      state.bootErrorKey = "no_snapshot";
      throw new Error(t("no_snapshot"));
    }
    updateResearchNotice();
    const payload = await api("/internal/v1/sessions");
    state.sessions = payload.items || [];
    await refreshDisplayLabels();
    renderHistory();
    showScreen("home");
  } catch (error) {
    byId("error-text").textContent = t(state.bootErrorKey);
    byId("error-text").title = error.message || "";
    showScreen("error");
  } finally { setBusy(false); }
}

function renderSelected() {
  byId("selected-symptoms").innerHTML = state.selected.map((item, index) => `
    <span class="chip"><span>${escapeHtml(displayLabel(item.concept_id, item.label))}</span>
      <button type="button" data-remove-index="${index}" aria-label="${escapeHtml(t("remove", {label: displayLabel(item.concept_id, item.label)}))}">×</button>
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
        ${escapeHtml(item.display_label || item.label)}${item.fallback_english ? " [EN]" : ""}
      </button>`).join("")
    : `<div class="suggestion-empty">${escapeHtml(t("no_concept"))}</div>`;
  panel.hidden = false;
  byId("symptom-search").setAttribute("aria-expanded", "true");
}

async function searchConcepts() {
  const query = byId("symptom-search").value.trim();
  const sequence = ++state.searchSequence;
  if (query.length < 2) {
    state.suggestions = [];
    renderSuggestions();
    byId("search-hint").textContent = t("search_hint");
    return;
  }
  byId("search-hint").textContent = t("searching");
  const params = new URLSearchParams({
    snapshot: state.selection.snapshot_id,
    strategy: state.selection.strategy_id,
    q: query,
    limit: "12",
    language: locale(),
  });
  try {
    const payload = await api(`/internal/v1/presentation/concepts?${params}`);
    if (sequence !== state.searchSequence) return;
    state.suggestions = payload.items || [];
    renderSuggestions();
    byId("search-hint").textContent = state.suggestions.length
      ? t("choose") : t("try_wording");
  } catch (error) {
    if (sequence !== state.searchSequence) return;
    state.suggestions = [];
    renderSuggestions();
    byId("search-hint").textContent = t("search_unavailable");
    notice(error.message);
  }
}

function selectSuggestion(index) {
  const item = state.suggestions[index];
  if (!item) return;
  if (!state.selected.some((selected) => selected.concept_id === item.concept_id)) {
    state.selected.push(item);
    state.displayLabels[item.concept_id] = item;
  }
  byId("symptom-search").value = "";
  state.suggestions = [];
  ++state.searchSequence;
  renderSuggestions();
  renderSelected();
  byId("search-hint").textContent = t("added");
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
    throw new Error(t("age_error"));
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
      || t("new_analysis");
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
    await renderQuestion(payload.run.result.question);
    showScreen("question");
  } else {
    await diagnose();
  }
}

async function renderQuestion(question) {
  byId("question-count").textContent = t("question_count", {count: state.questionCount});
  const params = new URLSearchParams({snapshot: state.selection.snapshot_id, strategy: state.selection.strategy_id,
    system: question.concept.system, code: question.concept.code, language: locale()});
  let display;
  try { display = await api("/internal/v1/presentation/question?" + params); } catch { display = {}; }
  byId("question-text").textContent = display.question_text || question.text;
  byId("question-fallback").hidden = !display.fallback_english && Boolean(display.question_text);
  byId("question-fallback").textContent = t("english_fallback");
  byId("question-source").textContent = question.question_id + " · " + question.concept.code + " — " + question.concept.label + "\n" + question.text;
  byId("question-summary").textContent = state.selected.map((item) => displayLabel(item.concept_id, item.label)).join(" · ");
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
  const payload = await api(`${sessionPath()}/analyses?view=summary`, {
    method: "POST", body: JSON.stringify({ revision: state.session.revision }),
  });
  state.session = payload.session;
  state.resultRun = payload.run;
  await refreshDisplayLabels();
  renderResults();
  showScreen("results");
}

function observationLabel(contribution) {
  const observation = (state.session?.clinical_case?.observations || [])
    .find((item) => item.observation_id === contribution.observation);
  return observation ? displayLabel(observation.concept?.concept_id, observation.concept?.coding?.display || observation.concept?.coding?.code) : t("documented");
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
    ? t("result_warning_unreviewed")
    : t("result_warning");
  if (!candidates.length || result.abstention) {
    byId("result-intro").textContent = candidates.length
      ? t("abstention")
      : t("no_results");
  } else {
    byId("result-intro").textContent = t("result_intro");
  }
  const visible = candidates.slice(0, state.visibleCount);
  byId("result-list").innerHTML = visible.map((candidate, index) => {
    const favorable = contributionLabels(candidate.favorable);
    const unfavorable = contributionLabels(candidate.unfavorable);
    return `<article class="result-card"><div class="result-heading">
      <span class="rank-badge" aria-label="${escapeHtml(t("rank", {rank: candidate.rank || index + 1}))}">${escapeHtml(candidate.rank || index + 1)}</span>
      <h2>${escapeHtml(displayLabel(candidate.candidate_id, candidate.label))}</h2></div>
      ${favorable ? `<ul aria-label="${escapeHtml(t("favorable"))}">${favorable}</ul>` : ""}
      ${unfavorable ? `<ul aria-label="${escapeHtml(t("unfavorable"))}"><li>${escapeHtml(t("contradiction"))}</li>${unfavorable}</ul>` : ""}
      <button type="button" class="text-link" data-detail-index="${index}">${escapeHtml(t("see_why"))}</button>
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
  if (!items?.length) return `<p>${escapeHtml(t("no_missing"))}</p>`;
  const known = items.filter((item) => observationLabel(item) !== t("documented"));
  return known.length
    ? detailList(known, "")
    : `<p>${escapeHtml(t("missing_count", {count: items.length}))}</p>`;
}

function sourceLabel(source) {
  const release = source.source_release_id || "";
  const names = { monarch: "Monarch Knowledge Graph", orphadata: "Orphadata",
    medlineplus: "MedlinePlus", hpo: "HPO", mondo: "Mondo", doid: "DOID" };
  const [id, version] = release.split(":", 2);
  return `${names[id] || id || t("local_source")}${version ? ` (${version})` : ""}`;
}

async function openDetail(index) {
  const selected = state.resultRun?.result?.candidates?.[index];
  if (!selected) return;
  const detail = await api(`${sessionPath()}/runs/${encodeURIComponent(state.resultRun.run_id)}`
    + `/candidates/${encodeURIComponent(selected.candidate_id)}`);
  const candidate = detail.candidate;
  byId("dialog-title").textContent = t("why_candidate", {label: displayLabel(candidate.candidate_id, candidate.label)});
  byId("dialog-content").innerHTML = `
    <p>${escapeHtml(t("rank_notice", {rank: candidate.rank}))}</p>
    <section class="detail-section"><h3>${escapeHtml(t("favorable"))}</h3>
      ${detailList(candidate.favorable, t("no_favorable"))}</section>
    <section class="detail-section"><h3>${escapeHtml(t("unfavorable"))}</h3>
      ${detailList(candidate.unfavorable, t("no_contradiction"))}</section>
    <section class="detail-section"><h3>${escapeHtml(t("not_evaluated"))}</h3>
      ${unknownDetails(candidate.unknown)}</section>
    <section class="detail-section"><h3>${escapeHtml(t("sources"))}</h3>
      ${candidate.source_views?.length
    ? `<ul class="detail-list">${candidate.source_views.map((source) => `<li>${escapeHtml(sourceLabel(source))}</li>`).join("")}</ul>`
    : `<p>${escapeHtml(t("no_sources"))}</p>`}</section>
    <details class="technical-details"><summary>${escapeHtml(t("technical"))}</summary>
      <p>${escapeHtml(t("raw_score", {score: candidate.aggregate?.value}))}</p>
      <pre>${escapeHtml(JSON.stringify(detail, null, 2))}</pre>
    </details>`;
  byId("result-dialog").showModal();
}

function sessionLabels(session) {
  const answerIds = new Set((session.clinical_case?.question_history || [])
    .map((item) => item.resulting_observation_id));
  return (session.clinical_case?.observations || [])
    .filter((item) => item.clinical_status === "present" && !answerIds.has(item.observation_id))
    .map((item) => displayLabel(item.concept?.concept_id, item.concept?.coding?.display || item.concept?.coding?.code))
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
      const date = new Date(session.updated_at).toLocaleString({fr:"fr-FR",de:"de-DE",en:"en-GB"}[locale()], { dateStyle: "medium", timeStyle: "short" });
      const action = isSimpleCompatible(session)
        ? `<button type="button" class="button button-secondary" data-resume-id="${escapeHtml(session.session_id)}">${escapeHtml(t("resume"))}</button>`
        : `<a class="button button-secondary" href="/expert?session=${encodeURIComponent(session.session_id)}">${escapeHtml(t("resume_expert"))}</a>`;
      return `<article class="history-card"><div><h2>${escapeHtml(labels.join(", ") || session.display_name)}</h2>
        <p>${escapeHtml(date)} · ${escapeHtml(t("saved_locally"))}</p></div>
        ${action}</article>`;
    }).join("")
    : `<p>${escapeHtml(t("no_history"))}</p>`;
}

async function openHistory() {
  const payload = await api("/internal/v1/sessions");
  state.sessions = payload.items || [];
  await refreshDisplayLabels();
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
    throw new Error(t("advanced_session"));
  }
  const available = (state.capabilities.compatible_selections || []).find((item) =>
    item.available && item.snapshot_id === session.selection.snapshot_id
    && item.strategy_id === session.selection.strategy_id);
  if (!available) throw new Error(t("session_snapshot_missing"));
  state.session = session;
  state.selection = available;
  state.selected = selectedFromSession(session);
  state.visibleCount = 5;
  state.questionCount = session.clinical_case?.question_history?.length || 0;
  updateResearchNotice();
  await refreshDisplayLabels();
  renderSelected();
  byId("patient-age").value = session.clinical_case?.subject_context?.age?.value ?? "";
  const diagnoseIsCurrent = session.latest_diagnose
    && (!session.latest_question || new Date(session.latest_diagnose.created_at)
      >= new Date(session.latest_question.created_at));
  if (diagnoseIsCurrent) {
    state.resultRun = await api(`${sessionPath()}/runs/${encodeURIComponent(session.latest_diagnose.run_id)}/summary`);
    await refreshDisplayLabels();
    renderResults();
    showScreen("results");
  } else if (session.latest_question) {
    state.questionRun = await api(`${sessionPath()}/runs/${encodeURIComponent(session.latest_question.run_id)}`);
    const question = state.questionRun.result.question;
    const answered = (session.clinical_case?.question_history || [])
      .some((item) => item.question_id === question?.question_id);
    if (question && !answered) {
      state.questionCount += 1;
      await renderQuestion(question);
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
  state.displayLabels = {};
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
}, t("prepare_questions")));
byId("age-skip").addEventListener("click", () => guarded(async () => {
  byId("patient-age").value = "";
  await ensureSession();
  await askNextQuestion();
}, t("prepare_questions")));
document.querySelectorAll("[data-answer]").forEach((button) => {
  button.addEventListener("click", () => guarded(() => answerQuestion(button.dataset.answer), t("analyse_answer")));
});
byId("question-to-results").addEventListener("click", () => guarded(diagnose, t("calculating")));
byId("result-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-detail-index]");
  if (button) guarded(() => openDetail(Number(button.dataset.detailIndex)), t("loading_detail"));
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
  if (button) guarded(() => resumeSession(button.dataset.resumeId), t("opening_analysis"));
});
document.querySelectorAll("[data-back]").forEach((button) => {
  button.addEventListener("click", () => { notice(""); showScreen(button.dataset.back); });
});
byId("retry-boot").addEventListener("click", boot);

function displayLabel(id, source) {
  const display = state.displayLabels[id];
  return (display?.display_label || source || t("documented"))
    + (locale() !== "en" && (!display || display.fallback_english) ? " [EN]" : "");
}

async function refreshDisplayLabels() {
  if (!state.selection) return;
  const language = locale(), snapshot = state.selection.snapshot_id;
  const ids = [...new Set([
    ...state.selected.map(item => item.concept_id),
    ...(state.session?.clinical_case?.observations || []).map(item => item.concept?.concept_id),
    ...(state.resultRun?.result?.candidates || []).map(item => item.candidate_id),
    ...state.sessions.slice(0, 20).flatMap(session => (session.clinical_case?.observations || []).slice(0, 3).map(item => item.concept?.concept_id)),
  ].filter(Boolean))].slice(0, 100);
  if (!ids.length) { state.displayLabels = {}; return; }
  const params = new URLSearchParams({snapshot, strategy: state.selection.strategy_id, language});
  ids.forEach(id => params.append("ids", id));
  const payload = await api("/internal/v1/presentation/labels?" + params);
  if (language === locale() && snapshot === state.selection?.snapshot_id) state.displayLabels = payload.items || {};
}

async function changeLanguage(language) {
  if (state.busy) return;
  await guarded(async () => {
    window.LatrosI18n.setLanguage(language);
    ++state.searchSequence;
    state.displayLabels = {};
    byId("result-dialog").close();
    updateResearchNotice(); renderSelected(); renderResults(); renderHistory();
    if (state.screen === "error") byId("error-text").textContent = t(state.bootErrorKey);
    await refreshDisplayLabels();
    updateResearchNotice(); renderSelected(); renderResults(); renderHistory();
    if (state.screen === "question" && state.questionRun?.result.question) await renderQuestion(state.questionRun.result.question);
    if (state.selection && byId("symptom-search").value.trim()) await searchConcepts();
    byId("search-hint").textContent = t("search_hint");
  });
}
document.querySelectorAll("[data-language]").forEach(button => {
  button.addEventListener("click", () => changeLanguage(button.dataset.language));
});
window.LatrosI18n.apply();

boot();
