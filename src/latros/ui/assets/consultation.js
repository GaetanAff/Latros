// Workflow projection only; source scope, budgets and questions live in the backend.
function consultationPhase() { return state.session?.consultation?.phase || 'general'; }
async function exploreRare() {
  state.session = await api(`${sessionPath()}/consultation/rare`, {
    method:'POST', body:JSON.stringify({revision:state.session.revision}),
  });
  state.generalRun = state.resultRun;
  state.selection = (state.capabilities.compatible_selections || []).find(item =>
    item.available && item.snapshot_id === state.session.selection.snapshot_id
    && item.strategy_id === 'rare_question_v1');
  state.questionRun = null; state.questionCount = 0;
  notice(t('rare_explanation'));
  await askNextQuestion();
}
function updateConsultationView() {
  const rare = consultationPhase() === 'rare';
  byId('results-title').textContent = t(rare ? 'rare_results' : 'general_results');
  byId('question-title').textContent = t(rare ? 'rare_title' : 'general_title');
  byId('question-to-results').textContent = t(rare ? 'rare_now' : 'results_now');
  byId('rare-opt-in').hidden = !state.session?.consultation?.general_run || rare;
  byId('general-result-section').hidden = !rare || !state.generalRun;
  if (rare && state.generalRun) {
    byId('general-result-list').innerHTML = resultCards(state.generalRun.result.candidates || [], 'general');
    byId('general-result-status').textContent = state.generalRun.result.abstention ? t('abstention') : t('complete');
  }
}
async function restoreConsultationRuns(session) {
  state.generalRun = null;
  if (session.consultation?.general_run) {
    state.generalRun = await api(`${sessionPath()}/runs/${encodeURIComponent(session.consultation.general_run.run_id)}/summary`);
  }
  updateConsultationView();
}
byId('rare-start').addEventListener('click',()=>guarded(exploreRare, t('prepare_questions')));
byId('general-result-list').addEventListener('click',event=>{
  const button=event.target.closest('[data-detail-index]');
  if (button) guarded(()=>openDetail(Number(button.dataset.detailIndex),'general'),t('loading_detail'));
});
