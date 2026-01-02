// Fastband Enterprise Control Plane
//
// This is the main entrypoint for the Fastband Enterprise control plane server.
// It implements fail-closed semantics: the server refuses to start if required
// configuration is missing or invalid.
//
// Required environment variables:
//   - FASTBAND_AUTH_SECRET: Authentication secret (required, fail-closed)
//
// Optional environment variables:
//   - FASTBAND_LISTEN_ADDR: Listen address (default: ":8080")
//   - FASTBAND_SHUTDOWN_TIMEOUT: Graceful shutdown timeout (default: "30s")
//   - DATABASE_URL: Postgres connection string (optional, for Task 3.3)
//   - REDIS_ADDR: Redis server address (optional, for Task 3.4)
//   - FASTBAND_RATE_LIMIT_RPS: Rate limit requests per second (default: 100)
//   - FASTBAND_RATE_LIMIT_BURST: Rate limit burst size (default: 200)
//   - FASTBAND_SESSION_TTL: Session TTL (default: "24h")
package main

import (
	"context"
	"database/sql"
	"log/slog"
	"os"

	_ "github.com/jackc/pgx/v5/stdlib"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/config"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/health"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/middleware/ratelimit"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/router"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/server"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage/postgres"
	redisstore "github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage/redis"
)

// Version is set at build time via ldflags.
var Version = "dev"

func main() {
	// Initialize structured logger
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	logger.Info("starting fastband-enterprise",
		slog.String("version", Version),
	)

	// Load and validate configuration
	// This implements FAIL-CLOSED: server refuses to start if config is invalid
	cfg, err := config.Load()
	if err != nil {
		logger.Error("configuration validation failed",
			slog.String("error", err.Error()),
		)

		// Provide helpful error message for fail-closed conditions
		if config.IsFailClosedError(err) {
			logger.Error("FAIL-CLOSED: Server cannot start without valid configuration",
				slog.String("hint", "Set FASTBAND_AUTH_SECRET environment variable"),
			)
		}

		os.Exit(1)
	}

	logger.Info("configuration loaded successfully",
		slog.String("listen_addr", cfg.ListenAddr),
		slog.Bool("postgres_configured", cfg.HasPostgres()),
		slog.Bool("redis_configured", cfg.HasRedis()),
	)

	// Initialize storage backends with fail-closed semantics
	stores, rateLimiter, healthHandler := initStorage(cfg, logger)

	// Create router with all handlers
	r := router.New(router.Config{
		AuthSecret:    cfg.AuthSecret,
		Version:       Version,
		Logger:        logger,
		Stores:        stores,
		RateLimiter:   rateLimiter,
		HealthHandler: healthHandler,
	})

	// Create and start server
	srv := server.New(server.Config{
		Addr:            cfg.ListenAddr,
		Handler:         r,
		ShutdownTimeout: cfg.ShutdownTimeout,
		Logger:          logger,
	})

	// Start server (blocks until shutdown signal or error)
	ctx := context.Background()
	if err := srv.Start(ctx); err != nil {
		logger.Error("server error",
			slog.String("error", err.Error()),
		)
		os.Exit(1)
	}

	// Cleanup storage connections
	if err := stores.Close(); err != nil {
		logger.Warn("error closing storage connections",
			slog.String("error", err.Error()),
		)
	}

	logger.Info("fastband-enterprise shutdown complete")
}

// initStorage initializes storage backends based on configuration.
// Implements FAIL-CLOSED: if a backend is configured but fails to connect, exit.
func initStorage(cfg *config.Config, logger *slog.Logger) (*storage.Stores, *ratelimit.Limiter, *health.Handler) {
	ctx := context.Background()
	stores := storage.NewStores()
	healthHandler := health.NewHandler(Version)
	var rateLimiter *ratelimit.Limiter

	// Postgres initialization (FAIL-CLOSED if configured but unreachable)
	if cfg.HasPostgres() {
		logger.Info("initializing postgres",
			slog.String("dsn", maskDSN(cfg.Postgres.DSN)),
		)
		db, err := sql.Open("pgx", cfg.Postgres.DSN)
		if err != nil {
			logger.Error("FAIL-CLOSED: failed to open postgres connection", slog.String("error", err.Error()))
			os.Exit(1)
		}
		db.SetMaxOpenConns(cfg.Postgres.MaxOpenConns)
		db.SetMaxIdleConns(cfg.Postgres.MaxIdleConns)
		db.SetConnMaxLifetime(cfg.Postgres.ConnMaxLifetime)
		if err := db.PingContext(ctx); err != nil {
			logger.Error("FAIL-CLOSED: postgres unreachable", slog.String("error", err.Error()))
			os.Exit(1)
		}
		pg := postgres.NewWithDB(db)
		stores.SetPostgres(pg)
		healthHandler.RegisterChecker(pg)
		logger.Info("postgres initialized successfully")
	}

	// Redis initialization (FAIL-CLOSED if configured but unreachable)
	if cfg.HasRedis() {
		logger.Info("initializing redis", slog.String("addr", cfg.Redis.Addr))
		r, err := redisstore.New(redisstore.Options{
			Addr:     cfg.Redis.Addr,
			Password: cfg.Redis.Password,
			DB:       cfg.Redis.DB,
		})
		if err != nil {
			logger.Error("FAIL-CLOSED: failed to create redis client", slog.String("error", err.Error()))
			os.Exit(1)
		}
		if err := r.Ping(ctx); err != nil {
			logger.Error("FAIL-CLOSED: redis unreachable", slog.String("error", err.Error()))
			os.Exit(1)
		}
		stores.SetRedis(r)
		healthHandler.RegisterChecker(r)
		// Create rate limiter
		rateLimiter, err = ratelimit.New(r.Client(), ratelimit.Config{
			RPS:   cfg.Redis.RateLimitRPS,
			Burst: cfg.Redis.RateLimitBurst,
		})
		if err != nil {
			logger.Error("FAIL-CLOSED: failed to create rate limiter", slog.String("error", err.Error()))
			os.Exit(1)
		}
		logger.Info("redis initialized successfully")
	}

	return stores, rateLimiter, healthHandler
}

// maskDSN masks sensitive parts of a database connection string for logging.
func maskDSN(dsn string) string {
	if dsn == "" {
		return ""
	}
	// Simple masking - just show that it's configured
	if len(dsn) > 20 {
		return dsn[:10] + "****" + dsn[len(dsn)-6:]
	}
	return "****"
}
