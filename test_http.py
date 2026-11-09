import json, tempfile, threading, unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
import app, lab_bridge

class HttpWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.old_db=app.DB; self.old_store=lab_bridge.REVIEW_STORE
        self.env=patch.dict('os.environ',{'KYC_POLICY_SEARCH':'off'}); self.env.start()
        app.DB=Path(self.tmp.name)/'demo.sqlite3'; lab_bridge.REVIEW_STORE=Path(self.tmp.name)/'reviews.json'
        app.init_db(); self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        app.DB=self.old_db; lab_bridge.REVIEW_STORE=self.old_store; self.env.stop(); self.tmp.cleanup()
    def get(self,path):
        with urlopen(self.base+path) as response: return json.load(response)
    def post(self,path,body):
        request=Request(self.base+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urlopen(request) as response: return json.load(response)
    def test_document_and_review_workflow(self):
        with urlopen(self.base+'/markdown.js') as response:
            self.assertIn('text/javascript',response.headers['Content-Type'])
        ids=self.get('/api/lab/applications')['application_ids']
        self.assertEqual(len(ids),201)
        self.assertIn('SPECIMEN-APP-5200',ids)
        self.assertIn('SPECIMEN-APP-5201',ids)
        linked=self.post('/api/lab/run',{'application_id':'SPECIMEN-APP-5201'})
        self.assertEqual(linked['linked_document_case'],'CASE-A')
        self.assertEqual(linked['status'],'MISSING_DATA')
        documents=self.get('/api/documents/CASE-B'); self.assertTrue(documents['review_items'])
        result=self.post('/api/lab/run',{'application_id':'SPECIMEN-APP-5155'})
        self.assertEqual(result['status'],'COMPLIANCE_REVIEW')
        review=result['review_cases'][0]['id']
        result=self.post('/api/lab/review',{'application_id':'SPECIMEN-APP-5155','review_id':review,'action':'reviewed_for_analyst','rationale':'Review completed for analyst follow-up.'})
        self.assertEqual(result['actions'][-1]['action'],'reviewed_for_analyst')
        operations=self.get('/api/operations'); self.assertGreaterEqual(operations['review_case_count'],2)
        self.assertTrue(any(review in event['message'] for event in operations['events']))
    def test_directory_counts_only_checks_actually_run_and_marks_changes_stale(self):
        directory=self.get('/api/lab/directory')
        self.assertEqual(directory['counts']['All applications'],201)
        self.assertEqual(directory['counts']['Not checked'],201)
        self.post('/api/lab/run',{'application_id':'SPECIMEN-APP-5155'})
        self.post('/api/lab/run',{'application_id':'SPECIMEN-APP-5201'})
        directory=self.get('/api/lab/directory')
        self.assertEqual(directory['counts']['Not checked'],199)
        self.assertEqual(directory['counts']['Compliance review'],1)
        self.assertEqual(directory['counts']['Needs information'],1)
        self.post('/api/linked/5201/review',{'action':'correct','field':'A4:issue_date','value':'2026-08-01'})
        directory=self.get('/api/lab/directory')
        linked=next(x for x in directory['applications'] if x['id']=='SPECIMEN-APP-5201')
        self.assertEqual(linked['category'],'Needs recheck')
        self.assertEqual(directory['counts']['Needs recheck'],1)
        self.assertEqual(directory['counts']['Needs information'],0)
        self.post('/api/lab/run',{'application_id':'SPECIMEN-APP-5201'})
        self.assertEqual(self.get('/api/lab/directory')['counts']['Needs information'],1)
    def test_linked_case_can_be_reviewed_and_rerun(self):
        run=lambda:self.post('/api/lab/run',{'application_id':'SPECIMEN-APP-5201'})
        initial=run()
        self.assertEqual(initial['status'],'MISSING_DATA')
        with self.assertRaises(HTTPError):
            self.post('/api/linked/5201/review',{'action':'verify_supplement'})
        with self.assertRaises(HTTPError):
            self.post('/api/linked/5201/review',{'action':'correct','field':'A4:issue_date','value':'2O26-O8-Ol'})
        for field,value in [('A4:name','Halden Logistics Ltd'),('A4:address','14 Quay Street, Port Ellery, XB 2041'),('A4:issue_date','2026-08-01')]:
            self.post('/api/linked/5201/review',{'action':'correct','field':field,'value':value})
        self.post('/api/linked/5201/review',{'action':'attach_supplement'})
        self.assertEqual(run()['status'],'MISSING_DATA')
        self.post('/api/linked/5201/review',{'action':'verify_supplement'})
        self.post('/api/linked/5201/review',{'action':'correct','field':'A4:name','value':'Different company'})
        self.assertIn('MISSING_FIELD:proof_of_address_name_mismatch',run()['reasons'])
        self.post('/api/linked/5201/review',{'action':'correct','field':'A4:name','value':'Halden Logistics Ltd'})
        self.post('/api/linked/5201/review',{'action':'correct','field':'A4:issue_date','value':'2026-09-01'})
        after_application=run()
        self.assertEqual(after_application['status'],'MISSING_DATA')
        self.assertIn('MISSING_FIELD:proof_of_address_after_application',after_application['reasons'])
        self.post('/api/linked/5201/review',{'action':'correct','field':'A4:issue_date','value':'2026-08-01'})
        final=run()
        self.assertEqual(final['status'],'NO_FLAGS')
        self.assertTrue(final['recommendation_held'])
        self.assertEqual(final['document_review_items'],[])
        self.assertEqual(len(final['screenings']),3)
        state=self.get('/api/linked/5201')
        self.assertEqual(state['supplement'],'verified')
        self.assertEqual(len(state['audit']),9)
        doc=self.get('/api/documents/CASE-A')
        address_date=next(x for x in doc['evidence'] if x['id']=='A4:issue_date')
        self.assertEqual(address_date['value'],'2026-08-01')
        self.assertEqual(address_date['original_value'],'2O26-O8-Ol')
        self.assertFalse(address_date['review_required'])
        self.assertTrue(any(x['id']=='A5:identity.name' for x in doc['evidence']))
    def test_course_case_edit_is_scoped_audited_and_changes_the_lab_result(self):
        case_id='SPECIMEN-APP-5154'
        before=self.get('/api/lab/case/'+case_id)
        self.assertTrue(before['company']['name'])
        self.assertTrue(before['parties'])
        self.assertTrue(before['documents'])
        original=next(x for x in before['fields'] if x['id']=='proof_of_address_date')['original']
        run=lambda:self.post('/api/lab/run',{'application_id':case_id})
        self.assertEqual(run()['status'],'NO_FLAGS')
        edited=self.post('/api/lab/case/'+case_id+'/edit',{'field':'proof_of_address_date','value':'2020-01-01'})
        self.assertEqual(edited['audit'][0]['old_value'],original)
        self.assertEqual(edited['audit'][0]['new_value'],'2020-01-01')
        item=next(x for x in self.get('/api/lab/directory')['applications'] if x['id']==case_id)
        self.assertEqual(item['category'],'Needs recheck')
        result=run()
        self.assertIn('POA_STALE',result['reasons'])
        self.assertEqual(result['status'],'FLAGGED')
        source=lab_bridge.data_layer.get_application_pack(case_id)
        self.assertEqual(lab_bridge.rules.document(source,'PROOF_OF_ADDRESS')['document_date'],original)
        self.post('/api/lab/case/'+case_id+'/edit',{'field':'proof_of_address_date','reset':True})
        self.assertEqual(run()['status'],'NO_FLAGS')
        with self.assertRaises(HTTPError): self.post('/api/lab/case/'+case_id+'/edit',{'field':'approve','value':'yes'})
        with self.assertRaises(HTTPError): self.post('/api/lab/case/'+case_id+'/edit',{'field':'application_date','value':'nonsense'})

if __name__=='__main__': unittest.main()
