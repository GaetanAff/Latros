"use strict";
// All references are navigation-only; the API resolves supported canonical concepts.
function anatomyTrail(config, region) {
  const trail = [];
  for (let node = config.nodes[region]; node; node = config.nodes[node.parent]) trail.unshift(node);
  return trail;
}
function regionForObservation(item) {
  return Object.entries(state.anatomy.resolvedRegions || {}).find(([,items])=>items.some(option=>option.concept_id===item.concept_id))?.[0];
}
function scrollMotion() {
  return window.matchMedia?.('(prefers-reduced-motion:reduce)')?.matches ? 'auto' : 'smooth';
}

async function anatomyNavigate(region = 'body') {
  if (!state.selection) return;
  const changingRegion = region !== state.anatomy.region;
  const navigationFocus = document.activeElement?.closest?.('[data-region],[data-anatomy-region],#region-back');
  const sequence = ++state.anatomy.sequence;
  state.anatomy.picked = null;
  byId('region-selection').hidden = true;
  byId('region-panel').hidden = state.screen !== 'home' || region === 'body' || region === 'head';
  byId('region-options').textContent = t('region_loading');
  const params = new URLSearchParams({snapshot:state.selection.snapshot_id,
    strategy:state.selection.strategy_id,region,language:locale()});
  try {
    const payload = await api('/internal/v1/presentation/anatomy?' + params);
    if (sequence !== state.anatomy.sequence) return;
    state.anatomy.config = payload.config;
    if (state.anatomy.snapshot !== state.selection.snapshot_id) state.anatomy.resolvedRegions = {};
    state.anatomy.snapshot = state.selection.snapshot_id;
    state.anatomy.resolvedRegions[region] = payload.items;
    state.anatomy.region = region;
    state.anatomy.items = payload.items;
    const node = payload.config.nodes[region];
    for (const item of payload.items) rememberDisplay(item);
    byId('anatomy-breadcrumb').innerHTML = anatomyTrail(payload.config,region).map((entry,index) =>
      `<button type="button" data-anatomy-region="${escapeHtml(entry.id)}" ${entry.id===region?'aria-current="page"':''}>${escapeHtml(entry.labels[locale()])}</button>${entry.id===region?'':'<span aria-hidden="true">›</span>'}`).join('');
    byId('home-title').textContent = region === 'body' ? t('explore') : node.labels[locale()];
    byId('region-title').textContent = node.labels[locale()];
    byId('region-pending').hidden = node.implemented;
    const response = await fetch('/assets/anatomy/' + node.asset);
    if (!response.ok) throw new Error(t('region_error'));
    const documentSvg = new DOMParser().parseFromString(await response.text(),'image/svg+xml');
    if (sequence !== state.anatomy.sequence) return;
    const svg = documentSvg.documentElement;
    svg.setAttribute('role','group'); svg.setAttribute('aria-label',node.labels[locale()]);
    svg.querySelectorAll('title').forEach(title=>{title.textContent=node.labels[locale()];});
    svg.querySelectorAll('[data-region-label]').forEach(label=>{
      const target=payload.config.nodes[label.dataset.regionLabel];
      if(target) label.textContent=target.labels[locale()];
    });
    svg.querySelectorAll('[data-region]').forEach(zone => {
      const target = payload.config.nodes[zone.dataset.region];
      if (target) zone.setAttribute('aria-label',target.labels[locale()]);
      zone.classList.toggle('active',zone.dataset.region === region);
    });
    byId('anatomy-canvas').replaceChildren(document.importNode(svg,true));
    byId('anatomy-region-links').innerHTML = node.children.map(id =>
      `<button type="button" class="region-link" data-anatomy-region="${id}">${escapeHtml(payload.config.nodes[id].labels[locale()])}</button>`).join('');
    renderRegionOptions(); renderSelected();
    if (navigationFocus) {
      const focusTarget = byId('region-panel').hidden
        ? byId('anatomy-breadcrumb').querySelector('[aria-current="page"]') : byId('region-back');
      focusTarget?.focus();
    }
    if (changingRegion && state.screen === 'home' && window.matchMedia?.('(max-width:800px)')?.matches) {
      const target = byId('region-panel').hidden ? byId('screen-home') : byId('region-panel');
      target.scrollIntoView?.({block:'start',behavior:scrollMotion()});
    }
  } catch (error) {
    if (sequence !== state.anatomy.sequence) return;
    state.anatomy.items = []; state.anatomy.picked = null;
    byId('region-options').textContent = t('region_error'); notice(error.message);
  }
}

function renderRegionOptions() {
  byId('region-options').innerHTML = state.anatomy.items.length ? state.anatomy.items.map((item,index) =>
    `<button class="region-finding" type="button" data-region-finding="${index}" aria-pressed="${state.selected.some(selected=>selected.concept_id===item.concept_id)}">${escapeHtml(displayLabel(item.concept_id,item.label))}</button>`).join('')
    : `<p class="field-hint">${escapeHtml(t('region_empty'))}</p>`;
}

function updateAnatomySelection() {
  const selectedIds = new Set(state.selected.map(item=>item.concept_id));
  const config = state.anatomy.config;
  if (!config) return;
  document.querySelectorAll('#anatomy-canvas [data-region]').forEach(zone => {
    const target = config.nodes[zone.dataset.region];
    const descendants = Object.values(config.nodes).filter(node=>anatomyTrail(config,node.id).some(entry=>entry.id===target?.id));
    zone.classList.toggle('selected',descendants.some(node=>(state.anatomy.resolvedRegions?.[node.id]||[]).some(item=>selectedIds.has(item.concept_id))));
  });
  renderRegionOptions();
}

function pickRegionFinding(index) {
  const item = state.anatomy.items[index];
  if (!item) return;
  state.anatomy.picked = item;
  byId('region-finding-title').textContent = displayLabel(item.concept_id,item.label);
  const existing = state.selected.find(selected=>selected.concept_id===item.concept_id);
  document.querySelectorAll('input[name="region-status"]').forEach(input=>input.checked=Boolean(existing && existing.status===input.value));
  byId('region-selection').hidden = false;
  byId('region-selection').scrollIntoView?.({block:'nearest',behavior:scrollMotion()});
}

function toggleTheme() {
  const dark = document.documentElement.dataset.theme !== 'dark';
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  byId('theme-toggle').setAttribute('aria-pressed',String(dark));
  try { localStorage.setItem('latros-theme',dark?'dark':'light'); } catch {}
}
try {
  const theme = localStorage.getItem('latros-theme');
  if (theme === 'dark') { document.documentElement.dataset.theme='dark'; byId('theme-toggle').setAttribute('aria-pressed','true'); }
} catch {}
byId('theme-toggle').addEventListener('click',toggleTheme);
byId('anatomy-canvas').addEventListener('click',event => {
  const zone=event.target.closest('[data-region]'); if(zone) anatomyNavigate(zone.dataset.region);
});
byId('anatomy-canvas').addEventListener('keydown',event => {
  const zone=event.target.closest('[data-region]');
  if(zone && ['Enter',' '].includes(event.key)) { event.preventDefault(); anatomyNavigate(zone.dataset.region); }
});
for (const id of ['anatomy-breadcrumb','anatomy-region-links']) byId(id).addEventListener('click',event=>{
  const button=event.target.closest('[data-anatomy-region]'); if(button) anatomyNavigate(button.dataset.anatomyRegion);
});
byId('region-options').addEventListener('click',event=>{
  const button=event.target.closest('[data-region-finding]'); if(button) pickRegionFinding(Number(button.dataset.regionFinding));
});
byId('region-selection').addEventListener('submit',event=>{
  event.preventDefault(); if(state.busy) return;
  const input=document.querySelector('input[name="region-status"]:checked');
  if(!input || !state.anatomy.picked) return;
  addObservation(state.anatomy.picked,input.value); notice(t('added_case'));
  byId('region-selection').hidden=true; state.anatomy.picked=null;
});
byId('explore-body').addEventListener('click',()=>{showScreen('home'); anatomyNavigate('body');});
byId('region-back').addEventListener('click',()=>{
  const parent=state.anatomy.config?.nodes[state.anatomy.region]?.parent;
  if(parent) anatomyNavigate(parent);
});
byId('mobile-search-toggle').addEventListener('click',()=>{byId('symptom-search').scrollIntoView({block:'center',behavior:scrollMotion()});byId('symptom-search').focus();});
