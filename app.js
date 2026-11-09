// Pineway analyst workspace: the directory and detail view share one KYC dataset.
const state = {directory:null,selected:null,detail:null,assessment:{},agent:{},policyAnswer:{},documentAnswer:{},editOpen:{},evidence:null,reviewState:null,filter:'All applications',limit:20,request:0};
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const displayName = value => String(value || 'Name unavailable').replace(/^SPECIMEN\s+/i,'');
const label = value => String(value||'').replaceAll('_',' ').toLowerCase().replace(/\b\w/g,c=>c.toUpperCase());
const readableDate = value => {if(!value)return '—';const date=new Date(/^\d{4}-\d{2}-\d{2}$/.test(value)?value+'T12:00:00':value);return Number.isNaN(date.valueOf())?value:new Intl.DateTimeFormat(undefined,{year:'numeric',month:'short',day:'numeric'}).format(date)};
const readableTime = value => {if(!value)return '—';const date=new Date(value);return Number.isNaN(date.valueOf())?value:new Intl.DateTimeFormat(undefined,{year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(date)};
const badge = text => {const cls=text==='Flagged for analyst'||text==='Flagged'?'flagged':text==='Compliance review'?'compliance':text==='Needs information'||text==='Needs recheck'||text==='Screening unavailable'?'info':text==='No rule flags'?'ready':'';return `<span class="pill ${cls}">${esc(text)}</span>`};
async function api(url,options){const response=await fetch(url,options);const body=await response.json();if(!response.ok)throw new Error(body.error||'Request failed');return body}
function currentItem(){return state.directory?.applications.find(item=>item.id===state.selected)}
function explainReason(code){
 const descriptions={COMPLEX_OWNERSHIP:'A beneficial owner holds an interest through two or more intermediary companies.',HIGH_RISK_JURISDICTION:'The applicant or a related party is associated with a high-risk jurisdiction.',PEP_PARTY:'A politically exposed person declaration requires review.',POSSIBLE_WATCHLIST_MATCH:'A possible match needs investigation; it is not a confirmed match.',OWNERSHIP_OVER_100:'Declared ownership adds up to more than 100%.',NO_BENEFICIAL_OWNER_IDENTIFIED:'No owner at or above the applicable threshold was identified.',POA_STALE:'The proof of address is older than the policy allows.',PASSPORT_EXPIRED:'An identity document expired before the application date.',NAME_MISMATCH:'A name differs from the corresponding identity document.',DUPLICATE_APPLICATION:'Another open application has the same registration number.',SCREENING_UNAVAILABLE:'Screening did not complete for every required party.'};
 if(code.startsWith('MISSING_DOCUMENT:'))return 'Required document missing: '+label(code.split(':')[1])+'.';
 if(code.startsWith('MISSING_FIELD:'))return 'Required information missing or awaiting review: '+label(code.split(':')[1])+'.';
 if(code.startsWith('DATE_UNREADABLE:'))return 'A required date could not be read: '+label(code.split(':')[1])+'.';
 return descriptions[code]||'Review the case evidence and applicable policy.';
}
function nextStep(item,result){
 if(!item)return 'Choose an application to get started.';
 if(item.category==='Needs recheck')return 'The case has changed since its last check. Run checks again.';
 if(item.review?.current)return 'The latest checks have been reviewed. A separate decision is still required.';
 if(!result){if(item.category==='Not checked')return 'Run checks to assess the application and screen the recorded parties.';return 'Review the case details and run checks to refresh the results.'}
 if(result.status==='COMPLIANCE_REVIEW')return 'Review the reasons and coordinate the required compliance review.';
 if(result.status==='MISSING_DATA')return 'Review the missing or uncertain information before proceeding.';
 if(result.status==='SCREENING_UNAVAILABLE')return 'Screening is incomplete. Hold the application and retry when available.';
 if(result.status==='FLAGGED')return 'Review the flagged evidence before proceeding.';
 return 'Review the screening results and applicable policy before making a decision.';
}
function renderMetrics(){
 if(!state.directory)return;
 const counts=state.directory.counts;
 const cards=[['All applications','in the queue'],['Not checked','awaiting checks'],['Needs information','evidence to review'],['Flagged for analyst','requires attention'],['Compliance review','requires review']];
 $('#metrics').innerHTML=cards.map(([key,caption])=>`<button type="button" class="metric metric-action ${key==='Flagged for analyst'?'flagged-metric':''}" data-filter="${esc(key)}" aria-pressed="${state.filter===key}"><span class="label">${esc(key)}</span><span class="number">${esc(counts[key])}</span><span class="caption">${esc(caption)}</span></button>`).join('');
 $('#nav-count').textContent=counts['All applications'];
}
function renderQueue(){
 if(!state.directory)return;
 const counts=state.directory.counts, filter=$('#directory-filter');
 filter.innerHTML=Object.keys(counts).map(key=>`<option value="${esc(key)}" ${state.filter===key?'selected':''}>${esc(key)} (${esc(counts[key])})</option>`).join('');
 filter.value=state.filter;
 const query=$('#directory-search').value.trim().toLowerCase();
 const matches=state.directory.applications.filter(item=>(state.filter==='All applications'||item.category===state.filter)&&(!query||(item.id+' '+item.company).toLowerCase().includes(query)));
 $('#directory-summary').textContent=matches.length+' applications';
 $('#directory-list').innerHTML=matches.slice(0,state.limit).map(item=>`<button type="button" class="case ${item.category==='Flagged for analyst'?'case-flagged ':''}${state.selected===item.id?'selected':''}" data-open-case="${esc(item.id)}"><div class="case-top"><span class="company-icon">${esc(displayName(item.company).charAt(0))}</span><span><span class="case-title">${esc(displayName(item.company))}</span><span class="case-id">${esc(item.id)}</span></span></div><div class="case-foot">${badge(item.category)}<span>Submitted ${esc(readableDate(item.submitted))}</span></div></button>`).join('')||'<p class="queue-empty">No applications match.</p>';
 $('#directory-more').hidden=matches.length<=state.limit;
}
async function loadDirectory(){
 const data=await api('/api/lab/directory');state.directory=data;
 for(const item of data.applications){if(item.category==='Needs recheck'||item.category==='Not checked'){delete state.assessment[item.id];delete state.agent[item.id];delete state.policyAnswer[item.id];delete state.documentAnswer[item.id]}}
 if(!state.selected&&data.applications.length)state.selected=data.applications[0].id;
 renderMetrics();renderQueue();renderReports();return data;
}
function renderAnswer(result){
 const heading=result.mode==='gemini'?'Gemini · '+esc(result.model):result.mode==='unavailable'?'Assistant unavailable':'Answer held';
 return `<div class="insight"><span class="spark">✳</span><div><strong>${heading}</strong><div class="markdown">${renderMarkdown(result.text)}</div>${result.citations?result.citations.map(c=>`<p><strong>${esc(c.source_id)}</strong> · ${esc(c.description)}${c.review_required?' · requires review':''}<br>“${esc(c.quote)}”</p>`).join(''):''}<p>Verify source relevance and the answer before using it.</p></div></div>`;
}
function renderFields(detail){
 if(!detail.fields?.length)return '';
 const fields=detail.fields.map(f=>`<div class="course-field"><label for="edit-${esc(f.id)}">${esc(f.label)}</label><div class="lab-controls"><input id="edit-${esc(f.id)}" value="${esc(f.stale?f.stale_value:f.value)}" maxlength="160" ${f.available?'':'disabled'}><button type="button" class="action" data-edit-save="${esc(f.id)}" ${f.available?'':'disabled'}>Save</button>${f.edited||f.stale?`<button type="button" class="action" data-edit-reset="${esc(f.id)}">Revert</button>`:''}</div><p>${!f.available?'Source record unavailable.':f.stale?'Source changed. Review and save this value again or revert it.':f.edited?'Edited · original: '+esc(f.original||'(missing)'):f.id.includes('date')?'Use YYYY-MM-DD; leave blank if missing.':'Source record'}</p></div>`).join('');
 return `<details class="case-section" ${state.editOpen[state.selected]?'open':''}><summary>Edit application details</summary><p>Edits are saved locally and require a fresh check. Original records remain unchanged.</p>${fields}</details>`;
}
function renderLinkedReview(){
 if(!state.detail?.linked)return '';
 if(!state.evidence||!state.reviewState)return `<div class="linked-box"><p>Supporting evidence includes fields that require review.</p><button type="button" class="action" data-action="load-evidence">Review supporting documents</button></div>`;
 const corrections=state.reviewState.corrections;
 const fields=['A4:name','A4:address','A4:issue_date'].map(id=>{const item=state.evidence.evidence.find(e=>e.id===id);if(!item)return '';const saved=corrections[id],original=item.original_value??item.value,current=saved&&saved.valid?saved.value:'';return `<div class="review-card"><strong>${esc(label(item.field))}</strong><p>Extracted: ${esc(original)} · confidence ${esc(item.confidence)} · <a href="/document-source/${encodeURIComponent(item.document)}" target="_blank" rel="noopener">View source</a></p><label for="linked-${esc(id)}">Reviewed value${id==='A4:issue_date'?' (YYYY-MM-DD)':''}</label><div class="lab-controls"><input id="linked-${esc(id)}" maxlength="160" value="${esc(current)}" placeholder="Enter the value from the document"><button type="button" class="action" data-linked-field="${esc(id)}">Save review</button></div><p>${saved?(saved.valid?'Reviewed value saved.':'Source changed; review again.'):'Awaiting review.'}</p></div>`}).join('');
 const stage=state.reviewState.supplement;
 const action=stage==='not_attached'?'<button class="action" type="button" data-supplement="attach_supplement">Attach supporting record</button>':stage==='attached'?'<button class="action" type="button" data-supplement="verify_supplement">Record document review</button>':'<span class="pill ready">Supporting record reviewed</span>';
 return `<div class="linked-box"><h4>Review extracted fields</h4><p>Compare each field with its source before saving.</p>${fields}<h4>Additional supporting record</h4><p><a href="/document-source/A5_CASE-A_synthetic_supplement.json" target="_blank" rel="noopener">View supporting record</a> · ${esc(label(stage))}</p><p>The supporting record is an invented demonstration artifact, not an official identity or registry document.</p>${action}<details><summary>Evidence review history (${state.reviewState.audit.length})</summary>${state.reviewState.audit.map(a=>`<p>${esc(readableDate(a.time))} · ${esc(label(a.action))} · ${esc(a.field_id)} · ${esc(a.before_value)} → ${esc(a.after_value)}</p>`).join('')||'<p>No review actions recorded.</p>'}</details><div class="question-block"><label for="document-question">Ask about supporting evidence</label><div class="lab-controls"><input id="document-question" maxlength="800" placeholder="What is the registration number?"><button type="button" class="action" data-action="ask-document">Ask assistant</button></div><div id="document-answer">${state.documentAnswer[state.selected]?renderAnswer(state.documentAnswer[state.selected]):''}</div></div></div>`;
}
function renderReviews(result){
 return result.review_cases.map(review=>`<div class="review-card"><strong>${esc(review.id)} · ${esc(label(review.reason))}</strong><p>${esc(explainReason(review.reason))}</p><p>${review.party_id?'Party: '+esc(review.party_id):'Application-level review'}${review.candidates.length?' · Candidates: '+review.candidates.map(c=>esc(c.entry_id)+' ('+esc(c.score)+')').join(', '):''}</p><p>${review.actions.length?review.actions.map(a=>esc(label(a.action))+' by '+esc(a.actor)+' · '+esc(readableDate(a.time))+(a.rationale?' — '+esc(a.rationale):'')).join('; '):'Awaiting review · no reviewer assigned'}</p><label for="review-${esc(review.id)}">Review notes</label><input id="review-${esc(review.id)}" maxlength="300" placeholder="Record findings or next steps"><div class="actions"><button type="button" class="action" data-review-id="${esc(review.id)}" data-review-action="acknowledged">Acknowledge</button><button type="button" class="action" data-review-id="${esc(review.id)}" data-review-action="escalated">Escalate</button><button type="button" class="action" data-review-id="${esc(review.id)}" data-review-action="reviewed_for_analyst">Record findings</button></div><p>Recorded locally; no role authentication, assignment or notification is available.</p></div>`).join('');
}
function renderCheckDetails(result,detail,item){
 if(!result)return '';
 const reasons=result.reasons.length?'<ul>'+result.reasons.map(code=>`<li><strong>${esc(label(code))}</strong> <span class="muted">(${esc(code)})</span> — ${esc(explainReason(code))}</li>`).join('')+'</ul>':'<p>No rule flags were raised.</p>';
 const screenings=result.screenings.map(s=>{const party=(detail.parties||[]).find(p=>p.id===s.party_id);return `<li><strong>${esc(party?displayName(party.name||party.id):s.party_id)}</strong> · ${esc(s.party_id)} · ${esc(label(s.outcome))}${s.list_version?' · list '+esc(s.list_version):''}</li>`}).join('');
 const policy=result.policy.outcome==='ok'?`Found ${result.policy.sections.length} policy source(s); review relevance below.`:result.policy.outcome==='not_configured'?'Policy search is not configured.':'Policy sources are unavailable for this run.';
 const trace=(result.trace||[]).map(step=>{const names={get_application:'Load application',screen_watchlist:'Screen party',open_review_case:'Open compliance review'};return `<li>${esc(names[step.name]||label(step.name))}${step.party_id?' · '+esc(step.party_id):''}${step.reason_code?' · '+esc(label(step.reason_code)):''}${step.ok===false?' · unsuccessful':step.ok===true?' · completed':''}</li>`}).join('');
 return `<details class="check-details" open><summary>Check results · ${esc(label(result.status))}</summary><p>Checked ${esc(readableTime(item?.checked_at))}. Review these results before generating a summary.</p><h4>Outcome and reasons</h4><p>${esc(result.status_text||'')}</p>${reasons}<h4>Screening results</h4>${screenings?'<ul>'+screenings+'</ul>':'<p>No screening results returned.</p>'}<p>Synthetic watchlist screening; a possible match requires human investigation.</p><h4>Policy and review cases</h4><p>${esc(policy)}</p><p>${result.review_cases.length} compliance review case(s) recorded in this result.</p>${trace?`<details class="check-steps"><summary>Show recorded tool steps</summary><ol>${trace}</ol><p>The steps shown are recorded tool calls, not a separate pass/fail result for each rule.</p></details>`:''}</details>`;
}
function renderAssessment(result){
 if(!result)return '';
 const reasons=result.reasons.length?'<ul>'+result.reasons.map(code=>`<li><strong>${esc(label(code))}</strong> — ${esc(explainReason(code))}</li>`).join('')+'</ul>':'<p>No rule flags were raised.</p>';
 const chains=(result.ownership_chains||[]).map(c=>`<p>Ownership path: ${esc([c.owner_id,...c.intermediate_ids,c.company_id].join(' → '))}</p>`).join('');
 const policies=result.policy.sections.map(s=>`<details class="policy-item"><summary>${esc(s.section_id)} v${esc(s.version)} — ${esc(s.title)}</summary><div class="markdown">${renderMarkdown(s.content)}</div></details>`).join('');
 return `<section><div class="section-title"><h3>Checks &amp; review</h3>${badge(label(result.status))}</div>${reasons}${chains}<p><strong>Screening:</strong> ${result.screenings.map(x=>esc(x.party_id)+': '+esc(label(x.outcome))).join(' · ')||'Unavailable'}</p>${renderReviews(result)}<p class="muted">Screening uses synthetic data. A person investigates potential matches and makes the decision.</p></section><section><div class="section-title"><h3>Policy sources</h3><span class="tag">${result.policy.outcome==='ok'?'AVAILABLE':esc(label(result.policy.outcome))}</span></div>${policies||'<p>Policy sources are unavailable for this run.</p>'}<p>Check each source for relevance to this application.</p><div class="question-block"><label for="policy-question">Ask about policy</label><div class="lab-controls"><input id="policy-question" maxlength="800" placeholder="What evidence is required?"><button type="button" class="action" data-action="ask-policy">Ask assistant</button></div><div id="policy-answer">${state.policyAnswer[state.selected]?renderAnswer(state.policyAnswer[state.selected]):''}</div></div></section>`;
}
function renderDetail(){
 const target=$('#detail'),d=state.detail,item=currentItem();
 if(!state.selected){target.innerHTML='<p class="screen-line">Select an application.</p>';return}
 if(!d){target.innerHTML='<p class="screen-line">Loading application…</p>';return}
 const result=state.assessment[state.selected],summary=state.agent[state.selected];
 const parties=(d.parties||[]).map(p=>`<div class="doc"><span class="doc-icon">◦</span><span class="doc-main"><strong>${esc(displayName(p.name||p.id))}</strong><small>${esc(label(p.role))} · ${esc(p.id)}${p.ownership_pct?' · '+esc(p.ownership_pct)+'% ownership':''}${p.owned_via?' · via '+esc(p.owned_via):''}</small></span></div>`).join('');
 const docs=(d.documents||[]).map(doc=>`<div class="doc"><span class="doc-icon">▤</span><span class="doc-main"><strong>${esc(label(doc.type))}</strong><small>${esc(doc.id)} · ${esc(doc.party_id)}${doc.document_date?' · '+esc(readableDate(doc.document_date)):''}${doc.expiry_date?' · expires '+esc(readableDate(doc.expiry_date)):''}</small></span>${doc.source?`<a class="action-link" href="/document-source/${encodeURIComponent(doc.source)}" target="_blank" rel="noopener">View</a>`:'<span class="tag">RECORD ONLY</span>'}</div>`).join('');
 const audit=(d.audit||[]).map(a=>`<p>${esc(readableDate(a.time))} · ${esc(label(a.action))} · ${esc(a.field||a.field_id)}${a.old_value!==undefined?' · '+esc(a.old_value||'(missing)')+' → '+esc(a.new_value||'(missing)'):''}</p>`).join('');
 target.innerHTML=`<div class="detail-head"><div><div class="eyebrow">APPLICATION ${esc(d.application_id)}</div><h2>${esc(displayName(d.company.name))}</h2><div class="detail-sub">Submitted ${esc(readableDate(item?.submitted))} · ${esc(d.company.jurisdiction||'Jurisdiction unavailable')}${item?.checked_at?' · Last checked '+esc(readableTime(item.checked_at)):''}</div></div>${badge(item?.category||'Not checked')}</div>
 <section><div class="section-title"><h3>Case overview</h3><span class="tag">NEXT STEP</span></div><div class="insight"><span class="spark">✳</span><div><strong>Suggested next step</strong><p>${esc(nextStep(item,result))}</p></div></div><div class="actions"><button type="button" class="action primary" data-action="run-checks">Run checks →</button></div>${renderCheckDetails(result,d,item)}<div class="actions"><button type="button" class="action" data-action="generate-summary" ${result?'':'disabled'}>Generate case summary ✳</button></div><p class="muted">Generating a summary runs fresh checks and sends limited synthetic case facts to Gemini. A previous review of the checks will no longer be current.</p><p class="muted">The recommendation remains held for analyst review.</p>${summary?renderAnswer(summary):''}</section>
 <section><div class="section-title"><h3>Business &amp; ownership</h3><span class="tag">APPLICATION DETAILS</span></div><div class="facts"><div class="fact"><small>BUSINESS NAME</small><strong>${esc(displayName(d.company.name))}</strong></div><div class="fact"><small>REGISTRATION</small><strong>${esc(d.company.registration_number||'Not provided')}</strong></div><div class="fact"><small>JURISDICTION RISK</small><strong>${esc(label(d.company.risk_tier)||'Not available')}</strong></div></div><div class="subheading">Related parties</div>${parties||'<p>No related parties recorded.</p>'}</section>
 <section><div class="section-title"><h3>Document evidence</h3><span class="tag">${d.linked?'SOURCE DOCUMENTS':'DOCUMENT RECORDS'}</span></div>${docs||'<p>No document records available.</p>'}${d.linked?renderLinkedReview():'<p class="muted">File contents are not available for these document records.</p>'}</section>
 ${renderFields(d)}${renderAssessment(result)}
 <section><div class="section-title"><h3>Analyst review</h3>${item?.review?.current?badge('Reviewed'):''}</div>${item?.review?`<p>${item.review.current?'Review recorded':'Previous review (not current)'} · ${esc(readableTime(item.review.time))}</p><p>${esc(item.review.notes)}</p>`:'<p>No analyst review recorded.</p>'}${result?.status==='NO_FLAGS'&&item?.category==='No rule flags'&&!item?.review?.current?`<label for="case-review-notes">Review notes</label><textarea id="case-review-notes" maxlength="500" rows="3" placeholder="Record what you reviewed and any remaining next steps"></textarea><div class="actions"><button class="action" type="button" data-action="record-case-review">Mark checks reviewed</button></div>`:''}<p class="muted">A review records your assessment of these checks. It does not approve the application or record a final decision.</p></section>
 <section><div class="section-title"><h3>Case activity</h3></div>${audit||'<p>No case edits recorded.</p>'}</section>`;
}
async function openCase(id){
 const ticket=++state.request;state.selected=id;state.detail=null;state.evidence=null;state.reviewState=null;renderQueue();renderDetail();
 try{const data=await api('/api/lab/case/'+encodeURIComponent(id));if(ticket!==state.request)return;state.detail=data;renderDetail()}
 catch(error){if(ticket===state.request)$('#detail').innerHTML=`<div class="error">${esc(error.message)}</div>`}
}
async function refreshCase(id,loadEvidence=false){
 const [data,evidence,review]=await Promise.all([api('/api/lab/case/'+encodeURIComponent(id)),loadEvidence?api('/api/documents/CASE-A'):null,loadEvidence?api('/api/linked/5201'):null]);
 if(state.selected!==id)return;
 state.detail=data;state.evidence=evidence;state.reviewState=review;renderDetail();
}
async function loadActivity(){
 try{const data=await api('/api/operations');$('#activity-content').innerHTML=data.events.length?data.events.map(e=>`<div class="event"><strong>${esc(e.case_id)}</strong> · ${esc(readableTime(e.time))} · ${esc(e.message)}</div>`).join(''):'<p>No activity recorded yet.</p>'}
 catch(error){$('#activity-content').textContent='Activity is unavailable.'}
}
function renderReports(){
 if(!state.directory)return;
 const counts=state.directory.counts;
 $('#reports-content').innerHTML=`<div class="report-grid">${Object.entries(counts).map(([name,count])=>`<button type="button" class="report-filter ${name==='Flagged for analyst'?'flagged-report':''}" data-filter="${esc(name)}" aria-pressed="${state.filter===name}"><span>${esc(name)}</span><strong>${esc(count)}</strong></button>`).join('')}</div><p>Select a count to view its applications. Counts reflect checks recorded in this workspace, not elapsed onboarding time.</p>`;
}
async function applyFilter(filter,clearSearch=false){
 state.filter=filter;state.limit=20;if(clearSearch)$('#directory-search').value='';
 const query=$('#directory-search').value.trim().toLowerCase();
 const matches=state.directory.applications.filter(item=>(filter==='All applications'||item.category===filter)&&(!query||(item.id+' '+item.company).toLowerCase().includes(query)));
 renderMetrics();renderQueue();renderReports();
 if(!matches.some(item=>item.id===state.selected)){
  if(matches.length)await openCase(matches[0].id);
  else{state.request++;state.selected=null;state.detail=null;renderDetail()}
 }
}
async function sendReview(button){
 const id=state.selected,reviewId=button.dataset.reviewId,action=button.dataset.reviewAction;
 const rationale=document.getElementById('review-'+reviewId).value;
 const response=await api('/api/lab/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({application_id:id,review_id:reviewId,action,rationale})});
 const entry=state.assessment[id]?.review_cases.find(r=>r.id===reviewId);if(entry)entry.actions=response.actions;
 if(state.selected===id)renderDetail();await loadActivity();
}
async function recordCaseReview(button){
 const id=state.selected,item=currentItem(),notes=$('#case-review-notes').value.trim();
 if(!notes){$('#case-review-notes').focus();return}
 button.disabled=true;
 await api('/api/lab/case-review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({application_id:id,checked_at:item.checked_at,notes})});
 await loadDirectory();if(state.selected===id)renderDetail();await loadActivity();
}
async function saveEdit(button,reset){
 const id=state.selected,field=reset?button.dataset.editReset:button.dataset.editSave,value=reset?'':document.getElementById('edit-'+field).value;
 const data=await api('/api/lab/case/'+encodeURIComponent(id)+'/edit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({field,value,reset})});
 delete state.assessment[id];delete state.agent[id];delete state.policyAnswer[id];state.editOpen[id]=true;await loadDirectory();
 if(state.selected===id){state.detail=data;renderDetail()}await loadActivity();
}
async function updateLinked(button){
 const id=state.selected, action=button.dataset.linkedField?'correct':button.dataset.supplement,field=button.dataset.linkedField||'',value=field?document.getElementById('linked-'+field).value:'';
 await api('/api/linked/5201/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,field,value})});
 delete state.assessment[id];delete state.agent[id];delete state.documentAnswer[id];delete state.policyAnswer[id];await loadDirectory();await refreshCase(id,true);await loadActivity();
}
async function runChecks(button){
 const id=state.selected;button.disabled=true;button.textContent='Running checks…';
 try{const result=await api('/api/lab/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({application_id:id})});state.assessment[id]=result;delete state.agent[id];delete state.policyAnswer[id];await loadDirectory();if(state.selected===id)renderDetail();await loadActivity()}
 catch(error){if(state.selected===id){button.disabled=false;button.textContent='Run checks →';alert(error.message)}}
}
async function generateSummary(button){
 const id=state.selected;button.disabled=true;button.textContent='Preparing summary…';
 try{const result=await api('/api/lab/agent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({application_id:id})});state.agent[id]=result;if(result.assessment)state.assessment[id]=result.assessment;await loadDirectory();if(state.selected===id)renderDetail()}
 catch(error){if(state.selected===id){button.disabled=false;button.textContent='Generate case summary ✳';alert(error.message)}}
}
async function ask(button,type){
 const id=state.selected,input=$('#'+type+'-question'),question=input.value.trim();if(!question){input.focus();return}
 button.disabled=true;const target=$('#'+type+'-answer');target.textContent='Preparing answer…';
 try{const payload=type==='policy'?{application_id:id,question}:{case_id:'CASE-A',question};const result=await api('/api/questions/'+type,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(type==='policy')state.policyAnswer[id]=result;else state.documentAnswer[id]=result;if(state.selected===id)target.innerHTML=renderAnswer(result)}
 catch(error){if(state.selected===id)target.innerHTML=`<div class="error">${esc(error.message)}</div>`}finally{button.disabled=false}
}
document.addEventListener('click',async event=>{
 const filter=event.target.closest('[data-filter]');if(filter){await applyFilter(filter.dataset.filter,true);$('#applications').scrollIntoView({behavior:'smooth'});return}
 const selected=event.target.closest('[data-open-case]');if(selected){await openCase(selected.dataset.openCase);return}
 const button=event.target.closest('[data-action],[data-edit-save],[data-edit-reset],[data-linked-field],[data-supplement],[data-review-id]');if(!button)return;
 try{
  if(button.dataset.editSave){await saveEdit(button,false);return}
  if(button.dataset.editReset){await saveEdit(button,true);return}
  if(button.dataset.linkedField||button.dataset.supplement){button.disabled=true;await updateLinked(button);return}
  if(button.dataset.reviewId){button.disabled=true;await sendReview(button);return}
  if(button.dataset.action==='run-checks'){await runChecks(button);return}
  if(button.dataset.action==='record-case-review'){await recordCaseReview(button);return}
  if(button.dataset.action==='generate-summary'){await generateSummary(button);return}
  if(button.dataset.action==='load-evidence'){button.disabled=true;await refreshCase(state.selected,true);return}
  if(button.dataset.action==='ask-policy'){await ask(button,'policy');return}
  if(button.dataset.action==='ask-document'){await ask(button,'document');return}
 }catch(error){button.disabled=false;alert(error.message)}
});
$('#directory-filter').addEventListener('change',event=>{applyFilter(event.target.value)});
$('#directory-search').addEventListener('input',()=>{state.limit=20;renderQueue()});
$('#directory-more').addEventListener('click',()=>{state.limit+=20;renderQueue()});
(async()=>{try{await loadDirectory();if(state.selected)await openCase(state.selected);await loadActivity()}catch(error){$('#detail').innerHTML=`<div class="error">Could not load applications: ${esc(error.message)}</div>`}})();
