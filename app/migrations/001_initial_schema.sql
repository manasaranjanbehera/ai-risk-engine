--
-- Initial schema: extensions, core tables (tenants, jobs, audit_logs, etc.), and application events table.
-- Authoritative bootstrap migration for the AI Risk Engine. Apply to a clean PostgreSQL instance.
--

--
-- Extension: uuid-ossp
--
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;
COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';

--
-- Core tables (reference schema)
--

CREATE TABLE public.tenants (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.jobs (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    external_reference text,
    event_type text NOT NULL,
    event_source text,
    payload jsonb NOT NULL,
    priority integer DEFAULT 5,
    status text NOT NULL,
    retry_count integer DEFAULT 0,
    error_message text,
    correlation_id text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    completed_at timestamp without time zone,
    CONSTRAINT jobs_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'queued'::text, 'processing'::text, 'completed'::text, 'failed'::text, 'escalated'::text])))
);

CREATE TABLE public.audit_logs (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    job_id uuid,
    tenant_id uuid NOT NULL,
    actor_type text,
    actor_id text,
    action text NOT NULL,
    previous_state jsonb,
    new_state jsonb,
    metadata jsonb,
    ip_address text,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.escalations (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    job_id uuid NOT NULL,
    assigned_to text,
    status text,
    resolution_notes text,
    resolved_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT escalations_status_check CHECK ((status = ANY (ARRAY['open'::text, 'in_review'::text, 'resolved'::text, 'rejected'::text])))
);

CREATE TABLE public.job_events (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    job_id uuid NOT NULL,
    event_type text NOT NULL,
    event_payload jsonb,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.risk_results (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    job_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    risk_score numeric(5,2),
    category text,
    confidence numeric(5,2),
    requires_escalation boolean DEFAULT false,
    explanation text,
    structured_output jsonb,
    model_provider text,
    model_name text,
    model_version text,
    prompt_version text,
    routing_strategy text,
    token_input integer,
    token_output integer,
    cost_estimate numeric(10,5),
    latency_ms integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);

--
-- Primary keys
--
ALTER TABLE ONLY public.tenants ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.jobs ADD CONSTRAINT jobs_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.jobs ADD CONSTRAINT jobs_external_reference_key UNIQUE (external_reference);
ALTER TABLE ONLY public.audit_logs ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.escalations ADD CONSTRAINT escalations_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.job_events ADD CONSTRAINT job_events_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.risk_results ADD CONSTRAINT risk_results_pkey PRIMARY KEY (id);

--
-- Indexes
--
CREATE INDEX idx_audit_job ON public.audit_logs USING btree (job_id);
CREATE INDEX idx_audit_tenant ON public.audit_logs USING btree (tenant_id);
CREATE INDEX idx_escalation_job ON public.escalations USING btree (job_id);
CREATE INDEX idx_job_events_job ON public.job_events USING btree (job_id);
CREATE INDEX idx_jobs_created_at ON public.jobs USING btree (created_at);
CREATE INDEX idx_jobs_status ON public.jobs USING btree (status);
CREATE INDEX idx_jobs_tenant ON public.jobs USING btree (tenant_id);
CREATE INDEX idx_risk_job ON public.risk_results USING btree (job_id);
CREATE INDEX idx_risk_tenant ON public.risk_results USING btree (tenant_id);

--
-- Foreign keys
--
ALTER TABLE ONLY public.audit_logs ADD CONSTRAINT audit_logs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);
ALTER TABLE ONLY public.escalations ADD CONSTRAINT escalations_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(id);
ALTER TABLE ONLY public.job_events ADD CONSTRAINT job_events_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(id);
ALTER TABLE ONLY public.jobs ADD CONSTRAINT jobs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);
ALTER TABLE ONLY public.risk_results ADD CONSTRAINT risk_results_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(id);
ALTER TABLE ONLY public.risk_results ADD CONSTRAINT risk_results_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Application events table (DB-backed event store; status RECEIVED at application boundary).
-- Required for DbEventRepository. Optional BaseModel-style columns included.
--
CREATE TABLE IF NOT EXISTS events (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    tenant_id varchar NOT NULL,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz,
    created_by varchar,
    updated_by varchar,
    is_deleted boolean DEFAULT false,
    event_id varchar NOT NULL,
    correlation_id varchar NOT NULL,
    status varchar NOT NULL DEFAULT 'received',
    event_type varchar NOT NULL,
    metadata jsonb,
    version varchar NOT NULL DEFAULT '1.0'
);
CREATE INDEX IF NOT EXISTS idx_events_tenant_id ON events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_events_event_id ON events(event_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_tenant_event_id ON events(tenant_id, event_id);
COMMENT ON TABLE events IS 'Persisted domain events at application boundary (status RECEIVED).';
