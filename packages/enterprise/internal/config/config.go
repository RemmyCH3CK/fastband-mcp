// Package config provides configuration loading and validation for the Fastband Enterprise control plane.
// It implements fail-closed semantics: the server refuses to start if required configuration is missing or invalid.
package config

import (
	"errors"
	"fmt"
	"os"
	"time"
)

// Config holds all configuration for the Fastband Enterprise control plane.
type Config struct {
	// Server configuration
	ListenAddr      string
	ShutdownTimeout time.Duration

	// Authentication
	AuthSecret string

	// Feature flags (for future use)
	EnableEventStream bool

	// Postgres configuration (Task 3.3)
	// Validation will be enforced once Postgres storage is implemented.
	Postgres PostgresConfig

	// Redis configuration (Task 3.4)
	// Validation will be enforced once Redis storage is implemented.
	Redis RedisConfig
}

// PostgresConfig holds Postgres connection configuration.
// Fields are parsed but not yet validated (placeholder for Task 3.3).
type PostgresConfig struct {
	// DSN is the Postgres connection string (e.g., "postgres://user:pass@host:5432/dbname")
	DSN string

	// MaxOpenConns is the maximum number of open connections to the database.
	MaxOpenConns int

	// MaxIdleConns is the maximum number of idle connections in the pool.
	MaxIdleConns int

	// ConnMaxLifetime is the maximum amount of time a connection may be reused.
	ConnMaxLifetime time.Duration
}

// RedisConfig holds Redis connection and feature configuration.
// Fields are parsed but not yet validated (placeholder for Task 3.4).
type RedisConfig struct {
	// Addr is the Redis server address (e.g., "localhost:6379")
	Addr string

	// Password for Redis authentication (optional)
	Password string

	// DB is the Redis database number
	DB int

	// Session configuration
	SessionTTL time.Duration

	// Rate limiting configuration
	RateLimitRPS   int // Requests per second
	RateLimitBurst int // Burst size
}

// ValidationError represents a configuration validation failure.
type ValidationError struct {
	Field   string
	Message string
}

func (e ValidationError) Error() string {
	return fmt.Sprintf("config validation failed: %s: %s", e.Field, e.Message)
}

// MultiValidationError aggregates multiple validation errors.
type MultiValidationError struct {
	Errors []ValidationError
}

func (e MultiValidationError) Error() string {
	if len(e.Errors) == 1 {
		return e.Errors[0].Error()
	}
	return fmt.Sprintf("config validation failed: %d errors", len(e.Errors))
}

// Load reads configuration from environment variables and validates it.
// It returns an error if required configuration is missing or invalid.
// This implements fail-closed semantics.
func Load() (*Config, error) {
	cfg := &Config{
		// Server
		ListenAddr:        getEnvWithFallback("FASTBAND_LISTEN_ADDR", "CONTROLPLANE_BIND_ADDR", ":8080"),
		ShutdownTimeout:   parseDurationOrDefault("FASTBAND_SHUTDOWN_TIMEOUT", 30*time.Second),
		AuthSecret:        os.Getenv("FASTBAND_AUTH_SECRET"),
		EnableEventStream: getEnvBool("FASTBAND_ENABLE_EVENT_STREAM", false),

		// Postgres (placeholder - parsed but not validated until Task 3.3 implementation)
		Postgres: PostgresConfig{
			DSN:             os.Getenv("DATABASE_URL"),
			MaxOpenConns:    getEnvIntOrDefault("DATABASE_MAX_OPEN_CONNS", 25),
			MaxIdleConns:    getEnvIntOrDefault("DATABASE_MAX_IDLE_CONNS", 5),
			ConnMaxLifetime: parseDurationOrDefault("DATABASE_CONN_MAX_LIFETIME", 5*time.Minute),
		},

		// Redis (placeholder - parsed but not validated until Task 3.4 implementation)
		Redis: RedisConfig{
			Addr:           getEnvOrDefault("REDIS_ADDR", "localhost:6379"),
			Password:       os.Getenv("REDIS_PASSWORD"),
			DB:             getEnvIntOrDefault("REDIS_DB", 0),
			SessionTTL:     parseDurationOrDefault("FASTBAND_SESSION_TTL", 24*time.Hour),
			RateLimitRPS:   getEnvIntOrDefault("FASTBAND_RATE_LIMIT_RPS", 100),
			RateLimitBurst: getEnvIntOrDefault("FASTBAND_RATE_LIMIT_BURST", 200),
		},
	}

	if err := cfg.Validate(); err != nil {
		return nil, err
	}

	return cfg, nil
}

// Validate checks that all required configuration is present and valid.
// It returns a MultiValidationError if any validation fails.
func (c *Config) Validate() error {
	var errs []ValidationError

	// FAIL-CLOSED: AuthSecret is required
	if c.AuthSecret == "" {
		errs = append(errs, ValidationError{
			Field:   "FASTBAND_AUTH_SECRET",
			Message: "required but not set - server cannot start without authentication secret",
		})
	}

	// Validate listen address format (basic check)
	if c.ListenAddr == "" {
		errs = append(errs, ValidationError{
			Field:   "FASTBAND_LISTEN_ADDR",
			Message: "cannot be empty",
		})
	}

	// Validate shutdown timeout
	if c.ShutdownTimeout <= 0 {
		errs = append(errs, ValidationError{
			Field:   "FASTBAND_SHUTDOWN_TIMEOUT",
			Message: "must be positive duration",
		})
	}

	// NOTE: Postgres and Redis validation is intentionally NOT enforced here.
	// Validation will be added in Tasks 3.3 and 3.4 when those features are implemented.
	// This allows the skeleton to run without Postgres/Redis for development.

	if len(errs) > 0 {
		return MultiValidationError{Errors: errs}
	}

	return nil
}

// HasPostgres returns true if Postgres DSN is configured.
// Use this to conditionally enable Postgres features.
func (c *Config) HasPostgres() bool {
	return c.Postgres.DSN != ""
}

// HasRedis returns true if Redis address is configured and not default localhost.
// Use this to conditionally enable Redis features.
func (c *Config) HasRedis() bool {
	return c.Redis.Addr != "" && c.Redis.Addr != "localhost:6379"
}

// IsFailClosedError returns true if the error indicates a fail-closed condition.
func IsFailClosedError(err error) bool {
	var mve MultiValidationError
	if errors.As(err, &mve) {
		for _, ve := range mve.Errors {
			if ve.Field == "FASTBAND_AUTH_SECRET" {
				return true
			}
		}
	}
	var ve ValidationError
	if errors.As(err, &ve) {
		return ve.Field == "FASTBAND_AUTH_SECRET"
	}
	return false
}

func getEnvOrDefault(key, defaultValue string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultValue
}

// getEnvWithFallback checks primary env var, then fallback, then returns defaultValue.
func getEnvWithFallback(primary, fallback, defaultValue string) string {
	if v := os.Getenv(primary); v != "" {
		return v
	}
	if v := os.Getenv(fallback); v != "" {
		return v
	}
	return defaultValue
}

func parseDurationOrDefault(key string, defaultValue time.Duration) time.Duration {
	v := os.Getenv(key)
	if v == "" {
		return defaultValue
	}
	d, err := time.ParseDuration(v)
	if err != nil {
		return defaultValue
	}
	return d
}

func getEnvBool(key string, defaultValue bool) bool {
	v := os.Getenv(key)
	if v == "" {
		return defaultValue
	}
	return v == "true" || v == "1" || v == "yes"
}

func getEnvIntOrDefault(key string, defaultValue int) int {
	v := os.Getenv(key)
	if v == "" {
		return defaultValue
	}
	var i int
	_, err := fmt.Sscanf(v, "%d", &i)
	if err != nil {
		return defaultValue
	}
	return i
}
