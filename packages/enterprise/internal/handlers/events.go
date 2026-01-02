package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/response"
)

// EventHandler handles event stream endpoints.
type EventHandler struct{}

// NewEventHandler creates a new event handler.
func NewEventHandler() *EventHandler {
	return &EventHandler{}
}

// Routes returns a chi router with event routes.
func (h *EventHandler) Routes() chi.Router {
	r := chi.NewRouter()

	r.Get("/stream", h.Stream)

	return r
}

// Stream handles GET /v1/events/stream - Server-Sent Events stream for real-time updates.
func (h *EventHandler) Stream(w http.ResponseWriter, r *http.Request) {
	response.NotImplemented(w, r, "GET /v1/events/stream")
}
