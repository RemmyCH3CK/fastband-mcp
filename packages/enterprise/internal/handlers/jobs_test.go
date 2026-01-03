package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/models"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/requestid"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage/postgres"
)

// mockPostgresStore is a mock implementation of storage.PostgresStore for testing.
type mockPostgresStore struct {
	getJobFunc    func(ctx context.Context, id string) (*models.Job, error)
	updateJobFunc func(ctx context.Context, job *models.Job) error
}

func (m *mockPostgresStore) Ping(ctx context.Context) error { return nil }
func (m *mockPostgresStore) CreateTicket(ctx context.Context, ticket *models.Ticket) error {
	return nil
}
func (m *mockPostgresStore) GetTicket(ctx context.Context, id string) (*models.Ticket, error) {
	return nil, nil
}
func (m *mockPostgresStore) UpdateTicket(ctx context.Context, ticket *models.Ticket) error {
	return nil
}
func (m *mockPostgresStore) DeleteTicket(ctx context.Context, id string) error { return nil }
func (m *mockPostgresStore) ListTickets(ctx context.Context, filter models.TicketFilter) (*models.TicketList, error) {
	return nil, nil
}
func (m *mockPostgresStore) CreateJob(ctx context.Context, job *models.Job) error { return nil }
func (m *mockPostgresStore) GetJob(ctx context.Context, id string) (*models.Job, error) {
	if m.getJobFunc != nil {
		return m.getJobFunc(ctx, id)
	}
	return nil, nil
}
func (m *mockPostgresStore) UpdateJob(ctx context.Context, job *models.Job) error {
	if m.updateJobFunc != nil {
		return m.updateJobFunc(ctx, job)
	}
	return nil
}
func (m *mockPostgresStore) ListJobs(ctx context.Context, filter models.JobFilter) (*models.JobList, error) {
	return nil, nil
}
func (m *mockPostgresStore) CreateApproval(ctx context.Context, approval *models.Approval) error {
	return nil
}
func (m *mockPostgresStore) GetApproval(ctx context.Context, id string) (*models.Approval, error) {
	return nil, nil
}
func (m *mockPostgresStore) UpdateApproval(ctx context.Context, approval *models.Approval) error {
	return nil
}
func (m *mockPostgresStore) ListApprovals(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
	return nil, nil
}
func (m *mockPostgresStore) CreateAuditRecord(ctx context.Context, record *models.AuditRecord) error {
	return nil
}
func (m *mockPostgresStore) GetAuditRecord(ctx context.Context, id string) (*models.AuditRecord, error) {
	return nil, nil
}
func (m *mockPostgresStore) ListAuditRecords(ctx context.Context, filter models.AuditFilter) (*models.AuditList, error) {
	return nil, nil
}

func TestNewJobsHandler(t *testing.T) {
	store := &mockPostgresStore{}
	log := slog.Default()
	handler := NewJobsHandler(store, log)

	if handler == nil {
		t.Fatal("expected handler to not be nil")
	}
	if handler.store != store {
		t.Error("expected store to be set")
	}
	if handler.log != log {
		t.Error("expected log to be set")
	}
}

func TestJobsHandler_Get_Success(t *testing.T) {
	expectedJob := &models.Job{
		ID:        "job_123",
		TicketID:  "ticket_456",
		Status:    models.JobStatusQueued,
		CreatedAt: time.Now().UTC(),
	}

	store := &mockPostgresStore{
		getJobFunc: func(ctx context.Context, id string) (*models.Job, error) {
			if id != "job_123" {
				t.Errorf("expected job_123, got %s", id)
			}
			return expectedJob, nil
		},
	}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Get("/v1/jobs/{jobID}", handler.Get)

	req := httptest.NewRequest(http.MethodGet, "/v1/jobs/job_123", nil)
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rec.Code)
	}

	var resp response.SuccessResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if !resp.Success {
		t.Error("expected success to be true")
	}
	if resp.Meta.RequestID == "" {
		t.Error("expected request_id to be set")
	}

	// Verify data contains job
	data, ok := resp.Data.(map[string]interface{})
	if !ok {
		t.Fatal("expected data to be a map")
	}
	if data["id"] != "job_123" {
		t.Errorf("expected job id job_123, got %v", data["id"])
	}
}

func TestJobsHandler_Get_NotFound(t *testing.T) {
	store := &mockPostgresStore{
		getJobFunc: func(ctx context.Context, id string) (*models.Job, error) {
			return nil, postgres.ErrNotFound
		},
	}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Get("/v1/jobs/{jobID}", handler.Get)

	req := httptest.NewRequest(http.MethodGet, "/v1/jobs/nonexistent", nil)
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected status %d, got %d", http.StatusNotFound, rec.Code)
	}

	var resp response.ErrorResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Success {
		t.Error("expected success to be false")
	}
	if resp.Error.Code != "NOT_FOUND" {
		t.Errorf("expected error code NOT_FOUND, got %s", resp.Error.Code)
	}
}

func TestJobsHandler_Get_InternalError(t *testing.T) {
	store := &mockPostgresStore{
		getJobFunc: func(ctx context.Context, id string) (*models.Job, error) {
			return nil, errors.New("database connection failed")
		},
	}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Get("/v1/jobs/{jobID}", handler.Get)

	req := httptest.NewRequest(http.MethodGet, "/v1/jobs/job_123", nil)
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected status %d, got %d", http.StatusInternalServerError, rec.Code)
	}

	var resp response.ErrorResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Success {
		t.Error("expected success to be false")
	}
	if resp.Error.Code != "INTERNAL_ERROR" {
		t.Errorf("expected error code INTERNAL_ERROR, got %s", resp.Error.Code)
	}
}

func TestJobsHandler_Update_Success(t *testing.T) {
	existingJob := &models.Job{
		ID:        "job_123",
		TicketID:  "ticket_456",
		Status:    models.JobStatusQueued,
		CreatedAt: time.Now().UTC(),
	}

	var updatedJob *models.Job

	store := &mockPostgresStore{
		getJobFunc: func(ctx context.Context, id string) (*models.Job, error) {
			// Return a copy to avoid mutation issues
			jobCopy := *existingJob
			return &jobCopy, nil
		},
		updateJobFunc: func(ctx context.Context, job *models.Job) error {
			updatedJob = job
			return nil
		},
	}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Patch("/v1/jobs/{jobID}", handler.Update)

	status := models.JobStatusRunning
	body := UpdateJobRequest{
		Status: &status,
	}
	bodyBytes, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPatch, "/v1/jobs/job_123", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rec.Code)
	}

	var resp response.SuccessResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if !resp.Success {
		t.Error("expected success to be true")
	}

	if updatedJob == nil {
		t.Fatal("expected job to be updated")
	}
	if updatedJob.Status != models.JobStatusRunning {
		t.Errorf("expected status running, got %s", updatedJob.Status)
	}
}

func TestJobsHandler_Update_WithExecutionNode(t *testing.T) {
	existingJob := &models.Job{
		ID:        "job_123",
		TicketID:  "ticket_456",
		Status:    models.JobStatusQueued,
		CreatedAt: time.Now().UTC(),
	}

	var updatedJob *models.Job

	store := &mockPostgresStore{
		getJobFunc: func(ctx context.Context, id string) (*models.Job, error) {
			jobCopy := *existingJob
			return &jobCopy, nil
		},
		updateJobFunc: func(ctx context.Context, job *models.Job) error {
			updatedJob = job
			return nil
		},
	}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Patch("/v1/jobs/{jobID}", handler.Update)

	execNode := "node-1"
	body := UpdateJobRequest{
		ExecutionNode: &execNode,
	}
	bodyBytes, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPatch, "/v1/jobs/job_123", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rec.Code)
	}

	if updatedJob == nil {
		t.Fatal("expected job to be updated")
	}
	if !updatedJob.ExecutionNode.Valid || updatedJob.ExecutionNode.String != "node-1" {
		t.Errorf("expected execution_node node-1, got %s", updatedJob.ExecutionNode.String)
	}
}

func TestJobsHandler_Update_WithContextAndResult(t *testing.T) {
	existingJob := &models.Job{
		ID:        "job_123",
		TicketID:  "ticket_456",
		Status:    models.JobStatusRunning,
		CreatedAt: time.Now().UTC(),
	}

	var updatedJob *models.Job

	store := &mockPostgresStore{
		getJobFunc: func(ctx context.Context, id string) (*models.Job, error) {
			jobCopy := *existingJob
			return &jobCopy, nil
		},
		updateJobFunc: func(ctx context.Context, job *models.Job) error {
			updatedJob = job
			return nil
		},
	}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Patch("/v1/jobs/{jobID}", handler.Update)

	body := UpdateJobRequest{
		Context: map[string]interface{}{"key": "value"},
		Result:  map[string]interface{}{"output": "success"},
	}
	bodyBytes, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPatch, "/v1/jobs/job_123", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rec.Code)
	}

	if updatedJob == nil {
		t.Fatal("expected job to be updated")
	}
	if updatedJob.Context["key"] != "value" {
		t.Errorf("expected context key=value, got %v", updatedJob.Context)
	}
	if updatedJob.Result["output"] != "success" {
		t.Errorf("expected result output=success, got %v", updatedJob.Result)
	}
}

func TestJobsHandler_Update_InvalidJSON(t *testing.T) {
	store := &mockPostgresStore{}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Patch("/v1/jobs/{jobID}", handler.Update)

	req := httptest.NewRequest(http.MethodPatch, "/v1/jobs/job_123", bytes.NewReader([]byte("invalid json")))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rec.Code)
	}

	var resp response.ErrorResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Error.Code != "VALIDATION_ERROR" {
		t.Errorf("expected error code VALIDATION_ERROR, got %s", resp.Error.Code)
	}
}

func TestJobsHandler_Update_NoFieldsProvided(t *testing.T) {
	store := &mockPostgresStore{}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Patch("/v1/jobs/{jobID}", handler.Update)

	body := UpdateJobRequest{}
	bodyBytes, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPatch, "/v1/jobs/job_123", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rec.Code)
	}

	var resp response.ErrorResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Error.Code != "VALIDATION_ERROR" {
		t.Errorf("expected error code VALIDATION_ERROR, got %s", resp.Error.Code)
	}
}

func TestJobsHandler_Update_InvalidStatus(t *testing.T) {
	store := &mockPostgresStore{}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Patch("/v1/jobs/{jobID}", handler.Update)

	invalidStatus := models.JobStatus("invalid_status")
	body := UpdateJobRequest{
		Status: &invalidStatus,
	}
	bodyBytes, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPatch, "/v1/jobs/job_123", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rec.Code)
	}

	var resp response.ErrorResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Error.Code != "VALIDATION_ERROR" {
		t.Errorf("expected error code VALIDATION_ERROR, got %s", resp.Error.Code)
	}
	if resp.Error.Details["status"] != "invalid_status" {
		t.Errorf("expected status in details, got %v", resp.Error.Details)
	}
}

func TestJobsHandler_Update_NotFound(t *testing.T) {
	store := &mockPostgresStore{
		getJobFunc: func(ctx context.Context, id string) (*models.Job, error) {
			return nil, postgres.ErrNotFound
		},
	}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Patch("/v1/jobs/{jobID}", handler.Update)

	status := models.JobStatusRunning
	body := UpdateJobRequest{
		Status: &status,
	}
	bodyBytes, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPatch, "/v1/jobs/job_123", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected status %d, got %d", http.StatusNotFound, rec.Code)
	}

	var resp response.ErrorResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Error.Code != "NOT_FOUND" {
		t.Errorf("expected error code NOT_FOUND, got %s", resp.Error.Code)
	}
}

func TestJobsHandler_Update_UpdateFailsNotFound(t *testing.T) {
	existingJob := &models.Job{
		ID:        "job_123",
		TicketID:  "ticket_456",
		Status:    models.JobStatusQueued,
		CreatedAt: time.Now().UTC(),
	}

	store := &mockPostgresStore{
		getJobFunc: func(ctx context.Context, id string) (*models.Job, error) {
			jobCopy := *existingJob
			return &jobCopy, nil
		},
		updateJobFunc: func(ctx context.Context, job *models.Job) error {
			return postgres.ErrNotFound
		},
	}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Patch("/v1/jobs/{jobID}", handler.Update)

	status := models.JobStatusRunning
	body := UpdateJobRequest{
		Status: &status,
	}
	bodyBytes, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPatch, "/v1/jobs/job_123", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected status %d, got %d", http.StatusNotFound, rec.Code)
	}
}

func TestJobsHandler_Update_InternalError(t *testing.T) {
	existingJob := &models.Job{
		ID:        "job_123",
		TicketID:  "ticket_456",
		Status:    models.JobStatusQueued,
		CreatedAt: time.Now().UTC(),
	}

	store := &mockPostgresStore{
		getJobFunc: func(ctx context.Context, id string) (*models.Job, error) {
			jobCopy := *existingJob
			return &jobCopy, nil
		},
		updateJobFunc: func(ctx context.Context, job *models.Job) error {
			return errors.New("database error")
		},
	}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Patch("/v1/jobs/{jobID}", handler.Update)

	status := models.JobStatusRunning
	body := UpdateJobRequest{
		Status: &status,
	}
	bodyBytes, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPatch, "/v1/jobs/job_123", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected status %d, got %d", http.StatusInternalServerError, rec.Code)
	}

	var resp response.ErrorResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Error.Code != "INTERNAL_ERROR" {
		t.Errorf("expected error code INTERNAL_ERROR, got %s", resp.Error.Code)
	}
}

func TestJobsHandler_Update_GetJobInternalError(t *testing.T) {
	store := &mockPostgresStore{
		getJobFunc: func(ctx context.Context, id string) (*models.Job, error) {
			return nil, errors.New("database connection failed")
		},
	}

	handler := NewJobsHandler(store, slog.Default())
	router := chi.NewRouter()
	router.Use(requestid.Middleware)
	router.Patch("/v1/jobs/{jobID}", handler.Update)

	status := models.JobStatusRunning
	body := UpdateJobRequest{
		Status: &status,
	}
	bodyBytes, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPatch, "/v1/jobs/job_123", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected status %d, got %d", http.StatusInternalServerError, rec.Code)
	}
}

func TestJobsHandler_Routes(t *testing.T) {
	store := &mockPostgresStore{}
	handler := NewJobsHandler(store, slog.Default())
	router := handler.Routes()

	if router == nil {
		t.Fatal("expected router to not be nil")
	}
}

func TestIsValidJobStatus(t *testing.T) {
	tests := []struct {
		status   models.JobStatus
		expected bool
	}{
		{models.JobStatusQueued, true},
		{models.JobStatusRunning, true},
		{models.JobStatusCompleted, true},
		{models.JobStatusFailed, true},
		{models.JobStatusCancelled, true},
		{models.JobStatus("invalid"), false},
		{models.JobStatus(""), false},
	}

	for _, tt := range tests {
		t.Run(string(tt.status), func(t *testing.T) {
			result := isValidJobStatus(tt.status)
			if result != tt.expected {
				t.Errorf("isValidJobStatus(%s) = %v, want %v", tt.status, result, tt.expected)
			}
		})
	}
}
