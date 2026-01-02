package health

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHealthz_Healthy(t *testing.T) {
	handler := NewHandler("1.0.0")

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rec := httptest.NewRecorder()

	handler.Healthz(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", rec.Code)
	}

	var resp HealthResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Status != "healthy" {
		t.Errorf("expected status 'healthy', got '%s'", resp.Status)
	}

	if resp.Version != "1.0.0" {
		t.Errorf("expected version '1.0.0', got '%s'", resp.Version)
	}

	if resp.Uptime < 0 {
		t.Error("uptime should be non-negative")
	}
}

func TestHealthz_WithUnhealthyChecker(t *testing.T) {
	handler := NewHandler("1.0.0")
	handler.RegisterChecker(&mockChecker{
		name:   "database",
		status: "unhealthy",
	})

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rec := httptest.NewRecorder()

	handler.Healthz(rec, req)

	if rec.Code != http.StatusServiceUnavailable {
		t.Errorf("expected status 503, got %d", rec.Code)
	}

	var resp HealthResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Status != "unhealthy" {
		t.Errorf("expected status 'unhealthy', got '%s'", resp.Status)
	}

	if resp.Checks["database"].Status != "unhealthy" {
		t.Error("expected database check to be unhealthy")
	}
}

func TestReadyz_Ready(t *testing.T) {
	handler := NewHandler("1.0.0")

	req := httptest.NewRequest(http.MethodGet, "/readyz", nil)
	rec := httptest.NewRecorder()

	handler.Readyz(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", rec.Code)
	}

	var resp ReadyResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if !resp.Ready {
		t.Error("expected ready to be true")
	}
}

func TestReadyz_NotReady(t *testing.T) {
	handler := NewHandler("1.0.0")
	handler.SetReady(false)

	req := httptest.NewRequest(http.MethodGet, "/readyz", nil)
	rec := httptest.NewRecorder()

	handler.Readyz(rec, req)

	if rec.Code != http.StatusServiceUnavailable {
		t.Errorf("expected status 503, got %d", rec.Code)
	}

	var resp ReadyResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp.Ready {
		t.Error("expected ready to be false")
	}
}

func TestReadyz_UnhealthyChecker(t *testing.T) {
	handler := NewHandler("1.0.0")
	handler.RegisterChecker(&mockChecker{
		name:   "redis",
		status: "unhealthy",
	})

	req := httptest.NewRequest(http.MethodGet, "/readyz", nil)
	rec := httptest.NewRecorder()

	handler.Readyz(rec, req)

	if rec.Code != http.StatusServiceUnavailable {
		t.Errorf("expected status 503, got %d", rec.Code)
	}
}

func TestLivenessHandler(t *testing.T) {
	handler := LivenessHandler()

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rec := httptest.NewRecorder()

	handler(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", rec.Code)
	}

	var resp map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	if resp["status"] != "ok" {
		t.Errorf("expected status 'ok', got '%s'", resp["status"])
	}
}

// mockChecker implements Checker for testing
type mockChecker struct {
	name    string
	status  string
	message string
}

func (m *mockChecker) Name() string {
	return m.name
}

func (m *mockChecker) Check() CheckResult {
	return CheckResult{
		Status:  m.status,
		Message: m.message,
	}
}
