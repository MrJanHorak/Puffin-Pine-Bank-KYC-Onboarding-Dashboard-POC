"""Read-only extraction of the separate synthetic document practice pack."""
import sys
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
