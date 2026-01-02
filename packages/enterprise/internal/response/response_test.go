package response

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/requestid"
)

func TestSuccess(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req = req.WithContext(requestid.NewContext(req.Context(), "req_test123"))
	rec := httptest.NewRecorder()

	data := map[string]string{"message": "hello"}
	Success(rec, req, http.StatusOK, data)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", rec.Code)
	}

	contentType := rec.Header().Get("Content-Type")
	if contentType != "application/json; charset=utf-8" {
		t.Errorf("expected content-type 'application/json; charset=utf-8', got '%s'", contentType)
	}

	var resp SuccessResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if !resp.Success {
		t.Error("expected success to be true")
	}

	if resp.Meta.RequestID != "req_test123" {
		t.Errorf("expected request ID 'req_test123', got '%s'", resp.Meta.RequestID)
	}
}

func TestError(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req = req.WithContext(requestid.NewContext(req.Context(), "req_test456"))
	rec := httptest.NewRecorder()

	Error(rec, req, http.StatusBadRequest, "INVALID_INPUT", "Invalid request", nil)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d", rec.Code)
	}

	var resp ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Success {
		t.Error("expected success to be false")
	}

	if resp.Error.Code != "INVALID_INPUT" {
		t.Errorf("expected error code 'INVALID_INPUT', got '%s'", resp.Error.Code)
	}

	if resp.Error.Message != "Invalid request" {
		t.Errorf("expected error message 'Invalid request', got '%s'", resp.Error.Message)
	}
}

func TestNotImplemented(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req = req.WithContext(requestid.NewContext(req.Context(), "req_test"))
	rec := httptest.NewRecorder()

	NotImplemented(rec, req, "GET /v1/tickets")

	if rec.Code != http.StatusNotImplemented {
		t.Errorf("expected status 501, got %d", rec.Code)
	}

	var resp ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "NOT_IMPLEMENTED" {
		t.Errorf("expected error code 'NOT_IMPLEMENTED', got '%s'", resp.Error.Code)
	}
}

func TestUnauthorized(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req = req.WithContext(requestid.NewContext(req.Context(), "req_test"))
	rec := httptest.NewRecorder()

	Unauthorized(rec, req, "Invalid token")

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected status 401, got %d", rec.Code)
	}

	var resp ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "AUTHENTICATION_REQUIRED" {
		t.Errorf("expected error code 'AUTHENTICATION_REQUIRED', got '%s'", resp.Error.Code)
	}
}

func TestForbidden(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req = req.WithContext(requestid.NewContext(req.Context(), "req_test"))
	rec := httptest.NewRecorder()

	Forbidden(rec, req, "Access denied")

	if rec.Code != http.StatusForbidden {
		t.Errorf("expected status 403, got %d", rec.Code)
	}

	var resp ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "PERMISSION_DENIED" {
		t.Errorf("expected error code 'PERMISSION_DENIED', got '%s'", resp.Error.Code)
	}
}

func TestNotFound(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req = req.WithContext(requestid.NewContext(req.Context(), "req_test"))
	rec := httptest.NewRecorder()

	NotFound(rec, req, "tkt_123")

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected status 404, got %d", rec.Code)
	}

	var resp ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "RESOURCE_NOT_FOUND" {
		t.Errorf("expected error code 'RESOURCE_NOT_FOUND', got '%s'", resp.Error.Code)
	}
}

func TestInternalError(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req = req.WithContext(requestid.NewContext(req.Context(), "req_test"))
	rec := httptest.NewRecorder()

	InternalError(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected status 500, got %d", rec.Code)
	}

	var resp ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Error.Code != "INTERNAL_ERROR" {
		t.Errorf("expected error code 'INTERNAL_ERROR', got '%s'", resp.Error.Code)
	}
}

func TestMeta_IncludesTimestamp(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req = req.WithContext(requestid.NewContext(req.Context(), "req_test"))
	rec := httptest.NewRecorder()

	Success(rec, req, http.StatusOK, nil)

	var resp SuccessResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Meta.Timestamp == "" {
		t.Error("expected timestamp to be set")
	}
}

func TestMeta_UsesCorrelationID(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("X-Correlation-ID", "cor_trace789")
	req = req.WithContext(requestid.NewContext(req.Context(), "req_test"))
	rec := httptest.NewRecorder()

	Success(rec, req, http.StatusOK, nil)

	var resp SuccessResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Meta.CorrelationID != "cor_trace789" {
		t.Errorf("expected correlation ID 'cor_trace789', got '%s'", resp.Meta.CorrelationID)
	}
}
