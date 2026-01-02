// Package router provides HTTP routing for the Fastband Enterprise control plane.
// It wires together all handlers, middleware, and health endpoints.
package router

import (
	"log/slog"
	"net/http"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/handlers"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/health"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/middleware/auth"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/middleware/ratelimit"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/requestid"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage"
)

// Config holds router configuration.
type Config struct {
	// AuthSecret for Bearer token validation
	AuthSecret string

	// Version string for health endpoint
	Version string

	// Logger for request logging
	Logger *slog.Logger

	// Stores provides access to storage backends (Postgres, Redis)
	Stores *storage.Stores

	// RateLimiter for API rate limiting (optional, nil if Redis not configured)
	RateLimiter *ratelimit.Limiter

	// HealthHandler for health endpoints (optional, created if nil)
	HealthHandler *health.Handler
}

// New creates a new chi router with all routes configured.
func New(cfg Config) http.Handler {
	r := chi.NewRouter()

	logger := cfg.Logger
	if logger == nil {
		logger = slog.Default()
	}

	// Global middleware (applied to all routes)
	r.Use(chimw.RealIP)
	r.Use(requestid.Middleware)
	r.Use(chimw.Recoverer)

	// Health endpoints (public, no auth required)
	healthHandler := cfg.HealthHandler
	if healthHandler == nil {
		healthHandler = health.NewHandler(cfg.Version)
	}

	r.Get("/healthz", healthHandler.Healthz)
	r.Get("/readyz", healthHandler.Readyz)

	// Also expose health under /v1 path per API spec
	r.Get("/v1/health", healthHandler.Healthz)
	r.Get("/v1/ready", healthHandler.Readyz)

	// Auth middleware configuration
	authConfig := auth.Config{
		AuthSecret: cfg.AuthSecret,
		Logger:     logger,
	}

	// API v1 routes (require authentication)
	r.Route("/v1", func(r chi.Router) {
		r.Use(auth.Middleware(authConfig))
		if cfg.RateLimiter != nil {
			r.Use(cfg.RateLimiter.Middleware)
		}

		r.Mount("/tickets", handlers.NewTicketHandler().Routes())
		r.Mount("/jobs", handlers.NewJobHandler().Routes())
		r.Mount("/policy", handlers.NewPolicyHandler().Routes())
		r.Mount("/approvals", handlers.NewApprovalHandler().Routes())
		r.Mount("/audit", handlers.NewAuditHandler().Routes())
		r.Mount("/events", handlers.NewEventHandler().Routes())
	})

	// Also expose legacy /api/v1 path for compatibility
	r.Route("/api/v1", func(r chi.Router) {
		r.Use(auth.Middleware(authConfig))
		if cfg.RateLimiter != nil {
			r.Use(cfg.RateLimiter.Middleware)
		}

		r.Mount("/tickets", handlers.NewTicketHandler().Routes())
		r.Mount("/jobs", handlers.NewJobHandler().Routes())
		r.Mount("/policy", handlers.NewPolicyHandler().Routes())
		r.Mount("/approvals", handlers.NewApprovalHandler().Routes())
		r.Mount("/audit", handlers.NewAuditHandler().Routes())
		r.Mount("/events", handlers.NewEventHandler().Routes())
	})

	return r
}

// HealthHandler returns the health handler for external registration of checkers.
// This allows the main application to register health checkers for dependencies.
func HealthHandler(version string) *health.Handler {
	return health.NewHandler(version)
}
