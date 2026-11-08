"""Run applicable Day 7 reference checks against the Pineway KYC adapter.

Gemini and unsupported original replay/summary trajectory checks are not evaluated.
"""
import json, os, sys, tempfile
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import lab_bridge

def main():
    suite=yaml.safe_load((ROOT/'evals/cases/reference_cases.yaml').read_text(encoding='utf-8'))
    rows=[]; original_store=lab_bridge.REVIEW_STORE; old_mode=os.environ.get('KYC_POLICY_SEARCH')
    try:
        os.environ['KYC_POLICY_SEARCH']='off'
        with tempfile.TemporaryDirectory() as folder:
            for case in suite['cases']:
                # Original summary order and replay-specific assertions cannot be proved here.
                if case.get('order') or case['input'].get('fault') or case['input'].get('fields'):
                    rows.append({'id':case['eval_id'],'verdict':'SKIPPED','reason':'Original replay/fault/summary path not exercised'}); continue
                lab_bridge.REVIEW_STORE=Path(folder)/(case['eval_id']+'.json')
                try:
                    result=lab_bridge.run_course_case(case['input']['application_id'])
                    expected=case['expected']; failures=[]; trace=result['trace']
                    if result['status']!=expected['status']: failures.append('status')
                    if sorted(result['reasons'])!=sorted(expected['reasons']): failures.append('reasons')
                    names=[s['name'] for s in trace]
                    if any(n not in names for n in case.get('must_call',[])): failures.append('must_call')
                    if case.get('must_call_per_party'):
                        listed={p for s in trace if s['name']=='get_application' for p in s['party_ids']}
                        screened={s['party_id'] for s in trace if s['name']=='screen_watchlist' and s['ok']}
                        if not listed or listed-screened: failures.append('must_call_per_party')
                    if 'max_tool_calls' in case and len(trace)>case['max_tool_calls']: failures.append('max_tool_calls')
                    state=case.get('expected_state')
                    if state and (len(result['review_cases'])!=state['review_cases'] or sorted(r['reason'] for r in result['review_cases'])!=sorted(state['review_case_reasons'])): failures.append('review_cases')
                    rows.append({'id':case['eval_id'],'verdict':'FAIL' if failures else 'PASS','failures':failures})
                except Exception as exc:
                    rows.append({'id':case['eval_id'],'verdict':'ERROR','error':type(exc).__name__})
    finally:
        lab_bridge.REVIEW_STORE=original_store
        if old_mode is None: os.environ.pop('KYC_POLICY_SEARCH',None)
        else: os.environ['KYC_POLICY_SEARCH']=old_mode
    for row in rows: print(json.dumps(row))
    print(json.dumps({'counts':{v:sum(r['verdict']==v for r in rows) for v in ('PASS','FAIL','ERROR','SKIPPED')},'scope':'deterministic adapter only; Gemini, live search and replay summary excluded'}))
    return 1 if any(r['verdict'] in ('FAIL','ERROR') for r in rows) else 0

if __name__=='__main__': sys.exit(main())
