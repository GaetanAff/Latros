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
function setHoveredRegion(region) {
  state.anatomy.hoveredRegion = region;
  for (const element of document.querySelectorAll('#anatomy-canvas [data-region], #anatomy-region-links [data-anatomy-region]')) {
    const id = element.dataset.region || element.dataset.anatomyRegion;
    element.classList.toggle('is-hovered',id === region);
  }
}

// A local illustration is independent from keyboard-accessible navigation hitboxes.
function composeAtlas(svg, node, config) {
  const ns = 'http://www.w3.org/2000/svg';
  svg.setAttribute('viewBox',(node.focus_box || [0,0,...node.canvas]).join(' '));
  const illustration = document.createElementNS(ns,'image');
  illustration.setAttribute('href','/assets/anatomy/' + node.image);
  illustration.setAttribute('width',String(node.canvas[0]));
  illustration.setAttribute('height',String(node.canvas[1]));
  illustration.setAttribute('preserveAspectRatio','xMidYMid meet');
  illustration.setAttribute('aria-hidden','true');
  svg.appendChild(illustration);
  for (const id of node.children) {
    const target = config.nodes[id];
    const zone = document.createElementNS(ns,'g');
    zone.setAttribute('id','region-' + id);
    zone.setAttribute('data-region',id);
    zone.setAttribute('role','button');
    zone.setAttribute('tabindex','0');
    zone.setAttribute('aria-label',target.labels[locale()]);
    for (const box of target.hitboxes) {
      const rect = document.createElementNS(ns,'rect');
      ['x','y','width','height'].forEach((name,index)=>rect.setAttribute(name,String(box[index])));
      rect.setAttribute('rx','12'); rect.setAttribute('class','anatomy-hitbox');
      zone.appendChild(rect);
    }
    svg.appendChild(zone);
  }
  return svg;
}

async function anatomyNavigate(region = 'body') {
  if (!state.selection) return;
  setHoveredRegion(null);
  const changingRegion = region !== state.anatomy.region;
  const navigationFocus = document.activeElement?.closest?.('[data-region],[data-anatomy-region],#region-back');
  const sequence = ++state.anatomy.sequence;
  state.anatomy.picked = null;
  state.anatomy.regionQuery = '';
  state.anatomy.showAll = false;
  byId('region-search').value = '';
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
    composeAtlas(svg,node,payload.config);
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
  const normalize=value=>value.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase(locale());
  const query=normalize(state.anatomy.regionQuery || '').trim();
  const matches=state.anatomy.items.map((item,index)=>({item,index})).filter(({item})=>
    !query || normalize(displayLabel(item.concept_id,item.label)).includes(query));
  const visible=state.anatomy.showAll || query ? matches : matches.slice(0,8);
  byId('region-options').innerHTML = matches.length ? visible.map(({item,index}) =>
    `<button class="region-finding" type="button" data-region-finding="${index}" aria-pressed="${state.selected.some(selected=>selected.concept_id===item.concept_id)}">${escapeHtml(displayLabel(item.concept_id,item.label))}</button>`).join('') +
      (visible.length<matches.length ? `<button class="region-more" type="button" data-region-more="true">${escapeHtml(t('region_more'))} · ${matches.length-visible.length}</button>` : '')
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
  if (state.busy) return;
  addObservation(item,'present');
  notice(t('added_case'));
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
for (const id of ['anatomy-canvas','anatomy-region-links']) {
  const container=byId(id);
  const regionOf=element=>{
    const target=element?.closest?.('[data-region],[data-anatomy-region]');
    return target?.dataset.region || target?.dataset.anatomyRegion || null;
  };
  container.addEventListener('pointerover',event=>setHoveredRegion(regionOf(event.target)));
  container.addEventListener('pointerout',event=>setHoveredRegion(regionOf(event.relatedTarget)));
  container.addEventListener('focusin',event=>setHoveredRegion(regionOf(event.target)));
  container.addEventListener('focusout',event=>setHoveredRegion(regionOf(event.relatedTarget)));
}
for (const id of ['anatomy-breadcrumb','anatomy-region-links']) byId(id).addEventListener('click',event=>{
  const button=event.target.closest('[data-anatomy-region]'); if(button) anatomyNavigate(button.dataset.anatomyRegion);
});
byId('region-options').addEventListener('click',event=>{
  if(event.target.closest('[data-region-more]')) { state.anatomy.showAll=true; renderRegionOptions(); return; }
  const button=event.target.closest('[data-region-finding]'); if(button) pickRegionFinding(Number(button.dataset.regionFinding));
});
byId('region-search').addEventListener('input',event=>{
  state.anatomy.regionQuery=event.target.value;
  renderRegionOptions();
});
byId('explore-body').addEventListener('click',()=>{showScreen('home'); anatomyNavigate('body');});
byId('region-back').addEventListener('click',()=>{
  const parent=state.anatomy.config?.nodes[state.anatomy.region]?.parent;
  if(parent) anatomyNavigate(parent);
});
byId('mobile-search-toggle').addEventListener('click',()=>{byId('symptom-search').scrollIntoView({block:'center',behavior:scrollMotion()});byId('symptom-search').focus();});
