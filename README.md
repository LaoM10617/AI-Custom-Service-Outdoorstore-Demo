# BlueHarbor Outdoor Store AI Support

一个面向虚构户外用品商店的 AI 客服与业务自动化实验项目。项目目标不是冒充真实品牌，也不是把演示代码包装成生产系统，而是用最低成本接入 Shopify 开发商店，逐步练习真实订单、Webhook、权限、安全、审计、评测和人工审批等落地问题。

> **项目状态：可运行 Demo，正在向真实业务模拟演进。** 当前聊天、RAG、流式响应、监控和稳定性组件已有实现；订单查询仍为 Mock，Shopify 接入、持久化、鉴权和高风险操作审批尚待完成。请勿直接面向真实客户或真实交易上线。

## 业务背景

BlueHarbor 是一家虚构的户外用品网店，销售露营灯、登山水壶、防水背包和数字版露营清单。这个业务背景用于模拟：

- 商品规格、配送和售后政策问答；
- 订单、付款、履约、物流和退款状态查询；
- 商品破损、地址修改、取消订单等客服工单；
- Shopify Webhook 重复投递、外部 API 超时和模型服务异常；
- AI 提议操作、人工审批、执行结果和审计追踪。

BlueHarbor 与 Allianz 没有关系。本仓库不得用于冒充 Allianz 或任何其他真实企业。

## 落地目标

项目采用渐进式路线，优先建立真实业务边界，而不是过早引入复杂基础设施。

### 阶段 0：当前 Demo

- FastAPI 同步聊天和 SSE 流式聊天；
- `knowledge / order / chat` 意图路由；
- PDF、DOCX、Markdown、TXT 知识库导入；
- 向量检索 + BM25 + RRF，可选 BGE reranker；
- 可选 CrewAI 双 Agent，失败时降级到内置路由；
- 进程内会话记忆、限流、语义缓存和链路追踪；
- 自包含监控 Dashboard、评测数据、Docker 和 CI；
- 订单查询为固定 Mock，不代表真实业务集成。

### 阶段 1：Shopify 真实业务模拟

- 创建免费的 Shopify Development Store 和测试订单；
- 通过自定义应用接收订单、履约、取消和退款 Webhook；
- 使用 SQLite 保存订单镜像、Webhook 事件和审计日志；
- 用真实只读订单查询替换 `query_order` Mock；
- 实现 Webhook HMAC 校验、事件幂等和订单归属验证；
- 增加订单查询、重复事件和越权访问的集成测试。

### 阶段 2：单人可运营试生产

- Dashboard 和管理接口鉴权；
- 会话、缓存和限流迁移到 Redis，业务数据迁移到 PostgreSQL；
- 上传大小、类型、超时和并发限制；
- 结构化日志、敏感信息脱敏、指标和告警；
- 退款、取消、修改地址等高风险操作进入人工审批队列；
- 完整的失败恢复、数据保留和隐私删除流程。

## 当前架构

```text
用户 / Dashboard
       |
       v
FastAPI API + SSE
       |
       +-- 语义缓存
       +-- 意图路由
       +-- RAG：向量 + BM25 + RRF + 可选 reranker
       +-- 订单工具：当前 Mock，阶段 1 替换为 Shopify 订单镜像/API
       +-- 会话记忆
       |
       v
链路追踪 / 运行指标 / Dashboard

阶段 1 新增：
Shopify Development Store --Webhooks--> HMAC 校验与幂等处理 --> SQLite
                                                        |
客服订单查询 --------------------------------------------+
```

## 核心接口

- `GET /health`：健康检查；
- `POST /api/v1/chat`：同步客服响应；
- `POST /api/v1/chat/stream`：SSE 流式客服响应；
- `POST /api/v1/ingest`：知识文档上传，当前尚无管理员鉴权；
- `GET /api/v1/stats`：运行状态；
- `GET /api/v1/traces`：最近请求和延迟汇总；
- `GET /dashboard`：聊天和链路监控页面；
- `GET /docs`：FastAPI OpenAPI 文档。

示例请求：

```powershell
$body = @{
  message = "订单 202608090001 到哪里了？"
  session_id = "demo-user-001"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://localhost:8000/api/v1/chat `
  -Method Post `
  -Body $body `
  -ContentType "application/json"
```

## 本地启动

### 前置条件

- Python 3.10–3.13，推荐 3.11；
- Docker Desktop，可选；
- 一个 OpenAI 兼容的 LLM 和 Embedding 服务；
- 最低成本方案为本地 Ollama。

### Windows 一键启动

```powershell
git clone <repository-url>
cd <repository-directory>
Copy-Item .env.example .env
.\start.ps1
```

脚本会创建 `.venv`、安装核心依赖、检查 Ollama 并启动服务。Dashboard 地址为 <http://localhost:8000/dashboard>。

停止服务：

```powershell
.\stop.ps1
```

### 手动启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

可选能力：

```powershell
pip install -r requirements-extra.txt # CrewAI、reranker、Milvus
pip install -r requirements-eval.txt  # RAGAS 评测
```

### Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose logs -f blueharbor-support
Invoke-RestMethod http://localhost:8000/health
```

Compose 默认启动本地 Ollama，并自动拉取配置的聊天和向量模型。首次启动可能较慢。

## 配置

复制 `.env.example` 为 `.env` 后选择模型服务。Ollama 示例：

```ini
AIROBOT_LLM_BASE_URL=http://localhost:11434/v1
AIROBOT_LLM_API_KEY=ollama
AIROBOT_LLM_MODEL=qwen2.5:3b
AIROBOT_EMBEDDING_BASE_URL=http://localhost:11434/v1
AIROBOT_EMBEDDING_API_KEY=ollama
AIROBOT_EMBEDDING_MODEL=nomic-embed-text
```

`AIROBOT_*` 是项目早期名称留下的兼容性前缀，当前仍被代码、CI 和已有 `.env` 使用。品牌调整阶段不立即改名，以免破坏现有部署；后续可提供 `BLUEHARBOR_*` 别名并分阶段弃用旧前缀。

常用配置包括：

- `AIROBOT_USE_CREW`：是否优先使用 CrewAI；
- `AIROBOT_HYBRID_ENABLED`：是否启用混合检索；
- `AIROBOT_RERANK_ENABLED`：是否启用语义重排；
- `AIROBOT_VECTOR_STORE`：`inmemory` 或 `milvus`；
- `AIROBOT_RATELIMIT_PER_MINUTE`：单 IP 每分钟请求限制；
- `AIROBOT_CACHE_ENABLED`：是否启用语义缓存；
- `AIROBOT_MEMORY_MAX_TURNS`：每个会话保留的最大轮数。

完整配置及说明见 [.env.example](.env.example)。

## 知识库

当前示例知识位于 `data/knowledge_base.md`，服务启动时会自动导入。按照 BlueHarbor 业务背景，建议逐步拆分为：

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

每份业务文档应增加版本、生效日期、负责人和适用地区，从而测试政策更新、缓存失效和答案可追溯性。

## 测试与评测

语法和现有离线测试：

```powershell
python -m compileall -q app eval scripts tests
python tests/test_stability.py
python tests/test_tracing.py
```

检索实验和评测：

```powershell
python scripts/bench_retrieval.py --top-k 5
python scripts/bench_splitter.py --top-k 3
$env:AIROBOT_RERANK_ENABLED="false"
python eval/run_eval.py --limit 5
```

`eval/dataset/qa.jsonl` 包含 52 条示例。Shopify 接入后应新增真实业务回归集，至少覆盖：

- 正确和错误订单归属；
- 不存在、取消和已退款订单；
- Webhook 重放和乱序；
- Shopify、LLM 和 Embedding 超时或限流；
- Prompt injection 和敏感信息请求；
- 政策更新后的缓存与引用一致性。

## 安全边界

当前版本尚未完成生产安全要求：

- `/ingest`、`/stats`、`/traces` 和 Dashboard 尚无鉴权；
- 上传接口尚无文件大小和解析超时限制；
- 会话、缓存、限流和默认向量库均为进程内状态；
- 订单工具返回 Mock 数据；
- 尚无客户身份及订单归属验证；
- 尚无高风险业务动作审批队列。

接入 Shopify 时，模型不得直接持有 Shopify 管理凭据。模型只能调用后端定义的窄工具。退款、取消订单、修改地址、补发和删除客户数据等操作必须默认进入人工审批。

## 项目结构

```text
app/
  main.py              FastAPI、接口、中间件和 SSE
  config.py            环境变量配置
  agents/              CrewAI 编排和业务工具
  rag/                 文档加载、混合检索、融合与重排
  services/            聊天、记忆、重试、限流、缓存和追踪
  static/dashboard.html
data/                   示例知识库
eval/                   评测脚本和数据集
scripts/                检索与切分实验
tests/                  离线单元测试
.github/workflows/      CI
```

## 完成定义

当以下条件全部满足时，项目才进入可试生产状态：

- 订单来自 Shopify，不再依赖 Mock；
- Webhook 具备签名验证、幂等和失败重试；
- 客户身份与订单归属可验证；
- 管理和上传接口有鉴权；
- 关键业务数据持久化；
- 高风险操作必须人工审批；
- 日志脱敏且可通过 request ID 追踪；
- 外部服务故障时能够安全降级；
- 关键业务场景有自动化集成测试。

## License

本项目使用仓库中 [LICENSE](LICENSE) 所述许可证。
