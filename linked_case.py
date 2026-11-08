"""A new synthetic application assembled from the CASE-A practice documents.

It does not modify, overwrite or imply a match with the original course CSVs.
"""
import document_bridge

APPLICATION_ID = 'SPECIMEN-APP-5201'
DOCUMENT_CASE = 'CASE-A'

def build_pack():
    extracted = document_bridge.extract_case(DOCUMENT_CASE)
    fields = {item['id']:item for item in extracted['evidence']}
    def verified(field):
        item = fields.get(field)
        return item['value'] if item and not item['review_required'] else None
    def party(party_id, role, name, dob=None, country=None, ownership=None):
        return {'party_id':party_id,'application_id':APPLICATION_ID,'party_type':'COMPANY' if role=='APPLICANT_COMPANY' else 'PERSON',
                'role':role,'full_name':name,'date_of_birth':dob,'incorporation_date':None,'registration_number':None,
                'country_code':country,'ownership_pct':ownership,'owned_via_party_id':None,'declared_pep':None,
                'risk_tier': {'XA':'LOW','XB':'LOW'}.get(country)}
    company = party('SPECIMEN-PTY-8901','APPLICANT_COMPANY',verified('A1:company_name'), country=verified('A1:jurisdiction'))
    company['incorporation_date']=verified('A1:date_of_incorporation')
    company['registration_number']=verified('A1:registration_number')
    owners=[party('SPECIMEN-PTY-8902','BENEFICIAL_OWNER',verified('A2:owners[1].name'),verified('A2:owners[1].date_of_birth'),verified('A2:owners[1].nationality'),verified('A2:owners[1].ownership_pct')),
            party('SPECIMEN-PTY-8903','BENEFICIAL_OWNER',verified('A2:owners[2].name'),verified('A2:owners[2].date_of_birth'),verified('A2:owners[2].nationality'),verified('A2:owners[2].ownership_pct'))]
    docs=[{'document_id':'SPECIMEN-DOC-8901','party_id':company['party_id'],'doc_type':'CERTIFICATE_OF_INCORPORATION','name_on_document':company['full_name'], 'document_date':None,'expiry_date':None},
          {'document_id':'SPECIMEN-DOC-8902','party_id':company['party_id'],'doc_type':'OWNERSHIP_DECLARATION','name_on_document':verified('A2:company_name'),'document_date':None,'expiry_date':None},
          {'document_id':'SPECIMEN-DOC-8904','party_id':company['party_id'],'doc_type':'PROOF_OF_ADDRESS','name_on_document':verified('A4:name'),'document_date':verified('A4:issue_date'),'expiry_date':None}]
    identity_name = ' '.join(filter(None,[verified('A3:given_names'),verified('A3:surname')]))
    # Do not attach an identity document to an owner unless both name and DOB agree.
    if identity_name and owners[0]['full_name'] and identity_name.casefold() == owners[0]['full_name'].casefold() and verified('A3:date_of_birth') and verified('A3:date_of_birth') == owners[0]['date_of_birth']:
        docs.append({'document_id':'SPECIMEN-DOC-8903','party_id':owners[0]['party_id'],'doc_type':'PASSPORT','name_on_document':identity_name,'document_date':None,'expiry_date':verified('A3:expiry_date')})
    return {'application_id':APPLICATION_ID, 'application_date':'2026-08-15', 'company':company, 'parties':owners,
            'documents':docs, 'jurisdiction_risk':company['risk_tier'], 'duplicate_of':None}, extracted
