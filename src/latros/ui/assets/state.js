"use strict";
const DISPLAY_LABEL_CACHE_LIMIT = 100;
function rememberDisplay(option) {
  delete state.displayLabels[option.concept_id];
  state.displayLabels[option.concept_id] = option;
  Object.keys(state.displayLabels).slice(0,Math.max(0,Object.keys(state.displayLabels).length-DISPLAY_LABEL_CACHE_LIMIT))
    .forEach(id=>delete state.displayLabels[id]);
}

// Presentation only: all concept resolution, questions, scoring and safety state
// come from the loopback Latros API. No clinical rule is evaluated here.
const state = {
  capabilities: null,
  selection: null,
  sessions: [],
  session: null,
  selected: [],
  suggestions: [],
  resultRun: null,
  generalRun: null,
  questionRun: null,
  questionCount: 0,
  searchSequence: 0,
  searchTimer: null,
  busyTimer: null,
  busy: false,
  visibleCount: 5,
  displayLabels: {},
  screen: 'home',
  bootErrorKey: 'service_unavailable',
  caseDirty: true,
  ageDirty: true,
  pendingAction: 'diagnose',
  anatomy: { config: null, region: 'body', items: [], picked: null, sequence: 0 },
};

const byId = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");
const t = (key, values = {}) => window.LatrosI18n.t(key, values);
const locale = () => window.LatrosI18n.language;
const sessionPath = () => `/internal/v1/sessions/${encodeURIComponent(state.session.session_id)}`;
