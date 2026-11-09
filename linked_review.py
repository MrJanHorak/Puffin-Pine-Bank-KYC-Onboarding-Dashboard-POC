"""Scoped human-review state for the single linked synthetic application.

This is a POC adapter inspired by the lab's extraction/review/case tools;
it does not replace the lab's CaseManagementAPI or allow arbitrary writes.
"""
import hashlib, json, sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

CASE_ID = 'SPECIMEN-APP-5201'
EDITABLE = {'A4:name', 'A4:address', 'A4:issue_date'}
SUPPLEMENT = Path(__file__).resolve().parent / 'document_lab/fixtures/documents/A5_CASE-A_synthetic_supplement.json'
DOCS = SUPPLEMENT.parent
SCHEMA = Path(__file__).resolve().parent / 'document_lab/starter-code/schema/kyc_extraction_schema.yaml'

def init(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS linked_current
      (field_id TEXT PRIMARY KEY, value TEXT NOT NULL, source_hash TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS linked_audit
      (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT NOT NULL, action TEXT NOT NULL,
       field_id TEXT NOT NULL, before_value TEXT NOT NULL, after_value TEXT NOT NULL, source_hash TEXT NOT NULL);''')

def digest(value): return hashlib.sha256(value.encode('utf-8')).hexdigest()
def source_digest(field, item):
    source = DOCS / item['document']
    if source.name != item['document']: raise ValueError('Invalid document source.')
    hasher = hashlib.sha256((field+'\n'+item['value']).encode('utf-8'))
    hasher.update(source.read_bytes())
    sidecar = source.with_suffix('.ocr.json')
    if sidecar.exists(): hasher.update(sidecar.read_bytes())
    hasher.update(SCHEMA.read_bytes())
    return hasher.hexdigest()
def supplement():
    raw = SUPPLEMENT.read_text(encoding='utf-8')
    return json.loads(raw), digest(raw)

def snapshot(db, extracted):
    evidence = {x['id']:x for x in extracted['evidence']}
    rows = {r['field_id']:dict(r) for r in db.execute('SELECT field_id,value,source_hash FROM linked_current')}
    corrections = {}
    for field in EDITABLE:
        source = evidence.get(field); saved = rows.get(field)
        current_hash = source_digest(field,source) if source else None
        if saved and source:
            corrections[field] = {'value':saved['value'], 'original':source['value'],
                                  'valid':saved['source_hash']==current_hash}
    _, bundle_hash = supplement()
    bundle = rows.get('SUPPLEMENT')
    bundle_state = bundle['value'] if bundle and bundle['source_hash']==bundle_hash else 'not_attached'
    return {'corrections':corrections, 'supplement':bundle_state,
            'audit':[dict(x) for x in db.execute('SELECT time,action,field_id,before_value,after_value FROM linked_audit ORDER BY id DESC')]}

def execute(db, extracted, action, field='', value=''):
    if action not in ('correct','attach_supplement','verify_supplement'): raise ValueError('Unknown review action.')
    db.execute('BEGIN IMMEDIATE')
    current = snapshot(db, extracted)
    if action == 'correct':
        if field not in EDITABLE: raise ValueError('This field cannot be edited in the demo.')
        if not isinstance(value,str) or not value.strip() or len(value.strip())>160: raise ValueError('Enter a non-empty synthetic value of at most 160 characters.')
        value = value.strip()
        if field == 'A4:issue_date':
            try:
                if date.fromisoformat(value).isoformat() != value: raise ValueError()
            except ValueError: raise ValueError('Use a valid date in YYYY-MM-DD format.') from None
        item = next((x for x in extracted['evidence'] if x['id']==field),None)
        if not item or not item['review_required']: raise ValueError('The original field is not available for review.')
        source_hash = source_digest(field,item)
        existing = current['corrections'].get(field)
        before = existing['value'] if existing and existing['valid'] else item['value']
        if existing and existing['valid'] and before == value: return current
    else:
        field='SUPPLEMENT'; _, source_hash=supplement()
        before=current['supplement']
        if action=='attach_supplement':
            if before in ('attached','verified'): return current
            value='attached'
        else:
            if before=='verified': return current
            if before!='attached': raise ValueError('Attach and inspect the sample supplement before recording its review.')
            value='verified'
    db.execute('INSERT OR REPLACE INTO linked_current(field_id,value,source_hash) VALUES (?,?,?)',(field,value,source_hash))
    db.execute('INSERT INTO linked_audit(time,action,field_id,before_value,after_value,source_hash) VALUES (?,?,?,?,?,?)',
               (datetime.now(timezone.utc).isoformat(timespec='seconds'),action,field,before,value,source_hash))
    return snapshot(db, extracted)
