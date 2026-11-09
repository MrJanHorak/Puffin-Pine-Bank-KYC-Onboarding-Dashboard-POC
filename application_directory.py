"""A local index of synthetic applications and their last explicitly run checks."""
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import course_edits

ROOT = Path(__file__).resolve().parent
CATEGORIES = ('Not checked','Needs recheck','Needs information','Screening unavailable',
              'Compliance review','Flagged for analyst','No rule flags')
STATUS_TO_CATEGORY = {'MISSING_DATA':'Needs information','SCREENING_UNAVAILABLE':'Screening unavailable',
                      'COMPLIANCE_REVIEW':'Compliance review','FLAGGED':'Flagged for analyst','NO_FLAGS':'No rule flags'}

def init(db):
    db.execute('''CREATE TABLE IF NOT EXISTS lab_runs
      (application_id TEXT PRIMARY KEY, checked_at TEXT NOT NULL, status TEXT NOT NULL,
       reasons TEXT NOT NULL, source_revision TEXT NOT NULL, linked_revision TEXT NOT NULL)''')

def source_revision():
    """Detect changes to the local rule engine and included synthetic case sources."""
    files = [ROOT/'lab/fixtures/data'/name for name in ('applications.csv','parties.csv','documents.csv','jurisdictions.csv','watchlist.csv')]
    files += [ROOT/'lab/starter-code/kyc'/name for name in ('data_layer.py','rules.py','screening.py','routing.py','tools.py','circuit_breaker.py')]
    files += [ROOT/'lab/starter-code/config/rules.yaml',ROOT/'app.py',ROOT/'lab_bridge.py',ROOT/'linked_case.py',ROOT/'course_edits.py',ROOT/'document_bridge.py',ROOT/'linked_review.py',ROOT/'document_lab/starter-code/schema/kyc_extraction_schema.yaml']
    files += [ROOT/'document_lab/starter-code/kit'/name for name in ('common.py','extract.py','review.py')]
    files += sorted(p for p in (ROOT/'document_lab/fixtures/documents').iterdir() if p.is_file())
    h=hashlib.sha256()
    for path in files:
        h.update(str(path.relative_to(ROOT)).encode('utf-8')); h.update(b'\0'); h.update(path.read_bytes()); h.update(b'\0')
    return h.hexdigest()

def linked_revision(state):
    if state is None: return ''
    relevant={'corrections':state.get('corrections',{}),'supplement':state.get('supplement')}
    return hashlib.sha256(json.dumps(relevant,sort_keys=True).encode('utf-8')).hexdigest()

def save_run(db, result, source_rev, case_revision=''):
    db.execute('''INSERT OR REPLACE INTO lab_runs(application_id,checked_at,status,reasons,source_revision,linked_revision)
      VALUES (?,?,?,?,?,?)''', (result['application_id'], datetime.now(timezone.utc).isoformat(timespec='seconds'),
      result['status'],json.dumps(result['reasons']),source_rev,case_revision))

def directory(db, data_layer, linked_id, linked_state):
    runs={row['application_id']:dict(row) for row in db.execute('SELECT * FROM lab_runs')}
    rev=source_revision(); tables=data_layer.tables(); items=[]; edits=course_edits.revisions(db)
    for app_id, app in tables['applications'].items():
        company=data_layer.company_of(app_id)
        items.append({'id':app_id,'company':company.get('full_name') or 'Unknown company', 'submitted':app['application_date']})
    items.append({'id':linked_id,'company':'Halden Logistics Ltd','submitted':'2026-08-15'})
    for item in items:
        run=runs.get(item['id'])
        if not run: item.update(category='Not checked',checked_at=None,reasons=[],last_status=None)
        elif run['source_revision'] != rev or run['linked_revision'] != (linked_revision(linked_state) if item['id']==linked_id else edits.get(item['id'],'')):
            item.update(category='Needs recheck',checked_at=run['checked_at'],reasons=json.loads(run['reasons']),last_status=run['status'])
        else:
            item.update(category=STATUS_TO_CATEGORY.get(run['status'],'Needs recheck'),checked_at=run['checked_at'],reasons=json.loads(run['reasons']),last_status=run['status'])
    items.sort(key=lambda x:x['id'])
    return {'applications':items,'counts':{'All applications':len(items), **{name:sum(i['category']==name for i in items) for name in CATEGORIES}},
            'note':'Statuses reflect checks run in this local demo. Unchecked cases have not been screened. All decisions remain with a person.'}
