"""Adapter around the synthetic Day 4–10 course implementation."""
import json, os, re, sys, threading
from datetime import datetime, timezone
from pathlib import Path
import linked_case

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'lab' / 'starter-code'))
from kyc import data_layer, rules, tools, routing, policy_search

_review_lock = threading.Lock()
REVIEW_STORE = ROOT / 'state' / 'lab-review-cases.json'

def ownership_evidence(pack):
    """Identify intermediary chains without exposing names or inventing links."""
    by_id = {p['party_id']:p for p in pack['parties']}
    chains = []
    for person in rules.people(pack):
        if 'OWNER' not in person.get('role','') or not person.get('ownership_pct'):
            continue
        via, seen, intermediaries = person.get('owned_via_party_id'), {person['party_id']}, []
        while via and via not in seen:
            seen.add(via)
            owner = by_id.get(via)
            if not owner: break
            intermediaries.append(owner['party_id'])
            via = owner.get('owned_via_party_id')
        if len(intermediaries) >= 2 and not via:
            chains.append({'owner_id':person['party_id'], 'intermediate_ids':intermediaries,
                           'company_id':pack['company']['party_id']})
    return chains

def run_course_case(application_id, review_state=None, fields=None):
    if not isinstance(application_id, str) or not re.fullmatch(r'SPECIMEN-APP-\d{4}', application_id):
        raise ValueError('Use an application ID such as SPECIMEN-APP-5154.')
    linked = application_id == linked_case.APPLICATION_ID
    pack, extracted = linked_case.build_pack(review_state) if linked else (data_layer.get_application_pack(application_id, fields), None)
    if pack is None: raise ValueError('Application not found.')
    application = {'parties':[{'party_id':p['party_id']} for p in rules.parties_to_screen(pack)]} if linked else tools.get_application(application_id, fields)
    trace = [{'kind':'tool','name':'get_application','ok':True,'party_ids':[p['party_id'] for p in application['parties']]}]
    screenings = routing.screen_every_party(pack, tools.FaultPlan(), trace)
    status, reasons = rules.check_application(pack, screenings)
    if linked:
        # The original practice pack does not establish a complete director list or PEP declarations.
        extra = []
        if not extracted['supplement_ready']: extra += ['MISSING_FIELD:director_list','MISSING_FIELD:declared_pep']
        if extracted['review_items']: extra.append('MISSING_FIELD:document_review')
        proof = rules.document(pack, 'PROOF_OF_ADDRESS')
        if proof and proof.get('name_on_document') and rules.normalise_name(proof['name_on_document']) != rules.normalise_name(pack['company']['full_name'] or ''):
            extra.append('MISSING_FIELD:proof_of_address_name_mismatch')
        proof_date = rules.as_date(proof.get('document_date')) if proof else None
        application_date = rules.as_date(pack['application_date'])
        if proof_date and application_date and proof_date > application_date:
            extra.append('MISSING_FIELD:proof_of_address_after_application')
        reasons = sorted(set(reasons + extra))
        status = rules.status_for(reasons)
    reviews = []
    with _review_lock:
        for reason in reasons:
            if rules.reason_status(reason) == 'COMPLIANCE_REVIEW':
                parties = [pid for pid, result in screenings.items() if result['outcome'] == 'POSSIBLE_MATCH'] if reason == 'POSSIBLE_WATCHLIST_MATCH' else ['']
                if not parties: raise RuntimeError('A possible match has no screening evidence; case held.')
                for party_id in parties:
                    review = tools.open_review_case(application_id, reason, party_id, REVIEW_STORE)
                    trace.append({'kind':'tool','name':'open_review_case','ok':True,'reason_code':reason,'party_id':party_id})
                    candidates = screenings[party_id]['candidates'] if party_id else []
                    reviews.append({'reason':reason, 'id':review['review_case_id'], 'party_id':party_id, 'candidates':candidates})
        stored = json.loads(REVIEW_STORE.read_text(encoding='utf-8')) if REVIEW_STORE.exists() else []
        for review in reviews:
            row = next(c for c in stored if c['review_case_id'] == review['id'])
            row['candidates'] = review['candidates']
            review['actions'] = row.get('actions', [])
        if reviews: REVIEW_STORE.write_text(json.dumps(stored, indent=2), encoding='utf-8')
    policy = retrieve_policy(pack['company']['country_code'])
    # No names or identity numbers are returned to the browser or model.
    return {'application_id':application_id, 'status':status, 'status_text':rules.display_text(status),
            'reasons':reasons, 'screenings':[{'party_id':pid, 'outcome':item['outcome'], 'list_version':item['list_version']} for pid,item in screenings.items()],
            'review_cases':reviews, 'policy':policy,
            'recommendation_held':True,
            'trace':trace,
            'linked_document_case': linked_case.DOCUMENT_CASE if linked else None,
            'document_review_items': extracted['review_items'] if linked else [],
            'case_notes': (['Synthetic application date: 2026-08-15.',
                'Synthetic supplemental records reviewed.' if extracted['supplement_ready'] else 'Director list and PEP declarations have not been verified.',
                'Low-confidence fields require analyst review before use.'] if linked else []),
            'ownership_chains': ownership_evidence(pack) if 'COMPLEX_OWNERSHIP' in reasons else [],
            'note':'Synthetic records and watchlist. A person reviews and decides.'}

def retrieve_policy(jurisdiction):
    mode = os.environ.get('KYC_POLICY_SEARCH', 'off').lower()
    if mode == 'off':
        policy = {'mode':'off', 'outcome':'not_configured', 'sections':[]}
    elif mode == 'azure':
        try:
            sections = policy_search.search_policy(jurisdiction, os.environ.get('KYC_POLICY_AS_OF_DATE','2026-11-05'))
            if not sections: raise policy_search.PolicyUnavailable('No applicable sections returned.')
            policy = {'mode':'azure','outcome':'ok','sections':sections}
        except policy_search.PolicyUnavailable:
            policy = {'mode':'azure','outcome':'unavailable','sections':[]}
    else:
        policy = {'mode':mode,'outcome':'unavailable','sections':[]}
    return policy

def policy_for_case(application_id):
    if not isinstance(application_id, str) or not re.fullmatch(r'SPECIMEN-APP-\d{4}', application_id): raise ValueError('Use an application ID such as SPECIMEN-APP-5154.')
    pack = linked_case.build_pack()[0] if application_id == linked_case.APPLICATION_ID else data_layer.get_application_pack(application_id)
    if pack is None: raise ValueError('Application not found.')
    return retrieve_policy(pack['company']['country_code'])

def record_review(application_id, review_id, action, rationale=''):
    if action not in ('acknowledged','escalated','reviewed_for_analyst'):
        raise ValueError('Choose acknowledge, escalate, or return to analyst.')
    if not isinstance(rationale, str) or len(rationale) > 300: raise ValueError('Rationale must be at most 300 characters.')
    rationale = rationale.strip()
    if action == 'reviewed_for_analyst' and len(rationale) < 10: raise ValueError('Enter a synthetic review rationale of at least 10 characters.')
    with _review_lock:
        rows = json.loads(REVIEW_STORE.read_text(encoding='utf-8')) if REVIEW_STORE.exists() else []
        row = next((r for r in rows if r['review_case_id'] == review_id and r['application_id'] == application_id), None)
        if row is None: raise ValueError('Review case not found for this application.')
        actions = row.setdefault('actions', [])
        if not actions or (actions[-1]['action'],actions[-1].get('rationale','')) != (action,rationale):
            actions.append({'action':action, 'actor':'demo reviewer', 'time':datetime.now(timezone.utc).isoformat(timespec='seconds'), 'rationale':rationale})
            REVIEW_STORE.write_text(json.dumps(rows, indent=2), encoding='utf-8')
        return {'review_id':review_id,'actions':actions, 'message':'Recorded for human review; the case remains open.'}

def list_review_cases():
    with _review_lock:
        return json.loads(REVIEW_STORE.read_text(encoding='utf-8')) if REVIEW_STORE.exists() else []
