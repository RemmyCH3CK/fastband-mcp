package config

import (
	"testing"
)

func TestLoad_FailClosed_MissingAuthSecret(t *testing.T) {
	// Use t.Setenv which automatically cleans up after the test
	t.Setenv("FASTBAND_AUTH_SECRET", "")
	t.Setenv("FASTBAND_LISTEN_ADDR", "")

	cfg, err := Load()
	if err == nil {
		t.Fatal("expected error when FASTBAND_AUTH_SECRET is not set")
	}

	if cfg != nil {
		t.Fatal("expected nil config on validation error")
	}

	if !IsFailClosedError(err) {
		t.Errorf("expected fail-closed error, got: %v", err)
	}
}

func TestLoad_Success(t *testing.T) {
	t.Setenv("FASTBAND_AUTH_SECRET", "test-secret-12345")
	t.Setenv("FASTBAND_LISTEN_ADDR", ":9090")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.AuthSecret != "test-secret-12345" {
		t.Errorf("expected auth secret 'test-secret-12345', got '%s'", cfg.AuthSecret)
	}

	if cfg.ListenAddr != ":9090" {
		t.Errorf("expected listen addr ':9090', got '%s'", cfg.ListenAddr)
	}
}

func TestLoad_DefaultValues(t *testing.T) {
	t.Setenv("FASTBAND_AUTH_SECRET", "test-secret")
	t.Setenv("FASTBAND_LISTEN_ADDR", "")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.ListenAddr != ":8080" {
		t.Errorf("expected default listen addr ':8080', got '%s'", cfg.ListenAddr)
	}

	if cfg.ShutdownTimeout.Seconds() != 30 {
		t.Errorf("expected default shutdown timeout 30s, got %v", cfg.ShutdownTimeout)
	}
}

func TestValidationError_Error(t *testing.T) {
	ve := ValidationError{
		Field:   "TEST_FIELD",
		Message: "test message",
	}

	expected := "config validation failed: TEST_FIELD: test message"
	if ve.Error() != expected {
		t.Errorf("expected '%s', got '%s'", expected, ve.Error())
	}
}

func TestMultiValidationError_Error(t *testing.T) {
	mve := MultiValidationError{
		Errors: []ValidationError{
			{Field: "FIELD1", Message: "msg1"},
			{Field: "FIELD2", Message: "msg2"},
		},
	}

	expected := "config validation failed: 2 errors"
	if mve.Error() != expected {
		t.Errorf("expected '%s', got '%s'", expected, mve.Error())
	}

	// Test single error
	mve.Errors = mve.Errors[:1]
	expected = "config validation failed: FIELD1: msg1"
	if mve.Error() != expected {
		t.Errorf("expected '%s', got '%s'", expected, mve.Error())
	}
}

func TestListenAddr_EnvVarPrecedence(t *testing.T) {
	t.Run("default is :8080", func(t *testing.T) {
		t.Setenv("FASTBAND_AUTH_SECRET", "test-secret")
		t.Setenv("FASTBAND_LISTEN_ADDR", "")
		t.Setenv("CONTROLPLANE_BIND_ADDR", "")

		cfg, err := Load()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.ListenAddr != ":8080" {
			t.Errorf("expected ':8080', got '%s'", cfg.ListenAddr)
		}
	})

	t.Run("FASTBAND_LISTEN_ADDR overrides default", func(t *testing.T) {
		t.Setenv("FASTBAND_AUTH_SECRET", "test-secret")
		t.Setenv("FASTBAND_LISTEN_ADDR", ":9090")
		t.Setenv("CONTROLPLANE_BIND_ADDR", "")

		cfg, err := Load()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.ListenAddr != ":9090" {
			t.Errorf("expected ':9090', got '%s'", cfg.ListenAddr)
		}
	})

	t.Run("CONTROLPLANE_BIND_ADDR works when FASTBAND_LISTEN_ADDR unset", func(t *testing.T) {
		t.Setenv("FASTBAND_AUTH_SECRET", "test-secret")
		t.Setenv("FASTBAND_LISTEN_ADDR", "")
		t.Setenv("CONTROLPLANE_BIND_ADDR", ":7070")

		cfg, err := Load()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.ListenAddr != ":7070" {
			t.Errorf("expected ':7070', got '%s'", cfg.ListenAddr)
		}
	})

	t.Run("FASTBAND_LISTEN_ADDR wins when both set", func(t *testing.T) {
		t.Setenv("FASTBAND_AUTH_SECRET", "test-secret")
		t.Setenv("FASTBAND_LISTEN_ADDR", ":9090")
		t.Setenv("CONTROLPLANE_BIND_ADDR", ":7070")

		cfg, err := Load()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.ListenAddr != ":9090" {
			t.Errorf("expected ':9090' (FASTBAND_LISTEN_ADDR wins), got '%s'", cfg.ListenAddr)
		}
	})
}

func TestIsFailClosedError(t *testing.T) {
	tests := []struct {
		name     string
		err      error
		expected bool
	}{
		{
			name: "auth secret validation error",
			err: ValidationError{
				Field:   "FASTBAND_AUTH_SECRET",
				Message: "required",
			},
			expected: true,
		},
		{
			name: "other validation error",
			err: ValidationError{
				Field:   "OTHER_FIELD",
				Message: "invalid",
			},
			expected: false,
		},
		{
			name: "multi error with auth secret",
			err: MultiValidationError{
				Errors: []ValidationError{
					{Field: "FASTBAND_AUTH_SECRET", Message: "required"},
				},
			},
			expected: true,
		},
		{
			name: "multi error without auth secret",
			err: MultiValidationError{
				Errors: []ValidationError{
					{Field: "OTHER", Message: "msg"},
				},
			},
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsFailClosedError(tt.err)
			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
		})
	}
}
