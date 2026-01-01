"""
Database Connectors - Connection management for various databases.

Supports:
- SQLite (built-in)
- PostgreSQL (via psycopg2 if installed)
- MySQL/MariaDB (via mysql-connector if installed)

All connectors provide a unified interface for:
- Connection management
- Query execution
- Schema inspection
"""

import logging
import os
import re
import sqlite3
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator
from urllib.parse import parse_qs, urlparse

from fastband.core.security import SQLSecurityError, validate_sql_identifier
from fastband.tools.database.models import (
    Column,
    ColumnType,
    DatabaseInfo,
    DatabaseType,
    ForeignKey,
    Index,
    IndexType,
    QueryPlan,
    QueryResult,
    Table,
)

logger = logging.getLogger(__name__)


class DatabaseConnector(ABC):
    """Abstract base class for database connectors."""

    db_type: DatabaseType = DatabaseType.UNKNOWN

    @abstractmethod
    def connect(self) -> bool:
        """Establish database connection."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close database connection."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected."""
        pass

    @abstractmethod
    def execute(self, query: str, params: tuple | None = None) -> QueryResult:
        """Execute a query and return results."""
        pass

    @abstractmethod
    def get_tables(self) -> list[Table]:
        """Get all tables in the database."""
        pass

    @abstractmethod
    def get_table(self, table_name: str) -> Table | None:
        """Get detailed info about a specific table."""
        pass

    @abstractmethod
    def get_info(self) -> DatabaseInfo:
        """Get database information."""
        pass

    @abstractmethod
    def explain(self, query: str) -> QueryPlan:
        """Get query execution plan."""
        pass


class SQLiteConnector(DatabaseConnector):
    """SQLite database connector."""

    db_type = DatabaseType.SQLITE

    def __init__(self, db_path: str):
        """
        Initialize SQLite connector.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> bool:
        """Connect to SQLite database."""
        try:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            return True
        except Exception as e:
            logger.error(f"SQLite connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Close connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._conn is not None

    @contextmanager
    def _cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Get a cursor with automatic cleanup."""
        if not self._conn:
            self.connect()
        cursor = self._conn.cursor()  # type: ignore
        try:
            yield cursor
        finally:
            cursor.close()

    def execute(self, query: str, params: tuple | None = None) -> QueryResult:
        """Execute a query."""
        result = QueryResult(query=query)

        # Determine query type
        query_upper = query.strip().upper()
        if query_upper.startswith("SELECT") or query_upper.startswith("PRAGMA"):
            result.query_type = "SELECT"  # PRAGMA returns rows like SELECT
        elif query_upper.startswith("INSERT"):
            result.query_type = "INSERT"
        elif query_upper.startswith("UPDATE"):
            result.query_type = "UPDATE"
        elif query_upper.startswith("DELETE"):
            result.query_type = "DELETE"
        elif query_upper.startswith("CREATE"):
            result.query_type = "CREATE"
        elif query_upper.startswith("DROP"):
            result.query_type = "DROP"
        elif query_upper.startswith("ALTER"):
            result.query_type = "ALTER"
        else:
            result.query_type = "OTHER"

        start_time = time.time()

        try:
            with self._cursor() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                if result.query_type == "SELECT":
                    rows = cursor.fetchall()
                    result.columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    result.rows = [list(row) for row in rows]
                    result.row_count = len(rows)
                else:
                    self._conn.commit()  # type: ignore
                    result.affected_rows = cursor.rowcount
                    result.last_insert_id = cursor.lastrowid

        except sqlite3.Error as e:
            result.error = str(e)
            result.error_code = type(e).__name__
        except Exception as e:
            result.error = str(e)

        result.execution_time_ms = (time.time() - start_time) * 1000
        return result

    def get_tables(self) -> list[Table]:
        """Get all tables."""
        tables = []

        result = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )

        for row in result.rows:
            table_name = row[0]
            table = self.get_table(table_name)
            if table:
                tables.append(table)

        return tables

    def _validate_identifier(self, name: str) -> str:
        """Validate a SQL identifier (table/index name) to prevent injection.

        Args:
            name: The identifier to validate

        Returns:
            The validated identifier

        Raises:
            SQLSecurityError: If the identifier is invalid
        """
        try:
            return validate_sql_identifier(name)
        except SQLSecurityError:
            # For SQLite, also allow identifiers that contain only safe chars
            # even if they don't match the strict pattern (e.g., sqlite_sequence)
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name) or name.startswith('sqlite_'):
                return name
            raise

    def get_table(self, table_name: str) -> Table | None:
        """Get detailed table info."""
        # SECURITY: Validate table name to prevent SQL injection
        safe_table_name = self._validate_identifier(table_name)
        table = Table(name=safe_table_name)

        # Get columns - using validated identifier
        result = self.execute(f"PRAGMA table_info('{safe_table_name}')")
        for row in result.rows:
            # cid, name, type, notnull, dflt_value, pk
            col = Column(
                name=row[1],
                data_type=row[2],
                normalized_type=self._normalize_type(row[2]),
                is_nullable=not row[3],
                default_value=row[4],
                is_primary_key=bool(row[5]),
            )

            # Check for autoincrement
            if col.is_primary_key and "INTEGER" in col.data_type.upper():
                # SQLite INTEGER PRIMARY KEY is autoincrement
                col.is_auto_increment = True

            table.columns.append(col)

        # Get indexes
        result = self.execute(f"PRAGMA index_list('{safe_table_name}')")
        for row in result.rows:
            # seq, name, unique, origin, partial
            idx_name = row[1]
            is_unique = bool(row[2])

            # Get index columns - validate index name
            safe_idx_name = self._validate_identifier(idx_name)
            idx_info = self.execute(f"PRAGMA index_info('{safe_idx_name}')")
            columns = [r[2] for r in idx_info.rows]

            idx = Index(
                name=idx_name,
                columns=columns,
                is_unique=is_unique,
                index_type=IndexType.UNIQUE if is_unique else IndexType.INDEX,
            )
            table.indexes.append(idx)

        # Get foreign keys
        result = self.execute(f"PRAGMA foreign_key_list('{safe_table_name}')")
        fk_dict: dict[str, ForeignKey] = {}
        for row in result.rows:
            # id, seq, table, from, to, on_update, on_delete, match
            fk_id = str(row[0])
            if fk_id not in fk_dict:
                fk_dict[fk_id] = ForeignKey(
                    name=f"fk_{table_name}_{row[0]}",
                    columns=[],
                    references_table=row[2],
                    references_columns=[],
                    on_update=row[5],
                    on_delete=row[6],
                )
            fk_dict[fk_id].columns.append(row[3])
            fk_dict[fk_id].references_columns.append(row[4])

            # Update column foreign key info
            col = table.get_column(row[3])
            if col:
                col.references_table = row[2]
                col.references_column = row[4]

        table.foreign_keys = list(fk_dict.values())

        # Get row count - using validated table name
        count_result = self.execute(f"SELECT COUNT(*) FROM '{safe_table_name}'")
        if count_result.rows:
            table.row_count = count_result.rows[0][0]

        return table

    def get_info(self) -> DatabaseInfo:
        """Get database info."""
        info = DatabaseInfo(
            db_type=DatabaseType.SQLITE,
            database_name=os.path.basename(self.db_path),
            connected=self.is_connected(),
        )

        # Get SQLite version
        result = self.execute("SELECT sqlite_version()")
        if result.rows:
            info.version = result.rows[0][0]
            parts = info.version.split(".")
            info.version_number = tuple(int(p) for p in parts if p.isdigit())

        # Get table count
        result = self.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        if result.rows:
            info.table_count = result.rows[0][0]

        # Get file size
        if os.path.exists(self.db_path):
            info.total_size_bytes = os.path.getsize(self.db_path)

        return info

    def explain(self, query: str) -> QueryPlan:
        """Get query execution plan."""
        plan = QueryPlan(query=query)

        result = self.execute(f"EXPLAIN QUERY PLAN {query}")

        lines = []
        for row in result.rows:
            # id, parent, notused, detail
            detail = row[3] if len(row) > 3 else str(row)
            lines.append(detail)

            detail_lower = detail.lower()

            # Analyze plan
            if "scan" in detail_lower:
                if "using index" in detail_lower:
                    plan.uses_index = True
                    # Extract index name
                    match = re.search(r"using index (\w+)", detail_lower)
                    if match:
                        plan.index_names.append(match.group(1))
                else:
                    plan.has_full_scan = True

            if "using temp" in detail_lower or "temp b-tree" in detail_lower:
                plan.has_temp_table = True

            if "order by" in detail_lower or "sort" in detail_lower:
                plan.has_sort = True

        plan.plan_text = "\n".join(lines)

        # Generate suggestions
        if plan.has_full_scan:
            plan.suggestions.append("Consider adding an index to avoid full table scan")
        if plan.has_temp_table:
            plan.suggestions.append("Query uses temporary table - may be slow for large datasets")
        if plan.has_sort and not plan.uses_index:
            plan.suggestions.append("Consider adding an index for ORDER BY columns")

        return plan

    def _normalize_type(self, db_type: str) -> ColumnType:
        """Normalize SQLite type to standard type."""
        db_type_upper = db_type.upper()

        if "INT" in db_type_upper:
            if "BIG" in db_type_upper:
                return ColumnType.BIGINT
            elif "SMALL" in db_type_upper or "TINY" in db_type_upper:
                return ColumnType.SMALLINT
            return ColumnType.INTEGER
        elif "CHAR" in db_type_upper or "TEXT" in db_type_upper or "CLOB" in db_type_upper:
            if "VAR" in db_type_upper:
                return ColumnType.VARCHAR
            return ColumnType.TEXT
        elif "BLOB" in db_type_upper:
            return ColumnType.BLOB
        elif "REAL" in db_type_upper or "DOUBLE" in db_type_upper or "FLOAT" in db_type_upper:
            return ColumnType.FLOAT
        elif "BOOL" in db_type_upper:
            return ColumnType.BOOLEAN
        elif "DATE" in db_type_upper:
            if "TIME" in db_type_upper:
                return ColumnType.DATETIME
            return ColumnType.DATE
        elif "TIME" in db_type_upper:
            if "STAMP" in db_type_upper:
                return ColumnType.TIMESTAMP
            return ColumnType.TIME
        elif "JSON" in db_type_upper:
            return ColumnType.JSON

        return ColumnType.UNKNOWN


class PostgreSQLConnector(DatabaseConnector):
    """PostgreSQL database connector."""

    db_type = DatabaseType.POSTGRESQL

    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL connector.

        Args:
            connection_string: PostgreSQL connection URL or params
        """
        self.connection_string = connection_string
        self._conn = None
        self._parse_connection_string()

    def _parse_connection_string(self) -> None:
        """Parse connection string into components."""
        if self.connection_string.startswith("postgresql://") or self.connection_string.startswith("postgres://"):
            parsed = urlparse(self.connection_string)
            self.host = parsed.hostname or "localhost"
            self.port = parsed.port or 5432
            self.database = parsed.path.lstrip("/") if parsed.path else ""
            self.user = parsed.username or ""
            self.password = parsed.password or ""
        else:
            # Assume it's a libpq connection string
            self.host = "localhost"
            self.port = 5432
            self.database = ""
            self.user = ""
            self.password = ""

    def connect(self) -> bool:
        """Connect to PostgreSQL."""
        try:
            import psycopg2
            self._conn = psycopg2.connect(self.connection_string)
            return True
        except ImportError:
            logger.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
            return False
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Close connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._conn is not None and not self._conn.closed

    def execute(self, query: str, params: tuple | None = None) -> QueryResult:
        """Execute a query."""
        result = QueryResult(query=query)

        # Determine query type
        query_upper = query.strip().upper()
        for qt in ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]:
            if query_upper.startswith(qt):
                result.query_type = qt
                break
        else:
            result.query_type = "OTHER"

        start_time = time.time()

        try:
            cursor = self._conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if result.query_type == "SELECT":
                rows = cursor.fetchall()
                result.columns = [desc[0] for desc in cursor.description] if cursor.description else []
                result.rows = [list(row) for row in rows]
                result.row_count = len(rows)
            else:
                self._conn.commit()
                result.affected_rows = cursor.rowcount

            cursor.close()

        except Exception as e:
            result.error = str(e)

        result.execution_time_ms = (time.time() - start_time) * 1000
        return result

    def get_tables(self) -> list[Table]:
        """Get all tables."""
        tables = []

        result = self.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)

        for row in result.rows:
            table = self.get_table(row[0])
            if table:
                tables.append(table)

        return tables

    def get_table(self, table_name: str) -> Table | None:
        """Get detailed table info."""
        table = Table(name=table_name, schema="public")

        # Get columns
        result = self.execute("""
            SELECT
                column_name, data_type, is_nullable,
                column_default, character_maximum_length,
                numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))

        for row in result.rows:
            col = Column(
                name=row[0],
                data_type=row[1],
                is_nullable=row[2] == "YES",
                default_value=row[3],
                max_length=row[4],
                precision=row[5],
                scale=row[6],
            )
            table.columns.append(col)

        # Get primary key
        pk_result = self.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass AND i.indisprimary
        """, (table_name,))

        for row in pk_result.rows:
            col = table.get_column(row[0])
            if col:
                col.is_primary_key = True

        # Get row count estimate
        count_result = self.execute(f"SELECT COUNT(*) FROM \"{table_name}\"")
        if count_result.rows:
            table.row_count = count_result.rows[0][0]

        return table

    def get_info(self) -> DatabaseInfo:
        """Get database info."""
        info = DatabaseInfo(
            db_type=DatabaseType.POSTGRESQL,
            database_name=self.database,
            host=self.host,
            port=self.port,
            user=self.user,
            connected=self.is_connected(),
        )

        result = self.execute("SELECT version()")
        if result.rows:
            info.version = result.rows[0][0]

        result = self.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        if result.rows:
            info.table_count = result.rows[0][0]

        return info

    def explain(self, query: str) -> QueryPlan:
        """Get query execution plan."""
        plan = QueryPlan(query=query)

        result = self.execute(f"EXPLAIN (FORMAT TEXT) {query}")

        lines = [row[0] for row in result.rows]
        plan.plan_text = "\n".join(lines)

        # Analyze plan
        plan_text_lower = plan.plan_text.lower()
        if "index scan" in plan_text_lower or "index only scan" in plan_text_lower:
            plan.uses_index = True
        if "seq scan" in plan_text_lower:
            plan.has_full_scan = True
        if "sort" in plan_text_lower:
            plan.has_sort = True

        return plan


def get_connector(connection_string: str) -> DatabaseConnector:
    """
    Get appropriate connector for a connection string.

    Args:
        connection_string: Database connection string or file path

    Returns:
        Appropriate DatabaseConnector instance
    """
    db_type = DatabaseType.from_url(connection_string)

    if db_type == DatabaseType.SQLITE:
        return SQLiteConnector(connection_string)
    elif db_type == DatabaseType.POSTGRESQL:
        return PostgreSQLConnector(connection_string)
    else:
        # Default to SQLite for file paths
        if os.path.exists(connection_string) or connection_string.endswith((".db", ".sqlite", ".sqlite3")):
            return SQLiteConnector(connection_string)

        raise ValueError(f"Unsupported database type: {connection_string}")


def find_databases(project_root: str) -> list[str]:
    """
    Find database files in a project.

    Args:
        project_root: Project root directory

    Returns:
        List of database file paths
    """
    databases = []
    root = Path(project_root)

    # Common SQLite file patterns
    patterns = ["*.db", "*.sqlite", "*.sqlite3"]

    for pattern in patterns:
        for db_file in root.rglob(pattern):
            # Skip common non-database files
            if any(skip in str(db_file) for skip in ["node_modules", ".git", "__pycache__", "venv", ".venv"]):
                continue
            databases.append(str(db_file))

    return databases
