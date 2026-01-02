package router

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage"
)

func TestHealthEndpoints_NoAuthRequired(t *testing.T) {
	r := New(Config{
		AuthSecret: "test-secret",
		Version:    "1.0.0",
		Stores:     storage.NewStores(),
	})

	tests := []struct {
		path string
	}{
		{"/healthz"},
		{"/readyz"},
		{"/v1/health"},
		{"/v1/ready"},
	}

	for _, tt := range tests {
		t.Run(tt.path, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, tt.path, nil)
			rec := httptest.NewRecorder()

			r.ServeHTTP(rec, req)

			if rec.Code != http.StatusOK {
				t.Errorf("expected status 200 for %s, got %d", tt.path, rec.Code)
			}
		})
	}
}

func TestAPIEndpoints_RequireAuth(t *testing.T) {
	r := New(Config{
		AuthSecret: "test-secret",
		Version:    "1.0.0",
		Stores:     storage.NewStores(),
	})

	endpoints := []struct {
		method string
		path   string
	}{
		// Tickets
		{http.MethodGet, "/v1/tickets"},
		{http.MethodPost, "/v1/tickets"},
		{http.MethodGet, "/v1/tickets/tkt_123"},
		{http.MethodPatch, "/v1/tickets/tkt_123"},
		{http.MethodPost, "/v1/tickets/tkt_123/jobs"},

		// Jobs
		{http.MethodGet, "/v1/jobs/job_123"},
		{http.MethodPatch, "/v1/jobs/job_123"},

		// Policy
		{http.MethodPost, "/v1/policy/check"},

		// Approvals
		{http.MethodGet, "/v1/approvals"},
		{http.MethodGet, "/v1/approvals/apr_123"},
		{http.MethodPost, "/v1/approvals/apr_123/approve"},
		{http.MethodPost, "/v1/approvals/apr_123/deny"},

		// Audit
		{http.MethodGet, "/v1/audit"},
		{http.MethodPost, "/v1/audit"},
		{http.MethodGet, "/v1/audit/aud_123"},

		// Events
		{http.MethodGet, "/v1/events/stream"},
	}

	for _, ep := range endpoints {
		t.Run(ep.method+" "+ep.path, func(t *testing.T) {
			// Without auth - should return 401
			req := httptest.NewRequest(ep.method, ep.path, nil)
			rec := httptest.NewRecorder()

			r.ServeHTTP(rec, req)

			if rec.Code != http.StatusUnauthorized {
				t.Errorf("expected status 401 without auth for %s %s, got %d", ep.method, ep.path, rec.Code)
			}

			// Verify error envelope format
			var resp map[string]interface{}
			if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
				t.Fatalf("failed to unmarshal response: %v", err)
			}

			if resp["success"] != false {
				t.Error("expected success to be false")
			}

			if _, ok := resp["error"]; !ok {
				t.Error("expected error field in response")
			}
		})
	}
}

func TestAPIEndpoints_WithValidAuth(t *testing.T) {
	secret := "test-secret-12345"
	r := New(Config{
		AuthSecret: secret,
		Version:    "1.0.0",
		Stores:     storage.NewStores(),
	})

	// Test a few endpoints with valid auth - should return 501 Not Implemented (stub)
	endpoints := []struct {
		method string
		path   string
	}{
		{http.MethodGet, "/v1/tickets"},
		{http.MethodPost, "/v1/policy/check"},
		{http.MethodGet, "/v1/audit"},
	}

	for _, ep := range endpoints {
		t.Run(ep.method+" "+ep.path, func(t *testing.T) {
			req := httptest.NewRequest(ep.method, ep.path, nil)
			req.Header.Set("Authorization", "Bearer "+secret)
			rec := httptest.NewRecorder()

			r.ServeHTTP(rec, req)

			if rec.Code != http.StatusNotImplemented {
				t.Errorf("expected status 501 for stub %s %s, got %d", ep.method, ep.path, rec.Code)
			}

			// Verify v1 error envelope format
			var resp map[string]interface{}
			if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
				t.Fatalf("failed to unmarshal response: %v", err)
			}

			if resp["success"] != false {
				t.Error("expected success to be false")
			}

			errObj, ok := resp["error"].(map[string]interface{})
			if !ok {
				t.Fatal("expected error object in response")
			}

			if errObj["code"] != "NOT_IMPLEMENTED" {
				t.Errorf("expected error code 'NOT_IMPLEMENTED', got '%v'", errObj["code"])
			}
		})
	}
}

func TestAPIEndpoints_LegacyPath(t *testing.T) {
	secret := "test-secret"
	r := New(Config{
		AuthSecret: secret,
		Version:    "1.0.0",
		Stores:     storage.NewStores(),
	})

	// /api/v1/* should also work
	req := httptest.NewRequest(http.MethodGet, "/api/v1/tickets", nil)
	req.Header.Set("Authorization", "Bearer "+secret)
	rec := httptest.NewRecorder()

	r.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotImplemented {
		t.Errorf("expected status 501, got %d", rec.Code)
	}
}

func TestRequestID_InResponse(t *testing.T) {
	r := New(Config{
		AuthSecret: "test-secret",
		Version:    "1.0.0",
		Stores:     storage.NewStores(),
	})

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rec := httptest.NewRecorder()

	r.ServeHTTP(rec, req)

	reqID := rec.Header().Get("X-Request-ID")
	if reqID == "" {
		t.Error("expected X-Request-ID header in response")
	}

	if !strings.HasPrefix(reqID, "req_") {
		t.Errorf("expected request ID to start with 'req_', got '%s'", reqID)
	}
}

func TestCorrelationID_Propagated(t *testing.T) {
	r := New(Config{
		AuthSecret: "test-secret",
		Version:    "1.0.0",
		Stores:     storage.NewStores(),
	})

	corrID := "cor_custom123"
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	req.Header.Set("X-Correlation-ID", corrID)
	rec := httptest.NewRecorder()

	r.ServeHTTP(rec, req)

	respCorrID := rec.Header().Get("X-Correlation-ID")
	if respCorrID != corrID {
		t.Errorf("expected correlation ID '%s', got '%s'", corrID, respCorrID)
	}
}
