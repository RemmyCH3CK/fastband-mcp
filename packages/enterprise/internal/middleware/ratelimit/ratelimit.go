// Package ratelimit provides rate limiting middleware for the Fastband Enterprise control plane.
// It implements a sliding window rate limiter using Redis for distributed state.
package ratelimit

import (
	"context"
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
)

// RedisClient is the minimal interface required from a Redis client.
type RedisClient interface {
	Eval(ctx context.Context, script string, keys []string, args ...interface{}) *redis.Cmd
	EvalSha(ctx context.Context, sha1 string, keys []string, args ...interface{}) *redis.Cmd
	ScriptLoad(ctx context.Context, script string) *redis.StringCmd
}

// Config holds rate limiting configuration.
type Config struct {
	// RPS is the number of requests allowed per second.
	RPS int

	// Burst is the maximum burst size (token bucket capacity).
	Burst int

	// Window is the sliding window duration (default: 1 second).
	Window time.Duration

	// KeyPrefix is prepended to all rate limit keys (default: "ratelimit:")
	KeyPrefix string

	// KeyFunc extracts the rate limit key from the request.
	// Default uses the client IP address.
	KeyFunc func(r *http.Request) string
}

// DefaultConfig returns default rate limiting configuration.
func DefaultConfig() Config {
	return Config{
		RPS:       100,
		Burst:     200,
		Window:    1 * time.Second,
		KeyPrefix: "ratelimit:",
		KeyFunc:   defaultKeyFunc,
	}
}

// defaultKeyFunc extracts the client IP from the request.
func defaultKeyFunc(r *http.Request) string {
	// Try X-Forwarded-For first (for proxied requests)
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		return xff
	}
	// Try X-Real-IP
	if xri := r.Header.Get("X-Real-IP"); xri != "" {
		return xri
	}
	// Fall back to RemoteAddr
	return r.RemoteAddr
}

// Limiter implements sliding window rate limiting using Redis.
type Limiter struct {
	client    RedisClient
	config    Config
	scriptSHA string
}

// New creates a new rate limiter with the given Redis client and configuration.
func New(client RedisClient, cfg Config) (*Limiter, error) {
	if cfg.RPS <= 0 {
		return nil, fmt.Errorf("RPS must be positive, got %d", cfg.RPS)
	}
	if cfg.Burst <= 0 {
		cfg.Burst = cfg.RPS
	}
	if cfg.Window <= 0 {
		cfg.Window = 1 * time.Second
	}
	if cfg.KeyPrefix == "" {
		cfg.KeyPrefix = "ratelimit:"
	}
	if cfg.KeyFunc == nil {
		cfg.KeyFunc = defaultKeyFunc
	}

	l := &Limiter{
		client: client,
		config: cfg,
	}

	// Pre-load the Lua script
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	sha, err := client.ScriptLoad(ctx, slidingWindowScript).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to load rate limit script: %w", err)
	}
	l.scriptSHA = sha

	return l, nil
}

// slidingWindowScript implements a sliding window rate limiter in Lua.
// It uses a sorted set where members are timestamps (in microseconds).
// Arguments: window_ms, limit, now_ms
// Returns: [allowed (0/1), remaining, retry_after_ms]
const slidingWindowScript = `
local key = KEYS[1]
local window_ms = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now_ms = tonumber(ARGV[3])

-- Remove old entries outside the window
local window_start = now_ms - window_ms
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Count current requests in window
local current = redis.call('ZCARD', key)

if current < limit then
    -- Add new request
    redis.call('ZADD', key, now_ms, now_ms .. '-' .. math.random(1000000))
    -- Set expiry on the key
    redis.call('PEXPIRE', key, window_ms)
    return {1, limit - current - 1, 0}
else
    -- Get oldest entry to calculate retry-after
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 0
    if oldest[2] then
        retry_after = tonumber(oldest[2]) + window_ms - now_ms
        if retry_after < 0 then
            retry_after = 0
        end
    end
    return {0, 0, retry_after}
end
`

// Result holds the result of a rate limit check.
type Result struct {
	// Allowed is true if the request is within the rate limit.
	Allowed bool

	// Remaining is the number of requests remaining in the current window.
	Remaining int

	// RetryAfter is the duration to wait before retrying (only set if Allowed is false).
	RetryAfter time.Duration
}

// Allow checks if a request is allowed under the rate limit.
func (l *Limiter) Allow(ctx context.Context, key string) (Result, error) {
	fullKey := l.config.KeyPrefix + key
	windowMs := l.config.Window.Milliseconds()
	limit := l.config.Burst
	nowMs := time.Now().UnixMilli()

	// Try to run the pre-loaded script
	result, err := l.client.EvalSha(ctx, l.scriptSHA, []string{fullKey}, windowMs, limit, nowMs).Result()
	if err != nil {
		// Fall back to EVAL if EVALSHA fails (script may have been flushed)
		result, err = l.client.Eval(ctx, slidingWindowScript, []string{fullKey}, windowMs, limit, nowMs).Result()
		if err != nil {
			return Result{}, fmt.Errorf("failed to execute rate limit script: %w", err)
		}
	}

	// Parse the result
	arr, ok := result.([]interface{})
	if !ok || len(arr) != 3 {
		return Result{}, fmt.Errorf("unexpected script result format")
	}

	allowed, _ := arr[0].(int64)
	remaining, _ := arr[1].(int64)
	retryAfterMs, _ := arr[2].(int64)

	return Result{
		Allowed:    allowed == 1,
		Remaining:  int(remaining),
		RetryAfter: time.Duration(retryAfterMs) * time.Millisecond,
	}, nil
}

// Middleware returns an HTTP middleware that enforces rate limiting.
// It uses the v1 error envelope format for 429 responses.
func (l *Limiter) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		key := l.config.KeyFunc(r)

		result, err := l.Allow(r.Context(), key)
		if err != nil {
			// On error, fail open (allow the request) but log
			// In production, you might want to fail closed instead
			next.ServeHTTP(w, r)
			return
		}

		// Set rate limit headers
		w.Header().Set("X-RateLimit-Limit", strconv.Itoa(l.config.Burst))
		w.Header().Set("X-RateLimit-Remaining", strconv.Itoa(result.Remaining))

		if !result.Allowed {
			// Calculate retry-after in seconds (rounded up)
			retryAfterSec := int(result.RetryAfter.Seconds())
			if result.RetryAfter > 0 && retryAfterSec == 0 {
				retryAfterSec = 1 // Minimum 1 second
			}

			// Set Retry-After header
			w.Header().Set("Retry-After", strconv.Itoa(retryAfterSec))
			w.Header().Set("X-RateLimit-Reset", strconv.FormatInt(time.Now().Add(result.RetryAfter).Unix(), 10))

			// Return 429 with v1 error envelope
			response.Error(w, r, http.StatusTooManyRequests, "RATE_LIMITED",
				"Too many requests, please try again later",
				map[string]interface{}{
					"retry_after_seconds": retryAfterSec,
					"limit":               l.config.Burst,
				})
			return
		}

		next.ServeHTTP(w, r)
	})
}

// MiddlewareFunc is a convenience wrapper that returns an http.HandlerFunc.
func (l *Limiter) MiddlewareFunc(next http.HandlerFunc) http.HandlerFunc {
	return l.Middleware(next).ServeHTTP
}
