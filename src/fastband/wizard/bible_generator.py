"""
Agent Bible Generator for Fastband MCP.

Generates project-specific AGENT_BIBLE.md from template during setup wizard.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError:
    # Fallback for basic string replacement if jinja2 not available
    Environment = None


@dataclass
class DatabaseRule:
    """Project-specific database rule configuration."""

    title: str = "Follow Database Conventions"
    description: str = "Use the established database patterns for this project."
    forbidden: list[str] = field(default_factory=list)
    always: list[str] = field(default_factory=list)

    @classmethod
    def postgresql(cls) -> "DatabaseRule":
        """Create PostgreSQL-specific rule."""
        return cls(
            title="Database is PostgreSQL Only",
            description=(
                "`DATABASE_URL` must point to PostgreSQL. "
                "ALL database access goes through PostgreSQL via SQLAlchemy."
            ),
            forbidden=[
                "`sqlite3` imports",
                "`.db` file references",
                "`PRAGMA` statements",
                "`sqlite_master` queries",
                "Any SQLite-specific SQL",
            ],
            always=[
                "Use PostgreSQL via SQLAlchemy or database helpers",
                "Test with PostgreSQL connection",
            ],
        )

    @classmethod
    def sqlite(cls) -> "DatabaseRule":
        """Create SQLite-specific rule."""
        return cls(
            title="Database is SQLite",
            description="This project uses SQLite for data storage.",
            forbidden=[
                "PostgreSQL-specific syntax",
                "Connection pooling (not needed for SQLite)",
            ],
            always=[
                "Use SQLite-compatible SQL",
                "Handle concurrent writes carefully",
                "Use WAL mode for better performance",
            ],
        )

    @classmethod
    def mysql(cls) -> "DatabaseRule":
        """Create MySQL-specific rule."""
        return cls(
            title="Database is MySQL",
            description="This project uses MySQL for data storage.",
            forbidden=[
                "SQLite-specific syntax",
                "PostgreSQL-specific syntax",
            ],
            always=[
                "Use MySQL-compatible SQL",
                "Test with MySQL connection",
            ],
        )


@dataclass
class ProjectConfig:
    """Project configuration for Agent Bible generation."""

    # Required fields
    name: str
    type: str  # webapp, api, cli, library, etc.
    language: str  # python, javascript, typescript, etc.
    root_path: str
    ticket_prefix: str = "FB"

    # Paths
    templates_path: str = "templates"
    static_path: str = "static"
    screenshots_path: str = "data/test_screenshots"
    data_path: str = "data"
    fastband_path: str = ".fastband"

    # Server/URL configuration (optional)
    server_ip: str | None = None
    ssh_connection: str | None = None
    dev_url: str | None = None
    prod_url: str | None = None
    ops_log_url: str | None = None

    # Container configuration (optional)
    container_name: str | None = None
    service_name: str | None = None
    container_app_path: str | None = None

    # Database configuration (optional)
    database_type: str | None = None
    database_connection: str | None = None
    database_rule: DatabaseRule | None = None

    # Git configuration
    repo_name: str = "project"
    git_default_branch: str = "main"

    # Review configuration
    review_agent_count: int = 3  # 1-3 review agents

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectConfig":
        """Create ProjectConfig from dictionary."""
        # Handle nested database_rule
        db_rule_data = data.pop("database_rule", None)
        if db_rule_data and isinstance(db_rule_data, dict):
            data["database_rule"] = DatabaseRule(**db_rule_data)
        elif db_rule_data and isinstance(db_rule_data, str):
            # Handle preset rules
            if db_rule_data == "postgresql":
                data["database_rule"] = DatabaseRule.postgresql()
            elif db_rule_data == "sqlite":
                data["database_rule"] = DatabaseRule.sqlite()
            elif db_rule_data == "mysql":
                data["database_rule"] = DatabaseRule.mysql()

        return cls(**data)

    def to_template_context(self) -> dict[str, Any]:
        """Convert to template context dictionary."""
        return {
            "project": self,
            "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


class AgentBibleGenerator:
    """Generates project-specific Agent Bible from template."""

    def __init__(self, template_dir: Path | None = None):
        """
        Initialize generator.

        Args:
            template_dir: Directory containing templates.
                          Defaults to wizard/templates in package.
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.template_dir = template_dir
        self.template_name = "AGENT_BIBLE.md.j2"

        if Environment is not None:
            self.env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
        else:
            self.env = None

    def generate(self, config: ProjectConfig) -> str:
        """
        Generate Agent Bible markdown from project config.

        Args:
            config: Project configuration

        Returns:
            Generated markdown content
        """
        if self.env is None:
            return self._generate_fallback(config)

        template = self.env.get_template(self.template_name)
        context = config.to_template_context()
        return template.render(**context)

    def _generate_fallback(self, config: ProjectConfig) -> str:
        """Fallback generation using basic string replacement."""
        template_path = self.template_dir / self.template_name

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        content = template_path.read_text()

        # Basic variable substitution
        replacements = {
            "{{ project.name }}": config.name,
            "{{ project.type }}": config.type,
            "{{ project.language }}": config.language,
            "{{ project.root_path }}": config.root_path,
            "{{ project.ticket_prefix }}": config.ticket_prefix,
            "{{ project.templates_path }}": config.templates_path,
            "{{ project.static_path }}": config.static_path,
            "{{ project.screenshots_path }}": config.screenshots_path,
            "{{ project.data_path }}": config.data_path,
            "{{ project.fastband_path }}": config.fastband_path,
            "{{ project.dev_url }}": config.dev_url or "http://localhost:5000",
            "{{ project.prod_url }}": config.prod_url or "",
            "{{ project.repo_name }}": config.repo_name,
            "{{ project.git_default_branch }}": config.git_default_branch,
            "{{ project.review_agent_count }}": str(config.review_agent_count),
            "{{ generation_date }}": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        for old, new in replacements.items():
            content = content.replace(old, new)

        return content

    def save(self, config: ProjectConfig, output_path: Path) -> Path:
        """
        Generate and save Agent Bible to file.

        Args:
            config: Project configuration
            output_path: Where to save the file

        Returns:
            Path to saved file
        """
        content = self.generate(config)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)

        return output_path


def generate_agent_bible(
    project_name: str,
    project_type: str,
    project_language: str,
    project_path: Path,
    **kwargs,
) -> str:
    """
    Convenience function to generate Agent Bible.

    Args:
        project_name: Name of the project
        project_type: Type (webapp, api, cli, library)
        project_language: Primary language (python, javascript, etc.)
        project_path: Root path of the project
        **kwargs: Additional ProjectConfig options

    Returns:
        Generated markdown content
    """
    config = ProjectConfig(
        name=project_name,
        type=project_type,
        language=project_language,
        root_path=str(project_path),
        **kwargs,
    )

    generator = AgentBibleGenerator()
    return generator.generate(config)


def create_agent_bible_for_project(project_path: Path, **kwargs) -> Path:
    """
    Create Agent Bible in project's .fastband directory.

    Args:
        project_path: Root path of the project
        **kwargs: ProjectConfig options

    Returns:
        Path to created Agent Bible
    """
    output_path = project_path / ".fastband" / "AGENT_BIBLE.md"

    config = ProjectConfig(
        root_path=str(project_path),
        **kwargs,
    )

    generator = AgentBibleGenerator()
    return generator.save(config, output_path)


# Example configurations for common project types
EXAMPLE_CONFIGS = {
    "flask_webapp": ProjectConfig(
        name="My Flask App",
        type="webapp",
        language="python",
        root_path="/path/to/project",
        ticket_prefix="APP",
        dev_url="http://localhost:5000",
        container_name="my-flask-app",
        service_name="webapp",
        container_app_path="/app",
        database_type="PostgreSQL",
        database_rule=DatabaseRule.postgresql(),
        review_agent_count=3,
    ),
    "fastapi": ProjectConfig(
        name="My FastAPI Service",
        type="api",
        language="python",
        root_path="/path/to/project",
        ticket_prefix="API",
        dev_url="http://localhost:8000",
        database_type="PostgreSQL",
        database_rule=DatabaseRule.postgresql(),
        review_agent_count=2,
    ),
    "nextjs": ProjectConfig(
        name="My Next.js App",
        type="webapp",
        language="typescript",
        root_path="/path/to/project",
        ticket_prefix="WEB",
        templates_path="pages",
        static_path="public",
        dev_url="http://localhost:3000",
        review_agent_count=3,
    ),
    "python_library": ProjectConfig(
        name="My Python Library",
        type="library",
        language="python",
        root_path="/path/to/project",
        ticket_prefix="LIB",
        templates_path="src",
        static_path="docs",
        review_agent_count=1,
    ),
    "cli_tool": ProjectConfig(
        name="My CLI Tool",
        type="cli",
        language="python",
        root_path="/path/to/project",
        ticket_prefix="CLI",
        templates_path="src",
        review_agent_count=1,
    ),
}
