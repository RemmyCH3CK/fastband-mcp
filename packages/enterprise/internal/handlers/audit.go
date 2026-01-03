// Package handlers provides HTTP handlers for the Fastband Enterprise control plane API v1.
package handlers

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/models"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage/postgres"
)

// AuditHandler handles audit-related endpoints.
type AuditHandler struct {
	store storage.PostgresStore
	log   *slog.Logger
}

// NewAuditHandler creates a new audit handler.
func NewAuditHandler(store storage.PostgresStore, log *slog.Logger) *AuditHandler {
	if log == nil {
		log = slog.Default()
	}
	return &AuditHandler{
		store: store,
		log:   log,
	}
}

// Routes returns a chi router with audit routes.
func (h *AuditHandler) Routes() chi.Router {
	r := chi.NewRouter()

	r.Post("/", h.Create)
	r.Get("/", h.List)
	r.Get("/{recordID}", h.Get)

	return r
}

// CreateAuditRecordRequest represents the request body for creating an audit record.
type CreateAuditRecordRequest struct {
	EventType    string                 `json:"event_type"`
	Category     models.EventCategory   `json:"category"`
	Severity     models.EventSeverity   `json:"severity"`
	ActorID      string                 `json:"actor_id"`
	ActorType    models.ActorType       `json:"actor_type"`
	Action       string                 `json:"action"`
	ResourceID   string                 `json:"resource_id"`
	ResourceType string                 `json:"resource_type"`
	WorkspaceID  string                 `json:"workspace_id"`
	Outcome      models.EventOutcome    `json:"outcome"`
	Context      map[string]interface{} `json:"context,omitempty"`
	Details      map[string]interface{} `json:"details,omitempty"`
	Timestamp    *time.Time             `json:"timestamp,omitempty"`
}

// Create handles POST /v1/audit - Append an audit record.
func (h *AuditHandler) Create(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	var req CreateAuditRecordRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error("failed to decode request body",
			slog.String("error", err.Error()),
		)
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Invalid request body: "+err.Error(), nil)
		return
	}

	// Validate required fields
	var fieldErrors []response.FieldError

	if req.EventType == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "event_type",
			Code:    "required",
			Message: "event_type is required",
		})
	}
	if req.Category == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "category",
			Code:    "required",
			Message: "category is required",
		})
	} else if !isValidEventCategory(req.Category) {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "category",
			Code:    "invalid",
			Message: "category must be one of: security, compliance, operational, access, data",
		})
	}
	if req.Severity == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "severity",
			Code:    "required",
			Message: "severity is required",
		})
	} else if !isValidEventSeverity(req.Severity) {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "severity",
			Code:    "invalid",
			Message: "severity must be one of: info, warning, error, critical",
		})
	}
	if req.ActorID == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "actor_id",
			Code:    "required",
			Message: "actor_id is required",
		})
	}
	if req.ActorType == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "actor_type",
			Code:    "required",
			Message: "actor_type is required",
		})
	} else if !isValidActorType(req.ActorType) {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "actor_type",
			Code:    "invalid",
			Message: "actor_type must be one of: user, system, agent, service",
		})
	}
	if req.Action == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "action",
			Code:    "required",
			Message: "action is required",
		})
	}
	if req.ResourceID == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "resource_id",
			Code:    "required",
			Message: "resource_id is required",
		})
	}
	if req.ResourceType == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "resource_type",
			Code:    "required",
			Message: "resource_type is required",
		})
	}
	if req.WorkspaceID == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "workspace_id",
			Code:    "required",
			Message: "workspace_id is required",
		})
	}
	if req.Outcome == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "outcome",
			Code:    "required",
			Message: "outcome is required",
		})
	} else if !isValidEventOutcome(req.Outcome) {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "outcome",
			Code:    "invalid",
			Message: "outcome must be one of: success, failure, pending",
		})
	}

	if len(fieldErrors) > 0 {
		details := map[string]interface{}{
			"fields": fieldErrors,
		}
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Request validation failed", details)
		return
	}

	// Create the audit record
	now := time.Now().UTC()
	timestamp := now
	if req.Timestamp != nil {
		timestamp = *req.Timestamp
	}

	record := &models.AuditRecord{
		ID:           uuid.New().String(),
		EventType:    req.EventType,
		Category:     req.Category,
		Severity:     req.Severity,
		ActorID:      req.ActorID,
		ActorType:    req.ActorType,
		Action:       req.Action,
		ResourceID:   req.ResourceID,
		ResourceType: req.ResourceType,
		WorkspaceID:  req.WorkspaceID,
		Outcome:      req.Outcome,
		Context:      models.JSONB(req.Context),
		Details:      models.JSONB(req.Details),
		Timestamp:    timestamp,
		ReceivedAt:   now,
	}

	if err := h.store.CreateAuditRecord(ctx, record); err != nil {
		h.log.Error("failed to create audit record",
			slog.String("error", err.Error()),
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR",
			"Failed to create audit record", nil)
		return
	}

	h.log.Info("audit record created",
		slog.String("id", record.ID),
		slog.String("event_type", record.EventType),
		slog.String("category", string(record.Category)),
	)

	response.Success(w, r, http.StatusCreated, record)
}

// List handles GET /v1/audit - Query audit records.
func (h *AuditHandler) List(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	query := r.URL.Query()

	filter := models.AuditFilter{
		WorkspaceID:  query.Get("workspace_id"),
		EventType:    query.Get("event_type"),
		Category:     models.EventCategory(query.Get("category")),
		Severity:     models.EventSeverity(query.Get("severity")),
		ActorID:      query.Get("actor_id"),
		ActorType:    models.ActorType(query.Get("actor_type")),
		ResourceID:   query.Get("resource_id"),
		ResourceType: query.Get("resource_type"),
		Outcome:      models.EventOutcome(query.Get("outcome")),
		Cursor:       query.Get("cursor"),
	}

	// Parse limit
	if limitStr := query.Get("limit"); limitStr != "" {
		limit, err := strconv.Atoi(limitStr)
		if err != nil {
			response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
				"Invalid limit parameter: must be a number", nil)
			return
		}
		filter.Limit = limit
	}

	// Parse start_time
	if startTimeStr := query.Get("start_time"); startTimeStr != "" {
		startTime, err := time.Parse(time.RFC3339, startTimeStr)
		if err != nil {
			response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
				"Invalid start_time parameter: must be RFC3339 format", nil)
			return
		}
		filter.StartTime = &startTime
	}

	// Parse end_time
	if endTimeStr := query.Get("end_time"); endTimeStr != "" {
		endTime, err := time.Parse(time.RFC3339, endTimeStr)
		if err != nil {
			response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
				"Invalid end_time parameter: must be RFC3339 format", nil)
			return
		}
		filter.EndTime = &endTime
	}

	// Validate category if provided
	if filter.Category != "" && !isValidEventCategory(filter.Category) {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Invalid category parameter: must be one of security, compliance, operational, access, data", nil)
		return
	}

	// Validate severity if provided
	if filter.Severity != "" && !isValidEventSeverity(filter.Severity) {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Invalid severity parameter: must be one of info, warning, error, critical", nil)
		return
	}

	// Validate actor_type if provided
	if filter.ActorType != "" && !isValidActorType(filter.ActorType) {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Invalid actor_type parameter: must be one of user, system, agent, service", nil)
		return
	}

	// Validate outcome if provided
	if filter.Outcome != "" && !isValidEventOutcome(filter.Outcome) {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Invalid outcome parameter: must be one of success, failure, pending", nil)
		return
	}

	result, err := h.store.ListAuditRecords(ctx, filter)
	if err != nil {
		if errors.Is(err, postgres.ErrInvalidCursor) {
			response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
				"Invalid cursor parameter", nil)
			return
		}
		h.log.Error("failed to list audit records",
			slog.String("error", err.Error()),
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR",
			"Failed to list audit records", nil)
		return
	}

	response.Success(w, r, http.StatusOK, result)
}

// Get handles GET /v1/audit/{recordID} - Get a specific audit record.
func (h *AuditHandler) Get(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	recordID := chi.URLParam(r, "recordID")

	if recordID == "" {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR",
			"Record ID is required", nil)
		return
	}

	record, err := h.store.GetAuditRecord(ctx, recordID)
	if err != nil {
		if errors.Is(err, postgres.ErrNotFound) {
			response.Error(w, r, http.StatusNotFound, "NOT_FOUND",
				"Audit record not found", nil)
			return
		}
		h.log.Error("failed to get audit record",
			slog.String("error", err.Error()),
			slog.String("record_id", recordID),
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR",
			"Failed to get audit record", nil)
		return
	}

	response.Success(w, r, http.StatusOK, record)
}

// Validation helpers

func isValidEventCategory(category models.EventCategory) bool {
	switch category {
	case models.EventCategorySecurity,
		models.EventCategoryCompliance,
		models.EventCategoryOperational,
		models.EventCategoryAccess,
		models.EventCategoryData:
		return true
	}
	return false
}

func isValidEventSeverity(severity models.EventSeverity) bool {
	switch severity {
	case models.EventSeverityInfo,
		models.EventSeverityWarning,
		models.EventSeverityError,
		models.EventSeverityCritical:
		return true
	}
	return false
}

func isValidActorType(actorType models.ActorType) bool {
	switch actorType {
	case models.ActorTypeUser,
		models.ActorTypeSystem,
		models.ActorTypeAgent,
		models.ActorTypeService:
		return true
	}
	return false
}

func isValidEventOutcome(outcome models.EventOutcome) bool {
	switch outcome {
	case models.EventOutcomeSuccess,
		models.EventOutcomeFailure,
		models.EventOutcomePending:
		return true
	}
	return false
}
