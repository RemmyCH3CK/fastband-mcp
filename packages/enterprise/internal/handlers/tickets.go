// Package handlers provides HTTP handlers for the Fastband Enterprise control plane API v1.
package handlers

import (
	"database/sql"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/models"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage"
	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/storage/postgres"
)

// TicketsHandler handles ticket-related endpoints.
type TicketsHandler struct {
	store storage.PostgresStore
	log   *slog.Logger
}

// NewTicketsHandler creates a new tickets handler.
func NewTicketsHandler(store storage.PostgresStore, log *slog.Logger) *TicketsHandler {
	return &TicketsHandler{store: store, log: log}
}

// Routes returns a chi router with ticket routes.
func (h *TicketsHandler) Routes() chi.Router {
	r := chi.NewRouter()

	r.Post("/", h.Create)
	r.Get("/", h.List)
	r.Get("/{ticketID}", h.Get)
	r.Patch("/{ticketID}", h.Update)
	r.Post("/{ticketID}/jobs", h.CreateJob)

	return r
}

// CreateTicketRequest represents the request body for creating a ticket.
type CreateTicketRequest struct {
	WorkspaceID string                 `json:"workspace_id"`
	Title       string                 `json:"title"`
	Description string                 `json:"description"`
	Priority    models.TicketPriority  `json:"priority"`
	Labels      []string               `json:"labels"`
	AssignedTo  string                 `json:"assigned_to,omitempty"`
	CreatedBy   string                 `json:"created_by"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// UpdateTicketRequest represents the request body for updating a ticket.
type UpdateTicketRequest struct {
	Title       *string                `json:"title,omitempty"`
	Description *string                `json:"description,omitempty"`
	Status      *models.TicketStatus   `json:"status,omitempty"`
	Priority    *models.TicketPriority `json:"priority,omitempty"`
	Labels      []string               `json:"labels,omitempty"`
	AssignedTo  *string                `json:"assigned_to,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// Create handles POST /v1/tickets - Create a new ticket.
func (h *TicketsHandler) Create(w http.ResponseWriter, r *http.Request) {
	var req CreateTicketRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error("failed to decode request body", slog.String("error", err.Error()))
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR", "Invalid JSON body", nil)
		return
	}

	// Validate required fields
	var fieldErrors []response.FieldError
	if req.WorkspaceID == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "workspace_id",
			Code:    "required",
			Message: "workspace_id is required",
		})
	}
	if req.Title == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "title",
			Code:    "required",
			Message: "title is required",
		})
	}
	if req.CreatedBy == "" {
		fieldErrors = append(fieldErrors, response.FieldError{
			Field:   "created_by",
			Code:    "required",
			Message: "created_by is required",
		})
	}

	if len(fieldErrors) > 0 {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR", "Request validation failed",
			map[string]interface{}{"fields": fieldErrors})
		return
	}

	// Set defaults
	priority := req.Priority
	if priority == "" {
		priority = models.TicketPriorityMedium
	}

	// Validate priority if provided
	if !isValidTicketPriority(priority) {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR", "Invalid priority value",
			map[string]interface{}{
				"fields": []response.FieldError{{
					Field:   "priority",
					Code:    "invalid",
					Message: "priority must be one of: low, medium, high, critical",
				}},
			})
		return
	}

	now := time.Now().UTC()
	ticket := &models.Ticket{
		ID:          uuid.New().String(),
		WorkspaceID: req.WorkspaceID,
		Title:       req.Title,
		Description: req.Description,
		Status:      models.TicketStatusOpen,
		Priority:    priority,
		Labels:      req.Labels,
		CreatedBy:   req.CreatedBy,
		CreatedAt:   now,
		UpdatedAt:   now,
		Metadata:    req.Metadata,
	}

	if req.AssignedTo != "" {
		ticket.AssignedTo = sql.NullString{String: req.AssignedTo, Valid: true}
	}

	if err := h.store.CreateTicket(r.Context(), ticket); err != nil {
		h.log.Error("failed to create ticket",
			slog.String("error", err.Error()),
			slog.String("workspace_id", req.WorkspaceID),
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR", "Failed to create ticket", nil)
		return
	}

	h.log.Info("ticket created",
		slog.String("ticket_id", ticket.ID),
		slog.String("workspace_id", ticket.WorkspaceID),
	)

	response.Success(w, r, http.StatusCreated, ticket)
}

// List handles GET /v1/tickets - List tickets with filtering and pagination.
func (h *TicketsHandler) List(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query()

	filter := models.TicketFilter{
		WorkspaceID: query.Get("workspace_id"),
		Status:      models.TicketStatus(query.Get("status")),
		Priority:    models.TicketPriority(query.Get("priority")),
		AssignedTo:  query.Get("assigned_to"),
		CreatedBy:   query.Get("created_by"),
		Cursor:      query.Get("cursor"),
	}

	// Parse labels (comma-separated)
	if labels := query.Get("labels"); labels != "" {
		filter.Labels = splitAndTrim(labels)
	}

	// Parse limit
	if limitStr := query.Get("limit"); limitStr != "" {
		limit, err := strconv.Atoi(limitStr)
		if err != nil || limit < 1 {
			response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR", "Invalid limit parameter",
				map[string]interface{}{
					"fields": []response.FieldError{{
						Field:   "limit",
						Code:    "invalid",
						Message: "limit must be a positive integer",
					}},
				})
			return
		}
		if limit > models.MaxPageLimit {
			limit = models.MaxPageLimit
		}
		filter.Limit = limit
	}

	// Validate status if provided
	if filter.Status != "" && !isValidTicketStatus(filter.Status) {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR", "Invalid status value",
			map[string]interface{}{
				"fields": []response.FieldError{{
					Field:   "status",
					Code:    "invalid",
					Message: "status must be one of: open, in_progress, pending, resolved, closed",
				}},
			})
		return
	}

	// Validate priority if provided
	if filter.Priority != "" && !isValidTicketPriority(filter.Priority) {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR", "Invalid priority value",
			map[string]interface{}{
				"fields": []response.FieldError{{
					Field:   "priority",
					Code:    "invalid",
					Message: "priority must be one of: low, medium, high, critical",
				}},
			})
		return
	}

	result, err := h.store.ListTickets(r.Context(), filter)
	if err != nil {
		if errors.Is(err, postgres.ErrInvalidCursor) {
			response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR", "Invalid cursor",
				map[string]interface{}{
					"fields": []response.FieldError{{
						Field:   "cursor",
						Code:    "invalid",
						Message: "cursor is invalid or expired",
					}},
				})
			return
		}
		h.log.Error("failed to list tickets",
			slog.String("error", err.Error()),
			slog.String("workspace_id", filter.WorkspaceID),
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR", "Failed to list tickets", nil)
		return
	}

	response.Success(w, r, http.StatusOK, result)
}

// Get handles GET /v1/tickets/{ticketID} - Get ticket details.
func (h *TicketsHandler) Get(w http.ResponseWriter, r *http.Request) {
	ticketID := chi.URLParam(r, "ticketID")
	if ticketID == "" {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR", "ticket ID is required", nil)
		return
	}

	ticket, err := h.store.GetTicket(r.Context(), ticketID)
	if err != nil {
		if errors.Is(err, postgres.ErrNotFound) {
			response.Error(w, r, http.StatusNotFound, "NOT_FOUND", "Ticket not found",
				map[string]interface{}{"ticket_id": ticketID})
			return
		}
		h.log.Error("failed to get ticket",
			slog.String("error", err.Error()),
			slog.String("ticket_id", ticketID),
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR", "Failed to get ticket", nil)
		return
	}

	response.Success(w, r, http.StatusOK, ticket)
}

// Update handles PATCH /v1/tickets/{ticketID} - Update ticket fields.
func (h *TicketsHandler) Update(w http.ResponseWriter, r *http.Request) {
	ticketID := chi.URLParam(r, "ticketID")
	if ticketID == "" {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR", "ticket ID is required", nil)
		return
	}

	var req UpdateTicketRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error("failed to decode request body", slog.String("error", err.Error()))
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR", "Invalid JSON body", nil)
		return
	}

	// Validate status if provided
	if req.Status != nil && !isValidTicketStatus(*req.Status) {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR", "Invalid status value",
			map[string]interface{}{
				"fields": []response.FieldError{{
					Field:   "status",
					Code:    "invalid",
					Message: "status must be one of: open, in_progress, pending, resolved, closed",
				}},
			})
		return
	}

	// Validate priority if provided
	if req.Priority != nil && !isValidTicketPriority(*req.Priority) {
		response.Error(w, r, http.StatusBadRequest, "VALIDATION_ERROR", "Invalid priority value",
			map[string]interface{}{
				"fields": []response.FieldError{{
					Field:   "priority",
					Code:    "invalid",
					Message: "priority must be one of: low, medium, high, critical",
				}},
			})
		return
	}

	// Fetch existing ticket
	ticket, err := h.store.GetTicket(r.Context(), ticketID)
	if err != nil {
		if errors.Is(err, postgres.ErrNotFound) {
			response.Error(w, r, http.StatusNotFound, "NOT_FOUND", "Ticket not found",
				map[string]interface{}{"ticket_id": ticketID})
			return
		}
		h.log.Error("failed to get ticket for update",
			slog.String("error", err.Error()),
			slog.String("ticket_id", ticketID),
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR", "Failed to get ticket", nil)
		return
	}

	// Apply updates
	if req.Title != nil {
		ticket.Title = *req.Title
	}
	if req.Description != nil {
		ticket.Description = *req.Description
	}
	if req.Status != nil {
		ticket.Status = *req.Status
	}
	if req.Priority != nil {
		ticket.Priority = *req.Priority
	}
	if req.Labels != nil {
		ticket.Labels = req.Labels
	}
	if req.AssignedTo != nil {
		if *req.AssignedTo == "" {
			ticket.AssignedTo = sql.NullString{Valid: false}
		} else {
			ticket.AssignedTo = sql.NullString{String: *req.AssignedTo, Valid: true}
		}
	}
	if req.Metadata != nil {
		ticket.Metadata = req.Metadata
	}
	ticket.UpdatedAt = time.Now().UTC()

	if err := h.store.UpdateTicket(r.Context(), ticket); err != nil {
		h.log.Error("failed to update ticket",
			slog.String("error", err.Error()),
			slog.String("ticket_id", ticketID),
		)
		response.Error(w, r, http.StatusInternalServerError, "INTERNAL_ERROR", "Failed to update ticket", nil)
		return
	}

	h.log.Info("ticket updated",
		slog.String("ticket_id", ticket.ID),
		slog.String("workspace_id", ticket.WorkspaceID),
	)

	response.Success(w, r, http.StatusOK, ticket)
}

// CreateJob handles POST /v1/tickets/{ticketID}/jobs - Create a job under a ticket.
// This endpoint is a stub that returns 501 Not Implemented.
func (h *TicketsHandler) CreateJob(w http.ResponseWriter, r *http.Request) {
	ticketID := chi.URLParam(r, "ticketID")
	response.NotImplemented(w, r, "POST /v1/tickets/"+ticketID+"/jobs")
}

// Helper functions

func isValidTicketStatus(s models.TicketStatus) bool {
	switch s {
	case models.TicketStatusOpen, models.TicketStatusInProgress, models.TicketStatusPending,
		models.TicketStatusResolved, models.TicketStatusClosed:
		return true
	}
	return false
}

func isValidTicketPriority(p models.TicketPriority) bool {
	switch p {
	case models.TicketPriorityLow, models.TicketPriorityMedium, models.TicketPriorityHigh, models.TicketPriorityCritical:
		return true
	}
	return false
}

func splitAndTrim(s string) []string {
	var result []string
	for _, part := range strings.Split(s, ",") {
		trimmed := strings.TrimSpace(part)
		if trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}
