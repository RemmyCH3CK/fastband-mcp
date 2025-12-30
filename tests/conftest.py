"""Pytest configuration and fixtures for Fastband tests."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir_with_security():
    """Create a temporary directory that's allowed by the path validator.

    Use this fixture for tests that need file operations in temp directories.
    """
    from fastband.tools.core import files as files_module

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir).resolve()
        # Save original validator
        original_validator = files_module._path_validator
        # Allow temp directory along with defaults
        files_module.set_allowed_roots([Path.cwd(), Path.home(), tmpdir_path])
        yield tmpdir_path
        # Restore original validator
        files_module._path_validator = original_validator


@pytest.fixture
def temp_project_with_security():
    """Create a temporary project directory that's allowed by the path validator."""
    from fastband.tools.core import files as files_module

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir).resolve()
        # Create .fastband directory
        (project_path / ".fastband").mkdir()
        # Save original validator and allow temp directory
        original_validator = files_module._path_validator
        files_module.set_allowed_roots([Path.cwd(), Path.home(), project_path])
        yield project_path
        # Restore original validator
        files_module._path_validator = original_validator
