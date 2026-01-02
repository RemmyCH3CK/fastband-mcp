package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
)

// PolicyHandler handles policy-related endpoints.
type PolicyHandler struct{}

// NewPolicyHandler creates a new policy handler.
func NewPolicyHandler() *PolicyHandler {
	return &PolicyHandler{}
}

// Routes returns a chi router with policy routes.
func (h *PolicyHandler) Routes() chi.Router {
	r := chi.NewRouter()

	r.Post("/check", h.Check)

	return r
}

// Check handles POST /v1/policy/check - Request policy evaluation for a tool call.
func (h *PolicyHandler) Check(w http.ResponseWriter, r *http.Request) {
	response.NotImplemented(w, r, "POST /v1/policy/check")
}
