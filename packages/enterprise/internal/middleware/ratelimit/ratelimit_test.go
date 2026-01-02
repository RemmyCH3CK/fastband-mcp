package ratelimit

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

func newTestRedisClient(t *testing.T) (*redis.Client, *miniredis.Miniredis) {
	t.Helper()
	mr := miniredis.RunT(t)
	client := redis.NewClient(&redis.Options{
		Addr: mr.Addr(),
	})
	return client, mr
}

func TestNew(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := DefaultConfig()
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	if limiter == nil {
		t.Error("expected non-nil limiter")
	}
}

func TestNew_InvalidRPS(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := Config{
		RPS: 0, // Invalid
	}
	_, err := New(client, cfg)
	if err == nil {
		t.Error("expected error for zero RPS")
	}

	cfg.RPS = -1
	_, err = New(client, cfg)
	if err == nil {
		t.Error("expected error for negative RPS")
	}
}

func TestAllow_UnderLimit(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := Config{
		RPS:   10,
		Burst: 10,
	}
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	ctx := context.Background()

	// Make requests up to the limit
	for i := 0; i < 10; i++ {
		result, err := limiter.Allow(ctx, "test-key")
		if err != nil {
			t.Fatalf("Allow failed: %v", err)
		}
		if !result.Allowed {
			t.Errorf("request %d should be allowed", i)
		}
		if result.Remaining != 10-i-1 {
			t.Errorf("expected remaining %d, got %d", 10-i-1, result.Remaining)
		}
	}
}

func TestAllow_OverLimit(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := Config{
		RPS:   5,
		Burst: 5,
	}
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	ctx := context.Background()

	// Exhaust the limit
	for i := 0; i < 5; i++ {
		_, err := limiter.Allow(ctx, "test-key")
		if err != nil {
			t.Fatalf("Allow failed: %v", err)
		}
	}

	// Next request should be denied
	result, err := limiter.Allow(ctx, "test-key")
	if err != nil {
		t.Fatalf("Allow failed: %v", err)
	}
	if result.Allowed {
		t.Error("request should be denied after limit exhausted")
	}
	if result.Remaining != 0 {
		t.Errorf("expected remaining 0, got %d", result.Remaining)
	}
	if result.RetryAfter <= 0 {
		t.Error("expected positive RetryAfter")
	}
}

func TestAllow_SeparateKeys(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := Config{
		RPS:   5,
		Burst: 5,
	}
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	ctx := context.Background()

	// Exhaust limit for key1
	for i := 0; i < 5; i++ {
		_, _ = limiter.Allow(ctx, "key1")
	}

	// key2 should still be allowed
	result, err := limiter.Allow(ctx, "key2")
	if err != nil {
		t.Fatalf("Allow failed: %v", err)
	}
	if !result.Allowed {
		t.Error("key2 should be allowed (separate from key1)")
	}
}

func TestAllow_WindowReset(t *testing.T) {
	client, mr := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := Config{
		RPS:    5,
		Burst:  5,
		Window: 1 * time.Second,
	}
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	ctx := context.Background()

	// Exhaust the limit
	for i := 0; i < 5; i++ {
		_, _ = limiter.Allow(ctx, "test-key")
	}

	// Should be denied
	result, _ := limiter.Allow(ctx, "test-key")
	if result.Allowed {
		t.Error("should be denied before window reset")
	}

	// Fast forward past the window
	mr.FastForward(2 * time.Second)

	// Should be allowed again
	result, err = limiter.Allow(ctx, "test-key")
	if err != nil {
		t.Fatalf("Allow failed after window reset: %v", err)
	}
	if !result.Allowed {
		t.Error("should be allowed after window reset")
	}
}

func TestMiddleware_AllowedRequest(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := Config{
		RPS:   100,
		Burst: 100,
	}
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	// Create a test handler
	handler := limiter.Middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("OK"))
	}))

	// Make a request
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.RemoteAddr = "192.168.1.1:12345"
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", rec.Code)
	}

	// Check rate limit headers
	if rec.Header().Get("X-RateLimit-Limit") != "100" {
		t.Errorf("expected X-RateLimit-Limit '100', got %q", rec.Header().Get("X-RateLimit-Limit"))
	}
	if rec.Header().Get("X-RateLimit-Remaining") == "" {
		t.Error("expected X-RateLimit-Remaining header")
	}
}

func TestMiddleware_RateLimited(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := Config{
		RPS:   2,
		Burst: 2,
	}
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	handler := limiter.Middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	// Make requests to exhaust the limit
	for i := 0; i < 2; i++ {
		req := httptest.NewRequest(http.MethodGet, "/test", nil)
		req.RemoteAddr = "192.168.1.1:12345"
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
	}

	// Next request should be rate limited
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.RemoteAddr = "192.168.1.1:12345"
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusTooManyRequests {
		t.Errorf("expected status 429, got %d", rec.Code)
	}

	// Check Retry-After header
	retryAfter := rec.Header().Get("Retry-After")
	if retryAfter == "" {
		t.Error("expected Retry-After header")
	}

	// Verify v1 error envelope format
	body, _ := io.ReadAll(rec.Body)
	var response map[string]interface{}
	if err := json.Unmarshal(body, &response); err != nil {
		t.Fatalf("failed to parse response body: %v", err)
	}

	if response["success"] != false {
		t.Error("expected success: false")
	}

	errorObj, ok := response["error"].(map[string]interface{})
	if !ok {
		t.Fatal("expected error object in response")
	}

	if errorObj["code"] != "RATE_LIMITED" {
		t.Errorf("expected error code 'RATE_LIMITED', got %v", errorObj["code"])
	}

	if errorObj["message"] == "" {
		t.Error("expected non-empty error message")
	}

	details, ok := errorObj["details"].(map[string]interface{})
	if !ok {
		t.Fatal("expected details object in error")
	}

	if _, exists := details["retry_after_seconds"]; !exists {
		t.Error("expected retry_after_seconds in details")
	}

	// Check meta
	meta, ok := response["meta"].(map[string]interface{})
	if !ok {
		t.Fatal("expected meta object in response")
	}

	if meta["timestamp"] == "" {
		t.Error("expected timestamp in meta")
	}
}

func TestMiddleware_XForwardedFor(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := Config{
		RPS:   2,
		Burst: 2,
	}
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	handler := limiter.Middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	// Make requests with X-Forwarded-For
	for i := 0; i < 2; i++ {
		req := httptest.NewRequest(http.MethodGet, "/test", nil)
		req.Header.Set("X-Forwarded-For", "10.0.0.1")
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
	}

	// Next request should be rate limited for 10.0.0.1
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("X-Forwarded-For", "10.0.0.1")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusTooManyRequests {
		t.Errorf("expected status 429 for same X-Forwarded-For, got %d", rec.Code)
	}

	// Request from different IP should be allowed
	req = httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("X-Forwarded-For", "10.0.0.2")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status 200 for different X-Forwarded-For, got %d", rec.Code)
	}
}

func TestMiddleware_XRealIP(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := Config{
		RPS:   2,
		Burst: 2,
	}
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	handler := limiter.Middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	// Make requests with X-Real-IP
	for i := 0; i < 2; i++ {
		req := httptest.NewRequest(http.MethodGet, "/test", nil)
		req.Header.Set("X-Real-IP", "10.0.0.100")
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
	}

	// Next request should be rate limited
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("X-Real-IP", "10.0.0.100")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusTooManyRequests {
		t.Errorf("expected status 429 for same X-Real-IP, got %d", rec.Code)
	}
}

func TestMiddleware_CustomKeyFunc(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	// Custom key function that uses a header
	cfg := Config{
		RPS:   2,
		Burst: 2,
		KeyFunc: func(r *http.Request) string {
			return r.Header.Get("X-API-Key")
		},
	}
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	handler := limiter.Middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	// Make requests with API key A
	for i := 0; i < 2; i++ {
		req := httptest.NewRequest(http.MethodGet, "/test", nil)
		req.Header.Set("X-API-Key", "key-A")
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
	}

	// API key A should be rate limited
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("X-API-Key", "key-A")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusTooManyRequests {
		t.Errorf("expected 429 for key-A, got %d", rec.Code)
	}

	// API key B should still be allowed
	req = httptest.NewRequest(http.MethodGet, "/test", nil)
	req.Header.Set("X-API-Key", "key-B")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200 for key-B, got %d", rec.Code)
	}
}

func TestMiddlewareFunc(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := Config{
		RPS:   100,
		Burst: 100,
	}
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	handlerFunc := func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}

	wrapped := limiter.MiddlewareFunc(handlerFunc)

	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	rec := httptest.NewRecorder()

	wrapped.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", rec.Code)
	}
}

func TestDefaultConfig(t *testing.T) {
	cfg := DefaultConfig()

	if cfg.RPS != 100 {
		t.Errorf("expected RPS 100, got %d", cfg.RPS)
	}
	if cfg.Burst != 200 {
		t.Errorf("expected Burst 200, got %d", cfg.Burst)
	}
	if cfg.Window != 1*time.Second {
		t.Errorf("expected Window 1s, got %v", cfg.Window)
	}
	if cfg.KeyPrefix != "ratelimit:" {
		t.Errorf("expected KeyPrefix 'ratelimit:', got %q", cfg.KeyPrefix)
	}
	if cfg.KeyFunc == nil {
		t.Error("expected non-nil KeyFunc")
	}
}

func TestDefaultKeyFunc(t *testing.T) {
	tests := []struct {
		name     string
		xff      string
		xri      string
		remote   string
		expected string
	}{
		{
			name:     "X-Forwarded-For takes precedence",
			xff:      "10.0.0.1",
			xri:      "10.0.0.2",
			remote:   "10.0.0.3:1234",
			expected: "10.0.0.1",
		},
		{
			name:     "X-Real-IP second precedence",
			xff:      "",
			xri:      "10.0.0.2",
			remote:   "10.0.0.3:1234",
			expected: "10.0.0.2",
		},
		{
			name:     "RemoteAddr fallback",
			xff:      "",
			xri:      "",
			remote:   "10.0.0.3:1234",
			expected: "10.0.0.3:1234",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/test", nil)
			if tt.xff != "" {
				req.Header.Set("X-Forwarded-For", tt.xff)
			}
			if tt.xri != "" {
				req.Header.Set("X-Real-IP", tt.xri)
			}
			req.RemoteAddr = tt.remote

			key := defaultKeyFunc(req)
			if key != tt.expected {
				t.Errorf("expected key %q, got %q", tt.expected, key)
			}
		})
	}
}

func TestRetryAfterHeader(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := Config{
		RPS:    1,
		Burst:  1,
		Window: 5 * time.Second,
	}
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	handler := limiter.Middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	// Make first request
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.RemoteAddr = "192.168.1.1:12345"
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	// Second request should be rate limited
	req = httptest.NewRequest(http.MethodGet, "/test", nil)
	req.RemoteAddr = "192.168.1.1:12345"
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("expected 429, got %d", rec.Code)
	}

	retryAfter := rec.Header().Get("Retry-After")
	if retryAfter == "" {
		t.Fatal("expected Retry-After header")
	}

	retryAfterInt, err := strconv.Atoi(retryAfter)
	if err != nil {
		t.Fatalf("invalid Retry-After value: %v", err)
	}

	// Retry-After should be positive and reasonable (within window)
	if retryAfterInt < 1 || retryAfterInt > 5 {
		t.Errorf("expected Retry-After between 1-5, got %d", retryAfterInt)
	}
}

func TestBurstBehavior(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	cfg := Config{
		RPS:    2,
		Burst:  10, // Burst is higher than RPS
		Window: 1 * time.Second,
	}
	limiter, err := New(client, cfg)
	if err != nil {
		t.Fatalf("failed to create limiter: %v", err)
	}

	ctx := context.Background()

	// Should be able to make 10 requests in burst
	for i := 0; i < 10; i++ {
		result, err := limiter.Allow(ctx, "burst-key")
		if err != nil {
			t.Fatalf("Allow failed: %v", err)
		}
		if !result.Allowed {
			t.Errorf("request %d should be allowed (within burst)", i)
		}
	}

	// 11th request should be denied
	result, err := limiter.Allow(ctx, "burst-key")
	if err != nil {
		t.Fatalf("Allow failed: %v", err)
	}
	if result.Allowed {
		t.Error("request should be denied after burst exhausted")
	}
}
