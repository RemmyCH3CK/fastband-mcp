"""
Security utilities for Fastband MCP.

Provides:
- Path validation and sanitization
- Input validation and sanitization
- SQL injection prevention helpers
- Secure configuration handling
"""

import logging
import os
import re
import secrets
import string
from pathlib import Path
from re import Pattern
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Path Security
# =============================================================================


class PathSecurityError(Exception):
    """Raised when a path fails security validation."""

    pass


class PathValidator:
    """
    Validates file paths to prevent path traversal and other attacks.

    Example:
        validator = PathValidator(allowed_roots=[Path("/project")])

        # Valid paths
        validator.validate("/project/src/file.py")  # OK

        # Invalid paths - raises PathSecurityError
        validator.validate("/project/../etc/passwd")  # Path traversal
        validator.validate("/etc/passwd")  # Outside allowed roots
    """

    # Patterns that indicate path traversal attempts
    DANGEROUS_PATTERNS: list[Pattern] = [
        re.compile(r"\.\."),  # Parent directory traversal
        re.compile(r"\.\.%2[fF]"),  # URL-encoded traversal
        re.compile(r"%2[eE]%2[eE]"),  # Double URL-encoded dots
        re.compile(r"\.\.\\"),  # Windows-style traversal
        re.compile(r"%00"),  # Null byte injection
        re.compile(r"\x00"),  # Actual null byte
    ]

    # Dangerous filenames on various systems
    DANGEROUS_NAMES: set[str] = {
        "con",
        "prn",
        "aux",
        "nul",  # Windows reserved
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
        ".",
        "..",
        "",  # Special directory entries
    }

    def __init__(
        self,
        allowed_roots: list[Path] | None = None,
        allow_symlinks: bool = False,
        max_path_length: int = 4096,
        allowed_extensions: set[str] | None = None,
        blocked_extensions: set[str] | None = None,
    ):
        """
        Initialize path validator.

        Args:
            allowed_roots: List of allowed root directories. If None, uses current directory.
            allow_symlinks: Whether to allow symlinks (default: False for security)
            max_path_length: Maximum allowed path length
            allowed_extensions: If set, only these extensions are allowed
            blocked_extensions: If set, these extensions are blocked
        """
        self.allowed_roots = [Path(p).resolve() for p in (allowed_roots or [Path.cwd()])]
        self.allow_symlinks = allow_symlinks
        self.max_path_length = max_path_length
        self.allowed_extensions = allowed_extensions
        self.blocked_extensions = blocked_extensions or {
            ".exe",
            ".dll",
            ".so",
            ".dylib",  # Executables
            ".sh",
            ".bash",
            ".cmd",
            ".bat",
            ".ps1",  # Scripts
        }

    def validate(self, path: str | Path) -> Path:
        """
        Validate a path and return the resolved, safe path.

        Args:
            path: Path to validate

        Returns:
            Resolved Path object

        Raises:
            PathSecurityError: If path fails validation
        """
        path_str = str(path)

        # Check path length
        if len(path_str) > self.max_path_length:
            raise PathSecurityError(f"Path exceeds maximum length of {self.max_path_length}")

        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.search(path_str):
                raise PathSecurityError(f"Path contains dangerous pattern: {path_str}")

        # Convert to Path and resolve
        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError) as e:
            raise PathSecurityError(f"Invalid path: {e}")

        # Check filename
        if resolved.name.lower() in self.DANGEROUS_NAMES:
            raise PathSecurityError(f"Dangerous filename: {resolved.name}")

        # Check if within allowed roots
        if not self._is_within_allowed_roots(resolved):
            raise PathSecurityError(
                f"Path {resolved} is outside allowed directories: {self.allowed_roots}"
            )

        # Check symlinks - must check BEFORE resolution since resolve() follows symlinks
        if not self.allow_symlinks:
            try:
                original_path = Path(path)
                if original_path.exists():
                    if original_path.is_symlink():
                        raise PathSecurityError(f"Symlinks not allowed: {path}")
                    # Check if any parent is a symlink
                    for parent in original_path.resolve().parents:
                        # Check the actual parent path, not the resolved one
                        parent_original = Path(str(parent))
                        if parent_original.is_symlink():
                            raise PathSecurityError(f"Path contains symlink: {parent}")
            except OSError:
                pass  # Path doesn't exist yet, can't be a symlink

        # Check extensions
        if self.allowed_extensions is not None:
            ext = resolved.suffix.lower()
            if ext and ext not in self.allowed_extensions:
                raise PathSecurityError(f"Extension not allowed: {ext}")

        if self.blocked_extensions:
            ext = resolved.suffix.lower()
            if ext in self.blocked_extensions:
                raise PathSecurityError(f"Extension blocked: {ext}")

        return resolved

    def _is_within_allowed_roots(self, path: Path) -> bool:
        """Check if path is within allowed root directories."""
        for root in self.allowed_roots:
            try:
                path.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def is_safe(self, path: str | Path) -> bool:
        """
        Check if a path is safe without raising exceptions.

        Args:
            path: Path to check

        Returns:
            True if path is safe, False otherwise
        """
        try:
            self.validate(path)
            return True
        except PathSecurityError:
            return False

    def sanitize(self, path: str | Path) -> Path:
        """
        Attempt to sanitize a path to make it safe.

        This removes dangerous components and normalizes the path.

        Args:
            path: Path to sanitize

        Returns:
            Sanitized Path object

        Raises:
            PathSecurityError: If path cannot be made safe
        """
        path_str = str(path)

        # Remove null bytes
        path_str = path_str.replace("\x00", "")

        # Normalize path separators
        path_str = path_str.replace("\\", "/")

        # Remove URL encoding of dangerous patterns
        path_str = re.sub(r"%2[eE]", ".", path_str)
        path_str = re.sub(r"%2[fF]", "/", path_str)
        path_str = re.sub(r"%00", "", path_str)

        # Convert to path and normalize
        try:
            normalized = Path(path_str).resolve()
        except (OSError, ValueError) as e:
            raise PathSecurityError(f"Cannot sanitize path: {e}")

        # Validate the sanitized path
        return self.validate(normalized)


def validate_path(
    path: str | Path,
    allowed_roots: list[Path] | None = None,
    allow_symlinks: bool = False,
) -> Path:
    """
    Convenience function to validate a path.

    Args:
        path: Path to validate
        allowed_roots: Allowed root directories
        allow_symlinks: Whether to allow symlinks

    Returns:
        Validated Path object

    Raises:
        PathSecurityError: If validation fails
    """
    validator = PathValidator(
        allowed_roots=allowed_roots,
        allow_symlinks=allow_symlinks,
    )
    return validator.validate(path)


# =============================================================================
# Input Sanitization
# =============================================================================


class InputSanitizer:
    """
    Sanitizes user input to prevent injection attacks.

    Example:
        sanitizer = InputSanitizer()

        # Sanitize text
        safe_text = sanitizer.sanitize_text("<script>alert('xss')</script>")

        # Sanitize for SQL LIKE patterns
        safe_pattern = sanitizer.sanitize_sql_like("50% off!")
    """

    # Characters that could be dangerous in various contexts
    HTML_ESCAPE_MAP = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
        "/": "&#x2F;",
    }

    # SQL LIKE pattern special characters
    SQL_LIKE_ESCAPE_MAP = {
        "%": "\\%",
        "_": "\\_",
        "\\": "\\\\",
    }

    def __init__(
        self,
        max_length: int = 10000,
        allow_newlines: bool = True,
        strip_html: bool = True,
    ):
        """
        Initialize sanitizer.

        Args:
            max_length: Maximum allowed input length
            allow_newlines: Whether to allow newline characters
            strip_html: Whether to strip HTML tags
        """
        self.max_length = max_length
        self.allow_newlines = allow_newlines
        self.strip_html = strip_html

    def sanitize_text(self, text: str) -> str:
        """
        Sanitize plain text input.

        Args:
            text: Input text

        Returns:
            Sanitized text
        """
        if not isinstance(text, str):
            text = str(text)

        # Truncate to max length
        text = text[: self.max_length]

        # Remove null bytes
        text = text.replace("\x00", "")

        # Handle newlines
        if not self.allow_newlines:
            text = text.replace("\n", " ").replace("\r", " ")

        # Strip HTML if requested
        if self.strip_html:
            text = re.sub(r"<[^>]+>", "", text)

        # Remove control characters (except newlines/tabs if allowed)
        if self.allow_newlines:
            text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        else:
            text = re.sub(r"[\x00-\x1f\x7f]", "", text)

        return text.strip()

    def escape_html(self, text: str) -> str:
        """
        Escape HTML special characters.

        Args:
            text: Input text

        Returns:
            HTML-escaped text
        """
        for char, escape in self.HTML_ESCAPE_MAP.items():
            text = text.replace(char, escape)
        return text

    def sanitize_sql_like(self, text: str) -> str:
        """
        Escape SQL LIKE pattern special characters.

        Use this when building LIKE patterns to prevent SQL injection.

        Args:
            text: Input text for LIKE pattern

        Returns:
            Escaped text safe for LIKE patterns
        """
        for char, escape in self.SQL_LIKE_ESCAPE_MAP.items():
            text = text.replace(char, escape)
        return text

    def sanitize_identifier(self, name: str, allowed_chars: str = "a-zA-Z0-9_") -> str:
        """
        Sanitize an identifier (e.g., table name, column name).

        Args:
            name: Input identifier
            allowed_chars: Regex character class of allowed characters

        Returns:
            Sanitized identifier
        """
        if not isinstance(name, str):
            name = str(name)

        # Remove all non-allowed characters
        pattern = f"[^{allowed_chars}]"
        sanitized = re.sub(pattern, "", name)

        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = "_" + sanitized

        return sanitized[:128]  # Reasonable identifier length limit

    def validate_email(self, email: str) -> bool:
        """
        Validate email format (basic check).

        Args:
            email: Email address to validate

        Returns:
            True if valid, False otherwise
        """
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email)) and len(email) <= 254

    def validate_url(self, url: str, allowed_schemes: set[str] | None = None) -> bool:
        """
        Validate URL format.

        Args:
            url: URL to validate
            allowed_schemes: Allowed URL schemes (default: http, https)

        Returns:
            True if valid, False otherwise
        """
        if allowed_schemes is None:
            allowed_schemes = {"http", "https"}

        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            return parsed.scheme in allowed_schemes and bool(parsed.netloc) and len(url) <= 2048
        except Exception:
            return False


def sanitize_input(text: str, **kwargs) -> str:
    """
    Convenience function to sanitize text input.

    Args:
        text: Input text
        **kwargs: Arguments passed to InputSanitizer

    Returns:
        Sanitized text
    """
    sanitizer = InputSanitizer(**kwargs)
    return sanitizer.sanitize_text(text)


# =============================================================================
# SQL Security
# =============================================================================


class SQLSecurityError(Exception):
    """Raised when SQL security check fails."""

    pass


def validate_sql_identifier(name: str) -> str:
    """
    Validate and return a safe SQL identifier.

    Args:
        name: Identifier name (table, column, etc.)

    Returns:
        Validated identifier

    Raises:
        SQLSecurityError: If identifier is invalid
    """
    if not isinstance(name, str):
        raise SQLSecurityError("Identifier must be a string")

    # Check length
    if len(name) > 128:
        raise SQLSecurityError("Identifier too long")

    if len(name) == 0:
        raise SQLSecurityError("Identifier cannot be empty")

    # Check for valid characters (alphanumeric and underscore only)
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise SQLSecurityError(f"Invalid identifier: {name}")

    # Check against SQL reserved words (common ones)
    reserved = {
        "select",
        "insert",
        "update",
        "delete",
        "drop",
        "create",
        "alter",
        "table",
        "index",
        "from",
        "where",
        "and",
        "or",
        "not",
        "null",
        "true",
        "false",
        "union",
        "join",
        "on",
    }
    if name.lower() in reserved:
        raise SQLSecurityError(f"Identifier is a reserved word: {name}")

    return name


def build_parameterized_query(
    base_query: str,
    conditions: list[tuple[str, str, Any]],
) -> tuple[str, list[Any]]:
    """
    Build a parameterized SQL query safely.

    Args:
        base_query: Base query without WHERE clause (e.g., "SELECT * FROM users")
        conditions: List of (column, operator, value) tuples
                   Operator must be one of: =, !=, <, >, <=, >=, LIKE, IN

    Returns:
        Tuple of (query_string, parameters_list)

    Example:
        query, params = build_parameterized_query(
            "SELECT * FROM users",
            [("status", "=", "active"), ("age", ">", 18)]
        )
        # Returns: ("SELECT * FROM users WHERE status = ? AND age > ?", ["active", 18])
    """
    allowed_operators = {"=", "!=", "<", ">", "<=", ">=", "LIKE", "IN", "IS"}

    if not conditions:
        return base_query, []

    where_parts = []
    params = []

    for column, operator, value in conditions:
        # Validate column name
        column = validate_sql_identifier(column)

        # Validate operator
        operator = operator.upper()
        if operator not in allowed_operators:
            raise SQLSecurityError(f"Invalid operator: {operator}")

        # Handle NULL specially
        if value is None:
            if operator == "=":
                where_parts.append(f"{column} IS NULL")
            elif operator == "!=":
                where_parts.append(f"{column} IS NOT NULL")
            else:
                raise SQLSecurityError(f"Cannot use {operator} with NULL")
        elif operator == "IN":
            if not isinstance(value, (list, tuple)):
                raise SQLSecurityError("IN operator requires a list")
            placeholders = ",".join("?" * len(value))
            where_parts.append(f"{column} IN ({placeholders})")
            params.extend(value)
        else:
            where_parts.append(f"{column} {operator} ?")
            params.append(value)

    query = f"{base_query} WHERE {' AND '.join(where_parts)}"
    return query, params


# =============================================================================
# Secrets and Keys
# =============================================================================


def generate_secret_key(length: int = 32) -> str:
    """
    Generate a cryptographically secure secret key.

    Args:
        length: Length of key in bytes (will be hex-encoded to 2x length)

    Returns:
        Hex-encoded secret key
    """
    return secrets.token_hex(length)


def generate_api_token(prefix: str = "fb", length: int = 32) -> str:
    """
    Generate an API token with a prefix.

    Args:
        prefix: Token prefix for identification
        length: Length of random part

    Returns:
        Token string (e.g., "fb_a1b2c3...")
    """
    chars = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(length))
    return f"{prefix}_{random_part}"


def mask_secret(secret: str, visible_chars: int = 4) -> str:
    """
    Mask a secret string for safe logging.

    Args:
        secret: Secret to mask
        visible_chars: Number of characters to show at end

    Returns:
        Masked string (e.g., "****abc123")
    """
    if not secret:
        return ""
    if len(secret) <= visible_chars:
        return "*" * len(secret)
    return "*" * (len(secret) - visible_chars) + secret[-visible_chars:]


def is_secret_key_secure(key: str, min_length: int = 32) -> tuple[bool, str]:
    """
    Check if a secret key meets security requirements.

    Args:
        key: Secret key to check
        min_length: Minimum required length

    Returns:
        Tuple of (is_secure, reason)
    """
    if not key:
        return False, "Key is empty"

    if len(key) < min_length:
        return False, f"Key too short (minimum {min_length} characters)"

    # Check for common weak keys
    weak_patterns = [
        "dev-secret-key",
        "secret",
        "password",
        "changeme",
        "example",
        "0" * 10,
        "1" * 10,
    ]
    for pattern in weak_patterns:
        if pattern in key.lower():
            return False, f"Key contains weak pattern: {pattern}"

    # Check entropy (should have mix of character types)
    has_upper = any(c.isupper() for c in key)
    has_lower = any(c.islower() for c in key)
    has_digit = any(c.isdigit() for c in key)

    if not (has_upper or has_lower or has_digit):
        return False, "Key lacks character variety"

    return True, "Key meets security requirements"


# =============================================================================
# Environment and Configuration Security
# =============================================================================


def get_env_or_default(
    key: str,
    default: str | None = None,
    required: bool = False,
) -> str | None:
    """
    Safely get an environment variable.

    Args:
        key: Environment variable name
        default: Default value if not set
        required: If True, raises ValueError when not set

    Returns:
        Environment variable value or default

    Raises:
        ValueError: If required and not set
    """
    value = os.environ.get(key)

    if value is None:
        if required:
            raise ValueError(f"Required environment variable not set: {key}")
        return default

    return value


def secure_config_dict(
    config: dict[str, Any], secret_keys: set[str] | None = None
) -> dict[str, Any]:
    """
    Create a copy of config dict with secrets masked.

    Args:
        config: Configuration dictionary
        secret_keys: Keys to mask (default: api_key, password, secret, token)

    Returns:
        Config dict with secrets masked
    """
    if secret_keys is None:
        secret_keys = {"api_key", "password", "secret", "token", "key", "credential"}

    def _mask_recursive(obj: Any, depth: int = 0) -> Any:
        if depth > 10:  # Prevent infinite recursion
            return obj

        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                key_lower = k.lower()
                if any(sk in key_lower for sk in secret_keys):
                    if isinstance(v, str):
                        result[k] = mask_secret(v)
                    else:
                        result[k] = "***MASKED***"
                else:
                    result[k] = _mask_recursive(v, depth + 1)
            return result
        elif isinstance(obj, list):
            return [_mask_recursive(item, depth + 1) for item in obj]
        else:
            return obj

    return _mask_recursive(config)
