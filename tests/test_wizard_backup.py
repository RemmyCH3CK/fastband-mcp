"""Tests for the Backup Configuration wizard step."""

import tempfile
from pathlib import Path

import pytest

from fastband.core.config import BackupConfig, FastbandConfig
from fastband.wizard.base import (
    StepStatus,
    WizardContext,
)
from fastband.wizard.steps.backup import BackupConfigurationStep

# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def wizard_context(temp_dir):
    """Create a wizard context for testing."""
    return WizardContext(
        project_path=temp_dir,
        config=FastbandConfig(),
        interactive=True,
    )


@pytest.fixture
def non_interactive_context(temp_dir):
    """Create a non-interactive wizard context for testing."""
    return WizardContext(
        project_path=temp_dir,
        config=FastbandConfig(),
        interactive=False,
    )


@pytest.fixture
def backup_step():
    """Create a BackupConfigurationStep instance."""
    return BackupConfigurationStep()


# =============================================================================
# STEP PROPERTIES TESTS
# =============================================================================


class TestBackupStepProperties:
    """Tests for BackupConfigurationStep properties."""

    def test_name(self, backup_step):
        """Test step name property."""
        assert backup_step.name == "backup"

    def test_title(self, backup_step):
        """Test step title property."""
        assert backup_step.title == "Backup Configuration"

    def test_description(self, backup_step):
        """Test step description property."""
        assert "backup" in backup_step.description.lower()

    def test_required(self, backup_step):
        """Test step is not required."""
        assert backup_step.required is False

    def test_initial_status(self, backup_step):
        """Test initial step status."""
        assert backup_step.status == StepStatus.PENDING


# =============================================================================
# DATABASE DETECTION TESTS
# =============================================================================


class TestDatabaseDetection:
    """Tests for database type detection."""

    def test_detect_sqlite_by_db_file(self, backup_step, temp_dir):
        """Test SQLite detection by .db file."""
        db_file = temp_dir / "data.db"
        db_file.touch()

        result = backup_step.detect_database_type(temp_dir)
        assert result == "sqlite"

    def test_detect_sqlite_by_sqlite_file(self, backup_step, temp_dir):
        """Test SQLite detection by .sqlite file."""
        db_file = temp_dir / "database.sqlite"
        db_file.touch()

        result = backup_step.detect_database_type(temp_dir)
        assert result == "sqlite"

    def test_detect_sqlite_by_sqlite3_file(self, backup_step, temp_dir):
        """Test SQLite detection by .sqlite3 file."""
        db_file = temp_dir / "app.sqlite3"
        db_file.touch()

        result = backup_step.detect_database_type(temp_dir)
        assert result == "sqlite"

    def test_detect_sqlite_by_fastband_data_db(self, backup_step, temp_dir):
        """Test SQLite detection by .fastband/data.db."""
        fastband_dir = temp_dir / ".fastband"
        fastband_dir.mkdir()
        db_file = fastband_dir / "data.db"
        db_file.touch()

        result = backup_step.detect_database_type(temp_dir)
        assert result == "sqlite"

    def test_detect_postgresql_by_pg_hba(self, backup_step, temp_dir):
        """Test PostgreSQL detection by pg_hba.conf."""
        pg_file = temp_dir / "pg_hba.conf"
        pg_file.touch()

        result = backup_step.detect_database_type(temp_dir)
        assert result == "postgresql"

    def test_detect_postgresql_by_pgpass(self, backup_step, temp_dir):
        """Test PostgreSQL detection by .pgpass."""
        pgpass_file = temp_dir / ".pgpass"
        pgpass_file.touch()

        result = backup_step.detect_database_type(temp_dir)
        assert result == "postgresql"

    def test_detect_mysql_by_my_cnf(self, backup_step, temp_dir):
        """Test MySQL detection by my.cnf."""
        mysql_file = temp_dir / "my.cnf"
        mysql_file.touch()

        result = backup_step.detect_database_type(temp_dir)
        assert result == "mysql"

    def test_detect_mysql_by_dot_my_cnf(self, backup_step, temp_dir):
        """Test MySQL detection by .my.cnf."""
        mysql_file = temp_dir / ".my.cnf"
        mysql_file.touch()

        result = backup_step.detect_database_type(temp_dir)
        assert result == "mysql"

    def test_detect_sqlite_from_env_file(self, backup_step, temp_dir):
        """Test SQLite detection from .env file."""
        env_file = temp_dir / ".env"
        env_file.write_text("DATABASE_URL=sqlite:///data.db")

        result = backup_step.detect_database_type(temp_dir)
        assert result == "sqlite"

    def test_detect_postgresql_from_env_file(self, backup_step, temp_dir):
        """Test PostgreSQL detection from .env file."""
        env_file = temp_dir / ".env"
        env_file.write_text("DATABASE_URL=postgresql://user:pass@localhost/db")

        result = backup_step.detect_database_type(temp_dir)
        assert result == "postgresql"

    def test_detect_mysql_from_env_file(self, backup_step, temp_dir):
        """Test MySQL detection from .env file."""
        env_file = temp_dir / ".env"
        env_file.write_text("DATABASE_URL=mysql://user:pass@localhost/db")

        result = backup_step.detect_database_type(temp_dir)
        assert result == "mysql"

    def test_default_to_sqlite_when_unknown(self, backup_step, temp_dir):
        """Test default to SQLite when no database detected."""
        # Empty directory
        result = backup_step.detect_database_type(temp_dir)
        assert result == "sqlite"


# =============================================================================
# BACKUP CONFIGURATION TESTS
# =============================================================================


class TestBackupConfiguration:
    """Tests for backup configuration."""

    def test_get_backup_storage_path(self, backup_step, temp_dir):
        """Test getting backup storage path."""
        path = backup_step.get_backup_storage_path(temp_dir)

        assert path == temp_dir / ".fastband" / "backups"

    def test_format_frequency_options(self, backup_step):
        """Test frequency options format."""
        options = backup_step.format_frequency_options()

        assert len(options) == 3
        values = [opt["value"] for opt in options]
        assert "daily" in values
        assert "weekly" in values
        assert "on-change" in values

        # Check each option has required keys
        for opt in options:
            assert "value" in opt
            assert "label" in opt
            assert "description" in opt

    def test_format_retention_options(self, backup_step):
        """Test retention options format."""
        options = backup_step.format_retention_options()

        assert len(options) == 4
        values = [opt["value"] for opt in options]
        assert "3" in values
        assert "7" in values
        assert "14" in values
        assert "30" in values

        # Check each option has required keys
        for opt in options:
            assert "value" in opt
            assert "label" in opt
            assert "description" in opt

    @pytest.mark.asyncio
    async def test_test_backup_success(self, backup_step, wizard_context, temp_dir):
        """Test successful backup test."""
        result = await backup_step.test_backup(wizard_context, "sqlite")

        assert result is True
        # Verify backup directory was created
        backup_dir = temp_dir / ".fastband" / "backups"
        assert backup_dir.exists()

    @pytest.mark.asyncio
    async def test_test_backup_creates_directory(self, backup_step, wizard_context, temp_dir):
        """Test that backup test creates backup directory."""
        backup_dir = temp_dir / ".fastband" / "backups"
        assert not backup_dir.exists()

        await backup_step.test_backup(wizard_context, "sqlite")

        assert backup_dir.exists()


# =============================================================================
# NON-INTERACTIVE MODE TESTS
# =============================================================================


class TestNonInteractiveMode:
    """Tests for non-interactive mode."""

    @pytest.mark.asyncio
    async def test_non_interactive_uses_defaults(self, backup_step, non_interactive_context):
        """Test non-interactive mode uses sensible defaults."""
        result = await backup_step.execute(non_interactive_context)

        assert result.success is True
        assert result.data["frequency"] == "daily"
        assert result.data["retention_days"] == 7

    @pytest.mark.asyncio
    async def test_non_interactive_enables_backup(self, backup_step, non_interactive_context):
        """Test non-interactive mode enables backup."""
        await backup_step.execute(non_interactive_context)

        assert non_interactive_context.backup_enabled is True

    @pytest.mark.asyncio
    async def test_non_interactive_sets_config(self, backup_step, non_interactive_context):
        """Test non-interactive mode sets backup config."""
        await backup_step.execute(non_interactive_context)

        backup_config = non_interactive_context.config.backup
        assert backup_config.enabled is True
        assert backup_config.daily_enabled is True
        assert backup_config.daily_retention == 7
        assert backup_config.change_detection is True

    @pytest.mark.asyncio
    async def test_non_interactive_detects_database(
        self, backup_step, non_interactive_context, temp_dir
    ):
        """Test non-interactive mode detects database type."""
        # Create a sqlite file
        db_file = temp_dir / "data.db"
        db_file.touch()

        result = await backup_step.execute(non_interactive_context)

        assert result.data["db_type"] == "sqlite"
        assert non_interactive_context.get("detected_db_type") == "sqlite"

    @pytest.mark.asyncio
    async def test_non_interactive_sets_backup_path(
        self, backup_step, non_interactive_context, temp_dir
    ):
        """Test non-interactive mode sets backup path in context."""
        await backup_step.execute(non_interactive_context)

        backup_path = non_interactive_context.get("backup_path")
        assert backup_path is not None
        assert ".fastband/backups" in backup_path

    @pytest.mark.asyncio
    async def test_non_interactive_returns_success_message(
        self, backup_step, non_interactive_context
    ):
        """Test non-interactive mode returns success message."""
        result = await backup_step.execute(non_interactive_context)

        assert result.success is True
        assert result.message == "Backup configuration complete"


# =============================================================================
# VALIDATION TESTS
# =============================================================================


class TestValidation:
    """Tests for backup configuration validation."""

    @pytest.mark.asyncio
    async def test_validate_disabled_backup(self, backup_step, wizard_context):
        """Test validation passes when backup is disabled."""
        wizard_context.backup_enabled = False

        result = await backup_step.validate(wizard_context)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_enabled_backup_with_config(self, backup_step, non_interactive_context):
        """Test validation passes with valid backup config."""
        await backup_step.execute(non_interactive_context)

        result = await backup_step.validate(non_interactive_context)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_fails_with_invalid_retention(self, backup_step, wizard_context):
        """Test validation fails with invalid retention."""
        wizard_context.backup_enabled = True
        wizard_context.config.backup = BackupConfig(
            enabled=True,
            daily_retention=0,  # Invalid: must be positive
        )

        result = await backup_step.validate(wizard_context)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_fails_with_negative_retention(self, backup_step, wizard_context):
        """Test validation fails with negative retention."""
        wizard_context.backup_enabled = True
        wizard_context.config.backup = BackupConfig(
            enabled=True,
            daily_retention=-1,  # Invalid: must be positive
        )

        result = await backup_step.validate(wizard_context)

        assert result is False


# =============================================================================
# STEP RESULT TESTS
# =============================================================================


class TestStepResult:
    """Tests for step result data."""

    @pytest.mark.asyncio
    async def test_result_contains_db_type(self, backup_step, non_interactive_context):
        """Test result contains database type."""
        result = await backup_step.execute(non_interactive_context)

        assert "db_type" in result.data
        assert result.data["db_type"] in ["sqlite", "postgresql", "mysql", "unknown"]

    @pytest.mark.asyncio
    async def test_result_contains_backup_path(self, backup_step, non_interactive_context):
        """Test result contains backup path."""
        result = await backup_step.execute(non_interactive_context)

        assert "backup_path" in result.data
        assert isinstance(result.data["backup_path"], str)

    @pytest.mark.asyncio
    async def test_result_contains_frequency(self, backup_step, non_interactive_context):
        """Test result contains frequency."""
        result = await backup_step.execute(non_interactive_context)

        assert "frequency" in result.data
        assert result.data["frequency"] in ["daily", "weekly", "on-change"]

    @pytest.mark.asyncio
    async def test_result_contains_retention_days(self, backup_step, non_interactive_context):
        """Test result contains retention days."""
        result = await backup_step.execute(non_interactive_context)

        assert "retention_days" in result.data
        assert isinstance(result.data["retention_days"], int)
        assert result.data["retention_days"] > 0


# =============================================================================
# CONTEXT UPDATE TESTS
# =============================================================================


class TestContextUpdates:
    """Tests for wizard context updates."""

    @pytest.mark.asyncio
    async def test_context_backup_enabled_set(self, backup_step, non_interactive_context):
        """Test context.backup_enabled is set."""
        assert non_interactive_context.backup_enabled is True  # Default value

        await backup_step.execute(non_interactive_context)

        assert non_interactive_context.backup_enabled is True

    @pytest.mark.asyncio
    async def test_context_config_backup_set(self, backup_step, non_interactive_context):
        """Test context.config.backup is set."""
        await backup_step.execute(non_interactive_context)

        backup_config = non_interactive_context.config.backup
        assert isinstance(backup_config, BackupConfig)
        assert backup_config.enabled is True

    @pytest.mark.asyncio
    async def test_context_metadata_set(self, backup_step, non_interactive_context):
        """Test context metadata is set."""
        await backup_step.execute(non_interactive_context)

        assert non_interactive_context.get("detected_db_type") is not None
        assert non_interactive_context.get("backup_path") is not None


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_empty_project_directory(self, backup_step, non_interactive_context, temp_dir):
        """Test with empty project directory."""
        result = await backup_step.execute(non_interactive_context)

        assert result.success is True
        # Should default to sqlite
        assert result.data["db_type"] == "sqlite"

    @pytest.mark.asyncio
    async def test_should_skip_returns_false(self, backup_step, wizard_context):
        """Test should_skip returns False by default."""
        result = backup_step.should_skip(wizard_context)

        assert result is False

    def test_database_patterns_defined(self, backup_step):
        """Test database patterns are defined."""
        assert "sqlite" in backup_step.DATABASE_PATTERNS
        assert "postgresql" in backup_step.DATABASE_PATTERNS
        assert "mysql" in backup_step.DATABASE_PATTERNS

    def test_config_file_patterns_defined(self, backup_step):
        """Test config file patterns are defined."""
        assert "sqlite" in backup_step.CONFIG_FILE_PATTERNS
        assert "postgresql" in backup_step.CONFIG_FILE_PATTERNS
        assert "mysql" in backup_step.CONFIG_FILE_PATTERNS
