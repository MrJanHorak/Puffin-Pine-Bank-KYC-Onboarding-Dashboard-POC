"""Read-only extraction of the separate synthetic document practice pack."""
import copy, sys
import linked_review
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent / 'document_lab' / 'starter-code'
sys.path.insert(0, str(ROOT))
from kit.common import list_documents, doc_type_of
from kit.extract import OfflineExtractor
from kit.review import review_items

def extract_case(case_id):
    if case_id not in ('CASE-A', 'CASE-B', 'CASE-C'): raise ValueError('Select one of the synthetic document cases.')
    schema = yaml.safe_load((ROOT / 'schema' / 'kyc_extraction_schema.yaml').read_text(encoding='utf-8'))
    extractor = OfflineExtractor()
    evidence, reviews = [], []
    for path in list_documents(case_id):
        document_id = path.name.split('_')[0]
        record = extractor.extract(path)
        items = review_items(document_id, doc_type_of(path), record, schema)
        reviews.extend({'document_id':document_id, 'field':item['field'], 'reason':item['reason']} for item in items)
        for field, data in record['fields'].items():
            entries = [(field, data)] if field != 'owners' else [(f'owners[{i}].{name}', val) for i, owner in enumerate(data, start=1) for name,val in owner.items()]
            for name, val in entries:
                if not isinstance(val, dict) or val.get('value') is None: continue
                evidence.append({'id':document_id+':'+name, 'document_id':document_id, 'document':path.name,
                                 'field':name, 'value':str(val['value']), 'confidence':val.get('confidence'),
                                 'source':record['source'], 'review_required':any(item['field']==name for item in items)})
    return {'case_id':case_id,'evidence':evidence,'review_items':reviews,
            'notice':('This synthetic document pack is linked to example application SPECIMEN-APP-5201. ' if case_id == 'CASE-A' else 'This synthetic document pack is not linked to an application. ') + 'PDF text and simulated OCR require review.'}

def apply_linked_reviews(extracted, state):
    """Layer human-reviewed values on the original extractor output, preserving provenance."""
    result = copy.deepcopy(extracted)
    corrections = state.get('corrections', {}) if state else {}
    reviewed = set()
    for item in result['evidence']:
        correction = corrections.get(item['id'])
        if correction and correction['valid'] and item['review_required']:
            item['original_value'] = item['value']
            item['value'] = correction['value']
            item['source'] = 'human-reviewed ' + item['source']
            item['review_required'] = False
            item['human_reviewed'] = True
            reviewed.add(item['id'])
    result['review_items'] = [item for item in result['review_items'] if item['document_id']+':'+item['field'] not in reviewed]
    if state and state.get('supplement') in ('attached','verified'):
        sample, _ = linked_review.supplement()
        fields = {'identity.name':sample['identity']['name'], 'identity.date_of_birth':sample['identity']['date_of_birth'],
                  'identity.expiry_date':sample['identity']['expiry_date'], 'director.name':sample['directors'][0]['name'],
                  'director.date_of_birth':sample['directors'][0]['date_of_birth']}
        fields.update({'pep.'+name:value for name,value in sample['pep_declarations'].items()})
        for field, value in fields.items():
            result['evidence'].append({'id':'A5:'+field,'document_id':'A5','document':linked_review.SUPPLEMENT.name,
                'field':field,'value':value,'confidence':None,'source':'synthetic supplemental record',
                'review_required':state['supplement'] != 'verified'})
    return result
