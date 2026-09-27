async function diagnose() {
  const payload = await api(`${sessionPath()}/analyses?view=summary`, {
    method: "POST", body: JSON.stringify({ revision: state.session.revision }),
  });
  state.session = payload.session;
  state.resultRun = payload.run;
  if (consultationPhase() === 'general') state.generalRun = payload.run;
  await refreshDisplayLabels();
  renderResults();
  showScreen("results");
}

function observationLabel(contribution) {
  const observation = (state.session?.clinical_case?.observations || [])
    .find((item) => item.observation_id === contribution.observation);
  return observation ? displayLabel(observation.concept?.concept_id, observation.concept?.coding?.display || observation.concept?.coding?.code) : t("documented");
}

function contributionLabels(items, max = 2) {
  const labels = [...new Set((items || []).map(observationLabel))].slice(0, max);
  return labels.map((label) => `<li>${escapeHtml(label)}</li>`).join("");
}

function renderResults() {
  const result = state.resultRun?.result;
  if (!result) return;
  updateConsultationView();
  const candidates = result.candidates || [];
  const alert = byId("result-alert");
  const unreviewed = Boolean(result.research_unreviewed);
  alert.hidden = false;
  alert.textContent = unreviewed
    ? t("result_warning_unreviewed")
    : t("result_warning");
  if (!candidates.length || result.abstention) {
    byId("result-intro").textContent = candidates.length
      ? t("abstention")
      : t("no_results");
  } else {
    byId("result-intro").textContent = t("result_intro");
  }
  const visible = candidates.slice(0, state.visibleCount);
  byId("result-list").innerHTML = resultCards(visible, consultationPhase());
  byId("show-more-results").hidden = candidates.length <= state.visibleCount;
}
function resultCards(candidates, phase) {
  return candidates.map((candidate, index) => {
    const favorable = contributionLabels(candidate.favorable);
    const unfavorable = contributionLabels(candidate.unfavorable);
    return `<article class="result-card"><div class="result-heading">
      <span class="rank-badge" aria-label="${escapeHtml(t("rank", {rank: candidate.rank || index + 1}))}">${escapeHtml(candidate.rank || index + 1)}</span>
      <h2>${escapeHtml(displayLabel(candidate.candidate_id, candidate.label))}</h2></div>
      ${favorable ? `<ul aria-label="${escapeHtml(t("favorable"))}">${favorable}</ul>` : ""}
      ${unfavorable ? `<ul aria-label="${escapeHtml(t("unfavorable"))}"><li>${escapeHtml(t("contradiction"))}</li>${unfavorable}</ul>` : ""}
      <button type="button" class="text-link" data-detail-index="${index}">${escapeHtml(t("see_why"))}</button>
    </article>`;
  }).join("");
}

function detailList(items, empty) {
  return items?.length
    ? `<ul class="detail-list">${[...new Set(items.map(observationLabel))].map((label) => `<li>${escapeHtml(label)}</li>`).join("")}</ul>`
    : `<p>${escapeHtml(empty)}</p>`;
}

function unknownDetails(items) {
  if (!items?.length) return `<p>${escapeHtml(t("no_missing"))}</p>`;
  const known = items.filter((item) => observationLabel(item) !== t("documented"));
  return known.length
    ? detailList(known, "")
    : `<p>${escapeHtml(t("missing_count", {count: items.length}))}</p>`;
}

function sourceLabel(source) {
  const release = source.source_release_id || "";
  const names = { monarch: "Monarch Knowledge Graph", orphadata: "Orphadata",
    medlineplus: "MedlinePlus", hpo: "HPO", mondo: "Mondo", doid: "DOID" };
  const [id, version] = release.split(":", 2);
  return `${names[id] || id || t("local_source")}${version ? ` (${version})` : ""}`;
}

async function openDetail(index, phase) {
  const run = phase === 'general' && consultationPhase() === 'rare' ? state.generalRun : state.resultRun;
  const selected = run?.result?.candidates?.[index];
  if (!selected) return;
  const detail = await api(`${sessionPath()}/runs/${encodeURIComponent(run.run_id)}`
    + `/candidates/${encodeURIComponent(selected.candidate_id)}`);
  const candidate = detail.candidate;
  byId("dialog-title").textContent = t("why_candidate", {label: displayLabel(candidate.candidate_id, candidate.label)});
  byId("dialog-content").innerHTML = `
    <p>${escapeHtml(t("rank_notice", {rank: candidate.rank}))}</p>
    <section class="detail-section"><h3>${escapeHtml(t("favorable"))}</h3>
      ${detailList(candidate.favorable, t("no_favorable"))}</section>
    <section class="detail-section"><h3>${escapeHtml(t("unfavorable"))}</h3>
      ${detailList(candidate.unfavorable, t("no_contradiction"))}</section>
    <section class="detail-section"><h3>${escapeHtml(t("not_evaluated"))}</h3>
      ${unknownDetails(candidate.unknown)}</section>
    <section class="detail-section"><h3>${escapeHtml(t("sources"))}</h3>
      ${candidate.source_views?.length
    ? `<ul class="detail-list">${candidate.source_views.map((source) => `<li>${escapeHtml(sourceLabel(source))}</li>`).join("")}</ul>`
    : `<p>${escapeHtml(t("no_sources"))}</p>`}</section>
    <details class="technical-details"><summary>${escapeHtml(t("technical"))}</summary>
      <p>${escapeHtml(t("raw_score", {score: candidate.aggregate?.value}))}</p>
      <pre>${escapeHtml(JSON.stringify(detail, null, 2))}</pre>
    </details>`;
  byId("result-dialog").showModal();
}
