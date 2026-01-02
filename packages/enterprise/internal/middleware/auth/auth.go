// Package auth provides authentication middleware for the Fastband Enterprise control plane.
// It implements deny-by-default semantics: all requests without valid authentication are rejected.
package auth

import (
	"context"
	"crypto/subtle"
	"log/slog"
	"net/http"
	"strings"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
)

// contextKey is used for storing auth info in request context.
type contextKey struct{}

var (
	// ActorKey is used to store/retrieve the authenticated actor from context.
	ActorKey = contextKey{}
)

// Actor represents an authenticated entity.
type Actor struct {
	ID   string
	Type string // "user", "service", "api_key"
}

// Config holds authentication middleware configuration.
type Config struct {
	// AuthSecret is the secret used to validate Bearer tokens.
	// This is a simple shared secret for the initial implementation.
	AuthSecret string

	// Logger for authentication events.
	Logger *slog.Logger
}

// Middleware creates an authentication middleware that validates Bearer tokens.
// It implements deny-by-default: all requests without valid authentication are rejected with 401.
func Middleware(cfg Config) func(http.Handler) http.Handler {
	logger := cfg.Logger
	if logger == nil {
		logger = slog.Default()
	}

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Extract Authorization header
			authHeader := r.Header.Get("Authorization")
			if authHeader == "" {
				logger.Warn("authentication failed: missing Authorization header",
					slog.String("path", r.URL.Path),
					slog.String("method", r.Method),
				)
				response.Unauthorized(w, r, "Authorization header required")
				return
			}

			// Parse Bearer token
			parts := strings.SplitN(authHeader, " ", 2)
			if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
				logger.Warn("authentication failed: invalid Authorization header format",
					slog.String("path", r.URL.Path),
					slog.String("method", r.Method),
				)
				response.Unauthorized(w, r, "Invalid Authorization header format. Expected: Bearer <token>")
				return
			}

			token := parts[1]
			if token == "" {
				logger.Warn("authentication failed: empty token",
					slog.String("path", r.URL.Path),
					slog.String("method", r.Method),
				)
				response.Unauthorized(w, r, "Token cannot be empty")
				return
			}

			// Validate token (constant-time comparison to prevent timing attacks)
			if subtle.ConstantTimeCompare([]byte(token), []byte(cfg.AuthSecret)) != 1 {
				logger.Warn("authentication failed: invalid token",
					slog.String("path", r.URL.Path),
					slog.String("method", r.Method),
				)
				response.Unauthorized(w, r, "Invalid or expired token")
				return
			}

			// Authentication successful
			// In a full implementation, we would decode a JWT and extract actor info.
			// For now, we create a placeholder actor.
			actor := Actor{
				ID:   "authenticated_user",
				Type: "api_key",
			}

			logger.Debug("authentication successful",
				slog.String("path", r.URL.Path),
				slog.String("actor_id", actor.ID),
			)

			// Add actor to context
			ctx := context.WithValue(r.Context(), ActorKey, actor)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// FromContext retrieves the authenticated actor from the request context.
// Returns nil if no actor is present (should not happen if auth middleware is applied).
func FromContext(ctx context.Context) *Actor {
	if v := ctx.Value(ActorKey); v != nil {
		actor := v.(Actor)
		return &actor
	}
	return nil
}

// RequireAuth is a helper that wraps a handler with authentication middleware.
// This is useful for applying auth to specific routes.
func RequireAuth(cfg Config, handler http.Handler) http.Handler {
	return Middleware(cfg)(handler)
}
