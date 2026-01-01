"""
System Capability Detection Module

Detects system resources (RAM, CPU, disk) and combines with
AI provider limits to recommend optimal tool configurations.
"""

from dataclasses import dataclass, field
from typing import Optional
import platform
import sys

# Optional psutil import for detailed system info
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# AI provider context limits and recommended tool counts
AI_PROVIDER_LIMITS = {
    "anthropic": {
        "claude-opus-4": {"context": 200000, "recommended_tools": 100},
        "claude-sonnet-4": {"context": 200000, "recommended_tools": 80},
        "claude-haiku-3.5": {"context": 200000, "recommended_tools": 60},
        "claude-3-opus": {"context": 200000, "recommended_tools": 100},
        "claude-3-sonnet": {"context": 200000, "recommended_tools": 80},
        "claude-3-haiku": {"context": 200000, "recommended_tools": 60},
        "default": {"context": 200000, "recommended_tools": 80},
    },
    "openai": {
        "gpt-4o": {"context": 128000, "recommended_tools": 60},
        "gpt-4-turbo": {"context": 128000, "recommended_tools": 50},
        "gpt-4": {"context": 8192, "recommended_tools": 30},
        "gpt-3.5-turbo": {"context": 16385, "recommended_tools": 25},
        "default": {"context": 128000, "recommended_tools": 50},
    },
    "gemini": {
        "gemini-pro": {"context": 32000, "recommended_tools": 30},
        "gemini-1.5-pro": {"context": 1000000, "recommended_tools": 100},
        "gemini-1.5-flash": {"context": 1000000, "recommended_tools": 80},
        "default": {"context": 32000, "recommended_tools": 30},
    },
    "ollama": {
        "llama3.2": {"context": 8000, "recommended_tools": 20},
        "llama3.1": {"context": 8000, "recommended_tools": 20},
        "mistral": {"context": 8000, "recommended_tools": 20},
        "codellama": {"context": 8000, "recommended_tools": 15},
        "default": {"context": 8000, "recommended_tools": 20},
    },
}


@dataclass
class SystemCapabilities:
    """System resource and capability information."""

    # System info
    platform: str = ""
    cpu_cores: int = 2
    total_ram_gb: float = 8.0
    available_ram_gb: float = 4.0
    disk_free_gb: float = 10.0
    python_version: str = ""

    # AI Provider context
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    context_window: int = 0

    # Computed recommendations
    max_recommended_tools: int = 40

    @classmethod
    def detect(cls) -> "SystemCapabilities":
        """Detect current system capabilities."""
        caps = cls(
            platform=platform.system().lower(),
            python_version=sys.version,
        )

        if HAS_PSUTIL:
            try:
                # CPU cores (physical, not logical)
                caps.cpu_cores = psutil.cpu_count(logical=False) or 2

                # Memory info
                mem = psutil.virtual_memory()
                caps.total_ram_gb = round(mem.total / (1024**3), 1)
                caps.available_ram_gb = round(mem.available / (1024**3), 1)

                # Disk info (root partition)
                disk = psutil.disk_usage("/")
                caps.disk_free_gb = round(disk.free / (1024**3), 1)
            except Exception:
                # Use defaults on error
                pass
        else:
            # Fallback without psutil - conservative defaults
            caps.cpu_cores = 2
            caps.total_ram_gb = 8.0
            caps.available_ram_gb = 4.0
            caps.disk_free_gb = 10.0

        # Calculate initial recommendation based on RAM
        caps.max_recommended_tools = caps._calculate_base_tools()

        return caps

    def _calculate_base_tools(self) -> int:
        """Calculate recommended max tools based on system resources."""
        # Base calculation on available RAM
        if self.available_ram_gb < 4:
            base = 20
        elif self.available_ram_gb < 8:
            base = 40
        elif self.available_ram_gb < 16:
            base = 60
        elif self.available_ram_gb < 32:
            base = 80
        else:
            base = 100

        # Adjust for CPU cores
        if self.cpu_cores >= 8:
            base = int(base * 1.1)
        elif self.cpu_cores <= 2:
            base = int(base * 0.8)

        return max(15, min(base, 100))  # Clamp between 15 and 100

    def set_ai_provider(self, provider: str, model: Optional[str] = None) -> None:
        """Set AI provider and recalculate recommendations."""
        self.ai_provider = provider.lower()
        self.ai_model = model

        # Get provider limits
        provider_limits = AI_PROVIDER_LIMITS.get(self.ai_provider, {})
        model_key = model or "default"
        model_limits = provider_limits.get(model_key, provider_limits.get("default", {}))

        self.context_window = model_limits.get("context", 0)
        provider_recommended = model_limits.get("recommended_tools", 50)

        # Combine system-based and provider-based recommendations
        system_based = self._calculate_base_tools()

        # Take the minimum of system and provider recommendations
        self.max_recommended_tools = min(system_based, provider_recommended)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "platform": self.platform,
            "cpuCores": self.cpu_cores,
            "totalRamGB": self.total_ram_gb,
            "availableRamGB": self.available_ram_gb,
            "diskFreeGB": self.disk_free_gb,
            "pythonVersion": self.python_version,
            "aiProvider": self.ai_provider,
            "aiModel": self.ai_model,
            "contextWindow": self.context_window,
            "maxRecommendedTools": self.max_recommended_tools,
            "hasPsutil": HAS_PSUTIL,
        }

    @classmethod
    def from_config(cls, config: dict) -> "SystemCapabilities":
        """Create from config dictionary with AI provider info."""
        caps = cls.detect()

        # Check for AI provider in config
        providers = config.get("providers", {})
        for provider_name in ["anthropic", "openai", "gemini", "ollama"]:
            provider_config = providers.get(provider_name, {})
            if provider_config.get("key") or provider_config.get("host"):
                model = provider_config.get("model")
                caps.set_ai_provider(provider_name, model)
                break

        return caps


def get_system_capabilities(config: Optional[dict] = None) -> SystemCapabilities:
    """
    Get system capabilities, optionally with config for AI provider info.

    Args:
        config: Optional configuration dictionary with AI provider settings

    Returns:
        SystemCapabilities instance with detected resources and recommendations
    """
    if config:
        return SystemCapabilities.from_config(config)
    return SystemCapabilities.detect()
