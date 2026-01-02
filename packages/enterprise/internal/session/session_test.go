package session

import (
	"context"
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

func TestSession_IsExpired(t *testing.T) {
	tests := []struct {
		name      string
		expiresAt time.Time
		expected  bool
	}{
		{
			name:      "not expired",
			expiresAt: time.Now().Add(1 * time.Hour),
			expected:  false,
		},
		{
			name:      "expired",
			expiresAt: time.Now().Add(-1 * time.Hour),
			expected:  true,
		},
		{
			name:      "just expired",
			expiresAt: time.Now().Add(-1 * time.Second),
			expected:  true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			s := &Session{ExpiresAt: tt.expiresAt}
			if got := s.IsExpired(); got != tt.expected {
				t.Errorf("IsExpired() = %v, want %v", got, tt.expected)
			}
		})
	}
}

func TestSession_TTL(t *testing.T) {
	s := &Session{ExpiresAt: time.Now().Add(1 * time.Hour)}
	ttl := s.TTL()

	// TTL should be approximately 1 hour (within 1 second margin)
	if ttl < 59*time.Minute || ttl > 61*time.Minute {
		t.Errorf("TTL() = %v, want approximately 1 hour", ttl)
	}
}

func TestRedisSessionStore_SetAndGet(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	store := NewRedisSessionStore(client, DefaultRedisSessionStoreOptions())

	session := &Session{
		ID:        "test-session-id",
		UserID:    "user-123",
		TenantID:  "tenant-456",
		CreatedAt: time.Now(),
		Metadata: map[string]string{
			"user_agent": "test-agent",
		},
	}

	ctx := context.Background()
	ttl := 1 * time.Hour

	// Set the session
	if err := store.Set(ctx, session, ttl); err != nil {
		t.Fatalf("Set failed: %v", err)
	}

	// Get the session
	retrieved, err := store.Get(ctx, session.ID)
	if err != nil {
		t.Fatalf("Get failed: %v", err)
	}

	if retrieved == nil {
		t.Fatal("expected session, got nil")
	}

	if retrieved.ID != session.ID {
		t.Errorf("expected ID %q, got %q", session.ID, retrieved.ID)
	}
	if retrieved.UserID != session.UserID {
		t.Errorf("expected UserID %q, got %q", session.UserID, retrieved.UserID)
	}
	if retrieved.TenantID != session.TenantID {
		t.Errorf("expected TenantID %q, got %q", session.TenantID, retrieved.TenantID)
	}
	if retrieved.Metadata["user_agent"] != "test-agent" {
		t.Errorf("expected metadata user_agent 'test-agent', got %q", retrieved.Metadata["user_agent"])
	}
}

func TestRedisSessionStore_Get_NotFound(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	store := NewRedisSessionStore(client, DefaultRedisSessionStoreOptions())

	ctx := context.Background()
	session, err := store.Get(ctx, "non-existent-session")

	if err != nil {
		t.Fatalf("Get failed: %v", err)
	}

	if session != nil {
		t.Error("expected nil session for non-existent ID")
	}
}

func TestRedisSessionStore_Delete(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	store := NewRedisSessionStore(client, DefaultRedisSessionStoreOptions())

	session := &Session{
		ID:       "test-session-to-delete",
		UserID:   "user-123",
		TenantID: "tenant-456",
	}

	ctx := context.Background()

	// Set the session
	if err := store.Set(ctx, session, 1*time.Hour); err != nil {
		t.Fatalf("Set failed: %v", err)
	}

	// Verify it exists
	retrieved, err := store.Get(ctx, session.ID)
	if err != nil || retrieved == nil {
		t.Fatal("session should exist before delete")
	}

	// Delete the session
	if err := store.Delete(ctx, session.ID); err != nil {
		t.Fatalf("Delete failed: %v", err)
	}

	// Verify it's gone
	retrieved, err = store.Get(ctx, session.ID)
	if err != nil {
		t.Fatalf("Get after delete failed: %v", err)
	}
	if retrieved != nil {
		t.Error("session should not exist after delete")
	}
}

func TestRedisSessionStore_Refresh(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	store := NewRedisSessionStore(client, DefaultRedisSessionStoreOptions())

	session := &Session{
		ID:        "test-session-to-refresh",
		UserID:    "user-123",
		TenantID:  "tenant-456",
		CreatedAt: time.Now(),
	}

	ctx := context.Background()

	// Set with short TTL
	initialTTL := 10 * time.Minute
	if err := store.Set(ctx, session, initialTTL); err != nil {
		t.Fatalf("Set failed: %v", err)
	}

	// Refresh with longer TTL
	newTTL := 2 * time.Hour
	refreshed, err := store.Refresh(ctx, session.ID, newTTL)
	if err != nil {
		t.Fatalf("Refresh failed: %v", err)
	}

	if refreshed == nil {
		t.Fatal("expected refreshed session, got nil")
	}

	// Check that ExpiresAt was updated
	expectedExpiry := time.Now().Add(newTTL)
	if refreshed.ExpiresAt.Before(expectedExpiry.Add(-1*time.Minute)) ||
		refreshed.ExpiresAt.After(expectedExpiry.Add(1*time.Minute)) {
		t.Errorf("ExpiresAt not updated correctly: got %v, expected around %v",
			refreshed.ExpiresAt, expectedExpiry)
	}
}

func TestRedisSessionStore_Refresh_NotFound(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	store := NewRedisSessionStore(client, DefaultRedisSessionStoreOptions())

	ctx := context.Background()
	_, err := store.Refresh(ctx, "non-existent-session", 1*time.Hour)

	if err == nil {
		t.Error("expected error when refreshing non-existent session")
	}
}

func TestRedisSessionStore_Set_NilSession(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	store := NewRedisSessionStore(client, DefaultRedisSessionStoreOptions())

	ctx := context.Background()
	err := store.Set(ctx, nil, 1*time.Hour)

	if err == nil {
		t.Error("expected error when setting nil session")
	}
}

func TestRedisSessionStore_Set_EmptyID(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	store := NewRedisSessionStore(client, DefaultRedisSessionStoreOptions())

	session := &Session{
		ID:     "",
		UserID: "user-123",
	}

	ctx := context.Background()
	err := store.Set(ctx, session, 1*time.Hour)

	if err == nil {
		t.Error("expected error when setting session with empty ID")
	}
}

func TestRedisSessionStore_TTLExpiration(t *testing.T) {
	client, mr := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	store := NewRedisSessionStore(client, DefaultRedisSessionStoreOptions())

	session := &Session{
		ID:       "test-session-expiring",
		UserID:   "user-123",
		TenantID: "tenant-456",
	}

	ctx := context.Background()

	// Set with short TTL
	if err := store.Set(ctx, session, 1*time.Second); err != nil {
		t.Fatalf("Set failed: %v", err)
	}

	// Verify it exists
	retrieved, err := store.Get(ctx, session.ID)
	if err != nil || retrieved == nil {
		t.Fatal("session should exist immediately after creation")
	}

	// Fast forward time in miniredis
	mr.FastForward(2 * time.Second)

	// Session should be expired now
	retrieved, err = store.Get(ctx, session.ID)
	if err != nil {
		t.Fatalf("Get after expiration failed: %v", err)
	}
	if retrieved != nil {
		t.Error("session should not exist after TTL expiration")
	}
}

func TestRedisSessionStore_CustomKeyPrefix(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	opts := RedisSessionStoreOptions{
		KeyPrefix: "custom-prefix:",
	}
	store := NewRedisSessionStore(client, opts)

	session := &Session{
		ID:     "test-session",
		UserID: "user-123",
	}

	ctx := context.Background()

	if err := store.Set(ctx, session, 1*time.Hour); err != nil {
		t.Fatalf("Set failed: %v", err)
	}

	// Verify the key was stored with custom prefix
	key := "custom-prefix:test-session"
	exists, err := client.Exists(ctx, key).Result()
	if err != nil {
		t.Fatalf("Exists check failed: %v", err)
	}
	if exists != 1 {
		t.Error("expected key with custom prefix to exist")
	}
}

func TestDefaultRedisSessionStoreOptions(t *testing.T) {
	opts := DefaultRedisSessionStoreOptions()

	if opts.KeyPrefix != "session:" {
		t.Errorf("expected default key prefix 'session:', got %q", opts.KeyPrefix)
	}
}

func TestNewRedisSessionStore_EmptyKeyPrefix(t *testing.T) {
	client, _ := newTestRedisClient(t)
	defer func() { _ = client.Close() }()

	opts := RedisSessionStoreOptions{
		KeyPrefix: "",
	}
	store := NewRedisSessionStore(client, opts)

	// Should use default prefix
	if store.keyPrefix != "session:" {
		t.Errorf("expected default key prefix 'session:' for empty option, got %q", store.keyPrefix)
	}
}
