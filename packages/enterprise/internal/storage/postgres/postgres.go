// Package postgres implements PostgreSQL storage for the Fastband Enterprise control plane.
// It provides the PostgresStore interface implementation with connection pooling,
// health checking, and CRUD operations for domain models.
package postgres

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"

	// Import pgx driver for Postgres
	_ "github.com/jackc/pgx/v5/stdlib"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/health"
)

// ErrNotImplemented is returned when an operation is not yet implemented.
var ErrNotImplemented = errors.New("operation not implemented")

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
// Ticket Operations (Placeholder implementations)
// =============================================================================

// CreateTicket creates a new ticket in the database.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) CreateTicket(ctx context.Context, ticket interface{}) error {
	return ErrNotImplemented
}

// GetTicket retrieves a ticket by ID.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) GetTicket(ctx context.Context, id string) (interface{}, error) {
	return nil, ErrNotImplemented
}

// UpdateTicket updates an existing ticket.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) UpdateTicket(ctx context.Context, ticket interface{}) error {
	return ErrNotImplemented
}

// DeleteTicket deletes a ticket by ID.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) DeleteTicket(ctx context.Context, id string) error {
	return ErrNotImplemented
}

// ListTickets retrieves tickets matching the given filters.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) ListTickets(ctx context.Context, filters interface{}) ([]interface{}, error) {
	return nil, ErrNotImplemented
}

// =============================================================================
// Job Operations (Placeholder implementations)
// =============================================================================

// CreateJob creates a new job in the database.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) CreateJob(ctx context.Context, job interface{}) error {
	return ErrNotImplemented
}

// GetJob retrieves a job by ID.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) GetJob(ctx context.Context, id string) (interface{}, error) {
	return nil, ErrNotImplemented
}

// UpdateJob updates an existing job.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) UpdateJob(ctx context.Context, job interface{}) error {
	return ErrNotImplemented
}

// ListJobsByTicket retrieves all jobs for a ticket.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) ListJobsByTicket(ctx context.Context, ticketID string) ([]interface{}, error) {
	return nil, ErrNotImplemented
}

// =============================================================================
// Approval Operations (Placeholder implementations)
// =============================================================================

// CreateApproval creates a new approval request.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) CreateApproval(ctx context.Context, approval interface{}) error {
	return ErrNotImplemented
}

// GetApproval retrieves an approval by ID.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) GetApproval(ctx context.Context, id string) (interface{}, error) {
	return nil, ErrNotImplemented
}

// UpdateApproval updates an existing approval (e.g., to approve/reject).
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) UpdateApproval(ctx context.Context, approval interface{}) error {
	return ErrNotImplemented
}

// ListApprovalsByJob retrieves all approvals for a job.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) ListApprovalsByJob(ctx context.Context, jobID string) ([]interface{}, error) {
	return nil, ErrNotImplemented
}

// =============================================================================
// Audit Record Operations (Placeholder implementations)
// =============================================================================

// CreateAuditRecord creates a new audit record (append-only).
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) CreateAuditRecord(ctx context.Context, record interface{}) error {
	return ErrNotImplemented
}

// GetAuditRecord retrieves an audit record by ID.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) GetAuditRecord(ctx context.Context, id string) (interface{}, error) {
	return nil, ErrNotImplemented
}

// ListAuditRecords retrieves audit records matching the given filters.
// TODO: Implement in Task 3.3 expansion or later task.
func (p *Postgres) ListAuditRecords(ctx context.Context, filters interface{}) ([]interface{}, error) {
	return nil, ErrNotImplemented
}

// Ensure Postgres implements the required interfaces at compile time.
var (
	_ health.Checker = (*Postgres)(nil)
)
