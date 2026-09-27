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
  return ['general_v1','general_question_v2','rare_question_v1'].includes(session.selection?.strategy_id)
    && !clinicalCase.subject_context?.sex
    && !(clinicalCase.source_statements || []).length
    && !(clinicalCase.observation_proposals || []).length
    && (clinicalCase.observations || []).every((item) =>
      answerIds.has(item.observation_id)
      || (["symptom", "sign", "exam"].includes(item.kind)
        && ['present','absent','unknown'].includes(item.clinical_status)
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
  return (session.clinical_case?.observations || [])
    .filter((item) => ['symptom','sign','exam'].includes(item.kind))
    .map((item) => ({
      concept_id: item.concept.concept_id,
      system: item.concept.coding.system,
      code: item.concept.coding.code,
      label: item.concept.coding.display || item.concept.coding.code,
      observation_kind: item.kind,
      status: item.clinical_status,
      savedObservation: structuredClone(item),
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
  await restoreConsultationRuns(session);
  state.caseDirty = false;
  state.ageDirty = false;
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
