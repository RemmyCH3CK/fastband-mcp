package postgres

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
)

func TestDefaultConfig(t *testing.T) {
	cfg := DefaultConfig()

	if cfg.Host != "localhost" {
		t.Errorf("Host = %s, want localhost", cfg.Host)
	}
	if cfg.Port != 5432 {
		t.Errorf("Port = %d, want 5432", cfg.Port)
	}
	if cfg.Database != "fastband" {
		t.Errorf("Database = %s, want fastband", cfg.Database)
	}
	if cfg.User != "postgres" {
		t.Errorf("User = %s, want postgres", cfg.User)
	}
	if cfg.SSLMode != "disable" {
		t.Errorf("SSLMode = %s, want disable", cfg.SSLMode)
	}
	if cfg.MaxOpenConns != 25 {
		t.Errorf("MaxOpenConns = %d, want 25", cfg.MaxOpenConns)
	}
	if cfg.MaxIdleConns != 5 {
		t.Errorf("MaxIdleConns = %d, want 5", cfg.MaxIdleConns)
	}
}

func TestConfig_DSN(t *testing.T) {
	cfg := Config{
		Host:           "db.example.com",
		Port:           5433,
		Database:       "testdb",
		User:           "testuser",
		Password:       "testpass",
		SSLMode:        "require",
		ConnectTimeout: 30 * time.Second,
	}

	dsn := cfg.DSN()

	expected := "host=db.example.com port=5433 dbname=testdb user=testuser password=testpass sslmode=require connect_timeout=30"
	if dsn != expected {
		t.Errorf("DSN() = %s, want %s", dsn, expected)
	}
}

func TestNewWithDB(t *testing.T) {
	db, _, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)

	if pg.db != db {
		t.Error("NewWithDB did not set the db correctly")
	}
	if pg.DB() != db {
		t.Error("DB() did not return the correct db")
	}
}

func TestPostgres_Ping_Success(t *testing.T) {
	db, mock, err := sqlmock.New(sqlmock.MonitorPingsOption(true))
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	mock.ExpectPing()

	pg := NewWithDB(db)

	ctx := context.Background()
	if err := pg.Ping(ctx); err != nil {
		t.Errorf("Ping() error = %v, want nil", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_Ping_Error(t *testing.T) {
	db, mock, err := sqlmock.New(sqlmock.MonitorPingsOption(true))
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pingErr := errors.New("connection refused")
	mock.ExpectPing().WillReturnError(pingErr)

	pg := NewWithDB(db)

	ctx := context.Background()
	if err := pg.Ping(ctx); err == nil {
		t.Error("Ping() error = nil, want error")
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_Ping_NilDB(t *testing.T) {
	pg := &Postgres{db: nil}

	ctx := context.Background()
	err := pg.Ping(ctx)
	if err == nil {
		t.Error("Ping() with nil db should return error")
	}
	if err.Error() != "database connection is nil" {
		t.Errorf("Ping() error = %v, want 'database connection is nil'", err)
	}
}

func TestPostgres_Close(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}

	mock.ExpectClose()

	pg := NewWithDB(db)

	if err := pg.Close(); err != nil {
		t.Errorf("Close() error = %v, want nil", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_Close_NilDB(t *testing.T) {
	pg := &Postgres{db: nil}

	if err := pg.Close(); err != nil {
		t.Errorf("Close() with nil db error = %v, want nil", err)
	}
}

func TestPostgres_Name(t *testing.T) {
	pg := &Postgres{}

	if name := pg.Name(); name != "database" {
		t.Errorf("Name() = %s, want 'database'", name)
	}
}

func TestPostgres_Check_Healthy(t *testing.T) {
	db, mock, err := sqlmock.New(sqlmock.MonitorPingsOption(true))
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	mock.ExpectPing()

	pg := NewWithDB(db)

	result := pg.Check()

	if result.Status != "healthy" {
		t.Errorf("Check().Status = %s, want 'healthy'", result.Status)
	}
	if result.Message == "" {
		t.Error("Check().Message should not be empty for healthy status")
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_Check_Unhealthy(t *testing.T) {
	db, mock, err := sqlmock.New(sqlmock.MonitorPingsOption(true))
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	mock.ExpectPing().WillReturnError(errors.New("connection lost"))

	pg := NewWithDB(db)

	result := pg.Check()

	if result.Status != "unhealthy" {
		t.Errorf("Check().Status = %s, want 'unhealthy'", result.Status)
	}
	if result.Message == "" {
		t.Error("Check().Message should contain error details")
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_PlaceholderMethods(t *testing.T) {
	db, _, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	// Test ticket operations return ErrNotImplemented
	if err := pg.CreateTicket(ctx, nil); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("CreateTicket() error = %v, want ErrNotImplemented", err)
	}
	if _, err := pg.GetTicket(ctx, ""); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("GetTicket() error = %v, want ErrNotImplemented", err)
	}
	if err := pg.UpdateTicket(ctx, nil); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("UpdateTicket() error = %v, want ErrNotImplemented", err)
	}
	if err := pg.DeleteTicket(ctx, ""); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("DeleteTicket() error = %v, want ErrNotImplemented", err)
	}
	if _, err := pg.ListTickets(ctx, nil); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("ListTickets() error = %v, want ErrNotImplemented", err)
	}

	// Test job operations return ErrNotImplemented
	if err := pg.CreateJob(ctx, nil); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("CreateJob() error = %v, want ErrNotImplemented", err)
	}
	if _, err := pg.GetJob(ctx, ""); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("GetJob() error = %v, want ErrNotImplemented", err)
	}
	if err := pg.UpdateJob(ctx, nil); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("UpdateJob() error = %v, want ErrNotImplemented", err)
	}
	if _, err := pg.ListJobsByTicket(ctx, ""); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("ListJobsByTicket() error = %v, want ErrNotImplemented", err)
	}

	// Test approval operations return ErrNotImplemented
	if err := pg.CreateApproval(ctx, nil); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("CreateApproval() error = %v, want ErrNotImplemented", err)
	}
	if _, err := pg.GetApproval(ctx, ""); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("GetApproval() error = %v, want ErrNotImplemented", err)
	}
	if err := pg.UpdateApproval(ctx, nil); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("UpdateApproval() error = %v, want ErrNotImplemented", err)
	}
	if _, err := pg.ListApprovalsByJob(ctx, ""); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("ListApprovalsByJob() error = %v, want ErrNotImplemented", err)
	}

	// Test audit record operations return ErrNotImplemented
	if err := pg.CreateAuditRecord(ctx, nil); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("CreateAuditRecord() error = %v, want ErrNotImplemented", err)
	}
	if _, err := pg.GetAuditRecord(ctx, ""); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("GetAuditRecord() error = %v, want ErrNotImplemented", err)
	}
	if _, err := pg.ListAuditRecords(ctx, nil); !errors.Is(err, ErrNotImplemented) {
		t.Errorf("ListAuditRecords() error = %v, want ErrNotImplemented", err)
	}
}

// TestPostgres_ImplementsChecker verifies that Postgres implements the health.Checker interface.
func TestPostgres_ImplementsChecker(t *testing.T) {
	db, _, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)

	// This test is a compile-time check enforced by the var _ declaration in postgres.go,
	// but we can also verify it at runtime.
	// Verify the interface methods are callable and return expected types
	name := pg.Name()
	if name != "database" {
		t.Errorf("Name() = %s, want 'database'", name)
	}
	result := pg.Check()
	if result.Status == "" {
		t.Error("Check() should return a result with a status")
	}
}

// TestNew_InvalidConnection tests that New returns an error for invalid connections.
// Note: This test requires mocking at the driver level, which is complex.
// In production, integration tests with a real database would cover this.
func TestNew_InvalidConnection(t *testing.T) {
	// Skip this test as it requires a real database or driver-level mocking
	t.Skip("Skipping: requires integration test with real database")

	ctx := context.Background()
	cfg := Config{
		Host:           "invalid-host-that-does-not-exist",
		Port:           5432,
		Database:       "testdb",
		User:           "testuser",
		Password:       "testpass",
		SSLMode:        "disable",
		ConnectTimeout: 1 * time.Second,
	}

	_, err := New(ctx, cfg)
	if err == nil {
		t.Error("New() with invalid host should return error")
	}
}
