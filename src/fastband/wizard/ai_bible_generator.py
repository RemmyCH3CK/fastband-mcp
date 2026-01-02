"""
AI-Powered Agent Bible Generator.

Analyzes the codebase using AI to generate a context-aware AGENT_BIBLE.md
that reflects the project's actual patterns, conventions, and architecture.

The generated bible follows a strict 10 Laws structure with:
- Ops Log coordination for parallel agents
- Security requirements (no secrets, parameterized queries, path validation)
- Screenshot verification with Vision API
- Review agent protocols
- MCP tool reference
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
    test_command: str = "pytest"
    lint_command: str = "ruff check ."
    dev_url: str = "http://localhost:8000"
    service_name: str = "app"

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

DETECTED COMMANDS:
- Test command: {self.test_command}
- Lint command: {self.lint_command}
- Dev URL: {self.dev_url}
- Service name: {self.service_name}
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

        # Detect project-specific commands and URLs
        test_command = self._detect_test_command(all_files)
        lint_command = self._detect_lint_command(all_files)
        dev_url = self._detect_dev_url(all_files)
        service_name = self._detect_service_name(all_files)

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
            test_command=test_command,
            lint_command=lint_command,
            dev_url=dev_url,
            service_name=service_name,
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

    def _detect_test_command(self, files: list[Path]) -> str:
        """Detect the appropriate test command for the project."""
        file_names = [f.name.lower() for f in files]

        # Python projects
        if 'pytest.ini' in file_names or 'conftest.py' in file_names:
            return 'pytest'
        if 'pyproject.toml' in file_names:
            return 'pytest'
        if 'setup.py' in file_names:
            return 'python -m pytest'

        # JavaScript/TypeScript projects
        if 'package.json' in file_names:
            # Check for specific test runners
            for f in files:
                if f.name == 'package.json':
                    try:
                        content = f.read_text(errors='ignore')
                        if 'vitest' in content:
                            return 'npm run test'
                        if 'jest' in content:
                            return 'npm test'
                        if 'mocha' in content:
                            return 'npm test'
                    except Exception:
                        pass
            return 'npm test'

        # Go projects
        if 'go.mod' in file_names:
            return 'go test ./...'

        # Rust projects
        if 'Cargo.toml' in file_names:
            return 'cargo test'

        return 'pytest'  # Default fallback

    def _detect_lint_command(self, files: list[Path]) -> str:
        """Detect the appropriate lint command for the project."""
        file_names = [f.name.lower() for f in files]

        # Python projects
        if 'pyproject.toml' in file_names or 'ruff.toml' in file_names:
            return 'ruff check .'
        if '.flake8' in file_names:
            return 'flake8 .'
        if 'setup.cfg' in file_names:
            return 'ruff check .'

        # JavaScript/TypeScript projects
        if '.eslintrc' in file_names or '.eslintrc.js' in file_names or '.eslintrc.json' in file_names:
            return 'npm run lint'

        # Go projects
        if 'go.mod' in file_names:
            return 'golangci-lint run'

        # Rust projects
        if 'Cargo.toml' in file_names:
            return 'cargo clippy'

        return 'ruff check .'  # Default fallback

    def _detect_dev_url(self, files: list[Path]) -> str:
        """Detect the development server URL."""
        file_names = [f.name.lower() for f in files]

        # Check docker-compose for port mappings
        for f in files:
            if 'docker-compose' in f.name.lower():
                try:
                    content = f.read_text(errors='ignore')
                    # Look for common port patterns
                    if '8080:' in content:
                        return 'http://localhost:8080'
                    if '3000:' in content:
                        return 'http://localhost:3000'
                    if '5000:' in content:
                        return 'http://localhost:5000'
                except Exception:
                    pass

        # Framework-specific defaults
        if 'package.json' in file_names:
            return 'http://localhost:3000'
        if any('fastapi' in str(f).lower() for f in files):
            return 'http://localhost:8000'
        if any('flask' in str(f).lower() for f in files):
            return 'http://localhost:5000'
        if any('django' in str(f).lower() for f in files):
            return 'http://localhost:8000'

        return 'http://localhost:8000'  # Default fallback

    def _detect_service_name(self, files: list[Path]) -> str:
        """Detect the primary service/container name."""
        # Check docker-compose for service names
        for f in files:
            if 'docker-compose' in f.name.lower():
                try:
                    content = f.read_text(errors='ignore')
                    # Look for service definitions
                    if 'webapp:' in content or 'web:' in content:
                        return 'webapp'
                    if 'api:' in content:
                        return 'api'
                    if 'app:' in content:
                        return 'app'
                except Exception:
                    pass

        return 'app'  # Default fallback


class AIBibleGenerator:
    """Generates Agent Bible using AI based on codebase analysis."""

    SYSTEM_PROMPT = """You are an expert at creating Agent Bible documents for AI agent coordination systems.

The Agent Bible is the AUTHORITATIVE set of rules that AI agents MUST follow when working on a project.
It enables safe parallel agent operation through strict protocols.

You will generate a comprehensive AGENT_BIBLE.md following this EXACT structure:

## REQUIRED STRUCTURE (Follow This Order):

1. **THE HIERARCHY OF AUTHORITY** - ASCII diagram showing: USER > MCP TOOLS > AGENT_BIBLE > AGENTS
2. **THE TEN LAWS** - 10 specific, enforceable laws (see below)
3. **PROJECT ARCHITECTURE** - Tech stack, directory structure, key files
4. **TICKET WORKFLOW (7 Steps)** - Claim → Screenshot → Work → Verify → Commit → Complete → Review
5. **AGENT OPS LOG PROTOCOL** - Holds, clearances, rebuild coordination for parallel agents
6. **VERIFICATION REQUIREMENTS** - Checklists for completing work
7. **REVIEW AGENT PROTOCOL** - 3-agent review system (Code, Security, Process)
8. **MCP TOOL REFERENCE** - Table of available tools
9. **SECURITY REQUIREMENTS** - Code examples of correct vs incorrect patterns
10. **ERROR RECOVERY & COMMON FIXES** - Pattern-based troubleshooting
11. **QUICK REFERENCE CARD** - Summary of laws and essential commands

## THE TEN LAWS (Adapt to Project):

Each law MUST have: THE RULE, FORBIDDEN examples, REQUIRED examples

1. **Ops Log Reporting is Mandatory** - All agents report to ops log, check for holds before work
2. **Never Commit Secrets** - No hardcoded credentials, use environment variables
3. **Use Parameterized Queries Only** - No SQL injection, use placeholders
4. **Validate All Paths** - Prevent path traversal attacks
5. **Screenshots Must Be Analyzed** - Vision API verification, not just captured
6. **Test Before Completing** - Run tests, don't assume code works
7. **Never Auto-Resolve Tickets** - Only humans set status to Resolved
8. **Never Give Up** - Persist through difficulties, try multiple approaches
9. **Keep the Bible Updated** - Propose corrections when discrepancies found
10. **Commit Changes After Work** - Git commits required before completing

## OPS LOG PROTOCOL (Critical for Parallel Agents):

The Agent Ops Log enables safe parallel agent coordination:
- **Holds** - Stop all agents from proceeding (e.g., during deploy)
- **Clearances** - Allow agents to proceed after hold
- **Rebuild announcements** - Coordinate container restarts
- Agents MUST check for holds BEFORE starting any work
- Agents MUST announce rebuilds BEFORE and AFTER

## KEY PRINCIPLES:

1. Be SPECIFIC to the project - use actual file paths, commands, URLs from the analysis
2. Include working code examples with project-specific imports/patterns
3. Laws must have FORBIDDEN and REQUIRED sections with concrete examples
4. Use the exact tool names: mcp__fastband-mcp__<tool_name>()
5. Include the ticket workflow with status flow diagram
6. Make error recovery actionable with specific fixes

## FORMATTING:

- Use markdown with clear headers
- Include ASCII diagrams for visual concepts
- Use code blocks with language hints
- Include tables for quick reference
- Status flow: 🔴 Open → 🟡 In Progress → 🔍 Under Review → 🔵 Awaiting Approval → 🟢 Resolved

IMPORTANT: Generate the COMPLETE AGENT_BIBLE.md content, not just an outline.
Make it actionable and specific to THIS project based on the analysis provided."""

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

    def generate(
        self,
        analysis: CodebaseAnalysis,
        ticket_prefix: str = "FB",
        hub_url: str = "http://localhost:8000",
    ) -> str:
        """
        Generate Agent Bible content using AI.

        Args:
            analysis: Codebase analysis results
            ticket_prefix: Ticket prefix to use (e.g., "FB")
            hub_url: URL for the Fastband Hub

        Returns:
            Generated AGENT_BIBLE.md content
        """
        user_prompt = f"""Generate a comprehensive AGENT_BIBLE.md for this project:

{analysis.to_prompt_context()}

## PROJECT-SPECIFIC VALUES TO USE:

| Placeholder | Value |
|-------------|-------|
| PROJECT_NAME | {analysis.project_name} |
| GENERATION_DATE | {datetime.now().strftime('%Y-%m-%d')} |
| TICKET_PREFIX | {ticket_prefix} |
| TEST_COMMAND | {analysis.test_command} |
| LINT_COMMAND | {analysis.lint_command} |
| DEV_URL | {analysis.dev_url} |
| HUB_URL | {hub_url} |
| SERVICE_NAME | {analysis.service_name} |
| PRIMARY_LANGUAGE | {analysis.primary_language} |
| FRAMEWORKS | {', '.join(analysis.frameworks) or 'None detected'} |
| REPO_NAME | {analysis.project_name} |

## REQUIREMENTS:

1. Use the VALUES above in your generated content (not placeholders)
2. Include the 10 Laws with FORBIDDEN/REQUIRED sections
3. Include the Ops Log Protocol for parallel agent coordination
4. Include the 7-step ticket workflow with status diagram
5. Include the 3-agent review protocol (Code, Security, Process)
6. Include project-specific security examples
7. Include error recovery patterns relevant to this tech stack
8. Make all code examples use the actual project structure

Generate the COMPLETE AGENT_BIBLE.md now. Be specific to this project, not generic."""

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
    hub_url: str = "http://localhost:8000",
) -> Path:
    """
    Generate an AI-powered Agent Bible for a project.

    The generated bible includes:
    - 10 Laws with FORBIDDEN/REQUIRED sections
    - Ops Log Protocol for parallel agent coordination
    - 7-step ticket workflow
    - 3-agent review protocol
    - Project-specific security examples
    - Error recovery patterns

    Args:
        project_path: Root path of the project to analyze
        output_path: Where to save the Bible (default: .fastband/AGENT_BIBLE.md)
        ticket_prefix: Ticket prefix for the project (e.g., "FB", "MLB")
        provider: AI provider to use ("anthropic", "openai", or "auto")
        hub_url: URL for the Fastband Hub dashboard

    Returns:
        Path to the generated Agent Bible
    """
    # Analyze the codebase
    analyzer = CodebaseAnalyzer(project_path)
    analysis = analyzer.analyze()

    # Generate the Bible using AI
    generator = AIBibleGenerator(provider=provider)
    content = generator.generate(
        analysis,
        ticket_prefix=ticket_prefix,
        hub_url=hub_url,
    )

    # Save to file
    if output_path is None:
        output_path = project_path / ".fastband" / "AGENT_BIBLE.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)

    return output_path
