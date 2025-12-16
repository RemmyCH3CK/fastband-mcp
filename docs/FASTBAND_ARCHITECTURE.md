# Fastband MCP - Technical Architecture

## Document Version: v1.2025.12.0
**Status**: Design Phase
**License**: MIT

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FASTBAND MCP PLATFORM                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │   Claude     │    │   OpenAI     │    │   Gemini     │   ...more    │
│  │   Provider   │    │   Provider   │    │   Provider   │              │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘              │
│         │                   │                   │                       │
│         └───────────────────┼───────────────────┘                       │
│                             │                                           │
│                    ┌────────▼────────┐                                  │
│                    │  AI Abstraction │                                  │
│                    │     Layer       │                                  │
│                    └────────┬────────┘                                  │
│                             │                                           │
│  ┌──────────────────────────▼──────────────────────────┐               │
│  │                    CORE ENGINE                       │               │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │               │
│  │  │ Tool        │ │ Project     │ │ Config      │   │               │
│  │  │ Registry    │ │ Manager     │ │ Manager     │   │               │
│  │  └─────────────┘ └─────────────┘ └─────────────┘   │               │
│  └─────────────────────────┬────────────────────────────┘               │
│                            │                                            │
│         ┌──────────────────┼──────────────────┐                        │
│         │                  │                  │                        │
│  ┌──────▼──────┐   ┌───────▼───────┐   ┌──────▼──────┐                │
│  │ Tool Garage │   │ Ticket Manager│   │ Setup Wizard│                │
│  │             │   │               │   │             │                │
│  │ ┌─────────┐ │   │ ┌───────────┐ │   │ ┌─────────┐ │                │
│  │ │  Core   │ │   │ │  Web UI   │ │   │ │ Project │ │                │
│  │ ├─────────┤ │   │ ├───────────┤ │   │ │ Detect  │ │                │
│  │ │  Web    │ │   │ │   CLI     │ │   │ ├─────────┤ │                │
│  │ ├─────────┤ │   │ ├───────────┤ │   │ │ GitHub  │ │                │
│  │ │ Mobile  │ │   │ │ Embedded  │ │   │ │ Config  │ │                │
│  │ ├─────────┤ │   │ ├───────────┤ │   │ ├─────────┤ │                │
│  │ │ Desktop │ │   │ │Integration│ │   │ │  Tool   │ │                │
│  │ ├─────────┤ │   │ │(GH,Jira)  │ │   │ │ Select  │ │                │
│  │ │ DevOps  │ │   │ └───────────┘ │   │ └─────────┘ │                │
│  │ └─────────┘ │   └───────────────┘   └─────────────┘                │
│  └─────────────┘                                                       │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      STORAGE LAYER                              │   │
│  │  ┌─────────┐  ┌────────────┐  ┌─────────┐  ┌──────────────┐    │   │
│  │  │ SQLite  │  │ PostgreSQL │  │  MySQL  │  │ File (JSON)  │    │   │
│  │  └─────────┘  └────────────┘  └─────────┘  └──────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 1. AI Abstraction Layer

### Provider Interface

```python
# src/fastband/providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, AsyncIterator
from enum import Enum


class Capability(Enum):
    """AI provider capabilities."""
    TEXT_COMPLETION = "text_completion"
    CODE_GENERATION = "code_generation"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    LONG_CONTEXT = "long_context"  # >100k tokens
    EXTENDED_THINKING = "extended_thinking"


@dataclass
class ProviderConfig:
    """Configuration for an AI provider."""
    name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 120
    extra: Dict[str, Any] = None


@dataclass
class CompletionResponse:
    """Standardized response from any AI provider."""
    content: str
    model: str
    provider: str
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    finish_reason: str
    raw_response: Optional[Dict] = None


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    All providers must implement this interface to ensure
    consistent behavior across Claude, OpenAI, Gemini, etc.
    """

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider-specific configuration."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return provider name (claude, openai, gemini, etc.)."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[Capability]:
        """Return list of supported capabilities."""
        pass

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> CompletionResponse:
        """
        Send a completion request to the AI.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            **kwargs: Provider-specific options

        Returns:
            Standardized CompletionResponse
        """
        pass

    @abstractmethod
    async def complete_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> CompletionResponse:
        """
        Complete with tool/function calling support.

        Args:
            prompt: The user prompt
            tools: List of tool definitions (OpenAI format)
            system_prompt: Optional system prompt

        Returns:
            Response with potential tool calls
        """
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream completion response.

        Yields:
            Text chunks as they arrive
        """
        pass

    @abstractmethod
    async def analyze_image(
        self,
        image_data: bytes,
        prompt: str,
        **kwargs
    ) -> CompletionResponse:
        """
        Analyze an image (vision capability).

        Args:
            image_data: Image bytes (PNG, JPEG, etc.)
            prompt: Analysis prompt

        Returns:
            Analysis response
        """
        pass

    def supports(self, capability: Capability) -> bool:
        """Check if provider supports a capability."""
        return capability in self.capabilities

    def get_recommended_model(self, task: str) -> str:
        """Get recommended model for a specific task type."""
        # Override in subclasses for task-specific recommendations
        return self.config.model
```

### Provider Implementations

```python
# src/fastband/providers/claude.py
from anthropic import AsyncAnthropic
from .base import AIProvider, Capability, CompletionResponse, ProviderConfig


class ClaudeProvider(AIProvider):
    """Claude/Anthropic AI provider."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.client = AsyncAnthropic(api_key=config.api_key)

    @property
    def name(self) -> str:
        return "claude"

    @property
    def capabilities(self) -> List[Capability]:
        return [
            Capability.TEXT_COMPLETION,
            Capability.CODE_GENERATION,
            Capability.VISION,
            Capability.FUNCTION_CALLING,
            Capability.STREAMING,
            Capability.LONG_CONTEXT,
            Capability.EXTENDED_THINKING,
        ]

    def _validate_config(self) -> None:
        if not self.config.api_key:
            raise ValueError("Claude requires ANTHROPIC_API_KEY")
        if not self.config.model:
            self.config.model = "claude-sonnet-4-20250514"

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> CompletionResponse:
        messages = [{"role": "user", "content": prompt}]

        response = await self.client.messages.create(
            model=self.config.model,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            system=system_prompt or "",
            messages=messages,
        )

        return CompletionResponse(
            content=response.content[0].text,
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
            raw_response=response.model_dump(),
        )

    # ... implement other methods


# src/fastband/providers/openai.py
class OpenAIProvider(AIProvider):
    """OpenAI/GPT AI provider."""

    @property
    def name(self) -> str:
        return "openai"

    @property
    def capabilities(self) -> List[Capability]:
        return [
            Capability.TEXT_COMPLETION,
            Capability.CODE_GENERATION,
            Capability.VISION,
            Capability.FUNCTION_CALLING,
            Capability.STREAMING,
        ]

    # ... implement methods


# src/fastband/providers/gemini.py
class GeminiProvider(AIProvider):
    """Google Gemini AI provider."""
    # ... implementation


# src/fastband/providers/ollama.py
class OllamaProvider(AIProvider):
    """Local Ollama AI provider."""
    # ... implementation
```

### Provider Registry

```python
# src/fastband/providers/registry.py
from typing import Dict, Type, Optional
from .base import AIProvider, ProviderConfig


class ProviderRegistry:
    """Registry for AI providers with lazy loading."""

    _providers: Dict[str, Type[AIProvider]] = {}
    _instances: Dict[str, AIProvider] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[AIProvider]) -> None:
        """Register a provider class."""
        cls._providers[name.lower()] = provider_class

    @classmethod
    def get(cls, name: str, config: Optional[ProviderConfig] = None) -> AIProvider:
        """
        Get or create a provider instance.

        Args:
            name: Provider name (claude, openai, gemini, ollama)
            config: Optional configuration (uses env vars if not provided)
        """
        name = name.lower()

        # Return cached instance if exists and no new config
        if name in cls._instances and config is None:
            return cls._instances[name]

        if name not in cls._providers:
            raise ValueError(f"Unknown provider: {name}. Available: {list(cls._providers.keys())}")

        # Create configuration from environment if not provided
        if config is None:
            config = cls._config_from_env(name)

        instance = cls._providers[name](config)
        cls._instances[name] = instance
        return instance

    @classmethod
    def _config_from_env(cls, name: str) -> ProviderConfig:
        """Create config from environment variables."""
        import os

        env_mappings = {
            "claude": ("ANTHROPIC_API_KEY", "claude-sonnet-4-20250514"),
            "openai": ("OPENAI_API_KEY", "gpt-4-turbo"),
            "gemini": ("GOOGLE_API_KEY", "gemini-pro"),
            "ollama": (None, "llama2"),  # No API key needed for local
        }

        api_key_env, default_model = env_mappings.get(name, (None, None))

        return ProviderConfig(
            name=name,
            api_key=os.getenv(api_key_env) if api_key_env else None,
            model=os.getenv(f"{name.upper()}_MODEL", default_model),
        )

    @classmethod
    def available_providers(cls) -> List[str]:
        """List registered providers."""
        return list(cls._providers.keys())


# Auto-register built-in providers
def _register_builtin_providers():
    from .claude import ClaudeProvider
    from .openai import OpenAIProvider
    from .gemini import GeminiProvider
    from .ollama import OllamaProvider

    ProviderRegistry.register("claude", ClaudeProvider)
    ProviderRegistry.register("openai", OpenAIProvider)
    ProviderRegistry.register("gemini", GeminiProvider)
    ProviderRegistry.register("ollama", OllamaProvider)


_register_builtin_providers()


# Convenience function
def get_provider(name: str = None) -> AIProvider:
    """
    Get the configured AI provider.

    If name is not specified, uses FASTBAND_AI_PROVIDER env var,
    defaulting to 'claude'.
    """
    import os
    if name is None:
        name = os.getenv("FASTBAND_AI_PROVIDER", "claude")
    return ProviderRegistry.get(name)
```

---

## 2. Tool Garage System

### Tool Definition

```python
# src/fastband/tools/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from enum import Enum


class ToolCategory(Enum):
    """Tool categories for the garage system."""
    CORE = "core"              # Always loaded
    FILE_OPS = "file_ops"      # File operations
    GIT = "git"                # Version control
    WEB = "web"                # Web development
    MOBILE = "mobile"          # Mobile development
    DESKTOP = "desktop"        # Desktop development
    DEVOPS = "devops"          # CI/CD, containers
    TESTING = "testing"        # Test execution
    ANALYSIS = "analysis"      # Code quality, security
    TICKETS = "tickets"        # Ticket management
    SCREENSHOTS = "screenshots" # Visual capture
    AI = "ai"                  # AI-powered analysis


class ProjectType(Enum):
    """Project types for tool recommendation."""
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


@dataclass
class ToolMetadata:
    """Metadata for a tool."""
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    author: str = "Fastband Team"

    # Recommendation hints
    project_types: List[ProjectType] = field(default_factory=list)
    tech_stack_hints: List[str] = field(default_factory=list)  # e.g., ["python", "react"]

    # Dependencies
    requires_tools: List[str] = field(default_factory=list)
    conflicts_with: List[str] = field(default_factory=list)

    # Resource hints
    memory_intensive: bool = False
    network_required: bool = False

    # Curation status (for third-party tools)
    curated: bool = True
    curator_notes: Optional[str] = None


@dataclass
class ToolParameter:
    """Parameter definition for a tool."""
    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None


@dataclass
class ToolDefinition:
    """Complete tool definition."""
    metadata: ToolMetadata
    parameters: List[ToolParameter]
    handler: Callable[..., Dict[str, Any]]

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling schema."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.metadata.name,
                "description": self.metadata.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class Tool(ABC):
    """Base class for all tools."""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return tool definition."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters."""
        pass

    def validate_params(self, **kwargs) -> bool:
        """Validate parameters against definition."""
        for param in self.definition.parameters:
            if param.required and param.name not in kwargs:
                raise ValueError(f"Missing required parameter: {param.name}")
        return True
```

### Tool Registry

```python
# src/fastband/tools/registry.py
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
import logging

from .base import Tool, ToolCategory, ProjectType, ToolDefinition

logger = logging.getLogger(__name__)


@dataclass
class ToolLoadStatus:
    """Status of a loaded tool."""
    name: str
    loaded: bool
    category: ToolCategory
    load_time_ms: float
    error: Optional[str] = None


class ToolRegistry:
    """
    Registry for managing the Tool Garage.

    Handles tool loading, unloading, and recommendations.
    """

    def __init__(self, max_active_tools: int = 60):
        self._available: Dict[str, Tool] = {}  # All registered tools
        self._active: Dict[str, Tool] = {}     # Currently loaded tools
        self._max_active = max_active_tools
        self._load_history: List[ToolLoadStatus] = []

    def register(self, tool: Tool) -> None:
        """Register a tool (make it available in garage)."""
        name = tool.definition.metadata.name
        self._available[name] = tool
        logger.info(f"Registered tool: {name}")

    def load(self, name: str) -> ToolLoadStatus:
        """Load a tool from garage into active set."""
        import time
        start = time.perf_counter()

        if name not in self._available:
            return ToolLoadStatus(
                name=name,
                loaded=False,
                category=ToolCategory.CORE,
                load_time_ms=0,
                error=f"Tool not found: {name}",
            )

        if name in self._active:
            return ToolLoadStatus(
                name=name,
                loaded=True,
                category=self._active[name].definition.metadata.category,
                load_time_ms=0,
                error="Already loaded",
            )

        # Check max tools limit (soft limit with warning)
        if len(self._active) >= self._max_active:
            logger.warning(
                f"Tool count ({len(self._active)}) at limit ({self._max_active}). "
                "Performance may be impacted."
            )

        tool = self._available[name]
        self._active[name] = tool

        elapsed = (time.perf_counter() - start) * 1000
        status = ToolLoadStatus(
            name=name,
            loaded=True,
            category=tool.definition.metadata.category,
            load_time_ms=elapsed,
        )
        self._load_history.append(status)

        logger.info(f"Loaded tool: {name} ({elapsed:.2f}ms)")
        return status

    def unload(self, name: str) -> bool:
        """Unload a tool from active set."""
        if name not in self._active:
            return False

        # Don't unload core tools
        tool = self._active[name]
        if tool.definition.metadata.category == ToolCategory.CORE:
            logger.warning(f"Cannot unload core tool: {name}")
            return False

        del self._active[name]
        logger.info(f"Unloaded tool: {name}")
        return True

    def get_active_tools(self) -> List[Tool]:
        """Get all currently active tools."""
        return list(self._active.values())

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get an active tool by name."""
        return self._active.get(name)

    def get_active_definitions(self) -> List[ToolDefinition]:
        """Get definitions for all active tools."""
        return [t.definition for t in self._active.values()]

    def get_openai_schemas(self) -> List[Dict]:
        """Get OpenAI function schemas for all active tools."""
        return [t.definition.to_openai_schema() for t in self._active.values()]

    def get_performance_report(self) -> Dict:
        """Get tool loading performance report."""
        active_count = len(self._active)
        available_count = len(self._available)

        status = "optimal"
        if active_count > 40:
            status = "heavy"
        if active_count > 60:
            status = "overloaded"

        return {
            "active_tools": active_count,
            "available_tools": available_count,
            "max_recommended": self._max_active,
            "status": status,
            "categories": self._count_by_category(),
            "recommendation": self._get_performance_recommendation(),
        }

    def _count_by_category(self) -> Dict[str, int]:
        """Count active tools by category."""
        counts = {}
        for tool in self._active.values():
            cat = tool.definition.metadata.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def _get_performance_recommendation(self) -> Optional[str]:
        """Get performance optimization recommendation."""
        count = len(self._active)
        if count < 20:
            return None
        if count < 40:
            return "Consider reviewing unused tools with 'fastband tools audit'"
        if count < 60:
            return "Tool count is high. Run 'fastband tools optimize' to unload unused tools"
        return "WARNING: Tool count exceeds recommended limit. Performance may be degraded."


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
```

### Tool Recommendation Engine

```python
# src/fastband/tools/recommender.py
from dataclasses import dataclass
from typing import List, Dict, Set, Optional
from pathlib import Path
import json

from .base import ToolCategory, ProjectType
from .registry import ToolRegistry, get_registry


@dataclass
class ProjectContext:
    """Detected project context."""
    project_type: ProjectType
    tech_stack: Set[str]
    frameworks: Set[str]
    has_docker: bool
    has_ci: bool
    has_tests: bool
    file_count: int
    loc_estimate: int
    git_initialized: bool
    has_remote: bool


@dataclass
class ToolRecommendation:
    """A tool recommendation."""
    tool_name: str
    category: ToolCategory
    reason: str
    confidence: float  # 0.0 - 1.0
    required: bool  # If True, strongly recommend


class ProjectDetector:
    """Detect project type and context."""

    TECH_INDICATORS = {
        # Python
        "requirements.txt": ("python", 0.9),
        "pyproject.toml": ("python", 0.95),
        "setup.py": ("python", 0.9),
        "Pipfile": ("python", 0.9),

        # JavaScript/TypeScript
        "package.json": ("javascript", 0.9),
        "tsconfig.json": ("typescript", 0.95),
        "yarn.lock": ("javascript", 0.8),
        "pnpm-lock.yaml": ("javascript", 0.8),

        # Framework indicators
        "next.config.js": ("nextjs", 0.95),
        "nuxt.config.js": ("nuxt", 0.95),
        "angular.json": ("angular", 0.95),
        "vue.config.js": ("vue", 0.9),
        "vite.config.ts": ("vite", 0.9),

        # Mobile
        "Podfile": ("ios", 0.9),
        "build.gradle": ("android", 0.8),
        "pubspec.yaml": ("flutter", 0.95),
        "app.json": ("react_native", 0.7),

        # Desktop
        "electron.js": ("electron", 0.9),
        "electron-builder.json": ("electron", 0.95),
        "tauri.conf.json": ("tauri", 0.95),

        # DevOps
        "Dockerfile": ("docker", 0.9),
        "docker-compose.yml": ("docker", 0.95),
        ".github/workflows": ("github_actions", 0.95),
        "Jenkinsfile": ("jenkins", 0.95),

        # Testing
        "pytest.ini": ("pytest", 0.95),
        "jest.config.js": ("jest", 0.95),
        "cypress.config.js": ("cypress", 0.95),
    }

    def analyze(self, project_path: Path) -> ProjectContext:
        """Analyze a project directory."""
        tech_stack = set()
        frameworks = set()

        # Scan for indicator files
        for indicator, (tech, confidence) in self.TECH_INDICATORS.items():
            indicator_path = project_path / indicator
            if indicator_path.exists() or (project_path / indicator).is_dir():
                if confidence > 0.8:
                    tech_stack.add(tech)
                if tech in ["nextjs", "nuxt", "angular", "vue", "react_native", "flutter"]:
                    frameworks.add(tech)

        # Determine project type
        project_type = self._determine_project_type(tech_stack, frameworks)

        return ProjectContext(
            project_type=project_type,
            tech_stack=tech_stack,
            frameworks=frameworks,
            has_docker="docker" in tech_stack,
            has_ci="github_actions" in tech_stack or "jenkins" in tech_stack,
            has_tests=any(t in tech_stack for t in ["pytest", "jest", "cypress"]),
            file_count=self._count_files(project_path),
            loc_estimate=self._estimate_loc(project_path),
            git_initialized=(project_path / ".git").is_dir(),
            has_remote=self._has_git_remote(project_path),
        )

    def _determine_project_type(
        self,
        tech_stack: Set[str],
        frameworks: Set[str]
    ) -> ProjectType:
        """Determine the primary project type."""
        # Mobile first (more specific)
        if "flutter" in frameworks:
            return ProjectType.MOBILE_CROSS
        if "react_native" in frameworks:
            return ProjectType.MOBILE_CROSS
        if "ios" in tech_stack and "android" not in tech_stack:
            return ProjectType.MOBILE_IOS
        if "android" in tech_stack and "ios" not in tech_stack:
            return ProjectType.MOBILE_ANDROID

        # Desktop
        if "electron" in tech_stack or "tauri" in tech_stack:
            return ProjectType.DESKTOP_ELECTRON

        # Web
        if any(f in frameworks for f in ["nextjs", "nuxt", "angular", "vue"]):
            return ProjectType.WEB_APP
        if "javascript" in tech_stack or "typescript" in tech_stack:
            return ProjectType.WEB_APP

        # Python-based
        if "python" in tech_stack:
            if "flask" in tech_stack or "django" in tech_stack or "fastapi" in tech_stack:
                return ProjectType.WEB_APP
            return ProjectType.API_SERVICE

        return ProjectType.UNKNOWN

    def _count_files(self, path: Path) -> int:
        """Count source files in project."""
        extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".svelte"}
        count = 0
        for ext in extensions:
            count += len(list(path.rglob(f"*{ext}")))
        return count

    def _estimate_loc(self, path: Path) -> int:
        """Rough LOC estimate."""
        # Quick estimate: file_count * 100 average lines
        return self._count_files(path) * 100

    def _has_git_remote(self, path: Path) -> bool:
        """Check if git remote is configured."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "remote", "-v"],
                cwd=path,
                capture_output=True,
                text=True,
            )
            return bool(result.stdout.strip())
        except Exception:
            return False


class ToolRecommender:
    """AI-powered tool recommendation engine."""

    # Base recommendations per project type
    PROJECT_TOOL_MAP = {
        ProjectType.WEB_APP: [
            ("take_screenshot", 0.95, "Visual testing for web apps"),
            ("build_container", 0.8, "Docker support detected"),
            ("run_tests", 0.9, "Testing framework detected"),
            ("code_quality", 0.85, "Maintain code quality"),
            ("security_scan", 0.8, "Security best practice"),
            ("browser_console", 0.7, "Debug frontend issues"),
        ],
        ProjectType.MOBILE_CROSS: [
            ("mobile_preview", 0.95, "Preview on devices"),
            ("build_mobile", 0.9, "Cross-platform builds"),
            ("app_store_prep", 0.7, "Prepare for distribution"),
        ],
        ProjectType.DESKTOP_ELECTRON: [
            ("package_app", 0.95, "Package desktop app"),
            ("cross_platform_build", 0.9, "Multi-platform support"),
            ("embedded_tickets", 0.8, "Built-in ticket management"),
        ],
        # ... more mappings
    }

    # Core tools always recommended
    CORE_TOOLS = [
        ("health_check", 1.0, "System health monitoring"),
        ("list_files", 1.0, "File browsing"),
        ("read_file", 1.0, "File reading"),
        ("write_file", 1.0, "File writing"),
        ("search_code", 1.0, "Code search"),
        ("git_status", 0.95, "Version control"),
        ("git_commit", 0.95, "Commit changes"),
    ]

    def __init__(self, registry: ToolRegistry = None):
        self.registry = registry or get_registry()
        self.detector = ProjectDetector()

    def analyze_and_recommend(
        self,
        project_path: Path
    ) -> tuple[ProjectContext, List[ToolRecommendation]]:
        """
        Analyze project and recommend tools.

        Returns:
            Tuple of (ProjectContext, List of recommendations)
        """
        context = self.detector.analyze(project_path)
        recommendations = self._generate_recommendations(context)
        return context, recommendations

    def _generate_recommendations(
        self,
        context: ProjectContext
    ) -> List[ToolRecommendation]:
        """Generate tool recommendations based on context."""
        recommendations = []

        # Always add core tools
        for tool_name, confidence, reason in self.CORE_TOOLS:
            recommendations.append(ToolRecommendation(
                tool_name=tool_name,
                category=ToolCategory.CORE,
                reason=reason,
                confidence=confidence,
                required=confidence > 0.9,
            ))

        # Add project-type specific tools
        project_tools = self.PROJECT_TOOL_MAP.get(context.project_type, [])
        for tool_name, confidence, reason in project_tools:
            recommendations.append(ToolRecommendation(
                tool_name=tool_name,
                category=self._get_tool_category(tool_name),
                reason=reason,
                confidence=confidence,
                required=False,
            ))

        # Adjust based on detected features
        if context.has_docker:
            recommendations.append(ToolRecommendation(
                tool_name="build_container",
                category=ToolCategory.DEVOPS,
                reason="Docker files detected",
                confidence=0.95,
                required=False,
            ))

        if context.has_ci:
            recommendations.append(ToolRecommendation(
                tool_name="ci_status",
                category=ToolCategory.DEVOPS,
                reason="CI/CD pipeline detected",
                confidence=0.85,
                required=False,
            ))

        # Sort by confidence
        recommendations.sort(key=lambda r: r.confidence, reverse=True)

        return recommendations

    def _get_tool_category(self, tool_name: str) -> ToolCategory:
        """Get category for a tool name."""
        # Would look up in registry in real implementation
        category_hints = {
            "take_screenshot": ToolCategory.SCREENSHOTS,
            "build_container": ToolCategory.DEVOPS,
            "run_tests": ToolCategory.TESTING,
            "code_quality": ToolCategory.ANALYSIS,
            "security_scan": ToolCategory.ANALYSIS,
        }
        return category_hints.get(tool_name, ToolCategory.CORE)
```

---

## 3. Storage Abstraction Layer

```python
# src/fastband/storage/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class StorageConfig:
    """Storage backend configuration."""
    backend: str  # "sqlite", "postgres", "mysql", "file"
    connection_string: Optional[str] = None
    path: Optional[str] = None  # For SQLite/file backends
    extra: Dict[str, Any] = None


class StorageBackend(ABC):
    """Abstract storage backend."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to storage."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close storage connection."""
        pass

    @abstractmethod
    async def get(self, collection: str, key: str) -> Optional[Dict]:
        """Get a single item."""
        pass

    @abstractmethod
    async def set(self, collection: str, key: str, value: Dict) -> None:
        """Set a single item."""
        pass

    @abstractmethod
    async def delete(self, collection: str, key: str) -> bool:
        """Delete an item."""
        pass

    @abstractmethod
    async def query(
        self,
        collection: str,
        filters: Dict[str, Any] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Query items with filters."""
        pass

    @abstractmethod
    async def count(self, collection: str, filters: Dict[str, Any] = None) -> int:
        """Count items matching filters."""
        pass


# Implementations in separate files:
# - src/fastband/storage/sqlite.py
# - src/fastband/storage/postgres.py
# - src/fastband/storage/mysql.py
# - src/fastband/storage/file_based.py
```

---

## 4. Configuration Schema

```yaml
# config/defaults.yaml
fastband:
  version: "1.2025.12"

  # AI Provider Configuration
  ai:
    default_provider: "claude"  # claude, openai, gemini, ollama
    providers:
      claude:
        model: "claude-sonnet-4-20250514"
        max_tokens: 4096
      openai:
        model: "gpt-4-turbo"
        max_tokens: 4096
      gemini:
        model: "gemini-pro"
      ollama:
        model: "llama2"
        base_url: "http://localhost:11434"

  # Tool Garage Configuration
  tools:
    max_active: 60  # Soft limit, warns above this
    auto_load_core: true
    performance_warning_threshold: 40

  # Storage Configuration
  storage:
    backend: "sqlite"  # sqlite, postgres, mysql, file
    sqlite:
      path: ".fastband/data.db"
    postgres:
      host: "localhost"
      port: 5432
      database: "fastband"
    mysql:
      host: "localhost"
      port: 3306
      database: "fastband"
    file:
      path: ".fastband/data"
      format: "json"  # json or yaml

  # Ticket Manager Configuration
  tickets:
    enabled: true
    mode: "auto"  # auto, cli, web, embedded
    web_port: 5050
    review_agents: true
    external_sync:
      enabled: false
      provider: null  # github, jira, linear

  # GitHub Integration
  github:
    enabled: false
    automation_level: "hybrid"  # full, guided, hybrid, none
    default_branch: "main"
    create_pr_template: true

  # Backup Configuration
  backup:
    auto_backup: true
    frequency: "daily"
    retention_days: 30
    location: ".fastband/backups"
```

---

## 5. Plugin Architecture (Curated Third-Party)

```python
# src/fastband/plugins/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from ..tools.base import Tool


@dataclass
class PluginMetadata:
    """Plugin metadata for curation."""
    name: str
    version: str
    author: str
    description: str
    homepage: Optional[str] = None
    repository: Optional[str] = None

    # Curation info
    curated: bool = False
    curated_date: Optional[str] = None
    curator: Optional[str] = None
    security_reviewed: bool = False
    review_notes: Optional[str] = None


class FastbandPlugin(ABC):
    """Base class for Fastband plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        pass

    @abstractmethod
    def get_tools(self) -> List[Tool]:
        """Return tools provided by this plugin."""
        pass

    def on_load(self) -> None:
        """Called when plugin is loaded."""
        pass

    def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        pass


# Example curated plugin structure:
# plugins/
# ├── official/          # First-party plugins
# │   ├── aws_tools/
# │   ├── gcp_tools/
# │   └── azure_tools/
# └── curated/           # Reviewed third-party
#     ├── notion_sync/
#     └── slack_notify/
```

---

## Next Steps

1. **Review this architecture** with stakeholders
2. **Create GitHub repository** with this structure
3. **Implement core engine** first (AI abstraction + tool registry)
4. **Port existing tools** from MLB implementation
5. **Build setup wizard** for new projects
6. **Create documentation** site

---

*Architecture document - Fastband MCP v1.2025.12*
