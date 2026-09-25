"use strict";

const state = { token: null, dataset: "g1", index: 0, item: null };
const byId = (id) => document.getElementById(id);
const labels = {
  topic_id: "Topic ID", topic_title: "Topic MedlinePlus", disease_source_label: "Libellé maladie source",
  synonyms: "Synonymes", mesh_ids: "IDs MeSH", candidate_assertions_blocked: "Candidates bloquées",
  current_mapping_status: "Statut de mapping actuel", current_mapping_relation: "Relation actuelle",
  candidate_disease_code: "Code maladie proposé", candidate_disease_label: "Maladie proposée",
  hypothesis_type: "Type de piste", technical_justification: "Justification technique",
  disease_label: "Maladie", disease_code: "Code maladie", finding_label: "Finding",
  finding_code: "Code finding", relation: "Relation", polarity: "Polarité",
  source_release: "Release source", source_record_id: "Record source", source_locator: "Locator",
  source_url: "URL source", artifact_ids: "Artefacts", artifact_sha256: "Hash artefact",
  subject_mapping_provenance: "Mapping maladie", object_mapping_provenance: "Mapping finding",
  evidence_family: "Famille de preuve", dependency_group: "Groupe de dépendance",
  dependency_type: "Type de dépendance", dependency_primary_reference: "Amont primaire",
  primary_knowledge_source: "Source primaire", aggregator_knowledge_source: "Agrégateur",
  audit_class: "Classe d’audit", review_status: "Statut initial non revu", domains: "Domaines",
  extractor: "Extracteur", review_stratum: "Strate de l’échantillon",
};
const actionLabels = {
  approve_exact: "Approuver le mapping exact (décision de revue seulement)",
  approve_equivalent: "Approuver le mapping équivalent (décision de revue seulement)",
  approve_for_review: "Retenir l’assertion / provenance pour la revue",
  reject: "Rejeter", ambiguous: "Ambigu — demander une analyse supplémentaire",
  invalid_candidate: "Pas une maladie / candidat invalide",
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.message || `Erreur HTTP ${response.status}`);
  return payload;
}

function message(value) {
  byId("message").textContent = value;
  byId("message").hidden = !value;
}

function render() {
  const item = state.item;
  if (!item) return;
  const row = item.row;
  byId("progress").textContent = `${item.index + 1} / ${item.count} · ${state.dataset}`;
  byId("item-title").textContent = row.topic_title || row.disease_label || row.disease_source_label || "Ligne de revue";
  byId("status").textContent = item.history.length ? "Décision enregistrée — révision possible" : "Non revu";
  const fields = byId("fields");
  fields.replaceChildren();
  Object.entries(row).forEach(([key, value]) => {
    if (!value || key.startsWith("human_")) return;
    const wrapper = document.createElement("div");
    wrapper.className = "field";
    const term = document.createElement("dt");
    term.textContent = labels[key] || key.replaceAll("_", " ");
    const description = document.createElement("dd");
    description.textContent = value;
    wrapper.append(term, description);
    fields.append(wrapper);
  });
  const actions = byId("actions");
  actions.replaceChildren();
  item.allowed_actions.filter((action) =>
    !(state.dataset === "g1" && !row.candidate_disease_code && action.startsWith("approve_"))
  ).forEach((action) => {
    const label = document.createElement("label");
    label.className = "action";
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "action";
    radio.value = action;
    radio.required = true;
    label.append(radio, document.createTextNode(actionLabels[action] || action));
    actions.append(label);
  });
  document.querySelectorAll('input[name="action"]').forEach((input) => { input.checked = false; });
  byId("comment").value = "";
  byId("previous").disabled = item.index === 0;
  byId("next").disabled = item.index + 1 >= item.count;
  const history = byId("history");
  history.replaceChildren();
  if (!item.history.length) history.textContent = "Aucune décision enregistrée sur cette ligne.";
  item.history.forEach((event) => {
    const entry = document.createElement("article");
    entry.className = "history-entry";
    const heading = document.createElement("strong");
    heading.textContent = `${actionLabels[event.action] || event.action} · ${event.reviewer_name}`;
    const detail = document.createElement("p");
    detail.textContent = `${event.timestamp_utc} · ${event.reviewer_id}${event.comment ? ` · ${event.comment}` : ""}`;
    entry.append(heading, detail);
    history.append(entry);
  });
}

async function loadItem() {
  message("");
  state.item = await api(`/api/item?dataset=${encodeURIComponent(state.dataset)}&index=${state.index}`);
  render();
  window.scrollTo({ top: 0, behavior: "instant" });
}

byId("dataset").addEventListener("change", async (event) => {
  state.dataset = event.target.value;
  state.index = 0;
  try { await loadItem(); } catch (error) { message(error.message); }
});
byId("previous").addEventListener("click", async () => {
  state.index -= 1;
  try { await loadItem(); } catch (error) { message(error.message); }
});
byId("next").addEventListener("click", async () => {
  state.index += 1;
  try { await loadItem(); } catch (error) { message(error.message); }
});
byId("decision-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.item) return;
  const selected = document.querySelector('input[name="action"]:checked');
  if (!selected) { message("Choisissez une décision explicite."); return; }
  byId("save").disabled = true;
  try {
    await api("/api/decision", {
      method: "POST",
      headers: { "X-Latros-Review-Token": state.token },
      body: JSON.stringify({
        dataset: state.dataset, index: state.index, row_id: state.item.row_id,
        action: selected.value, reviewer_name: byId("reviewer-name").value,
        reviewer_id: byId("reviewer-id").value, attests_identity: byId("attest").checked,
        comment: byId("comment").value,
      }),
    });
    await loadItem();
    message("Décision horodatée et ajoutée au journal local. Le snapshot n’a pas changé.");
  } catch (error) { message(error.message); }
  finally { byId("save").disabled = false; }
});
byId("export").addEventListener("click", async () => {
  try {
    const response = await fetch("/api/export", { headers: { "X-Latros-Review-Token": state.token } });
    if (!response.ok) throw new Error("L’export des décisions a échoué.");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "latros-v07-g-decisions.json";
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (error) { message(error.message); }
});

(async () => {
  try {
    state.token = (await api("/api/token")).token;
    await loadItem();
  } catch (error) { message(error.message); }
})();
