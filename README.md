# 安心保 · 智能保险顾问 Agent 平台

一个面向保险商城的 AI 保险顾问：用自然语言完成产品咨询、方案推荐、条款问答与理赔引导。项目采用前后端分离 + AI 服务独立部署的架构，覆盖 **Agent 编排、RAG 知识库、流式对话、人工确认（HITL）** 的完整链路。

> 技术关键词：Python · FastAPI · LangGraph · RAG · Milvus · BGE-M3 · PostgreSQL · SSE · React · Docker Compose

---

## 功能特性

- **多意图 Agent 编排**：LangGraph 父图做意图路由，子图分别承载「闲聊 / 保险推荐 / 理赔咨询」，另有兜底与转人工分支。
- **推荐流程与人工确认**：收集被保人画像 → 查询候选产品 → 生成组合方案 → `interrupt` 暂停等待用户确认 → 确认后落库，模型不能直接写库。
- **RAG 条款问答**：MinerU 解析条款 PDF → 父子分块 → BGE-M3 稠密/稀疏向量 → Milvus 混合检索 → Cross-Encoder 重排 → 回查父块，回答带条款级引用。
- **会话记忆**：基于 PostgreSQL Checkpointer 持久化 LangGraph 状态，服务重启后同一 `thread_id` 仍可恢复。
- **流式对话**：SSE 推送文本增量与结构化卡片，前端逐字渲染。
- **一键基础设施**：Docker Compose 编排 PostgreSQL、Milvus、etcd、MinIO、业务服务与前端。

---

## 系统架构

```
浏览器 (React + Ant Design)
   │
   ▼
nginx
   ├── /business-api/ → biz-service :8001   （用户 / 产品 / 方案 / 保单 / 理赔）
   └── /agent-api/    → agent-service :8002 （AI 编排 / RAG / SSE）
                            │
                            ├── PostgreSQL 16   （业务数据 + Checkpoint）
                            ├── Milvus 2.6      （向量检索，依赖 etcd + MinIO）
                            └── DeepSeek API    （对话与结构化输出）
```

---

## 目录结构

```
hm-insurance/
├── agent-service/          # AI 服务（FastAPI + LangGraph + RAG）
│   ├── app/
│   │   ├── api/            # 对话、会话、健康检查接口
│   │   ├── orchestrator/   # 父图、意图路由、SSE 事件转换
│   │   ├── workflows/      # chitchat / recommendation / claim 子图
│   │   ├── rag/            # 解析、切分、向量化、检索、重排
│   │   ├── clients/        # 业务服务 HTTP 客户端
│   │   └── core/           # 配置、日志、数据库、代理处理
│   ├── scripts/            # 知识库灌入脚本
│   └── schema.sql          # agent 库建表脚本
├── biz-service/            # 业务服务（FastAPI + PostgreSQL）
├── frontend/               # 前端（React + TypeScript + Vite）
├── deploy/                 # Docker Compose 与初始化 SQL
└── README.md
```

---

## 快速开始

### 0. 前置依赖

- Docker + Docker Compose
- Python 3.14（或与 `agent-service/pyproject.toml` 一致）
- Node.js 20+

### 1. 启动基础设施

```bash
cd deploy
cp .env.example .env        # 按需修改数据库密码、端口
docker compose up -d
docker compose ps           # 等到 postgres / milvus / minio 均为 healthy
```

### 2. 配置 AI 服务

```bash
cd agent-service
cp .env.example .env
```

至少填写：

```dotenv
DATABASE_URL=postgresql://insurance:insurance123@localhost:5432/insurance_agent
MILVUS_URI=http://localhost:19530
DEEPSEEK_API_KEY=sk-你的key
MINERU_TOKEN=你的MinerU token      # 灌知识库时需要
EMBEDDING_MODEL=BAAI/bge-m3
RERANK_MODEL=BAAI/bge-reranker-v2-m3
```

### 3. 启动 AI 服务

```bash
cd agent-service
uv sync
uv run python -m app.main          # 监听 http://127.0.0.1:8002
```

首次启动会自动下载约 4.3GB 的 BGE-M3 与 Reranker 模型（可提前放到本地目录并用 `EMBEDDING_MODEL` / `RERANK_MODEL` 指向）。

### 4. 灌入知识库（可选）

```bash
cd agent-service
uv run python -m scripts.rag_ingest \
  --dir ../data/raw/kb \
  --document-type clause \
  --version v1 \
  --continue-on-error
```

> 需要 MinerU Token（免费注册）。`data/` 目录因版权原因未随仓库提供，请自行放入条款 PDF。

### 5. 启动业务服务与前端

```bash
# 业务服务
cd biz-service
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001

# 前端
cd frontend
npm install
npm run dev        # http://localhost:5173
```

前端开发服务器需要把 `/business-api` 与 `/agent-api` 代理到对应后端（可参考 `frontend/nginx.conf`）。

---

## 核心配置说明

| 变量 | 说明 |
|---|---|
| `DATABASE_URL` | PostgreSQL 连接串（agent 库） |
| `MILVUS_URI` | Milvus 地址，默认 `http://localhost:19530` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `MINERU_TOKEN` | MinerU PDF 解析 Token |
| `EMBEDDING_MODEL` / `RERANK_MODEL` | 本地模型路径或 HuggingFace 仓库名 |
| `EMBEDDING_DEVICE` | `cpu` / `cuda`，显存不足时用 CPU |
| `BUSINESS_SERVICE_URL` | biz-service 地址 |
| `JWT_SECRET` | 与 biz-service 保持一致 |

---

## 主要接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/chat` | 对话（SSE 流式） |
| GET | `/api/v1/chat-threads` | 会话列表 |
| POST | `/api/v1/chat-threads` | 新建会话 |
| GET | `/api/v1/chat-threads/{id}/messages` | 历史消息 |
| DELETE | `/api/v1/chat-threads/{id}` | 删除会话 |
| GET | `/api/v1/health` | 健康检查 |

---

## RAG 处理流程

```
离线建库：PDF → MinerU 解析 → DeepSeek 修复 Markdown → 父子分块
        → BGE-M3 向量化（dense + sparse）→ 子块写 Milvus、父块写 PostgreSQL

在线检索：问题 → 双路召回（candidate_k=50）→ RRF 融合
        → Cross-Encoder 重排（top_k=5）→ 回查父块 → 证据列表（source_id）
```

---

## 踩坑记录（Windows 环境）

- **事件循环**：psycopg 异步连接不支持 Proactor，需切换到 `WindowsSelectorEventLoopPolicy`。
- **系统代理**：Clash 等代理会让内网请求返回 502、gRPC 握手超时，内网客户端需 `trust_env=False`，Milvus 需关闭 gRPC HTTP 代理。
- **NO_PROXY**：代理软件写入的 `[::1]` 会让 httpx 解析崩溃，启动时需清洗。
- **显存不足**：4GB 显卡装不下两个模型，灌库时设置 `EMBEDDING_DEVICE=cpu`。

---

## License

MIT
