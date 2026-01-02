"""
Database Tool - Unified interface for database operations.

Provides MCP tools for:
- Schema inspection and documentation
- Query execution with safety checks
- Query explanation and optimization
- Data exploration
"""

import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastband.tools.database.connectors import (
    DatabaseConnector,
    find_databases,
    get_connector,
)
from fastband.tools.database.models import (
    DatabaseInfo,
    DatabaseType,
    QueryPlan,
    QueryResult,
    SchemaReport,
    Table,
)

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Configuration for database operations."""

    # Safety settings
    allow_write: bool = False  # Allow INSERT/UPDATE/DELETE
    allow_ddl: bool = False  # Allow CREATE/DROP/ALTER
    max_rows: int = 1000  # Maximum rows to return
    query_timeout: int = 30  # Query timeout in seconds

    # Connection
    default_connection: str = ""  # Default database connection


class DatabaseTool:
    """
    Unified database tool for schema inspection and queries.

    Supports SQLite (built-in), PostgreSQL, and MySQL.
    """

    def __init__(self, project_root: str, config: DatabaseConfig | None = None):
        self.project_root = Path(project_root)
        self.config = config or DatabaseConfig()
        self._connectors: dict[str, DatabaseConnector] = {}

    def get_connector(self, connection: str) -> DatabaseConnector:
        """Get or create a connector for the connection string."""
        # Resolve relative paths
        if not connection.startswith(("postgresql://", "postgres://", "mysql://")):
            if not os.path.isabs(connection):
                connection = str(self.project_root / connection)

        if connection not in self._connectors:
            connector = get_connector(connection)
            connector.connect()
            self._connectors[connection] = connector

        return self._connectors[connection]

    def close_all(self) -> None:
        """Close all database connections."""
        for connector in self._connectors.values():
            connector.disconnect()
        self._connectors.clear()

    # =========================================================================
    # DISCOVERY
    # =========================================================================

    async def discover_databases(self) -> list[dict[str, Any]]:
        """
        Find all databases in the project.

        Returns list of discovered database files with basic info.
        """
        databases = find_databases(str(self.project_root))

        results = []
        for db_path in databases:
            try:
                connector = self.get_connector(db_path)
                info = connector.get_info()
                results.append({
                    "path": os.path.relpath(db_path, self.project_root),
                    "type": info.db_type.value,
                    "tables": info.table_count,
                    "size_mb": round(info.total_size_bytes / (1024 * 1024), 2) if info.total_size_bytes else 0,
                })
            except Exception as e:
                results.append({
                    "path": os.path.relpath(db_path, self.project_root),
                    "error": str(e),
                })

        return results

    # =========================================================================
    # SCHEMA INSPECTION
    # =========================================================================

    async def get_schema(self, connection: str) -> SchemaReport:
        """
        Get complete schema report for a database.

        Args:
            connection: Database connection string or file path

        Returns:
            SchemaReport with all tables, columns, indexes, etc.
        """
        connector = self.get_connector(connection)

        report = SchemaReport(report_id=str(uuid.uuid4())[:8])
        report.database_info = connector.get_info()
        report.tables = connector.get_tables()

        # Calculate totals
        for table in report.tables:
            report.total_columns += len(table.columns)
            report.total_indexes += len(table.indexes)
            report.total_foreign_keys += len(table.foreign_keys)

        # Generate recommendations
        report.recommendations = self._analyze_schema(report)

        return report

    async def get_table_schema(
        self,
        connection: str,
        table_name: str,
    ) -> dict[str, Any]:
        """
        Get schema for a specific table.

        Args:
            connection: Database connection string
            table_name: Table name

        Returns:
            Table schema with columns, indexes, and DDL
        """
        connector = self.get_connector(connection)
        table = connector.get_table(table_name)

        if not table:
            return {"error": f"Table '{table_name}' not found"}

        result = table.to_dict()
        result["ddl"] = table.to_ddl(connector.db_type)

        return result

    async def list_tables(self, connection: str) -> list[dict[str, Any]]:
        """
        List all tables in a database with basic stats.

        Args:
            connection: Database connection string

        Returns:
            List of tables with row counts
        """
        connector = self.get_connector(connection)
        tables = connector.get_tables()

        return [
            {
                "name": t.name,
                "columns": len(t.columns),
                "rows": t.row_count,
                "primary_key": t.primary_key_columns,
            }
            for t in tables
        ]

    # =========================================================================
    # QUERY EXECUTION
    # =========================================================================

    async def execute_query(
        self,
        connection: str,
        query: str,
        params: tuple | None = None,
    ) -> QueryResult:
        """
        Execute a SQL query with safety checks.

        Args:
            connection: Database connection string
            query: SQL query to execute
            params: Query parameters (for parameterized queries)

        Returns:
            QueryResult with data or error
        """
        # Safety checks
        query_upper = query.strip().upper()

        # Check for write operations
        write_keywords = ["INSERT", "UPDATE", "DELETE", "REPLACE"]
        if any(query_upper.startswith(kw) for kw in write_keywords):
            if not self.config.allow_write:
                return QueryResult(
                    query=query,
                    error="Write operations are disabled. Set allow_write=True to enable.",
                )

        # Check for DDL operations
        ddl_keywords = ["CREATE", "DROP", "ALTER", "TRUNCATE"]
        if any(query_upper.startswith(kw) for kw in ddl_keywords):
            if not self.config.allow_ddl:
                return QueryResult(
                    query=query,
                    error="DDL operations are disabled. Set allow_ddl=True to enable.",
                )

        # Execute query
        connector = self.get_connector(connection)
        result = connector.execute(query, params)

        # Limit rows returned
        if result.query_type == "SELECT" and len(result.rows) > self.config.max_rows:
            result.rows = result.rows[:self.config.max_rows]
            result.row_count = len(result.rows)

        return result

    async def explain_query(
        self,
        connection: str,
        query: str,
    ) -> QueryPlan:
        """
        Get execution plan and optimization suggestions for a query.

        Args:
            connection: Database connection string
            query: SQL query to explain

        Returns:
            QueryPlan with execution details and suggestions
        """
        connector = self.get_connector(connection)
        return connector.explain(query)

    # =========================================================================
    # DATA EXPLORATION
    # =========================================================================

    async def sample_data(
        self,
        connection: str,
        table_name: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Get sample data from a table.

        Args:
            connection: Database connection string
            table_name: Table to sample
            limit: Number of rows to return

        Returns:
            Sample rows with column names
        """
        connector = self.get_connector(connection)

        # Validate table exists
        table = connector.get_table(table_name)
        if not table:
            return {"error": f"Table '{table_name}' not found"}

        # Get sample with ORDER BY to get consistent results
        pk_cols = table.primary_key_columns
        order_by = f"ORDER BY {pk_cols[0]}" if pk_cols else ""

        result = connector.execute(
            f"SELECT * FROM \"{table_name}\" {order_by} LIMIT {limit}"
        )

        return {
            "table": table_name,
            "columns": result.columns,
            "rows": result.rows,
            "total_rows": table.row_count,
            "sampled": limit,
        }

    async def search_data(
        self,
        connection: str,
        table_name: str,
        column: str,
        value: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Search for data in a table column.

        Args:
            connection: Database connection string
            table_name: Table to search
            column: Column to search in
            value: Value to search for (supports % wildcards)
            limit: Maximum results

        Returns:
            Matching rows
        """
        connector = self.get_connector(connection)

        # Validate table and column
        table = connector.get_table(table_name)
        if not table:
            return {"error": f"Table '{table_name}' not found"}

        col = table.get_column(column)
        if not col:
            return {"error": f"Column '{column}' not found in table '{table_name}'"}

        # Use LIKE for string columns, = for others
        if "%" in value:
            operator = "LIKE"
        else:
            operator = "="

        result = connector.execute(
            f"SELECT * FROM \"{table_name}\" WHERE \"{column}\" {operator} ? LIMIT {limit}",
            (value,)
        )

        return {
            "table": table_name,
            "search_column": column,
            "search_value": value,
            "columns": result.columns,
            "rows": result.rows,
            "match_count": len(result.rows),
        }

    async def get_column_stats(
        self,
        connection: str,
        table_name: str,
        column: str,
    ) -> dict[str, Any]:
        """
        Get statistics for a column.

        Args:
            connection: Database connection string
            table_name: Table name
            column: Column name

        Returns:
            Column statistics (distinct values, nulls, min, max, etc.)
        """
        connector = self.get_connector(connection)

        # Validate table and column
        table = connector.get_table(table_name)
        if not table:
            return {"error": f"Table '{table_name}' not found"}

        col = table.get_column(column)
        if not col:
            return {"error": f"Column '{column}' not found"}

        stats: dict[str, Any] = {
            "column": column,
            "type": col.data_type,
            "nullable": col.is_nullable,
        }

        # Get basic stats
        result = connector.execute(f"""
            SELECT
                COUNT(*) as total,
                COUNT("{column}") as non_null,
                COUNT(DISTINCT "{column}") as distinct_count
            FROM "{table_name}"
        """)

        if result.rows:
            stats["total_rows"] = result.rows[0][0]
            stats["non_null"] = result.rows[0][1]
            stats["null_count"] = stats["total_rows"] - stats["non_null"]
            stats["distinct_count"] = result.rows[0][2]

        # For numeric columns, get min/max/avg
        if col.normalized_type.value in ["integer", "bigint", "float", "double", "decimal"]:
            result = connector.execute(f"""
                SELECT MIN("{column}"), MAX("{column}"), AVG("{column}")
                FROM "{table_name}"
            """)
            if result.rows:
                stats["min"] = result.rows[0][0]
                stats["max"] = result.rows[0][1]
                stats["avg"] = round(result.rows[0][2], 2) if result.rows[0][2] else None

        # Get top values
        result = connector.execute(f"""
            SELECT "{column}", COUNT(*) as cnt
            FROM "{table_name}"
            WHERE "{column}" IS NOT NULL
            GROUP BY "{column}"
            ORDER BY cnt DESC
            LIMIT 10
        """)

        stats["top_values"] = [
            {"value": row[0], "count": row[1]}
            for row in result.rows
        ]

        return stats

    # =========================================================================
    # ANALYSIS
    # =========================================================================

    def _analyze_schema(self, report: SchemaReport) -> list[str]:
        """Analyze schema and generate recommendations."""
        recommendations = []

        for table in report.tables:
            # Check for missing primary key
            if not table.primary_key_columns:
                recommendations.append(
                    f"Table '{table.name}' has no primary key. Consider adding one."
                )

            # Check for tables without indexes
            if not table.indexes and table.row_count and table.row_count > 1000:
                recommendations.append(
                    f"Table '{table.name}' has {table.row_count:,} rows but no indexes. "
                    "Consider adding indexes for frequently queried columns."
                )

            # Check for nullable foreign keys
            for col in table.columns:
                if col.references_table and col.is_nullable:
                    recommendations.append(
                        f"Column '{table.name}.{col.name}' is a nullable foreign key. "
                        "Consider if this is intentional."
                    )

        if not recommendations:
            recommendations.append("Schema looks healthy. No issues found.")

        return recommendations[:10]


# =========================================================================
# MCP TOOL FUNCTIONS
# =========================================================================

async def db_discover(path: str = "") -> dict[str, Any]:
    """
    Discover databases in a project.

    Finds SQLite database files in the project directory.

    Args:
        path: Project path (defaults to current directory)

    Returns:
        List of discovered databases with type and table count

    Example:
        {} or {"path": "/path/to/project"}
    """
    project_root = path or os.getcwd()
    tool = DatabaseTool(project_root)

    databases = await tool.discover_databases()

    return {
        "type": "database_discovery",
        "project": project_root,
        "databases": databases,
        "count": len(databases),
    }


async def db_schema(
    connection: str,
    table: str = "",
) -> dict[str, Any]:
    """
    Get database schema information.

    If table is specified, returns detailed info for that table.
    Otherwise returns overview of all tables.

    Args:
        connection: Database file path or connection string
        table: Specific table name (optional)

    Returns:
        Schema information with tables, columns, indexes

    Example:
        {"connection": "data.db"}
        {"connection": "data.db", "table": "users"}
    """
    tool = DatabaseTool(os.getcwd())

    if table:
        result = await tool.get_table_schema(connection, table)
        return {"type": "table_schema", **result}
    else:
        report = await tool.get_schema(connection)
        return {
            "type": "database_schema",
            **report.to_summary(),
            "markdown": report.to_markdown(),
        }


async def db_tables(connection: str) -> dict[str, Any]:
    """
    List all tables in a database.

    Args:
        connection: Database file path or connection string

    Returns:
        List of tables with column counts and row counts

    Example:
        {"connection": "data.db"}
    """
    tool = DatabaseTool(os.getcwd())
    tables = await tool.list_tables(connection)

    return {
        "type": "table_list",
        "connection": connection,
        "tables": tables,
        "count": len(tables),
    }


async def db_query(
    connection: str,
    sql: str,
    allow_write: bool = False,
) -> dict[str, Any]:
    """
    Execute a SQL query.

    By default, only SELECT queries are allowed. Set allow_write=True
    for INSERT/UPDATE/DELETE.

    Args:
        connection: Database file path or connection string
        sql: SQL query to execute
        allow_write: Allow write operations (default: false)

    Returns:
        Query results with columns and rows

    Example:
        {"connection": "data.db", "sql": "SELECT * FROM users LIMIT 10"}
    """
    config = DatabaseConfig(allow_write=allow_write)
    tool = DatabaseTool(os.getcwd(), config)

    result = await tool.execute_query(connection, sql)

    response = result.to_dict()
    response["type"] = "query_result"

    # Add markdown table for SELECT results
    if result.success and result.query_type == "SELECT":
        response["markdown"] = result.to_markdown_table()

    return response


async def db_explain(
    connection: str,
    sql: str,
) -> dict[str, Any]:
    """
    Explain a query execution plan.

    Shows how the database will execute the query and suggests optimizations.

    Args:
        connection: Database file path or connection string
        sql: SQL query to explain

    Returns:
        Execution plan with optimization suggestions

    Example:
        {"connection": "data.db", "sql": "SELECT * FROM users WHERE email = 'test@example.com'"}
    """
    tool = DatabaseTool(os.getcwd())
    plan = await tool.explain_query(connection, sql)

    return {
        "type": "query_plan",
        **plan.to_dict(),
    }


async def db_sample(
    connection: str,
    table: str,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Get sample data from a table.

    Args:
        connection: Database file path or connection string
        table: Table name
        limit: Number of rows to return (default: 10)

    Returns:
        Sample rows from the table

    Example:
        {"connection": "data.db", "table": "users", "limit": 5}
    """
    tool = DatabaseTool(os.getcwd())
    return await tool.sample_data(connection, table, limit)


async def db_search(
    connection: str,
    table: str,
    column: str,
    value: str,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Search for data in a table column.

    Use % as wildcard for partial matching.

    Args:
        connection: Database file path or connection string
        table: Table to search
        column: Column to search in
        value: Value to find (use % for wildcards)
        limit: Maximum results (default: 50)

    Returns:
        Matching rows

    Example:
        {"connection": "data.db", "table": "users", "column": "email", "value": "%@gmail.com"}
    """
    tool = DatabaseTool(os.getcwd())
    return await tool.search_data(connection, table, column, value, limit)


async def db_stats(
    connection: str,
    table: str,
    column: str,
) -> dict[str, Any]:
    """
    Get statistics for a column.

    Shows distinct values, nulls, min/max (for numbers), and top values.

    Args:
        connection: Database file path or connection string
        table: Table name
        column: Column name

    Returns:
        Column statistics

    Example:
        {"connection": "data.db", "table": "orders", "column": "status"}
    """
    tool = DatabaseTool(os.getcwd())
    return await tool.get_column_stats(connection, table, column)
