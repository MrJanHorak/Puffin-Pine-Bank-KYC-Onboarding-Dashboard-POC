// Run with node tests/frontend-smoke.cjs. No browser or external packages needed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const handlers = new Map();
const elements = new Map();
function el(selector) {
  if (!elements.has(selector)) elements.set(selector, {value:'', innerHTML:'', disabled:false, addEventListener(name, handler) { handlers.set(selector+':'+name, handler); }});
  return elements.get(selector);
}
el('#doc-case').value = 'CASE-B';
el('#lab-id').value = 'SPECIMEN-APP-5154';
const document = {querySelector:el, addEventListener() {}};
const cases = {cases:[], operations:{events:[], sample_counts:{}, review_case_count:0, scope:'test'}, docs:{notice:'test',evidence:[],review_items:[]},
  lab:{application_id:'SPECIMEN-APP-5154',status:'NO_FLAGS',status_text:'Test',reasons:[],screenings:[],review_cases:[],policy:{outcome:'not_configured',sections:[]}}};
async function fetch(url) {
  let data = url === '/api/cases' ? cases.cases : url === '/api/operations' ? cases.operations : url === '/api/lab/applications' ? {application_ids:['SPECIMEN-APP-5154']} : url.startsWith('/api/documents/') ? cases.docs : url === '/api/lab/run' ? cases.lab : {};
  return {ok:true, async json(){return data;}};
}
const context = vm.createContext({document,fetch,console,alert(){},encodeURIComponent});
vm.runInContext(fs.readFileSync('app.js','utf8'),context);
(async()=>{
  const button=el('#load-docs'); const event={currentTarget:button};
  const pending=handlers.get('#load-docs:click')(event);
  event.currentTarget=null; // Browsers clear currentTarget after dispatch.
  await pending;
  assert.equal(button.disabled,false);
  assert.match(el('#doc-evidence').innerHTML,/test/);
  const submit={preventDefault(){},submitter:null}; // requestSubmit() without a submitter.
  await handlers.get('#lab-form:submit')(submit);
  assert.equal(el('#lab-form button[type="submit"]').disabled,false);
  assert.match(el('#lab-result').innerHTML,/SPECIMEN-APP-5154/);
  console.log('Frontend smoke checks passed');
})().catch(error=>{console.error(error);process.exitCode=1});
