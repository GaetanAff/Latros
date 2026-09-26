function renderSuggestions() {
  const panel = byId("symptom-suggestions");
  const query = byId("symptom-search").value.trim();
  if (query.length < 2) {
    panel.hidden = true;
    byId("symptom-search").setAttribute("aria-expanded", "false");
    return;
  }
  panel.innerHTML = state.suggestions.length
    ? state.suggestions.map((item, index) => `
      <button type="button" class="suggestion" role="option" data-suggestion-index="${index}">
        ${escapeHtml(item.display_label || item.label)}${item.fallback_english ? " [EN]" : ""}
      </button>`).join("")
    : `<div class="suggestion-empty">${escapeHtml(t("no_concept"))}</div>`;
  panel.hidden = false;
  byId("symptom-search").setAttribute("aria-expanded", "true");
}

async function searchConcepts() {
  const query = byId("symptom-search").value.trim();
  const sequence = ++state.searchSequence;
  if (query.length < 2) {
    state.suggestions = [];
    renderSuggestions();
    byId("search-hint").textContent = t("search_hint");
    return;
  }
  byId("search-hint").textContent = t("searching");
  const params = new URLSearchParams({
    snapshot: state.selection.snapshot_id,
    strategy: state.selection.strategy_id,
    q: query,
    limit: "12",
    language: locale(),
  });
  try {
    const payload = await api(`/internal/v1/presentation/concepts?${params}`);
    if (sequence !== state.searchSequence) return;
    state.suggestions = payload.items || [];
    renderSuggestions();
    byId("search-hint").textContent = state.suggestions.length
      ? t("choose") : t("try_wording");
  } catch (error) {
    if (sequence !== state.searchSequence) return;
    state.suggestions = [];
    renderSuggestions();
    byId("search-hint").textContent = t("search_unavailable");
    notice(error.message);
  }
}

function selectSuggestion(index) {
  if (state.busy) return;
  const item = state.suggestions[index];
  if (!item) return;
  // Existing states are preserved when selecting the same concept again via search.
  addObservation(item, state.selected.find(selected => selected.concept_id === item.concept_id)?.status || 'present');
  byId("symptom-search").value = "";
  state.suggestions = [];
  ++state.searchSequence;
  renderSuggestions();
  renderSelected();
  byId("search-hint").textContent = t("added");
  byId("symptom-search").focus();
}
