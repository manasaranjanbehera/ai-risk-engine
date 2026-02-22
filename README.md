# AI Risk Governance Engine

**Architectural blueprint for AI risk, compliance, and governance in regulated environments.**

---

## 1. Project Vision

The **AI Risk Governance Engine** is a governance-focused platform foundation designed for financial and regulated institutions that need to:

- **Govern** AI usage through model and prompt registries, approval workflows, and audit trails.
- **Assess risk** via deterministic, auditable pipelines (retrieval → policy → scoring → guardrails → decision).
- **Enforce compliance** with regulatory flags, escalation paths, and immutable audit records.
- **Scale** horizontally with distributed locking, per-tenant rate limits, circuit breakers, and workload partitioning.

The architecture assumes high-accountability environments: idempotency, transaction boundaries, failure classification, and tenant isolation are first-class concerns. The design is **enterprise-oriented**—audit-compliant, event-driven, async-first, and observable—without sacrificing clarity or testability.

---

## 2. Architectural Overview

The system follows a **layered, dependency-injected** design. The API layer is the only place that depends on FastAPI; domain, application, workflows, governance, security, observability, and scalability layers are **framework-agnostic** and receive dependencies via constructors.

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                        EXTERNAL CLIENTS                            │
                    └─────────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
    ┌───────────────────────────────────────────────────────────────────────────────────────────┐
    │                              API LAYER (FastAPI)                                             │
    │  Routers: /health, /events, /risk, /compliance, /tenant  │  Middleware: Correlation, Tenant   │
    │  Exception handlers → Domain/Application errors → HTTP 422/503/500                           │
    └───────────────────────────────────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
    ┌───────────────────────────────────────────────────────────────────────────────────────────┐
    │                         APPLICATION LAYER (Transaction Boundary)                           │
    │  EventService: idempotency → persist → publish (RabbitMQ) → workflow trigger → audit → cache  │
    │  Protocols: EventRepository, WorkflowTrigger                                                │
    └───────────────────────────────────────────────────────────────────────────────────────────┘
                    │                    │                    │                    │
                    ▼                    ▼                    ▼                    ▼
    ┌───────────────┐    ┌───────────────────┐    ┌─────────────────┐    ┌─────────────────────┐
    │   DOMAIN      │    │   WORKFLOWS        │    │   GOVERNANCE    │    │   SECURITY          │
    │   Models,     │    │   LangGraph-style  │    │   Audit,        │    │   RBAC,             │
    │   Schemas,    │    │   Risk/Compliance  │    │   Model/Prompt  │    │   TenantContext,    │
    │   Validators, │    │   State store,     │    │   Registry,     │    │   Encryption        │
    │   Exceptions  │    │   Nodes, Idempotent│    │   Approval      │    │                     │
    └───────────────┘    └───────────────────┘    └─────────────────┘    └─────────────────────┘
                    │                    │                    │                    │
                    └────────────────────┴────────────────────┴────────────────────┘
                                                │
                                                ▼
    ┌───────────────────────────────────────────────────────────────────────────────────────────┐
    │                    OBSERVABILITY  │  SCALABILITY                                          │
    │  Metrics, Tracing, Cost, FailureClassifier, Evaluation  │  Lock, RateLimit, CircuitBreaker │
    │  Langfuse (simulated)                                   │  Bulkhead, Partitioning, Health │
    └───────────────────────────────────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
    ┌───────────────────────────────────────────────────────────────────────────────────────────┐
    │                              INFRASTRUCTURE                                                 │
    │  PostgreSQL │ Redis (idempotency, event store, workflow state, lock) │ RabbitMQ (events)   │
    └───────────────────────────────────────────────────────────────────────────────────────────┘
```

**Component interaction (request flow):**

1. **Request** hits a router (e.g. POST `/risk`). Middleware sets `correlation_id` and `tenant_id` in context.
2. **Router** validates the payload against domain schemas, builds a domain event (`RiskEvent` / `ComplianceEvent`), and calls `EventService.create_event(...)` with idempotency key and correlation id.
3. **EventService** (transaction boundary):  
   (a) Checks idempotency in Redis; on hit, returns cached response.  
   (b) Persists event (e.g. Redis or DB) with status `RECEIVED`.  
   (c) Publishes to RabbitMQ (exchange `risk_events`, routing by type).  
   (d) Triggers workflow (e.g. `RiskWorkflow.run(state)`).  
   (e) Audits the action; on success, caches idempotency and returns `EventResponse`.  
   If **messaging** fails, the transaction is not considered successful and idempotency is not cached (retry can re-publish). Workflow failure is logged but does not fail the transaction.
4. **Workflows** (when triggered) load state, run nodes (retrieval → policy → scoring → guardrails → decision), optionally use metrics/tracing/cost/evaluation/failure classification, and persist state for idempotency.
5. **Governance** and **security** are used throughout: audit on every material action, RBAC on approvals, `TenantContext` to enforce tenant isolation on resources.

This design reflects **enterprise-oriented architecture** because: (1) every decision path can be audited and traced; (2) model and prompt usage are versioned and approval-gated; (3) tenant data and rate limits are isolated; (4) idempotency and distributed locking support safe horizontal scaling; (5) failure taxonomy and observability support incident response and compliance reporting.

---

## 3. Layered Design

| Layer | Responsibility | Dependencies |
|-------|-----------------|--------------|
| **API** | HTTP transport, routing, middleware, exception mapping to HTTP codes. | FastAPI; injects application and infra. |
| **Application** | Transaction boundary: orchestration of persist, publish, workflow, audit. No HTTP. | Domain, repositories, publisher, Redis, workflow trigger, audit. |
| **Domain** | Entities, value objects, schemas, validators, domain exceptions. Pure business rules. | None (no infra, no framework). |
| **Workflows** | Deterministic pipelines (LangGraph-style): state, nodes, state store. | Domain; optional observability and governance. |
| **Governance** | Audit (immutable records), model registry, prompt registry, approval workflow. | Protocols (e.g. AuditRepository). |
| **Security** | RBAC, tenant context (isolation), encryption. | No framework. |
| **Observability** | Metrics, tracing, cost, failure classification, evaluation, Langfuse-style logging. | Injected; no global mutable state. |
| **Scalability** | Distributed lock, rate limiter, circuit breaker, bulkhead, partitioning, health aggregation. | Backends injected (e.g. Redis). |
| **Infrastructure** | DB sessions, Redis client, RabbitMQ publisher, event repository implementations. | External systems. |

Dependencies point **inward**: API → Application → Domain; infrastructure and cross-cutting concerns are injected so that domain and application remain testable and portable.

---

## 4. Domain-Driven Design Elements

- **Bounded context:** Risk and compliance events are distinct domain types with explicit status lifecycles (`EventStatus`: RECEIVED → CREATED → VALIDATED → PROCESSING → APPROVED | REJECTED | FAILED) and validated transitions via `BaseEvent.transition_to()`.
- **Entities and value objects:** `RiskEvent`, `ComplianceEvent`; Pydantic schemas for requests/responses; immutable `AuditRecord` in governance.
- **Domain logic in one place:** Validators (`event_validator`) and entity methods enforce rules; domain exceptions (`DomainValidationError`, `InvalidStatusTransitionError`, `InvalidTenantError`, etc.) are raised from the domain layer and mapped to HTTP at the API edge.
- **Application services as orchestrators:** `EventService` does not contain business rules; it coordinates repositories, messaging, workflow trigger, and audit. Workflows encapsulate risk/compliance decision logic in nodes and state.
- **Explicit protocols:** `EventRepository`, `WorkflowTrigger`, `AuditRepository`, `WorkflowStateStore` define contracts; infrastructure implements them (e.g. `RedisEventRepository`, `RedisWorkflowStateStore`, `DummyWorkflowTrigger`).

---

## 5. Multi-Tenant Strategy

- **Tenant identity:** Every request carries a tenant identifier (e.g. via header or context). Middleware sets `tenant_id` in request-scoped context.
- **Isolation:** `TenantContext.validate_access(resource_tenant, request_tenant)` is used before any resource access; mismatch raises `TenantIsolationError`. Event APIs and workflows are keyed by `tenant_id`; idempotency keys are namespaced (`idempotency:{tenant_id}:{key}`).
- **Metering and limiting:** Observability records metrics and cost per `tenant_id`. `TenantRateLimiter` enforces per-tenant request limits (sliding window). `WorkloadPartitioner` assigns tenants to partitions via consistent hashing for stable routing and cache affinity.
- **No cross-tenant leakage:** Load and chaos tests assert that event ownership and metrics remain tenant-scoped under concurrency.

---

## 6. Deployment Architecture (Docker-Based)

**Local / development:** Core dependencies run via Docker Compose:

- **PostgreSQL 15** — Primary relational store; schema applied from `app/migrations/001_initial_schema.sql` (manual run; not auto-applied by Compose).
- **RabbitMQ 3 (with management UI)** — Event publishing; exchange `risk_events`, routing by event type.
- **Redis 7** — Idempotency cache, event store (optional), workflow state store, distributed lock.

The application runs on the host (e.g. `uvicorn app.main:app --reload`) and connects to these services via `DATABASE_URL`, `REDIS_URL`, and `RABBITMQ_URL`. No application image is defined in the current Compose file; the design supports adding an `app` service that builds from a Dockerfile and depends on the three backing services.

**Production deployment pattern:** Stateless API replicas behind a load balancer; shared Redis and RabbitMQ (and optionally PostgreSQL for event store and audit). Distributed lock ensures exactly-one workflow execution per event across replicas. Health checks can call `HealthMonitor.system_health()` for DB, Redis, RabbitMQ, and circuit breaker state to drive readiness.

---

## 7. Database Governance Strategy

The AI Risk Engine uses a **single authoritative SQL bootstrap migration** located at:

- **`app/migrations/001_initial_schema.sql`**

This file defines the full schema and is intended to be applied to a clean PostgreSQL instance. For production deployments, it can be replaced by a formal migration framework (e.g. Alembic). For the purpose of this platform blueprint, a **controlled SQL-first strategy** is used to maintain deterministic schema definition.

**Applying the schema:** After starting services (e.g. `docker compose up -d`), apply the schema once (see [docs/TESTING_AND_LOCAL_SETUP.md](docs/TESTING_AND_LOCAL_SETUP.md) for the exact `docker exec` command). Schema application is not auto-run by Compose by design; for production, automation (e.g. init container or `docker-entrypoint-initdb.d`) can run the migration on first deploy.

**Future schema evolution:** For incremental evolution beyond the bootstrap phase, add numbered migration files in `app/migrations/`, apply them sequentially, and maintain applied-migration tracking in a dedicated table (or adopt a tool such as Alembic). This repo does not implement that layer; the single bootstrap file is intentional for blueprint clarity.

---

## 8. Security Considerations

- **Authentication:** `JWT_SECRET` is configured; JWT validation and tenant binding at the API layer are the intended next step for production.
- **Authorization:** `RBACService.check_permission(role, action)` with roles ADMIN, ANALYST, APPROVER, VIEWER; approval workflows enforce APPROVER/ADMIN for approve/reject.
- **Tenant isolation:** Enforced via `TenantContext` and tenant-scoped resource access; cross-tenant access raises and is not surfaced to the client.
- **Sensitive data:** `EncryptionService` (AES/Fernet) is available for encrypting data at rest; key from environment; no global state.
- **Audit:** Governance layer writes immutable audit records (who, what, when UTC, why, correlation_id) for material actions (event creation, model/prompt changes, approvals).

---

## 9. Observability and Scalability

**Observability:**  
Metrics (Prometheus-style counters and histograms), OpenTelemetry-style tracing (trace/span hierarchy), cost tracking per tenant/model/request, failure classification (VALIDATION_ERROR, POLICY_VIOLATION, HIGH_RISK, WORKFLOW_ERROR, INFRA_ERROR, UNEXPECTED_ERROR), and deterministic quality evaluation. All components are dependency-injected; in-memory and simulated Langfuse allow tests and staging without external SaaS. Same interfaces can be wired to real Prometheus, OTLP, or Langfuse later.

**Scalability:**  
Distributed lock (Redis SETNX + TTL, token-based release) prevents duplicate workflow execution across nodes. Per-tenant rate limiting, circuit breaker (CLOSED → OPEN → HALF_OPEN), and bulkhead (max concurrent + queue depth) protect stability. Workload partitioning by tenant (consistent hash) supports sharding and affinity. `AutoScalingPolicy.evaluate(MetricsSnapshot)` yields SCALE_UP / SCALE_DOWN / NO_ACTION for integration with orchestrators. `HealthMonitor` aggregates DB, Redis, RabbitMQ, backlog, and circuit state for liveness/readiness.

---

## 10. Future Enterprise Extensions

- **Auth and tenant binding:** Enforce JWT at API edge and bind tenant from token/claims.
- **Event store and audit in DB:** Use `DbEventRepository` and run `001_initial_schema.sql`; optional dedicated audit table and retention policy.
- **Real observability backends:** Prometheus push/OTLP export, real Langfuse SDK, and optional billing/usage API integration.
- **Redis-backed rate limiter and distributed circuit state:** Shared rate limit and circuit state across replicas.
- **Vector store and LLM integration:** Qdrant (or similar) and LLM layer for retrieval and generation, with model/prompt versions from registries.
- **Kubernetes/operator:** Use scaling decisions and health output for HPA-style scaling and rollout strategy.
- **Alembic (or equivalent):** Versioned, incremental migrations and rollbacks on top of the current single bootstrap SQL file.

---

## References

| Document | Purpose |
|----------|---------|
| [docs/TESTING_AND_LOCAL_SETUP.md](docs/TESTING_AND_LOCAL_SETUP.md) | Local setup, venv, Docker Compose, health check, running tests. |
| [docs/FOLDER_AND_FILE_STRUCTURE.md](docs/FOLDER_AND_FILE_STRUCTURE.md) | Folder and file tree reference. |
| [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) | Project structure and conventions. |
| [docs/architecture/ai-system-design-governance-framework.md](docs/architecture/ai-system-design-governance-framework.md) | AI system design and governance framework. |

**Install:** From the project root, `pip install -e .` (dependencies are defined in `pyproject.toml`). For local setup and tests, see [docs/TESTING_AND_LOCAL_SETUP.md](docs/TESTING_AND_LOCAL_SETUP.md).

**API:** When the server is running, interactive docs are at `/docs`. Health: `GET /health`.

## License

MIT License — see [LICENSE](LICENSE) file.
