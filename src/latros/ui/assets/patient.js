// Identification is session-local, never an observation or a reasoning input.
function contextItems(value) {
  return value.split('\n').map(label => label.trim()).filter(Boolean)
    .map(label => ({label, origin:'self_reported', evaluation_status:'captured_not_evaluated'}));
}

function patientContextFromForm() {
  const first_name = byId('patient-first-name').value.trim();
  const last_name = byId('patient-last-name').value.trim();
  const age = byId('patient-age').value.trim();
  if (!first_name || !last_name) throw new Error(t('patient_name_error'));
  if (!age || !Number.isInteger(Number(age)) || Number(age) < 0 || Number(age) > 130) throw new Error(t('age_error'));
  return {
    context_version:1, demographics:{first_name,last_name,age_years:Number(age)},
    allergies:contextItems(byId('patient-allergies').value),
    known_conditions:contextItems(byId('patient-conditions').value),
    medications:contextItems(byId('patient-medications').value),
    relevant_history:contextItems(byId('patient-history').value),
    symptom_narrative:byId('patient-narrative').value.trim() || null,
    clinical_evaluation:'not_evaluated',
  };
}

function restorePatientForm(session) {
  const context = session?.patient_context;
  byId('patient-summary').textContent = context?.demographics.first_name || t('my_information');
  byId('patient-first-name').value = context?.demographics.first_name || '';
  byId('patient-last-name').value = context?.demographics.last_name || '';
  byId('patient-age').value = context?.demographics.age_years ?? session?.clinical_case?.subject_context?.age?.value ?? '';
  byId('patient-narrative').value = context?.symptom_narrative || '';
  for (const [id,key] of [['allergies','allergies'],['conditions','known_conditions'],['medications','medications'],['history','relevant_history']]) {
    byId('patient-'+id).value = (context?.[key] || []).map(item=>item.label).join('\n');
  }
  state.patientDirty = false;
}

async function savePatientInformation() {
  const context = patientContextFromForm();
  if (!state.session) {
    state.session = await api('/internal/v1/sessions', {
      method:'POST', body:JSON.stringify({display_name:t('new_analysis')}),
    });
  }
  state.session = await api(`${sessionPath()}/patient-context`, {
    method:'PUT',body:JSON.stringify({revision:state.session.revision,patient_context:context}),
  });
  // A profile-only session must remain resumable in the simple flow before
  // the user has selected any observation.
  if (state.selection && !state.session.selection) {
    state.session = await api(`${sessionPath()}/selection`, {
      method:'PUT',body:JSON.stringify({revision:state.session.revision,
        snapshot_id:state.selection.snapshot_id,strategy_id:state.selection.strategy_id}),
    });
  }
  state.patientDirty = false;
  state.ageDirty = false;
  state.caseDirty = true;
  byId('nlp-panel').hidden = true;
  state.resultRun = null; state.questionRun = null;
  byId('patient-summary').textContent = context.demographics.first_name;
}

byId('patient-form').addEventListener('submit',event=>{
  event.preventDefault();
  guarded(async()=>{
    await savePatientInformation();
    showScreen('home'); await anatomyNavigate(state.anatomy.region);
    if (state.session.patient_context?.symptom_narrative) void startSymptomInterpretation();
  },t('saving_information'));
});
byId('patient-form').addEventListener('input',()=>{state.patientDirty=true;state.ageDirty=true;});
byId('edit-patient').addEventListener('click',()=>showScreen('age'));
