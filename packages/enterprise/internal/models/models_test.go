package models

import (
	"encoding/json"
	"testing"
)

func TestJSONB_Scan(t *testing.T) {
	tests := []struct {
		name    string
		input   interface{}
		want    JSONB
		wantErr bool
	}{
		{
			name:    "nil value",
			input:   nil,
			want:    nil,
			wantErr: false,
		},
		{
			name:    "valid bytes",
			input:   []byte(`{"key": "value"}`),
			want:    JSONB{"key": "value"},
			wantErr: false,
		},
		{
			name:    "valid string",
			input:   `{"key": "value"}`,
			want:    JSONB{"key": "value"},
			wantErr: false,
		},
		{
			name:    "empty object",
			input:   []byte(`{}`),
			want:    JSONB{},
			wantErr: false,
		},
		{
			name:    "invalid json",
			input:   []byte(`{invalid}`),
			want:    nil,
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var j JSONB
			err := j.Scan(tt.input)

			if (err != nil) != tt.wantErr {
				t.Errorf("JSONB.Scan() error = %v, wantErr %v", err, tt.wantErr)
				return
			}

			if !tt.wantErr && tt.want != nil {
				wantJSON, _ := json.Marshal(tt.want)
				gotJSON, _ := json.Marshal(j)
				if string(wantJSON) != string(gotJSON) {
					t.Errorf("JSONB.Scan() = %s, want %s", gotJSON, wantJSON)
				}
			}
		})
	}
}

func TestStringArray_Scan(t *testing.T) {
	tests := []struct {
		name    string
		input   interface{}
		want    StringArray
		wantErr bool
	}{
		{
			name:    "nil value",
			input:   nil,
			want:    nil,
			wantErr: false,
		},
		{
			name:    "valid bytes",
			input:   []byte(`["a", "b", "c"]`),
			want:    StringArray{"a", "b", "c"},
			wantErr: false,
		},
		{
			name:    "valid string",
			input:   `["x", "y"]`,
			want:    StringArray{"x", "y"},
			wantErr: false,
		},
		{
			name:    "empty array",
			input:   []byte(`[]`),
			want:    StringArray{},
			wantErr: false,
		},
		{
			name:    "invalid json",
			input:   []byte(`[invalid]`),
			want:    nil,
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var a StringArray
			err := a.Scan(tt.input)

			if (err != nil) != tt.wantErr {
				t.Errorf("StringArray.Scan() error = %v, wantErr %v", err, tt.wantErr)
				return
			}

			if !tt.wantErr && tt.want != nil {
				if len(a) != len(tt.want) {
					t.Errorf("StringArray.Scan() length = %d, want %d", len(a), len(tt.want))
					return
				}
				for i, v := range a {
					if v != tt.want[i] {
						t.Errorf("StringArray.Scan()[%d] = %s, want %s", i, v, tt.want[i])
					}
				}
			}
		})
	}
}

func TestTicketStatus_Constants(t *testing.T) {
	// Verify status constants are defined correctly
	statuses := []TicketStatus{
		TicketStatusOpen,
		TicketStatusInProgress,
		TicketStatusPending,
		TicketStatusResolved,
		TicketStatusClosed,
	}

	expected := []string{"open", "in_progress", "pending", "resolved", "closed"}

	for i, s := range statuses {
		if string(s) != expected[i] {
			t.Errorf("TicketStatus %d = %s, want %s", i, s, expected[i])
		}
	}
}

func TestJobStatus_Constants(t *testing.T) {
	statuses := []JobStatus{
		JobStatusQueued,
		JobStatusRunning,
		JobStatusCompleted,
		JobStatusFailed,
		JobStatusCancelled,
	}

	expected := []string{"queued", "running", "completed", "failed", "cancelled"}

	for i, s := range statuses {
		if string(s) != expected[i] {
			t.Errorf("JobStatus %d = %s, want %s", i, s, expected[i])
		}
	}
}

func TestApprovalStatus_Constants(t *testing.T) {
	statuses := []ApprovalStatus{
		ApprovalStatusPending,
		ApprovalStatusApproved,
		ApprovalStatusRejected,
		ApprovalStatusExpired,
	}

	expected := []string{"pending", "approved", "rejected", "expired"}

	for i, s := range statuses {
		if string(s) != expected[i] {
			t.Errorf("ApprovalStatus %d = %s, want %s", i, s, expected[i])
		}
	}
}

func TestEventCategory_Constants(t *testing.T) {
	categories := []EventCategory{
		EventCategorySecurity,
		EventCategoryCompliance,
		EventCategoryOperational,
		EventCategoryAccess,
		EventCategoryData,
	}

	expected := []string{"security", "compliance", "operational", "access", "data"}

	for i, c := range categories {
		if string(c) != expected[i] {
			t.Errorf("EventCategory %d = %s, want %s", i, c, expected[i])
		}
	}
}

func TestEventSeverity_Constants(t *testing.T) {
	severities := []EventSeverity{
		EventSeverityInfo,
		EventSeverityWarning,
		EventSeverityError,
		EventSeverityCritical,
	}

	expected := []string{"info", "warning", "error", "critical"}

	for i, s := range severities {
		if string(s) != expected[i] {
			t.Errorf("EventSeverity %d = %s, want %s", i, s, expected[i])
		}
	}
}

func TestTicket_JSON(t *testing.T) {
	ticket := Ticket{
		ID:          "ticket-123",
		WorkspaceID: "ws-456",
		Title:       "Test Ticket",
		Description: "Test Description",
		Status:      TicketStatusOpen,
		Priority:    TicketPriorityHigh,
		Labels:      StringArray{"bug", "urgent"},
		CreatedBy:   "user-789",
		Metadata:    JSONB{"custom": "data"},
	}

	data, err := json.Marshal(ticket)
	if err != nil {
		t.Fatalf("Failed to marshal ticket: %v", err)
	}

	var decoded Ticket
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("Failed to unmarshal ticket: %v", err)
	}

	if decoded.ID != ticket.ID {
		t.Errorf("ID = %s, want %s", decoded.ID, ticket.ID)
	}
	if decoded.Status != ticket.Status {
		t.Errorf("Status = %s, want %s", decoded.Status, ticket.Status)
	}
	if decoded.Priority != ticket.Priority {
		t.Errorf("Priority = %s, want %s", decoded.Priority, ticket.Priority)
	}
}
