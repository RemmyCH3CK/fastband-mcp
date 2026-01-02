"""
Documentation Tools - Auto-documentation and analysis.

Provides MCP tools for:
- Documentation coverage analysis
- Changelog generation from commits
- README template generation
- Documentation file checks

Usage:
    # Check coverage
    result = await docs_coverage()
    print(f"Coverage: {result['coverage_percentage']}%")

    # Generate changelog
    result = await docs_changelog(version="1.0.0")
    print(result['markdown'])

    # Check required docs
    result = await docs_check()
    print(f"Complete: {result['complete']}")
"""

from fastband.tools.documentation.tool import (
    ChangelogEntry,
    DocCoverage,
    DocumentationTool,
    analyze_doc_coverage,
    docs_changelog,
    docs_check,
    docs_coverage,
    docs_readme,
    generate_changelog_from_commits,
    generate_readme_template,
)

__all__ = [
    # Main tool
    "DocumentationTool",
    # Utility functions
    "analyze_doc_coverage",
    "generate_changelog_from_commits",
    "generate_readme_template",
    # MCP functions
    "docs_coverage",
    "docs_changelog",
    "docs_readme",
    "docs_check",
    # Models
    "DocCoverage",
    "ChangelogEntry",
]


# =========================================================================
# MCP TOOL REGISTRATION
# =========================================================================

def register_tools(mcp_server):
    """Register documentation tools with the MCP server."""

    @mcp_server.tool()
    async def docs_analyze_coverage(language: str = "", path: str = "") -> dict:
        """
        Analyze documentation coverage in code.

        Scans Python/JS/TS files for functions and classes,
        checking for docstrings and comments.

        Args:
            language: Language to analyze (auto-detects if empty)
            path: Project path

        Returns:
            Coverage analysis:
            - coverage_percentage: Overall coverage
            - grade: Letter grade (A-F)
            - missing_docs: List of undocumented items

        Example:
            {} or {"language": "python"}
        """
        return await docs_coverage(language=language, path=path)

    @mcp_server.tool()
    async def docs_generate_changelog(
        since: str = "",
        version: str = "Unreleased",
        path: str = "",
    ) -> dict:
        """
        Generate changelog from git commits.

        Parses conventional commits and groups changes
        by type (feat, fix, refactor, etc.).

        Args:
            since: Git ref to start from (default: last 50 commits)
            version: Version for changelog header
            path: Project path

        Returns:
            Changelog:
            - version: Version string
            - change_count: Number of changes
            - changes: Grouped changes
            - markdown: Formatted changelog

        Example:
            {} or {"since": "v1.0.0", "version": "v1.1.0"}
        """
        return await docs_changelog(since=since, version=version, path=path)

    @mcp_server.tool()
    async def docs_generate_readme(path: str = "") -> dict:
        """
        Generate README template for project.

        Creates a README template based on detected
        project type (Node, Python, Rust, Go).

        Args:
            path: Project path

        Returns:
            README template:
            - project: Project name
            - markdown: Generated template

        Example:
            {}
        """
        return await docs_readme(path=path)

    @mcp_server.tool()
    async def docs_check_files(path: str = "") -> dict:
        """
        Check for required documentation files.

        Verifies presence of README, LICENSE,
        CONTRIBUTING, CHANGELOG, and docs directory.

        Args:
            path: Project path

        Returns:
            Documentation check:
            - checks: Status of each file
            - missing_required: Required files not found
            - missing_recommended: Recommended files not found
            - complete: True if all required files exist

        Example:
            {}
        """
        return await docs_check(path=path)

    return [
        "docs_analyze_coverage",
        "docs_generate_changelog",
        "docs_generate_readme",
        "docs_check_files",
    ]
