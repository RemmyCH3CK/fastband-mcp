// Package models defines domain models for the Fastband Enterprise control plane.
// These models represent the core entities stored in Postgres.
package models

import (
	"database/sql"
	"encoding/json"
	"time"
)

// TicketStatus represents the status of a ticket.
type TicketStatus string

const (
	TicketStatusOpen       TicketStatus = "open"
	TicketStatusInProgress TicketStatus = "in_progress"
	TicketStatusPending    TicketStatus = "pending"
	TicketStatusResolved   TicketStatus = "resolved"
	TicketStatusClosed     TicketStatus = "closed"
)

// TicketPriority represents the priority of a ticket.
type TicketPriority string

const (
	TicketPriorityLow      TicketPriority = "low"
	TicketPriorityMedium   TicketPriority = "medium"
	TicketPriorityHigh     TicketPriority = "high"
	TicketPriorityCritical TicketPriority = "critical"
)

// JobStatus represents the status of a job.
type JobStatus string

const (
	JobStatusQueued    JobStatus = "queued"
	JobStatusRunning   JobStatus = "running"
	JobStatusCompleted JobStatus = "completed"
	JobStatusFailed    JobStatus = "failed"
	JobStatusCancelled JobStatus = "cancelled"
)

// ApprovalStatus represents the status of an approval request.
type ApprovalStatus string

const (
	ApprovalStatusPending  ApprovalStatus = "pending"
	ApprovalStatusApproved ApprovalStatus = "approved"
	ApprovalStatusRejected ApprovalStatus = "rejected"
	ApprovalStatusExpired  ApprovalStatus = "expired"
)

// EventCategory represents the category of an audit event.
type EventCategory string

const (
	EventCategorySecurity    EventCategory = "security"
	EventCategoryCompliance  EventCategory = "compliance"
	EventCategoryOperational EventCategory = "operational"
	EventCategoryAccess      EventCategory = "access"
	EventCategoryData        EventCategory = "data"
)

// EventSeverity represents the severity of an audit event.
type EventSeverity string

const (
	EventSeverityInfo     EventSeverity = "info"
	EventSeverityWarning  EventSeverity = "warning"
	EventSeverityError    EventSeverity = "error"
	EventSeverityCritical EventSeverity = "critical"
)

// ActorType represents the type of actor that performed an action.
type ActorType string

const (
	ActorTypeUser    ActorType = "user"
	ActorTypeSystem  ActorType = "system"
	ActorTypeAgent   ActorType = "agent"
	ActorTypeService ActorType = "service"
)

// EventOutcome represents the outcome of an audited action.
type EventOutcome string

const (
	EventOutcomeSuccess EventOutcome = "success"
	EventOutcomeFailure EventOutcome = "failure"
	EventOutcomePending EventOutcome = "pending"
)

// JSONB represents a JSONB column that can be scanned from and marshaled to JSON.
type JSONB map[string]interface{}

// Scan implements the sql.Scanner interface.
func (j *JSONB) Scan(value interface{}) error {
	if value == nil {
		*j = nil
		return nil
	}

	switch v := value.(type) {
	case []byte:
		return json.Unmarshal(v, j)
	case string:
		return json.Unmarshal([]byte(v), j)
	default:
		return nil
	}
}

// StringArray represents a PostgreSQL text array.
type StringArray []string

// Scan implements the sql.Scanner interface.
func (a *StringArray) Scan(value interface{}) error {
	if value == nil {
		*a = nil
		return nil
	}

	switch v := value.(type) {
	case []byte:
		return json.Unmarshal(v, a)
	case string:
		return json.Unmarshal([]byte(v), a)
	default:
		return nil
	}
}

// Ticket represents a work ticket in the system.
type Ticket struct {
	ID          string          `json:"id" db:"id"`
	WorkspaceID string          `json:"workspace_id" db:"workspace_id"`
	Title       string          `json:"title" db:"title"`
	Description string          `json:"description" db:"description"`
	Status      TicketStatus    `json:"status" db:"status"`
	Priority    TicketPriority  `json:"priority" db:"priority"`
	Labels      StringArray     `json:"labels" db:"labels"`
	AssignedTo  sql.NullString  `json:"assigned_to,omitempty" db:"assigned_to"`
	CreatedBy   string          `json:"created_by" db:"created_by"`
	CreatedAt   time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt   time.Time       `json:"updated_at" db:"updated_at"`
	Metadata    JSONB           `json:"metadata,omitempty" db:"metadata"`
}

// Job represents an execution job associated with a ticket.
type Job struct {
	ID            string         `json:"id" db:"id"`
	TicketID      string         `json:"ticket_id" db:"ticket_id"`
	Status        JobStatus      `json:"status" db:"status"`
	ExecutionNode sql.NullString `json:"execution_node,omitempty" db:"execution_node"`
	Context       JSONB          `json:"context,omitempty" db:"context"`
	CreatedAt     time.Time      `json:"created_at" db:"created_at"`
	StartedAt     sql.NullTime   `json:"started_at,omitempty" db:"started_at"`
	CompletedAt   sql.NullTime   `json:"completed_at,omitempty" db:"completed_at"`
	Result        JSONB          `json:"result,omitempty" db:"result"`
}

// Approval represents an approval request for a tool execution.
type Approval struct {
	ID          string          `json:"id" db:"id"`
	JobID       string          `json:"job_id" db:"job_id"`
	ToolCallID  string          `json:"tool_call_id" db:"tool_call_id"`
	Tool        string          `json:"tool" db:"tool"`
	Resource    string          `json:"resource" db:"resource"`
	Status      ApprovalStatus  `json:"status" db:"status"`
	RequestedBy string          `json:"requested_by" db:"requested_by"`
	RequestedAt time.Time       `json:"requested_at" db:"requested_at"`
	DecidedBy   sql.NullString  `json:"decided_by,omitempty" db:"decided_by"`
	DecidedAt   sql.NullTime    `json:"decided_at,omitempty" db:"decided_at"`
	Comment     sql.NullString  `json:"comment,omitempty" db:"comment"`
	Conditions  JSONB           `json:"conditions,omitempty" db:"conditions"`
}

// AuditRecord represents an immutable audit log entry.
// This table is append-only; UPDATE and DELETE operations are blocked at the database level.
type AuditRecord struct {
	ID           string        `json:"id" db:"id"`
	EventType    string        `json:"event_type" db:"event_type"`
	Category     EventCategory `json:"category" db:"category"`
	Severity     EventSeverity `json:"severity" db:"severity"`
	ActorID      string        `json:"actor_id" db:"actor_id"`
	ActorType    ActorType     `json:"actor_type" db:"actor_type"`
	Action       string        `json:"action" db:"action"`
	ResourceID   string        `json:"resource_id" db:"resource_id"`
	ResourceType string        `json:"resource_type" db:"resource_type"`
	WorkspaceID  string        `json:"workspace_id" db:"workspace_id"`
	Outcome      EventOutcome  `json:"outcome" db:"outcome"`
	Context      JSONB         `json:"context,omitempty" db:"context"`
	Details      JSONB         `json:"details,omitempty" db:"details"`
	Timestamp    time.Time     `json:"timestamp" db:"timestamp"`
	ReceivedAt   time.Time     `json:"received_at" db:"received_at"`
}
