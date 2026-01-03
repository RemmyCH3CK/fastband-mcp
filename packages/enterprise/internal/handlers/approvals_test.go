package handlers

import (
	"bytes"
	"context"
	"database/sql"
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

// mockApprovalStore implements storage.PostgresStore for approvals testing.
type mockApprovalStore struct {
	// Approval methods
	createApprovalFn func(ctx context.Context, approval *models.Approval) error
	getApprovalFn    func(ctx context.Context, id string) (*models.Approval, error)
	updateApprovalFn func(ctx context.Context, approval *models.Approval) error
	listApprovalsFn  func(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error)
}

func (m *mockApprovalStore) Ping(ctx context.Context) error { return nil }

// Ticket operations - not used in approvals tests
func (m *mockApprovalStore) CreateTicket(ctx context.Context, ticket *models.Ticket) error {
	return nil
}
func (m *mockApprovalStore) GetTicket(ctx context.Context, id string) (*models.Ticket, error) {
	return nil, nil
}
func (m *mockApprovalStore) UpdateTicket(ctx context.Context, ticket *models.Ticket) error {
	return nil
}
func (m *mockApprovalStore) DeleteTicket(ctx context.Context, id string) error { return nil }
func (m *mockApprovalStore) ListTickets(ctx context.Context, filter models.TicketFilter) (*models.TicketList, error) {
	return nil, nil
}

// Job operations - not used in approvals tests
func (m *mockApprovalStore) CreateJob(ctx context.Context, job *models.Job) error { return nil }
func (m *mockApprovalStore) GetJob(ctx context.Context, id string) (*models.Job, error) {
	return nil, nil
}
func (m *mockApprovalStore) UpdateJob(ctx context.Context, job *models.Job) error { return nil }
func (m *mockApprovalStore) ListJobs(ctx context.Context, filter models.JobFilter) (*models.JobList, error) {
	return nil, nil
}

// Approval operations
func (m *mockApprovalStore) CreateApproval(ctx context.Context, approval *models.Approval) error {
	if m.createApprovalFn != nil {
		return m.createApprovalFn(ctx, approval)
	}
	return nil
}

func (m *mockApprovalStore) GetApproval(ctx context.Context, id string) (*models.Approval, error) {
	if m.getApprovalFn != nil {
		return m.getApprovalFn(ctx, id)
	}
	return nil, nil
}

func (m *mockApprovalStore) UpdateApproval(ctx context.Context, approval *models.Approval) error {
	if m.updateApprovalFn != nil {
		return m.updateApprovalFn(ctx, approval)
	}
	return nil
}

func (m *mockApprovalStore) ListApprovals(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
	if m.listApprovalsFn != nil {
		return m.listApprovalsFn(ctx, filter)
	}
	return &models.ApprovalList{}, nil
}

// Audit operations - not used in approvals tests
func (m *mockApprovalStore) CreateAuditRecord(ctx context.Context, record *models.AuditRecord) error {
	return nil
}
func (m *mockApprovalStore) GetAuditRecord(ctx context.Context, id string) (*models.AuditRecord, error) {
	return nil, nil
}
func (m *mockApprovalStore) ListAuditRecords(ctx context.Context, filter models.AuditFilter) (*models.AuditList, error) {
	return nil, nil
}

// approvalTestLogger returns a discarding logger for tests.
func approvalTestLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelError}))
}

// setupApprovalTestHandler creates a handler with chi router for URL parameter extraction.
func setupApprovalTestHandler(store *mockApprovalStore) (*ApprovalsHandler, chi.Router) {
	handler := NewApprovalsHandler(store, approvalTestLogger())
	r := chi.NewRouter()
	r.Route("/v1/approvals", func(r chi.Router) {
		r.Get("/", handler.List)
		r.Get("/{approvalID}", handler.Get)
		r.Post("/{approvalID}/approve", handler.Approve)
		r.Post("/{approvalID}/deny", handler.Deny)
	})
	return handler, r
}

// addApprovalRequestID adds a request ID to the request context.
func addApprovalRequestID(r *http.Request) *http.Request {
	ctx := requestid.NewContext(r.Context(), "req_test123")
	return r.WithContext(ctx)
}

// TestNewApprovalsHandler tests handler creation.
func TestNewApprovalsHandler(t *testing.T) {
	store := &mockApprovalStore{}
	log := approvalTestLogger()

	handler := NewApprovalsHandler(store, log)

	if handler == nil {
		t.Fatal("Expected non-nil handler")
	}
	if handler.store != store {
		t.Error("Expected store to be set")
	}
	if handler.log != log {
		t.Error("Expected logger to be set")
	}
}

// TestApprovalsHandler_Routes tests that routes are registered.
func TestApprovalsHandler_Routes(t *testing.T) {
	handler := NewApprovalsHandler(&mockApprovalStore{}, approvalTestLogger())
	routes := handler.Routes()

	if routes == nil {
		t.Fatal("Expected non-nil router")
	}
}

// TestApprovalsHandler_List tests the List endpoint.
func TestApprovalsHandler_List(t *testing.T) {
	now := time.Now().UTC()

	tests := []struct {
		name           string
		query          string
		mockList       func(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error)
		expectedStatus int
		expectedCode   string
	}{
		{
			name:  "success - empty list",
			query: "",
			mockList: func(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
				return &models.ApprovalList{
					Approvals: []models.Approval{},
					PageInfo:  models.PageInfo{HasNextPage: false},
				}, nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:  "success - with results",
			query: "",
			mockList: func(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
				return &models.ApprovalList{
					Approvals: []models.Approval{
						{
							ID:          "apv_123",
							JobID:       "job_456",
							ToolCallID:  "tc_789",
							Tool:        "bash",
							Resource:    "/usr/bin/ls",
							Status:      models.ApprovalStatusPending,
							RequestedBy: "user_001",
							RequestedAt: now,
						},
					},
					PageInfo: models.PageInfo{HasNextPage: false, TotalCount: 1},
				}, nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:  "success - with status filter",
			query: "?status=pending",
			mockList: func(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
				if filter.Status != models.ApprovalStatusPending {
					t.Errorf("Expected status filter pending, got %s", filter.Status)
				}
				return &models.ApprovalList{Approvals: []models.Approval{}}, nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:  "success - with job_id filter",
			query: "?job_id=job_123",
			mockList: func(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
				if filter.JobID != "job_123" {
					t.Errorf("Expected job_id filter job_123, got %s", filter.JobID)
				}
				return &models.ApprovalList{Approvals: []models.Approval{}}, nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:  "success - with tool filter",
			query: "?tool=bash",
			mockList: func(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
				if filter.Tool != "bash" {
					t.Errorf("Expected tool filter bash, got %s", filter.Tool)
				}
				return &models.ApprovalList{Approvals: []models.Approval{}}, nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:  "success - with limit",
			query: "?limit=10",
			mockList: func(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
				if filter.Limit != 10 {
					t.Errorf("Expected limit 10, got %d", filter.Limit)
				}
				return &models.ApprovalList{Approvals: []models.Approval{}}, nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:  "success - limit capped at max",
			query: "?limit=500",
			mockList: func(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
				if filter.Limit != models.MaxPageLimit {
					t.Errorf("Expected limit %d, got %d", models.MaxPageLimit, filter.Limit)
				}
				return &models.ApprovalList{Approvals: []models.Approval{}}, nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:           "error - invalid limit",
			query:          "?limit=invalid",
			expectedStatus: http.StatusBadRequest,
			expectedCode:   "VALIDATION_ERROR",
		},
		{
			name:           "error - negative limit",
			query:          "?limit=-5",
			expectedStatus: http.StatusBadRequest,
			expectedCode:   "VALIDATION_ERROR",
		},
		{
			name:  "error - storage error",
			query: "",
			mockList: func(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
				return nil, errors.New("database connection failed")
			},
			expectedStatus: http.StatusInternalServerError,
			expectedCode:   "INTERNAL_ERROR",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			store := &mockApprovalStore{
				listApprovalsFn: tt.mockList,
			}
			_, router := setupApprovalTestHandler(store)

			req := httptest.NewRequest(http.MethodGet, "/v1/approvals"+tt.query, nil)
			req = addApprovalRequestID(req)
			rec := httptest.NewRecorder()

			router.ServeHTTP(rec, req)

			if rec.Code != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d", tt.expectedStatus, rec.Code)
			}

			var resp map[string]interface{}
			if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
				t.Fatalf("Failed to parse response: %v", err)
			}

			if tt.expectedStatus == http.StatusOK {
				if resp["success"] != true {
					t.Error("Expected success to be true")
				}
			} else {
				if resp["success"] != false {
					t.Error("Expected success to be false")
				}
				if errObj, ok := resp["error"].(map[string]interface{}); ok {
					if errObj["code"] != tt.expectedCode {
						t.Errorf("Expected error code %s, got %v", tt.expectedCode, errObj["code"])
					}
				}
			}
		})
	}
}

// TestApprovalsHandler_Get tests the Get endpoint.
func TestApprovalsHandler_Get(t *testing.T) {
	now := time.Now().UTC()
	testApproval := &models.Approval{
		ID:          "apv_123",
		JobID:       "job_456",
		ToolCallID:  "tc_789",
		Tool:        "bash",
		Resource:    "/usr/bin/ls",
		Status:      models.ApprovalStatusPending,
		RequestedBy: "user_001",
		RequestedAt: now,
	}

	tests := []struct {
		name           string
		approvalID     string
		mockGet        func(ctx context.Context, id string) (*models.Approval, error)
		expectedStatus int
		expectedCode   string
	}{
		{
			name:       "success",
			approvalID: "apv_123",
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				if id != "apv_123" {
					t.Errorf("Expected id apv_123, got %s", id)
				}
				return testApproval, nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:       "not found",
			approvalID: "apv_notfound",
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				return nil, postgres.ErrNotFound
			},
			expectedStatus: http.StatusNotFound,
			expectedCode:   "NOT_FOUND",
		},
		{
			name:       "storage error",
			approvalID: "apv_123",
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				return nil, errors.New("database connection failed")
			},
			expectedStatus: http.StatusInternalServerError,
			expectedCode:   "INTERNAL_ERROR",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			store := &mockApprovalStore{
				getApprovalFn: tt.mockGet,
			}
			_, router := setupApprovalTestHandler(store)

			req := httptest.NewRequest(http.MethodGet, "/v1/approvals/"+tt.approvalID, nil)
			req = addApprovalRequestID(req)
			rec := httptest.NewRecorder()

			router.ServeHTTP(rec, req)

			if rec.Code != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d", tt.expectedStatus, rec.Code)
			}

			var resp map[string]interface{}
			if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
				t.Fatalf("Failed to parse response: %v", err)
			}

			if tt.expectedStatus == http.StatusOK {
				if resp["success"] != true {
					t.Error("Expected success to be true")
				}
				if data, ok := resp["data"].(map[string]interface{}); ok {
					if data["id"] != testApproval.ID {
						t.Errorf("Expected approval ID %s, got %v", testApproval.ID, data["id"])
					}
				}
			} else {
				if resp["success"] != false {
					t.Error("Expected success to be false")
				}
				if errObj, ok := resp["error"].(map[string]interface{}); ok {
					if errObj["code"] != tt.expectedCode {
						t.Errorf("Expected error code %s, got %v", tt.expectedCode, errObj["code"])
					}
				}
			}
		})
	}
}

// TestApprovalsHandler_Approve tests the Approve endpoint.
func TestApprovalsHandler_Approve(t *testing.T) {
	now := time.Now().UTC()
	pendingApproval := &models.Approval{
		ID:          "apv_123",
		JobID:       "job_456",
		ToolCallID:  "tc_789",
		Tool:        "bash",
		Resource:    "/usr/bin/ls",
		Status:      models.ApprovalStatusPending,
		RequestedBy: "user_001",
		RequestedAt: now,
	}

	approvedApproval := &models.Approval{
		ID:          "apv_already",
		JobID:       "job_456",
		ToolCallID:  "tc_789",
		Tool:        "bash",
		Resource:    "/usr/bin/ls",
		Status:      models.ApprovalStatusApproved,
		RequestedBy: "user_001",
		RequestedAt: now,
		DecidedBy:   sql.NullString{String: "admin", Valid: true},
		DecidedAt:   sql.NullTime{Time: now, Valid: true},
	}

	tests := []struct {
		name           string
		approvalID     string
		body           interface{}
		mockGet        func(ctx context.Context, id string) (*models.Approval, error)
		mockUpdate     func(ctx context.Context, approval *models.Approval) error
		expectedStatus int
		expectedCode   string
		checkApproval  func(t *testing.T, approval *models.Approval)
	}{
		{
			name:       "success - no body",
			approvalID: "apv_123",
			body:       nil,
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				// Return a copy to avoid mutation issues
				cp := *pendingApproval
				return &cp, nil
			},
			mockUpdate: func(ctx context.Context, approval *models.Approval) error {
				if approval.Status != models.ApprovalStatusApproved {
					t.Errorf("Expected status approved, got %s", approval.Status)
				}
				if !approval.DecidedBy.Valid {
					t.Error("Expected DecidedBy to be set")
				}
				if !approval.DecidedAt.Valid {
					t.Error("Expected DecidedAt to be set")
				}
				return nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:       "success - with comment",
			approvalID: "apv_123",
			body: map[string]string{
				"comment": "Approved after review",
			},
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				cp := *pendingApproval
				return &cp, nil
			},
			mockUpdate: func(ctx context.Context, approval *models.Approval) error {
				if !approval.Comment.Valid || approval.Comment.String != "Approved after review" {
					t.Errorf("Expected comment to be set, got %v", approval.Comment)
				}
				return nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:       "success - with decided_by",
			approvalID: "apv_123",
			body: map[string]string{
				"decided_by": "admin_user",
			},
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				cp := *pendingApproval
				return &cp, nil
			},
			mockUpdate: func(ctx context.Context, approval *models.Approval) error {
				if !approval.DecidedBy.Valid || approval.DecidedBy.String != "admin_user" {
					t.Errorf("Expected decided_by to be admin_user, got %v", approval.DecidedBy)
				}
				return nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:       "not found",
			approvalID: "apv_notfound",
			body:       nil,
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				return nil, postgres.ErrNotFound
			},
			expectedStatus: http.StatusNotFound,
			expectedCode:   "NOT_FOUND",
		},
		{
			name:       "already decided",
			approvalID: "apv_already",
			body:       nil,
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				return approvedApproval, nil
			},
			expectedStatus: http.StatusBadRequest,
			expectedCode:   "VALIDATION_ERROR",
		},
		{
			name:       "storage error on get",
			approvalID: "apv_123",
			body:       nil,
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				return nil, errors.New("database error")
			},
			expectedStatus: http.StatusInternalServerError,
			expectedCode:   "INTERNAL_ERROR",
		},
		{
			name:       "storage error on update",
			approvalID: "apv_123",
			body:       nil,
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				cp := *pendingApproval
				return &cp, nil
			},
			mockUpdate: func(ctx context.Context, approval *models.Approval) error {
				return errors.New("database error")
			},
			expectedStatus: http.StatusInternalServerError,
			expectedCode:   "INTERNAL_ERROR",
		},
		{
			name:           "invalid json body",
			approvalID:     "apv_123",
			body:           "invalid json{{{",
			expectedStatus: http.StatusBadRequest,
			expectedCode:   "VALIDATION_ERROR",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			store := &mockApprovalStore{
				getApprovalFn:    tt.mockGet,
				updateApprovalFn: tt.mockUpdate,
			}
			_, router := setupApprovalTestHandler(store)

			var body []byte
			if tt.body != nil {
				switch v := tt.body.(type) {
				case string:
					body = []byte(v)
				default:
					var err error
					body, err = json.Marshal(tt.body)
					if err != nil {
						t.Fatalf("Failed to marshal body: %v", err)
					}
				}
			}

			req := httptest.NewRequest(http.MethodPost, "/v1/approvals/"+tt.approvalID+"/approve", bytes.NewReader(body))
			req = addApprovalRequestID(req)
			if len(body) > 0 {
				req.Header.Set("Content-Type", "application/json")
			}
			rec := httptest.NewRecorder()

			router.ServeHTTP(rec, req)

			if rec.Code != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d. Body: %s", tt.expectedStatus, rec.Code, rec.Body.String())
			}

			var resp map[string]interface{}
			if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
				t.Fatalf("Failed to parse response: %v", err)
			}

			if tt.expectedStatus == http.StatusOK {
				if resp["success"] != true {
					t.Error("Expected success to be true")
				}
				if data, ok := resp["data"].(map[string]interface{}); ok {
					if data["status"] != string(models.ApprovalStatusApproved) {
						t.Errorf("Expected status approved, got %v", data["status"])
					}
				}
			} else {
				if resp["success"] != false {
					t.Error("Expected success to be false")
				}
				if errObj, ok := resp["error"].(map[string]interface{}); ok {
					if errObj["code"] != tt.expectedCode {
						t.Errorf("Expected error code %s, got %v", tt.expectedCode, errObj["code"])
					}
				}
			}
		})
	}
}

// TestApprovalsHandler_Deny tests the Deny endpoint.
func TestApprovalsHandler_Deny(t *testing.T) {
	now := time.Now().UTC()
	pendingApproval := &models.Approval{
		ID:          "apv_123",
		JobID:       "job_456",
		ToolCallID:  "tc_789",
		Tool:        "bash",
		Resource:    "/usr/bin/ls",
		Status:      models.ApprovalStatusPending,
		RequestedBy: "user_001",
		RequestedAt: now,
	}

	rejectedApproval := &models.Approval{
		ID:          "apv_already",
		JobID:       "job_456",
		ToolCallID:  "tc_789",
		Tool:        "bash",
		Resource:    "/usr/bin/ls",
		Status:      models.ApprovalStatusRejected,
		RequestedBy: "user_001",
		RequestedAt: now,
		DecidedBy:   sql.NullString{String: "admin", Valid: true},
		DecidedAt:   sql.NullTime{Time: now, Valid: true},
	}

	tests := []struct {
		name           string
		approvalID     string
		body           interface{}
		mockGet        func(ctx context.Context, id string) (*models.Approval, error)
		mockUpdate     func(ctx context.Context, approval *models.Approval) error
		expectedStatus int
		expectedCode   string
	}{
		{
			name:       "success - no body",
			approvalID: "apv_123",
			body:       nil,
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				cp := *pendingApproval
				return &cp, nil
			},
			mockUpdate: func(ctx context.Context, approval *models.Approval) error {
				if approval.Status != models.ApprovalStatusRejected {
					t.Errorf("Expected status rejected, got %s", approval.Status)
				}
				if !approval.DecidedBy.Valid {
					t.Error("Expected DecidedBy to be set")
				}
				if !approval.DecidedAt.Valid {
					t.Error("Expected DecidedAt to be set")
				}
				return nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:       "success - with comment",
			approvalID: "apv_123",
			body: map[string]string{
				"comment": "Denied - security concern",
			},
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				cp := *pendingApproval
				return &cp, nil
			},
			mockUpdate: func(ctx context.Context, approval *models.Approval) error {
				if !approval.Comment.Valid || approval.Comment.String != "Denied - security concern" {
					t.Errorf("Expected comment to be set, got %v", approval.Comment)
				}
				return nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:       "success - with decided_by",
			approvalID: "apv_123",
			body: map[string]string{
				"decided_by": "security_admin",
			},
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				cp := *pendingApproval
				return &cp, nil
			},
			mockUpdate: func(ctx context.Context, approval *models.Approval) error {
				if !approval.DecidedBy.Valid || approval.DecidedBy.String != "security_admin" {
					t.Errorf("Expected decided_by to be security_admin, got %v", approval.DecidedBy)
				}
				return nil
			},
			expectedStatus: http.StatusOK,
		},
		{
			name:       "not found",
			approvalID: "apv_notfound",
			body:       nil,
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				return nil, postgres.ErrNotFound
			},
			expectedStatus: http.StatusNotFound,
			expectedCode:   "NOT_FOUND",
		},
		{
			name:       "already decided",
			approvalID: "apv_already",
			body:       nil,
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				return rejectedApproval, nil
			},
			expectedStatus: http.StatusBadRequest,
			expectedCode:   "VALIDATION_ERROR",
		},
		{
			name:       "storage error on get",
			approvalID: "apv_123",
			body:       nil,
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				return nil, errors.New("database error")
			},
			expectedStatus: http.StatusInternalServerError,
			expectedCode:   "INTERNAL_ERROR",
		},
		{
			name:       "storage error on update",
			approvalID: "apv_123",
			body:       nil,
			mockGet: func(ctx context.Context, id string) (*models.Approval, error) {
				cp := *pendingApproval
				return &cp, nil
			},
			mockUpdate: func(ctx context.Context, approval *models.Approval) error {
				return errors.New("database error")
			},
			expectedStatus: http.StatusInternalServerError,
			expectedCode:   "INTERNAL_ERROR",
		},
		{
			name:           "invalid json body",
			approvalID:     "apv_123",
			body:           "invalid json{{{",
			expectedStatus: http.StatusBadRequest,
			expectedCode:   "VALIDATION_ERROR",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			store := &mockApprovalStore{
				getApprovalFn:    tt.mockGet,
				updateApprovalFn: tt.mockUpdate,
			}
			_, router := setupApprovalTestHandler(store)

			var body []byte
			if tt.body != nil {
				switch v := tt.body.(type) {
				case string:
					body = []byte(v)
				default:
					var err error
					body, err = json.Marshal(tt.body)
					if err != nil {
						t.Fatalf("Failed to marshal body: %v", err)
					}
				}
			}

			req := httptest.NewRequest(http.MethodPost, "/v1/approvals/"+tt.approvalID+"/deny", bytes.NewReader(body))
			req = addApprovalRequestID(req)
			if len(body) > 0 {
				req.Header.Set("Content-Type", "application/json")
			}
			rec := httptest.NewRecorder()

			router.ServeHTTP(rec, req)

			if rec.Code != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d. Body: %s", tt.expectedStatus, rec.Code, rec.Body.String())
			}

			var resp map[string]interface{}
			if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
				t.Fatalf("Failed to parse response: %v", err)
			}

			if tt.expectedStatus == http.StatusOK {
				if resp["success"] != true {
					t.Error("Expected success to be true")
				}
				if data, ok := resp["data"].(map[string]interface{}); ok {
					if data["status"] != string(models.ApprovalStatusRejected) {
						t.Errorf("Expected status rejected, got %v", data["status"])
					}
				}
			} else {
				if resp["success"] != false {
					t.Error("Expected success to be false")
				}
				if errObj, ok := resp["error"].(map[string]interface{}); ok {
					if errObj["code"] != tt.expectedCode {
						t.Errorf("Expected error code %s, got %v", tt.expectedCode, errObj["code"])
					}
				}
			}
		})
	}
}

// TestApprovalsHandler_ResponseFormat tests that responses follow v1 envelope format.
func TestApprovalsHandler_ResponseFormat(t *testing.T) {
	store := &mockApprovalStore{
		listApprovalsFn: func(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
			return &models.ApprovalList{Approvals: []models.Approval{}}, nil
		},
	}
	_, router := setupApprovalTestHandler(store)

	req := httptest.NewRequest(http.MethodGet, "/v1/approvals", nil)
	req = addApprovalRequestID(req)
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	var resp response.SuccessResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("Failed to parse response: %v", err)
	}

	// Verify v1 envelope structure
	if !resp.Success {
		t.Error("Expected success to be true")
	}
	if resp.Data == nil {
		t.Error("Expected data to be present")
	}
	if resp.Meta.RequestID == "" {
		t.Error("Expected request_id in meta")
	}
	if resp.Meta.Timestamp == "" {
		t.Error("Expected timestamp in meta")
	}
}

// TestApprovalsHandler_ErrorResponseFormat tests that error responses follow v1 envelope format.
func TestApprovalsHandler_ErrorResponseFormat(t *testing.T) {
	store := &mockApprovalStore{
		getApprovalFn: func(ctx context.Context, id string) (*models.Approval, error) {
			return nil, postgres.ErrNotFound
		},
	}
	_, router := setupApprovalTestHandler(store)

	req := httptest.NewRequest(http.MethodGet, "/v1/approvals/nonexistent", nil)
	req = addApprovalRequestID(req)
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	var resp response.ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("Failed to parse response: %v", err)
	}

	// Verify v1 error envelope structure
	if resp.Success {
		t.Error("Expected success to be false")
	}
	if resp.Error.Code == "" {
		t.Error("Expected error code")
	}
	if resp.Error.Message == "" {
		t.Error("Expected error message")
	}
	if resp.Meta.RequestID == "" {
		t.Error("Expected request_id in meta")
	}
	if resp.Meta.Timestamp == "" {
		t.Error("Expected timestamp in meta")
	}
}

// TestApprovalsHandler_Approve_EmptyBody tests approve with empty body.
func TestApprovalsHandler_Approve_EmptyBody(t *testing.T) {
	now := time.Now().UTC()
	pendingApproval := &models.Approval{
		ID:          "apv_123",
		Status:      models.ApprovalStatusPending,
		RequestedAt: now,
	}

	store := &mockApprovalStore{
		getApprovalFn: func(ctx context.Context, id string) (*models.Approval, error) {
			cp := *pendingApproval
			return &cp, nil
		},
		updateApprovalFn: func(ctx context.Context, approval *models.Approval) error {
			// Should use default decided_by
			if !approval.DecidedBy.Valid || approval.DecidedBy.String != "system" {
				t.Errorf("Expected default decided_by 'system', got %v", approval.DecidedBy)
			}
			return nil
		},
	}
	_, router := setupApprovalTestHandler(store)

	// Request with no body at all
	req := httptest.NewRequest(http.MethodPost, "/v1/approvals/apv_123/approve", nil)
	req = addApprovalRequestID(req)
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d. Body: %s", rec.Code, rec.Body.String())
	}
}

// TestApprovalsHandler_Deny_EmptyBody tests deny with empty body.
func TestApprovalsHandler_Deny_EmptyBody(t *testing.T) {
	now := time.Now().UTC()
	pendingApproval := &models.Approval{
		ID:          "apv_123",
		Status:      models.ApprovalStatusPending,
		RequestedAt: now,
	}

	store := &mockApprovalStore{
		getApprovalFn: func(ctx context.Context, id string) (*models.Approval, error) {
			cp := *pendingApproval
			return &cp, nil
		},
		updateApprovalFn: func(ctx context.Context, approval *models.Approval) error {
			// Should use default decided_by
			if !approval.DecidedBy.Valid || approval.DecidedBy.String != "system" {
				t.Errorf("Expected default decided_by 'system', got %v", approval.DecidedBy)
			}
			return nil
		},
	}
	_, router := setupApprovalTestHandler(store)

	// Request with no body at all
	req := httptest.NewRequest(http.MethodPost, "/v1/approvals/apv_123/deny", nil)
	req = addApprovalRequestID(req)
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d. Body: %s", rec.Code, rec.Body.String())
	}
}
