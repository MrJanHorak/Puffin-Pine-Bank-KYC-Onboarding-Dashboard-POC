"""Adapter around the synthetic Day 4–10 course implementation."""
import os, re, sys, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'lab' / 'starter-code'))
from kyc import data_layer, rules, tools, routing, policy_search

_review_lock = threading.Lock()
REVIEW_STORE = ROOT / 'state' / 'lab-review-cases.json'

def run_course_case(application_id):
    if not isinstance(application_id, str) or not re.fullmatch(r'SPECIMEN-APP-\d{4}', application_id):
        raise ValueError('Use a course case ID such as SPECIMEN-APP-5154.')
    pack = data_layer.get_application_pack(application_id)
    if pack is None: raise ValueError('Course case not found.')
    trace = []
    screenings = routing.screen_every_party(pack, tools.FaultPlan(), trace)
    status, reasons = rules.check_application(pack, screenings)
    reviews = []
    with _review_lock:
        for reason in reasons:
            if rules.reason_status(reason) == 'COMPLIANCE_REVIEW':
                matched = next((pid for pid, result in screenings.items() if result['outcome'] == 'POSSIBLE_MATCH'), '')
                review = tools.open_review_case(application_id, reason, matched if reason == 'POSSIBLE_WATCHLIST_MATCH' else '', REVIEW_STORE)
                reviews.append({'reason':reason, 'id':review['review_case_id']})
    mode = os.environ.get('KYC_POLICY_SEARCH', 'off').lower()
    if mode == 'off':
        policy = {'mode':'off', 'outcome':'not_configured', 'sections':[]}
    elif mode == 'azure':
        try:
            sections = policy_search.search_policy(pack['company']['country_code'], os.environ.get('KYC_POLICY_AS_OF_DATE','2026-11-05'))
            if not sections: raise policy_search.PolicyUnavailable('No applicable sections returned.')
            policy = {'mode':'azure','outcome':'ok','sections':sections}
        except policy_search.PolicyUnavailable:
            policy = {'mode':'azure','outcome':'unavailable','sections':[]}
    else:
        policy = {'mode':mode,'outcome':'unavailable','sections':[]}
    # No names or identity numbers are returned to the browser or model.
    return {'application_id':application_id, 'status':status, 'status_text':rules.display_text(status),
            'reasons':reasons, 'screenings':[{'party_id':pid, 'outcome':item['outcome'], 'list_version':item['list_version']} for pid,item in screenings.items()],
            'review_cases':reviews, 'policy':policy,
            'recommendation_held':any(r.startswith(('MISSING_FIELD:', 'MISSING_DOCUMENT:', 'DATE_UNREADABLE:')) or r == 'SCREENING_UNAVAILABLE' for r in reasons) or policy['outcome'] != 'ok',
            'note':'Synthetic course rules and watchlist. A person reviews and decides.'}
