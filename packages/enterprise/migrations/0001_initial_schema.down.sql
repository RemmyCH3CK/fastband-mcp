-- Migration: 0001_initial_schema (DOWN)
-- Description: Rollback initial schema for Fastband Enterprise control plane
-- Created: Task 3.3 - Postgres Persistence

-- =============================================================================
-- DROP TABLES IN REVERSE ORDER OF CREATION
-- =============================================================================
-- Tables must be dropped in reverse order due to foreign key constraints.

-- Drop audit_records table and its triggers
DROP TRIGGER IF EXISTS audit_records_no_delete ON audit_records;
DROP TRIGGER IF EXISTS audit_records_no_update ON audit_records;
DROP FUNCTION IF EXISTS audit_records_prevent_delete();
DROP FUNCTION IF EXISTS audit_records_prevent_update();
DROP TABLE IF EXISTS audit_records;

-- Drop approvals table
DROP TABLE IF EXISTS approvals;

-- Drop jobs table
DROP TABLE IF EXISTS jobs;

-- Drop tickets table and its trigger
DROP TRIGGER IF EXISTS tickets_updated_at ON tickets;
DROP TABLE IF EXISTS tickets;

-- Drop shared trigger function
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Note: We do not drop the uuid-ossp extension as it may be used by other schemas
