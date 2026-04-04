# 跨境电商 AI 助手平台 (Mini Claw Platform)

LangGraph + Skills 引擎驱动的 Web App AI 助手平台，为跨境电商团队提供个性化 Bot 服务。

## 技术栈

- **后端**: FastAPI + LangGraph + LiteLLM + SQLAlchemy 2.0 (async)
- **前端**: Next.js + assistant-ui (`useAssistantTransportRuntime`)
- **数据库**: PostgreSQL 17 + pgvector (向量语义搜索)
- **流式协议**: assistant-stream (`append_langgraph_event`)
- **CLI 沙箱**: Docker 容器隔离执行

## 快速开始

### 一键启动（推荐）

```bash
./scripts/start.sh
```

自动检测端口占用（8000/3000）→ 释放 → 启动后端 + 前端，`Ctrl+C` 一键停止。

### 分步启动

#### 1. 启动数据库

```bash
docker compose up -d
```

#### 2. 初始化数据库

```bash
cd backend
alembic upgrade head
```

#### 3. 启动后端

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

#### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

### 5. 构建 CLI 沙箱镜像（可选）

```bash
docker build -t mclaw-sandbox:latest -f sandbox/Dockerfile sandbox/
```

## 项目结构

```
mini_claw_platform/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/                # REST API 路由
│   │   ├── engine/             # LangGraph Agent 引擎
│   │   ├── models/             # SQLAlchemy 数据模型
│   │   ├── schemas/            # Pydantic 请求/响应模型
│   │   ├── services/           # 业务逻辑层
│   │   └── tools/              # LangChain Tool 实现
│   ├── alembic/                # 数据库迁移
│   └── tests/                  # 测试
├── frontend/                   # Next.js 前端
│   ├── app/                    # 页面
│   └── components/             # 组件 (assistant-ui)
├── scripts/                    # 脚本 (启动、部署等)
├── docs/                       # 文档
├── sandbox/                    # CLI 沙箱 Docker 镜像
├── docker-compose.yml          # PG + Redis 开发环境
└── .env.example                # 环境变量模板
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/assistant` | Chat 端点 (assistant-stream 协议) |
| POST | `/auth/register` | 用户注册 |
| POST | `/auth/login` | 用户登录 |
| GET  | `/auth/me` | 当前用户信息 |
| GET  | `/bots/` | 列出我的 Bot |
| POST | `/bots/` | 创建 Bot |
| GET  | `/bots/{id}` | 获取 Bot 详情 |
| PATCH| `/bots/{id}` | 更新 Bot |
| GET  | `/skills/` | 列出所有 Skill |
| POST | `/skills/` | 创建 Skill |
| PATCH| `/skills/{id}` | 更新 Skill |

## 运行测试

```bash
cd backend
python3 -m pytest tests/ -v
```
