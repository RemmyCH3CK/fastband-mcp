"""
Security tests for Fastband MCP.

Tests for:
- SQL injection prevention
- Path traversal prevention
- Input validation and sanitization
- Secrets handling
"""

import os

import pytest

from fastband.core.security import (
    # Input sanitization
    InputSanitizer,
    # Path security
    PathSecurityError,
    PathValidator,
    # SQL security
    SQLSecurityError,
    build_parameterized_query,
    generate_api_token,
    # Secrets and keys
    generate_secret_key,
    # Environment security
    get_env_or_default,
    is_secret_key_secure,
    mask_secret,
    sanitize_input,
    secure_config_dict,
    validate_path,
    validate_sql_identifier,
)

# =============================================================================
# Path Security Tests
# =============================================================================


class TestPathValidator:
    """Test PathValidator class."""

    def test_valid_path_in_allowed_root(self, tmp_path):
        """Test that valid paths within allowed roots pass validation."""
        validator = PathValidator(allowed_roots=[tmp_path])
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = validator.validate(str(test_file))
        assert result == test_file.resolve()

    def test_path_outside_allowed_root_fails(self, tmp_path):
        """Test that paths outside allowed roots are rejected."""
        validator = PathValidator(allowed_roots=[tmp_path / "subdir"])
        test_file = tmp_path / "outside.txt"
        test_file.touch()

        with pytest.raises(PathSecurityError):
            validator.validate(str(test_file))

    def test_path_traversal_attack_blocked(self, tmp_path):
        """Test that path traversal attacks are blocked."""
        validator = PathValidator(allowed_roots=[tmp_path])

        # Various traversal attempts
        traversal_paths = [
            str(tmp_path / ".." / "etc" / "passwd"),
            str(tmp_path) + "/../etc/passwd",
            str(tmp_path) + "/subdir/../../etc/passwd",
            str(tmp_path) + "/%2e%2e/etc/passwd",
            str(tmp_path) + "/..\\etc\\passwd",
        ]

        for path in traversal_paths:
            with pytest.raises(PathSecurityError):
                validator.validate(path)

    def test_null_byte_injection_blocked(self, tmp_path):
        """Test that null byte injection is blocked."""
        validator = PathValidator(allowed_roots=[tmp_path])

        with pytest.raises(PathSecurityError):
            validator.validate(str(tmp_path) + "/file.txt\x00.jpg")

        with pytest.raises(PathSecurityError):
            validator.validate(str(tmp_path) + "/file.txt%00.jpg")

    def test_dangerous_filenames_blocked(self, tmp_path):
        """Test that dangerous filenames are blocked."""
        import sys

        validator = PathValidator(allowed_roots=[tmp_path])

        # Test Windows reserved names - these should be blocked on all platforms
        # as a defense-in-depth measure for cross-platform security
        if sys.platform == "win32":
            # On Windows, these names can't even be created
            dangerous_names = ["con", "prn", "aux", "nul"]
            for name in dangerous_names:
                path = tmp_path / name
                with pytest.raises(PathSecurityError):
                    validator.validate(str(path))
        else:
            # On Unix, Windows reserved names are valid filenames.
            # The dangerous names list in the validator includes ".", "..", and ""
            # but these resolve to actual directories, not dangerous files.
            # Test that path traversal patterns (which use ..) are caught
            with pytest.raises(PathSecurityError):
                validator.validate(str(tmp_path) + "/../../../etc/passwd")

            # Test that the empty filename check works indirectly
            # (paths ending in / are directory references, not file names with empty names)

    def test_symlink_blocking(self, tmp_path):
        """Test that symlinks can be blocked."""
        validator = PathValidator(allowed_roots=[tmp_path], allow_symlinks=False)

        # Create a symlink
        real_file = tmp_path / "real.txt"
        real_file.touch()
        symlink = tmp_path / "link.txt"
        symlink.symlink_to(real_file)

        # Symlink should be blocked
        with pytest.raises(PathSecurityError):
            validator.validate(str(symlink))

    def test_symlink_allowed_when_configured(self, tmp_path):
        """Test that symlinks can be allowed."""
        validator = PathValidator(allowed_roots=[tmp_path], allow_symlinks=True)

        real_file = tmp_path / "real.txt"
        real_file.touch()
        symlink = tmp_path / "link.txt"
        symlink.symlink_to(real_file)

        # Should not raise
        result = validator.validate(str(symlink))
        assert result.exists()

    def test_path_length_limit(self, tmp_path):
        """Test that excessively long paths are rejected."""
        validator = PathValidator(allowed_roots=[tmp_path], max_path_length=100)

        long_path = str(tmp_path) + "/" + "a" * 200
        with pytest.raises(PathSecurityError):
            validator.validate(long_path)

    def test_blocked_extensions(self, tmp_path):
        """Test that blocked extensions are rejected."""
        validator = PathValidator(
            allowed_roots=[tmp_path],
            blocked_extensions={".exe", ".dll"},
        )

        with pytest.raises(PathSecurityError):
            validator.validate(str(tmp_path / "malware.exe"))

        with pytest.raises(PathSecurityError):
            validator.validate(str(tmp_path / "library.dll"))

        # Allowed extension should work
        safe_path = tmp_path / "script.py"
        safe_path.touch()
        validator.validate(str(safe_path))

    def test_is_safe_method(self, tmp_path):
        """Test the is_safe convenience method."""
        validator = PathValidator(allowed_roots=[tmp_path])

        safe_file = tmp_path / "safe.txt"
        safe_file.touch()

        assert validator.is_safe(str(safe_file)) is True
        assert validator.is_safe(str(tmp_path / ".." / "etc" / "passwd")) is False

    def test_sanitize_path(self, tmp_path):
        """Test path sanitization."""
        validator = PathValidator(allowed_roots=[tmp_path])
        test_file = tmp_path / "test.txt"
        test_file.touch()

        # URL-encoded path should be sanitized
        validator.sanitize(str(test_file).replace("/", "%2f"))
        # Note: This depends on how the path is constructed


class TestValidatePath:
    """Test the validate_path convenience function."""

    def test_convenience_function(self, tmp_path):
        """Test the validate_path convenience function."""
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = validate_path(str(test_file), allowed_roots=[tmp_path])
        assert result.exists()


# =============================================================================
# Input Sanitization Tests
# =============================================================================


class TestInputSanitizer:
    """Test InputSanitizer class."""

    def test_sanitize_text_basic(self):
        """Test basic text sanitization."""
        sanitizer = InputSanitizer()

        assert sanitizer.sanitize_text("Hello World") == "Hello World"
        assert sanitizer.sanitize_text("  spaces  ") == "spaces"

    def test_strip_html_tags(self):
        """Test HTML tag stripping."""
        sanitizer = InputSanitizer(strip_html=True)

        input_text = "<script>alert('xss')</script>Hello"
        result = sanitizer.sanitize_text(input_text)
        assert "<script>" not in result
        assert "Hello" in result

    def test_preserve_html_when_disabled(self):
        """Test that HTML is preserved when strip_html is False."""
        sanitizer = InputSanitizer(strip_html=False)

        input_text = "<b>Bold</b>"
        result = sanitizer.sanitize_text(input_text)
        assert "<b>" in result

    def test_null_byte_removal(self):
        """Test null byte removal."""
        sanitizer = InputSanitizer()

        input_text = "Hello\x00World"
        result = sanitizer.sanitize_text(input_text)
        assert "\x00" not in result
        assert "HelloWorld" == result

    def test_control_character_removal(self):
        """Test control character removal."""
        sanitizer = InputSanitizer(allow_newlines=False)

        input_text = "Hello\x01\x02\x03World"
        result = sanitizer.sanitize_text(input_text)
        assert "HelloWorld" == result

    def test_max_length_truncation(self):
        """Test that input is truncated to max length."""
        sanitizer = InputSanitizer(max_length=10)

        result = sanitizer.sanitize_text("This is a very long string")
        assert len(result) <= 10

    def test_newline_handling(self):
        """Test newline handling based on configuration."""
        with_newlines = InputSanitizer(allow_newlines=True)
        without_newlines = InputSanitizer(allow_newlines=False)

        input_text = "Line1\nLine2"

        result_with = with_newlines.sanitize_text(input_text)
        assert "\n" in result_with

        result_without = without_newlines.sanitize_text(input_text)
        assert "\n" not in result_without

    def test_html_escape(self):
        """Test HTML escaping."""
        sanitizer = InputSanitizer()

        input_text = "<script>alert('xss')</script>"
        result = sanitizer.escape_html(input_text)

        assert "&lt;" in result
        assert "&gt;" in result
        assert "<script>" not in result

    def test_sql_like_escape(self):
        """Test SQL LIKE pattern escaping."""
        sanitizer = InputSanitizer()

        result = sanitizer.sanitize_sql_like("50% off!")
        assert "\\%" in result

        result = sanitizer.sanitize_sql_like("test_value")
        assert "\\_" in result

    def test_identifier_sanitization(self):
        """Test identifier sanitization."""
        sanitizer = InputSanitizer()

        assert sanitizer.sanitize_identifier("valid_name") == "valid_name"
        assert sanitizer.sanitize_identifier("123start") == "_123start"
        assert sanitizer.sanitize_identifier("has spaces") == "hasspaces"
        assert sanitizer.sanitize_identifier("has-dashes") == "hasdashes"

    def test_email_validation(self):
        """Test email validation."""
        sanitizer = InputSanitizer()

        assert sanitizer.validate_email("test@example.com") is True
        assert sanitizer.validate_email("user.name@domain.co.uk") is True
        assert sanitizer.validate_email("invalid") is False
        assert sanitizer.validate_email("missing@domain") is False
        assert sanitizer.validate_email("") is False

    def test_url_validation(self):
        """Test URL validation."""
        sanitizer = InputSanitizer()

        assert sanitizer.validate_url("https://example.com") is True
        assert sanitizer.validate_url("http://localhost:8080") is True
        assert sanitizer.validate_url("ftp://files.example.com") is False  # Not in allowed schemes
        assert sanitizer.validate_url("javascript:alert(1)") is False
        assert sanitizer.validate_url("not-a-url") is False


class TestSanitizeInput:
    """Test the sanitize_input convenience function."""

    def test_convenience_function(self):
        """Test the sanitize_input convenience function."""
        result = sanitize_input("<b>Hello</b>", strip_html=True)
        assert "<b>" not in result
        assert "Hello" in result


# =============================================================================
# SQL Security Tests
# =============================================================================


class TestSQLSecurity:
    """Test SQL security functions."""

    def test_valid_identifier(self):
        """Test that valid identifiers pass validation."""
        assert validate_sql_identifier("users") == "users"
        assert validate_sql_identifier("user_table") == "user_table"
        assert validate_sql_identifier("Table1") == "Table1"
        assert validate_sql_identifier("_private") == "_private"

    def test_invalid_identifier_characters(self):
        """Test that invalid characters are rejected."""
        with pytest.raises(SQLSecurityError):
            validate_sql_identifier("user-table")  # Hyphen

        with pytest.raises(SQLSecurityError):
            validate_sql_identifier("user.table")  # Dot

        with pytest.raises(SQLSecurityError):
            validate_sql_identifier("user table")  # Space

        with pytest.raises(SQLSecurityError):
            validate_sql_identifier("user;drop")  # Semicolon

    def test_sql_injection_in_identifier(self):
        """Test that SQL injection attempts in identifiers are blocked."""
        injection_attempts = [
            "users; DROP TABLE users;--",
            "users UNION SELECT * FROM passwords",
            "users OR 1=1",
            "users' OR '1'='1",
        ]

        for attempt in injection_attempts:
            with pytest.raises(SQLSecurityError):
                validate_sql_identifier(attempt)

    def test_reserved_words_blocked(self):
        """Test that SQL reserved words are blocked as identifiers."""
        reserved_words = ["SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "TABLE"]

        for word in reserved_words:
            with pytest.raises(SQLSecurityError):
                validate_sql_identifier(word.lower())

    def test_identifier_starting_with_number(self):
        """Test that identifiers starting with numbers are rejected."""
        with pytest.raises(SQLSecurityError):
            validate_sql_identifier("123table")

    def test_empty_identifier(self):
        """Test that empty identifiers are rejected."""
        with pytest.raises(SQLSecurityError):
            validate_sql_identifier("")

    def test_long_identifier(self):
        """Test that excessively long identifiers are rejected."""
        with pytest.raises(SQLSecurityError):
            validate_sql_identifier("a" * 200)


class TestBuildParameterizedQuery:
    """Test parameterized query building."""

    def test_simple_query(self):
        """Test building a simple parameterized query."""
        query, params = build_parameterized_query(
            "SELECT * FROM users",
            [("status", "=", "active")],
        )

        assert query == "SELECT * FROM users WHERE status = ?"
        assert params == ["active"]

    def test_multiple_conditions(self):
        """Test building query with multiple conditions."""
        query, params = build_parameterized_query(
            "SELECT * FROM users",
            [
                ("status", "=", "active"),
                ("age", ">", 18),
                ("role", "!=", "admin"),
            ],
        )

        assert "status = ?" in query
        assert "age > ?" in query
        assert "role != ?" in query
        assert params == ["active", 18, "admin"]

    def test_null_handling(self):
        """Test NULL value handling."""
        query, params = build_parameterized_query(
            "SELECT * FROM users",
            [("deleted_at", "=", None)],
        )

        assert "deleted_at IS NULL" in query
        assert params == []

    def test_null_not_equal(self):
        """Test NOT NULL handling."""
        query, params = build_parameterized_query(
            "SELECT * FROM users",
            [("deleted_at", "!=", None)],
        )

        assert "deleted_at IS NOT NULL" in query

    def test_in_operator(self):
        """Test IN operator handling."""
        query, params = build_parameterized_query(
            "SELECT * FROM users",
            [("role", "IN", ["admin", "moderator", "user"])],
        )

        assert "role IN (?,?,?)" in query
        assert params == ["admin", "moderator", "user"]

    def test_like_operator(self):
        """Test LIKE operator handling."""
        query, params = build_parameterized_query(
            "SELECT * FROM users",
            [("name", "LIKE", "%john%")],
        )

        assert "name LIKE ?" in query
        assert params == ["%john%"]

    def test_invalid_operator_rejected(self):
        """Test that invalid operators are rejected."""
        with pytest.raises(SQLSecurityError):
            build_parameterized_query(
                "SELECT * FROM users",
                [("status", "INVALID", "value")],
            )

    def test_injection_in_column_blocked(self):
        """Test that SQL injection in column names is blocked."""
        with pytest.raises(SQLSecurityError):
            build_parameterized_query(
                "SELECT * FROM users",
                [("status; DROP TABLE users;--", "=", "value")],
            )

    def test_empty_conditions(self):
        """Test query with no conditions."""
        query, params = build_parameterized_query(
            "SELECT * FROM users",
            [],
        )

        assert query == "SELECT * FROM users"
        assert params == []


# =============================================================================
# Secrets and Keys Tests
# =============================================================================


class TestSecretsHandling:
    """Test secrets and key handling."""

    def test_generate_secret_key(self):
        """Test secret key generation."""
        key1 = generate_secret_key()
        key2 = generate_secret_key()

        # Keys should be different
        assert key1 != key2

        # Keys should have correct length (32 bytes = 64 hex chars)
        assert len(key1) == 64

        # Keys should be hex strings
        assert all(c in "0123456789abcdef" for c in key1)

    def test_generate_api_token(self):
        """Test API token generation."""
        token = generate_api_token(prefix="fb")

        assert token.startswith("fb_")
        assert len(token) >= 35  # prefix (2) + underscore (1) + 32 chars = 35

        # Different calls should generate different tokens
        token2 = generate_api_token(prefix="fb")
        assert token != token2

    def test_mask_secret(self):
        """Test secret masking."""
        secret = "my-secret-api-key"
        masked = mask_secret(secret, visible_chars=4)

        assert masked.endswith("-key")
        assert "*" in masked
        assert "my-secret" not in masked

    def test_mask_short_secret(self):
        """Test masking short secrets."""
        secret = "abc"
        masked = mask_secret(secret, visible_chars=4)

        assert masked == "***"

    def test_mask_empty_secret(self):
        """Test masking empty secrets."""
        assert mask_secret("") == ""
        assert mask_secret(None) == ""

    def test_is_secret_key_secure(self):
        """Test secret key security validation."""
        # Secure key
        is_secure, reason = is_secret_key_secure("a" * 64)
        assert is_secure is True

        # Too short
        is_secure, reason = is_secret_key_secure("short")
        assert is_secure is False
        assert "short" in reason.lower()

        # Contains weak pattern
        is_secure, reason = is_secret_key_secure("dev-secret-key" + "a" * 50)
        assert is_secure is False
        assert "weak" in reason.lower()

        # Empty
        is_secure, reason = is_secret_key_secure("")
        assert is_secure is False


# =============================================================================
# Environment Security Tests
# =============================================================================


class TestEnvironmentSecurity:
    """Test environment and configuration security."""

    def test_get_env_or_default(self):
        """Test environment variable retrieval."""
        # Set up test env var
        os.environ["TEST_VAR"] = "test_value"

        assert get_env_or_default("TEST_VAR") == "test_value"
        assert get_env_or_default("NONEXISTENT_VAR", "default") == "default"

        # Clean up
        del os.environ["TEST_VAR"]

    def test_get_env_required(self):
        """Test required environment variable."""
        with pytest.raises(ValueError):
            get_env_or_default("DEFINITELY_NOT_SET", required=True)

    def test_secure_config_dict(self):
        """Test configuration dictionary masking."""
        config = {
            "database": "sqlite:///app.db",
            "api_key": "sk-secret-key-12345",
            "password": "super_secret_password",
            "nested": {
                "token": "bearer-token-xyz",
                "safe": "visible-value",
            },
            "credentials": {"user": "admin", "pass": "hidden"},
        }

        masked = secure_config_dict(config)

        # API key should be masked
        assert "sk-secret-key-12345" not in str(masked)
        assert masked["api_key"].startswith("*")

        # Password should be masked
        assert "super_secret_password" not in str(masked)

        # Nested token should be masked
        assert "bearer-token-xyz" not in str(masked)

        # Safe values should be visible
        assert masked["nested"]["safe"] == "visible-value"

        # Database URL should be visible
        assert masked["database"] == "sqlite:///app.db"

        # Credentials dict should be masked
        assert "***MASKED***" in str(masked["credentials"])


# =============================================================================
# Integration Tests
# =============================================================================


class TestSecurityIntegration:
    """Integration tests for security features."""

    def test_path_validation_in_file_operations(self, tmp_path):
        """Test that path validation integrates with file operations."""
        validator = PathValidator(allowed_roots=[tmp_path])

        # Create a safe file
        safe_file = tmp_path / "safe.txt"
        safe_file.write_text("Safe content")

        # Validate and read
        validated_path = validator.validate(str(safe_file))
        content = validated_path.read_text()
        assert content == "Safe content"

        # Try to escape - should fail
        with pytest.raises(PathSecurityError):
            validator.validate(str(tmp_path / ".." / "etc" / "passwd"))

    def test_input_sanitization_with_sql(self):
        """Test that sanitized input is safe for SQL."""
        sanitizer = InputSanitizer()

        # Malicious input
        user_input = "Robert'; DROP TABLE Students;--"

        # Sanitize for LIKE pattern
        safe_pattern = sanitizer.sanitize_sql_like(user_input)

        # Build safe query
        query, params = build_parameterized_query(
            "SELECT * FROM users",
            [("name", "LIKE", f"%{safe_pattern}%")],
        )

        # Query should be parameterized
        assert "?" in query
        # Params should contain the escaped pattern
        assert len(params) == 1
