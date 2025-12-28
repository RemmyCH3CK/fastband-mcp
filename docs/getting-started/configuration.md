# Configuration Reference

Complete reference for Fastband MCP configuration options.

## Configuration File

Fastband stores configuration in `.fastband/config.yaml` in your project directory.

### Full Configuration Example

```yaml
fastband:
  version: "1.2025.12"

  # Project information (auto-detected or manual)
  project:
    name: "my-app"
    type: "web"
    language: "python"

  # AI Provider configuration
  ai:
    default_provider: "claude"
    providers:
      claude:
        model: "claude-sonnet-4-20250514"
        max_tokens: 4096
        temperature: 0.7
      openai:
        model: "gpt-4-turbo"
        max_tokens: 4096
        temperature: 0.7
      gemini:
        model: "gemini-pro"
        max_tokens: 4096
        temperature: 0.7
      ollama:
        model: "llama3"
        base_url: "http://localhost:11434"
        max_tokens: 4096
        temperature: 0.7

  # Tool garage settings
  tools:
    max_active: 60
    auto_load_core: true
    performance_warning_threshold: 40

  # Ticket manager settings
  tickets:
    enabled: true
    mode: "cli_web"
    web_port: 5050
    review_agents: true

  # Backup settings
  backup:
    enabled: true
    daily_enabled: true
    daily_time: "02:00"
    daily_retention: 7
    weekly_enabled: true
    weekly_day: "sunday"
    weekly_retention: 4
    change_detection: true

  # GitHub integration
  github:
    enabled: false
    automation_level: "hybrid"
    default_branch: "main"

  # Storage backend
  storage:
    backend: "sqlite"
    path: ".fastband/data.db"
```

## Configuration Sections

### Project Settings

```yaml
project:
  name: "my-app"           # Project name (auto-detected from package.json, pyproject.toml, etc.)
  type: "web"              # Project type: web, api, desktop, mobile, library, cli
  language: "python"       # Primary language: python, javascript, typescript, go, rust
```

These are typically auto-detected during `fastband init`.

### AI Provider Settings

```yaml
ai:
  default_provider: "claude"   # Which provider to use by default
  providers:
    claude:
      model: "claude-sonnet-4-20250514"
      max_tokens: 4096
      temperature: 0.7
```

#### Available Models

| Provider | Model Options |
|----------|---------------|
| Claude | `claude-sonnet-4-20250514`, `claude-opus-4-20250514`, `claude-3.5-sonnet` |
| OpenAI | `gpt-4-turbo`, `gpt-4`, `gpt-3.5-turbo` |
| Gemini | `gemini-pro`, `gemini-pro-vision` |
| Ollama | Any model you have pulled locally |

#### Provider Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `model` | string | varies | Model identifier |
| `api_key` | string | from env | API key (prefer environment variables) |
| `base_url` | string | provider default | Custom API endpoint |
| `max_tokens` | int | 4096 | Maximum tokens in response |
| `temperature` | float | 0.7 | Response randomness (0.0-1.0) |

### Tool Garage Settings

```yaml
tools:
  max_active: 60                        # Maximum tools loaded at once
  auto_load_core: true                  # Automatically load core tools
  performance_warning_threshold: 40     # Warn when this many tools active
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_active` | int | 60 | Maximum number of active tools |
| `auto_load_core` | bool | true | Load core tools on startup |
| `performance_warning_threshold` | int | 40 | Show warning when exceeded |

### Ticket Manager Settings

```yaml
tickets:
  enabled: true         # Enable ticket management
  mode: "cli_web"       # Interface mode
  web_port: 5050        # Web dashboard port
  review_agents: true   # Enable AI code review agents
```

#### Ticket Modes

| Mode | Description |
|------|-------------|
| `cli` | Command-line only |
| `cli_web` | CLI + Web dashboard |
| `embedded` | Embedded in desktop apps (Ctrl+Shift+T) |

### Backup Settings

```yaml
backup:
  enabled: true          # Enable automatic backups
  daily_enabled: true    # Run daily backups
  daily_time: "02:00"    # Time for daily backup (24h format)
  daily_retention: 7     # Keep 7 daily backups
  weekly_enabled: true   # Run weekly backups
  weekly_day: "sunday"   # Day for weekly backup
  weekly_retention: 4    # Keep 4 weekly backups
  change_detection: true # Only backup if changes detected
```

### GitHub Integration

```yaml
github:
  enabled: false              # Enable GitHub integration
  automation_level: "hybrid"  # Automation level
  default_branch: "main"      # Default branch for PRs
```

#### Automation Levels

| Level | Description |
|-------|-------------|
| `none` | No automation, manual only |
| `guided` | Suggestions only, human confirms |
| `hybrid` | Auto for simple tasks, guided for complex |
| `full` | Fully automated (use with caution) |

### Storage Backend

```yaml
storage:
  backend: "sqlite"            # Database type
  path: ".fastband/data.db"    # Database file/connection
```

#### Storage Options

| Backend | Path Format | Requirements |
|---------|-------------|--------------|
| `sqlite` | File path | None (built-in) |
| `postgres` | Connection URI | `pip install fastband-mcp[postgres]` |
| `mysql` | Connection URI | `pip install fastband-mcp[mysql]` |
| `file` | Directory path | None (JSON files) |

PostgreSQL example:
```yaml
storage:
  backend: "postgres"
  path: "postgresql://user:pass@localhost/fastband"
```

## Environment Variables

Fastband reads these environment variables:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `GOOGLE_API_KEY` | Gemini API key |
| `FASTBAND_SECRET_KEY` | Secret key for web sessions |
| `FASTBAND_CONFIG_PATH` | Override config file location |

## CLI Configuration Commands

### View Configuration

```bash
# Show full config as YAML
fastband config show

# Show as JSON
fastband config show --json
```

### Get Specific Values

```bash
fastband config get ai.default_provider
fastband config get tools.max_active
fastband config get tickets.web_port
```

### Set Values

```bash
# String values
fastband config set ai.default_provider openai

# Numeric values
fastband config set tools.max_active 40
fastband config set tickets.web_port 8080

# Boolean values
fastband config set tickets.enabled true
fastband config set backup.change_detection false
```

### Reset Configuration

```bash
# Reset to defaults (with confirmation)
fastband config reset

# Skip confirmation
fastband config reset --yes
```

## Configuration Precedence

Configuration is loaded in this order (later overrides earlier):

1. Default values (built into code)
2. `.fastband/config.yaml` file
3. Environment variables
4. CLI arguments

## Validating Configuration

The configuration is validated when loaded. Invalid values will show an error:

```bash
# This will validate your config
fastband status
```

Common validation errors:

- Invalid provider name
- Port number out of range (1-65535)
- Invalid automation level
- Missing required fields
