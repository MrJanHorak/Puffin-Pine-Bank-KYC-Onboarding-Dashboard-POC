"""Scoped, auditable synthetic edits using the course data-layer overrides."""
import hashlib, json
from datetime import date, datetime, timezone

FIELD_LABELS={'application_date':'Application date','incorporation_date':'Incorporation date',
              'proof_of_address_date':'Proof-of-address date','director_full_name':'First director name'}
DATE_FIELDS={'application_date','incorporation_date','proof_of_address_date'}

def init(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS course_edits
        (application_id TEXT NOT NULL, field TEXT NOT NULL, value TEXT NOT NULL, base_hash TEXT NOT NULL,
         PRIMARY KEY(application_id,field));
        CREATE TABLE IF NOT EXISTS course_edit_audit
        (id INTEGER PRIMARY KEY AUTOINCREMENT, application_id TEXT NOT NULL, time TEXT NOT NULL,
         field TEXT NOT NULL, old_value TEXT, new_value TEXT, action TEXT NOT NULL);''')

def base_pack(data_layer, application_id):
    pack=data_layer.get_application_pack(application_id)
    if pack is None: raise ValueError('Application not found.')
    return pack

def base_hash(pack):
    return hashlib.sha256(json.dumps(pack,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()

def original_values(pack):
    director=next((p for p in pack['parties'] if (p.get('role') or '').startswith('DIRECTOR')),None)
    proof=next((d for d in pack['documents'] if d.get('doc_type')=='PROOF_OF_ADDRESS'),None)
    return {'application_date':pack.get('application_date'), 'incorporation_date':pack['company'].get('incorporation_date'),
            'director_full_name':director.get('full_name') if director else None,
            'proof_of_address_date':proof.get('document_date') if proof else None}, director is not None, proof is not None

def snapshot(db,data_layer,application_id):
    pack=base_pack(data_layer,application_id); original,has_director,has_proof=original_values(pack); base=base_hash(pack)
    rows={r['field']:dict(r) for r in db.execute('SELECT field,value,base_hash FROM course_edits WHERE application_id=?',(application_id,))}
    stale=[f for f,row in rows.items() if row['base_hash']!=base]
    overrides={f:row['value'] for f,row in rows.items() if row['base_hash']==base}
    effective=data_layer.get_application_pack(application_id,overrides) if overrides else pack
    values,_,_=original_values(effective)
    fields=[]
    for field,label in FIELD_LABELS.items():
        available=(field!='director_full_name' or has_director) and (field!='proof_of_address_date' or has_proof)
        fields.append({'id':field,'label':label,'value':values[field] or '', 'original':original[field] or '',
                       'edited':field in overrides,'stale':field in stale,'stale_value':rows[field]['value'] if field in stale else None,'available':available})
    return {'application_id':application_id,'overrides':overrides,'stale_fields':stale,'fields':fields,
            'company':{'name':effective['company'].get('full_name'),'registration_number':effective['company'].get('registration_number'),
                       'jurisdiction':effective['company'].get('country_code'),'risk_tier':effective['company'].get('risk_tier')},
            'parties':[{'id':p['party_id'],'role':p['role'],'name':p.get('full_name'),'ownership_pct':p.get('ownership_pct'),
                        'owned_via':p.get('owned_via_party_id')} for p in effective['parties']],
            'documents':[{'id':d['document_id'],'type':d['doc_type'],'party_id':d['party_id'],
                          'document_date':d.get('document_date'),'expiry_date':d.get('expiry_date')} for d in effective['documents']],
            'audit':[dict(row) for row in db.execute('SELECT time,field,old_value,new_value,action FROM course_edit_audit WHERE application_id=? ORDER BY id DESC',(application_id,))]}

def change(db,data_layer,application_id,field,value,reset=False):
    if field not in FIELD_LABELS: raise ValueError('This field is not available for editing.')
    if not isinstance(reset,bool): raise ValueError('Invalid edit action.')
    if not reset:
        if not isinstance(value,str) or len(value)>160: raise ValueError('Enter a value of at most 160 characters.')
        value=value.strip()
        if field in DATE_FIELDS and value:
            try:
                if date.fromisoformat(value).isoformat()!=value: raise ValueError()
            except ValueError: raise ValueError('Use a valid date in YYYY-MM-DD format, or leave it blank to mark missing.') from None
        if field=='director_full_name' and len(value)<2: raise ValueError('Enter the synthetic director name; it cannot be blank.')
    db.execute('BEGIN IMMEDIATE'); current=snapshot(db,data_layer,application_id)
    field_info=next(f for f in current['fields'] if f['id']==field)
    if not field_info['available']: raise ValueError('The source record for this field is missing; a field edit cannot create it.')
    prior=db.execute('SELECT value,base_hash FROM course_edits WHERE application_id=? AND field=?',(application_id,field)).fetchone()
    if reset:
        if prior is None: return current
        db.execute('DELETE FROM course_edits WHERE application_id=? AND field=?',(application_id,field))
        new_value=field_info['original']; action='revert'
    else:
        base=base_hash(base_pack(data_layer,application_id))
        if prior and prior['value']==value and prior['base_hash']==base: return current
        db.execute('INSERT OR REPLACE INTO course_edits(application_id,field,value,base_hash) VALUES (?,?,?,?)',(application_id,field,value,base))
        new_value=value; action='edit'
    db.execute('INSERT INTO course_edit_audit(application_id,time,field,old_value,new_value,action) VALUES (?,?,?,?,?,?)',
        (application_id,datetime.now(timezone.utc).isoformat(timespec='seconds'),field,prior['value'] if prior else field_info['value'],new_value,action))
    return snapshot(db,data_layer,application_id)

def revisions(db):
    """Stable per-case edit revision; does not expose values in the directory."""
    grouped={}
    for row in db.execute('SELECT application_id,field,value,base_hash FROM course_edits ORDER BY application_id,field'):
        grouped.setdefault(row['application_id'],{})[row['field']]={'value':row['value'],'base_hash':row['base_hash']}
    return {app_id:hashlib.sha256(json.dumps(fields,sort_keys=True).encode('utf-8')).hexdigest() for app_id,fields in grouped.items()}
