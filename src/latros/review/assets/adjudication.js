"use strict";
const $ = (id) => document.getElementById(id);
const state = { token: "", item: null, indices: [], position: 0, epoch: 0 };
const categories = {
  correct_clinical_manifestation: "Manifestation clinique correcte", wrong_semantic_role: "Mauvais rôle sémantique",
  disease_self_reference: "Auto-référence maladie", modifier: "Modificateur", negated: "Négation",
  family_history: "Histoire familiale", risk_or_prevention: "Risque / prévention",
  treatment_or_procedure_context: "Traitement / procédure", other_disease_mention: "Autre maladie",
  mapping_problem: "Problème de mapping", ambiguous: "Ambigu", insufficient_context: "Contexte insuffisant", other: "Autre"
};
const finals = { approve: "Approuver pour la revue (aucune promotion)", reject: "Rejeter", defer: "Différer", needs_second_review: "Demander une seconde revue" };
for (const [value, label] of Object.entries(categories)) {
  const option = document.createElement("option"); option.value = value; option.textContent = label; $("category").append(option);
}
for (const [value, text] of Object.entries(finals)) {
  const label = document.createElement("label"); label.className = "action";
  const input = document.createElement("input"); input.type = "radio"; input.name = "final"; input.value = value; input.required = true;
  label.append(input, document.createTextNode(text)); $("decisions").append(label);
}
function message(text) { $("message").textContent = text; $("message").hidden = !text; }
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", "X-Latros-Review-Token": state.token, ...options.headers } });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.message || "Saisie invalide ou service local indisponible."); return payload;
}
function highlight(target, text, phrase) {
  target.replaceChildren();
  const tokens = (phrase || "").match(/[a-z0-9]+/gi);
  if (!tokens) { target.textContent = text; return; }
  const pattern = new RegExp("\\b" + tokens.join("[\\W_]+") + "\\b", "gi");
  let offset = 0;
  for (const match of text.matchAll(pattern)) {
    target.append(document.createTextNode(text.slice(offset, match.index)));
    const mark = document.createElement("mark"); mark.textContent = match[0]; target.append(mark); offset = match.index + match[0].length;
  }
  target.append(document.createTextNode(text.slice(offset)));
}
function parsed(value) { try { return JSON.parse(value); } catch { return []; } }
async function loadItem() {
  const epoch = ++state.epoch;
  if (!state.indices.length) {
    state.item = null; $("item-title").textContent = "Aucun item dans cette file";
    for (const id of ["finding", "comparison", "source-context", "source-text", "occurrences", "technical", "history"]) $(id).replaceChildren();
    for (const id of ["previous", "next", "save"]) $(id).disabled = true;
    return;
  }
  const query = new URLSearchParams({ dataset: $("dataset").value, index: state.indices[state.position], reviewer_id: $("reviewer-id").value, stage: $("stage").value });
  const item = await api("/api/v2/item?" + query); if (epoch !== state.epoch) return;
  state.item = item; const row = item.row;
  localStorage.setItem("latros-g5-position", JSON.stringify({ dataset: item.dataset, position: state.position }));
  $("item-title").textContent = row.topic_title || row.disease_label || row.disease_source_label || "Item de revue";
  $("finding").textContent = `${row.finding_label || row.candidate_disease_label || "Mapping / provenance"} ${row.finding_code || row.candidate_disease_code || ""} · ${row.relation || "mapping"} · ${row.polarity || ""}`;
  $("comparison").textContent = `Extraction historique : ${row.historical_state || row.review_status || "candidat non revu"}\nG4 : ${row.auto_filter_decision || "non applicable à ce jeu historique"}\nRaison : ${row.auto_filter_rule || "—"}\nSignaux : ${row.g4_signals || "—"}\nRéviseurs indépendants enregistrés : ${item.reviewer_count}`;
  highlight($("source-context"), row.source_context || "Le jeu historique ne fournit pas de segment textuel. Consultez les locators dans le panneau technique.", row.finding_label);
  highlight($("source-text"), row.source_text || "", row.finding_label);
  $("occurrences").replaceChildren();
  for (const occurrence of parsed(row.match_contexts)) { const p = document.createElement("p"); highlight(p, `${occurrence.section} — ${occurrence.text}`, row.finding_label); $("occurrences").append(p); }
  $("technical").replaceChildren();
  for (const [key, value] of Object.entries(row)) {
    if (!value || key.startsWith("human_") || ["source_text", "match_contexts"].includes(key)) continue;
    const div = document.createElement("div"); div.className = "field"; const dt = document.createElement("dt"); dt.textContent = key;
    const dd = document.createElement("dd"); dd.textContent = value; div.append(dt, dd); $("technical").append(div);
  }
  $("history").replaceChildren();
  for (const event of item.history) { const p = document.createElement("p"); p.textContent = `${event.stage || "historique"} · ${event.reviewer_name} · ${event.timestamp_utc} · ${event.category || ""} · ${event.final_decision || event.action} · ${event.comment}`; $("history").append(p); }
  $("category").value = ""; document.querySelectorAll('input[name="final"]').forEach((input) => input.checked = false); $("comment").value = "";
  $("mapping-wrap").hidden = item.dataset !== "g1"; $("mapping-relation").value = "";
  $("previous").disabled = state.position === 0; $("next").disabled = state.position + 1 >= state.indices.length; $("save").disabled = false;
}
async function loadQueue(reset = false) {
  const query = new URLSearchParams(new FormData($("filters"))); query.set("dataset", $("dataset").value);
  const queue = await api("/api/v2/queue?" + query); state.indices = queue.indices;
  state.position = reset ? 0 : Math.min(state.position, Math.max(0, state.indices.length - 1));
  const p = queue.progress; $("progress").textContent = `Revus ${p.reviewed} / ${queue.total} · accords ${p.agreement} · désaccords ${p.disagreement} · différés ${p.deferred} · adjudications ${p.adjudicated} (progression de revue, pas métrique clinique)`;
  await loadItem();
}
function guard(task) { return (...args) => task(...args).catch((error) => message(error.message)); }
$("filters").addEventListener("submit", guard(async (event) => { event.preventDefault(); await loadQueue(true); }));
$("dataset").addEventListener("change", guard(() => loadQueue(true)));
$("stage").addEventListener("change", guard(loadItem));
$("reviewer-id").addEventListener("change", guard(loadItem));
for (const [id, delta] of [["previous", -1], ["next", 1]]) $(id).addEventListener("click", guard(async () => { state.position = Math.max(0, Math.min(state.indices.length - 1, state.position + delta)); await loadItem(); }));
$("decision-form").addEventListener("submit", guard(async (event) => {
  event.preventDefault(); const selected = document.querySelector('input[name="final"]:checked'); if (!state.item || !selected) return;
  let mapping = null;
  if (state.item.dataset === "g1" && selected.value === "approve") { mapping = $("mapping-relation").value; if (!["exact", "equivalent"].includes(mapping)) throw new Error("Choisissez explicitement exact/equivalent ou différez."); }
  $("save").disabled = true;
  try {
    await api("/api/v2/decision", { method: "POST", body: JSON.stringify({ dataset: state.item.dataset, index: state.item.index, row_id: state.item.row_id,
      stage: $("stage").value, category: $("category").value, final_decision: selected.value, reviewer_name: $("reviewer-name").value, reviewer_id: $("reviewer-id").value,
      attests_identity: $("attest").checked, qualification_self_attested: $("qualification").value, comment: $("comment").value,
      mapping_relation: mapping, basis_event_hashes: $("stage").value === "adjudication" ? state.item.basis_event_hashes : [] }) });
    await loadQueue(); message("Décision ajoutée au journal append-only. Aucun snapshot modifié.");
  } finally { $("save").disabled = false; }
}));
document.addEventListener("keydown", (event) => { if (event.altKey && ["ArrowLeft", "ArrowRight"].includes(event.key)) { event.preventDefault(); $(event.key === "ArrowLeft" ? "previous" : "next").click(); } if (event.ctrlKey && event.key === "Enter") $("decision-form").requestSubmit(); });
$("export").addEventListener("click", guard(async () => {
  const kind = $("export-kind").value; const response = await fetch("/api/v2/export/" + kind, { headers: { "X-Latros-Review-Token": state.token } });
  if (!response.ok) throw new Error("Export refusé."); const url = URL.createObjectURL(await response.blob()); const a = document.createElement("a"); a.href = url; a.download = `latros-g5-${kind}.json`; a.click(); URL.revokeObjectURL(url);
}));
guard(async () => { state.token = (await api("/api/v2/token")).token; const saved = parsed(localStorage.getItem("latros-g5-position") || "{}"); if (saved.dataset) $("dataset").value = saved.dataset; state.position = saved.position || 0; await loadQueue(); })();
