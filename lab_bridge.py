"""Adapter around the synthetic Day 4–10 course implementation."""
import json, os, re, sys, threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'lab' / 'starter-code'))
from kyc import data_layer, rules, tools, routing, policy_search

_review_lock = threading.Lock()
REVIEW_STORE = ROOT / 'state' / 'lab-review-cases.json'

def run_course_case(application_id):
    if not isinstance(application_id, str) or not re.fullmatch(r'SPECIMEN-APP-\d{4}', application_id):
        raise ValueError('Use an application ID such as SPECIMEN-APP-5154.')
    pack = data_layer.get_application_pack(application_id)
    if pack is None: raise ValueError('Application not found.')
    application = tools.get_application(application_id)
    trace = [{'kind':'tool','name':'get_application','ok':True,'party_ids':[p['party_id'] for p in application['parties']]}]
    screenings = routing.screen_every_party(pack, tools.FaultPlan(), trace)
    status, reasons = rules.check_application(pack, screenings)
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
            'note':'Synthetic course rules and watchlist. A person reviews and decides.'}

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
    pack = data_layer.get_application_pack(application_id)
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
