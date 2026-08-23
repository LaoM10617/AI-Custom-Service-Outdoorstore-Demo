## Business Background

BlueHarbor is a fictional online outdoor store that sells camping lanterns, hiking water bottles, waterproof backpacks, and digital camping checklists. This business setting is used to simulate:

- Q&A about product specifications, shipping, and after-sales policies.
- Queries about order, payment, fulfillment, logistics, and refund status.
- Customer-service tickets such as damaged goods, address changes, and order cancellations.
- Repeated Shopify webhook deliveries, external API timeouts, and model service failures.
- AI-proposed actions, human approval, execution results, and audit tracking.

## Delivery Goals

The project follows a progressive roadmap that prioritizes building real business boundaries before introducing overly complex infrastructure.

### Phase 0: Current Demo

- FastAPI synchronous chat and SSE streaming chat.
- `knowledge / order / chat` intent routing.
- Knowledge-base ingestion for PDF, DOCX, Markdown, and TXT.
- Vector retrieval + BM25 + RRF, with optional BGE reranker.
- Optional CrewAI dual-agent flow, with fallback to the built-in router on failure.
- In-process session memory, rate limiting, semantic cache, and tracing.
- Self-contained monitoring dashboard, evaluation data, Docker, and CI.
- Order lookup is a fixed Mock and does not represent real business integration.

### Phase 1: Shopify Real-Business Simulation

- Create a free Shopify Development Store and test orders.
- Receive order, fulfillment, cancellation, and refund webhooks through a custom app.
- Use SQLite to store order mirrors, webhook events, and audit logs.
- Replace the `query_order` Mock with real read-only order queries.
- Implement webhook HMAC verification, event idempotency, and order-ownership validation.
- Add integration tests for order lookup, duplicate events, and unauthorized access.

### Phase 2: One-Person Operable Pre-Production

- Authentication for the dashboard and admin APIs.
- Move sessions, cache, and rate limiting to Redis, and migrate business data to PostgreSQL.
- Add upload-size, file-type, timeout, and concurrency limits.
- Add structured logs, sensitive-data masking, metrics, and alerting.
- Route high-risk actions such as refunds, cancellations, and address changes into a human-approval queue.
- Establish complete failure recovery, data retention, and privacy-deletion processes.

## Current Architecture

```text
User / Dashboard
       |
       v
FastAPI API + SSE
       |
       +-- Semantic cache
       +-- Intent routing
       +-- RAG: vector + BM25 + RRF + optional reranker
       +-- Order tool: currently Mock, to be replaced in Phase 1 by Shopify order mirror/API
       +-- Session memory
       |
       v
Tracing / Runtime metrics / Dashboard

Added in Phase 1:
Shopify Development Store --Webhooks--> HMAC verification and idempotent handling --> SQLite
                                                                       |
Customer-service order lookup -----------------------------------------+
```

## Core Interfaces

- `GET /health`: health check.
- `POST /api/v1/chat`: synchronous customer-service response.
- `POST /api/v1/chat/stream`: SSE streaming customer-service response.
- `POST /api/v1/ingest`: knowledge document upload; currently has no admin authentication.
- `GET /api/v1/stats`: runtime status.
- `GET /api/v1/traces`: recent requests and latency summary.
- `GET /dashboard`: chat and request-tracing monitoring page.
- `GET /docs`: FastAPI OpenAPI documentation.

Example request:

```powershell
$body = @{
  message = "Where is order 202608090001 now?"
  session_id = "demo-user-001"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://localhost:8000/api/v1/chat `
  -Method Post `
  -Body $body `
  -ContentType "application/json"
```

## Local Startup

### Prerequisites

- Python 3.10–3.13, with 3.11 recommended.
- Docker Desktop, optional.
- One OpenAI-compatible LLM and embedding service.
- The lowest-cost option is local Ollama.

### One-Click Startup on Windows

```powershell
git clone <repository-url>
cd <repository-directory>
Copy-Item .env.example .env
.\start.ps1
```

The script creates `.venv`, installs the core dependencies, checks Ollama, and starts the service. The dashboard is available at <http://localhost:8000/dashboard>.

To stop the service:

```powershell
.\stop.ps1
```

### Manual Startup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

Optional capabilities:

```powershell
pip install -r requirements-extra.txt # CrewAI, reranker, Milvus
pip install -r requirements-eval.txt  # RAGAS evaluation
```

### Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose logs -f blueharbor-support
Invoke-RestMethod http://localhost:8000/health
```

By default, Compose starts local Ollama and automatically pulls the configured chat and embedding models. The first startup may be slow.

## Configuration

Copy `.env.example` to `.env`, then choose your model service. Example for Ollama:

```ini
AIROBOT_LLM_BASE_URL=http://localhost:11434/v1
AIROBOT_LLM_API_KEY=ollama
AIROBOT_LLM_MODEL=qwen2.5:3b
AIROBOT_EMBEDDING_BASE_URL=http://localhost:11434/v1
AIROBOT_EMBEDDING_API_KEY=ollama
AIROBOT_EMBEDDING_MODEL=nomic-embed-text
```

`AIROBOT_*` is a compatibility prefix left over from the project's earlier name. It is still used by the codebase, CI, and existing `.env` files. During the branding transition, it is not being renamed immediately in order to avoid breaking current deployments; later, `BLUEHARBOR_*` aliases can be introduced and the old prefix can be deprecated in stages.

Common settings include:

- `AIROBOT_USE_CREW`: whether to prefer CrewAI.
- `AIROBOT_HYBRID_ENABLED`: whether to enable hybrid retrieval.
- `AIROBOT_RERANK_ENABLED`: whether to enable semantic reranking.
- `AIROBOT_VECTOR_STORE`: `inmemory` or `milvus`.
- `AIROBOT_RATELIMIT_PER_MINUTE`: request limit per IP per minute.
- `AIROBOT_CACHE_ENABLED`: whether to enable semantic cache.
- `AIROBOT_MEMORY_MAX_TURNS`: maximum number of turns retained per session.

See [.env.example](.env.example) for the complete configuration and explanations.

## Knowledge Base

The current sample knowledge lives in `data/knowledge_base.md` and is automatically ingested at startup. Based on the BlueHarbor business setup, it is recommended to gradually split it into the following structure:

```text
data/
  products/
    camping-light.md
    backpack.md
  policies/
    shipping.md
    returns.md
    warranty.md
    privacy.md
  operations/
    escalation.md
    damaged-item.md
```

Each business document should include a version, effective date, owner, and applicable region, so that policy updates, cache invalidation, and answer traceability can be tested.

## Testing and Evaluation

Syntax checks and existing offline tests:

```powershell
python -m compileall -q app eval scripts tests
python tests/test_stability.py
python tests/test_tracing.py
```

Retrieval experiments and evaluation:

```powershell
python scripts/bench_retrieval.py --top-k 5
python scripts/bench_splitter.py --top-k 3
$env:AIROBOT_RERANK_ENABLED="false"
python eval/run_eval.py --limit 5
```

`eval/dataset/qa.jsonl` contains 52 sample entries. After Shopify integration, a real-business regression set should be added, covering at least:

- Correct and incorrect order ownership.
- Nonexistent, canceled, and refunded orders.
- Webhook replay and out-of-order delivery.
- Timeouts or rate limits from Shopify, the LLM, and the embedding service.
- Prompt injection and sensitive-information requests.
- Cache and citation consistency after policy updates.

## Security Boundaries

The current version does not yet meet production security requirements:

- `/ingest`, `/stats`, `/traces`, and the dashboard currently have no authentication.
- The upload endpoint does not yet enforce file-size or parsing-timeout limits.
- Sessions, cache, rate limiting, and the default vector store all use in-process state.
- The order tool returns Mock data.
- Customer identity and order ownership are not yet verified.
- There is no approval queue yet for high-risk business actions.

When Shopify is connected, the model must not hold Shopify admin credentials directly. The model may only call narrowly scoped tools defined by the backend. Operations such as refunds, order cancellation, address changes, reshipment, and customer-data deletion must go to human approval by default.

## Project Structure

```text
app/
  main.py              FastAPI, APIs, middleware, and SSE
  config.py            Environment variable configuration
  agents/              CrewAI orchestration and business tools
  rag/                 Document loading, hybrid retrieval, fusion, and reranking
  services/            Chat, memory, retry, rate limiting, cache, and tracing
  static/dashboard.html
data/                  Sample knowledge base
eval/                  Evaluation scripts and dataset
scripts/               Retrieval and chunking experiments
tests/                 Offline unit tests
.github/workflows/     CI
```

## Definition of Done

The project should only be considered ready for pre-production when all of the following conditions are met:

- Orders come from Shopify and no longer depend on Mock data.
- Webhooks have signature verification, idempotency, and retry handling.
- Customer identity and order ownership can be verified.
- Admin and upload interfaces are authenticated.
- Critical business data is persisted.
- High-risk operations always require human approval.
- Logs are redacted and traceable through request IDs.
- The system can degrade safely when external services fail.
- Key business scenarios are covered by automated integration tests.

## License

This project uses the license described in [LICENSE](LICENSE) in the repository.
