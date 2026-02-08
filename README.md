# Browser Flow Backend

FastAPI backend for **Agentic URL Context Service**: URL context collection, intent understanding, task identification, and action execution with PostgreSQL and optional Opik observability.

---

## Table of Contents

- [Agentic Core](#agentic-core)
- [APIs](#apis)
- [Database Architecture](#database-architecture)
- [Opik Integration](#opik-integration)
- [Quick Start](#quick-start)

---

## Agentic Core

The backend is built around an **agentic core** that routes user intents to specialized agents, each composed of shared building blocks and optional MCP (Model Context Protocol) tool servers.

### Components

| Component | Role |
|-----------|------|
| **BaseAgent** | Abstract base for all agents. Provides `reason()`, `use_tool()`, `evaluate()`, and optional `retrieve_knowledge()` via a reasoning engine, tool integration, and evaluator. |
| **AgentRegistry** | File-based registry (`app/config/agents_registry.json`) mapping **task types** to agent classes. Loads metadata (capabilities, required tools, MCP servers) and supports discovery by capabilities/task types. |
| **AgentSpawner** | Factory that instantiates agents with: **PromptManager**, **ToolIntegration**, **Evaluator**, **ReasoningEngine**, optional **SemanticKnowledgeService**, and MCP servers (Excel, Notion, Composio). Can inject `excel_tools`, `notion_client`, and Composio fallback when required tools are missing. |
| **ReasoningEngine** | Uses Claude (via `claude_agent_sdk`) for reasoning and tool use. Accepts prompts, context, allowed tools, and MCP servers; returns structured results. Integrates with Opik (`@track`, `store_prompt`) when enabled. |
| **ToolIntegration** | Bridges agents to **ToolRegistry** and MCP: discover tools by capability, execute by name. |
| **TaskOrchestrator** | Entry point after **TaskIdentificationService**. Decides atomic vs non-atomic execution, looks up the agent for the identified `task_type` from the registry, spawns the agent via **AgentSpawner**, and runs it with the provided context and task input. |

### Flow

1. **Task identification** — `TaskIdentificationService` classifies user input (and optional URLs) into a `TaskType` and intent.
2. **Context processing** — `SemanticKnowledgeService` processes URLs/text into structured contexts; **UserContextRepository** persists them (with embeddings and optional parent-topic linking).
3. **Orchestration** — `TaskOrchestrator.orchestrate_task()` gets the agent class and metadata from **AgentRegistry** for that `task_type`, then **AgentSpawner** builds the agent (with the right tools/MCP servers).
4. **Execution** — The agent’s `execute()` runs (e.g. **DataExtractionAgent**, **NoteTakingAgent**), using the reasoning engine and tools; result is returned and stored on **UserTask**.

### Task Types

Defined in `app/core/task_types.py` (e.g. `NOTE_TAKING`, `ADD_TO_KNOWLEDGE_BASE`, `CREATE_TODO`, `EXTRACT_DATA_TO_SHEET`, `EXTRACT_DATA_TABLE`). Supported types are wired to agents in `agents_registry.json`.

### Agents

- **DataExtractionAgent** — `EXTRACT_DATA_TO_SHEET`: parses text and writes structured data to Excel via MCP Excel tools.
- **NoteTakingAgent** — `NOTE_TAKING`, `CREATE_TODO`, `EXTRACT_DATA_TABLE`: creates and organizes notes in Notion via Notion MCP (and optional Composio).

---

## APIs

All API routes are under `/api` unless noted. Requests that are user-scoped require the **`X-User-Guest-ID`** header (UUID).

### Tasks (`/api/tasks`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| **POST** | `/api/tasks` | **Initiate task.** Accepts `urls`, `selected_text`, `user_context`, optional `task_type`. Runs context processing (URLs or text), intent/task identification, then agent orchestration. Persists contexts and task; returns `task_id`, `task_type`, `context_ids`, `context_result`, `task_identification`, `execution_result`, `execution_status`. |
| **GET** | `/api/tasks` | **List tasks.** Pagination (`page`, `page_size`), filter by `task_type`, `search` in input/output. |
| **GET** | `/api/tasks/{task_id}` | **Get one task** by ID (user-scoped). |

### Contexts (`/api/contexts`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| **GET** | `/api/contexts` | **List contexts.** Pagination, filter by `context_type`, `tags`, `search`. |
| **GET** | `/api/contexts/graph` | **Graph view.** Returns nodes/edges and root nodes for hierarchical visualization. |
| **GET** | `/api/contexts/{context_id}` | **Context detail** including parent/children. |

### Integrations (`/api/integrations`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| **GET** | `/api/integrations/capabilities` | **List supported integrations** (e.g. Notion, Excel) and whether they require an API key. |
| **POST** | `/api/integrations/tokens` | **Upsert integration token** for the user (`integration_tool`, optional `api_key`, `integration_metadata`). |
| **GET** | `/api/integrations/tokens` | **List user’s integration tokens** (active only). |
| **PATCH** | `/api/integrations/tokens/{token_id}` | **Update** `integration_metadata` for a token. |
| **DELETE** | `/api/integrations/tokens/{integration_tool}` | **Soft-delete** token for that integration. |

### Files (`/api/files`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| **GET** | `/api/files/excel/{file_path:path}` | **Download Excel file** by path under the app’s Excel storage (user-scoped by header). |

### Health

- **GET** `/health` — Returns `{"status": "healthy"}`.

---

## Database Architecture

- **Engine:** Async PostgreSQL via **SQLAlchemy** (`asyncpg`), configured with `app/db/session.py` (async engine, session factory, `get_async_session` for FastAPI).
- **Migrations:** **Alembic** under `alembic/`; schema changes in `alembic/versions/`.

### Main Tables

| Table | Purpose |
|-------|--------|
| **user_contexts** | Stored context per user: `context_id` (PK), `raw_content`, `context_tags`, `user_defined_context`, `embedding` (pgvector 1536), `url`, `context_type` (IMAGE/TEXT/VIDEO), `user_guest_id`, `timestamp`, `parent_topic` (self-FK for hierarchy). |
| **user_tasks** | Per-user tasks: `task_id` (PK), `task_type` (enum), `input`/`output` (JSONB), `user_guest_id`, `user_contexts` (array of UUIDs), `timestamp`, `execution_status`. |
| **user_integration_tokens** | Per-user integration credentials: `id` (PK), `user_guest_id`, `integration_tool`, `api_key`, `integration_metadata` (JSONB), `is_deleted`, `created_at`/`updated_at`. Unique on `(user_guest_id, integration_tool)`. |

### Features

- **pgvector** for `user_contexts.embedding` (when extension is available) for similarity search.
- **Enums:** `TaskType`, `ContextType`, `ExecutionStatus` (where used).
- **Soft delete:** Integration tokens use `is_deleted` instead of hard delete.

### Repositories

- **UserContextRepository** — Create/get contexts, list by user, optional parent-topic resolution and embedding.
- **UserTaskRepository** — Create/list/get tasks by user.
- **UserIntegrationTokenRepository** — Upsert, list by user, update metadata, soft-delete.

---

## Opik Integration

[Opik](https://opik.dev) is used for **observability** (prompts and traces). It is **optional** and does not affect core logic when disabled or misconfigured.

### Configuration

- **`OPIK_ENABLED`** — Set to `"true"` to enable (default `"false"`).
- **`OPIK_API_KEY`** — Optional API key for Opik backend.
- **`OPIK_WORKSPACE`** — Optional workspace.
- **`OPIK_URL_OVERRIDE`** / **`OPIK_BASE_URL`** — Override Opik API URL (e.g. self-hosted).

Configured at **startup** in `app/main.py`: `opik.configure(use_local=False, automatic_approvals=True, ...)`.

### Usage in Code

- **`app/utils/opik_wrapper.store_prompt()`** — Best-effort store of a prompt (name, prompt text, metadata). No-op if Opik is disabled or missing; never raises into app code.
- **`@opik.track`** — Decorator used on:
  - **ReasoningEngine** (`reason()`, and any other tracked methods)
  - **TaskIdentificationService**
  - **SemanticKnowledgeService**
  - **DataExtractionAgent** (e.g. `execute()`)

So the agentic core (reasoning, task identification, semantic knowledge, and key agents) is instrumented for traces and prompt logging when Opik is enabled.

---

## Quick Start

1. **Environment** — Copy `.env.example` to `.env`, set `DATABASE_URL` (e.g. `postgresql+asyncpg://...`), `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and optionally Notion/Composio/Opik keys.
2. **Database** — Install pgvector in PostgreSQL, then run migrations:  
   `alembic upgrade head`
3. **Run** — From project root:  
   `uv run uvicorn app.main:app --reload`  
   (or use the `main.py` entrypoint if configured.)

Required header for user-scoped endpoints: **`X-User-Guest-ID: <uuid>`**.
