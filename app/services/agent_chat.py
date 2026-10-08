"""Shared multi-agent execution for JSON and SSE chat endpoints."""
import uuid
import json
from hashlib import sha256

from app.library.store import get_library, LibraryError

from app.agents.loop import ModelGateway, run_loop
from app.config import settings
from app.services.memory import memory
from app.services.tracing import traces


async def agent_events(message, session_id, document_ids=None):
    session_id = session_id or "default"
    if not settings.llm_api_key:
        yield {"type": "result", "run_id": uuid.uuid4().hex, "reply":
               "Configure AIROBOT_LLM_API_KEY and a tool-calling model to start the agents.",
               "engine": "agent_loop", "intent": "support", "sources": [],
               "events": [], "stop_reason": "not_configured", "review_approved": False,
               "model_calls": 0, "tool_calls": 0, "total_ms": 0}
        return
    try:
        documents = get_library().scope(document_ids)
    except LibraryError as exc:
        yield {"type": "result", "run_id": uuid.uuid4().hex, "reply": str(exc),
               "engine": "agent_loop", "intent": "support", "sources": [], "events": [],
               "stop_reason": "invalid_documents", "review_approved": False,
               "model_calls": 0, "tool_calls": 0, "total_ms": 0}
        return
    # Isolate history when selected source files change; old facts are not new evidence.
    resolved_ids = [d["document_id"] for d in documents] if documents or document_ids is not None else None
    scope_key = sha256(json.dumps(resolved_ids if resolved_ids is None else sorted(resolved_ids)).encode()).hexdigest()[:16]
    memory_session = session_id + ":" + scope_key
    context = "Selected uploaded documents (reference metadata only): " + json.dumps([
        {"name": d["name"], "kind": d["kind"], "id_column": d.get("id_column")} for d in documents])
    history = [{"role": "user" if m.type == "human" else "assistant", "content": str(m.content)}
               for m in memory.get_messages(memory_session)]
    model = ModelGateway(settings)
    try:
        async for event in run_loop(message, history, model, document_ids=resolved_ids, source_context=context):
            if event["type"] == "result":
                if event["review_approved"]:
                    memory.add(memory_session, message, event["reply"])
                traces.record({"message": message[:80], "session_id": session_id,
                    "status": 200 if event["review_approved"] else 503,
                    "intent": "support", "engine": "agent_loop", "total_ms": event["total_ms"],
                    "run_id": event["run_id"], "stop_reason": event["stop_reason"],
                    "agent_events": event["events"], "model_calls": event["model_calls"],
                    "tool_calls": event["tool_calls"], "cache_checked": False})
            yield event
    finally:
        await model.close()



async def agent_chat(message, session_id, document_ids=None):
    async for event in agent_events(message, session_id, document_ids):
        if event["type"] == "result":
            return event
