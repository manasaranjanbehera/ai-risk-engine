# Project structure guide

This document explains how this project is organized and how you can set up a similar, scalable folder structure for a new project. For a **complete folder and file tree** of the current codebase, see [FOLDER_AND_FILE_STRUCTURE.md](./FOLDER_AND_FILE_STRUCTURE.md). For **running and testing the app locally** (venv, dependencies, health check), see [TESTING_AND_LOCAL_SETUP.md](./TESTING_AND_LOCAL_SETUP.md). We’ve kept the tone friendly and the steps simple so that someone new to the codebase (or to structuring projects) can follow along easily.

---

## What this project looks like (folder scan summary)

Here’s a high-level overview of the main folders and what they’re for:

| Folder | Purpose |
|--------|--------|
| **`app/`** | Main application code. Everything that runs lives under here. |
| **`app/application/`** | Application layer (transaction boundary): `EventService` with single entry point `create_event` (idempotency → persist → publish → workflow → audit → cache); `EventRepository` protocol and `PersistedEvent`; application exceptions. No HTTP/FastAPI; all dependencies injected. |
| **`app/core/`** | Request-scoped context (e.g. correlation ID, tenant ID) used by middleware and logging. |
| **`app/api/`** | HTTP layer: FastAPI routers (e.g. health, events), middleware, and shared dependencies. |
| **`app/config/`** | Settings, logging, and environment-based configuration. |
| **`app/domain/`** | Core business logic: **exceptions** (domain errors), **models** (e.g. EventStatus, BaseEvent, RiskEvent, ComplianceEvent with status lifecycle), **schemas** (request/response Pydantic models), **validators** (pure validation functions), policies, and domain services. No infrastructure or DB — easy to test and change. |
| **`app/workflows/`** | Workflow trigger interface (`WorkflowTrigger` protocol), placeholder (`DummyWorkflowTrigger`), and **Phase 6** LangGraph AI workflows: `langgraph/` (state models, nodes, risk/compliance workflows, idempotency store). Deterministic pipelines with audit and model/prompt version tracking. |
| **`app/infrastructure/`** | External systems: database (session, repository, ORM models), Redis cache (`redis_client.py`, `event_repository_redis.py` for event store), RabbitMQ messaging, and placeholders for LLM, vector store, and tools. Keeps “plumbing” in one place. |
| **`app/security/`** | **Phase 5:** Security: `RBACService` (Role enum, permission matrix), `TenantContext` (strict tenant isolation), `EncryptionService` (AES/Fernet). No FastAPI; all components dependency-injected. |
| **`app/governance/`** | **Phase 5:** Governance: `AuditLogger` (immutable audit records via `AuditRepository`), `ModelRegistry` (version + approval; no deploy unapproved), `PromptRegistry` (versioned, immutable history), `ApprovalWorkflow` (human-in-the-loop, RBAC). No FastAPI. |
| **`app/observability/`** | **Phase 7:** Observability & production hardening: Prometheus-style **metrics** (request/workflow/node latency, tenant usage, failure counts, approval counts); OpenTelemetry-style **tracing** (in-memory, trace/span hierarchy); **cost tracking** (per tenant, per model, deterministic); **failure classification** (VALIDATION_ERROR, POLICY_VIOLATION, HIGH_RISK, WORKFLOW_ERROR, INFRA_ERROR, UNEXPECTED_ERROR); **evaluation** (deterministic quality scores, audit); simulated **Langfuse** client (LLM trace logging, no external calls). All dependency-injected; workflows optionally record latency, cost, and metrics. |
| **`app/scalability/`** | **Phase 8:** Scalability & distributed deployment: **DistributedLock** (Redis SETNX, TTL, safe release); **TenantRateLimiter** (per-tenant sliding window, metrics); **CircuitBreaker** (CLOSED/OPEN/HALF_OPEN); **BulkheadExecutor** (max concurrent + queue overflow); **AutoScalingPolicy** (deterministic SCALE_UP/SCALE_DOWN/NO_ACTION); **WorkloadPartitioner** (consistent hashing); **HealthMonitor** (DB, Redis, RabbitMQ, backlog, circuit states). No FastAPI; thread- and async-safe; dependency-injected. |
| **`tests/`** | All tests. Subfolders: `unit/`, `integration/`, `load/`, `chaos/` so you can run the right kind of tests when needed. |
| **`migrations/`** | Database migrations (e.g. Alembic). Empty until you add your first migration. |
| **`docker/`** | Docker-related files (e.g. Dockerfiles, scripts). Empty until you add them. |
| **`docs/`** | Documentation (like this file). Architecture, testing guide, and development history live here. |

At the root you’ll also see:

- **`pyproject.toml`** – Canonical dependency definition and pytest config; install with `pip install -e .`.
- **`docker-compose.yml`** – For running local services (Postgres, RabbitMQ, Redis).
- **`app/migrations/001_initial_schema.sql`** – Initial DB schema and events table (reference).
- **`README.md`** – Short project overview and how to run it.
- **`.gitignore`** – Files and folders that Git should ignore.

This layout keeps different concerns in separate places so the project can grow without turning into a big, tangled ball of code.

---

## Why this structure is scalable

- **Separate concerns** – Domain logic, API, infrastructure, and workflows live in different packages. You can change one part (e.g. swap the database or add a new API) without digging through the whole app.
- **Clear entrypoint** – `app/main.py` is the application entrypoint. New people know where the app starts.
- **Test-friendly** – Domain and services can be tested without starting the API or real databases. Tests are grouped by type under `tests/`.
- **Room to grow** – Empty (or mostly empty) folders like `migrations/` and `docker/` are placeholders. You fill them when you need migrations or containers.

---

## How to create a new empty project with this structure

If you want to start a **new** project that is empty but scalable from day one, you can do the following.

### 1. Create the project root

```bash
mkdir my_new_project
cd my_new_project
```

### 2. Create the folder structure

Create the same top-level folders as above. You can do it by hand or with a short script. Example (run from the project root):

```bash
mkdir -p app/core app/application app/config app/domain/models app/domain/schemas app/domain/services \
         app/domain/policies app/domain/validators \
         app/api/routers app/infrastructure/database app/infrastructure/llm \
         app/infrastructure/cache app/infrastructure/messaging \
         app/infrastructure/vectorstore app/infrastructure/tools \
         app/workflows app/security app/governance app/observability \
         tests/unit tests/integration tests/load tests/workflow \
         migrations docker scripts docs
```

Adjust names if your project doesn’t need workflows, governance, or observability yet; you can add those folders when you need them.

### 3. Make `app` a Python package

Add an empty `__init__.py` in every folder that should be a package (so Python can import from it). At minimum:

- `app/__init__.py`
- `app/core/__init__.py`
- `app/application/__init__.py`
- `app/config/__init__.py`
- `app/domain/__init__.py`
- `app/domain/models/__init__.py`
- `app/api/__init__.py`
- `app/api/routers/__init__.py`
- …and the same for any other subpackages you created.

You can touch them with:

```bash
touch app/__init__.py app/core/__init__.py app/application/__init__.py app/config/__init__.py \
      app/domain/__init__.py app/domain/models/__init__.py app/api/__init__.py app/api/routers/__init__.py
```

(Repeat for other packages as needed.)

### 4. Add a minimal entrypoint

Create `app/main.py` with a minimal FastAPI app (or whatever framework you use), for example:

```python
# app/main.py
from fastapi import FastAPI

app = FastAPI(title="My New Project")

@app.get("/health")
def health():
    return {"status": "ok"}
```

This gives you a single, clear place where the application starts.

### 5. Add root-level files

- **`pyproject.toml`** – Declare your project dependencies (canonical); install with `pip install -e .`.
- **`README.md`** – Briefly describe the project and how to run it (e.g. `uvicorn app.main:app --reload`).
- **`.gitignore`** – Include at least `__pycache__/`, `.env`, `*.pyc`, and any virtualenv or IDE folders you use.

### 6. Initialize Git and make the first commit

```bash
git init
git add .
git commit -m "Initial commit: scalable project structure"
```

You can then create a branch (e.g. `docs/project-structure` or `main`) and push to GitHub when you’re ready.

---

## Quick reference: where to put what

- **New API route** → `app/api/routers/` (e.g. a new file or router module such as `events.py`).
- **New application service** → `app/application/` (e.g. `event_service.py` — transaction boundary: idempotency, persist, publish, workflow, audit; use `EventRepository` protocol and application exceptions).
- **New business rule or model** → `app/domain/models/` or `app/domain/services/`; schemas in `app/domain/schemas/`, validators in `app/domain/validators/`, domain-specific errors in `app/domain/exceptions.py`.
- **New workflow or pipeline** → `app/workflows/` (implement `WorkflowTrigger` protocol; use `interface.py` for the protocol). For AI pipelines, add nodes and/or workflows under `app/workflows/langgraph/` (state models, nodes, risk_workflow, compliance_workflow).
- **New integration (DB, API client, queue, cache)** → `app/infrastructure/` (e.g. `database/models.py`, `database/repository.py`, `database/session.py`, `messaging/rabbitmq_publisher.py`, `cache/redis_client.py`).
- **New config or env variable** → `app/config/` (e.g. in `settings.py` or a dedicated module).
- **New test** → `tests/unit/`, `tests/integration/`, `tests/load/`, `tests/chaos/`, mirroring the `app/` structure if you like.

---

---

## Pushing to GitHub

When you’re ready to put this project on GitHub:

1. **Create a new repository** on GitHub (via the website or CLI). Don’t initialize it with a README if you already have one locally.

2. **Add the remote** (replace `YOUR_USERNAME` and `YOUR_REPO` with your GitHub username and repo name):
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   ```

3. **Push your branch** (this guide was added on the `docs/project-structure` branch):
   ```bash
   git push -u origin docs/project-structure
   ```

4. **Optionally push `main` as well** so your default branch is on GitHub:
   ```bash
   git checkout main
   git push -u origin main
   ```

After that, you can open a Pull Request from `docs/project-structure` into `main` on GitHub if you’d like, or keep working on either branch.

