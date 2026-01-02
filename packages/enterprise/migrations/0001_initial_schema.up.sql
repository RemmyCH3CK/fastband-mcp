-- Migration: 0001_initial_schema
-- Description: Initial schema for Fastband Enterprise control plane
-- Created: Task 3.3 - Postgres Persistence

-- Enable UUID extension for generating UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- TICKETS TABLE
-- =============================================================================
-- Tickets represent work items in the system. They can be assigned to users
-- and have associated jobs for execution.

CREATE TABLE tickets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    VARCHAR(255) NOT NULL,
    title           VARCHAR(500) NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    status          VARCHAR(50) NOT NULL DEFAULT 'open',
    priority        VARCHAR(50) NOT NULL DEFAULT 'medium',
    labels          TEXT[] NOT NULL DEFAULT '{}',
    assigned_to     VARCHAR(255),
    created_by      VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB NOT NULL DEFAULT '{}',

    -- Constraints
    CONSTRAINT tickets_status_check CHECK (status IN ('open', 'in_progress', 'pending', 'resolved', 'closed')),
    CONSTRAINT tickets_priority_check CHECK (priority IN ('low', 'medium', 'high', 'critical'))
);

-- Indexes for tickets table
CREATE INDEX idx_tickets_workspace_id ON tickets(workspace_id);
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_priority ON tickets(priority);
CREATE INDEX idx_tickets_assigned_to ON tickets(assigned_to) WHERE assigned_to IS NOT NULL;
CREATE INDEX idx_tickets_created_by ON tickets(created_by);
CREATE INDEX idx_tickets_created_at ON tickets(created_at DESC);
CREATE INDEX idx_tickets_workspace_status ON tickets(workspace_id, status);
CREATE INDEX idx_tickets_labels ON tickets USING GIN(labels);

-- Trigger function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to tickets
CREATE TRIGGER tickets_updated_at
    BEFORE UPDATE ON tickets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- JOBS TABLE
-- =============================================================================
-- Jobs represent execution tasks associated with tickets. Each job tracks
-- the execution status and results.

CREATE TABLE jobs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id       UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    status          VARCHAR(50) NOT NULL DEFAULT 'queued',
    execution_node  VARCHAR(255),
    context         JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    result          JSONB NOT NULL DEFAULT '{}',

    -- Constraints
    CONSTRAINT jobs_status_check CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled'))
);

-- Indexes for jobs table
CREATE INDEX idx_jobs_ticket_id ON jobs(ticket_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_execution_node ON jobs(execution_node) WHERE execution_node IS NOT NULL;
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX idx_jobs_ticket_status ON jobs(ticket_id, status);

-- =============================================================================
-- APPROVALS TABLE
-- =============================================================================
-- Approvals track approval requests for tool executions within jobs.
-- Used for human-in-the-loop workflows.

CREATE TABLE approvals (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id          UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    tool_call_id    VARCHAR(255) NOT NULL,
    tool            VARCHAR(255) NOT NULL,
    resource        VARCHAR(500) NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    requested_by    VARCHAR(255) NOT NULL,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_by      VARCHAR(255),
    decided_at      TIMESTAMPTZ,
    comment         TEXT,
    conditions      JSONB NOT NULL DEFAULT '{}',

    -- Constraints
    CONSTRAINT approvals_status_check CHECK (status IN ('pending', 'approved', 'rejected', 'expired'))
);

-- Indexes for approvals table
CREATE INDEX idx_approvals_job_id ON approvals(job_id);
CREATE INDEX idx_approvals_status ON approvals(status);
CREATE INDEX idx_approvals_requested_by ON approvals(requested_by);
CREATE INDEX idx_approvals_requested_at ON approvals(requested_at DESC);
CREATE INDEX idx_approvals_job_status ON approvals(job_id, status);
CREATE INDEX idx_approvals_tool ON approvals(tool);

-- =============================================================================
-- AUDIT_RECORDS TABLE (APPEND-ONLY)
-- =============================================================================
-- Audit records provide an immutable audit trail of all actions in the system.
-- This table is APPEND-ONLY: UPDATE and DELETE operations are blocked by triggers.

CREATE TABLE audit_records (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type      VARCHAR(255) NOT NULL,
    category        VARCHAR(50) NOT NULL,
    severity        VARCHAR(50) NOT NULL,
    actor_id        VARCHAR(255) NOT NULL,
    actor_type      VARCHAR(50) NOT NULL,
    action          VARCHAR(255) NOT NULL,
    resource_id     VARCHAR(255) NOT NULL,
    resource_type   VARCHAR(255) NOT NULL,
    workspace_id    VARCHAR(255) NOT NULL,
    outcome         VARCHAR(50) NOT NULL,
    context         JSONB NOT NULL DEFAULT '{}',
    details         JSONB NOT NULL DEFAULT '{}',
    timestamp       TIMESTAMPTZ NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT audit_records_category_check CHECK (category IN ('security', 'compliance', 'operational', 'access', 'data')),
    CONSTRAINT audit_records_severity_check CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    CONSTRAINT audit_records_actor_type_check CHECK (actor_type IN ('user', 'system', 'agent', 'service')),
    CONSTRAINT audit_records_outcome_check CHECK (outcome IN ('success', 'failure', 'pending'))
);

-- Indexes for audit_records table
CREATE INDEX idx_audit_records_event_type ON audit_records(event_type);
CREATE INDEX idx_audit_records_category ON audit_records(category);
CREATE INDEX idx_audit_records_severity ON audit_records(severity);
CREATE INDEX idx_audit_records_actor_id ON audit_records(actor_id);
CREATE INDEX idx_audit_records_actor_type ON audit_records(actor_type);
CREATE INDEX idx_audit_records_action ON audit_records(action);
CREATE INDEX idx_audit_records_resource_id ON audit_records(resource_id);
CREATE INDEX idx_audit_records_resource_type ON audit_records(resource_type);
CREATE INDEX idx_audit_records_workspace_id ON audit_records(workspace_id);
CREATE INDEX idx_audit_records_outcome ON audit_records(outcome);
CREATE INDEX idx_audit_records_timestamp ON audit_records(timestamp DESC);
CREATE INDEX idx_audit_records_received_at ON audit_records(received_at DESC);
CREATE INDEX idx_audit_records_workspace_timestamp ON audit_records(workspace_id, timestamp DESC);
CREATE INDEX idx_audit_records_actor_timestamp ON audit_records(actor_id, timestamp DESC);

-- =============================================================================
-- APPEND-ONLY ENFORCEMENT FOR AUDIT_RECORDS
-- =============================================================================
-- These triggers prevent UPDATE and DELETE operations on the audit_records table,
-- enforcing append-only semantics at the database level.

-- Trigger function to prevent UPDATE operations
CREATE OR REPLACE FUNCTION audit_records_prevent_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'UPDATE operations are not allowed on audit_records table. This table is append-only.';
END;
$$ LANGUAGE plpgsql;

-- Trigger function to prevent DELETE operations
CREATE OR REPLACE FUNCTION audit_records_prevent_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'DELETE operations are not allowed on audit_records table. This table is append-only.';
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to prevent UPDATE and DELETE
CREATE TRIGGER audit_records_no_update
    BEFORE UPDATE ON audit_records
    FOR EACH ROW
    EXECUTE FUNCTION audit_records_prevent_update();

CREATE TRIGGER audit_records_no_delete
    BEFORE DELETE ON audit_records
    FOR EACH ROW
    EXECUTE FUNCTION audit_records_prevent_delete();

-- =============================================================================
-- COMMENTS
-- =============================================================================
COMMENT ON TABLE tickets IS 'Work tickets in the Fastband Enterprise system';
COMMENT ON TABLE jobs IS 'Execution jobs associated with tickets';
COMMENT ON TABLE approvals IS 'Approval requests for tool executions';
COMMENT ON TABLE audit_records IS 'Immutable audit trail (append-only, no UPDATE/DELETE allowed)';

COMMENT ON TRIGGER audit_records_no_update ON audit_records IS 'Prevents UPDATE operations to enforce append-only semantics';
COMMENT ON TRIGGER audit_records_no_delete ON audit_records IS 'Prevents DELETE operations to enforce append-only semantics';
