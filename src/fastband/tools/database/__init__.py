"""
Database Tools - Schema inspection, query execution, and data exploration.

Provides MCP tools for:
- Database discovery in projects
- Schema inspection and documentation
- Safe query execution with limits
- Query explanation and optimization
- Data sampling and search

Supports SQLite (built-in), PostgreSQL (with psycopg2), MySQL (with mysql-connector).

Usage:
    # Discover databases in project
    result = await db_discover()
    for db in result["databases"]:
        print(f"{db['path']}: {db['tables']} tables")

    # Get schema
    result = await db_schema("data.db")
    print(result["markdown"])

    # Execute query
    result = await db_query("data.db", "SELECT * FROM users LIMIT 10")
    print(result["markdown"])

    # Explain query
    result = await db_explain("data.db", "SELECT * FROM users WHERE email = 'test'")
    for suggestion in result["suggestions"]:
        print(f"- {suggestion}")
"""

from fastband.tools.database.connectors import (
    DatabaseConnector,
    PostgreSQLConnector,
    SQLiteConnector,
    find_databases,
    get_connector,
)
from fastband.tools.database.models import (
    Column,
    ColumnType,
    ConstraintType,
    DatabaseInfo,
    DatabaseType,
    ForeignKey,
    Index,
    IndexType,
    Migration,
    QueryPlan,
    QueryResult,
    SchemaReport,
    Table,
)
from fastband.tools.database.tool import (
    DatabaseConfig,
    DatabaseTool,
    db_discover,
    db_explain,
    db_query,
    db_sample,
    db_schema,
    db_search,
    db_stats,
    db_tables,
)

__all__ = [
    # Main tool
    "DatabaseTool",
    "DatabaseConfig",
    # Connectors
    "DatabaseConnector",
    "SQLiteConnector",
    "PostgreSQLConnector",
    "get_connector",
    "find_databases",
    # MCP functions
    "db_discover",
    "db_schema",
    "db_tables",
    "db_query",
    "db_explain",
    "db_sample",
    "db_search",
    "db_stats",
    # Models
    "DatabaseType",
    "DatabaseInfo",
    "Table",
    "Column",
    "ColumnType",
    "Index",
    "IndexType",
    "ForeignKey",
    "ConstraintType",
    "QueryResult",
    "QueryPlan",
    "Migration",
    "SchemaReport",
]


# =========================================================================
# MCP TOOL REGISTRATION
# =========================================================================

def register_tools(mcp_server):
    """Register database tools with the MCP server."""

    @mcp_server.tool()
    async def db_discover_databases(path: str = "") -> dict:
        """
        Discover databases in a project directory.

        Finds SQLite database files (.db, .sqlite, .sqlite3) in the project.

        Args:
            path: Project path (defaults to current directory)

        Returns:
            List of discovered databases with:
            - path: Relative path to database file
            - type: Database type (sqlite, postgresql, etc.)
            - tables: Number of tables
            - size_mb: File size in MB

        Example:
            {} or {"path": "/path/to/project"}
        """
        return await db_discover(path=path)

    @mcp_server.tool()
    async def db_get_schema(
        connection: str,
        table: str = "",
    ) -> dict:
        """
        Get database or table schema.

        Returns complete schema information including tables, columns,
        indexes, foreign keys, and recommendations.

        Args:
            connection: Database file path (e.g., "data.db") or connection URL
            table: Specific table name (optional, omit for full database schema)

        Returns:
            Schema information with:
            - tables: List of tables with columns
            - indexes: Index definitions
            - foreign_keys: Relationships
            - recommendations: Schema improvement suggestions
            - markdown: Formatted documentation

        Example:
            {"connection": "data.db"}
            {"connection": "data.db", "table": "users"}
        """
        return await db_schema(connection=connection, table=table)

    @mcp_server.tool()
    async def db_list_tables(connection: str) -> dict:
        """
        List all tables in a database.

        Quick overview of tables with row counts.

        Args:
            connection: Database file path or connection URL

        Returns:
            List of tables with:
            - name: Table name
            - columns: Column count
            - rows: Approximate row count
            - primary_key: Primary key columns

        Example:
            {"connection": "data.db"}
        """
        return await db_tables(connection=connection)

    @mcp_server.tool()
    async def db_execute_query(
        connection: str,
        sql: str,
        allow_write: bool = False,
    ) -> dict:
        """
        Execute a SQL query.

        By default, only SELECT queries are allowed for safety.
        Set allow_write=True for INSERT/UPDATE/DELETE operations.

        Args:
            connection: Database file path or connection URL
            sql: SQL query to execute
            allow_write: Allow write operations (default: false)

        Returns:
            Query results with:
            - success: Whether query succeeded
            - columns: Column names (for SELECT)
            - rows: Result data (for SELECT)
            - affected_rows: Rows affected (for write ops)
            - execution_time_ms: Query duration
            - markdown: Formatted table (for SELECT)

        Example:
            {"connection": "data.db", "sql": "SELECT * FROM users LIMIT 10"}
            {"connection": "data.db", "sql": "UPDATE users SET active=1", "allow_write": true}
        """
        return await db_query(connection=connection, sql=sql, allow_write=allow_write)

    @mcp_server.tool()
    async def db_explain_query(
        connection: str,
        sql: str,
    ) -> dict:
        """
        Explain how a query will be executed.

        Shows the query execution plan and suggests optimizations.
        Useful for debugging slow queries.

        Args:
            connection: Database file path or connection URL
            sql: SQL query to explain

        Returns:
            Query plan with:
            - plan: Execution plan text
            - uses_index: Whether indexes are used
            - indexes_used: Names of indexes used
            - warnings: Potential performance issues
            - suggestions: Optimization recommendations

        Example:
            {"connection": "data.db", "sql": "SELECT * FROM orders WHERE customer_id = 123"}
        """
        return await db_explain(connection=connection, sql=sql)

    @mcp_server.tool()
    async def db_sample_data(
        connection: str,
        table: str,
        limit: int = 10,
    ) -> dict:
        """
        Get sample data from a table.

        Quick way to see what data looks like without writing SQL.

        Args:
            connection: Database file path or connection URL
            table: Table name to sample
            limit: Number of rows to return (default: 10, max: 100)

        Returns:
            Sample data with:
            - table: Table name
            - columns: Column names
            - rows: Sample data rows
            - total_rows: Total rows in table

        Example:
            {"connection": "data.db", "table": "users", "limit": 5}
        """
        return await db_sample(connection=connection, table=table, limit=min(limit, 100))

    @mcp_server.tool()
    async def db_search_data(
        connection: str,
        table: str,
        column: str,
        value: str,
        limit: int = 50,
    ) -> dict:
        """
        Search for specific values in a table column.

        Use % as wildcard for partial matching (LIKE queries).

        Args:
            connection: Database file path or connection URL
            table: Table to search
            column: Column to search in
            value: Value to find (use % for wildcards)
            limit: Maximum results (default: 50)

        Returns:
            Matching rows with:
            - table: Table name
            - search_column: Column searched
            - search_value: Search term
            - columns: All column names
            - rows: Matching data
            - match_count: Number of matches

        Example:
            {"connection": "data.db", "table": "users", "column": "email", "value": "%@gmail.com"}
            {"connection": "data.db", "table": "orders", "column": "status", "value": "pending"}
        """
        return await db_search(
            connection=connection,
            table=table,
            column=column,
            value=value,
            limit=limit,
        )

    @mcp_server.tool()
    async def db_column_stats(
        connection: str,
        table: str,
        column: str,
    ) -> dict:
        """
        Get statistics for a table column.

        Analyzes data distribution including distinct values, nulls,
        min/max for numbers, and most common values.

        Args:
            connection: Database file path or connection URL
            table: Table name
            column: Column name

        Returns:
            Column statistics:
            - column: Column name
            - type: Data type
            - total_rows: Total row count
            - null_count: Number of NULL values
            - distinct_count: Number of unique values
            - min/max/avg: For numeric columns
            - top_values: Most common values with counts

        Example:
            {"connection": "data.db", "table": "orders", "column": "status"}
        """
        return await db_stats(connection=connection, table=table, column=column)

    return [
        "db_discover_databases",
        "db_get_schema",
        "db_list_tables",
        "db_execute_query",
        "db_explain_query",
        "db_sample_data",
        "db_search_data",
        "db_column_stats",
    ]
