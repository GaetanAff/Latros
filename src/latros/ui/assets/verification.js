// Projection of result_verification_v1. All question selection and case updates
// are performed by the loopback backend; the UI never scores hypotheses.
async function startVerification() {
  if (!state.resultRun?.run_id || consultationPhase() !== 'general') return;
  const payload = await api(`${sessionPath()}/runs/${encodeURIComponent(state.resultRun.run_id)}/verification`, {
    method: 'POST', body: JSON.stringify({revision:state.session.revision}),
  });
  state.verificationPlan = payload.plan;
  state.verificationRunId = payload.plan.base_run_id;
  await renderVerification(payload);
}

async function renderVerification(payload) {
  if (!payload.question) {
    if (payload.answered > 0) await finishVerification();
    else showScreen('results');
    return;
  }
  const item = payload.question;
  state.verificationQuestion = item;
  byId('verification-progress').textContent = t('verification_progress', {
    count:payload.answered+1, maximum:payload.maximum,
  });
  const params = new URLSearchParams({snapshot:state.selection.snapshot_id,
    strategy:state.selection.strategy_id, system:item.system, code:item.code, language:locale()});
  let display = {};
  try { display = await api('/internal/v1/presentation/question?' + params); } catch {}
  byId('verification-question-text').textContent = display.question_text || t('verification_question', {
    label:display.display_label || item.label,
  });
  byId('verification-fallback').hidden = !display.fallback_english;
  byId('verification-fallback').textContent = t('english_fallback');
  showScreen('verification');
}

async function answerVerification(answer) {
  const item = state.verificationQuestion;
  if (!item || !state.verificationRunId) return;
  const payload = await api(`${sessionPath()}/runs/${encodeURIComponent(state.verificationRunId)}/verification/answer`, {
    method:'POST', body:JSON.stringify({revision:state.session.revision,
      question_id:item.question_id,answer}),
  });
  state.session = payload.session;
  state.selected = selectedFromSession(state.session);
  state.caseDirty = false;
  await refreshDisplayLabels(); renderSelected();
  await renderVerification(payload);
}

async function finishVerification() {
  const answered = (state.session?.clinical_case?.question_history || []).some(item =>
    state.verificationPlan?.items?.some(verification => verification.question_id === item.question_id));
  if (!answered) { showScreen('results'); return; }
  state.verificationUpdated = true;
  await diagnose(); // New immutable run; the original run and its plan remain local.
}

byId('verification-start').addEventListener('click', () => guarded(startVerification, t('verification_loading')));
byId('verification-back').addEventListener('click', () => showScreen('results'));
byId('verification-finish').addEventListener('click', () => guarded(finishVerification, t('calculating')));
document.querySelectorAll('[data-verification-answer]').forEach(button => {
  button.addEventListener('click', () => guarded(() => answerVerification(button.dataset.verificationAnswer), t('analyse_answer')));
});
