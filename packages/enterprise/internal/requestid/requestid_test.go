package requestid

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestGenerate(t *testing.T) {
	id1 := Generate()
	id2 := Generate()

	// Should have req_ prefix
	if !strings.HasPrefix(id1, "req_") {
		t.Errorf("expected id to start with 'req_', got '%s'", id1)
	}

	// Should be unique
	if id1 == id2 {
		t.Error("generated IDs should be unique")
	}

	// Should have consistent length (req_ + 16 hex chars)
	if len(id1) != 20 {
		t.Errorf("expected id length 20, got %d", len(id1))
	}
}

func TestContext(t *testing.T) {
	ctx := context.Background()
	requestID := "req_test123"

	// Store in context
	ctx = NewContext(ctx, requestID)

	// Retrieve from context
	retrieved := FromContext(ctx)
	if retrieved != requestID {
		t.Errorf("expected '%s', got '%s'", requestID, retrieved)
	}
}

func TestFromContext_Empty(t *testing.T) {
	ctx := context.Background()
	retrieved := FromContext(ctx)

	if retrieved != "" {
		t.Errorf("expected empty string, got '%s'", retrieved)
	}
}

func TestMiddleware_GeneratesRequestID(t *testing.T) {
	var capturedID string

	handler := Middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedID = FromContext(r.Context())
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	// Should have generated a request ID
	if capturedID == "" {
		t.Error("expected request ID to be set in context")
	}

	if !strings.HasPrefix(capturedID, "req_") {
		t.Errorf("expected request ID to start with 'req_', got '%s'", capturedID)
	}

	// Should be in response header
	respID := rec.Header().Get("X-Request-ID")
	if respID != capturedID {
		t.Errorf("expected response header '%s', got '%s'", capturedID, respID)
	}
}

func TestMiddleware_UsesProvidedRequestID(t *testing.T) {
	providedID := "req_provided123"
	var capturedID string

	handler := Middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedID = FromContext(r.Context())
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("X-Request-ID", providedID)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if capturedID != providedID {
		t.Errorf("expected '%s', got '%s'", providedID, capturedID)
	}
}

func TestMiddleware_SetsCorrelationID(t *testing.T) {
	correlationID := "cor_trace123"

	handler := Middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("X-Correlation-ID", correlationID)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	respCorrID := rec.Header().Get("X-Correlation-ID")
	if respCorrID != correlationID {
		t.Errorf("expected correlation ID '%s', got '%s'", correlationID, respCorrID)
	}
}

func TestMiddleware_UsesRequestIDAsCorrelationID(t *testing.T) {
	handler := Middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	// No X-Correlation-ID header
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	reqID := rec.Header().Get("X-Request-ID")
	corrID := rec.Header().Get("X-Correlation-ID")

	if reqID != corrID {
		t.Errorf("expected correlation ID to match request ID: req=%s, corr=%s", reqID, corrID)
	}
}
