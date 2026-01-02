package postgres

import (
	"context"
	"database/sql"
	"encoding/base64"
	"errors"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/lib/pq"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/models"
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

// =============================================================================
// Cursor Helper Tests
// =============================================================================

func TestEncodeCursor(t *testing.T) {
	id := "test-id-123"
	cursor := encodeCursor(id)
	expected := base64.StdEncoding.EncodeToString([]byte(id))
	if cursor != expected {
		t.Errorf("encodeCursor() = %s, want %s", cursor, expected)
	}
}

func TestDecodeCursor(t *testing.T) {
	tests := []struct {
		name    string
		cursor  string
		want    string
		wantErr bool
	}{
		{
			name:    "empty cursor",
			cursor:  "",
			want:    "",
			wantErr: false,
		},
		{
			name:    "valid cursor",
			cursor:  base64.StdEncoding.EncodeToString([]byte("test-id")),
			want:    "test-id",
			wantErr: false,
		},
		{
			name:    "invalid cursor",
			cursor:  "not-base64!!!",
			want:    "",
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := decodeCursor(tt.cursor)
			if (err != nil) != tt.wantErr {
				t.Errorf("decodeCursor() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if got != tt.want {
				t.Errorf("decodeCursor() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNormalizeLimit(t *testing.T) {
	tests := []struct {
		input int
		want  int
	}{
		{0, models.DefaultPageLimit},
		{-1, models.DefaultPageLimit},
		{10, 10},
		{50, 50},
		{100, 100},
		{101, models.MaxPageLimit},
		{1000, models.MaxPageLimit},
	}

	for _, tt := range tests {
		got := normalizeLimit(tt.input)
		if got != tt.want {
			t.Errorf("normalizeLimit(%d) = %d, want %d", tt.input, got, tt.want)
		}
	}
}

// =============================================================================
// Ticket Repository Tests
// =============================================================================

func TestPostgres_CreateTicket(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()
	ticket := &models.Ticket{
		ID:          "ticket-123",
		WorkspaceID: "ws-456",
		Title:       "Test Ticket",
		Description: "Test Description",
		Status:      models.TicketStatusOpen,
		Priority:    models.TicketPriorityHigh,
		Labels:      models.StringArray{"bug", "urgent"},
		CreatedBy:   "user-789",
		CreatedAt:   now,
		UpdatedAt:   now,
		Metadata:    models.JSONB{"key": "value"},
	}

	mock.ExpectExec("INSERT INTO tickets").
		WithArgs(
			ticket.ID,
			ticket.WorkspaceID,
			ticket.Title,
			ticket.Description,
			ticket.Status,
			ticket.Priority,
			pq.Array(ticket.Labels),
			nil, // assignedTo
			ticket.CreatedBy,
			ticket.CreatedAt,
			ticket.UpdatedAt,
			sqlmock.AnyArg(), // metadata JSON
		).
		WillReturnResult(sqlmock.NewResult(1, 1))

	err = pg.CreateTicket(ctx, ticket)
	if err != nil {
		t.Errorf("CreateTicket() error = %v, want nil", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_CreateTicket_NilTicket(t *testing.T) {
	db, _, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	err = pg.CreateTicket(ctx, nil)
	if err == nil {
		t.Error("CreateTicket(nil) should return error")
	}
}

func TestPostgres_GetTicket(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()
	ticketID := "ticket-123"

	// Use []byte format for Postgres array - this is what pq.Array expects
	rows := sqlmock.NewRows([]string{
		"id", "workspace_id", "title", "description", "status", "priority",
		"labels", "assigned_to", "created_by", "created_at", "updated_at", "metadata",
	}).AddRow(
		ticketID,
		"ws-456",
		"Test Ticket",
		"Test Description",
		"open",
		"high",
		[]byte(`{bug,urgent}`), // Postgres array as bytes
		nil,
		"user-789",
		now,
		now,
		[]byte(`{"key": "value"}`),
	)

	mock.ExpectQuery("SELECT (.+) FROM tickets WHERE id = \\$1").
		WithArgs(ticketID).
		WillReturnRows(rows)

	ticket, err := pg.GetTicket(ctx, ticketID)
	if err != nil {
		t.Errorf("GetTicket() error = %v, want nil", err)
	}

	if ticket.ID != ticketID {
		t.Errorf("ticket.ID = %s, want %s", ticket.ID, ticketID)
	}
	if ticket.Status != models.TicketStatusOpen {
		t.Errorf("ticket.Status = %s, want %s", ticket.Status, models.TicketStatusOpen)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_GetTicket_NotFound(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	mock.ExpectQuery("SELECT (.+) FROM tickets WHERE id = \\$1").
		WithArgs("nonexistent").
		WillReturnError(sql.ErrNoRows)

	_, err = pg.GetTicket(ctx, "nonexistent")
	if !errors.Is(err, ErrNotFound) {
		t.Errorf("GetTicket() error = %v, want ErrNotFound", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_UpdateTicket(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	ticket := &models.Ticket{
		ID:          "ticket-123",
		Title:       "Updated Title",
		Description: "Updated Description",
		Status:      models.TicketStatusInProgress,
		Priority:    models.TicketPriorityCritical,
		Labels:      models.StringArray{"updated"},
		Metadata:    models.JSONB{"updated": true},
	}

	mock.ExpectExec("UPDATE tickets SET").
		WithArgs(
			ticket.ID,
			ticket.Title,
			ticket.Description,
			ticket.Status,
			ticket.Priority,
			pq.Array(ticket.Labels),
			nil, // assignedTo
			sqlmock.AnyArg(), // metadata JSON
		).
		WillReturnResult(sqlmock.NewResult(0, 1))

	err = pg.UpdateTicket(ctx, ticket)
	if err != nil {
		t.Errorf("UpdateTicket() error = %v, want nil", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_UpdateTicket_NotFound(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	ticket := &models.Ticket{
		ID:     "nonexistent",
		Title:  "Title",
		Status: models.TicketStatusOpen,
	}

	mock.ExpectExec("UPDATE tickets SET").
		WithArgs(sqlmock.AnyArg(), sqlmock.AnyArg(), sqlmock.AnyArg(), sqlmock.AnyArg(), sqlmock.AnyArg(), sqlmock.AnyArg(), sqlmock.AnyArg(), sqlmock.AnyArg()).
		WillReturnResult(sqlmock.NewResult(0, 0))

	err = pg.UpdateTicket(ctx, ticket)
	if !errors.Is(err, ErrNotFound) {
		t.Errorf("UpdateTicket() error = %v, want ErrNotFound", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_DeleteTicket(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	mock.ExpectExec("DELETE FROM tickets WHERE id = \\$1").
		WithArgs("ticket-123").
		WillReturnResult(sqlmock.NewResult(0, 1))

	err = pg.DeleteTicket(ctx, "ticket-123")
	if err != nil {
		t.Errorf("DeleteTicket() error = %v, want nil", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_DeleteTicket_NotFound(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	mock.ExpectExec("DELETE FROM tickets WHERE id = \\$1").
		WithArgs("nonexistent").
		WillReturnResult(sqlmock.NewResult(0, 0))

	err = pg.DeleteTicket(ctx, "nonexistent")
	if !errors.Is(err, ErrNotFound) {
		t.Errorf("DeleteTicket() error = %v, want ErrNotFound", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_ListTickets(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()

	rows := sqlmock.NewRows([]string{
		"id", "workspace_id", "title", "description", "status", "priority",
		"labels", "assigned_to", "created_by", "created_at", "updated_at", "metadata",
	}).
		AddRow("ticket-1", "ws-1", "Ticket 1", "Desc 1", "open", "high",
			[]byte(`{bug}`), nil, "user-1", now, now, []byte(`{}`)).
		AddRow("ticket-2", "ws-1", "Ticket 2", "Desc 2", "open", "medium",
			[]byte(`{feature}`), nil, "user-2", now, now, []byte(`{}`))

	mock.ExpectQuery("SELECT (.+) FROM tickets").
		WithArgs("ws-1", sqlmock.AnyArg()).
		WillReturnRows(rows)

	filter := models.TicketFilter{
		WorkspaceID: "ws-1",
		Limit:       10,
	}

	result, err := pg.ListTickets(ctx, filter)
	if err != nil {
		t.Errorf("ListTickets() error = %v, want nil", err)
	}

	if len(result.Tickets) != 2 {
		t.Errorf("len(tickets) = %d, want 2", len(result.Tickets))
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_ListTickets_WithPagination(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()

	// Return 3 rows when limit is 2 (to indicate hasNextPage)
	rows := sqlmock.NewRows([]string{
		"id", "workspace_id", "title", "description", "status", "priority",
		"labels", "assigned_to", "created_by", "created_at", "updated_at", "metadata",
	}).
		AddRow("ticket-1", "ws-1", "Ticket 1", "Desc 1", "open", "high",
			[]byte(`{}`), nil, "user-1", now, now, []byte(`{}`)).
		AddRow("ticket-2", "ws-1", "Ticket 2", "Desc 2", "open", "medium",
			[]byte(`{}`), nil, "user-2", now, now, []byte(`{}`)).
		AddRow("ticket-3", "ws-1", "Ticket 3", "Desc 3", "open", "low",
			[]byte(`{}`), nil, "user-3", now, now, []byte(`{}`))

	mock.ExpectQuery("SELECT (.+) FROM tickets").
		WithArgs(sqlmock.AnyArg()).
		WillReturnRows(rows)

	filter := models.TicketFilter{
		Limit: 2,
	}

	result, err := pg.ListTickets(ctx, filter)
	if err != nil {
		t.Errorf("ListTickets() error = %v, want nil", err)
	}

	if len(result.Tickets) != 2 {
		t.Errorf("len(tickets) = %d, want 2", len(result.Tickets))
	}
	if !result.PageInfo.HasNextPage {
		t.Error("PageInfo.HasNextPage = false, want true")
	}
	if result.PageInfo.NextCursor == "" {
		t.Error("PageInfo.NextCursor should not be empty")
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_ListTickets_InvalidCursor(t *testing.T) {
	db, _, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	filter := models.TicketFilter{
		Cursor: "invalid-base64!!!",
	}

	_, err = pg.ListTickets(ctx, filter)
	if !errors.Is(err, ErrInvalidCursor) {
		t.Errorf("ListTickets() error = %v, want ErrInvalidCursor", err)
	}
}

// =============================================================================
// Job Repository Tests
// =============================================================================

func TestPostgres_CreateJob(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()
	job := &models.Job{
		ID:        "job-123",
		TicketID:  "ticket-456",
		Status:    models.JobStatusQueued,
		CreatedAt: now,
		Context:   models.JSONB{"input": "data"},
		Result:    models.JSONB{},
	}

	mock.ExpectExec("INSERT INTO jobs").
		WithArgs(
			job.ID,
			job.TicketID,
			job.Status,
			nil, // executionNode
			sqlmock.AnyArg(), // context JSON
			job.CreatedAt,
			nil, // startedAt
			nil, // completedAt
			sqlmock.AnyArg(), // result JSON
		).
		WillReturnResult(sqlmock.NewResult(1, 1))

	err = pg.CreateJob(ctx, job)
	if err != nil {
		t.Errorf("CreateJob() error = %v, want nil", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_GetJob(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()
	jobID := "job-123"

	rows := sqlmock.NewRows([]string{
		"id", "ticket_id", "status", "execution_node", "context",
		"created_at", "started_at", "completed_at", "result",
	}).AddRow(
		jobID,
		"ticket-456",
		"running",
		"node-1",
		[]byte(`{"input": "data"}`),
		now,
		now,
		nil,
		[]byte(`{}`),
	)

	mock.ExpectQuery("SELECT (.+) FROM jobs WHERE id = \\$1").
		WithArgs(jobID).
		WillReturnRows(rows)

	job, err := pg.GetJob(ctx, jobID)
	if err != nil {
		t.Errorf("GetJob() error = %v, want nil", err)
	}

	if job.ID != jobID {
		t.Errorf("job.ID = %s, want %s", job.ID, jobID)
	}
	if job.Status != models.JobStatusRunning {
		t.Errorf("job.Status = %s, want %s", job.Status, models.JobStatusRunning)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_GetJob_NotFound(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	mock.ExpectQuery("SELECT (.+) FROM jobs WHERE id = \\$1").
		WithArgs("nonexistent").
		WillReturnError(sql.ErrNoRows)

	_, err = pg.GetJob(ctx, "nonexistent")
	if !errors.Is(err, ErrNotFound) {
		t.Errorf("GetJob() error = %v, want ErrNotFound", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_UpdateJob(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()
	job := &models.Job{
		ID:        "job-123",
		Status:    models.JobStatusCompleted,
		StartedAt: sql.NullTime{Time: now, Valid: true},
		Context:   models.JSONB{},
		Result:    models.JSONB{"output": "success"},
	}

	mock.ExpectExec("UPDATE jobs SET").
		WithArgs(
			job.ID,
			job.Status,
			nil, // executionNode
			sqlmock.AnyArg(), // context JSON
			sqlmock.AnyArg(), // startedAt
			nil, // completedAt
			sqlmock.AnyArg(), // result JSON
		).
		WillReturnResult(sqlmock.NewResult(0, 1))

	err = pg.UpdateJob(ctx, job)
	if err != nil {
		t.Errorf("UpdateJob() error = %v, want nil", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_ListJobs(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()

	rows := sqlmock.NewRows([]string{
		"id", "ticket_id", "status", "execution_node", "context",
		"created_at", "started_at", "completed_at", "result",
	}).
		AddRow("job-1", "ticket-1", "queued", nil, []byte(`{}`), now, nil, nil, []byte(`{}`)).
		AddRow("job-2", "ticket-1", "running", "node-1", []byte(`{}`), now, now, nil, []byte(`{}`))

	mock.ExpectQuery("SELECT (.+) FROM jobs").
		WithArgs("ticket-1", sqlmock.AnyArg()).
		WillReturnRows(rows)

	filter := models.JobFilter{
		TicketID: "ticket-1",
		Limit:    10,
	}

	result, err := pg.ListJobs(ctx, filter)
	if err != nil {
		t.Errorf("ListJobs() error = %v, want nil", err)
	}

	if len(result.Jobs) != 2 {
		t.Errorf("len(jobs) = %d, want 2", len(result.Jobs))
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

// =============================================================================
// Approval Repository Tests
// =============================================================================

func TestPostgres_CreateApproval(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()
	approval := &models.Approval{
		ID:          "approval-123",
		JobID:       "job-456",
		ToolCallID:  "tool-call-789",
		Tool:        "file_write",
		Resource:    "/path/to/file",
		Status:      models.ApprovalStatusPending,
		RequestedBy: "user-1",
		RequestedAt: now,
		Conditions:  models.JSONB{},
	}

	mock.ExpectExec("INSERT INTO approvals").
		WithArgs(
			approval.ID,
			approval.JobID,
			approval.ToolCallID,
			approval.Tool,
			approval.Resource,
			approval.Status,
			approval.RequestedBy,
			approval.RequestedAt,
			nil, // decidedBy
			nil, // decidedAt
			nil, // comment
			sqlmock.AnyArg(), // conditions JSON
		).
		WillReturnResult(sqlmock.NewResult(1, 1))

	err = pg.CreateApproval(ctx, approval)
	if err != nil {
		t.Errorf("CreateApproval() error = %v, want nil", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_GetApproval(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()
	approvalID := "approval-123"

	rows := sqlmock.NewRows([]string{
		"id", "job_id", "tool_call_id", "tool", "resource", "status",
		"requested_by", "requested_at", "decided_by", "decided_at", "comment", "conditions",
	}).AddRow(
		approvalID,
		"job-456",
		"tool-call-789",
		"file_write",
		"/path/to/file",
		"pending",
		"user-1",
		now,
		nil,
		nil,
		nil,
		[]byte(`{}`),
	)

	mock.ExpectQuery("SELECT (.+) FROM approvals WHERE id = \\$1").
		WithArgs(approvalID).
		WillReturnRows(rows)

	approval, err := pg.GetApproval(ctx, approvalID)
	if err != nil {
		t.Errorf("GetApproval() error = %v, want nil", err)
	}

	if approval.ID != approvalID {
		t.Errorf("approval.ID = %s, want %s", approval.ID, approvalID)
	}
	if approval.Status != models.ApprovalStatusPending {
		t.Errorf("approval.Status = %s, want %s", approval.Status, models.ApprovalStatusPending)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_UpdateApproval(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()
	approval := &models.Approval{
		ID:        "approval-123",
		Status:    models.ApprovalStatusApproved,
		DecidedBy: sql.NullString{String: "admin-1", Valid: true},
		DecidedAt: sql.NullTime{Time: now, Valid: true},
		Comment:   sql.NullString{String: "Approved for deployment", Valid: true},
	}

	mock.ExpectExec("UPDATE approvals SET").
		WithArgs(
			approval.ID,
			approval.Status,
			sqlmock.AnyArg(), // decidedBy
			sqlmock.AnyArg(), // decidedAt
			sqlmock.AnyArg(), // comment
			sqlmock.AnyArg(), // conditions JSON
		).
		WillReturnResult(sqlmock.NewResult(0, 1))

	err = pg.UpdateApproval(ctx, approval)
	if err != nil {
		t.Errorf("UpdateApproval() error = %v, want nil", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_ListApprovals(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()

	rows := sqlmock.NewRows([]string{
		"id", "job_id", "tool_call_id", "tool", "resource", "status",
		"requested_by", "requested_at", "decided_by", "decided_at", "comment", "conditions",
	}).
		AddRow("approval-1", "job-1", "tc-1", "bash", "/bin/ls", "pending",
			"user-1", now, nil, nil, nil, []byte(`{}`)).
		AddRow("approval-2", "job-1", "tc-2", "file_read", "/etc/passwd", "approved",
			"user-1", now, "admin-1", now, "OK", []byte(`{}`))

	mock.ExpectQuery("SELECT (.+) FROM approvals").
		WithArgs("pending", sqlmock.AnyArg()).
		WillReturnRows(rows)

	filter := models.ApprovalFilter{
		Status: models.ApprovalStatusPending,
		Limit:  10,
	}

	result, err := pg.ListApprovals(ctx, filter)
	if err != nil {
		t.Errorf("ListApprovals() error = %v, want nil", err)
	}

	if len(result.Approvals) != 2 {
		t.Errorf("len(approvals) = %d, want 2", len(result.Approvals))
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

// =============================================================================
// Audit Record Repository Tests
// =============================================================================

func TestPostgres_CreateAuditRecord(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()
	record := &models.AuditRecord{
		ID:           "audit-123",
		EventType:    "ticket.created",
		Category:     models.EventCategoryOperational,
		Severity:     models.EventSeverityInfo,
		ActorID:      "user-456",
		ActorType:    models.ActorTypeUser,
		Action:       "create",
		ResourceID:   "ticket-789",
		ResourceType: "ticket",
		WorkspaceID:  "ws-1",
		Outcome:      models.EventOutcomeSuccess,
		Context:      models.JSONB{},
		Details:      models.JSONB{"title": "New Ticket"},
		Timestamp:    now,
		ReceivedAt:   now,
	}

	mock.ExpectExec("INSERT INTO audit_records").
		WithArgs(
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
			sqlmock.AnyArg(), // context JSON
			sqlmock.AnyArg(), // details JSON
			record.Timestamp,
			record.ReceivedAt,
		).
		WillReturnResult(sqlmock.NewResult(1, 1))

	err = pg.CreateAuditRecord(ctx, record)
	if err != nil {
		t.Errorf("CreateAuditRecord() error = %v, want nil", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_GetAuditRecord(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()
	recordID := "audit-123"

	rows := sqlmock.NewRows([]string{
		"id", "event_type", "category", "severity", "actor_id", "actor_type",
		"action", "resource_id", "resource_type", "workspace_id", "outcome",
		"context", "details", "timestamp", "received_at",
	}).AddRow(
		recordID,
		"ticket.created",
		"operational",
		"info",
		"user-456",
		"user",
		"create",
		"ticket-789",
		"ticket",
		"ws-1",
		"success",
		[]byte(`{}`),
		[]byte(`{"title": "New Ticket"}`),
		now,
		now,
	)

	mock.ExpectQuery("SELECT (.+) FROM audit_records WHERE id = \\$1").
		WithArgs(recordID).
		WillReturnRows(rows)

	record, err := pg.GetAuditRecord(ctx, recordID)
	if err != nil {
		t.Errorf("GetAuditRecord() error = %v, want nil", err)
	}

	if record.ID != recordID {
		t.Errorf("record.ID = %s, want %s", record.ID, recordID)
	}
	if record.Category != models.EventCategoryOperational {
		t.Errorf("record.Category = %s, want %s", record.Category, models.EventCategoryOperational)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_GetAuditRecord_NotFound(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	mock.ExpectQuery("SELECT (.+) FROM audit_records WHERE id = \\$1").
		WithArgs("nonexistent").
		WillReturnError(sql.ErrNoRows)

	_, err = pg.GetAuditRecord(ctx, "nonexistent")
	if !errors.Is(err, ErrNotFound) {
		t.Errorf("GetAuditRecord() error = %v, want ErrNotFound", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_ListAuditRecords(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()

	rows := sqlmock.NewRows([]string{
		"id", "event_type", "category", "severity", "actor_id", "actor_type",
		"action", "resource_id", "resource_type", "workspace_id", "outcome",
		"context", "details", "timestamp", "received_at",
	}).
		AddRow("audit-1", "ticket.created", "operational", "info", "user-1", "user",
			"create", "ticket-1", "ticket", "ws-1", "success", []byte(`{}`), []byte(`{}`), now, now).
		AddRow("audit-2", "ticket.updated", "operational", "info", "user-1", "user",
			"update", "ticket-1", "ticket", "ws-1", "success", []byte(`{}`), []byte(`{}`), now, now)

	mock.ExpectQuery("SELECT (.+) FROM audit_records").
		WithArgs("ws-1", sqlmock.AnyArg()).
		WillReturnRows(rows)

	filter := models.AuditFilter{
		WorkspaceID: "ws-1",
		Limit:       10,
	}

	result, err := pg.ListAuditRecords(ctx, filter)
	if err != nil {
		t.Errorf("ListAuditRecords() error = %v, want nil", err)
	}

	if len(result.Records) != 2 {
		t.Errorf("len(records) = %d, want 2", len(result.Records))
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestPostgres_ListAuditRecords_WithTimeRange(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock: %v", err)
	}
	defer func() { _ = db.Close() }()

	pg := NewWithDB(db)
	ctx := context.Background()

	now := time.Now().UTC()
	startTime := now.Add(-24 * time.Hour)
	endTime := now

	rows := sqlmock.NewRows([]string{
		"id", "event_type", "category", "severity", "actor_id", "actor_type",
		"action", "resource_id", "resource_type", "workspace_id", "outcome",
		"context", "details", "timestamp", "received_at",
	}).
		AddRow("audit-1", "ticket.created", "operational", "info", "user-1", "user",
			"create", "ticket-1", "ticket", "ws-1", "success", []byte(`{}`), []byte(`{}`), now, now)

	mock.ExpectQuery("SELECT (.+) FROM audit_records").
		WithArgs(sqlmock.AnyArg(), sqlmock.AnyArg(), sqlmock.AnyArg()).
		WillReturnRows(rows)

	filter := models.AuditFilter{
		StartTime: &startTime,
		EndTime:   &endTime,
		Limit:     10,
	}

	result, err := pg.ListAuditRecords(ctx, filter)
	if err != nil {
		t.Errorf("ListAuditRecords() error = %v, want nil", err)
	}

	if len(result.Records) != 1 {
		t.Errorf("len(records) = %d, want 1", len(result.Records))
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
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
