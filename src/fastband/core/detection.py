"""
Project detection system.

Automatically detects project type, language, frameworks, and build tools
based on directory contents.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class Language(Enum):
    """Programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    KOTLIN = "kotlin"
    SWIFT = "swift"
    CSHARP = "csharp"
    CPP = "cpp"
    C = "c"
    RUBY = "ruby"
    PHP = "php"
    DART = "dart"
    UNKNOWN = "unknown"


class ProjectType(Enum):
    """Project types."""

    WEB_APP = "web_app"
    API_SERVICE = "api_service"
    MOBILE_IOS = "mobile_ios"
    MOBILE_ANDROID = "mobile_android"
    MOBILE_CROSS = "mobile_cross_platform"
    DESKTOP_ELECTRON = "desktop_electron"
    DESKTOP_NATIVE = "desktop_native"
    CLI_TOOL = "cli_tool"
    LIBRARY = "library"
    MONOREPO = "monorepo"
    UNKNOWN = "unknown"


class Framework(Enum):
    """Frameworks and libraries."""

    # Python
    FLASK = "flask"
    DJANGO = "django"
    FASTAPI = "fastapi"
    PYTEST = "pytest"

    # JavaScript/TypeScript
    REACT = "react"
    VUE = "vue"
    ANGULAR = "angular"
    SVELTE = "svelte"
    NEXTJS = "nextjs"
    NUXT = "nuxt"
    EXPRESS = "express"
    NESTJS = "nestjs"

    # Mobile
    REACT_NATIVE = "react_native"
    FLUTTER = "flutter"
    SWIFTUI = "swiftui"
    JETPACK_COMPOSE = "jetpack_compose"

    # Desktop
    ELECTRON = "electron"
    TAURI = "tauri"
    QT = "qt"

    # Other
    SPRING = "spring"
    RAILS = "rails"
    LARAVEL = "laravel"


class PackageManager(Enum):
    """Package managers."""

    PIP = "pip"
    POETRY = "poetry"
    PIPENV = "pipenv"
    CONDA = "conda"
    UV = "uv"
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    BUN = "bun"
    CARGO = "cargo"
    GO_MOD = "go_mod"
    MAVEN = "maven"
    GRADLE = "gradle"
    COCOAPODS = "cocoapods"
    SPM = "swift_package_manager"
    PUB = "pub"
    COMPOSER = "composer"
    BUNDLER = "bundler"
    NUGET = "nuget"


class BuildTool(Enum):
    """Build tools."""

    SETUPTOOLS = "setuptools"
    WEBPACK = "webpack"
    VITE = "vite"
    ESBUILD = "esbuild"
    ROLLUP = "rollup"
    PARCEL = "parcel"
    TURBOPACK = "turbopack"
    MAKE = "make"
    CMAKE = "cmake"
    BAZEL = "bazel"
    GRADLE = "gradle"
    MAVEN = "maven"
    XCODEBUILD = "xcodebuild"
    DOCKER = "docker"


@dataclass
class DetectedFramework:
    """A detected framework with confidence."""

    framework: Framework
    confidence: float  # 0.0 to 1.0
    version: str | None = None
    evidence: list[str] = field(default_factory=list)


@dataclass
class DetectedLanguage:
    """A detected language with confidence."""

    language: Language
    confidence: float
    file_count: int = 0
    evidence: list[str] = field(default_factory=list)


@dataclass
class ProjectInfo:
    """
    Complete project detection result.

    Contains detected languages, project type, frameworks, package managers,
    and build tools with confidence scores.
    """

    path: Path

    # Primary detection
    primary_language: Language
    primary_type: ProjectType

    # All detected items with confidence
    languages: list[DetectedLanguage] = field(default_factory=list)
    frameworks: list[DetectedFramework] = field(default_factory=list)
    package_managers: list[PackageManager] = field(default_factory=list)
    build_tools: list[BuildTool] = field(default_factory=list)

    # Confidence for primary detection
    language_confidence: float = 0.0
    type_confidence: float = 0.0

    # Project metadata
    name: str | None = None
    version: str | None = None
    description: str | None = None

    # Monorepo detection
    is_monorepo: bool = False
    subprojects: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "path": str(self.path),
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "primary_language": self.primary_language.value,
            "primary_type": self.primary_type.value,
            "language_confidence": self.language_confidence,
            "type_confidence": self.type_confidence,
            "languages": [
                {
                    "language": l.language.value,
                    "confidence": l.confidence,
                    "file_count": l.file_count,
                }
                for l in self.languages
            ],
            "frameworks": [
                {
                    "framework": f.framework.value,
                    "confidence": f.confidence,
                    "version": f.version,
                }
                for f in self.frameworks
            ],
            "package_managers": [pm.value for pm in self.package_managers],
            "build_tools": [bt.value for bt in self.build_tools],
            "is_monorepo": self.is_monorepo,
            "subprojects": self.subprojects,
        }


# Detection patterns
LANGUAGE_PATTERNS: dict[Language, dict] = {
    Language.PYTHON: {
        "extensions": [".py", ".pyi", ".pyx"],
        "files": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"],
    },
    Language.JAVASCRIPT: {
        "extensions": [".js", ".mjs", ".cjs"],
        "files": ["package.json"],
    },
    Language.TYPESCRIPT: {
        "extensions": [".ts", ".tsx", ".mts", ".cts"],
        "files": ["tsconfig.json", "package.json"],
    },
    Language.RUST: {
        "extensions": [".rs"],
        "files": ["Cargo.toml", "Cargo.lock"],
    },
    Language.GO: {
        "extensions": [".go"],
        "files": ["go.mod", "go.sum"],
    },
    Language.JAVA: {
        "extensions": [".java"],
        "files": ["pom.xml", "build.gradle", "build.gradle.kts"],
    },
    Language.KOTLIN: {
        "extensions": [".kt", ".kts"],
        "files": ["build.gradle.kts"],
    },
    Language.SWIFT: {
        "extensions": [".swift"],
        "files": ["Package.swift", "*.xcodeproj", "*.xcworkspace"],
    },
    Language.CSHARP: {
        "extensions": [".cs"],
        "files": ["*.csproj", "*.sln"],
    },
    Language.CPP: {
        "extensions": [".cpp", ".cc", ".cxx", ".hpp", ".h"],
        "files": ["CMakeLists.txt", "Makefile"],
    },
    Language.RUBY: {
        "extensions": [".rb"],
        "files": ["Gemfile", "Rakefile", "*.gemspec"],
    },
    Language.PHP: {
        "extensions": [".php"],
        "files": ["composer.json"],
    },
    Language.DART: {
        "extensions": [".dart"],
        "files": ["pubspec.yaml"],
    },
}

FRAMEWORK_PATTERNS: dict[Framework, dict] = {
    # Python frameworks
    Framework.FLASK: {
        "dependencies": ["flask"],
        "files": ["app.py", "wsgi.py"],
        "imports": ["from flask", "import flask"],
    },
    Framework.DJANGO: {
        "dependencies": ["django"],
        "files": ["manage.py", "settings.py"],
        "dirs": ["templates", "static"],
    },
    Framework.FASTAPI: {
        "dependencies": ["fastapi"],
        "imports": ["from fastapi", "import fastapi"],
    },
    # JavaScript frameworks
    Framework.REACT: {
        "dependencies": ["react", "react-dom"],
        "files": ["*.jsx", "*.tsx"],
    },
    Framework.VUE: {
        "dependencies": ["vue"],
        "files": ["*.vue", "vue.config.js"],
    },
    Framework.ANGULAR: {
        "dependencies": ["@angular/core"],
        "files": ["angular.json"],
    },
    Framework.SVELTE: {
        "dependencies": ["svelte"],
        "files": ["svelte.config.js", "*.svelte"],
    },
    Framework.NEXTJS: {
        "dependencies": ["next"],
        "files": ["next.config.js", "next.config.mjs"],
        "dirs": ["pages", "app"],
    },
    Framework.EXPRESS: {
        "dependencies": ["express"],
    },
    Framework.NESTJS: {
        "dependencies": ["@nestjs/core"],
        "files": ["nest-cli.json"],
    },
    # Mobile frameworks
    Framework.REACT_NATIVE: {
        "dependencies": ["react-native"],
        "files": ["metro.config.js", "app.json"],
    },
    Framework.FLUTTER: {
        "dependencies": ["flutter"],
        "files": ["pubspec.yaml"],
        "dirs": ["lib", "android", "ios"],
    },
    # Desktop frameworks
    Framework.ELECTRON: {
        "dependencies": ["electron"],
        "files": ["electron.js", "main.js"],
    },
    Framework.TAURI: {
        "dependencies": ["@tauri-apps/api"],
        "files": ["tauri.conf.json"],
        "dirs": ["src-tauri"],
    },
}

PACKAGE_MANAGER_FILES: dict[str, PackageManager] = {
    "pyproject.toml": PackageManager.POETRY,  # Could also be pip
    "Pipfile": PackageManager.PIPENV,
    "requirements.txt": PackageManager.PIP,
    "environment.yml": PackageManager.CONDA,
    "uv.lock": PackageManager.UV,
    "package-lock.json": PackageManager.NPM,
    "yarn.lock": PackageManager.YARN,
    "pnpm-lock.yaml": PackageManager.PNPM,
    "bun.lockb": PackageManager.BUN,
    "Cargo.toml": PackageManager.CARGO,
    "go.mod": PackageManager.GO_MOD,
    "pom.xml": PackageManager.MAVEN,
    "build.gradle": PackageManager.GRADLE,
    "build.gradle.kts": PackageManager.GRADLE,
    "Podfile": PackageManager.COCOAPODS,
    "Package.swift": PackageManager.SPM,
    "pubspec.yaml": PackageManager.PUB,
    "composer.json": PackageManager.COMPOSER,
    "Gemfile": PackageManager.BUNDLER,
}

BUILD_TOOL_FILES: dict[str, BuildTool] = {
    "webpack.config.js": BuildTool.WEBPACK,
    "vite.config.js": BuildTool.VITE,
    "vite.config.ts": BuildTool.VITE,
    "rollup.config.js": BuildTool.ROLLUP,
    "esbuild.config.js": BuildTool.ESBUILD,
    "Makefile": BuildTool.MAKE,
    "CMakeLists.txt": BuildTool.CMAKE,
    "BUILD": BuildTool.BAZEL,
    "WORKSPACE": BuildTool.BAZEL,
    "Dockerfile": BuildTool.DOCKER,
    "docker-compose.yml": BuildTool.DOCKER,
    "docker-compose.yaml": BuildTool.DOCKER,
}


class ProjectDetector:
    """
    Detects project type, language, frameworks, and tools.

    Example:
        detector = ProjectDetector()
        info = detector.detect("/path/to/project")

        print(f"Language: {info.primary_language.value}")
        print(f"Type: {info.primary_type.value}")
        for fw in info.frameworks:
            print(f"Framework: {fw.framework.value} ({fw.confidence:.0%})")
    """

    def __init__(self, max_depth: int = 3, max_files: int = 1000):
        """
        Initialize detector.

        Args:
            max_depth: Maximum directory depth to scan
            max_files: Maximum number of files to scan
        """
        self.max_depth = max_depth
        self.max_files = max_files

    def detect(self, path: Path | None = None) -> ProjectInfo:
        """
        Detect project information.

        Args:
            path: Project root path (default: current directory)

        Returns:
            ProjectInfo with detection results
        """
        if path is None:
            path = Path.cwd()
        path = Path(path).resolve()

        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")

        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")

        logger.info(f"Detecting project at: {path}")

        # Collect files
        files = self._collect_files(path)

        # Detect components
        languages = self._detect_languages(path, files)
        package_managers = self._detect_package_managers(path)
        build_tools = self._detect_build_tools(path)
        frameworks = self._detect_frameworks(path, files, package_managers)

        # Determine primary language and type
        primary_language, lang_confidence = self._get_primary_language(languages)
        primary_type, type_confidence = self._detect_project_type(
            path, primary_language, frameworks, files
        )

        # Get project metadata
        name, version, description = self._get_project_metadata(path, package_managers)

        # Detect monorepo
        is_monorepo, subprojects = self._detect_monorepo(path)

        return ProjectInfo(
            path=path,
            primary_language=primary_language,
            primary_type=primary_type,
            languages=languages,
            frameworks=frameworks,
            package_managers=package_managers,
            build_tools=build_tools,
            language_confidence=lang_confidence,
            type_confidence=type_confidence,
            name=name,
            version=version,
            description=description,
            is_monorepo=is_monorepo,
            subprojects=subprojects,
        )

    def _collect_files(self, path: Path) -> list[Path]:
        """Collect files up to max_depth and max_files."""
        files = []
        count = 0

        def walk(current: Path, depth: int):
            nonlocal count
            if depth > self.max_depth or count >= self.max_files:
                return

            try:
                for item in current.iterdir():
                    if count >= self.max_files:
                        return

                    # Skip hidden and common ignore patterns
                    if item.name.startswith(".") or item.name in {
                        "node_modules",
                        "__pycache__",
                        "venv",
                        ".venv",
                        "env",
                        ".env",
                        "dist",
                        "build",
                        "target",
                        ".git",
                    }:
                        continue

                    if item.is_file():
                        files.append(item)
                        count += 1
                    elif item.is_dir():
                        walk(item, depth + 1)
            except PermissionError:
                pass

        walk(path, 0)
        return files

    def _detect_languages(self, path: Path, files: list[Path]) -> list[DetectedLanguage]:
        """Detect programming languages."""
        language_files: dict[Language, list[Path]] = {lang: [] for lang in Language}

        for file in files:
            ext = file.suffix.lower()
            for lang, patterns in LANGUAGE_PATTERNS.items():
                if ext in patterns.get("extensions", []):
                    language_files[lang].append(file)

        # Also check for indicator files
        for lang, patterns in LANGUAGE_PATTERNS.items():
            for indicator in patterns.get("files", []):
                if "*" in indicator:
                    # Glob pattern
                    matches = list(path.glob(indicator))
                    if matches:
                        language_files[lang].extend(matches)
                elif (path / indicator).exists():
                    language_files[lang].append(path / indicator)

        # Calculate confidence based on file count
        total_files = sum(len(f) for f in language_files.values()) or 1

        results = []
        for lang, lang_files in language_files.items():
            if lang_files:
                count = len(lang_files)
                confidence = min(count / total_files + 0.1, 1.0)
                results.append(
                    DetectedLanguage(
                        language=lang,
                        confidence=confidence,
                        file_count=count,
                        evidence=[str(f.relative_to(path)) for f in lang_files[:5]],
                    )
                )

        # Sort by confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    def _detect_package_managers(self, path: Path) -> list[PackageManager]:
        """Detect package managers."""
        managers = []

        for filename, manager in PACKAGE_MANAGER_FILES.items():
            if (path / filename).exists():
                if manager not in managers:
                    managers.append(manager)

        # Check pyproject.toml for poetry vs pip
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                if "[tool.poetry]" in content:
                    if PackageManager.POETRY not in managers:
                        managers.append(PackageManager.POETRY)
                elif "[project]" in content or "[build-system]" in content:
                    if PackageManager.PIP not in managers:
                        managers.append(PackageManager.PIP)
            except Exception:
                pass

        return managers

    def _detect_build_tools(self, path: Path) -> list[BuildTool]:
        """Detect build tools."""
        tools = []

        for filename, tool in BUILD_TOOL_FILES.items():
            if (path / filename).exists():
                if tool not in tools:
                    tools.append(tool)

        return tools

    def _detect_frameworks(
        self,
        path: Path,
        files: list[Path],
        package_managers: list[PackageManager],
    ) -> list[DetectedFramework]:
        """Detect frameworks."""
        frameworks = []
        dependencies = self._get_dependencies(path, package_managers)

        for framework, patterns in FRAMEWORK_PATTERNS.items():
            confidence = 0.0
            evidence = []
            version = None

            # Check dependencies
            dep_names = patterns.get("dependencies", [])
            for dep in dep_names:
                if dep in dependencies:
                    confidence += 0.6
                    evidence.append(f"dependency: {dep}")
                    version = dependencies.get(dep)
                    break

            # Check files
            file_patterns = patterns.get("files", [])
            for pattern in file_patterns:
                if "*" in pattern:
                    if list(path.glob(pattern)):
                        confidence += 0.2
                        evidence.append(f"file pattern: {pattern}")
                elif (path / pattern).exists():
                    confidence += 0.2
                    evidence.append(f"file: {pattern}")

            # Check directories
            dir_patterns = patterns.get("dirs", [])
            for dir_name in dir_patterns:
                if (path / dir_name).is_dir():
                    confidence += 0.1
                    evidence.append(f"directory: {dir_name}")

            if confidence > 0:
                frameworks.append(
                    DetectedFramework(
                        framework=framework,
                        confidence=min(confidence, 1.0),
                        version=version,
                        evidence=evidence,
                    )
                )

        # Sort by confidence
        frameworks.sort(key=lambda x: x.confidence, reverse=True)
        return frameworks

    def _get_dependencies(
        self, path: Path, package_managers: list[PackageManager]
    ) -> dict[str, str | None]:
        """Get project dependencies."""
        deps: dict[str, str | None] = {}

        # package.json
        pkg_json = path / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                for key in ["dependencies", "devDependencies", "peerDependencies"]:
                    if key in data:
                        for name, version in data[key].items():
                            deps[name] = version
            except Exception:
                pass

        # pyproject.toml (basic parsing)
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                # Simple extraction - look for dependencies
                in_deps = False
                for line in content.split("\n"):
                    if "dependencies" in line.lower() and "=" in line:
                        in_deps = True
                        continue
                    if in_deps:
                        if line.startswith("["):
                            in_deps = False
                            continue
                        if "=" in line or line.strip().startswith('"'):
                            # Extract package name
                            clean = line.strip().strip('",')
                            if clean:
                                parts = clean.split(">=")[0].split("==")[0].split("<")[0]
                                deps[parts.strip()] = None
            except Exception:
                pass

        # requirements.txt
        req_txt = path / "requirements.txt"
        if req_txt.exists():
            try:
                for line in req_txt.read_text().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Parse package==version or package>=version
                        for sep in ["==", ">=", "<=", ">", "<", "~="]:
                            if sep in line:
                                name, version = line.split(sep, 1)
                                deps[name.strip()] = version.strip()
                                break
                        else:
                            deps[line.split("[")[0].strip()] = None
            except Exception:
                pass

        return deps

    def _get_primary_language(self, languages: list[DetectedLanguage]) -> tuple[Language, float]:
        """Get primary language."""
        if not languages:
            return Language.UNKNOWN, 0.0

        primary = languages[0]
        return primary.language, primary.confidence

    def _detect_project_type(
        self,
        path: Path,
        language: Language,
        frameworks: list[DetectedFramework],
        files: list[Path],
    ) -> tuple[ProjectType, float]:
        """Detect project type."""

        framework_names = {f.framework for f in frameworks}

        # Check for mobile
        if Framework.REACT_NATIVE in framework_names:
            return ProjectType.MOBILE_CROSS, 0.9
        if Framework.FLUTTER in framework_names:
            return ProjectType.MOBILE_CROSS, 0.9
        if language == Language.SWIFT and (path / "*.xcodeproj").exists():
            return ProjectType.MOBILE_IOS, 0.8
        if (path / "android").is_dir() and (path / "app/build.gradle").exists():
            return ProjectType.MOBILE_ANDROID, 0.8

        # Check for desktop
        if Framework.ELECTRON in framework_names:
            return ProjectType.DESKTOP_ELECTRON, 0.9
        if Framework.TAURI in framework_names:
            return ProjectType.DESKTOP_NATIVE, 0.9

        # Check for web app
        web_frameworks = {
            Framework.REACT,
            Framework.VUE,
            Framework.ANGULAR,
            Framework.SVELTE,
            Framework.NEXTJS,
            Framework.NUXT,
        }
        if framework_names & web_frameworks:
            return ProjectType.WEB_APP, 0.8

        # Check for API service
        api_frameworks = {
            Framework.FLASK,
            Framework.DJANGO,
            Framework.FASTAPI,
            Framework.EXPRESS,
            Framework.NESTJS,
        }
        if framework_names & api_frameworks:
            # Could be web app or API
            has_templates = (path / "templates").is_dir() or (path / "views").is_dir()
            if has_templates:
                return ProjectType.WEB_APP, 0.7
            return ProjectType.API_SERVICE, 0.7

        # Check for CLI tool
        if (path / "cli.py").exists() or (path / "bin").is_dir():
            return ProjectType.CLI_TOOL, 0.6

        # Check for library
        if (path / "src").is_dir() and (path / "tests").is_dir():
            return ProjectType.LIBRARY, 0.5

        return ProjectType.UNKNOWN, 0.3

    def _get_project_metadata(
        self, path: Path, package_managers: list[PackageManager]
    ) -> tuple[str | None, str | None, str | None]:
        """Get project name, version, description."""
        name = None
        version = None
        description = None

        # Try package.json
        pkg_json = path / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                name = data.get("name")
                version = data.get("version")
                description = data.get("description")
            except Exception:
                pass

        # Try pyproject.toml
        if not name:
            pyproject = path / "pyproject.toml"
            if pyproject.exists():
                try:
                    content = pyproject.read_text()
                    for line in content.split("\n"):
                        if line.startswith("name ="):
                            name = line.split("=")[1].strip().strip("\"'")
                        elif line.startswith("version ="):
                            version = line.split("=")[1].strip().strip("\"'")
                        elif line.startswith("description ="):
                            description = line.split("=")[1].strip().strip("\"'")
                except Exception:
                    pass

        # Try Cargo.toml
        if not name:
            cargo = path / "Cargo.toml"
            if cargo.exists():
                try:
                    content = cargo.read_text()
                    in_package = False
                    for line in content.split("\n"):
                        if line.strip() == "[package]":
                            in_package = True
                            continue
                        if in_package:
                            if line.startswith("["):
                                break
                            if line.startswith("name ="):
                                name = line.split("=")[1].strip().strip("\"'")
                            elif line.startswith("version ="):
                                version = line.split("=")[1].strip().strip("\"'")
                            elif line.startswith("description ="):
                                description = line.split("=")[1].strip().strip("\"'")
                except Exception:
                    pass

        # Fall back to directory name
        if not name:
            name = path.name

        return name, version, description

    def _detect_monorepo(self, path: Path) -> tuple[bool, list[str]]:
        """Detect if project is a monorepo."""
        subprojects = []

        # Check for common monorepo patterns
        monorepo_dirs = ["packages", "apps", "libs", "modules", "services"]

        for dir_name in monorepo_dirs:
            packages_dir = path / dir_name
            if packages_dir.is_dir():
                for item in packages_dir.iterdir():
                    if item.is_dir():
                        # Check if it looks like a package
                        if any(
                            (item / f).exists()
                            for f in [
                                "package.json",
                                "pyproject.toml",
                                "Cargo.toml",
                                "setup.py",
                                "go.mod",
                            ]
                        ):
                            subprojects.append(f"{dir_name}/{item.name}")

        # Check for workspace files
        if (path / "pnpm-workspace.yaml").exists():
            return True, subprojects
        if (path / "lerna.json").exists():
            return True, subprojects

        pkg_json = path / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                if "workspaces" in data:
                    return True, subprojects
            except Exception:
                pass

        return len(subprojects) > 1, subprojects


# Convenience function
def detect_project(path: Path | None = None) -> ProjectInfo:
    """
    Detect project information.

    Args:
        path: Project root path (default: current directory)

    Returns:
        ProjectInfo with detection results
    """
    detector = ProjectDetector()
    return detector.detect(path)
