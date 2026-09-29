// Generic backend capture definition, not a frontend medical questionnaire.
async function beginRefinements(action) {
  state.pendingAction = action;
  await ensureSession();
  const payload = await api(`${sessionPath()}/refinements`);
  const answered = new Set((payload.answers || []).map(item=>item.observation_id));
  state.refinements = (payload.items || []).filter(item=>!answered.has(item.observation_id));
  state.refinementIndex = 0;
  if (!state.refinements.length) return finishRefinements();
  renderRefinement(); showScreen('refinement');
}

function renderRefinement() {
  const definition = state.refinements[state.refinementIndex];
  if (!definition) return;
  byId('refinement-title').textContent = displayLabel(definition.concept_id,definition.source_label);
  byId('refinement-count').textContent = t('refinement_count',{count:state.refinementIndex+1,total:state.refinements.length});
  document.querySelectorAll('[data-refinement-field]').forEach(element=>{
    element.hidden=!definition.question_types.includes(element.dataset.refinementField);
  });
  byId('refinement-duration').value = '';
  byId('refinement-unit').innerHTML = definition.duration_units.map(unit=>`<option value="${escapeHtml(unit)}">${escapeHtml(t(`unit_${unit}`))}</option>`).join('');
  for (const [id,values] of [['severity',definition.severity_options],['laterality',definition.laterality_options]]) {
    byId('refinement-'+id).innerHTML = `<option value="">${escapeHtml(t('not_specified'))}</option>` + values.map(value=>`<option value="${escapeHtml(value)}">${escapeHtml(t(`refine_${value}`))}</option>`).join('');
  }
  byId('refinement-technical').textContent = JSON.stringify(definition,null,2);
}

async function saveRefinement() {
  const definition = state.refinements[state.refinementIndex];
  const duration = byId('refinement-duration').value.trim();
  if (duration && (!Number.isInteger(Number(duration)) || Number(duration)<1 || Number(duration)>10000)) throw new Error(t('duration_error'));
  const answer = {
    definition_id:definition.definition_id,observation_id:definition.observation_id,concept_id:definition.concept_id,
    duration_value:definition.question_types.includes('duration') && duration?Number(duration):null,
    duration_unit:definition.question_types.includes('duration') && duration?byId('refinement-unit').value:null,
    reported_severity:definition.question_types.includes('reported_severity')?byId('refinement-severity').value || null:null,
    reported_laterality:definition.question_types.includes('reported_laterality')?byId('refinement-laterality').value || null:null,
  };
  state.session = await api(`${sessionPath()}/refinements`, {
    method:'PUT',body:JSON.stringify({revision:state.session.revision,answer}),
  });
  state.selected = selectedFromSession(state.session); state.caseDirty=false;
  renderSelected();
  await advanceRefinement();
}
async function advanceRefinement() {
  state.refinementIndex += 1;
  if (state.refinementIndex < state.refinements.length) renderRefinement();
  else await finishRefinements();
}
async function finishRefinements() {
  await (state.pendingAction === 'question' ? askNextQuestion() : diagnose());
}
byId('refinement-form').addEventListener('submit',event=>{event.preventDefault();guarded(saveRefinement,t('saving_information'));});
byId('refinement-skip').addEventListener('click',()=>guarded(advanceRefinement));
byId('refinement-finish').addEventListener('click',()=>guarded(finishRefinements,t('calculating')));
