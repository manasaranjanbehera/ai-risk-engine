# ADR-001: Runtime Governance Enforcement

## Status

Accepted

## Context

The AI Risk Engine previously maintained model and prompt registries to track approved assets. Workflows could, however, resolve and use model or prompt versions through registry methods that did not strictly require approval at runtime. As a result, execution paths could proceed with unapproved or fallback assets when resolution failed or returned non-approved records.

This created a governance gap: policy required that only approved models and prompts be used in production, but the runtime did not enforce that requirement. Governance could effectively be bypassed if enforcement was not embedded in the execution path. The risk is that unapproved AI assets could be invoked, undermining auditability and compliance with enterprise AI governance controls.

## Decision

Workflows must resolve models and prompts exclusively through the governance-approved resolution API:

- **Model resolution:** `get_approved_model(model_name [, version])` on the model registry. Only approved, deployable model records may be returned.
- **Prompt resolution:** `get_approved_prompt(prompt_id [, version])` on the prompt registry. Only approved prompt records may be returned.

When approval is missing or the asset is not found:

1. **Execution is blocked.** The workflow must not proceed with unapproved model or prompt versions. No fallback to default or unapproved assets is permitted.
2. **A governance violation error is raised.** The registry raises an appropriate exception (e.g. `ModelNotApprovedError` or `PromptNotApprovedError`), treated as a governance violation; the workflow does not swallow these exceptions.
3. **The violation is logged via AuditLogger.** On catching the governance exception, the workflow logs an audit event (e.g. `GOVERNANCE_VIOLATION`) with actor, tenant, correlation context, resource type, resource id, reason, and metadata so that every attempt to use an unapproved asset is recorded.
4. **FailureClassifier classifies the event.** The exception is classified (e.g. as `POLICY_VIOLATION`) so that metrics, dashboards, and alerting can treat runtime governance failures consistently with other policy violations.

Workflows depend on the governance layer for these resolution calls when registries are injected; when no registry is provided (e.g. certain tests or non-governed environments), workflows may use alternative resolution strategies as documented, without weakening enforcement in governed environments.

## Consequences

### Positive

- **Strict governance enforcement:** Only approved models and prompts can be used at runtime; approval is enforced in code at the point of resolution, not only by process or documentation.
- **Prevention of unapproved AI usage:** Execution is blocked before any workflow nodes run with unapproved assets, reducing the risk of policy violations and inappropriate model or prompt use.
- **Improved auditability:** Every attempted use of an unapproved asset produces an immutable audit record (e.g. `GOVERNANCE_VIOLATION`) with correlation context and reason, supporting compliance reviews and forensics.
- **Alignment with enterprise AI governance:** The design aligns with enterprise expectations for controlled, auditable, and policy-driven use of AI assets.

### Trade-offs

- **Tighter coupling between workflow runtime and governance layer:** Workflows must call registry APIs and handle governance exceptions; the orchestration layer depends on the governance interfaces and behaviour.
- **Additional runtime checks:** Resolution of model and prompt versions incurs registry lookups and approval checks at workflow start, adding a small overhead and dependency on registry availability and correctness.
