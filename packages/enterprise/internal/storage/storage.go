// Package storage provides storage abstractions for the Fastband Enterprise control plane.
// It defines interfaces that are implemented by specific storage backends:
//   - internal/storage/postgres/ (Task 3.3)
//   - internal/storage/redis/ (Task 3.4)
//
// This package contains only interfaces and the Stores aggregator.
// Implementation details are in subpackages to maintain clean boundaries.
package storage

import (
	"context"
	"io"
)

// Stores aggregates all storage backends.
// It provides a single point of access to all storage implementations.
type Stores struct {
	postgres PostgresStore
	redis    RedisStore
}

// NewStores creates a new Stores instance with no-op implementations.
func NewStores() *Stores {
	return &Stores{
		postgres: &noopPostgres{},
		redis:    &noopRedis{},
	}
}

// Postgres returns the Postgres store implementation.
func (s *Stores) Postgres() PostgresStore {
	return s.postgres
}

// SetPostgres sets the Postgres store implementation.
// Called during initialization when Postgres is configured.
func (s *Stores) SetPostgres(pg PostgresStore) {
	s.postgres = pg
}

// Redis returns the Redis store implementation.
func (s *Stores) Redis() RedisStore {
	return s.redis
}

// SetRedis sets the Redis store implementation.
// Called during initialization when Redis is configured.
func (s *Stores) SetRedis(r RedisStore) {
	s.redis = r
}

// Close closes all storage connections.
func (s *Stores) Close() error {
	var firstErr error

	if closer, ok := s.postgres.(io.Closer); ok {
		if err := closer.Close(); err != nil && firstErr == nil {
			firstErr = err
		}
	}

	if closer, ok := s.redis.(io.Closer); ok {
		if err := closer.Close(); err != nil && firstErr == nil {
			firstErr = err
		}
	}

	return firstErr
}

// PostgresStore defines the interface for Postgres storage operations.
// Implemented in internal/storage/postgres/ (Task 3.3).
type PostgresStore interface {
	// Ping checks if the database connection is healthy.
	Ping(ctx context.Context) error

	// Ticket operations (to be expanded in Task 3.3)
	// CreateTicket(ctx context.Context, ticket *models.Ticket) error
	// GetTicket(ctx context.Context, id string) (*models.Ticket, error)
	// ... etc
}

// RedisStore defines the interface for Redis storage operations.
// Implemented in internal/storage/redis/ (Task 3.4).
type RedisStore interface {
	// Ping checks if the Redis connection is healthy.
	Ping(ctx context.Context) error

	// Session operations (to be expanded in Task 3.4)
	// GetSession(ctx context.Context, sessionID string) (*Session, error)
	// SetSession(ctx context.Context, session *Session) error
	// DeleteSession(ctx context.Context, sessionID string) error

	// Rate limiting operations (to be expanded in Task 3.4)
	// CheckRateLimit(ctx context.Context, key string) (allowed bool, remaining int, err error)
}

// noopPostgres is a no-op implementation of PostgresStore.
// Used when Postgres is not configured.
type noopPostgres struct{}

func (n *noopPostgres) Ping(ctx context.Context) error {
	return nil
}

// noopRedis is a no-op implementation of RedisStore.
// Used when Redis is not configured.
type noopRedis struct{}

func (n *noopRedis) Ping(ctx context.Context) error {
	return nil
}
