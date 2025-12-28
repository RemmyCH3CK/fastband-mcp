# Web App Demo

A simple Flask web application demonstrating how to use Fastband MCP for AI-assisted web development.

## Overview

This example shows how Fastband MCP can help you:
- Manage development tasks with the ticket system
- Use AI-powered tools for code generation and assistance
- Track file changes and development progress

## Prerequisites

- Python 3.10+
- Fastband MCP installed (`pip install fastband-mcp`)

## Setup

1. **Install dependencies:**

   ```bash
   cd examples/web-app-demo
   pip install -r requirements.txt
   ```

2. **Initialize Fastband:**

   The `.fastband/` directory is already configured, but you can reinitialize:

   ```bash
   fastband init --force
   ```

3. **Check status:**

   ```bash
   fastband status
   ```

## Running the App

```bash
# Start the Flask development server
python app.py
```

Visit http://localhost:5001 to see the app.

## Development Workflow with Fastband

### 1. Check Available Tools

```bash
fastband tools list
```

### 2. Create a Development Ticket

```bash
fastband tickets create --title "Add user profile page" \
    --type feature \
    --priority medium \
    --description "Create a user profile page with avatar and bio"
```

### 3. Claim the Ticket

```bash
fastband tickets claim 1 --agent "Developer"
```

### 4. Start the MCP Server

For AI-assisted development, start the MCP server:

```bash
fastband serve
```

This allows AI clients (like Claude Code) to use Fastband tools.

### 5. Complete the Ticket

```bash
fastband tickets complete 1 \
    --problem "No user profile page existed" \
    --solution "Created profile.html template with user info display" \
    --files "templates/profile.html,app.py"
```

## Project Structure

```
web-app-demo/
├── .fastband/
│   └── config.yaml      # Fastband configuration
├── app.py               # Flask application
├── templates/
│   ├── base.html        # Base template
│   └── index.html       # Home page
├── static/
│   └── style.css        # Styles
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Configuration

The `.fastband/config.yaml` file configures:

- AI provider settings
- Ticket management mode (CLI + Web UI)
- Tool loading preferences

See the config file for all available options.

## Next Steps

- Try creating more tickets and tracking your work
- Experiment with the MCP server and AI assistance
- Check out the `cli-tool-demo` for more CLI usage patterns
