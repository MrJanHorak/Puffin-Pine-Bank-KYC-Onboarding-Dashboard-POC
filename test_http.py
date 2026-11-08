import json, tempfile, threading, unittest
from pathlib import Path
from urllib.request import Request, urlopen
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
        documents=self.get('/api/documents/CASE-B'); self.assertTrue(documents['review_items'])
        result=self.post('/api/lab/run',{'application_id':'SPECIMEN-APP-5155'})
        self.assertEqual(result['status'],'COMPLIANCE_REVIEW')
        review=result['review_cases'][0]['id']
        result=self.post('/api/lab/review',{'application_id':'SPECIMEN-APP-5155','review_id':review,'action':'reviewed_for_analyst','rationale':'Review completed for analyst follow-up.'})
        self.assertEqual(result['actions'][-1]['action'],'reviewed_for_analyst')
        operations=self.get('/api/operations'); self.assertGreaterEqual(operations['review_case_count'],2)
        self.assertTrue(any(review in event['message'] for event in operations['events']))

if __name__=='__main__': unittest.main()
