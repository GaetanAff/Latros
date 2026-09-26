"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const root = path.resolve(__dirname, "../..");
const source = name => fs.readFileSync(path.join(root, "src/latros/ui/assets", name), "utf8");

function environment(saved = new Map()) {
  const elements = new Map(), calls = [];
  const node = id => {
    if (!elements.has(id)) elements.set(id, {
      value:"", textContent:"", innerHTML:"", hidden:false, disabled:false, dataset:{},
      classList:{toggle(){}}, setAttribute(name,value){this[name]=value;},
      addEventListener(){}, querySelector(){return null;}, focus(){}, close(){}, showModal(){},
      replaceChildren(){}, scrollIntoView(){},
    });
    return elements.get(id);
  };
  const staticNode = node("translated"); staticNode.dataset.i18n = "home";
  const question = {question_id:"backend-question-fixed", text:"Do you have Rhinorrhea?",
    concept:{system:"HPO",code:"HP:0031417",label:"Rhinorrhea"}, allowed_answers:["present","absent","unknown"]};
  const context = vm.createContext({console, URLSearchParams, structuredClone,
    localStorage:{getItem:key=>saved.get(key)||null,setItem:(key,value)=>saved.set(key,value)},
    crypto:{randomUUID:()=>"test-uuid"},
    DOMParser:class { parseFromString(){return {documentElement:{querySelectorAll:()=>[],setAttribute(){}}};} },
    document:{documentElement:{lang:"",dataset:{}},getElementById:node,importNode:node=>node,
      querySelectorAll:selector=>selector==="[data-i18n]"?[staticNode]:[],querySelector:()=>null},
    window:{clearTimeout(){},setTimeout(){return 1;},scrollTo(){}},
    fetch:async (url,options) => {
      calls.push({url,options}); const parsed = new URL(url,"http://127.0.0.1");
      let body={};
      if(parsed.pathname.endsWith("capabilities")) body={snapshots:[{snapshot_id:"test",research_unreviewed:true}], compatible_selections:[{snapshot_id:"test",strategy_id:"general_v1",available:true}]};
      if(parsed.pathname.endsWith("sessions")) body={items:[]};
      const lang=parsed.searchParams.get("language")||"en";
      const display={display_label:{fr:"Nez qui coule",de:"Laufende Nase",en:"Runny nose"}[lang],display_language:lang,fallback_english:false};
      if(parsed.pathname.endsWith("presentation/labels")) body={items:{finding:display}};
      if(parsed.pathname.endsWith("presentation/concepts")) body={items:[{concept_id:"finding",system:"HPO",code:"HP:0031417",label:"Rhinorrhea",language:"en",observation_kind:"symptom",...display}]};
      if(parsed.pathname.endsWith("presentation/question")) body={...display,question_text:{fr:"Avez-vous le nez qui coule ?",de:"Läuft Ihre Nase?",en:"Do you have a runny nose?"}[lang]};
      if(parsed.pathname.endsWith('presentation/anatomy')) body={config:JSON.parse(source('anatomy/navigation.json')),items:parsed.searchParams.get('region')==='sinuses'?[{concept_id:'finding',system:'HPO',code:'HP:0031417',label:'Rhinorrhea',observation_kind:'symptom',...display}]:[]};
      return {ok:true,status:200,json:async()=>body,text:async()=>'<svg />'};
    }});
  vm.runInContext(source("i18n.js"),context);
  for(const name of ['state','api','search','observations','questions','results','history','anatomy','checker']) vm.runInContext(source(name+'.js'),context);
  return {context,node,calls,saved,question,run:code=>vm.runInContext(code,context)};
}
async function ready(env) { for(let i=0;i<20 && env.run("state.busy");i++) await new Promise(resolve=>setImmediate(resolve)); }

test("complete local UI catalog and persistent language with explicit fallback",async()=>{
  const env=environment(); await ready(env);
  const html=fs.readFileSync(path.join(root,"src/latros/ui/templates/checker.html"),"utf8");
  const keys=[...html.matchAll(/data-i18n(?:-aria|-placeholder)?="([^"]+)"/g)].map(m=>m[1]);
  const allJs=['checker','api','search','observations','questions','results','history','anatomy'].map(name=>source(name+'.js')).join('\n');
  const jsKeys=[...allJs.matchAll(/\bt\(['"]([^'"]+)['"]/g)].map(m=>m[1]);
  for(const lang of ["fr","de","en"]) {
    env.run(`window.LatrosI18n.setLanguage('${lang}')`);
    for(const key of [...keys,...jsKeys]) assert.ok(env.run(`t('${key}')`).length>0,key);
    assert.equal(env.context.document.documentElement.lang,lang);
    assert.match(env.run("t('english_fallback')"),/EN/);
  }
  const resumed=environment(env.saved); await ready(resumed);
  assert.equal(resumed.run("locale()"),"en");
  assert.throws(()=>env.run("window.LatrosI18n.setLanguage('xx')"));
  assert.ok(!source("i18n.js").includes("fetch("));
});

test("search FR/DE/EN selects the same canonical coding and keeps source English",async()=>{
  const env=environment(); await ready(env);
  for(const lang of ["fr","de","en"]) {
    env.run(`window.LatrosI18n.setLanguage('${lang}'); state.selected=[];`);
    env.node("symptom-search").value={fr:"nez qui coule",de:"Schnupfen",en:"runny nose"}[lang];
    await env.run("searchConcepts()"); env.run("selectSuggestion(0)");
    const coding=JSON.parse(env.run("JSON.stringify(makeObservation(state.selected[0]).concept)"));
    assert.deepEqual(coding,{concept_id:"finding",coding:{system:"HPO",code:"HP:0031417",display:"Rhinorrhea"}});
    assert.ok(env.calls.some(call=>call.url.includes("language="+lang)));
  }
});

test("language switch during session translates question but leaves run and question_id intact",async()=>{
  const env=environment(); await ready(env);
  env.context.testQuestion=env.question;
  env.run(`state.session={session_id:'test-session',clinical_case:{observations:[],question_history:[]}};
    state.questionRun={run_id:'immutable-run',result:{question:testQuestion}};
    state.screen='question';state.questionCount=1;`);
  const original=env.run("JSON.stringify(state.questionRun)");
  await env.run("changeLanguage('de')");
  assert.equal(env.node("question-text").textContent,"Läuft Ihre Nase?");
  assert.match(env.node("question-source").textContent,/backend-question-fixed.*HP:0031417.*Rhinorrhea/s);
  assert.equal(env.run("JSON.stringify(state.questionRun)"),original);
  await env.run("changeLanguage('fr')");
  assert.equal(env.node("question-text").textContent,"Avez-vous le nez qui coule ?");
  assert.equal(env.run("JSON.stringify(state.questionRun)"),original);
  assert.equal(env.saved.get("latros-language"),"fr");
});

test("untranslated labels, abstention, research and safety stay explicit without percentages",async()=>{
  const env=environment(); await ready(env);
  env.run("window.LatrosI18n.setLanguage('de'); state.displayLabels={};");
  assert.equal(env.run("displayLabel('missing','Source label')"),"Source label [EN]");
  env.run("state.resultRun={result:{research_unreviewed:true,abstention:{reason:'insufficient_supported_findings'},candidates:[]}}; renderResults(); updateResearchNotice();");
  assert.match(env.node("result-alert").textContent,/Ungeprüftes Wissen/);
  assert.match(env.node("research-banner").textContent,/keine klinische Validierung/);
  assert.ok(!env.node("result-list").innerHTML.includes("%"));
  assert.match(env.run("t('safety')"),/Notfallsituationen/);
});

test("body/head/sinuses breadcrumb, back navigation and supported findings",async()=>{
  const env=environment(); await ready(env);
  await env.run("anatomyNavigate('head')");
  assert.equal(env.run("anatomyTrail(state.anatomy.config,'head').map(n=>n.id).join('/')"),'body/head');
  await env.run("anatomyNavigate('sinuses')");
  assert.equal(env.run("anatomyTrail(state.anatomy.config,'sinuses').map(n=>n.id).join('/')"),'body/head/sinuses');
  assert.match(env.node('anatomy-breadcrumb').innerHTML,/aria-current="page"/);
  assert.equal(env.run('state.anatomy.items.length'),1);
  assert.equal(env.node('region-panel').hidden,false);
  await env.run("anatomyNavigate('body')");
  assert.equal(env.node('region-panel').hidden,true);
  assert.equal(env.run('state.anatomy.items.length'),0);
});

test("anatomy and text search upsert one canonical observation with three explicit states",async()=>{
  const env=environment(); await ready(env);
  await env.run("anatomyNavigate('sinuses')");
  env.run("pickRegionFinding(0)");
  assert.equal(env.run('state.selected.length'),0); // Picking is not a patient answer.
  env.run("addObservation(state.anatomy.picked,'absent')");
  env.node('symptom-search').value='nez qui coule';
  await env.run('searchConcepts()'); env.run('selectSuggestion(0)');
  assert.equal(env.run('state.selected.length'),1);
  assert.equal(env.run('state.selected[0].status'),'absent'); // Search does not overwrite an existing answer.
  const coding=env.run('JSON.stringify(makeObservation(state.selected[0]).concept)');
  for(const status of ['present','absent','unknown']) {
    env.run(`addObservation(state.anatomy.items[0],'${status}')`);
    assert.equal(env.run('state.selected.length'),1);
    assert.equal(env.run('JSON.stringify(makeObservation(state.selected[0]).concept)'),coding);
    assert.equal(env.run('makeObservation(state.selected[0]).clinical_status'),status);
    assert.equal(env.run('makeObservation(state.selected[0]).uncertainty_reason'),status==='unknown'?'unknown_to_subject':undefined);
  }
  assert.throws(()=>env.run("addObservation(state.anatomy.items[0],'invented')"));
});

test("theme is local, persistent and accessible",async()=>{
  const env=environment(); await ready(env);
  env.run('toggleTheme()');
  assert.equal(env.context.document.documentElement.dataset.theme,'dark');
  assert.equal(env.node('theme-toggle')['aria-pressed'],'true');
  const resumed=environment(env.saved); await ready(resumed);
  assert.equal(resumed.context.document.documentElement.dataset.theme,'dark');
  resumed.run('toggleTheme()');
  assert.equal(resumed.saved.get('latros-theme'),'light');
});

test("resumed present/absent/unknown and answered questions retain original observation identity",async()=>{
  const env=environment(); await ready(env);
  for(const status of ['present','absent','unknown']) {
    env.context.example={clinical_case:{observations:[{kind:'symptom',observation_id:'unchanged',
      concept:{concept_id:'finding',coding:{system:'HPO',code:'HP:0031417',display:'Rhinorrhea'}},
      clinical_status:status,evaluation_status:'assessed',acquisition_method:'reported'}],
      question_history:[{observation_id:'unchanged'}]}};
    env.run('state.selected=selectedFromSession(example)');
    assert.equal(env.run('state.selected.length'),1);
    assert.equal(env.run('makeObservation(state.selected[0]).observation_id'),'unchanged');
    assert.equal(env.run('makeObservation(state.selected[0]).clinical_status'),status);
  }
});

test("unchanged resumed session is not rewritten before a next question or analysis",async()=>{
  const env=environment(); await ready(env);
  env.run("state.session={session_id:'existing'};state.caseDirty=false;");
  const before=env.calls.length;
  await env.run('ensureSession()');
  assert.equal(env.calls.length,before);
});

test("new analysis routes to age with the chosen backend action, without frontend questions",async()=>{
  const env=environment(); await ready(env);
  env.run("state.selected=[{concept_id:'finding'}];beginAnalysis('question')");
  assert.equal(env.run('state.screen'),'age');
  assert.equal(env.run('state.pendingAction'),'question');
  env.run("beginAnalysis('diagnose')");
  assert.equal(env.run('state.pendingAction'),'diagnose');
});

test("editing observations leaves old scientific run intact but hides stale results/questions",async()=>{
  const env=environment(); await ready(env);
  await env.run("anatomyNavigate('sinuses')");
  env.run("state.resultRun={run_id:'immutable-run'};state.screen='results';state.caseDirty=false;");
  env.run("addObservation(state.anatomy.items[0],'present')");
  assert.equal(env.run('state.screen'),'home');
  assert.equal(env.run('state.caseDirty'),true);
  assert.equal(env.run('state.resultRun.run_id'),'immutable-run');
  assert.equal(env.run("regionForObservation(state.selected[0])"),'sinuses');
  assert.match(env.node('selected-symptoms').innerHTML,/data-observation-region="sinuses"/);
  env.run("state.screen='question';observationsChanged()");
  assert.equal(env.run('state.screen'),'home');
});

test("display cache is bounded and isolated when the active snapshot changes",async()=>{
  const env=environment(); await ready(env);
  env.run("for(let i=0;i<150;i++) rememberDisplay({concept_id:'id-'+i,display_label:'label'});");
  assert.equal(env.run('Object.keys(state.displayLabels).length'),100);
  assert.equal(env.run("state.displayLabels['id-0']"),undefined);
  await env.run("anatomyNavigate('sinuses')");
  assert.equal(env.run("regionForObservation({concept_id:'finding'})"),'sinuses');
  env.run("state.selection.snapshot_id='another';");
  await env.run("anatomyNavigate('body')");
  assert.equal(env.run("regionForObservation({concept_id:'finding'})"),undefined);
});
