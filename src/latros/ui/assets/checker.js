function showScreen(name) {
  state.screen = name;
  byId('region-panel').hidden = name !== 'home' || ['body','head'].includes(state.anatomy.region);
  ["home", "age", "refinement", "question", "verification", "results", "history", "error"].forEach((screen) => {
    byId(`screen-${screen}`).hidden = screen !== name;
  });
  document.documentElement.dataset.screen = name;
  const steps = ["age", "home", "question", "results"];
  const progressName = ['refinement', 'verification'].includes(name) ? 'question' : name;
  document.querySelectorAll("[data-progress]").forEach((element) => {
    const step = element.dataset.progress;
    element.classList.toggle("active", step === progressName);
    element.classList.toggle("done", steps.indexOf(step) < steps.indexOf(progressName) && steps.includes(progressName));
    element.setAttribute('aria-current',step===progressName?'step':'false');
  });
  byId("nav-expert").href = state.session
    ? `/expert?session=${encodeURIComponent(state.session.session_id)}` : "/expert";
  renderHuatuoPanel();
  window.scrollTo({ top: 0, behavior: "instant" });
}

function preferredSelection(capabilities) {
  const general = (capabilities.compatible_selections || []).find(item =>
    item.available && item.strategy_id === 'general_question_v2');
  if (general) return general;
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
    // History labels are resolved when history is opened, not on the landing page.
    renderHistory();
    renderSelected();
    showScreen("age");
    // Navigation metadata/SVG only; no repository warm-up delaying startup.
    anatomyNavigate('body');
  } catch (error) {
    byId("error-text").textContent = t(state.bootErrorKey);
    byId("error-text").title = error.message || "";
    showScreen("error");
  } finally { setBusy(false); }
}
function newAnalysis() {
  state.session = null;
  state.resultRun = null;
  state.generalRun = null;
  state.questionRun = null;
  state.verificationPlan = null;
  state.verificationQuestion = null;
  state.verificationRunId = null;
  state.verificationUpdated = false;
  state.aiAnalysis = null;
  state.aiStale = false;
  state.aiError = null;
  state.aiBusy = false;
  state.selected = [];
  state.suggestions = [];
  state.displayLabels = {};
  state.visibleCount = 5;
  state.questionCount = 0;
  state.caseDirty = true;
  state.ageDirty = true;
  state.patientDirty = false;
  nlpProposal = null;
  byId('nlp-panel').hidden = true;
  state.refinements=[];state.refinementIndex=0;
  state.selection = preferredSelection(state.capabilities);
  byId("patient-age").value = "";
  restorePatientForm(null);
  byId("symptom-search").value = "";
  updateResearchNotice();
  renderSelected();
  renderSuggestions();
  showScreen("age");
  anatomyNavigate('body');
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
  if (state.busy) return;
  const region = event.target.closest('[data-observation-region]');
  if (region) { showScreen('home'); anatomyNavigate(region.dataset.observationRegion); return; }
  const button = event.target.closest("[data-remove-index]");
  if (!button) return;
  state.selected.splice(Number(button.dataset.removeIndex), 1);
  observationsChanged();
  renderSelected();
});
byId('selected-symptoms').addEventListener('change',event=>{
  if (state.busy) { renderSelected(); return; }
  const select=event.target.closest('[data-status-index]');
  if(!select) return;
  state.selected[Number(select.dataset.statusIndex)].status=select.value;
  observationsChanged(); renderSelected();
});
function beginAnalysis(action) {
  state.pendingAction=action; notice('');
  if(!state.selected.length) return;
  if(!state.session || state.patientDirty) showScreen('age');
  else guarded(()=>beginRefinements(action),t('prepare_questions'));
}
byId("home-continue").addEventListener("click", () => beginAnalysis('diagnose'));
byId("home-question").addEventListener("click", () => beginAnalysis('question'));
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
byId("results-edit").addEventListener("click", () => { notice(""); showScreen("age"); });
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
    renderHuatuoPanel();
    if (state.screen === "error") byId("error-text").textContent = t(state.bootErrorKey);
    await refreshDisplayLabels();
    updateResearchNotice(); renderSelected(); renderResults(); renderHistory();
    renderHuatuoPanel();
    if (state.screen === "question" && state.questionRun?.result.question) await renderQuestion(state.questionRun.result.question);
    if (state.screen === 'verification' && state.verificationQuestion) {
      const answered = (state.session.clinical_case.question_history || []).filter(item =>
        state.verificationPlan?.items?.some(question => question.question_id === item.question_id)).length;
      await renderVerification({question:state.verificationQuestion, answered, maximum:6});
    }
    if (state.screen === 'refinement' && state.refinements[state.refinementIndex]) renderRefinement();
    if (state.selection && byId("symptom-search").value.trim()) await searchConcepts();
    await anatomyNavigate(state.anatomy.region);
    byId("search-hint").textContent = t("search_hint");
  });
}
document.querySelectorAll("[data-language]").forEach(button => {
  button.addEventListener("click", () => changeLanguage(button.dataset.language));
});
window.LatrosI18n.apply();

boot();
