import io, json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import gemini_agent, lab_bridge

class CourseIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = lab_bridge.REVIEW_STORE
        lab_bridge.REVIEW_STORE = Path(self.tmp.name) / 'reviews.json'
        self.env = patch.dict(os.environ, {'KYC_POLICY_SEARCH':'off','GEMINI_API_KEY':'test-key'}, clear=False)
        self.env.start()
    def tearDown(self):
        self.env.stop(); lab_bridge.REVIEW_STORE = self.old; self.tmp.cleanup()
    def test_course_screening_and_review_routing(self):
        result = lab_bridge.run_course_case('SPECIMEN-APP-5155')
        self.assertEqual(result['status'],'COMPLIANCE_REVIEW')
        self.assertIn('PEP_PARTY',result['reasons'])
        self.assertEqual(len(result['review_cases']),2)
        self.assertEqual(result['review_cases'],lab_bridge.run_course_case('SPECIMEN-APP-5155')['review_cases'])
        self.assertTrue(result['recommendation_held'])
    def test_missing_data_and_policy_failure_hold(self):
        result = lab_bridge.run_course_case('SPECIMEN-APP-5192')
        self.assertEqual(result['status'],'MISSING_DATA')
        self.assertEqual(gemini_agent.run_agent(result)['mode'],'held')
        with patch.dict(os.environ, {'KYC_POLICY_SEARCH':'azure'}), patch('lab_bridge.policy_search.search_policy', side_effect=lab_bridge.policy_search.PolicyUnavailable('offline')):
            result = lab_bridge.run_course_case('SPECIMEN-APP-5154')
            self.assertEqual(result['policy']['outcome'],'unavailable')
            self.assertEqual(gemini_agent.run_agent(result)['mode'],'held')
        result['policy']['outcome'] = 'ok'
        result['status'] = 'COMPLIANCE_REVIEW'
        result['reasons'] = ['PEP_PARTY','MISSING_DOCUMENT:PASSPORT']
        self.assertEqual(gemini_agent.run_agent(result)['mode'],'held')
    def test_search_results_use_course_client(self):
        section = {'section_id':'CDD-1','version':'1','title':'Due diligence','effective_date':'2026-01-01','content':'Synthetic policy.'}
        with patch.dict(os.environ, {'KYC_POLICY_SEARCH':'azure'}), patch('lab_bridge.policy_search.search_policy',return_value=[section]) as search:
            result = lab_bridge.run_course_case('SPECIMEN-APP-5154')
        self.assertEqual(result['policy']['sections'],[section])
        self.assertEqual(result['policy']['outcome'],'ok')
        search.assert_called_once()
    def test_agent_returns_model_tool_parts_and_requires_both_tools(self):
        assessment = lab_bridge.run_course_case('SPECIMEN-APP-5154')
        replies = [
            {'candidates':[{'content':{'role':'model','parts':[{'functionCall':{'name':'get_kyc_assessment','args':{}},'thoughtSignature':'signed'}]}}]},
            {'candidates':[{'content':{'role':'model','parts':[{'functionCall':{'name':'get_policy_evidence','args':{}}}]}}]},
            {'candidates':[{'content':{'role':'model','parts':[{'text':'Policy not checked. Analyst review remains.'}]}}]},
        ]
        requests=[]
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self,*args): self.close()
        def fake(request, timeout):
            requests.append(json.loads(request.data)); return Response(json.dumps(replies.pop(0)).encode())
        with patch('gemini_agent.urlopen',side_effect=fake): result=gemini_agent.run_agent(assessment)
        self.assertEqual(result['mode'],'gemini')
        self.assertEqual(result['trace'],['get_kyc_assessment','get_policy_evidence'])
        self.assertEqual(requests[1]['contents'][1]['parts'][0]['thoughtSignature'],'signed')
        self.assertEqual(requests[1]['contents'][2]['parts'][0]['functionResponse']['name'],'get_kyc_assessment')
    def test_agent_rejects_unlisted_tools(self):
        assessment = lab_bridge.run_course_case('SPECIMEN-APP-5154')
        data = {'candidates':[{'content':{'role':'model','parts':[{'functionCall':{'name':'approve','args':{}}}]}}]}
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self,*args): self.close()
        with patch('gemini_agent.urlopen',return_value=Response(json.dumps(data).encode())):
            self.assertEqual(gemini_agent.run_agent(assessment)['mode'],'unavailable')

if __name__ == '__main__': unittest.main()
