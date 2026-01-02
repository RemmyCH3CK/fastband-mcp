package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
)

// ApprovalHandler handles approval-related endpoints.
type ApprovalHandler struct{}

// NewApprovalHandler creates a new approval handler.
func NewApprovalHandler() *ApprovalHandler {
	return &ApprovalHandler{}
}

// Routes returns a chi router with approval routes.
func (h *ApprovalHandler) Routes() chi.Router {
	r := chi.NewRouter()

	r.Get("/", h.List)
	r.Get("/{approvalID}", h.Get)
	r.Post("/{approvalID}/approve", h.Approve)
	r.Post("/{approvalID}/deny", h.Deny)

	return r
}

// List handles GET /v1/approvals - List pending approvals.
func (h *ApprovalHandler) List(w http.ResponseWriter, r *http.Request) {
	response.NotImplemented(w, r, "GET /v1/approvals")
}

// Get handles GET /v1/approvals/{approvalID} - Get approval details.
func (h *ApprovalHandler) Get(w http.ResponseWriter, r *http.Request) {
	approvalID := chi.URLParam(r, "approvalID")
	response.NotImplemented(w, r, "GET /v1/approvals/"+approvalID)
}

// Approve handles POST /v1/approvals/{approvalID}/approve - Approve a pending action.
func (h *ApprovalHandler) Approve(w http.ResponseWriter, r *http.Request) {
	approvalID := chi.URLParam(r, "approvalID")
	response.NotImplemented(w, r, "POST /v1/approvals/"+approvalID+"/approve")
}

// Deny handles POST /v1/approvals/{approvalID}/deny - Deny a pending action.
func (h *ApprovalHandler) Deny(w http.ResponseWriter, r *http.Request) {
	approvalID := chi.URLParam(r, "approvalID")
	response.NotImplemented(w, r, "POST /v1/approvals/"+approvalID+"/deny")
}
