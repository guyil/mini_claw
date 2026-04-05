# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mini Claw (小爪) is a cross-border e-commerce AI assistant platform. It uses a LangGraph-based agent engine with a Skills system, backed by a FastAPI backend and Next.js frontend connected via the assistant-stream protocol.

## Common Commands

### Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000          # Start dev server
python3 -m pytest tests/ -v                         # Run all tests
python3 -m pytest tests/test_api/test_health.py -v  # Run single test file
alembic upgrade head                                # Apply DB migrations
alembic revision --autogenerate -m "description"    # Create new migration
ruff check app/                                     # Lint
ruff format app/                                    # Format
```

### Frontend

```bash
cd frontend
npm install        # Install dependencies
npm run dev        # Start dev server (Next.js + Turbopack on :3000)
npm run build      # Production build
```

### Infrastructure

```bash
docker compose up -d                                          # Start PostgreSQL (pgvector) + Redis
docker build -t mclaw-sandbox:latest -f sandbox/Dockerfile sandbox/  # Build CLI sandbox image
./scripts/start.sh                                            # One-command start (backend + frontend)
```

## Architecture

### Streaming Protocol

Frontend (`assistant-ui` with `useAssistantTransportRuntime`) communicates with backend via the `assistant-stream` protocol. The backend's `/assistant` endpoint (`backend/app/api/chat.py`) receives commands, streams LangGraph events through `append_langgraph_event`, and returns a `DataStreamResponse`. The frontend runtime provider is in `frontend/app/MyRuntimeProvider.tsx`.

### LangGraph Agent Engine (`backend/app/engine/`)

The agent is a dynamically-built `StateGraph` constructed per-request in `graph_builder.py` based on the Bot's DB config. The graph flow is:

```
START → memory → router → (direct_answer→END | use_tool→tool_executor→router | use_skill→skill_loader→skill_executor→END)
```

- **State** (`state.py`): `AgentState` TypedDict with messages, bot_config, available_skills, active_skill, skill_instructions, memory_context, and session metadata.
- **Nodes** (`nodes.py`): `memory_node` (retrieves context), `router_node` (decides action), `skill_loader_node` (loads skill instructions from DB), `skill_executor_node` (runs skill with tools).
- **Prompt Builder** (`prompt_builder.py`): Assembles system prompts from bot soul, instructions, user context, skill summaries, and memory context.

### Tools (`backend/app/tools/`)

LangChain tools injected into the agent: `memory_tools` (vector-based memory with pgvector), `sandbox_tools` (Docker container code execution), `feishu_tools` (Feishu/Lark API integration), `web_tools` (URL fetching).

### Skills System

Skills are configurable instruction sets stored in DB. The router can activate a skill via the `activate_skill` tool, which triggers `skill_loader` → `skill_executor` nodes. Skills complete via the `skill_complete` tool.

### Data Layer

- **ORM models** in `backend/app/models/` (SQLAlchemy 2.0 async): User, Bot, Conversation, Skill, Memory, Tool.
- **Pydantic schemas** in `backend/app/schemas/` for API request/response validation.
- **Services** in `backend/app/services/` for business logic (bot_service, skill_service, memory_service, feishu_service, sandbox_pool).
- **DB**: PostgreSQL 17 with pgvector extension; migrations via Alembic.

### Auth

JWT-based auth with Feishu (Lark) OAuth support. Auth routes in `backend/app/api/auth.py`. The chat endpoint gracefully degrades when no auth token is present (uses anonymous user with default bot).

## Configuration

Backend config via `pydantic-settings` in `backend/app/config.py`. Reads from `.env` file (see `.env.example`). LLM calls go through LiteLLM (`langchain-litellm`), allowing model switching via `DEFAULT_MODEL` env var.

## Code Style

- Backend: Python 3.11+, ruff for linting/formatting, line length 100.
- Frontend: TypeScript, Tailwind CSS v4, shadcn/ui components in `frontend/components/ui/`.
- Backend tests use pytest with `asyncio_mode = "auto"`.
- Primary language in code comments and UI strings is Chinese.
