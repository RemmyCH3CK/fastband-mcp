"""
Tests for Context Tools.

Tests cover:
- IndexCodebaseTool: Codebase indexing for semantic search
- SemanticSearchTool: Natural language code search
- IndexStatusTool: Index status checking
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastband.tools.context.index_codebase import IndexCodebaseTool
from fastband.tools.context.semantic_search import SemanticSearchTool

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)
        # Create some source files
        (project / "main.py").write_text("""
def main():
    '''Main entry point.'''
    print("Hello, World!")

if __name__ == "__main__":
    main()
""")
        (project / "utils.py").write_text("""
def add(a, b):
    '''Add two numbers.'''
    return a + b

def multiply(a, b):
    '''Multiply two numbers.'''
    return a * b
""")
        yield project


@pytest.fixture
def index_tool():
    """Create an IndexCodebaseTool instance."""
    return IndexCodebaseTool()


@pytest.fixture
def search_tool():
    """Create a SemanticSearchTool instance."""
    return SemanticSearchTool()


# =============================================================================
# INDEX CODEBASE TOOL TESTS
# =============================================================================


class TestIndexCodebaseToolDefinition:
    """Tests for IndexCodebaseTool definition."""

    def test_tool_name(self, index_tool):
        """Test tool name."""
        assert index_tool.definition.metadata.name == "index_codebase"

    def test_tool_description(self, index_tool):
        """Test tool has description."""
        assert "index" in index_tool.definition.metadata.description.lower()
        assert "semantic" in index_tool.definition.metadata.description.lower()

    def test_tool_parameters(self, index_tool):
        """Test tool parameters are defined."""
        params = {p.name for p in index_tool.definition.parameters}
        assert "directory" in params
        assert "provider" in params
        assert "incremental" in params
        assert "clear" in params

    def test_provider_parameter_enum(self, index_tool):
        """Test provider parameter has correct enum values."""
        provider_param = next(
            p for p in index_tool.definition.parameters if p.name == "provider"
        )
        assert provider_param.enum == ["openai", "gemini", "ollama"]


class TestIndexCodebaseToolExecution:
    """Tests for IndexCodebaseTool execution."""

    @pytest.mark.asyncio
    async def test_directory_not_found(self, index_tool):
        """Test error when directory doesn't exist."""
        result = await index_tool.execute(directory="/nonexistent/path")
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_not_a_directory(self, index_tool, temp_project):
        """Test error when path is not a directory."""
        file_path = temp_project / "main.py"
        result = await index_tool.execute(directory=str(file_path))
        assert result.success is False
        assert "not a directory" in result.error.lower()

    @pytest.mark.asyncio
    async def test_missing_openai_api_key(self, index_tool, temp_project):
        """Test error when OPENAI_API_KEY is missing."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if it exists
            os.environ.pop("OPENAI_API_KEY", None)
            result = await index_tool.execute(
                directory=str(temp_project), provider="openai"
            )
            assert result.success is False
            assert "OPENAI_API_KEY" in result.error

    @pytest.mark.asyncio
    async def test_missing_gemini_api_key(self, index_tool, temp_project):
        """Test error when Gemini API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GOOGLE_API_KEY", None)
            os.environ.pop("GEMINI_API_KEY", None)
            result = await index_tool.execute(
                directory=str(temp_project), provider="gemini"
            )
            assert result.success is False
            assert "API_KEY" in result.error

    @pytest.mark.asyncio
    async def test_ollama_provider_no_key_required(self, index_tool, temp_project):
        """Test Ollama provider doesn't require API key."""
        # Mock the create_index to avoid actual indexing
        mock_index = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.chunks_indexed = 5
        mock_result.files_processed = 2
        mock_result.files_skipped = 0
        mock_result.duration_seconds = 1.5
        mock_result.errors = []
        mock_index.index_directory = AsyncMock(return_value=mock_result)
        mock_index.clear = MagicMock()
        mock_index.close = MagicMock()

        with patch(
            "fastband.embeddings.index.create_index",
            return_value=mock_index,
        ):
            result = await index_tool.execute(
                directory=str(temp_project), provider="ollama"
            )
            assert result.success is True
            assert result.data["provider"] == "ollama"

    @pytest.mark.asyncio
    async def test_successful_indexing(self, index_tool, temp_project):
        """Test successful indexing operation."""
        mock_index = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.chunks_indexed = 10
        mock_result.files_processed = 5
        mock_result.files_skipped = 1
        mock_result.duration_seconds = 2.5
        mock_result.errors = []
        mock_index.index_directory = AsyncMock(return_value=mock_result)
        mock_index.clear = MagicMock()
        mock_index.close = MagicMock()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch(
                "fastband.embeddings.index.create_index",
                return_value=mock_index,
            ):
                result = await index_tool.execute(directory=str(temp_project))

                assert result.success is True
                assert result.data["chunks_indexed"] == 10
                assert result.data["files_processed"] == 5
                assert result.data["files_skipped"] == 1

    @pytest.mark.asyncio
    async def test_indexing_with_clear(self, index_tool, temp_project):
        """Test indexing with clear option."""
        mock_index = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.chunks_indexed = 5
        mock_result.files_processed = 2
        mock_result.files_skipped = 0
        mock_result.duration_seconds = 1.0
        mock_result.errors = []
        mock_index.index_directory = AsyncMock(return_value=mock_result)
        mock_index.clear = MagicMock()
        mock_index.close = MagicMock()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch(
                "fastband.embeddings.index.create_index",
                return_value=mock_index,
            ):
                result = await index_tool.execute(
                    directory=str(temp_project), clear=True
                )

                assert result.success is True
                mock_index.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_indexing_import_error(self, index_tool, temp_project):
        """Test handling of missing dependencies."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch(
                "fastband.embeddings.index.create_index",
                side_effect=ImportError("numpy not found"),
            ):
                result = await index_tool.execute(directory=str(temp_project))

                assert result.success is False
                assert "Missing dependency" in result.error

    @pytest.mark.asyncio
    async def test_indexing_exception(self, index_tool, temp_project):
        """Test handling of general exceptions."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch(
                "fastband.embeddings.index.create_index",
                side_effect=Exception("Connection failed"),
            ):
                result = await index_tool.execute(directory=str(temp_project))

                assert result.success is False
                assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_uses_cwd_when_no_directory(self, index_tool):
        """Test uses current directory when none specified."""
        mock_index = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.chunks_indexed = 0
        mock_result.files_processed = 0
        mock_result.files_skipped = 0
        mock_result.duration_seconds = 0.1
        mock_result.errors = []
        mock_index.index_directory = AsyncMock(return_value=mock_result)
        mock_index.clear = MagicMock()
        mock_index.close = MagicMock()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch(
                "fastband.embeddings.index.create_index",
                return_value=mock_index,
            ):
                result = await index_tool.execute()
                assert result.success is True
                # Should use cwd
                assert Path.cwd().name in result.data["directory"]


# =============================================================================
# SEMANTIC SEARCH TOOL TESTS
# =============================================================================


class TestSemanticSearchToolDefinition:
    """Tests for SemanticSearchTool definition."""

    def test_tool_name(self, search_tool):
        """Test tool name."""
        assert search_tool.definition.metadata.name == "semantic_search"

    def test_tool_description(self, search_tool):
        """Test tool has description."""
        assert "search" in search_tool.definition.metadata.description.lower()
        assert "semantic" in search_tool.definition.metadata.description.lower()

    def test_tool_parameters(self, search_tool):
        """Test tool parameters are defined."""
        params = {p.name for p in search_tool.definition.parameters}
        assert "query" in params
        assert "limit" in params
        assert "file_type" in params
        assert "file_pattern" in params
        assert "directory" in params
        assert "provider" in params

    def test_query_parameter_required(self, search_tool):
        """Test query parameter is required."""
        query_param = next(
            p for p in search_tool.definition.parameters if p.name == "query"
        )
        assert query_param.required is True


class TestSemanticSearchToolExecution:
    """Tests for SemanticSearchTool execution."""

    @pytest.mark.asyncio
    async def test_index_not_found(self, search_tool, temp_project):
        """Test error when no index exists."""
        result = await search_tool.execute(
            query="authentication", directory=str(temp_project)
        )
        assert result.success is False
        assert "No index found" in result.error

    @pytest.mark.asyncio
    async def test_missing_api_key(self, search_tool, temp_project):
        """Test error when API key is missing."""
        # Create fake index file
        index_path = temp_project / ".fastband" / "semantic.db"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("fake index")

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            result = await search_tool.execute(
                query="test", directory=str(temp_project), provider="openai"
            )
            assert result.success is False
            assert "API_KEY" in result.error

    @pytest.mark.asyncio
    async def test_successful_search(self, search_tool, temp_project):
        """Test successful search operation."""
        # Create fake index file
        index_path = temp_project / ".fastband" / "semantic.db"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("fake index")

        # Mock search result
        mock_result = MagicMock()
        mock_result.metadata = MagicMock()
        mock_result.metadata.file_path = "main.py"
        mock_result.metadata.name = "main"
        mock_result.metadata.chunk_type = MagicMock(value="function")
        mock_result.metadata.start_line = 1
        mock_result.metadata.end_line = 5
        mock_result.metadata.docstring = "Main entry point"
        mock_result.score = 0.95
        mock_result.content = "def main(): print('Hello')"

        mock_index = MagicMock()
        mock_index.search = AsyncMock(return_value=[mock_result])
        mock_index.close = MagicMock()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch(
                "fastband.embeddings.index.create_index",
                return_value=mock_index,
            ):
                result = await search_tool.execute(
                    query="main function", directory=str(temp_project)
                )

                assert result.success is True
                assert result.data["query"] == "main function"
                assert result.data["total_results"] == 1
                assert result.data["results"][0]["file"] == "main.py"
                assert result.data["results"][0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_search_with_filters(self, search_tool, temp_project):
        """Test search with file type and pattern filters."""
        index_path = temp_project / ".fastband" / "semantic.db"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("fake index")

        mock_index = MagicMock()
        mock_index.search = AsyncMock(return_value=[])
        mock_index.close = MagicMock()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch(
                "fastband.embeddings.index.create_index",
                return_value=mock_index,
            ):
                result = await search_tool.execute(
                    query="test",
                    directory=str(temp_project),
                    file_type="py",
                    file_pattern="src/",
                    limit=10,
                )

                assert result.success is True
                mock_index.search.assert_called_once_with(
                    query="test",
                    limit=10,
                    file_type="py",
                    file_path_pattern="src/",
                )

    @pytest.mark.asyncio
    async def test_search_import_error(self, search_tool, temp_project):
        """Test handling of missing dependencies."""
        index_path = temp_project / ".fastband" / "semantic.db"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("fake index")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch(
                "fastband.embeddings.index.create_index",
                side_effect=ImportError("torch not found"),
            ):
                result = await search_tool.execute(
                    query="test", directory=str(temp_project)
                )

                assert result.success is False
                assert "Missing dependency" in result.error

    @pytest.mark.asyncio
    async def test_search_exception(self, search_tool, temp_project):
        """Test handling of general exceptions."""
        index_path = temp_project / ".fastband" / "semantic.db"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("fake index")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch(
                "fastband.embeddings.index.create_index",
                side_effect=Exception("Network error"),
            ):
                result = await search_tool.execute(
                    query="test", directory=str(temp_project)
                )

                assert result.success is False
                assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_search_long_content_truncation(self, search_tool, temp_project):
        """Test that long content is truncated."""
        index_path = temp_project / ".fastband" / "semantic.db"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("fake index")

        mock_result = MagicMock()
        mock_result.metadata = MagicMock()
        mock_result.metadata.file_path = "long.py"
        mock_result.metadata.name = "long_function"
        mock_result.metadata.chunk_type = MagicMock(value="function")
        mock_result.metadata.start_line = 1
        mock_result.metadata.end_line = 100
        mock_result.metadata.docstring = "A" * 300  # Long docstring
        mock_result.score = 0.9
        mock_result.content = "x" * 1000  # Long content

        mock_index = MagicMock()
        mock_index.search = AsyncMock(return_value=[mock_result])
        mock_index.close = MagicMock()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch(
                "fastband.embeddings.index.create_index",
                return_value=mock_index,
            ):
                result = await search_tool.execute(
                    query="test", directory=str(temp_project)
                )

                assert result.success is True
                # Docstring truncated to 200 chars
                assert len(result.data["results"][0]["docstring"]) == 200
                # Content truncated to 500 + "..."
                assert len(result.data["results"][0]["content_preview"]) == 503


# =============================================================================
# TOOL CATEGORY TESTS
# =============================================================================


class TestToolCategories:
    """Tests for tool categories."""

    def test_index_tool_category(self, index_tool):
        """Test IndexCodebaseTool has AI category."""
        from fastband.tools.base import ToolCategory

        assert index_tool.definition.metadata.category == ToolCategory.AI

    def test_search_tool_category(self, search_tool):
        """Test SemanticSearchTool has AI category."""
        from fastband.tools.base import ToolCategory

        assert search_tool.definition.metadata.category == ToolCategory.AI
