// Package handlers provides HTTP handlers for the Fastband Enterprise control plane API v1.
package handlers

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/models"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage/postgres"
)

// JobsHandler handles job-related endpoints.
type JobsHandler struct {
	store storage.PostgresStore
	log   *slog.Logger
}

// NewJobsHandler creates a new jobs handler.
func NewJobsHandler(store storage.PostgresStore, log *slog.Logger) *JobsHandler {
	return &JobsHandler{store: store, log: log}
}

// Routes returns a chi router with job routes.
func (h *JobsHandler) Routes() chi.Router {
	r := chi.NewRouter()

	r.Get("/{jobID}", h.Get)
	r.Patch("/{jobID}", h.Update)

	return r
}

// Get handles GET /v1/jobs/{jobID} - Get job status and details.
func (h *JobsHandler) Get(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	jobID := chi.URLParam(r, "jobID")

	// Validate job ID
	if jobID == "" {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Job ID is required", nil)
		return
	}

	job, err := h.store.GetJob(ctx, jobID)
	if err != nil {
		if errors.Is(err, postgres.ErrNotFound) {
			response.Error(w, r, http.StatusNotFound, "NOT_FOUND",
				"Job not found", map[string]interface{}{"job_id": jobID})
			return
		}
		h.log.Error("failed to get job",
			slog.String("job_id", jobID),
			slog.String("error", err.Error()))
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR",
			"An unexpected error occurred", nil)
		return
	}

	response.Success(w, r, http.StatusOK, job)
}

// UpdateJobRequest represents the request body for updating a job.
type UpdateJobRequest struct {
	Status        *models.JobStatus      `json:"status,omitempty"`
	ExecutionNode *string                `json:"execution_node,omitempty"`
	Context       map[string]interface{} `json:"context,omitempty"`
	Result        map[string]interface{} `json:"result,omitempty"`
}

// Update handles PATCH /v1/jobs/{jobID} - Update job status.
func (h *JobsHandler) Update(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	jobID := chi.URLParam(r, "jobID")

	// Validate job ID
	if jobID == "" {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Job ID is required", nil)
		return
	}

	// Parse request body
	var req UpdateJobRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Invalid JSON body", map[string]interface{}{"parse_error": err.Error()})
		return
	}

	// Validate that at least one field is provided for update
	if req.Status == nil && req.ExecutionNode == nil && req.Context == nil && req.Result == nil {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"At least one field must be provided for update", nil)
		return
	}

	// Validate status if provided
	if req.Status != nil {
		if !isValidJobStatus(*req.Status) {
			response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
				"Invalid job status", map[string]interface{}{
					"status":         *req.Status,
					"allowed_values": []string{"queued", "running", "completed", "failed", "cancelled"},
				})
			return
		}
	}

	// Get existing job
	job, err := h.store.GetJob(ctx, jobID)
	if err != nil {
		if errors.Is(err, postgres.ErrNotFound) {
			response.Error(w, r, http.StatusNotFound, "NOT_FOUND",
				"Job not found", map[string]interface{}{"job_id": jobID})
			return
		}
		h.log.Error("failed to get job for update",
			slog.String("job_id", jobID),
			slog.String("error", err.Error()))
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR",
			"An unexpected error occurred", nil)
		return
	}

	// Apply updates
	if req.Status != nil {
		job.Status = *req.Status
	}
	if req.ExecutionNode != nil {
		job.ExecutionNode.String = *req.ExecutionNode
		job.ExecutionNode.Valid = true
	}
	if req.Context != nil {
		job.Context = models.JSONB(req.Context)
	}
	if req.Result != nil {
		job.Result = models.JSONB(req.Result)
	}

	// Update in storage
	if err := h.store.UpdateJob(ctx, job); err != nil {
		if errors.Is(err, postgres.ErrNotFound) {
			response.Error(w, r, http.StatusNotFound, "NOT_FOUND",
				"Job not found", map[string]interface{}{"job_id": jobID})
			return
		}
		h.log.Error("failed to update job",
			slog.String("job_id", jobID),
			slog.String("error", err.Error()))
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR",
			"An unexpected error occurred", nil)
		return
	}

	response.Success(w, r, http.StatusOK, job)
}

// isValidJobStatus checks if a job status is valid.
func isValidJobStatus(status models.JobStatus) bool {
	switch status {
	case models.JobStatusQueued,
		models.JobStatusRunning,
		models.JobStatusCompleted,
		models.JobStatusFailed,
		models.JobStatusCancelled:
		return true
	default:
		return false
	}
}
