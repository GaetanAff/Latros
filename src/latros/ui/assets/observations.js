function renderSelected() {
  byId("selected-symptoms").innerHTML = state.selected.length ? state.selected.map((item, index) => `
    <div class="selected-observation"><span>${escapeHtml(displayLabel(item.concept_id, item.label))}${regionForObservation(item) ? `<button type="button" class="observation-region" data-observation-region="${escapeHtml(regionForObservation(item))}" aria-label="${escapeHtml(t('navigate_region'))}">${escapeHtml(state.anatomy.config.nodes[regionForObservation(item)].labels[locale()])}</button>` : ''}</span>
      <select data-status-index="${index}" aria-label="${escapeHtml(t('select_state')+' · '+displayLabel(item.concept_id,item.label))}">
        ${['present','absent','unknown'].map(status => `<option value="${status}" ${status === (item.status || 'present') ? 'selected' : ''}>${escapeHtml(t(status))}</option>`).join('')}
      </select><button type="button" data-remove-index="${index}" class="icon-button" aria-label="${escapeHtml(t("remove", {label: displayLabel(item.concept_id, item.label)}))}">×</button>
    </div>`).join("") : `<p class="field-hint">${escapeHtml(t('selected_empty'))}</p>`;
  byId("home-continue").disabled = state.selected.length === 0;
  byId("home-question").disabled = state.selected.length === 0;
  if (state.anatomy.config) updateAnatomySelection();
}

function addObservation(option, status = 'present') {
  if (state.busy) return;
  if (!['present','absent','unknown'].includes(status)) throw new Error('Invalid observation state');
  const existing = state.selected.find(item => item.concept_id === option.concept_id);
  if (existing) existing.status = status;
  else state.selected.push({...option, status});
  rememberDisplay(option);
  observationsChanged();
  renderSelected();
}
function observationsChanged() {
  state.caseDirty = true;
  // Never answer a stale question or present a prior run as analysing unsaved edits.
  if (['question','results'].includes(state.screen)) {
    showScreen('home'); notice(t('case_changed'));
  }
}
function makeObservation(option) {
  const status = option.status || 'present';
  if (option.savedObservation?.clinical_status === status) return structuredClone(option.savedObservation);
  return {
    kind: option.observation_kind,
    observation_id: `observation-${crypto.randomUUID()}`,
    concept: {
      concept_id: option.concept_id,
      coding: { system: option.system, code: option.code, display: option.label },
    },
    clinical_status: status,
    evaluation_status: "assessed",
    ...(status === 'unknown' ? {uncertainty_reason:'unknown_to_subject'} : {}),
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
  if (!state.caseDirty) return;
  if (state.session.consultation?.phase === 'rare') {
    state.selection = preferredSelection(state.capabilities);
    state.generalRun = null;
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
  clinicalCase.subject_context = subjectContextForSave(clinicalCase.subject_context);
  clinicalCase.observations = state.selected.map(makeObservation);
  const savedIds = new Set(clinicalCase.observations.map(item=>item.observation_id));
  clinicalCase.question_history = (clinicalCase.question_history || [])
    .filter(item=>savedIds.has(item.resulting_observation_id));
  state.session = await api(`${sessionPath()}/case`, {
    method: "PUT",
    body: JSON.stringify({ revision: state.session.revision, clinical_case: clinicalCase }),
  });
  state.resultRun = null;
  state.questionRun = null;
  state.questionCount = 0;
  state.caseDirty = false;
  state.ageDirty = false;
  byId("nav-expert").href = `/expert?session=${encodeURIComponent(state.session.session_id)}`;
}

function subjectContextForSave(previous) {
  const context = structuredClone(previous || {});
  if (state.ageDirty) {
    delete context.age;
    Object.assign(context, ageContext());
  }
  return context;
}
