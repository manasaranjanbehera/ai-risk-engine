# AI Risk Engine — Folder and File Structure

This document describes the current folder and file layout of the **ai_risk_engine** project (excluding `.git`, `__pycache__`, and `venv/`). Use it as a quick reference for where code and assets live.

**Last updated:** February 2026 (post–architect polish: archive, architecture doc, pyproject.toml canonical)

---

## Phase 8 Scalability & distributed deployment (summary)

Scalability layer is dependency-injected; no FastAPI imports; thread- and async-safe.

- **`app/scalability/distributed_lock.py`** — `DistributedLock`: Redis SETNX + TTL, unique token per acquire, atomic release via compare-and-delete; prevents duplicate workflow execution across nodes.
- **`app/scalability/rate_limiter.py`** — `TenantRateLimiter`: per-tenant sliding window; `InMemoryRateLimitBackend` for tests; optional metrics callback.
- **`app/scalability/circuit_breaker.py`** — `CircuitBreaker`: CLOSED → OPEN (failure threshold) → HALF_OPEN (recovery timeout); `call(func)` wraps async calls; metrics tracking.
- **`app/scalability/bulkhead.py`** — `BulkheadExecutor`: bounded queue + semaphore; max concurrent and max queued; queue overflow raises.
- **`app/scalability/autoscaling_policy.py`** — `AutoScalingPolicy.evaluate(MetricsSnapshot)` → `ScalingDecision` (SCALE_UP, SCALE_DOWN, NO_ACTION); CPU, latency, failure rate, queue depth; deterministic.
- **`app/scalability/workload_partitioning.py`** — `WorkloadPartitioner.get_partition(tenant_id)`: consistent hashing, stable partition index.
- **`app/scalability/health_monitor.py`** — `HealthMonitor.system_health()`: aggregates DB, Redis, RabbitMQ, workflow backlog, circuit breaker states, node latency; all backends injected.

**Load tests:** `tests/load/test_load_workflow.py`, `tests/load/test_load_api.py` — concurrent workflow and API calls; multi-tenant; no cross-tenant leakage; bulkhead/rate limiter/partitioning.

**Chaos tests:** `tests/chaos/test_chaos_workflow_failures.py`, `test_chaos_messaging_failures.py`, `test_chaos_redis_failures.py`, `test_chaos_partial_node_failure.py` — workflow/messaging/Redis/circuit-breaker failure scenarios; graceful degradation; audit and idempotency preserved.

---

## Phase 7 Observability & production hardening (summary)

Observability is in-memory and simulated (no real Prometheus/OTLP/SaaS). All services are dependency-injected; workflows optionally accept metrics, tracing, cost, failure classifier, Langfuse client, and evaluation service.

- **`app/observability/metrics.py`** — `MetricsCollector`: counters (request_count by tenant, workflow_execution_count, failure_count by category, approval_required_count, model_usage_count, prompt_usage_count); histograms (node_execution_latency, request_latency); thread-safe; `increment`, `observe_latency`, `export_metrics`.
- **`app/observability/tracing.py`** — `TracingService`: OpenTelemetry-style spans; trace ID propagation; span hierarchy (workflow → nodes); latency and metadata (tenant_id, correlation_id, model_version, prompt_version); in-memory exporter; async `start_span` context manager.
- **`app/observability/langfuse_client.py`** — Simulated Langfuse: `log_generation` (event_id, tenant_id, prompt/model version, tokens, cost, latency); integrates with `CostTracker` and `MetricsCollector`; no external calls.
- **`app/observability/evaluation.py`** — `EvaluationService.evaluate_decision`: deterministic confidence, policy alignment, guardrail, and overall quality scores; stores result in workflow state; emits audit event.
- **`app/observability/cost_tracker.py`** — `CostTracker`: cost per request, per tenant, per model version; cumulative; deterministic (e.g. token_count × rate); `add_cost`, `get_tenant_cost`, `add_cost_from_tokens`.
- **`app/observability/failure_classifier.py`** — `FailureClassifier.classify(exception)` → `FailureCategory` (VALIDATION_ERROR, POLICY_VIOLATION, HIGH_RISK, WORKFLOW_ERROR, INFRA_ERROR, UNEXPECTED_ERROR); maps domain/application/governance/security exceptions; unknown → UNEXPECTED_ERROR.

**Workflow integration:** `RiskWorkflow` and `ComplianceWorkflow` accept optional `metrics_collector`, `tracing_service`, `cost_tracker`, `failure_classifier`, `langfuse_client`, `evaluation_service`. When provided: request_count and workflow_execution_count incremented; per-node spans and latency; model/prompt usage counts; approval_required_count when decision escalates; request_latency; cost recorded; Langfuse generation log; evaluation result stored in state; on exception, failure classified and failure_count incremented.

**State:** `RiskState` and `ComplianceState` include optional `evaluation_result` (dict) for quality scores.

Tests: `tests/unit/observability/` (metrics, tracing, Langfuse, evaluation, cost tracker, failure classifier, workflow integration).

---

## Phase 6 AI workflows (summary)

LangGraph-style deterministic pipelines; no FastAPI in workflow layer; all dependencies injected.

- **`app/workflows/langgraph/state_models.py`** — `RiskState`, `ComplianceState` (Pydantic); immutable transitions via `transition()`; fully serializable; version metadata (model_version, prompt_version), audit_trail.
- **`app/workflows/langgraph/nodes/retrieval.py`** — `retrieve_context(state)` — simulated vector retrieval; audit "context_retrieved".
- **`app/workflows/langgraph/nodes/policy_validation.py`** — `validate_policy(state)` — rule-based PASS/FAIL; audit.
- **`app/workflows/langgraph/nodes/risk_scoring.py`** — `score_risk(state)` — deterministic score; audit.
- **`app/workflows/langgraph/nodes/guardrails.py`** — `apply_guardrails(state)` — threshold/blocked patterns; audit.
- **`app/workflows/langgraph/nodes/decision.py`** — `make_decision(state)` — APPROVED / REQUIRE_APPROVAL; audit "decision_made".
- **`app/workflows/langgraph/nodes/compliance_nodes.py`** — Compliance variants + `make_compliance_decision` (regulatory flags, approval_required).
- **`app/workflows/langgraph/risk_workflow.py`** — `RiskWorkflow.run(state)` — retrieval → policy → scoring → guardrails → decision; idempotent via state store; model/prompt version from registries.
- **`app/workflows/langgraph/compliance_workflow.py`** — `ComplianceWorkflow.run(state)` — same pipeline with compliance gating; low regulatory flags → auto-approve; else escalate.
- **`app/workflows/langgraph/workflow_state_store.py`** — `WorkflowStateStore`, `ComplianceStateStore` protocols; `RedisWorkflowStateStore` (key `workflow:{event_id}`) for idempotency.

Tests: `tests/unit/workflows/` (state, nodes, risk/compliance workflow, idempotency, failures).

---

## Phase 5 governance & security (summary)

Governance and security layers are domain-style: no FastAPI, no HTTP, all dependencies injected.

- **`app/governance/audit_models.py`** — Immutable `AuditRecord` (who, what, when UTC, why, correlation_id).
- **`app/governance/audit_repository.py`** — `AuditRepository` protocol (save).
- **`app/governance/audit_logger.py`** — `AuditLogger.log_action(...)`; writes structured immutable records via repository.
- **`app/governance/model_registry.py`** — `ModelRegistry`: register_model, approve_model, reject_model, get_model, get_approved_model; status PENDING/APPROVED/REJECTED; approval emits audit; cannot deploy unapproved.
- **`app/governance/prompt_registry.py`** — `PromptRegistry`: register_prompt, update_prompt, get_prompt; versioned, change_reason, author; immutable previous versions; audit every change.
- **`app/governance/approval_workflow.py`** — `ApprovalWorkflow`: request_approval, approve, reject; RBAC (only APPROVER/ADMIN); audit trail; status transitions enforced.
- **`app/governance/exceptions.py`** — `GovernanceError`, `ModelNotApprovedError`, `InvalidModelStateError`, `InvalidWorkflowStateError`.
- **`app/security/rbac.py`** — `Role` (ADMIN, ANALYST, APPROVER, VIEWER), `RBACService.check_permission(role, action)`; raises `AuthorizationError` if denied.
- **`app/security/tenant_context.py`** — `TenantContext.validate_access(resource_tenant, request_tenant)`; raises `TenantIsolationError` on mismatch.
- **`app/security/encryption.py`** — `EncryptionService(key)`; AES (Fernet); encrypt/decrypt; fails if key missing; no global state.
- **`app/security/exceptions.py`** — `SecurityError`, `AuthorizationError`, `TenantIsolationError`, `EncryptionError`.

Tests: `tests/unit/governance/`, `tests/unit/security/`.

---

## Phase 4 application layer (summary)

The application layer is the **transaction boundary**: orchestration only, no HTTP/FastAPI, all dependencies injected.

- **`app/application/event_service.py`** — Single entry point `create_event(event, tenant_id, idempotency_key, correlation_id)`; flow: idempotency → persist → publish (RabbitMQ) → workflow trigger → audit log → cache idempotency → return `EventResponse`. Also `get_event(tenant_id, event_id)`.
- **`app/application/event_repository.py`** — `EventRepository` protocol (`save`, `get`) and `PersistedEvent` dataclass.
- **`app/application/exceptions.py`** — `ApplicationError`, `IdempotencyConflictError`, `MessagingFailureError` (do not reuse domain exceptions).
- **`app/workflows/interface.py`** — `WorkflowTrigger` protocol (`async def start(event_id, tenant_id)`).
- **`app/workflows/dummy_workflow.py`** — `DummyWorkflowTrigger` placeholder (logs only).
- **`app/infrastructure/cache/event_repository_redis.py`** — `RedisEventRepository` implements event persistence (Redis, 7-day TTL).

Domain: `EventStatus.RECEIVED` added; validators include RECEIVED in transitions.

---

## Phase 2 domain layer (summary)

The domain package (`app/domain/`) is self-contained and free of infrastructure:

- **`exceptions.py`** — Base `DomainError` and specific errors for validation, status transitions, tenant, risk threshold, and metadata.
- **`models/event.py`** — `EventStatus` enum (received → created → validated → processing → approved/rejected/failed), allowed transitions, `BaseEvent` with `transition_to()`, and entity types `RiskEvent`, `ComplianceEvent`.
- **`schemas/event.py`** — Pydantic request schemas (`RiskEventCreateRequest`, `ComplianceEventCreateRequest`) and `EventResponse`; validators for tenant_id, risk_score 0–100, JSON-serializable metadata, version.
- **`validators/event_validator.py`** — Pure functions that enforce domain rules and raise domain exceptions; used for both API request validation and entity validation.

Import the public API from `app.domain` (see `app/domain/__init__.py` for `__all__`).

---

## Complete directory tree

```
ai_risk_engine/
├── .env                    # Local env vars (not committed)
├── .env.example            # Template for .env; copy to .env and fill in
├── .gitignore
├── README.md
├── pyproject.toml          # Canonical dependency definition; pytest config in [tool.pytest.ini_options]
├── docker-compose.yml      # Local services (Postgres, RabbitMQ, Redis)
│
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI app entrypoint, middleware, router registration
│   ├── migrations/         # SQL migrations (001_initial_schema.sql = full schema + events table)
│   │
│   ├── core/               # Request-scoped context (e.g. correlation_id, tenant_id)
│   │   ├── __init__.py
│   │   └── context.py
│   │
│   ├── application/
│   │   ├── __init__.py
│   │   ├── event_repository.py   # EventRepository protocol, PersistedEvent
│   │   ├── event_service.py      # create_event, get_event (transaction boundary)
│   │   └── exceptions.py         # ApplicationError, IdempotencyConflictError, MessagingFailureError
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py       # get_event_service, get_redis_client, get_publisher, get_correlation_id
│   │   ├── middleware.py
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── health.py         # Health check (mounted in main)
│   │       ├── events.py        # POST/GET events (idempotent create_event)
│   │       ├── risk.py          # POST /risk (uses create_event)
│   │       ├── compliance.py    # POST /compliance (uses create_event)
│   │       └── tenant.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── logging.py      # JSON logging, log level from settings
│   │   └── settings.py     # Pydantic settings (env, .env)
│   │
│   ├── domain/
│   │   ├── __init__.py     # Re-exports models, schemas, validators, exceptions
│   │   ├── exceptions.py   # Domain errors (DomainError, DomainValidationError, etc.)
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── event.py    # EventStatus, BaseEvent, RiskEvent, ComplianceEvent; status transitions
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── event.py    # RiskEventCreateRequest, ComplianceEventCreateRequest, EventResponse
│   │   ├── validators/
│   │   │   ├── __init__.py
│   │   │   └── event_validator.py  # Tenant, risk score, metadata, status transition validators
│   │   ├── policies/       # (placeholder)
│   │   └── services/       # (placeholder)
│   │
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── repository.py
│   │   │   └── session.py
│   │   ├── messaging/
│   │   │   ├── __init__.py
│   │   │   └── rabbitmq_publisher.py
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   ├── redis_client.py           # Redis client (idempotency, cache)
│   │   │   └── event_repository_redis.py  # RedisEventRepository (event store)
│   │   ├── llm/            # (placeholder)
│   │   ├── tools/          # (placeholder)
│   │   └── vectorstore/    # (placeholder)
│   │
│   ├── governance/         # Phase 5: audit, model/prompt registry, approval workflow
│   │   ├── __init__.py
│   │   ├── audit_models.py      # AuditRecord (immutable)
│   │   ├── audit_repository.py   # AuditRepository protocol
│   │   ├── audit_logger.py      # AuditLogger
│   │   ├── model_registry.py    # ModelRegistry, ModelStatus, ModelRecord
│   │   ├── prompt_registry.py   # PromptRegistry, PromptRecord
│   │   ├── approval_workflow.py  # ApprovalWorkflow, ApprovalStatus
│   │   └── exceptions.py        # GovernanceError, ModelNotApprovedError, etc.
│   ├── observability/      # Phase 7: metrics, tracing, cost, failure classification, evaluation, Langfuse
│   │   ├── __init__.py
│   │   ├── metrics.py           # MetricsCollector (Prometheus-style, thread-safe)
│   │   ├── tracing.py           # TracingService (OpenTelemetry-style, in-memory)
│   │   ├── langfuse_client.py  # Simulated Langfuse (log_generation, cost, metrics)
│   │   ├── evaluation.py       # EvaluationService (quality scoring, audit)
│   │   ├── cost_tracker.py     # CostTracker (per tenant/model/request)
│   │   └── failure_classifier.py  # FailureClassifier (exception → FailureCategory)
│   ├── scalability/       # Phase 8: distributed lock, rate limiter, circuit breaker, bulkhead, autoscaling, partitioning, health
│   │   ├── __init__.py
│   │   ├── distributed_lock.py
│   │   ├── rate_limiter.py
│   │   ├── circuit_breaker.py
│   │   ├── bulkhead.py
│   │   ├── autoscaling_policy.py
│   │   ├── workload_partitioning.py
│   │   └── health_monitor.py
│   ├── security/           # Phase 5: RBAC, tenant isolation, encryption
│   │   ├── __init__.py
│   │   ├── rbac.py              # Role, RBACService
│   │   ├── tenant_context.py    # TenantContext
│   │   ├── encryption.py        # EncryptionService (AES/Fernet)
│   │   └── exceptions.py        # AuthorizationError, TenantIsolationError, etc.
│   └── workflows/
│       ├── __init__.py
│       ├── interface.py    # WorkflowTrigger protocol
│       ├── dummy_workflow.py  # DummyWorkflowTrigger (placeholder)
│       └── langgraph/      # Phase 6: AI workflows
│           ├── __init__.py
│           ├── state_models.py    # RiskState, ComplianceState
│           ├── workflow_state_store.py  # WorkflowStateStore, RedisWorkflowStateStore
│           ├── risk_workflow.py   # RiskWorkflow.run()
│           ├── compliance_workflow.py  # ComplianceWorkflow.run()
│           └── nodes/
│               ├── __init__.py
│               ├── retrieval.py
│               ├── policy_validation.py
│               ├── risk_scoring.py
│               ├── guardrails.py
│               ├── decision.py
│               └── compliance_nodes.py
│
├── docker/                 # (empty — Dockerfiles go here)
├── migrations/             # (optional empty dir; canonical SQL migrations in app/migrations/)
│
├── tests/
│   ├── unit/
│   │   ├── application/    # EventService unit tests (Phase 4)
│   │   │   └── test_event_service.py
│   │   ├── observability/ # Phase 7: metrics, tracing, cost, failure, evaluation, Langfuse, workflow integration
│   │   │   ├── test_metrics.py
│   │   │   ├── test_tracing.py
│   │   │   ├── test_langfuse_client.py
│   │   │   ├── test_evaluation.py
│   │   │   ├── test_cost_tracker.py
│   │   │   ├── test_failure_classifier.py
│   │   │   └── test_workflow_integration.py
│   │   ├── workflows/      # Phase 6: state, nodes, risk/compliance workflow, failures
│   │   │   ├── conftest.py
│   │   │   ├── test_state_models.py
│   │   │   ├── test_nodes.py
│   │   │   ├── test_risk_workflow.py
│   │   │   ├── test_compliance_workflow.py
│   │   │   ├── test_workflow_failures.py
│   │   │   └── test_workflow_state_store.py
│   │   ├── governance/     # Phase 5: audit, model registry, prompt registry, approval workflow
│   │   │   ├── test_audit_logger.py
│   │   │   ├── test_model_registry.py
│   │   │   ├── test_prompt_registry.py
│   │   │   └── test_approval_workflow.py
│   │   ├── security/       # Phase 5: RBAC, tenant context, encryption
│   │   │   ├── test_rbac.py
│   │   │   ├── test_tenant_context.py
│   │   │   └── test_encryption.py
│   │   └── api/
│   ├── integration/
│   ├── load/              # Phase 8: test_load_workflow.py, test_load_api.py
│   ├── chaos/            # Phase 8: test_chaos_workflow_failures.py, test_chaos_messaging_failures.py, test_chaos_redis_failures.py, test_chaos_partial_node_failure.py
│   └── workflow/
│
└── docs/
    ├── PROJECT_STRUCTURE.md           # Guide to project layout and conventions
    ├── FOLDER_AND_FILE_STRUCTURE.md   # This file — full tree reference
    ├── TESTING_AND_LOCAL_SETUP.md     # How to run and test locally (venv → health)
    ├── architecture/                  # Design and governance framework
    │   └── ai-system-design-governance-framework.md
    ├── development-phase/             # Development history (phase summaries)
    │   └── development-history/
    │       ├── PHASE_5_GOVERNANCE_AND_SECURITY.md
    │       ├── PHASE_6_AI_WORKFLOWS.md
    │       ├── PHASE_7_OBSERVABILITY_AND_PRODUCTION_HARDENING.md
    │       └── phase8-scalability-and-distributed-deployment.md
    └── archive/                       # Internal validation and cleanup reports (historical)
        ├── repo_cleanup_phase1.md
        ├── final_architect_cleanup_summary.md
        ├── test_quality_report.md
        ├── database_governance_report.md
        ├── PROJECT_REVIEW_AND_NEXT_PHASE.md
        └── PROJECT_REVIEW_AND_IMPROVEMENTS.md
```

---

## File inventory by area

### Root

| File | Description |
|------|-------------|
| `.env.example` | Template for required/optional env vars; copy to `.env` (includes JWT_SECRET, DATABASE_URL, REDIS_URL, RABBITMQ_URL) |
| `.gitignore` | Git ignore rules (venv, .env, IDE, etc.) |
| `README.md` | Project overview and quick start |
| `pyproject.toml` | Canonical dependency definition and pytest config (`[tool.pytest.ini_options]`); install with `pip install -e .` |
| `app/migrations/001_initial_schema.sql` | Initial schema (extensions, core tables, events table); run to set up DB and enable DbEventRepository. |
| `docker-compose.yml` | Local services: Postgres, RabbitMQ, Redis |

### Application (`app/`)

| Path | Description |
|------|-------------|
| `app/main.py` | FastAPI app, context middleware (correlation/tenant headers), router includes |
| `app/core/context.py` | Context vars: `correlation_id_ctx`, `tenant_id_ctx` |
| `app/application/event_service.py` | Event application service: `create_event` (idempotency → persist → publish → workflow → audit → cache), `get_event`; transaction boundary, no HTTP |
| `app/application/event_repository.py` | `EventRepository` protocol (save, get), `PersistedEvent` dataclass |
| `app/application/exceptions.py` | Application errors: `ApplicationError`, `IdempotencyConflictError`, `MessagingFailureError` |
| `app/api/dependencies.py` | DI: `get_event_service`, `get_redis_client`, `get_publisher`, `get_tenant_id`, `get_correlation_id` |
| `app/api/routers/health.py` | Health check: `GET /health` (status, environment, version) — mounted in main |
| `app/api/routers/events.py` | Events API: POST/GET events; builds domain events, calls `create_event` |
| `app/api/routers/risk.py` | POST /risk — builds RiskEvent, calls `create_event` |
| `app/api/routers/compliance.py` | POST /compliance — builds ComplianceEvent, calls `create_event` |
| `app/infrastructure/cache/redis_client.py` | Redis async client (idempotency keys, cache) |
| `app/infrastructure/cache/event_repository_redis.py` | `RedisEventRepository`: persist events to Redis (status RECEIVED), 7-day TTL |
| `app/config/settings.py` | Main settings (Pydantic BaseSettings, `.env`) |
| `app/config/logging.py` | Logging config (JSON formatter, correlation/tenant in logs) |
| `app/domain/exceptions.py` | Domain errors: `DomainError`, `DomainValidationError`, `InvalidStatusTransitionError`, `InvalidTenantError`, `RiskThresholdViolationError`, `InvalidMetadataError` |
| `app/domain/models/event.py` | Event domain model: `EventStatus` (incl. RECEIVED), `BaseEvent` (with `transition_to()`), `RiskEvent`, `ComplianceEvent` |
| `app/domain/schemas/event.py` | Event request/response schemas: `RiskEventCreateRequest`, `ComplianceEventCreateRequest`, `EventResponse` (Pydantic; metadata JSON-serializable, risk 0–100) |
| `app/domain/validators/event_validator.py` | Pure validators: tenant_id, risk_score, metadata, status transition; request and entity validation |
| `app/infrastructure/database/models.py` | Database ORM models |
| `app/infrastructure/database/repository.py` | Database repository (CRUD, queries; e.g. AsyncRepository) |
| `app/infrastructure/database/session.py` | Database session factory and dependency |
| `app/infrastructure/messaging/rabbitmq_publisher.py` | RabbitMQ message publisher |
| `app/workflows/interface.py` | `WorkflowTrigger` protocol: `async def start(event_id, tenant_id)` |
| `app/workflows/dummy_workflow.py` | `DummyWorkflowTrigger` — placeholder implementation (logs only) |
| `app/workflows/langgraph/state_models.py` | `RiskState`, `ComplianceState` (Pydantic); immutable transitions; serializable |
| `app/workflows/langgraph/workflow_state_store.py` | `WorkflowStateStore`, `ComplianceStateStore`; `RedisWorkflowStateStore` (idempotency) |
| `app/workflows/langgraph/risk_workflow.py` | `RiskWorkflow.run(state)` — 5-node pipeline; idempotent; model/prompt version |
| `app/workflows/langgraph/compliance_workflow.py` | `ComplianceWorkflow.run(state)` — compliance gating; regulatory flags |
| `app/workflows/langgraph/nodes/*.py` | retrieval, policy_validation, risk_scoring, guardrails, decision, compliance_nodes |
| `app/governance/audit_models.py` | Immutable `AuditRecord` (who, what, when UTC, why, correlation_id) |
| `app/governance/audit_repository.py` | `AuditRepository` protocol (save) |
| `app/governance/audit_logger.py` | `AuditLogger.log_action` — immutable audit via repository |
| `app/governance/model_registry.py` | `ModelRegistry`, `ModelStatus`, `ModelRecord`; register/approve/reject; no deploy unapproved |
| `app/governance/prompt_registry.py` | `PromptRegistry`, `PromptRecord`; versioned prompts, audit every change |
| `app/governance/approval_workflow.py` | `ApprovalWorkflow`, `ApprovalStatus`; RBAC, audit trail |
| `app/governance/exceptions.py` | `GovernanceError`, `ModelNotApprovedError`, `InvalidModelStateError`, `InvalidWorkflowStateError` |
| `app/security/rbac.py` | `Role` enum, `RBACService.check_permission`; permission matrix |
| `app/security/tenant_context.py` | `TenantContext.validate_access`; strict tenant isolation |
| `app/security/encryption.py` | `EncryptionService` — AES (Fernet), env key, no global state |
| `app/security/exceptions.py` | `SecurityError`, `AuthorizationError`, `TenantIsolationError`, `EncryptionError` |
| `app/observability/metrics.py` | `MetricsCollector`: counters (request/workflow/failure/approval/model/prompt), histograms (latency); thread-safe; export_metrics |
| `app/observability/tracing.py` | `TracingService`: OpenTelemetry-style spans; trace/span hierarchy; in-memory; async start_span |
| `app/observability/langfuse_client.py` | Simulated Langfuse: log_generation; integrates with CostTracker and MetricsCollector |
| `app/observability/evaluation.py` | `EvaluationService.evaluate_decision`: deterministic quality scores; audit |
| `app/observability/cost_tracker.py` | `CostTracker`: per tenant/model/request; add_cost_from_tokens; deterministic rate |
| `app/observability/failure_classifier.py` | `FailureClassifier.classify(exception)` → FailureCategory (VALIDATION_ERROR, etc.) |
| `app/scalability/distributed_lock.py` | `DistributedLock`: Redis SETNX + TTL; acquire/release; safe in concurrent async |
| `app/scalability/rate_limiter.py` | `TenantRateLimiter`: per-tenant sliding window; `InMemoryRateLimitBackend` |
| `app/scalability/circuit_breaker.py` | `CircuitBreaker`: CLOSED/OPEN/HALF_OPEN; call(func); failure threshold, recovery timeout |
| `app/scalability/bulkhead.py` | `BulkheadExecutor`: max concurrent + queue overflow; submit(task) |
| `app/scalability/autoscaling_policy.py` | `AutoScalingPolicy.evaluate(metrics)` → ScalingDecision (SCALE_UP/SCALE_DOWN/NO_ACTION) |
| `app/scalability/workload_partitioning.py` | `WorkloadPartitioner.get_partition(tenant_id)`: consistent hashing |
| `app/scalability/health_monitor.py` | `HealthMonitor.system_health()`: DB, Redis, RabbitMQ, backlog, circuit states |

### Tests (`tests/`)

| Path | Description |
|------|-------------|
| `tests/unit/application/test_event_service.py` | EventService unit tests: happy path, idempotent replay, messaging/repository/workflow failure (Phase 4) |
| `tests/unit/observability/*.py` | Phase 7: metrics, tracing, cost, failure classifier, evaluation, Langfuse, workflow integration |
| `tests/unit/workflows/*.py` | Phase 6: state, nodes, risk/compliance workflow, idempotency, failures, state store |
| `tests/unit/governance/test_audit_logger.py` | Audit immutability, audit fields completeness |
| `tests/unit/governance/test_model_registry.py` | Model approve/reject, cannot approve twice, cannot deploy unapproved |
| `tests/unit/governance/test_prompt_registry.py` | Prompt version increments, audit every change |
| `tests/unit/governance/test_approval_workflow.py` | RBAC enforcement, status transitions |
| `tests/unit/security/test_rbac.py` | RBAC permission matrix (all roles × actions) |
| `tests/unit/security/test_tenant_context.py` | Tenant isolation, cross-tenant raises |
| `tests/unit/security/test_encryption.py` | Encryption round-trip, wrong key fails, key missing fails |
| `tests/unit/api/conftest.py` | API test fixtures: FakeRedis, mock_publisher, app_with_overrides |
| `tests/unit/api/test_events.py` | Events API: idempotency, validation, GET by id |
| `tests/unit/api/test_risk.py` | POST /risk: valid payload, validation failure, idempotency |
| `tests/unit/api/test_compliance.py` | POST /compliance: valid payload, validation, idempotency |
| `tests/unit/scalability/*.py` | Phase 8: distributed lock, rate limiter, circuit breaker, bulkhead, autoscaling, partitioning, health |
| `tests/load/test_load_workflow.py` | Phase 8: concurrent workflow, multi-tenant, no cross-tenant leakage; bulkhead, rate limiter, partitioning |
| `tests/load/test_load_api.py` | Phase 8: health throughput, multi-tenant no leakage |
| `tests/chaos/test_chaos_workflow_failures.py` | Phase 8: workflow failure classified; failure classifier mapping |
| `tests/chaos/test_chaos_messaging_failures.py` | Phase 8: messaging failure raises MessagingFailureError; idempotency not cached |
| `tests/chaos/test_chaos_redis_failures.py` | Phase 8: Redis outage; lock/rate limiter fail gracefully |
| `tests/chaos/test_chaos_partial_node_failure.py` | Phase 8: circuit breaker OPEN/HALF_OPEN behavior |

### Documentation (`docs/`)

| Path | Description |
|------|-------------|
| `docs/PROJECT_STRUCTURE.md` | Project structure guide and conventions |
| `docs/FOLDER_AND_FILE_STRUCTURE.md` | This file — full folder and file structure |
| `docs/TESTING_AND_LOCAL_SETUP.md` | Local setup and testing (venv, run app, health check) |
| `docs/architecture/ai-system-design-governance-framework.md` | AI system design and governance framework |
| `docs/development-phase/development-history/` | Phase 5–8 development summaries (governance, workflows, observability, scalability) |
| `docs/archive/` | Archived internal reports (cleanup, quality, governance reviews); historical only |

---

## Related docs

- **Project layout and conventions:** [docs/PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)
- **Local setup and testing:** [docs/TESTING_AND_LOCAL_SETUP.md](./TESTING_AND_LOCAL_SETUP.md)
- **Development phase history:** [docs/development-phase/development-history/](./development-phase/development-history/)
- **Architecture and governance:** [docs/architecture/ai-system-design-governance-framework.md](./architecture/ai-system-design-governance-framework.md)

To regenerate a full schema dump for reference: `docker exec -t compliance_postgres pg_dump -U compliance_user -d compliance_db --schema-only > schema_dump.sql` (not committed; app/migrations/ is the source of truth).
