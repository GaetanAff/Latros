// Display only: independent local model output never enters Latros reasoning.
async function refreshHuatuo() {
  if (!state.session) return;
  const sessionId = state.session.session_id;
  const payload = await api(`${sessionPath()}/local-ai/huatuo/latest`);
  if (state.session?.session_id !== sessionId) return;
  state.aiAnalysis = payload.analysis;
  state.aiStale = Boolean(payload.stale);
  renderHuatuoPanel();
}

function renderHuatuoPanel() {
  const panel = byId('ai-panel');
  panel.hidden = state.screen !== 'results' || !state.session?.latest_diagnose;
  if (panel.hidden) return;
  panel.setAttribute('aria-busy',String(Boolean(state.aiBusy)));
  byId('ai-run').disabled = Boolean(state.aiBusy);
  const analysis = state.aiAnalysis;
  byId('ai-title').textContent = t(analysis ? 'ai_complete' : 'ai_waiting');
  const status = byId('ai-status');
  status.textContent = state.aiBusy ? t('ai_loading')
    : state.aiStale ? t('ai_stale')
    : state.aiError ? t(state.aiError) : '';
  status.classList.toggle('ai-stale',Boolean(state.aiStale));
  const output = byId('ai-output');
  output.hidden = !analysis;
  if (!analysis) { output.innerHTML = ''; return; }
  const hypotheses = analysis.output?.hypotheses || [];
  output.innerHTML = `<p class="field-hint">${escapeHtml(t('ai_no_triage'))}</p>`
    + hypotheses.map((item,index) => `<article class="ai-hypothesis">
      <h3>${index+1}. ${escapeHtml(item.name)}</h3>
      <p><strong>${escapeHtml(t('ai_reason'))} :</strong> ${escapeHtml(item.reason)}</p>
      <p><strong>${escapeHtml(t('ai_uncertainty'))} :</strong> ${escapeHtml(item.uncertainty)}</p>
      </article>`).join('')
    + `<h3>${escapeHtml(t('ai_uncertainty'))}</h3><ul>${(analysis.output?.uncertainties||[])
      .map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
    + `<p><strong>${escapeHtml(t('ai_limitations'))} :</strong> ${escapeHtml(analysis.output?.limitations||'')}</p>`;
}

async function runHuatuo() {
  if (!state.session?.latest_diagnose || state.aiBusy) return;
  const sessionId = state.session.session_id;
  state.aiBusy = true; state.aiError = null; renderHuatuoPanel();
  try {
    const payload = await api(`${sessionPath()}/local-ai/huatuo`, {
      method:'POST',body:JSON.stringify({revision:state.session.revision,language:locale()}),
    });
    if (state.session?.session_id !== sessionId) return;
    state.session = payload.session;
    state.aiAnalysis = payload.analysis;
    state.aiStale = Boolean(payload.stale);
  } catch (error) {
    if (state.session?.session_id === sessionId)
      state.aiError = /unavailable/i.test(error.message || '') ? 'ai_unavailable' : 'ai_failed';
  } finally {
    if (state.session?.session_id === sessionId) {
      state.aiBusy = false;
      renderHuatuoPanel();
    }
  }
}
byId('ai-run').addEventListener('click',runHuatuo);
