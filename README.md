# AI Robot Intelligent Customer Service Platform (Simplified and self-replicated version from Allianz Q4 Intern Project)

A production-ready **complete intelligent customer service platform** built with **FastAPI + LangChain RAG + CrewAI multi-agent orchestration**.
It provides core customer-service capabilities such as intent-routing, knowledge-base question answering, multi-agent collaboration, and SSE streaming chat. It also includes retrieval engineering (BM25 + RRF + reranker), reliability engineering (retries / rate limiting / semantic cache), observability (real-time monitoring dashboard), and an evaluation framework (RAGAS closed loop). It can be deployed directly to production or integrated as an independent AI service into existing business systems (such as Spring Cloud or Node.js backends) over HTTP/SSE.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)

## Table of Contents

- [Project Positioning](#project-positioning)
- [Core Capability Overview](#core-capability-overview)
- [Feature Details](#feature-details)
- [Tech Stack](#tech-stack)
- [System Architecture](#system-architecture)
- [Quick Start (From Clone to Run)](#quick-start-from-clone-to-run)
- [API Documentation](#api-documentation)
- [Visualization Dashboard](#visualization-dashboard)
- [Docker Deployment](#docker-deployment)
- [CI Gates](#ci-gates)
- [Evaluation (RAGAS)](#evaluation-ragas)
- [Retrieval and Chunking Experiments](#retrieval-and-chunking-experiments)
- [Design Decisions](#design-decisions)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [FAQ](#faq)
- [License](#license)

## Project Positioning

This service turns the customer-service pipeline of **"intent recognition → tool/RAG execution → streaming response"** into a **production-usable complete application**, rather than a toy demo:

1. **Multi-agent orchestration**: two CrewAI agents (`Intent Classifier -> Customer Service Executor`) collaborate sequentially with multiple tools. If CrewAI is unavailable or invocation fails, the system automatically falls back to an equivalent built-in LangChain router to keep the service available.
2. **RAG retrieval pipeline**: PDF / Word / Markdown parsing -> chunking -> dual indexing with vectors + BM25 -> RRF fusion -> bge-reranker reranking -> retrieval-augmented generation. Built-in comparative experiments demonstrate the gains of hybrid retrieval (vector 67% -> hybrid 98% hit rate).
3. **Engineering support**: conversation memory, SSE streaming, tenacity retries, sliding-window rate limiting, semantic cache, tracing, RAGAS evaluation sets, Docker one-click deployment, and CI quality gates — every layer is observable, evaluable, and replaceable.

## Core Capability Overview

| Capability Module | What It Provides | Related Interface |
|---|---|---|
| Intelligent Chat | Intent routing (`knowledge` / `order` / `chat`) + RAG QA + tool calling + multi-turn memory | `POST /api/v1/chat` |
| Streaming Chat | SSE token-by-token output, full-response instant return on cache hit | `POST /api/v1/chat/stream` |
| Multi-Agent | CrewAI Intent Classifier -> Customer Service Executor, automatic fallback on failure | `app/agents/crew.py` |
| Knowledge Base QA | Example KB auto-import on startup; supports PDF / DOCX / MD / TXT upload and ingestion | `POST /api/v1/ingest` |
| Tool Integration | Order lookup (Mock, pluggable with real systems), after-sales rules | `app/agents/tools.py` |
| Reliability | Three layers of protection: retries / rate limiting / semantic cache | `app/services/*` |
| Observability | Real-time monitoring dashboard (including simulated user chat and end-to-end visualization), request tracing, runtime metrics | `/dashboard`, `/api/v1/traces`, `/api/v1/stats` |
| Evaluation | Four RAGAS metrics + LLM-as-Judge + 52-item evaluation set | `eval/run_eval.py` |
| Deployment | Docker / docker-compose / GitHub Actions gates | repository root |

## Feature Details

### 1. Intelligent Chat Service (`app/services/chat.py`)

- **Intent routing**: the LLM classifies each user message as `knowledge` (knowledge QA), `order` (order inquiry), or `chat` (casual chat). If JSON parsing of the classification fails, it falls back to `chat` so the service does not break.
- **Multi-turn session memory**: isolated by `session_id` (`InMemoryChatMessageHistory`). Each session keeps the latest `AIROBOT_MEMORY_MAX_TURNS` turns, and includes the latest `AIROBOT_MEMORY_RETRIEVE_TURNS` turns during generation to support contextual follow-up questions.
- **Dual output channels**: synchronous JSON (`/api/v1/chat`) and SSE streaming (`/api/v1/chat/stream`). In streaming mode, events are pushed as `stage (rate limiting / cache / intent / retrieval / generation, etc.) -> intent -> token* -> done`, allowing the dashboard to reconstruct the full pipeline in real time.
- **Fallback chain**: CrewAI is preferred when available (executed in an isolated thread) -> automatic fallback to the built-in LangChain router on exception -> if no API key is configured, the service returns a clear prompt instead of crashing.

### 2. Multi-Agent Orchestration (`app/agents/crew.py`)

- **Two-agent collaboration**: the `Intent Classifier` (outputs intent JSON) -> the `Customer Service Executor` (executes with 3 tools), using `Process.sequential` and structured as `Agent (role / goal / background / tools / LLM) + Task + Crew`.
- **Toolset** (`app/agents/tools.py`, with both raw functions and CrewAI `@tool` wrappers):
  - `search_knowledge`: RAG-powered retrieval-augmented generation over the knowledge base.
  - `query_order`: order / logistics lookup (currently Mock; in production, connect over HTTP to an order server; see “Design Decisions”).
  - `after_sale_rule`: after-sales and return policy rules.
- **Availability guarantees**: if `crewai` is not installed, `CREW_TOOLS_READY=false` and the system automatically switches to the built-in router. Runtime exceptions also trigger fallback, and the observable status is exposed as `crew_available` via `/api/v1/stats`.

### 3. RAG Knowledge Base (`app/rag/`)

- **Document parsing** (`loader.py`): PDF parsing via `pypdf`, Word parsing via `python-docx`, and direct reading for text files.
- **Chunking strategy** (`retriever.py`):
  - Markdown files are first split by heading hierarchy using `MarkdownHeaderTextSplitter` (H1–H4, with headings preserved in the body), and oversized sections are then split again.
  - Other file types use `RecursiveCharacterTextSplitter` (default: 400 characters with 80 overlap, prioritizing Chinese punctuation for sentence boundaries).
- **Dual indexing + fusion**:
  - Vector path: OpenAI-compatible embeddings (DashScope `text-embedding-v4` / Ollama `nomic-embed-text`), with pluggable vector backends: `InMemoryVectorStore` (default, zero dependency) or Milvus (`AIROBOT_VECTOR_STORE=milvus`, persistent ANN), both sharing the same interface.
  - Lexical path: `jieba` Chinese tokenization + `rank_bm25` (`BM25Okapi`) to compensate for vector models being less sensitive to proper nouns.
  - Fusion: rankings from both paths are merged by `reciprocal_rank_fusion` (RRF) in `app/rag/fusion.py`.
- **Semantic reranking** (`reranker.py`): `BAAI/bge-reranker-base` CrossEncoder reranks candidates. It uses lazy loading, prefers local cache (`HF_ENDPOINT` mirror), and automatically degrades to fusion order if errors occur.
- **Retrieval-augmented generation**: the `RAG_PROMPT` constrains the model to answer **only** based on the supplied documents, and to state clearly when the information is not present. Answers include sources (`file#chunk_number`) for traceability.

### 4. Reliability Engineering (`app/services/`)

| Component | Mechanism | Config |
|---|---|---|
| Retry `resilience.py` | Exponential backoff with tenacity (starts at 0.5s, max 8s), retries only recoverable errors (429 / 5xx / network / timeout), validation errors fail fast; both sync and async versions plus `safe_call` for non-critical fallback paths | `AIROBOT_RETRY_ATTEMPTS`, `AIROBOT_RETRY_MAX_WAIT` |
| Rate limiting `ratelimit.py` | In-process sliding window (per IP, 60s); returns JSON 429 on limit exceed; monitoring endpoints (`stats` / `traces`) are exempt | `AIROBOT_RATELIMIT_PER_MINUTE` |
| Semantic cache `semantic_cache.py` | First-turn, no-context questions reuse answers only when **cosine >= 0.75 and jieba lexical overlap >= 0.5**; within candidates, the highest cosine score that passes both thresholds is selected; dynamic data (orders) is not cached | `AIROBOT_CACHE_ENABLED`, `CACHE_THRESHOLD`, `CACHE_LEXICAL_THRESHOLD` |

### 5. Observability (`app/main.py` + `app/services/tracing.py`)

- Request logging middleware: method / path / status code / latency (`X-Process-Time-Ms` response header).
- Tracing: each request records stage latency for `cache_lookup / intent / retrieval / llm / first_token / total` (in-memory ring buffer of 300 items), and aggregates P95, average latency, cache hit rate, rate-limit blocks, and intent distribution.
- Visualization dashboard: `/dashboard` is a self-contained single page with a built-in **simulated user chat + full pipeline visualization** panel (streaming queries with real-time display of stage latency), plus 3-second polling of status cards, feature guides, and live request details.

### 6. Evaluation Framework (`eval/`)

- Evaluation set `eval/dataset/qa.jsonl`: 52 samples across 8 topics, including negative examples where the knowledge base does not contain the answer.
- Metrics: RAGAS Faithfulness / AnswerRelevancy / ContextPrecision / ContextRecall + LLM-as-Judge (1–5) + keyword-hit baseline.
- Reports: console tables + `eval/reports/report_<timestamp>.json` / `.md` (score band statistics + low-scoring samples).
- CI integration: the `eval` job runs automatically after configuring secrets (see [CI Gates](#ci-gates)).

## Tech Stack

| Layer | Components | Description |
|---|---|---|
| Service framework | FastAPI + uvicorn + Pydantic | Async APIs, automatic OpenAPI docs (`/docs`), SSE support |
| LLM orchestration | LangChain (LCEL / ChatPromptTemplate / InMemoryVectorStore / Milvus) | Intent routing, RAG pipeline, streaming generation |
| Multi-agent | CrewAI (`Agent` / `Task` / `Crew`) | Optional; automatically falls back if not installed |
| Model access | OpenAI-compatible protocol | DashScope (`qwen-plus` / `text-embedding-v4`), DeepSeek, Ollama (`qwen2.5` / `nomic-embed-text`) |
| Retrieval | `jieba` + `rank_bm25` (`BM25Okapi`), RRF fusion | Lexical recall and multi-path fusion |
| Reranking | sentence-transformers `bge-reranker-base` | Optional; lazy loading + fallback |
| Reliability | tenacity | Exponential backoff retries |
| Evaluation | ragas 0.3.9 + langchain-community 0.3.31 | Four RAGAS metrics + LLM-as-Judge |
| Deployment | Docker / docker-compose / GitHub Actions | Containerized deployment + CI gates |

## System Architecture

```text
Client (Mini Program / Web / Backend Service)
  │  POST /api/v1/chat | /chat/stream | /ingest
  ▼
FastAPI (app/main.py)
  │  ── Request logging middleware (latency stats) / sliding-window rate limiting middleware / unified exception handling
  │
  ├─ CrewAI available -> multi-agent (Intent Classifier -> Customer Service Executor, isolated thread)
  │                     ├─ search_knowledge (RAG retrieval-augmented generation)
  │                     ├─ query_order (Mock, production via HTTP to order-server)
  │                     └─ after_sale_rule (after-sales rules)
  │
  └─ Fallback -> built-in LangChain router (intent classification + RAG / chat, logically equivalent to Crew)
        │
  └─ Reliability layer: semantic cache (first-turn dual threshold) -> retry (LLM / embedding) -> rate limiting (entry point)
        │
  └─ RAG pipeline:
      document parsing (pypdf / python-docx) -> chunking (Recursive / Markdown headings)
        -> embedding (OpenAI-compatible) -> vector retrieval
        -> hybrid: jieba + BM25 lexical retrieval -> RRF fusion -> bge-reranker reranking
        -> RAG generation (with session memory)
        │
  └─ Observability: traces -> /dashboard console / /api/v1/traces / /api/v1/stats
```

**Full timing sequence of one chat request (non-streaming)**

```text
Client ──POST /api/v1/chat──▶ Rate limit middleware (allow / 429)
      ──▶ Semantic cache check (first-turn without context only: embedding -> dual-threshold; return immediately on hit)
      ──▶ Intent classification (LLM: knowledge / order / chat)
      ──▶ Execution: knowledge -> hybrid retrieval (vector + BM25 -> RRF -> rerank) -> RAG generation
              order     -> order tool (Mock / HTTP)
              chat      -> casual chat via LLM
      ──▶ Write session memory + write semantic cache (knowledge only) + record tracing
      ──▶ 200 JSON {reply, intent, sources, engine, cache_hit}
```

## Quick Start (From Clone to Run)

### Prerequisites

- Windows / macOS / Linux; use PowerShell on Windows.
- Python 3.10 - 3.13 (3.11 recommended): <https://www.python.org/downloads/>
- One OpenAI-compatible LLM / embedding service; choose one of the following:
  - **Local Ollama (recommended, free and offline)**: <https://ollama.com/>. After installation, run:
    `ollama pull qwen2.5:1.5b && ollama pull nomic-embed-text`
  - **Alibaba Cloud DashScope** (`qwen-plus` / `text-embedding-v4`, API key required)
  - **DeepSeek** (note: no embedding API, so you must pair it with DashScope or Ollama for embeddings)

### 0. One-Click Start (Recommended, Skip Steps 1–4 Below)

```powershell
cd E:\develop\airobot
.\start.ps1        # or double-click start.bat
```

`start.ps1` automatically performs: checking `.env` (creating one if missing) -> creating the virtual environment -> installing core dependencies -> checking whether Ollama and the models are ready -> starting the service and waiting for the health check -> automatically opening the dashboard in the browser at `http://localhost:8000/dashboard`.
To stop the service: `.\stop.ps1` (logs are stored in `.logs/`).

### 1. Create a Virtual Environment and Install Dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate

# Core dependencies (service + RAG + reliability, required)
pip install -r requirements.txt

# Optional capabilities, install as needed (automatic fallback if omitted; basic QA still works)
pip install -r requirements-extra.txt    # CrewAI multi-agent + bge-reranker reranking (includes torch, large size)
pip install -r requirements-eval.txt     # RAGAS evaluation
```

### 2. Configure Environment Variables

```powershell
Copy-Item .env.example .env     # macOS/Linux: cp .env.example .env
```

Edit `.env` according to your LLM service (see [Environment Variables](#environment-variables)). Example for local Ollama:

```ini
AIROBOT_LLM_BASE_URL=http://localhost:11434/v1
AIROBOT_LLM_API_KEY=ollama
AIROBOT_LLM_MODEL=qwen2.5:1.5b
AIROBOT_EMBEDDING_BASE_URL=http://localhost:11434/v1
AIROBOT_EMBEDDING_API_KEY=ollama
AIROBOT_EMBEDDING_MODEL=nomic-embed-text
```

### 3. Start the Service

```powershell
uvicorn app.main:app --reload --port 8000
```

At startup, `data/knowledge_base.md` (sample knowledge base, 7 chunks) is imported automatically.

### 4. Verify

```powershell
# Health check
Invoke-RestMethod http://localhost:8000/health

# Runtime metrics (knowledge-base chunk count / cache / rate limit, etc.)
Invoke-RestMethod http://localhost:8000/api/v1/stats

# Knowledge QA (RAG)
$body = @{ message = "How do I apply for a refund?"; session_id = "user-001" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/api/v1/chat -Method Post -Body $body -ContentType "application/json"
```

## API Documentation

> Interactive API docs: after startup, visit <http://localhost:8000/docs> (Swagger UI, auto-generated).

### GET /health

Health check; returns the current model configuration. No parameters.

```json
{"status": "ok", "llm_model": "qwen2.5:1.5b", "embedding_model": "nomic-embed-text"}
```

### POST /api/v1/chat

Intelligent chat (intent routing + RAG + tools). Request body:

```json
{
  "message": "Who pays the return shipping fee?",
  "session_id": "user-001"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| message | string | Yes | User message |
| session_id | string | No | Session identifier, default `default`; the same ID automatically carries multi-turn context |

Response 200:

```json
{
  "reply": "According to the platform rules, if a return is caused by product quality issues or mismatch with the description, the seller bears the shipping cost; if the buyer returns it for personal reasons, the buyer bears the cost.",
  "intent": "knowledge",
  "sources": ["knowledge_base.md#4", "knowledge_base.md#3"],
  "engine": "langchain",
  "used_crew": false,
  "cache_hit": false
}
```

| Field | Description |
|---|---|
| reply | Customer service response |
| intent | `knowledge` (knowledge QA) / `order` (order inquiry) / `chat` (casual chat) / `crew` (multi-agent) |
| sources | RAG source list (`file#chunk_number`); empty for non-knowledge responses |
| engine | `langchain` (built-in router) / `crew` (multi-agent) |
| used_crew | Whether CrewAI was actually used for this request |
| cache_hit | Whether the semantic cache was hit (on hit, the whole response is reused and returned within milliseconds) |

Error responses: `429` (rate limit, `{"detail":"Too many requests, please try again later."}`), `500` (unified exception handling).

### POST /api/v1/chat/stream

SSE streaming chat. The request body is the same as `/api/v1/chat`. The response is `text/event-stream`, with the following event sequence:

```text
data: {"type":"stage","stage":"rate_limit","msg":"Rate-limit check passed, request entered the service","ms":0,"ok":true}
data: {"type":"stage","stage":"cache","msg":"Semantic cache miss","ms":21.4,"ok":true}
data: {"type":"intent","intent":"knowledge"}
data: {"type":"stage","stage":"intent","msg":"Intent identified as knowledge","ms":547.2,"ok":true}
data: {"type":"stage","stage":"retrieval","msg":"Hybrid retrieval completed","ms":2138.1,
       "detail":{"vector_ms":22.2,"vector_hits":7,"bm25_ms":0.1,"bm25_hits":6,
                 "fusion_ms":0.0,"fused":7,"rerank_ms":2115.4,"rerank_enabled":true},
       "sources":["knowledge_base.md#0"],"ok":true}
data: {"type":"token","content":"According to the platform rules, "}
data: {"type":"token","content":"if the product has quality issues..."}
...
data: {"type":"stage","stage":"generate","msg":"RAG generation completed (53 tokens)","ms":517.4,"ok":true}
data: {"type":"done","intent":"knowledge","sources":["knowledge_base.md#4"],"total_ms":3225.6}
```

- The `stage` events include per-stage status / latency / details; during retrieval they further break down vector / BM25 / RRF / rerank timings and hit counts for end-to-end dashboard visualization.
- On semantic cache hit: before `intent`, the `cache` stage includes `hit: true`, followed by a single `token` (the full reused answer) + `done` with `cache_hit: true`.
- For `intent=order`, the `tool` stage indicates the tool invocation, and a single `token` returns the tool result.
- On exception: `stage.error` + `token` carrying the error message + `done`.

### POST /api/v1/ingest

Upload a document into the knowledge base (multipart form, field name `file`). Supports `.pdf / .docx / .md / .txt / .markdown`.

```powershell
curl.exe -X POST http://localhost:8000/api/v1/ingest -F "file=@data/knowledge_base.md"
```

```json
{"file_name": "knowledge_base.md", "chunks": 7, "total_chunks": 14}
```

### GET /api/v1/stats

Runtime metrics: knowledge-base chunk count, LLM / embedding models, multi-agent availability, hybrid retrieval / reranker switches, cache enabled state and hit statistics, rate-limit config, and blocked-request counts. This is one of the dashboard data sources.

### GET /api/v1/traces

Tracing data: stage latencies (cache / intent / retrieval / generation) for the most recent N requests (default 50) + aggregated statistics (P95, average latency, cache hit rate, rate-limit blocks, intent distribution).

### GET /dashboard

Visualization dashboard (open in browser), described in the next section.

## Visualization Dashboard

After starting the service, open <http://localhost:8000/dashboard> (self-contained single page, no external CDN dependency):

- **Simulated user chat**: directly simulate user questions in the dashboard (SSE streaming output, supports switching `session_id` to simulate multiple users, includes built-in quick questions).
- **End-to-end visualization**: during each conversation, it displays `rate-limit check -> semantic cache -> intent recognition -> hybrid retrieval -> tool / generation -> memory / cache write` with stage status and latency in real time; retrieval is further broken down into vector / BM25 / RRF / reranking.
- **Status cards**: service health / LLM / embedding / knowledge-base chunks / cache hit rate / P95 latency / rate-limit blocks / total requests.
- **Feature guide**: one-line descriptions of 16 capabilities for quickly understanding what the service can do.
- **Real-time execution monitoring**: stage-latency breakdown (cache lookup / retrieval / intent / generation) and status code for each conversation request; bar-style trend of total latency for the latest 20 requests (auto-refresh every 3 seconds).
- Data sources: `GET /api/v1/traces` + `GET /api/v1/stats`; monitoring endpoints are exempt from business rate limiting.

## Docker Deployment

> Docker Desktop (Windows/macOS) or Docker Engine (Linux) is required.

### Local Ollama Mode (Default, Free and Offline)

```powershell
docker compose up -d --build
docker compose logs -f airobot
Invoke-RestMethod http://localhost:8000/api/v1/stats
```

- The compose stack includes a built-in `ollama` service. Its entrypoint automatically runs `ollama pull` for the model configured in `.env`, so the first startup may be slow.
- Inside the container, the LLM / embedding endpoints automatically point to `http://ollama:11434/v1` (resolved by service name, no need to modify `.env`).
- `./data` is mounted as a volume (hot updates for the knowledge base), and the `hf-cache` volume reuses downloaded reranker model cache.

### Cloud API Mode

Edit `docker-compose.yml`, change the two `AIROBOT_*_BASE_URL` values for `airobot` to DashScope endpoints, fill the API key in `.env`, optionally remove the `ollama` service, and then rerun `docker compose up -d --build`.

### Build Acceleration

- pip uses the Tsinghua mirror by default (`ARG PIP_INDEX_URL` can be overridden with Alibaba Cloud or another mirror).
- `--mount=type=cache` reuses pip download cache: changing only code leads to near-instant rebuilds; changing dependencies downloads only newly added packages.
- If pulling the base image is slow: in Docker Desktop -> Settings -> Docker Engine, configure `registry-mirrors` (for example `["https://docker.m.daocloud.io", "https://dockerproxy.com"]`). Base images only need to be pulled once.

## CI Gates

`.github/workflows/ci.yml`: on push / PR, three sequential jobs run automatically.

| Job | Content | Notes |
|---|---|---|
| `build` | `pip install` + `py_compile` syntax check | Mandatory |
| `test` | Offline unit tests for reliability engineering + service import smoke test | Mandatory |
| `eval` | RAGAS smoke evaluation on the first 5 samples | Enabled after configuring secrets |

Configure repository secrets (Settings -> Secrets and variables -> Actions): `AIROBOT_LLM_API_KEY`, `AIROBOT_EMBEDDING_API_KEY`. If they are not configured, `eval` is skipped automatically, while `build` and `test` still remain enforced. Evaluation reports are uploaded as workflow artifacts.

## Evaluation (RAGAS)

```powershell
# Smoke test: first 5 samples
$env:AIROBOT_RERANK_ENABLED="false"; python eval\run_eval.py --limit 5
# Full 52 samples (four RAGAS metrics + Judge + baseline)
python eval\run_eval.py
```

- Evaluation set: `eval/dataset/qa.jsonl` (52 samples, 8 topics, including negative examples not covered by the knowledge base)
- Metrics: RAGAS Faithfulness / AnswerRelevancy / ContextPrecision / ContextRecall + LLM-as-Judge (1–5) + keyword-hit baseline
- Output: console tables + `eval/reports/report_<timestamp>.json` / `.md` (score bands + low-scoring samples)
- Note: ragas 0.3.9 should be paired with `langchain-community==0.3.31` (see `requirements-eval.txt`)

## Retrieval and Chunking Experiments

```powershell
python scripts\bench_retrieval.py --top-k 5     # hit rate and latency for vector / bm25 / hybrid_rrf / hybrid_rerank
python scripts\bench_splitter.py --top-k 3      # retrieval hit rate under different chunking parameters
python scripts\ingest.py data\knowledge_base.md # CLI ingest for knowledge files (standalone process)
```

Reference measurement (52-sample evaluation set, top-k=2): vector 67% -> bm25 98% / hybrid_rrf 98%, demonstrating the necessity of hybrid retrieval.

## Design Decisions

- **Why maintain two implementations (CrewAI + built-in routing)?** A multi-agent framework is the orchestration layer, while business tools are the execution layer. If the framework is unavailable or incompatible by version, the service degrades to an equivalent internal router to preserve availability.
- **How is RAG quality ensured?** Through chunking parameters, Top-K, prompt constraints, a RAGAS evaluation loop, and comparative experiment data on hybrid retrieval / reranking.
- **How does the semantic cache avoid false positives?** It uses dual thresholds of cosine similarity + jieba lexical overlap, caches only first-turn no-context questions, excludes dynamic data (orders), and exposes hits via the `cache_hit` field.
- **How can order queries connect to real data?** It is currently Mock. Two production approaches:
  - Option A (Java-side routing): after recognizing `intent=order`, the business backend queries orders itself.
  - Option B (AI-side invocation): modify the `airobot` order tool to call an order server over HTTP (configure `AIROBOT_ORDER_API_URL` + timeout fallback).
- **How can in-memory components be productionized?** The vector store / session memory / semantic cache / rate limiting are currently implemented in-process, but their interfaces are consistent with Chroma / FAISS / Milvus and Redis, so they can be replaced with minimal effort (see table below).

| Current Implementation | Production Replacement |
|---|---|
| `InMemoryVectorStore` / Milvus (already built in, switched by `AIROBOT_VECTOR_STORE`) | Chroma / FAISS (persistence + ANN indexing, same interface and still replaceable later) |
| In-process session memory | Redis / SQLite persistence |
| In-process semantic cache / rate limiting | Redis (distributed cache and counters), gateway-level rate limiting |
| No authentication | Unified gateway auth + `X-API-Key` header validation |
| `query_order` Mock | HTTP integration with order-server (idempotency + timeout fallback) |

## Project Structure

```text
airobot/
├── app/
│   ├── main.py            FastAPI entry: APIs / middleware / SSE / exception handling / dashboard
│   ├── config.py          Environment variable config (dotenv)
│   ├── schemas.py         Request / response models
│   ├── agents/            CrewAI orchestration (`crew.py`) and toolset (`tools.py`)
│   ├── rag/               loader (parsing) / retriever (retrieval + generation) / lexical (BM25) / fusion (RRF) / reranker
│   ├── services/          chat (orchestration) / memory (session) / resilience (retry) / ratelimit (rate limiting)
│   │                      / semantic_cache (cache) / tracing (request tracing)
│   └── static/            `dashboard.html` visualization dashboard
├── data/                  Knowledge base files (auto-ingested on startup) and experiment-output CSVs
├── eval/                  `run_eval.py` + `dataset/qa.jsonl` (52 samples) + `reports/`
├── scripts/               Retrieval / chunking comparison experiments, CLI ingest
├── tests/                 `test_stability.py` / `test_tracing.py` offline unit tests
├── .github/workflows/     `ci.yml` (`build -> test -> eval` gates)
├── Dockerfile / docker-compose.yml / docker-compose-milvus.yml / .dockerignore   Containerized deployment (Milvus single-container orchestration)
├── start.ps1 / stop.ps1 / start.bat   One-click start / stop (Windows)
├── requirements.txt       Core runtime dependencies
├── requirements-eval.txt  RAGAS evaluation dependencies
├── requirements-extra.txt Optional: CrewAI multi-agent + bge-reranker reranking
└── .env.example           Environment variable template (copy to `.env` before use)
```

## Environment Variables

| Variable | Description |
|---|---|
| `AIROBOT_LLM_BASE_URL` / `API_KEY` / `MODEL` | LLM endpoint (OpenAI-compatible: DashScope / DeepSeek / Ollama) |
| `AIROBOT_EMBEDDING_BASE_URL` / `API_KEY` / `MODEL` | Embedding model endpoint (DashScope `text-embedding-v4` or Ollama `nomic-embed-text`) |
| `AIROBOT_USE_CREW` | Whether to prefer CrewAI (automatically falls back if not installed) |
| `AIROBOT_TOP_K` / `CHUNK_SIZE` / `CHUNK_OVERLAP` | Recall count and chunking parameters |
| `AIROBOT_HYBRID_ENABLED` / `VECTOR_TOP_K` / `BM25_TOP_K` / `FUSION_TOP_K` | Hybrid retrieval switch and recall counts for each path |
| `AIROBOT_RERANK_ENABLED` / `RERANK_MODEL` | bge-reranker switch and model |
| `AIROBOT_RETRY_ATTEMPTS` / `RETRY_MAX_WAIT` | Retry count and maximum backoff time |
| `AIROBOT_RATELIMIT_ENABLED` / `RATELIMIT_PER_MINUTE` | Rate limiting switch and per-minute cap (per IP, 60-second window) |
| `AIROBOT_CACHE_ENABLED` / `CACHE_THRESHOLD` / `CACHE_LEXICAL_THRESHOLD` / `CACHE_MAX_ENTRIES` | Semantic cache switch and dual-threshold parameters |
| `AIROBOT_MEMORY_MAX_TURNS` / `AIROBOT_MEMORY_RETRIEVE_TURNS` | Session memory retention turns / context turns included in generation |
| `AIROBOT_VECTOR_STORE` / `MILVUS_URI` / `MILVUS_TOKEN` / `MILVUS_COLLECTION` / `MILVUS_RESET_ON_START` | Vector backend (`inmemory` / `milvus`) and Milvus connection, collection, startup reset switch |

## FAQ

**Q: Can it run without an API key?** Yes. The service itself can start normally (health checks / document parsing / retrieval all remain available), while the chat API will return a prompt saying `AIROBOT_LLM_API_KEY` is not configured. Installing local Ollama is the recommended free way to run the full pipeline.

**Q: What happens if `crewai`, `ragas`, or `sentence-transformers` is not installed?** The system degrades automatically: multi-agent falls back to the built-in LangChain router, evaluation scripts require `requirements-eval.txt`, and reranking falls back to the RRF fusion order.

**Q: What if reranker model download is slow or hangs?** The project already includes an HF mirror (`HF_ENDPOINT=https://hf-mirror.com`) and a local-cache-first strategy; you can also disable it with `AIROBOT_RERANK_ENABLED=false`.

**Q: Do I need to rebuild the Docker image every time I change code?** No. For daily development, use the host `.venv` + `uvicorn --reload`; build the image only for release / delivery with `docker compose up -d --build` (code-only changes rebuild in seconds; see “Build Acceleration”).

**Q: How can Java / Node backends call it?** Use HTTP/SSE against `/api/v1/chat` or `/api/v1/chat/stream`; see [API Documentation](#api-documentation). In production, using a gateway + internal network isolation + `X-API-Key` authentication is recommended.
