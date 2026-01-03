// Package handlers provides HTTP handlers for the Fastband Enterprise control plane API v1.
package handlers

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/models"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage/postgres"
)

// ApprovalsHandler handles approval-related endpoints.
type ApprovalsHandler struct {
	store storage.PostgresStore
	log   *slog.Logger
}

// NewApprovalsHandler creates a new approvals handler.
func NewApprovalsHandler(store storage.PostgresStore, log *slog.Logger) *ApprovalsHandler {
	return &ApprovalsHandler{
		store: store,
		log:   log,
	}
}

// ApprovalHandler is an alias for backwards compatibility with router.go.
// Deprecated: Use ApprovalsHandler instead.
type ApprovalHandler = ApprovalsHandler

// NewApprovalHandler creates a new approval handler with no-op store.
// This is provided for backwards compatibility with the existing router.
// Deprecated: Use NewApprovalsHandler instead.
func NewApprovalHandler() *ApprovalHandler {
	return &ApprovalHandler{
		store: &noopApprovalStore{},
		log:   slog.Default(),
	}
}

// noopApprovalStore provides a no-op implementation for backwards compatibility.
type noopApprovalStore struct{}

func (n *noopApprovalStore) Ping(_ context.Context) error                  { return nil }
func (n *noopApprovalStore) CreateTicket(_ context.Context, _ *models.Ticket) error { return nil }
func (n *noopApprovalStore) GetTicket(_ context.Context, _ string) (*models.Ticket, error) {
	return nil, nil
}
func (n *noopApprovalStore) UpdateTicket(_ context.Context, _ *models.Ticket) error { return nil }
func (n *noopApprovalStore) DeleteTicket(_ context.Context, _ string) error         { return nil }
func (n *noopApprovalStore) ListTickets(_ context.Context, _ models.TicketFilter) (*models.TicketList, error) {
	return &models.TicketList{}, nil
}
func (n *noopApprovalStore) CreateJob(_ context.Context, _ *models.Job) error { return nil }
func (n *noopApprovalStore) GetJob(_ context.Context, _ string) (*models.Job, error) {
	return nil, nil
}
func (n *noopApprovalStore) UpdateJob(_ context.Context, _ *models.Job) error { return nil }
func (n *noopApprovalStore) ListJobs(_ context.Context, _ models.JobFilter) (*models.JobList, error) {
	return &models.JobList{}, nil
}
func (n *noopApprovalStore) CreateApproval(_ context.Context, _ *models.Approval) error { return nil }
func (n *noopApprovalStore) GetApproval(_ context.Context, _ string) (*models.Approval, error) {
	return nil, nil
}
func (n *noopApprovalStore) UpdateApproval(_ context.Context, _ *models.Approval) error { return nil }
func (n *noopApprovalStore) ListApprovals(_ context.Context, _ models.ApprovalFilter) (*models.ApprovalList, error) {
	return &models.ApprovalList{}, nil
}
func (n *noopApprovalStore) CreateAuditRecord(_ context.Context, _ *models.AuditRecord) error {
	return nil
}
func (n *noopApprovalStore) GetAuditRecord(_ context.Context, _ string) (*models.AuditRecord, error) {
	return nil, nil
}
func (n *noopApprovalStore) ListAuditRecords(_ context.Context, _ models.AuditFilter) (*models.AuditList, error) {
	return &models.AuditList{}, nil
}

// Routes returns a chi router with approval routes.
func (h *ApprovalsHandler) Routes() chi.Router {
	r := chi.NewRouter()

	r.Get("/", h.List)
	r.Get("/{approvalID}", h.Get)
	r.Post("/{approvalID}/approve", h.Approve)
	r.Post("/{approvalID}/deny", h.Deny)

	return r
}

// decisionRequest represents the optional body for approve/deny endpoints.
type decisionRequest struct {
	Comment   string `json:"comment,omitempty"`
	DecidedBy string `json:"decided_by,omitempty"`
}

// List handles GET /v1/approvals - List approvals with filtering and pagination.
func (h *ApprovalsHandler) List(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// Parse query parameters
	filter := models.ApprovalFilter{
		JobID:       r.URL.Query().Get("job_id"),
		RequestedBy: r.URL.Query().Get("requested_by"),
		Tool:        r.URL.Query().Get("tool"),
		Cursor:      r.URL.Query().Get("cursor"),
	}

	// Parse status if provided
	if status := r.URL.Query().Get("status"); status != "" {
		filter.Status = models.ApprovalStatus(status)
	}

	// Parse limit
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		limit, err := strconv.Atoi(limitStr)
		if err != nil || limit < 1 {
			h.log.WarnContext(ctx, "invalid limit parameter",
				"limit", limitStr,
				"error", err,
			)
			response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
				"Invalid limit parameter: must be a positive integer", nil)
			return
		}
		if limit > models.MaxPageLimit {
			limit = models.MaxPageLimit
		}
		filter.Limit = limit
	}

	// Call storage
	list, err := h.store.ListApprovals(ctx, filter)
	if err != nil {
		h.log.ErrorContext(ctx, "failed to list approvals",
			"error", err,
			"filter", filter,
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR",
			"Failed to list approvals", nil)
		return
	}

	response.Success(w, r, http.StatusOK, list)
}

// Get handles GET /v1/approvals/{approvalID} - Get approval details.
func (h *ApprovalsHandler) Get(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	approvalID := chi.URLParam(r, "approvalID")

	// Validate ID
	if approvalID == "" {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Approval ID is required", nil)
		return
	}

	// Call storage
	approval, err := h.store.GetApproval(ctx, approvalID)
	if err != nil {
		if errors.Is(err, postgres.ErrNotFound) {
			h.log.InfoContext(ctx, "approval not found",
				"approval_id", approvalID,
			)
			response.Error(w, r, http.StatusNotFound, "NOT_FOUND",
				"Approval not found", map[string]interface{}{
					"approval_id": approvalID,
				})
			return
		}

		h.log.ErrorContext(ctx, "failed to get approval",
			"approval_id", approvalID,
			"error", err,
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR",
			"Failed to get approval", nil)
		return
	}

	response.Success(w, r, http.StatusOK, approval)
}

// Approve handles POST /v1/approvals/{approvalID}/approve - Approve a pending action.
func (h *ApprovalsHandler) Approve(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	approvalID := chi.URLParam(r, "approvalID")

	// Validate ID
	if approvalID == "" {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Approval ID is required", nil)
		return
	}

	// Parse optional request body
	var req decisionRequest
	if r.Body != nil && r.ContentLength > 0 {
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			h.log.WarnContext(ctx, "failed to decode request body",
				"approval_id", approvalID,
				"error", err,
			)
			response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
				"Invalid request body", nil)
			return
		}
	}

	// Get existing approval
	approval, err := h.store.GetApproval(ctx, approvalID)
	if err != nil {
		if errors.Is(err, postgres.ErrNotFound) {
			h.log.InfoContext(ctx, "approval not found for approve action",
				"approval_id", approvalID,
			)
			response.Error(w, r, http.StatusNotFound, "NOT_FOUND",
				"Approval not found", map[string]interface{}{
					"approval_id": approvalID,
				})
			return
		}

		h.log.ErrorContext(ctx, "failed to get approval for approve action",
			"approval_id", approvalID,
			"error", err,
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR",
			"Failed to get approval", nil)
		return
	}

	// Check if already decided
	if approval.Status != models.ApprovalStatusPending {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Approval has already been decided", map[string]interface{}{
				"current_status": approval.Status,
			})
		return
	}

	// Update approval
	now := time.Now().UTC()
	approval.Status = models.ApprovalStatusApproved
	approval.DecidedAt = sql.NullTime{Time: now, Valid: true}

	// Set decided_by from request or use a default
	decidedBy := req.DecidedBy
	if decidedBy == "" {
		decidedBy = "system" // Default if not provided
	}
	approval.DecidedBy = sql.NullString{String: decidedBy, Valid: true}

	// Set comment if provided
	if req.Comment != "" {
		approval.Comment = sql.NullString{String: req.Comment, Valid: true}
	}

	// Save to storage
	if err := h.store.UpdateApproval(ctx, approval); err != nil {
		h.log.ErrorContext(ctx, "failed to update approval",
			"approval_id", approvalID,
			"error", err,
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR",
			"Failed to approve", nil)
		return
	}

	h.log.InfoContext(ctx, "approval approved",
		"approval_id", approvalID,
		"decided_by", decidedBy,
	)

	response.Success(w, r, http.StatusOK, approval)
}

// Deny handles POST /v1/approvals/{approvalID}/deny - Deny a pending action.
func (h *ApprovalsHandler) Deny(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	approvalID := chi.URLParam(r, "approvalID")

	// Validate ID
	if approvalID == "" {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Approval ID is required", nil)
		return
	}

	// Parse optional request body
	var req decisionRequest
	if r.Body != nil && r.ContentLength > 0 {
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			h.log.WarnContext(ctx, "failed to decode request body",
				"approval_id", approvalID,
				"error", err,
			)
			response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
				"Invalid request body", nil)
			return
		}
	}

	// Get existing approval
	approval, err := h.store.GetApproval(ctx, approvalID)
	if err != nil {
		if errors.Is(err, postgres.ErrNotFound) {
			h.log.InfoContext(ctx, "approval not found for deny action",
				"approval_id", approvalID,
			)
			response.Error(w, r, http.StatusNotFound, "NOT_FOUND",
				"Approval not found", map[string]interface{}{
					"approval_id": approvalID,
				})
			return
		}

		h.log.ErrorContext(ctx, "failed to get approval for deny action",
			"approval_id", approvalID,
			"error", err,
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR",
			"Failed to get approval", nil)
		return
	}

	// Check if already decided
	if approval.Status != models.ApprovalStatusPending {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Approval has already been decided", map[string]interface{}{
				"current_status": approval.Status,
			})
		return
	}

	// Update approval
	now := time.Now().UTC()
	approval.Status = models.ApprovalStatusRejected
	approval.DecidedAt = sql.NullTime{Time: now, Valid: true}

	// Set decided_by from request or use a default
	decidedBy := req.DecidedBy
	if decidedBy == "" {
		decidedBy = "system" // Default if not provided
	}
	approval.DecidedBy = sql.NullString{String: decidedBy, Valid: true}

	// Set comment if provided
	if req.Comment != "" {
		approval.Comment = sql.NullString{String: req.Comment, Valid: true}
	}

	// Save to storage
	if err := h.store.UpdateApproval(ctx, approval); err != nil {
		h.log.ErrorContext(ctx, "failed to update approval",
			"approval_id", approvalID,
			"error", err,
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR",
			"Failed to deny", nil)
		return
	}

	h.log.InfoContext(ctx, "approval denied",
		"approval_id", approvalID,
		"decided_by", decidedBy,
	)

	response.Success(w, r, http.StatusOK, approval)
}
