package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
)

// AuditHandler handles audit-related endpoints.
type AuditHandler struct{}

// NewAuditHandler creates a new audit handler.
func NewAuditHandler() *AuditHandler {
	return &AuditHandler{}
}

// Routes returns a chi router with audit routes.
func (h *AuditHandler) Routes() chi.Router {
	r := chi.NewRouter()

	r.Post("/", h.Create)
	r.Get("/", h.List)
	r.Get("/{recordID}", h.Get)

	return r
}

// Create handles POST /v1/audit - Append an audit record.
func (h *AuditHandler) Create(w http.ResponseWriter, r *http.Request) {
	response.NotImplemented(w, r, "POST /v1/audit")
}

// List handles GET /v1/audit - Query audit records.
func (h *AuditHandler) List(w http.ResponseWriter, r *http.Request) {
	response.NotImplemented(w, r, "GET /v1/audit")
}

// Get handles GET /v1/audit/{recordID} - Get a specific audit record.
func (h *AuditHandler) Get(w http.ResponseWriter, r *http.Request) {
	recordID := chi.URLParam(r, "recordID")
	response.NotImplemented(w, r, "GET /v1/audit/"+recordID)
}
