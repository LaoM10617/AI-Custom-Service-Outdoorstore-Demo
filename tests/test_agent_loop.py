"""Deterministic loop protocol checks; no model service or credentials required."""
import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agents.loop import execute_tool, run_loop


def call(name, args, ident="c1"):
    return {"role": "assistant", "content": "", "tool_calls": [{"id": ident,
        "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


def text(value):
    return {"role": "assistant", "content": value, "tool_calls": []}


class ScriptedModel:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.inputs = []

    async def close(self):
        pass

    async def complete(self, messages, tools):
        self.inputs.append(copy.deepcopy(messages))
        return next(self.responses)


class AgentLoopTests(unittest.IsolatedAsyncioTestCase):
    async def collect(self, model, **kwargs):
        return [e async for e in run_loop("My backpack BH-1003 is damaged", [], model, **kwargs)]

    async def test_observation_and_independent_reviewer(self):
        model = ScriptedModel([call("get_order", {"order_id": "BH-1003"}),
            call("read_knowledge", {"section": "returns"}), text("Simulated delivered order; human review required."),
            call("read_knowledge", {"section": "returns"}),
            call("submit_review", {"decision": "approve", "feedback": "Grounded in the supplied evidence."})])
        events = await self.collect(model)
        result = events[-1]
        self.assertTrue(result["review_approved"])
        self.assertEqual(result["tool_calls"], 3)
        self.assertEqual(model.inputs[1][-1]["role"], "tool")
        self.assertIn('"status": "delivered"', model.inputs[1][-1]["content"])
        self.assertIn("Evidence Reviewer", model.inputs[3][0]["content"])
        self.assertEqual([e["sequence"] for e in events[:-1]], list(range(1,len(events))))
        self.assertEqual({e["agent"] for e in events[:-1]}, {"investigator", "reviewer"})

    async def test_revision_returns_to_investigator(self):
        model = ScriptedModel([text("Unverified draft"), call("submit_review", {"decision": "revise", "feedback": "Check the order."}),
            call("get_order", {"order_id": "BH-1003"}), text("Revised simulated order response"),
            call("submit_review", {"decision": "approve", "feedback": "Verified."})])
        events = await self.collect(model)
        self.assertIn("Revised simulated order response", events[-1]["reply"])
        self.assertFalse(events[-1]["reply"].startswith("Demo response"))
        self.assertIn("Check the order", model.inputs[2][-1]["content"])

    async def test_second_rejection_never_releases_draft(self):
        model = ScriptedModel([text("bad"),call("submit_review", {"decision":"revise","feedback":"unsupported"}),
            text("still bad"),call("submit_review", {"decision":"revise","feedback":"unsupported"})])
        result = (await self.collect(model))[-1]
        self.assertEqual(result["stop_reason"], "review_rejected")
        self.assertNotIn("still bad", result["reply"])

    async def test_unknown_tool_is_returned_as_observation(self):
        model = ScriptedModel([call("refund_order", {"order_id":"BH-1003"}),text("Cannot refund."),
            call("submit_review", {"decision":"approve","feedback":"No action claimed."})])
        await self.collect(model)
        self.assertIn("unknown_tool", model.inputs[1][-1]["content"])

    async def test_tool_failure_can_be_observed(self):
        model=ScriptedModel([call("get_order", {"order_id":"BH-1003"}),text("Cannot verify."),
            call("submit_review", {"decision":"approve","feedback":"Accurate limitation."})])
        with patch("app.agents.loop.execute_tool", side_effect=OSError("private details")):
            events=await self.collect(model)
        self.assertIn("tool_unavailable",model.inputs[1][-1]["content"])
        self.assertNotIn("private details",json.dumps(events))

    async def test_bounded_loop(self):
        model=ScriptedModel([call("get_order", {"order_id":"BH-1003"})]*3)
        result=(await self.collect(model,max_calls=3))[-1]
        self.assertEqual(result["stop_reason"],"model_limit")
        self.assertFalse(result["review_approved"])

    async def test_timeout(self):
        class SlowModel:
            async def complete(self,*args):
                await asyncio.sleep(1)
        result=(await self.collect(SlowModel(),call_timeout=.01))[-1]
        self.assertEqual(result["stop_reason"],"timeout")

    async def test_invalid_review_does_not_release_draft(self):
        model=ScriptedModel([text("draft"),call("submit_review", {"decision":"approve"})])
        result=(await self.collect(model,max_calls=2))[-1]
        self.assertFalse(result["review_approved"])

    def test_dispatch_boundaries(self):
        self.assertFalse(execute_tool("get_order",{"order_id":"BH-9999"})["found"])
        self.assertEqual(execute_tool("get_order",{})["error"],"invalid_arguments")
        self.assertEqual(execute_tool("read_knowledge",{"section":[]})["error"],"invalid_arguments")
        self.assertEqual(execute_tool("refund",{})["error"],"unknown_tool")


if __name__ == "__main__":
    unittest.main()
