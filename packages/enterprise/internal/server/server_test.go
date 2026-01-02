package server

import (
	"context"
	"net/http"
	"testing"
	"time"
)

func TestNew(t *testing.T) {
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	srv := New(Config{
		Addr:            ":0",
		Handler:         handler,
		ShutdownTimeout: 5 * time.Second,
	})

	if srv == nil {
		t.Fatal("expected server to be created")
	}

	if srv.ListenAddr() != ":0" {
		t.Errorf("expected listen addr ':0', got '%s'", srv.ListenAddr())
	}
}

func TestServer_Shutdown(t *testing.T) {
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	srv := New(Config{
		Addr:            ":0",
		Handler:         handler,
		ShutdownTimeout: 1 * time.Second,
	})

	// Start server in background
	ctx, cancel := context.WithCancel(context.Background())
	errCh := make(chan error, 1)

	go func() {
		errCh <- srv.Start(ctx)
	}()

	// Give server time to start
	time.Sleep(100 * time.Millisecond)

	// Cancel context to trigger shutdown
	cancel()

	// Wait for shutdown
	select {
	case err := <-errCh:
		if err != nil {
			t.Errorf("unexpected error during shutdown: %v", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("shutdown timed out")
	}
}

func TestConfig_DefaultTimeout(t *testing.T) {
	cfg := Config{
		Addr:    ":8080",
		Handler: http.DefaultServeMux,
	}

	srv := New(cfg)

	// When no timeout is specified, it defaults to zero
	// The actual default should be set by the caller when creating the config
	if srv.shutdownTimeout != 0 {
		t.Errorf("expected shutdown timeout 0 when not configured, got %v", srv.shutdownTimeout)
	}
}
