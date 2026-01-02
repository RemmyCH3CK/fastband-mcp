// Package health provides liveness and readiness probe endpoints for the Fastband Enterprise control plane.
// These endpoints are public (no authentication required) and follow Kubernetes probe conventions.
package health

import (
	"encoding/json"
	"net/http"
	"sync/atomic"
	"time"
)

// HealthResponse is the response for the /healthz endpoint.
type HealthResponse struct {
	Status  string                 `json:"status"`
	Version string                 `json:"version,omitempty"`
	Uptime  int64                  `json:"uptime_seconds,omitempty"`
	Checks  map[string]CheckResult `json:"components,omitempty"`
}

// ReadyResponse is the response for the /readyz endpoint.
type ReadyResponse struct {
	Ready  bool   `json:"ready"`
	Reason string `json:"reason,omitempty"`
}

// CheckResult represents the result of a health check.
type CheckResult struct {
	Status  string `json:"status"`
	Message string `json:"message,omitempty"`
}

// Checker defines an interface for health check components.
type Checker interface {
	Name() string
	Check() CheckResult
}

// Handler provides HTTP handlers for health endpoints.
type Handler struct {
	version   string
	startTime time.Time
	ready     atomic.Bool
	checkers  []Checker
}

// NewHandler creates a new health handler.
func NewHandler(version string) *Handler {
	h := &Handler{
		version:   version,
		startTime: time.Now(),
		checkers:  make([]Checker, 0),
	}
	// Start ready by default (no dependencies yet)
	h.ready.Store(true)
	return h
}

// RegisterChecker adds a health checker to be included in health checks.
func (h *Handler) RegisterChecker(c Checker) {
	h.checkers = append(h.checkers, c)
}

// SetReady sets the readiness state.
func (h *Handler) SetReady(ready bool) {
	h.ready.Store(ready)
}

// Healthz handles the /healthz liveness probe endpoint.
// Returns 200 OK if the server is alive, 503 if unhealthy.
func (h *Handler) Healthz(w http.ResponseWriter, r *http.Request) {
	checks := make(map[string]CheckResult)
	allHealthy := true

	for _, checker := range h.checkers {
		result := checker.Check()
		checks[checker.Name()] = result
		if result.Status != "healthy" {
			allHealthy = false
		}
	}

	status := "healthy"
	httpStatus := http.StatusOK
	if !allHealthy {
		status = "unhealthy"
		httpStatus = http.StatusServiceUnavailable
	}

	resp := HealthResponse{
		Status:  status,
		Version: h.version,
		Uptime:  int64(time.Since(h.startTime).Seconds()),
		Checks:  checks,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(httpStatus)
	_ = json.NewEncoder(w).Encode(resp)
}

// Readyz handles the /readyz readiness probe endpoint.
// Returns 200 OK if ready to receive traffic, 503 if not ready.
func (h *Handler) Readyz(w http.ResponseWriter, r *http.Request) {
	ready := h.ready.Load()

	// Also check all registered checkers for readiness
	for _, checker := range h.checkers {
		result := checker.Check()
		if result.Status != "healthy" {
			ready = false
			break
		}
	}

	var resp ReadyResponse
	var httpStatus int

	if ready {
		resp = ReadyResponse{Ready: true}
		httpStatus = http.StatusOK
	} else {
		resp = ReadyResponse{
			Ready:  false,
			Reason: "One or more dependencies not ready",
		}
		httpStatus = http.StatusServiceUnavailable
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(httpStatus)
	_ = json.NewEncoder(w).Encode(resp)
}

// LivenessHandler returns a simple liveness handler that always returns 200.
// Use this for basic liveness checks without dependency verification.
func LivenessHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}
}
