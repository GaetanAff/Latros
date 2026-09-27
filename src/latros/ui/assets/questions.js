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
  updateConsultationView();
  byId("question-count").textContent = t("question_count", {count: state.questionCount});
  const budget = question.expected_contribution || {};
  if (Number.isInteger(budget.remaining_budget)) {
    byId('question-count').textContent = t('bounded_question', {
      count: budget.answered_in_phase+1, budget:budget.maximum_questions,
      remaining:budget.remaining_budget,
    });
  }
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
  state.selected = selectedFromSession(accepted);
  state.caseDirty = false;
  await refreshDisplayLabels(); renderSelected();
  await askNextQuestion();
}
