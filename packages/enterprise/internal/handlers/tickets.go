// Package handlers provides HTTP handlers for the Fastband Enterprise control plane API v1.
package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
)

// TicketHandler handles ticket-related endpoints.
type TicketHandler struct{}

// NewTicketHandler creates a new ticket handler.
func NewTicketHandler() *TicketHandler {
	return &TicketHandler{}
}

// Routes returns a chi router with ticket routes.
func (h *TicketHandler) Routes() chi.Router {
	r := chi.NewRouter()

	r.Post("/", h.Create)
	r.Get("/", h.List)
	r.Get("/{ticketID}", h.Get)
	r.Patch("/{ticketID}", h.Update)
	r.Post("/{ticketID}/jobs", h.CreateJob)

	return r
}

// Create handles POST /v1/tickets - Create a new ticket.
func (h *TicketHandler) Create(w http.ResponseWriter, r *http.Request) {
	response.NotImplemented(w, r, "POST /v1/tickets")
}

// List handles GET /v1/tickets - List tickets with filtering and pagination.
func (h *TicketHandler) List(w http.ResponseWriter, r *http.Request) {
	response.NotImplemented(w, r, "GET /v1/tickets")
}

// Get handles GET /v1/tickets/{ticketID} - Get ticket details.
func (h *TicketHandler) Get(w http.ResponseWriter, r *http.Request) {
	ticketID := chi.URLParam(r, "ticketID")
	response.NotImplemented(w, r, "GET /v1/tickets/"+ticketID)
}

// Update handles PATCH /v1/tickets/{ticketID} - Update ticket fields.
func (h *TicketHandler) Update(w http.ResponseWriter, r *http.Request) {
	ticketID := chi.URLParam(r, "ticketID")
	response.NotImplemented(w, r, "PATCH /v1/tickets/"+ticketID)
}

// CreateJob handles POST /v1/tickets/{ticketID}/jobs - Create a job under a ticket.
func (h *TicketHandler) CreateJob(w http.ResponseWriter, r *http.Request) {
	ticketID := chi.URLParam(r, "ticketID")
	response.NotImplemented(w, r, "POST /v1/tickets/"+ticketID+"/jobs")
}
