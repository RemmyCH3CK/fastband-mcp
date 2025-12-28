# Providers API Reference

Complete API documentation for Fastband's AI provider system.

## Module: `fastband.providers`

### Functions

#### `get_provider(name: str = None, config: ProviderConfig = None) -> AIProvider`

Get an AI provider instance.

**Parameters:**
- `name` (str, optional): Provider name ("claude", "openai", "gemini", "ollama"). If None, uses default from config.
- `config` (ProviderConfig, optional): Custom configuration to use instead of project config.

**Returns:**
- `AIProvider`: Configured provider instance.

**Raises:**
- `ProviderNotFoundError`: If provider name is not recognized.
- `ProviderConfigError`: If configuration is invalid.

**Example:**
```python
from fastband.providers import get_provider

# Get default provider
provider = get_provider()

# Get specific provider
claude = get_provider("claude")
openai = get_provider("openai")

# With custom config
from fastband.providers.base import ProviderConfig
config = ProviderConfig(
    name="claude",
    model="claude-opus-4-20250514",
    max_tokens=8192
)
provider = get_provider("claude", config=config)
```

---

#### `register_provider(name: str, provider_class: Type[AIProvider]) -> None`

Register a custom provider class.

**Parameters:**
- `name` (str): Unique provider name.
- `provider_class` (Type[AIProvider]): Provider class implementing AIProvider.

**Example:**
```python
from fastband.providers import register_provider
from fastband.providers.base import AIProvider

class CustomProvider(AIProvider):
    # ... implementation
    pass

register_provider("custom", CustomProvider)
```

---

#### `set_default_provider(name: str) -> None`

Set the default provider for the current session.

**Parameters:**
- `name` (str): Provider name to use as default.

**Example:**
```python
from fastband.providers import set_default_provider

set_default_provider("openai")
```

---

## Class: `AIProvider`

Abstract base class for all AI providers.

**Module:** `fastband.providers.base`

### Properties

#### `name: str`

Provider name (e.g., "claude", "openai").

**Returns:** str

---

#### `capabilities: List[Capability]`

List of supported capabilities.

**Returns:** List[Capability]

---

#### `config: ProviderConfig`

Provider configuration.

**Returns:** ProviderConfig

---

### Methods

#### `async complete(prompt: str, system_prompt: str = None, **kwargs) -> CompletionResponse`

Send a completion request.

**Parameters:**
- `prompt` (str): The user prompt.
- `system_prompt` (str, optional): System instructions.
- `**kwargs`: Provider-specific options.

**Returns:** CompletionResponse

**Example:**
```python
response = await provider.complete(
    prompt="Explain recursion in Python",
    system_prompt="You are a helpful coding tutor."
)
print(response.content)
```

---

#### `async complete_with_tools(prompt: str, tools: List[Dict], system_prompt: str = None, **kwargs) -> CompletionResponse`

Complete with tool/function calling support.

**Parameters:**
- `prompt` (str): The user prompt.
- `tools` (List[Dict]): Tool definitions.
- `system_prompt` (str, optional): System instructions.
- `**kwargs`: Provider-specific options.

**Returns:** CompletionResponse

**Example:**
```python
tools = [{
    "name": "read_file",
    "description": "Read a file from disk",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"}
        },
        "required": ["path"]
    }
}]

response = await provider.complete_with_tools(
    prompt="Read the config.yaml file",
    tools=tools
)
```

---

#### `async stream(prompt: str, system_prompt: str = None, **kwargs) -> AsyncIterator[str]`

Stream completion response.

**Parameters:**
- `prompt` (str): The user prompt.
- `system_prompt` (str, optional): System instructions.
- `**kwargs`: Provider-specific options.

**Yields:** str - Response chunks.

**Example:**
```python
async for chunk in provider.stream("Tell me a story"):
    print(chunk, end="", flush=True)
```

---

#### `async analyze_image(image_data: bytes, prompt: str, **kwargs) -> CompletionResponse`

Analyze an image (vision capability).

**Parameters:**
- `image_data` (bytes): Raw image data.
- `prompt` (str): Analysis prompt.
- `**kwargs`: Provider-specific options.

**Returns:** CompletionResponse

**Raises:** NotImplementedError if provider doesn't support vision.

**Example:**
```python
with open("screenshot.png", "rb") as f:
    image_data = f.read()

response = await provider.analyze_image(
    image_data=image_data,
    prompt="What's shown in this image?"
)
```

---

#### `supports(capability: Capability) -> bool`

Check if provider supports a capability.

**Parameters:**
- `capability` (Capability): Capability to check.

**Returns:** bool

**Example:**
```python
from fastband.providers.base import Capability

if provider.supports(Capability.VISION):
    # Use vision features
    pass
```

---

#### `get_recommended_model(task: str) -> str`

Get recommended model for a specific task type.

**Parameters:**
- `task` (str): Task description.

**Returns:** str - Model identifier.

---

## Class: `ProviderConfig`

Configuration for an AI provider.

**Module:** `fastband.providers.base`

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | required | Provider name |
| `api_key` | Optional[str] | None | API key (prefer env vars) |
| `base_url` | Optional[str] | None | Custom API endpoint |
| `model` | Optional[str] | None | Model identifier |
| `max_tokens` | int | 4096 | Maximum response tokens |
| `temperature` | float | 0.7 | Response randomness (0-1) |
| `timeout` | int | 120 | Request timeout in seconds |
| `extra` | Dict[str, Any] | {} | Provider-specific options |

**Example:**
```python
from fastband.providers.base import ProviderConfig

config = ProviderConfig(
    name="claude",
    model="claude-sonnet-4-20250514",
    max_tokens=8192,
    temperature=0.5,
    extra={"top_p": 0.9}
)
```

---

## Class: `CompletionResponse`

Standardized response from any AI provider.

**Module:** `fastband.providers.base`

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `content` | str | Generated text content |
| `model` | str | Model that generated the response |
| `provider` | str | Provider name |
| `usage` | Dict[str, int] | Token usage stats |
| `finish_reason` | str | Why generation stopped |
| `raw_response` | Optional[Dict] | Original API response |

**Example:**
```python
response = await provider.complete("Hello")

print(response.content)       # "Hello! How can I help?"
print(response.model)         # "claude-sonnet-4-20250514"
print(response.provider)      # "claude"
print(response.usage)         # {"input_tokens": 5, "output_tokens": 10}
print(response.finish_reason) # "stop"
```

---

## Enum: `Capability`

AI provider capabilities.

**Module:** `fastband.providers.base`

### Values

| Value | Description |
|-------|-------------|
| `TEXT_COMPLETION` | Basic text generation |
| `CODE_GENERATION` | Code-specific generation |
| `VISION` | Image analysis |
| `FUNCTION_CALLING` | Tool/function calling |
| `STREAMING` | Streaming responses |
| `LONG_CONTEXT` | Extended context window |
| `EXTENDED_THINKING` | Extended thinking/reasoning |

**Example:**
```python
from fastband.providers.base import Capability

if Capability.VISION in provider.capabilities:
    # Vision is supported
    pass
```

---

## Provider-Specific Classes

### ClaudeProvider

Claude (Anthropic) provider implementation.

**Module:** `fastband.providers.claude`

**Default Model:** `claude-sonnet-4-20250514`

**Capabilities:**
- TEXT_COMPLETION
- CODE_GENERATION
- VISION
- FUNCTION_CALLING
- STREAMING
- LONG_CONTEXT
- EXTENDED_THINKING

**Extra Configuration:**
```python
config = ProviderConfig(
    name="claude",
    extra={
        "top_p": 0.9,
        "top_k": 40,
    }
)
```

---

### OpenAIProvider

OpenAI provider implementation.

**Module:** `fastband.providers.openai`

**Default Model:** `gpt-4-turbo`

**Capabilities:**
- TEXT_COMPLETION
- CODE_GENERATION
- VISION (GPT-4V models)
- FUNCTION_CALLING
- STREAMING
- LONG_CONTEXT

**Extra Configuration:**
```python
config = ProviderConfig(
    name="openai",
    extra={
        "frequency_penalty": 0.5,
        "presence_penalty": 0.5,
    }
)
```

---

### GeminiProvider

Google Gemini provider implementation.

**Module:** `fastband.providers.gemini`

**Default Model:** `gemini-pro`

**Capabilities:**
- TEXT_COMPLETION
- CODE_GENERATION
- VISION (gemini-pro-vision)
- STREAMING

---

### OllamaProvider

Ollama local LLM provider implementation.

**Module:** `fastband.providers.ollama`

**Default Model:** None (must be specified)

**Default Base URL:** `http://localhost:11434`

**Capabilities:**
- TEXT_COMPLETION
- CODE_GENERATION
- STREAMING

**Extra Configuration:**
```python
config = ProviderConfig(
    name="ollama",
    base_url="http://localhost:11434",
    model="llama3",
    extra={
        "num_ctx": 4096,
    }
)
```

---

## Exceptions

### `ProviderError`

Base exception for provider errors.

**Module:** `fastband.providers`

---

### `ProviderNotFoundError`

Raised when a provider is not found.

**Module:** `fastband.providers`

---

### `ProviderConfigError`

Raised when provider configuration is invalid.

**Module:** `fastband.providers`

---

### `RateLimitError`

Raised when API rate limit is exceeded.

**Module:** `fastband.providers`

---

## Provider Registry

### Class: `ProviderRegistry`

Manages provider registration and instantiation.

**Module:** `fastband.providers.registry`

#### Methods

##### `register(name: str, provider_class: Type[AIProvider]) -> None`

Register a provider class.

##### `get(name: str, config: ProviderConfig = None) -> AIProvider`

Get a provider instance.

##### `list_providers() -> List[str]`

List registered provider names.

##### `is_registered(name: str) -> bool`

Check if a provider is registered.

**Example:**
```python
from fastband.providers.registry import ProviderRegistry

registry = ProviderRegistry()
registry.register("custom", CustomProvider)

if registry.is_registered("custom"):
    provider = registry.get("custom")

print(registry.list_providers())
# ["claude", "openai", "gemini", "ollama", "custom"]
```
