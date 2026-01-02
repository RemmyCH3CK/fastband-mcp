"""
Database Models - Data structures for database operations.

Defines standardized representations for:
- Database connections and metadata
- Schema objects (tables, columns, indexes)
- Query results and execution plans
- Migration tracking
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DatabaseType(str, Enum):
    """Supported database types."""

    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MARIADB = "mariadb"
    UNKNOWN = "unknown"

    @classmethod
    def from_url(cls, url: str) -> "DatabaseType":
        """Detect database type from connection URL."""
        url_lower = url.lower()
        if url_lower.startswith("sqlite") or url_lower.endswith(".db") or url_lower.endswith(".sqlite"):
            return cls.SQLITE
        elif "postgresql" in url_lower or "postgres" in url_lower:
            return cls.POSTGRESQL
        elif "mysql" in url_lower:
            return cls.MYSQL
        elif "mariadb" in url_lower:
            return cls.MARIADB
        return cls.UNKNOWN


class ColumnType(str, Enum):
    """Normalized column types."""

    INTEGER = "integer"
    BIGINT = "bigint"
    SMALLINT = "smallint"
    DECIMAL = "decimal"
    FLOAT = "float"
    DOUBLE = "double"
    BOOLEAN = "boolean"
    VARCHAR = "varchar"
    TEXT = "text"
    CHAR = "char"
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    TIMESTAMP = "timestamp"
    BLOB = "blob"
    JSON = "json"
    UUID = "uuid"
    ARRAY = "array"
    UNKNOWN = "unknown"


class IndexType(str, Enum):
    """Types of database indexes."""

    PRIMARY = "primary"
    UNIQUE = "unique"
    INDEX = "index"
    FULLTEXT = "fulltext"
    SPATIAL = "spatial"


class ConstraintType(str, Enum):
    """Types of database constraints."""

    PRIMARY_KEY = "primary_key"
    FOREIGN_KEY = "foreign_key"
    UNIQUE = "unique"
    CHECK = "check"
    NOT_NULL = "not_null"
    DEFAULT = "default"


@dataclass
class Column:
    """A database column."""

    name: str
    data_type: str  # Raw type from database
    normalized_type: ColumnType = ColumnType.UNKNOWN

    # Constraints
    is_nullable: bool = True
    is_primary_key: bool = False
    is_unique: bool = False
    is_auto_increment: bool = False

    # Default value
    default_value: str | None = None

    # Foreign key
    references_table: str | None = None
    references_column: str | None = None

    # Metadata
    max_length: int | None = None
    precision: int | None = None
    scale: int | None = None
    comment: str = ""

    # Statistics (if available)
    distinct_count: int | None = None
    null_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "name": self.name,
            "type": self.data_type,
            "nullable": self.is_nullable,
        }
        if self.is_primary_key:
            result["primary_key"] = True
        if self.is_unique:
            result["unique"] = True
        if self.is_auto_increment:
            result["auto_increment"] = True
        if self.default_value:
            result["default"] = self.default_value
        if self.references_table:
            result["references"] = f"{self.references_table}.{self.references_column}"
        return result


@dataclass
class Index:
    """A database index."""

    name: str
    columns: list[str]
    index_type: IndexType = IndexType.INDEX
    is_unique: bool = False

    # For partial indexes
    condition: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "columns": self.columns,
            "type": self.index_type.value,
            "unique": self.is_unique,
        }


@dataclass
class ForeignKey:
    """A foreign key constraint."""

    name: str
    columns: list[str]
    references_table: str
    references_columns: list[str]

    # Actions
    on_delete: str = "NO ACTION"
    on_update: str = "NO ACTION"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "columns": self.columns,
            "references": f"{self.references_table}({', '.join(self.references_columns)})",
            "on_delete": self.on_delete,
            "on_update": self.on_update,
        }


@dataclass
class Table:
    """A database table."""

    name: str
    schema: str = ""  # Schema/database name

    columns: list[Column] = field(default_factory=list)
    indexes: list[Index] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)

    # Statistics
    row_count: int | None = None
    size_bytes: int | None = None

    # Metadata
    comment: str = ""
    created_at: datetime | None = None

    @property
    def primary_key_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.is_primary_key]

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def get_column(self, name: str) -> Column | None:
        for col in self.columns:
            if col.name.lower() == name.lower():
                return col
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "schema": self.schema or None,
            "columns": [c.to_dict() for c in self.columns],
            "primary_key": self.primary_key_columns,
            "indexes": [i.to_dict() for i in self.indexes],
            "foreign_keys": [fk.to_dict() for fk in self.foreign_keys],
            "row_count": self.row_count,
        }

    def to_ddl(self, db_type: DatabaseType = DatabaseType.SQLITE) -> str:
        """Generate CREATE TABLE statement."""
        lines = [f"CREATE TABLE {self.name} ("]

        col_defs = []
        for col in self.columns:
            col_def = f"  {col.name} {col.data_type}"
            if not col.is_nullable:
                col_def += " NOT NULL"
            if col.is_primary_key and len(self.primary_key_columns) == 1:
                col_def += " PRIMARY KEY"
            if col.is_auto_increment:
                if db_type == DatabaseType.SQLITE:
                    col_def = col_def.replace("PRIMARY KEY", "PRIMARY KEY AUTOINCREMENT")
                elif db_type == DatabaseType.POSTGRESQL:
                    col_def = col_def.replace(col.data_type, "SERIAL")
                else:
                    col_def += " AUTO_INCREMENT"
            if col.default_value:
                col_def += f" DEFAULT {col.default_value}"
            col_defs.append(col_def)

        # Multi-column primary key
        if len(self.primary_key_columns) > 1:
            col_defs.append(f"  PRIMARY KEY ({', '.join(self.primary_key_columns)})")

        # Foreign keys
        for fk in self.foreign_keys:
            fk_def = f"  FOREIGN KEY ({', '.join(fk.columns)}) REFERENCES {fk.references_table}({', '.join(fk.references_columns)})"
            if fk.on_delete != "NO ACTION":
                fk_def += f" ON DELETE {fk.on_delete}"
            if fk.on_update != "NO ACTION":
                fk_def += f" ON UPDATE {fk.on_update}"
            col_defs.append(fk_def)

        lines.append(",\n".join(col_defs))
        lines.append(");")

        return "\n".join(lines)


@dataclass
class QueryResult:
    """Result of a database query."""

    # Query info
    query: str
    query_type: str = ""  # SELECT, INSERT, UPDATE, DELETE, etc.

    # Results
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0

    # For non-SELECT queries
    affected_rows: int = 0
    last_insert_id: int | None = None

    # Timing
    execution_time_ms: float = 0

    # Errors
    error: str | None = None
    error_code: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "success": self.success,
            "query_type": self.query_type,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }

        if self.error:
            result["error"] = self.error
        elif self.query_type.upper() == "SELECT":
            result["columns"] = self.columns
            result["row_count"] = self.row_count
            result["rows"] = self.rows[:100]  # Limit for output
            if self.row_count > 100:
                result["truncated"] = True
        else:
            result["affected_rows"] = self.affected_rows
            if self.last_insert_id:
                result["last_insert_id"] = self.last_insert_id

        return result

    def to_markdown_table(self, max_rows: int = 20) -> str:
        """Format results as markdown table."""
        if not self.columns or not self.rows:
            return f"*No results* ({self.row_count} rows)"

        lines = []

        # Header
        lines.append("| " + " | ".join(self.columns) + " |")
        lines.append("| " + " | ".join(["---"] * len(self.columns)) + " |")

        # Rows
        for row in self.rows[:max_rows]:
            formatted = []
            for val in row:
                if val is None:
                    formatted.append("NULL")
                elif isinstance(val, str) and len(val) > 50:
                    formatted.append(val[:47] + "...")
                else:
                    formatted.append(str(val))
            lines.append("| " + " | ".join(formatted) + " |")

        if self.row_count > max_rows:
            lines.append(f"\n*... and {self.row_count - max_rows} more rows*")

        return "\n".join(lines)


@dataclass
class QueryPlan:
    """Execution plan for a query."""

    query: str
    plan_text: str = ""
    plan_json: dict[str, Any] | None = None

    # Extracted metrics
    estimated_cost: float | None = None
    estimated_rows: int | None = None

    # Analysis
    uses_index: bool = False
    index_names: list[str] = field(default_factory=list)
    has_full_scan: bool = False
    has_sort: bool = False
    has_temp_table: bool = False

    # Recommendations
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan_text,
            "estimated_cost": self.estimated_cost,
            "estimated_rows": self.estimated_rows,
            "uses_index": self.uses_index,
            "indexes_used": self.index_names,
            "warnings": {
                "full_scan": self.has_full_scan,
                "sort": self.has_sort,
                "temp_table": self.has_temp_table,
            },
            "suggestions": self.suggestions,
        }


@dataclass
class Migration:
    """A database migration."""

    id: str
    name: str
    version: str = ""

    # SQL content
    up_sql: str = ""
    down_sql: str = ""

    # Status
    applied: bool = False
    applied_at: datetime | None = None

    # Metadata
    checksum: str = ""
    execution_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "applied": self.applied,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
        }


@dataclass
class DatabaseInfo:
    """Information about a database connection."""

    # Connection
    db_type: DatabaseType
    database_name: str
    host: str = ""
    port: int = 0
    user: str = ""

    # Version
    version: str = ""
    version_number: tuple[int, ...] = ()

    # Statistics
    table_count: int = 0
    total_size_bytes: int = 0

    # Tables
    tables: list[Table] = field(default_factory=list)

    # Status
    connected: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.db_type.value,
            "database": self.database_name,
            "host": self.host or "local",
            "version": self.version,
            "connected": self.connected,
            "table_count": self.table_count,
            "size_mb": round(self.total_size_bytes / (1024 * 1024), 2) if self.total_size_bytes else None,
            "tables": [t.name for t in self.tables],
        }


@dataclass
class SchemaReport:
    """Complete schema analysis report."""

    report_id: str
    created_at: datetime = field(default_factory=_utc_now)

    # Database info
    database_info: DatabaseInfo | None = None

    # Tables with full details
    tables: list[Table] = field(default_factory=list)

    # Analysis
    total_columns: int = 0
    total_indexes: int = 0
    total_foreign_keys: int = 0

    # Issues found
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_summary(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "database": self.database_info.to_dict() if self.database_info else None,
            "table_count": len(self.tables),
            "total_columns": self.total_columns,
            "total_indexes": self.total_indexes,
            "total_foreign_keys": self.total_foreign_keys,
            "issues": self.issues[:5],
            "recommendations": self.recommendations[:5],
        }

    def to_markdown(self) -> str:
        """Generate markdown schema documentation."""
        lines = ["# Database Schema Report", ""]

        if self.database_info:
            db = self.database_info
            lines.extend([
                f"**Database**: {db.database_name}",
                f"**Type**: {db.db_type.value}",
                f"**Version**: {db.version}",
                f"**Tables**: {db.table_count}",
                "",
            ])

        lines.append("## Tables")
        lines.append("")

        for table in self.tables:
            lines.append(f"### {table.name}")
            if table.row_count is not None:
                lines.append(f"*{table.row_count:,} rows*")
            lines.append("")

            # Columns
            lines.append("| Column | Type | Nullable | Key |")
            lines.append("|--------|------|----------|-----|")
            for col in table.columns:
                key = "PK" if col.is_primary_key else ("FK" if col.references_table else "")
                nullable = "YES" if col.is_nullable else "NO"
                lines.append(f"| {col.name} | {col.data_type} | {nullable} | {key} |")
            lines.append("")

            # Indexes
            if table.indexes:
                lines.append("**Indexes:**")
                for idx in table.indexes:
                    lines.append(f"- `{idx.name}` on ({', '.join(idx.columns)})")
                lines.append("")

        if self.issues:
            lines.extend(["## Issues", ""])
            for issue in self.issues:
                lines.append(f"- {issue}")
            lines.append("")

        if self.recommendations:
            lines.extend(["## Recommendations", ""])
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)
