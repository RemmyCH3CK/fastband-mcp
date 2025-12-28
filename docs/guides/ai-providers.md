# AI Providers Guide

Fastband MCP supports multiple AI providers through a unified interface. This guide covers how to configure and use each provider effectively.

## Provider Architecture

All providers implement the `AIProvider` base class, ensuring consistent behavior:

```python
from fastband.providers import get_provider

# Get any provider by name
provider = get_provider("claude")  # or "openai", "gemini", "ollama"

# All providers have the same interface
response = await provider.complete("Your prompt here")
```

## Supported Providers

### Claude (Anthropic)

Claude is the recommended provider for code generation and complex reasoning tasks.

#### Setup

```bash
# Install Claude support
pip install fastband-mcp[claude]

# Set API key
export ANTHROPIC_API_KEY="your-api-key"
```

#### Configuration

```yaml
# .fastband/config.yaml
fastband:
  ai:
    default_provider: "claude"
    providers:
      claude:
        model: "claude-sonnet-4-20250514"
        max_tokens: 4096
        temperature: 0.7
```

#### Available Models

| Model | Best For | Context Window |
|-------|----------|----------------|
| `claude-opus-4-20250514` | Complex reasoning, extended thinking | 200K |
| `claude-sonnet-4-20250514` | Balanced performance/cost | 200K |
| `claude-3.5-sonnet` | Fast, efficient coding | 200K |

#### Capabilities

- Text completion
- Code generation
- Vision (image analysis)
- Function/tool calling
- Streaming responses
- Extended thinking

#### Usage Example

```python
from fastband.providers import get_provider
from fastband.providers.base import Capability

claude = get_provider("claude")

# Check capabilities
if claude.supports(Capability.VISION):
    print("Vision supported!")

# Basic completion
response = await claude.complete(
    prompt="Explain this Python code...",
    system_prompt="You are a helpful coding assistant."
)
print(response.content)

# With streaming
async for chunk in claude.stream("Tell me about async programming"):
    print(chunk, end="")

# With tool calling
tools = [{
    "name": "read_file",
    "description": "Read a file from disk",
    "parameters": {...}
}]
response = await claude.complete_with_tools(
    prompt="Read the README file",
    tools=tools
)
```

### OpenAI

GPT-4 and GPT-3.5 models for versatile AI capabilities.

#### Setup

```bash
# Install OpenAI support
pip install fastband-mcp[openai]

# Set API key
export OPENAI_API_KEY="your-api-key"
```

#### Configuration

```yaml
fastband:
  ai:
    providers:
      openai:
        model: "gpt-4-turbo"
        max_tokens: 4096
        temperature: 0.7
```

#### Available Models

| Model | Best For | Context Window |
|-------|----------|----------------|
| `gpt-4-turbo` | Latest, best quality | 128K |
| `gpt-4` | Stable, high quality | 8K |
| `gpt-3.5-turbo` | Fast, cost-effective | 16K |

#### Capabilities

- Text completion
- Code generation
- Vision (GPT-4 Vision)
- Function calling
- Streaming responses

#### Usage Example

```python
from fastband.providers import get_provider

openai = get_provider("openai")

# Completion with specific model
response = await openai.complete(
    prompt="Write a Python function to sort a list",
    model="gpt-4-turbo"  # Override default model
)

# Image analysis (GPT-4 Vision)
with open("screenshot.png", "rb") as f:
    image_data = f.read()

response = await openai.analyze_image(
    image_data=image_data,
    prompt="What's shown in this screenshot?"
)
```

### Google Gemini

Google's multimodal AI models.

#### Setup

```bash
# Install Gemini support
pip install fastband-mcp[gemini]

# Set API key
export GOOGLE_API_KEY="your-api-key"
```

#### Configuration

```yaml
fastband:
  ai:
    providers:
      gemini:
        model: "gemini-pro"
        max_tokens: 4096
        temperature: 0.7
```

#### Available Models

| Model | Best For | Context Window |
|-------|----------|----------------|
| `gemini-pro` | Text and code | 32K |
| `gemini-pro-vision` | Multimodal tasks | 32K |

#### Capabilities

- Text completion
- Code generation
- Vision (with gemini-pro-vision)
- Streaming responses

#### Usage Example

```python
from fastband.providers import get_provider

gemini = get_provider("gemini")

response = await gemini.complete(
    prompt="Explain machine learning",
    system_prompt="You are a helpful AI tutor."
)
```

### Ollama (Local LLMs)

Run models locally without API costs or internet connectivity.

#### Setup

1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Pull models you want to use:

```bash
ollama pull llama3
ollama pull codellama
ollama pull mistral
```

3. Install Fastband support:

```bash
pip install fastband-mcp[ollama]
```

#### Configuration

```yaml
fastband:
  ai:
    providers:
      ollama:
        model: "llama3"
        base_url: "http://localhost:11434"
        max_tokens: 4096
        temperature: 0.7
```

#### Available Models

Any model you pull with Ollama. Popular options:

| Model | Best For | Size |
|-------|----------|------|
| `llama3` | General purpose | 8B |
| `codellama` | Code generation | 7B-34B |
| `mistral` | Fast, efficient | 7B |
| `mixtral` | High quality | 47B |

#### Capabilities

- Text completion
- Code generation
- Streaming responses

#### Usage Example

```python
from fastband.providers import get_provider

ollama = get_provider("ollama")

# Use specific local model
response = await ollama.complete(
    prompt="Refactor this code for better performance",
    model="codellama"
)
```

## Switching Between Providers

### Programmatically

```python
from fastband.providers import get_provider, set_default_provider

# Use default provider
provider = get_provider()  # Uses ai.default_provider from config

# Get specific provider
claude = get_provider("claude")
openai = get_provider("openai")

# Change default at runtime
set_default_provider("openai")
```

### Via CLI

```bash
# Change default provider
fastband config set ai.default_provider openai

# Check current setting
fastband config get ai.default_provider
```

## Provider Capabilities

Check what each provider can do:

```python
from fastband.providers import get_provider
from fastband.providers.base import Capability

provider = get_provider("claude")

# Check specific capability
if provider.supports(Capability.VISION):
    # Use image analysis
    pass

if provider.supports(Capability.STREAMING):
    # Use streaming responses
    pass

if provider.supports(Capability.FUNCTION_CALLING):
    # Use tool calling
    pass

# Get all capabilities
print(provider.capabilities)
# [Capability.TEXT_COMPLETION, Capability.CODE_GENERATION, ...]
```

### Capability Matrix

| Capability | Claude | OpenAI | Gemini | Ollama |
|------------|--------|--------|--------|--------|
| Text Completion | Yes | Yes | Yes | Yes |
| Code Generation | Yes | Yes | Yes | Yes |
| Vision | Yes | Yes* | Yes* | No |
| Function Calling | Yes | Yes | No | No |
| Streaming | Yes | Yes | Yes | Yes |
| Long Context | Yes | Yes | Yes | Varies |
| Extended Thinking | Yes | No | No | No |

*Requires specific models (GPT-4V, gemini-pro-vision)

## Best Practices

### 1. Use Environment Variables for API Keys

Never commit API keys to version control:

```bash
# Good - use environment variables
export ANTHROPIC_API_KEY="sk-..."

# Bad - don't put in config file
# api_key: "sk-..."  # NEVER DO THIS
```

### 2. Choose the Right Model for the Task

```python
# Complex reasoning - use most capable model
response = await provider.complete(
    prompt="Analyze this architecture...",
    model="claude-opus-4-20250514"
)

# Simple tasks - use faster/cheaper model
response = await provider.complete(
    prompt="Format this JSON",
    model="claude-3.5-sonnet"
)
```

### 3. Handle Provider Errors

```python
from fastband.providers import get_provider, ProviderError

try:
    provider = get_provider("claude")
    response = await provider.complete("...")
except ProviderError as e:
    print(f"Provider error: {e}")
    # Fall back to another provider
    provider = get_provider("openai")
    response = await provider.complete("...")
```

### 4. Use Streaming for Long Responses

```python
# For long responses, streaming provides better UX
async for chunk in provider.stream(long_prompt):
    print(chunk, end="", flush=True)
```

## Custom Provider Configuration

For advanced use cases, configure providers programmatically:

```python
from fastband.providers import register_provider
from fastband.providers.base import AIProvider, ProviderConfig

# Register a custom provider configuration
config = ProviderConfig(
    name="custom-claude",
    api_key="your-key",
    model="claude-opus-4-20250514",
    max_tokens=8192,
    temperature=0.5
)

provider = get_provider("claude", config=config)
```

## Troubleshooting

### "API key not found"

Ensure your API key environment variable is set:

```bash
echo $ANTHROPIC_API_KEY  # Should show your key (or part of it)
```

### "Model not found" (Ollama)

Pull the model first:

```bash
ollama pull llama3
```

### Rate limiting

Handle rate limits gracefully:

```python
import asyncio
from fastband.providers import get_provider

async def with_retry(prompt, max_retries=3):
    provider = get_provider()
    for attempt in range(max_retries):
        try:
            return await provider.complete(prompt)
        except RateLimitError:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    raise Exception("Max retries exceeded")
```
