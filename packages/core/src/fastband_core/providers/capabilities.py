"""
Provider capability definitions.

Defines capabilities that providers can support, enabling runtime
capability checking and feature-based provider selection.

Architecture Rules:
- No side effects on import
- No external SDK imports
- No framework imports
- All types are pure data definitions
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =============================================================================
# CAPABILITY DEFINITIONS
# =============================================================================


class Capability(str, Enum):
    """
    AI provider capabilities.

    Used to declare what features a provider supports, enabling
    runtime capability checking and provider selection.
    """

    # Core capabilities
    TEXT_COMPLETION = "text_completion"
    CODE_GENERATION = "code_generation"
    CHAT = "chat"

    # Advanced capabilities
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    TOOL_USE = "tool_use"
    STREAMING = "streaming"

    # Context capabilities
    LONG_CONTEXT = "long_context"
    EXTENDED_THINKING = "extended_thinking"
    MULTI_TURN = "multi_turn"

    # Output capabilities
    JSON_MODE = "json_mode"
    STRUCTURED_OUTPUT = "structured_output"

    # Embedding capabilities
    EMBEDDINGS = "embeddings"
    BATCH_EMBEDDINGS = "batch_embeddings"

    # Speech capabilities
    TEXT_TO_SPEECH = "text_to_speech"
    SPEECH_TO_TEXT = "speech_to_text"

    # Image capabilities
    IMAGE_GENERATION = "image_generation"
    IMAGE_EDITING = "image_editing"


class CapabilityLevel(str, Enum):
    """
    Level of capability support.

    Indicates how well a provider supports a capability.
    """

    FULL = "full"  # Full, production-ready support
    BETA = "beta"  # Beta/preview support
    LIMITED = "limited"  # Limited or partial support
    NONE = "none"  # Not supported


# =============================================================================
# CAPABILITY METADATA
# =============================================================================


@dataclass(frozen=True, slots=True)
class CapabilityInfo:
    """
    Detailed information about a capability.

    Provides metadata about a capability including support level,
    constraints, and documentation.
    """

    capability: Capability
    level: CapabilityLevel = CapabilityLevel.FULL
    max_tokens: int | None = None  # Token limit for this capability
    max_images: int | None = None  # Image limit for vision
    supported_formats: tuple[str, ...] = ()  # Supported file formats
    notes: str | None = None  # Usage notes or limitations
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_supported(self) -> bool:
        """Check if capability is supported at any level."""
        return self.level != CapabilityLevel.NONE

    @property
    def is_production_ready(self) -> bool:
        """Check if capability is production-ready."""
        return self.level == CapabilityLevel.FULL

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "capability": self.capability.value,
            "level": self.level.value,
            "max_tokens": self.max_tokens,
            "max_images": self.max_images,
            "supported_formats": list(self.supported_formats),
            "notes": self.notes,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityInfo":
        """Create from dictionary."""
        return cls(
            capability=Capability(data["capability"]),
            level=CapabilityLevel(data.get("level", "full")),
            max_tokens=data.get("max_tokens"),
            max_images=data.get("max_images"),
            supported_formats=tuple(data.get("supported_formats", [])),
            notes=data.get("notes"),
            extra=data.get("extra", {}),
        )


# =============================================================================
# CAPABILITY SET
# =============================================================================


@dataclass(frozen=True, slots=True)
class CapabilitySet:
    """
    A set of capabilities with their metadata.

    Provides convenient methods for checking capability support
    and comparing capability sets.
    """

    capabilities: tuple[CapabilityInfo, ...] = ()

    def supports(self, capability: Capability) -> bool:
        """Check if a capability is supported."""
        return any(
            c.capability == capability and c.is_supported for c in self.capabilities
        )

    def supports_all(self, *capabilities: Capability) -> bool:
        """Check if all specified capabilities are supported."""
        return all(self.supports(cap) for cap in capabilities)

    def supports_any(self, *capabilities: Capability) -> bool:
        """Check if any of the specified capabilities is supported."""
        return any(self.supports(cap) for cap in capabilities)

    def get(self, capability: Capability) -> CapabilityInfo | None:
        """Get capability info if supported."""
        for cap_info in self.capabilities:
            if cap_info.capability == capability:
                return cap_info
        return None

    def get_level(self, capability: Capability) -> CapabilityLevel:
        """Get support level for a capability."""
        cap_info = self.get(capability)
        return cap_info.level if cap_info else CapabilityLevel.NONE

    def list_supported(self) -> list[Capability]:
        """List all supported capabilities."""
        return [c.capability for c in self.capabilities if c.is_supported]

    def list_production_ready(self) -> list[Capability]:
        """List production-ready capabilities."""
        return [c.capability for c in self.capabilities if c.is_production_ready]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {"capabilities": [c.to_dict() for c in self.capabilities]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilitySet":
        """Create from dictionary."""
        return cls(
            capabilities=tuple(
                CapabilityInfo.from_dict(c) for c in data.get("capabilities", [])
            )
        )

    @classmethod
    def from_capabilities(cls, *capabilities: Capability) -> "CapabilitySet":
        """Create from a list of capabilities with default (full) support."""
        return cls(
            capabilities=tuple(
                CapabilityInfo(capability=cap) for cap in capabilities
            )
        )


# =============================================================================
# MODEL INFORMATION
# =============================================================================


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """
    Information about a specific model.

    Provides metadata about a model's capabilities, limits, and pricing.
    """

    model_id: str
    provider: str
    display_name: str | None = None
    description: str | None = None
    capabilities: CapabilitySet = field(default_factory=CapabilitySet)
    context_window: int = 0  # Max context tokens
    max_output_tokens: int = 0  # Max output tokens
    input_price_per_1k: float | None = None  # Price per 1K input tokens
    output_price_per_1k: float | None = None  # Price per 1K output tokens
    deprecated: bool = False
    deprecation_date: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Get display name or model ID."""
        return self.display_name or self.model_id

    def supports(self, capability: Capability) -> bool:
        """Check if model supports a capability."""
        return self.capabilities.supports(capability)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "display_name": self.display_name,
            "description": self.description,
            "capabilities": self.capabilities.to_dict(),
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "input_price_per_1k": self.input_price_per_1k,
            "output_price_per_1k": self.output_price_per_1k,
            "deprecated": self.deprecated,
            "deprecation_date": self.deprecation_date,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelInfo":
        """Create from dictionary."""
        return cls(
            model_id=data["model_id"],
            provider=data.get("provider", ""),
            display_name=data.get("display_name"),
            description=data.get("description"),
            capabilities=CapabilitySet.from_dict(data.get("capabilities", {})),
            context_window=data.get("context_window", 0),
            max_output_tokens=data.get("max_output_tokens", 0),
            input_price_per_1k=data.get("input_price_per_1k"),
            output_price_per_1k=data.get("output_price_per_1k"),
            deprecated=data.get("deprecated", False),
            deprecation_date=data.get("deprecation_date"),
            extra=data.get("extra", {}),
        )


# =============================================================================
# CAPABILITY REQUIREMENTS
# =============================================================================


@dataclass(frozen=True, slots=True)
class CapabilityRequirements:
    """
    Requirements specification for provider/model selection.

    Used to specify what capabilities are needed for a task.
    """

    required: tuple[Capability, ...] = ()
    preferred: tuple[Capability, ...] = ()
    min_context_window: int = 0
    min_output_tokens: int = 0

    def is_satisfied_by(self, capabilities: CapabilitySet) -> bool:
        """Check if requirements are satisfied by a capability set."""
        return all(capabilities.supports(cap) for cap in self.required)

    def score_match(
        self, capabilities: CapabilitySet, model_info: ModelInfo | None = None
    ) -> float:
        """
        Score how well a capability set matches requirements.

        Returns a score from 0.0 to 1.0, where 1.0 is a perfect match.
        """
        if not self.is_satisfied_by(capabilities):
            return 0.0

        score = 1.0

        # Add bonus for preferred capabilities
        if self.preferred:
            preferred_count = sum(
                1 for cap in self.preferred if capabilities.supports(cap)
            )
            score += (preferred_count / len(self.preferred)) * 0.5

        # Check context/output requirements if model info provided
        if model_info:
            if self.min_context_window > 0:
                if model_info.context_window < self.min_context_window:
                    return 0.0
            if self.min_output_tokens > 0:
                if model_info.max_output_tokens < self.min_output_tokens:
                    return 0.0

        return min(score, 1.5) / 1.5  # Normalize to 0.0-1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "required": [c.value for c in self.required],
            "preferred": [c.value for c in self.preferred],
            "min_context_window": self.min_context_window,
            "min_output_tokens": self.min_output_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityRequirements":
        """Create from dictionary."""
        return cls(
            required=tuple(Capability(c) for c in data.get("required", [])),
            preferred=tuple(Capability(c) for c in data.get("preferred", [])),
            min_context_window=data.get("min_context_window", 0),
            min_output_tokens=data.get("min_output_tokens", 0),
        )
