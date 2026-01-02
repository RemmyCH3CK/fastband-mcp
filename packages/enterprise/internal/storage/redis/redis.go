// Package redis provides a Redis storage implementation for the Fastband Enterprise control plane.
// It implements the storage.RedisStore interface and health.Checker interface.
package redis

import (
	"context"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/health"
)

// Options configures the Redis client.
type Options struct {
	// Addr is the Redis server address (e.g., "localhost:6379")
	Addr string

	// Password for Redis authentication (optional)
	Password string

	// DB is the Redis database number
	DB int

	// DialTimeout is the timeout for establishing new connections.
	DialTimeout time.Duration

	// ReadTimeout is the timeout for socket reads.
	ReadTimeout time.Duration

	// WriteTimeout is the timeout for socket writes.
	WriteTimeout time.Duration

	// PoolSize is the maximum number of socket connections.
	PoolSize int

	// MinIdleConns is the minimum number of idle connections.
	MinIdleConns int
}

// DefaultOptions returns default Redis options.
func DefaultOptions() Options {
	return Options{
		Addr:         "localhost:6379",
		Password:     "",
		DB:           0,
		DialTimeout:  5 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
		PoolSize:     10,
		MinIdleConns: 2,
	}
}

// Redis implements the storage.RedisStore and health.Checker interfaces.
type Redis struct {
	client *redis.Client
	opts   Options
}

// New creates a new Redis client with the given options.
func New(opts Options) (*Redis, error) {
	client := redis.NewClient(&redis.Options{
		Addr:         opts.Addr,
		Password:     opts.Password,
		DB:           opts.DB,
		DialTimeout:  opts.DialTimeout,
		ReadTimeout:  opts.ReadTimeout,
		WriteTimeout: opts.WriteTimeout,
		PoolSize:     opts.PoolSize,
		MinIdleConns: opts.MinIdleConns,
	})

	r := &Redis{
		client: client,
		opts:   opts,
	}

	return r, nil
}

// Ping checks if the Redis connection is healthy.
func (r *Redis) Ping(ctx context.Context) error {
	if r.client == nil {
		return fmt.Errorf("redis client not initialized")
	}

	result := r.client.Ping(ctx)
	if err := result.Err(); err != nil {
		return fmt.Errorf("redis ping failed: %w", err)
	}

	return nil
}

// Client returns the underlying redis.Client for advanced operations.
// This is used by SessionStore and RateLimiter.
func (r *Redis) Client() *redis.Client {
	return r.client
}

// Close closes the Redis connection.
func (r *Redis) Close() error {
	if r.client == nil {
		return nil
	}
	return r.client.Close()
}

// Name implements health.Checker interface.
func (r *Redis) Name() string {
	return "cache"
}

// Check implements health.Checker interface.
func (r *Redis) Check() health.CheckResult {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	if err := r.Ping(ctx); err != nil {
		return health.CheckResult{
			Status:  "unhealthy",
			Message: err.Error(),
		}
	}

	return health.CheckResult{
		Status:  "healthy",
		Message: "redis connection ok",
	}
}

// Ensure Redis implements the required interfaces at compile time.
var (
	_ health.Checker = (*Redis)(nil)
)
