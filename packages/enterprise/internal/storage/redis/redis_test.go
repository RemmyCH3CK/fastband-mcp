package redis

import (
	"context"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
)

func TestNew(t *testing.T) {
	mr := miniredis.RunT(t)

	opts := Options{
		Addr:         mr.Addr(),
		Password:     "",
		DB:           0,
		DialTimeout:  5 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
		PoolSize:     10,
		MinIdleConns: 2,
	}

	r, err := New(opts)
	if err != nil {
		t.Fatalf("failed to create Redis client: %v", err)
	}
	defer func() { _ = r.Close() }()

	if r.client == nil {
		t.Error("expected client to be initialized")
	}
}

func TestPing(t *testing.T) {
	mr := miniredis.RunT(t)

	opts := Options{
		Addr: mr.Addr(),
	}

	r, err := New(opts)
	if err != nil {
		t.Fatalf("failed to create Redis client: %v", err)
	}
	defer func() { _ = r.Close() }()

	ctx := context.Background()
	if err := r.Ping(ctx); err != nil {
		t.Errorf("Ping failed: %v", err)
	}
}

func TestPing_ConnectionError(t *testing.T) {
	// Use a non-existent address to simulate connection error
	opts := Options{
		Addr:        "localhost:59999", // unlikely to be in use
		DialTimeout: 100 * time.Millisecond,
		ReadTimeout: 100 * time.Millisecond,
	}

	r, err := New(opts)
	if err != nil {
		t.Fatalf("failed to create Redis client: %v", err)
	}
	defer func() { _ = r.Close() }()

	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()

	err = r.Ping(ctx)
	if err == nil {
		t.Error("expected Ping to fail with connection error")
	}
}

func TestPing_NilClient(t *testing.T) {
	r := &Redis{client: nil}

	ctx := context.Background()
	err := r.Ping(ctx)
	if err == nil {
		t.Error("expected error for nil client")
	}
	if err.Error() != "redis client not initialized" {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestClose(t *testing.T) {
	mr := miniredis.RunT(t)

	opts := Options{
		Addr: mr.Addr(),
	}

	r, err := New(opts)
	if err != nil {
		t.Fatalf("failed to create Redis client: %v", err)
	}

	// Close should not return an error
	if err := r.Close(); err != nil {
		t.Errorf("Close failed: %v", err)
	}
}

func TestClose_NilClient(t *testing.T) {
	r := &Redis{client: nil}

	// Close on nil client should be safe
	if err := r.Close(); err != nil {
		t.Errorf("Close on nil client failed: %v", err)
	}
}

func TestName(t *testing.T) {
	r := &Redis{}
	if r.Name() != "cache" {
		t.Errorf("expected Name() to return 'cache', got %q", r.Name())
	}
}

func TestCheck_Healthy(t *testing.T) {
	mr := miniredis.RunT(t)

	opts := Options{
		Addr: mr.Addr(),
	}

	r, err := New(opts)
	if err != nil {
		t.Fatalf("failed to create Redis client: %v", err)
	}
	defer func() { _ = r.Close() }()

	result := r.Check()
	if result.Status != "healthy" {
		t.Errorf("expected status 'healthy', got %q", result.Status)
	}
	if result.Message != "redis connection ok" {
		t.Errorf("unexpected message: %q", result.Message)
	}
}

func TestCheck_Unhealthy(t *testing.T) {
	// Use a non-existent address to simulate unhealthy state
	opts := Options{
		Addr:        "localhost:59999",
		DialTimeout: 100 * time.Millisecond,
		ReadTimeout: 100 * time.Millisecond,
	}

	r, err := New(opts)
	if err != nil {
		t.Fatalf("failed to create Redis client: %v", err)
	}
	defer func() { _ = r.Close() }()

	result := r.Check()
	if result.Status != "unhealthy" {
		t.Errorf("expected status 'unhealthy', got %q", result.Status)
	}
	if result.Message == "" {
		t.Error("expected non-empty error message")
	}
}

func TestClient(t *testing.T) {
	mr := miniredis.RunT(t)

	opts := Options{
		Addr: mr.Addr(),
	}

	r, err := New(opts)
	if err != nil {
		t.Fatalf("failed to create Redis client: %v", err)
	}
	defer func() { _ = r.Close() }()

	client := r.Client()
	if client == nil {
		t.Fatal("expected Client() to return non-nil client")
	}

	// Test that we can use the client directly
	ctx := context.Background()
	if err := client.Set(ctx, "test-key", "test-value", 0).Err(); err != nil {
		t.Errorf("failed to set value: %v", err)
	}

	val, err := client.Get(ctx, "test-key").Result()
	if err != nil {
		t.Errorf("failed to get value: %v", err)
	}
	if val != "test-value" {
		t.Errorf("expected 'test-value', got %q", val)
	}
}

func TestDefaultOptions(t *testing.T) {
	opts := DefaultOptions()

	if opts.Addr != "localhost:6379" {
		t.Errorf("expected default addr 'localhost:6379', got %q", opts.Addr)
	}
	if opts.Password != "" {
		t.Errorf("expected empty default password, got %q", opts.Password)
	}
	if opts.DB != 0 {
		t.Errorf("expected default DB 0, got %d", opts.DB)
	}
	if opts.DialTimeout != 5*time.Second {
		t.Errorf("expected default dial timeout 5s, got %v", opts.DialTimeout)
	}
	if opts.ReadTimeout != 3*time.Second {
		t.Errorf("expected default read timeout 3s, got %v", opts.ReadTimeout)
	}
	if opts.WriteTimeout != 3*time.Second {
		t.Errorf("expected default write timeout 3s, got %v", opts.WriteTimeout)
	}
	if opts.PoolSize != 10 {
		t.Errorf("expected default pool size 10, got %d", opts.PoolSize)
	}
	if opts.MinIdleConns != 2 {
		t.Errorf("expected default min idle conns 2, got %d", opts.MinIdleConns)
	}
}
