// Package server provides the HTTP server lifecycle management for the Fastband Enterprise control plane.
// It implements graceful shutdown on SIGTERM/SIGINT signals.
package server

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

// Server wraps an HTTP server with graceful shutdown capabilities.
type Server struct {
	httpServer      *http.Server
	shutdownTimeout time.Duration
	logger          *slog.Logger
}

// Config holds server configuration.
type Config struct {
	Addr            string
	Handler         http.Handler
	ShutdownTimeout time.Duration
	Logger          *slog.Logger
}

// New creates a new Server instance.
func New(cfg Config) *Server {
	logger := cfg.Logger
	if logger == nil {
		logger = slog.Default()
	}

	return &Server{
		httpServer: &http.Server{
			Addr:         cfg.Addr,
			Handler:      cfg.Handler,
			ReadTimeout:  15 * time.Second,
			WriteTimeout: 30 * time.Second,
			IdleTimeout:  60 * time.Second,
		},
		shutdownTimeout: cfg.ShutdownTimeout,
		logger:          logger,
	}
}

// Start begins listening for requests and blocks until shutdown.
// It handles SIGTERM and SIGINT for graceful shutdown.
func (s *Server) Start(ctx context.Context) error {
	// Channel to receive shutdown signals
	shutdown := make(chan os.Signal, 1)
	signal.Notify(shutdown, syscall.SIGTERM, syscall.SIGINT)

	// Channel to receive server errors
	serverErr := make(chan error, 1)

	// Start server in goroutine
	go func() {
		s.logger.Info("starting HTTP server",
			slog.String("addr", s.httpServer.Addr),
		)
		err := s.httpServer.ListenAndServe()
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			serverErr <- err
		}
	}()

	// Wait for shutdown signal or server error
	select {
	case err := <-serverErr:
		return err

	case sig := <-shutdown:
		s.logger.Info("received shutdown signal",
			slog.String("signal", sig.String()),
		)

	case <-ctx.Done():
		s.logger.Info("context cancelled, initiating shutdown")
	}

	// Graceful shutdown
	return s.Shutdown()
}

// Shutdown gracefully shuts down the server.
func (s *Server) Shutdown() error {
	s.logger.Info("initiating graceful shutdown",
		slog.Duration("timeout", s.shutdownTimeout),
	)

	ctx, cancel := context.WithTimeout(context.Background(), s.shutdownTimeout)
	defer cancel()

	err := s.httpServer.Shutdown(ctx)
	if err != nil {
		s.logger.Error("graceful shutdown failed",
			slog.String("error", err.Error()),
		)
		return err
	}

	s.logger.Info("server shutdown complete")
	return nil
}

// ListenAddr returns the server's listen address.
func (s *Server) ListenAddr() string {
	return s.httpServer.Addr
}
