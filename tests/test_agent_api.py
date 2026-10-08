"""Verify both chat endpoints use the same loop with a deterministic model double."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from test_agent_loop import ScriptedModel, call, text


def model():
    return ScriptedModel([call("get_order",{"order_id":"BH-1003"}),text("Simulation: delivered. No action executed."),
        call("submit_review",{"decision":"approve","feedback":"Order evidence checked."})])


class ApiTests(unittest.TestCase):
    def test_json_and_sse(self):
        with patch.object(settings,'agent_engine','loop'), patch.object(settings,'llm_api_key','offline-test'), \
             patch('app.services.agent_chat.ModelGateway',side_effect=lambda _:model()), TestClient(app) as client:
            result=client.post('/api/v1/chat',json={'message':'Check BH-1003','session_id':'offline-json'}).json()
            self.assertEqual(result['engine'],'agent_loop')
            self.assertTrue(result['review_approved'])
            self.assertEqual(result['model_calls'],3)
            stream=client.post('/api/v1/chat/stream',json={'message':'Check BH-1003','session_id':'offline-sse'})
            self.assertIn('"type": "agent_event"',stream.text)
            self.assertIn('"agent": "reviewer"',stream.text)
            self.assertIn('"stop_reason": "review_approved"',stream.text)
            self.assertIn('"type": "done"',stream.text)
            self.assertEqual(client.get('/agent-demo').status_code,200)
            traces=client.get('/api/v1/traces').json()['entries']
            self.assertTrue(any(t.get('agent_events') for t in traces))

    def test_unconfigured_does_not_fabricate_success(self):
        with patch.object(settings,'agent_engine','loop'), patch.object(settings,'llm_api_key',''), TestClient(app) as client:
            result=client.post('/api/v1/chat',json={'message':'Hello'}).json()
            self.assertFalse(result['review_approved'])
            self.assertEqual(result['stop_reason'],'not_configured')


if __name__=='__main__':
    unittest.main()
