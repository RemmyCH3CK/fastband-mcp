//go:build integration

package postgres

import (
	"context"
	"database/sql"
	"os"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/models"
)

// getTestDSN returns the DSN from environment or a default for local testing.
func getTestDSN() string {
	if dsn := os.Getenv("TEST_POSTGRES_DSN"); dsn != "" {
		return dsn
	}
	// Default for local docker-compose setup
	return "host=localhost port=5432 dbname=fastband_test user=postgres password=postgres sslmode=disable"
}

func setupTestDB(t *testing.T) *Postgres {
	t.Helper()

	ctx := context.Background()
	cfg := DefaultConfig()
	cfg.Database = "fastband_test"
	cfg.Password = "postgres"

	// Allow override from environment
	if dsn := os.Getenv("TEST_POSTGRES_DSN"); dsn != "" {
		// Parse DSN and set config fields as needed
		db, err := sql.Open("pgx", dsn)
		if err != nil {
			t.Fatalf("Failed to open database: %v", err)
		}
		if err := db.PingContext(ctx); err != nil {
			t.Fatalf("Failed to ping database: %v", err)
		}
		return NewWithDB(db)
	}

	pg, err := New(ctx, cfg)
	if err != nil {
		t.Skipf("Skipping integration test: %v", err)
	}

	return pg
}

// TestIntegration_TicketCRUD tests the full CRUD lifecycle for tickets.
func TestIntegration_TicketCRUD(t *testing.T) {
	pg := setupTestDB(t)
	defer func() { _ = pg.Close() }()

	ctx := context.Background()
	now := time.Now().UTC().Truncate(time.Microsecond)

	// Create a ticket
	ticketID := uuid.New().String()
	ticket := &models.Ticket{
		ID:          ticketID,
		WorkspaceID: "ws-integration-test",
		Title:       "Integration Test Ticket",
		Description: "Testing CRUD operations",
		Status:      models.TicketStatusOpen,
		Priority:    models.TicketPriorityHigh,
		Labels:      models.StringArray{"integration", "test"},
		CreatedBy:   "test-user",
		CreatedAt:   now,
		UpdatedAt:   now,
		Metadata:    models.JSONB{"test": true},
	}

	// Create
	err := pg.CreateTicket(ctx, ticket)
	if err != nil {
		t.Fatalf("CreateTicket failed: %v", err)
	}

	// Read
	retrieved, err := pg.GetTicket(ctx, ticketID)
	if err != nil {
		t.Fatalf("GetTicket failed: %v", err)
	}

	if retrieved.ID != ticket.ID {
		t.Errorf("ID mismatch: got %s, want %s", retrieved.ID, ticket.ID)
	}
	if retrieved.Title != ticket.Title {
		t.Errorf("Title mismatch: got %s, want %s", retrieved.Title, ticket.Title)
	}
	if retrieved.Status != ticket.Status {
		t.Errorf("Status mismatch: got %s, want %s", retrieved.Status, ticket.Status)
	}
	if len(retrieved.Labels) != 2 {
		t.Errorf("Labels count mismatch: got %d, want 2", len(retrieved.Labels))
	}

	// Update
	retrieved.Status = models.TicketStatusInProgress
	retrieved.Title = "Updated Integration Test Ticket"
	err = pg.UpdateTicket(ctx, retrieved)
	if err != nil {
		t.Fatalf("UpdateTicket failed: %v", err)
	}

	// Verify update
	updated, err := pg.GetTicket(ctx, ticketID)
	if err != nil {
		t.Fatalf("GetTicket after update failed: %v", err)
	}
	if updated.Status != models.TicketStatusInProgress {
		t.Errorf("Status not updated: got %s, want %s", updated.Status, models.TicketStatusInProgress)
	}
	if updated.Title != "Updated Integration Test Ticket" {
		t.Errorf("Title not updated: got %s", updated.Title)
	}

	// List with filter
	list, err := pg.ListTickets(ctx, models.TicketFilter{
		WorkspaceID: "ws-integration-test",
		Limit:       10,
	})
	if err != nil {
		t.Fatalf("ListTickets failed: %v", err)
	}
	if len(list.Tickets) == 0 {
		t.Error("ListTickets returned no tickets")
	}

	// Delete
	err = pg.DeleteTicket(ctx, ticketID)
	if err != nil {
		t.Fatalf("DeleteTicket failed: %v", err)
	}

	// Verify delete
	_, err = pg.GetTicket(ctx, ticketID)
	if err != ErrNotFound {
		t.Errorf("Expected ErrNotFound after delete, got: %v", err)
	}
}

// TestIntegration_JobCRUD tests the full CRUD lifecycle for jobs.
func TestIntegration_JobCRUD(t *testing.T) {
	pg := setupTestDB(t)
	defer func() { _ = pg.Close() }()

	ctx := context.Background()
	now := time.Now().UTC().Truncate(time.Microsecond)

	// First create a ticket (jobs need a valid ticket_id due to FK)
	ticketID := uuid.New().String()
	ticket := &models.Ticket{
		ID:          ticketID,
		WorkspaceID: "ws-integration-test",
		Title:       "Ticket for Job Test",
		Description: "Testing job operations",
		Status:      models.TicketStatusOpen,
		Priority:    models.TicketPriorityMedium,
		Labels:      models.StringArray{},
		CreatedBy:   "test-user",
		CreatedAt:   now,
		UpdatedAt:   now,
		Metadata:    models.JSONB{},
	}
	if err := pg.CreateTicket(ctx, ticket); err != nil {
		t.Fatalf("CreateTicket for job test failed: %v", err)
	}
	defer func() { _ = pg.DeleteTicket(ctx, ticketID) }()

	// Create a job
	jobID := uuid.New().String()
	job := &models.Job{
		ID:        jobID,
		TicketID:  ticketID,
		Status:    models.JobStatusQueued,
		CreatedAt: now,
		Context:   models.JSONB{"input": "test data"},
		Result:    models.JSONB{},
	}

	err := pg.CreateJob(ctx, job)
	if err != nil {
		t.Fatalf("CreateJob failed: %v", err)
	}

	// Read
	retrieved, err := pg.GetJob(ctx, jobID)
	if err != nil {
		t.Fatalf("GetJob failed: %v", err)
	}
	if retrieved.ID != jobID {
		t.Errorf("ID mismatch: got %s, want %s", retrieved.ID, jobID)
	}
	if retrieved.Status != models.JobStatusQueued {
		t.Errorf("Status mismatch: got %s, want %s", retrieved.Status, models.JobStatusQueued)
	}

	// Update
	retrieved.Status = models.JobStatusRunning
	retrieved.StartedAt = sql.NullTime{Time: now, Valid: true}
	err = pg.UpdateJob(ctx, retrieved)
	if err != nil {
		t.Fatalf("UpdateJob failed: %v", err)
	}

	// Verify update
	updated, err := pg.GetJob(ctx, jobID)
	if err != nil {
		t.Fatalf("GetJob after update failed: %v", err)
	}
	if updated.Status != models.JobStatusRunning {
		t.Errorf("Status not updated: got %s, want %s", updated.Status, models.JobStatusRunning)
	}

	// List
	list, err := pg.ListJobs(ctx, models.JobFilter{
		TicketID: ticketID,
		Limit:    10,
	})
	if err != nil {
		t.Fatalf("ListJobs failed: %v", err)
	}
	if len(list.Jobs) == 0 {
		t.Error("ListJobs returned no jobs")
	}
}

// TestIntegration_AuditRecordAppendOnly tests audit record creation and verifies
// it's append-only (no update/delete at application level).
func TestIntegration_AuditRecordAppendOnly(t *testing.T) {
	pg := setupTestDB(t)
	defer func() { _ = pg.Close() }()

	ctx := context.Background()
	now := time.Now().UTC().Truncate(time.Microsecond)

	// Create an audit record
	recordID := uuid.New().String()
	record := &models.AuditRecord{
		ID:           recordID,
		EventType:    "integration.test",
		Category:     models.EventCategoryOperational,
		Severity:     models.EventSeverityInfo,
		ActorID:      "test-actor",
		ActorType:    models.ActorTypeUser,
		Action:       "test.action",
		ResourceID:   "test-resource",
		ResourceType: "test",
		WorkspaceID:  "ws-integration-test",
		Outcome:      models.EventOutcomeSuccess,
		Context:      models.JSONB{},
		Details:      models.JSONB{"integration": true},
		Timestamp:    now,
		ReceivedAt:   now,
	}

	err := pg.CreateAuditRecord(ctx, record)
	if err != nil {
		t.Fatalf("CreateAuditRecord failed: %v", err)
	}

	// Read
	retrieved, err := pg.GetAuditRecord(ctx, recordID)
	if err != nil {
		t.Fatalf("GetAuditRecord failed: %v", err)
	}
	if retrieved.ID != recordID {
		t.Errorf("ID mismatch: got %s, want %s", retrieved.ID, recordID)
	}
	if retrieved.EventType != "integration.test" {
		t.Errorf("EventType mismatch: got %s, want integration.test", retrieved.EventType)
	}

	// List with filters
	list, err := pg.ListAuditRecords(ctx, models.AuditFilter{
		WorkspaceID: "ws-integration-test",
		Category:    models.EventCategoryOperational,
		Limit:       10,
	})
	if err != nil {
		t.Fatalf("ListAuditRecords failed: %v", err)
	}
	if len(list.Records) == 0 {
		t.Error("ListAuditRecords returned no records")
	}

	// Note: We don't test Update/Delete for audit records because:
	// 1. There are no UpdateAuditRecord/DeleteAuditRecord methods (by design)
	// 2. The database has triggers that prevent UPDATE/DELETE operations
}

// TestIntegration_Pagination tests cursor-based pagination.
func TestIntegration_Pagination(t *testing.T) {
	pg := setupTestDB(t)
	defer func() { _ = pg.Close() }()

	ctx := context.Background()
	now := time.Now().UTC().Truncate(time.Microsecond)

	// Create multiple tickets
	workspaceID := "ws-pagination-test-" + uuid.New().String()[:8]
	var ticketIDs []string

	for i := 0; i < 5; i++ {
		ticketID := uuid.New().String()
		ticketIDs = append(ticketIDs, ticketID)

		ticket := &models.Ticket{
			ID:          ticketID,
			WorkspaceID: workspaceID,
			Title:       "Pagination Test Ticket",
			Description: "Testing pagination",
			Status:      models.TicketStatusOpen,
			Priority:    models.TicketPriorityMedium,
			Labels:      models.StringArray{},
			CreatedBy:   "test-user",
			CreatedAt:   now,
			UpdatedAt:   now,
			Metadata:    models.JSONB{},
		}
		if err := pg.CreateTicket(ctx, ticket); err != nil {
			t.Fatalf("CreateTicket %d failed: %v", i, err)
		}
	}

	// Cleanup
	defer func() {
		for _, id := range ticketIDs {
			_ = pg.DeleteTicket(ctx, id)
		}
	}()

	// First page
	page1, err := pg.ListTickets(ctx, models.TicketFilter{
		WorkspaceID: workspaceID,
		Limit:       2,
	})
	if err != nil {
		t.Fatalf("ListTickets page 1 failed: %v", err)
	}
	if len(page1.Tickets) != 2 {
		t.Errorf("Page 1 count: got %d, want 2", len(page1.Tickets))
	}
	if !page1.PageInfo.HasNextPage {
		t.Error("Page 1 should have next page")
	}
	if page1.PageInfo.NextCursor == "" {
		t.Error("Page 1 should have next cursor")
	}

	// Second page
	page2, err := pg.ListTickets(ctx, models.TicketFilter{
		WorkspaceID: workspaceID,
		Cursor:      page1.PageInfo.NextCursor,
		Limit:       2,
	})
	if err != nil {
		t.Fatalf("ListTickets page 2 failed: %v", err)
	}
	if len(page2.Tickets) != 2 {
		t.Errorf("Page 2 count: got %d, want 2", len(page2.Tickets))
	}
	if !page2.PageInfo.HasNextPage {
		t.Error("Page 2 should have next page")
	}

	// Third page (last)
	page3, err := pg.ListTickets(ctx, models.TicketFilter{
		WorkspaceID: workspaceID,
		Cursor:      page2.PageInfo.NextCursor,
		Limit:       2,
	})
	if err != nil {
		t.Fatalf("ListTickets page 3 failed: %v", err)
	}
	if len(page3.Tickets) != 1 {
		t.Errorf("Page 3 count: got %d, want 1", len(page3.Tickets))
	}
	if page3.PageInfo.HasNextPage {
		t.Error("Page 3 should NOT have next page")
	}
}
