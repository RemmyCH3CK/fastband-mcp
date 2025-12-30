"""Tests for project detection."""

import json
import tempfile
from pathlib import Path

import pytest

from fastband.core.detection import (
    BuildTool,
    DetectedFramework,
    DetectedLanguage,
    Framework,
    Language,
    PackageManager,
    ProjectDetector,
    ProjectInfo,
    ProjectType,
    detect_project,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def python_project(temp_dir):
    """Create a minimal Python project."""
    # pyproject.toml
    (temp_dir / "pyproject.toml").write_text("""
[project]
name = "test-project"
version = "1.0.0"
description = "A test project"
dependencies = ["flask>=2.0"]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
""")

    # requirements.txt for flask detection
    (temp_dir / "requirements.txt").write_text("flask>=2.0\n")

    # Source files
    src = temp_dir / "src"
    src.mkdir()
    (src / "app.py").write_text("from flask import Flask\napp = Flask(__name__)")
    (src / "utils.py").write_text("def helper(): pass")

    # Tests
    tests = temp_dir / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text("def test_example(): pass")

    return temp_dir


@pytest.fixture
def javascript_project(temp_dir):
    """Create a minimal JavaScript/React project."""
    # package.json
    (temp_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "react-app",
                "version": "0.1.0",
                "description": "A React application",
                "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"},
                "devDependencies": {"vite": "^5.0.0"},
            }
        )
    )

    # package-lock.json (indicates npm)
    (temp_dir / "package-lock.json").write_text("{}")

    # Vite config
    (temp_dir / "vite.config.js").write_text("export default {}")

    # Source files
    src = temp_dir / "src"
    src.mkdir()
    (src / "App.jsx").write_text("export function App() { return <div>Hello</div> }")
    (src / "index.js").write_text("import React from 'react'")

    return temp_dir


@pytest.fixture
def rust_project(temp_dir):
    """Create a minimal Rust project."""
    (temp_dir / "Cargo.toml").write_text("""
[package]
name = "rust-cli"
version = "0.1.0"
description = "A Rust CLI tool"

[dependencies]
clap = "4.0"
""")

    src = temp_dir / "src"
    src.mkdir()
    (src / "main.rs").write_text('fn main() { println!("Hello"); }')
    (src / "lib.rs").write_text("pub fn greet() {}")

    return temp_dir


@pytest.fixture
def monorepo_project(temp_dir):
    """Create a monorepo project."""
    # Root package.json with workspaces
    (temp_dir / "package.json").write_text(
        json.dumps({"name": "monorepo", "private": True, "workspaces": ["packages/*"]})
    )

    (temp_dir / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'")

    # pnpm-lock.yaml (indicates pnpm)
    (temp_dir / "pnpm-lock.yaml").write_text("lockfileVersion: 6.0")

    # Packages
    packages = temp_dir / "packages"
    packages.mkdir()

    # Package A
    pkg_a = packages / "pkg-a"
    pkg_a.mkdir()
    (pkg_a / "package.json").write_text(json.dumps({"name": "@mono/pkg-a", "version": "1.0.0"}))

    # Package B
    pkg_b = packages / "pkg-b"
    pkg_b.mkdir()
    (pkg_b / "package.json").write_text(json.dumps({"name": "@mono/pkg-b", "version": "1.0.0"}))

    return temp_dir


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestEnums:
    """Tests for detection enums."""

    def test_language_values(self):
        """Test Language enum values."""
        assert Language.PYTHON.value == "python"
        assert Language.JAVASCRIPT.value == "javascript"
        assert Language.TYPESCRIPT.value == "typescript"
        assert Language.RUST.value == "rust"
        assert Language.GO.value == "go"

    def test_project_type_values(self):
        """Test ProjectType enum values."""
        assert ProjectType.WEB_APP.value == "web_app"
        assert ProjectType.API_SERVICE.value == "api_service"
        assert ProjectType.MOBILE_CROSS.value == "mobile_cross_platform"
        assert ProjectType.CLI_TOOL.value == "cli_tool"
        assert ProjectType.LIBRARY.value == "library"

    def test_framework_values(self):
        """Test Framework enum values."""
        assert Framework.FLASK.value == "flask"
        assert Framework.REACT.value == "react"
        assert Framework.NEXTJS.value == "nextjs"
        assert Framework.FLUTTER.value == "flutter"

    def test_package_manager_values(self):
        """Test PackageManager enum values."""
        assert PackageManager.PIP.value == "pip"
        assert PackageManager.NPM.value == "npm"
        assert PackageManager.CARGO.value == "cargo"

    def test_build_tool_values(self):
        """Test BuildTool enum values."""
        assert BuildTool.WEBPACK.value == "webpack"
        assert BuildTool.VITE.value == "vite"
        assert BuildTool.DOCKER.value == "docker"


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestDataclasses:
    """Tests for detection dataclasses."""

    def test_detected_language(self):
        """Test DetectedLanguage dataclass."""
        lang = DetectedLanguage(
            language=Language.PYTHON, confidence=0.9, file_count=15, evidence=["app.py", "utils.py"]
        )

        assert lang.language == Language.PYTHON
        assert lang.confidence == 0.9
        assert lang.file_count == 15
        assert len(lang.evidence) == 2

    def test_detected_framework(self):
        """Test DetectedFramework dataclass."""
        fw = DetectedFramework(
            framework=Framework.FLASK,
            confidence=0.8,
            version="2.0.0",
            evidence=["dependency: flask", "file: app.py"],
        )

        assert fw.framework == Framework.FLASK
        assert fw.confidence == 0.8
        assert fw.version == "2.0.0"
        assert len(fw.evidence) == 2

    def test_project_info_to_dict(self, temp_dir):
        """Test ProjectInfo.to_dict() method."""
        info = ProjectInfo(
            path=temp_dir,
            primary_language=Language.PYTHON,
            primary_type=ProjectType.API_SERVICE,
            languages=[DetectedLanguage(Language.PYTHON, 0.9, 10, ["app.py"])],
            frameworks=[DetectedFramework(Framework.FLASK, 0.8, "2.0.0", ["flask"])],
            package_managers=[PackageManager.PIP],
            build_tools=[BuildTool.DOCKER],
            language_confidence=0.9,
            type_confidence=0.7,
            name="test",
            version="1.0.0",
            description="Test project",
            is_monorepo=False,
            subprojects=[],
        )

        d = info.to_dict()

        assert d["path"] == str(temp_dir)
        assert d["primary_language"] == "python"
        assert d["primary_type"] == "api_service"
        assert d["language_confidence"] == 0.9
        assert d["name"] == "test"
        assert len(d["languages"]) == 1
        assert len(d["frameworks"]) == 1
        assert "pip" in d["package_managers"]


# =============================================================================
# PROJECT DETECTOR TESTS
# =============================================================================


class TestProjectDetector:
    """Tests for ProjectDetector class."""

    def test_init_defaults(self):
        """Test detector initialization with defaults."""
        detector = ProjectDetector()
        assert detector.max_depth == 3
        assert detector.max_files == 1000

    def test_init_custom(self):
        """Test detector initialization with custom values."""
        detector = ProjectDetector(max_depth=5, max_files=500)
        assert detector.max_depth == 5
        assert detector.max_files == 500

    def test_detect_nonexistent_path(self):
        """Test detection with nonexistent path."""
        detector = ProjectDetector()

        with pytest.raises(ValueError) as exc_info:
            detector.detect(Path("/nonexistent/path"))

        assert "does not exist" in str(exc_info.value)

    def test_detect_file_not_directory(self, temp_dir):
        """Test detection with file instead of directory."""
        file_path = temp_dir / "test.txt"
        file_path.write_text("test")

        detector = ProjectDetector()

        with pytest.raises(ValueError) as exc_info:
            detector.detect(file_path)

        assert "not a directory" in str(exc_info.value)


class TestPythonProjectDetection:
    """Tests for Python project detection."""

    def test_detect_python_project(self, python_project):
        """Test detection of Python project."""
        info = detect_project(python_project)

        assert info.primary_language == Language.PYTHON
        assert info.language_confidence > 0.5
        assert info.name == "test-project"
        assert info.version == "1.0.0"

    def test_detect_flask_framework(self, python_project):
        """Test detection of Flask framework."""
        info = detect_project(python_project)

        flask_frameworks = [f for f in info.frameworks if f.framework == Framework.FLASK]
        assert len(flask_frameworks) > 0
        assert flask_frameworks[0].confidence > 0.5

    def test_detect_pip_package_manager(self, python_project):
        """Test detection of pip package manager."""
        info = detect_project(python_project)

        assert PackageManager.PIP in info.package_managers


class TestJavaScriptProjectDetection:
    """Tests for JavaScript project detection."""

    def test_detect_javascript_project(self, javascript_project):
        """Test detection of JavaScript project."""
        info = detect_project(javascript_project)

        # Should detect JavaScript or TypeScript
        js_langs = [Language.JAVASCRIPT, Language.TYPESCRIPT]
        assert info.primary_language in js_langs

    def test_detect_react_framework(self, javascript_project):
        """Test detection of React framework."""
        info = detect_project(javascript_project)

        react_frameworks = [f for f in info.frameworks if f.framework == Framework.REACT]
        assert len(react_frameworks) > 0

    def test_detect_npm_package_manager(self, javascript_project):
        """Test detection of npm package manager."""
        info = detect_project(javascript_project)

        assert PackageManager.NPM in info.package_managers

    def test_detect_vite_build_tool(self, javascript_project):
        """Test detection of Vite build tool."""
        info = detect_project(javascript_project)

        assert BuildTool.VITE in info.build_tools


class TestRustProjectDetection:
    """Tests for Rust project detection."""

    def test_detect_rust_project(self, rust_project):
        """Test detection of Rust project."""
        info = detect_project(rust_project)

        assert info.primary_language == Language.RUST
        assert info.name == "rust-cli"

    def test_detect_cargo_package_manager(self, rust_project):
        """Test detection of Cargo package manager."""
        info = detect_project(rust_project)

        assert PackageManager.CARGO in info.package_managers


class TestMonorepoDetection:
    """Tests for monorepo detection."""

    def test_detect_monorepo(self, monorepo_project):
        """Test detection of monorepo."""
        info = detect_project(monorepo_project)

        assert info.is_monorepo is True
        assert len(info.subprojects) >= 2

    def test_detect_pnpm_in_monorepo(self, monorepo_project):
        """Test detection of pnpm in monorepo."""
        info = detect_project(monorepo_project)

        assert PackageManager.PNPM in info.package_managers


# =============================================================================
# PROJECT TYPE DETECTION TESTS
# =============================================================================


class TestProjectTypeDetection:
    """Tests for project type detection."""

    def test_web_app_detection(self, javascript_project):
        """Test web app type detection."""
        info = detect_project(javascript_project)

        assert info.primary_type == ProjectType.WEB_APP

    def test_library_detection(self, temp_dir):
        """Test library type detection."""
        # Create library structure
        src = temp_dir / "src"
        src.mkdir()
        (src / "lib.py").write_text("def helper(): pass")

        tests = temp_dir / "tests"
        tests.mkdir()
        (tests / "test_lib.py").write_text("def test_helper(): pass")

        (temp_dir / "pyproject.toml").write_text("""
[project]
name = "my-lib"
version = "0.1.0"
""")

        info = detect_project(temp_dir)

        assert info.primary_type == ProjectType.LIBRARY


class TestConvenienceFunction:
    """Tests for detect_project convenience function."""

    def test_detect_project_function(self, python_project):
        """Test detect_project function."""
        info = detect_project(python_project)

        assert isinstance(info, ProjectInfo)
        # Resolve both paths to handle macOS /var -> /private/var symlink
        assert info.path == python_project.resolve()

    def test_detect_project_default_path(self):
        """Test detect_project with default path (current directory)."""
        # Should work without error
        info = detect_project()

        assert isinstance(info, ProjectInfo)
        assert info.path.exists()


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_directory(self, temp_dir):
        """Test detection in empty directory."""
        info = detect_project(temp_dir)

        assert info.primary_language == Language.UNKNOWN
        assert info.primary_type == ProjectType.UNKNOWN
        assert len(info.languages) == 0
        assert len(info.frameworks) == 0

    def test_hidden_files_ignored(self, temp_dir):
        """Test that hidden files are ignored."""
        # Create hidden directory with files
        hidden = temp_dir / ".hidden"
        hidden.mkdir()
        (hidden / "secret.py").write_text("pass")

        # Create visible Python file
        (temp_dir / "app.py").write_text("pass")

        info = detect_project(temp_dir)

        # Should only find the visible file
        python_lang = next((l for l in info.languages if l.language == Language.PYTHON), None)
        if python_lang:
            assert "hidden" not in str(python_lang.evidence)

    def test_node_modules_ignored(self, temp_dir):
        """Test that node_modules is ignored."""
        # Create package.json
        (temp_dir / "package.json").write_text('{"name": "test"}')

        # Create node_modules with many files
        node_modules = temp_dir / "node_modules"
        node_modules.mkdir()
        for i in range(100):
            (node_modules / f"file{i}.js").write_text("module.exports = {}")

        # Create source file
        (temp_dir / "index.js").write_text("console.log('hello')")

        detector = ProjectDetector(max_files=50)
        info = detector.detect(temp_dir)

        # Should not have scanned all node_modules files
        js_lang = next((l for l in info.languages if l.language == Language.JAVASCRIPT), None)
        if js_lang:
            assert js_lang.file_count < 10

    def test_max_depth_respected(self, temp_dir):
        """Test that max_depth is respected."""
        # Create deeply nested structure
        current = temp_dir
        for i in range(10):
            current = current / f"level{i}"
            current.mkdir()
            (current / f"file{i}.py").write_text("pass")

        detector = ProjectDetector(max_depth=2)
        info = detector.detect(temp_dir)

        # Should not have found files deeper than max_depth
        python_lang = next((l for l in info.languages if l.language == Language.PYTHON), None)
        if python_lang:
            assert python_lang.file_count <= 3  # level0, level1, level2

    def test_max_files_respected(self, temp_dir):
        """Test that max_files is respected."""
        # Create many files
        for i in range(100):
            (temp_dir / f"file{i}.py").write_text("pass")

        detector = ProjectDetector(max_files=10)
        info = detector.detect(temp_dir)

        # Should have stopped at max_files
        total_files = sum(l.file_count for l in info.languages)
        assert total_files <= 10
