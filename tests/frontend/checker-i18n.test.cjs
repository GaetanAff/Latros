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
    });
    return elements.get(id);
  };
  const staticNode = node("translated"); staticNode.dataset.i18n = "home";
  const question = {question_id:"backend-question-fixed", text:"Do you have Rhinorrhea?",
    concept:{system:"HPO",code:"HP:0031417",label:"Rhinorrhea"}, allowed_answers:["present","absent","unknown"]};
  const context = vm.createContext({console, URLSearchParams, structuredClone,
    localStorage:{getItem:key=>saved.get(key)||null,setItem:(key,value)=>saved.set(key,value)},
    crypto:{randomUUID:()=>"test-uuid"},
    document:{documentElement:{lang:""},getElementById:node,
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
      return {ok:true,status:200,json:async()=>body};
    }});
  vm.runInContext(source("i18n.js"),context);
  vm.runInContext(source("checker.js"),context);
  return {context,node,calls,saved,question,run:code=>vm.runInContext(code,context)};
}
async function ready(env) { for(let i=0;i<20 && env.run("state.busy");i++) await new Promise(resolve=>setImmediate(resolve)); }

test("complete local UI catalog and persistent language with explicit fallback",async()=>{
  const env=environment(); await ready(env);
  const html=fs.readFileSync(path.join(root,"src/latros/ui/templates/checker.html"),"utf8");
  const keys=[...html.matchAll(/data-i18n(?:-aria|-placeholder)?="([^"]+)"/g)].map(m=>m[1]);
  const jsKeys=[...source("checker.js").matchAll(/\bt\("([^"]+)"/g)].map(m=>m[1]);
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
