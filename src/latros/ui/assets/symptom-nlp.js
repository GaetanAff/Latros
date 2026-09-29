// Local Qwen only proposes explicit patient findings. Nothing is added until confirmation.
let nlpProposal = null;

async function startSymptomInterpretation() {
  const panel = byId('nlp-panel');
  const narrative = state.session?.patient_context?.symptom_narrative;
  if (!narrative || !state.session) { panel.hidden = true; return; }
  panel.hidden = false;
  byId('nlp-mentions').innerHTML = '';
  byId('nlp-confirm').hidden = true;
  byId('nlp-status').textContent = t('nlp_loading');
  const sessionId = state.session.session_id;
  const revision = state.session.revision;
  try {
    const payload = await api(`${sessionPath()}/symptom-interpretations`, {
      method:'POST',body:JSON.stringify({revision,language:locale()}),
    });
    if (state.session?.session_id !== sessionId || state.session.revision !== revision
        || state.session.patient_context?.symptom_narrative?.trim() !== narrative.trim()) return;
    nlpProposal = payload;
    renderSymptomInterpretation();
  } catch (error) {
    if (state.session?.session_id !== sessionId) return;
    byId('nlp-status').textContent = t('nlp_unavailable');
    byId('nlp-status').title = error.message || '';
  }
}

function renderSymptomInterpretation() {
  const mentions = nlpProposal?.mentions || [];
  byId('nlp-status').textContent = mentions.length ? t('nlp_review') : t('nlp_no_match');
  byId('nlp-mentions').innerHTML = mentions.map((mention,index)=>{
    const selected = mention.suggested_concept_id;
    const options = mention.options || [];
    return `<div class="nlp-mention">
      <label><input type="checkbox" data-nlp-check="${index}" ${selected?'checked':''} ${options.length?'':'disabled'}>
        <span>${escapeHtml(mention.text)}</span></label>
      <select data-nlp-choice="${index}" aria-label="${escapeHtml(t('nlp_choice'))}">
        <option value="">${escapeHtml(t('nlp_choose'))}</option>
        ${options.map((option,choice)=>`<option value="${choice}" ${option.concept_id===selected?'selected':''}>${escapeHtml(option.label)} · ${escapeHtml(option.code)}</option>`).join('')}
      </select><select data-nlp-status="${index}" aria-label="${escapeHtml(t('select_state'))}">
        ${['present','absent','unknown'].map(status=>`<option value="${status}" ${status===mention.status?'selected':''}>${escapeHtml(t(status))}</option>`).join('')}
      </select>
    </div>`;
  }).join('');
  byId('nlp-confirm').hidden = !mentions.some(item => item.options.length);
}

async function confirmSymptomInterpretation() {
  if (!nlpProposal || !state.session) return;
  const confirmed=[];
  for (const [index,mention] of nlpProposal.mentions.entries()) {
    const checked=byId('nlp-mentions').querySelector(`[data-nlp-check="${index}"]`)?.checked;
    const choice=byId('nlp-mentions').querySelector(`[data-nlp-choice="${index}"]`)?.value;
    if (!checked || choice === '') continue;
    const option=mention.options[Number(choice)];
    if (!option) continue;
    const status=byId('nlp-mentions').querySelector(`[data-nlp-status="${index}"]`)?.value || mention.status;
    confirmed.push({text:mention.text,start:mention.start,end:mention.end,
      status,concept_id:option.concept_id,system:option.system,code:option.code});
  }
  const before=state.selected;
  const dirty=state.caseDirty;
  state.session=await api(`${sessionPath()}/symptom-interpretations/confirm`,{
    method:'POST',body:JSON.stringify({revision:state.session.revision,
      narrative:nlpProposal.narrative,language:locale(),confirmed}),
  });
  const saved=selectedFromSession(state.session);
  const byConcept=new Map(saved.map(item=>[item.concept_id,item]));
  before.forEach(item=>byConcept.set(item.concept_id,item));
  state.selected=[...byConcept.values()];
  state.caseDirty=dirty;
  nlpProposal=null;
  byId('nlp-panel').hidden=true;
  await refreshDisplayLabels();
  renderSelected();
  notice(t('nlp_confirmed'));
}

byId('nlp-confirm').addEventListener('click',()=>guarded(confirmSymptomInterpretation,t('nlp_saving')));
byId('nlp-mentions').addEventListener('change',event=>{
  const choice=event.target.closest('[data-nlp-choice]');
  if (choice) {
    const check=byId('nlp-mentions').querySelector(`[data-nlp-check="${choice.dataset.nlpChoice}"]`);
    if (check) check.checked=choice.value!=='';
  }
});
