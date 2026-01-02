// Package response provides standardized API response formatting following the v1 envelope specification.
// All API responses use a consistent structure for both success and error cases.
package response

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/RemmyCH3CK/fastband-mcp/packages/enterprise/internal/requestid"
)

// Meta contains request metadata included in all responses.
type Meta struct {
	RequestID     string `json:"request_id"`
	CorrelationID string `json:"correlation_id,omitempty"`
	Timestamp     string `json:"timestamp"`
}

// ErrorDetail contains error information for error responses.
type ErrorDetail struct {
	Code             string                 `json:"code"`
	Message          string                 `json:"message"`
	Details          map[string]interface{} `json:"details,omitempty"`
	DocumentationURL string                 `json:"documentation_url,omitempty"`
}

// SuccessResponse represents a successful API response.
type SuccessResponse struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data"`
	Meta    Meta        `json:"meta"`
}

// ErrorResponse represents an error API response.
type ErrorResponse struct {
	Success bool        `json:"success"`
	Error   ErrorDetail `json:"error"`
	Meta    Meta        `json:"meta"`
}

// Writer provides methods for writing standardized API responses.
type Writer struct{}

// NewWriter creates a new response writer.
func NewWriter() *Writer {
	return &Writer{}
}

// Success writes a successful response with the given data.
func (w *Writer) Success(rw http.ResponseWriter, r *http.Request, status int, data interface{}) {
	resp := SuccessResponse{
		Success: true,
		Data:    data,
		Meta:    buildMeta(r),
	}
	writeJSON(rw, status, resp)
}

// Error writes an error response.
func (w *Writer) Error(rw http.ResponseWriter, r *http.Request, status int, code, message string, details map[string]interface{}) {
	resp := ErrorResponse{
		Success: false,
		Error: ErrorDetail{
			Code:    code,
			Message: message,
			Details: details,
		},
		Meta: buildMeta(r),
	}
	writeJSON(rw, status, resp)
}

// NotImplemented writes a 501 Not Implemented response in v1 envelope format.
func (w *Writer) NotImplemented(rw http.ResponseWriter, r *http.Request, endpoint string) {
	w.Error(rw, r, http.StatusNotImplemented, "NOT_IMPLEMENTED",
		"This endpoint is not yet implemented: "+endpoint, nil)
}

// Unauthorized writes a 401 Unauthorized response.
func (w *Writer) Unauthorized(rw http.ResponseWriter, r *http.Request, message string) {
	w.Error(rw, r, http.StatusUnauthorized, "AUTHENTICATION_REQUIRED", message, nil)
}

// Forbidden writes a 403 Forbidden response.
func (w *Writer) Forbidden(rw http.ResponseWriter, r *http.Request, message string) {
	w.Error(rw, r, http.StatusForbidden, "PERMISSION_DENIED", message, nil)
}

// NotFound writes a 404 Not Found response.
func (w *Writer) NotFound(rw http.ResponseWriter, r *http.Request, resource string) {
	w.Error(rw, r, http.StatusNotFound, "RESOURCE_NOT_FOUND",
		"Resource not found: "+resource, nil)
}

// ValidationError writes a 422 Unprocessable Entity response for validation failures.
func (w *Writer) ValidationError(rw http.ResponseWriter, r *http.Request, fields []FieldError) {
	details := map[string]interface{}{
		"fields": fields,
	}
	w.Error(rw, r, http.StatusUnprocessableEntity, "VALIDATION_ERROR",
		"Request validation failed", details)
}

// RateLimited writes a 429 Too Many Requests response.
func (w *Writer) RateLimited(rw http.ResponseWriter, r *http.Request, retryAfter int) {
	rw.Header().Set("Retry-After", string(rune(retryAfter)))
	w.Error(rw, r, http.StatusTooManyRequests, "RATE_LIMITED",
		"Too many requests", map[string]interface{}{"retry_after_seconds": retryAfter})
}

// InternalError writes a 500 Internal Server Error response.
func (w *Writer) InternalError(rw http.ResponseWriter, r *http.Request) {
	w.Error(rw, r, http.StatusInternalServerError, "INTERNAL_ERROR",
		"An unexpected error occurred", nil)
}

// ServiceUnavailable writes a 503 Service Unavailable response.
func (w *Writer) ServiceUnavailable(rw http.ResponseWriter, r *http.Request, reason string) {
	w.Error(rw, r, http.StatusServiceUnavailable, "SERVICE_UNAVAILABLE", reason, nil)
}

// FieldError represents a single field validation error.
type FieldError struct {
	Field   string `json:"field"`
	Code    string `json:"code"`
	Message string `json:"message"`
}

func buildMeta(r *http.Request) Meta {
	reqID := requestid.FromContext(r.Context())
	corrID := r.Header.Get("X-Correlation-ID")
	if corrID == "" {
		corrID = reqID // Use request ID as correlation ID if not provided
	}

	return Meta{
		RequestID:     reqID,
		CorrelationID: corrID,
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
	}
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

// Global writer instance for convenience
var defaultWriter = NewWriter()

// Success writes a successful response using the default writer.
func Success(w http.ResponseWriter, r *http.Request, status int, data interface{}) {
	defaultWriter.Success(w, r, status, data)
}

// Error writes an error response using the default writer.
func Error(w http.ResponseWriter, r *http.Request, status int, code, message string, details map[string]interface{}) {
	defaultWriter.Error(w, r, status, code, message, details)
}

// NotImplemented writes a 501 response using the default writer.
func NotImplemented(w http.ResponseWriter, r *http.Request, endpoint string) {
	defaultWriter.NotImplemented(w, r, endpoint)
}

// Unauthorized writes a 401 response using the default writer.
func Unauthorized(w http.ResponseWriter, r *http.Request, message string) {
	defaultWriter.Unauthorized(w, r, message)
}

// Forbidden writes a 403 response using the default writer.
func Forbidden(w http.ResponseWriter, r *http.Request, message string) {
	defaultWriter.Forbidden(w, r, message)
}

// NotFound writes a 404 response using the default writer.
func NotFound(w http.ResponseWriter, r *http.Request, resource string) {
	defaultWriter.NotFound(w, r, resource)
}

// InternalError writes a 500 response using the default writer.
func InternalError(w http.ResponseWriter, r *http.Request) {
	defaultWriter.InternalError(w, r)
}
