# Explicit multi-agent loop — 2026-10-08 (current)

## Decision superseding the earlier animation-only scope

The user requested implementation of the real loop and multi-agent presentation. Default JSON/SSE chat now uses an explicit Investigator + Reviewer tool loop. Earlier statements below saying the loop is not implemented or the dashboard uses fixed routing are historical.

## Implementation

- `app/agents/loop.py`: native model tool protocol, read-only allowlist, observation feedback, independent reviewer context, one revision, strict review output, bounded model/tool calls, timeouts and safe stop outcomes. Provider tool-call metadata is preserved for Gemini multi-turn compatibility.
- `app/services/agent_chat.py`: shared execution, reviewed-only session writes, actual event traces, HTTP client cleanup.
- `app/main.py`, `app/services/chat.py`, `app/schemas.py`, `app/config.py`: route both entry points through the loop, expose run IDs and stop reasons, serve `/agent-demo`, skip startup embedding ingestion in loop mode, and support an explicitly configured key-file path.
- Dashboard renders sequential actual agent events using textContent. The separate animation depicts Investigator/Reviewer handoff, independent tool use and revision; its scripted nature remains labeled.
- `.env` uses the user-authorized Gemini key file through the official compatibility endpoint; key contents were not copied. `.gitignore` excludes the key file. `requirements.txt` explicitly includes the OpenAI client. Existing `AIROBOT_*` names and legacy code remain compatible.

## Verification and runtime

- Nine deterministic loop tests cover observation feedback, independent reviewer tools, revision, repeated rejection, forbidden tools, tool failures, budget exhaustion, malformed review and timeout. Six-fixture checks pass.
- Two FastAPI integration tests verify JSON/SSE execution, trace events, animation route and unconfigured failures with scripted model doubles.
- Existing six stability and three tracing tests pass. An existing LangChain memory deprecation warning remains; no unrelated migration was performed.
- Real Gemini evidence: see `live_agent_loop_verification.json`; consult its stop_reason before asserting a successful run. Google listed gemini-2.5-flash but rejected generation for new users with HTTP 404; the local configuration was switched to the API-recommended gemini-3.8-flash.
- Browser layout/interaction checks and final runtime status are recorded in the delivery verification note added after testing.

## Run and limitations

Run `.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`, then open `/dashboard`. `/agent-demo` is the labeled scripted presentation. Set `AIROBOT_AGENT_ENGINE=legacy` and restart to restore the old routing; loop mode intentionally bypasses semantic caching and vector ingestion.

This is a demo: read-only synthetic orders; no customer authentication, business mutations, notifications, payment execution or durable trace/session storage. Reviewer approval is a model judgment about text, not a guarantee of factual correctness or an approval of any business action. The old marketplace evaluation dataset is still unsuitable for current quality claims. Tool calls/review decisions are observable; private model reasoning is neither requested nor displayed.

---

## Historical delivery

# BlueHarbor English demo refresh — 2026-10-08

## Implemented

- Unified customer-facing prompts, CrewAI roles, RAG prompt, knowledge base, dashboard and API response messages in English under the BlueHarbor outdoor-store brand.
- Added six fictional read-only order fixtures in `data/mock_orders.json`: BH-1001 processing, BH-1002 in transit, BH-1003 delivered, BH-1004 delayed, BH-1005 cancelled, BH-1006 refunded. Snapshot date: 2026-10-08. Prices, status events and tracking identifiers are simulated.
- `query_order` now reads exact fixture IDs. Missing IDs ask for clarification, unknown IDs return not found, and requests with several IDs ask for one order. No invented default order is used.
- The after-sales tool reads the same returns section as the knowledge base to avoid divergent policy text. RAG imports in the knowledge tool are lazy, allowing fixture checks without model dependencies.
- Created `demo/agent-loop.html`, an independent browser animation with play/pause, replay, next-step, timeline selection and normal/failure scenarios. It runs offline and requires no application server.
- Removed unsupported dashboard quality percentages and clarified that its streaming chat uses the existing router. No explicit autonomous loop was added to the application, as requested.

## Verification

- All seven modified/new Python files passed AST syntax parsing.
- `python tests/test_demo_orders.py` passed for all six statuses, lowercase IDs, missing/unknown/multiple IDs, exact-match boundaries, simulation labels and shared policy content.
- Headless Edge checks passed: normal and failure animation endings, next-step/replay controls, 390px layout without horizontal overflow, and dashboard rendering with mocked stats/traces responses. No JavaScript page errors were reported. Desktop screenshots were inspected.
- These are offline checks, not a running backend or live model validation. No model calls, Shopify calls, messages, refunds or ticket creation occurred.

## Run / demonstrate

1. Open `demo/agent-loop.html` directly in a browser. It is a scripted concept presentation, not a live execution trace. Reduced-motion settings disable autoplay; use Play or Next step.
2. For the real chat UI, configure `.env`, install runtime dependencies and start the existing application. Its entry remains `http://localhost:8000/dashboard`. The default `start.ps1` expects local Ollama; review the existing README before first setup.
3. Try `Track order BH-1002`, `Check order BH-1004`, `Check order BH-9999`, and `What is the demo return policy?`.
4. Knowledge is ingested on startup; restart existing services to load the revised document. Existing in-process sessions/caches also reset on restart.

## Limits and next step

- This checkout had no `.env` or `.venv` and no observed listener on port 8000 before changes. Live application/model startup remains unverified.
- Optional CrewAI execution has not been exercised. The application still uses its prior routing paths and framework-managed execution.
- The historical 52-question evaluation dataset describes a second-hand marketplace. It is not a valid benchmark for the revised BlueHarbor knowledge base; replace/rebaseline it before reporting quality scores.
- The existing `AIROBOT_*` environment names are preserved for compatibility.
- No authentication, ownership validation, real business mutations, support-ticket queue or Shopify synchronization was added. Fictional policies are not real merchant/legal policies.
- Next authorized development step should focus on model configuration and one end-to-end English chat check, if requested. Do not describe the animation as proof of an implemented agent loop.

## Changed files

`README.md`, `app/agents/crew.py`, `app/agents/tools.py`, `app/services/chat.py`, `app/services/memory.py`, `app/rag/retriever.py`, `app/main.py`, `app/static/dashboard.html`, `data/knowledge_base.md`, `data/mock_orders.json`, `tests/test_demo_orders.py`, `demo/agent-loop.html`, and this handoff.

## Final delivery verification — 2026-10-08

- Real browser-to-SSE-to-Gemini run passed after policy clarification: engine agent_loop, Investigator and Reviewer both observed, 3 model calls, 2 read-only tool calls, review_approved, approximately 16.2 seconds. Evidence is in live_agent_loop_verification.json (run.stop_reason and run.agent_events). No tool/model responses were mocked in this browser run.
- The first successful core run exposed a policy-scope error despite reviewer approval. The policy and both role prompts now explicitly distinguish unused-goods return windows from unspecified damaged-item deadlines. The subsequent real browser response correctly preserved that distinction. This is evidence for this case, not a general accuracy guarantee.
- Normal animation and reviewer-revision controls passed browser checks. No JavaScript errors; 390px viewport had no horizontal overflow. Desktop animation and live dashboard screenshots were visually inspected.
- The local backend is running at http://127.0.0.1:8000 with gemini-3.8-flash. /dashboard is interactive; /agent-demo is the independent scripted presentation. The backend was started hidden with logs under .logs/.
- 20 test methods passed (9 loop, 2 API, 6 existing stability, 3 existing tracing), plus the six-order fixture check and application syntax checks. API unit tests use model doubles; real browser evidence is separate. Reviewer-driven revision was tested with deterministic doubles, not forced through an additional paid live run.
- .env and Gemini_API_KEY.txt are ignored by Git. No commits, pushes or public deployment were performed.

## Customer-facing presentation refresh — 2026-10-08 (current)

At the user's request, removed demo/simulation terminology from the animation, dashboard labels, routine responses and displayed activity metadata. Dashboard title and heading are now exactly `product customer service`. `/agent-workflow` is the new presentation link; `/agent-demo` remains a backward-compatible alias.

Removed the forced response prefix and changed role prompts to use neutral business language without unsolicited implementation labels. Explicit provenance questions must still be answered truthfully. Internal simulated flags remain in order fixtures and backend results; the UI omits those fields from its presentation of tool evidence. Tracking labels now use BH-TRACK-. No live Shopify integration or new business action was added. These are still six fixed sample orders; technical documentation retains that boundary. The animation remains labeled as an architecture walkthrough with illustrated steps; actual execution is visible on the dashboard.

Validation: 9 loop tests, fixture checks, 2 API tests and syntax/diff checks passed. Headless Edge inspected all 11 steps of both animation scenarios, exact dashboard title, and a real Gemini-backed BH-1002 request. No demo/simulation/simulated words appeared in visible UI, answer or activity in those checks; no JavaScript errors. The real request passed review in 3 model calls, about 8.9 seconds. Model-generated wording for arbitrary future questions is not guaranteed, especially explicit questions about data provenance. Evidence: presentation_verification.json.

Current business scope: six order records (items, quantities, EUR totals, processing/shipping/delivery/delay/cancellation/refund status and tracking); general shipping estimates; unused-goods returns; damaged/wrong-item guidance and return-shipping responsibility; cancellation/address-change policy; store overview; detailed StormGlow 600 lantern specifications and limited basic information for other listed products. No live stock, catalogue-wide pricing, new orders, refunds, address updates, ticket creation or image inspection.


## PDF / CSV library integration — 2026-10-08 (current)

User requested merging SITECO Document Chat upload/query capabilities into the existing BlueHarbor customer-service application. The current default remains the actual Investigator/Reviewer loop. SITECO's separate frontend/server were not embedded: the reusable PDF layout parser and BM25L retrieval module were migrated, and the fixed German product price-list CSV schema was replaced by generic exact order-record storage.

Source: `D:/Projects/SITECO-document-chat`, HEAD `7525fdb5e328e25a83daefd65a6b674a4e51010b`. Adapted `backend/app/parsing.py`, copied `pdf_layout.py` and `retrieval/lexical.py`, and adapted parser contract tests. Existing uncommitted SITECO changes were left untouched. No Voyage/FAISS embedding service was added; PDF retrieval is lexical, not the source project's vector/RRF pipeline.

Implementation:
- `app/library/`: native-text PDF extraction, source locators, UTF-8 CSV parsing with automatic/custom ID column, atomic SQLite persistence, content deduplication, exact case-sensitive order lookup, document scoping, Archive/Restore, original-file and escaped HTML record previews.
- `app/agents/loop.py`: `search_documents` plus uploaded CSV `get_order`; tools obey selected documents. No built-in fallback when uploads are in scope or an explicit empty scope is supplied. Both agents receive selected-file metadata and evidence-only instructions. Final results include source links.
- `app/services/agent_chat.py`: resolves selected sources and scopes conversation history by document selection. `app/main.py`, `app/services/chat.py`, `app/schemas.py`: shared JSON/SSE integration and document API registration.
- `app/static/dashboard.html`: upload, optional CSV ID heading, selection, archive/restore, source links, actual uploaded chunk count, retrieval label, and horizontally scrollable request table. Existing title remains `product customer service`.
- `requirements.txt`: pdfplumber 0.11.10; `.gitignore`: data/library/. Tests: new isolated library fixture, store/API/loop cases and migrated PDF parser contracts. README's current sections supersede the historical legacy architecture.

Validation:
- Installed target project: 41 pytest checks passed; six-order fixture script passed; git diff --check passed. A pre-existing LangChain memory deprecation warning remains.
- Real Edge upload of a synthetic PDF specifying a 45-day unused-goods return window and a CSV with UP-2001. Gemini answered delivered + 45 days with both exact filename locators; Investigator and Reviewer completed in 3 model calls, 2 tool calls, 11.118 seconds, review_approved.
- Both source links returned readable content; page reload and backend restart preserved sources. No browser JavaScript errors; 390px viewport no horizontal overflow after the request-table fix. Desktop screenshot visually inspected.
- Evidence: `uploaded_library_verification.json`. The two synthetic verification uploads are archived, not active. Restore them explicitly to reproduce this check; their 45-day policy intentionally differs from the built-in 30-day fixture.

Limits and operation:
- Start `.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`; open `/dashboard`. Server was restarted hidden with existing .logs paths.
- Persistent originals and indexes: `data/library/library.sqlite3` (override AIROBOT_LIBRARY_DIR). 20 MB/file, 50 PDF pages, 20,000 CSV records, 30 stored files including archived. Archive is not permanent deletion.
- Native-text PDFs only; unreadable/image-only documents need OCR. Partial extraction warnings are shown. Keyword retrieval is not a general accuracy guarantee, and arbitrary order aggregation/SQL is unsupported.
- CSV preserves raw values and leading zeros. Duplicate IDs return up to five records and a total match count. Missing or conflicting evidence must be acknowledged rather than filled from examples.
- Uploads supply local read-only business evidence; no Shopify synchronization, authentication, customer ownership checks or business-action execution was added. The old `/api/v1/ingest` endpoint belongs to legacy in-memory RAG; the new loop uses `/api/v1/documents`.

## Reviewed-response streaming — 2026-10-08

The loop SSE endpoint now sends the final response in paced text chunks after Investigator/Reviewer execution, followed by the existing done event and citations. This is delivery of the completed reviewed answer, not provider token generation streamed before review. A response_start event updates the dashboard to Writing response. Chunk delivery is capped at approximately 2.4 seconds; no extra model request is made. Error/limitation responses also use the same delivery path. SSE headers disable caching and proxy buffering where supported.

Changed app/main.py, app/static/dashboard.html and tests/test_agent_api.py. Eleven focused API/loop tests passed, including exact text reconstruction and approval-before-token ordering. A real Edge/Gemini request for BH-1002 produced 23 chunks over 748 ms, matched the final reply exactly, began after reviewer approval and had no JavaScript errors. The local server was restarted. Changes are not committed or pushed in this step.
