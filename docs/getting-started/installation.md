# Installation Guide

This guide covers installing Fastband MCP on your system.

## Requirements

- **Python 3.10 or higher** - Fastband requires Python 3.10+ for full async support
- **pip** - Python package manager
- **Git** - For version control integration (optional but recommended)

## Installation Options

### Basic Installation

The simplest way to install Fastband MCP:

```bash
pip install fastband-mcp
```

This installs the core functionality with minimal dependencies.

### Installation with AI Providers

Install with support for specific AI providers:

```bash
# Claude (Anthropic) support
pip install fastband-mcp[claude]

# OpenAI support
pip install fastband-mcp[openai]

# Google Gemini support
pip install fastband-mcp[gemini]

# Ollama (local LLMs) support
pip install fastband-mcp[ollama]

# All AI providers
pip install fastband-mcp[all-providers]
```

### Full Installation

Install all features including web dashboard, screenshots, and database support:

```bash
pip install fastband-mcp[full]
```

This includes:
- All AI providers (Claude, OpenAI, Gemini, Ollama)
- Web dashboard (FastAPI, Uvicorn, Jinja2)
- Screenshot capabilities (Playwright, Pillow)
- PostgreSQL and MySQL support
- Development tools (pytest, ruff, mypy)

### Specific Feature Sets

Install only the features you need:

```bash
# Web dashboard support
pip install fastband-mcp[web]

# Screenshot and browser automation
pip install fastband-mcp[screenshots]

# PostgreSQL database backend
pip install fastband-mcp[postgres]

# MySQL database backend
pip install fastband-mcp[mysql]

# Development dependencies
pip install fastband-mcp[dev]
```

## Setting Up API Keys

### Claude (Anthropic)

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

Or add to your shell profile (`~/.bashrc`, `~/.zshrc`):

```bash
echo 'export ANTHROPIC_API_KEY="your-api-key"' >> ~/.zshrc
```

### OpenAI

```bash
export OPENAI_API_KEY="your-api-key"
```

### Google Gemini

```bash
export GOOGLE_API_KEY="your-api-key"
```

### Ollama (Local)

Ollama runs locally and doesn't require an API key. Install Ollama from [ollama.ai](https://ollama.ai) and pull your desired models:

```bash
ollama pull llama3
ollama pull codellama
```

## Verifying Installation

After installation, verify everything is working:

```bash
# Check version
fastband --version

# Show help
fastband --help

# Check status (after initializing a project)
fastband status
```

Expected output for version check:

```
fastband version 1.2025.12.0-alpha.1
```

## Development Installation

For contributing to Fastband MCP:

```bash
# Clone the repository
git clone https://github.com/RemmyCH3CK/fastband-mcp
cd fastband-mcp

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest
```

## Docker Installation

Run Fastband in a Docker container:

```dockerfile
FROM python:3.11-slim

RUN pip install fastband-mcp[full]

WORKDIR /app
COPY . .

CMD ["fastband", "serve"]
```

Build and run:

```bash
docker build -t fastband .
docker run -v $(pwd):/app fastband
```

## Troubleshooting

### "Command not found: fastband"

Ensure your Python scripts directory is in your PATH:

```bash
# For pip user installations
export PATH="$HOME/.local/bin:$PATH"

# Or use the module directly
python -m fastband --version
```

### Playwright not working

Install Playwright browsers:

```bash
playwright install chromium
```

### Permission errors on Linux

Use user installation:

```bash
pip install --user fastband-mcp
```

## Next Steps

After installation:

1. [MCP Setup Guide](mcp-setup.md) - Connect Fastband to Claude Code/Desktop
2. [Quick Start Tutorial](quickstart.md) - Learn the CLI commands
3. [Configuration Reference](configuration.md) - Customize your setup
4. [AI Providers Guide](../guides/ai-providers.md) - Configure AI providers
