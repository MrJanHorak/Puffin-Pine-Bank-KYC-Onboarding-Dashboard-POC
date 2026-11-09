// Run with node tests/frontend-smoke.cjs. Uses a small DOM/API test double.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const handlers=new Map(),elements=new Map();
function el(selector){
 if(!elements.has(selector))elements.set(selector,{value:'',innerHTML:'',textContent:'',hidden:false,disabled:false,scrollIntoView(){},focus(){},addEventListener(name,fn){handlers.set(selector+':'+name,fn)}});
 return elements.get(selector);
}
const document={querySelector:el,getElementById:id=>el('#'+id),addEventListener(name,fn){handlers.set('document:'+name,fn)}};
const directory={applications:[{id:'SPECIMEN-APP-5154',company:'SPECIMEN Example Ltd',submitted:'2026-01-01',category:'Not checked',checked_at:null},{id:'SPECIMEN-APP-5201',company:'Halden Logistics Ltd',submitted:'2026-08-15',category:'Not checked',checked_at:null}],counts:{'All applications':2,'Not checked':2,'Needs information':0,'Flagged for analyst':0,'Compliance review':0}};
const detail={application_id:'SPECIMEN-APP-5154',company:{name:'SPECIMEN Example Ltd',registration_number:'REG-1',jurisdiction:'XA',risk_tier:'LOW'},parties:[{id:'SPECIMEN-PTY-1',role:'DIRECTOR',name:'SPECIMEN Person'}],documents:[],fields:[{id:'application_date',label:'Application date',value:'2026-01-01',original:'2026-01-01',available:true}],audit:[]};
const linked={application_id:'SPECIMEN-APP-5201',linked:true,company:{name:'Halden Logistics Ltd',registration_number:'HL-482913',jurisdiction:'XB',risk_tier:'LOW'},parties:[],documents:[{id:'DOC-1',type:'PROOF_OF_ADDRESS',party_id:'PTY-1',source:'A4.png'}],fields:[],audit:[]};
const assessment={application_id:'SPECIMEN-APP-5154',status:'NO_FLAGS',status_text:'Test',reasons:[],screenings:[{party_id:'SPECIMEN-PTY-1',outcome:'NO_MATCH',list_version:'GDL-2026.06'}],review_cases:[],policy:{outcome:'not_configured',sections:[]},ownership_chains:[],trace:[{name:'get_application',ok:true},{name:'screen_watchlist',party_id:'SPECIMEN-PTY-1',ok:true}]};
async function fetch(url,options={}){
 let data;
 if(url==='/api/lab/directory')data=directory;
 else if(url==='/api/operations')data={events:[],review_case_count:0};
 else if(url==='/api/lab/case/SPECIMEN-APP-5154')data=detail;
 else if(url==='/api/lab/case/SPECIMEN-APP-5154/edit'){const change=JSON.parse(options.body);detail.fields[0].value=change.value;detail.fields[0].edited=true;detail.audit=[{time:'2026-11-01T00:00:00Z',field:'application_date',old_value:'2026-01-01',new_value:change.value,action:'edit'}];directory.applications[0].category='Needs recheck';data=detail}
 else if(url==='/api/lab/case/SPECIMEN-APP-5201')data=linked;
 else if(url==='/api/documents/CASE-A')data={evidence:[{id:'A4:name',field:'name',value:'Halden',confidence:.57,document:'A4.png',review_required:true}],review_items:[{field:'name'}]};
 else if(url==='/api/linked/5201')data={corrections:{},supplement:'not_attached',audit:[]};
 else if(url==='/api/lab/run'){directory.applications[0].category='No rule flags';directory.applications[0].checked_at='2026-11-01T00:00:00Z';directory.counts['Not checked']=1;directory.counts['No rule flags']=1;data=assessment}
 else if(url==='/api/lab/case-review'){const review=JSON.parse(options.body);assert.equal(review.checked_at,directory.applications[0].checked_at);directory.applications[0].review={time:'2026-11-01T01:00:00Z',notes:review.notes,current:true};data={message:'Review recorded.'}}
 else throw Error('Unexpected request: '+url);
 return {ok:true,async json(){return data}};
}
const context=vm.createContext({document,fetch,console,alert(){},encodeURIComponent});
vm.runInContext(fs.readFileSync('markdown.js','utf8'),context);
vm.runInContext(fs.readFileSync('app.js','utf8'),context);
const wait=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 await wait();await wait();
 assert.match(el('#directory-list').innerHTML,/Example Ltd/);
 assert.match(el('#detail').innerHTML,/Business &amp; ownership/);
 assert.match(el('#detail').innerHTML,/Person/);
 assert.match(el('#detail').innerHTML,/Run checks/);
 assert.doesNotMatch(el('#detail').innerHTML,/Separate sample scenarios|Course KYC/);
 const button={dataset:{action:'run-checks'},disabled:false,textContent:''};
 await handlers.get('document:click')({target:{closest(query){return query.startsWith('[data-action]')?button:null}}});
 assert.match(el('#detail').innerHTML,/No rule flags were raised/);
 assert.match(el('#detail').innerHTML,/Check results · No Flags/);
 assert.match(el('#detail').innerHTML,/GDL-2026.06/);
 assert.match(el('#detail').innerHTML,/Show recorded tool steps/);
 assert.ok(el('#detail').innerHTML.indexOf('Check results ·')<el('#detail').innerHTML.indexOf('Generate case summary'));
 assert.match(el('#detail').innerHTML,/Policy sources/);
 assert.match(el('#detail').innerHTML,/Mark checks reviewed/);
 el('#case-review-notes').value='Screening reviewed';
 const reviewButton={dataset:{action:'record-case-review'},disabled:false};
 await handlers.get('document:click')({target:{closest(query){return query.startsWith('[data-action]')?reviewButton:null}}});
 assert.match(el('#detail').innerHTML,/Screening reviewed/);
 assert.doesNotMatch(el('#detail').innerHTML,/Mark checks reviewed/);
 el('#edit-application_date').value='2026-02-01';
 const edit={dataset:{editSave:'application_date'},disabled:false};
 await handlers.get('document:click')({target:{closest(query){return query.startsWith('[data-action]')?edit:null}}});
 assert.match(el('#detail').innerHTML,/2026-02-01/);
 assert.doesNotMatch(el('#detail').innerHTML,/No rule flags were raised/);
 const selectLinked={dataset:{openCase:'SPECIMEN-APP-5201'}};
 await handlers.get('document:click')({target:{closest(query){return query==='[data-open-case]'?selectLinked:null}}});
 assert.match(el('#detail').innerHTML,/Halden Logistics Ltd/);
 assert.match(el('#detail').innerHTML,/Review supporting documents/);
 const evidenceButton={dataset:{action:'load-evidence'},disabled:false};
 await handlers.get('document:click')({target:{closest(query){return query.startsWith('[data-action]')?evidenceButton:null}}});
 assert.match(el('#detail').innerHTML,/Extracted: Halden/);
 assert.match(el('#detail').innerHTML,/Attach supporting record/);
 directory.applications[0].category='Flagged for analyst';directory.counts['Flagged for analyst']=1;
 el('#directory-search').value='unrelated search';
 const flagged={dataset:{filter:'Flagged for analyst'}};
 await handlers.get('document:click')({target:{closest(query){return query==='[data-filter]'?flagged:null}}});
 assert.equal(el('#directory-search').value,'');
 assert.match(el('#directory-list').innerHTML,/case-flagged/);
 assert.match(el('#directory-list').innerHTML,/pill flagged/);
 assert.match(el('#detail').innerHTML,/Example Ltd/);
 assert.match(el('#metrics').innerHTML,/data-filter="Flagged for analyst" aria-pressed="true"/);
 assert.match(el('#reports-content').innerHTML,/data-filter="Flagged for analyst" aria-pressed="true"/);
 const filter={dataset:{filter:'Needs information'}};
 await handlers.get('document:click')({target:{closest(query){return query==='[data-filter]'?filter:null}}});
 assert.match(el('#directory-list').innerHTML,/No applications match/);
 console.log('Frontend smoke checks passed');
})().catch(error=>{console.error(error);process.exitCode=1});
