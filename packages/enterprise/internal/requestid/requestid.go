// Package requestid provides request ID generation and context propagation.
package requestid

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"net/http"
)

type contextKey struct{}

var requestIDKey = contextKey{}

// Generate creates a new unique request ID with the req_ prefix.
func Generate() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b) // Error is ignored; crypto/rand.Read always succeeds on supported platforms
	return "req_" + hex.EncodeToString(b)
}

// NewContext returns a new context with the request ID stored.
func NewContext(ctx context.Context, requestID string) context.Context {
	return context.WithValue(ctx, requestIDKey, requestID)
}

// FromContext retrieves the request ID from the context.
// Returns an empty string if not present.
func FromContext(ctx context.Context) string {
	if v := ctx.Value(requestIDKey); v != nil {
		return v.(string)
	}
	return ""
}

// Middleware adds a request ID to each request.
// If X-Request-ID header is present, it uses that value.
// Otherwise, it generates a new request ID.
func Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestID := r.Header.Get("X-Request-ID")
		if requestID == "" {
			requestID = Generate()
		}

		// Add to response headers
		w.Header().Set("X-Request-ID", requestID)

		// Add correlation ID if present
		if corrID := r.Header.Get("X-Correlation-ID"); corrID != "" {
			w.Header().Set("X-Correlation-ID", corrID)
		} else {
			// Use request ID as correlation ID if not provided
			w.Header().Set("X-Correlation-ID", requestID)
		}

		// Add to context
		ctx := NewContext(r.Context(), requestID)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}
