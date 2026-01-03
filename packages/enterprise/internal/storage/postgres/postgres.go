// Package postgres implements PostgreSQL storage for the Fastband Enterprise control plane.
// It provides the PostgresStore interface implementation with connection pooling,
// health checking, and CRUD operations for domain models.
package postgres

import (
	"context"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	// Import pgx driver for Postgres
	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/lib/pq"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/health"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/models"
)

// Common errors for repository operations.
var (
	ErrNotFound      = errors.New("record not found")
	ErrInvalidCursor = errors.New("invalid cursor")
)

// Config holds configuration for the Postgres connection.
type Config struct {
	// Host is the database server hostname.
	Host string
	// Port is the database server port.
	Port int
	// Database is the database name.
	Database string
	// User is the database user.
	User string
	// Password is the database password.
	Password string
	// SSLMode is the SSL mode (disable, require, verify-ca, verify-full).
	SSLMode string
	// MaxOpenConns is the maximum number of open connections in the pool.
	MaxOpenConns int
	// MaxIdleConns is the maximum number of idle connections in the pool.
	MaxIdleConns int
	// ConnMaxLifetime is the maximum lifetime of a connection.
	ConnMaxLifetime time.Duration
	// ConnMaxIdleTime is the maximum idle time for a connection.
	ConnMaxIdleTime time.Duration
	// ConnectTimeout is the timeout for establishing a connection.
	ConnectTimeout time.Duration
}

// DefaultConfig returns a Config with sensible defaults.
func DefaultConfig() Config {
	return Config{
		Host:            "localhost",
		Port:            5432,
		Database:        "fastband",
		User:            "postgres",
		Password:        "",
		SSLMode:         "disable",
		MaxOpenConns:    25,
		MaxIdleConns:    5,
		ConnMaxLifetime: 5 * time.Minute,
		ConnMaxIdleTime: 1 * time.Minute,
		ConnectTimeout:  10 * time.Second,
	}
}

// DSN returns the data source name (connection string) for the config.
func (c Config) DSN() string {
	return fmt.Sprintf(
		"host=%s port=%d dbname=%s user=%s password=%s sslmode=%s connect_timeout=%d",
		c.Host,
		c.Port,
		c.Database,
		c.User,
		c.Password,
		c.SSLMode,
		int(c.ConnectTimeout.Seconds()),
	)
}

// Postgres implements the PostgresStore interface.
// It provides connection pooling and health checking for PostgreSQL.
type Postgres struct {
	db     *sql.DB
	config Config
}

// New creates a new Postgres store with the given configuration.
// It establishes a connection pool and verifies connectivity.
func New(ctx context.Context, cfg Config) (*Postgres, error) {
	db, err := sql.Open("pgx", cfg.DSN())
	if err != nil {
		return nil, fmt.Errorf("failed to open database connection: %w", err)
	}

	// Configure connection pool
	db.SetMaxOpenConns(cfg.MaxOpenConns)
	db.SetMaxIdleConns(cfg.MaxIdleConns)
	db.SetConnMaxLifetime(cfg.ConnMaxLifetime)
	db.SetConnMaxIdleTime(cfg.ConnMaxIdleTime)

	// Verify connectivity
	if err := db.PingContext(ctx); err != nil {
		_ = db.Close() // Clean up on failure
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return &Postgres{
		db:     db,
		config: cfg,
	}, nil
}

// NewWithDB creates a new Postgres store with an existing database connection.
// This is primarily used for testing with mock databases.
func NewWithDB(db *sql.DB) *Postgres {
	return &Postgres{
		db:     db,
		config: DefaultConfig(),
	}
}

// DB returns the underlying database connection pool.
// Use with caution - prefer using the store methods.
func (p *Postgres) DB() *sql.DB {
	return p.db
}

// Close closes the database connection pool.
func (p *Postgres) Close() error {
	if p.db != nil {
		return p.db.Close()
	}
	return nil
}

// =============================================================================
// PostgresStore Interface Implementation
// =============================================================================

// Ping checks if the database connection is healthy.
// It satisfies the PostgresStore interface.
func (p *Postgres) Ping(ctx context.Context) error {
	if p.db == nil {
		return errors.New("database connection is nil")
	}
	return p.db.PingContext(ctx)
}

// =============================================================================
// health.Checker Interface Implementation
// =============================================================================

// Name returns the name of this health checker.
func (p *Postgres) Name() string {
	return "database"
}

// Check performs a health check on the database connection.
func (p *Postgres) Check() health.CheckResult {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := p.Ping(ctx); err != nil {
		return health.CheckResult{
			Status:  "unhealthy",
			Message: fmt.Sprintf("database ping failed: %v", err),
		}
	}

	// Get connection pool stats
	stats := p.db.Stats()

	return health.CheckResult{
		Status: "healthy",
		Message: fmt.Sprintf(
			"open_connections=%d, in_use=%d, idle=%d",
			stats.OpenConnections,
			stats.InUse,
			stats.Idle,
		),
	}
}

// =============================================================================
// Cursor Helpers
// =============================================================================

// encodeCursor encodes a cursor value (typically an ID) to a base64 string.
func encodeCursor(id string) string {
	return base64.StdEncoding.EncodeToString([]byte(id))
}

// decodeCursor decodes a base64 cursor string to the original ID.
func decodeCursor(cursor string) (string, error) {
	if cursor == "" {
		return "", nil
	}
	data, err := base64.StdEncoding.DecodeString(cursor)
	if err != nil {
		return "", ErrInvalidCursor
	}
	return string(data), nil
}

// normalizeLimit ensures limit is within valid bounds.
func normalizeLimit(limit int) int {
	if limit <= 0 {
		return models.DefaultPageLimit
	}
	if limit > models.MaxPageLimit {
		return models.MaxPageLimit
	}
	return limit
}

// =============================================================================
// Ticket Operations
// =============================================================================

// CreateTicket creates a new ticket in the database.
func (p *Postgres) CreateTicket(ctx context.Context, ticket *models.Ticket) error {
	if ticket == nil {
		return errors.New("ticket cannot be nil")
	}

	// Marshal metadata and labels to JSON
	metadataJSON, err := json.Marshal(ticket.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	query := `
		INSERT INTO tickets (
			id, workspace_id, title, description, status, priority,
			labels, assigned_to, created_by, created_at, updated_at, metadata
		) VALUES (
			$1, $2, $3, $4, $5, $6,
			$7, $8, $9, $10, $11, $12
		)
	`

	var assignedTo *string
	if ticket.AssignedTo.Valid {
		assignedTo = &ticket.AssignedTo.String
	}

	_, err = p.db.ExecContext(ctx, query,
		ticket.ID,
		ticket.WorkspaceID,
		ticket.Title,
		ticket.Description,
		ticket.Status,
		ticket.Priority,
		pq.Array(ticket.Labels),
		assignedTo,
		ticket.CreatedBy,
		ticket.CreatedAt,
		ticket.UpdatedAt,
		metadataJSON,
	)
	if err != nil {
		return fmt.Errorf("failed to create ticket: %w", err)
	}

	return nil
}

// GetTicket retrieves a ticket by ID.
func (p *Postgres) GetTicket(ctx context.Context, id string) (*models.Ticket, error) {
	query := `
		SELECT id, workspace_id, title, description, status, priority,
			   labels, assigned_to, created_by, created_at, updated_at, metadata
		FROM tickets
		WHERE id = $1
	`

	ticket := &models.Ticket{}
	var metadataJSON []byte

	err := p.db.QueryRowContext(ctx, query, id).Scan(
		&ticket.ID,
		&ticket.WorkspaceID,
		&ticket.Title,
		&ticket.Description,
		&ticket.Status,
		&ticket.Priority,
		&ticket.Labels,
		&ticket.AssignedTo,
		&ticket.CreatedBy,
		&ticket.CreatedAt,
		&ticket.UpdatedAt,
		&metadataJSON,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, fmt.Errorf("failed to get ticket: %w", err)
	}

	if len(metadataJSON) > 0 {
		if err := json.Unmarshal(metadataJSON, &ticket.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}
	}

	return ticket, nil
}

// UpdateTicket updates an existing ticket.
func (p *Postgres) UpdateTicket(ctx context.Context, ticket *models.Ticket) error {
	if ticket == nil {
		return errors.New("ticket cannot be nil")
	}

	metadataJSON, err := json.Marshal(ticket.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	query := `
		UPDATE tickets SET
			title = $2,
			description = $3,
			status = $4,
			priority = $5,
			labels = $6,
			assigned_to = $7,
			metadata = $8
		WHERE id = $1
	`

	var assignedTo *string
	if ticket.AssignedTo.Valid {
		assignedTo = &ticket.AssignedTo.String
	}

	result, err := p.db.ExecContext(ctx, query,
		ticket.ID,
		ticket.Title,
		ticket.Description,
		ticket.Status,
		ticket.Priority,
		pq.Array(ticket.Labels),
		assignedTo,
		metadataJSON,
	)
	if err != nil {
		return fmt.Errorf("failed to update ticket: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}
	if rows == 0 {
		return ErrNotFound
	}

	return nil
}

// DeleteTicket deletes a ticket by ID.
func (p *Postgres) DeleteTicket(ctx context.Context, id string) error {
	query := `DELETE FROM tickets WHERE id = $1`

	result, err := p.db.ExecContext(ctx, query, id)
	if err != nil {
		return fmt.Errorf("failed to delete ticket: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}
	if rows == 0 {
		return ErrNotFound
	}

	return nil
}

// ListTickets retrieves tickets matching the given filters with cursor pagination.
func (p *Postgres) ListTickets(ctx context.Context, filter models.TicketFilter) (*models.TicketList, error) {
	limit := normalizeLimit(filter.Limit)

	// Decode cursor to get the last seen ID
	cursorID, err := decodeCursor(filter.Cursor)
	if err != nil {
		return nil, err
	}

	// Build query with filters
	var conditions []string
	var args []interface{}
	argNum := 1

	if filter.WorkspaceID != "" {
		conditions = append(conditions, fmt.Sprintf("workspace_id = $%d", argNum))
		args = append(args, filter.WorkspaceID)
		argNum++
	}
	if filter.Status != "" {
		conditions = append(conditions, fmt.Sprintf("status = $%d", argNum))
		args = append(args, filter.Status)
		argNum++
	}
	if filter.Priority != "" {
		conditions = append(conditions, fmt.Sprintf("priority = $%d", argNum))
		args = append(args, filter.Priority)
		argNum++
	}
	if filter.AssignedTo != "" {
		conditions = append(conditions, fmt.Sprintf("assigned_to = $%d", argNum))
		args = append(args, filter.AssignedTo)
		argNum++
	}
	if filter.CreatedBy != "" {
		conditions = append(conditions, fmt.Sprintf("created_by = $%d", argNum))
		args = append(args, filter.CreatedBy)
		argNum++
	}
	if len(filter.Labels) > 0 {
		conditions = append(conditions, fmt.Sprintf("labels && $%d", argNum))
		args = append(args, pq.Array(filter.Labels))
		argNum++
	}
	if cursorID != "" {
		conditions = append(conditions, fmt.Sprintf("id > $%d", argNum))
		args = append(args, cursorID)
		argNum++
	}

	whereClause := ""
	if len(conditions) > 0 {
		whereClause = "WHERE " + strings.Join(conditions, " AND ")
	}

	// Fetch one more than limit to determine if there's a next page
	query := fmt.Sprintf(`
		SELECT id, workspace_id, title, description, status, priority,
			   labels, assigned_to, created_by, created_at, updated_at, metadata
		FROM tickets
		%s
		ORDER BY id ASC
		LIMIT $%d
	`, whereClause, argNum)
	args = append(args, limit+1)

	rows, err := p.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to list tickets: %w", err)
	}
	defer func() { _ = rows.Close() }()

	var tickets []models.Ticket
	for rows.Next() {
		var ticket models.Ticket
		var metadataJSON []byte

		if err := rows.Scan(
			&ticket.ID,
			&ticket.WorkspaceID,
			&ticket.Title,
			&ticket.Description,
			&ticket.Status,
			&ticket.Priority,
			&ticket.Labels,
			&ticket.AssignedTo,
			&ticket.CreatedBy,
			&ticket.CreatedAt,
			&ticket.UpdatedAt,
			&metadataJSON,
		); err != nil {
			return nil, fmt.Errorf("failed to scan ticket: %w", err)
		}

		if len(metadataJSON) > 0 {
			if err := json.Unmarshal(metadataJSON, &ticket.Metadata); err != nil {
				return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
			}
		}

		tickets = append(tickets, ticket)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating tickets: %w", err)
	}

	// Check if there's a next page
	hasNextPage := len(tickets) > limit
	if hasNextPage {
		tickets = tickets[:limit]
	}

	result := &models.TicketList{
		Tickets: tickets,
		PageInfo: models.PageInfo{
			HasNextPage: hasNextPage,
		},
	}

	if hasNextPage && len(tickets) > 0 {
		result.PageInfo.NextCursor = encodeCursor(tickets[len(tickets)-1].ID)
	}

	return result, nil
}

// =============================================================================
// Job Operations
// =============================================================================

// CreateJob creates a new job in the database.
func (p *Postgres) CreateJob(ctx context.Context, job *models.Job) error {
	if job == nil {
		return errors.New("job cannot be nil")
	}

	contextJSON, err := json.Marshal(job.Context)
	if err != nil {
		return fmt.Errorf("failed to marshal context: %w", err)
	}

	resultJSON, err := json.Marshal(job.Result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	query := `
		INSERT INTO jobs (
			id, ticket_id, status, execution_node, context,
			created_at, started_at, completed_at, result
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9
		)
	`

	var executionNode *string
	if job.ExecutionNode.Valid {
		executionNode = &job.ExecutionNode.String
	}

	var startedAt, completedAt *time.Time
	if job.StartedAt.Valid {
		startedAt = &job.StartedAt.Time
	}
	if job.CompletedAt.Valid {
		completedAt = &job.CompletedAt.Time
	}

	_, err = p.db.ExecContext(ctx, query,
		job.ID,
		job.TicketID,
		job.Status,
		executionNode,
		contextJSON,
		job.CreatedAt,
		startedAt,
		completedAt,
		resultJSON,
	)
	if err != nil {
		return fmt.Errorf("failed to create job: %w", err)
	}

	return nil
}

// GetJob retrieves a job by ID.
func (p *Postgres) GetJob(ctx context.Context, id string) (*models.Job, error) {
	query := `
		SELECT id, ticket_id, status, execution_node, context,
			   created_at, started_at, completed_at, result
		FROM jobs
		WHERE id = $1
	`

	job := &models.Job{}
	var contextJSON, resultJSON []byte

	err := p.db.QueryRowContext(ctx, query, id).Scan(
		&job.ID,
		&job.TicketID,
		&job.Status,
		&job.ExecutionNode,
		&contextJSON,
		&job.CreatedAt,
		&job.StartedAt,
		&job.CompletedAt,
		&resultJSON,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, fmt.Errorf("failed to get job: %w", err)
	}

	if len(contextJSON) > 0 {
		if err := json.Unmarshal(contextJSON, &job.Context); err != nil {
			return nil, fmt.Errorf("failed to unmarshal context: %w", err)
		}
	}
	if len(resultJSON) > 0 {
		if err := json.Unmarshal(resultJSON, &job.Result); err != nil {
			return nil, fmt.Errorf("failed to unmarshal result: %w", err)
		}
	}

	return job, nil
}

// UpdateJob updates an existing job.
func (p *Postgres) UpdateJob(ctx context.Context, job *models.Job) error {
	if job == nil {
		return errors.New("job cannot be nil")
	}

	contextJSON, err := json.Marshal(job.Context)
	if err != nil {
		return fmt.Errorf("failed to marshal context: %w", err)
	}

	resultJSON, err := json.Marshal(job.Result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	query := `
		UPDATE jobs SET
			status = $2,
			execution_node = $3,
			context = $4,
			started_at = $5,
			completed_at = $6,
			result = $7
		WHERE id = $1
	`

	var executionNode *string
	if job.ExecutionNode.Valid {
		executionNode = &job.ExecutionNode.String
	}

	var startedAt, completedAt *time.Time
	if job.StartedAt.Valid {
		startedAt = &job.StartedAt.Time
	}
	if job.CompletedAt.Valid {
		completedAt = &job.CompletedAt.Time
	}

	result, err := p.db.ExecContext(ctx, query,
		job.ID,
		job.Status,
		executionNode,
		contextJSON,
		startedAt,
		completedAt,
		resultJSON,
	)
	if err != nil {
		return fmt.Errorf("failed to update job: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}
	if rows == 0 {
		return ErrNotFound
	}

	return nil
}

// ListJobs retrieves jobs matching the given filters with cursor pagination.
func (p *Postgres) ListJobs(ctx context.Context, filter models.JobFilter) (*models.JobList, error) {
	limit := normalizeLimit(filter.Limit)

	cursorID, err := decodeCursor(filter.Cursor)
	if err != nil {
		return nil, err
	}

	var conditions []string
	var args []interface{}
	argNum := 1

	if filter.TicketID != "" {
		conditions = append(conditions, fmt.Sprintf("ticket_id = $%d", argNum))
		args = append(args, filter.TicketID)
		argNum++
	}
	if filter.Status != "" {
		conditions = append(conditions, fmt.Sprintf("status = $%d", argNum))
		args = append(args, filter.Status)
		argNum++
	}
	if cursorID != "" {
		conditions = append(conditions, fmt.Sprintf("id > $%d", argNum))
		args = append(args, cursorID)
		argNum++
	}

	whereClause := ""
	if len(conditions) > 0 {
		whereClause = "WHERE " + strings.Join(conditions, " AND ")
	}

	query := fmt.Sprintf(`
		SELECT id, ticket_id, status, execution_node, context,
			   created_at, started_at, completed_at, result
		FROM jobs
		%s
		ORDER BY id ASC
		LIMIT $%d
	`, whereClause, argNum)
	args = append(args, limit+1)

	rows, err := p.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to list jobs: %w", err)
	}
	defer func() { _ = rows.Close() }()

	var jobs []models.Job
	for rows.Next() {
		var job models.Job
		var contextJSON, resultJSON []byte

		if err := rows.Scan(
			&job.ID,
			&job.TicketID,
			&job.Status,
			&job.ExecutionNode,
			&contextJSON,
			&job.CreatedAt,
			&job.StartedAt,
			&job.CompletedAt,
			&resultJSON,
		); err != nil {
			return nil, fmt.Errorf("failed to scan job: %w", err)
		}

		if len(contextJSON) > 0 {
			if err := json.Unmarshal(contextJSON, &job.Context); err != nil {
				return nil, fmt.Errorf("failed to unmarshal context: %w", err)
			}
		}
		if len(resultJSON) > 0 {
			if err := json.Unmarshal(resultJSON, &job.Result); err != nil {
				return nil, fmt.Errorf("failed to unmarshal result: %w", err)
			}
		}

		jobs = append(jobs, job)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating jobs: %w", err)
	}

	hasNextPage := len(jobs) > limit
	if hasNextPage {
		jobs = jobs[:limit]
	}

	result := &models.JobList{
		Jobs: jobs,
		PageInfo: models.PageInfo{
			HasNextPage: hasNextPage,
		},
	}

	if hasNextPage && len(jobs) > 0 {
		result.PageInfo.NextCursor = encodeCursor(jobs[len(jobs)-1].ID)
	}

	return result, nil
}

// =============================================================================
// Approval Operations
// =============================================================================

// CreateApproval creates a new approval request.
func (p *Postgres) CreateApproval(ctx context.Context, approval *models.Approval) error {
	if approval == nil {
		return errors.New("approval cannot be nil")
	}

	conditionsJSON, err := json.Marshal(approval.Conditions)
	if err != nil {
		return fmt.Errorf("failed to marshal conditions: %w", err)
	}

	query := `
		INSERT INTO approvals (
			id, job_id, tool_call_id, tool, resource, status,
			requested_by, requested_at, decided_by, decided_at, comment, conditions
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
		)
	`

	var decidedBy, comment *string
	if approval.DecidedBy.Valid {
		decidedBy = &approval.DecidedBy.String
	}
	if approval.Comment.Valid {
		comment = &approval.Comment.String
	}

	var decidedAt *time.Time
	if approval.DecidedAt.Valid {
		decidedAt = &approval.DecidedAt.Time
	}

	_, err = p.db.ExecContext(ctx, query,
		approval.ID,
		approval.JobID,
		approval.ToolCallID,
		approval.Tool,
		approval.Resource,
		approval.Status,
		approval.RequestedBy,
		approval.RequestedAt,
		decidedBy,
		decidedAt,
		comment,
		conditionsJSON,
	)
	if err != nil {
		return fmt.Errorf("failed to create approval: %w", err)
	}

	return nil
}

// GetApproval retrieves an approval by ID.
func (p *Postgres) GetApproval(ctx context.Context, id string) (*models.Approval, error) {
	query := `
		SELECT id, job_id, tool_call_id, tool, resource, status,
			   requested_by, requested_at, decided_by, decided_at, comment, conditions
		FROM approvals
		WHERE id = $1
	`

	approval := &models.Approval{}
	var conditionsJSON []byte

	err := p.db.QueryRowContext(ctx, query, id).Scan(
		&approval.ID,
		&approval.JobID,
		&approval.ToolCallID,
		&approval.Tool,
		&approval.Resource,
		&approval.Status,
		&approval.RequestedBy,
		&approval.RequestedAt,
		&approval.DecidedBy,
		&approval.DecidedAt,
		&approval.Comment,
		&conditionsJSON,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, fmt.Errorf("failed to get approval: %w", err)
	}

	if len(conditionsJSON) > 0 {
		if err := json.Unmarshal(conditionsJSON, &approval.Conditions); err != nil {
			return nil, fmt.Errorf("failed to unmarshal conditions: %w", err)
		}
	}

	return approval, nil
}

// UpdateApproval updates an existing approval (e.g., to approve/reject).
func (p *Postgres) UpdateApproval(ctx context.Context, approval *models.Approval) error {
	if approval == nil {
		return errors.New("approval cannot be nil")
	}

	conditionsJSON, err := json.Marshal(approval.Conditions)
	if err != nil {
		return fmt.Errorf("failed to marshal conditions: %w", err)
	}

	query := `
		UPDATE approvals SET
			status = $2,
			decided_by = $3,
			decided_at = $4,
			comment = $5,
			conditions = $6
		WHERE id = $1
	`

	var decidedBy, comment *string
	if approval.DecidedBy.Valid {
		decidedBy = &approval.DecidedBy.String
	}
	if approval.Comment.Valid {
		comment = &approval.Comment.String
	}

	var decidedAt *time.Time
	if approval.DecidedAt.Valid {
		decidedAt = &approval.DecidedAt.Time
	}

	result, err := p.db.ExecContext(ctx, query,
		approval.ID,
		approval.Status,
		decidedBy,
		decidedAt,
		comment,
		conditionsJSON,
	)
	if err != nil {
		return fmt.Errorf("failed to update approval: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}
	if rows == 0 {
		return ErrNotFound
	}

	return nil
}

// ListApprovals retrieves approvals matching the given filters with cursor pagination.
func (p *Postgres) ListApprovals(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
	limit := normalizeLimit(filter.Limit)

	cursorID, err := decodeCursor(filter.Cursor)
	if err != nil {
		return nil, err
	}

	var conditions []string
	var args []interface{}
	argNum := 1

	if filter.JobID != "" {
		conditions = append(conditions, fmt.Sprintf("job_id = $%d", argNum))
		args = append(args, filter.JobID)
		argNum++
	}
	if filter.Status != "" {
		conditions = append(conditions, fmt.Sprintf("status = $%d", argNum))
		args = append(args, filter.Status)
		argNum++
	}
	if filter.RequestedBy != "" {
		conditions = append(conditions, fmt.Sprintf("requested_by = $%d", argNum))
		args = append(args, filter.RequestedBy)
		argNum++
	}
	if filter.Tool != "" {
		conditions = append(conditions, fmt.Sprintf("tool = $%d", argNum))
		args = append(args, filter.Tool)
		argNum++
	}
	if cursorID != "" {
		conditions = append(conditions, fmt.Sprintf("id > $%d", argNum))
		args = append(args, cursorID)
		argNum++
	}

	whereClause := ""
	if len(conditions) > 0 {
		whereClause = "WHERE " + strings.Join(conditions, " AND ")
	}

	query := fmt.Sprintf(`
		SELECT id, job_id, tool_call_id, tool, resource, status,
			   requested_by, requested_at, decided_by, decided_at, comment, conditions
		FROM approvals
		%s
		ORDER BY id ASC
		LIMIT $%d
	`, whereClause, argNum)
	args = append(args, limit+1)

	rows, err := p.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to list approvals: %w", err)
	}
	defer func() { _ = rows.Close() }()

	var approvals []models.Approval
	for rows.Next() {
		var approval models.Approval
		var conditionsJSON []byte

		if err := rows.Scan(
			&approval.ID,
			&approval.JobID,
			&approval.ToolCallID,
			&approval.Tool,
			&approval.Resource,
			&approval.Status,
			&approval.RequestedBy,
			&approval.RequestedAt,
			&approval.DecidedBy,
			&approval.DecidedAt,
			&approval.Comment,
			&conditionsJSON,
		); err != nil {
			return nil, fmt.Errorf("failed to scan approval: %w", err)
		}

		if len(conditionsJSON) > 0 {
			if err := json.Unmarshal(conditionsJSON, &approval.Conditions); err != nil {
				return nil, fmt.Errorf("failed to unmarshal conditions: %w", err)
			}
		}

		approvals = append(approvals, approval)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating approvals: %w", err)
	}

	hasNextPage := len(approvals) > limit
	if hasNextPage {
		approvals = approvals[:limit]
	}

	result := &models.ApprovalList{
		Approvals: approvals,
		PageInfo: models.PageInfo{
			HasNextPage: hasNextPage,
		},
	}

	if hasNextPage && len(approvals) > 0 {
		result.PageInfo.NextCursor = encodeCursor(approvals[len(approvals)-1].ID)
	}

	return result, nil
}

// =============================================================================
// Audit Record Operations (Append-Only)
// =============================================================================

// CreateAuditRecord creates a new audit record (append-only).
func (p *Postgres) CreateAuditRecord(ctx context.Context, record *models.AuditRecord) error {
	if record == nil {
		return errors.New("audit record cannot be nil")
	}

	contextJSON, err := json.Marshal(record.Context)
	if err != nil {
		return fmt.Errorf("failed to marshal context: %w", err)
	}

	detailsJSON, err := json.Marshal(record.Details)
	if err != nil {
		return fmt.Errorf("failed to marshal details: %w", err)
	}

	query := `
		INSERT INTO audit_records (
			id, event_type, category, severity, actor_id, actor_type,
			action, resource_id, resource_type, workspace_id, outcome,
			context, details, timestamp, received_at
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
		)
	`

	_, err = p.db.ExecContext(ctx, query,
		record.ID,
		record.EventType,
		record.Category,
		record.Severity,
		record.ActorID,
		record.ActorType,
		record.Action,
		record.ResourceID,
		record.ResourceType,
		record.WorkspaceID,
		record.Outcome,
		contextJSON,
		detailsJSON,
		record.Timestamp,
		record.ReceivedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to create audit record: %w", err)
	}

	return nil
}

// GetAuditRecord retrieves an audit record by ID.
func (p *Postgres) GetAuditRecord(ctx context.Context, id string) (*models.AuditRecord, error) {
	query := `
		SELECT id, event_type, category, severity, actor_id, actor_type,
			   action, resource_id, resource_type, workspace_id, outcome,
			   context, details, timestamp, received_at
		FROM audit_records
		WHERE id = $1
	`

	record := &models.AuditRecord{}
	var contextJSON, detailsJSON []byte

	err := p.db.QueryRowContext(ctx, query, id).Scan(
		&record.ID,
		&record.EventType,
		&record.Category,
		&record.Severity,
		&record.ActorID,
		&record.ActorType,
		&record.Action,
		&record.ResourceID,
		&record.ResourceType,
		&record.WorkspaceID,
		&record.Outcome,
		&contextJSON,
		&detailsJSON,
		&record.Timestamp,
		&record.ReceivedAt,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, fmt.Errorf("failed to get audit record: %w", err)
	}

	if len(contextJSON) > 0 {
		if err := json.Unmarshal(contextJSON, &record.Context); err != nil {
			return nil, fmt.Errorf("failed to unmarshal context: %w", err)
		}
	}
	if len(detailsJSON) > 0 {
		if err := json.Unmarshal(detailsJSON, &record.Details); err != nil {
			return nil, fmt.Errorf("failed to unmarshal details: %w", err)
		}
	}

	return record, nil
}

// ListAuditRecords retrieves audit records matching the given filters with cursor pagination.
func (p *Postgres) ListAuditRecords(ctx context.Context, filter models.AuditFilter) (*models.AuditList, error) {
	limit := normalizeLimit(filter.Limit)

	cursorID, err := decodeCursor(filter.Cursor)
	if err != nil {
		return nil, err
	}

	var conditions []string
	var args []interface{}
	argNum := 1

	if filter.WorkspaceID != "" {
		conditions = append(conditions, fmt.Sprintf("workspace_id = $%d", argNum))
		args = append(args, filter.WorkspaceID)
		argNum++
	}
	if filter.EventType != "" {
		conditions = append(conditions, fmt.Sprintf("event_type = $%d", argNum))
		args = append(args, filter.EventType)
		argNum++
	}
	if filter.Category != "" {
		conditions = append(conditions, fmt.Sprintf("category = $%d", argNum))
		args = append(args, filter.Category)
		argNum++
	}
	if filter.Severity != "" {
		conditions = append(conditions, fmt.Sprintf("severity = $%d", argNum))
		args = append(args, filter.Severity)
		argNum++
	}
	if filter.ActorID != "" {
		conditions = append(conditions, fmt.Sprintf("actor_id = $%d", argNum))
		args = append(args, filter.ActorID)
		argNum++
	}
	if filter.ActorType != "" {
		conditions = append(conditions, fmt.Sprintf("actor_type = $%d", argNum))
		args = append(args, filter.ActorType)
		argNum++
	}
	if filter.ResourceID != "" {
		conditions = append(conditions, fmt.Sprintf("resource_id = $%d", argNum))
		args = append(args, filter.ResourceID)
		argNum++
	}
	if filter.ResourceType != "" {
		conditions = append(conditions, fmt.Sprintf("resource_type = $%d", argNum))
		args = append(args, filter.ResourceType)
		argNum++
	}
	if filter.Outcome != "" {
		conditions = append(conditions, fmt.Sprintf("outcome = $%d", argNum))
		args = append(args, filter.Outcome)
		argNum++
	}
	if filter.StartTime != nil {
		conditions = append(conditions, fmt.Sprintf("timestamp >= $%d", argNum))
		args = append(args, filter.StartTime)
		argNum++
	}
	if filter.EndTime != nil {
		conditions = append(conditions, fmt.Sprintf("timestamp <= $%d", argNum))
		args = append(args, filter.EndTime)
		argNum++
	}
	if cursorID != "" {
		conditions = append(conditions, fmt.Sprintf("id > $%d", argNum))
		args = append(args, cursorID)
		argNum++
	}

	whereClause := ""
	if len(conditions) > 0 {
		whereClause = "WHERE " + strings.Join(conditions, " AND ")
	}

	query := fmt.Sprintf(`
		SELECT id, event_type, category, severity, actor_id, actor_type,
			   action, resource_id, resource_type, workspace_id, outcome,
			   context, details, timestamp, received_at
		FROM audit_records
		%s
		ORDER BY id ASC
		LIMIT $%d
	`, whereClause, argNum)
	args = append(args, limit+1)

	rows, err := p.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to list audit records: %w", err)
	}
	defer func() { _ = rows.Close() }()

	var records []models.AuditRecord
	for rows.Next() {
		var record models.AuditRecord
		var contextJSON, detailsJSON []byte

		if err := rows.Scan(
			&record.ID,
			&record.EventType,
			&record.Category,
			&record.Severity,
			&record.ActorID,
			&record.ActorType,
			&record.Action,
			&record.ResourceID,
			&record.ResourceType,
			&record.WorkspaceID,
			&record.Outcome,
			&contextJSON,
			&detailsJSON,
			&record.Timestamp,
			&record.ReceivedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan audit record: %w", err)
		}

		if len(contextJSON) > 0 {
			if err := json.Unmarshal(contextJSON, &record.Context); err != nil {
				return nil, fmt.Errorf("failed to unmarshal context: %w", err)
			}
		}
		if len(detailsJSON) > 0 {
			if err := json.Unmarshal(detailsJSON, &record.Details); err != nil {
				return nil, fmt.Errorf("failed to unmarshal details: %w", err)
			}
		}

		records = append(records, record)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating audit records: %w", err)
	}

	hasNextPage := len(records) > limit
	if hasNextPage {
		records = records[:limit]
	}

	result := &models.AuditList{
		Records: records,
		PageInfo: models.PageInfo{
			HasNextPage: hasNextPage,
		},
	}

	if hasNextPage && len(records) > 0 {
		result.PageInfo.NextCursor = encodeCursor(records[len(records)-1].ID)
	}

	return result, nil
}

// Ensure Postgres implements the required interfaces at compile time.
var (
	_ health.Checker = (*Postgres)(nil)
)
