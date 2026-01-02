// Package session provides session management for the Fastband Enterprise control plane.
// Sessions are stored in Redis with configurable TTL and support for refresh operations.
package session

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

// Session represents a user session.
type Session struct {
	// ID is the unique session identifier.
	ID string `json:"id"`

	// UserID is the ID of the user who owns this session.
	UserID string `json:"user_id"`

	// TenantID is the ID of the tenant this session belongs to.
	TenantID string `json:"tenant_id"`

	// CreatedAt is when the session was created.
	CreatedAt time.Time `json:"created_at"`

	// ExpiresAt is when the session will expire.
	ExpiresAt time.Time `json:"expires_at"`

	// Metadata holds additional session data.
	Metadata map[string]string `json:"metadata,omitempty"`
}

// IsExpired returns true if the session has expired.
func (s *Session) IsExpired() bool {
	return time.Now().After(s.ExpiresAt)
}

// TTL returns the remaining time until the session expires.
func (s *Session) TTL() time.Duration {
	return time.Until(s.ExpiresAt)
}

// SessionStore defines the interface for session storage operations.
type SessionStore interface {
	// Get retrieves a session by ID.
	// Returns nil, nil if the session does not exist.
	Get(ctx context.Context, sessionID string) (*Session, error)

	// Set stores a session with the given TTL.
	Set(ctx context.Context, session *Session, ttl time.Duration) error

	// Delete removes a session by ID.
	Delete(ctx context.Context, sessionID string) error

	// Refresh extends the session TTL by the specified duration.
	// Returns the updated session or an error if the session does not exist.
	Refresh(ctx context.Context, sessionID string, ttl time.Duration) (*Session, error)
}

// RedisClient is the minimal interface required from a Redis client.
type RedisClient interface {
	Get(ctx context.Context, key string) *redis.StringCmd
	Set(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.StatusCmd
	Del(ctx context.Context, keys ...string) *redis.IntCmd
	Expire(ctx context.Context, key string, expiration time.Duration) *redis.BoolCmd
}

// RedisSessionStore implements SessionStore using Redis.
type RedisSessionStore struct {
	client    RedisClient
	keyPrefix string
}

// RedisSessionStoreOptions configures the RedisSessionStore.
type RedisSessionStoreOptions struct {
	// KeyPrefix is prepended to all session keys (default: "session:")
	KeyPrefix string
}

// DefaultRedisSessionStoreOptions returns default options.
func DefaultRedisSessionStoreOptions() RedisSessionStoreOptions {
	return RedisSessionStoreOptions{
		KeyPrefix: "session:",
	}
}

// NewRedisSessionStore creates a new Redis-backed session store.
func NewRedisSessionStore(client RedisClient, opts RedisSessionStoreOptions) *RedisSessionStore {
	if opts.KeyPrefix == "" {
		opts.KeyPrefix = "session:"
	}

	return &RedisSessionStore{
		client:    client,
		keyPrefix: opts.KeyPrefix,
	}
}

// Get retrieves a session by ID.
func (s *RedisSessionStore) Get(ctx context.Context, sessionID string) (*Session, error) {
	key := s.keyPrefix + sessionID

	data, err := s.client.Get(ctx, key).Result()
	if err != nil {
		if err == redis.Nil {
			// Session not found
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get session: %w", err)
	}

	var session Session
	if err := json.Unmarshal([]byte(data), &session); err != nil {
		return nil, fmt.Errorf("failed to unmarshal session: %w", err)
	}

	// Check if session is expired (should not happen with Redis TTL, but double-check)
	if session.IsExpired() {
		// Clean up expired session
		_ = s.Delete(ctx, sessionID)
		return nil, nil
	}

	return &session, nil
}

// Set stores a session with the given TTL.
func (s *RedisSessionStore) Set(ctx context.Context, session *Session, ttl time.Duration) error {
	if session == nil {
		return fmt.Errorf("session cannot be nil")
	}

	if session.ID == "" {
		return fmt.Errorf("session ID cannot be empty")
	}

	// Update ExpiresAt based on TTL
	session.ExpiresAt = time.Now().Add(ttl)

	data, err := json.Marshal(session)
	if err != nil {
		return fmt.Errorf("failed to marshal session: %w", err)
	}

	key := s.keyPrefix + session.ID
	if err := s.client.Set(ctx, key, data, ttl).Err(); err != nil {
		return fmt.Errorf("failed to set session: %w", err)
	}

	return nil
}

// Delete removes a session by ID.
func (s *RedisSessionStore) Delete(ctx context.Context, sessionID string) error {
	key := s.keyPrefix + sessionID

	if err := s.client.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("failed to delete session: %w", err)
	}

	return nil
}

// Refresh extends the session TTL by the specified duration.
func (s *RedisSessionStore) Refresh(ctx context.Context, sessionID string, ttl time.Duration) (*Session, error) {
	// Get the existing session
	session, err := s.Get(ctx, sessionID)
	if err != nil {
		return nil, err
	}

	if session == nil {
		return nil, fmt.Errorf("session not found: %s", sessionID)
	}

	// Update the expiration time
	session.ExpiresAt = time.Now().Add(ttl)

	// Re-serialize and store with new TTL
	data, err := json.Marshal(session)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal session: %w", err)
	}

	key := s.keyPrefix + sessionID
	if err := s.client.Set(ctx, key, data, ttl).Err(); err != nil {
		return nil, fmt.Errorf("failed to refresh session: %w", err)
	}

	return session, nil
}

// Ensure RedisSessionStore implements SessionStore at compile time.
var _ SessionStore = (*RedisSessionStore)(nil)
