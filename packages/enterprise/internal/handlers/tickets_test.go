package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/models"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/requestid"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage/postgres"
)

// ticketsMockStore implements storage.PostgresStore for tickets testing.
// Named uniquely to avoid conflicts with other handler test files.
type ticketsMockStore struct {
	// Ticket operations
	createTicketFunc func(ctx context.Context, ticket *models.Ticket) error
	getTicketFunc    func(ctx context.Context, id string) (*models.Ticket, error)
	updateTicketFunc func(ctx context.Context, ticket *models.Ticket) error
	deleteTicketFunc func(ctx context.Context, id string) error
	listTicketsFunc  func(ctx context.Context, filter models.TicketFilter) (*models.TicketList, error)
}

func (m *ticketsMockStore) Ping(ctx context.Context) error {
	return nil
}

func (m *ticketsMockStore) CreateTicket(ctx context.Context, ticket *models.Ticket) error {
	if m.createTicketFunc != nil {
		return m.createTicketFunc(ctx, ticket)
	}
	return nil
}

func (m *ticketsMockStore) GetTicket(ctx context.Context, id string) (*models.Ticket, error) {
	if m.getTicketFunc != nil {
		return m.getTicketFunc(ctx, id)
	}
	return nil, nil
}

func (m *ticketsMockStore) UpdateTicket(ctx context.Context, ticket *models.Ticket) error {
	if m.updateTicketFunc != nil {
		return m.updateTicketFunc(ctx, ticket)
	}
	return nil
}

func (m *ticketsMockStore) DeleteTicket(ctx context.Context, id string) error {
	if m.deleteTicketFunc != nil {
		return m.deleteTicketFunc(ctx, id)
	}
	return nil
}

func (m *ticketsMockStore) ListTickets(ctx context.Context, filter models.TicketFilter) (*models.TicketList, error) {
	if m.listTicketsFunc != nil {
		return m.listTicketsFunc(ctx, filter)
	}
	return &models.TicketList{Tickets: []models.Ticket{}}, nil
}

// Job operations (stubs - not used in tickets tests)
func (m *ticketsMockStore) CreateJob(ctx context.Context, job *models.Job) error {
	return nil
}

func (m *ticketsMockStore) GetJob(ctx context.Context, id string) (*models.Job, error) {
	return nil, nil
}

func (m *ticketsMockStore) UpdateJob(ctx context.Context, job *models.Job) error {
	return nil
}

func (m *ticketsMockStore) ListJobs(ctx context.Context, filter models.JobFilter) (*models.JobList, error) {
	return &models.JobList{Jobs: []models.Job{}}, nil
}

// Approval operations (stubs - not used in tickets tests)
func (m *ticketsMockStore) CreateApproval(ctx context.Context, approval *models.Approval) error {
	return nil
}

func (m *ticketsMockStore) GetApproval(ctx context.Context, id string) (*models.Approval, error) {
	return nil, nil
}

func (m *ticketsMockStore) UpdateApproval(ctx context.Context, approval *models.Approval) error {
	return nil
}

func (m *ticketsMockStore) ListApprovals(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
	return &models.ApprovalList{Approvals: []models.Approval{}}, nil
}

// Audit operations (stubs - not used in tickets tests)
func (m *ticketsMockStore) CreateAuditRecord(ctx context.Context, record *models.AuditRecord) error {
	return nil
}

func (m *ticketsMockStore) GetAuditRecord(ctx context.Context, id string) (*models.AuditRecord, error) {
	return nil, nil
}

func (m *ticketsMockStore) ListAuditRecords(ctx context.Context, filter models.AuditFilter) (*models.AuditList, error) {
	return &models.AuditList{Records: []models.AuditRecord{}}, nil
}

// ticketsTestLogger returns a discarding logger for tickets tests.
func ticketsTestLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
}

// ticketsAddRequestID adds a request ID to the request context for tickets tests.
func ticketsAddRequestID(r *http.Request) *http.Request {
	ctx := requestid.NewContext(r.Context(), "req_test123")
	return r.WithContext(ctx)
}

// setupTicketsChiContext sets up chi URL parameters in the request context.
func setupTicketsChiContext(r *http.Request, params map[string]string) *http.Request {
	rctx := chi.NewRouteContext()
	for key, val := range params {
		rctx.URLParams.Add(key, val)
	}
	ctx := context.WithValue(r.Context(), chi.RouteCtxKey, rctx)
	return r.WithContext(ctx)
}

func TestNewTicketsHandler(t *testing.T) {
	store := &ticketsMockStore{}
	log := ticketsTestLogger()

	handler := NewTicketsHandler(store, log)

	if handler == nil {
		t.Fatal("expected handler to be non-nil")
	}
	if handler.store != store {
		t.Error("expected store to be set correctly")
	}
	if handler.log != log {
		t.Error("expected logger to be set correctly")
	}
}

func TestTicketsHandler_Create_Success(t *testing.T) {
	store := &ticketsMockStore{
		createTicketFunc: func(ctx context.Context, ticket *models.Ticket) error {
			if ticket.Title != "Test Ticket" {
				t.Errorf("expected title 'Test Ticket', got %s", ticket.Title)
			}
			if ticket.WorkspaceID != "ws-123" {
				t.Errorf("expected workspace_id 'ws-123', got %s", ticket.WorkspaceID)
			}
			if ticket.Status != models.TicketStatusOpen {
				t.Errorf("expected status 'open', got %s", ticket.Status)
			}
			return nil
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	reqBody := CreateTicketRequest{
		WorkspaceID: "ws-123",
		Title:       "Test Ticket",
		Description: "Test description",
		Priority:    models.TicketPriorityHigh,
		CreatedBy:   "user-123",
		Labels:      []string{"bug", "urgent"},
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest(http.MethodPost, "/v1/tickets", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.Create(rr, req)

	if rr.Code != http.StatusCreated {
		t.Errorf("expected status %d, got %d", http.StatusCreated, rr.Code)
	}

	var resp response.SuccessResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if !resp.Success {
		t.Error("expected success to be true")
	}
}

func TestTicketsHandler_Create_ValidationError_MissingFields(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	// Missing required fields
	reqBody := CreateTicketRequest{
		Description: "Test description",
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest(http.MethodPost, "/v1/tickets", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.Create(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Success {
		t.Error("expected success to be false")
	}
	if resp.Error.Code != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_Create_ValidationError_InvalidPriority(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	reqBody := map[string]interface{}{
		"workspace_id": "ws-123",
		"title":        "Test Ticket",
		"created_by":   "user-123",
		"priority":     "invalid_priority",
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest(http.MethodPost, "/v1/tickets", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.Create(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_Create_InvalidJSON(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodPost, "/v1/tickets", bytes.NewReader([]byte("invalid json")))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.Create(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_Create_InternalError(t *testing.T) {
	store := &ticketsMockStore{
		createTicketFunc: func(ctx context.Context, ticket *models.Ticket) error {
			return errors.New("database error")
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	reqBody := CreateTicketRequest{
		WorkspaceID: "ws-123",
		Title:       "Test Ticket",
		CreatedBy:   "user-123",
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest(http.MethodPost, "/v1/tickets", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.Create(rr, req)

	if rr.Code != http.StatusInternalServerError {
		t.Errorf("expected status %d, got %d", http.StatusInternalServerError, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "INTERNAL_ERROR" {
		t.Errorf("expected error code 'INTERNAL_ERROR', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_Create_DefaultPriority(t *testing.T) {
	var capturedTicket *models.Ticket
	store := &ticketsMockStore{
		createTicketFunc: func(ctx context.Context, ticket *models.Ticket) error {
			capturedTicket = ticket
			return nil
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	reqBody := CreateTicketRequest{
		WorkspaceID: "ws-123",
		Title:       "Test Ticket",
		CreatedBy:   "user-123",
		// Priority is not set, should default to medium
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest(http.MethodPost, "/v1/tickets", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.Create(rr, req)

	if rr.Code != http.StatusCreated {
		t.Errorf("expected status %d, got %d", http.StatusCreated, rr.Code)
	}

	if capturedTicket.Priority != models.TicketPriorityMedium {
		t.Errorf("expected default priority 'medium', got %s", capturedTicket.Priority)
	}
}

func TestTicketsHandler_List_Success(t *testing.T) {
	now := time.Now().UTC()
	store := &ticketsMockStore{
		listTicketsFunc: func(ctx context.Context, filter models.TicketFilter) (*models.TicketList, error) {
			return &models.TicketList{
				Tickets: []models.Ticket{
					{
						ID:          "ticket-1",
						WorkspaceID: "ws-123",
						Title:       "Ticket 1",
						Status:      models.TicketStatusOpen,
						Priority:    models.TicketPriorityHigh,
						CreatedBy:   "user-123",
						CreatedAt:   now,
						UpdatedAt:   now,
					},
					{
						ID:          "ticket-2",
						WorkspaceID: "ws-123",
						Title:       "Ticket 2",
						Status:      models.TicketStatusInProgress,
						Priority:    models.TicketPriorityLow,
						CreatedBy:   "user-456",
						CreatedAt:   now,
						UpdatedAt:   now,
					},
				},
				PageInfo: models.PageInfo{
					HasNextPage: false,
					TotalCount:  2,
				},
			}, nil
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/tickets?workspace_id=ws-123", nil)
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.List(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rr.Code)
	}

	var resp response.SuccessResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if !resp.Success {
		t.Error("expected success to be true")
	}
}

func TestTicketsHandler_List_WithFilters(t *testing.T) {
	var capturedFilter models.TicketFilter
	store := &ticketsMockStore{
		listTicketsFunc: func(ctx context.Context, filter models.TicketFilter) (*models.TicketList, error) {
			capturedFilter = filter
			return &models.TicketList{Tickets: []models.Ticket{}}, nil
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/tickets?workspace_id=ws-123&status=open&priority=high&limit=25&labels=bug,urgent", nil)
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.List(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rr.Code)
	}

	if capturedFilter.WorkspaceID != "ws-123" {
		t.Errorf("expected workspace_id 'ws-123', got %s", capturedFilter.WorkspaceID)
	}
	if capturedFilter.Status != models.TicketStatusOpen {
		t.Errorf("expected status 'open', got %s", capturedFilter.Status)
	}
	if capturedFilter.Priority != models.TicketPriorityHigh {
		t.Errorf("expected priority 'high', got %s", capturedFilter.Priority)
	}
	if capturedFilter.Limit != 25 {
		t.Errorf("expected limit 25, got %d", capturedFilter.Limit)
	}
	if len(capturedFilter.Labels) != 2 || capturedFilter.Labels[0] != "bug" || capturedFilter.Labels[1] != "urgent" {
		t.Errorf("expected labels ['bug', 'urgent'], got %v", capturedFilter.Labels)
	}
}

func TestTicketsHandler_List_InvalidLimit(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/tickets?limit=invalid", nil)
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.List(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_List_InvalidStatus(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/tickets?status=invalid_status", nil)
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.List(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_List_InvalidPriority(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/tickets?priority=invalid_priority", nil)
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.List(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}
}

func TestTicketsHandler_List_InvalidCursor(t *testing.T) {
	store := &ticketsMockStore{
		listTicketsFunc: func(ctx context.Context, filter models.TicketFilter) (*models.TicketList, error) {
			return nil, postgres.ErrInvalidCursor
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/tickets?cursor=invalid", nil)
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.List(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_List_InternalError(t *testing.T) {
	store := &ticketsMockStore{
		listTicketsFunc: func(ctx context.Context, filter models.TicketFilter) (*models.TicketList, error) {
			return nil, errors.New("database error")
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/tickets", nil)
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.List(rr, req)

	if rr.Code != http.StatusInternalServerError {
		t.Errorf("expected status %d, got %d", http.StatusInternalServerError, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "INTERNAL_ERROR" {
		t.Errorf("expected error code 'INTERNAL_ERROR', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_List_LimitCapped(t *testing.T) {
	var capturedFilter models.TicketFilter
	store := &ticketsMockStore{
		listTicketsFunc: func(ctx context.Context, filter models.TicketFilter) (*models.TicketList, error) {
			capturedFilter = filter
			return &models.TicketList{Tickets: []models.Ticket{}}, nil
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	// Request with limit exceeding MaxPageLimit
	req := httptest.NewRequest(http.MethodGet, "/v1/tickets?limit=500", nil)
	req = ticketsAddRequestID(req)

	rr := httptest.NewRecorder()
	handler.List(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rr.Code)
	}

	if capturedFilter.Limit != models.MaxPageLimit {
		t.Errorf("expected limit to be capped at %d, got %d", models.MaxPageLimit, capturedFilter.Limit)
	}
}

func TestTicketsHandler_Get_Success(t *testing.T) {
	now := time.Now().UTC()
	store := &ticketsMockStore{
		getTicketFunc: func(ctx context.Context, id string) (*models.Ticket, error) {
			if id != "ticket-123" {
				t.Errorf("expected id 'ticket-123', got %s", id)
			}
			return &models.Ticket{
				ID:          "ticket-123",
				WorkspaceID: "ws-123",
				Title:       "Test Ticket",
				Status:      models.TicketStatusOpen,
				Priority:    models.TicketPriorityHigh,
				CreatedBy:   "user-123",
				CreatedAt:   now,
				UpdatedAt:   now,
			}, nil
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/tickets/ticket-123", nil)
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": "ticket-123"})

	rr := httptest.NewRecorder()
	handler.Get(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rr.Code)
	}

	var resp response.SuccessResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if !resp.Success {
		t.Error("expected success to be true")
	}
}

func TestTicketsHandler_Get_NotFound(t *testing.T) {
	store := &ticketsMockStore{
		getTicketFunc: func(ctx context.Context, id string) (*models.Ticket, error) {
			return nil, postgres.ErrNotFound
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/tickets/nonexistent", nil)
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": "nonexistent"})

	rr := httptest.NewRecorder()
	handler.Get(rr, req)

	if rr.Code != http.StatusNotFound {
		t.Errorf("expected status %d, got %d", http.StatusNotFound, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "NOT_FOUND" {
		t.Errorf("expected error code 'NOT_FOUND', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_Get_InternalError(t *testing.T) {
	store := &ticketsMockStore{
		getTicketFunc: func(ctx context.Context, id string) (*models.Ticket, error) {
			return nil, errors.New("database error")
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/tickets/ticket-123", nil)
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": "ticket-123"})

	rr := httptest.NewRecorder()
	handler.Get(rr, req)

	if rr.Code != http.StatusInternalServerError {
		t.Errorf("expected status %d, got %d", http.StatusInternalServerError, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "INTERNAL_ERROR" {
		t.Errorf("expected error code 'INTERNAL_ERROR', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_Get_EmptyID(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/tickets/", nil)
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": ""})

	rr := httptest.NewRecorder()
	handler.Get(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}
}

func TestTicketsHandler_Update_Success(t *testing.T) {
	now := time.Now().UTC()
	existingTicket := &models.Ticket{
		ID:          "ticket-123",
		WorkspaceID: "ws-123",
		Title:       "Original Title",
		Description: "Original description",
		Status:      models.TicketStatusOpen,
		Priority:    models.TicketPriorityMedium,
		CreatedBy:   "user-123",
		CreatedAt:   now,
		UpdatedAt:   now,
	}

	var updatedTicket *models.Ticket
	store := &ticketsMockStore{
		getTicketFunc: func(ctx context.Context, id string) (*models.Ticket, error) {
			// Return a copy to simulate real behavior
			ticketCopy := *existingTicket
			return &ticketCopy, nil
		},
		updateTicketFunc: func(ctx context.Context, ticket *models.Ticket) error {
			updatedTicket = ticket
			return nil
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	newTitle := "Updated Title"
	newStatus := models.TicketStatusInProgress
	reqBody := UpdateTicketRequest{
		Title:  &newTitle,
		Status: &newStatus,
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest(http.MethodPatch, "/v1/tickets/ticket-123", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": "ticket-123"})

	rr := httptest.NewRecorder()
	handler.Update(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rr.Code)
	}

	if updatedTicket.Title != "Updated Title" {
		t.Errorf("expected title 'Updated Title', got %s", updatedTicket.Title)
	}
	if updatedTicket.Status != models.TicketStatusInProgress {
		t.Errorf("expected status 'in_progress', got %s", updatedTicket.Status)
	}
	// Original fields should be preserved
	if updatedTicket.Description != "Original description" {
		t.Errorf("expected description 'Original description', got %s", updatedTicket.Description)
	}
}

func TestTicketsHandler_Update_NotFound(t *testing.T) {
	store := &ticketsMockStore{
		getTicketFunc: func(ctx context.Context, id string) (*models.Ticket, error) {
			return nil, postgres.ErrNotFound
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	newTitle := "Updated Title"
	reqBody := UpdateTicketRequest{
		Title: &newTitle,
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest(http.MethodPatch, "/v1/tickets/nonexistent", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": "nonexistent"})

	rr := httptest.NewRecorder()
	handler.Update(rr, req)

	if rr.Code != http.StatusNotFound {
		t.Errorf("expected status %d, got %d", http.StatusNotFound, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "NOT_FOUND" {
		t.Errorf("expected error code 'NOT_FOUND', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_Update_InvalidJSON(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodPatch, "/v1/tickets/ticket-123", bytes.NewReader([]byte("invalid json")))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": "ticket-123"})

	rr := httptest.NewRecorder()
	handler.Update(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_Update_InvalidStatus(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	reqBody := map[string]interface{}{
		"status": "invalid_status",
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest(http.MethodPatch, "/v1/tickets/ticket-123", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": "ticket-123"})

	rr := httptest.NewRecorder()
	handler.Update(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_Update_InvalidPriority(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	reqBody := map[string]interface{}{
		"priority": "invalid_priority",
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest(http.MethodPatch, "/v1/tickets/ticket-123", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": "ticket-123"})

	rr := httptest.NewRecorder()
	handler.Update(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}
}

func TestTicketsHandler_Update_InternalError_OnGet(t *testing.T) {
	store := &ticketsMockStore{
		getTicketFunc: func(ctx context.Context, id string) (*models.Ticket, error) {
			return nil, errors.New("database error")
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	newTitle := "Updated Title"
	reqBody := UpdateTicketRequest{
		Title: &newTitle,
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest(http.MethodPatch, "/v1/tickets/ticket-123", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": "ticket-123"})

	rr := httptest.NewRecorder()
	handler.Update(rr, req)

	if rr.Code != http.StatusInternalServerError {
		t.Errorf("expected status %d, got %d", http.StatusInternalServerError, rr.Code)
	}
}

func TestTicketsHandler_Update_InternalError_OnUpdate(t *testing.T) {
	now := time.Now().UTC()
	store := &ticketsMockStore{
		getTicketFunc: func(ctx context.Context, id string) (*models.Ticket, error) {
			return &models.Ticket{
				ID:          "ticket-123",
				WorkspaceID: "ws-123",
				Title:       "Original Title",
				Status:      models.TicketStatusOpen,
				Priority:    models.TicketPriorityMedium,
				CreatedBy:   "user-123",
				CreatedAt:   now,
				UpdatedAt:   now,
			}, nil
		},
		updateTicketFunc: func(ctx context.Context, ticket *models.Ticket) error {
			return errors.New("database error")
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	newTitle := "Updated Title"
	reqBody := UpdateTicketRequest{
		Title: &newTitle,
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest(http.MethodPatch, "/v1/tickets/ticket-123", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": "ticket-123"})

	rr := httptest.NewRecorder()
	handler.Update(rr, req)

	if rr.Code != http.StatusInternalServerError {
		t.Errorf("expected status %d, got %d", http.StatusInternalServerError, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "INTERNAL_ERROR" {
		t.Errorf("expected error code 'INTERNAL_ERROR', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_Update_EmptyID(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodPatch, "/v1/tickets/", bytes.NewReader([]byte("{}")))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": ""})

	rr := httptest.NewRecorder()
	handler.Update(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}
}

func TestTicketsHandler_Update_ClearAssignedTo(t *testing.T) {
	now := time.Now().UTC()
	store := &ticketsMockStore{
		getTicketFunc: func(ctx context.Context, id string) (*models.Ticket, error) {
			return &models.Ticket{
				ID:          "ticket-123",
				WorkspaceID: "ws-123",
				Title:       "Test Ticket",
				Status:      models.TicketStatusOpen,
				Priority:    models.TicketPriorityMedium,
				CreatedBy:   "user-123",
				CreatedAt:   now,
				UpdatedAt:   now,
			}, nil
		},
		updateTicketFunc: func(ctx context.Context, ticket *models.Ticket) error {
			if ticket.AssignedTo.Valid {
				t.Error("expected AssignedTo to be cleared (invalid)")
			}
			return nil
		},
	}

	handler := NewTicketsHandler(store, ticketsTestLogger())

	emptyAssignee := ""
	reqBody := UpdateTicketRequest{
		AssignedTo: &emptyAssignee,
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest(http.MethodPatch, "/v1/tickets/ticket-123", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": "ticket-123"})

	rr := httptest.NewRecorder()
	handler.Update(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rr.Code)
	}
}

func TestTicketsHandler_CreateJob_NotImplemented(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	req := httptest.NewRequest(http.MethodPost, "/v1/tickets/ticket-123/jobs", nil)
	req = ticketsAddRequestID(req)
	req = setupTicketsChiContext(req, map[string]string{"ticketID": "ticket-123"})

	rr := httptest.NewRecorder()
	handler.CreateJob(rr, req)

	if rr.Code != http.StatusNotImplemented {
		t.Errorf("expected status %d, got %d", http.StatusNotImplemented, rr.Code)
	}

	var resp response.ErrorResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "NOT_IMPLEMENTED" {
		t.Errorf("expected error code 'NOT_IMPLEMENTED', got %s", resp.Error.Code)
	}
}

func TestTicketsHandler_Routes(t *testing.T) {
	store := &ticketsMockStore{}
	handler := NewTicketsHandler(store, ticketsTestLogger())

	router := handler.Routes()

	if router == nil {
		t.Fatal("expected router to be non-nil")
	}
}

func TestTicketsIsValidTicketStatus(t *testing.T) {
	tests := []struct {
		status   models.TicketStatus
		expected bool
	}{
		{models.TicketStatusOpen, true},
		{models.TicketStatusInProgress, true},
		{models.TicketStatusPending, true},
		{models.TicketStatusResolved, true},
		{models.TicketStatusClosed, true},
		{models.TicketStatus("invalid"), false},
		{models.TicketStatus(""), false},
	}

	for _, tt := range tests {
		result := isValidTicketStatus(tt.status)
		if result != tt.expected {
			t.Errorf("isValidTicketStatus(%s) = %v, expected %v", tt.status, result, tt.expected)
		}
	}
}

func TestTicketsIsValidTicketPriority(t *testing.T) {
	tests := []struct {
		priority models.TicketPriority
		expected bool
	}{
		{models.TicketPriorityLow, true},
		{models.TicketPriorityMedium, true},
		{models.TicketPriorityHigh, true},
		{models.TicketPriorityCritical, true},
		{models.TicketPriority("invalid"), false},
		{models.TicketPriority(""), false},
	}

	for _, tt := range tests {
		result := isValidTicketPriority(tt.priority)
		if result != tt.expected {
			t.Errorf("isValidTicketPriority(%s) = %v, expected %v", tt.priority, result, tt.expected)
		}
	}
}

func TestTicketsSplitAndTrim(t *testing.T) {
	tests := []struct {
		input    string
		expected []string
	}{
		{"a,b,c", []string{"a", "b", "c"}},
		{"a, b, c", []string{"a", "b", "c"}},
		{"  a  ,  b  ,  c  ", []string{"a", "b", "c"}},
		{"a", []string{"a"}},
		{"", nil},
		{",,,", nil},
		{"a,,b", []string{"a", "b"}},
	}

	for _, tt := range tests {
		result := splitAndTrim(tt.input)
		if len(result) != len(tt.expected) {
			t.Errorf("splitAndTrim(%q) = %v, expected %v", tt.input, result, tt.expected)
			continue
		}
		for i := range result {
			if result[i] != tt.expected[i] {
				t.Errorf("splitAndTrim(%q)[%d] = %q, expected %q", tt.input, i, result[i], tt.expected[i])
			}
		}
	}
}
