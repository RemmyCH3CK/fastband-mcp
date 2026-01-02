package auth

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestMiddleware_MissingAuthorizationHeader(t *testing.T) {
	middleware := Middleware(Config{AuthSecret: "test-secret"})
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Error("handler should not be called")
	}))

	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected status 401, got %d", rec.Code)
	}

	body := rec.Body.String()
	if !strings.Contains(body, "AUTHENTICATION_REQUIRED") {
		t.Errorf("expected AUTHENTICATION_REQUIRED in response, got: %s", body)
	}
}

func TestMiddleware_InvalidAuthorizationFormat(t *testing.T) {
	middleware := Middleware(Config{AuthSecret: "test-secret"})
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Error("handler should not be called")
	}))

	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("Authorization", "Basic dXNlcjpwYXNz") // Basic auth, not Bearer
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected status 401, got %d", rec.Code)
	}
}

func TestMiddleware_EmptyToken(t *testing.T) {
	middleware := Middleware(Config{AuthSecret: "test-secret"})
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Error("handler should not be called")
	}))

	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("Authorization", "Bearer ")
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected status 401, got %d", rec.Code)
	}
}

func TestMiddleware_InvalidToken(t *testing.T) {
	middleware := Middleware(Config{AuthSecret: "correct-secret"})
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Error("handler should not be called")
	}))

	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("Authorization", "Bearer wrong-secret")
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected status 401, got %d", rec.Code)
	}

	body := rec.Body.String()
	if !strings.Contains(body, "Invalid or expired token") {
		t.Errorf("expected 'Invalid or expired token' in response, got: %s", body)
	}
}

func TestMiddleware_ValidToken(t *testing.T) {
	secret := "valid-secret-12345"
	handlerCalled := false

	middleware := Middleware(Config{AuthSecret: secret})
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		handlerCalled = true

		// Verify actor is in context
		actor := FromContext(r.Context())
		if actor == nil {
			t.Error("expected actor in context")
			return
		}

		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("Authorization", "Bearer "+secret)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if !handlerCalled {
		t.Error("handler should have been called")
	}

	if rec.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", rec.Code)
	}
}

func TestMiddleware_BearerCaseInsensitive(t *testing.T) {
	secret := "test-secret"
	handlerCalled := false

	middleware := Middleware(Config{AuthSecret: secret})
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		handlerCalled = true
		w.WriteHeader(http.StatusOK)
	}))

	// Test lowercase "bearer"
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("Authorization", "bearer "+secret)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if !handlerCalled {
		t.Error("handler should have been called with lowercase 'bearer'")
	}
}

func TestFromContext_NoActor(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	actor := FromContext(req.Context())

	if actor != nil {
		t.Error("expected nil actor when not authenticated")
	}
}

func TestRequireAuth(t *testing.T) {
	secret := "test-secret"
	cfg := Config{AuthSecret: secret}

	innerHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	handler := RequireAuth(cfg, innerHandler)

	// Without auth
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401 without auth, got %d", rec.Code)
	}

	// With auth
	req = httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("Authorization", "Bearer "+secret)
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200 with auth, got %d", rec.Code)
	}
}
