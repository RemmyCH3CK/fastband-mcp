package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/models"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage/postgres"
)

// mockAuditStore implements storage.PostgresStore for testing audit handlers.
type mockAuditStore struct {
	createErr     error
	getErr        error
	listErr       error
	createdRecord *models.AuditRecord
	getRecord     *models.AuditRecord
	listResult    *models.AuditList
	lastFilter    models.AuditFilter
}

// Implement PostgresStore interface - only audit methods are used in tests

func (m *mockAuditStore) Ping(ctx context.Context) error { return nil }

func (m *mockAuditStore) CreateTicket(ctx context.Context, ticket *models.Ticket) error {
	return nil
}
func (m *mockAuditStore) GetTicket(ctx context.Context, id string) (*models.Ticket, error) {
	return nil, nil
}
func (m *mockAuditStore) UpdateTicket(ctx context.Context, ticket *models.Ticket) error {
	return nil
}
func (m *mockAuditStore) DeleteTicket(ctx context.Context, id string) error { return nil }
func (m *mockAuditStore) ListTickets(ctx context.Context, filter models.TicketFilter) (*models.TicketList, error) {
	return nil, nil
}

func (m *mockAuditStore) CreateJob(ctx context.Context, job *models.Job) error { return nil }
func (m *mockAuditStore) GetJob(ctx context.Context, id string) (*models.Job, error) {
	return nil, nil
}
func (m *mockAuditStore) UpdateJob(ctx context.Context, job *models.Job) error { return nil }
func (m *mockAuditStore) ListJobs(ctx context.Context, filter models.JobFilter) (*models.JobList, error) {
	return nil, nil
}

func (m *mockAuditStore) CreateApproval(ctx context.Context, approval *models.Approval) error {
	return nil
}
func (m *mockAuditStore) GetApproval(ctx context.Context, id string) (*models.Approval, error) {
	return nil, nil
}
func (m *mockAuditStore) UpdateApproval(ctx context.Context, approval *models.Approval) error {
	return nil
}
func (m *mockAuditStore) ListApprovals(ctx context.Context, filter models.ApprovalFilter) (*models.ApprovalList, error) {
	return nil, nil
}

func (m *mockAuditStore) CreateAuditRecord(ctx context.Context, record *models.AuditRecord) error {
	m.createdRecord = record
	return m.createErr
}

func (m *mockAuditStore) GetAuditRecord(ctx context.Context, id string) (*models.AuditRecord, error) {
	if m.getErr != nil {
		return nil, m.getErr
	}
	return m.getRecord, nil
}

func (m *mockAuditStore) ListAuditRecords(ctx context.Context, filter models.AuditFilter) (*models.AuditList, error) {
	m.lastFilter = filter
	if m.listErr != nil {
		return nil, m.listErr
	}
	return m.listResult, nil
}

func newTestLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
}

func TestAuditHandler_Create_Success(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, newTestLogger())

	body := CreateAuditRecordRequest{
		EventType:    "user.login",
		Category:     models.EventCategorySecurity,
		Severity:     models.EventSeverityInfo,
		ActorID:      "user-123",
		ActorType:    models.ActorTypeUser,
		Action:       "login",
		ResourceID:   "session-456",
		ResourceType: "session",
		WorkspaceID:  "ws-789",
		Outcome:      models.EventOutcomeSuccess,
		Context:      map[string]interface{}{"ip": "192.168.1.1"},
		Details:      map[string]interface{}{"method": "password"},
	}

	bodyJSON, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/v1/audit", bytes.NewReader(bodyJSON))
	req.Header.Set("Content-Type", "application/json")
	rr := httptest.NewRecorder()

	handler.Create(rr, req)

	if rr.Code != http.StatusCreated {
		t.Errorf("expected status %d, got %d", http.StatusCreated, rr.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if !resp["success"].(bool) {
		t.Error("expected success to be true")
	}

	data := resp["data"].(map[string]interface{})
	if data["event_type"] != "user.login" {
		t.Errorf("expected event_type to be 'user.login', got '%s'", data["event_type"])
	}
	if data["category"] != "security" {
		t.Errorf("expected category to be 'security', got '%s'", data["category"])
	}

	// Verify store was called
	if store.createdRecord == nil {
		t.Error("expected store.CreateAuditRecord to be called")
	}
	if store.createdRecord.EventType != "user.login" {
		t.Errorf("expected created record event_type to be 'user.login', got '%s'", store.createdRecord.EventType)
	}
}

func TestAuditHandler_Create_WithTimestamp(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, newTestLogger())

	customTime := time.Date(2024, 1, 15, 10, 30, 0, 0, time.UTC)
	body := CreateAuditRecordRequest{
		EventType:    "user.login",
		Category:     models.EventCategorySecurity,
		Severity:     models.EventSeverityInfo,
		ActorID:      "user-123",
		ActorType:    models.ActorTypeUser,
		Action:       "login",
		ResourceID:   "session-456",
		ResourceType: "session",
		WorkspaceID:  "ws-789",
		Outcome:      models.EventOutcomeSuccess,
		Timestamp:    &customTime,
	}

	bodyJSON, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/v1/audit", bytes.NewReader(bodyJSON))
	req.Header.Set("Content-Type", "application/json")
	rr := httptest.NewRecorder()

	handler.Create(rr, req)

	if rr.Code != http.StatusCreated {
		t.Errorf("expected status %d, got %d", http.StatusCreated, rr.Code)
	}

	// Verify timestamp was set correctly
	if store.createdRecord == nil {
		t.Fatal("expected store.CreateAuditRecord to be called")
	}
	if !store.createdRecord.Timestamp.Equal(customTime) {
		t.Errorf("expected timestamp to be %v, got %v", customTime, store.createdRecord.Timestamp)
	}
}

func TestAuditHandler_Create_ValidationError_MissingFields(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, newTestLogger())

	// Empty request - all required fields missing
	body := CreateAuditRecordRequest{}
	bodyJSON, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/v1/audit", bytes.NewReader(bodyJSON))
	req.Header.Set("Content-Type", "application/json")
	rr := httptest.NewRecorder()

	handler.Create(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp["success"].(bool) {
		t.Error("expected success to be false")
	}

	errObj := resp["error"].(map[string]interface{})
	if errObj["code"] != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got '%s'", errObj["code"])
	}

	details := errObj["details"].(map[string]interface{})
	fields := details["fields"].([]interface{})
	if len(fields) < 10 {
		t.Errorf("expected at least 10 validation errors, got %d", len(fields))
	}
}

func TestAuditHandler_Create_ValidationError_InvalidCategory(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, newTestLogger())

	body := CreateAuditRecordRequest{
		EventType:    "user.login",
		Category:     models.EventCategory("invalid"),
		Severity:     models.EventSeverityInfo,
		ActorID:      "user-123",
		ActorType:    models.ActorTypeUser,
		Action:       "login",
		ResourceID:   "session-456",
		ResourceType: "session",
		WorkspaceID:  "ws-789",
		Outcome:      models.EventOutcomeSuccess,
	}

	bodyJSON, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/v1/audit", bytes.NewReader(bodyJSON))
	req.Header.Set("Content-Type", "application/json")
	rr := httptest.NewRecorder()

	handler.Create(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	errObj := resp["error"].(map[string]interface{})
	if errObj["code"] != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got '%s'", errObj["code"])
	}
}

func TestAuditHandler_Create_InvalidJSON(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodPost, "/v1/audit", bytes.NewReader([]byte("{invalid json")))
	req.Header.Set("Content-Type", "application/json")
	rr := httptest.NewRecorder()

	handler.Create(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	errObj := resp["error"].(map[string]interface{})
	if errObj["code"] != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got '%s'", errObj["code"])
	}
}

func TestAuditHandler_Create_StoreError(t *testing.T) {
	store := &mockAuditStore{
		createErr: postgres.ErrNotFound, // Using any error to simulate failure
	}
	handler := NewAuditHandler(store, newTestLogger())

	body := CreateAuditRecordRequest{
		EventType:    "user.login",
		Category:     models.EventCategorySecurity,
		Severity:     models.EventSeverityInfo,
		ActorID:      "user-123",
		ActorType:    models.ActorTypeUser,
		Action:       "login",
		ResourceID:   "session-456",
		ResourceType: "session",
		WorkspaceID:  "ws-789",
		Outcome:      models.EventOutcomeSuccess,
	}

	bodyJSON, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/v1/audit", bytes.NewReader(bodyJSON))
	req.Header.Set("Content-Type", "application/json")
	rr := httptest.NewRecorder()

	handler.Create(rr, req)

	if rr.Code != http.StatusInternalServerError {
		t.Errorf("expected status %d, got %d", http.StatusInternalServerError, rr.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	errObj := resp["error"].(map[string]interface{})
	if errObj["code"] != "INTERNAL_ERROR" {
		t.Errorf("expected error code 'INTERNAL_ERROR', got '%s'", errObj["code"])
	}
}

func TestAuditHandler_Get_Success(t *testing.T) {
	now := time.Now().UTC()
	store := &mockAuditStore{
		getRecord: &models.AuditRecord{
			ID:           "record-123",
			EventType:    "user.login",
			Category:     models.EventCategorySecurity,
			Severity:     models.EventSeverityInfo,
			ActorID:      "user-123",
			ActorType:    models.ActorTypeUser,
			Action:       "login",
			ResourceID:   "session-456",
			ResourceType: "session",
			WorkspaceID:  "ws-789",
			Outcome:      models.EventOutcomeSuccess,
			Timestamp:    now,
			ReceivedAt:   now,
		},
	}
	handler := NewAuditHandler(store, newTestLogger())

	// Create request with chi URL param
	req := httptest.NewRequest(http.MethodGet, "/v1/audit/record-123", nil)
	rr := httptest.NewRecorder()

	// Set up chi context
	rctx := chi.NewRouteContext()
	rctx.URLParams.Add("recordID", "record-123")
	req = req.WithContext(context.WithValue(req.Context(), chi.RouteCtxKey, rctx))

	handler.Get(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rr.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if !resp["success"].(bool) {
		t.Error("expected success to be true")
	}

	data := resp["data"].(map[string]interface{})
	if data["id"] != "record-123" {
		t.Errorf("expected id to be 'record-123', got '%s'", data["id"])
	}
	if data["event_type"] != "user.login" {
		t.Errorf("expected event_type to be 'user.login', got '%s'", data["event_type"])
	}
}

func TestAuditHandler_Get_NotFound(t *testing.T) {
	store := &mockAuditStore{
		getErr: postgres.ErrNotFound,
	}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit/nonexistent", nil)
	rr := httptest.NewRecorder()

	rctx := chi.NewRouteContext()
	rctx.URLParams.Add("recordID", "nonexistent")
	req = req.WithContext(context.WithValue(req.Context(), chi.RouteCtxKey, rctx))

	handler.Get(rr, req)

	if rr.Code != http.StatusNotFound {
		t.Errorf("expected status %d, got %d", http.StatusNotFound, rr.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	errObj := resp["error"].(map[string]interface{})
	if errObj["code"] != "NOT_FOUND" {
		t.Errorf("expected error code 'NOT_FOUND', got '%s'", errObj["code"])
	}
}

func TestAuditHandler_Get_InternalError(t *testing.T) {
	store := &mockAuditStore{
		getErr: postgres.ErrInvalidCursor, // Using a different error
	}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit/record-123", nil)
	rr := httptest.NewRecorder()

	rctx := chi.NewRouteContext()
	rctx.URLParams.Add("recordID", "record-123")
	req = req.WithContext(context.WithValue(req.Context(), chi.RouteCtxKey, rctx))

	handler.Get(rr, req)

	if rr.Code != http.StatusInternalServerError {
		t.Errorf("expected status %d, got %d", http.StatusInternalServerError, rr.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	errObj := resp["error"].(map[string]interface{})
	if errObj["code"] != "INTERNAL_ERROR" {
		t.Errorf("expected error code 'INTERNAL_ERROR', got '%s'", errObj["code"])
	}
}

func TestAuditHandler_List_Success(t *testing.T) {
	now := time.Now().UTC()
	store := &mockAuditStore{
		listResult: &models.AuditList{
			Records: []models.AuditRecord{
				{
					ID:           "record-1",
					EventType:    "user.login",
					Category:     models.EventCategorySecurity,
					Severity:     models.EventSeverityInfo,
					ActorID:      "user-123",
					ActorType:    models.ActorTypeUser,
					Action:       "login",
					ResourceID:   "session-1",
					ResourceType: "session",
					WorkspaceID:  "ws-789",
					Outcome:      models.EventOutcomeSuccess,
					Timestamp:    now,
					ReceivedAt:   now,
				},
				{
					ID:           "record-2",
					EventType:    "user.logout",
					Category:     models.EventCategorySecurity,
					Severity:     models.EventSeverityInfo,
					ActorID:      "user-123",
					ActorType:    models.ActorTypeUser,
					Action:       "logout",
					ResourceID:   "session-1",
					ResourceType: "session",
					WorkspaceID:  "ws-789",
					Outcome:      models.EventOutcomeSuccess,
					Timestamp:    now,
					ReceivedAt:   now,
				},
			},
			PageInfo: models.PageInfo{
				HasNextPage: false,
			},
		},
	}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit", nil)
	rr := httptest.NewRecorder()

	handler.List(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rr.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if !resp["success"].(bool) {
		t.Error("expected success to be true")
	}

	data := resp["data"].(map[string]interface{})
	records := data["records"].([]interface{})
	if len(records) != 2 {
		t.Errorf("expected 2 records, got %d", len(records))
	}
}

func TestAuditHandler_List_WithFilters(t *testing.T) {
	store := &mockAuditStore{
		listResult: &models.AuditList{
			Records:  []models.AuditRecord{},
			PageInfo: models.PageInfo{HasNextPage: false},
		},
	}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit?workspace_id=ws-123&event_type=user.login&category=security&severity=info&actor_id=user-1&actor_type=user&outcome=success&limit=10", nil)
	rr := httptest.NewRecorder()

	handler.List(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rr.Code)
	}

	// Verify filters were passed to store
	if store.lastFilter.WorkspaceID != "ws-123" {
		t.Errorf("expected workspace_id filter 'ws-123', got '%s'", store.lastFilter.WorkspaceID)
	}
	if store.lastFilter.EventType != "user.login" {
		t.Errorf("expected event_type filter 'user.login', got '%s'", store.lastFilter.EventType)
	}
	if store.lastFilter.Category != models.EventCategorySecurity {
		t.Errorf("expected category filter 'security', got '%s'", store.lastFilter.Category)
	}
	if store.lastFilter.Severity != models.EventSeverityInfo {
		t.Errorf("expected severity filter 'info', got '%s'", store.lastFilter.Severity)
	}
	if store.lastFilter.ActorID != "user-1" {
		t.Errorf("expected actor_id filter 'user-1', got '%s'", store.lastFilter.ActorID)
	}
	if store.lastFilter.ActorType != models.ActorTypeUser {
		t.Errorf("expected actor_type filter 'user', got '%s'", store.lastFilter.ActorType)
	}
	if store.lastFilter.Outcome != models.EventOutcomeSuccess {
		t.Errorf("expected outcome filter 'success', got '%s'", store.lastFilter.Outcome)
	}
	if store.lastFilter.Limit != 10 {
		t.Errorf("expected limit filter 10, got %d", store.lastFilter.Limit)
	}
}

func TestAuditHandler_List_TimeRangeFilters(t *testing.T) {
	store := &mockAuditStore{
		listResult: &models.AuditList{
			Records:  []models.AuditRecord{},
			PageInfo: models.PageInfo{HasNextPage: false},
		},
	}
	handler := NewAuditHandler(store, newTestLogger())

	startTime := "2024-01-01T00:00:00Z"
	endTime := "2024-01-31T23:59:59Z"
	req := httptest.NewRequest(http.MethodGet, "/v1/audit?start_time="+startTime+"&end_time="+endTime, nil)
	rr := httptest.NewRecorder()

	handler.List(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, rr.Code)
	}

	// Verify time filters were parsed correctly
	if store.lastFilter.StartTime == nil {
		t.Error("expected start_time filter to be set")
	} else {
		expectedStart := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
		if !store.lastFilter.StartTime.Equal(expectedStart) {
			t.Errorf("expected start_time %v, got %v", expectedStart, *store.lastFilter.StartTime)
		}
	}

	if store.lastFilter.EndTime == nil {
		t.Error("expected end_time filter to be set")
	} else {
		expectedEnd := time.Date(2024, 1, 31, 23, 59, 59, 0, time.UTC)
		if !store.lastFilter.EndTime.Equal(expectedEnd) {
			t.Errorf("expected end_time %v, got %v", expectedEnd, *store.lastFilter.EndTime)
		}
	}
}

func TestAuditHandler_List_InvalidStartTime(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit?start_time=invalid-date", nil)
	rr := httptest.NewRecorder()

	handler.List(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	errObj := resp["error"].(map[string]interface{})
	if errObj["code"] != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got '%s'", errObj["code"])
	}
}

func TestAuditHandler_List_InvalidEndTime(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit?end_time=invalid-date", nil)
	rr := httptest.NewRecorder()

	handler.List(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}
}

func TestAuditHandler_List_InvalidLimit(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit?limit=notanumber", nil)
	rr := httptest.NewRecorder()

	handler.List(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}
}

func TestAuditHandler_List_InvalidCategory(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit?category=invalid", nil)
	rr := httptest.NewRecorder()

	handler.List(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}
}

func TestAuditHandler_List_InvalidSeverity(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit?severity=invalid", nil)
	rr := httptest.NewRecorder()

	handler.List(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}
}

func TestAuditHandler_List_InvalidActorType(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit?actor_type=invalid", nil)
	rr := httptest.NewRecorder()

	handler.List(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}
}

func TestAuditHandler_List_InvalidOutcome(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit?outcome=invalid", nil)
	rr := httptest.NewRecorder()

	handler.List(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}
}

func TestAuditHandler_List_InvalidCursor(t *testing.T) {
	store := &mockAuditStore{
		listErr: postgres.ErrInvalidCursor,
	}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit?cursor=invalid", nil)
	rr := httptest.NewRecorder()

	handler.List(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	errObj := resp["error"].(map[string]interface{})
	if errObj["code"] != "VALIDATION_ERROR" {
		t.Errorf("expected error code 'VALIDATION_ERROR', got '%s'", errObj["code"])
	}
}

func TestAuditHandler_List_InternalError(t *testing.T) {
	store := &mockAuditStore{
		listErr: postgres.ErrNotFound, // Any other error
	}
	handler := NewAuditHandler(store, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/v1/audit", nil)
	rr := httptest.NewRecorder()

	handler.List(rr, req)

	if rr.Code != http.StatusInternalServerError {
		t.Errorf("expected status %d, got %d", http.StatusInternalServerError, rr.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	errObj := resp["error"].(map[string]interface{})
	if errObj["code"] != "INTERNAL_ERROR" {
		t.Errorf("expected error code 'INTERNAL_ERROR', got '%s'", errObj["code"])
	}
}

func TestAuditHandler_Routes(t *testing.T) {
	store := &mockAuditStore{
		listResult: &models.AuditList{
			Records:  []models.AuditRecord{},
			PageInfo: models.PageInfo{},
		},
	}
	handler := NewAuditHandler(store, newTestLogger())
	router := handler.Routes()

	// Test that routes are registered
	if router == nil {
		t.Fatal("expected router to be non-nil")
	}

	// Create a test server with the routes
	r := chi.NewRouter()
	r.Mount("/v1/audit", router)
	ts := httptest.NewServer(r)
	defer ts.Close()

	// Test GET /v1/audit
	resp, err := http.Get(ts.URL + "/v1/audit")
	if err != nil {
		t.Fatalf("failed to make request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Errorf("expected status %d for GET /v1/audit, got %d", http.StatusOK, resp.StatusCode)
	}
}

func TestAuditHandler_NewAuditHandler_NilLogger(t *testing.T) {
	store := &mockAuditStore{}
	handler := NewAuditHandler(store, nil)

	if handler.log == nil {
		t.Error("expected log to be set to default logger when nil is passed")
	}
}

func TestAuditHandler_Create_AllEventCategories(t *testing.T) {
	categories := []models.EventCategory{
		models.EventCategorySecurity,
		models.EventCategoryCompliance,
		models.EventCategoryOperational,
		models.EventCategoryAccess,
		models.EventCategoryData,
	}

	for _, category := range categories {
		t.Run(string(category), func(t *testing.T) {
			store := &mockAuditStore{}
			handler := NewAuditHandler(store, newTestLogger())

			body := CreateAuditRecordRequest{
				EventType:    "test.event",
				Category:     category,
				Severity:     models.EventSeverityInfo,
				ActorID:      "user-123",
				ActorType:    models.ActorTypeUser,
				Action:       "test",
				ResourceID:   "resource-456",
				ResourceType: "resource",
				WorkspaceID:  "ws-789",
				Outcome:      models.EventOutcomeSuccess,
			}

			bodyJSON, _ := json.Marshal(body)
			req := httptest.NewRequest(http.MethodPost, "/v1/audit", bytes.NewReader(bodyJSON))
			req.Header.Set("Content-Type", "application/json")
			rr := httptest.NewRecorder()

			handler.Create(rr, req)

			if rr.Code != http.StatusCreated {
				t.Errorf("expected status %d for category %s, got %d", http.StatusCreated, category, rr.Code)
			}
		})
	}
}

func TestAuditHandler_Create_AllEventSeverities(t *testing.T) {
	severities := []models.EventSeverity{
		models.EventSeverityInfo,
		models.EventSeverityWarning,
		models.EventSeverityError,
		models.EventSeverityCritical,
	}

	for _, severity := range severities {
		t.Run(string(severity), func(t *testing.T) {
			store := &mockAuditStore{}
			handler := NewAuditHandler(store, newTestLogger())

			body := CreateAuditRecordRequest{
				EventType:    "test.event",
				Category:     models.EventCategorySecurity,
				Severity:     severity,
				ActorID:      "user-123",
				ActorType:    models.ActorTypeUser,
				Action:       "test",
				ResourceID:   "resource-456",
				ResourceType: "resource",
				WorkspaceID:  "ws-789",
				Outcome:      models.EventOutcomeSuccess,
			}

			bodyJSON, _ := json.Marshal(body)
			req := httptest.NewRequest(http.MethodPost, "/v1/audit", bytes.NewReader(bodyJSON))
			req.Header.Set("Content-Type", "application/json")
			rr := httptest.NewRecorder()

			handler.Create(rr, req)

			if rr.Code != http.StatusCreated {
				t.Errorf("expected status %d for severity %s, got %d", http.StatusCreated, severity, rr.Code)
			}
		})
	}
}

func TestAuditHandler_Create_AllActorTypes(t *testing.T) {
	actorTypes := []models.ActorType{
		models.ActorTypeUser,
		models.ActorTypeSystem,
		models.ActorTypeAgent,
		models.ActorTypeService,
	}

	for _, actorType := range actorTypes {
		t.Run(string(actorType), func(t *testing.T) {
			store := &mockAuditStore{}
			handler := NewAuditHandler(store, newTestLogger())

			body := CreateAuditRecordRequest{
				EventType:    "test.event",
				Category:     models.EventCategorySecurity,
				Severity:     models.EventSeverityInfo,
				ActorID:      "actor-123",
				ActorType:    actorType,
				Action:       "test",
				ResourceID:   "resource-456",
				ResourceType: "resource",
				WorkspaceID:  "ws-789",
				Outcome:      models.EventOutcomeSuccess,
			}

			bodyJSON, _ := json.Marshal(body)
			req := httptest.NewRequest(http.MethodPost, "/v1/audit", bytes.NewReader(bodyJSON))
			req.Header.Set("Content-Type", "application/json")
			rr := httptest.NewRecorder()

			handler.Create(rr, req)

			if rr.Code != http.StatusCreated {
				t.Errorf("expected status %d for actor_type %s, got %d", http.StatusCreated, actorType, rr.Code)
			}
		})
	}
}

func TestAuditHandler_Create_AllEventOutcomes(t *testing.T) {
	outcomes := []models.EventOutcome{
		models.EventOutcomeSuccess,
		models.EventOutcomeFailure,
		models.EventOutcomePending,
	}

	for _, outcome := range outcomes {
		t.Run(string(outcome), func(t *testing.T) {
			store := &mockAuditStore{}
			handler := NewAuditHandler(store, newTestLogger())

			body := CreateAuditRecordRequest{
				EventType:    "test.event",
				Category:     models.EventCategorySecurity,
				Severity:     models.EventSeverityInfo,
				ActorID:      "user-123",
				ActorType:    models.ActorTypeUser,
				Action:       "test",
				ResourceID:   "resource-456",
				ResourceType: "resource",
				WorkspaceID:  "ws-789",
				Outcome:      outcome,
			}

			bodyJSON, _ := json.Marshal(body)
			req := httptest.NewRequest(http.MethodPost, "/v1/audit", bytes.NewReader(bodyJSON))
			req.Header.Set("Content-Type", "application/json")
			rr := httptest.NewRecorder()

			handler.Create(rr, req)

			if rr.Code != http.StatusCreated {
				t.Errorf("expected status %d for outcome %s, got %d", http.StatusCreated, outcome, rr.Code)
			}
		})
	}
}

func TestValidationHelpers(t *testing.T) {
	// Test isValidEventCategory
	t.Run("isValidEventCategory", func(t *testing.T) {
		validCategories := []models.EventCategory{
			models.EventCategorySecurity,
			models.EventCategoryCompliance,
			models.EventCategoryOperational,
			models.EventCategoryAccess,
			models.EventCategoryData,
		}
		for _, c := range validCategories {
			if !isValidEventCategory(c) {
				t.Errorf("expected %s to be valid", c)
			}
		}
		if isValidEventCategory(models.EventCategory("invalid")) {
			t.Error("expected 'invalid' to be invalid")
		}
	})

	// Test isValidEventSeverity
	t.Run("isValidEventSeverity", func(t *testing.T) {
		validSeverities := []models.EventSeverity{
			models.EventSeverityInfo,
			models.EventSeverityWarning,
			models.EventSeverityError,
			models.EventSeverityCritical,
		}
		for _, s := range validSeverities {
			if !isValidEventSeverity(s) {
				t.Errorf("expected %s to be valid", s)
			}
		}
		if isValidEventSeverity(models.EventSeverity("invalid")) {
			t.Error("expected 'invalid' to be invalid")
		}
	})

	// Test isValidActorType
	t.Run("isValidActorType", func(t *testing.T) {
		validActorTypes := []models.ActorType{
			models.ActorTypeUser,
			models.ActorTypeSystem,
			models.ActorTypeAgent,
			models.ActorTypeService,
		}
		for _, a := range validActorTypes {
			if !isValidActorType(a) {
				t.Errorf("expected %s to be valid", a)
			}
		}
		if isValidActorType(models.ActorType("invalid")) {
			t.Error("expected 'invalid' to be invalid")
		}
	})

	// Test isValidEventOutcome
	t.Run("isValidEventOutcome", func(t *testing.T) {
		validOutcomes := []models.EventOutcome{
			models.EventOutcomeSuccess,
			models.EventOutcomeFailure,
			models.EventOutcomePending,
		}
		for _, o := range validOutcomes {
			if !isValidEventOutcome(o) {
				t.Errorf("expected %s to be valid", o)
			}
		}
		if isValidEventOutcome(models.EventOutcome("invalid")) {
			t.Error("expected 'invalid' to be invalid")
		}
	})
}
