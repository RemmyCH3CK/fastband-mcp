"""
AI-Powered Agent Bible Generator.

Analyzes the codebase using AI to generate a context-aware AGENT_BIBLE.md
that reflects the project's actual patterns, conventions, and architecture.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Try to import AI providers
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


@dataclass
class CodebaseAnalysis:
    """Results of codebase analysis."""

    project_name: str
    root_path: Path
    primary_language: str
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    file_structure: dict[str, Any] = field(default_factory=dict)
    key_files: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    test_patterns: list[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Convert analysis to prompt context string."""
        return f"""
PROJECT ANALYSIS:
================
Project Name: {self.project_name}
Root Path: {self.root_path}
Primary Language: {self.primary_language}
Languages Detected: {', '.join(self.languages)}
Frameworks/Libraries: {', '.join(self.frameworks)}

KEY FILES:
{chr(10).join(f'- {f}' for f in self.key_files[:30])}

CONFIG FILES:
{chr(10).join(f'- {f}' for f in self.config_files)}

FILE STRUCTURE (top-level):
{json.dumps(self.file_structure, indent=2)}

DETECTED PATTERNS:
{chr(10).join(f'- {p}' for p in self.patterns)}

TEST PATTERNS:
{chr(10).join(f'- {p}' for p in self.test_patterns)}
"""


class CodebaseAnalyzer:
    """Analyzes a codebase to extract structure and patterns."""

    # Common framework indicators
    FRAMEWORK_INDICATORS = {
        'fastapi': ['fastapi', 'uvicorn', 'starlette'],
        'flask': ['flask', 'werkzeug', 'jinja2'],
        'django': ['django', 'wsgi', 'asgi'],
        'react': ['react', 'jsx', 'tsx', 'create-react-app'],
        'vue': ['vue', '.vue', 'vuex'],
        'nextjs': ['next.config', 'pages/', 'app/'],
        'express': ['express', 'node_modules'],
        'pytorch': ['torch', 'pytorch'],
        'tensorflow': ['tensorflow', 'keras'],
        'pytest': ['pytest', 'conftest.py'],
    }

    # Language extensions
    LANGUAGE_EXTENSIONS = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript/React',
        '.jsx': 'JavaScript/React',
        '.go': 'Go',
        '.rs': 'Rust',
        '.java': 'Java',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        '.cs': 'C#',
        '.cpp': 'C++',
        '.c': 'C',
    }

    # Skip these directories
    SKIP_DIRS = {
        '__pycache__', 'node_modules', '.git', '.venv', 'venv',
        'env', '.env', 'dist', 'build', '.next', '.nuxt',
        'target', 'vendor', '.cache', '.pytest_cache',
    }

    def __init__(self, project_path: Path):
        self.project_path = project_path

    def analyze(self) -> CodebaseAnalysis:
        """Perform full codebase analysis."""
        project_name = self.project_path.name

        # Collect all files
        all_files = self._collect_files()

        # Detect languages
        languages = self._detect_languages(all_files)
        primary_language = languages[0] if languages else 'Unknown'

        # Detect frameworks
        frameworks = self._detect_frameworks(all_files)

        # Get file structure
        file_structure = self._get_file_structure()

        # Find key files
        key_files = self._find_key_files(all_files)

        # Find config files
        config_files = self._find_config_files(all_files)

        # Detect patterns
        patterns = self._detect_patterns(all_files)

        # Find test patterns
        test_patterns = self._detect_test_patterns(all_files)

        return CodebaseAnalysis(
            project_name=project_name,
            root_path=self.project_path,
            primary_language=primary_language,
            languages=languages,
            frameworks=frameworks,
            file_structure=file_structure,
            key_files=key_files,
            patterns=patterns,
            config_files=config_files,
            test_patterns=test_patterns,
        )

    def _collect_files(self) -> list[Path]:
        """Collect all files in the project."""
        files = []
        for path in self.project_path.rglob('*'):
            if path.is_file():
                # Skip hidden and ignored directories
                parts = path.relative_to(self.project_path).parts
                if any(p in self.SKIP_DIRS or p.startswith('.') for p in parts):
                    continue
                files.append(path)
        return files

    def _detect_languages(self, files: list[Path]) -> list[str]:
        """Detect programming languages used."""
        lang_counts: dict[str, int] = {}
        for f in files:
            ext = f.suffix.lower()
            if ext in self.LANGUAGE_EXTENSIONS:
                lang = self.LANGUAGE_EXTENSIONS[ext]
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

        # Sort by count
        return sorted(lang_counts.keys(), key=lambda x: lang_counts[x], reverse=True)

    def _detect_frameworks(self, files: list[Path]) -> list[str]:
        """Detect frameworks and libraries used."""
        detected = set()
        file_contents_cache: dict[str, str] = {}

        # Check file names and contents
        for f in files:
            fname = f.name.lower()

            # Check common config files
            if fname in ['requirements.txt', 'pyproject.toml', 'package.json', 'go.mod', 'Cargo.toml']:
                try:
                    content = f.read_text(errors='ignore').lower()
                    file_contents_cache[str(f)] = content

                    for framework, indicators in self.FRAMEWORK_INDICATORS.items():
                        if any(ind.lower() in content for ind in indicators):
                            detected.add(framework)
                except Exception:
                    pass

        return sorted(detected)

    def _get_file_structure(self, max_depth: int = 2) -> dict[str, Any]:
        """Get simplified file structure."""
        structure: dict[str, Any] = {}

        for item in self.project_path.iterdir():
            if item.name.startswith('.') or item.name in self.SKIP_DIRS:
                continue

            if item.is_dir():
                # Get subdirectory contents (one level)
                subfiles = []
                try:
                    for sub in item.iterdir():
                        if not sub.name.startswith('.'):
                            subfiles.append(sub.name)
                except PermissionError:
                    pass
                structure[item.name + '/'] = subfiles[:10]  # Limit
            else:
                structure[item.name] = 'file'

        return structure

    def _find_key_files(self, files: list[Path]) -> list[str]:
        """Find important files in the codebase."""
        key_patterns = [
            'main.py', 'app.py', 'index.py', 'server.py',
            'main.js', 'index.js', 'app.js', 'server.js',
            'main.ts', 'index.ts', 'app.ts',
            'main.go', 'main.rs',
            '__init__.py', 'cli.py', 'api.py', 'routes.py',
            'models.py', 'schema.py', 'database.py',
            'setup.py', 'pyproject.toml', 'package.json',
            'Dockerfile', 'docker-compose.yml',
            'Makefile', 'README.md', 'CONTRIBUTING.md',
        ]

        found = []
        for f in files:
            rel_path = str(f.relative_to(self.project_path))
            if f.name in key_patterns:
                found.append(rel_path)

        return sorted(found)[:30]

    def _find_config_files(self, files: list[Path]) -> list[str]:
        """Find configuration files."""
        config_patterns = [
            '.env', '.env.example', 'config.py', 'settings.py',
            'pyproject.toml', 'setup.py', 'setup.cfg',
            'package.json', 'tsconfig.json', 'vite.config',
            'webpack.config', '.prettierrc', '.eslintrc',
            'Dockerfile', 'docker-compose', '.dockerignore',
            'Makefile', 'Justfile', '.github/',
            'pytest.ini', 'tox.ini', 'mypy.ini',
        ]

        found = []
        for f in files:
            fname = f.name.lower()
            if any(pat.lower() in fname for pat in config_patterns):
                found.append(str(f.relative_to(self.project_path)))

        return sorted(set(found))[:20]

    def _detect_patterns(self, files: list[Path]) -> list[str]:
        """Detect architectural patterns."""
        patterns = []

        # Check for common patterns
        file_names = [f.name.lower() for f in files]
        dir_names = set()
        for f in files:
            for part in f.relative_to(self.project_path).parts[:-1]:
                dir_names.add(part.lower())

        if 'models.py' in file_names or 'models/' in dir_names:
            patterns.append('MVC/Model layer')
        if 'views.py' in file_names or 'views/' in dir_names:
            patterns.append('MVC/View layer')
        if 'controllers/' in dir_names:
            patterns.append('MVC/Controller layer')
        if 'routes.py' in file_names or 'routers/' in dir_names:
            patterns.append('Router-based API')
        if 'services/' in dir_names:
            patterns.append('Service layer pattern')
        if 'repositories/' in dir_names:
            patterns.append('Repository pattern')
        if 'handlers/' in dir_names:
            patterns.append('Handler pattern')
        if 'middleware/' in dir_names or 'middleware.py' in file_names:
            patterns.append('Middleware pattern')
        if 'schemas/' in dir_names or 'schema.py' in file_names:
            patterns.append('Schema/DTO pattern')
        if any('factory' in f for f in file_names):
            patterns.append('Factory pattern')
        if 'components/' in dir_names:
            patterns.append('Component-based architecture')
        if 'hooks/' in dir_names:
            patterns.append('React hooks pattern')
        if 'stores/' in dir_names:
            patterns.append('State management stores')

        return patterns

    def _detect_test_patterns(self, files: list[Path]) -> list[str]:
        """Detect testing patterns."""
        patterns = []

        test_files = [f for f in files if 'test' in f.name.lower() or 'spec' in f.name.lower()]

        if test_files:
            # Check test directory structure
            if any('tests/' in str(f) for f in test_files):
                patterns.append('tests/ directory for test files')
            if any('test_' in f.name for f in test_files):
                patterns.append('test_*.py naming convention')
            if any('_test.py' in f.name for f in test_files):
                patterns.append('*_test.py naming convention')
            if any('.spec.' in f.name for f in test_files):
                patterns.append('*.spec.* naming convention (JS/TS)')

            # Check for fixtures
            if any('conftest.py' in f.name for f in files):
                patterns.append('pytest fixtures (conftest.py)')
            if any('fixtures/' in str(f) for f in files):
                patterns.append('fixtures/ directory')

        return patterns


class AIBibleGenerator:
    """Generates Agent Bible using AI based on codebase analysis."""

    SYSTEM_PROMPT = """You are an expert software architect analyzing a codebase to create an Agent Bible document.

The Agent Bible is a set of rules and conventions that AI agents MUST follow when working on this project.

Based on the codebase analysis provided, generate a comprehensive AGENT_BIBLE.md that includes:

1. PROJECT OVERVIEW - Brief description of what the project does
2. TECH STACK - Languages, frameworks, key dependencies
3. ARCHITECTURE - How the code is organized, key patterns
4. CRITICAL RULES - What agents MUST and MUST NOT do
5. FILE CONVENTIONS - Naming, organization, imports
6. CODE STYLE - Formatting, patterns to follow
7. TESTING REQUIREMENTS - How to test changes
8. COMMON PITFALLS - Things to avoid

Be specific to THIS project based on the analysis. Don't be generic.
Use markdown formatting with clear sections.
Include practical examples from the actual codebase structure.
Make rules actionable and specific, not vague guidelines.

IMPORTANT: Generate the FULL AGENT_BIBLE.md content, not just an outline."""

    def __init__(self, provider: str = "auto"):
        """
        Initialize the generator.

        Args:
            provider: AI provider to use ('anthropic', 'openai', or 'auto')
        """
        self.provider = self._select_provider(provider)

    def _select_provider(self, provider: str) -> str:
        """Select the AI provider to use."""
        if provider == "auto":
            if os.environ.get("ANTHROPIC_API_KEY") and HAS_ANTHROPIC:
                return "anthropic"
            elif os.environ.get("OPENAI_API_KEY") and HAS_OPENAI:
                return "openai"
            else:
                raise ValueError(
                    "No AI provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY"
                )
        return provider

    def generate(self, analysis: CodebaseAnalysis, ticket_prefix: str = "FB") -> str:
        """
        Generate Agent Bible content using AI.

        Args:
            analysis: Codebase analysis results
            ticket_prefix: Ticket prefix to use (e.g., "FB")

        Returns:
            Generated AGENT_BIBLE.md content
        """
        user_prompt = f"""Analyze this codebase and generate an AGENT_BIBLE.md:

{analysis.to_prompt_context()}

Additional context:
- Ticket prefix for this project: {ticket_prefix}
- Generate date: {datetime.now().strftime('%Y-%m-%d')}

Generate the complete AGENT_BIBLE.md content now."""

        if self.provider == "anthropic":
            return self._generate_anthropic(user_prompt)
        elif self.provider == "openai":
            return self._generate_openai(user_prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _generate_anthropic(self, user_prompt: str) -> str:
        """Generate using Anthropic Claude."""
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic package not installed")

        client = anthropic.Anthropic()

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=self.SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        return message.content[0].text

    def _generate_openai(self, user_prompt: str) -> str:
        """Generate using OpenAI."""
        if not HAS_OPENAI:
            raise ImportError("openai package not installed")

        client = openai.OpenAI()

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=8000,
        )

        return response.choices[0].message.content or ""


def generate_ai_bible(
    project_path: Path,
    output_path: Path | None = None,
    ticket_prefix: str = "FB",
    provider: str = "auto",
) -> Path:
    """
    Generate an AI-powered Agent Bible for a project.

    Args:
        project_path: Root path of the project to analyze
        output_path: Where to save the Bible (default: .fastband/AGENT_BIBLE.md)
        ticket_prefix: Ticket prefix for the project
        provider: AI provider to use

    Returns:
        Path to the generated Agent Bible
    """
    # Analyze the codebase
    analyzer = CodebaseAnalyzer(project_path)
    analysis = analyzer.analyze()

    # Generate the Bible using AI
    generator = AIBibleGenerator(provider=provider)
    content = generator.generate(analysis, ticket_prefix=ticket_prefix)

    # Save to file
    if output_path is None:
        output_path = project_path / ".fastband" / "AGENT_BIBLE.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)

    return output_path
