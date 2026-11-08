import tempfile
import unittest
import json
from unittest.mock import patch
from urllib.error import HTTPError
from pathlib import Path
import app

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = app.DB
        app.DB = Path(self.temp.name) / 'test.sqlite3'
        app.init_db()
    def tearDown(self):
        app.DB = self.old_db
        self.temp.cleanup()
    def test_standard_case_and_persistence(self):
        case = app.action('PP-1042','screen',{})
        self.assertEqual(case['status'], 'Ready for analyst')
        app.action('PP-1042','screen',{})
        with app.connect() as db:
            self.assertEqual(len(app.detail(db, 'PP-1042')['events']), 1)
    def test_missing_evidence_requires_review(self):
        app.action('PP-1043','verify',{'document_id':'identity'})
        app.action('PP-1043','draft',{})
        case = app.action('PP-1043','receive',{'document_id':'address'})
        self.assertEqual(case['status'], 'Needs information')
        app.action('PP-1043','verify',{'document_id':'address'})
        self.assertEqual(app.action('PP-1043','screen',{})['status'], 'Ready for analyst')
    def test_match_goes_to_compliance_and_is_idempotent(self):
        case = app.action('PP-1044','screen',{})
        self.assertEqual(case['status'], 'Compliance review')
        self.assertTrue(case['review_case'])
        self.assertEqual(len(app.action('PP-1044','screen',{})['events']), 1)
    def test_invalid_actions_are_rejected(self):
        with self.assertRaises(ValueError): app.action('PP-1042','verify',{'document_id':'identity'})
        with self.assertRaises(ValueError): app.action('PP-1042','approve',{})
        with self.assertRaises(ValueError): app.action('unknown','screen',{})
    def test_gemini_missing_key_and_success(self):
        with app.connect() as db: case = app.detail(db, 'PP-1044')
        with patch.dict('os.environ', {'GEMINI_API_KEY':''}):
            self.assertEqual(app.assistant(case)['mode'], 'unavailable')
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return json.dumps({'candidates':[{'content':{'parts':[{'text':'Screening has not run.'}]}}]}).encode()
        with patch.dict('os.environ', {'GEMINI_API_KEY':'test-key','GEMINI_MODEL':'gemini-3.1-flash-lite'}), patch('app.urlopen', return_value=Response()) as send:
            result = app.assistant(case)
            self.assertEqual(result['mode'], 'gemini')
            request = send.call_args.args[0]
            payload = json.loads(request.data)
            self.assertIn('not run', payload['contents'][0]['parts'][0]['text'])
            self.assertNotIn('test-key', request.full_url)
    def test_gemini_quota_failure_is_safe(self):
        with app.connect() as db: case = app.detail(db, 'PP-1044')
        error = HTTPError('https://example.invalid', 429, 'quota', {}, None)
        with patch.dict('os.environ', {'GEMINI_API_KEY':'test-key'}), patch('app.urlopen', side_effect=error):
            self.assertIn('quota', app.assistant(case)['text'])
        with app.connect() as db: self.assertFalse(app.detail(db, 'PP-1044')['screened'])

if __name__ == '__main__': unittest.main()
