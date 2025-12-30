"""
Backup Configuration wizard step.

Configures backup settings for the Fastband MCP server including:
- Database type detection (SQLite, PostgreSQL, MySQL)
- Backup frequency (daily, weekly, on-change)
- Retention policies
- Storage location configuration
- Test backup functionality
"""

from pathlib import Path

from fastband.core.config import BackupConfig
from fastband.wizard.base import StepResult, WizardContext, WizardStep


class BackupConfigurationStep(WizardStep):
    """
    Wizard step for configuring backup settings.

    This step:
    1. Auto-detects the database type being used
    2. Configures backup frequency
    3. Sets retention policies
    4. Shows backup storage location
    5. Offers to test backup operation
    """

    # Database detection patterns
    DATABASE_PATTERNS = {
        "sqlite": [
            "*.db",
            "*.sqlite",
            "*.sqlite3",
            "data.db",
            ".fastband/data.db",
        ],
        "postgresql": [
            "pg_hba.conf",
            ".pgpass",
        ],
        "mysql": [
            "my.cnf",
            ".my.cnf",
        ],
    }

    # Common database connection file patterns
    CONFIG_FILE_PATTERNS = {
        "sqlite": ["DATABASE_URL=sqlite", "storage_backend.*sqlite"],
        "postgresql": ["DATABASE_URL=postgres", "storage_backend.*postgres"],
        "mysql": ["DATABASE_URL=mysql", "storage_backend.*mysql"],
    }

    @property
    def name(self) -> str:
        """Short name for the step."""
        return "backup"

    @property
    def title(self) -> str:
        """Display title for the step."""
        return "Backup Configuration"

    @property
    def description(self) -> str:
        """Description shown before step execution."""
        return "Configure automated backups for your project data"

    @property
    def required(self) -> bool:
        """Whether this step is required (cannot be skipped)."""
        return False

    def detect_database_type(self, project_path: Path) -> str:
        """
        Auto-detect the database type by checking common files.

        Args:
            project_path: Path to the project directory

        Returns:
            Detected database type: 'sqlite', 'postgresql', 'mysql', or 'unknown'
        """
        # Check for SQLite files first (most common)
        for pattern in self.DATABASE_PATTERNS["sqlite"]:
            if pattern.startswith("*."):
                # Glob pattern
                if list(project_path.rglob(pattern)):
                    return "sqlite"
            else:
                # Exact path
                if (project_path / pattern).exists():
                    return "sqlite"

        # Check for PostgreSQL indicators
        for pattern in self.DATABASE_PATTERNS["postgresql"]:
            if (project_path / pattern).exists():
                return "postgresql"

        # Check for MySQL indicators
        for pattern in self.DATABASE_PATTERNS["mysql"]:
            if (project_path / pattern).exists():
                return "mysql"

        # Check config files for database URL patterns
        config_files = [
            project_path / ".env",
            project_path / ".fastband" / "config.yaml",
            project_path / "config.yaml",
        ]

        for config_file in config_files:
            if config_file.exists():
                try:
                    content = config_file.read_text().lower()
                    for db_type, patterns in self.CONFIG_FILE_PATTERNS.items():
                        for pattern in patterns:
                            if pattern.lower() in content:
                                return db_type
                except Exception:
                    continue

        # Default to sqlite if nothing detected
        return "sqlite"

    def get_backup_storage_path(self, project_path: Path) -> Path:
        """
        Get the default backup storage path.

        Args:
            project_path: Path to the project directory

        Returns:
            Path to backup storage directory
        """
        return project_path / ".fastband" / "backups"

    def format_frequency_options(self) -> list[dict[str, str]]:
        """Get formatted frequency options for selection."""
        return [
            {
                "value": "daily",
                "label": "Daily",
                "description": "Backup every day at a specified time",
            },
            {
                "value": "weekly",
                "label": "Weekly",
                "description": "Backup once a week on a specified day",
            },
            {
                "value": "on-change",
                "label": "On Change",
                "description": "Backup whenever data changes are detected",
            },
        ]

    def format_retention_options(self) -> list[dict[str, str]]:
        """Get formatted retention options for selection."""
        return [
            {
                "value": "3",
                "label": "3 days",
                "description": "Keep backups for 3 days",
            },
            {
                "value": "7",
                "label": "7 days (recommended)",
                "description": "Keep backups for 1 week",
            },
            {
                "value": "14",
                "label": "14 days",
                "description": "Keep backups for 2 weeks",
            },
            {
                "value": "30",
                "label": "30 days",
                "description": "Keep backups for 1 month",
            },
        ]

    async def test_backup(self, context: WizardContext, db_type: str) -> bool:
        """
        Test the backup operation.

        Args:
            context: Wizard context
            db_type: Detected database type

        Returns:
            True if backup test succeeded, False otherwise
        """
        backup_path = self.get_backup_storage_path(context.project_path)

        try:
            # Ensure backup directory exists
            backup_path.mkdir(parents=True, exist_ok=True)

            # Create a test file to verify write access
            test_file = backup_path / ".backup_test"
            test_file.write_text("backup test")
            test_file.unlink()

            return True
        except Exception as e:
            self.show_error(f"Backup test failed: {e}")
            return False

    async def execute(self, context: WizardContext) -> StepResult:
        """
        Execute the backup configuration step.

        Args:
            context: Shared wizard context

        Returns:
            StepResult indicating success/failure and configuration data
        """
        # Detect database type
        db_type = self.detect_database_type(context.project_path)
        self.show_info(f"Detected database type: {db_type}")

        # Get backup storage path
        backup_path = self.get_backup_storage_path(context.project_path)
        self.show_info(f"Backup storage location: {backup_path}")

        if not context.interactive:
            # Non-interactive mode: use sensible defaults
            backup_config = BackupConfig(
                enabled=True,
                daily_enabled=True,
                daily_time="02:00",
                daily_retention=7,
                weekly_enabled=False,
                weekly_day="sunday",
                weekly_retention=4,
                change_detection=True,
            )

            # Update context
            context.backup_enabled = True
            context.config.backup = backup_config
            context.set("detected_db_type", db_type)
            context.set("backup_path", str(backup_path))

            self.show_success("Backup configured with defaults (daily, 7-day retention)")

            return StepResult(
                success=True,
                data={
                    "db_type": db_type,
                    "backup_path": str(backup_path),
                    "frequency": "daily",
                    "retention_days": 7,
                },
                message="Backup configuration complete",
            )

        # Interactive mode
        self.console.print()

        # Ask if user wants to enable backups
        enable_backup = self.confirm("Enable automated backups?", default=True)

        if not enable_backup:
            context.backup_enabled = False
            context.config.backup.enabled = False
            self.show_warning("Backups disabled. You can enable them later in config.")

            return StepResult(
                success=True,
                data={"enabled": False},
                message="Backups disabled",
            )

        # Select backup frequency
        self.console.print()
        frequency_options = self.format_frequency_options()
        selected_frequency = self.select_from_list(
            "Select backup frequency",
            frequency_options,
            allow_multiple=False,
        )
        frequency = selected_frequency[0] if selected_frequency else "daily"

        # Select retention period
        self.console.print()
        retention_options = self.format_retention_options()
        selected_retention = self.select_from_list(
            "Select retention period",
            retention_options,
            allow_multiple=False,
        )
        retention_days = int(selected_retention[0]) if selected_retention else 7

        # Configure based on frequency
        backup_config = BackupConfig(
            enabled=True,
            daily_enabled=(frequency == "daily"),
            daily_time="02:00",
            daily_retention=retention_days,
            weekly_enabled=(frequency == "weekly"),
            weekly_day="sunday",
            weekly_retention=retention_days // 7 if retention_days >= 7 else 1,
            change_detection=(frequency == "on-change"),
        )

        # Ask about change detection (as additional option for daily/weekly)
        if frequency != "on-change":
            self.console.print()
            enable_change_detection = self.confirm(
                "Also backup on data changes?",
                default=True,
            )
            backup_config.change_detection = enable_change_detection

        # Show backup storage location
        self.console.print()
        self.show_info(f"Backups will be stored in: {backup_path}")

        # Offer to test backup
        self.console.print()
        if self.confirm("Test backup operation?", default=True):
            self.console.print()
            self.show_info("Testing backup...")
            if await self.test_backup(context, db_type):
                self.show_success("Backup test passed!")
            else:
                self.show_warning("Backup test had issues, but configuration saved.")

        # Update context
        context.backup_enabled = True
        context.config.backup = backup_config
        context.set("detected_db_type", db_type)
        context.set("backup_path", str(backup_path))

        self.console.print()
        self.show_success(f"Backup configured: {frequency}, {retention_days}-day retention")

        return StepResult(
            success=True,
            data={
                "db_type": db_type,
                "backup_path": str(backup_path),
                "frequency": frequency,
                "retention_days": retention_days,
                "change_detection": backup_config.change_detection,
            },
            message="Backup configuration complete",
        )

    async def validate(self, context: WizardContext) -> bool:
        """
        Validate backup configuration.

        Args:
            context: Wizard context

        Returns:
            True if configuration is valid
        """
        # If backups are disabled, that's valid
        if not context.backup_enabled:
            return True

        # Verify backup config exists
        if context.config.backup is None:
            return False

        # Verify retention is positive
        if context.config.backup.daily_retention <= 0:
            return False

        return True
