package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
)

// JobHandler handles job-related endpoints.
type JobHandler struct{}

// NewJobHandler creates a new job handler.
func NewJobHandler() *JobHandler {
	return &JobHandler{}
}

// Routes returns a chi router with job routes.
func (h *JobHandler) Routes() chi.Router {
	r := chi.NewRouter()

	r.Get("/{jobID}", h.Get)
	r.Patch("/{jobID}", h.Update)

	return r
}

// Get handles GET /v1/jobs/{jobID} - Get job status and details.
func (h *JobHandler) Get(w http.ResponseWriter, r *http.Request) {
	jobID := chi.URLParam(r, "jobID")
	response.NotImplemented(w, r, "GET /v1/jobs/"+jobID)
}

// Update handles PATCH /v1/jobs/{jobID} - Update job status.
func (h *JobHandler) Update(w http.ResponseWriter, r *http.Request) {
	jobID := chi.URLParam(r, "jobID")
	response.NotImplemented(w, r, "PATCH /v1/jobs/"+jobID)
}
